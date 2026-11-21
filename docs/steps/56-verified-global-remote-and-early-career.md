# Step 56: Verified Worldwide Remote & Early-Career Opportunities

**Date:** `2026-11-21`  
**Branch:** `step/56-verified-global-remote-and-early-career`  
**Base Commit (`origin/main` / PR #55 Merge SHA):** `e62bdb225cef732b86dd8424d1bd5607d6a55cf2`  
**Permanent Product Principle:** **Global job discovery. Applicant-country-aware eligibility. Nigerian-first validation, not Nigerian-only coverage.**

---

## 1. Executive Summary

Step 55 expanded the direct employer catalog to `20` boards (`39` worldwide technical postings, `51`/`52` Nigeria-eligible technical postings, and `34` early-career technical roles across `6` employers), while flagging significant publication-age staleness on `lever:metabase` (`325.7d` median) and `ashby:railway` (`476.7d` median). Step 56 executed four autonomous priorities while spending **`0` Serper credits**, adding **zero** new ATS providers (`len(MONITORABLE_PROVIDERS) == 9`), and keeping the operational SQLite database untouched (`ADR 0030`):

1. **Revalidated all Step 55 worldwide technical postings live (`2026-11-21`)**: Audited all `12` `Metabase` + `Railway` worldwide technical listings individually against live ATS feeds, canonical detail URLs, direct apply URLs, HTML career pages, and schema/JSON-LD `validThrough` metadata, plus live presence checks on `Supabase` (`80` live roles: `25/27` baseline live, `2` closed, `2` new `Remote, Global` roles added). Only `1` of `12` Metabase/Railway postings (`Metabase Security Engineer`, `37.8d`) is a verified fresh `<=90d` opening, `2` Metabase postings (`Backend` and `Frontend` SWE) carry explicit multi-hire evergreen language (`"hiring for multiple ... positions"`), and `9` (`3` Metabase + all `6` Railway roles, `162.7d–2,384.7d`) are **`Stale but still published`**. Excluding stale/evergreen roles left a fresh (`<=90d`) Step 55 baseline of **`28`** (`96.4%` Supabase; or **`20`** = `19` Supabase `95.0%` + `1` Metabase at exact Step 56 replay timestamps).
2. **Calculated the complete Early-Career × Work-Arrangement × 12-Country Intersection**: Recomputing the baseline `34` early-career technical postings and expanding to **`47`** early-career technical roles (`30` intern, `4` graduate, `13` junior, `0` apprenticeship) across **`12`** employers raised `GB` (`1 -> 5`), `US` (`11 -> 16`), `CA` (`12 -> 13`), and `SG` (`0 -> 1`). Crucially and transparently, **Intersections A (`NG` eligible), B (`NG` eligible + remote), and C (`worldwide` + `remote`) remain `0`** across all verified direct employer boards, while **`D` (5-country African union)** stands at `2` (`Electrum` South Africa).
3. **Screened `400+` ATS endpoints across `9` existing providers and promoted `8` verified direct employer boards (`20 -> 28`)**: Added [`ElevenLabs`](../../tests/fixtures/real/step56_employers/ashby_elevenlabs.json), [`Circle`](../../tests/fixtures/real/step56_employers/ashby_circle.json), [`Cohere`](../../tests/fixtures/real/step56_employers/ashby_cohere.json), [`Keyrock`](../../tests/fixtures/real/step56_employers/ashby_keyrock.json), [`Coinbase`](../../tests/fixtures/real/step56_employers/greenhouse_coinbase.json), [`Sentry`](../../tests/fixtures/real/step56_employers/ashby_sentry.json), [`Property Finder`](../../tests/fixtures/real/step56_employers/teamtailor_propertyfinder.xml), and [`Foodics`](../../tests/fixtures/real/step56_employers/workable_foodics.json). Fresh `<=90d` worldwide technical supply rose **`+60.0%`** (`20 -> 32` across `4` employers), cutting Supabase's fresh worldwide share from **`95.0%` to `59.4%`** (outside largest employer `1 -> 13`). Overall worldwide tech rose `39 -> 54` (`Supabase 69.2% -> 50.0%` across `5` employers) and Nigeria-eligible tech rose `52 -> 67` (`Supabase 51.9% -> 40.3%` across `9` employers; outside largest `25 -> 40`).
4. **Fixed extractor, career-stage, CLI preview, and E2E gaps**: Handled explicit role-level global execution clauses (`"This role is remote-first and can be executed globally"` — resolving `ElevenLabs` without false regional pollution while preserving `"East Coast"`/`"between"` guards), resolved `Anywhere` first segments (`Circle`), mapped major city hubs with leading `Hybrid - ` / `In-person - ` prefixes (`Affirm` London -> `GB`, `Coinbase` `Hybrid - Singapore` -> `SG`), extracted hierarchical `classify_career_stage()` (`src/project_files/career_stage.py`), added read-only `--preview-catalog` CLI inspection, and verified all **11** user countries plus early-career filter composition in Playwright E2E.

---

## 2. Priority 1 — Dated Audit of Step 55 Worldwide Technical Postings (`2026-11-21`)

*Historical integrity notice: [`55-global-remote-and-early-career-coverage.md`](55-global-remote-and-early-career-coverage.md) is preserved untouched as the Step 55 historical record.*

### 2.1 Live Verification of All 12 `Metabase` & `Railway` Worldwide Technical Roles

Evaluated live at `2026-11-21` UTC across ATS feeds (`api.lever.co`, `api.ashbyhq.com`), canonical job pages, direct apply endpoints, official career pages (`metabase.com/jobs` HTTP `200`, `148,663` bytes JS-embedded Lever widget; `railway.com/careers` HTTP `200`), and `validThrough` JSON-LD metadata:

| Board | Role Title | Published Date | Age (`2026-11-21`) | Feed Present | Detail / Apply HTTP | `validThrough` | Dated Revalidation Status & Evidence |
|---|---|---|---|---|---|---|---|
| `lever:metabase` | **Security Engineer** | `2026-10-14` | `37.8d` | `True` | `200 / 200` | `None` | **`Verified active`** — live Lever feed + detail/apply `200`, published within `90d`. |
| `lever:metabase` | **Software Engineer (Backend)** | `2020-05-19` | `2,376.6d` | `True` | `200 / 200` | `None` | **`Evergreen / continuously open`** — May 2020 req explicitly states `"We are hiring for multiple backend software engineer positions"`. |
| `lever:metabase` | **Software Engineer (Frontend)** | `2020-05-11` | `2,384.7d` | `True` | `200 / 200` | `None` | **`Evergreen / continuously open`** — May 2020 req explicitly states `"We are hiring for multiple frontend software engineer positions"`. |
| `lever:metabase` | CI Engineer | `2026-04-21` | `213.7d` | `True` | `200 / 200` | `None` | **`Stale but still published`** — `>90d` without `validThrough` or explicit multi-hire evergreen statement; feed `200` only. |
| `lever:metabase` | Senior SRE/DevOps Engineer | `2020-05-11` | `2,384.7d` | `True` | `200 / 200` | `None` | **`Stale but still published`** — May 2020 single req without explicit evergreen headcount confirmation. |
| `lever:metabase` | Success Engineer (Global) | `2020-05-19` | `2,376.5d` | `True` | `200 / 200` | `None` | **`Stale but still published`** — May 2020 single req without `validThrough` or evergreen headcount statement. |
| `ashby:railway` | Senior Full-Stack Engineer - Product | `2024-02-07` | `1,017.6d` | `True` | `200 / 200` | `None` | **`Stale but still published`** — listed on `railway.com/careers` (`200`), `1,017.6d` without `validThrough` or explicit evergreen hiring guarantee. |
| `ashby:railway` | Infrastructure Engineer | `2024-06-03` | `900.7d` | `True` | `200 / 200` | `None` | **`Stale but still published`** — `900.7d` old (`>90d`); `"stuff is ALWAYS happening"` is culture prose, not evergreen headcount confirmation. |
| `ashby:railway` | Senior Platform Engineer: Storage | `2025-08-01` | `476.8d` | `True` | `200 / 200` | `None` | **`Stale but still published`** — `476.8d` old; careers page route `200` with no `validThrough` or explicit evergreen headcount confirmation. |
| `ashby:railway` | Senior Infra Engineer: Observability | `2026-05-01` | `203.5d` | `True` | `200 / 200` | `None` | **`Stale but still published`** — `203.5d` old (`>90d`) without `validThrough` or evergreen hiring confirmation. |
| `ashby:railway` | Senior Infra Engineer: Baremetal Orchestration | `2026-05-08` | `196.6d` | `True` | `200 / 200` | `None` | **`Stale but still published`** — `196.6d` old (`>90d`) without `validThrough` or evergreen hiring confirmation. |
| `ashby:railway` | Senior Product Engineer, Scalability | `2026-06-11` | `162.7d` | `True` | `200 / 200` | `None` | **`Stale but still published`** — `162.7d` old (`>90d`); role route `200` without `validThrough` or explicit evergreen confirmation. |

- **Metabase & Railway 12-role audit tally**: **`1`** `Verified active`, **`2`** `Evergreen / continuously open`, **`9`** `Stale but still published`, **`0`** `Expired or closed`, **`0`** `Unverified`.

### 2.2 Live `Supabase` Check & Recalculated Fresh Worldwide Baseline

- **Supabase live feed (`2026-11-21`, `80` active postings)**: **`25/27`** Step 54/55 baseline worldwide technical roles remained live (`2` FinOps postings — `FinOps Engineer` and `FinOps Data Engineer` — closed since the Step 54 fixture capture, while `2` new `Remote, Global` roles appeared).
- **Recalculated Step 55 fresh verified-active worldwide baseline**: Excluding Metabase's `2` evergreen and `3` stale roles plus all `6` stale (`>162d`) Railway roles leaves **`28`** verified `<=90d` worldwide roles on the Step 55 historical baseline (`27` Supabase Step 54 baseline + `1` Metabase `Security Engineer` = **`96.4%` Supabase**). Re-evaluating the committed 20-board fixtures at Step 56 capture time (`2026-11-21T12:57Z`) yields **`20`** fresh `<=90d` worldwide technical roles (`19` Supabase = **`95.0%`**, `1` Metabase).

---

## 3. Priority 2 — Early-Career Opportunity Intersection Cross-Tab

All `34` baseline early-career technical roles (Steps 54–55) and all `47` combined early-career technical roles (Step 56) were evaluated across career stage (`src/project_files/career_stage.py`), work arrangement, and 12 applicant countries (`evaluation_manifest.json`).

### 3.1 Summary & Intersections A–D (Before `20 Boards` vs After `28 Boards`)

| Intersection / Dimension | Before (`20` Boards, Recomputed) | After (`28` Boards) | Notes & Evidence |
|---|---|---|---|
| **Total Early-Career Tech Roles** | `34` (`20` intern, `2` grad, `12` junior, `0` apprentice) | **`47`** (`30` intern, `4` grad, `13` junior, `0` apprentice) | Expanded from `6` to **`12`** distinct employers. |
| **Work Arrangement (Remote / Hybrid / Onsite / Unknown)** | `5 / 15 / 8 / 6` | **`7 / 22 / 11 / 7`** | Added remote Cohere ML Intern & Foodics Junior AI Forward Engineer + hybrid/onsite interns. |
| **Intersection A: Nigeria (`NG`) Eligible** | `0` | **`0`** | No direct employer in the 28-board catalog lists an explicitly `NG`-eligible early-career tech opening. |
| **Intersection B: Nigeria Eligible + Remote** | `0` | **`0`** | Same root gap as Intersection A. |
| **Intersection C: Worldwide + Remote** | `0` | **`0`** | Cohere's remote ML intern is explicitly `CA/US/GB/Europe`-scoped; Foodics' remote Jordan role discloses `JO` location without open global residency. |
| **Intersection D: 5-Country Africa Sample (`NG/GH/KE/ZA/EG`)** | `2` | **`2`** | `Electrum` (`workable:electrum`): `2027 Software Developer Graduate Programme` & `Summer Internship` in Cape Town (`ZA`). |

### 3.2 Intersection E: Per-Country Early-Career Eligibility Matrix (`Eligible / Restricted / Unknown`)

| Country (ISO-2) | Before (`34` Early-Career) | After (`47` Early-Career) | Primary Verified Early-Career Employers When Eligible |
|---|---|---|---|
| **Nigeria** (`NG`) | `0 / 16 / 18` | `0 / 20 / 27` | — (priority gap recorded for Step 57) |
| **Ghana** (`GH`) | `0 / 16 / 18` | `0 / 20 / 27` | — |
| **Kenya** (`KE`) | `0 / 16 / 18` | `0 / 20 / 27` | — |
| **South Africa** (`ZA`) | `2 / 14 / 18` | **`2 / 18 / 27`** | `Electrum` (`2` Cape Town graduate/intern) |
| **Egypt** (`EG`) | `0 / 16 / 18` | `0 / 20 / 27` | — *(Property Finder has Cairo senior/mid SWEs, `Dubai` Graduate Trainee)* |
| **United Kingdom** (`GB`) | `1 / 16 / 17` | **`5 / 16 / 26`** | `Keyrock` (`3` London/Brussels interns), `Cohere` (`1` remote UK/CA/US/EU ML intern), `Affirm` (`1` London Early Career fixed by city lookup) |
| **Germany** (`DE`) | `3 / 13 / 18` | **`3 / 16 / 28`** | `Almedia` (`3` Berlin Junior SWE/Data/AI) |
| **United States** (`US`) | `11 / 11 / 12` | **`16 / 14 / 17`** | `Coinbase` (`4` NY/SF interns), `Cohere` (`1` remote ML intern), `Affirm`, `Lyft` |
| **Canada** (`CA`) | `12 / 12 / 10` | **`13 / 15 / 19`** | `Cohere` (`1` remote ML intern), `Affirm`, `Lyft` |
| **India** (`IN`) | `0 / 16 / 18` | `0 / 20 / 27` | — |
| **Singapore** (`SG`) | `0 / 16 / 18` | **`1 / 20 / 26`** | `Coinbase` (`1` Hybrid - Singapore Software Engineer Intern) |
| **Australia** (`AU`) | `0 / 16 / 18` | `0 / 20 / 27` | — |

### 3.3 Intersection F: Early-Career Technical Roles by Employer & Freshness

| Employer | Stage (`Intern / Grad / Jr`) | Total | `<=30d` | `<=90d` | Primary Footprint / Work Model Highlights |
|---|---|---|---|---|---|
| `Lyft` (`greenhouse:lyft`) | `15 / 0 / 0` | `15` | `0` | `15` | US/CA Summer 2027 Internships (`hybrid`/`unknown`) |
| `Affirm` (`greenhouse:affirm`) | `2 / 0 / 9` | `11` | `5` | `11` | Remote CA SWE I (`4`), Remote US SWE I (`3`), London Early Career (`GB`, fixed in Step 56), SF Interns (`2`), NY/SF Analyst |
| `Coinbase` (`greenhouse:coinbase`) | `5 / 0 / 0` | **`5`** | `0` | **`5`** | `4` NY/SF Hybrid interns (`US`) + **`1` Hybrid Singapore SWE Intern (`SG`)** |
| `Almedia` (`ashby:almedia`) | `0 / 0 / 3` | `3` | `1` | `3` | Berlin Junior SWE / Data / Python-TS-DevOps-AI (`DE`) |
| `Keyrock` (`ashby:keyrock`) | `3 / 0 / 0` | **`3`** | **`3`** | **`3`** | Ultra-fresh (`4.6d–17.9d`) Quant & DeFi Interns (London/Brussels, `GB`) |
| `Whippy` (`ashby:whippy`) | `1 / 1 / 0` | `2` | `2` | `2` | Dublin onsite Intern & New Graduate (`IE`, `5.0d`) |
| `Electrum` (`workable:electrum`) | `1 / 1 / 0` | `2` | `1` | `2` | Cape Town Graduate Programme & Summer Intern (`ZA`) |
| `Sentry` (`ashby:sentry`) | `1 / 1 / 0` | **`2`** | `0` | **`2`** | Vienna Intern (Summer 2027) & New Grad (`AT`, `71.9d`) |
| `Wikimedia Foundation` (`greenhouse:wikimedia`) | `1 / 0 / 0` | `1` | `0` | `1` | SWE Internship |
| `Cohere` (`ashby:cohere`) | `1 / 0 / 0` | **`1`** | `0` | `0` | Remote Machine Learning Intern/Co-op (`CA/US/GB/Europe`, `191.8d`) |
| `Property Finder` (`teamtailor:propertyfinder`) | `0 / 1 / 0` | **`1`** | `0` | **`1`** | `Engineering Graduate Trainee` (Dubai `AE`, `53.2d`) |
| `Foodics` (`workable:foodics`) | `0 / 0 / 1` | **`1`** | `0` | **`1`** | `Junior AI Forward Engineer, Foodics Online` (Amman `JO`, `37.5d`, `remote`) |

---

## 4. Priority 3 — Discovery Screening, Permission Checks & Declined Candidates

- **Zero Serper credits spent** (`serper_credits_spent == 0`) and **zero new ATS providers added** (`len(MONITORABLE_PROVIDERS) == 9`).
- **Discovery leads inspected**: Probed `400+` candidate ATS endpoints across rounds 1–4 (`328` distinct non-empty boards returned across existing providers), verified official career portals and `robots.txt` rules across `jobs.ashbyhq.com`, `boards-api.greenhouse.io`, `api.lever.co`, `apply.workable.com`, and `propertyfinder.teamtailor.com`, consulted `US-RSE` & `Python.org` communities, and used `OpenToAfrica` strictly as a **`Discovery-only`** lead directory (promoting `ashby:circle` and `ashby:keyrock` via their official careers portals and public Ashby feeds with **zero** listing prose copied).

| Declined / Deferred Candidate | Observed Screening Metrics (`2026-11-21`) | Concrete Exclusion Rationale |
|---|---|---|
| `smartrecruiters` (provider) | `api.smartrecruiters.com/robots.txt` | `Disallow: /` for `User-agent: *`; remains gated out from curated catalog promotions. |
| `greenhouse:canonical` | `318` uniq / `138` tech / `45` WW / `2` WW Jr | Raw `?content=true` payload is `3,552,712` bytes (`> 3,145,728` B cap); extreme staleness (`med 861.3d`, only `1/45` WW `<=90d`, `Junior` roles `378.8d` & `999.3d`). |
| `greenhouse:celonis` | `262` uniq / `144` tech / `0` WW / `8` early | Raw `?content=true` payload is `4,759,926` bytes (`> 3,145,728` B cap). |
| `greenhouse:scaleai` | `169` uniq / `72` tech / `0` WW / `8` early | Undisclosed `work_model=unknown` on early-career postings + `112.5d` median age. |
| `greenhouse:automatticcareers` | `6` uniq / `2` tech / `0` WW / `0` early | `582.8d` median age, `0` within 30d. |
| `greenhouse:brave` | `9` uniq / `5` tech / `1` WW / `1` early | Single WW role is `2,347.6d` stale; intern has `unknown` work model. |
| `greenhouse:openzeppelin` | `6` uniq / `3` tech / `1` WW | Single WW role is `2,145.5d` stale. |
| `greenhouse:strike` | `4` uniq / `2` tech / `0` WW | `1,703.2d` median age. |
| `workable:renmoney` | `72` raw / `4` tech / `0` WW / `0` early | `220.5d` median age, `1` within 30d. |
| `ashby:andela` | — | `0` internal technical/WW postings found. |
| `ashby:backmarket` / `ashby:mollie` | `32/9/3` & `48/12/3` early | Official careers landing check returned HTTP `404` during verification gate. |

---

## 5. Promoted 8 Boards & Catalogued vs Operationally Active Status

All **8** promoted boards pass the `3,145,728`-byte response limit, return HTTP `200` on official careers pages and sampled direct apply URLs, and belong to existing `MONITORABLE_PROVIDERS`.

| Company | Key (`provider:token`) | Discovery Lead | Fixtures (`bytes` `< 3MB`) | Careers / Apply | Uniq / Tech / Early / WW90 | Median Age |
|---|---|---|---|---|---|---|
| **ElevenLabs** | `ashby:elevenlabs` | Global remote seed | `1,768,278` B (`501fbf354b41...`) | `200` / `[200, 200]` | `122 / 36 / 0 / 11` (`14` WW) | `36.8d` |
| **Circle** | `ashby:circle` | `OpenToAfrica` lead | `120,647` B (`72ee5c0d02cc...`) | `200` / `[200, 200]` | `6 / 1 / 0 / 1` | `37.9d` |
| **Cohere** | `ashby:cohere` | Global early-career seed | `2,272,349` B (`0f2bdbc3f310...`) | `200` / `[200, 200]` | `124 / 58 / 1 / 0` (`CA 18, US 11, GB 10`) | `49.5d` |
| **Keyrock** | `ashby:keyrock` | `OpenToAfrica` lead | `207,706` B (`857618bf38d3...`) | `200` / `[200, 200]` | `11 / 6 / 3 / 0` (`GB 3`) | `17.9d` |
| **Coinbase** | `greenhouse:coinbase` | Global early-career seed | `2,790,478` B (`0fe4739213b0...`) | `200` / `[200, 200]` | `252 / 104 / 5 / 0` (`US 81, IN 7, CA 6, SG 4`) | `56.6d` |
| **Sentry** | `ashby:sentry` | EU early-career seed | `659,045` B (`125501ecb703...`) | `200` / `[200, 200]` | `42 / 31 / 2 / 0` (`US 18, CA 9, AT 2`) | `55.7d` |
| **Property Finder** | `teamtailor:propertyfinder` | MENA/Africa seed | `364,681` B (`9993c19c3966...`) | `200` / `[200, 200]` | `41 / 8 / 1 / 0` (`AE` Grad + Cairo hubs) | `53.2d` |
| **Foodics** | `workable:foodics` | MENA/Africa seed | `22,357` + `174,342` B | `200` / `[200, 200]` | `30 / 6 / 1 / 0` (`JO` Jr AI + `SA/EG`) | `36.0d` |

### Explicit Distinction: Catalogued vs Operationally Active (`ADR 0030`)

| State Flag | Value at End of Step 56 | Meaning |
|---|---|---|
| `catalogued` | **`true`** (`28` boards) | Defined in [`VERIFIED_EMPLOYER_BOARDS`](../../src/project_files/employer_board_catalog.py) with committed offline fixtures & SHA-256 manifests. |
| `permission_verified` | **`true`** (`28` boards) | `robots.txt`, official careers URL, and public ATS feed access verified. |
| `technically_verified` | **`true`** (`28` boards) | Replayed offline end-to-end through `BoardMonitor.check_single_board` & `extract_eligibility()`. |
| `operationally_registered` | **`false`** (default in repo) | **NOT seeded into `data/cache.sqlite`** during automated development (`ADR 0030` prohibits touching operational DB). Operators inspect read-only via `python -m src.project_files.board_monitor --preview-catalog` (`"operational_db_opened": false`) and explicitly activate via `python -m src.project_files.board_monitor --seed-catalog --allow-operational-db`. |

---

## 6. Before vs After Comparison & 12-Country Eligibility Matrix (`evaluation_manifest.json`)

### 6.1 Aggregate Comparison (`Step 55 Baseline Recomputed` vs `New 8 Boards` vs `Combined 28 Boards`)

| Metric | Step 55 Baseline (`20` Boards Recomputed) | Step 56 New `8` Boards Only | Step 56 Combined (`28` Boards) |
|---|---|---|---|
| Raw Adapter Listings | `1,059` | `629` | **`1,688`** |
| Canonical Unique Active Jobs (`Dups Removed`) | `1,023` (`36`) | `628` (`1`) | **`1,651`** (`37`) |
| Unique Technical Roles | `472` | `250` | **`722`** |
| Tech Work Models (`Remote / Hybrid / Onsite / Unk`) | `264 / 84 / 24 / 100` | `172 / 60 / 9 / 9` | **`436 / 144 / 33 / 109`** |
| Tech Classifications (`WW / CR / RR / Local / Auth / Unk`) | `39 / 277 / 18 / 90 / 1 / 47` | `15 / 137 / 4 / 51 / 0 / 43` | **`54 / 414 / 22 / 141 / 1 / 90`** |
| **Worldwide Tech `<=90d` Fresh (`Largest Share / Employers`)** | `20` (**`95.0%`** Supabase, `2` emp, `1` outside) | `12` (`ElevenLabs 11`, `Circle 1`, `2` emp) | **`32`** (**`59.4%`** Supabase, **`4`** emp, **`13`** outside) |
| **Worldwide Tech `<=30d` Fresh** | `8` | `5` | **`13`** |
| **Worldwide Tech All Ages (`Largest Share / Employers`)** | `39` (`69.2%` Supabase, `3` emp, `12` outside) | `15` (`ElevenLabs 14`, `Circle 1`) | **`54`** (**`50.0%`** Supabase, **`5`** emp, **`27`** outside) |
| **Nigeria-Eligible Tech (`Largest Share / Employers`)** | `52` (`51.9%` Supabase, `7` emp, `25` outside) | `15` (`ElevenLabs 14`, `Circle 1`) | **`67`** (**`40.3%`** Supabase, **`9`** emp, **`40`** outside) |
| Early-Career Tech (`Intern / Grad / Jr / Apprent`) | `34` (`20 / 2 / 12 / 0`, `6` emp) | `13` (`10 / 2 / 1 / 0`, `6` emp) | **`47`** (`30 / 4 / 13 / 0`, **`12`** emp) |
| Freshness (`Median / P90 / <=30d / <=90d`) | `33.3d / 134.0d / 462 / 826` | `46.7d / 158.6d / 222 / 480` | `38.5d / 144.7d / 684 / 1,306` |

### 6.2 Representative 12-Country Eligibility Breakdown

| Applicant Country | ISO-2 | `20`-Board Tech (`Elig / Restr / Unk`) | New `8` Boards Tech (`Elig / Restr / Unk`) | Combined `28`-Board Tech (`Elig / Restr / Unk`) | Combined All Active (`1,651`) |
|---|---|---|---|---|---|
| **Nigeria (Priority Market)** | `NG` | `52 / 305 / 115` | `15 / 147 / 88` | **`67 / 452 / 203`** | `138 / 933 / 580` |
| **Ghana** | `GH` | `48 / 304 / 120` | `15 / 147 / 88` | **`63 / 451 / 208`** | `117 / 927 / 607` |
| **Kenya** | `KE` | `49 / 303 / 120` | `15 / 147 / 88` | **`64 / 450 / 208`** | `119 / 924 / 608` |
| **South Africa** | `ZA` | `79 / 273 / 120` | `15 / 147 / 88` | **`94 / 420 / 208`** | `159 / 886 / 606` |
| **Egypt** | `EG` | `45 / 313 / 114` | `15 / 147 / 88` | **`60 / 460 / 202`** | `108 / 947 / 596` |
| **United Kingdom** | `GB` | `90 / 265 / 117` | `38 / 122 / 90` | **`128 / 387 / 207`** | `246 / 798 / 607` |
| **Germany** | `DE` | `64 / 290 / 118` | `16 / 132 / 102` | **`80 / 422 / 220`** | `150 / 872 / 629` |
| **United States** | `US` | `160 / 215 / 97` | `133 / 54 / 63` | **`293 / 269 / 160`** | `630 / 533 / 488` |
| **Canada** | `CA` | `146 / 230 / 96` | `48 / 126 / 76` | **`194 / 356 / 172`** | `334 / 766 / 551` |
| **India** | `IN` | `46 / 307 / 119` | `22 / 140 / 88` | **`68 / 447 / 207`** | `124 / 916 / 611` |
| **Singapore** | `SG` | `46 / 307 / 119` | `19 / 144 / 87` | **`65 / 451 / 206`** | `121 / 920 / 610` |
| **Australia** | `AU` | `40 / 313 / 119` | `15 / 147 / 88` | **`55 / 460 / 207`** | `92 / 948 / 611` |

- **Deduplicated 5-Country Sampled-Africa Union (`NG`, `GH`, `KE`, `ZA`, `EG`)**: **`106`** unique technical roles are eligible in at least one of the 5 sampled African countries (`39` non-Nigeria-eligible).

---

## 7. Extraction, Career-Stage & Frontend Changes Implemented

- [`src/project_files/eligibility_extractor.py`](../../src/project_files/eligibility_extractor.py): Added `_EXPLICIT_ROLE_GLOBAL_EXEC_RE` (`"this role is remote-first and can be executed globally"` / `"from anywhere"`) with `"East/West Coast"` and `"between"` bounds guards so `ElevenLabs` global engineering roles extract `worldwide` cleanly without letting sample Ashby `secondaryLocations` tags pollute explicit global prose; added `Anywhere` first-segment resolution (`Circle`); stripped leading `Hybrid -` / `In-person -` prefixes and added `_MAJOR_CITY_TO_COUNTRY_CODE` (`London -> GB`, `Singapore -> SG`, `Amman -> JO`, `Vienna -> AT`, `Dubai -> AE`, `Lagos -> NG`, etc.).
- [`frontend/src/lib/eligibility.ts`](../../frontend/src/lib/eligibility.ts): Mirrored `_LOCAL_MODE_PREFIX_RE` and `MAJOR_CITY_TO_COUNTRY_CODE` in `inferPhysicalCountryCode` so frontend client filtering stays aligned with backend physical country resolution.
- [`src/project_files/career_stage.py`](../../src/project_files/career_stage.py): Extracted canonical hierarchical `classify_career_stage()` (`intern -> graduate -> apprenticeship -> junior -> senior_plus -> level-one -> mid_or_unspecified`), resolving the Step 55 ambiguity bug where `"Senior Software Engineer I"` and `"Principal Software Engineer I"` previously matched junior regexes.
- [`src/project_files/employer_board_catalog.py`](../../src/project_files/employer_board_catalog.py) & [`src/project_files/board_monitor.py`](../../src/project_files/board_monitor.py): Expanded `VERIFIED_EMPLOYER_BOARDS` (`20 -> 28`) and added read-only `--preview-catalog` CLI inspection alongside `preview_catalog_activation()` without opening operational SQLite.

---

## 8. Operational DB Safety (`ADR 0030`) & Step 57 Recommendation

- **Operational DB untouched**: No code or test opened, seeded, checkpointed, or altered `data/cache.sqlite`, sidecars, backups, restore-staging files, or `subscriptions.csv`. All 9 SHA-256 baseline digests matched 100% before and after Step 56.
- **Recommended Step 57**:
  1. Target the verified **`0`-role gap in genuine worldwide-remote and Nigeria/Africa-eligible early-career technical roles** by investigating direct international graduate/internship programs (including global OSS fellowship/apprenticeship sponsors and EOR-hiring technical teams) without relaxing evidence standards or counting stale `>90d` requisitions as fresh openings.
  2. Seek explicit project-owner authorization to run `python -m src.project_files.board_monitor --seed-catalog --allow-operational-db` so the `28` catalogued boards become `operationally_registered: true` in runtime search.
