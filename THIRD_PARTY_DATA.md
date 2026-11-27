# Third-Party Data & Test Fixture Inventory

This document catalogs every real third-party fixture dataset tracked under `tests/fixtures/real/`, its personal-data audit status, redistribution rationale, large-fixture justifications (`> 500 KB`), and secret-handling policy.

---

## 1. Personal-Data & Secret Audit Findings

1. **Email addresses in tracked fixtures:** Inspected across `tests/fixtures/real/`. Observed email addresses are employer role mailboxes (`accommodations@`, `security@`, `careers@`, `recruiting@`, `hr@`, `info@`, `personal@montana-energie.de`) and per-job ATS routing aliases (`job.xxxxx@miaplaza.recruitee.com`), not private personal email accounts of named individuals.
2. **Named individual URLs (`tests/fixtures/real/teamtailor/dotworld_rss.xml`):** Originally contained **11 personal LinkedIn profile URLs** (`33` URL occurrences) published inside the employer's public Teamtailor RSS feed (`dotworld_rss.xml`). Replaced with deterministic placeholders (`https://www.linkedin.com/in/redacted-profile-01/`..`11/`, `135.9 KB`), recorded with `modified: true` and SHA-256 digests in `tests/fixtures/real/teamtailor/manifest.json`.
3. **No secrets in git history or `.env.example`:** No `.env` file was ever committed, and `.env.example` / `frontend/.env.example` contain placeholder tokens only.

### Git History & Redaction Policy

- **No git history rewrite:** Bottom Pot does **not** rewrite git history for `dotworld_rss.xml`. The data was originally published openly by the employer, the exposure surface is small, and rewriting git history breaks PR links, clones/forks, and historical step cross-references in `docs/history/` without guaranteeing removal of existing copies.
- **Dedicated redaction PR:** The 11 personal LinkedIn URLs in `tests/fixtures/real/teamtailor/dotworld_rss.xml` were replaced with deterministic redacted placeholders in a dedicated owner-review PR without rewriting git history, recorded with `modified: true` in `tests/fixtures/real/teamtailor/manifest.json` and covered by parser tests. Other fixtures remain unredacted.
- **Secret rotation rule:** CI runs `python scripts/check_secrets.py` plus repository secret scanning on every pull request. If a real credential is ever committed, **revoke and rotate it immediately** at the provider—never rewrite git history.

---

## 2. Fixture Group Ledger (`tests/fixtures/real/`)

All fixtures below are real employer/ATS public responses captured solely for deterministic offline parser regression testing and conformance verification (`tests/conformance/`). Live test traffic is blocked by default (`tests/conftest.py`).

| Fixture Group | Source | Files | Total Size (KB) | Manifest Present | Personal Data Finding | Redistribution Position |
|---|---|---:|---:|---|---|---|
| `ashby` | Public Ashby posting API & board pages | 13 | 1,351.9 | No | Role mailboxes only (if present) | Public employer career JSON/HTML for offline parser tests; original apply URLs preserved |
| `avature` | Public enterprise Avature portals | 8 | 164.6 | No | None beyond role mailboxes | Offline HTML parser regression fixtures; source-only (non-monitored) |
| `bamboohr` | Public BambooHR career JSON | 1 | 1.3 | No | None beyond role mailboxes | Offline unit parser fixture; search/provisional only |
| `greenhouse` | Public Greenhouse Boards API v1 JSON | 33 | 760.2 | No | Role mailboxes only (if present) | Offline unit & date-parsing regression fixtures |
| `hotnigerianjobs` | Public HotNigerianJobs HTML listings | 12 | 1,230.8 | No | Role/recruiting contacts only | Offline Nigerian scraper & salary parser fixtures |
| `jobberman` | Public Jobberman HTML listings | 6 | 1,782.7 | No | Role/recruiting contacts only | Offline Nigerian scraper regression fixtures |
| `jobvite` | Public Jobvite career HTML pages | 6 | 311.8 | No | Role mailboxes only | Offline HTML parser fixtures; search/enrichment only |
| `lever` | Public Lever Postings API & HTML boards | 22 | 4,002.0 | No | Role mailboxes only (if present) | Offline API & HTML enricher regression fixtures |
| `myjobmag` | Public MyJobMag job detail HTML pages | 7 | 254.8 | Yes (`manifest.json`, `modified: true`) | Board/employer emails replaced with deterministic `[REDACTED_EMAIL_*]` placeholders; zero phone numbers or personal recruiter names | Offline MyJobMag detail extraction regression fixtures |
| `personio` | Public Personio XML feeds (`/xml` & `?language=en`) | 9 | 263.3 | No | Role mailboxes (`personal@` HR alias) | Offline bilingual XML parser & conformance fixtures |
| `pinpointhq` | Public Pinpoint `/postings.json` & detail HTML | 8 | 297.2 | Yes (`probe_census_manifest.json`) | Public S3 pre-signed OpenGraph asset query param only (expired) | Offline JSON/JSON-LD & conformance fixtures |
| `recruitee` | Public Recruitee `/api/offers/` JSON | 6 | 1,267.7 | No | Per-job ATS aliases (`job.*@*.recruitee.com`) | Offline API & conformance fixtures |
| `smartrecruiters` | Public SmartRecruiters v1 postings JSON | 13 | 501.2 | No | Role mailboxes only | Offline pagination, detail hydration & conformance fixtures |
| `step54_employers` | Direct verified employer snapshots (`monitors` census) | 12 | 6,254.1 | Yes (`evaluation_manifest.json`) | Role mailboxes only | Offline global eligibility & fresh-remote audit baseline |
| `step55_employers` | Direct verified employer snapshots (wave 2) | 13 | 6,857.5 | Yes (`evaluation_manifest.json`) | Role mailboxes only | Offline early-career & global eligibility audit baseline |
| `step56_employers` | Direct verified employer snapshots (wave 3) | 10 | 8,320.7 | Yes (`evaluation_manifest.json`) | Role mailboxes only | Offline freshness & global remote audit baseline |
| `teamtailor` | Public Teamtailor `/jobs.rss` & HTML job pages | 44 | 2,317.3 | Yes (`manifest.json`, `modified: true`) | `dotworld_rss.xml` 11 personal LinkedIn URLs (33 occurrences) redacted to `redacted-profile-01..11`; remaining files contain role mailboxes only | Offline RSS/HTML & conformance fixtures; `dotworld_rss.xml` redacted via dedicated owner-review PR without rewriting history |
| `workable` | Public Workable v1 widget & v2 job detail JSON | 21 | 283.9 | No | Role mailboxes only | Offline multi-city dedup, detail hydration & conformance fixtures |
| `workday` | Public Workday CXS JSON responses | 7 | 53.7 | No | None beyond role mailboxes | Offline Workday search/detail client fixtures |

