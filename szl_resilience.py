# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED: 749 declarations · 14 unique axioms · 163 sorries.
# Λ = Conjecture 1 (Λ-Aggregator Uniqueness; NOT a closed theorem).
"""
szl_resilience.py — SZL-native resilience layer: a Hystrix-style CIRCUIT BREAKER
around flaky outbound dependencies, plus a Kubernetes-style LIVENESS vs READINESS
probe split. ADDITIVE (register(app, ns="a11oy")); composes with — never rewrites —
the existing szl_backend_hardening probe helpers (#346) and prod hardening (#345).

PROVEN PATTERNS WE APPLY (engineering leaders' knowledge; OUR OWN implementation,
no foreign source copied — pure stdlib):

  1. CIRCUIT BREAKER — the Netflix / Hystrix pattern.
     Wrap every outbound call to a flaky dependency (the GPU nodes — chaski
     especially, and any external feed). Three states:
       • CLOSED      — calls pass through to the real dependency.
       • OPEN        — after N CONSECUTIVE failures the breaker trips; subsequent
                       calls FAIL FAST with a fallback for a cooldown window and do
                       NOT pay the expensive per-call timeout at all. This is the
                       DEEP fix beyond caching: when chaski is down the breaker
                       opens and the compute-pool stops paying the TCP timeout.
       • HALF_OPEN   — after the cooldown, a limited number of probe calls are let
                       through; a success closes the breaker (recovery), a failure
                       re-opens it for another cooldown window.
     Reference: Nygard, "Release It!" (Circuit Breaker / Stability Patterns);
     Netflix Hystrix (https://github.com/Netflix/Hystrix/wiki/How-it-Works).
     We re-implement the state machine ourselves; nothing from Hystrix is vendored.

  2. LIVENESS vs READINESS — the Kubernetes probe pattern.
       • /health/live  — "is the process alive?" A trivial 200 with NO dependency
                         logic. A liveness probe must never fail just because a
                         downstream dep is down, or the orchestrator would kill a
                         perfectly healthy process.
       • /health/ready — "should this instance receive traffic?" 200 ONLY if the
                         core dependencies are healthy (the dark-surface modules
                         registered AND the harvest reader responding AND no
                         critical breaker stuck OPEN); otherwise 503.
     A readiness 503 means "don't send traffic / don't mark this deploy good." This
     is the EXACT mechanism that STOPS the deploy flapping: a new image only becomes
     live (gets traffic, is marked good) after /health/ready returns 200, so a build
     whose core deps fail to come up is held back instead of flap-cycling.
     Reference: Kubernetes docs — Configure Liveness, Readiness and Startup Probes
     (https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/).

ROUTES REGISTERED (ADDITIVE — never replaces an existing route):
  GET /api/<ns>/v1/health/live    trivial 200 (process alive)         — namespaced
  GET /api/<ns>/v1/health/ready   200 if deps healthy else 503        — namespaced
  GET /health/live                trivial 200 (process alive)         — plain (k8s)
  GET /health/ready               200 if deps healthy else 503        — plain (k8s)
  GET /api/<ns>/v1/resilience     breaker registry snapshot (honest)  — observability

HONESTY / DOCTRINE v11 (binding, enforced by construction):
  • breaker state is REAL: every CLOSED→OPEN→HALF_OPEN→CLOSED transition reflects
    ACTUAL call outcomes (success/failure counts from real wrapped calls). Nothing
    is fabricated; an OPEN breaker is OPEN because real calls really failed.
  • readiness reflects REAL dependency checks (modules actually imported/registered,
    harvest reader actually responding); a down dep yields a real 503, never bluffed.
  • joules are MEASURED only via the on-box exporter — this module makes NO energy
    claim. sovereign is a property of owned metal, decided elsewhere, never here.
  • locked = 8; Λ = Conjecture 1 (OPEN, never a theorem, never "proven trust");
    no key committed. Pure Python stdlib (threading, time, enum, functools).

Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
"""
from __future__ import annotations

import functools
import sys
import threading
import time
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

