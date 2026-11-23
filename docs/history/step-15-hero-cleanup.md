# Step 15: Hero Cleanup & Marketing-Workspace Handoff

**Step Branch**: `step/15-hero-cleanup`
**Primary Branch**: `main`
**Baseline**: main at `b6a6a3f` after step 14 (user app strip), PR #17
**Status**: COMPLETED
**PR URL**: https://github.com/richmondsogo/bottom-pot/pull/18
**First Commit SHA**: `6918e0a`
**Last Commit SHA**: `02441d1`
**Merge Commit SHA**: TBD (recorded in Step 16 doc)

---

## 1. Goal

Eliminate the embedded `<SearchForm variant="embedded" />` from the hero portal reveal and static fallback, eliminate the `SampleResultsSection` fake results table under the hero, and streamline the user workspace heading and submit button copy to "Search jobs". Establish a calm, editorial, deliberate handoff from the marketing landing page to the user workspace.

---

## 2. Scope

- **Sample Results Table Removal**:
  - Deleted `frontend/src/components/marketing/SampleResultsSection.tsx`.
  - Removed import and rendering of `SampleResultsSection` from `frontend/src/components/marketing/MarketingLanding.tsx`.
- **Embedded Hero Form Removal & Clean CTA Handoff**:
  - In `frontend/src/components/marketing/HeroPortalSection.tsx`, removed `<SearchForm variant="embedded" />` from both the portal reveal (`[data-gp-portal-content]`) and the static fallback (`#search-panel`).
  - Replaced the embedded form with a focused hero CTA block:
    - Heading: `"What kind of role are you after?"`
    - Primary CTA button: `"Start searching"` with arrow icon, transitioning cleanly to `/app` and focusing `#keywords-input`.
    - Preset chips: 3 quick-starter `PromptSuggestion` chips ("React engineer · Remote", "Python developer · Lagos", "Product Manager · Remote") calling `onQuickSearch` to trigger search on `/app`.
    - Calm trust indicator line: `"Searches Greenhouse, Lever, Ashby, Workable, and Nigerian job boards."`
  - Cleaned up top nav anchor links in `HeroPortalSection.tsx`: removed dead `"How it works"` link (`#how-it-works`); anchors are strictly `"Where we search"` (`#where-we-search`), `"Why Bottom Pot"` (`#why-bottom-pot`), and `"Manifesto"` (`#manifesto`).
- **User Workspace Heading & Submit Copy Streamlining**:
  - In `frontend/src/components/SearchForm.tsx`, gated heading and submit button copy by `mode`:
    - When `mode === 'user'`: renders `<h1 className="text-2xl sm:text-3xl font-semibold tracking-tight text-[var(--ink)]">Search jobs</h1>` (no subtitle / lead sentence) and primary submit button copy `"Search jobs"`.
    - When `mode === 'admin'`: preserves original `<h1>Find the signal behind the noise.</h1>`, lead sentence, and `"Search ATS platforms"` button copy.
- **Restrained CTA Motion (140ms ease-out, ADR 0014 & ADR 0021)**:
  - Added restrained motion (`transition-[background-color,color,transform] duration-140 ease-out active:scale-[0.98] motion-reduce:transform-none motion-reduce:transition-none` and arrow `group-hover:translate-x-0.5`) across all marketing "Start searching" CTA buttons:
    - `HeroPortalSection.tsx` (primary CTA button).
    - `glyph-portal.tsx` (`[data-gp-enter]` button with `motion-reduce:transition-none motion-reduce:transform-none`).
    - `EditorialManifesto.tsx` (bottom manifesto CTA button).
  - Explicitly avoided scale transforms on the workspace search submit button.
- **Test Suite Updates**:
  - Updated `tests/e2e/bottom-pot.spec.js`:
    - Updated `runSearch` helper button selector to match `/search (jobs|ats platforms)/i`.
    - Updated heading assertion to expect `'Search jobs'`.
    - Resolved strict mode button locator in manifesto check by targeting `.first().click()`.
    - Added comprehensive E2E test verifying zero embedded forms on `/`, zero sample results strings, and clean handoff to `/app` via both primary button and preset chips.

---

## 3. Out of Scope

- Changes to `WhyDifferentSection`, `WhereWeSearchSection`, or `EditorialManifesto` copy/structure.
- Scale transforms or bounce motion on workspace search submit button.
- Backend pipeline, ATS clients, scraping logic, or model changes.
- Any new dependencies (npm or pip).

---

## 4. Known Limits & Edge Cases

- **Marketing Baseline Parity Diff**: `ext-1` was captured prior to Step 15 when marketing contained `SampleResultsSection` and the embedded SearchForm. In Step 15, marketing intentionally removes both. The visual comparison is documented in `contact-sheet-step15.html`.
- **User Baseline Command Palette Diff**: In `user-1` baseline, `results_command_palette` HTML captured a transient table-row focus class because `Ctrl+K` had been pressed before the modifier guard was added in Step 14. In `user-step15`, the table row correctly remains unfocused.

---

## 5. Verification & Test Suite

- **Frontend Linter (Oxlint)**: 3 baseline warnings (only-export-components), 0 errors.
- **Frontend Unit Tests (Vitest)**: 57 passed across 8 test suites in 2.41s.
- **Frontend Production Build**: `tsc -b && vite build` clean in 2.11s.
- **Backend Unit & Integration Tests (Pytest)**: 329 passed, 21 pre-existing warnings in 12.23s.
- **End-to-End Tests (Playwright)**: 30 passed (`--workers=1`) in 1.3m across all desktop and mobile viewports.
- **Marketing Audit (5 Viewports: 1920, 1440, 1024, 768, 390)**:
  - 0 occurrences of all 9 `SampleResultsSection` strings across all 5 viewports.
  - 0 `<form>` tags across all 5 viewports.
- **Admin Workspace Parity**:
  - 33/33 admin workspace states MATCH 100% byte/DOM identical to `ext-1` under `normalizeAdminDom` (0 mismatches).
- **User Workspace Parity**:
  - 26/28 non-form workspace states MATCH 100% byte/DOM identical to `user-1` (2 command palette states differ only by pre-existing row focus bug fixed in Step 14).
  - 5/5 `form_*` states differ strictly and solely by the streamlined "Search jobs" heading and button copy.
- **Serper Daily Budget Invariance**:
  - Budget before: 36.
  - Budget after: 36.
  - Exactly 0 new Serper calls incurred (`SERPER_MODE=cache_only` verified).
- **Visual Contact Sheet**:
  - Generated at `$env:TEMP\bp-refactor-baseline\contact-sheet-step15.html` (~1.08 MB) showing `ext-1` vs `mkt-step15` across 5 viewports and `user-1` vs `user-step15` across 2 viewports.
