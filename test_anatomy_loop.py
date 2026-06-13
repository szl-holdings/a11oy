# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
"""
test_anatomy_loop.py — offline self-test for szl_anatomy_loop.

Imports the module, registers the endpoint on a FAKE app, drives the handler,
and asserts the doctrine v11 invariants hold OFFLINE (no network, no serve.py):

  - joules_label == "sample" by default (off-box, no real meter wired);
  - ayni.balanced is True (reciprocal, never net-positive);
  - no "key" anywhere in the output (no leaked/secret key in the response);
  - every organ carries "experimental" (organs are never claimed proven).

Plus the LATENCY regression guard (the #anatomy-loop-latency fix): when the GPU-
node-backed posture probe is sleeping/failing, the loop must return FAST (<1s, no
~3s synchronous dependency-wait) by fail-fasting through the EXISTING circuit
breaker (szl_resilience) + short-timeout/cache helpers (szl_backend_hardening),
and the degraded posture must be HONEST: gpu flagged sleeping, intake degraded,
joules SAMPLE with NO fabricated measured value, and Ayni STILL balances.

Pure stdlib. Run: python3 test_anatomy_loop.py
"""
import json
import time
import urllib.request

import szl_anatomy_loop as loop


class _FakeApp:
    """Minimal app exposing add_api_route — records what register() wires."""

    def __init__(self):
        self.routes = []

    def add_api_route(self, path, fn, methods=None):
        self.routes.append((path, fn, tuple(methods or [])))


def _extract_body(resp):
    """Pull the JSON dict out of whatever the handler returned (JSONResponse or dict)."""
    if isinstance(resp, dict):
        return resp
    # Starlette JSONResponse keeps the encoded bytes on .body
    body = getattr(resp, "body", None)
    if body is not None:
        return json.loads(body.decode("utf-8") if isinstance(body, (bytes, bytearray)) else body)
    raise AssertionError(f"could not extract body from {resp!r}")


def test_register_wires_loop_route():
    app = _FakeApp()
    registered = loop.register(app, ns="a11oy")
    assert registered == ["/api/a11oy/v1/anatomy/loop"], registered
    assert len(app.routes) == 1
    path, fn, methods = app.routes[0]
    assert path == "/api/a11oy/v1/anatomy/loop"
    assert "GET" in methods
    return fn


def test_loop_invariants():
    # Drive the registered handler exactly as the app would (offline).
    fn = test_register_wires_loop_route()
    resp = fn(None)
    out = _extract_body(resp)

    # (1) joules_label is "sample" by default — never a fabricated measurement.
    assert out["joules_label"] == "sample", out["joules_label"]
    assert out["intake"]["joules_label"] == "sample", out["intake"]
    assert out["reservoir"]["joules_label"] == "sample", out["reservoir"]

    # (2) Ayni balances — reciprocal, never net-positive.
    assert out["ayni"]["balanced"] is True, out["ayni"]

    # (3) No "key" anywhere in the serialized output (no leaked secret key).
    blob = json.dumps(out).lower()
    assert "key" not in blob, "output must not contain any 'key'"

    # (4) Every organ carries "experimental" — organs are never claimed proven.
    assert out["organs"], "expected at least one organ"
    for organ in out["organs"]:
        assert "experimental" in organ["note"].lower(), organ
        assert "flowing" in organ and isinstance(organ["flowing"], bool)

    # Shape sanity: required top-level keys present and honest.
    assert out["kind"] == "anatomy-circulation-loop"
    assert out["ns"] == "a11oy"
    assert out["doctrine"] == "v11"
    assert "honesty" in out and isinstance(out["honesty"], str)
    assert isinstance(out["beats_last_cycle"], int)

    return out


# ---------------------------------------------------------------------------
# LATENCY regression guard — the #anatomy-loop-latency fix.
# ---------------------------------------------------------------------------
class _slow_gpu_probe:
    """Context manager: make the GPU-node-backed posture probe SLEEP then fail.

    Simulates the sleeping GPU / offline chaski node exactly as production hits it:
    the in-process harvest organ is absent, and each HTTP posture surface hangs for
    ~`hang_s` and then errors. With the OLD synchronous code this cost ~3s
    (three surfaces); the fix must abandon it sub-second via the breaker + short
    timeout. Also resets the shared intake breaker + cache so the measurement is
    clean and the change is isolated to the wrapped dependency call.
    """

    def __init__(self, hang_s: float = 1.5):
        self.hang_s = hang_s
        self._orig_urlopen = urllib.request.urlopen
        self._orig_inproc = loop._try_in_process_posture

    def __enter__(self):
        def _slow_urlopen(req, timeout=None, *a, **k):
            time.sleep(min(timeout if timeout is not None else self.hang_s, self.hang_s))
            raise TimeoutError("simulated sleeping GPU / offline chaski node")
        urllib.request.urlopen = _slow_urlopen
        loop._try_in_process_posture = lambda: None   # force the network path
        # Clean slate: a fresh breaker state + empty cache for a deterministic read.
        if loop._INTAKE_CACHE is not None:
            loop._INTAKE_CACHE.invalidate()
        if loop._INTAKE_BREAKER is not None:
            loop._INTAKE_BREAKER.reset()
        return self

    def __exit__(self, *exc):
        urllib.request.urlopen = self._orig_urlopen
        loop._try_in_process_posture = self._orig_inproc
        if loop._INTAKE_CACHE is not None:
            loop._INTAKE_CACHE.invalidate()
        if loop._INTAKE_BREAKER is not None:
            loop._INTAKE_BREAKER.reset()
        return False


