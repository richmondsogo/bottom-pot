# Step 04: UI Layout Restore — Critique Rounds & Verification Loop

## Overview
Following the Phase 1 root cause fix, Phase 2 layout restoration, and Phase 3 guardrail implementation, Phase 4 executed an iterative 5-round critique process against all 10 application states and 16 component-level 2x crops across 5 viewports (1920, 1440, 1024, 768, 390) in both light and dark modes.

Every round evaluated the UI against the strict 9-point failure checklist:
1. Text touching or nearly touching a border
2. Unequal padding or unequal control heights in the same row
3. Label too close to heading/lead/field, or inconsistent gaps
4. Misaligned left edges across header, hero, summary, toolbar, table
5. Ragged or misaligned table columns; header not aligned with cells
6. More than two font families, uppercase mono, off-scale sizes, controls whose font size differs from the UI size (14px)
7. Native-looking selects; clipped or overflowing text or buttons
8. Green overuse or green used for non-interactive decoration
9. Anything that looks less organized than the pass-1 screenshots

---

## Round 1: Post-Reset Base Layout Evaluation
- **Artifacts Inspected**: Initial rendered states after `@layer base` CSS fix.
- **Issues Found**:
  - Hero rhythm was left-aligned inside a wide shell, creating large dead space on 1920px and 1440px displays.
  - Form panel lacked framing; controls touched the edge of the screen on narrower viewports.
  - Results view used two-line list rows from pass 2 where columns (Role, Company, Salary, Posted) failed to align vertically across rows.
  - Platform tags rendered uppercase monospace, violating the two-family typography rule.
  - Suggestion chips wrapped unevenly, producing an orphaned single chip on desktop widths.
  - All 18 platform chips featured bright green borders, creating visual noise.
- **Remediations**:
  - Centered hero layout with explicit vertical rhythm scale (`header-to-headline: 64-96px`, `headline-to-lead: 16-20px`, `lead-to-form: 40-48px`).
  - Restored framed form card (`max-w-[760px]`, `p-6 sm:p-8`, 1px hairline border).
  - Designed semantic fixed-layout table with `<colgroup>` and strict column widths.
  - Redesigned platform chips to use neutral selected state (ink border / subtle surface fill) with a green checkmark icon.

---

## Round 2: Component Alignment & Geometry
- **Artifacts Inspected**: Intermediate build with framed form and fixed table structure.
- **Issues Found**:
  - Control heights were disparate: inputs were 40px, buttons were 36px or 44px, creating uneven vertical alignment when side by side.
  - Table cell padding differed between `<th>` (`px-4 py-2`) and `<td>` (`px-3 py-3`), causing headers to misalign by 4px from cell contents.
  - Results row hover lacked a clear visual indicator without over-coloring.
  - Mobile viewports (390px, 768px) attempted to render the 6-column table, resulting in severe horizontal compression.
- **Remediations**:
  - Standardized all form controls to exactly `h-10` (40px) with `px-3.5` (14px) padding.
  - Unified table cell padding across both `<th>` and `<td>` to identical `px-3.5 py-3.5`.
  - Added a 2px green left-bar indicator on row hover/focus with a subtle surface tint.
  - Introduced `ResultsCards.tsx` for responsive mobile viewports (< 768px), transforming rows into spacious, structured cards.

---

## Round 3: Chrome Discipline & Action Bar Consolidation
- **Artifacts Inspected**: Results toolbar and search summary bar.
- **Issues Found**:
  - Search summary bar displayed separate "Download CSV" and "Download JSON" buttons alongside "Edit search", cluttering the quiet single summary line.
  - Toolbar filters (Role input, Location input, Work model select, Platform select, Nigeria Only toggle, Remote Only toggle) had inconsistent heights (32px vs 36px vs 40px).
  - Toggles lacked clear visual state indicators beyond background color.
- **Remediations**:
  - Consolidated actions into ONE "Edit search" button and ONE overflow menu (⋯) containing Run again, New search, Clear saved (with confirmation), Download CSV, and Download JSON.
  - Standardized all toolbar controls to `h-9` (36px) and 14px font size (`text-sm`).
  - Enhanced Base UI switch toggles with dedicated status dots and clear on/off labels.

---

## Round 4: Base UI Select Display Labels & Sticky Header Scoping
- **Artifacts Inspected**: Production screenshots and 2x component crops.
- **Issues Found**:
  - Base UI `<SelectValue>` rendered raw internal value strings (e.g., `'any'`, `'all'`) instead of human-friendly labels when items were unmounted.
  - In automated crops, the table header crop was partially occluded by the sticky `SearchSummaryBar` due to `position: sticky`.
  - Platform chips in More Filters were partially clipped on small viewports when grid columns were too wide.
- **Remediations**:
  - Passed explicit children to `<SelectValue>`: `{workModel === 'any' ? 'Any work model' : ...}` and `{platform === 'all' ? 'Any platform' : ...}` to guarantee polished display text at all times.
  - Updated screenshot capture script to calculate element viewport offset and scroll sticky headers out of the capture box.
  - Adjusted platform grid to responsive 4-column (desktop) / 2-column (mobile) with `gap-2` and `h-9` chips.

---

## Round 5: Final Comprehensive 2x Crop Audit (Zero Checklist Hits)
- **Artifacts Inspected**: All 16 component-level 2x crops in `docs/design/after-restore/crops/` and 100 full-page screenshots across 5 viewports in light and dark mode.
- **Checklist Results**:
  1. *Text touching borders*: **ZERO hits**. Every button, input, select, and chip satisfies computed horizontal padding ≥ 12px (chips 12px, inputs/buttons 14–32px).
  2. *Unequal padding or heights*: **ZERO hits**. Form controls are uniformly 40px, toolbar controls are uniformly 36px, primary CTA is 48px.
  3. *Label gaps*: **ZERO hits**. Field labels have 8px gap (`gap-2`) to controls; headline to lead is 16px; lead to form is 40px.
  4. *Misaligned left edges*: **ZERO hits**. Shared `--page-max: 1160px` with `--page-gutter: 32px` (`px-4 sm:px-6 lg:px-8`) across Header, Hero, Summary, Toolbar, Table, and Footer.
  5. *Ragged table columns*: **ZERO hits**. Fixed `<table-layout: fixed>` with `<col>` widths (Role flexible min 260px, Company 240px, Location 220px, Salary 130px, Work model 120px, Posted 100px). Headers and cells share identical `px-3.5 py-3.5` padding.
  6. *Typography & casing*: **ZERO hits**. Single sans font for UI; mono restricted to data (lowercase slugs, counts, timestamps); control fonts strictly 14px (`text-sm`).
  7. *Native selects / clipped text*: **ZERO hits**. Base UI styled selects with square geometry; titles clamped to 2 lines with tooltip for overflow.
  8. *Green budget*: **ZERO hits**. Green strictly reserved for primary CTA, Remote badges, selected chip checkmarks, row hover left bar, focus rings, links, and live status dots.
  9. *Organization vs Pass 1*: **ZERO hits**. Layout retains Pass 1's clean centered hierarchy while integrating all Pass 2 interactive components, tokens, and dark mode excellence.

**Outcome**: Round 5 achieved **0 checklist hits**. Full verification passed.
