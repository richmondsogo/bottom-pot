"""
Personio bilingual XML company-board monitoring adapter.
"""

from __future__ import annotations

import asyncio
import json
import re
from urllib.parse import quote

import httpx

from src.core.clock import Clock, use_clock
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
from src.safety.url_safety import DnsResolver, UnsafeRedirectError
from src.storage.company_board_registry import CompanyBoard

_XML_UNSAFE_DECL_RE = re.compile(rb"<!(?:DOCTYPE|ENTITY)\b", re.IGNORECASE)


_PERSONIO_ACCEPT = "application/xml, text/xml;q=0.9, */*;q=0.8"
_PERSONIO_ID_RE = re.compile(r"^\d+$")


def _encode_personio_etag(
    en_etag: str | None,
    def_etag: str | None,
    needs_fallback: bool,
) -> str | None:
    """Encode Personio single- or dual-language conditional ETags compatibly into ``company_boards.etag``."""
    if not needs_fallback:
        if not en_etag:
            return None
        return "p1:" + json.dumps({"en": en_etag, "fb": 0}, separators=(",", ":"), sort_keys=True)
    if not en_etag and not def_etag:
        return None
    return "p1:" + json.dumps({"en": en_etag, "def": def_etag, "fb": 1}, separators=(",", ":"), sort_keys=True)


def _decode_personio_etag(raw_etag: str | None) -> tuple[str | None, str | None, bool]:
    """Decode stored Personio ETag state into ``(en_etag, def_etag, needs_fallback)``."""
    if not raw_etag or not isinstance(raw_etag, str):
        return None, None, False
    cleaned = raw_etag.strip()
    if not cleaned:
        return None, None, False
    if cleaned.startswith("p1:"):
        try:
            payload = json.loads(cleaned[3:])
            if not isinstance(payload, dict):
                return None, None, False
            en_val = payload.get("en")
            def_val = payload.get("def")
            fb_val = bool(payload.get("fb"))
            return (
                str(en_val) if isinstance(en_val, str) and en_val else None,
                str(def_val) if isinstance(def_val, str) and def_val else None,
                fb_val,
            )
        except (json.JSONDecodeError, TypeError, ValueError):
            return None, None, False
    return cleaned, None, False


def _extract_personio_location_list(pos_el) -> list[str]:
    """Return deduplicated Personio ``<office>`` + ``<additionalOffices>`` labels without truncation."""
    ordered: list[str] = []
    seen: set[str] = set()

    def _add(val: str | None) -> None:
        text = (val or "").strip()
        if not text:
            return
        key = text.lower()
        if key not in seen:
            seen.add(key)
            ordered.append(text)

    _add(pos_el.findtext("office"))
    extra_el = pos_el.find("additionalOffices")
    if extra_el is not None:
        child_offices = extra_el.findall("office")
        if child_offices:
            for ch in child_offices:
                _add(ch.text)
        elif (extra_el.text or "").strip():
            _add(extra_el.text)
    return ordered


def _extract_personio_locations(pos_el) -> tuple[str | None, str | None]:
    """Extract compact and preserved Personio ``<office>`` + ``<additionalOffices>`` strings."""
    ordered = _extract_personio_location_list(pos_el)
    if not ordered:
        return None, None

    raw_loc = ", ".join(ordered)
    joined = "; ".join(ordered)
    if len(joined) > 80:
        fitted: list[str] = []
        for entry in ordered:
            cand = "; ".join([*fitted, entry])
            if len(cand) <= 68:
                fitted.append(entry)
            else:
                break
        rem = len(ordered) - len(fitted)
        joined = f"{'; '.join(fitted)} (+{rem} more)" if fitted and rem > 0 else (ordered[0][:77] + "...")
    return joined, raw_loc


def _normalize_personio_employment_type(
    employment_type: str | None,
    schedule: str | None,
) -> str | None:
    """Resolve Personio ``<employmentType>`` and ``<schedule>`` deterministically per ADR 0001.

    Personio separates contract duration (``employmentType="permanent"``) from working
    hours (``schedule="full-time"`` / ``"part-time"``). Permanent employment never
    implies ``full_time`` when schedule is absent, ambiguous, or unrecognized.
    """
    emp = (employment_type or "").strip().lower().replace("-", " ").replace("_", " ")
    sched = (schedule or "").strip().lower().replace("-", " ").replace("_", " ")

    if emp in {"intern", "internship", "trainee", "traineeship"}:
        return "internship"
    if emp in {"freelance", "freelancer", "fixed term", "contractor", "temp", "temporary"}:
        return "contract"
    if sched in {"part time", "teilzeit"}:
        return "part_time"
    if sched in {"full or part time", "part or full time"}:
        return None
    if sched in {"full time", "vollzeit"}:
        return "full_time"
    return None


