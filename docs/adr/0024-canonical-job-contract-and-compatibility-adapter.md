# ADR 0024: Canonical Job Contract and Compatibility Adapter Architecture

## Status

Proposed

## Context

Bottom Pot currently maintains two parallel and disconnected job representations in `src/project_files/models.py`:

1. `JobListing` (lines 66–154): The operational model used throughout search orchestration (`search_pipeline.py`), ATS API clients (`ats_api_client.py`), generic page enrichment (`ats_page_enricher.py`), Nigerian scrapers (`nigerian_scrapers.py`), SQLite URL caching (`cache_store.py`), and FastAPI SSE streaming (`src/api/main.py`). It contains flat scalar fields, loose types (`salary: JobSalary | str | None`), heuristic confidence penalties, and UI-specific properties (`freshness_label`).
2. `CanonicalJob` (lines 265–281): A contract model introducing field-level evidence (`FieldEvidence`), validation statuses (`FieldValidation`), and confidence scoring (`FieldConfidence`). It is referenced solely in `tests/test_contracts_and_observability.py` and is completely disconnected from search execution, caching, and serialization.

Simultaneously, existing external consumers (the CLI `main.py`, FastAPI SSE streaming endpoints, and the React frontend) rely on `JobListing` field shapes and SSE event schemas (`ResultsBatch`, `DoneEvent`). Modifying or replacing `JobListing` in-place risks breaking SSE client deserialization, frontend table rendering, and existing CLI automation.

## Decision

We will establish a single authoritative internal domain model, `CanonicalJob`, and treat `JobListing` exclusively as an external serialization and backward-compatibility adapter.

Specifically:
- All upstream extraction, normalization, deduplication, and validation stages will produce and operate on `CanonicalJob`.
- `CanonicalJob` will hold strictly validated fields, explicit provenance (`field_evidence`), per-field validation logs (`field_validations`), and field-level confidence scores (`field_confidence`).
- A dedicated adapter (`CanonicalJobAdapter.to_job_listing(canonical: CanonicalJob) -> JobListing`) will translate the canonical model into `JobListing` at system boundaries:
  - When streaming SSE batches (`ResultsBatch`) in `src/api/main.py`.
  - When exporting or returning data to legacy consumers.
- An inverted adapter (`CanonicalJobAdapter.from_job_listing(listing: JobListing) -> CanonicalJob`) will deserialize legacy cache entries or fixtures when needed.
- `SearchResponse` (currently dead scaffolding at `models.py:155`) will be formally deprecated or updated to represent non-streaming batched searches.

## Alternatives Considered

1. **In-place mutation of `JobListing`**: Add all provenance and validation lists directly to `JobListing`. Rejected because `JobListing` is serialized directly over public SSE streams and stored in SQLite `url_cache`. Inflating it with provenance vectors violates the public API contract (ADR 0008, `allowlist.py`) and breaks existing serialized cache records.
2. **Immediate retirement of `JobListing` across frontend and backend**: Replace all frontend types and backend schemas simultaneously. Rejected because it violates the Build Protocol's incremental step isolation rule and risks regressions across 71 frontend tests and 339 backend tests in one jump.
3. **Leave `CanonicalJob` as dead scaffolding**: Continue adding ad-hoc fields to `JobListing`. Rejected because field-level provenance, confidence scoring, and auditability cannot be maintained reliably without first-class evidence structures.

## Trade-offs

- **Memory and Translation Overhead**: Converting `CanonicalJob` to `JobListing` before yielding SSE batches incurs minor object instantiation overhead per job. Given search batch sizes (typically 10–100 jobs), this overhead is negligible (< 1ms).
- **Two Models in Codebase During Overhaul**: Developers must be aware of the boundary: internal pipeline logic uses `CanonicalJob`; external serialization uses `JobListing`. Clear module boundaries will enforce this distinction.

## Consequences

- Internal pipeline components (`ats_api_client.py`, `ats_page_enricher.py`, `nigerian_scrapers.py`, `field_normalizer.py`, `search_pipeline.py`) can evolve to structured provenance without breaking public API contracts.
- Frontend components and tests remain 100% green without requiring simultaneous frontend rewrites.
- Cache stores will transition to versioned serialization so old `JobListing` JSON records can be transparently upgraded to `CanonicalJob`.
