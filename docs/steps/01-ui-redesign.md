# Step 01: UI Redesign, Square Design System, and Frontend Craft

**Date**: 2026-10-17  
**Branch**: `feat/ui-redesign` (stacked on `chore/adopt-agent-starter`)  
**Status**: Completed  

---

## 1. Goal
Execute a complete visual redesign and frontend engineering craft overhaul of Bottom Pot. Transform the UI from a "vibecoded" template into an editorial, typography-first, high-density product inspired by the craft of Daybreak, while strictly enforcing the non-negotiable **Square Design System** (`--radius: 0px` everywhere) and preserving 100% of existing functionality with zero backend/API changes.

---

## 2. Architecture & Design Decisions
1. **Square Design System (Non-Negotiable)**: Enforced `--radius: 0` across all cards, buttons, inputs, selects, monogram tiles, tags, tooltips, dialogs, and sheets. See [`docs/adr/0004-square-design-system-and-daybreak-craft.md`](../adr/0004-square-design-system-and-daybreak-craft.md).
2. **Design Tokens as Single Source of Truth**: All colors, fonts, spacing, and transitions defined as CSS custom properties in `frontend/src/index.css`. Zero hardcoded hex colors or arbitrary pixel margins outside the tokens file.
3. **Typography**: Self-hosted Manrope (display/body) and DM Mono (data/timestamps) using `@fontsource`. Preloaded latin woff2 subsets with `font-display: swap`. Zero external Google Fonts network calls.
4. **Daybreak Craft Elements**:
   - Two-pane reading experience (results table + right-side slide-out detail sheet).
   - "Visited" dimming: Postings clicked or opened by the user have their titles dimmed to reduce scanning fatigue, persisted safely in `localStorage`. See [`docs/adr/0005-client-side-visited-state-and-results-persistence.md`](../adr/0005-client-side-visited-state-and-results-persistence.md).
   - Full keyboard navigation: `j`/`k` (navigate rows), `Enter`/`o` (open detail sheet), `Esc` (close), `/` (focus filter), `?` (help modal). See [`docs/adr/0006-results-detail-panel-and-keyboard-navigation.md`](../adr/0006-results-detail-panel-and-keyboard-navigation.md).
5. **No Framework Migration**: Preserved React 19 + TypeScript + Vite. Extracted modular, single-purpose components and pure utility functions. Purged dead legacy files. See [`docs/adr/0007-no-framework-migration-and-frontend-architecture.md`](../adr/0007-no-framework-migration-and-frontend-architecture.md).
6. **Backend API Recommendations**: Proposed non-breaking enhancements for granular SSE platform progress and structured salary payloads in [`docs/adr/0008-backend-api-recommendations-for-frontend-ux.md`](../adr/0008-backend-api-recommendations-for-frontend-ux.md).

---

## 3. The 11 Observed Problems & How Each Was Fixed

| # | Problem Observed | Solution Implemented |
|---|---|---|
| **1** | Too much status chrome before data | Consolidated multiple banners into a single quiet status strip (`StatusStrip.tsx`): e.g. `"143 results from 20 platforms · 1.4s · Saved 1d ago · [Run again] [Clear]"`. Moved Serper calls and cache stats into a subtle expandable "Details" disclosure. Deleted the redundant "Results are ready" banner. |
| **2** | Developer jargon leaking into UI | Removed `GET /search`, `LIVE SEARCH INFRASTRUCTURE`, and raw API verbiage. Replaced with clear, plain language copy. |
| **3** | Uppercase mono eyebrows flattening hierarchy | Restricted uppercase mono to data columns, timestamps, and codes. UI section headings use clean sentence-case sans with natural typographic contrast. |
| **4** | Inconsistent empty values (`"Not listed"`, `"Unknown"`, `"—"`) | Standardized on a muted `"—"` throughout the results table. Auto-hides the salary column when all visible results lack salary data. Full wording reserved for the detail panel. |
| **5** | Circular pastel company avatars breaking square system | Replaced with deterministic `28x28px` square monogram tiles in restrained neutral ink/cream tints. No rainbow circles. |
| **6** | Work-model badges with heavy, inconsistent styling | Replaced with a quiet, square tag system: plain text + 6px square color marker (Remote: deep green, Hybrid: warm amber, In-person: neutral slate). Color is never the sole carrier of meaning. |
| **7** | Card-inside-card nesting & boxed table | Flattened into a single clean container with 1px hairline dividers (`--border: #E6E1D8`). Full-width table within the maximum page container. |
| **8** | Sticky header/filter stacking glitch with blurred remnants | Fixed sticky z-index layering (`--z-header: 10`, `--z-toolbar: 9`, `--z-sheet: 50`) with 100% solid, opaque backgrounds (`--bg` and `--surface`). |
| **9** | Empty decorative gradient blob in hero | Removed completely. Replaced with a flat editorial cream canvas structured by crisp hairline borders and balanced display typography. |
| **10** | Results pushed far below fold | Post-search, the full hero automatically collapses into a slim, sticky 40px search summary bar (`"Data Engineer · Remote · 7 days · [Edit search]"`) so the results table immediately dominates the viewport. |
| **11** | Inconsistent row heights & uncontrolled title wrapping | Clamped job titles to exactly 2 lines (`line-clamp: 2`) with native `title` tooltip displaying full text on hover. Consistent 56px row height with robust support for mixed scripts (Japanese, emojis, punctuation). |

---

## 4. Verification & Quality Metrics

1. **Unit Tests (Vitest)**:
   - 23/23 tests passing in 1.35s across `formatting.test.ts`, `filtering.test.ts`, `sorting.test.ts`, `visitedStore.test.ts`, `savedResultsStore.test.ts`, and `mockMode.test.ts`.
2. **Linter (oxlint)**:
   - 26 files checked: 0 errors, 0 warnings.
3. **Production Build (tsc + vite)**:
   - `tsc -b && vite build` succeeded in 1.45s.
   - Bundle size: JS 288.76 kB (87.24 kB gzipped), CSS 46.31 kB (21.55 kB gzipped), including self-hosted Manrope and DM Mono font subsets.
4. **Playwright E2E & Axe-core Accessibility**:
   - 7/7 automated end-to-end test suites passing in 24.3s.
   - Zero serious or critical WCAG 2.1 AA violations on both desktop and mobile viewports.
5. **Lighthouse Audit (via Chrome DevTools MCP)**:
   - Desktop: Accessibility: **100**, Best Practices: **100**, SEO: **100**, Agentic Browsing: **100**.
   - Mobile: Accessibility: **100**, Best Practices: **100**, SEO: **100**, Agentic Browsing: **100**.
   - Performance Trace: Observed LCP: 515ms, Cumulative Layout Shift (CLS): 0.00.
6. **Console Inspection**:
   - Zero console errors, zero warnings.
7. **Serper Live Queries**:
   - Exact count: **0** live Serper searches executed. All development and verification ran strictly against mock data and fixtures.
8. **Screenshots**:
   - 30 baseline "before" screenshots in `docs/design/before/`.
   - 30 verified "after" screenshots in `docs/design/after/` across 6 states (`landing`, `loading`, `results`, `saved-results`, `no-results`, `error`) and 5 viewports (1920x1080, 1440x900, 1024x768, 768x1024, 390x844).
9. **Full Project Verification Script**:
   - `scripts/verify.ps1` ran cleanly with all 7 checks green.
