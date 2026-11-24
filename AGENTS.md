# Bottom Pot Agent Instructions & Operating Agreement

Authoritative working agreement for autonomous and human contributors. Read this and [`docs/LESSONS.md`](docs/LESSONS.md) before modifying code.

## Mandatory Agent Checklist

**Before you start:**
- Read [`docs/LESSONS.md`](docs/LESSONS.md) first so past mistakes do not recur.
- Restate the owner's phase/step scope at the top of every PR body (no silent scope substitution).
- Obey the **Provider Freeze** (§6): add zero new ATS providers or curated employer boards until the owner lifts it.
- Never open, move, migrate, or modify operational `data/` files or `subscriptions.csv` (`ADR 0030` / `ADR 0032`).

**Before you finish:**
- Never write commit SHAs into any active committed doc (record PR number + merge SHA in the PR description after merge).
- Never allow real network/DNS calls in offline tests (mark true live tests `@pytest.mark.live`).
- If you fix a bug class, add a `docs/LESSONS.md` entry and an automated check in the same PR.
- Run `ruff`, `check_secrets.py`, `check_db_safety.py`, `check_repo_hygiene.py`, `smoke.py`, and `.\scripts\verify.ps1`.

---

## 1. Critical Operational Data Safety (`ADR 0030`, `ADR 0032`)

1. **Operational SQLite is never test data:** Never open, migrate, checkpoint, move, or delete `<repo>/data/cache.sqlite`, `-wal`/`-shm`/`-journal` sidecars, `cache.sqlite.bak-*`, `.cache.sqlite.restore-staging-*`, `<repo>/subscriptions.csv`, the outside-repo default production dir, or `BOTTOM_POT_DATA_DIR`.
2. **Disposable workspaces only:** Tests (`pytest`), Playwright E2E, `scripts/smoke.py`, and temporary servers must isolate to a fresh temp directory (`OwnedDisposableWorkspace` / `tmp_path` / `mkdtempSync`) and fail closed (`UnsafeDatabasePathError`) on protected paths.
3. **Default-deny operational runtime:** Only documented entrypoints (`scripts/run_prod.ps1`, `board_monitor:main`, `scripts.db_backup:main`, cache repair CLIs) may touch operational DBs with explicit `BOTTOM_POT_ALLOW_OPERATIONAL_DB=1` / `--allow-operational-db` outside test/CI contexts. Never put `BOTTOM_POT_ALLOW_OPERATIONAL_DB=1` in `.env` or `.env.example`.
4. **Never swallow `SafetyError`:** `SafetyError` and `UnsafeDatabasePathError` must always propagate uncaught (`docs/exception-audit.md`). `UnsafeRedirectError` converts fail-closed at explicit network boundary adapters.

---

## 2. Precedence, Hosting Scope & Git Workflow

1. **Precedence:** Active user prompt -> `AGENTS.md` & [`BUILD_PROTOCOL.md`](BUILD_PROTOCOL.md) -> [`CONTEXT.md`](CONTEXT.md) & [`DESIGN.md`](DESIGN.md) -> `.agents/skills/` -> defaults.
2. **Hosting scope (Option 1 split deploy):** Static frontend (`frontend/`) deploys on **Vercel** (`frontend/vercel.json`, `VITE_API_BASE_URL`), while the FastAPI API and `BoardMonitor` run in a **persistent container** (`Dockerfile`) with mounted `/data` (`BOTTOM_POT_DATA_DIR`) so WAL SQLite and `subscriptions.csv` remain durable. Direct SQLite/cron execution inside stateless Vercel serverless functions and managed cloud SQL migration (`Neon`) remain out of scope until explicitly planned.
3. **Primary branch protection:** Never commit directly to `main`. Work on isolated step/feature branches and merge via standard merge commits (`--no-ff`) only after CI is green.
4. **Provenance tracking:** Git history and merged PRs own provenance. Never write commit SHAs inside committed active markdown files (`scripts/check_repo_hygiene.py` fails on SHAs outside `docs/history/` and `docs/superpowers/`).

---

## 3. Product Direction & Extraction Invariants

