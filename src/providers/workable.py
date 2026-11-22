"""
Workable company-board monitoring and detail hydration adapter.
"""

from __future__ import annotations

import asyncio
import json
import re
from urllib.parse import quote

import httpx

from src.ats.ats_api_client import _WORKABLE_TYPE_MAP, _format_workable_location_item
from src.core.clock import Clock, epoch_now, use_clock
from src.core.models import JobListing
from src.core.settings import settings
from src.extraction.canonical_job_adapter import CanonicalJobAdapter
from src.extraction.field_normalizer import humanize_slug, normalize_job_type
from src.extraction.job_extraction_service import JobExtractionService, RawJobPosting
from src.providers.contract import (
    BoardCheckResult,
    FailureKind,
    classify_exception,
    classify_http_status,
    failure_result,
    get_reconciliation_policy,
)
from src.providers.detail_hydration import (
    build_deferred_detail_state,
    build_detail_failure_state,
    build_hydrated_detail_state,
    classify_detail_candidate,
    fetch_detail_json_batch,
    preserve_cached_detail_state,
    resolve_prev_hydrated_at,
    select_fair_detail_hydration_batch,
)
from src.providers.fingerprint import canonical_content_hash, compute_board_fingerprint
from src.providers.http import (
    build_conditional_headers,
    fetch_provider_bytes,
    validate_board_token_safety,
)
from src.safety.url_safety import DnsResolver
from src.storage.company_board_registry import CompanyBoard, MonitoredJobDetailState


def _workable_widget_job_hash(item: dict) -> str:
    """Stable full 64-hex SHA-256 hash of Workable widget listing metadata."""
    payload = {
        "title": item.get("title"),
        "published_on": item.get("published_on"),
        "department": item.get("department"),
        "employment_type": item.get("employment_type"),
        "telecommuting": item.get("telecommuting"),
        "country": item.get("country"),
        "city": item.get("city"),
        "state": item.get("state"),
        "locations": item.get("locations"),
    }
    return canonical_content_hash(payload)


def _norm_workable_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).casefold()


def _extract_widget_location_tuples(item: dict) -> list[tuple[str, str, str]]:
    """Return non-hidden (city, region/state, country) tuples from a Workable widget item."""
    tuples: list[tuple[str, str, str]] = []
    raw_locs = item.get("locations")
    if isinstance(raw_locs, list):
        for loc in raw_locs:
            if not isinstance(loc, dict) or loc.get("hidden"):
                continue
            city = str(loc.get("city") or "").strip()
            region = str(loc.get("region") or loc.get("state") or "").strip()
            country = str(loc.get("country") or "").strip()
            if city or region or country:
                tuples.append((city, region, country))
    if not tuples:
        city = str(item.get("city") or "").strip()
        state = str(item.get("state") or item.get("region") or "").strip()
        country = str(item.get("country") or "").strip()
        if city or state or country:
            tuples.append((city, state, country))
    return tuples


def _workable_widget_location_signature(item: dict) -> str | None:
    """Stable normalized JSON signature of widget location tuples (including state/region)."""
    tuples = _extract_widget_location_tuples(item)
    if not tuples:
        return None
    normalized = [
        [_norm_workable_text(c), _norm_workable_text(r), _norm_workable_text(co)]
        for c, r, co in tuples
    ]
    return json.dumps(normalized, ensure_ascii=False)


