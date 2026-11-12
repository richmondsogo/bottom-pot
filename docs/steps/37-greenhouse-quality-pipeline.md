# Step 37: Greenhouse Quality Pipeline

**Branch:** `step/37-greenhouse-quality-pipeline`
**Base:** `main` (`3716b3d`, Merge Step 36: Lever quality pipeline)
**Date:** 2026-11-12
**Status:** Complete (Local feature branch ready for review; not pushed or merged)
**Serper Budget Spent:** `0` credits

---

## Verified Baseline (Before Step 37)

Populations audited from `data/cache.sqlite` (zero synthetic `company0..9` / `acme` rows):

- Total `url_cache` Greenhouse rows: 58 (**48** genuine cached records across **40** unique genuine company slugs; 10 synthetic `company0..9`)
- Genuine `serper_cache` Greenhouse URLs: **81** unique URLs
  - 74 currently match `parse_ats_url`
  - 8 use `http://` (2 EU, 6 US)
  - 6 use `job-boards.eu.greenhouse.io` (ignored by parser)
  - 1 uses hyphenated ID (`https://job-boards.greenhouse.io/corasps/jobs/5131342007-8`, ignored by parser)
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

## Observed Before / After Benchmark (`data/cache.sqlite` & Genuine Corpus)

Bounded zero-Serper repair (`src/project_files/greenhouse_cache_repair.py`) processed 58 cached Greenhouse rows across 50 unique slugs (41 repaired from public board APIs, 17 expired/unavailable preserved/classified, 23 board identities enriched, `0` Serper calls made):

| Metric | Before Step 37 | After Step 37 |
|---|---|---|
| Total cached Greenhouse rows (`url_cache`) | 58 (48 genuine, 10 synthetic) | 64 (with alias normalization) |
| Verified company logos (`company_logo_verified=True`) | 0 | 23 |
| Populated `requirements` | 0 | 30 |
| Populated `eligibility` | 0 | 41 |
| Populated `salary` | 13 | 22 |
| Populated `work_model` | 30 | 37 |
| Registered Greenhouse `company_boards` | 18 (0 verified logos) | 28 (21 verified logos) |

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

All checks executed cleanly after the final edit on `step/37-greenhouse-quality-pipeline`:

- **Fixture Integrity**: `tests/fixtures/real/greenhouse/job_8860302002.json` remains untouched; 31 genuine Greenhouse API/HTML/cache fixture files + `serper_urls_81.json` (32 new files total) added under `tests/fixtures/real/greenhouse/`. Documented Step 37 `eligibility` and `requirements` progression asserted in `tests/test_real_api_fixtures.py`.
- **Cross-Provider Regression Suite (13 test files)**: `458 passed`.
- **Full Backend Test Suite (`python -m pytest -q`)**: `888 passed`.
- **Frontend Unit Tests (`npm --prefix frontend run test`)**: `113 passed` (17 files).
- **Frontend Linting, CSS Cascade Lint & Production Build (`oxlint`, `lint_css_cascade.js`, `tsc -b && vite build`)**: `0` errors.
- **Playwright E2E Suite (`npx playwright test`)**: `41 passed`, including `Step 37: Greenhouse CDN logos, authoritative names, hourly/annual salary, work models, requirements, and 5-viewport responsiveness` across `1920x1080`, `1440x900`, `1024x768`, `768x1024`, and `390x844` (0px square `CompanyMark`, CDN logo image loading and monogram fallback, salary & work-model rendering, `DetailSheet` requirements, zero horizontal overflow, zero console/page errors, zero critical/serious Axe WCAG violations).
- **Full Project Verification (`.\scripts\verify.ps1`)**: `8 passed, 0 failed, 0 skipped (of 8 checks)`.

---

## Provenance

- **Branch**: `step/37-greenhouse-quality-pipeline`
- **Base Commit (`main`)**: `3716b3d` (Merge Step 36: Lever quality pipeline)
- **Step 37 Commit(s) / PR**: Local feature branch committed and verified (`PR / Merge`: not pushed or merged per instructions).
