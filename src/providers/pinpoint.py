"""
Pinpoint company-board monitoring adapter.
"""

from __future__ import annotations

import asyncio
import json
import re
from urllib.parse import quote

import httpx

from src.core.clock import Clock, use_clock
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
from src.safety.url_safety import DnsResolver
from src.storage.company_board_registry import CompanyBoard

_PINPOINT_ACCEPT = "application/json"
_PINPOINT_UUID_IN_PATH_RE = re.compile(
    r"/postings/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})(?:/applications/new|/apply)?/?$",
    re.IGNORECASE,
)

_PINPOINT_WORKPLACE_MAP: dict[str, str] = {
    "remote": "remote",
    "fully_remote": "remote",
    "fully remote": "remote",
    "hybrid": "hybrid",
    "onsite": "in_person",
    "on_site": "in_person",
    "on-site": "in_person",
    "on site": "in_person",
    "in_person": "in_person",
    "in person": "in_person",
    "office": "in_person",
}

_PINPOINT_EMPLOYMENT_MAP: dict[str, str] = {
    "full_time": "full_time",
    "fulltime": "full_time",
    "full time": "full_time",
    "full_time_permanent": "full_time",
    "permanent_full_time": "full_time",
    "part_time": "part_time",
    "parttime": "part_time",
    "part time": "part_time",
    "part_time_permanent": "part_time",
    "permanent_part_time": "part_time",
    "contract": "contract",
    "contractor": "contract",
    "temporary": "contract",
    "temp": "contract",
    "fixed_term": "contract",
    "fixed term": "contract",
    "full_time_fixed_term": "contract",
    "part_time_fixed_term": "contract",
    "fixed_term_full_time": "contract",
    "fixed_term_part_time": "contract",
    "freelance": "contract",
    "internship": "internship",
    "intern": "internship",
    "placement": "internship",
    "apprenticeship": "internship",
}


def _normalize_pinpoint_workplace_type(
    workplace_type: str | None,
    workplace_type_text: str | None,
) -> str | None:
    for candidate in (workplace_type, workplace_type_text):
        if isinstance(candidate, str):
            norm_key = candidate.strip().lower().replace("-", "_").replace(" ", "_")
            mapped = _PINPOINT_WORKPLACE_MAP.get(norm_key) or _PINPOINT_WORKPLACE_MAP.get(candidate.strip().lower())
            if mapped:
                return mapped
    return None


def _normalize_pinpoint_employment_type(
    employment_type: str | None,
    employment_type_text: str | None,
) -> tuple[str | None, bool]:
    """
    Map Pinpoint employment_type enums conservatively per ADR 0001.

    Returns ``(normalized_type, saw_explicit_unrecognized)``.
    """
    saw_value = False
    for candidate in (employment_type, employment_type_text):
        if isinstance(candidate, str) and candidate.strip():
            saw_value = True
            norm_key = candidate.strip().lower().replace("-", "_").replace(" ", "_")
            mapped = _PINPOINT_EMPLOYMENT_MAP.get(norm_key) or _PINPOINT_EMPLOYMENT_MAP.get(candidate.strip().lower())
            if mapped:
                return mapped, False
    return None, saw_value


def _extract_pinpoint_location(loc_obj: object) -> tuple[str | None, dict[str, str] | None]:
    """
    Extract display location and non-empty structured Pinpoint location metadata.

    Prefers ``location.name`` (e.g. ``"Nigeria"``, ``"Australia (Remote)"``, ``"Remote"``)
    when present so tenant-level city defaults (e.g. Lagos HQ on regional postings) never
    overwrite an explicit country/region name, falling back to deduplicated ``city, province``.
    """
    if not isinstance(loc_obj, dict):
        return None, None

    meta: dict[str, str] = {}
    for k in ("name", "city", "province", "postal_code", "street_address"):
        v = loc_obj.get(k)
        if isinstance(v, str) and v.strip():
            meta[k] = v.strip()

    name = meta.get("name")
    city = meta.get("city")
    province = meta.get("province")

    if name:
        return name, meta

    parts: list[str] = []
    for part in (city, province):
        if part and part.lower() not in {p.lower() for p in parts}:
            parts.append(part)
    if parts:
        return ", ".join(parts), meta
    return None, meta or None


