"""
Job freshness model, boundary constants, explicit evergreen detection, and tier ordering.

Separates posting age and freshness visibility from feed manipulation:
- Fresh: <= FRESH_MAX_DAYS (30 days)
- Recent: <= RECENT_MAX_DAYS (90 days)
- Stale: > RECENT_MAX_DAYS (90 days), OR unlisted-date jobs first seen > 90 days ago
- Evergreen: ONLY when an explicit ATS flag or explicit multi-hire/pipeline statement exists
  (never inferred from age or missing dates, per ADR 0001).
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from enum import Enum
from typing import Any, Sequence, TypeVar

from src.core.clock import utc_now

T = TypeVar("T")

FRESH_MAX_DAYS: int = 30
RECENT_MAX_DAYS: int = 90


class FreshnessTier(str, Enum):
    FRESH = "fresh"
    RECENT = "recent"
    STALE = "stale"
    EVERGREEN = "evergreen"


FRESHNESS_TIER_ORDER: dict[FreshnessTier | None, int] = {
    FreshnessTier.FRESH: 0,
    FreshnessTier.RECENT: 1,
    FreshnessTier.EVERGREEN: 2,
    None: 3,
    FreshnessTier.STALE: 4,
}

_EVERGREEN_FLAG_KEYS: tuple[str, ...] = ("evergreen", "is_evergreen", "isEvergreen")
_EVERGREEN_TYPE_KEYS: tuple[str, ...] = ("requisitionType", "openingType", "job_type")

_EVERGREEN_STATEMENT_RE = re.compile(
    r"\b(?:"
    r"evergreen\s+(?:role|position|requisition|req|opening|posting|pipeline)"
    r"|(?:continuously|constantly|always|ongoing)\s+(?:hiring|accepting\s+applications|recruiting)\s+for\s+(?:this|these)\s+(?:role|roles|position|positions|pipeline|talent\s+pool)"
    r"|(?:hiring|recruiting)\s+(?:for\s+)?multiple\s+(?:openings|positions|roles|headcount|candidates)"
    r"|multiple\s+(?:openings|positions|headcount)\s+(?:available|across|for\s+this\s+role)"
    r"|general\s+application"
    r"|open\s+application"
    r"|rolling\s+applications?"
    r"|talent\s+pool\s+(?:posting|requisition|opening)"
    r")\b",
    re.IGNORECASE,
)


def _is_truthy_flag(val: Any) -> bool:
    if isinstance(val, bool):
        return val
    if isinstance(val, int) and val in (0, 1):
        return val == 1
    if isinstance(val, str):
        return val.strip().lower() in {"true", "yes", "1"}
    return False


def _ensure_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def parse_freshness_timestamp(raw: Any) -> datetime | None:
    """Parse datetime, ISO-8601, RFC-2822, or epoch seconds/milliseconds to UTC datetime."""
    if raw is None or raw == "":
        return None
    if isinstance(raw, datetime):
        return _ensure_utc(raw).astimezone(timezone.utc)
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        ts = float(raw)
        if ts <= 0:
            return None
        if ts > 1e12:
            ts /= 1000.0
        try:
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        except (OSError, OverflowError, ValueError):
            return None
    if isinstance(raw, str):
        cleaned = raw.strip()
        if not cleaned:
            return None
        if cleaned.isdigit():
            return parse_freshness_timestamp(int(cleaned))
        iso = cleaned[:-1] + "+00:00" if cleaned.endswith("Z") else cleaned
        try:
            return _ensure_utc(datetime.fromisoformat(iso)).astimezone(timezone.utc)
        except ValueError:
            pass
        try:
            dt = parsedate_to_datetime(cleaned)
            return _ensure_utc(dt).astimezone(timezone.utc)
        except (TypeError, ValueError):
            return None
    return None


def detect_evergreen_signal(
    *,
    title: str | None = None,
    description: str | None = None,
    raw_fields: dict[str, Any] | None = None,
) -> str | None:
    """
    Detect an explicit evergreen/multi-hire signal without inferring from age or missing dates.

    Returns a short provenance tag (``ats_flag:<key>`` or ``statement:<match>``) or ``None``.
    """
    if isinstance(raw_fields, dict):
        for key in _EVERGREEN_FLAG_KEYS:
            if key in raw_fields and _is_truthy_flag(raw_fields.get(key)):
                return f"ats_flag:{key}"
        for key in _EVERGREEN_TYPE_KEYS:
            val = raw_fields.get(key)
            if isinstance(val, str) and val.strip().lower() == "evergreen":
                return f"ats_flag:{key}"
        metadata = raw_fields.get("metadata")
        if isinstance(metadata, list):
            for entry in metadata:
                if not isinstance(entry, dict):
                    continue
                name = str(entry.get("name") or "")
                if "evergreen" in name.lower() and _is_truthy_flag(entry.get("value")):
                    return "ats_flag:metadata"

    for text in (title, description):
        if not text or not isinstance(text, str):
            continue
        match = _EVERGREEN_STATEMENT_RE.search(text)
        if match:
            normalized = re.sub(r"\s+", " ", match.group(0).strip().lower())
            return f"statement:{normalized}"

    return None


def compute_freshness(
    *,
    posted_at: Any,
    first_seen_at: Any = None,
    evergreen_signal: str | None = None,
    explicit_freshness: FreshnessTier | str | None = None,
    now: datetime | None = None,
) -> FreshnessTier | None:
    """
    Derive canonical freshness tier from explicit evergreen signal, posting date, or observation age.
    """
    resolved_explicit: FreshnessTier | None = None
    if isinstance(explicit_freshness, FreshnessTier):
        resolved_explicit = explicit_freshness
    elif isinstance(explicit_freshness, str) and explicit_freshness.strip():
        try:
            resolved_explicit = FreshnessTier(explicit_freshness.strip().lower())
        except ValueError:
            resolved_explicit = None

    if (evergreen_signal and evergreen_signal.strip()) or resolved_explicit == FreshnessTier.EVERGREEN:
        return FreshnessTier.EVERGREEN

    ref_now = _ensure_utc(now or utc_now())

    posted_utc = parse_freshness_timestamp(posted_at)
    if posted_utc is not None:
        days = max(0, (ref_now - posted_utc).days)
        if days <= FRESH_MAX_DAYS:
            return FreshnessTier.FRESH
        if days <= RECENT_MAX_DAYS:
            return FreshnessTier.RECENT
        return FreshnessTier.STALE

    seen_utc = parse_freshness_timestamp(first_seen_at)
    if seen_utc is not None:
        if max(0, (ref_now - seen_utc).days) > RECENT_MAX_DAYS:
            return FreshnessTier.STALE

    return None


def compute_age_days(
    posted_at: Any,
    *,
    first_seen_at: Any = None,
    now: datetime | None = None,
) -> int | None:
    """Return non-negative age in whole days from ``posted_at`` (falling back to ``first_seen_at``)."""
    ref_dt = parse_freshness_timestamp(posted_at) or parse_freshness_timestamp(first_seen_at)
    if ref_dt is None:
        return None
    ref_now = _ensure_utc(now or utc_now())
    return max(0, (ref_now - ref_dt).days)


def hydrate_listing_freshness(
    job: T,
    *,
    first_discovered_at: Any = None,
    last_checked_at: Any = None,
) -> T:
    """Populate first_seen_at, last_verified_at, and derived freshness tier on a hydrated job."""
    if getattr(job, "first_seen_at", None) is None and first_discovered_at and float(first_discovered_at) > 0:
        setattr(job, "first_seen_at", datetime.fromtimestamp(float(first_discovered_at), tz=timezone.utc))
    if last_checked_at and float(last_checked_at) > 0:
        setattr(job, "last_verified_at", datetime.fromtimestamp(float(last_checked_at), tz=timezone.utc))
    setattr(
        job,
        "freshness",
        compute_freshness(
            posted_at=getattr(job, "posted_at", None),
            first_seen_at=getattr(job, "first_seen_at", None),
            evergreen_signal=getattr(job, "evergreen_signal", None),
            explicit_freshness=getattr(job, "freshness", None),
        ),
    )
    return job


def freshness_rank_key(job: Any) -> int:
    """Return primary sort rank for default relevance ordering (Fresh, Recent, Evergreen, Unknown, Stale)."""
    tier = getattr(job, "freshness", None)
    if isinstance(tier, str) and not isinstance(tier, FreshnessTier):
        try:
            tier = FreshnessTier(tier.lower())
        except ValueError:
            tier = None
    return FRESHNESS_TIER_ORDER.get(tier, FRESHNESS_TIER_ORDER[None])


def sort_jobs_by_freshness(jobs: Sequence[T]) -> list[T]:
    """Stably order jobs by freshness tier without changing intra-tier relative order."""
    return sorted(jobs, key=freshness_rank_key)
