# Design Philosophy & Design System: Bottom Pot

This document defines the design principles, visual language, and token specifications for Bottom Pot.

---

## 1. Core Principles (Restored Editorial Architecture)

**Quiet & Typography-Led.** The interface is calm, editorial, and typography-first. Hierarchy is carried by precise type scale, weight, and subtle ink tiers (ink, muted, subtle)—not by borders, boxed badges, colored cards, or visual noise.

**Unified Page Shell.** Every state (landing, loading, results, saved-results, errors) lives inside the exact same page shell (`--page-max: 1160px; --page-gutter: 32px` on desktop/tablet, `16px` on mobile). Hairlines extend full bleed to frame the viewport, while content remains strictly aligned to the shell. `scrollbar-gutter: stable` prevents page shifts.

**Semantic Fixed Table & Scannable Hierarchy.** Postings are presented in a semantic `<table>` with `table-layout: fixed; width: 100%` and explicit column widths. Headers and cells share identical padding (`py-3.5 px-3.5`) so column content and labels align to the exact pixel. On mobile (<768px), rows adapt into clean stacked cards.

**Square Geometry (Non-Negotiable).** All corners are strictly square (`--radius: 0`). Buttons, inputs, selects, tags, avatars, popovers, dialogs, sheets, tooltips, and focus rings share 90-degree geometry.

**Strict Green Usage Budget.** Forest green (`--accent: #1A382B` light, `#34D399` dark) is strictly budgeted. It is reserved for:
- Primary search button CTA.
- Platform chip affirmative checkmarks (with neutral borders/surfaces).
- Remote work model indicator dot and marker text.
- 2px left accent bar on table row hover.
- High-contrast square keyboard focus rings (`:focus-visible`).
- Links and live status indicator dots.
Green is strictly banned for non-interactive backgrounds, full borders on passive chips, or decorative boxes.

---

## 2. Visual Language & Identity

- **Canvas & Surfaces**: Warm editorial cream (`#FAF8F5`) for light mode, crisp white (`#FFFFFF`) on interactive surfaces; in dark mode, deep rich obsidian canvas (`#0C0D0C`) with elevated dark surfaces (`#161716`).
- **Wordmark**: Square `BP` brandmark tile in forest green with single sans "Bottom Pot" wordmark (no developer taglines).
- **Hairlines**: 1px dividers with subtle low alpha (`#00000014` in light, `#FFFFFF14` in dark).
- **Chrome Discipline**: One quiet summary bar. No duplicate status bands, no redundant icons, no developer jargon ("Serper calls", "GET /search").
- **Motion**: Restrained native transitions (120ms–180ms ease-out). Smooth native scrolling with `scrollbar-gutter: stable`. View transitions via `startViewTransition` with reduced-motion fallback.

---

## 3. Typography System

- **Font Family**:
  - Primary Sans: Self-hosted Manrope (`--font-sans: 'Manrope', -apple-system, sans-serif`). Used for all headings, body text, form controls, and labels.
  - Monospace: Self-hosted DM Mono (`--font-mono: 'DM Mono', monospace`). Used ONLY for machine slugs (`lever`, `greenhouse` in lowercase), keyboard shortcut hints (`/`, `⌘K`), and tabular counts. Slugs must be lowercase, never uppercase.
- **Headings**:
  - Display: Headline "Find the signal behind the noise." with tight tracking (`-0.03em`) and balanced text wrap (`text-wrap: balance`).
  - Section Titles: Sentence case, medium weight, crisp contrast.
- **Body & UI**:
  - Body text: 16px / 1.55 line-height.
  - UI controls & inputs: Unified 14px / 1.4 line-height across inputs, selects, and buttons.
  - Data, numbers, timestamps, and codes: 12–13px monospace with `font-variant-numeric: tabular-nums`.
- **Text Tiers**:
  - Primary ink: `#181816` (high contrast, readable).
  - Muted ink: `#5C5A53` (AA contrast on cream, for secondary labels and metadata).
  - Subtle ink: `#63625B` (WCAG AA contrast > 5.5:1 on cream and white, for indicators and metadata).

---

## 4. Spacing Recipes & Tokens Reference

### Page Shell
- `--page-max: 1160px`
- `--page-gutter: 32px` (desktop/tablet >= 640px)
- `--page-gutter: 16px` (mobile < 640px)
- `scrollbar-gutter: stable` on `:root`

