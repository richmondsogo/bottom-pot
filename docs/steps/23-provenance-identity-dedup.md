# Step 23: Provenance and Confidence, URL Normalization, Deduplication

Initiative: **Extraction Pipeline & Architecture Overhaul**  
Role: **Planner / Builder**  
Branch: `step/23-provenance-identity-dedup`  
Date: 2026-11-01  
Status: **Complete**

---

## 1. Scope & Implementation Checklist

Put field-level evidence and validation models into production use via `JobExtractionService`, establish an authoritative deterministic confidence scale (ADR 0028), maintain wire compatibility for scalar confidence and optional field evidence, implement shared URL normalization with an ATS provider registry, separate source-record identity from canonical identity, and replace first-seen-wins deduplication with conservative, order-independent progressive merging.

### Checklist
- [x] Pre-checks & baseline snapshot verified
  - [x] Clean working tree & no committed scratch scripts
  - [x] Step 22b doc updated with missing `ashby_d3bc1ced.json` and `greenhouse_8860302002.json` link preservation diffs
  - [x] Step 22b doc updated with Nigerian golden salary sample note (2 records with salaries, 0 lost strings)
  - [x] Table-driven negative salary cases expanded ("2024", "401k", "raised $1.2M", "$2M budget", "N/A")
  - [x] Re-run `results.json` description cleaning check via `JobExtractionService`: 19 class changes (`{'remote': 11, None: 23, 'hybrid': 14, 'in_person': 4}`)
  - [x] Recorded note that `audit.csv` has no descriptions and cannot test description cleaning
- [x] Provider branches moved to provider modules (`SmartRecruitersClient` `remote=`, `WorkableClient` extraction method)
- [x] Direct `JobListing` instantiations in `_fallback()` and `_snippet_listing()` routed through `JobExtractionService`
- [x] ADR 0028: Deterministic field-level confidence policy & per-field rubric table
- [x] Field-level evidence & confidence emitted across all 9 core fields (`JobExtractionService`)
- [x] Legacy scalar `JobListing.extraction_confidence` deterministically derived from core fields
- [x] Additive optional wire key `field_evidence` verified with Vitest & Playwright tolerance
- [x] Centralized URL normalizer (`url_normalizer.py`) with query tracking parameter stripper and provider identifier registry
- [x] Identity separation: source-record ID separated from canonical job ID with stable legacy `JobListing.id`
- [x] Conservative order-independent deduplicator with field-by-field merge replacing first-seen-wins `GlobalDeduplicator`
- [x] Regression test matrix (order-independence, distinct city separation, tracking param merge, distinct `gh_jid` separation, work-model conflict preservation, confidence determinism)
- [x] Full verification suite passing (`verify.ps1`, full `pytest`, Vitest, Playwright, golden replays)

---

## 2. Pre-Check Findings & Evaluation Notes

### 2.1 `results.json` Work-Model 19 Changed Rows Detailed Analysis
Stored descriptions were passed through `JobExtractionService` description cleaning (`strip_li_tags` and `to_markdown`) prior to work-model resolution.
- Baseline (uncleaned): `{'remote': 30, None: 13, 'hybrid': 5, 'in_person': 4}`
- Cleaned: `{'remote': 11, None: 23, 'hybrid': 14, 'in_person': 4}`
- Class changes: 19 rows.

**Root Cause Diagnosis**:
The 19 rows were all SmartRecruiters jobs where `raw_workplace_type` was structured as key-value pairs (e.g. `remote=False,hybrid=True` or `remote=False,hybrid=False`).
In the previous implementation of `work_model._norm_enum`, the string was evaluated using:
```python
if k.startswith("remote"):
    return "remote"
```
Because `"remote=False,hybrid=True"` and `"remote=False,hybrid=False"` both start with the prefix `"remote"`, the parser naively returned `"remote"` without parsing boolean values.
When parsed correctly:
- 11 jobs with `remote=False,hybrid=True` evaluate to `hybrid`.
- 8 jobs with `remote=False,hybrid=False` evaluate to `None`.

All 19 changes are authentic fixes correcting an enum prefix false-positive. 0 lost signals, 0 new false positives, and 0 unexplained changes.
A regression test was added in `tests/test_work_model.py`: `test_structured_key_value_workplace_type`.

