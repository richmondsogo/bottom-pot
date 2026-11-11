# Step 32: Final Correctness Pass Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the 7 correctness issues in Step 32 (`step/32-global-ats-monitoring-registry`), including empty platform selection, monitored-job tri-state remote & date filters, SQLite cross-process revision counter, Greenhouse authentic descriptions, platform migration set matching, Nigerian scraper tests, and backlog scheduling.

**Architecture:** Maintain the existing ATS-first architecture, SQLite monitored job store, board registry, and SSE pipeline. Enhance precision of search contracts, transactional database revisions, description extraction, and scheduling fairness without adding new external infrastructure.

**Tech Stack:** FastAPI, Python 3.14, SQLite3 with FTS5, React 19, TypeScript, Vitest, Pytest, Playwright, Tailwind CSS.

**Spec:** Step 32 Final Correctness Pass prompt requirements.

## Global Constraints
- Primary branch `main` is protected: direct commits forbidden. Work strictly on `step/32-global-ats-monitoring-registry`.
- Do NOT merge PR #36 or approve it.
- Never invent job data or description text (Unknown beats wrong - ADR 0001).
- Square geometry is non-negotiable (`--radius: 0`).
- No distributed queue or external infrastructure dependencies.

## Review Focus
1. An explicit empty platform selection (`?platforms=`) must not fall back to default all-providers.
2. `is_remote=False` must exclude remote jobs while preserving onsite, hybrid, and unknown arrangements.
3. Posted date filter must only match authoritative `posted_at` dates; unknown dates must be excluded when filtering by recent days.
4. Separate instances of `CompanyBoardRegistry` pointing to the same SQLite database must share revision updates immediately and invalidate search caches without waiting for TTL.
5. Greenhouse jobs must only have `description_is_authentic=True` when authentic HTML/text is returned from the provider.

---

### Task 1: Fix Explicit Empty Platform Selection

**Files:**
- Modify: `frontend/src/App.tsx:719-721`
- Modify: `frontend/src/lib/urlState.ts:40-70`
- Modify: `src/api/main.py:126-143`
- Modify: `src/project_files/query_builder.py:72-85`
- Modify: `src/project_files/search_pipeline.py:618-680`
- Test: `tests/test_empty_platform_selection.py`
- Test: `frontend/src/lib/__tests__/urlState.test.ts`

**Interfaces:**
- Frontend: Transmits `platforms=""` or `platforms=none` when `selectedPlatforms.length === 0`.
- Backend FastAPI route: Distinguishes `platforms is None` (omitted -> default providers) from `platforms is not None` (e.g. `platforms=""` -> `target_platforms = []`).
- `build_ats_queries(params, platforms)`: When `platforms is not None and not platforms`, returns `{}`.
- `SearchOrchestrator.run(params, platforms)`: When `platforms == []`, skips ATS Serper, Nigerian scrapers, direct board routing, and monitored store.

- [ ] **Step 1: Write failing test in `tests/test_empty_platform_selection.py`**
- [ ] **Step 2: Run pytest to verify it fails**
- [ ] **Step 3: Implement contract in `src/api/main.py`, `src/project_files/query_builder.py`, `src/project_files/search_pipeline.py`, and `frontend/src/App.tsx`**
- [ ] **Step 4: Run pytest and vitest to verify it passes**
- [ ] **Step 5: Commit**

---

### Task 2: Correct Monitored-Job Filters

**Files:**
- Modify: `src/project_files/search_pipeline.py:557-567`
- Modify: `src/project_files/company_board_registry.py:760-785`
- Test: `tests/test_monitored_jobs_search.py`

**Interfaces:**
- `SearchOrchestrator._search_monitored_store(params, platforms)`: Passes `is_remote=params.remote` (tri-state: `True`, `False`, or `None`).
- `CompanyBoardRegistry.search_monitored_jobs`:
  - `is_remote is True`: `(m.work_model = 'remote' OR (m.location LIKE '%remote%' AND m.location NOT LIKE '%not remote%'))`
  - `is_remote is False`: `((m.work_model != 'remote' OR m.work_model IS NULL) AND (m.location IS NULL OR m.location NOT LIKE '%remote%'))`
  - `posted_within_days > 0`: `m.posted_at IS NOT NULL AND m.posted_at >= ?` (with `cutoff_iso`)

