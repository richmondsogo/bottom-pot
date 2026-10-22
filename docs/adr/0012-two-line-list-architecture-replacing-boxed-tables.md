# ADR 0012: Two-Line List Architecture Replacing Boxed Tables

## Status
Accepted

## Context
Pass 1 used an HTML `<table>` on desktop and separate card components on mobile. The table had significant defects:
- Filled beige header bands in uppercase mono.
- Role titles truncated aggressively while Company columns ballooned.
- Unknown work models rendered strange "■ —" tags.
- Maintaining two parallel DOM structures (table on desktop, card list on mobile) led to synchronization bugs and layout reflows.

## Decision
1. Replace both table and mobile cards with a single responsive **two-line list row architecture** (`<JobRow>`) wrapped in accessible list markup (`role="list"`, `role="listitem"`).
2. Row Anatomy:
   - **Left / Main Column**:
     - Line 1: Job title (weight 500, primary ink, stretched anchor link `target="_blank"` `rel="noopener noreferrer"`, hover micro-indicator `↗`). Dimmed title for visited rows.
     - Line 2: Monogram icon (square 18x18) + Company name + `·` + Location (muted ink).
   - **Right / Metadata Column**:
     - Work model badge (only rendered if known; `remote`, `hybrid`, `in_person` with subtle colored square dot).
     - Salary badge (only rendered if compensation is present).
     - Relative date (`Today`, `3d ago`, `Oct 15`) with `<time datetime="...">` and exact date in Tooltip.
     - Platform slug (muted DM Mono).
3. Hairline Dividers: 1px divider with low alpha; no zebra striping; no filled header bands.
4. Hover & Focus States:
   - Subtle background shift (`var(--surface-hover)`).
   - 2px forest green bar (`var(--accent)`) on the left border.
   - High-contrast square outline for keyboard focus.
5. Unified Layout: The same list anatomy renders on desktop (1920px) down to mobile (390px) without switching markup. Sorting is controlled via a dedicated Sort dropdown (`Newest`, `Role`, `Company`).

## Consequences
- Single, maintainable layout code path.
- Cleaner editorial aesthetic adhering directly to brianlovin.com lists.
- Full screen real estate utilized efficiently without horizontal scrolling or truncation artifacts.
