"""
ATS API clients — one class per platform.

All endpoints are public, unauthenticated GET requests.
The orchestrator owns the httpx.AsyncClient lifecycle and passes it in.

Return values:
  - None         → 404 dead listing (silently discard)
  - JobListing   → data_source="api" on success
  - JobListing   → data_source="snippet" on timeout/unexpected error (uses fallback_snippet)
"""

from __future__ import annotations

import asyncio
import hashlib
import html
import re
import time
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import quote

import httpx
from loguru import logger
from bs4 import BeautifulSoup

from src.config import settings
from src.project_files.ats_url_parser import ParsedATSUrl, canonicalize_recognized_greenhouse_url
from src.project_files.url_normalizer import normalize_job_url
from src.project_files.company_board_registry import (
    CompanyBoardRegistry,
    company_board_registry,
    is_valid_board_slug,
)
from src.project_files.exceptions import ParseError, SearchProviderError
from src.project_files.http_resilience import (
    CircuitBreakerOpenError,
    HostRateLimitedError,
    throttled_get,
)
from src.project_files.logo_extractor import (
    LogoResult,
    extract_ashby_app_data_from_soup,
    extract_company_logo_for_provider,
)
from src.project_files.field_normalizer import (
    clean_html_to_markdown,
    description_quality,
    humanize_slug,
    normalize_fields,
    normalize_job_type,
    normalize_job_type_from_text,
    normalize_work_model,
    parse_datetime,
    to_markdown,
)
from src.project_files.work_model import WorkModelResult, resolve_work_model, strip_li_tags
from src.project_files.http_headers import browser_headers
from src.project_files.models import ExtractionMethod, JobListing
from src.project_files.canonical_job_adapter import CanonicalJobAdapter
from src.project_files.job_extraction_service import JobExtractionService, RawJobPosting
from src.project_files.extraction_outcome import (
    ExtractionOutcome,
    ExtractionResult,
    map_status_or_exception_to_outcome,
    sanitize_error_text,
)
from src.project_files.retry import get_current_attempts, with_retry

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TIMEOUT = httpx.Timeout(settings.ats_request_timeout_seconds)


def _make_id(provider: str, company_slug: str, job_id: str) -> str:
    return f"{provider}:{company_slug}:{job_id}"


def _normalize_employment(raw: str | None) -> str | None:
    return normalize_job_type(raw)


def _normalize_work_model(raw: str | None, is_remote: bool | None = None, **kwargs: str | None) -> str | None:
    return normalize_work_model(raw, is_remote, **kwargs)


def _text_from_html(value: str | None) -> str | None:
    """Convert HTML or plain-text job-description body into clean Markdown."""
    return to_markdown(value)


def _first_name(value: object) -> str | None:
    """Read a name from common ATS object/list response shapes."""
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, dict):
        name = value.get("name") or value.get("label") or value.get("title")
        return name.strip() if isinstance(name, str) and name.strip() else None
    if isinstance(value, list) and value:
        return _first_name(value[0])
    return None


def _fallback(
    parsed: ParsedATSUrl,
    fallback_snippet: str | None,
    query_used: str,
) -> JobListing:
    """Build a minimal snippet-based JobListing when the ATS API fails."""
    fields = normalize_fields(title=fallback_snippet, snippet=fallback_snippet)
    raw = RawJobPosting(
        provider=parsed.ats,
        source_url=parsed.raw_url,
        apply_url=parsed.raw_url,
        provider_job_id=parsed.job_id,
        company_slug=parsed.company_slug,
        raw_title=fields.get("title") or fallback_snippet or parsed.raw_url,
        raw_company=humanize_slug(parsed.company_slug) or "Unknown",
        raw_location=fields.get("location"),
        raw_description=None,
        raw_employment_type=fields.get("employment_type"),
        raw_fields={"snippet": fallback_snippet},
        description_is_authentic=False,
        query_used=query_used,
        extraction_method=ExtractionMethod.SNIPPET,
    )
    canonical = JobExtractionService.extract(raw)
    listing = CanonicalJobAdapter.to_listing(canonical)
    listing.id = _make_id(parsed.ats, parsed.company_slug, parsed.job_id)
    listing.provider = parsed.ats
    listing.data_source = "snippet"
    listing.ats_source = parsed.ats
    listing.description = None
    listing.description_ok = False
    return listing


# ---------------------------------------------------------------------------
# Greenhouse
# ---------------------------------------------------------------------------

def greenhouse_payload_to_raw(
    item: dict,
    *,
    company_slug: str,
    source_url: str | None = None,
    query_used: str = "",
    default_job_id: str | None = None,
    default_company_name: str | None = None,
    is_board_monitor: bool = False,
    company_logo_url: str | None = None,
    company_logo_source: str | None = None,
    company_logo_verified: bool = False,
) -> RawJobPosting | None:
    """
    Build a unified RawJobPosting from Greenhouse single-posting or board-list JSON.
    Guarantees parity across search pipeline, company board monitor, and direct router.
    """
    if not isinstance(item, dict):
        return None
    raw_id = item.get("id")
    provider_job_id = str(raw_id).strip() if raw_id not in (None, "") else (default_job_id or "").strip()
    if ":" in provider_job_id:
        provider_job_id = provider_job_id.split(":")[-1]
    if not provider_job_id:
        return None
    title = str(item.get("title") or "").strip()
    if not title:
        return None

    slug_lower = company_slug.strip().lower()
    raw_abs = canonicalize_recognized_greenhouse_url(str(item.get("absolute_url") or ""))
    raw_source = canonicalize_recognized_greenhouse_url(
        str(source_url or raw_abs or f"https://job-boards.greenhouse.io/{slug_lower}/jobs/{provider_job_id}")
    )
    apply_url = normalize_job_url(raw_abs or raw_source, "greenhouse") or raw_abs or raw_source
    norm_source_url = normalize_job_url(raw_source, "greenhouse") or raw_source

    company_val = item.get("company_name")
    if isinstance(company_val, str) and company_val.strip():
        company = company_val.strip()
    elif default_company_name and default_company_name.strip() and not (
        default_company_name.strip().lower() == slug_lower and default_company_name.islower()
    ):
        company = default_company_name.strip()
    else:
        company = humanize_slug(slug_lower)

    loc_obj = item.get("location")
    if isinstance(loc_obj, dict):
        location = loc_obj.get("name")
    elif isinstance(loc_obj, str) and loc_obj.strip():
        location = loc_obj.strip()
    else:
        location = None

    raw_content = item.get("content") or item.get("description")
    has_authentic_content = isinstance(raw_content, str) and bool(raw_content.strip())
    desc_to_use = raw_content if has_authentic_content else None

    raw_emp = (
        item.get("employment_type")
        or item.get("employmentType")
        or item.get("employment")
    )
    raw_date = item.get("first_published") or item.get("created_at")
    dept = _first_name(item.get("departments") or item.get("department"))

    raw_fields = dict(item)
    if is_board_monitor:
        raw_fields["is_board_monitor"] = True
    if company_logo_url:
        raw_fields["company_logo_url"] = company_logo_url
        raw_fields["company_logo_source"] = company_logo_source
        raw_fields["company_logo_verified"] = company_logo_verified

    return RawJobPosting(
        provider="greenhouse",
        source_url=norm_source_url,
        provider_job_id=provider_job_id,
        company_slug=slug_lower,
        apply_url=apply_url,
        raw_title=title,
        raw_company=company,
        raw_location=location,
        raw_department=dept,
        raw_employment_type=raw_emp,
        raw_date=raw_date,
        raw_fields=raw_fields,
        raw_description=desc_to_use,
        description_is_authentic=has_authentic_content,
        extraction_method=ExtractionMethod.ATS_API,
        query_used=query_used,
    )


class GreenhouseClient:
    """
    GET https://boards-api.greenhouse.io/v1/boards/{slug}/jobs/{job_id}
    Fields: title, location.name, updated_at, absolute_url, company_name
    """

    @with_retry(max_attempts=3, base_delay=0.5)
    async def _do_fetch(self, url: str, client: httpx.AsyncClient) -> dict:
        resp = await client.get(url, headers=browser_headers(url, "application/json,text/plain;q=0.9,*/*;q=0.8"), timeout=_TIMEOUT)
        resp.raise_for_status()
        return resp.json()

    async def fetch_raw_result(
        self,
        parsed: ParsedATSUrl,
        client: httpx.AsyncClient,
        fallback_snippet: str | None = None,
        query_used: str = "",
    ) -> ExtractionResult:
        url = (
            f"https://boards-api.greenhouse.io/v1/boards/"
            f"{parsed.company_slug}/jobs/{parsed.job_id}?pay_transparency=true"
        )
        try:
            data = await self._do_fetch(url, client)
        except httpx.HTTPStatusError as exc:
            outcome = map_status_or_exception_to_outcome(exception=exc)
            safe_err = sanitize_error_text(f"[greenhouse] HTTP error {exc.response.status_code} for {url}")
            return ExtractionResult(
                outcome=outcome,
                raw=None,
                status_code=exc.response.status_code,
                error_summary=safe_err,
                attempts=get_current_attempts(),
            )
        except Exception as exc:
            outcome = map_status_or_exception_to_outcome(exception=exc)
            safe_err = sanitize_error_text(f"[greenhouse] Unexpected error for {url}: {exc}")
            return ExtractionResult(
                outcome=outcome,
                raw=None,
                status_code=None,
                error_summary=safe_err,
                attempts=get_current_attempts(),
            )

        raw = greenhouse_payload_to_raw(
            data,
            company_slug=parsed.company_slug,
            source_url=parsed.raw_url,
            query_used=query_used,
            default_job_id=parsed.job_id,
        )
        if raw is None:
            return ExtractionResult(
                outcome=ExtractionOutcome.NOT_FOUND,
                raw=None,
                status_code=404,
                error_summary="Failed to build raw posting from Greenhouse payload",
                attempts=get_current_attempts(),
            )

        return ExtractionResult(
            outcome=ExtractionOutcome.SUCCESS,
            raw=raw,
            status_code=200,
            attempts=get_current_attempts(),
        )

    async def fetch_raw(
        self,
        parsed: ParsedATSUrl,
        client: httpx.AsyncClient,
        fallback_snippet: str | None = None,
        query_used: str = "",
    ) -> RawJobPosting | None:
        res = await self.fetch_raw_result(parsed, client, fallback_snippet, query_used)
        if res.outcome == ExtractionOutcome.NOT_FOUND:
            return None
        if res.raw is not None:
            return res.raw
        if res.status_code is not None and res.status_code != 200:
            import httpx
            raise httpx.HTTPStatusError(
                f"HTTP Error {res.status_code}",
                request=httpx.Request("GET", parsed.raw_url),
                response=httpx.Response(res.status_code),
            )
        raise RuntimeError(res.error_summary or "Greenhouse fetch failed")

    async def fetch_result(
        self,
        parsed: ParsedATSUrl,
        client: httpx.AsyncClient,
        fallback_snippet: str | None = None,
        query_used: str = "",
    ) -> tuple[JobListing | None, ExtractionResult]:
        res = await self.fetch_raw_result(parsed, client, fallback_snippet, query_used)
        if res.outcome == ExtractionOutcome.NOT_FOUND:
            return None, res
        if res.outcome == ExtractionOutcome.SUCCESS and res.raw is not None:
            canonical = JobExtractionService.extract(res.raw)
            return CanonicalJobAdapter.to_listing(canonical), res
        # Degradation to snippet fallback
        listing = _fallback(parsed, fallback_snippet, query_used)
        listing.extraction_outcome = res.outcome.value
        listing.degraded_from = "api"
        res.degraded_from = "api"
        return listing, res

    async def fetch(
        self,
        parsed: ParsedATSUrl,
        client: httpx.AsyncClient,
        fallback_snippet: str | None = None,
        query_used: str = "",
    ) -> JobListing | None:
        listing, _ = await self.fetch_result(parsed, client, fallback_snippet, query_used)
        return listing


# ---------------------------------------------------------------------------
# Lever
# ---------------------------------------------------------------------------

def _lever_normalize_overlap_text(value: str) -> str:
    """Flatten HTML/whitespace so Lever opening prefixes can be compared deterministically."""
    if not value:
        return ""
    if "<" in value:
        from bs4 import BeautifulSoup

        plain = BeautifulSoup(value, "lxml").get_text(" ", strip=True)
    else:
        plain = value
    return re.sub(r"\s+", " ", plain.replace("\xa0", " ")).strip().lower()


def _build_lever_description(data: dict) -> tuple[str | None, bool]:
    """Assemble full non-duplicated Lever description HTML/text preserving lists and additional."""
    from html import escape as html_escape

    opening_raw = (data.get("opening") or data.get("openingPlain") or "").strip()
    body_raw = (data.get("descriptionBody") or data.get("descriptionBodyPlain") or "").strip()
    full_desc_raw = (data.get("description") or data.get("descriptionPlain") or "").strip()
    additional_raw = (data.get("additional") or data.get("additionalPlain") or "").strip()

    parts: list[str] = []
    opening_norm = _lever_normalize_overlap_text(opening_raw)

    if body_raw:
        if opening_raw:
            body_norm = _lever_normalize_overlap_text(body_raw)
            if not (opening_norm and body_norm.startswith(opening_norm[:120])):
                parts.append(opening_raw)
        parts.append(body_raw)
    elif full_desc_raw:
        if opening_raw:
            full_norm = _lever_normalize_overlap_text(full_desc_raw)
            if not (opening_norm and full_norm.startswith(opening_norm[:120])):
                parts.append(opening_raw)
        parts.append(full_desc_raw)
    elif opening_raw:
        parts.append(opening_raw)

    for item in data.get("lists") or []:
        if not isinstance(item, dict):
            continue
        header = (item.get("text") or "").strip()
        content = (item.get("content") or "").strip()
        if not header and not content:
            continue
        if header:
            parts.append(f"<h3>{html_escape(header)}</h3>")
        if content:
            lower_c = content.lower()
            if "<li" in lower_c and "<ul" not in lower_c and "<ol" not in lower_c:
                parts.append(f"<ul>{content}</ul>")
            else:
                parts.append(content)

    if additional_raw:
        parts.append(additional_raw)

    combined = "\n\n".join(parts) if parts else None
    is_authentic = bool(combined and combined.strip())
    return combined, is_authentic


