# ADR 0028: Deterministic Field Confidence and Provenance Architecture

## Status

Accepted

## Context

Prior to this decision, Bottom Pot tracked extraction confidence solely as an ad-hoc scalar float (`JobListing._compute_confidence`) with heuristic penalties and bonuses (e.g. +0.1 for salary, -0.3 for short descriptions) tied to whether fields were populated rather than the quality of the evidence. Furthermore, source reliability and field confidence were conflated: an authentic Greenhouse API payload was assumed to confer uniform confidence across all fields, even when location was a free-form string or work model was absent.

In addition, provenance was incomplete: while `CanonicalJob` defined `FieldEvidence`, `FieldValidation`, and `FieldConfidence` models in Step 22a, they were not populated across all 9 core fields or utilized for downstream resolution and deduplication.

## Decision

We establish an authoritative, deterministic field-level confidence and provenance policy governed by the following core invariants:

1. **Evidence Quality Over Field Presence**:
   Confidence reflects evidence specificity, structured typing, and agreement between independent signals—not whether a field happens to be non-null, and not solely the acquisition transport.

2. **Decoupled Source Reliability & Field Confidence**:
   An authentic ATS API job does not receive uniform confidence. Structured enums (e.g. `workplaceType`) receive high confidence (0.9), while free-text fields (e.g. `location: "Remote - US"`) receive moderate confidence (0.7), and missing fields receive `None`.

3. **Deterministic Rubric Scale (Never 1.0, Max 0.95)**:
   - **0.90**: Typed or enumerated structured values (ATS API workplace enum, JSON-LD employment enum, ISO UTC date, structured salary with verified currency AND period); structured free text for title and company; authentic full descriptions meeting display quality (`description_ok=True`).
   - **0.70**: Structured free-text location; authentic descriptions that are short (<300 chars, `description_ok=False`); explicitly labelled text in job bodies (e.g. `"Salary: $120k"`, `"#LI-Remote"` recruiter tag).
   - **0.60**: Capped maximum for salary missing currency or period.
   - **0.50**: Unlabelled contextual text inference (e.g. regex matched within paragraph text).
   - **0.30**: Search snippet-derived fields (title, location, company), restricted only to fields that snippets are authorized to populate.
   - **Modifiers**:
     - **+0.05**: Independent signal agreement (e.g. title mentions "Remote" and API enum confirms "Remote"). Capped at 0.95.
     - **-0.20**: Signal conflict (e.g. structured enum conflicts with body text). Both signals are preserved in evidence, the winning structured value receives a -0.20 penalty, and a conflict flag is recorded.
   - **None**: Unknown or unpopulated fields receive `None`, never 0.0 or an arbitrary low number.

4. **Zero Non-Determinism**:
   Confidence calculations contain zero randomness, zero wall-clock dependence, and zero LLM calls. The confidence of identical inputs is identical across runs.

5. **Sanitized Evidence & Wire Safety**:
   - Source URLs stored in evidence have query parameters stripped to prevent leaking security tokens or sensitive query parameters.
   - Raw text evidence snippets are capped at 200 characters; raw job descriptions are never embedded in field evidence.
   - Optional unparseable compensation strings (e.g. "Competitive", "DOE", "Negotiable") are retained in field evidence with `ValidationStatus.REJECTED` and explicit explanation, ensuring raw signals are auditable without fabricating a `JobSalary` object.

## Alternatives Considered

1. **Continuous Probabilistic Scoring (0.0 to 1.0)**: Use machine-learned or fuzzy weights. Rejected because opaque float scores cannot be audited deterministically, invite drift, and violate the project's preference for deterministic rules over statistical guesses.
2. **Keying Confidence on Acquisition Method Alone**: Assign 1.0 to API, 0.7 to Scrape, 0.3 to Snippet. Rejected because an authentic API response can contain unverified free text or omit fields entirely.

## Consequences

- Every extracted field carries traceable evidence, validation status, and a deterministic score.
- Downstream deduplication can compare field confidences directly, replacing first-seen-wins with field-by-field progressive merging.
- Wire compatibility is preserved: external consumers receive the legacy scalar `extraction_confidence` (derived from core field confidences) and may optionally inspect additive `field_evidence`.
