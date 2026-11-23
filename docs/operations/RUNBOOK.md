# Operations Runbook: Data Directory, SQLite Recovery & Catalog Seeding

Operational procedures for backing up, verifying, rehearsing restores, migrating to an external `BOTTOM_POT_DATA_DIR`, and safely seeding the curated employer board catalog.

---

## 1. Automated Backup Audit Finding (Baseline State)

An inspection of both the repository and the local Windows host established:

- **Repository inspection (`scripts/`, `src/`, `.github/workflows/`, `docs/`)**: No automated database backup scripts, cron jobs, CI backup workflows, or scheduled dump tasks exist in the repository today.
- **Host OS inspection (read-only `Get-ScheduledTask`)**: No Bottom Pot or SQLite backup tasks exist in Windows Task Scheduler (only built-in Windows `AppListBackup` and `RegIdleBackup` tasks were present).
- **Existing files in `data/`**: The preserved `data/cache.sqlite.bak-*` and `.cache.sqlite.restore-staging-*` artifacts came from one-off manual pre-repair snapshots and November 2026 forensic recovery (`ADR 0030`), not from any recurring schedule.
- **Agent action taken**: Zero OS scheduled tasks were created or modified, and no operational files were opened or moved. If you want recurring unattended backups after merging Phase 7, register your own OS task (Windows Task Scheduler or cron/systemd timer) invoking `scripts/db_backup.py backup` as a dedicated non-privileged command writing outside the repository tree.

---

## 2. Configurable External Data Directory (`BOTTOM_POT_DATA_DIR`)

Bottom Pot separates operational state from the git working tree (`ADR 0032`) while preserving existing installs until you migrate:

| Install / Context | Data Directory (`data_dir`) | SQLite DB (`sqlite_db_path`) | Subscriptions CSV (`subscriptions_file`) |
|---|---|---|---|
| **Explicit `BOTTOM_POT_DATA_DIR`** | `<BOTTOM_POT_DATA_DIR>` | `<BOTTOM_POT_DATA_DIR>/cache.sqlite` | `<BOTTOM_POT_DATA_DIR>/subscriptions.csv` |
| **Fresh production install** (`data/cache.sqlite` absent) | **Windows:** `%LOCALAPPDATA%\bottom-pot`<br>**macOS:** `~/Library/Application Support/bottom-pot`<br>**Linux:** `${XDG_DATA_HOME:-~/.local/share}/bottom-pot` | `<data_dir>/cache.sqlite` | `<data_dir>/subscriptions.csv` |
| **Legacy repo install** (`data/cache.sqlite` exists & `BOTTOM_POT_DATA_DIR` unset) | `<repo>/data` (preserved unchanged) | `<repo>/data/cache.sqlite` | `<repo>/subscriptions.csv` |
| **Automated test / Playwright E2E / CI** | Fresh disposable OS temp directory (`OwnedDisposableWorkspace` / `mkdtempSync`) | `<temp>/test_cache.sqlite` or `<temp>/e2e-cache.sqlite` | `<temp>/test_subscriptions.csv` or `<temp>/e2e-subscriptions.csv` |

Inspect active path resolution read-only (never opens SQLite):

```powershell
python scripts/db_backup.py paths
```

All six `ADR 0030` safety layers protect **both** `<repo>/data/` and the resolved external `BOTTOM_POT_DATA_DIR` / default outside-repo directory. Automated test, Playwright E2E, and CI contexts fail closed (`UnsafeDatabasePathError`) if any configured or inherited path resolves to a protected location.

---

## 3. Running WAL/SHM-Safe Backups

Bottom Pot opens SQLite in `WAL` mode (`cache.sqlite`, `cache.sqlite-wal`, `cache.sqlite-shm`). **Never copy `cache.sqlite` with plain `cp` / `Copy-Item` while the DB has active or uncheckpointed WAL frames**: splitting the main file from `-wal`/`-shm` corrupts transactions or silently drops uncheckpointed rows.

Instead, use `scripts/db_backup.py backup`, which:
1. Requires non-test execution and explicit `--allow-operational-db` (using documented entrypoint `scripts.db_backup:main`).
2. Opens the source with `PRAGMA query_only = ON` so no SQL writes happen.
3. Streams a consistent page-by-page snapshot via SQLite's online `sqlite3.Connection.backup()` API (merging committed `-wal`/`-shm` frames automatically without mutating the source DB).
4. Verifies `PRAGMA integrity_check` on the temporary snapshot, atomically promotes `<timestamp>.sqlite`, and writes a sibling `<timestamp>.sqlite.meta.json` containing the SHA-256 digest (`<sha256-digest>`), size, source journal mode, and table row counts.
5. Refuses any `--output-dir` inside `<repo>/data/`, the repository root, or a protected external data directory.

Example (choose a backup folder outside the repo, e.g. `C:\Backups\bottom-pot`):

```powershell
python scripts/db_backup.py backup --output-dir C:\Backups\bottom-pot --label manual --allow-operational-db
```

---

## 4. Integrity Checks (`check`)

Run a read-only SQLite integrity check (`PRAGMA integrity_check` by default, or `--quick` for `PRAGMA quick_check`) plus sidecar sizes and table row counts:

```powershell
python scripts/db_backup.py check --allow-operational-db
```

- Exit code `0` means `PRAGMA integrity_check` returned `ok`.
- Exit code `1` reports corruption diagnostics without crashing. **If an operational DB fails `check`:** stop `uvicorn`, `board_monitor`, and any repair scripts immediately, preserve the broken files untouched (do **not** delete `-wal`/`-shm`), take a raw forensic copy to an isolated directory, and restore only from a backup that passes Section 5 rehearsal.

