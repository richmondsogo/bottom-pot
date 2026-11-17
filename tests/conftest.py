import os

import pytest

os.environ.setdefault("SERPER_API_KEY", "test-serper-key")
os.environ.setdefault("ADMIN_PASSWORD", "test-admin-password")
os.environ.setdefault(
    "ADMIN_SESSION_SECRET",
    "test-admin-session-secret-at-least-32-chars-long",
)
os.environ["BOTTOM_POT_TEST_MODE"] = "1"

from src.project_files.db_safety import OwnedDisposableWorkspace

# Test database & subscriptions isolation: force every pytest run into an owned temporary directory
_test_workspace = OwnedDisposableWorkspace.create(prefix="bottom-pot-pytest-")
_test_db_path = str(_test_workspace.db_path)
_test_subs_path = str(_test_workspace.subscriptions_file)
os.environ["SQLITE_DB_PATH"] = _test_db_path
os.environ["SUBSCRIPTIONS_FILE"] = _test_subs_path

from src.config import settings

settings.sqlite_db_path = _test_db_path
settings.subscriptions_file = _test_subs_path

from src.project_files.cache_store import cache_store
from src.project_files.company_board_registry import company_board_registry
from src.project_files.http_resilience import resilience_manager
from src.project_files.search_pipeline import _cache
from src.api.main import limiter

cache_store.db_path = _test_db_path
cache_store._ensure_db()
company_board_registry.db_path = _test_db_path
company_board_registry._ensure_db()


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_sqlite_dir():
    yield
    try:
        _test_workspace.cleanup()
    except Exception:
        pass


@pytest.fixture(autouse=True)
def clean_cache_and_resilience():
    settings.sqlite_db_path = _test_db_path
    settings.subscriptions_file = _test_subs_path
    cache_store.db_path = _test_db_path
    company_board_registry.db_path = _test_db_path
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
    settings.subscriptions_file = _test_subs_path
    cache_store.db_path = _test_db_path
    company_board_registry.db_path = _test_db_path
    cache_store.clear()
    _cache.clear()
    resilience_manager.reset()
    limiter.reset()
    try:
        from tests.test_api_endpoints import client

        client.cookies.clear()
    except Exception:
        pass
