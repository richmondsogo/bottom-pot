# Step 03: UI Layout Restore — Phase 0 & Phase 1 Root Cause Diagnosis & Fix

## Phase 0: Orient
- Current branch: `fix/ui-layout-restore` branched from `feat/ui-craft-pass` (commit `dfacc5c`).
- Tag `pre-restore` created at starting commit.
- Captured 2x scale reference screenshots for all 10 states across 5 viewports into `docs/design/before-restore/`:
  - `landing` (light, dark)
  - `landing-more-filters` (light, dark)
  - `loading` (light, dark)
  - `results` (light, dark)
  - `results-filters-active` (light, dark)
  - `saved-results` (light, dark)
  - `no-results` (light, dark)
  - `error` (light, dark)
  - `command-palette` (light, dark)
  - `help-modal` (light, dark)
- Referenced pass-1 structural truth in `docs/design/before-pass-2/` (centered hero, framed form card, fixed table with column alignment).

## Phase 1: Root Cause Diagnosis
1. Ran `scripts/diagnose_computed_styles.js` via Playwright Chromium to read live computed padding, margin, height, and line-height.
2. Empirical findings:
   - `h1`: `mb-4` computed to `margin-bottom: 0px`.
   - `Location input`: `px-3.5` computed to `padding: 0px`.
   - `Search ATS platforms button`: `px-8` computed to `padding: 0px`.
   - `Suggestion chip`: `px-3 py-1` computed to `padding: 0px`.
   - `More filters panel`: `p-6 mt-4` computed to `padding: 0px`, `margin-top: 0px`.
3. Root Cause Identified:
   - Unlayered universal resets in `frontend/src/index.css`:
     ```css
     * {
       box-sizing: border-box;
       margin: 0;
       padding: 0;
       border-radius: 0 !important;
     }
     ```
   - Unlayered CSS takes cascade precedence over `@layer utilities` in Tailwind CSS v4. The unlayered `*` rule silenced all utility padding, margins, and gaps.
4. Source Fix Applied:
   - Removed `margin: 0; padding: 0;` from `*`.
   - Moved all base element resets (`*`, `html`, `body`, `button, input, select, textarea`, `::-webkit-scrollbar`) inside `@layer base`.
   - Verified that Tailwind preflight normalizes elements safely.
   - Re-measured computed styles:
     - `h1` margin-bottom: 16px.
     - `Location input` horizontal padding: 14px (`px-3.5`).
     - `Search ATS platforms button` horizontal padding: 32px (`px-8`).
     - `Suggestion chip` padding: 4px top/bottom, 12px left/right.
     - `More filters panel`: 24px padding (`p-6`), 16px margin-top (`mt-4`).
5. Documented in [ADR 0018](file:///c:/Users/Richmond/Desktop/Codebase/bottom-pot-v1/docs/adr/0018-root-cause-and-fix-of-unlayered-css-resets.md).
