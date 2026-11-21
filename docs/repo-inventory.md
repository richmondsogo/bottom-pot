# Repository Inventory & Baseline Weight (Phase 1)

This document records the complete top-level inventory and baseline tracked repository footprint audited at `origin/main` before Step 57 cleanup.

---

## 1. Baseline Repository Footprint (Pre-Cleanup)

| Metric | Baseline Measurement |
|---|---|
| Tracked files (`git ls-files`) | 1,160 files (`103.20 MB` / `108,218,156 B`) |
| `docs/` tracked weight | `63.21 MB` (`66,280,043 B`) |
| `docs/design/` tracked weight | `61.64 MB` (`64,631,251 B`) |
| `docs/screenshots/` tracked weight | `0.46 MB` (`480,903 B`) |
| `tests/fixtures/real/` tracked weight | `35.18 MB` (`36,886,188 B`) |
| Tracked images (`.png`, `.svg`, `.ico`, etc.) | 459 files |
| `src/project_files/` module count | 42 Python files (`board_adapters.py`: 4,314 lines; `ats_api_client.py`: 3,820 lines; `nigerian_scrapers.py`: 2,199 lines; `company_board_registry.py`: 1,771 lines; `eligibility_extractor.py`: 1,530 lines) |
| `except Exception` blocks in `src/` | 188 |
| Baseline verification (`.\scripts\verify.ps1`) | `9 passed, 0 failed, 0 skipped (of 9 checks)` |
| Baseline `pytest -q` | `1221 passed, 2 warnings in 1117.90s (0:18:37)` |
| Baseline `vitest` (`frontend`) | `18 passed` files, `127 passed` tests |
| Baseline `oxlint` (`frontend`) | `0 errors, 3 warnings` (97 files) |
| Baseline Playwright E2E | `46 passed (2.6m)` (side effect: `step 28` dirtied `docs/design/after/step28_platform_chips_*.png` until fixed in Phase 1) |

---

## 2. Top-Level Directory & File Inventory

Every top-level file and directory present on disk at the start of Phase 1 (`38` repository entries plus `scratch/`, created gitignored for verification notes):