def _extract_personio_salary(pos_el) -> dict[str, str] | None:
    """Extract non-empty ``<salaryInformation>`` child tags from a Personio ``<position>``."""
    sal_el = pos_el.find("salaryInformation")
    if sal_el is None:
        return None
    out: dict[str, str] = {}
    for key in ("min", "max", "currencySymbol", "currencyCode", "type"):
        val = (sal_el.findtext(key) or "").strip()
        if val:
            out[key] = val
    return out or None


def _attach_personio_salary_fields(sal_info: dict[str, str] | None, raw_fields: dict) -> None:
    """Preserve raw salary metadata and expose ``baseSalary`` only when positive bounds exist."""
    if not sal_info:
        return
    raw_fields["salaryInformation"] = sal_info

    def _positive_num(raw_val: str | None) -> float | None:
        if not raw_val:
            return None
        try:
            num = float(raw_val.replace(",", "").strip())
            return num if num > 0 else None
        except (ValueError, TypeError):
            return None

    min_num = _positive_num(sal_info.get("min"))
    max_num = _positive_num(sal_info.get("max"))
    if min_num is None and max_num is None:
        return

    curr = sal_info.get("currencyCode") or sal_info.get("currencySymbol")
    val_block: dict[str, str] = {}
    if min_num is not None:
        val_block["minValue"] = sal_info["min"]
    if max_num is not None:
        val_block["maxValue"] = sal_info["max"]
    if sal_info.get("type"):
        val_block["unitText"] = sal_info["type"]
    raw_fields["baseSalary"] = {"currency": curr, "value": val_block}


def parse_personio_xml_feed(xml_bytes: bytes) -> tuple[list[dict], str | None]:
    """
    Strictly parse and validate a Personio public ``/xml`` recruiting feed.

    Returns ``(items, error)``. Rejects empty payloads, full-payload ``<!DOCTYPE``
    or ``<!ENTITY`` declarations, invalid UTF-8 / malformed XML, non-``<workzag-jobs>``
    root elements, non-numeric or empty ``<id>``, missing ``<name>``, and duplicate IDs.
    An empty valid ``<workzag-jobs></workzag-jobs>`` returns ``([], None)``.
    """
    import html as html_lib
    import xml.etree.ElementTree as ET

    if not xml_bytes or not xml_bytes.strip():
        return [], "Empty Personio XML response"
    if _XML_UNSAFE_DECL_RE.search(xml_bytes):
        return [], "Rejected unsafe DOCTYPE/ENTITY declaration in Personio XML"

    try:
        text = xml_bytes.decode("utf-8")
        root = ET.fromstring(text)
    except (UnicodeDecodeError, ET.ParseError) as exc:
        return [], f"Malformed Personio XML: {exc}"

    if root.tag != "workzag-jobs":
        return [], f"Unexpected Personio XML root tag: {root.tag!r}"

    items: list[dict] = []
    seen_ids: set[str] = set()
    for pos in root.findall("position"):
        job_id = (pos.findtext("id") or "").strip()
        if not job_id or not _PERSONIO_ID_RE.match(job_id):
            return [], f"Personio XML position has invalid/missing numeric <id>: {job_id!r}"
        if job_id in seen_ids:
            return [], f"Duplicate Personio job ID in XML snapshot: {job_id}"
        seen_ids.add(job_id)

        name = (pos.findtext("name") or "").strip()
        if not name:
            return [], f"Personio XML position {job_id} missing required <name>"

        location, raw_loc = _extract_personio_locations(pos)
        all_locs = _extract_personio_location_list(pos)

        desc_blocks: list[str] = []
        jd_parent = pos.find("jobDescriptions")
        if jd_parent is not None:
            for block in jd_parent.findall("jobDescription"):
                heading = (block.findtext("name") or "").strip()
                val_html = (block.findtext("value") or "").strip()
                if not val_html:
                    continue
                if heading:
                    desc_blocks.append(f"<h4>{html_lib.escape(heading)}</h4>\n{val_html}")
                else:
                    desc_blocks.append(val_html)
        description_html = "\n".join(desc_blocks) if desc_blocks else None

        items.append(
            {
                "id": job_id,
                "name": name,
                "subcompany": (pos.findtext("subcompany") or "").strip() or None,
                "location": location,
                "raw_location": raw_loc,
                "all_locations": all_locs,
                "department": (pos.findtext("department") or "").strip() or None,
                "recruiting_category": (pos.findtext("recruitingCategory") or "").strip() or None,
                "employment_type": (pos.findtext("employmentType") or "").strip() or None,
                "seniority": (pos.findtext("seniority") or "").strip() or None,
                "schedule": (pos.findtext("schedule") or "").strip() or None,
                "years_of_experience": (pos.findtext("yearsOfExperience") or "").strip() or None,
                "keywords": (pos.findtext("keywords") or "").strip() or None,
                "occupation": (pos.findtext("occupation") or "").strip() or None,
                "occupation_category": (pos.findtext("occupationCategory") or "").strip() or None,
                "created_at": (pos.findtext("createdAt") or "").strip() or None,
                "salary_info": _extract_personio_salary(pos),
                "description_html": description_html,
            }
        )

    return items, None