---

## 5. Disposable Restore Rehearsal (`rehearse`)

Before relying on any backup or running an operational migration, verify that a backup file copies cleanly and passes full `PRAGMA integrity_check` inside an isolated `OwnedDisposableWorkspace`:

```powershell
python scripts/db_backup.py rehearse --backup C:\Backups\bottom-pot\bottom-pot-backup-YYYYMMDDTHHMMSSZ-label.sqlite
```

This verifies source-vs-copy SHA-256 equality (`sha256_match: true`), runs `PRAGMA integrity_check`, prints restored table row counts (`company_boards`, `monitored_jobs`, `serper_cache`, etc.), and removes the temporary workspace automatically (pass `--keep-temp` if you want to inspect the disposable copy manually).

---

## 6. Migrating an Existing Install from `data/cache.sqlite` to `BOTTOM_POT_DATA_DIR`

Existing installs with `data/cache.sqlite` continue working without disruption. When you are ready to move operational data outside the repository tree:

1. **Stop running Bottom Pot processes** (`uvicorn`, `scripts/run_prod.ps1`, `board_monitor`) so no writer opens new WAL frames during switchover.
2. **Verify source integrity**:
   ```powershell
   python scripts/db_backup.py check --allow-operational-db
   ```
3. **Take a standalone WAL/SHM-safe snapshot**:
   ```powershell
   python scripts/db_backup.py backup --output-dir C:\Backups\bottom-pot --label pre-external-migration --allow-operational-db
   ```
4. **Rehearse the restore** using the backup file printed in step 3:
   ```powershell
   python scripts/db_backup.py rehearse --backup <backup-file>
   ```
5. **Populate the external data directory** (do **not** delete `data/` yet):
   ```powershell
   $targetDir = "$env:LOCALAPPDATA\bottom-pot"
   New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
   Copy-Item <backup-file> (Join-Path $targetDir "cache.sqlite")
   if (Test-Path subscriptions.csv) {
       Copy-Item subscriptions.csv (Join-Path $targetDir "subscriptions.csv")
   }
   ```
6. **Configure `.env`** (gitignored): set `BOTTOM_POT_DATA_DIR` to `$targetDir` (or leave unset once `data/cache.sqlite` is eventually archived away) and remove/comment out any old `SQLITE_DB_PATH=data/cache.sqlite` or `SUBSCRIPTIONS_FILE=subscriptions.csv` lines.
7. **Verify new paths & integrity** before starting production:
   ```powershell
   python scripts/db_backup.py paths
   python scripts/db_backup.py check --allow-operational-db
   ```
8. **Archive legacy `data/` safely**: once production runs cleanly against `BOTTOM_POT_DATA_DIR` and another backup succeeds against the new location, move `<repo>/data/` to cold offline storage (outside any test/workspace directory) rather than deleting backups prematurely.

---

## 7. Catalog Seeding Policy (Decided — Owner Run Only)

The 28 direct employer boards catalogued across Steps 54–56 (`VERIFIED_EMPLOYER_BOARDS`, covering `ashby`, `greenhouse`, `lever`, `workable`, `teamtailor`, and `pinpointhq`) currently remain `operationally_registered: false` until you explicitly seed them.

### Why Seeding Waits Until Phase 5 and Phase 7 Merge

1. **Freshness ranking must be live first (Phase 5):** An empirical Step 56 audit found 9 of 12 "worldwide" roles on catalog boards such as Metabase and Railway were stale-but-published (162–2,384 days old). Without Phase 5's `freshness` tiers, default freshness-first ordering, and `"Older postings"` divider, seeding those boards surfaces stale postings at the top of tester results.
2. **Recovery safety must exist before mutating operational state (Phase 7):** The November 2026 operational incident (`ADR 0030`) caused operational database loss. Verified WAL/SHM-safe backups, integrity checks, and disposable restore rehearsal must be merged before seeding new boards into live SQLite.

### Exact Owner Seeding Sequence (All 28 Boards Together)

**Note:** None of the steps below were executed by the autonomous agent (`Hard Rule 2`). Execute them in this exact order only after both Phase 5 and Phase 7 have merged:

1. **Read-only catalog preview** (verify all 28 boards and domains before touching SQLite):
   ```powershell
   python -m src.monitoring.board_monitor --preview-catalog
   ```
2. **Take a pre-seed WAL/SHM-safe backup**:
   ```powershell
   python scripts/db_backup.py backup --output-dir C:\Backups\bottom-pot --label pre-catalog-seed --allow-operational-db
   ```
3. **Run an integrity check on the operational DB**:
   ```powershell
   python scripts/db_backup.py check --allow-operational-db
   ```
4. **Rehearse restoring the pre-seed backup** into a disposable workspace:
   ```powershell
   python scripts/db_backup.py rehearse --backup <pre-seed-backup-file>
   ```
5. **Seed all 28 catalogued boards idempotently**:
   ```powershell
   python -m src.monitoring.board_monitor --seed-catalog --allow-operational-db
   ```
6. **Run the offline beta smoke check** (added in Phase 8) to confirm app startup and search/detail/apply flows remain healthy:
   ```powershell
   python scripts/smoke.py
   ```
7. **Inspect live per-provider freshness distribution** (read-only) after initial polling completes:
   ```powershell
   python scripts/report_freshness.py --allow-operational-db
   ```
