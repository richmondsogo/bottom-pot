# Step 28: Nigerian Boards Selection & Derived Checkbox

## Overview
- **Goal**: Make "Include Nigerian boards" checkbox strictly derived from selected platform chips, establishing a single source of truth:
  - The checkbox is checked only when ALL 3 Nigerian chips (`jobberman`, `myjobmag`, `hotnigerianjobs`) are selected.
  - Ticking the checkbox selects all 3 Nigerian chips.
  - Unticking the checkbox clears all 3 Nigerian chips.
  - Deselecting any single Nigerian chip unchecks the checkbox.
  - Re-selecting the last missing Nigerian chip re-checks the checkbox.
  - With only an ATS selected (e.g. Greenhouse), the checkbox is unchecked.
  - Selection persists across page reloads via `localStorage` (`bp.selectedPlatforms`).
  - URL parameter rules:
    - Applied only when `ng` is explicitly present in the URL query.
    - `ng=0` deselects all Nigerian chips.
    - `ng=1` selects all 3 Nigerian chips only if none are currently selected.
    - Absent `ng` leaves the user's saved selection untouched.
    - `buildShareableSearchUrl` writes `ng=1` if any Nigerian chip is selected, or `ng=0` if none is selected.
  - Complete removal of `includeNigerian` as separate state across `SearchParams`, `RecentSearchPreset`, `App.tsx`, and `urlState.ts`.
  - Legacy stored blobs containing `includeNigerian` load gracefully without throwing or erroring.
- **PR**: https://github.com/richmondsogo/bottom-pot/pull/33
- **Branch**: `step/28-nigerian-chips`
- **First Commit SHA**: Pending commit
- **Last Commit SHA**: Pending commit
- **Merge Commit SHA**: Pending merge
- **Baseline Metrics**:
  - Full pytest: 570 passed (backend delta: 0, 570 passed)
  - Vitest: 89 passed (+5 new tests in `nigerianChips.test.ts`, 94 passed)
  - Playwright: 35 passed (+1 new test in `bottom-pot.spec.js`, 36 passed)
  - `.\scripts\verify.ps1`: 8/8 passed

## Verification Results
- `npm --prefix frontend run test`: 13 test files passed, 94 tests passed.
- `npm --prefix frontend run build`: zero errors (production build succeeded).
- `python -m pytest`: 570 passed, 4 warnings in 32.42s (delta: 0).
- `npx playwright test`: 36 passed (1.1m) across 2 workers.
- `.\scripts\verify.ps1`: 8 passed, 0 failed, 0 skipped.
- Visual inspection: Captured AFTER screenshots in light (`docs/design/after/step28_platform_chips_light.png`) and dark (`docs/design/after/step28_platform_chips_dark.png`) modes, both optimized (<45 KB).

## Changed Pre-Existing Tests
- `frontend/src/lib/__tests__/modules.test.ts`: Removed deprecated `includeNigerian: true` property from `SearchParams` fixtures.
- `frontend/src/lib/__tests__/promptInput.test.tsx`: Removed deprecated `includeNigerian: true` from mock `searchParams` props; updated assertion to verify `id="nigerian-boards-check"` is rendered in `SearchForm`.
- `frontend/src/lib/__tests__/shareUrl.test.ts`: Removed deprecated `includeNigerian: true` from `dummyState.searchParams` test fixture.
- `frontend/src/lib/__tests__/urlState.test.ts`: Removed deprecated `includeNigerian: true` from `mockState.searchParams` and `emptyState.searchParams` test fixtures.
- `tests/e2e/bottom-pot.spec.js`: Added 1 end-to-end test verifying all 4 interactive checkbox/chip behaviors, reload persistence, Greenhouse-only unchecked state, and screenshot capture.
