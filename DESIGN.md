# Design Philosophy & Design System: Bottom Pot

This document defines the design principles, visual language, and token specifications for Bottom Pot.

---

## 1. Core Principles (Restored Editorial Architecture)

**Quiet & Typography-Led.** The interface is calm, editorial, and typography-first. Hierarchy is carried by precise type scale, weight, and subtle ink tiers (ink, muted, subtle) rather than borders, boxed badges, colored cards, or visual noise.

**Unified Page Shell.** Every state (landing, loading, results, saved-results, errors) lives inside the exact same page shell (`--page-max: 1160px; --page-gutter: 32px` on desktop/tablet, `16px` on mobile). Hairlines extend full bleed to frame the viewport, while content remains strictly aligned to the shell. `scrollbar-gutter: stable` prevents page shifts.

**Semantic Fixed Table & Scannable Hierarchy.** Postings are presented in a semantic `<table>` with `table-layout: fixed; width: 100%` and explicit column widths. Headers and cells share identical padding (`py-3.5 px-3.5`) so column content and labels align to the exact pixel. On mobile (<768px), rows adapt into clean stacked cards.

**Soft-Square Radius Scale (ADR 0036).** Interactive controls and surfaces follow a three-token radius scale (`--radius-sm: 4px` for badges, tags, `CompanyMark`, and `<kbd>` hints; `--radius-md: 6px` for buttons, inputs, selects, comboboxes, chips, and toolbar pills; `--radius-lg: 8px` for the search card, popovers, dropdowns, command palette, dialogs, and `DetailSheet` inner cards/actions), while the results table (`table`/`tr`/`td`, hover bar), header/section hairlines, and edge-attached `DetailSheet` panel stay `0px`.

**Strict Green Usage Budget.** Forest green (`--accent: #1A382B` light, `#2E7D52` dark) is strictly budgeted. It is reserved for:
- Primary search button CTA.
- Platform chip affirmative checkmarks (with neutral borders/surfaces).
- Remote work model indicator dot and marker text.
- 2px left accent bar on table row hover.
- **High-contrast keyboard focus rings (`:focus-visible`).**
- Links and live status indicator dots.
Green is strictly banned for non-interactive backgrounds, full borders on passive chips, or decorative boxes.

---

## 2. Visual Language & Identity

- **Canvas & Surfaces**: Warm editorial cream (`#FAF8F5`) for light mode, crisp white (`#FFFFFF`) on interactive surfaces; in dark mode, deep rich obsidian canvas (`#0C0D0C`) with elevated dark surfaces (`#141614`).
- **Wordmark**: Standalone `LogoSymbol` SVG with a single sans `"Bottom Pot"` label (no boxed `BP` badge or developer taglines).
- **Multi-Page Navigation**: Dedicated HTML/SPA routes (`/` Home, `/app` Workspace, `/product` Product, `/sources` Sources, `/about` About, `/admin` Admin) linked cleanly in `<Header>` and editorial 3-column `<Footer>` with zero `#` section-separator anchors and zero scroll-jacking.
- **Active Navigation State**: Indicate the current page in `<Header>` with a tactile active surface (`--surface-subtle`), crisp `--border-strong` frame (`--radius-md`), and subtle forest-green indicator rather than a bare bottom underline.
- **Hairlines**: 1px dividers (`--border: #E6E1D7` / `--border-subtle: #ECE8E0` in light, `rgba(255, 255, 255, 0.12)` / `rgba(255, 255, 255, 0.08)` in dark).
- **Overlay Alignment**: Base UI `SelectContent`, `DropdownMenuContent`, and `PopoverContent` default to `align="start"` (or `align="end"` on right-aligned card triggers like `SearchForm` country selector), `side="bottom"`, `sideOffset={4}`, `alignItemWithTrigger={false}`, and `min-w-(--anchor-width) w-max` so menus open directly below triggers without overlapping, overhanging, or green fill floods (`focus:bg-[var(--surface-hover)]`).
- **Chrome Discipline**: Keep one calm sticky result header with immediate `New search`, collapsible inline `Edit search`, `Export`, and `...` actions above one crisp horizontal filter strip (`Toolbar` with overflow secondary filters inside `More filters` and a clean 2-column grid on `390px`), without duplicate counters, `Try:`/`Recent:` noise, or competing query bars.
- **Motion**: Restrained GPU-only micro-motion (`transform`, `opacity`, `120ms-220ms`: `--duration-fast: 120ms`, `--duration-press: 140ms`, `--duration-base: 180ms`, `--duration-drawer: 220ms` with `--ease-out`, `--ease-press`, and `--ease-drawer` in `frontend/src/index.css`): tactile `:active` press feedback (`scale(0.97)`), origin-aware overlay entrances (`scale(0.95) -> 1`), subtle `@starting-style` inline reveal, and view transitions. Keep routine UI motion quiet while leaving room for intentional craft in isolated playful surfaces (such as the easter egg canvas and pointer), always respecting `prefers-reduced-motion`.

