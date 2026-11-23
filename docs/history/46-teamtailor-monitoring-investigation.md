# Step 46: Teamtailor Monitoring & Direct-Routing Investigation

**Status:** Investigation & Feasibility Decision Complete (Documentation Only — No Step 46/47 Implementation)  
**Date:** 2026-11-17  
**Investigation Branch:** `step/46-teamtailor-monitoring-investigation`  
**Stacked Base:** `step/45-smartrecruiters-quality-pipeline` (`428ffe93b24083dd2ae763f8fffd5754eb0a9f58`, PR #42 OPEN & unmerged)  
**Selected Candidate:** `teamtailor` (over `bamboohr`, `personio`, `jobvite`, `breezy`, `jazzhr`, `workday`, and remaining non-monitored ATS platforms)  
**Feasibility Decision:** **`suitable with constraints`**

---

## 1. Branch Topology Note

This investigation branch (`step/46-teamtailor-monitoring-investigation`) is stacked on top of `step/45-smartrecruiters-quality-pipeline` (`428ffe93b24083dd2ae763f8fffd5754eb0a9f58`, PR #42), which remains **OPEN and UNMERGED** on GitHub.  
Branching from `origin/main` (`c4e8a1654d5ad31dc69b0088e7a462878be42e1c`) would omit Step 45 (`SmartRecruiters` quality pipeline, Step 45 Playwright DB isolation hardening, and the Scenario B recovery documentation recorded in `docs/steps/45-smartrecruiters-quality-pipeline.md`). Any stacked Draft PR for this investigation targets `--base step/45-smartrecruiters-quality-pipeline` so PR #42 stays cleanly independent and unmerged.

---

## 2. Executive Summary & Candidate Selection

Following Steps 42–45 (`recruitee` and `smartrecruiters`), `MONITORABLE_PROVIDERS` in `src/project_files/company_board_registry.py` covers six ATS providers: `greenhouse`, `lever`, `ashby`, `workable`, `recruitee`, and `smartrecruiters`. Twelve `ATS_PLATFORMS` entries (`src/project_files/config.py`) remain outside `MONITORABLE_PROVIDERS`: `workday`, `bamboohr`, `jobvite`, `icims`, `personio`, `teamtailor`, `breezy`, `taleo`, `jobadder`, `jazzhr`, `avature`, and `successfactors`.

Using read-only inspection of the recovered operational SQLite database (`data/cache.sqlite`, `file:...?mode=ro`), existing repository extraction modules/fixtures, and bounded sequential unauthenticated HTTP GET probes (`0` Serper credits, no DB writes), **Teamtailor** is selected as the strongest next Step 46/47 candidate:

1. **Largest non-monitored `company_boards` footprint**: `7` already-registered operational `teamtailor` boards (`dotworld`, `eitrawmaterialsgmbh`, `gravita`, `implicity`, `smartestenergy`, `wiremind-1714146283`, `worksterjobs`), vs `1` each for `jobvite` (`glidewelldental`) and `personio` (`montana`), and `0` for `bamboohr`, `workday`, `breezy`, and `jazzhr`.
2. **Mature Step 35 quality pipeline already built**: Teamtailor already has dedicated DOM/JSON-LD extraction (`_extract_teamtailor_dom` in `src/project_files/ats_page_enricher.py`), custom-domain HTML proof resolution (`parse_teamtailor_custom_domain_url` in `src/project_files/ats_url_parser.py` and `_resolve_teamtailor_candidate` in `src/project_files/search_pipeline.py`), verified logo extraction (`_extract_teamtailor_logo` in `src/project_files/logo_extractor.py`), `40` real HTML/JSON fixtures under `tests/fixtures/real/teamtailor/`, and `tests/test_teamtailor_pipeline.py`.
3. **Unauthenticated public RSS feed verified across 100% of registered boards**: `GET https://{slug}.teamtailor.com/jobs.rss` returned HTTP `200 OK` (`application/rss+xml; charset=utf-8`) on all `7/7` registered boards plus a regional host (`cc-jobs-jobsity.na.teamtailor.com/jobs.rss`), complete with `ETag` + `Last-Modified` (`304 Not Modified` verified with `0` bytes), full HTML `<description>`, `<pubDate>`, `<guid>`, `<remoteStatus>`, `<tt:locations>`, `<tt:department>`, and `<tt:role>`.

**Why `suitable with constraints` (not unconditionally `suitable`):**  
Live probing of `worksterjobs.teamtailor.com/jobs.rss` revealed that Teamtailor's RSS feed **silently truncates at 100 `<item>` entries and ignores `?page=2`** (`?page=2` returns the exact same 100 items), whereas the HTML `/jobs` board paginates at `20` items/page (`page=2` links present). Integrating Teamtailor into `BoardMonitor` safely requires handling that 100-item ceiling explicitly so boards with `>= 100` jobs never falsely auto-close unreturned postings (`missing_confirmation` / `mark_missing_jobs_closed`), alongside custom-domain slug/URL nuances and `employmentType`/logo supplementation from HTML pages.

---

## 3. Baseline Inventory & Contender Comparison

### 3.1 Recovered Operational Database Inventory (`data/cache.sqlite`, read-only)

From read-only inspection of `data/cache.sqlite` (`14,016,512` bytes, SHA-256 `e64b4c020e694f738aaef195bd02a17ab86ee7275a7092b380d6bd234b1919d`):

| ATS Provider | `company_boards` | `monitoring_capability` | `url_cache` matches | `serper_cache` unique URLs | Real Fixtures (`tests/fixtures/real/`) |
|---|---:|---|---:|---:|---:|
| **Lever** (monitored) | 36 | `supported` | — | — | 22 files |
| **Greenhouse** (monitored) | 34 | `supported` | — | — | 33 files |
| **Ashby** (monitored) | 21 | `supported` | — | — | 13 files |
| **SmartRecruiters** (Step 45) | 13 | `provisional` (legacy rows) | — | — | 13 files |
| **Workable** (Step 41) | 9 | `provisional` (legacy rows) | — | — | 21 files |
| **Teamtailor** | **7** | `unsupported` | **31** (incl. 2 test hosts) | **51** (`47` non-support/www) | **40 files** |
| **Jobvite** | 1 | `unsupported` | 6 (incl. `company`) | 33 | 6 files |
| **Personio** | 1 | `unsupported` | 3 (incl. 2 `acme`) | 27 | 0 |
| **BambooHR** (`PROVISIONAL_PROVIDERS`) | 0 | `—` | 0 | 10 (`example.com` only) | 1 (`deel_list.json`) |
| **Workday** | 0 | `—` | 46 | 64 | 7 files |
| **Breezy HR** | 0 | `—` | 0 | 29 | 0 |
| **JazzHR** (`applytojob.com`) | 0 | `—` | 3 (incl. `company`) | 23 (+10 `example.com`) | 0 |
| **iCIMS / Avature / Taleo / JobAdder** | 0 | `—` | 4 (`avature`) | 36 / 25 / 24 / 20 | 8 (`avature`) |

Registered operational Teamtailor boards in `company_boards` (all `discovery_source='search'`, `verification_status='candidate'`, `monitoring_capability='unsupported'`):
1. `dotworld` (`Dotworld`, `https://dotworld.teamtailor.com`)
2. `eitrawmaterialsgmbh` (`EIT RawMaterials`, `https://eitrawmaterialsgmbh.teamtailor.com`)
3. `gravita` (`Gravita`, `https://gravita.teamtailor.com`)
4. `implicity` (`Implicity`, `https://implicity.teamtailor.com`)
5. `smartestenergy` (`SmartestEnergy`, `https://smartestenergy.teamtailor.com`)
6. `wiremind-1714146283` (`Wiremind`, `https://wiremind-1714146283.teamtailor.com`)
7. `worksterjobs` (`Workster Jobs`, `https://worksterjobs.teamtailor.com`)

### 3.2 Empirical Comparison of Top Contenders

| Criterion | Teamtailor | Personio | BambooHR | Jobvite | Workday |
|---|---|---|---|---|---|
| **Public listing feed** | `GET https://{slug}.teamtailor.com/jobs.rss` (`200`, `application/rss+xml`) | `GET https://{slug}.jobs.personio.{com,de}/xml` (`200`, `text/xml`) | `GET https://{slug}.bamboohr.com/careers/list` (`302` on `deel` -> moved off) | No RSS/JSON (`/jobs/rss` returned `303` -> `?error=301`); HTML only | Multi-part tenant/wdN/site CXS POST; no standardized board discovery |
| **ETag / Last-Modified / 304** | Verified both `ETag` (`W/"..."`) and `Last-Modified`; `304` verified (`0` B) | `ETag` present; `montana` `.de` vs `saeki` `.com` TLD split | No `304` cache contract | No `ETag`/`Last-Modified` on `glidewelldental` HTML | No standardized board feed `304` |
| **Descriptions in single list GET** | Yes — full HTML `<description>` inside each `<item>` | Yes — `<jobDescriptions>` inside `<position>` | **No** — `/careers/list` omits descriptions; requires N `/detail` GETs | **No** — requires HTML scraping | **No** — paginated CXS summaries lack full details |
| **Operational DB boards / existing quality step** | **7 boards** + Step 35 extractor/logo/custom-domain pipeline | 1 board (`montana`) + regex-only enricher, no `.com`/`.de` persistence | **0 real DB rows** (`0` boards, `0` url_cache, `0` real serper_cache) | 1 board (`glidewelldental`), HTML only | 0 boards (`build_canonical_board_url` returns `None`) |
| **Key limitation found** | `/jobs.rss` silently caps at **100** items & ignores `?page=2` | `.com` vs `.de` TLD split + XML feed optional in tenant settings | `0` operational presence + detail fan-out | HTML-only board + no feed headers | Non-standardized `wdN` + `site_id` discovery |

**Selection Verdict:**
- **Teamtailor** wins decisively on operational database footprint (`7` boards, `31` `url_cache`, `47` genuine `serper_cache` URLs across `35` unique hosts), existing Step 35 extraction/logo/fixture assets (`40` fixtures), and single-GET RSS completeness with verified HTTP `304`.
- **Personio** (`/xml`) is a plausible later follow-up (`Step 48+`) if `.com`/`.de` TLD canonicalization and a dedicated quality pipeline are built first.
- **BambooHR** (currently marked `PROVISIONAL_PROVIDERS` with `BambooHRClient`) has **zero** real operational footprint in `data/cache.sqlite` (`0` boards, `0` `url_cache`, `0` real `serper_cache`), and `deel.bamboohr.com/careers/list` now returns `302` -> `https://www.bamboohr.com`.
- **Jobvite** lacks an unauthenticated JSON/RSS listing feed (`303` error redirect on `/jobs/rss`) and **Workday** lacks standardized board root routes.

---

## 4. Public Endpoint Findings (Live Bounded Probes)

All probes used sequential unauthenticated `GET` requests (`follow_redirects=False`, 10s timeout, `0` Serper credits):

### 4.1 All 7 Operational Boards + Regional Subdomain + Conditional 304 + Negative 404

| Probe Target | HTTP | Bytes | `Content-Type` | `ETag` / `Last-Modified` / `Cache-Control` | Parsed Items & Notes |
|---|---:|---:|---|---|---|
| `https://dotworld.teamtailor.com/jobs.rss` | `200` | `139,311` | `application/rss+xml; charset=utf-8` | `W/"ad32381503dc904478aad6132f9996cb"`, `Tue, 17 Nov 2026 11:04:34 GMT`, `max-age=5, public, must-revalidate` | **7** `<item>`s; `<channel><title>`: `Dotworld`; `remoteStatus`: `['fully']` |
| `https://dotworld.teamtailor.com/jobs.rss` (with `If-None-Match` + `If-Modified-Since`) | **`304`** | `0` | — | `W/"ad32381503dc904478aad6132f9996cb"` | Clean conditional revalidation verified |
| `https://dotworld.teamtailor.com/jobs` | `200` | `105,164` | `text/html; charset=utf-8` | `W/"ad32381503dc904478aad6132f9996cb"` | Shares weak ETag validator with `/jobs.rss` |
| `https://eitrawmaterialsgmbh.teamtailor.com/jobs.rss` | `200` | `58,116` | `application/rss+xml; charset=utf-8` | `W/"7e88f82b93ac92761e55c1592005a4dd"`, `Mon, 16 Nov 2026 13:17:43 GMT` | **4** `<item>`s; `<channel><title>`: `EIT RawMaterials` |
| `https://gravita.teamtailor.com/jobs.rss` | `200` | `116,823` | `application/rss+xml; charset=utf-8` | `W/"486f6e1b11f5ec9d18e8ce86f0e53e0e"`, `Wed, 28 Oct 2026 11:45:31 GMT` | **16** `<item>`s; custom `<link>` host `careers.gravita.com` |
| `https://implicity.teamtailor.com/jobs.rss` | `200` | `132,650` | `application/rss+xml; charset=utf-8` | `W/"8be6c0170ef935d6c2145f6c27a5e486"`, `Tue, 17 Nov 2026 09:47:15 GMT` | **13** `<item>`s; `<channel><title>`: `Implicity` |
| `https://smartestenergy.teamtailor.com/jobs.rss` | `200` | `224,262` | `application/rss+xml; charset=utf-8` | `W/"0cdec481ba535cfbe1dc36afcb548619"`, `Tue, 17 Nov 2026 11:35:25 GMT` | **28** `<item>`s; `remoteStatus`: `['fully', 'hybrid', 'none', 'onsite']` |
| `https://wiremind-1714146283.teamtailor.com/jobs.rss` | `200` | `116,246` | `application/rss+xml; charset=utf-8` | `W/"0471c2d9945f2fe808f28af5f398d48c"`, `Tue, 17 Nov 2026 09:04:54 GMT` | **13** `<item>`s; `<channel><title>`: `Wiremind` |
| `https://worksterjobs.teamtailor.com/jobs.rss` | `200` | `477,129` | `application/rss+xml; charset=utf-8` | `W/"51268a8a03f65e2b28a04f58fb3fa84b"`, `Tue, 17 Nov 2026 10:23:43 GMT` | **100** `<item>`s (**cap observed!**) |
| `https://worksterjobs.teamtailor.com/jobs.rss?page=2` | `200` | — | `application/rss+xml; charset=utf-8` | — | **100** `<item>`s — **identical to page 1** (`identical_to_p1=True`) |
| `https://worksterjobs.teamtailor.com/jobs` | `200` | `121,905` | `text/html; charset=utf-8` | — | **20** `/jobs/{id}` links on page 1 + `page=2` HTML pagination marker |
| `https://cc-jobs-jobsity.na.teamtailor.com/jobs.rss` | `200` | `144,678` | `application/rss+xml; charset=utf-8` | — | **18** `<item>`s; `<channel><title>`: `Jobsity` |
| `https://nonexistent-slug-999999-test.teamtailor.com/jobs.rss` | `404` | `837` | — | — | Clean 404 on unknown slug |

### 4.2 Observed RSS Schema (`/jobs.rss`)

- **Channel metadata (`<rss><channel>`)**:
  - `<title>`: Employer display name (e.g. `Dotworld`, `Wiremind`, `Jobsity`).
  - `<description>`: Career-site tagline (`Offres d'emploi disponibles`, `Open Positions`, or empty `''`).
  - `<link>`: Canonical `.teamtailor.com/jobs` URL.
- **Item fields (`<item xmlns:tt="https://teamtailor.com/locations">`)**:
  - `<title>`: Job title string.
  - `<description>`: Full escaped HTML body (headings, bullets, paragraphs).
  - `<pubDate>`: RFC 2822 timestamp (e.g. `Fri, 30 Oct 2026 11:08:43 +0100`).
  - `<link>`: Canonical posting URL (`/jobs/{numeric_id}-{slug}`, may use custom domain such as `https://careers.gravita.com/jobs/8672245-audit-manager` or localized prefix).
  - `<remoteStatus>`: Observed enum values: `fully`, `hybrid`, `none`, `onsite` (`none` means unspecified, not necessarily onsite — do **not** map `none` to onsite without checking location/text).
  - `<guid>`: Stable UUID (e.g. `3f33c4d4-5167-480f-82c6-d7a17a573a3f`).
  - `<tt:locations>`: Contains zero or more `<tt:location>` children, each with `<tt:name>`, `<tt:address>`, `<tt:zip>`, `<tt:city>`, `<tt:country>` (supports multi-location postings such as `Lisbon Portugal` + `Porto Portugal`).
  - `<tt:department>` and `<tt:role>`: String labels (may be empty elements).

---

## 5. Authentication, Rate Limits & Politeness

- **Authentication**: None required for `{slug}.teamtailor.com/jobs.rss` or `{slug}.teamtailor.com/jobs`. Teamtailor's official REST API (`api.teamtailor.com/v1`) requires per-company API tokens (`Token token=...`) and is therefore unsuitable; `/jobs.rss` and public career pages are completely unauthenticated.
- **Caching & Bandwidth**: Every tested board sends `Cache-Control: max-age=5, public, must-revalidate`, weak `ETag` (`W/"..."`), and `Last-Modified`, and honors `If-None-Match` + `If-Modified-Since` with `HTTP 304` (`0` bytes). Response sizes on our `7` operational boards ranged from `58 KB` (`4` items) to `477 KB` (`100` items), comfortably below `settings.max_response_bytes` (`3 MiB`), though bounded streaming via `throttled_stream_bytes` (e.g. `4–8 MiB` ceiling) protects against malformed feeds or large XML descriptions.
- **Rate Limits**: No rate-limit headers (`X-RateLimit-*` or `429`) were triggered during sequential 0.5s-spaced requests. Existing host throttling + circuit breakers in `src/project_files/http_resilience.py` (`throttled_stream_bytes` / `throttled_get`, per-host concurrency `3`) should be used for all board fetches and any optional detail hydration.

---

## 6. Pagination, Snapshot Completeness & Closure Semantics (Critical Constraint)

1. **Silent 100-item RSS cap**: `worksterjobs.teamtailor.com/jobs.rss` returned `100` items and returned the exact same `100` items on `?page=2`. Thus **an RSS snapshot of `len(items) >= 100` cannot prove absence of older active jobs**.
2. **BoardMonitor reconciliation gap**: Inspecting `src/project_files/board_monitor.py:114-125` shows `BoardMonitor.check_single_board` **unconditionally** calls either `mark_missing_jobs_closed` or `reconcile_missing_jobs` whenever `result.success and not result.not_modified`. `BoardCheckResult` (`src/project_files/board_adapters.py:51-63`) currently has no `snapshot_complete: bool = True` / `skip_missing_reconciliation: bool = False` flag!
   - **Required safeguard for Step 47**: Either add `snapshot_complete: bool = True` to `BoardCheckResult` and skip missing-job closure in `BoardMonitor.check_single_board` whenever `snapshot_complete=False` (when `len(rss_items) >= 100`), **or** fall back to bounded HTML `/jobs?page=1..N` pagination when `len(rss_items) >= 100` (with `snapshot_complete=False` if HTML pagination hits a safety page cap or partial fetch error). Never auto-close missing jobs from a truncated 100-item feed.
3. **Zero-item valid board vs error**: An active company with 0 open jobs serves a valid `<rss><channel>...</channel></rss>` with `0` `<item>` tags (`200 OK`); only treat HTTP non-200 or malformed XML as failure (`failure_count += 1`), never closing jobs on fetch/parse errors. For transient RSS flakiness, `missing_confirmation_threshold=2` is safer than `1` (matching Step 45 SmartRecruiters).
4. **304 + `remoteStatus` changes**: Because `/jobs.rss` includes `ETag` and `Last-Modified`, `304 Not Modified` short-circuits cleanly; when modified, comparing sorted `(job_id, pubDate, title/description/remoteStatus/location hash)` via `compute_board_fingerprint` avoids unnecessary DB writes while catching edits.

---

## 7. Detail Hydration, Identity, Custom Domains & Failure Semantics

### 7.1 Identity & Canonical URL
- `ParsedATSUrl` (`src/project_files/ats_url_parser.py`) uses `ats="teamtailor"`, `company_slug` (`sub_chain`, supporting multi-label regional tokens like `cc-jobs-jobsity.na`), and numeric `job_id` from `/jobs/(\d+)`.
- Canonical ID in `JobExtractionService` / `url_normalizer.py`: `teamtailor:{slug}:{numeric_id}` (or canonical `f"https://{slug}.teamtailor.com/jobs/{numeric_id}-..."` vs preserved custom-domain `<link>`).
- **Custom-domain quirk (`gravita` / `lunar`)**:
  - For `gravita`, `gravita.teamtailor.com/jobs.rss` lists `<link>https://careers.gravita.com/jobs/8672245-audit-manager</link>`. Matching `job_id` by `/jobs/(\d+)` works cleanly even when `<link>` uses a custom domain (`careers.gravita.com`).
  - Conversely, when search results return a custom-domain job URL directly (e.g., `https://jobs.lunar.app/jobs/8614059-...`), `parse_teamtailor_custom_domain_url` sets `company_slug = host.removeprefix("jobs.").split(".")[0]` (`lunar`) if it doesn't redirect to `*.teamtailor.com`. Probing `https://lunar.teamtailor.com/jobs.rss` may `404` if the customer's actual `.teamtailor.com` subdomain differs (e.g. `lunarway` or a timestamped slug like `wiremind-1714146283`), or if an HTML page links back to `{real_slug}.teamtailor.com`. **Constraint:** direct routing & board discovery must NOT assume custom-domain derived slugs always map 1:1 to `{slug}.teamtailor.com` without HTML verification (`canonical`/asset host inspection or verified HTTP 200 RSS response matching the posting/company).

### 7.2 RSS Completeness vs HTML Detail Fields
- **Present directly in `/jobs.rss`**: `title`, full HTML `description` (convertible via `to_markdown`), `pubDate` (published timestamp), `remoteStatus` (`fully` -> `remote`, `hybrid` -> `hybrid`, `onsite` -> `onsite`, `none` -> unresolved/`None`), `<tt:locations>` (`city`, `country`, `name`), `<tt:department>`, `<tt:role>`, `<link>`, `<guid>`, `<channel><title>`.
- **Absent from `/jobs.rss` (HTML-only)**:
  - `employmentType` (`JobPosting` JSON-LD / `<dl>` terms such as Full-time, CDI, Internship)
  - `salary` (`<dl>` / JSON-LD)
  - Company logo (`_extract_teamtailor_logo` inspects `/jobs` board HTML or a single posting HTML page; `<rss><channel>` has no `<image>` element in the probed feeds)
- **Implication for Step 47**:
  - Board monitoring from `/jobs.rss` yields **complete authentic descriptions, locations, departments, published dates, and work models in 1 HTTP GET**, without mandatory N-job detail fan-out!
  - Company logo can be enriched once per board (`ttl_seconds = 7 * 86400`, cached on `company_boards`, identical pattern to `enrich_recruitee_board_identity`) from `https://{slug}.teamtailor.com/jobs` HTML via `_extract_teamtailor_logo`.
  - If optional `employmentType` / `salary` enrichment via `_extract_teamtailor_dom` is desired later, keep it strictly bounded (or reuse cached `url_cache` values via completeness-preserving merge rather than doing unbounded per-job HTML fetches on `100`-job boards). Wait-free baseline monitoring does **not** need N HTML detail GETs per poll.

### 7.3 Existing Codebase Coverage & Gaps (`src/project_files/`)
1. `company_board_registry.py`: `MONITORABLE_PROVIDERS` lacks `"teamtailor"` (currently `supports` only 6 providers; `7` DB rows stay `monitoring_capability='unsupported'`). Safe promotion in Step 47 requires checking how existing `unsupported` Teamtailor boards in `company_boards` should be re-promoted on verification (`sync_from_search_results` / migration/verification path).
2. `board_adapters.py`: No `TeamtailorBoardAdapter` in `BOARD_ADAPTERS`.
3. `board_monitor.py`: No `snapshot_complete` guard against truncated RSS feeds (`len >= 100`) before calling `mark_missing_jobs_closed` / `reconcile_missing_jobs`.
4. `direct_board_router.py`: `probe_direct_boards` only probes the 6 existing monitored providers, not `probe_teamtailor_board`. Note: Teamtailor slug guessing during search carries a slight extra risk for hyphenated/timestamped subdomains (e.g. `wiremind-1714146283`), though 1-token company slugs like `dotworld`, `implicity`, `gravita`, `smartestenergy` work directly via `GET https://{slug}.teamtailor.com/jobs.rss`.
5. `ats_url_parser.py`: No `parse_teamtailor_board_root_url(url)` helper yet (`parse_teamtailor_custom_domain_url` only parses `/jobs/{id}` posting paths; `_TEAMTAILOR_RESERVED_SUBDOMAINS` already exists).
6. `logo_extractor.py`: `_extract_teamtailor_logo` already exists!

---

## 8. Smallest Credible Step 47 Implementation Scope

1. **RSS Feed Parser & `TeamtailorBoardAdapter` (`src/project_files/board_adapters.py`)**:
   - Safe XML parsing (`defusedxml` if available or `xml.etree.ElementTree` with `ResponseTooLargeError` streaming cap and zero external entity resolution; strict RSS `<rss><channel>` structural validation).
   - Conditional `If-None-Match` / `If-Modified-Since` -> HTTP `304` handling.
   - Deterministic `compute_board_fingerprint` across `(job_id, pubDate, content_hash)`.
   - Authentic conversion of each `<item>` (`title`, HTML->Markdown `description`, `pubDate`, `<tt:locations>`, `<tt:department>`, `<tt:role>`, `<remoteStatus>` ignoring `'none'`, plus board-level cached logo lookup via `https://{slug}.teamtailor.com/jobs` + `_extract_teamtailor_logo`).
   - Preserve `<link>` (including custom domains like `careers.gravita.com/jobs/...`) while normalizing canonical ID under `teamtailor:{board_token}:{numeric_id}`.
2. **Truncated Feed Closure Guard (`src/project_files/board_adapters.py` & `src/project_files/board_monitor.py`)**:
   - Add `snapshot_complete: bool = True` to `BoardCheckResult` (and `missing_confirmation_threshold: int = 2` for Teamtailor).
   - When `len(items) >= 100`, mark `snapshot_complete=False` (unless bounded HTML `/jobs?page=...` fallback fetches all pages cleanly) so `BoardMonitor.check_single_board` skips `mark_missing_jobs_closed` / `reconcile_missing_jobs` and never falsely closes jobs beyond item #100.
3. **Registry Promotion & URL Root Helper (`src/project_files/company_board_registry.py`, `src/project_files/ats_url_parser.py`)**:
   - Add `"teamtailor"` to `MONITORABLE_PROVIDERS` and ensure existing `teamtailor` rows with `monitoring_capability='unsupported'` upgrade safely when verified/re-synced.
   - Add `parse_teamtailor_board_root_url`.
4. **Direct Board Routing (`src/project_files/direct_board_router.py`)**:
   - Add `probe_teamtailor_board(slug, client)` using `GET https://{slug}.teamtailor.com/jobs.rss` via `throttled_stream_bytes` (strictly rejecting redirects off `.teamtailor.com` / invalid feeds and passing regional/alphanumeric slugs cleanly via `is_valid_board_slug`).
5. **Out of Scope for Step 47**:
   - Automatic discovery of `.teamtailor.com` slugs for arbitrary custom domains that do not expose their `.teamtailor.com` subdomain in HTML or redirects.
   - Per-job HTML fan-out (`N` extra GETs) solely to scrape `<dl>` salary/employmentType during routine board polling (preserve via existing `CacheStore._merge_preserving_completeness` instead).

---

## 9. Unknowns, Risks & Fixture Plan

### 9.1 Open Unknowns
- **Exact RSS threshold edge behavior**: We proved `worksterjobs.teamtailor.com/jobs.rss` caps at `100` items and ignores `?page=2`. Whether *every* Teamtailor tenant uses `100` (vs e.g. configurable lower/higher limits) is unverified beyond `worksterjobs` (`100`) and `smartestenergy` (`28`). Treating `len(items) >= 100` as potentially truncated (plus cross-checking if `<link>` or HTML shows page 2) is conservatively safe.
- **Custom-domain HTTP redirects on `/jobs.rss`**: Some tenants redirect `{slug}.teamtailor.com/jobs.rss` or only serve RSS on their custom domain (`careers.company.com/jobs.rss`); probing showed `gravita` serves `/jobs.rss` on `gravita.teamtailor.com` even while `<item><link>` points to `careers.gravita.com`. Step 47 must handle `301`/`302` ONLY with `is_safe_public_https_url` + Teamtailor RSS proof, never blind SSRF redirect following.
- **XXE / Large XML protection**: Although Python's `xml.etree.ElementTree` does not expand external entities by default, Step 47 must enforce streaming byte caps and reject `<!DOCTYPE` / `<!ENTITY` declarations defensively.

### 9.2 Risks & Mitigations
- **False job closure on >100-job boards**: Mitigated by `snapshot_complete=False` when `len(items) >= 100` (or bounded HTML fallback) + `missing_confirmation_threshold=2`.
- **Overwriting richer cached `employmentType` / `salary` from RSS-only polls**: Mitigated because `BoardMonitor.check_single_board` already calls `CacheStore._merge_preserving_completeness(..., preserve_omitted_optional_fields=True)` when `url_cache` has HTML-enriched fields! Step 47 tests should explicitly assert this preservation.
- **Unsupported Teamtailor rows staying stuck in `data/cache.sqlite`**: Currently the `7` operational `teamtailor` boards have `monitoring_capability='unsupported'`; Step 47 must promote them safely on initialization/migration or next registry pass.

### 9.3 Planned Fixtures (for Step 47 Implementation)
Do **not** modify `tests/fixtures/` during this investigation step. In Step 47, add sanitized offline fixtures under `tests/fixtures/real/teamtailor/`:
- `dotworld_rss.xml` (standard multi-job `.teamtailor.com/jobs.rss` with `<tt:locations>`, `<tt:department>`, `<tt:role>`, `remoteStatus`)
- `gravita_rss.xml` (`.teamtailor.com/jobs.rss` emitting custom-domain `<link>https://careers.gravita.com/jobs/...</link>`)
- `worksterjobs_rss_100.xml` (100-item capped RSS snapshot + multi-`<tt:location>` items & `remoteStatus="none"`)
- `worksterjobs_jobs_page1.html` (HTML board listing showing pagination markers and board logo for `_extract_teamtailor_logo`)

---

## 10. Measurable Acceptance Criteria for Step 47

1. **Zero paid API usage**: `TeamtailorBoardAdapter` and `probe_teamtailor_board` perform `0` Serper API calls and work unauthenticated (`tests` run offline with mocked/real XML fixtures).
2. **Conditional 304 support**: `TeamtailorBoardAdapter.check_board` sends `If-None-Match` / `If-Modified-Since` and returns `BoardCheckResult(success=True, not_modified=True)` on HTTP `304`.
3. **Full RSS extraction fidelity**: Correctly parses `<title>`, HTML `<description>` -> Markdown, `<pubDate>`, `<tt:locations>` (including multi-location items), `<tt:department>`, `<tt:role>`, `<remoteStatus>` (mapping `none` -> `None`, never `onsite`), regional subdomains (`*.na.teamtailor.com`), and custom-domain `<link>` (`careers.gravita.com`).
4. **Safe >100-item truncation guard**: Simulated `100`-item RSS response sets `snapshot_complete=False` and provably does **not** close existing `monitored_jobs` missing from the `100` items.
5. **Completeness preservation**: RSS poll updates never erase pre-existing HTML-derived `job_type` / `salary` in `url_cache`.
6. **Registry & Direct Router integration**: `"teamtailor"` included in `MONITORABLE_PROVIDERS`, `BOARD_ADAPTERS["teamtailor"]` registered, existing `'unsupported'` `teamtailor` boards promotable to `'supported'`, and `probe_teamtailor_board` wired into `probe_direct_boards`.
7. **Full regression pass**: Targeted Teamtailor unit/pipeline tests + repository `scripts/verify.ps1` (with strict Playwright DB isolation leaving operational `data/cache.sqlite` untouched).
