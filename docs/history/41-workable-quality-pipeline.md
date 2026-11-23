# Step 41: Workable Quality Pipeline

**Branch:** `step/41-workable-quality-pipeline`
**Base:** `main` (`ffacf667e0ab0a50ad85c25dc50db4ed8f16839e`, Step 39 Ashby Quality Pipeline)
**Date:** 2026-11-13
**Status:** Merged to `main` via PR #38 (`7ddd864bf37d6193b171b08a7f21288b4143623b`)
**Serper Budget Spent:** `0` credits

---

## Reconciled Inventory & Verified Baseline (Step 40)

### 1. Serper URL Inventory Reconciliation (`serper_cache`)

- **`64`** distinct Workable organic URLs in `serper_cache`, reconciling to **`60`** unique genuine postings across **`54`** company slugs:
  - **`49`** initially parsed URLs
  - **`15`** `/apply` (and `/apply/`) URLs that previously failed parsing, of which **`4`** duplicated already-parsed job IDs and **`11`** were net-new postings (`49 + 11 = 60` unique genuine postings).

### 2. Operational Cache Baseline (`data/cache.sqlite` Before Step 41)

Across **`30`** genuine Workable `url_cache` rows across **`28`** unique company slugs (excluding `1` synthetic `example.com` row), **`9`** Workable `company_boards` rows (`monitoring_capability='provisional'`, `0` checked, `0` verified logos), and **`0`** `monitored_jobs`:

- Clean canonical URLs: **`13 / 30`** (`16 / 30` trailing slashes, `1 / 30` tracking query)
- Chrome-free descriptions (no `## Apply` / `Powered by Workable`): **`0 / 30`** (`30 / 30` leaked Markdown chrome)
- `requirements`: **`0 / 30`**
- `eligibility`: **`0 / 30`**
- `raw_location`: **`0 / 30`**
- `salary` present: **`4 / 30`** (`3 / 30` with `currency`, `0 / 30` with `period`)
- `employment_type`: **`26 / 30`**
- `company_logo_verified`: **`0 / 30`**
- `apply_url` distinct from canonical `source_url`: **`0 / 30`** (`30 / 30` equal to `source_url`)

---

## Observed Before / After Benchmark (`data/cache.sqlite` Operational Cache)

Before running live zero-Serper repair, a read-only backup of `data/cache.sqlite` was saved outside the repository (`cache.sqlite.bak-pre-workable-repair`).

### Zero-Serper Repair Execution (`python -m src.project_files.workable_cache_repair`)

| Metric | Dry Run (`--dry-run`) | Live Pass 1 | Live Pass 2 (Idempotency) |
|---|---:|---:|---:|
| `total_urls` | `30` | `30` | `30` |
| `unique_slugs` | `28` | `28` | `0` |
| `repaired_from_v2_api` | `28` | `28` | `0` |
| `canonicalized_urls` (alias re-keyed) | `16` | `16` | `0` |
| `boards_reconciled` | `9` | `9` | `0` |
| `boards_promoted` (`provisional -> supported`) | `0` | `9` | `0` |
| `boards_identity_enriched` | `23` | `23` | `0` |
| `expired_or_unavailable` (HTTP 404 preserved) | `2` | `2` | `0` |
| `skipped_already_repaired` | `0` | `0` | `30` |
| `skipped_synthetic` | `0` | `0` | `0` |
| `transient_errors` | `0` | `0` | `0` |
| `serper_calls_used` | `0` | `0` | `0` |

### Field Coverage Across `30` Genuine `url_cache` Postings & `company_boards`

