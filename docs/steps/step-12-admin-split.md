# Step 12: Admin Split & Backend Security Gate

> [!CAUTION]
> **DO NOT DEPLOY STEP 12 TO PRODUCTION ALONE.**
> **Plain words statement**: After completing Step 12, all telemetry, debug fields, and scraper traces remain **100% publicly visible** to anyone visiting `/app` or calling the `GET /search` API. Step 12 builds the authentication gate, cookie mechanics, and the `/admin` login surface, but it **does not strip any data from public streams**. Step 12 does not protect any data on its own. **Step 12 and Step 14 must ship and deploy together** before internal scraper telemetry is truly hidden from the public.

**Step Branch**: `step/12-admin-split`  
**Primary Branch**: `main`  
**Baseline**: main at 830ff72 after step 13 (search routing), PR #15  
**Status**: IN PROGRESS (Commit 1: Backend Auth)  
**PR URL**: TBD  
**First Commit SHA**: TBD  
**Last Commit SHA**: TBD  

---

## 1. Goal

Split Bottom Pot into a dedicated, password-protected `/admin` workspace and a user-facing `/app` workspace.
Enforce authentication on the backend via an `ADMIN_PASSWORD` environment variable, a signed 7-day `httpOnly` cookie session, and rate-limited auth endpoints.
Keep the user workspace behavior identical to today in this step, establishing the security and routing foundation before UI and data stripping ship in Step 14.

---

## 2. Not in This Step

The following items are explicitly **OUT OF SCOPE** for Step 12:
- **Stripping the user UI**: TelemetryDeck, StatusStrip, the 5-stage pipeline in DetailSheet, and CommandPalette remain in the user workspace for this step; stripping them is exclusively Step 14.
- **Stripping SSE debug data**: The `GET /search` stream continues to send full telemetry and debug metadata to all callers in this step; data redaction for non-admin callers occurs in Step 14.
- **Hero redesign / landing modifications**: No changes to GlyphPortal, manifesto, or marketing copy.
- **Result-mix fixes / scraper adjustments**: No modifications to Nigerian scrapers vs. ATS ratio, progressive stopper, or parsing logic.
- **Export modifications**: JSON and CSV client-side exports remain untouched.
- **Logo / brand changes**: No alterations to the "BP" brandmark, typography, or favicon.
- **Search depth / credit knobs**: No per-user credit controls or dynamic Serper depth adjustments.
- **User accounts / multi-tenant authentication**: No user registration, user databases, or OAuth; authentication is strictly a single shared administrator password for developer access.

---

## 3. What Step 11 Already Built vs. What Step 12 Adds

### What Already Exists (Do Not Re-Implement)
Step 11 (`docs/steps/step-11-decoupled-pages-and-telemetry.md`) already completed the foundation for developer telemetry and page separation:
1. **Decoupled routing primitives**: Native View Transitions between marketing (`/`) and workspace (`/search` & `/app`) in `App.tsx:85-150`.
2. **Complete Prompt-Kit Telemetry Deck**: `frontend/src/components/TelemetryDeck.tsx` (using adapted `@prompt-kit/tool`, `@prompt-kit/thinking-bar`, `@prompt-kit/text-shimmer`, and `@prompt-kit/system-message`).
3. **Telemetry trigger**: The `Cpu` disclosure button in `SearchSummaryBar.tsx`.
4. **DetailSheet 5-stage pipeline trace**: Built on `@prompt-kit/steps` and `@prompt-kit/source`.
5. **Vite HTML proxy bypass**: Proxy bypass for `text/html` requests on `/search` in `vite.config.ts`.

### What Step 12 Adds
1. **Backend authentication subsystem**: `src/api/auth.py` for HMAC-SHA256 session tokens and FastAPI dependencies.
2. **Backend endpoints**: `POST /api/admin/login` (rate-limited), `POST /api/admin/logout`, `GET /api/admin/verify`.
3. **Route architecture**: Registering `/admin` on FastAPI and Vite; routing `/admin` in `App.tsx`.
4. **Frontend login surface**: Square-styled `<AdminLogin />` card that preserves query parameters.
5. **Workspace variant split**: Refactoring the search workspace in `App.tsx` into a shared component with a `mode="admin" | "user"` prop.

---

## 4. Architecture & Code-Sharing Analysis: Approach A vs. Approach B

`frontend/src/App.tsx` is currently **1,191 lines of code**. It encapsulates the router, URL search parameter synchronization, active filter state, saved jobs management, sorting logic, EventSource/SSE streaming consumption, and component orchestration.

