# Frontend Architecture & Developer Guide

Welcome to the Bottom Pot frontend! This guide explains how the React/Vite + TypeScript UI under `frontend/` is structured across public editorial routes, the candidate search workspace, admin telemetry mode, client-side state, and verification commands.

Visual rules, soft-square radius tokens, typography scale, and `.page-shell` layout metrics live in [`DESIGN.md`](../DESIGN.md) and [`frontend/src/index.css`](../frontend/src/index.css).

---

## 1. How the Frontend Is Organized

The entire frontend lives inside `frontend/` (`package.json` includes React, Vite, TypeScript, Tailwind CSS v4, `@base-ui/react`, `cmdk`, `sonner`, `lucide-react`, `motion`, `react-markdown`, `rehype-sanitize`, `remark-gfm`, `next-themes`, and `class-variance-authority`):

- `frontend/index.html` & `frontend/src/main.tsx`: Pre-hydration dark/light theme script, React entrypoint, and self-hosted `@fontsource-variable/geist` + `@fontsource/dm-mono` imports.
- `frontend/src/index.css`: Single source of truth for CSS theme variables, soft-square radius scale (`--radius-sm` / `--radius-md` / `--radius-lg`), typography scale, `@layer base`, motion durations, and `.page-shell`.
- `frontend/src/App.tsx` & `frontend/src/types.ts`: Multi-page SPA router (`resolveRoute`), progressive SSE search lifecycle, theme state, view transitions, and shared TypeScript contracts.
- `frontend/src/pages/`: Dedicated editorial routes (`HomePage.tsx` at `/` with desktop-centered / mobile-left-aligned hero and embedded `SearchForm`, plus `ProductPage.tsx` at `/product`, `SourcesPage.tsx` at `/sources`, and `AboutPage.tsx` at `/about`).
- `frontend/src/components/`: Core application UI:
  - `Header.tsx` & `Footer.tsx`: Sticky route navigation with `BottomPotLogo` (`LogoSymbol` + `"Bottom Pot"`), bordered active route indicator, contextual `"Open search"` on editorial subpages, and 3-column footer with Logo.dev attribution.
  - `Workspace.tsx`, `AdminLogin.tsx`, & `TelemetryDeck.tsx`: Candidate/admin search workspace (`/app`, `/admin`), admin cookie authentication gate, and admin-only search telemetry summary.
  - `SearchForm.tsx` & `CountryCombobox.tsx`: Framed 2-row desktop / 4-row mobile search composer built on `PromptInput` (`prompt-kit`) with country selector, expandable `Filters` drawer, and `/app` pre-search `Recent searches` strip.
  - `CompactSearchBar.tsx` & `Toolbar.tsx`: Sticky search summary header (rendering the concise `<N> open roles` / `<N> roles · <query>` / `<N> saved roles` and filtered `<F> of <N> ...` summary on both desktop and mobile in user mode, while folding secondary actions into the overflow menu and hiding scope notes on mobile) above the desktop/mobile filter toolbar.
  - `ResultsTable.tsx`, `ResultsCards.tsx`, & `CompanyMark.tsx`: Fixed-layout desktop `<table>` (square `0px` table/rows with conditional `Salary` column and 2px green hover bar), flat hairline-separated 4-line mobile rows (`<768px`), and `CompanyMark` (`4px` softly rounded API / Logo.dev / initials monogram tiles).
  - `DetailSheet.tsx`: Lazy-loaded edge-attached square side reader (`role="dialog"`) opened by row click, showing sanitized Markdown preview, 4-stage shortlist selector, optional issue report link, and `"Open application"` external link.
  - `CommandPalette.tsx`, `ShortcutsModal.tsx`, `BottomPotEasterEgg.tsx`, & `States.tsx`: Admin-only `Cmd+K` / `Ctrl+K` command palette (`mode === 'admin'`), keyboard shortcuts dialog, lazy-loaded Easter egg canvas, and fixed-width loading skeleton / empty / error states.
