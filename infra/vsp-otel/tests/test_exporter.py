# SPDX-License-Identifier: Apache-2.0
# © 2026 SZL Holdings — Yachay (CTO) + Perplexity Computer Agent
# Doctrine v11 LOCKED — 749/14/163 · Λ = Conjecture 1
"""Real exporter test: a mock OTLP receiver captures exported span batches."""

from __future__ import annotations

from vsp_otel.exporter import Welford, VSPExporterConfig, build_exporter


class _MockOTLPReceiver:
    """Stand-in for the upstream OTLPSpanExporter — captures batches.

    Implements the SpanExporter protocol so VSPSpanExporter can delegate to it
    exactly as it would to the real gRPC exporter.
    """

    def __init__(self):
        self.batches = []
        self.shutdown_called = False

    def export(self, spans):
        self.batches.append(list(spans))
        return "SUCCESS"

    def shutdown(self):
        self.shutdown_called = True

    def force_flush(self, timeout_millis=30000):
        return True


def test_exporter_delegates_and_records_fanout():
    recv = _MockOTLPReceiver()
    exp = build_exporter(VSPExporterConfig(endpoint="http://mock:4317"),
                         inner=recv)

    exp.export(["s1", "s2", "s3"])
    exp.export(["s4"])

    # Spans actually reached the (mock) OTLP receiver, in the right batches.
    assert len(recv.batches) == 2
    assert recv.batches[0] == ["s1", "s2", "s3"]
    assert recv.batches[1] == ["s4"]

    # Fan-out (Welford) recorded batch sizes 3 and 1.
    snap = exp.fanout_snapshot()
    assert snap["n"] == 2
    assert abs(snap["mean"] - 2.0) < 1e-9


def test_exporter_shutdown_and_flush_delegate():
    recv = _MockOTLPReceiver()
    exp = build_exporter(inner=recv)
    assert exp.force_flush() is True
    exp.shutdown()
    assert recv.shutdown_called is True


def test_build_exporter_raises_without_otlp_package(monkeypatch):
    """HONESTY: with no inner and no OTLP package, we raise — not silent no-op."""
    import builtins
    real_import = builtins.__import__

    def fake_import(name, *a, **k):
        if name.startswith("opentelemetry.exporter.otlp"):
            raise ImportError("simulated missing otlp")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    try:
        build_exporter(VSPExporterConfig())
        assert False, "expected RuntimeError"
    except RuntimeError as e:
        assert "otlp" in str(e).lower()


def test_welford_matches_numpy_style_variance():
    w = Welford()
    data = [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]
    for x in data:
        w.update(x)
    # Population mean=5, population variance=4, stddev=2 (classic example).
    assert abs(w.mean - 5.0) < 1e-9
    assert abs(w.variance - 4.0) < 1e-9
    assert abs(w.stddev - 2.0) < 1e-9


def test_config_from_env(monkeypatch):
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector:4317")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_HEADERS", "x-api-key=abc,team=mesh")
    cfg = VSPExporterConfig.from_env()
    assert cfg.endpoint == "http://collector:4317"
    assert cfg.headers["x-api-key"] == "abc"
    assert cfg.headers["team"] == "mesh"
