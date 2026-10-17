# Bottom Pot Agent Instructions & Operating Agreement

This document is the authoritative working agreement for any autonomous or human agent operating in this repository. Read it before touching anything.

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