# ---------------------------------------------------------------------------
# Doctrine echo — same shape the other szl_* surfaces emit so any response that
# reuses it stays honesty-clean under the doctrine guards.
# ---------------------------------------------------------------------------
DOCTRINE: Dict[str, Any] = {
    "version": "v11",
    "counts": "749/14/163",
    "locked": 8,
    "lambda": "Conjecture 1",          # OPEN — never a theorem, never "proven trust"
    "organs": "EXPERIMENTAL",
    "joules": "MEASURED only via on-box exporter; this module makes no energy claim",
    "free_energy": False,
    "sovereign": "only on own metal",
    "breaker_state": "real — reflects actual call outcomes, never fabricated",
    "readiness": "real dependency checks — 503 is honest, never bluffed green",
    "key_committed": False,
}

DEFAULT_FAILURE_THRESHOLD = 5     # consecutive failures before CLOSED -> OPEN
DEFAULT_COOLDOWN = 30.0           # seconds OPEN before a HALF_OPEN probe is allowed
DEFAULT_HALF_OPEN_MAX = 1         # concurrent probe calls allowed in HALF_OPEN


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stderr(msg: str) -> None:
    try:
        print(msg, file=sys.stderr)
    except Exception:
        pass


class CircuitState(str, Enum):
    CLOSED = "closed"        # calls pass through
    OPEN = "open"            # fail-fast with fallback, no expensive call
    HALF_OPEN = "half_open"  # limited probe calls to test recovery


class CircuitOpenError(RuntimeError):
    """Raised by a breaker call when OPEN and no fallback is supplied.

    Carries the breaker name so a caller can distinguish a fail-fast trip from a
    genuine downstream exception.
    """

    def __init__(self, name: str, retry_after: float) -> None:
        super().__init__(f"circuit '{name}' is OPEN; fail-fast (retry_after={retry_after:.1f}s)")
        self.name = name
        self.retry_after = retry_after


