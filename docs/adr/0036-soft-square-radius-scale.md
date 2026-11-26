# ADR 0036: Soft-Square Radius Scale

## Status

Accepted (amends [ADR 0004](0004-square-design-system-and-daybreak-craft.md) §1)

## Context

`ADR 0004` established strict `0px` (`--radius: 0`) corners everywhere and enforced `* { border-radius: 0 !important; }` and `button, input, select, textarea { border-radius: 0 !important; }` in `frontend/src/index.css`. While sharp hairlines and a crisp fixed-column results table give Bottom Pot strong editorial legibility, applying `0px` with `!important` overrides across every interactive control, card, popover, badge, and dialog made buttons, inputs, tags, and overlays feel overly harsh and prevented semantic scale separation between small inline tags and larger floating surfaces.

## Decision

We replace the global `0px` `!important` override with a three-token **soft-square** radius scale declared in `@theme` and `:root` inside `frontend/src/index.css`:

- `--radius-sm: 4px` (`rounded-sm`): badges, work-model and age tags, `CompanyMark` logo/monogram tiles, `<kbd>` shortcut hints, and menu items (`SelectItem`, `DropdownMenuItem`).
- `--radius-md: 6px` (`rounded-md`): buttons, inputs, select triggers, `CountryCombobox` triggers, platform and recency chips, toolbar filter pills/switches, navigation tabs, and tooltips.
- `--radius-lg: 8px` (`rounded-lg`): search prompt card, `Filters` drawer, popovers, dropdown/select popups, command palette, dialogs, toast notifications, editorial cards, and `DetailSheet` inner cards and primary action buttons.
- `none (0px)` (`rounded-none`): results table (`<table>`, `<thead>`, `<tbody>`, `<tr>`, `<th>`, `<td>`, 2px left row hover bar, older-postings divider), full-bleed header/footer/toolbar/section hairlines, edge-attached `DetailSheet` panel, mobile result list rows, and tiny status indicator dots.

Both global `border-radius: 0 !important;` rules in `frontend/src/index.css` are removed so Tailwind utilities map cleanly to the three tokens without `!important` suppression.

## Alternatives Considered

- **Keep strict `0px` everywhere**: Preserves brutalist uniformity, but flattens hierarchy between inline tags, interactive controls, and floating overlays.
- **Full pill / large-radius (`12px+` / `rounded-full`)**: Softens the interface too aggressively and breaks the disciplined, high-density editorial character defined in `DESIGN.md`.

## Trade-offs

- **Token discipline required**: Removing the `!important` base reset means new UI primitives must explicitly map to `rounded-sm`, `rounded-md`, `rounded-lg`, or `rounded-none`. Automated Vitest assertions, Playwright computed-style checks, and zero-token completeness audits guard against unmapped upstream classes (`rounded-xl`, `rounded-4xl`).
- **Slightly softer interactive silhouette**: Buttons and cards lose pure 90-degree corners, while the results table and edge-anchored sheet retain crisp architectural boundaries.

## How to Revert

Set all three radius tokens in `frontend/src/index.css` (`@theme` and `:root`) to `0px`:

```css
--radius-sm: 0px;
--radius-md: 0px;
--radius-lg: 0px;
```

Because every component consumes these three tokens (with no hardcoded pixel radii), setting them to `0px` immediately restores strict square geometry across the entire application.

## Consequences

- `DESIGN.md`, `docs/FRONTEND.md`, `AGENTS.md`, `README.md`, `.agents/skills/design-system/SKILL.md`, and `.agents/skills/frontend-design/SKILL.md` are updated to reference the soft-square scale and square-table invariant.
- Tests verify computed `border-radius` values by component role (`4px`, `6px`, `8px`, and `0px` on `table`/`tr`/`td` and `.detail-sheet`).
