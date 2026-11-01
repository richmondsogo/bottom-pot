# ADR 0025: Shared Extraction and Normalization Pipeline

## Status

Proposed

## Context

Today, job data ingestion is fragmented across three distinct subsystems with redundant, divergent, and inconsistent normalization logic:

1. **Dedicated ATS API Clients** (`src/project_files/ats_api_client.py`): 7 clients (Greenhouse, Lever, Ashby, SmartRecruiters, Workable, BambooHR, Recruitee). Each client independently parses raw JSON or HTML payloads, makes ad-hoc date parsing calls, extracts descriptions differently, and re-implements work-model parameter mapping.
2. **Generic ATS Page Enricher** (`src/project_files/ats_page_enricher.py`): Extracts data from 11+ platforms (Workday, Jobvite, SAP, Personio, JazzHR, Taleo, etc.) using JSON-LD, meta tags, and DOM selectors. It features platform-specific regex parsing branches and custom fallback logic.
3. **Nigerian Scrapers** (`src/project_files/nigerian_scrapers.py`): 4 scrapers (Jobberman, MyJobMag, NGCareers, HotNigerianJobs) that directly parse HTML, run custom regexes for salary, and instantiate `JobListing` objects with ad-hoc work-model parameters.

Because each provider creates `JobListing` directly, critical domain rules are bypassed or inconsistently applied:
- Some providers call `strip_li_tags` before converting markdown; others do not.
- Some providers pass raw strings as `workplace_type`; others synthesize pseudo-enums from boolean flags.
- Date parsing varies: some reimplement `datetime.fromisoformat`, some use timestamp division, some use `parse_datetime`, and some fall back to `updated_at`.
- None of the ATS API clients or generic enrichers pass descriptions to `resolve_work_model` for keyword scanning, while Nigerian scrapers hardcode `description_ok=True`.

## Decision

We will decouple **Data Acquisition** (fetching raw data) from **Extraction and Normalization** (parsing, standardizing, and validating fields).

Specifically:
1. Provider adapters (`ats_api_client.py`, `ats_page_enricher.py`, `nigerian_scrapers.py`) will have a single responsibility: fetch the raw source payload (JSON or HTML) and package it into an immutable raw extraction container (`RawJobPosting` or `RawExtractionResult`).
2. A centralized `JobExtractionService` (or `CanonicalJobPipeline`) will own all normalization and validation:
   - Structured JSON-LD / schema metadata extraction.
   - ATS-specific structured field normalization.
   - Centralized work-model resolution via `resolve_work_model`.
   - Centralized salary parsing into `JobSalary`.
   - Centralized Markdown description conversion and quality verification.
   - Centralized ISO 8601 UTC date parsing with strict rejection of update timestamps as posting dates.
   - Provenance tracking: recording exact extraction method, raw snippet evidence, and validation status per field.
3. Provider modules will not import or call normalization logic directly.

## Alternatives Considered

1. **Keep per-provider normalization and clean up duplicated helpers in `field_normalizer.py`**: Leave each provider constructing `JobListing`/`CanonicalJob`. Rejected because whenever a new normalization rule is added (e.g. currency validation, new work-model keywords), all 18+ provider codepaths must be individually updated and tested, inviting silent regressions.
2. **Universal HTML/DOM extraction for all providers**: Treat all providers as raw web pages and ignore ATS JSON APIs. Rejected because structured ATS APIs provide 100% deterministic, high-signal data without DOM scraping fragility or anti-bot blocks.

## Trade-offs

- **Intermediate Object Layer**: Introducing a raw envelope (`RawJobPosting`) adds an internal object boundary between network fetching and domain model generation.
- **Migration Scope**: All 7 ATS API clients, generic enricher paths, and 4 Nigerian scrapers must be adapted to yield raw envelopes rather than fully formed `JobListing` instances. This will be phased across dedicated steps.

## Consequences

- Normalization logic is written, tested, and audited in exactly one place (`JobExtractionService`).
- Provider adapters become lightweight, robust HTTP clients focusing solely on request construction, pagination, and error handling.
- Adding support for a new ATS or Nigerian job board requires only writing a raw fetcher and schema mapping, inheriting all canonical validation and normalization rules for free.
