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
import re
from typing import Optional

import httpx
from loguru import logger

from src.core.exceptions import SafetyError
from src.core.http_headers import browser_headers
from src.core.http_resilience import throttled_get, throttled_stream_bytes
from src.core.models import JobListing
from src.core.settings import settings
from src.extraction.field_normalizer import humanize_slug

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

        from src.ats.ats_api_client import (
            enrich_greenhouse_board_identity,
            greenhouse_payload_to_raw,
        )
        from src.extraction.canonical_job_adapter import CanonicalJobAdapter
        from src.extraction.job_extraction_service import JobExtractionService

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
        except (asyncio.CancelledError, SafetyError):
            raise
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
    except (asyncio.CancelledError, SafetyError):
        raise
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

        from src.ats.ats_api_client import enrich_lever_board_identity, lever_payload_to_raw
        from src.extraction.canonical_job_adapter import CanonicalJobAdapter
        from src.extraction.job_extraction_service import JobExtractionService

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
        except (asyncio.CancelledError, SafetyError):
            raise
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
    except (asyncio.CancelledError, SafetyError):
        raise
    except Exception as exc:
        logger.debug(f"[direct_board_router] Lever probe for '{slug}' failed: {exc}")
        return []


async def probe_ashby_board(slug: str, client: httpx.AsyncClient) -> list[JobListing]:
    """
    Probes Ashby public list API: GET https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true
    """
    from urllib.parse import quote

    from src.ats.ats_api_client import ashby_payload_to_raw, enrich_ashby_board_identity
    from src.extraction.canonical_job_adapter import CanonicalJobAdapter
    from src.extraction.job_extraction_service import JobExtractionService

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
    except (asyncio.CancelledError, SafetyError):
        raise
    except Exception as exc:
        logger.debug(f"[direct_board_router] Ashby probe for '{slug}' failed: {exc}")
        return []


async def probe_workable_board(slug: str, client: httpx.AsyncClient) -> list[JobListing]:
    """
    Probes Workable public widget + bounded api/v2 detail endpoints.
    """
    from urllib.parse import quote

    from src.providers.board_adapters import hydrate_workable_board_jobs

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
    except (asyncio.CancelledError, SafetyError):
        raise
    except Exception as exc:
        logger.debug(f"[direct_board_router] Workable probe for '{slug}' failed: {exc}")
        return []


