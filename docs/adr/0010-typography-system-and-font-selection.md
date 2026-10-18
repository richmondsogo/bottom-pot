# ADR 0010: Typography System and Font Selection (Geist Sans + DM Mono)

## Status
Accepted

## Context
Pass 1 had typography chaos: mixed sans (Manrope), bold mono eyebrow labels, uppercase tracked mono chips, mixed font weights within single controls, and off-scale font sizes. The mission mandates at most TWO self-hosted variable font families:
- ONE sans for all UI text, headings, buttons, and labels.
- ONE mono strictly for machine-ish data: platform slugs, counts in tabular contexts, keyboard hints, and ISO timestamps in tooltips.
- Hierarchy must be achieved through scale, weight (400/500/600), and ink tiers (ink / muted / subtle)—never uppercase mono boxes or bold mono text.

## Decision
1. **Primary Sans: Geist Variable (`@fontsource-variable/geist`)**:
   - Neutral, precise geometric grotesk with optical sizing, balanced character metrics, and tight tracking (`-0.025em` on display/headings).
   - Serves all UI controls, body text, headlines, navigation, and badges.
   - Self-hosted via `@fontsource-variable/geist`, `font-display: swap`.
2. **Machine Monospace: DM Mono (`@fontsource/dm-mono`)**:
   - Monospace font strictly reserved for: platform slugs (`lever`, `greenhouse`), keyboard shortcut badges (`⌘K`, `/`), and tabular counts.
   - Banned from: headings, eyebrow labels, regular buttons, suggestions, filter labels, and status messages.
3. **Weight Discipline**: Only weights 400 (regular), 500 (medium), and 600 (semi-bold) are permitted.
4. **Sentence Case Everywhere**: All uppercase tracked mono labels are removed.

## Consequences
- Immediate visual calm and coherence across the entire application.
- Clear distinction between human editorial language (Geist) and machine metadata (DM Mono).
- Enforced by automated typography audit tests in Playwright.
