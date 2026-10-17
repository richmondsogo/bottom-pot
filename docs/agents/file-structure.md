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
│   ├── design/              # Visual design artifacts
│   │   ├── before/          # Baseline screenshots across 5 viewports & 6 states
│   │   ├── after/           # Post-redesign screenshots
│   │   └── reference/       # Quality benchmarks (Daybreak, before shots)
│   └── steps/               # Sequential step execution logs (Build Protocol)
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
│   ├── verify.ps1           # Project verification runner (lint, typecheck, tests, build)
│   └── capture_all_states.js # Automated Playwright screenshot harness
├── src/                     # Backend Python package
│   ├── api/                 # FastAPI HTTP and SSE endpoints (`main.py`)
│   ├── project_files/       # ATS scraper clients, normalizers, and orchestrator
│   └── config.py            # Backend settings and configuration knobs
├── tests/                   # Automated test suites
│   ├── e2e/                 # Playwright end-to-end browser tests
│   ├── fixtures/            # Real ATS JSON and HTML response fixtures
│   └── test_*.py            # Pytest unit and integration suites
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
   - `docs/design/`: Screenshot artifacts for design comparison.
   - `docs/agents/`: Operational reference documentation for agents.
5. **`scripts/`**: Automation scripts. All PowerShell scripts must run smoothly in Windows PowerShell.
