# Step 16: Result Mix & HotNigerianJobs Application Extraction

**Step Branch**: `step/16-result-mix-and-hnj-extraction`  
**Primary Branch**: `main`  
**Baseline**: main at `7391f5f` after step 15 (hero cleanup), PR #18  
**Status**: COMPLETED  
**PR URL**: TBD  
**First Commit SHA**: `926bd51`  
**Last Commit SHA**: `ad10a00`  
**Merge Commit SHA**: (recorded in step 17 doc)  

---

## 1. Goal

1. Extract authentic direct application methods (clean ATS/external apply URLs and decoded Cloudflare/plain-text emails) from HotNigerianJobs postings instead of linking users back to aggregator card pages or unroutable internal links.
2. Gracefully handle `mailto:` links across the frontend without opening blank browser tabs or throwing URL parse errors.
3. Fix the Nigerian board result skew by eliminating early cancellation of pending ATS queries when fast Nigerian scrapers return high volumes, enforcing Nigerian board dominance caps when ATS queries are active, and relaxing Nigerian location tokens in ATS dorks so global remote roles hiring in Nigeria/EMEA are discoverable.
4. Lock `SERPER_MODE: process.env.SERPER_MODE || 'cache_only'` in `playwright.config.js` to safeguard Serper API budgets during automated browser runs.

---

## 2. Key Scope & Implementation Details

### A. HotNigerianJobs Application Method Extraction (`src/project_files/nigerian_scrapers.py`)
- **Cloudflare & Plain-Text Email Decoding**:
  - Implemented `_decode_cf_email(cf_hex: str)` performing XOR hex decoding against the key byte.
  - Automatically extracts and decodes emails from `<span class="__cf_email__" data-cfemail="...">` tags and `/cdn-cgi/l/email-protection#<hex>` anchor hrefs.
  - Falls back to regex extraction for plain-text email addresses in application instructions.
- **Exact Subject Line Extraction**:
  - Implemented `_extract_hnj_subject(text: str, default_title: str)` with pattern matching for explicit instructions (e.g. `using "Chinese Translator" as the subject`, `with "X" as subject`, `subject of the email should be "X"`).
  - Uses exact quoted subjects verbatim in `?subject={urllib.parse.quote(subject)}`; falls back to `role_title` without prepending extraneous text.
- **External Apply URLs & Tracking Cleanup**:
  - Implemented `_clean_external_apply_url(url: str)` which fixes duplicate protocol typos (`https://https://...`) and strips aggregator tracking parameters (`src=HNJ`, `utm_source`, `utm_medium`, `utm_campaign`, etc.).
  - Implemented `_is_valid_external_apply_url(url: str)` strictly rejecting internal `hotnigerianjobs.com` URLs, `javascript:`, `#anchors`, `/cdn-cgi/`, social share URLs (`facebook.com`, `twitter.com`, `x.com`, `linkedin.com/share`, `whatsapp.com`, `t.me`), and ad networks (`doubleclick.net`, `googlesyndication`, `googleadservices`).
- **Multi-Position Roundups & Detail Enrichment**:
  - In multi-position roundup posts (`Case 1` in `parse_html`), checks each numbered role block first for external links, then falls back to any shared "How to Apply" / "Method of Application" section at the bottom of the container with sub-role title plugged in.
  - Updated `_enrich_detail_item` and `enrich_listing_from_detail` so feed cards pointing to HNJ detail URLs or `#slug` anchors fetch and replace `apply_url` with the extracted direct external URL or `mailto:` link.
- **Provenance Discipline**:
  - Preserves `source_url` as the original HotNigerianJobs posting URL (admin provenance trace).
  - Sets `apply_url` to the direct external apply URL or `mailto:` URI (or falls back to HNJ URL only when no external link or email exists).

### B. Frontend `mailto:` Handling (`DetailSheet.tsx`, `normalize.ts`, `source.tsx`)
- **Navigation Safety**:
  - In `DetailSheet.tsx` and `openPosting()`, checks if `targetUrl.startsWith('mailto:')`.
  - Replaces `window.open(targetUrl, '_blank', 'noopener,noreferrer')` (which spawns dead blank tabs) with `window.location.href = targetUrl`.
- **Hostname Formatting & Favicon Fallback**:
  - Updated `extractDomain()` in `normalize.ts` and `<Source>` in `source.tsx` to safely extract email addresses (`hr@avtne.com`) from `mailto:hr@avtne.com?...` without throwing `TypeError: Invalid URL` on `new URL()`.
  - In `<SourceTrigger>` and `<SourceContent>`, disabled `target="_blank"` on `mailto:` anchors and bypassed external favicon queries for `mailto:` targets.

### C. Balanced Result Mix & Nigerian Skew Fix (`search_pipeline.py`, `query_builder.py`)
- **Progressive Stopper Protection**:
  - In `SearchOrchestrator.run`, ensured `effective_max_results` reaching its threshold while ATS tasks are still pending does not cancel or starve pending ATS queries.
  - Pending ATS tasks continue until completion; early halting only applies to redundant Nigerian scrapers while ATS is running.
- **Dominance Caps**:
  - Implemented per-scraper cap (`min(12, max(5, effective_max_results // 2))`) and total Nigerian board dominance cap (`min(25, max(10, int(effective_max_results * 0.6)))`) when ATS queries are active, guaranteeing diverse board representation.
- **ATS Location Dork Relaxation**:
  - In `build_ats_query()` and `QueryBuilder.build_query_string()`, when `params.location` is a Nigerian location (`Nigeria`, `Lagos`, `Abuja`, `Port Harcourt`, `Ibadan`) and `params.remote` is not explicitly `False`, relaxed the ATS location token to `("Nigeria" OR "Lagos" OR "Remote" OR "EMEA")`.
  - Preserves exact location behavior for non-Nigerian queries or when strict on-site work is requested (`remote=False`).

### D. Playwright E2E Configuration (`playwright.config.js`)
- Locked `SERPER_MODE: process.env.SERPER_MODE || 'cache_only'` in `webServer.env` inside `playwright.config.js`.

---

## 3. Verification & Proof

- **Oxlint**:
  - 3 expected warnings (`react(only-export-components)` on UI primitives), 0 errors.
- **Vitest**:
  - 8 test files passed (59 tests passed), including new tests for `extractDomain` mailto parsing and `openPosting` dispatching.
- **Vite Build**:
  - `tsc -b && vite build` succeeded with 0 errors.
- **Pytest**:
  - 333 passed in full test suite (0 failures), including:
    - `test_hotnigerianjobs_single_detail_fixture_ab0275a4_extracts_clean_ashby_apply_url`
    - `test_hotnigerianjobs_single_detail_fixture_extracts_fields_without_duplication` (decodes `mailto:hr@avtne.com?subject=Chinese%20Translator`)
    - `test_hotnigerianjobs_roundup_detail_fixture_unbundles_all_positions`
    - `test_hotnigerianjobs_apply_url_blocklist_rejects_disallowed_links`
    - `test_nigerian_location_relaxed_for_ats_queries`
    - `test_orchestrator_balanced_mix_nigerian_scrapers_do_not_cancel_pending_ats`
- **Playwright E2E**:
  - 30 passed (1 worker, 1.3m) with webServer in `cache_only` mode.
- **Serper Budget Integrity**:
  - Before: `[('2026-10-28', 36)]`
  - After: `[('2026-10-28', 36)]`
  - Credits spent: **0**.
