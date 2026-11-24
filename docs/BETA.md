# Bottom Pot Beta Guide: Tester Tasks, Telemetry & Deploy Options

Guide for running structured usability testing, checking analytics/telemetry status, and optionally exposing a build to external testers once the owner explicitly permits hosting.

---

## 1. Five Beta Tester Tasks & Observation Rubric

Do **not** coach testers through clicks before they attempt each task. Record outcomes in blank session logs (never fabricate results).

| # | Tester Task | What Success Looks Like | What to Observe |
|---|---|---|---|
| **1** | **Find a relevant role** | Tester enters a role keyword (e.g., `Backend Engineer`), optionally refines city/work model inside `Filters`, submits a search, opens a matching posting, and explains why it matches. | Search latency perception, clarity of progressive streaming and filters, whether stale vs. fresh roles or error states confuse expectations. |
| **2** | **Check eligibility for your country** | Tester selects their country in `"Where can you work from?"` (search form or toolbar) and accurately identifies whether a role is `Eligible`, `Restricted`, or `Unverified` and why (`Evidence details`). | Discoverability of `"Where can you work from?"`, trust in reason explanations, whether remote vs. worldwide distinctions are understood. |
| **3** | **Find a worldwide-remote role** | Tester uses Remote filter + country selection to locate an explicitly worldwide-remote role distinct from country-restricted remote listings. | Whether testers confuse generic `"Remote"` labels with `"Worldwide"`, usefulness of work-model badges + eligibility scope labels. |
| **4** | **Find an early-career role** | Tester locates an intern, graduate, or junior technical opening (using search terms/filters) and distinguishes it from senior roles. | Clarity of role titles, posting dates, freshness badges, and `"Older postings"` divider behavior. |
| **5** | **Reach the original application page** | Tester opens the job detail sheet (`DetailSheet`), inspects description/compensation/freshness timestamps, locates the direct employer ATS apply button, and notes how to flag bad data (`Report a problem with this listing`, if configured). | Confidence in apply link destination (`via <provider>`), copy/shortlist usability, mobile `390px` comfort and readability. |

### Metrics to Record per Session (Template — Record Actual Observations Only)

| Metric | Tester 1 | Tester 2 | Tester 3 | Tester 4 | Tester 5 |
|---|---|---|---|---|---|
| Tasks completed unassisted (`/5`) | | | | | |
| Time to first opened relevant role (sec) | | | | | |
| False-eligibility misunderstandings (`count`) | | | | | |
| UI blockers on desktop or `390px` mobile | | | | | |
| Broken/stale/mislabeled listings reported (`count`) | | | | | |

---

## 2. TelemetryDeck Audit & Privacy-Safe Setup Steps

### Current Repository Audit

- **Product analytics SDK status:** `@telemetrydeck/sdk` (or any third-party analytics SDK) is **not installed or configured** in `frontend/package.json` or `frontend/src/`.
- **Existing `TelemetryDeck.tsx` note:** `frontend/src/components/TelemetryDeck.tsx` is strictly an internal **admin-only** SSE diagnostic drawer (`mode === 'admin'`) rendering request counters (`serper_calls`, `pages_fetched`, `budget_exhausted`). It sends **no** external analytics events.
- **No external telemetry is enabled by default.**

### Exact Configuration Steps (If/When Owner Enables TelemetryDeck)

Do **not** install analytics during cleanup/beta-prep without owner rollout approval. When enabling TelemetryDeck for beta telemetry, follow these steps strictly:

1. **Install the official Web SDK** inside `frontend/`:
   ```bash
   npm --prefix frontend install @telemetrydeck/sdk
   ```
2. **Add public client App ID** via gitignored `frontend/.env.local` (and document a placeholder in `frontend/.env.example`):
   ```env
   VITE_TELEMETRYDECK_APP_ID=<your-telemetrydeck-app-uuid>
   ```
3. **Create a strict allowlisted wrapper** (`frontend/src/lib/analytics.ts`) using an anonymous ephemeral per-session client ID (no cookies, no email, **no raw search query string `keywords`**, no listing titles/URLs, no IP logging).
4. **Emit strictly these 7 events (exact names + safe payload keys only):**
   - `search_submitted`: `{ has_location: boolean, work_model, post_age, applicant_country_set: boolean, platform_count: number }` (NEVER include raw keyword text)
   - `results_shown`: `{ total_results: number, incomplete: boolean, has_country: boolean }`
   - `applicant_country_selected`: `{ country_code: string, surface: 'form' | 'toolbar' }`
   - `eligibility_filter_applied`: `{ filter_mode: string }`
   - `job_opened`: `{ provider: string, freshness_tier: string, eligibility_status: string }`
   - `application_link_clicked`: `{ provider: string, work_model: string }`
   - `search_zero_results`: `{ incomplete: boolean, post_age: string, has_country: boolean }`

