# Skills Reference: Bottom Pot

This document catalogs the skills available in this repository (`.agents/skills/`) and environment-level skills, outlining their usage for recurring engineering workflows.

---

## Project-Local Skills (`.agents/skills/`)

### 1. Design & UI Craft
| Skill | Location | Purpose |
|---|---|---|
| `design-system` | `.agents/skills/design-system/SKILL.md` | Ensures adherence to the soft-square design system (`4px`/`6px`/`8px` radius scale + square tables/hairlines/detail panel, cream/green tokens, typography) defined in [`DESIGN.md`](../../DESIGN.md) and [`frontend/src/index.css`](../../frontend/src/index.css). |
| `frontend-design` | `.agents/skills/frontend-design/SKILL.md` | Directs production of editorial, minimal, and high-craft UI layouts aligned with `DESIGN.md`. |

### 2. Engineering Workflow
| Skill | Location | Purpose |
|---|---|---|
| `tdd` | `.agents/skills/tdd/SKILL.md` | Test-driven development loop for pure frontend/backend logic. |
| `code-review` | `.agents/skills/code-review/SKILL.md` | Automated two-axis review (Standards + Spec) on staged diffs. |
| `diagnosing-bugs` | `.agents/skills/diagnosing-bugs/SKILL.md` | Systematic bug isolation and reproduction before patching. |

### 3. Bottom Pot Domain & UI Primitives
| Skill | Location | Purpose |
|---|---|---|
| `parser-change` | `.agents/skills/parser-change/SKILL.md` | Governs all scraping and parsing changes across `src/ats/`, `src/discovery/`, and `src/extraction/`. Requires real posting fixtures. |
| `motion` | `.agents/skills/motion/SKILL.md` | Governs animations with Motion and CSS animation. Ensures restrained, performant transitions. |
| `shadcn` | `.agents/skills/shadcn/SKILL.md` | Component composition using Base UI / shadcn patterns aligned with the soft-square radius scale in [`DESIGN.md`](../../DESIGN.md) and [`frontend/src/index.css`](../../frontend/src/index.css). |
| `browser-verification` | `.agents/skills/browser-verification/SKILL.md` | Multi-viewport screenshot and interaction verification using Playwright. |

---

## Fallback & Manual Handling

If an agent or environment cannot natively execute a specialized skill directly through subagent routing, the agent must manually inspect the corresponding `SKILL.md` file and follow its instructions sequentially.