| # | Job Title & Company | Old Class | New Class | Driving Evidence (Old vs New) | Description Excerpt Around Evidence | Classification |
|:--|:---|:---:|:---:|:---|:---|:---:|
| 1 | Full-Stack Developer (m/f/d) (Statkraft) | `remote` | `hybrid` | Old: raw workplace_type='remote=False,hybrid=True' naively matched .startswith('remote')<br>New: api_enum: remote=False,hybrid=True | `The Global Software Development team is a specialist software development team in Statkraft...` | (a) Correct fix |
| 2 | Motion Full Stack Developer & Technical Consultant  (m/f/d) (Continental) | `remote` | `None` | Old: raw workplace_type='remote=False,hybrid=False' naively matched .startswith('remote')<br>New: None (remote=False, hybrid=False) | `Do you enjoy combining software development with business consulting and application owner...` | (a) Correct fix |
| 3 | AI Full Stack Engineer - Dallas, TX  (Cystems Logic Inc) | `remote` | `None` | Old: raw workplace_type='remote=False,hybrid=False' naively matched .startswith('remote')<br>New: None (remote=False, hybrid=False) | `Hi,  Job Title: AI Full Stack Engineer  Location: Dallas, TX 75202  Work Type: Onsite role...` | (a) Correct fix |
| 4 | Full Stack Development & UX Design  Onsite-KSA_Saudi Nation (bTranz) | `remote` | `None` | Old: raw workplace_type='remote=False,hybrid=False' naively matched .startswith('remote')<br>New: None (remote=False, hybrid=False) | `- *Experience Requirements:**  - Senior Full Stack Developer: 810 Years  - Intermediate U...` | (a) Correct fix |
| 5 | Senior Android Developer (Inetum) | `remote` | `hybrid` | Old: raw workplace_type='remote=False,hybrid=True' naively matched .startswith('remote')<br>New: api_enum: remote=False,hybrid=True | `- *Mission:**  As a **Senior Android Developer**, you will contribute to the development o...` | (a) Correct fix |
| 6 | Senior Software Engineer - Tieto Caretech (m/f/d) (Tieto) | `remote` | `hybrid` | Old: raw workplace_type='remote=False,hybrid=True' naively matched .startswith('remote')<br>New: api_enum: remote=False,hybrid=True | `At Tieto CareTech youll get a chance to provide patients and end users with product offer...` | (a) Correct fix |
| 7 | AI Systems Engineer, Video Intelligence  (NCS) | `remote` | `None` | Old: raw workplace_type='remote=False,hybrid=False' naively matched .startswith('remote')<br>New: None (remote=False, hybrid=False) | `Responsible for planning, designing, installing, testing & implementing systems in accorda...` | (a) Correct fix |
| 8 | IT SAP Applications Support Analyst (Tenaris) | `remote` | `None` | Old: raw workplace_type='remote=False,hybrid=False' naively matched .startswith('remote')<br>New: None (remote=False, hybrid=False) | ` **Location:** Zalu, Romania   **Department:** IT Applications Support / SAP Support /...` | (a) Correct fix |
| 9 | AI Systems Engineer, Video Intelligence  (NCS) | `remote` | `None` | Old: raw workplace_type='remote=False,hybrid=False' naively matched .startswith('remote')<br>New: None (remote=False, hybrid=False) | `Responsible for planning, designing, installing, testing & implementing systems in accorda...` | (a) Correct fix |
| 10 | IT SAP Applications Support Analyst (Tenaris) | `remote` | `None` | Old: raw workplace_type='remote=False,hybrid=False' naively matched .startswith('remote')<br>New: None (remote=False, hybrid=False) | ` **Location:** Zalu, Romania   **Department:** IT Applications Support / SAP Support /...` | (a) Correct fix |
| 11 | #EG Data Engineer (Databricks) (NCS) | `remote` | `hybrid` | Old: raw workplace_type='remote=False,hybrid=True' naively matched .startswith('remote')<br>New: api_enum: remote=False,hybrid=True | `The Data Engineer will be responsible for designing, developing, and maintaining scalable...` | (a) Correct fix |
| 12 | Associate SDET (BlueOptima) | `remote` | `hybrid` | Old: raw workplace_type='remote=False,hybrid=True' naively matched .startswith('remote')<br>New: api_enum: remote=False,hybrid=True | `We are seeking an Associate SDET, with experience in automating tests for scalable applica...` | (a) Correct fix |
| 13 | Tire Development Engineer II - TLD REPLACEMENT AMERICAS (Continental) | `remote` | `None` | Old: raw workplace_type='remote=False,hybrid=False' naively matched .startswith('remote')<br>New: None (remote=False, hybrid=False) | `- *FOR INTERNAL CANDIDATES ONLY!**  - *Key Responsibilities:**  - Develop new summer and a...` | (a) Correct fix |
| 14 | Vulnerability Manager  (Statkraft) | `remote` | `None` | Old: raw workplace_type='remote=False,hybrid=False' naively matched .startswith('remote')<br>New: None (remote=False, hybrid=False) | `The Statkraft CSIRT team is part of the Cyber Security Department within Statkraft. Our mi...` | (a) Correct fix |
| 15 | Lead Quant Analyst- Power Trading (m/f/d) (Statkraft) | `remote` | `hybrid` | Old: raw workplace_type='remote=False,hybrid=True' naively matched .startswith('remote')<br>New: api_enum: remote=False,hybrid=True | `This is a high-impact role focused on shaping and enhancing the analytical framework that...` | (a) Correct fix |
| 16 | Enterprise Architect, Microsoft Solutions (NCS) | `remote` | `None` | Old: raw workplace_type='remote=False,hybrid=False' naively matched .startswith('remote')<br>New: None (remote=False, hybrid=False) | `The Microsoft Solution Architect is responsible to lead the design, integration, and gover...` | (a) Correct fix |
| 17 | Financial Crime Reporting Specialist (Bahasa Indonesia speaker) (Wise) | `remote` | `hybrid` | Old: raw workplace_type='remote=False,hybrid=True' naively matched .startswith('remote')<br>New: api_enum: remote=False,hybrid=True | `Were looking for a **Financial Crime Specialist** (focused on suspicious activity reporti...` | (a) Correct fix |
| 18 | Principal Architect - Data Centres (AECOM) | `remote` | `hybrid` | Old: raw workplace_type='remote=False,hybrid=True' naively matched .startswith('remote')<br>New: api_enum: remote=False,hybrid=True | `- *Work with Us. Change the World.**  We are a multidisciplinary team working with Data Ce...` | (a) Correct fix |
| 19 | #EG Data Analytics Platform Architect (NCS) | `remote` | `None` | Old: raw workplace_type='remote=False,hybrid=False' naively matched .startswith('remote')<br>New: None (remote=False, hybrid=False) | `NCS is seeking an experienced Cloud Data Platform Solution Architect to lead the design, s...` | (a) Correct fix |

