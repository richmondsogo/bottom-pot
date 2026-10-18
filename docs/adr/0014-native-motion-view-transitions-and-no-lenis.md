# ADR 0014: Native Motion, View Transitions API, and Rejection of Scroll-Jacking (Lenis)

## Status
Accepted

## Context
Smooth page scrolling and visual continuity during view transitions are critical for a calm, editorial application. However, third-party scroll-jacking libraries (e.g. Lenis, SmoothScroll) introduce severe liabilities:
- Hijack the native browser rendering thread, causing trackpad lag and stutter.
- Break browser built-in Ctrl+F "find in page" auto-scrolling.
- Break native browser accessibility features, screen readers, and touch gestures.
- Introduce substantial JavaScript bundle weight.

## Decision
1. **Rely 100% on Native CSS & Browser APIs**:
   - `scroll-behavior: smooth` on `html`.
   - `scroll-padding-top: 64px` to account for sticky header.
   - `scrollbar-gutter: stable` to prevent layout reflow.
   - Guard all motion under `@media (prefers-reduced-motion: no-preference)`.
2. **View Transitions API**:
   - Wrap view mode changes (landing ↔ loading ↔ results) in `document.startViewTransition()`.
   - Fall back smoothly to instant state replacement in unsupported browsers or when `prefers-reduced-motion` is active.
   - CSS animations: 160ms–200ms subtle fade and 6px translateY.
3. **Scroll Restoration**:
   - Save scroll position when navigating to "Edit search", and restore position when returning to results.
4. **Explicit Rejection of Lenis / Scroll-Jacking**:
   - Scroll-jacking libraries are explicitly banned from this repository.

## Consequences
- Native 120Hz/60Hz smoothness on mobile and desktop trackpads.
- Zero accessibility regressions for screen reader or keyboard scrolling.
- Instant, predictable page interaction without third-party bundle bloat.
