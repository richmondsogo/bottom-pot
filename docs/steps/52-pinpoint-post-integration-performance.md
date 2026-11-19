# Step 52: Pinpoint (`pinpointhq`) Post-Integration Empirical Performance Audit & Detail Timeout Fix

**Status:** Complete — **Pinpoint `Operationally accepted with limitations` (`Constrained`)**  
**Date:** 2026-11-19  
**Branch:** `step/52-pinpoint-post-integration-performance`  
**Base Commit (`main`):** `64bc76b80e2539d790e46609f0599a3d5a01dd0c` (Merge PR #51)  
**Assessment Verdict:** **`Operationally accepted with limitations`** (`Constrained` in [`docs/job-source-catalog.md`](../job-source-catalog.md))  
**Next Source Cycle:** **Step 53** — Head-to-head empirical permission, technical-yield, and eligibility audit of **Gem ATS (`gem`)** and **Manatal Career Page API v3 (`manatal`)** (implementing at most one qualifying winner).

---

## 1. PR #51 Merge Provenance

- **Pull Request:** https://github.com/richmondsogo/bottom-pot/pull/51
- **Verified Head SHA Prior to Merge:** `f3b5e703d2a081de7de4572b0d14dea012dee5c3` (4/4 exact-head CI checks passed: `GitGuardian Security Checks`, `frontend-checks`, `backend-and-db-safety`, `windows-safety`; `0` review comments/unresolved threads)
- **Merge Strategy & Timestamp:** Ready-for-review transition followed by standard merge commit (`--merge`) at `2026-11-19T10:10:20Z`
- **Exact Merge Commit SHA:** `64bc76b80e2539d790e46609f0599a3d5a01dd0c`
- **Post-Merge Verification:** `main` and `origin/main` both resolve to `64bc76b80e2539d790e46609f0599a3d5a01dd0c`; complete PR #51 commit history (`26808f0`, `0264fc0`, `02ea4cc`, `f3b5e70`, `64bc76b`) preserved; historical branch `step/51-global-source-discovery` preserved; `pinpointhq` verified active across backend inventories, frontend chips (`21` total platforms), and `docs/job-source-catalog.md`; offline post-merge checks on `main` passed (`check_db_safety.py`: 0 unsafe patterns; `test_pinpoint_monitoring.py` + `test_platform_reconciliation.py`: `20/20` passed; frontend `vitest`: `17` files / `116/116` passed).

---

## 2. Live Tenant Census Scope & Collection Date

- **Scope:** All `24` tenant subdomains in [`tests/fixtures/real/pinpointhq/probe_census_manifest.json`](../../tests/fixtures/real/pinpointhq/probe_census_manifest.json), queried sequentially (`0.5s` delay, concurrency `1`, `follow_redirects=False`, timeout `25.0s`, size cap `3 MiB`, **zero Serper credits spent**).
- **Pass 1 (`2026-11-19T10:20:34Z`–`10:25:42Z` UTC):** `12/24` boards completed cleanly (`9` non-empty `200 OK`, `2` empty `200 OK`, `1` `404` `rowden`), `3` timed out on `ReadTimeout` during streaming (`confluence`, `davies`, `tradingtechnologies`), and `9` failed DNS resolution (`ConnectError: [Errno 11001] getaddrinfo failed`) during a local network/DNS disruption starting `10:22:22Z`.
- **Pass 2 Clean Retry of the `12` Incomplete Boards (`2026-11-19T10:48:55Z`–`10:55:18Z` UTC):** All `12` completed with authentic server responses (`10` non-empty `200 OK`, `1` `404` `brightsg`, `1` `301` redirect `cintra -> https://pssg.pinpointhq.com/postings.json`).

---

## 3. Current Live Tenant Feed Results (24-Board Combined Snapshot)

*(Pass 1 outcomes are preserved alongside Pass 2 outcomes where retried; `snapshot_complete=True` strictly requires a valid complete `HTTP 200` JSON snapshot or `304` with prior snapshot.)*

| Tenant Slug | Pass | HTTP Status | Elapsed (ms) | TTFB (ms) | Max Chunk Gap (ms) | Bytes | Raw / Valid / Rej / Norm | Outcome Classification | Step 51 Baseline Delta |
|---|---|---:|---:|---:|---:|---:|---|---|---|
| `workwithus` | P1 | `200` | `11,602.2` | `11,175.3` | `224.7` | `35,687` | `3 / 3 / 0 / 3` | `http_200_valid_non_empty` | Same (`3`) |
| `confluence` | P2 (P1 `ReadTimeout`) | `200` | `4,882.0` | `1,687.8` | `1,780.8` | `131,788` | `11 / 11 / 0 / 11` | `http_200_valid_non_empty` | Same (`11`) |
| `scurri` | P1 | `200` | `2,057.7` | `1,779.5` | `224.0` | `28,191` | `4 / 4 / 0 / 4` | `http_200_valid_non_empty` | `-1` job (`5 -> 4`) |
| `cfc` | P1 | `200` | `14,907.4` | `1,702.9` | `3,021.0` | `433,563` | `70 / 70 / 0 / 70` | `http_200_valid_non_empty` | Same (`70`) |
| `whiteswandata` | P1 | `200` | `5,810.4` | `5,031.7` | `299.2` | `93,656` | `16 / 16 / 0 / 16` | `http_200_valid_non_empty` | Same (`16`) |
| `calligo` | P1 | `200` | `1,659.0` | `1,656.7` | `0.0` | `11` | `0 / 0 / 0 / 0` | `http_200_valid_empty` | Same (`0`) |
| `pathify` | P1 | `200` | `1,999.9` | `1,692.3` | `303.9` | `36,640` | `4 / 4 / 0 / 4` | `http_200_valid_non_empty` | Same (`4`) |
| `teachingstrategies` | P1 | `200` | `2,233.6` | `2,231.0` | `0.0` | `11` | `0 / 0 / 0 / 0` | `http_200_valid_empty` | Same (`0`) |
| `coforma` | P1 | `200` | `4,503.2` | `2,869.2` | `1,251.6` | `47,013` | `5 / 5 / 0 / 5` | `http_200_valid_non_empty` | Same (`5`) |
| `arkatechture` | P1 | `200` | `1,463.2` | `1,461.3` | `0.5` | `9,351` | `1 / 1 / 0 / 1` | `http_200_valid_non_empty` | Same (`1`) |
| `receptive` | P1 | `200` | `8,253.5` | `4,872.6` | `1,115.9` | `109,847` | `16 / 16 / 0 / 16` | `http_200_valid_non_empty` | Recovered (`ConnectTimeout -> 16`) |
| `propellerindustries` | P1 | `200` | `9,617.2` | `1,950.7` | `5,469.2` | `96,632` | `6 / 6 / 0 / 6` | `http_200_valid_non_empty` | Same (`6`) |
| `brightsg` | P2 (P1 DNS) | `404` | `3,683.6` | `3,682.8` | `—` | `—` | `— / 0 / 0 / 0` | `http_404_not_found` (`snapshot_complete=False`) | Same (`404`) |
| `frazil` | P2 (P1 DNS) | `200` | `11,791.0` | `8,678.4` | `2,488.2` | `39,583` | `5 / 5 / 0 / 5` | `http_200_valid_non_empty` | `+1` job (`4 -> 5`) |
| `davies` | P2 (P1 `ReadTimeout`) | `200` | `165,847.7` | `7,492.3` | `17,102.3` | `2,185,604` | `263 / 263 / 0 / 263` | `http_200_valid_non_empty` | Decoded (`263`, < `3 MiB`) |
| `bizimply` | P2 (P1 DNS) | `200` | `1,498.4` | `1,496.0` | `0.5` | `13,676` | `2 / 2 / 0 / 2` | `http_200_valid_non_empty` | Same (`2`) |
| `surgohealth` | P2 (P1 DNS) | `200` | `16,966.0` | `4,779.3` | `9,617.6` | `146,370` | `12 / 12 / 0 / 12` | `http_200_valid_non_empty` | Same (`12`) |
| `emergn` | P2 (P1 DNS) | `200` | `5,873.7` | `3,828.5` | `1,282.9` | `53,226` | `8 / 8 / 0 / 8` | `http_200_valid_non_empty` | Same (`8`) |
| `rowden` | P1 | `404` | `5,541.0` | `5,540.3` | `—` | `—` | `— / 0 / 0 / 0` | `http_404_not_found` (`snapshot_complete=False`) | Same (`404`) |
| `tradingtechnologies` | P2 (P1 `ReadTimeout`) | `200` | `9,731.1` | `1,686.7` | `2,194.4` | `260,586` | `21 / 21 / 0 / 21` | `http_200_valid_non_empty` | Same (`21`) |
| `indrive` | P2 (P1 DNS) | `200` | `101,635.5` | `4,366.1` | `9,213.7` | `1,051,185` | `162 / 162 / 0 / 162` | `http_200_valid_non_empty` | `+1` job (`161 -> 162`) |
| `cintra` | P2 (P1 DNS) | `301` | `1,215.4` | `1,213.9` | `—` | `—` | `— / 0 / 0 / 0` | `http_301_redirect -> pssg` (`snapshot_complete=False`) | Same (`301`) |
| `intermedia` | P2 (P1 DNS) | `200` | `31,556.2` | `1,349.4` | `9,095.4` | `465,276` | `45 / 45 / 0 / 45` | `http_200_valid_non_empty` | `-1` job (`46 -> 45`) |
| `sunking` | P2 (P1 DNS) | `200` | `61,777.2` | `6,169.8` | `6,865.3` | `1,425,935` | `186 / 186 / 0 / 186` | `http_200_valid_non_empty` | `+3` jobs (`183 -> 186`) |

- **Status Breakdown (`24` total):** `19` active non-empty `200 OK` feeds, `2` valid empty feeds, `2` `HTTP 404` boards, `1` `HTTP 301` redirect, `0` `429`, `0` `5xx`, `0` malformed payloads, `0` oversize (> `3 MiB`).

---

## 4. Raw, Valid, Normalized, and Unique Listing Counts

| Metric | Count | Notes |
|---|---:|---|
| Active non-empty feeds (`HTTP 200`, `len(data) > 0`) | **19** | `+2` vs Step 51 (`davies`, `receptive`) |
| Valid empty boards (`HTTP 200`, `{"data":[]}`) | **2** | `calligo`, `teachingstrategies` |
| Unavailable / failed boards (final combined snapshot) | **3** | `brightsg` (`404`), `rowden` (`404`), `cintra` (`301`) |
| Total raw postings returned across `19` active feeds | **840** | Sum of `len(payload["data"])` |
| Total validated postings (`parse_pinpoint_postings_json`) | **840** | `0` validation errors |
| Total normalized listings (`_pinpoint_item_to_listing`) | **840** | `0` conversion failures |
| Total rejected postings | **0** | `0.0%` |
| Unique canonical job count (`pinpointhq:{slug}:{uuid}`) | **840** | Across all `19` active feeds |

---

## 5. Duplicate Metrics and Cross-Source Limitations

- **Canonical identity duplicates:** **`0 / 840` (`0.0%`)** — all `840` postings carry distinct canonical `(slug, uuid)` IDs, and URL normalization collapsed locale/apply/case variants cleanly to `https://{slug}.pinpointhq.com/postings/{uuid}`.
- **Cross-tenant Pinpoint duplicates:** **`0`** shared UUIDs and **`0`** identical `(title, description_sha256)` pairs across different Pinpoint tenants.
- **Intra-tenant content duplicates (distinct requisition UUIDs with identical normalized title + description SHA-256):** **`47`** extra postings (`5.60%` of `840`) — predominantly `davies` (multi-seat/regional claims & ops requisitions), `indrive` (same engineering role posted across multiple regional hubs such as Cyprus/Kazakhstan/Egypt/Pakistan), `confluence`, `cfc`, `intermedia`, and `tradingtechnologies`. Intra-tenant identical `(slug, title, location)` across distinct UUIDs accounted for **`36`** extra postings (`4.29%`).
- **Cross-source overlap limitation:** Per ADR 0030, operational `data/cache.sqlite` was not opened or queried during this audit; exhaustive posting-level overlap with Greenhouse/Lever/Ashby/Workable/Recruitee operational tables cannot be measured safely without an approved read-only operational audit harness.

---

## 6. Freshness and Publication-Date Findings

- **Feed-level (`840` postings):** `0/840` (`0%`) expose `posted_at` (ADR 0001 honored; `deadline_at` is present on `61/840` [`7.3%`] with `0` expired as of `2026-11-19`, and never synthesized as `posted_at`); `839/840` (`99.9%`) pass `description_ok`; `136/840` (`16.2%`) expose visible compensation.
- **30-Posting Balanced Detail & Apply-Link Sample (`2026-11-19`):**
  - `24/30` detail HTML pages returned `200 OK` (`6` hit transient `ReadTimeout`/`ConnectTimeout`/`getaddrinfo` at `15.0s` client timeout); `24/24` (`100%`) of fetched detail pages contained Schema.org `JobPosting` JSON-LD with verifiable `datePosted`, while **`0/24`** included `validThrough`.
  - `26/30` direct `/applications/new` URLs returned `200 OK` (`4` hit transient `ConnectTimeout`/`ReadTimeout`).
  - **Age distribution across `24` verifiable `datePosted` postings:** **min `2.9 days`** (`bizimply` Senior SDET, `2026-11-16`), **median `50.8 days`**, **max `313.9 days`** (`indrive` Abuja `Business Development Manager`, `2026-01-09`), with **`8/24` `<= 30 days`**, **`8/24` `31–90 days`**, and **`8/24` `> 90 days`** (including evergreen/stale listings: `184.4d` `coforma`, `183.8d` `indrive` Senior Data Engineer, `202.8d` `davies` Lead Associate PO, `118.8d` `cfc` Senior ML Engineer, `118.6d` `frazil` Software Developer, `100.2d` & `113.1d` `sunking` Nigeria roles).
- **Feed/detail discrepancies & longitudinal freshness:**
  1. Detail HTML JSON-LD omits `hybrid` (`jobLocationType` only represents `TELECOMMUTE`), so detail-only enrichment yielded `work_model=None` on `hybrid` feed jobs (`sunking`, `indrive`, `cfc`, `davies`) and `work_model="remote"` on `confluence` `#29` (`hybrid` in feed vs prose phrase).
  2. Detail HTML JSON-LD emits only a single `applicantLocationRequirements` country (`Kenya` on Sun King dual-location `"Lagos, Nigeria or Nairobi, Kenya"` `#02`; `United Kingdom` on Sun King `"Job Location: Africa"` `#15`; `United States` on Surgo Health `"Remote - Global"` `#16`), diverging from multi-hub descriptions.
  3. One snapshot cannot establish long-term posting turnover or staleness decay; multi-day `BoardMonitor` tracking (`monitored_jobs.first_discovered_at`, `last_checked_at`, and `ETag` `304` checks) is the existing mechanism that collects longitudinal freshness over multiple days.

---

## 7. Nigerian Applicant Eligibility Findings

- **Automated feed eligibility safety (`840` postings):** `auto_nigeria_eligible`: **`0` `True`**, **`92` `False`**, **`748` `None`** — zero false Nigeria-eligibility claims.
- **Full-inventory Nigeria-referenced check (`43 / 840`):** `36` `sunking` `location.name="Nigeria"` postings, `1` `indrive` `location.name="Nigeria"` posting (`Business Development Manager`, `313.9d` old), `4` `sunking` `Africa` postings, and `2` `sunking` `Global`/`China` postings mentioning Nigeria. **`0` of those `43`** are core software/AI/data/DevOps roles (`36` Sun King `Nigeria` postings are retail/EasyBuy sales, phone repair, solar installation, and store operations; only `2` are adjacent hybrid `Global Analytics and Technology` roles at Sun King: `Senior Product Designer` & `PayG Phones TechOps Manager`).
- **30-Posting Manual Audit (Nigeria Eligibility):**
  - **`Eligible`: `7/30` (`23.3%`)** (`#01` Sun King `Senior Product Designer`, `#02` Sun King `PayG Phones TechOps Manager`, `#03` inDrive `BDM` Abuja, `#04` Sun King `Regional Phone Business Manager`, `#05` Sun King `Area Business Manager`, `#06` Sun King `Global Marketing Manager`, `#08` Sun King `SEO Specialist`) — **`0/7` core technical**, `2/7` adjacent design/TechOps, `5/7` non-technical.
  - **`Unverified`: `3/30` (`10.0%`)** (`#15` Sun King `Global Digital Sales Lead` — description says `"Africa"`, JSON-LD says `UK`; `#16` Surgo `Research Fellow AI` — `Remote - Global`, JSON-LD `US`; `#17` Surgo `Research Fellow LMIC` — detail timed out).
  - **`Restricted`: `20/30` (`66.7%`)** (`#07` Kenya-only, `#09–#14` Egypt-only, `#18–#30` US/UK/PT/IN/CA-only) — `12/20` core technical, `2/20` adjacent PM/PO, `6/20` non-technical.

---

## 8. Wider African Applicant Eligibility Findings

Across the same `30`-posting balanced sample (disjoint from `Restricted` outside Africa):

- **`Eligible` in Nigeria & Kenya (`4/30`):** `#01`, `#02`, `#06`, `#08` (Sun King dual Lagos/Nairobi descriptions).
- **`Eligible` in Nigeria only (`3/30`):** `#03` (inDrive Abuja), `#04`, `#05` (Sun King Nigeria states).
- **`Eligible` in Kenya only (`1/30`):** `#07` (`Mobile Security Technician`, Nairobi onsite).
- **`Eligible` in Egypt only (`6/30`):** `#09` (`bizimply` `Senior SDET`, Egypt `remote`, `2.9d` old), `#10–#14` (`indrive` Cairo `hybrid`: `Senior Backend`, `Platform/MLOps`, `Senior Data`, `Senior AI SWE`, `Middle CV ML`).
- **Total African-country eligible in sample: `14/30` (`46.7%`)** — all **`6/6` core technical postings** in the African sample are **Egypt-only** (Cairo hybrid or Egypt remote), **not open to Nigerian applicants**. Remaining **`3/30`** are `Unverified` and **`13/30`** are `Restricted` outside Africa.

<details>
<summary>Complete 30-Posting Live Sample Evidence Ledger (URLs, Freshness, Tech Tier, Nigeria &amp; Africa Eligibility)</summary>

| # | Slug & Title | Source URL | Feed Loc / WM | DatePosted (Age) | Detail / Apply | Tier / Sen | Nigeria Elig | Wider Africa Elig | Primary Evidence |
|---:|---|---|---|---|---|---|---|---|---|
| 1 | `sunking`: Senior Product Designer | [`77c61905`](https://sunking.pinpointhq.com/en/postings/77c61905-cb4d-45ba-91c6-9efbc6dc0a91) | `Africa` / `hybrid` | `None` (timeout) | `— / —` | Adj Design / Sr | **`Eligible`** | **NG + KE** | `"Job Location: Nairobi, Kenya or Lagos, Nigeria"` |
| 2 | `sunking`: PayG Phones TechOps Manager | [`fc6a5da5`](https://sunking.pinpointhq.com/en/postings/fc6a5da5-a44b-4911-a1ed-aa7c228d6ea9) | `Africa` / `hybrid` | `2026-10-07` (`42.7d`) | `200 / 200` | Adj TechOps / Sr | **`Eligible`** | **NG + KE** | `"Location : Lagos, Nigeria or Nairobi, Kenya."` (JSON-LD omitted NG -> KE only) |
| 3 | `indrive`: Business Development Manager | [`81d489e6`](https://indrive.pinpointhq.com/en/postings/81d489e6-36f6-4e42-acf5-8b2b8e99e3e9) | `Nigeria` / `hybrid` | `2026-01-09` (`313.9d`) | `200 / 200` | Non-tech / Sr | **`Eligible`** | **Nigeria** | City `Abuja`; JSON-LD `applicantLocationRequirements: Nigeria` |
| 4 | `sunking`: Regional Phone Business Manager | [`111e5eb7`](https://sunking.pinpointhq.com/en/postings/111e5eb7-da03-43eb-965a-7136e4aa6936) | `Nigeria` / `in_person` | `2026-08-11` (`100.2d`) | `200 / 200` | Non-tech / Sr | **`Eligible`** | **Nigeria** | `"Job Location: Abuja, Nigeria"`; JSON-LD `Nigeria` |
| 5 | `sunking`: Area Business Manager, Kafanchan | [`1c93cb2b`](https://sunking.pinpointhq.com/en/postings/1c93cb2b-8fdc-4ee8-bc32-6febf960ca7e) | `Nigeria` / `in_person` | `2026-07-29` (`113.1d`) | `200 / 200` | Non-tech / Sr | **`Eligible`** | **Nigeria** | `"Job Location: Kafanchan"`; `location.name="Nigeria"`; JSON-LD `Nigeria` |
| 6 | `sunking`: Global Marketing Manager | [`21382d3e`](https://sunking.pinpointhq.com/en/postings/21382d3e-69bd-4256-ae28-26853f824db4) | `Global` / `hybrid` | `None` (timeout) | `— / 200` | Non-tech / Sr | **`Eligible`** | **NG + KE** | `"Job Location: Lagos, Nigeria or Nairobi, Kenya"` |
| 7 | `sunking`: Mobile Security Technician. | [`448719b4`](https://sunking.pinpointhq.com/en/postings/448719b4-e359-4cde-b150-75d9c2d16d0d) | `Africa` / `in_person` | `2026-09-28` (`52.2d`) | `200 / 200` | Non-tech / Unc | **`Restricted`** | **Kenya** | `"Location: Nairobi, Kenya"` onsite; JSON-LD `Kenya` |
| 8 | `sunking`: SEO Specialist | [`8ae79995`](https://sunking.pinpointhq.com/en/postings/8ae79995-1d93-45e6-83fa-b777457e1381) | `Africa` / `hybrid` | `2026-10-26` (`23.9d`) | `200 / 200` | Non-tech / Unc | **`Eligible`** | **NG + KE** | `"Job Location: Lagos, Nigeria/Nairobi, Kenya"` |
| 9 | `bizimply`: Senior SDET | [`9be6a7d7`](https://bizimply.pinpointhq.com/en/postings/9be6a7d7-5b80-48a7-9673-7c48b225fb11) | `Egypt` / `remote` | `2026-11-16` (`2.9d`) | `200 / —` | Core QA / Sr | **`Restricted`** | **Egypt** | `location="Egypt"`, `city="Cairo"`, JSON-LD `Egypt` |
| 10 | `indrive`: Senior Backend Engineer | [`5cf6bb3a`](https://indrive.pinpointhq.com/en/postings/5cf6bb3a-8000-4875-8db2-4e673bbf0a86) | `Egypt` / `hybrid` | `None` (DNS) | `— / —` | Core BE / Sr | **`Restricted`** | **Egypt** | `location="Egypt"`, `city="Cairo"`, `hybrid` |
| 11 | `indrive`: Platform Engineer (AI/MLOps) | [`9acc9255`](https://indrive.pinpointhq.com/en/postings/9acc9255-a367-4601-a819-a9e3e35b03cc) | `Egypt` / `hybrid` | `2026-10-14` (`35.9d`) | `200 / 200` | Core AI/ML / Unc | **`Restricted`** | **Egypt** | Cairo `hybrid`; JSON-LD `Egypt` |
| 12 | `indrive`: Senior Data Engineer | [`9df9f2e4`](https://indrive.pinpointhq.com/en/postings/9df9f2e4-8e45-41b1-980e-75def01d1110) | `Egypt` / `hybrid` | `2026-05-19` (`183.8d`) | `200 / 200` | Core Data / Sr | **`Restricted`** | **Egypt** | Cairo `hybrid`; JSON-LD `Egypt` |
| 13 | `indrive`: Senior SWE (AI CS & Safety) | [`ba0a8994`](https://indrive.pinpointhq.com/en/postings/ba0a8994-7511-4c07-a170-1a0eaeb04f13) | `Egypt` / `hybrid` | `2026-08-26` (`84.8d`) | `200 / 200` | Core AI/ML / Sr | **`Restricted`** | **Egypt** | Cairo `hybrid`; JSON-LD `Egypt` |
| 14 | `indrive`: Middle ML Engineer (CV) | [`c24f7a18`](https://indrive.pinpointhq.com/en/postings/c24f7a18-ad17-4c0b-aceb-8d89005a7321) | `Egypt` / `hybrid` | `2026-10-15` (`34.8d`) | `200 / 200` | Core AI/ML / Mid | **`Restricted`** | **Egypt** | Cairo `hybrid`; JSON-LD `Egypt` |
| 15 | `sunking`: Global Digital Sales Lead | [`2deb6083`](https://sunking.pinpointhq.com/en/postings/2deb6083-7b0e-48a5-a529-68864197948c) | `Global` / `hybrid` | `2026-11-03` (`15.9d`) | `200 / 200` | Non-tech / Sr | **`Unverified`** | **`Unverified`** | Feed `Global`, desc `"Job Location: Africa"`, JSON-LD `UK` |
| 16 | `surgohealth`: Research Fellow (AI Study) | [`d21ce4c4`](https://surgohealth.pinpointhq.com/en/postings/d21ce4c4-e04e-4357-abbd-9e195a3f3c03) | `Remote - Global` / `remote` | `2026-10-06` (`44.0d`) | `200 / 200` | Non-tech / Unc | **`Unverified`** | **`Unverified`** | Tagged `Remote - Global`; JSON-LD `US`; $6k research grant |
| 17 | `surgohealth`: Research Fellow (LMIC) | [`e54ce00e`](https://surgohealth.pinpointhq.com/en/postings/e54ce00e-d7ba-4800-a20d-f58b2612f466) | `Remote - Global` / `remote` | `None` (timeout) | `— / 200` | Non-tech / Unc | **`Unverified`** | **`Unverified`** | Tagged `Remote - Global`; detail timeout |
| 18 | `coforma`: Evergreen Software Engineer | [`1a979aed`](https://coforma.pinpointhq.com/en/postings/1a979aed-0158-4d98-9470-18edf0bce6e7) | `Remote (select US states)` | `None` (timeout) | `— / 200` | Core SWE / Unc | **`Restricted`** | **`Restricted`** | US work authorization / select US states |
| 19 | `coforma`: Evergreen Automated Test (SDET) | [`4a295089`](https://coforma.pinpointhq.com/en/postings/4a295089-e9c6-4adf-8e7b-be9d2e8ba3c3) | `Remote (select US states)` | `None` (`2026-05-19` P1) | `— / —` | Core QA / Unc | **`Restricted`** | **`Restricted`** | US work auth / select US states (P1 JSON-LD `US`) |
| 20 | `coforma`: Evergreen DevSecOps Engineer | [`bd95e9e4`](https://coforma.pinpointhq.com/en/postings/bd95e9e4-564a-4f23-a28d-380f43d98e8f) | `Remote (select US states)` | `2026-05-19` (`184.4d`) | `200 / 200` | Core DevOps / Unc | **`Restricted`** | **`Restricted`** | JSON-LD `applicantLocationRequirements: United States` |
| 21 | `davies`: Field Motor Engineer - North West | [`1c6926e1`](https://davies.pinpointhq.com/en/postings/1c6926e1-4449-41e8-a9c2-93a64ea6a2cf) | `Home United Kingdom` / `remote` | `2026-09-25` (`55.0d`) | `200 / 200` | Non-tech / Unc | **`Restricted`** | **`Restricted`** | UK field motor inspection; JSON-LD `UK` |
| 22 | `davies`: Casualty Claims QA Auditor | [`acdd47e5`](https://davies.pinpointhq.com/en/postings/acdd47e5-8954-468d-9a9c-0083c5670b7d) | `Home United Kingdom` / `remote` | `2026-11-02` (`16.8d`) | `200 / 200` | Non-tech / Unc | **`Restricted`** | **`Restricted`** | UK insurance claims QA; JSON-LD `UK` |
| 23 | `davies`: Casualty Claims QA Auditor | [`cd1d5f77`](https://davies.pinpointhq.com/en/postings/cd1d5f77-5b4a-45a2-b3c5-9db8a52374b2) | `Home United Kingdom` / `remote` | `2026-09-29` (`50.8d`) | `200 / 200` | Non-tech / Unc | **`Restricted`** | **`Restricted`** | UK insurance claims QA; JSON-LD `UK` |
| 24 | `emergn`: Junior Full Stack (Python/Angular) | [`04a4231a`](https://emergn.pinpointhq.com/en/postings/04a4231a-a4b0-4f43-9840-f48237cb1545) | `Portugal - Nationwide` / `remote` | `2026-10-29` (`21.1d`) | `200 / 200` | Core Python / Jr | **`Restricted`** | **`Restricted`** | Portugal nationwide; JSON-LD `Portugal` |
| 25 | `davies`: Senior Associate - Full stack | [`204fb83d`](https://davies.pinpointhq.com/en/postings/204fb83d-52d0-43de-8002-4083b241a880) | `Pune` / `hybrid` | `2026-11-04` (`14.9d`) | `200 / 200` | Core BE/FE / Mid | **`Restricted`** | **`Restricted`** | Pune, India hybrid (`6-8 yrs`); JSON-LD `India` |
| 26 | `davies`: Lead Associate - Product Owner | [`2990b153`](https://davies.pinpointhq.com/en/postings/2990b153-43d3-46da-97a0-4d88b647b4e0) | `Pune` / `hybrid` | `2026-11-12` (`7.1d`) | `200 / 200` | Adj PO / Sr | **`Restricted`** | **`Restricted`** | Pune, India hybrid; JSON-LD `India` |
| 27 | `davies`: Lead Associate - Product Owner | [`3352dc0e`](https://davies.pinpointhq.com/en/postings/3352dc0e-f5e1-40e1-9927-81265836ad5e) | `Pune` / `hybrid` | `2026-04-30` (`202.8d`) | `200 / 200` | Adj PO / Sr | **`Restricted`** | **`Restricted`** | Pune, India hybrid; JSON-LD `India` |
| 28 | `cfc`: Senior Machine Learning Engineer | [`0a76a67b`](https://cfc.pinpointhq.com/en/postings/0a76a67b-2cc1-43d2-b448-33b9bdca8480) | `UK - London` / `hybrid` | `2026-07-23` (`118.8d`) | `200 / 200` | Core AI/ML / Sr | **`Restricted`** | **`Restricted`** | London hybrid; JSON-LD `United Kingdom` |
| 29 | `confluence`: Senior IT Infra Admin, DevOps | [`384b5076`](https://confluence.pinpointhq.com/en/postings/384b5076-238b-42d2-b1bd-af4b51076703) | `Montreal, Canada` / `hybrid` | `2026-11-06` (`13.0d`) | `200 / 200` | Core DevOps / Sr | **`Restricted`** | **`Restricted`** | Toronto/Montreal/Pittsburgh; JSON-LD `Canada` |
| 30 | `frazil`: Software Developer | [`34f7e623`](https://frazil.pinpointhq.com/en/postings/34f7e623-7ae1-44d0-87ef-4bcd848c64be) | `Salt Lake City, Utah` / `in_person` | `2026-07-23` (`118.6d`) | `200 / 200` | Core SWE / Unc | **`Restricted`** | **`Restricted`** | Fully onsite Utah, US; JSON-LD `United States` |

</details>

---

## 9. Relevant Technical-Role Yield and Seniority Breakdown

Strict classification across all `840` unique canonical postings (excluding non-software roles such as insurance claims QA audit, automotive motor/collision investigation, solar survey engineering, insurance wordings development, and generic retail/sales):

| Category Tier | Unique Postings (`840` total) | Share |
|---|---:|---:|
| **Core Technical (SWE / AI / Data / DevOps / GIS / QA)** | **116** | **13.8%** |
| — DevOps, Infra, Cloud, Security & Software QA/SDET | 39 | 4.6% |
| — Software Engineering (general) | 22 | 2.6% |
| — Backend / Frontend / Full-Stack | 17 | 2.0% |
| — AI & Machine Learning | 15 | 1.8% |
| — Data Engineering, Science & Analytics | 15 | 1.8% |
| — Python Development | 7 | 0.8% |
| — Geospatial / GIS | 1 | 0.1% |
| — Scientific & Research Software Engineering | 0 | 0.0% |
| **Adjacent Technology / Design / Product / TechOps** | **51** | **6.1%** |
| **Non-Technical (Sales, Field Ops, Claims, Finance, Marketing, HR)** | **673** | **80.1%** |

**Core Technical Seniority (`116`):** `62` `senior_experienced`, `7` `mid_level` (including `davies` Pune `Senior Associate` roles requiring `6-8` years), `3` `junior_entry` (`emergn` Portugal Junior Full Stack, `indrive` Egypt Junior QA, `sunking` India `SDE I`), `44` `unclear`, `0` `internship`, `0` `graduate`.

**Technical Yield by Eligibility Cohort:**
- **Total source inventory (`840`):** `116` core technical (`+51` adjacent).
- **Nigeria-eligible sample (`7`):** **`0` core technical** (`2` adjacent design/TechOps hybrid Lagos/Nairobi roles at Sun King). Across the full `43` Nigeria-referenced inventory, **`0` core technical**.
- **Wider Africa-eligible sample (`14`):** **`6` core technical** — all `6` Egypt-restricted (`bizimply` remote SDET + `5` `indrive` Cairo hybrid Backend/AI/ML/Data roles); **`2` adjacent** (Sun King Lagos/Nairobi).
- **Worldwide-eligible sample (`0` verified):** **`0`** core technical.
- **Unverified sample (`3`):** **`0`** core technical (`0` core SWEs).
- **Restricted outside Nigeria (`20`, incl. `6` Egypt-only):** `12` core technical (`2` adjacent PO, `6` non-technical).

---

## 10. Direct Routing, Monitoring, and Integration-Path Validation

Executed against live Pinpoint feeds using a fresh disposable SQLite database in `BOTTOM_POT_TEST_MODE=1` (`0` Serper credits; operational `data/` untouched):

1. **Direct Board Routing:** `probe_pinpoint_board` returned `4` (`1.7s`) for `pathify`, `2` (`1.6s`) for `bizimply`, `0` cleanly for `calligo` (empty), `brightsg` (`404`), and `cintra` (`301`); `probe_direct_boards(["pathify", "bizimply"], platforms=["pinpointhq"])` returned `6` listings across `2` distinct slugs. Larger `cfc` (`70` jobs) succeeded in `84.7s` in run 1 and failed at `28.5s` on retry (search-route contention).
2. **URL Parsing & Canonical Normalization:** Collapsed locale prefixes (`/en/`, `/pt-BR/`), uppercase UUIDs, `http://`, tracking params, and `/applications/new` or `/apply` suffixes cleanly to `https://{slug}.pinpointhq.com/postings/{uuid}`; rejected reserved subdomains and non-job board roots.
3. **Detail Page Enrichment:** Pre-fix live uncached `enrich_ats_page_result` returned `RETRYABLE_ERROR` (`status=None`) due to hardcoded `10.0s` timeout; **post-fix** returned `ExtractionOutcome.SUCCESS` (`200 OK`, `id="pinpointhq:pathify:5287daee-876a-4fd2-b6e2-ead3aa0c23e7"`, `posted_at=2026-08-09T23:19:39Z`, `elig=False`), and nonexistent UUID returned `ExtractionOutcome.NOT_FOUND`.
4. **Monitoring, Conditional `304`, Snapshot Reconciliation, & Error Isolation:** `BoardMonitor` Poll 1 persisted active jobs + `ETag` + SHA-256 fingerprint for `pathify` (`4`), `bizimply` (`2`), and `calligo` (`0`), while failing closed (`snapshot_complete=False`) on `brightsg` (`404`) and `cintra` (`301`). Immediate Poll 2 verified live **`HTTP 304 Not Modified`** (`not_modified=True`, `0` closures). Simulated `404`/`301`/`500` checks against populated `bizimply` kept `2/2` active jobs intact (`missing_confirmation_count=0`).
5. **Frontend Visibility:** `pinpointhq` is active across frontend `ALL_PLATFORMS` (`21`), `platformMigration.ts` (`v51`), and offline Vitest checks (`17` files / `116` tests passed).

---

## 11. Timeout and Performance Measurements

- **Feed timeout (`pinpoint_board_request_timeout_seconds = 25.0`):** Retained unchanged. Because `httpx` timeout governs socket connect/read inactivity between chunks rather than total download wall time, all **`19/19`** active non-empty feeds completed cleanly in Pass 2 — including slow multi-MB streams (`davies` `2.19 MB` in `165.8s`, max chunk gap `17.1s`; `indrive` `1.05 MB` in `101.6s`, max gap `9.2s`; `sunking` `1.43 MB` in `61.8s`, max gap `6.9s`; `intermedia` `465 KB` in `31.6s`, max gap `9.1s`). Increasing the feed timeout is unnecessary and would only extend hung-socket wait times during transient Pinpoint slowdowns.
- **Detail-page timeout (`ats_page_enricher.py`):** Live Pinpoint detail HTML pages frequently required `10s–43.3s` (`cfc` `43.3s`, `coforma` `16.9s` & `32.8s`, `emergn` `17.7s`, `scurri` `14.7s`, `sunking` `13.1s`). The hardcoded `10.0s` detail timeout systematically triggered `RETRYABLE_ERROR` on live uncached Pinpoint detail enrichment and was corrected.

---

## 12. Defects Found, Root Cause, Fix, and Regression Tests

- **Defect (High Priority):** `src/project_files/ats_page_enricher.py` hardcoded `timeout=10.0` in `fetch_page_with_cap` for `provider == "pinpointhq"`, ignoring `settings.pinpoint_board_request_timeout_seconds` (`25.0s`) and causing live uncached Pinpoint detail enrichment to time out (`ExtractionOutcome.RETRYABLE_ERROR`).
- **Root Cause:** Step 51 wired `resolve_pinpoint_board_timeout(...)` into `PinpointBoardAdapter` and `direct_board_router.py`, leaving `ats_page_enricher.py` on the generic `10.0s` default.
- **Fix Applied:** Updated [`src/project_files/ats_page_enricher.py`](../../src/project_files/ats_page_enricher.py) to use `resolve_pinpoint_board_timeout(bound_to_search_timeout=True)` when `provider == "pinpointhq"`, keeping `10.0s` unchanged for other providers.
- **Regression Test:** Added `test_15_pinpoint_detail_enrichment_uses_configured_timeout` in [`tests/test_pinpoint_monitoring.py`](../../tests/test_pinpoint_monitoring.py) (verified RED `10.0 != 25.0` before edit, GREEN `15/15` passed after edit, plus live uncached disposable-DB `enrich_ats_page_result` returning `SUCCESS`).

---

## 13. Final Pinpoint Assessment

- **Technical Success:** **Pass.** Feed parsing, canonical UUID normalization, `ETag`/`304`, fail-closed `404`/`301`/oversize handling, monitoring isolation, and post-fix detail enrichment all work safely and deterministically.
- **Coverage Success:** **Partial / Constrained.** Adds `840` unique postings across a new ATS ecosystem, but only `13.8%` (`116/840`) are core technical engineering/AI/data/DevOps roles (`3` early-career globally), large feeds take `31–166s`, and `33%+` of dated postings are `>90` days old (up to `313.9d`).
- **Applicant Value:** **Low for Nigeria / Worldwide Remote SWEs; Moderate for Egypt.** Zero Nigeria-located core software engineering roles (`0` across `43` Nigeria-referenced postings; `2` Lagos/Nairobi hybrid design/TechOps roles; `0` verified worldwide-remote SWEs), while Egypt has real engineering roles (`bizimply` remote SDET, `indrive` Cairo AI/ML/Backend/Data) that require Egyptian residency.
- **Overall Judgment:** **`Operationally accepted with limitations`** (`Constrained`). Retain Pinpoint as an implemented provider without spending another development cycle forcing higher Nigerian yield from an employer-population constraint.

---

## 14. Outstanding Limitations

1. Pinpoint `/postings.json` omits `posted_at` (`deadline_at` present on only `7.3%` of postings).
2. Slow Pinpoint server response/streaming times (`31–166s` for `450 KB–2.2 MB` feeds) can cause occasional `ReadTimeout` on `25s` stalls or hit `probe_pinpoint_board` latency limits on huge boards like `cfc`.
3. Detail HTML JSON-LD omits `hybrid` (`jobLocationType` only encodes `TELECOMMUTE`) and collapses multi-hub roles (e.g., `"Lagos, Nigeria or Nairobi, Kenya"`) to a single `applicantLocationRequirements` country (`Kenya`) or flags `Global` roles with employer HQ (`UK`/`US`).
4. Cross-source duplicate overlap against operational `data/cache.sqlite` was not measured per ADR 0030, and multi-day freshness decay requires ongoing `BoardMonitor` observation.

---

## 15. Next Source Recommendation

Advance immediately to **Step 53** to run a head-to-head empirical investigation (terms/permission gate, unauthenticated public feed schema, `ETag`/freshness, technical/early-career yield, and Nigeria/Africa/worldwide applicant eligibility) between:

1. **Gem ATS (`api.gem.com/job_board/v0/{vanity_url_path}/job_posts/`):** Public, unauthenticated official Job Board REST API returning single-payload active jobs with HTML/plain descriptions, `location_type` (`remote`/`hybrid`/`onsite`), `first_published_at` / `updated_at`, and `departments`/`offices` (`20 req/s` documented limit), heavily adopted by modern remote/AI tech startups.
2. **Manatal (`api.manatal.com/open/v3/career-page/{client_slug}/jobs/` & `open/v1/job-posts/`):** Official OpenAPI-documented public Career Page JSON API used across African, EMEA, APAC, and remote engineering employers.

Select and implement **only one** qualifying winner that clears all hard gates cleanly.
