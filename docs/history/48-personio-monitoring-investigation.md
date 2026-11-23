# Step 48: Personio Monitoring & Direct-Routing Investigation

**Status:** Investigation & Feasibility Decision Complete (Documentation Only — No Step 48/49 Code Implementation)  
**Date:** 2026-11-17  
**Branch:** `step/48-personio-monitoring-investigation`  
**Base Commit (`main`):** `f5fac971fb745f4f1bd9df3cc95aee76180f8155`  
**Selected Candidate:** `personio` (over `breezy`, `jobvite`, `jazzhr`, `workday`, `bamboohr`, `icims`, `avature`, `taleo`, `jobadder`, and `successfactors`)  
**Feasibility Decision:** **`Suitable with constraints`**

---

## 1. Executive Recommendation

Select **`personio`** as the next ATS provider to integrate into `MONITORABLE_PROVIDERS`, `BOARD_ADAPTERS`, and `probe_direct_boards`, with feasibility decision **`Suitable with constraints`**.

**Why `personio` wins across the evidence criteria (while acknowledging real caveats):**
1. **Verified operational footprint with an already-registered board**: `personio` has **`1`** registered board in `company_boards` (`montana`, `monitoring_capability='unsupported'`), **`3`** `url_cache` rows, and **`17`** unique genuine posting URLs across **`15`** unique employer hosts in `serper_cache` (`4` remote/Africa/global-tagged). Among non-Workday unmonitored providers, only `personio` (`1` board, `15` hosts) and `jobvite` (`1` board, HTML-only) have an active `company_boards` row.
2. **Unauthenticated, unpaginated single-GET XML feed with `ETag` + `304`**: `GET https://{slug}.jobs.personio.{com,de}/xml` returned HTTP `200 OK` (`text/xml`) across **`8 / 8`** probed real company feeds (`7 / 7` non-empty feeds — `montana`, `cosine`, `enopai`, `jedox`, `saeki`, `adbaker-gmbh`, `inexogy` — plus `traviangames` empty `72`-byte XML verified against `0` HTML job links), supports `If-None-Match` -> **`304 Not Modified`** (`0` bytes), returns **`404`** on unknown tenants, and lists all active openings in a single unpaginated `<workzag-jobs>` response without a 100-item RSS cap.
3. **Structured descriptions in one GET (no `1 + N` scraping tax)**: Unlike `breezy` (`/json` omits descriptions entirely), `jobvite` (HTML-only), and `jazzhr` (`/apply/rss` returns `410 Gone`), Personio XML delivers HTML `<jobDescriptions>`, `<employmentType>`, `<schedule>`, `<seniority>`, `<office>`, `<additionalOffices>`, `<department>`, and `<createdAt>` in the single list response on `montana` (`20/20`), `cosine` (`5/5`), `adbaker-gmbh` (`19/19`), `inexogy` (`14/14`), and `saeki` (`9/9` via `?language=en`).

**Why `Suitable with constraints` (explicit caveats):**
- **Bilingual XML description split**: `?language=en` returns the exact same `<position>` count, **but omits `<jobDescriptions>` on German-only roles** (verified on `montana`: `0` empty default vs `20` empty in `?language=en`), while default `/xml` omits English-only descriptions (verified on `saeki`: `8` empty default vs `0` empty in `?language=en`). A safe adapter must handle `?language=en` plus bounded fallback to `/xml` when empty descriptions occur.
- **`.com` vs `.de` TLD split**: `company_boards` registered `montana.jobs.personio.de` while `url_cache` cached `montana.jobs.personio.com/job/2852393` and `ats_page_enricher.py:818` checks `"jobs.personio.com"` only. Live probes across `montana`, `adbaker-gmbh`, and `inexogy` confirmed identical XML payloads and identical ETags on both `.com` and `.de`.
- **DACH employer concentration**: Most currently cached Personio hosts (`15`) are DACH/European companies (`German-Speaking`, `(m/w/d)` roles). **Runner-up `breezy` (`breezy.hr`)** initially appeared to have stronger remote/global SWE representation in `serper_cache` (`19` genuine URLs, `9` hosts, `6` remote hits, `/json` with `ETag`/`304`, `is_remote`, `salary`, `company.logo_url`), with `0` `company_boards`, `0` `url_cache`, and missing descriptions in `/json` (`1 + N` detail fetches). *(Historical update: Step 50 subsequently evaluated `breezy`, proved its remote metadata misleading and audience value unsuitable, marked it **`Rejected` (`Unsuitable`)**, and removed active `breezy` integration code; see [Step 50](50-breezy-monitoring-investigation.md).)*

