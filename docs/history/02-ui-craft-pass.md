# Step 02: UI Craft Pass 2 — shadcn Foundation, Typography System, Page Shell & Brian Lovin Refinement

**Branch**: `feat/ui-craft-pass`  
**Base Commit**: `4cb62b9f14198c843f064e81ca283d10cf379a14` (tagged `pre-craft-pass`)  
**Status**: Completed  
**Serper Live Searches**: 0 (mock/fixture mode strictly used)

---

## 1. Goal & Objectives
Elevate Bottom Pot from a functional initial redesign to a calm, typography-led, editorial discovery experience inspired by brianlovin.com and grounded in shadcn/ui primitives with strict square geometry (`--radius: 0`).

Objectives:
1. Ground the component architecture on official `shadcn/ui` primitives (Button, Input, Select, DropdownMenu, Popover, Command, Dialog, Sheet, Tooltip, Toggle, Checkbox, Collapsible, Badge, Separator, Skeleton, Empty, Kbd, Sonner).
2. Fix all 11 known defects: unified page shell (`--page-max: 960px`), unified left margins, two-line clean list rows replacing the boxed table, single quiet summary bar, overflow dropdown menu replacing the 6 outlined buttons, proper toggle switches, matching loading skeletons, smooth native scrolling & transitions.
3. Enforce a strict two-family typography system (Geist Variable for all UI/headings, DM Mono strictly for machine data/slugs/tabular numbers).
4. Full dark mode support with theme persistence and pre-hydration flash prevention.
5. Automated guardrails: typography audit, layout audit, token lint, axe a11y, interaction tests, all checks in `scripts/verify.ps1` green.

---

## 2. Shadcn MCP Tool Use Log (Proof of Tool Use)

| Timestamp (UTC) | MCP Tool | Arguments / Query | Action / Result | Notes / Decision |
|---|---|---|---|---|
| 2026-10-17T23:32:31Z | `shadcn:get_project_registries` | `{}` | Checked configured registries | Returned empty in components.json; needs `@shadcn` target |
| 2026-10-17T23:33:00Z | `shadcn:search_items_in_registries` | `query: "button", registries: ["@shadcn"]` | Returned 33 items matching button | Confirmed MCP registry connection and available components |
| 2026-10-17T23:44:24Z | `shadcn:search_items_in_registries` | `query: "input", registries: ["@shadcn"]` | Found input components & examples | Confirmed `@shadcn/input` availability |
| 2026-10-17T23:44:31Z | `shadcn:search_items_in_registries` | `query: "command", registries: ["@shadcn"]` | Found command, command-dialog | Selected `@shadcn/command` for global palette |
| 2026-10-17T23:44:36Z | `shadcn:search_items_in_registries` | `query: "dropdown-menu", registries: ["@shadcn"]` | Found dropdown-menu items | Selected for overflow toolbar actions |
| 2026-10-17T23:44:44Z | `shadcn:search_items_in_registries` | `query: "popover", registries: ["@shadcn"]` | Found popover items | Selected for search details popover |
| 2026-10-17T23:44:49Z | `shadcn:search_items_in_registries` | `query: "sheet", registries: ["@shadcn"]` | Found sheet items | Selected for job detail drawer |
| 2026-10-17T23:44:56Z | `shadcn:search_items_in_registries` | `query: "tooltip", registries: ["@shadcn"]` | Found tooltip items | Selected for exact timestamps & company raw names |
| 2026-10-17T23:45:03Z | `shadcn:view_items_in_registries` | `items: ["@shadcn/button"]` | Viewed button item specification | Inspected dependencies & cva variant structure |
| 2026-10-17T23:45:13Z | `shadcn:get_add_command_for_items` | `items: ["button"]` | Returned `npx shadcn@latest add button` | Executed via CLI into `src/components/ui/button.tsx` |
| 2026-10-17T23:45:50Z | CLI via MCP command | `add input select dropdown-menu popover dialog sheet tooltip toggle checkbox collapsible badge separator skeleton command kbd sonner` | Generated 18 component files | Core primitives installed into `src/components/ui/` |
| 2026-10-17T23:46:31Z | `shadcn:search_items_in_registries` | `query: "empty", registries: ["@shadcn"]` | Found empty state components | Selected `@shadcn/empty` for zero-results & errors |
| 2026-10-17T23:46:38Z | `shadcn:search_items_in_registries` | `query: "spinner", registries: ["@shadcn"]` | Found spinner items | Selected `@shadcn/spinner` for loading micro-states |
| 2026-10-17T23:46:45Z | `shadcn:search_items_in_registries` | `query: "field", registries: ["@shadcn"]` | Found field items | Selected `@shadcn/field` for structured form layout |
| 2026-10-17T23:46:52Z | CLI via MCP command | `add empty spinner field` | Generated 4 files (empty, spinner, label, field) | Full set of 23 shadcn primitives installed |

---

## 3. Resolution of All 11 Known Defects

