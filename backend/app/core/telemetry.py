"""Unified OTel telemetry: traces, metrics, and logs over OTLP.

When ``JAIL_OTEL_EXPORTER_OTLP_ENDPOINT`` is set the three OTel SDK providers
(traces, metrics, logs) are initialized and export to the collector via gRPC.
When the endpoint is empty, ``incr`` / ``record`` fall back to in-memory dicts
so the application continues to function without a collector.

All three signals (traces, metrics, logs) are exportable to any
OTel-compliant log/metrics/traces sync (collector, Grafana, Datadog, etc.).
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from typing import Any

from app.config import get_settings

# ---------------------------------------------------------------------------
# Resource (shared across all three OTel providers)
# ---------------------------------------------------------------------------
_resource: Any = None  # lazily created once


def _get_resource() -> Any:
    global _resource
    if _resource is None:
        from opentelemetry.sdk.resources import Resource

        _resource = Resource.create({"service.name": "jurisflow-api"})
    return _resource


# ---------------------------------------------------------------------------
# In-memory counters (fallback when OTel endpoint is not configured)
# ---------------------------------------------------------------------------
_metrics_lock = threading.Lock()
_metrics: dict[str, float] = {}
_instruments: dict[str, Any] = {}  # OTel Counter / Histogram references
_meter: Any = None  # OTel Meter (set once by init_metrics)


def _get_or_create_instrument(name: str, kind: str = "counter") -> Any:
    """Return a cached OTel instrument or create it on first use."""
    if _meter is None or name in _instruments:
        return _instruments.get(name)
    if kind == "counter":
        inst = _meter.create_counter(name, description=name.replace(".", " "))
    else:
        inst = _meter.create_histogram(
            name, unit="ms", description=name.replace(".", " ")
        )
    _instruments[name] = inst
    return inst


def incr(name: str, amount: int = 1) -> None:
    """Increment a counter.  OTel when available, in-memory dict otherwise."""
    inst = _get_or_create_instrument(name, "counter")
    if inst is not None:
        inst.add(amount)
    else:
        with _metrics_lock:
            _metrics[name] = _metrics.get(name, 0) + amount


def record(name: str, value: float) -> None:
    """Record a value in a histogram.  OTel when available, in-memory otherwise."""
    inst = _get_or_create_instrument(name, "histogram")
    if inst is not None:
        inst.record(value)
    else:
        with _metrics_lock:
            _metrics.setdefault(name, 0.0)
            _metrics[name] += 1.0
            current = _metrics.get(f"{name}_total", 0.0)
            _metrics[f"{name}_total"] = current + value


def snapshot_metrics() -> dict[str, int | float]:
    """Snapshot of in-memory counters (non-OTel fallback)."""
    with _metrics_lock:
        return dict(_metrics)


def timed(name: str) -> Callable[[], None]:
    """Context-manager-ish helper returning a stop() callable recording elapsed ms."""
    start = time.perf_counter()

    def stop() -> None:
        record(name, (time.perf_counter() - start) * 1000.0)

    return stop


# ---------------------------------------------------------------------------
# OTel initializers (called once during FastAPI lifespan)
# ---------------------------------------------------------------------------


def _otlp_endpoint() -> str | None:
    endpoint = get_settings().otel_exporter_otlp_endpoint
    return endpoint or None


def init_tracing() -> None:
    """Initialize OTel TracerProvider + BatchSpanProcessor + optional
    auto-instrumentation for FastAPI HTTP spans."""
    endpoint = _otlp_endpoint()
    if endpoint is None:
        return
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        provider = TracerProvider(resource=_get_resource())
        provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint))
        )
        trace.set_tracer_provider(provider)
    except Exception:  # pragma: no cover
        logging.getLogger(__name__).warning("OTel tracing init failed", exc_info=True)


def init_metrics() -> None:
    """Initialize OTel MeterProvider + OTLP metrics exporter.

    Once initialized the global ``_meter`` is set and all ``incr``/``record``
    calls flow through OTel Counter / Histogram instruments.
    """
    global _meter
    endpoint = _otlp_endpoint()
    if endpoint is None:
        return
    try:
        from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
            OTLPMetricExporter,
        )
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader

        reader = PeriodicExportingMetricReader(
            OTLPMetricExporter(endpoint=endpoint),
            export_interval_millis=15_000,
        )
        provider = MeterProvider(resource=_get_resource(), metric_readers=[reader])
        _meter = provider.get_meter("jurisflow-api")
    except Exception:  # pragma: no cover
        logging.getLogger(__name__).warning("OTel metrics init failed", exc_info=True)


def init_logs() -> None:
    """Attach an OTel ``LoggingHandler`` to the root logger so every
    ``logging.info(...)`` / ``logging.error(...)`` call is exported as an
    OTel LogRecord via OTLP."""
    endpoint = _otlp_endpoint()
    if endpoint is None:
        return
    try:
        from opentelemetry._logs import set_logger_provider
        from opentelemetry.exporter.otlp.proto.grpc._log_exporter import (
            OTLPLogExporter,
        )
        from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
        from opentelemetry.sdk._logs.export import BatchLogRecordProcessor

        provider = LoggerProvider(resource=_get_resource())
        provider.add_log_record_processor(
            BatchLogRecordProcessor(OTLPLogExporter(endpoint=endpoint))
        )
        set_logger_provider(provider)
        handler = LoggingHandler(logger_provider=provider)
        logging.root.addHandler(handler)
    except Exception:  # pragma: no cover
        logging.getLogger(__name__).warning("OTel logs init failed", exc_info=True)


def instrument_logging() -> None:
    """Bridge stdlib logging → OTel via opentelemetry-instrumentation-logging.

    This injects the OTel trace/span context into every log record so log
    lines emitted by third-party libraries are correlated with traces.
    """
    try:
        from opentelemetry.instrumentation.logging import (  # type: ignore[import-not-found]
            LoggingInstrumentor,
        )

        LoggingInstrumentor().instrument()
    except Exception:  # pragma: no cover
        logging.getLogger(__name__).debug(
            "LoggingInstrumentor unavailable", exc_info=True
        )


def instrument_fastapi(app: Any) -> None:
    """Auto-instrument FastAPI — generates per-request spans automatically."""
    try:
        from opentelemetry.instrumentation.fastapi import (  # type: ignore[import-not-found]
            FastAPIInstrumentor,
        )

        FastAPIInstrumentor.instrument_app(app)
    except Exception:  # pragma: no cover
        logging.getLogger(__name__).debug(
            "FastAPIInstrumentor unavailable", exc_info=True
        )


def init_otel(app: Any) -> None:
    """Convenience: initialize all three OTel signals in one call.

    Called from ``app/main.py`` lifespan startup.
    """
    init_tracing()
    init_metrics()
    init_logs()
    instrument_logging()
    instrument_fastapi(app)
