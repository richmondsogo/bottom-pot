# Step 22a: Canonical Contract, Shared Extraction Service, ATS Migration

Initiative: **Extraction Pipeline & Architecture Overhaul**  
Role: **Planner / Builder**  
Branch: `step/22a-canonical-contract-ats`  
Date: 2026-11-01  
Status: **In Progress**

---

## 1. Scope & Objective

Establish `CanonicalJob` as the authoritative internal domain model, build `CanonicalJobAdapter` (`to_listing`, `from_listing`) to preserve the `JobListing` wire format, implement a shared `JobExtractionService` consuming `RawJobPosting`, implement deterministic salary extraction (`salary_parser.py`), and migrate all 7 ATS API clients to yield raw envelopes.

### Provider Migration Checklist
- [x] Golden baseline snapshotted (`tests/fixtures/golden/`)
- [x] `CanonicalJob` contract, `JobSalary` extensions & `CanonicalJobAdapter`
- [x] Salary extraction engine (`salary_parser.py`) & table-driven tests
- [x] Shared `JobExtractionService` & `RawJobPosting` envelope
- [x] Provider: Greenhouse (`GreenhouseClient`)
- [x] Provider: Lever (`LeverClient`)
- [x] Provider: Ashby (`AshbyClient`)
- [x] Provider: SmartRecruiters (`SmartRecruitersClient`)
- [x] Provider: Workable (`WorkableClient`)
- [x] Provider: BambooHR (`BambooHRClient` - lightweight)
- [ ] Provider: Recruitee (`RecruiteeClient`)
- [ ] Golden replay comparison & documentation of intentional diffs
- [ ] Verification suite (`scripts/verify.ps1`, full `pytest`)

---

## 2. Intentional Diffs & Output Ledger

| Fixture / Provider | Field | Old Value (`main`) | New Value (Step 22a) | Rationale |
|---|---|---|---|---|
| `smartrecruiters_744000155937924` | `salary` | `null` | `JobSalary(min=135000, max=175000, currency="GBP", period="year")` | Extracted from structured `compensation` field in API fixture. |
| `recruitee_2774909` | `salary` | `null` | `JobSalary(min=40, max=48, currency="USD", period="hour")` | Extracted from structured `salary` object in API fixture. |
| All | `JobSalary` schema | `{min, max, currency, period}` | Added `raw_text`, `source` | Evidence preservation per ADR 0027. |

*Note on `salary_parser.py`: Newly created in Step 22a; previously no shared salary parsing module existed (only ad-hoc regex in `nigerian_scrapers.py`).*

---

## 3. Verification & Baseline Results

| Suite / Check | Baseline (Step 21) | Step 22a Result | Status |
|---|---|---|---|
| **Repository Secrets** | 0 tracked secrets | Pending | - |
| **Frontend Checks (Lint/Typecheck/Vitest)** | 72 tests passed, 0 errors | Pending | - |
| **Backend Test Suite (`pytest`)** | 350 passed, 0 `utcnow` warnings | Pending | - |
| **Playwright E2E** | 11 passed | Pending | - |
| **Full Verify Suite (`verify.ps1`)** | 8/8 checks passed | Pending | - |

---

## 4. Provenance & Git Tracking

| Field | Value |
|---|---|
| **Branch** | `step/22a-canonical-contract-ats` |
| **Pull Request** | Pending |
| **First Commit SHA** | Pending |
| **Last Commit SHA** | Pending |
| **Merge Commit SHA** | Pending |
