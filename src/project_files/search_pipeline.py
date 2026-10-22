"""
Search Orchestrator, In-Memory Cache, and Global Deduplicator.

Coordinates concurrent searches across ATS platforms (via Serper + ATS APIs)
and Nigerian job boards (via direct HTML scrapers), streaming deduplicated
results progressively to the client.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import inspect
import time
from typing import AsyncGenerator

import httpx
from loguru import logger

from src.config import settings
from src.project_files.ats_api_client import ATS_CLIENTS
from src.project_files.ats_url_parser import SUPPORTED_ATS_PATTERNS, parse_ats_url
from src.project_files.models import (
    DoneEvent,
    ErrorEvent,
    JobListing,
    ResultsBatch,
    SearchParams,
)
from src.project_files.nigerian_scrapers import NIGERIAN_SCRAPERS, BaseScraper
from src.project_files.observability import (
    SourceKind,
    SourceOutcome,
    SourceTelemetryEvent,
    source_telemetry,
)
from src.project_files.config import SERPER_ENDPOINT
from src.project_files.ats_page_enricher import enrich_ats_page
from collections import OrderedDict
from typing import AsyncGenerator, Awaitable, Callable

from src.project_files.cache_store import cache_store
from src.project_files.http_resilience import resilience_manager, CircuitBreakerOpenError
from src.project_files.field_normalizer import clean_title
from src.project_files.query_builder import build_ats_queries

# ---------------------------------------------------------------------------
# Step 9 — In-Memory Cache (with LRU cap)
# ---------------------------------------------------------------------------

@dataclass
class CacheEntry:
    results: list[JobListing]
    providers_searched: list[str]
    serper_queries_used: int
    stored_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class SearchRunStats:
    serper_calls: int = 0
    serper_cache_hits: int = 0
    pages_fetched: int = 0
    budget_exhausted: bool = False


_cache: OrderedDict[str, CacheEntry] = OrderedDict()


def _cache_key(params: SearchParams, platforms: list[str] | None = None) -> str:
    payload = "api-v3-broad-search:" + params.model_dump_json(exclude={"max_results"})
    if platforms is not None:
        normalized = ",".join(sorted({p.strip().lower() for p in platforms if p and p.strip()}))
        payload += f":platforms={normalized}"
    return hashlib.sha256(payload.encode()).hexdigest()[:24]


def _cache_get(key: str) -> CacheEntry | None:
    if key not in _cache:
        return None
    entry = _cache[key]
    stored_time = entry.stored_at if entry.stored_at.tzinfo else entry.stored_at.replace(tzinfo=timezone.utc)
    age = (datetime.now(timezone.utc) - stored_time).total_seconds()
    if age > settings.cache_ttl_seconds:
        del _cache[key]
        return None
    _cache.move_to_end(key)
    return entry


def _cache_set(key: str, entry: CacheEntry) -> None:
    _cache[key] = entry
    _cache.move_to_end(key)
    if len(_cache) > settings.in_memory_cache_max_entries:
        _cache.popitem(last=False)


# ---------------------------------------------------------------------------
# Global Deduplicator
# ---------------------------------------------------------------------------

class GlobalDeduplicator:
    def __init__(self):
        self._seen: set[str] = set()

    def filter(self, listings: list[JobListing]) -> list[JobListing]:
        new = [l for l in listings if l.id not in self._seen]
        self._seen.update(l.id for l in new)
        return new


def _sort_by_posted_at(listings: list[JobListing]) -> list[JobListing]:
    """Sort listings by posted_at descending, nulls last."""
    def sort_key(item: JobListing):
        if not item.posted_at:
            return datetime.min.replace(tzinfo=timezone.utc)
        dt = item.posted_at
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt

    return sorted(listings, key=sort_key, reverse=True)


def _snippet_listing(
    url: str,
    title: str,
    snippet: str,
    provider: str,
    query_used: str,
) -> JobListing:
    """Keep unsupported ATS results instead of discarding them during URL parsing."""
    listing_id = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    cleaned_title = clean_title(title, snippet) if (title or snippet) else url
    return JobListing(
        id=f"{provider}:{listing_id}",
        provider=provider,
        data_source="snippet",
        title=cleaned_title,
        company="Unknown",
        scraped_at=datetime.now(timezone.utc),
        apply_url=url,
        source_url=url,
        query_used=query_used,
        ats_source=provider,
    )


# ---------------------------------------------------------------------------
# Step 10 — Search Orchestrator
# ---------------------------------------------------------------------------

class SearchOrchestrator:
    """
    Orchestrates concurrent searches across ATS platforms and Nigerian sites.
    Yields events: ("results", ResultsBatch), ("done", DoneEvent), ("error", ErrorEvent).
    """

    def __init__(self):
        self._dropped_by_platform: dict[str, int] = {}
        self._total_dropped_by_platform: dict[str, int] = {}

    @classmethod
    def _record_source_telemetry(
        cls,
        source: str,
        kind: SourceKind,
        outcome: SourceOutcome,
        started_at: float,
        result_count: int = 0,
        dropped_count: int = 0,
    ) -> None:
        source_telemetry.record(
            SourceTelemetryEvent(
                source=source,
                kind=kind,
                outcome=outcome,
                duration_ms=int((time.monotonic() - started_at) * 1000),
                result_count=result_count,
                dropped_count=dropped_count,
            )
        )

    async def _enrich_ats_item(
        self,
        platform: str,
        item: dict,
        query_str: str,
        client: httpx.AsyncClient,
        stats: SearchRunStats | None = None,
    ) -> JobListing | None:
        url = item.get("link", "")
        title = item.get("title", "")
        snippet = item.get("snippet", "")
        if not url or not url.startswith("https"):
            return None

        parsed = parse_ats_url(url)
        if parsed is None:
            if platform in SUPPORTED_ATS_PATTERNS:
                logger.debug(f"[{platform}] Dropping non-job URL: {url}")
                self._dropped_by_platform[platform] = self._dropped_by_platform.get(platform, 0) + 1
                self._total_dropped_by_platform[platform] = self._total_dropped_by_platform.get(platform, 0) + 1
                return None
            # Unsupported ATS platform
            cached_listing = cache_store.get_url_cache(url)
            if cached_listing is not None:
                return cached_listing
            if stats:
                stats.pages_fetched += 1
            listing = await enrich_ats_page(
                url=url,
                provider=platform,
                search_title=title,
                snippet=snippet,
                query_used=query_str,
                client=client,
            )
            if listing and listing.data_source in ("api", "scrape"):
                cache_store.set_url_cache(url, listing)
            return listing

        # Valid job URL on supported ATS platform
        cached_listing = cache_store.get_url_cache(url)
        if cached_listing is not None:
            return cached_listing

        if stats:
            stats.pages_fetched += 1

        ats_client = ATS_CLIENTS.get(parsed.ats)
        try:
            if ats_client:
                listing = await ats_client.fetch(
                    parsed=parsed,
                    client=client,
                    fallback_snippet=title or snippet,
                    query_used=query_str,
                )
            else:
                listing = await enrich_ats_page(
                    url=url,
                    provider=parsed.ats,
                    search_title=title,
                    snippet=snippet,
                    query_used=query_str,
                    client=client,
                )
            if listing and listing.data_source in ("api", "scrape"):
                cache_store.set_url_cache(url, listing)
            return listing
        except Exception as exc:
            logger.warning(f"[{platform}] Error enriching job from {url}: {exc}")
            return _snippet_listing(url, title, snippet, platform, query_str)

    async def _search_ats_serper(
        self,
        platform: str,
        query_str: str,
        params: SearchParams,
        client: httpx.AsyncClient,
        stats: SearchRunStats | None = None,
        is_halted: Callable[[], bool] | None = None,
    ) -> tuple[str, list[JobListing], bool]:
        """
        Executes Serper search for one ATS platform, parses URLs,
        and fetches structured listings from the ATS API.
        Returns (platform_name, listings, serper_query_used_bool).
        """
        listings: list[JobListing] = []
        serper_used = False

        for page in range(1, settings.serper_max_pages + 1):
            if is_halted and is_halted():
                logger.debug(f"[{platform}] Halting Serper pagination: max results reached")
                break

            payload = {
                "q": query_str,
                "page": page,
                "num": 10,
                "hl": "en",
                "tbs": f"qdr:d{params.days_back}" if params.days_back and params.days_back > 0 else "qdr:d7",
            }
            if params.country_code:
                payload["gl"] = params.country_code.strip().lower()

            cache_key = hashlib.sha256(
                f"{query_str}:{page}:{params.days_back}:{params.country_code}".encode()
            ).hexdigest()

            cached_data = cache_store.get_serper_cache(cache_key)
            if cached_data is not None:
                data = cached_data
                if stats:
                    stats.serper_cache_hits += 1
                logger.debug(f"[{platform}] Serper cache hit for page {page}")
            else:
                if settings.serper_mode == "cache_only":
                    logger.info(f"[{platform}] Serper cache miss in cache_only mode; skipping call.")
                    break

                allowed, count = cache_store.check_and_increment_daily_budget(settings.serper_daily_budget)
                if not allowed:
                    logger.warning(
                        f"[{platform}] Serper daily budget limit ({settings.serper_daily_budget}) exceeded ({count})."
                    )
                    if stats:
                        stats.budget_exhausted = True
                    break

                if stats:
                    stats.serper_calls += 1
                serper_used = True

                try:
                    resp = await client.post(
                        SERPER_ENDPOINT,
                        json=payload,
                        headers={
                            "X-API-KEY": settings.serper_api_key,
                            "Content-Type": "application/json",
                        },
                        timeout=settings.ats_request_timeout_seconds + 5.0,
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    cache_store.set_serper_cache(cache_key, data)
                except Exception as exc:
                    logger.warning(f"[{platform}] Serper page {page} failed: {exc}")
                    continue

            items = data.get("organic", [])

            # Concurrency-controlled enrichment via global and host semaphores
            async def _throttled_enrich(item: dict) -> JobListing | None:
                item_url = item.get("link", "")
                if not item_url:
                    return None
                try:
                    async with resilience_manager.throttle(item_url):
                        return await self._enrich_ats_item(platform, item, query_str, client, stats)
                except CircuitBreakerOpenError:
                    return None

            enriched = await asyncio.gather(
                *(_throttled_enrich(item) for item in items),
                return_exceptions=True,
            )
            for job in enriched:
                if isinstance(job, JobListing):
                    listings.append(job)

            # Smart pagination check (Requirement B.2):
            # Fetch page N+1 only if page N returned >= 8 organic results AND >= 50% parsed as real job URLs
            if is_halted and is_halted():
                break

            def _is_real_job_url(u: str) -> bool:
                if not u or not u.startswith("https"):
                    return False
                if platform in SUPPORTED_ATS_PATTERNS:
                    return parse_ats_url(u) is not None
                return True

            valid_job_count = sum(1 for it in items if _is_real_job_url(it.get("link", "")))
            if len(items) < 8 or (valid_job_count < len(items) / 2):
                logger.debug(
                    f"[{platform}] Stopping pagination at page {page}: organic={len(items)}, valid_jobs={valid_job_count}"
                )
                break

        return (platform, listings, serper_used)

    async def _search_nigerian_scraper(
        self,
        scraper: BaseScraper,
        params: SearchParams,
        client: httpx.AsyncClient,
    ) -> tuple[str, list[JobListing], bool]:
        """Execute one Nigerian scraper without failing the whole search."""
        try:
            listings = await scraper.search(client, params)
            return (scraper.site_name, listings, False)
        except Exception as exc:
            logger.warning(f"[{scraper.site_name}] Scraper failed: {exc}")
            return (scraper.site_name, [], False)

    async def run(
        self,
        params: SearchParams,
        platforms: list[str] | None = None,
        is_disconnected: Callable[[], Awaitable[bool]] | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> AsyncGenerator[tuple[str, ResultsBatch | DoneEvent | ErrorEvent], None]:

        start_time = time.monotonic()
        cache_key = _cache_key(params, platforms)
        cached_entry = _cache_get(cache_key)

        if cached_entry:
            logger.info(f"Cache hit for query: {params.job_title}")
            sorted_results = _sort_by_posted_at(cached_entry.results)
            yield ("results", ResultsBatch(batch=sorted_results, total_so_far=len(sorted_results)))
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            yield (
                "done",
                DoneEvent(
                    total=len(sorted_results),
                    search_time_ms=elapsed_ms,
                    serper_queries_used=0,
                    serper_calls=0,
                    serper_cache_hits=0,
                    pages_fetched=0,
                    budget_exhausted=False,
                    providers_searched=cached_entry.providers_searched,
                    providers_skipped=[],
                    cached=True,
                    dropped_count={},
                ),
            )
            return

        deduplicator = GlobalDeduplicator()
        all_collected: list[JobListing] = []
        providers_searched: list[str] = []
        providers_skipped: list[str] = []
        stats = SearchRunStats()

        # Build list of provider tasks
        ats_queries = build_ats_queries(params, platforms)
        http_client = client if client is not None else httpx.AsyncClient(timeout=30.0)
        should_close = client is None

        try:
            tasks: dict[asyncio.Task, tuple[str, SourceKind, float]] = {}

            # Create ATS tasks
            for platform, query_str in ats_queries.items():
                started_at = time.monotonic()
                sig = inspect.signature(self._search_ats_serper)
                kwargs = {}
                if "stats" in sig.parameters:
                    kwargs["stats"] = stats
                if "is_halted" in sig.parameters:
                    kwargs["is_halted"] = lambda: len(all_collected) >= settings.max_results
                t = asyncio.create_task(
                    self._search_ats_serper(
                        platform,
                        query_str,
                        params,
                        http_client,
                        **kwargs,
                    )
                )
                tasks[t] = (platform, SourceKind.ATS, started_at)

            # Create Nigerian scraper tasks
            if params.include_nigerian_sites:
                platforms_lower = (
                    {p.strip().lower() for p in platforms if p and p.strip()}
                    if platforms is not None
                    else None
                )
                for scraper in NIGERIAN_SCRAPERS:
                    if platforms_lower is not None:
                        s_low = scraper.site_name.lower()
                        if s_low not in platforms_lower and not (
                            s_low in ("hotnigerianjobs", "ngcareers")
                            and "jobberman" in platforms_lower
                            and "myjobmag" in platforms_lower
                            and bool(ats_queries)
                        ):
                            continue
                    started_at = time.monotonic()
                    t = asyncio.create_task(
                        self._search_nigerian_scraper(scraper, params, http_client)
                    )
                    tasks[t] = (scraper.site_name, SourceKind.NIGERIAN_BOARD, started_at)

            deadline = time.monotonic() + settings.search_hard_timeout_seconds

            try:
                while tasks:
                    if is_disconnected and await is_disconnected():
                        logger.info("SSE client disconnected. Aborting remaining search tasks.")
                        for pending_task, (
                            pending_provider,
                            pending_kind,
                            pending_started_at,
                        ) in tasks.items():
                            pending_task.cancel()
                            self._record_source_telemetry(
                                pending_provider,
                                pending_kind,
                                SourceOutcome.CANCELLED,
                                pending_started_at,
                            )
                        providers_skipped.extend(provider for provider, _, _ in tasks.values())
                        tasks.clear()
                        return

                    remaining_timeout = max(0.1, deadline - time.monotonic())
                    wait_timeout = min(remaining_timeout, 0.5) if is_disconnected else remaining_timeout
                    done, pending = await asyncio.wait(
                        tasks.keys(),
                        timeout=wait_timeout,
                        return_when=asyncio.FIRST_COMPLETED,
                    )

                    if not done:
                        # Timeout reached or check interval elapsed
                        if time.monotonic() >= deadline:
                            logger.warning("Search reached hard timeout limit")
                            break
                        continue

                    for task in done:
                        provider_name, source_kind, source_started_at = tasks.pop(task)
                        providers_searched.append(provider_name)
                        try:
                            _, listings, query_used = task.result()
                            dropped_count = self._dropped_by_platform.pop(provider_name, 0)
                            self._record_source_telemetry(
                                provider_name,
                                source_kind,
                                SourceOutcome.SUCCESS,
                                source_started_at,
                                result_count=len(listings),
                                dropped_count=dropped_count,
                            )

                            unique_new = deduplicator.filter(listings)
                            if unique_new:
                                all_collected.extend(unique_new)
                                yield (
                                    "results",
                                    ResultsBatch(
                                        batch=unique_new,
                                        total_so_far=len(all_collected),
                                    ),
                                )

                            # Check progressive stopper limit
                            if len(all_collected) >= settings.max_results:
                                logger.info(f"Reached max results limit ({settings.max_results}). Halting remaining tasks.")
                                for pending_task, (
                                    pending_provider,
                                    pending_kind,
                                    pending_started_at,
                                ) in tasks.items():
                                    pending_task.cancel()
                                    self._record_source_telemetry(
                                        pending_provider,
                                        pending_kind,
                                        SourceOutcome.CANCELLED,
                                        pending_started_at,
                                    )
                                providers_skipped.extend(provider for provider, _, _ in tasks.values())
                                tasks.clear()
                                break
                        except Exception as exc:
                            self._record_source_telemetry(
                                provider_name,
                                source_kind,
                                SourceOutcome.FAILURE,
                                source_started_at,
                            )
                            logger.warning(f"Task for provider {provider_name} raised: {exc}")

            finally:
                # Cancel any remaining pending tasks
                for pending_task, (
                    pending_provider,
                    pending_kind,
                    pending_started_at,
                ) in tasks.items():
                    pending_task.cancel()
                    self._record_source_telemetry(
                        pending_provider,
                        pending_kind,
                        SourceOutcome.CANCELLED,
                        pending_started_at,
                    )
                providers_skipped.extend(provider for provider, _, _ in tasks.values())

            # Final sort and cache
            final_sorted = _sort_by_posted_at(all_collected)
            if final_sorted:
                _cache_set(
                    cache_key,
                    CacheEntry(
                        results=final_sorted,
                        providers_searched=providers_searched,
                        serper_queries_used=stats.serper_calls,
                    ),
                )

            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            budget_msg = None
            if stats.budget_exhausted:
                budget_msg = f"Serper daily budget limit ({settings.serper_daily_budget}) exceeded. Returning cached results."

            yield (
                "done",
                DoneEvent(
                    total=len(final_sorted),
                    search_time_ms=elapsed_ms,
                    serper_queries_used=stats.serper_calls,
                    serper_calls=stats.serper_calls,
                    serper_cache_hits=stats.serper_cache_hits,
                    pages_fetched=stats.pages_fetched,
                    budget_exhausted=stats.budget_exhausted,
                    message=budget_msg,
                    providers_searched=providers_searched,
                    providers_skipped=providers_skipped,
                    cached=False,
                    dropped_count=dict(self._total_dropped_by_platform),
                ),
            )
        finally:
            if should_close:
                await http_client.aclose()
