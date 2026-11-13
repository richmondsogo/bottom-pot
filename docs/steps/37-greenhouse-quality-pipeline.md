# Step 37: Greenhouse Quality Pipeline

**Branch:** `step/37-greenhouse-quality-pipeline`
**Base:** `main` (`3716b3d`, Merge Step 36: Lever quality pipeline)
**Date:** 2026-11-12 (reconciled 2026-11-13)
**Status:** Merged to `main` (`6041ce7`, `--no-ff`) and published to `origin/main`
**Serper Budget Spent:** `0` credits

---

## Verified Baseline (Before Step 37)

Populations audited from `data/cache.sqlite` (separating genuine postings from the `10` pre-existing synthetic `company0`–`company9` test rows created `2026-11-04`):

- Total `url_cache` Greenhouse rows before cleanup: `58` (**`48`** genuine cached jobs across **`40`** unique genuine company slugs + `10` pre-existing synthetic `company0`–`company9` rows).
- Genuine `serper_cache` Greenhouse URLs: **81** unique URLs *(note: the observations below overlap and are non-exclusive categories, so they must not be summed)*:
  - `74` parsed by the original `parse_ats_url`
  - `8` use `http://` (2 EU, 6 US)
  - `6` use `job-boards.eu.greenhouse.io` (previously ignored by parser)
  - `1` uses a hyphenated ID (`https://job-boards.greenhouse.io/corasps/jobs/5131342007-8`, previously ignored by parser)
- Registered Greenhouse `company_boards`: **18** rows (all `candidate`, `supported`, `active_job_count=0`, `company_logo_verified=0`; row `#64` has `company_name="Canonical Nigeria"` for `canonical_managed_posts`)
- Monitored Greenhouse jobs: **0**
- Field coverage across the **48** genuine cached Greenhouse records:
  - `description_ok=True`: 48 / 48
  - `requirements`: **0 / 48**
  - `eligibility`: **0 / 48**
  - `company_logo_url` (`company_logo_verified=True`): **0 / 48**
  - `salary`: **13 / 48** (7 structured `pay_input_ranges` had `period=None` and raw dict+HTML strings in `raw_text`; Twilio Canadian `$` missed/unqualified currency; Schonfeld/Excel/GitLab ranges missed)
  - `work_model`: **30 / 48** (SpaceX explicit onsite misclassified `hybrid`; Okta `#LI - Hybrid` missed; Checkr/Excel `3+ days` / `3-days` in office missed)
  - Eligibility false positives reproduced when evaluated: Figma product copy (`anywhere in the world`), Nortal (`Latin America - Remote` contradicted by `work from anywhere`), Reddit CCPA clause (false `contractor`), Databricks/Walker Sands `B2B` copy (false `contractor`).

---

## Implementation Plan (Milestones 1-11)

1. Capture real Greenhouse API JSON, HTML, and `serper_urls_81.json` fixtures under `tests/fixtures/real/greenhouse/` (preserving immutable `job_8860302002.json`).
2. Fix Greenhouse URL discovery, parsing, normalization, and canonicalization (`job-boards.eu.greenhouse.io`, `http://` -> `https://` for recognized hosts, hyphenated IDs like `5131342007-8`, redundant `?gh_jid=` stripping vs unverified custom-domain rejection, board-root registration).
3. Fix expired Greenhouse `?error=true` HTML redirect detection cleanly in page enrichment and monitoring.
4. Unify `GreenhouseClient`, `GreenhouseBoardAdapter` (`?content=true&pay_transparency=true`, fingerprint `v37`), and `probe_greenhouse_board` onto a shared `greenhouse_payload_to_raw` builder.
5. Enable & expand requirements extraction for Greenhouse headings and stop headings.
6. Fix work-model classification (SpaceX onsite override vs AppDirect hybrid, `#LI - Hybrid`, `N+ days` office context) while respecting ADR 0002.
7. Harden eligibility extractors (marketing/product copy vs hiring scope, CCPA contractor disclaimer, B2B context, GitLab US-only salary footnote, regional contradiction) and enable Greenhouse eligibility.
8. Improve Greenhouse structured (`pay_input_ranges`) and description salary extraction (clean `raw_text`, conservative period normalization, `$17.00 per hour`, `between $X and $Y`, multi-line salary headings, multi-level/Canadian `$` safety).
9. Enable Greenhouse CDN company logos (`_extract_greenhouse_logo`, board HTML/job HTML fallback, banner rejection) and protect authoritative board identity (`enrich_greenhouse_board_identity`, `Canonical Nigeria` prevention).
10. Run bounded zero-Serper repair (`src/project_files/greenhouse_cache_repair.py`) over the 48 genuine cached rows and record exact before-and-after metrics.
11. Complete cross-provider regression suite, 5-viewport Playwright browser verification, and `.\scripts\verify.ps1`.