- [ ] **Step 1: Write failing regression tests in `tests/test_monitored_jobs_search.py` for old job discovered today, recently posted job, active job with no verified date, and remote/non-remote/hybrid/unknown arrangements**
- [ ] **Step 2: Run pytest to verify failures**
- [ ] **Step 3: Implement tri-state remote filter and authoritative `posted_at` filter in `search_pipeline.py` and `company_board_registry.py`**
- [ ] **Step 4: Run pytest to verify passes**
- [ ] **Step 5: Commit**

---

### Task 3: Make Monitored-Store Revision Genuinely Cross-Process

**Files:**
- Modify: `src/project_files/company_board_registry.py:116-220, 720-726, 868-874, 940-950, 980-996`
- Modify: `src/project_files/search_pipeline.py:91-98`
- Test: `tests/test_cross_process_store_version.py`

**Interfaces:**
- SQLite table `registry_meta` (`key TEXT PRIMARY KEY`, `value INTEGER NOT NULL`)
- Transactional increment on insert, material update, and closing:
  `UPDATE registry_meta SET value = value + 1 WHERE key = 'store_version'`
- `CompanyBoardRegistry.get_monitored_store_version() -> int`: reads `value FROM registry_meta WHERE key = 'store_version'`

- [ ] **Step 1: Write failing cross-instance test with 2 `CompanyBoardRegistry` instances sharing SQLite DB and Serper disabled**
- [ ] **Step 2: Run pytest to verify failure**
- [ ] **Step 3: Implement SQLite durable revision counter and transactional updates in `CompanyBoardRegistry`**
- [ ] **Step 4: Run pytest to verify passes**
- [ ] **Step 5: Commit**

---

### Task 4: Improve Greenhouse Monitored-Job Descriptions

**Files:**
- Modify: `src/project_files/board_adapters.py:65-175`
- Test: `tests/test_greenhouse_descriptions.py`

**Interfaces:**
- `GreenhouseBoardAdapter.check_board`: Request `https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true`
- When `item.get("content")` is present and valid string: `raw_description=content`, `description_is_authentic=True`
- When absent, null, or malformed: `raw_description=None`, `description_is_authentic=False`

- [ ] **Step 1: Write failing tests for Greenhouse posting with authentic description content and one without**
- [ ] **Step 2: Run pytest to verify failures**
- [ ] **Step 3: Implement `content=true` query and authentic description handling in `GreenhouseBoardAdapter`**
- [ ] **Step 4: Run pytest to verify passes**
- [ ] **Step 5: Commit**

---

### Task 5: Correct Platform Migration Detection

**Files:**
- Modify: `frontend/src/lib/platformMigration.ts:1-70`
- Modify: `frontend/src/lib/__tests__/platformMigration.test.ts`
- Test: Vitest suite

**Interfaces:**
- Historical full platform sets: `HISTORICAL_16`, `HISTORICAL_18`, `HISTORICAL_19`, `CURRENT_21`
- Set comparison helper: checks exact set equality regardless of ordering
- Preserves custom 16-provider selection, preserves explicit empty selection `[]`, upgrades genuine historical sets to 21

- [ ] **Step 1: Write failing Vitest tests for custom 16-provider selection preservation and historical set upgrades**
- [ ] **Step 2: Run vitest to verify failure**
- [ ] **Step 3: Implement exact set comparison in `frontend/src/lib/platformMigration.ts`**
- [ ] **Step 4: Run vitest to verify passes**
- [ ] **Step 5: Commit**

---

### Task 6: Strengthen Nigerian Scraper Evidence and Tests