---

## 2. Provider Inventory & Selection Rationale

### 2.1 Codebase Baseline (at commit `f5fac971fb745f4f1bd9df3cc95aee76180f8155`)

- **Currently Monitorable (`MONITORABLE_PROVIDERS` in `src/project_files/company_board_registry.py:124-132`, wired in `BOARD_ADAPTERS` & `direct_board_router.py`)**: `7` providers — `greenhouse`, `lever`, `ashby`, `workable`, `recruitee`, `smartrecruiters`, `teamtailor`.
- **Provisional (`PROVISIONAL_PROVIDERS`)**: `bamboohr` (`BambooHRClient` only).
- **Direct Board Root Parsers (`src/project_files/ats_url_parser.py`)**: Exist for all `7` monitorable providers only; missing for `personio`, `breezy`, `jobvite`, `jazzhr`, `bamboohr`, `workday`, `icims`, `avature`, `taleo`, `jobadder`, `successfactors`.
- **Completed Step History (`docs/steps/41-*` through `47-*`)**: Steps 41 (Workable quality), 42–43 (Recruitee investigation + quality), 44–45 (SmartRecruiters investigation + quality), 46–47 (Teamtailor investigation + monitoring pipeline).

### 2.2 Operational Database Inventory (`data/cache.sqlite`, strictly read-only)

Inspected via a byte-copied isolated temp bundle (`cache.sqlite`, `cache.sqlite-wal`, `cache.sqlite-shm`) opened with `sqlite3.connect(uri, uri=True)` (`?mode=ro`) without instantiating `CacheStore` or `CompanyBoardRegistry` and without modifying operational files.

| Table | Observed Counts |
|---|---|
| `company_boards` | `greenhouse` (`34`, supported), `lever` (`36`, supported: `34` candidate + `2` verified), `ashby` (`21`, supported), `smartrecruiters` (`13`, provisional legacy), `workable` (`9`, provisional legacy), `teamtailor` (`7`, legacy `'unsupported'` auto-promoted by Step 47 `_ensure_db()`), **`jobvite` (`1`, `'unsupported'`: `glidewelldental`)**, **`personio` (`1`, `'unsupported'`: `montana`)** |
| `monitored_jobs` | `lever`: `160` active, `1` closed |

Non-monitored candidate comparison across all `11` remaining `ATS_PLATFORMS`:

