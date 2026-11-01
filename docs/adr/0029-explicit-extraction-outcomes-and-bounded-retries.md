# ADR 0029: Explicit Extraction Outcomes, Bounded Retries, and Failure Isolation

## Status

Accepted

## Context

Bottom Pot orchestrates concurrent job discovery across 7 ATS platforms and multiple regional job scrapers. Prior to this decision:
1. Provider API and scraping failures were collapsed into `None` (on 404) or into fallback snippet rows (`data_source="snippet"`, `_fallback()`). The caller and upstream search pipeline could not determine whether a snippet resulted from an organic search snippet or from a network timeout, HTTP 429, 500 error, or JSON parsing failure.
2. The search pipeline had no formal vocabulary for distinguishing between retryable network faults, rate limits, permanent client errors, malformed payloads, or non-existent listings.
3. Outbound HTTP retries existed only as a hardcoded decorator (`@with_retry`) on raw private ATS fetch methods, without tracking attempt counts, honoring caller search budgets, or allowing deterministic test clock/jitter injection.
4. When one provider failed or timed out, its errors were swallowed or dropped from `DoneEvent` metrics, reporting the search as complete without indicating partial failure.

## Decision

We establish an explicit outcome taxonomy, structured result containers, bounded retry policies, failure isolation semantics, and wire-safe telemetry according to the following invariants:

### 1. `ExtractionOutcome` Taxonomy & Mapping Table

All provider fetches, page enrichments, and scraping operations must classify their execution into exactly one `ExtractionOutcome`:

| Outcome | Semantics & Triggers | Retried? | Counts as Breaker Failure? | Marks Provider Partial? |
|:---|:---|:---:|:---:|:---:|
| `success` | Usable record extracted from target source. | No | No (records success) | No |
| `partial_success` | Usable record extracted, but a secondary enrichment step failed (e.g. apply URL JSON-LD fetch failed; undisclosed salary or work model is NOT partial). | No | No (records success) | No |
| `not_found` | Explicit HTTP 404, HTTP 410, absent from listing API/page, or confirmed expired listing notice. | No | No (neutral) | No |
| `rate_limited` | HTTP 429, or `Retry-After` header delay exceeds remaining budget. | Yes (bounded) | No (preserves breaker) | Yes |
| `retryable_error` | HTTP 408, 500, 502, 503, 504, `httpx.TimeoutException`, `httpx.ConnectError`, `httpx.NetworkError`, DNS failure, or circuit breaker tripped (0 attempts). | Yes (bounded, except circuit-open) | Yes (increments failure counter) | Yes |
| `permanent_error` | HTTP 401, 403, other 4xx (400, 422), other 5xx, redirect loops, WAF challenge/block (e.g. AWS WAF, Cloudflare bot block). | No | No (neutral/client error) | Yes |
| `parse_error` | HTTP 200 returned, but payload is malformed JSON, invalid HTML, or schema mismatch. | No | No | Yes |
| `unsupported_source` | Unknown host, unsupported ATS slug/URL pattern, or unrecognized URL scheme. | No | No | No |

### 2. `ExtractionResult` Container

Provider client methods must provide result-returning variants (`fetch_raw_result`, `fetch_result`, `enrich_ats_page_result`, `scraper.search_result`) returning:
```python
@dataclass
class ExtractionResult:
    outcome: ExtractionOutcome
    raw: RawJobPosting | None = None
    status_code: int | None = None
    error_summary: str | None = None
    attempts: int = 1
    degraded_from: str | None = None
```
- **Error sanitization**: `error_summary` must be safe for logging and admin telemetry. It MUST NOT contain authorization tokens, query strings, or credential-bearing URLs. URLs embedded in error summaries must be sanitized using `sanitize_source_url`.
- **Backward compatibility**: Public `fetch()` methods remain unchanged, returning `JobListing | None` built on top of the result-returning variants.

### 3. Visible Degradation Invariant

When a job falls back from ATS API to page scrape, or from API/scrape to snippet after an error:
- Additive per-job keys `extraction_outcome` and `degraded_from` are populated ONLY on degraded records (e.g. `extraction_outcome="retryable_error"`, `degraded_from="api"`).
- They are strictly absent on successful authentic records and on native snippet-only search results.
- Successful golden fixtures remain 100% byte-identical.

### 4. Bounded Retries & Budget Interaction

Outbound HTTP retries in `retry.py` are strictly bounded:
- **Eligible outcomes**: Only `retryable_error` and `rate_limited` on idempotent GET requests. Never retry `not_found`, `permanent_error`, `parse_error`, `unsupported_source`, circuit-open skips, or paid POST requests (Serper).
- **Limits**: Maximum 2 retries (3 attempts total).
- **Backoff schedule**: Base delay 0.5s doubling exponentially (0.5s, 1.0s) plus full jitter `random.uniform(0.05, 0.4)`. Capped at 5.0s per delay, and 10.0s total delay cap per job.
- **`Retry-After` Header**: Honored (parsing delta-seconds or HTTP date). If the required delay exceeds 10.0s or the remaining task budget, the request is NOT retried and immediately yields `rate_limited`.
- **Budget counting**: Each retry attempt increments the existing `SearchRunStats.pages_fetched` counter and honors `settings.global_concurrency_limit` and `settings.per_host_concurrency_limit`.
- **Testability**: Clock (`time_fn`), sleep (`sleep_fn`), and random number generator (`rng_fn`) are dependency-injected into retry executors for fast, deterministic unit testing.

### 5. Failure Isolation & Wire Telemetry

- **Heterogeneous Failure Isolation**: In `search_pipeline.py`, provider tasks run concurrently. Exceptions captured in `asyncio.gather(..., return_exceptions=True)` or task execution are classified into `ExtractionOutcome` and counted. Unexpected exceptions (programming errors) are logged at ERROR level with `unexpected_exception`, classified as `permanent_error`, and never silently converted into normal-looking snippets. `asyncio.CancelledError` is cleanly re-raised/handled.
- **`DoneEvent.provider_outcomes`**:
  An additive optional key `provider_outcomes` is added to `DoneEvent`:
  ```json
  {
    "provider_outcomes": {
      "greenhouse": {
        "outcomes": {"success": 4, "not_found": 1},
        "partial": false
      },
      "lever": {
        "outcomes": {"retryable_error": 2},
        "partial": true
      }
    }
  }
  ```
  - **No leakage**: `provider_outcomes` contains ONLY outcome counts and the boolean `partial` flag. No URLs, error messages, or internal tokens.
  - **Partial definition**: `partial = True` if the provider has any `retryable_error`, `rate_limited`, `permanent_error`, or `parse_error`. `not_found` and `unsupported_source` do not mark a provider as partial.
  - **Classification**: Classified in `allowlist.py` and typed in `frontend/src/types.ts`.

## Consequences

- All extraction failures are explicitly classified and auditable.
- Post-failure snippets are visibly distinguishable from clean snippet-only results.
- Outbound retries cannot spin out of control, multiply volume, or ignore host semaphores.
- The frontend and search clients receive honest wire indicators when provider results are partial.
