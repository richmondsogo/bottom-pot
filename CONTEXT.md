# Project Context: Bottom Pot

> Authoritative source of project and domain knowledge for Bottom Pot.
> Kept synchronized with architectural decisions in `docs/adr/`.

---

## Product

**Bottom Pot is global by design. Nigeria is a priority market and a first-class validation target, not a hard-coded eligibility boundary.**

**Global job discovery. Applicant-country-aware eligibility. Nigerian-first validation, not Nigerian-only coverage.**

Bottom Pot is a global, ATS-first job discovery engine serving applicants across Nigeria, Africa, Europe, North America, Asia, Latin America, Australia, and elsewhere. It searches 18 configured public Applicant Tracking Systems (Greenhouse, Lever, Ashby, Workable, Pinpoint, and 13 others defined in `src/project_files/config.py`, plus 3 Nigerian job boards and a curated 20-board direct-employer monitoring catalog inside the existing 9 `MONITORABLE_PROVIDERS`; lifecycle status tracked in `docs/job-source-catalog.md`) directly via Google dork queries over Serper.dev and monitored employer boards, streams fresh job listings to the browser via Server-Sent Events (SSE), and evaluates job-level applicant eligibility against the user's selectable country across early-career through senior technical roles without aggregator noise or duplicate postings.

## Users

- **Software engineers, product designers, and technology professionals worldwide** (across Nigeria, Africa, Europe, North America, Asia, Latin America, Australia, and elsewhere) looking for high-signal, direct-to-company job opportunities evaluated against where they can work from.
- **Applicants in Nigeria and wider Africa** as priority validation markets for accurate remote, regional, and local-hub eligibility without misleading `"Remote"` labels.

## Core Problem

Mainstream job boards and aggregators (LinkedIn, Indeed, generic scrapers) are riddled with duplicate reposts, stale ghost jobs, affiliate redirects, and stripped application metadata. Bottom Pot bypasses aggregator middlemen by querying the ATS boards where hiring teams actually publish openings, providing deterministic, direct-to-ATS application links.

## Domain

- **Applicant Tracking Systems (ATS)**: Cloud-hosted hiring platforms (Greenhouse, Lever, Ashby, Workable, Recruitee, SmartRecruiters, Teamtailor, etc.) where companies manage open requisitions.
- **Google Dork Queries**: Targeted Google search queries (`site:boards.greenhouse.io`, `site:jobs.lever.co`, etc.) executed via the Serper.dev search API.
- **Extraction Pipeline**: Progressive deterministic pipeline: discovery → fetching → extraction (structured JSON-LD / Schema.org → provider APIs → source-specific adapters → DOM / semantic fallbacks) → normalization → validation → presentation. Current production extraction is deterministic and does not actively invoke LLM-based extraction; missing or ambiguous fields remain unknown. (`AGENTS.md` describes LLM structured extraction only as a potential last-resort policy fallback and forbids using an LLM when deterministic structured data is available.)
- **Streaming Delivery**: The FastAPI backend progressively yields batches of jobs over HTTP Server-Sent Events (`event: results`, `event: done`, `event: error`), allowing instantaneous rendering of the first results while downstream ATS queries complete.

## Important Terms

| Term | Definition |
|---|---|
| **ATS** | Applicant Tracking System; platforms like Greenhouse, Lever, Ashby, Workable hosting primary job postings. |
| **Serper** | Serper.dev Google Search API provider used to dork for ATS job URLs. |
| **SSE** | Server-Sent Events (`text/event-stream`); one-way real-time streaming protocol from FastAPI to the browser. |
| **DoneMetrics** | Payload returned with `event: done` including `total`, `search_time_ms`, `serper_queries_used`, `serper_calls`, `cached`. |
| **Work Model / Arrangement** | Employment arrangement: `remote`, `hybrid`, `in_person` (`onsite`), or `unknown`. Governed by ADR 0002; strictly separate from applicant eligibility. |
| **Applicant Eligibility** | Country-aware evaluation (`eligible`, `restricted`, or `unknown`) derived from structured residence, regional, work authorization, payroll, and attendance restrictions against the user's selected ISO 3166-1 alpha-2 country. |
| **Extraction Confidence** | Numeric confidence score (0 to 1) representing evidence quality for extracted structured fields. |
| **Saved Results** | Cached search results preserved in the user's `localStorage` (capped at ~3MB) so users can return to previous search sets without expending API credits. |