| Provider | `company_boards` | `url_cache` (Hosts) | Genuine `serper_cache` URLs (Unique Hosts) | Remote / Africa Tagged | Real Fixtures (`tests/fixtures/real/`) | Existing Parser / Client Maturity | Feasibility Verdict |
|---|---:|---:|---:|---:|---:|---|---|
| **`personio`** | **1** (`montana`) | **3** (`2`: `acme`, `montana`) | **17** (`15` hosts) | 4 | 0 | `_PERSONIO`, `build_canonical_board_url`, HTML rules in `ats_page_enricher.py:818` | **`Suitable with constraints` (Selected)** |
| **`breezy`** | 0 | 0 | **19** (`9` hosts) | **6** | 0 | `_BREEZY_SUBDOMAIN`, `_BREEZY_APPLY`, `build_canonical_board_url` | `Suitable with constraints` *(historical Step 48 preliminary rating — subsequently **`Rejected` (`Unsuitable`)** and removed in [Step 50](50-breezy-monitoring-investigation.md))* |
| **`workday`** | 0 | **46** (`37` hosts) | **64** (`50` hosts) | 2 | **7** | `parse_workday_url`, `WorkdayClient`; `build_canonical_board_url=None` | **`Unsuitable for now`** (`HTTP 429` on single unauth GET; listing requires `POST /wday/cxs/.../jobs`) |
| **`jobvite`** | 1 (`glidewelldental`) | 6 (`5` slugs) | 23 (`jobs.jobvite.com`) | 0 | **6** | `_JOBVITE`, expired check `ats_page_enricher.py:86,696` | **`Unsuitable for now`** (HTML-only listing, no public XML/JSON feed, no ETag/JSON-LD on `/jobs`) |
| **`jazzhr`** | 0 | 3 (`2` hosts) | 23 (`15` hosts) | 1 (`corpsafrica`) | 0 | `_JAZZHR`, `_JAZZHR_SHARE`, `_jazzhr_share_attributes` | **`Unsuitable for now`** (`/apply/rss` returns `410 Gone`; HTML `/apply` has `no-cache`, no JSON-LD) |
| **`bamboohr`** | 0 | 0 | **0** (`10` `example.com` only) | 0 | 1 (`deel_list.json`) | `BambooHRClient` (`PROVISIONAL_PROVIDERS`) | **`Unsuitable for now`** (zero real operational inventory; `/careers/list` omits descriptions) |
| **`icims`** | 0 | 0 | 26 (`22` hosts) | 3 | 0 | `_ICIMS` regex only | **`Unsuitable for now`** (iframe/multi-portal HTML; zero canonical board route) |
| **`avature`** | 0 | 4 (`2` hosts) | 15 (`6` hosts) | 1 | **8** | `_AVATURE` regex only | **`Unsuitable for now`** (non-standardized localized enterprise paths; no public board feed) |
| **`taleo` / `successfactors` / `jobadder`** | 0 | 0 | `14` (`7`) / `0` real / `0` job URLs | 0 | 0 | Basic regexes (`_TALEO`, `_SUCCESSFACTORS`, `_JOBADDER`) | **`Unsuitable for now`** (JSF careersections / single SAP host / marketing links only) |

---

## 3. Public Endpoint Contract

Observed via sequential unauthenticated `GET` probes (`follow_redirects=False`, 12s timeout, `0` Serper credits):

- **Primary Listing Feed**: `GET https://{slug}.jobs.personio.com/xml` (or `https://{slug}.jobs.personio.de/xml`)
  - Optional query parameter: `?language=en` (or `de`, `fr`, `es`, `nl`, `it`, `pt`).
  - Response `Content-Type`: `text/xml` (UTF-8).
  - Root XML element: `<workzag-jobs>` containing `0..N` `<position>` child elements.
- **Exact `.com` vs `.de` Parity Observed (`3 / 3` hosts)**:
  - `montana.jobs.personio.de/xml` == `montana.jobs.personio.com/xml`: both `200`, `116,649` bytes, `ETag: "21713bfc0564c106a0f0ed6badc7ef25"`.
  - `adbaker-gmbh.jobs.personio.com/xml` == `.de/xml`: both `200`, `130,649` bytes.
  - `inexogy.jobs.personio.com/xml` == `.de/xml`: both `200`, `101,672` bytes.
- **Observed `<position>` Child Tags Across Probed Non-Empty Live Feeds**:
  `['additionalOffices', 'createdAt', 'department', 'employmentType', 'id', 'jobDescriptions', 'keywords', 'name', 'occupation', 'occupationCategory', 'office', 'recruitingCategory', 'salaryInformation', 'schedule', 'seniority', 'subcompany', 'yearsOfExperience']`
- **Detail Job URL**: `https://{slug}.jobs.personio.{com,de}/job/{position_id}` (`text/html`, embeds Schema.org JSON-LD `JobPosting`, verified `200`, `102,607` bytes on `enopai`).

---

## 4. Authentication Requirements

- `GET https://{slug}.jobs.personio.{com,de}/xml` and `/job/{id}` are **100% unauthenticated**. No API keys, OAuth tokens, or cookies are required.
- Note distinction from Personio's authenticated Recruiting API (`api.personio.de/v1/recruiting/...`), which requires tenant API credentials and is **not** used.

