# Bottom Pot Job Source Lifecycle Catalog

This document is the authoritative source-of-truth inventory and lifecycle ledger for every job board, Applicant Tracking System (ATS), remote-job feed, and other job source considered or integrated in Bottom Pot.

---

## 1. Purpose, Selection Principles & Evaluation Standard

Bottom Pot optimizes for **genuinely eligible, fresh technical jobs** that developers and technology professionals living in **Nigeria and elsewhere in Africa** can apply for (covering internship, junior, entry-level, and experienced roles), **not provider count**.

### Mandatory Evaluation Rules
1. **Do not prioritize a source solely because** it is popular, has high raw posting volume, offers a convenient API, is easy to integrate, or is consumed by other aggregators.
2. **Distinguish source categories**:
   - `Employer ATS / career board`
   - `Regional technology job board`
   - `International remote-only board`
   - `Specialized programming or industry job board`
   - `General job aggregator`
   - `Talent marketplace or recruiting network`
   - `Professional community or job-posting feed`
3. **Prefer direct employer career pages**: A source may be useful for discovering employer career URLs even when direct listing ingestion is legally or technically unsuitable.
4. **Before implementation, establish**: public access & authentication, official API/feed documentation, explicit data reuse/redistribution rights, attribution & original application-link requirements, description completeness, stable identity, pagination & empty-feed semantics, expiration/closure signals, HTTP limits & conditional requests, geographic/work-authorization restrictions, relevant technical/early-career coverage, incremental value, duplicate coverage, and maintenance cost.
5. **Never infer worldwide access from `is_remote=true` or generic remote labels**. Classify applicant eligibility explicitly as:
   - `Eligible`: explicit evidence permits applications from Nigeria or the relevant applicant location.
   - `Restricted`: explicit country, region, work-authorization, or hiring restrictions exclude the applicant.
   - `Unverified`: remote status exists, but applicant eligibility is unclear or contradictory.
6. **Mandatory rejected-provider cleanup**: When a source is `Rejected` (`Unsuitable`), remove all active configuration, URL parsers, canonical URL builders, normalizers, enrichers, routers, adapters, frontend constants, and active tests—without deleting shared capabilities, historical investigation records (`docs/steps/`), or operational SQLite data (`data/cache.sqlite`).

### Lifecycle States

| State | Meaning |
|---|---|
| `Discovered` | Candidate identified; not yet formally evaluated. |
| `Investigating` | Bounded empirical & documentation audit in progress. |
| `Approved` | Passed evaluation; queued for dedicated bounded implementation. |
| `Implemented` | Active in production discovery/monitoring with full tests, fixtures, and safeguards. |
| `Constrained` | Active (or scoped to enrichment/search only) with documented technical, geographic, or coverage constraints. |
| `Rejected` | Evaluated as `Unsuitable` (or unclear permission); active integration code removed. |
| `Retired` | Previously configured/supported, now removed from active discovery/monitoring. |

---

## 2. Master Source Lifecycle Catalog

### 2.1 Active Monitorable & Search ATS Platforms (`17` configured in `ATS_PLATFORMS`)

