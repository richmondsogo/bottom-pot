# Step 49: Personio Monitoring & Direct-Routing Pipeline

**Date:** 2026-11-17  
**Branch:** `step/49-personio-monitoring-pipeline` (stacked on `step/48-personio-monitoring-investigation`)  
**Prerequisite Investigation:** Step 48 ([docs/steps/48-personio-monitoring-investigation.md](48-personio-monitoring-investigation.md))  
**Serper credits consumed:** `0` (`data/cache.sqlite` operational database untouched)

---

## 1. Scope & Architecture

Promotes **Personio** from an HTML/regex-only ATS provider to a full independently monitorable and directly routable provider in `MONITORABLE_PROVIDERS`, `BOARD_ADAPTERS`, and `probe_direct_boards`:

1. **Strict XML Parsing & Safety (`parse_personio_xml_feed` in [`src/project_files/board_adapters.py`](../../src/project_files/board_adapters.py))**:
   - Streams `GET https://{slug}.jobs.personio.com/xml?language=en` via shared `throttled_stream_bytes(..., follow_redirects=False)` up to `settings.max_response_bytes`.
   - Rejects empty payloads, full-payload `<!DOCTYPE` / `<!ENTITY` declarations (`_XML_UNSAFE_DECL_RE`), invalid UTF-8 / malformed XML, non-`<workzag-jobs>` roots, blank/non-numeric `<id>`, missing `<name>`, and duplicate `<id>` entries.
   - Recognizes valid empty `<workzag-jobs></workzag-jobs>` snapshots as complete (`snapshot_complete=True`).

2. **Bilingual XML Merge & Blind-Spot-Free Conditional ETag Design (`PersonioBoardAdapter`)**:
   - Primary endpoint: `GET https://{slug}.jobs.personio.com/xml?language=en`.
   - When every `<position>` has non-empty `<jobDescriptions>` (or the feed is a valid empty `<workzag-jobs>`), no second request is made (`fb=0`).
   - When one or more positions lack `<jobDescriptions>` in `?language=en`, performs a bounded fallback `GET https://{slug}.jobs.personio.com/xml`, validates identical position ID sets between feeds, preserves English titles and existing English descriptions, fills empty descriptions from default `/xml`, and leaves positions absent in both feeds as sparse (`description=None`).
   - **Composite Conditional ETag State (`p1:{"en":..., "def":..., "fb":0|1}` stored in `company_boards.etag`)**:
     - When `fb=0`, `304 Not Modified` on `?language=en` short-circuits immediately (`not_modified=True, snapshot_complete=True`).
     - When `fb=1`, a `304` on `?language=en` triggers conditional validation of default `/xml` (`If-None-Match: def_etag`):
       - `EN=304` and `Default=304` -> short-circuits safely (`not_modified=True`).
       - `EN=304` and `Default=200` -> refetches `?language=en` unconditionally, merges the updated fallback descriptions, and returns full updated `listings`.
       - `EN=200` and `Default=304` -> refetches default `/xml` unconditionally to hydrate fallback descriptions alongside the updated English snapshot.
       - Any mismatch in position IDs or failed/truncated/invalid response on either feed fails closed (`success=False, snapshot_complete=False`), ensuring `BoardMonitor` never closes active jobs from partial snapshots (`missing_confirmation_threshold=2`).

3. **Field Normalization (`_personio_position_to_listing`)**:
   - Canonical job ID: `personio:{lowercase_slug}:{numeric_position_id}` and canonical URL `https://{lowercase_slug}.jobs.personio.com/job/{id}`.
   - `<subcompany>` preferred over `board.company_name` / `humanize_slug(slug)`.
   - `<office>` + `<additionalOffices>` deduplicated into compact `location` and preserved in `raw_fields["raw_location_preserved"]`.
   - `<employmentType>` (`permanent`, `fixed_term`, `freelance`, `intern`, `working_student`) + `<schedule>` (`full-time`, `part-time`, `full-or-part-time`) normalized deterministically per ADR 0001 (`part-time` overrides `permanent` -> `part_time`; `fixed_term`/`freelance` -> `contract`; `full-or-part-time` remains `None` rather than guessing `full_time`).
   - `<salaryInformation>` (`min`, `max`, `currencyCode`, `type`) preserved in `raw_fields` and mapped cleanly via `baseSalary` only when positive bounds exist (`0.00` rejected per ADR 0001).
   - `<createdAt>` ISO-8601 UTC timestamps preserved in `posted_at`; `work_model` resolved strictly through `JobExtractionService` / `resolve_work_model` per ADR 0001/0002 (unstated remains `None`; `#LI-*` extracted before stripping).

