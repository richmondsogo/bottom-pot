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
import hashlib
import json
from typing import Optional

import httpx
from loguru import logger
from pydantic import BaseModel, Field

from src.config import settings
from src.project_files.company_board_registry import CompanyBoard
from src.project_files.field_normalizer import humanize_slug, parse_datetime
from src.project_files.http_headers import browser_headers
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


def compute_board_fingerprint(items: list[tuple[str, str | None]]) -> str:
    """Compute deterministic SHA256 digest of sorted (job_id, timestamp) tuples."""
    sorted_items = sorted(items, key=lambda x: x[0])
    payload = "|".join(f"{jid}:{ts or ''}" for jid, ts in sorted_items)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class GreenhouseBoardAdapter:
    """Adapter for Greenhouse public board API: GET /v1/boards/{slug}/jobs"""

    async def check_board(
        self,
        board: CompanyBoard,
        client: httpx.AsyncClient,
        timeout: float = 8.0,
    ) -> BoardCheckResult:
        url = f"https://boards-api.greenhouse.io/v1/boards/{board.board_token}/jobs"
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

            fingerprint_items = [(str(j.get("id")), str(j.get("updated_at"))) for j in raw_jobs if j.get("id")]
            fingerprint = compute_board_fingerprint(fingerprint_items)

            if board.content_fingerprint and fingerprint == board.content_fingerprint:
                return BoardCheckResult(
                    success=True,
                    not_modified=True,
                    etag=new_etag or board.etag,
                    last_modified=new_last_mod or board.last_modified,
                    content_fingerprint=fingerprint,
                )

            now = datetime.now(timezone.utc)
            company_name = board.company_name or humanize_slug(board.board_token)
            listings: list[JobListing] = []

            for item in raw_jobs:
                job_id = str(item.get("id") or "")
                title = (item.get("title") or "").strip()
                apply_url = (item.get("absolute_url") or "").strip()
                if not title or not apply_url:
                    continue

                loc_obj = item.get("location") or {}
                loc_name = loc_obj.get("name") if isinstance(loc_obj, dict) else str(loc_obj)
                loc_str = loc_name.strip() if loc_name else None
                posted_at = parse_datetime(item.get("updated_at"))

                listings.append(
                    JobListing(
                        id=f"greenhouse:{board.board_token}:{job_id}",
                        provider="greenhouse",
                        data_source="api",
                        ats_source="greenhouse",
                        title=title,
                        company=company_name,
                        location=loc_str,
                        apply_url=apply_url,
                        source_url=apply_url,
                        posted_at=posted_at,
                        scraped_at=now,
                        query_used=board.board_token,
                    )
                )

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

            fingerprint_items = [(str(it.get("id")), str(it.get("createdAt"))) for it in data if isinstance(it, dict) and it.get("id")]
            fingerprint = compute_board_fingerprint(fingerprint_items)

            if board.content_fingerprint and fingerprint == board.content_fingerprint:
                return BoardCheckResult(
                    success=True,
                    not_modified=True,
                    etag=new_etag or board.etag,
                    last_modified=new_last_mod or board.last_modified,
                    content_fingerprint=fingerprint,
                )

            now = datetime.now(timezone.utc)
            company_name = board.company_name or humanize_slug(board.board_token)
            listings: list[JobListing] = []

            for item in data:
                if not isinstance(item, dict):
                    continue
                job_id = str(item.get("id") or "")
                title = (item.get("text") or "").strip()
                apply_url = (item.get("applyUrl") or item.get("hostedUrl") or "").strip()
                hosted_url = (item.get("hostedUrl") or apply_url).strip()
                if not title or not hosted_url:
                    continue

                categories = item.get("categories") or {}
                location = categories.get("location") if isinstance(categories, dict) else None

                posted_at = None
                created_at_ms = item.get("createdAt")
                if created_at_ms and isinstance(created_at_ms, (int, float)):
                    try:
                        posted_at = datetime.fromtimestamp(created_at_ms / 1000.0, tz=timezone.utc)
                    except Exception:
                        posted_at = None

                listings.append(
                    JobListing(
                        id=f"lever:{board.board_token}:{job_id}",
                        provider="lever",
                        data_source="api",
                        ats_source="lever",
                        title=title,
                        company=company_name,
                        location=location.strip() if location else None,
                        apply_url=apply_url or hosted_url,
                        source_url=hosted_url,
                        posted_at=posted_at,
                        scraped_at=now,
                        query_used=board.board_token,
                    )
                )

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

            fingerprint_items = [(str(j.get("id")), str(j.get("publishedAt"))) for j in raw_jobs if isinstance(j, dict) and j.get("id")]
            fingerprint = compute_board_fingerprint(fingerprint_items)

            if board.content_fingerprint and fingerprint == board.content_fingerprint:
                return BoardCheckResult(
                    success=True,
                    not_modified=True,
                    etag=new_etag or board.etag,
                    last_modified=new_last_mod or board.last_modified,
                    content_fingerprint=fingerprint,
                )

            now = datetime.now(timezone.utc)
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
                posted_at = parse_datetime(item.get("publishedAt"))

                listings.append(
                    JobListing(
                        id=f"ashby:{board.board_token}:{job_id}",
                        provider="ashby",
                        data_source="api",
                        ats_source="ashby",
                        title=title,
                        company=company_name,
                        location=loc_str,
                        apply_url=apply_url,
                        source_url=job_url,
                        posted_at=posted_at,
                        scraped_at=now,
                        query_used=board.board_token,
                    )
                )

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
