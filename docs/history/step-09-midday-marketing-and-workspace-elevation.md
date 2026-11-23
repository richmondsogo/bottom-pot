# Step 09: Midday Marketing and Workspace Elevation

**Step Branch**: `step/09-midday-marketing-and-workspace-elevation`  
**Primary Branch**: `main`  
**Commit SHA**: `ae2675b`  
**Pull Request**: `Pending`  

---

## Objective

Elevate Bottom Pot to Awwwards SOTD visual and interactive caliber by:
1. Forensic reverse-engineering of Midday.ai's hairline architectural grid, centered hero, tabbed interactive product stage, 4-column proof strip, live interactive bento grid, 18+ ATS matrix, and editorial manifesto into a dedicated marketing experience (`/`).
2. Elevating the core product workspace (`/app` or `?view=app` or `?mock=1`) with pixel-locked table/card layouts, collapsed summary bar, quiet status chrome, and seamless native View Transitions (`document.startViewTransition`) bridging both views.

## Scope

### Included:
- Dual-experience SPA view routing in `App.tsx` (`marketing` view at `/`, `workspace` view at `/app` or `?view=app` / `?mock=1` / on search run), with URL synchronization and native View Transitions (`startViewTransition`).
- Marketing View component suite in `frontend/src/components/marketing/`:
  - `MarketingLanding.tsx`: Architectural shell with full-bleed 1px horizontal hairlines and 1160px vertical side rails.
  - `MarketingHeader.tsx`: Sticky architectural navbar with BP monogram, wordmark, quiet links, ⌘K trigger, theme toggle, and primary CTA.
  - `HeroSection.tsx`: Editorial display headline, status indicator pill, lead subcopy, dual CTAs, and inline quick-search bar with preset chips.
  - `HeroInteractiveStage.tsx`: Framed 1160px showcase stage with 4 live interactive tabs (Live ATS table, 7-tier provenance inspector, SSE dork stream simulation, ⌘K command palette preview).
  - `SignalMetricsStrip.tsx`: 4-column hairline proof strip with tabular numerals and quiet metadata.
  - `BentoFeatureGrid.tsx`: 2x2 architectural feature grid featuring live micro-UIs.
  - `ProvenanceLadderInteractive.tsx`: Interactive 7-tier work model source inspector with real ATS evidence snippets.
  - `AtsPlatformMatrix.tsx`: Interactive 18+ ATS platform coverage grid with multi-selection and direct workspace launch.
  - `EditorialManifesto.tsx`: Midday /story-style high-contrast editorial block + full-width footer CTA.
- Core Workspace Polish:
  - Header: smooth view switcher back to marketing overview (`← Overview` or BP mark) without losing session state (`bp.savedResults`).
  - SearchForm: expanded architectural frame and 40px collapsed summary bar with `/` shortcut re-expand.
  - ResultsTable & ResultsCards: pixel-perfect fixed semantic table, identical `py-3.5 px-3.5` padding, 2px green hover bar (`box-shadow: inset 2px 0 0 0 var(--accent-primary)`), conditional salary column.
  - DetailSheet: 480px slide-out drawer with auditable provenance card, copy action, and keyboard navigation.
  - Strict compliance with ADRs 0001–0021 (`--radius: 0`, forest green accent budget, 2-font typography system).
- Automated unit tests in `frontend/src/test/` and complete verification via `scripts/verify.ps1`.

### Excluded:
- Backend changes to FastAPI endpoints or SSE streaming contracts.
- Any framework migrations (Next.js/Astro/Remix are banned per ADR 0007).
- Invoicing, receipt scanning, or pricing tiers (Midday financial features irrelevant to Bottom Pot).

## Plan

1. **Architecture & Routing Foundation**:
   - Establish `viewMode` state (`marketing` vs `workspace`) in `App.tsx` or a custom hook `useAppView` with URL path and query param synchronization (`/` vs `/app` or `?view=app` / `?mock=1`), native `document.startViewTransition`, and popstate listener.
   - Ensure seamless state preservation (`bp.savedResults`, `bp.searchParams`, `bp.visited`).

2. **Marketing Site Component Suite**:
   - Build `MarketingHeader.tsx`, `HeroSection.tsx`, `HeroInteractiveStage.tsx`, `SignalMetricsStrip.tsx`, `BentoFeatureGrid.tsx`, `ProvenanceLadderInteractive.tsx`, `AtsPlatformMatrix.tsx`, `EditorialManifesto.tsx`, and `MarketingLanding.tsx`.
   - Implement real deterministic data, interactive states, theme-aware tokens, and 0-radius square geometry throughout.

3. **Workspace Craft & Polish**:
   - Update `Header.tsx` to include quick overview link to marketing view.
   - Validate and refine `SearchForm.tsx`, `SearchSummaryBar.tsx`, `Toolbar.tsx`, `ResultsTable.tsx`, `ResultsCards.tsx`, `DetailSheet.tsx`, and `CommandPalette.tsx`.

4. **Automated Testing & ADR Guardrails**:
   - Add Vitest tests for view switching, marketing component interactions, and ADR assertions.
   - Run CSS cascade lint (`node scripts/lint_css_cascade.js`).

5. **Multi-Viewport & Verification Gate**:
   - Visual inspection across 5 viewports (1920, 1440, 1024, 768, 390) and dual themes (light/dark).
   - Run full `.\scripts\verify.ps1`.

---

## Implementation Summary

