import os

import pytest

os.environ.setdefault("SERPER_API_KEY", "test-serper-key")
os.environ.setdefault("ADMIN_PASSWORD", "test-admin-password")
os.environ.setdefault(
    "ADMIN_SESSION_SECRET",
    "test-admin-session-secret-at-least-32-chars-long",
)

from src.project_files.cache_store import cache_store
from src.project_files.http_resilience import resilience_manager
from src.project_files.search_pipeline import _cache
from src.api.main import limiter


@pytest.fixture(autouse=True)
def clean_cache_and_resilience():
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
    cache_store.clear()
    _cache.clear()
    resilience_manager.reset()
    limiter.reset()
    try:
        from tests.test_api_endpoints import client
        client.cookies.clear()
    except Exception:
        pass