---

## Observed Before / After Benchmark (`data/cache.sqlite` — Reconciled Genuine Population)

### Cache & Registry Denominators (Before vs. After Cleanup)

- **Before cleanup**: `58` Greenhouse `url_cache` rows (`48` genuine unique jobs across `40` unique genuine slugs + `10` pre-existing synthetic `company0`–`company9` rows created `2026-11-04`).
- **After cleanup**: **`54`** genuine Greenhouse `url_cache` keys representing **`48` genuine unique jobs across `40` unique genuine slugs** plus **`6` canonicalized URL alias keys** (`spacex:8769729002`, `cloudflare:8328914`, `cloudflare:8329741`, `figma:6238015004`, `shifttechnology:7674348003`, `appdirect:8910223002`), and **`0`** synthetic Greenhouse rows. *(Note: `54` cache keys do not represent `54` unique postings; they represent `48` genuine jobs plus six query-parameter aliases.)*
- **`greenhouse_repair_state`**: **`54`** genuine entries (`47` `repaired`: `41` `board_api` + `6` `board_api_normalized`; `7` genuine `unavailable_404`), **`0`** synthetic records.
- **`company_boards` (Greenhouse)**: **`18`** (`0` verified logos) before Step 37 → **`34`** genuine Greenhouse boards (**`23`** verified logos) after Step 37, **`0`** synthetic boards.
- **`monitored_jobs` (Greenhouse)**: **`0`** rows.

### Field Coverage Across `48` Unique Genuine Jobs (Preferring Repaired Canonical Key)

| Metric (`48` unique genuine jobs) | Before Step 37 | Final after Step 37 |
|---|---:|---:|
| Verified logos (`company_logo_verified=True`) | `0 / 48` | `23 / 48` |
| Populated `requirements` | `0 / 48` | `30 / 48` |
| Populated `eligibility` | `0 / 48` | `41 / 48` |
| Populated `salary` | `13 / 48` | `20 / 48` |
| Populated `work_model` | `30 / 48` | `33 / 48` |

### Field Coverage Across `54` Genuine `url_cache` Keys

*(For the `6` jobs that retain both an older pre-repair query-parameter URL key and a newly repaired canonical key, older un-repaired alias rows do not gain newly populated `requirements`/`eligibility`/`logo` fields. Measuring across all `54` cache keys gives the following key-level counts; do not combine these with the `48`-job canonical counts above.)*

| Metric (`54` genuine cache keys) | Final after Step 37 |
|---|---:|
| Verified logos (`company_logo_verified=True`) | `23 / 54` |
| Populated `requirements` | `30 / 54` |
| Populated `eligibility` | `41 / 54` |
| Populated `salary` | `22 / 54` |
| Populated `work_model` | `37 / 54` |

### Synthetic-Record Audit & Remediation

