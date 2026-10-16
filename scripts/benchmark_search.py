import asyncio
import time
import json
import sys
from pathlib import Path
from collections import defaultdict
from typing import Any
import httpx

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.project_files.models import SearchParams, JobListing
from src.project_files.search_pipeline import SearchOrchestrator
from src.project_files.config import ATS_PLATFORMS, SERPER_ENDPOINT

async def run_benchmark():
    serper_calls = defaultdict(int)
    page_fetches = defaultdict(int)
    active_requests = 0
    peak_concurrency = 0
    lock = asyncio.Lock()

    # Pre-generate sample organic results for platforms
    def get_sample_organic(platform: str, page: int):
        # realistic mock: page 1 has 10 items, page 2 has 5 items, page 3 has 2 items
        count = 10 if page == 1 else (5 if page == 2 else 2)
        items = []
        for i in range(count):
            if platform == "greenhouse":
                url = f"https://boards.greenhouse.io/company{i}/jobs/{1000 + i}"
            elif platform == "lever":
                url = f"https://jobs.lever.co/company{i}/{2000 + i}"
            elif platform == "workday":
                url = f"https://company{i}.wd1.myworkdayjobs.com/Careers/job/City/Role_{3000 + i}"
            else:
                url = f"https://example.com/{platform}/job/{i}"
            items.append({
                "title": f"Software Engineer {i} - {platform.title()}",
                "link": url,
                "snippet": f"Looking for software engineer at {platform.title()}...",
            })
        return items

    def mock_transport_handler(request: httpx.Request):
        nonlocal active_requests, peak_concurrency
        url_str = str(request.url)
        
        # We simulate a small network latency (e.g. 10ms)
        # But in sync handler we just record metrics
        if "google.serper.dev" in url_str:
            body = json.loads(request.content)
            q = body.get("q", "")
            page = body.get("page", 1)
            # Find platform from q
            plat = "unknown"
            for p in ATS_PLATFORMS:
                if p.site_operator in q:
                    plat = p.name
                    break
            serper_calls[plat] += 1
            serper_calls["__total__"] += 1
            items = get_sample_organic(plat, page)
            return httpx.Response(200, json={"organic": items})
        else:
            # ATS / page fetch
            # find host/platform
            plat = "other"
            for p in ATS_PLATFORMS:
                if p.name in url_str or p.site_operator in url_str:
                    plat = p.name
                    break
            page_fetches[plat] += 1
            page_fetches["__total__"] += 1
            # Return realistic minimal HTML/JSON
            if "boards-api.greenhouse.io" in url_str or "api.lever.co" in url_str:
                return httpx.Response(200, json={"title": "Software Engineer", "content": "<p>Description</p>"})
            return httpx.Response(200, text="<html><head><script type='application/ld+json'>{\"@type\": \"JobPosting\", \"title\": \"Software Engineer\", \"description\": \"Job description with details.\"}</script></head><body></body></html>")

    # Wrap transport to track concurrency accurately with async sleep
    class InstrumentedTransport(httpx.AsyncBaseTransport):
        def __init__(self, handler):
            self.handler = handler

        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            nonlocal active_requests, peak_concurrency
            async with lock:
                active_requests += 1
                if active_requests > peak_concurrency:
                    peak_concurrency = active_requests
            try:
                # Simulate small I/O delay
                await asyncio.sleep(0.01)
                return self.handler(request)
            finally:
                async with lock:
                    active_requests -= 1

    pipeline = SearchOrchestrator()
    params = SearchParams(job_title="Software Engineer", days_back=7, max_results=100)

    # Monkey patch httpx.AsyncClient inside search_pipeline for the benchmark run
    orig_client_cls = httpx.AsyncClient

    transport = InstrumentedTransport(mock_transport_handler)

    def client_factory(*args, **kwargs):
        kwargs["transport"] = transport
        return orig_client_cls(*args, **kwargs)

    httpx.AsyncClient = client_factory

    start_time = time.monotonic()
    results_count = 0
    try:
        async for event_type, event in pipeline.run(params):
            if event_type == "results":
                results_count += len(event.batch)
    finally:
        httpx.AsyncClient = orig_client_cls

    wall_time = time.monotonic() - start_time

    print("=== MEASURE BEFORE: BROAD SEARCH BENCHMARK ===")
    print(f"Wall Time        : {wall_time:.3f} s")
    print(f"Peak Concurrency : {peak_concurrency}")
    print(f"Total Serper Calls: {serper_calls['__total__']}")
    print("Serper Calls Per Platform:")
    for p in sorted(ATS_PLATFORMS, key=lambda x: x.name):
        print(f"  {p.name:15}: {serper_calls[p.name]}")
    print(f"Total Page Fetches : {page_fetches['__total__']}")
    print("Page Fetches Per Platform (sample):")
    for p in sorted(ATS_PLATFORMS, key=lambda x: x.name)[:5]:
        print(f"  {p.name:15}: {page_fetches[p.name]}")
    print(f"Total Results Gathered: {results_count}")

if __name__ == "__main__":
    asyncio.run(run_benchmark())
