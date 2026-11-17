# Step 45: SmartRecruiters Quality Pipeline, Monitoring & Direct Routing

**Date:** 2026-11-16  
**Branch:** `step/45-smartrecruiters-quality-pipeline`  
**Base Commit (`main`):** `c4e8a1654d5ad31dc69b0088e7a462878be42e1c` (Step 44 SmartRecruiters Monitoring Feasibility Investigation)  
**Serper Credits Spent:** `0`  
**Continuous Monitoring Activation:** Unchanged (`settings.monitoring_enabled = False`)

---

## 1. Scope

Upgraded SmartRecruiters from a provisional posting-only integration to a first-class, deterministically extracted, independently monitorable, and directly routable ATS provider across the Bottom Pot pipeline while preserving all existing working SmartRecruiters extraction behavior and leaving all other ATS providers' lifecycle semantics untouched:

1. Consistent URL parsing, canonical lowercase identity normalization, reserved-path guards, and board-root registration.
2. Shared deterministic converter `smartrecruiters_payload_to_raw(...)` fixing the `ref` -> `apply_url` bug and preserving `postingUrl` vs `applyUrl` (`?oga=true`) separation.
3. Eligibility extraction and description-based requirements fallback (with structured `qualifications` prioritized) in `JobExtractionService`.
4. Bounded, 7-day SQLite-cached, single-flight company logo extraction from authentic posting HTML (`c.smartrecruiters.com/sr-company-logo-prod-*`), rejecting platform wordmarks (`av-www.smartrecruiters.com/sr-logo/...`).
5. Independent monitoring (`SmartRecruitersBoardAdapter`) with sequential `limit=100` pagination, atomic snapshot validation, full-board SHA-256 fingerprinting, bounded fair detail hydration, and durable 2-snapshot missing-job confirmation.
6. Promotion of `"smartrecruiters"` from `PROVISIONAL_PROVIDERS` to `MONITORABLE_PROVIDERS` and registration in `BOARD_ADAPTERS`.
7. Direct-board probing (`probe_smartrecruiters_board`) wired into `probe_direct_boards()` and `SearchOrchestrator._search_direct_boards()` auto-registration.
8. Offline deterministic unit and integration regression coverage across all 7 investigation fixtures, 4 pre-existing detail fixtures, and 2 newly captured posting HTML fixtures.

---

## 2. Implementation Decisions

### URL Parsing, Identity & Canonicalization (`ats_url_parser.py`, `url_normalizer.py`, `search_pipeline.py`)

- **Canonical lowercase `company_slug`**: `parse_ats_url()` normalizes SmartRecruiters `company_slug` to lowercase (`"Wise"` -> `"wise"`) while preserving numeric `job_id` and supporting both `jobs.smartrecruiters.com` and `careers.smartrecruiters.com`.
- **Reserved-path guards**: Rejects non-company platform paths (`api`, `app`, `apply`, `assets`, `auth`, `blog`, `careers`, `companies`, `company`, `docs`, `embed`, `external-referrals`, `favicon.ico`, `help`, `img`, `images`, `internal`, `job`, `jobs`, `login`, `postings`, `privacy`, `robots.txt`, `search`, `sign-up`, `signup`, `sitemap.xml`, `static`, `status`, `support`, `terms`, `www`) and dotted slugs.
- **Board-root discovery**: Added `parse_smartrecruiters_board_root_url()` matching single-segment `{jobs,careers}.smartrecruiters.com/{slug}` board roots without mistaking 2-segment posting URLs for board roots; wired into `SearchOrchestrator._enrich_ats_item()`.
- **Customer-facing URL preservation vs. deduplication keys**:
  - `normalize_job_url(..., "smartrecruiters")` upgrades `http` -> `https`, strips universal tracking parameters (`utm_*`, `gclid`, etc.), and **preserves** `?oga=true`, authoritative casing, and path title slugs so `apply_url` remains distinct from `source_url`.
  - `canonicalize_smartrecruiters_posting_url()` and `build_url_match_key(..., "smartrecruiters")` lowercase the company segment and strip conservative SmartRecruiters apply/tracking parameters (`oga`, `dcr_ci`, `trid`) while preserving `{id}-{title-slug}` path information, collapsing `Wise` vs `wise` and `?oga=true` during deduplication.
