# Step 32: Global ATS Discovery, Independent Monitoring & Extraction Reliability

## Overview
- **Goal**:
  1. Reconcile frontend and backend platform inventories across all 18 configured ATS platforms and 3 active Nigerian job boards (21 platforms total).
  2. Implement an automatically growing SQLite company-board registry (`company_boards` table) that indexes verified public boards, rejects placeholders and stopwords, and deduplicates records.
  3. Build an independent, pluggable ATS company-board monitoring engine with adapters for Greenhouse, Lever, and Ashby, supporting conditional HTTP headers (ETag, If-Modified-Since), content fingerprinting, exponential backoff, and a standalone CLI runner (`python -m src.project_files.board_monitor`).
  4. Harden Nigerian scrapers: clean title suffixes, implement bounded detail enrichment for MyJobMag, and extract direct external ATS application links from Jobberman, MyJobMag, and HotNigerianJobs to automatically feed candidate boards into the registry.
  5. Decouple Serper by making `serper_api_key: str = ""` optional in `src/config.py`, gracefully bypassing live Serper calls when unconfigured or budget-exhausted while preserving direct board probes and Nigerian scrapers.
  6. Resolve all 10 independent engineering review gaps:
     - Implement durable SQLite `monitored_jobs` store with FTS5 keyword search and lifecycle tracking.
     - Route monitored postings through canonical extraction (`RawJobPosting` -> `JobExtractionService` -> `CanonicalJobAdapter`).
     - Query local store in `SearchOrchestrator`, deduplicating and streaming to ordinary searches with cache versioning.
     - Add configurable batch size, concurrency, jitter (1800±180s), and visibility into due boards.
     - Implement cross-process SQLite lease locking (`monitor_leases` table with heartbeat and TTL) for Windows compatibility.
     - Implement 3-tuple `(job_id, timestamp, content_hash)` adapter change detection.
     - Handle unverified ATS routes by returning `None` from `build_canonical_board_url`.
     - Harden Nigerian scrapers with contextual apply buttons, safe title cleaning, and scoped roundup enrichment backed by real HTML fixtures.
     - Implement versioned frontend platform migration (`migrateStoredPlatforms`) preserving "Select none" across page reloads.
     - Pass full test suite (pytest, vitest, oxlint, build, playwright e2e, verify.ps1).
- **PR**: https://github.com/richmondsogo/bottom-pot/pull/36
- **Branch**: `step/32-global-ats-monitoring-registry`
- **First Commit SHA**: `5e15758`
- **Last Commit SHA**: `Pending (review gap resolutions)`
- **Merge Commit SHA**: Pending

---

## Architecture & Engineering Gap Resolutions

### 1. Persistent Searchable Job Store (`monitored_jobs` & FTS5)
- Replaced 24-hour `url_cache` reliance with durable `monitored_jobs` table in SQLite:
  - Columns: `job_id`, `board_id`, `ats_provider`, `company_slug`, `company_name`, `title`, `location`, `work_model`, `employment_type`, `salary`, `description`, `requirements`, `posted_at`, `first_discovered_at`, `last_checked_at`, `source_url`, `apply_url`, `confidence_score`, `source_evidence`, `status`, `content_fingerprint`, `canonical_json`.
  - Indexes: `idx_monitored_jobs_board`, `idx_monitored_jobs_status`, `idx_monitored_jobs_posted`, `idx_monitored_jobs_provider`.
- SQLite FTS5 Full-Text Search:
  - Virtual table `monitored_jobs_fts` with `unicode61 remove_diacritics 2` tokenization indexing `title`, `company_name`, `location`, `description`.
  - Automated SQLite synchronization triggers (`trg_monitored_jobs_ai`, `trg_monitored_jobs_ad`, `trg_monitored_jobs_au`).
- Explicit Lifecycle Policy:
  - Jobs are upserted with `status = 'active'`.
  - When a board poll succeeds, `mark_missing_jobs_closed(board_id, active_job_ids)` transitions absent jobs to `status = 'closed'` while preserving full provenance and discovery history.

### 2. Canonical Extraction Integration
- Board adapters (`GreenhouseBoardAdapter`, `LeverBoardAdapter`, `AshbyBoardAdapter`) pass all discovered postings through the canonical extraction pipeline:
  ```
  RawJobPosting -> JobExtractionService.extract(raw) -> CanonicalJobAdapter.to_listing(canonical)
  ```
- Retains authentic ATS provenance without synthetic metadata fabrication.
- Stores complete canonical JSON payload in `canonical_json` column.

### 3. Monitored Jobs Available to Ordinary Searches
- Extended `SearchOrchestrator` in `src/project_files/search_pipeline.py`:
  - `_search_monitored_store` executes concurrently alongside live ATS probes and Nigerian scrapers.
  - Returns local matches even when Serper is unconfigured, budget-exhausted, or down.
  - Normalizes and deduplicates via `GlobalDeduplicator`.
  - Respects keyword search, location, remote filter (`remote=True`), date range, and platform selection.
  - Emits results into the SSE streaming pipeline.
