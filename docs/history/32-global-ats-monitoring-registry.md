# Step 32: Global ATS Discovery, Independent Monitoring & Extraction Reliability

## Overview
- **Goal**:
  1. Reconcile frontend and backend platform inventories across all 18 configured ATS platforms and 3 active Nigerian job boards (21 platforms total).
  2. Implement an automatically growing SQLite company-board registry (`company_boards` table) that indexes verified public boards, rejects placeholders and stopwords, and deduplicates records.
  3. Build an independent, pluggable ATS company-board monitoring engine with adapters for Greenhouse, Lever, and Ashby, supporting conditional HTTP headers (ETag, If-Modified-Since), content fingerprinting, exponential backoff, and a standalone CLI runner (`python -m src.project_files.board_monitor`).
  4. Harden Nigerian scrapers: clean title suffixes, implement bounded detail enrichment for MyJobMag, and extract direct external ATS application links from Jobberman, MyJobMag, and HotNigerianJobs to automatically feed candidate boards into the registry.
  5. Decouple Serper by making `serper_api_key: str = ""` optional in `src/config.py`, gracefully bypassing live Serper calls when unconfigured or budget-exhausted while preserving direct board probes and Nigerian scrapers.
  6. Final Correctness Pass & Engineering Review Gaps:
     - Implemented durable SQLite `registry_meta.store_version` counter incremented transactionally for genuine cross-process cache invalidation.
     - Implemented tri-state remote filtering (`True`, `False`, `None`) and authoritative `posted_at` date filtering on monitored jobs.
     - Corrected explicit empty platform selection (`platforms=""` searches 0 providers, omitted uses default provider set).
     - Enhanced Greenhouse monitored job descriptions with `?content=true`, authentic description HTML/markdown normalization, and requirements extraction.
     - Upgraded platform migration detection to exact set matching against historical full inventories (16, 18, 19, 21), preserving custom 16-provider selections.
     - Strengthened Nigerian scraper tests with real `MyJobMagScraper.clean_title` execution, contextual apply link rejection of headers/footers/nav/related widgets, and representative fixture labeling.
     - Addressed monitoring backlog growth with starvation-free scheduling order and exposed capacity/backlog metrics in `get_monitoring_status()`.
     - Added end-to-end integration test (`tests/test_e2e_monitored_search_flow.py`) verifying full discovery, canonical extraction, search without Serper, deduplication, cache invalidation, and filtering.
- **PR**: https://github.com/richmondsogo/bottom-pot/pull/36 (live PR head is the source of truth for latest commit)
- **Branch**: `step/32-global-ats-monitoring-registry`
- **First Commit SHA**: `5e15758`
- **Merge Commit SHA**: Pending

---

## Architecture & Engineering Correctness Resolutions

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

### 2. Canonical Extraction Integration & Greenhouse Authentic Descriptions
- Board adapters (`GreenhouseBoardAdapter`, `LeverBoardAdapter`, `AshbyBoardAdapter`) pass all discovered postings through the canonical extraction pipeline:
  ```
  RawJobPosting -> JobExtractionService.extract(raw) -> CanonicalJobAdapter.to_listing(canonical)
  ```
- In `GreenhouseBoardAdapter`:
  - Queries public board API with `?content=true` to obtain authentic description HTML.
  - Generates content hashes embedded in the board fingerprint so content modifications trigger updates.
  - Normalizes authentic HTML into markdown and extracts requirements sections.
  - Sets `description_is_authentic=True` only when content is actually provided by Greenhouse.
  - Stores complete canonical JSON payload in `canonical_json` column.

### 3. Monitored Jobs Available to Ordinary Searches & Cross-Process Revision
- Extended `SearchOrchestrator` in `src/project_files/search_pipeline.py`:
  - `_search_monitored_store` executes concurrently alongside live ATS probes and Nigerian scrapers.
  - Returns local matches even when Serper is unconfigured, budget-exhausted, or down.
  - Normalizes and deduplicates via `GlobalDeduplicator`.
  - Supports tri-state remote filtering: `True` (remote only), `False` (exclude remote, matching UI option), `None` (all).
  - Uses authoritative `posted_at` date filtering (cutoff relative to employer posting date; excludes undated jobs when date filter is active).
  - Emits results into the SSE streaming pipeline.
- Cross-Process SQLite Revision:
  - Created `registry_meta` table in SQLite storing `store_version`.
  - Atomically and transactionally increments `store_version` on job upsert, lifecycle closure, and table clearance.
  - `get_monitored_store_version()` reads the durable shared database revision, ensuring CLI monitor workers and multi-worker API processes instantly invalidate whole-search cache entries upon discovery without restart.

