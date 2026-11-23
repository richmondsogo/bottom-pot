# ADR 0034: Job Freshness Tiers, Ranking Policy, and Backend Eligibility Authority

## Status
Accepted (Step 57 Phase 5)

## Context
1. **Stale postings masquerading as fresh (`docs/LESSONS.md` `L-07`):** Audits showed long-lived postings (some 162–2,384 days old) appearing alongside new openings with only an unranked `posted_at` date.
2. **Duplicated Python/TypeScript eligibility logic (`docs/LESSONS.md` `L-06`):** Despite `ADR 0003` ("Backend owns parsing"), TypeScript code in `frontend/src/lib/` re-parsed display labels such as `"Paystack (+N more)"`, drifting from `src/extraction/eligibility_extractor.py`.

## Decision

1. **Canonical Freshness Model (`src/extraction/freshness.py`, `frontend/src/lib/freshness.ts`):**
   - Classify every posting into a `FreshnessTier`:
     - `fresh`: `<= 30` days since `posted_at` (or `first_seen_at` fallback)
     - `recent`: `31–90` days
     - `stale`: `> 90` days
     - `evergreen`: Assigned **only** on an explicit ATS evergreen flag or explicit multi-hire/pipeline statement (`ADR 0001` forbids inferring evergreen status solely from age or missing dates).
   - Default search result sorting (`sortJobs` / `freshness_rank_key`) ranks fresh/recent/evergreen roles ahead of stale postings, and both `ResultsTable.tsx` and `ResultsCards.tsx` render explicit age badges plus an `"Older postings (N) · Posted over 90 days ago"` divider.
   - Read-only freshness audits run via `python scripts/report_freshness.py` (offline fixture census or opt-in DB inspection).
2. **Backend-Authoritative Eligibility Evaluation (`POST /api/eligibility/evaluate`):**
   - `src/extraction/eligibility_extractor.py` and `src/extraction/eligibility_labels.py` remain the sole authoritative source for `objective_scope_label` and country-specific `applicant_assessment`.
   - Changing the applicant country selector re-evaluates currently loaded jobs via `POST /api/eligibility/evaluate` rather than re-parsing display strings on the client (`frontend/src/lib/legacyEligibilityFallback.ts` handles only offline/mock fallback records).
   - Shared cross-language test vectors in `tests/vectors/eligibility.json` lock parity between `pytest` (`tests/test_eligibility_vectors.py`) and `vitest` (`frontend/src/lib/__tests__/eligibilityVectors.test.ts`).

## Consequences
- Testers see posting age clearly separated from stale listings in default search results.
- Country switching remains consistent across backend SSE streams and client interactions without duplicating geographic restriction parsers in TypeScript.
