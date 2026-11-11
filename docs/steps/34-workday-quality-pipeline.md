# Step 34: Workday Quality Pipeline & Geographic/Application Eligibility Framework

## Overview
- **Goal**:
  1. Consolidate all Workday URL parsing, CXS API extraction, HTML/JSON-LD fallback, and resilience tracking onto a single authoritative pathway anchored by `WorkdayClient` (`src/project_files/ats_api_client.py`), registered in `ATS_CLIENTS["workday"]`, with `ats_page_enricher.py` delegating directly to `WorkdayClient` (no parallel competing implementation).
  2. Eliminate all observed Workday URL parsing failures (3-segment `/job/<loc>/<slug>/apply`, `/apply` collision on `job_id == "apply"`, `site_id="jobs"`/`"Jobs"` career sites, query/fragment preservation for `hiringCompany`, and shared-tenant `{site_id.lower()}__{job_slug}` disambiguation).
  3. Build a conservative, reusable **Geographic & Application Eligibility Framework** (`JobEligibility`, `EligibilityFact` with controlled `EligibilityFactDimension` in `models.py` and `eligibility_extractor.py`) separating physical location, residence restrictions, citizenship, security clearance, work authorization, visa sponsorship, payroll requirements, relocation, employment arrangement (`employee`/`contractor`/`eor`), timezone, and confirmed foreign hybrid attendance (`nigeria_eligible: bool | None`).
  4. Apply User Decision 1 (Option A): preserve verbatim `raw_location`, clean duplicate trailing country suffixes and UTF-8 text without guessing cities from facility codes, and append verified structured CXS country descriptors (`ESP - MD - LAS ROZAS, Spain`).
  5. Apply User Decision 2 & Safeguard 1: domestic work authorization without sponsorship resolves `nigeria_eligible = None` (not automatically `False`); contractor/EOR arrangements never override explicit residence or physical attendance restrictions; foreign hybrid roles require confirmed attendance obligations to resolve `False`; marketing boilerplate (`"for P&C insurers worldwide"`) never establishes `global_remote_explicit`.
  6. Remediate all 4 verified Tier-3 `salary_parser.py` bugs discovered in real Workday `url_cache` records (decimal truncation, ISO currency suffix shadowing, half-open `$ USD - $max` fabrication, and competing multi-band/level pay disclosures) with zero cross-provider regressions.
  7. Extend Workday work-model resolution (including bilingual API enums and `TELECOMMUTE`), bold/Spanish `requirements` extraction, and `posted_at` date validation (reject future `startDate > scraped_at + 1d` and coarse `"Posted 30+ Days Ago"` labels).
  8. Propagate `eligibility` and `raw_location` cleanly through `CanonicalJob`, `JobListing`, `CanonicalJobAdapter`, `GlobalDeduplicator`, `src/api/allowlist.py` (`eligibility` user-visible, `raw_location` admin-only), and the square editorial `DetailSheet.tsx` + `export.ts` UI.
- **Branch**: `step/34-workday-quality-pipeline`
- **Serper Budget Allocated**: `0` live calls (offline evaluation against authentic captured fixtures, SQLite caches, and observed stores)

---

## 1. Reconciled Baseline vs. Post-Change Denominators

To avoid denominator confusion, every dataset and failure mode is measured separately, distinguishing CXS (`api`), JSON-LD HTML fallback (`scrape`), and unenriched (`snippet`) outcomes:

| Data Store / Source | Exact Workday Denominator | Pre-Change (`main`) | Post-Change (`step/34-workday-quality-pipeline`, Offline) |
|---|---:|---|---|
| **Observed Real Workday URL Corpus** (`serper_cache` + `url_cache` + `audit.csv` + `results.json`, excluding `10` synthetic `company0..9` URLs) | **84 unique real URLs** *(87 incl. 3 fixture URLs)* | **10 / 84 fail `parse_ats_url`**: `3` dropped (`None`), `7` misparsed (`job_id == "apply"`). | **0 / 84 fail `parse_ats_url`** (`0` dropped `None`, `0` `job_id == "apply"`, `0` `build_workday_cxs_url` failures; **0 / 87** including all 3 fixtures). |
| **`data/cache.sqlite` (`url_cache`, real rows)** | **35 real rows** *(separating `10` synthetic `company0..9` rows from `45` total Workday rows)* | `32` `api` (descriptions present; `0` `requirements`; `5` salary incl. 3 Tier-3 bugs: dropped `CAD` currency & truncated min=max ranges; `0` `eligibility`); `3` `snippet` (`roche.wd3` x2, `saabgroup.wd116` x1; `0`-char descriptions). | **`api` (`n=32`)**: `32/32` URLs parse cleanly; `32/32` descriptions; **`19/32` `requirements`**; **`8/32` `salary`** (remediated `CAD` currency & full min–max ranges + recovered 3 previously missed ranges); `17/32` `work_model`; `14/32` eligibility facts (`nigeria_eligible`: `0` `True`, `2` `False`, `30` `None` — zero false positives on domestic work auth or Guidewire `"worldwide"` marketing copy). **`snippet` (`n=3`)**: `3/3` URLs parse cleanly (`0` `apply` errors); `0/3` descriptions (offline mode — `0` live HTTP/CXS requests). |
| **`results.json`** | **7 rows** (`4` `api` + `3` `/apply` `snippet`) | `4` `api` (`1,943–6,381` chars; `0/4` `requirements`; `0/4` `salary`; `0/4` `eligibility`); `3` `snippet` (all 3 `/apply` URLs previously failed URL parsing / yielded `0` chars). | **`api` (`n=4`)**: `4/4` URLs parse cleanly; **`1/4` `salary`** (`Software Developer, Senior` recovered `USD 86,800–198,000`); `1/4` eligibility facts (`Top Secret clearance` -> `nigeria_eligible = None`). **`snippet` (`n=3`)**: `3/3` `/apply` URLs now resolve clean `job_id` & CXS endpoints (`0` live requests). |
| **Captured HTML & CXS Fixtures** (`tests/fixtures/real/workday/`) | **3 postings** (`4dcb1862`, `760bc3cc`, `d5f8651a`) + `cxs_4dcb1862.json` | CXS inline in `ats_page_enricher.py` (`4dcb1862` returned `ESP - MD - LAS ROZAS` without country; no JSON-LD HTML fallback on `WorkdayClient`; no `postingAvailable: false` detection). | **CXS `api` (`4dcb1862`)**: `SUCCESS`, `raw_location="ESP - MD - LAS ROZAS"` -> `location="ESP - MD - LAS ROZAS, Spain"`, `work_model="in_person"`, `requirements` `493` chars, `description` `5,511` chars, `posted_at=2026-10-13T00:00:00Z`, `nigeria_eligible=False`. **HTML `scrape` fallback (`4dcb1862.html`, `760bc3cc.html`)**: `SUCCESS` (`data_source="scrape"`), **1.000** word completeness (`611/611` and `647/647`), `760bc3cc.html` `work_model="remote"` (`api_enum`, `TELECOMMUTE`) + `nigeria_eligible=False` (`allowed_residence: ["Tunisia"]`). **Expired shell (`d5f8651a.html`)**: `postingAvailable: false` -> **`ExtractionOutcome.NOT_FOUND`**. |

*(Note: `audit.csv` contains 20 Workday summary rows (`16` `scrape`, `4` `snippet`) covering URL/location/work_model columns only; its 20 URLs are included in the 84-URL corpus above.)*

---

## 2. Key Architectural Changes

1. **Single Authoritative Workday Extraction Path**:
   - Implemented `WorkdayClient` in `src/project_files/ats_api_client.py` and registered `"workday": WorkdayClient()` in `ATS_CLIENTS`.
   - Extracted shared challenge/unavailable/JSON-LD helpers into `src/project_files/html_helpers.py` (`is_waf_challenge`, `is_workday_posting_unavailable`, `extract_json_ld_documents`, `extract_job_posting_json_ld`, `jsonld_text`, `html_title_fallback`, `html_meta_content`).
   - Refactored `ats_page_enricher.py` to delegate Workday CXS URL building and fetching directly to `ats_url_parser.build_workday_cxs_url` and `WorkdayClient().fetch_result`.
   - Fetch flow: `WorkdayClient.fetch_raw_result` tries `/wday/cxs/{tenant}/{site_id}/job/{job_slug}` -> falls back on CXS `404`/`403`/WAF/transient failure to canonical posting HTML (`JobPosting` JSON-LD -> `ExtractionMethod.JSON_LD` / `data_source="scrape"`; `postingAvailable: false` or HTTP `404`/`410` -> `ExtractionOutcome.NOT_FOUND`) -> degrades to `snippet` (`degraded_from="api"`, `eligibility=None`) only when both paths fail.