---

## 5. Board Identity & Job Identity Rules

- **Board token (`board_token`)**: Lowercased Personio tenant subdomain `{slug}` (matching `is_valid_board_slug("personio", slug)`).
- **Canonical Board URL (`build_canonical_board_url` gap)**: Currently `company_board_registry.py:161-162` returns `https://{token}.jobs.personio.de` while `config.py:25` uses `jobs.personio.com`, `url_cache` stores `montana.jobs.personio.com`, and `ats_page_enricher.py:818` checks `"jobs.personio.com" in url` only. Step 49 should normalize `.de` / `.com` consistently to `https://{slug}.jobs.personio.com` (verified identical on `3/3` hosts) while parsing both `.com` and `.de`.
- **Canonical Job Identity**: `f"personio:{clean_slug}:{position_id}"` where `position_id` is the stripped numeric `<id>` from `<position><id>...</id></position>`.
- **Board-Root Discovery Gap**: Add `parse_personio_board_root_url(url)` to `ats_url_parser.py` accepting `https://{slug}.jobs.personio.{com,de}/?` (excluding `jobs.jobs` / `www`) and wire it into `search_pipeline.py:_enrich_ats_item` so board-root search hits register `company_boards` without throwing away valid boards.

---

## 6. Pagination & Snapshot Completeness Evidence

- **Unpaginated Single-Response Contract**: Personio's public `/xml` feed has **no pagination parameters** and does not impose Teamtailor's 100-item RSS cap; `<workzag-jobs>` returns all published open positions for the tenant in one document.
- **Verified Equivalence Across Languages**:
  - `montana`: default `/xml` = `20` positions (`0` empty desc); `?language=en` = `20` positions (`20` empty desc), identical first-5 IDs `['2863267', '2852393', '2524384', '2562999', '2892242']`.
  - `saeki`: default `/xml` = `9` positions (`8` empty desc); `?language=en` = `9` positions (`0` empty desc).
  - `jedox`: default `/xml` = `9` positions (`6` empty desc); `?language=en` = `9` positions (`3` empty desc).
  - `enopai`: default `/xml` = `4` positions (`4` empty desc); `?language=en` = `4` positions (`1` empty desc).
- **Empty Board Distinction**: `traviangames.jobs.personio.com/xml` returned HTTP `200`, `72` bytes (`<?xml version="1.0" encoding="UTF-8"?>\n\n<workzag-jobs>\n\n\n</workzag-jobs>`), independently confirmed against HTML `https://traviangames.jobs.personio.com/` (`200`, `53,088` bytes, `job_links=0`). Thus valid `<workzag-jobs>` with `0` `<position>` nodes represents a genuinely empty open-jobs snapshot (`snapshot_complete=True`).
- **`snapshot_complete=False` Rules**: Any non-200 status (`404`, `429`, `5xx`), network/size error, `<!DOCTYPE`/`<!ENTITY` declaration, malformed XML, non-`workzag-jobs` root, duplicate `<id>`, or missing `<id>`/`<name>` MUST return `BoardCheckResult(success=False, snapshot_complete=False, ...)` so `BoardMonitor` never auto-closes existing jobs.

---

## 7. Conditional Request Behaviour

- **ETag Support Verified**: All `200 OK` Personio `/xml` responses returned strong ETags (e.g., `saeki`: `"57f2d8bf31eff0048f8da07bf5939253"`, `?language=en`: `"c9c3a963976190a92f945846101fd9f9"`).
- **HTTP `304 Not Modified` Verified**: Sending `If-None-Match: "57f2d8bf31eff0048f8da07bf5939253"` to `https://saeki.jobs.personio.com/xml` returned **`HTTP 304` with `0` bytes**.
- **Headers Absent**: No `Last-Modified` or `Cache-Control` headers were emitted on `200 OK` XML feeds.
- **Two-Feed Merge ETag Rule**: If Step 49 uses `?language=en` alongside fallback default `/xml` when any `<position>` has empty `<jobDescriptions>`, it must ensure a `304` on `?language=en` never masks changes to default `/xml` descriptions (nor vice versa) — computing `compute_board_fingerprint` over the merged item payload hash + `<createdAt>` (see Section 12).

