"""
Shared two-step detail hydration retry backoff, priority scheduling, batch fetching,
and detail-state helpers.

Used by providers that fetch an initial board summary feed and hydrate full job
details lazily with bounded per-poll budgets (Workable, SmartRecruiters).
"""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Sequence

import httpx

from src.core.exceptions import SafetyError
from src.core.http_resilience import CircuitBreakerOpenError, HostRateLimitedError
from src.providers.http import build_conditional_headers, fetch_provider_bytes
from src.safety.url_safety import DnsResolver
from src.storage.company_board_registry import MonitoredJobDetailState

if TYPE_CHECKING:
    from src.core.models import JobListing


TRANSIENT_RETRY_BACKOFF_SECONDS: tuple[float, ...] = (
    300.0,
    900.0,
    1800.0,
    3600.0,
    7200.0,
    21600.0,
)
DETAIL_404_RETRY_BACKOFF_SECONDS: tuple[float, ...] = (
    3600.0,
    7200.0,
    14400.0,
    21600.0,
)


def compute_detail_retry_delay(
    detail_status: str,
    retry_count: int,
    *,
    ttl_seconds: float = 21600.0,
) -> float:
    """Compute bounded exponential-style backoff delay for deferred detail fetches."""
    if detail_status == "widget_fallback":
        return 0.0
    schedule = (
        DETAIL_404_RETRY_BACKOFF_SECONDS
        if detail_status == "detail_404"
        else TRANSIENT_RETRY_BACKOFF_SECONDS
    )
    idx = max(0, min(int(retry_count) - 1, len(schedule) - 1))
    delay = schedule[idx]
    if ttl_seconds > 0:
        return min(delay, float(ttl_seconds))
    return delay


def classify_detail_candidate(
    now: float,
    cached_entry: tuple["JobListing", float] | None,
    detail_state: MonitoredJobDetailState | None,
    detail_revalidate_ttl_seconds: float,
) -> tuple[bool, int, float]:
    """Return ``(is_due, priority_tier, sort_ts)`` for stale/retry candidate selection."""
    if cached_entry is None:
        return True, 0, 0.0
    _, last_checked_at = cached_entry
    last_checked = float(last_checked_at or 0.0)
    status = detail_state.detail_status if detail_state is not None else "hydrated"
    retry_at = detail_state.detail_next_retry_at if detail_state is not None else None
    hydrated_at = detail_state.detail_last_hydrated_at if detail_state is not None else None

    if status in ("widget_fallback", "transient_error", "invalid_detail"):
        is_due = retry_at is None or now >= float(retry_at)
        tier = 0 if hydrated_at is None else 1
        sort_ts = float(retry_at) if retry_at is not None else last_checked
        return is_due, tier, sort_ts
    if status == "detail_404":
        is_due = retry_at is None or now >= float(retry_at)
        sort_ts = float(retry_at) if retry_at is not None else last_checked
        return is_due, 2, sort_ts

    is_due = (now - last_checked) >= detail_revalidate_ttl_seconds
    return is_due, 1, last_checked


def resolve_prev_hydrated_at(
    prev_state: MonitoredJobDetailState | None,
    cached_entry: tuple["JobListing", float] | None,
) -> float | None:
    """Resolve the prior hydration timestamp, falling back to cache check time for legacy hydrated rows."""
    prev_hydrated_at = prev_state.detail_last_hydrated_at if prev_state is not None else None
    if (
        prev_hydrated_at is None
        and prev_state is not None
        and prev_state.detail_status == "hydrated"
        and cached_entry is not None
        and cached_entry[1] > 0
    ):
        prev_hydrated_at = float(cached_entry[1])
    return prev_hydrated_at


def select_fair_detail_hydration_batch(
    *,
    immediate_ids: Sequence[str] = (),
    pending_old: list[tuple[float, int, str]] | None = None,
    changed_known: Sequence[tuple[int, str]] = (),
    brand_new: Sequence[tuple[int, str]] = (),
    stale_candidates: list[tuple[int, float, str]] | None = None,
    max_new_hydrations_per_poll: int | None = None,
    max_revalidations_per_poll: int = 10,
    max_detail_fetches: int | None = None,
) -> list[str]:
    """Select bounded fair detail-fetch IDs prioritizing pending/changed/new work ahead of revalidation."""
    sorted_pending = sorted(pending_old, key=lambda e: (e[0], e[1])) if pending_old else []
    new_queue = [
        *immediate_ids,
        *(pid for _, _, pid in sorted_pending),
        *(pid for _, pid in changed_known),
        *(pid for _, pid in brand_new),
    ]
    if max_new_hydrations_per_poll is not None:
        selected_new = new_queue[: max(0, int(max_new_hydrations_per_poll))]
    else:
        selected_new = new_queue

    sorted_stale = (
        sorted(stale_candidates, key=lambda e: (e[0], e[1])) if stale_candidates else []
    )
    selected_reval = [
        pid for _, _, pid in sorted_stale[: max(0, int(max_revalidations_per_poll))]
    ]
    fetch_ids = selected_new + selected_reval
    if max_detail_fetches is not None and len(fetch_ids) > max_detail_fetches:
        return fetch_ids[: max(0, int(max_detail_fetches))]
    return fetch_ids


