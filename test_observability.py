# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
"""test_observability — SZL-native distributed tracing is real, bounded, leak-proof.

Asserts szl_observability behaviour, fully OFFLINE (pure stdlib + FastAPI
TestClient; no network):

  1. A span records a REAL measured duration (> 0, and ~tracks an actual sleep).
  2. Nested spans form a TREE under ONE trace_id (child.parent_id == parent.span_id).
  3. The ring buffer is BOUNDED — appending past capacity drops the OLDEST.
  4. The /traces endpoint returns recent traces SLOWEST-FIRST.
  5. NO secret leaks into span attributes (key-name screened, body coerced).
  6. Tracing FAILS OPEN when its internals error (never raises into wrapped code),
     and a span() outside any trace is a harmless no-op.
  7. The compute-pool fan-out story: a concurrent fan-out yields one trace whose
     per-node spans show WHERE the time went (the slow/timeout node is visible).
  8. register(app) is additive and the endpoints serve real ring data.

Run:
    python3 test_observability.py     (or: pytest test_observability.py)
"""
from __future__ import annotations

import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import szl_observability as obs  # noqa: E402

NS = "a11oy"


# ---------------------------------------------------------------------------
# 1. A span records a REAL measured duration.
# ---------------------------------------------------------------------------
def test_span_records_real_duration():
    tr = obs.start_trace("dur-test")
    with obs.span("slow-bit") as s:
        time.sleep(0.02)  # 20ms
    obs.finish_trace(tr, record=False)
    assert s is not None
    assert s.ended is True
    assert s.duration_ms is not None
    # Real wall time: at least the sleep, and a sane upper bound (not fabricated).
    assert s.duration_ms >= 15.0, f"expected >=15ms real duration, got {s.duration_ms}"
    assert s.duration_ms < 2000.0


def test_unended_span_has_no_fabricated_duration():
    # Honest: a span never ended reports duration None, NOT a made-up number.
    sp = obs.Span("never-ended", trace_id="t", parent_id=None)
    assert sp.ended is False
    assert sp.duration_ms is None


# ---------------------------------------------------------------------------
# 2. Nested spans form a tree under ONE trace_id.
# ---------------------------------------------------------------------------
def test_nested_spans_form_tree_under_one_trace_id():
    tr = obs.start_trace("tree-test")
    with obs.span("parent") as p:
        with obs.span("child-1") as c1:
            with obs.span("grandchild") as g:
                pass
        with obs.span("child-2") as c2:
            pass
    obs.finish_trace(tr, record=False)

    # All spans share the one trace_id (== root trace_id).
    for sp in (p, c1, c2, g):
        assert sp.trace_id == tr.trace_id

    # Parent/child wiring is correct (a real tree, not a flat list).
    assert c1.parent_id == p.span_id
    assert c2.parent_id == p.span_id
    assert g.parent_id == c1.span_id

    # On exit, context restores to the parent each time (siblings share a parent).
    assert c1.parent_id == c2.parent_id


# ---------------------------------------------------------------------------
# 3. The ring buffer is BOUNDED (drops oldest past capacity).
# ---------------------------------------------------------------------------
def test_ring_buffer_is_bounded_drops_oldest():
    ring = obs.TraceRing(capacity=4)
    for i in range(20):
        t = obs.Trace(f"trace-{i}")
        t.end()
        ring.add(t)
    assert len(ring) == 4, "ring must never exceed capacity"
    names = [t.name for t in ring.all()]
    # Oldest 16 dropped; only the last 4 remain, in order.
    assert names == ["trace-16", "trace-17", "trace-18", "trace-19"]


# ---------------------------------------------------------------------------
# 4. /traces endpoint returns traces SLOWEST-FIRST.
# ---------------------------------------------------------------------------
def _fresh_ring(monkeypatch_cap=200):
    """Swap in a fresh process ring so tests don't interfere with each other."""
    ring = obs.TraceRing(capacity=monkeypatch_cap)
    obs.TRACES = ring  # rebind the module-global ring the endpoints read
    return ring


def test_traces_endpoint_is_slowest_first():
    _fresh_ring()
    # Build three traces with controlled, REAL but distinct durations.
    for nm, sleep_s in (("fast", 0.005), ("slow", 0.05), ("medium", 0.02)):
        tr = obs.start_trace(nm)
        with obs.span("body"):
            time.sleep(sleep_s)
        obs.finish_trace(tr, record=True)

    summaries = obs.recent_traces(limit=10, slowest_first=True)
    durs = [s["duration_ms"] for s in summaries]
    # Monotonically non-increasing -> slowest first.
    assert durs == sorted(durs, reverse=True), f"not slowest-first: {durs}"
    assert summaries[0]["name"] == "slow"


