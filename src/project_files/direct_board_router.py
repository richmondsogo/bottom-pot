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
    Probes Greenhouse public list API: GET https://boards-api.greenhouse.io/v1/boards/{slug}/jobs
    """
    url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
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
        company_name = humanize_slug(slug)
        now = datetime.now(timezone.utc)

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
                    id=f"greenhouse:{slug}:{job_id}",
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
                    query_used=slug,
                )
            )
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

        company_name = humanize_slug(slug)
        now = datetime.now(timezone.utc)

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
                    id=f"lever:{slug}:{job_id}",
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
                    query_used=slug,
                )
            )
        return listings
    except Exception as exc:
        logger.debug(f"[direct_board_router] Lever probe for '{slug}' failed: {exc}")
        return []


async def probe_ashby_board(slug: str, client: httpx.AsyncClient) -> list[JobListing]:
    """
    Probes Ashby public list API: POST https://api.ashbyhq.com/posting-api/job-board/{slug}
    """
    url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
    try:
        resp = await client.post(
            url,
            headers=browser_headers(url, "application/json"),
            json={},
            timeout=_ROUTER_TIMEOUT,
        )
        if resp.status_code != 200:
            return []
        data = resp.json()
        raw_jobs = data.get("jobs") or []
        company_name = humanize_slug(slug)
        now = datetime.now(timezone.utc)

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
                    id=f"ashby:{slug}:{job_id}",
                    provider="ashby",
                    data_source="api",
                    ats_source="ashby",
                    title=title,
                    company=company_name,
                    location=loc_str,
                    apply_url=apply_url or job_url,
                    source_url=job_url,
                    posted_at=posted_at,
                    scraped_at=now,
                    query_used=slug,
                )
            )
        return listings
    except Exception as exc:
        logger.debug(f"[direct_board_router] Ashby probe for '{slug}' failed: {exc}")
        return []


async def probe_direct_boards(
    slugs: list[str],
    client: httpx.AsyncClient,
    platforms: Optional[list[str]] = None,
) -> list[JobListing]:
    """
    Concurrently probes candidate company slugs across Greenhouse, Lever, and Ashby.
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

    if not tasks:
        return []

    results = await asyncio.gather(*tasks, return_exceptions=True)
    all_jobs: list[JobListing] = []
    for res in results:
        if isinstance(res, list):
            all_jobs.extend(res)

    return all_jobs
