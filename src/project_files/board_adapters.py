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

from dataclasses import dataclass, field
from datetime import datetime, timezone
import asyncio
import hashlib
import json
import re
import time
from typing import Optional

import httpx
from loguru import logger
from pydantic import BaseModel, Field

from src.config import settings
from src.project_files.ats_api_client import (
    _WORKABLE_TYPE_MAP,
    _format_workable_location_item,
    greenhouse_payload_to_raw,
)
from src.project_files.canonical_job_adapter import CanonicalJobAdapter
from src.project_files.company_board_registry import CompanyBoard, MonitoredJobDetailState
from src.project_files.field_normalizer import humanize_slug, normalize_job_type, parse_datetime
from src.project_files.http_headers import browser_headers
from src.project_files.http_resilience import (
    CircuitBreakerOpenError,
    HostRateLimitedError,
    ResponseTooLargeError,
    throttled_get,
    throttled_stream_bytes,
)
from src.project_files.job_extraction_service import JobExtractionService, RawJobPosting
from src.project_files.models import JobListing


@dataclass
class BoardCheckResult:
    success: bool
    not_modified: bool = False
    listings: list[JobListing] = field(default_factory=list)
    etag: str | None = None
    last_modified: str | None = None
    content_fingerprint: str | None = None
    error: str | None = None
    refreshed_job_ids: set[str] | None = None
    detail_states: dict[str, MonitoredJobDetailState] | None = None
    missing_confirmation_threshold: int = 1
    snapshot_complete: bool = True

    def __post_init__(self) -> None:
        if not self.success:
            self.snapshot_complete = False


def compute_board_fingerprint(
    items: list[tuple[str, str | None] | tuple[str, str | None, str | None]],
) -> str:
    """Compute deterministic SHA256 digest of sorted job identifier, timestamp, and content hash tuples."""
    sorted_items = sorted(items, key=lambda x: str(x[0]))
    payload_parts = []
    for it in sorted_items:
        jid = str(it[0])
        ts = str(it[1] or "")
        ch = str(it[2] or "") if len(it) > 2 else ""
        payload_parts.append(f"{jid}:{ts}:{ch}")
    payload = "|".join(payload_parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class GreenhouseBoardAdapter:
    """Adapter for Greenhouse public board API: GET /v1/boards/{slug}/jobs"""

    async def get_job_detail(
        self,
        board_token: str,
        job_id: str | int,
        client: httpx.AsyncClient,
        timeout: float = 5.0,
    ) -> Optional[dict]:
        """Fetch individual job detail from Greenhouse public API:
        GET https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs/{job_id}
        Exposes authoritative 'first_published' date and individual job fields.
        """
        url = f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs/{job_id}?pay_transparency=true"
        headers = browser_headers(url, "application/json,text/plain;q=0.9,*/*;q=0.8")
        try:
            resp = await client.get(url, headers=headers, timeout=timeout)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, dict):
                    return data
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
        **kwargs,
    ) -> BoardCheckResult:
        url = f"https://boards-api.greenhouse.io/v1/boards/{board.board_token}/jobs?content=true&pay_transparency=true"
        headers = browser_headers(url, "application/json,text/plain;q=0.9,*/*;q=0.8")
        if board.etag:
            headers["If-None-Match"] = board.etag
        if board.last_modified:
            headers["If-Modified-Since"] = board.last_modified

        try:
            resp = await client.get(url, headers=headers, timeout=timeout)
            if resp.status_code == 304:
                return BoardCheckResult(
                    success=True,
                    not_modified=True,
                    etag=board.etag,
                    last_modified=board.last_modified,
                    content_fingerprint=board.content_fingerprint,
                )
            if resp.status_code == 404:
                return BoardCheckResult(success=False, error="Board not found (HTTP 404)")
            if resp.status_code != 200:
                return BoardCheckResult(
                    success=False,
                    error=f"HTTP {resp.status_code}",
                )

            data = resp.json()
            raw_jobs = data.get("jobs") or []
            new_etag = resp.headers.get("etag")
            new_last_mod = resp.headers.get("last-modified")

            fingerprint_items: list[tuple[str, str | None, str | None]] = []
            for j in raw_jobs:
                if not isinstance(j, dict) or not j.get("id"):
                    continue
                jid = str(j.get("id"))
                ts = str(j.get("updated_at") or "")
                title_val = str(j.get("title") or "")
                loc_val = str(j.get("location") or "")
                content_sample = str(j.get("content") or "")[:64]
                pay_repr = json.dumps(j.get("pay_input_ranges") or [], sort_keys=True)
                ch = hashlib.sha256(
                    f"{title_val}:{loc_val}:{content_sample}:{pay_repr}".encode("utf-8")
                ).hexdigest()[:16]
                fingerprint_items.append((jid, ts, ch))

            fingerprint = f"v37:{compute_board_fingerprint(fingerprint_items)}"

            if board.content_fingerprint and fingerprint == board.content_fingerprint:
                return BoardCheckResult(
                    success=True,
                    not_modified=True,
                    etag=new_etag or board.etag,
                    last_modified=new_last_mod or board.last_modified,
                    content_fingerprint=fingerprint,
                )

            company_name = board.company_name or humanize_slug(board.board_token)
            listings: list[JobListing] = []

            # 1. Bounded concurrent lookup of authoritative publication dates:
            # Only query individual job endpoints for newly discovered jobs lacking both
            # item.first_published and an existing known publication date in the database.
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
                        detail = await self.get_job_detail(board.board_token, jid, client, timeout=min(timeout, 4.0))
                        return jid, detail

                tasks = [_fetch_single_detail(str(item["id"])) for item in jobs_needing_detail]
                detail_results = await asyncio.gather(*tasks, return_exceptions=True)
                for res in detail_results:
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

                # Publication date vs update date:
                # Use authoritative first_published when available; preserve known dates;
                # use bounded fetched details when available. Never fall back to updated_at as posted_at.
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
            )
        except Exception as exc:
            return BoardCheckResult(success=False, error=str(exc))


