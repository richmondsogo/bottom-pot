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
2. **Local testing & out-of-scope cloud hosting:** Cloud hosting (`Vercel`, `Neon`) and live production deployments remain out of scope; testing runs locally until the owner amends this rule (`CONTEXT.md`).
3. **Primary branch protection:** Never commit directly to `main`. Work on isolated step/feature branches and merge via standard merge commits (`--no-ff`) only after CI is green.
4. **Provenance tracking:** Git history and merged PRs own provenance. Never write commit SHAs inside committed active markdown files (`scripts/check_repo_hygiene.py` fails on SHAs outside `docs/history/` and `docs/superpowers/`).

---

## 3. Product Direction & Extraction Invariants

- **Global by design (`CONTEXT.md`):** Serve applicants worldwide while treating Nigeria and wider Africa as first-class validation markets. Never assume every applicant is Nigerian or convert `"Remote"` / missing eligibility into `"Worldwide"`.
- **Keep four dimensions separate:** `Work arrangement` (`onsite`/`hybrid`/`remote`/`unknown`), `Source geography`, `Job geography`, and `Applicant eligibility` (`eligible`/`restricted`/`unknown` per ISO-2 country).
- **Unknown beats wrong (`ADR 0001`) & backend owns parsing (`ADR 0003`, `ADR 0034`):** Structured data precedes DOM heuristics (zero LLMs when deterministic data exists). Frontend consumes backend `FreshnessTier`, `company_domain`, and `POST /api/eligibility/evaluate` without re-parsing raw snippets.
- **Real fixtures & budgets:** Parser changes require real fixtures; tracked images or fixtures exceeding `500 KB` must be justified in [`THIRD_PARTY_DATA.md`](THIRD_PARTY_DATA.md).

---

## 4. Square Design System (`DESIGN.md`, `docs/FRONTEND.md`)

- Enforce `--radius: 0` everywhere (cards, buttons, inputs, badges, `CompanyMark`).
- Palette: warm cream (`#FAF8F5`) / deep forest green accent (`#1A382B`), tabular figures, sentence case UI labels, restrained 120–180ms ease-out motion, no developer jargon on user routes (`/app`).
- Logo resolution (`ADR 0031`): `api -> Logo.dev (pk_ only, fallback=404) -> monogram`. Never put `sk_*` keys anywhere in the repository or frontend bundle.

---

## 5. Verification Gates Before Completion

Run all automated checks (`python -m ruff check src/ tests/ scripts/`, `python scripts/check_secrets.py`, `python scripts/check_db_safety.py`, `python scripts/check_repo_hygiene.py`, `python scripts/smoke.py`, `python -m pytest -q`, `npm --prefix frontend run lint`, `npm --prefix frontend run test`, `npm --prefix frontend run build`, Playwright E2E, `.\scripts\verify.ps1`), review `git status` and `git diff`, check protected-asset hashes, and verify UI changes across `1920`, `1440`, `1024`, `768`, and `390` viewports. Configuration reference lives in [`src/core/settings.py`](src/core/settings.py).

---

## 6. Source Lifecycle Policy & Provider Freeze (§8.6)

1. **Provider Freeze (in effect until the owner lifts it):** Add **no** new ATS providers and **no** new curated employer boards.
2. **Permission gate when unfrozen:** Public HTTP access is not permission to republish. Investigate and verify redistribution terms, robots rules, snapshot completeness, canonical IDs, and bounded offline conformance specs (`tests/conformance/`) one source at a time.
3. **Rejected-provider cleanup:** When a source is `Rejected` or `Retired`, remove active code and UI registrations while retaining justified shared helpers, `HISTORICAL_FULL_INVENTORIES`, [`docs/history/`](docs/history/), operational SQLite data, and [`docs/job-source-catalog.md`](docs/job-source-catalog.md).
