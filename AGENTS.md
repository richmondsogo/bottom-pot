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

Before adding or creating a UI component, always check .\components.json to verify the path configurations. Use npx shadcn@latest add [component] to install standard shadcn primitives instead of writing them from scratch.