| Field | Before Step 41 | After Step 41 Live Repair |
|---|---:|---:|
| Chrome-free `description` (`description_ok=True`) | `0 / 30` (`30` with chrome) | **`28 / 30`** (`28 / 28` live jobs; `2` historical 404 rows preserved) |
| `requirements` | `0 / 30` | **`25 / 30`** (`25 / 28` live jobs) |
| `eligibility` | `0 / 30` | **`28 / 30`** (`28 / 28` live jobs) |
| `raw_location` preserved (where multi-location/distinct) | `0 / 30` | **`6 / 30`** |
| `salary` present | `4 / 30` | **`7 / 30`** |
| `salary.currency` present | `3 / 30` (missing INR on `learnrush`) | **`7 / 30`** (`100%` of extracted salaries incl. `INR` & `JOD`) |
| `salary.period` present | `0 / 30` | **`6 / 30`** |
| `company_logo_url` & `company_logo_verified` | `0 / 30` | **`21 / 30`** (`7` accounts return `logo: null`) |
| Distinct `/apply` `apply_url` (`apply_url != source_url`) | `0 / 30` | **`28 / 30`** (`28 / 28` live jobs) |
| Canonical URL keys (no trailing `/` or query params) | `13 / 30` | **`29 / 30`** (`28 / 28` live jobs; `1` historical 404 row preserved) |
| `company_boards` (Workable) | `9` (`0` `supported`, `0` checked, `0` logos) | **`29`** (`29` `supported`, `23` verified logos) |
| `workable_repair_state` | — | **`46`** state rows (`44` `repaired` incl. 14 aliases, `2` `unavailable_404`) |

---

## Key Architectural & Quality Changes Implemented

1. **URL Parsing, Canonicalization & Board-Root Registration (`src/project_files/ats_url_parser.py`, `url_normalizer.py`, `search_pipeline.py`)**:
   - Extended `_WORKABLE_SUBDOMAIN` and `_WORKABLE_APPLY` to accept optional `/apply` suffixes (`apply.workable.com/{slug}/j/{id}/apply` and `{slug}.workable.com/jobs/{id}/apply`), guarded with `is_valid_board_slug`, `_WORKABLE_NON_BOARD_PATHS`, and `_WORKABLE_RESERVED_SUBDOMAINS`.
   - Added `parse_workable_board_root_url` and wired it into `_enrich_ats_item` so board-root URLs (`apply.workable.com/{slug}`, `{slug}.workable.com`) register Workable candidates in `company_board_registry`.
   - Registered `"workable"` in `_PROVIDER_RULES` and canonicalized `{slug}.workable.com/jobs/{id}`, `http://`, trailing `/`, and `/apply` onto `https://apply.workable.com/{slug}/j/{id}`.

2. **Workable `api/v2` Primary Client & Shared Conversion (`src/project_files/ats_api_client.py`)**:
   - Added single shared deterministic converter `workable_payload_to_raw(...)` plus `workable_widget_job_to_raw(...)` and clean `workable_markdown_to_raw(...)` fallback (stripping `# Title`, metadata blockquote, `## Apply`, and `Powered by Workable` while preserving authentic description sections, requirements, benefits, and `/apply` CTA URL).
   - Upgraded `WorkableClient` to fetch `GET https://apply.workable.com/api/v2/accounts/{slug}/jobs/{job_id}` primarily, preserving structured primary/secondary locations (skipping `hidden: true` entries and guarding against top-level `state: "published"` false US-state collisions), `workplace` / `remote`, `department`, `employment_type`, `published_on`, authentic HTML/text sections, and `https://apply.workable.com/{slug}/j/{id}/apply`.

3. **Salary, Currency, Eligibility, Requirements & Logos (`src/project_files/salary_parser.py`, `eligibility_extractor.py`, `job_extraction_service.py`, `logo_extractor.py`)**:
   - Extended `ISO_4217_CURRENCIES` with `"JOD"`, `"KWD"`, `"BHD"`, `"OMR"`, `"QAR"` and `_CURR_SYMBOLS` / `_resolve_currency` with `₹ -> INR`, plus Workable structured `salary_from`/`salary_to`/`salary_currency_iso_code`/`salary_frequency`, bulleted explicit currency+period fallback (`- $30/hr`), and Markdown-link stripping in salary extraction.
   - Added Jordan/Middle East/African country aliases (`Jordan`/`JO`, `Japan`/`JP`, `Kenya`/`KE`, `South Africa`/`ZA`, etc.) and structured `raw_fields["location"]` country fallback in `eligibility_extractor.py`; opted `"workable"` into requirements and eligibility extraction in `JobExtractionService`.
   - Rejected Workable default `open_graph_logo` / `facebook-preview` templates in `_REJECTED_LOGO_PATTERNS`, implemented `_extract_workable_logo`, and added 7-day cached/coalesced `enrich_workable_board_identity` (`GET /api/v1/accounts/{slug}`).