## Actors

- **End User**: Interacts with the React/Vite single-page web application.
- **FastAPI Web Service**: Orchestrates search queries, rate limiting, and SSE streaming over `/search`.
- **Serper.dev API**: External Google Search API used for discovery queries.
- **Remote ATS Endpoints**: Public job boards and JSON endpoints fetched for metadata enrichment.

## Constraints

- **Square Design System (Non-Negotiable)**: All corners square (`--radius: 0`) across cards, inputs, selects, buttons, badges, chips, focus rings, sheets, and tooltips. Cream (`#FBF9F5`) and deep green (`#1B4332`) identity.
- **Serper API Budget**: Serper credits are limited (free tier). Outbound live queries must be strictly budgeted. Never run live searches for testing or verification (mock/fixtures only).
- **Backend API Invariance**: Frontend redesign must NOT change backend behavior, query parameters, API contracts, response shapes, or environment variables.
- **Platform Compatibility**: All commands and scripts must be Windows PowerShell compatible.
- **Framework Invariance**: React + Vite + Tailwind CSS + Base UI primitives. No migration to other frameworks.
- **Accessibility & Performance**: WCAG AA color contrast, full keyboard navigation, aria labels, no horizontal scroll, Lighthouse targets (Performance ≥ 90, Accessibility ≥ 95, Best Practices ≥ 95, SEO ≥ 90).

## Non-Goals

- User accounts, authentication, or cloud database storage (Neon/Vercel are strictly out of scope).
- Automated job application submission or resume parsing.
- Arbitrary framework migrations or replacement of existing backend search pipelines.
- Live deployment or touching production cloud infrastructure.

## Important Decisions

- **ADR 0001: Unknown Beats Wrong**: Missing evidence must result in null/unknown rather than invented data.
- **ADR 0002: Work Model Source Ladder**: Hierarchical classification for remote/hybrid/in-person status.
- **ADR 0003: Backend Owns Parsing**: The frontend must never re-parse raw descriptions or snippets to infer fields.
- **ADR 0004: Square Design System & Daybreak Craft**: Editorial, minimal, calm, typography-first, strict 0-radius geometry.
- **ADR 0005: Client-Side Visited State & Results Persistence**: Local storage stores visited URLs and recent search results with quota safeguards.
- **ADR 0030: Operational SQLite Database Isolation and Destructive Test Safety**: Operational `data/cache.sqlite`, sidecars, and backups are never test data; multi-layer runtime, E2E, ownership-cleanup, and CI guards fail closed before touching protected files.

## Source Discovery & Lifecycle Policy

- **Global by design (Nigeria as priority validation target, not boundary)**: Job discovery is global across all regions (Nigeria, Africa, Europe, North America, Asia, Latin America, Australia, and elsewhere). The product must never assume every user is Nigerian, and applicant eligibility must always be evaluated against a selectable applicant country—with equal structural support across countries while maintaining deliberate validation and quality attention on Nigeria and wider Africa.
- **Keep four dimensions strictly separate**:
  1. **Work arrangement**: `onsite`, `hybrid`, `remote`, or `unknown`.
  2. **Source geography**: Where the job board or aggregator is based.
  3. **Job geography**: Where the employer expects the role to be performed or where the role is located.
  4. **Applicant eligibility**: Which countries applicants may reside in, work from, or hold work authorization for (`eligible`, `restricted`, or `unknown` per selected applicant country, with retained evidence). Never infer applicant eligibility or worldwide availability from board country, employer HQ, job location, or a generic `remote` flag.
- **Permission & quality gates**: Optimize for fresh, genuinely accessible technical roles (early-career through senior) over provider count, popularity, raw volume, or scraping ease. Keep sources with unclear redistribution rights as `Discovery-only` or `Permission pending` (public HTTP access is not permission to republish). Investigate and implement one provider at a time with bounded evidence.
- **Rejected-provider cleanup**: When a source is `Rejected` or `Retired`, remove active configuration, URL parsing, regexes, canonical URL builders, normalizers, enrichers, routers, adapters, frontend inventories, tests, and dependencies while preserving justified shared code, `docs/steps/` historical records, `HISTORICAL_FULL_INVENTORIES` migration tables, and operational SQLite history, and synchronize `docs/job-source-catalog.md`.
