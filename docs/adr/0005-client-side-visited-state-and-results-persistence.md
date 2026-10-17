# ADR 0005: Client-Side Visited State and Results Persistence

## Status
Accepted

## Context
Job seekers often review dozens of listings in a session. Without clear feedback on which postings have already been inspected or opened, users repeatedly re-open postings they have already seen. Additionally, because Serper search queries consume finite API budget, users who refresh the page or return to the application should not lose recent search results or be forced to execute expensive live queries.

## Decision

1. **Visited Postings Tracking**:
   - We introduce a client-side visited state manager in `frontend/src/lib/visited.ts`.
   - When a user opens a posting link or opens the job details panel, the posting's canonical URL (or ID) is recorded in `localStorage` under `bp.visited`.
   - In the results table and card views, visited postings have their titles visually dimmed (using `--ink-subtle`, 60% opacity), mimicking Daybreak's "read" pattern.
   - All `localStorage` interactions are encapsulated in a robust module protected with try/catch to guard against disabled storage or private browsing errors.

2. **Saved Results Persistence**:
   - Recent search results, metrics, and timestamps are preserved in `localStorage` under `bp.savedResults`.
   - A hard quota limit (~3 MB) is enforced before writing. If a search result payload exceeds this cap, persistence is skipped safely rather than triggering `QuotaExceededError`.
   - On initial page load with saved results present, the application opens directly to the results screen with a quiet status strip indicating when the search was executed (`"Saved 1d ago"`), with immediate one-click actions to "Run again" or "Clear".

## Consequences
- Significant reduction in user fatigue when navigating high-volume search results.
- Protection of Serper search credits by enabling users to re-examine previously fetched listings without re-querying.
- Resilient operation in restricted browser privacy environments.
