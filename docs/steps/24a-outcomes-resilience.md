# Step 24a: Explicit Outcomes, Bounded Retries, and Failure Isolation

Initiative: **Extraction Pipeline & Architecture Overhaul**  
Role: **Planner / Builder**  
Branch: `step/24a-outcomes-resilience`  
Base Commit: `61e841916b4f82562a8ca74ff837c6eeea609481`  
Date: 2026-11-01  
Status: **In Progress**  

---

## 1. Scope & Implementation Checklist

Establish typed extraction outcomes (`ExtractionOutcome`), structured result objects for ATS and page enrichment callers (`ExtractionResult`), explicit degraded-from provenance tracking, bounded idempotent retries respecting search budgets, multi-provider failure isolation, and transparent `provider_outcomes` wire telemetry in `DoneEvent`.

### Checklist
- [x] **Commit 1: Pre-checks, Audit Doc & Baseline Snapshot**
  - [x] Pre-checks verified: `git status` clean on `main`, zero scratch scripts, tests baseline verified (`8/8 verify.ps1`, `470 pytest`, `74 vitest`, `33 playwright`).
  - [x] Confirmed PR #27 merged (`796d3d821fc878799e1875c8d18dca3e3c6b612a`) and provenance recorded in `docs/steps/23-provenance-identity-dedup.md`.
  - [x] Read-only audit of all provider fetch, enrichment, and scraper error paths, `http_resilience.py`, `ErrorEvent`/`DoneEvent` contracts, and frontend event handling.
  - [x] Audit additions completed: usages of `with_retry`, nested retry multiplication analysis, Serper search call failure mode, Nigerian scraper failure modes, and broad `except Exception` inventory.
- [x] **Commit 2: Outcome Enum, ADR 0029, and Mapping Tests**
  - [x] Write ADR 0029 defining exact mapping and semantics for `ExtractionOutcome`: `success`, `partial_success`, `not_found`, `retryable_error`, `permanent_error`, `parse_error`, `unsupported_source`, `rate_limited`.
  - [x] Create `ExtractionResult` container carrying outcome, optional `RawJobPosting`, HTTP status code, sanitized error summary, and attempt count.
  - [x] Red-Green test suite for HTTP status / exception to `ExtractionOutcome` mapping table (`tests/test_extraction_outcomes.py`, 22 passed).
- [ ] **Commit 3: Result-Returning Variants for the 7 ATS Clients**
  - [x] 3.1 Greenhouse (`GreenhouseClient.fetch_raw_result` / `fetch_result`)
  - [x] 3.2 Lever (`LeverClient.fetch_raw_result` / `fetch_result`)
  - [x] 3.3 Ashby (`AshbyClient.fetch_raw_result` / `fetch_result`)
  - [x] 3.4 SmartRecruiters (`SmartRecruitersClient.fetch_raw_result` / `fetch_result`)
  - [x] 3.5 Workable (`WorkableClient.fetch_raw_result` / `fetch_result`)
  - [ ] 3.6 BambooHR (`BambooHRClient.fetch_raw_result` / `fetch_result`)
  - [ ] 3.7 Recruitee (`RecruiteeClient.fetch_raw_result` / `fetch_result`)
  - [ ] Backward compatibility: public `fetch()` preserved across all 7 clients without collapsing failures into `None` internally. Goldens unchanged.
- [ ] **Commit 4: Enricher, Scraper Paths & Visible Degradation**
  - [ ] 4.1 Page Enricher (`ats_page_enricher.py` returns `ExtractionResult` carrying `RawJobPosting` / outcome).
  - [ ] 4.2 Nigerian Scrapers (`nigerian_scrapers.py` listing-page and detail-page return structured outcomes).
  - [ ] 4.3 Visible degradation: Add additive per-job keys `extraction_outcome` and `degraded_from` ONLY when a job degraded after a failure (API to page to snippet). Absent on successful records and native snippets. List every golden diff (only fallback fixtures).
- [ ] **Commit 5: Bounded Retry Policy & Search Budget Interaction**
  - [ ] Bounded retry engine in `retry.py`: only `retryable_error` (408, 500, 502, 503, 504, timeout, connection, DNS, circuit open with 0 attempts) and `rate_limited` (429) on idempotent GETs.
  - [ ] Serper (paid POST) gets NO automatic retries; records outcome only.
  - [ ] Retry parameters: 2 retries (3 attempts total), 0.5s base doubling, full jitter from injected RNG, 5s per-delay cap, 10s total delay cap per job.
  - [ ] Honor `Retry-After` only if it fits remaining budget, else give up as `rate_limited`.
  - [ ] Never retry `not_found`, `permanent_error`, `parse_error`, `unsupported_source`, or circuit-open skip.
  - [ ] Retries use same per-host limiter and count against search budget (`SearchRunStats`); inject clock, sleep, and RNG for deterministic tests.
  - [ ] Define breaker failure outcomes: 5xx, timeout, network error count as breaker failures; 429 does NOT trip breaker. Test retry/breaker interaction.