def _build_pinpoint_description_html(entry: dict) -> tuple[str | None, str | None]:
    """
    Combine Pinpoint's four structured HTML sections into canonical HTML description
    and isolate ``skills_knowledge_expertise`` for ``raw_requirements``.
    """
    import html as html_lib

    blocks: list[str] = []
    desc = entry.get("description")
    if isinstance(desc, str) and desc.strip():
        blocks.append(desc.strip())

    for body_key, header_key, default_header in (
        ("key_responsibilities", "key_responsibilities_header", "Key Responsibilities"),
        ("skills_knowledge_expertise", "skills_knowledge_expertise_header", "Skills, Knowledge & Expertise"),
        ("benefits", "benefits_header", "Benefits"),
    ):
        body = entry.get(body_key)
        if isinstance(body, str) and body.strip():
            hdr_raw = entry.get(header_key)
            hdr = hdr_raw.strip() if isinstance(hdr_raw, str) and hdr_raw.strip() else default_header
            blocks.append(f"<h4>{html_lib.escape(hdr)}</h4>\n{body.strip()}")

    combined_html = "\n".join(blocks) if blocks else None
    skills_raw = entry.get("skills_knowledge_expertise")
    requirements_html = skills_raw.strip() if isinstance(skills_raw, str) and skills_raw.strip() else None
    return combined_html, requirements_html


