# Frontend Architecture & Developer Guide

Welcome to the Bottom Pot frontend! This guide is written in plain language for developers, designers, or maintainers who might not be React specialists. It explains how the web app is structured, where to change styles and copy, how to run mock mode, how to add a column or filter, and how to verify your changes.

---

## 1. How the Frontend Is Organized

The entire frontend codebase lives inside the `frontend/` directory.

```
frontend/
├── index.html                   # HTML entry point, meta tags, SVG favicon, title
├── package.json                 # Dependencies and scripts (build, test, lint)
├── vite.config.ts               # Vite bundler configuration
├── tsconfig.json                # TypeScript strict configuration
└── src/
    ├── index.css                # THE SINGLE SOURCE OF TRUTH for design tokens & styles
    ├── main.tsx                 # React DOM mount point
    ├── App.tsx                  # Top-level state coordinator, keyboard shortcuts, SSE stream
    ├── types.ts                 # TypeScript types for jobs, search params, and filters
    │
    ├── components/              # Modular, single-purpose UI components
    │   ├── Header.tsx           # Square BP logo, title, mock badge, shortcut modal trigger
    │   ├── SearchForm.tsx       # Landing search form, "More filters", platform chips, How it works
    │   ├── SearchSummaryBar.tsx # Sticky collapsed bar shown after search ("Data Engineer · Edit search")
    │   ├── StatusStrip.tsx      # Consolidated single-line results stats and search info disclosure
    │   ├── Toolbar.tsx          # Results count, "/" filter input, provider/work-model dropdowns
    │   ├── ResultsTable.tsx     # Desktop table: sortable headers, square monogram tiles, 2-line clamping
    │   ├── ResultsCards.tsx     # Mobile stacked cards (<768px): touch targets >= 44px
    │   ├── DetailSheet.tsx      # Right-side (desktop) / full-screen (mobile) posting inspector
    │   ├── ShortcutsModal.tsx   # Modal explaining keyboard shortcuts (j/k, o, Esc, /, ?)
    │   └── States.tsx           # Honest loading skeleton, no-results state, human error state
    │
    └── lib/                     # Pure, tested JavaScript/TypeScript helper modules
        ├── normalize.ts         # String cleanup, company monograms, empty value ("—") formatting
        ├── sort.ts              # Multi-column table sorting logic
        ├── filter.ts            # Keyword and dropdown filtering across title, company, location
        ├── visited.ts           # Safe localStorage store for tracking read/opened postings
        ├── storage.ts           # Safe localStorage store for saving and restoring last search
        ├── mock.ts              # Deterministic fixture dataset with edge cases (150+ rows, Japanese, etc.)
        └── __tests__/           # Vitest unit test suite (23 tests passing)
```

---

## 2. Where to Change Colors, Fonts, Spacing, and Tokens

**Rule**: All colors, fonts, spacing, and geometry are controlled by CSS Custom Properties in `frontend/src/index.css`. Never write hardcoded hex values or arbitrary pixel margins inside React components.

### Changing Colors
Open `frontend/src/index.css` and locate the `:root` block:
- **Canvas background**: `--bg: #FAF8F5;` (warm editorial cream)
- **Card/table background**: `--surface: #FFFFFF;`
- **Primary text**: `--ink: #181816;`
- **Secondary text**: `--ink-muted: #5C5A53;` (meets WCAG AA contrast)
- **Subtle borders/labels**: `--ink-subtle: #63625B;` (meets WCAG AA contrast > 5.5:1)
- **Brand accent**: `--accent: #1A382B;` (deep forest green)
- **Hairline borders**: `--border: #E6E1D8;`, `--border-strong: #CDC6B9;`

### Square Geometry (Non-Negotiable)
- All corners must stay strictly square:
  ```css
  --radius: 0px;
  ```
  Do not introduce rounded corners, pills, or circular badges.

### Fonts
Bottom Pot uses self-hosted open-source fonts bundled via `@fontsource` (zero external network requests to Google Fonts):
- Primary UI & Headings: **Manrope** (`--font-sans: 'Manrope', -apple-system, sans-serif;`)
- Codes, Timestamps & Numbers: **DM Mono** (`--font-mono: 'DM Mono', monospace;`) with `font-variant-numeric: tabular-nums;`.

---

## 3. Where to Change Copy and Text

