"""Generic extraction for ATS job pages that do not have a dedicated API client."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import html
import json
import logging
import re
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from src.project_files.ats_url_parser import (
    ParsedATSUrl,
    parse_ats_url,
    parse_teamtailor_custom_domain_url,
)
from src.project_files.cache_store import cache_store
from src.project_files.canonical_job_adapter import CanonicalJobAdapter
from src.project_files.http_resilience import fetch_page_with_cap, resilience_manager, CircuitBreakerOpenError
from src.project_files.job_extraction_service import JobExtractionService, RawJobPosting
from src.project_files.logo_extractor import extract_company_logo_for_provider
from src.project_files.models import JobListing
from src.project_files.extraction_outcome import (
    ExtractionOutcome,
    ExtractionResult,
    map_status_or_exception_to_outcome,
    sanitize_error_text,
)
from src.project_files.http_headers import browser_headers
from src.project_files.field_normalizer import (
    clean_html_to_markdown,
    clean_title,
    description_quality,
    extract_labeled_fields,
    humanize_slug,
    normalize_fields,
    normalize_job_type,
    normalize_job_type_from_text,
    normalize_work_model,
    parse_datetime,
    to_markdown,
)
from src.project_files.work_model import resolve_work_model, strip_li_tags

logger = logging.getLogger(__name__)


def _is_waf_challenge(text: str) -> bool:
    return any(
        marker in text
        for marker in (
            "AwsWafIntegration",
            "awswaf.com",
            "awsWafCookieDomainList",
            "challenge-container",
        )
    )


def _parse_url_metadata(url: str, provider: str) -> tuple[str | None, str | None]:
    company = None
    title = None
    try:
        parsed = urlparse(url)
        sub = parsed.netloc.split(".")[0] if "." in parsed.netloc else ""
        if sub and sub.lower() not in ("www", "jobs", "careers"):
            company = humanize_slug(sub)

        if provider == "jobvite" or "jobs.jobvite.com" in parsed.netloc.lower():
            m = re.match(r"^/([^/?#]+)/job/([^/?#]+)", parsed.path)
            if m:
                company = humanize_slug(m.group(1))

        m = re.search(r"/JobDetail/([^/?#]+)", parsed.path, re.IGNORECASE)
        if m:
            slug = m.group(1).replace("-", " ")
            title = humanize_slug(slug)
        elif provider == "teamtailor":
            m = re.search(r"/jobs/\d+-([^/?#]+)", parsed.path)
            if m:
                title = humanize_slug(m.group(1).replace("-", " "))
    except Exception:
        pass
    return company, title


def _text(value: Any) -> str | None:
    if isinstance(value, str):
        value = value.strip()
        return value or None
    if isinstance(value, dict):
        if any(key in value for key in ("addressLocality", "addressRegion", "addressCountry")):
            parts = [value.get(key) for key in ("addressLocality", "addressRegion", "addressCountry")]
            return ", ".join(str(part).strip() for part in parts if part)
        for key in ("name", "value", "text", "address", "addressLocality", "addressRegion", "addressCountry"):
            result = _text(value.get(key))
            if result:
                return result
    if isinstance(value, list):
        values = [_text(item) for item in value]
        values = [item for item in values if item]
        return ", ".join(values) if values else None
    return None


def _json_ld_documents(soup: BeautifulSoup) -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            payload = json.loads(script.string or script.get_text())
        except (TypeError, json.JSONDecodeError):
            continue
        values = payload if isinstance(payload, list) else [payload]
        for item in values:
            if not isinstance(item, dict):
                continue
            graph = item.get("@graph")
            if isinstance(graph, list):
                documents.extend(node for node in graph if isinstance(node, dict))
            else:
                documents.append(item)
    return documents


_COMPANY_TITLE_RE = re.compile(
    r"(?:\s+at\s+|\s+@\s*|^Careers\s+at\s+)(.+?)(?:\s+[|·–—-]\s+|$)",
    re.IGNORECASE,
)


def _company_from_title(title: str) -> str | None:
    match = _COMPANY_TITLE_RE.search(title)
    return match.group(1).strip(" .") if match else None


def _clean_html_text(value: Any) -> str | None:
    """Decode HTML entities and convert description body into clean Markdown."""
    return to_markdown(value)


def _meta_content(soup: BeautifulSoup, attr: str, name: str) -> str | None:
    node = soup.find("meta", attrs={attr: name})
    if node is None:
        return None
    content = node.get("content")
    return content.strip() if isinstance(content, str) and content.strip() else None


def _jazzhr_share_attributes(soup: BeautifulSoup) -> dict[str, str | None]:
    """Read the labelled attribute rows JazzHR renders on its share pages."""
    result: dict[str, str | None] = {"location": None, "job_type": None, "experience": None}
    for node in soup.select("#focus-subheader-content-info li, .focus-subheader-content-info li"):
        text = node.get_text(" ", strip=True)
        icon = node.select_one("i, span.fa, .fa")
        icon_classes = " ".join(icon.get("class", [])) if icon else ""
        if "map-marker" in icon_classes:
            result["location"] = text or None
        elif "clock" in icon_classes:
            result["job_type"] = text or None
        elif "graduation" in icon_classes:
            result["experience"] = text or None
    return result


def _build_workday_cxs_url(url: str) -> str | None:
    """Derive the Workday public CXS endpoint from a job URL."""
    from src.project_files.ats_url_parser import build_workday_cxs_url

    return build_workday_cxs_url(url)


def _build_snippet_fallback(
    provider: str,
    url: str,
    query_used: str,
    title: str,
    company: str,
    location: str | None,
    job_type: str | None,
    snippet: str,
    search_title: str | None,
) -> JobListing:
    url_company, url_title = _parse_url_metadata(url, provider)
    fallback_title = clean_title(search_title) if search_title and search_title != "Job" else (url_title or clean_title(title, snippet))
    fallback_company = url_company or company
    host_id = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    parsed_ats = parse_ats_url(url)
    company_slug = parsed_ats.company_slug if parsed_ats else None

    raw = RawJobPosting(
        provider=provider,
        source_url=url,
        apply_url=url,
        provider_job_id=host_id,
        company_slug=company_slug,
        raw_title=fallback_title,
        raw_company=fallback_company,
        raw_location=location,
        raw_description=None,
        raw_employment_type=job_type,
        raw_date=None,
        raw_fields={"snippet": snippet},
        description_is_authentic=False,
        query_used=query_used,
    )
    canonical = JobExtractionService.extract(raw)
    listing = CanonicalJobAdapter.to_listing(canonical)
    listing.id = f"{provider}:{host_id}"
    listing.provider = provider
    listing.data_source = "snippet"
    listing.apply_url = url
    listing.source_url = url
    listing.query_used = query_used
    listing.ats_source = provider
    listing.description = None
    listing.description_ok = False
    listing.extraction_confidence = None
    listing._compute_confidence()
    return listing


_CLOSED_BANNER_PHRASES = (
    "this position is no longer active",
    "either the position was filled, or the ad has expired",
    "the job listing no longer exists",
    "this job is no longer available",
)

_TT_DL_KEY_MAP = {
    "department": "department",
    "departamento": "department",
    "affärsområde": "department",
    "afdeling": "department",
    "abteilung": "department",
    "département": "department",
    "division": "department",
    "role": "role",
    "puesto": "role",
    "roll": "role",
    "location": "location",
    "locations": "location",
    "ubicación": "location",
    "ubicaciones": "location",
    "plats": "location",
    "platser": "location",
    "sted": "location",
    "standort": "location",
    "lieu": "location",
    "remote status": "work_model",
    "workplace type": "work_model",
    "work arrangement": "work_model",
    "estado remoto": "work_model",
    "modalidad": "work_model",
    "arbetsplats": "work_model",
    "arbeitsmodell": "work_model",
    "employment type": "employment_type",
    "employment contracts": "employment_type",
    "tipo de empleo": "employment_type",
    "anställningsform": "employment_type",
    "ansættelsesform": "employment_type",
    "anstellungsart": "employment_type",
    "type d'emploi": "employment_type",
    "salary": "salary",
    "salario": "salary",
    "lön": "salary",
    "gehalt": "salary",
    "compensation": "salary",
}

_TRAILING_TEAMTAILOR_CTA_RE = re.compile(
    r"\n+(?:#+\s*)?(?:Already\s+working\s+at|¿Ya\s+trabajas\s+en|Jobbar\s+du\s+redan\s+på)\b[\s\S]*$",
    re.IGNORECASE,
)


def _format_teamtailor_locations(
    *,
    dl_location: str | None,
    cover_location: str | None,
    jsonld_location: Any,
) -> tuple[str | None, str | None]:
    """Return (compact_display_location, raw_location_preserved) for Teamtailor."""
    raw_jsonld_loc = _text(jsonld_location)
    compact_items: list[str] = []
    places = jsonld_location if isinstance(jsonld_location, list) else ([jsonld_location] if jsonld_location else [])
    for place in places:
        if not isinstance(place, dict):
            continue
        addr = place.get("address")
        if not isinstance(addr, dict):
            continue
        city = str(addr.get("addressLocality") or "").strip()
        region = str(addr.get("addressRegion") or "").strip()
        country_raw = addr.get("addressCountry")
        if isinstance(country_raw, dict):
            country = str(country_raw.get("name") or country_raw.get("@id") or "").strip()
        else:
            country = str(country_raw or "").strip()

        label = ""
        if city and country and city.lower() != country.lower():
            label = f"{city}, {country}"
        elif city:
            label = city
        elif region:
            label = region
        elif country:
            label = country
        if label and label not in compact_items:
            compact_items.append(label)

    raw_loc = raw_jsonld_loc or dl_location or cover_location
    if dl_location and len(dl_location) <= 80:
        return dl_location, raw_loc or dl_location
    if cover_location and len(cover_location) <= 80:
        return cover_location, raw_loc or cover_location
    if compact_items:
        joined = "; ".join(compact_items)
        if len(joined) > 80:
            fitted: list[str] = []
            for item in compact_items:
                cand = "; ".join([*fitted, item])
                if len(cand) <= 68:
                    fitted.append(item)
                else:
                    break
            rem = len(compact_items) - len(fitted)
            if fitted and rem > 0:
                joined = f"{'; '.join(fitted)} (+{rem} more)"
            elif fitted:
                joined = "; ".join(fitted)
            else:
                joined = compact_items[0][:77] + "..."
        return joined, raw_loc or joined
    if dl_location:
        return dl_location[:77] + "...", raw_loc or dl_location
    if raw_jsonld_loc:
        return (raw_jsonld_loc[:77] + "..." if len(raw_jsonld_loc) > 80 else raw_jsonld_loc), raw_jsonld_loc
    return None, None


def _extract_teamtailor_dom(
    soup: BeautifulSoup,
    document: dict[str, Any],
) -> dict[str, Any]:
    """Extract structured Teamtailor <dl>, section.block-cover, H1, and prose description."""
    fields: dict[str, Any] = {"raw_dl": {}}
    for dl in soup.select("dl"):
        dts = dl.select("dt")
        dds = dl.select("dd")
        for dt, dd in zip(dts, dds):
            key = dt.get_text(" ", strip=True)
            val = dd.get_text(" ", strip=True)
            if not key or not val:
                continue
            fields["raw_dl"][key] = val
            mapped = _TT_DL_KEY_MAP.get(key.lower().rstrip(":"))
            if mapped and not fields.get(mapped):
                fields[mapped] = val

    cover = soup.select_one("section.block-cover")
    cover_tokens: list[str] = []
    h1_title: str | None = None
    if cover is not None:
        h1_node = cover.select_one("h1")
        if h1_node:
            h1_title = h1_node.get_text(" ", strip=True) or None
        # Collect header breadcrumb line immediately preceding h1 (or top metadata strip)
        meta_parts: list[str] = []
        for node in cover.find_all(["span", "p", "div", "li"]):
            if h1_node and (node == h1_node or h1_node in node.parents or node in h1_node.descendants):
                continue
            if node.name in ("a", "button") or node.find(["a", "button", "h1"]):
                continue
            if not node.find(["span", "p", "div", "li"]):
                txt = node.get_text(" ", strip=True)
                if txt and txt != "·":
                    meta_parts.append(txt)
        for part in meta_parts:
            for piece in re.split(r"\s*[·|]\s*", part):
                clean_piece = piece.strip()
                if clean_piece and clean_piece not in cover_tokens:
                    cover_tokens.append(clean_piece)
    else:
        main_h1 = soup.select_one("main h1, h1")
        if main_h1:
            h1_title = main_h1.get_text(" ", strip=True) or None

    org_name = _text(document.get("hiringOrganization"))
    known_non_loc = {
        v.lower()
        for v in (org_name, fields.get("department"), fields.get("role"), h1_title)
        if v
    }
    cover_location: str | None = None
    cover_work_model: str | None = None
    for tok in cover_tokens:
        low = tok.lower()
        if low in known_non_loc:
            continue
        wm = resolve_work_model(workplace_type=tok)
        if wm.value is not None:
            if not cover_work_model:
                cover_work_model = tok
            continue
        if not cover_location and len(tok) <= 80:
            cover_location = tok

    if cover_work_model and not fields.get("work_model"):
        fields["work_model"] = cover_work_model

    display_loc, raw_loc = _format_teamtailor_locations(
        dl_location=fields.get("location"),
        cover_location=cover_location,
        jsonld_location=document.get("jobLocation"),
    )
    fields["location"] = display_loc
    fields["raw_location_preserved"] = raw_loc
    fields["h1_title"] = h1_title

    prose_el = soup.select_one("main div.prose, div.prose")
    if prose_el is not None:
        prose_md = to_markdown(str(prose_el))
        if prose_md:
            prose_md = _TRAILING_TEAMTAILOR_CTA_RE.sub("", prose_md).strip()
        fields["prose_description"] = prose_md or None
        fields["is_dom_prose"] = bool(prose_md)

    return fields


async def enrich_ats_page_result(
    url: str,
    provider: str,
    search_title: str,
    snippet: str,
    query_used: str,
    client: httpx.AsyncClient,
    *,
    prefetched: tuple[int, str, str] | None = None,
    parsed_ats: ParsedATSUrl | None = None,
) -> tuple[JobListing | None, ExtractionResult]:
    """Fetch a generic ATS page and return (listing, extraction_result)."""
    cached_listing = cache_store.get_url_cache(url)
    if cached_listing is not None:
        return cached_listing, ExtractionResult(outcome=ExtractionOutcome.SUCCESS, status_code=200, attempts=1)

    title = search_title or snippet or url
    company = _company_from_title(title) or "Unknown"
    labeled = extract_labeled_fields(f"{title} {snippet}")
    location = labeled.get("location")
    job_type = labeled.get("employment_type")
    work_model = labeled.get("work_model")
    posted_at = None
    department = None
    structured_source_found = False
    resolved_apply_url = url
    description: str | None = None
    jsonld_location_type: str | None = None
    page_fields: dict[str, str] = {}
    secondary_failed = False

    # 1. Delegate Workday postings to the single authoritative WorkdayClient path.
    if provider == "workday" or "myworkdayjobs.com" in url:
        from src.project_files.ats_api_client import WorkdayClient

        parsed_wd = parse_ats_url(url)
        if parsed_wd is None:
            return None, ExtractionResult(outcome=ExtractionOutcome.NOT_FOUND, status_code=404, attempts=0)
        listing, res = await WorkdayClient().fetch_result(
            parsed_wd,
            client,
            fallback_snippet=search_title or snippet,
            query_used=query_used,
        )
        if listing is not None and res.outcome == ExtractionOutcome.SUCCESS:
            cache_store.set_url_cache(url, listing)
        return listing, res

    host = resilience_manager.extract_host(url)
    raw_location_preserved: str | None = None
    extra_raw_fields: dict[str, Any] = {}

    if not resilience_manager.is_host_open(host) and prefetched is None:
        logger.warning(f"[{provider}] Circuit breaker is open for host '{host}'; falling back to snippet row")
        fallback_listing = _build_snippet_fallback(
            provider=provider,
            url=url,
            query_used=query_used,
            title=title,
            company=company,
            location=location,
            job_type=job_type,
            snippet=snippet,
            search_title=search_title,
        )
        fallback_listing.extraction_outcome = "retryable_error"
        fallback_listing.degraded_from = "page_scrape"
        res = ExtractionResult(
            outcome=ExtractionOutcome.RETRYABLE_ERROR,
            error_summary=f"Circuit breaker is open for host '{host}'",
            attempts=0,
            degraded_from="page_scrape",
        )
        return fallback_listing, res

    try:
        if prefetched is not None:
            status_code, page_content, final_url = prefetched
            if final_url:
                url = final_url
        else:
            status_code, page_content, _ = await fetch_page_with_cap(
                client, url, headers=browser_headers(url), timeout=10.0, follow_redirects=True
            )
        if status_code == 202 or _is_waf_challenge(page_content):
            logger.debug(f"[{provider}] WAF challenge page detected for {url}; treating as fetch failure")
            fallback_listing = _build_snippet_fallback(
                provider=provider,
                url=url,
                query_used=query_used,
                title=title,
                company=company,
                location=location,
                job_type=job_type,
                snippet=snippet,
                search_title=search_title,
            )
            fallback_listing.extraction_outcome = "permanent_error"
            fallback_listing.degraded_from = "page_scrape"
            res = ExtractionResult(
                outcome=ExtractionOutcome.PERMANENT_ERROR,
                status_code=status_code,
                error_summary="WAF challenge or bot block detected",
                attempts=1,
                degraded_from="page_scrape",
            )
            return fallback_listing, res

        if status_code in (404, 410):
            logger.debug(f"[{provider}] Job listing returned HTTP {status_code}: {url}")
            return None, ExtractionResult(
                outcome=ExtractionOutcome.NOT_FOUND,
                status_code=status_code,
                attempts=1,
            )

        if status_code >= 400:
            outcome = map_status_or_exception_to_outcome(status_code=status_code)
            fallback_listing = _build_snippet_fallback(
                provider=provider,
                url=url,
                query_used=query_used,
                title=title,
                company=company,
                location=location,
                job_type=job_type,
                snippet=snippet,
                search_title=search_title,
            )
            fallback_listing.extraction_outcome = outcome.value
            fallback_listing.degraded_from = "page_scrape"
            res = ExtractionResult(
                outcome=outcome,
                status_code=status_code,
                error_summary=f"HTTP {status_code} error fetching page",
                attempts=1,
                degraded_from="page_scrape",
            )
            return fallback_listing, res

        soup = BeautifulSoup(page_content, "lxml")
        page_text = " ".join(soup.stripped_strings)
        lower_page_text = page_text.lower()

        # Drop expired/non-job pages (e.g. Jobvite expired/catalog redirects, or explicit 404/closed alert messages)
        if any(phrase in lower_page_text for phrase in _CLOSED_BANNER_PHRASES) or soup.select_one(".jv-alert, .jv-page-error"):
            logger.debug(f"[{provider}] Job listing no longer exists / expired: {url}")
            return None, ExtractionResult(outcome=ExtractionOutcome.NOT_FOUND, status_code=status_code, attempts=1)

        if provider == "teamtailor":
            resolved_tt = parsed_ats or parse_ats_url(url)
            if resolved_tt is None or resolved_tt.ats != "teamtailor":
                resolved_tt = parse_teamtailor_custom_domain_url(url, html_text=page_content, final_url=url)
            if resolved_tt is None or resolved_tt.ats != "teamtailor":
                logger.debug(f"[{provider}] Rejected non-Teamtailor/non-job page: {url}")
                return None, ExtractionResult(outcome=ExtractionOutcome.NOT_FOUND, status_code=status_code, attempts=1)
            parsed_ats = resolved_tt

        document = next((item for item in _json_ld_documents(soup) if item.get("@type") == "JobPosting"), {})
        if provider == "jobvite" and not document:
            logger.debug(f"[{provider}] Non-job / catalog page detected (no JobPosting): {url}")
            return None, ExtractionResult(outcome=ExtractionOutcome.NOT_FOUND, status_code=status_code, attempts=1)

        structured_source_found = bool(document)
        tt_fields: dict[str, Any] = _extract_teamtailor_dom(soup, document) if provider == "teamtailor" else {}

        title = _text(document.get("title")) or tt_fields.get("h1_title") or _meta_content(soup, "property", "og:title") or title
        organization = document.get("hiringOrganization")
        company = _text(organization) or _company_from_title(title) or company
        if company == "Unknown" or not company:
            url_company, _ = _parse_url_metadata(url, provider)
            company = url_company or company

        if provider == "teamtailor":
            location = tt_fields.get("location") or location
            raw_location_preserved = tt_fields.get("raw_location_preserved")
            for k in ("department", "employment_type", "work_model", "salary", "role"):
                if tt_fields.get(k):
                    page_fields[k] = tt_fields[k]
            if tt_fields.get("raw_dl"):
                extra_raw_fields["raw_dl"] = tt_fields["raw_dl"]
            if tt_fields.get("salary"):
                extra_raw_fields["salary"] = tt_fields["salary"]
        else:
            location = _text(document.get("jobLocation")) or location

        job_type = normalize_job_type(_text(document.get("employmentType"))) or normalize_job_type(page_fields.get("employment_type")) or normalize_job_type(job_type)
        is_dom_scraped = False
        raw_jsonld_desc = _text(document.get("description"))
        if provider == "teamtailor" and tt_fields.get("prose_description"):
            description = tt_fields["prose_description"]
            is_dom_scraped = not bool(document)
            structured_source_found = True
        else:
            description = _clean_html_text(strip_li_tags(raw_jsonld_desc)) or description
        if not description:
            main_el = soup.select_one("section.js_views, [data-careersite-propertyid='description'], [itemprop='description'], main, article, [role='main']")
            if main_el:
                description = _clean_html_text(str(main_el))
                is_dom_scraped = True
        jsonld_location_type = _text(document.get("jobLocationType"))
        wm_res = resolve_work_model(
            workplace_type=page_fields.get("work_model"),
            jsonld_location_type=jsonld_location_type,
            location=location,
            title=title,
            trusted_description=raw_jsonld_desc or description,
        )
        work_model = wm_res.value or work_model
        posted_at = parse_datetime(document.get("datePosted"))
        if posted_at is None:
            date_meta = soup.find("meta", attrs={"property": "datePosted"}) or soup.find("meta", attrs={"name": "datePosted"})
            posted_at = parse_datetime(date_meta.get("content") if date_meta else None)
            structured_source_found = structured_source_found or posted_at is not None
        department = page_fields.get("department") or _text(document.get("occupationalCategory")) or _text(document.get("department"))

        # SAP SuccessFactors career pages
        if "jobs.sap.com" in url:
            company = company if company != "Unknown" else "SAP"
            for token in soup.select(".joblayouttoken"):
                label_node = token.select_one(".joblayouttoken-label")
                if not label_node:
                    continue
                label = label_node.get_text(" ", strip=True).lower().rstrip(":")
                value = token.get_text(" ", strip=True)
                value = re.sub(rf"^{re.escape(label)}\s*:\s*", "", value, flags=re.IGNORECASE).strip()
                if not value:
                    continue
                if label == "location":
                    page_fields["location"] = value
                elif label == "employment type":
                    page_fields["employment_type"] = value
                elif label == "posted date":
                    posted_at = parse_datetime(value)
                elif label == "office attendance":
                    page_fields["work_model"] = value
                elif label in {"work area", "department"}:
                    page_fields["department"] = value
            sap_description = soup.select_one('[data-careersite-propertyid="description"], [itemprop="description"]')
            if sap_description:
                description = to_markdown(str(sap_description))
                is_dom_scraped = True
        elif provider != "teamtailor":
            page_fields.update(extract_labeled_fields(page_text))

        location = location or page_fields.get("location")
        job_type = job_type or normalize_job_type(page_fields.get("employment_type"))
        work_model = work_model or normalize_work_model(
            page_fields.get("work_model"),
            location=location,
            title=title,
            description=description,
            snippet=snippet,
        )
        department = department or page_fields.get("department")
        if job_type is None:
            type_scan_text = " ".join(
                part for part in (title, snippet, page_fields.get("employment_type", ""), description or "", location or "") if part
            )
            job_type = normalize_job_type_from_text(type_scan_text, title=title)
        structured_source_found = structured_source_found or bool(location or job_type or work_model or department or posted_at)

        if "taleo.net" in url:
            for panel in soup.select(".contentlinepanel"):
                label = panel.select_one("h2, .subtitle, .title")
                if not label:
                    continue
                label_text = label.get_text(" ", strip=True).lower()
                value = panel.select_one(".text")
                value_text = value.get_text(" ", strip=True) if value else ""
                if not value_text or value_text.lower() == label_text:
                    continue
                if "location" in label_text and not location:
                    location = value_text
                elif "organization" in label_text and company == "Unknown":
                    company = value_text
                elif ("job type" in label_text or "employment" in label_text) and not page_fields.get("employment_type"):
                    page_fields["employment_type"] = value_text
                elif "posting date" in label_text or "posted date" in label_text:
                    posted_at = posted_at or parse_datetime(value_text)

        if "jobs.personio.com" in url:
            raw_html = page_content
            office_match = re.search(r'"main_office"\s*:\s*"([^"]+)"', raw_html)
            schedule_match = re.search(r'"schedule"\s*:\s*"([^"]+)"', raw_html)
            employment_like = re.search(r'"employment_type"\s*:\s*"([^"]+)"', raw_html)
            department_match = re.search(r'"department"\s*:\s*"([^"]+)"', raw_html)
            subcompany_match = re.search(r'"subcompany"\s*:\s*"([^"]+)"', raw_html)
            location = location or (office_match.group(1) if office_match else None)
            if not page_fields.get("employment_type"):
                matched_type = (employment_like or schedule_match)
                if matched_type:
                    page_fields["employment_type"] = matched_type.group(1)
            department = department or (department_match.group(1) if department_match else None)
            if company == "Unknown":
                if subcompany_match:
                    company = subcompany_match.group(1)
                else:
                    og_title = _meta_content(soup, "property", "og:title")
                    if og_title:
                        org_match = re.search(r"\s*\|\s*Jobs? at Work for\s+(.+)$", og_title, re.IGNORECASE)
                        if org_match:
                            company = org_match.group(1).strip()
            job_type = job_type or page_fields.get("employment_type")
            structured_source_found = structured_source_found or bool(location or job_type or department)

        if "applytojob.com/app/share" in url:
            title_node = soup.select_one(".focus-subheader-content h1 a, .focus-subheader h1, h1")
            if title_node:
                title = title_node.get_text(" ", strip=True) or title
            share_link = soup.select_one("a[href*='/apply/']")
            if share_link and share_link.get("href"):
                resolved_apply_url = urljoin(url, share_link.get("href"))
            share_attrs = _jazzhr_share_attributes(soup)
            location = location or share_attrs.get("location")
            job_type = job_type or normalize_job_type(share_attrs.get("job_type"))
            work_model = work_model or normalize_work_model(
                None,
                location=location or share_attrs.get("location"),
                title=title,
            )
            structured_source_found = structured_source_found or bool(title_node or any(share_attrs.values()))
            if company == "Unknown":
                og_title = _meta_content(soup, "property", "og:title")
                if og_title:
                    org_match = re.search(r"\s-\s(.+?)\s+-\s+Career\s+Page\s*$", og_title, re.IGNORECASE)
                    if org_match:
                        company = org_match.group(1).strip()
            if resolved_apply_url and resolved_apply_url != url:
                try:
                    apply_status, apply_content, _ = await fetch_page_with_cap(
                        client,
                        resolved_apply_url,
                        headers=browser_headers(resolved_apply_url),
                        timeout=12.0,
                        follow_redirects=True,
                    )
                    if apply_status == 200:
                        apply_soup = BeautifulSoup(apply_content, "lxml")
                        apply_doc = next((item for item in _json_ld_documents(apply_soup) if item.get("@type") == "JobPosting"), {})
                        if apply_doc:
                            structured_source_found = True
                            description = _clean_html_text(_text(apply_doc.get("description"))) or description
                            is_dom_scraped = False
                            title = _text(apply_doc.get("title")) or title
                            org = _text(apply_doc.get("hiringOrganization"))
                            if org:
                                company = org
                            apply_location = _text(apply_doc.get("jobLocation"))
                            location = apply_location or location
                            job_type = job_type or normalize_job_type(_text(apply_doc.get("employmentType")))
                            posted_at = posted_at or parse_datetime(apply_doc.get("datePosted"))
                            apply_jsonld_loc_type = _text(apply_doc.get("jobLocationType"))
                            apply_raw_desc = _text(apply_doc.get("description"))
                            apply_wm_res = resolve_work_model(
                                jsonld_location_type=apply_jsonld_loc_type,
                                location=location,
                                title=title,
                                trusted_description=apply_raw_desc,
                            )
                            work_model = apply_wm_res.value or work_model
                            jsonld_location_type = apply_jsonld_loc_type or jsonld_location_type
                    else:
                        secondary_failed = True
                except (httpx.HTTPError, ValueError):
                    secondary_failed = True
    except Exception as exc:
        outcome = map_status_or_exception_to_outcome(exception=exc)
        fallback_listing = _build_snippet_fallback(
            provider=provider,
            url=url,
            query_used=query_used,
            title=title,
            company=company,
            location=location,
            job_type=job_type,
            snippet=snippet,
            search_title=search_title,
        )
        fallback_listing.extraction_outcome = outcome.value
        fallback_listing.degraded_from = "page_scrape"
        res = ExtractionResult(
            outcome=outcome,
            error_summary=sanitize_error_text(str(exc)),
            attempts=1,
            degraded_from="page_scrape",
        )
        return fallback_listing, res

    host_id = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    parsed_ats = parsed_ats or parse_ats_url(url)
    if parsed_ats is None and provider == "teamtailor":
        parsed_ats = parse_teamtailor_custom_domain_url(url, html_text=page_content, final_url=url)
    company_slug = parsed_ats.company_slug if parsed_ats else None
    canonical_provider_id = (
        parsed_ats.job_id
        if provider == "teamtailor" and parsed_ats and parsed_ats.job_id
        else host_id
    )

    is_authentic = bool(description and structured_source_found)
    active_doc = apply_doc if ('apply_doc' in locals() and apply_doc) else document
    active_soup = apply_soup if ('apply_soup' in locals() and apply_soup is not None) else soup
    logo_res = extract_company_logo_for_provider(
        provider,
        soup=active_soup,
        json_ld_doc=active_doc,
        page_url=url,
        company_name=company if company != "Unknown" else None,
    )

    raw = RawJobPosting(
        provider=provider,
        source_url=url,
        apply_url=resolved_apply_url,
        provider_job_id=canonical_provider_id,
        company_slug=company_slug,
        raw_title=title,
        raw_company=company,
        raw_location=location,
        raw_description=description,
        raw_workplace_type=page_fields.get("work_model"),
        raw_department=department or page_fields.get("department"),
        raw_employment_type=job_type or page_fields.get("employment_type"),
        raw_date=posted_at,
        raw_fields={
            "json_ld": active_doc,
            "jobLocationType": jsonld_location_type,
            **({"raw_location_preserved": raw_location_preserved} if raw_location_preserved else {}),
            **({"company_logo_url": logo_res.url, "company_logo_source": logo_res.source, "company_logo_verified": logo_res.verified} if logo_res.url else {}),
            **extra_raw_fields,
            **page_fields,
        },
        description_is_authentic=is_authentic,
        query_used=query_used,
    )
    canonical = JobExtractionService.extract(raw)
    listing = CanonicalJobAdapter.to_listing(canonical)
    listing.id = canonical.id if (provider == "teamtailor" and parsed_ats and parsed_ats.company_slug and parsed_ats.job_id) else f"{provider}:{host_id}"
    listing.provider = provider
    listing.data_source = "scrape" if structured_source_found else "snippet"
    listing.apply_url = resolved_apply_url
    listing.source_url = url
    listing.query_used = query_used
    listing.ats_source = provider
    if company_slug and not listing.company_slug:
        listing.company_slug = company_slug
    if raw_location_preserved and not listing.raw_location:
        listing.raw_location = raw_location_preserved
    if logo_res.url and not listing.company_logo_url:
        listing.company_logo_url = logo_res.url
        listing.company_logo_source = logo_res.source
        listing.company_logo_verified = logo_res.verified
    if jsonld_location_type or page_fields.get("work_model"):
        listing.raw_workplace_type = jsonld_location_type or page_fields.get("work_model")
    if department and not listing.department:
        listing.department = department
    if posted_at and not listing.posted_at:
        listing.posted_at = posted_at
    desc_ok = bool(listing.description and description_quality(listing.description, is_dom_scraped=is_dom_scraped))
    listing.description_ok = desc_ok
    if not desc_ok:
        listing.description = None
    listing.extraction_confidence = None
    listing._compute_confidence()
    cache_store.set_url_cache(url, listing)

    outcome = ExtractionOutcome.PARTIAL_SUCCESS if secondary_failed else ExtractionOutcome.SUCCESS
    res = ExtractionResult(
        outcome=outcome,
        raw=raw,
        status_code=status_code if 'status_code' in locals() else 200,
        attempts=1,
    )
    return listing, res


async def enrich_ats_page(
    url: str,
    provider: str,
    search_title: str,
    snippet: str,
    query_used: str,
    client: httpx.AsyncClient,
) -> JobListing | None:
    listing, _ = await enrich_ats_page_result(url, provider, search_title, snippet, query_used, client)
    return listing
