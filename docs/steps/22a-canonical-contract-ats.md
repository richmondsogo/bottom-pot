# Step 22a: Canonical Contract, Shared Extraction Service, ATS Migration

Initiative: **Extraction Pipeline & Architecture Overhaul**  
Role: **Planner / Builder**  
Branch: `step/22a-canonical-contract-ats`  
Date: 2026-11-01  
Status: **Completed — Ready for PR & Merge**

---

## 1. Scope & Provider Checklist

Establish `CanonicalJob` as the authoritative internal domain model, build `CanonicalJobAdapter` (`to_listing`, `from_listing`) preserving wire compatibility, implement a shared `JobExtractionService` consuming `RawJobPosting`, implement deterministic salary extraction (`salary_parser.py`), and migrate all 7 ATS API clients to yield raw envelopes.

- [x] Golden baseline snapshotted (`tests/fixtures/golden/`)
- [x] `CanonicalJob` lean contract, `JobSalary` extensions & `CanonicalJobAdapter`
- [x] Salary extraction engine (`salary_parser.py`) & table-driven tests (33 cases)
- [x] Shared `JobExtractionService` & `RawJobPosting` envelope
- [x] Provider: Greenhouse (`GreenhouseClient`)
- [x] Provider: Lever (`LeverClient`)
- [x] Provider: Ashby (`AshbyClient`)
- [x] Provider: SmartRecruiters (`SmartRecruitersClient`)
- [x] Provider: Workable (`WorkableClient`)
- [x] Provider: BambooHR (`BambooHRClient` - lightweight)
- [x] Provider: Recruitee (`RecruiteeClient`)
- [x] Golden replay comparison & documentation of intentional diffs
- [x] Verification suite (`scripts/verify.ps1`, full `pytest` 388/388, vitest 72/72)

---

## 2. Intentional Diffs & Output Ledger

| Fixture / Provider | Field | Old Value (`main`) | New Value (Step 22a) | Rationale |
|---|---|---|---|---|
| `smartrecruiters_744000155937924` | `salary` | `null` | `JobSalary(min=135000, max=175000, currency="GBP", period="year", source="smartrecruiters_structured")` | Extracted from structured `compensation` field in API fixture. |
| `recruitee_2774909` | `salary` | `null` | `JobSalary(min=40, max=48, currency="USD", period="hour", source="recruitee_structured")` | Extracted from structured `salary` object in API fixture. |
| All fixtures | `JobSalary` schema | `{min, max, currency, period}` | Added `raw_text`, `source` | Evidence tracking per ADR 0027. Tolerated by frontend & Playwright. |

*Note on `salary_parser.py`: Newly created in Step 22a; replaces ad-hoc regex in scrapers with a shared, deterministic engine with ISO 4217 validation, currency disambiguation (e.g. `$` requires context; `£` -> GBP; `€` -> EUR), and negative filtering.*

---

## 3. Regression Test Proofs & Matrix

| Component | Target Test | Proof / Behavior | Status |
|---|---|---|---|
| **Contract Round-Trip** | `test_canonical_job_adapter_round_trip` | Proves `JobListing` -> `from_listing()` -> `to_listing()` is byte-identical for all fields. | Fully Resolved |
| **Salary Extraction** | `test_salary_parser.py` (33 tests) | Tests ranges (`$80,000–$100,000/yr`), `k` suffixes (`80k-100k`), multi-currency (`GBP`, `EUR`, `NGN`, `CAD`), periods (`year`, `month`, `week`, `day`, `hour`), units (cents conversion), negative guards (`401k`, `$50M raised`, `10,000 employees`, `$5,000 bonus`, years like 2024), and conflicting range rejection. | Fully Resolved |
| **Short Description Work-Model** | `test_short_authentic_description_classifies_work_model_via_client` | Proves a concise authentic description (<300 chars) correctly extracts `remote` work model via `JobExtractionService` without UI display threshold conflation. | Fully Resolved |
| **Golden Replay** | `test_replay_all_real_fixtures_against_golden_snapshots` | Replays all 10 real ATS fixtures against snapshots; asserts byte-identical match with only the 2 intentional structured salary diffs above. | Fully Resolved |

---

## 4. Verification Suite Results

| Suite / Check | Baseline (Step 21) | Step 22a Result | Status |
|---|---|---|---|
| **Repository Secrets** | 0 tracked secrets | 0 tracked secrets | Pass |
| **Frontend Checks (Lint/Typecheck/Vitest)** | 72 tests passed, 0 errors | 72 passed, 0 errors | Pass |
| **Backend Test Suite (`pytest`)** | 350 passed, 0 `utcnow` warnings | 388 passed, 0 `utcnow` warnings | Pass |
| **Playwright E2E** | 11 passed | 11 passed | Pass |
| **Full Verify Suite (`verify.ps1`)** | 8/8 checks passed | 8/8 checks passed | Pass |

---

## 5. Provenance & Git Tracking

| Field | Value |
|---|---|
| **Branch** | `step/22a-canonical-contract-ats` |
| **Pull Request** | Pending |
| **First Commit SHA** | `2f4417c` |
| **Last Commit SHA** | Pending |
| **Merge Commit SHA** | Pending |
