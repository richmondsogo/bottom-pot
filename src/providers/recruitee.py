"""
Recruitee company-board monitoring adapter.
"""

from __future__ import annotations

import asyncio
import json
from urllib.parse import quote

import httpx

from src.core.clock import Clock, use_clock
from src.core.exceptions import SafetyError
from src.core.models import JobListing
from src.core.settings import settings
from src.extraction.canonical_job_adapter import CanonicalJobAdapter
from src.extraction.field_normalizer import humanize_slug
from src.extraction.job_extraction_service import JobExtractionService
from src.providers.contract import (
    BoardCheckResult,
    FailureKind,
    classify_exception,
    classify_http_status,
    failure_result,
    get_reconciliation_policy,
)
from src.providers.fingerprint import canonical_content_hash, compute_board_fingerprint
from src.providers.http import (
    build_conditional_headers,
    fetch_provider_bytes,
    validate_board_token_safety,
)
from src.safety.url_safety import DnsResolver, UnsafeRedirectError
from src.storage.company_board_registry import CompanyBoard


def _recruitee_job_content_hash(offer: dict) -> str:
    """
    Deterministic canonical full-payload SHA-256 hex digest across all Recruitee offer fields.
    """
    return canonical_content_hash(offer)


_RECRUITEE_ACTIVE_STATUSES: frozenset[str] = frozenset({"published"})
# Documented Recruitee API offer statuses excluded from public careers-board listings:
# `closed`, `archived`, and `draft` are inactive states; `internal` ("Use internally")
# is excluded from public board listings rather than necessarily closed or inapplicable.
_RECRUITEE_EXCLUDED_STATUSES: frozenset[str] = frozenset({"closed", "archived", "draft", "internal"})


def _recruitee_offer_is_active(offer: dict) -> bool:
    status = offer.get("status")
    if status is None:
        return True
    if isinstance(status, str):
        return status.strip().lower() in _RECRUITEE_ACTIVE_STATUSES
    return False


def _validate_recruitee_offer_record(offer: object) -> tuple[bool, str | None]:
    """
    Validate a single entry from Recruitee ``{"offers": [...]}``.

    Returns ``(is_active, error_message)``:
    - Non-dict entries, empty/non-string statuses, or unrecognized statuses return ``(False, error)``.
    - Explicitly recognized non-public or inactive Recruitee statuses (``closed``,
      ``archived``, ``draft``, ``internal``) are excluded from public careers-board listings
      and return ``(False, None)`` (``internal`` indicates public-board exclusion, not
      necessarily that the role is closed).
    - Active entries (``published`` or missing status) must supply both identity (``id`` or ``slug``)
      and title (``title`` or ``position``); otherwise they return ``(False, error)``.
    """
    if not isinstance(offer, dict):
        return False, "Malformed Recruitee offer entry (expected object)"

    status = offer.get("status")
    if status is not None:
        if not isinstance(status, str) or not status.strip():
            return False, "Malformed Recruitee offer status"
        norm_status = status.strip().lower()
        if norm_status in _RECRUITEE_EXCLUDED_STATUSES:
            return False, None
        if norm_status not in _RECRUITEE_ACTIVE_STATUSES:
            return False, f"Unrecognized Recruitee offer status: {status.strip()!r}"

    raw_id = offer.get("id")
    has_id = (
        raw_id is not None
        and not isinstance(raw_id, (bool, list, dict))
        and bool(str(raw_id).strip())
    )
    raw_slug = offer.get("slug")
    has_slug = isinstance(raw_slug, str) and bool(raw_slug.strip())
    if not (has_id or has_slug):
        return False, "Malformed active Recruitee offer missing required identity"

    raw_title = offer.get("title")
    raw_position = offer.get("position")
    has_title = (
        (isinstance(raw_title, str) and bool(raw_title.strip()))
        or (isinstance(raw_position, str) and bool(raw_position.strip()))
    )
    if not has_title:
        return False, "Malformed active Recruitee offer missing required title"

    return True, None


def validate_recruitee_offers_snapshot(raw_offers: object) -> tuple[list[dict] | None, str | None]:
    """
    Validate a complete Recruitee ``offers`` snapshot array before hydration.

    Shared by ``RecruiteeBoardAdapter.check_board`` and ``probe_recruitee_board`` so both
    monitoring and direct discovery reject incomplete snapshots, duplicate IDs, or
    unrecognized statuses without returning partial listings or triggering false closures.
    """
    if not isinstance(raw_offers, list):
        return None, "Invalid Recruitee offers payload shape"

    active_offers: list[dict] = []
    seen_ids: set[str] = set()
    for entry in raw_offers:
        is_active, validation_error = _validate_recruitee_offer_record(entry)
        if validation_error:
            return None, validation_error
        if is_active:
            assert isinstance(entry, dict)
            raw_id = entry.get("id")
            jid = (
                str(raw_id).strip()
                if raw_id is not None and not isinstance(raw_id, (bool, list, dict)) and str(raw_id).strip()
                else str(entry.get("slug") or "").strip()
            )
            if jid in seen_ids:
                return None, f"Duplicate Recruitee offer id in snapshot: {jid}"
            seen_ids.add(jid)
            active_offers.append(entry)
    return active_offers, None


