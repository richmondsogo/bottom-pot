# Step 21: Confirmed Bug Fixes

Initiative: **Extraction Pipeline & Architecture Overhaul**  
Role: **Planner / Builder**  
Branch: `step/21-extraction-bugfixes`  
Date: 2026-11-01  
Status: **Planned — Awaiting Approval**

---

## 1. Objective & Scope

Execute immediate correctness and bug fixes identified during Step 20 without architectural refactoring, new abstractions, or external contract breaks. Every fix follows strict TDD: a regression test is written and shown failing before applying the fix.

### Bugs in Scope
1. **BUG-01 (Personio `NameError`)**: In `ats_page_enricher.py:457`, replace nonexistent `response.text` with `page_content`.
2. **BUG-02 (`JobSalary` Invalid Defaults)**: In `models.py:227-232`, set `currency=None` and `period=None` (unknown stays `None`). Callers remain untouched without inventing values.
3. **BUG-03 (Ghost Jobs in Frontend Filter)**: In `filter.ts:61-67`, treat `work_model: "unknown"` and `null` as `"not_specified"`, preventing exclusion from results.
4. **BUG-04 (Freshness Label & Greenhouse Date Fallback)**: In `models.py:136-137`, return `"Date not listed"` when `posted_at` is missing. In `ats_api_client.py:169`, remove `updated_at` fallback for `posted_at`.
5. **BUG-05 & BUG-06 (Fallback `is_remote` & Snippet Workplace Type)**: In `ats_page_enricher.py:296, 327`, set fallback `is_remote=None` (not `False`). In `field_normalizer.py:471, 476`, stop passing search snippet as `workplace_type`.
6. **Work-Model Integration & Eligibility Decoupling**: Pass authoritative descriptions from all 7 ATS clients (`greenhouse`, `lever`, `ashby`, `smartrecruiters`, `workable`, `bamboohr`, `recruitee`) to `resolve_work_model`. Decouple extraction eligibility from the presentation display threshold (`len >= 300` in `description_quality` remains strictly preserved for UI). Ensure mere mentions of `"remote teams"` or `"remote collaboration"` do not trigger `remote`.
7. **Timezone Awareness & UTC Deprecation**: Replace `datetime.utcnow()` in `models.py:138` with `datetime.now(timezone.utc)`, eliminating naive datetime arithmetic and all 17 pytest deprecation warnings.

---

## 2. Regression Test Matrix

| Bug / Item | Target Test File | Failure Condition (Before Fix) | Expected Passing Behavior (After Fix) |
|---|---|---|---|
| **BUG-01** | `tests/test_scrapers_and_clients.py` | `NameError: name 'response' is not defined` when parsing Personio HTML | Extracted location, employment type, and department from embedded Personio JSON |
| **BUG-02** | `tests/test_contracts_and_observability.py` | `JobSalary(minimum=100000).currency == "USD"` | `JobSalary(minimum=100000).currency is None` and `period is None` |
| **BUG-03** | `frontend/src/lib/__tests__/filter.test.ts` | Filter by `not_specified` returns 0 for `"unknown"` job | Filter by `not_specified` retains `"unknown"` and `null` jobs; filters for `remote`/`hybrid`/`in_person` exclude `"unknown"` |
| **BUG-04** | `tests/test_field_normalizer.py` & `tests/test_scrapers_and_clients.py` | `JobListing(..., posted_at=None).freshness_label == "Recently posted"` | Returns `"Date not listed"`; Greenhouse with only `updated_at` leaves `posted_at=None` |
| **BUG-05/06** | `tests/test_scrapers_and_clients.py` & `tests/test_work_model.py` | Circuit breaker/WAF produces `is_remote=False`; snippet string resolves as `api_enum` | Circuit breaker/WAF produces `is_remote=None`; snippet string does not resolve as `api_enum` |
| **Work-Model** | `tests/test_work_model.py` & `tests/test_real_api_fixtures.py` | Concise description (<300 chars) ignored because `description_ok=False`; `"remote team"` incorrectly resolves to `remote` | Short description resolves work model; `"remote teams"` and `"remote collaboration"` yield `None` |
| **Time Handling**| `tests/test_contracts_and_observability.py` | 17 `DeprecationWarning: datetime.datetime.utcnow()` | Zero pytest warnings for `utcnow` |

---

## 3. Compatibility Impact Assessment

- **Backend API**: No breaking changes. `JobListing` structure, SSE events, and query endpoints are preserved. `posted_at=None` correctly surfaces `"Date not listed"`.
- **Frontend App**: Bug fix eliminates ghost jobs under filter toggles. No styling or layout regressions.
- **CLI Scripts**: Backward compatible. Raw outputs preserve un-invented fields.

---

## 4. Verification & Baseline Targets

- **Standard Verification Suite**: `powershell -ExecutionPolicy Bypass -File .\scripts\verify.ps1` (8 of 8 passing).
- **Backend Full Test Suite**: `pytest` passes all tests with 0 failures, and `utcnow` deprecation warnings reduced from 17 to 0.
- **Frontend Vitest Suite**: `npm --prefix frontend test` passes all tests including new work-model filter cases.