### Hero Rhythm
- Top spacing (header to headline): 64px to 96px (`py-16 sm:py-20`).
- Headline to lead paragraph: 16px to 20px.
- Lead paragraph: `max-w-[60ch] mx-auto text-center`.
- Lead to form panel: 40px to 48px (`mb-10 sm:mb-12`).

### Form Panel & Controls
- Form container: `max-w-[760px] mx-auto`, 1px hairline border, `p-6 sm:p-8` (24px to 32px padding).
- Control height: Unified 40px (`h-10`) with 12px horizontal padding (`px-3`).
- Control font size: Unified 14px (`text-sm`).
- Field label to control gap: 8px (`gap-2`).
- Field-to-field gap: 20px to 24px (`gap-5` to `gap-6`).
- Suggestions buttons: `h-8 px-3 text-xs sm:text-sm` with 8px gaps.
- More filters trigger: `h-9 px-3` with count badge.
- More filters panel: Sits 12px below trigger (`mt-3`), 20px to 24px padding (`p-5 sm:p-6`), hairline top.
- Platform chips: 4-column grid (2-column on mobile), 36px height (`h-9`), 8px gaps (`gap-2`). Selected state is neutral (`border-[var(--ink)] bg-[var(--surface-subtle)]` with green check); unselected is muted line.
- Primary search CTA: Full-width green button (`h-12 px-6`), keyboard hint centered below.
- "How it works": 64px to 96px top margin (`mt-20 sm:mt-24`), hairline top rule, 3 columns, 14px muted copy.

### Results Table Metrics (Desktop >= 768px)
- Semantic `<table>` with `table-layout: fixed; width: 100%`.
- Cell padding: Identical `py-3.5 px-3.5` (14px) for all `<th>` and `<td>`.
- Row height: 56px to 64px.
- Column width budget:
  - Role: Flexible (`min-width: 260px`, `w-auto`). Clamped to 2 lines, full title in tooltip.
  - Company: Fixed `240px`. Leading 28px square monogram tile, company name (font-medium), lowercase mono platform slug on line 2.
  - Location: Fixed `220px`. Muted ink, clamped 1 line.
  - Salary: Fixed `130px`. Rendered conditionally: present in `<colgroup>`, `<thead>`, and `<tbody>` only when at least one row has compensation data.
  - Work Model: Fixed `120px`. Badge rendered only if known, empty if unknown (never "—").
  - Posted: Fixed `100px`. Left-aligned relative date with tabular numerals and exact date tooltip.
- Table Row Interactions: 2px green hover bar on left border, surface tint on hover, visible high-contrast square outline on keyboard focus. Whole row opens posting (`target="_blank" rel="noopener noreferrer"`).
- Mobile adaptation (< 768px): Stacked card format (`ResultsCards.tsx`) preserving spacing scale.

---

## 5. Banned Patterns

1. **Unlayered Global CSS**:
   - Universal or element resets (`*`, `button`, `input`, `select`, `h1`..`h6`, `p`, `table`) outside `@layer base` are strictly prohibited.
2. **Rounded Corners**:
   - Any border radius other than 0px (`--radius: 0`).
3. **Uppercase Monospace**:
   - Uppercase tracked platform names or slugs (`GREENHOUSE`, `LEVER`). Slugs must be lowercase (`greenhouse`, `lever`).
4. **Native Unstyled Selects**:
   - Raw browser `<select>` controls exposed in the UI. All visible selectors must use styled shadcn/Base UI components.
5. **Off-Scale Typography & Unequal Control Metrics**:
   - Buttons, inputs, or selects in the same bar with disparate heights or font sizes.
6. **Green Overuse**:
   - Green outlines on unselected or all 18 platform chips; green backgrounds on non-interactive banners; green decorative strokes.
7. **Synthetic Unknown Values**:
   - Rendering "—", "N/A", or dummy tags when data is missing (ADR 0001: Unknown beats wrong). Unknown cells must remain empty or cleanly omit the tag.

---

## 7. Verification

Every visual change must be verified against:
- Five core viewports: 1920x1080, 1440x900, 1024x768, 768x1024, 390x844.
- WCAG AA color contrast (automated axe-core checks).
- Zero console errors and zero layout shifts.
