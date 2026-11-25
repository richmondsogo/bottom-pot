"""Dual-backend connection helpers for SQLite (local/tests) and Neon PostgreSQL."""

from __future__ import annotations

import atexit
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from typing import Any, Iterator

from src.core.exceptions import SafetyError
from src.core.settings import settings
from src.safety.db_safety import is_test_or_disposable_context

try:
    import psycopg2
    import psycopg2.extras
    from psycopg2.pool import ThreadedConnectionPool

    PG_AVAILABLE = True
    _PG_ERROR_TYPES: tuple[type[BaseException], ...] = (psycopg2.Error,)
except ImportError:  # pragma: no cover - psycopg2-binary expected in prod/dev
    psycopg2 = None  # type: ignore[assignment]
    ThreadedConnectionPool = None  # type: ignore[assignment, misc]
    PG_AVAILABLE = False
    _PG_ERROR_TYPES = ()

DB_ERRORS: tuple[type[BaseException], ...] = (
    sqlite3.Error,
    *_PG_ERROR_TYPES,
    OSError,
    ValueError,
    TypeError,
)

_PG_POOLS_LOCK = threading.RLock()
_PG_POOLS: dict[str, Any] = {}
_PG_LAST_OK: dict[int, float] = {}
_PG_HEALTHCHECK_INTERVAL_S = 30.0


def _is_pg_dsn(value: str | None) -> bool:
    if not isinstance(value, str):
        return False
    lowered = value.strip().lower()
    return lowered.startswith("postgres://") or lowered.startswith("postgresql://")


def resolve_database_url(explicit_url: str | None = None) -> str | None:
    """
    Resolve an active PostgreSQL DSN or return ``None`` to use local SQLite.

    Fail-closed inside automated test/CI contexts unless either an explicit URL
    was supplied directly or ``BOTTOM_POT_ALLOW_TEST_POSTGRES=1`` is set.
    """
    if isinstance(explicit_url, str) and explicit_url.strip():
        return explicit_url.strip() if _is_pg_dsn(explicit_url) else None

    if is_test_or_disposable_context():
        allow_test_pg = os.environ.get("BOTTOM_POT_ALLOW_TEST_POSTGRES", "").strip().lower()
        if allow_test_pg not in {"1", "true", "yes"}:
            return None

    for candidate in (
        settings.database_url,
        os.environ.get("DATABASE_URL", ""),
        os.environ.get("POSTGRES_URL", ""),
    ):
        if _is_pg_dsn(candidate):
            return candidate.strip()
    return None


def is_postgres_enabled(explicit_url: str | None = None) -> bool:
    """Return True when runtime persistence targets PostgreSQL instead of SQLite."""
    return resolve_database_url(explicit_url) is not None


def qmark_to_pyformat(sql: str, *, has_params: bool = True) -> str:
    """
    Translate SQLite ``?`` placeholders into psycopg2 ``%s`` placeholders.

    Respects single-quoted SQL literals (including ``''`` escapes) and doubles literal
    ``%`` characters whenever ``has_params`` is True so ``LIKE '%remote%'`` filters do
    not confuse ``psycopg2`` parameter interpolation.
    """
    out: list[str] = []
    in_quote = False
    i = 0
    n = len(sql)
    while i < n:
        ch = sql[i]
        if ch == "'":
            out.append(ch)
            if in_quote and i + 1 < n and sql[i + 1] == "'":
                out.append("'")
                i += 2
                continue
            in_quote = not in_quote
            i += 1
            continue
        if ch == "?" and not in_quote:
            out.append("%s")
        elif ch == "%" and has_params:
            out.append("%%")
        else:
            out.append(ch)
        i += 1
    return "".join(out)


