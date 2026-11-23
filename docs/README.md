# Bottom Pot Documentation Index

Authoritative index of current repository documentation. Historical step execution logs are archived in [`docs/history/`](history/).

---

## Core Operating & Project Docs

- [Project README](../README.md) — Overview, status tables, Windows/Linux quickstarts, architecture, and verification commands
- [Agent Operating Agreement](../AGENTS.md) — Mandatory agent checklist, safety invariants, Provider Freeze, and workflow rules
- [Build Protocol](../BUILD_PROTOCOL.md) — 10-stage development workflow and PR lifecycle
- [Project Context](../CONTEXT.md) — Domain glossary, constraints, and non-goals
- [Design System](../DESIGN.md) — Square `--radius: 0` visual language and tokens
- [Contributing Guide](../CONTRIBUTING.md) — Local workflow, PR verification checklist, and design rules
- [Security Policy](../SECURITY.md) — Security boundaries, SSRF/DB isolation invariants, and vulnerability reporting
- [Third-Party Data & Fixture Inventory](../THIRD_PARTY_DATA.md) — Personal-data audit, redaction policy, secret-rotation policy, and `> 500 KB` fixture justifications

## Architecture, Operations & Quality

- [Architecture Overview](architecture.md) — Current-state module map for `src/` + `frontend/` and request/monitoring/storage data flows
- [Beta Testing & Deploy Guide](BETA.md) — Five tester tasks, observation metrics template, TelemetryDeck audit, and untested owner deploy options
- [Operations & Recovery Runbook](operations/RUNBOOK.md) — `BOTTOM_POT_DATA_DIR`, WAL/SHM-safe backups, integrity checks, restore rehearsal, migration, and catalog seeding policy
- [Lessons Learned](LESSONS.md) — Institutional memory of recurring defects and automated checks preventing them
- [Exception Audit & SafetyError Policy](exception-audit.md) — `SafetyError` propagation contract and risk-grouped exception audit across `src/`
- [Repository Inventory & Baseline](repo-inventory.md) — Phase 1 top-level file inventory and baseline tracked footprint
- [Frontend Architecture Guide](FRONTEND.md) — React/Vite components, lib modules, and CSS layer rules
- [Job Source Lifecycle Catalog](job-source-catalog.md) — Authoritative ledger of all ATS providers, scrapers, and 28 direct employer boards
- [Brian Lovin Design Reference Notes](design/reference/brianlovin-notes.md) — Reference typography and list layout measurements

## Monitored ATS Providers (`docs/providers/`)

- [Provider Contract & Inventory Matrix](providers/inventory.md) — Unified 9-provider concern matrix and C1–C12 defect audit
- [Greenhouse](providers/greenhouse.md) · [Lever](providers/lever.md) · [Ashby](providers/ashby.md) · [Workable](providers/workable.md) · [Recruitee](providers/recruitee.md) · [SmartRecruiters](providers/smartrecruiters.md) · [Teamtailor](providers/teamtailor.md) · [Personio](providers/personio.md) · [Pinpoint HQ](providers/pinpointhq.md)

## Agent Guides (`docs/agents/`)

- [Agent Reference Hub](agents/PROJECT_COMPENDIUM.md) — Navigation index replacing legacy duplicated notes
- [Domain Knowledge Guide](agents/domain.md) — How `CONTEXT.md` relates to ADRs
- [Repository File Structure](agents/file-structure.md) — Directory conventions and placement rules
- [Issue Tracking Guide](agents/issue-tracker.md) — Issue reporting and triage rules
- [MCP Server Reference](agents/mcps.md) — Allowed and out-of-scope MCP integrations
- [Skills Reference](agents/skills.md) — Project-local `.agents/skills/` index

## Architecture Decision Records (`docs/adr/`)

Complete ADR index: [`docs/adr/README.md`](adr/README.md) (covers `ADR 0000` through `ADR 0034`, including [ADR 0031 Logo.dev Fallback](adr/0031-logo-dev-fallback.md), [ADR 0032 External Data Directory](adr/0032-external-data-directory.md), [ADR 0033 Provider Contract & Conformance](adr/0033-provider-contract-and-conformance.md), and [ADR 0034 Freshness Model & Backend Eligibility Authority](adr/0034-job-freshness-model-and-ranking.md)).