def _merge_personio_feeds(en_items: list[dict], def_items: list[dict]) -> tuple[list[dict], str | None]:
    """
    Merge ``?language=en`` items with default ``/xml`` fallback descriptions.

    Preserves English metadata and non-empty English descriptions, fills empty
    descriptions from the default feed only, and fails closed if position ID sets differ.
    """
    en_ids = {it["id"] for it in en_items}
    def_ids = {it["id"] for it in def_items}
    if en_ids != def_ids:
        return [], "Inconsistent position ID sets between Personio EN and default XML feeds"

    def_by_id = {it["id"]: it for it in def_items}
    merged: list[dict] = []
    for it in en_items:
        copy_item = dict(it)
        if not copy_item.get("description_html"):
            copy_item["description_html"] = def_by_id[it["id"]].get("description_html")
        merged.append(copy_item)
    return merged, None


def _personio_position_to_listing(
    item: dict,
    *,
    board_token: str,
    board_company_name: str | None = None,
    is_board_monitor: bool = True,
) -> JobListing:
    """Convert a validated Personio position dictionary into a canonical ``JobListing``."""
    from src.core.models import ExtractionMethod

    clean_slug = board_token.strip().lower()
    job_url = f"https://{clean_slug}.jobs.personio.com/job/{item['id']}"
    comp_name = (
        (item.get("subcompany") or "").strip()
        or (board_company_name or "").strip()
        or humanize_slug(clean_slug)
        or clean_slug
    )
    resolved_emp = _normalize_personio_employment_type(
        item.get("employment_type"),
        item.get("schedule"),
    )

    raw_fields: dict = {"date_field_name": "createdAt"}
    if resolved_emp is None and (item.get("employment_type") or item.get("schedule")):
        # Prevent free-text fallback (e.g. matching "permanent") when Personio XML
        # already supplied structured employment fields whose hours are unspecified.
        raw_fields["skip_employment_text_fallback"] = True
    if item.get("raw_location"):
        raw_fields["raw_location_preserved"] = item["raw_location"]
    if item.get("all_locations"):
        raw_fields["all_locations"] = item["all_locations"]
    for key, src_key in (
        ("recruitingCategory", "recruiting_category"),
        ("seniority", "seniority"),
        ("yearsOfExperience", "years_of_experience"),
        ("keywords", "keywords"),
        ("occupation", "occupation"),
        ("occupationCategory", "occupation_category"),
        ("personio_employment_type", "employment_type"),
        ("personio_schedule", "schedule"),
    ):
        if item.get(src_key):
            raw_fields[key] = item[src_key]
    _attach_personio_salary_fields(item.get("salary_info"), raw_fields)

    desc_html = item.get("description_html")
    raw = RawJobPosting(
        provider="personio",
        source_url=job_url,
        provider_job_id=item["id"],
        company_slug=clean_slug,
        apply_url=job_url,
        extraction_method=ExtractionMethod.ATS_API,
        raw_title=item["name"],
        raw_company=comp_name,
        raw_location=item.get("location"),
        raw_employment_type=resolved_emp,
        raw_department=item.get("department"),
        raw_date=item.get("created_at"),
        raw_fields=raw_fields,
        raw_description=desc_html,
        description_is_authentic=bool(desc_html),
        query_used="board_monitor" if is_board_monitor else clean_slug,
    )
    canonical = JobExtractionService.extract(raw)
    listing = CanonicalJobAdapter.to_listing(canonical)
    listing.provider = "personio"
    listing.id = f"personio:{clean_slug}:{item['id']}"
    listing.company_slug = clean_slug
    return listing


