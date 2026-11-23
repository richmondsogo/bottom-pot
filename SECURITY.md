# Security Policy

## Supported Scope & Data Classification

Bottom Pot is a local-first job discovery application combining a FastAPI backend (`src/`) and a React/Vite frontend (`frontend/`).

- **Operational data:** `cache.sqlite` (and its `-wal`/`-shm` sidecars) and `subscriptions.csv` store local search caches, board polling state, and email subscriptions. They live outside the repo by default (`BOTTOM_POT_DATA_DIR`, `ADR 0032`) or in legacy `<repo>/data/` and are never committed.
- **Public client config vs. server secrets:**
  - `VITE_LOGO_DEV_TOKEN` (`pk_*`) and `VITE_REPORT_PROBLEM_URL` are embedded into frontend builds and treated as public configuration. Restrict `pk_*` tokens by domain in the Logo.dev dashboard.
  - `SERPER_API_KEY`, `ADMIN_PASSWORD`, `ADMIN_SESSION_SECRET`, and any `sk_*` token are server secrets. They belong **only** in local gitignored `.env` files or runtime environment variables.

## Security Boundaries Enforced in Code

1. **SSRF & Outbound HTTP (`src/safety/url_safety.py`, `src/providers/http.py`):**
   - Only `https://` targets resolving exclusively to globally routable public IPv4/IPv6 addresses are permitted. Private, loopback, link-local, carrier-grade NAT, multicast, and reserved ranges are rejected before connection and on every HTTP redirect hop (`follow_redirects=False`).
   - Streaming downloads enforce fail-closed byte limits (`MAX_RESPONSE_BYTES`).
2. **Operational Database Protection (`src/safety/db_safety.py`, `ADR 0030`, `ADR 0032`):**
   - Test suites, Playwright E2E runners, and read-only utilities fail closed (`SafetyError` / `UnsafeDatabasePathError`) if any path resolves to `<repo>/data/` or the configured `BOTTOM_POT_DATA_DIR` / default OS data directory without explicit non-test operational authorization.
   - `SafetyError` must propagate uncaught across `src/` (`docs/exception-audit.md`, verified by `scripts/check_db_safety.py`).
3. **Anonymous SSE Redaction (`src/api/allowlist.py`):**
   - Anonymous `/search` callers receive strictly allowlisted job and completion fields; admin telemetry, provider outcomes, and scraping provenance stay admin-only (`POST /api/admin/login`).
4. **Secret Scanning & Leak Handling:**
   - Every PR runs `python scripts/check_secrets.py` alongside repository CI secret scanning.
   - **If a real secret is ever committed:** revoke and rotate the credential immediately at the provider dashboard; never rewrite git history.

## Reporting a Vulnerability

Please do **not** open a public issue with live exploit details or exposed credentials.

- Report vulnerabilities privately to the repository owner via GitHub Security Advisories (`Security` -> `Report a vulnerability` on `richmondsogo/bottom-pot`) or private direct contact.
- Include reproduction steps, affected endpoint or module, and potential impact. Please allow reasonable time for investigation and rotation/remediation before public disclosure.
