# Bottom Pot — Direct ATS Job Discovery Engine

[![Verification Suite](https://img.shields.io/badge/verification-passing-1A382B?style=flat-square)](#verification--testing)
[![WCAG Accessibility](https://img.shields.io/badge/accessibility-100%25%20AA-1A382B?style=flat-square)](#design-system--frontend-architecture)
[![Design](https://img.shields.io/badge/design-square%20editorial-1A382B?style=flat-square)](#design-system--frontend-architecture)

Bottom Pot is an editorial, high-density job discovery product for software and technology opportunities, specializing in remote roles and positions relevant to Nigerian developers.

![Bottom Pot Results UI](docs/design/after-restore/results_1440x900_light.png)

---

## Why Search ATS Platforms Directly?

Traditional job boards and aggregators (like LinkedIn, Indeed, and ZipRecruiter) are inundated with stale reposts, recruiter spam, sponsored fluff, duplicate postings, and "ghost jobs" that have already been filled. 

Bottom Pot cuts through the noise by querying public **Applicant Tracking Systems (ATS)** directly at the source—including Greenhouse, Lever, Ashby, Workable, BambooHR, SmartRecruiters, Workday, and 14+ other platforms, alongside curated Nigerian job boards. By constructing targeted Google dork queries via Serper.dev, Bottom Pot surfaces fresh postings published directly to company career boards.

### Core Principle: "Unknown Beats Wrong"
Bottom Pot enforces strict extraction integrity: **no fallback may turn absence of evidence into a fabricated value**.
- If an employer does not explicitly state whether a role is remote, hybrid, or on-site, `work_model` is strictly `null` (rendered as a clean empty cell in the UI rather than a synthetic `"—"` placeholder).
- Every derived work model preserves its source (`api`, `page_label`, `description`) and a literal verbatim snippet as proof.
- The backend owns parsing; the frontend never re-parses snippets or applies regexes to titles.
- See our architectural decisions in [`docs/adr/0001-unknown-beats-wrong.md`](docs/adr/0001-unknown-beats-wrong.md) and [`docs/adr/0002-work-model-source-ladder.md`](docs/adr/0002-work-model-source-ladder.md).

---

## Architecture Overview

```
1. Discovery      → Serper.dev Google dorks per ATS platform + native Nigerian board feeds
2. URL Routing    → ats_url_parser.py extracts platform, tenant slug, and job identifier
3. Enrichment     → ats_api_client.py, ats_page_enricher.py, and nigerian_scrapers.py detail fetchers
4. Normalization  → field_normalizer.py (HTML → Markdown) & work_model.py (literal evidence ladder)
5. Resilience     → Circuit breakers, per-host semaphores, 3MB stream read caps
6. Persistence    → SQLite query cache & URL payloads (data/cache.sqlite) + in-memory LRU
7. Streaming API  → FastAPI Server-Sent Events (GET /search) streaming real-time batches
8. UI Experience  → React 19 + TypeScript + Custom CSS Tokens (editorial square design)
```

---

## Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+ and npm
- Serper.dev API key (for live searches; mock mode requires no key)

### Clone the Repository
```powershell
git clone https://github.com/richmondsogo/bottom-pot-v1.git
cd bottom-pot-v1
```

### 1. Web Application Setup
#### Backend:
```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

#### Frontend Build:
```powershell
cd frontend
npm install
npm run build
cd ..
```

#### Environment Configuration:
Copy `.env.example` to `.env` and insert your Serper API key:
```powershell
Copy-Item .env.example .env
```
*(Configure `SERPER_API_KEY` in `.env`)*

#### Run the Web App:
```powershell
uvicorn src.api.main:app --reload
```
Open [http://127.0.0.1:8000](http://127.0.0.1:8000) in your browser. The backend automatically serves the compiled production build from `frontend/dist/`.

---

### 2. CLI Usage
Bottom Pot also includes a rich command-line interface for terminal-based searches and exports:

```powershell
# Search for remote React roles published in the last 7 days
python main.py --job-title "React Engineer" --remote --days-back 7

# Search for Nigerian Python opportunities and export to CSV
python main.py --job-title "Python Developer" --location "Nigeria" --export-csv "results.csv"

# Run in cache-only mode (zero outbound Serper API calls)
python main.py --job-title "Backend Engineer" --strategy serper
```

CLI options include:
- `--job-title`: Job title to search for (required).
- `--location`: Location context added to the dork query.
- `--country-code`: Restrict search to a country's Google index (e.g. `us`, `gb`, `ng`).
- `--days-back`: Age limit for postings in days.
- `--remote`: Filter for remote roles.
- `--export-csv`: Filepath to save results as CSV.
- `--export-json`: Filepath to save results as JSON.

---

## Mock Data Mode (Zero Credits Used)

To explore, design, or develop the user interface without consuming Serper search credits:

Append `?mock=1` to the URL in your browser:
```
http://127.0.0.1:8000/?mock=1
```

The mock fixture dataset includes realistic edge cases:
- 150+ realistic tech postings across Greenhouse, Lever, Ashby, Workable, and more
- Multi-byte non-Latin characters (Japanese postings)
- Very long job titles and company names
- Missing salary, location, or work model entries
- Simulated states: `?mock=1&state=empty` (No results), `?mock=1&state=error` (Error handling), `?mock=1&state=slow` (Loading skeleton & timer).

---

## Configuration Knobs

Configurable via environment variables or `.env` ([`src/config.py`](src/config.py)):

| Variable | Default | Description |
|---|---|---|
| `SERPER_API_KEY` | *(None)* | Your Serper.dev API key. |
| `SERPER_MODE` | `live` | `live` runs outbound dork searches; `cache_only` serves strictly from cached SQLite results. |
| `SERPER_DAILY_BUDGET` | `200` | Maximum Serper queries allowed per UTC day (persisted in SQLite, auto-resets at midnight). |
| `SERPER_CACHE_TTL_HOURS` | `12` | TTL in hours for persistent Serper search query caching in SQLite. |
| `URL_CACHE_TTL_HOURS` | `24` | TTL in hours for individual job page enrichment payloads in SQLite. |
| `SQLITE_DB_PATH` | `data/cache.sqlite` | Filepath to persistent cache database (gitignored). |
| `GLOBAL_CONCURRENCY_LIMIT` | `20` | Max concurrent outbound HTTP requests across all domains. |
| `PER_HOST_CONCURRENCY_LIMIT` | `3` | Max concurrent outbound HTTP requests per ATS domain. |
| `CIRCUIT_BREAKER_FAILURE_THRESHOLD` | `5` | Consecutive failures before tripping the circuit breaker for a host. |
| `CIRCUIT_BREAKER_COOLDOWN_SECONDS` | `600` | Cooldown period (10 minutes) before re-attempting a tripped host. |
| `MAX_RESPONSE_BYTES` | `3145728` | Stream read cap per page (3 MB) to prevent memory exhaustion. |
| `RATE_LIMIT_SEARCH` | `20/hour` | Rate limit on the `/search` SSE endpoint per client IP. |
| `IN_MEMORY_CACHE_MAX_ENTRIES` | `100` | In-memory whole-search LRU cache cap. |

---

## Design System & Frontend Architecture

Bottom Pot uses a calm, typography-first **Square Design System** inspired by brianlovin.com and built on **shadcn / Base UI** primitives:
- **Square Geometry (Non-Negotiable)**: `--radius: 0rem` strictly enforced across buttons, inputs, selects, sheets, popovers, and dialogs.
- **Color Palette & Themes**: Warm editorial cream (`#FAF8F5`) light mode, carbon (`#0C0D0C`) dark mode, deep forest green accent (`#1A382B` light / `#2E7D52` dark), strict green usage budget, and high-contrast ink tiers exceeding WCAG AA standards.
- **Typography System**: Strict two-family hierarchy using self-hosted **Geist Variable** (all UI text, headings, labels) and **DM Mono** (tabular numbers, platform slugs, kbd hints) with zero external network requests.
- **Fixed-Layout Semantic Table**: Pixel-perfect fixed-layout `<table>` (`table-layout: fixed`) with strict column widths (Role flexible, Company 240px, Location 220px, Salary 130px conditional, Work model 120px, Posted 100px), 28px square company monograms with lowercase mono platform slugs underneath, and 2px green hover bars. Rows transform into structured cards on mobile (<768px).
- **Sanitized Markdown Preview (`DetailSheet.tsx`)**: Renders `job.description` and `job.requirements` using `react-markdown`, `remark-gfm`, and `rehype-sanitize` mapped to Square Design System typography tokens (clean section headings, bulleted/numbered lists, bold/italic emphasis, safe external links) with an honest fallback when a board omits description text.
- **Deep Nigerian Board Enrichment (`nigerian_scrapers.py`)**:
  - **Jobberman**: Extracts search-card summaries (`p.md\:pl-5`) and concurrently enriches matched listings from `<article class="job__details">` (`Job Summary` + `Job Description/Requirements`) into structured Markdown.
  - **HotNigerianJobs**: Routes searches concurrently to native `/role/<id>/` and `/field/<id>/` feeds when `/?s=` returns the homepage roundup feed, resolves homepage `#slug` placeholders via their roundup detail page for dedicated `/hotjobs/<id>/<slug>.html` URLs and salaries, and enriches single-role `.mycase4` pages (stripping embedded AdSense tags) into Markdown.
  - **MyJobMag & NgCareers**: Extracts card descriptions and structured work-model provenance.
- **Saved Jobs ("Shortlist") & Application Stage Tracker (`savedJobs.ts`)**: Bookmark postings via the `DetailSheet` button or `s` keyboard shortcut, track application pipeline stages (`Saved` · `Applied` · `Interviewing` · `Archived`) with inline stage badges in the table and mobile cards, and filter via the `Saved (N)` toolbar switch or landing shortlist shortcut.
- **Shareable URL State Sync & 1-Click Recent Searches (`urlState.ts`)**: Synchronizes active query and filter state with browser query parameters (`?q=...&loc=...&wm=...&saved=1`), provides a **Copy search link** action in the summary bar, and persists up to 5 one-click **Recent** search presets beneath `Try:` on the landing form.
- **Command Palette & Overflow Menu**: Accessible `Cmd+K` / `Ctrl+K` command menu powered by cmdk for instant keyboard navigation, theme toggling, and exports. Single quiet search summary bar with consolidated overflow menu (⋯).
- **Accessibility & Web Vitals**: 100% Lighthouse Accessibility, Best Practices, and SEO; 0 Axe-core violations; 0.069 CLS; native View Transitions API.
- **Keyboard Navigation**: Full shortcuts support (`j`/`k` to navigate postings, `Enter`/`o` to view details, `s` to save/bookmark to shortlist, `Esc` to close, `/` to focus filter, `⌘K` for command palette, `?` for help).

For full design tokens and implementation guidelines, see [`DESIGN.md`](DESIGN.md) and [`docs/FRONTEND.md`](docs/FRONTEND.md).

---

## Developer Tooling & Verification

### Unified Project Verification
Run the complete automated verification suite (secrets scan, linter, unit tests, build, backend tests, Playwright e2e with spacing/column/green audits, CSS cascade lint):
```powershell
.\scripts\verify.ps1
```

### Component-Specific Verification
- **Frontend Unit Tests**: `cd frontend && npm test` (74 tests passing in Vitest).
- **Frontend Linter**: `cd frontend && npm run lint` (0 errors, 0 warnings in oxlint).
- **Production Build**: `cd frontend && npm run build` (TypeScript check + Vite production bundle).
- **CSS Cascade Lint**: `node scripts/lint_css_cascade.js` (ensures base resets remain inside `@layer base`).
- **Backend Tests**: `pytest` (301 tests covering ATS parsers, Nigerian scrapers, real HTML fixtures, normalizers, and caching).
- **Playwright E2E Suite**: `npx playwright test` (14 automated suites testing search, Markdown preview & shortlist pipeline, keyboard navigation, visited dimming, spacing audit, column alignment audit, green budget audit, and Axe-core accessibility).
- **Evaluation Scripts**:
  - `python scripts/eval_work_model.py`: Benchmarks work-model extraction accuracy against labeled ground truth.
  - `python scripts/audit_jobs.py`: Evaluates description quality and boilerplate leakage across results.
  - `python scripts/summarize_results.py`: Analyzes provider yield, null work models, and missing fields.

---

## Known Limitations

1. **Serper Quota Constraints**: Live searches rely on external Google dork queries via Serper.dev. Users on free tiers should use cached results or mock mode during development.
2. **ATS Layout Evolution**: Non-API ATS providers that rely on DOM scraping (such as older Taleo or iCIMS portals) can change page layouts over time, triggering our "unknown beats wrong" fallback rather than inferring bad data.
3. **Dynamic Single-Page Applications**: Some enterprise career portals load postings exclusively via client-side JavaScript without exposing structured JSON-LD or public REST endpoints. These postings may show limited metadata in search results.

---

## License

MIT
