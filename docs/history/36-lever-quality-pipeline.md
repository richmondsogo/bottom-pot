# Step 36: Lever Quality Pipeline

## Overview
- **Goal**:
  1. Remediate Lever discovery, URL parsing/canonicalisation (`/apply` and board-root handling), unified extraction across `LeverClient`, `LeverBoardAdapter`, `BoardMonitor`, and `probe_lever_board`, completeness-preserving persistence (`CacheStore` / `BoardMonitor`), structured `lists[]` + fallback requirements, geographic & eligibility extraction, salary parsing, multi-location preservation (`categories.allLocations`), and bounded Lever board identity/logo enrichment.
  2. Keep `tests/fixtures/real/lever/job_caadac8e.json` and all pre-existing real fixtures untouched while establishing a genuine reproducible Lever fixture corpus (`21` new captured files + `serper_urls_104.json`).
- **Branch**: `step/36-lever-quality-pipeline`
- **Base**: Local `main` (`8cccc60`)
- **Serper Budget Spent**: `0` Serper credits spent during Step 36 implementation or offline verification.
- **Provenance**:
  - **Initial Implementation Commit**: `a6bfa8b`
  - **Final Acceptance Correction Commit**: `df46a1b`
  - **Merge Commit**: `3716b3d` (`--no-ff` into `main`; parent 1 `8cccc60`, parent 2 `df46a1b`)
  - **Publication Status**: Merged to `main` via `--no-ff` and included in the subsequent push of Steps 33–37 to `origin/main`.

---

## 1. Benchmark Summary: Observed Baseline vs. Post-Change Results

| Data Store / Source | Denominator | Pre-Change Baseline | Post-Change (`step/36-lever-quality-pipeline`) |
|---|---|---|---|
| **`data/cache.sqlite` (`url_cache`)** | **`217` cached Lever rows** (`37` unique lowercased slugs, `217` `(slug, job_id)` pairs, `217` `api`, `0` `/apply` URLs, `10` Lever `company_boards`) | `214/217` `description` (`description_quality=True`), `0/217` `requirements`, `48/217` `salary`, `0/217` `eligibility`, `0/217` `company_logo_url`, `217/217` `work_model`. | Text-only re-evaluation across the `217` cached descriptions/locations/work models: `51/217` `requirements`, `109/217` `eligibility` populated (`0` `, CA -> Canada` errors, `0` false-positive `nigeria_eligible=True`, `20` `nigeria_eligible=False`), `52/217` `salary`. *(Existing `data/cache.sqlite` left untouched.)* |
| **Captured Serper URLs (`serper_urls_104.json`)** | **`104` unique Lever URLs** | `/apply` URLs dropped or failed deduplication with canonical URLs; board-root URLs silently dropped without board registration. | **`92`** parsed job URLs (including all **`13`** `/apply` URLs canonicalised to `https://jobs.lever.co/{slug}/{uuid}`, deduplicating to **`89`** unique match keys), **`2`** board-root URLs (`palantir`) routed to `company_board_registry.register_candidate`, and **`10`** invalid non-UUID URLs (`company0/2000`–`company9/2009`) rejected. |
| **Captured API Corpus (`tests/fixtures/real/lever/`)** | **`16` real API JSON fixtures** (`job_caadac8e.json` + `15` `api_*.json`) | Duplicated `opening` (Palantir), empty `description` on lists-only (Spotify) and HTML-only (`The-Battery-Network`), dropped `additional` (Extreme Networks), blank-line list gaps, `0/16` requirements, `0/16` eligibility, missed salaries (Penumbra, Extreme Networks, Mendix, Strada, Jobgether `CA$`). | **`16/16`** `description_quality=True` (`0/16` consecutive-bullet blank-line gaps), **`16/16`** `requirements` populated, **`16/16`** `eligibility` populated (verified `Remote - Latam` `allowed_residence=['LATAM']`, `global_remote=None`, `nigeria_eligible=False` on Muttdata; `United States` on `, CA` cities), **`9/16`** disclosed salaries accurately extracted (`api_fad6ad02.json` Jobgether Brazil per-diem rejected as `None`), `London; Stockholm` multi-location preserved on Spotify (`api_9f66e598.json`). |
| **Captured HTML & Board Corpus (`tests/fixtures/real/lever/`)** | **`5` real HTML fixtures** (`board_tpgsi.html`, `board_zoox.html`, `html_1cb2b7f2.html`, `html_42be630d.html`, `html_9176aa65.html`) | Lever logo extraction disabled (`url=None`); HTML fallback missed logo and Penumbra starting salary phrasing. | **`3/5`** employer logos verified (`board_tpgsi.html`, `html_1cb2b7f2.html`, `html_42be630d.html`); **`2/5`** (`board_zoox.html`, `html_9176aa65.html`) cleanly return `url=None, verified=False` (rejecting `/img/lever-logo-refresh.svg` & `og:image`). HTML fallback (`html_42be630d.html`) extracts Penumbra company name, verified logo, and `$95,000–$145,000 USD` salary. |

