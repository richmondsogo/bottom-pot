# Step 01: Repository Audit and Implementation Plan

Initiative: **Extraction Pipeline & Architecture Overhaul**  
Role: **Planner**  
Branch: `step/01-repo-audit`  
Date: 2026-11-01  
Status: **Complete — Awaiting Approval**

---

## 1. Executive Summary & Initiative Goals

Bottom Pot is an ATS-first job discovery engine. Its core value proposition is finding high-signal, authentic job postings directly from primary hiring systems (Greenhouse, Lever, Ashby, Workable, and 16+ ATS platforms, plus Nigerian career boards) without aggregator spam, reposts, or phantom listings.

The goal of this overhaul is to make Bottom Pot's job data **reliable, traceable, and honest**:
1. Every acquisition path (ATS APIs, direct HTML scraping, JSON-LD schema parsing, DOM extraction, and search snippet fallbacks) feeds **one canonical extraction and normalization pipeline**.
2. Missing or ambiguous values stay `null` or `unknown`. No heuristics or fallback defaults may invent data (ADR 0001: "Unknown beats wrong").
3. Field-level provenance and confidence are tracked from source to presentation.
4. Existing external contracts (FastAPI SSE endpoints, React frontend, and CLI scripts) are preserved through compatibility adapters without regressions.

This document records the exhaustive audit of the existing codebase across 11 key architectural dimensions, catalogues confirmed bugs with source evidence, establishes clean test baselines, drafts necessary ADRs (ADR 0024 through ADR 0027), and outlines a validated, 12-step implementation roadmap for subsequent execution.

---

## 2. Test Baseline & Environment Health

Verification was executed on a clean working tree from branch `step/01-repo-audit` (commit derived from `main`).

### 2.1 Standard Verification Suite (`scripts/verify.ps1`)

Running `powershell -ExecutionPolicy Bypass -File .\scripts\verify.ps1` completed with **8 of 8 checks passing**:

| Check Category | Task / Tool | Result | Details |
|---|---|---|---|
| **Repository State** | Git available | **OK** | Git 2.x verified |
| **Repository State** | No tracked secrets | **OK** | Checked `.env`, `*.key`, `*.pem`, `*.secret`, `credentials.json` |
| **Frontend Checks** | CSS Cascade Lint | **OK** | `node scripts/lint_css_cascade.js` passed (0 unlayered element/reset selectors) |
| **Frontend Checks** | Frontend Linting | **OK** | `npm --prefix frontend run lint` (oxlint) passed with 0 errors |
| **Frontend Checks** | Frontend Unit Tests | **OK** | `npm --prefix frontend run test` (vitest): 10 test files, 71 tests passed, 0 failed |
| **Frontend Checks** | Frontend Build & Typecheck | **OK** | `npm --prefix frontend run build` (`tsc -b && vite build`) passed |
| **Backend Checks** | Python Unit Tests | **OK** | `pytest tests/test_api_endpoints.py -q` passed (33 passed) |
| **E2E Browser Tests** | Playwright E2E Suite | **OK** | `npx playwright test` (chromium Desktop Chrome) passed |

**Summary:** `Results: 8 passed, 0 failed, 0 skipped (of 8 checks)`.

### 2.2 Full Backend Pytest Suite (`pytest -v`)

While `scripts/verify.ps1` runs only `test_api_endpoints.py`, executing the complete test suite across all 11 test modules (`pytest -v`) yielded:
- **339 passed**
- **0 failed**
- **21 warnings** in 21.41 seconds.

#### Recorded Warnings Summary (Pre-existing Technical Debt)
1. **Deprecated `datetime.utcnow()` Call (17 occurrences)**:
   - Location: `src/project_files/models.py:138` in `JobListing.freshness_label`:
     ```python
     days = (datetime.utcnow() - self.posted_at.replace(tzinfo=None)).days
     ```
   - Warning: `DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).`
   - Triggered during test runs of `test_api_endpoints.py`, `test_description_extraction.py`, `test_real_api_fixtures.py`, and `test_scrapers_and_clients.py`.
2. **FastAPI `@app.on_event("startup")` Deprecation (2 occurrences)**:
   - Location: `src/api/main.py:201` and internal Starlette router.
   - Warning: `DeprecationWarning: on_event is deprecated, use lifespan event handlers instead.`
3. **SlowAPI Coroutine Inspection Deprecation (2 occurrences)**:
   - Location: `slowapi/extension.py:720` (`asyncio.iscoroutinefunction` slated for removal in Python 3.16).

---

## 3. Detailed Audit Findings (Checklist Items 1–11)

### Item 1: Models & Dead Scaffolding

- **`JobListing` (`src/project_files/models.py:66-154`)**:
  - The live operational model used for all search results, caching, and SSE serialization.
  - *Issues*: Contains mixed-responsibility computed fields (`_compute_confidence` lines 117–131 hardcoding arbitrary additions/penalties), naive date comparison in `freshness_label` (lines 133–153), loose types (`salary: JobSalary | str | None = None` line 98), and fields specific to scraping implementation details.
- **`CanonicalJob` (`src/project_files/models.py:265-281`)**:
  - Contains rich fields: `field_evidence: list[FieldEvidence]`, `field_validations: list[FieldValidation]`, `field_confidence: list[FieldConfidence]`.
  - *Usage Status*: **DEAD SCAFFOLDING in production**. A global codebase search reveals `CanonicalJob` is imported and used **only** in `tests/test_contracts_and_observability.py`. It is never instantiated or returned by `ats_api_client.py`, `ats_page_enricher.py`, `nigerian_scrapers.py`, `search_pipeline.py`, or `src/api/main.py`.
- **`SearchResponse` (`src/project_files/models.py:155-164`)**:
  - *Usage Status*: **DEAD SCAFFOLDING**. Defined at line 155 with fields `query`, `total`, `results: list[JobListing]`, `serper_queries_used`, etc., but never imported, instantiated, or returned anywhere in `src/` or `tests/`. Bottom Pot search operates exclusively via SSE streaming (`ResultsBatch` and `DoneEvent`).