4. **Independent Monitoring, Direct Board Routing & Zero-Serper Repair (`src/project_files/board_adapters.py`, `board_monitor.py`, `company_board_registry.py`, `direct_board_router.py`, `workable_cache_repair.py`)**:
   - Promoted `"workable"` to `MONITORABLE_PROVIDERS`; implemented `WorkableBoardAdapter` (`GET /api/v1/widget/accounts/{slug}` + SHA-256 fingerprint diff + bounded rotating `api/v2` detail revalidation respecting `detail_revalidate_ttl_seconds` & `max_revalidations_per_poll` + `preserve_last_checked_at` for unrotated active jobs + transient error preservation).
   - Added `probe_workable_board` in `direct_board_router.py` sharing `hydrate_workable_board_jobs`.
   - Implemented `src/project_files/workable_cache_repair.py` with `--dry-run`, `--force`, `v41` checkpointing, board promotion/reconciliation, conservative alias cleanup, and 404 historical preservation.

---

## Verification Results

All checks passed after the final code, fixture, and documentation edits:

- **Targeted Workable & Monitoring Suite (`pytest tests/test_workable_pipeline.py tests/test_board_monitor.py tests/test_direct_board_router.py tests/test_company_board_registry.py tests/test_platform_reconciliation.py -q`)**: Passed cleanly (17 tests in `tests/test_workable_pipeline.py` covering URL parsing/normalization, `api/v2` + `.md` fallback, JOD/INR/USD salary parsing, requirements, eligibility, verified logos, monitoring lifecycle & rotating TTL refresh, direct board routing, and cache repair).
- **Real Fixture Corpus (`tests/fixtures/real/workable/`)**: Captured 18 real Workable API/HTML fixtures across 5 verified boards (`treq`, `verneek`, `mercari`, `learnrush`, `99brightminds`) plus `serper_urls_78.json`; left pre-existing `job_D94DBAF102.md` intact; updated `tests/test_real_api_fixtures.py` for Step 41's expected extraction improvements on `workable_D94DBAF102.json`.
- **Full Project Verification Suite (`.\scripts\verify.ps1`)**: **`8 passed, 0 failed, 0 skipped (of 8 checks)`**.
- **Full Python Test Suite (`python -m pytest -q`)**: **`928 passed, 4 warnings in 75.09s`**.
- **Frontend Unit Tests & Build**: `vitest` **`17 test files, 113 passed`**; `tsc -b && vite build` clean.
- **Playwright E2E Suite (`npx playwright test --reporter=line`)**: **`43 passed (1.4m)`**, including `Step 41: Workable square logos, JOD/INR/USD salaries, work models, eligibility, /apply links, and 5-viewport responsiveness` across `1920x1080`, `1440x900`, `1024x768`, `768x1024`, and `390x844` with `0px` square `CompanyMark` geometry, 0 horizontal overflow, 0 console/page errors, and 0 critical/serious Axe WCAG violations.
- **Work Model Evaluation (`python scripts/eval_work_model.py`)**: Ran cleanly across `49` valid labelled rows with zero regressions.

---

## Provenance

- **Feature Branch**: `step/41-workable-quality-pipeline`
- **Base Commit (`main`)**: `ffacf667e0ab0a50ad85c25dc50db4ed8f16839e`
- **Pull Request**: `https://github.com/richmondsogo/bottom-pot/pull/38` (merged)
- **Merge Commit (`main`)**: `7ddd864bf37d6193b171b08a7f21288b4143623b`
- **First Implementation Commit**: `6947d14c6d85172a0326f973dc98ab9382c44da1` (`feat(step-41): implement Workable quality pipeline, api/v2 ingestion, monitoring, and zero-Serper cache repair`)

---

## Follow-up: Workable Monitoring Correctness & Retry Accounting

Addressed three monitoring reliability findings on `step/41-workable-quality-pipeline` without modifying the Workable extraction pipeline structure or other providers:

### Corrections Implemented

1. **Per-Job Widget Change Detection (`src/project_files/board_adapters.py`, `company_board_registry.py`)**:
   - Expanded `_workable_widget_differs_from_listing` to compare normalized values across all meaningful widget fields: `title`, `published_on`, `employment_type`, `department`, `telecommuting` / `work_model` (preserving real `telecommuting: false` compatibility with `api/v2` `workplace: "hybrid"`), `city`, `state` / `region`, `country`, and `locations` (including multi-location arrays while ignoring `hidden: true` entries).
   - Preserved the missing-field rule: empty or omitted widget fields are never treated as removals of known listing metadata.
   - Persisted `widget_location_signature` alongside monitored jobs so state/region-only changes (e.g. `Oregon -> Maine` with identical city and country) trigger immediate `api/v2` rehydration even when canonical `JobListing.location` omits region strings. Unchanged metadata triggers zero unnecessary detail requests.

