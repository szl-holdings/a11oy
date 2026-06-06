"""Real OpenTelemetry span-emission tests.

These run only when the OpenTelemetry SDK is installed (the `[otel]` extra);
they are skipped otherwise so the default dependency-light test run stays green.
When they run, they assert against a real in-memory span exporter — the spans
must actually be recorded with the expected names and attributes. No mocks of
the tracer itself, no `assert True`.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

# Skip the whole module unless the OpenTelemetry SDK is importable.
pytest.importorskip("opentelemetry.sdk.trace")

from opentelemetry import trace  # noqa: E402
from opentelemetry.sdk.trace import TracerProvider  # noqa: E402
from opentelemetry.sdk.trace.export import SimpleSpanProcessor  # noqa: E402
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (  # noqa: E402
    InMemorySpanExporter,
)


@pytest.fixture()
def telemetry_with_memory_exporter(monkeypatch):
    """Reload amaru.telemetry with OTel enabled, wired to an in-memory exporter.

    OpenTelemetry's *global* TracerProvider can only be set once per process,
    so this fixture does NOT rely on the global. It builds its own provider +
    in-memory exporter and points the telemetry module's tracer straight at
    that provider's ``get_tracer``. That keeps every test independent and the
    exporter assertions deterministic regardless of test execution order.
    """
    monkeypatch.setenv("AMARU_OTEL_ENABLED", "1")

    provider = TracerProvider()
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    for name in list(sys.modules):
        if name.startswith("amaru"):
            del sys.modules[name]
    telemetry = importlib.import_module("amaru.telemetry")
    # Bind the module tracer to OUR provider (not the global one), so spans
    # always land in `exporter` even if another test already set the global.
    telemetry._tracer = provider.get_tracer("amaru-test")  # type: ignore[attr-defined]
    exporter.clear()
    try:
        yield telemetry, exporter
    finally:
        # Restore the no-otel default so we don't leak an active tracer into
        # other tests (e.g. the /healthz otel-flag assertion).
        telemetry._tracer = None  # type: ignore[attr-defined]
        for name in list(sys.modules):
            if name.startswith("amaru"):
                del sys.modules[name]


def test_span_is_recorded_with_name_and_attributes(telemetry_with_memory_exporter):
    telemetry, exporter = telemetry_with_memory_exporter
    assert telemetry.otel_active() is True

    with telemetry.span("amaru.span.scheduler_tick", has_envelope=True):
        pass

    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    span = spans[0]
    assert span.name == "amaru.span.scheduler_tick"
    assert span.attributes.get("has_envelope") is True


def test_two_operations_emit_two_distinct_spans(telemetry_with_memory_exporter):
    telemetry, exporter = telemetry_with_memory_exporter

    with telemetry.span("amaru.span.scheduler_tick", has_envelope=False):
        pass
    with telemetry.span("amaru.span.receipts_read", limit=25):
        pass

    spans = exporter.get_finished_spans()
    names = sorted(s.name for s in spans)
    assert names == ["amaru.span.receipts_read", "amaru.span.scheduler_tick"]
    receipts_span = next(s for s in spans if s.name == "amaru.span.receipts_read")
    assert receipts_span.attributes.get("limit") == 25


def test_endpoint_spans_emitted_through_fastapi_routes(telemetry_with_memory_exporter):
    # Drive the real endpoints via TestClient and confirm our explicit
    # operation spans are recorded for /scheduler/tick and /receipts.
    telemetry, exporter = telemetry_with_memory_exporter
    from fastapi.testclient import TestClient

    app_mod = importlib.import_module("amaru.app")
    # app.py imported its own `span` symbol at module load; repoint it at the
    # reloaded, otel-active telemetry so endpoint spans hit our exporter.
    app_mod.span = telemetry.span  # type: ignore[attr-defined]
    client = TestClient(app_mod.app)

    client.post("/scheduler/tick", json={"envelope": {"signals": {
        "grounded": 0.9, "integrity": 0.9, "novelty": 0.4, "fluency": 0.7,
        "intent": 0.8, "agency": 0.9, "friction": 0.1, "care": 0.8, "harm": 0.2,
        "clarity": 0.9, "truth": 0.9, "pattern_strength": 0.7, "uncertainty": 0.2,
    }}})
    client.get("/receipts?limit=10")

    names = [s.name for s in exporter.get_finished_spans()]
    assert "amaru.span.scheduler_tick" in names
    assert "amaru.span.receipts_read" in names
