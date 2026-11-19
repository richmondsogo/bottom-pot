# Step 53: Global Job Source Discovery, Permission, Technical Yield & 3-Dimensional Eligibility Audit

**Status:** Complete — **Audited `11` Live Candidates (`+16` Secondary Doc/Terms Screenings); `0` Approved (Path B: No Forced Integration)**  
**Date:** 2026-11-19  
**Branch:** `step/53-global-source-discovery-audit`  
**Base Commit (`main`):** `a4612587edace2c4791d0c7dc5666deb70bc4cea` (Merge PR #52)  
**Serper Credits Used:** `0`  
**Operational Data Modified:** None (`data/cache.sqlite`, WAL/SHM/journal sidecars, backups, forensic files, and absent `subscriptions.csv` untouched)  

---

## 1. Executive Summary & Path B Decision

Following the merge of PR #51 (`pinpointhq`: `64bc76b80e2539d790e46609f0599a3d5a01dd0c`) and PR #52 (Step 52 Pinpoint post-integration live performance validation + detail enrichment timeout fix: `a4612587edace2c4791d0c7dc5666deb70bc4cea`), Step 53 executed the authorized next-source empirical audit in `BOTTOM_POT_TEST_MODE=1` using zero Serper credits.

Eleven geographically and technically diverse candidate platforms were probed live against official endpoints, `robots.txt`, and governing legal/API terms:

1. **`JobScore`** (`careers.jobscore.com`)
2. **`Trakstar Hire / Recruiterbox`** (`jsapi.recruiterbox.com` / `hire.trakstar.com`)
3. **`Polymer`** (`api.polymer.co`)
4. **`Gem`** (`api.gem.com`)
5. **`Manatal`** (`api.manatal.com`)
6. **`ReliefWeb`** (`api.reliefweb.int`)
7. **`Zoho Recruit`** (`*.zohorecruit.com`)
8. **`SeamlessHiring`** (`*.seamlesshiring.com`)
9. **`Dover`** (`app.dover.com`)
10. **`Jobylon`** (`feed.jobylon.com`)
11. **`FactorialHR`** (`*.factorialhr.com`)

An additional `16` platforms (`Rippling ATS`, `We Work Remotely`, `HiBob`, `Homerun`, `JOIN`, `Gupy`, `Working Nomads`, `80,000 Hours`, `Fuzu`, `BeApplied`, `Occupop`, `Kula.ai`, `Deel`, `Keka`, `BrighterMonday`, `Jobberman Ghana`) underwent secondary documentation/terms screening (plus a direct endpoint/terms check on `TalentLyft`) before allocating full live census probes.

### Decision: Path B (No Forced Source Integration in Step 53)

**Zero of the `11` live-audited candidates passed both mandatory gates:**

1. **Permission, `robots.txt` & Terms Gate (`AGENTS.md` §8 Rule 5):** Every unauthenticated JSON feed inspected either explicitly restricts use to customer-internal / non-commercial / personal purposes, explicitly prohibits commercial republication/reproduction or availability monitoring (`Manatal`, `JobScore`, `Gem`, `Trakstar`, `Zoho Recruit`, `ReliefWeb`), blocks crawlers in `robots.txt` (`Trakstar` `hire.trakstar.com`, `Dover` `/api/`, `Jobylon` aggregator bots, `ReliefWeb` `api.reliefweb.int`, `Gem` `api.gem.com` `403`), or lacks any developer documentation or third-party redistribution grant (`Polymer`).
2. **Genuine Nigeria, Wider Africa & Worldwide Technical Applicant Value (`AGENTS.md` §8 Rules 1 & 3):**
   - Openly accessible non-blocked feeds (`Polymer`, `JobScore`, `Trakstar`, `Gem`) showed **`0` Nigeria-located roles**, **`0` Africa country codes**, and heavily US/EU/LatAm/India-restricted or severely stale inventories (median age `168.84d` on `Polymer`, `186.54d` up to `4,751.67d` on `JobScore`, `0` timestamps + `404` ghost URLs on `Trakstar`, and US/India-restricted roles on `Gem`).
   - Meanwhile Africa-present ecosystems (`Manatal`, `Zoho Recruit`, `SeamlessHiring`, `ReliefWeb`) failed the legal permission gate, CSR/login walls, or timestamp completeness (`0/330` `created_at` on `Manatal v3`, `0` SSR/JSON-LD on `Zoho Recruit` and `SeamlessHiring`, `403` without approved partner `appname` on `ReliefWeb v2`).

Per `AGENTS.md` §8 and [`docs/job-source-catalog.md`](../job-source-catalog.md), Bottom Pot optimizes for genuinely eligible, fresh technical roles open to applicants in Nigeria and wider Africa—not provider count. No production adapter code was written for any unqualified source. Instead, Step 53 records the complete empirical findings cleanly and synchronizes the catalog.

---

## 2. Master 11-Candidate Live Evaluation Matrix

| # | Candidate | Category | Source Geo | Primary Live Endpoint Probed | Probed & HTTP Outcomes | Permission / `robots.txt` / Terms | Contract & Freshness | Technical Yield & 3-Dim Eligibility | Status |
|---:|---|---|---|---|---|---|---|---|---|
| 1 | **`JobScore`** | Employer ATS | USA | `https://careers.jobscore.com/jobs/{slug}/feed.json` | `16` follow-up customer slugs: `8` non-empty `200`, `1` empty `200`, `6` `410`, `1` `404` (`82` unique jobs) | `careers.jobscore.com/robots.txt` `200` (`Disallow: /apply_flow/`); `agreements/terms_of_service/` bans commercial/public reproduction & redistribution | Single-GET JSON, `W/` `ETag` -> `304`; `82/82` dates, **median `186.54d`**, max **`4,751.67d`** (back to 2013); `remote=None` (`82/82`) | `37` broad tech-keyword (`2` early-career); `0` NG, `0` AF; `13` `"worldwide"` hits are `finalsite` marketing copy paired with US/LatAm/India residency locks | **`Rejected`** (`Unsuitable`) |
| 2 | **`Trakstar Hire`** (`Recruiterbox`) | Employer ATS | USA | `https://jsapi.recruiterbox.com/v1/openings?client_name={slug}` | `16` slugs: `9` non-empty `200` (`36` jobs), `6` empty `200`, `1` `400` | `jsapi` `robots.txt` allows `/`, **but `hire.trakstar.com/robots.txt` `Disallow: /`**; Mitratech Terms (`1.4.b`, `1.4.c`, `1.7.b`) ban reproduction & scraping; `v2` API requires Basic Auth | **`0/36` pub dates**, `etag=None`; **`404` ghost `hosted_url`s** on `avaaz` & `basecasecareers`; `400` on invalid slug | `11` tech-keyword (`4` early-career); `0` NG; `0` Africa country codes (`1` EMEA non-tech Dutch role whose `hosted_url` `404`ed) | **`Rejected`** (`Unsuitable`) |
| 3 | **`Polymer`** | Employer ATS | USA | `https://api.polymer.co/v1/hire/organizations/{slug}/jobs` | `30` orgs: `11` non-empty `200` (`38` jobs), `9` empty `200`, `10` `422` | `jobs.polymer.co/robots.txt` `200` empty; `/api` & `/developers` `404`; `polymer.co/terms` has no third-party redistribution grant | Single-GET JSON + detail `200` (`W/` `ETag` -> `304`, invalid `422`, `/v1/hire/jobs/{id}` `401`); `38/38` dates, **median `168.84d`**, max `921.89d` (incl. `830.44d` test job) | `14` core tech (`2` early-career); `0/38` Nigeria/Africa; remote tech US/CA/AU/NL-restricted or `679.65d` stale | **`Rejected`** (`Unsuitable`) |
| 4 | **`Gem`** | Employer ATS | USA | `https://api.gem.com/job_board/v0/{vanity_url_path}/job_posts/` | `22` slugs: `15` non-empty `200` (`196` jobs), `2` empty `200`, `5` `404` | `api.gem.com/robots.txt` **`403 Forbidden`**; `gem.com/compliance/terms` limits Services to Customer internal business purposes | Single-GET JSON (`etag=None`, `404` invalid slug/ID); `196/196` `first_published_at` (min `0.7d`, median `44.45d`, max `987.79d`), `0` dups | `55` core tech (`28.1%`, `5` early-career); **`0/196` Nigeria/Africa**; `16`-job sample US-restricted/PST/in-office or India-only | **`Rejected`** (`Unsuitable`) |
| 5 | **`Manatal`** | Employer ATS | Singapore / Global | `https://api.manatal.com/open/v3/career-page/{slug}/jobs/` | `23` slugs: `15` non-empty `200` (`330` jobs), `1` empty `200`, `7` `404` | `manatal.com/terms-and-conditions` explicitly bans accessing Services without written consent for **reproduction** or **availability/performance monitoring**; `robots.txt` `404` | **`0/330` pub dates** on `v3` list & detail (`estradaintl/jobs/432273` `created_at=None`); `etag=None`; `open/v1` `404`; `32` intra-board dups | `65` core tech (`19.7%`, `19` early-career); `11` NG (`3` tech), `97` AF (`1` tech), `17` WW refs — blocked by explicit ToS ban & zero dates | **`Rejected`** (`Unsuitable`) |
| 6 | **`ReliefWeb`** | Humanitarian aggregator | UN OCHA (Global) | `https://api.reliefweb.int/v2/jobs` | `v1` `410 Gone`; `v2` `400` (no `appname`) / `403` (unapproved `appname`) | `api.reliefweb.int/robots.txt` **`Disallow: /`**; `reliefweb.int/terms-conditions` prohibits resale, redistribution & derivative works without partner approval | Requires pre-approved `appname` token (`apidoc.reliefweb.int/parameters#appname`); `etag=None` on API | Not inspectable without approved `appname`; gated by ToS & API approval | **`Permission pending`** |
| 7 | **`Zoho Recruit`** | Employer ATS | India / Global | `https://{slug}.zohorecruit.com/jobs/Careers` (+ RSS/sitemap/detail) | `8` boards probed (incl. `flexisaf`, `habaripay`, `gtcoplc`, `appzonegroup`, `irecruitersafrica`, `dordar`, `tangramvision`, `audatic`): `7` `200` (`1.74–1.83 MB`), `1` `ReadTimeout` | `recruit.zoho.com/robots.txt` allows portals/RSS; `zoho.com/terms.html` bars providing services based on Services & third-party logos/names without consent | **CSR Lyte JS SPA** (`0` SSR job links, `0` JSON-LD on list & `dordar` detail); RSS/sitemap return `139 KB` Sign-In HTML without private `digest`; REST API needs OAuth 2.0 | Nigeria/Africa employers present (`flexisaf`, `habaripay`, `appzonegroup`), but technically & legally inaccessible without OAuth/JS browser execution | **`Rejected`** (`Unsuitable`) |
| 8 | **`SeamlessHiring`** | Employer ATS | Nigeria (SeamlessHR) | `https://{slug}.seamlesshiring.com` | `6` slugs (`seamlesshr`, `creditswitch`, `wemabank` `200`; `unifiedpayments`, `sterlingbank`, `interswitch` DNS failed) | `seamlesshr.com/terms-of-use/` `404`; `robots.txt` empty `Disallow:` | Laravel/Vue **CSR shell** (`0` SSR job links, `0` JSON-LD); no public API or RSS feed | Zero extractable structured job listings | **`Rejected`** (`Unsuitable`) |
| 9 | **`Dover`** | Employer ATS | USA | `https://app.dover.com/robots.txt`, `https://www.dover.com/terms` | Verified policies & robots (`110` HN slug leads identified) | `app.dover.com/robots.txt` **`Disallow: /api/`**; `dover.com/terms` restricts access to internal business purposes; API requires company key | API path blocked by `robots.txt` and authentication | Blocked at pre-census permission/`robots.txt` gate | **`Rejected`** (`Unsuitable`) |
| 10 | **`Jobylon`** | Employer ATS | Sweden / EU | `https://feed.jobylon.com/robots.txt`, `https://www.jobylon.com/terms` | Verified policies & robots | `feed.jobylon.com/robots.txt` explicitly sets **`Disallow: /`** across job aggregator crawlers (`JobrapidoBot`, `JoobleBot`, `CareerJet`, `AdzunaBot`, `JobliftBot`, `TalentBot`, `RecruitBot`, `JobsCrawler`, `JobSearchBot`, etc.); `/terms` `404` | Explicitly disallows job-aggregator bots | Blocked by explicit aggregator bot exclusion | **`Rejected`** (`Unsuitable`) |
| 11 | **`FactorialHR`** | Employer ATS | Spain / EU | `https://{slug}.factorialhr.com` | `3` slugs (`airy` `404`, `eedi` `200`, `revieve` `200`) | Authenticated REST API requires `x-api-key`/OAuth2; `/terms-of-service` `404` on `.com` | Public portal HTML has **`0` JSON-LD** and minimal SSR links (`0` on `eedi`, `1` on `revieve`) | EU SMB focus; no public API/JSON-LD contract | **`Rejected`** (`Unsuitable`) |

---

## 3. Detailed Empirical Findings & Three-Dimensional Eligibility Evidence

Per `AGENTS.md` §8 Rule 3, **Source geography**, **Job geography**, and **Applicant eligibility** were strictly separated across all inspected records.

### 3.1 JobScore (`careers.jobscore.com`) — **Rejected**
- **Permission & Docs:** `https://careers.jobscore.com/robots.txt` (`200 OK`) allows crawling (only `Disallow: /apply_flow/`). However, `https://www.jobscore.com/agreements/terms_of_service/` (`200 OK`) restricts Site materials to *"personal, non-commercial, and informational purposes"* and states: *"in no event may the materials be modified or redistributed... Any use of the Site not expressly granted herein is prohibited. You may not reproduce, republish, or publicly display, perform or distribute, or otherwise use the materials on the Site for any public or commercial purpose"*. Help Center documentation (`https://support.jobscore.com/hc/en-us/articles/202001320-Developers-Guide-to-Job-Feed-APIs`) scopes `feed.json` / `feed.xml` to *"deeper integration with your company's website or application, on paid plans"* (enforcing <= 1 poll/hour), while `https://developers.jobscore.com` Hire API v2 requires Enterprise customer or partner credentials (`partners@jobscore.com`). *(Note: `httpx` requests to `jobscore.com` fail brotli decoding unless `Accept-Encoding: gzip, deflate` is sent.)*
- **Census & Freshness (`16` customer follow-up slugs probed -> `8` non-empty `200 OK` totalling `82` unique live jobs, `1` valid empty `buysellads`, `6` `410 Gone`, `1` `404` `rayneo`):**
  - Native `W/` `ETag` (`304` verified) and full HTML descriptions, with `82/82` `opened_date`/`created_on`/`last_updated_date` timestamps — but severe staleness (`min 7.68d`, **median `186.54d`**, **max `4,751.67d`** with `ptp` holding `36` requisitions dating back to `2013`), and `remote=None` on `82/82` records.
- **Technical Yield & 3-Dim Eligibility (`82` jobs):**
  - Country distribution: `US: 61 (74.4%)`, `AU: 4`, `BR: 3`, `IN: 3`, `CA: 3`, `ID: 3`, `DE: 2`, `PE: 1`, `ES: 1`, `SG: 1` -> **`0/82` Nigeria, `0/82` Africa**.
  - `37` matched broad technical title keywords (including non-software `Solution Engineer`, `Engineering Coordinator`, and mining `Project Engineer`), with only `2` early-career matches (`NPI, Proving Ground Intern` US onsite; `Project Engineer I` DE hybrid).
  - **Counterexample — Marketing `"worldwide"` + `Anywhere` vs Domestic Residency Lock (`finalsite`):** All `13` `"worldwide"`/`"anywhere"` text hits in the `82`-job corpus matched `finalsite` company boilerplate (*"Finalsite supports more than 7,000 schools and districts worldwide"*), while the actual eligibility text stated:
    * US roles (`100% Remote in the U.S`, e.g., `Senior Database Administrator`, `Staff Engineer`): `"LOCATION 100% Remote - Anywhere within the US"` + `"RESIDENCY REQUIREMENT Finalsite offers 100% fully remote employment opportunities, however, these opportunities are limited to permanent residents of the United States."` -> **`Restricted`**.
    * Brazil roles (`Engineering Manager - Storefront`, `Senior Software Engineer - Payment Processing - Contract`): `"LOCATION 100% Remote - Anywhere within LatAm"` -> **`Restricted`**.
    * India roles (`Senior Application Security Engineer - India`): `"limited to permanent residents of India"` -> **`Restricted`**.
  - `16`-posting manual eligibility ledger: **`0/16`** Nigeria-, Africa-, or worldwide-eligible.

### 3.2 Trakstar Hire / Recruiterbox (`jsapi.recruiterbox.com` / `hire.trakstar.com`) — **Rejected**
- **Permission & `robots.txt`:** While `https://jsapi.recruiterbox.com/robots.txt` allows `/`, `https://hire.trakstar.com/robots.txt` (where `hosted_url` job and application pages live) returns `User-Agent: *` `Disallow: /`. `https://developers.recruiterbox.com/reference/recruiterbox-public-api.md` documents only authenticated `api.recruiterbox.com/v2/openings` via HTTP Basic Auth (`curl -u {api_key}:`). `https://www.trakstar.com/terms/` redirects to `https://mitratech.com/legal-notice/trakstar/trakstar-terms-and-conditions/`, whose Subscription Agreement limits usage to *"Client's internal purposes"* (`§1.4.c`), forbids reproduction/distribution (`§1.4.b`), and prohibits *"screen scraping"* / bots (`§1.7.b`).
- **Census, Freshness & Ghost-Job Defects (`16` slugs probed -> `9` active `200` totalling `36` unique jobs, `6` valid empty `200`, `1` `400` `agara`):**
  - `jsapi` omits creation timestamps (**`0/36` publication dates**), returns `etag=None`, returns `HTTP 400` on invalid client names (`{"client_name": "Invalid client name"}`), and exhibited active ghost-job desynchronization: both `https://avaaz.hire.trakstar.com/jobs/fk0py79/` and `https://basecasecareers.hire.trakstar.com/jobs/fk01x71/` returned **`HTTP 404`** on live HTML checks while `jsapi` still served them (`chaordic` `hosted_url` resolved under `Linx.hire.trakstar.com`, and `/rss` returned `404` on sampled hosts).
- **Technical Yield & 3-Dim Eligibility (`36` jobs):**
  - Countries: `United States: 22`, `Brasil: 8`, `(blank): 4`, `CA: 1` (`Richmond, CA`), `Germany: 1` -> **`0/36` Nigeria, `0/36` Africa country codes**.
  - `11` technical-keyword matches (`4` early-career, e.g., `Jr Software Engineer: Physical Modeling` in California, `Engenheiro(a) Dados JR` in Brasil). Only `1` posting mentioned Africa (`avaaz22194` non-tech part-time `Language Associate (Dutch)`, *"ideally be based in the European/Middle East/African time zones"*), and its `hosted_url` returned `HTTP 404`.

### 3.3 Polymer (`api.polymer.co`) — **Rejected**
- **Permission & Docs:** `jobs.polymer.co/robots.txt` returned `200 OK` (empty); however `https://www.polymer.co/api` and `https://www.polymer.co/developers` both returned `HTTP 404` (`developers.polymer.co` DNS failed), `sitemap.xml` listed no developer API docs, and `https://www.polymer.co/terms` (`Curious One, Inc.`) grants only Customer internal hiring use with no third-party job-board redistribution license.
- **Technical Schema vs Live Inventory (`30` orgs probed -> `11` non-empty `200` totalling `38` jobs, `9` empty `200`, `10` `422`):**
  - Polymer had the cleanest unauthenticated API schema inspected in Step 53 (`W/` `ETag` -> `304`, invalid ID/org `422`, `38/38` `published_at` timestamps, `salary_pretty`, `remote_restriction_country_residency_is_required`, `remote_restriction_country_list`, `remote_restriction_overlap_hours`).
  - However, live volume and freshness failed cleanly: only **`38` jobs** across `30` probed orgs (`14` core tech, `2` early-career), **median age `168.84 days`** (`min 3.14d`, **`max 921.89d`**), including `tablespace` `#31430` (`830.44d` old) whose description literally reads `"THIS IS NOT A REAL JOB. DO NOT APPLY. THIS IS A TEST ACCOUNT."` and `spatialise` `#33167` (`Intern Backend Engineer Python`, `679.65d` old). **`0/38`** jobs referenced Nigeria or Africa; sampled remote technical roles restricted residency (`['US']`, `['CA', 'US']`, `['AU']`, or `Beirut, LB`).

### 3.4 Gem (`api.gem.com`) — **Rejected**
- **Permission & `robots.txt`:** `https://api.gem.com/robots.txt` returned **`HTTP 403 Forbidden`** (`{"message":"Forbidden"}`); `https://jobs.gem.com/robots.txt` returned `404`; `https://www.gem.com/compliance/terms` grants a license *"solely for (i) Customer's internal business purposes and (ii) other purposes separately authorized by Gem Software in writing"* and bars reproducing, distributing, or commercially exploiting the Services. Developer docs (`developers.gem.com`) repeatedly terminated TLS connections (`WinError 10054`) during probing.
- **Census & Eligibility (`22` slugs probed -> `15` non-empty `200` totalling `196` jobs, `2` empty `200`, `5` `404`):**
  - `196/196` valid `first_published_at` timestamps (`min 0.7d`, median `44.45d`, max `987.79d`), `0` intra-board title/body dups, `404` on invalid slugs/IDs, `etag=None`, `55/196` (`28.1%`) core tech (`5` early-career).
  - **Eligibility failure:** **`0/196` Nigeria mentions**, **`0/196` Africa mentions**. Across the `16`-job detailed sample, `cloudraft` roles were `"India - Remote"`, `bluesky` roles required US/Pacific (`PST`) working-hour overlap + US travel, `nominal` defense software roles were US onsite (`New York, NY, Los Angeles, CA, Austin, TX`), and `faraday`/`accelos`/`bikky`/`converge` were US in-office.

### 3.5 Manatal (`api.manatal.com/open/v3/career-page/{slug}/jobs/`) — **Rejected**
- **Permission Gate Blocker:** Unlike the open ATS APIs above, Manatal **does** host real Nigerian and African hiring (`11` Nigeria references / `3` core tech such as `estradaintl` `Network Systems Engineer` and `plentytechjobs` `DevOps Engineer` & `Java Developer` in Lagos, `97` Africa references, `17` worldwide references across `330` jobs on `15` active feeds out of `23` probed). **However**, `https://www.manatal.com/terms-and-conditions` (`Effective Date: September 7 2026`) explicitly prohibits scraping/monitoring without consent:
  > *"You may not, without Manatal’s prior written consent, access the Manatal Services: for reproduction purposes; if you are a competitor of Manatal; to monitor the availability, performance or functionality of the Manatal Services; or for other benchmarking or competitive purposes."*
- **Additional Technical Disqualifiers:** **`0/330` publication dates** (`created_at=None, updated_at=None` verified on both the `v3` list endpoint and `estradaintl` detail `#432273`), `open/v1` public list route returned `404`, `etag=None`, `32` intra-board duplicate postings, and heavy staffing-agency dominance.

### 3.6 ReliefWeb (`api.reliefweb.int/v2/jobs`) — **Permission Pending**
- `https://api.reliefweb.int/v1/jobs?limit=5` returned **`410 Gone`** (decommissioned).
- `https://api.reliefweb.int/v2/jobs?limit=5` returned `400 BadRequestHttpException` (`Missing appname parameter`), and supplying an unregistered `appname=bottom-pot-eval` returned **`403 AccessDeniedHttpException`** (*"You are not using an approved appname"*).
- `https://api.reliefweb.int/robots.txt` serves `User-agent: *` `Disallow: /`, and `https://reliefweb.int/terms-conditions` permits only *"personal, non-commercial use, without any right to resell or redistribute them or to compile or create derivative works therefrom"*.

### 3.7 Zoho Recruit (`*.zohorecruit.com`) — **Rejected**
- Probed `8` tenant career portals (`flexisaf`, `habaripay`, `gtcoplc`, `appzonegroup`, `irecruitersafrica`, `dordar`, `tangramvision`, `audatic`). Although `recruit.zoho.com/robots.txt` explicitly allows `/jobs/*`, `/recruit/Portal.na`, `/recruit/ViewJob.na`, `/recruit/downloadrssfeed`, and `/recruit/sitemapfeed`:
  1. `/jobs/Careers` (`1.74–1.83 MB` HTML) and individual job pages (`dordar_job`, `1.74 MB`) are client-rendered **Lyte JS SPAs** containing **`0` SSR job links** and **`0` JSON-LD** metadata (`audatic` timed out).
  2. `/recruit/downloadrssfeed` and `/recruit/sitemapfeed` returned a `139,719`-byte **Zoho Sign-In HTML page** without each tenant's private `digest` token (or a Client Portal HTML page on `irecruitersafrica`), and official REST endpoints require OAuth 2.0.
  3. `https://www.zoho.com/terms.html` restricts use to internal business purpose and prohibits providing *"any service based on the Services without prior written permission"* or using third-party logos/company names without prior written permission.

### 3.8 SeamlessHiring (`*.seamlesshiring.com`) — **Rejected**
- Probed `6` Nigerian corporate & bank slugs: `seamlesshr`, `creditswitch`, and `wemabank` returned `200 OK` Laravel/Vue SPA shells with **`0` SSR job links** and **`0` JSON-LD** metadata; `unifiedpayments`, `sterlingbank`, and `interswitch` failed DNS (`ConnectError: [Errno 11001] getaddrinfo failed`); `https://seamlesshr.com/terms-of-use/` returned `404` (`https://seamlesshr.com/ats-and-recruitment-management-software/` + `/legal/privacy-policy/` returned `200`); no public JSON API or RSS feed exists.

### 3.9 Dover, Jobylon, and FactorialHR — **Rejected**
- **`Dover`** (`app.dover.com`): `https://app.dover.com/robots.txt` disallows `/api/`; API access requires a company key; `https://www.dover.com/terms` licenses Services strictly for Customer's internal business purposes.
- **`Jobylon`** (`feed.jobylon.com`): `https://feed.jobylon.com/robots.txt` explicitly blocks job aggregator bots (`Disallow: /` for `JobrapidoBot`, `JoobleBot`, `CareerJet`, `AdzunaBot`, `JobliftBot`, `NeuvooBot`, `TalentBot`, `RecruitBot`, `JobsCrawler`, `JobSearchBot`, `Jobdigger`, etc.); `https://www.jobylon.com/terms` returned `404`.
- **`FactorialHR`** (`*.factorialhr.com`): `airy` `404`, `eedi` `200` (`0` JSON-LD, `0` SSR job links), `revieve` `200` (`0` JSON-LD, `1` link); Factorial's REST API requires `x-api-key`/OAuth2 authentication.

---

## 4. Secondary Documentation & Terms Screening (`16` Additional Global Sources + `TalentLyft`)

*(Sources below were screened via official documentation, legal terms, `robots.txt`, or light contract checks and were stopped prior to launching full 15–30 board census sweeps where an immediate auth, terms, or non-JSON-LD blocker held.)*

| Candidate / Ecosystem | Screening Evidence & Blocker Observed | Step 53 Disposition |
|---|---|---|
| **`TalentLyft`** (`api.talentlyft.com`) | Direct probe of `api.talentlyft.com/v2/public/talentlyft/jobs` returned `200 OK` empty `{"Results":[],"Count":0}`, `api.talentlyft.com/robots.txt` `404`, `talentlyft.com/en/terms-of-use` `404`; search docs indicate tenant-scoped `/v2/public/{subdomain}/jobs` for company career sites under Master Subscription Agreement rather than open third-party syndication. | Not advanced (no open third-party redistribution grant / empty sample) |
| **`Rippling ATS`** (`ats.rippling.com` / `api.rippling.com`) | Previously **Retired** in [Step 32](steps/32-global-ats-monitoring-registry.md). Docs confirm core v2 API requires tenant OAuth/tokens while unauthenticated `api.rippling.com/platform/api/ats/v1/board/{slug}/jobs` is internal career-widget plumbing omitting full list descriptions and creation dates (`1+N` detail calls required). | Keep **`Retired`** |
| **`We Work Remotely`** | Public RSS & API "Do's and Don'ts" (`weworkremotely.com`) explicitly forbid using WWR data/API to build a competing search service or job board for finding remote workers, and forbid bypassing `weworkremotely.com` application routing. | Not advanced (direct ToS conflict) |
| **`HiBob`**, **`Homerun`**, **`JOIN`**, **`Gupy`**, **`Kula.ai`**, **`Deel`**, **`Keka`** | Official developer documentation (`apidocs.hibob.com`, `api.homerun.co/v2/`, `api.join.com`, `developers.gupy.io`, `kula.ai`, `developer.deel.com`, `keka.com`) requires Bearer tokens, JWTs, or OAuth 2.0 per-tenant credentials (`401` unauthenticated; Homerun XML feed requires tenant-generated account URL). | Not advanced (auth-gated) |
| **`Working Nomads`**, **`80,000 Hours`**, **`Fuzu`**, **`BeApplied`**, **`Occupop`**, **`BrighterMonday` (`KE`)**, **`Jobberman` (`GH`)** | No open unauthenticated developer API/RSS for third-party ingestion; `BrighterMonday`/`Jobberman` Terms forbid automated extraction/robots/screen-scraping without prior written consent; `Working Nomads` API/Sponsorship is commercial partner-only; `Fuzu`/`80,000 Hours`/`BeApplied`/`Occupop` lack public syndication APIs. | Not advanced (no public API / ToS-restricted) |

---

## 5. Repository Cleanliness, Safety & Verification

- **Active Code Trace Audit (`src/` and `frontend/src/`):** Case-insensitive pattern scan across all source files for `jobscore`, `trakstar`, `recruiterbox`, `polymer`, `manatal`, `zohorecruit`, `seamlesshiring`, `dover`, `jobylon`, `factorialhr`, `\bgem\b`, and `reliefweb` returned **`0` matches** (`AGENTS.md` §8 Rule 7 satisfied).
- **Local Verification Gates:** Run via Step 53 PR validation (`scripts/check_db_safety.py`, `scripts/verify.ps1`, and `scratch/verify_baseline.py` confirming `MATCH_BASELINE: True` across all operational files in `data/` and absent `subscriptions.csv`).

---

## 6. Strategic Recommendation for Step 54

Instead of adding low-yield or legally ambiguous ATS integrations, **Step 54 should expand active monitored employer-board depth across Bottom Pot's existing `9` native ATS adapters** (`Ashby`, `Greenhouse`, `Lever`, `Workable`, `Recruitee`, `Teamtailor`, `SmartRecruiters`, `Personio`, and qualified global `Pinpoint` employers):

1. Use `Discovery-only` ethical lead sources already verified in Step 51 (`OpenToAfrica`, `RemoteWork.ng`, direct company career directories) solely to extract **primary employer ATS slugs** hosted on Ashby, Greenhouse, Lever, Workable, Recruitee, and Teamtailor—turning Step 51's `100%` overlap observation (`OpenToAfrica` `10/10` native ATS redirects) into durable, direct-to-employer `BoardMonitor` coverage with verified `ETag` / `datePosted` / canonical apply links.
2. Only revisit `Manatal` or `ReliefWeb` (`api.reliefweb.int/v2/jobs`) if explicit written API / redistribution partner permission (`appname` approval or commercial consent) is obtained first.