| Source | Category | Geography & Target Audience | Official URL & Feed / API | Permission & Attribution | Last Verified | Evidence / Investigation | Incremental Value | Lifecycle State & Decision | Implementation / PR |
|---|---|---|---|---|---|---|---|---|---|
| **`greenhouse`** | Employer ATS / career board | Global tech startups & enterprise (US/EU/global remote + some Africa) | `https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true` | Public Job Board API; direct ATS links preserved | Baseline (Steps 22a–30) | [Step 22a](steps/22a-canonical-contract-ats.md) | High — core global tech SWE/AI coverage; single-GET descriptions | **`Implemented`** (`Suitable`) | Core (`MONITORABLE_PROVIDERS`) |
| **`lever`** | Employer ATS / career board | Global tech companies & remote startups | `https://api.lever.co/v0/postings/{slug}?mode=json` | Public Postings API; direct ATS links preserved | Baseline (Steps 22a–30) | [Step 22a](steps/22a-canonical-contract-ats.md) | High — largest `monitored_jobs` active footprint (`160` rows in DB) | **`Implemented`** (`Suitable`) | Core (`MONITORABLE_PROVIDERS`) |
| **`ashby`** | Employer ATS / career board | High-growth AI/SaaS/remote-friendly tech companies | `https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true` | Public Job Board API; direct ATS links preserved | Step 39 | [Step 39](steps/39-ashby-quality-pipeline.md) | High — strong remote SWE/AI startups, compensation & workplace metadata | **`Implemented`** (`Suitable`) | Step 39 (`MONITORABLE_PROVIDERS`) |
| **`workable`** | Employer ATS / career board | SMB/startup global & remote tech employers | `https://apply.workable.com/api/v1/widget/accounts/{slug}` + bounded `v2` detail hydration | Public career widget/detail endpoints; direct ATS links preserved | Step 41 | [Step 41](steps/41-workable-quality-pipeline.md) | Medium-High — adds SMB remote/tech coverage; requires bounded `1+N` hydration | **`Constrained`** (`Suitable with constraints`) | Step 41 (`MONITORABLE_PROVIDERS`) |
| **`recruitee`** | Employer ATS / career board | EU/UK/global startups & distributed tech teams | `https://{slug}.recruitee.com/api/offers/` | Public Offers API; direct ATS links preserved | Step 42–43 | [Step 42](steps/42-recruitee-monitoring-investigation.md), [Step 43](steps/43-recruitee-quality-pipeline.md) | Medium — single-GET full descriptions & explicit remote tags | **`Implemented`** (`Suitable`) | Step 43 (`MONITORABLE_PROVIDERS`) |
| **`smartrecruiters`** | Employer ATS / career board | Global enterprise & tech (paginated list + bounded detail hydration) | `https://api.smartrecruiters.com/v1/companies/{slug}/postings` | Public Posting API; direct ATS links preserved | Step 44–45 | [Step 44](steps/44-smartrecruiters-monitoring-investigation.md), [Step 45](steps/45-smartrecruiters-quality-pipeline.md) | Medium — paginated snapshot + bounded detail hydration (`20` new/`10` reval) | **`Constrained`** (`Suitable with constraints`) | Step 45 (`MONITORABLE_PROVIDERS`) |
| **`teamtailor`** | Employer ATS / career board | EU/UK/global & African tech startups (e.g., Paystack) | `https://{slug}.teamtailor.com/jobs.rss` + HTML `/jobs?page=N` fallback | Public career portal RSS/HTML; direct ATS links preserved | Step 46–47 (`2026-11-17`) | [Step 46](steps/46-teamtailor-monitoring-investigation.md), [Step 47](steps/47-teamtailor-monitoring-pipeline.md) | Medium-High — `7` operational boards, `<remoteStatus>`; RSS caps at 100 items | **`Constrained`** (`Suitable with constraints`) | PR #43 / PR #45 (`MONITORABLE_PROVIDERS`) |
| **`personio`** | Employer ATS / career board | Primarily DACH/European SMEs & tech firms | `https://{slug}.jobs.personio.com/xml?language=en` + `/xml` merge | Officially documented XML recruiting feed; direct links | Step 48–49 (`2026-11-17`) | [Step 48](steps/48-personio-monitoring-investigation.md), [Step 49](steps/49-personio-monitoring-pipeline.md) | Low-Medium — single-GET XML + `304`, but DACH-heavy & bilingual split | **`Constrained`** (`Suitable with constraints`) | PR #48 / PR #49 (`MONITORABLE_PROVIDERS`) |
| **`bamboohr`** | Employer ATS / career board | SMEs (minimal tech footprint in operational DB) | `https://{slug}.bamboohr.com/careers/list` (`BambooHRClient`) | Public career widget; direct links | Step 48 (`2026-11-17`) | [Step 46](steps/46-teamtailor-monitoring-investigation.md), [Step 48](steps/48-personio-monitoring-investigation.md) | Low — `0` real DB rows in `company_boards`/`url_cache`/`serper_cache`; search-only | **`Constrained`** (`PROVISIONAL_PROVIDERS`; monitoring `Unsuitable`) | Legacy `BambooHRClient` only |
| **`workday`** | Employer ATS / career board | Large global enterprises (`myworkdayjobs.com`) | `POST https://{tenant}.{wdN}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs` (`WorkdayClient`) | Public career site; no official unauth board API (`429` on GET) | Step 48 (`2026-11-17`) | [Step 48](steps/48-personio-monitoring-investigation.md) | Medium for search enrichment (`46` `url_cache`); board monitoring `Unsuitable` | **`Constrained`** (search + `WorkdayClient` only; monitoring `Unsuitable`) | Search + detail client only |
| **`jobvite`** | Employer ATS / career board | Mid-market/enterprise (`jobs.jobvite.com`) | HTML `/jobs` + JSON-LD detail pages | Public career pages; RSS returns `303` | Step 48 (`2026-11-17`) | [Step 48](steps/48-personio-monitoring-investigation.md) | Low (`1` `company_boards`, `0` remote/Africa hits); search enrichment only | **`Constrained`** (search + HTML only; monitoring `Unsuitable`) | Search + enricher only |
| **`jazzhr`** | Employer ATS / career board | SMBs (`applytojob.com`) | HTML `/apply` + `/app/share` (`/apply/rss` returns `410 Gone`) | Public career pages; `/apply/rss` deprecated | Step 48 (`2026-11-17`) | [Step 48](steps/48-personio-monitoring-investigation.md) | Low (`3` `url_cache`, `0` `company_boards`); search enrichment only | **`Constrained`** (search + HTML only; monitoring `Unsuitable`) | Search + enricher only |
| **`icims`** | Employer ATS / career board | Enterprise (`*.icims.com`) | Multi-portal iframe HTML | Public career pages; no canonical board feed | Step 48 (`2026-11-17`) | [Step 48](steps/48-personio-monitoring-investigation.md) | Low (`0` `company_boards`, `0` `url_cache`); search enrichment only | **`Constrained`** (search + HTML only; monitoring `Unsuitable`) | Search + regex/enricher only |
| **`avature`** | Employer ATS / career board | Global enterprise (`*.avature.net`) | Localized enterprise HTML | Public career pages; non-standardized paths | Step 48 (`2026-11-17`) | [Step 48](steps/48-personio-monitoring-investigation.md) | Low (`4` `url_cache`, `0` `company_boards`); search enrichment only | **`Constrained`** (search + HTML only; monitoring `Unsuitable`) | Search + regex/enricher only |
| **`taleo`** | Employer ATS / career board | Legacy enterprise (`*.taleo.net/careersection`) | Oracle Taleo JSF HTML | Public career pages; JSF session/HTML only | Step 48 (`2026-11-17`) | [Step 48](steps/48-personio-monitoring-investigation.md) | Low (`0` `company_boards`, `0` `url_cache`); search enrichment only | **`Constrained`** (search + HTML only; monitoring `Unsuitable`) | Search + regex/enricher only |
| **`jobadder`** | Employer ATS / career board | Recruitment agencies (`apply.jobadder.com`) | Agency apply pages | Marketing/apply links; `0` real job URLs in DB | Step 48 (`2026-11-17`) | [Step 48](steps/48-personio-monitoring-investigation.md) | Very low (`0` real job URLs in DB); search enrichment only | **`Constrained`** (search + HTML only; monitoring `Unsuitable`) | Search + regex/enricher only |
| **`successfactors`** | Employer ATS / career board | SAP enterprise portals (`jobs.sap.com`) | HTML with `.joblayouttoken` | Public career pages; single-enterprise domain | Step 48 (`2026-11-17`) | [Step 48](steps/48-personio-monitoring-investigation.md) | Very low (`0` real non-SAP URLs); search enrichment only | **`Constrained`** (search + HTML only; monitoring `Unsuitable`) | Search + regex/enricher only |