def _extract_lever_locations(categories: dict) -> str | None:
    """Build primary + additional unique locations string from Lever categories."""
    if not isinstance(categories, dict):
        return None
    ordered: list[str] = []
    seen_lower: set[str] = set()

    primary = categories.get("location")
    if isinstance(primary, str) and primary.strip():
        p_clean = primary.strip()
        ordered.append(p_clean)
        seen_lower.add(p_clean.lower())

    all_locs = categories.get("allLocations")
    if isinstance(all_locs, list):
        for loc in all_locs:
            if not isinstance(loc, str) or not loc.strip():
                continue
            loc_clean = loc.strip()
            if loc_clean.lower() not in seen_lower:
                ordered.append(loc_clean)
                seen_lower.add(loc_clean.lower())

    if not ordered:
        return None
    if len(ordered) == 1:
        return ordered[0]
    return "; ".join(ordered)


def lever_payload_to_raw(
    data: dict,
    *,
    company_slug: str,
    source_url: str | None = None,
    query_used: str = "",
    default_company_name: str | None = None,
    is_board_monitor: bool = False,
) -> RawJobPosting | None:
    """Shared deterministic builder mapping a Lever v0 API posting dict to RawJobPosting."""
    if not isinstance(data, dict):
        return None

    from src.project_files.url_normalizer import normalize_job_url

    job_id = str(data.get("id") or "").strip()
    title = (data.get("text") or "").strip()
    if not title and not job_id:
        return None

    hosted_url = (data.get("hostedUrl") or "").strip()
    raw_apply_url = (data.get("applyUrl") or "").strip()
    fallback_url = f"https://jobs.lever.co/{company_slug}/{job_id}" if company_slug and job_id else ""
    canonical_source = normalize_job_url(hosted_url or source_url or fallback_url, "lever")
    if not canonical_source:
        canonical_source = fallback_url or (hosted_url or source_url or "")

    apply_url = raw_apply_url or canonical_source
    company = (
        _first_name(data.get("company") or data.get("companyName"))
        or (default_company_name.strip() if isinstance(default_company_name, str) and default_company_name.strip() else None)
        or humanize_slug(company_slug)
        or "Unknown"
    )

    categories = data.get("categories") if isinstance(data.get("categories"), dict) else {}
    location = _extract_lever_locations(categories)
    commitment = categories.get("commitment")
    dept = _first_name(categories.get("team") or categories.get("department"))
    workplace_type = data.get("workplaceType") or data.get("workplace_type")
    combined_desc, is_authentic = _build_lever_description(data)
    raw_fields = dict(data)
    if is_board_monitor:
        raw_fields["is_board_monitor"] = True

    return RawJobPosting(
        provider="lever",
        source_url=canonical_source,
        provider_job_id=job_id or None,
        company_slug=company_slug,
        apply_url=apply_url,
        raw_title=title,
        raw_company=company,
        raw_location=location,
        raw_workplace_type=workplace_type,
        raw_department=dept,
        raw_employment_type=commitment,
        raw_date=data.get("createdAt"),
        raw_fields=raw_fields,
        raw_description=combined_desc,
        description_is_authentic=is_authentic,
        query_used=query_used,
    )


_LEVER_IDENTITY_INFLIGHT: dict[tuple[int, str, int], asyncio.Task] = {}


def _extract_lever_board_company_name(soup: BeautifulSoup) -> str | None:
    title_tag = soup.find("title")
    if title_tag is not None:
        raw_title = title_tag.get_text(" ", strip=True)
        cleaned = re.sub(r"\s*(?:-|\||–)\s*(?:Careers|Jobs|Open Positions|Lever)\s*$", "", raw_title, flags=re.IGNORECASE).strip()
        if cleaned and cleaned.lower() not in {"lever", "jobs", "careers", "404", "not found"}:
            return cleaned
    header_img = soup.select_one("a.main-header-logo img, .main-header-logo img")
    if header_img is not None:
        alt_text = (header_img.get("alt") or "").strip()
        alt_cleaned = re.sub(r"\s+logo\s*$", "", alt_text, flags=re.IGNORECASE).strip()
        if alt_cleaned and alt_cleaned.lower() not in {"lever", "logo"}:
            return alt_cleaned
    return None


async def enrich_lever_board_identity(
    company_slug: str,
    client: httpx.AsyncClient,
    *,
    registry: CompanyBoardRegistry | None = None,
    ttl_seconds: int = 7 * 86400,
) -> tuple[str | None, LogoResult]:
    """
    Bounded Lever board-page identity enrichment (company name + verified logo)
    with negative caching and per-slug concurrency coalescing.
    """
    slug = (company_slug or "").strip()
    slug_lower = slug.lower()
    if not slug or "/" in slug or "?" in slug or not is_valid_board_slug("lever", slug_lower):
        return None, LogoResult()

    target_reg = registry or company_board_registry
    now = time.time()
    board = target_reg.get_board("lever", slug_lower)
    if board is not None:
        checked_ts = board.company_logo_checked_at or board.company_logo_updated_at
        if board.company_logo_url and board.company_logo_verified:
            if checked_ts is None or (now - checked_ts) < ttl_seconds:
                return board.company_name, LogoResult(
                    url=board.company_logo_url,
                    source=board.company_logo_source,
                    raw_value=board.company_logo_url,
                    verified=True,
                )
        elif board.company_logo_checked_at is not None and (now - board.company_logo_checked_at) < ttl_seconds:
            return board.company_name, LogoResult()

    loop = asyncio.get_running_loop()
    inflight_key = (id(loop), slug_lower, id(target_reg))
    existing_task = _LEVER_IDENTITY_INFLIGHT.get(inflight_key)
    if existing_task is not None:
        return await existing_task

    async def _fetch_identity() -> tuple[str | None, LogoResult]:
        board_url = f"https://jobs.lever.co/{slug}"
        try:
            resp = await client.get(
                board_url,
                headers=browser_headers(board_url, "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8"),
                timeout=min(float(settings.ats_request_timeout_seconds), 8.0),
            )
        except Exception as exc:
            logger.debug(f"[lever] Board identity fetch failed for {slug_lower}: {exc}")
            existing_logo = (
                LogoResult(
                    url=board.company_logo_url,
                    source=board.company_logo_source,
                    raw_value=board.company_logo_url,
                    verified=bool(board.company_logo_verified),
                )
                if board and board.company_logo_url
                else LogoResult()
            )
            return (board.company_name if board else None), existing_logo

        if resp.status_code != 200:
            if resp.status_code in (404, 410):
                target_reg.set_board_identity(
                    ats_provider="lever",
                    board_token=slug_lower,
                    board_url=f"https://jobs.lever.co/{slug_lower}",
                )
            existing_logo = (
                LogoResult(
                    url=board.company_logo_url,
                    source=board.company_logo_source,
                    raw_value=board.company_logo_url,
                    verified=bool(board.company_logo_verified),
                )
                if board and board.company_logo_url
                else LogoResult()
            )
            return (board.company_name if board else None), existing_logo

        content_type = (resp.headers.get("content-type") or "").lower()
        body_text = resp.text or ""
        if "json" in content_type or not body_text.lstrip().startswith("<"):
            return (board.company_name if board else None), LogoResult()

        soup = BeautifulSoup(body_text, "lxml")
        extracted_name = _extract_lever_board_company_name(soup)
        logo_res = extract_company_logo_for_provider(
            "lever",
            soup=soup,
            page_url=board_url,
            company_name=extracted_name or (board.company_name if board else None),
        )
        updated = target_reg.set_board_identity(
            ats_provider="lever",
            board_token=slug_lower,
            company_name=extracted_name,
            logo_url=logo_res.url,
            logo_source=logo_res.source,
            logo_verified=logo_res.verified,
            board_url=f"https://jobs.lever.co/{slug_lower}",
        )
        final_name = extracted_name or (updated.company_name if updated else (board.company_name if board else None))
        if logo_res.url:
            return final_name, logo_res
        if board and board.company_logo_url and board.company_logo_verified:
            return final_name, LogoResult(
                url=board.company_logo_url,
                source=board.company_logo_source,
                raw_value=board.company_logo_url,
                verified=True,
            )
        return final_name, LogoResult()

    task = asyncio.create_task(_fetch_identity())
    _LEVER_IDENTITY_INFLIGHT[inflight_key] = task
    try:
        return await task
    finally:
        if _LEVER_IDENTITY_INFLIGHT.get(inflight_key) is task:
            _LEVER_IDENTITY_INFLIGHT.pop(inflight_key, None)


_GREENHOUSE_IDENTITY_INFLIGHT: dict[tuple[int, str, int], asyncio.Task[tuple[str | None, LogoResult]]] = {}


def _extract_greenhouse_board_company_name(soup: BeautifulSoup, slug: str) -> str | None:
    name: str | None = None
    title_tag = soup.find("title")
    if title_tag:
        t_text = title_tag.get_text(strip=True)
        m_title = re.search(r"Jobs\s+at\s+([^\n\-–|]+)", t_text, re.IGNORECASE)
        if m_title:
            name = m_title.group(1).strip()
        else:
            m_title_dash = re.search(r"^([^\n\-–|]+?)\s*[-–|]\s*Jobs", t_text, re.IGNORECASE)
            if m_title_dash:
                name = m_title_dash.group(1).strip()

    if not name:
        h1_tag = soup.find("h1")
        if h1_tag:
            h_text = h1_tag.get_text(strip=True)
            m_h = re.search(r"Current\s+openings\s+at\s+([^\n\-–|]+)", h_text, re.IGNORECASE)
            if m_h:
                name = m_h.group(1).strip()

    if not name:
        name = humanize_slug(slug)

    # Strip internal board suffixes like "_managed_posts", "_jobs", "_careers"
    name = re.sub(r"[_ -]managed[_ -]posts?\b", "", name, flags=re.IGNORECASE).strip()
    name = re.sub(r"[_ -]jobs\b", "", name, flags=re.IGNORECASE).strip()
    name = re.sub(r"[_ -]careers\b", "", name, flags=re.IGNORECASE).strip()
    return name or humanize_slug(slug)


async def enrich_greenhouse_board_identity(
    company_slug: str,
    client: httpx.AsyncClient,
    *,
    registry: CompanyBoardRegistry | None = None,
    ttl_seconds: int = 7 * 86400,
) -> tuple[str | None, LogoResult]:
    """
    Bounded Greenhouse board-page identity enrichment (company name + verified logo)
    with negative caching and per-slug concurrency coalescing.
    Normalizes polluted slug variants like 'canonical_managed_posts' -> 'Canonical'.
    """
    slug = (company_slug or "").strip()
    slug_lower = slug.lower()
    if not slug or "/" in slug or "?" in slug or not is_valid_board_slug("greenhouse", slug_lower):
        return None, LogoResult()

    target_reg = registry or company_board_registry
    now = time.time()
    board = target_reg.get_board("greenhouse", slug_lower)
    if board is not None:
        checked_ts = board.company_logo_checked_at or board.company_logo_updated_at
        if board.company_logo_url and board.company_logo_verified:
            if checked_ts is None or (now - checked_ts) < ttl_seconds:
                return board.company_name, LogoResult(
                    url=board.company_logo_url,
                    source=board.company_logo_source,
                    raw_value=board.company_logo_url,
                    verified=True,
                )
        elif board.company_logo_checked_at is not None and (now - board.company_logo_checked_at) < ttl_seconds:
            return board.company_name, LogoResult()

    loop = asyncio.get_running_loop()
    inflight_key = (id(loop), slug_lower, id(target_reg))
    existing_task = _GREENHOUSE_IDENTITY_INFLIGHT.get(inflight_key)
    if existing_task is not None:
        return await existing_task

    async def _fetch_identity() -> tuple[str | None, LogoResult]:
        board_url = f"https://job-boards.greenhouse.io/{slug_lower}"
        try:
            resp = await client.get(
                board_url,
                headers=browser_headers(board_url, "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8"),
                timeout=min(float(settings.ats_request_timeout_seconds), 8.0),
            )
        except Exception as exc:
            logger.debug(f"[greenhouse] Board identity fetch failed for {slug_lower}: {exc}")
            existing_logo = (
                LogoResult(
                    url=board.company_logo_url,
                    source=board.company_logo_source,
                    raw_value=board.company_logo_url,
                    verified=bool(board.company_logo_verified),
                )
                if board and board.company_logo_url
                else LogoResult()
            )
            return (board.company_name if board else None), existing_logo

        if resp.status_code != 200:
            existing_logo = (
                LogoResult(
                    url=board.company_logo_url,
                    source=board.company_logo_source,
                    raw_value=board.company_logo_url,
                    verified=bool(board.company_logo_verified),
                )
                if board and board.company_logo_url
                else LogoResult()
            )
            return (board.company_name if board else None), existing_logo

        content_type = (resp.headers.get("content-type") or "").lower()
        body_text = resp.text or ""
        if "json" in content_type or not body_text.lstrip().startswith("<"):
            return (board.company_name if board else None), LogoResult()

        soup = BeautifulSoup(body_text, "html.parser")
        extracted_name = _extract_greenhouse_board_company_name(soup, slug_lower)
        logo_res = extract_company_logo_for_provider(
            "greenhouse",
            soup=soup,
            page_url=board_url,
            company_name=extracted_name or (board.company_name if board else None),
        )
        updated = target_reg.set_board_identity(
            ats_provider="greenhouse",
            board_token=slug_lower,
            company_name=extracted_name,
            logo_url=logo_res.url,
            logo_source=logo_res.source,
            logo_verified=logo_res.verified,
            board_url=f"https://job-boards.greenhouse.io/{slug_lower}",
        )
        final_name = extracted_name or (updated.company_name if updated else (board.company_name if board else None))
        if logo_res.url:
            return final_name, logo_res
        if board and board.company_logo_url and board.company_logo_verified:
            return final_name, LogoResult(
                url=board.company_logo_url,
                source=board.company_logo_source,
                raw_value=board.company_logo_url,
                verified=True,
            )
        return final_name, LogoResult()

    task = asyncio.create_task(_fetch_identity())
    _GREENHOUSE_IDENTITY_INFLIGHT[inflight_key] = task
    try:
        return await task
    finally:
        if _GREENHOUSE_IDENTITY_INFLIGHT.get(inflight_key) is task:
            _GREENHOUSE_IDENTITY_INFLIGHT.pop(inflight_key, None)


