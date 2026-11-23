"""Read-only job freshness report by ATS provider.

Summarizes fresh (<=30d), recent (31-90d), stale (>90d), evergreen, and unlisted
job postings either from a SQLite cache/registry DB (opened strictly read-only)
or offline from captured API/RSS fixtures.

Usage:
    python scripts/report_freshness.py --fixtures-dir tests/fixtures/real
    python scripts/report_freshness.py --db path/to/temp.sqlite --json
    python scripts/report_freshness.py --allow-operational-db
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.core.settings import settings  # noqa: E402
from src.extraction.freshness import (  # noqa: E402
    FreshnessTier,
    compute_age_days,
    compute_freshness,
    detect_evergreen_signal,
)
from src.safety.db_safety import (  # noqa: E402
    assert_safe_sqlite_db_path,
    cli_operational_runtime,
)

_DATE_FIELD_CANDIDATES = (
    "posted_at",
    "publishedAt",
    "published_at",
    "publishedDate",
    "updated_at",
    "updatedAt",
    "first_published",
    "created_at",
    "createdAt",
    "datePosted",
    "postedOn",
    "releasedDate",
    "pubDate",
    "start_date",
)

_XML_ITEM_RE = re.compile(r"<(?:item|job|entry)\b[^>]*>(.*?)</(?:item|job|entry)>", re.IGNORECASE | re.DOTALL)
_XML_TAG_VALUE_RE = {
    "title": re.compile(r"<title\b[^>]*>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", re.IGNORECASE | re.DOTALL),
    "posted": re.compile(
        r"<(?:pubDate|published|updated|created_at|datePosted)\b[^>]*>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</(?:pubDate|published|updated|created_at|datePosted)>",
        re.IGNORECASE | re.DOTALL,
    ),
    "description": re.compile(
        r"<(?:description|content|summary)\b[^>]*>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</(?:description|content|summary)>",
        re.IGNORECASE | re.DOTALL,
    ),
}


def _epoch_to_iso(epoch: Any) -> str | None:
    if isinstance(epoch, (int, float)) and epoch > 0:
        return datetime.fromtimestamp(float(epoch), tz=timezone.utc).isoformat()
    return None


def _parse_reference_now(now_str: str | None) -> datetime:
    if not now_str:
        return datetime.now(timezone.utc)
    cleaned = now_str.strip()
    if cleaned.endswith("Z"):
        cleaned = cleaned[:-1] + "+00:00"
    dt = datetime.fromisoformat(cleaned)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _new_bucket() -> dict[str, Any]:
    return {
        "total": 0,
        "fresh": 0,
        "recent": 0,
        "stale": 0,
        "evergreen": 0,
        "unlisted": 0,
        "ages": [],
    }


def _record_posting(
    buckets: dict[str, dict[str, Any]],
    provider: str,
    *,
    posted_at: Any,
    first_seen_at: Any = None,
    evergreen_signal: str | None = None,
    explicit_freshness: FreshnessTier | str | None = None,
    now: datetime,
) -> None:
    bucket = buckets[provider or "unknown"]
    bucket["total"] += 1
    tier = compute_freshness(
        posted_at=posted_at,
        first_seen_at=first_seen_at,
        evergreen_signal=evergreen_signal,
        explicit_freshness=explicit_freshness,
        now=now,
    )
    if tier is None:
        bucket["unlisted"] += 1
    else:
        bucket[tier.value] += 1
    age_days = compute_age_days(posted_at, first_seen_at=first_seen_at, now=now)
    if age_days is not None:
        bucket["ages"].append(age_days)


def _finalize_summary(source: str, buckets: dict[str, dict[str, Any]], now: datetime) -> dict[str, Any]:
    providers: dict[str, dict[str, Any]] = {}
    totals = _new_bucket()
    for provider in sorted(buckets):
        raw = buckets[provider]
        ages = sorted(raw["ages"])
        providers[provider] = {
            "total": raw["total"],
            "fresh": raw["fresh"],
            "recent": raw["recent"],
            "stale": raw["stale"],
            "evergreen": raw["evergreen"],
            "unlisted": raw["unlisted"],
            "median_age_days": round(float(statistics.median(ages)), 1) if ages else None,
            "oldest_age_days": ages[-1] if ages else None,
        }
        for key in ("total", "fresh", "recent", "stale", "evergreen", "unlisted"):
            totals[key] += raw[key]
        totals["ages"].extend(ages)

    all_ages = sorted(totals["ages"])
    return {
        "source": source,
        "as_of": now.isoformat(),
        "total_postings": totals["total"],
        "totals": {
            "fresh": totals["fresh"],
            "recent": totals["recent"],
            "stale": totals["stale"],
            "evergreen": totals["evergreen"],
            "unlisted": totals["unlisted"],
            "median_age_days": round(float(statistics.median(all_ages)), 1) if all_ages else None,
            "oldest_age_days": all_ages[-1] if all_ages else None,
        },
        "providers": providers,
    }


def report_from_sqlite(
    db_path: str | Path,
    *,
    allow_operational_db: bool = False,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Read monitored_jobs strictly read-only and compute per-provider freshness counts."""
    ref_now = now or datetime.now(timezone.utc)
    buckets: dict[str, dict[str, Any]] = defaultdict(_new_bucket)

    with cli_operational_runtime("scripts.report_freshness:main", allow_operational_db=allow_operational_db):
        safe_path = Path(assert_safe_sqlite_db_path(db_path, operation="connect"))
        if not safe_path.exists():
            raise FileNotFoundError(f"SQLite database not found: {safe_path}")
        ro_uri = f"{safe_path.resolve().as_uri()}?mode=ro"
        conn = sqlite3.connect(ro_uri, uri=True, timeout=5.0)
        try:
            has_table = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='monitored_jobs'"
            ).fetchone()
            if has_table:
                rows = conn.execute(
                    """
                    SELECT ats_provider, title, description, posted_at, first_discovered_at, canonical_json
                    FROM monitored_jobs
                    WHERE status = 'active'
                    """
                ).fetchall()
                for provider, title, description, posted_at, first_discovered_at, canonical_json in rows:
                    ev_signal: str | None = None
                    if canonical_json:
                        try:
                            payload = json.loads(canonical_json)
                            if isinstance(payload, dict):
                                ev_signal = payload.get("evergreen_signal")
                        except json.JSONDecodeError:
                            pass
                    if ev_signal is None:
                        ev_signal = detect_evergreen_signal(title=title, description=description)
                    _record_posting(
                        buckets,
                        str(provider or "unknown"),
                        posted_at=posted_at,
                        first_seen_at=_epoch_to_iso(first_discovered_at),
                        evergreen_signal=ev_signal,
                        now=ref_now,
                    )
        finally:
            conn.close()

    return _finalize_summary(f"db:{safe_path}", buckets, ref_now)


