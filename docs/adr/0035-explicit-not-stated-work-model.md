# ADR 0035: Explicit "Not stated" Display for Unknown Work Model

Date: 2026-11-25

## Status

Accepted (Amends [ADR 0001](0001-unknown-beats-wrong.md))

## Context

Under [ADR 0001](0001-unknown-beats-wrong.md) ("Unknown Beats Wrong"), missing or ambiguous `work_model` values remain `None` (`null`) rather than being guessed or defaulted to `in_person`. In the frontend results table (`ResultsTable.tsx`) and mobile cards (`ResultsCards.tsx`), `renderWorkModelTag` previously returned `null` when `work_model` was `null`. When a listing also had no eligibility label (for example, `work_model: null` and `eligibility: null`), the entire `Work & eligibility` cell rendered empty, leaving users unsure whether data failed to load or whether the employer simply omitted the work arrangement.

## Decision

When `work_model` is `null` (or not one of the known canonical values `remote`, `hybrid`, `in_person` / `onsite`), both `ResultsTable.tsx` and `ResultsCards.tsx` render muted plain text `"Not stated"` (`--ink-subtle`, no badge border, no background, no icon) on line 1 of the Work & eligibility area, with any eligibility line rendered unchanged underneath.

- Never render `"-"`, `"—"`, `"N/A"`, or an inferred work-model badge for unknown `work_model`.
- Missing salary cells and missing location values remain blank in results views.
- The backend data model and API contracts remain unchanged (`work_model: null`).

## Alternatives Considered

1. **Keep the cell completely empty when `work_model` is `null`:** Ambiguous when eligibility is also absent; users cannot distinguish an omitted employer policy from a missing cell.
2. **Render a neutral `"Unknown"` badge:** Visually competes with confirmed `Remote`, `Hybrid`, and `In-person` status badges and adds unnecessary visual noise.

## Trade-offs

- Adds subtle text (`Not stated`) to rows with undisclosed work arrangements, slightly increasing text density in exchange for unambiguous clarity.

## Consequences

- `ResultsTable.tsx` and `ResultsCards.tsx` render `<span data-testid="work-model-not-stated">` with `--ink-subtle` plain text when `work_model` is missing or unrecognized.
- `DESIGN.md`, `README.md`, and `.agents/skills/design-system/SKILL.md` document the `"Not stated"` presentation rule alongside blank missing salaries.
- Covered by Vitest truth-table assertions (`work_model x eligibility`) and Playwright E2E checks.
