"""
Ashby company-board monitoring adapter.
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


def _ashby_job_content_hash(item: dict) -> str:
    """
    Build a deterministic SHA256 digest over all meaningful Ashby posting fields
    that affect extraction and monitoring, excluding transient response metadata.
    """
    workplace_type = item.get("workplaceType")
    workplace_type_name = item.get("workplaceTypeName")
    has_explicit_workplace = bool(
        (isinstance(workplace_type, str) and workplace_type.strip())
        or (isinstance(workplace_type_name, str) and workplace_type_name.strip())
    )
    canonical_payload = {
        "v": "v39_full",
        "id": str(item.get("id") or "").strip().lower(),
        "publishedAt": item.get("publishedAt"),
        "title": item.get("title"),
        "descriptionHtml": item.get("descriptionHtml"),
        "descriptionPlain": item.get("descriptionPlain"),
        "description": item.get("description"),
        "location": item.get("location"),
        "locationName": item.get("locationName"),
        "secondaryLocations": item.get("secondaryLocations"),
        "address": item.get("address"),
        "workplaceType": workplace_type,
        "workplaceTypeName": workplace_type_name,
        "isRemote": item.get("isRemote") if not has_explicit_workplace else None,
        "compensation": item.get("compensation"),
        "employmentType": item.get("employmentType"),
        "departmentName": item.get("departmentName"),
        "department": item.get("department"),
        "team": item.get("team"),
        "jobUrl": item.get("jobUrl"),
        "applyUrl": item.get("applyUrl"),
        "company": item.get("company"),
        "companyName": item.get("companyName"),
    }
    return canonical_content_hash(canonical_payload)


class AshbyBoardAdapter:
    """Adapter for Ashby public board API: GET /posting-api/job-board/{slug}?includeCompensation=true"""

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
        from src.ats.ats_api_client import ashby_payload_to_raw, enrich_ashby_board_identity
        from src.extraction.logo_extractor import LogoResult

        policy = get_reconciliation_policy("ashby")
        if not validate_board_token_safety(board.board_token):
            return failure_result(
                kind=FailureKind.UNSAFE_URL,
                error="Invalid Ashby board token",
                policy=policy,
            )

        encoded_slug = quote(board.board_token.strip(), safe="-_.~")
        url = f"https://api.ashbyhq.com/posting-api/job-board/{encoded_slug}?includeCompensation=true"
        headers = build_conditional_headers(
            url,
            "application/json",
            etag=board.etag,
            last_modified=board.last_modified,
            accept_gzip=True,
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
                        error=f"Invalid Ashby JSON payload: {exc}",
                        policy=policy,
                    )
                if not isinstance(data, dict) or "jobs" not in data or not isinstance(data.get("jobs"), list):
                    return failure_result(
                        kind=FailureKind.PARSE_ERROR,
                        error="Invalid Ashby jobs payload shape",
                        policy=policy,
                    )
                raw_jobs = data["jobs"]
                new_etag = resp_headers.get("etag")
                new_last_mod = resp_headers.get("last-modified")

                fingerprint_items: list[tuple[str, str | None, str | None]] = []
                seen_ids: set[str] = set()
                for j in raw_jobs:
                    if not isinstance(j, dict) or not j.get("id"):
                        continue
                    jid = str(j.get("id")).strip()
                    if jid in seen_ids:
                        return failure_result(
                            kind=FailureKind.INCOMPLETE_SNAPSHOT,
                            error=f"Duplicate Ashby job id in snapshot: {jid}",
                            policy=policy,
                        )
                    seen_ids.add(jid)
                    ts = str(j.get("publishedAt") or "")
                    ch = _ashby_job_content_hash(j)
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
                        enriched_name, enriched_logo = await enrich_ashby_board_identity(
                            board.board_token,
                            client,
                            registry=kwargs.get("registry"),
                        )
                        if enriched_name and (not company_name or company_name == humanize_slug(board.board_token)):
                            company_name = enriched_name
                        if enriched_logo.url and enriched_logo.verified:
                            resolved_logo = enriched_logo
                    except (asyncio.CancelledError, SafetyError):
                        raise
                    except Exception:
                        pass

                listings: list[JobListing] = []
                for item in raw_jobs:
                    if not isinstance(item, dict):
                        continue
                    raw = ashby_payload_to_raw(
                        item,
                        company_slug=board.board_token,
                        query_used=board.board_token,
                        default_company_name=company_name,
                        is_board_monitor=True,
                        company_logo_url=resolved_logo.url if resolved_logo.verified else None,
                        company_logo_source=resolved_logo.source if resolved_logo.verified else None,
                        company_logo_verified=bool(resolved_logo.verified and resolved_logo.url),
                    )
                    if raw is None or not raw.raw_title or not raw.source_url:
                        continue
                    canonical = JobExtractionService.extract(raw)
                    listing = CanonicalJobAdapter.to_listing(canonical)
                    listing.provider = "ashby"
                    listing.ats_source = "ashby"
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
