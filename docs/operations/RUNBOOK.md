# Operations Runbook: Data Directory, SQLite Recovery & Catalog Seeding

Operational procedures for backing up, verifying, rehearsing restores, migrating to an external `BOTTOM_POT_DATA_DIR`, and safely seeding the curated employer board catalog.

---

## 1. Automated Backup Audit Finding (Baseline State)

An inspection of both the repository and the local Windows host established:

- **Repository inspection (`scripts/`, `src/`, `.github/workflows/`, `docs/`)**: No automated **database backup** scripts, backup cron jobs, CI backup workflows, or scheduled dump tasks exist in the repository. (Board-polling crons do exist via `/api/cron/monitor` in [`vercel.json`](../../vercel.json) and [`.github/workflows/board-monitor.yml`](../../.github/workflows/board-monitor.yml), which manage board refreshes rather than database backups.)
- **Host OS inspection (read-only `Get-ScheduledTask`)**: No Bottom Pot or SQLite backup tasks exist in Windows Task Scheduler (only built-in Windows `AppListBackup` and `RegIdleBackup` tasks were present).
- **Existing files in `data/`**: The preserved `data/cache.sqlite.bak-*` and `.cache.sqlite.restore-staging-*` artifacts came from one-off manual pre-repair snapshots and November 2026 forensic recovery (`ADR 0030`), not from any recurring schedule.
- **Agent action taken**: Zero OS scheduled tasks were created or modified, and no operational files were opened or moved. For recurring unattended local backups, register an OS task (Windows Task Scheduler or cron/systemd timer) invoking `scripts/db_backup.py backup` as a dedicated non-privileged command writing outside the repository tree.

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

## 7. Catalog Seeding Policy (Cloud Cron Default vs. Local Manual Seed)

The 28 direct employer boards catalogued across Steps 54–56 (`VERIFIED_EMPLOYER_BOARDS` in [`src/monitoring/employer_board_catalog.py`](../../src/monitoring/employer_board_catalog.py)) span `6` providers (`ashby`: 14, `greenhouse`: 5, `workable`: 4, `lever`: 2, `teamtailor`: 2, `recruitee`: 1 — `0` `pinpointhq`).

### Cloud Cron Behavior (`/api/cron/monitor`)

- **Auto-seeding is intended on `/api/cron/monitor` (`src/api/main.py`):** `GET`/`POST /api/cron/monitor` accepts `seed` (default **`true`**) and `max_boards` (default `10`, bounded **`1..28`**), acquires a `"board_monitor"` lease (`240s` TTL; returns `skipped: "lease_busy"` if held), and idempotently calls `monitor.seed_curated_boards()` whenever `seed=true`.
- Both [`vercel.json`](../../vercel.json) (`0 6 * * *`) and [`.github/workflows/board-monitor.yml`](../../.github/workflows/board-monitor.yml) call `/api/cron/monitor?max_boards=10` (so cloud deployments seed all 28 curated boards by default; pass `seed=false` to skip seeding on a cron invocation).

### Local Non-Cron SQLite Behavior & Manual Seed Sequence

On local non-cron SQLite runs, `BoardMonitor.run_loop` and `_ensure_db()` **do not auto-seed** curated boards; local SQLite databases keep curated boards unseeded until an operator explicitly seeds them after confirming recovery safeguards:

1. **Freshness ranking & recovery safety are active on `main`:** `FreshnessTier` ranking (`ADR 0034`, keeping older evergreen roles below `"Older postings"`) and WAL/SHM-safe backups/restore rehearsal (`scripts/db_backup.py`) protect live SQLite state before seeding.
2. **Exact Local Owner Seeding Sequence:**
   1. Read-only catalog preview (inspect all 28 boards and domains before touching SQLite):
      ```powershell
      python -m src.monitoring.board_monitor --preview-catalog
      ```
   2. Take a pre-seed WAL/SHM-safe backup:
      ```powershell
      python scripts/db_backup.py backup --output-dir C:\Backups\bottom-pot --label pre-catalog-seed --allow-operational-db
      ```
   3. Run an integrity check on the operational DB:
      ```powershell
      python scripts/db_backup.py check --allow-operational-db
      ```
   4. Rehearse restoring the pre-seed backup into a disposable workspace:
      ```powershell
      python scripts/db_backup.py rehearse --backup <pre-seed-backup-file>
      ```
   5. Seed all 28 catalogued boards idempotently:
      ```powershell
      python -m src.monitoring.board_monitor --seed-catalog --allow-operational-db
      ```
   6. Run the offline beta smoke check (`scripts/smoke.py`) to confirm app startup and search/detail/apply flows remain healthy:
      ```powershell
      python scripts/smoke.py
      ```
   7. Inspect live per-provider freshness distribution (read-only) after initial polling completes:
      ```powershell
      python scripts/report_freshness.py --allow-operational-db
      ```

