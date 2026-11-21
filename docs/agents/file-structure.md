# Repository File Structure: Bottom Pot

This document defines the functional directory conventions and file placement rules for the Bottom Pot repository.

---

## Directory Conventions

```
bottom-pot-v1/
├── .agents/                 # Local agent intelligence configuration and skills
│   ├── skills/              # Reusable agent skills (workflow, design-system, etc.)
│   └── mcp_config.json      # Local MCP configuration (gitignored, see .example)
├── docs/                    # Persistent documentation
│   ├── adr/                 # Architecture Decision Records
│   ├── agents/              # Agent operating guides and reference docs
│   ├── design/              # Active visual design artifacts & references
│   │   ├── after/           # README UI screenshots (4 files)
│   │   └── reference/       # Design reference notes (brianlovin-notes.md)
│   ├── steps/               # Historical step execution logs (moving to docs/history/ in Phase 8)
│   ├── FRONTEND.md          # Frontend architecture and developer guide
│   ├── LESSONS.md           # Institutional memory of past bugs & automated checks
│   ├── README.md            # Documentation index
│   ├── job-source-catalog.md # Authoritative job source lifecycle & evaluation ledger
│   └── repo-inventory.md    # Phase 1 top-level inventory & baseline weight
├── frontend/                # React / Vite single-page application
│   ├── src/                 # Frontend source code
│   │   ├── assets/          # Static logos and brand assets
│   │   ├── components/      # Modular React components (SearchForm, ResultsTable, DetailSheet, etc.)
│   │   ├── lib/             # Pure logic modules (filter, sort, normalize, storage, visited, mock)
│   │   ├── types.ts         # TypeScript interfaces and data models
│   │   ├── index.css        # Design tokens and global CSS
│   │   └── App.tsx          # Main application container
│   ├── package.json         # Frontend npm dependencies and scripts
│   └── vite.config.ts       # Vite bundler configuration
├── scripts/                 # PowerShell and Node automation scripts
│   ├── bootstrap.ps1        # Initial workspace setup
│   ├── check-env.ps1        # Environment prerequisite verification
│   ├── check_db_safety.py   # Static & policy checker for operational DB safety
│   ├── verify.ps1           # Project verification runner (lint, typecheck, tests, build)
│   └── capture_all_states.js # Automated Playwright screenshot harness
├── src/                     # Backend Python package
│   ├── api/                 # FastAPI HTTP and SSE endpoints (`main.py`)
│   ├── project_files/       # ATS scraper clients, normalizers, db_safety.py, and orchestrator
│   └── config.py            # Authoritative backend settings, operational knobs & ATS_PLATFORMS
├── tests/                   # Automated test suites
│   ├── e2e/                 # Playwright end-to-end browser tests
│   ├── fixtures/            # Real ATS JSON, HTML, and census evidence fixtures (`tests/fixtures/real/<provider>/`, including `pinpointhq/` & `probe_census_manifest.json`)
│   └── test_*.py            # Pytest unit and integration suites (including `test_pinpoint_monitoring.py`)
├── AGENTS.md                # Agent working agreement & repository instructions
├── BUILD_PROTOCOL.md        # 10-stage development methodology
├── CONTEXT.md               # Authoritative project domain and context
├── DESIGN.md                # Design philosophy, visual rules, and token specifications
├── README.md                # Project entry point and user documentation
└── pyproject.toml           # Python package configuration
```

---

## Directory Placement Rules

1. **Root (`/`)**: Core markdown documentation (`AGENTS.md`, `BUILD_PROTOCOL.md`, `CONTEXT.md`, `DESIGN.md`, `README.md`) and ecosystem configuration files. No loose scratch scripts.
2. **`frontend/`**: All web user interface code lives in `frontend/`. Components are structured by feature and role with single-purpose files.
3. **`src/`**: Python backend modules and services.
4. **`docs/`**: Persistent documentation:
   - `docs/adr/`: Architecture decision records (`0000-template.md`, etc.).
   - `docs/steps/`: Sequential step execution logs (`00-plan.md`, etc.).
   - `docs/design/`: Current UI screenshots referenced by `README.md` (`after/`) and reference notes (`reference/`).
   - `docs/agents/`: Operational reference documentation for agents.
   - `docs/FRONTEND.md`: Frontend architecture and developer guide.
   - `docs/job-source-catalog.md`: Authoritative lifecycle catalog and evaluation status of every job source.
5. **`scripts/`**: Automation scripts. All PowerShell scripts must run smoothly in Windows PowerShell.
