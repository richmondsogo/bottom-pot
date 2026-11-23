# Contributing to Bottom Pot

Thank you for helping keep Bottom Pot reliable, fast, and honest for applicants.

## Before You Start

1. Read [`AGENTS.md`](AGENTS.md) and [`docs/LESSONS.md`](docs/LESSONS.md) to understand the repository invariants, active **Provider Freeze** (`AGENTS.md` §8.6), and operational DB protections (`ADR 0030` / `ADR 0032`).
2. Follow the setup instructions in [`README.md`](README.md) using a disposable test environment—never point tests or manual scripts at `data/cache.sqlite` or `subscriptions.csv`.

## Workflow Rules

- **Branching:** Never commit directly to `main`. Work on a dedicated feature/step branch and merge cleanly with a standard merge commit (`--no-ff`) only after all checks pass.
- **Provider freeze:** Do not add new ATS providers or new curated employer boards unless the owner explicitly lifts the freeze in writing.
- **No commit SHAs in active docs:** Never write commit SHAs inside committed active markdown files; PR descriptions record merge SHAs (`docs/LESSONS.md` `L-04`).
- **Offline tests only:** All unit/integration tests must run offline (`@pytest.mark.live` is required for any opt-in live test; `tests/conftest.py` blocks real `socket.getaddrinfo` by default).
- **Large fixtures & third-party data:** Keep fixtures minimal and real. Any tracked image or fixture above `500 KB` must be justified and recorded in [`THIRD_PARTY_DATA.md`](THIRD_PARTY_DATA.md).
- **UI geometry:** Preserve the square `--radius: 0` design system defined in [`DESIGN.md`](DESIGN.md) and CSS cascade layers in [`docs/FRONTEND.md`](docs/FRONTEND.md).

## Verification Checklist

Run these checks locally before opening a pull request:

```powershell
python -m ruff check src/ tests/ scripts/
python scripts/check_secrets.py
python scripts/check_db_safety.py
python scripts/check_repo_hygiene.py
python scripts/smoke.py
python -m pytest -q
npm --prefix frontend run lint
npm --prefix frontend run test
npm --prefix frontend run build
```

On Windows, `powershell -ExecutionPolicy Bypass -File scripts/verify.ps1` runs the full suite end-to-end (including Playwright E2E).