- **`RawSearchResults` (`src/project_files/models.py:47-59`)**:
  - Active only in the legacy CLI script `main.py` and `serper_searcher.py`.
  - *Bug*: Line 58 specifies `scraped_at: datetime = datetime.now(timezone.utc)`, which evaluates once at class definition time rather than per instance instantiation (`Field(default_factory=...)`).

### Item 2: Provider Adapters & Normalization Reimplementations

The codebase supports 18 ATS platforms in `SUPPORTED_ATS_PATTERNS` (`ats_url_parser.py:31-50`), split into two tiers: 7 dedicated API clients and 11 fallback enricher integrations, plus 4 Nigerian scrapers.

| Provider | Ingestion Mechanism | Raw Fields Extracted | Reimplemented / Divergent Normalization |
|---|---|---|---|
| **Greenhouse** (`ats_api_client.py:105`) | `GET /v1/boards/{slug}/jobs/{id}` JSON | `title`, `location.name`, `content` (HTML), `first_published`, `created_at`, `updated_at`, `employment_type` | • Re-implements ISO date parsing with `.replace("Z", "+00:00")`<br>• Falls back to `updated_at` if `first_published` missing (violates freshness rule)<br>• Completely ignores salary<br>• Does NOT pass description text to `resolve_work_model` |
| **Lever** (`ats_api_client.py:210`) | `GET /v0/postings/{slug}/{id}` JSON | `text`, `categories.location`, `categories.commitment`, `workplaceType`, `description`, `lists`, `createdAt` | • Re-implements epoch ms timestamp division (`createdAt / 1000`)<br>• Custom joins `lists` into `parts.append("<h3>...</h3>")`<br>• Ignores potential salary objects in posting<br>• Does NOT pass description to `resolve_work_model` |
| **Ashby** (`ats_api_client.py:316`) | `GET /posting-api/job-board/{slug}` JSON | Fetches **entire company board**, iterates to find `job_id`. `title`, `locationName`, `employmentType`, `workplaceType`, `publishedAt`, `descriptionHtml`, `compensation` | • Re-implements ISO date parsing<br>• **Ignores structured compensation object** (`compensationTierSummary` / `targetSalaryRange`) present in Ashby API payload<br>• Does NOT pass description to `resolve_work_model` |
| **SmartRecruiters** (`ats_api_client.py:414`) | `GET /v1/companies/{slug}/postings/{id}` JSON | `name`, `location.city`, `location.remote` (bool), `location.hybrid` (bool), `typeOfEmployment.label`, `jobDescription.text`, `releasedDate` | • Synthesizes string `sr_workplace = "hybrid"` or `"remote"` from booleans to bypass `_map_enum` bool check<br>• Ignores salary<br>• Re-implements ISO date parsing<br>• Does NOT pass description to `resolve_work_model` |
| **Workable** (`ats_api_client.py:519`) | `GET https://r.jina.ai/...` Markdown | Markdown summary line `> Company · Location · Employment`, `**Workplace:**`, `**Department:**`, `Posted ...` | • Extracts fields via regex from Jina markdown mirror<br>• Marked as `data_source="scrape"`<br>• Ignores salary<br>• Does NOT pass description to `resolve_work_model` |
| **BambooHR** (`ats_api_client.py:607`) | `GET /{slug}.bamboohr.com/careers/list` JSON | Fetches entire careers list. `jobTitle`, `location.city`, `locationType`, `department` | • **No job description available** in list endpoint (`description=None`)<br>• **No posting date available** (`posted_at=None`)<br>• Ignores salary |
| **Recruitee** (`ats_api_client.py:706`) | `GET /api/offers/{id}` JSON | `title`, `location`, `workplace_type`, `description`, `employment_type`, `created_at`, `salary` | • Re-implements ISO date parsing<br>• Ignores salary object in offer payload<br>• Does NOT pass description to `resolve_work_model` |
| **Workday** (`ats_page_enricher.py:205`) | `GET /wday/cxs/{tenant}/{site}/job/{slug}` JSON | `jobPostingInfo.title`, `jobPostingInfo.location`, `timeType`, `jobDescription`, `startDate`, `remoteType` | • Custom hardcoded check for Deloitte: `"Télétravail partiel" -> hybrid`<br>• Ignores compensation<br>• Does NOT pass description to `resolve_work_model` |
| **Generic Enricher** (`ats_page_enricher.py:350`) | HTML fetch + JSON-LD / DOM parsing (SAP, Taleo, Personio, JazzHR, Jobvite, etc.) | JSON-LD `JobPosting`, meta tags, DOM selector tables | • **Confirmed Bug (Line 457)**: `raw_html = response.text` raises `NameError` on Personio pages<br>• **Confirmed Bug (Lines 296, 327)**: Circuit breaker/WAF fallbacks hardcode `is_remote=False` instead of `None`<br>• Ignores JSON-LD `baseSalary` |
| **Nigerian Scrapers** (`nigerian_scrapers.py`) | HTML scrape: Jobberman, MyJobMag, NGCareers, HotNigerianJobs | Card headings, meta badges, `.mycase4` body text | • Re-implements custom salary regexes in each scraper, dumping raw unparsed strings into `JobListing.salary`<br>• Bypasses `description_quality` by hardcoding `description_ok=True` (line 1205) or `bool(body_text)` (line 1075) |

### Item 3: Work Model Resolution & Description Eligibility

