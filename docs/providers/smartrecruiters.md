# SmartRecruiters Provider Contract Reference

Adapter module: [`src/providers/smartrecruiters.py`](../../src/providers/smartrecruiters.py) (`SmartRecruitersBoardAdapter`)  
Shared matrix: [`docs/providers/inventory.md`](inventory.md)

## Endpoints & Transport

- **Paginated listing feed:** `GET https://api.smartrecruiters.com/v1/companies/{slug}/postings?limit=100&offset={offset}`
- **Per-job detail JSON:** `ref` URL per posting fetched in bounded batches via [`src/providers/detail_hydration.py`](../../src/providers/detail_hydration.py)
- **Public posting URL (optional identity enrichment):** `https://jobs.smartrecruiters.com/{company}/{id}`
- **HTTP transport:** Routed through [`fetch_provider_bytes`](../../src/providers/http.py); response size capped at `settings.max_response_bytes` (`3 MiB` default per page/detail)
- **Conditional requests:** `supports_http_304=False` — omits `If-None-Match` on page 0 so edits on later pages are not masked; instead returns `not_modified=True` when the full-snapshot fingerprint is unchanged and no due detail retries exist

## Snapshot Completeness Rules

- Sequential offset pagination (`_SMARTREC_PAGE_SIZE = 100`) validated by [`validate_smartrecruiters_page`](../../src/providers/smartrecruiters.py) and `validate_offset_page`.
- Enforces `totalFound` page-count consistency, matching tenant company slug, and zero duplicate job IDs across all pages (`snapshot_complete=False` / fail closed on pagination mismatch).

## Identity Key & Fingerprinting

- **Canonical job ID:** `smartrecruiters:{slug}:{id}`
- **Fingerprint:** `_smartrecruiters_listing_item_hash` (normalizes `/v1/companies/<slug>/` casing inside `ref` URL) + `compute_board_fingerprint`
- **Cross-poll ID drift:** Checked via `detect_id_drift` in [`src/providers/contract.py`](../../src/providers/contract.py)

## Missing-Job Closure Rule

- Policy: `ReconciliationPolicy(missing_confirmation_threshold=2, require_complete_snapshot=True, close_on_empty_snapshot=True)`
- Missing confirmation threshold: `2` consecutive complete paginated snapshots confirm closure.

## Known Limits & Caps

- List items omit descriptions (`has_description_in_snapshot=False`), requiring bounded `ref` detail hydration (`detail_hydration.py`).
- `api.smartrecruiters.com/robots.txt` disallows crawling for `User-agent: *`, so zero SmartRecruiters boards are included in `VERIFIED_EMPLOYER_BOARDS` (only existing legacy/fixture coverage remains monitored).

## Fixture Provenance

- Conformance fixtures: [`tests/fixtures/real/smartrecruiters/nearmap_postings.json`](../../tests/fixtures/real/smartrecruiters/nearmap_postings.json), [`tests/fixtures/real/smartrecruiters/nearmap_744000161158698_detail.json`](../../tests/fixtures/real/smartrecruiters/nearmap_744000161158698_detail.json), [`tests/fixtures/real/smartrecruiters/scalable_postings_p0.json`](../../tests/fixtures/real/smartrecruiters/scalable_postings_p0.json)
- Additional real fixtures live under `tests/fixtures/real/smartrecruiters/` (see [`THIRD_PARTY_DATA.md`](../../THIRD_PARTY_DATA.md)).