# ===========================================================================
# CircuitBreaker — the Hystrix state machine (CLOSED / OPEN / HALF_OPEN).
# ===========================================================================
class CircuitBreaker:
    """A thread-safe Hystrix-style circuit breaker.

    Configurable:
      • failure_threshold — N CONSECUTIVE failures in CLOSED trips it to OPEN.
      • cooldown          — seconds to stay OPEN before allowing a HALF_OPEN probe.
      • half_open_max     — how many probe calls may run concurrently in HALF_OPEN.

    State machine (exactly the Hystrix semantics, our own implementation):
      CLOSED:    calls pass; each failure increments a consecutive-failure counter;
                 a success resets it. On reaching `failure_threshold` -> OPEN.
      OPEN:      calls FAIL FAST (no real call, no timeout paid). After `cooldown`
                 has elapsed since the trip, the NEXT call transitions -> HALF_OPEN.
      HALF_OPEN: up to `half_open_max` probe calls run the real dependency. A success
                 closes the breaker (-> CLOSED, counters reset); any failure re-opens
                 it (-> OPEN, cooldown restarts).

    HONEST: every transition is driven by a REAL call outcome reported via
    record_success()/record_failure() (or the call()/wrap helpers). The breaker
    NEVER invents an outcome; an OPEN breaker is OPEN because calls really failed.

    `is_fallback` (the optional time/clock and lock are injectable for tests).
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = DEFAULT_FAILURE_THRESHOLD,
        cooldown: float = DEFAULT_COOLDOWN,
        half_open_max: int = DEFAULT_HALF_OPEN_MAX,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if failure_threshold < 1:
            raise ValueError("failure_threshold must be >= 1")
        if cooldown < 0:
            raise ValueError("cooldown must be >= 0")
        if half_open_max < 1:
            raise ValueError("half_open_max must be >= 1")
        self.name = name
        self.failure_threshold = int(failure_threshold)
        self.cooldown = float(cooldown)
        self.half_open_max = int(half_open_max)
        self._clock = clock

        self._lock = threading.RLock()
        self._state = CircuitState.CLOSED
        self._consecutive_failures = 0
        self._opened_at: Optional[float] = None
        self._half_open_inflight = 0
        # honest lifetime counters (never reset on transition; for observability)
        self._total_calls = 0
        self._total_successes = 0
        self._total_failures = 0
        self._total_fast_failed = 0   # calls rejected fast while OPEN (no real call)
        self._last_change_iso = _now_iso()
        self._last_outcome: Optional[str] = None

    # --- introspection -----------------------------------------------------
    @property
    def state(self) -> CircuitState:
        """Current state, advancing OPEN -> HALF_OPEN lazily if cooldown elapsed.

        Reading the state is side-effecting ONLY for the OPEN->HALF_OPEN cooldown
        transition (the canonical breaker behaviour: the cooldown is checked on the
        next access/call, there is no background timer).
        """
        with self._lock:
            self._maybe_half_open_locked()
            return self._state

    def _maybe_half_open_locked(self) -> None:
        if self._state is CircuitState.OPEN and self._opened_at is not None:
            if (self._clock() - self._opened_at) >= self.cooldown:
                self._transition_locked(CircuitState.HALF_OPEN)
                self._half_open_inflight = 0

    def _transition_locked(self, new: CircuitState) -> None:
        if new is not self._state:
            self._state = new
            self._last_change_iso = _now_iso()

    # --- gate: may a call proceed right now? -------------------------------
    def allow_request(self) -> bool:
        """Return True if a real call may proceed; advances OPEN->HALF_OPEN on cooldown.

        In HALF_OPEN, only up to `half_open_max` probe calls are admitted; extra
        callers are rejected (treated like OPEN) so a flood doesn't hammer a
        still-sick dependency.
        """
        with self._lock:
            self._maybe_half_open_locked()
            if self._state is CircuitState.CLOSED:
                return True
            if self._state is CircuitState.OPEN:
                return False
            # HALF_OPEN: admit a bounded number of probe calls.
            if self._half_open_inflight < self.half_open_max:
                self._half_open_inflight += 1
                return True
            return False

    def retry_after(self) -> float:
        """Seconds remaining before an OPEN breaker will allow a probe (>=0)."""
        with self._lock:
            if self._state is CircuitState.OPEN and self._opened_at is not None:
                return max(0.0, self.cooldown - (self._clock() - self._opened_at))
            return 0.0

    # --- outcome reporting (drives all transitions; REAL outcomes only) ----
    def record_success(self) -> None:
        with self._lock:
            self._total_successes += 1
            self._last_outcome = "success"
            if self._state is CircuitState.HALF_OPEN:
                # Recovery confirmed by a real successful probe -> close.
                self._half_open_inflight = max(0, self._half_open_inflight - 1)
                self._consecutive_failures = 0
                self._opened_at = None
                self._transition_locked(CircuitState.CLOSED)
            else:
                self._consecutive_failures = 0

    def record_failure(self) -> None:
        with self._lock:
            self._total_failures += 1
            self._last_outcome = "failure"
            if self._state is CircuitState.HALF_OPEN:
                # Probe failed — dependency still sick. Re-open, restart cooldown.
                self._half_open_inflight = max(0, self._half_open_inflight - 1)
                self._opened_at = self._clock()
                self._transition_locked(CircuitState.OPEN)
                return
            self._consecutive_failures += 1
            if (self._state is CircuitState.CLOSED
                    and self._consecutive_failures >= self.failure_threshold):
                self._opened_at = self._clock()
                self._transition_locked(CircuitState.OPEN)

    # --- the wrapped call ---------------------------------------------------
    def call(
        self,
        fn: Callable[..., Any],
        *args: Any,
        fallback: Optional[Callable[..., Any]] = None,
        **kwargs: Any,
    ) -> Any:
        """Invoke `fn` through the breaker.

        CLOSED / admitted HALF_OPEN probe: run `fn`; a return records success, an
        exception records failure and is re-raised (after the fallback, if any).
        OPEN / not-admitted HALF_OPEN: FAIL FAST — `fn` is NOT called at all (the
        whole point: no expensive timeout paid). If `fallback` is given it is called
        and its value returned; otherwise CircuitOpenError is raised.
        """
        with self._lock:
            self._total_calls += 1
        if not self.allow_request():
            with self._lock:
                self._total_fast_failed += 1
            if fallback is not None:
                return fallback(*args, **kwargs)
            raise CircuitOpenError(self.name, self.retry_after())
        try:
            result = fn(*args, **kwargs)
        except Exception:
            self.record_failure()
            if fallback is not None:
                return fallback(*args, **kwargs)
            raise
        else:
            self.record_success()
            return result

    def snapshot(self) -> Dict[str, Any]:
        """Honest observability snapshot of the breaker (no side effects beyond
        the lazy OPEN->HALF_OPEN cooldown advance that `state` performs)."""
        with self._lock:
            self._maybe_half_open_locked()
            return {
                "name": self.name,
                "state": self._state.value,
                "consecutive_failures": self._consecutive_failures,
                "failure_threshold": self.failure_threshold,
                "cooldown_s": self.cooldown,
                "half_open_max": self.half_open_max,
                "retry_after_s": round(self.retry_after(), 3),
                "totals": {
                    "calls": self._total_calls,
                    "successes": self._total_successes,
                    "failures": self._total_failures,
                    "fast_failed_open": self._total_fast_failed,
                },
                "last_outcome": self._last_outcome,
                "last_state_change": self._last_change_iso,
                "honesty": "state reflects real call outcomes only; never fabricated",
            }

    def reset(self) -> None:
        """Force the breaker back to CLOSED (operator action; counters preserved)."""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._consecutive_failures = 0
            self._opened_at = None
            self._half_open_inflight = 0
            self._last_change_iso = _now_iso()


# ===========================================================================
# Breaker registry — one named breaker per dependency, shared across requests.
# ===========================================================================
class BreakerRegistry:
    """Thread-safe registry of named CircuitBreakers (one per dependency)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._breakers: Dict[str, CircuitBreaker] = {}

    def get_or_create(
        self,
        name: str,
        failure_threshold: int = DEFAULT_FAILURE_THRESHOLD,
        cooldown: float = DEFAULT_COOLDOWN,
        half_open_max: int = DEFAULT_HALF_OPEN_MAX,
    ) -> CircuitBreaker:
        with self._lock:
            cb = self._breakers.get(name)
            if cb is None:
                cb = CircuitBreaker(name, failure_threshold, cooldown, half_open_max)
                self._breakers[name] = cb
            return cb

    def get(self, name: str) -> Optional[CircuitBreaker]:
        with self._lock:
            return self._breakers.get(name)

    def all(self) -> List[CircuitBreaker]:
        with self._lock:
            return list(self._breakers.values())

    def snapshot(self) -> Dict[str, Any]:
        return {cb.name: cb.snapshot() for cb in self.all()}


