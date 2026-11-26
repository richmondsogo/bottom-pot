# Frontend Architecture & Developer Guide (UI Layout Restore)

Welcome to the Bottom Pot frontend! This guide is written for engineers and designers. It explains how the web app is structured following the UI Layout Restoration pass: shadcn/Base UI foundation, centered hero rhythm, framed form card, fixed-layout semantic table, unified 1160px page shell, single-sans typography system, and command palette.

---

## 1. How the Frontend Is Organized

The entire frontend lives inside the `frontend/` directory.

```
frontend/
├── index.html                   # HTML entry point with pre-hydration theme script
├── package.json                 # Dependencies (Base UI, cmdk, sonner, lucide-react)
├── vite.config.ts               # Vite bundler configuration
├── tsconfig.json                # TypeScript strict configuration
└── src/
    ├── index.css                # THE SINGLE SOURCE OF TRUTH: CSS tokens, theme vars, radius: 0, @layer base
    ├── main.tsx                 # React entry point, imports @fontsource-variable/geist & @fontsource/dm-mono
    ├── App.tsx                  # Multi-page router coordinator, progressive SSE handler, theme state, View Transitions
    ├── types.ts                 # TypeScript types for jobs, search params, and filters
    │
    ├── pages/                   # Dedicated editorial pages served cleanly at /, /product, /sources, /about
    │   ├── HomePage.tsx         # Calm editorial overview with direct /app CTA and 13-source summary
    │   ├── ProductPage.tsx      # Two-phase retrieval explanation, guarantees, and keyboard workflow
    │   ├── SourcesPage.tsx      # Live 13-source matrix grouped by retrieval tier with direct search links
    │   └── AboutPage.tsx        # Editorial narrative and five operating rules
    │
    ├── components/
    │   ├── Header.tsx           # LogoSymbol + "Bottom Pot" sans wordmark, square active nav tab, theme & help triggers
    │   ├── Footer.tsx           # Editorial 3-column footer with real multi-page links and Logo.dev attribution
    │   ├── CommandPalette.tsx   # shadcn Command (cmdk) modal for keyboard navigation (⌘K / Ctrl+K)
    │   ├── SearchForm.tsx       # Framed 760px composer with "Where can you work from?", Work model, and collapsible Filters drawer (City or office hub, Posted within, 13 sources)
    │   ├── CompactSearchBar.tsx # Sticky results header with New search, collapsible Edit search, Export dropdown & admin telemetry
    │   ├── Toolbar.tsx          # Single-row filter bar ('/' hint, Work model, CountryCombobox, Eligibility, Saved, More filters) with flush 2-col mobile grid
    │   ├── ResultsTable.tsx     # Semantic fixed-layout <table> with explicit <col> widths (195px Salary), theme-aware square monograms, React.memo rows
    │   ├── ResultsCards.tsx     # Mobile stacked cards (<768px) with tokenized Work & eligibility tags and >= 44px touch targets
    │   ├── DetailSheet.tsx      # Lazy-loaded side reader with sanitized Markdown preview, Save toggle, 4-stage pipeline bar, and ATS apply link
    │   ├── ShortcutsModal.tsx   # Lazy-loaded keyboard shortcuts dialog (j/k, Enter/o, s, /, Ctrl+K, ?, Esc)
    │   ├── BottomPotEasterEgg.tsx # Lazy-loaded "Bottom of the Pot" canvas ember overlay (0 KB in main entry; 5x footer logo click or typing "jollof" on /about)
    │   ├── States.tsx           # Fixed table skeleton matching real results columns with tabular timer; Empty states for no-results & error
    │   │
    │   └── ui/                  # shadcn primitives (Base UI + Tailwind v4 + CVA, radius 0, neutral hover highlights)
    │       ├── badge.tsx
    │       ├── button.tsx
    │       ├── collapsible.tsx
    │       ├── command.tsx
    │       ├── dialog.tsx
    │       ├── dropdown-menu.tsx
    │       ├── empty.tsx
    │       ├── input.tsx
    │       ├── kbd.tsx
    │       ├── popover.tsx
    │       ├── select.tsx
    │       ├── separator.tsx
    │       ├── sonner.tsx
    │       └── tooltip.tsx
    │
    └── lib/                     # Pure, tested helper modules
        ├── apiBase.ts           # Optional VITE_API_BASE_URL + credentials helper (defaults to same-origin "")
        ├── router.ts            # Multi-page URL path resolver and serializer (zero # hash anchors)
        ├── constants.ts         # 13 active platform definitions (10 ATS + 3 Nigerian) and recency options
        ├── normalize.ts         # String cleanup, freshness metadata, safe display-name transforms, null-safe field formatting
        ├── logo.ts              # Safe Logo.dev publishable token validation and fallback=404 URL builder
        ├── freshness.ts         # Canonical freshness tier resolution and age badges (<=30d fresh, <=90d recent, >90d stale)
        ├── eligibility.ts       # Backend-first eligibility display facade with offline fallback
        ├── legacyEligibilityFallback.ts # Isolated offline/cached fallback for records missing backend evaluation
        ├── sort.ts              # Freshness-first default ordering + multi-column explicit sorting
        ├── filter.ts            # Keyword and dropdown filtering across title, company, location
        ├── savedJobs.ts         # Persistent job shortlist & 4-stage application tracker (Saved, Applied, Interviewing, Archived)
        ├── urlState.ts          # Shareable URL query parameter sync (?q, loc, wm, saved) & recent search presets
        ├── export.ts            # CSV and JSON export generators
        ├── visited.ts           # Memoized localStorage store for dimming visited postings
        ├── storage.ts           # Safe localStorage store + CSS-tokenized square monogram palettes (--mono-0-*..--mono-6-*)
        ├── mock.ts              # Deterministic fixture dataset with edge cases (150+ rows, Japanese, etc.)
        └── __tests__/           # Vitest unit test suite (22 files)
```