**Files:**
- Modify: `tests/fixtures/nigerian/jobberman_sample_detail.html`
- Modify: `tests/fixtures/nigerian/myjobmag_sample_detail.html`
- Modify: `tests/fixtures/nigerian/hotnigerianjobs_roundup_detail.html`
- Modify: `src/project_files/nigerian_scrapers.py:718-735`
- Modify: `tests/test_nigerian_enrichment_fixtures.py`

**Interfaces:**
- Accurately label fixture comments as representative/synthetic HTML
- Production method `MyJobMagScraper.clean_title(raw_title: str, company: str | None = None) -> tuple[str, str | None]`
- Tests verify: "Live at Home Carer" and "Architect at Sea" remain intact, real company suffix is removed, contextual application-link extraction ignores unrelated links in header/footer/nav/related-jobs, and HotNigerianJobs multi-role isolation is preserved

- [ ] **Step 1: Update fixture comments accurately**
- [ ] **Step 2: Add failing tests in `tests/test_nigerian_enrichment_fixtures.py` exercising real scraper title cleaning and contextual link rejection**
- [ ] **Step 3: Implement `clean_title` on `MyJobMagScraper` and use in both production parsing and tests**
- [ ] **Step 4: Run pytest to verify passes**
- [ ] **Step 5: Commit**

---

### Task 7: Address Monitoring Backlog Growth

**Files:**
- Modify: `src/config.py`
- Modify: `src/project_files/company_board_registry.py:465-495, 933-980`
- Modify: `src/project_files/board_monitor.py:105-135`
- Test: `tests/test_board_monitor.py`

**Interfaces:**
- `CompanyBoardRegistry.get_due_monitoring_boards`:
  `ORDER BY CASE WHEN next_scheduled_check IS NULL THEN 0 ELSE 1 END, next_scheduled_check ASC, polling_priority DESC`
- `CompanyBoardRegistry.get_monitoring_status`:
  Includes `due_boards`, `overdue_boards`, `oldest_overdue_seconds`, `hourly_check_capacity`, `sustainable_board_count`, `batch_size`, `interval_seconds`
- Scheduler test with more due boards than one batch verifying backlog drains fairly without starvation

- [ ] **Step 1: Write failing test in `tests/test_board_monitor.py` with 50 due boards and batch size 20, verifying multi-batch fair drainage**
- [ ] **Step 2: Run pytest to verify failure**
- [ ] **Step 3: Implement anti-starvation query order and backlog metrics in `company_board_registry.py` and `board_monitor.py`**
- [ ] **Step 4: Run pytest to verify passes**
- [ ] **Step 5: Commit**

---

### Task 8: End-to-End Verification & Full Test Suites

**Files:**
- Test: `tests/test_e2e_monitored_search_flow.py`
- Run: `pytest`
- Run: `npm --prefix frontend test`
- Run: `npm --prefix frontend run lint`
- Run: `npm --prefix frontend run build`
- Run: `npx playwright test`
- Run: `powershell -ExecutionPolicy Bypass -File .\scripts\verify.ps1`

- [ ] **Step 1: Implement full end-to-end integration test (independent monitor -> canonical extraction -> SQLite -> SearchOrchestrator without Serper -> deduplication -> cache invalidation -> filters)**
- [ ] **Step 2: Run pytest on all tests**
- [ ] **Step 3: Run frontend tests, lint, and build**
- [ ] **Step 4: Run Playwright e2e tests**
- [ ] **Step 5: Run `.\scripts\verify.ps1`**

---

### Task 9: Documentation and Delivery

**Files:**
- Modify: `docs/steps/32-global-ats-monitoring-registry.md`
- Inspect git status and git diff
- Update PR #36 description
- Commit and push to `step/32-global-ats-monitoring-registry`

- [ ] **Step 1: Update documentation removing stale in-memory revision and fixture capture claims**
- [ ] **Step 2: Inspect git diff for clean formatting and no stray files**
- [ ] **Step 3: Commit and push**
- [ ] **Step 4: Prepare final report**