- [ ] **Commit 6: Failure Isolation in the Search Pipeline**
  - [ ] Heterogeneous provider failures isolated: `asyncio.gather(..., return_exceptions=True)` results classified and counted, never dropped.
  - [ ] Unexpected exceptions (programming errors) logged at ERROR level with reason `unexpected_exception`, counted as `permanent_error`, and never silently turned into a normal-looking snippet.
  - [ ] Correctly handle `asyncio.CancelledError`.
  - [ ] Successful providers continue streaming.
- [ ] **Commit 7: Honest Search Outcome on Wire, Frontend Tolerance & Observability**
  - [ ] `provider_outcomes` on `DoneEvent`: per-provider counts by outcome and `partial` flag only (no URLs, no messages).
  - [ ] Partial definition: true if provider has any `retryable_error`, `rate_limited`, `permanent_error`, or `parse_error`. (`not_found` and `unsupported_source` do not mark partial).
  - [ ] Classify new keys in `allowlist.py` and `frontend/src/types.ts`.
  - [ ] Frontend tolerance verified via Vitest and Playwright.
  - [ ] Safe errors and logs: Error summaries and logs never include query strings, tokens, or raw exception text containing URLs (reuse `sanitize_source_url`). Test with credential-bearing URL in log path and error summary.

---

## 2. Read-Only Audit of Current Behavior & Failure Handling

### 2.1 Provider Fetches (`ats_api_client.py`)
- **Greenhouse (`GreenhouseClient`)**:
  - `_do_fetch` decorated with `@with_retry(max_attempts=3, base_delay=1.0)` (lines 126-130).
  - `fetch_raw`: Line 146 catches 404 and returns `None`. Other status codes raise `HTTPStatusError` (line 149). Line 150 catches generic `Exception` and re-raises.
  - `fetch`: Catches any `Exception` (line 202) and falls back to `_fallback(...)`, converting failures into `JobListing(data_source="snippet")`.
- **Lever (`LeverClient`)**:
  - `_do_fetch` decorated with `@with_retry` (line 217). Catches 404 returning `None` (line 234). `fetch` catches any `Exception` (line 297) and falls back to `_fallback(...)`.
- **Ashby (`AshbyClient`)**:
  - `_do_fetch` decorated with `@with_retry` (line 312). Catches 404 returning `None` (line 329). `fetch` catches any `Exception` (line 387) and falls back to `_fallback(...)`.
- **SmartRecruiters (`SmartRecruitersClient`)**:
  - `_do_fetch` decorated with `@with_retry` (line 402). Catches 404 returning `None` (line 422). `fetch` catches any `Exception` (line 486) and falls back to `_fallback(...)`.
- **Workable (`WorkableClient`)**:
  - `_do_fetch` decorated with `@with_retry` (line 501). Catches 404 returning `None` (line 509). `fetch` catches any `Exception` (line 581) and falls back to `_fallback(...)`.
- **BambooHR (`BambooHRClient`)**:
  - `_do_fetch` decorated with `@with_retry` (line 596). Catches 404 returning `None` (line 613). `fetch` catches any `Exception` (line 678) and falls back to `_fallback(...)`.
- **Recruitee (`RecruiteeClient`)**:
  - `_do_fetch` decorated with `@with_retry` (line 693). Catches 404 returning `None` (line 710). `fetch` catches any `Exception` (line 762) and falls back to `_fallback(...)`.

### 2.2 Nested Retry Analysis & Usages of `with_retry`
- `with_retry` is currently applied ONLY to the `_do_fetch` private method in each of the 7 ATS clients in `ats_api_client.py` (lines 126, 217, 312, 402, 501, 596, 693).
- **Nested Retry Check**:
  - `search_pipeline.py` calls `ats_client.fetch(...)`. There is NO outer retry decorator or retry loop wrapping `fetch(...)`.
  - In `nigerian_scrapers.py`, `JobbermanScraper.search()` (lines 297-304) has an ad-hoc single retry on `RateLimitError` (`await asyncio.sleep(5)` then retry once). It does NOT use `with_retry`.
  - There is currently **no nested retry multiplication** in the production pipeline, but ad-hoc retry logic in scrapers must be unified into the single bounded retry policy in `retry.py`.