- `frontend/src/components/ui/`: shadcn / Base UI (`base-nova`) primitives (`badge`, `button`, `checkbox`, `collapsible`, `command`, `dialog`, `dropdown-menu`, `empty`, `field`, `hover-card`, `input`, `input-group`, `kbd`, `label`, `pointer`, `popover`, `select`, `separator`, `sonner`, `textarea`, `tooltip`).
- `frontend/src/components/prompt-kit/`: Prompt-kit composer primitives (`prompt-input.tsx` and supporting message/tool primitives) used by `SearchForm`.
- `frontend/src/lib/`: Pure helper modules covering API base/admin auth (`apiBase.ts`, `adminAuth.ts`), routing and URL state (`router.ts`, `urlState.ts`), persistence (`storage.ts`, `platformMigration.ts`, `savedJobs.ts`, `visited.ts`), normalization/logos/countries/sources (`normalize.ts`, `logo.ts`, `countries.ts`, `constants.ts`, `nigerianPlatforms.ts`, `identity.ts`, `mobileCardMeta.ts`, `reportLink.ts`, `utils.ts`, `viewTransition.ts`), freshness/eligibility (`freshness.ts`, `eligibility.ts`, `legacyEligibilityFallback.ts`), filtering/sorting/export (`filter.ts`, `sort.ts`, `export.ts`), and offline mock fixtures (`mock.ts`).
- `frontend/src/lib/__tests__/`: Vitest unit and component test suite (`npm --prefix frontend run test`).

---

## 2. Component Architecture: shadcn / Base UI Primitives

All UI components in Bottom Pot are composed from primitives located in `frontend/src/components/ui/`.

| UI Component | shadcn Primitive | Purpose |
| :--- | :--- | :--- |
| `Header` | `Button`, `DropdownMenu`, `Kbd` | Sticky top navigation with `LogoSymbol`, bordered active route indicator, contextual `Open search`, theme & help triggers |
| `Footer` | Native HTML + `LogoSymbol` | Editorial 3-column footer with `/app`, `/product`, `/sources`, `/about`, and Logo.dev attribution |
| `CommandPalette` | `Command`, `Dialog`, `Kbd` | Admin-mode only (`mode === 'admin'`) keyboard command palette (`Cmd+K` / `Ctrl+K`) |
| `SearchForm` | `PromptInput`, `CountryCombobox`, `Select`, `Collapsible`, `Button`, `Badge` | 2-row desktop (Role + Country over Work model / Filters / Search jobs) and 4-row mobile composer + `/app` recent searches |
| `CompactSearchBar` | `Input`, `Select`, `Popover`, `DropdownMenu` | Sticky summary bar rendering concise user-mode counts (`<N> open roles`, `<N> roles · <query>`, `<N> saved roles`, plus `<F> of <N> ...`) on both desktop and mobile, with immediate `New search`, collapsible `Edit search`, and mobile overflow actions |
| `Toolbar` | `Input`, `Kbd`, `Button`, `Select`, `Popover` | 36px desktop bar; 2-row mobile bar (Row 1 filter + `Filters`, Row 2 horizontal Country/Work model/Saved strip) |
| `ResultsTable` | Memoized `<table>` rows | Desktop fixed-layout `<table>` with explicit `<col>` widths, theme-aware monogram tiles, 2px green hover bar |
| `ResultsCards` | Flat 4-line mobile rows | Hairline-separated rows (<768px) with Company+age+quick-save, title, salary line, and deduplicated metadata |
| `DetailSheet` | Side sheet (`role="dialog"`) | Side reader with sanitized Markdown preview, shortlist stage pipeline, and source evidence |
| `ShortcutsModal` | Dialog (`role="dialog"`) + `Kbd` | Accessible keyboard shortcuts reference modal (`?` / `Esc`) |
| `States` | `Empty`, `Button` | Table skeleton with matching column widths, tabular timer, and clean empty/error states |

---

## 3. Where to Change Colors, Fonts, Spacing, and Tokens

**Rule**: All tokens are declared in `frontend/src/index.css` (using `@custom-variant dark (&:where(.dark, .dark *));` so `dark:` follows `.dark` on `<html>`, never OS `prefers-color-scheme`). Never use ad-hoc hex values or hardcoded `dark:` color overrides in components.

