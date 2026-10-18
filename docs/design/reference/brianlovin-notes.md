# Reference Study: brianlovin.com Measurements & Observations

This document records computed measurements, styles, and structural observations extracted via Playwright and Chrome DevTools from [brianlovin.com](https://brianlovin.com) across desktop and mobile, light and dark themes.

---

## 1. Typography & Hierarchy

### Font Family
- **Stack**: `Inter, "Inter Fallback", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`
- **Single Sans**: A single clean sans-serif typeface handles all headings, body, labels, and metadata.
- **Rendering**: `-webkit-font-smoothing: antialiased`, `subpixel-antialiased`.

### Type Scale & Weights
- **Page Titles / Hero Headline**: 24px–40px, font-weight 600 or 700, line-height 1.2–1.33, tracking `-0.016em` to `-0.025em`.
- **Section Headers / Post Titles**: 20px, font-weight 500, line-height 28px (1.4).
- **Body & Primary Links**: 16px, font-weight 400 or 500, line-height 24px (1.5).
- **Secondary / Metadata / Domain Labels**: 13px–15px, font-weight 400, line-height 20px–24px.
- **Micro Labels / Timestamps**: 12px–13px, tabular numbers.
- **Allowed Weights**: 400 (regular), 500 (medium), 600/700 (semi-bold/bold). No bold monospace; no uppercase tracked labels.

---

## 2. Color Palette & Ink Tiers

### Light Theme
- **Canvas / Background Main**: `#FFFFFF` to subtle neutral-50 (`#FBFBFB`).
- **Primary Ink**: Neutral-900 / `lab(7.78 -0.00001 0)` (~`#121212`) — High contrast for titles and body.
- **Secondary Ink (Muted)**: Neutral-600 / `lab(34.92 0 0)` (~`#525252`) — Secondary summaries and metadata.
- **Tertiary Ink (Subtle)**: Neutral-500 / `lab(66.12 0 0)` (~`#737373`) — Domains, dates, trailing metadata.
- **Borders & Dividers**:
  - Primary Hairline: `#0000001f` (12% black)
  - Subtle Hairline: `#00000017` (9% black)
- **Hover Surfaces**: Neutral-100 / `#F5F5F5` (or low-alpha black `rgba(0, 0, 0, 0.04)`).

### Dark Theme
- **Canvas**: Pure black (`#000000`) or deep carbon (`#0A0A0A`).
- **Primary Ink**: White / Neutral-50 (`#FAFAFA`).
- **Secondary Ink**: Neutral-400 (`#A3A3A3`).
- **Tertiary Ink**: Neutral-500 (`#737373`).
- **Borders**: `#FFFFFF1f` (12% white) / `#262626`.
- **Hover Surfaces**: Neutral-900 (`#171717`) or `rgba(255, 255, 255, 0.05)`.

---

## 3. Layout, Shell & Spacing

### Shell & Containers
- **Max Width**: Central reading/writing column is constrained (`max-w-2xl` = 672px, or index views up to 880px–960px).
- **Alignment**: Strict left alignment. Headings, body copy, list rows, and navigation share the exact same left edge. No centered forms or centered cards floating disconnectedly.
- **Page Padding / Gutters**:
  - Desktop: 24px–32px side padding.
  - Mobile (<768px): 14px–16px side padding.
- **Vertical Rhythm**:
  - Header height: 56px (`h-14`), sticky top.
  - Section gaps: 48px–64px between logical blocks.
  - Row padding: 12px vertical padding on list rows (`py-3 px-3.5`).
  - Row gap: 2px–4px between title and subtitle/metadata.

---

## 4. List Pattern vs. Card Grid

- **Lists, Not Cards**: Dense, clean lists replace chunky outlined cards.
- **Row Anatomy**:
  - Line 1: Primary title / role (weight 500, primary ink).
  - Line 2: Secondary context (company, location, source domain) in muted ink.
  - Trailing Meta: Right-aligned date, tag, or action.
- **Hover Interaction**:
  - Entire row is interactive (`cursor-pointer`).
  - Background shifts quietly to subtle tint (120ms ease-out).
  - No drop shadow; no card lift or scale transform.

---

## 5. Chrome & Visual Discipline

- **No Status Bloat**: Zero developer jargon, zero unnecessary badge pill counters, zero redundant "?" icons.
- **Hairlines Over Boxes**: Separation is achieved through whitespace first, and 1px hairlines second. No heavy multi-layer card borders.
- **Focus Rings**: Clean 2px high-contrast outline with 2px offset.
- **Smooth Native Scrolling**: `scroll-behavior: smooth`, `scrollbar-gutter: stable`, custom thin square scrollbar (`scrollbar-width: thin`).