4. **`.com`/`.de` Normalization, Registry Promotion, Discovery & Direct Routing**:
   - Added `parse_personio_board_root_url(url)` in [`src/project_files/ats_url_parser.py`](../../src/project_files/ats_url_parser.py) accepting `https://{slug}.jobs.personio.{com,de}/?` and wired into `SearchOrchestrator._enrich_ats_item` ([`src/project_files/search_pipeline.py`](../../src/project_files/search_pipeline.py)).
   - Added `"personio"` to `MONITORABLE_PROVIDERS` and standardized `build_canonical_board_url("personio", token)` to `https://{token}.jobs.personio.com` in [`src/project_files/company_board_registry.py`](../../src/project_files/company_board_registry.py); pre-existing `'unsupported'` `montana` rows auto-promote to `'supported'` on `_ensure_db()`.
   - Canonicalized `.jobs.personio.de` posting URLs to `.jobs.personio.com` in [`src/project_files/url_normalizer.py`](../../src/project_files/url_normalizer.py) so `.com` and `.de` collapse cleanly without duplicate cache/board/job rows.
   - Widened Personio HTML metadata extraction in [`src/project_files/ats_page_enricher.py`](../../src/project_files/ats_page_enricher.py) to support both `jobs.personio.com` and `jobs.personio.de`.
   - Added `probe_personio_board` and wired `"personio"` into `probe_direct_boards` in [`src/project_files/direct_board_router.py`](../../src/project_files/direct_board_router.py).

---

## 2. Captured Real Fixtures (`tests/fixtures/real/personio/`)

Captured sequentially via unauthenticated bounded GET probes on `2026-11-17T15:25Z` (`0` Serper credits, provenance recorded in [`metadata.json`](../../tests/fixtures/real/personio/metadata.json)):

- `montana_xml_default.xml` (`116,649` bytes, `20` items, `0` empty descriptions; German `<jobDescriptions>`, `subcompany`, `additionalOffices`, structured `salaryInformation`)
- `montana_xml_en.xml` (`18,815` bytes, `20` items, `20` empty descriptions — triggers bilingual fallback)
- `saeki_xml_default.xml` (`12,846` bytes, `9` items, `8` empty descriptions)
- `saeki_xml_en.xml` (`66,447` bytes, `9` items, `0` empty descriptions — EN-only single GET)
- `enopai_xml_default.xml` (`6,432` bytes, `4` items, `3` empty descriptions)
- `enopai_xml_en.xml` (`40,984` bytes, `4` items, `1` empty description — mixed EN + DE merge)
- `traviangames_xml_empty.xml` (`72` bytes, `0` items — valid empty `<workzag-jobs>`)

---

## 3. Verification Results

All tests execute strictly offline against captured real fixtures and mocked HTTP transports (`MockTransport`) using isolated `tmp_path` SQLite databases:

- `pytest tests/test_personio_monitoring.py -v`: **`55 passed, 0 failed`**
- Combined targeted suites (`test_personio_monitoring.py`, `test_teamtailor_monitoring.py`, `test_board_monitor.py`, `test_company_board_registry.py`, `test_direct_board_router.py`, `test_ats_url_parser.py`, `test_url_normalizer.py`): **`211 passed, 0 failed`**
- `python scripts/check_db_safety.py`: **`PASSED` (0 unsafe patterns)**
- `.\scripts\verify.ps1`: **`9 passed, 0 failed, 0 skipped (of 9 checks)`**
- Protected `data/` SQLite database, WAL/SHM sidecars, backups, and preserved staging artifacts verified byte-for-byte identical before and after testing (`data/cache.sqlite`: `14,016,512` bytes, SHA-256 `a7c88bb24d383813213342ea1a0990f0c7bf62b4c1308647fc18f834be028638`).