### Approach A: Duplicate `App.tsx` into a Separate `AdminApp.tsx`
- **Mechanism**: Copy the 1,191 lines of `App.tsx` into a new `AdminApp.tsx`. The main router delegates `/admin` to `AdminApp` and `/app` to `App`.
- **Code Duplication**: **~1,100+ lines duplicated immediately**. The complete EventSource SSE reader, result batch state updates, deduplication state, filter reducers, and table layout would exist twice.
- **Tradeoffs**:
  - *Pros*: Total visual isolation. When stripping user UI in Step 14, `App.tsx` can be ruthlessly edited without fear of breaking the admin console.
  - *Cons*: Severe technical debt and logic drift. Any bugfix or performance update to search streaming, error handling, date sorting, or deduplication must be manually copied between two 1,100-line files. Violates DRY for core search functionality.

### Approach B: Shared Search Workspace with Mode / Variant Prop (Recommended)
- **Mechanism**: Extract the core search workspace from `App.tsx` into a reusable component (e.g. `<Workspace mode="admin" | "user" />` or provide an `AdminContext`). `App.tsx` acts as the clean top-level shell and router.
- **Code Duplication**: **0 lines duplicated**.
- **Tradeoffs**:
  - *Pros*: Single source of truth for the SSE streaming pipeline, search state, sorting, and filtering. The `mode="admin"` prop gates whether developer-only features (such as `TelemetryDeck`, `StatusStrip`, mock controls, and raw debug payloads) are active. When Step 14 executes, the user branch of `<Workspace mode="user" />` simply renders the calm, stripped layout without touching search engine primitives.
  - *Cons*: Requires clean prop/context plumbing so that conditional rendering does not clutter layout code.

### Recommendation
**Approach B**. Duplicating 1,100+ lines of async SSE stream processing, URL state synchronization, and reactive table filters is brittle and error-prone. Extracting the core workspace logic ensures that fixes to search correctness automatically benefit both admin and user surfaces.

---

## 5. Route Architecture & FastAPI Integration

### Target Routes
- `/` = Marketing Landing Page (Hero, Value Proposition, Search Starters)
- `/app` = User Search Workspace (`/search` preserved as an alias/redirect)
- `/admin` = Protected Admin / Developer Workspace

### Technical Code Evaluation: Is This a Good Idea?
**YES, this is significantly better than the current route setup.**
- *Current conflict*: FastAPI defines `GET /search` as an SSE streaming endpoint expecting query parameter `q`. In local development, `frontend/vite.config.ts:18-22` had to implement an awkward proxy `bypass` checking `req.headers.accept.includes("text/html")` to avoid returning 422 errors when users refreshed `/search`.
- *Fix*: Standardizing the user app route at `/app` cleanly decouples the browser HTML page from the API data endpoint `GET /search`.
- *FastAPI requirement*: FastAPI's static server (`src/api/main.py:151-158`) already has an explicit `@app.get("/app")` returning `index.html`. For `/admin`, FastAPI must also register `@app.get("/admin")` to return `index.html` on direct browser refresh.

---

## 6. Backend Authentication Design & Rate Limiting

### Configuration (`src/config.py` & `.env.example`)
1. **`ADMIN_PASSWORD`**:
   - In `Settings`: `admin_password: str = ""`.
   - **Unset handling**: If `ADMIN_PASSWORD` is empty/unset, the backend starts normally and the user app functions completely. Any call to `POST /api/admin/login` immediately returns **HTTP 503 Service Unavailable** with `{"detail": "Admin access disabled: ADMIN_PASSWORD is not configured"}`. A startup warning is logged: `logger.warning("ADMIN_PASSWORD is not set. Admin login is disabled.")`. Zero default passwords exist.
2. **`ADMIN_SESSION_SECRET`**:
   - In `Settings`: `admin_session_secret: str = ""`.
   - **Unset handling**: If `ADMIN_SESSION_SECRET` is empty/unset, generate a cryptographically secure random 32-byte secret at startup via `secrets.token_urlsafe(32)`. Log a prominent warning: `logger.warning("ADMIN_SESSION_SECRET is unset. Generated ephemeral secret; admin sessions will reset on server restart.")`.
   - > [!IMPORTANT]
     > **Multi-worker note**: If more than one uvicorn worker is used (`--workers N`), `ADMIN_SESSION_SECRET` **must** be set explicitly in `.env`, or each worker process will generate a different ephemeral secret, causing session rejection across worker processes.