async def fetch_detail_json_batch(
    client: httpx.AsyncClient,
    item_urls: Sequence[tuple[str, str]],
    *,
    concurrency: int = 3,
    timeout: float = 10.0,
    max_bytes: int | None = None,
    resolver: DnsResolver | None = None,
) -> dict[str, tuple[int | None, dict | None, str | None]]:
    """Fetch bounded-concurrency JSON detail payloads via shared SSRF-validated HTTP transport."""
    if not item_urls:
        return {}

    sem = asyncio.Semaphore(max(1, int(concurrency)))

    async def _fetch_one(item_id: str, url: str) -> tuple[str, int | None, dict | None, str | None]:
        async with sem:
            try:
                status_code, body_bytes, _ = await fetch_provider_bytes(
                    client,
                    url,
                    headers=build_conditional_headers(url, "application/json"),
                    timeout=timeout,
                    max_bytes=max_bytes,
                    resolver=resolver,
                )
            except (asyncio.CancelledError, SafetyError):
                raise
            except CircuitBreakerOpenError:
                return item_id, None, None, "circuit_breaker_open"
            except HostRateLimitedError:
                return item_id, None, None, "host_rate_limited"
            except Exception:  # broad-except-ok: per-detail batch fetch returns network_or_timeout sentinel  # noqa: BLE001
                return item_id, None, None, "network_or_timeout"

            if status_code != 200:
                return item_id, status_code, None, None
            try:
                payload = json.loads(body_bytes.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError):
                return item_id, 200, None, "invalid_detail_json"
            if not isinstance(payload, dict):
                return item_id, 200, None, "invalid_detail_json"
            return item_id, 200, payload, None

    fetched = await asyncio.gather(*(_fetch_one(item_id, url) for item_id, url in item_urls))
    return {item_id: (status_code, payload, err_reason) for item_id, status_code, payload, err_reason in fetched}


def build_hydrated_detail_state(
    now: float,
    *,
    widget_location_signature: str | None = None,
    listing_item_hash: str | None = None,
) -> MonitoredJobDetailState:
    """Create the state record for a freshly hydrated job detail."""
    return MonitoredJobDetailState(
        detail_status="hydrated",
        detail_last_hydrated_at=now,
        detail_retry_count=0,
        detail_next_retry_at=None,
        detail_last_error=None,
        widget_location_signature=widget_location_signature,
        listing_item_hash=listing_item_hash,
    )


def build_detail_failure_state(
    *,
    status_code: int | None,
    err_reason: str | None,
    prev_state: MonitoredJobDetailState | None,
    prev_hydrated_at: float | None,
    now: float,
    ttl_seconds: float,
    invalid_detail_override: bool = False,
    widget_location_signature: str | None = None,
    listing_item_hash: str | None = None,
) -> MonitoredJobDetailState:
    """Build retry/backoff state after a failed or incomplete detail fetch."""
    retry_count = (prev_state.detail_retry_count + 1) if prev_state is not None else 1
    if invalid_detail_override:
        detail_status = "invalid_detail"
        err_msg = err_reason or "invalid_or_incomplete_detail"
    elif status_code == 404:
        detail_status = "detail_404"
        err_msg = "http_404"
    elif status_code == 200:
        detail_status = "invalid_detail"
        err_msg = err_reason or "invalid_detail_json"
    else:
        detail_status = "transient_error"
        err_msg = err_reason or (f"http_{status_code}" if status_code is not None else "network_or_timeout")

    delay = compute_detail_retry_delay(detail_status, retry_count, ttl_seconds=ttl_seconds)
    return MonitoredJobDetailState(
        detail_status=detail_status,
        detail_last_hydrated_at=prev_hydrated_at,
        detail_retry_count=retry_count,
        detail_next_retry_at=now + delay,
        detail_last_error=err_msg,
        widget_location_signature=widget_location_signature,
        listing_item_hash=listing_item_hash,
    )


def preserve_cached_detail_state(
    prev_state: MonitoredJobDetailState | None,
    prev_hydrated_at: float | None,
    cached_entry: tuple["JobListing", float],
    now: float,
    *,
    widget_location_signature: str | None = None,
    listing_item_hash: str | None = None,
) -> MonitoredJobDetailState:
    """Carry forward existing detail state for an unchanged cached job skipped this poll."""
    if prev_state is not None:
        return MonitoredJobDetailState(
            detail_status=prev_state.detail_status,
            detail_last_hydrated_at=prev_hydrated_at,
            detail_retry_count=prev_state.detail_retry_count,
            detail_next_retry_at=prev_state.detail_next_retry_at,
            detail_last_error=prev_state.detail_last_error,
            widget_location_signature=widget_location_signature or prev_state.widget_location_signature,
            listing_item_hash=prev_state.listing_item_hash or listing_item_hash,
        )
    return MonitoredJobDetailState(
        detail_status="hydrated",
        detail_last_hydrated_at=float(cached_entry[1]) if cached_entry[1] > 0 else now,
        detail_retry_count=0,
        detail_next_retry_at=None,
        detail_last_error=None,
        widget_location_signature=widget_location_signature,
        listing_item_hash=listing_item_hash,
    )


def build_deferred_detail_state(
    now: float,
    *,
    detail_status: str = "widget_fallback",
    last_error: str = "deferred_widget_fallback",
    widget_location_signature: str | None = None,
    listing_item_hash: str | None = None,
) -> MonitoredJobDetailState:
    """Create initial pending state when a newly seen job is deferred beyond poll budget."""
    return MonitoredJobDetailState(
        detail_status=detail_status,
        detail_last_hydrated_at=None,
        detail_retry_count=0,
        detail_next_retry_at=now,
        detail_last_error=last_error,
        widget_location_signature=widget_location_signature,
        listing_item_hash=listing_item_hash,
    )
