import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
OPERATIONAL_DB = DATA_DIR / "cache.sqlite"


def _canonical_path(p: str) -> str:
    return os.path.normcase(os.path.realpath(os.path.abspath(p)))


def _is_within(candidate_path: str, base_dir: Path) -> bool:
    cand = _canonical_path(candidate_path)
    base = _canonical_path(str(base_dir))
    try:
        return os.path.commonpath([cand, base]) == base
    except ValueError:
        return False


def _load_playwright_cfg_via_node(extra_env: dict[str, str], *, cwd: Path | None = None) -> dict:
    script = """
const os = require('os');
const cfg = require('./playwright.config.js');
console.log(JSON.stringify({
  os_tmpdir: os.tmpdir(),
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
    pw_pkg = REPO_ROOT / "node_modules" / "@playwright" / "test" / "package.json"
    if not pw_pkg.exists():
        pnpm_pw = sorted((REPO_ROOT / "node_modules" / ".pnpm").glob("@playwright+test*"))
        if pnpm_pw:
            existing_np = env.get("NODE_PATH", "")
            pnpm_nm = str(pnpm_pw[0] / "node_modules")
            env["NODE_PATH"] = f"{pnpm_nm}{os.pathsep}{existing_np}" if existing_np else pnpm_nm

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


def _create_dir_junction(link_path: Path, target_path: Path) -> bool:
    if sys.platform != "win32":
        return False
    res = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link_path), str(target_path)],
        capture_output=True,
        text=True,
        timeout=15,
    )
    return res.returncode == 0


def _try_symlink(link_path: Path, target_path: str | Path) -> bool:
    try:
        os.symlink(str(target_path), str(link_path))
        return True
    except OSError:
        return False


def _remove_reparse_only(link_path: Path) -> None:
    if os.path.islink(link_path) or (hasattr(os.path, "isjunction") and os.path.isjunction(link_path)):
        try:
            if link_path.is_dir() and not os.path.islink(link_path):
                link_path.rmdir()
            else:
                link_path.unlink()
        except OSError:
            if os.path.isdir(link_path):
                link_path.rmdir()
            else:
                link_path.unlink()


def _create_synthetic_repo(base_dir: Path) -> tuple[Path, list[Path]]:
    """Build a synthetic mock repo data/ tree for CI environments lacking gitignored data/."""
    mock_repo = base_dir / "synthetic_pw_repo"
    mock_data = mock_repo / "data"
    mock_data.mkdir(parents=True, exist_ok=True)
    files = [
        mock_data / "cache.sqlite",
        mock_data / "cache.sqlite-wal",
        mock_data / "cache.sqlite-shm",
        mock_data / "cache.sqlite-journal",
        mock_data / "cache.sqlite.bak-pre-ashby-repair",
        mock_data / "cache.sqlite.bak-pre-greenhouse-synthetic-cleanup",
        mock_data / ".cache.sqlite.restore-staging-test",
    ]
    for idx, f in enumerate(files):
        f.write_bytes(f"synthetic-op-asset-{idx}".encode("utf-8"))
    (mock_repo / "subscriptions.csv").write_text("email,search_query,subscribed_at\n", encoding="utf-8")
    return mock_repo, files


def _snapshot_dir_hashes(target_dir: Path) -> dict[Path, tuple[int, str]]:
    if not target_dir.exists():
        return {}
    return {
        p: (p.stat().st_size, hashlib.sha256(p.read_bytes()).hexdigest())
        for p in sorted(target_dir.iterdir())
        if p.is_file()
    }


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
        assert not _is_within(safe_db, DATA_DIR)

        safe_sub = ws_env.get("SUBSCRIPTIONS_FILE")
        assert safe_sub
        assert safe_sub == payload["env_playwright_sub"]
        assert _canonical_path(safe_sub) != _canonical_path(str(REPO_ROOT / "subscriptions.csv"))
        assert not _is_within(safe_sub, DATA_DIR)

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
        assert not _is_within(safe_db, DATA_DIR)
        assert ":memory:" not in safe_db.lower()
        assert not safe_db.lower().startswith("file:")

    def test_existing_symlink_to_operational_target_rejected(self, tmp_path: Path):
        extra_env: dict[str, str] = {}
        forbidden_data_dir = DATA_DIR
        if OPERATIONAL_DB.exists():
            existing_target = OPERATIONAL_DB
        else:
            existing_backups = sorted(DATA_DIR.glob("cache.sqlite.bak-*")) if DATA_DIR.exists() else []
            if existing_backups:
                existing_target = existing_backups[0]
            else:
                mock_repo, mock_files = _create_synthetic_repo(tmp_path)
                existing_target = mock_files[0]
                forbidden_data_dir = mock_repo / "data"
                extra_env["BOTTOM_POT_TEST_EXTRA_PROTECTED_ROOT"] = str(mock_repo)

        link_path = tmp_path / "existing-op-link.sqlite"
        candidate_path: Path
        if _try_symlink(link_path, existing_target):
            candidate_path = link_path
        elif sys.platform == "win32":
            # Windows without Developer Mode / SeCreateSymbolicLinkPrivilege returns WinError 1314
            # for file symlinks; verify equivalent existing-target reparse aliasing via a directory junction.
            junc_dir = tmp_path / "existing-op-junction"
            assert _create_dir_junction(junc_dir, existing_target.parent), (
                "Neither file symlinks nor directory junctions could be created on Windows"
            )
            link_path = junc_dir
            candidate_path = junc_dir / existing_target.name
        else:
            pytest.fail("POSIX OS denied symlink creation for existing operational target test")

        try:
            extra_env.update(
                {
                    "PLAYWRIGHT_SQLITE_DB_PATH": str(candidate_path),
                    "SQLITE_DB_PATH": str(OPERATIONAL_DB),
                }
            )
            payload = _load_playwright_cfg_via_node(extra_env)
            safe_db = payload["env_playwright_db"]
            assert safe_db
            assert payload["ws_env"].get("SQLITE_DB_PATH") == safe_db
            assert _canonical_path(safe_db) != _canonical_path(str(candidate_path))
            assert not _is_within(safe_db, DATA_DIR)
            assert not _is_within(safe_db, forbidden_data_dir)
        finally:
            _remove_reparse_only(link_path)

    def test_dangling_link_to_missing_operational_db_rejected(self, tmp_path: Path):
        # Assert against a missing target inside operational data/ (regardless of whether data/cache.sqlite exists)
        missing_op_target = DATA_DIR / "cache.sqlite"
        if missing_op_target.exists():
            missing_op_target = DATA_DIR / "dangling_nonexistent_cache.sqlite"

        created_links: list[Path] = []
        try:
            # Case A: POSIX/Dev-mode dangling file symlink (both absolute and relative targets)
            sym_abs = tmp_path / "dangling-abs.sqlite"
            sym_rel = tmp_path / "dangling-rel.sqlite"
            has_file_sym = _try_symlink(sym_abs, missing_op_target)
            if has_file_sym:
                created_links.append(sym_abs)
                try:
                    rel_target = os.path.relpath(str(missing_op_target), str(tmp_path))
                except ValueError:
                    # Cross-drive CI layout (e.g. D:\ workspace vs C:\ temp): hop through a junction
                    # inside tmp_path so relative symlink resolution still resolves into DATA_DIR.
                    rel_data_junc = tmp_path / "rel_data_junc"
                    assert _create_dir_junction(rel_data_junc, DATA_DIR)
                    created_links.append(rel_data_junc)
                    rel_target = os.path.join(rel_data_junc.name, missing_op_target.name)
                assert _try_symlink(sym_rel, rel_target)
                created_links.append(sym_rel)
                for candidate in (sym_abs, sym_rel):
                    payload = _load_playwright_cfg_via_node(
                        {"PLAYWRIGHT_SQLITE_DB_PATH": str(candidate), "SQLITE_DB_PATH": str(OPERATIONAL_DB)}
                    )
                    safe_db = payload["env_playwright_db"]
                    assert safe_db and payload["ws_env"].get("SQLITE_DB_PATH") == safe_db
                    assert not _is_within(safe_db, DATA_DIR)
                    assert Path(safe_db).name != candidate.name

            # Case B: Unprivileged Windows dangling directory junction pointing directly at missing data/cache.sqlite
            if sys.platform == "win32":
                dangling_junc = tmp_path / "dangling-junc.sqlite"
                dangling_subdir_junc = tmp_path / "dangling-subdir-junc"
                assert _create_dir_junction(dangling_junc, missing_op_target)
                created_links.append(dangling_junc)
                assert _create_dir_junction(dangling_subdir_junc, DATA_DIR / "nonexistent_subdir")
                created_links.append(dangling_subdir_junc)

                for candidate in (dangling_junc, dangling_subdir_junc / "cache.sqlite"):
                    payload = _load_playwright_cfg_via_node(
                        {"PLAYWRIGHT_SQLITE_DB_PATH": str(candidate), "SQLITE_DB_PATH": str(OPERATIONAL_DB)}
                    )
                    safe_db = payload["env_playwright_db"]
                    assert safe_db and payload["ws_env"].get("SQLITE_DB_PATH") == safe_db
                    assert not _is_within(safe_db, DATA_DIR)
                    assert _canonical_path(safe_db) != _canonical_path(str(dangling_junc))
                    assert not _is_within(safe_db, dangling_subdir_junc)
            elif not has_file_sym:
                pytest.skip("OS does not permit symlink creation")
        finally:
            for link in reversed(created_links):
                _remove_reparse_only(link)

    def test_intermediate_directory_symlink_or_junction_rejected(self, tmp_path: Path):
        inter_link = tmp_path / "via_dir_link"
        if sys.platform == "win32":
            if not _create_dir_junction(inter_link, DATA_DIR):
                pytest.skip("Unable to create Windows directory junction")
        else:
            if not _try_symlink(inter_link, DATA_DIR):
                pytest.skip("OS does not permit directory symlink creation")

        try:
            candidate = inter_link / "cache.sqlite"
            payload = _load_playwright_cfg_via_node(
                {
                    "PLAYWRIGHT_SQLITE_DB_PATH": str(candidate),
                    "SQLITE_DB_PATH": str(OPERATIONAL_DB),
                }
            )
            safe_db = payload["env_playwright_db"]
            assert safe_db and payload["ws_env"].get("SQLITE_DB_PATH") == safe_db
            assert _canonical_path(safe_db) != _canonical_path(str(candidate))
            assert not _is_within(safe_db, DATA_DIR)
        finally:
            _remove_reparse_only(inter_link)

    def test_multilevel_symlink_or_junction_chain_rejected(self, tmp_path: Path):
        created_links: list[Path] = []
        try:
            if sys.platform == "win32":
                hop2 = tmp_path / "hop2_data"
                hop1 = tmp_path / "hop1_link"
                assert _create_dir_junction(hop2, DATA_DIR)
                created_links.append(hop2)
                assert _create_dir_junction(hop1, hop2)
                created_links.append(hop1)
                candidate = hop1 / "cache.sqlite"
            else:
                hop2 = tmp_path / "hop2.sqlite"
                hop1 = tmp_path / "hop1.sqlite"
                if not _try_symlink(hop2, OPERATIONAL_DB):
                    pytest.skip("OS does not permit symlink creation")
                created_links.append(hop2)
                if not _try_symlink(hop1, hop2):
                    pytest.skip("OS does not permit multi-level symlink creation")
                created_links.append(hop1)
                candidate = hop1

            # Also verify POSIX multi-level file symlinks when permitted on Windows Developer Mode
            payload = _load_playwright_cfg_via_node(
                {
                    "PLAYWRIGHT_SQLITE_DB_PATH": str(candidate),
                    "SQLITE_DB_PATH": str(OPERATIONAL_DB),
                }
            )
            safe_db = payload["env_playwright_db"]
            assert safe_db and payload["ws_env"].get("SQLITE_DB_PATH") == safe_db
            assert not _is_within(safe_db, DATA_DIR)
            assert _canonical_path(safe_db) != _canonical_path(str(hop1))
        finally:
            for link in reversed(created_links):
                _remove_reparse_only(link)

    def test_circular_reparse_or_symlink_loop_fails_closed(self, tmp_path: Path):
        created_links: list[Path] = []
        try:
            loop_a = tmp_path / "loop_a"
            loop_b = tmp_path / "loop_b"
            if sys.platform == "win32":
                assert _create_dir_junction(loop_a, loop_b)
                created_links.append(loop_a)
                assert _create_dir_junction(loop_b, loop_a)
                created_links.append(loop_b)
                candidate = loop_a / "cache.sqlite"
            else:
                if not _try_symlink(loop_a, loop_b):
                    pytest.skip("OS does not permit symlink creation")
                created_links.append(loop_a)
                assert _try_symlink(loop_b, loop_a)
                created_links.append(loop_b)
                candidate = loop_a

            payload = _load_playwright_cfg_via_node(
                {
                    "PLAYWRIGHT_SQLITE_DB_PATH": str(candidate),
                    "SQLITE_DB_PATH": str(OPERATIONAL_DB),
                }
            )
            safe_db = payload["env_playwright_db"]
            assert safe_db and payload["ws_env"].get("SQLITE_DB_PATH") == safe_db
            assert not _is_within(safe_db, DATA_DIR)
            assert not _is_within(safe_db, tmp_path)
        finally:
            for link in reversed(created_links):
                _remove_reparse_only(link)

    def test_sibling_prefix_temp_root_accepted_and_concurrent_runs_isolated(self, tmp_path: Path):
        # Verify sibling-prefix name collision safety in TEMP root AND that concurrent
        # Playwright loads allocate distinct disposable DB paths overriding inherited values.
        custom_db = tmp_path / "custom-e2e.sqlite"
        sibling_prefix_dir = tmp_path / f"{tmp_path.name}Evil"
        sibling_prefix_dir.mkdir(parents=True, exist_ok=True)

        p1 = _load_playwright_cfg_via_node(
            {
                "TEMP": str(sibling_prefix_dir),
                "TMP": str(sibling_prefix_dir),
                "TMPDIR": str(sibling_prefix_dir),
                "PLAYWRIGHT_SQLITE_DB_PATH": str(custom_db),
                "SQLITE_DB_PATH": str(OPERATIONAL_DB),
                "PLAYWRIGHT_REUSE_SERVER": "1",
            }
        )
        p2 = _load_playwright_cfg_via_node(
            {
                "TEMP": str(sibling_prefix_dir),
                "TMP": str(sibling_prefix_dir),
                "TMPDIR": str(sibling_prefix_dir),
                "PLAYWRIGHT_SQLITE_DB_PATH": str(custom_db),
                "SQLITE_DB_PATH": str(OPERATIONAL_DB),
                "PLAYWRIGHT_REUSE_SERVER": "1",
            }
        )

        for payload in (p1, p2):
            db = payload["env_playwright_db"]
            assert db
            assert _is_within(db, sibling_prefix_dir)
            assert _canonical_path(db) != _canonical_path(str(custom_db))
            assert _canonical_path(payload["ws_env"]["SQLITE_DB_PATH"]) == _canonical_path(db)
            assert payload["ws_env"]["MONITORING_ENABLED"] == "false"
            assert payload["ws_env"]["BOTTOM_POT_TEST_MODE"] == "1"
            assert payload["reuse_existing_server"] is False

        assert _canonical_path(p1["env_playwright_db"]) != _canonical_path(p2["env_playwright_db"])
        assert Path(p1["env_playwright_db"]).parent != Path(p2["env_playwright_db"]).parent

    def test_inherited_sqlite_db_path_without_playwright_var_is_ignored(self):
        payload = _load_playwright_cfg_via_node({"SQLITE_DB_PATH": str(OPERATIONAL_DB)})
        safe_db = payload["env_playwright_db"]
        assert safe_db
        assert payload["ws_env"]["SQLITE_DB_PATH"] == safe_db
        assert _canonical_path(safe_db) != _canonical_path(str(OPERATIONAL_DB))
        assert not _is_within(safe_db, DATA_DIR)

    def test_loaded_webserver_env_routes_app_startup_to_isolated_tmp_path(self, tmp_path: Path):
        before_real_snap = _snapshot_dir_hashes(DATA_DIR)
        mock_repo, _ = _create_synthetic_repo(tmp_path)
        mock_data_dir = mock_repo / "data"
        before_mock_snap = _snapshot_dir_hashes(mock_data_dir)

        isolated_tmp = tmp_path / "e2e_os_tmpdir"
        isolated_tmp.mkdir(parents=True, exist_ok=True)

        payload = _load_playwright_cfg_via_node(
            {
                "PLAYWRIGHT_SQLITE_DB_PATH": str(OPERATIONAL_DB),
                "SQLITE_DB_PATH": str(OPERATIONAL_DB),
                "BOTTOM_POT_ALLOW_OPERATIONAL_DB": "1",
                "BOTTOM_POT_TEST_EXTRA_PROTECTED_ROOT": str(mock_repo),
                "PLAYWRIGHT_REUSE_SERVER": "1",
                "TMPDIR": str(isolated_tmp),
                "TEMP": str(isolated_tmp),
                "TMP": str(isolated_tmp),
            }
        )
        ws_env = {str(k): str(v) for k, v in payload["ws_env"].items()}
        safe_db = ws_env["SQLITE_DB_PATH"]
        assert _canonical_path(payload["os_tmpdir"]) == _canonical_path(str(isolated_tmp))
        assert payload["env_playwright_db"] == safe_db
        assert ws_env.get("BOTTOM_POT_ALLOW_OPERATIONAL_DB") == "0"
        assert _is_within(safe_db, isolated_tmp)
        assert not _is_within(safe_db, DATA_DIR)
        assert not _is_within(safe_db, mock_data_dir)

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
        assert _is_within(resolved["registry_db"], isolated_tmp)
        assert resolved["monitoring"] is False
        assert os.path.exists(safe_db)

        assert _snapshot_dir_hashes(DATA_DIR) == before_real_snap
        assert _snapshot_dir_hashes(mock_data_dir) == before_mock_snap

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

    @pytest.mark.parametrize("temp_var", ["TEMP", "TMP", "TMPDIR", "ALL"])
    def test_hostile_temp_env_vars_never_poison_fallback(self, temp_var: str):
        hostile_dir = str(DATA_DIR)
        extra_env: dict[str, str] = {
            "PLAYWRIGHT_SQLITE_DB_PATH": str(OPERATIONAL_DB),
            "PLAYWRIGHT_SUBSCRIPTIONS_FILE": str(REPO_ROOT / "subscriptions.csv"),
        }
        if temp_var == "ALL":
            extra_env["TEMP"] = hostile_dir
            extra_env["TMP"] = hostile_dir
            extra_env["TMPDIR"] = hostile_dir
        else:
            extra_env[temp_var] = hostile_dir

        # Run Node without pre-starting FastAPI or SQLite; verify fallback resolves safely outside data/
        script = """
