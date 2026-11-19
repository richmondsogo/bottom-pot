# Step 51: Global Job Source Discovery, Eligibility & Permission Audit, and First Qualified Integration (`pinpointhq`)

**Status:** Complete — **1 Qualified Source Integrated (`pinpointhq`)** (Draft PR #51)  
**Date:** 2026-11-18  
**Branch:** `step/51-global-source-discovery`  
**Base Commit (`main`):** `3d36c343f4f478d3f6340a70290877567d06a028` (Merge PR #50)  
**Selected & Integrated Source:** **`Pinpoint`** (`pinpointhq`, `https://{slug}.pinpointhq.com/postings.json`) — Rank **#1 (`86/100`)**, **Approved & Implemented**  
**Non-Selected Candidates:** `Jobicy` (`Discovery-only` / constrained), `Get on Board` (`Permission pending`), `Python.org Jobs` (`Permission pending` / `Discovery-only`), `OpenToAfrica` (`Discovery-only`), `RemoteWork.ng` (`Discovery-only`), `Remote OK` (`Permission pending`), `Himalayas` (`Discovery-only` / `Permission pending`), `Remotive` (`Discovery-only` / `Permission pending`), `US-RSE` (`Discovery-only`), `Arbeitnow` (`Permission pending`), `Hasjob` (`Permission pending`), `Habr Career` (`Permission pending`), `HeadHunter` (`Permission pending`), `Blognone Jobs` (`Discovery-only`), `ThailandDev` (`Rejected` — DNS failure), plus screened regional/niche boards (`NodeFlair`, `TokyoDev`, `OfferZen`, `Wuzzuf`, `Hatch`, `FOSSJobs`, `DevITjobs`, `Earthworks`, `NaijaRemoteJobs`).  

---

## 1. Executive Summary

Following the rejection and removal of Breezy HR (`breezy`) in Step 50, Step 51 executed a deliberative, globally scoped job source discovery audit across **9 geographic macro-regions** and specialist technical domains, grounded in the permanent mandate in `AGENTS.md`:

- **Discover globally, evaluate locally relevant eligibility:** Never restrict discovery to countries already represented in Bottom Pot's ATS configuration, and never infer applicant eligibility from where a job board is operated, where an employer is headquartered, where a job is geographically located, or a generic `remote` flag.
- **Permission and quality before volume:** Public HTTP accessibility (`200 OK` without auth) is **not** redistribution permission. Every candidate underwent an explicit permission gate and a `>= 10`-job empirical eligibility inspection before ranking on the 100-point rubric.
- **Select at most one qualifying source:** Implement only the highest-scoring candidate that passes **all** hard gates cleanly.

### Key Findings & Decision

1. **Selected Single Source for Step 51 Integration — Pinpoint (`pinpointhq`) (`86/100`, Approved -> Implemented):**
   - **Authoritative Public Feed & Permission Clarity:** Unlike Breezy's undocumented `/json` feed, Pinpoint officially documents `GET https://{company-subdomain}.pinpointhq.com/postings.json` ([`developers.pinpointhq.com/docs/job-feeds-overview.md`](https://developers.pinpointhq.com/docs/job-feeds-overview.md), [`jobs-json-endpoint.md`](https://developers.pinpointhq.com/docs/jobs-json-endpoint.md)) as an unauthenticated, CORS-enabled public endpoint specifically designed for external job displays and custom boards ([`help.pinpoint.support/.../embedding-job-listings-on-an-external-website`](https://help.pinpoint.support/en/articles/17141546-embedding-job-listings-on-an-external-website)). Documented IP rate limits are `120 requests / ~1 min` and `240 requests / ~8 min` ([`rate-limits.md`](https://developers.pinpointhq.com/docs/rate-limits.md)), and tenant `robots.txt` (`workwithus`, `pathify`, `sunking`) explicitly permits `User-Agent: *` crawling of `/postings.json`, `/jobs.rss`, and public `/postings/*` pages.
   - **Real Nigeria, Africa, Global Remote & Technical Incremental Value:** Probing **20 diverse Pinpoint tenant subdomains** returned **`17` active `200 OK` boards totaling `552` live postings** (`+2` live valid empty `{"data":[]}` boards `calligo` & `teachingstrategies`, `+1` `301` redirect `cintra -> pssg`). Notable high-signal boards include **`sunking.pinpointhq.com`** (`183` jobs: **`36` directly in Nigeria** + **`3` pan-Africa roles** explicitly listing `"Lagos, Nigeria or Nairobi, Kenya"` in `Global Analytics and Technology`, `83.6%` Africa total), **`indrive.pinpointhq.com`** (`161` jobs across 26 countries including `48` technical/engineering/AI/ML/geospatial roles across Nigeria, Egypt, South Africa, Morocco, Tunisia, and UAE/Cyprus/Kazakhstan), and **`bizimply.pinpointhq.com`** (`Egypt - Fully Remote Senior SDET`), alongside Python, AI/ML, quantitative engineering, and full-stack openings across Europe, North America, and Australia.
   - **Technical Reliability & Single-GET Completeness:** Single `GET /postings.json` returns complete HTML descriptions (`description`, `key_responsibilities`, `skills_knowledge_expertise`, `benefits`), structured `workplace_type`, `employment_type`, `job.department`, structured `compensation_*` (`compensation_visible` flag), immutable UUID URLs (`/en/postings/{uuid}`) alongside numeric `id`, clean `404` on closed jobs, and honors weak `ETag` `If-None-Match` with **`HTTP 304 Not Modified` (`0` bytes)**.
   - **ADR 0001 Boundary Observed:** `/postings.json` omits `datePosted` / creation timestamps (`deadline_at` is the application deadline and must never be used as `posted_at`). Therefore `PinpointBoardAdapter` and `probe_pinpoint_board` leave `posted_at=None`, while individual posting HTML pages (`{slug}.pinpointhq.com/en/postings/{uuid}`) provide embedded Schema.org `JobPosting` JSON-LD `datePosted` when enriched via `ats_page_enricher.py`.

2. **Why All Other Strong Candidates Were Deferred (`Discovery-only`, `Permission pending`, or `Rejected`):**
   - **`Jobicy` (`64/100`, Rank #2 — `Discovery-only` / Constrained):** Explicitly allows job board reuse under `/jobs-rss-feed` Section 10 & 12, **but**: (a) the free `/api/jobs` endpoint replaces direct employer URLs with `https://jobicy.com/jobs/...` and requires paid Commercial API access (`$0.01/job`) to obtain direct employer ATS links; (b) `jobicy.com/terms-and-conditions` still retains conflicting boilerplate prohibiting retrieval-system storage/redistribution; (c) across **1,000 traversed 7-day jobs**, `44.9%` (`449/1000`) are `USA`-only, `?get=locations` contains **zero African countries**, **`12/12`** sampled `EMEA` engineering jobs were Europe-only (`0/12` Nigeria), and **`Anywhere` (`15/1000`, `1.5%`)** technical jobs (`Supabase`, `Canonical`) are delayed reposts of Ashby and Greenhouse boards already monitored directly.
   - **`Get on Board` (`58/100`, Rank #3 — `Permission pending`):** Technically solid JSON API (`ETag` + full fields), but Terms and Conditions (`Version 1.2`, Nov 17, 2026, Sections 8 & 14) restrict API consumption to client recruitment integrations and prohibit publishing/distributing Get on Board IP; `12/12` sampled programming jobs were Chile/LATAM-focused (`0/12` Nigeria-eligible).
   - **`Python.org Jobs` (`56/100`, Rank #4 — `Permission pending` / `Discovery-only`):** High technical signal (`3/12` `Remote, Worldwide`, `1` UNICEF), but `21` total active jobs globally, `<item>` omits `<pubDate>` (requiring `1+N` HTML fetches), and `python.org/about/legal/` reserves copyright without an explicit republishing license.
   - **`OpenToAfrica` (`55/100`, Rank #5 — `Discovery-only`) & `RemoteWork.ng` (`53/100`, Rank #6 — `Discovery-only`):** High Nigeria/Africa applicant relevance, **but** no public API or redistribution license, and empirical URL inspection shows **`10/10` (`100%`)** of sampled postings link directly to Ashby (`7`), Workable (`2`), and Greenhouse (`1`) (plus Lever/Recruitee on `RemoteWork.ng`) employer boards already supported natively by Bottom Pot. Best used as ethical **`Discovery-only`** employer-slug intelligence.
   - **`Remote OK` (`52/100`, Rank #7), `Himalayas` (`49/100`, Rank #8), `Remotive` (`44/100`, Rank #9):** Blocked by direct-apply-URL stripping, 24h delays (`Remotive`), commercial fees (`$5k/mo`), or redistribution restrictions.

---

## 2. Global Geographic & Technical Niche Coverage Matrix (25 Investigated Sources)

Discovery deliberately covered all **9 required geographic markets** and specialist technical niches (`25` total sources investigated with `0` Serper credits consumed):

| # | Source | Category | Source Geography | Regions & Markets Covered | Technical / Niche Focus | Access Mechanism Tested (2026-11-18) | Lifecycle Status |
|---|---|---|---|---|---|---|---|
| 1 | **`Pinpoint`** (`pinpointhq`) | Employer ATS | UK (Jersey HQ) | Global, West/East/North/Southern Africa, UK/EU, US, AU, LATAM, South Asia | Software eng, AI/ML, data, geospatial, InfoSec, Product, DevOps | `GET https://{slug}.pinpointhq.com/postings.json` (`17/20` live boards, `552` jobs) | **`Implemented`** (#1, `86/100`) |
| 2 | **`Jobicy`** | International remote-only board | International (US/EU) | Primarily USA (`44.9%`), EU/UK (`EMEA` = Europe), LATAM, APAC; `1.5%` `Anywhere` | Tech, AI, Data, DevOps, Design, Marketing | `GET https://jobicy.com/api/v2/remote-jobs` (`1,000` jobs traversed) | **`Discovery-only`** (#2, `64/100`) |
| 3 | **`Get on Board`** | Regional tech job board | Chile / LATAM | Latin America (Chile, Mexico, Colombia, Peru, LATAM remote) | Software engineering, Java/Spring, React/TS, QA, DevOps | `GET https://www.getonbrd.com/api/v0/categories/programming/jobs` (`29` pages) | **`Permission pending`** (#3, `58/100`) |
| 4 | **`Python.org Jobs`** | Specialist language job board | Global (PSF, US) | Global (`Remote, Worldwide`), US, EU, UK | Python, Django/FastAPI, ML/AI research, scientific computing | `GET https://www.python.org/jobs/feed/rss/` (`20/21` items) + HTML detail | **`Permission pending`** (#4, `56/100`) |
| 5 | **`OpenToAfrica`** | Curated African remote aggregator | Africa / Global | West/East/North Africa & EMEA/Worldwide remote | Software engineering, AI/ML, Data, Security (`330` listings) | HTML (`https://opentoafrica.com/`) — no public API | **`Discovery-only`** (#5, `55/100`) |
| 6 | **`RemoteWork.ng`** | Regional Nigerian remote aggregator | Nigeria (West Africa) | Nigeria-screened global remote roles | Tech, Operations, Tutor, Finance (Next.js RSC HTML) | HTML (`https://remotework.ng/jobs`) — no public API | **`Discovery-only`** (#6, `53/100`) |
| 7 | **`Remote OK`** | International remote-only board | US / Global | Global, predominantly US/EU timezones | Software engineering, AI, Data, Product (`642 KB` JSON) | `GET https://remoteok.com/api` (`200 OK`) | **`Permission pending`** (#7, `52/100`) |
| 8 | **`Himalayas`** | International remote-only board | Australia / Global | Global remote with explicit country restrictions | Tech, Product, Engineering | `GET https://himalayas.app/jobs/api` (`50,424 B` limit=5) | **`Discovery-only`** (#8, `49/100`) |
| 9 | **`Remotive`** | International remote-only board | France / EU | Global, US, Europe | Software Dev, Data, Product, Design (`254 KB` limit=5) | `GET https://remotive.com/api/remote-jobs` (24h delayed) | **`Discovery-only`** (#9, `44/100`) |
| 10 | **`US-RSE Job Board`** | Specialist Research SWE board | USA (North America) | North America (US universities, labs, federal contractors) | Research Software Engineering, HPC, AI/ML forecasting (`19` jobs) | `GET https://us-rse.org/api/jobs.json` (`5,408 B`) | **`Discovery-only`** (#10, `43/100`) |
| 11 | **`Arbeitnow`** | Regional tech/general board | Germany (EU DACH) | Germany / DACH (onsite & German-remote) | Working students (`Werkstudent`), internships, German-speaking tech (`300`/page) | `GET https://www.arbeitnow.com/api/job-board-api` (gzip) | **`Permission pending`** (#11, `41/100`) |
| 12 | **`Hasjob`** | Regional tech community board | India (South Asia) | India (Bengaluru, Mumbai, Hyderabad, India remote) | DevOps, AI systems, Cybersecurity interns, startups (`17` Atom items) | `GET https://hasjob.co/feed` (`57,523 B` Atom) | **`Permission pending`** (#12, `38/100`) |
| 13 | **`Habr Career`** | Regional tech community board | Russia & CIS | Russia (Moscow, St. Petersburg, RU remote) | Russian-language SWE, backend, data, QA (`25`/page) | HTML (`career.habr.com/vacancies`); API requires OAuth 2.0 (`career.habr.com/info/api`) | **`Permission pending`** (#13, `34/100`) |
| 14 | **`HeadHunter (hh.ru)`** | Regional job portal | Russia & CIS | Russia, Kazakhstan, Belarus, CIS | Broad general & tech | `GET https://api.hh.ru/vacancies` -> **`HTTP 403 Forbidden`** (OAuth/commercial key required) | **`Permission pending`** (#14, `30/100`) |
| 15 | **`Blognone Jobs`** | Regional tech media job board | Thailand (SEA) | Thailand (Bangkok/local) | Thai-market software & IT | `https://jobs.blognone.com/` (`47,664 B` SPA HTML, no public feed/API) | **`Discovery-only`** (#15, `28/100`) |
| 16 | **`ThailandDev`** | Regional dev portal (lead) | Thailand (SEA) | Unreachable | — | `https://thailanddev.com/` -> **`ConnectError` (`getaddrinfo failed`)** | **`Rejected`** (#16, `0/100`) |
| 17 | **`NaijaRemoteJobs`** | Nigerian remote blog/board | Nigeria (West Africa) | Nigeria remote (`WP HTML`, `101 KB`) | General remote + Nigerian listings | WordPress HTML; no documented redistribution API | Screened (`Discovery-only`) |
| 18 | **`TokyoDev`** | Regional foreign-friendly tech board | Japan (East Asia / APAC) | Japan / Japan relocation | English-speaking SWE in Japan (`gzip` HTML, JS-driven) | `https://www.tokyodev.com/jobs` (no public JSON API / AU-NZ/JP focus) | Screened (`Permission pending`) |
| 19 | **`NodeFlair`** | Regional APAC tech board | Singapore (SEA/APAC) | Singapore, Malaysia, Vietnam, APAC | Tech salaries & SWE in SEA | HTML/SSR portal (APAC-localized) | Screened (`Permission pending`) |
| 20 | **`Hatch`** | Early-career / intern platform | Singapore (SEA/APAC) | Singapore / APAC internships | Entry-level & university graduates in APAC | Web portal (`hatch.sg`); local SG/APAC | Screened (`Permission pending`) |
| 21 | **`OfferZen`** | Tech talent marketplace | South Africa & Netherlands | South Africa (Cape Town/JHB) & EU | Invite/employer-bid marketplace for SA/NL developers | Auth-gated reverse marketplace (`offerzen.com`); no public job feed | Screened (Not applicable) |
| 22 | **`Wuzzuf`** | Regional MENA job portal | Egypt (North Africa) | Egypt & MENA | High-volume local MENA general & tech hiring | Web portal (`wuzzuf.net`); onsite/Egypt-resident focus | Screened (`Permission pending`) |
| 23 | **`FOSSJobs`** | Open-source software board | Europe / Global | Open-source projects worldwide | FOSS engineering | `https://www.fossjobs.net/rss/` returned HTML `text/html` (`6,504 B`), not RSS | Screened (Low activity) |
| 24 | **`DevITjobs`** | Transparent-salary EU/UK/CH/DE tech | UK / Germany / Switzerland | UK, Germany, Switzerland (local authorization) | SWE with mandatory salary bands | Local country residency/work-auth required | Screened (Local EU/UK only) |
| 25 | **`Earthworks / GIS`** | Specialist geospatial & geoscience | UK / Global | Worldwide academic, GIS, climate, geospatial | Geospatial, remote sensing, scientific computing | Legacy HTML index without structured API or license | Screened (`Permission pending`) |

*Note on geographic distribution across Australia & New Zealand:* Coverage of AU/NZ appeared directly inside evaluated global sources—specifically Pinpoint boards (`pathify.pinpointhq.com` in Melbourne/Australia, `cfc.pinpointhq.com` Australia roles) and Jobicy (`Australia`, `APAC, Australia` tags), while Pinpoint's architecture uniformly covers NZ/AU employers using `*.pinpointhq.com`.

---

## 3. Three-Dimensional Separation Framework (Empirical Evidence)

Throughout Step 51, **Source geography**, **Job geography**, and **Applicant eligibility** were logged as independent dimensions:

1. **Counterexample 1 — UK ATS Hosting Direct African Engineering (`Pinpoint` — `sunking.pinpointhq.com` & `indrive.pinpointhq.com`):**
   - *Source geography:* Pinpoint HQ (`pinpointhq.com`) is incorporated in Jersey (UK Channel Islands).
   - *Job geography & Applicant eligibility:* Yet `sunking.pinpointhq.com` hosts **`183` live jobs of which `153/183` (`83.6%`) are in Africa** and **`38/183` explicitly target Nigeria** (`36` tagged `Nigeria` + pan-Africa roles `593610` `PayG Phones TechOps Manager` and `581464` `Senior Product Designer` in `Global Analytics and Technology` specifying *"Location: Lagos, Nigeria or Nairobi, Kenya"*). Meanwhile `indrive.pinpointhq.com` hosts `1` Nigeria role, `9` Egypt roles (`Senior Data Engineer`, `Senior Backend Engineer`, `Platform Engineer (AI/MLOps)`, `Middle ML Engineer (Computer Vision)`, `Junior QA Engineer`), `3` South Africa, `2` Morocco, and `2` Tunisia roles.
2. **Counterexample 2 — Aggregator `EMEA` Label Masking Europe-Only Restrictions (`Jobicy`):**
   - *Source geography:* Global remote aggregator (`jobicy.com`).
   - *Job geography metadata:* `jobGeo: "EMEA"`.
   - *Applicant eligibility:* On **`12/12`** sampled recent `EMEA` engineering jobs (`163127`, `163124`, `163121`, `163116`, `163114`, `163113`, `163106`, `163099`, `163065`, `155731`, plus `163125`/`163122` excluding France/Italy/Germany), actual geo/description constraints pointed to **Netherlands, Ireland, Poland, Spain, Germany, France, Portugal, or European Union residency**—`0/12` verified Nigerian eligibility.
3. **Counterexample 3 — Nigerian/African Curated Boards Hosting Existing Global ATS Postings (`OpenToAfrica` & `RemoteWork.ng`):**
   - *Source geography:* Africa-targeted aggregators.
   - *Applicant eligibility:* High (`10/10` sampled OpenToAfrica jobs open to Africa/Nigeria/Worldwide).
   - *Incremental value:* Zero unique direct listings—`10/10` (`100%`) of sampled `OpenToAfrica` jobs and the inspected Next.js rows on `RemoteWork.ng` link to **Ashby, Greenhouse, Lever, Workable, and Recruitee** employer boards that Bottom Pot can monitor at the primary source!
4. **Counterexample 4 — `Fully remote` Label Paired with Domestic Residence Lock (`Pinpoint` — `Pathify` & `WorkWithUs`):**
   - `pathify.pinpointhq.com` job `558423` (`Software Engineer`, Python/Django/Angular/TS) has `workplace_type: "remote"` and `workplace_type_text: "Fully remote"`, **but** `location.name: "Australia (Remote)"` and `skills_knowledge_expertise` states `Work remotely from anywhere in Australia` + `Unrestricted working rights in Australia` -> **`Restricted`** (`nigeria_eligible=False`).
   - `workwithus.pinpointhq.com` job `591998` (`Staff Product Designer`) has `workplace_type: "remote"` (`"Remote"`), **but** description states *"This is a remote role based in the UK, Portugal, Spain or Poland"* -> **`Restricted`**.

---

## 4. Detailed Technical & Terms Evaluation of Top Candidates (15 Dimensions)

### 4.1 Pinpoint (`pinpointhq`) — Selected Source
1. **Official website & operator:** Pinpoint HQ (`https://www.pinpointhq.com`, `https://developers.pinpointhq.com`, Channel Islands / UK SaaS ATS).
2. **Source category:** Employer ATS / career board.
3. **Source geography:** United Kingdom (Jersey).
4. **Intended audience & markets:** Multi-region employers using Pinpoint ATS (`sunking`, `indrive`, `bizimply`, `cfc`, `intermedia`, `emergn`, `tradingtechnologies`, `whiteswandata`, `surgohealth`, `confluence`, `scurri`, `coforma`, `pathify`, `workwithus`).
5. **Official API / feed mechanism:** Documented `GET https://{slug}.pinpointhq.com/postings.json` (plus `/jobs.rss` / `/jobs.xml`), returning `{"data": [...]}`; HTML detail pages at `https://{slug}.pinpointhq.com/en/postings/{uuid}` embed Schema.org `JobPosting` JSON-LD.
6. **Authentication requirements:** None (unauthenticated, CORS enabled).
7. **Published usage & redistribution terms:** `developers.pinpointhq.com/docs/job-feeds-overview.md` (`updatedAt: 2026-06-02`), `jobs-json-endpoint.md` (`2026-04-20`), and `help.pinpoint.support/.../17141546-embedding-job-listings-on-an-external-website` (`2026-09-24`) explicitly document using `/postings.json` to display employer openings on external job websites and custom career experiences. `robots.txt` allows `/postings.json` and public `/postings/*` while disallowing unlisted flagged postings and `/mydata`, `/admin`, `/companies`.
8. **Attribution & application links:** Preserves canonical `url` (`/en/postings/{uuid}`) and direct `/applications/new` ATS apply route with full employer identity.
9. **Complete job descriptions:** Yes — single `GET` returns full HTML `description`, `key_responsibilities`, `skills_knowledge_expertise`, and `benefits` (`desc=True` on all 17 non-empty active boards).
10. **Identity & canonical URL stability:** Stable UUID path (`/en/postings/{uuid}`) plus numeric `id` (`"558423"`); `/applications/new`, locale prefixes (`/en/`, `/pt-BR/`), and `/postings/{uuid}` normalize cleanly to `https://{slug}.pinpointhq.com/postings/{uuid}`.
11. **Freshness, publication dates & closure behavior:** `/postings.json` omits creation timestamps (exposes `deadline_at` only; `posted_at` stays `None` per ADR 0001; detail HTML JSON-LD provides `datePosted`). Closed jobs return `HTTP 404` on detail pages and vanish cleanly from `/postings.json` (empty board returns `{"data":[]}`).
12. **Pagination, rate limits & conditional requests:** Unpaginated single response (`?page=2`, `?limit=1` return identical payload hash); documented IP rate limits (`120 req/1 min`, `240 req/8 min`, `HTTP 429` with `RateLimit-*` & `Retry-After`); emits weak `ETag` (`W/"..."`) and returns `HTTP 304 Not Modified` (`0` B) on `If-None-Match`. Note: renamed tenants return `HTTP 301` (e.g. `cintra -> pssg`) and large boards (`sunking` 1.40 MB, `indrive` 1.04 MB, `davies` 2.18 MB) stream slowly (`15–20s`), requiring a `>=15s` adapter timeout and `3 MiB` cap (`follow_redirects=False`).
13. **Geographic & applicant restrictions:** Real mix across boards: Nigeria/Africa onsite, hybrid, & remote (`sunking`, `indrive`, `bizimply`), EU/UK remote (`workwithus`, `emergn`), US remote (`intermedia`, `coforma`), Australia remote (`pathify`). Requires per-job eligibility extraction.
14. **Incremental value:** **Very High** — zero overlap with existing `MONITORABLE_PROVIDERS`; unlocks direct Nigeria/Egypt/Kenya/Africa tech, AI/ML, and geospatial pipelines (`Sun King`, `inDrive`, `Bizimply`, etc.).
15. **Maintenance cost:** Low (~500 lines adapter + URL parser/normalizer + router, reusing existing resilience/registry/monitor infrastructure).

### 4.2 Summary Audits of Other Top Candidates (Dimensions 1–15 Condensed)

| Candidate | Operator & Category | Official API / Auth | Terms / Redistribution Reality | Identity, Completeness, Freshness & Pagination | Blocker / Decision Reasoning |
|---|---|---|---|---|---|
| **`Jobicy`** | Jobicy (`jobicy.com`), Remote Aggregator | `GET /api/v2/remote-jobs` (`?count=100&cursor=...`), no auth for free tier; Bearer key for Commercial API | `/jobs-rss-feed` §10/§12 permits display with credit, **but** requires keeping apply links pointing to `jobicy.com` unless paying (`$0.01/job` Commercial API), and `/terms-and-conditions` conflicts ("no retrieval system/redistribution") | Cursor pagination (24h expiry, max 7-day window -> **1,000 jobs** observed); full HTML descriptions; numeric ID; `pubDate` present; no `ETag` | **Do not ingest free API**: breaks Bottom Pot direct-ATS link principle, `44.9%` US-only, `0` Africa countries in `?get=locations`, `Anywhere` tech jobs mirror Ashby/Greenhouse |
| **`Get on Board`** | Get on Board (`getonbrd.com`), LATAM Tech Board | `GET /api/v0/categories/{cat}/jobs`, `search/jobs`, no auth | **TOS v1.2 (2026-11-17) §8 & §14**: explicitly restricts API to Client recruitment systems; forbids reproducing/publishing/distributing GoB IP | Clean JSON:API IDs, `per_page`/`total_pages`, weak `ETag`, `published_at` Unix timestamps, structured `remote_modality` (`hybrid`, `remote_local`, `fully_remote`) | **`Permission pending`**: TOS prohibits third-party job board republication; `0/12` Nigeria eligibility |
| **`Python.org Jobs`** | Python Software Foundation (`python.org/jobs/`), Specialist Board | `GET /jobs/feed/rss/` (`20` items of `21` active), no auth | `python.org/about/legal/` states **"All rights reserved"** with no permission for third-party job-board redistribution | Numeric `/jobs/{id}/` stable URLs; RSS omits `<pubDate>` (date `<time datetime>` & external apply links require `1+N` HTML detail fetches) | **`Permission pending` / `Discovery-only`**: Tiny inventory (`21` total jobs), missing `<pubDate>` in RSS, no clear redistribution grant |
| **`OpenToAfrica`** | OpenToAfrica (`opentoafrica.com`), African Curated Board | HTML only (`216 KB` homepage), no JSON/RSS API | Copyright site; no API or redistribution grant | Aggregator pages (`330` jobs) linking out to **Ashby, Workable, Greenhouse** | **`Discovery-only`**: `10/10` (`100%`) overlap with existing Bottom Pot ATS adapters |
| **`RemoteWork.ng`** | RemoteWork (`remotework.ng`), Nigerian Screened Remote Board | Next.js RSC HTML (`156 KB`), no public API | Copyright site; no redistribution grant | Row keys in React payload (`ashby_camunda_...`, `greenhouse_canonical_...`) directly embed upstream ATS IDs | **`Discovery-only`**: Already covered at primary ATS source (`Ashby`, `Greenhouse`, `Lever`, `Workable`, `Recruitee`) |
| **`Remote OK`** | Remote OK (`remoteok.com/api`), International Remote Board | `GET /api` (`642 KB` array), no auth | Embedded `legal` notice requires `follow` backlink to `remoteok.com`; `apply_url` routes through `remoteok.com` | Unpaginated JSON array, ISO dates, numeric `id`, partial tags/locations | **`Permission pending`**: Requires aggregator funnel backlink instead of direct employer ATS links; high noise (`Freelance Question Reviewers`, US/EU locks) |
| **`Himalayas`** | Himalayas (`himalayas.app/jobs/api`), Remote Board | Cursor JSON API, no auth | Terms prohibit replacing `applicationLink` (`himalayas.app/...`) with employer links and forbid job-board redistribution | Rich schema (`locationRestrictions`, `timezoneRestrictions`, `minSalary`), cursor pagination | **`Discovery-only` / `Permission pending`**: Explicit redistribution & direct-link prohibition |
| **`Remotive`** | Remotive (`remotive.com/api/remote-jobs`), Remote Board | Public JSON API, no auth | `0-legal-notice`: 24h delay, warns against submitting jobs to third-party job sites, requires traffic to `remotive.com`, paid API `$5k/mo` | JSON with company, category, `candidate_required_location`, 24h delay | **`Discovery-only` / `Permission pending`**: Explicit third-party job-board restriction |
| **`US-RSE`** | US Research Software Engineer Assoc (`us-rse.org/api/jobs.json`), Specialist | Static JSON (`5.4 KB`, `19` jobs), no auth | Community volunteer board; no open redistribution license stated | **4 summary fields only** (`title`, `published`, `location`, `url`), no descriptions, no pagination | **`Discovery-only`**: Useful exclusively for discovering external ATS URLs (`icims`, `lever`, `workable`, `workday`) |
| **`Arbeitnow`** | Arbeitnow (`arbeitnow.com/api/job-board-api`), German Board | Paginated JSON (`300`/page, gzip), no auth | Attribution link required; reserves revocation for aggregators | German-heavy metadata, `remote` bool, tags, Unix `created_at` | **`Permission pending`**: `10/10` DACH/Germany-focused (`0/10` Nigeria) |
| **`Hasjob`** | Hasgeek (`hasjob.co/feed`), India Tech Board | Atom feed (`17` entries), no JSON API | No third-party redistribution license | Full Atom XML with timestamps, company domains in URLs | **`Permission pending`**: `10/10` India-focused (`0/10` Nigeria) |
| **`Habr Career`** | Habr (`career.habr.com`), Russian Tech Board | Official API requires OAuth 2.0 registration (`career.habr.com/info/api`) | OAuth client agreement required; no public feed | Russian-language HTML cards (`25`/page) | **`Permission pending`**: Auth required; Russian market (`0/10` Nigeria) |
| **`HeadHunter`** | HeadHunter (`api.hh.ru`), Russian/CIS Aggregator | `GET /vacancies` -> **`403 Forbidden`** | Requires registered commercial client / OAuth | Blocked without approved client | **`Permission pending`**: HTTP `403` unauthenticated |
| **`Blognone Jobs`** | Blognone (`jobs.blognone.com`), Thailand Tech | Client-side SPA HTML (`47 KB`), no API/RSS | No public API/terms | JS-rendered Thailand board | **`Discovery-only`**: No feed; local Thailand audience |
| **`ThailandDev`** | `thailanddev.com` (lead) | DNS lookup failed (`getaddrinfo failed`) | Inactive/unreachable domain | None | **`Rejected`**: Dead lead |

---

## 5. Applicant Eligibility Investigation (Live Sample Tables, 2026-11-18)

All samples below were collected live on **2026-11-18** and classified strictly under `Eligible`, `Restricted`, or `Unverified` keeping Source Geography, Job Geography, and Applicant Eligibility separate.

### 5.1 Pinpoint (`pinpointhq`) — Cross-Board Probe (`20` Boards Probed, `552` Live Jobs) & `16`-Job Eligibility Sample

**Board-Level Census (`20` subdomains probed):**
`sunking` (`183` jobs: `36` Nigeria, `3` Africa incl. Lagos/Nairobi, `153` Africa total), `indrive` (`161` jobs: `1` Nigeria, `9` Egypt, `3` South Africa, `2` Morocco, `2` Tunisia, `48` technical/AI/geospatial), `cfc` (`70`), `intermedia` (`46`), `tradingtechnologies` (`21`), `whiteswandata` (`16`), `surgohealth` (`12`), `confluence` (`11`), `emergn` (`8`), `propellerindustries` (`6`), `scurri` (`5`), `coforma` (`5`), `pathify` (`4`), `frazil` (`4`), `workwithus` (`3`), `bizimply` (`2`), `arkatechture` (`1`); plus `calligo` (`0` jobs, `{"data":[]}` `11 B`), `teachingstrategies` (`0` jobs, `{"data":[]}` `11 B`), and `cintra` (`HTTP 301` redirect to `pssg.pinpointhq.com`). `brightsg` & `rowden` returned `404`; `davies` streamed `2.18 MB` (`2,176,520 B`); `receptive` SSL-timed out.

| # | Board / ID | Job Title & Dept | Source & Employer Direct URL (`url`) | Source Geo | Job Geo (`location.name` / `workplace_type`) | Classification (Nigeria/Africa) | Observed Evidence & Requirements |
|---|---|---|---|---|---|---|---|
| 1 | `sunking` `593610` | `PayG Phones TechOps Manager` (`Global Analytics and Technology`) | [`sunking.../fc6a5da5...`](https://sunking.pinpointhq.com/en/postings/fc6a5da5-a44b-4911-a1ed-aa7c228d6ea9) | UK ATS | `Africa` (`hybrid`) | **`Eligible`** (Nigeria & Kenya) | Description: *"Location : Lagos, Nigeria or Nairobi, Kenya"* |
| 2 | `sunking` `581464` | `Senior Product Designer` (`Global Analytics and Technology`) | [`sunking.../77c61905...`](https://sunking.pinpointhq.com/en/postings/77c61905-cb4d-45ba-91c6-9efbc6dc0a91) | UK ATS | `Africa` (`hybrid`) | **`Eligible`** (Nigeria & Kenya) | Description: *"Job Location: Nairobi, Kenya or Lagos, Nigeria"* |
| 3 | `sunking` `590613` | `Phone Repair Technician, Lagos (Nigeria)` (`Operations`) | [`sunking.../d64213c7...`](https://sunking.pinpointhq.com/en/postings/d64213c7-deea-4831-8db5-0d7198f47b34) | UK ATS | `Nigeria` (`onsite`) | **`Eligible`** (Nigeria) | Explicit Lagos, Nigeria location (`location.name="Nigeria"`) |
| 4 | `sunking` `532681` | `Area Business Manager, Afikpo (Ebonyi State)` | [`sunking.../b306cc95...`](https://sunking.pinpointhq.com/en/postings/b306cc95-0800-407e-833d-f49b2a411b11) | UK ATS | `Nigeria` (`onsite`) | **`Eligible`** (Nigeria) | *"Job Location: Afikpo, Ebonyi State"* (`location.name="Nigeria"`) |
| 5 | `sunking` `612705` | `Global Digital Sales Lead – Call Center` | [`sunking.../2deb6083...`](https://sunking.pinpointhq.com/en/postings/2deb6083-7b0e-48a5-a529-68864197948c) | UK ATS | `Global` (`hybrid`) | **`Unverified`** | Tagged `Global` + `hybrid`; physical office city not globally universal |
| 6 | `indrive` `438001` | `Business Development Manager` (`Delivery`) | [`indrive.../81d489e6...`](https://indrive.pinpointhq.com/en/postings/81d489e6-36f6-4e42-acf5-8b2b8e99e3e9) | UK ATS | `Nigeria` (`hybrid`) | **`Eligible`** (Nigeria) | Explicit `Nigeria` location & *"Nigeria context"* |
| 7 | `indrive` `568336` | `Senior Software Engineer (AI Customer Support & Safety)` | [`indrive.../ba0a8994...`](https://indrive.pinpointhq.com/en/postings/ba0a8994-7511-4c07-a170-1a0eaeb04f13) | UK ATS | `Egypt` (`hybrid`) | **`Eligible`** (Egypt / African regional) / **`Restricted`** (Nigeria onsite/hybrid) | Python/FastAPI AI role in Cairo, Egypt (African tech hub, hybrid local) |
| 8 | `indrive` `599240` | `Platform Engineer (Backend, AI Platform, MLOps)` | [`indrive.../9acc9255...`](https://indrive.pinpointhq.com/en/postings/9acc9255-a367-4601-a819-a9e3e35b03cc) | UK ATS | `Egypt` (`hybrid`) | **`Eligible`** (Egypt) / **`Restricted`** (Nigeria) | Python/Kubernetes/Databricks MLOps in Cairo, Egypt |
| 9 | `indrive` `511388` | `Senior Data Engineer` (`Data Platform`) | [`indrive.../9df9f2e4...`](https://indrive.pinpointhq.com/en/postings/9df9f2e4-8e45-41b1-980e-75def01d1110) | UK ATS | `Egypt` (`hybrid`) | **`Eligible`** (Egypt) / **`Restricted`** (Nigeria) | Python/Airflow/Kafka in Egypt; local hybrid hub |
| 10 | `indrive` `550655` | `Senior Geospatial Software Engineer - Maps & AV Data` | [`indrive.../d06be546...`](https://indrive.pinpointhq.com/en/postings/d06be546-854d-4af9-9fab-05e825f934da) | UK ATS | `United Arab Emirates` (`hybrid`) | **`Restricted`** (outside UAE) | Relocation/hybrid presence in UAE hub required |
| 11 | `bizimply` `620107` | `Senior SDET (Cypress / Playwright)` | [`bizimply.../9be6a7d7...`](https://bizimply.pinpointhq.com/en/postings/9be6a7d7-5b80-48a7-9673-7c48b225fb11) | UK ATS | `Egypt` (`remote`) | **`Eligible`** (Egypt / North Africa) / **`Unverified`** (Nigeria) | `location="Egypt"`, `city="Cairo"`, `workplace_type="remote"` (`Fully remote`) |
| 12 | `bizimply` `574391` | `Sales Development / Account Executive – North` | [`bizimply.../7bb07804...`](https://bizimply.pinpointhq.com/en/postings/7bb07804-bfef-40f4-b85e-fad1e897f5e3) | UK ATS | `UK` (`remote`) | **`Restricted`** | *"based in the North of England... outside the area will not be progressed"* |
| 13 | `pathify` `558423` | `Software Engineer` (Python/Django/Angular/TS) | [`pathify.../5287daee...`](https://pathify.pinpointhq.com/en/postings/5287daee-876a-4fd2-b6e2-ead3aa0c23e7) | UK ATS | `Australia (Remote)` (`remote`) | **`Restricted`** | *"Work remotely from anywhere in Australia"* + *"Unrestricted working rights in Australia"* (AU$135k–165k) |
| 14 | `workwithus` `591998` | `Staff Product Designer` | [`workwithus.../fa79e602...`](https://workwithus.pinpointhq.com/en/postings/fa79e602-e5a1-4ee7-9cee-3bb2a13eb20a) | UK ATS | `Remote` (`remote`) | **`Restricted`** | *"remote role based in the UK, Portugal, Spain or Poland"* |
| 15 | `workwithus` `610925` | `Senior Technical Success Engineer` (Python/APIs/AI) | [`workwithus.../6fc547ee...`](https://workwithus.pinpointhq.com/en/postings/6fc547ee-7139-41eb-92c8-add28d89e8c5) | UK ATS | `Remote` (`remote`) | **`Restricted`** | *"Anywhere in the UK, Spain, Portugal or Poland"* (EOR in ES/PT/PL) |
| 16 | `emergn` `568948` | `Full Stack Developer (Python & Angular)` | [`emergn.../548bf192...`](https://emergn.pinpointhq.com/en/postings/548bf192-c8a4-423a-92eb-528f2c5da70e) | UK ATS | `Portugal - Nationwide` (`remote`) | **`Restricted`** | Portugal nationwide remote lock |

**Summary:** Out of `16` sampled multi-board postings, **`5/16`** are directly Nigeria-eligible (`sunking` + `indrive`), **`4/16`** additional roles target North/East Africa (`Egypt`, `Kenya`) technical engineering (`indrive`, `bizimply`), **`1/16`** is `Unverified` (`Global` hybrid), and **`7/16`** (plus regional Egypt/UAE splits) clearly self-identify country restrictions in structured fields/descriptions so Bottom Pot can filter out restricted roles accurately!

### 5.2 Jobicy (`1,000` Jobs Traversed + `12` Engineering + `12` EMEA + `Anywhere` Breakdown)

**Full 7-Day Feed Traversal (`10` sequential cursor pages, `1,000` jobs):**
- `USA`-only: **`449/1000` (`44.9%`)**; `UK`: `65`; `Canada`: `36`; `Europe`: `35`; `Germany`: `23`; `Canada, USA`: `22`; `Brazil`: `22`; `Spain`: `18`; `LATAM`: `15`; `Poland`: `15`; `Anywhere`: **`15/1000` (`1.5%`)**; `EMEA`: **`13/1000` (`1.3%`)**; African countries explicitly listed in `?get=locations`: **`0` (`zero`)**.

**Recent Engineering Sample (`12` jobs from `?tag=python`/API & `12` `EMEA` jobs):**
- Recent general engineering batch (`J1`–`J12`, `163168` `Sayari` USA -> `163106` `Cross River` Spain): `5` US/Canada (`4` `Restricted`, `1` `Sayari` `Remote, US` `Restricted`), `7` EU/UK (`BJAK` Netherlands/Ireland/Poland/Spain, `Fivetran` Germany, `Elevenlabs` DK/FR/NL/PL/UK/US, `Cross River` Spain — all Europe/US restricted -> **`0/12` Nigeria `Eligible`**).
- Recent `EMEA` engineering sample (`12` jobs: `163127` `BJAK Applied AI` NL, `163124` `BJAK Mobile` IE, `163121` `BJAK Backend` PL, `163116` `BJAK Full Stack` ES, `163114` `Fivetran Principal Data Lakes` DE, `163113` `Elevenlabs` EU/US, `163106` `Cross River` ES, `163099` `Mozilla SpiderMonkey` FR, `163065` `SingleStore` PT, `155731` `Bloomreach Staff Python` Europe, plus `163125` & `163122` `Consensys` `EMEA` — **`0/12` verified Nigeria-eligible**, all tagged `EMEA` on European country restrictions).
- `Anywhere` slice (`15/1000` total): Non-tech roles include `Language Services Associates` interpreters (`155762`, `155758`, `155566`); tech roles are `Supabase` (`153453`, `153449`, `153446`, `162979`), `Canonical` (`155703`), and `Windranger Labs` (`153447`) — **all Ashby/Greenhouse direct boards already supported by Bottom Pot**.

### 5.3 Get on Board (`12`-Job Programming Category Sample)

| # | Job ID | Title | URL (`getonbrd.com/jobs/...`) | Job Geo (`countries` / `remote_modality`) | Applicant Eligibility |
|---|---|---|---|---|---|
| G1 | `semi-senior-full-stack-java-developer-qa-ai-bilingue-23people-santiago` | Semi Senior Full-Stack Java Developer (QA & AI) | [`23people`](https://www.getonbrd.com/jobs/semi-senior-full-stack-java-developer-qa-ai-bilingue-23people-santiago) | `['Chile']` / `hybrid` | **`Restricted`** |
| G2 | `software-engineer-full-stack-xintec-santiago-13d8` | Software Engineer Full-Stack | [`xintec`](https://www.getonbrd.com/jobs/software-engineer-full-stack-xintec-santiago-13d8) | `['Chile']` / `hybrid` | **`Restricted`** |
| G3 | `senior-product-engineer-kudert-remote` | Senior Product Engineer | [`kudert`](https://www.getonbrd.com/jobs/senior-product-engineer-kudert-remote) | `['Remote']` / `remote_local` (Spanish) | **`Restricted`** |
| G4 | `desarrollador-full-stack-senior-42labs-santiago` | Full-Stack Sr (Java, Spring Boot, Angular, Apigee) | [`42labs`](https://www.getonbrd.com/jobs/desarrollador-full-stack-senior-42labs-santiago) | `['Chile']` / `hybrid` | **`Restricted`** |
| G5 | `software-engineer-grupo-lagos-santiago-543b` | Software Engineer (6 Meses) | [`grupo-lagos`](https://www.getonbrd.com/jobs/software-engineer-grupo-lagos-santiago-543b) | `['Chile']` / `hybrid` | **`Restricted`** |
| G6 | `senior-software-engineer-employment-law-firm-remote` | Senior Software Engineer | [`employment-law`](https://www.getonbrd.com/jobs/senior-software-engineer-employment-law-firm-remote) | `['Remote']` / `fully_remote` (`lang=en`) | **`Unverified`** (no global designation) |
| G7 | `senior-engineering-manager-even-remote` | Senior Engineering Manager | [`even`](https://www.getonbrd.com/jobs/senior-engineering-manager-even-remote) | `['Remote']` / `fully_remote` (`Latin America`) | **`Restricted`** (LATAM + ES/EN) |
| G8 | `ingeniero-a-full-stack-ameris-capital-santiago` | Ingeniero(a) Full-Stack | [`ameris`](https://www.getonbrd.com/jobs/ingeniero-a-full-stack-ameris-capital-santiago) | `['Chile']` / `hybrid` | **`Restricted`** |
| G9 | `ingeniero-de-software-senior-integratz-vina-del-mar-2278` | Ingeniero de Software Senior | [`integratz`](https://www.getonbrd.com/jobs/ingeniero-de-software-senior-integratz-vina-del-mar-2278) | `['Remote']` / `remote_local` (Viña del Mar) | **`Restricted`** |
| G10 | `full-stack-developer-blueworks-crm-remote` | Full-Stack Developer (React/Node/TS) | [`blueworks`](https://www.getonbrd.com/jobs/full-stack-developer-blueworks-crm-remote) | `['Remote']` / `remote_local` | **`Restricted`** (`remote_local`) |
| G11 | `desarrollador-full-stack-senior-java-angularjs-3it-santiago` | Desarrollador Full-Stack Senior Java + AngularJS | [`3it`](https://www.getonbrd.com/jobs/desarrollador-full-stack-senior-java-angularjs-3it-santiago) | `['Chile']` / `hybrid` | **`Restricted`** |
| G12 | `automation-engineer-hibrido-3x2-las-condes-prontopaga-santiago` | Automation Engineer (Híbrido 3x2, Las Condes) | [`prontopaga`](https://www.getonbrd.com/jobs/automation-engineer-hibrido-3x2-las-condes-prontopaga-santiago) | `['Chile']` / `hybrid` | **`Restricted`** |

**Result:** **`0/12` `Eligible`** (`11 Restricted`, `1 Unverified`).

### 5.4 Python.org Jobs (`12`-Job RSS + Detail Sample)

| # | URL | Title & Company | Detail Apply Target | Job Geo | Applicant Eligibility (Nigeria) |
|---|---|---|---|---|---|
| P1 | [`python.org/jobs/8213/`](https://www.python.org/jobs/8213/) | Internet Measurement Researcher, TGScope | `tgscope.io/careers/...` | `Remote, North America, Europe` | **`Restricted`** |
| P2 | [`python.org/jobs/8212/`](https://www.python.org/jobs/8212/) | Research Scientist, TGScope | `tgscope.io` | `Remote, North America, Europe` | **`Restricted`** |
| P3 | [`python.org/jobs/8211/`](https://www.python.org/jobs/8211/) | Research Engineer, Multilingual Semantic Search, TGScope | `tgscope.io` | `Remote, North America, Europe` | **`Restricted`** |
| P4 | [`python.org/jobs/8206/`](https://www.python.org/jobs/8206/) | Senior Python Developer, Eliassen Group | US Staffing | `Denver, US` (Remote) | **`Unverified`** / US implied |
| P5 | [`python.org/jobs/8205/`](https://www.python.org/jobs/8205/) | Data/ML Engineer (Python), Odette Technologies | Employer direct | `North Carolina, USA` (`East Coast-based`) | **`Restricted`** |
| P6 | [`python.org/jobs/8195/`](https://www.python.org/jobs/8195/) | Backend Software Engineering, UNICEF | [`jobs.unicef.org/en-us/job/596538/...`](https://jobs.unicef.org/en-us/job/596538/consultancy-connectivity-credits-backend-software-engineering-consultantdigital-impact-divisiongeneva-ch6-months-remote) | `Remote` (UN Consultant) | **`Unverified`** (UN consultancy; verify UN eligibility) |
| P7 | [`python.org/jobs/8189/`](https://www.python.org/jobs/8189/) | Founding Principal Engineer, Ferto Health GmbH | German Employer | `Berlin, Germany` (`visa to work in Germany`) | **`Restricted`** |
| P8 | [`python.org/jobs/8188/`](https://www.python.org/jobs/8188/) | Agentic Python Engineer, Evaboot | `forms.gle/...` / `zrobinz.github.io` | `Remote, Worldwide` (`"remote from anywhere"`) | **`Eligible`** |
| P9 | [`python.org/jobs/8180/`](https://www.python.org/jobs/8180/) | Senior Python Engineer, Manychat | Barcelona (Relocation) | `Barcelona, Spain` | **`Restricted`** (for remote-in-Nigeria) |
| P10 | [`python.org/jobs/8176/`](https://www.python.org/jobs/8176/) | Junior Machine Learning Engineer, HFT Architecture | [`hftarchitecture.com/careers/...`](https://hftarchitecture.com/careers/junior-machine-learning-engineer) | `Remote, Worldwide` (`"remote, from anywhere in the world"`) | **`Eligible`** (Junior ML!) |
| P11 | [`python.org/jobs/8175/`](https://www.python.org/jobs/8175/) | Machine Learning Engineer, HFT Architecture | `hftarchitecture.com` | `Remote, Worldwide` (`"from anywhere in the world"`) | **`Eligible`** |
| P12 | [`python.org/jobs/8174/`](https://www.python.org/jobs/8174/) | Python Backend Engineer, Uvik Software | Tallinn/Contractor | `Tallinn, Estonia` (`Remote Contractor`) | **`Unverified`** |

**Result:** **`3/12` (`25%`) explicit `Eligible`** (`8188`, `8176` Junior ML, `8175`), `1` UNICEF consultant (`8195`). High technical quality, but blocked from automated ingestion by PSF copyright (`All rights reserved`), missing `<pubDate>` in RSS, and tiny total volume (`21` active jobs globally).

### 5.5 OpenToAfrica (`10`-Job Overlap & Eligibility Proof) & RemoteWork.ng

All **`10/10` (`100%`)** sampled `OpenToAfrica` listings (`330` on site) linked directly to existing Bottom Pot ATS engines:
1. `FairMoney` — Engineering Manager (`Workable`: `apply.workable.com/j/53DCEB0EAA`, Lagos `Eligible`)
2. `Qdrant` — Senior SWE Platform EMEA (`Ashby`: `jobs.ashbyhq.com/qdrant.tech/840f2ddc-...`, EMEA/Africa `Eligible`)
3. `Canonical` — Graduate Software Engineer, Open Source & Linux (`Greenhouse`: `job-boards.greenhouse.io/canonical/jobs/8379825`, `Home based - Worldwide` `Eligible`)
4. `Pavago` — Full-Stack SWE Remote U.S. Hours (`Workable`: `apply.workable.com/j/1C25A38987`, Open to Africa `Eligible`)
5. `Talent Safari / Jackfruit` — Head of Data, Technology & AI (`Ashby`: `jobs.ashbyhq.com/talentsafari/3613aa2e-...`, Nairobi/Africa `Eligible`)
6. `Supabase` — Engineering Manager Realtime (`Ashby`: `jobs.ashbyhq.com/supabase/33caf92a-...`, Global `Eligible`)
7. `Thndr` — Senior AI Engineer (`Ashby`: `jobs.ashbyhq.com/thndr/00557bee-...`, Cairo/Africa `Eligible`)
8. `Camunda` — InfoSec Engineer (`Ashby`: `jobs.ashbyhq.com/camunda/54b6e8a4-...`, Global `Eligible`)
9. `M-KOPA` — Senior Backend Engineer (.NET) (`Ashby`: `jobs.ashbyhq.com/M-KOPA/fbfc41bc-...`, Nairobi/Africa `Eligible`)
10. `Circle` — Lead Engineer Member Growth (`Ashby`: `jobs.ashbyhq.com/circle/194a7b5d-...`, Worldwide/Africa `Eligible`)

Similarly, **`RemoteWork.ng`** `/jobs` (`20` links per page) exposes Next.js RSC keys directly matching **`ashby_bjak`**, **`ashby_circle-so`**, **`ashby_chili-piper`**, **`ashby_camunda`**, **`recruitee_hm-novakid-school`**, **`workable_tuxcare`**, **`greenhouse_hm-wave-mobile-money`**, **`lever_superside`**, **`greenhouse_canonical`**, **`ashby_qdrant`**, **`ashby_skelar`**, and **`ashby_liven`** — confirming both African boards are `Discovery-only` employer-slug intelligence leads rather than unique direct feeds.

### 5.6 Remote OK (`12`), US-RSE (`19` total), Arbeitnow (`10`), Hasjob (`10`), and Habr Career (`10`) Summaries
- **`Remote OK` (`R1`–`R12`):** `R6` `Supabase SWE AI Tooling` (`1137793`) & `R12` `Addepto Data Engineer` (`1137714`) contained `anywhere in the world` / `worldwide` clues (`2/12`); `R3` (`PatientPoint`, US EST/CST), `R4` (`Fuku`, European timezones), `R5` (`DoiT`, NL/EE/SE/ES) were `Restricted`; remaining `R1, R2, R7, R8, R9, R10, R11` were healthcare/tutoring/talent pools (`Unverified`/`Restricted`).
- **`Arbeitnow` (`A1`–`A10` of `300`):** `10/10` Germany/DACH (`Offenburg`, `Deggendorf`, `Berlin`, `Stuttgart`, `Frankfurt`, `Munich`, `Düsseldorf`, `Köln`), mostly German-language `Werkstudent` / `Praktikum` -> `0/10` Nigeria `Eligible`.
- **`Hasjob` (`H1`–`H10` of `17`):** `9/10` India local/India remote (`Bangalore`, `Mumbai`, `Hyderabad`, `India`), `1/10` ambiguous medical content writer (`H3`) -> `0/10` Nigeria SWE `Eligible`.
- **`US-RSE` (`19` total):** `19/19` US universities/research labs (`Lynker/NOAA`, `[C]Worthy`, `Dartmouth`, `Syracuse`, `UChicago`, `NCSA`, `Purdue`, `Georgia Tech`, etc.) pointing to `icims`, `lever`, `myworkdayjobs`, `workable`, and university HR portals -> `0/19` Nigeria `Eligible`.
- **`Habr Career` (`10` HTML cards):** `10/10` Russian-language vacancies in Moscow/St. Petersburg/RU remote -> `0/10` Nigeria `Eligible`.

---

## 6. Mandatory Redistribution & Permission Gate Table

| Source | Official Docs / Terms Inspected | Third-Party Job Display | Direct Employer / ATS Link Allowed | Automated Unauth Collection | Redistribution Gate Decision |
|---|---|---|---|---|---|
| **`Pinpoint`** (`pinpointhq`) | `developers.pinpointhq.com/docs/job-feeds-overview.md` (`2026-06-02`), `jobs-json-endpoint.md` (`2026-04-20`), `help.pinpoint.support/.../17141546`, `robots.txt` | **Yes** (explicitly documented for external job websites/boards) | **Yes** (`url` -> `{slug}.pinpointhq.com/en/postings/{uuid}` & `/applications/new`) | **Yes** (public unauth CORS JSON + `robots.txt` `Allow`, `120 req/1m`) | **PASSED — `Approved` -> `Implemented`** |
| **`Jobicy`** | `jobicy.com/jobs-rss-feed` (§10, §12) & `jobicy.com/terms-and-conditions` | Conflicting (`§10` allows with credit; `Terms` prohibit) | **No on Free API** (stripped to `jobicy.com/jobs/...`; Commercial `$0.01/job` needed) | Public API documented (max 1x/hr, skip `:00`) | **BLOCKED for free ingestion -> `Discovery-only`** |
| **`Get on Board`** | `getonbrd.com/about/tos` (Version 1.2, 2026-11-17, §8 & §14) | **No** (API scoped to client ATS integrations; prohibits publishing IP) | API uses GoB `apply` links | **No** for third-party boards | **BLOCKED -> `Permission pending`** |
| **`Python.org Jobs`** | `python.org/about/legal/` | **No** explicit grant (`All rights reserved`) | Detail pages link externally | Public RSS exists without license | **BLOCKED -> `Permission pending` / `Discovery-only`** |
| **`Remote OK`** | Embedded legal header on `https://remoteok.com/api` | Conditional (requires `follow` backlink) | **No** (`apply_url` routes through `remoteok.com`) | Public JSON | **BLOCKED -> `Permission pending`** |
| **`Himalayas`** | `himalayas.app/jobs/api` terms & FAQ | **No** (prohibits job-board redistribution) | **No** (prohibits bypassing `himalayas.app?utm_source=api`) | Restricted | **BLOCKED -> `Discovery-only`** |
| **`Remotive`** | `0-legal-notice` in `/api/remote-jobs` | **No** (warns against third-party job sites; `$5k/mo` enterprise API) | Redirects traffic back to `remotive.com` | 24h delayed feed | **BLOCKED -> `Discovery-only`** |
| **`OpenToAfrica` / `RemoteWork.ng`** | Public HTML / no public API | **No** redistribution grant | Scrapes Ashby/Greenhouse/Workable/Lever | No API | **`Discovery-only` (seed intelligence)** |
| **`Arbeitnow` / `Hasjob` / `Habr` / `hh.ru` / `US-RSE` / `Blognone`** | Site headers / `dev.hh.ru` / `career.habr.com/info/api` | Unclear, OAuth-gated (`Habr`, `hh.ru` `403`), or attribution/revocation-reserved (`Arbeitnow`) | Mixed | OAuth/API client required on `Habr`/`hh.ru` | **`Permission pending` / `Discovery-only`** |

---

## 7. Candidate Ranking Table (100-Point Rubric)

| Rank | Candidate | Nigeria / Africa Eligibility (25) | Technical Quality & Relevance (20) | Incremental Coverage (15) | Redistribution Rights & Clarity (15) | Freshness & Completeness (10) | Technical Reliability & Stability (10) | Maintenance Cost (5) | **Total (100)** | Hard-Gate Verdict |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| **1** | **`Pinpoint` (`pinpointhq`)** | **21** (`38` NG + `16` EG + `153` AF on sampled boards) | **18** (AI/ML, Data, Geospatial, Python, QA) | **15** (`0` overlap; brand-new ATS ecosystem) | **14** (Official external job-board JSON docs + `robots.txt`) | **7** (Full HTML desc + comp; `/postings.json` omits `posted_at`) | **7** (`404` clean closure, weak `ETag`/`304`, slow 1–2 MB streams) | **4** | **86** | **PASS — Selected for Step 51** |
| **2** | **`Jobicy`** | 8 (`0` Africa locations; `15/1000` `Anywhere`) | 16 | 6 (`Anywhere` tech mirrors Ashby/GH) | 9 (`§10` allows; `Terms` conflict + no free direct ATS links) | **10** | **10** | 5 | **64** | FAIL (Free API strips direct apply + weak Africa reach + Terms conflict) |
| **3** | **`Get on Board`** | 4 (`0/12` NG; LATAM only) | 16 | 13 | 2 (TOS §8/§14 forbid redistribution) | **9** | **10** | 4 | **58** | FAIL (Permission gate + LATAM only) |
| **4** | **`Python.org Jobs`** | 11 (`3/12` worldwide + UNICEF) | **19** | 12 | 3 (`All rights reserved`) | 5 (`<item>` lacks `<pubDate>`) | 4 (`1+N` HTML detail fetches; `21` total jobs) | 2 | **56** | FAIL (Permission gate + low volume) |
| **5** | **`OpenToAfrica`** | **23** (`10/10` Africa/Global) | **18** | **1** (`10/10` existing Ashby/Workable/GH) | 3 (No API/license) | 4 | 4 | 2 | **55** | FAIL (Permission gate + `100%` overlap) |
| **6** | **`RemoteWork.ng`** | **23** (`NG` screened) | 14 | **1** (Scrapes Ashby/GH/Lever/Workable/Recruitee) | 3 (No API/license) | 5 | 4 | 3 | **53** | FAIL (Permission gate + upstream overlap) |
| **7** | **`Remote OK`** | 7 (`2/12` worldwide clues) | 13 | 8 | 4 (Requires `follow` link + proxies `apply_url`) | 8 | 8 | 4 | **52** | FAIL (Permission + direct-apply conflict) |
| **8** | **`Himalayas`** | 10 | 14 | 5 | 2 (Prohibits redistribution & direct links) | 7 | 7 | 4 | **49** | FAIL (Permission gate) |
| **9** | **`Remotive`** | 8 | 13 | 5 | 1 (`0-legal-notice` restricts 3rd-party boards; 24h delay) | 6 | 7 | 4 | **44** | FAIL (Permission gate) |
| **10** | **`US-RSE Job Board`** | 1 (`0/19` NG; US campuses) | 16 | 6 | 4 (No license stated) | 3 (4 summary fields only) | 9 | 4 | **43** | FAIL (Eligibility + incomplete schema) |
| **11** | **`Arbeitnow`** | 2 (`0/10` NG; DE/DACH) | 10 | 10 | 5 | 5 | 6 | 3 | **41** | FAIL (Permission + Germany-only) |
| **12** | **`Hasjob`** | 2 (`0/10` NG; India) | 11 | 9 | 3 | 6 | 5 | 2 | **38** | FAIL (Permission + India-only) |
| **13** | **`Habr Career`** | 1 (`0/10` RU only) | 13 | 10 | 2 (OAuth API registration required) | 3 | 3 | 2 | **34** | FAIL (Permission + OAuth + RU only) |
| **14** | **`HeadHunter (hh.ru)`** | 1 | 12 | 9 | 1 (`403 Forbidden`, commercial terms) | 3 | 2 | 2 | **30** | FAIL (Blocked `403` + RU/CIS only) |
| **15** | **`Blognone Jobs`** | 1 (`TH` local) | 9 | 9 | 2 (SPA, no feed/terms) | 3 | 2 | 2 | **28** | FAIL (SPA + no permission + TH only) |
| **16** | **`ThailandDev`** | 0 | 0 | 0 | 0 | 0 | 0 (DNS failure) | 0 | **0** | **`Rejected`** (Domain unreachable) |

---

## 8. Pinpoint (`pinpointhq`) Implementation Architecture

Step 51 integrates `pinpointhq` end-to-end across backend discovery, board monitoring, direct routing, URL normalization, enrichment, and frontend inventory (`18` active ATS platforms + `3` Nigerian = `21` total; `9` `MONITORABLE_PROVIDERS`):

1. **Configuration & Serper Dork Exclusion ([`config.py`](../../src/project_files/config.py), [`src/config.py`](../../src/config.py), [`query_builder.py`](../../src/project_files/query_builder.py)):**
   - Added `ATSConfig(name="pinpointhq", site_operator="pinpointhq.com", label="Pinpoint")` to `ATS_PLATFORMS`.
   - Added `pinpoint_board_max_response_bytes = 3 * 1024 * 1024` (`3 MiB`) to `Settings`.
   - Excluded marketing/docs hosts (`-site:www.pinpointhq.com`, `-site:developers.pinpointhq.com`, `-site:app.pinpointhq.com`) in `ATS_EXCLUDED_SUBDOMAINS`.
2. **URL Parsing & Cross-Source Deduplication ([`ats_url_parser.py`](../../src/project_files/ats_url_parser.py), [`url_normalizer.py`](../../src/project_files/url_normalizer.py)):**
   - Parses `https://{slug}.pinpointhq.com/(?:{locale}/)?postings/{uuid}(?:/applications/new|/apply)?` and legacy `/jobs/{numeric_id}` URLs while rejecting `_PINPOINT_RESERVED_SUBDOMAINS`.
   - Added `parse_pinpoint_board_root_url(url)` so board root hits discovered in Search register monitorable boards cleanly.
   - `canonicalize_pinpoint_posting_url` / `build_url_match_key` collapse locale prefixes (`/en/`, `/pt-BR/`), uppercase UUIDs, `http://`, tracking params, and `/applications/new` suffixes to `https://{slug}.pinpointhq.com/postings/{uuid}`.
3. **Board Monitoring Adapter ([`board_adapters.py`](../../src/project_files/board_adapters.py), [`company_board_registry.py`](../../src/project_files/company_board_registry.py)):**
   - `PinpointBoardAdapter` streams `GET https://{slug}.pinpointhq.com/postings.json` (`follow_redirects=False`, `timeout >= 15s` for 1–2 MB global boards, `Accept-Encoding: gzip, deflate`, conditional `If-None-Match` `304 Not Modified`, SHA-256 `compute_board_fingerprint`).
   - `parse_pinpoint_postings_json` validates JSON root, `data` list, required `id`/`title`/`url`, tenant host consistency, and unique IDs atomically — failing closed with `snapshot_complete=False` on any corruption, `301` redirect, `404`, `429`, or `ResponseTooLargeError`, and enforcing `missing_confirmation_threshold=2`.
   - `_pinpoint_item_to_listing` combines `description` + `key_responsibilities` + `skills_knowledge_expertise` + `benefits`, populates `requirements` from `skills_knowledge_expertise`, honors `compensation_visible=True` for `baseSalary`, maps `workplace_type` & `employment_type` (`permanent_full_time` -> `full_time`) without inventing `posted_at` from `deadline_at`, preserves `location.name` (avoiding city-override bugs like Lagos HQ on Ebonyi postings), and populates canonical UUID IDs plus `pinpointhq:{slug}:{numeric_id}` aliases.
4. **Direct Board Routing, Enricher, Extraction & Frontend Sync:**
   - Added `probe_pinpoint_board` to `probe_direct_boards` ([`direct_board_router.py`](../../src/project_files/direct_board_router.py)); wired `parse_pinpoint_board_root_url` into [`search_pipeline.py`](../../src/project_files/search_pipeline.py); enabled `pinpointhq` UUID identity + JSON-LD `datePosted`/`baseSalary` enrichment in [`ats_page_enricher.py`](../../src/project_files/ats_page_enricher.py) and [`job_extraction_service.py`](../../src/project_files/job_extraction_service.py).
   - Synchronized frontend [`constants.ts`](../../frontend/src/lib/constants.ts) (`21` platforms) and bumped [`platformMigration.ts`](../../frontend/src/lib/platformMigration.ts) to `CURRENT_PLATFORM_VERSION = '51'` (migrating Step 50 20-platform full selections cleanly to all `21` platforms).

---

## 9. Employer Discovery & Seed Intelligence Guidance

Sources classified as **`Discovery-only`** in Step 51 remain valuable without ingesting third-party listings:
- **`OpenToAfrica`** & **`RemoteWork.ng`** reveal African-hiring companies already hosting primary boards on Bottom Pot's supported ATS engines (`qdrant.tech`, `supabase`, `canonical`, `fairmoney`, `pavago`, `talentsafari`, `thndr`, `camunda`, `M-KOPA`, `circle`, `bjak`, `chili-piper`, `hm-wave-mobile-money`, `superside`, `skelar`, `liven`, `tuxcare`, `hm-novakid-school`).
- **`Python.org Jobs`** & **`US-RSE`** expose direct employer career pages (`tgscope.io`, `hftarchitecture.com`, `careers-lynker.icims.com`, `jobs.lever.co/convergentresearch`, `apply.workable.com/sei`, `uchicago.wd5.myworkdayjobs.com`).
- These employer ATS slugs can feed Bottom Pot's `CompanyBoardRegistry` directly via our native `Greenhouse`, `Lever`, `Ashby`, `Workable`, `Recruitee`, and **`Pinpoint`** board adapters while respecting aggregator terms.

---

## 10. Verification & Protected Data Integrity

All verification runs executed completely offline using captured fixtures (`tests/fixtures/real/pinpointhq/`) and isolated temporary SQLite databases (zero Serper credits consumed; `data/cache.sqlite` untouched). Only this Section 10 documentation summary was updated after the final `.\scripts\verify.ps1` and direct verbose verification runs completed (and `git checkout --` restored unrelated `docs/design/after/step28_platform_chips_{light,dark}.png` artifacts rewritten by Playwright E2E).

### Verification Suite Results (Post-Final Code Edit)

| Check | Command | Observed Result |
|---|---|---|
| Full Verification Suite | `.\scripts\verify.ps1` | **9 passed, 0 failed, 0 skipped** (of 9 checks) |
| Git & Secret Hygiene | `git --version` / tracked secret globs | **OK** (`0` tracked secret files) |
| CSS Cascade Lint | `node scripts/lint_css_cascade.js` | **Passed** (all element/reset styles scoped inside `@layer`) |
| Frontend Linting | `npm --prefix frontend run lint` (`oxlint`) | **0 errors** (`3` pre-existing Fast Refresh warnings across `93` files, `116` rules, `126ms`) |
| Frontend Unit Tests | `npm --prefix frontend run test` (`vitest`) | **17 files / 116 tests passed** (`0` failed, `11.73s`) |
| Frontend Typecheck & Build | `npm --prefix frontend run build` (`tsc -b && vite build`) | **Passed** (`2613` modules transformed, built in `1.41s`) |
| DB Safety Static Check | `python scripts/check_db_safety.py` | **PASSED** (`0` unsafe patterns found) |
| Python Backend Unit Tests | `BOTTOM_POT_TEST_MODE=1 python -m pytest -q` | **1179 passed**, `2` third-party `slowapi` warnings, `0` failed (`486.36s`) |
| Playwright E2E Suite | Isolated temp DB (`PLAYWRIGHT_REUSE_SERVER=0`, `BOTTOM_POT_TEST_MODE=1`) | **43 passed** (`1.5m`, `0` failed) |

### Protected `data/` Checksum Verification (ADR 0030)

| File | Size (Bytes) | Baseline & Post-Verification SHA-256 | Match |
|---|---:|---|---|
| `data/cache.sqlite` | `14,016,512` | `a7c88bb24d383813213342ea1a0990f0c7bf62b4c1308647fc18f834be028638` | Identical |
| `data/cache.sqlite-shm` | `32,768` | `fd4c9fda9cd3f9ae7c962b0ddf37232294d55580e1aa165aa06129b8549389eb` | Identical |
| `data/cache.sqlite-wal` | `0` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | Identical |

All `6` SQLite backup and restore-staging files inside `data/` (`cache.sqlite.bak-pre-ashby-repair`, `cache.sqlite.bak-pre-greenhouse-synthetic-cleanup*`, `.cache.sqlite.restore-staging-*`) also remained byte-identical.
