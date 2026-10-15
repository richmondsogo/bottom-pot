"""Process-local source telemetry for the Phase 1 pipeline foundation."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from enum import Enum
from threading import Lock

from loguru import logger


class SourceKind(str, Enum):
    ATS = "ats"
    NIGERIAN_BOARD = "nigerian_board"


class SourceOutcome(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class SourceTelemetryEvent:
    source: str
    kind: SourceKind
    outcome: SourceOutcome
    duration_ms: int
    result_count: int
    dropped_count: int = 0


@dataclass
class SourceTelemetrySummary:
    source: str
    kind: SourceKind
    runs: int = 0
    successful_runs: int = 0
    failed_runs: int = 0
    cancelled_runs: int = 0
    result_count: int = 0
    dropped_count: int = 0
    total_duration_ms: int = 0


class SourceTelemetry:
    """Thread-safe, in-memory source metrics with structured completion logs."""

    def __init__(self) -> None:
        self._summaries: dict[tuple[str, SourceKind], SourceTelemetrySummary] = {}
        self._lock = Lock()

    def record(self, event: SourceTelemetryEvent) -> None:
        key = (event.source, event.kind)
        with self._lock:
            summary = self._summaries.setdefault(
                key,
                SourceTelemetrySummary(source=event.source, kind=event.kind),
            )
            summary.runs += 1
            summary.result_count += event.result_count
            summary.dropped_count += event.dropped_count
            summary.total_duration_ms += event.duration_ms
            if event.outcome is SourceOutcome.SUCCESS:
                summary.successful_runs += 1
            elif event.outcome is SourceOutcome.FAILURE:
                summary.failed_runs += 1
            else:
                summary.cancelled_runs += 1

        logger.bind(event="source_telemetry").info(
            json.dumps(
                {
                    "event": "source_telemetry",
                    **asdict(event),
                    "kind": event.kind.value,
                    "outcome": event.outcome.value,
                },
                default=str,
                sort_keys=True,
            )
        )

    def snapshot(self) -> list[SourceTelemetrySummary]:
        with self._lock:
            return [
                SourceTelemetrySummary(**asdict(summary))
                for _, summary in sorted(
                    self._summaries.items(), key=lambda item: (item[0][0], item[0][1].value)
                )
            ]

    def reset(self) -> None:
        with self._lock:
            self._summaries.clear()


source_telemetry = SourceTelemetry()
