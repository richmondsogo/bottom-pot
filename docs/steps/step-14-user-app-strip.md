# Step 14: User App Strip & Public Stream Redaction

**Step Branch**: `step/14-user-app-strip`
**Primary Branch**: `main`
**Baseline**: main at 5ccc67a after step 12 (admin split), PR #16
**Status**: IN PROGRESS
**PR URL**: TBD
**First Commit SHA**: `131a00d`
**Last Commit SHA**: `3756b42`
**Merge Commit SHA**: TBD (recorded in Step 15 doc)

---

## 1. Goal

Strip all operational telemetry, pipeline provenance, scraping metadata, and internal debug disclosures from the public user experience (`/` and `/app`) and the unauthenticated `/search` SSE stream. Present a clean, editorial, calm job discovery workspace for users while preserving 100% of the operational and debugging capabilities for authenticated administrators on `/admin`.

---

## 2. Scope

- **Frontend User-Mode Gating**:
  - Thread `mode: 'user' | 'admin'` prop cleanly to `Header`, `SearchSummaryBar`, `DetailSheet`, `SearchForm`, `States`, and `Workspace` (no new global state).
  - Header: Hide Command Palette trigger button (`⌘K`) in user mode.
  - Workspace: Do not mount `TelemetryDeck`, `StatusStrip`, or `CommandPalette` in user mode. Replace loading `TelemetryDeck` with calm `LoadingState`.
  - SearchSummaryBar: Replace platform counts and timing with calm summary copy (`"{n} positions for {query}"` / `"Showing {x} of {n} positions for {query}"`). Unmount details popover and Telemetry Deck button.
  - DetailSheet: Omit the 5-Stage Verification Pipeline `<Steps>` block in user mode. In the footer, omit `data_source` and display only the posted date.
  - SearchForm: Hide the 3-column "How Bottom Pot works" block and platform list under the form on `/app` in user mode.
  - States: Calm loading state copy ("Searching company career pages", "Looking for open roles that match your search.") and empty state copy ("No open positions matched your search. Try a broader keyword or a wider date range."). Handle `incomplete: true` on zero results with "Search is busy right now. Please try again a little later."
  - ShortcutsModal: Hide Command Palette shortcut in user mode; ensure `?` shortcut modal remains accessible.
  - Keyboard: `Cmd+K` / `Ctrl+K` does nothing in user mode and does not call `preventDefault`.
  - Exports: Split `export.ts` into pure builders (`buildCsv`, `buildJson`). In user mode, CSV keeps 9 public columns (omitting internal source/evidence/extraction fields, strictly preserving `Apply URL`); JSON drops internal keys. Admin exports remain byte-identical.
- **Backend Allowlist Serialization**:
  - Classify all model fields of `JobListing`, `ResultsBatch`, and `DoneEvent` into explicit allowlists (`src/api/allowlist.py`).
  - Public anonymous SSE stream yields only allowlisted fields using Pydantic include sets.
  - For anonymous callers, `DoneEvent` adds `incomplete: true` when `budget_exhausted` is true, else false; operational counters (Serper calls, queries, cache hits, pages fetched, provider lists, timing) are stripped.
  - Error events sanitize message bodies for anonymous callers by error code (`TIMEOUT` -> `"The search took too long. Please try again."`, other codes -> `"Something went wrong while searching. Please try again."`), preserving code and stripping internal exception text and URLs.
  - Authenticated admin requests (`bp_admin_session` verified via existing session cookie logic) receive the full, unredacted stream byte-identical to previous behavior (excluding `incomplete`).
  - Cache invariance: In-memory LRU cache and SQLite persistent cache retain full, unredacted model instances. Redaction occurs strictly at serialization time.
  - Resilience: Missing, tampered, or expired cookies are treated gracefully as anonymous (HTTP 200 stream), never an error. Validation 422 behavior remains unchanged.

---

## 3. Out of Scope

- Changes to `/admin` rendering or behavior (aside from the header badge and logout already added in Step 12).
- Changes to scraping pipelines, ATS clients, or parsing logic.
- New dependencies (npm or pip).
- Visual redesign of hero, header/footer branding, or logos (deferred to subsequent steps).
- Changes to Nigerian-sites toggle or deep-scrape toggle in SearchForm.
- Platform slug under company name (retained as design system standard).

---

## 4. Known Limits & Edge Cases

- **Cross-Session LocalStorage Persistence**: An anonymous user who saves results to `localStorage` (shortlist) and subsequently logs in as an admin in the same browser session will see jobs lacking debug fields (since they were saved from the stripped anonymous stream). Full debug fields are only populated for searches performed while authenticated as admin.
- **Marketing DOM IDs Diff**: Marketing DOM differs from `ext-1` baseline only by generated React `useId` / Base UI IDs (`gp-r6` vs `gp-r7`) because `CommandPalette` no longer mounts in user mode on the marketing page.
- **Keyboard Navigation Fix**: Added modifier guard (`if (e.metaKey || e.ctrlKey || e.altKey) return;`) to table navigation shortcuts in `App.tsx`. Prevents `Ctrl/Cmd+K` from firing single-key row navigation `k` alongside opening the palette in admin mode. In user mode, `Ctrl/Cmd+K` does nothing.
- **'Search is busy right now' Message**: When an anonymous search returns zero results and `incomplete: true` (e.g. daily budget exhausted), the UI renders `"Search is busy right now. Please try again a little later."` instead of the standard empty search copy.
- **Verify Route**: The backend `/api/admin/verify` endpoint returns 200/401 for session checks; session verification on SSE streams falls back to anonymous on invalid/missing cookies.

---

## 5. Verification & Test Suite

- **Frontend Linter (Oxlint)**: 3 baseline warnings, 0 errors.
- **Frontend Unit Tests (Vitest)**: 57 passed across 8 test suites (including byte-equality test of admin export vs old logic).
- **Frontend Production Build**: `tsc -b && vite build` clean in ~2.5s.
- **Backend Tests (Pytest)**: 329 passed across entire test suite.
- **End-to-End Tests (Playwright)**: 29 passed (`--workers=1`) in ~1.5m.
- **Visual & Structural Parity**:
  - Marketing parity: 5/5 viewports PNG byte MATCH vs `ext-1`.
  - Admin parity: 38/38 DOM dumps MATCH vs `ext-1` (0 mismatches).
  - User stability self-diff: 76/76 files match (zero jitter).
  - DOM absence strings: 18/18 checks produced 0 occurrences across all 38 user HTML dumps.
