# Step 35: Teamtailor Quality Pipeline & Company Logo Extraction

## Overview
- **Goal**:
  1. Remediate all investigated Teamtailor discovery, URL parsing, closed/non-job rejection, structured extraction, canonical identity, deduplication, requirements, eligibility, work-model, salary, and post-relevance board registration defects on a single unified pipeline.
  2. Establish a reusable, SSRF-safe **Company Logo Extraction** capability (`src/project_files/logo_extractor.py`) with Teamtailor-only activation in Step 35, schema/adapter/deduplicator/registry/allowlist propagation (`company_logo_url` user-facing; `company_logo_source` and `company_logo_verified` admin-only), verified-logo overwrite protection, and square `--radius: 0` frontend rendering via [`CompanyMark`](frontend/src/components/CompanyMark.tsx).
- **Branch**: `step/35-teamtailor-quality-pipeline`
- **Serper Budget Allocated**: `2` live queries used during Step 35 reconnaissance/investigation; `0` additional live calls spent during Step 35 implementation or offline verification.

---

## 1. Reconciled Baseline vs. Post-Change Denominators

Every data source is measured separately:

| Data Store / Source | Exact Teamtailor Denominator | Pre-Change (`main` Baseline) | Post-Change (`step/35-teamtailor-quality-pipeline`, Offline) |
|---|---|---|---|
| **`audit.csv` Teamtailor Records** | **6 rows** *(out of `102` total audit rows)* | **`3 / 6` (`50%`) pollution**: `Vervoe integration` (`snippet`, `Unknown`), `HappyrMatch integration` (`snippet`, `Unknown`), `Título: Integrações` (`scrape`, `Unknown`). Only `3` genuine jobs. | Integration/marketing/support paths (`www.teamtailor.com/*/integrations*`, `support.teamtailor.com/*`, non-job pages) are excluded at query time (`-site:www.teamtailor.com -site:support.teamtailor.com`) and rejected cleanly at URL/page validation (`None`, `ExtractionOutcome.NOT_FOUND`). |
| **`data/cache.sqlite` (`url_cache`)** | **31 Teamtailor-associated rows** *(historical cache prior to re-enrichment; `serper_cache` holds `55` unique Teamtailor-linked URLs; `company_boards` holds `7` Teamtailor boards)* | `29` `scrape`, `2` synthetic `128b01af` `snippet` rows; `28` `description_ok=True`, `3` `description_ok=False` (including genuine active `theunlimited.teamtailor.com/jobs/8538757-data-analyst`!), `1` `requirements`, `1` `eligibility`, `5` `salary`, `0` `company_logo_url`. | Re-enriching `theunlimited` fixture now yields `description_ok=True` with full description, `requirements`, `eligibility`, and verified SVG `company_logo_url`. Expired `jobs.lunar.app` cached entry (`df512e48`) is now rejected (`NOT_FOUND`). *(Existing SQLite cache left untouched for historical baseline fidelity.)* |
| **Captured Real Fixtures (`tests/fixtures/real/teamtailor/`)** | **20 real HTML fixtures** *(`6` pre-existing + `14` captured in Step 35)* | Several multi-label `.na.` and locale-prefixed `/sv/jobs/` URLs failed `parse_ats_url`; custom domain `jobs.lunar.app` unverified; integration/support/people/expired HTTP `200`/`410` pages leaked into listings; `a3ea4593` failed `description_ok` under DOM path; no logo extraction. | **7 / 7 non-job & expired fixtures rejected** (`support.teamtailor.com` `0bbe167e`, `integrations` `128b01af`/`63a96b6e`/`7fc22ed2`, `people` profile `f0020ea3`, HTTP `410` `f6a01abc`, HTTP `200` expired `jobs.lunar.app` `df512e48` -> `ExtractionOutcome.NOT_FOUND`). **13 / 13 genuine active job fixtures accepted** (`100%`): `13/13` `title`, `13/13` `company` (`0` `"Unknown"`), `13/13` compact `location` + `raw_location`, `12/13` `work_model` (`41deef68` honestly `None`), `13/13` `employment_type`, `13/13` `description` (`description_ok=True`, CTA stripped), `13/13` `posted_at`, `13/13` `eligibility`, **`9/13` `requirements`**, **`5/5` disclosed `salary`**, **`12/13` `company_logo_url`** (`d93e9876` honestly `None` when absent). |

---

## 2. Key Architectural Changes

