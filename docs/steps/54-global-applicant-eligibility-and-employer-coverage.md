# Step 54: Global Job Discovery, Country-Aware Eligibility & Direct Employer Coverage

**Date:** `2026-11-19`  
**Branch:** `step/54-global-applicant-eligibility-and-employer-coverage`  
**Pull Request:** https://github.com/richmondsogo/bottom-pot/pull/54 (`#54`)  
**First Commit SHA:** `75957f9`  
**Prior Step 54 Commits:** `75957f9`, `d27867e`, `e33b2c1`, `0b2a8a1`, `56d9ffd`, `47938b4`  
**Predecessor Merge (PR #53):** `c46280baa7b992c9aec18dfdc977818181330664` (`Merge pull request #53 from richmondsogo/step/53-global-source-discovery-audit`, verified against exact-head CI before branching)  
**Product Direction Established:** **Bottom Pot is global by design. Nigeria is a priority market and a first-class validation target, not a hard-coded eligibility boundary.**  
*(Global job discovery. Applicant-country-aware eligibility. Nigerian-first validation, not Nigerian-only coverage.)*

---

## 1. Executive Summary

Step 54 transformed Bottom Pot from a Nigeria-centric binary eligibility flag (`nigeria_eligible` / `auto_nigeria_eligible`) into a **global, applicant-country-aware discovery platform** backed by **10 independently verified direct employer boards** across **6 existing native ATS adapters**:

1. **Permanent Product Principle (`75957f9`)**: Codified across [`AGENTS.md`](../../AGENTS.md), [`CONTEXT.md`](../../CONTEXT.md), [`README.md`](../../README.md), [`docs/agents/PROJECT_COMPENDIUM.md`](../agents/PROJECT_COMPENDIUM.md), [`docs/job-source-catalog.md`](../job-source-catalog.md), and [`WhyDifferentSection.tsx`](../../frontend/src/components/marketing/WhyDifferentSection.tsx), while preserving all existing global-discovery, permission-gate, and rejected-provider cleanup rules.
2. **Global Applicant-Eligibility Foundation & API Projection (`d27867e`)**:
   - Added [`src/project_files/countries.py`](../../src/project_files/countries.py) with ISO 3166-1 alpha-2 country taxonomy (`190+` countries) and macro-region resolution (`Africa`, `Sub-Saharan Africa`, `EU`, `EEA`, `Europe`, `EMEA`, `LATAM`, `APAC`, `North America`, `Americas`, `MENA`, plus `Worldwide`).
   - Extended `JobEligibility` (`src/project_files/models.py`) and `eligibility_extractor.py` to separate **work arrangement**, **source geography**, **job geography**, and **applicant eligibility**, retain structured restriction evidence (`classification`, `allowed_country_codes`, `excluded_country_codes`, `allowed_regions`, `excluded_regions`, `work_authorization_required`, `visa_sponsorship_status`, `timezone_requirements`, `evidence_url`, `evidence_excerpt`, `source`, `confidence`, `verified_at`), and compute compatibility dynamically for any requested `applicant_country` (`GET /search`, `JobSearchQuery`, `ApplicantEligibilityAssessment`).
   - Replaced legacy Nigerian-only `auto_nigeria_eligible` coupling with backward-compatible evaluation via `evaluate_eligibility_for_country` (Section 3 documents the remaining legacy DB migration plan).
3. **Selectable Applicant Country UX (`e33b2c1`)**:
   - Added [`CountryCombobox.tsx`](../../frontend/src/components/CountryCombobox.tsx), [`frontend/src/lib/countries.ts`](../../frontend/src/lib/countries.ts), and [`frontend/src/lib/eligibility.ts`](../../frontend/src/lib/eligibility.ts) asking **"Where can you work from?"** without hardcoding a small country subset, inferring user location from network IP, or pretending eligibility is known when unset (`""`).
   - Updated filter controls (`All`, `Eligible for <Country>`, `Eligible or unverified`, `Restricted`), URL state, results table/cards, and `DetailSheet.tsx` to display **Work arrangement** and **Applicant eligibility** separately (e.g., `Remote · Worldwide`, `Remote · US only`, `Remote · Eligibility unverified`, `Hybrid · Lagos, Nigeria`), never displaying `Worldwide` without explicit supporting evidence.
4. **30-Posting Empirical Audit & Extractor Fixes (`0b2a8a1`)**:
   - Audited 30 real technical postings across 18 candidate boards against 11 representative countries (`NG`, `GH`, `KE`, `EG`, `GB`, `DE`, `US`, `CA`, `IN`, `SG`, `AU`) and fixed 7 production extraction bugs: `AMER` & `NAMER`/`NORAM` macro-regions overriding generic footer copy (`supabase`, `clickhouse`), humanitarian mission copy no longer triggering false `worldwide` (`givedirectly`), `require successful candidates to be located in ...` (`sourcegraph91`), Wikimedia `**US States**:` + `**Countries:**` footnote lists (`wikimedia`), markdown `**Location**: 100% remote (EMEA)` (`miaplaza`), multi-hub hybrid `;`-separated locations (`paystack`), and `UTC -1 to UTC +3` timezone parsing (`m-kopa`).
5. **Verified Direct Employer Coverage Across Existing 9 Native ATS Adapters (`56d9ffd`)**:
   - Spent **`0` Serper credits**, added **zero** new ATS adapters (`len(MONITORABLE_PROVIDERS) == 9` unchanged), used `OpenToAfrica` and `RemoteWork.ng` strictly as **`Discovery-only`** lead aggregators (respecting `robots.txt` and never copying listing content), evaluated candidate feeds across **67+ live probes**, selected **10** fresh, high-integrity direct employer boards spanning **6 existing ATS platforms**, persisted 11 real raw captures + [`evaluation_manifest.json`](../../tests/fixtures/real/step54_employers/evaluation_manifest.json), and implemented [`employer_board_catalog.py`](../../src/project_files/employer_board_catalog.py) + `BoardMonitor --seed-catalog`.

---

## 2. Preserved Historical Audit Context (Steps 52 & 53)

All historical findings from Steps 52 and 53 remain intact and unrevised:

- **Step 52 (`pinpointhq`)**: Across 123 broad technical roles inspected on Pinpoint feeds (`2026-11-19`), `75` were hybrid/onsite and `48` were labeled remote — **all `48/48` remote technical postings carried geographic restrictions**. In the balanced `30`-job Step 52 sample, `7/30` were eligible for Nigerian applicants (`0/7` core software/AI/data), while `14/30` were eligible in the wider African sample (with `6/6` African core tech roles restricted to Egypt). These remain bounded-sample observations, not claims about all employers or the global market.
- **Step 53 (Global Source Discovery Audit)**: Rejected `7` permission-violating or broken ATS providers (`jobscore`, `trakstar`, `polymer`, `gem`, `manatal`, `zohorecruit`, `seamlesshiring`), blocked `3` at gate (`dover`, `jobylon`, `factorialhr`), marked `ReliefWeb` `Permission pending`, and identified `OpenToAfrica` and `RemoteWork.ng` as **`Discovery-only`** leads wrapping employers already hosted on Bottom Pot's existing native ATS adapters.

---

## 3. Four-Dimensional Model Separation & Backward-Compatible Migration Plan

Bottom Pot strictly separates four independent dimensions across backend models, API responses, and UI presentation:

| Dimension | Definition | Representation / Constraint |
|---|---|---|
| **Work arrangement** | How the work is performed | `onsite` (normalized from `in_person`), `hybrid`, `remote`, `unknown`. Never equated with worldwide permission. |
| **Source geography** | Where the job board, ATS operator, or aggregator is based | Documented at source-catalog level; never used to infer applicant eligibility. |
| **Job geography** | Where the employer or role is physically hubbed or expected to operate | `physical_location_country`, `physical_location_country_code` (ISO-2), city/location string, multi-hub list. A remote role's employer country is not blindly turned into an applicant ban. |
| **Applicant eligibility** | Where an applicant may legally reside/work from and under what constraints | `JobEligibility` fields (`classification`, `allowed_country_codes`, `excluded_country_codes`, `allowed_regions`, `excluded_regions`, `work_authorization_required`, `visa_sponsorship_status`, `timezone_requirements`, `evidence_url`, `evidence_excerpt`, `source`, `confidence`, `verified_at`) evaluated per selected ISO-2 country via `evaluate_eligibility_for_country` -> `eligible` / `restricted` / `unknown`. |

### Legacy Migration Status & Remaining Plan

- **Current Backward-Compatible State**: Existing SQLite rows (such as `cache_store` / `monitored_jobs.canonical_json`) that store legacy `nigeria_eligible`, `allowed_residence_countries`, or `auto_nigeria_eligible` continue to evaluate dynamically without destructive database rewrites: `evaluate_eligibility_for_country` derives normalized ISO-2 sets on read via `split_countries_and_regions` when `allowed_country_codes`/`allowed_regions` are absent, and only trusts legacy `nigeria_eligible` when evaluating `NG` specifically.
- **Remaining Larger Migration (Future Dedicated Step)**:
  1. Rename `/search` internal legacy query parameter `auto_nigeria_eligible` to a neutral parameter once any external callers/scripts are audited and updated, keeping API alias compatibility through a deprecation window.
  2. Introduce an additive idempotent background backfill utility (never auto-run on operational startup or inside `_ensure_db()`) to populate structured `JobEligibility` fields (`allowed_country_codes`, `allowed_regions`, `verified_at`) from stored raw job descriptions on operational snapshots when explicitly authorized by an operator.
  3. Extend regional-vs-national distinction where sub-national states (e.g., US state lists on Wikimedia or Canadian Québec exclusions on Grafana Labs) affect domestic eligibility.

---

## 4. Direct Employer Discovery, 30-Posting Audit & Extractor Fixes

### 4.1 Discovery Leads (`0` Serper Credits, `robots.txt` Checked)

Following Step 53, `OpenToAfrica` and `RemoteWork.ng` were inspected strictly as **discovery leads** (0.35s delay, max 15 internal detail pages per site, zero listing text copied) solely to extract outbound primary ATS URLs via `parse_ats_url`:

- **`OpenToAfrica`** (`robots.txt` HTTP `200`, `can_fetch=True`; homepage `200`, `sitemap.xml` `200` with `326` internal URLs; `/jobs` `404`): 15 sampled detail pages + homepage direct links yielded **`13`** unique ATS board tokens (`ashby:buffer`, `ashby:camunda`, `ashby:circle`, `ashby:clickhouse`, `ashby:constructor`, `ashby:keyrock`, `ashby:m-kopa`, `ashby:qdrant.tech`, `ashby:supabase`, `ashby:talentsafari`, `ashby:thndr`, `greenhouse:canonical`, `greenhouse:givedirectly`), alongside previously noted `workable:fairmoney`. Four (`supabase`, `qdrant.tech`, `m-kopa`, `thndr`) plus `fairmoney` passed primary evaluation and were promoted to the catalog.
- **`RemoteWork.ng`** (`/jobs` HTTP `200` with `23` internal URLs, `sitemap.xml` `200`; `robots.txt` errored/empty): 15 sampled detail pages yielded **`3`** direct ATS tokens (`ashby:aptura`, `ashby:bjakcareer`, `lever:weloglobal`). All three failed independent promotion criteria (`bjakcareer`: 1,610 rows fanned from 172 replicated titles; `aptura`: freelance domain-expert AI eval gigs; `weloglobal`: freelance crowd-annotation tasks, median age `203.5d`).

### 4.2 Manual 30-Posting Audit & Step C Fixes (`0b2a8a1`)

Inspecting 30 real technical postings exposed 7 real-world failure modes resolved in `0b2a8a1`:

1. **`AMER` / `NAMER` / `NORAM` Macro-Regions (`ashby:supabase`, `ashby:clickhouse`)**: `Remote, AMER` and `NAMER and LatAm` lacked region aliases, allowing generic footer boilerplate (`"We hire globally. We believe you can do your best work from anywhere."`) to misclassify Supabase's `Customer Solution Architect (AMER)` as `worldwide` (`NG=eligible` pre-fix -> `region_restricted` / `NG=restricted` post-fix).
2. **Humanitarian/Mission Copy (`greenhouse:givedirectly`)**: `"getting cash to disaster-affected communities within 5 days of a crisis—anywhere in the world"` falsely marked a restricted posting `worldwide` despite `"You must be based in one of the countries on this list"` (`worldwide` -> `work_auth_disclosed`, `NG=unknown`).
3. **Qualified Residency Infinitive (`greenhouse:sourcegraph91`)**: `"we do require successful candidates to be located in the United States"` missed existing patterns because of `require` + `successful` (`unknown` -> `country_restricted` [`US`]).
4. **Explicit Hiring Country Tables (`greenhouse:wikimedia`)**: `*Please note that we are currently able to hire in the following: **US States**: ... **Countries:** Brazil, ... Ghana, ... Kenya*, ... South Africa, ...` missed because of bold-tag colon placement and `*` footnote markers (`unknown` -> `country_restricted` across 18 countries + `US`; `GH/KE/DE/GB/US/CA/IN/SG=eligible`, `NG=restricted`).
5. **Markdown Parenthesized Region (`recruitee:miaplaza`)**: `**Location**: 100% remote (EMEA)` missed parenthesized macro-region after `100% remote` (`unknown` -> `region_restricted` [`EMEA`], `US=restricted`).
6. **Multi-Hub Hybrid Offices (`teamtailor:paystack`)**: `Lagos, Nigeria; Nairobi, Kenya; Cape Town, South Africa` previously extracted only the first hub (`NG`); now extracts all explicit hubs (`NG`, `KE`, `ZA`), raising Kenyan hub visibility from `0` to `1`.
7. **UTC Offset Ranges (`ashby:m-kopa`)**: Added `UTC -1 to UTC +3` timezone extraction (`timezone_requirements`).

*(Frontend parity updated identically in [`frontend/src/lib/countries.ts`](../../frontend/src/lib/countries.ts) for `amer`, `namer`, `noram`.)*

---

## 5. Selected 10 Verified Direct Employer Boards (Within Existing 9 `MONITORABLE_PROVIDERS`)

All 10 promoted boards run through existing native `BOARD_ADAPTERS` across **6** existing ATS platforms (**zero** new ATS adapters added):

| Employer | ATS Provider & Token | Discovery Lead | Raw -> Canonical Unique | Unique Tech | Tech Classifications (`WW / CR / RR / Local / Unk`) | Freshness Median (`<=30d`) | 304 / Feed |
|---|---|---|---|---|---|---|---|
| **Supabase** | `ashby:supabase` | OpenToAfrica direct ATS | `78 -> 78` | `33` | `25 / 3 / 5 / 0 / 0` | `39.1d` (`35`) | Yes (`ETag` / `304`) |
| **Qdrant** | `ashby:qdrant.tech` | OpenToAfrica detail | `10 -> 10` | `6` | `0 / 5 / 0 / 0 / 1` | `14.3d` (`8`) | Yes (`ETag` / `304`) |
| **M-KOPA** | `ashby:m-kopa` | OpenToAfrica detail | `50 -> 50` | `6` | `0 / 0 / 0 / 0 / 6` | `13.4d` (`47`) | Yes (`ETag` / `304`) |
| **Thndr** | `ashby:thndr` | OpenToAfrica detail | `18 -> 18` | `8` | `0 / 0 / 0 / 5 / 3` | `25.9d` (`10`) | Yes (`ETag` / `304`) |
| **FairMoney** | `workable:fairmoney` | OpenToAfrica direct ATS | `59 -> 25` | `3` | `0 / 0 / 0 / 3 / 0` | `37.8d` (`10`) | Fingerprint / v2 details |
| **Paystack** | `teamtailor:paystack` | Africa fintech seed | `24 -> 24` | `3` | `0 / 2 / 0 / 1 / 0` | `43.9d` (`11`) | Yes (`ETag` / `304` RSS) |
| **Wikimedia Foundation** | `greenhouse:wikimedia` | Global remote seed | `16 -> 16` | `4` | `0 / 4 / 0 / 0 / 0` | `36.4d` (`4`) | Yes (`ETag` / `304`) |
| **Grafana Labs** | `greenhouse:grafanalabs` | Global remote seed | `138 -> 138` | `68` | `0 / 68 / 0 / 0 / 0` | `30.5d` (`69`) | Yes (`ETag` / `304`) |
| **Spotify** | `lever:spotify` | EU/global tech benchmark | `92 -> 92` | `35` | `0 / 0 / 0 / 15 / 20` | `44.2d` (`34`) | Yes (`ETag` / `304`) |
| **Miaplaza** | `recruitee:miaplaza` | US/EU benchmark | `7 -> 7` | `4` | `0 / 0 / 1 / 0 / 3` | `12.8d` (`5`) | Offers API JSON |

---

## 6. Global vs Nigeria vs Wider Africa Bounded-Sample Evaluation

All figures below come directly from offline replay of the **10 selected boards** in [`tests/fixtures/real/step54_employers/evaluation_manifest.json`](../../tests/fixtures/real/step54_employers/evaluation_manifest.json) (captured `2026-11-19`):

- **Total Active Snapshot**: `492` raw adapter emissions -> **`458` canonical unique active postings** (`34` Workable city replicates on `fairmoney` deduplicated cleanly by `job_id`; `1` cross-entry same company/title/location collision).
- **Unique Technical Roles**: **`170`** (`37.1%` of `458`).
  - **Work arrangement (tech)**: `141` `remote`, `25` `hybrid`, `1` `onsite`, `3` `unknown`.
  - **Applicant-eligibility classification (tech)**: **`25` `worldwide`**, `82` `country_restricted`, `6` `region_restricted`, `24` `onsite_or_hybrid_local`, `33` `unknown`. Notice: **`116` of `141` remote technical postings were NOT worldwide** — `82` country-restricted, `6` region-restricted, and `28+` unverified/unknown, reinforcing that `remote != worldwide`.
- **Freshness (`458/458` = `100%` dated)**: median **`29.5` days** (`233` within `30` days = `50.9%`; `319` within `60` days = `69.7%`; max `735.1` days).
- **Seniority (technical `170`)**: `125` senior+ (`73.5%`), `45` mid/unspecified (`26.5%`), **`0` intern/graduate, `0` junior** explicitly titled in this 10-board snapshot (an honest coverage limitation for Step 55 follow-up).

### Representative 11-Country Technical & Total Eligibility Breakdown (No Overlapping Double Counts)

*Nigeria (`NG`) is reported strictly separately from global totals and from non-Nigeria Africa (`GH`, `KE`, `EG`) outcomes:*

| Applicant Country | ISO-2 | All Unique Active (`458`) Eligible / Restricted / Unknown | Unique Technical (`170`) Eligible / Restricted / Unknown | Key Verified Technical Sources |
|---|---|---|---|---|
| **Nigeria (Priority Market)** | `NG` | `87 / 219 / 152` | **`29 / 84 / 57`** | `25` worldwide (Supabase) + `2` FairMoney (Lagos/Abuja) + `2` Paystack (Lagos hubs) |
| **Ghana** | `GH` | `73 / 209 / 176` | **`30 / 80 / 60`** | `25` Supabase + `4` Wikimedia + `1` Paystack |
| **Kenya** | `KE` | `74 / 209 / 175` | **`30 / 80 / 60`** | `25` Supabase + `4` Wikimedia + `1` Paystack (multi-hub) |
| **Egypt** | `EG` | `59 / 229 / 170` | **`30 / 85 / 55`** | `25` Supabase + **`5` Thndr (Cairo)** — Egypt-specific, NOT Nigerian |
| **United Kingdom** | `GB` | `103 / 201 / 154` | **`49 / 72 / 49`** | Supabase + Wikimedia + Grafana Labs + Spotify London (`12`) |
| **Germany** | `DE` | `79 / 202 / 177` | **`38 / 75 / 57`** | Supabase + Qdrant (`3`) + Wikimedia (`4`) + Grafana Labs (`6`) |
| **United States** | `US` | `142 / 144 / 172` | **`53 / 57 / 60`** | Supabase (`27`) + Qdrant + Wikimedia + Grafana Labs (`21`) |
| **Canada** | `CA` | `78 / 195 / 185` | **`42 / 68 / 60`** | Supabase (`25`) + Wikimedia (`4`) + Grafana Labs (`13`) |
| **India** | `IN` | `67 / 214 / 177` | **`29 / 84 / 57`** | Supabase (`25`) + Wikimedia (`4`) |
| **Singapore** | `SG` | `63 / 216 / 179` | **`29 / 84 / 57`** | Supabase (`25`) + Wikimedia (`4`) |
| **Australia** | `AU` | `49 / 230 / 179` | **`25 / 88 / 57`** | Supabase (`25` worldwide) |

- **Deduplicated Sampled-Africa Aggregate (never summed linearly across columns)**: **`39`** unique technical roles are eligible in **at least one** of the four sampled African countries (`NG`, `GH`, `KE`, `EG`). **`10`** of those `39` are **not** Nigeria-eligible (`5` Cairo-specific Thndr roles + `4` Wikimedia EOR roles in `GH`/`KE` excluding `NG` + `1` Paystack hub role outside `NG`).
- **Bounded-Sample Caveat**: This 10-board catalog measures 10 deliberately selected direct employers on `2026-11-19`, not the entire hiring universe or every employer on any ATS platform. Roles marked `unknown` (`57` for Nigeria) require applicant verification (e.g., M-KOPA's `6` `UTC-1..+3` engineering roles split across UK/EU and Lagos/Nairobi hubs where location strings omit explicit residency statements).

---

## 7. Rejected & Unselected Candidate Summary

Notable candidates inspected and deliberately **not** promoted:

- **`ashby:bjakcareer`** (`1,610` rows / `17.75 MB`): Replicated `172` job descriptions fanned across ~`23–32` city/country combinations each (`27` exact dups, spammy board replication).
- **`greenhouse:canonical`** (`317` jobs / `3.45 MB`): Severely stale backlog (**median `862.1` days**; only `10/317` within 30 days, open requisitions from `2021`), despite accurate post-fix `worldwide`/`regional` phrasing on its subset of home-based roles.
- **`lever:weloglobal`** (`452` jobs): Freelance crowd AI-annotation vendor tasks with stale median age (**`203.5` days**).
- **`ashby:aptura`** (`38` jobs): Short-term task-based financial/medical AI-eval gigs rather than direct software engineering employment.
- **`smartrecruiters:wise`** (`438` jobs): List API pass delivered only **`4.6%`** description completeness.
- **`pinpointhq:indrive`** & **`pinpointhq:sunking`**: Already audited in Step 52 under **`Constrained`** (Pinpoint APIs omit publication dates cleanly).
- **`greenhouse:elastic`** (`6.88 MB`, `176/188` tech undisclosed), **`ashby:clickhouse`** (`22` dups, `91/113` undisclosed), **`greenhouse:gitlab`** (`3.79 MB`, `0` Africa tech), **`greenhouse:twilio`** (`10` dups, `0` Africa tech), **`greenhouse:givedirectly`** (`2` tech, external PerfectWiki country list), **`ashby:talentsafari`** (agency pool, `2` tech), plus `15+` HTTP `404`/empty/invalid probes (`airbyte`, `dbtlabsinc`, `flutterwave`, `andela`, `qdrant` -> resolved via `qdrant.tech`, `hotjar`, `doist`, `cohere`, `kuda`, etc.).

---

## 8. Catalog Seeding, Safety & Verification Evidence

- **Catalog & CLI (`56d9ffd`)**: Added [`src/project_files/employer_board_catalog.py`](../../src/project_files/employer_board_catalog.py) (`CuratedEmployerBoard`, `VERIFIED_EMPLOYER_BOARDS`, `seed_verified_employer_boards`) and `BoardMonitor.seed_curated_boards()` + `python -m src.project_files.board_monitor --seed-catalog` inside `cli_operational_runtime(...)` (never auto-seeded inside `_ensure_db()`).
- **Offline Regression Tests ([`tests/test_employer_board_catalog.py`](../../tests/test_employer_board_catalog.py))**: Validates catalog invariants, SHA-256 fixture matching, idempotent DB seeding, ADR 0030 fail-closed CLI guards against `data/cache.sqlite`, full offline `BoardMonitor.check_single_board` replay of all 10 boards (including `workable:fairmoney` `59 -> 25` deduplication via `workable_fairmoney_details.json`), `ETag`/`304`, fail-closed non-closure across `301`/`403`/`404`/`429`/`500`/malformed responses, and 11-country eligibility checks.
- **Protected Operational Database Integrity (ADR 0030)**: Verified before, during, and after Step 54 execution against `scratch/db_baseline_step54.json`: all 9 files inside `data/` (including `data/cache.sqlite`, `14,016,512` bytes, SHA-256 `a7c88bb24d383813213342ea1a0990f0c7bf62b4c1308647fc18f834be028638`) kept identical byte sizes and SHA-256 digests (`DB_MATCH: True`), and `subscriptions.csv` remained absent (`SUBS_EXISTS: False`).

---

## 9. Step 55 Recommendation

1. **Direct Early-Career & Intern/Graduate Board Discovery (On Existing 9 ATS Adapters)**: Step 54's 10-board catalog yielded `125` senior+ and `45` mid/unspecified technical roles, but `0` explicit intern/graduate/junior titles. Step 55 should specifically audit direct employer boards with active internship/new-grad engineering requisitions (and multi-country EOR/distributed contractor support) on Greenhouse, Lever, Ashby, Recruitee, and Teamtailor — rather than adding a 10th ATS provider.
2. **Legacy Snapshot Eligibility Migration & Region/Sub-National Refinement**: Follow up on the remaining migration plan in Section 3 (backfill structured `JobEligibility` fields safely offline/via operator utility, plus expose sub-national state/province disclaimers cleanly where employers list specific states alongside international countries).
