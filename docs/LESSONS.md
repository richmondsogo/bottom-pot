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
- **Mechanism that prevents it:** Six-layer defense-in-depth isolation (`ADR 0030`), default-deny operational runtime grants, external `BOTTOM_POT_DATA_DIR` support across repo and OS data directories (`ADR 0032`), `SafetyError` non-swallowing invariant (`docs/exception-audit.md`), and static + AST checks blocking broad exception swallowing or `SafetyError` catching without re-raise.
- **Where it is enforced:** `src/core/exceptions.py`, `src/core/data_dir.py`, `src/safety/db_safety.py`, `playwright.config.js`, `tests/conftest.py`, `scripts/check_db_safety.py` (`check_safety_error_propagation`), `tests/test_operational_db_safety.py`, and `scripts/check_repo_hygiene.py` (`check_safety_broad_excepts`, `check_forbidden_tracked_files`).

### L-03: The same provider bug was fixed separately in several providers
- **Symptom:** Nine monitored ATS adapters in `board_adapters.py` (4,313 lines) duplicated HTTP fetches, completeness checks, hashing, ETag handling, error classification, and cache repair across separate code paths.
- **Root cause:** No shared executable provider contract or shared snapshot/fingerprint/closure primitives existed across adapters.
- **Mechanism that prevents it:** Parametrized conformance suite across all nine monitored providers (`tests/conformance/` C1–C12), shared provider primitives (`src/providers/{contract,fingerprint,http,pagination,detail_hydration}.py`, `src/core/clock.py`), per-provider module split (`src/providers/<name>.py`), unified dry-run-by-default cache repair engine (`src/monitoring/cache_repair/engine.py`), and per-module line-limit enforcement.
- **Where it is enforced:** `tests/conformance/test_provider_conformance.py`, `src/providers/contract.py`, `src/monitoring/cache_repair/engine.py`, `tests/test_cache_repair_engine.py`, and `scripts/check_repo_hygiene.py` (`check_source_module_line_limits`).

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
- **Mechanism that prevents it:** Backend (`src/extraction/eligibility_extractor.py`, `src/extraction/eligibility_labels.py`, `POST /api/eligibility/evaluate`) owns authoritative `objective_scope_label` and `applicant_assessment`; legacy TypeScript logic is isolated to `frontend/src/lib/legacyEligibilityFallback.ts`; shared vectors in `tests/vectors/eligibility.json` are verified by both `pytest` (`tests/test_eligibility_vectors.py`) and `vitest` (`frontend/src/lib/__tests__/eligibilityVectors.test.ts`).
- **Where it is enforced:** `ADR 0003`, `tests/vectors/eligibility.json`, `POST /api/eligibility/evaluate`, and backend/frontend vector suites.

### L-07: Stale postings were presented as current
- **Symptom:** Live audit showed 9 of 12 "worldwide" roles on Metabase and Railway were stale-but-published (162–2,384 days old), appearing alongside genuinely fresh openings.
- **Root cause:** The canonical job model had only a raw posting date and lacked freshness tiers, age visibility, and freshness-first default ranking.
- **Mechanism that prevents it:** Canonical `FreshnessTier` (`fresh <= 30d`, `recent <= 90d`, `stale > 90d`, conservative `evergreen` only on explicit ATS flag or statement), freshness-first default ordering (`src/extraction/freshness.py`, `frontend/src/lib/freshness.ts`, `frontend/src/lib/sort.ts`), visible age badges + `"Older postings"` divider before stale roles, read-only `scripts/report_freshness.py`, and Playwright E2E regression tests.
- **Where it is enforced:** `src/extraction/freshness.py`, API allowlist/SSE/registry hydration, frontend UI/sorting, `tests/test_freshness.py`, `frontend/src/lib/__tests__/freshness.test.ts`, and `tests/e2e/bottom-pot.spec.js`.

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

