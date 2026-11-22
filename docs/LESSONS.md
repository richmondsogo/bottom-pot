# Institutional Memory & Lessons Learned

Every recurring defect or process failure fixed in Bottom Pot is recorded here with the automated mechanism that prevents it from happening again. Read this file before touching code.

---

### L-01: Offline tests used real DNS
- **Symptom:** Fixture-replay and URL validation tests called real `socket.getaddrinfo` via `url_safety.py` and failed whenever DNS/network was unavailable.
- **Root cause:** `url_safety.py` defaulted directly to `socket.getaddrinfo` with no injected test resolver, and `pytest` had no tripwire catching hidden real-network calls.
- **Mechanism that prevents it:** Injectable `DnsResolver` protocol (`SystemDnsResolver` default, explicit-table `StaticDnsResolver`, scoped `use_dns_resolver`) in `url_safety.py`, autouse `socket.getaddrinfo` tripwire in `tests/conftest.py` for non-`@pytest.mark.live` tests, and static network-call check in `scripts/check_repo_hygiene.py`.
- **Where it is enforced:** `src/safety/url_safety.py`, `tests/conftest.py`, `tests/test_url_safety.py`, `pyproject.toml`, and `scripts/check_repo_hygiene.py` (`check_offline_test_network_discipline`).

### L-02: Test teardown deleted the operational database
- **Symptom:** Running Playwright E2E and a TDD startup test against an inherited `SQLITE_DB_PATH` erased `data/cache.sqlite` while leaving older backups intact.
- **Root cause:** Inherited DB environment variables flowed into test servers and an unguarded teardown `unlink()` ran against the operational database path.
- **Mechanism that prevents it:** Six-layer defense-in-depth isolation (`ADR 0030`), default-deny operational runtime grants, dedicated `BOTTOM_POT_DATA_DIR` outside the repo (Phase 7), and static + AST checks blocking broad exception swallowing over safety/storage code.
- **Where it is enforced:** `src/safety/db_safety.py`, `playwright.config.js`, `tests/conftest.py`, `scripts/check_db_safety.py`, `tests/test_operational_db_safety.py`, and `scripts/check_repo_hygiene.py` (`check_safety_broad_excepts`, `check_forbidden_tracked_files`).

### L-03: The same provider bug was fixed separately in several providers
- **Symptom:** Nine monitored ATS adapters in `board_adapters.py` (4,313 lines) duplicated HTTP fetches, completeness checks, hashing, ETag handling, error classification, and cache repair across separate code paths.
- **Root cause:** No shared executable provider contract or shared snapshot/fingerprint/closure primitives existed across adapters.
- **Mechanism that prevents it:** Parametrized conformance suite across all nine monitored providers (`tests/conformance/` C1–C12), shared provider primitives (`src/providers/{contract,fingerprint,http,pagination,detail_hydration}.py`, `src/core/clock.py`), per-provider module split (`src/providers/<name>.py`), and per-module line-limit enforcement.
- **Where it is enforced:** `tests/conformance/test_provider_conformance.py`, `src/providers/contract.py`, and `scripts/check_repo_hygiene.py` (`check_source_module_line_limits`).

### L-04: Docs recorded their own commit SHAs, causing ~20 churn commits
- **Symptom:** Step logs and protocol docs required first/last/merge commit SHAs inside committed files, forcing repeated follow-up bookkeeping commits after merge.
- **Root cause:** `AGENTS.md`, `BUILD_PROTOCOL.md`, and `docs/agents/PROJECT_COMPENDIUM.md` mandated writing self-referential commit SHAs into committed markdown files.
- **Mechanism that prevents it:** Replace the rule so provenance is the PR number and merge commit recorded in the PR description after merge, backed by a CI regex gate rejecting commit SHAs in active docs.
- **Where it is enforced:** `AGENTS.md`, `BUILD_PROTOCOL.md`, and `scripts/check_repo_hygiene.py` (`check_no_commit_shas_in_docs`).

### L-05: A step shipped a different scope than the owner's brief
- **Symptom:** PR #56 shipped provider and catalog expansion while the owner's Step 56 brief asked for reliability work.
- **Root cause:** Nothing in repo rules or PR workflows forced the executing agent to restate the owner's assigned scope or halt unapproved provider expansion.
- **Mechanism that prevents it:** Mandatory owner-scope restatement at the top of every PR body (`AGENTS.md`) and an active **Provider Freeze** prohibiting new ATS providers or employer boards until the owner lifts it.
- **Where it is enforced:** `AGENTS.md` (Mandatory Agent Checklist & §8.6).