class LeverClient:
    """
    GET https://api.lever.co/v0/postings/{slug}/{job_id}
    Fields: text, categories.location, categories.commitment, createdAt (ms), applyUrl
    """

    @with_retry(max_attempts=3, base_delay=0.5)
    async def _do_fetch(self, url: str, client: httpx.AsyncClient) -> dict:
        resp = await client.get(url, headers=browser_headers(url, "application/json,text/plain;q=0.9,*/*;q=0.8"), timeout=_TIMEOUT)
        resp.raise_for_status()
        return resp.json()

    async def fetch_raw_result(
        self,
        parsed: ParsedATSUrl,
        client: httpx.AsyncClient,
        fallback_snippet: str | None = None,
        query_used: str = "",
    ) -> ExtractionResult:
        url = f"https://api.lever.co/v0/postings/{parsed.company_slug}/{parsed.job_id}"
        try:
            data = await self._do_fetch(url, client)
        except httpx.HTTPStatusError as exc:
            outcome = map_status_or_exception_to_outcome(exception=exc)
            safe_err = sanitize_error_text(f"[lever] HTTP error {exc.response.status_code} for {url}")
            return ExtractionResult(
                outcome=outcome,
                raw=None,
                status_code=exc.response.status_code,
                error_summary=safe_err,
                attempts=get_current_attempts(),
            )
        except Exception as exc:
            outcome = map_status_or_exception_to_outcome(exception=exc)
            safe_err = sanitize_error_text(f"[lever] Unexpected error for {url}: {exc}")
            return ExtractionResult(
                outcome=outcome,
                raw=None,
                status_code=None,
                error_summary=safe_err,
                attempts=get_current_attempts(),
            )

        raw = lever_payload_to_raw(
            data,
            company_slug=parsed.company_slug,
            source_url=parsed.raw_url,
            query_used=query_used,
        )
        if raw is None:
            return ExtractionResult(
                outcome=ExtractionOutcome.PARSE_FAILURE,
                raw=None,
                status_code=200,
                error_summary=sanitize_error_text(f"[lever] Invalid payload shape for {url}"),
                attempts=get_current_attempts(),
            )
        if not raw.raw_fields.get("company_logo_url"):
            try:
                board_name, logo_res = await enrich_lever_board_identity(parsed.company_slug, client)
                if board_name and (
                    not raw.raw_company
                    or raw.raw_company == "Unknown"
                    or raw.raw_company == humanize_slug(parsed.company_slug)
                ):
                    raw.raw_company = board_name
                if logo_res.url and logo_res.verified:
                    raw.raw_fields["company_logo_url"] = logo_res.url
                    raw.raw_fields["company_logo_source"] = logo_res.source
                    raw.raw_fields["company_logo_verified"] = True
            except Exception as exc:
                logger.debug(f"[lever] Optional board identity enrichment failed for {parsed.company_slug}: {exc}")
        return ExtractionResult(
            outcome=ExtractionOutcome.SUCCESS,
            raw=raw,
            status_code=200,
            attempts=get_current_attempts(),
        )

    async def fetch_raw(
        self,
        parsed: ParsedATSUrl,
        client: httpx.AsyncClient,
        fallback_snippet: str | None = None,
        query_used: str = "",
    ) -> RawJobPosting | None:
        res = await self.fetch_raw_result(parsed, client, fallback_snippet, query_used)
        if res.outcome == ExtractionOutcome.NOT_FOUND:
            return None
        if res.raw is not None:
            return res.raw
        if res.status_code is not None and res.status_code != 200:
            import httpx
            raise httpx.HTTPStatusError(
                f"HTTP Error {res.status_code}",
                request=httpx.Request("GET", parsed.raw_url),
                response=httpx.Response(res.status_code),
            )
        raise RuntimeError(res.error_summary or "Lever fetch failed")

    async def fetch_result(
        self,
        parsed: ParsedATSUrl,
        client: httpx.AsyncClient,
        fallback_snippet: str | None = None,
        query_used: str = "",
    ) -> tuple[JobListing | None, ExtractionResult]:
        res = await self.fetch_raw_result(parsed, client, fallback_snippet, query_used)
        if res.outcome == ExtractionOutcome.NOT_FOUND:
            return None, res
        if res.outcome == ExtractionOutcome.SUCCESS and res.raw is not None:
            canonical = JobExtractionService.extract(res.raw)
            return CanonicalJobAdapter.to_listing(canonical), res
        listing = _fallback(parsed, fallback_snippet, query_used)
        listing.extraction_outcome = res.outcome.value
        listing.degraded_from = "api"
        res.degraded_from = "api"
        return listing, res

    async def fetch(
        self,
        parsed: ParsedATSUrl,
        client: httpx.AsyncClient,
        fallback_snippet: str | None = None,
        query_used: str = "",
    ) -> JobListing | None:
        listing, _ = await self.fetch_result(parsed, client, fallback_snippet, query_used)
        return listing


# ---------------------------------------------------------------------------
# Ashby
# ---------------------------------------------------------------------------


def _extract_ashby_locations(data: dict) -> str | None:
    """Build primary + deduplicated secondary locations string from an Ashby posting dict."""
    if not isinstance(data, dict):
        return None
    ordered: list[str] = []
    seen_lower: set[str] = set()

    primary = data.get("location") or data.get("locationName")
    if isinstance(primary, str) and primary.strip():
        p_clean = re.sub(r"\s+", " ", primary).strip()
        ordered.append(p_clean)
        seen_lower.add(p_clean.lower())

    secondary = data.get("secondaryLocations")
    if isinstance(secondary, list):
        for item in secondary:
            loc_str: str | None = None
            if isinstance(item, dict):
                loc_str = item.get("location") or item.get("locationName")
                if not loc_str and isinstance(item.get("address"), dict):
                    postal = item["address"].get("postalAddress")
                    if isinstance(postal, dict):
                        parts = [
                            postal.get(k).strip()
                            for k in ("addressLocality", "addressRegion", "addressCountry")
                            if isinstance(postal.get(k), str) and postal.get(k).strip()
                        ]
                        if parts:
                            loc_str = ", ".join(parts)
            elif isinstance(item, str):
                loc_str = item
            if isinstance(loc_str, str) and loc_str.strip():
                loc_clean = re.sub(r"\s+", " ", loc_str).strip()
                if loc_clean.lower() not in seen_lower:
                    ordered.append(loc_clean)
                    seen_lower.add(loc_clean.lower())

    if not ordered:
        return None
    if len(ordered) == 1:
        return ordered[0]
    return "; ".join(ordered)


def ashby_payload_to_raw(
    data: dict,
    *,
    company_slug: str,
    source_url: str | None = None,
    query_used: str = "",
    default_job_id: str | None = None,
    default_company_name: str | None = None,
    is_board_monitor: bool = False,
    company_logo_url: str | None = None,
    company_logo_source: str | None = None,
    company_logo_verified: bool = False,
) -> RawJobPosting | None:
    """
    Build a unified RawJobPosting from an Ashby public posting dict.
    Guarantees parity across AshbyClient, AshbyBoardAdapter, probe_ashby_board, and cache repair.
    """
    if not isinstance(data, dict):
        return None

    raw_id = data.get("id")
    job_id = str(raw_id).strip().lower() if raw_id not in (None, "") else (default_job_id or "").strip().lower()
    title = str(data.get("title") or "").strip()
    if not title and not job_id:
        return None

    clean_slug = company_slug.strip()
    encoded_slug = quote(clean_slug, safe="-_.~")
    fallback_url = f"https://jobs.ashbyhq.com/{encoded_slug}/{job_id}" if clean_slug and job_id else ""
    raw_job_url = str(data.get("jobUrl") or "").strip()
    raw_apply_url = str(data.get("applyUrl") or "").strip()
    canonical_source = (
        normalize_job_url(source_url or raw_job_url or fallback_url, "ashby")
        or fallback_url
        or raw_job_url
        or (source_url or "")
    )
    apply_url = raw_apply_url or canonical_source

    company_val = _first_name(data.get("company") or data.get("companyName"))
    if company_val:
        company = company_val
    elif default_company_name and default_company_name.strip() and not (
        default_company_name.strip().lower() == clean_slug.lower() and default_company_name.islower()
    ):
        company = default_company_name.strip()
    else:
        company = humanize_slug(clean_slug) or "Unknown"

    location = _extract_ashby_locations(data)
    employment_raw = data.get("employmentType")
    # ADR 0002: workplaceType is the authoritative API enum; never treat isRemote=True as Remote override.
    raw_workplace_type = data.get("workplaceType") or data.get("workplaceTypeName")
    raw_desc = data.get("descriptionHtml") or data.get("descriptionPlain") or data.get("description")
    has_authentic = isinstance(raw_desc, str) and bool(raw_desc.strip())
    desc_to_use = raw_desc if has_authentic else None
    raw_date = data.get("publishedAt")
    dept = data.get("departmentName") or _first_name(data.get("department"))

    raw_fields = dict(data)
    if is_board_monitor:
        raw_fields["is_board_monitor"] = True
    if company_logo_url:
        raw_fields["company_logo_url"] = company_logo_url
        raw_fields["company_logo_source"] = company_logo_source
        raw_fields["company_logo_verified"] = company_logo_verified

    return RawJobPosting(
        provider="ashby",
        source_url=canonical_source,
        provider_job_id=job_id or None,
        company_slug=clean_slug,
        apply_url=apply_url,
        raw_title=title,
        raw_company=company,
        raw_location=location,
        raw_workplace_type=raw_workplace_type,
        raw_department=dept,
        raw_employment_type=employment_raw,
        raw_date=raw_date,
        raw_fields=raw_fields,
        raw_description=desc_to_use,
        description_is_authentic=has_authentic,
        extraction_method=ExtractionMethod.ATS_API,
        query_used=query_used,
    )


_ASHBY_IDENTITY_INFLIGHT: dict[tuple[int, str, int], asyncio.Task[tuple[str | None, LogoResult]]] = {}