### 2.2 Active Regional Technology & Local Job Boards (`3` configured in `NIGERIAN_SCRAPERS`)

| Source | Category | Geography & Target Audience | Official URL & Feed / API | Permission & Attribution | Last Verified | Evidence / Investigation | Incremental Value | Lifecycle State & Decision | Implementation / PR |
|---|---|---|---|---|---|---|---|---|---|
| **`jobberman`** | Regional technology job board (general + tech) | Nigeria (`NG`) — local & hybrid tech roles | `https://www.jobberman.com/jobs` (HTML scraper) | Public listings; direct Jobberman listing links preserved | Step 27–31 | [Step 27](steps/27-batch-b-direct-routing-and-nigerian-ui.md), [Step 28](steps/28-nigerian-chips.md) | High — primary local Nigerian job board coverage | **`Implemented`** (`Suitable`) | Steps 27–28 (`NIGERIAN_SCRAPERS`) |
| **`myjobmag`** | Regional technology job board (general + tech) | Nigeria (`NG`) — local & entry/mid tech roles | `https://www.myjobmag.com` (HTML scraper) | Public listings; direct MyJobMag links preserved | Step 27–31 | [Step 27](steps/27-batch-b-direct-routing-and-nigerian-ui.md), [Step 28](steps/28-nigerian-chips.md) | High — local Nigerian coverage including junior/graduate roles | **`Implemented`** (`Suitable`) | Steps 27–28 (`NIGERIAN_SCRAPERS`) |
| **`hotnigerianjobs`** | Regional technology job board (general + tech) | Nigeria (`NG`) — broad local hiring | `https://www.hotnigerianjobs.com` (HTML scraper) | Public listings; direct HNJ links preserved | Step 16, 31 | [Step 16](steps/step-16-result-mix-and-hnj-extraction.md), [Step 31](steps/31-hotnigerianjobs-chip.md) | Medium-High — Nigerian early-career & graduate openings | **`Implemented`** (`Suitable`) | Step 31 (`NIGERIAN_SCRAPERS`) |

