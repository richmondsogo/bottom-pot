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
│   ├── providers/           # Shared provider primitives + 9 monitored ATS adapters & facade (`providers/inventory.md`)
│   ├── steps/               # Historical step execution logs (moving to docs/history/ in Phase 8)
│   ├── FRONTEND.md          # Frontend architecture and developer guide
│   ├── LESSONS.md           # Institutional memory of past bugs & automated checks
│   ├── README.md            # Documentation index
│   ├── exception-audit.md   # SafetyError propagation invariant and src/ exception risk table
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
│   ├── check_repo_hygiene.py # Institutional-memory & hygiene CI gate
│   ├── logo_coverage.py     # Read-only 3-bucket logo coverage report CLI
│   ├── report_freshness.py  # Read-only per-provider job freshness report CLI
│   ├── verify.ps1           # Project verification runner (lint, typecheck, tests, build)
│   └── capture_all_states.js # Automated Playwright screenshot harness
├── src/                     # Backend Python domain subpackages
│   ├── api/                 # FastAPI HTTP/SSE endpoints (`main.py`, `auth.py`, `allowlist.py`)
│   ├── core/                # `settings.py`, `clock.py`, `models.py`, `exceptions.py`, `observability.py`, `countries.py`, shared `http_headers.py`, `http_resilience.py`, `retry.py`
│   ├── safety/              # `db_safety.py`, `url_safety.py`
│   ├── storage/             # `cache_store.py`, `company_board_registry.py`
│   ├── discovery/           # `query_builder.py`, `serper_searcher.py`, `nigerian_scrapers.py`, `search_pipeline.py`
│   ├── ats/                 # `ats_url_parser.py`, `ats_api_client.py`, `ats_page_enricher.py`, `direct_board_router.py`
│   ├── monitoring/          # `board_monitor.py`, `employer_board_catalog.py`, `cache_repair/` (`engine.py`, `ashby.py`, `greenhouse.py`, `lever.py`, `workable.py`)
│   ├── providers/           # Shared contract/HTTP/fingerprint/pagination/detail primitives (`contract.py`, `http.py`, `fingerprint.py`, `pagination.py`, `detail_hydration.py`), 9 per-provider modules (`greenhouse.py`, `lever.py`, `ashby.py`, `workable.py`, `recruitee.py`, `smartrecruiters.py`, `teamtailor.py`, `personio.py`, `pinpoint.py`), and compatibility facade (`board_adapters.py`)
│   └── extraction/          # `job_extraction_service.py`, `field_normalizer.py`, `salary_parser.py`, `work_model.py`, `eligibility_extractor.py`, `eligibility_labels.py`, `freshness.py`, `domain_extractor.py`, `career_stage.py`, `confidence_policy.py`, `extraction_outcome.py`, `relevance_classifier.py`, `deduplicator.py`, `canonical_job_adapter.py`, `logo_extractor.py`, `html_helpers.py`, `url_normalizer.py`
├── tests/                   # Automated test suites
│   ├── conformance/         # Parametrized C1-C12 provider contract conformance suite across all 9 monitored adapters
│   ├── e2e/                 # Playwright end-to-end browser tests
│   ├── fixtures/            # Real ATS JSON, HTML, and census evidence fixtures (`tests/fixtures/real/<provider>/`, including `pinpointhq/` & `probe_census_manifest.json`)
│   ├── vectors/             # Shared cross-language test vectors (`eligibility.json`) verified by pytest and vitest
│   └── test_*.py            # Pytest unit and integration suites (including `test_eligibility_vectors.py`, `test_freshness.py`, `test_company_domain_and_logo_coverage.py`)
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
3. **`src/`**: Python backend domain subpackages with no monolithic catch-all directory:
   - Shared transport primitives (`http_headers.py`, `http_resilience.py`, `retry.py`) live in `src/core/` because `ats/`, `discovery/`, `providers/`, and `monitoring/cache_repair/` all depend on them.
   - Extraction utilities (`html_helpers.py`, `url_normalizer.py`) live in `src/extraction/` alongside HTML/URL normalization and canonical deduplication.
   - Monitored ATS adapters live per provider in `src/providers/<name>.py`, built on shared primitives (`contract.py`, `http.py`, `fingerprint.py`, `pagination.py`, `detail_hydration.py`) with `board_adapters.py` retained as a slim registry and compatibility facade.
4. **`docs/`**: Persistent documentation:
   - `docs/adr/`: Architecture decision records (`0000-template.md`, etc.).
   - `docs/steps/`: Sequential step execution logs (`00-plan.md`, etc.).
   - `docs/design/`: Current UI screenshots referenced by `README.md` (`after/`) and reference notes (`reference/`).
   - `docs/agents/`: Operational reference documentation for agents.
   - `docs/FRONTEND.md`: Frontend architecture and developer guide.
   - `docs/job-source-catalog.md`: Authoritative lifecycle catalog and evaluation status of every job source.
5. **`scripts/`**: Automation scripts. All PowerShell scripts must run smoothly in Windows PowerShell.
