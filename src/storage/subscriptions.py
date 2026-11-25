"""Email subscription persistence (PostgreSQL in cloud, CSV in local/test runs)."""

from __future__ import annotations

import csv
import os
import threading
from datetime import datetime, timezone

from src.core.settings import settings
from src.safety.db_safety import assert_safe_subscriptions_path
from src.storage.db_conn import managed_postgres_connection, resolve_database_url

_SUBSCRIBE_LOCK = threading.Lock()
_CSV_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def sanitize_csv_cell(value: str) -> str:
    """Neutralize leading spreadsheet formula characters before writing CSV fields."""
    if value and value.startswith(_CSV_FORMULA_PREFIXES):
        return f"'{value}"
    return value


def ensure_subscriptions_table(conn) -> None:
    """Create the PostgreSQL ``subscriptions`` table if it does not yet exist."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS subscriptions (
            id SERIAL PRIMARY KEY,
            email TEXT NOT NULL,
            search_query TEXT NOT NULL DEFAULT '',
            subscribed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_subscriptions_subscribed_at ON subscriptions(subscribed_at DESC)"
    )


def save_subscription(
    email: str,
    search_query: str = "",
    *,
    database_url: str | None = None,
    subscriptions_file: str | None = None,
) -> str:
    """
    Persist a subscription entry and return the backend used (``'postgres'`` or ``'csv'``).

    When ``subscriptions_file`` is explicitly supplied, writes CSV to honor file overrides.
    Otherwise uses Neon/PostgreSQL when ``resolve_database_url()`` is active.
    """
    safe_query = (search_query or "").strip()
    if subscriptions_file is None:
        pg_url = resolve_database_url(database_url)
        if pg_url:
            subscribed_at = datetime.now(timezone.utc)
            with managed_postgres_connection(pg_url) as conn:
                ensure_subscriptions_table(conn)
                conn.execute(
                    """
                    INSERT INTO subscriptions (email, search_query, subscribed_at)
                    VALUES (?, ?, ?)
                    """,
                    (str(email).strip(), safe_query, subscribed_at),
                )
            return "postgres"

    target_file = subscriptions_file or settings.subscriptions_file
    safe_subs_path = assert_safe_subscriptions_path(target_file)
    csv_email = sanitize_csv_cell(str(email))
    csv_query = sanitize_csv_cell(safe_query)
    subscribed_at_iso = datetime.now(timezone.utc).isoformat()
    with _SUBSCRIBE_LOCK:
        parent = os.path.dirname(safe_subs_path)
        if parent and not os.path.exists(parent):
            os.makedirs(parent, exist_ok=True)
        file_exists = os.path.isfile(safe_subs_path)
        with open(safe_subs_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["email", "search_query", "subscribed_at"])
            writer.writerow([csv_email, csv_query, subscribed_at_iso])
    return "csv"