- **Call Sites of `resolve_work_model`**:
  A global search identifies 10 active call sites:
  1. `ats_api_client.py:160` (Greenhouse): Passes `location`, `title`, `trusted_description=raw_content`. **Does NOT pass `description` or `description_ok`.**
  2. `ats_api_client.py:264` (Lever): Passes `workplace_type`, `location`, `title`, `trusted_description=combined_desc`. **Does NOT pass `description` or `description_ok`.**
  3. `ats_api_client.py:362` (Ashby): Passes `workplace_type`, `location`, `title`, `trusted_description=raw_desc`. **Does NOT pass `description` or `description_ok`.**
  4. `ats_api_client.py:465` (SmartRecruiters): Passes `workplace_type=sr_workplace`, `location`, `title`, `trusted_description=raw_desc`. **Does NOT pass `description` or `description_ok`.**
  5. `ats_api_client.py:560` (Workable): Passes `workplace_type`, `location`, `title`, `trusted_description=markdown`. **Does NOT pass `description` or `description_ok`.**
  6. `ats_api_client.py:665` (BambooHR): Passes `workplace_type`, `location`, `title`. **No description available.**
  7. `ats_api_client.py:745` (Recruitee): Passes `workplace_type`, `location`, `title`, `trusted_description=raw_desc`. **Does NOT pass `description` or `description_ok`.**
  8. `ats_page_enricher.py:238` (Workday CXS): Passes `location`, `title`, `trusted_description=cxs_raw_desc`. **Does NOT pass `description` or `description_ok`.**
  9. `ats_page_enricher.py:373` (JSON-LD Enricher): Passes `jsonld_location_type`, `location`, `title`, `trusted_description=raw_jsonld_desc`. **Does NOT pass `description` or `description_ok`.**
  10. `ats_page_enricher.py:539` (JazzHR Apply JSON-LD): Passes `jsonld_location_type`, `location`, `title`, `trusted_description=apply_raw_desc`. **Does NOT pass `description` or `description_ok`.**
  11. `nigerian_scrapers.py:1070` (HotNigerianJobs card): Passes `description=body_text`, `description_ok=bool(body_text)`.
  12. `nigerian_scrapers.py:1200` (HotNigerianJobs detail): Passes `description=body_text`, `description_ok=True`.
  13. `field_normalizer.py:475` (`normalize_work_model` wrapper):
      ```python
      cand_val = value if value is not None else (snippet if snippet else None)
      eff_desc_ok = description_ok or (description is not None and not value and not snippet)
      res = resolve_work_model(workplace_type=cand_val, ...)
      ```
      *Severe Finding*: If `value` is None, it passes `snippet` as `workplace_type` (Tier 1 API enum!), attributing snippet keywords to `api_enum`! Furthermore, line 474 contains an explicit unit-test bypass comment (`"treat description_ok=True for direct unit-test convenience"`).
- **Conflation of Display Quality with Extraction Eligibility**:
  In `work_model.py:212` and line 245, description scanning is strictly guarded:
  ```python
  if description and description_ok:
  ```
  `description_ok` is governed by `description_quality` (`field_normalizer.py:62-84`), which requires `len(text) >= 300`. An authentic 280-character posting from Greenhouse or Lever API stating *"We are hiring a Senior Engineer for our 100% remote team"* fails `description_quality`. As a result, `description_ok` is False, Tier 6 description scanning is skipped, and the job is marked `None` / unknown!

### Item 4: Salary & Compensation Contradictions

- **Fabricated Defaults in `JobSalary` (`src/project_files/models.py:227-232`)**:
  ```python
  class JobSalary(BaseModel):
      minimum: Optional[int] = None
      maximum: Optional[int] = None
      currency: Optional[str] = "USD"    # INVENTED DEFAULT!
      period: Optional[str] = "year"      # INVENTED DEFAULT!
  ```
  This directly violates the domain rule: *"Unknown currency stays unknown (never default to USD). Unknown pay period stays unknown (never default to annual)."* If a Nigerian posting of ₦200,000/month or a London posting of £65,000 is parsed with partial arguments, it defaults to USD and annual period.
- **Violation of ADR 0003 (Backend Owns Parsing)**:
  In `JobListing`, `salary` is typed as a union: `JobSalary | str | None = None`. Nigerian scrapers dump raw strings (`"N 150,000 - N 250,000 monthly"`) into `JobListing.salary`.
  Because the backend fails to parse this into numeric bounds, the frontend (`frontend/src/lib/sort.ts:10` and `frontend/src/lib/normalize.ts:54`) executes client-side regexes:
  ```typescript
  if (typeof job.salary === 'string') {
    const match = job.salary.replace(/,/g, '').match(/\d+/);
  ```
  This is a direct violation of ADR 0003.
- **Untapped Structured Compensation**:
  Ashby API returns structured compensation (`compensationTierSummary`), and JSON-LD exposes `baseSalary` (`MonetaryAmount`), but neither `ats_api_client.py` nor `ats_page_enricher.py` extracts them.

### Item 5: Descriptions & Cleaning Paths

- **Divergent HTML Stripping**:
  - `to_markdown` (`field_normalizer.py:103-235`) parses HTML via BeautifulSoup, decomposes `_NOISE_TAGS` (`nav`, `footer`, `script`, etc.), converts headers/lists to markdown, and strips `#LI-*` recruiter tags.
  - In `nigerian_scrapers.py:938`, a custom `_extract_hnj_body_markdown` strips `.adsbygoogle`, `ins`, and removes trailing "Click Here and Apply Online" strings via regex.
  - In `ats_page_enricher.py:585`:
    ```python
    description=description if desc_ok else None
    ```
    If `desc_ok` is False, the description is wiped to `None`, discarding text that could have provided valuable context or search indexability.

### Item 6: Identity Generation & Deduplication

- **Identity Schemes Across Providers**:
  - Supported ATS: `{provider}:{company_slug}:{job_id}` (e.g. `greenhouse:stripe:456789`).
  - Unsupported ATS & Generic Enricher: `{provider}:{sha256(url)[:16]}`.
  - Nigerian Scrapers: `{provider}:{sha256(apply_url)[:16]}`.
  - Snippet Fallbacks: `{provider}:{sha256(url)[:16]}`.