### CSS Cascade & Layer Rules (MANDATORY)
- All base element resets (`*`, `html`, `body`, `button`, `input`, `select`, `textarea`) MUST live inside `@layer base`.
- Universal `* { margin: 0; padding: 0 }` is STRICTLY FORBIDDEN as it overrides Tailwind `@layer utilities` regardless of class specificity.
- Enforced by `node scripts/lint_css_cascade.js` in `scripts/verify.ps1`.

### Colors and Theme Modes
In `frontend/src/index.css`:
- **Light Theme (`:root`)**:
  - Background: `--bg: #FAF8F5;` (warm editorial cream)
  - Surface: `--surface: #FFFFFF;`
  - High ink: `--ink: #181816;`
  - Muted ink: `--ink-muted: #57564F;` (meets WCAG AA contrast)
  - Subtle ink: `--ink-subtle: #5A5952;` (meets WCAG AA contrast 6.7:1)
  - Deep green accent: `--accent: #1A382B;`
- **Dark Theme (`.dark`)**:
  - Background: `--bg: #0C0D0C;` (deep quiet carbon)
  - Surface: `--surface: #141614;`
  - High ink: `--ink: #EDEDEA;`
  - Muted ink: `--ink-muted: #A3A29B;`
  - Subtle ink: `--ink-subtle: #98968E;` (meets WCAG AA contrast 6.3:1)
  - Tuned green accent: `--accent: #2E7D52;` (lightened for dark contrast)

### Geometry, Typography & Page Shell
Visual design tokens are owned by [`DESIGN.md`](../DESIGN.md) and defined in [`frontend/src/index.css`](../frontend/src/index.css):
- **Soft-square radius scale (`ADR 0036`):** `--radius-sm` (`4px` — badges, tags, `CompanyMark`, `<kbd>` hints, menu items), `--radius-md` (`6px` — buttons, inputs, selects, comboboxes, chips, toolbar pills), `--radius-lg` (`8px` — search card, popovers, dropdowns, command palette, dialogs, `DetailSheet` inner cards/actions), while results table (`table`/`tr`/`td`, hover bar), hairlines, flat mobile rows, and the edge-attached `DetailSheet` panel stay `0px`.
- **Typography & page shell:** Self-hosted `Geist Variable` (`--font-sans`) and `DM Mono` (`--font-mono`, `tabular-nums`), type scale tokens (`--text-display` through `--text-data`), and the `.page-shell` container (`--page-max`, responsive `--page-gutter`, `scrollbar-gutter: stable`) are all read from [`frontend/src/index.css`](../frontend/src/index.css) and specified in [`DESIGN.md`](../DESIGN.md).

---

## 4. Client State, Persistence & Sorting (`frontend/src/lib/`)

### URL State & Workspace Entry (`urlState.ts`, `router.ts`)
- **Routes:** `/`, `/app`, `/product`, `/sources`, `/about`, `/admin` (query-driven workspace entry parameters `view`, `role`, `k`, `q`, `saved`, and `mock` also resolve into `/app` workspace behavior). Opening `/app?q=...` auto-runs the search.
- **Shareable workspace query params (`urlState.ts`):** `q` (keywords), `loc` (location), `wm` (work model), `age` (post age days), `ng` (`0`/`1` Nigerian boards toggle), `cc` (applicant country ISO-2 code), `elig` (`eligible_and_unknown` | `eligible` | `unknown` | `restricted`), `flt` (table filter text), `prov` (provider filter), `rem` (remote filter), `emp` (employment filter), `sal` (`1` for salary-only), `saved` (`1` for saved-only).

