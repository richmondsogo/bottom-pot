# Skills Reference: Bottom Pot

This document catalogs the skills available in this repository (`.agents/skills/`) and environment-level skills, outlining their usage for recurring engineering workflows.

---

## Project-Local Skills (`.agents/skills/`)

### 1. Project Initialization & Architecture
| Skill | Location | Purpose |
|---|---|---|
| `project-bootstrap` | `.agents/skills/project-bootstrap/SKILL.md` | Guides adoption of starter repository assets, directory conventions, and baseline planning. |
| `design-system` | `.agents/skills/design-system/SKILL.md` | Ensures strict adherence to the square design system (radius: 0, cream/green tokens, typography). |
| `frontend-design` | `.agents/skills/frontend-design/SKILL.md` | Directs production of editorial, minimal, and high-craft UI layouts avoiding AI-template cliches. |

### 2. Engineering Workflow (Matt Pocock Skills)
| Skill | Location | Purpose |
|---|---|---|
| `ask-matt` | `.agents/skills/ask-matt/SKILL.md` | Workflow router to direct which engineering skill to execute. |
| `to-spec` | `.agents/skills/to-spec/SKILL.md` | Turn requirements and conversations into actionable design specs. |
| `implement` | `.agents/skills/implement/SKILL.md` | Implementation cycle driven by tests and closed with code review. |
| `tdd` | `.agents/skills/tdd/SKILL.md` | Test-driven development loop for pure frontend/backend logic. |
| `code-review` | `.agents/skills/code-review/SKILL.md` | Automated two-axis review (Standards + Spec) on staged diffs. |
| `diagnosing-bugs` | `.agents/skills/diagnosing-bugs/SKILL.md` | Systematic bug isolation and reproduction before patching. |
| `prototype` | `.agents/skills/prototype/SKILL.md` | Fast throwaway experiments for uncertain UI or logic questions. |
| `triage` | `.agents/skills/triage/SKILL.md` | Triage incoming issues and structure actionable briefs. |

### 3. Bottom Pot Domain & UI Primitives
| Skill | Location | Purpose |
|---|---|---|
| `parser-change` | `.agents/skills/parser-change/SKILL.md` | Governs all scraping and parsing changes in `src/project_files/`. Requires real posting fixtures. |
| `motion` | `.agents/skills/motion/SKILL.md` | Governs animations with Framer Motion / Motion. Ensures restrained, performant transitions. |
| `migrate-radix-to-base` | `.agents/skills/migrate-radix-to-base/SKILL.md` | Primitives migration and headless component wiring for Base UI. |
| `shadcn` | `.agents/skills/shadcn/SKILL.md` | Component composition using Base UI / shadcn patterns under 0-radius constraints. |
| `browser-verification` | `.agents/skills/browser-verification/SKILL.md` | Multi-viewport screenshot and interaction verification using Playwright. |

---

## Fallback & Manual Handling

If an agent or environment cannot natively execute a specialized skill directly through subagent routing, the agent must manually inspect the corresponding `SKILL.md` file and follow its instructions sequentially.
