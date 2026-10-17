# Project Context: Bottom Pot

> Authoritative source of project and domain knowledge for Bottom Pot.
> Kept synchronized with architectural decisions in `docs/adr/`.

---

## Product

Bottom Pot is an ATS-first job discovery engine. It searches public Applicant Tracking Systems (Greenhouse, Lever, Ashby, Workable, and 16+ others) directly via Google dork queries over Serper.dev, streams fresh job listings to the browser via Server-Sent Events (SSE), and extracts high-confidence, structured job data without aggregator noise or duplicate postings.

## Users

- **Software engineers, product designers, and technology professionals** looking for high-signal, direct-to-company job opportunities without aggregator spam.
- **Nigerian developers and global remote job seekers** looking for verified remote roles and opportunities open to Nigerian candidates.

## Core Problem

Mainstream job boards and aggregators (LinkedIn, Indeed, generic scrapers) are riddled with duplicate reposts, stale ghost jobs, affiliate redirects, and stripped application metadata. Bottom Pot bypasses aggregator middlemen by querying the ATS boards where hiring teams actually publish openings, providing deterministic, direct-to-ATS application links.

## Domain

- **Applicant Tracking Systems (ATS)**: Cloud-hosted hiring platforms (Greenhouse, Lever, Ashby, Workable, Recruitee, SmartRecruiters, Teamtailor, etc.) where companies manage open requisitions.
- **Google Dork Queries**: Targeted Google search queries (`site:boards.greenhouse.io`, `site:jobs.lever.co`, etc.) executed via the Serper.dev search API.
- **Extraction Pipeline**: Progressive pipeline: discovery → fetching → extraction (JSON-LD / Schema.org → ATS-specific API/DOM → adapters → LLM fallback) → normalization → validation → presentation.
- **Streaming Delivery**: The FastAPI backend progressively yields batches of jobs over HTTP Server-Sent Events (`event: results`, `event: done`, `event: error`), allowing instantaneous rendering of the first results while downstream ATS queries complete.

## Important Terms

| Term | Definition |
|---|---|
| **ATS** | Applicant Tracking System; platforms like Greenhouse, Lever, Ashby, Workable hosting primary job postings. |
| **Serper** | Serper.dev Google Search API provider used to dork for ATS job URLs. |
| **SSE** | Server-Sent Events (`text/event-stream`); one-way real-time streaming protocol from FastAPI to the browser. |
| **DoneMetrics** | Payload returned with `event: done` including `total`, `search_time_ms`, `serper_queries_used`, `serper_calls`, `cached`. |
| **Work Model** | Employment arrangement: `remote`, `hybrid`, `in_person`, or `unknown`. Governed by ADR 0002. |
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
