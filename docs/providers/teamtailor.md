# Teamtailor Provider Contract Reference

Adapter module: [`src/providers/teamtailor.py`](../../src/providers/teamtailor.py) (`TeamtailorBoardAdapter`)  
Shared matrix: [`docs/providers/inventory.md`](inventory.md)

## Endpoints & Transport

- **Primary board feed:** `GET https://{slug}.teamtailor.com/jobs.rss`
- **Overflow HTML pagination fallback:** `GET https://{host}/jobs?page={page}` (triggered when RSS returns `_TEAMTAILOR_RSS_CAP = 100` items)
- **HTTP transport:** Routed through [`fetch_provider_bytes`](../../src/providers/http.py) (`follow_redirects=False`, SSRF & DNS checks); capped at `settings.max_response_bytes` (`3 MiB` default per response)
- **Conditional requests:** Sends `If-None-Match` and `If-Modified-Since` on RSS; returns `not_modified=True` on `HTTP 304` when the prior snapshot was complete

## Snapshot Completeness Rules

- Rejects unsafe XML declarations (`<!DOCTYPE`, `<!ENTITY>`), validates item links/tenant host/numeric job IDs, and rejects duplicate IDs.
- HTML fallback uses `HtmlPaginationTracker` (`_TEAMTAILOR_HTML_MAX_PAGES = 20`, `_TEAMTAILOR_HTML_MAX_ITEMS = 500`, next-page cycle detection).
- If RSS succeeds (`100` items) and HTML fallback fails partway, returns `success=True, snapshot_complete=False` with `incomplete_reason` so those 100 fresh postings stay updated while closure reconciliation is strictly skipped.

## Identity Key & Fingerprinting

- **Canonical job ID:** `teamtailor:{slug}:{numeric_job_id}` (extracted from `/jobs/{id}` URLs)
- **Fingerprint:** `canonical_content_hash` + `compute_board_fingerprint` across normalized RSS/HTML items
- **Cross-poll ID drift:** Checked via `detect_id_drift` in [`src/providers/contract.py`](../../src/providers/contract.py)

## Missing-Job Closure Rule

- Policy: `ReconciliationPolicy(missing_confirmation_threshold=2, require_complete_snapshot=True, close_on_empty_snapshot=True)`
- Missing confirmation threshold: `2` consecutive **complete** snapshots confirm missing-job closure.

## Known Limits & Caps

- Constants enforced in [`src/providers/teamtailor.py`](../../src/providers/teamtailor.py): `_TEAMTAILOR_RSS_CAP = 100`, `_TEAMTAILOR_HTML_MAX_PAGES = 20`, `_TEAMTAILOR_HTML_MAX_ITEMS = 500`.
- Preserves multi-location `<tt:location>` labels alongside country-aware eligibility evaluation.

## Fixture Provenance

- Conformance fixture: [`tests/fixtures/real/teamtailor/gravita_rss.xml`](../../tests/fixtures/real/teamtailor/gravita_rss.xml)
- Additional real RSS/HTML captures live under `tests/fixtures/real/teamtailor/` and `tests/fixtures/real/step5{4,6}_employers/` (see [`THIRD_PARTY_DATA.md`](../../THIRD_PARTY_DATA.md) regarding `dotworld_rss.xml`).