---

## 3. Deployment Guide for Beta Testers

### Pre-Flight Checklist Before Any External Beta Run

1. For **cloud Vercel + Neon** deployment, ensure your Neon database is provisioned and seeded (`DATABASE_URL`), and generate high-entropy secrets (`CRON_SECRET`, `ADMIN_PASSWORD`, 32+ char `ADMIN_SESSION_SECRET`). For local/container runs, verify `BOTTOM_POT_DATA_DIR` (`scripts/db_backup.py check --allow-operational-db`, [`docs/operations/RUNBOOK.md`](operations/RUNBOOK.md)).
2. Configure public frontend env vars if needed (`VITE_LOGO_DEV_TOKEN=pk_...`, optional `VITE_REPORT_PROBLEM_URL=https://...`). Leave `VITE_API_BASE_URL` **unset** on unified Vercel deploys so API calls stay same-origin.
3. Restrict the Logo.dev `pk_` key to your exact Vercel domain(s) in the Logo.dev dashboard and verify `"Logos provided by Logo.dev"` footer attribution on your free plan.
4. Configure runtime secrets in Vercel Project Settings (never commit): `DATABASE_URL`, `CRON_SECRET`, `SERPER_API_KEY`, `SERPER_MODE=fallback`, strong `ADMIN_PASSWORD`, `ADMIN_SESSION_SECRET`, and `TRUST_PROXY_HEADERS=true`.

### Option 1 (Recommended): 100% Vercel (SPA + FastAPI) + Neon Postgres

Import the repository root in **Vercel** (`Root Directory = .`). Root `vercel.json` builds `frontend/` into `frontend/dist`, deploys the FastAPI ASGI app via `api/index.py`, routes `/api/*`, `/health`, `/subscribe`, and SSE `/search` to Python, and configures a daily Hobby-plan cron (`0 6 * * *`) hitting `/api/cron/monitor`.

```bash
# Vercel Project Environment Variables (all confidential values set in dashboard)
DATABASE_URL=postgresql://.../neondb?sslmode=require
CRON_SECRET=<32+-char-random-secret>
SERPER_API_KEY=<your-serper-key>
SERPER_MODE=fallback
ADMIN_PASSWORD=<strong-password>
ADMIN_SESSION_SECRET=<32+-char-random-secret>
TRUST_PROXY_HEADERS=true
# Optional public frontend build vars (leave VITE_API_BASE_URL unset for same-origin):
VITE_LOGO_DEV_TOKEN=pk_...
```

For faster board refreshes than Vercel Hobby's once-daily cron cap, set GitHub repository variable `BOTTOM_POT_URL` (`https://your-app.vercel.app`) and repository secret `CRON_SECRET` so `.github/workflows/board-monitor.yml` polls `/api/cron/monitor?max_boards=10` every 30 minutes.

### Option 2: Split Host (Vercel Frontend + Persistent Container Backend)

If you prefer an always-on Docker daemon with local disk storage instead of Neon Serverless Postgres, deploy static `frontend/` on Vercel (`Root Directory = frontend`, `VITE_API_BASE_URL=https://your-backend.example`) and run the root `Dockerfile` on a container host with a persistent volume mounted at `/data`:

```bash
# Backend container environment
BOTTOM_POT_DATA_DIR=/data
BOTTOM_POT_ALLOW_OPERATIONAL_DB=1
MONITORING_ENABLED=true
SERPER_MODE=fallback
TRUST_PROXY_HEADERS=true
CORS_ALLOW_ORIGINS=https://your-app.vercel.app
ADMIN_COOKIE_SAMESITE=none
```

Always keep `/data/cache.sqlite` backed up (`scripts/db_backup.py backup --allow-operational-db`) before schema upgrades.

### Option 3: Single-Machine Local Run + HTTPS Tunnel

Suitable for short moderated tester sessions from an owner machine:

```powershell
# Terminal 1: build UI + launch API bound to loopback only
npm --prefix frontend run build
$env:BOTTOM_POT_ALLOW_OPERATIONAL_DB = "1"
python -m uvicorn src.api.main:app --host 127.0.0.1 --port 8000
```

In a second terminal, point an HTTPS tunnel you control (for example, `cloudflared tunnel --url http://127.0.0.1:8000`) at `127.0.0.1:8000`, verify `GET /health` returns `"status": "ok"`, and tear down the tunnel when tester sessions end.