const cfg = require('./playwright.config.js');
console.log(JSON.stringify({
  env_playwright_db: process.env.PLAYWRIGHT_SQLITE_DB_PATH || null,
  env_playwright_sub: process.env.PLAYWRIGHT_SUBSCRIPTIONS_FILE || null,
  ws_env: (cfg.webServer && cfg.webServer.env) || {},
}));
"""
        env = os.environ.copy()
        for k in (
            "PLAYWRIGHT_SQLITE_DB_PATH",
            "SQLITE_DB_PATH",
            "PLAYWRIGHT_SUBSCRIPTIONS_FILE",
            "SUBSCRIPTIONS_FILE",
            "TEMP",
            "TMP",
            "TMPDIR",
        ):
            env.pop(k, None)
        env.update(extra_env)
        pw_pkg = REPO_ROOT / "node_modules" / "@playwright" / "test" / "package.json"
        if not pw_pkg.exists():
            pnpm_pw = sorted((REPO_ROOT / "node_modules" / ".pnpm").glob("@playwright+test*"))
            if pnpm_pw:
                env["NODE_PATH"] = str(pnpm_pw[0] / "node_modules")

        proc = subprocess.run(
            ["node", "-e", script],
            cwd=str(REPO_ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=25,
        )
        if proc.returncode != 0:
            # Fail closed on hostile environment is acceptable if configuration refused to start
            assert "safe" in proc.stderr.lower() or "temporary" in proc.stderr.lower()
            return

        payload = json.loads(proc.stdout.strip())
        safe_db = payload["env_playwright_db"]
        safe_sub = payload["env_playwright_sub"]
        ws_env = payload["ws_env"]
        assert safe_db and ws_env.get("SQLITE_DB_PATH") == safe_db
        assert safe_sub and ws_env.get("SUBSCRIPTIONS_FILE") == safe_sub
        assert not _is_within(safe_db, DATA_DIR)
        assert not _is_within(safe_sub, DATA_DIR)
        assert _canonical_path(safe_db) != _canonical_path(str(OPERATIONAL_DB))

    def test_temp_dir_symlink_or_junction_into_data_rejected(self, tmp_path: Path):
        poison_tmp = tmp_path / "tmp_junction_to_data"
        if sys.platform == "win32":
            if not _create_dir_junction(poison_tmp, DATA_DIR):
                pytest.skip("Unable to create Windows directory junction")
        else:
            if not _try_symlink(poison_tmp, DATA_DIR):
                pytest.skip("OS does not permit directory symlink creation")

        try:
            payload = _load_playwright_cfg_via_node(
                {
                    "TEMP": str(poison_tmp),
                    "TMP": str(poison_tmp),
                    "TMPDIR": str(poison_tmp),
                }
            )
            safe_db = payload["env_playwright_db"]
            safe_sub = payload["env_playwright_sub"]
            ws_env = payload["ws_env"]
            assert safe_db and ws_env.get("SQLITE_DB_PATH") == safe_db
            assert safe_sub and ws_env.get("SUBSCRIPTIONS_FILE") == safe_sub
            assert not _is_within(safe_db, DATA_DIR)
            assert not _is_within(safe_sub, DATA_DIR)
            assert not _is_within(safe_db, poison_tmp)
            assert not _is_within(safe_sub, poison_tmp)
        finally:
            _remove_reparse_only(poison_tmp)

    def test_legitimate_isolated_temp_root_accepted(self, tmp_path: Path):
        safe_tmp = tmp_path / "legit_tmp"
        safe_tmp.mkdir(parents=True, exist_ok=True)
        payload = _load_playwright_cfg_via_node(
            {
                "TEMP": str(safe_tmp),
                "TMP": str(safe_tmp),
                "TMPDIR": str(safe_tmp),
            }
        )
        safe_db = payload["env_playwright_db"]
        safe_sub = payload["env_playwright_sub"]
        assert safe_db and payload["ws_env"].get("SQLITE_DB_PATH") == safe_db
        assert safe_sub and payload["ws_env"].get("SUBSCRIPTIONS_FILE") == safe_sub
        assert _is_within(safe_db, safe_tmp)
        assert _is_within(safe_sub, safe_tmp)
        assert not _is_within(safe_db, DATA_DIR)

    def test_hardlink_aliases_to_existing_backups_and_sidecars_rejected(self, tmp_path: Path):
        mock_repo, mock_files = _create_synthetic_repo(tmp_path)
        mock_data_dir = mock_repo / "data"
        real_files = (
            sorted(p for p in DATA_DIR.iterdir() if p.is_file() and "cache.sqlite" in p.name)
            if DATA_DIR.exists()
            else []
        )
        targets = [*mock_files, *real_files]

        tested_count = 0
        for backup_path in targets:
            before_stat = backup_path.stat()
            before_hash = hashlib.sha256(backup_path.read_bytes()).hexdigest()
            alias_path = tmp_path / f"hardlink_{tested_count}_{backup_path.name}.sqlite"
            try:
                os.link(str(backup_path), str(alias_path))
            except OSError as exc:
                if tested_count == 0:
                    pytest.skip(f"Platform/filesystem does not permit hard links ({exc})")
                continue

            tested_count += 1
            try:
                assert _is_within(str(alias_path), tmp_path)
                payload = _load_playwright_cfg_via_node(
                    {
                        "PLAYWRIGHT_SQLITE_DB_PATH": str(alias_path),
                        "SQLITE_DB_PATH": str(OPERATIONAL_DB),
                        "BOTTOM_POT_TEST_EXTRA_PROTECTED_ROOT": str(mock_repo),
                    }
                )
                safe_db = payload["env_playwright_db"]
                ws_env = payload["ws_env"]
                assert safe_db and ws_env.get("SQLITE_DB_PATH") == safe_db
                assert _canonical_path(safe_db) != _canonical_path(str(alias_path))
                assert not _is_within(safe_db, DATA_DIR)
                assert not _is_within(safe_db, mock_data_dir)
                assert not _is_within(safe_db, tmp_path)
            finally:
                if _is_within(str(alias_path), tmp_path) and alias_path.exists():
                    alias_path.unlink()

            after_stat = backup_path.stat()
            after_hash = hashlib.sha256(backup_path.read_bytes()).hexdigest()
            assert after_stat.st_size == before_stat.st_size
            assert after_stat.st_mtime_ns == before_stat.st_mtime_ns
            assert after_hash == before_hash

        assert tested_count >= 1

    def test_no_safe_temp_root_available_fails_closed(self):
        if sys.platform != "win32":
            pytest.skip("System /tmp exists outside env vars on POSIX; fail-closed fallback throw tested on win32")

        env = os.environ.copy()
        for k in (
            "PLAYWRIGHT_SQLITE_DB_PATH",
            "SQLITE_DB_PATH",
            "PLAYWRIGHT_SUBSCRIPTIONS_FILE",
            "SUBSCRIPTIONS_FILE",
        ):
            env.pop(k, None)
        env.update(
            {
                "TEMP": str(DATA_DIR),
                "TMP": str(DATA_DIR),
                "TMPDIR": str(DATA_DIR),
                "LOCALAPPDATA": str(DATA_DIR),
                "USERPROFILE": str(DATA_DIR),
                "TEST_HOSTILE_TMP": str(DATA_DIR),
            }
        )
        pw_pkg = REPO_ROOT / "node_modules" / "@playwright" / "test" / "package.json"
        if not pw_pkg.exists():
            pnpm_pw = sorted((REPO_ROOT / "node_modules" / ".pnpm").glob("@playwright+test*"))
            if pnpm_pw:
                env["NODE_PATH"] = str(pnpm_pw[0] / "node_modules")

        script = (
            "const os = require('os');"
            "os.tmpdir = () => process.env.TEST_HOSTILE_TMP;"
            "process.env.SystemRoot = process.env.TEST_HOSTILE_TMP;"
            "require('./playwright.config.js');"
        )
        proc = subprocess.run(
            ["node", "-e", script],
            cwd=str(REPO_ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=25,
        )
        assert proc.returncode != 0
        assert "Playwright E2E isolation failure" in proc.stderr
