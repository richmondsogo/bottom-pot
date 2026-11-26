# Security Policy

## Supported Scope & Data Classification

Bottom Pot combines a FastAPI backend (`src/`, deployed via `api/index.py` or `uvicorn`) and a React/Vite frontend (`frontend/`). It runs locally with SQLite (`BOTTOM_POT_DATA_DIR`) and deploys on Vercel Serverless (`vercel.json`) backed by Neon PostgreSQL (`DATABASE_URL` / `POSTGRES_URL`) with scheduled `/api/cron/monitor` refreshes.

- **Operational data:** `cache.sqlite` (and its `-wal`/`-shm` sidecars) and `subscriptions.csv` store local search caches, board polling state, and email subscriptions. They live outside the repo by default (`BOTTOM_POT_DATA_DIR`, `ADR 0032`) or in legacy `<repo>/data/` and are never committed. Cloud deployments store board/cache/subscription tables in Neon PostgreSQL (`DATABASE_URL` / `POSTGRES_URL`).
- **Public client config vs. server secrets:**
  - `VITE_API_BASE_URL`, `VITE_LOGO_DEV_TOKEN` (`pk_*`), `VITE_REPORT_PROBLEM_URL`, `VITE_CONTACT_EMAIL`, and `VITE_ENABLE_MOCK` are build/client configuration. Restrict `pk_*` tokens by domain in the Logo.dev dashboard.
  - `SERPER_API_KEY`, `DATABASE_URL`, `POSTGRES_URL`, `CRON_SECRET`, `ADMIN_PASSWORD`, `ADMIN_SESSION_SECRET`, and any `sk_*` token are server secrets. They belong **only** in local gitignored `.env` files or runtime environment variables.
- **Client analytics boundary (`frontend/src/lib/analytics.ts`):** `@vercel/analytics/react` (`<Analytics />`) records aggregate page views only on public production routes (`shouldEnableVercelAnalytics()` disables analytics in Vite dev builds, mock mode, Playwright `navigator.webdriver` runs, and `/admin`, with zero search query payloads, cookies, or user accounts).

## Security Boundaries Implemented in Code

1. **SSRF & Outbound HTTP (`src/safety/url_safety.py`, `src/providers/http.py`):**
   - Only `https://` targets resolving exclusively to globally routable public IPv4/IPv6 addresses are permitted. Private, loopback, link-local, carrier-grade NAT, multicast, and reserved ranges are rejected before connection and on every HTTP redirect hop (`follow_redirects=False`).
   - Streaming downloads enforce fail-closed byte limits (`MAX_RESPONSE_BYTES`, `RECRUITEE_BOARD_MAX_RESPONSE_BYTES`, `PINPOINT_BOARD_MAX_RESPONSE_BYTES`).
2. **Operational Database Protection (`src/safety/db_safety.py`, `ADR 0030`, `ADR 0032`):**
   - Test suites, Playwright E2E runners, and read-only utilities fail closed (`SafetyError` / `UnsafeDatabasePathError`) if any path resolves to `<repo>/data/` or the configured `BOTTOM_POT_DATA_DIR` / default OS data directory without explicit non-test operational authorization.
   - `SafetyError` must propagate uncaught across `src/` (`docs/exception-audit.md`, verified by `scripts/check_db_safety.py`).
3. **Cron & Admin Authentication (`src/api/main.py`, `src/api/auth.py`):**
   - `/api/cron/monitor` checks `Authorization: Bearer <CRON_SECRET>` using `secrets.compare_digest` (`503` if `CRON_SECRET` is unset, `401` on mismatch).
   - `POST /api/admin/login`, `POST /api/admin/logout`, and `GET /api/admin/verify` use an HMAC-SHA256 signed `HttpOnly` cookie (`ADMIN_COOKIE_NAME`, default `bp_admin_session`, configurable `ADMIN_COOKIE_SAMESITE`, 7-day TTL) and return `503` if `ADMIN_PASSWORD` is unset.
   - Anonymous `/search` callers receive strictly allowlisted job and completion fields (`src/api/allowlist.py`); admin telemetry, provider outcomes, and scraping provenance require a verified admin session cookie.
4. **HTTP Hardening, CORS, Rate Limits & CSV Neutralization (`src/api/main.py`, `src/storage/subscriptions.py`):**
   - `CORSMiddleware` enforces `CORS_ALLOW_ORIGINS`.
   - Security middleware sets `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, and `Permissions-Policy`.
   - `slowapi` enforces per-IP limits (`RATE_LIMIT_SEARCH`, `RATE_LIMIT_SUBSCRIBE`, `RATE_LIMIT_ELIGIBILITY`, `RATE_LIMIT_ADMIN_LOGIN`), reading forwarded IP headers when `TRUST_PROXY_HEADERS=true` or `VERCEL` is set.
   - `POST /subscribe` neutralizes spreadsheet formula prefixes (`src/storage/subscriptions.py`).
5. **Secret Scanning & Leak Handling:**
   - Every PR runs `python scripts/check_secrets.py` alongside repository CI secret scanning.
   - **If a real secret is ever committed:** revoke and rotate the credential immediately at the provider dashboard; never rewrite git history.

## Reporting a Vulnerability

Please do **not** open a public issue with live exploit details or exposed credentials.

- Report vulnerabilities privately to the repository owner via GitHub Security Advisories (`Security` -> `Report a vulnerability` on `richmondsogo/bottom-pot`) or private direct contact.
- Include reproduction steps, affected endpoint or module, and potential impact. Please allow reasonable time for investigation and rotation/remediation before public disclosure.
