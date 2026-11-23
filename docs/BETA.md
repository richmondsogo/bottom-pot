# Bottom Pot Beta Guide: Tester Tasks, Telemetry & Deploy Options

Guide for running structured usability testing, checking analytics/telemetry status, and optionally exposing a build to external testers once the owner explicitly permits hosting.

---

## 1. Five Beta Tester Tasks & Observation Rubric

Do **not** coach testers through clicks before they attempt each task. Record outcomes in blank session logs (never fabricate results).

| # | Tester Task | What Success Looks Like | What to Observe |
|---|---|---|---|
| **1** | **Find a relevant role** | Tester enters a role keyword (e.g., `Backend Engineer`), submits a search, opens a matching posting, and explains why it matches. | Search latency perception, clarity of `Try:` suggestions/filters, whether stale vs. fresh roles or error states confuse expectations. |
| **2** | **Check eligibility for your country** | Tester selects their country in `"Where can you work from?"` (search form or toolbar) and accurately identifies whether a role is `Eligible`, `Restricted`, or `Unverified` and why (`Evidence details`). | Visibility of the missing-country reminder (`no-country-notice`), trust in reason explanations, whether remote vs. worldwide distinctions are understood. |
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

## 3. Owner-Ready Deploy Guide (**UNTESTED — Owner Authorization Required**)

> **Important Constraint Notice (`UNTESTED`):**  
> `AGENTS.md` and `CONTEXT.md` currently declare cloud hosting (`Vercel`, `Neon`) and live public deployments **out of scope** and restrict testing to local runs. **No live server has been deployed or verified here.** Before exposing any URL to external testers, the owner must explicitly amend that local-only hosting rule in `AGENTS.md` and `CONTEXT.md` and provision their own runtime host/tunnel.

### Pre-Flight Checklist Before Any External Beta Run

1. Amend the local-only hosting rule in [`AGENTS.md`](../AGENTS.md) and [`CONTEXT.md`](../CONTEXT.md).
2. Migrate and seed your operational database outside the git tree (`BOTTOM_POT_DATA_DIR`, [`docs/operations/RUNBOOK.md`](operations/RUNBOOK.md)) and run `scripts/db_backup.py check --allow-operational-db`.
3. Configure public Logo.dev publishable key (`VITE_LOGO_DEV_TOKEN=pk_...`) and optional issue-report endpoint (`VITE_REPORT_PROBLEM_URL=https://...`) in `frontend/.env.local` before building (`npm --prefix frontend run build`).
4. Restrict the Logo.dev `pk_` key to your exact beta domain(s) in the Logo.dev dashboard and verify `"Logos provided by Logo.dev"` footer compliance on your free plan.
5. Set server secrets in `.env` (never commit): `SERPER_API_KEY`, strong `ADMIN_PASSWORD`, 32+ char `ADMIN_SESSION_SECRET`, plus `BOTTOM_POT_DATA_DIR`.

### Option A: Single-Machine Local Run + HTTPS Tunnel (**UNTESTED**)

Suitable for short moderated tester sessions from an owner machine:

```powershell
# Terminal 1: build UI + launch API bound to loopback only
npm --prefix frontend run build
$env:BOTTOM_POT_ALLOW_OPERATIONAL_DB = "1"
python -m uvicorn src.api.main:app --host 127.0.0.1 --port 8000
```

In a second terminal, point an HTTPS tunnel you control (for example, `cloudflared tunnel --url http://127.0.0.1:8000`) at `127.0.0.1:8000`, verify `GET /health` returns `"status": "ok"`, and tear down the tunnel when tester sessions end.

### Option B: Self-Hosted Container with External Volume Mount (**UNTESTED**)

Build/run behind an HTTPS reverse proxy (Caddy/Nginx) with a persistent volume mapped outside the app image to `BOTTOM_POT_DATA_DIR`:

```dockerfile
# Illustrative single-container build sketch (untested)
FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends nodejs npm && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY frontend/package*.json frontend/
RUN npm --prefix frontend ci
COPY . .
ARG VITE_LOGO_DEV_TOKEN=""
ARG VITE_REPORT_PROBLEM_URL=""
RUN VITE_LOGO_DEV_TOKEN="$VITE_LOGO_DEV_TOKEN" VITE_REPORT_PROBLEM_URL="$VITE_REPORT_PROBLEM_URL" npm --prefix frontend run build
ENV BOTTOM_POT_DATA_DIR=/var/lib/bottom-pot
VOLUME ["/var/lib/bottom-pot"]
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Always keep `BOTTOM_POT_DATA_DIR` backed up (`scripts/db_backup.py backup --allow-operational-db`) before upgrades.