### L-11: Logo fallbacks must never guess domains or leak ATS hosts
- **Symptom:** API-only ATS job listings without HTML-scraped logos fell back immediately to monograms, while naive URL host extraction or company-name guessing risks rendering ATS logos or wrong-company marks (`ADR 0001`).
- **Root cause:** No centralized public-suffix domain resolver or explicit ATS host deny-list existed between backend catalog/apply URLs and `CompanyMark.tsx`.
- **Mechanism that prevents it:** `src/extraction/domain_extractor.py` resolves `company_domain` strictly from verified catalog boards (`employer_board_catalog.py`) or non-ATS `apply_url` registrable hosts via `publicsuffixlist`, while `CompanyMark.tsx` orders `api -> Logo.dev (fallback=404) -> monogram` without backend image proxying or secret `sk_` key exposure.
- **Where it is enforced:** `ADR 0031`, `src/extraction/domain_extractor.py`, `scripts/logo_coverage.py`, `frontend/src/lib/logo.ts`, `tests/test_company_domain_and_logo_coverage.py`, and Playwright Logo.dev fallback tests.

### L-12: Operational SQLite needs external storage and WAL/SHM-safe recovery before mutations
- **Symptom:** Operational SQLite state defaulted inside the source checkout (`data/cache.sqlite`) with no backup, integrity-check, or restore-rehearsal utility, and plain file copies risk splitting live `-wal`/`-shm` transactions.
- **Root cause:** Storage settings lacked an outside-repo `BOTTOM_POT_DATA_DIR` default/override and lacked an online `sqlite3.Connection.backup()` + rehearsal CLI protected under `ADR 0030`.
- **Mechanism that prevents it:** `src/core/data_dir.py` defaults new production installs outside the repo while keeping legacy `data/cache.sqlite` working until migrated, `src/safety/db_safety.py` + `playwright.config.js` + `tests/conftest.py` extend all `ADR 0030` layers to `BOTTOM_POT_DATA_DIR`, and `src/storage/db_backup.py` / `scripts/db_backup.py` provide WAL/SHM-consistent backups, integrity checks, and disposable restore rehearsal (`docs/operations/RUNBOOK.md`).
- **Where it is enforced:** `src/core/data_dir.py`, `src/safety/db_safety.py`, `src/storage/db_backup.py`, `scripts/db_backup.py`, `scripts/check_db_safety.py`, `tests/test_data_dir_and_backup.py`, and `docs/operations/RUNBOOK.md`.

### L-13: Python `with sqlite3.connect(...)` does not close connections on exit
- **Symptom:** `tests/test_freshness.py::test_registry_hydrates_freshness_timestamps_and_orders_results` flaked on Windows CI when a read-only `report_from_sqlite()` call observed DB file bytes changing due to an asynchronous WAL checkpoint triggered during GC.
- **Root cause:** `CacheStore._get_connection()` and `CompanyBoardRegistry._get_connection()` returned raw `sqlite3.Connection` objects; Python's `with sqlite3.Connection:` commits or rolls back transactions on `__exit__` without calling `.close()`, leaving WAL connections open until GC collected them.
- **Mechanism that prevents it:** Route file-backed store and registry connections through `managed_sqlite_connection` (`src/storage/sqlite_conn.py`), a `@contextmanager` that preserves `with conn:` transaction semantics while deterministically calling `conn.close()` in `finally`.
- **Where it is enforced:** `src/storage/sqlite_conn.py`, `src/storage/cache_store.py`, `src/storage/company_board_registry.py`, and `tests/test_data_dir_and_backup.py` (`test_store_and_registry_deterministically_close_sqlite_connections_without_gc`).

### L-14: Explicit invalid token overrides must never silently fall back to configured env keys
- **Symptom:** Passing an invalid or secret (`sk_`) override token to `getConfiguredLogoDevToken(override)` fell through to `VITE_LOGO_DEV_TOKEN` whenever a local `.env.local` publishable key was set.
- **Root cause:** `getConfiguredLogoDevToken` checked `if (isValidPublishableLogoDevToken(overrideToken))` without returning `null` when a non-empty invalid override was explicitly supplied.
- **Mechanism that prevents it:** Explicit non-empty overrides are validated in isolation and return `null` on failure without env fallback; covered by Vitest regression assertion with stubbed `VITE_LOGO_DEV_TOKEN`.
- **Where it is enforced:** `frontend/src/lib/logo.ts` (`getConfiguredLogoDevToken`) and `frontend/src/lib/__tests__/companyMark.test.tsx`.
