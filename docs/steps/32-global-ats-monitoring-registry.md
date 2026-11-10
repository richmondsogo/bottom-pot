# Step 32: Global ATS Discovery, Independent Monitoring & Extraction Reliability

## Overview
- **Goal**:
  1. Reconcile frontend and backend platform inventories across all 18 configured ATS platforms and 3 active Nigerian job boards (21 platforms total).
  2. Implement an automatically growing SQLite company-board registry (`company_boards` table) that indexes verified public boards, rejects placeholders and stopwords, and deduplicates records.
  3. Build an independent, pluggable ATS company-board monitoring engine with adapters for Greenhouse, Lever, and Ashby, supporting conditional HTTP headers (ETag, If-Modified-Since), content fingerprinting, exponential backoff, and a standalone CLI runner (`python -m src.project_files.board_monitor`).
  4. Harden Nigerian scrapers: clean title suffixes, implement bounded detail enrichment for MyJobMag, and extract direct external ATS application links from Jobberman, MyJobMag, and HotNigerianJobs to automatically feed candidate boards into the registry.
  5. Decouple Serper by making `serper_api_key: str = ""` optional in `src/config.py`, gracefully bypassing live Serper calls when unconfigured or budget-exhausted while preserving direct board probes and Nigerian scrapers.
  6. Fix test date drift in golden replay tests and provide comprehensive regression tests.
- **PR**: Pending
- **Branch**: `step/32-global-ats-monitoring-registry`
- **First Commit SHA**: `5e15758`
- **Last Commit SHA**: `9e85f75`
- **Merge Commit SHA**: Pending

---

## Changes Implemented

### 1. Platform Inventory Reconciliation (21 Authoritative Platforms)
- Reconciled `frontend/src/lib/constants.ts` `ALL_PLATFORMS` to match the backend registry:
  - 18 ATS platforms: `greenhouse`, `lever`, `ashby`, `workable`, `bamboohr`, `jobvite`, `smartrecruiters`, `icims`, `personio`, `teamtailor`, `recruitee`, `breezy`, `workday`, `taleo`, `jobadder`, `jazzhr`, `avature`, `successfactors`.
  - 3 Nigerian job boards: `jobberman`, `myjobmag`, `hotnigerianjobs`.
  - Removed unsupported obsolete chips (`polywork`, `rippling`, `pinpointhq`).
  - Added missing backend platforms (`icims`, `jobadder`, `jazzhr`, `avature`, `successfactors`).
- Sanitized `frontend/src/App.tsx` state initialization so stale `localStorage` entries containing retired slugs are pruned on startup.
- Added `tests/test_platform_reconciliation.py` verifying that all 18 ATS platforms and 3 Nigerian platforms fan out concurrently by default, and that deselecting any platform does not drop unrelated platforms.

### 2. URL Parser & Tenant Slug Extraction Hardening (`ats_url_parser.py`)
- Added `is_valid_board_slug(ats, slug)` with `_GENERIC_SLUG_STOPWORDS` to reject generic strings (`"personio"`, `"apply"`, `"jobs"`, `"icims"`, `"career"`).
- Replaced hardcoded fallback strings with genuine tenant slug extraction for `personio`, `icims`, `breezy`, `jazzhr`, `jobadder`, and `successfactors`.
- Hardened regex patterns:
  - `_WORKDAY`: Support multi-segment paths before and after `/job/`.
  - `_BREEZY`: Support both company subdomains (`{company}.breezy.hr/p/{id}`) and canonical apply URLs (`apply.breezy.hr/p/{id}/{slug}`).
  - `_JAZZHR`: Support company subdomains on `applytojob.com` and `/app/share/` URLs.

### 3. Automatically Growing SQLite Company-Board Registry (`company_board_registry.py`)
- Created SQLite `company_boards` table with schema:
  - `(ats_provider, board_token)` unique index preventing duplicate company rows.
  - Verification lifecycle: `candidate` -> `verified` -> `unsupported` / `rejected`.
  - Monitoring metrics: `last_successful_check`, `next_scheduled_check`, `failure_count`, `active_job_count`, `etag`, `last_modified`, `content_fingerprint`.
- Provided thread-safe methods: `register_candidate`, `get_board`, `get_due_boards`, `record_check_success`, `record_check_failure`, `record_not_modified`.
- Added test suite: `tests/test_company_board_registry.py` (6 unit tests).

### 4. Independent ATS Monitoring Engine (`board_adapters.py`, `board_monitor.py`)
- Implemented `GreenhouseBoardAdapter`, `LeverBoardAdapter`, and `AshbyBoardAdapter` utilizing public JSON endpoints.
- Incorporated conditional HTTP caching:
  - Sends `If-None-Match` (ETag) and `If-Modified-Since` (Last-Modified).
  - Handles `304 Not Modified` without reparsing or re-extracting jobs.
  - Computes SHA256 content fingerprints for payload change detection.
- Bounded concurrency with `asyncio.Semaphore(settings.monitoring_concurrency_limit)`.
- Implemented exponential backoff on consecutive check failures (`30m` -> `1h` -> `2h` -> ... up to `48h`).
- Added standalone CLI runner: `python -m src.project_files.board_monitor [--run-once | --daemon]` with PID file locking at `data/monitor.lock`.
- Added test suite: `tests/test_board_monitor.py` (4 unit tests).

### 5. Nigerian Scraper Reliability & ATS Link Discovery (`nigerian_scrapers.py`)
- Cleaned title suffixes: stripped `" at <Company>"` and `" @ <Company>"` in `MyJobMagScraper`.
- Implemented bounded detail enrichment in `MyJobMagScraper` (`Semaphore(3)`, max 10 postings per search, graceful exception handling).
- Extracted direct external ATS links:
  - `JobbermanScraper._enrich_detail`: scans detail HTML for ATS links, updates `apply_url`, and calls `company_board_registry.register_candidate`.
  - `MyJobMagScraper._enrich_detail`: scans detail HTML for external ATS links and registers candidate boards.
  - `HotNigerianJobsScraper`: scans application methods and body HTML for ATS links and registers candidate boards.
- Added integration test suite: `tests/test_board_discovery_and_pipeline.py` (4 integration tests).

### 6. Pipeline Auto-Registration & Serper Decoupling (`search_pipeline.py`, `config.py`)
- Made `serper_api_key: str = ""` optional in `src/config.py`.
- Gracefully bypass live Serper queries when `serper_api_key` is empty or daily budget is exhausted; direct board probes and Nigerian scrapers proceed uninterrupted.
- In `_enrich_ats_item` and `_search_direct_boards`, automatically register discovered and verified company boards into `company_board_registry`.

---

## Verification Results

1. **Python Unit & Integration Tests**:
   - `pytest`: **593 passed**, 4 warnings in 61.07s (100% pass rate).
2. **Frontend Vitest Suite**:
   - `vitest`: **13 test files passed**, **94 tests passed** in 8.11s.
3. **Frontend Lint & Build**:
   - `oxlint`: 0 errors.
   - `tsc -b && vite build`: built client environment cleanly in 3.18s.
4. **Official Build Protocol Suite**:
   - `.\scripts\verify.ps1 -SkipE2E`: **7 passed, 0 failed, 1 skipped** (of 8 checks).