### 4. Scheduler Improvements, Backlog Growth & Anti-Starvation
- Configurable settings in `src/config.py`:
  - `monitoring_batch_size: int = 25` (capped boards per cycle).
  - `monitoring_interval_seconds: int = 300` (polling cycle interval).
  - `monitoring_board_interval_seconds: int = 1800` (target interval per board).
  - `monitoring_concurrency_limit: int = 5` (semaphore bound).
- Anti-Starvation Scheduling Policy:
  - Ordered by `CASE WHEN next_scheduled_check IS NULL THEN 0 ELSE 1 END, next_scheduled_check ASC, polling_priority DESC`.
  - Unchecked candidate boards are prioritized first.
  - Overdue boards are drained strictly in order of wait time (oldest `next_scheduled_check` first), guaranteeing that lower-priority boards are never starved by higher-priority boards.
- Backlog Metrics & Capacity Limits:
  - `get_monitoring_status()` exposes `due_boards`, `overdue_boards`, `oldest_overdue_seconds`, `hourly_check_capacity` (300 checks/hr default), and `sustainable_board_count` (150 boards at 30m intervals).
- Cross-Process Lease Locking:
  - `monitor_leases` table with heartbeat and TTL ensures only one monitor instance runs concurrently, safe on Windows and Linux.

### 5. Explicit Empty Platform Selection Contract
- Contract:
  - Omitted `platforms` parameter (`None`): runs default provider selection (all configured providers).
  - Explicitly empty `platforms` parameter (`[]`, transmitted as `platforms=` or `platforms=""` from frontend): runs zero providers.
  - Non-empty `platforms` parameter: runs only specified providers.
- Implemented in `frontend/src/App.tsx`, `src/api/main.py`, `src/project_files/query_builder.py`, and `src/project_files/search_pipeline.py`.
- Verified across `build_ats_queries`, direct-board routing, Nigerian scrapers, and monitored job store.

### 6. Platform Migration Detection via Exact Set Matching
- In `frontend/src/lib/platformMigration.ts`:
  - Replaced count-based thresholds with exact set equality (`setsEqual`) against known historical full inventories:
    - 16 platforms (early ATS set)
    - 18 platforms (ATS set with added providers)
    - 19 platforms (ATS set + Jobberman)
    - 21 platforms (current full inventory)
  - Upgrades genuine previous full selections to 21 platforms.
  - Preserves intentional custom subsets (including custom 16-platform selections) without expanding them.
  - Preserves explicit empty selection across page reloads.

### 7. Nigerian Source Reliability & Representative Fixtures
- Representative Fixture Labeling:
  - Accurately labeled `tests/fixtures/nigerian/` files as representative/synthetic HTML captures, preserving documentation honesty.
- Real Title Cleaning:
  - Extracted `MyJobMagScraper.clean_title` as a testable method.
  - Verified that legitimate titles ("Live at Home Carer", "Architect at Sea") remain intact, while genuine company suffixes ("... at Kuda Bank") are removed when supported by source data.
- Contextual Apply Link Discovery:
  - `_find_contextual_apply_link` targets authentic application buttons and sections while strictly ignoring `<header>`, `<footer>`, `<nav>`, `<aside>`, and related-job widgets.
- Scoped Roundup Parsing:
  - `HotNigerianJobsScraper` preserves per-position scoping, preventing link and description bleed across multiple roles in a single post.

### 8. Greenhouse Posting-Date Semantics & Production Monitor Wiring
- `GreenhouseBoardAdapter` decoupled update timestamps from posting dates:
  - Uses authoritative `first_published` when available; exposes `get_job_detail` for `/v1/boards/{token}/jobs/{id}` lookup.
  - Wired into production monitoring: `BoardMonitor.check_single_board` queries `registry.get_known_publication_dates(board_id)` and calls `GreenhouseBoardAdapter.check_board(fetch_publication_dates=True, known_publication_dates=known_dates)`.
  - Bounded concurrency: queries individual endpoints via `asyncio.Semaphore(max(1, concurrency_limit))` only for newly discovered jobs lacking both `first_published` on list response and an existing date in `known_dates`.
  - Redundancy elimination: subsequent board checks for unchanged or updated listings preserve known publication dates without making repeated individual detail calls.
  - Does NOT fall back to `updated_at` as `posted_at`; if authoritative publication date is genuinely absent or unavailable, preserves `posted_at=None`.
  - Preserves `updated_at` in raw fields and continues using it for board fingerprinting / change detection.
  - Regression verified: recent `updated_at` with older `first_published` is excluded from recent-posting window searches (`posted_within_days=7`).