# ---------------------------------------------------------------------------
# 5. NO secret leaks into span attributes.
# ---------------------------------------------------------------------------
def test_no_secret_leaks_into_attributes():
    tr = obs.start_trace("leak-test")
    with obs.span(
        "auth-call",
        api_key="SUPERSECRET-XYZ",
        authorization="Bearer leak-me",
        password="hunter2",
        session_token="sess-123",
        node="chaski",              # safe scalar -> kept
        endpoint="100.76.58.50:443",
        body={"password": "nested-secret", "card": "4111111111111111"},
    ) as s:
        pass
    obs.finish_trace(tr, record=False)

    # Secret-hinted keys are redacted.
    assert s.attributes.get("api_key") == "[redacted]"
    assert s.attributes.get("authorization") == "[redacted]"
    assert s.attributes.get("password") == "[redacted]"
    assert s.attributes.get("session_token") == "[redacted]"
    # Safe scalars are preserved (tracing is still useful).
    assert s.attributes.get("node") == "chaski"
    assert s.attributes.get("endpoint") == "100.76.58.50:443"
    # The whole serialized attribute blob contains no literal secret value.
    blob = repr(s.attributes)
    for secret in ("SUPERSECRET-XYZ", "Bearer leak-me", "hunter2", "sess-123",
                   "nested-secret", "4111111111111111"):
        assert secret not in blob, f"secret leaked: {secret}"


# ---------------------------------------------------------------------------
# 6. Tracing FAILS OPEN when internals error / outside any trace.
# ---------------------------------------------------------------------------
def test_fail_open_outside_trace_is_noop():
    # Clear the context: no active trace.
    obs._CURRENT_TRACE.set(None)
    obs._CURRENT_SPAN.set(None)
    ran = {"v": False}
    # span() with no active trace must NOT raise; the wrapped block runs normally.
    with obs.span("orphan", node="x"):
        ran["v"] = True
    assert ran["v"] is True


def test_fail_open_when_internals_error():
    # Force start_span to blow up; the context manager must still not raise into
    # the wrapped code (tracing is transparent / fail-open).
    tr = obs.start_trace("boom-test")
    orig = tr.start_span
    obs._CURRENT_TRACE.set(tr)

    def _explode(*a, **k):
        raise RuntimeError("induced tracer failure")

    tr.start_span = _explode  # type: ignore[assignment]
    ran = {"v": False}
    try:
        with obs.span("will-fail-internally"):
            ran["v"] = True
    finally:
        tr.start_span = orig  # type: ignore[assignment]
    assert ran["v"] is True, "fail-open: wrapped block must run even if tracer errors"


def test_wrapped_exception_is_reraised_and_span_marked():
    # An exception inside the span is re-raised (transparent) and the span status
    # reflects it honestly (TIMEOUT for timeout-family, ELSE ERROR).
    tr = obs.start_trace("err-test")
    captured = {}

    class _FakeTimeout(Exception):
        pass
    _FakeTimeout.__name__ = "TimeoutError"

    raised = False
    try:
        with obs.span("timing-out-node") as s:
            captured["s"] = s
            raise _FakeTimeout("simulated hang")
    except _FakeTimeout:
        raised = True
    obs.finish_trace(tr, record=False)
    assert raised is True, "exception must propagate (tracing is transparent)"
    assert captured["s"].status == "TIMEOUT"
    # Only the exception TYPE name is stored, never the message.
    assert captured["s"].attributes.get("exc_type") == "TimeoutError"
    assert "simulated hang" not in repr(captured["s"].attributes)