- **Display names**: `company` and `board.company_name` preserve authoritative API display casing (`"Wise"`, `"Nearmap"`, `"Scalable GmbH"`).

### Shared Converter & Extraction Quality (`ats_api_client.py`, `job_extraction_service.py`)

- Extracted `smartrecruiters_payload_to_raw(...)` used by `SmartRecruitersClient`, `SmartRecruitersBoardAdapter`, and `probe_smartrecruiters_board`.
- **URL bug fix**: `source_url` uses validated `postingUrl` (never `ref`), and `apply_url` uses validated `applyUrl` falling back to `postingUrl` then validated `fallback_source_url` (or verified numeric-ID `https://jobs.smartrecruiters.com/{company_identifier}/{id}`). The API `ref` URL is never surfaced as a candidate-facing link.
- **Numeric-ID URL verification**: Live public GETs confirmed `https://jobs.smartrecruiters.com/Nearmap/744000161158698` and `https://jobs.smartrecruiters.com/Wise/744000161639339` (without title slugs) both return HTTP `200 OK` with full posting HTML identical in byte length to their full-slug counterparts (`124,812` and `121,757` bytes). Listing-only fallbacks therefore emit a verified candidate-facing numeric-ID `source_url` (with `apply_url = source_url` and `description_is_authentic = False`, never fabricating `?oga=true` or exposing `ref`).
- **Work-model & uncertainty**: Preserved `remote`/`hybrid` semantics and added explicit `workplace_flags_conflict` signaling when both `remote=True` and `hybrid=True` are set simultaneously so `JobExtractionService` leaves `work_model=None` per ADR 0001/0002.
- **Eligibility & requirements**: Opted `"smartrecruiters"` into `JobExtractionService` eligibility extraction and description-based requirements fallback while preserving `jobAd.sections.qualifications` as the higher-priority source. Nigeria eligibility is never inferred from physical location or job title alone.
- **Documented Step 45 golden snapshot diffs (`tests/test_real_api_fixtures.py`)**: Updated assertions for the 4 `smartrecruiters_*.json` golden replays to document lowercased `id`/`company_slug`, authoritative `postingUrl` (`source_url`) and `applyUrl?oga=true` (`apply_url`), and newly extracted structured `eligibility` (`physical_location_country` from `location.country`).

### Verified Company Logo Extraction (`logo_extractor.py`, `ats_api_client.py`)

- Added `_extract_smartrecruiters_logo()` accepting only verified `https://c.smartrecruiters.com/sr-company-logo-prod-*` assets from `span.header-logo img`, `meta[itemprop='logo']`, or JSON-LD `hiringOrganization.logo`, and strictly rejecting `av-www.smartrecruiters.com/sr-logo/...` platform wordmarks, `sr-jobad/static/...`, `default_social_logo` banners, and untrusted hosts.
- Added bounded, 7-day SQLite-cached, single-flight coalesced `enrich_smartrecruiters_board_identity()` fetching at most 1 validated posting page HTML (using `use_resilience=True` in monitoring/direct routing and `use_resilience=False` inside `SmartRecruitersClient` search enrichment to avoid nested host semaphores), persisting both positive and negative cache timestamps without overwriting verified logos.

---

## 3. Pagination & Atomic Snapshot Semantics (`board_adapters.py`)

- Endpoint: `GET https://api.smartrecruiters.com/v1/companies/{companyIdentifier}/postings?limit=100&offset={offset}&destination=PUBLIC` routed through `throttled_get()`.
- **No arbitrary total coverage caps**: Pages drain sequentially (`offset += len(content)`) with no artificial board, job, or page cap (tested across 109 real jobs and 320 multi-page jobs).
- **No multi-page ETag short-circuit**: Conditional `If-None-Match` is never sent on SmartRecruiters pagination requests; `SmartRecruitersBoardAdapter` drains all pages and evaluates the deterministic full-board SHA-256 `content_fingerprint` (`compute_board_fingerprint`) built from `(id, releasedDate, _smartrecruiters_listing_item_hash(item))` tuples.
- **Atomic page & snapshot validation (`validate_smartrecruiters_page`)**: Every page must return HTTP `200`, valid JSON object shape, exact `offset == requested_offset`, integer `1 <= limit <= 100`, non-negative integer `totalFound` matching page 0 across all subsequent pages, list `content`, no short non-final pages, no premature empty pages, no zero-progress pagination, `visibility == "PUBLIC"` on every item, valid numeric `id` and non-empty `name` on every item, no duplicate IDs or repeated pages across pagination, and final unique item count `== totalFound`. Any violation fails the entire snapshot (`BoardCheckResult(success=False)` / `[]` in direct probe).