---

## 3. Typography System

- **Font Family**:
  - Primary Sans: Self-hosted Geist Variable (`--font-sans: 'Geist Variable', -apple-system, sans-serif`). Used for all headings, body text, form controls, and labels.
  - Monospace: Self-hosted DM Mono (`--font-mono: 'DM Mono', monospace`). Used ONLY for machine slugs (`lever`, `greenhouse` in lowercase), keyboard shortcut hints (`/`, `⌘K`), and tabular counts. Slugs must be lowercase, never uppercase.
- **Headings**:
  - Display: Headline "Find the signal behind the noise." with tight tracking (`-0.025em`) and balanced text wrap (`text-wrap: balance`).
  - Section Titles: Sentence case, medium weight, crisp contrast.
- **Body & UI**:
  - Body text: 15px (`--text-body: 15px`) / 1.55 line-height.
  - UI controls & inputs: Unified 14px / 1.4 line-height across inputs, selects, and buttons.
  - Data, numbers, timestamps, and codes: 12–13px monospace with `font-variant-numeric: tabular-nums`.
- **Text Tiers**:
  - Primary ink: `#181816` (high contrast, readable).
  - Muted ink: `#57564F` (AA contrast on cream, for secondary labels and metadata).
  - Subtle ink: `#5A5952` (WCAG AA contrast > 5.5:1 on cream and white, for indicators and metadata).

---

## 4. Spacing Recipes & Tokens Reference

### Page Shell
- `--page-max: 1160px`
- `--page-gutter: 32px` (desktop/tablet >= 768px)
- `--page-gutter: 16px` (mobile < 768px)
- `scrollbar-gutter: stable` on `:root`

### Hero Rhythm
- Top spacing (header to headline): 64px to 96px (`py-16 sm:py-20`).
- Headline to lead paragraph: 16px to 20px.
- Lead paragraph: `max-w-[60ch] mx-auto text-center`.
- Lead to form panel: 40px to 48px (`mb-10 sm:mb-12`).

### Form Panel & Controls
- Form container: `max-w-[760px] mx-auto`, 1px hairline border, `p-6 sm:p-8` (24px to 32px padding).
- Control height: Unified 40px on mobile (`h-10` / `data-[size=default]:h-10`) and 36px on desktop (`sm:h-9`) with 12px horizontal padding (`px-3`).
- Control font size: Unified 14px (`text-sm`).
- Primary card inputs: `Role or keyword` + `"Where can you work from?"` (`CountryCombobox` with `align="end"`) above `[Work model]`, `[Filters]`, and `[Search jobs]` without duplicate city/country fields in the dock or `Try:` / `Recent:` clutter below the card.
- Optional city refinement (`City or office hub (optional)`) lives cleanly inside the expandable `Filters` drawer (`mt-2`, `p-4 sm:p-5`, hairline top) alongside `Posted within`, Nigerian boards toggle, and 13 platform chips (4-column desktop / 2-column mobile, `h-9`, neutral selected state with green check).
- Primary search CTA: Green CTA button (`h-11 sm:h-9 px-5`), with saved shortlist banner underneath when postings are saved.
- "How it works": Visible in Admin mode (`mt-20 sm:mt-24`, hairline top rule, 3 columns, 14px muted copy).

