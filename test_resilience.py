# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
"""test_resilience — the SZL resilience layer is correct AND honest.

Runs fully OFFLINE (controllable fake clock; no sleeps, no network). Asserts:

  CIRCUIT BREAKER (Hystrix state machine):
    1. opens after exactly `failure_threshold` CONSECUTIVE failures (CLOSED->OPEN).
    2. when OPEN, fails fast — the wrapped fn is NOT called at all (no timeout paid);
       a fallback is used if supplied, else CircuitOpenError is raised.
    3. half-opens after the cooldown window (OPEN->HALF_OPEN), admitting one probe.
    4. closes on a successful probe (HALF_OPEN->CLOSED); a failed probe re-opens it.
    5. a success in CLOSED resets the consecutive-failure counter (no premature trip).
    6. breaker state is REAL — every transition is driven by recorded call outcomes.

  LIVENESS vs READINESS (Kubernetes probe split):
    7. /health/live (and /api/<ns>/v1/health/live) returns 200 TRIVIALLY, regardless
       of dependency health (process-only liveness contract).
    8. /health/ready (and namespaced) returns 503 when a mocked core dep is DOWN and
       200 when every dep is UP — the gate that stops deploy flapping.

Run: python3 test_resilience.py   (or: pytest test_resilience.py)
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import szl_resilience as R  # noqa: E402


# ---------------------------------------------------------------------------
# A controllable fake clock so cooldown transitions are deterministic (no sleep).
# ---------------------------------------------------------------------------
class _Clock:
    def __init__(self, t0: float = 1000.0) -> None:
        self.t = t0

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


# ===========================================================================
# CIRCUIT BREAKER
# ===========================================================================
def test_breaker_opens_after_threshold():
    clk = _Clock()
    cb = R.CircuitBreaker("dep", failure_threshold=4, cooldown=30.0, clock=clk)
    assert cb.state is R.CircuitState.CLOSED
    for i in range(3):
        cb.record_failure()
        assert cb.state is R.CircuitState.CLOSED, f"tripped early at failure {i+1}"
    cb.record_failure()  # 4th consecutive -> trip
    assert cb.state is R.CircuitState.OPEN, "did not open at threshold"


def test_breaker_success_resets_counter():
    clk = _Clock()
    cb = R.CircuitBreaker("dep", failure_threshold=3, cooldown=30.0, clock=clk)
    cb.record_failure()
    cb.record_failure()
    cb.record_success()           # resets consecutive count
    cb.record_failure()
    cb.record_failure()
    assert cb.state is R.CircuitState.CLOSED, "counter not reset by success"
    cb.record_failure()           # now 3 in a row -> open
    assert cb.state is R.CircuitState.OPEN


def test_breaker_fails_fast_when_open_no_call_made():
    clk = _Clock()
    cb = R.CircuitBreaker("dep", failure_threshold=1, cooldown=30.0, clock=clk)
    cb.record_failure()           # threshold 1 -> immediately OPEN
    assert cb.state is R.CircuitState.OPEN

    called = {"n": 0}

    def expensive():
        called["n"] += 1          # would pay a real timeout in production
        return "ran"

    # With a fallback: fallback value returned, fn NEVER invoked.
    out = cb.call(expensive, fallback=lambda: "fallback")
    assert out == "fallback", "did not use fallback while OPEN"
    assert called["n"] == 0, "expensive fn was called while OPEN (no fail-fast!)"

    # Without a fallback: CircuitOpenError, still no call.
    raised = False
    try:
        cb.call(expensive)
    except R.CircuitOpenError as exc:
        raised = True
        assert exc.name == "dep"
    assert raised, "CircuitOpenError not raised when OPEN and no fallback"
    assert called["n"] == 0, "expensive fn called while OPEN without fallback"


def test_breaker_half_opens_after_cooldown():
    clk = _Clock()
    cb = R.CircuitBreaker("dep", failure_threshold=1, cooldown=10.0,
                          half_open_max=1, clock=clk)
    cb.record_failure()
    assert cb.state is R.CircuitState.OPEN

    clk.advance(9.0)              # cooldown not yet elapsed
    assert cb.state is R.CircuitState.OPEN
    assert cb.allow_request() is False, "admitted a call before cooldown elapsed"

    clk.advance(2.0)              # total 11 > cooldown 10
    assert cb.state is R.CircuitState.HALF_OPEN, "did not half-open after cooldown"
    assert cb.allow_request() is True, "half-open did not admit a probe"
    assert cb.allow_request() is False, "half-open admitted more than half_open_max"


def test_breaker_closes_on_success_reopens_on_failure():
    clk = _Clock()
    cb = R.CircuitBreaker("dep", failure_threshold=1, cooldown=10.0, clock=clk)

    # trip -> open -> cooldown -> half-open -> success -> closed
    cb.record_failure()
    clk.advance(11.0)
    assert cb.state is R.CircuitState.HALF_OPEN
    assert cb.allow_request() is True
    cb.record_success()
    assert cb.state is R.CircuitState.CLOSED, "did not close on a successful probe"

    # trip again -> half-open -> failed probe -> re-open
    cb.record_failure()
    assert cb.state is R.CircuitState.OPEN
    clk.advance(11.0)
    assert cb.state is R.CircuitState.HALF_OPEN
    assert cb.allow_request() is True
    cb.record_failure()
    assert cb.state is R.CircuitState.OPEN, "failed probe did not re-open the breaker"


def test_breaker_call_drives_state_real_outcomes():
    """End-to-end through call(): real failures trip it, real success recovers it."""
    clk = _Clock()
    reg = R.BreakerRegistry()
    cb = reg.get_or_create("flaky", failure_threshold=3, cooldown=10.0)
    cb._clock = clk  # inject deterministic clock

    flip = {"fail": True}

    def dep():
        if flip["fail"]:
            raise RuntimeError("dep down")
        return "ok"

    # 3 real failures via call() -> OPEN (each call records a real failure).
    for _ in range(3):
        try:
            cb.call(dep)
        except RuntimeError:
            pass
    assert cb.state is R.CircuitState.OPEN

    snap = cb.snapshot()
    assert snap["state"] == "open"
    assert snap["totals"]["failures"] == 3, "failure count not real"

    # cooldown -> half-open; dependency recovers; success closes it.
    clk.advance(11.0)
    flip["fail"] = False
    out = cb.call(dep)
    assert out == "ok"
    assert cb.state is R.CircuitState.CLOSED, "real success did not close breaker"


def test_circuit_decorator_shares_breaker_state():
    reg = R.BreakerRegistry()

    @R.circuit("svc", failure_threshold=2, cooldown=30.0,
               fallback=lambda *a, **k: "FALLBACK", registry=reg)
    def call_svc(fail: bool):
        if fail:
            raise RuntimeError("boom")
        return "OK"

    assert call_svc(False) == "OK"
    # two real failures trip the shared breaker
    call_svc(True)
    call_svc(True)
    assert call_svc.breaker.state is R.CircuitState.OPEN
    # now fail-fast to fallback even with fail=False (fn not called while OPEN)
    assert call_svc(False) == "FALLBACK"


# ===========================================================================
# LIVENESS vs READINESS  (FastAPI TestClient, offline)
# ===========================================================================
def _make_client(readiness_checks):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    app = FastAPI()
    R.register(app, ns="a11oy", readiness_checks=readiness_checks)
    return TestClient(app)


def test_liveness_trivial_200_regardless_of_deps():
    # Even with a DOWN dependency, liveness must still be a trivial 200.
    client = _make_client({"x": lambda: {"ok": False, "detail": "down"}})
    for path in ("/health/live", "/api/a11oy/v1/health/live"):
        resp = client.get(path)
        assert resp.status_code == 200, f"{path} liveness not 200"
        body = resp.json()
        assert body["live"] is True
        assert body["status"] == "alive"


def test_readiness_503_when_dep_down():
    client = _make_client({
        "dark_surfaces": lambda: {"ok": True, "detail": "up"},
        "harvest_reader": lambda: {"ok": False, "detail": "harvest reader down (mocked)"},
    })
    for path in ("/health/ready", "/api/a11oy/v1/health/ready"):
        resp = client.get(path)
        assert resp.status_code == 503, f"{path} should be 503 when a dep is down"
        body = resp.json()
        assert body["ready"] is False
        assert body["checks"]["harvest_reader"]["ok"] is False


def test_readiness_200_when_all_deps_up():
    client = _make_client({
        "dark_surfaces": lambda: {"ok": True, "detail": "up"},
        "harvest_reader": lambda: {"ok": True, "detail": "responding"},
        "breakers": lambda: {"ok": True, "detail": "none open"},
    })
    for path in ("/health/ready", "/api/a11oy/v1/health/ready"):
        resp = client.get(path)
        assert resp.status_code == 200, f"{path} should be 200 when all deps up"
        body = resp.json()
        assert body["ready"] is True
        assert all(c["ok"] for c in body["checks"].values())


def test_readiness_check_crash_is_honest_not_ready():
    def _boom():
        raise RuntimeError("check exploded")
    client = _make_client({"boom": _boom, "ok": lambda: {"ok": True}})
    resp = client.get("/health/ready")
    assert resp.status_code == 503, "a crashing check must yield 503, not a 500"
    assert resp.json()["checks"]["boom"]["ok"] is False


# ---------------------------------------------------------------------------
# Minimal runner (mirrors test_backend_hardening.py style).
# ---------------------------------------------------------------------------
def _run_all() -> int:
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    failed = []
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
        except AssertionError as exc:
            failed.append((t.__name__, repr(exc)))
            print(f"  FAIL  {t.__name__}: {exc!r}")
        except Exception as exc:
            failed.append((t.__name__, repr(exc)))
            print(f"  ERROR {t.__name__}: {exc!r}")
    print(f"\n{len(tests) - len(failed)}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_run_all())
