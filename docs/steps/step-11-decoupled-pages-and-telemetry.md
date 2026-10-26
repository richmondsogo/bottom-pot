# Step 11: Decoupled Pages Architecture & Prompt Kit Telemetry Deck

**Step Branch**: `step/11-decoupled-pages-and-telemetry`  
**Primary Branch**: `main` (branching from `step/10-landing-hero`)  
**Status**: COMPLETED  
**PR URL**: TBD  
**First Commit SHA**: `052c23d`  
**Last Commit SHA**: TBD  

---

## 1. Problem Statement & Scope

### A. Page Decoupling (Landing vs. Product)
Previously, `App.tsx` managed marketing landing and product search in a single view with the landing hero sitting immediately above search interactions.
- **Outcome**: The application is cleanly decoupled into two dedicated page surfaces:
  1. **Landing Page (`/`)**: Front door featuring the brand header, GlyphPortal hero, value proposition, sample results, and curated `PromptSuggestion` search starters. Submitting a query or clicking a prompt starter transitions to `/search` via native View Transitions (`startViewTransition`).
  2. **Product Workspace (`/search` & `/app`)**: Dedicated, high-density search workspace featuring the compact persistent `Header`, `SearchSummaryBar` with live Telemetry trigger, `Toolbar`, fixed semantic `ResultsTable` (ADR 0019) / `ResultsCards`, `TelemetryDeck`, `DetailSheet` (ADR 0006), and `ScrollButton`. No marketing hero clutter.
  3. **Seamless Navigation**: Clicking the `BP` logo or `← Overview` in the workspace header returns to `/` with state synchronization.

### B. Deep Telemetry via Prompt Kit
Bottom Pot collects rich scraper telemetry (`SourceTelemetryEvent` and `DoneMetrics`). This is now rendered with adapted Prompt Kit components honoring the **Square Design System** (`--radius: 0`):
1. **`@prompt-kit/tool`**: Telemetry cards for each ATS provider (`greenhouse`, `lever`, `ashby`, `workable`, `recruitee`, `smartrecruiters`, `teamtailor`, `jobberman`), detailing execution status, dork parameters, duration in ms, and parsed vs. cached results.
2. **`@prompt-kit/thinking-bar` + `@prompt-kit/text-shimmer`**: Live SSE streaming pulse bar with animated shimmer text and one-click stream cancellation.
3. **`@prompt-kit/system-message`**: Alert banners for daily Serper budget exhaustion (`budget_exhausted`) or operational notices.
4. **`@prompt-kit/steps`**: 5-stage progressive verification pipeline trace in `DetailSheet` (Discovery → Fetch → Extraction → Remote Policy → Normalization).
5. **`@prompt-kit/source`**: Hover citation cards for verified ATS requisition domains using Base UI PreviewCard with square geometry.
6. **`@prompt-kit/prompt-suggestion`**: Square prompt starter chips on the landing page and recent searches in the search form.
7. **`@prompt-kit/scroll-button`**: Quick return-to-top floating button for large result sets.

---

## 2. Implementation Record

### Part 1: Prompt Kit Components (`frontend/src/components/prompt-kit/`)
- `text-shimmer.tsx`: Adapted to Bottom Pot ink tokens and custom CSS `@keyframes shimmer`.
- `thinking-bar.tsx`: Fitted with live pulse dot, shimmer text, and stop stream action.
- `tool.tsx`: Re-architected for ATS query telemetry (`durationMs`, `resultCount`, `cached`, `input`, `output`).
- `steps.tsx`: Adapted to 1px hairline connector bar and DM Mono step indicators.
- `system-message.tsx`: Enforced strict `rounded-none!` and warm alert styling.
- `source.tsx`: Built with `HoverCard` preview for direct requisition domains.
- `prompt-suggestion.tsx`: Square button chips with highlight and keyboard accessibility.
- `scroll-button.tsx`: Standalone window scroll-to-top button with smooth transition.

### Part 2: Base UI Integration (`frontend/src/components/ui/`)
- `hover-card.tsx`: Built on `@base-ui/react/preview-card` with square geometry (`rounded-none!`) and support for `delay`/`closeDelay` on triggers.
- `collapsible.tsx`: Enhanced `CollapsibleTrigger` to support `asChild` rendering via Base UI's native `render` prop.

### Part 3: Telemetry Deck (`frontend/src/components/TelemetryDeck.tsx`)
- Collapsed quiet summary with `Cpu` telemetry trigger button in `SearchSummaryBar`.
- Interactive grid of provider `Tool` cards detailing dork parameters, latency, hit counts, and output payloads.
- High-level KPI grid: Engine Source, Pages Inspected, Execution Latency, and Cache Hit Efficiency.

### Part 4: Decoupled Router & URL Synchronization
- `App.tsx`: Native View Transition router handling `/` (Landing Page) and `/search` / `/app` (Product Workspace).
- `urlState.ts`: URL state serialization targeting `/search` with full query parameter persistence.
- `vite.config.ts`: Added proxy `bypass` for `text/html` requests to `/search` so Vite serves `index.html` for SPA navigation while preserving FastAPI SSE proxying for fetch calls.

---

## 3. Verification Evidence

1. **Static Analysis & Linting**:
   - `npm run lint` (`oxlint`): 0 errors across all 70 frontend files.
   - `npm run build` (`tsc -b && vite build`): Succeeded in 4.42s with zero TypeScript diagnostics.
2. **Unit Tests**:
   - Frontend (`vitest`): 4 test files, 33/33 tests passed.
   - Backend (`pytest`): 301/301 tests passed in 15.08s.
3. **Repository Verification Suite (`.\scripts\verify.ps1 -SkipE2E`)**:
   - 7 passed, 0 failed (Git, secrets check, CSS cascade lint, oxlint, vitest, tsc+vite, pytest).
4. **Browser Verification (Chrome DevTools MCP)**:
   - Navigated to `http://localhost:5173/`: Verified landing front door with GlyphPortal, Wordmark, and prompt suggestion chips.
   - Clicked prompt starter chip (`React engineer · Remote`): Verified view transition to `http://localhost:5173/search`.
   - Verified active streaming `ThinkingBar` with pulse dot and `Cancel stream` button.
   - Navigated to `http://localhost:5173/search?mock=1`: Verified product workspace with header, summary bar, and `Telemetry (8)` button.
   - Clicked `Telemetry (8)`: Verified Telemetry Deck expanded showing 4 KPIs and 8 ATS provider Tool cards (Greenhouse, Lever, Ashby, Workable, etc.).
   - Expanded Ashby Tool card: Verified dork parameters, mode, and response payload JSON.
   - Clicked job row: Verified `DetailSheet` opened with Prompt Kit `Steps` (5-Stage Verification Pipeline) and `Source` hover preview.
   - Clicked `← Overview`: Verified smooth transition back to `http://localhost:5173/`.

