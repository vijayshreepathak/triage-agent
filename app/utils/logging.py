"""Structured JSON logging with request correlation.

Design decisions:

1. JSON lines to stdout — the 12-factor pattern; any log shipper
   (Datadog, CloudWatch, Loki) can ingest without parsing config.
2. ``contextvars`` carry request_id / patient_id / graph_execution_id so
   every log line inside a request is correlated automatically — nodes
   never pass IDs around just for logging (keeps signatures clean and
   async-safe, unlike thread-locals).
3. No ``print`` anywhere in the codebase; this module is the only logging
   entry point.
"""

from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

# Async-safe request-scoped context. Set by the API middleware, read everywhere.
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
patient_id_var: ContextVar[str] = ContextVar("patient_id", default="-")
graph_execution_id_var: ContextVar[str] = ContextVar("graph_execution_id", default="-")

_RESERVED_ATTRS = frozenset(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {"message", "asctime"}


class JsonFormatter(logging.Formatter):
    """Serializes each record as one JSON line, merging context and extras."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_var.get(),
            "patient_id": patient_id_var.get(),
            "graph_execution_id": graph_execution_id_var.get(),
        }
        # Merge structured extras passed via logger.info(..., extra={...}).
        for key, value in record.__dict__.items():
            if key not in _RESERVED_ATTRS and not key.startswith("_"):
                payload[key] = value
        if record.exc_info and record.exc_info[0] is not None:
            payload["error_type"] = record.exc_info[0].__name__
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    """Idempotent root logger setup. Called once at app startup."""
    root = logging.getLogger()
    root.setLevel(level.upper())
    root.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    # Quiet noisy third-party loggers unless we are debugging.
    if level.upper() != "DEBUG":
        for noisy in ("httpx", "httpcore", "urllib3"):
            logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Module-level logger accessor. Use ``get_logger(__name__)``."""
    return logging.getLogger(name)
