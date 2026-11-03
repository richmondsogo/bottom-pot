# Step 26: Live Bug Fixes (Batch A)

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

### Commit 5b: `fix(ats): support Ashby /application URLs and verify order-independent deduplication` (`9e75588`)
- **Problem**: `_ASHBY` in `src/project_files/ats_url_parser.py` required the URL to end with the job UUID. If a candidate or API result provided a direct application link with `/application`, `parse_ats_url` returned `None`.
- **Fix**: Updated `_ASHBY` regex pattern to `rf"^https?://jobs\.ashby(?:hq)?\.com/([^/?#]+)/({_UUID_RE})(?:/application)?/?$"`.
- **Regression Tests**:
  - `tests/test_ats_url_parser.py`: `test_ashby_application_url_accepted` and `test_ashby_other_suffix_rejected`.
  - `tests/test_conservative_deduplicator.py`: `test_ashby_application_and_posting_url_deduplication_both_orders` verifying both arrival orders (Serper snippet first vs API first) deduplicate into a single authentic record preserving direct apply URL.