1. **Query Exclusion, URL Parsing & Safe Redirect / Custom Domain Resolution**:
   - Extended `ATS_EXCLUDED_SUBDOMAINS["teamtailor"]` in `src/project_files/query_builder.py` with `support.teamtailor.com` alongside `www.teamtailor.com`.
   - Updated `src/project_files/ats_url_parser.py` to parse multi-label tenant subdomains (e.g. `rooftop.na.teamtailor.com`), locale prefixes (`/sv/jobs/...`, `/pt-BR/jobs/...`), and slugless `/jobs/{id}` paths, while excluding `support.teamtailor.com` and non-job paths (`/people/`, `/integrations/`, `/articles/`). Added `parse_teamtailor_custom_domain_url`.
   - Added SSRF-safe public HTTPS validation (`src/project_files/url_safety.py`, re-exported via `ats_url_parser.is_safe_public_https_url`) and bounded manual redirect resolution (`SearchOrchestrator._resolve_teamtailor_candidate` in `src/project_files/search_pipeline.py`) for `google.com/url` redirects and custom-domain candidates requiring verified Teamtailor HTML evidence before acceptance. Passing prefetched HTML into `enrich_ats_page_result` avoids double-fetching.
   - Moved `company_board_registry.register_candidate` in `_search_ats_serper` strictly post-`_filter_by_relevance` so irrelevant discovered postings never register boards into `company_boards`, and extended `register_candidate` to preserve custom `board_url`.

2. **Genuine Job Validation & Structured Extraction (`ats_page_enricher.py`, `job_extraction_service.py`)**:
   - Rejected HTTP `404`/`410` and explicit closed banners (`_CLOSED_BANNER_PHRASES`, e.g. `"This position is no longer active"` on HTTP `200` `jobs.lunar.app`) even when lingering `JobPosting` JSON-LD remains in `<head>`, while preserving retryable `5xx`/`429`/WAF snippet fallbacks.
   - Added `_extract_teamtailor_dom` for multilingual `<dl>` metadata, `section.block-cover` `·`-delimited metadata, compact `_format_teamtailor_locations` (avoiding 200+ char multi-office dumps while keeping `raw_location`), and clean `div.prose` descriptions stripping trailing `"Already working at..."` CTAs.
   - Preserved canonical `teamtailor:{slug}:{job_id}` identity across slugless/locale/redirect variants so `GlobalDeduplicator` merges URL variants cleanly.
   - Note on observed source discrepancy (`0624475a` Keypath Education): JSON-LD `applicantLocationRequirements` declares `Australia` while DOM `<dl>`, `jobLocation.addressCountry=MY`, and prose explicitly require residing in `Malaysia` with full working rights -> `allowed_residence_countries=["Australia", "Malaysia"]`, `nigeria_eligible=False`.

3. **Shared Extractor Extensions (Requirements, Eligibility, Work Model, Salary)**:
   - `job_extraction_service.py`: enabled Teamtailor for `extract_requirements`, `extract_eligibility`, and `raw_location` preservation; added 1:1 curly apostrophe normalization, bold ATX headings (`#### **What Makes You a Great Fit:**`), `#`..`######`, and trailing ellipsis handling (`You need to have...`).
   - `eligibility_extractor.py`: added missing country names/ISO codes (`Malaysia`, `Bulgaria`, `Thailand`, `Argentina`, `Malta`, `Denmark`, `Estonia`, `Lithuania`, etc.), `_NON_COUNTRY_REGIONS` guard (`EMEA`/`EU` never become `physical_location_country`), `_WORK_ANYWHERE_SCOPED_RE` guard for regional WFA, `"residing in"` residence extraction, visa sponsorship (`offers visa sponsorship`), and foreign hybrid attendance (`worked from our ... office`).
   - `work_model.py` & `field_normalizer.py`: added Spanish/Swedish/French work-model & employment-type terms (`Híbrido`, `Télétravail`, `På plats`, `Distans`, `Tiempo completo`, `Heltid`, `Temps plein`, `Prácticas`).
   - `salary_parser.py`: added `/año`, European thousands-dot normalization (preserving decimals like `52.50` / `1.5m`), inline pre-hyphen currency (`curr_min_suffix`), period-delimited bold labels (`**Gross salary.** 1160 EUR/month`), and same-line `label_context` period fallback (`Gross monthly salary range:`).

