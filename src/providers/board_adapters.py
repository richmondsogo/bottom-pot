"""
ATS Company-Board Adapters for Independent Monitoring.

Provides unauthenticated public endpoint adapters for:
- Greenhouse (GET /v1/boards/{token}/jobs)
- Lever (GET /v0/postings/{token}?mode=json)
- Ashby (GET /posting-api/job-board/{token}?includeCompensation=true)

Supports:
- HTTP 304 Not Modified conditional headers (If-None-Match, If-Modified-Since).
- SHA256 content fingerprinting across job IDs and timestamps.
- Zero paid API dependencies.
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Optional
from urllib.parse import quote

import httpx
from loguru import logger

from src.ats.ats_api_client import (
    _WORKABLE_TYPE_MAP,
    _format_workable_location_item,
    greenhouse_payload_to_raw,
)
from src.core.clock import Clock, epoch_now, use_clock
from src.core.models import JobListing
from src.core.settings import settings
from src.extraction.canonical_job_adapter import CanonicalJobAdapter
from src.extraction.field_normalizer import humanize_slug, normalize_job_type
from src.extraction.job_extraction_service import JobExtractionService, RawJobPosting
from src.providers.contract import (
    BoardCheckResult,
    FailureKind,
    classify_exception,
    classify_http_status,
    failure_result,
    get_reconciliation_policy,
)
from src.providers.detail_hydration import (
    build_deferred_detail_state,
    build_detail_failure_state,
    build_hydrated_detail_state,
    classify_detail_candidate,
    fetch_detail_json_batch,
    preserve_cached_detail_state,
    resolve_prev_hydrated_at,
    select_fair_detail_hydration_batch,
)
from src.providers.fingerprint import canonical_content_hash, compute_board_fingerprint
from src.providers.http import (
    build_conditional_headers,
    fetch_provider_bytes,
    validate_board_token_safety,
)
from src.providers.pagination import HtmlPaginationTracker, validate_offset_page
from src.safety.url_safety import DnsResolver
from src.storage.company_board_registry import CompanyBoard, MonitoredJobDetailState


class GreenhouseBoardAdapter:
    """Adapter for Greenhouse public board API: GET /v1/boards/{slug}/jobs"""

    async def get_job_detail(
        self,
        board_token: str,
        job_id: str | int,
        client: httpx.AsyncClient,
        timeout: float = 5.0,
        *,
        resolver: DnsResolver | None = None,
        max_response_bytes: int | None = None,
    ) -> Optional[dict]:
        """Fetch individual job detail from Greenhouse public API:
        GET https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs/{job_id}
        Exposes authoritative 'first_published' date and individual job fields.
        """
        if not validate_board_token_safety(board_token):
            return None
        encoded_token = quote(board_token.strip(), safe="-_.~")
        encoded_job_id = quote(str(job_id).strip(), safe="-_.~")
        url = (
            f"https://boards-api.greenhouse.io/v1/boards/{encoded_token}/jobs/{encoded_job_id}"
            "?pay_transparency=true"
        )
        headers = build_conditional_headers(
            url, "application/json,text/plain;q=0.9,*/*;q=0.8"
        )
        try:
            status, body_bytes, _ = await fetch_provider_bytes(
                client,
                url,
                headers=headers,
                timeout=timeout,
                max_bytes=max_response_bytes,
                resolver=resolver,
            )
            if status == 200:
                data = json.loads(body_bytes.decode("utf-8"))
                if isinstance(data, dict):
                    return data
        except asyncio.CancelledError:
            raise
        except Exception:
            pass
        return None

    async def check_board(
        self,
        board: CompanyBoard,
        client: httpx.AsyncClient,
        timeout: float = 8.0,
        fetch_publication_dates: bool = False,
        known_publication_dates: dict[str, str] | None = None,
        concurrency_limit: int = 5,
        clock: Clock | None = None,
        resolver: DnsResolver | None = None,
        max_response_bytes: int | None = None,
        **kwargs,
    ) -> BoardCheckResult:
        policy = get_reconciliation_policy("greenhouse")
        if not validate_board_token_safety(board.board_token):
            return failure_result(
                kind=FailureKind.UNSAFE_URL,
                error="Invalid Greenhouse board token",
                policy=policy,
            )

        encoded_token = quote(board.board_token.strip(), safe="-_.~")
        url = (
            f"https://boards-api.greenhouse.io/v1/boards/{encoded_token}/jobs"
            "?content=true&pay_transparency=true"
        )
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
                        error=f"Invalid Greenhouse JSON payload: {exc}",
                        policy=policy,
                    )

                if not isinstance(data, dict) or "jobs" not in data or not isinstance(data.get("jobs"), list):
                    return failure_result(
                        kind=FailureKind.PARSE_ERROR,
                        error="Invalid Greenhouse payload shape",
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
                            error=f"Duplicate Greenhouse job id in snapshot: {jid}",
                            policy=policy,
                        )
                    seen_ids.add(jid)
                    ts = str(j.get("updated_at") or "")
                    ch = canonical_content_hash({
                        "id": jid,
                        "title": j.get("title"),
                        "location": j.get("location"),
                        "content": j.get("content"),
                        "updated_at": j.get("updated_at"),
                        "first_published": j.get("first_published"),
                        "absolute_url": j.get("absolute_url"),
                        "departments": j.get("departments"),
                        "offices": j.get("offices"),
                        "metadata": j.get("metadata"),
                        "pay_input_ranges": j.get("pay_input_ranges"),
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
                listings: list[JobListing] = []

                known_dates = known_publication_dates or {}
                jobs_needing_detail = [
                    item for item in raw_jobs
                    if isinstance(item, dict)
                    and item.get("id")
                    and not item.get("first_published")
                    and str(item.get("id")) not in known_dates
                    and f"greenhouse:{board.board_token}:{item.get('id')}" not in known_dates
                ]

                fetched_details_map: dict[str, dict] = {}
                if fetch_publication_dates and jobs_needing_detail:
                    sem = asyncio.Semaphore(max(1, concurrency_limit))

                    async def _fetch_single_detail(jid: str) -> tuple[str, Optional[dict]]:
                        async with sem:
                            detail = await self.get_job_detail(
                                board.board_token,
                                jid,
                                client,
                                timeout=min(timeout, 4.0),
                                resolver=resolver,
                                max_response_bytes=eff_max_bytes,
                            )
                            return jid, detail

                    tasks = [_fetch_single_detail(str(item["id"])) for item in jobs_needing_detail]
                    detail_results = await asyncio.gather(*tasks, return_exceptions=True)
                    for res in detail_results:
                        if isinstance(res, asyncio.CancelledError):
                            raise res
                        if isinstance(res, tuple) and res[1] is not None:
                            fetched_details_map[res[0]] = res[1]

                for item in raw_jobs:
                    if not isinstance(item, dict):
                        continue
                    job_id = str(item.get("id") or "")
                    title = (item.get("title") or "").strip()
                    apply_url = (item.get("absolute_url") or "").strip()
                    if not title or not apply_url:
                        continue

                    detail = fetched_details_map.get(job_id) or {}
                    item_for_raw = dict(item)
                    if detail:
                        for dk, dv in detail.items():
                            if dv is not None and item_for_raw.get(dk) is None:
                                item_for_raw[dk] = dv

                    first_published = (
                        item_for_raw.get("first_published")
                        or known_dates.get(job_id)
                        or known_dates.get(f"greenhouse:{board.board_token}:{job_id}")
                        or detail.get("first_published")
                    )
                    if first_published:
                        item_for_raw["first_published"] = first_published

                    raw = greenhouse_payload_to_raw(
                        item_for_raw,
                        company_slug=board.board_token,
                        source_url=apply_url,
                        query_used=board.board_token,
                        default_job_id=job_id,
                        default_company_name=company_name,
                        is_board_monitor=True,
                        company_logo_url=board.company_logo_url if board.company_logo_verified else None,
                        company_logo_source=board.company_logo_source if board.company_logo_verified else None,
                        company_logo_verified=bool(board.company_logo_verified),
                    )
                    if raw is None:
                        continue
                    canonical = JobExtractionService.extract(raw)
                    listing = CanonicalJobAdapter.to_listing(canonical)
                    listing.provider = "greenhouse"
                    listing.ats_source = "greenhouse"
                    listing.data_source = "api"
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
                    except asyncio.CancelledError:
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
            except Exception as exc:
                return failure_result(
                    kind=classify_exception(exc),
                    error=str(exc),
                    policy=policy,
                )


def _workable_widget_job_hash(item: dict) -> str:
    """Stable full 64-hex SHA-256 hash of Workable widget listing metadata."""
    payload = {
        "title": item.get("title"),
        "published_on": item.get("published_on"),
        "department": item.get("department"),
        "employment_type": item.get("employment_type"),
        "telecommuting": item.get("telecommuting"),
        "country": item.get("country"),
        "city": item.get("city"),
        "state": item.get("state"),
        "locations": item.get("locations"),
    }
    return canonical_content_hash(payload)


def _norm_workable_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).casefold()


def _extract_widget_location_tuples(item: dict) -> list[tuple[str, str, str]]:
    """Return non-hidden (city, region/state, country) tuples from a Workable widget item."""
    tuples: list[tuple[str, str, str]] = []
    raw_locs = item.get("locations")
    if isinstance(raw_locs, list):
        for loc in raw_locs:
            if not isinstance(loc, dict) or loc.get("hidden"):
                continue
            city = str(loc.get("city") or "").strip()
            region = str(loc.get("region") or loc.get("state") or "").strip()
            country = str(loc.get("country") or "").strip()
            if city or region or country:
                tuples.append((city, region, country))
    if not tuples:
        city = str(item.get("city") or "").strip()
        state = str(item.get("state") or item.get("region") or "").strip()
        country = str(item.get("country") or "").strip()
        if city or state or country:
            tuples.append((city, state, country))
    return tuples


def _workable_widget_location_signature(item: dict) -> str | None:
    """Stable normalized JSON signature of widget location tuples (including state/region)."""
    tuples = _extract_widget_location_tuples(item)
    if not tuples:
        return None
    normalized = [
        [_norm_workable_text(c), _norm_workable_text(r), _norm_workable_text(co)]
        for c, r, co in tuples
    ]
    return json.dumps(normalized, ensure_ascii=False)


def _workable_widget_differs_from_listing(
    item: dict,
    existing: JobListing,
    *,
    existing_location_signature: str | None = None,
) -> bool:
    """
    Compare all meaningful Workable widget fields against an existing JobListing.
    Missing or empty widget fields are ignored unless authoritative and intentionally empty.
    """
    widget_title = _norm_workable_text(item.get("title"))
    existing_title = _norm_workable_text(existing.title)
    if widget_title and widget_title != existing_title:
        return True

    widget_pub = str(item.get("published_on") or "").strip()[:10]
    if widget_pub:
        if existing.posted_at is None:
            return True
        if widget_pub != existing.posted_at.date().isoformat():
            return True

    raw_emp = str(item.get("employment_type") or "").strip()
    if raw_emp:
        norm_widget_emp = (
            _WORKABLE_TYPE_MAP.get(raw_emp.lower())
            or normalize_job_type(raw_emp)
            or raw_emp.casefold()
        )
        if norm_widget_emp != _norm_workable_text(existing.employment_type):
            return True

    widget_dept = _norm_workable_text(item.get("department"))
    if widget_dept and widget_dept != _norm_workable_text(existing.department):
        return True

    tele = item.get("telecommuting")
    if tele is True:
        if existing.work_model != "remote":
            return True
    elif tele is False:
        # Workable widget reports telecommuting=false for both on_site and hybrid postings.
        if (
            existing.work_model == "remote"
            and (existing.raw_workplace_type or "").strip().lower() not in ("on_site", "hybrid")
        ):
            return True

    widget_loc_sig = _workable_widget_location_signature(item)
    if existing_location_signature and widget_loc_sig and widget_loc_sig != existing_location_signature:
        return True

    loc_tuples = _extract_widget_location_tuples(item)
    if loc_tuples:
        existing_locs = [
            _norm_workable_text(seg)
            for seg in str(existing.location or "").split(";")
            if seg.strip()
        ]
        if not existing_locs:
            return True
        if len(loc_tuples) != len(existing_locs):
            return True
        if len(loc_tuples) > 1:
            formatted = [
                _norm_workable_text(
                    _format_workable_location_item({"city": c, "region": r, "country": co})
                    or ", ".join(p for p in (c, r, co) if p)
                )
                for c, r, co in loc_tuples
            ]
            if formatted != existing_locs:
                return True
        else:
            w_city, w_state, w_country = (_norm_workable_text(x) for x in loc_tuples[0])
            ex_parts = [_norm_workable_text(p) for p in existing_locs[0].split(",") if p.strip()]
            if not ex_parts:
                return True
            if w_city:
                if w_country and len(ex_parts) >= 2:
                    if w_city != ex_parts[0] or w_country != ex_parts[-1]:
                        return True
                elif w_city not in ex_parts:
                    return True
            if w_country:
                if w_country != ex_parts[-1] and w_country not in ex_parts:
                    return True
            if w_state:
                if not w_city:
                    if w_state != ex_parts[0] and w_state not in ex_parts:
                        return True
                elif len(ex_parts) >= 3:
                    if w_state not in ex_parts[1:-1] and w_state not in ex_parts:
                        return True

    return False


def _extract_workable_listing(
    raw: RawJobPosting,
    *,
    logo_url: str | None,
    logo_source: str | None,
    logo_verified: bool,
) -> JobListing:
    canonical = JobExtractionService.extract(raw)
    listing = CanonicalJobAdapter.to_listing(canonical)
    listing.provider = "workable"
    listing.ats_source = "workable"
    listing.data_source = "api"
    if logo_verified and logo_url and not listing.company_logo_url:
        listing.company_logo_url = logo_url
        listing.company_logo_source = logo_source
        listing.company_logo_verified = True
    return listing


async def hydrate_workable_board_jobs(
    slug: str,
    raw_jobs: list[dict],
    client: httpx.AsyncClient,
    *,
    widget_company_name: str | None = None,
    board_company_name: str | None = None,
    board_logo_url: str | None = None,
    board_logo_source: str | None = None,
    board_logo_verified: bool = False,
    board_logo_checked_at: float | None = None,
    registry: object | None = None,
    known_monitored_jobs: dict[str, tuple[JobListing, float]] | None = None,
    known_detail_states: dict[str, MonitoredJobDetailState] | None = None,
    detail_states_out: dict[str, MonitoredJobDetailState] | None = None,
    detail_revalidate_ttl_seconds: float = 21600.0,
    max_revalidations_per_poll: int = 5,
    max_detail_fetches: int | None = None,
    timeout: float = 8.0,
    is_board_monitor: bool = True,
    board_fingerprint_changed: bool = True,
    resolver: DnsResolver | None = None,
    max_response_bytes: int | None = None,
) -> tuple[list[JobListing], set[str]]:
    """
    Shared Workable widget + bounded api/v2 detail hydration path used by both
    WorkableBoardAdapter and probe_workable_board.
    """
    from src.ats.ats_api_client import (
        enrich_workable_board_identity,
        workable_payload_to_raw,
        workable_widget_job_to_raw,
    )
    from src.extraction.logo_extractor import LogoResult

    known = known_monitored_jobs or {}
    known_states = known_detail_states or {}
    now = epoch_now()

    company_name = (
        board_company_name
        or widget_company_name
        or humanize_slug(slug)
    )
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
            enriched_name, enriched_logo = await enrich_workable_board_identity(
                slug,
                client,
                registry=registry,
                use_resilience=True,
            )
            if enriched_name and (
                not company_name
                or company_name == humanize_slug(slug)
                or company_name == widget_company_name
            ):
                company_name = enriched_name
                if enriched_logo.url and enriched_logo.verified:
                    resolved_logo = enriched_logo
        except asyncio.CancelledError:
            raise
        except Exception:
            pass

    immediate_shortcodes: list[str] = []
    stale_candidates: list[tuple[int, float, str]] = []
    widget_by_shortcode: dict[str, dict] = {}
    ordered_shortcodes: list[str] = []

    for item in raw_jobs:
        if not isinstance(item, dict):
            continue
        shortcode = str(item.get("shortcode") or "").strip()
        if not shortcode:
            continue
        widget_by_shortcode[shortcode] = item
        ordered_shortcodes.append(shortcode)

        job_id = f"workable:{slug}:{shortcode}"
        cached_entry = known.get(job_id)
        prev_state = known_states.get(job_id)
        if cached_entry is None:
            immediate_shortcodes.append(shortcode)
        else:
            existing_listing, _ = cached_entry
            existing_loc_sig = prev_state.widget_location_signature if prev_state is not None else None
            if board_fingerprint_changed and _workable_widget_differs_from_listing(
                item,
                existing_listing,
                existing_location_signature=existing_loc_sig,
            ):
                immediate_shortcodes.append(shortcode)
            else:
                is_due, tier, sort_ts = classify_detail_candidate(
                    now,
                    cached_entry,
                    prev_state,
                    detail_revalidate_ttl_seconds,
                )
                if is_due:
                    stale_candidates.append((tier, sort_ts, shortcode))

    fetch_shortcodes = select_fair_detail_hydration_batch(
        immediate_ids=immediate_shortcodes,
        stale_candidates=stale_candidates,
        max_revalidations_per_poll=max_revalidations_per_poll,
        max_detail_fetches=max_detail_fetches,
    )
    fetch_set = set(fetch_shortcodes)

    encoded_slug = quote(slug, safe="-_.~")
    detail_urls = [
        (
            sc,
            f"https://apply.workable.com/api/v2/accounts/{encoded_slug}/jobs/{quote(sc, safe='-_.~')}",
        )
        for sc in fetch_shortcodes
    ]
    detail_results = await fetch_detail_json_batch(
        client,
        detail_urls,
        concurrency=5,
        timeout=timeout,
        max_bytes=max_response_bytes,
        resolver=resolver,
    )

    listings: list[JobListing] = []
    refreshed_job_ids: set[str] = set()
    logo_url = resolved_logo.url if resolved_logo.verified else None
    logo_source = resolved_logo.source if resolved_logo.verified else None
    logo_verified = bool(resolved_logo.verified and resolved_logo.url)

    def _emit_preserved_or_fallback(
        sc_item: dict,
        jid: str,
        cached: tuple[JobListing, float] | None,
        new_state: MonitoredJobDetailState,
    ) -> None:
        if cached is not None:
            listings.append(cached[0])
            if detail_states_out is not None:
                detail_states_out[jid] = new_state
            return
        raw_widget = workable_widget_job_to_raw(
            sc_item,
            company_slug=slug,
            default_company_name=company_name,
            query_used=slug,
            company_logo_url=logo_url,
            company_logo_source=logo_source,
            company_logo_verified=logo_verified,
        )
        if raw_widget is None or not raw_widget.raw_title or not raw_widget.source_url:
            return
        fallback_listing = _extract_workable_listing(
            raw_widget,
            logo_url=logo_url,
            logo_source=logo_source,
            logo_verified=logo_verified,
        )
        listings.append(fallback_listing)
        if detail_states_out is not None:
            detail_states_out[fallback_listing.id] = new_state

    for shortcode in ordered_shortcodes:
        item = widget_by_shortcode[shortcode]
        job_id = f"workable:{slug}:{shortcode}"
        cached_entry = known.get(job_id)
        prev_state = known_states.get(job_id)
        loc_sig = _workable_widget_location_signature(item)
        prev_hydrated_at = resolve_prev_hydrated_at(prev_state, cached_entry)

        if shortcode in fetch_set:
            status_code, payload, err_reason = detail_results.get(shortcode, (None, None, None))
            if status_code == 200 and isinstance(payload, dict) and not payload.get("error"):
                raw = workable_payload_to_raw(
                    payload,
                    company_slug=slug,
                    default_job_id=shortcode,
                    default_company_name=company_name,
                    query_used=slug,
                    is_board_monitor=is_board_monitor,
                    company_logo_url=logo_url,
                    company_logo_source=logo_source,
                    company_logo_verified=logo_verified,
                )
                if (
                    raw is not None
                    and raw.raw_title
                    and raw.source_url
                    and raw.description_is_authentic
                ):
                    listing = _extract_workable_listing(
                        raw,
                        logo_url=logo_url,
                        logo_source=logo_source,
                        logo_verified=logo_verified,
                    )
                    listings.append(listing)
                    refreshed_job_ids.add(listing.id)
                    if detail_states_out is not None:
                        detail_states_out[listing.id] = build_hydrated_detail_state(
                            now,
                            widget_location_signature=loc_sig,
                        )
                    continue

                # HTTP 200 returned an incomplete or invalid detail payload
                _emit_preserved_or_fallback(
                    item,
                    job_id,
                    cached_entry,
                    build_detail_failure_state(
                        status_code=200,
                        err_reason=None,
                        prev_state=prev_state,
                        prev_hydrated_at=prev_hydrated_at,
                        now=now,
                        ttl_seconds=detail_revalidate_ttl_seconds,
                        invalid_detail_override=True,
                        widget_location_signature=loc_sig,
                    ),
                )
                continue

            _emit_preserved_or_fallback(
                item,
                job_id,
                cached_entry,
                build_detail_failure_state(
                    status_code=status_code,
                    err_reason=None if status_code == 200 else err_reason,
                    prev_state=prev_state,
                    prev_hydrated_at=prev_hydrated_at,
                    now=now,
                    ttl_seconds=detail_revalidate_ttl_seconds,
                    widget_location_signature=loc_sig,
                ),
            )
            continue

        if cached_entry is not None:
            # Known unchanged job outside this poll's rotation slice or within retry backoff
            listings.append(cached_entry[0])
            if detail_states_out is not None:
                detail_states_out[job_id] = preserve_cached_detail_state(
                    prev_state,
                    prev_hydrated_at,
                    cached_entry,
                    now,
                    widget_location_signature=loc_sig,
                )
            continue

        # Bounded widget fallback (e.g. direct router cap overflow) — never mark detail-refreshed
        _emit_preserved_or_fallback(
            item,
            job_id,
            None,
            build_deferred_detail_state(
                now,
                detail_status="widget_fallback",
                last_error="deferred_widget_fallback",
                widget_location_signature=loc_sig,
            ),
        )

    return listings, refreshed_job_ids


class WorkableBoardAdapter:
    """Adapter for Workable public widget + bounded api/v2 detail hydration."""

    def __init__(
        self,
        detail_revalidate_ttl_seconds: float = 21600.0,
        max_revalidations_per_poll: int = 5,
    ) -> None:
        self.detail_revalidate_ttl_seconds = float(detail_revalidate_ttl_seconds)
        self.max_revalidations_per_poll = int(max_revalidations_per_poll)

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
        policy = get_reconciliation_policy("workable")
        if not validate_board_token_safety(board.board_token):
            return failure_result(
                kind=FailureKind.UNSAFE_URL,
                error="Invalid Workable board token",
                policy=policy,
            )

        encoded_slug = quote(board.board_token.strip(), safe="-_.~")
        url = f"https://apply.workable.com/api/v1/widget/accounts/{encoded_slug}"
        headers = build_conditional_headers(
            url,
            "application/json",
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
                        error=f"Invalid Workable JSON payload: {exc}",
                        policy=policy,
                    )
                if not isinstance(data, dict) or "jobs" not in data or not isinstance(data.get("jobs"), list):
                    return failure_result(
                        kind=FailureKind.PARSE_ERROR,
                        error="Invalid Workable widget jobs shape",
                        policy=policy,
                    )
                raw_jobs = data["jobs"]

                new_etag = resp_headers.get("etag")
                new_last_mod = resp_headers.get("last-modified")

                fingerprint_items: list[tuple[str, str | None, str | None]] = []
                seen_shortcodes: set[str] = set()
                for j in raw_jobs:
                    if not isinstance(j, dict) or not j.get("shortcode"):
                        continue
                    sc = str(j.get("shortcode")).strip()
                    if sc in seen_shortcodes:
                        return failure_result(
                            kind=FailureKind.INCOMPLETE_SNAPSHOT,
                            error=f"Duplicate Workable shortcode in snapshot: {sc}",
                            policy=policy,
                        )
                    seen_shortcodes.add(sc)
                    ts = str(j.get("published_on") or "")
                    ch = _workable_widget_job_hash(j)
                    fingerprint_items.append((sc, ts, ch))

                fingerprint = compute_board_fingerprint(fingerprint_items)
                known_monitored: dict[str, tuple[JobListing, float]] = kwargs.get("known_monitored_jobs") or {}
                known_detail_states: dict[str, MonitoredJobDetailState] = (
                    kwargs.get("known_detail_states") or {}
                )
                now = epoch_now()
                fingerprint_changed = not (
                    board.content_fingerprint and fingerprint == board.content_fingerprint
                )

                has_new_or_changed = False
                has_due_retry_or_stale = False
                for j in raw_jobs:
                    if not isinstance(j, dict) or not j.get("shortcode"):
                        continue
                    sc = str(j.get("shortcode")).strip()
                    jid = f"workable:{board.board_token}:{sc}"
                    cached = known_monitored.get(jid)
                    d_state = known_detail_states.get(jid)
                    loc_sig = d_state.widget_location_signature if d_state is not None else None
                    if cached is None or (
                        fingerprint_changed
                        and _workable_widget_differs_from_listing(
                            j,
                            cached[0],
                            existing_location_signature=loc_sig,
                        )
                    ):
                        has_new_or_changed = True
                        break
                    is_due, _, _ = classify_detail_candidate(
                        now,
                        cached,
                        d_state,
                        self.detail_revalidate_ttl_seconds,
                    )
                    if is_due:
                        has_due_retry_or_stale = True

                if (
                    not fingerprint_changed
                    and not has_new_or_changed
                    and not has_due_retry_or_stale
                ):
                    return BoardCheckResult(
                        success=True,
                        not_modified=True,
                        etag=new_etag or board.etag,
                        last_modified=new_last_mod or board.last_modified,
                        content_fingerprint=fingerprint,
                        reconciliation_policy=policy,
                    )

                detail_states_out: dict[str, MonitoredJobDetailState] = {}
                listings, refreshed_job_ids = await hydrate_workable_board_jobs(
                    board.board_token,
                    raw_jobs,
                    client,
                    widget_company_name=(str(data.get("name")).strip() if data.get("name") else None),
                    board_company_name=board.company_name,
                    board_logo_url=board.company_logo_url,
                    board_logo_source=board.company_logo_source,
                    board_logo_verified=bool(board.company_logo_verified),
                    board_logo_checked_at=board.company_logo_checked_at,
                    registry=kwargs.get("registry"),
                    known_monitored_jobs=known_monitored,
                    known_detail_states=known_detail_states,
                    detail_states_out=detail_states_out,
                    detail_revalidate_ttl_seconds=self.detail_revalidate_ttl_seconds,
                    max_revalidations_per_poll=self.max_revalidations_per_poll,
                    timeout=timeout,
                    is_board_monitor=True,
                    board_fingerprint_changed=fingerprint_changed,
                    resolver=resolver,
                    max_response_bytes=eff_max_bytes,
                )

                return BoardCheckResult(
                    success=True,
                    not_modified=False,
                    listings=listings,
                    etag=new_etag,
                    last_modified=new_last_mod,
                    content_fingerprint=fingerprint,
                    refreshed_job_ids=refreshed_job_ids,
                    detail_states=detail_states_out,
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
                except Exception as exc:
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
            except Exception as exc:
                return failure_result(
                    kind=classify_exception(exc),
                    error=str(exc),
                    policy=policy,
                )


# ---------------------------------------------------------------------------
# SmartRecruiters
# ---------------------------------------------------------------------------

_SMARTREC_PAGE_SIZE = 100


def _smartrecruiters_listing_item_hash(item: dict) -> str:
    """
    Deterministic full-payload SHA-256 hex digest for a SmartRecruiters listing item.

    Normalizes only the company casing inside ``ref`` so requesting ``wise`` vs ``Wise``
    produces an identical hash while preserving sensitivity to every listing field.
    """
    normalized = dict(item)
    ref_val = normalized.get("ref")
    if isinstance(ref_val, str) and "/companies/" in ref_val:
        normalized["ref"] = re.sub(
            r"(/v1/companies/)([^/]+)(/postings/)",
            lambda m: f"{m.group(1)}{m.group(2).lower()}{m.group(3)}",
            ref_val,
            flags=re.IGNORECASE,
        )
    return canonical_content_hash(normalized)


def _validate_smartrecruiters_listing_entry(
    entry: object,
    *,
    seen_ids: set[str],
    expected_company_slug: str | None = None,
) -> tuple[str | None, str | None]:
    """Validate one SmartRecruiters public listing entry. Returns ``(item_id, error)``."""
    if not isinstance(entry, dict):
        return None, "Malformed SmartRecruiters listing entry (expected object)"

    vis = entry.get("visibility")
    if vis != "PUBLIC":
        return None, f"Non-PUBLIC or missing SmartRecruiters visibility: {vis!r}"

    raw_id = entry.get("id")
    if raw_id is None or isinstance(raw_id, (bool, list, dict)):
        return None, "Malformed SmartRecruiters posting missing id"
    item_id = str(raw_id).strip()
    if not item_id or not item_id.isdigit():
        return None, f"Invalid SmartRecruiters numeric posting id: {raw_id!r}"

    if item_id in seen_ids:
        return None, f"Duplicate SmartRecruiters posting id across snapshot: {item_id}"

    raw_name = entry.get("name")
    if not isinstance(raw_name, str) or not raw_name.strip():
        return None, f"Malformed SmartRecruiters posting {item_id} missing title"

    comp = entry.get("company")
    if comp is not None:
        if not isinstance(comp, dict):
            return None, f"Malformed SmartRecruiters company object on posting {item_id}"
        ident = comp.get("identifier")
        if ident is not None:
            if not isinstance(ident, str) or not ident.strip():
                return None, f"Invalid SmartRecruiters company.identifier on posting {item_id}"
            if expected_company_slug and ident.strip().lower() != expected_company_slug.strip().lower():
                return None, (
                    f"SmartRecruiters company.identifier mismatch on posting {item_id}: "
                    f"expected {expected_company_slug.strip().lower()!r}, got {ident.strip()!r}"
                )

    return item_id, None


def validate_smartrecruiters_page(
    data: object,
    *,
    requested_offset: int,
    expected_total: int | None,
    seen_ids: set[str],
    collected_count: int,
    expected_company_slug: str | None = None,
) -> tuple[list[dict] | None, int | None, int | None, str | None]:
    """
    Validate one sequential page of SmartRecruiters ``/postings`` JSON atomically
    via the shared ``validate_offset_page`` primitive.
    """
    page_seen: set[str] = set()

    def _validate_item(entry: object) -> str | None:
        item_id, entry_err = _validate_smartrecruiters_listing_entry(
            entry,
            seen_ids=seen_ids | page_seen,
            expected_company_slug=expected_company_slug,
        )
        if entry_err or item_id is None:
            return entry_err or "Malformed SmartRecruiters listing entry"
        page_seen.add(item_id)
        return None

    items, resp_limit, total_found, err = validate_offset_page(
        data,
        requested_offset=requested_offset,
        expected_total=expected_total,
        collected_count=collected_count,
        max_limit=100,
        list_key="content",
        total_key="totalFound",
        offset_key="offset",
        limit_key="limit",
        provider_label="SmartRecruiters",
        item_validator=_validate_item,
    )
    if err or items is None or total_found is None:
        return None, None, None, err or "Invalid SmartRecruiters listing page"
    seen_ids.update(page_seen)
    return items, resp_limit, total_found, None


async def _fetch_smartrecruiters_snapshot_with_kind(
    slug: str,
    client: httpx.AsyncClient,
    *,
    timeout: float = 10.0,
    resolver: DnsResolver | None = None,
    max_bytes: int | None = None,
) -> tuple[list[dict] | None, str | None, FailureKind | None]:
    from src.storage.company_board_registry import is_valid_board_slug

    clean_slug = (slug or "").strip().lower()
    if not validate_board_token_safety(slug) or not is_valid_board_slug("smartrecruiters", clean_slug):
        return None, "Invalid SmartRecruiters board token", FailureKind.UNSAFE_URL

    encoded_slug = quote(clean_slug, safe="-_.~")
    offset = 0
    expected_total: int | None = None
    seen_ids: set[str] = set()
    collected: list[dict] = []
    eff_max_bytes = max_bytes if max_bytes is not None else settings.max_response_bytes

    while True:
        url = (
            f"https://api.smartrecruiters.com/v1/companies/{encoded_slug}/postings"
            f"?limit={_SMARTREC_PAGE_SIZE}&offset={offset}&destination=PUBLIC"
        )
        headers = build_conditional_headers(url, "application/json")
        try:
            status, body_bytes, _ = await fetch_provider_bytes(
                client,
                url,
                headers=headers,
                timeout=timeout,
                max_bytes=eff_max_bytes,
                resolver=resolver,
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            kind = classify_exception(exc)
            if kind in (FailureKind.CIRCUIT_OPEN, FailureKind.RATE_LIMITED, FailureKind.RESPONSE_TOO_LARGE, FailureKind.UNSAFE_URL):
                return None, str(exc), kind
            return None, f"SmartRecruiters pagination error at offset {offset}: {exc}", kind

        if status != 200:
            return None, f"HTTP {status} at offset {offset}", classify_http_status(status)

        try:
            data = json.loads(body_bytes.decode("utf-8"))
        except Exception:
            return None, f"Invalid JSON payload at offset {offset}", FailureKind.PARSE_ERROR

        page_items, _, total_found, err = validate_smartrecruiters_page(
            data,
            requested_offset=offset,
            expected_total=expected_total,
            seen_ids=seen_ids,
            collected_count=len(collected),
            expected_company_slug=clean_slug,
        )
        if err or page_items is None or total_found is None:
            kind = (
                FailureKind.INCOMPLETE_SNAPSHOT
                if offset > 0 or (err and ("drift" in err.lower() or "duplicate" in err.lower() or "incomplete" in err.lower() or "premature" in err.lower()))
                else FailureKind.PARSE_ERROR
            )
            return None, err or "Invalid SmartRecruiters listing page", kind

        if expected_total is None:
            expected_total = total_found

        if total_found == 0:
            return [], None, None

        collected.extend(page_items)
        if len(collected) >= expected_total:
            break

        next_offset = offset + len(page_items)
        if next_offset <= offset:
            return None, "Zero-progress SmartRecruiters pagination", FailureKind.INCOMPLETE_SNAPSHOT
        offset = next_offset

    if expected_total is None or len(collected) != expected_total or len(seen_ids) != expected_total:
        return None, "Incomplete SmartRecruiters snapshot total mismatch", FailureKind.INCOMPLETE_SNAPSHOT

    return collected, None, None


async def fetch_smartrecruiters_postings_snapshot(
    slug: str,
    client: httpx.AsyncClient,
    *,
    timeout: float = 10.0,
    resolver: DnsResolver | None = None,
    max_bytes: int | None = None,
) -> tuple[list[dict] | None, str | None]:
    """
    Sequentially drain all public SmartRecruiters listing pages for ``slug`` with
    atomic snapshot validation and zero arbitrary page/job caps.
    """
    items, err, _ = await _fetch_smartrecruiters_snapshot_with_kind(
        slug,
        client,
        timeout=timeout,
        resolver=resolver,
        max_bytes=max_bytes,
    )
    return items, err


def _extract_smartrecruiters_listing(
    raw: RawJobPosting,
    *,
    logo_url: str | None,
    logo_source: str | None,
    logo_verified: bool,
) -> JobListing:
    canonical = JobExtractionService.extract(raw)
    listing = CanonicalJobAdapter.to_listing(canonical)
    listing.provider = "smartrecruiters"
    listing.ats_source = "smartrecruiters"
    listing.data_source = "api"
    if logo_verified and logo_url and not listing.company_logo_url:
        listing.company_logo_url = logo_url
        listing.company_logo_source = logo_source
        listing.company_logo_verified = True
    return listing


async def hydrate_smartrecruiters_board_jobs(
    slug: str,
    raw_items: list[dict],
    client: httpx.AsyncClient,
    *,
    board_company_name: str | None = None,
    board_logo_url: str | None = None,
    board_logo_source: str | None = None,
    board_logo_verified: bool = False,
    board_logo_checked_at: float | None = None,
    registry: object | None = None,
    known_monitored_jobs: dict[str, tuple[JobListing, float]] | None = None,
    known_detail_states: dict[str, MonitoredJobDetailState] | None = None,
    detail_states_out: dict[str, MonitoredJobDetailState] | None = None,
    detail_revalidate_ttl_seconds: float = 21600.0,
    max_new_hydrations_per_poll: int = 20,
    max_revalidations_per_poll: int = 10,
    max_detail_fetches: int | None = None,
    timeout: float = 10.0,
    is_board_monitor: bool = True,
    resolver: DnsResolver | None = None,
    max_response_bytes: int | None = None,
) -> tuple[list[JobListing], set[str]]:
    """
    Shared SmartRecruiters listing + bounded fair detail hydration path used by both
    ``SmartRecruitersBoardAdapter`` and ``probe_smartrecruiters_board``.

    - Validates every ``ref`` detail URL before fetching.
    - Separates pending/new hydration from stale-detail TTL revalidation.
    - Orders already-known pending unhydrated jobs ahead of newly arrived jobs so
      old pending items never starve on active boards.
    - Preserves rich cached listings on detail 404 or transient failure.
    """
    from src.ats.ats_api_client import (
        enrich_smartrecruiters_board_identity,
        smartrecruiters_payload_to_raw,
        validate_smartrecruiters_ref_url,
    )
    from src.extraction.logo_extractor import LogoResult

    clean_slug = (slug or "").strip().lower()
    known = known_monitored_jobs or {}
    known_states = known_detail_states or {}
    now = epoch_now()

    company_name = board_company_name or humanize_slug(clean_slug)
    company_ident_for_url: str | None = None
    for item in raw_items:
        comp = item.get("company")
        if isinstance(comp, dict):
            cn = comp.get("name")
            if isinstance(cn, str) and cn.strip():
                company_name = cn.strip()
            ci = comp.get("identifier")
            if isinstance(ci, str) and ci.strip() and not company_ident_for_url:
                company_ident_for_url = ci.strip()
            if company_name and company_ident_for_url:
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

    ordered_ids: list[str] = []
    item_by_id: dict[str, dict] = {}
    item_hashes: dict[str, str] = {}

    # Priority queues:
    # - pending_old: previously known jobs still lacking detail hydration whose retry is due
    # - changed_known: already-hydrated jobs whose listing item payload changed
    # - brand_new: jobs never seen before
    # - stale_reval: already-hydrated jobs due for TTL refresh or failed-refresh retry
    pending_old: list[tuple[float, int, str]] = []
    changed_known: list[tuple[int, str]] = []
    brand_new: list[tuple[int, str]] = []
    stale_reval: list[tuple[int, float, str]] = []

    for idx, item in enumerate(raw_items):
        pid = str(item.get("id") or "").strip()
        if not pid:
            continue
        ordered_ids.append(pid)
        item_by_id[pid] = item
        item_hash = _smartrecruiters_listing_item_hash(item)
        item_hashes[pid] = item_hash

        job_id = f"smartrecruiters:{clean_slug}:{pid}"
        cached_entry = known.get(job_id)
        prev_state = known_states.get(job_id)

        if cached_entry is None:
            brand_new.append((idx, pid))
            continue

        prev_hydrated_at = resolve_prev_hydrated_at(prev_state, cached_entry)

        if prev_hydrated_at is None:
            # Respect meaningful listing changes even while an unhydrated job is in retry backoff,
            # while keeping backoff intact for unchanged listings.
            listing_changed = (
                prev_state is not None
                and prev_state.listing_item_hash is not None
                and prev_state.listing_item_hash != item_hash
            )
            if listing_changed:
                changed_known.append((idx, pid))
            else:
                # Known job still awaiting initial detail hydration (never starve behind new arrivals)
                retry_at = prev_state.detail_next_retry_at if prev_state is not None else None
                if retry_at is None or now >= float(retry_at):
                    sort_ts = float(retry_at) if retry_at is not None else float(cached_entry[1] or 0.0)
                    pending_old.append((sort_ts, idx, pid))
            continue

        listing_changed = (
            prev_state is None
            or prev_state.listing_item_hash is None
            or prev_state.listing_item_hash != item_hash
        )
        if listing_changed:
            changed_known.append((idx, pid))
        else:
            is_due, tier, sort_ts = classify_detail_candidate(
                now,
                cached_entry,
                prev_state,
                detail_revalidate_ttl_seconds,
            )
            if is_due:
                stale_reval.append((tier, sort_ts, pid))

    fetch_ids = select_fair_detail_hydration_batch(
        pending_old=pending_old,
        changed_known=changed_known,
        brand_new=brand_new,
        stale_candidates=stale_reval,
        max_new_hydrations_per_poll=max_new_hydrations_per_poll,
        max_revalidations_per_poll=max_revalidations_per_poll,
        max_detail_fetches=max_detail_fetches,
    )
    fetch_set = set(fetch_ids)

    detail_results: dict[str, tuple[int | None, dict | None, str | None]] = {}
    detail_urls: list[tuple[str, str]] = []
    for pid in fetch_ids:
        item = item_by_id[pid]
        raw_ref = item.get("ref")
        if raw_ref is not None:
            detail_url = validate_smartrecruiters_ref_url(
                raw_ref if isinstance(raw_ref, str) else None,
                expected_company_slug=clean_slug,
                expected_job_id=pid,
            )
            if detail_url is None:
                detail_results[pid] = (200, None, "invalid_ref_url")
                continue
        else:
            detail_url = (
                f"https://api.smartrecruiters.com/v1/companies/"
                f"{quote(clean_slug, safe='-_.~')}/postings/{quote(pid, safe='-_.~')}"
            )
        detail_urls.append((pid, detail_url))

    if detail_urls:
        detail_results.update(
            await fetch_detail_json_batch(
                client,
                detail_urls,
                concurrency=3,
                timeout=timeout,
                max_bytes=max_response_bytes,
                resolver=resolver,
            )
        )

    # Bounded cached logo enrichment (at most 1 posting-page HTML fetch per uncached board)
    if not resolved_logo.url and board_logo_checked_at is None:
        sample_posting_url: str | None = None
        for pid in fetch_ids:
            status_code, payload, _ = detail_results.get(pid, (None, None, None))
            if status_code == 200 and isinstance(payload, dict):
                pu = payload.get("postingUrl")
                if isinstance(pu, str) and pu.strip():
                    sample_posting_url = pu.strip()
                    break
        if not sample_posting_url and ordered_ids:
            ident = company_ident_for_url or clean_slug
            sample_posting_url = (
                f"https://jobs.smartrecruiters.com/{quote(ident, safe='-_.~')}/"
                f"{quote(ordered_ids[0], safe='-_.~')}"
            )
        if sample_posting_url:
            try:
                _, enriched_logo = await enrich_smartrecruiters_board_identity(
                    clean_slug,
                    client,
                    registry=registry,
                    use_resilience=True,
                    posting_url=sample_posting_url,
                    company_name=company_name,
                )
                if enriched_logo.url and enriched_logo.verified:
                    resolved_logo = enriched_logo
            except asyncio.CancelledError:
                raise
            except Exception:
                pass

    logo_url = resolved_logo.url if resolved_logo.verified else None
    logo_source = resolved_logo.source if resolved_logo.verified else None
    logo_verified = bool(resolved_logo.verified and resolved_logo.url)

    listings: list[JobListing] = []
    refreshed_job_ids: set[str] = set()

    def _emit_preserved_or_fallback(
        item: dict,
        jid: str,
        cached: tuple[JobListing, float] | None,
        new_state: MonitoredJobDetailState,
        *,
        item_listing_changed: bool = False,
    ) -> None:
        if cached is not None:
            existing_listing = cached[0]
            update_fields: dict[str, object] = {}
            if (
                item_listing_changed
                or not existing_listing.description_ok
                or new_state.detail_last_hydrated_at is None
            ):
                raw_listing = smartrecruiters_payload_to_raw(
                    item,
                    company_slug=clean_slug,
                    default_company_name=company_name,
                    query_used=clean_slug,
                    is_board_monitor=is_board_monitor,
                    company_logo_url=logo_url,
                    company_logo_source=logo_source,
                    company_logo_verified=logo_verified,
                )
                if raw_listing is not None and raw_listing.raw_title and raw_listing.source_url:
                    fresh_fallback = _extract_smartrecruiters_listing(
                        raw_listing,
                        logo_url=logo_url,
                        logo_source=logo_source,
                        logo_verified=logo_verified,
                    )
                    update_fields.update(
                        {
                            "title": fresh_fallback.title,
                            "company": fresh_fallback.company,
                            "location": fresh_fallback.location,
                            "raw_location": fresh_fallback.raw_location,
                            "is_remote": fresh_fallback.is_remote,
                            "work_model": fresh_fallback.work_model,
                            "work_model_source": fresh_fallback.work_model_source,
                            "work_model_evidence": fresh_fallback.work_model_evidence,
                            "raw_workplace_type": fresh_fallback.raw_workplace_type,
                            "employment_type": fresh_fallback.employment_type,
                            "department": fresh_fallback.department,
                            "posted_at": fresh_fallback.posted_at,
                            "freshness_label": fresh_fallback.freshness_label,
                            "scraped_at": fresh_fallback.scraped_at,
                        }
                    )
                    if not existing_listing.description_ok or not existing_listing.source_url:
                        update_fields["source_url"] = fresh_fallback.source_url
                    if not existing_listing.description_ok or not existing_listing.apply_url:
                        update_fields["apply_url"] = fresh_fallback.apply_url
            if logo_verified and logo_url and not existing_listing.company_logo_url:
                update_fields["company_logo_url"] = logo_url
                update_fields["company_logo_source"] = logo_source
                update_fields["company_logo_verified"] = True
            if update_fields:
                existing_listing = existing_listing.model_copy(update=update_fields)
            listings.append(existing_listing)
            if detail_states_out is not None:
                detail_states_out[jid] = new_state
            return

        raw_listing = smartrecruiters_payload_to_raw(
            item,
            company_slug=clean_slug,
            default_company_name=company_name,
            query_used=clean_slug,
            is_board_monitor=is_board_monitor,
            company_logo_url=logo_url,
            company_logo_source=logo_source,
            company_logo_verified=logo_verified,
        )
        if raw_listing is None or not raw_listing.raw_title or not raw_listing.source_url:
            return
        fallback_listing = _extract_smartrecruiters_listing(
            raw_listing,
            logo_url=logo_url,
            logo_source=logo_source,
            logo_verified=logo_verified,
        )
        listings.append(fallback_listing)
        if detail_states_out is not None:
            detail_states_out[fallback_listing.id] = new_state

    for pid in ordered_ids:
        item = item_by_id[pid]
        job_id = f"smartrecruiters:{clean_slug}:{pid}"
        item_hash = item_hashes[pid]
        cached_entry = known.get(job_id)
        prev_state = known_states.get(job_id)
        item_changed = prev_state is not None and prev_state.listing_item_hash != item_hash
        prev_hydrated_at = resolve_prev_hydrated_at(prev_state, cached_entry)

        if pid in fetch_set:
            status_code, payload, err_reason = detail_results.get(pid, (None, None, None))
            if status_code == 200 and isinstance(payload, dict) and err_reason is None:
                raw = smartrecruiters_payload_to_raw(
                    payload,
                    company_slug=clean_slug,
                    default_job_id=pid,
                    default_company_name=company_name,
                    query_used=clean_slug,
                    is_board_monitor=is_board_monitor,
                    company_logo_url=logo_url,
                    company_logo_source=logo_source,
                    company_logo_verified=logo_verified,
                )
                if raw is not None and raw.raw_title and raw.source_url:
                    listing = _extract_smartrecruiters_listing(
                        raw,
                        logo_url=logo_url,
                        logo_source=logo_source,
                        logo_verified=logo_verified,
                    )
                    listings.append(listing)
                    refreshed_job_ids.add(listing.id)
                    if detail_states_out is not None:
                        detail_states_out[listing.id] = build_hydrated_detail_state(
                            now,
                            listing_item_hash=item_hash,
                        )
                    continue

                _emit_preserved_or_fallback(
                    item,
                    job_id,
                    cached_entry,
                    build_detail_failure_state(
                        status_code=200,
                        err_reason=err_reason,
                        prev_state=prev_state,
                        prev_hydrated_at=prev_hydrated_at,
                        now=now,
                        ttl_seconds=detail_revalidate_ttl_seconds,
                        invalid_detail_override=True,
                        listing_item_hash=item_hash,
                    ),
                    item_listing_changed=item_changed,
                )
                continue

            _emit_preserved_or_fallback(
                item,
                job_id,
                cached_entry,
                build_detail_failure_state(
                    status_code=status_code,
                    err_reason=err_reason,
                    prev_state=prev_state,
                    prev_hydrated_at=prev_hydrated_at,
                    now=now,
                    ttl_seconds=detail_revalidate_ttl_seconds,
                    listing_item_hash=item_hash,
                ),
                item_listing_changed=item_changed,
            )
            continue

        if cached_entry is not None:
            _emit_preserved_or_fallback(
                item,
                job_id,
                cached_entry,
                preserve_cached_detail_state(
                    prev_state,
                    prev_hydrated_at,
                    cached_entry,
                    now,
                    listing_item_hash=item_hash,
                ),
                item_listing_changed=item_changed,
            )
            continue

        # New posting deferred beyond this round's detail budget: persist pending state
        _emit_preserved_or_fallback(
            item,
            job_id,
            None,
            build_deferred_detail_state(
                now,
                detail_status="pending_hydration",
                last_error="deferred_pending_hydration",
                listing_item_hash=item_hash,
            ),
        )

    return listings, refreshed_job_ids


class SmartRecruitersBoardAdapter:
    """
    SmartRecruiters company-board adapter.

    - Sequential full pagination (limit=100, destination=PUBLIC).
    - Strict atomic snapshot validation (no partial closure or partial emission).
    - Full-board fingerprint without multi-page ETag short-circuiting.
    - Fair, bounded per-poll detail hydration via validated ``ref`` URLs.
    - Requires 2 independent complete snapshots before closing missing jobs.
    """

    def __init__(
        self,
        detail_revalidate_ttl_seconds: float = 21600.0,
        max_new_hydrations_per_poll: int = 20,
        max_revalidations_per_poll: int = 10,
    ) -> None:
        self.detail_revalidate_ttl_seconds = float(detail_revalidate_ttl_seconds)
        self.max_new_hydrations_per_poll = int(max_new_hydrations_per_poll)
        self.max_revalidations_per_poll = int(max_revalidations_per_poll)

    async def check_board(
        self,
        board: CompanyBoard,
        client: httpx.AsyncClient,
        timeout: float = 10.0,
        *,
        clock: Clock | None = None,
        resolver: DnsResolver | None = None,
        max_response_bytes: int | None = None,
        **kwargs,
    ) -> BoardCheckResult:
        policy = get_reconciliation_policy("smartrecruiters")
        if not validate_board_token_safety(board.board_token):
            return failure_result(
                kind=FailureKind.UNSAFE_URL,
                error="Invalid SmartRecruiters board token",
                policy=policy,
            )

        eff_max_bytes = (
            int(max_response_bytes)
            if max_response_bytes is not None
            else int(kwargs.get("max_response_bytes") or settings.max_response_bytes)
        )

        with use_clock(clock):
            try:
                raw_items, snapshot_err, snapshot_kind = await _fetch_smartrecruiters_snapshot_with_kind(
                    board.board_token,
                    client,
                    timeout=timeout,
                    resolver=resolver,
                    max_bytes=eff_max_bytes,
                )
                if snapshot_err or raw_items is None:
                    return failure_result(
                        kind=snapshot_kind or FailureKind.UNKNOWN,
                        error=snapshot_err or "SmartRecruiters snapshot failed",
                        policy=policy,
                    )

                fingerprint_items: list[tuple[str, str | None, str | None]] = []
                for item in raw_items:
                    pid = str(item.get("id") or "").strip()
                    ts = str(item.get("releasedDate") or "")
                    ch = _smartrecruiters_listing_item_hash(item)
                    fingerprint_items.append((pid, ts, ch))

                fingerprint = compute_board_fingerprint(fingerprint_items)
                known_monitored: dict[str, tuple[JobListing, float]] = kwargs.get("known_monitored_jobs") or {}
                known_detail_states: dict[str, MonitoredJobDetailState] = (
                    kwargs.get("known_detail_states") or {}
                )
                now = epoch_now()

                has_missing_candidates = any(
                    st.missing_confirmation_count > 0 for st in known_detail_states.values()
                )

                fingerprint_changed = not (
                    board.content_fingerprint and fingerprint == board.content_fingerprint
                )

                has_due_work = False
                if not fingerprint_changed and not has_missing_candidates:
                    for item in raw_items:
                        pid = str(item.get("id") or "").strip()
                        jid = f"smartrecruiters:{board.board_token.strip().lower()}:{pid}"
                        cached = known_monitored.get(jid)
                        d_state = known_detail_states.get(jid)
                        if cached is None:
                            has_due_work = True
                            break
                        if d_state is None or d_state.listing_item_hash != _smartrecruiters_listing_item_hash(item):
                            has_due_work = True
                            break
                        if d_state.detail_last_hydrated_at is None:
                            if d_state.detail_next_retry_at is None or now >= float(d_state.detail_next_retry_at):
                                has_due_work = True
                                break
                        else:
                            is_due, _, _ = classify_detail_candidate(
                                now,
                                cached,
                                d_state,
                                self.detail_revalidate_ttl_seconds,
                            )
                            if is_due:
                                has_due_work = True
                                break

                if not fingerprint_changed and not has_due_work and not has_missing_candidates:
                    return BoardCheckResult(
                        success=True,
                        not_modified=True,
                        content_fingerprint=fingerprint,
                        reconciliation_policy=policy,
                    )

                detail_states_out: dict[str, MonitoredJobDetailState] = {}
                listings, refreshed_job_ids = await hydrate_smartrecruiters_board_jobs(
                    board.board_token,
                    raw_items,
                    client,
                    board_company_name=board.company_name,
                    board_logo_url=board.company_logo_url,
                    board_logo_source=board.company_logo_source,
                    board_logo_verified=bool(board.company_logo_verified),
                    board_logo_checked_at=board.company_logo_checked_at,
                    registry=kwargs.get("registry"),
                    known_monitored_jobs=known_monitored,
                    known_detail_states=known_detail_states,
                    detail_states_out=detail_states_out,
                    detail_revalidate_ttl_seconds=self.detail_revalidate_ttl_seconds,
                    max_new_hydrations_per_poll=self.max_new_hydrations_per_poll,
                    max_revalidations_per_poll=self.max_revalidations_per_poll,
                    timeout=timeout,
                    is_board_monitor=True,
                    resolver=resolver,
                    max_response_bytes=eff_max_bytes,
                )

                return BoardCheckResult(
                    success=True,
                    not_modified=False,
                    listings=listings,
                    content_fingerprint=fingerprint,
                    refreshed_job_ids=refreshed_job_ids,
                    detail_states=detail_states_out,
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


# ---------------------------------------------------------------------------
# Teamtailor
# ---------------------------------------------------------------------------

_TEAMTAILOR_RSS_CAP = 100
_TEAMTAILOR_HTML_MAX_PAGES = 20
_TEAMTAILOR_HTML_MAX_ITEMS = 500
_TEAMTAILOR_LOC_NS = "{https://teamtailor.com/locations}"
_TEAMTAILOR_JOB_ID_PATH_RE = re.compile(r"^/(?:[a-z]{2}(?:-[a-z]{2,4})?/)?jobs/(\d+)(?:-[^/?#]+)?/?$", re.IGNORECASE)
_TEAMTAILOR_NEXT_PAGE_RE = re.compile(r"[?&]page=(\d+)", re.IGNORECASE)
_XML_UNSAFE_DECL_RE = re.compile(rb"<!(?:DOCTYPE|ENTITY)\b", re.IGNORECASE)


def _extract_tt_rss_location_list(item_el) -> list[str]:
    """Return all deduplicated formatted ``<tt:location>`` labels without length truncation."""
    locs_el = item_el.find(f"{_TEAMTAILOR_LOC_NS}locations")
    if locs_el is None:
        return []
    compact: list[str] = []
    for loc_el in locs_el.findall(f"{_TEAMTAILOR_LOC_NS}location"):
        name = (loc_el.findtext(f"{_TEAMTAILOR_LOC_NS}name") or "").strip()
        city = (loc_el.findtext(f"{_TEAMTAILOR_LOC_NS}city") or "").strip()
        country = (loc_el.findtext(f"{_TEAMTAILOR_LOC_NS}country") or "").strip()
        label = ""
        if city and country and city.lower() != country.lower():
            label = f"{city}, {country}"
        elif city:
            label = city
        elif country:
            label = country
        elif name:
            label = name
        if label and label not in compact:
            compact.append(label)
    return compact


def _format_tt_rss_locations(item_el) -> tuple[str | None, str | None]:
    """Extract compact and preserved Teamtailor RSS <tt:locations> text."""
    locs_el = item_el.find(f"{_TEAMTAILOR_LOC_NS}locations")
    if locs_el is None:
        return None, None
    compact = _extract_tt_rss_location_list(item_el)
    raw_names: list[str] = [
        (loc_el.findtext(f"{_TEAMTAILOR_LOC_NS}name") or "").strip()
        for loc_el in locs_el.findall(f"{_TEAMTAILOR_LOC_NS}location")
        if (loc_el.findtext(f"{_TEAMTAILOR_LOC_NS}name") or "").strip()
    ]

    raw_loc = ", ".join(raw_names) if raw_names else (", ".join(compact) if compact else None)
    if not compact:
        return None, raw_loc
    joined = "; ".join(compact)
    if len(joined) > 80:
        fitted: list[str] = []
        for entry in compact:
            cand = "; ".join([*fitted, entry])
            if len(cand) <= 68:
                fitted.append(entry)
            else:
                break
        rem = len(compact) - len(fitted)
        joined = f"{'; '.join(fitted)} (+{rem} more)" if fitted and rem > 0 else (compact[0][:77] + "...")
    return joined, raw_loc or joined


def _teamtailor_rss_item_hash(item: dict) -> str:
    return canonical_content_hash(item)


def parse_teamtailor_rss_feed(
    xml_bytes: bytes,
) -> tuple[list[dict], dict[str, str], str | None]:
    """
    Strictly parse and validate a Teamtailor ``/jobs.rss`` feed.

    Returns ``(items, channel_meta, error)``. Rejects unsafe DOCTYPE/ENTITY
    declarations anywhere in the payload, malformed XML, missing ``<rss><channel>``,
    items without valid numeric Teamtailor job URLs/titles, or duplicate job IDs.
    """
    import xml.etree.ElementTree as ET
    from urllib.parse import urlparse

    from src.safety.url_safety import is_safe_public_https_url

    if not xml_bytes or not xml_bytes.strip():
        return [], {}, "Empty Teamtailor RSS response"
    if _XML_UNSAFE_DECL_RE.search(xml_bytes):
        return [], {}, "Rejected unsafe DOCTYPE/ENTITY declaration in Teamtailor XML"

    try:
        text = xml_bytes.decode("utf-8")
        root = ET.fromstring(text)
    except Exception as exc:
        return [], {}, f"Malformed Teamtailor RSS XML: {exc}"

    if root.tag != "rss":
        return [], {}, f"Unexpected Teamtailor XML root tag: {root.tag!r}"
    channel = root.find("channel")
    if channel is None:
        return [], {}, "Teamtailor RSS missing <channel> element"

    channel_title = (channel.findtext("title") or "").strip()
    channel_link = (channel.findtext("link") or "").strip()
    channel_meta = {"channel_title": channel_title, "channel_link": channel_link}

    items: list[dict] = []
    seen_ids: set[str] = set()
    for el in channel.findall("item"):
        title = (el.findtext("title") or "").strip()
        link = (el.findtext("link") or "").strip()
        if not title:
            return [], channel_meta, "Teamtailor RSS item missing title"
        if not link or not is_safe_public_https_url(link):
            return [], channel_meta, f"Teamtailor RSS item has invalid/unsafe link: {link!r}"

        parsed_link = urlparse(link)
        m_job = _TEAMTAILOR_JOB_ID_PATH_RE.match(parsed_link.path or "")
        if not m_job:
            return [], channel_meta, f"Teamtailor RSS item link missing numeric job ID: {link!r}"
        job_id = m_job.group(1)
        if job_id in seen_ids:
            return [], channel_meta, f"Duplicate Teamtailor job ID in RSS snapshot: {job_id}"
        seen_ids.add(job_id)

        pub_date = (el.findtext("pubDate") or "").strip() or None
        description_html = (el.findtext("description") or "").strip()
        remote_raw = (el.findtext("remoteStatus") or "").strip().lower()
        guid = (el.findtext("guid") or "").strip() or None
        department = (el.findtext(f"{_TEAMTAILOR_LOC_NS}department") or "").strip() or None
        role = (el.findtext(f"{_TEAMTAILOR_LOC_NS}role") or "").strip() or None
        display_loc, raw_loc = _format_tt_rss_locations(el)
        all_locs = _extract_tt_rss_location_list(el)

        items.append(
            {
                "job_id": job_id,
                "title": title,
                "link": link,
                "description_html": description_html,
                "pub_date": pub_date,
                "remote_status": None if remote_raw in ("", "none") else remote_raw,
                "guid": guid,
                "department": department,
                "role": role,
                "location": display_loc,
                "raw_location": raw_loc,
                "all_locations": all_locs,
                "company_name": channel_title or None,
            }
        )

    return items, channel_meta, None


def _parse_teamtailor_html_jobs_page(
    html_text: str,
    *,
    expected_host: str,
    current_page: int = 1,
) -> tuple[list[dict], int | None, str | None]:
    """Parse one paginated Teamtailor HTML ``/jobs?page=N`` page safely."""
    from urllib.parse import urljoin, urlparse

    from bs4 import BeautifulSoup

    from src.safety.url_safety import is_safe_public_https_url

    soup = BeautifulSoup(html_text or "", "html.parser")
    frame = soup.select_one("turbo-frame#jobs_list")
    if frame is None:
        return [], None, "Teamtailor HTML page missing turbo-frame#jobs_list"

    base_url = f"https://{expected_host}/jobs"
    items: list[dict] = []
    seen_on_page: set[str] = set()
    for a in frame.select('a[href*="/jobs/"]'):
        href = str(a.get("href") or "").strip()
        if not href or "show_more" in href:
            continue
        abs_url = urljoin(base_url, href)
        if not is_safe_public_https_url(abs_url):
            continue
        parsed = urlparse(abs_url)
        m_job = _TEAMTAILOR_JOB_ID_PATH_RE.match(parsed.path or "")
        if not m_job:
            continue
        job_id = m_job.group(1)
        if job_id in seen_on_page:
            continue
        seen_on_page.add(job_id)

        title = a.get_text(" ", strip=True)
        card = a.find_parent("li") or a.parent
        meta_tokens: list[str] = []
        if card is not None:
            for sp in card.select("div span"):
                txt = sp.get_text(" ", strip=True)
                if txt and txt not in ("·", "|") and txt not in meta_tokens:
                    meta_tokens.append(txt)
        if not title:
            title = humanize_slug(parsed.path.rsplit("/", 1)[-1].split("-", 1)[-1]) or f"Job {job_id}"
        items.append(
            {
                "job_id": job_id,
                "title": title,
                "link": abs_url,
                "meta_tokens": meta_tokens,
            }
        )

    forward_pages: list[int] = []
    loop_candidates: list[int] = []
    for nav_a in frame.select('a[href*="page="]'):
        href = str(nav_a.get("href") or "")
        matches = _TEAMTAILOR_NEXT_PAGE_RE.findall(href)
        if not matches:
            continue
        try:
            target_page = int(matches[-1])
        except ValueError:
            continue
        if target_page > current_page:
            forward_pages.append(target_page)
        else:
            rel_vals = nav_a.get("rel") or []
            rel_str = " ".join(rel_vals) if isinstance(rel_vals, list) else str(rel_vals)
            label = f"{nav_a.get_text(' ', strip=True)} {rel_str} {href}".lower()
            if "show_more" in href.lower() or "next" in label or "show" in label or "more" in label:
                loop_candidates.append(target_page)

    next_page: int | None = None
    if forward_pages:
        next_page = min(forward_pages)
    elif loop_candidates:
        next_page = loop_candidates[0]

    return items, next_page, None


async def fetch_teamtailor_html_fallback(
    board_token: str,
    client: httpx.AsyncClient,
    *,
    timeout: float = 8.0,
    max_pages: int = _TEAMTAILOR_HTML_MAX_PAGES,
    max_items: int = _TEAMTAILOR_HTML_MAX_ITEMS,
    max_bytes: int | None = None,
    resolver: DnsResolver | None = None,
) -> tuple[list[dict], bool, str | None, str | None]:
    """
    Bounded HTML pagination fallback for Teamtailor boards hitting the 100-item RSS cap.

    Returns ``(html_items, fallback_complete, page1_html, error)``.
    Any non-200 HTTP response, missing frame, empty first page, repeated page,
    pagination loop, or page/item cap sets ``fallback_complete=False`` so callers
    never trigger missing-job auto-closure from an incomplete snapshot.
    """
    clean_slug = board_token.strip().lower()
    encoded_slug = quote(clean_slug, safe="-_.~")
    host = f"{encoded_slug}.teamtailor.com"
    byte_cap = int(max_bytes or settings.max_response_bytes)

    tracker = HtmlPaginationTracker(
        max_pages=max_pages,
        max_items=max_items,
        provider_label="Teamtailor HTML",
    )
    page = 1
    page1_html: str | None = None

    while True:
        can_go, gate_err = tracker.can_visit(page)
        if not can_go:
            return tracker.collected, False, page1_html, gate_err

        url = f"https://{host}/jobs?page={page}"
        try:
            status, body_bytes, _ = await fetch_provider_bytes(
                client,
                url,
                headers=build_conditional_headers(
                    url, "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8"
                ),
                timeout=timeout,
                max_bytes=byte_cap,
                follow_redirects=False,
                resolver=resolver,
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            return tracker.collected, False, page1_html, str(exc)

        if status != 200:
            return tracker.collected, False, page1_html, f"Teamtailor HTML fallback HTTP {status} on page={page}"

        html_text = body_bytes.decode("utf-8", errors="replace")
        if page == 1:
            page1_html = html_text

        page_items, next_page, parse_err = _parse_teamtailor_html_jobs_page(
            html_text,
            expected_host=host,
            current_page=page,
        )
        if parse_err:
            return tracker.collected, False, page1_html, parse_err

        done, complete, rec_err = tracker.record_page(page, page_items, next_page, id_key="job_id")
        if done:
            return tracker.collected, complete, page1_html, rec_err

        assert next_page is not None
        page = next_page


_TT_RSS_REMOTE_STATUS_MAP: dict[str, str] = {
    "fully": "remote",
    "remote": "remote",
    "hybrid": "hybrid",
    "onsite": "in_person",
    "on_site": "in_person",
}


def _teamtailor_rss_item_to_listing(
    item: dict,
    *,
    board_token: str,
    board_company_name: str | None = None,
    board_logo_url: str | None = None,
    board_logo_source: str | None = None,
    board_logo_verified: bool = False,
    board_logo_checked_at: float | None = None,
    is_board_monitor: bool = True,
) -> JobListing:
    from src.core.models import ExtractionMethod
    from src.extraction.field_normalizer import to_markdown
    from src.extraction.work_model import resolve_work_model

    clean_slug = board_token.strip().lower()
    desc_md = to_markdown(item.get("description_html")) if item.get("description_html") else None
    remote_raw = item.get("remote_status")
    mapped_workplace = _TT_RSS_REMOTE_STATUS_MAP.get(remote_raw) if remote_raw else None
    wm = resolve_work_model(
        workplace_type=mapped_workplace,
        location=item.get("location"),
        title=item.get("title"),
        trusted_description=desc_md,
    )
    comp_name = (
        (item.get("company_name") or "").strip()
        or (board_company_name or "").strip()
        or humanize_slug(clean_slug)
        or clean_slug
    )
    raw_fields: dict = {
        "guid": item.get("guid"),
        "role": item.get("role"),
        "date_field_name": "pubDate",
    }
    if item.get("raw_location"):
        raw_fields["raw_location_preserved"] = item["raw_location"]
    if item.get("all_locations"):
        raw_fields["all_locations"] = item["all_locations"]
    if remote_raw:
        raw_fields["remoteStatus"] = remote_raw
    if board_logo_url and board_logo_verified:
        raw_fields["company_logo_url"] = board_logo_url
        raw_fields["company_logo_source"] = board_logo_source
        raw_fields["company_logo_verified"] = True
        if board_logo_checked_at is not None:
            raw_fields["company_logo_checked_at"] = board_logo_checked_at

    raw = RawJobPosting(
        provider="teamtailor",
        source_url=item["link"],
        provider_job_id=item["job_id"],
        company_slug=clean_slug,
        apply_url=item["link"],
        extraction_method=ExtractionMethod.ATS_API,
        raw_title=item["title"],
        raw_company=comp_name,
        raw_location=item.get("location"),
        raw_workplace_type=mapped_workplace or remote_raw,
        workplace_type=wm.value,
        workplace_type_resolved=(wm.value is not None),
        work_model_evidence=wm.evidence,
        raw_department=item.get("department"),
        raw_date=item.get("pub_date"),
        raw_fields=raw_fields,
        raw_description=desc_md,
        description_is_authentic=bool(desc_md),
        query_used="board_monitor" if is_board_monitor else clean_slug,
    )
    canonical = JobExtractionService.extract(raw)
    listing = CanonicalJobAdapter.to_listing(canonical)
    listing.provider = "teamtailor"
    listing.id = f"teamtailor:{clean_slug}:{item['job_id']}"
    listing.company_slug = clean_slug
    return listing


def _teamtailor_html_card_to_listing(
    card: dict,
    *,
    board_token: str,
    board_company_name: str | None = None,
    board_logo_url: str | None = None,
    board_logo_source: str | None = None,
    board_logo_verified: bool = False,
) -> JobListing:
    from src.core.models import ExtractionMethod
    from src.extraction.work_model import resolve_work_model

    clean_slug = board_token.strip().lower()
    tokens: list[str] = card.get("meta_tokens") or []
    card_work_model: str | None = None
    card_location: str | None = None
    for tok in tokens:
        wm_probe = resolve_work_model(workplace_type=tok)
        if wm_probe.value is not None and not card_work_model:
            card_work_model = tok
        elif not card_location and len(tok) <= 80:
            card_location = tok

    wm = resolve_work_model(
        workplace_type=card_work_model,
        location=card_location,
        title=card["title"],
    )
    raw_fields: dict = {"card_tokens": tokens}
    if board_logo_url and board_logo_verified:
        raw_fields["company_logo_url"] = board_logo_url
        raw_fields["company_logo_source"] = board_logo_source
        raw_fields["company_logo_verified"] = True

    raw = RawJobPosting(
        provider="teamtailor",
        source_url=card["link"],
        provider_job_id=card["job_id"],
        company_slug=clean_slug,
        apply_url=card["link"],
        extraction_method=ExtractionMethod.DOM,
        raw_title=card["title"],
        raw_company=(board_company_name or "").strip() or humanize_slug(clean_slug) or clean_slug,
        raw_location=card_location,
        raw_workplace_type=card_work_model,
        workplace_type=wm.value,
        workplace_type_resolved=(wm.value is not None),
        work_model_evidence=wm.evidence,
        raw_fields=raw_fields,
        raw_description=None,
        description_is_authentic=False,
        query_used="board_monitor",
    )
    canonical = JobExtractionService.extract(raw)
    listing = CanonicalJobAdapter.to_listing(canonical)
    listing.provider = "teamtailor"
    listing.id = f"teamtailor:{clean_slug}:{card['job_id']}"
    listing.company_slug = clean_slug
    return listing


class TeamtailorBoardAdapter:
    """
    Teamtailor company-board adapter.

    Primary endpoint: ``GET https://{slug}.teamtailor.com/jobs.rss`` with ETag /
    Last-Modified ``304`` support. Because Teamtailor RSS silently caps at 100
    items and ignores ``?page=2``, boards returning >= 100 RSS items trigger a
    bounded HTML ``/jobs?page=N`` fallback; any incomplete fallback sets
    ``snapshot_complete=False`` so ``BoardMonitor`` never closes missing jobs.
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

        policy = get_reconciliation_policy("teamtailor")
        if not validate_board_token_safety(board.board_token) or not is_valid_board_slug(
            "teamtailor", board.board_token
        ):
            return failure_result(
                kind=FailureKind.UNSAFE_URL,
                error="Invalid Teamtailor board token",
                policy=policy,
            )

        clean_slug = board.board_token.strip().lower()
        encoded_slug = quote(clean_slug, safe="-_.~")
        rss_url = f"https://{encoded_slug}.teamtailor.com/jobs.rss"
        headers = build_conditional_headers(
            rss_url,
            "application/rss+xml, application/xml, text/xml;q=0.9, */*;q=0.8",
            etag=board.etag,
            last_modified=board.last_modified,
        )

        max_bytes = (
            int(max_response_bytes)
            if max_response_bytes is not None
            else int(kwargs.get("max_response_bytes") or settings.max_response_bytes)
        )
        with use_clock(clock):
            try:
                status, body_bytes, resp_headers = await fetch_provider_bytes(
                    client,
                    rss_url,
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
                        snapshot_complete=True,
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

                rss_items, channel_meta, parse_err = parse_teamtailor_rss_feed(body_bytes)
                if parse_err:
                    err_kind = (
                        FailureKind.INCOMPLETE_SNAPSHOT
                        if "duplicate" in parse_err.lower()
                        else FailureKind.PARSE_ERROR
                    )
                    return failure_result(kind=err_kind, error=parse_err, policy=policy)

                new_etag = resp_headers.get("etag")
                new_lm = resp_headers.get("last-modified")
                company_name = channel_meta.get("channel_title") or board.company_name

                fp_items: list[tuple[str, str | None, str | None]] = [
                    (it["job_id"], it.get("pub_date"), _teamtailor_rss_item_hash(it))
                    for it in rss_items
                ]

                snapshot_complete = True
                incomplete_reason: str | None = None
                html_only_cards: list[dict] = []
                page1_html: str | None = None

                if len(rss_items) >= _TEAMTAILOR_RSS_CAP:
                    html_cards, html_complete, page1_html, fallback_err = await fetch_teamtailor_html_fallback(
                        clean_slug,
                        client,
                        timeout=timeout,
                        max_pages=int(kwargs.get("html_max_pages") or _TEAMTAILOR_HTML_MAX_PAGES),
                        max_items=int(kwargs.get("html_max_items") or _TEAMTAILOR_HTML_MAX_ITEMS),
                        max_bytes=max_bytes,
                        resolver=resolver,
                    )
                    rss_ids = {it["job_id"] for it in rss_items}
                    if html_complete:
                        html_only_cards = [c for c in html_cards if c["job_id"] not in rss_ids]
                        for card in html_only_cards:
                            fp_items.append((card["job_id"], None, _teamtailor_rss_item_hash(card)))
                    else:
                        snapshot_complete = False
                        incomplete_reason = fallback_err or "incomplete_html_fallback"
                        if fallback_err:
                            logger.warning(
                                f"[teamtailor] Incomplete HTML pagination fallback for '{clean_slug}': {fallback_err}"
                            )

                fingerprint = compute_board_fingerprint(fp_items)
                if snapshot_complete and board.content_fingerprint and fingerprint == board.content_fingerprint:
                    return BoardCheckResult(
                        success=True,
                        not_modified=True,
                        etag=new_etag or board.etag,
                        last_modified=new_lm or board.last_modified,
                        content_fingerprint=fingerprint,
                        reconciliation_policy=policy,
                        snapshot_complete=True,
                    )

                logo_url = board.company_logo_url
                logo_source = board.company_logo_source
                logo_verified = bool(board.company_logo_verified)
                logo_checked_at = board.company_logo_checked_at
                if page1_html and (not logo_url or not logo_verified):
                    try:
                        from bs4 import BeautifulSoup

                        from src.extraction.logo_extractor import extract_company_logo_for_provider

                        logo_res = extract_company_logo_for_provider(
                            "teamtailor",
                            BeautifulSoup(page1_html, "html.parser"),
                            base_url=f"https://{encoded_slug}.teamtailor.com/jobs",
                        )
                        if logo_res.url and logo_res.verified:
                            logo_url = logo_res.url
                            logo_source = logo_res.source
                            logo_verified = True
                            logo_checked_at = epoch_now()
                    except asyncio.CancelledError:
                        raise
                    except Exception:
                        pass

                listings: list[JobListing] = [
                    _teamtailor_rss_item_to_listing(
                        it,
                        board_token=clean_slug,
                        board_company_name=company_name,
                        board_logo_url=logo_url,
                        board_logo_source=logo_source,
                        board_logo_verified=logo_verified,
                        board_logo_checked_at=logo_checked_at,
                        is_board_monitor=True,
                    )
                    for it in rss_items
                ]
                for card in html_only_cards:
                    listings.append(
                        _teamtailor_html_card_to_listing(
                            card,
                            board_token=clean_slug,
                            board_company_name=company_name,
                            board_logo_url=logo_url,
                            board_logo_source=logo_source,
                            board_logo_verified=logo_verified,
                        )
                    )

                return BoardCheckResult(
                    success=True,
                    not_modified=False,
                    listings=listings,
                    etag=new_etag if snapshot_complete else None,
                    last_modified=new_lm if snapshot_complete else None,
                    content_fingerprint=fingerprint if snapshot_complete else None,
                    reconciliation_policy=policy,
                    snapshot_complete=snapshot_complete,
                    incomplete_reason=incomplete_reason,
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                return failure_result(
                    kind=classify_exception(exc),
                    error=str(exc),
                    policy=policy,
                )


# ---------------------------------------------------------------------------
# Personio
# ---------------------------------------------------------------------------

_PERSONIO_ACCEPT = "application/xml, text/xml;q=0.9, */*;q=0.8"
_PERSONIO_ID_RE = re.compile(r"^\d+$")


def _encode_personio_etag(
    en_etag: str | None,
    def_etag: str | None,
    needs_fallback: bool,
) -> str | None:
    """Encode Personio single- or dual-language conditional ETags compatibly into ``company_boards.etag``."""
    if not needs_fallback:
        if not en_etag:
            return None
        return "p1:" + json.dumps({"en": en_etag, "fb": 0}, separators=(",", ":"), sort_keys=True)
    if not en_etag and not def_etag:
        return None
    return "p1:" + json.dumps({"en": en_etag, "def": def_etag, "fb": 1}, separators=(",", ":"), sort_keys=True)


def _decode_personio_etag(raw_etag: str | None) -> tuple[str | None, str | None, bool]:
    """Decode stored Personio ETag state into ``(en_etag, def_etag, needs_fallback)``."""
    if not raw_etag or not isinstance(raw_etag, str):
        return None, None, False
    cleaned = raw_etag.strip()
    if not cleaned:
        return None, None, False
    if cleaned.startswith("p1:"):
        try:
            payload = json.loads(cleaned[3:])
            if not isinstance(payload, dict):
                return None, None, False
            en_val = payload.get("en")
            def_val = payload.get("def")
            fb_val = bool(payload.get("fb"))
            return (
                str(en_val) if isinstance(en_val, str) and en_val else None,
                str(def_val) if isinstance(def_val, str) and def_val else None,
                fb_val,
            )
        except Exception:
            return None, None, False
    return cleaned, None, False


def _extract_personio_location_list(pos_el) -> list[str]:
    """Return deduplicated Personio ``<office>`` + ``<additionalOffices>`` labels without truncation."""
    ordered: list[str] = []
    seen: set[str] = set()

    def _add(val: str | None) -> None:
        text = (val or "").strip()
        if not text:
            return
        key = text.lower()
        if key not in seen:
            seen.add(key)
            ordered.append(text)

    _add(pos_el.findtext("office"))
    extra_el = pos_el.find("additionalOffices")
    if extra_el is not None:
        child_offices = extra_el.findall("office")
        if child_offices:
            for ch in child_offices:
                _add(ch.text)
        elif (extra_el.text or "").strip():
            _add(extra_el.text)
    return ordered


def _extract_personio_locations(pos_el) -> tuple[str | None, str | None]:
    """Extract compact and preserved Personio ``<office>`` + ``<additionalOffices>`` strings."""
    ordered = _extract_personio_location_list(pos_el)
    if not ordered:
        return None, None

    raw_loc = ", ".join(ordered)
    joined = "; ".join(ordered)
    if len(joined) > 80:
        fitted: list[str] = []
        for entry in ordered:
            cand = "; ".join([*fitted, entry])
            if len(cand) <= 68:
                fitted.append(entry)
            else:
                break
        rem = len(ordered) - len(fitted)
        joined = f"{'; '.join(fitted)} (+{rem} more)" if fitted and rem > 0 else (ordered[0][:77] + "...")
    return joined, raw_loc


def _normalize_personio_employment_type(
    employment_type: str | None,
    schedule: str | None,
) -> str | None:
    """Resolve Personio ``<employmentType>`` and ``<schedule>`` deterministically per ADR 0001.

    Personio separates contract duration (``employmentType="permanent"``) from working
    hours (``schedule="full-time"`` / ``"part-time"``). Permanent employment never
    implies ``full_time`` when schedule is absent, ambiguous, or unrecognized.
    """
    emp = (employment_type or "").strip().lower().replace("-", " ").replace("_", " ")
    sched = (schedule or "").strip().lower().replace("-", " ").replace("_", " ")

    if emp in {"intern", "internship", "trainee", "traineeship"}:
        return "internship"
    if emp in {"freelance", "freelancer", "fixed term", "contractor", "temp", "temporary"}:
        return "contract"
    if sched in {"part time", "teilzeit"}:
        return "part_time"
    if sched in {"full or part time", "part or full time"}:
        return None
    if sched in {"full time", "vollzeit"}:
        return "full_time"
    return None


def _extract_personio_salary(pos_el) -> dict[str, str] | None:
    """Extract non-empty ``<salaryInformation>`` child tags from a Personio ``<position>``."""
    sal_el = pos_el.find("salaryInformation")
    if sal_el is None:
        return None
    out: dict[str, str] = {}
    for key in ("min", "max", "currencySymbol", "currencyCode", "type"):
        val = (sal_el.findtext(key) or "").strip()
        if val:
            out[key] = val
    return out or None


def _attach_personio_salary_fields(sal_info: dict[str, str] | None, raw_fields: dict) -> None:
    """Preserve raw salary metadata and expose ``baseSalary`` only when positive bounds exist."""
    if not sal_info:
        return
    raw_fields["salaryInformation"] = sal_info

    def _positive_num(raw_val: str | None) -> float | None:
        if not raw_val:
            return None
        try:
            num = float(raw_val.replace(",", "").strip())
            return num if num > 0 else None
        except Exception:
            return None

    min_num = _positive_num(sal_info.get("min"))
    max_num = _positive_num(sal_info.get("max"))
    if min_num is None and max_num is None:
        return

    curr = sal_info.get("currencyCode") or sal_info.get("currencySymbol")
    val_block: dict[str, str] = {}
    if min_num is not None:
        val_block["minValue"] = sal_info["min"]
    if max_num is not None:
        val_block["maxValue"] = sal_info["max"]
    if sal_info.get("type"):
        val_block["unitText"] = sal_info["type"]
    raw_fields["baseSalary"] = {"currency": curr, "value": val_block}


def parse_personio_xml_feed(xml_bytes: bytes) -> tuple[list[dict], str | None]:
    """
    Strictly parse and validate a Personio public ``/xml`` recruiting feed.

    Returns ``(items, error)``. Rejects empty payloads, full-payload ``<!DOCTYPE``
    or ``<!ENTITY`` declarations, invalid UTF-8 / malformed XML, non-``<workzag-jobs>``
    root elements, non-numeric or empty ``<id>``, missing ``<name>``, and duplicate IDs.
    An empty valid ``<workzag-jobs></workzag-jobs>`` returns ``([], None)``.
    """
    import html as html_lib
    import xml.etree.ElementTree as ET

    if not xml_bytes or not xml_bytes.strip():
        return [], "Empty Personio XML response"
    if _XML_UNSAFE_DECL_RE.search(xml_bytes):
        return [], "Rejected unsafe DOCTYPE/ENTITY declaration in Personio XML"

    try:
        text = xml_bytes.decode("utf-8")
        root = ET.fromstring(text)
    except Exception as exc:
        return [], f"Malformed Personio XML: {exc}"

    if root.tag != "workzag-jobs":
        return [], f"Unexpected Personio XML root tag: {root.tag!r}"

    items: list[dict] = []
    seen_ids: set[str] = set()
    for pos in root.findall("position"):
        job_id = (pos.findtext("id") or "").strip()
        if not job_id or not _PERSONIO_ID_RE.match(job_id):
            return [], f"Personio XML position has invalid/missing numeric <id>: {job_id!r}"
        if job_id in seen_ids:
            return [], f"Duplicate Personio job ID in XML snapshot: {job_id}"
        seen_ids.add(job_id)

        name = (pos.findtext("name") or "").strip()
        if not name:
            return [], f"Personio XML position {job_id} missing required <name>"

        location, raw_loc = _extract_personio_locations(pos)
        all_locs = _extract_personio_location_list(pos)

        desc_blocks: list[str] = []
        jd_parent = pos.find("jobDescriptions")
        if jd_parent is not None:
            for block in jd_parent.findall("jobDescription"):
                heading = (block.findtext("name") or "").strip()
                val_html = (block.findtext("value") or "").strip()
                if not val_html:
                    continue
                if heading:
                    desc_blocks.append(f"<h4>{html_lib.escape(heading)}</h4>\n{val_html}")
                else:
                    desc_blocks.append(val_html)
        description_html = "\n".join(desc_blocks) if desc_blocks else None

        items.append(
            {
                "id": job_id,
                "name": name,
                "subcompany": (pos.findtext("subcompany") or "").strip() or None,
                "location": location,
                "raw_location": raw_loc,
                "all_locations": all_locs,
                "department": (pos.findtext("department") or "").strip() or None,
                "recruiting_category": (pos.findtext("recruitingCategory") or "").strip() or None,
                "employment_type": (pos.findtext("employmentType") or "").strip() or None,
                "seniority": (pos.findtext("seniority") or "").strip() or None,
                "schedule": (pos.findtext("schedule") or "").strip() or None,
                "years_of_experience": (pos.findtext("yearsOfExperience") or "").strip() or None,
                "keywords": (pos.findtext("keywords") or "").strip() or None,
                "occupation": (pos.findtext("occupation") or "").strip() or None,
                "occupation_category": (pos.findtext("occupationCategory") or "").strip() or None,
                "created_at": (pos.findtext("createdAt") or "").strip() or None,
                "salary_info": _extract_personio_salary(pos),
                "description_html": description_html,
            }
        )

    return items, None


def _merge_personio_feeds(en_items: list[dict], def_items: list[dict]) -> tuple[list[dict], str | None]:
    """
    Merge ``?language=en`` items with default ``/xml`` fallback descriptions.

    Preserves English metadata and non-empty English descriptions, fills empty
    descriptions from the default feed only, and fails closed if position ID sets differ.
    """
    en_ids = {it["id"] for it in en_items}
    def_ids = {it["id"] for it in def_items}
    if en_ids != def_ids:
        return [], "Inconsistent position ID sets between Personio EN and default XML feeds"

    def_by_id = {it["id"]: it for it in def_items}
    merged: list[dict] = []
    for it in en_items:
        copy_item = dict(it)
        if not copy_item.get("description_html"):
            copy_item["description_html"] = def_by_id[it["id"]].get("description_html")
        merged.append(copy_item)
    return merged, None


def _personio_position_to_listing(
    item: dict,
    *,
    board_token: str,
    board_company_name: str | None = None,
    is_board_monitor: bool = True,
) -> JobListing:
    """Convert a validated Personio position dictionary into a canonical ``JobListing``."""
    from src.core.models import ExtractionMethod

    clean_slug = board_token.strip().lower()
    job_url = f"https://{clean_slug}.jobs.personio.com/job/{item['id']}"
    comp_name = (
        (item.get("subcompany") or "").strip()
        or (board_company_name or "").strip()
        or humanize_slug(clean_slug)
        or clean_slug
    )
    resolved_emp = _normalize_personio_employment_type(
        item.get("employment_type"),
        item.get("schedule"),
    )

    raw_fields: dict = {"date_field_name": "createdAt"}
    if resolved_emp is None and (item.get("employment_type") or item.get("schedule")):
        # Prevent free-text fallback (e.g. matching "permanent") when Personio XML
        # already supplied structured employment fields whose hours are unspecified.
        raw_fields["skip_employment_text_fallback"] = True
    if item.get("raw_location"):
        raw_fields["raw_location_preserved"] = item["raw_location"]
    if item.get("all_locations"):
        raw_fields["all_locations"] = item["all_locations"]
    for key, src_key in (
        ("recruitingCategory", "recruiting_category"),
        ("seniority", "seniority"),
        ("yearsOfExperience", "years_of_experience"),
        ("keywords", "keywords"),
        ("occupation", "occupation"),
        ("occupationCategory", "occupation_category"),
        ("personio_employment_type", "employment_type"),
        ("personio_schedule", "schedule"),
    ):
        if item.get(src_key):
            raw_fields[key] = item[src_key]
    _attach_personio_salary_fields(item.get("salary_info"), raw_fields)

    desc_html = item.get("description_html")
    raw = RawJobPosting(
        provider="personio",
        source_url=job_url,
        provider_job_id=item["id"],
        company_slug=clean_slug,
        apply_url=job_url,
        extraction_method=ExtractionMethod.ATS_API,
        raw_title=item["name"],
        raw_company=comp_name,
        raw_location=item.get("location"),
        raw_employment_type=resolved_emp,
        raw_department=item.get("department"),
        raw_date=item.get("created_at"),
        raw_fields=raw_fields,
        raw_description=desc_html,
        description_is_authentic=bool(desc_html),
        query_used="board_monitor" if is_board_monitor else clean_slug,
    )
    canonical = JobExtractionService.extract(raw)
    listing = CanonicalJobAdapter.to_listing(canonical)
    listing.provider = "personio"
    listing.id = f"personio:{clean_slug}:{item['id']}"
    listing.company_slug = clean_slug
    return listing


async def _get_personio_xml_with_kind(
    client: httpx.AsyncClient,
    url: str,
    *,
    timeout: float,
    max_bytes: int,
    if_none_match: str | None = None,
    resolver: DnsResolver | None = None,
) -> tuple[int, list[dict] | None, str | None, str | None, FailureKind | None]:
    headers = build_conditional_headers(url, _PERSONIO_ACCEPT, etag=if_none_match)
    status, body_bytes, resp_headers = await fetch_provider_bytes(
        client,
        url,
        headers=headers,
        timeout=timeout,
        max_bytes=max_bytes,
        follow_redirects=False,
        resolver=resolver,
    )
    if status == 304 and if_none_match:
        return 304, None, resp_headers.get("etag") or if_none_match, None, None
    if status == 404:
        return 404, None, None, "Board not found (HTTP 404)", FailureKind.NOT_FOUND
    if status != 200:
        return status, None, None, f"HTTP {status}", classify_http_status(status)

    items, parse_err = parse_personio_xml_feed(body_bytes)
    if parse_err:
        err_kind = (
            FailureKind.INCOMPLETE_SNAPSHOT
            if "duplicate" in parse_err.lower()
            else FailureKind.PARSE_ERROR
        )
        return 200, None, resp_headers.get("etag"), parse_err, err_kind
    return 200, items, resp_headers.get("etag"), None, None


async def _get_personio_xml(
    client: httpx.AsyncClient,
    url: str,
    *,
    timeout: float,
    max_bytes: int,
    if_none_match: str | None = None,
    resolver: DnsResolver | None = None,
) -> tuple[int, list[dict] | None, str | None, str | None]:
    """
    Execute one bounded Personio XML GET (optionally conditional).

    Returns ``(status_code, parsed_items_or_none, response_etag, error_or_none)``.
    """
    status, items, etag, err, _ = await _get_personio_xml_with_kind(
        client,
        url,
        timeout=timeout,
        max_bytes=max_bytes,
        if_none_match=if_none_match,
        resolver=resolver,
    )
    return status, items, etag, err


class PersonioBoardAdapter:
    """
    Personio company-board adapter.

    Primary endpoint: ``GET https://{slug}.jobs.personio.com/xml?language=en``.
    When the English feed is empty or any position has empty ``<jobDescriptions>``,
    performs a bounded check/fallback to default ``GET https://{slug}.jobs.personio.com/xml``
    and tracks both ETags inside ``company_boards.etag`` so a ``304`` on one language
    never masks updates or non-empty jobs on the other. Always fails closed with
    ``snapshot_complete=False`` on errors, unsafe/malformed XML, or ID mismatches across
    bilingual feeds.
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

        policy = get_reconciliation_policy("personio")
        if not validate_board_token_safety(board.board_token) or not is_valid_board_slug(
            "personio", board.board_token
        ):
            return failure_result(
                kind=FailureKind.UNSAFE_URL,
                error="Invalid Personio board token",
                policy=policy,
            )

        clean_slug = board.board_token.strip().lower()
        encoded_slug = quote(clean_slug, safe="-_.~")
        en_url = f"https://{encoded_slug}.jobs.personio.com/xml?language=en"
        def_url = f"https://{encoded_slug}.jobs.personio.com/xml"
        max_bytes = (
            int(max_response_bytes)
            if max_response_bytes is not None
            else int(kwargs.get("max_response_bytes") or settings.max_response_bytes)
        )

        prev_en_etag, prev_def_etag, prev_fb = _decode_personio_etag(board.etag)

        with use_clock(clock):
            try:
                en_status, en_items, cur_en_etag, en_err, en_kind = await _get_personio_xml_with_kind(
                    client,
                    en_url,
                    timeout=timeout,
                    max_bytes=max_bytes,
                    if_none_match=prev_en_etag,
                    resolver=resolver,
                )
                if en_err:
                    return failure_result(
                        kind=en_kind or FailureKind.UNEXPECTED_ERROR,
                        error=en_err,
                        policy=policy,
                    )

                if en_status == 304:
                    if not prev_fb:
                        return BoardCheckResult(
                            success=True,
                            not_modified=True,
                            etag=board.etag,
                            last_modified=board.last_modified,
                            content_fingerprint=board.content_fingerprint,
                            reconciliation_policy=policy,
                            snapshot_complete=True,
                        )

                    # Bilingual fallback was required: must also validate default /xml before 304 short-circuit
                    def_status, def_items, cur_def_etag, def_err, def_kind = await _get_personio_xml_with_kind(
                        client,
                        def_url,
                        timeout=timeout,
                        max_bytes=max_bytes,
                        if_none_match=prev_def_etag,
                        resolver=resolver,
                    )
                    if def_err:
                        return failure_result(
                            kind=def_kind or FailureKind.UNEXPECTED_ERROR,
                            error=def_err,
                            policy=policy,
                        )
                    if def_status == 304:
                        return BoardCheckResult(
                            success=True,
                            not_modified=True,
                            etag=board.etag,
                            last_modified=board.last_modified,
                            content_fingerprint=board.content_fingerprint,
                            reconciliation_policy=policy,
                            snapshot_complete=True,
                        )

                    assert def_items is not None
                    _, en_items_fresh, fresh_en_etag, refetch_err, refetch_kind = await _get_personio_xml_with_kind(
                        client,
                        en_url,
                        timeout=timeout,
                        max_bytes=max_bytes,
                        if_none_match=None,
                        resolver=resolver,
                    )
                    if refetch_err or en_items_fresh is None:
                        return failure_result(
                            kind=refetch_kind or FailureKind.INCOMPLETE_SNAPSHOT,
                            error=refetch_err or "Failed to refresh EN Personio XML feed",
                            policy=policy,
                        )
                    merged_items, merge_err = _merge_personio_feeds(en_items_fresh, def_items)
                    if merge_err:
                        return failure_result(
                            kind=FailureKind.INCOMPLETE_SNAPSHOT,
                            error=merge_err,
                            policy=policy,
                        )
                    new_etag = _encode_personio_etag(fresh_en_etag or prev_en_etag, cur_def_etag, True)
                else:
                    assert en_items is not None
                    needs_fallback = (len(en_items) == 0) or any(not it.get("description_html") for it in en_items)
                    if not needs_fallback:
                        merged_items = en_items
                        new_etag = _encode_personio_etag(cur_en_etag, None, False)
                    else:
                        def_inm = prev_def_etag if (prev_fb and prev_def_etag) else None
                        def_status, def_items, cur_def_etag, def_err, def_kind = await _get_personio_xml_with_kind(
                            client,
                            def_url,
                            timeout=timeout,
                            max_bytes=max_bytes,
                            if_none_match=def_inm,
                            resolver=resolver,
                        )
                        if def_err:
                            return failure_result(
                                kind=def_kind or FailureKind.UNEXPECTED_ERROR,
                                error=def_err,
                                policy=policy,
                            )
                        if def_status == 304:
                            _, def_items, uncond_def_etag, uncond_err, uncond_kind = await _get_personio_xml_with_kind(
                                client,
                                def_url,
                                timeout=timeout,
                                max_bytes=max_bytes,
                                if_none_match=None,
                                resolver=resolver,
                            )
                            if uncond_err or def_items is None:
                                return failure_result(
                                    kind=uncond_kind or FailureKind.INCOMPLETE_SNAPSHOT,
                                    error=uncond_err or "Failed to hydrate unchanged default Personio XML feed",
                                    policy=policy,
                                )
                            cur_def_etag = uncond_def_etag or cur_def_etag
                        assert def_items is not None
                        merged_items, merge_err = _merge_personio_feeds(en_items, def_items)
                        if merge_err:
                            return failure_result(
                                kind=FailureKind.INCOMPLETE_SNAPSHOT,
                                error=merge_err,
                                policy=policy,
                            )
                        new_etag = _encode_personio_etag(cur_en_etag, cur_def_etag, True)

                fingerprint = compute_board_fingerprint(
                    [(it["id"], it.get("created_at"), canonical_content_hash(it)) for it in merged_items]
                )
                if board.content_fingerprint and fingerprint == board.content_fingerprint:
                    return BoardCheckResult(
                        success=True,
                        not_modified=True,
                        etag=new_etag or board.etag,
                        last_modified=board.last_modified,
                        content_fingerprint=fingerprint,
                        reconciliation_policy=policy,
                        snapshot_complete=True,
                    )

                listings = [
                    _personio_position_to_listing(
                        it,
                        board_token=clean_slug,
                        board_company_name=board.company_name,
                        is_board_monitor=True,
                    )
                    for it in merged_items
                ]
                return BoardCheckResult(
                    success=True,
                    not_modified=False,
                    listings=listings,
                    etag=new_etag,
                    content_fingerprint=fingerprint,
                    reconciliation_policy=policy,
                    snapshot_complete=True,
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                return failure_result(
                    kind=classify_exception(exc),
                    error=str(exc),
                    policy=policy,
                )


# ---------------------------------------------------------------------------
# Pinpoint (pinpointhq)
# ---------------------------------------------------------------------------

_PINPOINT_ACCEPT = "application/json"
_PINPOINT_UUID_IN_PATH_RE = re.compile(
    r"/postings/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})(?:/applications/new|/apply)?/?$",
    re.IGNORECASE,
)

_PINPOINT_WORKPLACE_MAP: dict[str, str] = {
    "remote": "remote",
    "fully_remote": "remote",
    "fully remote": "remote",
    "hybrid": "hybrid",
    "onsite": "in_person",
    "on_site": "in_person",
    "on-site": "in_person",
    "on site": "in_person",
    "in_person": "in_person",
    "in person": "in_person",
    "office": "in_person",
}

_PINPOINT_EMPLOYMENT_MAP: dict[str, str] = {
    "full_time": "full_time",
    "fulltime": "full_time",
    "full time": "full_time",
    "full_time_permanent": "full_time",
    "permanent_full_time": "full_time",
    "part_time": "part_time",
    "parttime": "part_time",
    "part time": "part_time",
    "part_time_permanent": "part_time",
    "permanent_part_time": "part_time",
    "contract": "contract",
    "contractor": "contract",
    "temporary": "contract",
    "temp": "contract",
    "fixed_term": "contract",
    "fixed term": "contract",
    "full_time_fixed_term": "contract",
    "part_time_fixed_term": "contract",
    "fixed_term_full_time": "contract",
    "fixed_term_part_time": "contract",
    "freelance": "contract",
    "internship": "internship",
    "intern": "internship",
    "placement": "internship",
    "apprenticeship": "internship",
}


def _normalize_pinpoint_workplace_type(
    workplace_type: str | None,
    workplace_type_text: str | None,
) -> str | None:
    for candidate in (workplace_type, workplace_type_text):
        if isinstance(candidate, str):
            norm_key = candidate.strip().lower().replace("-", "_").replace(" ", "_")
            mapped = _PINPOINT_WORKPLACE_MAP.get(norm_key) or _PINPOINT_WORKPLACE_MAP.get(candidate.strip().lower())
            if mapped:
                return mapped
    return None


def _normalize_pinpoint_employment_type(
    employment_type: str | None,
    employment_type_text: str | None,
) -> tuple[str | None, bool]:
    """
    Map Pinpoint employment_type enums conservatively per ADR 0001.

    Returns ``(normalized_type, saw_explicit_unrecognized)``.
    """
    saw_value = False
    for candidate in (employment_type, employment_type_text):
        if isinstance(candidate, str) and candidate.strip():
            saw_value = True
            norm_key = candidate.strip().lower().replace("-", "_").replace(" ", "_")
            mapped = _PINPOINT_EMPLOYMENT_MAP.get(norm_key) or _PINPOINT_EMPLOYMENT_MAP.get(candidate.strip().lower())
            if mapped:
                return mapped, False
    return None, saw_value


def _extract_pinpoint_location(loc_obj: object) -> tuple[str | None, dict[str, str] | None]:
    """
    Extract display location and non-empty structured Pinpoint location metadata.

    Prefers ``location.name`` (e.g. ``"Nigeria"``, ``"Australia (Remote)"``, ``"Remote"``)
    when present so tenant-level city defaults (e.g. Lagos HQ on regional postings) never
    overwrite an explicit country/region name, falling back to deduplicated ``city, province``.
    """
    if not isinstance(loc_obj, dict):
        return None, None

    meta: dict[str, str] = {}
    for k in ("name", "city", "province", "postal_code", "street_address"):
        v = loc_obj.get(k)
        if isinstance(v, str) and v.strip():
            meta[k] = v.strip()

    name = meta.get("name")
    city = meta.get("city")
    province = meta.get("province")

    if name:
        return name, meta

    parts: list[str] = []
    for part in (city, province):
        if part and part.lower() not in {p.lower() for p in parts}:
            parts.append(part)
    if parts:
        return ", ".join(parts), meta
    return None, meta or None


def _build_pinpoint_description_html(entry: dict) -> tuple[str | None, str | None]:
    """
    Combine Pinpoint's four structured HTML sections into canonical HTML description
    and isolate ``skills_knowledge_expertise`` for ``raw_requirements``.
    """
    import html as html_lib

    blocks: list[str] = []
    desc = entry.get("description")
    if isinstance(desc, str) and desc.strip():
        blocks.append(desc.strip())

    for body_key, header_key, default_header in (
        ("key_responsibilities", "key_responsibilities_header", "Key Responsibilities"),
        ("skills_knowledge_expertise", "skills_knowledge_expertise_header", "Skills, Knowledge & Expertise"),
        ("benefits", "benefits_header", "Benefits"),
    ):
        body = entry.get(body_key)
        if isinstance(body, str) and body.strip():
            hdr_raw = entry.get(header_key)
            hdr = hdr_raw.strip() if isinstance(hdr_raw, str) and hdr_raw.strip() else default_header
            blocks.append(f"<h4>{html_lib.escape(hdr)}</h4>\n{body.strip()}")

    combined_html = "\n".join(blocks) if blocks else None
    skills_raw = entry.get("skills_knowledge_expertise")
    requirements_html = skills_raw.strip() if isinstance(skills_raw, str) and skills_raw.strip() else None
    return combined_html, requirements_html


def parse_pinpoint_postings_json(
    payload_bytes: bytes,
    expected_slug: str | None = None,
) -> tuple[list[dict], str | None]:
    """
    Strictly parse and validate a Pinpoint public ``/postings.json`` snapshot.

    Returns ``(items, error)``. Fails closed on empty/non-UTF-8/invalid JSON, non-dict
    root, missing ``data`` list, cross-tenant URLs, missing required ``id``/``title``/``url``,
    or duplicate posting IDs. An empty ``{"data": []}`` returns ``([], None)``.
    """
    from urllib.parse import urlparse

    if not payload_bytes or not payload_bytes.strip():
        return [], "Empty Pinpoint JSON response"

    try:
        data = json.loads(payload_bytes.decode("utf-8"))
    except Exception:
        return [], "Invalid Pinpoint JSON payload"

    if not isinstance(data, dict) or not isinstance(data.get("data"), list):
        return [], "Invalid Pinpoint postings payload shape"

    clean_expected = expected_slug.strip().lower() if expected_slug else None
    items: list[dict] = []
    seen_job_ids: set[str] = set()
    seen_numeric_ids: set[str] = set()

    for entry in data["data"]:
        if not isinstance(entry, dict):
            return [], "Malformed Pinpoint posting entry (expected object)"

        raw_id = entry.get("id")
        if raw_id is None or isinstance(raw_id, (bool, list, dict)) or not str(raw_id).strip():
            return [], "Malformed Pinpoint posting missing required id"
        numeric_id = str(raw_id).strip()
        if numeric_id in seen_numeric_ids:
            return [], f"Duplicate Pinpoint numeric posting id in snapshot: {numeric_id}"
        seen_numeric_ids.add(numeric_id)

        raw_title = entry.get("title")
        if not isinstance(raw_title, str) or not raw_title.strip():
            return [], f"Malformed Pinpoint posting {numeric_id} missing required title"
        title = raw_title.strip()

        raw_url = entry.get("url")
        raw_path = entry.get("path")
        resolved_url: str | None = None
        if raw_url is not None:
            if not isinstance(raw_url, str) or not raw_url.strip():
                return [], f"Malformed Pinpoint posting {numeric_id} has invalid empty url"
            cand = raw_url.strip()
            if cand.lower().startswith("http://"):
                cand = "https://" + cand[7:]
            try:
                parsed_u = urlparse(cand)
            except Exception:
                return [], f"Invalid URL in Pinpoint posting {numeric_id}"
            host_low = (parsed_u.hostname or "").lower()
            if parsed_u.scheme.lower() != "https" or not host_low.endswith(".pinpointhq.com"):
                return [], f"Unexpected Pinpoint posting host for {numeric_id}: {host_low!r}"
            if clean_expected and host_low != f"{clean_expected}.pinpointhq.com":
                return [], (
                    f"Pinpoint tenant mismatch on posting {numeric_id}: "
                    f"expected {clean_expected!r}, got {host_low!r}"
                )
            resolved_url = cand
        elif isinstance(raw_path, str) and raw_path.strip().startswith("/") and clean_expected:
            resolved_url = f"https://{clean_expected}.pinpointhq.com{raw_path.strip()}"
        else:
            return [], f"Malformed Pinpoint posting {numeric_id} missing valid url/path"

        uuid_m = _PINPOINT_UUID_IN_PATH_RE.search(urlparse(resolved_url).path or "")
        if not uuid_m and isinstance(raw_path, str):
            uuid_m = _PINPOINT_UUID_IN_PATH_RE.search(raw_path.strip())
        job_id = uuid_m.group(1).lower() if uuid_m else numeric_id
        if job_id in seen_job_ids:
            return [], f"Duplicate Pinpoint posting id in snapshot: {job_id}"
        seen_job_ids.add(job_id)

        job_obj = entry.get("job") if isinstance(entry.get("job"), dict) else {}
        department: str | None = None
        for grp_key in ("department", "division", "structure_custom_group_one"):
            grp = job_obj.get(grp_key)
            if isinstance(grp, dict) and isinstance(grp.get("name"), str) and grp["name"].strip():
                department = grp["name"].strip()
                break

        location_display, location_meta = _extract_pinpoint_location(entry.get("location"))
        description_html, requirements_html = _build_pinpoint_description_html(entry)

        comp_visible = entry.get("compensation_visible") is True
        comp_min = entry.get("compensation_minimum")
        comp_max = entry.get("compensation_maximum")
        comp_curr = entry.get("compensation_currency")
        comp_freq = entry.get("compensation_frequency")
        comp_text = entry.get("compensation") if isinstance(entry.get("compensation"), str) else None

        items.append(
            {
                "job_id": job_id,
                "numeric_id": numeric_id,
                "title": title,
                "url": resolved_url,
                "path": raw_path.strip() if isinstance(raw_path, str) and raw_path.strip() else None,
                "location": location_display,
                "location_meta": location_meta,
                "workplace_type": entry.get("workplace_type") if isinstance(entry.get("workplace_type"), str) else None,
                "workplace_type_text": entry.get("workplace_type_text") if isinstance(entry.get("workplace_type_text"), str) else None,
                "employment_type": entry.get("employment_type") if isinstance(entry.get("employment_type"), str) else None,
                "employment_type_text": entry.get("employment_type_text") if isinstance(entry.get("employment_type_text"), str) else None,
                "department": department,
                "pinpoint_job_id": str(job_obj["id"]).strip() if job_obj.get("id") is not None else None,
                "requisition_id": job_obj.get("requisition_id").strip() if isinstance(job_obj.get("requisition_id"), str) and job_obj.get("requisition_id").strip() else None,
                "reporting_to": entry.get("reporting_to").strip() if isinstance(entry.get("reporting_to"), str) and entry.get("reporting_to").strip() else None,
                "deadline_at": entry.get("deadline_at") if isinstance(entry.get("deadline_at"), str) and entry.get("deadline_at").strip() else None,
                "compensation_visible": comp_visible,
                "compensation": comp_text.strip() if (comp_visible and comp_text and comp_text.strip()) else None,
                "compensation_minimum": comp_min if (comp_visible and isinstance(comp_min, (int, float)) and not isinstance(comp_min, bool) and comp_min > 0) else None,
                "compensation_maximum": comp_max if (comp_visible and isinstance(comp_max, (int, float)) and not isinstance(comp_max, bool) and comp_max > 0) else None,
                "compensation_currency": comp_curr.strip() if (comp_visible and isinstance(comp_curr, str) and comp_curr.strip()) else None,
                "compensation_frequency": comp_freq.strip() if (comp_visible and isinstance(comp_freq, str) and comp_freq.strip()) else None,
                "description_html": description_html,
                "requirements_html": requirements_html,
            }
        )

    return items, None


def _attach_pinpoint_compensation_fields(item: dict, raw_fields: dict) -> None:
    """Attach structured Pinpoint compensation fields only when ``compensation_visible`` is True."""
    if not item.get("compensation_visible"):
        return

    min_num = item.get("compensation_minimum")
    max_num = item.get("compensation_maximum")
    curr = item.get("compensation_currency")
    freq = item.get("compensation_frequency")

    if item.get("compensation"):
        raw_fields["compensation"] = item["compensation"]

    if min_num is None and max_num is None:
        return

    val_block: dict[str, object] = {}
    if min_num is not None:
        val_block["minValue"] = min_num
    if max_num is not None:
        val_block["maxValue"] = max_num
    if freq:
        val_block["unitText"] = freq

    raw_fields["baseSalary"] = {"currency": curr, "value": val_block}


def _pinpoint_item_to_listing(
    item: dict,
    *,
    board_token: str,
    board_company_name: str | None = None,
    board_logo_url: str | None = None,
    board_logo_source: str | None = None,
    board_logo_verified: bool = False,
    board_logo_checked_at: float | None = None,
    is_board_monitor: bool = True,
) -> JobListing:
    """Convert a validated Pinpoint posting dictionary into a canonical ``JobListing``."""
    from src.core.models import ExtractionMethod

    clean_slug = board_token.strip().lower()
    source_url = item["url"]
    if _PINPOINT_UUID_IN_PATH_RE.search(source_url) and not source_url.rstrip("/").lower().endswith("/applications/new"):
        apply_url = f"{source_url.rstrip('/')}/applications/new"
    else:
        apply_url = source_url

    comp_name = (board_company_name or "").strip() or humanize_slug(clean_slug) or clean_slug
    norm_workplace = _normalize_pinpoint_workplace_type(
        item.get("workplace_type"),
        item.get("workplace_type_text"),
    )
    norm_emp, saw_unrecognized_emp = _normalize_pinpoint_employment_type(
        item.get("employment_type"),
        item.get("employment_type_text"),
    )

    raw_fields: dict = {
        "pinpoint_posting_id": item["numeric_id"],
    }
    if norm_emp is None and saw_unrecognized_emp:
        raw_fields["skip_employment_text_fallback"] = True
    for k in (
        "workplace_type",
        "workplace_type_text",
        "employment_type",
        "employment_type_text",
        "pinpoint_job_id",
        "requisition_id",
        "reporting_to",
        "deadline_at",
    ):
        if item.get(k):
            raw_fields[k] = item[k]
    if item.get("location_meta"):
        raw_fields["location_meta"] = item["location_meta"]
    if board_logo_url and board_logo_verified:
        raw_fields["company_logo_url"] = board_logo_url
        raw_fields["company_logo_source"] = board_logo_source
        raw_fields["company_logo_verified"] = True
        if board_logo_checked_at is not None:
            raw_fields["company_logo_checked_at"] = board_logo_checked_at
    _attach_pinpoint_compensation_fields(item, raw_fields)

    desc_html = item.get("description_html")
    raw = RawJobPosting(
        provider="pinpointhq",
        source_url=source_url,
        apply_url=apply_url,
        provider_job_id=item["job_id"],
        company_slug=clean_slug,
        extraction_method=ExtractionMethod.ATS_API,
        raw_title=item["title"],
        raw_company=comp_name,
        raw_location=item.get("location"),
        raw_workplace_type=norm_workplace,
        raw_employment_type=norm_emp,
        raw_department=item.get("department"),
        # Pinpoint /postings.json omits publication timestamps (deadline_at is closing deadline, never posted_at).
        raw_date=None,
        raw_fields=raw_fields,
        raw_description=desc_html,
        raw_requirements=item.get("requirements_html"),
        description_is_authentic=bool(desc_html),
        query_used="board_monitor" if is_board_monitor else clean_slug,
    )
    canonical = JobExtractionService.extract(raw)
    listing = CanonicalJobAdapter.to_listing(canonical)
    listing.provider = "pinpointhq"
    listing.ats_source = "pinpointhq"
    listing.data_source = "api"
    listing.id = f"pinpointhq:{clean_slug}:{item['job_id']}"
    listing.company_slug = clean_slug
    listing.source_record_id = item["numeric_id"]

    aliases: list[str] = []
    for candidate_alias in (
        f"pinpointhq:{clean_slug}:{item['job_id']}",
        f"pinpointhq:{clean_slug}:{item['numeric_id']}",
    ):
        if candidate_alias not in aliases:
            aliases.append(candidate_alias)
    listing.aliases = aliases
    return listing


def resolve_pinpoint_board_timeout(
    override: float | None = None,
    *,
    bound_to_search_timeout: bool = False,
) -> float:
    """
    Resolve the effective HTTP streaming timeout for Pinpoint ``/postings.json`` fetches.

    Uses ``settings.pinpoint_board_request_timeout_seconds`` (default 25.0s, safely above
    Step 51's observed ~16-20.2s streaming times for large boards) floored by
    ``settings.ats_request_timeout_seconds`` and ``1.0s``. When used in interactive search
    direct routing (``bound_to_search_timeout=True``), caps the per-request timeout at
    ``settings.search_hard_timeout_seconds`` so routing remains bounded by search controls.
    """
    if override is not None:
        eff = max(float(override), 1.0)
    else:
        eff = max(
            float(settings.pinpoint_board_request_timeout_seconds),
            float(settings.ats_request_timeout_seconds),
            1.0,
        )
    if bound_to_search_timeout:
        hard_cap = max(1.0, float(settings.search_hard_timeout_seconds))
        eff = min(eff, hard_cap)
    return eff


class PinpointBoardAdapter:
    """
    Pinpoint company-board adapter.

    Public endpoint: ``GET https://{slug}.pinpointhq.com/postings.json``.
    Supports weak/strong ETag ``If-None-Match`` ``HTTP 304`` conditional short-circuit
    and deterministic SHA-256 content fingerprinting over full posting payloads.
    Fails closed on redirects (tenant renames), HTTP errors, oversize payloads, or
    malformed entries with ``snapshot_complete=False``.
    """

    async def check_board(
        self,
        board: CompanyBoard,
        client: httpx.AsyncClient,
        timeout: float | None = None,
        clock: Clock | None = None,
        resolver: DnsResolver | None = None,
        max_response_bytes: int | None = None,
        **kwargs,
    ) -> BoardCheckResult:
        from src.storage.company_board_registry import is_valid_board_slug

        policy = get_reconciliation_policy("pinpointhq")
        if not validate_board_token_safety(board.board_token) or not is_valid_board_slug(
            "pinpointhq", board.board_token
        ):
            return failure_result(
                kind=FailureKind.UNSAFE_URL,
                error="Invalid Pinpoint board token",
                policy=policy,
            )

        clean_slug = board.board_token.strip().lower()
        encoded_slug = quote(clean_slug, safe="-_.~")
        url = f"https://{encoded_slug}.pinpointhq.com/postings.json"
        headers = build_conditional_headers(
            url,
            _PINPOINT_ACCEPT,
            etag=board.etag,
            last_modified=board.last_modified,
            accept_gzip=True,
        )

        eff_timeout = resolve_pinpoint_board_timeout(timeout, bound_to_search_timeout=False)
        max_bytes = (
            int(max_response_bytes)
            if max_response_bytes is not None
            else int(kwargs.get("max_response_bytes") or settings.pinpoint_board_max_response_bytes)
        )

        with use_clock(clock):
            try:
                status, body_bytes, resp_headers = await fetch_provider_bytes(
                    client,
                    url,
                    headers=headers,
                    timeout=eff_timeout,
                    max_bytes=max_bytes,
                    follow_redirects=False,
                    resolver=resolver,
                )
                if status == 304 and (board.etag or board.last_modified):
                    return BoardCheckResult(
                        success=True,
                        not_modified=True,
                        etag=resp_headers.get("etag") or board.etag,
                        last_modified=resp_headers.get("last-modified") or board.last_modified,
                        content_fingerprint=board.content_fingerprint,
                        reconciliation_policy=policy,
                        snapshot_complete=True,
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

                items, parse_err = parse_pinpoint_postings_json(body_bytes, expected_slug=clean_slug)
                if parse_err:
                    lowered = parse_err.lower()
                    if "duplicate" in lowered:
                        err_kind = FailureKind.INCOMPLETE_SNAPSHOT
                    elif "mismatch" in lowered or "host" in lowered or "invalid url" in lowered:
                        err_kind = FailureKind.UNSAFE_URL
                    else:
                        err_kind = FailureKind.PARSE_ERROR
                    return failure_result(kind=err_kind, error=parse_err, policy=policy)

                new_etag = resp_headers.get("etag")
                new_lm = resp_headers.get("last-modified")
                fingerprint = compute_board_fingerprint(
                    [(it["job_id"], None, canonical_content_hash(it)) for it in items]
                )
                if board.content_fingerprint and fingerprint == board.content_fingerprint:
                    return BoardCheckResult(
                        success=True,
                        not_modified=True,
                        etag=new_etag or board.etag,
                        last_modified=new_lm or board.last_modified,
                        content_fingerprint=fingerprint,
                        reconciliation_policy=policy,
                        snapshot_complete=True,
                    )

                listings = [
                    _pinpoint_item_to_listing(
                        it,
                        board_token=clean_slug,
                        board_company_name=board.company_name,
                        board_logo_url=board.company_logo_url,
                        board_logo_source=board.company_logo_source,
                        board_logo_verified=bool(board.company_logo_verified),
                        board_logo_checked_at=board.company_logo_checked_at,
                        is_board_monitor=True,
                    )
                    for it in items
                ]
                return BoardCheckResult(
                    success=True,
                    not_modified=False,
                    listings=listings,
                    etag=new_etag,
                    last_modified=new_lm,
                    content_fingerprint=fingerprint,
                    reconciliation_policy=policy,
                    snapshot_complete=True,
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                return failure_result(
                    kind=classify_exception(exc),
                    error=str(exc),
                    policy=policy,
                )


BOARD_ADAPTERS: dict[str, object] = {
    "greenhouse": GreenhouseBoardAdapter(),
    "lever": LeverBoardAdapter(),
    "ashby": AshbyBoardAdapter(),
    "workable": WorkableBoardAdapter(),
    "recruitee": RecruiteeBoardAdapter(),
    "smartrecruiters": SmartRecruitersBoardAdapter(),
    "teamtailor": TeamtailorBoardAdapter(),
    "personio": PersonioBoardAdapter(),
    "pinpointhq": PinpointBoardAdapter(),
}
