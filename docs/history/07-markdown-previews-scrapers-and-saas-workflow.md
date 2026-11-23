# Step 07: Lightweight Markdown Previews, Jobberman & HotNigerianJobs Deep Fix, and SaaS Workflow Additions

**Step Branch**: `step/07-markdown-previews-scrapers-and-saas-workflow`  
**Base Branch**: `main` (`e44cacc3b87e3c536bd60b9f60257993c3ceeb37`)  
**Primary Branch**: `main`  

---

## Objective

1. Render structured, sanitized GitHub-Flavored Markdown in the preview drawer (`DetailSheet.tsx`) using the already-installed `react-markdown`, `remark-gfm`, and `rehype-sanitize` libraries without adding dependencies or altering the Square Design System (`DESIGN.md`).
2. Fix Jobberman missing job descriptions in the preview drawer by extracting card summaries on the search page and concurrently enriching listing detail pages (`article.job__details`) into clean Markdown.
3. Deep-fix HotNigerianJobs by routing searches to native `/role/<id>/` and `/field/<id>/` feeds, resolving homepage roundup placeholders via their roundup detail pages to obtain real per-role URLs, salaries, and locations, and concurrently enriching single-role detail pages (`.mycase4` with AdSense stripped) into Markdown.
4. Add two cohesive SaaS workflow capabilities:
   - **Saved Jobs ("Shortlist") & Application Stage Tracker** (`Saved` · `Applied` · `Interviewing` · `Archived`) with `s` keyboard shortcut, `DetailSheet` stage bar, and `Saved (N)` toolbar filter.
   - **URL-Synced Search State + 1-Click Recent Search Presets** so active searches and filters are shareable/bookmarkable and returning users can launch recent searches in one click.

## Scope

### Included
- **Markdown Normalization Fix (`src/project_files/field_normalizer.py`)**:
  - Fix bullet-line regex in `to_markdown()` so lines starting with `**Bold**` or `*Italic*` are not mangled into `- *Bold**`.
  - Strip `\ufffd` and `\xa0` before HTML parsing in `to_markdown()` and preserve spacing around `<strong>` / `<em>` tags.
- **Jobberman, MyJobMag, and HotNigerianJobs Scrapers (`src/project_files/nigerian_scrapers.py`)**:
  - `JobbermanScraper`: tighten card selector (`div[data-cy='listing-cards-components']` first) with `seen_ids` deduplication, extract card summary `<p>`, and concurrently enrich detail pages (`article.job__details`) into Markdown (`### Job Summary`, `### Job Description & Requirements`).
  - `MyJobMagScraper`: extract `li.job-desc` card snippet into Markdown and populate `work_model_source` / `work_model_evidence`.
  - `HotNigerianJobsScraper`:
    - Add `_select_feed_urls()` mapping query keywords to live HNJ `/role/<id>/` (`1108` Software Engineer, `427` Full Stack, `1121` Frontend/Backend, `445` Web, `437` Mobile, `1010` Data Analyst/Scientist, `349` UI/UX, `441` DevOps/SysAdmin, `365` DBA) and `/field/<id>/` (`273`, `268`, `258`, `257`, `269`) endpoints.
    - Extract per-role `Salary:` and inline descriptions in numbered roundup detail blocks.
    - Add `_resolve_roundup_placeholders()` to upgrade homepage roundup `#slug` items with their dedicated `/hotjobs/<id>/<slug>.html` URLs and per-role metadata.
    - Add `enrich_listing_from_detail()` and `_extract_hnj_body_markdown()` to strip Google AdSense `<script>`/`<ins>` tags from `.mycase4` and convert full job descriptions to Markdown.
- **Frontend Markdown Preview & SaaS Workflow (`frontend/src/components/DetailSheet.tsx`, `frontend/src/lib/savedJobs.ts`, `frontend/src/lib/urlState.ts`, `frontend/src/App.tsx`, `frontend/src/components/Toolbar.tsx`, `frontend/src/components/SearchForm.tsx`, `frontend/src/components/SearchSummaryBar.tsx`, `frontend/src/components/ResultsTable.tsx`, `frontend/src/components/ResultsCards.tsx`, `frontend/src/components/ShortcutsModal.tsx`)**:
  - Render `job.description` and `job.requirements` with `ReactMarkdown` + `remarkGfm` + `rehypeSanitize` and Square Design System typography mappings, plus an honest fallback message when a listing has no description.
  - Implement `savedJobs.ts` (`localStorage` shortlist + `Saved`/`Applied`/`Interviewing`/`Archived` stages) and `urlState.ts` (URL query parameter sync + recent search presets).