### `localStorage` Keys by Prefix & Purpose
All keys live under the `bp.` namespace (`storage.ts`, `urlState.ts`, `savedJobs.ts`, `platformMigration.ts`, `visited.ts`, `mock.ts`, `App.tsx`):
- `bp.theme`: Active UI theme (`light` / `dark`).
- `bp.searchParams`, `bp.applicantCountry`: Last submitted form parameters and selected applicant country.
- `bp.selectedPlatforms` + `bp.platforms.version`: Selected ATS/board platform IDs with versioned migration preserving custom user subsets and empty selections.
- `bp.filter.*` (`search`, `provider`, `remote`, `employment`, `eligibility`, `salaryOnly`) and `bp.sort.*` (`field`, `asc`): Workspace toolbar filters and active column sort.
- `bp.savedResults`: Cached last search results for reload recovery (capped at `3 MB` with an undo action when cleared).
- `bp.shortlist.v1` (`savedJobs.ts`): Persistent user shortlist keyed by job identity/aliases across four stages (`saved`, `applied`, `interviewing`, `archived`).
- `bp.recentSearches.v1` (`urlState.ts`): Up to `5` deduplicated recent search presets rendered on `/app` pre-search.
- `bp.visited` (`visited.ts`): Tracked clicked posting URLs (capped at `1,000` entries) used to dim visited rows.
- `bp.mock` (`mock.ts`): Client mock toggle, active only in Vite `DEV` builds or when `VITE_ENABLE_MOCK=true` (or `?mock=...`).

### Structured Salary Sorting (`sort.ts`)
- Default order (`field` unset) sorts by `freshnessTier` so postings <= 90 days precede `"Older postings"` (`stale`).
- When sorting explicitly by `salary`, `sort.ts` groups records with structured salary objects by `currency:period`, picks the highest-frequency `currency:period` group (ties broken by first seen), and sorts only that dominant group numerically (`minimum`, falling back to `maximum`) without performing cross-currency conversion. Postings in other currencies/periods, legacy unparsed string salaries, and missing salaries remain after the dominant group in stable order.

---

## 5. How to Add an Admin Command (`CommandPalette.tsx`)

`CommandPalette` is rendered only in admin mode (`mode === 'admin'`, triggered via `Cmd+K` / `Ctrl+K`):

1. Open `frontend/src/components/CommandPalette.tsx`.
2. Locate the relevant `<CommandGroup>` (e.g., "Actions", "Preferences", or "Navigation").
3. Add a new `<CommandItem>`:
   ```tsx
   <CommandItem
     onSelect={() => {
       runAction(() => {
         // Your logic here (e.g., window.open(...), state setter)
       });
     }}
   >
     <YourIcon className="mr-2 size-4 text-[var(--ink-muted)]" />
     <span>Action Label</span>
     <Kbd className="ml-auto">⌘Shift+X</Kbd>
   </CommandItem>
   ```

---

## 6. How to Add a New Filter

To add a new filter (e.g. "Seniority Level"):
1. In `frontend/src/types.ts`: add `seniority?: string` to `SearchParams` or filter state.
2. In `frontend/src/lib/filter.ts`: add the filtering predicate.
3. In `frontend/src/components/Toolbar.tsx`: add a styled shadcn/Base UI `Select` (`frontend/src/components/ui/select.tsx`) or toggle `Button` (never expose a raw visible `<select>`, per `DESIGN.md` §5).
4. In `tests/e2e/bottom-pot.spec.js`: add a test asserting that filtering correctly reduces the displayed row count.

---

## 7. How to Run Mock Data Mode

Mock mode runs completely client-side without making external Serper calls or consuming credits.
- Query parameter: `http://127.0.0.1:8000/?mock=1` (in production builds without `?mock=...`, `bp.mock` requires `VITE_ENABLE_MOCK=true`)
- Presets:
  - `?mock=empty` (or `?mock=no_results`, `?mock=0`) : Inspect empty results state
  - `?mock=error` (or `?mock=500`) : Inspect server error state
  - `?mock=slow` : Inspect skeleton loading state

---

## 8. Verification Commands

Run from PowerShell at the repository root:

```powershell
# 1. Full repository verification (Secrets, lint, tests, build, e2e)
.\scripts\verify.ps1

# 2. Frontend unit tests only (vitest)
npm --prefix frontend run test

# 3. Frontend linting only (oxlint)
npm --prefix frontend run lint

# 4. Frontend production build (tsc + vite)
npm --prefix frontend run build

# 5. Playwright E2E suite (accessibility, typography audit, layout audit)
npx playwright test
```