async def hydrate_recruitee_offers(
    slug: str,
    raw_offers: list,
    client: httpx.AsyncClient,
    *,
    board_company_name: str | None = None,
    board_logo_url: str | None = None,
    board_logo_source: str | None = None,
    board_logo_verified: bool = False,
    board_logo_checked_at: float | None = None,
    registry: object | None = None,
    is_board_monitor: bool = False,
) -> list[JobListing]:
    """
    Shared single-request Recruitee offer-list -> JobListing hydration helper
    used by both ``RecruiteeBoardAdapter`` and ``probe_recruitee_board``.
    """
    from src.ats.ats_api_client import (
        enrich_recruitee_board_identity,
        recruitee_payload_to_raw,
    )
    from src.extraction.logo_extractor import LogoResult

    clean_slug = slug.strip().lower()
    active_offers = [
        o for o in raw_offers
        if isinstance(o, dict) and _recruitee_offer_is_active(o)
    ]
    if not active_offers:
        return []

    company_name = board_company_name or humanize_slug(clean_slug)
    first_careers_url = next(
        (
            str(o.get("careers_url")).strip()
            for o in active_offers
            if isinstance(o.get("careers_url"), str) and o.get("careers_url", "").strip()
        ),
        None,
    )
    for o in active_offers:
        cn = o.get("company_name")
        if isinstance(cn, str) and cn.strip():
            company_name = cn.strip()
            break

    resolved_logo = (
        LogoResult(
            url=board_logo_url,
            source=board_logo_source,
            raw_value=board_logo_url,
            verified=bool(board_logo_verified),
        )
        if board_logo_url and board_logo_verified
        else LogoResult()
    )
    if not resolved_logo.url and board_logo_checked_at is None:
        try:
            _, enriched_logo = await enrich_recruitee_board_identity(
                clean_slug,
                client,
                registry=registry,
                use_resilience=True,
                fallback_offer_url=first_careers_url,
                company_name=company_name,
            )
            if enriched_logo.url and enriched_logo.verified:
                resolved_logo = enriched_logo
        except (asyncio.CancelledError, SafetyError):
            raise
        except Exception:
            pass

    listings: list[JobListing] = []
    for item in active_offers:
        raw = recruitee_payload_to_raw(
            item,
            company_slug=clean_slug,
            default_company_name=company_name,
            company_logo_url=resolved_logo.url if resolved_logo.verified else None,
            company_logo_source=resolved_logo.source if resolved_logo.verified else None,
            company_logo_verified=bool(resolved_logo.verified and resolved_logo.url),
            query_used=clean_slug,
        )
        if raw is None or not raw.raw_title or not raw.source_url:
            continue
        if is_board_monitor:
            raw.raw_fields["is_board_monitor"] = True
        canonical = JobExtractionService.extract(raw)
        listing = CanonicalJobAdapter.to_listing(canonical)
        listing.provider = "recruitee"
        listing.ats_source = "recruitee"
        listing.data_source = "api"
        if resolved_logo.verified and resolved_logo.url and not listing.company_logo_url:
            listing.company_logo_url = resolved_logo.url
            listing.company_logo_source = resolved_logo.source
            listing.company_logo_verified = True
        listings.append(listing)
    return listings


