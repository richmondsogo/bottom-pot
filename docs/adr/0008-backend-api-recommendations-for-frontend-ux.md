# 8. Backend API Recommendations for Frontend UX

Date: 2026-10-17

## Status

Proposed (Recommendations for future backend evolution)

## Context

During the frontend redesign of Bottom Pot, we adhered strictly to the hard constraint: **zero modifications to backend behavior, API contracts, search/query logic, or response shapes**. All UX improvements (consolidated status strip, square monogram tiles, 2-line title clamping, quiet square work-model tags, detail sheet, mock mode, client-side visited tracking) were accomplished using the existing `/search` Server-Sent Events (SSE) contract and data schemas.

While auditing frontend-backend integration, we identified several opportunities where modest, non-breaking backend API enhancements would substantially elevate the user experience.

## Recommendations

### 1. Granular Platform Progress Events on SSE Stream
- **Current State**: The `/search` endpoint streams `batch` events containing job objects, followed by a single `done` event. The frontend displays an honest elapsed timer and static platform counts because it cannot observe which specific ATS boards are currently being dorked or enriched.
- **Recommendation**: Emit lightweight `platform_status` SSE events (e.g., `{"event": "platform_status", "platform": "greenhouse", "status": "running" | "completed" | "rate_limited", "yield": 12}`).
- **UX Benefit**: Allows the frontend to show an authentic, non-gimmicky per-platform progress indicator showing exactly which ATS platforms have resolved.

### 2. Structured Salary Range Object
- **Current State**: `salary` is currently provided as a pre-formatted string (or `null`), such as `"$140,000 - $180,000"` or `"₦12,000,000"`.
- **Recommendation**: Provide an optional structured salary object alongside the formatted string:
  ```json
  "salary_structured": {
    "min": 140000,
    "max": 180000,
    "currency": "USD",
    "period": "annual"
  }
  ```
- **UX Benefit**: In accordance with the "Backend owns parsing" principle (ADR 0003), the frontend should never regex salary strings. A structured object enables client-side minimum salary filtering and currency-aware sorting without frontend parsing heuristics.

### 3. ISO-8601 Timestamps in Search Metadata
- **Current State**: Saved search cache durations and execution times are calculated client-side or serialized as raw seconds/strings.
- **Recommendation**: In the `done` event, include standard ISO-8601 timestamps:
  ```json
  "metadata": {
    "searched_at": "2026-10-17T21:40:00Z",
    "duration_ms": 1420,
    "serper_queries_count": 4,
    "cached_queries_count": 4,
    "budget_exhausted": false
  }
  ```
- **UX Benefit**: Enables consistent time-ago rendering (e.g., "Saved 2 hours ago") across timezones and daylight saving transitions.

### 4. Optional URL Query Parameters for Shareable Searches
- **Current State**: Active search filters and parameters reside in React state.
- **Recommendation**: Ensure the backend accepts clean query params matching frontend state (`/search?job_title=...&location=...&remote=true`), allowing search URLs to be deep-linked, shared, and bookmarked.

## Consequences

- These recommendations do NOT affect the current release or PR B.
- They serve as a clear roadmap for backend developers to collaborate with product design on subsequent iterations.