| Path | Type | Tracked | Purpose | Referenced By (`git grep`) | Last Meaningful Change | Verdict |
|---|---|---|---|---|---|---|
| `.agents` | dir | Yes | Local agent skills (`17` skills, `83` tracked files) and MCP config template | `AGENTS.md`, `BUILD_PROTOCOL.md`, `README.md`, `docs/agents/*`, `.gitignore` | `2026-10-22` — tactile UI transitions & skills | **Keep** (Owner decision on trimming vendored `ui-ux-pro-max` / `shadcn` / `motion` assets) |
| `.codex` | dir | Yes | Codex CLI MCP endpoint config (`config.toml`) | Mentioned generically only inside `.agents/skills/shadcn/mcp.md` | `2026-10-15` — dashboard UX & parser fixes | **Owner decision** (do not delete) |
| `.env` | file | No | Local environment variables & secrets | `.gitignore` | — (local only) | **Keep** (gitignored) |
| `.env.example` | file | Yes | Placeholder environment variable template | `README.md`, `AGENTS.md`, `docs/adr/0030*`, `scripts/check_db_safety.py`, `.gitignore` | `2026-10-27` — admin auth security gate | **Keep** |
| `.gitattributes` | file | Yes | Git EOL normalization rules (LF text, binary images) | Git | `2026-10-17` — adopt agent starter | **Keep** (strengthen fixture LF rule) |
| `.github` | dir | Yes | GitHub Actions CI workflow (`workflows/ci.yml`) | GitHub Actions, `docs/adr/0030*` | `2026-11-17` — Windows CI & safety checks | **Keep** |
| `.gitignore` | file | Yes | Ignore patterns for secrets, DBs, caches, and build outputs | `AGENTS.md`, `docs/agents/*` | `2026-11-04` — repo cleanup | **Keep** (add `scratch/`, `*.bak*`, `*.orig`, `*.sqlite-journal`) |
| `.pytest_cache` | dir | No | Pytest local cache | `.gitignore` | — (local only) | **Keep** (gitignored) |
| `.ruff_cache` | dir | No | Ruff local cache | `.gitignore` | — (local only) | **Keep** (gitignored) |
| `AGENTS.md` | file | Yes | Authoritative operating agreement for agents | `README.md`, `BUILD_PROTOCOL.md`, `CONTEXT.md`, `docs/agents/*` | `2026-11-19` — global-by-design principle | **Keep** (add checklist, provider freeze, no-SHA rule) |
| `audit.csv` | file | No | Local job audit CSV output | `.gitignore`, `scripts/audit_jobs.py`, `scripts/eval_work_model.py` | — (local only) | **Keep** (gitignored) |
| `BUILD_PROTOCOL.md` | file | Yes | 10-stage development methodology | `AGENTS.md`, `README.md`, `docs/agents/*` | `2026-11-01` — provenance-only commits note | **Keep** (replace SHA-in-docs provenance rule) |
| `CONTEXT.md` | file | Yes | Project domain context, glossary, and constraints | `AGENTS.md`, `BUILD_PROTOCOL.md`, `README.md`, `docs/agents/domain.md` | `2026-11-21` — Step 56 summary | **Keep** |
| `data` | dir | No | Operational SQLite DB (`cache.sqlite`), sidecars, and backups | `src/config.py`, `db_safety.py`, `docs/adr/0030*`, `.gitignore` | — (operational) | **Keep** (untouchable per ADR 0030) |
| `DESIGN.md` | file | Yes | Square design system, typography, and visual rules | `AGENTS.md`, `BUILD_PROTOCOL.md`, `README.md`, `docs/agents/*` | `2026-10-22` — HNJ unbundling & chip rules | **Keep** |
| `docs` | dir | Yes | ADRs, design references, agent guides, step logs | `README.md`, `AGENTS.md`, `docs/agents/*` | `2026-11-21` — Step 56 documentation | **Keep** (prune 442 unreferenced screenshots) |
| `frontend` | dir | Yes | React 19 + Vite 8 + TypeScript + Tailwind v4 SPA | `package.json`, `.github/workflows/ci.yml`, `scripts/verify.ps1`, `src/api/main.py` | `2026-11-21` — Step 56 eligibility fixes | **Keep** |
| `frontend-old` | dir | Yes | Legacy vanilla HTML/CSS/JS frontend (`3` files) | `src/api/main.py` (dead fallback), `README.md` (deferred cleanup note) | `2026-10-15` — pre-redesign fallback | **Delete** (Phase 1 safe cleanup) |
| `LICENSE` | file | Yes | Repository license | Open source metadata | `2026-09-01` — initial commit | **Keep** |
| `main.py` | file | Yes | Standalone CLI search entrypoint (`SerperSearcher`) | `README.md`, `docs/adr/0024*`, `docs/adr/0030*`, `docs/agents/file-structure.md` | `2026-09-01` — initial CLI + FastAPI | **Keep** (update config/module imports as codebase evolves) |
| `node_modules` | dir | No | Root npm/pnpm dependencies (`@playwright/test`, `motion`) | `.gitignore`, `package.json`, `playwright.config.js` | — (local only) | **Keep** (gitignored) |
| `outputs` | dir | No | CLI JSON/CSV output directory | `.gitignore`, `main.py`, `scripts/audit_jobs.py` | — (local only) | **Keep** (gitignored) |
| `package-lock.json` | file | Yes | Root npm lockfile | Root npm install | `2026-10-17` — UI redesign | **Keep** |
| `package.json` | file | Yes | Root workspace scripts and Playwright/Motion deps | `README.md`, `docs/FRONTEND.md`, `.github/workflows/ci.yml` | `2026-10-17` — UI redesign | **Keep** |
| `playwright.config.js` | file | Yes | Playwright E2E runner and ADR 0030 DB isolation config | `AGENTS.md`, `README.md`, `scripts/check_db_safety.py`, `tests/test_playwright_isolation.py` | `2026-11-17` — default-deny operational DB safety | **Keep** |
| `pr_body.md` | file | No | Local scratch PR description file | `.gitignore` | — (local only) | **Keep** (gitignored) |
| `pyproject.toml` | file | Yes | Ruff and mypy configuration | `README.md`, `docs/agents/file-structure.md` | `2026-10-15` — lint & typecheck config | **Keep** |
| `README.md` | file | Yes | Project entry point, setup, and test instructions | `AGENTS.md`, `docs/agents/file-structure.md` | `2026-11-21` — Step 56 documentation | **Keep** (rewritten in Phase 8) |
| `requirements-dev.txt` | file | Yes | Python dev/test dependencies (`pytest`, `ruff`, `mypy`) | `.github/workflows/ci.yml`, `README.md` | `2026-10-15` — dev deps | **Keep** |
| `requirements.txt` | file | Yes | Python runtime dependencies | `.github/workflows/ci.yml`, `README.md`, `requirements-dev.txt` | `2026-09-01` — initial FastAPI deps | **Keep** |
| `results.json` | file | No | Local CLI/script output JSON | `.gitignore`, `main.py`, `scripts/audit_jobs.py` | — (local only) | **Keep** (gitignored) |
| `scratch` | dir | No | Phase verification notes and baseline hashes (gitignored) | `.gitignore` (added in Phase 1) | — (local only) | **Keep** (gitignored) |
| `scripts` | dir | Yes | PowerShell/Node/Python verification & operational tooling | `.github/workflows/ci.yml`, `AGENTS.md`, `README.md` | `2026-11-19` — Pinpoint integration | **Keep** |
| `skills-lock.json` | file | Yes | Lockfile metadata for external agent skills (`shadcn`, `ui-ux-pro-max`) | Zero references (`git grep` empty) | `2026-10-22` — Emil Kowalski UI pass | **Owner decision** (do not delete) |
| `src` | dir | Yes | Backend FastAPI app, scrapers, extractors, safety, and monitoring | `pyproject.toml`, `scripts/*`, `tests/*`, `main.py` | `2026-11-21` — Step 56 catalog & eligibility | **Keep** (unify `config.py` in Phase 1; restructure in Phase 3) |
| `test-results` | dir | No | Playwright local test artifacts | `.gitignore` | — (local only) | **Keep** (gitignored) |
| `tests` | dir | Yes | Pytest backend suites, Playwright E2E, real/golden/synthetic fixtures | `.github/workflows/ci.yml`, `scripts/verify.ps1`, `scripts/check_db_safety.py` | `2026-11-21` — Step 56 E2E & catalog tests | **Keep** |
| `urls.txt` | file | Yes | 12 hardcoded Avature/Teamtailor/Workday URLs for manual capture | `scripts/capture_fixtures.py` (default arg), `.agents/skills/parser-change/SKILL.md` | `2026-10-15` — fixture capture helper | **Delete** (Phase 1 safe cleanup; move default input path to `scratch/urls.txt`) |
| `venv` | dir | No | Local Python virtual environment | `.gitignore`, `README.md` | — (local only) | **Keep** (gitignored) |
