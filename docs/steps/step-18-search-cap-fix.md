# Step 18: Search Cap Fix & Test Database Isolation

**Step Branch**: `step/18-search-cap-fix`  
**Primary Branch**: `main`  
**Baseline**: main at `58ef527` (PR #19)  
**Status**: IN_PROGRESS  
**PR URL**: (pending PR creation)  
**First Commit SHA**: `d5323cd`  
**Last Commit SHA**: (pending)  
**Merge Commit SHA**: (pending)  

---

## 1. Goal

1. Hotfix search cap leak from step 16 where `is_halted` in `SearchOrchestrator` checked `not any(k == SourceKind.ATS for _, k, _ in tasks.values())`, causing 18 ATS platforms to make 54 Serper page requests and stream 565 results against a cap of 100.
2. Restore clean progressive stopper cancellation across all tasks once `len(all_collected) >= effective_max_results`.
3. Adjust `total_nigerian_cap` to `min(25, int(effective_max_results * 0.5))` so that ATS platforms always have at least 50% of slots reserved across all `max_results` values (including `max_results=20`).
4. Ensure streamed result batches are sliced to remaining available slots (`max(0, effective_max_results - len(all_collected))`) so total streamed results strictly never exceed `effective_max_results`.
5. Isolate pytest from repository `data/cache.sqlite` by redirecting `SQLITE_DB_PATH` and `cache_store.db_path` to a temporary directory in `tests/conftest.py`.

---

## 2. Before & After Benchmark Table

Benchmark configuration: 18 ATS platforms, 10 organic results per page, 4 Nigerian scrapers returning 30 listings each.

| Metric | Before (Step 16 regression on main) | After (Step 18 fix) |
| :--- | :--- | :--- |
| **Total Results Streamed (`max_results=100`)** | 565 (540 ATS + 25 Nigerian) | 100 (75 ATS + 25 Nigerian) |
| **Serper Page Requests (`max_results=100`)** | 54 (18 platforms × 3 pages) | 18 (18 platforms × 1 page, page 2/3 halted) |
| **Nigerian Board Results (`max_results=100`)** | 25 | 25 (`total_nigerian_cap`) |
| **ATS Results (`max_results=100`)** | 540 | 75 (guaranteed floor) |
| **Total Results Streamed (`max_results=20`)** | 565 | 20 (10 ATS + 10 Nigerian) |
| **ATS Slot Floor (`max_results=20`)** | 8 slots (40%) | 10 slots (50% guaranteed) |
| **Late-finishing ATS Task Handling** | Ran to completion, yielded results | Cancelled immediately; 0 results appended |
| **`data/cache.sqlite` During Pytest** | Tables cleared; daily budget wiped | Unchanged (mtime identical before/after) |

---

## 3. Implementation Details

### A. Halting Semantics & Progressive Stopper (`src/project_files/search_pipeline.py`)
- Removed `and not any(k == SourceKind.ATS for _, k, _ in tasks.values())` from `is_halted` lambda.
- Restored `is_halted = lambda: len(all_collected) >= effective_max_results`.
- Removed `has_pending_ats` branch in progressive stopper; when `len(all_collected) >= effective_max_results`, all remaining pending tasks (both ATS and Nigerian) are cancelled immediately and recorded with `SourceOutcome.CANCELLED`.
- Added batch slicing: `unique_new = unique_new[:max(0, effective_max_results - len(all_collected))]` to guarantee strict `< = effective_max_results` compliance.

### B. Cap Arithmetic & ATS Slot Reservation
- Formula: `total_nigerian_cap = min(25, int(effective_max_results * 0.5))`
- Proof for test values:
  - `max_results = 100`: `total_nigerian_cap = min(25, 50) = 25`. ATS floor: `100 - 25 = 75` (75% reserved for ATS).
  - `max_results = 40`: `total_nigerian_cap = min(25, 20) = 20`. ATS floor: `40 - 20 = 20` (50% reserved for ATS).
  - `max_results = 20`: `total_nigerian_cap = min(25, 10) = 10`. ATS floor: `20 - 10 = 10` (50% reserved for ATS).

### C. Test Database Isolation (`tests/conftest.py`)
- Configured `tempfile.TemporaryDirectory()` at session start.
- Set `os.environ["SQLITE_DB_PATH"]`, `settings.sqlite_db_path`, and `cache_store.db_path` to point to the temporary database.
- Added session cleanup fixture to delete the temporary directory after pytest completes.
- Added test in `tests/test_phase5_cost_and_robustness.py` asserting `Path(settings.sqlite_db_path).resolve() != Path("data/cache.sqlite").resolve()`.