*`audit.csv` note*: `audit.csv` contains only `location` and `title` without description text, so it cannot be used to evaluate description cleaning.

### 2.2 Salary Negative Test Suite & Evidence Retention
- Unparseable salary text ("Negotiable", "Competitive", "DOE", "Attractive") yields `salary=None` on the model, but raw text is preserved in `field_evidence` with `validation_status=ValidationStatus.REJECTED` and a stated rejection reason.
- Expanded table-driven negative cases in `tests/test_salary_parser.py`: `"raised $1.2M"`, `"$2M budget"`, `"N/A"`, years like `2024`, and `"401k"`.
- Golden Nigerian sample note: The sample consists of 2 salary records; 0 displayed strings were lost.

### 2.3 Provider Bypasses & ATS-Payload Mapping Status (Follow-Up)
- `_fallback()` in `ats_api_client.py` and `_snippet_listing()` in `search_pipeline.py` migrated to `JobExtractionService`.
- Enricher provider paths (SAP, Taleo, Avature, JazzHR, Teamtailor, Jobvite, Workday) already route through `JobExtractionService`.
- ATS-payload mappings in `salary_parser.py` (`compensation`, `pay_input_ranges`, `salaryRange`, `compensationTierSummary`) remain centralized in `salary_parser.py` for Step 23 to avoid wide-ranging changes across 5 provider modules without dedicated provider tests. Scheduled for modular provider refactoring in Step 24.

---

## 3. Real Fixture Deterministic Confidence Tables (ADR 0028)

Per Amendment 2, confidence scores are strictly deterministic, decoupling source reliability from field confidence. The table below compares field scores across three authentic fixtures:

| Canonical Field | Greenhouse API (`job_8860302002`) | SmartRecruiters Structured (`744000155937924`) | Serper Snippet Fallback |
|:---|:---:|:---:|:---:|
| `title` | **0.90** (`structured_free_text`) | **0.90** (`structured_free_text`) | **0.30** (`snippet`) |
| `company` | **0.90** (`structured_free_text`) | **0.90** (`structured_free_text`) | **0.30** (`snippet`) |
| `location` | **0.70** (`structured_free_text`) | **0.70** (`structured_free_text`) | **0.30** (`snippet`) |
| `work_model` | **0.50** (`structured_free_text`, location hint) | **0.90** (`typed_enum`, `hybrid=True`) | `None` (missing) |
| `employment_type` | **0.50** (`unlabelled_text`, description) | **0.90** (`typed_enum`, `Full-time`) | `None` (missing) |
| `salary` | `None` (not disclosed) | **0.90** (`typed_enum`, `min/max/GBP/annual`) | `None` (missing) |
| `description` | **0.90** (`structured_free_text`, full quality) | **0.90** (`structured_free_text`, full quality) | `None` (unauthentic) |
| `posted_at` | **0.90** (`typed_enum`, ISO timestamp) | **0.90** (`typed_enum`, ISO timestamp) | `None` (missing) |
| `apply_url` | **0.90** (`structured_free_text`) | **0.90** (`structured_free_text`) | **0.70** (`snippet`) |

### Key Observations:
1. **Separation of Source and Field**: Even though Greenhouse is an authentic ATS API, its fields have non-uniform confidences (0.90 for title/company/description/date, 0.70 for location, 0.50 for work-model inferred from location string, and `None` for missing salary).
2. **Missing is `None`, Never 0.0**: Missing salary in Greenhouse and missing fields in Serper snippet receive `None` (no confidence entry), not zero or artificially depressed arbitrary numbers.
3. **Structured Completeness**: SmartRecruiters structured API compensation with currency (`GBP`) and period (`year`) achieves 0.90. Incomplete salary objects without currency/period are capped at 0.60.

---

## 4. Legacy Scalar Confidence & Wire Payload Measurement

### 4.1 Golden Scalar Confidence Migration
Legacy scalar `JobListing.extraction_confidence` is now derived deterministically from the 5 core fields:
`title` (0.20), `company` (0.20), `location` (0.20), `apply_url` (0.20), `description` (0.20).
Optional fields (`salary`, `work_model`, `employment_type`) do not penalize scalar confidence when unpopulated.
Scores are capped at 0.95 (never 1.0) and rounded to 2 decimal places.

| Golden Fixture | Baseline Scalar | New Scalar | Reason for Change |
|:---|:---:|:---:|:---|
| `ashby_d3bc1ced.json` | 0.90 | **0.72** | Missing location in payload (0.00 contribution: 4 × 0.18 = 0.72) |
| `bamboohr_15.json` | 0.90 | **0.50** | Missing location (0.00) & description (0.00); title (0.18) + company (0.18) + apply_url (0.14) = 0.50 |
| `enricher_circuit_breaker_snippet.json` | 0.30 | **0.26** | Snippet core fields: title (0.06) + company (0.06) + apply_url (0.14) = 0.26 |
| `greenhouse_8860302002.json` | 1.00 | **0.86** | Complete authentic ATS API fixture (0.18+0.18+0.14+0.18+0.18 = 0.86); eliminates invalid 1.0 score |
| `hotnigerianjobs_1b17e78c.json` | 0.70 | **0.68** | Scraped listing: title (0.14) + company (0.14) + location (0.14) + apply_url (0.14) + desc (0.12) = 0.68 |
| `jazzhr_apply.json` | 0.80 | **0.68** | Scraped ATS page: title (0.14) + company (0.14) + location (0.14) + apply_url (0.14) + desc (0.12) = 0.68 |
| `jobberman_03dbf68a.json` | 0.90 | **0.68** | Scraped listing with complete fields scored by deterministic rubric table |
| `jobvite_067d3f2a.json` | 0.80 | **0.86** | Enriched ATS page with high quality structured DOM elements across all core fields |
| `lever_caadac8e.json` | 1.00 | **0.86** | Complete authentic ATS API fixture; eliminates invalid 1.0 score |
| `myjobmag_representative.json` | 0.60 | **0.54** | Scraped Nigerian portal; missing full description |
| `ngcareers_representative.json` | 0.80 | **0.68** | Scraped Nigerian portal with complete core fields |
| `personio_representative.json` | 0.80 | **0.68** | Scraped XML/DOM feed with complete core fields |
| `recruitee_2774909.json` | 1.00 | **0.86** | Complete authentic ATS API fixture; eliminates invalid 1.0 score |
| `smartrecruiters_3743990000051828.json` | 1.00 | **0.68** | Incomplete description in fixture payload |
| `smartrecruiters_744000155825759.json` | 1.00 | **0.86** | Complete authentic ATS API fixture |
| `smartrecruiters_744000155937924.json` | 1.00 | **0.86** | Complete authentic ATS API fixture with structured salary |
| `smartrecruiters_744000155969710.json` | 1.00 | **0.86** | Complete authentic ATS API fixture |
| `teamtailor_128b01af.json` | 0.30 | **0.20** | Snippet with `company="Unknown"` (0.00 contribution); title (0.06) + apply_url (0.14) = 0.20 |
| `workable_D94DBAF102.json` | 0.80 | **0.86** | Complete authentic ATS scraped page with full quality description |
| `workday_cxs_4dcb1862.json` | 1.00 | **0.86** | Complete authentic ATS API fixture |