def _extract_fixture_postings(obj: Any) -> list[dict[str, Any]]:
    """Extract job-posting-like dicts from diverse real ATS fixture shapes."""
    postings: list[dict[str, Any]] = []
    if isinstance(obj, list):
        for item in obj:
            postings.extend(_extract_fixture_postings(item))
        return postings
    if not isinstance(obj, dict):
        return postings

    for container_key in ("jobs", "postings", "results", "jobPostings", "offers", "content", "openings", "data"):
        val = obj.get(container_key)
        if isinstance(val, list) and any(isinstance(x, dict) for x in val):
            for entry in val:
                if isinstance(entry, dict):
                    postings.append(entry)
            if postings:
                return postings

    if any(k in obj for k in ("title", "text", "name", "jobTitle")) and any(
        k in obj for k in _DATE_FIELD_CANDIDATES + ("id", "applyUrl", "hostedUrl", "absolute_url", "url")
    ):
        postings.append(obj)
        return postings

    for val in obj.values():
        if isinstance(val, (dict, list)):
            postings.extend(_extract_fixture_postings(val))
    return postings


def _pick_date_from_dict(posting: dict[str, Any]) -> Any:
    for field in _DATE_FIELD_CANDIDATES:
        val = posting.get(field)
        if val not in (None, "", 0):
            return val
    return None


