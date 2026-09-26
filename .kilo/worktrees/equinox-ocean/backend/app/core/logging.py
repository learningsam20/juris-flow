"""Structured JSON logging (PRD §7.3 P1) with correlation ID support."""

from __future__ import annotations

import json
import logging
import uuid
from contextvars import ContextVar
from typing import Any

correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if getattr(record, "exc_info", None):
            payload["exception"] = self.formatException(record.exc_info)  # type: ignore[arg-type]
        extra = getattr(record, "extra", {})
        payload.update(extra)
        cid = correlation_id.get()
        if cid:
            payload["correlation_id"] = cid
        try:
            from opentelemetry import trace

            span = trace.get_current_span()
            ctx = span.get_span_context()
        except Exception:
            ctx = None
        if ctx and ctx.trace_id:
            payload["trace_id"] = format(ctx.trace_id, "032x")
            payload["span_id"] = format(ctx.span_id, "016x")
        return json.dumps(payload, default=str)


def set_correlation_id(cid: str | None = None) -> str:
    value = cid or uuid.uuid4().hex
    correlation_id.set(value)
    return value


def get_correlation_id() -> str | None:
    return correlation_id.get()


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())
    for noisy in ("uvicorn.access", "httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def log_event(logger: logging.Logger, event: str, **fields: Any) -> None:
    logger.info(event, extra={"event": event, **fields})