3. **`RATE_LIMIT_ADMIN_LOGIN`**:
   - In `Settings`: `rate_limit_admin_login: str = "5/minute"`.
   - For Playwright e2e runs, this can be set to `"1000/minute"` via environment variable to prevent rate limit trip during automated browser suites.
4. **Cookie Specifications**:
   - Name: `bp_admin_session`
   - Lifetime: **7 days** (`max_age = 604800` seconds)
   - Flags: `HttpOnly=True`, `SameSite="Lax"`, `Path="/"`.
   - `Secure` flag: Dynamically applied if `request.url.scheme == "https"` or `request.headers.get("x-forwarded-proto") == "https"`.

### Rate Limiting on Login
- The login endpoint `POST /api/admin/login` is protected by SlowAPI using the existing Limiter:
  ```python
  @app.post("/api/admin/login")
  @limiter.limit(settings.rate_limit_admin_login)
  async def admin_login(request: Request, body: AdminLoginRequest): ...
  ```
  Exceeding the limit per minute per IP returns HTTP 429 (`RateLimitExceeded`).

### Endpoints (`src/api/main.py`)
1. `POST /api/admin/login`:
   - Validates `ADMIN_PASSWORD` using constant-time comparison `secrets.compare_digest`.
   - If invalid: returns HTTP 401 Unauthorized.
   - If valid: sets signed cookie and returns `{"authenticated": true}`.
2. `POST /api/admin/logout`:
   - Clears `bp_admin_session` cookie via `response.delete_cookie()`.
3. `GET /api/admin/verify`:
   - Verifies the HMAC-SHA256 signature and timestamp of the cookie.
   - If valid: returns `{"authenticated": true}`.
   - If invalid/missing: returns HTTP 401 Unauthorized.

---

## 7. Frontend `<AdminLogin />` & Design System Compliance (ADR 0021)

### Component Architecture
- New component: `frontend/src/components/AdminLogin.tsx`.
- Gated inside `App.tsx`: When `viewMode === 'admin'`, the app first verifies authentication via `GET /api/admin/verify`.
- If unauthenticated, render `<AdminLogin onLoginSuccess={...} />`.
- **Query Parameter Preservation**: If a user enters `http://localhost:5173/admin?q=python&loc=Lagos`, the login screen preserves `?q=python&loc=Lagos` in state and browser history. Upon successful login, the admin workspace mounts immediately with `keywords="python"` and `location="Lagos"`.

### Strict Green Budget Compliance (ADR 0021)
- **ADR 0021 Rule**: Forest green (`#1A382B` / `--accent`) is strictly budgeted for:
  1. The primary search CTA button ("Search ATS platforms").
  2. Selected platform chip checkmarks.
  3. Active Remote marker dot.
  4. Table row hover accent bar.
  5. Square keyboard focus rings.
- **Login Button Decision**: The login submit button **must NOT use green accent**.
- **Reused Component**: `<Button>` from `frontend/src/components/ui/button.tsx`.
- **Styling**: Reuses `<Button>` with the **neutral/ink** high-contrast solid button style:
  ```tsx
  <Button
    type="submit"
    disabled={isLoading}
    className="h-10 w-full rounded-none border border-transparent bg-[var(--ink)] text-[var(--bg)] hover:bg-[var(--ink)]/90 font-medium text-sm transition-colors cursor-pointer select-none"
  >
    {isLoading ? 'Verifying…' : 'Access Admin Workspace'}
  </Button>
  ```
  This passes the automated Playwright `green budget audit` without consuming budgeted green elements.

---

## 8. Commit Order Inside This Step

To maintain an atomic, testable paper trail, Step 12 is structured in three strictly ordered commits:
1. **Commit (1) — Backend Auth & Security Gate**:
   - `src/config.py`: Configuration settings (`admin_password`, `admin_session_secret`, `admin_cookie_name`, `admin_cookie_max_age_seconds`, `rate_limit_admin_login`).
   - `src/api/auth.py`: HMAC-SHA256 cookie signing, verification, and session token utilities.
   - `src/api/main.py`: `POST /api/admin/login`, `POST /api/admin/logout`, `GET /api/admin/verify`, and `@app.get("/admin")`.
   - `.env.example`: Blank commented variables.
   - `tests/conftest.py`: SlowAPI limiter reset fixture and test credential defaults.
   - `tests/test_api_endpoints.py`: Backend unit tests covering login, 503 unset handling, rate limiting (429), tampered cookies, verification, and logout.
   - *Constraint*: No frontend files touched in Commit 1.
