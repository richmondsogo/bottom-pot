# Step 13: Search Routing & Content Negotiation

**Step Branch**: `step/13-search-routing-and-content-negotiation`  
**Primary Branch**: `main`  
**Status**: IN_PROGRESS  

---

## Objective

Resolve the routing collision between browser page navigation and the Server-Sent Events (SSE) search streaming endpoint on `/search`.
Implement HTTP content negotiation in FastAPI so `/search` requests preferring `text/html` return the SPA `index.html` without consuming rate limit quota or requiring `q`, while updating frontend URL state synchronization so the canonical workspace URL is `/app` while seamlessly supporting incoming legacy `/search` links.

---

## Scope

### Included
1. **Backend Content Negotiation (`src/api/main.py`)**:
   - Detect browser page navigations when `Accept` contains `text/html` and does NOT contain `text/event-stream` (if both are present, event stream wins).
   - Return `index.html` reusing `serve_app()`.
   - Ensure the page-serving path completely bypasses SlowAPI rate limiting on `/search`.
   - Ensure non-HTML requests missing `q` return 422 JSON as before, but page navigations missing `q` return HTML.
   - Add `Vary: Accept` header to `/search` responses.
2. **Frontend Canonical Workspace Routing (`frontend/src/lib/urlState.ts`, `frontend/src/App.tsx`)**:
   - Update `syncStateToUrl` and `buildShareableSearchUrl` so root `/` and `/search` rewrite to `/app`.
   - Ensure `App.tsx` continues to recognize `/search` as the workspace view mode so old shared links load the workspace and transition smoothly to `/app`.
   - Preserve the streaming fetch call to `/search?...` with `Accept: text/event-stream`.
3. **Automated Tests**:
   - Pytest tests in `tests/test_api_endpoints.py` verifying HTML responses with/without `q`, event stream responses with `q`, 422 responses for default `Accept` without `q`, and rate-limit isolation (25 HTML requests do not exhaust the SSE rate limit).
   - Vitest unit tests in `frontend/src/lib/__tests__/urlState.test.ts` verifying `/app` generation for `buildShareableSearchUrl`, `syncStateToUrl`, and legacy `/search` path replacement.
   - Single targeted test-harness fix in `tests/e2e/bottom-pot.spec.js` inside `runSearch` helper to clear storage on `/favicon.svg` before navigating to the app.

### Excluded
- No changes to admin split features or admin routes.
- No modifications to existing test assertions, selectors, or timeouts. The only existing test file edit is the authorized helper fix in `tests/e2e/bottom-pot.spec.js` (`runSearch`).

---

## Discoveries & Limitations

1. **Root Cause of Baseline Playwright Failures on `main`**:
   On `main`, 12 of 15 Playwright tests failed because the URL was rewritten to `/search` by `urlState.ts` and on reload Playwright's `mockSearch` intercepted `**/search?**` or FastAPI served the raw SSE endpoint instead of HTML. This bug was originally introduced in step 11 (commit `4896d60`), which rewrote the URL to `/search` without adding server-side content negotiation in FastAPI.

2. **Test-Harness Race Condition in `runSearch`**:
   In `tests/e2e/bottom-pot.spec.js`, `runSearch` previously loaded `/?view=app`, then cleared `localStorage`, then reloaded. On multi-iteration tests (such as the 5-viewport layout audit), iteration 1 left search results in `localStorage`. When iteration 2 loaded `/?view=app`, the app restored the saved results and `syncStateToUrl` immediately rewrote the browser URL to `/app?q=Backend+Engineer` before `localStorage.clear()` executed. The subsequent `page.reload()` reloaded the search query URL, triggering auto-search and hiding the search input. This was resolved by clearing `localStorage` on a non-booting same-origin asset (`/favicon.svg`) before navigating to `/?view=app`.

3. **Known Limits (Unchanged by this step)**:
   - `HEAD /search` returns HTTP 404 (`application/json`) with `Vary: Accept` because FastAPI does not auto-bind HEAD to GET routes and falls through to the static mount.
   - `GET /search/` (with trailing slash) returns HTTP 404 (`application/json`) without `Vary: Accept` because the catch-all static files mount takes precedence over route slash redirection.
   These limits are pre-existing and remain untouched in this step.

---

## Plan

1. **Step Creation & Baseline Verification**:
   - Branch `step/13-search-routing-and-content-negotiation` from `main`.
   - Confirm repo status, clean working tree, and grep verification of existing test URL expectations.
2. **Backend Implementation (`src/api/main.py`)**:
   - Move static file setup / `serve_app()` above middleware or define helper so it is accessible.
   - Implement HTTP middleware checking `request.url.path == "/search"` and `request.method == "GET"`.
   - If `text/html` in `Accept` and `text/event-stream` not in `Accept`: return `serve_app()` with `Vary: Accept`.
   - If not page navigation: call next, and append `Vary: Accept` on `/search`.
3. **Frontend Implementation (`urlState.ts` and `App.tsx`)**:
   - Update `targetPath` in `buildShareableSearchUrl` and `syncStateToUrl` to map `'/'` and `'/search'` to `'/app'`.
   - In `App.tsx`, maintain workspace path detection for `'/search'` and update programmatic view transitions to `'/app'`.
4. **Testing & Verification**:
   - Add new pytest tests in `tests/test_api_endpoints.py`.
   - Add new vitest tests in `frontend/src/lib/__tests__/urlState.test.ts`.
   - Execute verification suite (pytest, npm lint, vitest, npm build, playwright e2e).
