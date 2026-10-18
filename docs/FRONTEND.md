# Frontend Architecture & Developer Guide (Craft Pass 2)

Welcome to the Bottom Pot frontend! This guide is written for engineers and designers. It explains how the web app is structured after the Craft Pass 2 redesign: shadcn/Base UI foundation, two-line list architecture inspired by brianlovin.com, unified page shell, typography system, and command palette.

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
    ├── index.css                # THE SINGLE SOURCE OF TRUTH: CSS tokens, theme vars, radius: 0
    ├── main.tsx                 # React entry point, imports @fontsource-variable/geist & @fontsource/dm-mono
    ├── App.tsx                  # Top-level state coordinator, theme state, View Transitions, Cmd+K coordinator
    ├── types.ts                 # TypeScript types for jobs, search params, and filters
    │
    ├── components/
    │   ├── Header.tsx           # Square BP mark, single sans wordmark, Cmd+K trigger, theme toggle, help
    │   ├── CommandPalette.tsx   # shadcn Command (cmdk) modal for keyboard-first navigation (⌘K / Ctrl+K)
    │   ├── SearchForm.tsx       # Left-aligned hero, quiet suggestions with wrap balance, Collapsible filters, Brian-style 3-item guide
    │   ├── SearchSummaryBar.tsx # Single quiet summary line ("Role · Last 7d · 6 platforms · 52 postings"), popover telemetry, overflow menu
    │   ├── Toolbar.tsx          # Keyword search with '/' hint, platform/model selects, clean switches for Remote & Salary, clear filters
    │   ├── ResultsTable.tsx     # Brian Lovin 2-line clean list with 2px green hover bar, sort dropdown, accessible table semantics
    │   ├── ResultsCards.tsx     # Mobile 2-line list cards (<768px) with touch targets >= 44px
    │   ├── DetailSheet.tsx      # Accessible side sheet with sentence-case typography, copy link, and direct ATS apply link
    │   ├── States.tsx           # 2-line skeleton rows matching real results anatomy with tabular timer; shadcn Empty for no-results & error
    │   │
    │   └── ui/                  # 23 shadcn primitives (Base UI + Tailwind v4 + CVA)
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
    │       ├── separator.tsx
    │       ├── sheet.tsx
    │       ├── skeleton.tsx
    │       ├── sonner.tsx
    │       └── tooltip.tsx
    │
    └── lib/                     # Pure, tested helper modules
        ├── normalize.ts         # String cleanup, company monograms, safe display-name transforms, empty value ("—") formatting
        ├── sort.ts              # Multi-column table sorting logic
        ├── filter.ts            # Keyword and dropdown filtering across title, company, location
        ├── visited.ts           # Safe localStorage store for dimming visited postings
        ├── storage.ts           # Safe localStorage store for saving/restoring last search
        ├── mock.ts              # Deterministic fixture dataset with edge cases (150+ rows, Japanese, etc.)
        └── __tests__/           # Vitest unit test suite (25 tests passing)
```

---

## 2. Component Architecture: shadcn / Base UI Primitives

All UI components in Bottom Pot are composed from primitives located in `frontend/src/components/ui/`.

| UI Component | shadcn Primitive | Purpose |
| :--- | :--- | :--- |
| `Header` | `Button`, `Kbd`, `Tooltip` | Sticky top navigation, command trigger, theme toggle, help modal trigger |
| `CommandPalette` | `Command`, `Dialog`, `Kbd` | Keyboard command palette (`Cmd+K` / `Ctrl+K`) for quick navigation |
| `SearchForm` | `Input`, `Button`, `Collapsible`, `Badge` | Primary job search form, suggestion pills, expandable advanced filters |
| `SearchSummaryBar` | `Button`, `Popover`, `DropdownMenu` | Sticky collapsed summary bar with popover search metrics and overflow actions |
| `Toolbar` | `Input`, `Kbd`, `Button` | Results filtering, text filter, platform/work-model selects, remote/salary toggles |
| `ResultsTable` | `Tooltip` | Desktop two-line job list with 2px accent hover indicator, company monogram tiles |
| `ResultsCards` | `Badge` | Mobile two-line job list cards for narrow screens (<768px) |
| `DetailSheet` | `Sheet`, `Button`, `Badge` | Side sheet sliding panel inspecting job description and source evidence |
| `States` | `Skeleton`, `Empty`, `Button` | Skeleton loading state with matching row anatomy, empty state, error state |

---

## 3. Where to Change Colors, Fonts, Spacing, and Tokens

**Rule**: All tokens are declared in `frontend/src/index.css`. Never use ad-hoc hex values or unscaled arbitrary pixel values in components.

### Colors and Theme Modes
In `frontend/src/index.css`:
- **Light Theme (`:root`)**:
  - Background: `--bg: #FAF8F5;` (warm editorial cream)
  - Surface: `--surface: #FFFFFF;`
  - High ink: `--ink: #181816;`
  - Muted ink: `--ink-muted: #4A4943;` (meets WCAG AA contrast > 7:1)
  - Subtle ink: `--ink-subtle: #5A5952;` (meets WCAG AA contrast 6.7:1)
  - Deep green accent: `--accent: #1A382B;`
- **Dark Theme (`.dark`)**:
  - Background: `--bg: #0C0D0C;` (deep quiet carbon)
  - Surface: `--surface: #151615;`
  - High ink: `--ink: #F2F1ED;`
  - Muted ink: `--ink-muted: #B8B5AC;`
  - Subtle ink: `--ink-subtle: #98968E;` (meets WCAG AA contrast 6.3:1)
  - Tuned green accent: `--accent: #2E7D52;` (lightened for dark contrast)

### Geometry: Square Everywhere
- `--radius: 0rem` is enforced globally. No rounded corners, pills, or circular avatars.

### Typography System
- Primary UI & Headings: **Geist Variable** (`--font-sans: 'Geist Variable', -apple-system, sans-serif;`)
- Tabular Numbers & Codes: **DM Mono** (`--font-mono: 'DM Mono', monospace;`) with `font-variant-numeric: tabular-nums;`
- Scales: `text-display` (28–36px), `text-title` (20–24px), `text-lead` (16–18px), `text-body` (14–15px), `text-small` (13px), `text-caption` (12px), `text-data` (monospace).

### Unified Page Shell
- `--page-max: 960px`
- Every view (header wordmark, landing hero, search form, search summary bar, filter toolbar, job listings, loading skeleton, footer) shares the `.page-shell` container so left edges align perfectly and layouts never jump when transitioning.

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
3. In `frontend/src/components/Toolbar.tsx`: add a compact `<select>` or toggle button styled with `border border-[var(--border)] h-8 text-small`.
4. In `tests/e2e/bottom-pot.spec.js`: add a test asserting that filtering correctly reduces the displayed row count.

---

## 6. How to Run Mock Data Mode

Mock mode runs completely client-side without making external Serper calls or consuming credits.
- Query parameter: `http://127.0.0.1:8000/?mock=1`
- Presets:
  - `?mock=1&state=empty` — Inspect empty results state
  - `?mock=1&state=error` — Inspect server error state
  - `?mock=1&state=slow` — Inspect skeleton loading state

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
