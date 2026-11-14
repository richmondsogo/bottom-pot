# Step 42: Recruitee Monitoring Feasibility Investigation

**Branch:** `step/42-recruitee-monitoring-investigation`  
**Base Commit (`main`):** `7ddd864bf37d6193b171b08a7f21288b4143623b` (Merge pull request #38, Step 41 Workable Quality Pipeline)  
**Investigation Date:** 2026-11-14  
**Investigation Scope:** Recruitee only (read-only analysis & documentation; zero source-code, test, fixture, or database mutations)  
**Serper Budget Spent:** `0` credits  
**Outcome:** **1. Suitable for a dedicated monitoring implementation** (Step 43), paired with prerequisite URL-parser and field-mapping fixes documented below.

---

## 1. Existing Implementation Baseline

### Repository Orientation & Step 40/41 Context

- Reviewed `AGENTS.md`, `BUILD_PROTOCOL.md`, `CONTEXT.md`, `docs/agents/PROJECT_COMPENDIUM.md`, `docs/steps/32-global-ats-monitoring-registry.md`, `docs/steps/39-ashby-quality-pipeline.md`, `docs/steps/41-workable-quality-pipeline.md`, and `docs/superpowers/plans/2026-11-13-step-41-workable-quality-pipeline.md`.
- **Step 40 investigation notes location**: No standalone `docs/steps/40-*.md` file exists in the repository; Step 40's reconciled inventory and baseline are recorded inside `docs/steps/41-workable-quality-pipeline.md` (`## Reconciled Inventory & Verified Baseline (Step 40)`) and `docs/superpowers/plans/2026-11-13-step-41-workable-quality-pipeline.md` (`## Step 40 Verified Baseline (Preserved Denominators)`).

### Current Recruitee Footprint in Code

| Capability | Current Status | Evidence / File Location |
|---|---|---|
| ATS Search Platform List | **Configured** | `src/project_files/config.py:27` (`ATSConfig(name="recruitee", site_operator="recruitee.com", label="Recruitee")`), `SUPPORTED_ATS_PATTERNS` (`src/project_files/ats_url_parser.py:59`) |
| Job URL Parsing | **Partial / Broken for live URLs** | `_RECRUITEE` in `src/project_files/ats_url_parser.py:230-233` (`r"^https?://([^./?#]+)\.recruitee\.com/o/(\d+)-[^/?#]+/?$"`) requires a leading numeric `\d+-` prefix; rejects slug-only `/o/{slug}` and `/o/{slug}/c/new` URLs. No `parse_recruitee_board_root_url` exists; no `"recruitee"` rule in `_PROVIDER_RULES` (`src/project_files/url_normalizer.py`). |
| Individual Job Extraction | **Implemented (with field gaps)** | `RecruiteeClient` in `src/project_files/ats_api_client.py:2437-2560`, wired into `ATS_CLIENTS["recruitee"]` (`line 3015`). |
| Independent Monitoring | **Not implemented** | Listed in `PROVISIONAL_PROVIDERS` (`src/project_files/company_board_registry.py:126`), NOT in `MONITORABLE_PROVIDERS` (`line 117`), no adapter in `BOARD_ADAPTERS` (`src/project_files/board_adapters.py:1334`). |
| Direct-Board Router | **Not implemented** | `probe_direct_boards()` (`src/project_files/direct_board_router.py:386-424`) supports Greenhouse, Lever, Ashby, and Workable only. |
| Company Identity & Logo Enrichment | **Not implemented** | No `enrich_recruitee_board_identity`, no Recruitee branch in `logo_extractor.py`, no board-root registration in `search_pipeline.py:_enrich_ats_item` (`lines 354-395`), though `build_canonical_board_url("recruitee", token)` returns `https://{token}.recruitee.com` (`company_board_registry.py:147-148`). |
| Public Company Listing Endpoint | **Not wired** | No code calls `GET https://{slug}.recruitee.com/api/offers/`. |
| Pagination / Listing Limits | **Not implemented** | N/A in repo; verified externally (see Section 3). |
| Real Fixture & Golden Test | **1 fixture pair** | `tests/fixtures/real/recruitee/offer_2774909.json` (`https://miaplaza.recruitee.com/o/2774909-academic-dean`) and `tests/fixtures/golden/recruitee_2774909.json`. |

### `RecruiteeClient` Docstring Discrepancy (Verified)

- **Docstring (`src/project_files/ats_api_client.py:2439`)**: Documents `GET https://api.recruitee.com/c/{slug}/offers/{job_id}`.
- **Implementation (`src/project_files/ats_api_client.py:2456`)**: Calls `https://{parsed.company_slug}.recruitee.com/api/offers/{parsed.job_id}`.
- **Live Verification**:
  - `GET https://api.recruitee.com/c/miaplaza/offers/2774909` returned **HTTP 401**: `{"error": "Resource access requires authentication!", "error_code": null}`. (`api.recruitee.com/c/{company_id}/...` is Recruitee's token-authenticated ATS management API.)
  - `GET https://tether.recruitee.com/api/offers/fullstack-engineer-agenticops-100-remote-14` returned **HTTP 200** JSON (`{"offer": {...}}`) without authentication, confirming the `{slug}.recruitee.com/api/offers/{id_or_slug}` implementation URL is the true public endpoint—and works for both numeric IDs and offer slugs.

---

## 2. Operational Data Inventory (`data/cache.sqlite`, Read-Only)

All queries were executed via `sqlite3.connect("file:data/cache.sqlite?mode=ro", uri=True)` with zero mutations.

### Table Counts

| Table | Recruitee Rows | Total Table Rows | Notes |
|---|---:|---:|---|
| `url_cache` | **`0`** | `524` | `0` fresh, `0` stale, `0` expired, `0` unavailable, `0` slugs, `0` job IDs, `0` duplicates |
| `company_boards` | **`0`** | `157` | `0` Recruitee boards registered |
| `monitored_jobs` | **`0`** | `161` | `0` Recruitee monitored jobs |
| `serper_cache` | **`31` distinct URLs** | `222` query rows | Across `6` expired Serper responses (`21` genuine `*.recruitee.com` URLs + `10` synthetic `example.com` URLs) |

### Root Cause of `0` Operational `url_cache` & `company_boards` Rows

Inspecting the `31` distinct Recruitee organic URLs in `serper_cache` reveals why operational caches contain zero Recruitee records:

- **`10 / 31`** are synthetic test URLs (`https://example.com/recruitee/job/0` through `/9`).
- **`21 / 31`** are genuine `*.recruitee.com` URLs across **`16` unique company slugs**:
  - `almavivadebelgique` (`2`), `bwgfoods` (`1`), `centric` (`1`), `concertgebouw` (`1`), `dransay` (`2`), `globalsurvivorsfund1` (`1`), `gsbsolutions1` (`1`), `highrollertechnologies` (`1`), `impactbrands` (`1`), `momomedicalbv` (`1`), `redsky` (`1`), `skinvision1` (`1`), `tether` (`4`, including `1` `/c/new` apply URL), `theinnercircle` (`1`), `tiugotech` (`1`), `transperfect` (`1`).
- **Url shape breakdown across the `21` genuine URLs**:
  - `20 / 21`: `https://{slug}.recruitee.com/o/{offer-slug}` (e.g. `https://tether.recruitee.com/o/fullstack-engineer-agenticops-100-remote-14`).
  - `1 / 21`: `https://{slug}.recruitee.com/o/{offer-slug}/c/new` (`https://tether.recruitee.com/o/developer-productivity-engineer-100-remote-5/c/new`).
  - **`0 / 21` have a leading numeric `{job_id}-` prefix.**
- Because `_RECRUITEE` in `src/project_files/ats_url_parser.py:230-233` requires `/o/(\d+)-[^/?#]+`, `parse_ats_url()` returned `None` for **`21 / 21` (`100%`)** of genuine Recruitee search results, causing `search_pipeline.py` to drop every single posting before enrichment or `company_boards` registration.
- **Slug variant check**: Three slugs (`globalsurvivorsfund1`, `gsbsolutions1`, `skinvision1`) carry a trailing `1` (Recruitee's automatic subdomain disambiguator when a requested subdomain is taken). No company in `serper_cache` appears under multiple slug variants. However, live probing showed custom-domain divergence: `highrollertechnologies.recruitee.com/api/offers/` returns `careers_url` on `https://highroller-careers.com/o/...`, and `tether.recruitee.com/` HTML executes a JS redirect to `https://careers.tether.io/`.

### Field Coverage Assessment

Because `data/cache.sqlite` `url_cache` has **`0 / 0` Recruitee records**, the operational cache contains **too few records (zero) to measure live field coverage across postings**.

To avoid inventing coverage numbers, the table below reports:
1. Operational `url_cache` counts (`0 / 0`), and
2. Observed behavior of the existing `RecruiteeClient` + `JobExtractionService` when replayed against the single real fixture (`tests/fixtures/real/recruitee/offer_2774909.json`) and checked against live `/api/offers/` schema keys (noting explicitly that 1 fixture does not represent all Recruitee boards).

| Field | `url_cache` Coverage | Existing Fixture Replay (`offer_2774909.json`, `n=1`) & Schema Finding |
|---|---|---|
| **Description** | `0 / 0` (no cached rows) | `1 / 1` present, authentic HTML converted to Markdown (`description_ok=True`, `6,133` chars in golden), clean, complete. All `5 / 5` probed boards expose HTML `description` in `/api/offers/`. |
| **Requirements** | `0 / 0` | **`0 / 1` extracted (`requirements=None`)** despite `offer_2774909.json` providing structured HTML `requirements`. `RecruiteeClient` ignores `offer["requirements"]`, and `"recruitee"` is excluded from `JobExtractionService` requirements fallback (`job_extraction_service.py:852`). |
| **Eligibility** | `0 / 0` | **`0 / 1` extracted (`eligibility=None`)** despite `country_code="US"`, `state_code="OH"`, `locations[0].note` (`"This role is 100% Remote for residents of Ohio."`), and `"Ohio residency required"` in description. `"recruitee"` is excluded from `JobExtractionService` eligibility allowlist (`line 471`). |
| **Location** | `0 / 0` | `1 / 1` `location="Remote job"`, `raw_location=None`. `RecruiteeClient` reads only `offer.get("location") or offer.get("city")`, dropping structured `city`, `state_name`, `country`, `country_code`, and `locations[]` array (losing `"United States"` / `"Ohio"` or multi-location lists). |
| **Salary** | `0 / 0` | `1 / 1` extracted in live replay (`$40–$48/hour USD`, `source="recruitee_structured"` via `salary_parser.py:288-302`). Note `tests/fixtures/golden/recruitee_2774909.json` still holds historical `"salary": null`, overridden in `tests/test_real_api_fixtures.py:294`. |
| **Employment** | `0 / 0` | `1 / 1` `employment_type="full_time"` in fixture replay, **but only by text fallback** from description (`"Full-time, exempt"`). `RecruiteeClient` reads `employment_type`/`employmentType` (absent in API) and ignores **`employment_type_code`** (`"fulltime_permanent"`, `"parttime_permanent"`). |
| **Work model** | `0 / 0` | `1 / 1` `work_model="remote"` (`source="location"`, `"Remote job"`), `raw_workplace_type=None`. `RecruiteeClient` reads `workplace_type`/`workplaceType` (absent in API) and ignores booleans **`remote`**, **`hybrid`**, **`on_site`**. Crucially, `dransay` offer `2650971` has **both `remote=True` and `hybrid=True`** simultaneously—requiring explicit precedence/ambiguity rules under ADR 0001/0002. |
| **Apply URL** | `0 / 0` | **`0 / 1` distinct apply URL**: `RecruiteeClient` sets `apply_url` to `careers_url` (`.../o/{slug}`) instead of **`careers_apply_url`** (`.../o/{slug}/c/new`). |
| **Company identity** | `0 / 0` | `1 / 1` `"Miaplaza"` in fixture only via `humanize_slug("miaplaza")`. `RecruiteeClient` reads `company`/`companyName` (absent in API) and ignores **`company_name`** (`"Tether Operations Limited"`, `"Dr. Ansay Ltd."`, `"High Roller"`, `"Inner Circle"`). |
| **Logo** | `0 / 0` | **`0 / 1` (`company_logo_url=None`, `verified=False`)**. `/api/offers/` and `/api/offers/{id}` expose no logo field (`sharing_image=null`, `cover_image=null`). Public HTML pages expose `<img class="... custom-css-style-navigation-logo-image" src="https://careers.recruiteecdn.com/...">` (`miaplaza` board root & `tether` offer page), except JS-redirect board roots (`tether.recruitee.com/` had `0` `<img>` tags). `og:image` is a `w_1920` hero banner, not a square logo. |
| **Posted date (extra)** | `0 / 0` | **`0 / 1` (`posted_at=None`)**: `RecruiteeClient` passes `created_at` (`"2026-10-07 13:02:41 UTC"`) instead of `published_at` (`"2026-10-09 21:32:44 UTC"`), and `parse_tz_aware_date` / `parse_datetime` fail to parse `"YYYY-MM-DD HH:MM:SS UTC"`! |

---

## 3. Public Endpoint Investigation (Bounded Live Probing)

All outbound probing obeyed strict rules: **`0` Serper credits**, genuine slugs from cache/fixtures only, sequential requests via `src.project_files.http_resilience.throttled_get`, and **10 total outbound GET requests** (strictly within the 10-request cap).

### Sample Companies & Request Log (10 / 10 Requests)

| # | Method & URL | Status | Content-Type | Bytes | Key Findings |
|---|---|---:|---|---:|---|
| 1 | `GET https://miaplaza.recruitee.com/api/offers/` | `200` | `application/json; charset=utf-8` | `295,955` | `{"offers": [...]}` with **7** offers; full 56-key schema; `cache-control: max-age=0, private, must-revalidate`; no `ETag` / `Last-Modified` / rate-limit headers |
| 2 | `GET https://tether.recruitee.com/api/offers/` | `200` | `application/json; charset=utf-8` | `5,972,660` | `{"offers": [...]}` with **234** offers in one response (no pagination); 5.97 MB exceeds `MAX_RESPONSE_BYTES` (3 MB) if streamed with default cap |
| 3 | `GET https://highrollertechnologies.recruitee.com/api/offers/` | `200` | `application/json; charset=utf-8` | `131,831` | **11** offers; `careers_url` uses custom domain `https://highroller-careers.com/o/...`, while `{slug}.recruitee.com/api/offers/` still serves full JSON |
| 4 | `GET https://theinnercircle.recruitee.com/api/offers/` | `200` | `application/json; charset=utf-8` | `55,116` | **3** offers; `remote=False, hybrid=True, on_site=False`, `company_name="Inner Circle"`, `salary` fields all `null` |
| 5 | `GET https://dransay.recruitee.com/api/offers/` | `200` | `application/json; charset=utf-8` | `64,811` | **4** offers; `company_name="Dr. Ansay Ltd."`; offer `2650971` has both `remote=True` and `hybrid=True` |
| 6 | `GET https://api.recruitee.com/c/miaplaza/offers/2774909` | `401` | `application/json` | `70` | `{"error": "Resource access requires authentication!", "error_code": null}` — confirms `RecruiteeClient` docstring endpoint requires auth |
| 7 | `GET https://tether.recruitee.com/api/offers/fullstack-engineer-agenticops-100-remote-14` | `200` | `application/json; charset=utf-8` | `22,105` | Slug-based detail lookup works (`id: 2785197`, `status: "published"`) without numeric ID |
| 8 | `GET https://miaplaza.recruitee.com/` | `200` | `text/html; charset=utf-8` | `336,389` | **7** distinct `/o/...` links in HTML match the **7** offers in `/api/offers/` 1-for-1; `0` JSON-LD scripts; `custom-css-style-navigation-logo-image` `<img>` on `careers.recruiteecdn.com` |
| 9 | `GET https://tether.recruitee.com/` | `200` | `text/html; charset=utf-8` | `3,473,768` | JS redirect page (`Redirect to https://careers.tether.io/`); `0` `<img>` tags; `0` `/o/` links; `0` JSON-LD scripts |
| 10 | `GET https://tether.recruitee.com/o/fullstack-engineer-agenticops-100-remote-14` | `200` | `text/html; charset=utf-8` | `3,601,368` | Contains `JobPosting` JSON-LD (`applicantLocationRequirements`, `datePosted`) and `custom-css-style-navigation-logo-image` `<img>` on `careers.recruiteecdn.com`; note `customIntegrationsApi.offerId` showed `2061555` vs API `offer.id` `2785197` |

*(No sensitive credentials or auth headers were sent or logged; `server: Cowboy` was the only platform header beyond standard caching/content headers.)*

### Answers to the 13 Endpoint Questions

1. **Full active job set retrievable?** **Yes.** `GET https://{slug}.recruitee.com/api/offers/` returned `{"offers": [...]}` on `5 / 5` companies, and `miaplaza`'s `7` API offers matched `7 / 7` public `/o/` links on `https://miaplaza.recruitee.com/`.
2. **Unauthenticated?** **Yes.** Keyless public GET on `{slug}.recruitee.com/api/offers/` and `{slug}.recruitee.com/api/offers/{id_or_slug}`. (`api.recruitee.com/c/{slug}/...` requires auth: HTTP 401.)
3. **Stable job IDs?** **Yes.** Every offer exposes numeric integer `id` (e.g. `2817565`, `2785197`) and string `slug` (plus `guid`, e.g. `"5d97k"`).
4. **Canonical posting URLs?** **Yes.** `careers_url` gives the canonical posting URL (`https://{slug}.recruitee.com/o/{slug}` or custom domain `https://highroller-careers.com/o/{slug}`). Note: `careers_url` does not contain the numeric `id` prefix, whereas `api/offers/{slug}` and `api/offers/{id}` both resolve.
5. **Publication / update timestamps?** **Yes.** Every offer includes `created_at`, `published_at`, `updated_at` (format `"YYYY-MM-DD HH:MM:SS UTC"`), and `close_at` (nullable).
6. **Descriptions or summary only?** **Full descriptions + requirements.** `/api/offers/` returns the complete 56-key offer object, including full HTML `description`, full HTML `requirements`, `translations`, and `open_questions`.
7. **Location, employment, workplace, salary, apply URL?** **Yes.** `location`, `city`, `state_name`, `state_code`, `country`, `country_code`, `locations[]`; `employment_type_code`; `remote`, `hybrid`, `on_site` booleans; `salary` (`{min, max, currency, period}`); and `careers_apply_url` (`.../c/new`).
8. **Pagination?** **None.** Official Recruitee public careers API docs and live observation (`234` offers on `tether` in one unpaginated `{"offers": [...]}` payload) confirm all published offers are returned in one response; only optional filter query params (`department`, `tag`) exist.
9. **Hard caps or filtering constraints?** **None observed up to 234 offers**, though payload size scales linearly (`5.97 MB` for 234 offers on `tether`, which exceeds `settings.max_response_bytes = 3 MB` if applied to JSON API reads).
10. **Detecting disappeared postings?** **Yes.** Each successful `200` response represents the complete `status="published"` board snapshot; disappearing offers can be reconciled cleanly against `monitored_jobs`.
11. **ETag or Last-Modified headers?** **No.** All `5 / 5` `/api/offers/` responses returned `cache-control: max-age=0, private, must-revalidate` with **neither `ETag` nor `Last-Modified`**.
12. **Rate limits or anti-bot restrictions?** **Not triggered in 10 bounded requests**, and **no `X-RateLimit-*` headers** were returned. Exact 429 thresholds remain **Unknown**.
13. **Consistent across Recruitee companies?** **Yes across all 5 tested companies**, including companies using custom careers domains (`highroller-careers.com`, `careers.tether.io`), provided we know their `{slug}.recruitee.com` subdomain.

---

## 4. Monitoring Feasibility Assessment

### Architecture Fit (Compared with Greenhouse, Lever, Ashby, Workable)

- **Closest architectural peers: Lever & Ashby** (single-request full-hydration JSON board endpoint), **simpler than Workable** (no two-step `widget_v1` -> `api/v2` rotating detail hydration needed!).
- **Board identity**:
  - Represent as `ats_provider="recruitee"`, `board_token=slug` (canonical URL `https://{slug}.recruitee.com`, already implemented in `build_canonical_board_url`).
  - Slug stability: Subdomain slugs are stable account identifiers; `company_name` can be read authoritatively from `offers[0]["company_name"]` without an extra endpoint.
  - Logo extraction: Not present in `/api/offers/` JSON. Requires bounded/cached HTML identity fetch (`https://{slug}.recruitee.com/` -> `img.custom-css-style-navigation-logo-image` on `careers.recruiteecdn.com`, falling back to a single `offers[0]["careers_url"]` if the board root is a JS redirect like `tether.recruitee.com/`), while strictly rejecting `og:image` banner photos (`w_1920`). Note: if a custom domain blocks or diverges, logo remains `verified=False` (ADR 0001).
- **Job discovery & hydration**:
  - **One GET request** (`GET https://{slug}.recruitee.com/api/offers/`) retrieves all active postings **with full payloads** (description, requirements, salary, locations, workplace booleans, `published_at`, `careers_url`, `careers_apply_url`).
  - Zero per-job detail requests needed during board polling!
  - One shared pure converter `recruitee_payload_to_raw(...)` in `ats_api_client.py` can serve `RecruiteeClient`, `RecruiteeBoardAdapter`, and `probe_recruitee_board` (mirroring `greenhouse_payload_to_raw`, `lever_payload_to_raw`, `ashby_payload_to_raw`, and `workable_payload_to_raw`).
  - Change detection: Since `ETag`/`Last-Modified` are absent, compute a deterministic SHA-256 `content_fingerprint` over sorted `(id, updated_at, field_hash)` tuples covering all extraction-affecting fields (title, description, requirements, salary, locations, remote/hybrid/on_site, employment_type_code, department, published_at, careers_url, careers_apply_url, company_name).
- **Lifecycle**:
  - Disappearance from an HTTP 200 `{"offers": [...]}` payload safely indicates closure via `BoardMonitor.mark_missing_jobs_closed()`.
  - Failed responses (404, 429, 5xx, network error, invalid JSON) return `BoardCheckResult(success=False, ...)` so `BoardMonitor.record_check_failure()` preserves active cached jobs.
  - Note: Individual detail `RecruiteeClient` calls returning 404 only remove single stale search hits; monitoring relies on the authoritative board listing.
- **Reliability**:
  - Route all monitoring and direct-board calls through `throttled_get()` (`src/project_files/http_resilience.py`) for 429 `Retry-After` backoff, per-host circuit breakers, and `global_concurrency_limit` (`20`).
  - Important subtlety: Because each company uses `{slug}.recruitee.com`, `per_host_concurrency_limit` (`3`) isolates per-company subdomains while `global_concurrency_limit` (`20`) and `monitoring_concurrency_limit` (`5`) bound aggregate traffic.
  - Watch payload size: `throttled_get()` uses `client.get()` (not `fetch_page_with_cap()`'s 3 MB truncation), allowing 6 MB payloads like `tether`; set explicit reasonable timeouts (e.g. `12-15s`) and guard JSON parsing against non-dict/HTML responses.
- **Direct routing (`direct_board_router.py`)**:
  - **Feasible and lightweight**: `probe_recruitee_board(slug, client)` makes a single `throttled_get(f"https://{slug}.recruitee.com/api/offers/")` and converts active offers via `recruitee_payload_to_raw(...)`.
  - Deduplication works identically to Greenhouse/Lever/Ashby/Workable via `recruitee:{slug}:{numeric_id}` (note: URL-discovered jobs where only `{offer_slug}` is parsed vs board-discovered jobs with numeric `id` must canonicalize to matching `source_url` / `apply_url` aliases so `GlobalDeduplicator` merges them cleanly without duplicates!).

---

## 5. Provider Comparison: Workable vs. Recruitee

| Capability | Workable (Step 41) | Recruitee (Observed / Assessed) |
|---|---|---|
| **Public board listing** | Verified (`GET /api/v1/widget/accounts/{slug}`) | **Verified** (`GET https://{slug}.recruitee.com/api/offers/`) |
| **Public job detail** | Verified (`GET /api/v2/accounts/{slug}/jobs/{shortcode}`) | **Verified** (`GET https://{slug}.recruitee.com/api/offers/{id_or_slug}`); docstring `api.recruitee.com/c/...` is 401 auth-only |
| **Stable job identity** | Verified (`shortcode`) | **Verified** (numeric `id` + string `slug`; requires URL/ID alias alignment between `/o/{slug}` and numeric `id`) |
| **Pagination** | Unpaginated widget JSON | **Unpaginated** (`{"offers": [...]}` returned 234 offers on `tether` in 1 request; 5.97 MB payload) |
| **Description quality** | Measured (`28/30` live clean after `api/v2`) | **High in API** (`5/5` boards & `offer_2774909.json` provide full clean HTML `description` + separate `requirements`; `0/0` in `url_cache` today) |
| **Salary structure** | Measured (`7/30`, structured + text) | **Structured `salary` object** (`{min, max, currency, period}`) parsed by `salary_parser.py` (`1/1` in replay; `miaplaza` & `tether` use structured or `null`) |
| **Company identity** | Verified (`api/v1/accounts/{slug}`) | **Present in listing** (`company_name` on every offer, currently ignored by `RecruiteeClient`) |
| **Logo extraction** | Verified (`api/v1/accounts/{slug}` `logo`, `23/29` boards) | **Not in JSON API**; available on public HTML (`careers.recruiteecdn.com` `custom-css-style-navigation-logo-image`), absent on JS-redirect board roots (`tether.recruitee.com/`) |
| **Active-job lifecycle** | Verified (`widget_v1` authoritative + rotating detail TTL) | **Verified** (`status="published"` complete board snapshot; absence from 200 `/api/offers/` = closed; `ETag`/`Last-Modified` absent) |
| **Rate limiting** | Shared `resilience_manager` (`throttled_get`) | **Unknown** exact Recruitee 429 thresholds (`X-RateLimit-*` absent); compatible with `throttled_get` |
| **Direct probing** | Implemented (`probe_workable_board`) | **Feasible** (`probe_recruitee_board` requires 1 GET to `/api/offers/`, no per-job hydration loop) |

---

## 6. Limitations & Unresolved Questions

1. **Zero operational cache sample (`0` rows in `url_cache`)**: All `21` genuine Recruitee URLs in `serper_cache` were dropped by `_RECRUITEE` regex before caching. Broad field coverage across dozens of companies will only be observable after Step 43 URL-parser fixes.
2. **Custom career domains**: Companies using custom domains (`highroller-careers.com`, `careers.tether.io`) are not discovered by `site:recruitee.com` if Google indexes only the custom domain; where `*.recruitee.com` is known, `/api/offers/` still works, though `careers_url` may point to the custom domain.
3. **JS-redirect board roots hinder logo scraping**: On `tether.recruitee.com/`, the root HTML is a JS redirect stub (`0` `<img>` tags), whereas `tether.recruitee.com/o/{slug}` renders the logo `<img>`.
4. **Dual workplace booleans**: `dransay` offer `2650971` sets `remote=True` AND `hybrid=True` simultaneously; naive `if remote: "remote"` would violate ADR 0002.
5. **Large board response size**: `tether` returned `5.97 MB` in one GET; monitoring must stream/decode safely without silent truncation at 3 MB and bound memory/timeouts.
6. **Rate-limit thresholds**: No `X-RateLimit-*` headers observed; exact burst limits are `Unknown`.
7. **Numeric `offerId` mismatch in HTML `customIntegrationsApi`**: Observed `offerId: 2061555` in `tether` HTML script vs `offer.id: 2785197` in `/api/offers/` JSON (reason unverified; monitoring should rely strictly on `/api/offers/` JSON `id` and `slug`).

---

## 7. Final Decision & Recommended Step 43 Scope

### Decision: **1. Suitable for a dedicated monitoring implementation**

Recruitee is ready to be upgraded to independent monitoring and direct-board probing in **Step 43** because `GET https://{slug}.recruitee.com/api/offers/` is an unauthenticated, unpaginated, single-call full-hydration JSON endpoint verified across 5/5 genuine boards.

### Recommended Step 43 Scope (Smallest Credible Implementation)

- **Complexity Estimate:** **Medium** (simpler monitoring lifecycle than Workable—no two-step widget/detail rotation—offset by URL-slug canonicalization, dual-ID deduplication, and field-mapping fixes).
- **Endpoints Used:**
  - Board listing & direct probing: `GET https://{slug}.recruitee.com/api/offers/` (single call via `throttled_get()`).
  - Individual detail enrichment: `GET https://{slug}.recruitee.com/api/offers/{id_or_slug}` (fix `RecruiteeClient` docstring to reflect actual endpoint and `api.recruitee.com` 401 auth boundary).
  - Optional bounded/cached logo enrichment: `GET https://{slug}.recruitee.com/` (with single offer-page fallback on JS redirect, 7-day cache + coalescing like Ashby/Workable).
- **Existing Code to Reuse & Update:**
  - `src/project_files/ats_url_parser.py` & `url_normalizer.py` & `search_pipeline.py`: Accept `/o/{slug}` (with optional numeric prefix and `/c/new` suffix), add `parse_recruitee_board_root_url` + `"recruitee"` `_PROVIDER_RULES` + board-root registration.
  - `src/project_files/field_normalizer.py` / `job_extraction_service.py`: Parse `"%Y-%m-%d %H:%M:%S UTC"` timestamps (`published_at`); opt `"recruitee"` into requirements, eligibility, and verified logo allowlist.
  - `src/project_files/ats_api_client.py`: Extract shared `recruitee_payload_to_raw(...)` mapping `company_name`, `careers_url`, `careers_apply_url`, `employment_type_code`, `remote`/`hybrid`/`on_site` (handling `remote & hybrid` conservatively), `published_at`, `requirements`, `locations[]`, and `salary`.
  - `src/project_files/board_adapters.py`, `company_board_registry.py`, `direct_board_router.py`: Add `RecruiteeBoardAdapter` (with full-field SHA-256 `content_fingerprint` and `throttled_get()`), promote `"recruitee"` to `MONITORABLE_PROVIDERS`, and add `probe_recruitee_board` to `probe_direct_boards()`.
  - `src/project_files/http_resilience.py` / timeout config: Ensure large `/api/offers/` payloads (e.g. 6 MB) are handled safely.
- **Required Tests & Real Fixtures:**
  - Capture real `/api/offers/` and HTML fixtures under `tests/fixtures/real/recruitee/` (including multi-offer list, `remote & hybrid` case, JS-redirect logo case, and `serper_urls` slug-only corpus).
  - Update `tests/test_ats_url_parser.py` (replace `test_recruitee_no_numeric_id_rejected`), `tests/test_real_api_fixtures.py` (documented Step 43 golden diff for `recruitee_2774909.json`), and add `tests/test_recruitee_pipeline.py` covering URL parsing, canonicalization, field mappings, `remote+hybrid` ADR 0001/0002 handling, UTC date parsing, logo validation, `RecruiteeBoardAdapter` lifecycle/404/transient preservation, `probe_recruitee_board`, and `throttled_get` resilience.
- **Unresolved Risks to Guard in Step 43:**
  - Identity/dedup alignment between URL-parsed `job_id="{offer-slug}"` and board-API `id="{numeric_id}"` (canonicalize `source_url` / `apply_url` aliases or align `provider_job_id`).
  - Rate-limit unknowns on `*.recruitee.com` (enforce `throttled_get` everywhere).
  - Large payload memory/timeouts (up to 6+ MB per board).

---

## 8. Zero-Serper Confirmation & Provenance

- **Zero-Serper Confirmation**: Confirmed via read-only `serper_daily_budget` inspection (`data/cache.sqlite` has no entries after `2026-11-12`) and investigation execution log (`0` Serper API calls made; all `10` outbound requests targeted public `*.recruitee.com` / `api.recruitee.com` URLs).
- **Operational Cache Integrity**: `data/cache.sqlite` was opened strictly read-only (`?mode=ro`) and was never modified.
- **Branch**: `step/42-recruitee-monitoring-investigation`
- **Base Commit (`main`)**: `7ddd864bf37d6193b171b08a7f21288b4143623b`
- **Pull Request**: `https://github.com/richmondsogo/bottom-pot/pull/39` (opened; not merged)
- **First Commit SHA**: `2876d825de4501687d207583aa14c61655685e74`
- **Merge Commit SHA**: Pending
