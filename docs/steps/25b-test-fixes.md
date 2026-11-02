# Step 25b: Test Fixes, Clock Freezing, and Pipeline Deduplication Alignment

Initiative: **Evaluation & Resilience Test Hardening**  
Role: **Planner / Builder**  
Branch: `step/25b-test-fixes`  
Base Commit: `bc72b7b514b8a24f0c4bbd72379b37c02b3cbbd1` (Merged PR #29 / Provenance on `main`)  
Date: 2026-11-02  
Status: **Merged to main**  
Pull Request: https://github.com/richmondsogo/bottom-pot/pull/30  
First Commit: `47f45582f6e917d8487b333cfb57f00ca8d338f0`  
Last Commit: `47f45582f6e917d8487b333cfb57f00ca8d338f0`  
Merge Commit: `335657d1f3711defa635ebedfabb6d8890757e69`  

---

## 1. Scope & Implementation Checklist

This follow-up resolves 4 specific test and pipeline alignment items after the Step 25 merge:
1. **Golden Replay Clock Freezing**: Restoring `freshness_label` comparisons across the four golden replay tests (`test_workday_cxs_golden_replay`, `test_jobvite_golden_replay`, `test_jazzhr_golden_replay`, `test_teamtailor_golden_replay`) by freezing the clock to fixture creation time (`2026-11-01T14:00:00Z`) instead of popping the field.
2. **Conservative Deduplicator Scenarios**: Restoring the original dedup scenario where snippet is emitted first and API record arrives second as an upgrade (asserting API record emits once, snippet does not re-emit, and total does not inflate), while preserving the lower-rank-after-higher test.
3. **Pipeline Deduplication Alignment & Cleanup**: Removing the duplicate declaration of `new_items_to_add` and removing `listings_match` from `search_pipeline.py` so the streaming pipeline matches strictly on deduplicator identity (`id` and `aliases` only).
4. **Pipeline Cap & Identity Tests**: Adding tests in `tests/test_deduplicator.py` verifying that jobs considered equal by `listings_match` but separated by the deduplicator both survive in `all_collected`, and verifying that upgrades are emitted even when the max-results cap has been reached while the cap still rejects new jobs.

### Checklist
- [x] **Item 1: Golden Replay Clock Freezing (`tests/test_description_extraction.py`)**
  - [x] Implemented `freeze_models_clock` context manager patching `src.project_files.models.datetime`.
  - [x] Restored `freshness_label` assertions across all four golden replay tests without stripping the field.
  - [x] Confirmed 31/31 tests pass in `tests/test_description_extraction.py`.
- [x] **Item 2: Conservative Deduplicator Scenarios (`tests/test_conservative_deduplicator.py`)**
  - [x] Restored `test_streaming_filter_merges_across_batches_without_duplicate_emission` (snippet emitted first, API arrives as upgrade).
  - [x] Asserted API record is emitted once as an upgrade (`len(emitted_2) == 2`), snippet is not re-emitted, and total does not inflate (`len(dedup._emitted) == 2`).
  - [x] Kept `test_streaming_filter_merges_lower_rank_arrival_without_duplicate_emission` (API emitted first, snippet merged internally without re-emission).
  - [x] Confirmed 8/8 tests pass in `tests/test_conservative_deduplicator.py`.
- [x] **Item 3: Search Pipeline Identity Matching & Cleanups (`src/project_files/search_pipeline.py`)**
  - [x] Removed duplicate declaration of `new_items_to_add: list[JobListing] = []`.
  - [x] Removed unused import of `listings_match` from `deduplicator.py`.
  - [x] Replaced `listings_match` scan with identity matching (`id` and `aliases` only).
- [x] **Item 4: Dedicated Pipeline Cap & Identity Tests (`tests/test_deduplicator.py`)**
  - [x] Added `test_search_pipeline_preserves_jobs_that_listings_match_considers_equal_when_dedup_keeps_separate`.
  - [x] Added `test_search_pipeline_emits_upgrades_when_cap_reached_and_caps_new_jobs`.
  - [x] Confirmed 8/8 tests pass in `tests/test_deduplicator.py`.
- [x] **Item 5: Verification & Zero Regression Audit**
  - [x] Confirmed no other existing assertions were modified or weakened.
  - [x] Ran `.\scripts\verify.ps1` (8/8 passed).
  - [x] Recorded test suite deltas vs baseline (540 passed vs 537 baseline).

---

## 2. Test Suites & Verification Comparison

| Suite | Step 25 Baseline | Step 25b Post-Fixes | Delta | Status |
|---|---|---|---|---|
| `verify.ps1` Checks | 8/8 Passed | **8/8 Passed** | 0 | All checks passing |
| Python Pytest Suite | 537 Passed | **540 Passed** | +3 passed | 0 failed, 0 skipped |
| Frontend Vitest Suite | 89 Passed (12 files) | **89 Passed (12 files)** | 0 | All tests passing |
| Playwright E2E Suite | 35 Passed | **35 Passed** | 0 | All tests passing |

---

## 3. Detailed Component Notes

### 3.1 Clock Freezing in Golden Replay Tests
In `tests/test_description_extraction.py`:
- `JobListing.freshness_label` computes relative time using `datetime.now(timezone.utc)`. Because the golden fixtures were recorded on `2026-11-01T14:00:00Z`, as calendar time advances into subsequent months, dynamic calculations without a fixed clock would diverge from static fixture values.
- Implemented `freeze_models_clock` context manager:
  ```python
  FIXED_GOLDEN_NOW = datetime(2026, 11, 1, 14, 0, 0, tzinfo=timezone.utc)

  @contextmanager
  def freeze_models_clock(frozen_dt: datetime = FIXED_GOLDEN_NOW):
      with patch("src.project_files.models.datetime") as mock_dt:
          mock_dt.now.return_value = frozen_dt
          mock_dt.timezone = timezone
          yield
  ```
- All four replay tests (`workday_cxs_golden_replay`, `jobvite_golden_replay`, `jazzhr_golden_replay`, `teamtailor_golden_replay`) now run within `freeze_models_clock()`, comparing `freshness_label` directly against the stored JSON files without popping or ignoring the field.

### 3.2 Deduplication Scenarios
In `tests/test_conservative_deduplicator.py`:
- **Snippet first, API second**:
  `test_streaming_filter_merges_across_batches_without_duplicate_emission` asserts that when `generic:snip1` is emitted in Batch 1, and the higher-ranked `smartrecruiters:wise:744000155937924` arrives in Batch 2 alongside `distinct_job`, the API record is emitted as an in-place upgrade (`emitted_2` length 2), the snippet is not re-emitted, and the deduplicator's internal total remains exactly 2.
- **API first, snippet second**:
  `test_streaming_filter_merges_lower_rank_arrival_without_duplicate_emission` asserts that when the API record is emitted first, a subsequent snippet arrival is merged internally without SSE re-emission (`emitted_2` length 1), and the total remains 2.

### 3.3 Pipeline Deduplication Alignment & Cap Isolation
In `src/project_files/search_pipeline.py`:
- Removed duplicate local variable initialization `new_items_to_add`.
- Removed `listings_match` from the in-place upgrade check in `SearchOrchestrator.run`, keeping only:
  ```python
  if (
      item.id == existing.id
      or item.id in existing.aliases
      or existing.id in item.aliases
  ):
  ```
- Verified that two jobs with matching URLs that the deduplicator intentionally keeps distinct are both preserved in `all_collected`.
- Verified that when `effective_max_results` is reached, arriving upgrades for existing jobs are still emitted, while new jobs are rejected by the cap.

---

## 4. Commit Provenance Table

| Commit SHA | Commit Message | Scope / Component |
|---|---|---|
| `47f4558` | `fix(tests,pipeline): freeze replay clock, restore dedup scenarios, and align pipeline identity` | `tests/test_description_extraction.py`, `tests/test_conservative_deduplicator.py`, `src/project_files/search_pipeline.py`, `tests/test_deduplicator.py`, `docs/steps/25b-test-fixes.md` |

### Merge Provenance Summary
- **Pull Request**: [PR #30: Step 25b: Test Fixes, Clock Freezing, and Pipeline Deduplication Alignment](https://github.com/richmondsogo/bottom-pot/pull/30)
- **First Commit SHA**: `47f45582f6e917d8487b333cfb57f00ca8d338f0`
- **Last Commit SHA**: `47f45582f6e917d8487b333cfb57f00ca8d338f0`
- **Merge Commit SHA**: `335657d1f3711defa635ebedfabb6d8890757e69`

