"""
ATS Company-Board Adapters for Independent Monitoring.

Provides unauthenticated public endpoint adapters for:
- Greenhouse (GET /v1/boards/{token}/jobs)
- Lever (GET /v0/postings/{token}?mode=json)
- Ashby (POST /posting-api/job-board/{token})

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
from typing import Optional

import httpx
from loguru import logger
from pydantic import BaseModel, Field

from src.config import settings
from src.project_files.canonical_job_adapter import CanonicalJobAdapter
from src.project_files.company_board_registry import CompanyBoard
from src.project_files.field_normalizer import humanize_slug, parse_datetime
from src.project_files.http_headers import browser_headers
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
        url = f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs/{job_id}"
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
        url = f"https://boards-api.greenhouse.io/v1/boards/{board.board_token}/jobs?content=true"
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
                ch = hashlib.sha256(f"{title_val}:{loc_val}:{content_sample}".encode("utf-8")).hexdigest()[:16]
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

                loc_obj = item.get("location") or {}
                loc_name = loc_obj.get("name") if isinstance(loc_obj, dict) else str(loc_obj)
                loc_str = loc_name.strip() if loc_name else None
                updated_at = item.get("updated_at")

                dept_name = None
                depts = item.get("departments")
                if depts and isinstance(depts, list) and len(depts) > 0 and isinstance(depts[0], dict):
                    dept_name = depts[0].get("name")

                raw_content = item.get("content")
                has_authentic_content = (
                    isinstance(raw_content, str) and bool(raw_content.strip())
                )
                desc_to_use = raw_content if has_authentic_content else None

                # Publication date vs update date:
                # Use authoritative first_published when available; preserve known dates;
                # use bounded fetched details when available. Never fall back to updated_at as posted_at.
                first_published = (
                    item.get("first_published")
                    or known_dates.get(job_id)
                    or known_dates.get(f"greenhouse:{board.board_token}:{job_id}")
                    or (fetched_details_map.get(job_id) or {}).get("first_published")
                )

                raw_fields_dict = dict(item)
                raw_fields_dict["is_board_monitor"] = True
                if updated_at:
                    raw_fields_dict["updated_at"] = updated_at
                if first_published:
                    raw_fields_dict["first_published"] = first_published

                raw = RawJobPosting(
                    provider="greenhouse",
                    source_url=apply_url,
                    provider_job_id=job_id,
                    company_slug=board.board_token,
                    apply_url=apply_url,
                    raw_title=title,
                    raw_company=company_name,
                    raw_location=loc_str,
                    raw_department=dept_name,
                    raw_date=first_published,
                    raw_fields=raw_fields_dict,
                    raw_description=desc_to_use,
                    description_is_authentic=has_authentic_content,
                    query_used=board.board_token,
                )
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


class AshbyBoardAdapter:
    """Adapter for Ashby public board API: POST /posting-api/job-board/{slug}"""

    async def check_board(
        self,
        board: CompanyBoard,
        client: httpx.AsyncClient,
        timeout: float = 8.0,
        **kwargs,
    ) -> BoardCheckResult:
        url = f"https://api.ashbyhq.com/posting-api/job-board/{board.board_token}"
        headers = browser_headers(url, "application/json")

        try:
            resp = await client.post(url, headers=headers, json={}, timeout=timeout)
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
                ts = str(j.get("publishedAt") or "")
                title_val = str(j.get("title") or "")
                desc_val = str(j.get("descriptionPlain") or j.get("descriptionHtml") or "")
                ch = hashlib.sha256(f"{title_val}:{desc_val[:200]}".encode("utf-8")).hexdigest()[:16]
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
            listings: list[JobListing] = []

            for item in raw_jobs:
                if not isinstance(item, dict):
                    continue
                job_id = str(item.get("id") or "")
                title = (item.get("title") or "").strip()
                job_url = (item.get("jobUrl") or "").strip()
                apply_url = (item.get("applyUrl") or job_url).strip()
                if not title or not job_url:
                    continue

                location = item.get("location")
                loc_str = str(location).strip() if location else None
                department = item.get("department")
                employment_type = item.get("employmentType")
                is_remote = item.get("isRemote")
                desc_plain = item.get("descriptionPlain") or item.get("descriptionHtml")

                raw = RawJobPosting(
                    provider="ashby",
                    source_url=job_url,
                    provider_job_id=job_id,
                    company_slug=board.board_token,
                    apply_url=apply_url,
                    raw_title=title,
                    raw_company=company_name,
                    raw_location=loc_str,
                    raw_department=department,
                    raw_employment_type=employment_type,
                    raw_workplace_type="remote" if is_remote is True else None,
                    raw_description=desc_plain,
                    description_is_authentic=bool(desc_plain),
                    raw_date=item.get("publishedAt"),
                    raw_fields=item,
                    query_used=board.board_token,
                )
                canonical = JobExtractionService.extract(raw)
                listing = CanonicalJobAdapter.to_listing(canonical)
                listing.provider = "ashby"
                listing.ats_source = "ashby"
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


BOARD_ADAPTERS: dict[str, object] = {
    "greenhouse": GreenhouseBoardAdapter(),
    "lever": LeverBoardAdapter(),
    "ashby": AshbyBoardAdapter(),
}
