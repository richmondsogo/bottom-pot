# ADR 0022: Glyph Portal Hero Scroll Motion, Wordmark Weight Exception, and Green Budget Compliance

## Status
Accepted

## Context
The landing page hero required elevation from a generic SaaS template into an authentic, product-revealing editorial experience. The chosen concept introduces a physical typographic passage: an opening frame anchored by a display wordmark ("Bottom Pot") that zooms into the ink interior of a glyph upon user scroll, smoothly depositing the visitor directly into the active search surface.

Integrating this interaction required addressing four critical design constraints:
1. **Typography Weight**: ADR 0010 standardizes body and heading typography on normal sans weights (400, 500, 600) with Geist Variable.
2. **Scroll-Jacking Ban**: ADR 0014 explicitly forbids scroll-jacking libraries (e.g. Lenis) that intercept native wheel/touch events.
3. **Green Accent Budget**: ADR 0021 mandates a strict budget for forest green (`#1A382B`), restricting it to primary action CTAs, active status markers, and focus rings. The upstream component defaulted to a full-screen green field.
4. **Square Geometry**: ADR 0004 enforces `--radius: 0` throughout the interface.

## Decision

1. **Wordmark Weight 700 Exception**:
   - Display wordmark `Bottom Pot` is rendered in mixed case using self-hosted `Geist Variable` at `fontWeight: 700`.
   - This weight is an explicit, documented exception granted strictly to the hero display wordmark. It provides the necessary optical stroke width and cross-sectional ink volume required for the 2D canvas distance-transform algorithm (`findInterior`) to locate an expansive interior focal point.

2. **Native Sticky Pinning (No Scroll-Jacking)**:
   - The `GlyphPortal` component uses native CSS `position: sticky` (`top: 0`) and reads standard passive window scroll offsets (`window.scrollY`).
   - Wheel, trackpad, and touch input are completely unintercepted. Built-in browser momentum, keyboard navigation, and scrollbars operate normally without synthetic physics or event hijacking, complying with ADR 0014.
   - When `@media (prefers-reduced-motion: reduce)` is active, sticky pinning and SVG scaling are disabled, rendering a clean, accessible layout directly.

3. **Ink Field Palette & Green Budget Compliance**:
   - Component tokens are mapped strictly to our CSS custom properties:
     - `--gp-paper: var(--bg)`
     - `--gp-ink: var(--ink)`
     - `--gp-field: var(--ink)`
     - `--gp-foreground: var(--bg)`
   - The revealed interior canvas field is deep ink (`var(--ink)`), completely avoiding green container bloat.
   - Deep forest green (`var(--accent)`) appears exclusively on the primary CTA ("Start searching") and square focus rings.

4. **Font Loading & Fallback Resilience**:
   - The component waits for `document.fonts.load('700 100px "Geist Variable"')` with a 1.6s timeout before enabling dynamic glyph measurement.
   - If the font fails or times out, the page renders a high-fidelity static fallback hero with no layout shift or visual breakage.

5. **Square Geometry Overrides**:
   - All internal letter choices and the coarse-pointer mobile select picker are styled with `border-radius: 0` to preserve the non-negotiable square geometry established in ADR 0004.

## Consequences
- The hero creates an unforgettable typographic first impression while remaining 100% faithful to native browser scrolling.
- Dark mode polarity inversion functions automatically via token mapping.
- Green retains its high-intent signal value without diluting the warm cream editorial aesthetic.