---

## 8. Field Mapping

| Personio XML Field | Target `RawJobPosting` / `JobListing` Field | Mapping Notes & Evidence |
|---|---|---|
| `<id>` | `provider_job_id`, `id` (`personio:{slug}:{id}`) | Mandatory non-empty numeric string. |
| `<name>` | `raw_title` -> `title` | Normalized cleanly. |
| `<subcompany>` / XML header | `raw_company` -> `company` | Falls back to `board.company_name` or `humanize_slug(slug)`. Note `<workzag-jobs>` has no top-level `<company>` tag when `<subcompany>` is absent (e.g. `saeki`), so Step 49 should preserve `board.company_name` or HTML title fallback. |
| `<jobDescriptions>/<jobDescription>` | `raw_description` -> `description` | Concatenate `<h4>{name}</h4> + {value}` HTML blocks via `to_markdown(...)`; `description_is_authentic = bool(desc_md)`. |
| `<office>` + `<additionalOffices>` | `raw_location`, `raw_location_preserved` | Combine distinct office names into compact `location`, preserving full list in `raw_location_preserved`. |
| `<department>` / `<recruitingCategory>` | `raw_department` | Optional clean string. |
| `<employmentType>` + `<schedule>` | `employment_type` | Observed: `permanent`, `fixed_term`, `freelance`, `intern`, `working_student` and `full-time`, `part-time`, `full-or-part-time`. Map deterministically via `normalize_job_type`; leave unknown if ambiguous. |
| `<createdAt>` | `raw_date` -> `posted_at` | Observed ISO-8601 UTC (`2026-10-27T15:59:02+00:00`); supported natively by `parse_datetime`. |
| `<salaryInformation>` | `raw_fields["salaryInformation"]` | Parse structured salary only when present cleanly (never invent). |
| *Work model* | `work_model` | **No explicit remote tag exists in `/xml`**. Pass `office` + `name` + `trusted_description` to `resolve_work_model` per ADR 0001/0002; unstated remains `None`. |
| *Company logo* | `company_logo_url` | **Not in `/xml`**. HTML pages include `https://assets.cdn.personio.de/logos/...`; optionally extract cleanly on board HTML visit or retain `board.company_logo_url`. |

---

## 9. Error, Timeout, and Throttling Behaviour

- **Unknown Tenant**: `GET https://nonexistent-bottom-pot-probe-99999.jobs.personio.com/xml` returned **`HTTP 404`** (`text/html`, `2,472` bytes, `Cache-Control: public, max-age=86400, s-maxage=86400`). Adapter maps `404` -> `BoardCheckResult(success=False, snapshot_complete=False, error="Board not found (HTTP 404)")`.
- **Observed Latency**: `1,336ms`–`1,823ms` per sequential XML GET (`0` HTTP 429 or Cloudflare challenges observed across the `19` sequential Personio requests logged in Section 17).
- **Polling Guidance**: Personio's official XML Recruiting documentation recommends syncing/polling `/xml` **at least once every hour** (no push webhooks are provided; `15–60` minutes is standard). Bottom Pot's default `monitoring_board_interval_seconds = 1800` (`30` minutes, yielding `1620–1980` s / `27–33` minutes with `±10%` jitter in `record_check_success`, clamped at `>= 300s`) satisfies this at-least-hourly requirement without modifying global configuration, while `throttled_stream_bytes` per-host semaphores & circuit breaker keep traffic bounded.

---

## 10. Existing Fixture Assessment

