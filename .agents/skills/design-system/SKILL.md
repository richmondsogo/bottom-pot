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
2. **Unified Page Shell**:
   - Single container `--page-max: 960px` with `--page-gutter: 24px` (desktop) and `16px` (mobile).
   - Left edges align across header wordmark, hero, search form, summary bar, list rows, and footer.
   - Never center floating cards. Left-align content to the shell.
3. **Strict Two-Family Typography System**:
   - **Primary Sans**: Geist Sans (`--font-sans`). Used for all headings, body, labels, buttons, and navigation.
   - **Machine Mono**: DM Mono (`--font-mono`). Used ONLY for machine slugs (`lever`, `greenhouse`), keyboard shortcut badges (`⌘K`, `/`), and tabular counts.
   - **Permitted Weights**: 400 (regular), 500 (medium), 600 (semi-bold).
   - **Sentence Case Everywhere**: All labels and UI text use natural sentence case.
   - **Banned**: Bold mono, uppercase tracked mono labels/eyebrows, off-scale font sizes, mixed font families inside one control.
4. **Color & Ink Discipline**:
   - Warm cream canvas (`#FAF8F5`) in light mode; pure dark obsidian (`#0C0D0C`) in dark mode.
   - Three ink tiers: Primary ink (`--ink`), Muted ink (`--ink-muted`), Subtle ink (`--ink-subtle`).
   - Deep forest green (`--accent: #1A382B` in light, `#2E7D52` in dark) is used deliberately and sparingly: primary buttons, 2px left hover indicator bar, remote badge dot, selection tint, focus rings.
5. **No Scroll-Jacking**:
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

## 3. List Row Architecture (Brian Lovin Pattern)

Postings and data rows must use the two-line list layout instead of boxed tables:
- **Line 1**: Job title (500 weight, primary ink, stretched link `target="_blank"`, `↗` hover indicator). Dimmed title for visited rows.
- **Line 2**: Company monogram + formatted company name + `·` + location (muted ink).
- **Right Meta**: Work model indicator (only if known), salary (only if known), relative date (`<time datetime="...">`), and ATS platform slug in muted mono.
- **Divider**: 1px subtle hairline (`--border-subtle`).
- **Hover/Active**: 2px forest green bar on left edge, subtle background tint.

---

## 4. Visual Verification Checklist

Before declaring any UI task complete, verify:
- [ ] 5 viewports: 1920x1080, 1440x900, 1024x768, 768x1024, 390x844.
- [ ] Light mode and dark mode have crisp AA contrast (no unreadable text).
- [ ] Left alignment is perfectly preserved across header, hero, summary, and list.
- [ ] `scrollbar-gutter: stable` prevents page shifts.
- [ ] Zero console errors or warnings in DevTools.
- [ ] Axe-core accessibility reports 0 serious or critical violations.
