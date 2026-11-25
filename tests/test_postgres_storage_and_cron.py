"""Tests for Step 61 dual SQLite/PostgreSQL helpers, subscriptions persistence, and /api/cron/monitor."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from src.api.main import app
from src.core.models import JobListing
from src.core.settings import settings
from src.storage.cache_store import CacheStore
from src.storage.company_board_registry import CompanyBoardRegistry, MonitoredJobDetailState
from src.storage.db_conn import PostgresConnectionWrapper, qmark_to_pyformat, resolve_database_url
from src.storage.subscriptions import save_subscription

client = TestClient(app)


def test_qmark_to_pyformat_handles_literals_and_like_percents():
    sql = (
        "SELECT id, '?' AS literal_q FROM monitored_jobs "
        "WHERE location ILIKE ? AND location NOT ILIKE '%remote%' AND status = ?"
    )
    translated = qmark_to_pyformat(sql, has_params=True)
    assert translated == (
        "SELECT id, '?' AS literal_q FROM monitored_jobs "
        "WHERE location ILIKE %s AND location NOT ILIKE '%%remote%%' AND status = %s"
    )
    # Without bound params, percentages must remain untouched
    assert qmark_to_pyformat("SELECT '%remote%'", has_params=False) == "SELECT '%remote%'"


def test_resolve_database_url_fails_closed_in_test_context(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@ep.example.neon.tech/neondb?sslmode=require")
    monkeypatch.setattr(settings, "database_url", "postgresql://user:pass@ep.example.neon.tech/neondb?sslmode=require")
    # Test context must ignore global DATABASE_URL unless explicitly opted in
    monkeypatch.delenv("BOTTOM_POT_ALLOW_TEST_POSTGRES", raising=False)
    assert resolve_database_url() is None

    # Explicit DSN argument still works when directly supplied in unit tests
    explicit = "postgresql://user:pass@localhost/testdb"
    assert resolve_database_url(explicit) == explicit
    assert resolve_database_url("sqlite:///tmp/local.db") is None


def test_health_exposes_storage_backend_and_api_search_alias():
    health_res = client.get("/health")
    assert health_res.status_code == 200
    assert health_res.json()["storage_backend"] == "sqlite"

    with patch(
        "src.api.main.orchestrator.run",
        side_effect=lambda *args, **kwargs: _empty_async_gen(),
    ):
        res = client.get("/api/search?q=engineer&platforms=greenhouse")
    assert res.status_code == 200
    assert "text/event-stream" in res.headers.get("content-type", "")


async def _empty_async_gen():
    if False:
        yield ("done", None)


def test_cron_monitor_auth_and_execution(monkeypatch):
    monkeypatch.setattr(settings, "cron_secret", "")
    res_unconfigured = client.get("/api/cron/monitor")
    assert res_unconfigured.status_code == 503

    monkeypatch.setattr(settings, "cron_secret", "super-cron-secret")
    assert client.get("/api/cron/monitor").status_code == 401
    assert client.post("/api/cron/monitor", headers={"Authorization": "Bearer wrong"}).status_code == 401

    mock_registry = MagicMock()
    mock_registry.acquire_lease.return_value = True
    mock_registry.get_monitoring_status.return_value = {
        "active_monitored_jobs": 42,
        "due_boards": 18,
    }
    mock_monitor = MagicMock()
    mock_monitor.registry = mock_registry
    mock_monitor.seed_curated_boards.return_value = [object()] * 28
    mock_monitor.poll_due_boards = AsyncMock(return_value=[object(), object(), object()])

    with patch("src.monitoring.board_monitor.BoardMonitor", return_value=mock_monitor):
        res_get = client.get(
            "/api/cron/monitor?max_boards=10",
            headers={"Authorization": "Bearer super-cron-secret"},
        )
        assert res_get.status_code == 200
        body = res_get.json()
        assert body["ok"] is True
        assert body["seeded_boards"] == 28
        assert body["polled_jobs"] == 3
        assert body["active_monitored_jobs"] == 42
        assert body["due_boards_remaining"] == 18
        mock_registry.release_lease.assert_called_once()

        res_post = client.post(
            "/api/cron/monitor?max_boards=5&seed=false",
            headers={"Authorization": "Bearer super-cron-secret"},
        )
        assert res_post.status_code == 200
        assert res_post.json()["seeded_boards"] == 0

    mock_registry.acquire_lease.return_value = False
    with patch("src.monitoring.board_monitor.BoardMonitor", return_value=mock_monitor):
        res_busy = client.get(
            "/api/cron/monitor",
            headers={"Authorization": "Bearer super-cron-secret"},
        )
        assert res_busy.status_code == 200
        assert res_busy.json()["skipped"] == "lease_busy"


def test_save_subscription_postgres_and_csv(tmp_path):
    executed: list[tuple[str, tuple | None]] = []

    class FakeConn:
        def execute(self, sql: str, params=None):
            executed.append((sql, tuple(params) if params is not None else None))
            return MagicMock()

    @contextmanager
    def fake_pg_conn(_dsn: str):
        yield FakeConn()

    with patch("src.storage.subscriptions.managed_postgres_connection", side_effect=fake_pg_conn):
        backend = save_subscription(
            "tester@example.com",
            "Backend Engineer",
            database_url="postgresql://user:pass@ep.example.neon.tech/neondb?sslmode=require",
        )
    assert backend == "postgres"
    assert any("CREATE TABLE IF NOT EXISTS subscriptions" in stmt for stmt, _ in executed)
    assert any("INSERT INTO subscriptions" in stmt for stmt, _ in executed)

    csv_path = str(tmp_path / "subs.csv")
    csv_backend = save_subscription(
        "csv-user@example.com",
        "=1+1",
        subscriptions_file=csv_path,
    )
    assert csv_backend == "csv"
    text = (tmp_path / "subs.csv").read_text(encoding="utf-8")
    assert "'=1+1" in text


def _sample_job(job_id: str, title: str, url_suffix: str) -> JobListing:
    now = datetime.now(timezone.utc)
    return JobListing(
        id=job_id,
        provider="greenhouse",
        data_source="api",
        ats_source="greenhouse",
        title=title,
        company="Acme",
        company_slug="acme",
        location="Remote",
        work_model="remote",
        is_remote=True,
        apply_url=f"https://boards.greenhouse.io/acme/jobs/{url_suffix}",
        source_url=f"https://boards.greenhouse.io/acme/jobs/{url_suffix}",
        posted_at=now,
        scraped_at=now,
        query_used="acme",
        description="A" * 100,
    )


def test_batch_url_cache_and_monitored_jobs_sqlite_and_pg_mock(tmp_path):
    db_file = str(tmp_path / "batch.sqlite")
    cache = CacheStore(db_path=db_file)
    reg = CompanyBoardRegistry(db_path=db_file)

    v0 = reg.get_monitored_store_version()
    j1_old = _sample_job("greenhouse:acme:1", "Old Title", "1")
    j1_new = _sample_job("greenhouse:acme:1", "Updated Title", "1")
    j2 = _sample_job("greenhouse:acme:2", "Second Role", "2")

    # Batch dedup keeps last occurrence and increments store_version once
    count = reg.upsert_monitored_jobs_batch(
        [j1_old, j1_new, j2],
        detail_states={"greenhouse:acme:1": MonitoredJobDetailState(detail_status="widget_fallback", detail_retry_count=2)},
    )
    assert count == 2
    assert reg.get_monitored_store_version() == v0 + 1
    fetched = reg.get_monitored_job("greenhouse:acme:1")
    assert fetched is not None and fetched.title == "Updated Title"

    # Subsequent batch omitting detail_states preserves existing detail_status & detail_retry_count
    j1_v3 = _sample_job("greenhouse:acme:1", "Third Title", "1")
    assert reg.upsert_monitored_jobs_batch([j1_v3], detail_states=None) == 1
    states = reg.get_monitored_job_detail_states(board_id=0)
    assert isinstance(states, dict)
    with reg._get_connection() as conn:
        row = conn.execute(
            "SELECT title, detail_status, detail_retry_count FROM monitored_jobs WHERE job_id = ?",
            ("greenhouse:acme:1",),
        ).fetchone()
    assert row == ("Third Title", "widget_fallback", 2)

    cache.set_url_cache_batch([(j1_v3.source_url, j1_v3), (j2.source_url, j2)])
    loaded = cache.get_url_cache_batch([j1_v3.source_url, j2.source_url, "https://boards.greenhouse.io/acme/jobs/missing"])
    assert loaded[j1_v3.source_url].title == "Third Title"
    assert loaded[j2.source_url].title == "Second Role"
    assert "https://boards.greenhouse.io/acme/jobs/missing" not in loaded

    # Verify PostgresConnectionWrapper.execute_values passes rows cleanly
    fake_raw = MagicMock()
    wrapper = PostgresConnectionWrapper(fake_raw)
    with patch("src.storage.db_conn.psycopg2.extras.execute_values") as mock_ev:
        wrapper.execute_values("INSERT INTO url_cache (url) VALUES %s", [("https://a.test",)])
        mock_ev.assert_called_once()

