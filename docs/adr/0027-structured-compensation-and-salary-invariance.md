# ADR 0027: Structured Compensation and Salary Invariance

## Status

Proposed

## Context

Compensation data in Bottom Pot currently suffers from severe model contradictions and domain rule violations:

1. **Fabricated Defaults in `JobSalary`**:
   In `src/project_files/models.py:227-232`:
   ```python
   class JobSalary(BaseModel):
       minimum: Optional[int] = None
       maximum: Optional[int] = None
       currency: Optional[str] = "USD"
       period: Optional[str] = "year"
   ```
   `currency` defaults to `"USD"` and `period` defaults to `"year"`. If a Nigerian posting specifies a monthly salary in Naira (e.g., NGN 200,000 / month) or a UK posting specifies GBP, constructing `JobSalary(minimum=200000)` without specifying currency causes it to default to USD 200,000 per year. This directly violates the core project domain rule:
   > *"Never invent, infer, or fabricate job information. Missing stays missing. Unknown currency stays unknown (never default to USD). Unknown pay period stays unknown (never default to annual)."*

2. **Union Type and Frontend Parsing Violation**:
   In `JobListing`, salary is typed as `JobSalary | str | None = None`. In Nigerian scrapers (`nigerian_scrapers.py`), raw unparsed strings like `"N 150,000 - N 250,000 monthly"` are dumped directly into `JobListing.salary`. The React frontend (`frontend/src/lib/normalize.ts` and `frontend/src/lib/sort.ts`) is then forced to re-parse the string with regexes (`match(/\d+/)`) to extract numbers for sorting and formatting. This directly violates **ADR 0003: Backend Owns Parsing**:
   > *"The backend parses and normalizes titles, compensation, and snippets. The frontend must never re-parse or infer raw data."*

3. **Untapped Structured Compensation**:
   ATS APIs (Ashby, Greenhouse custom fields, Recruitee) and JSON-LD `JobPosting.baseSalary` (`MonetaryAmount` with `minValue`, `maxValue`, `currency`, `unitText`) frequently provide structured compensation in real payloads, but current adapters ignore these fields completely.

## Decision

We will refactor salary representation and extraction into a deterministic, structured contract with zero invented defaults:

1. **Refactor `JobSalary` Model**:
   - `currency: Optional[str] = None` (No default; unknown currency stays `None`).
   - `period: Optional[str] = None` (No default; unknown period stays `None`, valid values: `"hour"`, `"day"`, `"week"`, `"month"`, `"year"`).
   - `minimum: Optional[int] = None`
   - `maximum: Optional[int] = None`
   - `raw_text: Optional[str] = None` (Preserves the exact literal string as evidence).
   - Validation ensures at least one of `minimum` or `maximum` is present, non-negative, and `minimum <= maximum`.

2. **Progressive Compensation Extraction**:
   - **Tier 1: Structured ATS API Fields**: Extract native compensation objects (e.g. Ashby `compensationTierSummary`, Greenhouse custom fields).
   - **Tier 2: JSON-LD `baseSalary`**: Extract schema.org `MonetaryAmount` (capturing ISO currency codes like `USD`, `GBP`, `EUR`, `NGN`, and `unitText`).
   - **Tier 3: Deterministic Text Extraction**: For Nigerian scrapers and job bodies with explicit compensation syntax (e.g. `"₦150,000 - ₦250,000 per month"`, `"$120,000 - $150,000 / yr"`), a shared parser normalizes values into numeric bounds, detects currency symbols/codes, and maps period.
   - Ambiguous phrases ("competitive salary", "market rate", "DOE") and non-base compensation (equity, bonuses, target bonuses) are explicitly rejected and remain `None`.

3. **Backend Exclusivity**:
   - The backend extraction service parses all salaries into structured `JobSalary` objects before serializing to `JobListing` or SSE streams.
   - The frontend will display pre-formatted compensation and consume typed numeric bounds for sorting without executing regex parsing.

## Alternatives Considered

1. **Keep `JobListing.salary` as a raw string**: Allow backend to pass whatever raw string was found. Rejected because client-side sorting and filtering break across currencies and pay periods, and it contradicts ADR 0003.
2. **Convert all salaries to USD for uniform sorting**: Use live or fixed FX rates to convert NGN/GBP/EUR to USD. Rejected because FX conversion introduces artificial estimation, currency drift, and violates "Unknown beats wrong". Jobs must preserve their native declared currency.

## Trade-offs

- **Strict Validation Discards Ambiguous Strings**: Text strings that fail deterministic parsing will result in `salary=None`. This is the intended behavior under ADR 0001 (unknown beats wrong).
- **Frontend Type Harmonization**: Frontend TypeScript interfaces will be tightened to expect structured `JobSalary` objects, deprecating loose string handling.

## Consequences

- Nigerian compensation (NGN) and international compensation (EUR, GBP, CAD) will be represented honestly without defaulting to USD per year.
- ATS platforms with structured pay transparency data will be accurately populated.
- Frontend sorting by salary will operate reliably on verified integers rather than fragile string regexes.