- **Pre-existing synthetic artifacts**: `10` synthetic `company0`–`company9` Greenhouse `url_cache` rows (`https://boards.greenhouse.io/company{0..9}/jobs/{1000..1009}`, `description='Description'`, `description_ok=False`) and `2` Greenhouse-only synthetic `serper_cache` entries existed prior to Step 37 (created `2026-11-04`).
- **Initial Step 37 repair (`7f7bb0f`)**: Queried `url_cache WHERE url LIKE '%greenhouse.io/%'` without filtering synthetic slugs, so those `10` synthetic rows were fetched (`HTTP 404`), written to `greenhouse_repair_state` (`unavailable_404`), and counted inside the earlier `58`-row / `50`-slug / `17`-unavailable summary. Crucially, **zero** synthetic `company_boards` rows were created (HTTP `404` aborted before `set_board_identity`), **zero** synthetic `monitored_jobs` were created, and **zero** extracted fields or logos were produced for `company0`–`company9`.
- **Follow-up guard (`60b108e`)**:
  1. Updated `is_valid_board_slug` in `src/project_files/ats_url_parser.py` to reject synthetic placeholder slugs (`company\d+`, `testcompany`, `fake*`, `dummy*`, `placeholder*`), protecting `CompanyBoardRegistry`, `enrich_greenhouse_board_identity`, and search discovery.
  2. Added `_is_synthetic_greenhouse_record` and `GreenhouseRepairReport.skipped_synthetic` in `src/project_files/greenhouse_cache_repair.py` so synthetic records are excluded before URL counting, `greenhouse_repair_state` writes, or HTTP requests.
  3. Removed the `10` repair-created `company0`–`company9` rows from `greenhouse_repair_state` while preserving all `54` genuine repair-state entries.
  4. Added `test_synthetic_records_skipped_by_repair_and_rejected_by_registry` in `tests/test_greenhouse_pipeline.py` verifying zero HTTP requests, zero `greenhouse_repair_state` entries, and zero `company_boards` registrations for synthetic slugs.
- **Final operational database cleanup**: After creating a local SQLite backup (`data/cache.sqlite.bak-pre-greenhouse-synthetic-cleanup`), removed the `10` pre-existing expired synthetic `company0`–`company9` Greenhouse rows from `url_cache` and the `2` Greenhouse-only synthetic `serper_cache` entries in a single transaction, leaving **zero** synthetic Greenhouse records in `url_cache`, `greenhouse_repair_state`, `company_boards`, `monitored_jobs`, or `serper_cache`. Because `data/cache.sqlite` is gitignored, this local operational-cache cleanup is not a tracked database change in Git.

---

## Key Architectural & Quality Changes Implemented

1. **Discovery, URL Parsing & Canonicalization (`src/project_files/ats_url_parser.py`, `url_normalizer.py`, `search_pipeline.py`)**:
   - Supported `boards.greenhouse.io`, `job-boards.greenhouse.io`, and `job-boards.eu.greenhouse.io`; normalized `http://` schemes on recognized Greenhouse hosts to `https://`.
   - Preserved hyphenated requisition IDs (`5131342007-8`), stripped redundant `?gh_jid=` parameters when `/jobs/{id}` matches, and routed board-root URLs cleanly to `company_board_registry`.
2. **Expired Job Redirect Handling (`src/project_files/ats_page_enricher.py`, `board_adapters.py`)**:
   - Detected `?error=true` expired Greenhouse redirects and unavailable postings cleanly without emitting synthetic/stale active records.
3. **Unified Extraction (`src/project_files/ats_api_client.py`, `board_adapters.py`, `direct_board_router.py`, `job_extraction_service.py`)**:
   - Added `greenhouse_payload_to_raw(...)` with `extraction_method=ExtractionMethod.ATS_API` and unified `GreenhouseClient`, `GreenhouseBoardAdapter` (`?content=true&pay_transparency=true`, versioned fingerprint `v37:`), and `probe_greenhouse_board`.
4. **Requirements Extraction (`src/project_files/job_extraction_service.py`)**:
   - Expanded heading/stop-heading handling (`What you'll bring`, `Must haves`, `What we look for`, `What we offer`, `Why join`) and enabled Greenhouse in `JobExtractionService.extract`.
