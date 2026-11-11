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
import re
import time
from typing import AsyncGenerator

import httpx
from loguru import logger

from src.config import settings
from src.project_files.ats_api_client import ATS_CLIENTS
from src.project_files.ats_url_parser import (
    SUPPORTED_ATS_PATTERNS,
    is_valid_board_slug,
    parse_ats_url,
)
from src.project_files.company_board_registry import company_board_registry
from src.project_files.models import (
    DoneEvent,
    ErrorEvent,
    ExtractionMethod,
    JobListing,
    ProviderOutcomeSummary,
    ResultsBatch,
    SearchParams,
)
from src.project_files.canonical_job_adapter import CanonicalJobAdapter
from src.project_files.job_extraction_service import JobExtractionService, RawJobPosting
from src.project_files.nigerian_scrapers import NIGERIAN_SCRAPERS, BaseScraper
from src.project_files.observability import (
    SourceKind,
    SourceOutcome,
    SourceTelemetryEvent,
    source_telemetry,
)
from src.project_files.config import SERPER_ENDPOINT
from src.project_files.ats_page_enricher import enrich_ats_page, enrich_ats_page_result
from src.project_files.relevance_classifier import RelevanceLevel, classify_relevance
from src.project_files.direct_board_router import (
    extract_company_slug_candidates,
    probe_direct_boards,
)
from src.project_files.extraction_outcome import (
    ExtractionOutcome,
    ExtractionResult,
    map_status_or_exception_to_outcome,
    sanitize_error_text,
)
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
    store_ver = company_board_registry.get_monitored_store_version()
    payload = f"api-v3-broad-search:v={store_ver}:" + params.model_dump_json(exclude={"max_results"})
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
# Global Deduplicator (Step 23: Conservative Order-Independent Deduplicator)
# ---------------------------------------------------------------------------