---

## 2. Key Architectural Changes

1. **URL Discovery, Parsing & Canonicalisation (`ats_url_parser.py`, `url_normalizer.py`, `search_pipeline.py`)**:
   - Extended `_LEVER` and `normalize_job_url` to accept optional `/apply` and `/apply/` suffixes, canonicalising full-UUID `/apply` URLs to `https://jobs.lever.co/{company_slug}/{job_uuid}` while preserving slug casing and keeping `applyUrl` separately in extracted payloads.
   - Added `parse_lever_board_root_url` and wired Lever board-root URLs in `_enrich_ats_item` to register candidate boards via `company_board_registry.register_candidate` without emitting synthetic job listings.

2. **Unified Extraction, Clean Markdown & Completeness Persistence (`ats_api_client.py`, `board_adapters.py`, `direct_board_router.py`, `field_normalizer.py`, `cache_store.py`, `board_monitor.py`)**:
   - Created shared `lever_payload_to_raw(...)` (plus `_build_lever_description`, `_lever_normalize_overlap_text`, `_extract_lever_locations`) and unified `LeverClient`, `LeverBoardAdapter`, `BoardMonitor`, and `probe_lever_board` on it:
     - Deduplicates `opening` when it overlaps the head of `description` / `descriptionPlain`.
     - Prefers HTML when structured tags exist and falls back cleanly across `lists[]` (preserving `<H3>` headings) and `additional` / `additionalPlain`.
     - Preserves multi-location `categories.allLocations` joined deterministically with `; `.
   - Eliminated consecutive list-item blank-line inflation in `field_normalizer.to_markdown` (handling both HTML `<ul>`/`<ol>` whitespace siblings and Lever `<div>• ...</div>` blocks).
   - Updated `CacheStore` and `BoardMonitor` with `_merge_preserving_completeness(incoming, existing)` and normalized-URL lookup so lighter monitor snapshots never overwrite verified logos, salary, requirements, eligibility, or richer descriptions.

3. **Requirements, Geographic Eligibility & Salary (`job_extraction_service.py`, `eligibility_extractor.py`, `salary_parser.py`)**:
   - Added `_extract_lever_lists_requirements` prioritizing qualification/requirement sections from `lists[]` (excluding responsibilities, benefits, perks, and working conditions) with prose fallback via `extract_requirements`, and enabled `extract_eligibility` for `provider == "lever"`.
   - Enhanced `eligibility_extractor.py`: mapped `"PH"` and additional ISO codes; added `_US_STATE_CODES` vs `_CANADIAN_PROVINCE_TOKENS` disambiguation so `<City>, CA` resolves to `United States`; added `_is_perks_or_culture_context` to prevent perks/culture `"work from anywhere"` slogans from triggering `global_remote_explicit=True`; parsed Lever `categories.commitment` geo tags (`Remote - Latam` -> `allowed_residence=['LATAM']`, `nigeria_eligible=False`).
   - Enhanced `salary_parser.py`: structured `salaryRange` preferred (zero/zero rejected) plus `salaryDescriptionPlain`/`salaryDescription` fallback; added BRL (`R$`), `Starting Base Salary`, `Pay:`, `Annual base salary`, upper-bound-only (`up to USD 170000` -> `minimum=None, maximum=170000`), unknown-period preservation (`$125,300 to $250,600` -> `period=None`), two-tier labelled rates (`$22.75/hour ...; $25/hour ...`), and per-diem meal/home-office allowance exclusion.

4. **Authoritative Identity & Verified Lever Logo Enrichment (`logo_extractor.py`, `company_board_registry.py`, `ats_api_client.py`, `job_extraction_service.py`, `board_adapters.py`, `direct_board_router.py`)**:
   - Enabled `"lever"` in `extract_company_logo_for_provider`: accepts JSON-LD `hiringOrganization.logo` (`verified=True`) and `a.main-header-logo img` (`lever_main_header_logo`, `verified=True`), while rejecting `/img/lever-logo-refresh.svg`, `jobs.lever.co/img/`, `og:image`, and `twitter:image`.
   - Added `company_logo_checked_at` SQLite column/migration and `set_board_identity` in `CompanyBoardRegistry` plus bounded async `enrich_lever_board_identity` with in-flight coalescing and 7-day negative caching (preserving verified logos against unverified overwrites).

