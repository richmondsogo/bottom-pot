# Step 26: Live Bug Fixes (Batch A)

- **PR**: https://github.com/richmondsogo/bottom-pot/pull/31
- **Branch**: `step/26-live-bugfixes`
- **First Commit SHA**: `36e561df4f4591323b0810b2471fb9df7a6f80cc`
- **Last Commit SHA**: `43be02d4edfb9f6ee34f2cadc28cf975a4a64501`

## Context & Objectives
Address high-priority bug fixes identified in live smoke testing:
1. Ashby ATS site operator misconfiguration in `config.py` (`jobs.ashby.com` -> `jobs.ashbyhq.com`).
2. Lever client dropped `openingPlain` and `additionalPlain`, omitting vital job details and base salary ranges (e.g. Palantir postings).
3. Salary parser failed to normalize slash-prefixed periods (e.g. `/month`, `/mo`, `/yr`) due to leading `\b` before non-word `/` and alternation order `mo|month`.
4. Structured compensation extraction for Greenhouse (`pay_input_ranges`) and Ashby (`includeCompensation=true`).
5. Nigerian detail salary extraction routed through shared deterministic extractor; removal of ad-hoc card parsing regex.
6. Ashby direct apply link preference (`applyUrl` over `jobUrl`).

---

## Commit Log

### Commit 1: `fix(config): correct Ashby ATS site operator to jobs.ashbyhq.com` (`4dee824`)
- **Problem**: `config.py` set Ashby `site_operator` to `jobs.ashby.com`. The domain does not resolve via DNS; Ashby's actual hosted career board domain is `jobs.ashbyhq.com`. This caused all Serper searches for Ashby jobs to return 0 results.
- **Fix**: Updated `ATS_PLATFORMS` entry for `ashby` to `site_operator="jobs.ashbyhq.com"`.
- **Regression Test**: Added assertion `assert ATS_DOMAINS["ashby"] == "jobs.ashbyhq.com"` in `tests/test_query_builder.py`. Failed first with `AssertionError: assert 'jobs.ashby.com' == 'jobs.ashbyhq.com'`.
- **Live Verification**:
  - Outbound Serper query `site:jobs.ashbyhq.com "Software Engineer"` returned 5 live job postings (e.g. `https://jobs.ashbyhq.com/candidhealth/f770bdc1-6704-44c6-9417-b98c1a4c75c4`).

### Commit 2: `fix(salary_parser): normalize slash-prefixed pay periods and prioritize month over mo` (`36e561d`)
- **Problem**:
  1. `_PERIOD_PATTERNS` in `src/project_files/salary_parser.py` had a leading `\b` before `/`. Because `/` is a non-word character, `\b/` required a preceding word character, causing `normalize_period("/mo")` and `normalize_period("/yr")` to fail.
  2. `_RANGE_REGEX` and `_SINGLE_REGEX` had alternation `mo|month`, which greedily matched `/mo` on `...$10,500/month`, leaving `nth` unconsumed and passing `/mo` to `normalize_period`.
- **Fix**:
  - Removed leading `\b` on slash-prefixed patterns in `_PERIOD_PATTERNS`.
  - Swapped `mo|month` to `month|mo` in `_RANGE_REGEX` and `_SINGLE_REGEX`.
- **Regression Test**:
  - Added `test_pay_period_normalization_slash_and_word_variants` in `tests/test_salary_parser.py` verifying `/month`, `/mo`, `/yr`, `/year`, `/hr`, `per month`, and no-period staying `None`. Failed first (`assert None == 'month'`). Passed after fix.
- **Suite & Golden Diff**:
  - 541 backend pytest tests passed. 89 Vitest unit tests passed. 0 golden files modified (all had `period: null` or no salary).

### Commit: `fix(ats): include Lever opening and additional sections in description` (`1ec5f67`)
- **Problem**: `LeverClient.fetch_result` assembled only `descriptionPlain` and `lists`, dropping `openingPlain` and `additionalPlain`. In Palantir postings, salary ranges (e.g. `$5,900 - $10,500/month` or `$60,000 - $97,000/year`) and introductory details are stored in `additionalPlain` and `openingPlain`.
- **Real Palantir Lever Payload (Redacted)**:
  - Role: `Administrative Business Partner - ShipOS` (`a237973c-cb29-41fe-9c80-416e6f42e087`)
  - `additionalPlain`:
    ```
    Salary
    The estimated salary range for this position is estimated to be $60,000 - $97,000/year. Total compensation for this position may also include Restricted Stock units, sign-on bonus and other potential future incentives...
    ```
  - Intern Role:
    ```
    Salary
    The salary range for this position is estimated to be $5,900 - $10,500/month...
    ```