### 2.3 Rejected & Retired Sources

| Source | Category | Geography & Target Audience | Official URL & Feed / API | Permission & Attribution | Last Verified | Evidence / Investigation | Rejection / Retirement Rationale | Lifecycle State & Decision | Cleanup / Migration Reference |
|---|---|---|---|---|---|---|---|---|---|
| **`breezy` (Breezy HR)** | Employer ATS / career board | Claimed global SMB; empirically US-federal-contractor & CA-heavy | `https://{slug}.breezy.hr/json` (**undocumented**; `developer.breezy.hr` documents authenticated `api.breezy.hr/v3` only) | Unauthenticated portal pages; `/json` lacks documented reuse guarantees; `apply.breezy.hr` fails DNS (`getaddrinfo failed`) | `2026-11-18` | [Step 50](steps/50-breezy-monitoring-investigation.md) | **Negative ROI**: `0` `company_boards`, `0` `url_cache`, `14` unique `serper_cache` jobs (`59.2%` US federal contractors `vetsez`/`expression-networks`, `18.3%` onsite Canadian civil engineering `pri`, `0` Nigeria/remote-junior SWEs); `/json` omits descriptions (`1+N` HTML fetch cost, `302 -> /` on closed jobs, missing JSON-LD on `vigil-global`); `"Fully remote, no location restrictions"` contradicted by JSON-LD `applicantLocationRequirements` (`US`, `NL`) | **`Rejected`** (`Unsuitable`) | Draft PR #50 (active backend/frontend code removed; retained only in `HISTORICAL_FULL_INVENTORIES` for `localStorage` migration; historical `data/cache.sqlite` untouched) |
| **`ngcareers`** | Regional job board | Nigeria (`NG`) | `https://www.ngcareers.com` | Public listings | Pre-Step 27 | `url_normalizer.py:165` | Removed from active `NIGERIAN_SCRAPERS`; URL normalization rule retained for historical URLs | **`Retired`** | Legacy removal; `url_normalizer.py` only |
| **`polywork`** | Professional network / job feed | Global tech | — | — | Step 32 | [Step 32](steps/32-global-ats-monitoring-registry.md) | Removed from active inventories in Step 32; retained only in `HISTORICAL_FULL_INVENTORIES` | **`Retired`** | Step 32 (`platformMigration.ts`) |
| **`rippling`** | Employer ATS | Global tech | — | — | Step 32 | [Step 32](steps/32-global-ats-monitoring-registry.md) | Removed from active `ATS_PLATFORMS` in Step 32; retained only in `HISTORICAL_FULL_INVENTORIES` | **`Retired`** | Step 32 (`platformMigration.ts`) |
| **`pinpointhq`** | Employer ATS | Global / UK / remote tech (`*.pinpointhq.com/postings.json`) | `*.pinpointhq.com` | Pending fresh evaluation | Step 32 | [Step 32](steps/32-global-ats-monitoring-registry.md), [Step 50](steps/50-breezy-monitoring-investigation.md) | Removed from active inventory in Step 32; retained in `HISTORICAL_FULL_INVENTORIES`; candidate for future fresh Section 3 evaluation | **`Retired`** (re-evaluation candidate) | Step 32 (`platformMigration.ts`) |

---

## 3. Documented Exceptions for Retained References

Per the repository normalization policy, active provider registrations for rejected/retired sources must be removed, while existing shared or historical migration artifacts are preserved only with explicit justification:

1. **`frontend/src/lib/platformMigration.ts` (`HISTORICAL_FULL_INVENTORIES`)**: Retains historical platform IDs (`'breezy'`, `'polywork'`, `'rippling'`, `'pinpointhq'`) **strictly** so existing users upgrading from Step 27–49 `localStorage` state have their `"all platforms"` selections migrated cleanly to the active 20-platform set (and rejected IDs stripped from custom subsets).
2. **`src/project_files/url_normalizer.py` (`ngcareers` rule)**: Retains URL normalization for historical URLs without performing any active search or scraping.
3. **Operational database (`data/cache.sqlite`, `serper_cache`)**: Historical rows referencing rejected or retired providers are **never** deleted or migrated without separate authorization and an explicit migration plan.
4. **Historical step documents (`docs/steps/*`)**: Preserved intact as immutable engineering audit records, annotated where superseded (e.g., [Step 48](steps/48-personio-monitoring-investigation.md) annotating that `breezy` was subsequently rejected in [Step 50](steps/50-breezy-monitoring-investigation.md)).