### 9. Work-Model Precedence Over Location Text
- In `CompanyBoardRegistry.search_monitored_jobs`:
  - Normalized work model takes strict precedence over location string heuristics:
    - Explicit `hybrid` and `onsite` jobs are retained in `is_remote=False` searches even when location text contains "Remote" (e.g. `work_model='hybrid'`, `location='Remote, London'`).
    - Explicit `remote` jobs are returned for `is_remote=True` and excluded from `is_remote=False`.
    - Location text heuristics are reserved strictly for unknown work arrangements (`work_model IS NULL`).
  - Regression verified: hybrid and onsite jobs with "Remote" in location are correctly categorized and never conflated with remote-only.

### 10. In-Orchestrator Cross-Source Deduplication & Material Field Propagation
- Resolved equal-rank deduplication propagation issue:
  - Previously, `GlobalDeduplicator.filter()` only emitted merged duplicates if `rank_incoming > rank_existing`. When two equal-ranked sources (e.g. both `data_source="api"`) discovered the same posting, metadata was merged internally but no update was emitted to `SearchOrchestrator`, leaving `all_collected` with stale/incomplete data.
  - Implemented `is_material_improvement(existing, merged)`: detects when an incoming duplicate supplies valuable fields that the existing emitted record lacked (description, requirements, salary, work model, location, posted date, or significant confidence gain) while suppressing meaningless updates when content is identical.
  - `GlobalDeduplicator.filter()` now emits whenever `rank_incoming > rank_existing` OR `is_material_improvement(existing, merged)` is true.
  - `SearchOrchestrator.run()` matches the emitted upgrade in `all_collected` using ID and aliases, replaces it in-place, and streams the updated record to SSE and the whole-search cache without increasing total result count.
- Strengthened Acceptance Integration Test (`test_e2e_monitored_search_flow.py`):
  - Replaced manual invocation with a call-tracking mock for `probe_direct_boards`, asserting that the orchestrator itself invokes the probe with extracted company slug (`"acme"`).
  - Enforced deterministic arrival order via slight delay so the monitored store's lean record emits first, and the direct board's enriched record arrives second.
  - Asserted both sources independently produced matching records with identical application URLs but distinct IDs.
  - Asserted the second source contributed rich description and requirements that the monitored record lacked.
  - Asserted the final emitted SSE result contained the enriched metadata and exactly one representation was emitted in `done_event.total` and accumulated results, with zero Serper calls.

### 11. URL State Architectural Note
- Verified `frontend/src/lib/urlState.ts`:
  - `urlState.ts` manages shareable URL query params (`q`, `loc`, `wm`, `age`, `ng`, `flt`, `prov`, `rem`, `emp`, `sal`, `saved`) and deliberately avoids serializing 21 provider slugs into the browser address bar.
  - Platform selections are managed via `localStorage` ('bp.selectedPlatforms.v1') and `platformMigration.ts`.
  - `frontend/src/App.tsx` directly formats the API request query string (`queryParams.set('platforms', '')` when empty, `platforms=...` when custom, omitted when default all).
  - The request contract is fully satisfied without modifying `urlState.ts`.

---

## Verification Evidence

1. **Backend Pytest Suite**:
   - Command: `pytest`
   - Output: `621 passed, 4 warnings in 61.51s` (100% pass rate across all 621 tests).
2. **Frontend Vitest Suite**:
   - Command: `npm --prefix frontend test -- --run`
   - Output: `15 test files passed, 106 tests passed in 11.44s`.
3. **Frontend Linting**:
   - Command: `npm --prefix frontend run lint`
   - Output: `oxlint`: 0 errors (3 warnings for button/toggle fast-refresh exports).
4. **Frontend Production Build**:
   - Command: `npm --prefix frontend run build`
   - Output: `tsc -b && vite build` completed in 6.64s.
5. **Playwright E2E Browser Suite**:
   - Command: `npx playwright test`
   - Output: `36 passed (1.5m)`.
6. **Full Verification Suite (`scripts/verify.ps1`)**:
   - Command: `powershell -ExecutionPolicy Bypass -File .\scripts\verify.ps1`
   - Output: `Results: 8 passed, 0 failed, 0 skipped (of 8 checks)`.
7. **End-to-End Monitored Search Flow (`tests/test_e2e_monitored_search_flow.py`)**:
   - Verified end-to-end: employer board registration -> board check with mock response -> canonical extraction -> SQLite persistence -> SearchOrchestrator keyword search without Serper -> real in-orchestrator cross-source deduplication -> cross-instance cache invalidation via SQLite revision -> tri-state remote and date filtering -> empty platform selection.
