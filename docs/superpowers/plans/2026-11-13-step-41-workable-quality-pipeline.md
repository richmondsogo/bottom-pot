# Step 41: Workable Quality Pipeline — Implementation Plan

**Goal:** Upgrade Workable end-to-end across URL parsing/canonicalization, structured GET API v2 ingestion, salary/currency/description/requirements/eligibility/location extraction, company identity & verified logo enrichment, direct board routing, independent board monitoring with bounded rotating detail refresh, zero-Serper cache repair, frontend Playwright E2E verification, and step documentation.

**Architecture:** Establish one shared pure mapping function `workable_payload_to_raw(...)` in `src/project_files/ats_api_client.py` used everywhere Workable job JSON enters the system (`WorkableClient`, `WorkableBoardAdapter`, `workable_cache_repair`). Migrate `WorkableClient` to `GET https://apply.workable.com/api/v2/accounts/{slug}/jobs/{job_id}` as authoritative primary source while keeping clean Markdown fallback for resilience and existing `.md` test fixtures. Add `enrich_workable_board_identity(...)` backed by `GET https://apply.workable.com/api/v1/accounts/{slug}` (7-day positive/negative SQLite caching + per-slug concurrency coalescing), reject `open_graph_logo` and `facebook-preview.png` traps in `logo_extractor.py`, promote `workable` to `MONITORABLE_PROVIDERS` via `WorkableBoardAdapter` (`api/v1/widget/accounts/{slug}` + bounded rotating detail refresh), wire `probe_workable_board` into `direct_board_router.py`, and execute zero-Serper idempotent repair (`src/project_files/workable_cache_repair.py`) with pre-repair SQLite backup.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, `httpx`, `BeautifulSoup4`, SQLite (`data/cache.sqlite`), `pytest` / `anyio`, React/TypeScript/Vite frontend (`lucide-react`, Tailwind v4, `0px` square design system), Playwright + `@axe-core/playwright`.

---

## Step 40 Verified Baseline (Preserved Denominators)

From read-only analysis of `data/cache.sqlite` prior to any Step 41 writes:
- `url_cache`: **30** genuine Workable cached postings across **28** unique slugs (`0/30` requirements, `0/30` eligibility, `0/30` company logo, `0/30` salary period, `4/30` salary with `learnrush` INR `currency=None` and `verneek` truncated `raw_text`, `26/30` employment_type, `30/30` `apply_url == source_url`, `16/30` trailing slash, `1/30` tracking query). Plus **1** synthetic `example.com` row excluded from genuine metrics.
- `serper_cache`: **64** unique Workable URLs -> **60** net unique genuine jobs across **54** slugs (**49** parsed posting URLs + **15** `/apply/` URLs currently unparsed with **4** overlapping keys).
- `company_boards`: **9** Workable rows (`candidate`, `monitoring_capability='provisional'`, `0` checked, `0` logos).
- `monitored_jobs`: **0** Workable rows.
- Live 5-board probe (`treq`, `verneek`, `mercari`, `learnrush`, `99brightminds`): `api/v1/accounts/{slug}` (200 on 5/5), `api/v1/widget/accounts/{slug}` (200 on 5/5), `api/v2/accounts/{slug}/jobs/{job_id}` (200 on 4 live jobs, 404 on closed `treq/D94DBAF102`). Genuine fixtures saved under `tests/fixtures/real/workable/`.

---

## Unit A — Workable URL Parsing, Canonicalization & Discovery

**Files:**
- Modify: `src/project_files/ats_url_parser.py`
- Modify: `src/project_files/url_normalizer.py`
- Modify: `src/project_files/search_pipeline.py`
- Test: `tests/test_ats_url_parser.py`, `tests/test_url_normalizer.py`, `tests/test_workable_pipeline.py`

