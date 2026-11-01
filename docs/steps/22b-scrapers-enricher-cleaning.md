# Step 22b: Nigerian Scrapers, Generic Enricher & JSON-LD, Description Cleaning

Initiative: **Extraction Pipeline & Architecture Overhaul**  
Role: **Planner / Builder**  
Branch: `step/22b-scrapers-enricher-cleaning`  
Date: 2026-11-01  
Status: **In Progress**  

---

## 1. Scope & Provider Checklist

Migrate Nigerian scrapers, generic ATS page enricher, JSON-LD extraction, and DOM/snippet fallback paths to yield `RawJobPosting` acquisition envelopes and canonicalize via `JobExtractionService`. Centralize idempotent HTML-to-Markdown description cleaning. Extend `salary_parser.py` with Nigerian adapter hints and currency disambiguation rules.

### Scraper & Enricher Checklist
- [x] Initial fixtures & tests committed (synthetic short description, Workable check, 22b golden baseline)
- [x] Currency `$` rule fix: USD only when no other dollar-currency signal is present, otherwise `None`
- [x] Centralized idempotent description cleaner (`to_markdown` / `clean_description`) preserving headings, lists, links, tables, and stripping noise/AdSense
- [x] Shared salary parser extensions: Nigerian adapter hint (`bare_n_is_ngn`), strict `m` suffix rule, rejection of "Negotiable"/"attractive"
- [x] JSON-LD structured extraction in `JobExtractionService` (`jobLocationType`, `applicantLocationRequirements`, `baseSalary`, `datePosted`, `employmentType`)
- [x] Provider: Jobberman (`JobbermanScraper`)
- [x] Provider: MyJobMag (`MyJobMagScraper`)
- [ ] Provider: NgCareers (`NgCareersScraper`)
- [ ] Provider: HotNigerianJobs (`HotNigerianJobsScraper`)
- [ ] Generic Enricher: Workday CXS
- [ ] Generic Enricher: JSON-LD (JazzHR, Teamtailor, Jobvite)
- [ ] Generic Enricher: Personio embedded JSON
- [ ] Generic Enricher: Fallback snippet rows & circuit breaker handling
- [ ] Vitest test cases: Nigerian salary object (NGN, month), null currency, legacy string, sorting
- [ ] Golden replay comparison & documentation of intentional diffs
- [ ] Verification suite (`scripts/verify.ps1`, full `pytest`, Vitest, Playwright)

---

## 2. Pre-Checks Findings

1. **`git status` on `main`**: Verified clean, 0 untracked files or stray scripts before branching.
2. **Short Authentic Description Fixture (<300 chars)**: Added `tests/fixtures/synthetic/greenhouse_short_authentic_desc.json` (labelled "synthetic, not live-verified") and updated `test_short_authentic_description_classifies_work_model_via_client` to load from this fixture file.
3. **Structured Salary Audit (Greenhouse & Workable)**:
   - **Greenhouse**: Real fixture `job_8860302002.json` contains no `pay_input_ranges`. Public Greenhouse API docs indicate `pay_input_ranges` (with `min_cents`/`max_cents`) is emitted only when companies enable pay transparency. This path is tested via `test_structured_greenhouse_cents_documentation_derived` (labelled "documentation-derived, not live-verified").
   - **Workable**: Inspection of real fixture `job_D94DBAF102.md` and public Workable API/Jina markdown endpoints confirms Workable does not expose a structured salary JSON object or dedicated request parameter. No synthetic fixture was invented.
4. **Salary Parsing Outside `salary_parser.py`**:
   - `src/project_files/nigerian_scrapers.py`: Lines 105, 111, 1304 contained ad-hoc regexes dumping unparsed strings into `JobListing.salary`.
   - `src/project_files/ats_page_enricher.py`: 0 salary extraction (previously ignored).
   - `src/project_files/field_normalizer.py`: 0 salary parsing.
5. **Currency `$` Disambiguation Rule**:
   - Pre-fix: When `_OTHER_DOLLAR_SIGNALS` matched (e.g. `location_hint="Toronto, Canada"` with `$`), code mapped `$` to `"CAD"`, asserting `"CAD"` in tests.
   - Spec Correction: Per ADR 0001, bare `$` in the presence of Canadian/Australian context is ambiguous between USD and the local currency; it must resolve to `USD` only when no other dollar signal is present, and otherwise `None`. Explicit `CA$` / `AU$` remain `CAD` / `AUD`.

---

## 3. Intentional Diffs & Output Ledger

| Fixture / Provider | Field | Old Value (`main`) | New Value (Step 22b) | Rationale |
|---|---|---|---|---|
| `test_dollar_currency_disambiguation_and_symbol_rules` | `currency` for `("$100k - $120k / yr", "Toronto, Canada")` | `"CAD"` | `None` | Spec correction: bare `$` with competing dollar signal is ambiguous (ADR 0001). |
| `lever_caadac8e.json` | `description` | `**grow** .` | `**grow**.` | Cleaner removes ungrammatical whitespace before punctuation after bold markdown tags. |
| `smartrecruiters_744000155969710.json` | `description` | `**Conti** ,` / `**você** !` | `**Conti**,` / `**você**!` | Cleaner removes whitespace between bold markdown tags and subsequent punctuation. |
| `smartrecruiters_744000155937924.json` | `description` | Non-breaking spaces `\xa0` / bold spacing | Normalized spaces / tightened punctuation | Cleaner normalizes NBSP to ASCII space and tightens punctuation. |
| `recruitee_2774909.json` | `description` | `**Requirements:** \n` | `**Requirements:**\n` | Cleaner trims trailing spaces before newlines on bold headings. |
| `test_table_driven_positive_salary_cases` | `currency` for `"₦500,000 per month"` | `None` | `"NGN"` | `₦` symbol universally mapped to `NGN` in Step 22b. |
| `jobberman_03dbf68a.json` | `salary` | `"NGN 400,000 - 600,000"` | `{"minimum": 400000, "maximum": 600000, "currency": "NGN", "period": null, "raw_text": "NGN 400,000 - 600,000", "source": "jobberman_salary"}` | Wire compatibility: Nigerian jobs emit structured `JobSalary` object. |
| `jobberman_03dbf68a.json` | `raw_workplace_type` | `null` | `"Remote (Work From Home)"` | Captured from badge to preserve provenance of `work_model` classification. |

---

## 4. Verification Suite Results

*(To be recorded upon completion of Step 22b)*

---

## 5. Provenance & Git Tracking

*(To be recorded upon PR merge)*