- **Real Fixtures & Automated Tests (`tests/fixtures/real/jobberman/`, `tests/fixtures/real/hotnigerianjobs/`, `tests/test_scrapers_and_clients.py`, `tests/conftest.py`, `playwright.config.js`, `frontend/src/lib/__tests__/modules.test.ts`, `tests/e2e/bottom-pot.spec.js`)**:
  - Capture 3 real Jobberman fixtures and 2 new HotNigerianJobs fixtures via `scripts/capture_fixtures.py`, configure worktree/CI test defaults in `tests/conftest.py` and `playwright.config.js`, and add unit + E2E tests.

### Excluded
- Any changes to the Square Design System (`DESIGN.md`) palette, typography scale, border radii (`--radius: 0`), or green budget limits.

## Plan

1. Capture real HTML fixtures from `jobberman.com` and `hotnigerianjobs.com` via `scripts/capture_fixtures.py`.
2. Fix `to_markdown()` bold-prefix handling in `src/project_files/field_normalizer.py`.
3. Upgrade `JobbermanScraper`, `MyJobMagScraper`, and `HotNigerianJobsScraper` in `src/project_files/nigerian_scrapers.py`.
4. Implement Markdown preview rendering in `DetailSheet.tsx` and build `savedJobs.ts` + `urlState.ts` SaaS workflow integrations across the React frontend.
5. Add backend unit tests (`pytest`), frontend unit tests (`vitest`), and E2E assertions (`playwright`), then run `.\scripts\verify.ps1` and `python scripts/eval_work_model.py results.json`.
6. Perform two-axis `code-review` (Standards + Spec), open PR, merge into `main`, and record provenance.

## Implementation

- Completed backend scraper and normalizer enhancements in `src/project_files/field_normalizer.py` and `src/project_files/nigerian_scrapers.py`.
- Completed frontend Markdown preview and SaaS workflow features in `frontend/src/`.
- Added real fixtures and unit/E2E test coverage.

## Verification

- `python scripts/eval_work_model.py results.json`: Passed (`0` regressions).
- `pytest -q`: **301 passed** (including new real-fixture tests for `JobbermanScraper` and `HotNigerianJobsScraper`).
- `npm --prefix frontend run test`: **74 passed** (including unit tests for `savedJobs.ts` and `urlState.ts`).
- `.\scripts\verify.ps1`: **8 / 8 checks passed** (Git state, secrets check, CSS cascade lint, `oxlint`, `vitest`, `tsc + vite build`, `pytest`, and **14 / 14 Playwright E2E tests** including axe-core WCAG 2.1 AA, typography audit, 5-viewport layout audit, spacing audit, column alignment audit, and green budget `< 35` audit).

## Two-Axis Code Review

- **Standards Axis**:
  - Zero hard violations of `DESIGN.md` (`--radius: 0`, 1px borders, typography scale, spacing scale, green budget `< 35` elements) or fixture provenance (`scripts/capture_fixtures.py` `.json` sidecars).
  - Addressed judgement calls: consolidated `h1`–`h4` Markdown heading components into `renderMarkdownHeading` with sentence-case typography per `DESIGN.md` §3, and extracted `WorkspaceUrlState` interface in `frontend/src/lib/urlState.ts`.
- **Spec Axis**:
  - Addressed all spec alignment findings:
    - Added `params.has('ng')` to `readStateFromUrl()` in `frontend/src/lib/urlState.ts` and updated `App.tsx` so opening `?saved=1` restores the saved shortlist directly into the `'delivery'` screen.
    - Updated `HotNigerianJobsScraper._select_feed_urls()` to cap at `urls[:3]` and made both `extra_urls` feed fetching and `_resolve_roundup_placeholders()` concurrent via `asyncio.gather`.

## PR & Merge Provenance

- **Pull Request**: [#11](https://github.com/richmondsogo/bottom-pot/pull/11)
- **Step Commit**: `77398a5`
- **Target Branch**: `main`
