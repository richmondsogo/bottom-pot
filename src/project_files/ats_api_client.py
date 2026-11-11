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

import hashlib
import html
import re
from datetime import datetime, timezone
from typing import Optional

import httpx
from loguru import logger
from bs4 import BeautifulSoup

from src.config import settings
from src.project_files.ats_url_parser import ParsedATSUrl
from src.project_files.exceptions import ParseError, SearchProviderError
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

        title = data.get("title", "")
        location = (data.get("location") or {}).get("name")
        apply_url = data.get("absolute_url") or parsed.raw_url
        company = data.get("company_name") or parsed.company_slug
        raw_content = data.get("content")
        raw_emp = (
            data.get("employment_type")
            or data.get("employmentType")
            or data.get("employment")
        )
        raw_date = data.get("first_published") or data.get("created_at")
        dept = _first_name(data.get("departments") or data.get("department"))

        raw = RawJobPosting(
            provider="greenhouse",
            source_url=parsed.raw_url,
            provider_job_id=parsed.job_id,
            company_slug=parsed.company_slug,
            apply_url=apply_url,
            raw_title=title,
            raw_company=company,
            raw_location=location,
            raw_department=dept,
            raw_employment_type=raw_emp,
            raw_date=raw_date,
            raw_fields=data,
            raw_description=raw_content,
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

        categories = data.get("categories") or {}
        title = data.get("text", "")
        company = _first_name(data.get("company") or data.get("companyName")) or humanize_slug(parsed.company_slug) or "Unknown"
        location = categories.get("location")
        commitment = categories.get("commitment")
        workplace_type = data.get("workplaceType") or data.get("workplace_type")
        opening = data.get("openingPlain") or data.get("opening")
        raw_desc = data.get("descriptionPlain") or data.get("description")
        additional = data.get("additionalPlain") or data.get("additional")
        parts = []
        if opening:
            parts.append(opening)
        if raw_desc:
            parts.append(raw_desc)
        for item in data.get("lists") or []:
            header = item.get("text", "")
            content = item.get("content", "")
            if header:
                parts.append(f"<h3>{header}</h3>")
            if content:
                parts.append(content)
        if additional:
            parts.append(additional)
        combined_desc = "\n\n".join(parts) if parts else (raw_desc or opening or additional)
        apply_url = data.get("applyUrl") or parsed.raw_url
        created_ms = data.get("createdAt")
        dept = _first_name(categories.get("team") or categories.get("department"))

        raw = RawJobPosting(
            provider="lever",
            source_url=parsed.raw_url,
            provider_job_id=parsed.job_id,
            company_slug=parsed.company_slug,
            apply_url=apply_url,
            raw_title=title,
            raw_company=company,
            raw_location=location,
            raw_workplace_type=workplace_type,
            raw_department=dept,
            raw_employment_type=commitment,
            raw_date=created_ms,
            raw_fields=data,
            raw_description=combined_desc,
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

class AshbyClient:
    """
    GET https://api.ashbyhq.com/posting-api/job-posting/{job_id}
    Fields: title, locationName, employmentType, publishedAt, jobUrl
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
        url = f"https://api.ashbyhq.com/posting-api/job-board/{parsed.company_slug}?includeCompensation=true"
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
            target = str(parsed.job_id)
            matched = next((j for j in data["jobs"] if str(j.get("id")) == target), None)
            if matched is None:
                return ExtractionResult(
                    outcome=ExtractionOutcome.NOT_FOUND,
                    raw=None,
                    status_code=404,
                    error_summary=f"[ashby] Job ID {parsed.job_id} not found in board list",
                    attempts=get_current_attempts(),
                )
            data = matched

        title = data.get("title", "")
        location = data.get("locationName")
        apply_url = data.get("applyUrl") or data.get("jobUrl") or parsed.raw_url
        employment_raw = data.get("employmentType")
        raw_workplace_type = data.get("workplaceType") or data.get("workplaceTypeName")
        raw_desc = data.get("descriptionHtml") or data.get("descriptionPlain") or data.get("description")
        raw_date = data.get("publishedAt")
        company = _first_name(data.get("company") or data.get("companyName")) or humanize_slug(parsed.company_slug) or "Unknown"
        dept = data.get("departmentName") or _first_name(data.get("department"))

        raw = RawJobPosting(
            provider="ashby",
            source_url=parsed.raw_url,
            provider_job_id=parsed.job_id,
            company_slug=parsed.company_slug,
            apply_url=apply_url,
            raw_title=title,
            raw_company=company,
            raw_location=location,
            raw_workplace_type=raw_workplace_type,
            raw_department=dept,
            raw_employment_type=employment_raw,
            raw_date=raw_date,
            raw_fields=data,
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

class WorkableClient:
    """
    GET https://{slug}.workable.com/j/{job_id}.json
    Fields: title, location.location_str, remote, created_at, url
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
        url = f"https://apply.workable.com/{parsed.company_slug}/jobs/view/{parsed.job_id}.md"
        try:
            response = await client.get(
                url,
                headers=browser_headers(url, "text/markdown,text/plain;q=0.9,*/*;q=0.8"),
                timeout=_TIMEOUT,
                follow_redirects=True,
            )
            response.raise_for_status()
            markdown = response.text
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
            safe_err = sanitize_error_text(f"[workable] Markdown fetch failed for {url}: {exc}")
            return ExtractionResult(
                outcome=outcome,
                raw=None,
                status_code=None,
                error_summary=safe_err,
                attempts=get_current_attempts(),
            )

        lines = [line.strip() for line in markdown.splitlines() if line.strip()]
        title = lines[0].removeprefix("# ").strip() if lines else ""
        summary = next((line[2:].strip() for line in lines if line.startswith("> ")), "")
        summary_parts = [part.strip() for part in summary.split("·")]
        company = summary_parts[0] if summary_parts else humanize_slug(parsed.company_slug) or "Unknown"
        location = summary_parts[1] if len(summary_parts) > 1 else None
        employment = summary_parts[2] if len(summary_parts) > 2 else None
        posted_match = re.search(r"Posted\s+(.+)$", summary, re.IGNORECASE)
        raw_date = posted_match.group(1) if posted_match else None
        workplace_match = re.search(r"\*\*Workplace:\*\*\s*(.+)", markdown, re.IGNORECASE)
        raw_workplace_type = workplace_match.group(1).strip() if workplace_match else None
        department_match = re.search(r"\*\*Department:\*\*\s*(.+)", markdown, re.IGNORECASE)
        dept = department_match.group(1).strip() if department_match else None

        raw = RawJobPosting(
            provider="workable",
            source_url=parsed.raw_url,
            provider_job_id=parsed.job_id,
            company_slug=parsed.company_slug,
            apply_url=parsed.raw_url,
            extraction_method=ExtractionMethod.SCRAPE,
            raw_title=title or fallback_snippet or parsed.raw_url,
            raw_company=company,
            raw_location=location,
            raw_workplace_type=raw_workplace_type,
            raw_department=dept,
            raw_employment_type=employment,
            raw_date=raw_date,
            raw_fields={"markdown": markdown},
            raw_description=markdown,
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
