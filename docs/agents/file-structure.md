# Repository File Structure: Bottom Pot

This document defines directory conventions and file placement rules for Bottom Pot.

---

## Directory Conventions

```text
bottom-pot/
├── .agents/                 # Local agent skill definitions
├── .codex/                  # Codex CLI MCP endpoint config
├── .github/
│   ├── workflows/
│   │   ├── ci.yml           # CI pipeline (backend/safety, Windows PowerShell, frontend, ruff, secret scan, smoke)
│   │   └── board-monitor.yml # Scheduled 30-minute board refresh workflow calling /api/cron/monitor
│   └── dependabot.yml       # Weekly pip, npm, and GitHub Actions dependency updates
├── api/                     # Vercel serverless FastAPI ASGI entrypoint (`api/index.py`)
├── docs/                    # Active current-state documentation & ADRs
│   ├── adr/                 # Architecture Decision Records (`README.md`, `0000`–`0036`)
│   ├── agents/              # Focused agent workspace guides
│   ├── design/              # UI screenshots (`after/`) & reference notes (`reference/`)
│   ├── history/             # Archived step execution logs (formerly `docs/steps/`)
│   ├── operations/          # Operational runbooks (`RUNBOOK.md`)
│   ├── providers/           # Monitored provider contract matrix + 9 per-provider docs
│   ├── architecture.md      # Backend & frontend current-state module map & runtime behavior
│   ├── BETA.md              # Beta usability tasks, TelemetryDeck status & deploy options
│   ├── exception-audit.md   # SafetyError propagation contract & AST risk table
│   ├── FRONTEND.md          # React/Vite components, state/storage & Tailwind v4 CSS layer contract
│   ├── job-source-catalog.md # Evaluated job source lifecycle ledger & 28 curated boards
│   ├── LESSONS.md           # Institutional memory of bug classes & CI checks
│   ├── README.md            # Documentation index (all active docs must be reachable here)
│   └── repo-inventory.md    # Historical Phase 1 top-level audit & baseline snapshot
├── frontend/                # React 19 + Vite + TypeScript + Tailwind v4 SPA (`frontend/src/`, `frontend/vercel.json`)
├── scripts/                 # PowerShell, Python & Node automation (`verify.ps1`, `run_prod.ps1`, `smoke.py`, `lint_css_cascade.js`, `db_backup.py`, `check_*.py`, `logo_coverage.py`, `report_freshness.py`)
├── src/                     # Backend Python packages (`api`, `ats`, `core`, `discovery`, `extraction`, `monitoring`, `providers`, `safety`, `storage`)
├── tests/                   # Offline pytest suites, conformance harness (`conformance/`), vectors (`vectors/`), real fixtures (`fixtures/`), Playwright E2E (`e2e/`)
├── .dockerignore            # Docker build context exclusions
├── .editorconfig            # Editor formatting defaults
├── .env.example             # Backend environment template
├── .gitattributes           # Git line-ending rules
├── .vercelignore            # Vercel deployment exclusions
├── AGENTS.md                # Authoritative agent rules & checklist
├── BUILD_PROTOCOL.md        # 10-stage PR workflow
├── CONTEXT.md               # Domain definitions, constraints & non-goals
├── CONTRIBUTING.md          # Contributor setup & verification guide
├── DESIGN.md                # Soft-square visual system (`frontend/src/index.css` tokens & square table/panel rules)
├── Dockerfile               # Container image definition for backend/self-hosting
├── LICENSE                  # MIT License
├── main.py                  # Standalone SerperSearcher CLI entrypoint
├── package.json             # Root npm workspace/Playwright scripts
├── package-lock.json        # Root npm lockfile
├── playwright.config.js     # Playwright E2E configuration
├── pyproject.toml           # Ruff (incl. BLE001 on safety/storage/monitoring/providers), pytest markers, mypy
├── README.md                # Project overview, quickstarts & status tables
├── requirements.txt         # Production Python dependencies
├── requirements-dev.txt     # Development & test Python dependencies
├── SECURITY.md              # Vulnerability disclosure & security boundary overview
├── skills-lock.json         # Installed skill lockfile
├── THIRD_PARTY_DATA.md      # Fixture personal-data audit, secret-rotation policy & >500 KB ledger
└── vercel.json              # Unified Vercel build, routes & daily cron (`/api/cron/monitor`) config
```

---

## Directory Placement Rules

1. **Root (`/`):** Core project entrypoints (`README.md`, `AGENTS.md`, `BUILD_PROTOCOL.md`, `CONTEXT.md`, `DESIGN.md`, `CONTRIBUTING.md`, `SECURITY.md`, `THIRD_PARTY_DATA.md`, `LICENSE`) and build manifests allowed in `scripts/check_repo_hygiene.py`. No loose scratch scripts.
2. **`frontend/`:** React/Vite SPA components (`frontend/src/components/`, `frontend/src/pages/`) and pure modules (`frontend/src/lib/`). Local keys (`frontend/.env.local`) stay gitignored.
3. **`src/`:** Domain subpackages (`api`, `ats`, `core`, `discovery`, `extraction`, `monitoring`, `providers`, `safety`, `storage`). No single module exceeds `1,500` lines unless explicitly legacy-capped (`scripts/check_repo_hygiene.py`).
4. **`docs/`:** Every active markdown file under `docs/` must be reachable from `docs/README.md` with zero broken relative links and zero commit SHAs. Historical step logs live in `docs/history/`.
5. **`scripts/`:** Cross-platform verification, backup, lint, and runtime scripts (`scripts/verify.ps1`, `scripts/run_prod.ps1`, `scripts/smoke.py`, `scripts/lint_css_cascade.js`, `scripts/db_backup.py`, `scripts/check_secrets.py`, `scripts/check_db_safety.py`, `scripts/check_repo_hygiene.py`, `scripts/logo_coverage.py`, `scripts/report_freshness.py`).
