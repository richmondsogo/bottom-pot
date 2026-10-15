---
name: parser-change
description: Use whenever editing job parsing or extraction code in src/project_files (field_normalizer.py, work_model.py, ats_page_enricher.py, ats_url_parser.py, ats_api_client.py, nigerian_scrapers.py) or adding or changing tests for them.
---

# Parser Change Workflow

Use this skill whenever modifying, fixing, or adding extractors, scrapers, URL parsers, or normalizers in `src/project_files/`.

## Core Principles

Before writing any parsing code, ensure strict compliance with project principles:

1. **Unknown beats wrong:** No fallback may turn absence of evidence into a concrete value. If evidence is missing, ambiguous, or contradictory, return `None`.
2. **Provenance is mandatory:** Every derived field must record its source and a literal text evidence snippet.
3. **Backend owns parsing:** The frontend must never re-parse or regex-mutate titles, snippets, locations, or descriptions.
4. **Real fixtures only:** Parser changes must be backed by real posting fixtures captured from real web pages or API responses, never hand-invented synthetic HTML or payloads.
5. **Never weaken tests to pass:** If an existing test encodes old behavior, say so and explain why it changed. Never loosen or delete a test silently.
6. **No broad single-word patterns:** Avoid bare `remote`, `office`, `flexible`, `distributed`, `virtual`, `anywhere`. Require surrounding context and handle negation ("not remote", "not hybrid").

## Step-by-Step Workflow

### 1. Read the Architecture Decision Records (ADRs)
Always review the foundational ADRs before proposing or implementing changes:
- `docs/adr/0001-unknown-beats-wrong.md`
- `docs/adr/0002-work-model-source-ladder.md`
- `docs/adr/0003-backend-owns-parsing.md`

### 2. Capture Real Fixtures
Do not write tests against fabricated mock HTML. Capture the real page or API payload:

```bash
# Add target URL to urls.txt
python scripts/capture_fixtures.py
```

Fixtures are stored under `tests/fixtures/real/<provider>/<sha8>.html` with a sidecar `.json` metadata file.

If no real fixture exists for the case you are working on, stop and ask for a URL instead of inventing one.

### 3. Implement the Parser or Normalizer Change
- Inspect the captured fixture directly to identify the exact DOM structure, JSON-LD schema, or embedded JSON.
- Never add default fallbacks. For example, do not assume that a physical location, or `is_remote=False`, implies `in_person`.
- Maintain the source ladder order: API enums > JSON-LD > LI tags (#LI-*) > location tokens > title tokens > verified description scan.
- Never log or swallow parser exceptions silently. Use a `loguru` warning that includes the URL and the exception.

### 4. Add Automated Tests
Add test cases that load and assert against the real captured fixture, or against exact substrings copied from real job postings. Include at least one negative case (a text that looks like a match but must return `None`).

### 5. Evaluate Against Golden Labels
Run the evaluation script if the golden set exists (`tests/golden/work_model_labels.csv`):

```bash
python scripts/eval_work_model.py results.json
```
If the golden set does not exist, the script prints "no golden set, skipping" and exits 0.

### 6. Verify and Run the Test Suite
Run the full suite and make sure everything passes before committing or proposing changes:

```bash
pytest
```

### 7. Report
Reply with:
- files changed
- tests added
- existing tests modified, and why
- any rule above you could not follow
