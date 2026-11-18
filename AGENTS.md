# Bottom Pot Agent Instructions & Operating Agreement

This document is the authoritative working agreement for any autonomous or human agent operating in this repository. Read it before touching anything.

---

## CRITICAL DATA SAFETY INVARIANT: OPERATIONAL DATABASE IS NEVER TEST DATA

1. **`data/cache.sqlite` and its backups are operational/user data**: Never treat `data/cache.sqlite`, `-wal`/`-shm`/`-journal` sidecars, `data/cache.sqlite.bak-*`, `data/.cache.sqlite.restore-staging-*`, or `subscriptions.csv` as test data.
2. **Fresh disposable databases only**: Every automated test (`pytest`), Playwright E2E run, temporary server, and disposable rehearsal must allocate and use a fresh disposable database in an isolated temporary directory (`OwnedDisposableWorkspace` / `tmp_path` / `playwright.config.js` `mkdtempSync`).
3. **Zero destructive or schema operations on operational data**: Never run migrations (`_ensure_db()`), cleanup (`unlink`/`rmtree`), deletion, WAL checkpointing, or destructive experiments against operational data or backups.
4. **Never trust inherited database environment variables**: Tests and E2E harnesses must unconditionally override or validate `SQLITE_DB_PATH`, `PLAYWRIGHT_SQLITE_DB_PATH`, `SUBSCRIPTIONS_FILE`, and `PLAYWRIGHT_SUBSCRIPTIONS_FILE` — never fall back to `data/cache.sqlite`, and never trust `TESTING=true` or `CI=true` to bypass path validation.
5. **Verify the effective database path first**: Before running any test, script, or server command that can write to SQLite, verify the effective `sqlite_db_path` resolves cleanly outside `data/`.
6. **Deny-by-default operational access**: Unknown scripts or ad-hoc processes inheriting `.env` are rejected even without test flags. Only documented production entry points in `DOCUMENTED_OPERATIONAL_ENTRYPOINTS` (`scripts/run_prod.ps1`, or CLIs explicitly passed `--allow-operational-db` / `BOTTOM_POT_ALLOW_OPERATIONAL_DB=1` outside test/E2E/CI contexts) may access `data/cache.sqlite`. `scripts/run_prod.ps1` restores or removes `BOTTOM_POT_ALLOW_OPERATIONAL_DB` on exit; never put `BOTTOM_POT_ALLOW_OPERATIONAL_DB=1` in `.env` or `.env.example`.
7. **Never delete backups, forensic artifacts, or unknown DB files**: Preserve all `data/cache.sqlite.bak-*`, `.cache.sqlite.restore-staging-*`, and unrecognized database files.
8. **Owned destructive targets only**: Destructive test cleanup requires a disposable fixture/workspace with explicit verified directory ownership (`safe_cleanup_disposable_path` / `tmp_path`) — never delete arbitrary paths passed via env vars or pattern matches.
9. **Fail closed on uncertainty**: If database isolation cannot be created, resolved, or verified, STOP immediately and report the blocker rather than proceeding.
10. **Passing tests alone do not prove safety**: Verify before and after sensitive/E2E runs that `data/cache.sqlite`, sidecars, backups, and preserved forensic artifacts keep identical byte sizes and SHA-256 hashes.

See [ADR 0030](docs/adr/0030-operational-sqlite-database-isolation-and-destructive-test-safety.md) and [`src/project_files/db_safety.py`](src/project_files/db_safety.py).

---

## 1. Order of Precedence

When instructions conflict, resolve them in this order:

1. **User instructions** in the active prompt (highest priority).
2. **`AGENTS.md` & `BUILD_PROTOCOL.md`** (Repository operating agreements & Build Protocol).
3. **`CONTEXT.md` & `DESIGN.md`** (Domain context and visual rules).
4. **Project-local skills** (`.agents/skills/`).
5. **Environment skills & general defaults** (lowest priority).

---

## 2. Methodology & Git Workflow