- **Fix**: Updated `LeverClient` in `src/project_files/ats_api_client.py` to assemble `openingPlain`, `descriptionPlain`, `lists`, and `additionalPlain`.
- **Regression Test**: Added `test_lever_client_includes_opening_and_additional_sections_and_extracts_salary` in `tests/test_scrapers_and_clients.py`. Failed first with `AssertionError: assert 'At Palantir' in ...`. Passed after fix.

### Commit 3: `fix(ats): extract Greenhouse and Ashby structured compensation with tier agreement` (`aa15bf2`)
- **Problem**:
  1. `GreenhouseClient` did not pass `?pay_transparency=true`, so the Greenhouse API never returned `pay_input_ranges`.
  2. `parse_structured_salary` expected `currency` and `period` keys in `pay_input_ranges`, but real Greenhouse payloads use `currency_type` and do not include any period key. The old mapping never functioned on real payloads.
  3. Period must never default to "year". Period must be inferred only from `title` (e.g. "Annual Base Salary Range:", "Hourly Base Pay Range:") or unambiguous `blurb`; otherwise `None`.
  4. Non-base compensation ranges (bonus, equity, commission, ote, quota) must be excluded by `title`.
  5. `AshbyClient` did not pass `?includeCompensation=true`, omitting `compensation` from API responses.
  6. Ashby multi-tier jobs with differing salary ranges across tiers (e.g. NY/SF $180k-$230k vs Nationwide $160k-$215k) must evaluate to `salary = None` across the full pipeline; fallbacks like `compensationTierSummary` or description label scanning must not reintroduce an ambiguous salary.
- **Real Greenhouse Payload (Redacted)**:
  - Board: `reddit`, Job ID: `8282760`, Title: `Analytics Engineer`
  - *(Note: An earlier preliminary exploration sample that cited a different title was replaced as unreliable; this is the verified live single-job payload from `/jobs/8282760?pay_transparency=true`.)*
  - `pay_input_ranges`:
    ```json
    [
      {
        "min_cents": 16420000,
        "max_cents": 22999000,
        "currency_type": "USD",
        "title": "The base salary range for this position is:",
        "blurb": "<p>In addition to base salary, this job is eligible to receive equity...</p>"
      }
    ]
    ```
  - Note on fallback keys: `parse_structured_salary` reads `currency_type` (fallback `currency`) and `r.get("period") or r.get("interval") or title`. If no period is stated, it checks `blurb` only if it matches exactly one unambiguous period keyword; otherwise `period` remains `None`. No period can ever be produced without literal textual evidence.
- **Real Ashby Payload (Redacted)**:
  - Board: `ramp`, Job ID: `b9568fb8-a47e-4738-87fb-a6d88c3a505f`, Title: `Account Manager | Commercial`
  - `compensation.compensationTiers`:
    - Tier 1 (`NY/SF`): Salary $180,000 - $230,000 USD / 1 YEAR
    - Tier 2 (`Nationwide`): Salary $160,000 - $215,000 USD / 1 YEAR
    - Differing tiers $\to$ Disputed $\to$ `salary = None`.
  - Cost: 48 out of 170 Ramp jobs have differing multi-tier ranges and evaluate to `salary = None`. 115 Ramp jobs have single-tier or agreeing ranges and successfully resolve salary.
- **Fix**:
  - Appended `?pay_transparency=true` to `GreenhouseClient` job request URL.
  - Appended `?includeCompensation=true` to `AshbyClient` board request URL.
  - Updated Greenhouse structured parsing in `salary_parser.py`: read `currency_type`, cents / 100, exclude non-base by `title`, resolve period from `title` or unambiguous `blurb` or `None`. Differing base ranges mark salary as disputed.
  - Updated Ashby structured parsing in `salary_parser.py`: inspect `compensationTiers` Salary components; if tiers agree, return salary; if tiers differ, mark as disputed.
  - Guarded `extract_salary`: when structured compensation is disputed, return `None` immediately without checking raw fields or scanning description labels.
- **Regression Tests**: Added 6 tests in `tests/test_salary_parser.py` and 2 tests in `tests/test_scrapers_and_clients.py`. All failed first; all pass after fix.

### Commit 5a: `fix(ats): prefer Ashby applyUrl over jobUrl for direct application link` (`5e8916b`)
- **Problem**: `AshbyClient` extracted `jobUrl` as `apply_url`. On Ashby boards, `jobUrl` links to the job description page (e.g. `https://jobs.ashbyhq.com/ramp/[uuid]`), while `applyUrl` links directly to the application form (e.g. `https://jobs.ashbyhq.com/ramp/[uuid]/application`).
- **Fix**: Updated `AshbyClient.fetch_raw_result` to prefer `applyUrl or jobUrl or parsed.raw_url`.
- **Regression Test**: Added `test_ashby_client_prefers_apply_url_over_job_url` in `tests/test_scrapers_and_clients.py`. Failed first (`assert jobUrl == applyUrl`); passed after fix.
- **Golden Snapshot Update**: Updated `tests/fixtures/golden/ashby_d3bc1ced.json` `apply_url` to `https://jobs.ashbyhq.com/linear/d3bc1ced-3ce4-4086-a050-555055dbb1ff/application` to reflect the authentic `applyUrl` present in `linear_board.json`.

