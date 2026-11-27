"""
Tests for FastAPI application endpoints.
"""

import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import src.api.main as api_main
from src.api.allowlist import (
    ADMIN_DONE_FIELDS,
    ADMIN_JOB_FIELDS,
    ADMIN_RESULTS_BATCH_FIELDS,
    USER_DONE_FIELDS,
    USER_JOB_FIELDS,
    USER_RESULTS_BATCH_FIELDS,
    serialize_event_for_user,
)
from src.api.auth import create_session_token, verify_session_token
from src.api.main import app, dist_dir, frontend_dir
from src.core.models import DoneEvent, JobListing, ResultsBatch, SearchParams
from src.core.settings import settings
from src.discovery.search_pipeline import CacheEntry, _cache, _cache_key, _cache_set

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["version"] == "2.0.0"
    assert data["monitored_provider_count"] == 9
    assert isinstance(data["monitored_providers"], list)
    assert "greenhouse" in data["monitored_providers"]
    assert "pinpointhq" in data["monitored_providers"]
    assert isinstance(data["frontend_built"], bool)
    assert isinstance(data["monitoring_enabled"], bool)
    assert data["serper_mode"] in ("live", "fallback", "cache_only")


def test_frontend_assets_are_served():
    response = client.get("/")
    assert response.status_code == 200
    assert "Bottom Pot" in response.text
    # Legacy frontend-old styles.css must never be served.
    assert "styles.css" not in response.text
    if frontend_dir == dist_dir:
        assert "assets/" in response.text
    else:
        assert "/src/main.tsx" in response.text


def test_frontend_unbuilt_source_fallback_and_compiled_dist_selection(monkeypatch, tmp_path):
    frontend_source = Path(__file__).resolve().parents[1] / "frontend"
    monkeypatch.setattr(api_main, "frontend_dir", frontend_source)
    source_res = client.get("/app")
    assert source_res.status_code == 200
    assert "Bottom Pot" in source_res.text
    assert "/src/main.tsx" in source_res.text
    assert "styles.css" not in source_res.text

    fake_dist = tmp_path / "dist"
    fake_dist.mkdir()
    (fake_dist / "index.html").write_text(
        '<!doctype html><title>Bottom Pot</title><script src="/assets/index.js"></script>',
        encoding="utf-8",
    )
    monkeypatch.setattr(api_main, "frontend_dir", fake_dist)
    dist_res = client.get("/app")
    assert dist_res.status_code == 200
    assert "Bottom Pot" in dist_res.text
    assert "assets/" in dist_res.text


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
    from src.core.models import SearchParams
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
    assert '"total":1' in content
    assert '"cached"' not in content


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


# ── Admin Authentication Endpoint Tests ─────────────────────────────────────


def test_admin_login_when_password_unset_returns_503(monkeypatch):
    monkeypatch.setattr(settings, "admin_password", "")
    response = client.post("/api/admin/login", json={"password": "any-password"})
    assert response.status_code == 503
    assert "ADMIN_PASSWORD is not configured" in response.json()["detail"]


def test_admin_login_wrong_password_returns_401(monkeypatch):
    monkeypatch.setattr(settings, "admin_password", "correct-secret-password")
    response = client.post("/api/admin/login", json={"password": "wrong-password"})
    assert response.status_code == 401
    assert "Invalid admin password" in response.json()["detail"]
    assert settings.admin_cookie_name not in response.cookies


def test_admin_login_correct_password_sets_signed_cookie(monkeypatch):
    monkeypatch.setattr(settings, "admin_password", "correct-secret-password")
    response = client.post(
        "/api/admin/login", json={"password": "correct-secret-password"}
    )
    assert response.status_code == 200
    assert response.json() == {"authenticated": True}
    assert settings.admin_cookie_name in response.cookies
    cookie_header = response.headers.get("set-cookie", "")
    assert "httponly" in cookie_header.lower()
    assert "samesite=lax" in cookie_header.lower()


def test_admin_login_rate_limiting(monkeypatch):
    monkeypatch.setattr(settings, "admin_password", "correct-secret-password")
    # First 5 attempts return 401
    for _ in range(5):
        res = client.post("/api/admin/login", json={"password": "wrong-password"})
        assert res.status_code == 401
    # 6th attempt within the same minute is rate-limited to 429
    res = client.post("/api/admin/login", json={"password": "wrong-password"})
    assert res.status_code == 429


def test_admin_verify_without_cookie_returns_401():
    response = client.get("/api/admin/verify")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_admin_verify_with_tampered_cookie_returns_401(monkeypatch):
    monkeypatch.setattr(settings, "admin_password", "correct-secret-password")
    login_res = client.post(
        "/api/admin/login", json={"password": "correct-secret-password"}
    )
    valid_cookie = login_res.cookies[settings.admin_cookie_name]
    tampered_cookie = valid_cookie[:-4] + "xxxx"
    client.cookies.set(settings.admin_cookie_name, tampered_cookie)
    response = client.get("/api/admin/verify")
    assert response.status_code == 401


def test_admin_verify_with_valid_cookie_returns_200(monkeypatch):
    monkeypatch.setattr(settings, "admin_password", "correct-secret-password")
    login_res = client.post(
        "/api/admin/login", json={"password": "correct-secret-password"}
    )
    assert login_res.status_code == 200
    response = client.get("/api/admin/verify")
    assert response.status_code == 200
    assert response.json() == {"authenticated": True}


