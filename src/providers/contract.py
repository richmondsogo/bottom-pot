"""
Shared monitored-provider contract types, failure taxonomy, reconciliation policy,
and cross-poll ID-drift detection (Step 57 Phase 4).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import json
from typing import TYPE_CHECKING, Any, Iterable, Mapping

import httpx
from loguru import logger

from src.core.http_resilience import (
    CircuitBreakerOpenError,
    HostRateLimitedError,
    ResponseTooLargeError,
)
from src.extraction.url_normalizer import normalize_job_url
from src.safety.url_safety import UnsafeRedirectError

if TYPE_CHECKING:
    from src.core.models import JobListing
    from src.storage.company_board_registry import CompanyBoardRegistry, MonitoredJobDetailState


class FailureKind(str, Enum):
    """Closed classification taxonomy for monitored provider poll failures."""

    NOT_FOUND = "not_found"
    RATE_LIMITED = "rate_limited"
    CIRCUIT_OPEN = "circuit_open"
    RESPONSE_TOO_LARGE = "response_too_large"
    UNSAFE_URL = "unsafe_url"
    HTTP_ERROR = "http_error"
    TIMEOUT = "timeout"
    NETWORK_ERROR = "network_error"
    PARSE_ERROR = "parse_error"
    INCOMPLETE_SNAPSHOT = "incomplete_snapshot"
    UNSUPPORTED_PROVIDER = "unsupported_provider"
    UNEXPECTED_ERROR = "unexpected_error"


@dataclass(frozen=True)
class ReconciliationPolicy:
    """Central policy governing missing-job confirmation and closure per board poll."""

    missing_confirmation_threshold: int = 1
    require_complete_snapshot: bool = True
    close_on_empty_snapshot: bool = True

    def reconcile(
        self,
        registry: "CompanyBoardRegistry",
        board_id: int,
        result: "BoardCheckResult",
        *,
        provider: str = "",
        board_token: str = "",
    ) -> tuple[int, int]:
        """Execute missing-job reconciliation/closure against *registry* under this policy."""
        if self.require_complete_snapshot and not result.snapshot_complete:
            reason = result.incomplete_reason or result.error or "incomplete_snapshot"
            logger.warning(
                f"[monitor] Incomplete snapshot for {provider}:{board_token} ({reason}); "
                "skipping missing-job reconciliation/closure."
            )
            return 0, 0

        active_job_ids = {j.id for j in result.listings}
        if not active_job_ids and not self.close_on_empty_snapshot:
            logger.warning(
                f"[monitor] Empty snapshot blocked from closure by policy for {provider}:{board_token}."
            )
            return 0, 0

        threshold = max(1, int(self.missing_confirmation_threshold))
        if threshold <= 1:
            return registry.mark_missing_jobs_closed(board_id, active_job_ids), 0
        return registry.reconcile_missing_jobs(
            board_id,
            active_job_ids,
            confirm_threshold=threshold,
        )


PROVIDER_RECONCILIATION_POLICIES: dict[str, ReconciliationPolicy] = {
    "greenhouse": ReconciliationPolicy(missing_confirmation_threshold=1),
    "lever": ReconciliationPolicy(missing_confirmation_threshold=1),
    "ashby": ReconciliationPolicy(missing_confirmation_threshold=1),
    "workable": ReconciliationPolicy(missing_confirmation_threshold=1),
    "recruitee": ReconciliationPolicy(missing_confirmation_threshold=1),
    "smartrecruiters": ReconciliationPolicy(missing_confirmation_threshold=2),
    "teamtailor": ReconciliationPolicy(missing_confirmation_threshold=2),
    "personio": ReconciliationPolicy(missing_confirmation_threshold=2),
    "pinpointhq": ReconciliationPolicy(missing_confirmation_threshold=2),
}


def get_reconciliation_policy(provider: str) -> ReconciliationPolicy:
    """Return the canonical ``ReconciliationPolicy`` for a monitored *provider*."""
    return PROVIDER_RECONCILIATION_POLICIES.get(
        (provider or "").strip().lower(),
        ReconciliationPolicy(missing_confirmation_threshold=1),
    )


@dataclass(frozen=True)
class IdDriftEvent:
    """Records a tracked posting whose canonical URL stayed the same while job_id changed."""

    canonical_url: str
    previous_job_id: str
    current_job_id: str
    provider: str = ""
    board_token: str = ""


def _iter_listings(
    items: Mapping[str, Any] | Iterable[Any],
) -> Iterable["JobListing"]:
    seq = items.values() if isinstance(items, Mapping) else items
    for entry in seq:
        if isinstance(entry, tuple) and entry:
            yield entry[0]
        else:
            yield entry


def _canonical_identity_url(listing: "JobListing") -> str:
    raw_url = (getattr(listing, "source_url", None) or getattr(listing, "apply_url", None) or "").strip()
    if not raw_url:
        return ""
    return normalize_job_url(raw_url) or raw_url


def detect_id_drift(
    previous_listings: Mapping[str, Any] | Iterable[Any],
    current_listings: Iterable["JobListing"],
    *,
    provider: str = "",
    board_token: str = "",
) -> list[IdDriftEvent]:
    """
    Compare *previous_listings* against *current_listings* and flag any job whose
    canonical URL matches a previously active job under a different ``id`` (excluding
    declared ``aliases``).
    """
    prev_by_url: dict[str, "JobListing"] = {}
    for prev in _iter_listings(previous_listings):
        url_key = _canonical_identity_url(prev)
        if url_key:
            prev_by_url[url_key] = prev

    events: list[IdDriftEvent] = []
    for cur in current_listings:
        url_key = _canonical_identity_url(cur)
        if not url_key:
            continue
        prev = prev_by_url.get(url_key)
        if prev is None or prev.id == cur.id:
            continue
        cur_aliases = set(getattr(cur, "aliases", None) or ())
        prev_aliases = set(getattr(prev, "aliases", None) or ())
        if prev.id in cur_aliases or cur.id in prev_aliases:
            continue
        events.append(
            IdDriftEvent(
                canonical_url=url_key,
                previous_job_id=prev.id,
                current_job_id=cur.id,
                provider=provider or getattr(cur, "provider", ""),
                board_token=board_token,
            )
        )
    return events


def classify_http_status(status_code: int) -> FailureKind:
    """Map a non-2xx/304 HTTP status code into the closed ``FailureKind`` enum."""
    if status_code == 404:
        return FailureKind.NOT_FOUND
    if status_code == 429:
        return FailureKind.RATE_LIMITED
    return FailureKind.HTTP_ERROR


def classify_exception(exc: BaseException) -> FailureKind:
    """Map an outbound fetch/parse exception into the closed ``FailureKind`` enum."""
    if isinstance(exc, CircuitBreakerOpenError):
        return FailureKind.CIRCUIT_OPEN
    if isinstance(exc, HostRateLimitedError):
        return FailureKind.RATE_LIMITED
    if isinstance(exc, ResponseTooLargeError):
        return FailureKind.RESPONSE_TOO_LARGE
    if isinstance(exc, UnsafeRedirectError):
        return FailureKind.UNSAFE_URL
    if isinstance(exc, (httpx.TimeoutException, TimeoutError)):
        return FailureKind.TIMEOUT
    if isinstance(exc, (httpx.HTTPError, OSError)):
        return FailureKind.NETWORK_ERROR
    if isinstance(exc, (json.JSONDecodeError, UnicodeDecodeError, ValueError)):
        return FailureKind.PARSE_ERROR
    return FailureKind.UNEXPECTED_ERROR


def classify_error_message(error: str | None) -> FailureKind:
    """Infer a ``FailureKind`` when legacy callers construct ``BoardCheckResult(success=False)``."""
    text = (error or "").strip().lower()
    if not text:
        return FailureKind.UNEXPECTED_ERROR
    if "404" in text:
        return FailureKind.NOT_FOUND
    if "429" in text or "rate limit" in text:
        return FailureKind.RATE_LIMITED
    if "circuit breaker" in text:
        return FailureKind.CIRCUIT_OPEN
    if "exceeded" in text and "bytes" in text:
        return FailureKind.RESPONSE_TOO_LARGE
    if "unsafe" in text or "invalid" in text and "token" in text or "tenant mismatch" in text:
        return FailureKind.UNSAFE_URL
    if "timeout" in text or "timed out" in text:
        return FailureKind.TIMEOUT
    if "incomplete" in text or "duplicate" in text or "drift" in text:
        return FailureKind.INCOMPLETE_SNAPSHOT
    if "malformed" in text or "json" in text or "xml" in text or "shape" in text or "empty" in text:
        return FailureKind.PARSE_ERROR
    if "no monitor adapter" in text or "unsupported" in text:
        return FailureKind.UNSUPPORTED_PROVIDER
    if "http " in text:
        return FailureKind.HTTP_ERROR
    return FailureKind.UNEXPECTED_ERROR


@dataclass
class BoardCheckResult:
    """Unified snapshot result returned by every monitored board adapter."""

    success: bool
    not_modified: bool = False
    listings: list["JobListing"] = field(default_factory=list)
    etag: str | None = None
    last_modified: str | None = None
    content_fingerprint: str | None = None
    error: str | None = None
    refreshed_job_ids: set[str] | None = None
    detail_states: dict[str, "MonitoredJobDetailState"] | None = None
    missing_confirmation_threshold: int = 1
    snapshot_complete: bool = True
    failure_kind: FailureKind | None = None
    incomplete_reason: str | None = None
    reconciliation_policy: ReconciliationPolicy | None = None
    id_drift_events: list[IdDriftEvent] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.reconciliation_policy is not None:
            self.missing_confirmation_threshold = (
                self.reconciliation_policy.missing_confirmation_threshold
            )
        if not self.success:
            self.snapshot_complete = False
            if self.failure_kind is None:
                self.failure_kind = classify_error_message(self.error)
            if self.incomplete_reason is None:
                self.incomplete_reason = self.error or self.failure_kind.value
        elif not self.snapshot_complete and not self.incomplete_reason:
            self.incomplete_reason = self.error or "incomplete_snapshot"


SnapshotResult = BoardCheckResult


def failure_result(
    *,
    kind: FailureKind,
    error: str,
    policy: ReconciliationPolicy | None = None,
) -> BoardCheckResult:
    """Construct a fail-closed ``BoardCheckResult`` with an explicit ``FailureKind``."""
    return BoardCheckResult(
        success=False,
        snapshot_complete=False,
        failure_kind=kind,
        incomplete_reason=error,
        error=error,
        reconciliation_policy=policy,
    )
