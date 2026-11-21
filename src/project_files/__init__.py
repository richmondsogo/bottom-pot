"""Bottom Pot core job discovery and extraction modules."""

from __future__ import annotations

from typing import Any

__all__ = ["SearchParams", "RawSearchResults", "ATS_PLATFORMS", "QueryBuilder"]


def __getattr__(name: str) -> Any:
    if name == "ATS_PLATFORMS":
        from src.config import ATS_PLATFORMS

        return ATS_PLATFORMS
    if name in ("SearchParams", "RawSearchResults"):
        from src.project_files import models

        return getattr(models, name)
    if name == "QueryBuilder":
        from src.project_files.query_builder import QueryBuilder

        return QueryBuilder
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