async def enrich_ashby_board_identity(
    company_slug: str,
    client: httpx.AsyncClient,
    *,
    registry: CompanyBoardRegistry | None = None,
    ttl_seconds: int = 7 * 86400,
) -> tuple[str | None, LogoResult]:
    """
    Bounded Ashby board-page identity enrichment (company name from window.__appData.organization.name
    + verified square logo from organization.theme.logoSquareImageUrl) with negative caching and
    per-slug concurrency coalescing.
    """
    slug = (company_slug or "").strip()
    slug_lower = slug.lower()
    if not slug or "/" in slug or "?" in slug or not is_valid_board_slug("ashby", slug):
        return None, LogoResult()

    target_reg = registry or company_board_registry
    now = time.time()
    board = target_reg.get_board("ashby", slug_lower)
    if board is not None:
        checked_ts = board.company_logo_checked_at or board.company_logo_updated_at
        if board.company_logo_url and board.company_logo_verified:
            if checked_ts is None or (now - checked_ts) < ttl_seconds:
                return board.company_name, LogoResult(
                    url=board.company_logo_url,
                    source=board.company_logo_source,
                    raw_value=board.company_logo_url,
                    verified=True,
                )
        elif board.company_logo_checked_at is not None and (now - board.company_logo_checked_at) < ttl_seconds:
            return board.company_name, LogoResult()

    loop = asyncio.get_running_loop()
    inflight_key = (id(loop), slug_lower, id(target_reg))
    existing_task = _ASHBY_IDENTITY_INFLIGHT.get(inflight_key)
    if existing_task is not None:
        return await existing_task

    async def _fetch_identity() -> tuple[str | None, LogoResult]:
        encoded_slug = quote(slug, safe="-_.~")
        board_url = f"https://jobs.ashbyhq.com/{encoded_slug}"
        headers = {
            **browser_headers(board_url, "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8"),
            "Accept-Encoding": "gzip, deflate",
        }
        try:
            resp = await client.get(
                board_url,
                headers=headers,
                timeout=min(float(settings.ats_request_timeout_seconds), 8.0),
            )
        except Exception as exc:
            logger.debug(f"[ashby] Board identity fetch failed for {slug_lower}: {exc}")
            existing_logo = (
                LogoResult(
                    url=board.company_logo_url,
                    source=board.company_logo_source,
                    raw_value=board.company_logo_url,
                    verified=bool(board.company_logo_verified),
                )
                if board and board.company_logo_url
                else LogoResult()
            )
            return (board.company_name if board else None), existing_logo

        if resp.status_code != 200:
            existing_logo = (
                LogoResult(
                    url=board.company_logo_url,
                    source=board.company_logo_source,
                    raw_value=board.company_logo_url,
                    verified=bool(board.company_logo_verified),
                )
                if board and board.company_logo_url
                else LogoResult()
            )
            return (board.company_name if board else None), existing_logo

        content_type = (resp.headers.get("content-type") or "").lower()
        body_text = resp.text or ""
        if "json" in content_type or not body_text.lstrip().startswith("<"):
            return (board.company_name if board else None), LogoResult()

        soup = BeautifulSoup(body_text, "html.parser")
        app_data = extract_ashby_app_data_from_soup(soup)
        extracted_name: str | None = None
        if isinstance(app_data, dict):
            org_obj = app_data.get("organization")
            if isinstance(org_obj, dict) and isinstance(org_obj.get("name"), str) and org_obj["name"].strip():
                extracted_name = org_obj["name"].strip()

        logo_res = extract_company_logo_for_provider(
            "ashby",
            soup=soup,
            page_url=board_url,
            company_name=extracted_name or (board.company_name if board else None),
        )
        updated = target_reg.set_board_identity(
            ats_provider="ashby",
            board_token=slug_lower,
            company_name=extracted_name,
            logo_url=logo_res.url,
            logo_source=logo_res.source,
            logo_verified=logo_res.verified,
            board_url=board_url,
        )
        final_name = extracted_name or (updated.company_name if updated else (board.company_name if board else None))
        if logo_res.url:
            return final_name, logo_res
        if board and board.company_logo_url and board.company_logo_verified:
            return final_name, LogoResult(
                url=board.company_logo_url,
                source=board.company_logo_source,
                raw_value=board.company_logo_url,
                verified=True,
            )
        return final_name, LogoResult()

    task = asyncio.create_task(_fetch_identity())
    _ASHBY_IDENTITY_INFLIGHT[inflight_key] = task
    try:
        return await task
    finally:
        if _ASHBY_IDENTITY_INFLIGHT.get(inflight_key) is task:
            _ASHBY_IDENTITY_INFLIGHT.pop(inflight_key, None)


class AshbyClient:
    """
    GET https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true
    Fields: title, location, secondaryLocations, address, workplaceType, compensation, descriptionHtml, applyUrl
    """

    @with_retry(max_attempts=3, base_delay=0.5)
    async def _do_fetch(self, url: str, client: httpx.AsyncClient) -> dict:
        headers = {
            **browser_headers(url, "application/json,text/plain;q=0.9,*/*;q=0.8"),
            "Accept-Encoding": "gzip, deflate",
        }
        resp = await client.get(url, headers=headers, timeout=_TIMEOUT)
        resp.raise_for_status()
        return resp.json()

    async def fetch_raw_result(
        self,
        parsed: ParsedATSUrl,
        client: httpx.AsyncClient,
        fallback_snippet: str | None = None,
        query_used: str = "",
    ) -> ExtractionResult:
        encoded_slug = quote(parsed.company_slug, safe="-_.~")
        url = f"https://api.ashbyhq.com/posting-api/job-board/{encoded_slug}?includeCompensation=true"
        try:
            data = await self._do_fetch(url, client)
        except httpx.HTTPStatusError as exc:
            outcome = map_status_or_exception_to_outcome(exception=exc)
            safe_err = sanitize_error_text(f"[ashby] HTTP error {exc.response.status_code} for {url}")
            return ExtractionResult(
                outcome=outcome,
                raw=None,
                status_code=exc.response.status_code,
                error_summary=safe_err,
                attempts=get_current_attempts(),
            )
        except Exception as exc:
            outcome = map_status_or_exception_to_outcome(exception=exc)
            safe_err = sanitize_error_text(f"[ashby] Unexpected error for {url}: {exc}")
            return ExtractionResult(
                outcome=outcome,
                raw=None,
                status_code=None,
                error_summary=safe_err,
                attempts=get_current_attempts(),
            )

        if isinstance(data, dict) and "jobs" in data:
            target = str(parsed.job_id).strip().lower()
            matched = next(
                (j for j in data["jobs"] if str(j.get("id") or "").strip().lower() == target),
                None,
            )
            if matched is None:
                return ExtractionResult(
                    outcome=ExtractionOutcome.NOT_FOUND,
                    raw=None,
                    status_code=404,
                    error_summary=f"[ashby] Job ID {parsed.job_id} not found in board list",
                    attempts=get_current_attempts(),
                )
            data = matched

        raw = ashby_payload_to_raw(
            data,
            company_slug=parsed.company_slug,
            source_url=parsed.raw_url,
            default_job_id=parsed.job_id,
            query_used=query_used,
        )
        if raw is None:
            return ExtractionResult(
                outcome=ExtractionOutcome.PARSE_FAILURE,
                raw=None,
                status_code=200,
                error_summary=sanitize_error_text(f"[ashby] Invalid payload shape for {url}"),
                attempts=get_current_attempts(),
            )
        return ExtractionResult(
            outcome=ExtractionOutcome.SUCCESS,
            raw=raw,
            status_code=200,
            attempts=get_current_attempts(),
        )

    async def fetch_raw(
        self,
        parsed: ParsedATSUrl,
        client: httpx.AsyncClient,
        fallback_snippet: str | None = None,
        query_used: str = "",
    ) -> RawJobPosting | None:
        res = await self.fetch_raw_result(parsed, client, fallback_snippet, query_used)
        if res.outcome == ExtractionOutcome.NOT_FOUND:
            return None
        if res.raw is not None:
            return res.raw
        if res.status_code is not None and res.status_code != 200:
            import httpx
            raise httpx.HTTPStatusError(
                f"HTTP Error {res.status_code}",
                request=httpx.Request("GET", parsed.raw_url),
                response=httpx.Response(res.status_code),
            )
        raise RuntimeError(res.error_summary or "Ashby fetch failed")

    async def fetch_result(
        self,
        parsed: ParsedATSUrl,
        client: httpx.AsyncClient,
        fallback_snippet: str | None = None,
        query_used: str = "",
    ) -> tuple[JobListing | None, ExtractionResult]:
        res = await self.fetch_raw_result(parsed, client, fallback_snippet, query_used)
        if res.outcome == ExtractionOutcome.NOT_FOUND:
            return None, res
        if res.outcome == ExtractionOutcome.SUCCESS and res.raw is not None:
            if not res.raw.raw_fields.get("company_logo_url"):
                try:
                    board_name, logo_res = await enrich_ashby_board_identity(parsed.company_slug, client)
                    if board_name and (
                        not res.raw.raw_company
                        or res.raw.raw_company in ("Unknown", parsed.company_slug, humanize_slug(parsed.company_slug))
                    ):
                        res.raw.raw_company = board_name
                    if logo_res.url and logo_res.verified:
                        res.raw.raw_fields["company_logo_url"] = logo_res.url
                        res.raw.raw_fields["company_logo_source"] = logo_res.source
                        res.raw.raw_fields["company_logo_verified"] = True
                except Exception as exc:
                    logger.debug(f"[ashby] Optional board identity enrichment failed for {parsed.company_slug}: {exc}")
            canonical = JobExtractionService.extract(res.raw)
            return CanonicalJobAdapter.to_listing(canonical), res
        listing = _fallback(parsed, fallback_snippet, query_used)
        listing.extraction_outcome = res.outcome.value
        listing.degraded_from = "api"
        res.degraded_from = "api"
        return listing, res

    async def fetch(
        self,
        parsed: ParsedATSUrl,
        client: httpx.AsyncClient,
        fallback_snippet: str | None = None,
        query_used: str = "",
    ) -> JobListing | None:
        listing, _ = await self.fetch_result(parsed, client, fallback_snippet, query_used)
        return listing


# ---------------------------------------------------------------------------
# SmartRecruiters
# ---------------------------------------------------------------------------

class SmartRecruitersClient:
    """
    GET https://api.smartrecruiters.com/v1/companies/{slug}/postings/{job_id}
    Fields: name, location.city, location.remote, releasedDate, ref
    """

    @with_retry(max_attempts=3, base_delay=0.5)
    async def _do_fetch(self, url: str, client: httpx.AsyncClient) -> dict:
        resp = await client.get(url, headers=browser_headers(url, "application/json,text/plain;q=0.9,*/*;q=0.8"), timeout=_TIMEOUT)
        resp.raise_for_status()
        return resp.json()

    def _parse_raw_payload(
        self,
        data: dict,
        parsed: ParsedATSUrl,
        query_used: str = "",
    ) -> RawJobPosting:
        title = data.get("name", "")
        loc_data = data.get("location") or {}
        raw_loc = loc_data.get("fullLocation") or loc_data.get("city")
        location: str | None = None
        if raw_loc:
            cleaned_loc = re.sub(r",\s*,+", ",", str(raw_loc))
            cleaned_loc = re.sub(r"\s+", " ", cleaned_loc)
            parts = [p.strip() for p in cleaned_loc.split(",") if p.strip()]
            location = ", ".join(parts) if parts else None

        is_remote_flag = loc_data.get("remote")
        is_hybrid_flag = loc_data.get("hybrid")
        raw_workplace_type = f"remote={is_remote_flag},hybrid={is_hybrid_flag}"

        if is_hybrid_flag is True:
            workplace_type = "hybrid"
            workplace_type_resolved = True
            work_model_evidence = raw_workplace_type
        elif is_remote_flag is True:
            workplace_type = "remote"
            workplace_type_resolved = True
            work_model_evidence = raw_workplace_type
        elif is_remote_flag is False and is_hybrid_flag is False:
            workplace_type = None
            workplace_type_resolved = True
            work_model_evidence = None
        else:
            workplace_type = None
            workplace_type_resolved = False
            work_model_evidence = None

        job_desc_sec = (data.get("jobAd") or {}).get("sections") or {}
        section_order = ["companyDescription", "jobDescription", "qualifications", "additionalInformation"]
        sections_content: list[str] = []
        raw_requirements: str | None = None

        for sec_key in section_order:
            sec = job_desc_sec.get(sec_key)
            if isinstance(sec, dict):
                sec_title = sec.get("title") or sec_key.replace("Description", " Description").title()
                sec_text = sec.get("text") or ""
                if sec_text.strip():
                    if sec_key == "qualifications":
                        raw_requirements = sec_text
                    sections_content.append(f"### {sec_title}\n\n{sec_text}")

        for sec_key, sec in job_desc_sec.items():
            if sec_key not in section_order and isinstance(sec, dict):
                sec_title = sec.get("title") or sec_key
                sec_text = sec.get("text") or ""
                if sec_text.strip():
                    sections_content.append(f"### {sec_title}\n\n{sec_text}")

        if sections_content:
            raw_desc = "\n\n".join(sections_content)
        else:
            raw_desc = data.get("jobDescription") or ""

        company = (
            _first_name(data.get("company") or data.get("companyName") or data.get("organization"))
            or humanize_slug(parsed.company_slug)
            or "Unknown"
        )
        apply_url = data.get("ref") or parsed.raw_url
        raw_date = data.get("releasedDate")
        dept = _first_name(data.get("function") or data.get("department"))
        raw_emp = data.get("typeOfEmployment")

        comp = data.get("compensation")
        raw_salary_str: str | None = None
        if isinstance(comp, dict):
            raw_salary_str = f"{comp.get('currency', '')} {comp.get('min', '')} - {comp.get('max', '')} {comp.get('period', '')}".strip()

        return RawJobPosting(
            provider="smartrecruiters",
            source_url=parsed.raw_url,
            provider_job_id=parsed.job_id,
            company_slug=parsed.company_slug,
            apply_url=apply_url,
            raw_title=title,
            raw_company=company,
            raw_location=location,
            raw_workplace_type=raw_workplace_type,
            workplace_type=workplace_type,
            workplace_type_resolved=workplace_type_resolved,
            work_model_evidence=work_model_evidence,
            raw_department=dept,
            raw_employment_type=_first_name(raw_emp),
            raw_salary=raw_salary_str,
            raw_date=raw_date,
            raw_fields=data,
            raw_description=raw_desc,
            raw_requirements=raw_requirements,
            description_is_authentic=True,
            query_used=query_used,
        )

    async def fetch_raw_result(
        self,
        parsed: ParsedATSUrl,
        client: httpx.AsyncClient,
        fallback_snippet: str | None = None,
        query_used: str = "",
    ) -> ExtractionResult:
        url = (
            f"https://api.smartrecruiters.com/v1/companies/"
            f"{parsed.company_slug}/postings/{parsed.job_id}"
        )
        try:
            data = await self._do_fetch(url, client)
        except httpx.HTTPStatusError as exc:
            outcome = map_status_or_exception_to_outcome(exception=exc)
            safe_err = sanitize_error_text(f"[smartrecruiters] HTTP error {exc.response.status_code} for {url}")
            return ExtractionResult(
                outcome=outcome,
                raw=None,
                status_code=exc.response.status_code,
                error_summary=safe_err,
                attempts=get_current_attempts(),
            )
        except Exception as exc:
            outcome = map_status_or_exception_to_outcome(exception=exc)
            safe_err = sanitize_error_text(f"[smartrecruiters] Unexpected error for {url}: {exc}")
            return ExtractionResult(
                outcome=outcome,
                raw=None,
                status_code=None,
                error_summary=safe_err,
                attempts=get_current_attempts(),
            )

        raw = self._parse_raw_payload(data, parsed, query_used=query_used)
        return ExtractionResult(
            outcome=ExtractionOutcome.SUCCESS,
            raw=raw,
            status_code=200,
            attempts=get_current_attempts(),
        )

    async def fetch_raw(
        self,
        parsed: ParsedATSUrl,
        client: httpx.AsyncClient,
        fallback_snippet: str | None = None,
        query_used: str = "",
    ) -> RawJobPosting | None:
        res = await self.fetch_raw_result(parsed, client, fallback_snippet, query_used)
        if res.outcome == ExtractionOutcome.NOT_FOUND:
            return None
        if res.raw is not None:
            return res.raw
        if res.status_code is not None and res.status_code != 200:
            import httpx
            raise httpx.HTTPStatusError(
                f"HTTP Error {res.status_code}",
                request=httpx.Request("GET", parsed.raw_url),
                response=httpx.Response(res.status_code),
            )
        raise RuntimeError(res.error_summary or "SmartRecruiters fetch failed")

    async def fetch_result(
        self,
        parsed: ParsedATSUrl,
        client: httpx.AsyncClient,
        fallback_snippet: str | None = None,
        query_used: str = "",
    ) -> tuple[JobListing | None, ExtractionResult]:
        res = await self.fetch_raw_result(parsed, client, fallback_snippet, query_used)
        if res.outcome == ExtractionOutcome.NOT_FOUND:
            return None, res
        if res.outcome == ExtractionOutcome.SUCCESS and res.raw is not None:
            canonical = JobExtractionService.extract(res.raw)
            return CanonicalJobAdapter.to_listing(canonical), res
        listing = _fallback(parsed, fallback_snippet, query_used)
        listing.extraction_outcome = res.outcome.value
        listing.degraded_from = "api"
        res.degraded_from = "api"
        return listing, res

    async def fetch(
        self,
        parsed: ParsedATSUrl,
        client: httpx.AsyncClient,
        fallback_snippet: str | None = None,
        query_used: str = "",
    ) -> JobListing | None:
        listing, _ = await self.fetch_result(parsed, client, fallback_snippet, query_used)
        return listing