1. **Dedicated Midday-Engineered Marketing Website (`/`)**:
   - Created full modular marketing component suite in `frontend/src/components/marketing/`:
     - `MarketingHeader.tsx`: 56px sticky top bar, 28x28 Forest Green BP monogram, wordmark, quiet navigation, ⌘K trigger, theme toggle, and primary CTA.
     - `HeroSection.tsx`: Active status indicator pill (`18+ ats platforms · zero aggregator middlemen`), display headline, lead subcopy, dual CTAs ("Launch job engine" & "Inspect live mock dataset"), inline quick-search bar with `query:` prompt prefix and preset chips.
     - `HeroInteractiveStage.tsx`: Framed 1160px showcase stage with window chrome metadata, live row counter, and 4 interactive tabs (`01. Live ATS table`, `02. 7-tier provenance`, `03. SSE dork stream`, `04. Command palette (⌘K)`).
     - `SignalMetricsStrip.tsx`: 4-column hairline proof strip with tabular metrics (`18+`, `7 tiers`, `0`, `<50ms`).
     - `ProvenanceLadderInteractive.tsx`: Clickable 7-step vertical ladder (Tiers 1–7) displaying real JSON/HTML ATS snippets and confidence ratings.
     - `BentoFeatureGrid.tsx`: 2x2 architectural feature grid hosting `ProvenanceLadderInteractive`, real-time SSE & SQLite caching diagnostics, Nigerian/Global Remote ecosystem switcher, and vim-style keyboard triage list (`j`/`k`/visited).
     - `AtsPlatformMatrix.tsx`: 18-platform interactive coverage grid with DM Mono slugs, dork patterns, fidelity badges, multi-select, and "Search selected platforms in Workspace ↗".
     - `EditorialManifesto.tsx`: Midday `/story` style editorial block + high-contrast footer CTA + bottom metadata strip.
     - `MarketingLanding.tsx`: Master shell compiling all marketing components into full-bleed 1px horizontal hairlines and 1160px vertical rails.

2. **Core Product Workspace Elevation (`/app` or `?view=app` / `?mock=1`)**:
   - `Header.tsx`: Added `onBackToMarketing` handler and `← Overview` back link while preserving active search state (`bp.savedResults`).
   - `CommandPalette.tsx`: Added Navigation group to switch between Marketing Overview and Workspace via keyboard.
   - `ResultsTable.tsx`: Adjusted `<th>` padding from `py-3` to `py-3.5 px-3.5` to match `<td>` pixel-for-pixel (ADR 0019), and replaced shifting borders with `box-shadow: inset 2px 0 0 0 var(--accent)` for hover/active/keyboard states.
   - `App.tsx`: Implemented dual-experience view switcher (`viewMode: 'marketing' | 'workspace'`), URL sync (`/` vs `/app` / `?mock=1`), native `document.startViewTransition` wrapper with `prefers-reduced-motion` check, and `popstate` browser back/forward listeners.
   - `src/api/main.py`: Added explicit `/app` route serving SPA `index.html`.

3. **Strict Design System Guardrails (ADRs 0001–0021)**:
   - ADR 0004: Strict `--radius: 0` (`borderRadius === '0px'`) across all elements.
   - ADR 0010: Geist Variable for copy/UI, DM Mono strictly for tabular numerals, slugs, and shortcut keys.
   - ADR 0014: View Transitions API for fluid, native transitions between Marketing and Workspace.
   - ADR 0015: Dual editorial polarity (Light Mode `#FAF8F5` / Dark Mode `#0C0D0C`).
   - ADR 0019: `table-layout: fixed` and identical `3.5` cell padding across `<th>` and `<td>`.
   - ADR 0021: Forest Green accent budget strictly limited to the 6 allowed touchpoints.

---

## Verification Evidence

All 8 verification checks passed with 100% success rate:

```
Bottom Pot Verification Suite
=============================

Repository State:
  OK  Git available
  OK  No tracked secrets (.env, keys, credentials)

Frontend Checks:
  OK  CSS Cascade Lint (no unlayered element/reset selectors)
  OK  Frontend Linting (oxlint)
  OK  Frontend Unit Tests (vitest) - 33 unit tests passed across 4 files
  OK  Frontend Typecheck & Production Build (tsc + vite)

Backend Checks:
  OK  Python Unit Tests (pytest) - 5 backend endpoint tests passed

End-to-End Browser Tests:
  OK  Playwright E2E Suite - 15 end-to-end tests passed across all viewports and states

Results: 8 passed, 0 failed, 0 skipped  (of 8 checks)
```

Playwright E2E Tests Executed:
1. `marketing landing page loads Midday-engineered architecture and meets a11y standards` (passed)
2. `product workspace loads search form and transitions from marketing view` (passed)
3. `search sends correct query parameters and displays results table` (passed)
4. `filter toolbar narrows postings by text search, provider, and work model` (passed)
5. `table sorting sorts by title, company, salary, and date` (passed)
6. `opening detail sheet displays metadata, opens posting, and marks visited` (passed)
7. `keyboard navigation with j/k, Enter, Esc, and /` (passed)
8. `mobile viewport (<768px) switches to stacked card list with zero overflow` (passed)
9. `typography audit validates font families, weights, and scale compliance across visible nodes` (passed)
10. `layout audit: validates shell left edge alignment and zero horizontal overflow across 5 viewports` (passed)
11. `command palette and theme toggle interactions work seamlessly` (passed)
12. `clear saved results triggers toast with undo functionality` (passed)
13. `spacing audit: interactive controls meet minimum padding (12px/8px) and height scale (32, 36, 40, 44, 48)` (passed)
14. `column alignment audit: table header cells and body cells share identical left alignment across columns and rows` (passed)
15. `green budget audit: enforces strict green usage budget across views` (passed)

