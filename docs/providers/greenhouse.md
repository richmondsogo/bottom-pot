# Greenhouse Provider Contract Reference

Adapter module: [`src/providers/greenhouse.py`](../../src/providers/greenhouse.py) (`GreenhouseBoardAdapter`)  
Shared matrix: [`docs/providers/inventory.md`](inventory.md)

## Endpoints & Transport

- **Board snapshot:** `GET https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true`
- **Individual detail lookup:** `GET https://boards-api.greenhouse.io/v1/boards/{slug}/jobs/{job_id}?pay_transparency=true` (used by `get_job_detail` for authoritative `first_published`)
- **HTTP transport:** Routed through [`fetch_provider_bytes`](../../src/providers/http.py) (`resilience_manager`, `validate_provider_url`, SSRF & DNS checks)
- **Conditional requests:** Sends `If-None-Match` and `If-Modified-Since`; returns `not_modified=True` on `HTTP 304`

## Snapshot Completeness Rules

- Response must decode as UTF-8 JSON `dict` containing `isinstance(data.get("jobs"), list)`.
- Missing `"jobs"` key or non-list root fails closed (`FailureKind.PARSE_ERROR`, `snapshot_complete=False`).
- Rejects duplicate job IDs within a single snapshot (`snapshot_complete=False`).

## Identity Key & Fingerprinting

- **Canonical job ID:** `greenhouse:{slug}:{id}` (via `greenhouse_payload_to_raw`)
- **Fingerprint:** Canonical 64-hex SHA-256 over meaningful posting fields via [`canonical_content_hash`](../../src/providers/fingerprint.py) and [`compute_board_fingerprint`](../../src/providers/fingerprint.py) (whitespace- and key-order-invariant)
- **Cross-poll ID drift:** Inspected centrally via `detect_id_drift` in [`src/providers/contract.py`](../../src/providers/contract.py)

## Missing-Job Closure Rule

- Policy: `ReconciliationPolicy(missing_confirmation_threshold=1, require_complete_snapshot=True, close_on_empty_snapshot=True)`
- Missing confirmation threshold: `1` complete snapshot confirms missing jobs for closure; incomplete snapshots skip reconciliation.

## Known Limits & Caps

- Single-request JSON board payload capped at `settings.max_response_bytes` (`3 MiB` default, or explicit `max_response_bytes` override).
- Uses `first_published` for posting recency rather than mutable `updated_at` timestamps so routine metadata edits do not mask stale roles.

## Fixture Provenance

- Conformance fixture: [`tests/fixtures/real/step54_employers/greenhouse_wikimedia.json`](../../tests/fixtures/real/step54_employers/greenhouse_wikimedia.json)
- Additional real captures live under `tests/fixtures/real/greenhouse/` and `tests/fixtures/real/step5{4,5,6}_employers/` (see [`THIRD_PARTY_DATA.md`](../../THIRD_PARTY_DATA.md)).
