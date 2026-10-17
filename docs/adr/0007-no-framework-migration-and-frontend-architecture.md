# ADR 0007: No Framework Migration and Frontend Architecture

## Status
Accepted

## Context
The project user interface is built with React 19, Vite 8, TypeScript, Tailwind CSS v4, and `@base-ui/react`. The user explicitly constrained the project against framework migrations and requested that the codebase remain conventional, clean, and easily maintainable by a developer who does not write complex React.

## Decision

1. **Stack Invariance**:
   - Retain React 19 + Vite 8 + TypeScript.
   - Do not migrate to Next.js, Remix, Astro, Vue, or Svelte.
   - Use Tailwind CSS v4 with design tokens mapped directly to CSS custom properties (`var(--bg)`, `var(--ink)`, `var(--accent)`, `var(--radius)`).

2. **Modular Component Decomposition**:
   - Decompose monolithic files (`App.tsx` was 854 lines with inlined state, tables, and filters).
   - Component boundaries:
     - `Header.tsx`: Square BP brandmark, status indicators, optional feedback link.
     - `SearchForm.tsx`: Search inputs, "More filters" disclosure, multi-select platform chips, 3-step how-it-works overview.
     - `SearchSummaryBar.tsx`: Compact collapsed sticky search bar when results are active.
     - `StatusStrip.tsx`: Consolidated single-line search metrics, timestamp, and refresh controls.
     - `Toolbar.tsx`: Results count, `/` filter input, provider/remote/employment selectors, clear filters.
     - `ResultsTable.tsx`: Tabular view for desktop/tablet with sortable headers, square monogram tiles, and visited indicators.
     - `ResultsCards.tsx`: Mobile stacked card list for viewports below 768px.
     - `DetailSheet.tsx`: Two-pane right sheet for viewing deep posting details.
     - `ShortcutsModal.tsx`: Keyboard shortcuts help dialog triggered by `?`.

3. **Pure Logic Extraction**:
   Extract business logic out of components into tested TypeScript modules under `frontend/src/lib/`:
   - `normalize.ts`: Job record normalization and display formatting.
   - `filter.ts`: Pure filtering algorithms.
   - `sort.ts`: Pure multi-field sorting algorithms.
   - `visited.ts`: Visited URL tracking with localStorage wrapper.
   - `storage.ts`: Generic typed persistent storage helper.
   - `mock.ts`: Deterministic mock data provider for local testing and zero-Serper verification.

4. **Mock Data Mode Switch**:
   - Support `?mock=1` (or `?mock=empty`, `?mock=error`, `?mock=slow`) in the URL or via `localStorage.setItem('bp.mock', 'true')` in development mode.
   - Provide realistic fixtures with 150+ listings, long titles, non-Latin (Japanese) scripts, missing values, and diverse work models.
   - Never activate mock mode in production builds unless explicitly flagged.

## Consequences
- The frontend codebase becomes modular, predictable, and approachable.
- All core business logic is covered by fast, automated unit tests.
- UI components focus purely on rendering and event dispatching.