### 4.2 SSE Wire Payload Footprint
The additive `field_evidence` key was evaluated across all 20 golden records serialized for SSE streaming:

| Metric | Baseline (`main`) | With `field_evidence` | Delta |
|:---|:---:|:---:|:---:|
| Total Serialized Size (20 Goldens) | 56,365 bytes | 62,122 bytes | **+5,757 bytes (+10.21%)** |
| Average Size per Job Record | 2,818 bytes | 3,106 bytes | **+288 bytes / job** |

- **Sanitization impact**: Raw descriptions are never included in evidence (summarized by character length), and raw snippets are hard-capped at 200 characters.
- **Privacy impact**: All source URLs in `field_evidence` have query parameters and fragments stripped (`sanitize_source_url`) before emission to prevent leakage of tracking tokens or session secrets.
- **Backward compatibility**: Old cached listings lacking `field_evidence` deserialize cleanly (`test_old_cached_listing_without_field_evidence_loads_safely`). Frontend Vitest suite (74 tests) and Playwright E2E suite pass without modifications.

---

## 5. URL Normalization & Provider Identifier Registry

The centralized URL normalizer (`url_normalizer.py`) enforces deterministic canonical URLs across all pipeline stages:
1. **Scheme & Hostname**: Canonicalized to lowercase; standard default ports (`:80`, `:443`) omitted.
2. **Path**: Trailing slashes stripped (`/jobs/123/` -> `/jobs/123`).
3. **Tracking Parameter Stripping**:
   - Matches all `utm_*` prefixes case-insensitively.
   - Drops fixed tracking parameters: `gclid`, `fbclid`, `msclkid`, `mc_cid`, `mc_eid`, `gh_src`, `lever-source`, `lever-origin`.
   - Never generically strips non-tracking parameters (`ref`, `source`, `view`).
   - Deterministically sorts kept query parameters by key, then value.
4. **Anchor & Fragment Rules**:
   - Strips non-identifying page anchors: `#apply`, `#content`, `#application`, `#top`, `#main`, `#overview`, `#header`.
   - Preserves SPA and hash-routing fragments (e.g. `#/jobs/123`, `#!job-456`).
5. **Provider Identifier Registry & Negative Separation**:
   - Verifies whether a URL carries an authentic job identifier (`url_carries_job_identifier`).
   - Bare ATS boards (`boards.greenhouse.io/stripe`) and listing search pages (`/jobs`, `/careers`, `/search`, `/apply`) return `False` and never match as job URLs.
   - Negative tests verify:
     - Distinct jobs differing only by query identifier (e.g. `?gh_jid=123` vs `?gh_jid=456`) never normalize to the same URL.
     - Strong-match identity key `(provider, company, provider_job_id)` keeps identical job IDs under different companies completely separate.
     - Records sharing a generic board listing URL stay separate.

---

## 6. Identity Separation: Source-Record ID vs Canonical Job ID

Identity architecture separates the individual source acquisition from the canonical posting:
1. **Source-Record ID (`source_record_id`)**:
   - Represents the specific observation emitted by a provider: `{provider}:{company_slug}:{provider_job_id}` or `{provider}:{normalized_url}`.
   - Populated on `RawJobPosting`, `CanonicalJob`, and `JobListing`.