- Cache Invalidation & Versioning:
  - Embedded `company_board_registry.get_monitored_store_version()` into `SearchOrchestrator._cache_key`.
  - Whenever `upsert_monitored_job` writes new or updated listings, the version increments atomically, instantly invalidating stale in-memory cached searches without race conditions.

### 4. Scheduler Improvements & Concurrency
- Configurable settings in `src/config.py`:
  - `monitoring_batch_size: int = 25` (capped boards per cycle).
  - `monitoring_board_interval_seconds: int = 1800` (base interval).
  - `monitoring_concurrency_limit: int = 5`.
- Interval Jitter & Backoff:
  - Added ±10% random jitter ($1800 \pm 180$ seconds) to prevent thundering herds against ATS endpoints.
  - Exponential backoff on failure ($30m \to 1h \to 2h \dots 48h$).
- Observability:
  - `get_monitoring_status()` provides counts of active boards, due boards, overdue boards, and active monitored jobs.

### 5. Cross-Process Process Locking & Windows Compatibility
- Replaced fragile PID file check (`data/monitor.lock`) with cross-process SQLite lease table (`monitor_leases`):
  - Schema: `lease_name PRIMARY KEY`, `holder_id`, `acquired_at`, `heartbeat_at`, `ttl_seconds`.
  - Thread-safe, multiprocess-safe, and 100% compatible with Windows file locking and process termination.
  - Continuous heartbeat every 20 seconds; automatically cleans up stale leases when TTL (60s) expires.

### 6. Adapter Change Detection
- Backwards-compatible SHA256 fingerprinting supporting 3-tuples `(job_id, timestamp, content_hash)`.
- Distinguishes:
  - HTTP 304 Not Modified.
  - Board content fingerprint unchanged.
  - New posting discovered.
  - Materially modified posting (content changed even if provider timestamp omitted).
  - Closed/removed posting.

### 7. Company-Board Identity Edge Cases
- `build_canonical_board_url` in `company_board_registry.py` returns `None` for ATS providers without authentic public board endpoints (`workday`, `taleo`, `sap`, `avature`, `jobadder`, `icims`).
- Discovered postings from these providers proceed through normal search and extraction pipelines without failing or polluting the monitoring queue with dead endpoints.

### 8. Nigerian Source Reliability & Real Fixtures
- Contextual apply link discovery:
  - `_find_contextual_apply_link` in `nigerian_scrapers.py` targets dedicated apply buttons, application sections, and explicit call-to-actions, avoiding site headers, footers, social share widgets, and ads.
  - Wired into `JobbermanScraper._enrich_detail` and `MyJobMagScraper._enrich_detail`.
- Safe title cleaning:
  - In `MyJobMagScraper.search_result`, only strips verified company suffix `at <Company>` when matched against known company name. Preserves valid titles like "Live at Home Carer", "Architect at Sea".
- Scoped roundup parsing:
  - In `HotNigerianJobsScraper.enrich_listing_from_detail`, scopes apply links, candidate ATS registration, and descriptions strictly to the matching sub-role section (`matching_role_tags` and `shared_app_tags`), never pulling links from unrelated positions in the roundup.
- Real HTML Fixtures:
  - `tests/fixtures/nigerian/jobberman_sample_detail.html` (Captured 2026-10-18)
  - `tests/fixtures/nigerian/myjobmag_sample_detail.html` (Captured 2026-10-22)
  - `tests/fixtures/nigerian/hotnigerianjobs_roundup_detail.html` (Captured 2026-10-25)
  - Tested in `tests/test_nigerian_enrichment_fixtures.py`.

### 9. Frontend Platform Selection Migration & "Select None" Fix
- Added `frontend/src/lib/platformMigration.ts` with `migrateStoredPlatforms`:
  - `CURRENT_PLATFORM_VERSION = '32'`.
  - Explicitly preserves `[]` when user clicks "Select none", persisting across page reload.
  - Upgrades users who had all platforms selected under prior versions (16 or 19 platforms) to receive all 21 current platforms.
  - Preserves custom subsets (e.g. `['greenhouse', 'lever']`) without forcing unwanted platforms.
  - Tested with 7 vitest unit tests in `frontend/src/lib/__tests__/platformMigration.test.ts`.

---

## Verification Evidence

1. **Backend Pytest Suite**:
   - Command: `pytest`
   - Output: `603 passed, 4 warnings in 48.42s` (100% pass rate across all 603 tests).
2. **Frontend Vitest Suite**:
   - Command: `npm --prefix frontend test`
   - Output: `14 test files passed, 101 tests passed in 6.00s`.
3. **Frontend Linting**:
   - Command: `npm --prefix frontend run lint`
   - Output: `oxlint`: 0 errors.
4. **Frontend Production Build**:
   - Command: `npm --prefix frontend run build`
   - Output: `tsc -b && vite build` completed in 2.69s.
5. **Playwright E2E Browser Suite**:
   - Command: `npx playwright test`
   - Output: `36 passed (1.5m)`.
6. **Full Verification Suite (`scripts/verify.ps1`)**:
   - Command: `.\scripts\verify.ps1`
   - Output: `Results: 8 passed, 0 failed, 0 skipped (of 8 checks)`.
