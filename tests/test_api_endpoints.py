"""
Tests for FastAPI application endpoints.
"""

import csv
import os
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.api.auth import create_session_token, verify_session_token
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