2. **URL Parsing & Normalization (`ats_url_parser.py`, `url_normalizer.py`)**:
   - Added `parse_workday_url` -> `WorkdayUrlParts`, supporting `{tenant}.wdN.myworkdayjobs.com` & `{tenant}.myworkdayjobs.com`, optional locales (`en-US`, `en-us`, `de-DE`, `fr-CA`, `zh-CN`, `es`), career site IDs including `"jobs"` / `"Jobs"` (PayPal, TravelHRPortal), optional location segments, trailing `/apply` suffixes, and query/fragment stripping while preserving tenant-scoping params (`hiringCompany`).
   - Prevented shared-tenant site collisions via `job_id = f"{site_id.lower()}__{job_slug}"`.

3. **Geographic & Application Eligibility Framework (`models.py`, `confidence_policy.py`, `eligibility_extractor.py`)**:
   - Added controlled `EligibilityFactDimension` `Literal[...]`, `EligibilityFact`, and `JobEligibility` models; registered `RAW_LOCATION` and `ELIGIBILITY` in `confidence_policy.py` without altering `CORE_FIELD_WEIGHTS`.
   - Implemented `extract_eligibility` separating applicant residence restrictions, physical location, citizenship, security clearance, work authorization, visa sponsorship (`available`/`not_available`/`conditional`/`undisclosed`), payroll requirements, relocation, employment arrangement (`employee`/`contractor`/`eor`), timezone, and confirmed foreign hybrid attendance.

4. **Salary, Location, Work-Model, Requirements, Dates & Frontend Propagation**:
   - Remediated all 4 Tier-3 `salary_parser.py` defects and Decision 1 (Option A) `raw_location` / country descriptor normalization in `job_extraction_service.py`.
   - Propagated `eligibility` and `raw_location` through `CanonicalJobAdapter`, `GlobalDeduplicator`, `src/api/allowlist.py` (`eligibility` in `USER_JOB_FIELDS`, `raw_location` in `ADMIN_JOB_FIELDS`), `frontend/src/types.ts`, `frontend/src/lib/normalize.ts`, `frontend/src/lib/export.ts`, and square editorial `frontend/src/components/DetailSheet.tsx`.

---

## 3. Verification Gate Results & Diff Hygiene

- **Git & Fixture Integrity**:
  - Active branch: `step/34-workday-quality-pipeline` (unmerged; `main` untouched; pending review/commit/PR per `BUILD_PROTOCOL.md` & `MERGE_POLICY`).
  - `git diff --check`: clean (0 whitespace errors).
  - `git diff --name-only tests/fixtures/real`: empty (`0` modifications to original real fixtures).
- **Frontend Verification**:
  - `node scripts/lint_css_cascade.js`: passed.
  - `npm --prefix frontend run lint` (`oxlint`): 0 errors (3 pre-existing shadcn export warnings).
  - `npm --prefix frontend run test` (`vitest`): 15 test files, 107 tests passed.
  - `npm --prefix frontend run build` (`tsc -b && vite build`): passed.
- **Backend Verification**:
  - `python -m pytest -q`: **704 passed, 0 failed, 4 warnings** (includes `68` Workday pipeline tests in `tests/test_workday_pipeline.py`, `43` client/scraper replay tests in `tests/test_scrapers_and_clients.py`, and all regression/allowlist/salary tests).
- **Verification Script & Playwright E2E**:
  - `.\scripts\verify.ps1 -SkipE2E`: 7 passed, 0 failed, 1 skipped (of 8 checks).
  - Default Playwright port `127.0.0.1:8000` is excluded on this Windows host by OS Hyper-V/WinNAT TCP exclusion range `7971–9070` (`WinError 10013`). Running the complete unmodified `tests/e2e/` Playwright suite against `127.0.0.1:18000` passed **38 / 38 tests** (including the two new Step 34 `DetailSheet` user/admin eligibility, square `0px` geometry, 5-viewport overflow, light/dark mode, and Axe-core WCAG 2.0 A/AA checks).
- **Serper Budget**: `0` live Serper API calls used during Step 34 implementation or evaluation.
