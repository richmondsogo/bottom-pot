"""Boundary canonicalization and single-flight coordination for search requests."""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Iterable

if TYPE_CHECKING:
    from src.core.models import JobListing, ProviderOutcomeSummary, SearchParams

_CURLY_SINGLE_QUOTES_RE = re.compile(r"[\u2018\u2019\u201a\u201b]")
_CURLY_DOUBLE_QUOTES_RE = re.compile(r"[\u201c\u201d\u201e\u201f]")
_UNICODE_DASHES_RE = re.compile(r"[\u2010\u2011\u2012\u2013\u2014\u2015\u2212]")
_SLASH_SEP_RE = re.compile(r"\s*/\s*")
_COMMA_SEP_RE = re.compile(r"\s*,\s*")
_SEMI_SEP_RE = re.compile(r"\s*;\s*")
_COLON_SEP_RE = re.compile(r"\s*:\s*")
_WHITESPACE_RE = re.compile(r"\s+")


def canonicalize_query_text(text: str | None) -> str:
    """Normalize search text while preserving token order.

    Applies NFKC normalization, curly quote and dash normalization,
    casefolding, separator spacing normalization, and whitespace collapse.
    """
    if text is None:
        return ""
    normalized = unicodedata.normalize("NFKC", str(text))
    normalized = _CURLY_SINGLE_QUOTES_RE.sub("'", normalized)
    normalized = _CURLY_DOUBLE_QUOTES_RE.sub('"', normalized)
    normalized = _UNICODE_DASHES_RE.sub("-", normalized)
    normalized = normalized.strip().casefold()
    normalized = _SLASH_SEP_RE.sub("/", normalized)
    normalized = _COMMA_SEP_RE.sub(", ", normalized)
    normalized = _SEMI_SEP_RE.sub("; ", normalized)
    normalized = _COLON_SEP_RE.sub(": ", normalized)
    return _WHITESPACE_RE.sub(" ", normalized).strip()


def canonicalize_location(location: str | None) -> str | None:
    """Canonicalize an optional location filter, collapsing empty text to None."""
    if location is None:
        return None
    cleaned = canonicalize_query_text(location)
    return cleaned or None


def canonicalize_country_code(country_code: str | None) -> str | None:
    """Canonicalize an optional country code, collapsing empty text to None."""
    if country_code is None:
        return None
    cleaned = unicodedata.normalize("NFKC", str(country_code)).strip().casefold()
    return cleaned or None


def canonicalize_platforms(platforms: Iterable[str] | None) -> list[str] | None:
    """Return sorted unique lowercase platform IDs, preserving None vs []."""
    if platforms is None:
        return None
    cleaned = {
        unicodedata.normalize("NFKC", str(p)).strip().casefold()
        for p in platforms
        if p is not None and unicodedata.normalize("NFKC", str(p)).strip()
    }
    return sorted(cleaned)


def canonicalize_exclude_keywords(keywords: Iterable[str] | None) -> list[str]:
    """Return sorted unique canonicalized exclude keywords."""
    if not keywords:
        return []
    cleaned = {
        canonicalize_query_text(kw)
        for kw in keywords
        if kw is not None and canonicalize_query_text(kw)
    }
    return sorted(cleaned)


def canonicalize_search_request(
    params: SearchParams,
    platforms: list[str] | None = None,
) -> tuple[SearchParams, list[str] | None]:
    """Return canonicalized copies of (params, platforms) without mutating inputs."""
    canon_days_back = params.days_back if (params.days_back is not None and params.days_back > 0) else 7
    canon_experience = (
        canonicalize_query_text(params.experience_level) or None
        if params.experience_level is not None
        else None
    )
    canon_params = params.model_copy(
        update={
            "job_title": canonicalize_query_text(params.job_title),
            "location": canonicalize_location(params.location),
            "country_code": canonicalize_country_code(params.country_code),
            "applicant_country": canonicalize_country_code(params.applicant_country),
            "exclude_keywords": canonicalize_exclude_keywords(params.exclude_keywords),
            "experience_level": canon_experience,
            "days_back": canon_days_back,
        }
    )
    return canon_params, canonicalize_platforms(platforms)