---

## 4. Hydration Throughput & Fairness Policy (`board_adapters.py`)

- Every `ref` URL is validated against `https://api.smartrecruiters.com/v1/companies/{slug}/postings/{id}` (`validate_smartrecruiters_ref_url`) before fetching; untrusted or mismatched URLs are never fetched.
- All detail requests run through `throttled_get()` under `api.smartrecruiters.com`'s shared `per_host_concurrency_limit = 3`, `global_concurrency_limit = 20`, circuit breaker, and `429 Retry-After` backoff (plus an inner `asyncio.Semaphore(3)`).
- **Per-poll throughput budgets (not lifetime caps)**:
  - `SmartRecruitersBoardAdapter`: `max_new_hydrations_per_poll = 20` and `max_revalidations_per_poll = 10` (with 6h `detail_revalidate_ttl_seconds = 21600.0`). At ~325 ms per detail request and concurrency 3, 20–30 detail requests take ~2.2–3.3s per poll.
  - `probe_smartrecruiters_board`: `max_detail_fetches = 15` (`~1.6s`).
- **Starvation prevention & fair drainage**:
  - Pending/new hydration and stale-detail revalidation use separate budgets so neither starves the other.
  - Already-known unhydrated jobs (`detail_last_hydrated_at is None`, due for retry/pending) are prioritized **ahead** of newly arrived postings so older pending jobs never starve behind continuous new arrivals on active boards.
  - Listing payload changes (`_smartrecruiters_listing_item_hash` persisted in `monitored_jobs.listing_item_hash`) trigger immediate rehydration.
  - Detail `404` (`detail_404`) and transient failures (`transient_error`, `invalid_detail`) preserve rich cached listings, never close active jobs present in the public listing, and enter bounded exponential retry backoff (`5m -> 15m -> 30m -> 1h -> 2h -> 6h` transient/invalid; `1h -> 2h -> 4h -> 6h` on 404).

---

## 5. Missing-Job Confirmation Policy (`company_board_registry.py`, `board_monitor.py`)

- Added durable SQLite columns on `monitored_jobs`: `missing_confirmation_count INTEGER NOT NULL DEFAULT 0` and `missing_first_seen_at REAL` (plus `listing_item_hash TEXT`).
- SmartRecruiters sets `BoardCheckResult.missing_confirmation_threshold = 2`; `BoardMonitor.check_single_board()` delegates to `CompanyBoardRegistry.reconcile_missing_jobs(..., confirm_threshold=2)`.
- **Rules enforced**:
  1. A job absent from one complete valid full snapshot remains `status='active'` with `missing_confirmation_count = 1`.
  2. A job reappearing in a subsequent complete snapshot (or upserted active) resets `missing_confirmation_count = 0` and `missing_first_seen_at = NULL`.
  3. A second independent complete snapshot showing the job absent confirms closure (`status='closed'`).
  4. Valid empty snapshots (`totalFound == 0, content == []`) on an established board follow the **same** 2-snapshot confirmation rule (`SmartRecruitersBoardAdapter` skips `not_modified=True` while any active job has `missing_confirmation_count > 0` so Poll 2 completes closure cleanly, and Poll 3 stabilizes at `not_modified=True`).
  5. Failed, interrupted, or partial scans never increment `missing_confirmation_count` and never close active jobs.
  6. Existing providers (`greenhouse`, `lever`, `ashby`, `workable`, `recruitee`) retain `missing_confirmation_threshold = 1` (immediate closure unchanged).

---

## 6. Direct-Board Routing (`direct_board_router.py`, `search_pipeline.py`)