# Process-wide default registry (shared by the decorator and the routes).
REGISTRY = BreakerRegistry()


def circuit(
    name: str,
    failure_threshold: int = DEFAULT_FAILURE_THRESHOLD,
    cooldown: float = DEFAULT_COOLDOWN,
    half_open_max: int = DEFAULT_HALF_OPEN_MAX,
    fallback: Optional[Callable[..., Any]] = None,
    registry: Optional[BreakerRegistry] = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator: protect a callable with a named CircuitBreaker.

    Usage:
        @circuit("chaski", failure_threshold=3, cooldown=20, fallback=lambda *a, **k: DEGRADED)
        def probe_chaski(): ...

    The breaker is created once in the registry and shared across calls, so its
    state persists across invocations (the whole point — repeated failures trip it).
    The wrapped function exposes `.breaker` for introspection.
    """
    reg = registry if registry is not None else REGISTRY

    def _decorate(fn: Callable[..., Any]) -> Callable[..., Any]:
        cb = reg.get_or_create(name, failure_threshold, cooldown, half_open_max)

        @functools.wraps(fn)
        def _wrapped(*args: Any, **kwargs: Any) -> Any:
            return cb.call(fn, *args, fallback=fallback, **kwargs)

        _wrapped.breaker = cb  # type: ignore[attr-defined]
        return _wrapped

    return _decorate


# ===========================================================================
# Breaker-protected fabric probe — composes with szl_backend_hardening (#346).
# We DO NOT rewrite the prober; we import probe_fabric_pool and wrap it so that
# when chaski (and friends) are down and the breaker trips, the compute-pool
# fail-fasts to the LAST cached snapshot instead of paying the probe cost again.
# ===========================================================================
# A dedicated breaker for the fabric sweep. Threshold is small + cooldown short so
# it trips quickly when the fabric prober itself starts failing, then recovers.
FABRIC_BREAKER = REGISTRY.get_or_create(
    "fabric-probe", failure_threshold=3, cooldown=20.0, half_open_max=1
)


def protected_probe_fabric_pool(**kwargs: Any) -> Dict[str, Any]:
    """Breaker-wrapped fabric probe.

    Calls szl_backend_hardening.probe_fabric_pool through FABRIC_BREAKER. When the
    breaker is OPEN it FAILS FAST to the last cached fabric snapshot (peeked from
    the hardening TTL cache) WITHOUT re-probing — so a sustained fabric outage stops
    costing the per-node timeout entirely. Honest: the fallback is clearly labelled
    `breaker_open=True` and serves only REAL prior probe data (or an explicit
    "no prior snapshot" envelope), never fabricated reachability.
    """
    import szl_backend_hardening as bh  # local import keeps this module import-safe

    def _fallback(**_kw: Any) -> Dict[str, Any]:
        cached = None
        try:
            cached = bh._FABRIC_CACHE.peek()  # last REAL snapshot, if any is still held
        except Exception:
            cached = None
        if isinstance(cached, dict):
            out = dict(cached)
            out["breaker_open"] = True
            out["breaker_note"] = (
                "fabric-probe breaker OPEN: failing fast to last REAL cached snapshot; "
                "not re-probing dead nodes (no timeout paid). Reachability is from the "
                "prior real sweep at cached_at; nothing fabricated."
            )
            return out
        return {
            "status": "degraded",
            "breaker_open": True,
            "breaker_note": (
                "fabric-probe breaker OPEN and no prior real snapshot available; "
                "failing fast without probing. No reachability fabricated."
            ),
            "doctrine": dict(DOCTRINE),
        }

    return FABRIC_BREAKER.call(bh.probe_fabric_pool, fallback=_fallback, **kwargs)


# ===========================================================================
# Readiness dependency checks — REAL checks; a down dep yields a real 503.
# ===========================================================================
def _check_dark_surfaces_registered() -> Dict[str, Any]:
    """Core dep: the dark-surface aggregator module imports (its surfaces register)."""
    try:
        import szl_dark_surfaces_register  # noqa: F401
        return {"ok": True, "detail": "szl_dark_surfaces_register importable"}
    except Exception as exc:  # honest: a real import failure is a real not-ready
        return {"ok": False, "detail": f"dark-surface aggregator import failed: {exc!r}"}


def _check_harvest_reader() -> Dict[str, Any]:
    """Core dep: the harvest reader is importable AND responds (real posture call)."""
    try:
        import a11oy_harvest_endpoints as he
        if not getattr(he, "_HARVEST_OK", False):
            return {"ok": False,
                    "detail": f"harvest not importable: {getattr(he, '_HARVEST_IMPORT_ERR', 'unknown')}"}
        # A real call: handle_posture() returns ok=True only if the reader responds.
        posture = he.handle_posture()
        ok = bool(posture.get("ok"))
        return {"ok": ok, "detail": "harvest reader responding" if ok
                else f"harvest reader degraded: {posture.get('error', 'unknown')}"}
    except Exception as exc:
        return {"ok": False, "detail": f"harvest reader check failed: {exc!r}"}


def _check_no_critical_breaker_open() -> Dict[str, Any]:
    """Core dep: no critical breaker is stuck OPEN (a wedged dep = not ready)."""
    open_breakers = [cb.name for cb in REGISTRY.all() if cb.state is CircuitState.OPEN]
    if open_breakers:
        return {"ok": False, "detail": f"breaker(s) OPEN: {', '.join(open_breakers)}"}
    return {"ok": True, "detail": "no breaker stuck OPEN"}


# The readiness check table. Each entry is (name, check_callable). A check is a
# zero-arg callable returning {"ok": bool, "detail": str}. Overridable for tests.
def default_readiness_checks() -> "Dict[str, Callable[[], Dict[str, Any]]]":
    return {
        "dark_surfaces": _check_dark_surfaces_registered,
        "harvest_reader": _check_harvest_reader,
        "breakers": _check_no_critical_breaker_open,
    }


def evaluate_readiness(
    checks: "Optional[Dict[str, Callable[[], Dict[str, Any]]]]" = None,
) -> Dict[str, Any]:
    """Run every readiness check and return an honest aggregate.

    ready=True iff EVERY core dependency check returns ok=True. Each check is run
    inside its own try/except so one crashing check can't crash readiness (it is
    reported as not-ok with the exception — still an honest 'not ready').
    """
    use = checks if checks is not None else default_readiness_checks()
    results: Dict[str, Any] = {}
    ready = True
    for name, fn in use.items():
        try:
            r = fn()
            ok = bool(r.get("ok"))
            results[name] = {"ok": ok, "detail": r.get("detail", "")}
        except Exception as exc:
            ok = False
            results[name] = {"ok": False, "detail": f"check raised: {exc!r}"}
        ready = ready and ok
    return {
        "ready": ready,
        "checks": results,
        "checked_at": _now_iso(),
        "honesty": (
            "ready=True only if EVERY core dependency check really passed; a down "
            "dep yields ready=False -> HTTP 503 (don't send traffic / don't mark "
            "this deploy good). Never bluffed green."
        ),
        "doctrine": dict(DOCTRINE),
    }


# ===========================================================================
# serve.py wiring — ADDITIVE, try/except-guarded. Liveness/readiness split.
# ===========================================================================
def register(
    app: Any,
    ns: str = "a11oy",
    readiness_checks: "Optional[Dict[str, Callable[[], Dict[str, Any]]]]" = None,
) -> List[str]:
    """ADDITIVE: attach the liveness/readiness routes + breaker observability route.

    Never replaces an existing route (uses add_api_route only if the path is free).
    Returns the list of route paths actually attached.

    Routes:
      GET /api/<ns>/v1/health/live    trivial 200 (process alive, NO dep logic)
      GET /api/<ns>/v1/health/ready   200 if core deps healthy else 503
      GET /health/live                plain k8s-style liveness alias (trivial 200)
      GET /health/ready               plain k8s-style readiness alias (200/503)
      GET /api/<ns>/v1/resilience     breaker registry snapshot (honest state)
    """
    paths: List[str] = []
    try:
        from fastapi.responses import JSONResponse
    except Exception:
        _stderr("[a11oy:resilience] fastapi not available; skipping route registration")
        return paths

    existing = {getattr(r, "path", None)
                for r in getattr(getattr(app, "router", None), "routes", [])}

    def _add(path: str, handler: Callable[..., Any]) -> None:
        if path in existing:
            _stderr(f"[a11oy:resilience] route present; skipped: {path}")
            return
        app.add_api_route(path, handler, methods=["GET"], include_in_schema=False)
        existing.add(path)
        paths.append(path)

    # --- LIVENESS: trivial 200, NO dependency logic (k8s liveness contract) ---
    async def _live():  # noqa: ANN202
        # Deliberately trivial: if the event loop can serve this, the process is
        # alive. A liveness probe must NOT consult dependencies, or a downstream
        # outage would get a healthy process killed.
        return JSONResponse({
            "live": True,
            "status": "alive",
            "ns": ns,
            "ts": _now_iso(),
            "note": "liveness is process-only; no dependency logic by design",
        }, status_code=200)

    # --- READINESS: 200 only if core deps healthy, else 503 (k8s readiness) ---
    async def _ready():  # noqa: ANN202
        payload = evaluate_readiness(readiness_checks)
        code = 200 if payload["ready"] else 503
        payload = {**payload, "ns": ns, "status": "ready" if payload["ready"] else "not_ready"}
        return JSONResponse(payload, status_code=code)

    # --- breaker observability (honest snapshot of every breaker) ---
    async def _resilience():  # noqa: ANN202
        return JSONResponse({
            "ns": ns,
            "breakers": REGISTRY.snapshot(),
            "ts": _now_iso(),
            "patterns": {
                "circuit_breaker": "Hystrix-style CLOSED/OPEN/HALF_OPEN (our impl)",
                "liveness_readiness": "Kubernetes-style probe split (our impl)",
            },
            "doctrine": dict(DOCTRINE),
        }, status_code=200)

    _add(f"/api/{ns}/v1/health/live", _live)
    _add(f"/api/{ns}/v1/health/ready", _ready)
    _add("/health/live", _live)
    _add("/health/ready", _ready)
    _add(f"/api/{ns}/v1/resilience", _resilience)

    _stderr(f"[a11oy:resilience] liveness/readiness + breaker routes registered: {paths}")
    return paths


# ===========================================================================
# Self-test — pure stdlib, OFFLINE. No network, no FastAPI required.
# ===========================================================================
def _selftest() -> Dict[str, Any]:
    checks: List = []

    def chk(name: str, cond: bool) -> None:
        checks.append((name, bool(cond)))

    # A controllable fake clock so cooldown is deterministic (no sleeps).
    class _Clock:
        def __init__(self) -> None:
            self.t = 1000.0
        def __call__(self) -> float:
            return self.t
        def advance(self, dt: float) -> None:
            self.t += dt

    clk = _Clock()
    cb = CircuitBreaker("t", failure_threshold=3, cooldown=10.0, half_open_max=1, clock=clk)

    # CLOSED initially, calls allowed.
    chk("starts_closed", cb.state is CircuitState.CLOSED)
    chk("closed_allows", cb.allow_request() is True)

    # Opens after exactly `threshold` consecutive failures.
    for _ in range(3):
        cb.record_failure()
    chk("opens_after_threshold", cb.state is CircuitState.OPEN)
    chk("open_fast_fails", cb.allow_request() is False)

    # Before cooldown elapses, still OPEN / fail-fast.
    clk.advance(5.0)
    chk("still_open_before_cooldown", cb.state is CircuitState.OPEN)

    # After cooldown, advances to HALF_OPEN and admits ONE probe.
    clk.advance(6.0)  # total 11 > cooldown 10
    chk("half_open_after_cooldown", cb.state is CircuitState.HALF_OPEN)
    chk("half_open_admits_one", cb.allow_request() is True)
    chk("half_open_rejects_second", cb.allow_request() is False)

    # A success in HALF_OPEN closes the breaker.
    cb.record_success()
    chk("closes_on_success", cb.state is CircuitState.CLOSED)

    # call() fail-fast: when OPEN, fn is NOT invoked.
    cb2 = CircuitBreaker("t2", failure_threshold=1, cooldown=10.0, clock=clk)
    cb2.record_failure()  # threshold 1 -> immediately OPEN
    called = {"n": 0}
    def _expensive():
        called["n"] += 1
        return "ran"
    out = cb2.call(_expensive, fallback=lambda: "fallback")
    chk("open_uses_fallback", out == "fallback")
    chk("open_did_not_call", called["n"] == 0)

    # readiness: all-up -> ready True; one down -> ready False.
    up = evaluate_readiness({"a": lambda: {"ok": True, "detail": "x"},
                             "b": lambda: {"ok": True, "detail": "y"}})
    chk("ready_all_up", up["ready"] is True)
    down = evaluate_readiness({"a": lambda: {"ok": True}, "b": lambda: {"ok": False}})
    chk("not_ready_one_down", down["ready"] is False)

    ok = all(p for _, p in checks)
    return {"ok": ok, "checks": len(checks),
            "failed": [n for n, p in checks if not p], "doctrine": dict(DOCTRINE)}


if __name__ == "__main__":
    import json
    print(json.dumps(_selftest(), indent=2))
