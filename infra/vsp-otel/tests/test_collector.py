"""
tests/test_collector.py — vsp-otel collector exporter shim tests.

Validates the Λ-gate (floor 0.90), DSSE signing, Welford latency, HyperLogLog
cardinality, and the OTLP process pipeline end-to-end (no network forwarding).

Run: pytest tests/ -v
"""
from __future__ import annotations

import importlib.util
import os
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from collector import lambda_gate, stats  # noqa: E402
from collector.dsse import DsseSigner  # noqa: E402


# ── Λ-gate ────────────────────────────────────────────────────────────────────
def test_lambda_floor_is_090():
    assert lambda_gate.LAMBDA_FLOOR == 0.90


def test_high_axes_pass():
    attrs = {f"lambda.a{i}": 0.97 for i in range(1, 6)}
    r = lambda_gate.evaluate(attrs)
    assert r.passed is True
    assert r.lambda_value >= 0.90


def test_low_axis_rejects():
    attrs = {"lambda.a1": 0.5, "lambda.a2": 0.97, "lambda.a3": 0.97,
             "lambda.a4": 0.97, "lambda.a5": 0.97}
    r = lambda_gate.evaluate(attrs)
    assert r.passed is False
    assert r.lambda_value < 0.90


def test_geometric_mean_penalises_one_bad_axis():
    # geometric mean of [0.99,0.99,0.99,0.99,0.10] is far below floor
    attrs = {"lambda.a1": 0.99, "lambda.a2": 0.99, "lambda.a3": 0.99,
             "lambda.a4": 0.99, "lambda.a5": 0.10}
    r = lambda_gate.evaluate(attrs)
    assert r.passed is False


# ── Welford ────────────────────────────────────────────────────────────────────
def test_welford_mean_exact():
    w = stats.Welford()
    data = [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]
    for x in data:
        w.update(x)
    assert abs(w.mean - sum(data) / len(data)) < 1e-9   # welford_mean_exact
    # sample variance of this classic dataset is 4.571428...
    assert abs(w.variance - 32.0 / 7.0) < 1e-9


# ── HyperLogLog ────────────────────────────────────────────────────────────────
def test_hll_cardinality_within_error():
    hll = stats.HyperLogLog(p=14)
    n = 10000
    for i in range(n):
        hll.add(f"trace-{i:08x}")
    est = hll.count()
    # standard error ~0.81% at p=14; allow generous 5% for CI determinism
    assert abs(est - n) / n < 0.05


def test_hll_dedupes():
    hll = stats.HyperLogLog(p=12)
    for _ in range(1000):
        hll.add("same-trace-id")
    assert hll.count() <= 2


# ── DSSE signing ────────────────────────────────────────────────────────────────
def test_dsse_envelope_shape():
    s = DsseSigner()
    env = s.sign_span(
        {"trace_id": "abc", "span_id": "def", "name": "sentra.gate.evaluate"},
        {"lambda_value": 0.95, "floor": 0.90, "passed": True,
         "axes": {"a1_moral_grounding": 0.95}},
    )
    assert env["payloadType"] == "application/vnd.in-toto+json"
    assert env["payload"]
    assert env["signatures"][0]["sig"]
    assert len(env["receipt_hash"]) == 64


# ── full OTLP pipeline ───────────────────────────────────────────────────────────
def _otlp_span(trace_id, span_id, axes, start_ns=0, end_ns=1_000_000):
    return {
        "traceId": trace_id, "spanId": span_id, "name": "sentra.gate.evaluate",
        "startTimeUnixNano": str(start_ns), "endTimeUnixNano": str(end_ns),
        "attributes": [{"key": f"lambda.a{i+1}", "value": {"doubleValue": v}}
                       for i, v in enumerate(axes)],
    }


def test_process_otlp_accepts_and_rejects():
    # fresh module state
    import importlib
    from collector import app as appmod
    importlib.reload(appmod)
    payload = {"resourceSpans": [{"scopeSpans": [{"spans": [
        _otlp_span("t1", "s1", [0.97, 0.97, 0.97, 0.97, 0.97]),   # pass
        _otlp_span("t2", "s2", [0.5, 0.97, 0.97, 0.97, 0.97]),    # reject
    ]}]}]}
    summary = appmod.process_otlp(payload)
    assert summary["received"] == 2
    assert summary["accepted"] == 1
    assert summary["rejected"] == 1
    assert summary["unique_traces_est"] >= 1
    assert summary["lambda_floor"] == 0.90


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
