"""Managed SQLite connections with deterministic close on context exit."""

from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
import sqlite3
from typing import Iterator, Literal

from src.safety.db_safety import assert_safe_sqlite_db_path

SqliteOperation = Literal["connect", "migrate", "checkpoint", "cleanup", "startup"]


@contextmanager
def managed_sqlite_connection(
    db_path: str | os.PathLike[str],
    *,
    operation: SqliteOperation = "connect",
    timeout: float = 10.0,
) -> Iterator[sqlite3.Connection]:
    """
    Validate ``db_path``, yield a transaction-scoped connection, and always close it.

    Python's ``with sqlite3.Connection:`` commits or rolls back transactions on exit
    but does not close the underlying handle; closing deterministically in ``finally``
    prevents lingering WAL connections from checkpointing asynchronously during GC.
    """
    safe_path = assert_safe_sqlite_db_path(db_path, operation=operation)
    if safe_path != ":memory:":
        parent = Path(safe_path).parent
        if parent and not parent.exists():
            parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(safe_path, timeout=timeout)
    try:
        if safe_path != ":memory:":
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
        with conn:
            yield conn
    finally:
        conn.close()
