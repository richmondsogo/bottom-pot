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

## 8. Verification Results & Cache Integrity

All checks passed after the final code and test edits:

- **Targeted SmartRecruiters, Workable, Recruitee, Registry, Router & Parser Suite**:
  `python -m pytest tests/test_smartrecruiters_pipeline.py tests/test_recruitee_pipeline.py tests/test_workable_pipeline.py tests/test_board_monitor.py tests/test_company_board_registry.py tests/test_direct_board_router.py tests/test_direct_board_routing_integration.py tests/test_board_discovery_and_pipeline.py tests/test_real_api_fixtures.py tests/test_ats_url_parser.py tests/test_url_normalizer.py -q` -> **`238 passed, 4 warnings in 38.26s`** (`30` tests in `tests/test_smartrecruiters_pipeline.py`).
- **Full Python Test Suite (`python -m pytest -q`)**: **`991 passed, 4 warnings in 107.10s`** (pre-existing SlowAPI and FastAPI `on_event` deprecation warnings only).
- **Work-Model Evaluation (`python scripts/eval_work_model.py`)**: Exited `0` across `49` valid labelled rows (`0` regressions).
- **Full Repository Verification (`.\scripts\verify.ps1`)**: **`8 passed, 0 failed, 0 skipped (of 8 checks)`** (Git, Secrets, CSS Cascade Lint, `oxlint`, `vitest`, `tsc` + `vite build`, `pytest`, Playwright E2E).
- **`git diff --check`**: Exited `0` with zero whitespace errors.
- **Serper Spend & Settings**: **`0` Serper credits spent** (`serper_daily_budget` latest row remains `('2026-11-12', 2)`); `settings.monitoring_enabled` remains `False`.
- **Operational Cache Integrity (`data/cache.sqlite`)**: File size remained **`14,143,488` bytes** with zero row mutations (`monitored_jobs`: `161`, `url_cache`: `524`, SmartRecruiters `company_boards`: `13` `provisional`). Note: during `.\scripts\verify.ps1`, the Playwright E2E server startup invoked `CompanyBoardRegistry._ensure_db()` against the default `data/cache.sqlite` path, applying the 3 additive `ALTER TABLE monitored_jobs ADD COLUMN` schema columns (`listing_item_hash`, `missing_confirmation_count`, `missing_first_seen_at`) and updating `LastWriteTimeUtc` to `2026-11-16T10:43:09Z` without altering any row data or byte length.

---

## 9. Known Limitations

1. **Custom corporate career domains**: Companies whose `jobs.smartrecruiters.com/{slug}` root redirects to an external custom career site still work cleanly via `api.smartrecruiters.com/v1/companies/{slug}/postings`, and posting detail pages on `jobs.smartrecruiters.com/{slug}/{id}` serve logos reliably when hosted there; companies that block `jobs.smartrecruiters.com` posting HTML leave logo enrichment `verified=False` (ADR 0001).
2. **Exact HTTP `429` burst thresholds**: SmartRecruiters returns no `X-RateLimit-*` headers; exact burst limits remain governed defensively via `throttled_get()` (`per_host_concurrency_limit=3`, `Retry-After` backoff, and circuit breaker).
3. **Existing `data/cache.sqlite` historical SmartRecruiters rows**: Per Step 45 exclusions, no cache repair or board promotion was run against `data/cache.sqlite`; existing provisional SmartRecruiters rows remain untouched until an authorized operational repair/migration step.

---

## 10. Provenance

- **Branch:** `step/45-smartrecruiters-quality-pipeline`
- **PR URL:** https://github.com/richmondsogo/bottom-pot/pull/42
- **First Commit SHA:** `233f3f6fcad14558dbb0fd28b9118324e969d761` (`feat(smartrecruiters): implement Step 45 quality pipeline, monitoring, and direct routing`)
- **Last Implementation Commit SHA:** `233f3f6fcad14558dbb0fd28b9118324e969d761`
- **Initial Documentation Commit SHA:** `95169bb9ccd80b0fbc7156ed553158bb0b15aa1f`
- **Final Documentation Commit SHA:** Recorded in follow-up provenance commit (`HEAD` after push)
- **Merge Commit SHA:** _Pending (do not merge without explicit authorization)_
