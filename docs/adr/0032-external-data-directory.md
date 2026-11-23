# ADR 0032: Configurable External Data Directory and Recovery Tooling

## Status

Accepted

## Context

Bottom Pot historically stored its operational SQLite cache and board registry at `<repo>/data/cache.sqlite` (alongside `-wal`, `-shm`, `-journal`, and `cache.sqlite.bak-*` snapshots) and newsletter signups at `<repo>/subscriptions.csv`. Placing mutable production databases inside the developer/CI repository checkout increased the risk of accidental test/E2E contamination (`ADR 0030`) and meant the repo shipped with zero standalone WAL/SHM-safe backup, integrity-check, or restore-rehearsal tooling.

At the same time, existing local installations that already hold valuable `data/cache.sqlite` operational data must not be broken or silently migrated behind the owner's back.

## Decision

1. **Configurable `BOTTOM_POT_DATA_DIR` (`src/core/data_dir.py`, `src/core/settings.py`)**:
   - Production installs support `BOTTOM_POT_DATA_DIR`, resolving `<BOTTOM_POT_DATA_DIR>/cache.sqlite` and `<BOTTOM_POT_DATA_DIR>/subscriptions.csv` (unless individually overridden by `SQLITE_DB_PATH` / `SUBSCRIPTIONS_FILE`).
   - Fresh production installs where `<repo>/data/cache.sqlite` does not exist default outside the repository tree (`%LOCALAPPDATA%\bottom-pot` on Windows, `~/Library/Application Support/bottom-pot` on macOS, `${XDG_DATA_HOME:-~/.local/share}/bottom-pot` on Linux).
   - Legacy installs where `<repo>/data/cache.sqlite` already exists (and `BOTTOM_POT_DATA_DIR` is unset) remain cleanly on `<repo>/data/cache.sqlite` and `<repo>/subscriptions.csv` until the owner executes the migration procedure in [`docs/operations/RUNBOOK.md`](../operations/RUNBOOK.md).
   - Automated test, Playwright E2E, and CI contexts always isolate to a fresh disposable temporary directory (`OwnedDisposableWorkspace` / `mkdtempSync`) and fail closed (`UnsafeDatabasePathError`) if any configured or resolved target overlaps a protected path.

2. **Full ADR 0030 Parity Across Repo & External Operational Dirs (`src/safety/db_safety.py`, `playwright.config.js`, `tests/conftest.py`, `scripts/check_db_safety.py`)**:
   - Preserve every existing ADR 0030 defense layer without loosening any guard.
   - Extend path, hard-link, symlink/junction, cleanup, default-deny runtime grant, Playwright E2E, and pytest isolation checks to cover `<repo>/data/`, the OS default production directory, and any configured `BOTTOM_POT_DATA_DIR`.

3. **WAL/SHM-Safe Backup, Integrity Check, and Disposable Restore Rehearsal (`src/storage/db_backup.py`, `scripts/db_backup.py`)**:
   - Ship `scripts/db_backup.py` (`paths`, `backup`, `check`, `rehearse`) under documented entrypoint `scripts.db_backup:main`.
   - `backup` uses SQLite's online `sqlite3.Connection.backup()` API with `PRAGMA query_only = ON` so committed WAL/SHM frames are captured atomically into a self-contained snapshot verified by `PRAGMA integrity_check` and SHA-256 manifest, while rejecting output paths inside any protected operational directory.
   - `rehearse` validates backup files strictly inside an auto-cleaned `OwnedDisposableWorkspace`.

## Alternatives Considered

- **Auto-migrating `<repo>/data/cache.sqlite` at startup**: Rejected. Implicitly moving or mutating live operational files violates `ADR 0030` and risks silent data loss or partial WAL/SHM splits.
- **Recommending raw filesystem copies (`cp` / `Copy-Item`)**: Rejected. Raw copies of `cache.sqlite` without consistent `-wal`/`-shm` capture corrupt or lose recent committed WAL transactions.

## Trade-offs

- Supporting backward-compatible legacy fallback when `data/cache.sqlite` exists means existing checkouts stay on `data/cache.sqlite` until the owner runs the documented migration steps.
- `scripts/db_backup.py` adds one small CLI utility and a new documented entrypoint (`scripts.db_backup:main`), which keeps non-test operational access explicitly gated behind `--allow-operational-db`.

## Consequences

- New installs never store mutable SQLite files inside the source checkout.
- Existing installs keep working uninterrupted and gain a safe, tested backup -> check -> rehearse -> migrate workflow prior to catalog seeding (`VERIFIED_EMPLOYER_BOARDS`).
