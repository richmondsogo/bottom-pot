# ADR 0011: Unified Page Shell and Left Alignment

## Status
Accepted

## Context
In pass 1, container widths varied erratically across views:
- Header and results were set to ~1216px.
- Landing search form card was constrained to 780px and centered.
- Loading card expanded to ~1080px.
- The results "Search:" band was full-bleed with 32px gutters that misaligned with the 112px content gutters.
This caused jarring layout jumps when navigating between landing, loading, and results states.

## Decision
1. Implement a single unified page shell component (`<PageShell>`) with:
   - Max width: `--page-max: 960px` (tested across 390px to 1920px viewports).
   - Side gutters: `--page-gutter: 24px` on desktop (≥768px), `16px` on mobile (<768px).
2. Share this exact shell across all views:
   - Header (BP brandmark aligns with content left edge).
   - Hero headline, subtitle, and search form.
   - Sticky search summary bar and toolbar.
   - Results list rows and loading skeleton rows.
   - Empty, error, and footer states.
3. Left-align the hero headline and body copy to the shell (brianlovin.com style), eliminating centered floating cards.
4. Set `scrollbar-gutter: stable` on `:root` to eliminate layout shift when scrollbars appear or disappear.

## Consequences
- Zero layout shift (CLS = 0) between view switches.
- Harmonious vertical alignment along the left margin at any screen size.
- Automated layout audit tests verify identical left bounding box across header, form, summary, and list.