def compute_effective_max_results(params: SearchParams, settings_max_results: int) -> int:
    """Compute effective max_results honoring explicit caller cap vs configured default."""
    if "max_results" in params.model_fields_set and params.max_results is not None:
        return min(params.max_results, settings_max_results)
    return settings_max_results


def build_search_cache_key(
    params: SearchParams,
    platforms: list[str] | None,
    *,
    store_ver: int,
    relevance_mode: str,
    serper_mode: str,
    settings_max_results: int,
) -> str:
    """Build deterministic canonical JSON hash for whole-search cache & single-flight."""
    canon_params, canon_platforms = canonicalize_search_request(params, platforms)
    effective_max = compute_effective_max_results(canon_params, settings_max_results)
    payload = {
        "schema": "api-v4-canonical",
        "store_ver": store_ver,
        "relevance_mode": (relevance_mode or "").strip().casefold(),
        "serper_mode": (serper_mode or "").strip().casefold(),
        "effective_max_results": effective_max,
        "job_title": canon_params.job_title,
        "location": canon_params.location,
        "salary_min": canon_params.salary_min,
        "experience_level": canon_params.experience_level,
        "exclude_keywords": canon_params.exclude_keywords or [],
        "remote": canon_params.remote,
        "days_back": canon_params.days_back,
        "country_code": canon_params.country_code,
        "include_nigerian_sites": canon_params.include_nigerian_sites,
        "live_discovery": canon_params.live_discovery,
        "platforms": canon_platforms,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:24]


def build_serper_cache_key(payload: dict[str, Any]) -> str:
    """Build versioned canonical JSON hash for persistent Serper query cache."""
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "serper-v2:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()


@dataclass
class SingleFlightResult:
    """Country-neutral search output shared from a single-flight leader to followers."""

    results: list[JobListing]
    providers_searched: list[str]
    providers_skipped: list[str]
    serper_calls: int
    serper_cache_hits: int
    pages_fetched: int
    budget_exhausted: bool
    message: str | None
    dropped_count: dict[str, int]
    provider_outcomes: dict[str, ProviderOutcomeSummary]
    partial: bool
    was_cached: bool


@dataclass
class SingleFlightEntry:
    """Synchronization state for one in-flight canonical search key."""

    done_event: asyncio.Event = field(default_factory=asyncio.Event)
    result: SingleFlightResult | None = None
    failed_or_cancelled: bool = False


class SingleFlightRegistry:
    """Coalesces identical concurrent searches by canonical cache key."""

    def __init__(self) -> None:
        self._inflight: dict[str, SingleFlightEntry] = {}

    def acquire(self, key: str) -> tuple[SingleFlightEntry, bool]:
        """Join an active flight for *key* or become its leader."""
        existing = self._inflight.get(key)
        if existing is not None:
            return existing, False
        entry = SingleFlightEntry()
        self._inflight[key] = entry
        return entry, True

    def complete(self, key: str, entry: SingleFlightEntry, result: SingleFlightResult) -> None:
        """Publish successful leader result and wake all followers."""
        entry.result = result
        if self._inflight.get(key) is entry:
            del self._inflight[key]
        entry.done_event.set()

    def abort(self, key: str, entry: SingleFlightEntry) -> None:
        """Mark leader aborted/failed, evict flight slot, and wake followers to retry."""
        entry.failed_or_cancelled = True
        if self._inflight.get(key) is entry:
            del self._inflight[key]
        entry.done_event.set()


async def wait_for_single_flight(
    entry: SingleFlightEntry,
    is_disconnected: Callable[[], Awaitable[bool]] | None = None,
) -> bool | None:
    """Wait for an in-flight leader without cancelling it if this follower disconnects.

    Returns True if the leader produced a usable result, False if the leader failed or
    was cancelled (caller should retry), or None if this follower's client disconnected.
    """
    wait_task = asyncio.create_task(entry.done_event.wait())
    try:
        while not entry.done_event.is_set():
            if is_disconnected and await is_disconnected():
                return None
            if is_disconnected:
                await asyncio.wait({wait_task}, timeout=0.2)
            else:
                await wait_task
        return not entry.failed_or_cancelled
    finally:
        if not wait_task.done():
            wait_task.cancel()