- Implemented `probe_smartrecruiters_board(slug, client, max_detail_fetches=15)` sharing `fetch_smartrecruiters_postings_snapshot()` and `hydrate_smartrecruiters_board_jobs()`.
- Wired `"smartrecruiters"` into `probe_direct_boards()`; `SearchOrchestrator._search_direct_boards()` continues using `MONITORABLE_PROVIDERS`.
- Unknown-company `200` empty responses (`totalFound: 0`) and failed/incomplete snapshots return `[]` without registering boards; non-empty valid probes register lowercase `board_token` with authoritative `company_name`, `source_posting_url`, verified logo, and `active_job_count`.

---

## 7. Fixture Inventory

Preserved all 4 pre-existing SmartRecruiters detail fixtures (`744000155825759.json`, `744000155937924.json`, `744000155969710.json`, `job_3743990000051828.json`) and all 7 Step 44 investigation fixtures (`nearmap_postings.json`, `nearmap_744000161158698_detail.json`, `scalable_postings_p0.json`, `scalable_postings_p1.json`, `wise_744000161639339_detail.json`, `nonexistent_company_postings.json`, `nearmap_posting_404.json`), plus 2 newly captured authentic posting HTML fixtures under `tests/fixtures/real/smartrecruiters/`:

| Fixture File | Source URL | HTTP | Bytes | Purpose |
|---|---|---:|---:|---|
| `nearmap_slug_posting.html` | `https://jobs.smartrecruiters.com/Nearmap/744000161158698-enterprise-account-executive-commercial-aec-` | `200` | `124,812` | Authentic posting HTML with `c.smartrecruiters.com/sr-company-logo-prod-*` header logo + `av-www.smartrecruiters.com/sr-logo/...` platform icons |
| `wise_slug_posting.html` | `https://jobs.smartrecruiters.com/Wise/744000161639339-lead-data-analyst-wise-business-commercial-sales` | `200` | `121,757` | Authentic posting HTML verifying header logo DOM & `meta[itemprop="logo"]` across companies |

---

## 8. PR #42 Review Corrections

Two review correction passes resolved the remaining blockers identified on PR #42:

1. **SmartRecruiters Identity & Strict Numeric ID Validation (`ats_api_client.py`, `board_adapters.py`, `test_ats_client_outcomes.py`)**:
   - `_validate_smartrecruiters_listing_entry()`, `validate_smartrecruiters_page()`, and `fetch_smartrecruiters_postings_snapshot()` validate `company.identifier` case-insensitively against the requested board slug (`Wise` == `wise`), rejecting foreign-company entries atomically while falling back to the validated board slug when `company.identifier` is absent.
   - Added `_normalize_smartrecruiters_numeric_id()` in `ats_api_client.py` enforcing strict ASCII numeric `[0-9]+` posting IDs (`int` non-negative or ASCII digit `str`). `smartrecruiters_payload_to_raw()` requires the payload itself to carry a valid numeric `id` (rejecting missing, empty, whitespace-only, boolean, list, dict, UUID, alphanumeric, float/decimal, signed, scientific-notation, and non-ASCII digit IDs without silently substituting `default_job_id`).
   - Preserved legitimate UUID lookup compatibility (`SmartRecruitersClient` passing a non-numeric UUID as `default_job_id`): when the API response carries its canonical numeric `id`, conversion succeeds using that numeric ID, while an invalid payload ID is still rejected even under a UUID lookup.
   - When `default_job_id` is numeric, an exact match with the validated payload `id` is required. `_validate_smartrecruiters_candidate_url()` checks official `jobs.smartrecruiters.com` and `careers.smartrecruiters.com` URLs against `expected_company_slug` and `expected_job_id` while preserving valid external career/application URLs (`is_safe_public_https_url()`). Fixed `SmartRecruitersClient.fetch_raw_result()` to return `ExtractionOutcome.PARSE_ERROR` on invalid payloads, and updated the outdated synthetic SmartRecruiters mock in `tests/test_ats_client_outcomes.py` to include a realistic numeric `"id"` instead of relying on silent fallback.
