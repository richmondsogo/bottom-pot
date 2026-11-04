# Step 29: Repository Cleanup

## Overview
- **Goal**: Clean up tracked scratch files, unreferenced exports, redundant lockfiles, stale documentation contradicting current architecture, dead screenshot harnesses, tighten `.gitignore` rules, move the system compendium to `docs/agents/`, and update the verification suite (`scripts/verify.ps1`) to run the full pytest suite.
- **Branch**: `step/29-repo-cleanup`
- **PR**: https://github.com/richmondsogo/bottom-pot/pull/34
- **First Commit SHA**: `60bac48ef2e2a2eb0a693c0618037ca0fb7383a1`
- **Last Commit SHA**: `079bd1516e507bfa76f1c4fc97a0a52dfdb07914`
- **Merge Commit SHA**: `7a08a08b625f0e08e6b30126afd522cef581ffde`

---

## Approved Cleanup Actions

### 1. Deleted Tracked Files (10 files, 10,950 lines removed)
All files deleted via `git rm`:
1. `Design-Bottom-Pot-UI-2026-08-21.html` (187,540 bytes): Unreferenced August 2026 standalone HTML export at root.
2. `walkthrough.md` (61,595 bytes): Obsolete tutorial documenting legacy September vanilla JS architecture (`frontend/app.js`, old CLI pipeline), directly contradicting current architecture.
3. `pnpm-lock.yaml` (82,796 bytes): Redundant lockfile from an experimental run. Confirmed no `packageManager` field or CI references `pnpm` (npm is project standard).
4. `frontend/README.md` (1,029 bytes): Default Vite template boilerplate (`# React + TypeScript + Vite`), not project-specific.
5. `scripts/capture_pass2_states.js` (11,682 bytes): One-off scratch script from Step 02/03.
6. `scripts/capture_states_2x.js` (27,188 bytes): One-off scratch script from Step 03.
7. `scripts/capture_states_and_crops_2x.js` (9,037 bytes): One-off scratch script from Step 03/04.
8. `scripts/capture_ui_screenshots.js` (5,824 bytes): One-off scratch script from Step 01; superseded by canonical `scripts/capture_all_states.js`.
9. `scripts/diagnose_computed_styles.js` (3,248 bytes): Temporary layout debugging script from Step 03.
10. `scripts/verify_hero_browser.js` (7,570 bytes): Standalone hero script from Step 10; superseded by Playwright E2E suite.

### 2. Retained Functional Tool
- `scripts/benchmark_search.py` (5,609 bytes): Verified functional and executable via import/run check (completed in 1.02s with mock organic results). Kept in `scripts/`.

### 3. Moved Files
- `PROJECT_COMPENDIUM.md` → `docs/agents/PROJECT_COMPENDIUM.md`: Moved via `git mv`. Self-referencing link in tree updated to `docs/agents/`.

### 4. Retained & Documented (Deferred Items)
- `frontend-old/` (`app.js`, `index.html`, `styles.css`) and fallback in `src/api/main.py:57-58`: Kept intact. Removing `frontend-old/` requires modifying `src/api/main.py` (production code change), which is deferred to its own isolated step.
- `audit.csv`: Kept at root as ground truth evaluation input.
- `urls.txt`: Kept at root as functional input for `scripts/capture_fixtures.py`.
- `docs/FRONTEND.md`: Kept at `docs/FRONTEND.md`.
- `docs/screenshots/`: Kept as historical Step 10 landing hero visual evidence.
- Historical design directories (`docs/design/after-pass-2`, `after-restore`, `before-pass-2`, `before-restore`): Kept as visual audit records of past steps.
- `docs/agents/file-structure.md`: Updated to document `docs/FRONTEND.md`, `docs/screenshots/`, and the historical design folders.

### 5. Gitignore Tightening
- Changed `data/` to `/data/` to prevent accidentally ignoring nested `data/` directories in skills.
- Added explicit ignore rule for `.agents/skills/ui-ux-pro-max/data/` so no previously ignored files newly appear.
- Added ignores for SQLite WAL/SHM: `*.sqlite-wal`, `*.sqlite-shm`.
- Added test coverage ignores: `coverage/`, `frontend/coverage/`.
- Added build artifacts: `*.tsbuildinfo`, `.vite/`.
- Added log ignores: `*.log`, `npm-debug.log*`, `yarn-debug.log*`, `pnpm-debug.log*`.
- Verified `audit.csv` remains ignored.
- Verified `git ls-files | Measure-Object`: exactly 881 files before and 881 files after. Zero tracked files disappeared; zero previously ignored files newly appeared.

### 6. Verification Suite Pytest Update (`scripts/verify.ps1`)
- Changed `pytest tests/test_api_endpoints.py -q` to `python -m pytest -q`.
- Total verification suite runtime: 2m 45s (165.33 seconds).
- Confirmed all 570 backend tests run and pass without requiring external network or live ports.

---

