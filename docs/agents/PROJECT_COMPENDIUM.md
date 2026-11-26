# Bottom Pot Agent Reference Hub

Concise navigation hub replacing duplicated historical notes. Read [`AGENTS.md`](../../AGENTS.md) for mandatory operating rules and [`CONTEXT.md`](../../CONTEXT.md) for product constraints.

---

## Authoritative Single-Source References

| Topic | Authoritative Document |
|---|---|
| Operating checklist, data safety & Provider Freeze | [`AGENTS.md`](../../AGENTS.md) |
| Domain definitions, 4 dimensions & non-goals (incl. Vercel + Neon Postgres hosting & local SQLite fallback) | [`CONTEXT.md`](../../CONTEXT.md) |
| 10-stage PR & merge workflow (no commit SHAs in docs) | [`BUILD_PROTOCOL.md`](../../BUILD_PROTOCOL.md) |
| Soft-square radius scale (`4px`/`6px`/`8px` + `0px` square table/hairlines/panel) & visual rules (`frontend/src/index.css`) | [`DESIGN.md`](../../DESIGN.md) |
| Institutional memory & automated prevention gates | [`docs/LESSONS.md`](../LESSONS.md) |
| Module map & end-to-end request/monitoring flows | [`docs/architecture.md`](../architecture.md) |
| External `BOTTOM_POT_DATA_DIR`, backup, restore, catalog seed & configuration reference | [`docs/operations/RUNBOOK.md`](../operations/RUNBOOK.md) |
| Shared 9-provider contract matrix & C1–C12 conformance | [`docs/providers/inventory.md`](../providers/inventory.md) |
| Frontend components & CSS layer contract | [`docs/FRONTEND.md`](../FRONTEND.md) |
| All Architecture Decision Records (`ADR 0000`–`ADR 0036`) | [`docs/adr/README.md`](../adr/README.md) |
| Job source evaluation ledger & 28 curated boards | [`docs/job-source-catalog.md`](../job-source-catalog.md) |
| Fixture datasets, `> 500 KB` ledger & personal-data audit | [`THIRD_PARTY_DATA.md`](../../THIRD_PARTY_DATA.md) |
| Beta testing protocol, TelemetryDeck audit & deployment guide | [`docs/BETA.md`](../BETA.md) |
| `SafetyError` propagation contract | [`docs/exception-audit.md`](../exception-audit.md) |

---

## Agent Workspace Guides (`docs/agents/`)

- [`file-structure.md`](file-structure.md) — Exact directory layout and placement conventions
- [`domain.md`](domain.md) — Domain context and ADR relationship summary
- [`issue-tracker.md`](issue-tracker.md) — Issue triage and unresolved item promotion
- [`mcps.md`](mcps.md) — Allowed and production-restricted MCP servers (`Neon` and `Vercel` cover production hosting per `AGENTS.md` §2 and require explicit owner authorization before any mutation)
- [`skills.md`](skills.md) — Project-local `.agents/skills/` workflows (historical workflow notes remain archived in [`docs/history/`](../history/))

---

## Runtime Configuration Surface

All backend settings resolve through `Settings` in [`src/core/settings.py`](../../src/core/settings.py), `resolve_data_paths` in [`src/core/data_dir.py`](../../src/core/data_dir.py), and [`src/storage/db_conn.py`](../../src/storage/db_conn.py), with the complete table of backend and frontend variables documented in [`docs/operations/RUNBOOK.md`](../operations/RUNBOOK.md#8-configuration-reference). Frontend build-time flags (`VITE_API_BASE_URL`, `VITE_LOGO_DEV_TOKEN`, `VITE_REPORT_PROBLEM_URL`, and `VITE_ENABLE_MOCK`) never store server secrets (`sk_*`).