---

## 5. Execution Proof & Commit Log

### BUG-01: Personio Enrichment `NameError`
- **Failing Test Command**: `pytest tests/test_scrapers_and_clients.py -k "test_personio_enrichment_does_not_raise_name_error_on_response"`
- **Failing Output**:
  ```text
  FAILED tests/test_scrapers_and_clients.py::test_personio_enrichment_does_not_raise_name_error_on_response[asyncio]
  >   raw_html = response.text
  E   NameError: name 'response' is not defined
  src\project_files\ats_page_enricher.py:457: NameError
  ```
- **Fix**: Replaced nonexistent `response.text` with `page_content` in `ats_page_enricher.py:457`.
- **Passing Output**: `1 passed, 28 deselected in 0.16s`.
- **Resolution**: Fully resolved.
- **Compatibility Impact**: None; internal enrichment bug fix.

### BUG-02: `JobSalary` Defaults Removal
- **Failing Test Command**: `pytest tests/test_contracts_and_observability.py -k "test_jobsalary_defaults_are_none_not_invented"`
- **Failing Output**:
  ```text
  FAILED tests/test_contracts_and_observability.py::test_jobsalary_defaults_are_none_not_invented
  >   assert salary.currency is None
  E   AssertionError: assert 'USD' is None
  E   + where 'USD' = JobSalary(minimum=100000, maximum=None, currency='USD', period='year').currency
  ```
- **Fix**: Changed `currency: Optional[str] = None` and `period: Optional[str] = None` in `src/project_files/models.py:230-231`.
- **Passing Output**: `9 passed in 2.17s`.
- **Frontend & Cache Store Audit**:
  - `frontend/src/lib/normalize.ts` (`formatSalary`) checks `salary.currency ? ... : ''` and `salary.period ? ... : ''`. Null currency and period format cleanly as `100,000 – 140,000` without fabricated "$" or "/yr".
  - `frontend/src/lib/sort.ts` inspects numeric `minimum`/`maximum` directly; unaffected by null currency.
  - `src/project_files/cache_store.py`: Persists `listing.model_dump_json()` with 24h TTL. Existing cached entries prior to this fix may carry serialized `USD`/`year`; these expire naturally under `URL_CACHE_TTL_HOURS=24` (noted as known limitation until Step 24 cache versioning).
- **Resolution**: Fully resolved.
- **Compatibility Impact**: None; models honestly preserve `None` when currency/period are not supplied.

### BUG-03: Frontend Filter Ghost Jobs for `work_model: "unknown"`
- **Failing Test Command**: `npm --prefix frontend test filter.test.ts`
- **Failing Output**:
  ```text
  FAIL src/lib/__tests__/filter.test.ts > filterJobs > treats unknown and null work models as not specified without ghosting
  AssertionError: expected [ '5' ] to include '4'
  > 131| expect(notSpecifiedIds).toContain('4');
  ```
- **Fix**: In `frontend/src/lib/filter.ts:66`, evaluated `const isSpecified = Boolean(job.work_model && job.work_model !== 'unknown')` so `"unknown"` is recognized as not specified.
- **Passing Output**: `7 passed in 13ms` (`filter.test.ts`), `72 passed in 4.09s` (full Vitest suite).
- **Resolution**: Fully resolved.
- **Compatibility Impact**: Jobs with `work_model: "unknown"` are now visible when filtering by `"not_specified"`, eliminating ghost jobs while properly excluded from `"remote"`, `"hybrid"`, and `"in_person"`.

### BUG-04: Freshness Label "Date not listed" & Greenhouse Fallback Removal
- **Failing Test Command**: `pytest tests/test_field_normalizer.py tests/test_scrapers_and_clients.py -k "test_freshness_label_without_posted_at_is_date_not_listed or test_greenhouse_client_does_not_fallback_to_updated_at"`
- **Failing Output**:
  ```text
  FAILED tests/test_field_normalizer.py::test_freshness_label_without_posted_at_is_date_not_listed
  >   assert job.freshness_label == 'Date not listed'
  E   AssertionError: assert 'Recently posted' == 'Date not listed'

  FAILED tests/test_scrapers_and_clients.py::test_greenhouse_client_does_not_fallback_to_updated_at[asyncio]
  >   assert job.posted_at is None
  E   AssertionError: assert datetime.datetime(2024, 3, 1, 12, 0, tzinfo=datetime.timezone.utc) is None
  ```
- **Fix**:
  - In `src/project_files/models.py:136-137`, returned `"Date not listed"` when `not self.posted_at`.
  - In `src/project_files/ats_api_client.py:169`, removed `or data.get("updated_at")` fallback, requiring explicit `first_published` or `created_at`.
- **Passing Output**: `2 passed, 144 deselected in 0.40s`.
- **Resolution**: Fully resolved.
- **Compatibility Impact**: Jobs without dates display `"Date not listed"` honestly instead of pretending to be recent; stale Greenhouse postings with minor edits no longer appear as newly posted.