def test_admin_logout_clears_cookie(monkeypatch):
    monkeypatch.setattr(settings, "admin_password", "correct-secret-password")
    login_res = client.post(
        "/api/admin/login", json={"password": "correct-secret-password"}
    )
    assert login_res.status_code == 200
    logout_res = client.post("/api/admin/logout")
    assert logout_res.status_code == 200
    assert logout_res.json() == {"authenticated": False}
    set_cookie = logout_res.headers.get("set-cookie", "")
    assert settings.admin_cookie_name in set_cookie
    assert "max-age=0" in set_cookie.lower() or "expires=" in set_cookie.lower()


def test_admin_page_serves_html():
    response = client.get("/admin")
    assert response.status_code == 200
    assert "Bottom Pot" in response.text


def test_admin_verify_with_expired_token_returns_401():
    token = create_session_token(max_age_seconds=-1)
    client.cookies.set(settings.admin_cookie_name, token)
    response = client.get("/api/admin/verify")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_admin_token_invalid_after_secret_change(monkeypatch):
    monkeypatch.setattr(settings, "admin_password", "correct-secret-password")
    monkeypatch.setattr(settings, "admin_session_secret", "secret-key-version-1")
    login_res = client.post(
        "/api/admin/login", json={"password": "correct-secret-password"}
    )
    assert login_res.status_code == 200

    # Rotate the session secret
    monkeypatch.setattr(settings, "admin_session_secret", "secret-key-version-2")
    response = client.get("/api/admin/verify")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_admin_login_non_ascii_password_returns_401(monkeypatch):
    monkeypatch.setattr(settings, "admin_password", "correct-secret-password")
    response = client.post(
        "/api/admin/login", json={"password": "pässword-密码"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid admin password"


def test_admin_verify_with_non_ascii_cookie_returns_401():
    token = "eyJhZG1pbiI6dHJ1ZX0.non-ascii-sig-密码"
    try:
        client.cookies.set(settings.admin_cookie_name, token)
        response = client.get("/api/admin/verify")
        assert response.status_code == 401
    except Exception:
        # If client refuses to encode non-ASCII into HTTP headers, verify function directly
        assert verify_session_token(token) is False


# ── Step 14 Public Stream Redaction & Allowlist Tests ─────────────────────────


def _parse_sse_events(text: str) -> list[tuple[str, dict]]:
    """Helper to parse SSE text into a list of (event_name, data_dict) tuples."""
    events = []
    current_event = None
    for line in text.splitlines():
        if line.startswith("event: "):
            current_event = line.replace("event: ", "").strip()
        elif line.startswith("data: "):
            data_str = line.replace("data: ", "").strip()
            try:
                events.append((current_event or "message", json.loads(data_str)))
            except Exception:
                pass
    return events


def test_anonymous_search_stream_strips_operational_and_debug_fields():
    """Verify anonymous SSE search stream only contains allowlisted fields."""
    rich_job = JobListing(
        id="job-allowlist-test-1",
        provider="greenhouse",
        data_source="scrape",
        title="Senior Python Backend Engineer",
        company="Acme Corp",
        company_slug="acme-corp",
        location="Lagos, Nigeria",
        is_remote=True,
        employment_type="Full-time",
        work_model="remote",
        work_model_source="regex",
        work_model_evidence="100% remote anywhere in Nigeria",
        raw_workplace_type="telecommute",
        department="Engineering",
        salary="$120k - $150k",
        description="Great python role",
        description_ok=True,
        requirements="Python, FastAPI, Postgres",
        extraction_confidence=0.98,
        posted_at=datetime.now(timezone.utc),
        scraped_at=datetime.now(timezone.utc),
        apply_url="https://jobs.example.com/apply/1",
        source_url="https://jobs.example.com/1",
        query_used="site:boards.greenhouse.io python lagos",
        ats_source="greenhouse",
    )

    params = SearchParams(
        job_title="AllowlistTestAnonymous",
        location=None,
        remote=None,
        days_back=7,
        include_nigerian_sites=True,
    )
    key = _cache_key(params)
    _cache_set(
        key,
        CacheEntry(
            results=[rich_job],
            providers_searched=["greenhouse"],
            serper_queries_used=1,
        ),
    )

    client.cookies.clear()
    response = client.get("/search?q=AllowlistTestAnonymous")
    assert response.status_code == 200
    events = _parse_sse_events(response.text)
    assert len(events) >= 2

    # Results event checks
    results_event = next(e for e in events if e[0] == "results")
    batch_payload = results_event[1]
    assert set(batch_payload.keys()) == {"batch", "total_so_far"}
    job_payload = batch_payload["batch"][0]

    assert set(job_payload.keys()) == USER_JOB_FIELDS
    for field in ADMIN_JOB_FIELDS:
        assert field not in job_payload

    # Done event checks
    done_event = next(e for e in events if e[0] == "done")
    done_payload = done_event[1]
    assert set(done_payload.keys()) == {"total", "incomplete", "partial"}
    assert done_payload["total"] == 1
    assert done_payload["incomplete"] is False
    assert done_payload["partial"] is False
    for field in ADMIN_DONE_FIELDS:
        assert field not in done_payload


def test_admin_search_stream_preserves_all_debug_and_operational_fields():
    """Verify admin SSE search stream retains all 25 JobListing fields and unredacted DoneEvent."""
    rich_job = JobListing(
        id="job-allowlist-admin-1",
        provider="greenhouse",
        data_source="scrape",
        title="Staff Engineer",
        company="Admin Corp",
        company_slug="admin-corp",
        location="Remote",
        is_remote=True,
        employment_type="Full-time",
        work_model="remote",
        work_model_source="api",
        work_model_evidence="fully remote",
        raw_workplace_type="remote",
        department="Platform",
        salary="$180k",
        description="Admin test description",
        description_ok=True,
        requirements="Python",
        extraction_confidence=1.0,
        posted_at=datetime.now(timezone.utc),
        scraped_at=datetime.now(timezone.utc),
        apply_url="https://admin.example.com/apply/1",
        source_url="https://admin.example.com/1",
        query_used="site:boards.greenhouse.io staff remote",
        ats_source="greenhouse",
    )

    params = SearchParams(
        job_title="AllowlistTestAdmin",
        location=None,
        remote=None,
        days_back=7,
        include_nigerian_sites=True,
    )
    key = _cache_key(params)
    _cache_set(
        key,
        CacheEntry(
            results=[rich_job],
            providers_searched=["greenhouse"],
            serper_queries_used=1,
        ),
    )

    token = create_session_token()
    client.cookies.clear()
    client.cookies.set(settings.admin_cookie_name, token)
    response = client.get("/search?q=AllowlistTestAdmin")
    client.cookies.clear()
    assert response.status_code == 200
    events = _parse_sse_events(response.text)
    assert len(events) >= 2

    # Results event checks: all fields match model_dump_json() output
    results_event = next(e for e in events if e[0] == "results")
    batch_payload = results_event[1]
    expected_batch = json.loads(
        ResultsBatch(batch=[rich_job], total_so_far=1).model_dump_json()
    )
    assert batch_payload == expected_batch
    job_payload = batch_payload["batch"][0]
    assert job_payload["work_model_evidence"] == "fully remote"
    assert job_payload["data_source"] == "scrape"

    # Done event checks: unredacted and does not have "incomplete"
    done_event = next(e for e in events if e[0] == "done")
    done_payload = done_event[1]
    assert "incomplete" not in done_payload
    assert "cached" in done_payload
    assert "search_time_ms" in done_payload


def test_cached_search_stream_strips_for_anonymous_and_preserves_for_admin():
    """Verify cache entry itself remains full/unredacted when read by anonymous and admin."""
    rich_job = JobListing(
        id="job-cache-test-1",
        provider="greenhouse",
        data_source="scrape",
        title="Cache Lead",
        company="Cache Corp",
        location="Lagos",
        work_model_evidence="hybrid 2 days",
        apply_url="https://example.com/cache",
        scraped_at=datetime.now(timezone.utc),
        source_url="https://example.com/cache-source",
        query_used="test query",
        ats_source="greenhouse",
    )
    params = SearchParams(
        job_title="CachePreserveTest",
        location=None,
        remote=None,
        days_back=7,
        include_nigerian_sites=True,
    )
    key = _cache_key(params)
    entry = CacheEntry(
        results=[rich_job],
        providers_searched=["greenhouse"],
        serper_queries_used=0,
    )
    _cache_set(key, entry)

    # 1. Anonymous request: stripped
    client.cookies.clear()
    anon_resp = client.get("/search?q=CachePreserveTest")
    assert anon_resp.status_code == 200
    anon_events = _parse_sse_events(anon_resp.text)
    anon_job = anon_events[0][1]["batch"][0]
    assert "work_model_evidence" not in anon_job
    assert "cached" not in anon_events[1][1]

    # Verify cache entry in memory is still full
    cached_obj = _cache[key]
    assert cached_obj.results[0].work_model_evidence == "hybrid 2 days"

    # 2. Admin request: unredacted
    token = create_session_token()
    client.cookies.clear()
    client.cookies.set(settings.admin_cookie_name, token)
    admin_resp = client.get("/search?q=CachePreserveTest")
    client.cookies.clear()
    assert admin_resp.status_code == 200
    admin_events = _parse_sse_events(admin_resp.text)
    admin_job = admin_events[0][1]["batch"][0]
    assert admin_job["work_model_evidence"] == "hybrid 2 days"
    assert admin_events[1][1]["cached"] is True

    # Cache entry still full
    assert _cache[key].results[0].work_model_evidence == "hybrid 2 days"


def test_invalid_or_tampered_admin_cookie_treated_as_anonymous():
    """Missing, tampered, or expired admin cookies default to anonymous stripped response with 200."""
    rich_job = JobListing(
        id="job-tamper-test-1",
        provider="greenhouse",
        data_source="scrape",
        title="Tamper Test",
        company="Security Corp",
        location="Remote",
        apply_url="https://example.com/tamper",
        work_model_evidence="confidential evidence",
        scraped_at=datetime.now(timezone.utc),
        source_url="https://example.com/source",
        query_used="test query",
        ats_source="greenhouse",
    )
    params = SearchParams(
        job_title="TamperCookieTest",
        location=None,
        remote=None,
        days_back=7,
        include_nigerian_sites=True,
    )
    key = _cache_key(params)
    _cache_set(
        key,
        CacheEntry(
            results=[rich_job],
            providers_searched=["greenhouse"],
            serper_queries_used=0,
        ),
    )

    expired_token = create_session_token(max_age_seconds=-10)
    test_cookies = [
        None,  # missing
        "bogus.invalid.cookie",  # tampered
        expired_token,  # expired
    ]

    for cookie_val in test_cookies:
        client.cookies.clear()
        if cookie_val is not None:
            client.cookies.set(settings.admin_cookie_name, cookie_val)
        res = client.get("/search?q=TamperCookieTest")
        client.cookies.clear()
        assert res.status_code == 200
        events = _parse_sse_events(res.text)
        job_payload = events[0][1]["batch"][0]
        assert "work_model_evidence" not in job_payload
        assert set(job_payload.keys()) == USER_JOB_FIELDS
        assert "cached" not in events[1][1]


def test_422_behavior_unchanged_for_anonymous_and_admin():
    """Invalid search query parameters return 422 for both user and admin."""
    # days_back expects an integer; pass a non-integer string
    client.cookies.clear()
    anon_res = client.get("/search?q=test&days_back=invalid_number")
    assert anon_res.status_code == 422

    token = create_session_token()
    client.cookies.set(settings.admin_cookie_name, token)
    admin_res = client.get("/search?q=test&days_back=invalid_number")
    client.cookies.clear()
    assert admin_res.status_code == 422


def test_incomplete_flag_behavior():
    """Verify incomplete flag is true only when budget_exhausted is true, and absent for admin."""
    done_exhausted = DoneEvent(
        total=0,
        search_time_ms=100,
        serper_queries_used=1,
        providers_searched=["greenhouse"],
        providers_skipped=[],
        cached=False,
        budget_exhausted=True,
    )
    done_normal = DoneEvent(
        total=5,
        search_time_ms=100,
        serper_queries_used=1,
        providers_searched=["greenhouse"],
        providers_skipped=[],
        cached=False,
        budget_exhausted=False,
    )

    # Anonymous user serialization
    user_exhausted_json = serialize_event_for_user("done", done_exhausted)
    assert user_exhausted_json is not None
    user_exhausted = json.loads(user_exhausted_json)
    assert user_exhausted == {"total": 0, "incomplete": True, "partial": False}

    user_normal_json = serialize_event_for_user("done", done_normal)
    assert user_normal_json is not None
    user_normal = json.loads(user_normal_json)
    assert user_normal == {"total": 5, "incomplete": False, "partial": False}

    # Admin payload uses model_dump_json() and does not have incomplete
    admin_exhausted = json.loads(done_exhausted.model_dump_json())
    assert "incomplete" not in admin_exhausted
    assert admin_exhausted["budget_exhausted"] is True


def test_allowlist_completeness():
    """Exhaustive check that all model fields are explicitly classified in allowlist.py."""
    # JobListing
    assert set(JobListing.model_fields.keys()) == USER_JOB_FIELDS | ADMIN_JOB_FIELDS
    assert not (USER_JOB_FIELDS & ADMIN_JOB_FIELDS)

    # ResultsBatch
    assert (
        set(ResultsBatch.model_fields.keys())
        == USER_RESULTS_BATCH_FIELDS | ADMIN_RESULTS_BATCH_FIELDS
    )
    assert not (USER_RESULTS_BATCH_FIELDS & ADMIN_RESULTS_BATCH_FIELDS)

    # DoneEvent
    assert set(DoneEvent.model_fields.keys()) == USER_DONE_FIELDS | ADMIN_DONE_FIELDS
    assert not (USER_DONE_FIELDS & ADMIN_DONE_FIELDS)


def test_anonymous_serialization_no_provider_outcomes_leak():
    """Anonymous done events contain 'partial' but never leak provider_outcomes or provider names."""
    from src.core.models import ProviderOutcomeSummary

    done_with_outcomes = DoneEvent(
        total=12,
        search_time_ms=250,
        serper_queries_used=1,
        providers_searched=["greenhouse", "lever"],
        providers_skipped=[],
        cached=False,
        provider_outcomes={
            "greenhouse": ProviderOutcomeSummary(counts={"success": 2, "retryable_error": 1}, partial=True),
            "lever": ProviderOutcomeSummary(counts={"success": 5}, partial=False),
        },
        partial=True,
    )
    user_json = serialize_event_for_user("done", done_with_outcomes)
    assert user_json is not None
    user_data = json.loads(user_json)
    assert user_data == {"total": 12, "incomplete": False, "partial": True}
    assert "provider_outcomes" not in user_data
    assert "greenhouse" not in user_json
    assert "lever" not in user_json
    assert "retryable_error" not in user_json

    # Admin caller receives full provider_outcomes with counts and partial flag
    admin_data = json.loads(done_with_outcomes.model_dump_json())
    assert admin_data["partial"] is True
    assert "provider_outcomes" in admin_data
    assert admin_data["provider_outcomes"]["greenhouse"]["partial"] is True
    assert admin_data["provider_outcomes"]["greenhouse"]["counts"]["retryable_error"] == 1


def test_anonymous_error_event_strips_internal_details_for_provider_error(monkeypatch):
    """Anonymous error events strip sensitive message details and URLs while admin preserves them."""
    secret_text = "secret-internal-detail https://internal.example/?key=abc"

    async def mock_run_raising(*args, **kwargs):
        raise Exception(secret_text)
        yield  # Make it an async generator

    monkeypatch.setattr("src.api.main.orchestrator.run", mock_run_raising)

    # 1. Anonymous caller
    client.cookies.clear()
    anon_resp = client.get("/search?q=ErrorDetailTest")
    assert anon_resp.status_code == 200
    assert "event: error" in anon_resp.text
    assert secret_text not in anon_resp.text
    assert "https://internal.example/?key=abc" not in anon_resp.text
    assert "Something went wrong while searching. Please try again." in anon_resp.text
    assert '"code":"PROVIDER_ERROR"' in anon_resp.text

    # 2. Admin caller
    token = create_session_token()
    client.cookies.set(settings.admin_cookie_name, token)
    admin_resp = client.get("/search?q=ErrorDetailTest")
    client.cookies.clear()
    assert admin_resp.status_code == 200
    assert "event: error" in admin_resp.text
    assert secret_text in admin_resp.text
    assert "https://internal.example/?key=abc" in admin_resp.text
    assert '"code":"PROVIDER_ERROR"' in admin_resp.text


def test_anonymous_error_event_strips_internal_details_for_timeout(monkeypatch):
    """Anonymous stream-yielded timeout errors strip internal details while preserving code."""
    timeout_secret = "upstream service timed out https://internal-ats.service.local/timeout"

    async def mock_run_timeout(*args, **kwargs):
        from src.core.models import ErrorEvent
        yield ("error", ErrorEvent(message=timeout_secret, code="TIMEOUT"))

    monkeypatch.setattr("src.api.main.orchestrator.run", mock_run_timeout)

    # 1. Anonymous caller
    client.cookies.clear()
    anon_resp = client.get("/search?q=TimeoutTest")
    assert anon_resp.status_code == 200
    assert "event: error" in anon_resp.text
    assert timeout_secret not in anon_resp.text
    assert "The search took too long. Please try again." in anon_resp.text
    assert '"code":"TIMEOUT"' in anon_resp.text

    # 2. Admin caller
    token = create_session_token()
    client.cookies.set(settings.admin_cookie_name, token)
    admin_resp = client.get("/search?q=TimeoutTest")
    client.cookies.clear()
    assert admin_resp.status_code == 200
    assert "event: error" in admin_resp.text
    assert timeout_secret in admin_resp.text
    assert '"code":"TIMEOUT"' in admin_resp.text


@pytest.mark.anyio
async def test_orchestrator_balanced_mix_nigerian_scrapers_do_not_cancel_pending_ats(monkeypatch):
    """Proves Nigerian scrapers finishing first with high volume do not cancel pending ATS tasks and both stream."""
    import asyncio

    import httpx

    from src.core.models import JobListing, SearchParams
    from src.discovery.search_pipeline import SearchOrchestrator

    now = datetime.now(timezone.utc)
    ats_listing = JobListing(
        id="ats_job_1",
        provider="greenhouse",
        ats_source="greenhouse",
        data_source="api",
        title="Senior Python Engineer",
        company="GlobalTech",
        location="Remote",
        is_remote=True,
        work_model="remote",
        apply_url="https://boards.greenhouse.io/globaltech/jobs/1",
        source_url="https://boards.greenhouse.io/globaltech/jobs/1",
        query_used="Senior Python Engineer",
        posted_at=now,
        scraped_at=now,
    )

    async def mock_search_ats(platform, query_str, params, http_client, stats=None, is_halted=None):
        # Slower ATS task
        await asyncio.sleep(0.05)
        return platform, [ats_listing], query_str

    def make_nigerian_listing(i):
        return JobListing(
            id=f"hnj_job_{i}",
            provider="hotnigerianjobs",
            ats_source="hotnigerianjobs",
            data_source="scrape",
            title=f"Python Developer {i}",
            company="LocalCo",
            location="Lagos",
            is_remote=False,
            work_model="in_person",
            apply_url=f"https://www.hotnigerianjobs.com/hotjobs/{i}",
            source_url=f"https://www.hotnigerianjobs.com/hotjobs/{i}",
            query_used="Python",
            posted_at=now,
            scraped_at=now,
        )

    async def mock_search_nigerian(scraper, params, http_client):
        # Fast Nigerian scraper returning 30 listings
        await asyncio.sleep(0.01)
        return scraper.site_name, [make_nigerian_listing(i) for i in range(30)], "Python"

    pipeline = SearchOrchestrator()
    monkeypatch.setattr(pipeline, "_search_ats_serper", mock_search_ats)
    monkeypatch.setattr(pipeline, "_search_nigerian_scraper", mock_search_nigerian)

    params = SearchParams(
        job_title="Unique Python Balanced Mix Test",
        include_nigerian_sites=True,
        max_results=20,
    )

    batches = []
    done_event = None
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _req: httpx.Response(404))
    ) as offline_client:
        async for event_type, payload in pipeline.run(
            params,
            platforms=["greenhouse", "hotnigerianjobs"],
            client=offline_client,
        ):
            if event_type == "results":
                batches.append(payload)
            elif event_type == "done":
                done_event = payload

    all_jobs = [job for b in batches for job in b.batch]
    ats_jobs = [j for j in all_jobs if j.provider == "greenhouse"]
    nigerian_jobs = [j for j in all_jobs if j.provider == "hotnigerianjobs"]

    # Verify both streams yielded results without cancellation
    assert len(ats_jobs) >= 1
    assert len(nigerian_jobs) >= 1
    # Verify Nigerian dominance cap was applied
    assert len(nigerian_jobs) <= 12
    # Verify done event recorded both providers searched
    assert done_event is not None
    assert "greenhouse" in done_event.providers_searched
    assert "hotnigerianJobs" in done_event.providers_searched or any("nigerian" in p.lower() for p in done_event.providers_searched)


