# Step 23: Provenance and Confidence, URL Normalization, Deduplication

Initiative: **Extraction Pipeline & Architecture Overhaul**  
Role: **Planner / Builder**  
Branch: `step/23-provenance-identity-dedup`  
Date: 2026-11-01  
Status: **In Progress**

---

## 1. Scope & Implementation Checklist

Put field-level evidence and validation models into production use via `JobExtractionService`, establish an authoritative deterministic confidence scale (ADR 0028), maintain wire compatibility for scalar confidence and optional field evidence, implement shared URL normalization with an ATS provider registry, separate source-record identity from canonical identity, and replace first-seen-wins deduplication with conservative, order-independent progressive merging.

### Checklist
- [x] Pre-checks & baseline snapshot verified
  - [x] Clean working tree & no committed scratch scripts
  - [x] Step 22b doc updated with missing `ashby_d3bc1ced.json` and `greenhouse_8860302002.json` link preservation diffs
  - [x] Step 22b doc updated with Nigerian golden salary sample note (2 records with salaries, 0 lost strings)
  - [x] Table-driven negative salary cases expanded ("2024", "401k", "raised $1.2M", "$2M budget", "N/A")
  - [x] Re-run `results.json` description cleaning check via `JobExtractionService`: 19 class changes (`{'remote': 11, None: 23, 'hybrid': 14, 'in_person': 4}`)
  - [x] Recorded note that `audit.csv` has no descriptions and cannot test description cleaning
- [ ] Provider branches moved to provider modules (`SmartRecruitersClient` `remote=`, `WorkableClient` extraction method)
- [ ] Direct `JobListing` instantiations in `_fallback()` and `_snippet_listing()` routed through `JobExtractionService`
- [ ] ADR 0028: Deterministic field-level confidence policy & per-field rubric table
- [ ] Field-level evidence & confidence emitted across all 9 core fields (`JobExtractionService`)
- [ ] Legacy scalar `JobListing.extraction_confidence` deterministically derived from core fields
- [ ] Additive optional wire key `field_evidence` verified with Vitest & Playwright tolerance
- [ ] Centralized URL normalizer (`url_normalizer.py`) with query tracking parameter stripper and provider identifier registry
- [ ] Identity separation: source-record ID separated from canonical job ID with stable legacy `JobListing.id`
- [ ] Conservative order-independent deduplicator with field-by-field merge replacing first-seen-wins `GlobalDeduplicator`
- [ ] Regression test matrix (order-independence, distinct city separation, tracking param merge, distinct `gh_jid` separation, work-model conflict preservation, confidence determinism)
- [ ] Full verification suite passing (`verify.ps1`, full `pytest`, Vitest, Playwright, golden replays)

---

## 2. Pre-Check Findings & Evaluation Notes

1. **`results.json` Work-Model Cleaner Evaluation**:
   - Stored descriptions passed through `JobExtractionService` description cleaning (`strip_li_tags` and `to_markdown`) prior to work-model resolution:
     - Baseline (uncleaned): `{'remote': 30, None: 13, 'hybrid': 5, 'in_person': 4}`
     - Cleaned: `{'remote': 11, None: 23, 'hybrid': 14, 'in_person': 4}`
     - Class changes: 19 rows. Cleaning removes noisy recruiter tags and ungrammatical HTML formatting, accurately reclassifying jobs to `hybrid` or `None`.
   - **`audit.csv` note**: `audit.csv` contains only `location` and `title` without description text, so it cannot test the description cleaner.
2. **Unparseable Salary Evidence Retention**:
   - Unparseable salary text (e.g. "Negotiable", "DOE", "Attractive") yields `salary=None` on the model, but the raw text is preserved in `field_evidence` with `validation_status=ValidationStatus.REJECTED` and an explicit reason.
3. **Provider Bypasses**:
   - `_fallback()` in `ats_api_client.py` and `_snippet_listing()` in `search_pipeline.py` migrated to `JobExtractionService`.
   - Enricher provider paths (SAP, Taleo, Avature, JazzHR, Teamtailor, Jobvite, Workday) already route through `JobExtractionService`.
