# Step 08: Update README and Frontend Documentation for Step 07 Capabilities

**Step Branch**: `step/08-readme-and-docs-update`  
**Base Branch**: `main` (`1c457e6`)  
**Primary Branch**: `main`  

---

## Objective

Update `README.md` and `docs/FRONTEND.md` so project documentation accurately reflects the new capabilities shipped in Step 07:
1. Sanitized GitHub-Flavored Markdown preview rendering (`react-markdown` + `remark-gfm` + `rehype-sanitize`) in `DetailSheet.tsx` with Square Design System typography.
2. Deep Nigerian job board enrichment (`JobbermanScraper` card summary + `article.job__details` detail enrichment, `HotNigerianJobsScraper` `/role/<id>/` & `/field/<id>/` feed routing, roundup `#slug` resolution, and `.mycase4` detail extraction, `MyJobMagScraper` snippet extraction).
3. Saved Jobs ("Shortlist") & 4-stage Application Pipeline (`Saved` · `Applied` · `Interviewing` · `Archived`, `s` keyboard shortcut, `Saved (N)` toolbar filter).
4. Shareable URL State Sync (`?q=...&loc=...&wm=...&saved=1`, Copy search link) and 1-Click Recent Search Presets.
5. Updated verification test counts (`301` Python unit tests, `74` Vitest unit tests, `14` Playwright E2E suites).

## Scope

### Included
- `README.md`
- `docs/FRONTEND.md`
- `docs/steps/08-readme-and-docs-update.md`

### Excluded
- Any production code, styling, or configuration changes.

## Plan

1. Create isolated worktree `step/08-readme-and-docs-update`.
2. Update `README.md` and `docs/FRONTEND.md`.
3. Run `.\scripts\verify.ps1` and `python scripts/eval_work_model.py results.json`.
4. Perform Two-Axis Code Review (`Standards` and `Spec`).
5. Commit, push, open PR, merge into `main`, record provenance, and remove worktree.

## Implementation

- Updated `README.md` (`Architecture Overview`, `Design System & Frontend Architecture`, and `Developer Tooling & Verification`) to document sanitized Markdown previews, deep Nigerian job board enrichment (`Jobberman`, `HotNigerianJobs`, `MyJobMag`, `NgCareers`), Saved Jobs shortlist & 4-stage pipeline, shareable URL state sync & recent search presets, `s` keyboard shortcut, and current test suite counts (`301` pytest, `74` Vitest, `14` Playwright E2E).
- Updated `docs/FRONTEND.md` directory tree and component architecture table to document `savedJobs.ts`, `urlState.ts`, `constants.ts`, `export.ts`, `ShortcutsModal.tsx`, and null-safe field formatting.

## Verification

- `python scripts/eval_work_model.py results.json`: Passed (`0` regressions).
- `.\scripts\verify.ps1`: **8 / 8 checks passed** (Git state, secrets check, CSS cascade lint, `oxlint`, `vitest` 74/74, `tsc + vite build`, `pytest` 301/301, and Playwright E2E 14/14).

## Two-Axis Code Review

- **Standards Axis**: Passed with zero blocking violations; applied two consistency suggestions in `docs/FRONTEND.md` (updated `normalize.ts` description to `null-safe field formatting` per `DESIGN.md` §5.7 and added `ShortcutsModal` to the §2 component table).
- **Spec Axis**: Passed with zero missing requirements, zero scope creep, and full alignment with the codebase.
