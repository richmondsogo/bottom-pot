"""
Deterministic injectable UTC clock utilities.

Production defaults to the system wall clock (``time.time()``). Tests may bind
an isolated deterministic clock via ``use_clock(...)`` without monkeypatching
``datetime`` or ``time`` globals.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Callable, Iterator

Clock = Callable[[], datetime]

_active_clock: ContextVar[Clock | None] = ContextVar("bottom_pot_active_clock", default=None)


def utc_now() -> datetime:
    """Return the current UTC datetime from the active clock or system clock."""
    clock = _active_clock.get()
    if clock is None:
        return datetime.fromtimestamp(time.time(), tz=timezone.utc)
    dt = clock()
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def epoch_now() -> float:
    """Return the current UTC Unix timestamp in seconds from ``utc_now()``."""
    clock = _active_clock.get()
    if clock is None:
        return float(time.time())
    return utc_now().timestamp()


@contextmanager
def use_clock(clock: Clock | None) -> Iterator[None]:
    """Bind *clock* in the current async/thread context when provided."""
    if clock is None:
        yield
        return
    token = _active_clock.set(clock)
    try:
        yield
    finally:
        _active_clock.reset(token)
