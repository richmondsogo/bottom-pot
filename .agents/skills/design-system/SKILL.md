---
name: design-system
description: >
  Bottom Pot UI Rulebook: Keep UI implementation aligned with the square design system,
  shadcn component foundation, typography hierarchy, and Brian Lovin craft principles.
  Use when creating or modifying any visual component, layout, or styling.
---

# Bottom Pot UI Rulebook & Design System Skill

This skill is the authoritative implementation guide for Bottom Pot UI. Any agent touching frontend styling, layouts, components, or typography must follow these rules without exception.

---

## 1. Non-Negotiable Core Constraints

1. **Square Geometry Everywhere**:
   - `--radius: 0` / `rounded-none` on all elements: buttons, inputs, selects, dialogs, sheets, popovers, tooltips, avatars, tags, and focus rings.
   - Never override `--radius` with rounded corners.
2. **Never Add Unlayered Global CSS**:
   - Resets and element selectors (`*`, `button`, `input`, `select`, `h1`..`h6`, `p`, etc.) MUST ALWAYS reside within `@layer base`.
   - Never write unlayered element styles: unlayered rules override Tailwind `@layer utilities` regardless of specificity, breaking component padding, margins, and heights.
   - Always verify COMPUTED spacing (`padding`, `margin`, `height`, `line-height`) in DevTools or automated audits after styling changes.
3. **Unified Page Shell & Centered Hero**:
   - Single container `--page-max: 1160px` with `--page-gutter: 32px` (desktop/tablet) and `16px` (mobile).
   - Centered hero rhythm: display headline, centered lead (`max-w-[60ch]`), and framed form panel (`max-w-[760px]`, 24-32px padding).
   - Hairlines extend full-bleed at boundaries; inner content aligns strictly to the shell.
   - `scrollbar-gutter: stable` prevents page shifts.
4. **Strict Two-Family Typography System**:
   - **Primary Sans**: Geist Sans (`--font-sans`). Used for all headings, body, labels, buttons, and navigation.
   - **Machine Mono**: DM Mono (`--font-mono`). Used ONLY for machine slugs (`lever`, `greenhouse`), keyboard shortcut badges (`⌘K`, `/`), and tabular counts. Slugs must be lowercase, never uppercase.
   - **Permitted Weights**: 400 (regular), 500 (medium), 600 (semi-bold).
   - **Sentence Case Everywhere**: All labels and UI text use natural sentence case.
   - **Control Typography**: Inputs, selects, and buttons all share identical 14px font size.
5. **Color & Green Usage Budget**:
   - Warm cream canvas (`#FAF8F5`) in light mode; pure dark obsidian (`#0C0D0C`) in dark mode.
   - Three ink tiers: Primary ink (`--ink`), Muted ink (`--ink-muted`), Subtle ink (`--ink-subtle`).
   - Forest green (`--accent`) is strictly budgeted: primary CTA button, platform chip checkmarks (neutral borders), active Remote tag indicator, 2px row hover bar, and focus ring. Banned: green borders on non-interactive containers or unselected chips.
6. **No Scroll-Jacking**:
   - Lenis and other scroll-hijacking libraries are strictly prohibited. Native smooth scrolling and View Transitions API only.

---

## 2. Shadcn First Workflow

Before writing any custom DOM or CSS:
1. Search `@shadcn` registry via shadcn MCP (`search_items_in_registries`).
2. View component code and dependencies (`view_items_in_registries`).
3. Install via shadcn CLI into `frontend/src/components/ui/`.
4. Compose application components from these primitives using `cva` variants and token classes.
5. Log all shadcn MCP interactions in the current step document under `docs/steps/`.

---

## 3. Results Architecture: Semantic Table (Desktop) & Stacked Cards (Mobile)

Postings and data rows must use semantic, scannable layouts:
- **Desktop (>=768px)**: Fixed-layout table (`table-layout: fixed; width: 100%`) with explicit `<colgroup>`:
  - Role (flexible, clamped 2 lines with tooltip, stretched link with `↗`).
  - Company (fixed 240px, leading 28px monogram on line 1, lowercase mono platform slug on line 2).
  - Location (fixed 220px, muted, clamped 1 line).
  - Salary (fixed 130px, conditional: rendered only when at least one job in the set has salary).
  - Work Model (fixed 120px, badge rendered only if known, empty if unknown).
  - Posted (fixed 100px, left-aligned, tabular relative date with exact date tooltip).
  - `<th>` and `<td>` MUST share identical padding (`py-3.5 px-3.5`) so column labels and data align to the exact pixel.
- **Mobile (<768px)**: Stacked cards with identical spacing scale and clean visual hierarchy.
- **Hover/Active**: 2px forest green bar on left edge, subtle background tint. Keyboard navigation via `j`/`k` and Enter.

---

## 4. Visual Verification Checklist

Before declaring any UI task complete, verify:
- [ ] 5 viewports: 1920x1080, 1440x900, 1024x768, 768x1024, 390x844.
- [ ] Light mode and dark mode have crisp AA contrast (no unreadable text).
- [ ] Left alignment is perfectly preserved across header, hero, summary, and list.
- [ ] `scrollbar-gutter: stable` prevents page shifts.
- [ ] Zero console errors or warnings in DevTools.
- [ ] Axe-core accessibility reports 0 serious or critical violations.