- **Current State**: `tests/fixtures/real/personio/` does **not exist (`0` files)**, unlike `teamtailor` (`43`), `greenhouse` (`33`), `lever` (`22`), `workable` (`21`), `smartrecruiters` (`13`), `workday` (`7`), `jobvite` (`6`), `avature` (`8`).
- **Step 49 Planned Captured Fixtures**: Save sanitized real XML payloads from our verified feeds into `tests/fixtures/real/personio/`:
  1. `montana_xml_default.xml` (`20` roles, German `<jobDescriptions>`, `subcompany`, `additionalOffices`, `.de`/`.com` parity)
  2. `saeki_xml_en.xml` (`9` roles, English `<jobDescriptions>`, `schedule`, `employmentType`, `seniority`, missing `<subcompany>`)
  3. `enopai_xml_sparse.xml` (`4` roles, including 1 role lacking `<jobDescriptions>` even in `?language=en`)
  4. `traviangames_xml_empty.xml` (`72`-byte valid empty `<workzag-jobs>`)

---

## 11. Recommended Adapter Architecture

1. **`parse_personio_xml_feed(xml_bytes, ...)`** in `src/project_files/board_adapters.py`:
   - Enforce size limit (`settings.max_response_bytes` via `throttled_stream_bytes(..., follow_redirects=False)`).
   - Reject `_XML_UNSAFE_DECL_RE.search(xml_bytes)` (anti-XXE / DOCTYPE / ENTITY across full payload).
   - Parse `<workzag-jobs>` strictly; validate unique non-empty `<id>` and `<name>` on every `<position>` (fail closed on duplicate/missing `<id>` or missing `<name>`).
2. **`PersonioBoardAdapter`** in `src/project_files/board_adapters.py`:
   - Poll `GET https://{encoded_slug}.jobs.personio.com/xml?language=en` with `If-None-Match`.
   - On `304`, return `BoardCheckResult(success=True, not_modified=True, snapshot_complete=True, ...)`.
   - On `200`, if any `<position>` has empty `<jobDescriptions>`, perform **at most one** supplementary `GET https://{encoded_slug}.jobs.personio.com/xml` (default language) and merge missing `<jobDescriptions>` by `<id>`. Note: if ANY role's descriptions come from the fallback feed, also watch default feed changes carefully or skip ETag short-circuit if the fallback had missing entries so updates are never masked (store composite or primary ETag carefully — safest rule: cache primary `ETag` only when all descriptions came from the primary URL OR poll default `/xml` only on change; see Section 12).
   - Map all items through `JobExtractionService` + `CanonicalJobAdapter` with `missing_confirmation_threshold=2` and `snapshot_complete=True`.
3. **Direct Routing & Discovery**:
   - Add `parse_personio_board_root_url` in `ats_url_parser.py` and wire in `search_pipeline.py`.
   - Add `probe_personio_board` in `direct_board_router.py`.
   - Add `"personio"` to `MONITORABLE_PROVIDERS` and fix `.jobs.personio.(?:com|de)` in `ats_page_enricher.py` + `build_canonical_board_url` (`company_board_registry.py`). Pre-existing `'unsupported'` `montana` row promotes cleanly via `_ensure_db()`.

---

## 12. Risks & Unresolved Questions

1. **ETag Blind Spot in Bilingual Two-Feed Merge**: If `montana` has `20` German-only descriptions, `?language=en`'s `ETag` only hashes the `?language=en` XML body. Checking default `/xml` when `any(empty_desc)` mitigates missing text cleanly, **except** if a German description is edited later without altering `?language=en`'s `ETag`, `If-None-Match` on `?language=en` would return `304`! **Resolution for Step 49**: Track whether fallback was needed — or simpler & 100% consistent: poll default `/xml` directly when `?language=en` had `empty_desc == len(positions)` (or omit `If-None-Match` when `board` needed default-language fallback, OR store `board.etag` ONLY for single-language boards).
2. **Large-Board XML Size Cap (>100 positions)**: The largest cached Personio board had `20` positions (`116,649` bytes -> ~5.8 KB/job). A 500-job enterprise board (~2.9 MB) nears `settings.max_response_bytes` (`3 MiB`); may warrant configurable `personio_board_max_response_bytes` (just like `recruitee_board_max_response_bytes`) and explicit truncation protection (`ResponseTooLargeError` -> `snapshot_complete=False`).
3. **Remote False-Negative/False-Positive Rate**: Since Personio XML omits an explicit remote flag, German words (`Deutschlandweit`, `Homeoffice`, `Mobiles Arbeiten`) inside `<office>` or `<jobDescriptions>` must be tested against `resolve_work_model` so ADR 0001/0002 is upheld without guessing.
4. **Enopai Sparse Job (`1/4` empty in both default & `?language=en`)**: Confirms rare positions have no XML `<jobDescriptions>` in *either* language while HTML JSON-LD has description; Step 49 must decide whether `description=None` is kept per ADR 0001 or an optional bounded detail hydration is added later.

