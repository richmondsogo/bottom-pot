"""
Teamtailor company-board RSS + HTML fallback monitoring adapter.
"""

from __future__ import annotations

import asyncio
import re
from urllib.parse import quote

import httpx
from loguru import logger

from src.core.clock import Clock, epoch_now, use_clock
from src.core.exceptions import SafetyError
from src.core.models import JobListing
from src.core.settings import settings
from src.extraction.canonical_job_adapter import CanonicalJobAdapter
from src.extraction.field_normalizer import humanize_slug
from src.extraction.job_extraction_service import JobExtractionService, RawJobPosting
from src.providers.contract import (
    BoardCheckResult,
    FailureKind,
    classify_exception,
    classify_http_status,
    failure_result,
    get_reconciliation_policy,
)
from src.providers.fingerprint import canonical_content_hash, compute_board_fingerprint
from src.providers.http import (
    build_conditional_headers,
    fetch_provider_bytes,
    validate_board_token_safety,
)
from src.providers.pagination import HtmlPaginationTracker
from src.safety.url_safety import DnsResolver, UnsafeRedirectError
from src.storage.company_board_registry import CompanyBoard

_TEAMTAILOR_RSS_CAP = 100
_TEAMTAILOR_HTML_MAX_PAGES = 20
_TEAMTAILOR_HTML_MAX_ITEMS = 500
_TEAMTAILOR_LOC_NS = "{https://teamtailor.com/locations}"
_TEAMTAILOR_JOB_ID_PATH_RE = re.compile(r"^/(?:[a-z]{2}(?:-[a-z]{2,4})?/)?jobs/(\d+)(?:-[^/?#]+)?/?$", re.IGNORECASE)
_TEAMTAILOR_NEXT_PAGE_RE = re.compile(r"[?&]page=(\d+)", re.IGNORECASE)
_XML_UNSAFE_DECL_RE = re.compile(rb"<!(?:DOCTYPE|ENTITY)\b", re.IGNORECASE)


def _extract_tt_rss_location_list(item_el) -> list[str]:
    """Return all deduplicated formatted ``<tt:location>`` labels without length truncation."""
    locs_el = item_el.find(f"{_TEAMTAILOR_LOC_NS}locations")
    if locs_el is None:
        return []
    compact: list[str] = []
    for loc_el in locs_el.findall(f"{_TEAMTAILOR_LOC_NS}location"):
        name = (loc_el.findtext(f"{_TEAMTAILOR_LOC_NS}name") or "").strip()
        city = (loc_el.findtext(f"{_TEAMTAILOR_LOC_NS}city") or "").strip()
        country = (loc_el.findtext(f"{_TEAMTAILOR_LOC_NS}country") or "").strip()
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
    return compact


