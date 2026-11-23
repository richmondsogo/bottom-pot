# Recruitee Provider Contract Reference

Adapter module: [`src/providers/recruitee.py`](../../src/providers/recruitee.py) (`RecruiteeBoardAdapter`)  
Shared matrix: [`docs/providers/inventory.md`](inventory.md)

## Endpoints & Transport

- **Board snapshot:** `GET https://{slug}.recruitee.com/api/offers/`
- **HTTP transport:** Routed through [`fetch_provider_bytes`](../../src/providers/http.py) (`follow_redirects=False`, gzip conditional headers, `validate_provider_url`, SSRF & DNS checks)
- **Conditional requests:** Sends `If-None-Match` and `If-Modified-Since`; returns `not_modified=True` on `HTTP 304`

## Snapshot Completeness Rules

- Response must decode as UTF-8 JSON `dict` containing an `offers` list validated by [`validate_recruitee_offers_snapshot`](../../src/providers/recruitee.py).
- Filters to active published statuses (`_RECRUITEE_ACTIVE_STATUSES = frozenset({"published"})`) and rejects duplicate active offer IDs (`snapshot_complete=False`).
- Optional board identity enrichment catches transport/HTML errors explicitly while re-raising `(asyncio.CancelledError, SafetyError)`.

## Identity Key & Fingerprinting

- **Canonical job ID:** `recruitee:{slug}:{id_or_slug}`
- **Fingerprint:** `_recruitee_job_content_hash` (`canonical_content_hash` over full offer payload) + `compute_board_fingerprint`
- **Cross-poll ID drift:** Checked via `detect_id_drift` in [`src/providers/contract.py`](../../src/providers/contract.py)

## Missing-Job Closure Rule

- Policy: `ReconciliationPolicy(missing_confirmation_threshold=1, require_complete_snapshot=True, close_on_empty_snapshot=True)`
- Missing confirmation threshold: `1` complete snapshot closes vanished postings.

## Known Limits & Caps

- Real Recruitee boards return full inline HTML descriptions in one JSON payload (~6 MiB on large tenants), so default response limit is `settings.recruitee_board_max_response_bytes` (`16 MiB`) while respecting explicit smaller `max_response_bytes` overrides.

## Fixture Provenance

- Conformance fixture: [`tests/fixtures/real/recruitee/dransay_offers.json`](../../tests/fixtures/real/recruitee/dransay_offers.json)
- Additional real captures live under `tests/fixtures/real/recruitee/` and `tests/fixtures/real/step54_employers/` (see [`THIRD_PARTY_DATA.md`](../../THIRD_PARTY_DATA.md)).
