# 2. Work Model Source Ladder and Provenance

Date: 2026-10-15

## Status

Accepted

## Context

Job postings convey work arrangement (remote, hybrid, or in-person) across disparate tiers of structured and unstructured data: structured API payloads, JSON-LD metadata, boolean flags, location strings, job titles, and freeform job descriptions. Historically, parsing logic inspected multiple fields haphazardly or allowed noisy freeform text to override structured ATS metadata. Furthermore, resolutions lacked audit trails, making it impossible to determine whether a "hybrid" label originated from an official ATS API enum or a casual phrase like "hybrid cloud architecture" in the job description.

## Decision

We establish a deterministic priority ladder for resolving work models. Resolution proceeds strictly from highest-confidence source to lowest-confidence source, stopping at the first conclusive signal:

1. **`api_enum`**: Explicit ATS workplace type enum (e.g., Ashby `workplaceType`, Lever `workplaceType`, SmartRecruiters enums).
2. **`jsonld`**: Standard schema.org `JobPosting.jobLocationType` (e.g. `TELECOMMUTE`).
3. **`api_flag`**: Explicit boolean flag `is_remote == True`. Note that `is_remote == False` carries zero evidential weight for `in_person` and is ignored.
4. **`location`**: Explicit prefix or token in the location string (e.g. `Remote`, `Hybrid`).
5. **`title`**: Delimited tag in the title (e.g. `[Remote]`, `(Hybrid)`, `- On-site`).
6. **`description`**: Scanned body text with negation boundaries and keyword context filtering, evaluated **only** when `description_ok` is verified. If conflicting signals exist in description text, resolution falls back to `None`.
7. **`None`**: Absence of evidence yields unknown (`None`).

Every derived work model must record:
- `value`: `"remote" | "hybrid" | "in_person" | None`
- `source`: The tier where the signal was obtained (`api_enum`, `jsonld`, `api_flag`, `location`, `title`, `description`)
- `evidence`: The literal text snippet or key/value pair providing the signal.

## Consequences

- **Determinism:** Structured signals from APIs always take precedence over fuzzy textual mentions.
- **Explainability:** Telemetry, audit reports, and UI tooltips can surface the exact snippet and source that determined the job's work model.
- **Safety:** Freeform descriptions are never scanned unless the description passes strict quality validation, preventing navigation, headers, or boilerplate from polluting results.
