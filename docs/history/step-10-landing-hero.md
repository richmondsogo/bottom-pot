# Step 10: Rebuild Landing Hero with Glyph Portal & Strip Internal Jargon

**Step Branch**: `step/10-landing-hero`  
**Primary Branch**: `main`  
**Pull Request**: https://github.com/richmondsogo/bottom-pot/pull/13  
**Commit SHA**: `13120e8`  

---

## 1. Landing Surfaces Architecture

The Bottom Pot application contains two distinct landing surfaces:
1. **Marketing Landing Page** (`/` when `viewMode === 'marketing'`): The public editorial face for discovery, explanation, and entry. **This is the surface overhauled in this step.**
2. **Product Workspace Search Surface** (`/app` or `?view=app` / `?view=workspace` when `screen === 'form'`): The direct, distraction-free search workbench with full filters, shortlist drawer, and keyboard shortcut listeners. **Left completely intact and unmodified** per scope instructions.

---

## 2. Problem & Principles

The previous marketing hero utilized a generic SaaS presentation (pill eyebrow, centered headline, grey lead paragraph, fake input row, and aggregator metrics). Furthermore, the copy spoke to engineers about internal pipeline architecture rather than to job seekers looking for honest work. It violated:
- **ADR 0004**: No developer jargon, no nested card-in-card layouts.
- **ADR 0010**: Monospace strictly reserved for counts, slugs, and shortcuts; no all-caps display headings.
- **ADR 0021**: Green budget discipline (deep green field violated accent restrictions).

**Core Principle**: Internals belong in docs and ADRs, never in the UI. A real user must never encounter the words: `tier`, `ladder`, `provenance`, `SSE`, `dork`, `ATS`, `serper`, `cache`, `ADR`, `engine`, `workspace`, `mock`, or `fabricated`.

---

## 3. Implementation Summary

### Part 1: Glyph Portal Hero (`frontend/src/components/ui/glyph-portal.tsx`)
- Installed self-hosted `GlyphPortal` with zero external dependencies (no Lucide icons, no Unsplash URLs, no remote fonts).
- Wordmark: `word="Bottom Pot"` in mixed case using self-hosted `Geist Variable` at `fontWeight: 700` (documented exception in ADR 0022).
- Dynamic ink detection: distance-transform algorithm (`findInterior`) computes the optimal ink patch interior without hardcoded offsets.
- Scroll configuration: `scrollLength={1.8}`, `interactive={true}`, `annotations={false}`, `enterLabel="Start searching"`.
- Theming & Green Budget (ADR 0021):
  - `--gp-paper: var(--bg)`
  - `--gp-ink: var(--ink)`
  - `--gp-field: var(--ink)` (deep ink field, strictly avoiding full-screen green container bloat)
  - `--gp-foreground: var(--bg)`
  - Deep forest green (`var(--accent)`) appears exclusively on the primary CTA ("Start searching") and square focus rings.
- Geometry: Overrode all internal radii and mobile select picker to `border-radius: 0`.
- Font Loading Gate: Evaluates `document.fonts.load('700 100px "Geist Variable"')` with a 1.6s timeout. On delay or timeout, renders a rock-solid static hero fallback (headline, wordmark, CTA, and search form) with zero layout shift.
- Opening Frame (`front` slot):
  - Architectural header: BP mark on left; on right, quiet anchor links ("How it works", "Where we search", "Why Bottom Pot") and theme toggle. No version tags, no ⌘K chip. Collapses cleanly on mobile viewports (`hidden md:flex`).
  - `<h1>` above wordmark: "Jobs straight from the company."
  - Support line below wordmark: "Real openings from company career pages. No reposts, no recruiter spam."
  - Primary CTA link: "Start searching ↘" styled as square primary button.
  - Quiet bottom hint: "Scroll to look inside".
- Revealed Content (`children` slot):
  - `<h2>`: "What kind of role are you after?"
  - Framed `SearchForm` (embedded variant, max-w-[760px], light surface on the ink field).
  - Platform chips tucked behind a disclosure labelled "Where to search: all platforms".
  - Under the form: plain text example buttons ("React engineer, remote" · "Python developer in Lagos" · "Product designer").
  - Quiet trust line: "If a listing doesn't say whether it's remote, we leave it blank instead of guessing."

### Part 2: Human-First Editorial Copy Overhaul
All marketing page sections were rewritten to speak plainly and warmly to job seekers:
1. **Example Table Intro** (`SampleResultsSection.tsx`):
   - Headline: **Here's what a search looks like.**
   - Subhead: "Sample results. Every row links to the company's own listing."
   - Explicit "Sample data" label badge.
   - Caption under rows: "Why Remote? The employer's listing says so."
2. **Why It's Different** (`WhyDifferentSection.tsx`):
   - Three plain columns, hairline-separated, no cards:
     - 01 **Straight from the source**: "We search company career pages directly, so every job is one the employer posted themselves."
     - 02 **Remote means remote**: "We only call a job remote, hybrid or on-site when the listing says so. If it doesn't, we leave it blank."
     - 03 **Made with Nigerian developers in mind**: "Find roles open to Lagos, Abuja and remote-friendly teams, plus local boards like Jobberman and MyJobMag."
   - Quiet keyboard navigation note: "Browse with your keyboard (j / k / Enter)".
