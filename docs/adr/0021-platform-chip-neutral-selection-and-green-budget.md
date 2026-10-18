# ADR 0021: Platform Chip Neutral Selection and Green Accent Budget

## Status
Accepted

## Context
In previous iterations, the 18 platform chips rendered with full green borders whenever active. Because all platforms are active by default, the entire landing page displayed 18 bright green outlines. This destroyed the visual hierarchy, turning the signature forest green accent (`#1A382B` / `#34D399`) into visual noise rather than an intentional accent.

## Decision
1. **Platform Chip Selection Design**:
   - Selected chips use neutral styling:
     - Border: primary ink line (`border-[var(--ink)]`).
     - Background: subtle surface fill (`bg-[var(--surface-subtle)]`).
     - Text: bold ink (`font-medium text-[var(--ink)]`).
     - Accent: a single small forest green checkmark icon (`text-[var(--accent)]`) preceding the label.
   - Unselected chips use muted styling:
     - Border: subtle line (`border-[var(--line)]`).
     - Background: transparent.
     - Text: muted (`text-[var(--ink-muted)]`).
   - Chip dimensions: 4-column grid on desktop (2-column on mobile), 36px height (`h-9`), 8px gaps (`gap-2`).
2. **Strict Green Usage Budget**:
   - Green is strictly reserved for:
     1. Primary action CTA button ("Search ATS platforms").
     2. Selected-state checkmarks on platform chips.
     3. Active Remote marker / tag dot.
     4. Table row hover accent bar (2px left border).
     5. Square keyboard focus rings.
     6. Links and status dots.
   - Banned green usages:
     - Green borders on all chips or passive containers.
     - Green non-interactive background panels or banners.
     - Unselected or multi-state outlines.
3. **Automated Enforcement**:
   - Added an automated Playwright audit (`green budget audit`) that verifies the total count of elements utilizing green borders or backgrounds does not exceed the budgeted threshold on landing and results pages.

## Consequences
- The editorial palette remains warm, crisp, and calm.
- Green retains its high-intent signal value for primary actions and affirmative selections.