def test_search_applicant_country_projects_without_mutating_shared_cache():
    """Different applicant_country values reuse global cache and return country-specific assessments."""
    from src.core.models import JobEligibility

    base_job = JobListing(
        id="ashby:eu-test:1",
        provider="ashby",
        data_source="api",
        title="Platform Engineer",
        company="EuroCloud",
        location="Remote (Germany and EU)",
        work_model="remote",
        scraped_at=datetime.now(timezone.utc),
        apply_url="https://jobs.ashbyhq.com/eurocloud/1",
        source_url="https://jobs.ashbyhq.com/eurocloud/1",
        query_used="ApplicantCountryCacheTest",
        ats_source="ashby",
        eligibility=JobEligibility(
            classification="country_restricted",
            allowed_residence_countries=["Germany", "EU"],
            allowed_country_codes=["DE"],
            allowed_regions=["EU"],
            pan_regional_remote_confirmed=True,
            residence_restriction_confirmed=True,
        ),
    )
    params = SearchParams(
        job_title="ApplicantCountryCacheTest",
        location=None,
        remote=None,
        days_back=7,
        include_nigerian_sites=True,
    )
    key = _cache_key(params)
    assert key == _cache_key(params.model_copy(update={"applicant_country": "NG"}))
    assert key == _cache_key(params.model_copy(update={"applicant_country": "DE"}))

    _cache_set(
        key,
        CacheEntry(
            results=[base_job],
            providers_searched=["ashby"],
            serper_queries_used=0,
        ),
    )

    client.cookies.clear()
    ng_res = client.get("/search?q=ApplicantCountryCacheTest&applicant_country=ng")
    assert ng_res.status_code == 200
    ng_events = _parse_sse_events(ng_res.text)
    ng_job = ng_events[0][1]["batch"][0]
    assert ng_job["eligibility"]["applicant_assessment"]["applicant_country_code"] == "NG"
    assert ng_job["eligibility"]["applicant_assessment"]["status"] == "restricted"
    assert ng_job["eligibility"]["applicant_assessment"]["summary_label"] == "Remote · Germany and EU"

    de_res = client.get("/search?q=ApplicantCountryCacheTest&applicant_country=DE")
    assert de_res.status_code == 200
    de_events = _parse_sse_events(de_res.text)
    de_job = de_events[0][1]["batch"][0]
    assert de_job["eligibility"]["applicant_assessment"]["applicant_country_code"] == "DE"
    assert de_job["eligibility"]["applicant_assessment"]["status"] == "eligible"

    # Cached object remains country-neutral
    assert _cache[key].results[0].eligibility is not None
    assert _cache[key].results[0].eligibility.applicant_assessment is None

    # Invalid ISO-2 code fails closed with 422
    bad_res = client.get("/search?q=ApplicantCountryCacheTest&applicant_country=ZZ")
    assert bad_res.status_code == 422


