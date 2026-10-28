"""
Tests for FastAPI application endpoints.
"""

import csv
import json
import os
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from src.api.main import app
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
from src.config import settings
from src.project_files.models import DoneEvent, JobListing, ResultsBatch, SearchParams
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
    assert set(done_payload.keys()) == {"total", "incomplete"}
    assert done_payload["total"] == 1
    assert done_payload["incomplete"] is False
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
    assert user_exhausted == {"total": 0, "incomplete": True}

    user_normal_json = serialize_event_for_user("done", done_normal)
    assert user_normal_json is not None
    user_normal = json.loads(user_normal_json)
    assert user_normal == {"total": 5, "incomplete": False}

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
        from src.project_files.models import ErrorEvent
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