---

## 13. Exact Smallest Viable Implementation Scope (Step 49)

1. `src/project_files/ats_url_parser.py`: add `parse_personio_board_root_url(url)` accepting `.com` and `.de`.
2. `src/project_files/ats_page_enricher.py`: widen `"jobs.personio.com"` check at line 818 to `.jobs.personio.(com|de)`.
3. `src/project_files/company_board_registry.py`: add `"personio"` to `MONITORABLE_PROVIDERS` and standardize `build_canonical_board_url` to `.com` (or preserve verified host cleanly).
4. `src/project_files/board_adapters.py`: add `parse_personio_xml_feed` + `PersonioBoardAdapter` + register `"personio"` in `BOARD_ADAPTERS`.
5. `src/project_files/direct_board_router.py`: add `probe_personio_board` and wire `"personio"` into `probe_direct_boards`.
6. `src/project_files/search_pipeline.py`: register discovered Personio board-root URLs in `SearchOrchestrator._enrich_ats_item`.
7. `tests/fixtures/real/personio/*` + `tests/test_personio_monitoring.py`: offline real-fixture + MockTransport regression suite.

---

## 14. Proposed Regression Tests (Step 49)

1. Registry, `BOARD_ADAPTERS`, and `parse_personio_board_root_url` (`.com`, `.de`, rejects `/job/...`, `www`, invalid slugs).
2. Real fixture parsing across `montana`, `saeki`, `enopai`, and empty `traviangames`.
3. Bilingual merge test (`?language=en` + default `/xml` fallback without overwriting English descriptions with German).
4. Conditional `ETag` / `304 Not Modified` preserves active jobs and resets `missing_confirmation_count`.
5. Empty `<workzag-jobs></workzag-jobs>` sets `snapshot_complete=True` cleanly; malformed XML, `<!DOCTYPE`/`<!ENTITY` anywhere in payload, duplicate `<id>`, missing `<id>`/`<name>`, `404`, `503`, timeout, and `ResponseTooLargeError` ALL set `success=False, snapshot_complete=False` without closing existing jobs.
6. Field normalization (`employmentType`, `schedule`, `createdAt`, `office` + `additionalOffices`, work model `None` when unstated per ADR 0001).
7. Completeness preservation (`CacheStore._merge_preserving_completeness`) retaining prior HTML-derived fields.
8. Pre-existing `'unsupported'` `montana` row promotion on `CompanyBoardRegistry._ensure_db()`.
9. Direct board router `probe_personio_board` and `probe_direct_boards(..., platforms=["personio"])`.
10. Verify operational `data/` asset SHA-256 checksums untouched.

---

## 15. Measurable Acceptance Criteria (Step 49)

1. `0` Serper credits and `0` live outbound requests in automated tests.
2. `"personio"` wired in `MONITORABLE_PROVIDERS`, `BOARD_ADAPTERS["personio"]`, `probe_direct_boards`, and `parse_personio_board_root_url`.
3. Pre-existing `'unsupported'` `personio` boards promote cleanly to `'supported'`.
4. `304 Not Modified` verified with `If-None-Match`; all failed/truncated/invalid XML paths return `snapshot_complete=False` and never close missing jobs.
5. `.\scripts\verify.ps1` and CI (`ubuntu-latest` + `windows-latest`) pass `100%` with pre/post protected asset hashes identical.

---

## 16. Explicit Non-Goals (Step 48 & Step 49)

