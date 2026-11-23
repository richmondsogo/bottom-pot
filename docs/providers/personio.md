# Personio Provider Contract Reference

Adapter module: [`src/providers/personio.py`](../../src/providers/personio.py) (`PersonioBoardAdapter`)  
Shared matrix: [`docs/providers/inventory.md`](inventory.md)

## Endpoints & Transport

- **Primary & localized XML feeds:** `GET https://{slug}.jobs.personio.com/xml` and `GET https://{slug}.jobs.personio.com/xml?language=en`
- **HTTP transport:** Routed through [`fetch_provider_bytes`](../../src/providers/http.py) (`follow_redirects=False`, SSRF & DNS checks); capped at `settings.max_response_bytes` (`3 MiB` default per feed)
- **Conditional requests:** Encodes bilingual state as `p1:` JSON conditional ETags (`_encode_personio_etag` / `_decode_personio_etag`), verifying both feeds on `HTTP 304` before returning `not_modified=True`

## Snapshot Completeness Rules

- Rejects unsafe XML declarations (`<!DOCTYPE`, `<!ENTITY>`), validates strictly numeric IDs (`^\d+$`), and rejects duplicate position IDs inside `parse_personio_xml_feed`.
- Merges default and `?language=en` feeds deterministically via `_merge_personio_feeds`; fails closed if either feed errors or produces malformed XML (`snapshot_complete=False`).

## Identity Key & Fingerprinting

- **Canonical job ID:** `personio:{slug}:{numeric_id}`
- **Fingerprint:** `canonical_content_hash` + `compute_board_fingerprint`
- **Cross-poll ID drift:** Checked via `detect_id_drift` in [`src/providers/contract.py`](../../src/providers/contract.py)

## Missing-Job Closure Rule

- Policy: `ReconciliationPolicy(missing_confirmation_threshold=2, require_complete_snapshot=True, close_on_empty_snapshot=True)`
- Missing confirmation threshold: `2` consecutive complete merged snapshots confirm missing-job closure.

## Known Limits & Caps

- Requires dual XML fetch when bilingual language fallback applies (`/xml` + `?language=en`), bounded by `settings.max_response_bytes` (`3 MiB`) per feed.
- Regional subdomain hosts (e.g., `jobs.personio.de` / `.com`) are excluded from non-ATS employer domain extraction (`ADR 0031`).

## Fixture Provenance

- Conformance fixtures: [`tests/fixtures/real/personio/saeki_xml_en.xml`](../../tests/fixtures/real/personio/saeki_xml_en.xml), [`tests/fixtures/real/personio/saeki_xml_default.xml`](../../tests/fixtures/real/personio/saeki_xml_default.xml)
- Additional real Personio XML captures live under `tests/fixtures/real/personio/` (see [`THIRD_PARTY_DATA.md`](../../THIRD_PARTY_DATA.md)).
