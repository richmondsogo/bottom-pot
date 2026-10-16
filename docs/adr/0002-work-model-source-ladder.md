# 2. Work Model Source Ladder and Provenance

Date: 2026-10-15

## Status

Accepted

## Context

Job postings convey work arrangement (remote, hybrid, or in-person) across disparate tiers of structured and unstructured data: structured API payloads, JSON-LD metadata, boolean flags, location strings, job titles, and freeform job descriptions. Historically, parsing logic inspected multiple fields haphazardly or allowed noisy freeform text to override structured ATS metadata. Furthermore, resolutions lacked audit trails, making it impossible to determine whether a "hybrid" label originated from an official ATS API enum or a casual phrase like "hybrid cloud architecture" in the job description.

## Decision

We establish a deterministic priority ladder for resolving work models. Resolution proceeds strictly from highest-confidence source to lowest-confidence source, stopping at the first conclusive signal:

1. **`api_enum`**: Explicit ATS workplace type enum (e.g., Ashby `workplaceType`, Lever `workplaceType`, SmartRecruiters `remoteType`).
2. **`jsonld`**: Standard schema.org `JobPosting.jobLocationType` (e.g. `TELECOMMUTE`).
3. **`li_tag`**: Explicit recruiter tags `#LI-(Remote|Hybrid|Onsite|On-site)` scanned from trusted descriptions (API field or JSON-LD) after HTML-unescaping and before markdown cleanup. Multiple different tags or disagreements with description-scan resolve to `None`. `#LI-Onsite` is treated as a weak fallback only when no other signal exists.
4. **`location`**: Explicit prefix or token in the location string (e.g. `Remote`, `Hybrid`).
5. **`title`**: Delimited tag in the title (e.g. `[Remote]`, `(Hybrid)`, `- On-site`).
6. **`description`**: Scanned body text with negation boundaries and keyword context filtering, evaluated **only** when `description_ok` is verified. If conflicting signals exist in description text, resolution falls back to `None`.
7. **`None`**: Absence of evidence yields unknown (`None`).

Provider boolean flags (previously `api_flag`) are excluded entirely: boolean flags are not evidence because providers like Ashby set `isRemote: true` for hybrid roles.

Every derived work model must record:
- `value`: `"remote" | "hybrid" | "in_person" | None`
- `source`: The tier where the signal was obtained (`api_enum`, `jsonld`, `li_tag`, `location`, `title`, `description`)
- `evidence`: The literal text snippet or key/value pair providing the signal.

## Consequences

- **Determinism:** Structured signals from APIs always take precedence over fuzzy textual mentions.
- **Provider Boolean Removal:** Eliminates false-positive remote classifications caused by ambiguous boolean flags (e.g., Ashby hybrid jobs marked as `isRemote=true`).
- **Recruiter Tag Fidelity:** Capitalizes on standardized `#LI-*` tokens embedded by recruiters in trusted descriptions while stripping them from display.
- **Explainability:** Telemetry, audit reports, and UI tooltips surface the exact snippet and source that determined the job's work model.
- **Safety:** Freeform descriptions are never scanned unless the description passes strict quality validation, preventing navigation, headers, or boilerplate from polluting results.