- **Global by design (`CONTEXT.md`):** Serve applicants worldwide while treating Nigeria and wider Africa as first-class validation markets. Never assume every applicant is Nigerian or convert `"Remote"` / missing eligibility into `"Worldwide"`.
- **Two-phase monitored-first discovery (`SERPER_MODE=fallback`) & daemon safety:** Production runs prefer `MONITORING_ENABLED=true` and `SERPER_MODE=fallback`, querying monitored boards, direct company probes, and Nigerian scrapers in Phase 1 before falling back to Serper below `serper_fallback_min_results` (unless `live_discovery=true`). `BoardMonitor` startup in `src/api/main.py` is strictly gated on `not is_test_or_disposable_context()`.
- **Keep four dimensions separate:** `Work arrangement` (`onsite`/`hybrid`/`remote`/`unknown`), `Source geography`, `Job geography`, and `Applicant eligibility` (`eligible`/`restricted`/`unknown` per ISO-2 country).
- **Unknown beats wrong (`ADR 0001`) & backend owns parsing (`ADR 0003`, `ADR 0034`):** Structured data precedes DOM heuristics (zero LLMs when deterministic data exists). Frontend consumes backend `FreshnessTier`, `company_domain` (including post-enrichment `apply_url`/corporate `mailto:` refreshes), and `POST /api/eligibility/evaluate` without re-parsing raw snippets.
- **Real fixtures & budgets:** Parser changes require real fixtures; tracked images or fixtures exceeding `500 KB` must be justified in [`THIRD_PARTY_DATA.md`](THIRD_PARTY_DATA.md).

---

## 4. Square Design System (`DESIGN.md`, `docs/FRONTEND.md`)

- Enforce `--radius: 0` everywhere (cards, buttons, inputs, badges, `CompanyMark`, overlays).
- Dedicated multi-page routes (`/`, `/app`, `/product`, `/sources`, `/about`, `/admin`) with unified `<Header>`, editorial 3-column `<Footer>`, neutral menu hover surfaces (`var(--surface-hover)`), and progressive SSE delivery on first non-empty batch; no `#` separator anchors or scroll-jacking.
- Palette: warm cream (`#FAF8F5`) / deep forest green accent (`#1A382B`), tabular figures, sentence case UI labels, restrained 120–180ms ease-out motion, no developer jargon on user routes (`/app`).
- **Job-seeker-first copy on all public pages:** Write like a frontier job-board designer speaking directly to serious candidates (direct company apply links, clear country eligibility, real dates, zero account walls). Never name-drop competing job sites, and keep backend jargon (`ATS adapters`, `career tenants`, `JSON/XML`, `GraphQL`, `mailto domains`) out of public copy.
- **Calm workspace chrome & fresh CTA intent:** Keep search controls structured without competing stacked search bars or `Try:`/`Recent:` noise, keep optional city refinement inside the expandable `Filters` drawer below `"Where can you work from?"`, make `New search` immediately visible above results, and ensure every `Start searching` / `Open search` / `Search jobs` entry CTA opens a clean search form rather than restoring stale `bp.savedResults`.
- **Theme-safe Tailwind v4 contrast:** Declare `@custom-variant dark (&:where(.dark, .dark *));` in `frontend/src/index.css` and style semantic badges (including Hybrid) and `CompanyMark` monogram tiles exclusively via `.dark`-aware CSS tokens verified for WCAG AA in both themes—never hardcoded `dark:` hex overrides.
- Logo resolution (`ADR 0031`): `verified board/ATS logo -> Logo.dev on verified company_domain (pk_ only, fallback=404) -> monogram`. Never put `sk_*` keys anywhere in the repository or frontend bundle.

---

## 5. Verification Gates Before Completion

Run all automated checks (`python -m ruff check src/ tests/ scripts/`, `python scripts/check_secrets.py`, `python scripts/check_db_safety.py`, `python scripts/check_repo_hygiene.py`, `python scripts/smoke.py`, `python -m pytest -q`, `npm --prefix frontend run lint`, `npm --prefix frontend run test`, `npm --prefix frontend run build`, Playwright E2E, `.\scripts\verify.ps1`), review `git status` and `git diff`, check protected-asset hashes, and verify UI changes across `1920`, `1440`, `1024`, `768`, and `390` viewports. Configuration reference lives in [`src/core/settings.py`](src/core/settings.py).

---

## 6. Source Lifecycle Policy & Provider Freeze (§8.6)

1. **Provider Freeze (in effect until the owner lifts it):** Add **no** new ATS providers and **no** new curated employer boards.
2. **Permission gate when unfrozen:** Public HTTP access is not permission to republish. Investigate and verify redistribution terms, robots rules, snapshot completeness, canonical IDs, and bounded offline conformance specs (`tests/conformance/`) one source at a time.
3. **Rejected-provider cleanup:** When a source is `Rejected` or `Retired`, remove active code and UI registrations while retaining justified shared helpers, `HISTORICAL_FULL_INVENTORIES`, [`docs/history/`](docs/history/), operational SQLite data, and [`docs/job-source-catalog.md`](docs/job-source-catalog.md).
