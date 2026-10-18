# Design Philosophy & Design System: Bottom Pot

This document defines the design principles, visual language, and token specifications for Bottom Pot.

---

## 1. Core Principles (Craft Pass 2: Brian Lovin Inspiration)

**Quiet & Typography-Led.** The interface is calm, editorial, and typography-first. Hierarchy is carried by precise type scale, weight, and subtle ink tiers (ink, muted, subtle)—not by borders, boxed badges, colored cards, or visual noise.

**Single Page Shell.** Every state (landing, loading, results, saved-results, errors) lives inside the exact same page shell (`--page-max: 980px`). Header wordmark, hero headline, search controls, summary strip, list rows, and footer share a unified left margin and width. Views never jump.

**Lists, Not Boxes.** Postings and information items are presented as clean two-line list rows with hairline dividers rather than chunky boxed cards or noisy tables.

**Square Geometry (Non-Negotiable).** All corners are strictly square (`--radius: 0`). Buttons, inputs, selects, tags, avatars, popovers, dialogs, sheets, tooltips, and focus rings share 90-degree geometry.

**Deliberate Splashes of Green.** The warm cream canvas (`#FAF8F5`) and neutral ink hierarchy are punctuated with deep forest green (`#1A382B`) only where it signifies action, active status, or primary identity:
- Primary search button
- Links / hover active indicator (a 2px left green bar on hover/focus)
- "Remote" status text and indicator dot
- Focus rings (`:focus-visible`)
- Selection background (`::selection`)
- Active toggle/checkbox states

---

## 2. Visual Language & Identity

- **Canvas & Surfaces**: Warm editorial cream (`#FAF8F5`) for light mode, crisp white (`#FFFFFF`) on interactive surfaces; in dark mode, deep rich charcoal/black canvas (`#0C0D0C`) with elevated dark surfaces (`#161716`).
- **Wordmark**: Square `BP` brandmark tile in forest green with single sans "Bottom Pot" wordmark (no developer taglines).
- **Hairlines**: 1px dividers with subtle low alpha (`#00000014` in light, `#FFFFFF14` in dark).
- **Chrome Discipline**: One quiet summary bar. No duplicate status bands, no redundant icons, no developer jargon ("Serper calls", "GET /search").
- **Motion**: Restrained native transitions (120ms–180ms ease-out). Smooth native scrolling with `scrollbar-gutter: stable`. View transitions via `startViewTransition` with reduced-motion fallback.

---

## 3. Typography System

- **Font Family**:
  - Primary Sans: Self-hosted Manrope (`--font-sans: 'Manrope', -apple-system, sans-serif`).
  - Monospace: Self-hosted DM Mono (`--font-mono: 'DM Mono', monospace`).
- **Headings**:
  - Display: Headline "Find the signal behind the noise." with tight tracking (`-0.03em`) and balanced text wrap (`text-wrap: balance`).
  - Section Titles: Sentence case, medium weight, crisp contrast.
- **Body & UI**:
  - Body text: 16px / 1.55 line-height.
  - UI controls & table text: 14px / 1.4 line-height.
  - Data, numbers, timestamps, and codes: 12–13px monospace with `font-variant-numeric: tabular-nums`.
- **Text Tiers**:
  - Primary ink: `#181816` (high contrast, readable).
  - Muted ink: `#5C5A53` (AA contrast on cream, for secondary labels and metadata).
  - Subtle ink: `#63625B` (WCAG AA contrast > 5.5:1 on cream and white, for indicators and metadata).

---

## 4. Design Tokens Reference

All design tokens are defined as CSS custom properties in `frontend/src/index.css`. Hardcoded hex colors and arbitrary pixel margins outside this tokens definition are prohibited.