---

## 8. Configuration Reference

Complete environment configuration resolved from [`src/core/settings.py`](../../src/core/settings.py), [`src/storage/db_conn.py`](../../src/storage/db_conn.py), [`src/safety/db_safety.py`](../../src/safety/db_safety.py), [`src/api/main.py`](../../src/api/main.py), [`.env.example`](../../.env.example), [`frontend/.env.example`](../../frontend/.env.example), and `frontend/src/lib/`. Rows marked **`[DIFFERS]`** actively override the code default in `.env.example`.

### Backend Settings (`src/core/settings.py`)

| Variable | Code Default | `.env.example` Default | Purpose |
|---|---|---|---|
| `SERPER_API_KEY` | `""` | `your_serper_api_key_here` (placeholder) | Serper Google Search API key for live ATS discovery |
| `SERPER_ENDPOINT` | `"https://google.serper.dev/search"` | *Omitted* | Serper REST search endpoint URL |
| `MAX_RESULTS` | `300` | `300` | Maximum job results emitted per search response when `max_results` is omitted (or upper bound for explicit caller caps) |
| `MONITORED_STORE_MAX_RESULTS` | `200` | `200` | Maximum monitored-store rows queried per search |
| `NIGERIAN_PER_SCRAPER_CAP` | `30` | `30` | Upper bound per Nigerian scraper when ATS platforms are active |
| `NIGERIAN_TOTAL_CAP` | `75` | `75` | Upper bound across all Nigerian scrapers when ATS platforms are active |
| `MAX_SERPER_QUERIES_PER_SEARCH` | `60` | `60` | Hard cap on outbound Serper queries per search run |
| `SERPER_MAX_PAGES` | `5` | `5` | Maximum pages fetched per Serper query |
| `RELEVANCE_MODE` | `"filter"` | `filter` | Title-first relevance gate mode (`"filter"` or `"off"`) |
| `SERPER_DAILY_BUDGET` | `500` | `500` | UTC daily outbound Serper query budget cap |
| `SERPER_MODE` | `"live"` | **`fallback` `[DIFFERS]`** | Serper execution mode (`"live"`, `"fallback"`, or `"cache_only"`) |
| `SERPER_FALLBACK_MIN_RESULTS` | `25` | `25` | Phase 1 ATS result threshold below which `"fallback"` triggers Serper |
| `SERPER_CACHE_TTL_HOURS` | `12` | `12` | Persistent cache TTL (hours) for Serper query results |
| `URL_CACHE_TTL_HOURS` | `24` | `24` | Persistent cache TTL (hours) for enriched job URLs |
| `MONITORING_ENABLED` | `False` | **`true` `[DIFFERS]`** | Enables background `BoardMonitor` polling (suppressed in test/Vercel contexts) |
| `MONITORING_INTERVAL_SECONDS` | `300` | *Omitted* | Polling loop sleep interval in seconds |
| `MONITORING_BOARD_INTERVAL_SECONDS` | `1800` | *Omitted* | Minimum re-poll interval per employer board in seconds |
| `MONITORING_CONCURRENCY_LIMIT` | `5` | *Omitted* | Concurrent board fetches per monitoring sweep |
| `MONITORING_BATCH_SIZE` | `25` | *Omitted* | Due boards fetched per local monitoring tick |
| `ATS_REQUEST_TIMEOUT_SECONDS` | `5` | `5` | Timeout (seconds) for direct ATS HTTP calls |
| `SCRAPER_REQUEST_TIMEOUT_SECONDS` | `10` | `10` | Timeout (seconds) for Nigerian board HTTP scrapes |
| `SEARCH_HARD_TIMEOUT_SECONDS` | `90` | `90` | Overall SSE search wall-clock budget in seconds |
| `PINPOINT_BOARD_REQUEST_TIMEOUT_SECONDS` | `25.0` | *Omitted* | Timeout (seconds) for Pinpoint `/postings.json` board feeds |
| `SCRAPER_DELAY_SECONDS` | `5.0` | **`1.5` `[DIFFERS]`** | Politeness delay (seconds) between Nigerian scraper requests |
| `CACHE_TTL_SECONDS` | `300` | `300` | In-memory search LRU cache TTL in seconds |
| `IN_MEMORY_CACHE_MAX_ENTRIES` | `100` | `100` | Maximum cached search entries retained in memory |
| `BOTTOM_POT_DATA_DIR` | Resolved OS data dir (or legacy `<repo>/data`) | Commented (`# BOTTOM_POT_DATA_DIR=`) | External operational directory for SQLite + CSV storage (`ADR 0032`) |
| `SQLITE_DB_PATH` | `<BOTTOM_POT_DATA_DIR>/cache.sqlite` | Commented (`# SQLITE_DB_PATH=data/cache.sqlite`) | Explicit SQLite database file path override |
| `DATABASE_URL` | `""` | Commented Neon PostgreSQL DSN | Primary Neon PostgreSQL connection string for cloud storage |
| `SUBSCRIPTIONS_FILE` | `<BOTTOM_POT_DATA_DIR>/subscriptions.csv` (or `./subscriptions.csv` legacy) | Commented (`# SUBSCRIPTIONS_FILE=subscriptions.csv`) | CSV fallback path for job alert subscriptions |
| `GLOBAL_CONCURRENCY_LIMIT` | `20` | `20` | Global outbound async HTTP request concurrency limit |
| `PER_HOST_CONCURRENCY_LIMIT` | `3` | `3` | Maximum simultaneous outbound requests per hostname |
| `CIRCUIT_BREAKER_FAILURE_THRESHOLD` | `5` | `5` | Consecutive host failures before opening circuit breaker |
| `CIRCUIT_BREAKER_COOLDOWN_SECONDS` | `600` | `600` | Cooldown duration (seconds) while host circuit is open |
| `MAX_RESPONSE_BYTES` | `3145728` (`3 MiB`) | `3145728` | Default fail-closed streaming byte limit per HTTP response |
| `RECRUITEE_BOARD_MAX_RESPONSE_BYTES` | `16777216` (`16 MiB`) | *Omitted* | Byte limit for Recruitee `/api/offers/` full-board snapshots |
| `PINPOINT_BOARD_MAX_RESPONSE_BYTES` | `3145728` (`3 MiB`) | *Omitted* | Byte limit for Pinpoint `/postings.json` board feeds |
| `RATE_LIMIT_PER_HOUR` | `20` | `20` | Legacy global per-IP hourly limit |
| `RATE_LIMIT_SEARCH` | `"20/hour"` | `20/hour` | `slowapi` rate limit for `GET /search` & `/api/search` |
| `RATE_LIMIT_SUBSCRIBE` | `"10/hour"` | `10/hour` | `slowapi` rate limit for `POST /subscribe` |
| `RATE_LIMIT_ELIGIBILITY` | `"60/minute"` | `60/minute` | `slowapi` rate limit for `POST /api/eligibility/evaluate` |
| `RATE_LIMIT_ADMIN_LOGIN` | `"5/minute"` | `5/minute` | `slowapi` rate limit for `POST /api/admin/login` |
| `TRUST_PROXY_HEADERS` | `False` | `false` | Honor `X-Forwarded-For` / proxy headers for rate limiting (also enabled when `VERCEL` is set) |
| `CORS_ALLOW_ORIGINS` | `"http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000,http://127.0.0.1:8000"` | Same | Comma-separated allowed browser origins for CORS |
| `ADMIN_PASSWORD` | `""` | `""` | Shared admin password required for `/admin` authentication |
| `ADMIN_SESSION_SECRET` | `""` | `""` | HMAC signing key for admin session cookies (required in serverless/prod) |
| `ADMIN_COOKIE_NAME` | `"bp_admin_session"` | *Omitted* | Cookie name for admin HMAC session token |
| `ADMIN_COOKIE_SAMESITE` | `"lax"` | `lax` | Cookie `SameSite` policy (`"none"` for cross-origin HTTPS deployments) |
| `ADMIN_COOKIE_MAX_AGE_SECONDS` | `604800` (`7d`) | *Omitted* | Admin session cookie lifetime in seconds |
| `CRON_SECRET` | `""` | `""` | Bearer secret protecting `GET`/`POST /api/cron/monitor` |
| `LOG_LEVEL` | `"INFO"` | `INFO` | Python logging level |

