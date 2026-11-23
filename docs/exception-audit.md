# Exception Audit & `SafetyError` Propagation Policy

Every module under `src/` is governed by a fail-closed safety invariant: **operational-database protection (`UnsafeDatabasePathError`) and SSRF protection (`UnsafeRedirectError`) inherit from `SafetyError` and must never be silently swallowed.**

---

## 1. Exception Hierarchy

```
Exception
└── BottomPotError                    (src/core/exceptions.py)
    └── SafetyError                   (src/core/exceptions.py — must never be swallowed)
        ├── UnsafeDatabasePathError   (src/safety/db_safety.py, also subclasses ValueError)
        └── UnsafeRedirectError       (src/safety/url_safety.py, also subclasses ValueError)
```

### Boundary Handling Rule

- **`SafetyError` & `UnsafeDatabasePathError`:** Must **always** propagate uncaught so any accidental attempt to access, migrate, clear, or delete the protected operational database (`data/cache.sqlite`, sidecars, backups, `subscriptions.csv`) terminates the operation immediately rather than degrading to an empty result.
- **`UnsafeRedirectError`:** At explicit provider/scraper SSRF boundary adapters (`src/providers/*.py` `check_board`, `src/ats/ats_page_enricher.py`, `src/discovery/search_pipeline.py`), `except UnsafeRedirectError` **must precede** `except SafetyError: raise` so blocked private/loopback/metadata destinations fail closed into structured results (`FailureKind.UNSAFE_URL`, HTTP `403`, or `None`) without swallowing `UnsafeDatabasePathError` or generic `SafetyError` instances.

---

## 2. Specific Silent-Swallowing Bugs Fixed in Phase 4b

| File | Symbol / Site | Prior Bug | Fix Applied |
|---|---|---|---|
| `src/storage/company_board_registry.py` | `search_monitored_jobs` (FTS5 & LIKE fallback) | Caught `Exception` without `except UnsafeDatabasePathError: raise`, silently returning `[]` if an unsafe operational path reached a deferred registry instance | Added `except SafetyError: raise` before narrowed `(sqlite3.Error, OSError, ValueError, TypeError)` handlers |
| `src/storage/company_board_registry.py` | FTS5 table setup & delete helpers | Caught broad `Exception:` around `conn.execute(...)` | Narrowed to `except sqlite3.Error:` (`SafetyError` cannot be trapped) |
| `src/ats/ats_api_client.py` | `enrich_*_board_identity`, `_get_html` | Caught `(CircuitBreakerOpenError, HostRateLimitedError, Exception)` and returned `(None, exc, attempts)` or existing logo without re-raising `SafetyError` / `CancelledError` | Added explicit `except (asyncio.CancelledError, SafetyError): raise` before every catch-all / transport handler |
| `src/providers/recruitee.py` | `parse_and_extract` / identity enrich | Bare `except Exception: pass` around `enrich_recruitee_board_identity` swallowed both `asyncio.CancelledError` and `SafetyError` | Added `except (asyncio.CancelledError, SafetyError): raise` before fallback `pass` |
| `src/providers/*.py` & `detail_hydration.py` | `check_board`, snapshot fetchers, batch hydration | `check_board` and helpers caught broad `Exception` (relying on `classify_exception`) or caught generic network exceptions in `detail_hydration.py` | Re-raises `(asyncio.CancelledError, SafetyError)` inside `detail_hydration.py` and identity enrich helpers; catches `except UnsafeRedirectError` -> `FailureKind.UNSAFE_URL` before `except SafetyError: raise` in every provider `check_board` |
| `src/discovery/search_pipeline.py` | `_run_monitored_store`, `stream_search` task loop, enrichment/probe wrappers | Caught `Exception` around `company_board_registry.search_monitored_jobs` and asyncio task completions, masking `SafetyError` | Added `except (asyncio.CancelledError, SafetyError): raise` on all DB/network/task boundaries while keeping `UnsafeRedirectError` fail-closed |
| `src/core/http_resilience.py` | `throttled_get`, `throttled_stream_bytes`, redirect fetcher | `except Exception:` incremented remote-host circuit breaker failures on local `SafetyError` or task cancellation | Added `except (asyncio.CancelledError, SafetyError): raise` before recording host failure |

---

## 3. Package-by-Package Exception Risk Table (`src/`)

AST scan of all broad `except` handlers (`except:`, `Exception`, `BaseException`, or tuples containing them) across `src/` before vs. after Phase 4b hardening:

| Package | Risk Tier | Before | After | Policy & Disposition |
|---|---|---|---|---|
| `src/safety/` | **Critical** | `1` | `0` | All handlers narrowed (`url_safety.py` `urlsplit` narrowed to `ValueError`); `0` broad handlers allowed. |
| `src/storage/` | **Critical** | `39` | `0` | `cache_store.py` (`9 -> 0`) and `company_board_registry.py` (`30 -> 0`) narrowed to `(sqlite3.Error, OSError, ValueError, TypeError)` / `(ValueError, TypeError)` with explicit `except SafetyError: raise` guards. |
| `src/monitoring/` | **Critical** | `25` | `2` | `cache_repair/engine.py` + 4 strategies have `0` broad handlers (`23 -> 0`). Remaining `2` in `board_monitor.py` (`check_single_board`, `run_loop`) are annotated `# broad-except-ok:` and preceded by `except SafetyError: raise`. |
| `src/providers/` | **High** | `28` | `19` | `9` pure JSON/XML/float/URL parse handlers narrowed. Remaining `19` network/enrichment/adapter boundaries across all 10 files catch `UnsafeRedirectError` explicitly (fail closed) and re-raise `(asyncio.CancelledError, SafetyError)`. |
| `src/ats/` | **High** | `54` | `47` | `ats_api_client.py` (`21`), `direct_board_router.py` (`12`), and `ats_page_enricher.py` (`1`) protect `SafetyError` with explicit re-raises; `7` pure URL/JSON parse blocks narrowed; `ats_url_parser.py` (`13`) is pure URL parsing with no DB/network I/O. |
| `src/discovery/` | **High** | `27` | `19` | `search_pipeline.py` (`8`) and `nigerian_scrapers.py` (`11`) protect `SafetyError` on every DB/network/task boundary; `8` pure URL/JSON-LD/CF-email parse blocks narrowed. |
| `src/core/` | **Medium** | `6` | `3` | `http_resilience.py` (`3`) re-raises `(asyncio.CancelledError, SafetyError)` before recording failure; `retry.py` and header/URL helpers narrowed (`3 -> 0`). |
| `src/api/` | **Medium** | `2` | `2` | `main.py` SSE `/search` generator (`1`) re-raises `SafetyError` explicitly; `auth.py` (`1`) validates stateless HMAC/JSON session tokens without DB/network I/O. |
| `src/extraction/` | **Low** | `12` | `9` | `logo_extractor.py` (`3 -> 0`) narrowed; remaining `9` across `confidence_policy.py` (`1`), `extraction_outcome.py` (`1`), `field_normalizer.py` (`1`), `salary_parser.py` (`1`), and `url_normalizer.py` (`5`) are pure string/numeric parsers with no DB/network I/O. |
| **Total (`src/`)** | — | **`194`** | **`101`** | **Every critical/high DB & network path propagates `SafetyError`; zero grandfathered safety exemptions remain.** |

---

## 4. Automated CI Enforcement

1. **`scripts/check_repo_hygiene.py` (`check_safety_broad_excepts`):**
   - `GRANDFATHERED_BROAD_EXCEPT_COUNTS` is cleared to `{}`.
   - Any unannotated broad handler in `src/safety/`, `src/storage/`, or `src/monitoring/` fails CI immediately.
2. **`scripts/check_db_safety.py` (`check_safety_error_propagation`):**
   - **Rule A (`src/**/*.py`):** Every `except SafetyError` or `except UnsafeDatabasePathError` handler must contain `raise`.
   - **Rule B (`src/safety/`, `src/storage/`, `src/monitoring/`, `src/providers/`):** Every broad `except` handler (`except:`, `Exception`, `BaseException`) must be preceded on the same `try` block by an `except SafetyError: raise` (or `UnsafeDatabasePathError`) sibling handler.
3. **Runtime Regression Suite (`tests/test_operational_db_safety.py` & `tests/test_cache_repair_engine.py`):**
   - Verifies subclassing (`BottomPotError -> SafetyError -> UnsafeDatabasePathError / UnsafeRedirectError`).
   - Verifies `CacheStore`, `CompanyBoardRegistry` (including `search_monitored_jobs`), `BoardMonitor.check_single_board`, `run_cache_repair`, and all 9 `BOARD_ADAPTERS` propagate `SafetyError` / `UnsafeDatabasePathError` uncaught while failing closed on `UnsafeRedirectError`.
