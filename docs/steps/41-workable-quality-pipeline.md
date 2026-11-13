# Step 41: Workable Quality Pipeline

**Branch:** `step/41-workable-quality-pipeline`
**Base:** `main` (`ffacf667e0ab0a50ad85c25dc50db4ed8f16839e`, Step 39 Ashby Quality Pipeline)
**Date:** 2026-11-13
**Status:** Feature branch verified and pushed to `origin/step/41-workable-quality-pipeline` (PR opened / not merged; `main` untouched)
**Serper Budget Spent:** `0` credits

---

## Reconciled Inventory & Verified Baseline (Step 40)

### 1. Serper URL Inventory Reconciliation (`serper_cache`)

- **`64`** distinct Workable organic URLs in `serper_cache`, reconciling to **`60`** unique genuine postings across **`54`** company slugs:
  - **`49`** initially parsed URLs
  - **`15`** `/apply` (and `/apply/`) URLs that previously failed parsing, of which **`4`** duplicated already-parsed job IDs and **`11`** were net-new postings (`49 + 11 = 60` unique genuine postings).

### 2. Operational Cache Baseline (`data/cache.sqlite` Before Step 41)

Across **`30`** genuine Workable `url_cache` rows across **`28`** unique company slugs (excluding `1` synthetic `example.com` row), **`9`** Workable `company_boards` rows (`monitoring_capability='provisional'`, `0` checked, `0` verified logos), and **`0`** `monitored_jobs`:

- Clean canonical URLs: **`13 / 30`** (`16 / 30` trailing slashes, `1 / 30` tracking query)
- Chrome-free descriptions (no `## Apply` / `Powered by Workable`): **`0 / 30`** (`30 / 30` leaked Markdown chrome)
- `requirements`: **`0 / 30`**
- `eligibility`: **`0 / 30`**
- `raw_location`: **`0 / 30`**
- `salary` present: **`4 / 30`** (`3 / 30` with `currency`, `0 / 30` with `period`)
- `employment_type`: **`26 / 30`**
- `company_logo_verified`: **`0 / 30`**
- `apply_url` distinct from canonical `source_url`: **`0 / 30`** (`30 / 30` equal to `source_url`)

---

## Observed Before / After Benchmark (`data/cache.sqlite` Operational Cache)

Before running live zero-Serper repair, a read-only backup of `data/cache.sqlite` was saved outside the repository (`cache.sqlite.bak-pre-workable-repair`).

### Zero-Serper Repair Execution (`python -m src.project_files.workable_cache_repair`)

| Metric | Dry Run (`--dry-run`) | Live Pass 1 | Live Pass 2 (Idempotency) |
|---|---:|---:|---:|
| `total_urls` | `30` | `30` | `30` |
| `unique_slugs` | `28` | `28` | `0` |
| `repaired_from_v2_api` | `28` | `28` | `0` |
| `canonicalized_urls` (alias re-keyed) | `16` | `16` | `0` |
| `boards_reconciled` | `9` | `9` | `0` |
| `boards_promoted` (`provisional -> supported`) | `0` | `9` | `0` |
| `boards_identity_enriched` | `23` | `23` | `0` |
| `expired_or_unavailable` (HTTP 404 preserved) | `2` | `2` | `0` |
| `skipped_already_repaired` | `0` | `0` | `30` |
| `skipped_synthetic` | `0` | `0` | `0` |
| `transient_errors` | `0` | `0` | `0` |
| `serper_calls_used` | `0` | `0` | `0` |

### Field Coverage Across `30` Genuine `url_cache` Postings & `company_boards`

| Field | Before Step 41 | After Step 41 Live Repair |
|---|---:|---:|
| Chrome-free `description` (`description_ok=True`) | `0 / 30` (`30` with chrome) | **`28 / 30`** (`28 / 28` live jobs; `2` historical 404 rows preserved) |
| `requirements` | `0 / 30` | **`25 / 30`** (`25 / 28` live jobs) |
| `eligibility` | `0 / 30` | **`28 / 30`** (`28 / 28` live jobs) |
| `raw_location` preserved (where multi-location/distinct) | `0 / 30` | **`6 / 30`** |
| `salary` present | `4 / 30` | **`7 / 30`** |
| `salary.currency` present | `3 / 30` (missing INR on `learnrush`) | **`7 / 30`** (`100%` of extracted salaries incl. `INR` & `JOD`) |
| `salary.period` present | `0 / 30` | **`6 / 30`** |
| `company_logo_url` & `company_logo_verified` | `0 / 30` | **`21 / 30`** (`7` accounts return `logo: null`) |
| Distinct `/apply` `apply_url` (`apply_url != source_url`) | `0 / 30` | **`28 / 30`** (`28 / 28` live jobs) |
| Canonical URL keys (no trailing `/` or query params) | `13 / 30` | **`29 / 30`** (`28 / 28` live jobs; `1` historical 404 row preserved) |
| `company_boards` (Workable) | `9` (`0` `supported`, `0` checked, `0` logos) | **`29`** (`29` `supported`, `23` verified logos) |
| `workable_repair_state` | — | **`46`** state rows (`44` `repaired` incl. 14 aliases, `2` `unavailable_404`) |

---

## Key Architectural & Quality Changes Implemented

