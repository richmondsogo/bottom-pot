# ADR 0030: Operational SQLite Database Isolation and Destructive Test Safety

## Status

Accepted

## Context

On 2026-11-16, during Step 45 development and verification on Windows, two separate gaps combined to erase the operational SQLite database `data/cache.sqlite` (while leaving pre-existing `2026-11-13` backup files intact):

1. `playwright.config.js` preserved an inherited `PLAYWRIGHT_SQLITE_DB_PATH` pointing at the operational database rather than unconditionally creating a disposable database directory.
2. That inherited operational path flowed into the backend uvicorn server via `SQLITE_DB_PATH` (`src/config.py`), causing FastAPI startup and `CompanyBoardRegistry._ensure_db()` / `CacheStore._ensure_db()` schema initialization to run against `data/cache.sqlite`.
3. A pre-fix TDD RED test (`test_loaded_webserver_env_routes_app_startup_to_isolated_tmp_path`) executed a teardown cleanup (`unlink()`) on the path resolved from config under the assumption it was disposable.
4. No central Python path safety guard existed before SQLite connection/migration/cleanup calls, and no regression tests reproduced the full inherited-env + startup + cleanup failure chain.

This was a test infrastructure and destructive-cleanup design failure, not an SQLite engine corruption bug or a job provider defect. The operational database was subsequently recovered via Scenario B (`data/cache.sqlite.bak-pre-ashby-repair` + verified additive migration; see `docs/steps/45-smartrecruiters-quality-pipeline.md`).

## Safety Invariant

> **No automated test, E2E process, fixture, temporary application server, disposable rehearsal, or test cleanup routine may open, migrate, checkpoint, modify, truncate, replace, or delete `data/cache.sqlite`, its `-wal`/`-shm`/`-journal` sidecars, any `data/cache.sqlite.bak-*` backup, or preserved `.cache.sqlite.restore-staging-*` forensic artifacts.**

Setting `TESTING=true` or `CI=true` only *tightens* enforcement (never allowing an operational path to pass).

## Decision

We implement a six-layer defence-in-depth architecture rather than relying on environment-variable conventions alone:

