# ADR 0033: Shared Monitored-Provider Contract and C1–C12 Conformance Suite

## Status
Accepted (Step 57 Phase 4)

## Context
Previously, all nine monitored ATS adapters resided together inside a 4,313-line `board_adapters.py` module alongside four near-parallel cache-repair modules. Each adapter implemented slightly different root-shape validation, content hashing (truncated SHA-1/SHA-256 hashes sensitive to JSON key order/whitespace), conditional `304` handling, HTTP transport wrappers, error handling, and missing-job closure thresholds. Fixing a bug in one provider left the other eight exposed to the same failure class (`docs/LESSONS.md` `L-03`).

## Decision

1. **Unified Provider Primitives (`src/providers/`):**
   - `contract.py`: Defines `FailureKind` closed error taxonomy, `ReconciliationPolicy` (`PROVIDER_RECONCILIATION_POLICIES`), `BoardCheckResult`, `failure_result`, `classify_http_status`, `classify_exception`, and cross-poll `detect_id_drift`.
   - `http.py`: Centralizes `validate_board_token_safety`, `build_conditional_headers`, `validate_provider_url`, and streaming `fetch_provider_bytes` with SSRF/DNS validation and byte caps across all 9 providers.
   - `fingerprint.py`: Enforces full 64-hex whitespace- and key-order-invariant SHA-256 (`canonical_content_hash`, `compute_board_fingerprint`).
   - `pagination.py` & `detail_hydration.py`: Extract shared offset pagination checks, HTML loop guards, and fair detail-retry scheduling (`Workable`, `SmartRecruiters`).
   - `src/core/clock.py`: Provides injectable `use_clock` / `utc_now` / `epoch_now` for deterministic timestamps.
2. **Per-Provider Modules & Unified Cache Repair:**
   - Split all nine adapters into dedicated `src/providers/<provider>.py` modules while retaining `src/providers/board_adapters.py` as a 112-line registry/facade (`BOARD_ADAPTERS`), and unified cache repairs behind dry-run-by-default `src/monitoring/cache_repair/engine.py`.
3. **Parametrized C1–C12 Conformance Suite (`tests/conformance/`):**
   - Holds every registered member of `BOARD_ADAPTERS` to one executable specification checking root-shape validation (C1), duplicate-ID rejection and ID-drift detection (C3), noise-invariant hashing (C4), conditional `304` semantics (C5), bounded byte streaming and transport path uniformity via AST verification (C6/C7), typed `FailureKind` and closure thresholds (C8), unknown-beats-wrong workplace mapping (C9), and injected clock determinism (C10), plus `SafetyError` propagation (`tests/test_operational_db_safety.py`).

## Consequences
- Any new provider-level safeguard or bug fix applies across all nine providers once and is verified identically for every adapter by the conformance suite (`docs/providers/inventory.md`).
- Per-provider differences (such as Recruitee's `16 MiB` response ceiling or `1` vs `2` missing-confirmation strikes) are declared explicitly in code (`settings.py`, `PROVIDER_RECONCILIATION_POLICIES`) and per-provider documentation (`docs/providers/<provider>.md`).