def parse_pinpoint_postings_json(
    payload_bytes: bytes,
    expected_slug: str | None = None,
) -> tuple[list[dict], str | None]:
    """
    Strictly parse and validate a Pinpoint public ``/postings.json`` snapshot.

    Returns ``(items, error)``. Fails closed on empty/non-UTF-8/invalid JSON, non-dict
    root, missing ``data`` list, cross-tenant URLs, missing required ``id``/``title``/``url``,
    or duplicate posting IDs. An empty ``{"data": []}`` returns ``([], None)``.
    """
    from urllib.parse import urlparse

    if not payload_bytes or not payload_bytes.strip():
        return [], "Empty Pinpoint JSON response"

    try:
        data = json.loads(payload_bytes.decode("utf-8"))
    except Exception:
        return [], "Invalid Pinpoint JSON payload"

    if not isinstance(data, dict) or not isinstance(data.get("data"), list):
        return [], "Invalid Pinpoint postings payload shape"

    clean_expected = expected_slug.strip().lower() if expected_slug else None
    items: list[dict] = []
    seen_job_ids: set[str] = set()
    seen_numeric_ids: set[str] = set()

    for entry in data["data"]:
        if not isinstance(entry, dict):
            return [], "Malformed Pinpoint posting entry (expected object)"

        raw_id = entry.get("id")
        if raw_id is None or isinstance(raw_id, (bool, list, dict)) or not str(raw_id).strip():
            return [], "Malformed Pinpoint posting missing required id"
        numeric_id = str(raw_id).strip()
        if numeric_id in seen_numeric_ids:
            return [], f"Duplicate Pinpoint numeric posting id in snapshot: {numeric_id}"
        seen_numeric_ids.add(numeric_id)

        raw_title = entry.get("title")
        if not isinstance(raw_title, str) or not raw_title.strip():
            return [], f"Malformed Pinpoint posting {numeric_id} missing required title"
        title = raw_title.strip()

        raw_url = entry.get("url")
        raw_path = entry.get("path")
        resolved_url: str | None = None
        if raw_url is not None:
            if not isinstance(raw_url, str) or not raw_url.strip():
                return [], f"Malformed Pinpoint posting {numeric_id} has invalid empty url"
            cand = raw_url.strip()
            if cand.lower().startswith("http://"):
                cand = "https://" + cand[7:]
            try:
                parsed_u = urlparse(cand)
            except Exception:
                return [], f"Invalid URL in Pinpoint posting {numeric_id}"
            host_low = (parsed_u.hostname or "").lower()
            if parsed_u.scheme.lower() != "https" or not host_low.endswith(".pinpointhq.com"):
                return [], f"Unexpected Pinpoint posting host for {numeric_id}: {host_low!r}"
            if clean_expected and host_low != f"{clean_expected}.pinpointhq.com":
                return [], (
                    f"Pinpoint tenant mismatch on posting {numeric_id}: "
                    f"expected {clean_expected!r}, got {host_low!r}"
                )
            resolved_url = cand
        elif isinstance(raw_path, str) and raw_path.strip().startswith("/") and clean_expected:
            resolved_url = f"https://{clean_expected}.pinpointhq.com{raw_path.strip()}"
        else:
            return [], f"Malformed Pinpoint posting {numeric_id} missing valid url/path"

        uuid_m = _PINPOINT_UUID_IN_PATH_RE.search(urlparse(resolved_url).path or "")
        if not uuid_m and isinstance(raw_path, str):
            uuid_m = _PINPOINT_UUID_IN_PATH_RE.search(raw_path.strip())
        job_id = uuid_m.group(1).lower() if uuid_m else numeric_id
        if job_id in seen_job_ids:
            return [], f"Duplicate Pinpoint posting id in snapshot: {job_id}"
        seen_job_ids.add(job_id)

        job_obj = entry.get("job") if isinstance(entry.get("job"), dict) else {}
        department: str | None = None
        for grp_key in ("department", "division", "structure_custom_group_one"):
            grp = job_obj.get(grp_key)
            if isinstance(grp, dict) and isinstance(grp.get("name"), str) and grp["name"].strip():
                department = grp["name"].strip()
                break

        location_display, location_meta = _extract_pinpoint_location(entry.get("location"))
        description_html, requirements_html = _build_pinpoint_description_html(entry)

        comp_visible = entry.get("compensation_visible") is True
        comp_min = entry.get("compensation_minimum")
        comp_max = entry.get("compensation_maximum")
        comp_curr = entry.get("compensation_currency")
        comp_freq = entry.get("compensation_frequency")
        comp_text = entry.get("compensation") if isinstance(entry.get("compensation"), str) else None

        items.append(
            {
                "job_id": job_id,
                "numeric_id": numeric_id,
                "title": title,
                "url": resolved_url,
                "path": raw_path.strip() if isinstance(raw_path, str) and raw_path.strip() else None,
                "location": location_display,
                "location_meta": location_meta,
                "workplace_type": entry.get("workplace_type") if isinstance(entry.get("workplace_type"), str) else None,
                "workplace_type_text": entry.get("workplace_type_text") if isinstance(entry.get("workplace_type_text"), str) else None,
                "employment_type": entry.get("employment_type") if isinstance(entry.get("employment_type"), str) else None,
                "employment_type_text": entry.get("employment_type_text") if isinstance(entry.get("employment_type_text"), str) else None,
                "department": department,
                "pinpoint_job_id": str(job_obj["id"]).strip() if job_obj.get("id") is not None else None,
                "requisition_id": job_obj.get("requisition_id").strip() if isinstance(job_obj.get("requisition_id"), str) and job_obj.get("requisition_id").strip() else None,
                "reporting_to": entry.get("reporting_to").strip() if isinstance(entry.get("reporting_to"), str) and entry.get("reporting_to").strip() else None,
                "deadline_at": entry.get("deadline_at") if isinstance(entry.get("deadline_at"), str) and entry.get("deadline_at").strip() else None,
                "compensation_visible": comp_visible,
                "compensation": comp_text.strip() if (comp_visible and comp_text and comp_text.strip()) else None,
                "compensation_minimum": comp_min if (comp_visible and isinstance(comp_min, (int, float)) and not isinstance(comp_min, bool) and comp_min > 0) else None,
                "compensation_maximum": comp_max if (comp_visible and isinstance(comp_max, (int, float)) and not isinstance(comp_max, bool) and comp_max > 0) else None,
                "compensation_currency": comp_curr.strip() if (comp_visible and isinstance(comp_curr, str) and comp_curr.strip()) else None,
                "compensation_frequency": comp_freq.strip() if (comp_visible and isinstance(comp_freq, str) and comp_freq.strip()) else None,
                "description_html": description_html,
                "requirements_html": requirements_html,
            }
        )

    return items, None


def _attach_pinpoint_compensation_fields(item: dict, raw_fields: dict) -> None:
    """Attach structured Pinpoint compensation fields only when ``compensation_visible`` is True."""
    if not item.get("compensation_visible"):
        return

    min_num = item.get("compensation_minimum")
    max_num = item.get("compensation_maximum")
    curr = item.get("compensation_currency")
    freq = item.get("compensation_frequency")

    if item.get("compensation"):
        raw_fields["compensation"] = item["compensation"]

    if min_num is None and max_num is None:
        return

    val_block: dict[str, object] = {}
    if min_num is not None:
        val_block["minValue"] = min_num
    if max_num is not None:
        val_block["maxValue"] = max_num
    if freq:
        val_block["unitText"] = freq

    raw_fields["baseSalary"] = {"currency": curr, "value": val_block}