### Commit 5b: `fix(ats): support Ashby /application URLs and verify order-independent deduplication` (`9e75588`)
- **Problem**: `_ASHBY` in `src/project_files/ats_url_parser.py` required the URL to end with the job UUID. If a candidate or API result provided a direct application link with `/application`, `parse_ats_url` returned `None`.
- **Fix**: Updated `_ASHBY` regex pattern to `rf"^https?://jobs\.ashby(?:hq)?\.com/([^/?#]+)/({_UUID_RE})(?:/application)?/?$"`.
- **Real Redacted URLs**:
  - Ashby (Ramp):
    - Posting URL: `https://jobs.ashbyhq.com/ramp/b9568fb8-a47e-4738-87fb-a6d88c3a505f`
    - Apply URL: `https://jobs.ashbyhq.com/ramp/b9568fb8-a47e-4738-87fb-a6d88c3a505f/application`
  - Lever (Palantir):
    - Posting URL: `https://jobs.lever.co/palantir/a237973c-cb29-41fe-9c80-416e6f42e087`
    - Apply URL: `https://jobs.lever.co/palantir/a237973c-cb29-41fe-9c80-416e6f42e087/apply`
- **Deduplication & Visited State**:
  - Serper search results returning `/application` now parse cleanly as valid ATS URLs and match the canonical ATS identity.
  - Dedup verified in both arrival orders (Serper snippet first vs API first) in `test_ashby_application_and_posting_url_deduplication_both_orders`: both orders resolve to the single authentic API listing and preserve the direct `apply_url`.
  - When users click the direct application link in the UI, browser `:visited` state correctly tracks the actual link they applied on.
- **Regression Tests**:
  - `tests/test_ats_url_parser.py`: `test_ashby_application_url_accepted` and `test_ashby_other_suffix_rejected`.
  - `tests/test_conservative_deduplicator.py`: `test_ashby_application_and_posting_url_deduplication_both_orders`.

### Commit 4: `fix(scrapers,salary): route authentic detail salary through shared extractor and remove ad-hoc card regexes` (`6346166`)
- **Problem**:
  1. HotNigerianJobs single-position detail pages (e.g. `dddf2c5a.html`, Chinese Translator) contained authentic salary text formatted as Markdown (`**Salary**\n\nN400,000 - N500,000 per month`). The shared label pattern in `extract_salary` required `:` or `is`, failing to match Markdown bold headers or colon-less labels.
  2. Nigerian scrapers (`JobbermanScraper`, `MyJobMagScraper`, `NgCareersScraper`, `_extract_card_metadata`) had ad-hoc card parsing regexes that performed free-text scanning on card snippets. Furthermore, in `_extract_card_metadata`, the regex only recognized ASCII `-` as a range delimiter, which truncated ranges containing Unicode en-dash `–` (U+2013) (e.g. `a5c6899a.html` `Salary: N2,000,000 – N5,000,000 monthly` was truncated to `2000000 / None`).
- **Fix**:
  - Updated shared `label_match` in `src/project_files/salary_parser.py`:
    `rf"(?:salary(?:\s+compensation)?|compensation|pay\s*range|base\s*pay)[*_]*\s*(?:(?:[^\n\r:.]*?(?::|\bis\b))|(?={_CURR_SYMBOLS}))\s*([^\n\r<.]+)"`
    Supports colon/is separators, Markdown emphasis `[*_]*`, and lookahead to currency symbols without colon.
  - Removed ad-hoc card regexes in `nigerian_scrapers.py`: only discrete DOM badges or explicit `\bSalary\s*:\s*([^\n\r<.]+)` labels are parsed.
  - Un-truncated salary text passes to central `extract_salary`, which already supports `[-–—]` in `_RANGE_REGEX`.