*(Logo fallback visual testing in E2E/Vitest uses mocked routes or offline assertions; runtime Logo.dev requests go directly from user browsers only when a domain-restricted publishable `pk_*` token is configured, with no third-party images stored in git.)*

---

## 3. Justified Tracked Fixtures Exceeding the 500 KB Budget

Per `scripts/check_repo_hygiene.py` (`check_asset_size_budgets`), no tracked fixture or image above `500 KB` may exist without an explicit entry below explaining why truncation would invalidate the parser or census test.

| Fixture Path | Size | Justification |
|---|---:|---|
| `tests/fixtures/real/step56_employers/greenhouse_coinbase.json` | 2,725.1 KB | Full single-GET Greenhouse board snapshot validating early-career/intern eligibility & freshness census (`evaluation_manifest.json`) |
| `tests/fixtures/real/step55_employers/greenhouse_affirm.json` | 2,437.0 KB | Full Greenhouse board snapshot verifying US/UK early-career role extraction (`evaluation_manifest.json`) |
| `tests/fixtures/real/step56_employers/ashby_cohere.json` | 2,219.1 KB | Full Ashby board payload validating multi-country AI internship & remote eligibility (`evaluation_manifest.json`) |
| `tests/fixtures/real/step54_employers/greenhouse_grafanalabs.json` | 2,046.9 KB | Full Greenhouse board snapshot covering 138 postings across US/CA/GB/DE remote scopes (`evaluation_manifest.json`) |
| `tests/fixtures/real/step56_employers/ashby_elevenlabs.json` | 1,726.8 KB | Full Ashby board snapshot proving explicit worldwide remote extraction (`evaluation_manifest.json`) |
| `tests/fixtures/real/step55_employers/ashby_kraken.com.json` | 1,509.6 KB | Full Ashby payload testing `secondaryLocations` multi-country remote extraction (`evaluation_manifest.json`) |
| `tests/fixtures/real/step55_employers/greenhouse_lyft.json` | 1,408.9 KB | Full Greenhouse snapshot validating US/CA internship extraction (`evaluation_manifest.json`) |
| `tests/fixtures/real/step54_employers/ashby_supabase.json` | 1,044.2 KB | Full Ashby board snapshot validating worldwide remote & AMER/EMEA/APAC scoping (`evaluation_manifest.json`) |
| `tests/fixtures/real/lever/board_zoox.html` | 899.6 KB | Real full-board Lever HTML used in board identity & logo extraction tests |
| `tests/fixtures/real/step54_employers/ashby_m-kopa.json` | 880.6 KB | Full Ashby board snapshot validating Africa/UK hybrid/remote hub splitting (`evaluation_manifest.json`) |
| `tests/fixtures/real/step54_employers/lever_spotify.json` | 848.3 KB | Full Lever board array verifying UK/EU/US streaming engineering extraction (`evaluation_manifest.json`) |
| `tests/fixtures/real/lever/html_42be630d.html` | 711.2 KB | Captured full Lever job detail HTML page verifying DOM description & eligibility parsing |
| `tests/fixtures/real/lever/html_1cb2b7f2.html` | 710.4 KB | Captured full Lever job detail HTML page paired with `api_1cb2b7f2` tests |
| `tests/fixtures/real/lever/html_9176aa65.html` | 706.7 KB | Captured full Lever job detail HTML page verifying structured extraction invariance |
| `tests/fixtures/real/lever/board_tpgsi.html` | 703.0 KB | Captured full Lever board HTML verifying logo & identity coercion tests |
| `tests/fixtures/real/step56_employers/ashby_sentry.json` | 643.6 KB | Full Ashby board payload validating Vienna/US early-career roles (`evaluation_manifest.json`) |
| `tests/fixtures/real/jobberman/38371977.html` | 638.6 KB | Real Jobberman search/listing DOM capture testing HTML scraper extraction |
| `tests/fixtures/real/jobberman/a3b49d05.html` | 609.1 KB | Real Jobberman DOM capture testing salary/location extraction |
| `tests/fixtures/real/teamtailor/7fc22ed2.html` | 551.0 KB | Real Teamtailor job page HTML testing DOM & JSON-LD fallback extraction |
| `tests/fixtures/real/jobberman/03dbf68a.html` | 534.1 KB | Real Jobberman DOM capture testing pagination & relative date parsing |