class LeverBoardAdapter:
    """Adapter for Lever public board API: GET /v0/postings/{slug}?mode=json"""

    async def check_board(
        self,
        board: CompanyBoard,
        client: httpx.AsyncClient,
        timeout: float = 8.0,
        **kwargs,
    ) -> BoardCheckResult:
        url = f"https://api.lever.co/v0/postings/{board.board_token}?mode=json"
        headers = browser_headers(url, "application/json,text/plain;q=0.9,*/*;q=0.8")
        if board.etag:
            headers["If-None-Match"] = board.etag
        if board.last_modified:
            headers["If-Modified-Since"] = board.last_modified

        try:
            resp = await client.get(url, headers=headers, timeout=timeout)
            if resp.status_code == 304:
                return BoardCheckResult(
                    success=True,
                    not_modified=True,
                    etag=board.etag,
                    last_modified=board.last_modified,
                    content_fingerprint=board.content_fingerprint,
                )
            if resp.status_code == 404:
                return BoardCheckResult(success=False, error="Board not found (HTTP 404)")
            if resp.status_code != 200:
                return BoardCheckResult(
                    success=False,
                    error=f"HTTP {resp.status_code}",
                )

            data = resp.json()
            if not isinstance(data, list):
                return BoardCheckResult(success=False, error="Invalid Lever payload shape")

            new_etag = resp.headers.get("etag")
            new_last_mod = resp.headers.get("last-modified")

            fingerprint_items: list[tuple[str, str | None, str | None]] = []
            for it in data:
                if not isinstance(it, dict) or not it.get("id"):
                    continue
                jid = str(it.get("id"))
                ts = str(it.get("createdAt") or "")
                title_val = str(it.get("text") or "")
                desc_val = str(it.get("descriptionPlain") or it.get("description") or "")
                lists_val = it.get("lists") or []
                add_val = str(it.get("additionalPlain") or it.get("additional") or "")
                sal_val = it.get("salaryRange") or ""
                ch = hashlib.sha256(
                    f"v36:{title_val}:{desc_val[:200]}:{len(lists_val)}:{len(add_val)}:{sal_val}".encode("utf-8")
                ).hexdigest()[:16]
                fingerprint_items.append((jid, ts, ch))

            fingerprint = compute_board_fingerprint(fingerprint_items)

            if board.content_fingerprint and fingerprint == board.content_fingerprint:
                return BoardCheckResult(
                    success=True,
                    not_modified=True,
                    etag=new_etag or board.etag,
                    last_modified=new_last_mod or board.last_modified,
                    content_fingerprint=fingerprint,
                )

            company_name = board.company_name or humanize_slug(board.board_token)
            from src.project_files.ats_api_client import enrich_lever_board_identity, lever_payload_to_raw
            from src.project_files.logo_extractor import LogoResult

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
            )
        except Exception as exc:
            return BoardCheckResult(success=False, error=str(exc))


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
    serialized = json.dumps(
        canonical_payload,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


class AshbyBoardAdapter:
    """Adapter for Ashby public board API: GET /posting-api/job-board/{slug}?includeCompensation=true"""

    async def check_board(
        self,
        board: CompanyBoard,
        client: httpx.AsyncClient,
        timeout: float = 8.0,
        **kwargs,
    ) -> BoardCheckResult:
        from urllib.parse import quote
        from src.project_files.ats_api_client import ashby_payload_to_raw, enrich_ashby_board_identity
        from src.project_files.logo_extractor import LogoResult

        encoded_slug = quote(board.board_token, safe="-_.~")
        url = f"https://api.ashbyhq.com/posting-api/job-board/{encoded_slug}?includeCompensation=true"
        headers = browser_headers(url, "application/json")
        headers["Accept-Encoding"] = "gzip, deflate"
        if board.etag:
            headers["If-None-Match"] = board.etag
        if board.last_modified:
            headers["If-Modified-Since"] = board.last_modified

        try:
            resp = await client.get(url, headers=headers, timeout=timeout)
            if resp.status_code == 304:
                return BoardCheckResult(
                    success=True,
                    not_modified=True,
                    etag=board.etag,
                    last_modified=board.last_modified,
                    content_fingerprint=board.content_fingerprint,
                )
            if resp.status_code == 404:
                return BoardCheckResult(success=False, error="Board not found (HTTP 404)")
            if resp.status_code != 200:
                return BoardCheckResult(
                    success=False,
                    error=f"HTTP {resp.status_code}",
                )

            data = resp.json()
            if not isinstance(data, dict):
                return BoardCheckResult(success=False, error="Invalid Ashby payload shape")
            raw_jobs = data.get("jobs") or []
            if not isinstance(raw_jobs, list):
                return BoardCheckResult(success=False, error="Invalid Ashby jobs payload shape")
            new_etag = resp.headers.get("etag")
            new_last_mod = resp.headers.get("last-modified")

            fingerprint_items: list[tuple[str, str | None, str | None]] = []
            for j in raw_jobs:
                if not isinstance(j, dict) or not j.get("id"):
                    continue
                jid = str(j.get("id"))
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
            )
        except Exception as exc:
            return BoardCheckResult(success=False, error=str(exc))


def _workable_widget_job_hash(item: dict) -> str:
    """Stable hash of Workable widget listing metadata for board diff detection."""
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
    return hashlib.sha1(
        json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    ).hexdigest()[:12]


_TRANSIENT_RETRY_BACKOFF_SECONDS: tuple[float, ...] = (
    300.0,
    900.0,
    1800.0,
    3600.0,
    7200.0,
    21600.0,
)
_DETAIL_404_RETRY_BACKOFF_SECONDS: tuple[float, ...] = (
    3600.0,
    7200.0,
    14400.0,
    21600.0,
)


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


def _workable_detail_retry_delay(
    detail_status: str,
    retry_count: int,
    *,
    ttl_seconds: float = 21600.0,
) -> float:
    if detail_status == "widget_fallback":
        return 0.0
    schedule = (
        _DETAIL_404_RETRY_BACKOFF_SECONDS
        if detail_status == "detail_404"
        else _TRANSIENT_RETRY_BACKOFF_SECONDS
    )
    idx = max(0, min(int(retry_count) - 1, len(schedule) - 1))
    delay = schedule[idx]
    if ttl_seconds > 0:
        return min(delay, float(ttl_seconds))
    return delay


