# Step 55: Global Remote & Early-Career Employer Coverage

**Date:** `2026-11-21`  
**Branch:** `step/55-global-remote-and-early-career-coverage`  
**Base Commit (`main` / PR #54 Merge SHA):** `6308791e15a76e4dc3f2656fdc47ed935be2b477`  
**Permanent Product Principle:** **Global job discovery. Applicant-country-aware eligibility. Nigerian-first validation, not Nigerian-only coverage.**

---

## 1. Executive Summary

Step 54 established Bottom Pot's 4-dimension global eligibility architecture and an initial 10-board catalog (`458` canonical unique active jobs, `170` technical under Step 54's filter), but left two severe market-coverage gaps:

1. **Extreme source concentration on worldwide & Nigeria-eligible remote tech**: `Supabase` accounted for `25/25` (`100.0%`) of Step 54's worldwide technical roles and `25/29` (`86.2%`) of its Nigeria-eligible technical roles, leaving only `4` Nigeria-eligible roles (`FairMoney` `2`, `Paystack` `2`) outside `Supabase`.
2. **Missing early-career coverage**: Step 54's published snapshot recorded `0` explicit intern, graduate, or junior technical titles (`125` senior+, `45` mid/unspecified; re-evaluating `greenhouse_wikimedia.json` with an inclusive filter finds `1` 2027 SWE internship).

Step 55 audited all Step 54 baseline classifications live, fixed **4** real-world extraction/adapter bugs uncovered during the audit, evaluated global direct-employer boards across **9** existing ATS providers (spending **`0` Serper credits** and adding **zero** new ATS providers), captured verified raw fixtures for **10 newly promoted direct employer boards** under [`tests/fixtures/real/step55_employers/`](../../tests/fixtures/real/step55_employers/evaluation_manifest.json), expanded [`VERIFIED_EMPLOYER_BOARDS`](../../src/project_files/employer_board_catalog.py) from `10` to **`20` verified boards**, and validated all **7** required user countries (`NG`, `DE`, `US`, `IN`, `CA`, `GH`, `EG`) in Playwright E2E without any forced Nigeria default.

---

## 2. Step 54 Live Audit & Source Concentration Baseline

### 2.1 Verification of the 25 Worldwide Supabase Roles (Section 3.1)

Inspecting the captured `ashby_supabase.json` fixture (`78` jobs) and live Supabase Ashby feed (`2026-11-21`):

