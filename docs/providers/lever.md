# Lever Provider Contract Reference

Adapter module: [`src/providers/lever.py`](../../src/providers/lever.py) (`LeverBoardAdapter`)  
Shared matrix: [`docs/providers/inventory.md`](inventory.md)

## Endpoints & Transport

- **Board snapshot:** `GET https://api.lever.co/v0/postings/{slug}?mode=json`
- **HTTP transport:** Routed through [`fetch_provider_bytes`](../../src/providers/http.py) (`resilience_manager`, `validate_provider_url`, SSRF & DNS checks)
- **Conditional requests:** Sends `If-None-Match` and `If-Modified-Since`; returns `not_modified=True` on `HTTP 304`

## Snapshot Completeness Rules

- Response must decode as UTF-8 top-level JSON `list` of `dict` posting entries.
- Non-list roots fail closed (`FailureKind.PARSE_ERROR`, `snapshot_complete=False`).
- Rejects duplicate job IDs within one snapshot (`snapshot_complete=False`).
- Optional board identity enrichment catches transport/parse errors while strictly re-raising `(asyncio.CancelledError, SafetyError)`.

## Identity Key & Fingerprinting

- **Canonical job ID:** `lever:{slug}:{id}` (via `lever_payload_to_raw`)
- **Fingerprint:** Canonical 64-hex SHA-256 via [`canonical_content_hash`](../../src/providers/fingerprint.py) and [`compute_board_fingerprint`](../../src/providers/fingerprint.py)
- **Cross-poll ID drift:** Checked via `detect_id_drift` in [`src/providers/contract.py`](../../src/providers/contract.py)

## Missing-Job Closure Rule

- Policy: `ReconciliationPolicy(missing_confirmation_threshold=1, require_complete_snapshot=True, close_on_empty_snapshot=True)`
- Missing confirmation threshold: `1` complete snapshot closes vanished postings.

## Known Limits & Caps

- Single-request JSON array capped at `settings.max_response_bytes` (`3 MiB` default, or explicit `max_response_bytes` override).
- Long-lived evergreen postings (for example, `lever:metabase` catalog captures) retain old `createdAt` dates without explicit expiration markers; surfaced transparently by the freshness model (`ADR 0034`).

## Fixture Provenance

- Conformance fixtures: [`tests/fixtures/real/lever/api_1cb2b7f2.json`](../../tests/fixtures/real/lever/api_1cb2b7f2.json), [`tests/fixtures/real/lever/api_624ad7e8.json`](../../tests/fixtures/real/lever/api_624ad7e8.json)
- Additional real API and HTML captures live under `tests/fixtures/real/lever/` and `tests/fixtures/real/step5{4,5}_employers/` (see [`THIRD_PARTY_DATA.md`](../../THIRD_PARTY_DATA.md)).