def _pinpoint_item_to_listing(
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
    """Convert a validated Pinpoint posting dictionary into a canonical ``JobListing``."""
    from src.core.models import ExtractionMethod

    clean_slug = board_token.strip().lower()
    source_url = item["url"]
    if _PINPOINT_UUID_IN_PATH_RE.search(source_url) and not source_url.rstrip("/").lower().endswith("/applications/new"):
        apply_url = f"{source_url.rstrip('/')}/applications/new"
    else:
        apply_url = source_url

    comp_name = (board_company_name or "").strip() or humanize_slug(clean_slug) or clean_slug
    norm_workplace = _normalize_pinpoint_workplace_type(
        item.get("workplace_type"),
        item.get("workplace_type_text"),
    )
    norm_emp, saw_unrecognized_emp = _normalize_pinpoint_employment_type(
        item.get("employment_type"),
        item.get("employment_type_text"),
    )

    raw_fields: dict = {
        "pinpoint_posting_id": item["numeric_id"],
    }
    if norm_emp is None and saw_unrecognized_emp:
        raw_fields["skip_employment_text_fallback"] = True
    for k in (
        "workplace_type",
        "workplace_type_text",
        "employment_type",
        "employment_type_text",
        "pinpoint_job_id",
        "requisition_id",
        "reporting_to",
        "deadline_at",
    ):
        if item.get(k):
            raw_fields[k] = item[k]
    if item.get("location_meta"):
        raw_fields["location_meta"] = item["location_meta"]
    if board_logo_url and board_logo_verified:
        raw_fields["company_logo_url"] = board_logo_url
        raw_fields["company_logo_source"] = board_logo_source
        raw_fields["company_logo_verified"] = True
        if board_logo_checked_at is not None:
            raw_fields["company_logo_checked_at"] = board_logo_checked_at
    _attach_pinpoint_compensation_fields(item, raw_fields)

    desc_html = item.get("description_html")
    raw = RawJobPosting(
        provider="pinpointhq",
        source_url=source_url,
        apply_url=apply_url,
        provider_job_id=item["job_id"],
        company_slug=clean_slug,
        extraction_method=ExtractionMethod.ATS_API,
        raw_title=item["title"],
        raw_company=comp_name,
        raw_location=item.get("location"),
        raw_workplace_type=norm_workplace,
        raw_employment_type=norm_emp,
        raw_department=item.get("department"),
        # Pinpoint /postings.json omits publication timestamps (deadline_at is closing deadline, never posted_at).
        raw_date=None,
        raw_fields=raw_fields,
        raw_description=desc_html,
        raw_requirements=item.get("requirements_html"),
        description_is_authentic=bool(desc_html),
        query_used="board_monitor" if is_board_monitor else clean_slug,
    )
    canonical = JobExtractionService.extract(raw)
    listing = CanonicalJobAdapter.to_listing(canonical)
    listing.provider = "pinpointhq"
    listing.ats_source = "pinpointhq"
    listing.data_source = "api"
    listing.id = f"pinpointhq:{clean_slug}:{item['job_id']}"
    listing.company_slug = clean_slug
    listing.source_record_id = item["numeric_id"]

    aliases: list[str] = []
    for candidate_alias in (
        f"pinpointhq:{clean_slug}:{item['job_id']}",
        f"pinpointhq:{clean_slug}:{item['numeric_id']}",
    ):
        if candidate_alias not in aliases:
            aliases.append(candidate_alias)
    listing.aliases = aliases
    return listing


def resolve_pinpoint_board_timeout(
    override: float | None = None,
    *,
    bound_to_search_timeout: bool = False,
) -> float:
    """
    Resolve the effective HTTP streaming timeout for Pinpoint ``/postings.json`` fetches.

    Uses ``settings.pinpoint_board_request_timeout_seconds`` (default 25.0s, safely above
    Step 51's observed ~16-20.2s streaming times for large boards) floored by
    ``settings.ats_request_timeout_seconds`` and ``1.0s``. When used in interactive search
    direct routing (``bound_to_search_timeout=True``), caps the per-request timeout at
    ``settings.search_hard_timeout_seconds`` so routing remains bounded by search controls.
    """
    if override is not None:
        eff = max(float(override), 1.0)
    else:
        eff = max(
            float(settings.pinpoint_board_request_timeout_seconds),
            float(settings.ats_request_timeout_seconds),
            1.0,
        )
    if bound_to_search_timeout:
        hard_cap = max(1.0, float(settings.search_hard_timeout_seconds))
        eff = min(eff, hard_cap)
    return eff


class PinpointBoardAdapter:
    """
    Pinpoint company-board adapter.

    Public endpoint: ``GET https://{slug}.pinpointhq.com/postings.json``.
    Supports weak/strong ETag ``If-None-Match`` ``HTTP 304`` conditional short-circuit
    and deterministic SHA-256 content fingerprinting over full posting payloads.
    Fails closed on redirects (tenant renames), HTTP errors, oversize payloads, or
    malformed entries with ``snapshot_complete=False``.
    """

    async def check_board(
        self,
        board: CompanyBoard,
        client: httpx.AsyncClient,
        timeout: float | None = None,
        clock: Clock | None = None,
        resolver: DnsResolver | None = None,
        max_response_bytes: int | None = None,
        **kwargs,
    ) -> BoardCheckResult:
        from src.storage.company_board_registry import is_valid_board_slug

        policy = get_reconciliation_policy("pinpointhq")
        if not validate_board_token_safety(board.board_token) or not is_valid_board_slug(
            "pinpointhq", board.board_token
        ):
            return failure_result(
                kind=FailureKind.UNSAFE_URL,
                error="Invalid Pinpoint board token",
                policy=policy,
            )

        clean_slug = board.board_token.strip().lower()
        encoded_slug = quote(clean_slug, safe="-_.~")
        url = f"https://{encoded_slug}.pinpointhq.com/postings.json"
        headers = build_conditional_headers(
            url,
            _PINPOINT_ACCEPT,
            etag=board.etag,
            last_modified=board.last_modified,
            accept_gzip=True,
        )

        eff_timeout = resolve_pinpoint_board_timeout(timeout, bound_to_search_timeout=False)
        max_bytes = (
            int(max_response_bytes)
            if max_response_bytes is not None
            else int(kwargs.get("max_response_bytes") or settings.pinpoint_board_max_response_bytes)
        )

        with use_clock(clock):
            try:
                status, body_bytes, resp_headers = await fetch_provider_bytes(
                    client,
                    url,
                    headers=headers,
                    timeout=eff_timeout,
                    max_bytes=max_bytes,
                    follow_redirects=False,
                    resolver=resolver,
                )
                if status == 304 and (board.etag or board.last_modified):
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

                items, parse_err = parse_pinpoint_postings_json(body_bytes, expected_slug=clean_slug)
                if parse_err:
                    lowered = parse_err.lower()
                    if "duplicate" in lowered:
                        err_kind = FailureKind.INCOMPLETE_SNAPSHOT
                    elif "mismatch" in lowered or "host" in lowered or "invalid url" in lowered:
                        err_kind = FailureKind.UNSAFE_URL
                    else:
                        err_kind = FailureKind.PARSE_ERROR
                    return failure_result(kind=err_kind, error=parse_err, policy=policy)

                new_etag = resp_headers.get("etag")
                new_lm = resp_headers.get("last-modified")
                fingerprint = compute_board_fingerprint(
                    [(it["job_id"], None, canonical_content_hash(it)) for it in items]
                )
                if board.content_fingerprint and fingerprint == board.content_fingerprint:
                    return BoardCheckResult(
                        success=True,
                        not_modified=True,
                        etag=new_etag or board.etag,
                        last_modified=new_lm or board.last_modified,
                        content_fingerprint=fingerprint,
                        reconciliation_policy=policy,
                        snapshot_complete=True,
                    )

                listings = [
                    _pinpoint_item_to_listing(
                        it,
                        board_token=clean_slug,
                        board_company_name=board.company_name,
                        board_logo_url=board.company_logo_url,
                        board_logo_source=board.company_logo_source,
                        board_logo_verified=bool(board.company_logo_verified),
                        board_logo_checked_at=board.company_logo_checked_at,
                        is_board_monitor=True,
                    )
                    for it in items
                ]
                return BoardCheckResult(
                    success=True,
                    not_modified=False,
                    listings=listings,
                    etag=new_etag,
                    last_modified=new_lm,
                    content_fingerprint=fingerprint,
                    reconciliation_policy=policy,
                    snapshot_complete=True,
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                return failure_result(
                    kind=classify_exception(exc),
                    error=str(exc),
                    policy=policy,
                )