def _format_tt_rss_locations(item_el) -> tuple[str | None, str | None]:
    """Extract compact and preserved Teamtailor RSS <tt:locations> text."""
    locs_el = item_el.find(f"{_TEAMTAILOR_LOC_NS}locations")
    if locs_el is None:
        return None, None
    compact = _extract_tt_rss_location_list(item_el)
    raw_names: list[str] = [
        (loc_el.findtext(f"{_TEAMTAILOR_LOC_NS}name") or "").strip()
        for loc_el in locs_el.findall(f"{_TEAMTAILOR_LOC_NS}location")
        if (loc_el.findtext(f"{_TEAMTAILOR_LOC_NS}name") or "").strip()
    ]

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
    return canonical_content_hash(item)


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

    from src.safety.url_safety import is_safe_public_https_url

    if not xml_bytes or not xml_bytes.strip():
        return [], {}, "Empty Teamtailor RSS response"
    if _XML_UNSAFE_DECL_RE.search(xml_bytes):
        return [], {}, "Rejected unsafe DOCTYPE/ENTITY declaration in Teamtailor XML"

    try:
        text = xml_bytes.decode("utf-8")
        root = ET.fromstring(text)
    except (UnicodeDecodeError, ET.ParseError) as exc:
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
        all_locs = _extract_tt_rss_location_list(el)

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
                "all_locations": all_locs,
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
    from urllib.parse import urljoin, urlparse

    from bs4 import BeautifulSoup

    from src.safety.url_safety import is_safe_public_https_url

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
    resolver: DnsResolver | None = None,
) -> tuple[list[dict], bool, str | None, str | None]:
    """
    Bounded HTML pagination fallback for Teamtailor boards hitting the 100-item RSS cap.

    Returns ``(html_items, fallback_complete, page1_html, error)``.
    Any non-200 HTTP response, missing frame, empty first page, repeated page,
    pagination loop, or page/item cap sets ``fallback_complete=False`` so callers
    never trigger missing-job auto-closure from an incomplete snapshot.
    """
    clean_slug = board_token.strip().lower()
    encoded_slug = quote(clean_slug, safe="-_.~")
    host = f"{encoded_slug}.teamtailor.com"
    byte_cap = int(max_bytes or settings.max_response_bytes)

    tracker = HtmlPaginationTracker(
        max_pages=max_pages,
        max_items=max_items,
        provider_label="Teamtailor HTML",
    )
    page = 1
    page1_html: str | None = None

    while True:
        can_go, gate_err = tracker.can_visit(page)
        if not can_go:
            return tracker.collected, False, page1_html, gate_err

        url = f"https://{host}/jobs?page={page}"
        try:
            status, body_bytes, _ = await fetch_provider_bytes(
                client,
                url,
                headers=build_conditional_headers(
                    url, "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8"
                ),
                timeout=timeout,
                max_bytes=byte_cap,
                follow_redirects=False,
                resolver=resolver,
            )
        except asyncio.CancelledError:
            raise
        except UnsafeRedirectError as exc:
            return tracker.collected, False, page1_html, str(exc)
        except SafetyError:
            raise
        except Exception as exc:  # broad-except-ok: HTML fallback returns incomplete snapshot on unexpected transport error  # noqa: BLE001
            return tracker.collected, False, page1_html, str(exc)

        if status != 200:
            return tracker.collected, False, page1_html, f"Teamtailor HTML fallback HTTP {status} on page={page}"

        html_text = body_bytes.decode("utf-8", errors="replace")
        if page == 1:
            page1_html = html_text

        page_items, next_page, parse_err = _parse_teamtailor_html_jobs_page(
            html_text,
            expected_host=host,
            current_page=page,
        )
        if parse_err:
            return tracker.collected, False, page1_html, parse_err

        done, complete, rec_err = tracker.record_page(page, page_items, next_page, id_key="job_id")
        if done:
            return tracker.collected, complete, page1_html, rec_err

        assert next_page is not None
        page = next_page


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
    from src.core.models import ExtractionMethod
    from src.extraction.field_normalizer import to_markdown
    from src.extraction.work_model import resolve_work_model

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
    if item.get("all_locations"):
        raw_fields["all_locations"] = item["all_locations"]
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
    from src.core.models import ExtractionMethod
    from src.extraction.work_model import resolve_work_model

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
        clock: Clock | None = None,
        resolver: DnsResolver | None = None,
        max_response_bytes: int | None = None,
        **kwargs,
    ) -> BoardCheckResult:
        from src.storage.company_board_registry import is_valid_board_slug

        policy = get_reconciliation_policy("teamtailor")
        if not validate_board_token_safety(board.board_token) or not is_valid_board_slug(
            "teamtailor", board.board_token
        ):
            return failure_result(
                kind=FailureKind.UNSAFE_URL,
                error="Invalid Teamtailor board token",
                policy=policy,
            )

        clean_slug = board.board_token.strip().lower()
        encoded_slug = quote(clean_slug, safe="-_.~")
        rss_url = f"https://{encoded_slug}.teamtailor.com/jobs.rss"
        headers = build_conditional_headers(
            rss_url,
            "application/rss+xml, application/xml, text/xml;q=0.9, */*;q=0.8",
            etag=board.etag,
            last_modified=board.last_modified,
        )

        max_bytes = (
            int(max_response_bytes)
            if max_response_bytes is not None
            else int(kwargs.get("max_response_bytes") or settings.max_response_bytes)
        )
        with use_clock(clock):
            try:
                status, body_bytes, resp_headers = await fetch_provider_bytes(
                    client,
                    rss_url,
                    headers=headers,
                    timeout=timeout,
                    max_bytes=max_bytes,
                    follow_redirects=False,
                    resolver=resolver,
                )
                if status == 304:
                    return BoardCheckResult(
                        success=True,
                        not_modified=True,
                        etag=resp_headers.get("etag") or board.etag,
                        last_modified=resp_headers.get("last-modified") or board.last_modified,
                        content_fingerprint=board.content_fingerprint,
                        reconciliation_policy=policy,
                        snapshot_complete=True,
                    )
                if status == 404:
                    return failure_result(
                        kind=FailureKind.NOT_FOUND,
                        error="Board not found (HTTP 404)",
                        policy=policy,
                    )
                if status != 200:
                    return failure_result(
                        kind=classify_http_status(status),
                        error=f"HTTP {status}",
                        policy=policy,
                    )

                rss_items, channel_meta, parse_err = parse_teamtailor_rss_feed(body_bytes)
                if parse_err:
                    err_kind = (
                        FailureKind.INCOMPLETE_SNAPSHOT
                        if "duplicate" in parse_err.lower()
                        else FailureKind.PARSE_ERROR
                    )
                    return failure_result(kind=err_kind, error=parse_err, policy=policy)

                new_etag = resp_headers.get("etag")
                new_lm = resp_headers.get("last-modified")
                company_name = channel_meta.get("channel_title") or board.company_name

                fp_items: list[tuple[str, str | None, str | None]] = [
                    (it["job_id"], it.get("pub_date"), _teamtailor_rss_item_hash(it))
                    for it in rss_items
                ]

                snapshot_complete = True
                incomplete_reason: str | None = None
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
                        resolver=resolver,
                    )
                    rss_ids = {it["job_id"] for it in rss_items}
                    if html_complete:
                        html_only_cards = [c for c in html_cards if c["job_id"] not in rss_ids]
                        for card in html_only_cards:
                            fp_items.append((card["job_id"], None, _teamtailor_rss_item_hash(card)))
                    else:
                        snapshot_complete = False
                        incomplete_reason = fallback_err or "incomplete_html_fallback"
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
                        reconciliation_policy=policy,
                        snapshot_complete=True,
                    )

                logo_url = board.company_logo_url
                logo_source = board.company_logo_source
                logo_verified = bool(board.company_logo_verified)
                logo_checked_at = board.company_logo_checked_at
                if page1_html and (not logo_url or not logo_verified):
                    try:
                        from bs4 import BeautifulSoup

                        from src.extraction.logo_extractor import extract_company_logo_for_provider

                        logo_res = extract_company_logo_for_provider(
                            "teamtailor",
                            BeautifulSoup(page1_html, "html.parser"),
                            base_url=f"https://{encoded_slug}.teamtailor.com/jobs",
                        )
                        if logo_res.url and logo_res.verified:
                            logo_url = logo_res.url
                            logo_source = logo_res.source
                            logo_verified = True
                            logo_checked_at = epoch_now()
                    except (asyncio.CancelledError, SafetyError):
                        raise
                    except (ImportError, ValueError, TypeError, AttributeError, LookupError, KeyError, RuntimeError):
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
                    reconciliation_policy=policy,
                    snapshot_complete=snapshot_complete,
                    incomplete_reason=incomplete_reason,
                )
            except asyncio.CancelledError:
                raise
            except UnsafeRedirectError as exc:
                return failure_result(
                    kind=FailureKind.UNSAFE_URL,
                    error=str(exc),
                    policy=policy,
                )
            except SafetyError:
                raise
            except Exception as exc:  # broad-except-ok: adapter check_board classifies failures into BoardCheckResult  # noqa: BLE001
                return failure_result(
                    kind=classify_exception(exc),
                    error=str(exc),
                    policy=policy,
                )