# ---------------------------------------------------------------------------
# Workable
# ---------------------------------------------------------------------------

_WORKABLE_TYPE_MAP: dict[str, str] = {
    "full": "Full-time",
    "full_time": "Full-time",
    "fulltime": "Full-time",
    "part": "Part-time",
    "part_time": "Part-time",
    "parttime": "Part-time",
    "contract": "Contract",
    "contractor": "Contract",
    "temporary": "Temporary",
    "temp": "Temporary",
    "intern": "Internship",
    "internship": "Internship",
}


def _format_workable_location_item(loc: object) -> str | None:
    if not isinstance(loc, dict) or loc.get("hidden") is True:
        return None
    city = str(loc.get("city") or "").strip()
    region = str(loc.get("region") or loc.get("state") or "").strip()
    country = str(loc.get("country") or "").strip()
    if city and country:
        return f"{city}, {country}"
    if region and country and region.lower() != country.lower():
        return f"{region}, {country}"
    if country:
        return country
    if city and region and city.lower() != region.lower():
        return f"{city}, {region}"
    return city or region or None


def _extract_workable_locations(data: dict) -> tuple[str | None, str | None]:
    """Return (normalized_location, raw_location_preserved) for Workable v2/widget payloads."""
    candidates: list[str] = []
    seen: set[str] = set()

    def _add(text: str | None) -> None:
        if not text:
            return
        norm = re.sub(r"\s+", " ", text).strip(" ,")
        if norm and norm.lower() not in seen:
            seen.add(norm.lower())
            candidates.append(norm)

    _add(_format_workable_location_item(data.get("location")))

    # Widget v1 flat city / state / country (skip top-level api/v2 publishing "state": "published")
    if not isinstance(data.get("location"), dict) and any(k in data for k in ("city", "country")):
        _add(
            _format_workable_location_item(
                {
                    "city": data.get("city"),
                    "region": data.get("state"),
                    "country": data.get("country"),
                }
            )
        )

    locs = data.get("locations")
    if isinstance(locs, list):
        for item in locs:
            _add(_format_workable_location_item(item))

    if not candidates:
        return None, None
    joined = " | ".join(candidates)
    preserved = joined if len(candidates) > 1 else None
    return joined, preserved


def _assemble_workable_description(
    desc_md: str | None,
    req_md: str | None,
    ben_md: str | None,
) -> str | None:
    """Assemble clean Workable description sections without duplicating headings."""
    sections: list[str] = []
    if desc_md and desc_md.strip():
        sections.append(desc_md.strip())

    if req_md and req_md.strip():
        req_clean = req_md.strip()
        has_heading = bool(
            re.match(r"^(?:#{1,6}\s+|[*_]{2})?(?:requirements|qualifications|minimum\s+qualifications)", req_clean, re.IGNORECASE)
        )
        sections.append(req_clean if has_heading else f"## Requirements\n\n{req_clean}")

    if ben_md and ben_md.strip():
        ben_clean = ben_md.strip()
        has_heading = bool(
            re.match(r"^(?:#{1,6}\s+|[*_]{2})?(?:benefits|perks|what\s+we\s+offer)", ben_clean, re.IGNORECASE)
        )
        sections.append(ben_clean if has_heading else f"## Benefits\n\n{ben_clean}")

    return "\n\n".join(sections) if sections else None


def workable_payload_to_raw(
    data: dict,
    *,
    company_slug: str,
    source_url: str | None = None,
    default_job_id: str | None = None,
    default_company_name: str | None = None,
    query_used: str = "",
    is_board_monitor: bool = False,
    company_logo_url: str | None = None,
    company_logo_source: str | None = None,
    company_logo_verified: bool = False,
) -> Optional[RawJobPosting]:
    """
    Shared deterministic converter from Workable public API v2 JSON
    (`GET https://apply.workable.com/api/v2/accounts/{slug}/jobs/{job_id}`) to RawJobPosting.
    """
    if not isinstance(data, dict):
        return None

    clean_slug = (company_slug or "").strip().lower()
    if not clean_slug:
        return None

    shortcode = str(data.get("shortcode") or default_job_id or "").strip()
    if not shortcode:
        return None

    encoded_slug = quote(clean_slug, safe="-_.~")
    canonical_default = f"https://apply.workable.com/{encoded_slug}/j/{shortcode}"
    canonical_source = (
        normalize_job_url(source_url, "workable")
        if source_url
        else canonical_default
    ) or canonical_default
    apply_url = f"{canonical_default}/apply"

    title = str(data.get("title") or "").strip()
    company = (
        str(data.get("company_name") or "").strip()
        or (default_company_name or "").strip()
        or humanize_slug(clean_slug)
        or "Unknown"
    )

    location, raw_loc_preserved = _extract_workable_locations(data)

    workplace_raw = str(data.get("workplace") or "").strip()
    remote_flag = data.get("remote")
    raw_workplace_type: str | None = workplace_raw or ("remote" if remote_flag is True else None)

    emp_raw_val = data.get("type") or data.get("employment_type")
    raw_employment_type: str | None = None
    if isinstance(emp_raw_val, str) and emp_raw_val.strip():
        emp_key = emp_raw_val.strip().lower().replace("-", "_").replace(" ", "_")
        raw_employment_type = _WORKABLE_TYPE_MAP.get(emp_key, emp_raw_val.strip())

    dept_val = data.get("department")
    raw_department: str | None = None
    if isinstance(dept_val, list):
        dept_parts = [str(d).strip() for d in dept_val if d and str(d).strip()]
        raw_department = ", ".join(dept_parts) if dept_parts else None
    elif isinstance(dept_val, str) and dept_val.strip():
        raw_department = dept_val.strip()

    raw_date = data.get("published") or data.get("published_on") or data.get("created_at")
    if raw_date is not None:
        raw_date = str(raw_date).strip() or None

    desc_html = str(data.get("description") or "").strip()
    req_html = str(data.get("requirements") or "").strip()
    ben_html = str(data.get("benefits") or "").strip()

    desc_md = to_markdown(strip_li_tags(desc_html)) if desc_html else None
    req_md = to_markdown(strip_li_tags(req_html)) if req_html else None
    ben_md = to_markdown(strip_li_tags(ben_html)) if ben_html else None
    assembled_desc = _assemble_workable_description(desc_md, req_md, ben_md)
    has_authentic = bool(assembled_desc and assembled_desc.strip())

    raw_fields: dict = {}
    if isinstance(data.get("location"), dict):
        raw_fields["location"] = data["location"]
    if isinstance(data.get("locations"), list):
        raw_fields["locations"] = data["locations"]
    if raw_loc_preserved:
        raw_fields["raw_location_preserved"] = raw_loc_preserved
    if workplace_raw:
        raw_fields["workplace"] = workplace_raw
    if isinstance(remote_flag, bool):
        raw_fields["remote"] = remote_flag
    for sal_key in ("salary_from", "salary_to", "salary_currency_iso_code", "salary_frequency"):
        if data.get(sal_key) is not None:
            raw_fields[sal_key] = data[sal_key]
    if data.get("id") is not None:
        raw_fields["workable_id"] = data["id"]
    if data.get("code"):
        raw_fields["code"] = data["code"]
    if data.get("accountUid"):
        raw_fields["accountUid"] = data["accountUid"]
    if is_board_monitor:
        raw_fields["is_board_monitor"] = True
    if company_logo_url and company_logo_verified:
        raw_fields["company_logo_url"] = company_logo_url
        raw_fields["company_logo_source"] = company_logo_source
        raw_fields["company_logo_verified"] = True

    return RawJobPosting(
        provider="workable",
        source_url=canonical_source,
        provider_job_id=shortcode,
        company_slug=clean_slug,
        apply_url=apply_url,
        extraction_method=ExtractionMethod.ATS_API,
        raw_title=title,
        raw_company=company,
        raw_location=location,
        raw_workplace_type=raw_workplace_type,
        raw_department=raw_department,
        raw_employment_type=raw_employment_type,
        raw_date=raw_date,
        raw_requirements=req_md if req_md else None,
        raw_fields=raw_fields,
        raw_description=assembled_desc,
        description_is_authentic=has_authentic,
        query_used=query_used,
    )


def workable_widget_job_to_raw(
    item: dict,
    *,
    company_slug: str,
    default_company_name: str | None = None,
    query_used: str = "",
    company_logo_url: str | None = None,
    company_logo_source: str | None = None,
    company_logo_verified: bool = False,
) -> Optional[RawJobPosting]:
    """Baseline Workable widget v1 conversion when full api/v2 detail is deferred."""
    if not isinstance(item, dict):
        return None
    shortcode = str(item.get("shortcode") or "").strip()
    clean_slug = (company_slug or "").strip().lower()
    if not shortcode or not clean_slug:
        return None
    encoded_slug = quote(clean_slug, safe="-_.~")
    canonical_url = f"https://apply.workable.com/{encoded_slug}/j/{shortcode}"
    apply_url = f"{canonical_url}/apply"
    location, raw_loc_preserved = _extract_workable_locations(item)

    raw_workplace = "remote" if item.get("telecommuting") is True else None
    raw_fields: dict = {"is_board_monitor": True}
    if isinstance(item.get("locations"), list):
        raw_fields["locations"] = item["locations"]
    loc_dict = {
        k: v
        for k, v in {
            "city": item.get("city"),
            "region": item.get("state"),
            "country": item.get("country"),
        }.items()
        if v
    }
    if not loc_dict and isinstance(item.get("locations"), list) and item["locations"]:
        first_loc = item["locations"][0]
        if isinstance(first_loc, dict):
            loc_dict = first_loc
    if loc_dict:
        raw_fields["location"] = loc_dict
    if raw_loc_preserved:
        raw_fields["raw_location_preserved"] = raw_loc_preserved
    if company_logo_url and company_logo_verified:
        raw_fields["company_logo_url"] = company_logo_url
        raw_fields["company_logo_source"] = company_logo_source
        raw_fields["company_logo_verified"] = True

    dept = str(item.get("department") or "").strip() or None
    emp = str(item.get("employment_type") or "").strip() or None
    raw_date = str(item.get("published_on") or item.get("created_at") or "").strip() or None
    return RawJobPosting(
        provider="workable",
        source_url=canonical_url,
        provider_job_id=shortcode,
        company_slug=clean_slug,
        apply_url=apply_url,
        extraction_method=ExtractionMethod.ATS_API,
        raw_title=str(item.get("title") or "").strip(),
        raw_company=(default_company_name or humanize_slug(clean_slug) or "Unknown").strip(),
        raw_location=location,
        raw_workplace_type=raw_workplace,
        raw_department=dept,
        raw_employment_type=emp,
        raw_date=raw_date,
        raw_fields=raw_fields,
        raw_description=None,
        description_is_authentic=False,
        query_used=query_used,
    )


