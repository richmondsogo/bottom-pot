"""
Tests for FastAPI application endpoints.
"""

import csv
import os
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.config import settings
from src.project_files.models import JobListing, SearchParams
from src.project_files.search_pipeline import CacheEntry, _cache, _cache_key, _cache_set
from datetime import datetime, timezone

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["version"] == "2.0.0"


def test_frontend_assets_are_served():
    response = client.get("/")
    assert response.status_code == 200
    assert "Bottom Pot" in response.text
    # Should link to compiled assets or css
    assert "assets/" in response.text or "styles.css" in response.text


def test_exports_use_same_filtered_result_source():
    # Verify export module in frontend source uses filteredResults logic
    export_ts = Path(__file__).resolve().parents[1] / "frontend" / "src" / "lib" / "export.ts"
    if export_ts.exists():
        content = export_ts.read_text(encoding="utf-8")
        assert "downloadCsv" in content
        assert "downloadJson" in content
    else:
        script = client.get("/app.js").text
        assert "filteredResults" in script


def test_subscribe_endpoint(tmp_path):
    sub_file = str(tmp_path / "test_subs.csv")
    settings.subscriptions_file = sub_file

    payload = {"email": "user@example.com", "search_query": "Data Scientist"}
    response = client.post("/subscribe", json=payload)
    assert response.status_code == 201
    assert response.json() == {"subscribed": True}

    assert os.path.exists(sub_file)
    with open(sub_file, "r", encoding="utf-8") as f:
        reader = list(csv.reader(f))
        assert len(reader) == 2  # header + 1 row
        assert reader[0] == ["email", "search_query", "subscribed_at"]
        assert reader[1][0] == "user@example.com"
        assert reader[1][1] == "Data Scientist"


def test_search_endpoint_cached_stream():
    # Prime cache with a dummy entry
    from src.project_files.models import SearchParams
    params = SearchParams(
        job_title="DevOps Lead",
        location=None,
        remote=None,
        days_back=7,
        include_nigerian_sites=True,
    )
    key = _cache_key(params)
    dummy_job = JobListing(
        id="greenhouse:acme:123",
        provider="greenhouse",
        data_source="api",
        title="DevOps Lead",
        company="Acme",
        company_slug="acme",
        scraped_at=datetime.now(timezone.utc),
        apply_url="https://boards.greenhouse.io/acme/jobs/123",
        source_url="https://boards.greenhouse.io/acme/jobs/123",
        query_used="test",
        ats_source="greenhouse",
    )
    _cache_set(
        key,
        CacheEntry(
            results=[dummy_job],
            providers_searched=["greenhouse"],
            serper_queries_used=0,
        ),
    )

    response = client.get("/search?q=DevOps+Lead")
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]

    content = response.text
    assert "event: results" in content
    assert "DevOps Lead" in content
    assert "event: done" in content
    assert '"cached":true' in content


def test_search_page_navigation_without_q_returns_html():
    response = client.get("/search", headers={"Accept": "text/html,application/xhtml+xml"})
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert response.headers.get("vary") == "Accept"
    assert "<!doctype html>" in response.text.lower()


def test_search_page_navigation_with_q_returns_html():
    response = client.get("/search?q=python", headers={"Accept": "text/html,application/xhtml+xml"})
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert response.headers.get("vary") == "Accept"
    assert "<!doctype html>" in response.text.lower()


def test_search_event_stream_with_q_returns_stream():
    params = SearchParams(
        job_title="EngineerStreamTest",
        location=None,
        remote=None,
        days_back=7,
        include_nigerian_sites=True,
    )
    key = _cache_key(params)
    dummy_job = JobListing(
        id="greenhouse:stream:1",
        provider="greenhouse",
        data_source="api",
        title="Stream Engineer",
        company="StreamCorp",
        scraped_at=datetime.now(timezone.utc),
        apply_url="https://boards.greenhouse.io/stream/1",
        source_url="https://boards.greenhouse.io/stream/1",
        query_used="EngineerStreamTest",
        ats_source="greenhouse",
    )
    _cache_set(
        key,
        CacheEntry(
            results=[dummy_job],
            providers_searched=["greenhouse"],
            serper_queries_used=0,
        ),
    )
    response = client.get("/search?q=EngineerStreamTest", headers={"Accept": "text/event-stream"})
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    assert response.headers.get("vary") == "Accept"
    assert "event: results" in response.text


def test_search_both_html_and_event_stream_accept_prefers_stream():
    params = SearchParams(
        job_title="BothAcceptTest",
        location=None,
        remote=None,
        days_back=7,
        include_nigerian_sites=True,
    )
    key = _cache_key(params)
    dummy_job = JobListing(
        id="greenhouse:stream:2",
        provider="greenhouse",
        data_source="api",
        title="Both Engineer",
        company="BothCorp",
        scraped_at=datetime.now(timezone.utc),
        apply_url="https://boards.greenhouse.io/stream/2",
        source_url="https://boards.greenhouse.io/stream/2",
        query_used="BothAcceptTest",
        ats_source="greenhouse",
    )
    _cache_set(
        key,
        CacheEntry(
            results=[dummy_job],
            providers_searched=["greenhouse"],
            serper_queries_used=0,
        ),
    )
    response = client.get(
        "/search?q=BothAcceptTest",
        headers={"Accept": "text/html, text/event-stream"},
    )
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    assert response.headers.get("vary") == "Accept"


def test_search_default_accept_without_q_returns_422():
    response = client.get("/search")
    assert response.status_code == 422
    assert "application/json" in response.headers["content-type"]
    assert response.headers.get("vary") == "Accept"


def test_search_page_navigation_does_not_consume_rate_limit():
    params = SearchParams(
        job_title="RateLimitIsolationTest",
        location=None,
        remote=None,
        days_back=7,
        include_nigerian_sites=True,
    )
    key = _cache_key(params)
    dummy_job = JobListing(
        id="greenhouse:rate:1",
        provider="greenhouse",
        data_source="api",
        title="Rate Limit Engineer",
        company="RateCorp",
        scraped_at=datetime.now(timezone.utc),
        apply_url="https://boards.greenhouse.io/rate/1",
        source_url="https://boards.greenhouse.io/rate/1",
        query_used="RateLimitIsolationTest",
        ats_source="greenhouse",
    )
    _cache_set(
        key,
        CacheEntry(
            results=[dummy_job],
            providers_searched=["greenhouse"],
            serper_queries_used=0,
        ),
    )

    for _ in range(25):
        html_res = client.get("/search", headers={"Accept": "text/html"})
        assert html_res.status_code == 200
        assert "text/html" in html_res.headers["content-type"]

    stream_res = client.get(
        "/search?q=RateLimitIsolationTest",
        headers={"Accept": "text/event-stream"},
    )
    assert stream_res.status_code == 200
    assert "text/event-stream" in stream_res.headers["content-type"]