---

## 2. Component Architecture: shadcn / Base UI Primitives

All UI components in Bottom Pot are composed from primitives located in `frontend/src/components/ui/`.

| UI Component | shadcn Primitive | Purpose |
| :--- | :--- | :--- |
| `Header` | `Button`, `DropdownMenu`, `Kbd` | Sticky top navigation with square `LogoSymbol`, bordered active route indicator, theme & help triggers |
| `Footer` | Native HTML + `LogoSymbol` | Editorial 3-column footer with `/app`, `/product`, `/sources`, `/about`, and Logo.dev attribution |
| `CommandPalette` | `Command`, `Dialog`, `Kbd` | Keyboard command palette (`Cmd+K` / `Ctrl+K`) for quick navigation |
| `SearchForm` | `Input`, `Button`, `Collapsible`, `Badge` | Centered framed search card, `"Where can you work from?"` combobox, Work model + expandable Filters (`City or office hub`, 13 sources) |
| `CompactSearchBar` | `Input`, `Select`, `Popover`, `DropdownMenu` | Sticky summary bar with immediate `New search`, collapsible inline `Edit search`, `Export`, and `More actions` |
| `Toolbar` | `Input`, `Kbd`, `Button`, `Select`, `Popover` | 36px filter bar, text filter with `/` hint, Work model, `CountryCombobox`, Eligibility, `Saved`, `More filters` |
| `ResultsTable` | Memoized `<table>` rows | Desktop fixed-layout `<table>` with explicit `<col>` widths, theme-aware monogram tiles, 2px green hover bar |
| `ResultsCards` | Stacked mobile cards | Mobile cards (<768px) with tokenized work-model badges and touch targets >= 44px |
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

### Geometry: Square Everywhere
- `--radius: 0rem` is enforced globally. No rounded corners, pills, or circular avatars.

### Typography System
- Primary UI & Headings: **Geist Variable** (`--font-sans: 'Geist Variable', -apple-system, sans-serif;`)
- Tabular Numbers & Codes: **DM Mono** (`--font-mono: 'DM Mono', monospace;`) with `font-variant-numeric: tabular-nums;`
- Scales: `text-display` (28–36px), `text-title` (20–24px), `text-lead` (16–18px), `text-body` (14–15px), `text-small` (13px), `text-caption` (12px), `text-data` (monospace).

### Unified Page Shell
- `--page-max: 1160px;`
- `--page-gutter: 32px;`
- `scrollbar-gutter: stable;`
- Every view (header wordmark, landing hero, search form, search summary bar, filter toolbar, job listings, loading skeleton, footer) shares the `.page-shell` container (`max-w-[var(--page-max)] px-4 sm:px-6 lg:px-8`) so left edges align perfectly and layouts never jump when transitioning.

---

## 4. How to Add a Command to the Command Palette

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

## 5. How to Add a New Filter

To add a new filter (e.g. "Seniority Level"):
1. In `frontend/src/types.ts`: add `seniority?: string` to `SearchParams` or filter state.
2. In `frontend/src/lib/filter.ts`: add the filtering predicate.
3. In `frontend/src/components/Toolbar.tsx`: add a styled shadcn/Base UI `Select` (`frontend/src/components/ui/select.tsx`) or toggle `Button` (never expose a raw visible `<select>`, per `DESIGN.md` §5).
4. In `tests/e2e/bottom-pot.spec.js`: add a test asserting that filtering correctly reduces the displayed row count.

---

## 6. How to Run Mock Data Mode

Mock mode runs completely client-side without making external Serper calls or consuming credits.
- Query parameter: `http://127.0.0.1:8000/?mock=1`
- Presets:
  - `?mock=empty` (or `?mock=no_results`, `?mock=0`) : Inspect empty results state
  - `?mock=error` (or `?mock=500`) : Inspect server error state
  - `?mock=slow` : Inspect skeleton loading state

---

## 7. Verification Commands

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
