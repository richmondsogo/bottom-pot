---
name: frontend-design
description: Guidance for distinctive, intentional visual design when building new UI or reshaping an existing one. DESIGN.md and frontend/src/index.css are the authoritative source of truth for Bottom Pot's palette, typography, spacing, and soft-square geometry.
license: Complete terms in LICENSE.txt
---

# Frontend Design

> **Source of truth:** For Bottom Pot, [`DESIGN.md`](../../DESIGN.md) and [`frontend/src/index.css`](../../frontend/src/index.css) are the authoritative source of truth for palette, typography (`Geist Variable` + `DM Mono`), spacing, motion tokens, and soft-square radius scale (`--radius-sm: 4px`, `--radius-md: 6px`, `--radius-lg: 8px`, `0px` on the results table and hairlines per `ADR 0036`). Follow `DESIGN.md` without overriding its established visual system.

## Ground your designs in the subject matter

Build with Bottom Pot's real job-discovery domain and candidate-first purpose: direct employer apply links, clear country eligibility, honest unknown states, and zero aggregator clutter. Let the hierarchy carry the weight rather than decorative chrome.

## Design principles

Typography carries the personality of the page. Follow the scale and two-family system in `DESIGN.md` (`Geist Variable` for UI and headings, `DM Mono` strictly for lowercase machine slugs, shortcut hints, and tabular counts/numbers).

Default to readable line lengths (under 80 characters, `max-w-[60ch]` for leads).

Avoid these default typographic treatments; they are the commonest tells of a generated page:
- Accenting just a single word or phrase in a headline, like putting one word in italic/bold or a different color.
- Using all caps for labels.
- Adding unnecessary typographic labels above content.

Visual structure is information. Structural devices like hairlines, borders, dividers, and labels encode useful hierarchy rather than decorating the page. Numbered markers (`01` / `02` / `03`) are only appropriate when the content actually is a sequence.

Use non-user-triggered motion sparingly and deliberately, staying within the token budget in `frontend/src/index.css` (`120ms–220ms`, GPU-only `transform` and `opacity`, always respecting `prefers-reduced-motion`). Motion that answers a person's action (opening, expanding, confirming) is welcome when it shows what changed.

## Process: plan, review against `DESIGN.md`, build, critique

Before building new UI or reshaping a screen, review the plan against `DESIGN.md` and `docs/FRONTEND.md`:
- Reuse existing `frontend/src/index.css` tokens (`--bg`, `--surface`, `--ink`, `--ink-muted`, `--ink-subtle`, `--accent`, `--border`) and `frontend/src/components/ui/` primitives rather than inventing new colors, fonts, or custom radii.
- Check layout alignment against `--page-max: 1160px` and `--page-gutter`.
- Keep CSS selectors properly layered inside `@layer base` or Tailwind utilities.

## Restraint and self-critique

Keep the workspace calm and disciplined, and cut any decoration that does not serve the candidate. Build to a quality floor without announcing it: responsive down to `390px`, visible keyboard focus (`:focus-visible`), `prefers-reduced-motion` respected, WCAG AA contrast in both light and dark themes. Critique your own work visually across viewports using screenshots before finishing.

## More on writing in design

Words appear in a design for one reason: to make it easier to understand and use. They are design content, not decoration. Bring the same intentionality and minimalism to copywriting that you would bring to spacing and color.

Write from the end user's perspective in plain language, not by how the system is built. Never expose backend jargon (`ATS adapters`, `career tenants`, `JSON/XML`, `GraphQL`, `mailto domains`) or competitor names on user-facing routes.

Use active voice as default. Keep labels consistent across triggers, actions, and confirmation toasts.

Treat failure and emptiness as moments for direction, not mood. Explain what went wrong and how to fix it clearly without apologizing or inventing missing data.

Keep the tone conversational: plain verbs, sentence case, no filler, and no prose em dashes. Let each written element do exactly one job.