1. **Layer 1 — Central Path Safety & Default-Deny Operational Authorization (`src/project_files/db_safety.py`)**:
   - Canonicalizes candidate paths relative to both CWD and `REPO_ROOT`, normalizing cross-platform `\` / `/` separators and case-folded operational lookalikes (e.g., `DATA\CACHE.SQLITE` on POSIX), resolving `file:` URIs and symlink/directory-junction chains (`resolve_canonical_path_following_links`), and checking `st_dev`/`st_ino` hard-link identity against all protected operational files and backups.
   - Fails closed (`UnsafeDatabasePathError`) on empty paths, directories, symlink loops, unresolvable paths, hard-link aliases, or protected targets.
   - **Denies operational `data/` DB access by default** — even for unknown processes or disposable scripts inheriting `.env` (`SQLITE_DB_PATH=data/cache.sqlite`) that set zero test/CI env vars. Legitimate operational access requires **all three**: (a) zero test/E2E/CI flags (`is_test_or_disposable_context() == False`), (b) explicit non-`.env` opt-in `BOTTOM_POT_ALLOW_OPERATIONAL_DB=1`, and (c) an in-process runtime grant (`authorize_operational_runtime(entrypoint)`) restricted to `DOCUMENTED_OPERATIONAL_ENTRYPOINTS` (`src.api.main:lifespan` via `scripts/run_prod.ps1`, `src.project_files.board_monitor:main`, and `*_cache_repair:main`). Note: the `DOCUMENTED_OPERATIONAL_ENTRYPOINTS` allow-list is an in-process guardrail against accidental calls from arbitrary scripts, not a cryptographic or adversarial OS security boundary. Automated test/E2E/CI flags unconditionally override and reject operational access even if `BOTTOM_POT_ALLOW_OPERATIONAL_DB=1` is set.
   - `scripts/run_prod.ps1` records any prior `BOTTOM_POT_ALLOW_OPERATIONAL_DB` value, scopes `=1` strictly to the child server process, and restores or removes it in a `finally` block (after test-marker rejection) so parent PowerShell sessions never retain production opt-in.
2. **Layer 2 — Unconditional E2E & Test Isolation (`playwright.config.js`, `tests/conftest.py`, `scripts/verify.ps1`)**:
   - `playwright.config.js` unconditionally allocates a fresh unique directory per run (`fs.mkdtempSync` inside a verified non-`data/` temp root), validates `e2e-cache.sqlite` and `e2e-subscriptions.csv`, overwrites `PLAYWRIGHT_SQLITE_DB_PATH`, `SQLITE_DB_PATH`, `PLAYWRIGHT_SUBSCRIPTIONS_FILE`, and `SUBSCRIPTIONS_FILE`, injects `BOTTOM_POT_TEST_MODE='1'`, forces `BOTTOM_POT_ALLOW_OPERATIONAL_DB='0'`, sets `MONITORING_ENABLED='false'`, and forces `reuseExistingServer: false` (preventing attachment to an arbitrary pre-existing dev server).
   - `tests/conftest.py` allocates an `OwnedDisposableWorkspace` and sets `SQLITE_DB_PATH`, `SUBSCRIPTIONS_FILE`, and `BOTTOM_POT_TEST_MODE` before importing `cache_store`, `company_board_registry`, or `src.api.main`.
3. **Layer 3 — Verified-Ownership Cleanup (`safe_cleanup_disposable_path`, `OwnedDisposableWorkspace`)**:
   - Destructive test cleanup requires an explicit `owned_root` verified outside the repo/operational `data/` directory and unconditionally rejects `data/`, sidecars, and backups regardless of context or flags.
4. **Layer 4 — Deferred Singletons, Store, Registry & App Lifespan Guards (`CacheStore`, `CompanyBoardRegistry`, `src/api/main.py`)**:
   - Module-level singletons (`cache_store`, `company_board_registry`) use deferred initialization (`_defer_init=True`) so mere module imports never open `data/cache.sqlite`.
   - `assert_safe_sqlite_db_path(...)` runs before `sqlite3.connect`, `mkdir`, `_ensure_db()` DDL/FTS migrations, and FastAPI `lifespan` startup, and `UnsafeDatabasePathError` is never swallowed by catch-all `except Exception:` blocks in `CacheStore` or `CompanyBoardRegistry`.
   - Idempotent migrations do **not** exempt an operational target.
5. **Layer 5 — Regression Tests (`tests/test_operational_db_safety.py`, `tests/test_playwright_isolation.py`)**:
   - Covers hostile env inheritance (`SQLITE_DB_PATH`, `PLAYWRIGHT_SQLITE_DB_PATH`), traversal aliases, backups/sidecars, hard links, junctions/symlinks, unowned cleanup, concurrent E2E runs, FastAPI startup failure, and full-chain hash-preservation verification.
6. **Layer 6 — CI Static, Ubuntu & Windows Safety Enforcement (`scripts/check_db_safety.py`, `.github/workflows/ci.yml`, `scripts/verify.ps1`)**:
   - Targeted static checks guard `playwright.config.js`, `.env`/`.env.example`, `tests/conftest.py`, and direct destructive calls referencing protected paths in `tests/`.
   - CI executes both `ubuntu-latest` (`backend-and-db-safety`, `frontend-checks`) and dedicated `windows-latest` (`windows-safety`) jobs across all pull requests and `main` pushes, covering Windows directory junctions, hostile Windows env roots, no-safe-temp fail-closed behavior, and real Windows PowerShell 5.1 launcher env-restoration tests.
   - *Platform note*: Standard unprivileged Windows without Developer Mode denies file symlink creation (`WinError 1314`); Windows tests cover equivalent reparse aliasing using NTFS directory junctions (`mklink /J`).

## Alternatives Considered

- **Relying only on `.env` / `conftest.py` / `verify.ps1` conventions**: Rejected. Any subprocess, `--noconftest` invocation, direct `npx playwright test`, or developer shell with inherited `SQLITE_DB_PATH` could bypass `conftest.py` or `verify.ps1`, as proved by the November 2026 incident.
- **Blocking all access to `data/cache.sqlite` unconditionally inside Python**: Rejected because legitimate production startup (`uvicorn src.api.main:app` outside test/CI contexts) must still be able to read and write `data/cache.sqlite`.
- **Regex-banning every `unlink()`/`rmtree()` across the repo**: Rejected as brittle and noisy; instead we combine runtime ownership checks with a targeted AST checker tested on positive and negative cases.

## Trade-offs

- Running `pytest` or Playwright directly with an explicit `SQLITE_DB_PATH=data/cache.sqlite` or `TESTING=true` + operational DB now aborts loudly (`UnsafeDatabasePathError`), requiring tests to use temp fixtures.
- Creating a unique `mkdtempSync` directory on every `playwright.config.js` evaluation ensures concurrent E2E runs cannot collide, at the minor cost of leaving an empty OS temp folder when tests only import config without executing `verify.ps1` wrapper cleanup.

## Consequences, Residual Risks & Limitations

- **What this prevents**: Accidental writes, schema migrations, server attachment (`reuseExistingServer`), `.env`-inherited access by unknown/disposable scripts without test markers, or destructive cleanup against `data/cache.sqlite`, sidecars, backups, symlinks, junctions, or hard-link aliases during `pytest`, Playwright E2E, `verify.ps1`, FastAPI `TestClient`, ad-hoc Python scripts, or test startup.
- **Residual risks outside guarantees**:
  - A deliberate operator invocation passing `--allow-operational-db` or `BOTTOM_POT_ALLOW_OPERATIONAL_DB=1` outside test/CI contexts (e.g., `scripts/run_prod.ps1`, `board_monitor.py`, or `*_cache_repair.py`) intentionally authorizes operational writes to `data/cache.sqlite`. Never place `BOTTOM_POT_ALLOW_OPERATIONAL_DB=1` inside `.env` or `.env.example`.
  - Direct raw `sqlite3` / external OS file tools bypassing `CacheStore`, `CompanyBoardRegistry`, and `db_safety.py` are outside Python/Node guardrails.
  - Filesystem `st_dev`/`st_ino` checks rely on OS metadata; filesystems lacking reliable inode identity fail closed (`UnsafeDatabasePathError`).
- **Verification requirements**: Any change touching `playwright.config.js`, `tests/conftest.py`, `src/project_files/cache_store.py`, `src/project_files/company_board_registry.py`, or cleanup helpers must pass `scripts/check_db_safety.py`, `tests/test_operational_db_safety.py`, `tests/test_playwright_isolation.py`, and pre/post SHA-256 verification of `data/` protected assets.
