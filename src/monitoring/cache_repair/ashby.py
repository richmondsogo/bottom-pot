"""
Ashby zero-Serper cache & monitored_jobs repair strategy.

Delegates orchestration, SQLite checkpointing, SSRF-safe HTTP lifecycle, and
dry-run-by-default CLI execution to ``src.monitoring.cache_repair.engine``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence
from urllib.parse import quote

import httpx
from bs4 import BeautifulSoup
from loguru import logger

from src.ats.ats_api_client import (
    AshbyClient,
    ashby_payload_to_raw,
    enrich_ashby_board_identity,
)
from src.ats.ats_url_parser import ParsedATSUrl
from src.core.http_headers import browser_headers
from src.core.models import JobListing
from src.core.settings import settings
from src.extraction.field_normalizer import humanize_slug
from src.extraction.logo_extractor import (
    LogoResult,
    extract_ashby_app_data_from_soup,
    extract_company_logo_for_provider,
)
from src.monitoring.cache_repair.engine import (
    CacheRepairReport,
    CacheRepairStrategy,
    SinglePostingResult,
    build_listing_from_raw,
    is_synthetic_record,
    is_synthetic_slug,
    run_cache_repair,
    run_repair_cli,
)
from src.storage.cache_store import CacheStore
from src.storage.company_board_registry import CompanyBoardRegistry

REPAIR_VERSION = "v39"
_is_synthetic_slug = is_synthetic_slug
_is_synthetic_ashby_record = is_synthetic_record


@dataclass
class AshbyRepairReport:
    dry_run: bool = False
    total_urls: int = 0
    unique_slugs: int = 0
    repaired_from_board_api: int = 0
    repaired_from_posting_api: int = 0
    canonicalized_urls: int = 0
    boards_reconciled: int = 0
    boards_identity_enriched: int = 0
    monitored_jobs_updated: int = 0
    monitored_jobs_closed: int = 0
    expired_or_unavailable: int = 0
    skipped_already_repaired: int = 0
    skipped_synthetic: int = 0
    unparsed_urls: int = 0
    transient_errors: int = 0
    serper_calls_used: int = 0


async def _fetch_board_identity_readonly(
    company_slug: str,
    client: httpx.AsyncClient,
) -> tuple[str | None, LogoResult]:
    """Read-only Ashby board page identity probe for --dry-run (never writes SQLite)."""
    slug = (company_slug or "").strip()
    if not slug:
        return None, LogoResult()
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
    except (httpx.HTTPError, OSError):
        return None, LogoResult()
    if resp.status_code != 200:
        return None, LogoResult()
    content_type = (resp.headers.get("content-type") or "").lower()
    body_text = resp.text or ""
    if "json" in content_type or not body_text.lstrip().startswith("<"):
        return None, LogoResult()

    soup = BeautifulSoup(body_text, "html.parser")
    app_data = extract_ashby_app_data_from_soup(soup)
    org_name: str | None = None
    if isinstance(app_data, dict):
        org = app_data.get("organization")
        if isinstance(org, dict):
            raw_name = org.get("name")
            if isinstance(raw_name, str) and raw_name.strip():
                org_name = raw_name.strip()
    logo = extract_company_logo_for_provider(
        "ashby",
        soup=soup,
        page_url=board_url,
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
    return await enrich_ashby_board_identity(slug, client, registry=registry)


async def _fetch_board_jobs_map(
    slug: str,
    client: httpx.AsyncClient,
) -> tuple[int | None, dict[str, dict]]:
    encoded_slug = quote(slug, safe="-_.~")
    board_api_url = f"https://api.ashbyhq.com/posting-api/job-board/{encoded_slug}?includeCompensation=true"
    headers = browser_headers(board_api_url, "application/json")
    headers["Accept-Encoding"] = "gzip, deflate"
    try:
        resp = await client.get(board_api_url, headers=headers, timeout=12.0)
    except (httpx.HTTPError, OSError) as exc:
        logger.debug(f"[ashby-repair] Board list fetch failed for {slug}: {exc}")
        return None, {}

    if resp.status_code != 200:
        return resp.status_code, {}

    try:
        payload = resp.json()
    except (ValueError, TypeError):
        return 200, {}
    if not isinstance(payload, dict):
        return 200, {}

    jobs_list = payload.get("jobs")
    if not isinstance(jobs_list, list):
        return 200, {}

    items_by_id: dict[str, dict] = {}
    for item in jobs_list:
        if isinstance(item, dict) and item.get("id"):
            items_by_id[str(item["id"]).strip().lower()] = item
    return 200, items_by_id


def _listing_from_ashby_item(
    item: dict,
    company_slug: str,
    source_url: str | None,
    board_name: str | None,
    logo: LogoResult,
) -> JobListing | None:
    raw = ashby_payload_to_raw(
        item,
        company_slug=company_slug,
        source_url=source_url,
        query_used=company_slug,
        default_company_name=board_name or humanize_slug(company_slug),
        is_board_monitor=False,
        company_logo_url=logo.url if logo.verified else None,
        company_logo_source=logo.source if logo.verified else None,
        company_logo_verified=bool(logo.verified and logo.url),
    )
    return build_listing_from_raw(
        "ashby",
        raw,
        board_name=board_name,
        company_slug=company_slug,
        logo=logo,
    )


async def _fetch_single_posting(
    parsed: ParsedATSUrl,
    client: httpx.AsyncClient,
) -> SinglePostingResult:
    res = await AshbyClient().fetch_raw_result(parsed, client)
    return SinglePostingResult(outcome=res.outcome, raw=res.raw, status_code=res.status_code)


ASHBY_REPAIR_STRATEGY = CacheRepairStrategy(
    provider="ashby",
    state_table="ashby_repair_state",
    repair_version=REPAIR_VERSION,
    url_cache_query="SELECT url, listing_json FROM url_cache WHERE LOWER(url) LIKE '%ashby%' ORDER BY created_at ASC",
    unparsed_detail="Not a single Ashby job posting URL",
    terminal_statuses=("repaired", "unavailable_404", "unparsed"),
    check_norm_url_completed=True,
    lowercase_fallback_id=True,
    canonicalize_aliases=True,
    board_item_id_lowercase=True,
    reconcile_company_boards=True,
    monitored_board_state_detail="board_api_monitored",
    is_synthetic=_is_synthetic_ashby_record,
    is_synthetic_slug=_is_synthetic_slug,
    enrich_identity=_enrich_identity,
    fetch_board_items_map=_fetch_board_jobs_map,
    listing_from_board_item=_listing_from_ashby_item,
    fetch_single_posting=_fetch_single_posting,
)


def _to_ashby_report(base: CacheRepairReport) -> AshbyRepairReport:
    return AshbyRepairReport(
        dry_run=base.dry_run,
        total_urls=base.total_urls,
        unique_slugs=base.unique_slugs,
        repaired_from_board_api=base.repaired_from_board_api,
        repaired_from_posting_api=base.repaired_from_posting_api,
        canonicalized_urls=base.canonicalized_urls,
        boards_reconciled=base.boards_reconciled,
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


async def repair_ashby_cache(
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
) -> AshbyRepairReport:
    """Re-extract degraded Ashby rows, reconcile board identities, and sync monitored jobs."""
    base = await run_cache_repair(
        ASHBY_REPAIR_STRATEGY,
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
    return _to_ashby_report(base)


def main(argv: Sequence[str] | None = None) -> None:
    run_repair_cli(
        "src.monitoring.cache_repair.ashby:main",
        "Repair degraded Ashby cache rows without Serper spend (--apply to write).",
        repair_ashby_cache,
        argv=argv,
    )


if __name__ == "__main__":
    main()