- **Landing Headline & Subtitle**: `frontend/src/components/SearchForm.tsx` (Look for `<h1>Find the signal behind the noise.</h1>`).
- **"How it works" 3-Step Guide**: `frontend/src/components/SearchForm.tsx` (in the `how-it-works-grid` section).
- **Consolidated Status Strip**: `frontend/src/components/StatusStrip.tsx` (e.g., `"results from"`, `"Saved"`, `"Run again"`).
- **Loading State Message**: `frontend/src/components/States.tsx` (Look for `Searching 20 applicant tracking systems...`).
- **Empty & Error Messages**: `frontend/src/components/States.tsx` (`NoResultsState` and `ErrorState`).
- **Keyboard Shortcuts Descriptions**: `frontend/src/components/ShortcutsModal.tsx`.

---

## 4. How to Run Mock Data Mode

Mock mode allows you to work on the UI, inspect states, and test responsive layouts **without spending Serper credits or needing an active internet connection**.

### Option A: Query Parameter (Easiest)
Simply append `?mock=1` to the URL in your browser:
```
http://127.0.0.1:8000/?mock=1
```
or when running the Vite dev server:
```
http://localhost:5173/?mock=1
```

### Option B: State Presets in Mock Mode
The mock fixtures include realistic edge cases:
- 150+ realistic tech job postings
- Very long job titles and company names
- Multi-byte non-Latin characters (Japanese postings)
- Missing compensation, location, or work model
- Remote, hybrid, in-person, and unknown work models
- Simulated slow-loading state for inspecting skeletons
- Simulated error state for inspecting error handling

To simulate specific states in mock mode, add the parameter:
- `?mock=1&state=empty` — Inspect the "No results found" state.
- `?mock=1&state=error` — Inspect the error state.
- `?mock=1&state=slow` — Inspect the loading skeleton and elapsed timer.

---

## 5. How to Add a Column to the Table

Follow these steps to add a new column (for example, "Department" or "Date Posted"):

1. **Verify the API Type**:
   Open `frontend/src/types.ts` and ensure the field exists on the `Job` interface:
   ```typescript
   export interface Job {
     // ...
     department?: string | null;
   }
   ```
2. **Add the Table Header**:
   Open `frontend/src/components/ResultsTable.tsx`. In the `<thead>` element, add a new `<th>`:
   ```tsx
   <th scope="col" style={{ width: '150px' }}>Department</th>
   ```
3. **Add the Table Cell**:
   In the same file, locate the `<tbody>` row mapping and add your `<td>`:
   ```tsx
   <td style={{ color: 'var(--ink-muted)' }}>
     {job.department || '—'}
   </td>
   ```
   *(Note: Remember the core principle: "Unknown beats wrong". Missing values must render as an em-dash `"—"`).*
4. **Update Mobile Cards (if applicable)**:
   Open `frontend/src/components/ResultsCards.tsx` and display the field inside the card layout if it should appear on mobile screens.

---

## 6. How to Add a New Filter

To add a new filter to the Results Toolbar (for example, filter by ATS Provider):

1. **Update Filter State in `App.tsx`**:
   In `frontend/src/App.tsx`, define a state variable:
   ```tsx
   const [selectedDepartment, setSelectedDepartment] = useState<string>('all');
   ```
2. **Add Logic to `filter.ts`**:
   Open `frontend/src/lib/filter.ts` and add your filtering condition:
   ```typescript
   if (department !== 'all' && job.department !== department) {
     return false;
   }
   ```
3. **Add UI Control to `Toolbar.tsx`**:
   Open `frontend/src/components/Toolbar.tsx` and add a `<select>` or button chip styled with `.input` or `.btn`.

---

## 7. How to Run the Tests and Verify

Everything can be verified with single-line commands from PowerShell:

### 1. Run Unit Tests (Fast, ~1.5s)
```powershell
cd frontend
npm test
```
Tests pure utilities (`normalize.ts`, `filter.ts`, `sort.ts`, `visited.ts`, `storage.ts`, `mock.ts`).

### 2. Run Code Linter
```powershell
cd frontend
npm run lint
```
Checks all TypeScript and React files with zero errors and zero warnings.

### 3. Build Production Bundle
```powershell
cd frontend
npm run build
```
Compiles TypeScript and outputs the production bundle to `frontend/dist/`. The backend serves this directory directly on `http://127.0.0.1:8000/`.

### 4. Run End-to-End & Accessibility Tests (Playwright + Axe-Core)
```powershell
npx playwright test
```
Validates the entire user flow (search, filters, sorting, keyboard shortcuts, visited state, detail sheet, mobile layout) and checks WCAG 2.1 AA accessibility with zero serious or critical violations.

### 5. Run Full Project Verification
From the repository root:
```powershell
.\scripts\verify.ps1
```
Executes git checks, secret scan, frontend lint, unit tests, production build, backend pytest, and Playwright e2e tests in one shot.
