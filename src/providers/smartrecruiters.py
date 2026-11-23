"""
SmartRecruiters company-board monitoring, pagination, and detail hydration adapter.
"""

from __future__ import annotations

import asyncio
import json
import re
from urllib.parse import quote

import httpx

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
from src.providers.pagination import validate_offset_page
from src.safety.url_safety import DnsResolver, UnsafeRedirectError
from src.storage.company_board_registry import CompanyBoard, MonitoredJobDetailState

_SMARTREC_PAGE_SIZE = 100


def _smartrecruiters_listing_item_hash(item: dict) -> str:
    """
    Deterministic full-payload SHA-256 hex digest for a SmartRecruiters listing item.

    Normalizes only the company casing inside ``ref`` so requesting ``wise`` vs ``Wise``
    produces an identical hash while preserving sensitivity to every listing field.
    """
    normalized = dict(item)
    ref_val = normalized.get("ref")
    if isinstance(ref_val, str) and "/companies/" in ref_val:
        normalized["ref"] = re.sub(
            r"(/v1/companies/)([^/]+)(/postings/)",
            lambda m: f"{m.group(1)}{m.group(2).lower()}{m.group(3)}",
            ref_val,
            flags=re.IGNORECASE,
        )
    return canonical_content_hash(normalized)


def _validate_smartrecruiters_listing_entry(
    entry: object,
    *,
    seen_ids: set[str],
    expected_company_slug: str | None = None,
) -> tuple[str | None, str | None]:
    """Validate one SmartRecruiters public listing entry. Returns ``(item_id, error)``."""
    if not isinstance(entry, dict):
        return None, "Malformed SmartRecruiters listing entry (expected object)"

    vis = entry.get("visibility")
    if vis != "PUBLIC":
        return None, f"Non-PUBLIC or missing SmartRecruiters visibility: {vis!r}"

    raw_id = entry.get("id")
    if raw_id is None or isinstance(raw_id, (bool, list, dict)):
        return None, "Malformed SmartRecruiters posting missing id"
    item_id = str(raw_id).strip()
    if not item_id or not item_id.isdigit():
        return None, f"Invalid SmartRecruiters numeric posting id: {raw_id!r}"

    if item_id in seen_ids:
        return None, f"Duplicate SmartRecruiters posting id across snapshot: {item_id}"

    raw_name = entry.get("name")
    if not isinstance(raw_name, str) or not raw_name.strip():
        return None, f"Malformed SmartRecruiters posting {item_id} missing title"

    comp = entry.get("company")
    if comp is not None:
        if not isinstance(comp, dict):
            return None, f"Malformed SmartRecruiters company object on posting {item_id}"
        ident = comp.get("identifier")
        if ident is not None:
            if not isinstance(ident, str) or not ident.strip():
                return None, f"Invalid SmartRecruiters company.identifier on posting {item_id}"
            if expected_company_slug and ident.strip().lower() != expected_company_slug.strip().lower():
                return None, (
                    f"SmartRecruiters company.identifier mismatch on posting {item_id}: "
                    f"expected {expected_company_slug.strip().lower()!r}, got {ident.strip()!r}"
                )

    return item_id, None


def validate_smartrecruiters_page(
    data: object,
    *,
    requested_offset: int,
    expected_total: int | None,
    seen_ids: set[str],
    collected_count: int,
    expected_company_slug: str | None = None,
) -> tuple[list[dict] | None, int | None, int | None, str | None]:
    """
    Validate one sequential page of SmartRecruiters ``/postings`` JSON atomically
    via the shared ``validate_offset_page`` primitive.
    """
    page_seen: set[str] = set()

    def _validate_item(entry: object) -> str | None:
        item_id, entry_err = _validate_smartrecruiters_listing_entry(
            entry,
            seen_ids=seen_ids | page_seen,
            expected_company_slug=expected_company_slug,
        )
        if entry_err or item_id is None:
            return entry_err or "Malformed SmartRecruiters listing entry"
        page_seen.add(item_id)
        return None

    items, resp_limit, total_found, err = validate_offset_page(
        data,
        requested_offset=requested_offset,
        expected_total=expected_total,
        collected_count=collected_count,
        max_limit=100,
        list_key="content",
        total_key="totalFound",
        offset_key="offset",
        limit_key="limit",
        provider_label="SmartRecruiters",
        item_validator=_validate_item,
    )
    if err or items is None or total_found is None:
        return None, None, None, err or "Invalid SmartRecruiters listing page"
    seen_ids.update(page_seen)
    return items, resp_limit, total_found, None


