"""Read-only offline logo coverage report across fixtures and curated catalog boards.

Reports the three mutually exclusive buckets across both catalog boards and
captured offline fixture postings without making network calls or opening SQLite:
  1. ``own_verified_logo``: bottom-pot pipeline already extracts a verified logo
  2. ``logo_dev_fallback_only``: no own verified logo, but verified ``company_domain`` exists
  3. ``neither_monogram``: neither own logo nor verified domain (renders local monogram)

Usage:
    python scripts/logo_coverage.py
    python scripts/logo_coverage.py --fixtures-dir tests/fixtures/real --json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Any

from bs4 import BeautifulSoup

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.report_freshness import _extract_fixture_postings  # noqa: E402
from src.extraction.domain_extractor import resolve_company_domain  # noqa: E402
from src.extraction.logo_extractor import (  # noqa: E402
    extract_company_logo_for_provider,
    validate_and_normalize_logo_url,
)
from src.monitoring.employer_board_catalog import (  # noqa: E402
    VERIFIED_EMPLOYER_BOARDS,
    CuratedEmployerBoard,
)

_STEP_PREFIX_RE = re.compile(
    r"^(greenhouse|lever|ashby|workable|recruitee|smartrecruiters|teamtailor|personio|pinpointhq|workday)_(.+)$",
    re.IGNORECASE,
)


def _infer_provider_and_slug(root: Path, path: Path) -> tuple[str, str | None]:
    rel = path.relative_to(root)
    top = rel.parts[0].lower() if len(rel.parts) > 1 else "unknown"
    m = _STEP_PREFIX_RE.match(path.stem)
    if top.startswith("step") and m:
        slug = m.group(2)
        for suffix in ("_details", "_jobs", "_board", "_sample"):
            if slug.endswith(suffix):
                slug = slug[: -len(suffix)]
        return m.group(1).lower(), slug.lower()
    slug_guess = path.stem.lower()
    for suffix in ("_board_sample", "_board", "_sample", "_list", "_offers", "_jobs", "_job", "_rss"):
        if slug_guess.endswith(suffix):
            slug_guess = slug_guess[: -len(suffix)]
    return top, slug_guess or None


def _extract_board_level_verified_logo(provider: str, paths: list[Path]) -> str | None:
    """Inspect captured JSON/HTML/RSS fixture files for an authentic verified board/account logo."""
    for p in paths:
        suf = p.suffix.lower()
        text = p.read_text(encoding="utf-8", errors="replace")
        if suf in (".html", ".htm"):
            soup = BeautifulSoup(text, "lxml")
            res = extract_company_logo_for_provider(provider, soup=soup, page_url=str(p))
            if res.verified and res.url:
                return res.url
        elif suf == ".json":
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict):
                raw_account_logo = data.get("logo")
                if isinstance(raw_account_logo, str) and provider == "workable":
                    res = extract_company_logo_for_provider("workable", workable_account_logo=raw_account_logo)
                    if res.verified and res.url:
                        return res.url
        elif suf in (".xml", ".rss"):
            m = re.search(r"<image>\s*(?:<[^>]+>.*?</[^>]+>\s*)*<url>(.*?)</url>", text, re.IGNORECASE | re.DOTALL)
            if m:
                norm = validate_and_normalize_logo_url(m.group(1))
                if norm:
                    return norm
    return None


def _posting_has_verified_logo(
    provider: str,
    posting: dict[str, Any],
    board_logo_url: str | None,
) -> bool:
    if board_logo_url and validate_and_normalize_logo_url(board_logo_url):
        return True
    direct = validate_and_normalize_logo_url(posting.get("company_logo_url"))
    if direct and posting.get("company_logo_verified"):
        return True
    hiring_org = posting.get("hiringOrganization")
    if isinstance(hiring_org, dict) and hiring_org.get("logo"):
        res = extract_company_logo_for_provider(provider, json_ld_doc=posting)
        if res.verified and res.url:
            return True
    if provider == "ashby":
        # Board-level Ashby logoSquareImageUrl handled via HTML fixtures; individual postings rarely embed logos
        return False
    return False


def _pick_apply_url(posting: dict[str, Any]) -> str | None:
    for key in ("apply_url", "applyUrl", "hostedUrl", "absolute_url", "application_url", "url", "shortlink"):
        val = posting.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return None


def compute_logo_coverage(
    fixtures_dir: str | Path,
    catalog: tuple[CuratedEmployerBoard, ...] = VERIFIED_EMPLOYER_BOARDS,
) -> dict[str, Any]:
    """Compute mutually exclusive 3-bucket logo coverage over catalog boards and fixture postings."""
    root = Path(fixtures_dir)
    if not root.exists():
        raise FileNotFoundError(f"Fixtures directory not found: {root}")

    files_by_board: dict[tuple[str, str], list[Path]] = {}
    all_fixture_files = [p for p in sorted(root.rglob("*")) if p.is_file()]
    for path in all_fixture_files:
        prov, slug = _infer_provider_and_slug(root, path)
        if slug:
            files_by_board.setdefault((prov, slug), []).append(path)

    board_logo_cache: dict[tuple[str, str], str | None] = {}
    for key, paths in files_by_board.items():
        board_logo_cache[key] = _extract_board_level_verified_logo(key[0], paths)

    catalog_counts = {"total": 0, "own_verified_logo": 0, "logo_dev_fallback_only": 0, "neither_monogram": 0}
    catalog_rows: list[dict[str, Any]] = []
    for board in catalog:
        catalog_counts["total"] += 1
        prov = board.ats_provider.strip().lower()
        token = board.board_token.strip().lower()
        matching_files = [
            p
            for p in all_fixture_files
            if token in p.name.lower() and (prov in p.name.lower() or prov in p.parent.name.lower())
        ]
        own_logo = board_logo_cache.get((prov, token)) or _extract_board_level_verified_logo(prov, matching_files)
        domain, source = resolve_company_domain(
            provider=prov,
            company_slug=token,
            apply_url=board.board_url,
            catalog_domain=board.company_domain,
        )
        if own_logo:
            bucket = "own_verified_logo"
        elif domain:
            bucket = "logo_dev_fallback_only"
        else:
            bucket = "neither_monogram"
        catalog_counts[bucket] += 1
        catalog_rows.append(
            {
                "company_name": board.company_name,
                "provider": prov,
                "board_token": token,
                "company_domain": domain,
                "company_domain_source": source,
                "has_own_verified_logo": bool(own_logo),
                "bucket": bucket,
            }
        )

    fixture_counts = {"total": 0, "own_verified_logo": 0, "logo_dev_fallback_only": 0, "neither_monogram": 0}
    per_provider: dict[str, dict[str, int]] = {}

    _XML_ITEM_RE = re.compile(r"<(?:item|job|entry)\b[^>]*>(.*?)</(?:item|job|entry)>", re.IGNORECASE | re.DOTALL)
    for path in all_fixture_files:
        suf = path.suffix.lower()
        if path.name.lower().endswith("manifest.json"):
            continue
        prov, slug = _infer_provider_and_slug(root, path)
        board_logo = board_logo_cache.get((prov, slug or "")) if slug else None
        stats = per_provider.setdefault(
            prov,
            {"total": 0, "own_verified_logo": 0, "logo_dev_fallback_only": 0, "neither_monogram": 0},
        )
        if suf == ".json":
            try:
                data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
            except json.JSONDecodeError:
                continue
            postings = _extract_fixture_postings(data)
            for posting in postings:
                fixture_counts["total"] += 1
                stats["total"] += 1
                has_own = _posting_has_verified_logo(prov, posting, board_logo)
                if has_own:
                    bucket = "own_verified_logo"
                else:
                    apply_url = _pick_apply_url(posting)
                    dom, _ = resolve_company_domain(provider=prov, company_slug=slug, apply_url=apply_url)
                    bucket = "logo_dev_fallback_only" if dom else "neither_monogram"
                fixture_counts[bucket] += 1
                stats[bucket] += 1
        elif suf in (".xml", ".rss"):
            raw_xml = path.read_text(encoding="utf-8", errors="replace")
            for match in _XML_ITEM_RE.finditer(raw_xml):
                block = match.group(1)
                link_m = re.search(r"<(?:link|url)\b[^>]*>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</(?:link|url)>", block, re.IGNORECASE | re.DOTALL)
                apply_url = link_m.group(1).strip() if link_m else None
                fixture_counts["total"] += 1
                stats["total"] += 1
                if board_logo and validate_and_normalize_logo_url(board_logo):
                    bucket = "own_verified_logo"
                else:
                    dom, _ = resolve_company_domain(provider=prov, company_slug=slug, apply_url=apply_url)
                    bucket = "logo_dev_fallback_only" if dom else "neither_monogram"
                fixture_counts[bucket] += 1
                stats[bucket] += 1
        if stats["total"] == 0:
            per_provider.pop(prov, None)

    return {
        "fixtures_dir": str(root),
        "catalog_boards": catalog_counts,
        "catalog_details": catalog_rows,
        "fixture_postings": fixture_counts,
        "fixture_postings_by_provider": dict(sorted(per_provider.items())),
    }


def format_coverage_report(summary: dict[str, Any]) -> str:
    cat = summary["catalog_boards"]
    fix = summary["fixture_postings"]
    lines = [
        f"Logo Coverage Report ({summary['fixtures_dir']}) [read-only, offline]",
        "",
        "Curated Catalog Boards (28):",
        f"  1. Own verified logo      : {cat['own_verified_logo']}",
        f"  2. Logo.dev fallback only : {cat['logo_dev_fallback_only']}",
        f"  3. Neither (monogram)     : {cat['neither_monogram']}",
        f"  Total                     : {cat['total']}",
        "",
        "Captured Fixture Postings:",
        f"  1. Own verified logo      : {fix['own_verified_logo']}",
        f"  2. Logo.dev fallback only : {fix['logo_dev_fallback_only']}",
        f"  3. Neither (monogram)     : {fix['neither_monogram']}",
        f"  Total                     : {fix['total']}",
        "",
        f"{'Provider':<18} {'Total':>7} {'OwnLogo':>9} {'Logo.dev':>9} {'Monogram':>9}",
        "-" * 56,
    ]
    for prov, st in summary["fixture_postings_by_provider"].items():
        lines.append(
            f"{prov:<18} {st['total']:>7} {st['own_verified_logo']:>9} "
            f"{st['logo_dev_fallback_only']:>9} {st['neither_monogram']:>9}"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only logo coverage report over catalog & offline fixtures.")
    parser.add_argument("--fixtures-dir", default="tests/fixtures/real", help="Offline fixture directory.")
    parser.add_argument("--json", action="store_true", dest="as_json", help="Emit JSON output.")
    args = parser.parse_args(argv)

    summary = compute_logo_coverage(args.fixtures_dir)
    if args.as_json:
        print(json.dumps(summary, indent=2))
    else:
        print(format_coverage_report(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