from src.project_files.deduplicator import GlobalDeduplicator



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
    raw = RawJobPosting(
        provider=provider,
        source_url=url,
        apply_url=url,
        provider_job_id=listing_id,
        raw_title=cleaned_title,
        raw_company="Unknown",
        raw_description=None,
        raw_fields={"snippet": snippet},
        description_is_authentic=False,
        query_used=query_used,
        extraction_method=ExtractionMethod.SNIPPET,
    )
    canonical = JobExtractionService.extract(raw)
    listing = CanonicalJobAdapter.to_listing(canonical)
    listing.id = f"{provider}:{listing_id}"
    listing.provider = provider
    listing.data_source = "snippet"
    listing.ats_source = provider
    listing.description = None
    listing.description_ok = False
    return listing


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
        self._provider_outcomes: dict[str, dict[str, int]] = {}

    def _record_provider_outcome(self, provider: str, outcome: ExtractionOutcome) -> None:
        key = provider.lower()
        if key not in self._provider_outcomes:
            self._provider_outcomes[key] = {}
        counts = self._provider_outcomes[key]
        counts[outcome.value] = counts.get(outcome.value, 0) + 1

    def _build_provider_outcomes_summary(self) -> dict[str, ProviderOutcomeSummary]:
        summary: dict[str, ProviderOutcomeSummary] = {}
        for provider, counts in self._provider_outcomes.items():
            is_partial = (
                counts.get(ExtractionOutcome.RETRYABLE_ERROR.value, 0) > 0
                or counts.get(ExtractionOutcome.RATE_LIMITED.value, 0) > 0
                or counts.get(ExtractionOutcome.PERMANENT_ERROR.value, 0) > 0
                or counts.get(ExtractionOutcome.PARSE_ERROR.value, 0) > 0
            )
            summary[provider] = ProviderOutcomeSummary(
                counts=dict(counts),
                partial=is_partial,
            )
        return summary

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
                self._record_provider_outcome(platform, ExtractionOutcome.NOT_FOUND)
                return None
            # Unsupported ATS platform
            cached_listing = cache_store.get_url_cache(url)
            if cached_listing is not None:
                self._record_provider_outcome(platform, ExtractionOutcome.SUCCESS)
                return cached_listing
            if stats:
                stats.pages_fetched += 1
            listing, res = await enrich_ats_page_result(
                url=url,
                provider=platform,
                search_title=title,
                snippet=snippet,
                query_used=query_str,
                client=client,
            )
            self._record_provider_outcome(platform, res.outcome)
            if listing and listing.data_source in ("api", "scrape"):
                cache_store.set_url_cache(url, listing)
            return listing

        # Valid job URL on supported ATS platform
        cached_listing = cache_store.get_url_cache(url)
        if cached_listing is not None:
            self._record_provider_outcome(parsed.ats, ExtractionOutcome.SUCCESS)
            if parsed.company_slug and is_valid_board_slug(parsed.ats, parsed.company_slug):
                comp_name = cached_listing.company if (cached_listing.company and cached_listing.company != "Unknown Company") else None
                company_board_registry.register_candidate(
                    ats_provider=parsed.ats,
                    board_token=parsed.company_slug,
                    company_name=comp_name,
                    source_url=url,
                )
            return cached_listing

        if stats:
            stats.pages_fetched += 1

        ats_client = ATS_CLIENTS.get(parsed.ats)
        try:
            if ats_client:
                listing, res = await ats_client.fetch_result(
                    parsed=parsed,
                    client=client,
                    fallback_snippet=title or snippet,
                    query_used=query_str,
                )
            else:
                listing, res = await enrich_ats_page_result(
                    url=url,
                    provider=parsed.ats,
                    search_title=title,
                    snippet=snippet,
                    query_used=query_str,
                    client=client,
                )
            self._record_provider_outcome(parsed.ats, res.outcome)
            if listing and listing.data_source in ("api", "scrape"):
                cache_store.set_url_cache(url, listing)
            if parsed.company_slug and is_valid_board_slug(parsed.ats, parsed.company_slug):
                comp_name = listing.company if (listing and listing.company and listing.company != "Unknown Company") else None
                company_board_registry.register_candidate(
                    ats_provider=parsed.ats,
                    board_token=parsed.company_slug,
                    company_name=comp_name,
                    source_url=url,
                )
            return listing
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error(f"[{platform}] Error enriching job from {url} with unexpected_exception: {exc}")
            self._record_provider_outcome(parsed.ats, ExtractionOutcome.PERMANENT_ERROR)
            return None

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
                if not settings.serper_api_key:
                    logger.debug(f"[{platform}] Serper API key not configured; skipping live Serper call.")
                    break

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
                except httpx.HTTPStatusError as exc:
                    outcome = map_status_or_exception_to_outcome(status_code=exc.response.status_code)
                    logger.warning(f"[{platform}] Serper page {page} failed with HTTP {exc.response.status_code}: {exc}")
                    self._record_provider_outcome(platform, outcome)
                    break
                except Exception as exc:
                    outcome = map_status_or_exception_to_outcome(exception=exc)
                    logger.warning(f"[{platform}] Serper page {page} failed: {exc}")
                    self._record_provider_outcome(platform, outcome)
                    break

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
                    self._record_provider_outcome(platform, ExtractionOutcome.RETRYABLE_ERROR)
                    return None

            enriched = await asyncio.gather(
                *(_throttled_enrich(item) for item in items),
                return_exceptions=True,
            )
            for job in enriched:
                if isinstance(job, asyncio.CancelledError):
                    raise job
                elif isinstance(job, Exception):
                    logger.error(
                        f"[{platform}] Item enrichment failed with unexpected_exception: {job}"
                    )
                    self._record_provider_outcome(platform, ExtractionOutcome.PERMANENT_ERROR)
                elif isinstance(job, JobListing):
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

        listings = self._filter_by_relevance(params.job_title, listings)
        return (platform, listings, serper_used)

    def _filter_by_relevance(self, query: str, listings: list[JobListing]) -> list[JobListing]:
        """Filters listings by query relevance using multi-signal classifier."""
        if not query or not query.strip():
            return listings

        filtered: list[JobListing] = []
        for job in listings:
            res = classify_relevance(
                query=query,
                title=job.title or "",
                responsibilities=job.description,
                qualifications=job.requirements,
            )
            if res.level in (RelevanceLevel.STRONG, RelevanceLevel.RELATED, RelevanceLevel.WEAK):
                filtered.append(job)
            else:
                logger.info(
                    f"[{job.provider}] Dropping irrelevant job '{job.title}' for query '{query}': {res.reason}"
                )
                self._record_provider_outcome(job.provider, ExtractionOutcome.NOT_FOUND)
        return filtered

    async def _search_nigerian_scraper(
        self,
        scraper: BaseScraper,
        params: SearchParams,
        client: httpx.AsyncClient,
    ) -> tuple[str, list[JobListing], bool]:
        """Execute one Nigerian scraper without failing the whole search."""
        try:
            try:
                listings, result = await scraper.search_result(client, params)
            except NotImplementedError:
                listings = await scraper.search(client, params)
                result = ExtractionResult(
                    outcome=ExtractionOutcome.SUCCESS,
                    status_code=200,
                    attempts=1,
                )

            self._record_provider_outcome(scraper.site_name, result.outcome)
            return (scraper.site_name, listings, False)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            outcome = map_status_or_exception_to_outcome(exception=exc)
            logger.error(f"[{scraper.site_name}] Scraper failed with unexpected_exception: {exc}")
            self._record_provider_outcome(scraper.site_name, outcome)
            return (scraper.site_name, [], False)

    async def _search_direct_boards(
        self,
        slugs: list[str],
        params: SearchParams,
        platforms: list[str] | None,
        client: httpx.AsyncClient,
    ) -> tuple[str, list[JobListing], bool]:
        """
        Directly probe public ATS boards (Greenhouse, Lever, Ashby) for company slug candidates.
        """
        try:
            listings = await probe_direct_boards(slugs, client, platforms=platforms)
            if not listings:
                return ("direct_board_routing", [], False)

            # Auto-register discovered direct boards into company board registry
            for job in listings:
                ats_prov = job.ats_source or job.provider
                if ats_prov in ("greenhouse", "lever", "ashby"):
                    token = job.query_used or (job.id.split(":")[1] if ":" in job.id else None)
                    if token and is_valid_board_slug(ats_prov, token):
                        comp_name = job.company if (job.company and job.company != "Unknown Company") else None
                        board = company_board_registry.register_candidate(
                            ats_provider=ats_prov,
                            board_token=token,
                            company_name=comp_name,
                            source_url=job.source_url or job.apply_url,
                        )
                        if board:
                            company_board_registry.record_check_success(
                                board_id=board.id,
                                active_job_count=len([j for j in listings if (j.query_used == token or (j.id.split(":")[1] if ":" in j.id else "") == token)]),
                            )

            # If user query contained role words (e.g. 'palantir software engineer'),
            # filter board listings to those matching role keywords to maintain high precision
            query_tokens = [t.lower() for t in re.sub(r"[^\w\s-]", " ", params.job_title).split() if t]
            role_keywords = [t for t in query_tokens if t not in slugs and len(t) > 2]
            if role_keywords:
                filtered = [
                    job for job in listings
                    if any(kw in job.title.lower() for kw in role_keywords)
                ]
                listings = filtered if filtered else listings

            return ("direct_board_routing", listings, False)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning(f"[direct_board_routing] Probe failed: {exc}")
            return ("direct_board_routing", [], False)

    async def _search_monitored_store(
        self,
        params: SearchParams,
        platforms: list[str] | None,
    ) -> tuple[str, list[JobListing], bool]:
        """
        Query persistent monitored jobs store for matching jobs.
        Functions even when Serper is offline, unconfigured, or budget exhausted.
        """
        try:
            if platforms is not None and not platforms:
                return ("monitored_store", [], False)
            listings = company_board_registry.search_monitored_jobs(
                query=params.job_title,
                location=params.location if params.location else None,
                is_remote=params.remote,
                platforms=platforms,
                posted_within_days=params.days_back if params.days_back else None,
                exclude_keywords=params.exclude_keywords if params.exclude_keywords else None,
                limit=min(params.max_results, 50) if params.max_results else 50,
            )
            return ("monitored_store", listings, False)
        except Exception as exc:
            logger.warning(f"[monitored_store] Local store search failed: {exc}")
            return ("monitored_store", [], False)

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
                    provider_outcomes={
                        p: ProviderOutcomeSummary(counts={"success": 1}, partial=False)
                        for p in cached_entry.providers_searched
                    },
                    partial=False,
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
            effective_max_results = min(params.max_results, settings.max_results) if params.max_results else settings.max_results
            for platform, query_str in ats_queries.items():
                started_at = time.monotonic()
                sig = inspect.signature(self._search_ats_serper)
                kwargs = {}
                if "stats" in sig.parameters:
                    kwargs["stats"] = stats
                if "is_halted" in sig.parameters:
                    kwargs["is_halted"] = lambda: len(all_collected) >= effective_max_results
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
                        if s_low not in platforms_lower:
                            continue
                    started_at = time.monotonic()
                    t = asyncio.create_task(
                        self._search_nigerian_scraper(scraper, params, http_client)
                    )
                    tasks[t] = (scraper.site_name, SourceKind.NIGERIAN_BOARD, started_at)

            # Probe candidate ATS company boards directly if company name detected in query
            company_slugs = extract_company_slug_candidates(params.job_title)
            if company_slugs and (platforms is None or len(platforms) > 0):
                started_at = time.monotonic()
                t = asyncio.create_task(
                    self._search_direct_boards(company_slugs, params, platforms, http_client)
                )
                tasks[t] = ("direct_board_routing", SourceKind.ATS, started_at)

            # Query persistent monitored jobs store concurrently (available offline / zero Serper dependency)
            if platforms is None or len(platforms) > 0:
                mon_started_at = time.monotonic()
                t_mon = asyncio.create_task(
                    self._search_monitored_store(params, platforms)
                )
                tasks[t_mon] = ("monitored_store", SourceKind.ATS, mon_started_at)

            deadline = time.monotonic() + settings.search_hard_timeout_seconds
            nigerian_collected_count = 0
            per_scraper_nigerian_cap = min(12, max(5, effective_max_results // 2))
            total_nigerian_cap = min(25, int(effective_max_results * 0.5))

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
                        try:
                            _, listings, query_used = task.result()

                            if provider_name not in ("direct_board_routing", "monitored_store"):
                                providers_searched.append(provider_name)
                                # Cap Nigerian board dominance when ATS queries are active so user gets a balanced mix
                                if source_kind == SourceKind.NIGERIAN_BOARD and bool(ats_queries):
                                    remaining_cap = max(0, total_nigerian_cap - nigerian_collected_count)
                                    allowed = min(len(listings), per_scraper_nigerian_cap, remaining_cap)
                                    listings = listings[:allowed]
                                    nigerian_collected_count += len(listings)

                                dropped_count = self._dropped_by_platform.pop(provider_name, 0)
                                self._record_source_telemetry(
                                    provider_name,
                                    source_kind,
                                    SourceOutcome.SUCCESS,
                                    source_started_at,
                                    result_count=len(listings),
                                    dropped_count=dropped_count,
                                )
                            else:
                                for job in listings:
                                    prov = job.ats_source or job.provider
                                    if prov and prov not in providers_searched:
                                        providers_searched.append(prov)

                            emissions = deduplicator.filter(listings)
                            if emissions:
                                upgraded_items: list[JobListing] = []
                                new_items_to_add: list[JobListing] = []
                                for item in emissions:
                                    matched_c_idx = -1
                                    for c_idx, existing in enumerate(all_collected):
                                        if (
                                            item.id == existing.id
                                            or item.id in existing.aliases
                                            or existing.id in item.aliases
                                            or bool(set(item.aliases) & set(existing.aliases))
                                        ):
                                            matched_c_idx = c_idx
                                            break

                                    if matched_c_idx >= 0:
                                        all_collected[matched_c_idx] = item
                                        upgraded_items.append(item)
                                    else:
                                        new_items_to_add.append(item)

                                if new_items_to_add:
                                    if len(all_collected) + len(new_items_to_add) > effective_max_results:
                                        remaining_slots = max(0, effective_max_results - len(all_collected))
                                        new_items_to_add = new_items_to_add[:remaining_slots]
                                    all_collected.extend(new_items_to_add)

                                batch_to_emit = upgraded_items + new_items_to_add
                                if batch_to_emit:
                                    yield (
                                        "results",
                                        ResultsBatch(
                                            batch=batch_to_emit,
                                            total_so_far=len(all_collected),
                                        ),
                                    )

                            # Check progressive stopper limit
                            if len(all_collected) >= effective_max_results:
                                logger.info(
                                    f"Reached max results limit ({effective_max_results}). Halting remaining tasks."
                                )
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
                            if provider_name not in ("direct_board_routing", "monitored_store"):
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
                    if pending_provider != "direct_board_routing":
                        self._record_source_telemetry(
                            pending_provider,
                            pending_kind,
                            SourceOutcome.CANCELLED,
                            pending_started_at,
                        )
                providers_skipped.extend(provider for provider, _, _ in tasks.values() if provider != "direct_board_routing")

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

            provider_outcomes_summary = self._build_provider_outcomes_summary()
            is_partial = any(s.partial for s in provider_outcomes_summary.values())

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
                    provider_outcomes=provider_outcomes_summary,
                    partial=is_partial,
                ),
            )
        finally:
            if should_close:
                await http_client.aclose()