async def _fetch_smartrecruiters_snapshot_with_kind(
    slug: str,
    client: httpx.AsyncClient,
    *,
    timeout: float = 10.0,
    resolver: DnsResolver | None = None,
    max_bytes: int | None = None,
) -> tuple[list[dict] | None, str | None, FailureKind | None]:
    from src.storage.company_board_registry import is_valid_board_slug

    clean_slug = (slug or "").strip().lower()
    if not validate_board_token_safety(slug) or not is_valid_board_slug("smartrecruiters", clean_slug):
        return None, "Invalid SmartRecruiters board token", FailureKind.UNSAFE_URL

    encoded_slug = quote(clean_slug, safe="-_.~")
    offset = 0
    expected_total: int | None = None
    seen_ids: set[str] = set()
    collected: list[dict] = []
    eff_max_bytes = max_bytes if max_bytes is not None else settings.max_response_bytes

    while True:
        url = (
            f"https://api.smartrecruiters.com/v1/companies/{encoded_slug}/postings"
            f"?limit={_SMARTREC_PAGE_SIZE}&offset={offset}&destination=PUBLIC"
        )
        headers = build_conditional_headers(url, "application/json")
        try:
            status, body_bytes, _ = await fetch_provider_bytes(
                client,
                url,
                headers=headers,
                timeout=timeout,
                max_bytes=eff_max_bytes,
                resolver=resolver,
            )
        except asyncio.CancelledError:
            raise
        except UnsafeRedirectError as exc:
            return None, str(exc), FailureKind.UNSAFE_URL
        except SafetyError:
            raise
        except Exception as exc:
            kind = classify_exception(exc)
            if kind in (FailureKind.CIRCUIT_OPEN, FailureKind.RATE_LIMITED, FailureKind.RESPONSE_TOO_LARGE, FailureKind.UNSAFE_URL):
                return None, str(exc), kind
            return None, f"SmartRecruiters pagination error at offset {offset}: {exc}", kind

        if status != 200:
            return None, f"HTTP {status} at offset {offset}", classify_http_status(status)

        try:
            data = json.loads(body_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError):
            return None, f"Invalid JSON payload at offset {offset}", FailureKind.PARSE_ERROR

        page_items, _, total_found, err = validate_smartrecruiters_page(
            data,
            requested_offset=offset,
            expected_total=expected_total,
            seen_ids=seen_ids,
            collected_count=len(collected),
            expected_company_slug=clean_slug,
        )
        if err or page_items is None or total_found is None:
            kind = (
                FailureKind.INCOMPLETE_SNAPSHOT
                if offset > 0 or (err and ("drift" in err.lower() or "duplicate" in err.lower() or "incomplete" in err.lower() or "premature" in err.lower()))
                else FailureKind.PARSE_ERROR
            )
            return None, err or "Invalid SmartRecruiters listing page", kind

        if expected_total is None:
            expected_total = total_found

        if total_found == 0:
            return [], None, None

        collected.extend(page_items)
        if len(collected) >= expected_total:
            break

        next_offset = offset + len(page_items)
        if next_offset <= offset:
            return None, "Zero-progress SmartRecruiters pagination", FailureKind.INCOMPLETE_SNAPSHOT
        offset = next_offset

    if expected_total is None or len(collected) != expected_total or len(seen_ids) != expected_total:
        return None, "Incomplete SmartRecruiters snapshot total mismatch", FailureKind.INCOMPLETE_SNAPSHOT

    return collected, None, None