def _classify_workable_candidate(
    now: float,
    cached_entry: tuple[JobListing, float] | None,
    detail_state: MonitoredJobDetailState | None,
    detail_revalidate_ttl_seconds: float,
) -> tuple[bool, int, float]:
    """Return (is_due, priority_tier, sort_ts) for stale/retry candidate selection."""
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
) -> tuple[list[JobListing], set[str]]:
    """
    Shared Workable widget + bounded api/v2 detail hydration path used by both
    WorkableBoardAdapter and probe_workable_board.
    """
    from urllib.parse import quote
    from src.project_files.ats_api_client import (
        enrich_workable_board_identity,
        workable_payload_to_raw,
        workable_widget_job_to_raw,
    )
    from src.project_files.logo_extractor import LogoResult

    known = known_monitored_jobs or {}
    known_states = known_detail_states or {}
    now = time.time()

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
                is_due, tier, sort_ts = _classify_workable_candidate(
                    now,
                    cached_entry,
                    prev_state,
                    detail_revalidate_ttl_seconds,
                )
                if is_due:
                    stale_candidates.append((tier, sort_ts, shortcode))

    stale_candidates.sort(key=lambda entry: (entry[0], entry[1]))
    rotated_shortcodes = [
        sc for _, _, sc in stale_candidates[: max(0, int(max_revalidations_per_poll))]
    ]

    fetch_shortcodes = immediate_shortcodes + rotated_shortcodes
    if max_detail_fetches is not None and len(fetch_shortcodes) > max_detail_fetches:
        fetch_shortcodes = fetch_shortcodes[: max(0, max_detail_fetches)]
    fetch_set = set(fetch_shortcodes)

    encoded_slug = quote(slug, safe="-_.~")
    sem = asyncio.Semaphore(5)

    async def _fetch_detail(shortcode: str) -> tuple[str, int | None, dict | None, str | None]:
        detail_url = (
            f"https://apply.workable.com/api/v2/accounts/{encoded_slug}/jobs/{quote(shortcode, safe='-_.~')}"
        )
        async with sem:
            try:
                d_resp = await throttled_get(
                    client,
                    detail_url,
                    headers=browser_headers(detail_url, "application/json"),
                    timeout=timeout,
                )
            except CircuitBreakerOpenError:
                return shortcode, None, None, "circuit_breaker_open"
            except HostRateLimitedError:
                return shortcode, None, None, "host_rate_limited"
            except Exception:
                return shortcode, None, None, "network_or_timeout"
            if d_resp.status_code != 200:
                return shortcode, d_resp.status_code, None, None
            try:
                payload = d_resp.json()
            except Exception:
                return shortcode, 200, None, None
            if not isinstance(payload, dict):
                return shortcode, 200, None, None
            return shortcode, 200, payload, None

    detail_results: dict[str, tuple[int | None, dict | None, str | None]] = {}
    if fetch_shortcodes:
        fetched = await asyncio.gather(*(_fetch_detail(sc) for sc in fetch_shortcodes))
        for sc, status_code, payload, err_reason in fetched:
            detail_results[sc] = (status_code, payload, err_reason)

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
        prev_hydrated_at = prev_state.detail_last_hydrated_at if prev_state is not None else None
        if (
            prev_hydrated_at is None
            and prev_state is not None
            and prev_state.detail_status == "hydrated"
            and cached_entry is not None
            and cached_entry[1] > 0
        ):
            prev_hydrated_at = float(cached_entry[1])

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
                        detail_states_out[listing.id] = MonitoredJobDetailState(
                            detail_status="hydrated",
                            detail_last_hydrated_at=now,
                            detail_retry_count=0,
                            detail_next_retry_at=None,
                            detail_last_error=None,
                            widget_location_signature=loc_sig,
                        )
                    continue

                # HTTP 200 returned an incomplete or invalid detail payload
                retry_count = (prev_state.detail_retry_count + 1) if prev_state is not None else 1
                delay = _workable_detail_retry_delay(
                    "invalid_detail",
                    retry_count,
                    ttl_seconds=detail_revalidate_ttl_seconds,
                )
                _emit_preserved_or_fallback(
                    item,
                    job_id,
                    cached_entry,
                    MonitoredJobDetailState(
                        detail_status="invalid_detail",
                        detail_last_hydrated_at=prev_hydrated_at,
                        detail_retry_count=retry_count,
                        detail_next_retry_at=now + delay,
                        detail_last_error="invalid_or_incomplete_detail",
                        widget_location_signature=loc_sig,
                    ),
                )
                continue

            if status_code == 404:
                # Widget still lists this job; never omit or auto-close on detail 404 alone.
                retry_count = (prev_state.detail_retry_count + 1) if prev_state is not None else 1
                delay = _workable_detail_retry_delay(
                    "detail_404",
                    retry_count,
                    ttl_seconds=detail_revalidate_ttl_seconds,
                )
                _emit_preserved_or_fallback(
                    item,
                    job_id,
                    cached_entry,
                    MonitoredJobDetailState(
                        detail_status="detail_404",
                        detail_last_hydrated_at=prev_hydrated_at,
                        detail_retry_count=retry_count,
                        detail_next_retry_at=now + delay,
                        detail_last_error="http_404",
                        widget_location_signature=loc_sig,
                    ),
                )
                continue

            # Transient detail error (5xx / 429 / network / timeout / malformed 200 JSON)
            retry_count = (prev_state.detail_retry_count + 1) if prev_state is not None else 1
            if status_code == 200:
                err_status = "invalid_detail"
                err_msg = "invalid_detail_json"
            else:
                err_status = "transient_error"
                err_msg = err_reason or (
                    f"http_{status_code}" if status_code is not None else "network_or_timeout"
                )
            delay = _workable_detail_retry_delay(
                err_status,
                retry_count,
                ttl_seconds=detail_revalidate_ttl_seconds,
            )
            _emit_preserved_or_fallback(
                item,
                job_id,
                cached_entry,
                MonitoredJobDetailState(
                    detail_status=err_status,
                    detail_last_hydrated_at=prev_hydrated_at,
                    detail_retry_count=retry_count,
                    detail_next_retry_at=now + delay,
                    detail_last_error=err_msg,
                    widget_location_signature=loc_sig,
                ),
            )
            continue

        if cached_entry is not None:
            # Known unchanged job outside this poll's rotation slice or within retry backoff
            listings.append(cached_entry[0])
            if detail_states_out is not None:
                if prev_state is not None:
                    detail_states_out[job_id] = MonitoredJobDetailState(
                        detail_status=prev_state.detail_status,
                        detail_last_hydrated_at=prev_hydrated_at,
                        detail_retry_count=prev_state.detail_retry_count,
                        detail_next_retry_at=prev_state.detail_next_retry_at,
                        detail_last_error=prev_state.detail_last_error,
                        widget_location_signature=loc_sig or prev_state.widget_location_signature,
                    )
                else:
                    detail_states_out[job_id] = MonitoredJobDetailState(
                        detail_status="hydrated",
                        detail_last_hydrated_at=(
                            float(cached_entry[1]) if cached_entry[1] > 0 else now
                        ),
                        detail_retry_count=0,
                        detail_next_retry_at=None,
                        detail_last_error=None,
                        widget_location_signature=loc_sig,
                    )
            continue

        # Bounded widget fallback (e.g. direct router cap overflow) — never mark detail-refreshed
        _emit_preserved_or_fallback(
            item,
            job_id,
            None,
            MonitoredJobDetailState(
                detail_status="widget_fallback",
                detail_last_hydrated_at=None,
                detail_retry_count=0,
                detail_next_retry_at=now,
                detail_last_error="deferred_widget_fallback",
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
        **kwargs,
    ) -> BoardCheckResult:
        from urllib.parse import quote

        encoded_slug = quote(board.board_token, safe="-_.~")
        url = f"https://apply.workable.com/api/v1/widget/accounts/{encoded_slug}"
        headers = browser_headers(url, "application/json")
        if board.etag:
            headers["If-None-Match"] = board.etag
        if board.last_modified:
            headers["If-Modified-Since"] = board.last_modified

        try:
            try:
                resp = await throttled_get(client, url, headers=headers, timeout=timeout)
            except (CircuitBreakerOpenError, HostRateLimitedError) as exc:
                return BoardCheckResult(success=False, error=str(exc))
            if resp.status_code == 304:
                return BoardCheckResult(
                    success=True,
                    not_modified=True,
                    etag=board.etag,
                    last_modified=board.last_modified,
                    content_fingerprint=board.content_fingerprint,
                )
            if resp.status_code == 404:
                return BoardCheckResult(success=False, error="Board not found (HTTP 404)")
            if resp.status_code != 200:
                return BoardCheckResult(success=False, error=f"HTTP {resp.status_code}")

            data = resp.json()
            if not isinstance(data, dict):
                return BoardCheckResult(success=False, error="Invalid Workable widget payload shape")
            raw_jobs = data.get("jobs") or []
            if not isinstance(raw_jobs, list):
                return BoardCheckResult(success=False, error="Invalid Workable widget jobs shape")

            new_etag = resp.headers.get("etag")
            new_last_mod = resp.headers.get("last-modified")

            fingerprint_items: list[tuple[str, str | None, str | None]] = []
            for j in raw_jobs:
                if not isinstance(j, dict) or not j.get("shortcode"):
                    continue
                sc = str(j.get("shortcode")).strip()
                ts = str(j.get("published_on") or "")
                ch = _workable_widget_job_hash(j)
                fingerprint_items.append((sc, ts, ch))

            fingerprint = compute_board_fingerprint(fingerprint_items)
            known_monitored: dict[str, tuple[JobListing, float]] = kwargs.get("known_monitored_jobs") or {}
            known_detail_states: dict[str, MonitoredJobDetailState] = (
                kwargs.get("known_detail_states") or {}
            )
            now = time.time()
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
                is_due, _, _ = _classify_workable_candidate(
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
            )
        except Exception as exc:
            return BoardCheckResult(success=False, error=str(exc))


def _recruitee_job_content_hash(offer: dict) -> str:
    """
    Deterministic full-payload SHA-256 hex digest across all Recruitee offer fields.

    Serializing the complete sorted offer dictionary ensures changes to any primary or
    fallback field (e.g., ``description_html``, ``intro``, ``employment_type``,
    ``workplace_type``, ``position``, ``company``) invalidate the board fingerprint.
    """
    encoded = json.dumps(
        offer,
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


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
    monitoring and direct discovery reject incomplete snapshots or unrecognized statuses
    without returning partial listings or triggering false board registrations/closures.
    """
    if not isinstance(raw_offers, list):
        return None, "Invalid Recruitee offers payload shape"

    active_offers: list[dict] = []
    for entry in raw_offers:
        is_active, validation_error = _validate_recruitee_offer_record(entry)
        if validation_error:
            return None, validation_error
        if is_active:
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
    from src.project_files.ats_api_client import (
        enrich_recruitee_board_identity,
        recruitee_payload_to_raw,
    )
    from src.project_files.logo_extractor import LogoResult

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
        **kwargs,
    ) -> BoardCheckResult:
        from urllib.parse import quote
        from src.project_files.company_board_registry import is_valid_board_slug

        if not is_valid_board_slug("recruitee", board.board_token):
            return BoardCheckResult(success=False, error="Invalid Recruitee board token")

        encoded_slug = quote(board.board_token.strip().lower(), safe="-_.~")
        url = f"https://{encoded_slug}.recruitee.com/api/offers/"
        headers = browser_headers(url, "application/json")
        headers["Accept-Encoding"] = "gzip, deflate"

        max_bytes = int(
            kwargs.get("max_response_bytes") or settings.recruitee_board_max_response_bytes
        )
        try:
            status, body_bytes, _ = await throttled_stream_bytes(
                client,
                url,
                headers=headers,
                timeout=timeout,
                max_bytes=max_bytes,
                follow_redirects=False,
            )
            if status == 404:
                return BoardCheckResult(success=False, error="Board not found (HTTP 404)")
            if status != 200:
                return BoardCheckResult(success=False, error=f"HTTP {status}")

            try:
                data = json.loads(body_bytes.decode("utf-8"))
            except Exception:
                return BoardCheckResult(success=False, error="Invalid Recruitee JSON payload")

            if not isinstance(data, dict) or "offers" not in data or not isinstance(data.get("offers"), list):
                return BoardCheckResult(success=False, error="Invalid Recruitee offers payload shape")

            active_offers, validation_error = validate_recruitee_offers_snapshot(data["offers"])
            if validation_error or active_offers is None:
                return BoardCheckResult(
                    success=False,
                    error=validation_error or "Invalid Recruitee offers payload shape",
                )

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
                    content_fingerprint=fingerprint,
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
                return BoardCheckResult(
                    success=False,
                    error=(
                        f"Recruitee offer hydration mismatch: converted {len(listings)} "
                        f"of {len(active_offers)} active offers"
                    ),
                )

            return BoardCheckResult(
                success=True,
                not_modified=False,
                listings=listings,
                content_fingerprint=fingerprint,
            )
        except (ResponseTooLargeError, CircuitBreakerOpenError, HostRateLimitedError, Exception) as exc:
            return BoardCheckResult(success=False, error=str(exc))


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
    encoded = json.dumps(
        normalized,
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


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
    Validate one sequential page of SmartRecruiters ``/postings`` JSON atomically.

    Returns ``(content_items, page_limit, total_found, error)``.
    """
    if not isinstance(data, dict):
        return None, None, None, "Invalid SmartRecruiters listing payload (expected JSON object)"

    resp_offset = data.get("offset")
    if isinstance(resp_offset, bool) or not isinstance(resp_offset, int) or resp_offset != requested_offset:
        return None, None, None, (
            f"SmartRecruiters offset mismatch: requested {requested_offset}, got {resp_offset!r}"
        )

    resp_limit = data.get("limit")
    if isinstance(resp_limit, bool) or not isinstance(resp_limit, int) or resp_limit < 1 or resp_limit > 100:
        return None, None, None, f"Invalid SmartRecruiters page limit: {resp_limit!r}"

    total_found = data.get("totalFound")
    if isinstance(total_found, bool) or not isinstance(total_found, int) or total_found < 0:
        return None, None, None, f"Invalid SmartRecruiters totalFound: {total_found!r}"

    if expected_total is not None and total_found != expected_total:
        return None, None, None, (
            f"SmartRecruiters totalFound drifted mid-pagination: {expected_total} -> {total_found}"
        )

    content = data.get("content")
    if not isinstance(content, list):
        return None, None, None, "Invalid SmartRecruiters content shape (expected list)"

    if len(content) > resp_limit:
        return None, None, None, (
            f"SmartRecruiters page exceeded limit {resp_limit}: got {len(content)}"
        )

    if total_found == 0:
        if requested_offset != 0 or len(content) != 0:
            return None, None, None, "Inconsistent SmartRecruiters empty snapshot"
        return [], resp_limit, 0, None

    if len(content) == 0:
        return None, None, None, (
            f"Premature empty SmartRecruiters page at offset {requested_offset} (totalFound={total_found})"
        )

    if collected_count + len(content) > total_found:
        return None, None, None, (
            f"SmartRecruiters item count exceeded totalFound ({collected_count + len(content)} > {total_found})"
        )

    if collected_count + len(content) < total_found and len(content) < resp_limit:
        return None, None, None, (
            f"Incomplete SmartRecruiters page at offset {requested_offset}: "
            f"got {len(content)} < limit {resp_limit} before totalFound {total_found}"
        )

    page_seen: set[str] = set()
    validated_items: list[dict] = []
    for entry in content:
        item_id, entry_err = _validate_smartrecruiters_listing_entry(
            entry,
            seen_ids=seen_ids | page_seen,
            expected_company_slug=expected_company_slug,
        )
        if entry_err or item_id is None:
            return None, None, None, entry_err or "Malformed SmartRecruiters listing entry"
        page_seen.add(item_id)
        validated_items.append(entry)  # type: ignore[arg-type]

    seen_ids.update(page_seen)
    return validated_items, resp_limit, total_found, None


async def fetch_smartrecruiters_postings_snapshot(
    slug: str,
    client: httpx.AsyncClient,
    *,
    timeout: float = 10.0,
) -> tuple[list[dict] | None, str | None]:
    """
    Sequentially drain all public SmartRecruiters listing pages for ``slug`` with
    atomic snapshot validation and zero arbitrary page/job caps.

    Never sends ``If-None-Match`` so multi-page boards cannot falsely short-circuit on
    a page-0 ETag. Any HTTP error, malformed page, offset drift, duplicate ID, or
    mid-pagination failure aborts and returns ``(None, error)``.
    """
    from urllib.parse import quote
    from src.project_files.company_board_registry import is_valid_board_slug

    clean_slug = (slug or "").strip().lower()
    if not is_valid_board_slug("smartrecruiters", clean_slug):
        return None, "Invalid SmartRecruiters board token"

    encoded_slug = quote(clean_slug, safe="-_.~")
    offset = 0
    expected_total: int | None = None
    seen_ids: set[str] = set()
    collected: list[dict] = []

    while True:
        url = (
            f"https://api.smartrecruiters.com/v1/companies/{encoded_slug}/postings"
            f"?limit={_SMARTREC_PAGE_SIZE}&offset={offset}&destination=PUBLIC"
        )
        headers = browser_headers(url, "application/json")
        try:
            resp = await throttled_get(client, url, headers=headers, timeout=timeout)
        except (CircuitBreakerOpenError, HostRateLimitedError) as exc:
            return None, str(exc)
        except Exception as exc:
            return None, f"SmartRecruiters pagination error at offset {offset}: {exc}"

        if resp.status_code != 200:
            return None, f"HTTP {resp.status_code} at offset {offset}"

        try:
            data = resp.json()
        except Exception:
            return None, f"Invalid JSON payload at offset {offset}"

        page_items, _, total_found, err = validate_smartrecruiters_page(
            data,
            requested_offset=offset,
            expected_total=expected_total,
            seen_ids=seen_ids,
            collected_count=len(collected),
            expected_company_slug=clean_slug,
        )
        if err or page_items is None or total_found is None:
            return None, err or "Invalid SmartRecruiters listing page"

        if expected_total is None:
            expected_total = total_found

        if total_found == 0:
            return [], None

        collected.extend(page_items)
        if len(collected) >= expected_total:
            break

        next_offset = offset + len(page_items)
        if next_offset <= offset:
            return None, "Zero-progress SmartRecruiters pagination"
        offset = next_offset

    if expected_total is None or len(collected) != expected_total or len(seen_ids) != expected_total:
        return None, "Incomplete SmartRecruiters snapshot total mismatch"

    return collected, None


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
    from urllib.parse import quote
    from src.project_files.ats_api_client import (
        enrich_smartrecruiters_board_identity,
        smartrecruiters_payload_to_raw,
        validate_smartrecruiters_ref_url,
    )
    from src.project_files.logo_extractor import LogoResult

    clean_slug = (slug or "").strip().lower()
    known = known_monitored_jobs or {}
    known_states = known_detail_states or {}
    now = time.time()

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

        prev_hydrated_at = prev_state.detail_last_hydrated_at if prev_state is not None else None
        if (
            prev_hydrated_at is None
            and prev_state is not None
            and prev_state.detail_status == "hydrated"
            and cached_entry[1] > 0
        ):
            prev_hydrated_at = float(cached_entry[1])

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
            is_due, tier, sort_ts = _classify_workable_candidate(
                now,
                cached_entry,
                prev_state,
                detail_revalidate_ttl_seconds,
            )
            if is_due:
                stale_reval.append((tier, sort_ts, pid))

    pending_old.sort(key=lambda e: (e[0], e[1]))
    stale_reval.sort(key=lambda e: (e[0], e[1]))

    new_budget = max(0, int(max_new_hydrations_per_poll))
    reval_budget = max(0, int(max_revalidations_per_poll))

    new_and_changed_queue = (
        [pid for _, _, pid in pending_old]
        + [pid for _, pid in changed_known]
        + [pid for _, pid in brand_new]
    )
    selected_new = new_and_changed_queue[:new_budget]
    selected_reval = [pid for _, _, pid in stale_reval[:reval_budget]]

    fetch_ids = selected_new + selected_reval
    if max_detail_fetches is not None and len(fetch_ids) > max_detail_fetches:
        fetch_ids = fetch_ids[: max(0, int(max_detail_fetches))]
    fetch_set = set(fetch_ids)

    sem = asyncio.Semaphore(3)

    async def _fetch_detail(pid: str) -> tuple[str, int | None, dict | None, str | None]:
        item = item_by_id[pid]
        raw_ref = item.get("ref")
        if raw_ref is not None:
            detail_url = validate_smartrecruiters_ref_url(
                raw_ref if isinstance(raw_ref, str) else None,
                expected_company_slug=clean_slug,
                expected_job_id=pid,
            )
            if detail_url is None:
                return pid, 200, None, "invalid_ref_url"
        else:
            detail_url = (
                f"https://api.smartrecruiters.com/v1/companies/"
                f"{quote(clean_slug, safe='-_.~')}/postings/{quote(pid, safe='-_.~')}"
            )

        async with sem:
            try:
                d_resp = await throttled_get(
                    client,
                    detail_url,
                    headers=browser_headers(detail_url, "application/json"),
                    timeout=timeout,
                )
            except CircuitBreakerOpenError:
                return pid, None, None, "circuit_breaker_open"
            except HostRateLimitedError:
                return pid, None, None, "host_rate_limited"
            except Exception:
                return pid, None, None, "network_or_timeout"

            if d_resp.status_code != 200:
                return pid, d_resp.status_code, None, None
            try:
                payload = d_resp.json()
            except Exception:
                return pid, 200, None, "invalid_detail_json"
            if not isinstance(payload, dict):
                return pid, 200, None, "invalid_detail_json"
            return pid, 200, payload, None

    detail_results: dict[str, tuple[int | None, dict | None, str | None]] = {}
    if fetch_ids:
        fetched = await asyncio.gather(*(_fetch_detail(pid) for pid in fetch_ids))
        for pid, status_code, payload, err_reason in fetched:
            detail_results[pid] = (status_code, payload, err_reason)

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
        prev_hydrated_at = prev_state.detail_last_hydrated_at if prev_state is not None else None
        if (
            prev_hydrated_at is None
            and prev_state is not None
            and prev_state.detail_status == "hydrated"
            and cached_entry is not None
            and cached_entry[1] > 0
        ):
            prev_hydrated_at = float(cached_entry[1])

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
                        detail_states_out[listing.id] = MonitoredJobDetailState(
                            detail_status="hydrated",
                            detail_last_hydrated_at=now,
                            detail_retry_count=0,
                            detail_next_retry_at=None,
                            detail_last_error=None,
                            listing_item_hash=item_hash,
                        )
                    continue

                retry_count = (prev_state.detail_retry_count + 1) if prev_state is not None else 1
                delay = _workable_detail_retry_delay(
                    "invalid_detail",
                    retry_count,
                    ttl_seconds=detail_revalidate_ttl_seconds,
                )
                _emit_preserved_or_fallback(
                    item,
                    job_id,
                    cached_entry,
                    MonitoredJobDetailState(
                        detail_status="invalid_detail",
                        detail_last_hydrated_at=prev_hydrated_at,
                        detail_retry_count=retry_count,
                        detail_next_retry_at=now + delay,
                        detail_last_error=err_reason or "invalid_or_incomplete_detail",
                        listing_item_hash=item_hash,
                    ),
                    item_listing_changed=item_changed,
                )
                continue

            if status_code == 404:
                retry_count = (prev_state.detail_retry_count + 1) if prev_state is not None else 1
                delay = _workable_detail_retry_delay(
                    "detail_404",
                    retry_count,
                    ttl_seconds=detail_revalidate_ttl_seconds,
                )
                _emit_preserved_or_fallback(
                    item,
                    job_id,
                    cached_entry,
                    MonitoredJobDetailState(
                        detail_status="detail_404",
                        detail_last_hydrated_at=prev_hydrated_at,
                        detail_retry_count=retry_count,
                        detail_next_retry_at=now + delay,
                        detail_last_error="http_404",
                        listing_item_hash=item_hash,
                    ),
                    item_listing_changed=item_changed,
                )
                continue

            retry_count = (prev_state.detail_retry_count + 1) if prev_state is not None else 1
            if status_code == 200:
                err_status = "invalid_detail"
                err_msg = err_reason or "invalid_detail_json"
            else:
                err_status = "transient_error"
                err_msg = err_reason or (
                    f"http_{status_code}" if status_code is not None else "network_or_timeout"
                )
            delay = _workable_detail_retry_delay(
                err_status,
                retry_count,
                ttl_seconds=detail_revalidate_ttl_seconds,
            )
            _emit_preserved_or_fallback(
                item,
                job_id,
                cached_entry,
                MonitoredJobDetailState(
                    detail_status=err_status,
                    detail_last_hydrated_at=prev_hydrated_at,
                    detail_retry_count=retry_count,
                    detail_next_retry_at=now + delay,
                    detail_last_error=err_msg,
                    listing_item_hash=item_hash,
                ),
                item_listing_changed=item_changed,
            )
            continue

        if cached_entry is not None:
            if prev_state is not None:
                preserved_state = MonitoredJobDetailState(
                    detail_status=prev_state.detail_status,
                    detail_last_hydrated_at=prev_hydrated_at,
                    detail_retry_count=prev_state.detail_retry_count,
                    detail_next_retry_at=prev_state.detail_next_retry_at,
                    detail_last_error=prev_state.detail_last_error,
                    listing_item_hash=prev_state.listing_item_hash or item_hash,
                )
            else:
                preserved_state = MonitoredJobDetailState(
                    detail_status="hydrated",
                    detail_last_hydrated_at=(
                        float(cached_entry[1]) if cached_entry[1] > 0 else now
                    ),
                    detail_retry_count=0,
                    detail_next_retry_at=None,
                    detail_last_error=None,
                    listing_item_hash=item_hash,
                )
            _emit_preserved_or_fallback(
                item,
                job_id,
                cached_entry,
                preserved_state,
                item_listing_changed=item_changed,
            )
            continue

        # New posting deferred beyond this round's detail budget: persist pending state
        _emit_preserved_or_fallback(
            item,
            job_id,
            None,
            MonitoredJobDetailState(
                detail_status="pending_hydration",
                detail_last_hydrated_at=None,
                detail_retry_count=0,
                detail_next_retry_at=now,
                detail_last_error="deferred_pending_hydration",
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
        **kwargs,
    ) -> BoardCheckResult:
        try:
            raw_items, snapshot_err = await fetch_smartrecruiters_postings_snapshot(
                board.board_token,
                client,
                timeout=timeout,
            )
            if snapshot_err or raw_items is None:
                return BoardCheckResult(
                    success=False,
                    error=snapshot_err or "SmartRecruiters snapshot failed",
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
            now = time.time()

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
                        is_due, _, _ = _classify_workable_candidate(
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
                    missing_confirmation_threshold=2,
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
            )

            return BoardCheckResult(
                success=True,
                not_modified=False,
                listings=listings,
                content_fingerprint=fingerprint,
                refreshed_job_ids=refreshed_job_ids,
                detail_states=detail_states_out,
                missing_confirmation_threshold=2,
            )
        except Exception as exc:
            return BoardCheckResult(success=False, error=str(exc))


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


def _format_tt_rss_locations(item_el) -> tuple[str | None, str | None]:
    """Extract compact and preserved Teamtailor RSS <tt:locations> text."""
    locs_el = item_el.find(f"{_TEAMTAILOR_LOC_NS}locations")
    if locs_el is None:
        return None, None
    compact: list[str] = []
    raw_names: list[str] = []
    for loc_el in locs_el.findall(f"{_TEAMTAILOR_LOC_NS}location"):
        name = (loc_el.findtext(f"{_TEAMTAILOR_LOC_NS}name") or "").strip()
        city = (loc_el.findtext(f"{_TEAMTAILOR_LOC_NS}city") or "").strip()
        country = (loc_el.findtext(f"{_TEAMTAILOR_LOC_NS}country") or "").strip()
        if name:
            raw_names.append(name)
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
    encoded = json.dumps(item, sort_keys=True, ensure_ascii=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


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
    from src.project_files.url_safety import is_safe_public_https_url

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
    from bs4 import BeautifulSoup
    from urllib.parse import urljoin, urlparse
    from src.project_files.url_safety import is_safe_public_https_url

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
) -> tuple[list[dict], bool, str | None, str | None]:
    """
    Bounded HTML pagination fallback for Teamtailor boards hitting the 100-item RSS cap.

    Returns ``(html_items, fallback_complete, page1_html, error)``.
    Any non-200 HTTP response, missing frame, empty first page, repeated page,
    pagination loop, or page/item cap sets ``fallback_complete=False`` so callers
    never trigger missing-job auto-closure from an incomplete snapshot.
    """
    from urllib.parse import quote

    clean_slug = board_token.strip().lower()
    encoded_slug = quote(clean_slug, safe="-_.~")
    host = f"{encoded_slug}.teamtailor.com"
    byte_cap = int(max_bytes or settings.max_response_bytes)

    collected: list[dict] = []
    seen_ids: set[str] = set()
    prev_page_ids: set[str] | None = None
    visited_pages: set[int] = set()
    page = 1
    page1_html: str | None = None

    while len(visited_pages) < max(1, max_pages):
        if page in visited_pages:
            return collected, False, page1_html, f"Teamtailor HTML pagination loop detected at page={page}"
        visited_pages.add(page)

        url = f"https://{host}/jobs?page={page}"
        try:
            status, body_bytes, _ = await throttled_stream_bytes(
                client,
                url,
                headers=browser_headers(url, "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8"),
                timeout=timeout,
                max_bytes=byte_cap,
                follow_redirects=False,
            )
        except Exception as exc:
            return collected, False, page1_html, str(exc)

        if status != 200:
            return collected, False, page1_html, f"Teamtailor HTML fallback HTTP {status} on page={page}"

        html_text = body_bytes.decode("utf-8", errors="replace")
        if page == 1:
            page1_html = html_text

        page_items, next_page, parse_err = _parse_teamtailor_html_jobs_page(
            html_text,
            expected_host=host,
            current_page=page,
        )
        if parse_err:
            return collected, False, page1_html, parse_err

        if page == 1 and not page_items:
            return collected, False, page1_html, "Teamtailor HTML fallback returned 0 jobs on page 1"

        if not page_items:
            # Reached clean empty terminal page
            return collected, True, page1_html, None

        page_ids = {it["job_id"] for it in page_items}
        if prev_page_ids is not None and page_ids == prev_page_ids:
            return collected, False, page1_html, f"Teamtailor HTML repeated page detected at page={page}"
        if page_ids.issubset(seen_ids):
            return collected, False, page1_html, f"Teamtailor HTML duplicate-only page detected at page={page}"

        prev_page_ids = page_ids
        for it in page_items:
            if it["job_id"] in seen_ids:
                continue
            seen_ids.add(it["job_id"])
            collected.append(it)
            if len(collected) >= max_items:
                return collected, False, page1_html, f"Teamtailor HTML fallback hit max_items cap ({max_items})"

        if next_page is None:
            return collected, True, page1_html, None
        if next_page <= page or next_page in visited_pages:
            return collected, False, page1_html, f"Teamtailor HTML pagination loop: page {page} -> {next_page}"

        page = next_page

    return collected, False, page1_html, f"Teamtailor HTML fallback hit max_pages cap ({max_pages})"


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
    from src.project_files.field_normalizer import to_markdown
    from src.project_files.models import ExtractionMethod
    from src.project_files.work_model import resolve_work_model

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
    from src.project_files.models import ExtractionMethod
    from src.project_files.work_model import resolve_work_model

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
        **kwargs,
    ) -> BoardCheckResult:
        from urllib.parse import quote
        from src.project_files.company_board_registry import is_valid_board_slug

        if not is_valid_board_slug("teamtailor", board.board_token):
            return BoardCheckResult(success=False, snapshot_complete=False, error="Invalid Teamtailor board token")

        clean_slug = board.board_token.strip().lower()
        encoded_slug = quote(clean_slug, safe="-_.~")
        rss_url = f"https://{encoded_slug}.teamtailor.com/jobs.rss"
        headers = browser_headers(rss_url, "application/rss+xml, application/xml, text/xml;q=0.9, */*;q=0.8")
        if board.etag:
            headers["If-None-Match"] = board.etag
        if board.last_modified:
            headers["If-Modified-Since"] = board.last_modified

        max_bytes = int(kwargs.get("max_response_bytes") or settings.max_response_bytes)
        try:
            status, body_bytes, resp_headers = await throttled_stream_bytes(
                client,
                rss_url,
                headers=headers,
                timeout=timeout,
                max_bytes=max_bytes,
                follow_redirects=False,
            )
            if status == 304:
                return BoardCheckResult(
                    success=True,
                    not_modified=True,
                    etag=board.etag,
                    last_modified=board.last_modified,
                    content_fingerprint=board.content_fingerprint,
                    missing_confirmation_threshold=2,
                    snapshot_complete=True,
                )
            if status == 404:
                return BoardCheckResult(success=False, snapshot_complete=False, error="Board not found (HTTP 404)")
            if status != 200:
                return BoardCheckResult(success=False, snapshot_complete=False, error=f"HTTP {status}")

            rss_items, channel_meta, parse_err = parse_teamtailor_rss_feed(body_bytes)
            if parse_err:
                return BoardCheckResult(success=False, snapshot_complete=False, error=parse_err)

            new_etag = resp_headers.get("etag")
            new_lm = resp_headers.get("last-modified")
            company_name = channel_meta.get("channel_title") or board.company_name

            fp_items: list[tuple[str, str | None, str | None]] = [
                (it["job_id"], it.get("pub_date"), _teamtailor_rss_item_hash(it))
                for it in rss_items
            ]

            snapshot_complete = True
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
                )
                rss_ids = {it["job_id"] for it in rss_items}
                if html_complete:
                    html_only_cards = [c for c in html_cards if c["job_id"] not in rss_ids]
                    for card in html_only_cards:
                        fp_items.append((card["job_id"], None, _teamtailor_rss_item_hash(card)))
                else:
                    snapshot_complete = False
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
                    missing_confirmation_threshold=2,
                    snapshot_complete=True,
                )

            logo_url = board.company_logo_url
            logo_source = board.company_logo_source
            logo_verified = bool(board.company_logo_verified)
            logo_checked_at = board.company_logo_checked_at
            if page1_html and (not logo_url or not logo_verified):
                try:
                    from bs4 import BeautifulSoup
                    from src.project_files.logo_extractor import extract_company_logo_for_provider

                    logo_res = extract_company_logo_for_provider(
                        "teamtailor",
                        BeautifulSoup(page1_html, "html.parser"),
                        base_url=f"https://{encoded_slug}.teamtailor.com/jobs",
                    )
                    if logo_res.url and logo_res.verified:
                        logo_url = logo_res.url
                        logo_source = logo_res.source
                        logo_verified = True
                        logo_checked_at = time.time()
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
                missing_confirmation_threshold=2,
                snapshot_complete=snapshot_complete,
            )
        except (ResponseTooLargeError, CircuitBreakerOpenError, HostRateLimitedError, Exception) as exc:
            return BoardCheckResult(success=False, snapshot_complete=False, error=str(exc))


BOARD_ADAPTERS: dict[str, object] = {
    "greenhouse": GreenhouseBoardAdapter(),
    "lever": LeverBoardAdapter(),
    "ashby": AshbyBoardAdapter(),
    "workable": WorkableBoardAdapter(),
    "recruitee": RecruiteeBoardAdapter(),
    "smartrecruiters": SmartRecruitersBoardAdapter(),
    "teamtailor": TeamtailorBoardAdapter(),
}
