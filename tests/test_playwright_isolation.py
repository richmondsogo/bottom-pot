import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
OPERATIONAL_DB = REPO_ROOT / "data" / "cache.sqlite"


def _load_playwright_cfg_via_node(extra_env: dict[str, str], *, cwd: Path | None = None) -> dict:
    script = """
const cfg = require('./playwright.config.js');
console.log(JSON.stringify({
  env_playwright_db: process.env.PLAYWRIGHT_SQLITE_DB_PATH || null,
  env_playwright_sub: process.env.PLAYWRIGHT_SUBSCRIPTIONS_FILE || null,
  reuse_existing_server: cfg.webServer && cfg.webServer.reuseExistingServer,
  ws_env: (cfg.webServer && cfg.webServer.env) || {},
}));
"""
    env = os.environ.copy()
    for key in (
        "PLAYWRIGHT_SQLITE_DB_PATH",
        "SQLITE_DB_PATH",
        "PLAYWRIGHT_SUBSCRIPTIONS_FILE",
        "SUBSCRIPTIONS_FILE",
        "PLAYWRIGHT_REUSE_SERVER",
        "MONITORING_ENABLED",
    ):
        env.pop(key, None)
    env.update(extra_env)

    proc = subprocess.run(
        ["node", "-e", script],
        cwd=str(cwd or REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=True,
        timeout=25,
    )
    return json.loads(proc.stdout.strip())


def _canonical_path(p: str) -> str:
    return os.path.normcase(os.path.realpath(os.path.abspath(p)))


class TestPlaywrightDatabaseIsolation:
    """Fail-closed regression tests for playwright.config.js and scripts/verify.ps1."""

    def test_hostile_inherited_operational_db_path_replaced(self):
        before_stat = OPERATIONAL_DB.stat() if OPERATIONAL_DB.exists() else None
        payload = _load_playwright_cfg_via_node(
            {
                "PLAYWRIGHT_SQLITE_DB_PATH": str(OPERATIONAL_DB),
                "SQLITE_DB_PATH": str(OPERATIONAL_DB),
                "PLAYWRIGHT_SUBSCRIPTIONS_FILE": str(REPO_ROOT / "subscriptions.csv"),
                "SUBSCRIPTIONS_FILE": str(REPO_ROOT / "subscriptions.csv"),
                "PLAYWRIGHT_REUSE_SERVER": "1",
                "MONITORING_ENABLED": "true",
            }
        )

        safe_db = payload["env_playwright_db"]
        ws_env = payload["ws_env"]
        assert safe_db
        assert ws_env.get("SQLITE_DB_PATH") == safe_db
        assert ws_env.get("PLAYWRIGHT_SQLITE_DB_PATH") == safe_db
        assert _canonical_path(safe_db) != _canonical_path(str(OPERATIONAL_DB))
        assert _canonical_path(os.path.dirname(safe_db)) != _canonical_path(str(REPO_ROOT / "data"))

        safe_sub = ws_env.get("SUBSCRIPTIONS_FILE")
        assert safe_sub
        assert safe_sub == payload["env_playwright_sub"]
        assert _canonical_path(safe_sub) != _canonical_path(str(REPO_ROOT / "subscriptions.csv"))

        assert ws_env.get("MONITORING_ENABLED") == "false"

        if before_stat is not None:
            after_stat = OPERATIONAL_DB.stat()
            assert after_stat.st_mtime_ns == before_stat.st_mtime_ns
            assert after_stat.st_size == before_stat.st_size

    @pytest.mark.parametrize(
        "hostile_value",
        [
            "data/cache.sqlite",
            "DATA\\CACHE.SQLITE",
            "./data/../data/cache.sqlite",
            "data/other.sqlite",
            ":memory:",
            "file:data/cache.sqlite",
            "   ",
        ],
    )
    def test_hostile_variants_fail_closed_to_temp_db(self, hostile_value: str):
        payload = _load_playwright_cfg_via_node(
            {
                "PLAYWRIGHT_SQLITE_DB_PATH": hostile_value,
                "SQLITE_DB_PATH": str(OPERATIONAL_DB),
            }
        )
        safe_db = payload["env_playwright_db"]
        ws_env = payload["ws_env"]
        assert safe_db
        assert ws_env.get("SQLITE_DB_PATH") == safe_db
        assert _canonical_path(safe_db) != _canonical_path(str(OPERATIONAL_DB))
        assert not _canonical_path(safe_db).startswith(_canonical_path(str(REPO_ROOT / "data")))
        assert ":memory:" not in safe_db.lower()
        assert not safe_db.lower().startswith("file:")

    def test_symlink_to_operational_db_or_dir_is_rejected(self, tmp_path: Path):
        link_path = tmp_path / "linked-cache.sqlite"
        cleanup_junction: Path | None = None
        if sys.platform == "win32":
            junction_dir = tmp_path / "linked_data"
            res = subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(junction_dir), str(REPO_ROOT / "data")],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if res.returncode != 0:
                pytest.skip("Unable to create Windows directory junction")
            cleanup_junction = junction_dir
            target_to_test = junction_dir / "cache.sqlite"
        else:
            try:
                os.symlink(OPERATIONAL_DB, link_path)
                target_to_test = link_path
            except OSError:
                pytest.skip("OS privilege unavailable for symlink creation")

        try:
            payload = _load_playwright_cfg_via_node(
                {
                    "PLAYWRIGHT_SQLITE_DB_PATH": str(target_to_test),
                    "SQLITE_DB_PATH": str(OPERATIONAL_DB),
                }
            )
            safe_db = payload["env_playwright_db"]
            ws_env = payload["ws_env"]
            assert safe_db
            assert ws_env.get("SQLITE_DB_PATH") == safe_db
            assert _canonical_path(safe_db) != _canonical_path(str(target_to_test))
            assert _canonical_path(safe_db) != _canonical_path(str(OPERATIONAL_DB))
        finally:
            if cleanup_junction is not None and cleanup_junction.exists():
                cleanup_junction.rmdir()

    def test_explicit_safe_temp_path_is_accepted_and_ignores_hostile_sqlite_env(self, tmp_path: Path):
        custom_db = tmp_path / "custom-e2e.sqlite"
        payload = _load_playwright_cfg_via_node(
            {
                "PLAYWRIGHT_SQLITE_DB_PATH": str(custom_db),
                "SQLITE_DB_PATH": str(OPERATIONAL_DB),
            }
        )
        assert _canonical_path(payload["env_playwright_db"]) == _canonical_path(str(custom_db))
        assert _canonical_path(payload["ws_env"]["SQLITE_DB_PATH"]) == _canonical_path(str(custom_db))
        assert payload["ws_env"]["MONITORING_ENABLED"] == "false"

    def test_inherited_sqlite_db_path_without_playwright_var_is_ignored(self):
        payload = _load_playwright_cfg_via_node({"SQLITE_DB_PATH": str(OPERATIONAL_DB)})
        safe_db = payload["env_playwright_db"]
        assert safe_db
        assert payload["ws_env"]["SQLITE_DB_PATH"] == safe_db
        assert _canonical_path(safe_db) != _canonical_path(str(OPERATIONAL_DB))
        assert not _canonical_path(safe_db).startswith(_canonical_path(str(REPO_ROOT / "data")))

    def test_loaded_webserver_env_routes_app_startup_to_isolated_db(self, tmp_path: Path):
        before_stat = OPERATIONAL_DB.stat() if OPERATIONAL_DB.exists() else None
        payload = _load_playwright_cfg_via_node(
            {
                "PLAYWRIGHT_SQLITE_DB_PATH": str(OPERATIONAL_DB),
                "SQLITE_DB_PATH": str(OPERATIONAL_DB),
                "PLAYWRIGHT_REUSE_SERVER": "1",
            }
        )
        ws_env = {str(k): str(v) for k, v in payload["ws_env"].items()}
        safe_db = ws_env["SQLITE_DB_PATH"]
        assert payload["env_playwright_db"] == safe_db
        # Fail before running or cleaning up if safe_db could ever point outside temp dir
        assert _canonical_path(safe_db) != _canonical_path(str(OPERATIONAL_DB))
        assert _canonical_path(safe_db).startswith(_canonical_path(tempfile.gettempdir()))
        try:
            probe_code = (
                "import json; "
                "from src.config import settings; "
                "from src.project_files.company_board_registry import CompanyBoardRegistry; "
                "reg = CompanyBoardRegistry(); "
                "print(json.dumps({'settings_db': settings.sqlite_db_path, 'registry_db': reg.db_path, 'monitoring': settings.monitoring_enabled}))"
            )
            proc = subprocess.run(
                [sys.executable, "-c", probe_code],
                cwd=str(REPO_ROOT),
                env=ws_env,
                capture_output=True,
                text=True,
                check=True,
                timeout=25,
            )
            resolved = json.loads(proc.stdout.strip())
            assert _canonical_path(resolved["settings_db"]) == _canonical_path(safe_db)
            assert _canonical_path(resolved["registry_db"]) == _canonical_path(safe_db)
            assert resolved["monitoring"] is False
            assert os.path.exists(safe_db)
        finally:
            if _canonical_path(safe_db).startswith(_canonical_path(tempfile.gettempdir())):
                for suffix in ("", "-wal", "-shm"):
                    p = Path(safe_db + suffix)
                    if p.exists():
                        p.unlink()

        if before_stat is not None:
            after_stat = OPERATIONAL_DB.stat()
            assert after_stat.st_mtime_ns == before_stat.st_mtime_ns
            assert after_stat.st_size == before_stat.st_size

    @pytest.mark.parametrize("shim_exit_code", [0, 1])
    def test_verify_ps1_forces_reuse_server_zero_and_restores_env(self, tmp_path: Path, shim_exit_code: int):
        if shutil.which("powershell") is None:
            pytest.skip("powershell not installed")

        shim_dir = tmp_path / "shim"
        shim_dir.mkdir(parents=True, exist_ok=True)
        record_file = tmp_path / "recorded_env.json"

        shim_script = tmp_path / "record_npx.py"
        shim_script.write_text(
            "import json, os, pathlib, sys\n"
            f"record_path = pathlib.Path(r'{str(record_file)}')\n"
            "data = {\n"
            "  'args': sys.argv[1:],\n"
            "  'PLAYWRIGHT_REUSE_SERVER': os.environ.get('PLAYWRIGHT_REUSE_SERVER'),\n"
            "  'PLAYWRIGHT_BASE_URL': os.environ.get('PLAYWRIGHT_BASE_URL'),\n"
            "  'PLAYWRIGHT_SQLITE_DB_PATH': os.environ.get('PLAYWRIGHT_SQLITE_DB_PATH'),\n"
            "  'PLAYWRIGHT_SUBSCRIPTIONS_FILE': os.environ.get('PLAYWRIGHT_SUBSCRIPTIONS_FILE'),\n"
            "  'db_dir_exists': os.path.isdir(os.path.dirname(os.environ.get('PLAYWRIGHT_SQLITE_DB_PATH', ''))),\n"
            "}\n"
            "record_path.write_text(json.dumps(data), encoding='utf-8')\n"
            f"sys.exit({shim_exit_code})\n",
            encoding="utf-8",
        )
        (shim_dir / "npx.cmd").write_text(
            f'@echo off\r\n"{sys.executable}" "{shim_script}" %*\r\n',
            encoding="utf-8",
        )

        sentinel_db = str(OPERATIONAL_DB)
        sentinel_sub = str(REPO_ROOT / "subscriptions.csv")
        sentinel_url = "http://127.0.0.1:9999"

        ps_cmd = (
            "$ErrorActionPreference = 'Stop'; "
            f"$verifyScript = '{str(REPO_ROOT / 'scripts' / 'verify.ps1')}'; "
            "if (-not (Get-Command $verifyScript).Parameters.ContainsKey('E2EOnly')) { "
            "  Write-Error 'verify.ps1 missing -E2EOnly parameter'; exit 2 "
            "}; "
            "& $verifyScript -E2EOnly; "
            "$verifyCode = $LASTEXITCODE; "
            "$after = @{"
            "  PLAYWRIGHT_REUSE_SERVER = $env:PLAYWRIGHT_REUSE_SERVER;"
            "  PLAYWRIGHT_BASE_URL = $env:PLAYWRIGHT_BASE_URL;"
            "  PLAYWRIGHT_SQLITE_DB_PATH = $env:PLAYWRIGHT_SQLITE_DB_PATH;"
            "  PLAYWRIGHT_SUBSCRIPTIONS_FILE = $env:PLAYWRIGHT_SUBSCRIPTIONS_FILE;"
            "  verify_exit = $verifyCode"
            "}; "
            "Write-Output ('__AFTER__' + ($after | ConvertTo-Json -Compress)); "
            "exit $verifyCode"
        )

        env = os.environ.copy()
        env["PATH"] = f"{shim_dir}{os.pathsep}{env.get('PATH', '')}"
        env["PLAYWRIGHT_REUSE_SERVER"] = "1"
        env["PLAYWRIGHT_SQLITE_DB_PATH"] = sentinel_db
        env["PLAYWRIGHT_SUBSCRIPTIONS_FILE"] = sentinel_sub
        env["PLAYWRIGHT_BASE_URL"] = sentinel_url

        proc = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd],
            cwd=str(REPO_ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=25,
        )
        assert proc.returncode == shim_exit_code
        assert record_file.exists()

        during = json.loads(record_file.read_text(encoding="utf-8"))
        assert during["args"] == ["playwright", "test"]
        assert during["PLAYWRIGHT_REUSE_SERVER"] == "0"
        assert during["PLAYWRIGHT_BASE_URL"] == "http://127.0.0.1:8000"
        assert during["db_dir_exists"] is True
        assert _canonical_path(during["PLAYWRIGHT_SQLITE_DB_PATH"]) != _canonical_path(sentinel_db)
        assert _canonical_path(during["PLAYWRIGHT_SUBSCRIPTIONS_FILE"]) != _canonical_path(sentinel_sub)

        after_line = [ln for ln in proc.stdout.splitlines() if ln.startswith("__AFTER__")][-1]
        after = json.loads(after_line[len("__AFTER__"):])
        assert after["PLAYWRIGHT_REUSE_SERVER"] == "1"
        assert after["PLAYWRIGHT_BASE_URL"] == sentinel_url
        assert after["PLAYWRIGHT_SQLITE_DB_PATH"] == sentinel_db
        assert after["PLAYWRIGHT_SUBSCRIPTIONS_FILE"] == sentinel_sub
        assert not os.path.isdir(os.path.dirname(during["PLAYWRIGHT_SQLITE_DB_PATH"]))