2. **Visible Missing-Job Reconciliation Failures (`company_board_registry.py`, `board_monitor.py`)**:
   - `CompanyBoardRegistry.reconcile_missing_jobs()` now re-raises persistence exceptions when `confirm_threshold > 1` rather than returning `(0, 0)`. `BoardMonitor.check_single_board()` catches the failure, calls `record_check_failure()`, leaves `board.content_fingerprint` and job active/missing state intact, and allows the next poll to complete the 2-snapshot confirmation policy. Single-snapshot providers (`confirm_threshold <= 1`) retain their existing immediate-closure behavior.
3. **Listing Changes During Retry Backoff & Fallback Freshness (`board_adapters.py`)**:
   - `hydrate_smartrecruiters_board_jobs()` compares `listing_item_hash` before skipping unhydrated jobs for `detail_next_retry_at`, so listing changes on failed unhydrated postings schedule immediate rehydration in `changed_known` while unchanged listings still obey retry backoff.
   - `_emit_preserved_or_fallback()` refreshes stale listing-sourced metadata (`title`, `company`, `location`, `work_model`, `employment_type`, `department`, `posted_at`) from newer API listing items when unhydrated or when the listing changes, and records `listing_item_hash = item_hash` when a detail fetch is attempted and fails so retry backoff applies cleanly until another change occurs. Deferred jobs retain prior hashes and bounded budgets/fairness remain intact.
