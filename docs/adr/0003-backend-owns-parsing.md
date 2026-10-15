# 3. Backend Owns Parsing

Date: 2026-10-15

## Status

Accepted

## Context

In web applications with complex data extraction pipelines, there is a common antipattern where the client interface attempts to patch or re-parse incoming data. For instance, frontend code might execute client-side regular expressions against job titles or snippets to infer remote work, strip company names, or clean up punctuation.

This dual-parsing paradigm introduces several severe issues:
1. **Split-Brain Behavior:** Logic updates in backend normalizers fail to take effect in the UI if frontend regexes override them.
2. **Untestable Transformations:** Backend test suites cannot guarantee what the user actually sees or filters by.
3. **Loss of Provenance:** Frontend regex mutations discard field provenance, making auditability and quality tracking impossible.

## Decision

The backend owns all parsing, extraction, normalization, and field derivation:

1. **Backend Exclusivity:** All parsing of job titles, company names, locations, employment types, work models, and descriptions occurs in the backend pipeline.
2. **Presentation-Only Client:** The frontend must never run heuristic parsers or regular expressions over titles, snippets, or descriptions to derive data attributes.
3. **Structured API Contract:** The backend delivers normalized fields alongside explicit provenance (e.g., `work_model`, `work_model_source`, `work_model_evidence`).
4. **Direct Filtering:** Client filters must operate strictly against backend-provided structured fields (e.g., filtering remote jobs checks `job.work_model === "remote"`).

## Consequences

- **Unified Single Source of Truth:** Changes to extraction heuristics exist in one place, backed by Python tests and real fixtures.
- **Client Simplicity:** Frontend codebase removes ad-hoc parsing routines, reducing client complexity and bundle size.
- **Consistent Auditability:** Data captured in backend audit tools (such as CSV exports or golden test sets) directly mirrors the data consumed by users in the UI.