def workable_markdown_to_raw(
    markdown: str,
    *,
    parsed: ParsedATSUrl,
    fallback_snippet: str | None = None,
    query_used: str = "",
) -> RawJobPosting:
    """Clean Workable `.md` endpoint fallback parser stripping header/footer chrome."""
    all_lines = markdown.splitlines()
    non_empty = [ln.strip() for ln in all_lines if ln.strip()]
    title = non_empty[0].removeprefix("# ").strip() if non_empty and non_empty[0].startswith("# ") else (non_empty[0] if non_empty else "")
    summary = next((ln[2:].strip() for ln in non_empty if ln.startswith("> ")), "")
    summary_parts = [part.strip() for part in summary.split("·") if part.strip()]
    company = summary_parts[0] if summary_parts else humanize_slug(parsed.company_slug) or "Unknown"
    location = summary_parts[1] if len(summary_parts) > 1 else None
    employment = summary_parts[2] if len(summary_parts) > 2 else None
    posted_match = re.search(r"Posted\s+(.+)$", summary, re.IGNORECASE)
    raw_date = posted_match.group(1).strip() if posted_match else None

    workplace_match = re.search(r"^\*\*Workplace:\*\*\s*(.+)$", markdown, re.IGNORECASE | re.MULTILINE)
    raw_workplace_type = workplace_match.group(1).strip() if workplace_match else None
    department_match = re.search(r"^\*\*Department:\*\*\s*(.+)$", markdown, re.IGNORECASE | re.MULTILINE)
    dept = department_match.group(1).strip() if department_match else None
    salary_match = re.search(r"^\*\*Salary:\*\*\s*(.+)$", markdown, re.IGNORECASE | re.MULTILINE)
    salary_header = salary_match.group(1).strip() if salary_match else None

    # Extract explicit /apply URL from trailing Apply link if present
    canonical_default = f"https://apply.workable.com/{quote(parsed.company_slug.lower(), safe='-_.~')}/j/{parsed.job_id}"
    canonical_source = normalize_job_url(parsed.raw_url, "workable") or canonical_default
    apply_match = re.search(
        r"##\s+Apply\s*\n+\s*\[[^\]]*\]\((https?://[^\s)]+/apply/?)\)",
        markdown,
        re.IGNORECASE,
    )
    apply_url = apply_match.group(1).rstrip("/") if apply_match else f"{canonical_default}/apply"

    # Strip header metadata chrome & footer boilerplate
    body = markdown
    sec_match = re.search(r"^##\s+", body, re.MULTILINE)
    if sec_match:
        body = body[sec_match.start():]
    else:
        body_lines = []
        skipping_header = True
        for ln in all_lines:
            s = ln.strip()
            if skipping_header:
                if (
                    not s
                    or s.startswith("# ")
                    or s.startswith("> ")
                    or re.match(r"^\*\*(?:Workplace|Department|Salary|Location|Employment\s+Type):\*\*", s, re.IGNORECASE)
                ):
                    continue
                skipping_header = False
            body_lines.append(ln)
        body = "\n".join(body_lines)

    body = re.sub(
        r"\n*##\s+Apply\s*\n+[\s\S]*?(?:Powered by \[Workable\][^\n]*)?\s*$",
        "",
        body,
        flags=re.IGNORECASE,
    )
    body = re.sub(r"\n*---\s*\n*Powered by \[Workable\][^\n]*\s*$", "", body, flags=re.IGNORECASE).strip()

    raw_fields: dict = {"markdown": markdown}
    if salary_header:
        raw_fields["salary"] = salary_header

    return RawJobPosting(
        provider="workable",
        source_url=canonical_source,
        provider_job_id=parsed.job_id,
        company_slug=parsed.company_slug,
        apply_url=apply_url,
        extraction_method=ExtractionMethod.SCRAPE,
        raw_title=title or fallback_snippet or parsed.raw_url,
        raw_company=company,
        raw_location=location,
        raw_workplace_type=raw_workplace_type,
        raw_department=dept,
        raw_employment_type=employment,
        raw_date=raw_date,
        raw_fields=raw_fields,
        raw_description=body or None,
        description_is_authentic=bool(body),
        query_used=query_used,
    )


_WORKABLE_IDENTITY_INFLIGHT: dict[tuple[int, str, int, bool], asyncio.Task[tuple[str | None, LogoResult]]] = {}


async def enrich_workable_board_identity(
    company_slug: str,
    client: httpx.AsyncClient,
    *,
    registry: CompanyBoardRegistry | None = None,
    ttl_seconds: int = 7 * 86400,
    use_resilience: bool = False,
) -> tuple[str | None, LogoResult]:
    """
    Bounded Workable board identity enrichment (`GET /api/v1/accounts/{slug}`)
    with 7-day SQLite positive/negative caching and per-slug concurrency coalescing.
    """
    slug = (company_slug or "").strip()
    slug_lower = slug.lower()
    if not slug or "/" in slug or "?" in slug or not is_valid_board_slug("workable", slug_lower):
        return None, LogoResult()

    target_reg = registry or company_board_registry
    now = time.time()
    board = target_reg.get_board("workable", slug_lower)
    if board is not None:
        checked_ts = board.company_logo_checked_at or board.company_logo_updated_at
        if board.company_logo_url and board.company_logo_verified:
            if checked_ts is None or (now - checked_ts) < ttl_seconds:
                return board.company_name, LogoResult(
                    url=board.company_logo_url,
                    source=board.company_logo_source,
                    raw_value=board.company_logo_url,
                    verified=True,
                )
        elif board.company_logo_checked_at is not None and (now - board.company_logo_checked_at) < ttl_seconds:
            return board.company_name, LogoResult()

    loop = asyncio.get_running_loop()
    inflight_key = (id(loop), slug_lower, id(target_reg), bool(use_resilience))
    existing_task = _WORKABLE_IDENTITY_INFLIGHT.get(inflight_key)
    if existing_task is not None:
        return await existing_task

    async def _fetch_identity() -> tuple[str | None, LogoResult]:
        encoded_slug = quote(slug_lower, safe="-_.~")
        acct_url = f"https://apply.workable.com/api/v1/accounts/{encoded_slug}"
        board_url = f"https://apply.workable.com/{encoded_slug}"
        headers = browser_headers(acct_url, "application/json,text/plain;q=0.9,*/*;q=0.8")
        try:
            if use_resilience:
                resp = await throttled_get(
                    client,
                    acct_url,
                    headers=headers,
                    timeout=min(float(settings.ats_request_timeout_seconds), 8.0),
                    follow_redirects=True,
                )
            else:
                resp = await client.get(
                    acct_url,
                    headers=headers,
                    timeout=min(float(settings.ats_request_timeout_seconds), 8.0),
                    follow_redirects=True,
                )
        except (CircuitBreakerOpenError, HostRateLimitedError, Exception) as exc:
            logger.debug(f"[workable] Account identity fetch failed for {slug_lower}: {exc}")
            existing_logo = (
                LogoResult(
                    url=board.company_logo_url,
                    source=board.company_logo_source,
                    raw_value=board.company_logo_url,
                    verified=bool(board.company_logo_verified),
                )
                if board and board.company_logo_url
                else LogoResult()
            )
            return (board.company_name if board else None), existing_logo

        if resp.status_code != 200:
            existing_logo = (
                LogoResult(
                    url=board.company_logo_url,
                    source=board.company_logo_source,
                    raw_value=board.company_logo_url,
                    verified=bool(board.company_logo_verified),
                )
                if board and board.company_logo_url
                else LogoResult()
            )
            return (board.company_name if board else None), existing_logo

        try:
            data = resp.json()
        except Exception:
            return (board.company_name if board else None), LogoResult()

        if not isinstance(data, dict):
            return (board.company_name if board else None), LogoResult()

        raw_name = data.get("name")
        extracted_name = raw_name.strip() if isinstance(raw_name, str) and raw_name.strip() else None
        logo_res = extract_company_logo_for_provider(
            "workable",
            workable_account_logo=data.get("logo"),
            page_url=board_url,
            company_name=extracted_name or (board.company_name if board else None),
        )
        updated = target_reg.set_board_identity(
            ats_provider="workable",
            board_token=slug_lower,
            company_name=extracted_name,
            logo_url=logo_res.url,
            logo_source=logo_res.source,
            logo_verified=logo_res.verified,
            board_url=board_url,
        )
        final_name = extracted_name or (updated.company_name if updated else (board.company_name if board else None))
        if logo_res.url:
            return final_name, logo_res
        if board and board.company_logo_url and board.company_logo_verified:
            return final_name, LogoResult(
                url=board.company_logo_url,
                source=board.company_logo_source,
                raw_value=board.company_logo_url,
                verified=True,
            )
        return final_name, LogoResult()

    task = asyncio.create_task(_fetch_identity())
    _WORKABLE_IDENTITY_INFLIGHT[inflight_key] = task
    try:
        return await task
    finally:
        if _WORKABLE_IDENTITY_INFLIGHT.get(inflight_key) is task:
            _WORKABLE_IDENTITY_INFLIGHT.pop(inflight_key, None)


class WorkableClient:
    """
    Primary: GET https://apply.workable.com/api/v2/accounts/{slug}/jobs/{job_id}
    Identity: GET https://apply.workable.com/api/v1/accounts/{slug}
    Fallback: Markdown view response when served non-JSON Markdown.
    """

    @with_retry(max_attempts=3, base_delay=0.5)
    async def _do_fetch(self, url: str, client: httpx.AsyncClient) -> httpx.Response:
        resp = await client.get(
            url,
            headers=browser_headers(url, "application/json,text/plain;q=0.9,*/*;q=0.8"),
            timeout=_TIMEOUT,
            follow_redirects=True,
        )
        resp.raise_for_status()
        return resp

    async def fetch_raw_result(
        self,
        parsed: ParsedATSUrl,
        client: httpx.AsyncClient,
        fallback_snippet: str | None = None,
        query_used: str = "",
    ) -> ExtractionResult:
        encoded_slug = quote(parsed.company_slug.lower(), safe="-_.~")
        encoded_job_id = quote(parsed.job_id, safe="-_.~")
        url = f"https://apply.workable.com/api/v2/accounts/{encoded_slug}/jobs/{encoded_job_id}"
        try:
            response = await self._do_fetch(url, client)
        except httpx.HTTPStatusError as exc:
            outcome = map_status_or_exception_to_outcome(exception=exc)
            safe_err = sanitize_error_text(f"[workable] HTTP error {exc.response.status_code} for {url}")
            return ExtractionResult(
                outcome=outcome,
                raw=None,
                status_code=exc.response.status_code,
                error_summary=safe_err,
                attempts=get_current_attempts(),
            )
        except Exception as exc:
            outcome = map_status_or_exception_to_outcome(exception=exc)
            safe_err = sanitize_error_text(f"[workable] API fetch failed for {url}: {exc}")
            return ExtractionResult(
                outcome=outcome,
                raw=None,
                status_code=None,
                error_summary=safe_err,
                attempts=get_current_attempts(),
            )

        body_text = response.text or ""
        content_type = (response.headers.get("content-type") or "").lower()
        data = None
        if "markdown" not in content_type and body_text.lstrip().startswith(("{", "[")):
            try:
                data = response.json()
            except Exception:
                data = None

        if isinstance(data, dict):
            raw = workable_payload_to_raw(
                data,
                company_slug=parsed.company_slug,
                source_url=parsed.raw_url,
                default_job_id=parsed.job_id,
                query_used=query_used,
            )
            if raw is None:
                return ExtractionResult(
                    outcome=ExtractionOutcome.PARSE_FAILURE,
                    raw=None,
                    status_code=200,
                    error_summary=sanitize_error_text(f"[workable] Invalid API v2 payload shape for {url}"),
                    attempts=get_current_attempts(),
                )
            return ExtractionResult(
                outcome=ExtractionOutcome.SUCCESS,
                raw=raw,
                status_code=200,
                attempts=get_current_attempts(),
            )

        if body_text.lstrip().startswith("# "):
            raw = workable_markdown_to_raw(
                body_text,
                parsed=parsed,
                fallback_snippet=fallback_snippet,
                query_used=query_used,
            )
            return ExtractionResult(
                outcome=ExtractionOutcome.SUCCESS,
                raw=raw,
                status_code=200,
                attempts=get_current_attempts(),
            )

        return ExtractionResult(
            outcome=ExtractionOutcome.PARSE_FAILURE,
            raw=None,
            status_code=200,
            error_summary=sanitize_error_text(f"[workable] Unrecognized response format for {url}"),
            attempts=get_current_attempts(),
        )

    async def fetch_raw(
        self,
        parsed: ParsedATSUrl,
        client: httpx.AsyncClient,
        fallback_snippet: str | None = None,
        query_used: str = "",
    ) -> RawJobPosting | None:
        res = await self.fetch_raw_result(parsed, client, fallback_snippet, query_used)
        if res.outcome == ExtractionOutcome.NOT_FOUND:
            return None
        if res.raw is not None:
            return res.raw
        if res.status_code is not None and res.status_code != 200:
            raise httpx.HTTPStatusError(
                f"HTTP Error {res.status_code}",
                request=httpx.Request("GET", parsed.raw_url),
                response=httpx.Response(res.status_code),
            )
        raise RuntimeError(res.error_summary or "Workable fetch failed")

    async def fetch_result(
        self,
        parsed: ParsedATSUrl,
        client: httpx.AsyncClient,
        fallback_snippet: str | None = None,
        query_used: str = "",
    ) -> tuple[JobListing | None, ExtractionResult]:
        res = await self.fetch_raw_result(parsed, client, fallback_snippet, query_used)
        if res.outcome == ExtractionOutcome.NOT_FOUND:
            return None, res
        if res.outcome == ExtractionOutcome.SUCCESS and res.raw is not None:
            if res.raw.extraction_method == ExtractionMethod.ATS_API and (
                not res.raw.raw_fields.get("company_logo_verified")
                or not res.raw.raw_company
                or res.raw.raw_company in ("Unknown", parsed.company_slug, humanize_slug(parsed.company_slug))
            ):
                try:
                    board_name, logo_res = await enrich_workable_board_identity(parsed.company_slug, client)
                    if board_name and (
                        not res.raw.raw_company
                        or res.raw.raw_company in ("Unknown", parsed.company_slug, humanize_slug(parsed.company_slug))
                    ):
                        res.raw.raw_company = board_name
                    if logo_res.url and logo_res.verified:
                        res.raw.raw_fields["company_logo_url"] = logo_res.url
                        res.raw.raw_fields["company_logo_source"] = logo_res.source
                        res.raw.raw_fields["company_logo_verified"] = True
                except Exception as exc:
                    logger.debug(f"[workable] Optional board identity enrichment failed for {parsed.company_slug}: {exc}")
            canonical = JobExtractionService.extract(res.raw)
            return CanonicalJobAdapter.to_listing(canonical), res
        listing = _fallback(parsed, fallback_snippet, query_used)
        listing.extraction_outcome = res.outcome.value
        listing.degraded_from = "api"
        res.degraded_from = "api"
        return listing, res

    async def fetch(
        self,
        parsed: ParsedATSUrl,
        client: httpx.AsyncClient,
        fallback_snippet: str | None = None,
        query_used: str = "",
    ) -> JobListing | None:
        listing, _ = await self.fetch_result(parsed, client, fallback_snippet, query_used)
        return listing


