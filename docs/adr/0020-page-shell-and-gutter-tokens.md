# ADR 0020: Unified Page Shell and Centered Hero Layout

## Status
Accepted (Supersedes ADR 0011)

## Context
ADR 0011 constrained the entire interface to 960px and forced left-alignment on all elements including the hero headline and search form. While this eliminated some layout jumps, it created new visual problems:
- On wide viewports (1440px and 1920px), a 960px left-aligned column left huge amounts of dead space on the right side of the screen.
- The hero section felt lopsided and cramped, lacking the visual authority of an intentional, centered application landing page.
- Hairlines were inconsistently bordered (some bleeding full width, others nested inside containers).

## Decision
1. **Container Max-Width and Gutters**:
   - Establish `--page-max: 1160px` (within the 1120px to 1216px design envelope).
   - Establish `--page-gutter: 32px` on desktop and tablet, and `16px` on mobile (<640px).
   - Use `scrollbar-gutter: stable` on `:root` to avoid layout jitter during vertical scrolling.
2. **Page Shell Boundary Discipline**:
   - Header, search summary bar, toolbar, results table, and footer all share the exact same `--page-max` container and `--page-gutter` padding.
   - Header hairlines and sticky bar borders extend full bleed to frame the viewport, while their interactive content aligns precisely to the inner page shell margins.
3. **Centered Hero Rhythm**:
   - The landing hero uses an authoritative centered layout:
     - Top spacing from header: 64px to 96px (`py-16 sm:py-20`).
     - Display headline: centered, tight display typography (`tracking-[-0.03em]`, balanced wrap).
     - Lead paragraph: centered, `max-w-[60ch]`, 16px font size, 16px to 20px gap from headline.
     - Spacing to search card: 40px to 48px (`mb-10 sm:mb-12`).
4. **Framed Form Panel**:
   - The search form is rendered as a clean, single framed panel:
     - Width: centered at `max-w-[760px]`.
     - Border: 1px hairline (`border-[var(--line)]`).
     - Padding: 24px to 32px (`p-6 sm:p-8`).
     - Control heights: unified 40px (`h-10`) with 12px horizontal padding (`px-3`).
     - Field-to-field gaps: 20px to 24px (`gap-5` to `gap-6`).
     - Label-to-control gaps: 8px (`gap-2`).

## Consequences
- Desktop layouts at 1024, 1440, and 1920px feel balanced and generous without awkward dead space.
- Results tables and toolbars have sufficient horizontal breadth to display 5-6 structured columns without truncation.
- Centered landing hero establishes calm editorial presence.
