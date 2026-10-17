# ADR 0006: Results Detail Panel and Keyboard Navigation

## Status
Accepted

## Context
In the previous UI, clicking "Details" expanded an inline accordion row across the full table width, displacing neighboring rows and causing jarring layout shifts. Furthermore, navigating dense job listings required tedious mouse clicks across multiple small table buttons.

## Decision

1. **Slide-Out Detail Sheet Architecture**:
   - On wide desktop screens (≥1024px), selecting a job opens an anchored slide-out right-side sheet (`480px` wide). The table remains visible and scrollable in the background.
   - On mobile screens (<768px), the sheet opens full-width from the bottom.
   - The sheet displays: Job Title, Company, Monogram tile, Metadata line (`Location · Work Model · Employment Type`), Formatted Compensation, Freshness/Date, Extraction Confidence indicator, Description markdown, Primary "Open posting" button (opens in new tab with `rel="noopener noreferrer"`), and Secondary "Copy link" button.
   - Opening a job automatically marks it as visited (ADR 0005).

2. **Keyboard Navigation Workflow**:
   - `j` or `ArrowDown`: Move active row selection down.
   - `k` or `ArrowUp`: Move active row selection up.
   - `Enter` or `o`: Open the detail panel for the currently active row (or open the posting directly).
   - `Escape`: Close the detail panel or dismiss active popovers.
   - `/`: Instantly focus the search/filter input field.
   - `?`: Toggle a quiet keyboard shortcuts legend modal.

3. **Motion**:
   - Subtle 150ms ease-out slide transitions for sheet appearance and row selection highlight.
   - Respects `prefers-reduced-motion` by disabling transitions when requested.

## Consequences
- Fast, fluid, power-user exploration of job listings without row-jumping layout thrash.
- Superior mobile usability with dedicated full-screen inspection.