class PostgresConnectionWrapper:
    """SQLite-compatible thin adapter over a psycopg2 connection."""

    is_postgres: bool = True

    def __init__(self, raw_conn: Any) -> None:
        self._conn = raw_conn
        self._cursors: list[Any] = []

    def execute(self, sql: str, params: tuple[Any, ...] | list[Any] | None = None) -> Any:
        param_tuple = tuple(params) if params else None
        pg_sql = qmark_to_pyformat(sql, has_params=bool(param_tuple))
        cur = self._conn.cursor()
        self._cursors.append(cur)
        if param_tuple:
            cur.execute(pg_sql, param_tuple)
        else:
            cur.execute(pg_sql)
        return cur

    def execute_values(
        self,
        sql: str,
        rows: list[tuple[Any, ...]],
        *,
        page_size: int = 200,
    ) -> None:
        if not rows:
            return
        if not PG_AVAILABLE or psycopg2 is None:
            raise RuntimeError("psycopg2-binary is required for PostgreSQL connections")
        cur = self._conn.cursor()
        self._cursors.append(cur)
        psycopg2.extras.execute_values(cur, sql, rows, page_size=page_size)

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()

    def close_cursors(self) -> None:
        for cur in self._cursors:
            try:
                cur.close()
            except DB_ERRORS:
                pass
        self._cursors.clear()


def _get_or_create_pool(db_url: str) -> Any:
    if not PG_AVAILABLE or ThreadedConnectionPool is None:
        raise RuntimeError(
            "DATABASE_URL is configured for PostgreSQL, but psycopg2-binary is not installed."
        )
    with _PG_POOLS_LOCK:
        pool = _PG_POOLS.get(db_url)
        if pool is None or getattr(pool, "closed", False):
            pool = ThreadedConnectionPool(
                minconn=1,
                maxconn=10,
                dsn=db_url,
                connect_timeout=10,
            )
            _PG_POOLS[db_url] = pool
        return pool


def _acquire_healthy_pg_conn(pool: Any) -> Any:
    """Borrow a live connection from the pool, validating stale/idle handles periodically."""
    now = time.monotonic()
    for attempt in range(2):
        conn = pool.getconn()
        if getattr(conn, "closed", 0) == 0:
            last_ok = _PG_LAST_OK.get(id(conn), 0.0)
            if (now - last_ok) < _PG_HEALTHCHECK_INTERVAL_S:
                return conn
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                conn.rollback()
                _PG_LAST_OK[id(conn)] = now
                return conn
            except DB_ERRORS:
                pass
        _PG_LAST_OK.pop(id(conn), None)
        try:
            pool.putconn(conn, close=True)
        except DB_ERRORS:
            pass
        if attempt == 1:
            break
    conn = pool.getconn()
    _PG_LAST_OK.pop(id(conn), None)
    return conn


@contextmanager
def managed_postgres_connection(db_url: str) -> Iterator[PostgresConnectionWrapper]:
    """
    Borrow a pooled psycopg2 connection wrapped for uniform ``execute`` usage.

    Commits cleanly on block exit, rolls back on errors, and discards broken sockets
    so Neon scale-to-zero reconnects remain transparent.
    """
    pool = _get_or_create_pool(db_url)
    raw_conn = _acquire_healthy_pg_conn(pool)
    wrapper = PostgresConnectionWrapper(raw_conn)
    committed = False
    broken = False
    try:
        yield wrapper
        if getattr(raw_conn, "closed", 0) == 0:
            raw_conn.commit()
        committed = True
    except SafetyError:
        raise
    except DB_ERRORS:
        broken = True
        raise
    finally:
        if not committed and getattr(raw_conn, "closed", 0) == 0:
            try:
                raw_conn.rollback()
            except DB_ERRORS:
                broken = True
        wrapper.close_cursors()
        is_closed = broken or getattr(raw_conn, "closed", 0) != 0
        if is_closed:
            _PG_LAST_OK.pop(id(raw_conn), None)
        elif committed:
            _PG_LAST_OK[id(raw_conn)] = time.monotonic()
        try:
            pool.putconn(raw_conn, close=is_closed)
        except DB_ERRORS:
            pass


def close_postgres_pools() -> None:
    """Close all pooled PostgreSQL connections cleanly."""
    with _PG_POOLS_LOCK:
        for pool in _PG_POOLS.values():
            try:
                pool.closeall()
            except DB_ERRORS:
                pass
        _PG_POOLS.clear()


atexit.register(close_postgres_pools)
