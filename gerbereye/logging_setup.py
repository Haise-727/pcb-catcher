"""Structured JSON-lines logging.

FR-027. Every inspection must record `registration_residual_px`, per-stage
duration and component count. Those three fields are what let you tell a
latency regression from an accuracy regression — without them both present as
"it got worse" and there is nothing to bisect against.

Format is one JSON object per line, which greps and parses without a log
library on the reading end. That matters on a shop laptop where the person
debugging has a terminal and nothing else.

The file is size-capped and rotated. A station running 100+ boards a shift
would otherwise fill the disk, and an inspection station that stops working
because its log grew is a worse failure than having no log.
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import time
from contextlib import contextmanager
from typing import Any, Iterator

from . import config

LOG_NAME = "gerbereye"
MAX_BYTES = 5 * 1024 * 1024
BACKUP_COUNT = 3

_configured = False


class JsonLinesFormatter(logging.Formatter):
    """Render each record as a single JSON object.

    Extra fields attached via `logger.info(..., extra={...})` are merged into
    the object, so an inspection record and a plain message share one schema.
    """

    # Attributes LogRecord always carries; anything else was added by a caller
    # and belongs in the output.
    _RESERVED = {
        "args", "asctime", "created", "exc_info", "exc_text", "filename",
        "funcName", "levelname", "levelno", "lineno", "module", "msecs",
        "message", "msg", "name", "pathname", "process", "processName",
        "relativeCreated", "stack_info", "thread", "threadName", "taskName",
    }

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created))
                  + f".{int(record.msecs):03d}Z",
            "level": record.levelname,
            "event": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in self._RESERVED and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        # default=str so a Path or a numpy scalar cannot take the log down.
        return json.dumps(payload, default=str)


def setup(level: int = logging.INFO) -> logging.Logger:
    """Configure the logger. Safe to call repeatedly."""
    global _configured
    logger = logging.getLogger(LOG_NAME)
    if _configured:
        return logger

    config.ensure_dirs()
    logger.setLevel(level)
    logger.propagate = False

    handler = logging.handlers.RotatingFileHandler(
        config.DATA_DIR / "gerbereye.jsonl",
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    handler.setFormatter(JsonLinesFormatter())
    logger.addHandler(handler)

    _configured = True
    return logger


def get_logger() -> logging.Logger:
    return setup()


class StageTimer:
    """Accumulates per-stage durations for one inspection.

    Deliberately a plain accumulator rather than anything clever: the timings
    are compared against a fixed latency budget (NFR-001), so they need to be
    trivially readable in the log rather than aggregated in the app.
    """

    def __init__(self) -> None:
        self._durations: dict[str, float] = {}
        self._start = time.perf_counter()

    @contextmanager
    def stage(self, name: str) -> Iterator[None]:
        started = time.perf_counter()
        try:
            yield
        finally:
            # Recorded even when the stage raises. A stage that failed slowly
            # is exactly the one worth seeing in the log.
            self._durations[name] = (time.perf_counter() - started) * 1000.0

    @property
    def total_ms(self) -> float:
        return (time.perf_counter() - self._start) * 1000.0

    def as_dict(self) -> dict[str, float]:
        return {f"{name}_ms": round(value, 2) for name, value in self._durations.items()}


def log_inspection(
    *,
    board_type_id: int,
    verdict: str,
    path_used: str,
    component_count: int,
    region_count: int,
    timer: StageTimer,
    registration_residual_px: float | None = None,
    registration_state: str | None = None,
    degraded: bool = False,
    inspection_id: int | None = None,
) -> None:
    """Record one inspection in the form FR-027 requires."""
    get_logger().info(
        "inspection",
        extra={
            "inspection_id": inspection_id,
            "board_type_id": board_type_id,
            "verdict": verdict,
            "path_used": path_used,
            "component_count": component_count,
            "region_count": region_count,
            "registration_residual_px": (
                round(registration_residual_px, 3)
                if registration_residual_px is not None
                else None
            ),
            "registration_state": registration_state,
            "degraded": degraded,
            "total_ms": round(timer.total_ms, 2),
            **timer.as_dict(),
        },
    )


def log_event(event: str, **fields: Any) -> None:
    get_logger().info(event, extra=fields)


def log_warning(event: str, **fields: Any) -> None:
    get_logger().warning(event, extra=fields)