async def _get_personio_xml_with_kind(
    client: httpx.AsyncClient,
    url: str,
    *,
    timeout: float,
    max_bytes: int,
    if_none_match: str | None = None,
    resolver: DnsResolver | None = None,
) -> tuple[int, list[dict] | None, str | None, str | None, FailureKind | None]:
    headers = build_conditional_headers(url, _PERSONIO_ACCEPT, etag=if_none_match)
    status, body_bytes, resp_headers = await fetch_provider_bytes(
        client,
        url,
        headers=headers,
        timeout=timeout,
        max_bytes=max_bytes,
        follow_redirects=False,
        resolver=resolver,
    )
    if status == 304 and if_none_match:
        return 304, None, resp_headers.get("etag") or if_none_match, None, None
    if status == 404:
        return 404, None, None, "Board not found (HTTP 404)", FailureKind.NOT_FOUND
    if status != 200:
        return status, None, None, f"HTTP {status}", classify_http_status(status)

    items, parse_err = parse_personio_xml_feed(body_bytes)
    if parse_err:
        err_kind = (
            FailureKind.INCOMPLETE_SNAPSHOT
            if "duplicate" in parse_err.lower()
            else FailureKind.PARSE_ERROR
        )
        return 200, None, resp_headers.get("etag"), parse_err, err_kind
    return 200, items, resp_headers.get("etag"), None, None


async def _get_personio_xml(
    client: httpx.AsyncClient,
    url: str,
    *,
    timeout: float,
    max_bytes: int,
    if_none_match: str | None = None,
    resolver: DnsResolver | None = None,
) -> tuple[int, list[dict] | None, str | None, str | None]:
    """
    Execute one bounded Personio XML GET (optionally conditional).

    Returns ``(status_code, parsed_items_or_none, response_etag, error_or_none)``.
    """
    status, items, etag, err, _ = await _get_personio_xml_with_kind(
        client,
        url,
        timeout=timeout,
        max_bytes=max_bytes,
        if_none_match=if_none_match,
        resolver=resolver,
    )
    return status, items, etag, err


