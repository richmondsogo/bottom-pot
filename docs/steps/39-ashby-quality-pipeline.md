# Step 39: Ashby Quality Pipeline

**Branch:** `step/39-ashby-quality-pipeline`
**Base:** `main` (`8ceb0cd`, Step 38 provider history documentation reconciliation)
**Date:** 2026-11-13
**Status:** Feature branch verified and pushed to `origin/step/39-ashby-quality-pipeline` (PR/merge pending explicit approval; `main` untouched)
**Serper Budget Spent:** `0` credits

---

## Reconciled Inventory & Verified Baseline (Before Step 39)

### 1. Serper URL Inventory Reconciliation (`serper_cache`)

Prior documentation reported two inconsistent totals (`84 genuine + 10 synthetic` vs. `93 total: 82 parsed, 10 synthetic, 1 unparsed genuine`). Deduplicating all Ashby-related organic URLs in `serper_cache` reconciles the exact population to **`93` distinct URLs**:

- **`82`** genuine parsed job posting URLs (`jobs.ashbyhq.com/{slug}/{uuid}`).
- **`1`** genuine unparsed URL: `https://jobs.ashbyhq.com/code-metal?jr_id=6ad90aa3950ef68d5184d761` (board slug `code-metal` with referral query `jr_id`, unresolvable directly via job-UUID API).
- **`0`** bare board-root URLs.
- **`10`** synthetic test/example URLs (`https://example.com/ashby/job/0` through `.../9`).
- **`0`** other/non-job URLs.

The reconciled total is `82 + 1 + 10 = 93` distinct URLs (`83` genuine + `10` synthetic). Separately, `21` rows in `company_boards` carried registry metadata (`verification_status='candidate'`, `monitoring_capability='supported'`, `active_job_count=0`), while `5` prior live `POST` API probes returned HTTP `401`; those `5` failed `POST` probes showed the legacy `POST` endpoint was rejected/unsupported rather than proving a `21/21` registry failure rate.

### 2. Operational Cache Baseline (`data/cache.sqlite`)

Across **`40`** genuine Ashby `url_cache` rows (representing `40` distinct job postings across **`36`** unique company slugs; **`0`** synthetic rows in `url_cache`), **`21`** Ashby `company_boards` rows (`0` verified logos, `0` checked), and **`0`** `monitored_jobs`:

- `description` (`description_ok=True`): **`40 / 40`**
- `location`: **`0 / 40`**
- `raw_location`: **`0 / 40`** (retained `0 / 40` by design: `JobExtractionService` populates `raw_location_preserved` only for Workday/sentinel preservation)
- `requirements`: **`0 / 40`**
- `eligibility`: **`0 / 40`**
- `company_logo_url` (`company_logo_verified=True`): **`0 / 40`**
- `work_model`: **`37 / 40`** (`17` `in_person`, `10` `hybrid`, `10` `remote`, `3` `unknown`; several `Hybrid` postings had leaked `is_remote=True` via raw `isRemote=True`)
- `employment_type`: **`40 / 40`**
- `department`: **`40 / 40`**
- `posted_at`: **`40 / 40`**
- `salary`: **`17 / 40`**
- `apply_url`: **`40 / 40`**
- Clean canonical URLs (without `?csj=`, `?locationId=`, `?embed=` tracking params): **`37 / 40`**
- Clean company names (without `Applied%20Compute` or UUID placeholder `Deaa6Ad2...`): **`38 / 40`**

---

## Observed Before / After Benchmark (`data/cache.sqlite` Operational Cache)

Before executing the live zero-Serper repair, a local backup was created at `data/cache.sqlite.bak-pre-ashby-repair` (gitignored).

### Zero-Serper Repair Execution (`python -m src.project_files.ashby_cache_repair`)

