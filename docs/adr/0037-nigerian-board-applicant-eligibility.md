# ADR 0037: Nigerian Job Board Applicant Eligibility for Nigeria

Date: 2026-11-26

## Status

Accepted (Refines [ADR 0001](0001-unknown-beats-wrong.md))

## Context

Under [ADR 0001](0001-unknown-beats-wrong.md) ("Unknown Beats Wrong"), `evaluate_eligibility_for_country` conservatively returns `status="unknown"` (`"Eligibility unverified"`) whenever a posting lacks explicit residence or country-level eligibility facts. While this prevents false positives on global ATS boards (Greenhouse, Lever, Ashby, Workable, etc.), it produced unverified badges for Nigerian applicants browsing jobs scraped from Nigeria's domestic job boards (`jobberman`, `myjobmag`, `hotnigerianjobs`—the three active boards in `NIGERIAN_SCRAPERS`), even when those postings omit an explicit `"Nigeria"` residence clause or have `eligibility=None` (such as search-card-only listings).

An offline audit of all 15 existing Nigerian board fixtures (`tests/fixtures/real/jobberman/*.html`, `tests/fixtures/real/hotnigerianjobs/*.html`, `tests/fixtures/nigerian/*.html`, and `tests/fixtures/golden/{jobberman,myjobmag,hotnigerianjobs}*.json`) confirmed zero matches (`0 / 15`) for `_EXCLUDED_RESIDENCE_RE` and zero explicit Nigerian exclusions.

## Decision

We will treat postings from the active Nigerian job boards (`NIGERIAN_BOARD_PROVIDERS = frozenset({"jobberman", "myjobmag", "hotnigerianjobs"})`) as `eligible` when evaluated for applicant country `"NG"` (`Nigeria`), subject to explicit exclusion precedence:

1. In `evaluate_eligibility_for_country(..., provider: str | None = None)`, when `cc == "NG"` and `(provider or "").strip().lower()` is in `NIGERIAN_BOARD_PROVIDERS`:
   - Check explicit exclusion evidence first (`"NG"` in `excluded_country_codes`, or any entry in `excluded_regions` containing `"NG"`). If explicitly excluded, return `status="restricted"` with the exclusion reason.
   - Otherwise—even when `eligibility is None` or metadata is missing or generic—return `status="eligible"` with reason `"Listed on a Nigerian job board (workable from Nigeria)."` and a clean `summary_label` (such as `"Nigeria eligible"`, `"Remote · Nigeria eligible"`, or `"Onsite · Lagos"`), never `"Eligibility unverified"` or `"Restricted"`.
2. Pass `provider=listing.provider or listing.ats_source` from `apply_applicant_country_assessment`, and `provider=provider` from `extract_eligibility` when computing `nigeria_eligible`.
3. Behavior for `cc != "NG"` and for all non-Nigerian providers remains 100% unchanged under ADR 0001.

## Alternatives Considered

1. **Synthesize `allowed_residence_countries=["Nigeria"]` during extraction:** Would misrepresent missing metadata as an observed textual fact in `JobEligibility.facts`, breaking provenance guarantees and failing `cc != "NG"` invariance (it would falsely mark non-NG applicants as `"restricted"` rather than `"unknown"`).
2. **Keep Nigerian board jobs `"unknown"` when metadata is omitted:** Leaves Nigerian users with `"Eligibility unverified"` across domestic Nigerian boards where local workability is implicit in the marketplace.

## Trade-offs

- Introduces a narrowly scoped source-market assumption exclusively for `(provider in NIGERIAN_BOARD_PROVIDERS, applicant_country == "NG")`.
- If a Nigerian board ever carries a non-Nigerian role without an explicit Nigerian exclusion clause recognized by `_EXCLUDED_RESIDENCE_RE`, it will be marked `eligible` for `NG` rather than `unknown`. Explicit exclusion patterns can still override this at any time.

## Consequences

- Nigerian applicants searching or viewing jobs from `jobberman`, `myjobmag`, and `hotnigerianjobs` see `eligible` with a clear explanation instead of `"Eligibility unverified"`, while explicit exclusions continue to show `"restricted"`.
- Stateless re-evaluation via `/api/eligibility/evaluate` requires passing `provider` on `EligibilityEvaluateItem` (`src/core/models.py`, `src/api/main.py`) so client-side country switching matches server-side search enrichment.
- All non-Nigerian providers and all non-`NG` applicant countries preserve strict ADR 0001 semantics.
