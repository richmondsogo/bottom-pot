# Pinpoint HQ Provider Contract Reference

Adapter module: [`src/providers/pinpoint.py`](../../src/providers/pinpoint.py) (`PinpointBoardAdapter`)  
Shared matrix: [`docs/providers/inventory.md`](inventory.md)

## Endpoints & Transport

- **Board snapshot:** `GET https://{slug}.pinpointhq.com/postings.json`
- **Canonical apply/detail path:** `https://{slug}.pinpointhq.com/postings/{uuid}/applications/new`
- **HTTP transport:** Routed through [`fetch_provider_bytes`](../../src/providers/http.py) (`follow_redirects=False`, SSRF & DNS checks)
- **Conditional requests:** Sends `If-None-Match` and `If-Modified-Since`; returns `not_modified=True` when `status == 304 and board.etag`

## Snapshot Completeness Rules

- Response must decode as UTF-8 JSON `dict` containing `data` list validated by [`parse_pinpoint_postings_json`](../../src/providers/pinpoint.py).
- Enforces matching tenant host (`{slug}.pinpointhq.com`) and rejects duplicate job IDs within a snapshot (`snapshot_complete=False`).

## Identity Key & Fingerprinting

- **Canonical job ID:** `pinpointhq:{slug}:{uuid_or_numeric_id}` with deterministic alias tracking (`aliases`) when UUIDs map across legacy URL forms
- **Fingerprint:** `canonical_content_hash` + `compute_board_fingerprint`
- **Cross-poll ID drift:** Checked via `detect_id_drift` in [`src/providers/contract.py`](../../src/providers/contract.py)

## Missing-Job Closure Rule

- Policy: `ReconciliationPolicy(missing_confirmation_threshold=2, require_complete_snapshot=True, close_on_empty_snapshot=True)`
- Missing confirmation threshold: `2` consecutive complete snapshots confirm closure.

## Known Limits & Caps

- Dedicated timeout `settings.pinpoint_board_request_timeout_seconds` (`25.0s` default) accommodates slow `/postings.json` responses (~16–20s observed on large feeds).
- Byte limit: `settings.pinpoint_board_max_response_bytes` (`3 MiB` default, or explicit `max_response_bytes` override).
- Upstream rate limits: `120 req/1m` and `240 req/8m` (`docs/job-source-catalog.md`); `/postings.json` omits `posted_at`, relying on detail JSON-LD `datePosted` when enriched.

## Fixture Provenance

- Conformance fixtures: [`tests/fixtures/real/pinpointhq/bizimply_postings.json`](../../tests/fixtures/real/pinpointhq/bizimply_postings.json), [`tests/fixtures/real/pinpointhq/calligo_postings_empty.json`](../../tests/fixtures/real/pinpointhq/calligo_postings_empty.json)
- Census manifest and additional fixtures: [`tests/fixtures/real/pinpointhq/probe_census_manifest.json`](../../tests/fixtures/real/pinpointhq/probe_census_manifest.json) (see [`THIRD_PARTY_DATA.md`](../../THIRD_PARTY_DATA.md)).
