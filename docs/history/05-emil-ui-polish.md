# Step 05: Emil Kowalski UI Motion Polish & Interaction Refinement

**Step Branch**: `feat/emil-ui-polish`  
**Base Branch**: `fix/ui-layout-restore` (`ac2fe0f17b28bae64142689d9203f6b9791b8c1e`)  
**Primary Branch**: `main`  

---

## Objective

Refine tactile interaction feedback, drawer/modal entrance transitions, and popover/tooltip timing across the Bottom Pot UI using Emil Kowalski's design engineering principles—while preserving 100% of the restored layout geometry, spacing, and visual appearance at rest.

## Scope

### Included
- Motion and easing CSS custom properties in `frontend/src/index.css` (`--duration-fast`, `--duration-base`, `--duration-press`, `--duration-drawer`, `--ease-out`, `--ease-drawer`, `--ease-press`).
- Hardware-accelerated `@starting-style` entrance animations for `.detail-sheet`, `.detail-sheet-backdrop`, `.modal-backdrop`, and `.modal-card` with `prefers-reduced-motion: reduce` overrides.
- Subtle active press scaling (`active:scale-[0.97]` / `active:scale-[0.98]`) and explicit property transitions (replacing `transition-all`) on buttons, suggestion chips, filter triggers, and platform chips (`button.tsx`, `SearchForm.tsx`, `ResultsTable.tsx`).
- Popover, dropdown, select, sheet, command dialog, and tooltip transition curve/delay refinements (`command.tsx`, `dropdown-menu.tsx`, `popover.tsx`, `select.tsx`, `sheet.tsx`, `tooltip.tsx`).
- Addition of `ui-ux-pro-max` skill in `.agents/skills/ui-ux-pro-max/` and `skills-lock.json`.

### Excluded
- Any change to static visual layout, spacing, colors, typography, or column alignment.
- Backend API or scraper logic changes (handled in Step 06).

## Plan

1. Inspect and verify all modified files in `feat/emil-ui-polish`.
2. Run `.\scripts\verify.ps1` (CSS cascade lint, `oxlint`, Vitest, `tsc + vite` build, `pytest`, and Playwright E2E suite including layout, spacing, column alignment, and green budget audits).
3. Run two-axis `code-review` (Standards + Spec) against `fix/ui-layout-restore`.
4. Commit the changes cleanly on `feat/emil-ui-polish`, push to `origin`, open Pull Request, and land via `--no-ff` merge commit per Build Protocol.

## Implementation

- Replaced broad `transition-all` on `Button` and interactive controls with explicit property lists (`transition-[color,background-color,border-color,transform]`) to avoid unintended layout transitions.
- Added tactile press feedback (`active:not-aria-[haspopup]:scale-[0.97]` on `Button`, `active:scale-[0.97]`/`[0.98]` on chips) at `140ms ease-out`.
- Configured `TooltipProvider` with `delay = 200` and `closeDelay = 150` and tightened zoom scale to `0.97` so tooltips do not flicker on cursor pass-through.
- Added `@starting-style` drawer slide (`translateX(100%)` with `cubic-bezier(0.32, 0.72, 0, 1)`) and modal card scale (`scale(0.96)` with `cubic-bezier(0.16, 1, 0.3, 1)`), plus `prefers-reduced-motion: reduce` fallbacks.
- Enforced `rounded-none!` on `DropdownMenuContent` and `PopoverContent` to guarantee strict 0-radius square geometry.

## Discoveries

- `DetailSheet.tsx` and `ShortcutsModal.tsx` mount conditionally when active, making CSS `@starting-style` an ideal zero-JS mechanism for smooth hardware-accelerated entry transitions without layout thrashing.
- `DropdownMenuContent` and `PopoverContent` in `components/ui/` previously had `rounded-lg` in their default class strings (overridden by `* { border-radius: 0 !important }` in `@layer base`); replacing `rounded-lg` with `rounded-none!` keeps the component classes aligned with the Square Design System.

## Two-Axis Code Review (`code-review` Skill)

- **Standards Axis**: Verified zero regressions in layout, spacing, or square geometry. Noted minor token duplication across `ui/` popup primitives (`cubic-bezier(0.16,1,0.3,1)`) and 220ms drawer slide curve (`--duration-drawer: 220ms`). Preserved as-is per user instruction not to alter any frontend visual/motion behavior.
- **Spec Axis**: Verified all 12 modified files and `.agents/skills/ui-ux-pro-max/` match the intended scope with zero static visual layout changes.

## Verification

- **Unified Verification (`.\scripts\verify.ps1`)**: **8 / 8 checks passed**
  - Git available: `OK`
  - No tracked secrets: `OK`
  - CSS Cascade Lint (`node scripts/lint_css_cascade.js`): `OK`
  - Frontend Linting (`oxlint`): `OK` (0 errors, 0 warnings)
  - Frontend Unit Tests (`vitest`): `OK` (25/25 passing)
  - Frontend Typecheck & Production Build (`tsc + vite`): `OK`
  - Python Unit Tests (`pytest`): `OK`
  - Playwright E2E Suite (`npx playwright test`): `OK` (14/14 passing across all 5 viewports, including typography audit, layout audit, spacing audit, column alignment audit, green budget audit, and Axe-core WCAG AA checks)
- **Serper Live Searches**: `0` (strictly mock/fixture mode)


## Provenance

| Field | Value |
| :--- | :--- |
| **Step Name** | `05-emil-ui-polish` |
| **Branch** | `feat/emil-ui-polish` |
| **PR URL** | https://github.com/richmondsogo/bottom-pot/pull/9 |
| **First Commit SHA** | `98095098e1051e8f4b1f7c75d9aa794e51148153` |
| **Last Commit SHA** | `98095098e1051e8f4b1f7c75d9aa794e51148153` |
| **Merge Commit SHA** | `8d1878140d17b7cf6f36c84b3f98c716bc7c33e5` |
