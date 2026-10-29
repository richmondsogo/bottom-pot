import os
from pathlib import Path
import tempfile

import pytest

os.environ.setdefault("SERPER_API_KEY", "test-serper-key")
os.environ.setdefault("ADMIN_PASSWORD", "test-admin-password")
os.environ.setdefault(
    "ADMIN_SESSION_SECRET",
    "test-admin-session-secret-at-least-32-chars-long",
)

# Test database isolation: redirect all SQLite operations to a temporary directory
_test_db_dir = tempfile.TemporaryDirectory()
_test_db_path = str(Path(_test_db_dir.name) / "test_cache.sqlite")
os.environ["SQLITE_DB_PATH"] = _test_db_path

from src.config import settings

settings.sqlite_db_path = _test_db_path

from src.project_files.cache_store import cache_store
from src.project_files.http_resilience import resilience_manager
from src.project_files.search_pipeline import _cache
from src.api.main import limiter

cache_store.db_path = _test_db_path
cache_store._ensure_db()


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_sqlite_dir():
    yield
    try:
        _test_db_dir.cleanup()
    except Exception:
        pass


@pytest.fixture(autouse=True)
def clean_cache_and_resilience():
    settings.sqlite_db_path = _test_db_path
    cache_store.db_path = _test_db_path
    cache_store.clear()
    _cache.clear()
    resilience_manager.reset()
    limiter.reset()
    try:
        from tests.test_api_endpoints import client

        client.cookies.clear()
    except Exception:
        pass
    yield
    settings.sqlite_db_path = _test_db_path
    cache_store.db_path = _test_db_path
    cache_store.clear()
    _cache.clear()
    resilience_manager.reset()
    limiter.reset()
    try:
        from tests.test_api_endpoints import client

        client.cookies.clear()
    except Exception:
        pass