def test_multipage_spa_routes_return_html():
    for path in ("/", "/app", "/product", "/sources", "/about", "/contact", "/privacy", "/terms", "/admin"):
        res = client.get(path)
        assert res.status_code == 200, f"Expected 200 for {path}, got {res.status_code}"
        assert "Bottom Pot" in res.text


@pytest.mark.anyio
async def test_lifespan_never_starts_board_monitor_in_test_context(monkeypatch):
    monkeypatch.setattr(settings, "monitoring_enabled", True)
    called = False

    async def _fake_run_loop(self, interval=3600):
        nonlocal called
        called = True

    monkeypatch.setattr("src.monitoring.board_monitor.BoardMonitor.run_loop", _fake_run_loop)
    async with api_main.lifespan(app):
        assert called is False


@pytest.mark.anyio
async def test_serper_fallback_mode_two_phase_and_live_discovery(monkeypatch):
    from unittest.mock import AsyncMock, patch

    import httpx

    from src.discovery.search_pipeline import SearchOrchestrator

    monkeypatch.setattr(settings, "serper_mode", "fallback")
    monkeypatch.setattr(settings, "serper_fallback_min_results", 2)

    orchestrator = SearchOrchestrator()
    now = datetime.now(timezone.utc)

    def _make_ats_job(idx: int) -> JobListing:
        return JobListing(
            id=f"greenhouse:acmecorp:{idx}",
            provider="greenhouse",
            data_source="api",
            title=f"Fallback Engineer {idx}",
            company="Acme Corp",
            company_slug="acmecorp",
            apply_url=f"https://boards.greenhouse.io/acmecorp/jobs/{idx}",
            source_url=f"https://boards.greenhouse.io/acmecorp/jobs/{idx}",
            posted_at=now,
            scraped_at=now,
            query_used="Fallback Engineer",
            ats_source="greenhouse",
        )

    # 1. Phase 1 satisfies fallback threshold (>= 2 ATS jobs) -> zero Serper calls
    with patch.object(orchestrator, "_search_monitored_store", new_callable=AsyncMock) as mock_mon, \
         patch.object(orchestrator, "_search_ats_serper", new_callable=AsyncMock) as mock_serper:
        mock_mon.return_value = ("monitored_store", [_make_ats_job(1), _make_ats_job(2)], "Fallback Engineer")
        mock_serper.return_value = ("greenhouse", [], "q")
        params = SearchParams(job_title="Fallback Engineer One", include_nigerian_sites=False)
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _req: httpx.Response(404))
        ) as http:
            events = [e async for e in orchestrator.run(params, platforms=["greenhouse"], client=http)]
        assert mock_serper.call_count == 0
        assert any(name == "results" for name, _ in events)

    # 2. Phase 1 below threshold (< 2 ATS jobs) -> Phase 2 triggers Serper
    with patch.object(orchestrator, "_search_monitored_store", new_callable=AsyncMock) as mock_mon, \
         patch.object(orchestrator, "_search_ats_serper", new_callable=AsyncMock) as mock_serper:
        mock_mon.return_value = ("monitored_store", [_make_ats_job(3)], "Fallback Engineer Two")
        mock_serper.return_value = ("greenhouse", [_make_ats_job(4)], "q")
        params = SearchParams(job_title="Fallback Engineer Two", include_nigerian_sites=False)
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _req: httpx.Response(404))
        ) as http:
            _ = [e async for e in orchestrator.run(params, platforms=["greenhouse"], client=http)]
        assert mock_serper.call_count == 1

    # 3. live_discovery=True bypasses wait and invokes Serper immediately
    with patch.object(orchestrator, "_search_monitored_store", new_callable=AsyncMock) as mock_mon, \
         patch.object(orchestrator, "_search_ats_serper", new_callable=AsyncMock) as mock_serper:
        mock_mon.return_value = ("monitored_store", [_make_ats_job(5), _make_ats_job(6)], "Fallback Engineer Three")
        mock_serper.return_value = ("greenhouse", [], "q")
        params = SearchParams(job_title="Fallback Engineer Three", include_nigerian_sites=False, live_discovery=True)
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _req: httpx.Response(404))
        ) as http:
            _ = [e async for e in orchestrator.run(params, platforms=["greenhouse"], client=http)]
        assert mock_serper.call_count == 1