async def probe_recruitee_board(slug: str, client: httpx.AsyncClient) -> list[JobListing]:
    """
    Probes GET https://{slug}.recruitee.com/api/offers/ and returns normalized JobListings
    via the shared ``recruitee_payload_to_raw`` converter. Validates the complete snapshot
    before hydration and returns [] cleanly on 404, malformed/unrecognized entries, or error.
    """
    import json
    from urllib.parse import quote

    from src.providers.board_adapters import (
        hydrate_recruitee_offers,
        validate_recruitee_offers_snapshot,
    )
    from src.storage.company_board_registry import is_valid_board_slug

    clean_slug = (slug or "").strip().lower()
    if not is_valid_board_slug("recruitee", clean_slug):
        return []

    encoded_slug = quote(clean_slug, safe="-_.~")
    url = f"https://{encoded_slug}.recruitee.com/api/offers/"
    headers = browser_headers(url, "application/json")
    headers["Accept-Encoding"] = "gzip, deflate"

    try:
        status, body_bytes, _ = await throttled_stream_bytes(
            client,
            url,
            headers=headers,
            timeout=float(settings.ats_request_timeout_seconds),
            max_bytes=settings.recruitee_board_max_response_bytes,
            follow_redirects=False,
        )
        if status != 200:
            return []
        data = json.loads(body_bytes.decode("utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("offers"), list):
            return []
        active_offers, validation_error = validate_recruitee_offers_snapshot(data["offers"])
        if validation_error or not active_offers:
            return []
        listings = await hydrate_recruitee_offers(
            clean_slug,
            active_offers,
            client,
            is_board_monitor=False,
        )
        if len(listings) != len(active_offers):
            logger.debug(
                f"[direct_board_router] Recruitee probe hydration mismatch for '{slug}': "
                f"converted {len(listings)} of {len(active_offers)} active offers"
            )
            return []
        return listings
    except (asyncio.CancelledError, SafetyError):
        raise
    except Exception as exc:
        logger.debug(f"[direct_board_router] Recruitee probe for '{slug}' failed: {exc}")
        return []


async def probe_smartrecruiters_board(
    slug: str,
    client: httpx.AsyncClient,
    *,
    max_detail_fetches: int = 15,
) -> list[JobListing]:
    """
    Probes SmartRecruiters public postings API sequentially with atomic snapshot
    validation and bounded detail hydration via validated ``ref`` URLs.

    Returns ``[]`` cleanly on unknown-company 200-empty responses, HTTP errors, or
    incomplete/malformed pagination snapshots so bogus or broken boards are never registered.
    """
    from src.providers.board_adapters import (
        fetch_smartrecruiters_postings_snapshot,
        hydrate_smartrecruiters_board_jobs,
    )
    from src.storage.company_board_registry import is_valid_board_slug

    clean_slug = (slug or "").strip().lower()
    if not is_valid_board_slug("smartrecruiters", clean_slug):
        return []

    try:
        raw_items, snapshot_err = await fetch_smartrecruiters_postings_snapshot(
            clean_slug,
            client,
            timeout=float(settings.ats_request_timeout_seconds),
        )
        if snapshot_err or not raw_items:
            return []

        cap = max(0, int(max_detail_fetches))
        listings, _ = await hydrate_smartrecruiters_board_jobs(
            clean_slug,
            raw_items,
            client,
            max_new_hydrations_per_poll=cap,
            max_revalidations_per_poll=0,
            max_detail_fetches=cap,
            timeout=float(settings.ats_request_timeout_seconds),
            is_board_monitor=False,
        )
        return listings
    except (asyncio.CancelledError, SafetyError):
        raise
    except Exception as exc:
        logger.debug(f"[direct_board_router] SmartRecruiters probe for '{slug}' failed: {exc}")
        return []


async def probe_teamtailor_board(slug: str, client: httpx.AsyncClient) -> list[JobListing]:
    """
    Probes Teamtailor public RSS feed: ``GET https://{slug}.teamtailor.com/jobs.rss``.

    Returns ``[]`` cleanly on 404, redirects, invalid XML, or network errors.
    """
    from urllib.parse import quote

    from src.providers.board_adapters import (
        _teamtailor_rss_item_to_listing,
        parse_teamtailor_rss_feed,
    )
    from src.storage.company_board_registry import is_valid_board_slug

    clean_slug = (slug or "").strip().lower()
    if not is_valid_board_slug("teamtailor", clean_slug):
        return []

    encoded_slug = quote(clean_slug, safe="-_.~")
    url = f"https://{encoded_slug}.teamtailor.com/jobs.rss"
    headers = browser_headers(url, "application/rss+xml, application/xml, text/xml;q=0.9, */*;q=0.8")
    try:
        status, body_bytes, _ = await throttled_stream_bytes(
            client,
            url,
            headers=headers,
            timeout=float(settings.ats_request_timeout_seconds),
            max_bytes=settings.max_response_bytes,
            follow_redirects=False,
        )
        if status != 200:
            return []
        rss_items, channel_meta, parse_err = parse_teamtailor_rss_feed(body_bytes)
        if parse_err or not rss_items:
            return []
        company_name = channel_meta.get("channel_title") or None
        return [
            _teamtailor_rss_item_to_listing(
                it,
                board_token=clean_slug,
                board_company_name=company_name,
                is_board_monitor=False,
            )
            for it in rss_items
        ]
    except (asyncio.CancelledError, SafetyError):
        raise
    except Exception as exc:
        logger.debug(f"[direct_board_router] Teamtailor probe for '{slug}' failed: {exc}")
        return []


async def probe_personio_board(slug: str, client: httpx.AsyncClient) -> list[JobListing]:
    """
    Probes Personio public XML feed: ``GET https://{slug}.jobs.personio.com/xml?language=en``
    (with bounded single fallback to default ``/xml`` if any position lacks descriptions).

    Returns ``[]`` cleanly on 404, redirects, invalid XML, mismatched bilingual feeds, or errors.
    """
    from urllib.parse import quote

    from src.providers.board_adapters import (
        _get_personio_xml,
        _merge_personio_feeds,
        _personio_position_to_listing,
    )
    from src.storage.company_board_registry import is_valid_board_slug

    clean_slug = (slug or "").strip().lower()
    if not is_valid_board_slug("personio", clean_slug):
        return []

    encoded_slug = quote(clean_slug, safe="-_.~")
    timeout = float(settings.ats_request_timeout_seconds)
    max_bytes = settings.max_response_bytes
    en_url = f"https://{encoded_slug}.jobs.personio.com/xml?language=en"
    def_url = f"https://{encoded_slug}.jobs.personio.com/xml"
    try:
        _, en_items, _, en_err = await _get_personio_xml(
            client,
            en_url,
            timeout=timeout,
            max_bytes=max_bytes,
        )
        if en_err or not en_items:
            return []

        if any(not it.get("description_html") for it in en_items):
            _, def_items, _, def_err = await _get_personio_xml(
                client,
                def_url,
                timeout=timeout,
                max_bytes=max_bytes,
            )
            if def_err or def_items is None:
                return []
            merged_items, merge_err = _merge_personio_feeds(en_items, def_items)
            if merge_err:
                return []
        else:
            merged_items = en_items

        return [
            _personio_position_to_listing(
                it,
                board_token=clean_slug,
                is_board_monitor=False,
            )
            for it in merged_items
        ]
    except (asyncio.CancelledError, SafetyError):
        raise
    except Exception as exc:
        logger.debug(f"[direct_board_router] Personio probe for '{slug}' failed: {exc}")
        return []


async def probe_pinpoint_board(slug: str, client: httpx.AsyncClient) -> list[JobListing]:
    """
    Probes Pinpoint public postings feed: ``GET https://{slug}.pinpointhq.com/postings.json``.

    Returns ``[]`` cleanly on 404, redirects, invalid JSON, empty boards, or errors.
    """
    from urllib.parse import quote

    from src.providers.board_adapters import (
        _pinpoint_item_to_listing,
        parse_pinpoint_postings_json,
        resolve_pinpoint_board_timeout,
    )
    from src.storage.company_board_registry import is_valid_board_slug

    clean_slug = (slug or "").strip().lower()
    if not is_valid_board_slug("pinpointhq", clean_slug):
        return []

    encoded_slug = quote(clean_slug, safe="-_.~")
    url = f"https://{encoded_slug}.pinpointhq.com/postings.json"
    headers = browser_headers(url, "application/json")
    headers["Accept-Encoding"] = "gzip, deflate"

    try:
        status, body_bytes, _ = await throttled_stream_bytes(
            client,
            url,
            headers=headers,
            timeout=resolve_pinpoint_board_timeout(bound_to_search_timeout=True),
            max_bytes=settings.pinpoint_board_max_response_bytes,
            follow_redirects=False,
        )
        if status != 200:
            return []
        items, parse_err = parse_pinpoint_postings_json(body_bytes, expected_slug=clean_slug)
        if parse_err or not items:
            return []
        return [
            _pinpoint_item_to_listing(
                it,
                board_token=clean_slug,
                is_board_monitor=False,
            )
            for it in items
        ]
    except (asyncio.CancelledError, SafetyError):
        raise
    except Exception as exc:
        logger.debug(f"[direct_board_router] Pinpoint probe for '{slug}' failed: {exc}")
        return []


async def probe_direct_boards(
    slugs: list[str],
    client: httpx.AsyncClient,
    platforms: Optional[list[str]] = None,
) -> list[JobListing]:
    """
    Concurrently probes candidate company slugs across Greenhouse, Lever, Ashby, Workable,
    Recruitee, SmartRecruiters, Teamtailor, Personio, and Pinpoint. Honors platforms filter if provided.
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
        if target_platforms is None or "recruitee" in target_platforms:
            tasks.append(probe_recruitee_board(slug, client))
        if target_platforms is None or "smartrecruiters" in target_platforms:
            tasks.append(probe_smartrecruiters_board(slug, client))
        if target_platforms is None or "teamtailor" in target_platforms:
            tasks.append(probe_teamtailor_board(slug, client))
        if target_platforms is None or "personio" in target_platforms:
            tasks.append(probe_personio_board(slug, client))
        if target_platforms is None or "pinpointhq" in target_platforms:
            tasks.append(probe_pinpoint_board(slug, client))

    if not tasks:
        return []

    results = await asyncio.gather(*tasks, return_exceptions=True)
    all_jobs: list[JobListing] = []
    for res in results:
        if isinstance(res, list):
            all_jobs.extend(res)

    return all_jobs
