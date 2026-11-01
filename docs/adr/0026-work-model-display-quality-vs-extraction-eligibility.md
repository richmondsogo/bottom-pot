# ADR 0026: Work-Model Display Quality vs Extraction Eligibility

## Status

Proposed

## Context

In Bottom Pot, work model resolution (`src/project_files/work_model.py`) is governed by ADR 0002 (Work Model Source Ladder):
1. Tier 1: Explicit API enum / workplace type.
2. Tier 2: JSON-LD `jobLocationType=TELECOMMUTE`.
3. Tier 3: Recruiter tag (`#LI-Remote`, `#LI-Hybrid`).
4. Tier 4: Location string tokens.
5. Tier 5: Title tokens.
6. Tier 6: Description text scan (only if `description_ok=True`).
7. Tier 7: Weak fallback (`#LI-Onsite`).
8. Tier 8: Unknown.

Currently, Tier 6 requires `description_ok: bool = True`. However, `description_ok` is determined by `description_quality(text)` in `field_normalizer.py`:
- Checks `len(text) >= 300`.
- Checks boilerplate match count < 3.
- If DOM scraped, checks for at least 2 structural terms.

This creates severe unintended side effects:
1. **Conflation of Display vs Extraction**: A concise, authentic job posting from Greenhouse or Lever API that has 280 characters of description text fails `description_quality` (`len < 300`). Consequently, `description_ok` is set to `False`, and `resolve_work_model` completely skips Tier 6 description scanning. Even if the text explicitly says "This is a 100% remote role", the job is left as `None`/unknown or misclassified.
2. **Provider Inconsistency**: To work around this, Nigerian scrapers bypass `description_quality` entirely by passing `description_ok=bool(body_text)` (line 1075) or hardcoding `description_ok=True` (line 1205), whereas all 7 ATS API clients never pass `description` or `description_ok` to `resolve_work_model` at all (they only pass `trusted_description` for `#LI-` tags).
3. **Ghost Jobs under Frontend Filters**: In `frontend/src/lib/filter.ts`, filtering by `workModel` matches exact strings (`'remote'`, `'hybrid'`, `'in_person'`). If a job has `work_model === 'unknown'` (as mandated by ADR 0001 and the domain rules), filtering by `'remote'` excludes it, `'hybrid'` excludes it, `'in_person'` excludes it, and `'not_specified'` also excludes it because `'unknown'` is a non-empty string. It vanishes from all filtered views.

## Decision

We will explicitly decouple **Description Display Quality** from **Extraction Eligibility**.

Specifically:
1. **Extraction Eligibility (`description_eligible_for_extraction`)**:
   - Any description text sourced directly from an authenticated or structured ATS API payload (Greenhouse, Lever, Ashby, etc.) or JSON-LD `JobPosting.description` is authentic and eligible for Tier 6 work-model and salary extraction, regardless of string length.
   - For uncurated DOM-scraped bodies (e.g. generic enricher or unbundled aggregator pages), basic anti-noise criteria must pass (boilerplate count < 3) before text is scanned.
2. **Display Quality (`description_ok`)**:
   - `description_ok` remains a presentation-layer gate indicating whether the description text is substantive and clean enough to render as a markdown reading pane in the UI (`len >= 300`, minimal boilerplate, structural layout).
   - If a description fails display quality, it is hidden from the reading pane, but any structured fields extracted from it during ingestion are preserved with their evidence.
3. **Explicit Unknown Work Model**:
   - When no valid signal is found across all tiers, `work_model` is explicitly set to `"unknown"` (never `None`, never defaulting to `remote` or `in_person`).
   - The frontend filter (`frontend/src/lib/filter.ts`) and normalizer (`frontend/src/lib/normalize.ts`) will treat `"unknown"` as synonymous with `"not_specified"`, preventing ghost jobs.

## Alternatives Considered

1. **Lower length threshold in `description_quality` from 300 to 100**: Lowering the threshold would allow shorter descriptions to be scanned, but would also allow low-quality 120-character snippets and cookie blurbs to render as "job descriptions" in the UI detail pane.
2. **Keep `work_model` as `None` instead of `"unknown"`**: Returning `None` conflates "not yet processed" with "processed and verified to have no disclosed work model arrangement". An explicit `"unknown"` satisfies ADR 0001.

## Trade-offs

- **Filter Semantics Adjustment**: Frontend filter unit tests expecting `null` work models will need test updates to verify `"unknown"` handling.
- **Evidence Verification**: Scanned descriptions must record exact matching snippets in `work_model_evidence` to prevent regression.

## Consequences

- Real remote jobs with concise descriptions on Greenhouse, Lever, and Ashby will no longer be lost to `None`/unknown.
- Display presentation logic is cleanly separated from data extraction semantics.
- Users filtering by "Not specified" / "Unknown" will accurately see all unclassified jobs without ghosting.