2. **Commit (2) — Shared Workspace Refactoring**:
   - Pure structural refactor of `frontend/src/App.tsx`.
   - Extract search workspace into a component/sub-render with `mode: 'admin' | 'user'`.
   - **Zero behavior change** and existing tests untouched.
3. **Commit (3) — AdminLogin Component & Route Wiring**:
   - `frontend/src/lib/adminAuth.ts`: API client functions.
   - `frontend/src/components/AdminLogin.tsx`: Neutral-styled square login form.
   - `frontend/src/App.tsx` & `vite.config.ts`: `/admin` routing, query parameter preservation, and Header indicator.
   - `tests/e2e/admin-auth.spec.js`: E2E verification of login, query preservation, and logout.

---

## 9. Test Impacts & Secrets Scan Analysis

### Secrets Scan Check
`scripts/verify.ps1` runs a file-level tracked secrets check (`git ls-files` matching `*.pem`, `*.key`, `.env`, `*.secret`, `credentials.json`, `.agents/mcp_config.json`). It does **not** perform content-regex scanning on `.py` or `.js` files. In addition, no `git-secrets` hooks are active. Therefore, placeholder test secrets in `conftest.py` (`"test-admin-password"`) and `playwright.config.js` (`'test-admin-password'`) **will not trip** the repository verification suite.

### Test Injections
1. **Pytest (`tests/conftest.py`)**:
   - Provide default test credentials:
     ```python
     os.environ.setdefault("ADMIN_PASSWORD", "test-admin-password")
     os.environ.setdefault("ADMIN_SESSION_SECRET", "test-admin-session-secret-at-least-32-chars-long")
     ```
   - Provide SlowAPI limiter reset fixture (`autouse=True`) to ensure in-memory rate limit counts do not bleed between unit tests:
     ```python
     @pytest.fixture(autouse=True)
     def reset_rate_limiter():
         from src.api.main import limiter
         limiter.reset()
         yield
         limiter.reset()
     ```
2. **Playwright (`playwright.config.js`)**:
   - Injected into `webServer.env`:
     ```javascript
     ADMIN_PASSWORD: process.env.ADMIN_PASSWORD || 'test-admin-password',
     ADMIN_SESSION_SECRET: process.env.ADMIN_SESSION_SECRET || 'test-admin-session-secret-at-least-32-chars-long',
     RATE_LIMIT_ADMIN_LOGIN: '1000/minute',
     ```

### New Tests to Add in Commit 1
In `tests/test_api_endpoints.py`:
- `test_admin_login_when_password_unset_returns_503(monkeypatch)`: Monkeypatches `settings.admin_password = ""` and asserts HTTP 503 with descriptive error.
- `test_admin_login_wrong_password_returns_401()`: Asserts 401 on incorrect password.
- `test_admin_login_correct_password_sets_signed_cookie()`: Asserts 200, checks `Set-Cookie` header attributes (`HttpOnly`, `Path=/`, `SameSite=lax`, `Max-Age=604800`).
- `test_admin_login_rate_limiting()`: Sends 6 consecutive login attempts; asserts the 6th returns HTTP 429.
- `test_admin_verify_without_cookie_returns_401()`: Asserts 401.
- `test_admin_verify_with_tampered_cookie_returns_401()`: Alters signature payload; asserts 401.
- `test_admin_verify_with_valid_cookie_returns_200()`: Asserts `{"authenticated": true}`.
- `test_admin_logout_clears_cookie()`: Asserts cookie is expired.
- `test_admin_page_serves_html()`: Asserts `GET /admin` serves `index.html`.

---

## 10. Verification Commands (Windows PowerShell)

All commands are formatted specifically for Windows PowerShell using `curl.exe` to avoid PowerShell's `Invoke-WebRequest` alias.

The sequence below properly accounts for the 5-attempt/minute rate limit window:
- Step A does not hit `/api/admin/login` (0 login attempts used).
- Step B uses login attempt 1 (failed).
- Step C uses login attempt 2 (successful login, saves cookie).
- Step D verifies the saved cookie (does not hit login).
- Step E tests the rate limiter by exhausting remaining attempts (attempts 3, 4, 5 return 401; attempt 6 returns 429).
- Step F tests logout.

