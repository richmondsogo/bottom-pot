# Step 00: Bottom Pot Frontend Redesign & Craft Overhaul

**Step Branch**: `chore/adopt-agent-starter` (PR A) → `feat/ui-redesign` (PR B)  
**Primary Branch**: `main`  
**Pull Request A**: `chore: adopt agent starter (docs, skills, scripts)`  
**Pull Request B**: `feat(ui): redesign with square design system, results workflow and polish`  

---

## Objective

Elevate Bottom Pot from an AI-vibecoded prototype into a calm, editorial, high-craft job discovery product. Enforce the non-negotiable square design system (`--radius: 0`, cream + deep green palette), fix all 11 identified UX flaws, extract pure modular logic with unit tests, add Playwright e2e and accessibility suites, achieve clean verification (Lighthouse & axe), and document the frontend for non-React developers.

---

## Hard Constraints

1. **Zero Backend / API Changes**: No modifications to `/search`, query parameters, Serper integrations, models, or response schemas.
2. **Strict Square Design System**: Radius 0 everywhere (cards, inputs, buttons, badges, avatars, chips, sheets, focus rings). No pills, circles, or rounded avatars.
3. **Budget & Limited Serper Credits**: Zero live Serper searches for verification (count = 0). All verification uses local mock fixtures and recorded datasets.
4. **No Hosting Alterations**: No touches to Neon or Vercel, no secret commits, no environment variable tampering.
5. **Windows PowerShell Compatibility**: All tooling scripts must be cross-platform and natively executable in Windows PowerShell.
6. **Framework Invariance**: Stay on React 19 + Vite 8 + Base UI + Tailwind CSS v4. No framework migration.

---

## Master Implementation Plan

### Phase 0: Orient and Protect (Completed)
- [x] Inspect workspace, backend health (`/health`), frontend setup, and existing test suites.
- [x] Snapshot uncommitted state and design reference to branch `chore/pre-redesign-snapshot`, tag `pre-redesign`, and push to origin.
- [x] Identify technology stack and architectural layers.
- [x] Capture baseline "before" screenshots across all 6 states (`landing`, `loading`, `results`, `saved-results`, `no-results`, `error`) and 5 viewports (1920x1080, 1440x900, 1024x768, 768x1024, 390x844) into `docs/design/before/`.

### Phase 1: Adopt Agent Starter (PR A - Current)
- [x] Branch `chore/adopt-agent-starter`.
- [x] Bring starter assets from `richmondsogo/antigravity-project-starter-repo`:
  - `BUILD_PROTOCOL.md`
  - `.gitattributes`
  - `.agents/mcp_config.json.example`
  - `.agents/skills/*`
  - `docs/adr/0000-template.md`
  - `docs/steps/00-plan-template.md`
  - `docs/agents/*`
  - `scripts/bootstrap.ps1`, `scripts/check-env.ps1`, `scripts/verify.ps1`
- [x] Fill `CONTEXT.md` with Bottom Pot domain, users, constraints, and non-goals.
- [x] Merge `DESIGN.md` uniting starter principles with Bottom Pot's square identity.
- [x] Update `docs/agents/file-structure.md`, `mcps.md`, and `skills.md`.
- [x] Customize `scripts/verify.ps1`.
- [x] Merge `.gitignore` (safeguard `.agents/mcp_config.json`, `.env*`, keep `docs/design/`).
- [x] Verify PR A has ZERO application code changes (`git diff --stat`).
- [ ] Push branch `chore/adopt-agent-starter` and open PR A via GitHub MCP.

### Phase 2: Design Direction, Tokens & UI Redesign (PR B)
- [ ] Branch `feat/ui-redesign` stacked on `chore/adopt-agent-starter`.
- [ ] Record ADRs:
  - `docs/adr/0004-square-design-system-and-daybreak-craft.md`
  - `docs/adr/0005-client-side-visited-state-and-results-persistence.md`
  - `docs/adr/0006-results-detail-panel-and-keyboard-navigation.md`
- [ ] Implement central design tokens in `frontend/src/index.css`:
  - `--radius: 0`, colors (`--bg`, `--surface`, ink tiers, deep green accent, semantic tags), 4px spacing scale, font scales, focus rings.
- [ ] Address all 11 observed UI problems:
  1. Collapse status chrome into a single quiet strip (`StatusStrip`).
  2. Eliminate developer jargon from UI text.
  3. Remove uppercase mono eyebrows flattening hierarchy; sentence case sans elsewhere.
  4. Unify empty values (`—` in table, detailed wording in sheet); auto-hide salary column if empty.
  5. Replace circular pastel avatars with deterministic square monogram tiles.
  6. Replace heavy work-model badges with quiet square tags (text + 6px square color marker).
  7. Flatten card-inside-card nesting; full-width table within page max-width.
  8. Fix sticky header/filter stacking glitch (solid backgrounds, proper z-indexes).
  9. Remove empty gradient blob from hero.
  10. Collapse hero into compact sticky search bar upon results delivery.
  11. Implement 2-line title clamping with native full-title tooltip and uniform row heights.
- [ ] Implement slide-out Detail Panel (desktop right-side sheet, mobile full-screen).
- [ ] Implement visited postings dimming (Daybreak pattern) with safe localStorage wrapper.
- [ ] Implement full keyboard shortcuts (j/k row navigation, Enter/o open, Esc close, `/` focus filter, `?` shortcut legend).
- [ ] Build multi-select platform chips with count and Select All / Select None controls.
- [ ] Add 3-step "How it works" hairline section and quiet supported platforms list.
- [ ] Design all 6 states: Landing, Loading (honest timer, skeleton rows), Results, Saved Results strip, No Results, and Error (humanized copy + Retry).
- [ ] Ensure full responsive layouts (1920, 1440, 1024, 768, 390px) with 0 horizontal page scroll.

### Phase 3: Frontend Code Quality & Testing (PR B)
- [ ] Decompose giant components into modular single-purpose files.
- [ ] Extract pure logic modules into `frontend/src/lib/`:
  - `filter.ts`, `sort.ts`, `visited.ts`, `storage.ts`, `mock.ts`.
- [ ] Add unit tests for extracted modules using Vitest.
- [ ] Add Playwright e2e smoke suite against mock data covering all states, interactions, and keyboard shortcuts.
- [ ] Integrate `@axe-core/playwright` for zero serious/critical a11y violations.
- [ ] Eliminate dead code, unused dependencies, and console logs. Measure bundle size before/after.

### Phase 4: Verification & Critique Loops (PR B)
- [ ] Capture "after" screenshots across all 6 states and 5 viewports into `docs/design/after/`.
- [ ] Execute 3 critique rounds comparing "before", "after", and `daybreak-reference.png`.
- [ ] Run Chrome DevTools Lighthouse audit (targets: Perf ≥ 90, A11y ≥ 95, Best Practices ≥ 95, SEO ≥ 90).
- [ ] Verify zero console errors and warnings.
- [ ] Run `scripts/verify.ps1` and verify all green.

### Phase 5: Documentation & Delivery (PR B)
- [ ] Rewrite `README.md` for web app + CLI, mock mode, architecture, and fix clone URL.
- [ ] Create `docs/FRONTEND.md` for non-React developers.
- [ ] Update `docs/steps/00-plan.md` with complete execution log and commit SHAs.
- [ ] Push `feat/ui-redesign` and open PR B via GitHub MCP.
- [ ] Present comprehensive final report to the user with PR links, before/after comparisons, and QA checklist.