| Metric | Dry Run (`--dry-run`) | Live Pass 1 | Live Pass 2 (Idempotency) |
|---|---:|---:|---:|
| `total_urls` | `40` | `40` | `40` |
| `unique_slugs` | `36` | `36` | `0` |
| `repaired_from_board_api` | `36` | `36` | `0` |
| `repaired_from_posting_api` | `0` | `0` | `0` |
| `canonicalized_urls` (alias re-keyed) | `3` | `3` | `0` |
| `boards_reconciled` | `21` | `21` | `0` |
| `boards_identity_enriched` | `33` | `33` | `0` |
| `expired_or_unavailable` (HTTP 404 preserved) | `4` | `4` | `0` |
| `skipped_already_repaired` | `0` | `0` | `40` |
| `skipped_synthetic` | `0` | `0` | `0` |
| `transient_errors` | `0` | `0` | `0` |
| `serper_calls_used` | `0` | `0` | `0` |

### Field Coverage Across `40` Genuine `url_cache` Postings & `company_boards`

| Field | Before Step 39 | After Step 39 Live Repair |
|---|---:|---:|
| `location` | `0 / 40` | **`36 / 40`** (`36 / 36` live jobs) |
| `requirements` | `0 / 40` | **`31 / 40`** |
| `eligibility` | `0 / 40` | **`36 / 40`** (`36 / 36` live jobs) |
| `company_logo_url` & `company_logo_verified` | `0 / 40` | **`34 / 40`** |
| `work_model` | `37 / 40` (`17` in-person, `10` hybrid, `10` remote, `3` none) | **`39 / 40`** (`17` in-person, `11` hybrid, `11` remote, `1` none) |
| `salary` | `17 / 40` | **`18 / 40`** |
| Clean company names | `38 / 40` (`Applied%20Compute`, `Deaa6Ad2...`) | **`40 / 40`** (`Applied Compute`, `Spring Health`, `Plug Technologies Inc`, `Western Magnetics Company`, etc.) |
| Clean canonical URLs | `37 / 40` (`?csj=senior`, `?locationId=...`, `?embed=js`) | **`40 / 40`** (alias keys conservatively re-keyed & superseded rows removed) |
| `company_boards` (Ashby) | `21` (`0` verified logos, `0` checked) | **`36`** (`33` verified square logos, `36` checked with negative cache) |
| `ashby_repair_state` | — | **`43`** state rows (`36` `board_api`, `3` `board_api_canonicalized`, `4` `unavailable_404`) |

---

## Key Architectural & Quality Changes Implemented

1. **URL Parsing, Canonicalization & Board-Root Registration (`src/project_files/ats_url_parser.py`, `url_normalizer.py`, `field_normalizer.py`, `search_pipeline.py`)**:
   - Percent-decoded Ashby board slugs via `unquote`, lowercased UUID `job_id`, guarded against non-board Ashby paths (`_ASHBY_NON_BOARD_PATHS`) and synthetic slugs (`is_valid_board_slug`), and added `parse_ashby_board_root_url` wired into `_enrich_ats_item` (catching `code-metal?jr_id=...`).
   - Dropped Ashby tracking params (`embed`, `locationid`, `csj`, `employmenttype`) and trailing `/application` ONLY on validated `_ASHBY_JOB_PATH_RE` job posting paths in `url_normalizer.py`.
   - Updated `humanize_slug` to decode percent escapes (`Applied%20Compute -> Applied Compute`).

2. **Unified Extraction & GET API Migration (`src/project_files/ats_api_client.py`, `board_adapters.py`, `direct_board_router.py`, `work_model.py`)**:
   - Added `_extract_ashby_locations` (primary + deduplicated secondary locations joined with ` • `) and `ashby_payload_to_raw(...)` (keeping `workplaceType` authoritative, never converting `isRemote=True` into `"remote"` per ADR 0002, preserving `applyUrl` distinct from canonical `source_url`).
   - Migrated `AshbyClient`, `AshbyBoardAdapter` (versioned `v39:` rich content fingerprint + HTTP 304 conditional headers), and `probe_ashby_board` to `GET https://api.ashbyhq.com/posting-api/job-board/{encoded_slug}?includeCompensation=true` with `Accept-Encoding: gzip, deflate` to avoid Windows `brotlicffi` decoding errors.
   - Updated `work_model.py` patterns for `"work fully remotely"` and `"in-person internship/fellowship/role"`.