### Tasks
1. **Failing tests first** in `tests/test_workable_pipeline.py` (and additions in `test_ats_url_parser.py`/`test_url_normalizer.py`):
   - Parse `apply.workable.com/{slug}/j/{job_id}`, `apply.workable.com/{slug}/j/{job_id}/`, `apply.workable.com/{slug}/j/{job_id}/apply`, `apply.workable.com/{slug}/j/{job_id}/apply/`, `{slug}.workable.com/jobs/{job_id}`, `{slug}.workable.com/jobs/{job_id}/apply` (if encountered) -> canonical `job_id = job_id.upper()` or preserved? Note: Workable shortcodes are uppercase hex-like strings (`D94DBAF102`), whereas numeric legacy IDs or mixed IDs may exist — preserve trimmed uppercase for hex/alnum? Wait: check existing cache & tests: `job_D94DBAF102`, `987654321`, `ABC123`, `DEF456`. Preserve `job_id.strip()` case-insensitively on comparison or normalize canonical URL case? Keep `job_id = m.group(2)` (or `.upper()`? Wait: existing `test_ats_url_parser.py:196` asserts `result.job_id == "ABC123"`, `DEF456` — existing tests already pass uppercase!). For canonical URL equality: `canonicalize_recognized_workable_url` should canonicalize `http://` -> `https://`, `{slug}.workable.com/jobs/{job_id}` -> `https://apply.workable.com/{slug}/j/{job_id}`, strip `/apply`, strip trailing `/`, and preserve slug lowercase (`slug.lower()`).
   - Reject reserved non-board paths on `apply.workable.com` (`j`, `api`, `jobs`, `widget`, `widgets`, `assets`, `static`, `images`, `cdn-cgi`, `apply`, `login`, `signup`, `careers`, `privacy`, `terms`) and reserved subdomains (`www`, `apply`, `api`, `app`, `help`, `support`, `blog`, `docs`, `resources`, `careers`, `status`, `workablehr`).
   - Reject bare `apply.workable.com/{slug}/apply` and `apply.workable.com/j/{job_id}` (Wait: `widget_v1` returns `https://apply.workable.com/j/A8DB68FCC3` WITHOUT `{slug}` in URL — `parse_ats_url` shouldn't guess a slug from `/j/{id}`, while `board_adapters` / `direct_board_router` already know `{slug}` and build `https://apply.workable.com/{slug}/j/{shortcode}`!).
   - Reject synthetic slugs/domains via `is_valid_board_slug("workable", ...)` and verify `parse_workable_board_root_url` accepts `https://apply.workable.com/{slug}`, `https://apply.workable.com/{slug}/`, `https://{slug}.workable.com`, `https://{slug}.workable.com/` and returns `None` for `/j/...`, `/jobs/...`, `/apply`, reserved paths, or synthetic domains (`example.com`).
   - Verify `normalize_job_url` strips `/apply`, strips trailing `/`, strips Workable/tracking params (`utm_*`, `gh_src`, `ref`, `source`, `workable-source` if Workable rule defines tracking params — preserve meaningful non-tracking query params like `?lang=en`). Add `"workable"` `ProviderUrlRule` to `_PROVIDER_RULES` in `url_normalizer.py`.
   - Verify `url_carries_job_identifier` returns `True` for `apply.workable.com/{slug}/j/{id}/apply` and `False` for `apply.workable.com/{slug}` and `apply.workable.com/{slug}/apply`.
   - Verify against `tests/fixtures/real/workable/serper_urls_78.json`: all 64 unique genuine URLs resolve cleanly to 60 unique `(company_slug, job_id)` pairs across 54 slugs, including all 15 `/apply/` URLs and zero false positives.
   - Verify `_enrich_ats_item` in `search_pipeline.py` registers valid `parse_workable_board_root_url` candidates into `company_board_registry` just like Greenhouse/Lever/Ashby before dropping non-job URLs.
2. **Implement** changes in `ats_url_parser.py`, `url_normalizer.py`, `search_pipeline.py`. Run tests to confirm green.

---

## Unit B — Structured Salary, Currency, Requirements, Eligibility & Location Extraction

**Files:**
- Modify: `src/project_files/salary_parser.py`
- Modify: `src/project_files/job_extraction_service.py`
- Test: `tests/test_salary_parser.py`, `tests/test_workable_pipeline.py`

### Tasks
1. **Failing tests first**:
   - Workable structured fields in `_parse_structured_salary_internal`: `salary_from`, `salary_to`, `salary_currency_iso_code`, `salary_frequency` -> `800000–1500000 INR/year` (`learnrush`), `800–900 JOD/year` (`99brightminds`), `salary_to`-only, `"month"` -> `"month"`, `"hour"` -> `"hour"`, `"day"`? Wait: check `normalize_period` allowed values in `salary_parser.py` before assuming! Guard `salary_from <= 0` and `salary_to <= 0` -> `None`; validate ISO currency code against expanded `ISO_4217_CURRENCIES` (`"JOD"` included).
   - Text salary improvements in `salary_parser.py`:
     - Support `INR` / `₹` and `JOD` in `_CURR_SYMBOLS` so `"**Salary:** INR 800,000–1,500,000"` resolves `currency="INR"` even without structured API fields (`learnrush` Markdown fallback). Wait: also check how `"Salary: INR 800,000–1,500,000"` maps period (does it infer period? NO, `period=None` unless explicit `"annual"`/`"/year"` per ADR-0001 "unknown beats wrong"!).
     - Clean empty markdown link tails `$40K-$200K[](https://apply.workable.com/...)` before extracting `$40K-$200K` (`verneek` `raw_text` cleanly `"$40K-$200K"`, `minimum=40000, maximum=200000, currency="USD", period="year"` when `"Annual Salary Range"` precedes it).
     - Support bulleted single hourly rate `- $30/hr` (`everyday-dose-inc`: `minimum=30, maximum=30, currency="USD", period="hour"`) without regressing existing negative salary tests (`20+ hrs/week`, percentages, etc.).
   - `JobExtractionService`:
     - Add `"workable"` to eligibility extraction gate (`raw.provider in ("workday", "teamtailor", "lever", "greenhouse", "ashby", "workable")`).
     - Add `"workable"` to requirements fallback gate (`L852`). Prefer `raw.raw_requirements` when structured `api/v2` provides `"requirements"` HTML; fall back to `_extract_requirements_fallback` when empty (like `mercari`).
     - Add `"workable"` `raw_location_preserved` if `raw.raw_fields.get("raw_location_preserved")` or multi-location formatting occurs cleanly.
     - Accept `"workable_account_logo"` in `company_logo_source` verified allowlist (`L868`).
2. **Implement** changes in `salary_parser.py` and `job_extraction_service.py`. Run `pytest tests/test_salary_parser.py tests/test_workable_pipeline.py`.

---

## Unit C — Shared `workable_payload_to_raw`, `WorkableClient`, Description Chrome Stripping & Logo Extraction

**Files:**
- Modify: `src/project_files/ats_api_client.py`
- Modify: `src/project_files/logo_extractor.py`
- Modify: `tests/test_real_api_fixtures.py` (add `workable` intentional Step 41 diff block + new `api/v2` fixture assertions)
- Modify: `tests/test_ats_client_outcomes.py`, `tests/test_company_logo.py`, `tests/test_workable_pipeline.py`

### Tasks
1. **Failing tests first**:
   - `_REJECTED_LOGO_PATTERNS` in `logo_extractor.py`: reject `.../uploads/account/open_graph_logo/{id}/social...` and `...workable.com/assets/facebook-preview...`.
   - `_extract_workable_logo(...)` and `"workable"` branch in `extract_company_logo_for_provider(...)`: accept valid JSON-LD `hiringOrganization.logo` OR explicit `workable_account_logo` URL from `api/v1/accounts/{slug}`, normalize/validate via `validate_and_normalize_logo_url`, reject SVG/invalid/social URLs, return `verified=True, source="workable_account_logo"`.
   - `workable_payload_to_raw(...)`:
     - Maps `id`, `shortcode`, `title`, `company_slug`, authoritative `default_company_name` -> `raw_company`, primary + visible `locations` (`hidden != True`) deduplicated cleanly preserving order (`"New York, United States"` / `"City, Region, Country"`? Wait: check existing Workable convention: `location`: `city, country` when distinct and `city` non-empty, `country` when `city` empty, joining multiple unique visible locations with `" | "` cleanly while preserving `raw_location_preserved` if needed; omit `hidden: true`!), `workplace` priority over `remote` boolean (`on_site`, `hybrid`, `remote`), `type` (`"full"` -> `"Full-time"` / `normalize_job_type` handles `"full"` if mapped in `workable_payload_to_raw` — note `normalize_job_type("full")` currently returns `None`, so map `"full"` -> `"Full-time"`, `"part"` -> `"Part-time"`, `"contract"` -> `"Contract"`, `"temporary"` -> `"Temporary"`, `"internship"` -> `"Internship"`, `"other"` -> `None` in `workable_payload_to_raw` AND check `normalize_job_type`!), `department` list/str, `published` ISO timestamp -> `raw_date`, `salary_from`/`salary_to`/`salary_currency_iso_code`/`salary_frequency` preserved in `raw_fields`, `raw_requirements = to_markdown(strip_li_tags(req_html))` when non-empty, authentic clean `raw_description` assembled without duplicated headings (`description_html` + cleanly formatted `Requirements` if `requirements_html` non-empty + `Benefits` if `benefits_html` non-empty), canonical `source_url = https://apply.workable.com/{slug}/j/{shortcode}`, distinct `apply_url = https://apply.workable.com/{slug}/j/{shortcode}/apply`.
   - `workable_markdown_to_raw(...)` helper for `.md` fallback:
     - Parses `# Title`, `> Company · Location · Employment · Posted ...`, `**Salary:**`, `**Workplace:**`, `**Department:**` into structured `raw_*` / `raw_fields` fields.
     - Strips chrome cleanly: leading `# Title`, `> Company...` blockquote and its `- ` metadata bullets (Wait: preserve location/employment/date before stripping!), top `**Salary:**` / `**Workplace:**` / `**Department:**` metadata lines AFTER capturing **Salary:** for salary_parser (`raw_fields["workable_md_salary"]` or keeping salary text? Wait: passing `raw_fields["salary_text"]` or extracting `salary_from` text so salary_parser still sees `"**Salary:** INR 800,000–1,500,000"` without polluting user-facing description OR letting salary extraction run on stripped salary line cleanly!), trailing `## Apply ...` link block (extracting `/apply` href into `apply_url`!), and `---\nPowered by [Workable](https://www.workable.com)`.
     - Preserves genuine `## Description`, `## Requirements`, `## Benefits` sections with zero mid-body or tail text loss!
   - `enrich_workable_board_identity(company_slug, client, registry=..., ttl_seconds=7*86400)`:
     - Calls `GET https://apply.workable.com/api/v1/accounts/{slug}`.
     - 7-day cache hit / negative cache (`company_logo_checked_at`), per-slug asyncio in-flight coalescing, writes `set_board_identity(ats_provider="workable", ...)`.
     - Handles `learnrush` (`logo: null` -> sets `company_name="Learnrush"`, `logo_verified=False`) and `verneek`/`treq`/`mercari`/`99brightminds` (real `workablehr.s3.amazonaws.com/uploads/account/logo/...` -> `verified=True`).
   - `WorkableClient.fetch_raw_result`:
     - Requests `GET https://apply.workable.com/api/v2/accounts/{slug}/jobs/{job_id}` first.
     - On `404` -> returns `ExtractionOutcome.NOT_FOUND` immediately (does NOT spam `.md`).
     - On `200` JSON -> calls `workable_payload_to_raw(...)` (`ATS_API`), optionally enriched via `enrich_workable_board_identity` in `fetch_result` (when `outcome == SUCCESS` and not degraded, mirroring `AshbyClient.fetch_result`!).
     - On `200` non-JSON starting with `# ` (e.g. offline `MockTransport` serving `.md`) -> parses cleanly via `workable_markdown_to_raw(...)` (`SCRAPE`).
     - On bounded non-404 API failure (e.g., 403/5xx if API blocked but `.md` open? Wait: check `test_workable_fetch_result_success_and_degradation`! That test mocks EVERY request returning `503` and expects `res.outcome == RETRYABLE_ERROR, res.status_code == 503, res.degraded_from == "api"`! Falling back to `.md` ONLY if status is 200 HTML/markdown or explicit opt-in/406 ensures 404/429/503 behave consistently with every other ATS client AND fast!).
2. **Implement** in `logo_extractor.py`, `ats_api_client.py`, update `test_real_api_fixtures.py` golden replay diff for `workable_D94DBAF102.json`. Run pytest!

---

## Unit D — `WorkableBoardAdapter`, Bounded Rotating Refresh, Direct Board Routing & Registry Promotion

**Files:**
- Modify: `src/project_files/company_board_registry.py` (`MONITORABLE_PROVIDERS`, `PROVISIONAL_PROVIDERS`, helper method `get_monitored_jobs_for_board(board_id)` returning `dict[str, tuple[JobListing, float]]` of `job_id -> (listing, last_checked_at)`)
- Modify: `src/project_files/board_adapters.py` (`WorkableBoardAdapter`, `BOARD_ADAPTERS["workable"]`)
- Modify: `src/project_files/board_monitor.py` (pass `known_monitored_jobs` or let `WorkableBoardAdapter.check_board` accept `known_monitored_jobs` alongside `known_publication_dates`)
- Modify: `src/project_files/direct_board_router.py` (`probe_workable_board` + `probe_direct_boards`)
- Test: `tests/test_board_monitor.py`, `tests/test_company_board_registry.py`, `tests/test_direct_board_router.py`, `tests/test_workable_pipeline.py`

### Design Detail for `WorkableBoardAdapter`
`GET https://apply.workable.com/api/v1/widget/accounts/{slug}` returns `name`, `description`, `jobs[]` (each item has `shortcode`, `title`, `employment_type`, `telecommuting`, `department`, `url`, `application_url`, `published_on`, `country`, `city`, `state`, `locations`), with **no** `description`, `requirements`, `salary_*`, or `workplace` (`hybrid` vs `on_site`).
1. Compute board-list SHA-256 fingerprint using `compute_board_fingerprint([(shortcode, published_on, _workable_widget_hash(j)) for j in jobs])` (where hash covers title, employment_type, telecommuting, department, city, region/state, country, application_url).
2. `not_modified` check: ONLY return `not_modified=True` if `board.content_fingerprint` matches AND **no** active tracked jobs on this board have stale or unhydrated details (`now - last_checked_at >= detail_revalidate_ttl_seconds`, default e.g. `6 * 3600 = 21600s` or `known_job` missing from `monitored_jobs`).
3. When `check_board` runs:
   - Call `enrich_workable_board_identity(board.board_token, client)` (bounded/cached 7 days) so `company_name` & verified `company_logo_*` are attached cleanly without scraping HTML.
   - Partition `jobs[]` from `widget_v1` into:
     - **Immediate detail fetch**: jobs NOT in `known_monitored_jobs`, OR jobs whose widget hash changed, capped defensively per initial onboarding? Wait: for normal boards (typically 1–50 jobs), fetch new/changed jobs concurrently via bounded `asyncio.Semaphore(5)`. For very large boards (say >25 new jobs), cap per-poll detail fetches via configurable `max_detail_fetches_per_poll: int = 25`? Better: separate `max_new_detail_fetches: int = 25` and `max_revalidations_per_poll: int = 5`:
       - Fetch `api/v2/accounts/{slug}/jobs/{shortcode}` for new/widget-changed jobs (up to 25 per poll; any overflow gets `widget_v1` baseline fallback or deferred without breaking active jobs — wait: even better, for new overflow on massive 100-job boards, construct baseline `JobListing` from `widget_v1` via `workable_widget_job_to_raw(...)` with `last_checked_at=0` style/flagged incomplete so next poll's rotating refresh hydrates details, while small/normal boards ≤25 jobs get 100% full `api/v2` hydration immediately!).
       - Among unchanged known jobs, pick up to `max_revalidations_per_poll` (5) oldest-checked stale jobs (`now - last_checked_at >= detail_revalidate_ttl_seconds`) and refresh their `api/v2` detail to catch salary/description/workplace edits missed by `widget_v1`!
       - For remaining unchanged non-stale jobs (or when an individual `api/v2` detail fetch transiently fails with 429/5xx/timeout): preserve the existing cached `JobListing` cleanly!
       - If an individual `api/v2` detail fetch returns **404** during that same poll, exclude that shortcode from `result.listings` (so `BoardMonitor` marks it closed).
   - If `widget_v1` returns `404` or `>=500` or malformed JSON or network error: return `BoardCheckResult(success=False, error=...)` so `BoardMonitor` records failure and **never** closes active jobs on transient failure!

4. **`probe_workable_board(slug, client)` in `direct_board_router.py`**:
   - Probes `GET https://apply.workable.com/api/v1/widget/accounts/{slug}` (fast single board endpoint) + bounded detail hydration (up to e.g. 10 jobs or semaphore=5) + `enrich_workable_board_identity`, falling back cleanly to `workable_widget_job_to_raw` if any individual detail times out.

---

## Unit E — Zero-Serper Restartable Cache & Board Repair

**Files:**
- Create: `src/project_files/workable_cache_repair.py`
- Test: `tests/test_workable_pipeline.py`

### Tasks
1. Implement `src/project_files/workable_cache_repair.py` following `ashby_cache_repair.py` patterns:
   - `REPAIR_VERSION = "v41"`
   - Table `workable_repair_state(url TEXT PRIMARY KEY, repair_version TEXT NOT NULL, status TEXT NOT NULL, repaired_at REAL NOT NULL, detail TEXT)`
   - Supports `--dry-run`, `--force`, `--db-path`, `--limit`, returning structured `WorkableRepairSummary` (`scanned`, `repaired`, `alias_rekeyed`, `closed_404`, `synthetic_skipped`, `boards_updated`, `logos_verified`, `logos_missing`, `monitored_updated`, `failed`).
   - Excludes synthetic domains (`example.com`, `*.example.com`) and synthetic slugs (`test-*`, `dummy-*`, etc.).
   - Groups genuine Workable `url_cache` rows by `(slug, job_id)` + fetches `api/v2/accounts/{slug}/jobs/{job_id}` and `api/v1/accounts/{slug}` once per slug (zero Serper calls!).
   - Re-keys alias URLs (`.../apply`, trailing `/`, subdomain `{slug}.workable.com/jobs/{id}`, tracking query `?utm_*`) cleanly to canonical `https://apply.workable.com/{slug}/j/{job_id}` **only after** canonical write succeeds (`CacheStore._merge_preserving_completeness`).
   - Marks `404` (`treq/D94DBAF102`) cleanly in repair state + removes/marks closed in `monitored_jobs` if tracked, while recording failure safely without crashing batch on `429`/`5xx`/timeout.
   - Refreshes all Workable `company_boards` rows (`monitoring_capability = 'supported'`, canonical `board_url`, `company_name`, `company_logo_*`).
   - Tests `--dry-run` (zero DB mutation), live repair (`repaired`, `404`, alias dedupe, completeness preservation), and idempotency pass (`0` re-fetches on second pass without `--force`).
2. **Operational Database Execution (with pre-repair backup)**:
   - Back up `data/cache.sqlite` -> `data/cache.sqlite.bak-pre-workable-repair` (remove backup only after or keep outside git — check `.gitignore` first!).
   - Snapshot EXACT BEFORE metrics on `data/cache.sqlite`.
   - Run `--dry-run`, run Pass 1, run Pass 2 (idempotency), snapshot EXACT AFTER metrics on identical denominators!

---

## Unit F — Frontend & Playwright E2E Verification + Step Documentation

**Files:**
- Modify: `tests/e2e/bottom-pot.spec.js` (add dedicated Step 41 Workable E2E test)
- Create: `docs/steps/41-workable-quality-pipeline.md`
- Modify (only if stale): `CONTEXT.md` / `docs/agents/PROJECT_COMPENDIUM.md` / `README.md`

### Tasks
1. Add deterministic Workable Playwright E2E test in `tests/e2e/bottom-pot.spec.js` covering:
   - `ResultsTable` & `DetailSheet`: real logo (`verneek`/`treq`) + initials monogram fallback (`learnrush` / `null` logo), strict `0px` square `CompanyMark` radius, structured INR (`INR 800,000 – 1,500,000 / year`), JOD (`JOD 800 – 900 / year`), and USD (`USD 40,000 – 200,000 / year`), `work_model` (`Hybrid` / `Remote` / `In-person`), `requirements`, `eligibility`, distinct `/apply` `apply_url` vs `source_url`, zero console/page errors, Axe WCAG AA clean, zero horizontal overflow across all 5 viewports (`1920`, `1440`, `1024`, `768`, `390`).
2. Run full verification gates:
   - Targeted pytest suites
   - Full `python -m pytest -q`
   - `python scripts/eval_work_model.py`
   - `npm --prefix frontend run test` & `npm --prefix frontend run build`
   - `npx playwright test`
   - `.\scripts\verify.ps1`
3. Record `docs/steps/41-workable-quality-pipeline.md`, inspect `git status` and full `git diff`, commit clean feature commits on `step/41-workable-quality-pipeline`, push to `origin` (`git push -u origin step/41-workable-quality-pipeline`), and prepare PR without merging.