# ---------------------------------------------------------------------------
# 7. The compute-pool fan-out story: a trace shows WHERE the 7s would go.
# ---------------------------------------------------------------------------
def test_compute_pool_fanout_trace_reveals_slow_node():
    import threading

    _fresh_ring()
    tr = obs.start_trace("compute-pool")

    # Simulate the concurrent fan-out: each node probe in its own thread, each
    # wrapped in a span. Durations are REAL sleeps standing in for probe latency.
    nodes = [("betterwithage", 0.03, "OK"), ("chaski", 0.06, "TIMEOUT"), ("groq", 0.01, "OK")]
    root_trace = tr  # captured for child threads to bind

    def _probe(name, latency, outcome):
        # Re-bind context in the worker thread (contextvars don't auto-propagate
        # across raw threads — we set the parent trace/span explicitly, exactly as
        # the real fan-out helper would when instrumenting each node).
        obs._CURRENT_TRACE.set(root_trace)
        obs._CURRENT_SPAN.set(root_trace.root)
        try:
            with obs.span(name, node=name) as sp:
                time.sleep(latency)
                if outcome == "TIMEOUT":
                    sp.set_status("TIMEOUT")
        except Exception:
            pass

    threads = [threading.Thread(target=_probe, args=n) for n in nodes]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    obs.finish_trace(tr, record=True)

    d = tr.to_dict()
    # One trace, four spans (root compute-pool + 3 node spans).
    assert d["span_count"] == 4
    by_name = {sp["name"]: sp for sp in d["spans"] if sp["name"] != "compute-pool"}
    assert set(by_name) == {"betterwithage", "chaski", "groq"}
    # Each node span has a REAL measured duration.
    for nm, sp in by_name.items():
        assert sp["duration_ms"] is not None and sp["duration_ms"] > 0
    # The slow/timeout node is visible and worst-status rolls up to TIMEOUT.
    assert by_name["chaski"]["status"] == "TIMEOUT"
    assert by_name["chaski"]["duration_ms"] > by_name["groq"]["duration_ms"]
    assert d["status"] == "TIMEOUT"


# ---------------------------------------------------------------------------
# 8. register(app) is additive; endpoints serve real ring data.
# ---------------------------------------------------------------------------
def test_register_and_endpoints():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    _fresh_ring()
    app = FastAPI()
    paths = obs.register(app, ns=NS)
    assert f"/api/{NS}/v1/observability/traces" in paths
    assert f"/api/{NS}/v1/observability/health-summary" in paths

    # Record a couple of real traces into the (rebound) ring.
    ids = []
    for nm, sleep_s in (("surfaceA", 0.01), ("surfaceA", 0.04), ("surfaceB", 0.02)):
        tr = obs.start_trace(nm)
        with obs.span("probe"):
            time.sleep(sleep_s)
        obs.finish_trace(tr, record=True)
        ids.append(tr.trace_id)

    client = TestClient(app)

    # /traces — slowest-first, real ring data.
    r = client.get(f"/api/{NS}/v1/observability/traces")
    assert r.status_code == 200
    body = r.json()
    assert body["order"] == "slowest-first"
    assert body["ring"]["size"] == 3
    durs = [t["duration_ms"] for t in body["traces"]]
    assert durs == sorted(durs, reverse=True)

    # /trace/{id} — full span tree for a known id.
    r = client.get(f"/api/{NS}/v1/observability/trace/{ids[0]}")
    assert r.status_code == 200
    assert r.json()["trace"]["trace_id"] == ids[0]

    # /trace/{id} — honest 404 for an unknown id (never fabricated).
    r = client.get(f"/api/{NS}/v1/observability/trace/does-not-exist")
    assert r.status_code == 404
    assert r.json()["error"] == "trace_not_found"

    # /health-summary — per-surface p50/p95 + error rate from the ring.
    r = client.get(f"/api/{NS}/v1/observability/health-summary")
    assert r.status_code == 200
    summ = r.json()["surfaces"]
    assert "surfaceA" in summ and "surfaceB" in summ
    assert summ["surfaceA"]["requests"] == 2
    assert summ["surfaceA"]["p50_ms"] is not None
    assert summ["surfaceA"]["p95_ms"] is not None


def test_register_is_additive_skips_existing():
    from fastapi import FastAPI

    app = FastAPI()
    first = obs.register(app, ns=NS)
    assert len(first) >= 1
    # Second registration must skip already-present paths (additive, no clobber).
    second = obs.register(app, ns=NS)
    assert second == [], "re-register must not re-add existing routes"


def test_trace_id_reuses_request_id():
    # trace_id reuses an inbound X-Request-ID so a trace correlates with the
    # prod-hardening access log line.
    rid = "req-correlation-abc123"
    tr = obs.start_trace("with-rid", trace_id=rid)
    with obs.span("x"):
        pass
    obs.finish_trace(tr, record=False)
    assert tr.trace_id == rid
    for sp in tr.spans:
        assert sp.trace_id == rid


if __name__ == "__main__":
    # Allow running directly without pytest (offline, deterministic).
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    failed = []
    for fn in fns:
        try:
            fn()
            passed += 1
            print(f"PASS {fn.__name__}")
        except Exception as exc:  # noqa: BLE001
            failed.append(fn.__name__)
            print(f"FAIL {fn.__name__}: {exc!r}")
    print(f"\n{passed}/{len(fns)} passed; failed: {failed}")
    sys.exit(1 if failed else 0)
