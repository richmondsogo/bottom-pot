# Ashby Provider Contract Reference

Adapter module: [`src/providers/ashby.py`](../../src/providers/ashby.py) (`AshbyBoardAdapter`)  
Shared matrix: [`docs/providers/inventory.md`](inventory.md)

## Endpoints & Transport

- **Board snapshot:** `GET https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true`
- **HTTP transport:** Routed through [`fetch_provider_bytes`](../../src/providers/http.py) (`resilience_manager`, `validate_provider_url`, SSRF & DNS checks)
- **Conditional requests:** Sends `If-None-Match` and `If-Modified-Since`; returns `not_modified=True` on `HTTP 304`

## Snapshot Completeness Rules

- Response must decode as UTF-8 JSON `dict` containing `isinstance(data.get("jobs"), list)`.
- Missing `"jobs"` key or invalid JSON fails closed (`FailureKind.PARSE_ERROR`, `snapshot_complete=False`).
- Rejects duplicate job IDs within one snapshot (`snapshot_complete=False`).
- Best-effort board identity enrichment catches explicit network/HTML parse errors while re-raising `(asyncio.CancelledError, SafetyError)`.

## Identity Key & Fingerprinting

- **Canonical job ID:** `ashby:{slug}:{id}` (via `ashby_payload_to_raw`)
- **Fingerprint:** `_ashby_job_content_hash` + `compute_board_fingerprint` (canonical 64-hex SHA-256, noise-invariant)
- **Cross-poll ID drift:** Checked via `detect_id_drift` in [`src/providers/contract.py`](../../src/providers/contract.py)

## Missing-Job Closure Rule

- Policy: `ReconciliationPolicy(missing_confirmation_threshold=1, require_complete_snapshot=True, close_on_empty_snapshot=True)`
- Missing confirmation threshold: `1` complete snapshot closes vanished postings.

## Known Limits & Caps

- Single-request JSON board payload capped at `settings.max_response_bytes` (`3 MiB` default, or explicit `max_response_bytes` override).
- Structured `secondaryLocations` lists on remote postings are normalized during eligibility extraction (`ADR 0001` separation between job geography and applicant eligibility).

## Fixture Provenance

- Conformance fixture: [`tests/fixtures/real/ashby/plaid_board_sample.json`](../../tests/fixtures/real/ashby/plaid_board_sample.json)
- Additional real captures live under `tests/fixtures/real/ashby/` and `tests/fixtures/real/step5{4,5,6}_employers/` (see [`THIRD_PARTY_DATA.md`](../../THIRD_PARTY_DATA.md)).