def _workable_widget_differs_from_listing(
    item: dict,
    existing: JobListing,
    *,
    existing_location_signature: str | None = None,
) -> bool:
    """
    Compare all meaningful Workable widget fields against an existing JobListing.
    Missing or empty widget fields are ignored unless authoritative and intentionally empty.
    """
    widget_title = _norm_workable_text(item.get("title"))
    existing_title = _norm_workable_text(existing.title)
    if widget_title and widget_title != existing_title:
        return True

    widget_pub = str(item.get("published_on") or "").strip()[:10]
    if widget_pub:
        if existing.posted_at is None:
            return True
        if widget_pub != existing.posted_at.date().isoformat():
            return True

    raw_emp = str(item.get("employment_type") or "").strip()
    if raw_emp:
        norm_widget_emp = (
            _WORKABLE_TYPE_MAP.get(raw_emp.lower())
            or normalize_job_type(raw_emp)
            or raw_emp.casefold()
        )
        if norm_widget_emp != _norm_workable_text(existing.employment_type):
            return True

    widget_dept = _norm_workable_text(item.get("department"))
    if widget_dept and widget_dept != _norm_workable_text(existing.department):
        return True

    tele = item.get("telecommuting")
    if tele is True:
        if existing.work_model != "remote":
            return True
    elif tele is False:
        # Workable widget reports telecommuting=false for both on_site and hybrid postings.
        if (
            existing.work_model == "remote"
            and (existing.raw_workplace_type or "").strip().lower() not in ("on_site", "hybrid")
        ):
            return True

    widget_loc_sig = _workable_widget_location_signature(item)
    if existing_location_signature and widget_loc_sig and widget_loc_sig != existing_location_signature:
        return True

    loc_tuples = _extract_widget_location_tuples(item)
    if loc_tuples:
        existing_locs = [
            _norm_workable_text(seg)
            for seg in str(existing.location or "").split(";")
            if seg.strip()
        ]
        if not existing_locs:
            return True
        if len(loc_tuples) != len(existing_locs):
            return True
        if len(loc_tuples) > 1:
            formatted = [
                _norm_workable_text(
                    _format_workable_location_item({"city": c, "region": r, "country": co})
                    or ", ".join(p for p in (c, r, co) if p)
                )
                for c, r, co in loc_tuples
            ]
            if formatted != existing_locs:
                return True
        else:
            w_city, w_state, w_country = (_norm_workable_text(x) for x in loc_tuples[0])
            ex_parts = [_norm_workable_text(p) for p in existing_locs[0].split(",") if p.strip()]
            if not ex_parts:
                return True
            if w_city:
                if w_country and len(ex_parts) >= 2:
                    if w_city != ex_parts[0] or w_country != ex_parts[-1]:
                        return True
                elif w_city not in ex_parts:
                    return True
            if w_country:
                if w_country != ex_parts[-1] and w_country not in ex_parts:
                    return True
            if w_state:
                if not w_city:
                    if w_state != ex_parts[0] and w_state not in ex_parts:
                        return True
                elif len(ex_parts) >= 3:
                    if w_state not in ex_parts[1:-1] and w_state not in ex_parts:
                        return True

    return False


def _extract_workable_listing(
    raw: RawJobPosting,
    *,
    logo_url: str | None,
    logo_source: str | None,
    logo_verified: bool,
) -> JobListing:
    canonical = JobExtractionService.extract(raw)
    listing = CanonicalJobAdapter.to_listing(canonical)
    listing.provider = "workable"
    listing.ats_source = "workable"
    listing.data_source = "api"
    if logo_verified and logo_url and not listing.company_logo_url:
        listing.company_logo_url = logo_url
        listing.company_logo_source = logo_source
        listing.company_logo_verified = True
    return listing