- **Step 48**: Investigation & documentation **only** — no changes to `src/`, `tests/`, `tests/fixtures/`, CI, or `data/cache.sqlite`.
- **Authenticated Recruiting API**: Do not integrate Personio's token-authenticated Recruiting API.
- **Workday / Jobvite / JazzHR / BambooHR**: Remain excluded from `MONITORABLE_PROVIDERS` in this step.
- **Unbounded detail scraping**: Do not fire `N` detail HTML GETs on every poll unless explicitly designed under bounded `detail_status` controls later.

---

## 17. Sources & Evidence Timestamps

- **Repository inspection commit**: `f5fac971fb745f4f1bd9df3cc95aee76180f8155` (`main`).
- **Read-only SQLite inventory timestamp**: `2026-11-17T14:44:28Z` (temp copy of `data/cache.sqlite` + `-wal` + `-shm`).
- **Live bounded unauthenticated HTTP GET probes** (`2026-11-17T14:46:19Z` – `14:51:42Z`):
  - `https://montana.jobs.personio.de/xml` (`200`, `116,649` B, ETag `"21713bfc0564c106a0f0ed6badc7ef25"`, `20` items)
  - `https://montana.jobs.personio.com/xml` (`200`, `116,649` B, ETag `"21713bfc0564c106a0f0ed6badc7ef25"`, `20` items)
  - `https://montana.jobs.personio.com/xml?language=en` (`200`, `18,815` B, `20` items, `empty_desc=20`, ETag `"eb96def26982413c3295354cb373c783"`)
  - `https://cosine.jobs.personio.com/xml` (`200`, `44,255` B, `5` items)
  - `https://enopai.jobs.personio.com/xml` (`200`, `6,432` B, `4` items, `empty_desc=4`) & `?language=en` (`200`, `4` items, `empty_desc=1`)
  - `https://enopai.jobs.personio.com/job/2512390` (`200`, `102,607` B, HTML with JSON-LD `JobPosting`)
  - `https://jedox.jobs.personio.com/xml` (`200`, `23,463` B, `9` items, `empty_desc=6`) & `?language=en` (`200`, `9` items, `empty_desc=3`)
  - `https://saeki.jobs.personio.com/xml` (`200`, `12,846` B, `9` items, `empty_desc=8`, ETag `"57f2d8bf31eff0048f8da07bf5939253"`) & conditional `304` (`0` B) & `?language=en` (`200`, `9` items, `empty_desc=0`, ETag `"c9c3a963976190a92f945846101fd9f9"`)
  - `https://adbaker-gmbh.jobs.personio.com/xml` & `.de/xml` (`200`, `130,649` B, `19` items)
  - `https://inexogy.jobs.personio.com/xml` & `.de/xml` (`200`, `101,672` B, `14` items)
  - `https://traviangames.jobs.personio.com/xml` (`200`, `72` B, `0` items) & `https://traviangames.jobs.personio.com/` (`200`, `53,088` B, `job_links=0`)
  - `https://nonexistent-bottom-pot-probe-99999.jobs.personio.com/xml` (`404`, `2,472` B)
  - Contender probes: `expression-networks.breezy.hr/json` (`200`, `26,504` B, `18` items), `solvative.breezy.hr/json` (`200`, `1,721` B, `2` items), `beli.breezy.hr/json` (`200`, `13,123` B, `13` items + `304` `0` B), `corpsafrica.applytojob.com/apply` (`200` HTML, `no-cache`), `brightvisiontechnologies.applytojob.com/apply` (`200` HTML), `burnmanufacturing.applytojob.com/apply/rss` (`410`), `jobs.jobvite.com/{glidewelldental,barracuda-networks-inc}/jobs` (`200` HTML), `amat.wd1.myworkdayjobs.com/External` (`429`).
- **Reference Documentation**: Official Personio Developer / Help documentation for Personio XML recruiting feeds (`{company}.jobs.personio.{com,de}/xml`, unpaginated full-openings XML, sync at least once every hour, `?language=en|de|...`).
