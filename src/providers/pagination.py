"""
Shared snapshot pagination completeness helpers for monitored ATS providers.

Provides:
- ``validate_offset_page`` for strict offset/limit/totalCount atomic JSON page checks.
- ``HtmlPaginationTracker`` for bounded HTML fallback loop, duplicate, and cap detection.
"""

from __future__ import annotations

from typing import Any, Callable


def validate_offset_page(
    data: object,
    *,
    requested_offset: int,
    expected_total: int | None,
    collected_count: int,
    max_limit: int = 100,
    list_key: str = "content",
    total_key: str = "totalFound",
    offset_key: str = "offset",
    limit_key: str = "limit",
    provider_label: str = "Provider",
    item_validator: Callable[[object], str | None] | None = None,
) -> tuple[list[dict] | None, int | None, int | None, str | None]:
    """
    Validate one sequential offset-paginated snapshot page atomically.

    Returns ``(validated_items, page_limit, total_found, error)``.
    """
    if not isinstance(data, dict):
        return None, None, None, f"Invalid {provider_label} listing payload (expected JSON object)"

    resp_offset = data.get(offset_key)
    if isinstance(resp_offset, bool) or not isinstance(resp_offset, int) or resp_offset != requested_offset:
        return None, None, None, (
            f"{provider_label} offset mismatch: requested {requested_offset}, got {resp_offset!r}"
        )

    resp_limit = data.get(limit_key)
    if (
        isinstance(resp_limit, bool)
        or not isinstance(resp_limit, int)
        or resp_limit < 1
        or resp_limit > max_limit
    ):
        return None, None, None, f"Invalid {provider_label} page limit: {resp_limit!r}"

    total_found = data.get(total_key)
    if isinstance(total_found, bool) or not isinstance(total_found, int) or total_found < 0:
        return None, None, None, f"Invalid {provider_label} {total_key}: {total_found!r}"

    if expected_total is not None and total_found != expected_total:
        return None, None, None, (
            f"{provider_label} {total_key} drifted mid-pagination: {expected_total} -> {total_found}"
        )

    items = data.get(list_key)
    if not isinstance(items, list):
        return None, None, None, f"Invalid {provider_label} {list_key} shape (expected list)"

    if len(items) > resp_limit:
        return None, None, None, (
            f"{provider_label} page exceeded limit {resp_limit}: got {len(items)}"
        )

    if total_found == 0:
        if requested_offset != 0 or len(items) != 0:
            return None, None, None, f"Inconsistent {provider_label} empty snapshot"
        return [], resp_limit, 0, None

    if len(items) == 0:
        return None, None, None, (
            f"Premature empty {provider_label} page at offset {requested_offset} ({total_key}={total_found})"
        )

    if collected_count + len(items) > total_found:
        return None, None, None, (
            f"{provider_label} item count exceeded {total_key} ({collected_count + len(items)} > {total_found})"
        )

    if collected_count + len(items) < total_found and len(items) < resp_limit:
        return None, None, None, (
            f"Incomplete {provider_label} page at offset {requested_offset}: "
            f"got {len(items)} < limit {resp_limit} before {total_key} {total_found}"
        )

    validated_items: list[dict] = []
    for entry in items:
        if item_validator is not None:
            entry_err = item_validator(entry)
            if entry_err:
                return None, None, None, entry_err
        validated_items.append(entry)  # type: ignore[arg-type]

    return validated_items, resp_limit, total_found, None


class HtmlPaginationTracker:
    """
    Bounded multi-page HTML pagination state tracker preventing loops, duplicate pages,
    and silently truncated snapshots.
    """

    def __init__(self, *, max_pages: int, max_items: int, provider_label: str = "HTML") -> None:
        self.max_pages = max(1, int(max_pages))
        self.max_items = max(1, int(max_items))
        self.provider_label = provider_label
        self.collected: list[dict[str, Any]] = []
        self.seen_ids: set[str] = set()
        self.prev_page_ids: set[str] | None = None
        self.visited_pages: set[int] = set()

    def can_visit(self, page: int) -> tuple[bool, str | None]:
        if len(self.visited_pages) >= self.max_pages:
            return False, f"{self.provider_label} fallback hit max_pages cap ({self.max_pages})"
        if page in self.visited_pages:
            return False, f"{self.provider_label} pagination loop detected at page={page}"
        self.visited_pages.add(page)
        return True, None

    def record_page(
        self,
        page: int,
        page_items: list[dict[str, Any]],
        next_page: int | None,
        *,
        id_key: str = "job_id",
    ) -> tuple[bool, bool, str | None]:
        """
        Validate and accumulate *page_items*.

        Returns ``(done, complete, error)``:
        - ``(True, True, None)`` when pagination terminated cleanly and completely.
        - ``(True, False, reason)`` when a loop, empty page 1, repeated page, or cap occurred.
        - ``(False, True, None)`` when safe to fetch *next_page*.
        """
        if page == 1 and not page_items:
            return True, False, f"{self.provider_label} fallback returned 0 jobs on page 1"

        if not page_items:
            return True, True, None

        page_ids = {str(it[id_key]) for it in page_items}
        if self.prev_page_ids is not None and page_ids == self.prev_page_ids:
            return True, False, f"{self.provider_label} repeated page detected at page={page}"
        if page_ids.issubset(self.seen_ids):
            return True, False, f"{self.provider_label} duplicate-only page detected at page={page}"

        self.prev_page_ids = page_ids
        for it in page_items:
            jid = str(it[id_key])
            if jid in self.seen_ids:
                continue
            self.seen_ids.add(jid)
            self.collected.append(it)
            if len(self.collected) >= self.max_items:
                return (
                    True,
                    False,
                    f"{self.provider_label} fallback hit max_items cap ({self.max_items})",
                )

        if next_page is None:
            return True, True, None
        if next_page <= page or next_page in self.visited_pages:
            return (
                True,
                False,
                f"{self.provider_label} pagination loop: page {page} -> {next_page}",
            )
        return False, True, None