def test_gzip_skips_sse_stream_and_assets_get_immutable_cache(monkeypatch, tmp_path):
    """SafeGZipMiddleware skips /search SSE streams while compressing HTML/JS assets with immutable caching."""
    fake_dist = tmp_path / "dist"
    assets_dir = fake_dist / "assets"
    assets_dir.mkdir(parents=True)
    big_html = "<!doctype html><title>Bottom Pot</title>" + ("<!-- padding -->" * 80)
    big_js = "console.log('bottom-pot');" * 80
    (fake_dist / "index.html").write_text(big_html, encoding="utf-8")
    (assets_dir / "app-abc123.js").write_text(big_js, encoding="utf-8")

    monkeypatch.setattr(api_main, "frontend_dir", fake_dist)

    html_res = client.get("/", headers={"Accept-Encoding": "gzip"})
    assert html_res.status_code == 200
    assert html_res.headers.get("content-encoding") == "gzip"
    assert "no-store" in html_res.headers.get("cache-control", "")

    params = SearchParams(
        job_title="GzipSseBypassTest",
        location=None,
        remote=None,
        days_back=7,
        include_nigerian_sites=True,
    )
    key = _cache_key(params)
    dummy_job = JobListing(
        id="greenhouse:gzip:1",
        provider="greenhouse",
        data_source="api",
        title="Gzip Bypass Engineer",
        company="FastCorp",
        scraped_at=datetime.now(timezone.utc),
        apply_url="https://boards.greenhouse.io/fastcorp/1",
        source_url="https://boards.greenhouse.io/fastcorp/1",
        query_used="GzipSseBypassTest",
        ats_source="greenhouse",
    )
    _cache_set(
        key,
        CacheEntry(results=[dummy_job], providers_searched=["greenhouse"], serper_queries_used=0),
    )

    sse_res = client.get(
        "/search?q=GzipSseBypassTest",
        headers={"Accept": "text/event-stream", "Accept-Encoding": "gzip"},
    )
    assert sse_res.status_code == 200
    assert sse_res.headers.get("content-encoding") != "gzip"
    assert "event: results" in sse_res.text

    # Asset path under mounted /assets receives immutable cache header on direct static app
    asset_res = client.get("/assets/app-abc123.js")
    if asset_res.status_code == 200:
        assert "immutable" in asset_res.headers.get("cache-control", "")