### Results Table Metrics (Desktop >= 768px)
- Semantic `<table>` with `table-layout: fixed; width: 100%`.
- Cell padding: Identical `py-3.5 px-3.5` (14px) for all `<th>` and `<td>`.
- Row height: 56px to 64px.
- Column width budget:
  - Role: Flexible (`min-width: 220px`, `w-auto`). Clamped to 2 lines, full title in tooltip.
  - Company: Fixed `195px`. Leading 28px soft-square (`--radius-sm`) theme-aware monogram/logo tile (`--mono-0-*`..`--mono-6-*`), company name (font-medium), lowercase mono platform slug on line 2.
  - Location: Fixed `165px`. Muted ink, clamped 1 line.
  - Salary: Fixed `195px`. Rendered conditionally: present in `<colgroup>`, `<thead>`, and `<tbody>` only when at least one row has compensation data.
  - Work & eligibility: Fixed `195px`. Tokenized `Remote` / `Hybrid` / `In-person` badge when known, or muted plain-text `"Not stated"` (`--ink-subtle`) when unknown (`ADR 0035`), plus objective country eligibility scope below.
  - Posted: Fixed `90px`. Left-aligned relative date with tabular numerals and exact date tooltip.
- Table Row Interactions: 2px green hover bar on left border, surface tint on hover, visible high-contrast outline on keyboard focus. Whole row opens posting (`target="_blank" rel="noopener noreferrer"`).
- Mobile adaptation (< 768px): Stacked card format (`ResultsCards.tsx`) preserving spacing scale.

---

## 5. Banned Patterns

1. **Unlayered Global CSS**:
   - Universal or element resets (`*`, `button`, `input`, `select`, `h1`..`h6`, `p`, `table`) outside `@layer base` are strictly prohibited.
2. **Off-Scale Border Radii**:
   - Any hardcoded pixel radius or off-scale Tailwind class (`rounded-full`, `rounded-xl`, `rounded-4xl`, `rounded-[...]`), or rounded corners on the results table (`table`/`tr`/`td`), hairlines, or edge-attached `DetailSheet` panel. Only `--radius-sm` (`4px`), `--radius-md` (`6px`), `--radius-lg` (`8px`), and `0px` are permitted (`ADR 0036`).
3. **Uppercase Monospace**:
   - Uppercase tracked platform names or slugs (`GREENHOUSE`, `LEVER`). Slugs must be lowercase (`greenhouse`, `lever`).
4. **Native Unstyled Selects**:
   - Raw browser `<select>` controls exposed in the UI. All visible selectors must use styled shadcn/Base UI components.
5. **Off-Scale Typography & Unequal Control Metrics**:
   - Buttons, inputs, or selects in the same bar with disparate heights or font sizes.
6. **Green Overuse**:
   - Green outlines on unselected or all 13 platform chips; green hover fills (`focus:bg-accent`) on dropdown items; green backgrounds on non-interactive banners; green decorative strokes.
7. **Synthetic Unknown Values**:
   - Rendering `"-"`, `"—"`, `"N/A"`, or guessed tags when data is missing (`ADR 0001`: Unknown beats wrong). Missing salary/location cells remain empty; unstated work models render explicitly as muted plain-text `"Not stated"` (`ADR 0035`).
8. **Hardcoded Theme Hexes & Missing Tailwind v4 Dark Variant**:
   - Using `dark:*` utilities without `@custom-variant dark (&:where(.dark, .dark *));` or hardcoding hex badge/monogram colors (e.g., Hybrid orange tags or light-only `CompanyMark` tiles) instead of AA-verified CSS theme tokens.

---

## 7. Verification

Every visual change must be verified against:
- Five core viewports: 1920x1080, 1440x900, 1024x768, 768x1024, 390x844.
- WCAG AA color contrast (automated axe-core checks).
- Zero console errors and zero layout shifts.