1. **URL Parsing, Canonicalization & Board-Root Registration (`src/project_files/ats_url_parser.py`, `url_normalizer.py`, `search_pipeline.py`)**:
   - Extended `_WORKABLE_SUBDOMAIN` and `_WORKABLE_APPLY` to accept optional `/apply` suffixes (`apply.workable.com/{slug}/j/{id}/apply` and `{slug}.workable.com/jobs/{id}/apply`), guarded with `is_valid_board_slug`, `_WORKABLE_NON_BOARD_PATHS`, and `_WORKABLE_RESERVED_SUBDOMAINS`.
   - Added `parse_workable_board_root_url` and wired it into `_enrich_ats_item` so board-root URLs (`apply.workable.com/{slug}`, `{slug}.workable.com`) register Workable candidates in `company_board_registry`.
   - Registered `"workable"` in `_PROVIDER_RULES` and canonicalized `{slug}.workable.com/jobs/{id}`, `http://`, trailing `/`, and `/apply` onto `https://apply.workable.com/{slug}/j/{id}`.

2. **Workable `api/v2` Primary Client & Shared Conversion (`src/project_files/ats_api_client.py`)**:
   - Added single shared deterministic converter `workable_payload_to_raw(...)` plus `workable_widget_job_to_raw(...)` and clean `workable_markdown_to_raw(...)` fallback (stripping `# Title`, metadata blockquote, `## Apply`, and `Powered by Workable` while preserving authentic description sections, requirements, benefits, and `/apply` CTA URL).
   - Upgraded `WorkableClient` to fetch `GET https://apply.workable.com/api/v2/accounts/{slug}/jobs/{job_id}` primarily, preserving structured primary/secondary locations (skipping `hidden: true` entries and guarding against top-level `state: "published"` false US-state collisions), `workplace` / `remote`, `department`, `employment_type`, `published_on`, authentic HTML/text sections, and `https://apply.workable.com/{slug}/j/{id}/apply`.

3. **Salary, Currency, Eligibility, Requirements & Logos (`src/project_files/salary_parser.py`, `eligibility_extractor.py`, `job_extraction_service.py`, `logo_extractor.py`)**:
   - Extended `ISO_4217_CURRENCIES` with `"JOD"`, `"KWD"`, `"BHD"`, `"OMR"`, `"QAR"` and `_CURR_SYMBOLS` / `_resolve_currency` with `₹ -> INR`, plus Workable structured `salary_from`/`salary_to`/`salary_currency_iso_code`/`salary_frequency`, bulleted explicit currency+period fallback (`- $30/hr`), and Markdown-link stripping in salary extraction.
   - Added Jordan/Middle East/African country aliases (`Jordan`/`JO`, `Japan`/`JP`, `Kenya`/`KE`, `South Africa`/`ZA`, etc.) and structured `raw_fields["location"]` country fallback in `eligibility_extractor.py`; opted `"workable"` into requirements and eligibility extraction in `JobExtractionService`.
   - Rejected Workable default `open_graph_logo` / `facebook-preview` templates in `_REJECTED_LOGO_PATTERNS`, implemented `_extract_workable_logo`, and added 7-day cached/coalesced `enrich_workable_board_identity` (`GET /api/v1/accounts/{slug}`).

4. **Independent Monitoring, Direct Board Routing & Zero-Serper Repair (`src/project_files/board_adapters.py`, `board_monitor.py`, `company_board_registry.py`, `direct_board_router.py`, `workable_cache_repair.py`)**:
   - Promoted `"workable"` to `MONITORABLE_PROVIDERS`; implemented `WorkableBoardAdapter` (`GET /api/v1/widget/accounts/{slug}` + SHA-256 fingerprint diff + bounded rotating `api/v2` detail revalidation respecting `detail_revalidate_ttl_seconds` & `max_revalidations_per_poll` + `preserve_last_checked_at` for unrotated active jobs + transient error preservation).
   - Added `probe_workable_board` in `direct_board_router.py` sharing `hydrate_workable_board_jobs`.
   - Implemented `src/project_files/workable_cache_repair.py` with `--dry-run`, `--force`, `v41` checkpointing, board promotion/reconciliation, conservative alias cleanup, and 404 historical preservation.

---

## Verification Results

All checks passed after the final code, fixture, and documentation edits:

- **Targeted Workable & Monitoring Suite (`pytest tests/test_workable_pipeline.py tests/test_board_monitor.py tests/test_direct_board_router.py tests/test_company_board_registry.py tests/test_platform_reconciliation.py -q`)**: Passed cleanly (17 tests in `tests/test_workable_pipeline.py` covering URL parsing/normalization, `api/v2` + `.md` fallback, JOD/INR/USD salary parsing, requirements, eligibility, verified logos, monitoring lifecycle & rotating TTL refresh, direct board routing, and cache repair).
- **Real Fixture Corpus (`tests/fixtures/real/workable/`)**: Captured 18 real Workable API/HTML fixtures across 5 verified boards (`treq`, `verneek`, `mercari`, `learnrush`, `99brightminds`) plus `serper_urls_78.json`; left pre-existing `job_D94DBAF102.md` intact; updated `tests/test_real_api_fixtures.py` for Step 41's expected extraction improvements on `workable_D94DBAF102.json`.
- **Full Project Verification Suite (`.\scripts\verify.ps1`)**: **`8 passed, 0 failed, 0 skipped (of 8 checks)`**.
- **Full Python Test Suite (`python -m pytest -q`)**: **`928 passed, 4 warnings in 75.09s`**.
- **Frontend Unit Tests & Build**: `vitest` **`17 test files, 113 passed`**; `tsc -b && vite build` clean.
- **Full Playwright E2E Suite (`npx playwright test --reporter=line`)**: **`43 passed (1.4m)`**, including `Step 41: Workable square logos, JOD/INR/USD salaries, work models, eligibility, /apply links, and 5-viewport responsiveness` across `1920x1080`, `1440x900`, `1024x768`, `768x1024`, and `390x844` with `0px` square `CompanyMark` geometry, 0 horizontal overflow, 0 console/page errors, and 0 critical/serious Axe WCAG violations.
- **Work Model Evaluation (`python scripts/eval_work_model.py`)**: Ran cleanly across `49` valid labelled rows with zero regressions.