# ---------------------------------------------------------------------------
# BambooHR
# ---------------------------------------------------------------------------

class BambooHRClient:
    """
    GET https://{slug}.bamboohr.com/careers/list
    Returns JSON array of all open roles. Filter by id field to find the target job.
    """

    @with_retry(max_attempts=3, base_delay=0.5)
    async def _do_fetch(self, url: str, client: httpx.AsyncClient) -> dict:
        resp = await client.get(url, headers=browser_headers(url, "application/json,text/plain;q=0.9,*/*;q=0.8"), timeout=_TIMEOUT)
        resp.raise_for_status()
        return resp.json()

    async def fetch_raw_result(
        self,
        parsed: ParsedATSUrl,
        client: httpx.AsyncClient,
        fallback_snippet: str | None = None,
        query_used: str = "",
    ) -> ExtractionResult:
        url = f"https://{parsed.company_slug}.bamboohr.com/careers/list"
        try:
            data = await self._do_fetch(url, client)
        except httpx.HTTPStatusError as exc:
            outcome = map_status_or_exception_to_outcome(exception=exc)
            safe_err = sanitize_error_text(f"[bamboohr] HTTP error {exc.response.status_code} for {url}")
            return ExtractionResult(
                outcome=outcome,
                raw=None,
                status_code=exc.response.status_code,
                error_summary=safe_err,
                attempts=get_current_attempts(),
            )
        except Exception as exc:
            outcome = map_status_or_exception_to_outcome(exception=exc)
            safe_err = sanitize_error_text(f"[bamboohr] Unexpected error for {url}: {exc}")
            return ExtractionResult(
                outcome=outcome,
                raw=None,
                status_code=None,
                error_summary=safe_err,
                attempts=get_current_attempts(),
            )

        jobs: list[dict] = []
        if isinstance(data, list):
            jobs = data
        elif isinstance(data, dict):
            jobs = data.get("result", []) or data.get("jobs", [])

        target = str(parsed.job_id)
        matched: dict | None = None
        for job in jobs:
            if str(job.get("id", "")) == target:
                matched = job
                break

        if matched is None:
            return ExtractionResult(
                outcome=ExtractionOutcome.NOT_FOUND,
                raw=None,
                status_code=404,
                error_summary=f"[bamboohr] Job ID {parsed.job_id} not found in career list",
                attempts=get_current_attempts(),
            )

        title = matched.get("title", "") or matched.get("jobTitle", "")
        location = matched.get("location", {}).get("city") if isinstance(matched.get("location"), dict) else matched.get("location")
        apply_url = f"https://{parsed.company_slug}.bamboohr.com/careers/{parsed.job_id}"
        raw_workplace_type = matched.get("locationType")
        company = _first_name(matched.get("company") or matched.get("companyName")) or humanize_slug(parsed.company_slug) or "Unknown"
        dept = _first_name(matched.get("department"))
        emp = matched.get("employmentStatus") or matched.get("employmentType")

        raw = RawJobPosting(
            provider="bamboohr",
            source_url=parsed.raw_url,
            provider_job_id=parsed.job_id,
            company_slug=parsed.company_slug,
            apply_url=apply_url,
            raw_title=title,
            raw_company=company,
            raw_location=location,
            raw_workplace_type=raw_workplace_type,
            raw_department=dept,
            raw_employment_type=emp,
            raw_date=None,
            raw_fields=matched,
            raw_description=None,
            description_is_authentic=True,
            query_used=query_used,
        )
        return ExtractionResult(
            outcome=ExtractionOutcome.SUCCESS,
            raw=raw,
            status_code=200,
            attempts=get_current_attempts(),
        )

    async def fetch_raw(
        self,
        parsed: ParsedATSUrl,
        client: httpx.AsyncClient,
        fallback_snippet: str | None = None,
        query_used: str = "",
    ) -> RawJobPosting | None:
        res = await self.fetch_raw_result(parsed, client, fallback_snippet, query_used)
        if res.outcome == ExtractionOutcome.NOT_FOUND:
            return None
        if res.raw is not None:
            return res.raw
        if res.status_code is not None and res.status_code != 200:
            import httpx
            raise httpx.HTTPStatusError(
                f"HTTP Error {res.status_code}",
                request=httpx.Request("GET", parsed.raw_url),
                response=httpx.Response(res.status_code),
            )
        raise RuntimeError(res.error_summary or "BambooHR fetch failed")

    async def fetch_result(
        self,
        parsed: ParsedATSUrl,
        client: httpx.AsyncClient,
        fallback_snippet: str | None = None,
        query_used: str = "",
    ) -> tuple[JobListing | None, ExtractionResult]:
        res = await self.fetch_raw_result(parsed, client, fallback_snippet, query_used)
        if res.outcome == ExtractionOutcome.NOT_FOUND:
            return None, res
        if res.outcome == ExtractionOutcome.SUCCESS and res.raw is not None:
            canonical = JobExtractionService.extract(res.raw)
            return CanonicalJobAdapter.to_listing(canonical), res
        listing = _fallback(parsed, fallback_snippet, query_used)
        listing.extraction_outcome = res.outcome.value
        listing.degraded_from = "api"
        res.degraded_from = "api"
        return listing, res

    async def fetch(
        self,
        parsed: ParsedATSUrl,
        client: httpx.AsyncClient,
        fallback_snippet: str | None = None,
        query_used: str = "",
    ) -> JobListing | None:
        listing, _ = await self.fetch_result(parsed, client, fallback_snippet, query_used)
        return listing


# ---------------------------------------------------------------------------
# Recruitee
# ---------------------------------------------------------------------------

class RecruiteeClient:
    """
    GET https://api.recruitee.com/c/{slug}/offers/{job_id}
    Fields: title, location, remote, created_at, careers_url
    """

    @with_retry(max_attempts=3, base_delay=0.5)
    async def _do_fetch(self, url: str, client: httpx.AsyncClient) -> dict:
        resp = await client.get(url, headers=browser_headers(url, "application/json,text/plain;q=0.9,*/*;q=0.8"), timeout=_TIMEOUT)
        resp.raise_for_status()
        return resp.json()

    async def fetch_raw_result(
        self,
        parsed: ParsedATSUrl,
        client: httpx.AsyncClient,
        fallback_snippet: str | None = None,
        query_used: str = "",
    ) -> ExtractionResult:
        url = f"https://{parsed.company_slug}.recruitee.com/api/offers/{parsed.job_id}"
        try:
            data = await self._do_fetch(url, client)
        except httpx.HTTPStatusError as exc:
            outcome = map_status_or_exception_to_outcome(exception=exc)
            safe_err = sanitize_error_text(f"[recruitee] HTTP error {exc.response.status_code} for {url}")
            return ExtractionResult(
                outcome=outcome,
                raw=None,
                status_code=exc.response.status_code,
                error_summary=safe_err,
                attempts=get_current_attempts(),
            )
        except Exception as exc:
            outcome = map_status_or_exception_to_outcome(exception=exc)
            safe_err = sanitize_error_text(f"[recruitee] Unexpected error for {url}: {exc}")
            return ExtractionResult(
                outcome=outcome,
                raw=None,
                status_code=None,
                error_summary=safe_err,
                attempts=get_current_attempts(),
            )

        offer = data.get("offer") or data
        title = offer.get("title", "") or offer.get("position", "")
        location = offer.get("location") or offer.get("city")
        raw_workplace_type = offer.get("workplace_type") or offer.get("workplaceType")
        raw_desc = offer.get("description") or offer.get("description_html") or offer.get("intro")
        company = _first_name(offer.get("company") or offer.get("companyName")) or humanize_slug(parsed.company_slug) or "Unknown"
        apply_url = offer.get("careers_url") or parsed.raw_url
        emp = offer.get("employment_type") or offer.get("employmentType")
        raw_date = offer.get("created_at")
        dept = _first_name(offer.get("department"))

        raw = RawJobPosting(
            provider="recruitee",
            source_url=parsed.raw_url,
            provider_job_id=parsed.job_id,
            company_slug=parsed.company_slug,
            apply_url=apply_url,
            raw_title=title,
            raw_company=company,
            raw_location=location,
            raw_workplace_type=raw_workplace_type,
            raw_department=dept,
            raw_employment_type=emp,
            raw_date=raw_date,
            raw_fields=offer,
            raw_description=raw_desc,
            description_is_authentic=True,
            query_used=query_used,
        )
        return ExtractionResult(
            outcome=ExtractionOutcome.SUCCESS,
            raw=raw,
            status_code=200,
            attempts=get_current_attempts(),
        )

    async def fetch_raw(
        self,
        parsed: ParsedATSUrl,
        client: httpx.AsyncClient,
        fallback_snippet: str | None = None,
        query_used: str = "",
    ) -> RawJobPosting | None:
        res = await self.fetch_raw_result(parsed, client, fallback_snippet, query_used)
        if res.outcome == ExtractionOutcome.NOT_FOUND:
            return None
        if res.raw is not None:
            return res.raw
        if res.status_code is not None and res.status_code != 200:
            import httpx
            raise httpx.HTTPStatusError(
                f"HTTP Error {res.status_code}",
                request=httpx.Request("GET", parsed.raw_url),
                response=httpx.Response(res.status_code),
            )
        raise RuntimeError(res.error_summary or "Recruitee fetch failed")

    async def fetch_result(
        self,
        parsed: ParsedATSUrl,
        client: httpx.AsyncClient,
        fallback_snippet: str | None = None,
        query_used: str = "",
    ) -> tuple[JobListing | None, ExtractionResult]:
        res = await self.fetch_raw_result(parsed, client, fallback_snippet, query_used)
        if res.outcome == ExtractionOutcome.NOT_FOUND:
            return None, res
        if res.outcome == ExtractionOutcome.SUCCESS and res.raw is not None:
            canonical = JobExtractionService.extract(res.raw)
            return CanonicalJobAdapter.to_listing(canonical), res
        listing = _fallback(parsed, fallback_snippet, query_used)
        listing.extraction_outcome = res.outcome.value
        listing.degraded_from = "api"
        res.degraded_from = "api"
        return listing, res

    async def fetch(
        self,
        parsed: ParsedATSUrl,
        client: httpx.AsyncClient,
        fallback_snippet: str | None = None,
        query_used: str = "",
    ) -> JobListing | None:
        listing, _ = await self.fetch_result(parsed, client, fallback_snippet, query_used)
        return listing


# ---------------------------------------------------------------------------
# Registry — maps ats name → client instance
# ---------------------------------------------------------------------------

