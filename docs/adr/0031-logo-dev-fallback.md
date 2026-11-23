# ADR 0031: Three-Tier Company Logo Resolution & Logo.dev Fallback

## Status
Accepted (Step 57 Phase 6)

## Context
Previously, Bottom Pot extracted authentic company logos natively from a subset of ATS platforms (`teamtailor`, `lever`, `greenhouse`, `ashby`, `workable`, `recruitee`, `smartrecruiters`), leaving postings from API-only endpoints without logos unless HTML enrichment fetched one.

Per [ADR 0001](0001-unknown-beats-wrong.md) ("Unknown beats wrong"), guessing a company's domain from its display name risks rendering the wrong company's logo, which is worse than displaying no logo at all.

## Decision

1. **Three-tier display priority (`frontend/src/components/CompanyMark.tsx`)**:
   - **Tier 1 (`api`)**: Use our own pipeline's verified HTTPS `company_logo_url` extracted directly from the ATS/employer page (`src/extraction/logo_extractor.py`).
   - **Tier 2 (`logo_dev`)**: When Tier 1 is absent or fails to load, request `https://img.logo.dev/<company_domain>?token=<pk_...>&size=128&format=png&fallback=404` ONLY when both a verified `company_domain` and a publishable `pk_` token are configured.
   - **Tier 3 (`monogram`)**: Render our square `rounded-none` monogram tile immediately on missing domain, missing `pk_` token, or `onError` (`404`) from Logo.dev — never displaying Logo.dev's generic generated placeholder.

2. **Verified `company_domain` resolution (`src/extraction/domain_extractor.py`)**:
   - **(a) `catalog_verified`**: Explicit `company_domain` verified from official employer sites/fixtures across all curated boards in `src/monitoring/employer_board_catalog.py`.
   - **(b) `apply_url_host`**: Employer-owned host extracted from `apply_url` only after rejecting every ATS domain from `ATS_PLATFORMS`, all `personio.*` regional hosts, aggregator boards, link shorteners, IP literals, and localhost/example placeholders, then reducing to the registrable domain via [`publicsuffixlist`](https://pypi.org/project/publicsuffixlist/) (`accept_unknown=False`, bundled offline PSL snapshot with zero runtime network lookups or transitive dependencies).
   - **(c) `(None, None)`**: Never guess from `company` name by default.

3. **Hotlinking & Key Separation**:
   - Backend services and caches **never** fetch, download, cache, store, or proxy Logo.dev image bytes (hotlink-only per Logo.dev CDN terms).
   - Frontend configuration (`VITE_LOGO_DEV_TOKEN`) accepts **only** publishable `pk_` keys restricted by domain in the Logo.dev dashboard; secret `sk_` keys are rejected by `isValidPublishableLogoDevToken` and must never appear in frontend code or tracked files.

4. **Free-Plan Attribution, Production Domain Verification & Privacy**:
   - The footer renders `<a href="https://logo.dev">Logos provided by Logo.dev</a>` on both marketing and workspace views.
   - Before deploying to production on the Logo.dev free tier, the owner must register the production URL in the Logo.dev dashboard for domain-restriction verification and attribution compliance.
   - **Privacy notice**: Logo.dev fallback images (`img.logo.dev`) are requested directly from the user's browser (using `referrerPolicy="no-referrer"` and `loading="lazy"`), so standard CDN HTTP metadata (IP address and user-agent) goes to Logo.dev directly. Users without `VITE_LOGO_DEV_TOKEN` configured receive zero calls to `img.logo.dev`.

## Consequences
- Increases logo coverage across captured postings while strictly preserving `ADR 0001` correctness and the `0px` square frame design system.
- Offline coverage visibility is auditable at any time via `python scripts/logo_coverage.py`.
