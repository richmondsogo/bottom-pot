# Step 30: README Rewrite & Production UI Screenshots

## Overview
- **Goal**: Rewrite `README.md` to provide a concise, high-density project overview readable in ~3 minutes (~700 words excluding code blocks), with accurate technical descriptions derived strictly from the current codebase and step documentation. Capture fresh, high-resolution, optimized screenshots of the production UI across core states.
- **Branch**: `step/30-readme`
- **Scope**: Docs and images only (`README.md`, `docs/steps/30-readme.md`, `docs/design/after/`). Zero changes to `src/`, `tests/`, or production behavior.
- **First Commit SHA**: `bfa45652f49557fcb5b882eb7277732a39a04bb4`
- **Last Commit SHA**: `bfa45652f49557fcb5b882eb7277732a39a04bb4`
- **Merge Commit SHA**: `c31425d4a42c41bddee6b3861965d7c045cd1aef`
- **PR**: https://github.com/richmondsogo/bottom-pot/pull/35

---

## Technical Accuracy & Verification Audit

### 1. Python & Node Tooling Sources
- **Python**: Sourced from `pyproject.toml` (`[tool.ruff] target-version = "py310"`, `[tool.mypy] python_version = "3.10"`). Documented as `see pyproject.toml`.
- **Node.js**: Sourced from `frontend/package.json` (Vite 8, React 19, TypeScript ~6.0). Documented as `see frontend/package.json`.
- **Environment Verification**: Pointed to `.\scripts\bootstrap.ps1` and `.\scripts\check-env.ps1`.

### 2. Search Channels & Direct Company Routing
- **16 Global ATS Platforms**: Greenhouse, Lever, Ashby, Workable, SmartRecruiters, Jobvite, BambooHR, Recruitee, Workday, Taleo, Polywork, Breezy HR, Rippling, Personio, Pinpoint, Teamtailor.
- **3 Nigerian Job Boards**: Jobberman (NG), MyJobMag (NG), HotNigerianJobs (NG).
- **Direct Company Routing (Step 27)**: When a query includes recognized company slugs, probes public career APIs for Greenhouse (`/v1/boards/{slug}/jobs`), Lever (`/v0/postings/{slug}?mode=json`), and Ashby (`/posting-api/job-board/{slug}`) directly and deduplicates with search results. 404s and non-200 responses are dropped without inventing data.

### 3. Core Principles & Caching
- **"Unknown beats wrong"** ([ADR 0001](../adr/0001-unknown-beats-wrong.md)): Missing fields remain `null`; unlisted dates display as `"Date not listed"`.
- **Deterministic Extraction**: Deterministic extraction only, no LLM in the extraction path.
- **Evidence Excerpts**: Work model evidence stored as short excerpts of literal text alongside the source.
- **Multi-Tier Caching**:
  - In-memory whole-search cache: 300s.
  - Serper search query cache: 12h in SQLite (`data/cache.sqlite`).
  - Page enrichment cache: 24h in SQLite (`data/cache.sqlite`).

### 4. Key Environment Variables
Documented names and one-line descriptions for essential settings, linking to `.env.example` for the rest:
- `SERPER_API_KEY`: API key for Serper.dev Google search API (required for live discovery).
- `SERPER_MODE`: Operating mode for searcher: `live` or `cache_only`.
- `SERPER_DAILY_BUDGET`: Daily outbound Serper query limit before halting live queries (default `200`).
- `ADMIN_PASSWORD`: Plaintext password required to access `/admin`.
- `ADMIN_SESSION_SECRET`: Secret key used to sign admin session cookies.
- `SQLITE_DB_PATH`: Filesystem path to SQLite cache database (`data/cache.sqlite`).

### 5. Playwright Test Suite Nuance
- Clarified that `scripts/verify.ps1` runs **36 browser integration tests on Desktop Chromium** via Playwright. Specific layout, accessibility, and visual audit tests internally cycle through 5 screen viewports (1920×1080, 1440×900, 1024×768, 768×1024, 390×844).
- Explicitly stated that tests run offline against recorded fixtures, synthetic streams, and local test servers, making no live external API calls.

### 6. Screenshots Captured
Captured at 1440×900 viewport using realistic fixture data (Acme Labs, Linear, Palantir, Paystack, Interswitch) with zero sensitive data, keys, or admin screens. Stored under canonical path `docs/design/after/`:
- `docs/design/after/search_form.png`: 66,053 bytes (64.5 KB)
- `docs/design/after/results_view.png`: 87,616 bytes (85.6 KB)
- `docs/design/after/detail_sheet.png`: 121,390 bytes (118.5 KB)
- `docs/design/after/results_view_dark.png`: 90,206 bytes (88.1 KB)

---

## Verification Results
- All relative links and image paths in `README.md` and `docs/steps/30-readme.md` tested and verified resolving.
- `README.md` word count excluding code blocks: 724 words.
- `.\scripts\verify.ps1`: 8 passed, 0 failed, 0 skipped.
  - Python tests: 570 passed (no delta).
  - Vitest tests: 94 passed (no delta).
  - Playwright tests: 36 passed (no delta).