class WorkdayClient:
    """
    Single authoritative Workday extractor:
      1. Primary: Public Workday CXS endpoint (/wday/cxs/{tenant}/{site_id}/job/{job_slug})
      2. Fallback: Canonical Workday HTML page (Schema.org JSON-LD JobPosting & postingAvailable check)
      3. Graceful degradation: Snippet fallback only when upstream failed (never on 404/expired).
    """

    @staticmethod
    def _unwrap_descriptor(val: object) -> str | None:
        if isinstance(val, dict):
            desc = val.get("descriptor") or val.get("name") or val.get("label")
            return str(desc).strip() if desc else None
        if isinstance(val, str) and val.strip():
            return val.strip()
        return None

    async def _get_with_short_retry(
        self,
        url: str,
        client: httpx.AsyncClient,
        *,
        accept: str,
    ) -> tuple[httpx.Response | None, Exception | None, int]:
        import asyncio as _asyncio

        last_exc: Exception | None = None
        attempts = 0
        for attempt in range(2):
            attempts += 1
            try:
                resp = await client.get(
                    url,
                    headers=browser_headers(url, accept),
                    timeout=_TIMEOUT,
                    follow_redirects=True,
                )
                if resp.status_code in (429, 500, 502, 503, 504) and attempt == 0:
                    await _asyncio.sleep(0.15)
                    continue
                return resp, None, attempts
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_exc = exc
                if attempt == 0:
                    await _asyncio.sleep(0.15)
                    continue
                return None, exc, attempts
            except Exception as exc:
                return None, exc, attempts
        return None, last_exc, attempts

    def _parse_cxs_payload(
        self,
        data: dict,
        parsed: ParsedATSUrl,
        *,
        tenant: str,
        site_id: str,
        query_used: str,
    ) -> RawJobPosting | None:
        import html as _html

        info = data.get("jobPostingInfo")
        if not isinstance(info, dict):
            return None
        title = _html.unescape(str(info.get("title") or "")).strip()
        raw_desc = info.get("jobDescription") or info.get("description") or ""
        if not title and not raw_desc:
            return None

        hiring_org = data.get("hiringOrganization")
        company = (
            self._unwrap_descriptor(info.get("company"))
            or (
                _html.unescape(str(hiring_org.get("name") or "")).strip()
                if isinstance(hiring_org, dict)
                else None
            )
            or humanize_slug(tenant)
            or "Unknown"
        )
        raw_loc = info.get("location")
        raw_workplace_type = self._unwrap_descriptor(
            info.get("remoteType") or info.get("workplaceType")
        )
        raw_emp = self._unwrap_descriptor(info.get("timeType"))
        dept = self._unwrap_descriptor(info.get("jobFamily") or info.get("department"))

        raw_fields = dict(info)
        raw_fields.setdefault("jobPostingSiteId", site_id)
        if isinstance(hiring_org, dict):
            raw_fields.setdefault("hiringOrganization", hiring_org)

        raw_date = info.get("postedDate")
        if not raw_date and info.get("startDate"):
            raw_date = info.get("startDate")
            raw_fields["date_field_name"] = "startDate"
        elif not raw_date:
            raw_date = info.get("postedOn")

        return RawJobPosting(
            provider="workday",
            source_url=parsed.raw_url,
            provider_job_id=parsed.job_id,
            company_slug=parsed.company_slug,
            apply_url=parsed.raw_url,
            raw_title=title,
            raw_company=company,
            raw_location=raw_loc if isinstance(raw_loc, str) else None,
            raw_workplace_type=raw_workplace_type,
            raw_department=dept,
            raw_employment_type=raw_emp,
            raw_date=raw_date,
            raw_fields=raw_fields,
            raw_description=raw_desc,
            description_is_authentic=True,
            query_used=query_used,
        )

    def _parse_html_fallback(
        self,
        html_text: str,
        parsed: ParsedATSUrl,
        *,
        tenant: str,
        site_id: str,
        query_used: str,
    ) -> RawJobPosting | None:
        import html as _html
        from bs4 import BeautifulSoup
        from src.project_files.html_helpers import (
            extract_job_posting_json_ld,
            html_meta_content,
            jsonld_text,
        )

        soup = BeautifulSoup(html_text, "lxml")
        doc = extract_job_posting_json_ld(soup)
        if not doc:
            return None

        title = (
            jsonld_text(doc.get("title"))
            or html_meta_content(soup, "property", "og:title")
            or (soup.title.get_text(" ", strip=True) if soup.title else "")
            or ""
        )
        company = (
            jsonld_text(doc.get("hiringOrganization"))
            or humanize_slug(tenant)
            or "Unknown"
        )
        raw_loc = jsonld_text(doc.get("jobLocation"))
        raw_desc_val = doc.get("description")
        raw_desc = _html.unescape(str(raw_desc_val)) if raw_desc_val else ""
        if not title and not raw_desc:
            return None

        raw_emp = jsonld_text(doc.get("employmentType"))
        raw_workplace = jsonld_text(doc.get("jobLocationType"))
        raw_date = doc.get("datePosted")
        raw_fields = {
            **doc,
            "json_ld": doc,
            "jobLocationType": doc.get("jobLocationType"),
            "jobPostingSiteId": site_id,
            "_extraction_method": "json_ld",
        }
        return RawJobPosting(
            provider="workday",
            source_url=parsed.raw_url,
            provider_job_id=parsed.job_id,
            company_slug=parsed.company_slug,
            apply_url=parsed.raw_url,
            raw_title=title,
            raw_company=company,
            raw_location=raw_loc,
            raw_workplace_type=raw_workplace,
            raw_employment_type=raw_emp,
            raw_date=raw_date,
            raw_fields=raw_fields,
            raw_description=raw_desc,
            description_is_authentic=bool(raw_desc),
            query_used=query_used,
        )

    async def fetch_raw_result(
        self,
        parsed: ParsedATSUrl,
        client: httpx.AsyncClient,
        fallback_snippet: str | None = None,
        query_used: str = "",
    ) -> ExtractionResult:
        import json as _json
        from urllib.parse import urlparse
        from src.project_files.ats_url_parser import parse_workday_url
        from src.project_files.html_helpers import (
            is_waf_challenge,
            is_workday_posting_unavailable,
        )
        from src.project_files.http_resilience import resilience_manager

        wd_parts = parse_workday_url(parsed.raw_url)
        if wd_parts is None:
            return ExtractionResult(
                outcome=ExtractionOutcome.NOT_FOUND,
                raw=None,
                status_code=404,
                error_summary=sanitize_error_text(f"[workday] Invalid Workday job URL: {parsed.raw_url}"),
                attempts=0,
            )

        host = resilience_manager.extract_host(wd_parts.cxs_url)
        if not resilience_manager.is_host_open(host):
            return ExtractionResult(
                outcome=ExtractionOutcome.RETRYABLE_ERROR,
                raw=None,
                status_code=None,
                error_summary=sanitize_error_text(f"[workday] Circuit open for {host}"),
                attempts=0,
            )

        total_attempts = 0
        cxs_outcome = ExtractionOutcome.RETRYABLE_ERROR
        cxs_status: int | None = None
        cxs_err: str | None = None

        # 1. Primary path: Workday CXS JSON endpoint
        cxs_resp, cxs_exc, cxs_attempts = await self._get_with_short_retry(
            wd_parts.cxs_url,
            client,
            accept="application/json",
        )
        total_attempts += cxs_attempts

        if cxs_exc is not None:
            cxs_outcome = map_status_or_exception_to_outcome(exception=cxs_exc)
            cxs_err = sanitize_error_text(f"[workday] CXS error for {wd_parts.cxs_url}: {cxs_exc}")
        elif cxs_resp is not None:
            cxs_status = cxs_resp.status_code
            cxs_body = cxs_resp.content.decode("utf-8", errors="replace")
            if is_waf_challenge(cxs_resp.status_code, cxs_body, cxs_resp.headers):
                cxs_outcome = ExtractionOutcome.PERMANENT_ERROR
                cxs_err = sanitize_error_text(f"[workday] CXS WAF challenge for {wd_parts.cxs_url}")
            elif cxs_resp.status_code == 200:
                try:
                    data = _json.loads(cxs_body)
                except (ValueError, TypeError):
                    data = None
                if isinstance(data, dict):
                    raw = self._parse_cxs_payload(
                        data,
                        parsed,
                        tenant=wd_parts.tenant,
                        site_id=wd_parts.site_id,
                        query_used=query_used,
                    )
                    if raw is not None:
                        resilience_manager.record_success(host)
                        return ExtractionResult(
                            outcome=ExtractionOutcome.SUCCESS,
                            raw=raw,
                            status_code=200,
                            attempts=total_attempts,
                        )
                cxs_outcome = ExtractionOutcome.PARSE_ERROR
                cxs_err = sanitize_error_text(f"[workday] Missing jobPostingInfo in CXS response for {wd_parts.cxs_url}")
            else:
                cxs_outcome = map_status_or_exception_to_outcome(status_code=cxs_resp.status_code)
                cxs_err = sanitize_error_text(f"[workday] CXS HTTP {cxs_resp.status_code} for {wd_parts.cxs_url}")

        # 2. Fallback path: Canonical HTML page (JSON-LD & postingAvailable check)
        html_resp, html_exc, html_attempts = await self._get_with_short_retry(
            wd_parts.canonical_posting_url,
            client,
            accept="text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
        )
        total_attempts += html_attempts

        if html_exc is not None:
            resilience_manager.record_failure(host)
            outcome = map_status_or_exception_to_outcome(exception=html_exc)
            return ExtractionResult(
                outcome=outcome,
                raw=None,
                status_code=cxs_status,
                error_summary=sanitize_error_text(f"[workday] HTML fallback error for {wd_parts.canonical_posting_url}: {html_exc}"),
                attempts=total_attempts,
            )

        assert html_resp is not None
        html_text = html_resp.content.decode("utf-8", errors="replace")

        if html_resp.status_code in (404, 410):
            return ExtractionResult(
                outcome=ExtractionOutcome.NOT_FOUND,
                raw=None,
                status_code=html_resp.status_code,
                error_summary=sanitize_error_text(f"[workday] HTML HTTP {html_resp.status_code} for {wd_parts.canonical_posting_url}"),
                attempts=total_attempts,
            )

        if is_workday_posting_unavailable(html_text):
            return ExtractionResult(
                outcome=ExtractionOutcome.NOT_FOUND,
                raw=None,
                status_code=html_resp.status_code,
                error_summary=sanitize_error_text(f"[workday] postingAvailable=false for {wd_parts.canonical_posting_url}"),
                attempts=total_attempts,
            )

        if is_waf_challenge(html_resp.status_code, html_text, html_resp.headers):
            resilience_manager.record_failure(host)
            return ExtractionResult(
                outcome=ExtractionOutcome.PERMANENT_ERROR,
                raw=None,
                status_code=html_resp.status_code,
                error_summary=sanitize_error_text(f"[workday] HTML WAF challenge for {wd_parts.canonical_posting_url}"),
                attempts=total_attempts,
            )

        if html_resp.status_code == 200:
            raw_html_posting = self._parse_html_fallback(
                html_text,
                parsed,
                tenant=wd_parts.tenant,
                site_id=wd_parts.site_id,
                query_used=query_used,
            )
            if raw_html_posting is not None:
                resilience_manager.record_success(host)
                return ExtractionResult(
                    outcome=ExtractionOutcome.SUCCESS,
                    raw=raw_html_posting,
                    status_code=200,
                    attempts=total_attempts,
                )

        # Record upstream failure only when server/network errors prevented extraction
        if html_resp.status_code in (429, 500, 502, 503, 504):
            resilience_manager.record_failure(host)
            best_outcome = map_status_or_exception_to_outcome(status_code=html_resp.status_code)
            best_status = html_resp.status_code
            best_err = sanitize_error_text(f"[workday] HTML HTTP {html_resp.status_code} for {wd_parts.canonical_posting_url}")
        else:
            best_outcome = cxs_outcome if cxs_outcome != ExtractionOutcome.NOT_FOUND else map_status_or_exception_to_outcome(status_code=html_resp.status_code)
            best_status = html_resp.status_code if html_resp.status_code != 200 else cxs_status
            best_err = cxs_err or sanitize_error_text(f"[workday] Incomplete HTML fallback for {wd_parts.canonical_posting_url}")

        return ExtractionResult(
            outcome=best_outcome,
            raw=None,
            status_code=best_status,
            error_summary=best_err,
            attempts=total_attempts,
        )

    async def fetch_raw(
        self,
        parsed: ParsedATSUrl,
        client: httpx.AsyncClient,
        fallback_snippet: str | None = None,
        query_used: str = "",
    ) -> RawJobPosting | None:
        res = await self.fetch_raw_result(parsed, client, fallback_snippet, query_used)
        if res.outcome == ExtractionOutcome.NOT_FOUND:
            return None
        if res.raw is not None:
            return res.raw
        if res.status_code is not None and res.status_code != 200:
            raise httpx.HTTPStatusError(
                f"HTTP Error {res.status_code}",
                request=httpx.Request("GET", parsed.raw_url),
                response=httpx.Response(res.status_code),
            )
        raise RuntimeError(res.error_summary or "Workday fetch failed")

    async def fetch_result(
        self,
        parsed: ParsedATSUrl,
        client: httpx.AsyncClient,
        fallback_snippet: str | None = None,
        query_used: str = "",
    ) -> tuple[JobListing | None, ExtractionResult]:
        from src.project_files.models import ExtractionMethod

        res = await self.fetch_raw_result(parsed, client, fallback_snippet, query_used)
        if res.outcome == ExtractionOutcome.NOT_FOUND:
            return None, res
        if res.outcome == ExtractionOutcome.SUCCESS and res.raw is not None:
            is_jsonld = res.raw.raw_fields.get("_extraction_method") == "json_ld"
            canonical = JobExtractionService.extract(res.raw)
            if is_jsonld:
                updated_eligibility = canonical.eligibility
                if updated_eligibility is not None and updated_eligibility.facts:
                    updated_eligibility = updated_eligibility.model_copy(
                        update={
                            "facts": [
                                f.model_copy(update={"method": ExtractionMethod.JSON_LD})
                                if f.method == ExtractionMethod.ATS_API
                                else f
                                for f in updated_eligibility.facts
                            ]
                        }
                    )
                canonical = canonical.model_copy(
                    update={
                        "eligibility": updated_eligibility,
                        "field_evidence": [
                            ev.model_copy(update={"method": ExtractionMethod.JSON_LD})
                            if ev.method == ExtractionMethod.ATS_API
                            else ev
                            for ev in canonical.field_evidence
                        ],
                    }
                )
            listing = CanonicalJobAdapter.to_listing(canonical)
            if is_jsonld:
                listing.data_source = "scrape"
            return listing, res
        listing = _fallback(parsed, fallback_snippet, query_used)
        listing.extraction_outcome = res.outcome.value
        listing.degraded_from = "api"
        res.degraded_from = "api"
        return listing, res

    async def fetch(
        self,
        parsed: ParsedATSUrl,
        client: httpx.AsyncClient,
        fallback_snippet: str | None = None,
        query_used: str = "",
    ) -> JobListing | None:
        listing, _ = await self.fetch_result(parsed, client, fallback_snippet, query_used)
        return listing


ATS_CLIENTS: dict[str, object] = {
    "greenhouse": GreenhouseClient(),
    "lever": LeverClient(),
    "ashby": AshbyClient(),
    "smartrecruiters": SmartRecruitersClient(),
    "workable": WorkableClient(),
    "bamboohr": BambooHRClient(),
    "recruitee": RecruiteeClient(),
    "workday": WorkdayClient(),
}
