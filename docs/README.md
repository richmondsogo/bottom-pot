# Bottom Pot Documentation Index

Authoritative index of current repository documentation. Historical step execution logs reside in [`docs/steps/`](steps/) (scheduled to move to `docs/history/` in Phase 8).

---

## Core Operating & Project Docs

- [Project README](../README.md) — Overview, quickstart, and verification commands
- [Agent Operating Agreement](../AGENTS.md) — Mandatory agent checklist, safety invariants, and workflow rules
- [Build Protocol](../BUILD_PROTOCOL.md) — 10-stage development workflow and PR lifecycle
- [Project Context](../CONTEXT.md) — Domain glossary, constraints, and non-goals
- [Design System](../DESIGN.md) — Square `--radius: 0` visual language and tokens

## Operations, Hygiene & Inventory

- [Lessons Learned](LESSONS.md) — Institutional memory of recurring defects and automated checks preventing them
- [Exception Audit & SafetyError Policy](exception-audit.md) — `SafetyError` propagation contract and risk-grouped exception audit across `src/`
- [Provider Contract & Inventory Matrix](providers/inventory.md) — Pre/post-refactor 9-provider concern matrix and defect audit
- [Repository Inventory & Baseline](repo-inventory.md) — Top-level file inventory and baseline tracked weight
- [Frontend Architecture Guide](FRONTEND.md) — React/Vite components, lib modules, and CSS layer rules
- [Job Source Lifecycle Catalog](job-source-catalog.md) — Authoritative ledger of all ATS providers, scrapers, and direct employer boards
- [Brian Lovin Design Reference Notes](design/reference/brianlovin-notes.md) — Reference typography and list layout measurements

## Agent Guides

- [Project Compendium](agents/PROJECT_COMPENDIUM.md) — Consolidated reference of ADRs, skills, constraints, and configuration
- [Domain Knowledge Guide](agents/domain.md) — How `CONTEXT.md` relates to ADRs
- [Repository File Structure](agents/file-structure.md) — Directory conventions and placement rules
- [Issue Tracking Guide](agents/issue-tracker.md) — Issue reporting and triage rules
- [MCP Server Reference](agents/mcps.md) — Allowed and out-of-scope MCP integrations
- [Skills Reference](agents/skills.md) — Project-local `.agents/skills/` index

## Architecture Decision Records (`docs/adr/`)

| ADR | Title |
|---|---|
| [ADR 0000](adr/0000-template.md) | Architecture Decision Record Template |
| [ADR 0001](adr/0001-unknown-beats-wrong.md) | Unknown Beats Wrong |
| [ADR 0002](adr/0002-work-model-source-ladder.md) | Work Model Source Ladder and Provenance |
| [ADR 0003](adr/0003-backend-owns-parsing.md) | Backend Owns Parsing |
| [ADR 0004](adr/0004-square-design-system-and-daybreak-craft.md) | Square Design System and Daybreak Craft Direction |
| [ADR 0005](adr/0005-client-side-visited-state-and-results-persistence.md) | Client-Side Visited State and Results Persistence |
| [ADR 0006](adr/0006-results-detail-panel-and-keyboard-navigation.md) | Results Detail Panel and Keyboard Navigation |
| [ADR 0007](adr/0007-no-framework-migration-and-frontend-architecture.md) | No Framework Migration and Frontend Architecture |
| [ADR 0008](adr/0008-backend-api-recommendations-for-frontend-ux.md) | Backend API Recommendations for Frontend UX |
| [ADR 0009](adr/0009-shadcn-foundation-and-base-ui-components.md) | shadcn/ui Foundation and Base UI Component Architecture |
| [ADR 0010](adr/0010-typography-system-and-font-selection.md) | Typography System and Font Selection (Geist Sans + DM Mono) |
| [ADR 0011](adr/0011-unified-page-shell-and-left-alignment.md) | Unified Page Shell and Left Alignment |
| [ADR 0012](adr/0012-two-line-list-architecture-replacing-boxed-tables.md) | Two-Line List Architecture Replacing Boxed Tables |
| [ADR 0013](adr/0013-command-palette-and-chrome-discipline.md) | Command Palette (Cmd+K) and Chrome Discipline |
| [ADR 0014](adr/0014-native-motion-view-transitions-and-no-lenis.md) | Native Motion, View Transitions API, and Rejection of Scroll-Jacking (Lenis) |
| [ADR 0015](adr/0015-theme-system-and-dark-mode-contrast.md) | Theme System and Dark Mode Contrast |
| [ADR 0016](adr/0016-safe-company-display-name-cleanup.md) | Safe Company Display Name Cleanup |
| [ADR 0017](adr/0017-layout-and-spacing-overhaul.md) | Layout and Spacing Overhaul (Pass 2 Craft Refinement) |
| [ADR 0018](adr/0018-root-cause-and-fix-of-unlayered-css-resets.md) | Root Cause and Fix of Missing Padding and Margins (Unlayered CSS Resets) |
| [ADR 0019](adr/0019-table-layout-over-two-line-list.md) | Table Layout with Fixed Column Alignment Over Two-Line List Rows |
| [ADR 0020](adr/0020-page-shell-and-gutter-tokens.md) | Unified Page Shell and Centered Hero Layout |
| [ADR 0021](adr/0021-platform-chip-neutral-selection-and-green-budget.md) | Platform Chip Neutral Selection and Green Accent Budget |
| [ADR 0022](adr/0022-glyph-portal-hero-scroll-motion-and-wordmark-weight.md) | Glyph Portal Hero Scroll Motion, Wordmark Weight Exception, and Green Budget Compliance |
| [ADR 0023](adr/0023-logo-and-icon-set.md) | Logo and Icon Set |
| [ADR 0024](adr/0024-canonical-job-contract-and-compatibility-adapter.md) | Canonical Job Contract and Compatibility Adapter Architecture |
| [ADR 0025](adr/0025-shared-extraction-and-normalization-pipeline.md) | Shared Extraction and Normalization Pipeline |
| [ADR 0026](adr/0026-work-model-display-quality-vs-extraction-eligibility.md) | Work-Model Display Quality vs Extraction Eligibility |
| [ADR 0027](adr/0027-structured-compensation-and-salary-invariance.md) | Structured Compensation and Salary Invariance |
| [ADR 0028](adr/0028-deterministic-field-confidence-and-provenance.md) | Deterministic Field Confidence and Provenance Architecture |
| [ADR 0029](adr/0029-explicit-extraction-outcomes-and-bounded-retries.md) | Explicit Extraction Outcomes, Bounded Retries, and Failure Isolation |
| [ADR 0030](adr/0030-operational-sqlite-database-isolation-and-destructive-test-safety.md) | Operational SQLite Database Isolation and Destructive Test Safety |
| [ADR 0031](adr/0031-logo-dev-fallback.md) | Three-Tier Company Logo Resolution & Logo.dev Fallback |
