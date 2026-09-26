"""Unit tests for the OTel telemetry façade (incr/record/snapshot + init)."""

from __future__ import annotations

import importlib

from app.core import telemetry


def test_incr_and_snapshot():
    telemetry.incr("unit.test.counter", amount=3)
    telemetry.incr("unit.test.counter", amount=2)
    snap = telemetry.snapshot_metrics()
    assert snap["unit.test.counter"] >= 5


def test_record_histogram():
    telemetry.record("unit.test.latency_ms", 42.0)
    telemetry.record("unit.test.latency_ms", 8.0)
    snap = telemetry.snapshot_metrics()
    assert snap["unit.test.latency_ms"] >= 2
    assert snap["unit.test.latency_ms_total"] >= 50.0


def test_timed_records_elapsed():
    stop = telemetry.timed("unit.test.timed")
    stop()
    snap = telemetry.snapshot_metrics()
    assert snap["unit.test.timed_total"] >= 0


def test_init_noop_without_endpoint(monkeypatch):
    monkeypatch.setenv("JAIL_OTEL_EXPORTER_OTLP_ENDPOINT", "")
    importlib.reload(telemetry)
    telemetry.init_tracing()
    telemetry.init_metrics()
    telemetry.init_logs()
    assert telemetry._meter is None


def test_init_otel_noop_without_endpoint(monkeypatch):
    monkeypatch.setenv("JAIL_OTEL_EXPORTER_OTLP_ENDPOINT", "")
    importlib.reload(telemetry)

    class _FakeApp:
        pass

    telemetry.init_otel(_FakeApp())
    assert telemetry._meter is None
