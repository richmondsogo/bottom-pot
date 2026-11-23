# Project Context: Bottom Pot

Authoritative domain summary and non-negotiable constraints. Architectural rationales live in [`docs/adr/`](docs/adr/README.md) and module layout in [`docs/architecture.md`](docs/architecture.md).

---

## Product & Problem

**Bottom Pot is global by design. Nigeria and wider Africa are priority validation markets, not hard-coded boundaries.**

Bottom Pot is a global, ATS-first job discovery web app built with FastAPI (`src/`) and React/Vite (`frontend/`). It bypasses aggregator reposts and stale ghost listings by:

1. Searching **18 configured public ATS platforms** (`ATS_PLATFORMS` in `src/core/settings.py`) plus **3 Nigerian job boards** (`jobberman`, `myjobmag`, `hotnigerianjobs`) via budgeted Google `site:` queries (`Serper.dev`) and direct ATS API/page enrichment, streamed over Server-Sent Events (`GET /search`).
2. Polling monitored direct employer boards across **9 monitored ATS adapters** (`BOARD_ADAPTERS` under `src/providers/`, all governed by one shared C1–C12 snapshot/closure contract) stored in SQLite FTS5.
3. Evaluating job-level **applicant eligibility** (`eligible`, `restricted`, or `unknown`) against a user-selectable ISO 3166-1 alpha-2 country via backend-authoritative rules (`POST /api/eligibility/evaluate`), clearly ranking posting freshness (`fresh`, `recent`, `stale`, `evergreen`).

---

## Domain Terms & Strict 4-Dimension Separation

Maintain strict separation across all extraction, storage, API, and UI code:

1. **Work arrangement:** `remote`, `hybrid`, `in_person` (`onsite`), or `unknown` (`ADR 0002`).
2. **Source geography:** Where an ATS platform or job board is operated.
3. **Job geography:** Physical location, city, country, or region named on the requisition.
4. **Applicant eligibility:** Where an applicant may legally reside/work from (`worldwide`, explicit allowed/excluded countries/regions, visa/work-authorization, payroll, timezone, or `unknown`). Never infer worldwide eligibility from `"Remote"` or missing evidence (`ADR 0001`).

| Term | Meaning |
|---|---|
| **Serper Daily Budget** | Hard cap of `SERPER_DAILY_BUDGET` (`200`/UTC day) outbound Serper requests; sets `budget_exhausted` (`incomplete: true` for anonymous callers) when hit. |
| **FreshnessTier (`ADR 0034`)** | `fresh` (`<=30d`), `recent` (`31–90d`), `stale` (`>90d`), or explicit `evergreen`; stale rows render below an `"Older postings"` divider in default order. |
| **Logo Fallback (`ADR 0031`)** | Browser hotlink chain: native ATS API logo -> Logo.dev (`fallback=404` with domain-restricted `pk_*` key) -> crisp square monogram. Zero backend image caching or guessing. |
| **External Data Dir (`ADR 0032`)** | Fresh production installs store `cache.sqlite` and `subscriptions.csv` outside git (`BOTTOM_POT_DATA_DIR`); legacy `<repo>/data/` installs stay protected under `ADR 0030`. |

---

## Constraints & Non-Goals

- **Square Design System (`DESIGN.md`):** `--radius: 0` everywhere; warm cream (`#FAF8F5`) and deep green (`#1A382B`); WCAG AA contrast; responsive down to `390px`.
- **Backend API & Parsing Authority (`ADR 0003`):** Backend owns parsing, freshness tiers, domain resolution, and eligibility vectors (`tests/vectors/eligibility.json`). Anonymous SSE events strip admin metadata (`src/api/allowlist.py`).
- **Offline Testing & Operational Safety (`ADR 0030`):** Live Serper searches are never run in tests. `tests/conftest.py` blocks real DNS unless `@pytest.mark.live` is set, and tests/E2E/smoke always isolate to disposable directories.
- **Platform Compatibility:** Commands and scripts must work on Windows PowerShell 5.1 as well as Linux/macOS.
- **Non-Goals / Out of Scope:**
  - User accounts, hosted multi-tenant auth, or cloud database storage (`Vercel`, `Neon` are strictly out of scope).
  - Live deployment or touching external cloud hosting infrastructure until the owner explicitly amends this constraint.
  - Automated job application submission or resume parsing.
  - Adding a 10th ATS provider or unapproved employer boards during the active **Provider Freeze** (`AGENTS.md` §6).

---

## Source Discovery & Lifecycle Policy

See [`docs/job-source-catalog.md`](docs/job-source-catalog.md) for the authoritative status of every evaluated source (`Implemented`, `Constrained`, `Discovery-only`, `Permission pending`, `Rejected`, `Retired`). Whenever a source is rejected or retired, remove active configuration, parsers, routers, and frontend references while preserving shared helpers, `HISTORICAL_FULL_INVENTORIES`, [`docs/history/`](docs/history/), and operational SQLite data.
