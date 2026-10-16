# Bottom Pot — ATS Job Search

Bottom Pot is a fast, targeted job discovery engine for software and technology opportunities—focusing on remote roles and positions relevant to Nigerian developers.

Instead of scraping aggregators like LinkedIn or Indeed (which frequently surface stale, duplicate, or ghost postings), Bottom Pot queries public applicant tracking systems (Greenhouse, Lever, Ashby, Workable, BambooHR, Workday, SmartRecruiters, and 11 others, plus Nigerian job boards) directly at the source.

---

## Architecture

```
1. Discovery      → Serper.dev Google dorks per ATS platform (3 pages max, bounded cost)
2. URL Routing    → ats_url_parser.py extracts platform, tenant slug, and job identifier
3. Enrichment     → ats_api_client.py (public APIs) or ats_page_enricher.py (JSON-LD, CXS, DOM)
4. Normalization  → field_normalizer.py & work_model.py derive fields with literal evidence
5. Resilience     → circuit breaker, per-host semaphores, streaming size caps (3 MB)
6. Persistence    → SQLite cache for queries & URL payloads (data/cache.sqlite) + in-memory LRU
7. Streaming API  → FastAPI Server-Sent Events (GET /search) streaming batches to client
8. UI Presentation→ React 19 + TypeScript + custom CSS design tokens (frontend/)
```

---

## Core Principle: "Unknown Beats Wrong"

Bottom Pot enforces a strict parsing philosophy: **no fallback may turn absence of evidence into a fabricated value**.

- If a posting does not explicitly state whether it is remote, hybrid, or on-site, `work_model` is `null` (`"—"` in the UI).
- Every derived `work_model` records its `work_model_source` (`api`, `page_label`, `description`) and a literal verbatim snippet in `work_model_evidence`.
- The backend owns parsing; the frontend never re-parses snippets or regexes titles.
- See our architectural decisions in [`docs/adr/0001-unknown-beats-wrong.md`](docs/adr/0001-unknown-beats-wrong.md) and [`docs/adr/0002-work-model-source-ladder.md`](docs/adr/0002-work-model-source-ladder.md).

---

## Supported ATS Platforms

- **API-Enriched**: Greenhouse, Lever, Ashby, SmartRecruiters, Workable, BambooHR, Recruitee.
- **Structured / CXS Enriched**: Workday (public CXS JSON endpoint), Teamtailor, Jobvite, Personio, Breezy HR, JazzHR.
- **Metadata / DOM Scraped**: iCIMS, Taleo, JobAdder, Avature, SAP SuccessFactors.
- **Nigerian Job Boards**: Jobberman, MyJobMag, HotNigerianJobs (when Nigerian boards are included).

Full configurations and domain site operators live in [`src/project_files/config.py`](src/project_files/config.py).

---

## Getting Started

### Prerequisites
- Python 3.10+
- Node.js 18+ and npm
- A [Serper.dev](https://serper.dev) API key (free tier includes 2,500 queries)

### 1. Backend Setup
```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### 2. Frontend Setup
```powershell
cd frontend
npm install
npm run build
cd ..
```

### 3. Environment Configuration
Copy `.env.example` to `.env` and provide your Serper API key:
```powershell
Copy-Item .env.example .env
```
Edit `.env`:
```ini
SERPER_API_KEY=your_actual_serper_key_here
```

### 4. Run the Application
Start the FastAPI server:
```powershell
uvicorn src.api.main:app --reload
```
Open [http://127.0.0.1:8000](http://127.0.0.1:8000) in your browser. The backend automatically serves the compiled production build from `frontend/dist`.

---

## Key Configuration Knobs

Configured via environment variables or `.env` ([`src/config.py`](src/config.py)):

| Variable | Default | Description |
|---|---|---|
| `SERPER_MODE` | `live` | `live` makes outbound Serper calls; `cache_only` serves strictly from cached queries. |
| `SERPER_DAILY_BUDGET` | `200` | Maximum Serper queries allowed per UTC day (persisted in SQLite). Prevents unexpected bills. |
| `SERPER_CACHE_TTL_HOURS` | `12` | TTL for persistent Serper search query caching in SQLite. |
| `URL_CACHE_TTL_HOURS` | `24` | TTL for individual job page enrichment payloads in SQLite. |
| `SQLITE_DB_PATH` | `data/cache.sqlite` | Path to persistent cache database (gitignored). |
| `GLOBAL_CONCURRENCY_LIMIT`| `20` | Max concurrent outbound HTTP requests across all domains. |
| `PER_HOST_CONCURRENCY_LIMIT`| `3` | Max concurrent outbound HTTP requests per ATS domain. |
| `CIRCUIT_BREAKER_FAILURE_THRESHOLD`| `5` | Consecutive failures before tripping the circuit breaker for a host. |
| `CIRCUIT_BREAKER_COOLDOWN_SECONDS` | `600` | Cooldown period (10 minutes) before re-attempting a tripped host. |
| `MAX_RESPONSE_BYTES` | `3145728` | Stream read cap per page (3 MB) to prevent memory exhaustion. |
| `RATE_LIMIT_SEARCH` | `20/hour` | Rate limit on the `/search` SSE endpoint per client IP. |
| `IN_MEMORY_CACHE_MAX_ENTRIES` | `100` | In-memory whole-search LRU cache cap. |

---

## Developer Tooling & Scripts

- `python scripts/capture_fixtures.py`: Downloads and archives live job postings and API responses into `tests/fixtures/real/` for deterministic regression testing.
- `python scripts/audit_jobs.py`: Evaluates description quality, HTML stripping, and boilerplate leakage across live results.
- `python scripts/eval_work_model.py`: Benchmarks work-model extraction accuracy against labeled ground truth.
- `python scripts/summarize_results.py`: Analyzes a results run, reporting provider yield, null work models, provenance breakdown, and missing fields.

---

## Testing

### Unit & Integration Tests (pytest)
```powershell
pytest
```
Runs 290+ tests covering query building, ATS URL parsing, API clients, field normalization, cost & cache controls, circuit breakers, and real API fixtures.

### End-to-End Tests (Playwright)
```powershell
npx playwright test
```
Runs 12 headless browser tests testing SSE streaming, keyboard navigation (`j`/`k`, `Enter`, `Esc`, `/`), density switching, quick-filter chips (`aria-pressed`), and details panel rendering.

---

## License

MIT
