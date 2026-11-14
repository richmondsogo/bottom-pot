"""
Direct ATS Job Board Router.

Probes public ATS board endpoints directly (Greenhouse, Lever, Ashby)
when candidate company slugs are detected in search queries, eliminating
reliance on Serper for direct company lookups.

Strict adherence to ADR 0001 ("Unknown beats wrong"):
If a company slug returns 404 or fails, it is quietly dropped without guessing or fabricating.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import re
from typing import Optional

import httpx
from loguru import logger

from src.config import settings
from src.project_files.field_normalizer import humanize_slug, parse_datetime
from src.project_files.http_headers import browser_headers
from src.project_files.http_resilience import throttled_get
from src.project_files.models import JobListing

_ROUTER_TIMEOUT = httpx.Timeout(settings.ats_request_timeout_seconds)

# Stopwords representing common job titles, seniorities, and locations that are NOT company names
_ROLE_STOPWORDS = {
    "software",
    "engineer",
    "engineering",
    "developer",
    "development",
    "senior",
    "sr",
    "junior",
    "jr",
    "staff",
    "lead",
    "principal",
    "manager",
    "management",
    "director",
    "backend",
    "frontend",
    "fullstack",
    "full-stack",
    "systems",
    "devops",
    "sre",
    "infrastructure",
    "infra",
    "cloud",
    "data",
    "analyst",
    "analytics",
    "scientist",
    "ml",
    "ai",
    "intern",
    "internship",
    "designer",
    "product",
    "qa",
    "test",
    "security",
    "remote",
    "hybrid",
    "onsite",
    "jobs",
    "job",
    "careers",
    "career",
    "hiring",
    "react",
    "vue",
    "angular",
    "node",
    "python",
    "golang",
    "ruby",
    "java",
    "rust",
    "c",
    "cpp",
    "csharp",
    "dotnet",
    "aws",
    "gcp",
    "azure",
    "sql",
    "nosql",
    "ios",
    "android",
    "flutter",
    "lagos",
    "abuja",
    "nigeria",
    "africa",
    "us",
    "uk",
    "london",
    "york",
    "francisco",
}


def extract_company_slug_candidates(query: str) -> list[str]:
    """
    Extracts potential company slug candidates from a user query string.
    
    Examples:
        "Palantir" -> ["palantir"]
        "palantir engineer" -> ["palantir"]
        "senior backend developer reddit" -> ["reddit"]
        "software engineer" -> [] (all tokens are role words)
    """
    if not query or not query.strip():
        return []

    cleaned = re.sub(r"[^\w\s-]", " ", query).strip()
    tokens = [t.lower() for t in cleaned.split() if t]

    candidates: list[str] = []
    # If the entire query is 1 token and not a pure role word
    if len(tokens) == 1:
        tok = tokens[0]
        if tok not in _ROLE_STOPWORDS and len(tok) >= 2:
            candidates.append(tok)
        return candidates

    # Filter out stopwords
    non_stopwords = [t for t in tokens if t not in _ROLE_STOPWORDS and len(t) >= 2 and not t.isdigit()]

    # If 1 or 2 non-stopwords remain, they are likely company names
    for token in non_stopwords:
        if token not in candidates:
            candidates.append(token)

    return candidates[:3]


async def probe_greenhouse_board(slug: str, client: httpx.AsyncClient) -> list[JobListing]:
    """
    Probes Greenhouse public list API:
    GET https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true&pay_transparency=true
    """
    url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true&pay_transparency=true"
    try:
        resp = await client.get(
            url,
            headers=browser_headers(url, "application/json,text/plain;q=0.9,*/*;q=0.8"),
            timeout=_ROUTER_TIMEOUT,
        )
        if resp.status_code != 200:
            return []
        data = resp.json()
        raw_jobs = data.get("jobs") or []

        from src.project_files.ats_api_client import (
            enrich_greenhouse_board_identity,
            greenhouse_payload_to_raw,
        )
        from src.project_files.canonical_job_adapter import CanonicalJobAdapter
        from src.project_files.job_extraction_service import JobExtractionService

        board_name: str | None = None
        board_logo_url: str | None = None
        board_logo_source: str | None = None
        board_logo_verified = False
        try:
            b_name, b_logo = await enrich_greenhouse_board_identity(slug, client)
            board_name = b_name
            if b_logo.url and b_logo.verified:
                board_logo_url = b_logo.url
                board_logo_source = b_logo.source
                board_logo_verified = True
        except Exception:
            pass

        listings: list[JobListing] = []
        for item in raw_jobs:
            raw = greenhouse_payload_to_raw(
                item,
                company_slug=slug,
                query_used=slug,
                default_company_name=board_name,
                is_board_monitor=False,
                company_logo_url=board_logo_url,
                company_logo_source=board_logo_source,
                company_logo_verified=board_logo_verified,
            )
            if raw is None or not raw.raw_title or not raw.source_url:
                continue
            canonical = JobExtractionService.extract(raw)
            listing = CanonicalJobAdapter.to_listing(canonical)
            listing.provider = "greenhouse"
            listing.ats_source = "greenhouse"
            listing.data_source = "api"
            listings.append(listing)
        return listings
    except Exception as exc:
        logger.debug(f"[direct_board_router] Greenhouse probe for '{slug}' failed: {exc}")
        return []


async def probe_lever_board(slug: str, client: httpx.AsyncClient) -> list[JobListing]:
    """
    Probes Lever public list API: GET https://api.lever.co/v0/postings/{slug}?mode=json
    """
    url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
    try:
        resp = await client.get(
            url,
            headers=browser_headers(url, "application/json,text/plain;q=0.9,*/*;q=0.8"),
            timeout=_ROUTER_TIMEOUT,
        )
        if resp.status_code != 200:
            return []
        data = resp.json()
        if not isinstance(data, list):
            return []

        from src.project_files.ats_api_client import enrich_lever_board_identity, lever_payload_to_raw
        from src.project_files.canonical_job_adapter import CanonicalJobAdapter
        from src.project_files.job_extraction_service import JobExtractionService

        board_name: str | None = None
        board_logo_url: str | None = None
        board_logo_source: str | None = None
        board_logo_verified = False
        try:
            b_name, b_logo = await enrich_lever_board_identity(slug, client)
            board_name = b_name
            if b_logo.url and b_logo.verified:
                board_logo_url = b_logo.url
                board_logo_source = b_logo.source
                board_logo_verified = True
        except Exception:
            pass

        listings: list[JobListing] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            raw = lever_payload_to_raw(
                item,
                company_slug=slug,
                query_used=slug,
                default_company_name=board_name,
            )
            if raw is None or not raw.raw_title or not raw.source_url:
                continue
            if board_logo_verified and board_logo_url and not raw.raw_fields.get("company_logo_url"):
                raw.raw_fields["company_logo_url"] = board_logo_url
                raw.raw_fields["company_logo_source"] = board_logo_source
                raw.raw_fields["company_logo_verified"] = True
            canonical = JobExtractionService.extract(raw)
            listing = CanonicalJobAdapter.to_listing(canonical)
            listing.provider = "lever"
            listing.ats_source = "lever"
            listing.data_source = "api"
            listings.append(listing)
        return listings
    except Exception as exc:
        logger.debug(f"[direct_board_router] Lever probe for '{slug}' failed: {exc}")
        return []


async def probe_ashby_board(slug: str, client: httpx.AsyncClient) -> list[JobListing]:
    """
    Probes Ashby public list API: GET https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true
    """
    from urllib.parse import quote
    from src.project_files.ats_api_client import ashby_payload_to_raw, enrich_ashby_board_identity
    from src.project_files.canonical_job_adapter import CanonicalJobAdapter
    from src.project_files.job_extraction_service import JobExtractionService

    encoded_slug = quote(slug, safe="-_.~")
    url = f"https://api.ashbyhq.com/posting-api/job-board/{encoded_slug}?includeCompensation=true"
    headers = browser_headers(url, "application/json")
    headers["Accept-Encoding"] = "gzip, deflate"

    try:
        resp = await client.get(
            url,
            headers=headers,
            timeout=_ROUTER_TIMEOUT,
        )
        if resp.status_code != 200:
            return []
        data = resp.json()
        if not isinstance(data, dict):
            return []
        raw_jobs = data.get("jobs") or []
        if not isinstance(raw_jobs, list):
            return []

        company_name = humanize_slug(slug)
        board_logo_url: str | None = None
        board_logo_source: str | None = None
        board_logo_verified = False
        try:
            b_name, b_logo = await enrich_ashby_board_identity(slug, client)
            if b_name:
                company_name = b_name
            if b_logo.verified and b_logo.url:
                board_logo_url = b_logo.url
                board_logo_source = b_logo.source
                board_logo_verified = True
        except Exception:
            pass

        listings: list[JobListing] = []
        for item in raw_jobs:
            if not isinstance(item, dict):
                continue
            raw = ashby_payload_to_raw(
                item,
                company_slug=slug,
                query_used=slug,
                default_company_name=company_name,
                is_board_monitor=True,
                company_logo_url=board_logo_url,
                company_logo_source=board_logo_source,
                company_logo_verified=board_logo_verified,
            )
            if raw is None or not raw.raw_title or not raw.source_url:
                continue
            canonical = JobExtractionService.extract(raw)
            listing = CanonicalJobAdapter.to_listing(canonical)
            listing.provider = "ashby"
            listing.ats_source = "ashby"
            listing.data_source = "api"
            if board_logo_verified and board_logo_url and not listing.company_logo_url:
                listing.company_logo_url = board_logo_url
                listing.company_logo_source = board_logo_source
                listing.company_logo_verified = True
            listings.append(listing)
        return listings
    except Exception as exc:
        logger.debug(f"[direct_board_router] Ashby probe for '{slug}' failed: {exc}")
        return []


async def probe_workable_board(slug: str, client: httpx.AsyncClient) -> list[JobListing]:
    """
    Probes Workable public widget + bounded api/v2 detail endpoints.
    """
    from urllib.parse import quote
    from src.project_files.board_adapters import hydrate_workable_board_jobs

    encoded_slug = quote(slug, safe="-_.~")
    url = f"https://apply.workable.com/api/v1/widget/accounts/{encoded_slug}"
    headers = browser_headers(url, "application/json")

    try:
        resp = await throttled_get(client, url, headers=headers, timeout=_ROUTER_TIMEOUT)
        if resp.status_code != 200:
            return []
        data = resp.json()
        if not isinstance(data, dict):
            return []
        raw_jobs = data.get("jobs") or []
        if not isinstance(raw_jobs, list):
            return []

        listings, _ = await hydrate_workable_board_jobs(
            slug,
            raw_jobs,
            client,
            widget_company_name=(str(data.get("name")).strip() if data.get("name") else None),
            max_detail_fetches=15,
            timeout=_ROUTER_TIMEOUT,
            is_board_monitor=False,
        )
        return listings
    except Exception as exc:
        logger.debug(f"[direct_board_router] Workable probe for '{slug}' failed: {exc}")
        return []


async def probe_direct_boards(
    slugs: list[str],
    client: httpx.AsyncClient,
    platforms: Optional[list[str]] = None,
) -> list[JobListing]:
    """
    Concurrently probes candidate company slugs across Greenhouse, Lever, Ashby, and Workable.
    Honors platforms filter if provided.
    """
    if not slugs:
        return []

    target_platforms = (
        {p.strip().lower() for p in platforms if p and p.strip()}
        if platforms is not None
        else None
    )

    tasks = []
    for slug in slugs:
        if target_platforms is None or "greenhouse" in target_platforms:
            tasks.append(probe_greenhouse_board(slug, client))
        if target_platforms is None or "lever" in target_platforms:
            tasks.append(probe_lever_board(slug, client))
        if target_platforms is None or "ashby" in target_platforms:
            tasks.append(probe_ashby_board(slug, client))
        if target_platforms is None or "workable" in target_platforms:
            tasks.append(probe_workable_board(slug, client))

    if not tasks:
        return []

    results = await asyncio.gather(*tasks, return_exceptions=True)
    all_jobs: list[JobListing] = []
    for res in results:
        if isinstance(res, list):
            all_jobs.extend(res)

    return all_jobs
