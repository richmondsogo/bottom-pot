# Step 06: Platform Filter Wiring, Cache Key Scoping, and HotNigerianJobs Roundup Unbundling

**Step Branch**: `step/06-platform-filter-and-hnj-scraper-fix`  
**Base Branch**: `main` (`8d1878140d17b7cf6f36c84b3f98c716bc7c33e5`)  
**Primary Branch**: `main`  

---

## Objective

Resolve subtle frontend/backend integration bugs and overhaul `HotNigerianJobsScraper` to accurately unbundle multi-position recruitment roundups, eliminate duplicate card extraction, extract honest company/location/date fields with full ADR 0001 and ADR 0002 provenance, and wire `selectedPlatforms` end-to-end—all with **zero changes to how the frontend looks**.

## Scope

### Included
- **HotNigerianJobs Scraper Overhaul (`src/project_files/nigerian_scrapers.py`, `src/project_files/field_normalizer.py`)**:
  - Fix 2x duplicate extraction caused by `.mycase, div[class*='job']` matching both `<div class="mycase">` and its nested `<div class="jobheader">` child.
  - Unbundle multi-position company recruitment roundups (both homepage summary cards like `"Company is recruiting ... to fill the following positions in <Location>: Role 1, Role 2, and Role 3"` and roundup detail pages with numbered `1.) <Role>` entries and `Click Here To View Details` links).
  - Normalize malformed `https://https://` URLs found in HotNigerianJobs detail links.
  - Extract real `company` and `location` from `<Role> at <Company>`, `<Company> is recruiting to fill the position of: <Role>. The position is located in <Location>`, or roundup headers; return `None` for unknown location instead of falsifying `params.location` (ADR 0001).
  - Preserve ADR 0002 source ladder ordering (`workplace_type` -> `location` -> `title` -> `description`) and populate `work_model_source` and `work_model_evidence` on `JobListing`.
  - Parse ordinal date strings in `<span class="semibio">` (e.g., `Posted on Thu 22nd Oct, 2026 -`).
  - Route searches across both the category/field feeds (`/field/273/` for ICT/Software/Data, `/field/269/` when `remote=True`) and the main feed, filtering out promotional ads and non-matching roles when query keywords are specified.
- **Platform Selection & Cache Key Wiring (`frontend/src/App.tsx`, `src/project_files/search_pipeline.py`)**:
  - Pass `platforms` query parameter from `executeSearch` in `frontend/src/App.tsx` when a user selects a subset of `ALL_PLATFORMS`, and avoid duplicate `switchScreen('delivery')` invocations after SSE `done`.
  - Include `platforms` in `_cache_key(params, platforms)` in `src/project_files/search_pipeline.py` and respect platform selection for Nigerian scrapers when `platforms` is explicitly scoped.
- **Real Fixtures & Tests (`tests/fixtures/real/hotnigerianjobs/`, `tests/test_scrapers_and_clients.py`, `tests/test_deduplicator.py`, `tests/test_contracts_and_observability.py`)**:
  - Capture 4 real HTML fixtures from HotNigerianJobs via `scripts/capture_fixtures.py` and add unit tests covering single-role extraction, multi-position roundup unbundling, `https://https://` URL normalization, ordinal date parsing, ad rejection, platform-scoped Nigerian scrapers, and platform-scoped cache keys.
- **Documentation & Step Provenance Sync (`DESIGN.md`, `README.md`, `docs/steps/05-emil-ui-polish.md`)**:
  - Align `DESIGN.md` font stack reference (`Geist Variable`), `README.md` `work_model: null` rendering description (empty cell per ADR 0019), and record PR #9 merge provenance in `docs/steps/05-emil-ui-polish.md`.

### Excluded
- Any change to frontend visual appearance, CSS, layout, typography, colors, or component structure.

## Plan

1. Capture real HTML fixtures from `hotnigerianjobs.com` into `tests/fixtures/real/hotnigerianjobs/` via `scripts/capture_fixtures.py`.
2. Update `parse_datetime` in `src/project_files/field_normalizer.py` to handle ordinal day suffixes (`1st`, `2nd`, `3rd`, `21st`) and weekday prefixes (`Posted on Thu 22nd Oct, 2026 -`).
3. Refactor `HotNigerianJobsScraper` in `src/project_files/nigerian_scrapers.py` to:
   - Select `.mycase` cards cleanly without nested `.jobheader` duplication.
   - Skip non-job promotional academy ads.
   - Unbundle multi-position roundup cards and roundup detail pages into distinct `JobListing` records with deterministic IDs, real company names, real locations (`None` when absent), ADR 0002 work model provenance (`work_model_source` and `work_model_evidence`), and normalized URLs.
   - Fetch relevant field feeds (`/field/273/`, `/field/269/`) alongside the search feed and filter by query relevance.
4. Update `_cache_key` and `SearchOrchestrator.run` in `src/project_files/search_pipeline.py` to scope cache keys and Nigerian scrapers by `platforms`.
5. Update `executeSearch` in `frontend/src/App.tsx` to send `platforms` when a subset of `ALL_PLATFORMS` is selected, and rebuild `frontend/dist`.
6. Sync minor documentation drift in `DESIGN.md` and `README.md`.
7. Add comprehensive unit tests, run `pytest`, `python scripts/eval_work_model.py results.json`, `.\scripts\verify.ps1`, and two-axis `code-review`, then open PR and merge into `main`.

