"""
Shared canonical SHA-256 content fingerprinting for monitored ATS boards.

Every monitored adapter hashes canonicalized items through ``canonical_content_hash``
and computes board snapshots through ``compute_board_fingerprint`` so:
- Outputs are always full 64-character lowercase hexadecimal SHA-256 digests.
- Dictionary key order, item order, and extraneous whitespace noise never alter digests.
- Any relevant field edit (including deep description text or nested pay/location fields)
  deterministically invalidates the board fingerprint.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from typing import Any, Sequence

_WHITESPACE_RE = re.compile(r"\s+")


def _collapse_ws(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", text.strip())


def canonicalize_value(value: Any) -> Any:
    """Recursively normalize *value* for order- and whitespace-invariant hashing."""
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return _collapse_ws(value)
    if isinstance(value, Mapping):
        return {
            _collapse_ws(str(k)): canonicalize_value(v)
            for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))
        }
    if isinstance(value, (list, tuple)):
        return [canonicalize_value(item) for item in value]
    return _collapse_ws(str(value))


def canonical_content_hash(payload: Any) -> str:
    """Return full 64-hex SHA-256 digest of *payload* after canonical normalization."""
    normalized = canonicalize_value(payload)
    encoded = json.dumps(
        normalized,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def compute_board_fingerprint(
    items: Sequence[tuple[str, str | None] | tuple[str, str | None, str | None]],
) -> str:
    """Compute deterministic 64-hex SHA-256 digest of sorted job identity/timestamp/content tuples."""
    normalized_rows: list[tuple[str, str, str]] = []
    for it in items:
        jid = _collapse_ws(str(it[0]))
        ts = _collapse_ws(str(it[1] or ""))
        ch = _collapse_ws(str(it[2] or "")) if len(it) > 2 else ""
        normalized_rows.append((jid, ts, ch))
    normalized_rows.sort()
    payload = "|".join(f"{jid}:{ts}:{ch}" for jid, ts, ch in normalized_rows)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