async def fetch_smartrecruiters_postings_snapshot(
    slug: str,
    client: httpx.AsyncClient,
    *,
    timeout: float = 10.0,
    resolver: DnsResolver | None = None,
    max_bytes: int | None = None,
) -> tuple[list[dict] | None, str | None]:
    """
    Sequentially drain all public SmartRecruiters listing pages for ``slug`` with
    atomic snapshot validation and zero arbitrary page/job caps.
    """
    items, err, _ = await _fetch_smartrecruiters_snapshot_with_kind(
        slug,
        client,
        timeout=timeout,
        resolver=resolver,
        max_bytes=max_bytes,
    )
    return items, err


def _extract_smartrecruiters_listing(
    raw: RawJobPosting,
    *,
    logo_url: str | None,
    logo_source: str | None,
    logo_verified: bool,
) -> JobListing:
    canonical = JobExtractionService.extract(raw)
    listing = CanonicalJobAdapter.to_listing(canonical)
    listing.provider = "smartrecruiters"
    listing.ats_source = "smartrecruiters"
    listing.data_source = "api"
    if logo_verified and logo_url and not listing.company_logo_url:
        listing.company_logo_url = logo_url
        listing.company_logo_source = logo_source
        listing.company_logo_verified = True
    return listing


async def hydrate_smartrecruiters_board_jobs(
    slug: str,
    raw_items: list[dict],
    client: httpx.AsyncClient,
    *,
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
    max_new_hydrations_per_poll: int = 20,
    max_revalidations_per_poll: int = 10,
    max_detail_fetches: int | None = None,
    timeout: float = 10.0,
    is_board_monitor: bool = True,
    resolver: DnsResolver | None = None,
    max_response_bytes: int | None = None,
) -> tuple[list[JobListing], set[str]]:
    """
    Shared SmartRecruiters listing + bounded fair detail hydration path used by both
    ``SmartRecruitersBoardAdapter`` and ``probe_smartrecruiters_board``.

    - Validates every ``ref`` detail URL before fetching.
    - Separates pending/new hydration from stale-detail TTL revalidation.
    - Orders already-known pending unhydrated jobs ahead of newly arrived jobs so
      old pending items never starve on active boards.
    - Preserves rich cached listings on detail 404 or transient failure.
    """
    from src.ats.ats_api_client import (
        enrich_smartrecruiters_board_identity,
        smartrecruiters_payload_to_raw,
        validate_smartrecruiters_ref_url,
    )
    from src.extraction.logo_extractor import LogoResult

    clean_slug = (slug or "").strip().lower()
    known = known_monitored_jobs or {}
    known_states = known_detail_states or {}
    now = epoch_now()

    company_name = board_company_name or humanize_slug(clean_slug)
    company_ident_for_url: str | None = None
    for item in raw_items:
        comp = item.get("company")
        if isinstance(comp, dict):
            cn = comp.get("name")
            if isinstance(cn, str) and cn.strip():
                company_name = cn.strip()
            ci = comp.get("identifier")
            if isinstance(ci, str) and ci.strip() and not company_ident_for_url:
                company_ident_for_url = ci.strip()
            if company_name and company_ident_for_url:
                break

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

    ordered_ids: list[str] = []
    item_by_id: dict[str, dict] = {}
    item_hashes: dict[str, str] = {}

    # Priority queues:
    # - pending_old: previously known jobs still lacking detail hydration whose retry is due
    # - changed_known: already-hydrated jobs whose listing item payload changed
    # - brand_new: jobs never seen before
    # - stale_reval: already-hydrated jobs due for TTL refresh or failed-refresh retry
    pending_old: list[tuple[float, int, str]] = []
    changed_known: list[tuple[int, str]] = []
    brand_new: list[tuple[int, str]] = []
    stale_reval: list[tuple[int, float, str]] = []

    for idx, item in enumerate(raw_items):
        pid = str(item.get("id") or "").strip()
        if not pid:
            continue
        ordered_ids.append(pid)
        item_by_id[pid] = item
        item_hash = _smartrecruiters_listing_item_hash(item)
        item_hashes[pid] = item_hash

        job_id = f"smartrecruiters:{clean_slug}:{pid}"
        cached_entry = known.get(job_id)
        prev_state = known_states.get(job_id)

        if cached_entry is None:
            brand_new.append((idx, pid))
            continue

        prev_hydrated_at = resolve_prev_hydrated_at(prev_state, cached_entry)

        if prev_hydrated_at is None:
            # Respect meaningful listing changes even while an unhydrated job is in retry backoff,
            # while keeping backoff intact for unchanged listings.
            listing_changed = (
                prev_state is not None
                and prev_state.listing_item_hash is not None
                and prev_state.listing_item_hash != item_hash
            )
            if listing_changed:
                changed_known.append((idx, pid))
            else:
                # Known job still awaiting initial detail hydration (never starve behind new arrivals)
                retry_at = prev_state.detail_next_retry_at if prev_state is not None else None
                if retry_at is None or now >= float(retry_at):
                    sort_ts = float(retry_at) if retry_at is not None else float(cached_entry[1] or 0.0)
                    pending_old.append((sort_ts, idx, pid))
            continue

        listing_changed = (
            prev_state is None
            or prev_state.listing_item_hash is None
            or prev_state.listing_item_hash != item_hash
        )
        if listing_changed:
            changed_known.append((idx, pid))
        else:
            is_due, tier, sort_ts = classify_detail_candidate(
                now,
                cached_entry,
                prev_state,
                detail_revalidate_ttl_seconds,
            )
            if is_due:
                stale_reval.append((tier, sort_ts, pid))

    fetch_ids = select_fair_detail_hydration_batch(
        pending_old=pending_old,
        changed_known=changed_known,
        brand_new=brand_new,
        stale_candidates=stale_reval,
        max_new_hydrations_per_poll=max_new_hydrations_per_poll,
        max_revalidations_per_poll=max_revalidations_per_poll,
        max_detail_fetches=max_detail_fetches,
    )
    fetch_set = set(fetch_ids)

    detail_results: dict[str, tuple[int | None, dict | None, str | None]] = {}
    detail_urls: list[tuple[str, str]] = []
    for pid in fetch_ids:
        item = item_by_id[pid]
        raw_ref = item.get("ref")
        if raw_ref is not None:
            detail_url = validate_smartrecruiters_ref_url(
                raw_ref if isinstance(raw_ref, str) else None,
                expected_company_slug=clean_slug,
                expected_job_id=pid,
            )
            if detail_url is None:
                detail_results[pid] = (200, None, "invalid_ref_url")
                continue
        else:
            detail_url = (
                f"https://api.smartrecruiters.com/v1/companies/"
                f"{quote(clean_slug, safe='-_.~')}/postings/{quote(pid, safe='-_.~')}"
            )
        detail_urls.append((pid, detail_url))

    if detail_urls:
        detail_results.update(
            await fetch_detail_json_batch(
                client,
                detail_urls,
                concurrency=3,
                timeout=timeout,
                max_bytes=max_response_bytes,
                resolver=resolver,
            )
        )

    # Bounded cached logo enrichment (at most 1 posting-page HTML fetch per uncached board)
    if not resolved_logo.url and board_logo_checked_at is None:
        sample_posting_url: str | None = None
        for pid in fetch_ids:
            status_code, payload, _ = detail_results.get(pid, (None, None, None))
            if status_code == 200 and isinstance(payload, dict):
                pu = payload.get("postingUrl")
                if isinstance(pu, str) and pu.strip():
                    sample_posting_url = pu.strip()
                    break
        if not sample_posting_url and ordered_ids:
            ident = company_ident_for_url or clean_slug
            sample_posting_url = (
                f"https://jobs.smartrecruiters.com/{quote(ident, safe='-_.~')}/"
                f"{quote(ordered_ids[0], safe='-_.~')}"
            )
        if sample_posting_url:
            try:
                _, enriched_logo = await enrich_smartrecruiters_board_identity(
                    clean_slug,
                    client,
                    registry=registry,
                    use_resilience=True,
                    posting_url=sample_posting_url,
                    company_name=company_name,
                )
                if enriched_logo.url and enriched_logo.verified:
                    resolved_logo = enriched_logo
            except (asyncio.CancelledError, SafetyError):
                raise
            except Exception:
                pass

    logo_url = resolved_logo.url if resolved_logo.verified else None
    logo_source = resolved_logo.source if resolved_logo.verified else None
    logo_verified = bool(resolved_logo.verified and resolved_logo.url)

    listings: list[JobListing] = []
    refreshed_job_ids: set[str] = set()

    def _emit_preserved_or_fallback(
        item: dict,
        jid: str,
        cached: tuple[JobListing, float] | None,
        new_state: MonitoredJobDetailState,
        *,
        item_listing_changed: bool = False,
    ) -> None:
        if cached is not None:
            existing_listing = cached[0]
            update_fields: dict[str, object] = {}
            if (
                item_listing_changed
                or not existing_listing.description_ok
                or new_state.detail_last_hydrated_at is None
            ):
                raw_listing = smartrecruiters_payload_to_raw(
                    item,
                    company_slug=clean_slug,
                    default_company_name=company_name,
                    query_used=clean_slug,
                    is_board_monitor=is_board_monitor,
                    company_logo_url=logo_url,
                    company_logo_source=logo_source,
                    company_logo_verified=logo_verified,
                )
                if raw_listing is not None and raw_listing.raw_title and raw_listing.source_url:
                    fresh_fallback = _extract_smartrecruiters_listing(
                        raw_listing,
                        logo_url=logo_url,
                        logo_source=logo_source,
                        logo_verified=logo_verified,
                    )
                    update_fields.update(
                        {
                            "title": fresh_fallback.title,
                            "company": fresh_fallback.company,
                            "location": fresh_fallback.location,
                            "raw_location": fresh_fallback.raw_location,
                            "is_remote": fresh_fallback.is_remote,
                            "work_model": fresh_fallback.work_model,
                            "work_model_source": fresh_fallback.work_model_source,
                            "work_model_evidence": fresh_fallback.work_model_evidence,
                            "raw_workplace_type": fresh_fallback.raw_workplace_type,
                            "employment_type": fresh_fallback.employment_type,
                            "department": fresh_fallback.department,
                            "posted_at": fresh_fallback.posted_at,
                            "freshness_label": fresh_fallback.freshness_label,
                            "scraped_at": fresh_fallback.scraped_at,
                        }
                    )
                    if not existing_listing.description_ok or not existing_listing.source_url:
                        update_fields["source_url"] = fresh_fallback.source_url
                    if not existing_listing.description_ok or not existing_listing.apply_url:
                        update_fields["apply_url"] = fresh_fallback.apply_url
            if logo_verified and logo_url and not existing_listing.company_logo_url:
                update_fields["company_logo_url"] = logo_url
                update_fields["company_logo_source"] = logo_source
                update_fields["company_logo_verified"] = True
            if update_fields:
                existing_listing = existing_listing.model_copy(update=update_fields)
            listings.append(existing_listing)
            if detail_states_out is not None:
                detail_states_out[jid] = new_state
            return

        raw_listing = smartrecruiters_payload_to_raw(
            item,
            company_slug=clean_slug,
            default_company_name=company_name,
            query_used=clean_slug,
            is_board_monitor=is_board_monitor,
            company_logo_url=logo_url,
            company_logo_source=logo_source,
            company_logo_verified=logo_verified,
        )
        if raw_listing is None or not raw_listing.raw_title or not raw_listing.source_url:
            return
        fallback_listing = _extract_smartrecruiters_listing(
            raw_listing,
            logo_url=logo_url,
            logo_source=logo_source,
            logo_verified=logo_verified,
        )
        listings.append(fallback_listing)
        if detail_states_out is not None:
            detail_states_out[fallback_listing.id] = new_state

    for pid in ordered_ids:
        item = item_by_id[pid]
        job_id = f"smartrecruiters:{clean_slug}:{pid}"
        item_hash = item_hashes[pid]
        cached_entry = known.get(job_id)
        prev_state = known_states.get(job_id)
        item_changed = prev_state is not None and prev_state.listing_item_hash != item_hash
        prev_hydrated_at = resolve_prev_hydrated_at(prev_state, cached_entry)

        if pid in fetch_set:
            status_code, payload, err_reason = detail_results.get(pid, (None, None, None))
            if status_code == 200 and isinstance(payload, dict) and err_reason is None:
                raw = smartrecruiters_payload_to_raw(
                    payload,
                    company_slug=clean_slug,
                    default_job_id=pid,
                    default_company_name=company_name,
                    query_used=clean_slug,
                    is_board_monitor=is_board_monitor,
                    company_logo_url=logo_url,
                    company_logo_source=logo_source,
                    company_logo_verified=logo_verified,
                )
                if raw is not None and raw.raw_title and raw.source_url:
                    listing = _extract_smartrecruiters_listing(
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
                            listing_item_hash=item_hash,
                        )
                    continue

                _emit_preserved_or_fallback(
                    item,
                    job_id,
                    cached_entry,
                    build_detail_failure_state(
                        status_code=200,
                        err_reason=err_reason,
                        prev_state=prev_state,
                        prev_hydrated_at=prev_hydrated_at,
                        now=now,
                        ttl_seconds=detail_revalidate_ttl_seconds,
                        invalid_detail_override=True,
                        listing_item_hash=item_hash,
                    ),
                    item_listing_changed=item_changed,
                )
                continue

            _emit_preserved_or_fallback(
                item,
                job_id,
                cached_entry,
                build_detail_failure_state(
                    status_code=status_code,
                    err_reason=err_reason,
                    prev_state=prev_state,
                    prev_hydrated_at=prev_hydrated_at,
                    now=now,
                    ttl_seconds=detail_revalidate_ttl_seconds,
                    listing_item_hash=item_hash,
                ),
                item_listing_changed=item_changed,
            )
            continue

        if cached_entry is not None:
            _emit_preserved_or_fallback(
                item,
                job_id,
                cached_entry,
                preserve_cached_detail_state(
                    prev_state,
                    prev_hydrated_at,
                    cached_entry,
                    now,
                    listing_item_hash=item_hash,
                ),
                item_listing_changed=item_changed,
            )
            continue

        # New posting deferred beyond this round's detail budget: persist pending state
        _emit_preserved_or_fallback(
            item,
            job_id,
            None,
            build_deferred_detail_state(
                now,
                detail_status="pending_hydration",
                last_error="deferred_pending_hydration",
                listing_item_hash=item_hash,
            ),
        )

    return listings, refreshed_job_ids