4. **Fail-Closed Playwright Database Isolation & `verify.ps1` Protection (`playwright.config.js`, `scripts/verify.ps1`, `tests/test_playwright_isolation.py`)**:
   - Hardened `playwright.config.js` so E2E isolation fails closed against hostile inherited environment variables (`PLAYWRIGHT_SQLITE_DB_PATH`, `SQLITE_DB_PATH`, `PLAYWRIGHT_SUBSCRIPTIONS_FILE`, `SUBSCRIPTIONS_FILE`, `MONITORING_ENABLED`): added segment-by-segment `lstatSync`/`readlinkSync` resolution (`resolveCanonicalPathFollowingLinks()`) with relative target expansion, `\\?\` prefix stripping, loop protection (`maxHops = 40`), and `dev`/`ino` hard-link identity checks (`sharesFilesystemIdentity()`). Relative paths, case variants (`DATA\CACHE.SQLITE`), existing/dangling symlinks, dangling/intermediate/multi-level/circular Windows directory junctions, `:memory:`, `file:` URIs, paths inside repo `data/`, and operational `subscriptions.csv` are all rejected and replaced with fresh paths under `os.tmpdir()`. Inherited `SQLITE_DB_PATH` is ignored, `process.env.PLAYWRIGHT_SQLITE_DB_PATH` and `process.env.PLAYWRIGHT_SUBSCRIPTIONS_FILE` are unconditionally overwritten with the validated temporary paths, and `webServer.env` enforces `SQLITE_DB_PATH`, `SUBSCRIPTIONS_FILE`, and `MONITORING_ENABLED="false"`.
   - Updated `scripts/verify.ps1` with `[CmdletBinding()]` and `[switch]$E2EOnly`, forced `$env:PLAYWRIGHT_REUSE_SERVER = "0"` during Playwright E2E inside an isolated temporary directory, restored existence and values of `PLAYWRIGHT_SQLITE_DB_PATH`, `PLAYWRIGHT_SUBSCRIPTIONS_FILE`, `PLAYWRIGHT_BASE_URL`, and `PLAYWRIGHT_REUSE_SERVER` in `finally` (including on failure), and removed the temporary directory afterward.
   - Replaced unsafe `str.startswith()` checks and manual `.unlink()` cleanup in `tests/test_playwright_isolation.py` with `os.path.commonpath()` (`_is_within`) and pytest-owned `tmp_path` isolation (`TMPDIR`/`TEMP`/`TMP`), plus `.pnpm` fallback `NODE_PATH` resolution when root `node_modules/@playwright/test` junctions are broken by directory rename. Added tests for existing/dangling symlinks, dangling/intermediate/multi-level/circular Windows directory junctions, `TempEvil`-style prefix collision safety, FastAPI/registry startup env routing, and child PowerShell execution of `scripts/verify.ps1 -E2EOnly`.

---

## 9. Verification Results & Operational Cache Recovery

### Verification Results (Local Agent Runs — Not GitHub Actions CI)

Note: Only `GitGuardian Security Checks` runs on GitHub PR status checks (no GitHub Actions workflow checks are configured). All suites below are local agent runs:

- **Post-final-hardening Playwright isolation check (`54bb1db3fa84cb6cf349655d528f2a64889e75a2`, fallback temp-root validation + 64-bit `BigInt` backup/sidecar hard-link protection; zero `src/` changes since `b8d4782`):**
  - `python -m pytest tests/test_playwright_isolation.py -v` -> **`25 passed, 1 skipped, 4 warnings in 64.64s`** (`test_existing_symlink_to_operational_target_rejected` skipped on unprivileged Windows due to `WinError 1314`; symlink/junction protections verified via dangling, intermediate-directory, multi-level, and circular link tests).
  - `git diff --check` -> exited **`0`**.
- **Prior full-suite verification on `b8d47820c62a5af50b5e628fdc1b195da2dbd121` (all `src/` and provider tests unchanged since):**
  - Focused Playwright Isolation & Strict Numeric ID Suite (`tests/test_playwright_isolation.py` + `TestSmartRecruitersStrictNumericIds`): **`33 passed, 39 deselected in 16.59s`**.
  - Targeted 11-File Provider, Registry, Monitor, Router & Parser Suite: **`266 passed in 37.07s`** (`58` in `tests/test_smartrecruiters_pipeline.py`).
  - Full Python Test Suite (`python -m pytest -q`): **`1033 passed, 4 warnings in 127.98s`**.
  - Work-Model Evaluation (`python scripts/eval_work_model.py`): exited **`0`** across `49` valid labelled rows (`0` regressions).
  - Full Repository Verification (`.\scripts\verify.ps1`): **`8 passed, 0 failed, 0 skipped (of 8 checks)`**.
- **Serper Spend & Settings**: Zero paid Serper requests were executed during implementation, tests, or recovery (`settings.monitoring_enabled` remains `False`).

### Operational Cache Incident, Rehearsal & Restored State (`data/cache.sqlite`)

1. **Original Incident (2026-11-16)**: Prior to Playwright isolation hardening, an E2E run allowed inherited `PLAYWRIGHT_SQLITE_DB_PATH` to reach `data/cache.sqlite` (baseline `14,143,488` bytes; `161` `monitored_jobs`, `524` `url_cache`, `13` SmartRecruiters `provisional` boards, `serper_daily_budget` latest `('2026-11-12', 2)`), and a subsequent pre-fix TDD RED test (`test_loaded_webserver_env_routes_app_startup_to_isolated_db`) unlinked `data/cache.sqlite`. All pre-existing `2026-11-13` backup files in `data/` remained completely untouched.
2. **Backup Assessment & Scenario B Selection (2026-11-17)**:
   - Preferred source: **`data/cache.sqlite.bak-pre-ashby-repair`** (`14,016,512` bytes, SHA-256 `10114b66d0b40183719f63949aa1fc018b08f0c691742e5f2ecdf670a8e9abe6`, `PRAGMA quick_check`/`integrity_check = ok`, `foreign_key_check = []`, `161` monitored jobs, `524` URL cache, `122` boards, `222` Serper cache, `8` budget rows, `54` Greenhouse repair rows, `379` Lever repair rows).
   - Superseded alternative: `data/cache.sqlite.bak-pre-greenhouse-synthetic-cleanup` (`45e28a49...`, retains 10 synthetic `company0..9` URLs and 2 extra `serper_cache` rows).
   - **Scenario B chosen**: Candidate A + additive schema migration via `CompanyBoardRegistry._ensure_db()` (adding 9 missing `monitored_jobs` columns: 6 from Steps 41/43 plus 3 from Step 45). Offline rehearsal established that Step 39 Ashby repair (`ashby_cache_repair.py`) cannot reconstruct post-`2026-11-13T12:58Z` Ashby enrichment offline (requires live Ashby HTTP calls across 36 slugs; only `4 / 40` job IDs exist in local fixtures).
3. **Failed Restoration Attempts (Preserved Forensic Evidence)**:
   - *Attempt 1 (2026-11-17T11:44)*: Failed before opening SQLite due to Windows PowerShell 5.1 native CLI double-quote stripping on `python -c $migratePy` (`SyntaxError`). Preserved staging artifact: `data/.cache.sqlite.restore-staging-a67a7e88-8b18-4675-874f-f3d9e3387d90` and safety archive `bottom-pot-restore-safety-70666fc1-4c6e-456f-ac80-543477454ed8`. Resolved by writing UTF-8-no-BOM `.py` scripts inside the safety archive directory (`& $pythonExe $scriptFile`).
   - *Attempt 2 (2026-11-17T12:09)*: Failed in `step1_migrate.py` before opening SQLite (`ModuleNotFoundError: No module named 'src'`) because executing `<Temp>\step1_migrate.py` put the Temp directory on `sys.path[0]` rather than the repository CWD (previously masked by rehearsal `PYTHONPATH`). Preserved staging artifact: `data/.cache.sqlite.restore-staging-3b2519d1-9f5c-4dcb-b646-6db8e40a8bcd` and safety archive `bottom-pot-restore-safety-a6c80e67-25cb-45ed-9cce-10291df62f84`. Resolved via explicit `BOTTOM_POT_SOURCE_ROOT` / `BOTTOM_POT_DATA_ROOT` validation + `sys.path.insert(0, str(source_root))` and verified without `PYTHONPATH` in a disposable rehearsal.
4. **Authorized Final Restoration & Independent Verification (2026-11-17, **RESTORED**)**:
   - Executed authorized Scenario B script `restore_scenario_b.ps1` (exit code `0`) promoting `data/.cache.sqlite.restore-staging-057c491e-e8ed-4b53-8680-1e83e3c6561f` to `data/cache.sqlite` (initial promoted SHA-256 `bedde91aa5dc2d95594cefdbe3c9c46006b85ce6c8fea4c3d1c1e34502deed1b`).
   - Independent post-restoration read-only checks plus application initialization (`CompanyBoardRegistry()`, `CacheStore()`, `TestClient(app).get("/health")` -> `200 ok`) and clean WAL `DELETE` checkpoint (`busy=0 log_frames=0 chk_frames=0`) verified `data/cache.sqlite` healthy and active.

#### Recovery Evidence Manifest

| Artifact / Check | Verified Path / Outcome | Size (Bytes) | Verified SHA-256 / Details |
|---|---|---:|---|
| **Final live database** | `data/cache.sqlite` | `14,016,512` | `e64b4c020e694f738aaef195bdc02a17ab86ee7275a7092b380d6bd234b1919d` (post-app init & `DELETE` checkpoint; initial post-move `bedde91aa5dc2d95594cefdbe3c9c46006b85ce6c8fea4c3d1c1e34502deed1b`) |
| **Source backup (untouched)** | `data/cache.sqlite.bak-pre-ashby-repair` | `14,016,512` | `10114b66d0b40183719f63949aa1fc018b08f0c691742e5f2ecdf670a8e9abe6` |
| **Successful safety archive** | `C:\Users\Richmond\AppData\Local\Temp\bottom-pot-restore-safety-cf6a7a96-b936-49a2-ba9e-674dec63cde9\cache.sqlite.bak-pre-ashby-repair` | `14,016,512` | `10114b66d0b40183719f63949aa1fc018b08f0c691742e5f2ecdf670a8e9abe6` |
| **Promoted staging path** | `data/.cache.sqlite.restore-staging-057c491e-e8ed-4b53-8680-1e83e3c6561f` | — | Moved to `data/cache.sqlite` (`bedde91aa5dc2d95594cefdbe3c9c46006b85ce6c8fea4c3d1c1e34502deed1b`) |
| **Recovery & verification scripts** | `C:\Users\Richmond\.gemini\antigravity-cli\brain\2dbbc6df-38f0-404d-ae17-87ba25d0142e\scratch\restore_scenario_b.ps1` (+ `test_restore_rehearsal.ps1`, `verify_post_restore.py`, `verify_post_restore_app.py`) | — | Script SHA-256 `5ac035e1f8a935a5932637e5bbb83a4ee1dc98d254619dbc5b3cd6b13b6d2d34` (`670` lines) |
| **SQLite integrity & schema** | `quick_check=ok`, `integrity_check=ok`, `foreign_key_check=[]`, `journal_mode=delete` | — | `monitored_jobs`: `31` cols (22 original + 9 added); `company_boards`: `25` cols; `7` indexes; `3` triggers; FTS5 `job_id` parity `True`; zero `-wal`/`-shm`/`-journal` sidecars |
| **Restored row counts** | Verified against immutable safety archive (`orig_rows_exact_match=True`) | — | `monitored_jobs=161` (`160` active, `1` closed), `monitored_jobs_fts=161`, `company_boards=122`, `url_cache=524`, `serper_cache=222`, `serper_daily_budget=8`, `greenhouse_repair_state=54`, `lever_repair_state=379` |
| **Operational boundaries** | `monitoring_enabled=False`, `0` Ashby repair, `0` Serper spend | — | Verified via `settings`, `serper_daily_budget` today=`0` (latest `2026-11-12`=`2`), and FastAPI `/health` `200` |
| **Preserved forensic staging files** | `data/.cache.sqlite.restore-staging-a67a7e88-8b18-4675-874f-f3d9e3387d90`, `data/.cache.sqlite.restore-staging-3b2519d1-9f5c-4dcb-b646-6db8e40a8bcd` | `14,016,512` each | Both `10114b66d0b40183719f63949aa1fc018b08f0c691742e5f2ecdf670a8e9abe6` (zero sidecars); prior safety archives (`70666fc1-...`, `a6c80e67-...`, rehearsal archives) & Candidate B backups (`45e28a49...`, `fd4c9fda...`, `e3b0c442...`) preserved untouched |

> [!WARNING]
> **Cache Freshness & Missing Ashby Updates**: Scenario B restores the `2026-11-13T12:58Z` backup with current schema. Post-`2026-11-13T12:58Z` Step 39 Ashby repair updates (`ashby_repair_state`, 15 Ashby board registrations, enriched Ashby `url_cache` rows) are absent; all `524` `url_cache` and `222` `serper_cache` entries are expired relative to `2026-11-17`; and `13` SmartRecruiters plus `9` Workable legacy boards remain `monitoring_capability='provisional'` until re-verified or promoted.

---

## 10. Known Limitations

1. **Custom corporate career domains**: Companies whose `jobs.smartrecruiters.com/{slug}` root redirects to an external custom career site still work cleanly via `api.smartrecruiters.com/v1/companies/{slug}/postings`, and posting detail pages on `jobs.smartrecruiters.com/{slug}/{id}` serve logos reliably when hosted there; companies that block `jobs.smartrecruiters.com` posting HTML leave logo enrichment `verified=False` (ADR 0001).
2. **Exact HTTP `429` burst thresholds**: SmartRecruiters returns no `X-RateLimit-*` headers; exact burst limits remain governed defensively via `throttled_get()` (`per_host_concurrency_limit=3`, `Retry-After` backoff, and circuit breaker).
3. **Post-restore Scenario B cache & board-state gaps**: `data/cache.sqlite` has been restored to Scenario B (verified schema & data), so pre-Step-39 Ashby `url_cache` gaps, expired `url_cache`/`serper_cache` TTLs, and `'provisional'` status on the `13` legacy SmartRecruiters / `9` legacy Workable boards remain until refreshed online under separate authorization.

---

## 11. Provenance

- **Branch:** `step/45-smartrecruiters-quality-pipeline`
- **PR URL:** https://github.com/richmondsogo/bottom-pot/pull/42
- **First Commit SHA:** `233f3f6fcad14558dbb0fd28b9118324e969d761` (`feat(smartrecruiters): implement Step 45 quality pipeline, monitoring, and direct routing`)
- **Latest Code Commit SHA:** `54bb1db3fa84cb6cf349655d528f2a64889e75a2` (`fix(e2e): validate fallback tmpdir and protect backup hard-link aliases`)
- **Initial Documentation Commit SHA:** `95169bb9ccd80b0fbc7156ed553158bb0b15aa1f`
- **Final Documentation Commit Policy:** Because a commit cannot self-referentially embed its own hash, the exact SHA of the final documentation reconciliation commit and remote branch `HEAD` are recorded in the PR #42 description and final verification report.
- **Merge Commit SHA:** _Pending (do not merge without explicit authorization)_