### L-06: Display strings were parsed instead of structured data (`Paystack (+N more)`)
- **Symptom:** Frontend TypeScript eligibility logic (`frontend/src/lib/eligibility.ts`) duplicated and drifted from backend extraction (`eligibility_extractor.py`), misclassifying truncated display strings despite ADR 0003.
- **Root cause:** Eligibility logic lived in both Python and TypeScript without shared cross-language test vectors or strict backend authority.
- **Mechanism that prevents it:** Make backend-evaluated eligibility authoritative and verify regressions via shared cross-language vectors in `tests/vectors/eligibility.json` consumed by both `pytest` and `vitest` (Phase 5).
- **Where it is enforced:** `ADR 0003`, `tests/vectors/eligibility.json` (Phase 5), and backend/frontend test suites.

### L-07: Stale postings were presented as current
- **Symptom:** Live audit showed 9 of 12 "worldwide" roles on Metabase and Railway were stale-but-published (162–2,384 days old), appearing alongside genuinely fresh openings.
- **Root cause:** The canonical job model had only a raw posting date and lacked freshness tiers, age visibility, and freshness-first default ranking.
- **Mechanism that prevents it:** Explicit freshness enum (`fresh`, `recent`, `stale`, `evergreen`), freshness-first default ordering, visible `"Older postings"` divider, and Playwright E2E regression tests (Phase 5).
- **Where it is enforced:** Canonical job model, API serialization, frontend sorting/UI, and Playwright E2E tests (Phase 5).

### L-08: Fixtures and comparison screenshots grew to 95+ MB of repo bloat
- **Symptom:** Tracked docs accumulated 62+ MB of unreferenced before/after screenshots (442 PNGs) and 35+ MB of third-party fixtures, plus stale root artifacts (`frontend-old/`, `urls.txt`).
- **Root cause:** No asset size budget, top-level allow-list, documentation reachability check, or third-party data ledger existed in CI.
- **Mechanism that prevents it:** Top-level allow-list, 500 KB per-image/fixture size budgets, `THIRD_PARTY_DATA.md` tracking (Phase 8), docs link & reachability checks, and CI hygiene gates.
- **Where it is enforced:** `scripts/check_repo_hygiene.py` (`check_top_level_allowlist`, `check_asset_size_budgets`, `check_docs_links`, `check_docs_reachability`, `check_forbidden_tracked_files`).

### L-09: E2E tests wrote screenshots into tracked `docs/design/after/`
- **Symptom:** Running Playwright (`tests/e2e/bottom-pot.spec.js` step 28) silently modified tracked PNGs in `docs/design/after/`, leaving a dirty working tree on every local verification run.
- **Root cause:** The test passed hardcoded tracked repo paths to `screenshot({ path: ... })` instead of Playwright's isolated `testInfo.outputPath(...)`.
- **Mechanism that prevents it:** Route all Playwright test screenshot outputs through `testInfo.outputPath(...)` inside gitignored test artifact folders.
- **Where it is enforced:** `tests/e2e/bottom-pot.spec.js` and `git status` clean-tree verification in `AGENTS.md`.

### L-10: Legacy `frontend-old/` masked a broken unbuilt-frontend assertion in backend CI
- **Symptom:** Removing legacy `frontend-old/` caused `test_frontend_assets_are_served` to pass locally (where `frontend/dist` existed) while failing in CI (where `frontend/dist` was not built before `pytest`), because the test checked `"assets/" or "styles.css"`.
- **Root cause:** `tests/test_api_endpoints.py` accepted deleted `frontend-old/styles.css` instead of explicitly testing both the compiled `frontend/dist` (`assets/`) and clean-checkout unbuilt `frontend/index.html` (`/src/main.tsx`) paths.
- **Mechanism that prevents it:** Assert both unbuilt source fallback (`/src/main.tsx`) and compiled `dist` (`assets/`) explicitly, rejecting legacy `styles.css`.
- **Where it is enforced:** `tests/test_api_endpoints.py` (`test_frontend_assets_are_served`, `test_frontend_unbuilt_source_fallback_and_compiled_dist_selection`).
