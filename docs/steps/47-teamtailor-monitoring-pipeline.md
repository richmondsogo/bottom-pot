# Step 47: Teamtailor Monitoring & Direct-Routing Pipeline

**Date:** 2026-11-17  
**Branch:** `step/47-teamtailor-monitoring-pipeline` (stacked on `step/46-teamtailor-monitoring-investigation` / PR #43)  
**Prerequisite Investigation:** Step 46 ([docs/steps/46-teamtailor-monitoring-investigation.md](46-teamtailor-monitoring-investigation.md))  
**Serper credits consumed:** `0` (`data/cache.sqlite` operational database untouched)

---

## 1. Scope & Architecture

Promotes **Teamtailor** from an enrichment-only ATS provider (Step 35) to a full independently monitorable and directly routable provider in `MONITORABLE_PROVIDERS` and `BOARD_ADAPTERS`, cleanly isolated from the concurrent operational database safety controls work (PR #44):

1. **Snapshot Completeness Contract (`BoardCheckResult.snapshot_complete` & `BoardMonitor`)**:
   - Added `snapshot_complete: bool = True` to `BoardCheckResult` in [`src/project_files/board_adapters.py`](../../src/project_files/board_adapters.py).
   - All existing providers (`GreenhouseBoardAdapter`, `LeverBoardAdapter`, `AshbyBoardAdapter`, `WorkableBoardAdapter`, `RecruiteeBoardAdapter`, `SmartRecruitersBoardAdapter`) preserve their `snapshot_complete=True` default behavior, and HTTP `304 Not Modified` retains its existing short-circuit semantics.
   - Updated `BoardMonitor.check_single_board` in [`src/project_files/board_monitor.py`](../../src/project_files/board_monitor.py) so `mark_missing_jobs_closed` / `reconcile_missing_jobs` only execute when `result.snapshot_complete` is `True`. Partial or truncated snapshots still persist newly observed/updated listings into `monitored_jobs` and `url_cache`, while suppressing missing-job closure.

2. **Teamtailor RSS Feed & Bounded HTML Fallback (`TeamtailorBoardAdapter`)**:
   - Implemented `parse_teamtailor_rss_feed(...)`, `fetch_teamtailor_html_fallback(...)`, `_parse_teamtailor_html_jobs_page(...)`, and `TeamtailorBoardAdapter` in [`src/project_files/board_adapters.py`](../../src/project_files/board_adapters.py).
   - **Primary Path (`GET https://{slug}.teamtailor.com/jobs.rss`)**:
     - Streams via shared `throttled_stream_bytes(..., follow_redirects=False)` with conditional `If-None-Match` and `If-Modified-Since` headers (`304 Not Modified` supported).
     - Defensively rejects `<!DOCTYPE`/`<!ENTITY` declarations, malformed XML, non-RSS roots, items lacking titles or safe HTTPS `/jobs/{id}` URLs, and duplicate numeric job IDs.
     - Parses HTML `<description>` to Markdown (`to_markdown`), `<pubDate>` RFC 2822 timestamps (added `email.utils.parsedate_to_datetime` fallback in `parse_datetime` in [`src/project_files/field_normalizer.py`](../../src/project_files/field_normalizer.py)), `<tt:locations>` multi-location tags, `<tt:department>`, `<tt:role>`, `<remoteStatus>` (`fully` -> `remote`, `hybrid` -> `hybrid`, `onsite` -> `in_person`; `none`/empty stays `None` per ADR 0001), regional hosts (`*.na.teamtailor.com`), and custom-domain `<link>` targets (e.g. `careers.gravita.com`).
   - **RSS 100-Item Cap & Bounded HTML Pagination Fallback**:
     - When `/jobs.rss` returns `< 100` items (`_TEAMTAILOR_RSS_CAP = 100`), RSS is complete (`snapshot_complete = True`) in a single GET.
     - When `/jobs.rss` returns `>= 100` items (Teamtailor RSS silently caps at `100` and ignores `?page=2`), `fetch_teamtailor_html_fallback(...)` paginates `https://{slug}.teamtailor.com/jobs?page=1..N` (`_TEAMTAILOR_HTML_MAX_PAGES = 20`, `_TEAMTAILOR_HTML_MAX_ITEMS = 500`), parsing `<turbo-frame id="jobs_list">` and `show_more?page=N` controls.
     - Repeated pages (`page_ids == prev_page_ids` / duplicate subsets), backward/self pagination loops (`next_page <= page` / already visited), non-200 errors, missing HTML frames, empty page 1, or hitting page/item caps immediately halt fallback with `snapshot_complete = False` and omit ETag/Last-Modified caching (`etag=None`, `last_modified=None`) so subsequent polls re-attempt a complete snapshot without falsely closing missing jobs.
     - HTML-only postings discovered past item #100 keep authentic title/URL/card metadata without fabricating descriptions (`description=None`). Pre-existing HTML-scraped `employment_type` / `salary` in `url_cache` are preserved via `CacheStore._merge_preserving_completeness`.

3. **URL Root Discovery, Registry Promotion & Direct Board Routing**:
   - Added `parse_teamtailor_board_root_url(...)` to [`src/project_files/ats_url_parser.py`](../../src/project_files/ats_url_parser.py) and wired it into `SearchOrchestrator._enrich_ats_item` ([`src/project_files/search_pipeline.py`](../../src/project_files/search_pipeline.py)).
   - Added `"teamtailor"` to `MONITORABLE_PROVIDERS` and promoted existing `'unsupported'` rows cleanly when re-synced via `register_candidate` in [`src/project_files/company_board_registry.py`](../../src/project_files/company_board_registry.py).
   - Added `probe_teamtailor_board` and wired `"teamtailor"` into `probe_direct_boards(...)` in [`src/project_files/direct_board_router.py`](../../src/project_files/direct_board_router.py).

---

## 2. Captured Real Fixtures (`tests/fixtures/real/teamtailor/`)

- `dotworld_rss.xml` (`139,311` bytes, `7` items from `dotworld.teamtailor.com/jobs.rss`)
- `gravita_rss.xml` (`116,823` bytes, `16` items from `gravita.teamtailor.com/jobs.rss` with custom domain `careers.gravita.com` links)
- `worksterjobs_jobs_p1.html` (`122,096` bytes, `20` items + `show_more?page=1&page=2` markup from `worksterjobs.teamtailor.com/jobs?page=1`)

---

## 3. Known Limitations & Non-Goals

- **HTML-only tail cards beyond item #100**: When a board exceeds `100` active jobs, items beyond the RSS 100-item window lack full RSS `<description>` and `<pubDate>` on `/jobs?page=N` cards (intentionally kept `None` per ADR 0001 rather than firing N detail GETs per poll).
- **Custom domains without known `.teamtailor.com` slug**: Arbitrary custom-domain career portals that do not expose their `.teamtailor.com` subdomain are out of scope for RSS polling.
- **Database safety PR isolation**: Permanent multi-layer operational DB safety controls (Layers 1–6, ADR 0030, CI) are intentionally isolated on PR #44 (`chore/operational-db-safety-controls`) to keep diff review focused.

---

## 4. Verification Results

Verified offline against captured real Teamtailor XML/HTML fixtures and mocked HTTP transports with isolated `tmp_path` SQLite databases (`0` Serper spend):

- `python -m pytest tests/test_teamtailor_monitoring.py -v`: **`18 passed, 0 failed`** (`13.50s`)
- Targeted Teamtailor, Monitor, Registry & Router suites (`test_teamtailor_monitoring.py`, `test_teamtailor_pipeline.py`, `test_board_monitor.py`, `test_company_board_registry.py`, `test_direct_board_router.py`): **`96 passed`** before adding test #18, **`18 passed`** after test #18
- Full Python Test Suite (`python -m pytest -q`): **`1062 passed, 1 skipped, 4 warnings in 179.84s`** (`test_existing_symlink_to_operational_target_rejected` skipped on unprivileged Windows due to `WinError 1314`)
- Work-Model Evaluation (`python scripts/eval_work_model.py`): exited **`0`** (`49` valid labelled rows, `0` regressions)
- Protected asset SHA-256 checksums (`data/cache.sqlite`, `data/cache.sqlite.bak-*`, preserved `.cache.sqlite.restore-staging-*`): identical before and after test runs.
