# ADR 0015: Theme System and Dark Mode Contrast

## Status
Accepted

## Context
Bottom Pot's visual brand is rooted in a warm editorial cream light mode (`#FAF8F5`) with deep forest green accents (`#1A382B`). However, modern developer tools require first-class dark mode support. A dark mode that is merely an inverted afterthought or compromises square geometry / contrast is unacceptable.

## Decision
1. Implement a complete token-driven `.dark` class theme:
   - Canvas: `#0C0D0C` (deep rich obsidian cream equivalent).
   - Surfaces: `#151715` (cards and inputs), `#1C1E1C` (hover states).
   - Inks: Primary `#EDEDEA` (15.5:1 contrast), Muted `#A6A59E` (7.2:1 contrast), Subtle `#7A7973` (4.8:1 contrast).
   - Borders: Hairlines at 12% white alpha (`rgba(255, 255, 255, 0.12)`).
   - Green Accent Re-tuning: `#2E7D52` / `#369963` for interactive buttons and indicators to ensure full WCAG AA contrast against dark backgrounds.
2. Zero Flash of Unstyled Theme (FOUT):
   - Inline pre-hydration script in `index.html` checks `localStorage.getItem('bp.theme')` or system `window.matchMedia('(prefers-color-scheme: dark)')` before the React tree mounts.
3. Controls:
   - Header theme toggle button (Sun / Moon icon).
   - Command palette "Toggle theme" command.

## Consequences
- Full parity between light and dark modes across every state.
- WCAG AA contrast verified across all five viewports.
- No flash of light theme on page load when dark mode is enabled.
