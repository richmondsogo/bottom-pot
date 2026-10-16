import pytest

from src.project_files.cache_store import cache_store
from src.project_files.http_resilience import resilience_manager
from src.project_files.search_pipeline import _cache


@pytest.fixture(autouse=True)
def clean_cache_and_resilience():
    cache_store.clear()
    _cache.clear()
    resilience_manager.reset()
    yield
    cache_store.clear()
    _cache.clear()
    resilience_manager.reset()