### Runtime & Safety Environment Flags (`os.environ`)

| Variable | Code Default | `.env.example` Default | Purpose |
|---|---|---|---|
| `POSTGRES_URL` | Unset | *Omitted* | Fallback PostgreSQL DSN checked by `src/storage/db_conn.py` after `DATABASE_URL` |
| `VERCEL` | Unset | *Omitted* | Disables in-process `BoardMonitor` startup and enables proxy client IP detection (`src/api/main.py`) |
| `BOTTOM_POT_ALLOW_OPERATIONAL_DB` | Unset (deny) | *Omitted (forbidden in `.env`)* | Explicit process opt-in (`1`) permitting non-test runtime access to operational SQLite (`src/safety/db_safety.py`) |
| `BOTTOM_POT_TEST_MODE` | Unset | *Omitted* | Forces disposable test-mode DB isolation (`src/safety/db_safety.py`, set by `scripts/verify.ps1`) |
| `BOTTOM_POT_PROTECTED_DATA_DIRS` | Unset | *Omitted* | Comma/pathsep list of extra directories protected as operational SQLite roots (`src/safety/db_safety.py`) |
| `BOTTOM_POT_TEST_EXTRA_PROTECTED_ROOT` | Unset | *Omitted* | Additional protected root used in operational DB safety tests (`src/safety/db_safety.py`) |
| `BOTTOM_POT_ALLOW_TEST_POSTGRES` | Unset | *Omitted* | Explicit opt-in (`1`) allowing Postgres connections inside test/CI contexts (`src/storage/db_conn.py`) |
| `PLAYWRIGHT_TEST`, `PLAYWRIGHT_SQLITE_DB_PATH` | Unset | *Omitted* | Signals Playwright E2E disposable DB isolation context (`src/safety/db_safety.py`) |