The standard 10-stage development methodology is defined in [`BUILD_PROTOCOL.md`](./BUILD_PROTOCOL.md):

```
Understand → Plan → Branch → Approve → Implement → Verify → Review diff → Record → PR & Review → Merge & Checkpoint
```

### Primary Branch Protection & Step Isolation

1. **Never commit directly to the primary branch**: The primary branch is `main`. Direct commits to `main` are strictly forbidden.
2. **Step Branches**: Every step operates on an isolated subbranch named `step/NN-<slug>` (or `chore/`, `feat/` as assigned).
3. **Merge Policy**: Default to `MERGE_POLICY`: open pull requests, do NOT merge them unless explicitly commanded ("merge when green"). Standard merge commits (`git merge --no-ff`) are used when landing to preserve granular commit history.
4. **Provenance Tracking**: Every completed step log in `docs/steps/` must record the PR URL, first commit SHA, last commit SHA, and merge commit SHA.

---

## 3. Mission & Product Principles

Bottom Pot is an ATS-first job discovery product focused on finding software and tech jobs, especially remote opportunities and roles relevant to Nigerian developers.

Priorities:
- Accurate job data without fabrication.
- Reliable, resilient scraping pipelines.
- Editorial, calm, typography-first UX with a strict square design system.
- Fast search response times via streaming SSE.
- Transparent extraction confidence and source evidence.
- Maintainable source-specific parsers.

---

## 4. Scraping & Extraction Pipeline

Job extraction must be treated as a progressive pipeline:

```
discovery → fetching → extraction → normalization → validation → presentation
```

Prefer extraction in this strict order:
1. JSON-LD / Schema.org structured metadata.
2. ATS-specific structured API / schema extraction.
3. Source-specific adapter (e.g. Jobberman, MyJobMag).
4. DOM / semantic extraction.
5. LLM structured extraction (fallback only).
6. Unknown / unavailable.

**Never use an LLM when deterministic structured data is available.**

### Parser Rules
1. **Unknown beats wrong (ADR 0001)**: No fallback may turn absence of evidence into an invented value. Missing fields remain `null` or `unknown`.
2. **Evidence tracking**: Derived fields record source + evidence (a literal snippet).
3. **Backend owns parsing (ADR 0003)**: The backend parses and normalizes titles, compensation, and snippets. The frontend must never re-parse or infer raw data.
4. **Real fixtures only**: Parser changes require a test fixture from a real posting, never synthetic/invented data.

---

## 5. Square Design System & UI Rules

- **Square Geometry is Non-Negotiable**: `--radius: 0` everywhere. No rounded cards, pills, circular avatars, or soft bubbles.
- **Palette**: Warm editorial cream (`#FAF8F5`), crisp white surfaces, deep forest green accent (`#1A382B`).
- **Typography First**: Large tight display typography (`text-wrap: balance`, tracking `-0.03em`), tabular figures for data columns, sentence case for UI labels. Reserve monospace for data, counts, codes, and metadata.
- **Chrome Discipline**: Avoid status bloat. Collapse status into a single quiet strip. Remove developer jargon ("GET /search", "SERPER CALLS").
- **Motion**: Restrained (120–180ms ease-out). No bouncy springs, parallax, or entrance stagger.

---

## 6. Configuration Knobs (`src/config.py`)

Bottom Pot provides configuration settings for cost control, caching, and network resilience:

- `SERPER_MODE`: `live` (default) or `cache_only`. In `cache_only` mode, the orchestrator never makes outbound Serper API calls.
- `SERPER_DAILY_BUDGET`: Maximum Serper requests allowed per UTC day (default: 200). Resets automatically at UTC midnight. When reached, `DoneEvent.budget_exhausted` is set to `true`.
- `SERPER_CACHE_TTL_HOURS`: TTL in hours for persistent Serper search query caching in SQLite (default: 12).
- `URL_CACHE_TTL_HOURS`: TTL in hours for per-URL job page enrichment cache in SQLite (default: 24).
- `SQLITE_DB_PATH`: Path to persistent cache database (`data/cache.sqlite`, gitignored).
- `GLOBAL_CONCURRENCY_LIMIT`: Global concurrency semaphore across all outbound page and API fetches (default: 20).
- `PER_HOST_CONCURRENCY_LIMIT`: Per-host concurrency semaphore (default: 3).
- `CIRCUIT_BREAKER_FAILURE_THRESHOLD`: Consecutive failure threshold to trip per-host circuit breaker (default: 5).
- `CIRCUIT_BREAKER_COOLDOWN_SECONDS`: Cooldown window before retrying a tripped host (default: 600s).
- `MAX_RESPONSE_BYTES`: Maximum stream read size before truncation (default: 3,145,728 bytes / 3 MB).
- `RATE_LIMIT_SEARCH`: SlowAPI rate limit for `/search` endpoint (default: `20/hour`).
- `IN_MEMORY_CACHE_MAX_ENTRIES`: LRU cap for in-memory whole-search cache (default: 100).

---

## 7. Verification Before Completion

Before declaring any task or step complete:

1. Run `.\scripts\verify.ps1` (validates git secrets, frontend lint, frontend typecheck/build, backend pytest, and Playwright e2e).
2. Run `git status` — confirm only intended files changed and no stray files remain.
3. Run `git diff` — read every line of the staged diff.
4. Verify browser rendering across 5 viewports (1920, 1440, 1024, 768, 390) and all states.
5. Record step log in `docs/steps/`.

---

## 8. Provider Discovery, Lifecycle & Repository Normalization

Every job board, ATS provider, remote-job feed, or external opportunity source considered for Bottom Pot must obey these lifecycle and repository normalization rules:

1. **Optimize for genuinely eligible jobs, not provider count**: Prioritize sources delivering fresh, relevant technical roles (internship, junior, entry-level, and experienced) that applicants in Nigeria and elsewhere in Africa can genuinely apply for—never adopt a source merely for API convenience, raw listing volume, or hype.
2. **Distinguish source types & prefer direct employer URLs**: Classify every candidate (`Employer ATS / career board`, `Regional technology job board`, `International remote-only board`, `Specialized programming or industry job board`, `General job aggregator`, `Talent marketplace or recruiting network`, or `Professional community or job-posting feed`). Prefer collecting original employer career-page URLs when direct monitoring improves freshness, description quality, and deduplication.
3. **Mandatory pre-implementation evaluation**: Before implementing any source, verify public access/authentication, official API/feed docs, explicit reuse/redistribution permission, attribution & original application-link requirements, description completeness, stable identity, pagination/empty-feed/closure semantics, HTTP limits/conditional requests, geographic/work-authorization restrictions, and incremental coverage. Never implement a source with unclear reuse rights.
4. **Normalize applicant eligibility**: Classify roles as `Eligible`, `Restricted`, or `Unverified` with retained evidence. Never infer worldwide eligibility from `is_remote=true`, generic remote labels, or international HQ locations.
5. **One provider at a time without weakening safety**: Each approved source receives its own bounded scope with strict validation, canonical identity, URL normalization, HTTP resilience, complete-snapshot closure safety, offline fixtures, and tests.
6. **Mandatory rejected-provider cleanup**: When an investigation concludes a source is `Unsuitable` (`Rejected`), audit the entire repository and remove active provider-specific configuration, URL regexes/parsers, canonical URL builders, normalizers, enrichers, routers, adapters, frontend platform entries, and active-inventory tests—without removing shared code used by other sources, historical step documents (`docs/steps/`), documented migration tables (`HISTORICAL_FULL_INVENTORIES`), or operational SQLite history (`data/cache.sqlite`).
7. **Maintain the source lifecycle catalog**: After every provider investigation, implementation, rejection, or retirement, update [`docs/job-source-catalog.md`](docs/job-source-catalog.md) and synchronize `README.md`, `CONTEXT.md`, tests, and step documentation before concluding.