class RecruiteeBoardAdapter:
    """
    Recruitee company-board adapter.
    Public endpoint: GET https://{slug}.recruitee.com/api/offers/
    Returns full offer payloads in a single request (no detail hydration needed).
    """

    async def check_board(
        self,
        board: CompanyBoard,
        client: httpx.AsyncClient,
        timeout: float = 8.0,
        clock: Clock | None = None,
        resolver: DnsResolver | None = None,
        max_response_bytes: int | None = None,
        **kwargs,
    ) -> BoardCheckResult:
        from src.storage.company_board_registry import is_valid_board_slug

        policy = get_reconciliation_policy("recruitee")
        if not validate_board_token_safety(board.board_token) or not is_valid_board_slug(
            "recruitee", board.board_token
        ):
            return failure_result(
                kind=FailureKind.UNSAFE_URL,
                error="Invalid Recruitee board token",
                policy=policy,
            )

        encoded_slug = quote(board.board_token.strip().lower(), safe="-_.~")
        url = f"https://{encoded_slug}.recruitee.com/api/offers/"
        headers = build_conditional_headers(
            url,
            "application/json",
            etag=board.etag,
            last_modified=board.last_modified,
            accept_gzip=True,
        )

        max_bytes = (
            int(max_response_bytes)
            if max_response_bytes is not None
            else int(kwargs.get("max_response_bytes") or settings.recruitee_board_max_response_bytes)
        )
        with use_clock(clock):
            try:
                status, body_bytes, resp_headers = await fetch_provider_bytes(
                    client,
                    url,
                    headers=headers,
                    timeout=timeout,
                    max_bytes=max_bytes,
                    follow_redirects=False,
                    resolver=resolver,
                )
                if status == 304:
                    return BoardCheckResult(
                        success=True,
                        not_modified=True,
                        etag=resp_headers.get("etag") or board.etag,
                        last_modified=resp_headers.get("last-modified") or board.last_modified,
                        content_fingerprint=board.content_fingerprint,
                        reconciliation_policy=policy,
                    )
                if status == 404:
                    return failure_result(
                        kind=FailureKind.NOT_FOUND,
                        error="Board not found (HTTP 404)",
                        policy=policy,
                    )
                if status != 200:
                    return failure_result(
                        kind=classify_http_status(status),
                        error=f"HTTP {status}",
                        policy=policy,
                    )

                try:
                    data = json.loads(body_bytes.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError) as exc:
                    return failure_result(
                        kind=FailureKind.PARSE_ERROR,
                        error=f"Invalid Recruitee JSON payload: {exc}",
                        policy=policy,
                    )

                if not isinstance(data, dict) or "offers" not in data or not isinstance(data.get("offers"), list):
                    return failure_result(
                        kind=FailureKind.PARSE_ERROR,
                        error="Invalid Recruitee offers payload shape",
                        policy=policy,
                    )

                active_offers, validation_error = validate_recruitee_offers_snapshot(data["offers"])
                if validation_error or active_offers is None:
                    kind = (
                        FailureKind.INCOMPLETE_SNAPSHOT
                        if validation_error and "duplicate" in validation_error.lower()
                        else FailureKind.PARSE_ERROR
                    )
                    return failure_result(
                        kind=kind,
                        error=validation_error or "Invalid Recruitee offers payload shape",
                        policy=policy,
                    )

                new_etag = resp_headers.get("etag")
                new_last_mod = resp_headers.get("last-modified")
                fingerprint_items: list[tuple[str, str | None, str | None]] = []
                for o in active_offers:
                    raw_id = o.get("id")
                    jid = (
                        str(raw_id).strip()
                        if raw_id is not None and str(raw_id).strip()
                        else str(o.get("slug") or "").strip()
                    )
                    ts = str(o.get("updated_at") or o.get("published_at") or "")
                    ch = _recruitee_job_content_hash(o)
                    fingerprint_items.append((jid, ts, ch))

                fingerprint = compute_board_fingerprint(fingerprint_items)

                if board.content_fingerprint and fingerprint == board.content_fingerprint:
                    return BoardCheckResult(
                        success=True,
                        not_modified=True,
                        etag=new_etag or board.etag,
                        last_modified=new_last_mod or board.last_modified,
                        content_fingerprint=fingerprint,
                        reconciliation_policy=policy,
                    )

                listings = await hydrate_recruitee_offers(
                    board.board_token,
                    active_offers,
                    client,
                    board_company_name=board.company_name,
                    board_logo_url=board.company_logo_url,
                    board_logo_source=board.company_logo_source,
                    board_logo_verified=bool(board.company_logo_verified),
                    board_logo_checked_at=board.company_logo_checked_at,
                    registry=kwargs.get("registry"),
                    is_board_monitor=True,
                )
                if len(listings) != len(active_offers):
                    return failure_result(
                        kind=FailureKind.INCOMPLETE_SNAPSHOT,
                        error=(
                            f"Recruitee offer hydration mismatch: converted {len(listings)} "
                            f"of {len(active_offers)} active offers"
                        ),
                        policy=policy,
                    )

                return BoardCheckResult(
                    success=True,
                    not_modified=False,
                    listings=listings,
                    etag=new_etag,
                    last_modified=new_last_mod,
                    content_fingerprint=fingerprint,
                    reconciliation_policy=policy,
                )
            except asyncio.CancelledError:
                raise
            except UnsafeRedirectError as exc:
                return failure_result(
                    kind=FailureKind.UNSAFE_URL,
                    error=str(exc),
                    policy=policy,
                )
            except SafetyError:
                raise
            except Exception as exc:
                return failure_result(
                    kind=classify_exception(exc),
                    error=str(exc),
                    policy=policy,
                )