5. **Work Model Classification (`src/project_files/work_model.py`)**:
   - Fixed explicit onsite overrides, supported `#LI - Hybrid` and negative after-patterns, and matched `3+ days a week` / `3-days a week` office requirements per ADR 0002.
6. **Eligibility Guardrails (`src/project_files/eligibility_extractor.py`, `job_extraction_service.py`)**:
   - Filtered product/marketing copy, CCPA/candidate privacy contractor disclaimers, and B2B copy false positives; required explicit `remote` pairing on `location` before inferring `allowed_residence`; treated broad Nigeria-containing regions (`EMEA`, `Africa`, `Sub-Saharan Africa`) neutrally (`nigeria_eligible is None`); enabled Greenhouse eligibility extraction.
7. **Salary Extraction (`src/project_files/salary_parser.py`)**:
   - Added `"and"` range separator (`between $100,000 and $110,000`), stripped HTML blurbs from structured `pay_input_ranges` `raw_text`, supported `$17.00 per hour` and labelled pay headings while preserving `None` on multi-level salaries and unqualified Canadian `$` disclosures.
8. **CDN Logos & Authoritative Board Identity (`src/project_files/logo_extractor.py`, `company_board_registry.py`, `greenhouse_cache_repair.py`)**:
   - Implemented `_extract_greenhouse_logo` validating `s*-recruiting.cdn.greenhouse.io/external_greenhouse_job_boards/logos/` (rejecting banners) and `enrich_greenhouse_board_identity` (normalizing Canonical identity without `"Canonical Nigeria"` pollution).

---

## Verification Results

All checks executed cleanly on merged `main` (`6041ce7`):

- **Fixture Integrity**: `tests/fixtures/real/greenhouse/job_8860302002.json` remains untouched; 31 genuine Greenhouse API/HTML/cache fixture files + `serper_urls_81.json` (32 new files total) added under `tests/fixtures/real/greenhouse/`. Documented Step 37 `eligibility` and `requirements` progression asserted in `tests/test_real_api_fixtures.py`.
- **Final Merged-`main` Backend Test Suite (`python -m pytest -q`)**: **`889 passed, 4 warnings`** *(historical feature-branch context: `888 passed` prior to adding `test_synthetic_records_skipped_by_repair_and_rejected_by_registry` in `60b108e`; targeted suites `458 passed` pre-audit / `215 passed` post-guard)*.
- **Final Merged-`main` Frontend Unit Tests (`npm --prefix frontend run test -- --run`)**: **`113 passed`** (`17` test files).
- **Frontend Linting, CSS Cascade Lint & Production Build (`oxlint`, `lint_css_cascade.js`, `tsc -b && vite build`)**: `0` errors.
- **Final Merged-`main` Playwright E2E Suite (`npx playwright test`)**: **`41 passed`**, including `Step 37: Greenhouse CDN logos, authoritative names, hourly/annual salary, work models, requirements, and 5-viewport responsiveness` across `1920x1080`, `1440x900`, `1024x768`, `768x1024`, and `390x844` (0px square `CompanyMark`, CDN logo image loading and monogram fallback, salary & work-model rendering, `DetailSheet` requirements, zero horizontal overflow, zero console/page errors, zero critical/serious Axe WCAG violations).
- **Final Merged-`main` Full Project Verification (`.\scripts\verify.ps1`)**: **`8 passed, 0 failed, 0 skipped (of 8 checks)`**.

---

## Provenance

- **Feature Branch**: `step/37-greenhouse-quality-pipeline`
- **Base Commit (`main`)**: `3716b3d` (Merge Step 36: Lever quality pipeline)
- **Initial Implementation Commit**: `7f7bb0f`
- **Synthetic-Record Guard Commit**: `60b108e`
- **Merge Commit (`main`)**: `6041ce7` (`--no-ff` merge; parent 1 `3716b3d`, parent 2 `60b108e`)
- **Publication Status**: Merged to `main` via `--no-ff` and pushed to `origin/main`.