class PersonioBoardAdapter:
    """
    Personio company-board adapter.

    Primary endpoint: ``GET https://{slug}.jobs.personio.com/xml?language=en``.
    When the English feed is empty or any position has empty ``<jobDescriptions>``,
    performs a bounded check/fallback to default ``GET https://{slug}.jobs.personio.com/xml``
    and tracks both ETags inside ``company_boards.etag`` so a ``304`` on one language
    never masks updates or non-empty jobs on the other. Always fails closed with
    ``snapshot_complete=False`` on errors, unsafe/malformed XML, or ID mismatches across
    bilingual feeds.
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

        policy = get_reconciliation_policy("personio")
        if not validate_board_token_safety(board.board_token) or not is_valid_board_slug(
            "personio", board.board_token
        ):
            return failure_result(
                kind=FailureKind.UNSAFE_URL,
                error="Invalid Personio board token",
                policy=policy,
            )

        clean_slug = board.board_token.strip().lower()
        encoded_slug = quote(clean_slug, safe="-_.~")
        en_url = f"https://{encoded_slug}.jobs.personio.com/xml?language=en"
        def_url = f"https://{encoded_slug}.jobs.personio.com/xml"
        max_bytes = (
            int(max_response_bytes)
            if max_response_bytes is not None
            else int(kwargs.get("max_response_bytes") or settings.max_response_bytes)
        )

        prev_en_etag, prev_def_etag, prev_fb = _decode_personio_etag(board.etag)

        with use_clock(clock):
            try:
                en_status, en_items, cur_en_etag, en_err, en_kind = await _get_personio_xml_with_kind(
                    client,
                    en_url,
                    timeout=timeout,
                    max_bytes=max_bytes,
                    if_none_match=prev_en_etag,
                    resolver=resolver,
                )
                if en_err:
                    return failure_result(
                        kind=en_kind or FailureKind.UNEXPECTED_ERROR,
                        error=en_err,
                        policy=policy,
                    )

                if en_status == 304:
                    if not prev_fb:
                        return BoardCheckResult(
                            success=True,
                            not_modified=True,
                            etag=board.etag,
                            last_modified=board.last_modified,
                            content_fingerprint=board.content_fingerprint,
                            reconciliation_policy=policy,
                            snapshot_complete=True,
                        )

                    # Bilingual fallback was required: must also validate default /xml before 304 short-circuit
                    def_status, def_items, cur_def_etag, def_err, def_kind = await _get_personio_xml_with_kind(
                        client,
                        def_url,
                        timeout=timeout,
                        max_bytes=max_bytes,
                        if_none_match=prev_def_etag,
                        resolver=resolver,
                    )
                    if def_err:
                        return failure_result(
                            kind=def_kind or FailureKind.UNEXPECTED_ERROR,
                            error=def_err,
                            policy=policy,
                        )
                    if def_status == 304:
                        return BoardCheckResult(
                            success=True,
                            not_modified=True,
                            etag=board.etag,
                            last_modified=board.last_modified,
                            content_fingerprint=board.content_fingerprint,
                            reconciliation_policy=policy,
                            snapshot_complete=True,
                        )

                    assert def_items is not None
                    _, en_items_fresh, fresh_en_etag, refetch_err, refetch_kind = await _get_personio_xml_with_kind(
                        client,
                        en_url,
                        timeout=timeout,
                        max_bytes=max_bytes,
                        if_none_match=None,
                        resolver=resolver,
                    )
                    if refetch_err or en_items_fresh is None:
                        return failure_result(
                            kind=refetch_kind or FailureKind.INCOMPLETE_SNAPSHOT,
                            error=refetch_err or "Failed to refresh EN Personio XML feed",
                            policy=policy,
                        )
                    merged_items, merge_err = _merge_personio_feeds(en_items_fresh, def_items)
                    if merge_err:
                        return failure_result(
                            kind=FailureKind.INCOMPLETE_SNAPSHOT,
                            error=merge_err,
                            policy=policy,
                        )
                    new_etag = _encode_personio_etag(fresh_en_etag or prev_en_etag, cur_def_etag, True)
                else:
                    assert en_items is not None
                    needs_fallback = (len(en_items) == 0) or any(not it.get("description_html") for it in en_items)
                    if not needs_fallback:
                        merged_items = en_items
                        new_etag = _encode_personio_etag(cur_en_etag, None, False)
                    else:
                        def_inm = prev_def_etag if (prev_fb and prev_def_etag) else None
                        def_status, def_items, cur_def_etag, def_err, def_kind = await _get_personio_xml_with_kind(
                            client,
                            def_url,
                            timeout=timeout,
                            max_bytes=max_bytes,
                            if_none_match=def_inm,
                            resolver=resolver,
                        )
                        if def_err:
                            return failure_result(
                                kind=def_kind or FailureKind.UNEXPECTED_ERROR,
                                error=def_err,
                                policy=policy,
                            )
                        if def_status == 304:
                            _, def_items, uncond_def_etag, uncond_err, uncond_kind = await _get_personio_xml_with_kind(
                                client,
                                def_url,
                                timeout=timeout,
                                max_bytes=max_bytes,
                                if_none_match=None,
                                resolver=resolver,
                            )
                            if uncond_err or def_items is None:
                                return failure_result(
                                    kind=uncond_kind or FailureKind.INCOMPLETE_SNAPSHOT,
                                    error=uncond_err or "Failed to hydrate unchanged default Personio XML feed",
                                    policy=policy,
                                )
                            cur_def_etag = uncond_def_etag or cur_def_etag
                        assert def_items is not None
                        merged_items, merge_err = _merge_personio_feeds(en_items, def_items)
                        if merge_err:
                            return failure_result(
                                kind=FailureKind.INCOMPLETE_SNAPSHOT,
                                error=merge_err,
                                policy=policy,
                            )
                        new_etag = _encode_personio_etag(cur_en_etag, cur_def_etag, True)

                fingerprint = compute_board_fingerprint(
                    [(it["id"], it.get("created_at"), canonical_content_hash(it)) for it in merged_items]
                )
                if board.content_fingerprint and fingerprint == board.content_fingerprint:
                    return BoardCheckResult(
                        success=True,
                        not_modified=True,
                        etag=new_etag or board.etag,
                        last_modified=board.last_modified,
                        content_fingerprint=fingerprint,
                        reconciliation_policy=policy,
                        snapshot_complete=True,
                    )

                listings = [
                    _personio_position_to_listing(
                        it,
                        board_token=clean_slug,
                        board_company_name=board.company_name,
                        is_board_monitor=True,
                    )
                    for it in merged_items
                ]
                return BoardCheckResult(
                    success=True,
                    not_modified=False,
                    listings=listings,
                    etag=new_etag,
                    content_fingerprint=fingerprint,
                    reconciliation_policy=policy,
                    snapshot_complete=True,
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
            except Exception as exc:
                return failure_result(
                    kind=classify_exception(exc),
                    error=str(exc),
                    policy=policy,
                )
