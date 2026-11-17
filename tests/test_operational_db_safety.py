"""Regression tests for Layer 1-6 permanent operational SQLite DB safety controls."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
OPERATIONAL_DB = DATA_DIR / "cache.sqlite"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _snapshot_protected_assets() -> dict[Path, tuple[int, str]]:
    snap: dict[Path, tuple[int, str]] = {}
    if DATA_DIR.exists():
        for entry in sorted(DATA_DIR.iterdir()):
            if entry.is_file():
                snap[entry] = (entry.stat().st_size, _sha256(entry))
    return snap


def _make_synthetic_repo(root: Path) -> tuple[Path, Path, dict[Path, tuple[int, str]]]:
    """Create a realistic isolated mock repo data/ layout with DB, sidecars, and backups."""
    mock_repo = root / "synthetic_repo"
    mock_data = mock_repo / "data"
    mock_data.mkdir(parents=True, exist_ok=True)
    mock_op_db = mock_data / "cache.sqlite"
    with sqlite3.connect(str(mock_op_db)) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS sentinel (id INTEGER PRIMARY KEY, val TEXT)")
        conn.execute("INSERT OR REPLACE INTO sentinel (id, val) VALUES (1, 'preserved')")
        conn.commit()
    (mock_data / "cache.sqlite-wal").write_bytes(b"synthetic-wal-bytes")
    (mock_data / "cache.sqlite-shm").write_bytes(b"synthetic-shm-bytes")
    (mock_data / "cache.sqlite-journal").write_bytes(b"synthetic-journal-bytes")
    (mock_data / "cache.sqlite.bak-pre-ashby-repair").write_bytes(b"synthetic-backup-ashby")
    (mock_data / "cache.sqlite.bak-pre-greenhouse-synthetic-cleanup").write_bytes(b"synthetic-backup-gh")
    (mock_data / ".cache.sqlite.restore-staging-a67a7e88-8b18-4675-874f-f3d9e3387d90").write_bytes(
        b"synthetic-staging"
    )
    (mock_repo / "subscriptions.csv").write_text("email,search_query,subscribed_at\n", encoding="utf-8")
    snap = {
        p: (p.stat().st_size, _sha256(p))
        for p in sorted(mock_data.iterdir())
        if p.is_file()
    }
    return mock_repo, mock_op_db, snap


def _clean_non_test_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    """Build a subprocess environment stripped of ALL test/CI/operational override flags."""
    env = os.environ.copy()
    for key in (
        "PYTEST_CURRENT_TEST",
        "PLAYWRIGHT_TEST",
        "PLAYWRIGHT_SQLITE_DB_PATH",
        "PLAYWRIGHT_SUBSCRIPTIONS_FILE",
        "BOTTOM_POT_TEST_MODE",
        "BOTTOM_POT_ALLOW_OPERATIONAL_DB",
        "BOTTOM_POT_TEST_EXTRA_PROTECTED_ROOT",
        "TESTING",
        "CI",
        "SQLITE_DB_PATH",
        "SUBSCRIPTIONS_FILE",
    ):
        env.pop(key, None)
    if extra:
        env.update(extra)
    return env


def test_db_safety_rejects_operational_db_and_variants_in_test_context():
    from src.project_files.db_safety import UnsafeDatabasePathError, assert_safe_sqlite_db_path

    hostile_inputs = [
        str(OPERATIONAL_DB),
        "data/cache.sqlite",
        "DATA\\CACHE.SQLITE",
        "./data/../data/cache.sqlite",
        "data/subdir/../cache.sqlite",
        "file:data/cache.sqlite",
        f"file:///{OPERATIONAL_DB.as_posix()}?mode=rwc",
        str(DATA_DIR / "cache.sqlite-wal"),
        str(DATA_DIR / "cache.sqlite-shm"),
        str(DATA_DIR / "cache.sqlite-journal"),
        str(DATA_DIR / "cache.sqlite.bak-pre-ashby-repair"),
        str(DATA_DIR / "cache.sqlite.bak-pre-greenhouse-synthetic-cleanup"),
        str(DATA_DIR / "cache.sqlite.bak-pre-greenhouse-synthetic-cleanup-wal"),
        str(DATA_DIR / "cache.sqlite.bak-pre-greenhouse-synthetic-cleanup-shm"),
        str(DATA_DIR / ".cache.sqlite.restore-staging-a67a7e88-8b18-4675-874f-f3d9e3387d90"),
        str(DATA_DIR / "arbitrary_other.sqlite"),
        "",
        "   ",
        str(DATA_DIR) + os.sep,
    ]
    for candidate in hostile_inputs:
        with pytest.raises(UnsafeDatabasePathError):
            assert_safe_sqlite_db_path(candidate, context="test")


def test_setting_testing_or_ci_flags_never_allows_operational_path(monkeypatch: pytest.MonkeyPatch):
    from src.project_files.db_safety import UnsafeDatabasePathError, assert_safe_sqlite_db_path

    monkeypatch.setenv("TESTING", "true")
    monkeypatch.setenv("CI", "true")
    monkeypatch.setenv("BOTTOM_POT_TEST_MODE", "1")

    with pytest.raises(UnsafeDatabasePathError):
        assert_safe_sqlite_db_path("data/cache.sqlite")
    with pytest.raises(UnsafeDatabasePathError):
        assert_safe_sqlite_db_path("data/cache.sqlite.bak-pre-ashby-repair")


def test_valid_disposable_and_memory_paths_accepted(tmp_path: Path):
    from src.project_files.db_safety import assert_safe_sqlite_db_path

    safe_file = tmp_path / "unit_cache.sqlite"
    assert Path(assert_safe_sqlite_db_path(str(safe_file), context="test")) == Path(os.path.realpath(safe_file))
    assert assert_safe_sqlite_db_path(":memory:", context="test") == ":memory:"


def test_hardlink_and_directory_target_rejected(tmp_path: Path):
    from src.project_files.db_safety import UnsafeDatabasePathError, assert_safe_sqlite_db_path

    sub_dir = tmp_path / "dir_not_file"
    sub_dir.mkdir()
    with pytest.raises(UnsafeDatabasePathError):
        assert_safe_sqlite_db_path(str(sub_dir), context="test")

    if OPERATIONAL_DB.exists():
        alias = tmp_path / "hardlink_op.sqlite"
        try:
            os.link(str(OPERATIONAL_DB), str(alias))
        except OSError as exc:
            pytest.skip(f"Hard links unsupported on filesystem: {exc}")
        try:
            with pytest.raises(UnsafeDatabasePathError):
                assert_safe_sqlite_db_path(str(alias), context="test")
        finally:
            if alias.exists():
                alias.unlink()


def test_cleanup_requires_verified_ownership_and_rejects_protected_assets(tmp_path: Path):
    from src.project_files.db_safety import (
        OwnedDisposableWorkspace,
        UnsafeDatabasePathError,
        safe_cleanup_disposable_path,
    )

    workspace = OwnedDisposableWorkspace.create(prefix="test-safety-")
    try:
        owned_file = workspace.root / "temp.sqlite"
        owned_file.write_text("disposable", encoding="utf-8")
        assert safe_cleanup_disposable_path(owned_file, owned_root=workspace.root) is True
        assert not owned_file.exists()

        stranger_file = tmp_path / "stranger.sqlite"
        stranger_file.write_text("keep-me", encoding="utf-8")
        with pytest.raises(UnsafeDatabasePathError):
            safe_cleanup_disposable_path(stranger_file, owned_root=workspace.root)
        assert stranger_file.exists()

        for protected in (
            OPERATIONAL_DB,
            DATA_DIR / "cache.sqlite-wal",
            DATA_DIR / "cache.sqlite-shm",
            DATA_DIR / "cache.sqlite-journal",
            DATA_DIR / "cache.sqlite.bak-pre-ashby-repair",
        ):
            with pytest.raises(UnsafeDatabasePathError):
                safe_cleanup_disposable_path(protected, owned_root=workspace.root)
    finally:
        workspace.cleanup()


def test_junction_or_symlink_into_data_rejected_by_db_safety_and_cleanup(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    from src.project_files.db_safety import (
        UnsafeDatabasePathError,
        assert_safe_sqlite_db_path,
        safe_cleanup_disposable_path,
    )

    if DATA_DIR.exists():
        target_data_dir = DATA_DIR
    else:
        mock_repo, _, _ = _make_synthetic_repo(tmp_path)
        monkeypatch.setenv("BOTTOM_POT_TEST_EXTRA_PROTECTED_ROOT", str(mock_repo))
        target_data_dir = mock_repo / "data"

    link_dir = tmp_path / "data_link"
    created = False
    if sys.platform == "win32":
        proc = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link_dir), str(target_data_dir)],
            capture_output=True,
            text=True,
            timeout=15,
        )
        created = proc.returncode == 0
    else:
        try:
            os.symlink(str(target_data_dir), str(link_dir))
            created = True
        except OSError:
            created = False

    if not created:
        pytest.skip("Platform does not permit creating directory symlink or junction")

    try:
        with pytest.raises(UnsafeDatabasePathError):
            assert_safe_sqlite_db_path(str(link_dir / "cache.sqlite"), context="test")
        with pytest.raises(UnsafeDatabasePathError):
            safe_cleanup_disposable_path(link_dir / "cache.sqlite", owned_root=tmp_path)
    finally:
        if os.path.isdir(link_dir) and not os.path.islink(link_dir):
            link_dir.rmdir()
        elif link_dir.exists() or os.path.islink(link_dir):
            link_dir.unlink()


def test_cache_store_and_registry_reject_operational_db_in_test_mode():
    from src.project_files.cache_store import CacheStore
    from src.project_files.company_board_registry import CompanyBoardRegistry
    from src.project_files.db_safety import UnsafeDatabasePathError

    with pytest.raises(UnsafeDatabasePathError):
        CacheStore(db_path=str(OPERATIONAL_DB))

    with pytest.raises(UnsafeDatabasePathError):
        CompanyBoardRegistry(db_path="data/../data/cache.sqlite")


def test_reproduce_original_failure_chain_in_subprocess_leaves_operational_assets_unchanged(tmp_path: Path):
    """
    Reproduce the exact November 2026 failure vector in an isolated subprocess:
    inherited SQLITE_DB_PATH & PLAYWRIGHT_SQLITE_DB_PATH pointing to operational DB
    (both real REPO_ROOT/data if present and synthetic CI mock_repo/data).
    Verify startup/init/migration fails closed before touching SQLite and hashes match identically.
    """
    before_real_assets = _snapshot_protected_assets()
    mock_repo, mock_op_db, before_mock_assets = _make_synthetic_repo(tmp_path)

    for target_db in (OPERATIONAL_DB, mock_op_db):
        env = os.environ.copy()
        env["SQLITE_DB_PATH"] = str(target_db)
        env["PLAYWRIGHT_SQLITE_DB_PATH"] = str(target_db)
        env["TESTING"] = "true"
        env["BOTTOM_POT_TEST_MODE"] = "1"
        env["BOTTOM_POT_TEST_EXTRA_PROTECTED_ROOT"] = str(mock_repo)

        code = (
            "from src.project_files.cache_store import CacheStore; "
            "CacheStore()"
        )
        proc = subprocess.run(
            [sys.executable, "-c", code],
            cwd=str(REPO_ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=25,
        )
        assert proc.returncode != 0
        assert "UnsafeDatabasePathError" in proc.stderr or "operational" in proc.stderr.lower()

    after_real_assets = _snapshot_protected_assets()
    after_mock_assets = {
        p: (p.stat().st_size, _sha256(p))
        for p in sorted((mock_repo / "data").iterdir())
        if p.is_file()
    }
    assert after_real_assets == before_real_assets
    assert after_mock_assets == before_mock_assets


def test_fastapi_startup_fails_closed_when_test_env_points_to_operational_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    from fastapi.testclient import TestClient
    from src.api.main import app
    from src.config import settings
    from src.project_files.db_safety import UnsafeDatabasePathError

    monkeypatch.setenv("BOTTOM_POT_TEST_MODE", "1")
    monkeypatch.setattr(settings, "sqlite_db_path", str(OPERATIONAL_DB))
    monkeypatch.setattr(settings, "subscriptions_file", str(tmp_path / "subs.csv"))

    with pytest.raises(UnsafeDatabasePathError):
        with TestClient(app):
            pass


def test_production_context_permits_repo_like_db_only_with_explicit_auth_on_mock_root(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    """Verify synthetic production validation rejects unauthorized access and requires explicit opt-in."""
    from src.project_files.db_safety import (
        UnsafeDatabasePathError,
        is_test_or_disposable_context,
        validate_sqlite_db_path,
    )

    mock_repo = tmp_path / "mock_prod_repo"
    mock_data = mock_repo / "data"
    mock_data.mkdir(parents=True)
    mock_op_db = mock_data / "cache.sqlite"
    with sqlite3.connect(str(mock_op_db)) as conn:
        conn.execute("CREATE TABLE t (x INT)")

    assert is_test_or_disposable_context() is True  # inside pytest
    with pytest.raises(UnsafeDatabasePathError):
        validate_sqlite_db_path(str(mock_op_db), context="test", repo_root=mock_repo)

    # Even enforce_env_test_guard=False fails without BOTTOM_POT_ALLOW_OPERATIONAL_DB=1
    monkeypatch.delenv("BOTTOM_POT_ALLOW_OPERATIONAL_DB", raising=False)
    with pytest.raises(UnsafeDatabasePathError):
        validate_sqlite_db_path(
            str(mock_op_db),
            context="production",
            repo_root=mock_repo,
            enforce_env_test_guard=False,
        )

    # Setting BOTTOM_POT_ALLOW_OPERATIONAL_DB=1 in test mode MUST STILL reject real REPO_ROOT DB
    monkeypatch.setenv("BOTTOM_POT_ALLOW_OPERATIONAL_DB", "1")
    with pytest.raises(UnsafeDatabasePathError):
        validate_sqlite_db_path(
            str(OPERATIONAL_DB),
            context="production",
            repo_root=REPO_ROOT,
            enforce_env_test_guard=False,
        )

    resolved = validate_sqlite_db_path(
        str(mock_op_db),
        context="production",
        repo_root=mock_repo,
        enforce_env_test_guard=False,
    )
    assert Path(resolved) == Path(os.path.realpath(mock_op_db))


def test_static_db_safety_checker_flags_unsafe_patterns_and_allows_safe_ones(tmp_path: Path):
    from scripts.check_db_safety import scan_repository

    safe_repo = tmp_path / "safe_repo"
    (safe_repo / "tests").mkdir(parents=True)
    (safe_repo / "playwright.config.js").write_text(
        "const fs = require('fs');\n"
        "const runDir = fs.mkdtempSync('/tmp/e2e-');\n"
        "module.exports = { webServer: { reuseExistingServer: false } };\n",
        encoding="utf-8",
    )
    (safe_repo / "tests" / "conftest.py").write_text(
        "import os\n"
        "os.environ['SQLITE_DB_PATH'] = '/tmp/test.sqlite'\n"
        "from src.config import settings\n",
        encoding="utf-8",
    )
    (safe_repo / "tests" / "test_good.py").write_text(
        "def test_ok(tmp_path):\n"
        "    f = tmp_path / 'a.sqlite'\n"
        "    f.write_text('x')\n"
        "    f.unlink()\n",
        encoding="utf-8",
    )
    assert scan_repository(safe_repo) == []

    unsafe_repo = tmp_path / "unsafe_repo"
    (unsafe_repo / "tests").mkdir(parents=True)
    (unsafe_repo / "playwright.config.js").write_text(
        "if (!process.env.PLAYWRIGHT_SQLITE_DB_PATH) { process.env.PLAYWRIGHT_SQLITE_DB_PATH = 'data/cache.sqlite'; }\n"
        "module.exports = { webServer: { reuseExistingServer: process.env.PLAYWRIGHT_REUSE_SERVER === '1' } };\n",
        encoding="utf-8",
    )
    (unsafe_repo / "tests" / "test_bad.py").write_text(
        "from pathlib import Path\n"
        "Path('data/cache.sqlite').unlink()\n",
        encoding="utf-8",
    )
    findings = scan_repository(unsafe_repo)
    assert len(findings) >= 2


def test_unknown_process_inheriting_dotenv_without_test_flags_denied_and_imports_lazy(tmp_path: Path):
    """
    A clean non-test script with NONE of PYTEST/PLAYWRIGHT/BOTTOM_POT_TEST_MODE/TESTING/CI
    must:
    1) Import cache_store, company_board_registry, and src.api.main without touching SQLite.
    2) Fail closed with UnsafeDatabasePathError when attempting to open .env-default data/cache.sqlite.
    """
    before_real = _snapshot_protected_assets()
    mock_repo, mock_op_db, before_mock = _make_synthetic_repo(tmp_path)
    env = _clean_non_test_env({"BOTTOM_POT_TEST_EXTRA_PROTECTED_ROOT": str(mock_repo)})

    # 1. Pure imports do NOT open SQLite
    import_probe = (
        "import json; "
        "from src.project_files.db_safety import is_test_or_disposable_context, is_operational_env_enabled, is_operational_runtime_authorized; "
        "from src.project_files.cache_store import cache_store; "
        "from src.project_files.company_board_registry import company_board_registry; "
        "from src.api.main import app; "
        "print(json.dumps({"
        "'test_ctx': is_test_or_disposable_context(), "
        "'op_env': is_operational_env_enabled(), "
        "'op_auth': is_operational_runtime_authorized(), "
        "'cache_init': cache_store._initialized, "
        "'reg_init': company_board_registry._initialized"
        "}))"
    )
    proc_import = subprocess.run(
        [sys.executable, "-c", import_probe],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=True,
        timeout=25,
    )
    info = json_loads_line(proc_import.stdout)
    assert info == {
        "test_ctx": False,
        "op_env": False,
        "op_auth": False,
        "cache_init": False,
        "reg_init": False,
    }

    # 2. Unknown script attempting DB access (direct or singleton or FastAPI lifespan) without operational grant fails closed
    for probe in (
        "from src.project_files.cache_store import CacheStore; CacheStore(db_path='data/cache.sqlite')",
        "from src.project_files.company_board_registry import CompanyBoardRegistry; CompanyBoardRegistry(db_path='data/cache.sqlite')",
        "from src.project_files.cache_store import cache_store; cache_store.db_path = 'data/cache.sqlite'; cache_store.get_serper_cache('k')",
        f"from src.project_files.company_board_registry import CompanyBoardRegistry; CompanyBoardRegistry(db_path=r'{mock_op_db}')",
        "from fastapi.testclient import TestClient; from src.config import settings; settings.sqlite_db_path = 'data/cache.sqlite'; from src.api.main import app; TestClient(app).__enter__()",
    ):
        proc = subprocess.run(
            [sys.executable, "-c", probe],
            cwd=str(REPO_ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=25,
        )
        assert proc.returncode != 0
        assert "UnsafeDatabasePathError" in proc.stderr

    assert _snapshot_protected_assets() == before_real
    after_mock = {p: (p.stat().st_size, _sha256(p)) for p in sorted((mock_repo / "data").iterdir()) if p.is_file()}
    assert after_mock == before_mock


def json_loads_line(stdout: str) -> dict:
    import json
    return json.loads(stdout.strip().splitlines()[-1])


def test_test_flags_unconditionally_override_operational_opt_in(monkeypatch: pytest.MonkeyPatch):
    from src.project_files.db_safety import (
        UnsafeDatabasePathError,
        assert_safe_sqlite_db_path,
        authorize_operational_runtime,
        is_operational_runtime_authorized,
    )

    monkeypatch.setenv("BOTTOM_POT_ALLOW_OPERATIONAL_DB", "1")
    monkeypatch.setenv("BOTTOM_POT_TEST_MODE", "1")
    with pytest.raises(UnsafeDatabasePathError):
        authorize_operational_runtime("test_override_attempt")
    assert is_operational_runtime_authorized() is False
    with pytest.raises(UnsafeDatabasePathError):
        assert_safe_sqlite_db_path("data/cache.sqlite")
    with pytest.raises(UnsafeDatabasePathError):
        assert_safe_sqlite_db_path("data/cache.sqlite", context="production")


def test_cleanup_and_explicit_operational_runtime_authorization_in_clean_subprocess(tmp_path: Path):
    mock_repo, mock_op_db, _ = _make_synthetic_repo(tmp_path)
    # 1. Cleanup is ALWAYS rejected even in non-test subprocess with operational opt-in + runtime auth!
    cleanup_env = _clean_non_test_env({"BOTTOM_POT_ALLOW_OPERATIONAL_DB": "1"})
    cleanup_code = (
        f"import pathlib; from src.project_files.db_safety import authorize_operational_runtime, assert_safe_sqlite_db_path, safe_cleanup_disposable_path, OwnedDisposableWorkspace; "
        f"authorize_operational_runtime('prod-test'); "
        f"ws = OwnedDisposableWorkspace.create(prefix='op-clean-'); "
        f"assert_safe_sqlite_db_path(r'{mock_op_db}', operation='connect', repo_root=pathlib.Path(r'{mock_repo}')); "
        f"safe_cleanup_disposable_path(r'{mock_op_db}', owned_root=ws.root, repo_root=pathlib.Path(r'{mock_repo}'))"
    )
    proc_cleanup = subprocess.run(
        [sys.executable, "-c", cleanup_code],
        cwd=str(REPO_ROOT),
        env=cleanup_env,
        capture_output=True,
        text=True,
        timeout=25,
    )
    assert proc_cleanup.returncode != 0
    assert "UnsafeDatabasePathError" in proc_cleanup.stderr

    # 2. Explicit non-test authorization succeeds on synthetic mock_repo, revokes cleanly, and fails again
    auth_code = "\n".join([
        "import pathlib",
        "from src.project_files.db_safety import (",
        "    UnsafeDatabasePathError,",
        "    assert_safe_sqlite_db_path,",
        "    operational_runtime_context,",
        ")",
        f"root = pathlib.Path(r'{mock_repo}')",
        f"db = r'{mock_op_db}'",
        "with operational_runtime_context('cli:test'):",
        "    res = assert_safe_sqlite_db_path(db, context='production', operation='connect', repo_root=root)",
        "    assert pathlib.Path(res).name == 'cache.sqlite'",
        "try:",
        "    assert_safe_sqlite_db_path(db, context='production', operation='connect', repo_root=root)",
        "    raise AssertionError('Expected failure after revoke')",
        "except UnsafeDatabasePathError:",
        "    pass",
    ])
    proc_auth = subprocess.run(
        [sys.executable, "-c", auth_code],
        cwd=str(REPO_ROOT),
        env=cleanup_env,
        capture_output=True,
        text=True,
        check=True,
        timeout=25,
    )
    assert proc_auth.returncode == 0


def test_store_and_registry_never_swallow_unsafe_database_path_error():
    from src.project_files.cache_store import CacheStore
    from src.project_files.company_board_registry import CompanyBoardRegistry
    from src.project_files.db_safety import UnsafeDatabasePathError

    deferred_cache = CacheStore(_defer_init=True)
    deferred_cache.db_path = "data/cache.sqlite"
    with pytest.raises(UnsafeDatabasePathError):
        deferred_cache.get_serper_cache("missing-key")
    with pytest.raises(UnsafeDatabasePathError):
        deferred_cache.clear()

    deferred_reg = CompanyBoardRegistry(_defer_init=True)
    deferred_reg.db_path = "DATA\\CACHE.SQLITE"
    with pytest.raises(UnsafeDatabasePathError):
        deferred_reg.get_board("ashby", "nonexistent")
    with pytest.raises(UnsafeDatabasePathError):
        deferred_reg.clear()


def test_cross_platform_backslash_and_case_lookalikes_rejected():
    from src.project_files.db_safety import (
        UnsafeDatabasePathError,
        assert_safe_sqlite_db_path,
        assert_safe_subscriptions_path,
    )

    for variant in (
        "DATA\\CACHE.SQLITE",
        "data\\subdir\\..\\cache.sqlite",
        "./DATA/cache.sqlite-wal",
        "data\\cache.sqlite.bak-pre-ashby-repair",
    ):
        with pytest.raises(UnsafeDatabasePathError):
            assert_safe_sqlite_db_path(variant, context="test")

    with pytest.raises(UnsafeDatabasePathError):
        assert_safe_subscriptions_path("DATA\\subscriptions.csv", context="test")