async def hydrate_workable_board_jobs(
    slug: str,
    raw_jobs: list[dict],
    client: httpx.AsyncClient,
    *,
    widget_company_name: str | None = None,
    board_company_name: str | None = None,
    board_logo_url: str | None = None,
    board_logo_source: str | None = None,
    board_logo_verified: bool = False,
    board_logo_checked_at: float | None = None,
    registry: object | None = None,
    known_monitored_jobs: dict[str, tuple[JobListing, float]] | None = None,
    known_detail_states: dict[str, MonitoredJobDetailState] | None = None,
    detail_states_out: dict[str, MonitoredJobDetailState] | None = None,
    detail_revalidate_ttl_seconds: float = 21600.0,
    max_revalidations_per_poll: int = 5,
    max_detail_fetches: int | None = None,
    timeout: float = 8.0,
    is_board_monitor: bool = True,
    board_fingerprint_changed: bool = True,
    resolver: DnsResolver | None = None,
    max_response_bytes: int | None = None,
) -> tuple[list[JobListing], set[str]]:
    """
    Shared Workable widget + bounded api/v2 detail hydration path used by both
    WorkableBoardAdapter and probe_workable_board.
    """
    from src.ats.ats_api_client import (
        enrich_workable_board_identity,
        workable_payload_to_raw,
        workable_widget_job_to_raw,
    )
    from src.extraction.logo_extractor import LogoResult

    known = known_monitored_jobs or {}
    known_states = known_detail_states or {}
    now = epoch_now()

    company_name = (
        board_company_name
        or widget_company_name
        or humanize_slug(slug)
    )
    resolved_logo = (
        LogoResult(
            url=board_logo_url,
            source=board_logo_source,
            raw_value=board_logo_url,
            verified=bool(board_logo_verified),
        )
        if board_logo_url and board_logo_verified
        else LogoResult()
    )
    if not resolved_logo.url and board_logo_checked_at is None:
        try:
            enriched_name, enriched_logo = await enrich_workable_board_identity(
                slug,
                client,
                registry=registry,
                use_resilience=True,
            )
            if enriched_name and (
                not company_name
                or company_name == humanize_slug(slug)
                or company_name == widget_company_name
            ):
                company_name = enriched_name
                if enriched_logo.url and enriched_logo.verified:
                    resolved_logo = enriched_logo
        except asyncio.CancelledError:
            raise
        except Exception:
            pass

    immediate_shortcodes: list[str] = []
    stale_candidates: list[tuple[int, float, str]] = []
    widget_by_shortcode: dict[str, dict] = {}
    ordered_shortcodes: list[str] = []

    for item in raw_jobs:
        if not isinstance(item, dict):
            continue
        shortcode = str(item.get("shortcode") or "").strip()
        if not shortcode:
            continue
        widget_by_shortcode[shortcode] = item
        ordered_shortcodes.append(shortcode)

        job_id = f"workable:{slug}:{shortcode}"
        cached_entry = known.get(job_id)
        prev_state = known_states.get(job_id)
        if cached_entry is None:
            immediate_shortcodes.append(shortcode)
        else:
            existing_listing, _ = cached_entry
            existing_loc_sig = prev_state.widget_location_signature if prev_state is not None else None
            if board_fingerprint_changed and _workable_widget_differs_from_listing(
                item,
                existing_listing,
                existing_location_signature=existing_loc_sig,
            ):
                immediate_shortcodes.append(shortcode)
            else:
                is_due, tier, sort_ts = classify_detail_candidate(
                    now,
                    cached_entry,
                    prev_state,
                    detail_revalidate_ttl_seconds,
                )
                if is_due:
                    stale_candidates.append((tier, sort_ts, shortcode))

    fetch_shortcodes = select_fair_detail_hydration_batch(
        immediate_ids=immediate_shortcodes,
        stale_candidates=stale_candidates,
        max_revalidations_per_poll=max_revalidations_per_poll,
        max_detail_fetches=max_detail_fetches,
    )
    fetch_set = set(fetch_shortcodes)

    encoded_slug = quote(slug, safe="-_.~")
    detail_urls = [
        (
            sc,
            f"https://apply.workable.com/api/v2/accounts/{encoded_slug}/jobs/{quote(sc, safe='-_.~')}",
        )
        for sc in fetch_shortcodes
    ]
    detail_results = await fetch_detail_json_batch(
        client,
        detail_urls,
        concurrency=5,
        timeout=timeout,
        max_bytes=max_response_bytes,
        resolver=resolver,
    )

    listings: list[JobListing] = []
    refreshed_job_ids: set[str] = set()
    logo_url = resolved_logo.url if resolved_logo.verified else None
    logo_source = resolved_logo.source if resolved_logo.verified else None
    logo_verified = bool(resolved_logo.verified and resolved_logo.url)

    def _emit_preserved_or_fallback(
        sc_item: dict,
        jid: str,
        cached: tuple[JobListing, float] | None,
        new_state: MonitoredJobDetailState,
    ) -> None:
        if cached is not None:
            listings.append(cached[0])
            if detail_states_out is not None:
                detail_states_out[jid] = new_state
            return
        raw_widget = workable_widget_job_to_raw(
            sc_item,
            company_slug=slug,
            default_company_name=company_name,
            query_used=slug,
            company_logo_url=logo_url,
            company_logo_source=logo_source,
            company_logo_verified=logo_verified,
        )
        if raw_widget is None or not raw_widget.raw_title or not raw_widget.source_url:
            return
        fallback_listing = _extract_workable_listing(
            raw_widget,
            logo_url=logo_url,
            logo_source=logo_source,
            logo_verified=logo_verified,
        )
        listings.append(fallback_listing)
        if detail_states_out is not None:
            detail_states_out[fallback_listing.id] = new_state

    for shortcode in ordered_shortcodes:
        item = widget_by_shortcode[shortcode]
        job_id = f"workable:{slug}:{shortcode}"
        cached_entry = known.get(job_id)
        prev_state = known_states.get(job_id)
        loc_sig = _workable_widget_location_signature(item)
        prev_hydrated_at = resolve_prev_hydrated_at(prev_state, cached_entry)

        if shortcode in fetch_set:
            status_code, payload, err_reason = detail_results.get(shortcode, (None, None, None))
            if status_code == 200 and isinstance(payload, dict) and not payload.get("error"):
                raw = workable_payload_to_raw(
                    payload,
                    company_slug=slug,
                    default_job_id=shortcode,
                    default_company_name=company_name,
                    query_used=slug,
                    is_board_monitor=is_board_monitor,
                    company_logo_url=logo_url,
                    company_logo_source=logo_source,
                    company_logo_verified=logo_verified,
                )
                if (
                    raw is not None
                    and raw.raw_title
                    and raw.source_url
                    and raw.description_is_authentic
                ):
                    listing = _extract_workable_listing(
                        raw,
                        logo_url=logo_url,
                        logo_source=logo_source,
                        logo_verified=logo_verified,
                    )
                    listings.append(listing)
                    refreshed_job_ids.add(listing.id)
                    if detail_states_out is not None:
                        detail_states_out[listing.id] = build_hydrated_detail_state(
                            now,
                            widget_location_signature=loc_sig,
                        )
                    continue

                # HTTP 200 returned an incomplete or invalid detail payload
                _emit_preserved_or_fallback(
                    item,
                    job_id,
                    cached_entry,
                    build_detail_failure_state(
                        status_code=200,
                        err_reason=None,
                        prev_state=prev_state,
                        prev_hydrated_at=prev_hydrated_at,
                        now=now,
                        ttl_seconds=detail_revalidate_ttl_seconds,
                        invalid_detail_override=True,
                        widget_location_signature=loc_sig,
                    ),
                )
                continue

            _emit_preserved_or_fallback(
                item,
                job_id,
                cached_entry,
                build_detail_failure_state(
                    status_code=status_code,
                    err_reason=None if status_code == 200 else err_reason,
                    prev_state=prev_state,
                    prev_hydrated_at=prev_hydrated_at,
                    now=now,
                    ttl_seconds=detail_revalidate_ttl_seconds,
                    widget_location_signature=loc_sig,
                ),
            )
            continue

        if cached_entry is not None:
            # Known unchanged job outside this poll's rotation slice or within retry backoff
            listings.append(cached_entry[0])
            if detail_states_out is not None:
                detail_states_out[job_id] = preserve_cached_detail_state(
                    prev_state,
                    prev_hydrated_at,
                    cached_entry,
                    now,
                    widget_location_signature=loc_sig,
                )
            continue

        # Bounded widget fallback (e.g. direct router cap overflow) — never mark detail-refreshed
        _emit_preserved_or_fallback(
            item,
            job_id,
            None,
            build_deferred_detail_state(
                now,
                detail_status="widget_fallback",
                last_error="deferred_widget_fallback",
                widget_location_signature=loc_sig,
            ),
        )

    return listings, refreshed_job_ids


