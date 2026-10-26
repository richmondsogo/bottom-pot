# Step 11: Decoupled Pages Architecture & Prompt Kit Telemetry Deck

**Step Branch**: `step/11-decoupled-pages-and-telemetry`  
**Primary Branch**: `main` (branching from `step/10-landing-hero`)  
**Status**: IN_PLANNING  

---

## 1. Problem Statement & Scope

### A. Page Decoupling (Landing vs. Product)
Currently, `App.tsx` manages both marketing landing and product search in a single monolithic controller. While `viewMode` toggles between `'marketing'` and `'workspace'`, the landing hero sits directly above search interactions.
- **Goal**: Formally decouple the experience into two separate page surfaces with distinct URLs and purposes:
  1. **Landing Page (`/`)**: Pure editorial front door. Headline, Glyph Portal, brand story, and curated `prompt-suggestion` search starters. Submitting a query or clicking a pill routes directly to `/search`.
  2. **Product Workspace (`/search` & `/app`)**: Dedicated, dense search workbench. Compact persistent header, fixed semantic table (ADR 0019), DetailSheet (ADR 0006), and real-time Telemetry Deck. No hero clutter.

### B. Deep Telemetry via Prompt Kit
Bottom Pot collects rich scraper telemetry (`SourceTelemetryEvent` and `DoneMetrics`: per-host execution time, results parsed, dropped duplicates, Serper calls, cache hits, circuit breakers). This data is currently presented in a plain text disclosure.
- **Goal**: Integrate Prompt Kit components adapted to the **Square Design System** (`--radius: 0`):
  1. **`@prompt-kit/tool`**: Telemetry card for each ATS provider (`greenhouse`, `lever`, `ashby`, etc.) detailing execution status, dork used, duration in ms, and results count.
  2. **`@prompt-kit/thinking-bar` + `@prompt-kit/text-shimmer`**: Active SSE streaming bar with animated shimmer text and live stop button.
  3. **`@prompt-kit/system-message`**: Alert strip for daily budget limits (`budget_exhausted`) or tripped circuit breakers.
  4. **`@prompt-kit/steps`**: 5-stage progressive extraction trace in the `DetailSheet` (Discovery → Serper → ATS → Normalization → Validation).
  5. **`@prompt-kit/source`**: Hover citation cards for verified ATS requisition domains.
  6. **`@prompt-kit/prompt-suggestion`**: Square prompt starter pills on the landing page.
  7. **`@prompt-kit/scroll-button`**: Quick return-to-top floating button for large result sets.

---

## 2. Architecture & Implementation Plan

### Part 1: Component Installation & Square Geometry Adaptation
1. Install prompt-kit components via shadcn CLI or direct source into `frontend/src/components/prompt-kit/`:
   - `tool`
   - `steps`
   - `thinking-bar`
   - `text-shimmer`
   - `system-message`
   - `source`
   - `prompt-suggestion`
   - `scroll-button`
2. Apply strict square geometry (`--radius: 0`, `rounded-none`), DM Mono tokens for numbers/slugs, and restrained forest green accents.

### Part 2: Telemetry Deck Component (`TelemetryDeck.tsx`)
1. Create `TelemetryDeck.tsx` wrapping `Tool` and `SystemMessage`:
   - Collapsed summary in `StatusStrip` and `SearchSummaryBar`.
   - Grid of provider cards displaying live status (`Completed`, `Cached`, `Failed`, `Circuit Open`), duration in ms, and parsed vs. dropped posting counts.
   - Budget meter showing daily Serper calls remaining (resets UTC midnight).

### Part 3: Router & Page Decoupling
1. Establish clean route handling for:
   - `/`: `LandingPage` (Hero, Glyph Portal, Suggestions, How It Works).
   - `/search` & `/app`: `ProductWorkspace` (Compact header, SearchForm drawer, ResultsTable, Telemetry Deck, DetailSheet).
2. Wire search query submission on `/` to navigate to `/search?q=...` with View Transitions.
3. Wire brandmark in `/search` to return to `/`.

### Part 4: Provenance & Detail Inspection
1. Update `DetailSheet.tsx` to include `Steps` trace showing:
   - Match tier (Tier 1 JSON-LD vs Tier 2 ATS API vs Tier 3 Scraper).
   - Exact evidence snippet for remote policy and compensation.
   - `Source` hover preview for direct requisition URL.

---

## 3. Verification Protocol

1. Run `.\scripts\verify.ps1` (validates git secrets, frontend lint, frontend typecheck/build, backend pytest).
2. Browser verification across 5 standard viewports (1920, 1440, 1024, 768, 390):
   - Landing page load and navigation to `/search`.
   - Active SSE search with `thinking-bar` and `TelemetryDeck` live updates.
   - Provider inspect details in `Tool` cards.
   - DetailSheet open with `Steps` pipeline trace.
   - Dark/light mode theme contrast.