3. **Requirements, Eligibility & Verified Square Logos (`src/project_files/job_extraction_service.py`, `eligibility_extractor.py`, `logo_extractor.py`, `cache_store.py`)**:
   - Opted `"ashby"` into `JobExtractionService` requirements & eligibility extraction; added Ashby requirement headers (`minimum/preferred requirements`, `what you need/have/done`, `you're a great fit if`, `you should apply if`, etc.) with optional leading emoji tolerance.
   - Added `_GEO_SCOPE` multi-region matching (`North America and Europe`), `address.postalAddress.addressCountry` structured country lookup excluding `_NON_COUNTRY_REGIONS` (`EU`, `European Union`), and macro-region remote `allowed_residence` fallback.
   - Rejected `/api/images/org-theme-social/` and `/api/images/org-theme-wordmark/` globally in `_REJECTED_LOGO_PATTERNS`, implemented `extract_ashby_app_data_from_soup` + `_extract_ashby_logo` (JSON-LD logo then `organization.theme.logoSquareImageUrl` at confidence `0.80`), opted `"ashby"` into `extract_company_logo_for_provider`, added bounded/coalesced `enrich_ashby_board_identity`, and wired verified logo propagation into `search_pipeline.py` and `CacheStore._merge_preserving_completeness`.

4. **Zero-Serper Restartable Cache & Board Repair (`src/project_files/ashby_cache_repair.py`)**:
   - Implemented `repair_ashby_cache` with `--dry-run`, `--force`, `ashby_repair_state` (`v39`) checkpointing, synthetic/domain exclusion, 404 preservation, conservative URL alias re-keying, and board identity reconciliation.

---

## Verification Results

All checks passed after the final code and test edits:

- **Real Fixture Corpus (`tests/fixtures/real/ashby/`)**: Captured `12` real Ashby JSON/HTML fixtures alongside existing `linear_board.json`. Updated `tests/test_real_api_fixtures.py` for Step 39's documented `ashby_d3bc1ced.json` progression (`location == "Europe"`, `requirements`, `eligibility`, `extraction_confidence == 0.86`).
- **Full Backend Unit & Integration Suite (`python -m pytest -q`)**: **`909 passed, 4 warnings in 70.77s`** (including `tests/test_ashby_pipeline.py` + 19 cross-provider/shared modules `600 passed`).
- **Frontend Unit Tests (`npm --prefix frontend run test`)**: **`17` test files, `113 passed`**.
- **Full Project Verification (`.\scripts\verify.ps1`)**: **`8 passed, 0 failed, 0 skipped (of 8 checks)`**:
  - Git available & zero tracked secrets
  - `node scripts/lint_css_cascade.js`
  - `npm --prefix frontend run lint` (`oxlint`)
  - `npm --prefix frontend run test` (`vitest`)
  - `npm --prefix frontend run build` (`tsc -b && vite build`)
  - `python -m pytest -q`
  - `npx playwright test` (**`42 passed`**, including `Step 39: Ashby square logos, authoritative names, work models, salary, eligibility, and 5-viewport responsiveness` across `1920x1080`, `1440x900`, `1024x768`, `768x1024`, and `390x844` with square `0px` `CompanyMark`, verified square logo + monogram fallback, `In-person`/`Hybrid`/`Remote` badges, zero horizontal overflow, zero console/page errors, and zero critical/serious Axe WCAG violations).
- **Work Model Dataset Evaluation (`python scripts/eval_work_model.py`)**: Ran cleanly with zero regressions across `49` labelled legacy rows.

---

## Provenance

- **Feature Branch**: `step/39-ashby-quality-pipeline`
- **Base Commit (`main`)**: `8ceb0cd2c9e6fe7982e34a1cc0ff60b5bddc57e6`
- **Implementation Commit**: `7464b2f` (`feat(step-39): implement Ashby quality pipeline, square logos, and bounded cache repair`)
- **Publication Status**: Pushed to `origin/step/39-ashby-quality-pipeline` (not merged to `main`).
