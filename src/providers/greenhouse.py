"""
Greenhouse company-board monitoring adapter.
"""

from __future__ import annotations

import asyncio
import json
from typing import Optional
from urllib.parse import quote

import httpx

from src.ats.ats_api_client import greenhouse_payload_to_raw
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
