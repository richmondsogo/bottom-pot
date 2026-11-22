"""
Lever company-board monitoring adapter.
"""

from __future__ import annotations

import asyncio
import json
from urllib.parse import quote

import httpx

from src.core.clock import Clock, use_clock
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
from src.safety.url_safety import DnsResolver
from src.storage.company_board_registry import CompanyBoard


class LeverBoardAdapter:
    """Adapter for Lever public board API: GET /v0/postings/{slug}?mode=json"""

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
        policy = get_reconciliation_policy("lever")
        if not validate_board_token_safety(board.board_token):
            return failure_result(
                kind=FailureKind.UNSAFE_URL,
                error="Invalid Lever board token",
                policy=policy,
            )

        encoded_token = quote(board.board_token.strip(), safe="-_.~")
        url = f"https://api.lever.co/v0/postings/{encoded_token}?mode=json"
        headers = build_conditional_headers(
            url,
            "application/json,text/plain;q=0.9,*/*;q=0.8",
            etag=board.etag,
            last_modified=board.last_modified,
        )
        eff_max_bytes = (
            int(max_response_bytes)
            if max_response_bytes is not None
            else int(kwargs.get("max_response_bytes") or settings.max_response_bytes)
        )

        with use_clock(clock):
            try:
                status, body_bytes, resp_headers = await fetch_provider_bytes(
                    client,
                    url,
                    headers=headers,
                    timeout=timeout,
                    max_bytes=eff_max_bytes,
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
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    return failure_result(
                        kind=FailureKind.PARSE_ERROR,
                        error=f"Invalid Lever JSON payload: {exc}",
                        policy=policy,
                    )
                if not isinstance(data, list):
                    return failure_result(
                        kind=FailureKind.PARSE_ERROR,
                        error="Invalid Lever payload shape",
                        policy=policy,
                    )

                new_etag = resp_headers.get("etag")
                new_last_mod = resp_headers.get("last-modified")

                fingerprint_items: list[tuple[str, str | None, str | None]] = []
                seen_ids: set[str] = set()
                for it in data:
                    if not isinstance(it, dict) or not it.get("id"):
                        continue
                    jid = str(it.get("id")).strip()
                    if jid in seen_ids:
                        return failure_result(
                            kind=FailureKind.INCOMPLETE_SNAPSHOT,
                            error=f"Duplicate Lever posting id in snapshot: {jid}",
                            policy=policy,
                        )
                    seen_ids.add(jid)
                    ts = str(it.get("createdAt") or "")
                    ch = canonical_content_hash({
                        "id": jid,
                        "text": it.get("text"),
                        "createdAt": it.get("createdAt"),
                        "descriptionPlain": it.get("descriptionPlain"),
                        "description": it.get("description"),
                        "lists": it.get("lists"),
                        "additionalPlain": it.get("additionalPlain"),
                        "additional": it.get("additional"),
                        "categories": it.get("categories"),
                        "workplaceType": it.get("workplaceType"),
                        "salaryRange": it.get("salaryRange"),
                        "hostedUrl": it.get("hostedUrl"),
                        "applyUrl": it.get("applyUrl"),
                    })
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

                company_name = board.company_name or humanize_slug(board.board_token)
                from src.ats.ats_api_client import enrich_lever_board_identity, lever_payload_to_raw
                from src.extraction.logo_extractor import LogoResult

                resolved_logo = (
                    LogoResult(
                        url=board.company_logo_url,
                        source=board.company_logo_source,
                        raw_value=board.company_logo_url,
                        verified=bool(board.company_logo_verified),
                    )
                    if board.company_logo_url and board.company_logo_verified
                    else LogoResult()
                )
                if not resolved_logo.url and board.company_logo_checked_at is None:
                    try:
                        enriched_name, enriched_logo = await enrich_lever_board_identity(board.board_token, client)
                        if enriched_name and (not company_name or company_name == humanize_slug(board.board_token)):
                            company_name = enriched_name
                        if enriched_logo.url and enriched_logo.verified:
                            resolved_logo = enriched_logo
                    except asyncio.CancelledError:
                        raise
                    except Exception:
                        pass

                listings: list[JobListing] = []
                for item in data:
                    if not isinstance(item, dict):
                        continue
                    raw = lever_payload_to_raw(
                        item,
                        company_slug=board.board_token,
                        query_used=board.board_token,
                        default_company_name=company_name,
                        is_board_monitor=True,
                    )
                    if raw is None or not raw.raw_title or not raw.source_url:
                        continue
                    if resolved_logo.url and resolved_logo.verified and not raw.raw_fields.get("company_logo_url"):
                        raw.raw_fields["company_logo_url"] = resolved_logo.url
                        raw.raw_fields["company_logo_source"] = resolved_logo.source
                        raw.raw_fields["company_logo_verified"] = True
                    canonical = JobExtractionService.extract(raw)
                    listing = CanonicalJobAdapter.to_listing(canonical)
                    listing.provider = "lever"
                    listing.ats_source = "lever"
                    listing.data_source = "api"
                    if resolved_logo.verified and resolved_logo.url and not listing.company_logo_url:
                        listing.company_logo_url = resolved_logo.url
                        listing.company_logo_source = resolved_logo.source
                        listing.company_logo_verified = True
                    listings.append(listing)

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
            except Exception as exc:
                return failure_result(
                    kind=classify_exception(exc),
                    error=str(exc),
                    policy=policy,
                )