```powershell
# Step A: Verify unauthenticated access fails (Expect HTTP 401)
curl.exe -i -X GET http://127.0.0.1:8000/api/admin/verify

# Step B: Attempt login with invalid password (Attempt 1 of 5; Expect HTTP 401)
curl.exe -i -X POST http://127.0.0.1:8000/api/admin/login `
  -H "Content-Type: application/json" `
  -d '{"password":"wrong-password"}'

# Step C: Valid login and session receipt (Attempt 2 of 5; Expect HTTP 200 with Set-Cookie)
curl.exe -i -c cookie.txt -X POST http://127.0.0.1:8000/api/admin/login `
  -H "Content-Type: application/json" `
  -d '{"password":"test-admin-password"}'

# Step D: Verification with signed cookie (Expect HTTP 200 with {"authenticated":true})
curl.exe -i -b cookie.txt -X GET http://127.0.0.1:8000/api/admin/verify

# Step E: Rate limit trip in PowerShell
# Attempts 3, 4, 5 return 401; Attempt 6 exceeds limit and returns 429
1..4 | ForEach-Object {
    $code = curl.exe -s -o /dev/null -w "%{http_code}" -X POST http://127.0.0.1:8000/api/admin/login `
      -H "Content-Type: application/json" `
      -d '{"password":"wrong"}'
    Write-Host "Call $_ status: $code"
}
# Output:
# Call 1 status: 401  (Attempt 3)
# Call 2 status: 401  (Attempt 4)
# Call 3 status: 401  (Attempt 5)
# Call 4 status: 429  (Attempt 6: Rate limit tripped)

# Step F: Logout and subsequent rejection (Expect HTTP 401 after logout)
curl.exe -i -b cookie.txt -c cookie.txt -X POST http://127.0.0.1:8000/api/admin/logout
curl.exe -i -b cookie.txt -X GET http://127.0.0.1:8000/api/admin/verify

# Cleanup test cookie file
Remove-Item -Path cookie.txt -ErrorAction SilentlyContinue
```

---

## 11. Known Limits
- Logout clears only the browser cookie. Tokens are stateless and stay valid until expiry (7 days). To revoke all sessions, change `ADMIN_SESSION_SECRET`.
- Behind a reverse proxy, the rate limiters key on the client IP as uvicorn sees it. Deployment must use `uvicorn --proxy-headers` with `--forwarded-allow-ips` set to the proxy, or all users share one bucket (login limit and the 20/hour search limit).

---

## 12. Commit 2: Workspace Extraction
- **Goal**: Extract the workspace JSX into a presentational `frontend/src/components/Workspace.tsx` driven by props (235 lines removed, 75 added in App.tsx).
- **Rule**: All hooks, refs, effects and handlers remain in `App.tsx`; `Workspace.tsx` contains 0 hooks and receives grouped props (`search`, `filters`, `results`, `shell`).
- **Verbatim Move**: The entire workspace render tree moved character-for-character with identical ordering and props aliases.
- **Baseline Facts**: 165 mock rows rendered initially, scroll restored at 400px after returning from overview, in-flight streams survive view switches with 0 errors, and `?` opens shortcuts modal on marketing view by design.
- **Proof Methods**: 20 core states at 5 viewports plus 18 extended states at 2 viewports (38 total) pixel-identical before vs. after; 38 DOM dumps character-identical under bundle hash normalization; Vitest (40/40), Oxlint (3 baseline warnings, 0 errors), and Playwright (15/15) all green.

---

## 13. Commit 3: Admin Login and Mode Prop
- **Added**: Routes (`/admin`), auth state machine (`checking` | `anonymous` | `authenticated`), single verify effect keyed on `[isAdminRoute]`, auto-search and URL-sync effect gating via `autoSearchDecidedRef`, Header `ADMIN` badge and `Log out` in admin mode only, `AdminLogin.tsx` (neutral ink, zero green), `adminAuth.ts` API client, Vite `/api/admin` proxy, and Playwright `webServer.env` credentials.
- **Verified Facts**: All 38 user-mode visual states (PNG) and DOM snapshots are 100% identical to `ext-1` baseline; `verify_session_token` checks HMAC signature against `ADMIN_SESSION_SECRET` without checking `ADMIN_PASSWORD` (cookies remain valid up to 7 days if password is unset unless the secret rotates); Vite serves `/admin` with 200 OK without special bypass.
- **Known Limits**: The public `/search` SSE stream still carries all telemetry, so `/admin` protects nothing until step 14; after step 14 the logout-then-login in-memory state note must be revisited because admin-only data will exist; `autoSearchDecidedRef` resets on route change, but since `initialUrlState` is mount-only, navigating from `/app` to `/admin?q=...` without a reload will not re-parse new query parameters into state.
- **Warning**: Do NOT deploy step 12 alone; without step 14's backend stream sanitization, administrative telemetry remains publicly accessible.