- **25/25 verified true positives (plus 2 additional IC engineering roles under Step 55's broader filter = 27)**: All 25 Step 54 Supabase worldwide technical roles (plus `Developer Relations Engineer` and `SDK Engineer - Python`) carry structured `location: "Remote, Global"`, empty `secondaryLocations`, `workplaceType: "Remote"`, live active status, `HTTP 200` apply URLs, and explicit description confirmation (`"We hire globally. We believe you can do your best work from anywhere. There are no Supabase offices..."`) with zero contradicting residency/country bans. They are retained as genuinely worldwide and eligible across Nigeria and all other sampled countries.
- **False-positive non-tech edge case fixed**: Supabase's non-technical `Dev Experiences and Community Lead (SF)` carried physical `location: "San Francisco, CA, US"` (`workplaceType: None`) yet was previously misclassified `worldwide` because Supabase's uppercase plain-text `"WHAT WE OFFER"` section heading bypassed `_HEADING_SCAN_RE`, allowing perks copy to override a city/state physical location.

### 2.2 Live Revalidation of FairMoney & Paystack (Section 3.2)

- **FairMoney (`workable:fairmoney`)**: Live widget returned `HTTP 200` (`63` raw / `27` unique shortcodes on `2026-11-21`, vs `59` / `25` in the Step 54 fixture) with `200 OK` apply links. Auditing the Step 54 fixture exposed a bug: `Senior Software Engineer-Lending` (`442ECC72EF`) had `location: "İstanbul, Turkey | Lagos, Nigeria"` (`hybrid`), leaving `NG=unknown` because `eligibility_extractor.py` only split multi-hub strings on `;` and ignored pipe (`|`) delimiters and Workable `raw_fields["locations"]`.
- **Paystack (`teamtailor:paystack`)**: Live RSS returned `HTTP 200` (`24` items, apply links `200`). Auditing the Step 54 XML exposed a major bug: `_format_tt_rss_locations` truncates `location` at 80 characters with `(+N more)` while `raw_location` preserved full hubs. Because `extract_eligibility` only parsed truncated `location`:
  - `Senior Database Administrator` (`Cape Town, South Africa; Accra, Ghana; Dubai, UAE (+3 more)` — raw XML contains `Lagos, Nigeria`, `Nairobi, Kenya`, `Abidjan, Côte d'Ivoire`) was marked **falsely restricted** for `NG` and `KE`.
  - `Senior DevOps Engineer` (`Accra, Ghana; Cape Town, South Africa; Dubai, UAE (+2 more)` — raw XML contains `Lagos, Nigeria`, `Nairobi, Kenya`) was marked **falsely restricted** for `NG` and `KE`.
  - `Data Science Lead` and `QA Lead` similarly lost downstream hubs (`KE`, `GH`) behind `(+2 more)`.
- **Historical snapshot integrity**: [`54-global-applicant-eligibility-and-employer-coverage.md`](54-global-applicant-eligibility-and-employer-coverage.md) is preserved untouched as the dated `2026-11-19` Step 54 snapshot.

### 2.3 Step 54 Baseline Source Concentration (Section 3.3)

| Metric | Step 54 Published Snapshot | Step 54 Recomputed With Step 55 Fixes & Inclusive Filter |
|---|---|---|
| Nigeria-eligible tech roles | `29` (`25` Supabase, `2` FairMoney, `2` Paystack) | `37` (`27` Supabase, `7` Paystack, `3` FairMoney) |
| Distinct NG tech employers | `3` | `3` |
| Largest employer share (NG) | **`86.2%`** (`Supabase`) | **`73.0%`** (`Supabase`) |
| Top-3 share (NG) | **`100.0%`** | **`100.0%`** |
| NG roles outside largest employer | **`4`** (`13.8%`) | **`10`** (`27.0%`) |
| Worldwide tech roles | `25` (`25` Supabase) | `27` (`27` Supabase) |
| Distinct WW tech employers | `1` | `1` |
| Largest employer share (WW) | **`100.0%`** (`Supabase`) | **`100.0%`** (`Supabase`) |
| WW roles outside largest employer | **`0`** (`0.0%`) | **`0`** (`0.0%`) |

---

## 3. Extractor & Adapter Fixes Implemented

1. **Preserve full multi-hub location arrays (`src/project_files/board_adapters.py`)**: Added `_extract_tt_rss_location_list` and `_extract_personio_location_list` so Teamtailor RSS and Personio XML feeds keep the untruncated `raw_fields["all_locations"]` list even when compact display strings truncate with `(+N more)`.
2. **Multi-hub `|`/structured resolution (`src/project_files/eligibility_extractor.py`, `frontend/src/lib/eligibility.ts`)**: Added `_extract_country_from_location_segment`, `_collect_multihub_countries`, and `(+N more)` stripping across Teamtailor `all_locations`, Workable `locations`, and `[;|]`-delimited strings, restoring Paystack's 7 NG tech hubs and FairMoney's `Senior Software Engineer-Lending`.
3. **Ashby multi-country remote `secondaryLocations` (`src/project_files/eligibility_extractor.py`)**: Added `_collect_remote_structured_geos` (with strict country/macro-region validation on every token) plus delimited segment resolution (`Slovakia (Remote)`, etc.) so remote multi-country hiring boards like `Kraken` and `DuckDuckGo` produce accurate `country_restricted` eligibility lists without ever turning single-country bare HQ locations into restrictions.
4. **Plain-text `"WHAT WE OFFER"` & physical city/hybrid guard (`src/project_files/eligibility_extractor.py`)**: Extended `_PERKS_CULTURE_HEADING_RE` and `_HEADING_SCAN_RE` to detect standalone `"WHAT WE OFFER"` lines, and blocked description-level global-remote phrases from overriding `onsite`, `hybrid`, or city-locked physical locations without remote markers.

---

## 4. Candidate Discovery, Permission Gate & Rejections

- **Discovery channels (`0` Serper credits)**: Used existing `Discovery-only` leads (`OpenToAfrica`, `RemoteWork.ng`, `US-RSE`, `Python.org` — zero listing text republished) plus direct public career portals across North/West/East/Southern Africa, Europe, North America, LATAM, APAC, and remote-first infrastructure companies (`300+` ATS probes screened; `30+` finalist boards deeply inspected with `>= 10` jobs where available).
- **Permission & `robots.txt` Gate (Section 8)**:
  - `boards-api.greenhouse.io/robots.txt`: Allows `/v1/boards/{slug}/jobs` (`Disallow: /embed/` only).
  - `api.lever.co/robots.txt`: `Allow: /` (`Crawl-delay: 1`).
  - `jobs.ashbyhq.com/robots.txt`: Public Posting API (`api.ashbyhq.com/posting-api/job-board/{slug}`) officially documented for external job boards.
  - `apply.workable.com/robots.txt`: `Content-Signal: search=yes, ai-input=yes, ai-train=no`; empty `Disallow:`.
  - `{slug}.recruitee.com`, `{slug}.teamtailor.com`, `{slug}.jobs.personio.com`, `{slug}.pinpointhq.com`: Permit public `/api/offers/`, `/jobs.rss`, `/xml`, `/postings.json`.
  - **`smartrecruiters` (`api.smartrecruiters.com/robots.txt`)**: Serves `User-agent: LinkedInBot Allow: /v1/companies/` and **`User-agent: * Disallow: /`** — all SmartRecruiters candidates excluded at permission gate.
- **Representative Declined Candidates (With Concrete Reasons)**:
  - `ashby:onhires`: Recruiting agency hiring on behalf of third-party clients rather than direct employer openings.
  - `greenhouse:pinterest`: Apply URLs returned `HTTP 403` during live link check.
  - `greenhouse:mthree`: Hire-train-deploy consultancy model with stale evergreen requisitions (`836–900d`).
  - `greenhouse:figma` & `greenhouse:duolingo`: High early-career counts (`4–7` tech), but `0` disclosed work models (`all cls=unknown`).
  - `personio:ultralytics` (`679.9d` median) & `recruitee:holepunch` (`246.8d` median): Severely stale boards.
  - `ashby:linear` (`211.2d`, `0` early-career, `0` WW tech), `ashby:render` (`US/CA` only), `greenhouse:vercel` (`29/31` unknown), `ashby:livekit` (`hybrid` SF false global fixed): Inferior incremental yield vs selected 10.
  - `greenhouse:stripe` (`6.1 MB`), `greenhouse:cloudflare` (`9.0 MB`), `greenhouse:databricks` (`9.8 MB`), `greenhouse:agoda` (`7.4 MB`), `greenhouse:palantir` (`6.0 MB`), `greenhouse:snowflake` (`4.9 MB`), `greenhouse:tether` (`5.3 MB`), `greenhouse:airwallex` (`8.3 MB`), `greenhouse:gitlab` (`3.75 MB`), `greenhouse:sumup` (`3.33 MB`), `greenhouse:okx` (`8.07 MB`): Exceed `MAX_RESPONSE_BYTES` (`3.15 MB`) stream cap.

---

## 5. Selected 10 Newly Promoted Direct Employer Boards (`20` Total Catalog)

All `10` new boards run strictly on existing native `BOARD_ADAPTERS` (`ashby`, `greenhouse`, `lever`, `workable`), returning `HTTP 200` on their official careers pages and `[200, 200]` on sampled live apply URLs:

| Employer | Native ATS | Official Careers (`HTTP 200`) | Unique / Tech | WW Tech | Early Tech (`Int / Grad / Jr`) | Median Age (`<=30d`) | Key Value Added |
|---|---|---|---|---|---|---|---|
| **Metabase** | `lever:metabase` | `metabase.com/jobs` | `21` / `9` | `6` | `0` (`0/0/0`) | `325.7d` (`2`) | Objective A: `6` explicit `Global Remote` engineering roles (`ETag`/`304`); evergreen Lever timestamps noted |
| **Railway** | `ashby:railway` | `railway.com/careers` | `7` / `7` | `6` | `0` (`0/0/0`) | `476.7d` (`0`) | Objective A: `6` explicit `Global` ("anywhere in the world") infra/product roles (`2` posted mid-2026 alongside long-open roles) |
| **Whippy** | `ashby:whippy` | `whippy.ai` | `26` / `8` | `0`* | `2` (`1/1/0`) | `11.2d` (`18`) | Objectives A & B: ultra-fresh (`4.9d`) Dublin Intern & New-Grad FDE roles + `1` WW EM & `1` WW Designer (outside IC filter) |
| **DuckDuckGo** | `ashby:duck-duck-go` | `duckduckgo.com/hiring` | `10` / `6` | `0` | `0` (`0/0/0`) | `40.8d` (`2`) | Objective A: explicit `25–30` country remote hiring lists (`ZA 4, GB 4, CA 4, US 5, IN 1, SG 3`; cleanly excludes `NG`) |
| **Kraken** | `ashby:kraken.com` | `kraken.com/careers` | `93` / `36` | `0` | `0` (`0/0/0`) | `24.8d` (`51`) | Objective A: fresh structured multi-country remote lists via `secondaryLocations` (`ZA 20`, `CA 10`, `GB`, `EU`, `LATAM`, `UAE`) |
| **Kuda** | `workable:kuda` | `kuda.com/careers/` | `5` (`7` raw) / `2` | `0` | `0` (`0/0/0`) | `50.4d` (`0`) | Objective A: Nigerian (`Lagos`/`Abuja`) & South African fintech coverage (`7 -> 5` dedup; widget + `v2` details) |
| **Electrum** | `workable:electrum` | `electrumsoftware.com/careers` | `5` / `5` | `0` | `2` (`1/1/0`) | `51.4d` (`1`) | Objectives A & B: Cape Town payments-tech (`ZA 5`, `NG restricted`) incl. `2027 Graduate Programme` & `Summer Internship` |
| **Affirm** | `greenhouse:affirm` | `affirm.com/careers` | `222` / `144` | `0` | `11` (`2/0/9`) | `35.7d` (`98`) | Objective B: fresh NA/UK early-career (`Remote Canada` & `Remote US` `Software Engineer I`, London, Intern; `304`) |
| **Lyft** | `greenhouse:lyft` | `lyft.com/careers` | `148` / `58` | `0` | `15` (`15/0/0`) | `45.5d` (`67`) | Objective B: `15` fresh Summer 2027 SWE, Data Engineering, and PhD/ML Internships across `CA` and `US` (`304`) |
| **Almedia** | `ashby:almedia` | `almedia.co/careers` | `28` / `12` | `0` | `3` (`0/0/3`) | `46.4d` (`7`) | Objective B: fresh Berlin explicit `Junior Software Engineer - Data`, `Junior Data Scientist`, and `Junior Engineer` (`DE 11`) |

*\*Note: `Whippy` also lists `1` `Remote - Worldwide` Software Engineering Manager and `1` `Remote - Worldwide` Product Designer outside the strict IC technical subset.*

---

## 6. Reproducible Before / After Comparison (`evaluation_manifest.json`)

All figures come directly from offline replay in [`tests/fixtures/real/step55_employers/evaluation_manifest.json`](../../tests/fixtures/real/step55_employers/evaluation_manifest.json) (captured `2026-11-21`). Because Step 54's dated snapshot (`170` tech) used a slightly narrower regex than Step 55's inclusive technical filter (`185` on those same 10 fixtures), both Step 54's published baseline AND Step 54 recomputed under the identical Step 55 pipeline/filter are shown:

### 6.1 Global Totals, Career Stages, Classifications, Freshness & Concentration

| Dimension | Step 54 Published (10 Boards) | Step 54 Recomputed w/ Step 55 Fixes (10 Boards) | Step 55 New 10 Boards Only | Combined 20-Board Catalog |
|---|---|---|---|---|
| Raw -> Canonical Unique Active | `492 -> 458` (`34` removed) | `492 -> 458` (`34` removed) | `567 -> 565` (`2` removed) | **`1,059 -> 1,023`** (`36` removed) |
| Cross-board Title+Company+Loc Dups | `1` | `1` | `3` | `4` |
| Unique Technical Roles | `170` | `185` | `287` | **`472`** |
| Work Models (Tech: Remote/Hybrid/Onsite/Unk) | `141 / 25 / 1 / 3` | `150 / 30 / 2 / 3` | `114 / 54 / 22 / 97` | `264 / 84 / 24 / 100` |
| Classifications (Tech: WW/CR/RR/Local/Auth/Unk) | `25 / 82 / 6 / 24 / 0 / 33` | `27 / 86 / 16 / 25 / 0 / 31` | `12 / 180 / 2 / 75 / 2 / 16` | **`39`** / `266` / `18` / `100` / `2` / `47` |
| Early-Career Tech (`Intern / Grad / Junior`) | `0` (`0 / 0 / 0`) | `1` (`1 / 0 / 0`) | **`33`** (`19 / 2 / 12`) | **`34`** (`20 / 2 / 12`) |
| Experienced Tech (`Senior+ / Mid or Unspec`) | `170` (`125 / 45`) | `184` (`119 / 65`) | `254` (`171 / 83`) | `438` (`290 / 148`) |
| Freshness (`Dated / Median / <=30d / <=90d`) | `458` / `29.5d` / `233` / — | `458` / `31.0d` / `218` / `374` | `565` / `36.7d` / `246` / `452` | `1,023` / `33.1d` / `464` / `826` |
| Nigeria-Eligible Tech (`Largest Employer Share`) | `29` (`86.2%` Supabase, `3` emp) | `37` (`73.0%` Supabase, `3` emp) | `14` (`3` emp) | **`51`** (**`52.9%`** Supabase, **`6`** emp) |
| NG Tech Outside Largest Employer (Top-3 Share) | `4` (`100.0%`) | `10` (`100.0%`) | `14` | **`24`** (**`78.4%`**) |
| Worldwide Tech (`Largest Employer Share`) | `25` (`100.0%` Supabase, `1` emp) | `27` (`100.0%` Supabase, `1` emp) | `12` (`Metabase 6, Railway 6`) | **`39`** (**`69.2%`** Supabase, **`3`** emp) |
| WW Tech Outside Largest Employer | `0` | `0` | `12` | **`12`** |

### 6.2 Representative 12-Country Technical Eligibility Breakdown (Before vs After)

*(No cross-country double counting; conservative `unknown` preserved wherever eligibility is undisclosed.)*

| Applicant Country | ISO-2 | Step 54 Published Tech Elig (`170`) | Step 54 Recomputed Tech Elig/Restr/Unk (`185`) | Combined 20-Board Tech Elig/Restr/Unk (`472`) | Combined All-Active Elig/Restr/Unk (`1,023`) |
|---|---|---|---|---|---|
| **Nigeria (Priority Market)** | `NG` | `29` | `37 / 91 / 57` | **`51 / 295 / 126`** | `114 / 568 / 341` |
| **Ghana** | `GH` | `30` | `35 / 90 / 60` | **`47 / 294 / 131`** | `93 / 562 / 368` |
| **Kenya** | `KE` | `30` | `37 / 89 / 59` | **`49 / 293 / 130`** | `96 / 559 / 368` |
| **South Africa** | `ZA` | — *(added in Step 55)* | `37 / 88 / 60` | **`78 / 263 / 131`** | `135 / 521 / 367` |
| **Egypt** | `EG` | `30` | `33 / 98 / 54` | **`45 / 302 / 125`** | `77 / 584 / 362` |
| **United Kingdom** | `GB` | `49` | `50 / 85 / 50` | **`87 / 264 / 121`** | `175 / 501 / 347` |
| **Germany** | `DE` | `38` | `40 / 88 / 57` | **`64 / 279 / 129`** | `120 / 532 / 371` |
| **United States** | `US` | `53` | `58 / 66 / 61` | **`160 / 204 / 108`** | `358 / 365 / 300` |
| **Canada** | `CA` | `42` | `42 / 80 / 63` | **`146 / 219 / 107`** | `269 / 429 / 325` |
| **India** | `IN` | `29` | `32 / 94 / 59` | **`46 / 296 / 130`** | `88 / 563 / 372` |
| **Singapore** | `SG` | `29` | `31 / 95 / 59` | **`46 / 296 / 130`** | `85 / 566 / 372` |
| **Australia** | `AU` | `25` | `27 / 99 / 59` | **`40 / 302 / 130`** | `68 / 583 / 372` |

- **Deduplicated 5-Country Sampled-Africa Union (`NG`, `GH`, `KE`, `ZA`, `EG`)**: **`91`** unique technical roles are eligible in at least one of the 5 sampled African countries (up from `48` recomputed / `39` published on the 4-country Step 54 sample), and **`40`** of those `91` are **non-Nigeria-eligible** (e.g., `Electrum` ZA grad/intern + engineers, `Kraken` ZA, `DuckDuckGo` ZA, `Thndr` EG, `Wikimedia` GH/KE/ZA).
- **Bounded-Sample Caveat**: These metrics evaluate 20 deliberately curated direct employer boards as a reproducible snapshot on `2026-11-21`, not a census of the global market or every employer on any ATS platform.

---

## 7. Operational Database Safety & Activation Note (ADR 0030)

- **Strictly Offline / Disposable Testing During Step 55**: Step 55 did NOT open, migrate, seed, or modify `data/cache.sqlite`, sidecars, backups, restore-staging files, or `subscriptions.csv`. Every pre/post SHA-256 digest and byte size across all 9 files in `data/` remained 100% unchanged, and `subscriptions.csv` stayed absent.
- **Explicit Operator Activation Command**: To seed the expanded 20-board curated catalog into the operational SQLite database when authorized outside test/CI environments, an operator runs:
  ```powershell
  python -m src.project_files.board_monitor --seed-catalog --allow-operational-db
  ```

---

## 8. Verification & Next Step Recommendation

- **Verification**: Full backend pytest (including 12-country 20-board offline replay, SHA-256 verification across both Step 54 & Step 55 manifests, and Step 55 extractor regression tests), frontend `oxlint` + `vitest` + `tsc`/`vite build`, Playwright E2E (including the Step 55 7-country UX flow across `NG, DE, US, IN, CA, GH, EG`), and `scripts/check_db_safety.py` executed via `.\scripts\verify.ps1`.
- **Recommended Step 56**: Expand **remote early-career / junior worldwide & African EOR** direct employers (specifically addressing the remaining concentration where all `39` WW tech roles sit across 3 employers and early-career remote roles remain North America / EU skewed), plus add an optional operator CLI utility to backfill structured `JobEligibility` metadata across pre-existing operational `cache_store` snapshots.