2. **Durable Detail-Refresh Accounting & Bounded Retry/Backoff (`src/project_files/board_adapters.py`, `board_monitor.py`, `company_board_registry.py`)**:
   - Added SQLite-persisted per-job detail tracking (`MonitoredJobDetailState` via additive `monitored_jobs` columns: `detail_status`, `detail_last_hydrated_at`, `detail_retry_count`, `detail_next_retry_at`, `detail_last_error`, `widget_location_signature`) surviving application restarts.
   - Separated outcomes into `hydrated`, `invalid_detail` (HTTP 200 with error/incomplete payload), `transient_error` (429/5xx/network/timeout), `detail_404`, and `widget_fallback`.
   - Stopped adding fallback/error/404 job IDs to `refreshed_job_ids`, fixed `upsert_monitored_job` to preserve `0.0` `last_checked_at` on fallback inserts and updates when `preserve_last_checked_at=True`, and preserved existing richer cached listings whenever `api/v2` fails.
   - Added bounded retry/backoff schedules capped by `detail_revalidate_ttl_seconds`: `5m -> 15m -> 30m -> 1h -> 2h -> 6h` for `transient_error` / `invalid_detail`, `1h -> 2h -> 4h -> 6h` for `detail_404`, and immediate eligibility for deferred `widget_fallback`, prioritized and bounded by `max_revalidations_per_poll=5`.

3. **Authoritative Widget Population & 404 Non-Closure (`src/project_files/board_adapters.py`)**:
   - Stopped skipping jobs still present in a valid HTTP 200 Workable widget feed when `api/v2` returns 404. Existing monitored jobs remain `active` with their preserved rich cached listing; new jobs with no rich cache use conservative widget fallback; both enter bounded `detail_404` retry backoff without false closure or tight-loop hammering.
   - Jobs absent from a valid HTTP 200 widget response still close cleanly via `BoardMonitor` / `mark_missing_jobs_closed()`, while failed widget responses never close jobs.

### Follow-up Verification Results

Run after all implementation edits (implementation commit `22ccdef13555ff9874e3bbd52072ae8a6d272770`):

- **Targeted Workable & Monitoring Suite (`pytest tests/test_workable_pipeline.py tests/test_board_monitor.py tests/test_direct_board_router.py tests/test_company_board_registry.py tests/test_platform_reconciliation.py -q`)**: **`48 passed, 4 warnings in 7.19s`** (includes 6 new regression tests in `tests/test_workable_pipeline.py`: `23` total in that file).
- **Full Python Test Suite (`pytest -q`)**: **`934 passed, 4 warnings in 126.29s (0:02:06)`** (pre-existing FastAPI `on_event` and SlowAPI `asyncio.iscoroutinefunction` deprecation warnings only).
- **Frontend Unit Tests (`npm --prefix frontend run test`)**: **`17 test files passed, 113 tests passed in 11.99s`**.
- **Frontend Build (`npm --prefix frontend run build`)**: `tsc -b && vite build` clean in `2.37s` (existing Rollup/Vite `> 500 kB` chunk size notice on `index-BQTiXdbO.js`).
- **Playwright E2E (`npx playwright test --reporter=list`)**: **`43 passed (2.1m)`**.
- **Full Repository Verification Script (`.\scripts\verify.ps1`)**: **`8 passed, 0 failed, 0 skipped (of 8 checks)`**.

### Follow-up Provenance

- **Follow-up Implementation Commit**: `22ccdef13555ff9874e3bbd52072ae8a6d272770` (`fix(workable): tighten monitoring diff detection, detail retry accounting, and 404 lifecycle`)

---

## Final Follow-up: Shared Workable Host Rate Limits & Resilience Integration

Integrated the shared `resilience_manager` (`src/project_files/http_resilience.py`) across all Workable independent monitoring and direct-board request paths so concurrent `apply.workable.com` requests respect `settings.per_host_concurrency_limit` (`3`), `settings.global_concurrency_limit` (`20`), circuit-breaker protection, and `Retry-After` host backoff.

### Corrections Implemented