## Implementation

- **HotNigerianJobs Scraper (`src/project_files/nigerian_scrapers.py`, `src/project_files/field_normalizer.py`, `src/project_files/work_model.py`)**:
  - Replaced `.mycase, div[class*='job'], article, .post` with `.mycase` (fallback `article, .post`) so `<div class="jobheader">` inside `<div class="mycase">` is never matched as a second duplicate job card.
  - Added `_is_hnj_promotional_ad` to filter out non-job training/bootcamp advertisements (such as Moat Academy's `"Apply Before November 2, 2026 and Become a Software Developer"`).
  - Implemented two-mode multi-position roundup unbundling:
    1. **Detail page numbered blocks**: Parses `1.) <Role>`, `Location: <Location>`, and `Click Here To View Details` links inside `.mycase4`, normalizing malformed `https://https://` URLs via `_normalize_hnj_url`.
    2. **Homepage summary cards**: Parses `"<Company> is recruiting ... to fill the following [remote] positions [in <Location>]: <Role List>"` via `_split_hnj_roundup_roles`, splitting semicolon- or comma/conjunction-delimited role lists into distinct `JobListing` objects with unique deterministic IDs (`<url>#<role-slug>`).
  - Added `_extract_hnj_company_and_title` and `_extract_hnj_location` to extract real employer names and locations, returning `None` when no location is stated instead of falsifying `params.location` (ADR 0001).
  - Preserved strict ADR 0002 work model source ladder ordering (`workplace_type` -> `location` -> `title` -> `description`) and recorded `work_model_source` and `work_model_evidence` on every listing; extended `_TITLE_TAG` in `src/project_files/work_model.py` to recognize `(Fully Remote)` / `(100% Remote)` parenthetical title tags.
  - Extended `_extract_card_metadata` to select `span.semibio` dates and Naira `Salary: N...` strings, and updated `parse_datetime` in `src/project_files/field_normalizer.py` to strip weekday prefixes and ordinal suffixes (`1st`, `2nd`, `3rd`, `22nd`).
  - Updated `HotNigerianJobsScraper.search` to also query `/field/273/` (Computer / ICT / AI / Software / Data Analytics) and `/field/269/` (Remote) when the unfiltered homepage is returned for `/?s=`.
- **Platform Selection & Cache Key Scoping (`frontend/src/App.tsx`, `src/project_files/search_pipeline.py`)**:
  - Wired `queryParams.set('platforms', selectedPlatforms.join(','))` in `App.tsx` when a subset of `ALL_PLATFORMS` is selected, and prevented duplicate `switchScreen('delivery')` calls after `done`.
  - Updated `_cache_key(params, platforms)` in `src/project_files/search_pipeline.py` to include normalized `platforms` when provided while keeping `platforms=None` hashes identical for backward compatibility.
  - Scoped `NIGERIAN_SCRAPERS` execution in `SearchOrchestrator.run` when `platforms` is explicitly passed.

## Discoveries

- `https://www.hotnigerianjobs.com/?s=<query>` ignores the query parameter server-side and returns the unfiltered homepage feed (`<title>Search for jobs & find your dream job | HotNigerianJobs</title>`), where company recruitments are posted as bundled multi-position roundups. Meanwhile, `/field/273/` (ICT/Software/AI) and `/field/269/` (Remote) publish already-unbundled single-position cards. Combining roundup unbundling + query token filtering on the homepage with `/field/273/` and `/field/269/` yields clean, relevant, non-duplicated single-role listings.
- Several detail links inside HotNigerianJobs roundup posts contain a doubled `https://https://` prefix typo in their `href` attributes, which `_normalize_hnj_url` now normalizes automatically.

## Two-Axis Code Review (`code-review` Skill)

- **Standards Axis**:
  - Identified that `work_model_source` and `work_model_evidence` should be populated on `HotNigerianJobsScraper` `JobListing` objects and that title/prose work model signals should flow through `title` (Tier 5) and `description` (Tier 6) rather than `workplace_type` (Tier 1) per ADR 0002, plus URL inclusion in scraper warning logs. All findings were resolved and verified with unit test assertions.
- **Spec Axis**:
  - Verified all requirements in Step 06 are implemented with zero visual frontend changes; aligned the Scope file list in this step document.

## Verification

- **Unified Verification (`.\scripts\verify.ps1`)**: **8 / 8 checks passed**
  - Git available: `OK`
  - No tracked secrets: `OK`
  - CSS Cascade Lint (`node scripts/lint_css_cascade.js`): `OK`
  - Frontend Linting (`oxlint`): `OK`
  - Frontend Unit Tests (`vitest`): `OK` (25/25 passing)
  - Frontend Typecheck & Production Build (`tsc + vite`): `OK`
  - Python Unit Tests (`pytest`): `OK` (299/299 passing)
  - Playwright E2E Suite (`npx playwright test`): `OK` (14/14 passing)
- **Work Model Evaluation (`python scripts/eval_work_model.py results.json`)**: `OK`
- **Serper Live Searches**: `0`