4. **Company Logo Extraction Architecture & Square UI**:
   - Added `src/project_files/logo_extractor.py` (`LogoResult`, SSRF-safe public `https://` validator rejecting private/loopback/link-local IPs, Teamtailor-only gate returning empty `LogoResult` for other providers in Step 35) extracting from Teamtailor JSON-LD `hiringOrganization.logo`, header brand `<img>`, and `og:image` fallback.
   - Propagated `company_logo_url`, `company_logo_source`, `company_logo_verified` across `models.py`, `confidence_policy.py` (`CanonicalJobField.COMPANY_LOGO`), `job_extraction_service.py`, `canonical_job_adapter.py`, `deduplicator.py` (preserving higher-priority verified logos against unverified overwrites), `company_board_registry.py` (`company_logo_*` schema columns + idempotent `ALTER TABLE` migration + `get_board_logo` + `mark_board_logo_broken`), and `src/api/allowlist.py` (`company_logo_url` user-visible; provenance admin-only).
   - Updated frontend (`frontend/src/types.ts`, `ResultsTable.tsx`, `ResultsCards.tsx`, `DetailSheet.tsx`, and new [`CompanyMark.tsx`](frontend/src/components/CompanyMark.tsx)) to render square `--radius: 0` bordered `#FAF8F5` logo containers (`size-4` mobile, `size-7` table, `size-9` detail sheet) with `object-contain` and zero-flash `onError` monogram fallback.

---

## 3. Recommended Next Provider (Provider 4)

Based on observed database footprints in `data/cache.sqlite`:
- **`url_cache`**: `lever` (`217` rows — largest cached provider corpus in the database), `smartrecruiters` (`87`), `greenhouse` (`58`), `workday` (`45`), `ashby` (`40`), `teamtailor` (`31`), `workable` (`30`).
- **`company_boards`**: `ashby` (`21`), `greenhouse` (`18`), `smartrecruiters` (`13`), `lever` (`10`), `workable` (`9`), `teamtailor` (`7`).

**Recommendation**: **Lever** (`217` cached postings, `10` registered boards) as **Provider 4**, followed by **Greenhouse** (`58` cached postings, `18` registered boards). Both already use clean public JSON APIs and will yield immediate leverage from unified eligibility, salary, requirements, and company-logo extraction.

---

## 4. Verification Gate Results

- **Git & Fixture Integrity**:
  - `git diff --check`: passed (`0` whitespace errors).
  - `git diff --name-only tests/fixtures/real`: empty (`0` modifications to existing real fixtures).
- **Frontend Verification**:
  - `npm --prefix frontend run lint` (`oxlint`): `0` errors (`3` pre-existing shadcn fast-refresh export warnings in `toggle.tsx`, `button.tsx`, `badge.tsx`; `0` warnings in Step 35 files).
  - `npm --prefix frontend run test` (`vitest`): **`17` test files, `113` tests passed**.
  - `npm --prefix frontend run build` (`tsc -b && vite build`): passed.
  - `node scripts/lint_css_cascade.js`: passed.
- **Backend Verification**:
  - `.\venv\Scripts\python.exe -m pytest -q`: **`798` passed, `0` failed, `5` warnings**.
- **Verification Script & Playwright E2E**:
  - `.\scripts\verify.ps1`: executed with venv Python first in `PATH` (**`8 passed, 0 failed, 0 skipped`** of `8` checks, including full Playwright E2E).
  - Playwright E2E suite after final merge-gate `runViewTransition` fix (`frontend/src/lib/viewTransition.ts`): **`39 passed (of 39)`** with `--workers=2`, **`39 passed (of 39)`** with `--workers=1`, **`6 passed (of 6)`** repeated standalone (`--repeat-each=6`), and **`1 passed (of 1)`** standalone Step 35 (`CompanyMark` SVG logo load, `404` `onError` monogram fallback, non-Teamtailor monogram behavior, square `0px` `border-radius`, mobile `390x844` layout, dark mode, and Axe WCAG 2.0 A/AA scan).
  - Production SSRF client-wiring audit confirmed `src/api/main.py` instantiates `SearchOrchestrator()` without injecting `client`, so all production Teamtailor discovery redirects and page enrichments traverse `create_ssrf_safe_async_client` (`PublicPinningNetworkBackend`, `trust_env=False`, `follow_redirects=False`) and `fetch_public_https_with_validated_redirects`.
  - Visual screenshot & 5-viewport (`1920`, `1440`, `1024`, `768`, `390`) check confirmed `overflow: false` across all 5 viewports and crisp `#FAF8F5` square logo contrast in both light and dark `DetailSheet`.
