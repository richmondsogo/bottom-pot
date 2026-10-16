# Bottom Pot Agent Instructions

## Mission

Bottom Pot is a job discovery and scraping product focused on finding useful software and technology jobs, especially remote opportunities and opportunities relevant to Nigerian developers.

The product should prioritize:
- accurate job data
- reliable scraping
- excellent UX
- fast search
- transparent extraction confidence
- maintainable source-specific parsers

## Engineering Principles

- Inspect the existing code before changing it.
- Prefer fixing root causes over adding patches.
- Do not rewrite working systems without a reason.
- Do not introduce dependencies unless they solve a real problem.
- Reuse existing utilities and components.
- Keep changes focused and modular.
- Never silently change behavior that could break existing sources.
- Never fabricate scraped job data.

## Scraping

Job extraction must be treated as a pipeline:

discovery → fetching → extraction → normalization → validation → presentation

Prefer extraction in this order:

1. JSON-LD / Schema.org
2. ATS-specific extraction
3. Source-specific adapter
4. DOM/semantic extraction
5. LLM extraction
6. unknown / unavailable

Never use an LLM when deterministic structured data is available.

Support source-specific adapters where necessary, especially for Nigerian job sites and WordPress sites.

## Job Data

Prefer structured fields:

- title
- company
- location
- workMode
- salary
- employmentType
- description
- requirements
- postedAt
- applicationUrl
- source
- extractionConfidence

Never infer a field when the evidence is insufficient. Use unknown/null instead.

## Parser rules

1. Unknown beats wrong. No fallback may turn absence of evidence into a value.
2. Every derived field records source + evidence (a literal snippet).
3. The backend owns parsing. The frontend must never re-parse titles/snippets/descriptions.
4. Parser changes need a fixture from a real posting, not an invented one.

## Deep Scrape

Deep scraping may perform more expensive processing than normal discovery.

Deep scrape should be able to:
- render pages when necessary
- inspect JSON-LD
- inspect metadata
- inspect relevant DOM content
- identify source type
- use source-specific extraction
- use LLM structured extraction as a fallback
- validate extracted fields
- produce extraction confidence

## UI

The UI should feel:
- editorial
- minimal
- calm
- typography-first
- highly readable
- fast
- intentional

Prefer existing shadcn/ui components before creating custom equivalents.

Avoid:
- unnecessary gradients
- excessive rounded cards
- excessive shadows
- visual clutter
- arbitrary colors
- arbitrary spacing

Use Motion only where animation improves hierarchy, feedback, or interaction.

## Verification

Before declaring a task complete:

- run TypeScript/typecheck
- run lint
- run relevant tests
- run browser tests when UI behavior changes
- inspect the git diff
- verify existing functionality was not unnecessarily broken

## Agent Behavior

For significant tasks:

1. Investigate first.
2. Explain findings.
3. Create an implementation plan.
4. Wait for approval before major implementation.
5. Implement incrementally.
6. Verify the result.
7. Explain important architectural decisions.

Do not make large architectural changes without first presenting the plan.

## Configuration Knobs (Phase 5)

Bottom Pot provides configuration settings in `src/config.py` for cost control, caching, and network resilience:

- `SERPER_MODE`: `live` (default) or `cache_only`. In `cache_only` mode, the orchestrator never makes outbound Serper API calls, serving only cached responses or returning an empty result set if uncached.
- `SERPER_DAILY_BUDGET`: Maximum Serper requests allowed per UTC day (default: 200). Counter is persisted in `data/cache.sqlite` and resets automatically at UTC midnight. When reached, remaining Serper calls are skipped and `DoneEvent.budget_exhausted` is set to `true`.
- `SERPER_CACHE_TTL_HOURS`: TTL in hours for persistent Serper search query caching in SQLite (default: 12).
- `URL_CACHE_TTL_HOURS`: TTL in hours for per-URL job page enrichment cache in SQLite (default: 24).
- `SQLITE_DB_PATH`: Path to persistent cache database (default: `data/cache.sqlite`, gitignored).
- `GLOBAL_CONCURRENCY_LIMIT`: Global concurrency semaphore across all outbound page and API fetches (default: 20).
- `PER_HOST_CONCURRENCY_LIMIT`: Per-host concurrency semaphore (default: 3).
- `CIRCUIT_BREAKER_FAILURE_THRESHOLD`: Consecutive failure threshold to trip per-host circuit breaker (default: 5).
- `CIRCUIT_BREAKER_COOLDOWN_SECONDS`: Cooldown window before retrying a tripped host (default: 600s / 10 minutes).
- `MAX_RESPONSE_BYTES`: Maximum stream read size for remote pages before truncation (default: 3,145,728 bytes / 3 MB).
- `RATE_LIMIT_SEARCH`: SlowAPI rate limit for `/search` endpoint (default: `20/hour`).
- `IN_MEMORY_CACHE_MAX_ENTRIES`: LRU cap for in-memory whole-search cache (default: 100).

Before adding or creating a UI component, always check .\components.json to verify the path configurations. Use npx shadcn@latest add [component] to install standard shadcn primitives instead of writing them from scratch.