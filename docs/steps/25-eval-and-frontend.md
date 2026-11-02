# Step 25: Work Model Evaluation Rebuild, Frontend Upsert & Alias Matching, Structured Salary Sorting, and Partial Results Notice

Initiative: **Evaluation Integrity & Frontend Polish**  
Role: **Planner / Builder**  
Branch: `step/25-eval-and-frontend`  
Base Commit: `29f94b79b29ddfcf4bf7e5033c4eb3544ff8bc8f` (Merged PR #28)  
Provenance Baseline Checkpoint: `67c9492`  
Date: 2026-11-02  
Status: **Merged to main**  
Pull Request: https://github.com/richmondsogo/bottom-pot/pull/29  
First Commit: `be5fe17`  
Last Commit: `33a1bcd`  
Merge Commit: `081e7701483e98f52c9fc3a32d34d3024ab1ab84`  

---

## 1. Scope & Implementation Checklist

This step resolves 5 core concerns across evaluation and the user experience:
1. Rebuilding `scripts/eval_work_model.py` to route strictly through the production extraction path (`JobExtractionService`), failing loudly on errors, ignoring pre-set values, breaking down metrics with sample sizes for records with and without stored descriptions, noting statistical power limits (7 remote, 15 hybrid), printing the full confusion matrix, and reporting truthful per-class / aggregate / per-provider metrics.
2. Hardening scraper resilience by enforcing per-host throttling (`resilience_manager.throttle`) and 429 backoff (`record_rate_limit`) on `BaseScraper.fetch_html`, preserving the 5.0s politeness gap.
3. Implementing backend upgrade-only emission for existing jobs (`rank_incoming > rank_existing`) while preventing `total_so_far` or `DoneEvent.total` count inflation.
4. Implementing a shared alias-matching helper (`matchesJobIdentity`) and frontend in-place batch upsert (`upsertJobBatch`) that preserves user scroll, selected job, expanded cards, and saved job states.
5. Implementing strict structured salary sorting scoped to the same currency and period, sorting unknown, mixed-group, and legacy strings last in stable order without currency conversion or throwing.
6. Emitting a plain neutral `"Results may be incomplete"` notice on `SearchSummaryBar` when `metrics.partial` is true, classifying `partial` for anonymous callers in `allowlist.py` while keeping `provider_outcomes` admin-only.
7. Adding Playwright E2E cases for the partial results notice and in-place upsert (including selection and bookmarking).

### Checklist
- [x] **Commit 0: Pre-checks & Scraper Throttling + 429 Backoff (Amendment 0)**
  - [x] Verified PR #27 was included in `main` (`796d3d8`).
  - [x] Addressed removed 5s scraper sleep: replaced with `resilience_manager.throttle(url)` across `BaseScraper.fetch_html`.
  - [x] Implemented host-level rate limit recording (`record_rate_limit`) and check (`is_host_rate_limited`, `HostRateLimitedError`) in `ResilienceManager` so 429 backoff applies per host with 5.0s default and exponential doubling up to 60.0s.
  - [x] Added unit tests in `tests/test_phase5_cost_and_robustness.py`.
- [x] **Commit 1: Rebuilt `eval_work_model.py` (Amendments 1 & 2)**
  - [x] Evaluates strictly through `JobExtractionService.extract(RawJobPosting(...))`; fails loudly if extraction fails or throws; strictly ignores pre-set `work_model` on input.
  - [x] Reconciled 49 valid labelled rows vs 54 labelled rows from earlier audits (5 non-job / unfindable rows identified).
  - [x] Reports metrics separately for rows with a stored description (N=0) and rows without a stored description (N=49), plainly stating that 0 labelled rows have stored descriptions.
  - [x] Reports full confusion matrix (Ground Truth by Predicted, including unknown).
  - [x] Reports per-class precision, recall, FP rate, unknown rate, macro/micro averages, and per-provider breakdown summing to N=49.
  - [x] Added test suite in `tests/test_eval_work_model.py` (4 passed).
- [x] **Commit 2: Backend Upgrade-Only Emission (Amendment 3)**
  - [x] Updated `GlobalDeduplicator.filter`: matching incoming records only emit if `rank_incoming > rank_existing`. Lower/equal rank records merge internally but do not emit.
  - [x] Updated `SearchOrchestrator.run`: upgraded emissions replace existing items in `all_collected` in-place, preventing inflation of `total_so_far` and `DoneEvent.total`.
  - [x] Added test suite in `tests/test_deduplicator.py` (6 passed).
- [x] **Commit 3: Shared Identity Helper & In-Place Batch Upsert (Amendments 3 & 4)**
  - [x] Created `frontend/src/lib/identity.ts` with `matchesJobIdentity` and `upsertJobBatch`.
  - [x] Updated `frontend/src/lib/savedJobs.ts`: alias-aware matching in `findSavedJobEntry`, `isJobSaved`, `getJobStage`, `toggleSavedJob`, `updateSavedJobStage`.
  - [x] Updated `frontend/src/App.tsx`, `ResultsCards.tsx`, `ResultsTable.tsx`, and `Workspace.tsx` to use shared alias helper and in-place upsert.
  - [x] Preserved UI state during upsert: scroll position, selected job, expanded card state, and saved bookmarks.
  - [x] `localStorage` key (`bp.shortlist.v1`) and format preserved without modification.
  - [x] Added unit tests in `frontend/src/lib/__tests__/upsertAndAliases.test.ts` (9 passed).
- [x] **Commit 4: Structured Salary Sorting (Amendment 5)**
  - [x] Extracted structured salary metadata: positive numeric minimum/maximum, currency, and period.
  - [x] Strictly compares amounts within the same currency and period group. No currency conversion.
  - [x] Legacy string salaries, unknown salaries, and mixed-group salaries sort last in stable order (both ascending and descending) without crashing.
  - [x] Added unit tests in `frontend/src/lib/__tests__/sort.test.ts` (4 passed) and updated `modules.test.ts`.
- [x] **Commit 5: Wire Classification & Plain Partial Results Notice (Amendment 6)**
  - [x] Added `partial: bool = False` to `DoneEvent` model and classified `"partial"` in `USER_DONE_FIELDS` (`src/api/allowlist.py`).
  - [x] Orchestrator computes `is_partial = any(s.partial for s in provider_outcomes.values())` and emits on `DoneEvent`.
  - [x] Verified `USER_DONE_FIELDS` and `ADMIN_DONE_FIELDS` remain strictly disjoint; `provider_outcomes` remains admin-only.
  - [x] Added anonymous serialization test in `tests/test_api_endpoints.py` showing no provider names or counts leak.
  - [x] Rendered neutral `"Results may be incomplete"` notice in `SearchSummaryBar.tsx` conforming to the square design system (`--radius: 0`).
  - [x] Added component test in `frontend/src/lib/__tests__/promptInput.test.tsx`.
- [x] **Commit 6: Playwright E2E Tests (Amendment 7)**
  - [x] Added Playwright test for `"Results may be incomplete"` notice on partial results.
  - [x] Added Playwright test for in-place upsert of snippet to enriched record asserting row count, metadata upgrade, detail selection, and bookmark saving.
  - [x] Ran Playwright test suite (35 passed).
- [x] **Commit 7: Full Verification & Provenance Documentation**
  - [x] Executed `.\scripts\verify.ps1` (8/8 passed).
  - [x] Documented commit provenance, audit findings, and metric deltas.

---

## 2. Work Model Evaluation & Audit Reconciliation

### 2.1 Reconciliation: 49 Valid Labelled Rows vs 54 Labelled Rows
Earlier audits in Step 21 cited 54 labelled rows in `audit.csv`. Total rows in `audit.csv` is 102.
Of the 54 rows with a non-empty `label_work_model` column:
- **49 rows** represent authentic job postings with evaluable ground truth labels (`in_person`: 27, `hybrid`: 15, `remote`: 7).
- **5 rows** are non-job / unfindable records excluded from classification evaluation:
  1. **Row 016 (successfactors)**: `https://jobs.sap.com/en/jobs/744000154631574/working-student-fmd-ai-engineering-data-science/`  
     *Title*: Working Student (f/m/d) – AI Engineering & Data Science | *Label*: `Not Found` (404/expired posting).
  2. **Row 023 (successfactors)**: `https://jobs.sap.com/en/job-areas/information-technology/`  
     *Title*: Information Technology | *Label*: `Not a job posting just a landing page` (category landing page).
  3. **Row 025 (teamtailor)**: `https://www.teamtailor.com/pt-br/integrations/vervoe/`  
     *Title*: Vervoe integration | *Label*: `Not a job but a product` (software integration page).
  4. **Row 029 (teamtailor)**: `https://www.teamtailor.com/pt/integrations/happyrmatch/`  
     *Title*: HappyrMatch integration | *Label*: `Not a job but a product` (software integration page).
  5. **Row 030 (teamtailor)**: `https://www.teamtailor.com/pt/integrations/`  
     *Title*: Título: Integrações | *Label*: `Not a job but a product listing page` (product directory page).

### 2.2 Split by Stored Description Presence
- **Rows with stored description ($N=0$)**: Plain Status: **No labelled rows in `audit.csv` contain a stored description.** `audit.csv` only records `url, provider, title, company, location`.
- **Rows without stored description ($N=49$)**: All 49 valid labelled records.

### 2.3 Full Confusion Matrix (Ground Truth Label vs Predicted Outcome)
Running strictly through `JobExtractionService.extract(RawJobPosting(...))` with authentic inputs:

| Ground Truth Label | Predicted `in_person` | Predicted `hybrid` | Predicted `remote` | Predicted `unknown` | Total Ground Truth |
|---|---|---|---|---|---|
| **`in_person`** | 0 | 0 | 0 | 27 | **27** |
| **`hybrid`** | 0 | 1 | 1 | 13 | **15** |
| **`remote`** | 0 | 0 | 2 | 5 | **7** |
| **Total Predicted** | **0** | **1** | **3** | **45** | **49** |

### 2.4 Per-Class Metrics Recomputed from Confusion Matrix

| Class | Ground Truth ($N$) | True Positives ($TP$) | False Positives ($FP$) | False Negatives ($FN$) | Precision | Recall | False-Positive Rate | Unknown Rate |
|---|---|---|---|---|---|---|---|---|
| `in_person` | 27 | 0 | 0 | 27 | 0.0% (0/0) | 0.0% (0/27) | 0.0% (0/22) | 100.0% (27/27) |
| `hybrid` | 15 | 1 | 0 | 14 | 100.0% (1/1) | 6.7% (1/15) | 0.0% (0/34) | 86.7% (13/15) |
| `remote` | 7 | 2 | 1 | 5 | 66.7% (2/3) | 28.6% (2/7) | 2.4% (1/42) | 71.4% (5/7) |

### 2.5 Summary Averages
- **Macro-Averaged Precision**: 83.3% (averaged across classes with predictions: 100% hybrid, 66.7% remote).
- **Macro-Averaged Recall**: 11.7% (average across all 3 classes: 0.0%, 6.7%, 28.6%).
- **Micro-Averaged Precision**: 75.0% (3 correct / 4 non-unknown predictions).
- **Micro-Averaged Recall**: 6.1% (3 correct / 49 total ground truth rows).
- **Overall Exact Accuracy**: 6.1% (3/49).
- **Overall Unknown Rate**: 91.8% (45/49).

> [!NOTE]
> **Adherence to ADR 0001 ("Unknown beats wrong")**: In the absence of job descriptions or authentic HTML bodies, `JobExtractionService` only has `title`, `company`, and `location`. In strict compliance with ADR 0001, physical locations without explicit workplace signals (e.g. "Atlanta, GA", "Lagos, Nigeria") resolve to `unknown` rather than guessing `in_person`. Consequently, 45 of 49 rows are safely classified as `unknown` with 0 false positives for `in_person`.

### 2.6 Formal Retraction of Earlier Preliminary Eval Figures & 5 False Positives
The earlier preliminary evaluation figures cited during initial drafting (85.71% accuracy/precision and 5 `in_person` false positives) were erroneous reporting artifacts resulting from a draft script bug that conflated the 5 excluded non-job rows ($54 - 49 = 5$) with false positives and reported overall accuracy as precision and recall. These figures are **formally retracted**.

The true production figures reflect evaluation through the production resolver on title and location only (zero labelled rows in `audit.csv` contain descriptions). In reality, **zero rows were predicted `in_person` by the production resolver** (all 27 `in_person` rows had absence of evidence and resolved to `unknown` under ADR 0001). There are zero `in_person` false positives in the production resolver.

The only non-unknown mismatch in the entire dataset is:
- **URL**: `https://www.pinterestcareers.com/jobs/?gh_jid=8247246`
  - *Title*: Staff Machine Learning Engineer, Content Visual AI
  - *Location*: San Francisco, CA, US; New York City, NY, US; Seattle, WA, US; Remote, US
  - *Label*: `hybrid`
  - *Predicted*: `remote` (source: `location`, evidence: `... Remote, US`)
  - *Classification*: **Ambiguous fixture**. The job listing location field literally contains `"Remote, US"` alongside three physical office locations, while the human labeler categorized it as hybrid. The resolver deterministically extracted `"Remote, US"` from the location field.

### 2.7 Complete Provider Inventory

| Provider | Labelled Rows ($N$) | Unlabelled Rows | Total Rows in `audit.csv` | Status / Testing Coverage |
|---|---|---|---|---|
| `smartrecruiters` | 20 | 0 | 20 | Evaluated in `audit.csv` |
| `greenhouse` | 10 | 0 | 10 | Evaluated in `audit.csv` |
| `successfactors` | 10 | 2 | 12 | Evaluated in `audit.csv` (2 excluded non-job rows) |
| `avature` | 4 | 0 | 4 | Evaluated in `audit.csv` |
| `teamtailor` | 3 | 3 | 6 | Evaluated in `audit.csv` (3 excluded product rows) |
| `personio` | 1 | 0 | 1 | Evaluated in `audit.csv` |
| `workday` | 1 | 19 | 20 | Evaluated in `audit.csv` |
| `workable` | 0 | 19 | 19 | Present in `audit.csv` but unlabelled; tested in `test_ats_client_outcomes.py` |
| `jobvite` | 0 | 6 | 6 | Present in `audit.csv` but unlabelled |
| `breezy` | 0 | 4 | 4 | Present in `audit.csv` but unlabelled |
| **TOTAL** | **49** | **53** | **102** | **Sum of Labelled N = 49 (CONFIRMED)** |

**Providers Absent from `audit.csv` Entirely**:
- `hotnigerianjobs`: 0 rows in `audit.csv`. Tested via real HTML fixtures in `tests/test_nigerian_scrapers.py` and `tests/test_phase5_cost_and_robustness.py`.
- `ngcareers`: 0 rows in `audit.csv`. Tested via dedicated scraper suites.
- `jobberman`: 0 rows in `audit.csv`. Tested via real HTML fixtures in `tests/test_nigerian_scrapers.py`.
- `myjobmag`: 0 rows in `audit.csv`. Tested via real HTML fixtures in `tests/test_nigerian_scrapers.py`.
- `lever`: 0 rows in `audit.csv`. Tested via live/cached API fixtures in `tests/test_ats_client_outcomes.py` and `tests/test_contracts_and_observability.py`.
- `ashby`: 0 rows in `audit.csv`. Tested via API fixtures in `tests/test_ats_client_outcomes.py`.

### 2.8 Known Limitation & External Descriptions Dataset Interface
- **Known Limitation**: Meaningful evaluation of precision and recall on real postings requires full job descriptions. Because `audit.csv` has $N=0$ descriptions, the production resolver strictly complies with ADR 0001 ("Unknown beats wrong") by assigning `unknown` to physical locations without explicit workplace indicators (e.g. "Atlanta, GA", "Lagos, Nigeria"), resulting in a 91.8% unknown rate on the title/location golden set.
- **Labelled Dataset with Descriptions**: The user will supply a labelled dataset containing full job descriptions (30–50 rows from `results.json`) as a CSV.
- **Zero-Code-Change Harness Compatibility**: The evaluation harness (`scripts/eval_work_model.py`) accepts this CSV directly with no code changes:
  ```powershell
  python scripts/eval_work_model.py path/to/labelled_descriptions.csv
  ```
  The harness expects the following columns in the CSV:
  - `url`: The job posting URL (used for deduplication and identification).
  - `label_work_model`: Ground truth label (must be one of `in_person`, `hybrid`, `remote`).
  - `title`: Job title string.
  - `company`: Company name string.
  - `location`: Location string.
  - `description` (or `raw_description`): Full text of the job description.
  - `provider`: (Optional) Name of the ATS or scraper provider (e.g., `greenhouse`, `jobberman`). Defaults to `"unknown"` if omitted.

---

## 3. Scraper Resilience, Throttle Intervals & 429 Backoff Confirmation

1. **Baseline per-host politeness interval for normal (non-429) requests**:
   - The baseline politeness interval between requests to Nigerian job board hosts (`settings.scraper_delay_seconds` in `src/config.py`) is set to **5.0 seconds** (raised from 1.5s), confirming it is $\ge$ the old fixed sleep of 5.0 seconds.
   - All scraper outbound requests execute through `resilience_manager.throttle(url)` across `BaseScraper.fetch_html`, bounded by `per_host_concurrency_limit = 3` and `global_concurrency_limit = 20`.
2. **Per-host 429 rate limit backoff**:
   - `resilience_manager.record_rate_limit(host, None)` sets an initial backoff delay of **5.0 seconds**, matching the old 5s politeness gap.
   - Consecutive 429s double the per-host backoff ($5.0\text{s} \to 10.0\text{s} \to 20.0\text{s} \to 40.0\text{s} \to 60.0\text{s}$ cap).
   - Explicit `Retry-After` headers (integer seconds or HTTP date) are honored up to a 60.0s cap.
   - Successful requests (`record_success(host)`) reset the backoff window.
   - Verified by unit tests in `tests/test_phase5_cost_and_robustness.py`: `test_per_host_429_backoff_and_reset` and `test_scraper_fetch_html_uses_throttle_and_backs_off_on_429` (subsequent calls to a rate-limited host within the backoff window fail fast via `HostRateLimitedError` without outbound network calls).

---

## 4. Test Modifications & Integrity Audit

No existing test assertions were weakened or removed. The only existing test files with modifications were:
1. `tests/test_api_endpoints.py`:
   - Line 481: `assert set(done_payload.keys()) == {"total", "incomplete"}` updated to `assert set(done_payload.keys()) == {"total", "incomplete", "partial"}` and added `assert done_payload["partial"] is False` to reflect the newly approved `"partial"` field on `DoneEvent`.
   - Lines 716 & 721: Added `"partial": False` to expected anonymous serialization dicts (`{"total": 0, "incomplete": True, "partial": False}`).
2. `frontend/src/lib/__tests__/modules.test.ts`:
   - Lines 38, 45, 52: Added `currency: 'USD', period: 'year'` to `salary` objects in the `jobs` test fixture to comply with Amendment 5's requirement that structured salaries specify currency and period.
   - Lines 108 & 111: Updated `mixedSalaryJobs` assertion from the old client-side regex sorting expectation (where `salary: null` sorted first on ascending) to the approved Amendment 5 rule where non-comparable / unstructured / null / legacy string salaries sort last in stable order for both ascending and descending (`['1', '2', '3', '4']`).
3. `tests/test_conservative_deduplicator.py`:
   - In `test_streaming_filter_merges_across_batches_without_duplicate_emission`, ordered the initial emission as `api` (rank 3) and the secondary arrival as `snippet` (rank 1). Under Step 25's upgrade-only emission rule, a higher-rank arrival is emitted as an in-place upgrade, whereas a lower-rank arrival is merged internally without SSE re-emission.
4. `tests/test_description_extraction.py`:
   - In golden replay tests (`test_workday_cxs_golden_replay`, `test_jobvite_golden_replay`, `test_jazzhr_golden_replay`, `test_teamtailor_golden_replay`), excluded time-dependent `freshness_label` before comparing against static golden JSON snapshots (which shift from '1 month ago' to '2 months ago' as calendar months elapse).

---

## 5. Playwright E2E Coverage & UI State Preservation

In `tests/e2e/bottom-pot.spec.js`:
- `displays neutral "Results may be incomplete" notice when search result is partial`: Validates that when `DoneEvent.partial` is `true`, the UI renders the caption notice with exact text `"Results may be incomplete"`.
- `in-place upsert updates snippet to enriched record preserving row count and selection`: Validates that:
  1. Row count does not inflate (exactly 1 row in table).
  2. Upgraded title and metadata replace the snippet in place (`Senior Python Engineer (Enriched)`).
  3. Clicking the row opens the detail sheet for the upgraded record (selection preserved).
  4. Saving the upgraded record successfully toggles the bookmark to saved.
- **Scroll Position & Unit Test Coverage Note**:
  - Scroll position preservation during in-place upsert (`upsertJobBatch`) is validated by unit tests in `frontend/src/lib/__tests__/upsertAndAliases.test.ts` (verifying exact array index preservation without table remounting). Scroll position is **not directly asserted in Playwright**.
  - Bookmark alias mapping and state preservation are covered both by the unit suite (9/9 passed) and the Playwright e2e upsert test.

---

## 6. Verification & Baseline Deltas

| Verification Suite | Pre-Step Baseline | Post-Step 25 | Delta |
|---|---|---|---|
| `verify.ps1` Checks | 8/8 Passed | **8/8 Passed** | 0 |
| Pytest Test Suite | 527 Passed | **537 Passed** | +10 passed |
| Vitest Test Suite | 75 Passed (10 files) | **89 Passed (12 files)** | +14 passed |
| Playwright E2E Suite | 33 Passed | **35 Passed** | +2 passed |

---

## 7. Commit Provenance Table

| Commit SHA | Commit Message | Scope / Component |
|---|---|---|
| `be5fe17` | `fix(resilience): apply per-host throttle and 429 backoff to scraper fetch_html` | `http_resilience.py`, `nigerian_scrapers.py`, `test_phase5_cost_and_robustness.py` |
| `57f6ed0` | `feat(eval): rebuild eval_work_model with production path, per-provider breakdown, and sample sizes` | `scripts/eval_work_model.py`, `tests/test_eval_work_model.py` |
| `a23d694` | `feat(dedup): backend upgrade-only emission for existing jobs without count inflation` | `src/project_files/deduplicator.py`, `src/project_files/search_pipeline.py`, `tests/test_deduplicator.py` |
| `8edceab` | `feat(frontend): alias-matching helper and in-place upsert preserving UI state` | `frontend/src/lib/identity.ts`, `savedJobs.ts`, `App.tsx`, `ResultsCards.tsx`, `ResultsTable.tsx`, `Workspace.tsx`, `types.ts`, `upsertAndAliases.test.ts` |
| `d128d4d` | `feat(sort): structured salary sort strictly scoped to same currency and period` | `frontend/src/lib/sort.ts`, `frontend/src/lib/__tests__/sort.test.ts`, `modules.test.ts` |
| `3f3bf62` | `feat(wire,ui): plain partial results notice and anonymous allowlist classification` | `src/project_files/models.py`, `src/project_files/search_pipeline.py`, `src/api/allowlist.py`, `SearchSummaryBar.tsx`, `promptInput.test.tsx`, `test_api_endpoints.py` |
| `f87e30e` | `test(e2e): playwright test cases for partial notice and in-place upsert` | `tests/e2e/bottom-pot.spec.js` |
| `b1dd46f` | `docs(step-25): record step 25 eval, frontend upsert, sort and partial notice` | `docs/steps/25-eval-and-frontend.md` |
| `b27d295` | `docs(eval): reconcile labelled rows, print confusion matrix, and verify test integrity` | `docs/steps/25-eval-and-frontend.md` |
| `33a1bcd` | `docs(step-25): record eval retraction, description schema, throttle interval, and test integrity` | `PROJECT_COMPENDIUM.md`, `docs/steps/25-eval-and-frontend.md`, `eval_work_model.py`, `config.py`, `search_pipeline.py`, tests |

### Merge Provenance Summary
- **Pull Request**: [PR #29: Step 25: Work Model Evaluation Rebuild, Frontend Upsert & Alias Matching, Structured Salary Sorting, and Partial Results Notice](https://github.com/richmondsogo/bottom-pot/pull/29)
- **First Commit SHA**: `be5fe1715bc347af8c31633d5ff7d8d3902b7eac`
- **Last Commit SHA**: `33a1bcd369527cf63980a31613b4e7fe67f70ef8`
- **Merge Commit SHA**: `081e7701483e98f52c9fc3a32d34d3024ab1ab84`
