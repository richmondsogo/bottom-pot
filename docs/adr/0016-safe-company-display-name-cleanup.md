# ADR 0016: Safe Company Display Name Cleanup

## Status
Accepted

## Context
Raw company names scraped from ATS board slugs or JSON-LD feeds frequently lack formatting (e.g. `HugeInc`, `Talentmanagementsolution`, `cloud-nine`, `acme_labs`). Showing unformatted machine slugs degrades editorial craft, but altering the underlying data model violates ADR 0001 ("Unknown beats wrong") and could corrupt search filtering or export parity.

## Decision
1. **Display-Layer Only**:
   - The underlying `job.company` string is never mutated or overwritten in state, localStorage, or export files.
2. **Safe Conservative Formatter (`formatCompanyDisplayName`)**:
   - PascalCase / CamelCase splitting: inserts spaces before capital letters only when preceded by lowercase (e.g., `HugeInc` -> `Huge Inc`).
   - Slugs: replaces hyphens and underscores with spaces and applies Title Case for lowercase slugs (e.g., `cloud-nine` -> `Cloud Nine`).
   - Suffix preservation: preserves common tech suffixes (`LLC`, `Inc`, `Corp`, `AI`, `Labs`, `HQ`).
   - Strict Safety Fallback: if a transform is ambiguous or could distort an intentional brand (e.g., all lowercase without separators), return the raw company string as-is.
3. **Raw Value in Tooltip**:
   - Whenever the displayed name differs from `job.company`, the raw value is made inspectable via a native or shadcn Tooltip.
4. **Unit Tests**:
   - Comprehensive unit tests in `frontend/src/lib/__tests__/normalize.test.ts` verify all positive and edge cases.

## Consequences
- Clean, human-readable company names in list rows and detail sheets.
- Zero risk of underlying data loss or distortion.
