# ADR 0019: Table Layout with Fixed Column Alignment Over Two-Line List Rows

## Status
Accepted (Supersedes ADR 0012)

## Context
ADR 0012 replaced desktop tables with a unified responsive two-line list row (`<JobRow>`). While this simplified markup, in practice it caused significant information scannability regressions:
- Column headers (Role, Company, Salary, Posted) did not line up with the free-flowing flex items in the row content.
- Metadata elements (work model, relative date, platform slug) landed at erratic horizontal positions across adjacent rows depending on company name length, making columnar scanning impossible.
- The company monogram sat on line 2 underneath the title instead of anchoring the lead of the row.
- Platform slugs used uppercase DM Mono (`UPPERCASE_SLUG`), which violated the typography ban on aggressive monospace and uppercase text.

## Decision
1. **Desktop / Tablet (>=768px): Semantic Fixed-Layout Table**:
   - Reintroduce a semantic `<table>` with `table-layout: fixed; width: 100%` and strict `<colgroup>` definitions:
     - `Role`: Flexible (`min-width: 260px`, `w-auto`). Clamped to 2 lines with a native Tooltip showing the full title. Stretched row link with hover micro-indicator (`↗`).
     - `Company`: Fixed `240px`. Line 1 has a leading square 28px monogram tile (`w-7 h-7`) plus company name in font-weight 500. Line 2 has the platform slug in lowercase muted mono (`text-xs font-mono lowercase text-[var(--ink-muted)]`).
     - `Location`: Fixed `220px`. Muted location text clamped to 1 line with tooltip.
     - `Salary`: Fixed `130px`. Rendered conditionally: included in `<colgroup>`, `<thead>`, and `<tbody>` only when at least one job in the current result set reports compensation.
     - `Work Model`: Fixed `120px`. Displays remote/hybrid/in-person badges with subtle neutral indicators. Rendered completely empty when unknown (never an artificial `—` tag).
     - `Posted`: Fixed `100px`. Left-aligned relative date (`Today`, `3d ago`, `Oct 15`) with tabular figures (`font-variant-numeric: tabular-nums`) and exact datetime tooltip.
2. **Column Alignment Guarantee**:
   - Both `<th>` and `<td>` cells use identical padding (`py-3.5 px-3.5` / `14px`), guaranteeing that header labels and cell contents align to the exact pixel.
   - Header labels are sentence-case muted 12-13px with 1px bottom border and subtle sort indicators.
3. **Mobile (<768px): Structured Stacked Cards**:
   - For viewports below 768px (`md`), render responsive stacked cards (`ResultsCards.tsx`) adhering to the same spacing scale, with title, company, location, badges, and relative date clearly demarcated.
4. **Interactive States & Green Budget**:
   - Row hover: subtle background tint (`var(--surface-hover)`) and a 2px forest green bar (`var(--accent)`) on the left border.
   - Row focus: visible high-contrast square outline.
   - Stretched link opens the original posting in a new tab (`rel="noopener noreferrer"`).
   - Entire row is keyboard navigable (`j`/`k` / arrows, `Enter`).

## Consequences
- Headers and row content align perfectly down the entire screen.
- Scannability is restored: engineers can read company monograms, roles, locations, salaries, and dates straight down their respective vertical columns.
- Fully verified by automated Playwright column alignment audits asserting matching horizontal bounding boxes across all rows.