### Frontend Build Variables (`frontend/.env.example`, `.env.example`, `frontend/src/lib/`)

| Variable | Code Default | `.env.example` / `frontend/.env.example` Default | Purpose |
|---|---|---|---|
| `VITE_API_BASE_URL` | `""` (same-origin) | Commented (`# VITE_API_BASE_URL=`) in `frontend/.env.example` | Optional external backend origin for split-host SPA deploys (`frontend/src/lib/apiBase.ts`) |
| `VITE_LOGO_DEV_TOKEN` | `""` | Commented (`# VITE_LOGO_DEV_TOKEN=pk_...`) in both | Optional domain-restricted publishable `pk_*` Logo.dev token (`frontend/src/lib/logo.ts`; never use `sk_*`) |
| `VITE_REPORT_PROBLEM_URL` | `""` | Commented (`# VITE_REPORT_PROBLEM_URL=https://...`) in both | Optional `https://` or `mailto:` URL for listing issue reports (`frontend/src/lib/reportLink.ts`) |
| `VITE_CONTACT_EMAIL` | `""` | Commented (`# VITE_CONTACT_EMAIL=richmondsogo@gmail.com`) in `frontend/.env.example` | Optional public contact email displayed on `/contact` and in the footer (`frontend/src/lib/contactConfig.ts`) |
| `VITE_ENABLE_MOCK` | `false` (`DEV` only by default) | *Omitted* | Set to `"true"` to enable persisted `bp.mock` mode in production builds (`frontend/src/lib/mock.ts`) |

---

## 9. Search Caching, Canonicalization & `v2` URL Cache Invalidation

- **Boundary canonicalization & effective caps (`src/discovery/search_canonicalizer.py`, `src/discovery/query_builder.py`):** Incoming search requests normalize whitespace, NFKC compatibility forms, quotes/dashes, separator spacing, casefolding (while preserving keyword token order), and sorted unique platform/exclude lists before building `api-v4-canonical` search cache keys or ATS `site:` dork queries. Explicit `SearchParams.max_results` overrides apply only when present in `model_fields_set`; otherwise searches inherit `MAX_RESULTS`.
- **Single-flight request coalescing (`SingleFlightRegistry`):** Concurrent searches sharing one canonical `cache_key` attach to the active leader instead of firing duplicate Serper/board scrapes. Follower client disconnects stop waiting without canceling the leader, and leader errors/cancellations abort cleanly without poisoning subsequent callers. Degraded or empty searches (`budget_exhausted`, `timed_out`, `had_failure`, `partial`, or zero results) skip in-memory search caching.
- **Persistent `serper-v2:` & `v2` `url_cache` invalidation (`src/storage/cache_store.py`):** Persistent Serper cache keys use `serper-v2:` sorted-payload SHA-256 hashes, and `url_cache` writes attach `_url_cache_version: "v2"` (`URL_CACHE_VERSION = "v2"`) inside `listing_json`. Legacy unversioned rows are automatically ignored on `CacheStore` reads (triggering clean re-enrichment on demand) while `url_cache.url` keys stay canonical.
