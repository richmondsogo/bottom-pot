# Repository File Structure: Bottom Pot

This document defines directory conventions and file placement rules for Bottom Pot.

---

## Directory Conventions

```text
bottom-pot/
├── .agents/                 # Local agent skill definitions (owner decision on trimming)
├── .codex/                  # Codex CLI MCP endpoint config (owner decision)
├── .github/
│   ├── workflows/ci.yml     # CI pipeline (backend/safety, Windows PowerShell, frontend, ruff, secret scan, smoke)
│   └── dependabot.yml       # Weekly pip, npm, and GitHub Actions dependency updates
├── docs/                    # Active current-state documentation & ADRs
│   ├── adr/                 # Architecture Decision Records (`README.md`, `0000`–`0034`)
│   ├── agents/              # Focused agent workspace guides
│   ├── design/              # UI screenshots referenced by README (`after/`) & reference notes
│   ├── history/             # Archived step execution logs (formerly `docs/steps/`)
│   ├── operations/          # Operational runbooks (`RUNBOOK.md`)
│   ├── providers/           # Monitored provider contract matrix + 9 per-provider docs
│   ├── architecture.md      # Backend & frontend current-state module map & Mermaid diagram
│   ├── BETA.md              # Beta usability tasks, TelemetryDeck status & untested deploy guide
│   ├── exception-audit.md   # SafetyError propagation contract & AST risk table
│   ├── FRONTEND.md          # React/Vite components & Tailwind v4 CSS layer contract
│   ├── job-source-catalog.md # Evaluated job source lifecycle ledger & 28 curated boards
│   ├── LESSONS.md           # Institutional memory of bug classes & CI checks
│   ├── README.md            # Documentation index (all active docs must be reachable here)
│   └── repo-inventory.md    # Phase 1 top-level audit & baseline footprint
├── frontend/                # React 19 + Vite + TypeScript + Tailwind v4 SPA (`src/`, `__tests__/`)
├── scripts/                 # PowerShell, Python & Node automation (`verify.ps1`, `smoke.py`, `db_backup.py`, `check_*.py`, `logo_coverage.py`, `report_freshness.py`)
├── src/                     # Backend Python packages (`api`, `ats`, `core`, `discovery`, `extraction`, `monitoring`, `providers`, `safety`, `storage`)
├── tests/                   # Offline pytest suites, conformance harness (`conformance/`), vectors (`vectors/`), real fixtures (`fixtures/`), Playwright E2E (`e2e/`)
├── AGENTS.md                # Authoritative agent rules & checklist
├── BUILD_PROTOCOL.md        # 10-stage PR workflow
├── CONTEXT.md               # Domain definitions, constraints & non-goals
├── CONTRIBUTING.md          # Contributor setup & verification guide
├── DESIGN.md                # Square `--radius: 0` visual system
├── LICENSE                  # MIT License
├── pyproject.toml           # Ruff (incl. BLE001 on safety/storage/monitoring/providers), pytest markers, mypy
├── README.md                # Project overview, quickstarts & status tables
├── SECURITY.md              # Vulnerability disclosure & security boundary overview
└── THIRD_PARTY_DATA.md      # Fixture personal-data audit, secret-rotation policy & >500 KB ledger
```

---

## Directory Placement Rules

1. **Root (`/`):** Core project entrypoints (`README.md`, `AGENTS.md`, `BUILD_PROTOCOL.md`, `CONTEXT.md`, `DESIGN.md`, `CONTRIBUTING.md`, `SECURITY.md`, `THIRD_PARTY_DATA.md`, `LICENSE`) and build manifests allowed in `scripts/check_repo_hygiene.py`. No loose scratch scripts.
2. **`frontend/`:** React/Vite SPA components (`src/components/`) and pure modules (`src/lib/`). Local keys (`frontend/.env.local`) stay gitignored.
3. **`src/`:** Domain subpackages (`api`, `ats`, `core`, `discovery`, `extraction`, `monitoring`, `providers`, `safety`, `storage`). No single module exceeds `1,500` lines unless explicitly legacy-capped (`scripts/check_repo_hygiene.py`).
4. **`docs/`:** Every active markdown file under `docs/` must be reachable from `docs/README.md` with zero broken relative links and zero commit SHAs. Historical step logs live in `docs/history/`.
5. **`scripts/`:** Cross-platform Python verification/operations scripts plus Windows PowerShell launchers (`scripts/verify.ps1`, `scripts/run_prod.ps1`, `scripts/bootstrap.ps1`, `scripts/check-env.ps1`).
