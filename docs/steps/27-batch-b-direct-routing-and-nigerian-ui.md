# Step 27: Batch B — Company Direct Board Routing and Nigerian UI Alignment

## Overview
- **Goal**: Implement Batch B features:
  1. **Feature 7 (Nigerian UI & Backend Alignment)**:
     - Retired `ngcareers` (domain is permanently retired / redirected to jobberman.com).
     - Unified Nigerian scrapers into the first-class `platforms` filter system in `SearchOrchestrator` (`jobberman`, `myjobmag`, `hotnigerianjobs`).
     - Added `hotnigerianjobs` ("HotNigerianJobs (NG)") as an explicit platform chip in `ALL_PLATFORMS`.
     - Removed the standalone "Include Nigerian Tech Sites" checkbox from `SearchForm.tsx`.
     - Deprecated `include_nigerian_sites` query param for wire backwards compatibility.
  2. **Feature 6 (Company Direct Board Routing)**:
     - Implemented candidate company slug detection in `direct_board_router.py`.
     - Added direct ATS board probing for Greenhouse (`/v1/boards/{slug}/jobs`), Lever (`/v0/postings/{slug}?mode=json`), and Ashby (`/posting-api/job-board/{slug}`).
     - Strict adherence to ADR 0001 ("Unknown beats wrong"): 404s/non-200s are dropped cleanly without hallucinating or guessing.
     - Wired direct board probing into `SearchOrchestrator`, running concurrently and cleanly deduplicating with Serper search results.
- **PR**: https://github.com/richmondsogo/bottom-pot/pull/32
- **First Commit SHA**: `3c3e367`
- **Last Commit SHA**: `41c3c0c`
- **Branch**: `step/27-batch-b-direct-routing-and-nigerian-ui`
- **Baseline Pytest Count**: 557 passed on `main` (`b9fd110`).
- **Post-Step Pytest Count**: 570 passed (+13 net new unit and integration tests).

## Commits & Deltas
1. `3c3e367` `feat(backend): unify Nigerian scrapers with platforms filter and retire ngcareers` (+4 tests, 557 -> 561)
   - Retired `NgCareersScraper` from active `NIGERIAN_SCRAPERS`.
   - Unified scraper filtering with `platforms` list; default (`platforms=None`) runs all 3 active scrapers.
   - Added `tests/test_platform_filter_nigerian.py`.
2. `47b60b0` `feat(frontend): add hotnigerianjobs platform chip and remove legacy checkbox`
   - Added `{ id: 'hotnigerianjobs', name: 'HotNigerianJobs (NG)' }` to `ALL_PLATFORMS`.
   - Removed standalone `includeNigerian` checkbox from `SearchForm.tsx`.
   - Updated `WhereWeSearchSection.tsx` and Vitest tests (89 tests passing).
3. `49db073` `feat(ats): company direct board router for Greenhouse, Lever, and Ashby` (+6 tests, 561 -> 567)
   - Added `src/project_files/direct_board_router.py` with `extract_company_slug_candidates`, `probe_greenhouse_board`, `probe_lever_board`, and `probe_ashby_board`.
   - Added unit tests in `tests/test_direct_board_router.py`.
4. `9ca0d87` `feat(pipeline): wire direct board routing into SearchOrchestrator with deduplication` (+3 tests, 567 -> 570)
   - Added `_search_direct_boards` to `SearchOrchestrator`.
   - Wired concurrent task execution and deduplication.
   - Added integration tests in `tests/test_direct_board_routing_integration.py`.
5. `docs(step-27): record step log and provenance`

## Verification Summary
- `python -m pytest -q`: 570 passed, 4 warnings in 40.00s.
- `npm --prefix frontend run test`: 12 test files passed, 89 passed.
- `npm --prefix frontend run build`: zero errors (production build succeeded in 2.17s).
- `.\scripts\verify.ps1`: 8 passed, 0 failed, 0 skipped.
