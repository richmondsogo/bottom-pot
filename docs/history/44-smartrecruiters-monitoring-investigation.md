# Step 44: SmartRecruiters Monitoring Feasibility Investigation

**Branch:** `step/44-smartrecruiters-monitoring-investigation`
**Base Commit (`main`):** `9b7913fe9bae69bd0cfe91ae54c5332a1a6f058a` (Merge pull request #40, Step 43 Recruitee Quality Pipeline)
**Investigation Date:** 2026-11-15
**Investigation Scope:** SmartRecruiters only (read-only analysis, bounded public API probing, real fixture capture, and investigation report; zero production code, allowlist, router, frontend, or database mutations)
**Serper Budget Spent:** `0` credits
**Outcome:** **Suitable with constraints** for Step 45 monitoring & quality pipeline implementation.

---

## 1. Verified Baseline Inventory (`data/cache.sqlite` & Fixtures, Read-Only)

All SQLite queries were executed strictly read-only via `sqlite3.connect("file:data/cache.sqlite?mode=ro", uri=True)` with zero mutations (`data/cache.sqlite` unchanged: `14,143,488` bytes, `LastWriteTimeUtc: 2026-11-14T14:33:06Z` / `2026-11-14T15:33:06+01:00`).

### Table Reconciliation

| Source / Table | SmartRecruiters Count | Total Table Rows | Verified Breakdown |
|---|---:|---:|---|
| `serper_cache` | **`115` distinct URLs** (`118` total links) | `222` query rows | `105` genuine `jobs.smartrecruiters.com` posting URLs + `10` synthetic test rows (`https://example.com/smartrecruiters/job/0`–`/9`) + `3` duplicate cross-query occurrences (`RRDonnelley`, `Grimco`, `SipwiseGmbH`). **`105 / 105` (`100%`)** genuine URLs parse via `parse_ats_url()`, spanning **`64`** unique company identifiers. |
| `url_cache` | **`87` rows** (`0` fresh, `87` expired) | `524` rows | `87` genuine `jobs.smartrecruiters.com` postings (`0` synthetic rows), `87 / 87` `data_source="api"`, `87 / 87` parsed by `parse_ats_url()`, spanning **`55`** unique company identifiers (`created_at` range: `2026-10-30T07:02:51Z` to `2026-11-11T10:53:58Z`). |
| `serper_cache` ∪ `url_cache` | **`105` unique genuine URLs / postings** | — | All `87` `url_cache` URLs exist in `serper_cache` (`87` overlap, `18` only in `serper_cache`, `0` only in `url_cache`). |
| `company_boards` | **`13` boards** | `157` rows | All `13` have `monitoring_capability='provisional'`, `verification_status='candidate'`, `discovery_source='search'`, `last_successful_check=None`, `active_job_count=0`, `company_logo_verified=0`. Note `board_token` is stored lowercased (`aecom2`, `servicenow`, `iotagroup`, etc.) while `source_posting_url` preserves mixed case (`AECOM2`, `ServiceNow`, `IOTAGROUP`). `iotagroup` exists in `company_boards` (`id=59`) while absent from current `serper_cache`/`url_cache`. |
| `monitored_jobs` | **`0` rows** | `161` rows | SmartRecruiters is provisional and not independently monitored. |
| Pre-existing Real Fixtures | **`4` JSON detail payloads** | — | `tests/fixtures/real/smartrecruiters/`: `744000155825759.json` (`Sutherland`), `744000155937924.json` (`Wise`), `744000155969710.json` (`Continental`), `job_3743990000051828.json` (`Uber`). |
| Pre-existing Golden Fixtures | **`4` JSON files** | — | `tests/fixtures/golden/smartrecruiters_{3743990000051828,744000155825759,744000155937924,744000155969710}.json`. |

### Unique Company Identifiers & Existing Cache Field Coverage

- **Total unique company identifiers** across `serper_cache` (`64`), `url_cache` (`55`), `company_boards` (`13`), and pre-existing real fixtures (`4`): **`67` case-insensitive company identifiers** (`79` exact-case strings due to lowercased `company_boards.board_token` alongside mixed-case URL/fixture identifiers).
- **Existing `company_boards` SmartRecruiters tokens (`13`)**: `aecom2`, `asos`, `experian`, `grab`, `intuitive`, `iotagroup`, `nearmap`, `nielseniq`, `servicenow`, `sportradar`, `version1`, `wellmarkinc`, `wisersolutions`.
- **Existing `url_cache` field coverage (`n=87`, cached prior to `2026-11-11`)**:
  - `description`: `87 / 87`, `location`: `87 / 87`, `posted_at`: `87 / 87`, `employment_type`: `86 / 87`, `work_model`: `39 / 87`, `salary`: `9 / 87`.
  - `requirements`: `0 / 87`, `eligibility`: `0 / 87`, `raw_location`: `0 / 87`, `apply_url != source_url`: `0 / 87`, `company_logo_verified`: `0 / 87`.

---

## 2. Public Listing Endpoint Findings

Tested sequentially without authentication against genuine cached/fixture company identifiers.

### Request / Response Observations

| Company / Probe | Request URL | UTC Timestamp | HTTP | Bytes | Latency (ms) | `totalFound` | `content` len | Key Observation |
|---|---|---|---:|---:|---:|---:|---:|---|
| `Wise` | `.../companies/Wise/postings?limit=100&offset=0` | `2026-11-15T20:41:20.208603+00:00` | `200` | `304,929` | `1348.0` | `441` | `100` | Page 0 of multi-page board; ETag `W/"4a721-pbHaoylWAacUMb9yP//synWGJMA"` |
| `wise` (lowercase) | `.../companies/wise/postings?limit=100&offset=0` | `2026-11-15T20:41:21.879294+00:00` | `200` | `304,929` | `317.1` | `441` | `100` | Case-insensitive path resolution; item `company.identifier` remains `"Wise"`, while `ref` mirrors requested `/companies/wise/...` |
| `ServiceNow` | `.../companies/ServiceNow/postings?limit=100&offset=0` | `2026-11-15T20:41:22.515743+00:00` | `200` | `232,561` | `292.9` | `815` | `100` | Large enterprise board (`9` pages at `limit=100`) |
| `Grab` | `.../companies/Grab/postings?limit=100&offset=0` | `2026-11-15T20:41:23.122201+00:00` | `200` | `157,238` | `334.7` | `431` | `100` | Multi-page board (`5` pages) |
| `Nearmap` | `.../companies/Nearmap/postings?limit=100&offset=0` | `2026-11-15T20:41:23.763706+00:00` | `200` | `49,091` | `252.3` | `36` | `36` | Single-page board (`< 100` postings) |
| `iotagroup` vs `IOTAGROUP` | `.../companies/{case}/postings?limit=100&offset=0` | `2026-11-15T20:41:24.319111+00:00` | `200` | `132,345` | `334.2` | `130` | `100` | Both return `130` jobs and canonical `company.identifier: "IOTAGROUP"` |
| `Uber` | `.../companies/Uber/postings?limit=100&offset=0` | `2026-11-15T20:41:25.657078+00:00` | `200` | `2,213` | `539.9` | `1` | `1` | Single public posting (`Test UAT`, `3743990000051828`) |
| `ScalableGmbH` | `.../companies/ScalableGmbH/postings?limit=100&offset=0` | `2026-11-15T20:41:26.498799+00:00` | `200` | `149,005` | `317.5` | `109` | `100` | `2`-page board (`100` + `9`) |
| `PitchBlackCreative` | `.../companies/PitchBlackCreative/postings?limit=100&offset=0` | `2026-11-15T20:41:27.124087+00:00` | `200` | `209,828` | `663.6` | `70` | `70` | `70` postings |
| `Nearmap` (`limit=200`) | `.../companies/Nearmap/postings?limit=200&offset=0` | `2026-11-15T20:42:12+00:00` (approx) | `200` | `49,091` | — | `36` | `36` | Response reports `"limit": 100` — server silently clamps `limit > 100` to `100` |
| `Nearmap` (`destination=PUBLIC`) | `.../companies/Nearmap/postings?limit=100&offset=0&destination=PUBLIC` | `2026-11-15T20:42:12+00:00` (approx) | `200` | — | — | `36` | `36` | Identical count to omitted `destination` |
| `Wise` (`destination=PUBLIC`) | `.../companies/Wise/postings?limit=100&offset=0&destination=PUBLIC` | `2026-11-15T20:44:10.087999+00:00` | `200` | — | — | `441` | `100` | Identical count to omitted `destination` |
| `Nearmap` (`destination=INTERNAL`) | `.../companies/Nearmap/postings?limit=100&offset=0&destination=INTERNAL` | `2026-11-15T20:42:13+00:00` (approx) | `200` | — | — | `0` | `0` | Returns `{"offset":0,"limit":100,"totalFound":0,"content":[]}` — no internal jobs exposed |
| `Wise` (`If-None-Match`) | `.../companies/Wise/postings?limit=100&offset=0` | `2026-11-15T20:42:13+00:00` (approx) | `304` | `0` | — | — | — | Honors `If-None-Match` weak ETag with HTTP `304 Not Modified` |
| `nonexistent-bottom-pot-probe-99999` | `.../companies/nonexistent-bottom-pot-probe-99999/postings?limit=100&offset=0` | `2026-11-15T20:42:14+00:00` (approx) | `200` | `52` | — | `0` | `0` | **Critical:** Unknown company returns HTTP `200` with `totalFound: 0, content: []` (NOT HTTP `404`) |
| `GET /v1/companies/Wise` | `https://api.smartrecruiters.com/v1/companies/Wise` | `2026-11-15T20:42:22+00:00` (approx) | `404` | — | — | — | — | HTML 404 (`Cannot GET /public-posting-api/api-v1/companies/Wise`); no public company metadata endpoint at `/v1/companies/{slug}` |

Additional cached boards verified at `200 OK`: `RecruitmentLoop` (`1`), `ProximateTechnologiesInc1` (`11`), `OteemoInc` (`18`), `Grimco` (`40`), `Carecom1` (`53`), `HoustonEngineeringInc` (`69`). All inspected listing items across `Nearmap` (`36`), `ScalableGmbH` (`109`), and `Wise` page 0 (`100`) had `visibility: "PUBLIC"`, `missing_fullLocation: 0`, and `releasedDate` ordered strictly descending.

### Response Shape & Listing Fields

- **Top-level JSON keys**: `["offset", "limit", "totalFound", "content"]`.
- **Listing item keys (18 keys)**: `id` (numeric string, e.g. `"744000161158698"`), `name`, `uuid` (UUID string), `jobAdId` (UUID string), `defaultJobAd` (`bool`), `refNumber`, `company` (`{"identifier": ..., "name": ...}`), `releasedDate` (ISO-8601 UTC with `.000Z` millis), `location` (`city`, `region`, `country`, `address`, `postalCode`, `remote`, `hybrid`, `latitude`, `longitude`, `fullLocation`), `industry`, `department`, `function`, `typeOfEmployment`, `experienceLevel`, `customField`, `visibility` (`"PUBLIC"`), `ref`, `language`.
- **Headers**: `content-type: application/json; charset=utf-8`, `server: cloudflare`, `cf-cache-status: DYNAMIC`, `etag: W/"..."`, `x-envoy-upstream-service-time`. No `Last-Modified` or `X-RateLimit-*` headers observed.

---

## 3. Authentication Findings

- **Public listing endpoint (`GET /v1/companies/{companyIdentifier}/postings`)**: **Unauthenticated.** All tested company boards succeeded with HTTP `200` without API keys, OAuth tokens, or cookies.
- **Public detail endpoint (`GET {ref}` / `GET /v1/companies/{companyIdentifier}/postings/{id_or_uuid}`)**: **Unauthenticated.** Succeeded with HTTP `200`.
- **Internal filter safety**: Passing `destination=INTERNAL` unauthenticated returned `totalFound: 0, content: []` (`200 OK`); all returned items in default and `destination=PUBLIC` requests had `visibility: "PUBLIC"`. Still, explicitly passing `destination=PUBLIC` documents intent cleanly.

---

## 4. Pagination Findings

Verified across two complete multi-page boards (`ScalableGmbH` with `109` postings; `Wise` with `441` postings):

| Company | Page | Offset | Returned `content` | `totalFound` | Bytes | Latency (ms) | Unique Check |
|---|---:|---:|---:|---:|---:|---:|---|
| `ScalableGmbH` | 0 | `0` | `100` | `109` | `149,005` | `1115.6` | — |
| `ScalableGmbH` | 1 | `100` | `9` | `109` | `13,367` | `343.7` | `109 / 109` unique `id` and `uuid`; `0` duplicates |
| `ScalableGmbH` | 2 (past end) | `200` | `0` | `109` | `56` | `246.2` | `{"offset": 200, "limit": 100, "totalFound": 109, "content": []}` |
| `Wise` | 0 | `0` | `100` | `441` | `304,929` | `325.4` | — |
| `Wise` | 1 | `100` | `100` | `441` | `302,729` | `326.0` | — |
| `Wise` | 2 | `200` | `100` | `441` | `302,679` | `326.3` | — |
| `Wise` | 3 | `300` | `100` | `441` | `307,648` | `413.6` | — |
| `Wise` | 4 | `400` | `41` | `441` | `121,020` | `327.3` | `441 / 441` unique `id`; `0` duplicates; `totalFound` consistent across all 5 pages |

### Pagination Rules & Hazards

1. **Page size constraint**: `limit` is capped at `100` (passing `limit=200` clamps response `"limit": 100`). This is a per-page limit, **not** a total-job limit.
2. **Draining all pages**: Sequential `offset += len(content)` (or `offset += limit`) drains all pages cleanly until `len(content) == 0` or `offset + len(content) >= totalFound` (plus a safety ceiling far above realistic boards—never a low arbitrary job cap like 100).
3. **Multi-page ETag hazard**: SmartRecruiters returns a weak `ETag` per page (`If-None-Match` returned `304` on `Wise` page 0). However, **page-0 `304` cannot prove a multi-page board (`totalFound > 100`) is unmodified**, because edits or closures on `offset >= 100` leave page 0 unchanged. Conditional `If-None-Match` on page 0 is only safe when the previously known board has `<= 100` jobs (and even then, page 0 changes if total rises past 100), or multi-page boards must skip `If-None-Match` and drain all pages.
4. **Concurrent mutation / drift guard**: Because pagination is offset-based across live queries, a posting added or removed mid-crawl could shift items across a page boundary or change `totalFound`. Monitoring must check that every page returns HTTP `200`, valid JSON (`offset`, `limit`, `totalFound`, `content`), `len(deduped_items)` accounts for the snapshot without mid-crawl page failure, and any page error aborts the whole snapshot.

---

## 5. Full-Detail Hydration Findings (`ref` vs Listing)

Verified by fetching `item["ref"]` and `.../postings/{uuid}` for `Nearmap` (`744000161158698`) and `Wise` (`744000161639339`):

- **`ref` validity**: `item["ref"]` is `https://api.smartrecruiters.com/v1/companies/{requestedSlug}/postings/{id}` and resolves unauthenticated (`200 OK`) cleanly, equivalent to `SmartRecruitersClient`'s `https://api.smartrecruiters.com/v1/companies/{slug}/postings/{job_id}`.
- **Numeric ID & UUID resolution**: Both `.../postings/744000161158698` (numeric `id`) and `.../postings/198010c2-4206-4c46-80c2-a216f941ea04` (`uuid`) returned `200 OK` with identical full detail JSON. Nonexistent posting ID `999999999999999` returned HTTP `404` JSON (`{"code": "RESOURCE_NOT_FOUND", ...}`).
- **Listing vs Detail Field Diff**:
  - **Listing-only**: `ref` (and in `Wise`, `department` appeared in listing while omitted in detail; in `Nearmap`, `department.id` was string `"5221948"` in listing vs integer `5221948` in detail).
  - **Detail-only (essential fields)**:
    - `jobAd.sections` (`companyDescription`, `jobDescription`, `qualifications`, `additionalInformation`) — **absent from listing** (`description_ok=False` and `requirements=None` if using listing alone).
    - `compensation` (`{"min", "max", "currency", "period"}`) — **absent from listing** (e.g. `Wise` `744000161639339` has `GBP 75000–115000 YEARLY` in detail only).
    - `postingUrl` (`https://jobs.smartrecruiters.com/{company.identifier}/{id}-{slug}`) and `applyUrl` (`{postingUrl}?oga=true`) and `referralUrl` — **absent from listing**.
    - `active` (`bool`), `jobId` (UUID), `creator`.
  - **Available in listing without detail fetch**: `id`, `uuid`, `jobAdId`, `name`, `company` (`identifier`, `name`), `releasedDate`, `location` (`fullLocation`, `city`, `region`, `country`, `remote`, `hybrid`, etc.), `typeOfEmployment`, `experienceLevel`, `function`, `department`, `industry`, `customField` (note `Wise` exposes `"Job Ad Salary Range"` in `customField`), `language`, `visibility`, `refNumber`.

### Minimum Safe Hydration Strategy

1. **Detail hydration is mandatory for quality**: Listing objects alone have zero description (`description_ok=False`), zero `requirements`, zero structured `compensation`, and no `postingUrl`/`applyUrl`. Every active posting needs detail hydration (`GET {ref}` or `/v1/companies/{slug}/postings/{id}`) to reach full Bottom Pot quality.
2. **Bounded incremental & rotating hydration (modeled on `WorkableBoardAdapter`)**:
   - **Never blindly hydrate 400–800 detail endpoints synchronously inside `/search` direct probing or a single unconstrained poll**.
   - **Direct-board probing (`probe_smartrecruiters_board`)**: Cap detail fetches (e.g. `max_detail_fetches=15`, matching `probe_workable_board`) and either emit hydrated jobs cleanly or bounded listing fallback where needed without exceeding `search_hard_timeout_seconds`.
   - **Board monitoring (`SmartRecruitersBoardAdapter`)**: Compute a full-item listing fingerprint per job (`_smartrecruiters_listing_job_hash(item)` excluding volatile request-echoed casing if needed) plus board-level `compute_board_fingerprint(...)`. Hydrate via `ref` when:
     - A posting is **new** (not in `known_monitored_jobs`),
     - Its **listing payload changed** (full listing item hash differs from stored/previous), OR
     - Its `detail_next_retry_at` / `detail_revalidate_ttl_seconds` (e.g., 6h rotating TTL) is due — **catching silent edits to `jobAd.sections` or `compensation` that do not change listing metadata**, while bounding per-poll detail fetches (e.g., `max_revalidations_per_poll` + bounded initial backlog catch-up across polls via `MonitoredJobDetailState`, preserving existing rich cached listings if a detail fetch fails).
   - **Security guard on `ref`**: Before fetching `item["ref"]`, validate it is `https://api.smartrecruiters.com/v1/companies/...` (or construct `https://api.smartrecruiters.com/v1/companies/{encoded_slug}/postings/{encoded_id}`) to prevent SSRF via untrusted URLs.

---

## 6. Stable Identity & Fingerprint Recommendations

1. **Canonical Posting Identity**:
   - **`id`** (numeric string, e.g. `"744000161158698"`): Stable primary key matching existing `_SMARTREC` URL parser (`jobs.smartrecruiters.com/{Company}/{id}-{slug}`), `SmartRecruitersClient`, and `url_cache`. `uuid` and `jobAdId` can be recorded in metadata/aliases if needed, while `id` remains canonical `provider_job_id`.
   - **Case-consistency bug to fix in Step 45**: `company_boards` stores `board_token` lowercased (`"wise"`, `"servicenow"`), whereas `parse_ats_url("https://jobs.smartrecruiters.com/Wise/744000161639339-...")` preserves `"Wise"`. That causes `job_id` mismatch (`"smartrecruiters:Wise:..."` vs `"smartrecruiters:wise:..."`). Step 45 should normalize `company_slug` consistently (lowercase `board_token` for `job_id` / `company_slug`, while preserving canonical `company.name` and `postingUrl` casing) and add `"smartrecruiters"` to `url_normalizer._PROVIDER_RULES` so search-discovered and board-monitored postings deduplicate identically.
2. **Board & Job Fingerprinting**:
   - **Listing-level item hash**: Compute full-payload SHA-256 over the complete normalized listing item (excluding `ref`, or normalizing `ref` to canonical lowercase company token, and normalizing `department.id` type only where listing vs detail differs—listing-to-listing comparison uses the listing schema consistently, where no ephemeral per-request tokens exist).
   - **Board-level fingerprint**: `compute_board_fingerprint([(id, releasedDate, listing_item_hash), ...])` across all public active items from all pages.
   - **Detail-level refresh**: Combine listing-change detection with `MonitoredJobDetailState` rotating TTL (`detail_revalidate_ttl_seconds`, e.g. 6h) so stale `jobAd.sections` / `compensation` never remain stale indefinitely even if `releasedDate` and listing fields don't change.

---

## 7. Failure & Snapshot-Completeness Semantics

| Condition | Observed Endpoint Behavior | Required Monitoring / Probing Behavior |
|---|---|---|
| **HTTP `200`, `totalFound == 0, content == []` on known board** | Valid empty public board (indistinguishable on `/postings` API from nonexistent company) | **Monitoring**: For an already-registered board, valid `totalFound == 0, content == []` with valid envelope `{"offset":0,"limit":...,"totalFound":0,"content":[]}` closes previously active jobs cleanly via `mark_missing_jobs_closed()`. **Direct probing**: Returns `[]` and does **not** register a candidate board (prevents bogus slug registration!). |
| **HTTP `200`, `totalFound == 0` on unknown/typo slug** | SmartRecruiters returns `200` empty (`nonexistent-bottom-pot-probe-99999`), NOT `404`! | Direct probing must never register a board with `0` active jobs; board registration from search relies on real posting URLs or non-empty probes. |
| **HTTP `404` on `/postings`** | Observed HTML 404 on `/v1/companies/{slug}` (wrong path); detail `/postings/{bad_id}` returns `404` JSON `RESOURCE_NOT_FOUND` | On listing: `BoardCheckResult(success=False)` — preserves previously active jobs. On detail while listing still includes the `id`: mark `detail_404` backoff (do **not** falsely close the job!). |
| **HTTP `429` / `5xx` / timeout / network error** | Handled by `throttled_get` (`record_rate_limit` / `record_failure`) | Return `BoardCheckResult(success=False, ...)` so `BoardMonitor.record_check_failure()` preserves all active jobs. |
| **Invalid JSON or malformed envelope** | Missing `content` list, non-dict response, non-int `totalFound`, or missing `id`/`name` on any listing entry | **Fail whole snapshot** (`BoardCheckResult(success=False, ...)` / `[]` in direct probe); never convert malformed data into an empty snapshot. |
| **Partial / interrupted pagination** | E.g. page 0 (`offset=0`) succeeds (`totalFound=441`) and page 2 (`offset=200`) fails (`5xx`/`429`/timeout), or `content` stops short of `totalFound` unexpectedly | **Abort entire board check** as `BoardCheckResult(success=False, ...)` — **never** pass partial page results to `mark_missing_jobs_closed()`, which would falsely close jobs on pages 2–4! |
| **Unrecognized `visibility`** | All 245 inspected live items had `visibility: "PUBLIC"` | Reject or treat unrecognized/missing `visibility` defensively if non-`"PUBLIC"` ever appears, failing snapshot validation if malformed rather than guessing. |

---

## 8. Rate-Limit & Resilience Observations

- **Observed headers**: No `X-RateLimit-*` or `Retry-After` headers were returned on `200`/`304`/`404` responses; traffic passes through Cloudflare + Envoy (`server: cloudflare`, `x-envoy-upstream-service-time`). Exact burst 429 threshold is **Unknown** (we did not stress-test/spam the API).
- **Latencies & sizes**: Listing pages (`limit=100`) ranged from `2.2 KB` (`Uber`, 1 job) to `307.6 KB` (`Wise`, 100 jobs), `246–1348 ms`; detail payloads were ~`9–13 KB`, ~`325 ms`. Well below `settings.max_response_bytes` (`3 MB`) per request.
- **Shared resilience compatibility**:
  - All requests hit a single host (`api.smartrecruiters.com`). Routing every listing page and `ref` detail fetch through `throttled_get()` (`src/project_files/http_resilience.py`) automatically enforces `per_host_concurrency_limit` (`3`), `global_concurrency_limit` (`20`), post-semaphore readiness rechecks, `429 Retry-After` exponential backoff, and per-host circuit breaking (`5` failures -> `600s` cooldown).
  - **Important capacity note**: Because every SmartRecruiters board shares `api.smartrecruiters.com` (`per_host_concurrency_limit = 3`), **no board check or direct probe may fire unbounded detail bursts**, otherwise a single 441-job or 815-job board (`Wise`, `ServiceNow`) would monopolize the host semaphore for >60s and trip timeouts across concurrent boards. Bounded per-poll detail hydration (e.g., `max_new_hydrations_per_poll` + `max_revalidations_per_poll`) is essential.
  - Note `SmartRecruitersClient._do_fetch` currently uses `@with_retry` + `client.get` directly (not `throttled_get`, because `search_pipeline._throttled_enrich` already holds `resilience_manager.throttle(item_url)` on `jobs.smartrecruiters.com` while `_do_fetch` hits `api.smartrecruiters.com`). Keep search-pipeline outer throttle behavior separate from `BoardMonitor` / `direct_board_router` `throttled_get()` to avoid nested semaphore issues.

---

## 9. Existing Implementation Gaps

| Area | Current State & File Location | Gap / Required Action for Step 45 |
|---|---|---|
| **Provider Monitoring Status** | `PROVISIONAL_PROVIDERS` in `src/project_files/company_board_registry.py:126`; no adapter in `BOARD_ADAPTERS` (`src/project_files/board_adapters.py:1648`) | Implement `SmartRecruitersBoardAdapter` + shared hydration helpers; promote `"smartrecruiters"` to `MONITORABLE_PROVIDERS`. |
| **Direct-Board Router** | `probe_direct_boards()` in `src/project_files/direct_board_router.py:444` supports GH, Lever, Ashby, Workable, Recruitee only | Add `probe_smartrecruiters_board()` sharing bounded pagination + hydration; wire into `probe_direct_boards()`. |
| **`applyUrl` / `postingUrl` bug** | `SmartRecruitersClient._parse_raw_payload()` (`src/project_files/ats_api_client.py:1451`) uses `data.get("ref") or parsed.raw_url` | Detail payloads lack `ref` and provide `applyUrl` (`?oga=true`) and `postingUrl`. Use `data.get("applyUrl") or data.get("postingUrl") or parsed.raw_url`, and canonical `source_url = data.get("postingUrl") or parsed.raw_url`. *(Verify existing `test_real_api_fixtures.py` / golden impact carefully.)* |
| **Eligibility Allowlist Gap** | `JobExtractionService.extract()` (`src/project_files/job_extraction_service.py:474`) excludes `"smartrecruiters"` from `extract_eligibility()` allowlist | Opt `"smartrecruiters"` into `extract_eligibility()` (and fallback `extract_requirements()` when `qualifications` absent, line `873`) as a dedicated Step 45 quality fix. |
| **URL Parser & Board-Root Discovery** | `_SMARTREC` (`src/project_files/ats_url_parser.py:162`) matches `jobs.smartrecruiters.com/{Company}/{digits}`; no board-root parser; `search_pipeline.py:358-408` lacks SmartRecruiters branch | Add `parse_smartrecruiters_board_root_url()` (`jobs.smartrecruiters.com/{slug}` and `careers.smartrecruiters.com/{slug}` with reserved path guards), wire into `_enrich_ats_item()`, and normalize `company_slug` case consistently (`wise` vs `Wise`). |
| **URL Normalizer** | `src/project_files/url_normalizer.py:92` `_PROVIDER_RULES` lacks `"smartrecruiters"` | Add `"smartrecruiters"` rule (e.g. handling `?oga=true` / tracking params vs canonical posting URL) for clean cross-source deduplication. |
| **Company Logo Enrichment** | `src/project_files/logo_extractor.py:421` does not enable `"smartrecruiters"`; `jobs.smartrecruiters.com/{slug}` often 301-redirects to custom corporate domains (`wise.jobs`, `nearmap.com`), whereas posting HTML `jobs.smartrecruiters.com/{slug}/{id}` exposes `c.smartrecruiters.com/sr-company-logo-prod-*` | Investigate/implement bounded posting-page HTML logo extraction (rejecting `av-www.smartrecruiters.com/sr-logo/...` platform wordmark) or leave `verified=False` if blocked (ADR 0001). |
| **Shared Pure Payload Converter** | Parsing logic lives inside `SmartRecruitersClient._parse_raw_payload` (`ats_api_client.py:1382`) | Extract shared `smartrecruiters_payload_to_raw(...)` (preserving existing `qualifications -> raw_requirements`, 4-section markdown assembly, `fullLocation`, `compensation`, and `remote`/`hybrid` ADR 0001/0002 semantics without regressing `tests/test_smartrecruiters_pipeline.py`). |

---

## 10. Feasibility Decision

**Decision: `Suitable with constraints`**

SmartRecruiters exposes a stable, unauthenticated, well-structured public JSON API (`GET https://api.smartrecruiters.com/v1/companies/{companyIdentifier}/postings` + `ref` detail endpoint) that supports complete active-job discovery, reliable pagination (`limit=100`, `offset`), and high-precision structured extraction (including `jobAd.sections`, `qualifications`, `compensation`, `fullLocation`, `remote`/`hybrid`, `releasedDate`, `postingUrl`, and `applyUrl`).

However, promotion to `MONITORABLE_PROVIDERS` is safe **only under four explicit engineering constraints**:
1. **Full multi-page draining with strict atomic snapshot validation** (no page-0 ETag short-circuit on `>100`-job boards; any page error aborts the board check without closing jobs).
2. **Mandatory detail hydration via `ref` with bounded per-poll budgets + rotating TTL** (never block search/monitoring with 400–800 unthrottled detail GETs, and never rely on listing-only payloads for descriptions/compensation).
3. **200-empty unknown-company guard** (because unknown company slugs return HTTP `200` with `totalFound: 0`, direct probing must never register empty boards).
4. **Canonical lowercase `company_slug` alignment + URL normalization** across `ats_url_parser.py`, `company_board_registry.py`, and `SmartRecruitersBoardAdapter` to prevent case-split duplicate `job_id`s (`Wise` vs `wise`).

---

## 11. Recommended Step 45 Implementation Scope

### In Scope (Smallest Credible & Safe Implementation)
1. **URL & Identity Normalization (`ats_url_parser.py`, `url_normalizer.py`, `search_pipeline.py`)**:
   - Add `parse_smartrecruiters_board_root_url()` + board-root candidate registration in `SearchOrchestrator._enrich_ats_item()`.
   - Normalize `company_slug` casing consistently (matching `company_boards.board_token` lowercase) and add `"smartrecruiters"` to `_PROVIDER_RULES`.
2. **Shared Converter & Quality Fixes (`ats_api_client.py`, `job_extraction_service.py`, `logo_extractor.py`)**:
   - Extract `smartrecruiters_payload_to_raw(...)` preserving all Step 33 behaviors (`jobAd` 4-section completeness, `qualifications -> raw_requirements`, `fullLocation`, `compensation`, `remote`/`hybrid` uncertainty).
   - Fix `apply_url` (`applyUrl` / `postingUrl` instead of `ref`) and `source_url` (`postingUrl`).
   - Opt `"smartrecruiters"` into `JobExtractionService` eligibility allowlist (`line 474`) and fallback requirements (`line 873`).
   - Add bounded/cached SmartRecruiters company logo extraction from a single posting page (`c.smartrecruiters.com/sr-company-logo-prod-*`), rejecting SmartRecruiters platform wordmarks.
3. **Monitoring Adapter & Direct-Board Router (`board_adapters.py`, `company_board_registry.py`, `direct_board_router.py`)**:
   - Implement `SmartRecruitersBoardAdapter` using `throttled_get()`, full sequential pagination (`limit=100`), atomic snapshot validation, listing-item full-hash fingerprinting, and Workable-style `MonitoredJobDetailState` bounded hydration + 6h rotating TTL revalidation (capped per poll so large 400–800 job boards hydrate cleanly without exhausting `per_host_concurrency_limit=3`).
   - Promote `"smartrecruiters"` from `PROVISIONAL_PROVIDERS` to `MONITORABLE_PROVIDERS`.
   - Add `probe_smartrecruiters_board()` in `direct_board_router.py` (bounded detail cap e.g. `max_detail_fetches=15`, never registering 0-job results).
4. **Offline Deterministic Tests & Zero-Serper Cache Repair (if authorized in Step 45)**:
   - Comprehensive unit/integration tests in `tests/test_smartrecruiters_pipeline.py` using the captured real fixtures (pagination, `200` empty unknown company, partial-page failure preservation, `ref` hydration, `applyUrl`/`eligibility`, case alignment, `throttled_get` resilience).

### Explicitly Known Unknowns Remaining
- Exact `api.smartrecruiters.com` HTTP `429` burst rate-limit threshold (no `X-RateLimit-*` headers returned).
- Behavior on boards with `> 1,000` postings (latency/drift across >10 sequential pages).
- Whether any company uses custom career-site domains without hosting posting detail pages on `jobs.smartrecruiters.com` (affecting HTML logo fallback, though API `api.smartrecruiters.com/v1/companies/{id}/postings` still works).

---

## 12. Fixture Inventory & Provenance

All 7 new fixtures under `tests/fixtures/real/smartrecruiters/` are unmodified authentic responses captured sequentially via unauthenticated `GET` requests (`0` credentials/sensitive headers):

| Fixture File | Request URL | UTC Capture Time | HTTP | Bytes | Company Identifier | Auth Required | Purpose / Coverage |
|---|---|---|---:|---:|---|---|---|
| `nearmap_postings.json` | `https://api.smartrecruiters.com/v1/companies/Nearmap/postings?limit=100&offset=0` | `2026-11-15T20:42:20Z` | `200` | `49,091` | `Nearmap` | No | Single-page listing (`totalFound: 36`), `ref` URLs, `remote`/`hybrid` flags |
| `nearmap_744000161158698_detail.json` | `https://api.smartrecruiters.com/v1/companies/Nearmap/postings/744000161158698` | `2026-11-15T20:42:21Z` | `200` | `10,141` | `Nearmap` | No | Detail fetched via `ref`; `jobAd.sections`, `postingUrl`, `applyUrl`, `active` |
| `scalable_postings_p0.json` | `https://api.smartrecruiters.com/v1/companies/ScalableGmbH/postings?limit=100&offset=0` | `2026-11-15T20:42:06Z` | `200` | `149,005` | `ScalableGmbH` | No | Multi-page listing page 0 (`offset=0`, `100` of `109` items) |
| `scalable_postings_p1.json` | `https://api.smartrecruiters.com/v1/companies/ScalableGmbH/postings?limit=100&offset=100` | `2026-11-15T20:42:07Z` | `200` | `13,367` | `ScalableGmbH` | No | Multi-page listing page 1 (`offset=100`, remaining `9` of `109` items) |
| `wise_744000161639339_detail.json` | `https://api.smartrecruiters.com/v1/companies/Wise/postings/744000161639339` | `2026-11-15T20:42:22Z` | `200` | `9,457` | `Wise` | No | Detail fetched via `ref`; structured `compensation` absent from listing |
| `nonexistent_company_postings.json` | `https://api.smartrecruiters.com/v1/companies/nonexistent-bottom-pot-probe-99999/postings?limit=100&offset=0` | `2026-11-15T20:42:14Z` | `200` | `52` | `nonexistent-bottom-pot-probe-99999` | No | Edge case: unknown company returns `200` empty (`totalFound: 0`) |
| `nearmap_posting_404.json` | `https://api.smartrecruiters.com/v1/companies/Nearmap/postings/999999999999999` | `2026-11-15T20:43:11Z` | `404` | `195` | `Nearmap` | No | Edge case: missing posting returns `404` `RESOURCE_NOT_FOUND` JSON |

*(Pre-existing fixtures preserved untouched: `744000155825759.json`, `744000155937924.json`, `744000155969710.json`, `job_3743990000051828.json`.)*

---

## 13. Verification, Cache Integrity & Provenance

- **Existing SmartRecruiters, Parser & Monitoring Regression Suite (`python -m pytest tests/test_smartrecruiters_pipeline.py tests/test_real_api_fixtures.py tests/test_salary_parser.py tests/test_ats_url_parser.py tests/test_url_normalizer.py tests/test_company_board_registry.py tests/test_board_monitor.py -q`)**: **`205 passed, 4 warnings in 6.05s`** (offline deterministic tests; 0 live network calls).
- **Fixture Offline Schema Check**: All `7` new JSON fixtures under `tests/fixtures/real/smartrecruiters/` validated cleanly as UTF-8 JSON dictionaries offline.
- **`git diff --check`**: Exited `0` with zero whitespace/trailing errors.
- **Operational Cache Integrity (`data/cache.sqlite`)**: Verified untouched (`14,143,488` bytes, `LastWriteTimeUtc: 2026-11-14T14:33:06Z`); `serper_daily_budget` latest entry remains `2026-11-12` (`call_count: 2`). **`0` Serper credits spent.**
- **Branch**: `step/44-smartrecruiters-monitoring-investigation`
- **Base Commit (`main`)**: `9b7913fe9bae69bd0cfe91ae54c5332a1a6f058a`
- **Pull Request**: `https://github.com/richmondsogo/bottom-pot/pull/41` (opened; not merged per MERGE_POLICY)
- **First Commit SHA**: `17f2a5021c17b2db86c81d8a5ef679799b580f09`
- **Final Doc Commit SHA**: Recorded in follow-up provenance commit (`HEAD` after push)
- **Merge Commit SHA**: Pending (do not merge without explicit authorization)