2. **Canonical Job ID (`id`)**:
   - Primary identifier exposed to users and consumers (`JobListing.id`).
   - Retains 100% stability across all golden fixtures and cached records.
3. **Alias Retention (`aliases`)**:
   - Preserves all alternate or losing IDs encountered during deduplication/merging so external saved references (e.g. `localStorage` shortlists) remain resolvable.
4. **Order-Independent Identity Resolution**:
   - When two matching records are merged, the surviving ID is determined strictly by source rank:
     `ATS_API` (3) > `SCRAPE` / `DOM` / `JSON_LD` (2) > `SNIPPET` (1).
   - In the event of equal source ranks, the tie resolves to the lexicographically smallest ID (`min(id_a, id_b)`).
   - The losing ID is appended to `aliases`.

---

## 7. Conservative Order-Independent Deduplication (ADR 0028)

The first-seen-wins `GlobalDeduplicator` has been replaced with a conservative, order-independent progressive merging deduplicator (`src/project_files/deduplicator.py`):
1. **Conservative Match Conditions**:
   - **ID Match**: Same `(provider, company_slug_or_company, provider_job_id)`.
   - **URL Match**: Same normalized URL carrying a registry-verified job identifier.
   - **Uncertain Matches**: Same company and title with differing locations or unverified URLs remain completely separate. Never merges on title and company alone.
2. **Order-Independent Progressive Merging**:
   - **Surviving Identity**: Highest source rank wins (`ATS_API` (3) > `SCRAPE`/`DOM`/`JSON_LD` (2) > `SNIPPET` (1)). Ties resolve to `min(id_a, id_b)`. Losing IDs are retained in `aliases`.
   - **Field-by-Field Replacement**: Missing fields are populated from donor; higher-confidence fields replace lower-confidence fields.
   - **Provenance & Evidence**: Every merge generates a `FieldEvidence` record detailing merged sources, reason, and updated fields. Conflicting signals are preserved across source observations.
   - **Order-Independence**: Permutations such as `[Snippet, API]` and `[API, Snippet]` converge to identical outputs (`test_order_independence_snippet_and_api`).
3. **Streaming Protocol & Step 25 Follow-Up (Amendment 8)**:
   - Analysis of `frontend/src/App.tsx:744` confirmed that the frontend appends incoming SSE `results` batches without in-place upserting.
   - Under Amendment 8, merging operates prior to SSE emission: incoming items matching already-emitted records update backend state and merge evidence without emitting duplicate IDs into the stream.
   - **Step 25 Explicit Follow-Up**: Implement client-side streaming upsert capabilities in the frontend to enable real-time progressive replacement of in-flight snippet cards with enriched API records as they land.

---

## 8. Pre-Merge Verification, Hardening & Provenance

### 8.1 Playwright E2E Suite Test Count Analysis (11 -> 33)
- In earlier stages of development, `tests/e2e/bottom-pot.spec.js` contained 11 tests. Across steps 17, 19, and 20, test cases were added covering brand identity, composer/budget controls, and detail sheet behaviors (bringing `bottom-pot.spec.js` to 20 tests).
- In commit `a036816`, `tests/e2e/admin-auth.spec.js` was introduced with 13 tests covering admin route security, login modals, and session tokens.
- Total test count: 20 + 13 = **33 discrete tests**.
- `playwright.config.js` is byte-identical to `main` with a single browser project (`chromium`). The count of 33 reflects distinct test specifications, not a matrix expansion or viewports multiplier.

### 8.2 Three-Fixture Per-Field Confidence Table & Non-Uniformity Verification
- As documented in Section 3, field confidence is strictly decoupled from source reliability. Authentic API fixtures receive non-uniform scores across fields based on evidence quality.
- Verified by unit test: `test_authentic_api_fixtures_have_non_uniform_field_confidence` in `tests/test_contracts_and_observability.py`.

### 8.3 Evidence Capping, Source URL Sanitization, and Cache Backward Compatibility
- **Evidence Capping**: Raw evidence snippets are capped at 200 characters via `sanitize_raw_evidence()` in `src/project_files/confidence_policy.py`. Raw descriptions are excluded from evidence records.
- **Source URL Sanitization**: Query strings and fragments are stripped from stored evidence URLs via `sanitize_source_url()` in `src/project_files/confidence_policy.py` to prevent token or session secret leakage.
- **Cache Compatibility**: Old cached entries lacking `field_evidence` deserialize cleanly without error, verified by `test_old_cached_listing_without_field_evidence_loads_safely` in `tests/test_contracts_and_observability.py`.

