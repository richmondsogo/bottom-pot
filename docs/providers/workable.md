# Workable Provider Contract Reference

Adapter module: [`src/providers/workable.py`](../../src/providers/workable.py) (`WorkableBoardAdapter`)  
Shared matrix: [`docs/providers/inventory.md`](inventory.md)

## Endpoints & Transport

- **Board summary widget:** `GET https://apply.workable.com/api/v1/widget/accounts/{slug}`
- **Per-job detail hydration:** `GET https://apply.workable.com/api/v2/accounts/{slug}/jobs/{shortcode}` (bounded batch execution via [`src/providers/detail_hydration.py`](../../src/providers/detail_hydration.py))
- **HTTP transport:** Routed through [`fetch_provider_bytes`](../../src/providers/http.py) (`resilience_manager`, SSRF & DNS checks)
- **Conditional requests:** Sends `If-None-Match` and `If-Modified-Since`; short-circuits on `304` or unchanged board fingerprint when no detail retries are due

## Snapshot Completeness Rules

- Widget response must decode as UTF-8 JSON `dict` with `isinstance(data.get("jobs"), list)`.
- Rejects exact duplicate `(shortcode, content_hash)` entries and conflicting titles sharing the same `shortcode`.
- Legitimately allows distinct multi-city widget rows sharing a `shortcode` (which deduplicate cleanly into one canonical posting).
- Preserves cached or summary fallback listings when bounded `v2` detail requests encounter transient rate limits or failures.

## Identity Key & Fingerprinting

- **Canonical job ID:** `workable:{slug}:{shortcode}`
- **Fingerprint:** `_workable_widget_job_hash` (64-hex SHA-256 via [`canonical_content_hash`](../../src/providers/fingerprint.py)) + [`compute_board_fingerprint`](../../src/providers/fingerprint.py)
- **Cross-poll ID drift:** Checked via `detect_id_drift` in [`src/providers/contract.py`](../../src/providers/contract.py)

## Missing-Job Closure Rule

- Policy: `ReconciliationPolicy(missing_confirmation_threshold=1, require_complete_snapshot=True, close_on_empty_snapshot=True)`
- Missing confirmation threshold: `1` complete widget snapshot closes vanished postings (even when individual detail hydrations defer to backoff queues).

## Known Limits & Caps

- Widget summary lacks full job descriptions (`has_description_in_snapshot=False`), requiring `1+N` bounded detail hydration scheduled via `select_fair_detail_hydration_batch` and retry backoff (`TRANSIENT_RETRY_BACKOFF_SECONDS`, `DETAIL_404_RETRY_BACKOFF_SECONDS`).
- Both widget and detail payloads are capped at `settings.max_response_bytes` (`3 MiB` default).

## Fixture Provenance

- Conformance fixtures: [`tests/fixtures/real/workable/widget_verneek.json`](../../tests/fixtures/real/workable/widget_verneek.json), [`tests/fixtures/real/workable/job_verneek_3DBA754691.json`](../../tests/fixtures/real/workable/job_verneek_3DBA754691.json)
- Additional real widget and detail fixtures live under `tests/fixtures/real/workable/` and `tests/fixtures/real/step5{4,5,6}_employers/` (see [`THIRD_PARTY_DATA.md`](../../THIRD_PARTY_DATA.md)).