```css
:root {
  /* Geometry */
  --radius: 0px;

  /* Colors: Canvas & Surfaces */
  --bg: #FAF8F5;
  --bg-subtle: #F3EFE8;
  --surface: #FFFFFF;
  --surface-raised: #FFFFFF;
  --surface-hover: #F6F3EC;
  --surface-selected: #EDE8DF;

  /* Colors: Ink Tiers */
  --ink: #181816;
  --ink-muted: #5C5A53;
  --ink-subtle: #63625B;
  --ink-inverted: #FAF8F5;

  /* Colors: Borders */
  --border: #E6E1D8;
  --border-strong: #CDC6B9;
  --border-focus: #1A382B;

  /* Colors: Accent (Deep Forest Green) */
  --accent: #1A382B;
  --accent-hover: #254F3D;
  --accent-active: #12281E;
  --accent-subtle: #EBF2ED;
  --accent-text: #FFFFFF;

  /* Semantic Tags & States */
  --remote-marker: #2D6A4F;
  --remote-bg: #EFF6F1;
  --remote-text: #1B4332;

  --hybrid-marker: #B45309;
  --hybrid-bg: #FEF3C7;
  --hybrid-text: #92400E;

  --inperson-marker: #4B5563;
  --inperson-bg: #F3F4F6;
  --inperson-text: #1F2937;

  --warning: #B45309;
  --error: #B91C1C;
  --error-bg: #FEF2F2;

  /* Spacing Scale (4px base) */
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 20px;
  --space-6: 24px;
  --space-8: 32px;
  --space-10: 40px;
  --space-12: 48px;
  --space-16: 64px;

  /* Controls */
  --control-height: 40px;
  --touch-target-min: 44px;

  /* Motion */
  --ease-standard: cubic-bezier(0.16, 1, 0.3, 1);
  --duration-fast: 120ms;
  --duration-normal: 180ms;
}
```

---

## 5. Layout & Component Rules

1. **Header**:
   - Square `BP` brandmark on the left with clean title.
   - Right side holds minimal utility controls (e.g. mock status badge, optional feedback link). Solid cream background with a 1px bottom border.
2. **Landing Hero & Form**:
   - Clean, flat cream canvas with hairline structural dividers. No gradient blobs or decorative illustrations.
   - Primary search fields (Role, Location, Remote) visible immediately; secondary filters ("More filters") tucked under a clean square disclosure.
   - Platform selector displayed as searchable multi-select chips with quick Select All / Select None controls.
   - 3-step "How it works" overview separated by hairline rules.
3. **Collapsed Search Bar (Post-Search)**:
   - When viewing results, the full hero collapses into a compact, sticky 40px search summary bar ("Data Engineer · Remote · 7 days · [Edit search]") so results dominate the viewport.
4. **Results Toolbar**:
   - Solid, opaque background stacking cleanly beneath the header.
   - Consolidated single-line status strip: `"143 results from 18 platforms · 1.4s · Saved 1d ago · [Run again] [Clear]"`.
   - Live search counts (`"Showing 38 of 143"`) with rapid keyword filter (`/` shortcut hint).
5. **Results Table**:
   - Sortable column headers with explicit `aria-sort` indicators.
   - 2-line title clamping with native full-title tooltip on hover.
   - Deterministic square monogram company tiles (`28x28px`).
   - Visited postings display a dimmed title (Daybreak read pattern) to streamline browsing.
   - Auto-hide the salary column when all visible results lack compensation data.
6. **Detail Panel**:
   - Desktop: Slide-out right-side sheet (`480px` wide) with full keyboard accessibility (j/k row selection, Enter/o to open, Esc to close).
   - Mobile: Full-screen modal sheet with touch targets ≥ 44px.
   - Actions: Primary square "Open posting" button (opens in new tab with `rel="noopener noreferrer"`) and secondary "Copy link" button.

---

## 6. Responsive Breakdown

- **Desktop (1440px–1920px)**: Two-pane reading experience, dense tabular presentation, full-width content constrained to 1320px max-width.
- **Laptop / Tablet Landscape (1024px)**: Complete table with responsive column width budgeting.
- **Tablet Portrait (768px)**: Table scrolls cleanly with sticky role column, or collapses into stacked card items.
- **Mobile (390px)**: Stacked cards with clear hierarchy (Title, Company, Location, Tags), drawer-based filter sheet, touch targets ≥ 44px, zero horizontal page overflow.

---

## 7. Verification

Every visual change must be verified against:
- Five core viewports: 1920x1080, 1440x900, 1024x768, 768x1024, 390x844.
- WCAG AA color contrast (automated axe-core checks).
- Zero console errors and zero layout shifts.