class WorkableBoardAdapter:
    """Adapter for Workable public widget + bounded api/v2 detail hydration."""

    def __init__(
        self,
        detail_revalidate_ttl_seconds: float = 21600.0,
        max_revalidations_per_poll: int = 5,
    ) -> None:
        self.detail_revalidate_ttl_seconds = float(detail_revalidate_ttl_seconds)
        self.max_revalidations_per_poll = int(max_revalidations_per_poll)

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
        policy = get_reconciliation_policy("workable")
        if not validate_board_token_safety(board.board_token):
            return failure_result(
                kind=FailureKind.UNSAFE_URL,
                error="Invalid Workable board token",
                policy=policy,
            )

        encoded_slug = quote(board.board_token.strip(), safe="-_.~")
        url = f"https://apply.workable.com/api/v1/widget/accounts/{encoded_slug}"
        headers = build_conditional_headers(
            url,
            "application/json",
            etag=board.etag,
            last_modified=board.last_modified,
        )
        eff_max_bytes = (
            int(max_response_bytes)
            if max_response_bytes is not None
            else int(kwargs.get("max_response_bytes") or settings.max_response_bytes)
        )

        with use_clock(clock):
            try:
                status, body_bytes, resp_headers = await fetch_provider_bytes(
                    client,
                    url,
                    headers=headers,
                    timeout=timeout,
                    max_bytes=eff_max_bytes,
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

                try:
                    data = json.loads(body_bytes.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    return failure_result(
                        kind=FailureKind.PARSE_ERROR,
                        error=f"Invalid Workable JSON payload: {exc}",
                        policy=policy,
                    )
                if not isinstance(data, dict) or "jobs" not in data or not isinstance(data.get("jobs"), list):
                    return failure_result(
                        kind=FailureKind.PARSE_ERROR,
                        error="Invalid Workable widget jobs shape",
                        policy=policy,
                    )
                raw_jobs = data["jobs"]

                new_etag = resp_headers.get("etag")
                new_last_mod = resp_headers.get("last-modified")

                fingerprint_items: list[tuple[str, str | None, str | None]] = []
                seen_shortcodes: set[str] = set()
                for j in raw_jobs:
                    if not isinstance(j, dict) or not j.get("shortcode"):
                        continue
                    sc = str(j.get("shortcode")).strip()
                    if sc in seen_shortcodes:
                        return failure_result(
                            kind=FailureKind.INCOMPLETE_SNAPSHOT,
                            error=f"Duplicate Workable shortcode in snapshot: {sc}",
                            policy=policy,
                        )
                    seen_shortcodes.add(sc)
                    ts = str(j.get("published_on") or "")
                    ch = _workable_widget_job_hash(j)
                    fingerprint_items.append((sc, ts, ch))

                fingerprint = compute_board_fingerprint(fingerprint_items)
                known_monitored: dict[str, tuple[JobListing, float]] = kwargs.get("known_monitored_jobs") or {}
                known_detail_states: dict[str, MonitoredJobDetailState] = (
                    kwargs.get("known_detail_states") or {}
                )
                now = epoch_now()
                fingerprint_changed = not (
                    board.content_fingerprint and fingerprint == board.content_fingerprint
                )

                has_new_or_changed = False
                has_due_retry_or_stale = False
                for j in raw_jobs:
                    if not isinstance(j, dict) or not j.get("shortcode"):
                        continue
                    sc = str(j.get("shortcode")).strip()
                    jid = f"workable:{board.board_token}:{sc}"
                    cached = known_monitored.get(jid)
                    d_state = known_detail_states.get(jid)
                    loc_sig = d_state.widget_location_signature if d_state is not None else None
                    if cached is None or (
                        fingerprint_changed
                        and _workable_widget_differs_from_listing(
                            j,
                            cached[0],
                            existing_location_signature=loc_sig,
                        )
                    ):
                        has_new_or_changed = True
                        break
                    is_due, _, _ = classify_detail_candidate(
                        now,
                        cached,
                        d_state,
                        self.detail_revalidate_ttl_seconds,
                    )
                    if is_due:
                        has_due_retry_or_stale = True

                if (
                    not fingerprint_changed
                    and not has_new_or_changed
                    and not has_due_retry_or_stale
                ):
                    return BoardCheckResult(
                        success=True,
                        not_modified=True,
                        etag=new_etag or board.etag,
                        last_modified=new_last_mod or board.last_modified,
                        content_fingerprint=fingerprint,
                        reconciliation_policy=policy,
                    )

                detail_states_out: dict[str, MonitoredJobDetailState] = {}
                listings, refreshed_job_ids = await hydrate_workable_board_jobs(
                    board.board_token,
                    raw_jobs,
                    client,
                    widget_company_name=(str(data.get("name")).strip() if data.get("name") else None),
                    board_company_name=board.company_name,
                    board_logo_url=board.company_logo_url,
                    board_logo_source=board.company_logo_source,
                    board_logo_verified=bool(board.company_logo_verified),
                    board_logo_checked_at=board.company_logo_checked_at,
                    registry=kwargs.get("registry"),
                    known_monitored_jobs=known_monitored,
                    known_detail_states=known_detail_states,
                    detail_states_out=detail_states_out,
                    detail_revalidate_ttl_seconds=self.detail_revalidate_ttl_seconds,
                    max_revalidations_per_poll=self.max_revalidations_per_poll,
                    timeout=timeout,
                    is_board_monitor=True,
                    board_fingerprint_changed=fingerprint_changed,
                    resolver=resolver,
                    max_response_bytes=eff_max_bytes,
                )

                return BoardCheckResult(
                    success=True,
                    not_modified=False,
                    listings=listings,
                    etag=new_etag,
                    last_modified=new_last_mod,
                    content_fingerprint=fingerprint,
                    refreshed_job_ids=refreshed_job_ids,
                    detail_states=detail_states_out,
                    reconciliation_policy=policy,
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                return failure_result(
                    kind=classify_exception(exc),
                    error=str(exc),
                    policy=policy,
                )