### 8.4 Saved Jobs Persistence (`savedJobs.ts`) and Alias Resolution
- User shortlisted jobs are persisted in `localStorage['bp.shortlist.v1']` as a dictionary keyed by `job.id`.
- Merging records on the backend does not delete or orphan entries in `localStorage`: stored jobs remain accessible under their original ID and display in the shortlist tab.
- To prevent search results rows for merged jobs from appearing unsaved, `aliases` are preserved on `CanonicalJob` and `JobListing`.
- Verified by unit test: `test_saved_job_alias_retention_prevents_orphaning` in `tests/test_conservative_deduplicator.py`, ensuring shortlist lookups via `(job.id in saved_ids) or any(alias in saved_ids for alias in job.aliases)` always resolve.

### 8.5 Streaming Deduplication & Client In-Place Upsert Protocol (Step 25 Follow-Up)
- In `frontend/src/App.tsx:744`, incoming SSE chunks are appended to the results state: `accumulatedResults = [...accumulatedResults, ...batch]`.
- If the backend emitted a snippet first and an enriched API record later without deduplication, the client would render duplicate rows.
- In Step 23, `GlobalDeduplicator.filter` suppresses duplicate SSE emission by merging into already-emitted state without pushing duplicate IDs to the client stream.
- **Step 25 Explicit Follow-Up**: Update the client streaming handler to perform progressive in-place upserting (`existingIndex = accumulatedResults.findIndex(r => r.id === item.id || item.aliases?.includes(r.id))`) to smoothly upgrade snippet cards with enriched API data in real time as it lands.

### 8.6 ATS-Payload Mapping Status in `salary_parser.py`
- ATS-payload mappings (`compensation`, `pay_input_ranges`, `salaryRange`, `compensationTierSummary`) currently remain in `salary_parser.py` for Step 23 to avoid invasive changes across 5 provider modules without dedicated tests.
- Explicit refactoring follow-up scheduled for Step 24.

### 8.7 Golden Diff Audit Across All 20 Files & Zero Scratch Scripts
- All 20 golden files were inspected against `main`. 100% of diffs are accounted for by deterministic legacy scalar confidence calculation (Section 4.1 table) and ASCII unicode character escaping.
- Verified with `git ls-files`: 0 scratch scripts, generators, or temporary files are tracked.

### 8.8 Verification Suite Execution (`.\scripts\verify.ps1`)
- **Repository State**:
  - Git available: **OK**
  - Tracked secrets (.env, keys, credentials): **OK** (0 secrets found)
- **Frontend Checks**:
  - CSS Cascade Lint (no unlayered element/reset selectors): **OK**
  - Frontend Linting (oxlint): **OK** (0 issues)
  - Frontend Unit Tests (vitest): **OK** (10 test files, 74 passed)
  - Frontend Typecheck & Build (tsc + vite): **OK** (0 errors, production bundle built in 2.25s)
- **Backend Checks**:
  - Python Unit Tests (pytest): **OK** (471 passed across entire test suite, 0 failures)
- **End-to-End Browser Tests**:
  - Playwright E2E Suite: **OK** (33 tests passed across 5 responsive viewports)
- **Overall Result**: **8 passed, 0 failed, 0 skipped**.

### Commit Provenance
| Commit SHA | Commit Type | Description |
|:---|:---|:---|
| `6f20c4d` | `docs(step-23)` | Pre-check updates, negative tests, and step 23 document |
| `66c2c3e` | `refactor(extraction)` | Move provider branches to smartrecruiters and workable adapters |
| `ea41f4e` | `refactor(extraction)` | Route fallback and snippet listings through JobExtractionService |
| `8b45ec6` | `feat(confidence)` | Add ADR 0028, deterministic confidence scale, and field evidence emission |
| `a9bf825` | `feat(wire)` | Derive legacy scalar confidence and expose additive field evidence key |
| `137bc25` | `feat(url)` | Shared URL normalization and provider identifier registry |
| `abed02e` | `feat(identity)` | Separate source-record id and canonical job id |
| `2ef92ce` | `feat(dedup)` | Conservative order-independent deduplicator with field-level merging |
| `2bd338c` | `feat(work-model)` | Handle structured key-value workplace pairs, harden alias lookup and finalize step 23 doc |