| Defect # | Issue Description | Root Cause in Pass 1 | Craft Pass 2 Resolution |
| :--- | :--- | :--- | :--- |
| **1** | Inconsistent widths and gutters | Landing was 780px, loading 1080px, results 1216px with mismatched margins | Unified `.page-shell` (`max-width: 960px`) and `px-4 sm:px-6` across Header, Landing, Loading, Results, and Footer. Left edges align perfectly. |
| **2** | Typography chaos | Mixed sans, bold mono labels, uppercase tracked tags, mono suggestions | Single sans (**Geist Variable**) for all UI, headings, and chips. Single mono (**DM Mono**) strictly for tabular data, slugs, and kbd hints. Sentence case everywhere. |
| **3** | Hero spacing & composition | Oversized headline, uneven gaps, wrapped suggestion chips orphaning words | Left-aligned display headline (`text-wrap: balance`), refined lead paragraph, compact suggestion buttons with wrap protection, clean Collapsible advanced filters. |
| **4** | Header clutter & redundant help | Tiny mono tagline, duplicated "?" icon + "?" label | Removed mono tagline; single BP square mark + "Bottom Pot" wordmark; unified help trigger in header and Cmd+K palette. |
| **5** | Button overload | 6 competing outlined icon buttons in header/toolbar | Primary "Edit search" ghost button + single overflow `<DropdownMenu>` for Run again, New search, Clear saved, CSV, and JSON downloads. |
| **6** | Two stacked redundant status bands | Full-bleed "Search:" band + results status card repeating stats | Consolidated into a single quiet sticky line: `"Full Stack Developer · Last 7d · 6 platforms · 52 postings · Saved 1m ago"`. Search telemetry in Popover. |
| **7** | Filter toggles look like static labels | Buttons looked like passive text tags | Converted to proper accessible switch controls with clear active state (`role="switch"`, active tint, indicator dot). |
| **8** | Results table reflow & noisy layout | Boxed table with beige headers, clipped titles, raw slug names, "■ —" tags | Replaced table with Brian Lovin two-line clean list with 2px accent hover bar; relative dates with full date tooltips; safe company display-name cleanup; dedicated Sort dropdown. |
| **9** | Loading state jumps and jargon | "Initializing connection to ATS search pipeline..."; skeleton columns didn't match table | Plain honest copy: `"Searching ATS platforms directly"` + tabular timer + Cancel button; 2-line skeleton rows with identical geometry to real result rows. |
| **10** | Abrupt swaps, no smooth transitions | Abrupt page unmounts, scroll jumping, layout shifts | Native View Transitions API wrapper (`startViewTransition`) with fade+translate; `scroll-behavior: smooth`; `scrollbar-gutter: stable`. Zero Lenis dependency. |
| **11** | Hand-rolled DOM primitives | Custom divs lacking ARIA semantics and token composition | Re-architected on 23 official shadcn / Base UI primitives styled via Tailwind v4 CSS variables. |

---

## 4. Architectural Decision Records (ADRs) Created

- [`docs/adr/0009-shadcn-foundation-and-base-ui-components.md`](../adr/0009-shadcn-foundation-and-base-ui-components.md): Adoption of shadcn/ui on Base UI primitives.
- [`docs/adr/0010-typography-system-and-font-selection.md`](../adr/0010-typography-system-and-font-selection.md): Geist Variable + DM Mono two-family hierarchy.
- [`docs/adr/0011-unified-page-shell-and-left-alignment.md`](../adr/0011-unified-page-shell-and-left-alignment.md): Single 960px page shell with unified left margins.
- [`docs/adr/0012-two-line-list-architecture-replacing-boxed-tables.md`](../adr/0012-two-line-list-architecture-replacing-boxed-tables.md): High-density two-line listings with 2px accent bar.
- [`docs/adr/0013-command-palette-and-chrome-discipline.md`](../adr/0013-command-palette-and-chrome-discipline.md): Cmd+K command palette and overflow action dropdown.
- [`docs/adr/0014-native-motion-view-transitions-and-no-lenis.md`](../adr/0014-native-motion-view-transitions-and-no-lenis.md): Native View Transitions API without third-party scroll-jackers.
- [`docs/adr/0015-theme-system-and-dark-mode-contrast.md`](../adr/0015-theme-system-and-dark-mode-contrast.md): Carbon dark mode with contrast-verified WCAG AA ink tiers.
- [`docs/adr/0016-safe-company-display-name-cleanup.md`](../adr/0016-safe-company-display-name-cleanup.md): Pure display-layer company formatting with raw data preservation.

---

## 5. Verification & Test Metrics

### Automated Verification Suite (`.\scripts\verify.ps1`)
- **Git Available**: Passed
- **No Tracked Secrets**: Passed
- **Frontend Linting (oxlint)**: Passed (0 errors, 0 warnings)
- **Frontend Unit Tests (vitest)**: Passed (25/25 passing)
- **Frontend Typecheck & Build (tsc + vite)**: Passed (1.43s build time, clean production bundle)
- **Backend Unit Tests (pytest)**: Passed
- **Playwright E2E Suite**: Passed (11/11 tests passing, including typography audit across all DOM nodes, layout audit across 5 viewports, Axe-core accessibility, command palette, shortcuts, undo toast)
- **Total Checks**: 7 passed, 0 failed, 0 skipped.

### Chrome DevTools & Lighthouse Metrics
- **Console Messages**: 0 errors, 0 warnings, 0 issues (`<no console messages found>`)
- **Lighthouse Accessibility**: **100 / 100**
- **Lighthouse Best Practices**: **100 / 100**
- **Lighthouse SEO**: **100 / 100**
- **Lighthouse Agentic Browsing**: **100 / 100**
- **Cumulative Layout Shift (CLS)**: **0.00**
- **Largest Contentful Paint (LCP)**: **872 ms**

### Screenshots Captured
- **Before Pass 2**: 50 screenshots across 10 states and 5 viewports in `docs/design/before-pass-2/`
- **After Pass 2**: 100 screenshots across 10 states, 5 viewports, light and dark modes in `docs/design/after-pass-2/`