3. **Where We Search** (`WhereWeSearchSection.tsx`):
   - Headline: **Where we search.**
   - Copy: "Greenhouse, Lever, Ashby, Workable and 12 more hiring platforms, plus Nigerian job boards." (The number 12 is derived dynamically from `ALL_PLATFORMS`).
   - Plain text and monogram grid only (no URL patterns, no fidelity tiers, no selector buttons).
4. **Editorial Manifesto & Final CTA** (`EditorialManifesto.tsx`):
   - Headline: **Job hunting shouldn't mean wading through spam.**
   - Copy: Plain 3-paragraph critique of aggregator spam, unverified reposts, and resume harvesting, explaining how Bottom Pot queries companies directly.
   - Final CTA: **Ready to find your next role?** Primary button: "Start searching" (transitions to workspace search); secondary link: "Try an example".
   - Footer: "Bottom Pot · Jobs straight from the company".

### Part 3: Deletions from Landing Page
- Deleted version tags (`v2.4 · ats-direct`).
- Deleted all mono pill badges (`architectural principles · adr-0001..0021`, `the bottom pot manifesto`, `coverage & system of record`, `18+ ats platforms · zero aggregator middlemen`).
- Deleted fake input row (`query:`, `Run SSE search`, `quick presets:`).
- Deleted mock mode buttons (`Inspect live mock dataset`, `Load instant mock workspace (?mock=1)`). Mock mode remains accessible via dev flags (`?mock=1`), never in customer UI.
- Deleted fake URL bar (`bottom-pot://workspace/live-preview`) and the 4 numbered stage tabs.
- Deleted stats strip (`18+`, `7 tiers`, `0`, `<50ms`).
- Deleted the engineered cache/SSE card (`query_hash`, `serper_credits_consumed`, `two_tier_cache`) and nested cards.
- Deleted URL patterns and fidelity tiers from the platform grid.
- Deleted footer telemetry string (`radius: 0px · adr-0001..0021 verified · press ⌘K anytime`).
- Deleted obsolete marketing components (`HeroSection.tsx`, `HeroInteractiveStage.tsx`, `SignalMetricsStrip.tsx`, `BentoFeatureGrid.tsx`, `ProvenanceLadderInteractive.tsx`, `AtsPlatformMatrix.tsx`, `MarketingHeader.tsx`).

### Part 4: Architectural Decision Record
- **ADR 0022**: Documented the weight 700 exception for the display wordmark, the ink field token mapping satisfying ADR 0021's green budget, and why sticky scroll-driven glyph zoom is not scroll-jacking (complying with ADR 0014).

---

## 4. Verification Telemetry

### Automated Suite (`.\scripts\verify.ps1`)
- **Git Available**: Passed
- **Secrets Audit**: Passed (no credentials or private keys tracked)
- **CSS Cascade Lint**: Passed (`node scripts/lint_css_cascade.js` — zero unlayered resets)
- **Frontend Oxlint**: Passed (0 errors, 3 warnings on standard UI fast-refresh exports)
- **Frontend Vitest**: Passed (4 suites, 33 tests in 1.93s)
- **Frontend Build**: Passed (`tsc -b && vite build` in 1.92s, bundle size reduced from 93.56 kB to 88.66 kB)
- **Backend Pytest**: Passed (`pytest tests/test_api_endpoints.py` — 5 passed)
- **Playwright E2E Suite**: Passed (15/15 tests passed across all responsive viewports, typography, a11y, column alignment, and green budget)

### Browser Verification (`scripts/verify_hero_browser.js`)
- **DOM Jargon Audit**: 0 banned words (`tier`, `ladder`, `provenance`, `SSE`, `dork`, `ATS`, `serper`, `cache`, `ADR`, `engine`, `workspace`, `mock`, `fabricated`) detected in visible landing text.
- **5 Responsive Viewports Tested & Captured**:
  - `docs/screenshots/hero_1920x1080_p0.png`: Display opening frame with balanced wordmark and CTAs.
  - `docs/screenshots/hero_1920x1080_p05.png`: Mid-portal scroll zoom into letter interior.
  - `docs/screenshots/hero_1920x1080_p10.png`: Revealed embedded search form framed on deep ink field.
  - `docs/screenshots/hero_1440x900_p0.png`: Standard desktop presentation.
  - `docs/screenshots/hero_1024x768_p0.png`: Small desktop / landscape tablet.
  - `docs/screenshots/hero_768x1024_p0.png`: Portrait tablet.
  - `docs/screenshots/hero_390x844_p0.png`: Mobile viewport with single-line header and touch picker.
- **Alternative States**:
  - `docs/screenshots/hero_reduced_motion.png`: Motion disabled (`data-gp-motion="off"`), instant access to form.
  - `docs/screenshots/hero_font_timeout_fallback.png`: Simulated 1.6s font timeout rendering static hero without shift.
- **Keyboard Navigation**:
  - Sequential Tab key traversal: Brandmark → Anchor links → Theme toggle → "Start searching" CTA → Enter key reveals search form.
  - Arrow-key letter selection in portal choices verified.
- **Accessibility**:
  - Axe-core scan on marketing landing: 0 critical, 0 serious violations.