- **Vulnerabilities in URL Hashing**:
  - Hashing raw URLs without canonical query string stripping means tracking tags (`?utm_source=...`, `?gh_src=...`) produce different IDs for the exact same posting.
  - In `ats_page_enricher.py:565`, `url` (the incoming search URL) is hashed rather than `resolved_apply_url` (the canonical destination URL discovered on JazzHR or redirected pages).
- **Absence of Merge Logic**:
  `GlobalDeduplicator` (`src/project_files/search_pipeline.py:104-112`) implements only exact set membership:
  ```python
  new = [l for l in listings if l.id not in self._seen]
  self._seen.update(l.id for l in new)
  ```
  There is zero field-level merging. If a snippet result arrives first and an enriched API result arrives second for the same job, the second result is silently discarded, keeping the low-confidence snippet.

### Item 7: Freshness & Datetime Integrity

- **Misleading "Recently Posted" Label**:
  `src/project_files/models.py:136-137`:
  ```python
  if not self.posted_at:
      return "Recently posted"
  ```
  If a job has no posted date, it is falsely labeled "Recently posted" in `freshness_label`. A job posted 3 years ago without metadata appears as new.
- **Fallback to `updated_at`**:
  `src/project_files/ats_api_client.py:169` (Greenhouse):
  `raw_date = data.get("first_published") or data.get("created_at") or data.get("updated_at")`
  If a company edits a 6-month-old job description today, `updated_at` makes the job appear as posted today.
- **Deprecated `datetime.utcnow()`**:
  `models.py:138` uses `datetime.utcnow()`, emitting Python 3.12+ deprecation warnings and performing naive datetime arithmetic by stripping tzinfo (`posted_at.replace(tzinfo=None)`).

### Item 8: Error Handling & Provider Fault Isolation

- **Provider Fault Isolation is Resilient**:
  In `SearchOrchestrator.run` (`search_pipeline.py:524-589`), provider tasks run concurrently under `asyncio.wait`. Individual task exceptions are caught (`except Exception as exc: logger.warning(...)`) and telemetry is recorded (`SourceOutcome.FAILURE`). One failing provider or scraper does not abort the search for other providers.
- **Dead `ErrorEvent` in Orchestrator**:
  `SearchOrchestrator.run` claims in its docstring and type signature to yield `("error", ErrorEvent)`, but **never** yields `("error", ErrorEvent)` in its loop. An error event is only emitted at the top HTTP layer (`src/api/main.py:164`) if the entire orchestrator generator crashes.
- **Provider Status Opaqueness**:
  In `DoneEvent`, `providers_searched` and `providers_skipped` are recorded, but client consumers cannot distinguish whether a provider returned 0 results, failed due to network timeout, tripped a circuit breaker, or encountered an authentication error.

### Item 9: Orchestration, Caching & Budgets

- **Three Caching Tiers**:
  1. *In-Memory Whole-Search Cache* (`_cache: OrderedDict[str, CacheEntry]` in `search_pipeline.py:69`):
     Keyed by `api-v3-broad-search:{params}:{platforms}` SHA256 (24 chars). Capped at `in_memory_cache_max_entries` (100). TTL `cache_ttl_seconds` (300s).
  2. *Persistent SQLite Serper Cache* (`cache_store.py:42`):
     Keyed by `{query_str}:{page}:{days_back}:{country_code}` SHA256. TTL `serper_cache_ttl_hours` (12h).
  3. *Persistent SQLite Per-URL Cache* (`cache_store.py:60`):
     Keyed by exact `url`. Stores `JobListing` JSON. TTL `url_cache_ttl_hours` (24h).
- **Serper Daily Budget Enforcement**:
  Table `serper_daily_budget` tracks UTC date call counts. When count reaches `serper_daily_budget` (200), `check_and_increment_daily_budget` returns `(False, count)`, setting `stats.budget_exhausted = True` and preventing further outbound Serper calls.
- **Limitation**:
  `url_cache` caches `JobListing` serialized JSON for 24 hours without an ETag or conditional `If-Modified-Since` check. If a posting closes 1 hour after being fetched, Bottom Pot continues serving it as active for 23 hours.

### Item 10: Evaluation Harness & Pipeline Bypasses

- **`scripts/eval_work_model.py` Analysis**:
  - The evaluation script loads a pre-scraped `results.json` and compares against a labels CSV (`audit.csv`).
  - *Pipeline Bypass (Lines 96–105)*: It calls `resolve_work_model` with `trusted_description=job.get("description")` and **never passes `description` or `description_ok`**. It tests only `#LI-` tags, location, and title.
  - *Fallback Bypass (Line 103)*:
    ```python
    predicted = res.value if res.value is not None else job.get("work_model")
    ```
    If `resolve_work_model` returns `None`, it falls back to the pre-classified `work_model` value stored in the JSON file! It does not evaluate the resolver independently.
- **Golden Set State**:
  `audit.csv` at repo root contains 50+ real labeled examples. Several rows show historical misclassifications (e.g. Pinterest classified as `remote` when label is `hybrid`, Graphcore classified as `hybrid` when label is `in_person`).

### Item 11: Consumers & Frontend Filtering Semantics

- **Public SSE Allowlist Redaction (`src/api/allowlist.py`)**:
  Anonymous users receive allowlisted fields only. Operational fields (`work_model_source`, `work_model_evidence`, `extraction_confidence`, `data_source`, `scraped_at`) are stripped and restricted to authenticated admin sessions.