## Verification Results
- `.\scripts\verify.ps1`: 8 passed, 0 failed, 0 skipped.
  1. Git available: `OK`
  2. No tracked secrets: `OK`
  3. CSS Cascade Lint (`scripts/lint_css_cascade.js`): `OK`
  4. Frontend Linting (`oxlint`): `OK`
  5. Frontend Unit Tests (`vitest`): `OK` (94 passed across 13 files)
  6. Frontend Typecheck & Production Build (`tsc + vite`): `OK`
  7. Python Unit Tests (`python -m pytest -q`): `OK` (570 passed, 4 warnings)
  8. Playwright E2E Suite (`npx playwright test`): `OK` (36 passed across 2 workers)
- Backend boots: `python -c "import src.api.main as m; print(m.app.title)"` → `Bottom Pot API` (`OK`)
- Documentation link check: 100% of relative links across active docs resolve. Corrected `README.md` image link to `docs/design/after-restore/results_1440x900.png`.
- Scratch check: Zero scratch scripts in repo.
- Git status: Clean.

---

## Target Repository Structure

```
bottom-pot-v1/
├── .agents/                          # Local agent intelligence configuration and skills
│   ├── skills/                       # 17 reusable agent skills
│   └── mcp_config.json.example       # Example MCP configuration
├── .codex/
│   └── config.toml                   # Motion dev MCP configuration
├── data/                             # Local cache store (gitignored database)
│   └── cache.sqlite                  # SQLite search cache (gitignored)
├── docs/                             # Persistent documentation
│   ├── adr/                          # Architecture Decision Records (0000–0029)
│   ├── agents/                       # Operational reference documentation
│   │   ├── domain.md
│   │   ├── file-structure.md
│   │   ├── issue-tracker.md
│   │   ├── mcps.md
│   │   ├── skills.md
│   │   └── PROJECT_COMPENDIUM.md     # [MOVED] Master single-source compendium
│   ├── design/                       # Visual design artifacts
│   │   ├── after/                    # Post-redesign screenshots
│   │   ├── before/                   # Baseline screenshots across 5 viewports & 6 states
│   │   ├── reference/                # Quality benchmarks (Daybreak, before shots)
│   │   ├── after-pass-2/             # [Historical Step 02 visual audit]
│   │   ├── after-restore/            # [Historical Step 04 visual audit]
│   │   ├── before-pass-2/            # [Historical Step 02 baseline]
│   │   └── before-restore/           # [Historical Step 03 baseline]
│   ├── screenshots/                  # [Historical Step 10 hero visual evidence]
│   ├── steps/                        # Sequential step execution logs (Build Protocol)
│   └── FRONTEND.md                   # Frontend architecture and developer guide
├── frontend/                         # React / Vite single-page application
│   ├── public/                       # Favicons, webmanifest, og-image
│   ├── src/                          # Application source code
│   ├── components.json               # shadcn registry configuration
│   ├── index.html                    # Root HTML document
│   ├── package-lock.json             # npm lockfile
│   ├── package.json                  # Frontend dependencies and scripts
│   ├── tsconfig.json                 # TypeScript configuration
│   └── vite.config.ts                # Vite bundler configuration
├── frontend-old/                     # [DEFERRED] Legacy vanilla JS client (retained with fallback)
├── scripts/                          # Automation & verification scripts
│   ├── audit_jobs.py                 # Description quality auditing
│   ├── benchmark_search.py           # Broad search performance benchmark
│   ├── bootstrap.ps1                 # Initial workspace setup
│   ├── capture_all_states.js         # Playwright multi-state screenshot harness
│   ├── capture_fixtures.py           # Real ATS HTML/JSON fixture capture
│   ├── check-env.ps1                 # Environment prerequisite verification
│   ├── eval_work_model.py            # Work-model accuracy evaluation
│   ├── lint_css_cascade.js           # CSS cascade linter (enforced in verify.ps1)
│   ├── summarize_results.py          # Provider yield and null-model analyzer
│   └── verify.ps1                    # Project verification runner (runs full pytest suite)
├── src/                              # Backend Python package
│   ├── api/                          # FastAPI endpoints, auth, and static mount
│   ├── project_files/                # Parsers, scrapers, deduplication, orchestration
│   └── config.py                     # Configuration settings
├── tests/                            # Automated test suites
│   ├── e2e/                          # Playwright browser tests
│   ├── fixtures/                     # Real & golden ATS fixtures
│   └── test_*.py                     # 28 pytest test suites (570 tests)
├── .env.example                      # Environment template
├── .gitattributes                    # Line ending and text attributes
├── .gitignore                        # Git ignore rules (tightened)
├── AGENTS.md                         # Agent operating agreement
├── audit.csv                         # Ground truth evaluation dataset (gitignored)
├── BUILD_PROTOCOL.md                 # 10-stage development methodology
├── CONTEXT.md                        # Authoritative project domain context
├── DESIGN.md                         # Design system specifications
├── LICENSE                           # MIT License
├── main.py                           # CLI search entry point
├── package-lock.json                 # Root npm lockfile
├── package.json                      # Root npm scripts & devDependencies
├── playwright.config.js              # Playwright browser test runner configuration
├── pyproject.toml                    # Python package metadata
├── README.md                         # Project documentation
├── requirements-dev.txt              # Development dependencies
├── requirements.txt                  # Production dependencies
├── skills-lock.json                  # Agent skills lockfile
└── urls.txt                          # Input URLs for capture_fixtures.py
```