1. **Shared `throttled_get()` Primitive (`src/project_files/http_resilience.py`)**:
   - Added `throttled_get(client, url, *, headers=None, timeout=10.0, follow_redirects=False)` wrapping single `client.get()` calls in `resilience_manager.throttle(url)` and recording explicit outcomes (`record_rate_limit(host, retry_after)` on HTTP `429`, `record_failure(host)` on HTTP `>= 500` or network/timeout exceptions, `record_success(host)` on HTTP `< 500`).

2. **Workable Widget, Detail & Direct-Probe Paths (`src/project_files/board_adapters.py`, `src/project_files/direct_board_router.py`)**:
   - Routed `WorkableBoardAdapter.check_board()` (`/api/v1/widget/accounts/{slug}`), `hydrate_workable_board_jobs()` (`/api/v2/accounts/{slug}/jobs/{shortcode}`), and `probe_workable_board()` (`/api/v1/widget/accounts/{slug}` + shared hydration) through `throttled_get()` without outer nested `throttle()` locks.
   - Kept the local per-board semaphore (`asyncio.Semaphore(5)`) strictly inside the detail loop while all concurrent board checks and direct probes share the `apply.workable.com` host semaphore (`per_host_concurrency_limit=3`).
   - Handled `CircuitBreakerOpenError` and `HostRateLimitedError` cleanly as transient failures (`circuit_breaker_open` / `host_rate_limited`), preserving active cached listings and never falsely closing jobs.
   - Left `GreenhouseBoardAdapter`, `LeverBoardAdapter`, `AshbyBoardAdapter`, and search pipeline request-throttling unchanged.

3. **Deadlock-Safe Account Identity Enrichment (`src/project_files/ats_api_client.py`)**:
   - Added `use_resilience: bool = False` to `enrich_workable_board_identity()` (`GET /api/v1/accounts/{slug}`) and included `use_resilience` in `_WORKABLE_IDENTITY_INFLIGHT` coalescing keys.
   - Independent monitoring and direct-board probing (`hydrate_workable_board_jobs()`) pass `use_resilience=True` (throttled and outcome-accounted under `apply.workable.com`); `WorkableClient` inside search pipeline keeps `use_resilience=False` because search pipeline items already hold `resilience_manager.throttle(item_url)`, preventing nested host-semaphore deadlocks.

### Final Follow-up Verification Results

Run after all implementation edits (implementation commit `19b77a4c1bf2dc626d4bc97d55be830902e531c4`):

- **Targeted Workable, Monitoring & Resilience Suite (`pytest tests/test_workable_pipeline.py tests/test_board_monitor.py tests/test_direct_board_router.py tests/test_company_board_registry.py tests/test_platform_reconciliation.py tests/test_bounded_retry.py -q`)**: **`63 passed, 4 warnings in 12.05s`** (includes 4 new resilience regression tests in `tests/test_workable_pipeline.py`: shared host cap `<= 3` across 5 concurrent boards + direct probe, `429 Retry-After` host backoff on widget/detail/account endpoints, open circuit breaker & 5xx/timeout/connect-error non-closure, 404 healthy-host accounting + non-closure, and non-deadlocking `WorkableClient` identity enrichment).
- **Full Python Test Suite (`pytest -q`)**: **`938 passed, 4 warnings in 143.27s (0:02:23)`** (pre-existing SlowAPI `asyncio.iscoroutinefunction` and FastAPI `on_event` deprecation warnings only).
- **Frontend Unit Tests (`npm --prefix frontend run test`)**: **`17 test files passed, 113 tests passed in 20.70s`**.
- **Frontend Build (`npm --prefix frontend run build`)**: `tsc -b && vite build` clean (`2613 modules transformed`, built in `2.33s`; pre-existing `> 500 kB` chunk notice on `index-BQTiXdbO.js`).
- **Playwright E2E (`npx playwright test --reporter=list`)**: **`43 passed (2.6m)`**.
- **Full Repository Verification Script (`.\scripts\verify.ps1`)**: **`8 passed, 0 failed, 0 skipped (of 8 checks)`**.

### Final Follow-up Provenance

- **Final Follow-up Implementation Commit**: `19b77a4c1bf2dc626d4bc97d55be830902e531c4` (`fix(workable): route monitoring and direct probing through shared host resilience limits`)

---

## Resilience Race-Condition Follow-up: Post-Semaphore Recheck & Concurrent 429 Preservation

