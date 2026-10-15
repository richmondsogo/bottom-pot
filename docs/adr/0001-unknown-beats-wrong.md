# 1. Unknown Beats Wrong

Date: 2026-10-15

## Status

Accepted

## Context

In job discovery and scraping systems, extracting accurate job metadata (such as work model, employment type, and salary) is critical for candidate trust. Historically, parsers frequently applied implicit assumptions and default values when evidence was missing. For example, if a job posting had a physical location like "Atlanta, GA" but did not state its work model, earlier logic defaulted the work model to `in_person`. Similarly, an ATS API flag `is_remote: false` was erroneously treated as proof of on-site work, when in practice companies set `false` for hybrid roles or merely leave default flags unconfigured.

Defaulting absence of evidence to a concrete value produces false classifications that mislead job seekers, particularly developers filtering specifically for remote or hybrid positions.

## Decision

We establish the foundational principle: **Unknown beats wrong.**

1. No fallback mechanism or parser heuristic may convert the absence of evidence into a concrete value.
2. If evidence is insufficient, ambiguous, or conflicting, the parser must produce `None` (`null`) for that field.
3. Negative inferences (such as `is_remote=False` implying `in_person`) are strictly prohibited unless supported by explicit textual or enum confirmation.
4. Downstream layers, including database models, API responses, and frontend displays, must treat `None` as a first-class neutral state ("Not specified").

## Consequences

- **Precision & Data Trust:** Users and automated pipelines receive only verified attributes. False positives and erroneous filters are eliminated.
- **Handling Nulls:** Frontend components and search filters must explicitly handle unclassified postings (e.g., displaying neutral badges instead of forced categorization).
- **Auditability:** Every classified field must be backed by tangible evidence rather than a silent default.