### 2.3 Serper Search Call Failure Mode (`search_pipeline.py`)
- Serper is a paid outbound POST endpoint (`SERPER_ENDPOINT`, line 326).
- Checked against `cache_store.check_and_increment_daily_budget` before invocation (line 312).
- Inside `_search_ats_serper` (lines 325-340):
  ```python
  try:
      resp = await client.post(SERPER_ENDPOINT, json=payload, headers=..., timeout=...)
      resp.raise_for_status()
      data = resp.json()
      cache_store.set_serper_cache(cache_key, data)
  except Exception as exc:
      logger.warning(f"[{platform}] Serper page {page} failed: {exc}")
      continue
  ```
- Failure behavior today: Any failure (network error, timeout, 400 invalid query, 403 invalid API key, 429 over budget) logs a warning and executes `continue` to the next page.
- Under Step 24a rule: Serper is a paid POST and gets **no automatic retries**; its outcome must simply be recorded.

### 2.4 Nigerian Listing-Page & Detail-Page Fetch Failures (`nigerian_scrapers.py`)
- Base scraper `fetch_html` (lines 167-176):
  - On 429: raises `RateLimitError(self.site_name)`.
  - On 4xx/5xx: `response.raise_for_status()` raises `httpx.HTTPStatusError`.
  - On Cloudflare/WAF challenge: `_check_bot_block` raises `BotBlockError`.
- In `search()` methods:
  - `JobbermanScraper`: lines 295-310 catches `RateLimitError` (manual 5s wait retry), `BotBlockError` (returns empty `listings`), `Exception` (returns empty `listings`). Detail fetches (line 262) are wrapped in `try/except Exception: pass`.
  - `MyJobMagScraper`: lines 428-432 catches `Exception` returning `listings`.
  - `NgCareersScraper`: lines 571-575 catches `Exception` returning `listings`.
  - `HotNigerianJobsScraper`: lines 1698-1704 catches `Exception` during detail fetch and continues; lines 1740-1744 catches `Exception` on top-level search and returns partial/empty listings.
- In `search_pipeline.py` (lines 384-396 `_search_nigerian_scraper`):
  ```python
  try:
      listings = await scraper.search(client, params)
      return (scraper.site_name, listings, False)
  except Exception as exc:
      logger.warning(f"[{scraper.site_name}] Scraper failed: {exc}")
      return (scraper.site_name, [], False)
  ```
  Any failure swallows the error and reports 0 listings without error classification.

### 2.5 Broad `except Exception` Inventory in Fetch and Enrichment Paths
1. `ats_api_client.py`:
   - Line 150 (`GreenhouseClient.fetch_raw`): `except Exception as exc: raise`
   - Line 202 (`GreenhouseClient.fetch`): `except Exception as exc: return _fallback(...)`
   - Line 238 (`LeverClient.fetch_raw`): `except Exception as exc: raise`
   - Line 297 (`LeverClient.fetch`): `except Exception as exc: return _fallback(...)`
   - Line 333 (`AshbyClient.fetch_raw`): `except Exception as exc: raise`
   - Line 387 (`AshbyClient.fetch`): `except Exception as exc: return _fallback(...)`
   - Line 426 (`SmartRecruitersClient.fetch_raw`): `except Exception as exc: raise`
   - Line 486 (`SmartRecruitersClient.fetch`): `except Exception as exc: return _fallback(...)`
   - Line 529 (`WorkableClient.fetch_raw`): `except Exception as exc: raise`
   - Line 581 (`WorkableClient.fetch`): `except Exception as exc: return _fallback(...)`
   - Line 617 (`BambooHRClient.fetch_raw`): `except Exception as exc: raise`
   - Line 678 (`BambooHRClient.fetch`): `except Exception as exc: return _fallback(...)`
   - Line 714 (`RecruiteeClient.fetch_raw`): `except Exception as exc: raise`
   - Line 762 (`RecruiteeClient.fetch`): `except Exception as exc: return _fallback(...)`
2. `ats_page_enricher.py`:
   - Line 76 (`_company_from_title`): `except Exception: return None`
   - Line 316 (`_build_workday_cxs_url` fetch): `except Exception as exc: ... falling back to HTML/JSON-LD`
   - Line 553 (Secondary apply URL JSON-LD fetch): `except (httpx.HTTPError, ValueError): pass`
3. `search_pipeline.py`:
   - Line 261 (`_enrich_ats_item`): `except Exception as exc: return _snippet_listing(...)`
   - Line 338 (`_search_ats_serper`): `except Exception as exc: continue`
   - Line 394 (`_search_nigerian_scraper`): `except Exception as exc: return (scraper.site_name, [], False)`
   - Line 588 (`run` task loop): `except Exception as exc: self._record_source_telemetry(..., FAILURE)`

### 2.6 Provenance Confirmation
- PR #27 verified merged into `main` (`796d3d821fc878799e1875c8d18dca3e3c6b612a`).
- Provenance table in `docs/steps/23-provenance-identity-dedup.md` fully recorded with first commit (`6f20c4d`), last commit (`a935921`), PR URL, and merge commit SHA.