---

## 3. Verification Results

*(Re-run cleanly after all final edits; see command outputs below.)*

- **Git & Fixture Integrity**:
  - `git diff --name-only tests/fixtures/real`: empty (`tests/fixtures/real/lever/job_caadac8e.json` and all pre-existing real fixtures untouched).
  - Intentional `tests/fixtures/golden/*.json` snapshots updated for crisp `\n- ` markdown lists (`7` files) and Step 36 Lever `requirements`/`eligibility` on `lever_caadac8e.json`, plus scoped `tests/test_company_logo.py` exclusion list (`"lever"` now opted in).
- **Playwright Browser Verification (Step 36 5-Viewport Test + Full Suite)**:
  - Verified `Step 36: Lever logos, authoritative names, clean markdown lists, eligibility, and 5-viewport responsiveness` across `1920x1080`, `1440x900`, `1024x768`, `768x1024`, and `390x844`: authoritative employer name (`Turning Point Global Solutions`), verified logo `<img>` load, `Zoox` square monogram fallback, `0px` `border-radius` `CompanyMark`, crisp `<ul><li>` list rendering in `DetailSheet` (`4` list items), zero horizontal overflow at all 5 viewports, zero console/page errors, and zero critical/serious Axe WCAG 2.0 A/AA violations.
- **Full Suite (`.\scripts\verify.ps1`)**:
  - Executed cleanly after merge (`3716b3d`): Backend `847 passed`, Vitest `113 passed`, Playwright `40 passed`, Full verification `8/8` (`pytest`, `oxlint`, `vitest`, `tsc + vite build`, CSS cascade lint, git secrets check, and full Playwright E2E suite).

---

## 4. Acceptance Audit Follow-Up (Cache Repair, Completeness Semantics & Identity Persistence)

1. **Completeness vs. Legitimate Edits (`src/project_files/cache_store.py`, `src/project_files/board_monitor.py`)**:
   - Upgraded `CacheStore._merge_preserving_completeness(incoming, existing, *, preserve_omitted_optional_fields=False)` and added `_is_plain_subset_of_richer_description` so degraded payloads (snippet downgrades, non-empty `extraction_outcome`, empty/`not description_ok`, or `descriptionPlain`-only prefix subsets of structured descriptions) never clobber richer content, while authoritative full updates allow shorter rewritten descriptions, salary/location/work-model corrections, and genuine salary/requirements deletion.
   - `BoardMonitor` calls `_merge_preserving_completeness(..., preserve_omitted_optional_fields=True)` so partial board feeds keep omitted optional fields without blocking legitimate edits. Always preserves verified company logos.
2. **Board Identity & Fingerprint Versioning (`src/project_files/company_board_registry.py`, `src/project_files/board_adapters.py`)**:
   - Allowed `CompanyBoardRegistry.set_board_identity` to update `company_name` when an authoritative non-empty name legitimately changes to a shorter value.
   - Versioned `LeverBoardAdapter.check_board` content fingerprints (`v36:` including `lists[]`, `additional`, and `salaryRange`) so pre-Step-36 board fingerprints (`spotify`, `extremenetworks`) invalidate cleanly on the next monitor poll.
3. **Bounded Zero-Serper Cache Repair (`src/project_files/lever_cache_repair.py`)**:
   - Executed one-time repair across the exact `217` pre-Step-36 cached Lever `url_cache` rows (`37` unique slugs) + `161` Lever `monitored_jobs` using Lever public APIs only (`0` Serper calls made):
     - Descriptions populated on the `217`-record population: `214/217` → `217/217`; empty descriptions: `3` (`spotify/785989a6`, `spotify/a3c9129a`, `spotify/080868dd`) → `0`.
     - Structured markdown headings/bullets (`### ` or `\n- `): `77/217` → `212/217` (`153` records grew by >50 chars; `9` `404`-expired rows preserved historical descriptions untouched while `1` monitored `404` job was closed in `monitored_jobs`; `3` active Extreme Networks prose postings had no `lists[]` natively).
     - `url_cache` (same `217` population): `requirements` `0/217` → `181/217`, `salary` `48/217` → `56/217` (`58/219` total rows with 2 normalized keys), `eligibility` `0/217` → `208/217`, `company_logo_verified` `0/217` → `195/217`.
     - `monitored_jobs` (`161` Lever rows): `160` active (`reqs` `0` → `135`, `salary` `21` → `23`, `elig` `0` → `160`, `logo_verified` `0` → `160`) and `1` `404` job closed.
     - Verified idempotent restart (`lever_repair_state` skipping all `219` rows with `0` Serper calls and `0` updates on repeat run).
