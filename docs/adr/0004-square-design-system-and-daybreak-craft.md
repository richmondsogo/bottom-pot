# ADR 0004: Square Design System and Daybreak Craft Direction

## Status
Accepted

## Context
Bottom Pot's existing web interface displayed visual symptoms of rapid, AI-assisted prototype construction ("vibecoded"):
1. Status chrome sprawl across multiple banner components before reaching data.
2. Leaking developer jargon ("GET /search", "LIVE SEARCH INFRASTRUCTURE", "SERPER CALLS").
3. Monospace uppercase eyebrows on every section flattening visual hierarchy.
4. Circular pastel avatars and pill-shaped badges conflicting with the square "BP" brand identity.
5. Inconsistent empty values ("Not listed", "Unknown", "—").
6. Card-in-card nesting with heavy borders pushing data below the fold.
7. Sticky stacking glitches where blurred remnants showed through during scrolling.
8. Decorative empty gradient blobs fighting the geometric language.
9. Uncontrolled row heights and line wrapping.

The quality bar is set by "Daybreak": a calm, typography-first, high-density, editorial reading experience. However, Bottom Pot retains its distinct brand identity: warm cream background (`#FAF8F5`), deep forest green accent (`#1A382B`), square "BP" mark, tight display tracking, and strictly square geometry (`--radius: 0`).

## Decision

1. **Non-Negotiable Square Geometry**:
   Every visual component—buttons, inputs, select triggers, cards, table rows, tags, tooltips, dialogs, monogram tiles, focus rings, and sheet containers—will have `border-radius: 0`.

2. **Centralized CSS Design Tokens**:
   All colors, spacing, borders, typography, line-heights, transitions, and z-index layers will be declared as CSS custom properties in `frontend/src/index.css`. No hardcoded hex values or arbitrary margins will exist in component code.

3. **Transfer of Daybreak Craftsmanship**:
   - **Hierarchy by Contrast and Scale**: High-contrast dark ink (`#181816`) for primary roles, muted ink (`#5C5A53`) for secondary metadata, quiet borders (`#E6E1D8`), avoiding decorative backgrounds.
   - **Quiet State Presentation**: Viewed job postings are dimmed (visited state) to reduce browsing fatigue; selected rows feature a subtle surface tint with a 2px square accent indicator.
   - **Content Dominance**: Upon search completion, the expansive landing hero collapses into a compact, sticky 40px search bar, keeping search results and filters prominent in the viewport.
   - **Consolidated Status Strip**: Multiple stacked banners are replaced by a single quiet status line: `"143 results from 18 platforms · 1.4s · Saved 1d ago · Run again · Clear"`. Diagnostic Serper counts are placed behind a discreet "Details" disclosure.
   - **Work Model Marker System**: Heavy solid badges are replaced by quiet text tags accompanied by an accessible 6px square color marker (Remote: Forest Green, Hybrid: Warm Amber, In-person: Slate).
   - **Deterministic Square Monograms**: Circular rainbow avatars are replaced by square `28x28px` monogram tiles using deterministic ink/cream tints derived from the company name.
   - **Unified Empty Values**: In the results table, all missing or undisclosed fields are presented as a muted `—`. The detail panel provides full explanatory text.

4. **Typography Disciplines**:
   - Display headline uses tight tracking (`-0.03em`) and balanced text wrap (`text-wrap: balance`).
   - Sentence case for UI actions and section titles.
   - Monospace reserved strictly for data, numbers, codes, and counts with `tabular-nums`.

## Consequences
- The product gains an intentional, editorial character suitable for professional tech talent.
- Visual clutter is eliminated, and table scanning efficiency is drastically improved.
- Mobile viewports transition cleanly to a card list with touch-accessible controls (≥44px) and zero horizontal scroll.
