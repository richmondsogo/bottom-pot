import os
import socket
from typing import Any

import pytest

_REAL_GETADDRINFO = socket.getaddrinfo


class OfflineDnsBlockedError(RuntimeError):
    """Raised when an offline test attempts real DNS resolution via ``socket.getaddrinfo``."""

os.environ.setdefault("SERPER_API_KEY", "test-serper-key")
os.environ.setdefault("ADMIN_PASSWORD", "test-admin-password")
os.environ.setdefault(
    "ADMIN_SESSION_SECRET",
    "test-admin-session-secret-at-least-32-chars-long",
)
os.environ["BOTTOM_POT_TEST_MODE"] = "1"

from src.safety.db_safety import OwnedDisposableWorkspace  # noqa: E402

# Preserve any inherited external BOTTOM_POT_DATA_DIR as read-only protected so tests cannot touch it
_inherited_data_dir = os.environ.pop("BOTTOM_POT_DATA_DIR", "").strip()
if _inherited_data_dir:
    _existing_protected = os.environ.get("BOTTOM_POT_PROTECTED_DATA_DIRS", "").strip()
    os.environ["BOTTOM_POT_PROTECTED_DATA_DIRS"] = (
        f"{_existing_protected}{os.pathsep}{_inherited_data_dir}"
        if _existing_protected
        else _inherited_data_dir
    )
# Clear env BOTTOM_POT_DATA_DIR so .env cannot override test isolation
os.environ["BOTTOM_POT_DATA_DIR"] = ""

# Test database & subscriptions isolation: force every pytest run into an owned temporary directory
_test_workspace = OwnedDisposableWorkspace.create(prefix="bottom-pot-pytest-")
_test_db_path = str(_test_workspace.db_path)
_test_subs_path = str(_test_workspace.subscriptions_file)
_test_data_dir = str(_test_workspace.root)
os.environ["SQLITE_DB_PATH"] = _test_db_path
os.environ["SUBSCRIPTIONS_FILE"] = _test_subs_path

from src.core.settings import settings  # noqa: E402

settings.bottom_pot_data_dir = _test_data_dir
settings.sqlite_db_path = _test_db_path
settings.subscriptions_file = _test_subs_path

from src.api.main import limiter  # noqa: E402
from src.core.http_resilience import resilience_manager  # noqa: E402
from src.discovery.search_pipeline import _cache  # noqa: E402
from src.storage.cache_store import cache_store  # noqa: E402
from src.storage.company_board_registry import company_board_registry  # noqa: E402

cache_store.db_path = _test_db_path
cache_store._ensure_db()
company_board_registry.db_path = _test_db_path
company_board_registry._ensure_db()


@pytest.fixture(autouse=True)
def block_real_dns_in_offline_tests(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
):
    if request.node.get_closest_marker("live") is not None:
        yield
        return

    blocked_calls: list[tuple[Any, Any]] = []
    request.node._offline_dns_blocked_calls = blocked_calls
    request.node._expect_offline_dns_tripwire = False

    def _tripwire_getaddrinfo(host: Any, port: Any, *args: Any, **kwargs: Any):
        blocked_calls.append((host, port))
        raise OfflineDnsBlockedError(
            f"Real DNS lookup blocked in offline test '{request.node.nodeid}' "
            f"for host={host!r}, port={port!r}. Inject an explicit resolver via "
            "url_safety.use_dns_resolver(StaticDnsResolver(...)), pass MockTransport, "
            "or mark the test @pytest.mark.live."
        )

    monkeypatch.setattr(socket, "getaddrinfo", _tripwire_getaddrinfo)
    yield
    if blocked_calls and not getattr(request.node, "_expect_offline_dns_tripwire", False):
        pytest.fail(
            f"Offline test {request.node.nodeid!r} attempted real DNS via "
            f"socket.getaddrinfo: {blocked_calls}"
        )


@pytest.fixture
def expect_dns_tripwire(request: pytest.FixtureRequest) -> list[tuple[Any, Any]]:
    """Opt in for unit tests asserting that real DNS hits the offline tripwire."""
    request.node._expect_offline_dns_tripwire = True
    return getattr(request.node, "_offline_dns_blocked_calls", [])


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_sqlite_dir():
    yield
    try:
        _test_workspace.cleanup()
    except Exception:
        pass


@pytest.fixture(autouse=True)
def clean_cache_and_resilience():
    settings.bottom_pot_data_dir = _test_data_dir
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
    settings.bottom_pot_data_dir = _test_data_dir
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