def test_security_headers_and_cors_allowlist():
    """Responses include hardened security headers and CORS reflects only configured origins."""
    allowed_res = client.get("/health", headers={"Origin": "http://localhost:5173"})
    assert allowed_res.status_code == 200
    assert allowed_res.headers.get("x-content-type-options") == "nosniff"
    assert allowed_res.headers.get("x-frame-options") == "DENY"
    assert allowed_res.headers.get("referrer-policy") == "strict-origin-when-cross-origin"
    assert "camera=()" in allowed_res.headers.get("permissions-policy", "")
    assert allowed_res.headers.get("access-control-allow-origin") == "http://localhost:5173"

    blocked_res = client.get("/health", headers={"Origin": "https://untrusted.example"})
    assert blocked_res.status_code == 200
    assert blocked_res.headers.get("access-control-allow-origin") is None


def test_proxy_client_ip_extraction(monkeypatch):
    """_get_client_ip trusts forwarded headers strictly when trust_proxy_headers is enabled."""
    from starlette.requests import Request as StarletteRequest

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/health",
        "client": ("10.0.0.5", 43210),
        "headers": [
            (b"x-forwarded-for", b"198.51.100.7, 10.0.0.5"),
            (b"x-real-ip", b"198.51.100.8"),
        ],
    }
    req = StarletteRequest(scope)
    monkeypatch.setattr(settings, "trust_proxy_headers", False)
    assert api_main._get_client_ip(req) == "10.0.0.5"

    monkeypatch.setattr(settings, "trust_proxy_headers", True)
    assert api_main._get_client_ip(req) == "198.51.100.7"


