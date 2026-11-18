# Step 50: Breezy HR Monitoring & Direct-Routing Investigation

**Status:** Investigation Complete — **`Rejected` (`Unsuitable`)** & Active Integration Code Cleaned Up (PR #50)  
**Date:** 2026-11-18  
**Branch:** `step/50-breezy-monitoring-investigation`  
**Base Commit (`main`):** `20b266474a91ba24ec98dfcea40a1644c8f232ce` (after merging PR #48 and PR #49)  
**Target Provider Evaluated:** `breezy` (Breezy HR, `https://{slug}.breezy.hr`)  
**Decision:** **`Unsuitable`** / **`Rejected`** (Implementation rejected; pre-existing active `breezy` code removed per [Section 26](#26-rejected-provider-cleanup--repository-normalization) and [`docs/job-source-catalog.md`](../job-source-catalog.md))  
**Confidence:** High (grounded in isolated read-only operational DB inventory, official `developer.breezy.hr` documentation, and bounded live probes across 12 diverse boards totaling 161 postings)

---

## 1. Executive Summary

Step 50 investigated whether **Breezy HR (`breezy`)** offers enough technically reliable and strategically valuable job discovery and monitoring coverage for Bottom Pot's target audience—remote developers, Nigerian/African applicants, and early-career/software engineers—to justify implementing a Breezy monitoring adapter, direct router, and discovery pipeline.

**Conclusion: Do NOT implement Breezy monitoring in Step 51.** While Breezy's undocumented public `GET https://{slug}.breezy.hr/json` endpoint is technically parseable (returning an unauthenticated, unpaginated JSON array with weak `ETag`/`304` support and immutable 12–14 character hex IDs), fresh empirical evidence invalidates the runner-up optimism from Step 48:

1. **Zero operational board or URL-cache footprint (Population A — `serper_cache` footprint)**: An isolated read-only inspection of `data/cache.sqlite` shows **`0` `company_boards` rows**, **`0` `monitored_jobs` rows**, and **`0` `url_cache` rows** (of 524 total) for `breezy`. Even `serper_cache` contains only **`19` cached `breezy.hr` URLs across `9` employer hosts**, **`5` of which are `/apply` URL duplicates**, leaving **`14` unique cached postings** after canonical duplicate removal; meanwhile `4` of `8` cached Breezy Serper queries (`"React engineer" "remote"`, `"software engineer Lagos"`, `"Python Engineer"`, `"Machine Learning Engineer"`) returned **`0` organic results**.
2. **Poor audience fit and contradictory `"remote"` metadata across live samples (Populations B & C)**:
   - **Population B — Live `/json` samples of the `9` employers discovered in `serper_cache` (`142` live postings)**: Two US federal government contractors—`vetsez` (`66`) and `expression-networks` (`18`)—account for **`84/142` (`59.2%`)** of those live postings, while the broader US-restricted employer group (`vetsez` `66`, `expression-networks` `18`, `beli` `13`, `incubator-lab` `3`, `soko-glam` `2`, `indinterns` `1`) accounts for **`103/142` (`72.5%`)**. Another **`26/142` (`18.3%`)** are onsite Canadian civil/geotechnical roles (`pri`), and the remaining `13/142` are `vigil-global` (`11`, primarily Brazil plus `2` legacy worldwide consulting roles) and `solvative` (`2`, India). **`0/142`** are Nigeria/Africa-targeted or accessible remote junior/intern SWE roles.
   - **Population C — Expanded `12`-board live sample (`161` live postings across the `9` cache hosts + `3` web-discovered hosts `awarri`, `gozem`, `moneyphone`)**: Expanding the sample with three Africa/remote-oriented boards yielded only **`3/161` (`1.9%`)** `worldwide` listings (`2` legacy consulting roles on `vigil-global` and `1` stale `awarri` Senior AI Engineer listing with `/json` `published_date: 2025-10-31` and HTML JSON-LD `datePosted: 2025-02-11`) and **`0/161`** accessible remote junior/intern SWE roles.
   - **Contradictory remote metadata in inspected examples**: Across several inspected employer examples (`vetsez`, `incubator-lab`, `moneyphone`), Breezy `/json` fields `is_remote: true` and `remote_details: {"value": "remote", "label": "Fully remote, no location restrictions"}` were contradicted by HTML `JobPosting` JSON-LD `applicantLocationRequirements` (`US` or `NL`), EST schedule constraints, or US federal clearance requirements. While this does not establish that every Breezy board's remote label is false, it demonstrates that `/json` remote metadata alone cannot be trusted without detail-page verification.
3. **High scraping & maintenance cost for weak incremental value**: Unlike Personio (`/xml`) or Teamtailor (`/jobs.rss`), Breezy `/json` **omits job descriptions on `12/12` probed boards (`161/161` jobs)** and has **no single-job public JSON endpoint**. Hydrating descriptions requires **`1 + N` HTTP requests** per board via HTML detail pages, where some postings omit `JobPosting` JSON-LD entirely and expose unrendered `%LABEL_...%` template tokens (`vigil-global`), and missing/closed jobs return `HTTP 302 -> /` rather than `404`.
4. **Better strategic leverage elsewhere**: In `data/cache.sqlite`, **`7` of `8` already-implemented `MONITORABLE_PROVIDERS`** (`greenhouse` 34, `ashby` 21, `smartrecruiters` 13, `workable` 9, `teamtailor` 7, `personio` 1, plus `0` `monitored_jobs` for all except `lever`'s 160 active rows) are not yet producing monitored job inventory, and Bottom Pot's pre-cleanup `ats_url_parser.py` even carried a dead `_BREEZY_APPLY` regex targeting `apply.breezy.hr` (which fails DNS resolution with `getaddrinfo failed`). Active `breezy` code has now been removed (see Section 26).

---

## 2. Decision and Confidence

| Dimension | Assessment | Confidence | Basis |
|---|---|---|---|
| **Overall Decision** | **`Unsuitable`** (Do not implement Breezy monitoring) | **High** | Weak observed incremental value relative to implementation cost, `0` registered boards, undocumented `/json`, and `1 + N` HTML hydration cost |
| **Technical Feasibility (Isolated)** | *Feasible with significant constraints* | **High** | `12/12` boards returned valid JSON with weak `ETag`/`304`, but `/json` is undocumented, omits descriptions, and `/p/*` missing URLs return `302 -> /` |
| **Audience Strategic Value** | **Poor fit among discoverable sample** | **High** | **Pop. A (`serper_cache`)**: `19` cached URLs (`5` `/apply` dupes -> `14` unique cached jobs across `9` hosts). **Pop. B (`9` cache hosts live)**: `142` live jobs (`84/142` = `59.2%` US federal contractors, `103/142` = `72.5%` US-restricted, `26/142` = `18.3%` CA onsite civil/geotech, `0/142` Nigeria/Africa or remote junior SWE). **Pop. C (`12` boards live)**: `3/161` (`1.9%`) `worldwide`, `0/161` accessible remote junior SWE |
| **Incremental Value vs Personio** | **Weak observed ROI** | **High** | Personio already had `1` board + single-GET full XML descriptions; Breezy has `0` boards + `1 + N` HTML scraping + poor audience fit in the discoverable sample |

**Explicit separation of fact vs. assessment:**
- **Facts**: Measured HTTP responses, byte sizes, SHA-256 hashes, JSON schemas, `JobPosting` JSON-LD fields, `developer.breezy.hr` OpenAPI text, and read-only SQLite counts across the three separately tracked populations (`14` unique cached postings in `serper_cache`, `142` live postings across the `9` cache-discovered boards, and `161` live postings across the expanded `12`-board sample).
- **Assessments / Recommendations**: The `Unsuitable` verdict (grounded in observed poor audience fit and weak incremental value in this sample, without claiming every Breezy employer worldwide is unsuitable) and recommendation to prioritize seeding/enforcing geo-eligibility on existing `MONITORABLE_PROVIDERS` or investigating higher-fit remote/African candidates under formal reuse/eligibility checks.

---

## 3. Research Methodology

1. **Repository & Architecture Audit**: Inspected `AGENTS.md`, `BUILD_PROTOCOL.md`, `docs/adr/0030-operational-sqlite-database-isolation-and-destructive-test-safety.md`, `docs/steps/46-teamtailor-monitoring-investigation.md`, `docs/steps/48-personio-monitoring-investigation.md`, `docs/steps/49-personio-monitoring-pipeline.md`, and source modules (`ats_url_parser.py`, `ats_page_enricher.py`, `board_adapters.py`, `board_monitor.py`, `company_board_registry.py`, `direct_board_router.py`, `search_pipeline.py`, `url_normalizer.py`, `work_model.py`, `config.py`, `query_builder.py`, `http_resilience.py`).
2. **Isolated Read-Only Operational DB Inventory**: Copied `data/cache.sqlite`, `data/cache.sqlite-wal`, and `data/cache.sqlite-shm` into a temporary OS directory outside the repository and opened the copy with `sqlite3.connect(uri, uri=True)` (`?mode=ro`). Never instantiated `CacheStore`, `CompanyBoardRegistry`, or FastAPI `app`, and never opened operational files in `data/`.
3. **Official Documentation Inspection**: Fetched `https://developer.breezy.hr/llms.txt`, `customer-guide.md`, `listpositions.md`, and `getposition.md`, plus searched `help.breezy.hr` for career-portal embeds, custom domains, and public feeds.
4. **Bounded Sequential Live HTTP Probes**: Selected **12 real Breezy HR employer boards** (`9` from Bottom Pot's `serper_cache` + `3` African/global-remote boards from public search) and executed sequential, unauthenticated, read-only `GET` requests (`follow_redirects=False`, 12s timeout, `3 MiB` response cap, `0.25–0.3s` inter-request pause) covering board `/json`, conditional `If-None-Match`, pagination query parameters, board HTML `/`, job detail HTML `/p/{friendly_id}`, `/p/{id}` short-URL variants, `/apply` suffix, `apply.breezy.hr`, `http://` redirect, alternate feed paths (`/rss`, `/jobs.rss`, `/xml`), and an unknown tenant.
5. **Protected Asset Hash Verification**: Recorded byte sizes and SHA-256 checksums of all `data/` operational files before starting and after completing all investigation work (`subscriptions.csv` was not present in the workspace).

---

## 4. Probe Boundaries and Safety Controls

- **Serper credits consumed**: **`0`** (`serper_cache` inspected read-only via isolated copy; no paid search API called).
- **Employer boards probed**: **`12`** (respecting the maximum 12-board cap).
- **Concurrency**: **`1`** (strictly sequential single-client execution with `0.25–0.30s` sleep between requests).
- **Request timeout**: **`12.0s`** (`httpx.Client(timeout=12.0, follow_redirects=False)`).
- **Response size limit**: **`3,145,728` bytes (`3 MiB`)**, matching `settings.max_response_bytes` in `src/config.py:45`. No probe truncated (`truncated=False` across all responses; largest payload was `vetsez` HTML board at `95,586` bytes and `/json` at `74,863` bytes).
- **Redirects**: `follow_redirects=False` on every probe to observe `302` behavior directly without silent redirection.
- **No production side effects**: Zero live monitoring runs, zero cache refreshes, zero Ashby/Lever/Greenhouse repairs, zero edits to `src/`, `tests/`, or `data/`.

---

## 5. Official API / Documentation Evidence

Direct inspection of `https://developer.breezy.hr/llms.txt` (`2026-11-18T15:24:42Z`, HTTP `200`, `21,731` bytes, SHA-256 `b4db61437551f86234f42f025b329f80cf6a2b6a332d65deeea9349c4daa9efd`) and linked OpenAPI v3 specifications (`listpositions.md`, `getposition.md`, `customer-guide.md`) establishes:

1. **Official API is authenticated v3 (`https://api.breezy.hr/v3`)**:
   - All documented endpoints require either a Personal Access Token (`Authorization: Bearer breezy_pat_<token>` or bare token) or session token from `POST /v3/signin` (`email` + `password`).
   - Only `GET /v3/health` is unauthenticated (`200 OK`, plain text `OK`).
   - Documented rate limit (v3 API): **100 requests/minute per access token** (`300 req/min` per customer for partner keys), emitting `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`, and `HTTP 429` with `Retry-After`.
   - Documented ID format (`listpositions.md`): `"All resource IDs are 12–14 character lowercase hex strings (e.g. a3f9c1d2e4b5). EU-region resources use 14-character IDs ending in 01."`
   - Documented webhooks (`customer-guide.md`): Pro plan only, max 10 endpoints/company, HMAC-SHA256 `X-Hook-Signature` (candidate events, not public multi-tenant job board discovery).
2. **`https://{slug}.breezy.hr/json` is NOT documented in `developer.breezy.hr`**:
   - Neither `llms.txt` nor the v3 OpenAPI spec mentions `{company}.breezy.hr/json`, its schema, pagination limits, or rate limits.
   - Breezy's Help Center (`help.breezy.hr`) officially documents **Career Portal** customization, **Embed Widget** (`Company Settings -> Career Site -> Embed Widget`), and **Custom Domain / CNAME** mapping (requiring a request to `support@breezyhr.com`).
   - **Implication**: Any reliance on `https://{slug}.breezy.hr/json` rests purely on **empirical portal behavior**, not an officially supported or versioned public API contract.

---

## 6. Endpoint Schema

Empirical observation across **`12 / 12` probed boards (`161` total items)** at `GET https://{slug}.breezy.hr/json`:

- **Response envelope**: Top-level JSON array `[ ... ]` (`Content-Type: application/json; charset=utf-8`).
- **Observed top-level object keys** (identical key set on all 12 boards):
  - `id` (`str`): 12-char hex (e.g., `"957cfba3613f"`) or 14-char hex ending in `"01"` (e.g., `"ddf6ace039b401"`).
  - `friendly_id` (`str`): `"{id}-{title-slug}"` (e.g., `"ddf6ace039b401-net-developer-remote-opportunity"`).
  - `name` (`str`): Job title.
  - `url` (`str`): Canonical job detail URL, `https://{slug}.breezy.hr/p/{friendly_id}`.
  - `published_date` (`str`): ISO-8601 UTC timestamp with milliseconds (`"2026-11-02T19:27:21.964Z"`).
  - `type` (`dict`): `{"id": str, "name": str}` — observed `id` values: `fullTime`, `partTime`, `temporary`, `contract`, `other`; note `name` is localized (`"Temps plein"` on `gozem`).
  - `department` (`str | null`): Free-text department or `""` / `null` (populated inconsistently: `0/66` on `vetsez`, `11/18` on `expression-networks`, `11/13` on `beli`, `10/17` on `gozem`).
  - `salary` (`str`): Free-text string or `""` (e.g., `"$200,000 – $230,000 / year"`, `"$1,000 – $2,000 / month"`, `"$84,700+ / year"`; populated on only `22/161` = `13.7%` of jobs across `5/12` boards).
  - `company` (`dict`): `{"name": str, "logo_url": str | null | "", "friendly_id": str, "isMultipleLocationsEnabled": bool}` — note `logo_url` may be `null`, `""` (`incubator-lab`), or a CDN URL on `gallery-cdn.breezy.hr` / `attachments-cdn.breezy.hr` (often with unencoded spaces, e.g., `.../Asset 2HappyEmploye.png`).
  - `location` (`dict`): Primary location object containing:
    - `country`: `{"id": str, "name": str}` — ISO-2 country code (`"US"`, `"IN"`, `"BR"`, `"CA"`, `"NL"`, `"TG"`, `"CM"`, `"GA"`, `"CG"`, `"BJ"`) OR sentinel **`"worldwide"`** (`{"id": "worldwide", "name": "Worldwide"}`); note country names can be localized (`"Países Bajos"` for `NL`, `"Cameroun"` for `CM`).
    - `state` (`dict`, optional): `{"id": str, "name": str}` (e.g. `TX` / `Texas`, `NH` / `Noord-Holland`).
    - `city` (`str`, optional).
    - `name` (`str`): Formatted label (`"Dallas, TX"`, `"United States"`, `"Worldwide"`, `"Brazil"`).
    - `is_remote` (`bool`): `true` or `false`.
    - `remote_details` (`dict`, optional, present when `is_remote=true`): Observed `value` enums:
      - `"remote"` -> `"Fully remote, no location restrictions"`
      - `"remote-location"` -> `"Fully remote, within chosen location(s)"`
      - `"hybrid"` -> `"Hybrid (Some remote, some in person)"`
    - `primary` (`bool`), `id` (`str`, optional), `streetAddress` (`dict`, optional, Google Places components or custom address), `isOther` (`bool`, optional).
  - `locations` (`list[dict]`): Array of location objects (`> 1` entry on `41/161` = `25.5%` of postings across `5` multi-location boards).
- **Critical omissions in `/json`**:
  - **No `description` / `body` / `summary` / `requirements` field** on any board (`0/12` boards, `0/161` jobs).
  - **No `category` / `experience` / `state` / `updated_date` fields** (unlike the authenticated v3 `/positions` endpoint).

---

## 7. Authentication Findings

- `GET https://{slug}.breezy.hr/json`, `GET https://{slug}.breezy.hr/`, and `GET https://{slug}.breezy.hr/p/{friendly_id}` are **100% unauthenticated**. No cookies, CSRF tokens, or API keys were required on any of the `12` probed boards.
- In contrast, `https://api.breezy.hr/v3/...` requires per-customer credentials (`breezy_pat_...` or email/password `/signin`) and is unusable for multi-employer public job monitoring.

---

## 8. Sample Board Results

Bounded sequential probes executed `2026-11-18T15:24:45Z`–`2026-11-18T15:25:16Z` UTC (`follow_redirects=False`, 12s timeout, `3 MiB` cap):

| # | Employer (Slug) | Source | Board URL & Endpoint | HTTP | Bytes | Jobs | `is_remote` | `worldwide` | SWE/Tech | Jr/Intern SWE | Desc in `/json` | ETag (`W/"..."`) | UTC Timestamp |
|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|---|
| 1 | VetsEZ (`vetsez`) | `serper_cache` | `https://vetsez.breezy.hr/json` | 200 | 74,863 | 66 | 64 | 0 | 51 | 1 (US-only) | No | `W/"1246f-xI575DRAaMknDtZV/xrd8fBZS4o"` | `15:24:45Z` |
| 2 | Expression (`expression-networks`) | `serper_cache` | `https://expression-networks.breezy.hr/json` | 200 | 26,504 | 18 | 3 (hybrid) | 0 | 16 | 1 (US-only) | No | `W/"6788-NmN2ZJ3VArRiIarXF/SI1sqhqDM"` | `15:24:51Z` |
| 3 | Solvative (`solvative`) | `serper_cache` | `https://solvative.breezy.hr/json` | 200 | 1,721 | 2 | 1 | 0 | 1 | 0 | No | `W/"6b9-j0x8zrwXGBEEHhB3JntrS3i3YRI"` | `15:24:53Z` |
| 4 | Beli (`beli`) | `serper_cache` | `https://beli.breezy.hr/json` | 200 | 13,123 | 13 | 1 | 0 | 5 | 2 (US-only) | No | `W/"3343-S5O5wmhYFKcIpVijNAeJxcUnBhI"` | `15:24:55Z` |
| 5 | Incubator Lab AI (`incubator-lab`) | `serper_cache` | `https://incubator-lab.breezy.hr/json` | 200 | 3,385 | 3 | 3 | 0 | 0 | 0 | No | `W/"d39-U7fC3N2TpGDwbf7KD6Cg7oMnZRM"` | `15:24:57Z` |
| 6 | TXP (`vigil-global`) | `serper_cache` | `https://vigil-global.breezy.hr/json` | 200 | 12,289 | 11 | 11 | 2 | 9 | 0 | No | `W/"3001-MpcklQ+tV+djO9SdlF63NUMNtr0"` | `15:25:00Z` |
| 7 | Indinterns (`indinterns`) | `serper_cache` | `https://indinterns.breezy.hr/json` | 200 | 855 | 1 | 1 | 0 | 1 | 0 | No | `W/"357-G7Ffeeu5GsTykEIW4/oIulyFxPE"` | `15:25:02Z` |
| 8 | PRI Consultants (`pri`) | `serper_cache` | `https://pri.breezy.hr/json` | 200 | 30,997 | 26 | 0 | 0 | 0 | 0 | No | `W/"7915-+VbOvXCtZIvtOBMbgOUPlShNN/I"` | `15:25:03Z` |
| 9 | Soko Glam (`soko-glam`) | `serper_cache` | `https://soko-glam.breezy.hr/json` | 200 | 1,785 | 2 | 1 (hybrid) | 0 | 0 | 0 | No | `W/"6f9-Eik6n3nRXc19VBTUz5kbK9lv+Rk"` | `15:25:07Z` |
| 10 | Awarri (`awarri`) | Web (Nigeria/AI) | `https://awarri.breezy.hr/json` | 200 | 844 | 1 | 1 | 1 | 1 | 0 | No | `W/"34c-amyLUMj6QkLReSAg8AqcW6BJME0"` | `15:25:08Z` |
| 11 | Gozem (`gozem`) | Web (Africa) | `https://gozem.breezy.hr/json` | 200 | 13,080 | 17 | 1 | 0 | 1 | 0 | No | `W/"3318-pIEnDLUokoBtV5lTGi2dBtV7Vzc"` | `15:25:09Z` |
| 12 | MoneyPhone (`moneyphone`) | Web (Remote SWE) | `https://moneyphone.breezy.hr/json` | 200 | 2,327 | 1 | 1 | 0 | 1 | 0 | No | `W/"917-5Yl9weArQc/aQFwMpvkGTzTXGCc"` | `15:25:16Z` |
| **Total (Pop. C)** | **12 boards** | **9 DB + 3 Web** | — | **12/12 `200`** | **171,772** | **161** | **88** (`16` `remote` + `68` `remote-location` + `4` `hybrid`) | **3** | **86** | **4 (0 global/NG)** | **0/12** | **12/12 present** | — |

*(Note: Rows `#1–#9` form **Population B** — `142` live postings across the `9` employers found in `serper_cache`; adding rows `#10–#12` (`19` live postings) forms **Population C** (`161` live postings). No empty `0`-job board occurred among the `12` sampled boards; see Section 14 for empty-board handling assumptions.)*

---

## 9. Description-Fetch Behavior

- **Listing endpoint**: `/json` never includes job descriptions (`0/12` boards, `0/161` items).
- **JSON detail endpoint absence**: Probed on `vetsez` (`https://vetsez.breezy.hr/p/ddf6ace039b401-net-developer-remote-opportunity`):
  - `GET /p/{friendly_id}/json` -> **`HTTP 302`** (`Location: /`, `30` bytes)
  - `GET /p/{friendly_id}.json` -> **`HTTP 200` `text/html`** (`33,294` bytes — returns the same HTML detail page, not JSON)
  - `GET /p/{friendly_id}?format=json` -> **`HTTP 200` `text/html`** (`33,293` bytes — returns the same HTML detail page, not JSON)
  - `GET /p/ddf6ace039b401` and `GET /p/ddf6ace039b401-wrong-slug` -> **`HTTP 200` `text/html`** (`33,293` bytes each)
  - `GET /p/ddf6ace039b401-net-developer-remote-opportunity/apply` -> **`HTTP 200` `text/html`** (`51,700` bytes — application form page)
- **Required pattern (`1 + N`)**: Obtaining descriptions requires `1` GET to `/json` plus up to `N` HTML GETs to `https://{slug}.breezy.hr/p/{friendly_id}`. Across the **`6` distinct canonical detail pages** whose raw payload byte length was recorded (`breezy_probe.py` and `breezy_anomaly_check.py`), HTML detail sizes ranged from **`21,686` bytes (`21.7 KB`) to `35,795` bytes (`35.8 KB`)** (plus `33,293–33,294` bytes on the `4` HTTP-200 URL-variant probes of `vetsez` `ddf6ace039b401`, and `51,700` bytes on its `/apply` page).

### 9.1 Reconciled HTML Detail-Page Accounting (`10` Distinct Job Detail URLs)

Across three sequential probe runs (`breezy_probe.py` at `15:25Z`, `breezy_followup.py` at `15:27Z`, and `breezy_anomaly_check.py` at `15:28Z`), **10 distinct canonical job detail URLs** spanning `7` employers were fetched (`12` total HTTP `GET` requests, because `awarri` `3dfc125ed8b401` and `vigil-global` `c4035bc588f101` were each requested twice). **`8` of `10` distinct detail pages contained `<script type="application/ld+json">` with `@type: "JobPosting"`**, while **`2` of `10`** (`vigil-global`) omitted JSON-LD completely:

| # | Host (`slug`) | Job Title & Canonical URL | Script(s) / UTC | HTTP Status | Logged Bytes | In `21.7–35.8 KB` Sample? | `JobPosting` JSON-LD | Unrendered `%...%` DOM Tokens |
|---:|---|---|---|---:|---:|---|---|---|
| 1 | `vetsez` | `.Net Developer (Remote Opportunity)` — `/p/ddf6ace039b401-net-developer-remote-opportunity` | `breezy_probe.py` (`15:25:29Z`) | `200` | `33,294` (`33.3 KB`) | Yes | **Present** (`applicantLocationRequirements: US`) | Not dumped (extracted JSON-LD `description`, `8,088` chars) |
| 2 | `solvative` | `Data Engineer` — `/p/d9bd06a44f43-data-engineer` | `breezy_probe.py` (`15:25:34Z`) | `200` | `27,907` (`27.9 KB`) | Yes | **Present** (`addressCountry: IN`) | Not dumped (extracted JSON-LD `description`, `6,551` chars) |
| 3 | `incubator-lab` | `Content Manager, Social` — `/p/ba5c05cbcdc6-content-manager-social` | `breezy_probe.py` (`15:25:35Z`) | `200` | `35,795` (`35.8 KB`) | Yes | **Present** (`applicantLocationRequirements: US`) | Not dumped (extracted JSON-LD `description`, `9,576` chars) |
| 4 | `awarri` | `Senior AI Engineer (WAT Remote)` — `/p/3dfc125ed8b401-senior-ai-engineer-wat-remote` | `breezy_probe.py` (`15:25:38Z`), `breezy_followup.py` (`15:27:34Z`) | `200` / `200` | `21,686` (`21.7 KB`; not logged in followup) | Yes | **Present** (`applicantLocationRequirements: worldwide`) | Not dumped (extracted JSON-LD `description`, `4,208` chars) |
| 5 | `vigil-global` | `Data / ML Engineer` — `/p/c4035bc588f101-data-ml-engineer` | `breezy_followup.py` (`15:27:30Z`), `breezy_anomaly_check.py` (`15:28:33Z`) | `200` / `200` | `22,875` (`22.9 KB` in anomaly check) | Yes | **Absent** (`0` `ld+json` `<script>` tags) | **Present** (`%HEADER_COMPANY_WEBSITE%`, `%HEADER_EMPLOYEES%`, `%LABEL_POSITION_TYPE_FULL_TIME%`, `%LABEL_POSITION_TYPE_REMOTE_ANY%`, `%BREADCRUMB_JOB_OPENINGS%`, `%BUTTON_APPLY_TO_POSITION%`) |
| 6 | `vigil-global` | `Frontend Developer – React / TypeScript` — `/p/80505a89809b01-frontend-developer-react-typescript` | `breezy_followup.py` (`15:27:32Z`) | `200` | Not persisted in script output | No | **Absent** (`0` `JobPosting` JSON-LD scripts) | Not dumped (DOM body not printed by `breezy_followup.py`) |
| 7 | `indinterns` | `Senior Webflow Developer` — `/p/ba5efb549225-senior-webflow-developer` | `breezy_followup.py` (`15:27:33Z`) | `200` | Not persisted in script output | No | **Present** (`applicantLocationRequirements: US`) | Not dumped |
| 8 | `moneyphone` | `Senior Software Engineer` — `/p/8ff87449dcdd01-senior-software-engineer` | `breezy_followup.py` (`15:27:38Z`) | `200` | Not persisted in script output | No | **Present** (`applicantLocationRequirements: NL`) | Not dumped |
| 9 | `vigil-global` | `Senior CA GEN Consultant` — `/p/633c42c0d74e01-senior-ca-gen-consultant` | `breezy_anomaly_check.py` (`~15:28:35Z`) | `200` | `26,796` (`26.8 KB`) | Yes | **Present** (`2` `ld+json` `<script>` tags incl. `JobPosting`) | **Present** (`%HEADER_COMPANY_WEBSITE%`, `%HEADER_EMPLOYEES%`, `%LABEL_POSITION_TYPE_REMOTE%`, `%LABEL_POSITION_TYPE_FULL_TIME%`, `%BREADCRUMB_JOB_OPENINGS%`, `%BUTTON_APPLY_TO_POSITION%`) |
| 10 | `vetsez` | `HealthShare Engineer (Remote Opportunity)` — first `remote_details.value == "remote"` item (`vs_rem[0]["url"]`; Tampa, FL location ID `2312519e75fe`) | `breezy_anomaly_check.py` (`~15:28:37Z`) | Parsed HTML (`200` implied; exact status/bytes not printed) | Not persisted in stdout log | No | **Present** (`applicantLocationRequirements: US`) | Not dumped |

- **Evidence limitations explicitly recorded**:
  1. For row #10 (`vetsez` `HealthShare Engineer (Remote Opportunity)`), `breezy_anomaly_check.py` fetched `vs_rem[0]["url"]` dynamically and logged the job title, Tampa FL location ID (`2312519e75fe`), JSON-LD `applicantLocationRequirements`, and 400-char description preview in stdout, without persisting the exact `/p/{friendly_id}` path, integer HTTP status code, or response byte length.
  2. For rows #6–#8 (`breezy_followup.py`), byte lengths and raw DOM body text were not written to `breezy_followup_results.json`.
  3. Because raw DOM body text was only dumped on rows #5 and #9 (`vigil-global`), where **both (`2/2`)** exposed unrendered `%HEADER_...%` / `%LABEL_...%` / `%BREADCRUMB_...%` / `%BUTTON_...%` template tokens even when JSON-LD was present (row #9), we cannot determine from retained logs how frequently other employers' detail templates expose unrendered tokens; however, the fact that **`2/10`** detail pages lacked `JobPosting` JSON-LD entirely proves any DOM fallback parser would have to strip `%...%` tokens and handle missing JSON-LD defensively.

---

## 10. Pagination Findings

Empirical verification on the largest sampled board (`vetsez`, `66` jobs, `74,863` bytes, SHA-256 `bc5a45815a6ff9627cb2a4b68809deab45df1065ff2d1c76c9fb55a33c716b9e`):

- `GET /json?page=2` -> `200`, `74,863` B, `66` items, **identical SHA-256** (`matches_unpaginated_sha=True`)
- `GET /json?limit=1` -> `200`, `74,863` B, `66` items, **identical SHA-256**
- `GET /json?offset=1` -> `200`, `74,863` B, `66` items, **identical SHA-256**
- **Cross-check vs HTML**: `GET https://vetsez.breezy.hr/` returned `200` (`95,586` B) with **`66` unique `/p/...` anchor links**, matching `/json` (`66` items) `1:1`.
- **Conclusion**: `/json` is an **unpaginated full-board dump** for boards up to at least `66` jobs (unlike the authenticated v3 API, which supports opt-in `page_size`). Because `/json` is undocumented, an undocumented upper bound (e.g., 100 or 500 jobs) cannot be ruled out without official documentation.

---

## 11. Identity and Canonicalization

- **Board token (`board_token`)**: Lowercase Breezy portal subdomain `{slug}` (`https://{slug}.breezy.hr`).
- **Job identifier**: Immutable `item["id"]` (12–14 lowercase hex characters; e.g., `ddf6ace039b401`), NOT `friendly_id`. Live probes on `vetsez` proved:
  - `/p/ddf6ace039b401` (bare hex ID) -> `200`, `33,293` B
  - `/p/ddf6ace039b401-wrong-slug` (arbitrary title slug) -> `200`, `33,293` B
  - `/p/ddf6ace039b401-net-developer-remote-opportunity` -> `200`, `33,294` B
  - `/p/ddf6ace039b401-net-developer-remote-opportunity/apply` -> `200`, `51,700` B
- **Pre-cleanup Bottom Pot parser defects discovered (subsequently removed in Section 26)**:
  1. **Dead `apply.breezy.hr` parser**: Pre-cleanup `src/project_files/ats_url_parser.py` (`_BREEZY_APPLY`) matched `apply.breezy.hr/p/...` and returned `company_slug="breezy"` (which `is_valid_board_slug` rejected). Live probes to `https://apply.breezy.hr/` and `https://apply.breezy.hr/p/...` failed DNS resolution (`ConnectError: [Errno 11001] getaddrinfo failed`).
  2. **Slug-polluted `job_id` in `parse_ats_url`**: Pre-cleanup `_BREEZY_SUBDOMAIN` captured the mutable `{hex}-{title-slug}` string rather than isolating the immutable `{hex}` ID.
  3. **Missing `url_normalizer.py` rule**: `url_normalizer.py` had no Breezy `ProviderUrlRule`, so `/p/{friendly_id}` and `/p/{friendly_id}/apply` failed to deduplicate (`5` of `19` URLs in `serper_cache` are `/apply` duplicates).
  4. **Custom domains**: Breezy supports CNAME custom domains via `support@breezyhr.com`, which subdomain regexes cannot detect without Teamtailor-style HTML inspection.

---

## 12. HTTP Behavior

- **CDN / Proxy stack**: Amazon CloudFront + Envoy (`server: envoy`, `via: ... cloudfront.net`), Express upstream (`x-powered-by: Express`).
- **Latency**: `815 ms` – `6,151 ms` across `12` boards (note `vetsez` `6.1s` and `gozem` `6.1s` exceed `settings.ats_request_timeout_seconds = 5` in `src/config.py:22`!).
- **HTTP -> HTTPS redirect**: `GET http://vetsez.breezy.hr/json` -> `302` `Location: https://vetsez.breezy.hr/json`.
- **Unknown tenant**: `GET https://nonexistent-bottom-pot-probe-99999.breezy.hr/json` -> **`HTTP 404`** (`3,265` B HTML `"Career portal not found | Breezy HR"`, `cache-control: public, max-age=300`).
- **Missing / closed job URL**: `GET https://vetsez.breezy.hr/p/nonexistent-bottom-pot-99999` -> **`HTTP 302`** (`30` B, **`Location: /`**). Using `follow_redirects=True` would silently land on the `200 OK` career homepage and cause false-positive enrichment!
- **Rate-limit headers**: Public `/json` and `/p/*` responses emitted **no** `X-RateLimit-*` headers and triggered **`0` HTTP 429s / WAF challenges** across ~35 sequential requests (`developer.breezy.hr/llms.txt` via Cloudflare emitted `X-RateLimit-Limit: 100`). Unauthenticated burst limits on CloudFront/Envoy remain undocumented.

---

## 13. Conditional Request Findings

- **ETag emitted**: `12 / 12` `/json` `200 OK` responses and all HTML responses emitted weak Express-style ETags (`W/"<hex_len>-<hash>"`), with no `Last-Modified` or `Cache-Control` headers on `/json`.
- **`304 Not Modified` verified**:
  - `vetsez` (`If-None-Match: W/"1246f-xI575DRAaMknDtZV/xrd8fBZS4o"`) -> **`HTTP 304` (`0` bytes)** at `15:25:17Z`.
  - `expression-networks` (`If-None-Match: W/"6788-NmN2ZJ3VArRiIarXF/SI1sqhqDM"`) -> **`HTTP 304` (`0` bytes)** at `15:25:20Z`.
- **Caveat for `1 + N` hydration**: A `304` on `/json` confirms the listing summary array did not change, **but** edits solely inside an existing job's HTML description (without changing `id`, `name`, `location`, `salary`, or `published_date`) will **not** invalidate `/json`'s ETag. Any `1 + N` adapter must maintain `MonitoredJobDetailState` TTL revalidation (`detail_revalidate_ttl_seconds`, matching `WorkableBoardAdapter` and `SmartRecruitersBoardAdapter`) rather than relying purely on `/json` `304`s.

---

## 14. Snapshot Completeness Analysis

Evaluating against `BoardMonitor` (`src/project_files/board_monitor.py:117-127`):

- **Complete board contents**: For typical SMB boards (`<= 66` jobs), `/json` returns all active openings in one response (verified `66 == 66` against HTML `/` on `vetsez`). Because `/json` is undocumented, any silent server-side cap (e.g. at 100 or 500 items) is **unverified**.
- **Stable job identity**: Yes, via `item["id"]` (12–14 hex chars).
- **Empty board distinction**: All `12` sampled boards had `>= 1` job (`1` to `66`), so an empty board's `/json` payload (expected `[]`, 2 bytes, `200 OK`) was **not directly observed**. A naive adapter must NOT mark jobs closed on `[]` without verifying HTML `/` shows `0` `/p/` links AND requiring `missing_confirmation_threshold >= 2`.
- **Failure vs. empty isolation**: `404` HTML ("Career portal not found"), `302` redirects, `429`/`5xx`, oversized responses (`> max_response_bytes`), non-JSON payloads, non-list JSON, or items missing `id`/`name` MUST set `success=False, snapshot_complete=False`.
- **Closed jobs**: Closed jobs are removed from `/json`, and their `/p/{friendly_id}` page returns `302 -> /` (never `404`), so `follow_redirects=False` is mandatory in both board and detail-hydration paths.

---

## 15. Existing Bottom Pot Footprint

From isolated read-only inspection of `data/cache.sqlite` copy (`2026-11-18`, `14,016,512` bytes, SHA-256 `a7c88bb24d383813213342ea1a0990f0c7bf62b4c1308647fc18f834be028638`):

| Table / Metric | Breezy Footprint | Repository Context |
|---|---:|---|
| `company_boards` | **`0`** | `lever`: `36` (`2` verified, `34` candidate), `greenhouse`: `34`, `ashby`: `21`, `smartrecruiters`: `13` (`provisional`), `workable`: `9` (`provisional`), `teamtailor`: `7` (`unsupported` pre-Step-47 run), `personio`: `1` (`unsupported` pre-Step-49 run), `jobvite`: `1` (`unsupported`) |
| `monitored_jobs` | **`0`** | `lever`: `160` active, `1` closed; **all other 7 monitorable providers: `0`** |
| `url_cache` | **`0`** (of `524`) | `lever`: `219`, `smartrecruiters`: `87`, `greenhouse`: `54`, `workday`: `46`, `ashby`: `40`, `teamtailor`: `32`, `workable`: `30`, `jobvite`: `6`, `avature`: `4`, `jazzhr`: `3`, `personio`: `3` |
| `serper_cache` queries mentioning `breezy` | **`8`** (`4` with `0` hits) | Hits: `"Full Stack"` (8), `"developer"` (10), `"intern"` (5), `"Backend Engineer"` (2); **Zero hits**: `"React engineer" "remote"`, `"software engineer Lagos"`, `"Python Engineer"`, `"Machine Learning Engineer"` |
| `serper_cache` unique `breezy.hr` URLs | **`19`** across **`9` hosts** | **`14` unique postings** (`5` are `/apply` duplicates): `vetsez` (`6` URLs / `4` jobs), `pri` (`3`/`3`), `beli` (`2`/`1`), `indinterns` (`2`/`1`), `solvative` (`2`/`1`), `expression-networks` (`1`/`1`), `incubator-lab` (`1`/`1`), `soko-glam` (`1`/`1`), `vigil-global` (`1`/`1`) |
| `tests/fixtures/real/` | **`0`** files | `teamtailor`: `43`, `greenhouse`: `33`, `lever`: `22`, `workable`: `21`, `smartrecruiters`: `13`, `personio`: `9`, `avature`: `8`, `workday`: `7`, `jobvite`: `6` |

**Existing codebase hooks (at investigation start, prior to Section 26 cleanup)**:
- `src/project_files/config.py`: previously included `ATSConfig(name="breezy", site_operator="breezy.hr", label="Breezy HR")`.
- `src/project_files/ats_url_parser.py`: previously included `"breezy"` in `SUPPORTED_ATS_PATTERNS` / `_GENERIC_SLUG_STOPWORDS`, `_BREEZY_SUBDOMAIN`, and dead `_BREEZY_APPLY`; **no** `parse_breezy_board_root_url`.
- `src/project_files/company_board_registry.py`: `build_canonical_board_url("breezy", token)` previously returned `f"https://{token}.breezy.hr"` (now returns `None`).
- `frontend/src/lib/constants.ts`: previously listed `{ id: 'breezy', name: 'Breezy HR' }` in `ALL_PLATFORMS`.
- **Never present**: Not in `MONITORABLE_PROVIDERS`, `PROVISIONAL_PROVIDERS`, `BOARD_ADAPTERS`, `direct_board_router.py`, `search_pipeline.py` board-root registration, `url_normalizer.py`, or `ats_page_enricher.py` special rules.

---

## 16. Discovery and Routing Opportunities

- **Why `company_boards` has `0` Breezy rows**:
  1. `search_pipeline.py:361-447` lacks `parse_breezy_board_root_url`, so board-root hits fall into `platform in SUPPORTED_ATS_PATTERNS` and are dropped (`Dropping non-job URL`).
  2. `_BREEZY_APPLY` resolves `apply.breezy.hr` to `company_slug="breezy"`, which `is_valid_board_slug` rejects.
  3. Live Serper coverage for Breezy on Nigerian/modern SWE queries is sparse (`4/8` cached Breezy queries returned `0` results).
- **Direct board routing (`probe_direct_boards`)**: Adding `probe_breezy_board(slug)` would let query-extracted slugs (e.g., `"awarri"`) probe `https://{slug}.breezy.hr/json`, **but** without descriptions in `/json` it would either emit description-less listings or add `1 + N` HTML latency to live `/search` SSE streams!

---

## 17. Audience-Value Analysis

Across the entire investigation, **three distinct job populations** are evaluated separately against Bottom Pot's target users (**Nigerian developers, African applicants, globally eligible remote developers, and junior/intern/entry-level SWEs**) so cached search-result counts are never conflated with live board totals:

- **Population A (`serper_cache` search-cache footprint)**: `19` cached Breezy URLs across `9` employer hosts (`5` `/apply` duplicates), leaving **`14` unique cached postings**.
- **Population B (Live `/json` sample of the `9` cache-discovered employers)**: **`142` live postings** (`vetsez` `66`, `pri` `26`, `expression-networks` `18`, `beli` `13`, `vigil-global` `11`, `incubator-lab` `3`, `solvative` `2`, `soko-glam` `2`, `indinterns` `1`).
- **Population C (Expanded `12`-board live `/json` sample — `9` cache hosts + `3` web-discovered hosts `awarri`, `gozem`, `moneyphone`)**: **`161` live postings** (`142` + `19`: `gozem` `17`, `awarri` `1`, `moneyphone` `1`).

### 17.1 Contradictory `"Remote"` Metadata in Inspected Employer Examples (Population C: `161` Live Postings)

- Across all `12` live boards (`161` postings), `88/161` (`54.7%`) set `is_remote: true`: **`16/161` (`9.9%`)** carry `remote_details.value = "remote"` (`"Fully remote, no location restrictions"`), **`68/161` (`42.2%`)** carry `"remote-location"` (`"Fully remote, within chosen location(s)"`), and **`4/161` (`2.5%`)** carry `"hybrid"`.
- **Inspecting HTML `JobPosting` JSON-LD and descriptions showed contradictory eligibility restrictions on several inspected examples**:
  - `vetsez` (`64` `is_remote: true`: `5` `"remote"`, `59` `"remote-location"`): All `66/66` `/json` entries specify `country.id = "US"`; even its `5` `"Fully remote, no location restrictions"` postings (e.g., `HealthShare Engineer (Remote Opportunity)`) emit HTML JSON-LD `applicantLocationRequirements: {"@type": "Country", "name": "US"}` and support **US Department of Veterans Affairs (VA) federal healthcare contracts**.
  - `incubator-lab` (`3` `is_remote: true`: `1` `"remote"`, `2` `"remote-location"`): Its `"Fully remote, no location restrictions"` `Content Manager, Social` posting emits HTML JSON-LD `applicantLocationRequirements: {"@type": "Country", "name": "US"}` and `"Schedule: Full-time | EST hours"`.
  - `moneyphone` (`1` `"remote"` SWE): `/json` labels the role `"Fully remote, no location restrictions"`, yet HTML JSON-LD emits **`applicantLocationRequirements: {"@type": "Country", "name": "NL"}`**.
  - `solvative` (`1` `"remote"` non-SWE, `1` onsite SWE): `country.id = "IN"` in `/json`; HTML detail confirms `"Location: Remote (India)"` (`Data Engineer` inspected).
  - `indinterns` (`1` `"remote-location"` Webflow): HTML JSON-LD emits `applicantLocationRequirements: {"@type": "Country", "name": "US"}`.
- **Scope of this finding**: This proves that `is_remote: true` and `"Fully remote, no location restrictions"` in Breezy `/json` are unreliable indicators of worldwide eligibility without detail-page verification. It does **not** prove that every Breezy employer worldwide uses false remote labels (for instance, `awarri` `3dfc125ed8b401` had `country.id = "worldwide"` in both `/json` and JSON-LD).

### 17.2 Population B Breakdown: Live `/json` Samples of the `9` Cache-Discovered Employers (`142` Postings)

1. **Two dominant US federal contractors (`vetsez` `66` + `expression-networks` `18`)**: **`84 / 142` (`59.2%`)**.
2. **Broader US-restricted employer group (`vetsez` `66`, `expression-networks` `18`, `beli` `13`, `incubator-lab` `3`, `soko-glam` `2`, `indinterns` `1`)**: **`103 / 142` (`72.5%`)** (`country.id = "US"`).
3. **Canadian onsite civil/geotechnical roles (`pri`)**: **`26 / 142` (`18.3%`)** (`0` software engineering roles).
4. **India (`solvative`)**: **`2 / 142` (`1.4%`)**.
5. **Brazil + Legacy `worldwide` consulting (`vigil-global`)**: **`11 / 142` (`7.7%`)** (`9` `BR` + `2` `worldwide`, both legacy mainframe `CA GEN` / legacy conversion consulting roles).
6. **Nigeria/Africa-targeted or accessible remote junior/intern SWE roles in Population B**: **`0 / 142` (`0.0%`)**.

### 17.3 Population C Breakdown: Adding the `3` Web-Discovered Africa/Remote Boards (`19` Jobs -> `161` Total)

- `awarri` (`1` job): `Senior AI Engineer (WAT Remote)` (`worldwide`, Nigeria-focused AI startup) — **`1` Nigeria/WAT-remote senior AI role** (`/json` `published_date: 2025-10-31T17:12:37.210Z`, >12 months old as of `2026-11-18`; HTML JSON-LD `datePosted: 2025-02-11`).
- `gozem` (`17` jobs): Francophone West/Central Africa (`TG` `7`, `GA` `6`, `CM` `2`, `CG` `1`, `BJ` `1`), **`0` Nigeria roles**, **`1` tech role** (`QA Engineer`, `remote`, `TG`).
- `moneyphone` (`1` job): `Senior Software Engineer` — `NL` country in both `/json` and JSON-LD `applicantLocationRequirements`.
- **Aggregate Population C yield (`161` live postings)**:
  - `86 / 161` (`53.4%`) SWE/Tech titles (title-classified).
  - **`3 / 161` (`1.9%`)** `worldwide` listings (`2` legacy consulting roles on `vigil-global` + `1` stale `awarri` Senior AI Engineer listing).
  - **`0 / 161` (`0.0%`)** accessible remote junior/intern SWE roles.

### 17.4 Early-Career & Junior/Intern Role Classification (`161` Live Postings)

Scanning all `161` job titles preserved in `breezy_followup_results.json` by seniority/early-career keywords (`Junior`, `Intern`, `Associate`, `EIT`, `Entry`, `Graduate`, `Trainee`) identifies **`12` explicit `Junior`/`Intern` titles (`7.5%`)** (plus `3` `Associate`/`EIT` titles: `Associate Proposal Manager` on `expression-networks`, `Structural EIT` on `pri`, and `Business Development Associate` on `gozem` — `15` early-career titles total, `9.3%`). Only **`4` (`4/161` = `2.5%`; `4/142` = `2.8%` in Population B)** are Junior or Intern SWE/Data/QA roles, and **none (`0/4`) are remotely accessible to Nigeria-based developers**:

| # | Employer (`slug`) | Title | Retained Job ID / Source Record | Declared Location & Remote Metadata | Applicant Eligibility Assessment |
|---:|---|---|---|---|---|
| 1 | `beli` | `Data Science Intern - Summer 2027` | `id: 7faefc00059e` (`breezy_probe_results.json` top-5 `sample_jobs`) | New York, NY (`US`), `streetAddress: 30 W 21st St`, `is_remote: false` | **Restricted (US onsite)**: Onsite New York summer internship (`temporary`). |
| 2 | `beli` | `Software Engineer Intern - Summer 2027` | Title & board aggregation in `breezy_followup_results.json` (full per-job JSON beyond top-5 `sample_jobs` not separately stored) | Board `13/13` `US`; `12/13` `is_remote: false` (`Growth Intern - School Year` `bdb9a1531d83` is the board's sole `is_remote: true` role) | **Restricted (US onsite)**: Proven `is_remote: false` and `US`-only (`New York, NY` onsite). |
| 3 | `vetsez` | `Junior Appian Integration Developer (Remote Opportunity)` | Title & board aggregation in `breezy_followup_results.json` (full per-job JSON beyond top-5 `sample_jobs` not separately stored) | Board `66/66` `US`; VetsEZ VA/DHA federal contracting roles restrict applicants to US | **Restricted (US contractor)**: `0/66` non-US listings on board; inspected VetsEZ remote JSON-LD requires `US`. |
| 4 | `expression-networks` | `Junior Test Engineer (DEA)` | Title & board aggregation in `breezy_followup_results.json` (full per-job JSON beyond top-5 `sample_jobs` not separately stored) | Board `18/18` `US` (`15` onsite, `3` hybrid, `0` fully remote); DEA federal contract | **Restricted (US federal)**: Explicitly tagged `(DEA)` US federal contract, non-remote/US-only. |

*(The remaining `8` explicit `Junior`/`Intern` titles are non-SWE or non-software civil roles restricted to US/CA/IN: `beli` `Growth Intern - School Year` [`bdb9a1531d83`, US], `Product Design Intern - Summer 2027` [US], `Social Media Intern - Summer 2027` [US], `Strategy & Operations Intern - Summer 2027` [US]; `solvative` `Graphic Design Intern` [`c11605654dda`, Ahmedabad, IN]; `soko-glam` `Influencer & PR Intern (Then I Met You)` [`00dc1f459de7`, Brooklyn, NY, US, hybrid]; `pri` `Junior Civil Drafter` [CA onsite] and `Junior Photo Interpreter` [CA onsite].)*

**Assessment**: Among the currently discoverable Breezy employers and expanded test boards, audience fit is **poor**, incremental technical/early-career value relative to implementation cost is **weak**, and inspected remote metadata on several boards is contradictory. (This assessment reflects the `12` evaluated boards and `9` cached employers and does not claim that every employer using Breezy HR worldwide is unsuitable.)

---

## 18. Comparison with Personio

| Criterion | Personio (Step 48/49 — Implemented) | Breezy HR (Step 50) |
|---|---|---|
| **Pre-existing DB & cache footprint (Pop. A)** | `1` `company_boards` (`montana`), `3` `url_cache`, `17` `serper_cache` (`15` hosts) | **`0` `company_boards`**, **`0` `url_cache`**, `19` `serper_cache` URLs (`5` `/apply` dupes -> `14` unique cached postings across `9` hosts) |
| **Official documentation** | Documented public XML Recruiting feed (`/xml`, hourly sync guidance) | `/json` is **undocumented** (`developer.breezy.hr` covers auth v3 API only) |
| **Descriptions in single list GET** | **Yes** (`<jobDescriptions>` in `/xml`, optional 1 fallback GET for bilingual) | **No (`0/12` boards)** — requires **`1 + N` HTML detail GETs** |
| **Remote / Geo clarity** | No explicit flag; honest office locations (`resolve_work_model` stays `None` per ADR 0001) | Explicit `is_remote` & `"no location restrictions"` flag **contradicted** JSON-LD `applicantLocationRequirements` (`US`, `NL`) on inspected examples |
| **Closed/missing job signal** | `404` on `/xml` unknown tenant | `404` on `/json` unknown tenant, **but `302 -> /` on closed `/p/*` detail pages** |
| **Observed audience fit** | DACH-heavy (constrained, already accepted in Step 48) | **Pop. B (`142` live jobs on the `9` cache hosts)**: `59.2%` (`84/142`) US federal contractors, `72.5%` (`103/142`) US-restricted, `18.3%` (`26/142`) CA onsite civil/geotech, `0/142` Nigeria/Africa or remote junior SWE. **Pop. C (`161` live jobs across `12` boards)**: `1.9%` (`3/161`) `worldwide`, `0/161` accessible remote junior SWE |

Personio was already borderline-constrained due to DACH concentration, justified primarily by its zero-`1+N` XML feed and existing `company_boards` row. Breezy lacks both advantages while adding `1 + N` scraping and contradictory remote metadata in the inspected sample.

---

## 19. Technical Implementation Cost

Implementing Breezy safely to Bottom Pot standards would require **medium-high engineering effort (~6–8 files + full `1 + N` test suite)**:
1. `board_adapters.py`: `BreezyBoardAdapter` with `throttled_stream_bytes(..., follow_redirects=False)`, strict JSON schema checks, `compute_board_fingerprint`, AND bounded `MonitoredJobDetailState` hydration (`hydrate_breezy_board_jobs` similar to Workable/SmartRecruiters, `max_new_hydrations_per_poll`, `max_revalidations_per_poll`) plus handling `302 -> /` as `detail_404` and missing JSON-LD fallback.
2. `ats_url_parser.py`: Fix `_BREEZY_SUBDOMAIN` to extract the immutable hex `id` rather than `{id}-{slug}`, remove or deprecate dead `_BREEZY_APPLY`, and add `parse_breezy_board_root_url`.
3. `url_normalizer.py`: Add `ProviderUrlRule` for `breezy` (normalize `/p/{id}-{slug}/apply` -> `/p/{id}-{slug}` or `/p/{id}`).
4. `ats_page_enricher.py`: Handle `302 -> /` closed jobs (`follow_redirects=False` / final URL check), extract `applicantLocationRequirements` carefully so `"no location restrictions"` isn't blindly trusted, and strip `%LABEL_...%` tokens if JSON-LD is absent.
5. `direct_board_router.py`, `search_pipeline.py`, `company_board_registry.py`: Register `breezy` in `MONITORABLE_PROVIDERS`, `BOARD_ADAPTERS`, `probe_direct_boards`, and `_enrich_ats_item`.
6. **Runtime & Timeout Cost**: `vetsez` (`6.10s`) and `gozem` (`6.15s`) exceeded `settings.ats_request_timeout_seconds = 5`, requiring `10–15s` timeouts plus `N` sequential/bounded detail requests per board poll.

---

## 20. Risks and Unknowns

1. **Undocumented `/json` stability**: Because `/json` is absent from `developer.breezy.hr`, Breezy could deprecate, rate-limit, or put Cloudflare/Bot protection in front of `/json` without notice.
2. **Undocumented `/json` size cap**: Verified unpaginated at `66` jobs (`vetsez`); behavior for boards with `100+` or `500+` openings is unknown (`3 MiB` `max_response_bytes` holds ~`2,600` Breezy summary objects at ~`1.13 KB/job`, assuming no silent server cap).
3. **Empty board payload unverified**: All `12` sampled boards had `>= 1` job; `0`-job `/json` behavior (`[]` vs `404` vs `302`) was not directly observed.
4. **Silent description edits**: `/json` ETag did not change unless summary fields changed (inferred from Express weak ETag hashing response body); HTML description edits require periodic detail revalidation.
5. **Geo-restriction false positives**: `is_remote=true` + `"Fully remote, no location restrictions"` would surface US-only VA federal jobs to Nigerian developers unless `applicantLocationRequirements` and text restrictions are enforced.

---

## 21. Recommended Implementation Architecture (Only If Revisited Later)

*Not justified for implementation now.* If Breezy is ever revisited after its Nigerian/global-remote footprint grows materially:
- Poll `GET https://{slug}.breezy.hr/json` with `follow_redirects=False`, `timeout >= 10s`, `If-None-Match` (`304` support).
- Key jobs by `breezy:{slug}:{item["id"]}` (12–14 hex ID), never mutable `friendly_id`.
- Reuse `MonitoredJobDetailState` bounded `1 + N` HTML hydration (`max_new_hydrations_per_poll`, `detail_revalidate_ttl_seconds`) with `follow_redirects=False` (treating `302 -> /` as closed/missing), extracting `JobPosting` JSON-LD first and checking `applicantLocationRequirements` before tagging globally remote.
- Never auto-close missing jobs on an empty `[]` `/json` without an HTML `/` sanity check (`0` `/p/` links) and `missing_confirmation_threshold=2`.

---

## 22. Proposed Test Strategy (Only If Revisited Later)

1. Capture sanitized real fixtures (`vetsez` multi-job, `awarri` worldwide, `vigil-global` missing-JSON-LD detail page, `moneyphone` NL-restricted remote, plus a verified empty `[]` board if discovered).
2. `MockTransport` tests for `304 Not Modified`, `302 -> /` closed-job detail handling, `404` unknown tenant, `ResponseTooLargeError`, malformed JSON -> `snapshot_complete=False`, and `missing_confirmation_threshold=2` closure safety.
3. Unit tests for `ats_url_parser` (`{hex}` ID extraction, `/apply` normalization, deprecation of dead `apply.breezy.hr`).
4. Geo-eligibility regression tests ensuring `vetsez`/`incubator-lab`/`moneyphone` `"no location restrictions"` postings preserve `country` / `applicantLocationRequirements` constraints rather than claiming worldwide eligibility.

---

## 23. Final Decision

**Decision: `Unsuitable`** (Implementation **NOT recommended**).

Breezy HR exhibits poor audience fit in the discoverable employer sample and weak observed incremental value relative to implementation cost:
- **Zero monitored/cached job footprint in DB (`data/cache.sqlite`) & small `serper_cache` Population A**: `0` `company_boards`, `0` `monitored_jobs`, and `0` `url_cache` entries; and in `serper_cache` (**Population A**), only `19` cached URLs across `9` employer hosts (`5` `/apply` duplicates -> **`14` unique cached postings**).
- **Poor audience fit across live employer samples (Populations B & C)**:
  - Across **Population B** (`142` live `/json` postings on the `9` cache-discovered employers), **`59.2%` (`84/142`)** belong to two US federal contractors (`vetsez` `66`, `expression-networks` `18`), **`72.5%` (`103/142`)** belong to the broader US-restricted employer group, **`18.3%` (`26/142`)** are onsite Canadian civil/geotechnical roles (`pri`), and **`0/142`** are Nigeria/Africa-targeted or accessible remote junior/intern SWE roles.
  - Across **Population C** (`161` live `/json` postings adding `3` web-discovered Africa/remote boards `awarri`, `gozem`, `moneyphone`), only **`1.9%` (`3/161`)** are `worldwide` listings (`2` legacy consulting roles + `1` stale `awarri` senior AI role) and **`0/161`** are accessible remote junior/intern SWE roles.
- **High technical friction relative to yield**: Undocumented `/json` omits descriptions (`1 + N` HTML cost), exhibits `302 -> /` closed-job redirects, omitted `JobPosting` JSON-LD on `2/10` inspected detail pages (`vigil-global`, exposing raw `%...%` template tokens on `2/2` inspected `vigil-global` DOM bodies), and carried contradictory `"Fully remote, no location restrictions"` labels on several inspected examples (`vetsez`, `incubator-lab`, `moneyphone`) whose JSON-LD `applicantLocationRequirements` enforced `US` or `NL`.

---

## 24. Suggested Next Step & Higher-Value Alternatives

Rather than implementing Breezy (or any of the remaining low-fit `ATS_PLATFORMS` like `workday` `429`/CXS, `jobvite` HTML-only, `jazzhr` `410 Gone`, `bamboohr` `0` inventory, or enterprise `icims`/`avature`/`taleo`/`jobadder`/`successfactors`), Bottom Pot will gain substantially more value for Nigerian and remote developers from:

1. **Alternative Next Provider Investigation — Step 51 Candidates (Recommended Option A)**:
   - Formally investigate **Pinpoint (`*.pinpointhq.com/postings.json`)** (retired in Step 32, queued for fresh Section 3 evaluation) and **Remote OK (`remoteok.com/api`)** in a dedicated **Step 51** audit—explicitly verifying **data reuse and redistribution permissions**, attribution/direct-link obligations, and genuine Nigeria/Africa & worldwide applicant eligibility before any implementation decision. *(Do NOT assume public endpoint availability grants redistribution permission.)*
   - Classify public remote aggregators such as **Remotive** and **Himalayas** strictly as **`Discovery-only` / `Permission pending`** (NOT approved direct listing-ingestion candidates): their public feeds carry redistribution, rate/delay, and attribution constraints not yet cleared for job republication, so any use without explicit permission is limited to discovering original employer ATS career URLs rather than ingesting aggregator job copy.
2. **Highest-ROI Platform Work (Recommended Option B)**: Operationalize and enrich the **8 already-implemented `MONITORABLE_PROVIDERS`**:
   - Curate and seed high-signal Nigerian/African & genuinely global-remote tech employers hosted on **Greenhouse, Lever, Ashby, Workable, Recruitee, SmartRecruiters, Teamtailor, and Personio** (currently `7` of `8` monitorable providers have `0` rows in `monitored_jobs`).
   - Surface structured **`applicantLocationRequirements`** / country-restriction filtering in `JobListing` so US-only `"Remote"` jobs (across all ATS providers) are flagged or filtered cleanly for Nigerian applicants.
   - *(Dead `_BREEZY_APPLY` and active `breezy` provider code have already been removed in this step; see Section 26.)*

---

## 25. Full Evidence Table

### 25.1 Pre- and Post-Investigation Protected Asset Checksums

*(Verified identical before and after all investigation probes; `subscriptions.csv` not present in repo.)*

| Protected Asset | Size (Bytes) | SHA-256 |
|---|---:|---|
| `data/cache.sqlite` | `14,016,512` | `a7c88bb24d383813213342ea1a0990f0c7bf62b4c1308647fc18f834be028638` |
| `data/cache.sqlite-shm` | `32,768` | `fd4c9fda9cd3f9ae7c962b0ddf37232294d55580e1aa165aa06129b8549389eb` |
| `data/cache.sqlite-wal` | `0` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `data/cache.sqlite.bak-pre-ashby-repair` | `14,016,512` | `10114b66d0b40183719f63949aa1fc018b08f0c691742e5f2ecdf670a8e9abe6` |
| `data/cache.sqlite.bak-pre-greenhouse-synthetic-cleanup` | `14,016,512` | `45e28a493cc84f0898286c819cf7b834d184cbb1365597597deedd1609924b77` |
| `data/cache.sqlite.bak-pre-greenhouse-synthetic-cleanup-shm` | `32,768` | `fd4c9fda9cd3f9ae7c962b0ddf37232294d55580e1aa165aa06129b8549389eb` |
| `data/cache.sqlite.bak-pre-greenhouse-synthetic-cleanup-wal` | `0` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `data/.cache.sqlite.restore-staging-3b2519d1-9f5c-4dcb-b646-6db8e40a8bcd` | `14,016,512` | `10114b66d0b40183719f63949aa1fc018b08f0c691742e5f2ecdf670a8e9abe6` |
| `data/.cache.sqlite.restore-staging-a67a7e88-8b18-4675-874f-f3d9e3387d90` | `14,016,512` | `10114b66d0b40183719f63949aa1fc018b08f0c691742e5f2ecdf670a8e9abe6` |

### 25.2 Live Bounded Probe Log (`2026-11-18` UTC)

| UTC Timestamp | URL | Status | Bytes | Latency (ms) | SHA-256 / Outcome |
|---|---|---:|---:|---:|---|
| `2026-11-18T15:24:42Z` | `https://developer.breezy.hr/llms.txt` | 200 | 21,731 | 2,730 | `b4db61437551f86234f42f025b329f80cf6a2b6a332d65deeea9349c4daa9efd` |
| `2026-11-18T15:24:45Z` | `https://vetsez.breezy.hr/json` | 200 | 74,863 | 6,103 | `bc5a45815a6ff9627cb2a4b68809deab45df1065ff2d1c76c9fb55a33c716b9e` (`66` jobs) |
| `2026-11-18T15:24:51Z` | `https://expression-networks.breezy.hr/json` | 200 | 26,504 | 1,974 | `0b249778c34717165315bd6efae8f73dcc86488a66349fc2ed8e2edac34fd009` (`18` jobs) |
| `2026-11-18T15:24:53Z` | `https://solvative.breezy.hr/json` | 200 | 1,721 | 1,347 | `923b5570483039f33cf28b1c11bfb40d8de480a9764c89bdc5a1ea39ce8a7a55` (`2` jobs) |
| `2026-11-18T15:24:55Z` | `https://beli.breezy.hr/json` | 200 | 13,123 | 1,364 | `d68e2a8a3c92a1292e99259285513d08d0268015efe61d234c760bb3b840d8f3` (`13` jobs) |
| `2026-11-18T15:24:57Z` | `https://incubator-lab.breezy.hr/json` | 200 | 3,385 | 3,202 | `94d0ff56bcac85f4c33fd03855e37089bff515e56e03f88f4805a01e0d546057` (`3` jobs) |
| `2026-11-18T15:25:00Z` | `https://vigil-global.breezy.hr/json` | 200 | 12,289 | 1,339 | `7309f37b0688c6f6772ee8cf7443285dced6c3839d5d44e32344ab5de914290b` (`11` jobs) |
| `2026-11-18T15:25:02Z` | `https://indinterns.breezy.hr/json` | 200 | 855 | 826 | `9370480966da15e0168104bb6609edd08e6622c2e0a43538aeec81479145c372` (`1` job) |
| `2026-11-18T15:25:03Z` | `https://pri.breezy.hr/json` | 200 | 30,997 | 3,836 | `e6f6f522d58e0f88768e61334171383b84c2f068cc071cd2580a4b1b19e56b2a` (`26` jobs) |
| `2026-11-18T15:25:07Z` | `https://soko-glam.breezy.hr/json` | 200 | 1,785 | 815 | `2a66ac777e8de4fd98ae37287fe414aa065bab7699f06b59daed1389eeece0e1` (`2` jobs) |
| `2026-11-18T15:25:08Z` | `https://awarri.breezy.hr/json` | 200 | 844 | 820 | `f1bc235998564c098d656042596f36f4cd5185eaca0340deddafda704f9db20d` (`1` job) |
| `2026-11-18T15:25:09Z` | `https://gozem.breezy.hr/json` | 200 | 13,080 | 6,151 | `b763c352850176e733c0d21c4466ad53ae2b708acc0b4073044094010155aa3f` (`17` jobs) |
| `2026-11-18T15:25:16Z` | `https://moneyphone.breezy.hr/json` | 200 | 2,327 | 1,065 | `f6acd1da5fbd300bb797018a03e0abf0699bb1c7a8a6b10bb29ea307989c79e2` (`1` job) |
| `2026-11-18T15:25:17Z` | `https://vetsez.breezy.hr/json` (`If-None-Match`) | 304 | 0 | — | Conditional revalidation verified |
| `2026-11-18T15:25:20Z` | `https://expression-networks.breezy.hr/json` (`If-None-Match`) | 304 | 0 | — | Conditional revalidation verified |
| `2026-11-18T15:25:22Z`–`24Z` | `https://vetsez.breezy.hr/json?{page=2,limit=1,offset=1}` | 200 | 74,863 | — | Identical SHA-256 `bc5a4581...` (`66` items) |
| `2026-11-18T15:25:25Z` | `https://vetsez.breezy.hr/` | 200 | 95,586 | — | HTML board: `66` `/p/...` links |
| `2026-11-18T15:25:29Z` | `https://vetsez.breezy.hr/p/ddf6ace039b401-net-developer-remote-opportunity` | 200 | 33,294 | — | `JobPosting` JSON-LD, `applicantLocationRequirements: US` |
| `2026-11-18T15:25:34Z` | `https://solvative.breezy.hr/p/d9bd06a44f43-data-engineer` | 200 | 27,907 | — | `JobPosting` JSON-LD, `IN` (`Remote (India)`) |
| `2026-11-18T15:25:35Z` | `https://incubator-lab.breezy.hr/p/ba5c05cbcdc6-content-manager-social` | 200 | 35,795 | — | `JobPosting` JSON-LD, `applicantLocationRequirements: US`, EST hours |
| `2026-11-18T15:25:38Z` | `https://awarri.breezy.hr/p/3dfc125ed8b401-senior-ai-engineer-wat-remote` | 200 | 21,686 | — | `JobPosting` JSON-LD, `worldwide` (Nigeria AI) |
| `2026-11-18T15:25:41Z`–`43Z` | `vetsez` detail `/json`, `.json`, `?format=json` | 302 / 200 / 200 | 30 / 33,294 / 33,293 | — | `302 -> /`; others return HTML, no JSON API |
| `2026-11-18T15:25:44Z` / `15:27:00Z`–`02Z` | `https://apply.breezy.hr/` & `/p/...` | `Err` | 0 | — | `ConnectError: [Errno 11001] getaddrinfo failed` |
| `2026-11-18T15:25:45Z` | `https://vetsez.breezy.hr/p/nonexistent-bottom-pot-99999` | 302 | 30 | — | `Location: /` |
| `2026-11-18T15:25:46Z` | `http://vetsez.breezy.hr/json` | 302 | 58 | — | `Location: https://vetsez.breezy.hr/json` |
| `2026-11-18T15:25:48Z`–`51Z` | `https://vetsez.breezy.hr/{rss,jobs.rss,xml}` | 302 | 30 | — | `Location: /` |
| `2026-11-18T15:25:51Z` | `https://nonexistent-bottom-pot-probe-99999.breezy.hr/json` | 404 | 3,265 | — | `"Career portal not found | Breezy HR"` |
| `2026-11-18T15:26:54Z`–`59Z` | `developer.breezy.hr/reference/{customer-guide,listpositions,getposition}.md` | 200 | 6,004 / 16,154 / 17,873 | — | Official OpenAPI v3 specs (no `/json` docs) |
| `2026-11-18T15:27:02Z`–`05Z` | `vetsez` `/p/ddf6ace039b401`, `/apply`, `-wrong-slug` | 200 / 200 / 200 | 33,293 / 51,700 / 33,293 | — | Hex ID resolves regardless of slug |
| `2026-11-18T15:27:30Z`–`38Z` | Detail geo checks (`vigil-global`, `indinterns`, `awarri`, `moneyphone`) | 200 | Not logged | — | `vigil-global` (`2/2`) missing JSON-LD; `indinterns` `US`; `moneyphone` JSON-LD `NL` despite `"no location restrictions"` |
| `2026-11-18T15:28:33Z`–`37Z` | `vigil-global` (`Data / ML Engineer`, `Senior CA GEN Consultant`) + `vetsez` (`HealthShare Engineer`) | 200 / 200 / (parsed HTML) | 22,875 / 26,796 / (not logged) | — | `%LABEL_...%` / `%HEADER_...%` DOM tokens observed on both `vigil-global` pages (`Data / ML` had `0` JSON-LD; `CA GEN` had `2` JSON-LD); `vetsez` `HealthShare` JSON-LD `US` |

---

## 26. Rejected-Provider Cleanup & Repository Normalization

Because Breezy HR was evaluated as **`Unsuitable`** and moved to **`Rejected`** in [`docs/job-source-catalog.md`](../job-source-catalog.md), all active `breezy` integration code and platform registrations were removed on branch `step/50-breezy-monitoring-investigation` (PR #50):

1. **Backend active traces removed (`src/project_files/` & `scripts/`)**:
   - `src/project_files/config.py`: removed `ATSConfig(name="breezy", ...)` from `ATS_PLATFORMS` (now `17` active ATS platforms).
   - `src/project_files/ats_url_parser.py`: removed `"breezy"` from `SUPPORTED_ATS_PATTERNS` and `_GENERIC_SLUG_STOPWORDS`, removed `_BREEZY_SUBDOMAIN` and `_BREEZY_APPLY` regexes, and removed `breezy` matching from `parse_ats_url`.
   - `src/project_files/company_board_registry.py`: removed `"breezy"` branch from `build_canonical_board_url` (now returns `None`) and removed redundant `breezy` mention from the unverified-ATS comment.
   - `scripts/capture_fixtures.py`: removed `"breezy.hr": "breezy"` from `KNOWN_PROVIDERS`.
2. **Frontend active traces removed (`frontend/src/`)**:
   - `lib/constants.ts`: removed `{ id: 'breezy', name: 'Breezy HR' }` from `ALL_PLATFORMS` (now `20` active platforms: `17` ATS + `3` Nigerian).
   - `components/SearchSummaryBar.tsx`, `components/StatusStrip.tsx`, `components/TelemetryDeck.tsx`, `lib/mock.ts`: updated default platform fallback/mock counts from `18` to `17`.
   - **Documented exception — `lib/platformMigration.ts` (`HISTORICAL_FULL_INVENTORIES`)**: bumped `CURRENT_PLATFORM_VERSION` from `'32'` to `'50'` and added the Step 32–49 21-platform list to `HISTORICAL_FULL_INVENTORIES` so existing users with full selections saved in `localStorage` migrate cleanly to the active 20-platform inventory and rejected `'breezy'` is stripped from custom subsets.
3. **Tests & documentation synchronized**:
   - Updated `tests/test_platform_reconciliation.py`, `tests/test_query_builder.py`, `tests/test_ats_url_parser.py`, `tests/test_company_board_registry.py`, `tests/test_real_api_fixtures.py`, `tests/test_phase5_cost_and_robustness.py`, `frontend/src/lib/__tests__/marketing.test.ts`, and `frontend/src/lib/__tests__/platformMigration.test.ts` to assert `17` ATS / `20` total active platforms and verify `breezy` is rejected.
   - Created [`docs/job-source-catalog.md`](../job-source-catalog.md) and codified the **Provider Discovery, Lifecycle & Repository Normalization** policy in [`AGENTS.md`](../../AGENTS.md), synchronizing `README.md`, `CONTEXT.md`, `docs/agents/file-structure.md`, `docs/agents/PROJECT_COMPENDIUM.md`, and `docs/steps/48-personio-monitoring-investigation.md`.
4. **Operational data preserved untouched**:
   - All `9` operational SQLite files and backups in `data/` remain completely untouched with identical byte sizes and SHA-256 checksums (`data/cache.sqlite` `serper_cache` history is preserved).
5. **Final `git grep -ni breezy` Audit Categories**:
   - **Historical evidence**: `docs/steps/25-eval-and-frontend.md`, `docs/steps/30-readme.md`, `docs/steps/46-teamtailor-monitoring-investigation.md`, `docs/steps/48-personio-monitoring-investigation.md`, `docs/steps/50-breezy-monitoring-investigation.md`, and `docs/job-source-catalog.md`.
   - **Migration compatibility**: `frontend/src/lib/platformMigration.ts` (`HISTORICAL_FULL_INVENTORIES` to migrate Step 27–49 user `localStorage` selections cleanly).
   - **Negative tests proving rejection**: `tests/test_ats_url_parser.py`, `tests/test_company_board_registry.py`, `tests/test_platform_reconciliation.py`, `tests/test_query_builder.py`, `frontend/src/lib/__tests__/marketing.test.ts`, and `frontend/src/lib/__tests__/platformMigration.test.ts`.
   - **Other retained references**: **`0`** (zero remaining active references in backend, frontend runtime, or helper scripts).
