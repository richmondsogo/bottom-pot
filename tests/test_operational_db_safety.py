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


def test_junction_or_symlink_into_data_rejected_by_db_safety_and_cleanup(tmp_path: Path):
    from src.project_files.db_safety import (
        UnsafeDatabasePathError,
        assert_safe_sqlite_db_path,
        safe_cleanup_disposable_path,
    )

    link_dir = tmp_path / "data_link"
    created = False
    if sys.platform == "win32":
        proc = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link_dir), str(DATA_DIR)],
            capture_output=True,
            text=True,
            timeout=15,
        )
        created = proc.returncode == 0
    else:
        try:
            os.symlink(str(DATA_DIR), str(link_dir))
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
    inherited SQLITE_DB_PATH & PLAYWRIGHT_SQLITE_DB_PATH pointing to data/cache.sqlite.
    Verify startup/init/migration fails closed before touching SQLite and hashes match identically.
    """
    before_assets = _snapshot_protected_assets()
    assert OPERATIONAL_DB in before_assets

    env = os.environ.copy()
    env["SQLITE_DB_PATH"] = str(OPERATIONAL_DB)
    env["PLAYWRIGHT_SQLITE_DB_PATH"] = str(OPERATIONAL_DB)
    env["TESTING"] = "true"
    env["BOTTOM_POT_TEST_MODE"] = "1"

    code = (
        "import sys; "
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

    after_assets = _snapshot_protected_assets()
    assert after_assets == before_assets


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


def test_production_context_permits_repo_like_db_in_isolated_mock_root(tmp_path: Path):
    """Verify production path classification works without risking real data/cache.sqlite."""
    from src.project_files.db_safety import is_test_or_disposable_context, validate_sqlite_db_path

    mock_repo = tmp_path / "mock_prod_repo"
    mock_data = mock_repo / "data"
    mock_data.mkdir(parents=True)
    mock_op_db = mock_data / "cache.sqlite"
    with sqlite3.connect(str(mock_op_db)) as conn:
        conn.execute("CREATE TABLE t (x INT)")

    assert is_test_or_disposable_context() is True  # inside pytest
    # When context="production" and not in test env check (explicit simulated non-test check),
    # operational path in mock_repo is allowed, whereas test context still rejects it.
    from src.project_files.db_safety import UnsafeDatabasePathError

    with pytest.raises(UnsafeDatabasePathError):
        validate_sqlite_db_path(
            str(mock_op_db),
            context="test",
            repo_root=mock_repo,
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
