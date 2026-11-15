# Step 43: Recruitee Quality Pipeline

**Date:** 2026-11-15  
**Branch:** `step/43-recruitee-quality-pipeline`  
**Base commit (`main`):** `794544ece0cc770098ae5b8a61f744d22617e969`  
**Prerequisite Investigation:** Step 42 (`docs/steps/42-recruitee-monitoring-investigation.md`, PR #39)  
**Serper credits consumed:** `0` (`data/cache.sqlite` unmodified)  

---

## 1. Objective & Summary

Promoted Recruitee from a provisional URL-only integration with broken slug parsing to a first-class, deterministically extracted, independently monitorable, and directly routable ATS provider across the Bottom Pot pipeline:

1. **URL Ingestion, Board-Root Registration & Normalization (Phase A)**:
   - Fixed `_RECRUITEE` in `src/project_files/ats_url_parser.py` to support slug-only `/o/{offer-slug}` URLs, `/c/new` application suffixes, trailing slashes, and legacy numeric-prefixed `/o/{id}-{slug}` paths while rejecting reserved subdomains (`www`, `api`, `app`, `careers`, `jobs`, `status`, `assets`, etc.), malformed paths, and custom domains.
   - Added `parse_recruitee_board_root_url(...)` and wired Recruitee board-root candidate registration into `SearchOrchestrator._enrich_ats_item` in `src/project_files/search_pipeline.py`.
   - Added `"recruitee"` to `_PROVIDER_RULES`, `normalize_job_url` (preserving `/c/new` on `careers_apply_url`), `canonicalize_recruitee_posting_url`, and `build_url_match_key` in `src/project_files/url_normalizer.py`.

2. **Single Shared Deterministic Converter & Extraction (Phase B)**:
   - Implemented `recruitee_payload_to_raw(...)` in `src/project_files/ats_api_client.py` supporting both single-offer `{"offer": {...}}` payloads and board-listing items from `{"offers": [...]}`.
   - Refactored `RecruiteeClient` to share `recruitee_payload_to_raw(...)`, fix its docstring to `GET https://{slug}.recruitee.com/api/offers/{job_id_or_slug}`, use authoritative `company_name`, `careers_url`, `careers_apply_url` (`/c/new`), `employment_type_code`, HTML `requirements`, structured `salary`, and structured location (`city`/`state_name`/`country`/`locations[]`, skipping `"Fully Remote"` city sentinel).
   - Updated `parse_datetime` in `src/project_files/field_normalizer.py` to parse `"%Y-%m-%d %H:%M:%S UTC"` timestamps cleanly so `published_at` is authoritative in UTC (`created_at` is preserved in `raw_fields` and never substituted for `published_at`).
   - Enforced strict ADR 0001/0002 workplace boolean classification (`remote`, `hybrid`, `on_site`): single `True` -> `api_enum`; conflicting `>= 2` `True` flags (observed in real `dransay` offer `2650971`) -> `unknown` (`None`) with raw evidence preserved and fallback text guessing disabled in `src/project_files/job_extraction_service.py`; all-`False`/missing -> `None`.
   - Opted `"recruitee"` into requirements & eligibility extraction in `src/project_files/job_extraction_service.py` (including Recruitee `requirements` HTML and `locations[].note` residency evidence).
   - Ensured numeric `offer["id"]` resolves consistently to `recruitee:{company_slug}:{numeric_offer_id}` across slug-discovered search URLs, board monitoring, and direct board probing.

3. **Verified Logo Enrichment (Phase C)**:
   - Added `_extract_recruitee_logo` and opted `"recruitee"` into `extract_company_logo_for_provider` in `src/project_files/logo_extractor.py`, accepting `img.custom-css-style-navigation-logo-image` on `careers.recruiteecdn.com` and rejecting `og:image` `w_1920` hero banners and generic Recruitee assets.
   - Implemented bounded, 7-day SQLite-cached, single-flight coalesced `enrich_recruitee_board_identity(...)` in `src/project_files/ats_api_client.py` with at most one bounded fallback offer-page lookup on JS-redirect roots.

4. **Independent Monitoring, Bounded Large-Response Streaming & Direct Routing (Phases D–E)**:
   - Added configurable `recruitee_board_max_response_bytes = 16 * 1024 * 1024` (16 MiB) in `src/config.py` and `throttled_stream_bytes` / `ResponseTooLargeError` in `src/project_files/http_resilience.py` so legitimate >3 MB Recruitee boards (e.g., real 5.97 MB `tether` payload) stream cleanly under `resilience_manager` while oversized payloads fail before parsing partial JSON.
   - Added `hydrate_recruitee_offers`, `_recruitee_job_content_hash`, and `RecruiteeBoardAdapter` to `src/project_files/board_adapters.py` and registered `"recruitee"` in `BOARD_ADAPTERS`.
   - Promoted `"recruitee"` from `PROVISIONAL_PROVIDERS` to `MONITORABLE_PROVIDERS` in `src/project_files/company_board_registry.py`.
   - Implemented `probe_recruitee_board` and wired `"recruitee"` into `probe_direct_boards()` in `src/project_files/direct_board_router.py`.

---

## 2. Captured Real Fixtures (Zero Serper Credits, 5 Public GETs)

- `tests/fixtures/real/recruitee/miaplaza_offers.json` (7 offers, 295,955 bytes)
- `tests/fixtures/real/recruitee/dransay_offers.json` (4 offers including dual `remote=True & hybrid=True` offer `2650971`, 64,811 bytes)
- `tests/fixtures/real/recruitee/tether_offers.json.gz` (234 offers, 5,972,660 bytes uncompressed)
- `tests/fixtures/real/recruitee/miaplaza_board.html` (verified nav logo HTML + `og:image` banner)
- `tests/fixtures/real/recruitee/tether_board_redirect.html.gz` (real JS-redirect stub HTML without nav logo)

---

## 3. Verification Results

- `pytest tests/test_ats_url_parser.py tests/test_url_normalizer.py -q`: `117 passed`
- `pytest tests/test_real_api_fixtures.py tests/test_ats_client_outcomes.py tests/test_salary_parser.py -q`: `79 passed` (with documented intentional Step 43 diffs on `recruitee_2774909.json`)
- `pytest tests/test_company_board_registry.py tests/test_board_monitor.py tests/test_direct_board_router.py tests/test_direct_board_routing_integration.py tests/test_board_discovery_and_pipeline.py -q`: `26 passed`
- `pytest tests/test_recruitee_pipeline.py -q`: `17 passed`
- `python scripts/eval_work_model.py`: completed cleanly (`0` regressions on labelled dataset)
- `.\scripts\verify.ps1`: **8 passed, 0 failed, 0 skipped** (Git, Secrets, CSS Cascade Lint, oxlint, vitest, tsc + vite build, pytest, Playwright E2E)

---

## 4. Provenance

- **Branch:** `step/43-recruitee-quality-pipeline`
- **PR URL:** https://github.com/richmondsogo/bottom-pot/pull/40
- **First Commit SHA:** `c21e24e309d5746a08e32edff52c88200eff61e6`
- **Last Commit SHA (before corrective commit):** `e97e3bd09b94712f45d24a151fe5941b9ea5a302` (`docs(steps): record Step 43 commit SHA and PR URL`)
- **Merge Commit SHA:** _Not merged per MERGE_POLICY_

---

## 5. Corrective Review Pass

### Fixes Implemented

1. **Snapshot Validation Against False Closures (`src/project_files/board_adapters.py`)**:
   - Added `_validate_recruitee_offer_record()` and snapshot-level active-offer hydration parity checks in `RecruiteeBoardAdapter.check_board()`.
   - Genuinely empty `{"offers": []}` and recognized inactive offers (`status != "published"`, non-empty string) remain valid; any non-dict offer entry, malformed status, or active offer missing required identity (`id`/`slug`) or title (`title`/`position`) now fails with `BoardCheckResult(success=False, ...)` so `BoardMonitor` preserves active monitored jobs instead of closing them.

2. **Full-Payload Recruitee Content Fingerprint (`src/project_files/board_adapters.py`)**:
   - Removed the partial `_RECRUITEE_HASH_FIELDS` whitelist and updated `_recruitee_job_content_hash()` to serialize the complete sorted `offer` payload and return the full 64-character SHA-256 hex digest.
   - No payload fields are excluded because Recruitee's public `/api/offers/` objects contain no ephemeral per-request tokens. Changes to fallback fields (`description_html`, `intro`, `employment_type`, `employmentType`, `workplace_type`, `workplaceType`, `position`, `company`, `companyName`) now invalidate the board fingerprint cleanly.

3. **Streaming Outcome Accounting (`src/project_files/http_resilience.py`)**:
   - Moved `resilience_manager.record_success(host)` in `throttled_stream_bytes()` so it executes only after the entire response stream is consumed cleanly. Interrupted mid-stream reads record failures without resetting consecutive-failure counters first and trip the host circuit breaker at `settings.circuit_breaker_failure_threshold`.

4. **PR #40 Description Cleanup**:
   - Rewrote the PR #40 body from a UTF-8 file without PowerShell control characters (`U+0007`, `U+0008`, `U+000C`).

### Corrective Verification Results

- `pytest tests/test_recruitee_pipeline.py -q`: `20 passed, 4 warnings in 25.26s` (includes 3 new regression tests for malformed active offers, fallback-field SHA-256 fingerprint invalidation, and interrupted-stream circuit-breaker tripping)
- `pytest tests/test_recruitee_pipeline.py tests/test_board_monitor.py tests/test_company_board_registry.py tests/test_direct_board_router.py tests/test_direct_board_routing_integration.py tests/test_board_discovery_and_pipeline.py tests/test_bounded_retry.py tests/test_phase5_cost_and_robustness.py -q`: `82 passed, 4 warnings in 44.96s`
- `python scripts/eval_work_model.py`: exited `0` (`49` valid labelled rows evaluated, `0` regressions)
- `.\scripts\verify.ps1`: `8 passed, 0 failed, 0 skipped (of 8 checks)`
- **Operational Cache & Serper Integrity**: `0` Serper credits spent; `data/cache.sqlite` untouched (`14143488` bytes, `mtime: 2026-11-14T15:33:06.999067`)

### Corrective Provenance

- **Corrective Implementation Commit:** `ec97677cd3ea664a4c8af8b46d348dcec95affdb` (`fix(recruitee): harden snapshot validation, full-payload hash, and stream accounting`)
- **Corrective Provenance Doc Commit:** `e53effaac017cfead474dcdac1e8a4335184f692` (`docs(steps): record Step 43 corrective commit SHA`)

---

## 6. Final Corrective Pass: Explicit Status Validation & Direct-Board Registration

### Fixes Implemented

1. **Explicit Recruitee Offer Status Validation (`src/project_files/board_adapters.py`, `tests/test_recruitee_pipeline.py`)**:
   - Replaced catch-all non-`"published"` exclusion in `_validate_recruitee_offer_record()` with explicit verified Recruitee API status sets (`_RECRUITEE_ACTIVE_STATUSES = {"published"}`, `_RECRUITEE_INACTIVE_STATUSES = {"closed", "archived", "draft", "internal"}`).
   - Missing (`None`) status retains active handling (still requiring valid identity and title), recognized inactive statuses are excluded cleanly, and empty, non-string, or unrecognized statuses fail the snapshot (`BoardCheckResult(success=False, ...)`) so `BoardMonitor` preserves active monitored jobs instead of treating an unrecognized state as an authoritative empty closure.
   - Added regression checks for all four recognized inactive statuses (`draft`, `internal`, `archived`, `closed`), missing-status active offers, and unrecognized statuses (`pending_review`, `paused`, `unexpected_state`, `""`, `123`).

2. **Monitorable-Provider Direct-Board Auto-Registration (`src/project_files/search_pipeline.py`, `src/project_files/company_board_registry.py`, `tests/test_board_discovery_and_pipeline.py`)**:
   - Replaced the hardcoded `("greenhouse", "lever", "ashby")` allowlist in `SearchOrchestrator._search_direct_boards()` with `MONITORABLE_PROVIDERS` and added `_resolve_direct_board_token()` to prefer structured `job.company_slug` / `job.query_used` before `job.id` fallback.
   - Grouped non-empty direct-probe results by `(ats_provider, board_token)` so registration preserves `ats_provider`, `board_token`, `company_name`, `source_posting_url`, verified logo metadata, and isolated per-provider `active_job_count`, while never registering failed or empty probes.
   - Updated `CompanyBoardRegistry.register_candidate()` existing-row updates to backfill `source_posting_url` when empty and upgrade placeholder humanized `company_name` when an authoritative name is available (handling boards created earlier in the same probe by `set_board_identity()`).
   - Preserved `_search_ats_serper()` registration unchanged.
   - Added integration tests in `tests/test_board_discovery_and_pipeline.py` proving Workable (`verneek`) and Recruitee (`miaplaza`) real-fixture direct probes register verified boards, failed/empty probes register nothing, and same-slug multi-provider probes isolate counts.

### Final Verification Results

- `pytest tests/test_recruitee_pipeline.py tests/test_board_discovery_and_pipeline.py tests/test_board_monitor.py tests/test_company_board_registry.py tests/test_direct_board_router.py tests/test_direct_board_routing_integration.py -q`: `48 passed, 4 warnings in 31.67s`
- `python scripts/eval_work_model.py`: exited `0` (`49` valid labelled rows evaluated, `0` regressions)
- `.\scripts\verify.ps1`: `8 passed, 0 failed, 0 skipped (of 8 checks)`
- **Operational Cache & Serper Integrity**: `0` Serper credits spent; `data/cache.sqlite` untouched (`14143488` bytes, `mtime: 2026-11-14T15:33:06.999067`)

### Final Follow-up Provenance

- **Final Corrective Implementation Commit:** `c9a6a645057f9792533b8812168a6327f91d9529` (`fix(recruitee): validate explicit offer statuses and register all monitorable direct boards`)