def report_from_fixtures(
    fixtures_dir: str | Path,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Scan local JSON/XML/RSS fixture snapshots offline without network or DB access."""
    root = Path(fixtures_dir)
    if not root.exists():
        raise FileNotFoundError(f"Fixtures directory not found: {root}")
    ref_now = now or datetime.now(timezone.utc)
    buckets: dict[str, dict[str, Any]] = defaultdict(_new_bucket)

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        provider = rel.parts[0] if len(rel.parts) > 1 else "root"
        suffix = path.suffix.lower()

        if suffix == ".json":
            try:
                data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
            except json.JSONDecodeError:
                continue
            for posting in _extract_fixture_postings(data):
                title = posting.get("title") or posting.get("text") or posting.get("name")
                desc = posting.get("description") or posting.get("descriptionPlain") or posting.get("content")
                posted_at = _pick_date_from_dict(posting)
                ev_signal = detect_evergreen_signal(
                    title=str(title) if isinstance(title, str) else None,
                    description=str(desc) if isinstance(desc, str) else None,
                    raw_fields=posting,
                )
                _record_posting(
                    buckets,
                    provider,
                    posted_at=posted_at,
                    evergreen_signal=ev_signal,
                    now=ref_now,
                )
        elif suffix in (".xml", ".rss"):
            raw_xml = path.read_text(encoding="utf-8", errors="replace")
            for match in _XML_ITEM_RE.finditer(raw_xml):
                block = match.group(1)
                title_m = _XML_TAG_VALUE_RE["title"].search(block)
                posted_m = _XML_TAG_VALUE_RE["posted"].search(block)
                desc_m = _XML_TAG_VALUE_RE["description"].search(block)
                title_val = title_m.group(1).strip() if title_m else None
                posted_val = posted_m.group(1).strip() if posted_m else None
                desc_val = desc_m.group(1).strip() if desc_m else None
                _record_posting(
                    buckets,
                    provider,
                    posted_at=posted_val,
                    evergreen_signal=detect_evergreen_signal(title=title_val, description=desc_val),
                    now=ref_now,
                )

    return _finalize_summary(f"fixtures:{root}", buckets, ref_now)


def format_text_report(summary: dict[str, Any]) -> str:
    """Render a compact terminal table summarizing freshness breakdown by provider."""
    lines = [
        f"Job Freshness Report ({summary['source']}) as of {summary['as_of']}",
        f"Total postings: {summary['total_postings']}",
        "",
        f"{'Provider':<20} {'Total':>6} {'Fresh':>6} {'Recent':>6} {'Evergr':>6} {'Stale':>6} {'Unlist':>6} {'Median(d)':>10} {'Oldest(d)':>10}",
        "-" * 86,
    ]
    for provider, stats in summary["providers"].items():
        med = f"{stats['median_age_days']:.1f}" if stats["median_age_days"] is not None else "-"
        old = str(stats["oldest_age_days"]) if stats["oldest_age_days"] is not None else "-"
        lines.append(
            f"{provider:<20} {stats['total']:>6} {stats['fresh']:>6} {stats['recent']:>6} "
            f"{stats['evergreen']:>6} {stats['stale']:>6} {stats['unlisted']:>6} {med:>10} {old:>10}"
        )
    totals = summary["totals"]
    med_all = f"{totals['median_age_days']:.1f}" if totals["median_age_days"] is not None else "-"
    old_all = str(totals["oldest_age_days"]) if totals["oldest_age_days"] is not None else "-"
    lines.append("-" * 86)
    lines.append(
        f"{'TOTAL':<20} {summary['total_postings']:>6} {totals['fresh']:>6} {totals['recent']:>6} "
        f"{totals['evergreen']:>6} {totals['stale']:>6} {totals['unlisted']:>6} {med_all:>10} {old_all:>10}"
    )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only freshness report per ATS provider.")
    parser.add_argument("--db", default=None, help="Path to SQLite database (opened strictly read-only).")
    parser.add_argument("--fixtures-dir", default=None, help="Scan offline API/RSS fixture files in directory.")
    parser.add_argument("--json", action="store_true", dest="as_json", help="Emit JSON output instead of text table.")
    parser.add_argument("--now", default=None, help="Optional ISO-8601 UTC reference timestamp.")
    parser.add_argument(
        "--allow-operational-db",
        action="store_true",
        help="Explicitly authorize read-only inspection of the configured operational database.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    ref_now = _parse_reference_now(args.now)

    if args.fixtures_dir:
        summary = report_from_fixtures(args.fixtures_dir, now=ref_now)
    else:
        db_target = args.db or settings.sqlite_db_path
        summary = report_from_sqlite(
            db_target,
            allow_operational_db=args.allow_operational_db,
            now=ref_now,
        )

    if args.as_json:
        print(json.dumps(summary, indent=2))
    else:
        print(format_text_report(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
