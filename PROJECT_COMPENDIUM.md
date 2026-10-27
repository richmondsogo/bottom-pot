# Bottom Pot: The Definitive System Compendium & Project Bible

> **The Authoritative Single-Source Reference for Bottom Pot**  
> *Consolidating all `.agents` skills, Model Context Protocol (MCP) integrations, Architecture Decision Records (ADRs 0001–0021), `DESIGN.md` visual specifications, technical constraints, and architectural concessions.*

---

## Table of Contents

1. [Executive Overview & Product Mission](#1-executive-overview--product-mission)
2. [Agent Operating Agreement & Order of Precedence](#2-agent-operating-agreement--order-of-precedence)
3. [Complete Inventory of Local Agent Skills (`.agents/skills/`)](#3-complete-inventory-of-local-agent-skills-agentsskills)
   - [3.1 ask-matt](#31-ask-matt)
   - [3.2 browser-verification](#32-browser-verification)
   - [3.3 code-review](#33-code-review)
   - [3.4 design-system](#34-design-system)
   - [3.5 diagnosing-bugs](#35-diagnosing-bugs)
   - [3.6 frontend-design](#36-frontend-design)
   - [3.7 implement](#37-implement)
   - [3.8 migrate-radix-to-base](#38-migrate-radix-to-base)
   - [3.9 motion](#39-motion)
   - [3.10 parser-change](#310-parser-change)
   - [3.11 project-bootstrap](#311-project-bootstrap)
   - [3.12 prototype](#312-prototype)
   - [3.13 shadcn](#313-shadcn)
   - [3.14 tdd](#314-tdd)
   - [3.15 to-spec](#315-to-spec)
   - [3.16 triage](#316-triage)
   - [3.17 ui-ux-pro-max](#317-ui-ux-pro-max)
4. [Model Context Protocol (MCP) Reference & Boundaries](#4-model-context-protocol-mcp-reference--boundaries)
   - [4.1 Active Project & Environment MCP Servers](#41-active-project--environment-mcp-servers)
   - [4.2 Explicitly Out-of-Scope MCP Servers](#42-explicitly-out-of-scope-mcp-servers)
   - [4.3 Configuration & Operational Security Rules](#43-configuration--operational-security-rules)
5. [Complete Catalog of Architecture Decision Records (ADRs 0001–0021)](#5-complete-catalog-of-architecture-decision-records-adrs-00010021)
   - [ADR 0000: Architecture Decision Record Template](#adr-0000-architecture-decision-record-template)
   - [ADR 0001: Unknown Beats Wrong](#adr-0001-unknown-beats-wrong)
   - [ADR 0002: Work Model Source Ladder and Provenance](#adr-0002-work-model-source-ladder-and-provenance)
   - [ADR 0003: Backend Owns Parsing](#adr-0003-backend-owns-parsing)
   - [ADR 0004: Square Design System and Daybreak Craft Direction](#adr-0004-square-design-system-and-daybreak-craft-direction)
   - [ADR 0005: Client-Side Visited State and Results Persistence](#adr-0005-client-side-visited-state-and-results-persistence)
   - [ADR 0006: Results Detail Panel and Keyboard Navigation](#adr-0006-results-detail-panel-and-keyboard-navigation)
   - [ADR 0007: No Framework Migration and Frontend Architecture](#adr-0007-no-framework-migration-and-frontend-architecture)
   - [ADR 0008: Backend API Recommendations for Frontend UX](#adr-0008-backend-api-recommendations-for-frontend-ux)
   - [ADR 0009: shadcn/ui Foundation and Base UI Component Architecture](#adr-0009-shadcnui-foundation-and-base-ui-component-architecture)
   - [ADR 0010: Typography System and Font Selection (Geist Sans + DM Mono)](#adr-0010-typography-system-and-font-selection-geist-sans--dm-mono)
   - [ADR 0011: Unified Page Shell and Left Alignment (Superseded by ADR 0020)](#adr-0011-unified-page-shell-and-left-alignment-superseded-by-adr-0020)
   - [ADR 0012: Two-Line List Architecture Replacing Boxed Tables (Superseded by ADR 0019)](#adr-0012-two-line-list-architecture-replacing-boxed-tables-superseded-by-adr-0019)
   - [ADR 0013: Command Palette (Cmd+K) and Chrome Discipline](#adr-0013-command-palette-cmdk-and-chrome-discipline)
   - [ADR 0014: Native Motion, View Transitions API, and Rejection of Scroll-Jacking (Lenis)](#adr-0014-native-motion-view-transitions-api-and-rejection-of-scroll-jacking-lenis)
   - [ADR 0015: Theme System and Dark Mode Contrast](#adr-0015-theme-system-and-dark-mode-contrast)
   - [ADR 0016: Safe Company Display Name Cleanup](#adr-0016-safe-company-display-name-cleanup)
   - [ADR 0017: Layout and Spacing Overhaul (Pass 2 Craft Refinement)](#adr-0017-layout-and-spacing-overhaul-pass-2-craft-refinement)
   - [ADR 0018: Root Cause and Fix of Missing Padding and Margins (Unlayered CSS Resets)](#adr-0018-root-cause-and-fix-of-missing-padding-and-margins-unlayered-css-resets)
   - [ADR 0019: Table Layout with Fixed Column Alignment Over Two-Line List Rows](#adr-0019-table-layout-with-fixed-column-alignment-over-two-line-list-rows)
   - [ADR 0020: Unified Page Shell and Centered Hero Layout](#adr-0020-unified-page-shell-and-centered-hero-layout)
   - [ADR 0021: Platform Chip Neutral Selection and Green Accent Budget](#adr-0021-platform-chip-neutral-selection-and-green-accent-budget)
6. [Design Philosophy, Visual Language & Token System (`DESIGN.md`)](#6-design-philosophy-visual-language--token-system-designmd)
   - [6.1 Core Principles](#61-core-principles)
   - [6.2 Visual Language & Identity](#62-visual-language--identity)
   - [6.3 Typography System](#63-typography-system)
   - [6.4 Spacing Scale & Page Metrics](#64-spacing-scale--page-metrics)
   - [6.5 Fixed Table Architecture](#65-fixed-table-architecture)
   - [6.6 Banned Patterns](#66-banned-patterns)
7. [Comprehensive Constraints, Concessions & Architectural Trade-offs](#7-comprehensive-constraints-concessions--architectural-trade-offs)
   - [7.1 Data & Scraping Integrity Concessions](#71-data--scraping-integrity-concessions)
   - [7.2 Frontend & UI System Concessions](#72-frontend--ui-system-concessions)
   - [7.3 Infrastructure, Caching & Budget Concessions](#73-infrastructure-caching--budget-concessions)
   - [7.4 Development Process & Git Workflow Concessions](#74-development-process--git-workflow-concessions)
8. [Backend Configuration & Operational Knobs (`src/config.py`)](#8-backend-configuration--operational-knobs-srcconfigpy)
9. [Build Protocol & Quality Verification Suite](#9-build-protocol--quality-verification-suite)

---

## 1. Executive Overview & Product Mission

**Bottom Pot** is an ATS-first job discovery engine designed for software engineers, product designers, and technology professionals seeking high-signal, direct-to-company opportunities without aggregator spam. It specializes in finding verified remote roles and opportunities open to Nigerian and international tech talent.

### The Core Problem
Mainstream job boards and aggregators (LinkedIn, Indeed, generic scrapers) are saturated with stale ghost jobs, duplicate reposts, affiliate click-farms, and stripped requisition metadata. Bottom Pot bypasses aggregator middlemen by querying public Applicant Tracking Systems (Greenhouse, Lever, Ashby, Workable, Recruitee, SmartRecruiters, and 14+ others) directly via Google dork queries over Serper.dev, streaming fresh job listings to the browser via HTTP Server-Sent Events (SSE).

### Product Principles
1. **Accurate Job Data Without Fabrication**: Missing fields stay `null`/`unknown`. The engine never invents data or guesses.
2. **Reliable, Resilient Scraping Pipelines**: Multi-tiered extraction (JSON-LD → ATS APIs → source adapters → DOM → LLM fallback) with per-host concurrency control and circuit breakers.
3. **Calm, Editorial, Square Typography-First UX**: A 0-radius square aesthetic inspired by Daybreak and Brian Lovin, eliminating visual noise, status bloat, and developer jargon.
4. **Fast SSE Streaming**: Immediate client-side rendering of initial listings while downstream ATS queries complete.
5. **Auditable Confidence**: Every derived work model records exact source tier and literal evidence snippets.

---

## 2. Agent Operating Agreement & Order of Precedence

When autonomous or human agents operate in this repository, instructions must be resolved in this strict order:

1. **User instructions** in the active prompt (highest priority).
2. **`AGENTS.md` & `BUILD_PROTOCOL.md`** (Repository operating agreements & build protocol).
3. **`CONTEXT.md` & `DESIGN.md`** (Domain context and visual design system).
4. **Project-local skills** (`.agents/skills/`).
5. **Environment skills & general defaults** (lowest priority).

### The Primary Operating Rules
- **Never commit directly to `main`**: All work occurs on isolated branches (`step/NN-<slug>`).
- **Standard Merge Commits (`--no-ff`)**: Pull requests merge with `--no-ff` to preserve granular commit history; never squash or rebase.
- **Merge Policy**: Agents open pull requests but do NOT merge them unless explicitly commanded ("merge when green").
- **Windows PowerShell Compatibility**: All automation and terminal scripts must run natively in Windows PowerShell (`pwsh`).
- **Zero Credential Commits**: Never log, display, or commit API keys or secret files.
- **Backend Invariance**: Redesign or frontend updates must NEVER alter backend search endpoints, query parameters, or response contracts without an approved ADR.

---

## 3. Complete Inventory of Local Agent Skills (`.agents/skills/`)

Bottom Pot maintains 17 specialized skills within `.agents/skills/` governing engineering workflows, design rules, scraping policies, and testing.

### 3.1 `ask-matt`
- **Location**: `.agents/skills/ask-matt/SKILL.md`
- **Purpose**: The primary router over the repository's engineering skills. Guides agents and developers to the right workflow based on the current situation.
- **Core Flows**:
  - **Main Flow (Idea → Ship)**: `/grill-with-docs` (interview & ADR record) → Detour to `/prototype` (if runnable answers needed) → `/to-spec` (spec & ticket generation) → `/implement` (one ticket at a time via `/tdd`) → `/code-review` (two-axis review) → `/pr` → `/retro`.
  - **On-Ramps**: Bugs/requests piling up → `/triage`; Something is broken → `/diagnosing-bugs`.
  - **Codebase Health**: `/improve-codebase-architecture` for deepening opportunities.
  - **Vocabulary Layers**: `/domain-modeling` (glossary/ADR definitions) and `/codebase-design` (deep modules, seams, adapters).
  - **Context Hygiene**: Maintain steps 1–3 in an unbroken context window; start fresh per `/implement` ticket.

### 3.2 `browser-verification`
- **Location**: `.agents/skills/browser-verification/SKILL.md`
- **Purpose**: Repeatable browser verification workflow for visual and interactive changes. Enforces visual proof before declaring UI tasks complete.
- **8-Step Verification Loop**:
  1. *Start the application*: Start Vite/Uvicorn dev server and confirm zero boot errors.
  2. *Navigate to affected routes*: Check primary, adjacent, and linking views (not just happy paths).
  3. *Verify important interactions*: Click buttons, trigger all states (loading, empty, error), test focus and keyboard navigation.
  4. *Check rendered states*: Idle, Loading, Empty, Error, Success.
  5. *Check responsive behavior*: 5 core viewports (1920x1080, 1440x900, 1024x768, 768x1024, 390x844).
  6. *Inspect computed styles*: Confirm computed padding, margin, height, and color tokens via DevTools.
  7. *Capture evidence*: Capture full-resolution screenshots via Playwright.
  8. *Report actual results*: Document what was inspected, what passed, and what failed in `docs/steps/`.

### 3.3 `code-review`
- **Location**: `.agents/skills/code-review/SKILL.md`
- **Purpose**: Automated two-axis review of diffs against a fixed point (commit, branch, or merge-base).
- **Two Distinct Axes**:
  - **Standards**: Does the code conform to documented repo standards (`CODING_STANDARDS.md`, `DESIGN.md`) and the Fowler smell baseline?
  - **Spec**: Does the code faithfully implement what the issue/spec requested without scope creep?
- **Fowler Code Smell Baseline**: Checks for *Mysterious Name*, *Duplicated Code*, *Feature Envy*, *Data Clumps*, *Primitive Obsession*, *Repeated Switches*, *Shotgun Surgery*, *Divergent Change*, *Speculative Generality*, *Message Chains*, *Middle Man*, and *Refused Bequest*.
- **Subagent Parallelism**: Runs both axes in parallel subagents to prevent context pollution, aggregating findings under separate headings without cross-axis reranking.

### 3.4 `design-system`
- **Location**: `.agents/skills/design-system/SKILL.md`
- **Purpose**: The authoritative implementation rulebook for Bottom Pot UI. Enforces square geometry, token consistency, and Daybreak craft principles.
- **Core Directives**:
  - Strict `--radius: 0` (`rounded-none`) across all controls, containers, tooltips, and focus rings.
  - Zero unlayered global CSS; all resets must reside strictly in `@layer base`.
  - Single unified page shell (`--page-max: 1160px; --page-gutter: 32px`).
  - Two-family typography: Geist Variable (UI/display) and DM Mono (lowercase machine slugs, counts, shortcuts).
  - Semantic fixed table layout with pixel-aligned cell and header padding (`py-3.5 px-3.5`).
  - Strict green budget: forest green (`#1A382B` / `#34D399`) reserved for primary CTA, checkmarks, remote tags, 2px row hover bar, and focus rings.

### 3.5 `diagnosing-bugs`
- **Location**: `.agents/skills/diagnosing-bugs/SKILL.md`
- **Purpose**: Rigorous 6-phase diagnostic loop for hard bugs, race conditions, and performance regressions.
- **Six Phases**:
  1. *Build a feedback loop*: Construct a fast, deterministic, agent-runnable command that goes red specifically on the symptom.
  2. *Reproduce & minimise*: Shrink inputs, steps, and data until every remaining element is strictly load-bearing.
  3. *Hypothesise*: Formulate 3–5 falsifiable, ranked hypotheses stating concrete predictions.
  4. *Instrument*: Target boundaries with tagged logs (`[DEBUG-uuid]`) or breakpoints, changing one variable at a time.
  5. *Fix & regression test*: Write a failing regression test at the correct seam before fixing code.
  6. *Cleanup*: Verify original repro passes, delete debug logs, and document the root cause.

### 3.6 `frontend-design`
- **Location**: `.agents/skills/frontend-design/SKILL.md`
- **Purpose**: Directs production of distinctive, intentional, and non-cliché visual identities.
- **Core Principles**:
  - Avoid AI template tropes: generic cream/terracotta combos, uniform rounded cards, tracked all-caps eyebrows, and meaningless decorative gradients.
  - Ground layout in subject matter: tech job discovery requires density, precision, and scannability.
  - Typographic restraint: line lengths <80ch, intentional type scales, and active voice copywriting.
  - Restraint: spend boldness in one focal area; keep surrounding chrome disciplined and quiet.

### 3.7 `implement`
- **Location**: `.agents/skills/implement/SKILL.md`
- **Purpose**: Drives test-driven implementation from approved specs or tickets.
- **Workflow**:
  - Implement agreed slices via `/tdd` at verified public seams.
  - Regularly run typechecking and single test suites.
  - Run the full test suite (`scripts/verify.ps1`) upon completion.
  - Close out with `/code-review` before committing to the step branch.

### 3.8 `migrate-radix-to-base`
- **Location**: `.agents/skills/migrate-radix-to-base/SKILL.md`
- **Purpose**: Safe migration of React components and shadcn wrappers from Radix UI to `@base-ui/react`.
- **Methodology**:
  - Prefer the **Golden Pair** via the shadcn CLI: diff stock origin against base variants (`base-<style>`).
  - Use `git merge-file` for three-way merging of customized wrappers.
  - Mandatory leftover sweep (`grep -n "radix-ui\|@radix-ui"`).
  - Progressive migration via `<component>-base.tsx` before repointing consumers.
  - Map non-equivalent primitives: AspectRatio → CSS div; Label → native `<label>`; VisuallyHidden → `sr-only`.

### 3.9 `motion`
- **Location**: `.agents/skills/motion/SKILL.md`
- **Purpose**: Governs animations, transitions, and motion performance using Motion (formerly Framer Motion) and native CSS.
- **Key Rules**:
  - Enforce restrained durations (120ms–180ms ease-out).
  - Use native View Transitions API (`document.startViewTransition`) for route and view switches.
  - Guard all transitions with `@media (prefers-reduced-motion: reduce)`.
  - Strictly avoid scroll-jacking libraries (Lenis is explicitly banned).

### 3.10 `parser-change`
- **Location**: `.agents/skills/parser-change/SKILL.md`
- **Purpose**: Governs all modifications to job extraction, URL parsing, and field normalization in `src/project_files/`.
- **Mandatory Principles**:
  - *Unknown beats wrong*: Absence of evidence yields `None`. Never default to `in_person`.
  - *Provenance is mandatory*: Derived fields must store source tier and literal evidence text.
  - *Backend owns parsing*: Frontend never regex-mutates titles, snippets, or locations.
  - *Real fixtures only*: Every test must run against real HTML/JSON captured via `scripts/capture_fixtures.py` (stored in `tests/fixtures/real/`). No synthetic mock HTML.
  - *Evaluate golden labels*: Run `python scripts/eval_work_model.py` to check accuracy regressions.

### 3.11 `project-bootstrap`
- **Location**: `.agents/skills/project-bootstrap/SKILL.md`
- **Purpose**: Structured foundation setup for projects copying from the engineering starter.
- **Process**:
  - Understand operating agreements (`AGENTS.md`, `BUILD_PROTOCOL.md`).
  - Fill `CONTEXT.md` completely (domain terms, actors, constraints, non-goals) before writing code.
  - Select stacks without speculative dependencies.
  - Establish step 0 planning in `docs/steps/00-plan.md`.

### 3.12 `prototype`
- **Location**: `.agents/skills/prototype/SKILL.md`
- **Purpose**: Rapid creation of throwaway code to answer specific design or logic questions.
- **Two Branches**:
  - *State / Logic*: Single runnable HTML file exercising edge cases and state machines.
  - *UI / Look*: Single route rendering radically different visual treatments switchable via query params.
- **Rules**: Zero persistence, skip tests/polish, locate near production files with clear prototype naming, and fold only validated decisions into `main`.

### 3.13 `shadcn`
- **Location**: `.agents/skills/shadcn/SKILL.md`
- **Purpose**: Authoritative guide for adding, composing, and styling shadcn primitives on `@base-ui/react`.
- **Composition Rules**:
  - Use existing primitives before writing custom markup (e.g., `Empty` for empty states, `Separator` for rules).
  - Forms use `FieldGroup` + `Field` + `FieldLabel` + `Input` with `data-invalid` / `aria-invalid`.
  - Never override colors via raw hex classes; use semantic tokens (`bg-background`, `text-muted-foreground`).
  - Enforce `--radius: 0` globally.

### 3.14 `tdd`
- **Location**: `.agents/skills/tdd/SKILL.md`
- **Purpose**: Test-Driven Development reference governing the red → green → refactor cycle.
- **Core Rules**:
  - Test behavior through public interfaces (seams), never implementation internals.
  - Agree on seams with the user before writing tests.
  - Vertical slices only (one test → minimal code → repeat). Avoid horizontal slicing (writing bulk tests upfront).
  - Red before green: watch tests fail before implementing.

### 3.15 `to-spec`
- **Location**: `.agents/skills/to-spec/SKILL.md`
- **Purpose**: Synthesizes active conversation and codebase context into an actionable engineering spec.
- **Template Sections**: Problem Statement, Solution, Long Numbered User Stories, Implementation Decisions (architectural changes without fragile line numbers), Testing Decisions (seams and assertions), Out of Scope, and Further Notes.

### 3.16 `triage`
- **Location**: `.agents/skills/triage/SKILL.md`
- **Purpose**: Moves incoming issues and external pull requests through a formal triage state machine.
- **Roles**:
  - Category: `bug` or `enhancement`.
  - States: `needs-triage` → `needs-info`, `ready-for-agent`, `ready-for-human`, or `wontfix`.
- **Agent Briefs**: Produces self-contained, implementation-agnostic briefs with context, acceptance criteria, out-of-scope items, testing seams, and primary reference links.

### 3.17 `ui-ux-pro-max`
- **Location**: `.agents/skills/ui-ux-pro-max/SKILL.md`
- **Purpose**: Searchable UI/UX design intelligence spanning 50+ styles, 192 product palettes, 119 UX guidelines, and 22 technology stacks.
- **Priority Stack**: Accessibility (CRITICAL) → Touch & Interaction (CRITICAL) → Performance (HIGH) → Style Selection (HIGH) → Layout & Responsive (HIGH) → Typography & Color (MEDIUM) → Animation (MEDIUM) → Forms & Feedback (MEDIUM) → Navigation (HIGH) → Charts (LOW).
- **Tooling**: Invokes local search script with `--design-system`, `--domain`, or `--stack` flags to pull verified design recipes.

---

## 4. Model Context Protocol (MCP) Reference & Boundaries

The repository operates in an Antigravity environment with strict MCP boundary constraints documented in `docs/agents/mcps.md`.

### 4.1 Active Project & Environment MCP Servers

| MCP Server | Integration Status | Role & Operational Boundary Rules |
| :--- | :--- | :--- |
| **`github-mcp-server`** | Active | Branch management, file reading, pull request creation, and issue comment updates. Must respect `MERGE_POLICY`: open PRs, do NOT merge without explicit approval. |
| **`playwright`** | Active | Multi-viewport headless browser execution, DOM inspection, user interaction emulation, and full-resolution screenshot capture. |
| **`chrome-devtools-mcp`** | Active | Performance audits, Lighthouse assessments, console log verification, layout shift measurements (CLS), and accessibility auditing. |
| **`shadcn`** | Active | Searching, inspecting, and retrieving shadcn/Base UI component source patterns. Enforces `--radius: 0` on all retrieved assets. |
| **`context7`** | Active | Fetching real-time upstream documentation for active libraries (Tailwind CSS v4, Base UI, Lucide). |
| **`gemini-api-docs`** | Active | Upstream API documentation search and reference. |
| **`awwwards`** | Active | Design brief analysis, page structure inspection, and motion DNA reference. |

### 4.2 Explicitly Out-of-Scope MCP Servers

| Server | Status | Boundary Constraint Rationale |
| :--- | :--- | :--- |
| **`Neon`** | *STRICTLY OUT OF SCOPE* | Bottom Pot uses local SQLite caching (`data/cache.sqlite`). Cloud Postgres is prohibited per project constraints; never invoke Neon tools. |
| **`Vercel`** | *STRICTLY OUT OF SCOPE* | Cloud hosting and unsolicited deployments are forbidden. All testing runs locally; never deploy to Vercel. |

### 4.3 Configuration & Operational Security Rules
1. **Local Configuration**: `.agents/mcp_config.json` is gitignored. The template is provided in `.agents/mcp_config.json.example`.
2. **Zero Credential Commits**: Never commit credentials, auth tokens, or API keys. Environment variables (`${API_KEY}`) must be used exclusively.
3. **No Unsolicited Hosting**: Never execute cloud provisioning, DNS modifications, or hosting mutations.

---

## 5. Complete Catalog of Architecture Decision Records (ADRs 0001–0021)

### ADR 0000: Architecture Decision Record Template
- **Status**: Template
- **Context**: Standardized format for capturing architectural decisions (`Title`, `Status`, `Context`, `Decision`, `Consequences`). Ensures decisions are recorded systematically rather than expensively rediscovered.

---

### ADR 0001: Unknown Beats Wrong
- **Status**: Accepted (2026-10-15)
- **Context**: Scraping systems frequently applied implicit defaults when evidence was absent (e.g., assuming a physical city implied `in_person`, or `is_remote: false` proved on-site work). This generated false classifications that misled job seekers filtering for remote roles.
- **Decision**:
  1. No fallback mechanism or heuristic may turn absence of evidence into an invented value.
  2. If evidence is missing, ambiguous, or contradictory, the parser returns `None` (`null`).
  3. Negative inferences (such as `is_remote=False` proving `in_person`) are strictly banned.
  4. Frontend and downstream APIs must treat `None` as a neutral first-class state ("Not specified").
- **Consequences**: Eliminates false positives, establishes candidate trust, and forces UI components to handle unclassified data gracefully.

---

### ADR 0002: Work Model Source Ladder and Provenance
- **Status**: Accepted (2026-10-15)
- **Context**: Job postings convey work model across conflicting tiers (APIs, JSON-LD, location strings, titles, freeform text). Earlier parsers allowed noisy freeform text to override structured ATS metadata without an audit trail.
- **Decision**:
  Resolution proceeds strictly down a deterministic 7-tier priority ladder:
  1. `api_enum`: Explicit ATS workplace enum (e.g., Ashby `workplaceType`, Lever `workplaceType`).
  2. `jsonld`: Schema.org `JobPosting.jobLocationType` (e.g., `TELECOMMUTE`).
  3. `li_tag`: Recruiter tags `#LI-(Remote|Hybrid|Onsite)` in trusted descriptions. Multiple tags resolve to `None`.
  4. `location`: Explicit prefix or token in location string (`Remote`, `Hybrid`).
  5. `title`: Delimited title token (`[Remote]`, `(Hybrid)`).
  6. `description`: Scanned body text with negation boundaries, evaluated **only** when `description_ok` passes quality gates.
  7. `None`: Absence of evidence yields `None`.
  *Provider boolean flags (`isRemote: true`) are excluded entirely* because platforms like Ashby set them for hybrid jobs.
  Every derived field must record `value`, `source`, and literal `evidence`.
- **Consequences**: Eliminates false-positive remote jobs, preserves recruiter tag fidelity, and provides explainable tooltips in the UI.

---

### ADR 0003: Backend Owns Parsing
- **Status**: Accepted (2026-10-15)
- **Context**: Frontend code previously ran client-side regexes over job titles and snippets to infer remote status or strip company prefixes. This created split-brain behavior where backend fixes did not reflect in the UI and stripped field provenance.
- **Decision**:
  1. The backend pipeline exclusively owns all parsing, extraction, normalization, and derivation.
  2. The frontend is presentation-only and must never run heuristics or regexes over raw descriptions.
  3. The backend delivers normalized fields with explicit provenance metadata.
  4. Client filters operate strictly on structured backend fields (`job.work_model === "remote"`).
- **Consequences**: Single source of truth, testable backend transforms with real fixtures, and reduced frontend bundle complexity.

---

### ADR 0004: Square Design System and Daybreak Craft Direction
- **Status**: Accepted (2026-10-16)
- **Context**: Initial UI suffered from AI-prototype sprawl: status chrome bloat, leaking developer jargon ("GET /search"), uppercase mono eyebrows, card-in-card nesting, and pill-shaped badges conflicting with the square "BP" brandmark.
- **Decision**:
  1. Non-negotiable square geometry: `--radius: 0` on every component, button, input, tag, and modal.
  2. Daybreak craft transfer: typography-first hierarchy, high-contrast dark ink (`#181816`), warm cream background (`#FAF8F5`), forest green accent (`#1A382B`), and 1px hairlines.
  3. Chrome discipline: collapse multi-band banners into a single quiet status strip; collapse the hero into a compact 40px bar on search completion.
  4. Deterministic square monograms (28x28px) derived from company names.
- **Consequences**: High-density, calm editorial reading experience suitable for senior engineers; visual clutter eliminated.

---

### ADR 0005: Client-Side Visited State and Results Persistence
- **Status**: Accepted (2026-10-16)
- **Context**: Users repeatedly re-opened postings they had already reviewed, and page refreshes triggered expensive, redundant Serper API queries that exhausted the daily search budget.
- **Decision**:
  1. Visited tracking: Opened job URLs/IDs are recorded in `localStorage` under `bp.visited`. Visited titles are visually dimmed to `--ink-subtle` (60% opacity).
  2. Results persistence: Recent search results and metrics are cached in `localStorage` under `bp.savedResults` with a hard ~3 MB quota cap. On refresh, the app restores results instantly with a `"Saved 1d ago"` status strip.
- **Consequences**: Diminished user fatigue, protection of Serper search credits, and graceful error handling in private browsing modes.

---

### ADR 0006: Results Detail Panel and Keyboard Navigation
- **Status**: Accepted (2026-10-16)
- **Context**: Expanding inline accordion rows displaced table content and caused layout thrash. Dense list navigation was tedious with mouse-only clicking.
- **Decision**:
  1. Slide-out detail sheet: Selecting a job opens an anchored 480px right-side sheet on desktop (bottom sheet on mobile). Postings open without shifting table rows.
  2. Keyboard navigation: `j`/`k` (move active row), `Enter`/`o` (open detail sheet or link), `Esc` (dismiss), `/` (focus search), and `?` (shortcuts modal).
- **Consequences**: Rapid power-user browsing, fluid navigation, and complete layout stability.

---

### ADR 0007: No Framework Migration and Frontend Architecture
- **Status**: Accepted (2026-10-16)
- **Context**: Pressure to migrate to Next.js or other SSR frameworks conflicted with the project constraint to keep the frontend simple, approachable, and stable.
- **Decision**:
  1. Stack invariance: Retain React 19 + Vite 8 + TypeScript + Tailwind CSS v4 + `@base-ui/react`.
  2. Decompose monolithic `App.tsx` into single-purpose components (`Header`, `SearchForm`, `ResultsTable`, `Toolbar`, `DetailSheet`).
  3. Extract business logic into pure, tested modules (`normalize.ts`, `filter.ts`, `sort.ts`, `visited.ts`, `storage.ts`).
  4. Provide client-side mock data mode (`?mock=1`) with edge cases (Japanese characters, 150+ listings) for zero-credit testing.
- **Consequences**: Maintainable architecture, fast unit test suite (vitest), and zero build friction.

---

### ADR 0008: Backend API Recommendations for Frontend UX
- **Status**: Proposed / Informational (2026-10-17)
- **Context**: Frontend redesign identified opportunities where non-breaking backend enhancements would improve UX while respecting API invariance during active releases.
- **Recommendations**:
  1. Granular platform progress SSE events (`platform_status`) to show real-time progress per ATS board.
  2. Structured salary objects (`min`, `max`, `currency`, `period`) to enable client-side salary filtering without regex.
  3. ISO-8601 timestamps in `DoneEvent` for timezone-safe time-ago formatting.
  4. Deep-linkable search URLs via standard query parameters.
- **Consequences**: Roadmap for future backend iterations without breaking the current freeze.

---

### ADR 0009: shadcn/ui Foundation and Base UI Component Architecture
- **Status**: Accepted (2026-10-18)
- **Context**: Initial pass used hand-rolled divs and bespoke classes, resulting in inconsistent focus states and maintenance overhead.
- **Decision**:
  1. Standardize UI controls on `shadcn/ui` primitives built over `@base-ui/react` (base-nova).
  2. Add primitives via shadcn CLI into `frontend/src/components/ui/`.
  3. Enforce `--radius: 0` globally at the CSS custom property level.
- **Consequences**: Built-in accessibility (ARIA, focus-visible outlines) and standardized `cva` variant composition.

---

### ADR 0010: Typography System and Font Selection (Geist Sans + DM Mono)
- **Status**: Accepted (2026-10-18)
- **Context**: Typography had degraded into mixed sans fonts, bold monospace eyebrow tags, uppercase tracked badges, and off-scale sizes.
- **Decision**:
  1. Primary Sans: Self-hosted **Geist Variable** for all headings, body, labels, buttons, and navigation (weights 400, 500, 600).
  2. Machine Monospace: Self-hosted **DM Mono** strictly reserved for machine slugs (`lever`, `greenhouse` in lowercase), tabular numbers, and shortcut badges (`⌘K`).
  3. Sentence case everywhere; ban uppercase tracked monospace headings and badges.
- **Consequences**: Restores visual calm, eliminates font dissonance, and establishes clear distinction between human copy and machine data.

---

### ADR 0011: Unified Page Shell and Left Alignment (Superseded by ADR 0020)
- **Status**: Superseded by ADR 0020 (2026-10-18)
- **Context**: Inconsistent container widths (780px to 1216px) caused horizontal jumping during page transitions.
- **Decision**: Established a 960px left-aligned container across all views.
- **Superseded Rationale**: 960px left-alignment created excessive dead space on 1440px/1920px viewports and caused the landing hero to feel lopsided. Superseded by the 1160px centered hero shell in ADR 0020.

---

### ADR 0012: Two-Line List Architecture Replacing Boxed Tables (Superseded by ADR 0019)
- **Status**: Superseded by ADR 0019 (2026-10-18)
- **Context**: Early tables had rigid truncations and uppercase headers.
- **Decision**: Replaced tables with responsive two-line flex rows (`<JobRow>`).
- **Superseded Rationale**: Free-flowing flex rows broke columnar alignment: company, location, salary, and date badges landed at erratic horizontal positions, destroying vertical scanning. Replaced by semantic fixed table in ADR 0019.

---

### ADR 0013: Command Palette (Cmd+K) and Chrome Discipline
- **Status**: Accepted (2026-10-19)
- **Context**: Results pages suffered from button sprawl (6 competing outline buttons in the toolbar) and duplicated status banners.
- **Decision**:
  1. Consolidate status into one quiet sticky line with a "Search details" popover for Serper diagnostic metrics.
  2. Action hierarchy: One primary "Edit search" button; all secondary actions moved into an overflow DropdownMenu.
  3. Command Palette: Implement `⌘K` / `Ctrl+K` command modal for rapid keyboard execution of all actions.
- **Consequences**: Vastly reduced cognitive load while empowering keyboard-first power users.

---

### ADR 0014: Native Motion, View Transitions API, and Rejection of Scroll-Jacking (Lenis)
- **Status**: Accepted (2026-10-19)
- **Context**: Smooth scrolling is essential for editorial reading, but third-party scroll-jackers (Lenis) hijack browser threads, break trackpad inertia, break native `Ctrl+F` search, and harm accessibility.
- **Decision**:
  1. Rely 100% on native CSS: `scroll-behavior: smooth`, `scroll-padding-top: 64px`, `scrollbar-gutter: stable`.
  2. Route transitions powered by native `document.startViewTransition()` with reduced-motion fallback.
  3. Third-party scroll-jacking libraries (Lenis) are strictly banned.
- **Consequences**: 120Hz/60Hz native hardware-accelerated scrolling, zero trackpad stutter, and zero accessibility violations.

---

### ADR 0015: Theme System and Dark Mode Contrast
- **Status**: Accepted (2026-10-19)
- **Context**: Dark mode required first-class execution without compromising square geometry or WCAG AA contrast.
- **Decision**:
  1. Token-driven `.dark` theme: `#0C0D0C` obsidian canvas, `#151715` elevated surfaces, `#EDEDEA` primary ink, tuned `#2E7D52` green accent.
  2. Zero FOUT: Pre-hydration inline script in `index.html` resolves theme from `localStorage` or `matchMedia` before React mounts.
- **Consequences**: Perfect contrast compliance across all five viewports with no flashing white on reload.

---

### ADR 0016: Safe Company Display Name Cleanup
- **Status**: Accepted (2026-10-20)
- **Context**: Scraped company names from ATS slugs (e.g., `cloud-nine`, `HugeInc`) degraded typography, but mutating raw data violated ADR 0001 and risked search corruption.
- **Decision**:
  1. Display-layer transformation only: `job.company` is never mutated in state or exports.
  2. Conservative formatter: PascalCase splitting (`HugeInc` → `Huge Inc`), slug un-hyphenation (`cloud-nine` → `Cloud Nine`), technology suffix preservation (`LLC`, `Corp`, `AI`, `HQ`).
  3. Raw value always available via tooltip.
- **Consequences**: Human-readable company labels with zero risk of underlying data corruption.

---

### ADR 0017: Layout and Spacing Overhaul (Pass 2 Craft Refinement)
- **Status**: Accepted (2026-10-21)
- **Context**: Feedback revealed the layout felt cramped and "squished" due to 960px constraints and dense row padding.
- **Decision**:
  1. Widen container to 1140px with 32px desktop gutters.
  2. Open borderless hero architecture: 56px primary search input, open spacing, 3-column editorial "How it works" grid.
  3. Expanded row heights: `py-5 px-4 sm:px-6` (~68px row height) matching skeleton rows.
- **Consequences**: Layout breathes naturally on desktop displays with relaxed editorial pacing.

---

### ADR 0018: Root Cause and Fix of Missing Padding and Margins (Unlayered CSS Resets)
- **Status**: Accepted (2026-10-22)
- **Context**: Elements sat flush against borders with zero padding/margins despite Tailwind classes (`p-6`, `gap-6`, `px-4`) being compiled into the CSS bundle.
- **Diagnosis**: Universal reset `* { margin: 0; padding: 0; }` was placed in the unlayered global CSS scope. In CSS Cascade Level 4/5, unlayered styles override all `@layer` styles regardless of specificity, eradicating Tailwind's `@layer utilities`.
- **Decision**:
  1. Remove `margin: 0; padding: 0;` from `*`.
  2. Enclose all base resets inside `@layer base`.
  3. Strictly ban unlayered element/universal resets in `index.css`. Enforce via automated lint script (`scripts/lint_css_cascade.js`).
- **Consequences**: Padding, margins, and gaps restored instantly; eliminated all `!important` utility workarounds.

---

### ADR 0019: Table Layout with Fixed Column Alignment Over Two-Line List Rows
- **Status**: Accepted (2026-10-23) - *Supersedes ADR 0012*
- **Context**: ADR 0012's two-line flex rows caused columnar misalignment. Data badges landed at varying horizontal coordinates across adjacent rows, making vertical scanning impossible.
- **Decision**:
  1. Desktop/Tablet (≥768px): Semantic `<table>` with `table-layout: fixed; width: 100%` and `<colgroup>` budget:
     - `Role`: Flexible (`min-width: 260px`, `w-auto`), clamped 2 lines with tooltip.
     - `Company`: Fixed `240px`. Line 1 has 28px square monogram + name; Line 2 has lowercase mono platform slug.
     - `Location`: Fixed `220px`. Muted ink, clamped 1 line.
     - `Salary`: Fixed `130px`. Conditionally rendered only when at least one job reports compensation.
     - `Work Model`: Fixed `120px`. Neutral badge; rendered completely empty if unknown.
     - `Posted`: Fixed `100px`. Tabular relative date with exact datetime tooltip.
  2. Exact padding match: `<th>` and `<td>` share identical `py-3.5 px-3.5` padding, aligning labels and data to the pixel.
  3. Mobile (<768px): Structured stacked cards (`ResultsCards.tsx`).
- **Consequences**: Perfect column scannability; automated Playwright audits verify matching bounding boxes across all rows.

---

### ADR 0020: Unified Page Shell and Centered Hero Layout
- **Status**: Accepted (2026-10-23) - *Supersedes ADR 0011*
- **Context**: ADR 0011's 960px left-aligned hero left dead space on the right of wide screens and felt visually unbalanced.
- **Decision**:
  1. Set `--page-max: 1160px` with `--page-gutter: 32px` desktop and `16px` mobile.
  2. Centered hero rhythm: Display headline centered with balanced text wrap; centered lead paragraph (`max-w-[60ch]`); framed form panel (`max-w-[760px]`, `p-6 sm:p-8`).
  3. Full-bleed boundary hairlines: Header and summary bar hairlines extend to viewport edges while inner content aligns strictly to the 1160px shell.
- **Consequences**: Harmonious, authoritative landing presence with zero layout jumping.

---

### ADR 0021: Platform Chip Neutral Selection and Green Accent Budget
- **Status**: Accepted (2026-10-24)
- **Context**: 18 platform chips rendered with bright green outlines when active. Because all platforms are active by default, the landing page displayed 18 green borders, creating visual noise and devaluing the signature accent color.
- **Decision**:
  1. Platform chip neutral selection:
     - Selected: Primary ink border (`border-[var(--ink)]`), subtle surface background (`bg-[var(--surface-subtle)]`), and a single forest green checkmark icon (`text-[var(--accent)]`).
     - Unselected: Subtle hairline border, transparent background, muted text.
  2. Strict green budget: Forest green (`--accent: #1A382B` light, `#34D399` dark) is strictly reserved for:
     - Primary search CTA button.
     - Selected platform chip checkmark.
     - Active Remote indicator dot.
     - 2px left border on table row hover.
     - High-contrast square keyboard focus rings (`:focus-visible`).
     - Links and live status indicator dots.
  3. Green is explicitly banned from non-interactive background panels or passive chip borders.
- **Consequences**: Preserves the signature accent as a high-signal indicator for primary actions; verified by automated Playwright green budget audit.

---

## 6. Design Philosophy, Visual Language & Token System (`DESIGN.md`)

### 6.1 Core Principles
- **Quiet & Typography-Led**: Visual hierarchy is carried by font scale, weight, and subtle ink tiers (high ink, muted ink, subtle ink)—never by heavy borders, boxed badges, or decorative gradients.
- **Square Geometry is Non-Negotiable**: `--radius: 0` everywhere. No rounded corners, pills, circular avatars, or soft bubble dialogs.
- **Unified Page Shell**: Every screen state lives inside `--page-max: 1160px; --page-gutter: 32px` (16px on mobile). Hairlines bleed full width while interactive content remains anchored to the shell.
- **Chrome Discipline**: One quiet status bar. Redundant buttons, duplicate headers, and developer jargon ("SERPER CALLS", "GET /search") are eliminated.

### 6.2 Visual Language & Identity
- **Canvas & Surfaces**:
  - Light mode: Warm editorial cream canvas (`--bg: #FAF8F5`), crisp white interactive cards (`--surface: #FFFFFF`).
  - Dark mode: Deep quiet carbon canvas (`--bg: #0C0D0C`), elevated dark surfaces (`--surface: #151615`).
- **Brand Identity**: Square `BP` monogram tile in forest green with single sans "Bottom Pot" wordmark.
- **Hairlines**: 1px dividers with subtle low alpha (`#00000014` light, `#FFFFFF14` dark).
- **Motion**: Restrained native transitions (120ms–180ms ease-out). Native scrolling with `scrollbar-gutter: stable`. View transitions via `document.startViewTransition()` with reduced-motion fallback.

### 6.3 Typography System
- **Font Families**:
  - Primary UI & Headings: **Geist Variable** (`--font-sans: 'Geist Variable', -apple-system, sans-serif`). Used for all headings, body text, form controls, and labels.
  - Machine Monospace: **DM Mono** (`--font-mono: 'DM Mono', monospace`). Used ONLY for lowercase machine slugs (`lever`, `greenhouse`), keyboard shortcut badges (`/`, `⌘K`), and tabular counts. Slugs must be lowercase, never uppercase.
- **Permitted Weights**: 400 (regular), 500 (medium), 600 (semi-bold).
- **Case Discipline**: Sentence case across all UI labels, table headers, and badges. All-caps text is banned.
- **Control Sizing**: Unified 14px font size across inputs, selects, and buttons.
- **Text Tiers**:
  - High Ink (`--ink`): `#181816` light / `#F2F1ED` dark (crisp contrast).
  - Muted Ink (`--ink-muted`): `#4A4943` light / `#B8B5AC` dark (WCAG AA > 7:1).
  - Subtle Ink (`--ink-subtle`): `#5A5952` light / `#98968E` dark (WCAG AA > 6:1).

### 6.4 Spacing Scale & Page Metrics
- **Page Shell**:
  - `--page-max: 1160px`
  - `--page-gutter: 32px` (desktop/tablet >= 640px)
  - `--page-gutter: 16px` (mobile < 640px)
  - `scrollbar-gutter: stable` on `:root`
- **Hero Rhythm**:
  - Top spacing (header to headline): 64px to 96px (`py-16 sm:py-20`).
  - Headline to lead copy: 16px to 20px.
  - Lead paragraph: `max-w-[60ch] mx-auto text-center`.
  - Lead to form panel: 40px to 48px (`mb-10 sm:mb-12`).
- **Form Panel & Controls**:
  - Form container: Centered `max-w-[760px]`, 1px hairline border, `p-6 sm:p-8`.
  - Control height: Unified 40px (`h-10`) with 12px horizontal padding (`px-3`).
  - Label-to-control gap: 8px (`gap-2`).
  - Field-to-field gap: 20px to 24px (`gap-5` to `gap-6`).
  - Primary CTA: Full-width forest green button (`h-12 px-6`).
  - Platform chips: 4-column grid (2-column on mobile), 36px height (`h-9`), 8px gaps (`gap-2`).

### 6.5 Fixed Table Architecture
- **Semantic Structure**: Semantic `<table>` with `table-layout: fixed; width: 100%`.
- **Pixel-Matched Padding**: Identical `py-3.5 px-3.5` (14px) for all `<th>` and `<td>`.
- **Column Width Budget**:
  - `Role`: Flexible (`min-width: 260px`, `w-auto`). Clamped to 2 lines with tooltip.
  - `Company`: Fixed `240px`. Leading 28px monogram on line 1, lowercase mono slug on line 2.
  - `Location`: Fixed `220px`. Muted ink, clamped 1 line.
  - `Salary`: Fixed `130px`. Conditionally rendered only when compensation is present in the set.
  - `Work Model`: Fixed `120px`. Badge rendered only if known; empty if unknown.
  - `Posted`: Fixed `100px`. Left-aligned relative date with tabular figures.
- **Row Interactions**: 2px forest green bar on left hover, subtle surface tint, high-contrast square outline on keyboard focus. Whole row opens posting (`target="_blank" rel="noopener noreferrer"`).
- **Mobile Format (<768px)**: Adapts cleanly into stacked cards (`ResultsCards.tsx`) preserving touch targets ≥44px.

### 6.6 Banned Patterns
1. **Unlayered Global CSS**: Element/reset selectors (`*`, `button`, `input`, `select`, `p`, `table`) outside `@layer base`.
2. **Rounded Corners**: Any border radius other than 0px (`--radius: 0`).
3. **Uppercase Monospace**: Tracked uppercase slugs (`GREENHOUSE`, `LEVER`).
4. **Native Unstyled Selects**: Raw browser select controls exposed without styling.
5. **Off-Scale Typography**: Disparate heights or font sizes within adjacent controls.
6. **Green Overuse**: Green outlines on unselected chips or passive banners.
7. **Synthetic Unknown Values**: Rendering artificial dummy tags ("—", "N/A") for missing fields. Unknown cells must remain empty.

---

## 7. Comprehensive Constraints, Concessions & Architectural Trade-offs

Every constraint in Bottom Pot reflects an explicit design decision or trade-off made to protect data accuracy, user trust, performance, or budget.

### 7.1 Data & Scraping Integrity Concessions

| Concession / Constraint | Architectural Trade-Off Made | Why It Was Made & What It Prevents |
| :--- | :--- | :--- |
| **"Unknown beats wrong" (ADR 0001)** | Missing fields stay `null` / `None`. The UI leaves cells empty or neutral instead of guessing. | Prevents misclassifying jobs (e.g. marking Atlanta hybrid jobs as on-site). Protects candidate trust. |
| **Deterministic Source Ladder (ADR 0002)** | Strict 7-tier precedence: `api_enum` > `jsonld` > `li_tag` > `location` > `title` > `description`. | Stops freeform text from overriding official API enums. Guarantees deterministic, explainable extraction. |
| **Exclusion of Provider Booleans (ADR 0002)** | Provider boolean flags (`isRemote: true`) are completely ignored. | ATS platforms (like Ashby) set `isRemote: true` for hybrid roles, causing false remote classifications. |
| **Backend Parsing Exclusivity (ADR 0003)** | Frontend regex parsing is strictly forbidden; all normalization occurs on the backend. | Eliminates split-brain logic, keeps transforms covered by pytest fixtures, and preserves field provenance. |
| **Real Test Fixtures Only** | Synthetic mock HTML is banned. Tests require real captured HTML/JSON via `capture_fixtures.py`. | Prevents parsers from overfitting to imaginary DOM structures that do not match live ATS boards. |
| **Conservative Company Formatting (ADR 0016)** | Company name formatting occurs only in the presentation layer; raw string stays untouched in state. | Improves readability without corrupting underlying data, search filtering, or export accuracy. |

### 7.2 Frontend & UI System Concessions

| Concession / Constraint | Architectural Trade-Off Made | Why It Was Made & What It Prevents |
| :--- | :--- | :--- |
| **Fixed Table over Two-Line List (ADR 0019 vs ADR 0012)** | Replaced flex list rows with a fixed-layout semantic table with explicit `<col>` widths. | Two-line flex rows caused metadata to drift horizontally across rows. Tables restore instant vertical scanning. |
| **Centered Hero & 1160px Shell (ADR 0020 vs ADR 0011)** | Replaced 960px left-aligned hero with centered 1160px shell with framed form panel. | 960px left-alignment left huge dead space on 1440px/1920px screens. Centering restores visual balance. |
| **Platform Chip Neutral Selection (ADR 0021)** | Selected chips use neutral ink borders with a green checkmark; unselected are muted. | Active green borders across all 18 chips created green visual noise, devaluing the accent color. |
| **CSS `@layer base` Isolation (ADR 0018)** | Universal reset `* { margin: 0; padding: 0; }` was banned; all base rules moved to `@layer base`. | Unlayered resets silently eradicated all Tailwind utility paddings and margins across the application. |
| **Rejection of Scroll-Jacking (ADR 0014)** | Lenis and smooth-scroll libraries are explicitly banned; native CSS and View Transitions used. | Prevents trackpad stutter, preserves browser native `Ctrl+F` search, and ensures zero a11y regressions. |
| **Single Quiet Summary Strip (ADR 0004, ADR 0013)** | Multi-band status bars collapsed into one line; diagnostic metrics hidden behind a Popover. | Eliminates status bloat and developer jargon, keeping actual job postings above the fold. |
| **Slide-Out Detail Sheet (ADR 0006)** | Side-sheet panel replaces inline expanding accordion table rows. | Inline accordions displaced neighboring rows and caused layout jumping. Sheets preserve table scroll position. |
| **Visited State Dimming & 3MB Quota (ADR 0005)** | Visited URLs tracked client-side; search results cached in localStorage up to 3MB. | Eliminates candidate browsing fatigue and prevents redundant Serper queries on page refresh. |
| **Stack Invariance (ADR 0007)** | Strictly locked to React 19 + Vite 8 + Base UI + Tailwind v4. No Next.js/Vue migration. | Keeps codebase lightweight, accessible to non-React specialists, and prevents framework churn. |
| **Backend API Invariance** | Frontend updates must not alter backend `/search` SSE contracts or query parameters. | Isolates frontend redesign from backend data pipeline stability. |

### 7.3 Infrastructure, Caching & Budget Concessions

| Concession / Constraint | Architectural Trade-Off Made | Why It Was Made & What It Prevents |
| :--- | :--- | :--- |
| **Serper Daily Budget (200 requests)** | Hard cap of 200 Serper requests per UTC day. When reached, returns `budget_exhausted: true`. | Prevents unexpected API billing overages on free-tier credits. |
| **Two-Tier SQLite Persistent Caching** | 12-hour TTL for Serper dork queries; 24-hour TTL for per-URL job page enrichments in `data/cache.sqlite`. | Eliminates redundant outbound queries for recurring search keywords and static job postings. |
| **In-Memory Cache (LRU 100 entries)** | Fast in-memory cache with 5-minute TTL for full search results. | Delivers instantaneous responses for identical queries executed in close succession. |
| **Concurrency Limits & Circuit Breakers** | Global semaphore: 20 concurrent requests; per-host limit: 3; circuit breaker: 5 failures trips 10m cooldown. | Prevents IP banning and protects ATS endpoints from aggressive scraping bursts. |
| **Max Response Size (3 MB)** | Outbound HTTP response streams truncate at 3,145,728 bytes. | Prevents memory exhaustion when encountering rogue multi-megabyte payloads or binary assets. |
| **Rate Limiting (/search)** | SlowAPI rate limit capped at 20 searches per hour per IP. | Prevents automated abuse and protects outbound Serper budget. |
| **Zero Cloud Hosting (Neon / Vercel banned)** | Local SQLite and local FastAPI server; cloud DBs and hosting platforms are strictly out of scope. | Avoids unnecessary cloud infrastructure costs, deployment sprawl, and operational overhead. |

### 7.4 Development Process & Git Workflow Concessions

| Concession / Constraint | Architectural Trade-Off Made | Why It Was Made & What It Prevents |
| :--- | :--- | :--- |
| **Direct Commits to `main` Banned** | All work must occur on isolated step branches (`step/NN-<slug>`). | Protects the primary branch from untested, broken, or half-implemented code. |
| **Standard Merge Commits (`--no-ff`)** | PRs merge with `--no-ff`; squashing and rebasing are prohibited. | Preserves the complete, granular commit narrative and history on the primary branch. |
| **Provenance Tracking in Step Logs** | Every step log in `docs/steps/` must record PR URL, first commit SHA, last commit SHA, and merge SHA. | Provides a permanent, auditable development history for every feature and bugfix. |
| **Mandatory Verification Gate** | `.\scripts\verify.ps1` must pass before any task or PR is declared complete. | Automatically verifies secrets, CSS cascade, oxlint, vitest, production build, pytest, and Playwright E2E. |

---

## 8. Backend Configuration & Operational Knobs (`src/config.py`)

All backend runtime settings are defined via Pydantic in `src/config.py` and configurable via `.env`:

| Setting Variable | Default | Type | Purpose & Operational Impact |
| :--- | :--- | :--- | :--- |
| `serper_api_key` | *(Required)* | `str` | API key for Serper.dev Google dork search queries. |
| `serper_mode` | `"live"` | `str` | `"live"` or `"cache_only"`. In `cache_only`, no outbound Serper calls are made. |
| `serper_daily_budget` | `200` | `int` | Maximum Serper API calls permitted per UTC day. Resets at midnight. |
| `serper_cache_ttl_hours` | `12` | `int` | TTL in hours for persistent Serper search query caching in SQLite. |
| `url_cache_ttl_hours` | `24` | `int` | TTL in hours for enriched job page HTML caching in SQLite. |
| `sqlite_db_path` | `"data/cache.sqlite"` | `str` | Filepath to persistent SQLite cache database (gitignored). |
| `max_results` | `100` | `int` | Maximum job records yielded to the client per search session. |
| `max_serper_queries_per_search` | `60` | `int` | Maximum dork queries dispatched across ATS platforms per search. |
| `serper_max_pages` | `3` | `int` | Maximum Google search result pages fetched per ATS platform dork. |
| `ats_request_timeout_seconds` | `5` | `int` | HTTP timeout for direct ATS API / JSON calls. |
| `scraper_request_timeout_seconds` | `10` | `int` | HTTP timeout for Nigerian job board scraping (Jobberman, etc.). |
| `search_hard_timeout_seconds` | `90` | `int` | Maximum duration before a `/search` SSE stream is terminated. |
| `scraper_delay_seconds` | `1.5` | `float` | Politeness delay between requests to Nigerian job board hosts. |
| `cache_ttl_seconds` | `300` | `int` | In-memory whole-search cache TTL (5 minutes). |
| `in_memory_cache_max_entries` | `100` | `int` | LRU capacity for in-memory search result cache. |
| `global_concurrency_limit` | `20` | `int` | Global concurrency semaphore across all outbound network fetches. |
| `per_host_concurrency_limit` | `3` | `int` | Maximum concurrent connections permitted to any single domain/host. |
| `circuit_breaker_failure_threshold` | `5` | `int` | Consecutive network errors required to trip host circuit breaker. |
| `circuit_breaker_cooldown_seconds` | `600` | `int` | Cooldown window (10 minutes) before retrying a tripped host. |
| `max_response_bytes` | `3145728` | `int` | Maximum stream read limit (3 MB) before truncation to prevent OOM. |
| `rate_limit_search` | `"20/hour"` | `str` | SlowAPI rate limit on `/search` per client IP. |
| `subscriptions_file` | `"subscriptions.csv"` | `str` | Storage path for email alert subscriptions. |
| `log_level` | `"INFO"` | `str` | Loguru logging threshold (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |

---

## 9. Build Protocol & Quality Verification Suite

Development follows the 10-stage lifecycle defined in `BUILD_PROTOCOL.md`:

```
Understand → Plan → Branch → Approve → Implement → Verify → Review diff → Record → PR & Review → Merge & Checkpoint
```

### The Verification Suite (`.\scripts\verify.ps1`)
Before declaring any task complete or merging a pull request, the complete verification pipeline must execute cleanly:

```powershell
# Run the complete test and quality pipeline
.\scripts\verify.ps1

# Run with E2E skipped (for rapid backend/unit check cycles)
.\scripts\verify.ps1 -SkipE2E
```

#### What `verify.ps1` Validates:
1. **Repository & Secret Health**:
   - Confirms git is available.
   - Scans git-tracked files for forbidden secret patterns (`*.pem`, `*.key`, `.env`, `credentials.json`, `.agents/mcp_config.json`).
2. **Frontend Quality Checks**:
   - `node scripts/lint_css_cascade.js`: Verifies zero unlayered CSS resets in `index.css`.
   - `npm --prefix frontend run lint`: Runs `oxlint` for high-speed JS/TS linting.
   - `npm --prefix frontend run test`: Runs `vitest` unit tests covering normalization, sorting, filtering, and storage.
   - `npm --prefix frontend run build`: Runs TypeScript strict typecheck (`tsc -b`) and Vite production bundle compilation.
3. **Backend Quality Checks**:
   - `pytest tests/test_api_endpoints.py -q`: Runs Python test suites for FastAPI routes, SSE streaming, and normalizers.
4. **End-to-End Browser Tests**:
   - `npx playwright test`: Runs headless browser tests against mock mode verifying table alignment, 5 viewports, keyboard shortcuts, green budget, and axe-core accessibility.

---

## 10. Summary & Repository Quick Reference

```
bottom-pot-v1/
├── .agents/                 # Local agent intelligence & 17 skills
│   ├── skills/              # Reusable agent skills (workflow, design-system, etc.)
│   └── mcp_config.json      # Local MCP configuration (gitignored, see .example)
├── docs/                    # Persistent documentation
│   ├── adr/                 # Architecture Decision Records (0000–0021)
│   ├── agents/              # Operational guides (mcps.md, skills.md, domain.md)
│   └── steps/               # Sequential step execution logs (Build Protocol)
├── frontend/                # React 19 + Vite 8 + Base UI + Tailwind v4 SPA
│   ├── src/
│   │   ├── components/      # UI components (Header, SearchForm, ResultsTable, etc.)
│   │   │   └── ui/          # 23 shadcn primitives on @base-ui/react
│   │   ├── lib/             # Pure tested helpers (normalize, filter, sort, storage)
│   │   └── index.css        # THE SINGLE SOURCE OF TRUTH: Tokens, theme, radius: 0
├── src/                     # Backend Python package
│   ├── api/                 # FastAPI routes and SSE streaming orchestrator
│   ├── project_files/       # Scrapers, normalizers, and ATS dork generators
│   └── config.py            # Pydantic settings & configuration knobs
├── scripts/                 # Automation & verification scripts (verify.ps1, lint_css_cascade.js)
├── tests/                   # Pytest suites, Playwright E2E, and real fixtures
├── AGENTS.md                # Agent working agreement & repository instructions
├── BUILD_PROTOCOL.md        # 10-stage development methodology
├── CONTEXT.md               # Domain context & terms
├── DESIGN.md                # Visual design system & token rules
├── PROJECT_COMPENDIUM.md    # THIS FILE: The master single-source bible
└── README.md                # User & developer getting started guide
```
