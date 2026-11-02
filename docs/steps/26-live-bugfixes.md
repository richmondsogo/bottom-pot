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