- **Scope & Measurement Notes**:
  - **MyJobMag**: Has zero real HTML fixture files in `tests/fixtures/real/` and is unmeasured on real fixtures. Its only test uses inline synthetic HTML.
  - **`dddf2c5a.html` Apply URL**: Uses a `mailto:` link extracted from the detail page (`mailto:hr@avtne.com?subject=Chinese%20Translator`). This is pre-existing publisher behavior, not altered here.
  - **Funding Guard**: Inputs like `"Compensation\n\n$50M Series B"` return `None` because of the parser's funding guard (`_FUNDING_PATTERNS`), not because the lookahead fails.
  - **`a5c6899a.html` En-Dash**: The literal file contains UTF-8 `\xe2\x80\x93` (`–`). The old card regex truncated at the en-dash and dropped `monthly`; the new code extracts the full range `(2000000, 5000000, 'month')`.
  - **`teamtailor/d93e9876.html` Behavior Change**: Under the new shared label pattern, `teamtailor/d93e9876.html` now parses `EUR 4,500 - 7,000` from `Monthly gross salary €4,500-7,000 based on experience and impact.` Period is `None` because `_RANGE_REGEX` does not infer period from prefix words like "Monthly" without an explicit period suffix or keyword. No golden file covers `d93e9876.html` (only `7fc22ed2.html` has a golden snapshot).
  - **Known Gap**: The badge selector regex `(?:NGN|₦|[$£€]|N\s*\d)` with `re.IGNORECASE` was already on `main` since Step 22b. It lacks a word boundary before `N`, meaning text like `"Min 3 years"` inside a badge can match. Left unchanged here to preserve stability.
- **Regression Tests**:
  - `tests/test_salary_parser.py`: `test_extract_salary_label_pattern_positives_and_negatives` asserting positives and negatives ("Salary Negotiable", "Salary Not disclosed", "Salary NA", "Salary Nil", "Salary Competitive", "Salary and benefits", "salary 401k", "Compensation 2 weeks", "Compensation\n\n$50M Series B", bare "N" disambiguation).
  - `tests/test_scrapers_and_clients.py`:
    - `test_hotnigerianjobs_detail_path_extracts_salary_from_fixture`: asserts full scraper detail path extracts `NGN 400,000 - 500,000 / month` from `dddf2c5a.html`.
    - `test_hotnigerianjobs_en_dash_salary_range_pinned_a5c6899a`: pins `(2000000, 5000000, 'month')` for row 4 in `a5c6899a.html`.

### Commit: `fix(tests): freeze models clock in test_myjobmag_golden_replay to stabilize freshness label` (`1c6ff04`)
- **Problem**: `test_myjobmag_golden_replay` in `tests/test_scrapers_and_clients.py` replayed against `tests/fixtures/golden/myjobmag_representative.json` with hardcoded posting date `13 October`. When generated, elapsed time was 14–20 days (`"2 weeks ago"`). On Nov 3, 2026, 21 days elapsed, causing `format_freshness` to return `"3 weeks ago"`, failing on `main`.
- **Fix**: Wrapped `results = await scraper.search(...)` and `model_dump_json()` in `test_myjobmag_golden_replay` with `patch("src.project_files.models.datetime")` frozen to `datetime(2026, 11, 1, 14, 0, 0, tzinfo=timezone.utc)` (19 days elapsed), matching the Step 25b frozen clock mechanism and reproducing `"2 weeks ago"` without editing the golden JSON or skipping `freshness_label`.

---

## Known Gaps & Operational Notes

1. **Greenhouse Salaries Without Stated Period**:
   - Greenhouse `pay_input_ranges` payloads provide `currency_type`, `min_cents`, and `max_cents`, but omit any period key.
   - For boards like Reddit and Pinterest, job titles ("The base salary range for this position is:") and blurbs do not state an explicit period ("annual", "year", "hour", etc.).
   - Following ADR 0001 (unknown beats wrong), `period` remains `None`. It never defaults to `"year"`.
2. **Ramp Tier Disagreement (48/170 Jobs Without Salary)**:
   - On Ashby boards with geographic/tier compensation structures (e.g. Ramp), 48 of 170 jobs have differing salary ranges across tiers (e.g. NY/SF $180k-$230k vs Nationwide $160k-$215k).
   - Under the disagreement guard, these evaluate strictly to `salary = None` across the entire pipeline; neither `compensationTierSummary` nor description label scanning is allowed to guess or reintroduce an ambiguous single range.
3. **MyJobMag Unmeasured on Real Fixtures**:
   - There are zero real HTML fixture files for MyJobMag in `tests/fixtures/real/` (only Jobberman and HotNigerianJobs have real fixture HTML).
   - MyJobMag is covered only by synthetic inline HTML and golden replay, remaining unmeasured against live production DOM variations.
4. **Pre-existing Badge Regex Gap**:
   - The badge selector regex `(?:NGN|₦|[$£€]|N\s*\d)` with `re.IGNORECASE` (introduced in Step 22b commit `719b8249`) lacks a word boundary before `N`.
   - Text like `"Min 3 years"` occurring inside a badge element can match the `N\s*3` alternation. Left unchanged in this batch to preserve scraping stability.
5. **Cached 24h Salaries in SQLite**:
   - Existing URL enrichments and search responses cached in `data/cache.sqlite` (`URL_CACHE_TTL_HOURS = 24`) will retain their previous salary parse values until TTL expiry.
   - Live environments can flush `data/cache.sqlite` or wait 24 hours for all enriched postings to transition to the new structured extraction pipeline.