- **Ghost Jobs Under Frontend Work-Model Filters (`frontend/src/lib/filter.ts:61-67`)**:
  ```typescript
  if (workModel) {
    if (workModel === 'remote' && job.work_model !== 'remote') return false;
    if (workModel === 'hybrid' && job.work_model !== 'hybrid') return false;
    if (workModel === 'in_person' && job.work_model !== 'in_person') return false;
    if (workModel === 'not_specified' && job.work_model) return false;
  }
  ```
  *Severe Filter Bug*: If `job.work_model === "unknown"`, it fails the `'remote'`, `'hybrid'`, and `'in_person'` checks. When the user filters by `'not_specified'`, because `"unknown"` is a truthy string, `job.work_model` evaluates to true and it returns `false`! Consequently, **any job with `work_model === "unknown"` disappears completely from every filtered view.**
- **Legacy CLI Consumer (`main.py`)**:
  Directly instantiates `SerperSearcher` and `SearchParams`, outputting `RawSearchResults` to `outputs/json/` and `outputs/csv/`. It does not use `SearchOrchestrator` or `CanonicalJob`.

---

## 4. Confirmed vs. Suspected Bugs Ledger

| Bug ID | Status | File & Line Reference | Description | Evidence / Proof | Severity |
|---|---|---|---|---|---|
| **BUG-01** | **CONFIRMED** | `src/project_files/ats_page_enricher.py:457` | Runtime `NameError: name 'response' is not defined` when enriching Personio postings. | Code reads `raw_html = response.text`. The function parameters are `url, provider, search_title, snippet, query_used, client` and the fetch returned `status_code, page_content, _`. Variable `response` does not exist in scope. | **High** (Crashes Personio enrichment) |
| **BUG-02** | **CONFIRMED** | `src/project_files/models.py:227-232` | `JobSalary` hardcodes invalid default values `currency="USD"` and `period="year"`. | Direct inspection of class definition: `currency: Optional[str] = "USD"`, `period: Optional[str] = "year"`. Violates project domain rule "Never default to USD or annual". | **High** (Corrupts compensation data) |
| **BUG-03** | **CONFIRMED** | `frontend/src/lib/filter.ts:66` | Jobs with `work_model === "unknown"` become ghost jobs excluded from all filters including "not_specified". | Line 66 checks `if (workModel === 'not_specified' && job.work_model) return false;`. Because `"unknown"` is a truthy string, it is rejected by 'not_specified', and also rejected by 'remote', 'hybrid', 'in_person'. | **High** (UI data invisibility) |
| **BUG-04** | **CONFIRMED** | `src/project_files/models.py:136-137` | Jobs without a posting date are labeled "Recently posted". | `if not self.posted_at: return "Recently posted"`. Violates domain rule: "Do not label jobs without a posting date as recent." | **Medium** (Misleading freshness) |
| **BUG-05** | **CONFIRMED** | `src/project_files/ats_page_enricher.py:296, 327` | Circuit breaker and WAF fallbacks hardcode `is_remote=False` instead of `None`. | Lines 296 and 327 instantiate fallback `JobListing` with `is_remote=False` even when `work_model=None`. Falsely classifies unknown jobs as non-remote. | **Medium** (False negative remote classification) |
| **BUG-06** | **CONFIRMED** | `src/project_files/field_normalizer.py:471, 476` | Search snippet is passed as `workplace_type` (Tier 1 API enum) when structured workplace is None. | `cand_val = value if value is not None else (snippet if snippet else None)` followed by `resolve_work_model(workplace_type=cand_val)`. Attributes search snippet text to API enum source. | **Medium** (Provenance corruption) |
| **BUG-07** | **CONFIRMED** | `src/project_files/models.py:138` | Deprecated `datetime.utcnow()` call producing runtime deprecation warnings and naive arithmetic. | Emits 17 pytest warnings: `DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version.` | **Low** (Deprecation technical debt) |
| **BUG-08** | **CONFIRMED** | `src/project_files/ats_api_client.py:169` | Greenhouse falls back to `updated_at` when `first_published` is missing. | `raw_date = data.get("first_published") or data.get("created_at") or data.get("updated_at")`. Causes old jobs with minor description edits to appear as new. | **Medium** (Freshness inaccuracy) |
| **BUG-09** | **CONFIRMED** | `src/project_files/search_pipeline.py:108-111` | Deduplication drops enriched secondary results in favor of earlier snippet results without merging. | `GlobalDeduplicator` does `if l.id not in self._seen`. Zero field-level merge logic exists. | **Medium** (Loss of enriched data) |
| **BUG-10** | **SUSPECTED** | `src/project_files/ats_api_client.py:330` | Ashby client fetches entire company job board on every single job URL lookup. | Ashby client calls `/posting-api/job-board/{company_slug}`. For companies with 500+ postings, fetching and parsing the entire board per Serper hit may create severe memory and latency spikes. Needs benchmarking under load. | **Performance** |
| **BUG-11** | **SUSPECTED** | `src/project_files/cache_store.py:173-186` | SQLite URL cache returns stale job postings without availability re-verification for 24 hours. | Listings are cached for 24 hours with no active requisition status check. Needs verification against live 404 rates. | **Data Freshness** |

---

## 5. Architectural Decisions Needing Approval (Draft ADRs)

Four foundational Architectural Decision Records have been authored in `docs/adr/` using `0000-template.md`:

1. **[`ADR 0024: Canonical Job Contract and Compatibility Adapter Architecture`](file:///c:/Users/Richmond/Desktop/Codebase/bottom-pot-v1/docs/adr/0024-canonical-job-contract-and-compatibility-adapter.md)**
   - *Core Decision*: Make `CanonicalJob` the single authoritative internal domain entity with explicit provenance, validations, and confidence. Maintain `JobListing` as an external serialization compatibility adapter to preserve FastAPI SSE streams, CLI exports, and frontend contracts without breaking changes.
2. **[`ADR 0025: Shared Extraction and Normalization Pipeline`](file:///c:/Users/Richmond/Desktop/Codebase/bottom-pot-v1/docs/adr/0025-shared-extraction-and-normalization-pipeline.md)**
   - *Core Decision*: Decouple data acquisition (raw network fetching into immutable `RawJobPosting` envelopes) from extraction and normalization (`JobExtractionService`). Stop provider adapters from reimplementing date parsing, salary regexes, work-model mapping, or HTML cleaning.
3. **[`ADR 0026: Work-Model Display Quality vs Extraction Eligibility`](file:///c:/Users/Richmond/Desktop/Codebase/bottom-pot-v1/docs/adr/0026-work-model-display-quality-vs-extraction-eligibility.md)**
   - *Core Decision*: Decouple description *display quality* (`description_ok`, length >= 300, structural check for UI rendering) from *extraction eligibility* (authoritative text from ATS APIs/JSON-LD is always eligible for work-model scanning). Standardize explicit `"unknown"` work model and update frontend filters to eliminate ghost jobs.
4. **[`ADR 0027: Structured Compensation and Salary Invariance`](file:///c:/Users/Richmond/Desktop/Codebase/bottom-pot-v1/docs/adr/0027-structured-compensation-and-salary-invariance.md)**
   - *Core Decision*: Refactor `JobSalary` to remove invalid defaults (`currency="USD"` and `period="year"`). Require backend extraction of structured compensation (JSON-LD `baseSalary`, Ashby compensation, Nigerian salary text) into typed numeric bounds with ISO currency codes, enforcing ADR 0003.

---

## 6. Open Questions Requiring Human Decision

Before Step 02 begins, the following 4 decisions require confirmation:

1. **Explicit `"unknown"` Work Model vs `null`**:
   - *Question*: Should the public API and frontend model explicitly expose `work_model: "unknown"` when no arrangement is disclosed, or should it remain `null` on the wire while the internal canonical model records `unknown`?
   - *Recommendation*: Expose `work_model: "unknown"` (or preserve null on public SSE wire via adapter if client backwards-compatibility requires it). Updating `frontend/src/lib/filter.ts` to treat `"unknown"` and `null` identically guarantees zero ghost jobs under either choice.
2. **Canonical Deduplication Precedence (Merge Policy)**:
   - *Question*: When multiple results for the same job arrive (e.g. initial Serper snippet followed by an enriched ATS API result, or multiple aggregators linking to the same ATS URL), should the pipeline merge fields by highest confidence tier (API > Scrape > Snippet) rather than first-seen wins?
   - *Recommendation*: Yes. Adopt a conservative field-level merge policy: structured fields from higher-confidence sources overwrite lower-confidence/missing fields, while preserving all evidence entries in `field_evidence`.
3. **BambooHR Description Handling**:
   - *Question*: BambooHR's public career API (`/careers/list`) provides only title, location, and department, but no job description. Should BambooHR listings remain description-less (as they are today), or should the orchestrator optionally fetch the individual HTML career detail page (`/careers/{id}`) to acquire descriptions?
   - *Recommendation*: Keep BambooHR lightweight (no secondary page fetch) unless explicitly configured, preserving API budget and concurrency limits.
4. **Retirement of `SearchResponse`**:
   - *Question*: Should `SearchResponse` in `src/project_files/models.py:155` be deleted as dead code, or retained for potential future non-streaming batch endpoints?
   - *Recommendation*: Delete or mark `@deprecated` with clear docstring, avoiding developer confusion.

---

## 7. Refined Implementation Roadmap (Steps 02–13)

Based on the audit findings, the starting roadmap is refined into 12 concrete, self-contained steps. Each step will operate on its own isolated step branch (`step/NN-<slug>`), ship its own tests and real fixtures, and produce a dedicated step log in `docs/steps/`.

```
Step 01: Repo audit & implementation plan (THIS STEP - Complete)
   ↓
Step 02: Canonical job contract & JobListing compatibility adapter (ADR 0024)
   ↓
Step 03: Raw extraction envelope & shared extraction service (ADR 0025)
   ↓
Step 04: Work-model resolution & display quality vs extraction eligibility (ADR 0026)
   ↓
Step 05: Structured salary extraction & JobSalary invariance (ADR 0027)
   ↓
Step 06: Centralized idempotent description cleaning & Markdown normalization
   ↓
Step 07: Field-level provenance, confidence scoring & telemetry integration
   ↓
Step 08: Explicit extraction outcomes & bounded provider error isolation
   ↓
Step 09: URL normalization, job identity & conservative field-level deduplication
   ↓
Step 10: Freshness, timezone awareness & availability status verification
   ↓
Step 11: Comprehensive evaluation harness & golden dataset benchmarking
   ↓
Step 12: Search orchestration, streaming lifecycle & SQLite cache hardening
   ↓
Step 13: Public API contract alignment & frontend filter synchronization
```

---

### Step 02: Canonical Job Contract & Compatibility Adapter

- **Scope**:
  - Implement the authoritative `CanonicalJob` contract model in `src/project_files/canonical_models.py` with typed fields, `FieldEvidence`, `FieldValidation`, and `FieldConfidence`.
  - Implement bidirectional `CanonicalJobAdapter` translating between `CanonicalJob` and legacy `JobListing`.
  - Fix default timestamp instantiation in `RawSearchResults`.
  - Remove dead scaffolding `SearchResponse` (or deprecate it).
- **Files Likely Touched**:
  - `src/project_files/canonical_models.py` (new)
  - `src/project_files/models.py`
  - `src/project_files/adapters.py` (new)
  - `tests/test_canonical_models.py` (new)
  - `tests/test_contracts_and_observability.py`
- **Compatibility Risks**:
  - None. `JobListing` remains fully intact for all external callers and SSE serialization.
- **Verification Plan**:
  - Unit tests for all round-trip conversions between `CanonicalJob` and `JobListing`.
  - Run `scripts/verify.ps1` to confirm zero regression on existing endpoints.

---

### Step 03: Shared Extraction Service & Provider Migration (Batch 1: ATS APIs)

- **Scope**:
  - Define `RawJobPosting` acquisition envelope.
  - Create `JobExtractionService` to centralize field extraction from structured JSON payloads.
  - Migrate the 7 dedicated ATS API clients (`GreenhouseClient`, `LeverClient`, `AshbyClient`, `SmartRecruitersClient`, `WorkableClient`, `BambooHRClient`, `RecruiteeClient`) to return `RawJobPosting` and delegate canonicalization to `JobExtractionService`.
- **Files Likely Touched**:
  - `src/project_files/extraction_service.py` (new)
  - `src/project_files/ats_api_client.py`
  - `src/project_files/search_pipeline.py`
  - `tests/test_extraction_service.py` (new)
  - `tests/test_real_api_fixtures.py`
- **Compatibility Risks**:
  - Orchestrator must handle `CanonicalJob` internally while yielding adapted `JobListing` batches.
- **Verification Plan**:
  - Re-run all existing real API fixture tests against the new extraction service.
  - Confirm identical or strictly superior extraction rates across all 7 ATS platforms.

---

### Step 04: Work-Model Resolution & Decoupled Extraction Eligibility

- **Scope**:
  - Implement ADR 0026: decouple description display quality (`description_ok`) from extraction eligibility (`description_eligible_for_extraction`).
  - Update `resolve_work_model` call sites across all providers to pass authoritative descriptions for keyword scanning.
  - Remove the test bypass / snippet-as-enum cheat in `field_normalizer.py:471`.
  - Eliminate confirmed `is_remote=False` hardcoding on snippet fallbacks in `ats_page_enricher.py`.
- **Files Likely Touched**:
  - `src/project_files/work_model.py`
  - `src/project_files/field_normalizer.py`
  - `src/project_files/ats_page_enricher.py`
  - `tests/test_work_model.py`
  - `tests/test_field_normalizer.py`
- **Compatibility Risks**:
  - Unit tests that relied on the test bypass in `normalize_work_model` will be pinned to explicit test inputs.
- **Verification Plan**:
  - Test concise description (< 300 chars) with remote keywords to prove it now resolves to `remote`.
  - Test fallback snippet without signals to prove it resolves to `unknown` with `is_remote=None`.

---

### Step 05: Structured Salary Extraction & `JobSalary` Invariance

- **Scope**:
  - Implement ADR 0027: refactor `JobSalary` in `models.py` / `canonical_models.py` to remove `currency="USD"` and `period="year"` defaults.
  - Add structured JSON-LD `baseSalary` parser (`MonetaryAmount` min/max, currency, unitText).
  - Add Ashby API structured compensation parser (`compensationTierSummary`).
  - Centralize Nigerian salary text extraction (Naira amounts, monthly/annual periods) into structured numeric `JobSalary`.
- **Files Likely Touched**:
  - `src/project_files/models.py`
  - `src/project_files/canonical_models.py`
  - `src/project_files/salary_parser.py` (new)
  - `src/project_files/ats_api_client.py`
  - `src/project_files/ats_page_enricher.py`
  - `src/project_files/nigerian_scrapers.py`
  - `tests/test_salary_parser.py` (new)
- **Compatibility Risks**:
  - In `JobListing`, `salary` will now consistently contain structured `JobSalary` objects rather than unparsed strings, fulfilling ADR 0003.
- **Verification Plan**:
  - Test real fixtures containing Ashby compensation, JSON-LD `baseSalary`, and Nigerian Naira formats.
  - Verify missing currency/period remains `None`.

---

### Step 06: Idempotent Description Cleaning & Structure Preservation

- **Scope**:
  - Centralize HTML-to-Markdown conversion in `field_normalizer.py` / `description_cleaner.py`.
  - Merge the custom AdSense / apply button stripping from `nigerian_scrapers.py` into the shared cleaner.
  - Ensure cleaning is strictly idempotent (`clean(clean(text)) == clean(text)`).
  - Preserve lists, paragraphs, headers, and bullet points while removing boilerplate, cookie consent, and navigation artifacts.
- **Files Likely Touched**:
  - `src/project_files/field_normalizer.py`
  - `src/project_files/nigerian_scrapers.py`
  - `tests/test_description_extraction.py`
- **Compatibility Risks**:
  - Low. Cleans output formatting for display.
- **Verification Plan**:
  - Test raw HTML dumps from Greenhouse, Lever, Workable, and HotNigerianJobs to confirm clean markdown rendering and idempotency.

---

### Step 07: Field-Level Provenance & Confidence Scoring

- **Scope**:
  - Wire `FieldEvidence`, `FieldValidation`, and `FieldConfidence` into `JobExtractionService`.
  - Every extracted field records:
    - Source method (API, JSON-LD, DOM, Snippet).
    - Source URL and literal snippet evidence.
    - Validation status (`ACCEPTED`, `REJECTED`, `SUSPECT`).
    - Numeric confidence score.
  - Replace the heuristic scalar penalty in `JobListing._compute_confidence` with the aggregated canonical confidence.
- **Files Likely Touched**:
  - `src/project_files/canonical_models.py`
  - `src/project_files/extraction_service.py`
  - `src/project_files/models.py`
  - `tests/test_contracts_and_observability.py`
- **Compatibility Risks**:
  - Admin allowlist retains full provenance; anonymous stream allowlist remains redacted.
- **Verification Plan**:
  - Verify every field on an extracted `CanonicalJob` has an associated evidence entry.

---

### Step 08: Explicit Extraction Outcomes & Provider Resilience

- **Scope**:
  - Fix BUG-01 (Personio `NameError` in `ats_page_enricher.py:457`).
  - Implement explicit provider extraction outcomes (`SUCCESS`, `EMPTY_RESULTS`, `TIMEOUT`, `CIRCUIT_BROKEN`, `AUTH_ERROR`).
  - Wire `ErrorEvent` or enriched `DoneEvent` provider status breakdown into search orchestration so clients have visibility into provider health without leaking sensitive internals.
  - Standardize bounded retry and backoff behavior across all outbound HTTP requests.
- **Files Likely Touched**:
  - `src/project_files/ats_page_enricher.py`
  - `src/project_files/search_pipeline.py`
  - `src/project_files/models.py`
  - `src/project_files/http_resilience.py`
  - `tests/test_phase5_cost_and_robustness.py`
- **Compatibility Risks**:
  - Low. Improves error transparency and fixes crash bugs.
- **Verification Plan**:
  - Synthetic network fault tests simulating timeouts and WAF challenges.
  - Unit test verifying Personio pages parse without `NameError`.

---

### Step 09: Canonical URL Normalization & Conservative Deduplication

- **Scope**:
  - Implement canonical URL normalization (stripping tracking parameters, fragment identifiers, and trailing slashes) prior to hashing job IDs.
  - Fix BUG-09: replace the binary `seen_ids` set in `GlobalDeduplicator` with a conservative field-level merge engine.
  - When a duplicate job is encountered, higher-confidence source fields enrich lower-confidence/missing fields.
- **Files Likely Touched**:
  - `src/project_files/url_normalizer.py` (new)
  - `src/project_files/deduplicator.py` (or `search_pipeline.py`)
  - `tests/test_deduplicator.py`
- **Compatibility Risks**:
  - Identical jobs with tracking parameter variations will now correctly collapse into a single listing.
- **Verification Plan**:
  - Test duplicate URLs with different tracking query strings (`?utm_source=...`) to prove they produce the same canonical ID and merge cleanly.

---

### Step 10: Freshness, Timezone Integrity & Availability Status

- **Scope**:
  - Fix BUG-04: replace misleading `"Recently posted"` fallback with `"Date not listed"` when `posted_at` is missing.
  - Fix BUG-07: eliminate all deprecated `datetime.utcnow()` calls; enforce timezone-aware UTC datetimes throughout.
  - Fix BUG-08: eliminate Greenhouse `updated_at` fallback for posting date; keep `posted_at=None` if `first_published` is absent.
  - Add posting availability status (`ACTIVE`, `EXPIRED`, `UNKNOWN`) to distinguish live jobs from stale cache records.
- **Files Likely Touched**:
  - `src/project_files/models.py`
  - `src/project_files/canonical_models.py`
  - `src/project_files/field_normalizer.py`
  - `src/project_files/ats_api_client.py`
  - `tests/test_field_normalizer.py`
- **Compatibility Risks**:
  - Jobs without posting dates will display `"Date not listed"` rather than `"Recently posted"`.
- **Verification Plan**:
  - Unit tests for date formatting and timezone awareness. Zero pytest deprecation warnings.

---

### Step 11: Comprehensive Evaluation Harness & Golden Benchmarking

- **Scope**:
  - Overhaul `scripts/eval_work_model.py` into a comprehensive pipeline evaluation harness (`scripts/evaluate_pipeline.py`).
  - Remove resolver bypasses (passing full descriptions, removing fallback to pre-classified values).
  - Expand golden dataset (`audit.csv`) with verified real-world test cases across all supported ATS platforms and Nigerian boards.
  - Measure field-level precision, recall, unknown rate, and false-positive rate.
- **Files Likely Touched**:
  - `scripts/evaluate_pipeline.py` (new)
  - `scripts/eval_work_model.py` (deprecated/updated)
  - `audit.csv`
  - `tests/test_evaluation_harness.py` (new)
- **Compatibility Risks**:
  - None (developer tooling and benchmarking).
- **Verification Plan**:
  - Run full benchmark evaluation report against golden test cases; confirm 0 false positives for remote/hybrid classifications.

---

### Step 12: Search Orchestration & Persistent Cache Hardening

- **Scope**:
  - Refactor `SearchOrchestrator` to stream canonical batches through `CanonicalJobAdapter`.
  - Upgrade SQLite cache (`data/cache.sqlite`) schema to support versioned canonical records.
  - Implement cache invalidation and conditional revalidation for expired job pages.
  - Hardened partial-result streaming and budget ceiling guards.
- **Files Likely Touched**:
  - `src/project_files/search_pipeline.py`
  - `src/project_files/cache_store.py`
  - `tests/test_phase5_cost_and_robustness.py`
- **Compatibility Risks**:
  - SQLite schema upgrade must gracefully migrate existing cache records.
- **Verification Plan**:
  - Integration test verifying SSE streaming under cache hits, cache misses, and budget exhaustion.

---

### Step 13: Public API Alignment & Frontend Filter Synchronization

- **Scope**:
  - Fix BUG-03: update `frontend/src/lib/filter.ts` so `"unknown"` work models are treated as `"not_specified"`, eliminating ghost jobs.
  - Harmonize frontend TypeScript definitions (`frontend/src/types.ts`) with the canonical contract.
  - Ensure frontend display formatters consume pre-parsed numeric compensation from backend `JobSalary`.
- **Files Likely Touched**:
  - `frontend/src/lib/filter.ts`
  - `frontend/src/lib/normalize.ts`
  - `frontend/src/types.ts`
  - `frontend/src/lib/__tests__/filter.test.ts`
  - `frontend/src/lib/__tests__/normalize.test.ts`
- **Compatibility Risks**:
  - Low. Frontend filter logic becomes more permissive and honest.
- **Verification Plan**:
  - Frontend vitest tests: verify jobs with `work_model: "unknown"` display properly and filter correctly under all toggles.
  - Playwright E2E browser tests across all viewports.

---

## 8. Stop Condition Compliance

Per user instructions and the Build Protocol:
- Investigation, audit analysis, and implementation planning are complete.
- Draft ADRs have been authored in `docs/adr/`.
- No application code, production tests, or configuration files were modified.
- **Execution stops here.** The plan is presented for review and approval prior to opening the Step 02 branch.
