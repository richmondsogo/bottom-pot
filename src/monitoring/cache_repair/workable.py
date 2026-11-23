"""
Workable zero-Serper cache & monitored_jobs repair strategy.

Delegates orchestration, SQLite checkpointing, SSRF-safe HTTP lifecycle, and
dry-run-by-default CLI execution to ``src.monitoring.cache_repair.engine``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence
from urllib.parse import quote

import httpx

from src.ats.ats_api_client import WorkableClient, enrich_workable_board_identity
from src.ats.ats_url_parser import ParsedATSUrl
from src.core.http_headers import browser_headers
from src.core.models import JobListing
from src.core.settings import settings
from src.extraction.logo_extractor import LogoResult, extract_company_logo_for_provider
from src.monitoring.cache_repair.engine import (
    CacheRepairReport,
    CacheRepairStrategy,
    SinglePostingResult,
    is_synthetic_record,
    is_synthetic_slug,
    run_cache_repair,
    run_repair_cli,
)
from src.storage.cache_store import CacheStore
from src.storage.company_board_registry import CompanyBoardRegistry, build_canonical_board_url

REPAIR_VERSION = "v41"
_is_synthetic_slug = is_synthetic_slug
_is_synthetic_workable_record = is_synthetic_record


@dataclass
class WorkableRepairReport:
    dry_run: bool = False
    total_urls: int = 0
    unique_slugs: int = 0
    repaired_from_v2_api: int = 0
    canonicalized_urls: int = 0
    boards_reconciled: int = 0
    boards_promoted: int = 0
    boards_identity_enriched: int = 0
    monitored_jobs_updated: int = 0
    monitored_jobs_closed: int = 0
    expired_or_unavailable: int = 0
    skipped_already_repaired: int = 0
    skipped_synthetic: int = 0
    unparsed_urls: int = 0
    transient_errors: int = 0
    serper_calls_used: int = 0


def _is_workable_row(
    url: str,
    parsed: ParsedATSUrl | None,
    existing_listing: JobListing | None,
) -> bool:
    return (
        (parsed is not None and parsed.ats == "workable")
        or "workable.com" in url.lower()
        or (
            existing_listing is not None
            and (existing_listing.provider == "workable" or existing_listing.ats_source == "workable")
        )
    )


async def _fetch_board_identity_readonly(
    company_slug: str,
    client: httpx.AsyncClient,
) -> tuple[str | None, LogoResult]:
    """Read-only Workable account API probe for --dry-run (never writes SQLite)."""
    slug = (company_slug or "").strip()
    if not slug:
        return None, LogoResult()
    encoded_slug = quote(slug, safe="-_.~")
    account_url = f"https://apply.workable.com/api/v1/accounts/{encoded_slug}"
    headers = browser_headers(account_url, "application/json")
    try:
        resp = await client.get(
            account_url,
            headers=headers,
            timeout=min(float(settings.ats_request_timeout_seconds), 8.0),
        )
    except (httpx.HTTPError, OSError):
        return None, LogoResult()
    if resp.status_code != 200:
        return None, LogoResult()
    try:
        payload = resp.json()
    except (ValueError, TypeError):
        return None, LogoResult()
    if not isinstance(payload, dict):
        return None, LogoResult()

    raw_name = payload.get("name")
    org_name = raw_name.strip() if isinstance(raw_name, str) and raw_name.strip() else None
    raw_logo = payload.get("logo")
    logo = extract_company_logo_for_provider(
        "workable",
        workable_account_logo=(str(raw_logo).strip() if isinstance(raw_logo, str) and raw_logo.strip() else None),
        page_url=f"https://apply.workable.com/{encoded_slug}",
        company_name=org_name,
    )
    return org_name, logo


async def _enrich_identity(
    slug: str,
    client: httpx.AsyncClient,
    registry: CompanyBoardRegistry,
    dry_run: bool,
) -> tuple[str | None, LogoResult]:
    if dry_run:
        return await _fetch_board_identity_readonly(slug, client)
    return await enrich_workable_board_identity(slug, client, registry=registry)


def _promote_workable_board_if_needed(
    registry: CompanyBoardRegistry,
    slug: str,
) -> int:
    """Ensure existing Workable board row uses supported capability and canonical board URL."""
    canonical_board_url = build_canonical_board_url("workable", slug)
    with registry._get_connection() as conn:
        cur = conn.execute(
            """
            UPDATE company_boards
            SET monitoring_capability = 'supported',
                board_url = COALESCE(NULLIF(board_url, ''), ?)
            WHERE ats_provider = 'workable'
              AND LOWER(board_token) = ?
              AND monitoring_capability != 'supported'
            """,
            (canonical_board_url, slug.lower()),
        )
        promoted = max(0, cur.rowcount or 0)
        if promoted > 0:
            conn.commit()
    return promoted


async def _fetch_single_posting(
    parsed: ParsedATSUrl,
    client: httpx.AsyncClient,
) -> SinglePostingResult:
    res = await WorkableClient().fetch_raw_result(parsed, client)
    return SinglePostingResult(outcome=res.outcome, raw=res.raw, status_code=res.status_code)


WORKABLE_REPAIR_STRATEGY = CacheRepairStrategy(
    provider="workable",
    state_table="workable_repair_state",
    repair_version=REPAIR_VERSION,
    url_cache_query="""
        SELECT url, listing_json FROM url_cache
        WHERE LOWER(url) LIKE '%workable.com%'
           OR LOWER(listing_json) LIKE '%"workable"%'
        ORDER BY created_at ASC
    """,
    unparsed_detail="Not a single Workable job posting URL",
    terminal_statuses=("repaired", "unavailable_404", "unparsed"),
    canonicalize_aliases=True,
    coalesce_aliases_within_slug=True,
    supports_board_feed=False,
    sync_monitored_from_board_feed=False,
    reconcile_company_boards=True,
    check_capability_supported=True,
    state_detail_prefix_posting="v2_api",
    is_matching_row=_is_workable_row,
    is_synthetic=_is_synthetic_workable_record,
    is_synthetic_slug=_is_synthetic_slug,
    enrich_identity=_enrich_identity,
    promote_board=_promote_workable_board_if_needed,
    fetch_single_posting=_fetch_single_posting,
)


def _to_workable_report(base: CacheRepairReport) -> WorkableRepairReport:
    return WorkableRepairReport(
        dry_run=base.dry_run,
        total_urls=base.total_urls,
        unique_slugs=base.unique_slugs,
        repaired_from_v2_api=base.repaired_from_posting_api,
        canonicalized_urls=base.canonicalized_urls,
        boards_reconciled=base.boards_reconciled,
        boards_promoted=base.boards_promoted,
        boards_identity_enriched=base.boards_identity_enriched,
        monitored_jobs_updated=base.monitored_jobs_updated,
        monitored_jobs_closed=base.monitored_jobs_closed,
        expired_or_unavailable=base.expired_or_unavailable,
        skipped_already_repaired=base.skipped_already_repaired,
        skipped_synthetic=base.skipped_synthetic,
        unparsed_urls=base.unparsed_urls,
        transient_errors=base.transient_errors,
        serper_calls_used=base.serper_calls_used,
    )


async def repair_workable_cache(
    *,
    cache: CacheStore | None = None,
    registry: CompanyBoardRegistry | None = None,
    client: httpx.AsyncClient | None = None,
    ttl_hours: float | None = None,
    concurrency: int = 4,
    max_urls: int | None = None,
    max_slugs: int | None = None,
    force: bool = False,
    dry_run: bool = False,
) -> WorkableRepairReport:
    """Re-extract degraded Workable rows, promote/reconcile board identities, and sync monitored jobs."""
    base = await run_cache_repair(
        WORKABLE_REPAIR_STRATEGY,
        cache=cache,
        registry=registry,
        client=client,
        ttl_hours=ttl_hours,
        concurrency=concurrency,
        max_urls=max_urls,
        max_slugs=max_slugs,
        force=force,
        dry_run=dry_run,
    )
    return _to_workable_report(base)


def main(argv: Sequence[str] | None = None) -> None:
    run_repair_cli(
        "src.monitoring.cache_repair.workable:main",
        "Repair degraded Workable cache rows without Serper spend (--apply to write).",
        repair_workable_cache,
        argv=argv,
    )


if __name__ == "__main__":
    main()