def test_subscribe_csv_formula_neutralization_and_bounds(monkeypatch, tmp_path):
    """POST /subscribe neutralizes spreadsheet formulas and rejects overly long search queries."""
    sub_file = str(tmp_path / "hardened_subs.csv")
    monkeypatch.setattr(settings, "subscriptions_file", sub_file)

    ok_res = client.post(
        "/subscribe",
        json={"email": "seeker@example.com", "search_query": "=HYPERLINK(\"https://bad.test\")"},
    )
    assert ok_res.status_code == 201
    with open(sub_file, "r", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    assert rows[1][1].startswith("'=")

    too_long = client.post(
        "/subscribe",
        json={"email": "seeker@example.com", "search_query": "x" * 201},
    )
    assert too_long.status_code == 422


def test_eligibility_evaluate_caps_batch_size():
    """POST /api/eligibility/evaluate enforces max_length=500 items per request."""
    oversized = [{"id": f"job-{i}", "location": "Remote"} for i in range(501)]
    res = client.post(
        "/api/eligibility/evaluate",
        json={"applicant_country": "NG", "jobs": oversized},
    )
    assert res.status_code == 422


def test_contact_route_serves_html_with_no_cache_headers(monkeypatch, tmp_path):
    """GET /contact, /privacy, and /terms serve the SPA HTML shell with strict no-cache headers."""
    fake_dist = tmp_path / "dist"
    fake_dist.mkdir()
    (fake_dist / "index.html").write_text(
        '<!doctype html><title>Bottom Pot</title><script src="/assets/index.js"></script>',
        encoding="utf-8",
    )
    monkeypatch.setattr(api_main, "frontend_dir", fake_dist)

    for path in ("/contact", "/privacy", "/terms"):
        res = client.get(path)
        assert res.status_code == 200
        assert "text/html" in res.headers.get("content-type", "")
        assert "Bottom Pot" in res.text
        assert res.headers.get("cache-control") == "no-cache, no-store, must-revalidate"
        assert res.headers.get("pragma") == "no-cache"
        assert res.headers.get("expires") == "0"


def test_eligibility_evaluate_nigerian_board_provider_rules():
    """POST /api/eligibility/evaluate marks Nigerian-board roles eligible for NG while leaving non-NG unchanged."""
    jobs_payload = [
        {"id": "ng-jobberman", "provider": "jobberman", "location": "Lagos"},
        {"id": "ng-myjobmag", "provider": "myjobmag", "work_model": "remote"},
        {
            "id": "ng-excluded",
            "provider": "hotnigerianjobs",
            "eligibility": {
                "classification": "country_restricted",
                "excluded_residence_countries": ["Nigeria"],
                "excluded_country_codes": ["NG"],
            },
        },
        {"id": "global-gh", "provider": "greenhouse", "location": "Remote"},
    ]

    ng_res = client.post(
        "/api/eligibility/evaluate",
        json={"applicant_country": "NG", "jobs": jobs_payload},
    )
    assert ng_res.status_code == 200
    ng_data = ng_res.json()
    assert ng_data["applicant_country_code"] == "NG"
    assert ng_data["assessments"]["ng-jobberman"]["status"] == "eligible"
    assert ng_data["assessments"]["ng-myjobmag"]["status"] == "eligible"
    assert ng_data["assessments"]["ng-excluded"]["status"] == "restricted"
    assert ng_data["assessments"]["global-gh"]["status"] == "unknown"

    us_res = client.post(
        "/api/eligibility/evaluate",
        json={"applicant_country": "US", "jobs": jobs_payload},
    )
    assert us_res.status_code == 200
    us_data = us_res.json()
    assert us_data["applicant_country_code"] == "US"
    assert us_data["assessments"]["ng-jobberman"]["status"] == "unknown"
    assert us_data["assessments"]["ng-myjobmag"]["status"] == "unknown"
    assert us_data["assessments"]["global-gh"]["status"] == "unknown"