def _assert_honest_degraded(out):
    """The shared honesty assertions for a degraded (sleeping-node) loop response."""
    # gpu node is honestly flagged sleeping/unreachable; intake marked degraded.
    assert out["intake"]["gpu_state"] in ("sleeping", "unreachable"), out["intake"]
    assert out["intake"]["degraded"] is True, out["intake"]
    assert out["intake"]["posture"] == "sample", out["intake"]
    # joules stay SAMPLE — NO fabricated measured value, evidence empty.
    assert out["joules_label"] == "sample", out["joules_label"]
    assert out["intake"]["joules_label"] == "sample", out["intake"]
    assert out.get("joules_evidence", {}) == {}, out.get("joules_evidence")
    assert out["intake"].get("joules_evidence", {}) == {}, out["intake"]
    # never wasted_energy_available off a dead feed; nothing invented.
    assert out["intake"]["wasted_energy_available"] is False, out["intake"]
    # the loop still produces a coherent, Ayni-balanced organ structure.
    assert out["ayni"]["balanced"] is True, out["ayni"]
    assert out["organs"], "expected organs even when degraded"
    for organ in out["organs"]:
        assert "experimental" in organ["note"].lower(), organ
    # no fabricated 'measured' label anywhere in the serialized body.
    assert "\"measured\"" not in json.dumps(out).replace("\"measured_any\"", ""), \
        "degraded posture must never claim 'measured'"


def test_loop_fast_when_gpu_probe_slow():
    """The loop returns in <1s when the GPU probe is sleeping (no ~3s dep-wait).

    With the old synchronous code, three 1.5s posture surfaces => ~3s+. The fix
    pays at most ONE short-timeout probe (~0.6s) then degrades honestly.
    """
    fn = test_register_wires_loop_route()
    with _slow_gpu_probe(hang_s=1.5):
        t0 = time.monotonic()
        out = _extract_body(fn(None))
        elapsed = time.monotonic() - t0
    # MUST be well under 1s — the whole point of the fix (was ~3-4.5s).
    assert elapsed < 1.0, f"loop took {elapsed:.3f}s with a sleeping node (target <1s)"
    _assert_honest_degraded(out)
    return elapsed


def test_loop_failfast_when_breaker_open():
    """After enough failures the breaker OPENs and the loop fail-fasts ~instantly.

    This is the DEEP fix beyond the short timeout: a SUSTAINED sleeping node stops
    costing ANY probe budget at all once the circuit breaker trips OPEN.
    """
    if loop._INTAKE_BREAKER is None:
        return None  # resilience helper absent; short-timeout path already covered
    fn = test_register_wires_loop_route()
    with _slow_gpu_probe(hang_s=1.5):
        # Drive failures past the breaker threshold so it trips OPEN.
        for _ in range(loop._INTAKE_BREAKER.failure_threshold + 2):
            _extract_body(fn(None))
        from szl_resilience import CircuitState
        assert loop._INTAKE_BREAKER.state is CircuitState.OPEN, \
            f"breaker should be OPEN, was {loop._INTAKE_BREAKER.state}"
        # Now a call must fail-fast: NO probe, NO timeout paid -> near-instant.
        t0 = time.monotonic()
        out = _extract_body(fn(None))
        elapsed = time.monotonic() - t0
    assert elapsed < 0.2, f"breaker-open call took {elapsed:.4f}s (should be ~instant)"
    _assert_honest_degraded(out)
    return elapsed


def test_loop_caches_real_posture_no_reprobe():
    """A successful posture is cached so a repeat call doesn't re-probe (honest cache).

    The cache only ever holds REAL probe output; a second call within TTL serves it
    without touching the network (and without inventing a 'measured' label).
    """
    if loop._INTAKE_CACHE is None:
        return None
    fn = test_register_wires_loop_route()
    calls = {"n": 0}
    real_posture = {"ok": True, "posture": "live", "wasted_energy_available": False,
                    "source": "test in-process posture"}

    orig_inproc = loop._try_in_process_posture
    loop._INTAKE_CACHE.invalidate()
    if loop._INTAKE_BREAKER is not None:
        loop._INTAKE_BREAKER.reset()

    def _counting_posture():
        calls["n"] += 1
        return dict(real_posture)
    try:
        loop._try_in_process_posture = _counting_posture
        out1 = _extract_body(fn(None))
        out2 = _extract_body(fn(None))   # within TTL -> served from cache, no re-probe
    finally:
        loop._try_in_process_posture = orig_inproc
        loop._INTAKE_CACHE.invalidate()

    assert calls["n"] == 1, f"expected ONE real probe, got {calls['n']} (cache should serve #2)"
    # live posture is honest too: joules still SAMPLE (no real exporter sample present).
    assert out1["joules_label"] == "sample" and out2["joules_label"] == "sample"
    assert out1["ayni"]["balanced"] is True and out2["ayni"]["balanced"] is True
    return calls["n"]


if __name__ == "__main__":
    result = test_loop_invariants()
    fast = test_loop_fast_when_gpu_probe_slow()
    failfast = test_loop_failfast_when_breaker_open()
    cached = test_loop_caches_real_posture_no_reprobe()
    print("PASS — anatomy loop self-test (incl. latency regression guard)")
    print(json.dumps({
        "latency_sleeping_node_s": round(fast, 4),
        "latency_breaker_open_s": round(failfast, 6) if failfast is not None else None,
        "real_probes_with_cache": cached,
    }, indent=2))
    print(json.dumps({
        "joules_label": result["joules_label"],
        "ayni_balanced": result["ayni"]["balanced"],
        "organs": [o["name"] for o in result["organs"]],
        "beats_last_cycle": result["beats_last_cycle"],
        "last_receipt_id": result["last_receipt_id"][:12] + "..." if result["last_receipt_id"] else "",
    }, indent=2))
