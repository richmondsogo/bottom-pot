"""Phase 7 tests: external BOTTOM_POT_DATA_DIR, ADR 0030 preservation, backup, integrity check, and restore rehearsal.

All tests execute strictly against disposable tmp_path / OwnedDisposableWorkspace DBs
and verify that real repository data/ assets remain untouched.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from tests.test_operational_db_safety import (
    DATA_DIR,
    OPERATIONAL_DB,
    _clean_non_test_env,
    _snapshot_protected_assets,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
DB_BACKUP_SCRIPT = REPO_ROOT / "scripts" / "db_backup.py"


def _create_disposable_wal_db(db_file: Path, *, rows: int = 3) -> Path:
    db_file.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_file))
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA wal_autocheckpoint=0;")
        conn.execute(
            "CREATE TABLE IF NOT EXISTS company_boards (id INTEGER PRIMARY KEY, company_name TEXT NOT NULL, ats_provider TEXT NOT NULL)"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS monitored_jobs (id TEXT PRIMARY KEY, title TEXT NOT NULL)"
        )
        for i in range(1, rows + 1):
            conn.execute(
                "INSERT INTO company_boards (id, company_name, ats_provider) VALUES (?, ?, ?)",
                (i, f"Company-{i}", "ashby"),
            )
            conn.execute(
                "INSERT INTO monitored_jobs (id, title) VALUES (?, ?)",
                (f"job-{i}", f"Role {i}"),
            )
        conn.commit()
    finally:
        conn.close()
    return db_file


def _pw_node_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    env = os.environ.copy()
    for key in (
        "PLAYWRIGHT_SQLITE_DB_PATH",
        "SQLITE_DB_PATH",
        "PLAYWRIGHT_SUBSCRIPTIONS_FILE",
        "SUBSCRIPTIONS_FILE",
        "BOTTOM_POT_DATA_DIR",
        "BOTTOM_POT_PROTECTED_DATA_DIRS",
    ):
        env.pop(key, None)
    pw_pkg = REPO_ROOT / "node_modules" / "@playwright" / "test" / "package.json"
    if not pw_pkg.exists():
        pnpm_pw = sorted((REPO_ROOT / "node_modules" / ".pnpm").glob("@playwright+test*"))
        if pnpm_pw:
            existing_np = env.get("NODE_PATH", "")
            pnpm_nm = str(pnpm_pw[0] / "node_modules")
            env["NODE_PATH"] = f"{pnpm_nm}{os.pathsep}{existing_np}" if existing_np else pnpm_nm
    if extra:
        env.update(extra)
    return env


def test_default_production_data_dir_per_platform_outside_repo(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    from src.safety import db_safety

    resolved_repo = REPO_ROOT.resolve()

    monkeypatch.setattr(db_safety.sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "LocalAppData"))
    win_dir = db_safety.default_production_data_dir()
    assert win_dir == (tmp_path / "LocalAppData" / "bottom-pot")
    assert resolved_repo not in win_dir.parents

    monkeypatch.setattr(db_safety.sys, "platform", "darwin")
    monkeypatch.setattr(db_safety.Path, "home", classmethod(lambda cls: tmp_path / "mac_home"))
    mac_dir = db_safety.default_production_data_dir()
    assert mac_dir == (tmp_path / "mac_home" / "Library" / "Application Support" / "bottom-pot")

    monkeypatch.setattr(db_safety.sys, "platform", "linux")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg_data"))
    linux_dir = db_safety.default_production_data_dir()
    assert linux_dir == (tmp_path / "xdg_data" / "bottom-pot")


def test_resolve_data_paths_fresh_legacy_configured_and_test_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    from src.core.data_dir import resolve_data_paths
    from src.safety.db_safety import UnsafeDatabasePathError, default_production_data_dir

    # 1. Fresh install (no repo data/cache.sqlite): defaults outside repo
    fresh_repo = tmp_path / "fresh_repo"
    fresh_repo.mkdir()
    fresh_prod = tmp_path / "os_prod_data"
    monkeypatch.setattr("src.core.data_dir.default_production_data_dir", lambda: fresh_prod)
    res_fresh = resolve_data_paths(repo_root=fresh_repo, is_test=False)
    assert res_fresh.mode == "default_production_dir"
    assert res_fresh.legacy_db_present is False
    assert res_fresh.data_dir == fresh_prod
    assert res_fresh.sqlite_db_path == fresh_prod / "cache.sqlite"
    assert res_fresh.subscriptions_file == fresh_prod / "subscriptions.csv"

    # 2. Legacy install (existing data/cache.sqlite): stays on repo data/cache.sqlite until migrated
    legacy_repo = tmp_path / "legacy_repo"
    (legacy_repo / "data").mkdir(parents=True)
    (legacy_repo / "data" / "cache.sqlite").write_bytes(b"placeholder")
    res_legacy = resolve_data_paths(repo_root=legacy_repo, is_test=False)
    assert res_legacy.mode == "legacy_repo_install"
    assert res_legacy.legacy_db_present is True
    assert res_legacy.sqlite_db_path == legacy_repo / "data" / "cache.sqlite"
    assert res_legacy.subscriptions_file == legacy_repo / "subscriptions.csv"

    # 3. Explicit BOTTOM_POT_DATA_DIR overrides legacy install cleanly
    custom_dir = tmp_path / "external_prod"
    res_cfg = resolve_data_paths(configured_data_dir=str(custom_dir), repo_root=legacy_repo, is_test=False)
    assert res_cfg.mode == "configured_data_dir"
    assert res_cfg.data_dir == custom_dir.resolve()
    assert res_cfg.sqlite_db_path == custom_dir.resolve() / "cache.sqlite"
    assert res_cfg.subscriptions_file == custom_dir.resolve() / "subscriptions.csv"

    # 4. Default test mode allocates an isolated disposable workspace outside all protected dirs
    res_test = resolve_data_paths(is_test=True)
    assert res_test.mode == "test"
    assert DATA_DIR.resolve() not in res_test.sqlite_db_path.resolve().parents
    assert res_test.data_dir != default_production_data_dir()

    # 5. Test mode fails closed if configured_data_dir resolves to protected repo data/ or external prod dir
    with pytest.raises(UnsafeDatabasePathError):
        resolve_data_paths(configured_data_dir=str(DATA_DIR), is_test=True)

    monkeypatch.setenv("BOTTOM_POT_DATA_DIR", str(custom_dir))
    with pytest.raises(UnsafeDatabasePathError):
        resolve_data_paths(configured_data_dir=str(custom_dir), is_test=True)


def test_configured_external_data_dir_inherits_full_adr0030_protections(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    from src.safety.db_safety import (
        UnsafeDatabasePathError,
        assert_safe_sqlite_db_path,
        default_production_data_dir,
    )

    before_real = _snapshot_protected_assets()
    ext_dir = tmp_path / "ext_prod_state"
    ext_dir.mkdir(parents=True)
    ext_db = ext_dir / "cache.sqlite"
    _create_disposable_wal_db(ext_db, rows=2)

    # 1. Test process with BOTTOM_POT_DATA_DIR set must reject targeting ext_dir directly or via Settings
    proc_test = subprocess.run(
        [
            sys.executable,
            "-c",
            "from src.core.settings import settings; print(settings.sqlite_db_path)",
        ],
        cwd=str(REPO_ROOT),
        env=_clean_non_test_env({"BOTTOM_POT_TEST_MODE": "1", "BOTTOM_POT_DATA_DIR": str(ext_dir)}),
        capture_output=True,
        text=True,
        timeout=25,
    )
    assert proc_test.returncode != 0
    assert "UnsafeDatabasePathError" in proc_test.stderr

    # 2. Clean non-test process CANNOT open ext_db without BOTTOM_POT_ALLOW_OPERATIONAL_DB=1 + documented entrypoint
    env_no_auth = _clean_non_test_env({"BOTTOM_POT_DATA_DIR": str(ext_dir)})
    proc_denied = subprocess.run(
        [
            sys.executable,
            "-c",
            "from src.storage.company_board_registry import CompanyBoardRegistry; "
            f"CompanyBoardRegistry(db_path=r'{ext_db}')",
        ],
        cwd=str(REPO_ROOT),
        env=env_no_auth,
        capture_output=True,
        text=True,
        timeout=25,
    )
    assert proc_denied.returncode != 0
    assert "UnsafeDatabasePathError" in proc_denied.stderr

    # 3. Clean non-test process WITH BOTTOM_POT_ALLOW_OPERATIONAL_DB=1 + documented entrypoint CAN connect
    #    on canonical cache.sqlite, but cleanup remains unconditionally forbidden.
    env_with_flag = _clean_non_test_env(
        {"BOTTOM_POT_DATA_DIR": str(ext_dir), "BOTTOM_POT_ALLOW_OPERATIONAL_DB": "1"}
    )
    ok_code = "\n".join(
        [
            "import pathlib",
            "from src.core.settings import settings",
            "from src.safety.db_safety import (",
            "    assert_safe_sqlite_db_path,",
            "    assert_safe_subscriptions_path,",
            "    operational_runtime_context,",
            ")",
            "with operational_runtime_context('scripts.db_backup:main'):",
            "    resolved = assert_safe_sqlite_db_path(settings.sqlite_db_path, context='production')",
            "    assert pathlib.Path(resolved).name == 'cache.sqlite'",
            "    subs = assert_safe_subscriptions_path(settings.subscriptions_file, context='production')",
            "    assert pathlib.Path(subs).name == 'subscriptions.csv'",
        ]
    )
    subprocess.run(
        [sys.executable, "-c", ok_code],
        cwd=str(REPO_ROOT),
        env=env_with_flag,
        capture_output=True,
        text=True,
        check=True,
        timeout=25,
    )

    cleanup_code = "\n".join(
        [
            "from src.safety.db_safety import OwnedDisposableWorkspace, operational_runtime_context, safe_cleanup_disposable_path",
            "ws = OwnedDisposableWorkspace.create(prefix='cleanup-refuse-')",
            "with operational_runtime_context('scripts.db_backup:main'):",
            f"    safe_cleanup_disposable_path(r'{ext_db}', owned_root=ws.root)",
        ]
    )
    proc_cleanup = subprocess.run(
        [sys.executable, "-c", cleanup_code],
        cwd=str(REPO_ROOT),
        env=env_with_flag,
        capture_output=True,
        text=True,
        timeout=25,
    )
    assert proc_cleanup.returncode != 0
    assert "UnsafeDatabasePathError" in proc_cleanup.stderr

    # Sidecar and canonical paths under configured BOTTOM_POT_DATA_DIR and default prod dir reject in test mode
    monkeypatch.setenv("BOTTOM_POT_DATA_DIR", str(ext_dir))
    with pytest.raises(UnsafeDatabasePathError):
        assert_safe_sqlite_db_path(ext_dir / "cache.sqlite", context="test")
    with pytest.raises(UnsafeDatabasePathError):
        assert_safe_sqlite_db_path(ext_dir / "cache.sqlite-wal", context="test")
    with pytest.raises(UnsafeDatabasePathError):
        assert_safe_sqlite_db_path(default_production_data_dir() / "cache.sqlite-wal", context="test")

    assert _snapshot_protected_assets() == before_real


def test_playwright_config_clears_and_protects_inherited_bottom_pot_data_dir(tmp_path: Path):
    ext_dir = tmp_path / "pw_external_prod"
    ext_dir.mkdir(parents=True)
    script = (
        "const cfg = require('./playwright.config.js');"
        "console.log(JSON.stringify({"
        "  env_db: process.env.SQLITE_DB_PATH,"
        "  env_data_dir: process.env.BOTTOM_POT_DATA_DIR,"
        "  ws_env: cfg.webServer && cfg.webServer.env"
        "}));"
    )
    proc = subprocess.run(
        ["node", "-e", script],
        cwd=str(REPO_ROOT),
        env=_pw_node_env({"BOTTOM_POT_DATA_DIR": str(ext_dir)}),
        capture_output=True,
        text=True,
        check=True,
        timeout=25,
    )
    payload = json.loads(proc.stdout.strip())
    assert payload["env_data_dir"] == ""
    assert payload["ws_env"]["BOTTOM_POT_DATA_DIR"] == ""
    assert str(ext_dir) in payload["ws_env"]["BOTTOM_POT_PROTECTED_DATA_DIRS"]
    assert Path(payload["env_db"]).parent != ext_dir


def test_wal_shm_safe_backup_captures_uncheckpointed_frames_and_rehearses_restore(tmp_path: Path):
    from src.safety.db_safety import UnsafeDatabasePathError
    from src.storage.db_backup import (
        backup_database,
        rehearse_restore,
        verify_database_integrity,
    )

    before_real = _snapshot_protected_assets()

    src_dir = tmp_path / "source_state"
    src_db = _create_disposable_wal_db(src_dir / "disposable.sqlite", rows=4)
    # Keep a live WAL connection open so -wal/-shm hold uncheckpointed committed frames during backup
    conn = sqlite3.connect(str(src_db), timeout=30.0)
    try:
        conn.execute("PRAGMA wal_autocheckpoint=0;")
        conn.execute(
            "INSERT INTO company_boards (id, company_name, ats_provider) VALUES (5, 'Uncheckpointed-Co', 'lever')"
        )
        conn.execute(
            "INSERT INTO monitored_jobs (id, title) VALUES ('job-5', 'WAL-Only Role')"
        )
        conn.commit()

        wal_file = Path(f"{src_db}-wal")
        assert wal_file.exists() and wal_file.stat().st_size > 0, "Expected non-empty WAL sidecar prior to backup"
        before_src_hash = hashlib.sha256(src_db.read_bytes()).hexdigest()
        before_wal_hash = hashlib.sha256(wal_file.read_bytes()).hexdigest()

        # Refuses writing backups inside operational REPO_ROOT /data
        with pytest.raises(UnsafeDatabasePathError):
            backup_database(src_db, output_dir=DATA_DIR, label="bad")

        backup_out = tmp_path / "backups"
        b_res = backup_database(src_db, output_dir=backup_out, label="pre-seed")
        assert b_res.integrity_ok is True
        assert b_res.source_journal_mode == "wal"
        assert b_res.table_counts["company_boards"] == 5
        assert b_res.table_counts["monitored_jobs"] == 5

        # Source DB & WAL bytes remain intact and standalone backup contains zero -wal/-shm sidecars
        assert hashlib.sha256(src_db.read_bytes()).hexdigest() == before_src_hash
        assert hashlib.sha256(wal_file.read_bytes()).hexdigest() == before_wal_hash
        backup_path = Path(b_res.backup_path)
        assert backup_path.exists()
        assert Path(b_res.manifest_path).exists()
        assert not Path(f"{backup_path}-wal").exists()
        assert not Path(f"{backup_path}-shm").exists()

        # Confirm the uncheckpointed WAL row landed inside the standalone backup file itself
        b_conn = sqlite3.connect(str(backup_path))
        try:
            titles = {r[0] for r in b_conn.execute("SELECT title FROM monitored_jobs").fetchall()}
            assert "WAL-Only Role" in titles
        finally:
            b_conn.close()

        # Verify manifest SHA-256 matches actual backup file
        manifest = json.loads(Path(b_res.manifest_path).read_text(encoding="utf-8"))
        assert manifest["sha256"] == hashlib.sha256(backup_path.read_bytes()).hexdigest()

        # Integrity check on both live WAL source and standalone backup succeeds with accurate counts
        src_check = verify_database_integrity(src_db)
        assert src_check.ok is True
        assert src_check.table_counts["monitored_jobs"] == 5
        assert src_check.sidecar_sizes.get("-wal", 0) > 0

        b_check = verify_database_integrity(backup_path)
        assert b_check.ok is True
        assert b_check.table_counts["monitored_jobs"] == 5

        # Restore rehearsal copies to a disposable workspace, verifies SHA-256 + integrity, and cleans up
        reh = rehearse_restore(backup_path)
        assert reh.ok is True
        assert reh.sha256_match is True
        assert reh.table_counts["monitored_jobs"] == 5
        assert not Path(reh.rehearsal_db).parent.exists(), "Expected disposable rehearsal dir to be cleaned up"
    finally:
        conn.close()

    assert _snapshot_protected_assets() == before_real


def test_integrity_check_and_rehearse_fail_cleanly_on_corrupt_sqlite_and_cli_works(tmp_path: Path):
    from src.storage.db_backup import rehearse_restore, verify_database_integrity

    before_real = _snapshot_protected_assets()

    good_db = _create_disposable_wal_db(tmp_path / "cli_src.sqlite", rows=2)
    backup_dir = tmp_path / "cli_backups"

    corrupt_db = tmp_path / "corrupt.sqlite"
    corrupt_db.write_bytes(b"NOT A VALID SQLITE DATABASE HEADER" * 20)

    bad_check = verify_database_integrity(corrupt_db)
    assert bad_check.ok is False
    assert bad_check.messages

    bad_rehearse = rehearse_restore(corrupt_db)
    assert bad_rehearse.ok is False
    assert bad_rehearse.sha256_match is True
    assert not Path(bad_rehearse.rehearsal_db).parent.exists()

    # CLI paths (non-DB read-only inspection)
    proc_paths = subprocess.run(
        [sys.executable, str(DB_BACKUP_SCRIPT), "paths", "--json"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=True,
        timeout=25,
    )
    paths_json = json.loads(proc_paths.stdout)
    assert paths_json["is_test_context"] is True
    assert paths_json["mode"] == "test"

    # CLI backup -> check -> rehearse on disposable DBs
    proc_backup = subprocess.run(
        [
            sys.executable,
            str(DB_BACKUP_SCRIPT),
            "backup",
            "--db",
            str(good_db),
            "--output-dir",
            str(backup_dir),
            "--label",
            "smoke",
            "--json",
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=True,
        timeout=25,
    )
    backup_json = json.loads(proc_backup.stdout)
    assert backup_json["integrity_ok"] is True

    proc_check = subprocess.run(
        [sys.executable, str(DB_BACKUP_SCRIPT), "check", "--db", str(good_db), "--json"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=True,
        timeout=25,
    )
    assert json.loads(proc_check.stdout)["ok"] is True

    proc_reh = subprocess.run(
        [
            sys.executable,
            str(DB_BACKUP_SCRIPT),
            "rehearse",
            "--backup",
            backup_json["backup_path"],
            "--json",
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=True,
        timeout=25,
    )
    assert json.loads(proc_reh.stdout)["ok"] is True

    proc_bad_check = subprocess.run(
        [sys.executable, str(DB_BACKUP_SCRIPT), "check", "--db", str(corrupt_db), "--json"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=25,
    )
    assert proc_bad_check.returncode == 1
    assert json.loads(proc_bad_check.stdout)["ok"] is False

    # Operational DB safety still rejects operational target via CLI even with --allow-operational-db in test mode
    proc_op_refused = subprocess.run(
        [
            sys.executable,
            str(DB_BACKUP_SCRIPT),
            "check",
            "--db",
            str(OPERATIONAL_DB),
            "--allow-operational-db",
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=25,
    )
    assert proc_op_refused.returncode != 0
    assert "UnsafeDatabasePathError" in proc_op_refused.stderr

    assert _snapshot_protected_assets() == before_real


def test_store_and_registry_deterministically_close_sqlite_connections_without_gc(tmp_path: Path):
    import gc
    from datetime import datetime, timezone

    from scripts.report_freshness import report_from_sqlite
    from src.core.models import JobListing
    from src.storage.cache_store import CacheStore
    from src.storage.company_board_registry import CompanyBoardRegistry

    before_real = _snapshot_protected_assets()
    cache_db = tmp_path / "deterministic_cache.sqlite"
    reg_db = tmp_path / "deterministic_registry.sqlite"
    now = datetime.now(timezone.utc)

    was_enabled = gc.isenabled()
    gc.disable()
    try:
        store = CacheStore(db_path=str(cache_db))
        store.set_serper_cache("k1", {"organic": []})
        assert store.get_serper_cache("k1") == {"organic": []}

        # With deterministic close, SQLite checkpoints and removes -wal immediately on context exit
        assert not Path(f"{cache_db}-wal").exists()

        reg = CompanyBoardRegistry(db_path=str(reg_db))
        listing = JobListing(
            id="greenhouse:acme:det-1",
            provider="greenhouse",
            data_source="api",
            title="Systems Engineer",
            company="Acme",
            location="Remote",
            work_model="remote",
            scraped_at=now,
            posted_at=now,
            apply_url="https://boards.greenhouse.io/acme/jobs/1",
            source_url="https://boards.greenhouse.io/acme/jobs/1",
            query_used="engineer",
            ats_source="greenhouse",
        )
        assert reg.upsert_monitored_job(listing) is True
        found = reg.search_monitored_jobs("Systems", limit=10)
        assert [j.id for j in found] == ["greenhouse:acme:det-1"]
        assert not Path(f"{reg_db}-wal").exists()

        before_sha = hashlib.sha256(reg_db.read_bytes()).hexdigest()
        summary = report_from_sqlite(reg_db, now=now)
        after_sha = hashlib.sha256(reg_db.read_bytes()).hexdigest()
        assert before_sha == after_sha
        assert summary["total_postings"] == 1

        # Confirm OS file handles are unlocked on both disposable DBs
        cache_check = sqlite3.connect(str(cache_db), timeout=1.0)
        cache_check.execute("PRAGMA locking_mode = EXCLUSIVE;").fetchone()
        cache_check.close()
        reg_check = sqlite3.connect(str(reg_db), timeout=1.0)
        reg_check.execute("PRAGMA locking_mode = EXCLUSIVE;").fetchone()
        reg_check.close()
    finally:
        if was_enabled:
            gc.enable()

    assert _snapshot_protected_assets() == before_real
