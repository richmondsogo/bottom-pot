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
- **Last Commit SHA:** `c21e24e309d5746a08e32edff52c88200eff61e6` (implementation commit; followed by this provenance update commit)
- **Merge Commit SHA:** _Not merged per MERGE_POLICY_