Fixed two concurrency race conditions in `ResilienceManager` (`src/project_files/http_resilience.py`) without altering provider behavior, the search pipeline's outer throttle, or cache state.

### Fixes Implemented (`src/project_files/http_resilience.py`)

1. **Post-Semaphore Host Readiness Recheck (`_ensure_host_ready()`, `throttle()`, `fetch_page_with_cap()`)**:
   - Extracted `_ensure_host_ready(host)` checking both circuit-breaker openness (`is_host_open(host)`) and active 429 `Retry-After` deadlines (`time.time() < until`).
   - `ResilienceManager.throttle()` now checks `_ensure_host_ready(host)` both before acquiring `global_sem` / `host_sem` and again immediately inside both `async with` blocks before yielding control. Waiters queued behind the semaphore abort cleanly with `HostRateLimitedError` or `CircuitBreakerOpenError` without reaching the HTTP transport if an in-flight response trips the breaker or records a 429, and Python's `async with` context managers release both semaphores on exception exit.
   - Simplified `fetch_page_with_cap()` to enter `resilience_manager.throttle(url)` directly so streamed fetches automatically inherit the post-semaphore recheck.

2. **Preserve Active 429 Backoff Across Concurrent 200s (`record_success()`, `record_rate_limit()`, `is_host_rate_limited()`)**:
   - `record_success(host)` no longer erases an active future `_host_rate_limited_until[host]` or `_host_rate_limit_backoff[host]`; it clears rate-limit state and resets exponential backoff only when no active deadline remains or `now >= until`.
   - `record_rate_limit(host, retry_after)` uses `max(existing_until, new_until)` so concurrent 429s never shorten an already-longer deadline, and expired deadline cleanup in `is_host_rate_limited()` / `_ensure_host_ready()` pops only `_host_rate_limited_until` while preserving `_host_rate_limit_backoff` until successful post-expiry recovery so consecutive 429s continue exponential doubling.

3. **Deterministic Async-Barrier Regression Tests (`tests/test_bounded_retry.py`, `tests/test_phase5_cost_and_robustness.py`)**:
   - Added `test_throttle_queued_waiters_recheck_429_and_concurrent_200_preserves_backoff`, `test_throttle_queued_waiters_recheck_circuit_breaker_after_semaphore`, and `test_rate_limit_exponential_backoff_doubles_across_expiry_and_resets_after_success` in `tests/test_bounded_retry.py` using `asyncio.Event` barriers and mocked `time.time()`.
   - Updated `test_per_host_429_backoff_and_reset` in `tests/test_phase5_cost_and_robustness.py` to assert active 429 deadline preservation on concurrent `record_success()` and backoff reset after deadline expiry recovery.

### Resilience Follow-up Verification Results

Run after final code/test edits (`d7ef0dbe55310d67749ed682cb05dedc7e90ddb4`):

- **Focused Resilience & Workable Suite (`pytest tests/test_bounded_retry.py tests/test_phase5_cost_and_robustness.py tests/test_workable_pipeline.py tests/test_board_monitor.py tests/test_direct_board_router.py tests/test_company_board_registry.py tests/test_platform_reconciliation.py -q`)**: **`88 passed, 4 warnings in 20.21s`**.
- **Full Python Test Suite (`pytest -q`)**: **`941 passed, 4 warnings in 116.31s (0:01:56)`** (pre-existing SlowAPI `asyncio.iscoroutinefunction` and FastAPI `on_event` deprecation warnings only).
- **Frontend Unit Tests (`npm --prefix frontend run test`)**: **`17 test files passed, 113 tests passed in 15.18s`**.
- **Frontend Build (`npm --prefix frontend run build`)**: `tsc -b && vite build` clean (`2613 modules transformed`, built in `2.31s`; pre-existing `> 500 kB` chunk notice on `index-BQTiXdbO.js`).
- **Playwright E2E (`npx playwright test --reporter=list`)**: **`43 passed (1.9m)`**.
- **Full Repository Verification Script (`.\scripts\verify.ps1`)**: **`8 passed, 0 failed, 0 skipped (of 8 checks)`**.

### Resilience Follow-up Provenance

- **Resilience Follow-up Implementation Commit**: `d7ef0dbe55310d67749ed682cb05dedc7e90ddb4` (`fix(resilience): recheck host readiness after semaphore and preserve active 429 backoff`)