class SmartRecruitersBoardAdapter:
    """
    SmartRecruiters company-board adapter.

    - Sequential full pagination (limit=100, destination=PUBLIC).
    - Strict atomic snapshot validation (no partial closure or partial emission).
    - Full-board fingerprint without multi-page ETag short-circuiting.
    - Fair, bounded per-poll detail hydration via validated ``ref`` URLs.
    - Requires 2 independent complete snapshots before closing missing jobs.
    """

    def __init__(
        self,
        detail_revalidate_ttl_seconds: float = 21600.0,
        max_new_hydrations_per_poll: int = 20,
        max_revalidations_per_poll: int = 10,
    ) -> None:
        self.detail_revalidate_ttl_seconds = float(detail_revalidate_ttl_seconds)
        self.max_new_hydrations_per_poll = int(max_new_hydrations_per_poll)
        self.max_revalidations_per_poll = int(max_revalidations_per_poll)

    async def check_board(
        self,
        board: CompanyBoard,
        client: httpx.AsyncClient,
        timeout: float = 10.0,
        *,
        clock: Clock | None = None,
        resolver: DnsResolver | None = None,
        max_response_bytes: int | None = None,
        **kwargs,
    ) -> BoardCheckResult:
        policy = get_reconciliation_policy("smartrecruiters")
        if not validate_board_token_safety(board.board_token):
            return failure_result(
                kind=FailureKind.UNSAFE_URL,
                error="Invalid SmartRecruiters board token",
                policy=policy,
            )

        eff_max_bytes = (
            int(max_response_bytes)
            if max_response_bytes is not None
            else int(kwargs.get("max_response_bytes") or settings.max_response_bytes)
        )

        with use_clock(clock):
            try:
                raw_items, snapshot_err, snapshot_kind = await _fetch_smartrecruiters_snapshot_with_kind(
                    board.board_token,
                    client,
                    timeout=timeout,
                    resolver=resolver,
                    max_bytes=eff_max_bytes,
                )
                if snapshot_err or raw_items is None:
                    return failure_result(
                        kind=snapshot_kind or FailureKind.UNKNOWN,
                        error=snapshot_err or "SmartRecruiters snapshot failed",
                        policy=policy,
                    )

                fingerprint_items: list[tuple[str, str | None, str | None]] = []
                for item in raw_items:
                    pid = str(item.get("id") or "").strip()
                    ts = str(item.get("releasedDate") or "")
                    ch = _smartrecruiters_listing_item_hash(item)
                    fingerprint_items.append((pid, ts, ch))

                fingerprint = compute_board_fingerprint(fingerprint_items)
                known_monitored: dict[str, tuple[JobListing, float]] = kwargs.get("known_monitored_jobs") or {}
                known_detail_states: dict[str, MonitoredJobDetailState] = (
                    kwargs.get("known_detail_states") or {}
                )
                now = epoch_now()

                has_missing_candidates = any(
                    st.missing_confirmation_count > 0 for st in known_detail_states.values()
                )

                fingerprint_changed = not (
                    board.content_fingerprint and fingerprint == board.content_fingerprint
                )

                has_due_work = False
                if not fingerprint_changed and not has_missing_candidates:
                    for item in raw_items:
                        pid = str(item.get("id") or "").strip()
                        jid = f"smartrecruiters:{board.board_token.strip().lower()}:{pid}"
                        cached = known_monitored.get(jid)
                        d_state = known_detail_states.get(jid)
                        if cached is None:
                            has_due_work = True
                            break
                        if d_state is None or d_state.listing_item_hash != _smartrecruiters_listing_item_hash(item):
                            has_due_work = True
                            break
                        if d_state.detail_last_hydrated_at is None:
                            if d_state.detail_next_retry_at is None or now >= float(d_state.detail_next_retry_at):
                                has_due_work = True
                                break
                        else:
                            is_due, _, _ = classify_detail_candidate(
                                now,
                                cached,
                                d_state,
                                self.detail_revalidate_ttl_seconds,
                            )
                            if is_due:
                                has_due_work = True
                                break

                if not fingerprint_changed and not has_due_work and not has_missing_candidates:
                    return BoardCheckResult(
                        success=True,
                        not_modified=True,
                        content_fingerprint=fingerprint,
                        reconciliation_policy=policy,
                    )

                detail_states_out: dict[str, MonitoredJobDetailState] = {}
                listings, refreshed_job_ids = await hydrate_smartrecruiters_board_jobs(
                    board.board_token,
                    raw_items,
                    client,
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
                    max_new_hydrations_per_poll=self.max_new_hydrations_per_poll,
                    max_revalidations_per_poll=self.max_revalidations_per_poll,
                    timeout=timeout,
                    is_board_monitor=True,
                    resolver=resolver,
                    max_response_bytes=eff_max_bytes,
                )

                return BoardCheckResult(
                    success=True,
                    not_modified=False,
                    listings=listings,
                    content_fingerprint=fingerprint,
                    refreshed_job_ids=refreshed_job_ids,
                    detail_states=detail_states_out,
                    reconciliation_policy=policy,
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
