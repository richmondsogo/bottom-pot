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
    throttled_get,
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


BOARD_ADAPTERS: dict[str, object] = {
    "greenhouse": GreenhouseBoardAdapter(),
    "lever": LeverBoardAdapter(),
    "ashby": AshbyBoardAdapter(),
    "workable": WorkableBoardAdapter(),
}
