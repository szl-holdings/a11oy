# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED: 749 declarations · 14 unique axioms · 163 sorries.
# Λ = Conjecture 1 (Λ-Aggregator Uniqueness; NOT a closed theorem).
"""
szl_observability.py — SZL-native DISTRIBUTED TRACING / observability layer.

ONE additive module, wired onto an existing FastAPI ``app`` via
``register(app, ns="a11oy")``. It NEVER replaces an existing route, NEVER edits
another module, and every tracing path is wrapped so a failure inside it can
never take a request down: tracing FAILS OPEN (any internal error in the tracer
is swallowed; the real request/response is untouched). This matches the
per-organ ``register(app, ns=...)`` discipline already used across the fleet
(see szl_prod_hardening.py #345, szl_backend_hardening.py #346, szl_resilience.py).

WHY (the ONE high-value resilience pattern the engineering leaders have that we
still lack: DISTRIBUTED TRACING — the OpenTelemetry model). The estate already
has request-id + structured access log (prod-hardening), concurrent+cached+
timeout probes (backend-hardening) and a circuit breaker + liveness/readiness
(resilience in-flight). What is STILL missing is the ability to SEE, for a
single slow request, WHICH node / probe / feed ate the time. When
GET /api/a11oy/v1/compute-pool took ~7s, the access log told us the request was
slow but NOT where the time went. Distributed tracing answers exactly that: a
single request produces a SPAN TREE, e.g.

    compute-pool  (7.01s)
      ├─ span betterwithage   1.40s  OK
      ├─ span chaski          1.50s  TIMEOUT   <-- the unreachable tailnet GPU
      └─ span groq            0.20s  OK

The fan-out is concurrent so wall time ≈ max(child), but the per-node spans make
the slow / timing-out node obvious at a glance — that is what reveals where the
7s goes and which node to fix (or trip a breaker on).

PROVEN PATTERN WE APPLY (engineering leaders' knowledge; OUR OWN lightweight
implementation — pure stdlib, NO heavy otel SDK dependency added):

  • OpenTelemetry tracing model — a Trace is a tree of Spans; each Span has a
    name, start time, duration, status, and attributes; context is propagated
    so child spans attach to the active parent automatically.
    Reference: OpenTelemetry — Traces (https://opentelemetry.io/docs/concepts/signals/traces/).
    We re-implement a MINIMAL COMPATIBLE SHAPE (trace_id / span_id / parent /
    attributes / status) ourselves with contextvars; nothing from the otel SDK
    is vendored or imported. trace_id REUSES the X-Request-ID minted by
    prod-hardening when present, so a trace correlates 1:1 with the access log.

  • RED metrics / SLO summary — Rate, Errors, Duration per surface, with p50/p95
    latency, computed from the trace ring buffer (the at-a-glance SLO view the
    leaders keep on a wall). Reference: Tom Wilkie, "The RED Method".

ROUTES REGISTERED (ADDITIVE — never replaces an existing route):
  GET /api/<ns>/v1/observability/traces           recent traces, slowest-first
  GET /api/<ns>/v1/observability/trace/{trace_id} one trace's full span tree
  GET /api/<ns>/v1/observability/health-summary   per-surface p50/p95 + error rate

HONESTY / DOCTRINE v11 (binding, enforced by construction):
  • durations are REAL MEASURED wall time (time.perf_counter); NEVER fabricated,
    never a placeholder. A span with no recorded end is reported as such, not
    invented.
  • NO secrets, NO request/response bodies, NO query strings, NO header values
    go into span attributes. Attribute values are sanitized (scalars only, length-
    bounded, key-name-screened) so a credential cannot leak into a trace.
  • memory is BOUNDED: a ring buffer (collections.deque(maxlen=N)) holds only the
    last ~200 traces; oldest are dropped. No unbounded growth.
  • joules MEASURED only via the on-box exporter — this module makes NO energy
    claim. sovereign is a property of owned metal, decided elsewhere, never here.
  • locked = 8; Λ = Conjecture 1 (OPEN, never a theorem, never "proven trust");
    no key committed. Pure Python stdlib (time, contextvars, collections.deque,
    threading.Lock, uuid).

Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
"""
# ---------------------------------------------------------------------------
# DEVELOPER ORIENTATION
# Purpose:       SZL-native distributed tracing (OpenTelemetry-style) so a single
#                slow request shows WHICH node/probe/feed ate the time. One call:
#                register(app, ns="a11oy") wires routes additively + fail-open.
# Key entry pts: start_trace(name, trace_id=None) -> Trace (context-bound)
#                span("name", **attrs)            -> context manager, real timing
#                current_trace() / current_span() -> the active ones (or None)
#                TRACES (ring buffer) + health_summary()/recent_traces()
# Doctrine note: tracing FAILS OPEN — never raises into the wrapped code. Real
#                measured durations only. No secret/body in attributes. Bounded
#                memory. Stdlib only; NO otel SDK dependency.
# ---------------------------------------------------------------------------
from __future__ import annotations

import contextvars
import os
import re
import sys
import threading
import time
import uuid
from collections import deque
from datetime import datetime, timezone
from typing import Any, Deque, Dict, List, Optional

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
    "durations": "REAL measured wall time only; never fabricated",
    "attributes": "no secrets, no bodies, no query strings, no private addresses — sanitized scalars only",
    "memory": "bounded ring buffer (deque maxlen); oldest traces dropped",
    "key_committed": False,
}

# Default ring-buffer capacity (env-overridable). ~200 traces is plenty for an
# at-a-glance SLO view while staying tiny in memory.
DEFAULT_RING_CAPACITY = 200
# Cap on number of spans retained per trace (defends against a pathological
# fan-out / loop producing unbounded spans in one request).
MAX_SPANS_PER_TRACE = 512
# Attribute hardening bounds.
_MAX_ATTR_KEYS = 24
_MAX_ATTR_STR_LEN = 256

# Substrings that, if present in an attribute KEY (case-insensitive), cause the
# value to be REDACTED. Defense-in-depth so a careless caller cannot leak a
# credential into a trace even by accident. (We still never auto-capture bodies.)
_SECRET_KEY_HINTS = (
    "secret", "token", "password", "passwd", "apikey", "api_key", "api-key",
    "authorization", "auth", "cookie", "session", "key", "credential", "cred",
    "private", "bearer", "signature", "sign", "salt", "hash", "pin", "otp",
    # Request/response payloads are NEVER stored in a span (doctrine: no bodies).
    # Redacting these key names defends against a caller passing a body dict whose
    # nested values could otherwise be exposed via repr().
    "body", "payload", "content", "data", "params", "query", "headers",
)

# Private/sensitive address tokens that must never appear in a served trace. The
# documented span() usage wraps node probes with an ``endpoint`` attribute (e.g.
# ``endpoint="100.76.58.50:443"``); these traces are published verbatim on the
# public ``/observability/traces`` route, so a raw 100.x tailnet IP, the :11434
# Ollama port, or the box public IP would leak. We scrub the ADDRESS while
# keeping the attribute (and the rest of its value) intact — this changes no
# true/false fact, it only hides private addressing (Doctrine v11; same class as
# the compute-pool egress scrub in szl_backend_hardening._PRIVATE_ADDR_RE).
_PRIVATE_ADDR_RE = re.compile(
    r"(?:https?://)?"                                               # optional scheme
    r"(?:100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.\d{1,3}\.\d{1,3}"  # 100.64-127.x.x CGNAT/tailnet
    r"|167\.233\.50\.75)"                                           # the box public IP
    r"(?::\d+)?"                                                    # optional :port (e.g. :11434)
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stderr(msg: str) -> None:
    try:
        print(msg, file=sys.stderr)
    except Exception:
        pass


def _env_int(name: str, default: int) -> int:
    try:
        v = int(os.environ.get(name, "").strip())
        return v if v > 0 else default
    except Exception:
        return default


def _sanitize_attr_value(key: str, value: Any) -> Any:
    """Make ONE attribute value safe to store/serialize.

    Rules (honest + leak-proof, never raises):
      • if the KEY name hints at a secret -> "[redacted]".
      • only scalars (str/int/float/bool/None) are kept; anything else is coerced
        to a short ``repr`` (so a body/object dict can't smuggle nested secrets).
      • private addresses (100.x tailnet IP, :11434, box IP) are scrubbed from
        any string value -> "(private)" (served traces are public).
      • strings are length-bounded so a huge value cannot bloat memory.
    """
    try:
        kl = str(key).lower()
        if any(h in kl for h in _SECRET_KEY_HINTS):
            return "[redacted]"
        if isinstance(value, bool) or value is None:
            return value
        if isinstance(value, (int, float)):
            return value
        if isinstance(value, str):
            v = _PRIVATE_ADDR_RE.sub("(private)", value)
            return v if len(v) <= _MAX_ATTR_STR_LEN else v[:_MAX_ATTR_STR_LEN] + "…"
        # Non-scalar: never store the object itself (could carry a body / secret).
        s = _PRIVATE_ADDR_RE.sub("(private)", repr(value))
        return s if len(s) <= _MAX_ATTR_STR_LEN else s[:_MAX_ATTR_STR_LEN] + "…"
    except Exception:
        return "[unserializable]"


def _sanitize_attrs(attrs: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Sanitize a whole attribute dict (bounded key count, screened values)."""
    out: Dict[str, Any] = {}
    if not attrs:
        return out
    try:
        for i, (k, v) in enumerate(attrs.items()):
            if i >= _MAX_ATTR_KEYS:
                break
            try:
                out[str(k)[:64]] = _sanitize_attr_value(k, v)
            except Exception:
                continue
    except Exception:
        pass
    return out


# ===========================================================================
# Span — one timed unit of work inside a trace (OpenTelemetry-shaped).
# ===========================================================================
class Span:
    """A single span: name, real start/end (perf_counter), status, attributes.

    A span is created via ``Trace.start_span`` / the ``span()`` context manager.
    Its duration is REAL measured wall time — ``end()`` records perf_counter so
    ``duration_ms`` is the true elapsed time, never a placeholder. A span that
    was never ended reports ``ended=False`` and ``duration_ms=None`` (honest —
    we do not invent a duration).
    """

    __slots__ = (
        "name", "span_id", "parent_id", "trace_id",
        "_t0", "_t_end", "status", "attributes", "_started_iso",
    )

    def __init__(self, name: str, trace_id: str, parent_id: Optional[str]) -> None:
        self.name = str(name)[:128]
        self.span_id = uuid.uuid4().hex[:16]
        self.parent_id = parent_id
        self.trace_id = trace_id
        self._t0 = time.perf_counter()          # REAL monotonic start
        self._t_end: Optional[float] = None
        self.status = "OK"                       # OK | ERROR | TIMEOUT (caller-set)
        self.attributes: Dict[str, Any] = {}
        self._started_iso = _now_iso()

    @property
    def ended(self) -> bool:
        return self._t_end is not None

    @property
    def duration_ms(self) -> Optional[float]:
        """REAL elapsed milliseconds, or None if the span never ended."""
        if self._t_end is None:
            return None
        return round((self._t_end - self._t0) * 1000.0, 3)

    def set_attribute(self, key: str, value: Any) -> None:
        """Record ONE sanitized attribute (no secret/body can land here)."""
        try:
            if len(self.attributes) >= _MAX_ATTR_KEYS:
                return
            self.attributes[str(key)[:64]] = _sanitize_attr_value(key, value)
        except Exception:
            pass

    def set_status(self, status: str) -> None:
        try:
            s = str(status).upper()
            if s in ("OK", "ERROR", "TIMEOUT"):
                self.status = s
        except Exception:
            pass

    def end(self) -> None:
        """Stamp the real end time (idempotent — first end wins)."""
        if self._t_end is None:
            self._t_end = time.perf_counter()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "span_id": self.span_id,
            "parent_id": self.parent_id,
            "trace_id": self.trace_id,
            "status": self.status,
            "duration_ms": self.duration_ms,   # None ONLY if never ended (honest)
            "ended": self.ended,
            "started_at": self._started_iso,
            "attributes": dict(self.attributes),
        }


# ===========================================================================
# Trace — a tree of spans sharing one trace_id (== X-Request-ID when present).
# ===========================================================================
class Trace:
    """A collection of spans for one request, forming a parent/child tree.

    ``trace_id`` reuses the inbound X-Request-ID (prod-hardening) when supplied,
    so a trace correlates 1:1 with the structured access log line; otherwise a
    fresh id is minted. Spans are appended as they are created; the root span is
    the first span with no parent. ``duration_ms`` is the root span's real
    duration (the whole-request wall time).
    """

    def __init__(self, name: str, trace_id: Optional[str] = None) -> None:
        self.name = str(name)[:128]
        self.trace_id = (str(trace_id)[:200] if trace_id else uuid.uuid4().hex)
        self.spans: List[Span] = []
        self._lock = threading.Lock()
        self._root_id: Optional[str] = None
        self.started_at = _now_iso()
        # The root span carries the whole-request timing.
        root = self.start_span(name, parent_id=None)
        self._root_id = root.span_id

    def start_span(self, name: str, parent_id: Optional[str]) -> Span:
        sp = Span(name, self.trace_id, parent_id)
        with self._lock:
            # Bound spans per trace (pathological fan-out defense).
            if len(self.spans) < MAX_SPANS_PER_TRACE:
                self.spans.append(sp)
        return sp

    @property
    def root(self) -> Optional[Span]:
        for sp in self.spans:
            if sp.span_id == self._root_id:
                return sp
        return self.spans[0] if self.spans else None

    @property
    def duration_ms(self) -> Optional[float]:
        r = self.root
        return r.duration_ms if r else None

    def end(self) -> None:
        """End the root span (idempotent). Child spans are ended by their CMs."""
        r = self.root
        if r is not None:
            r.end()

    def status(self) -> str:
        """Worst child status — ERROR > TIMEOUT > OK (honest roll-up)."""
        order = {"OK": 0, "TIMEOUT": 1, "ERROR": 2}
        worst = "OK"
        for sp in self.spans:
            if order.get(sp.status, 0) > order.get(worst, 0):
                worst = sp.status
        return worst

    def to_dict(self) -> Dict[str, Any]:
        spans = [sp.to_dict() for sp in self.spans]
        return {
            "trace_id": self.trace_id,
            "name": self.name,
            "started_at": self.started_at,
            "duration_ms": self.duration_ms,
            "status": self.status(),
            "span_count": len(spans),
            "spans": spans,
        }


# ===========================================================================
# Ring buffer of recent traces — BOUNDED memory (deque maxlen). Thread-safe.
# ===========================================================================
class TraceRing:
    """A bounded, thread-safe ring of the most recent completed traces.

    ``deque(maxlen=capacity)`` guarantees memory is bounded: when full, appending
    a new trace silently drops the OLDEST. No unbounded growth is possible.
    """

    def __init__(self, capacity: int = DEFAULT_RING_CAPACITY) -> None:
        self.capacity = max(1, int(capacity))
        self._dq: Deque[Trace] = deque(maxlen=self.capacity)
        self._lock = threading.Lock()

    def add(self, trace: Trace) -> None:
        try:
            with self._lock:
                self._dq.append(trace)
        except Exception:
            pass  # fail-open: never break a request to record a trace

    def all(self) -> List[Trace]:
        with self._lock:
            return list(self._dq)

    def get(self, trace_id: str) -> Optional[Trace]:
        with self._lock:
            for t in reversed(self._dq):
                if t.trace_id == trace_id:
                    return t
        return None

    def __len__(self) -> int:
        with self._lock:
            return len(self._dq)


# Process-wide ring (capacity env-overridable: A11OY_TRACE_RING_CAPACITY).
TRACES = TraceRing(_env_int("A11OY_TRACE_RING_CAPACITY", DEFAULT_RING_CAPACITY))

# Context propagation: the active trace + active span for THIS logical request,
# isolated per-task/per-thread by contextvars (the OpenTelemetry context model).
_CURRENT_TRACE: "contextvars.ContextVar[Optional[Trace]]" = contextvars.ContextVar(
    "szl_obs_current_trace", default=None
)
_CURRENT_SPAN: "contextvars.ContextVar[Optional[Span]]" = contextvars.ContextVar(
    "szl_obs_current_span", default=None
)


def current_trace() -> Optional[Trace]:
    try:
        return _CURRENT_TRACE.get()
    except Exception:
        return None


def current_span() -> Optional[Span]:
    try:
        return _CURRENT_SPAN.get()
    except Exception:
        return None


def start_trace(name: str, trace_id: Optional[str] = None) -> Trace:
    """Begin a trace and bind it (and its root span) to the current context.

    ``trace_id`` should be the inbound X-Request-ID (prod-hardening) so the trace
    correlates with the access log; if omitted a fresh id is minted. FAILS OPEN:
    on any internal error a throwaway Trace is still returned so callers never see
    an exception from the tracer.
    """
    try:
        tr = Trace(name, trace_id=trace_id)
        _CURRENT_TRACE.set(tr)
        _CURRENT_SPAN.set(tr.root)
        return tr
    except Exception:
        # Last-ditch: return a minimal trace object; never raise into caller code.
        try:
            return Trace(name)
        except Exception:
            t = object.__new__(Trace)  # type: ignore[call-arg]
            t.name = str(name)[:128]
            t.trace_id = uuid.uuid4().hex
            t.spans = []
            t._lock = threading.Lock()
            t._root_id = None
            t.started_at = _now_iso()
            return t


def finish_trace(trace: Optional[Trace] = None, record: bool = True) -> Optional[Trace]:
    """End the trace's root span and (optionally) push it into the ring buffer.

    FAILS OPEN: any error is swallowed; recording a trace must never break a
    request.
    """
    try:
        tr = trace if trace is not None else current_trace()
        if tr is None:
            return None
        tr.end()
        if record:
            TRACES.add(tr)
        return tr
    except Exception:
        return None


class _SpanCtx:
    """Context manager returned by ``span()``. Times REAL wall clock, attaches to
    the active parent span, restores the parent on exit, and marks ERROR if the
    wrapped block raised (the exception is RE-RAISED — tracing is transparent).
    Entirely guarded so the tracer itself never raises into the wrapped code.
    """

    __slots__ = ("_name", "_attrs", "_span", "_token", "_active")

    def __init__(self, name: str, attrs: Dict[str, Any]) -> None:
        self._name = name
        self._attrs = attrs
        self._span: Optional[Span] = None
        self._token = None
        self._active = False

    def __enter__(self) -> Optional[Span]:
        try:
            tr = current_trace()
            if tr is None:
                # No active trace -> a no-op span (still returns something usable),
                # so wrapping code outside a request never errors.
                return None
            parent = current_span()
            parent_id = parent.span_id if parent is not None else None
            sp = tr.start_span(self._name, parent_id=parent_id)
            for k, v in self._attrs.items():
                sp.set_attribute(k, v)
            self._span = sp
            self._token = _CURRENT_SPAN.set(sp)
            self._active = True
            return sp
        except Exception:
            return None  # fail-open

    def __exit__(self, exc_type, exc, tb) -> bool:
        try:
            if self._span is not None:
                if exc_type is not None:
                    # Mark TIMEOUT for timeout-family exceptions, else ERROR.
                    name = getattr(exc_type, "__name__", "") or ""
                    if "timeout" in name.lower() or "TimeoutError" in name:
                        self._span.set_status("TIMEOUT")
                    else:
                        self._span.set_status("ERROR")
                    self._span.set_attribute("exc_type", name)  # TYPE only, never msg
                self._span.end()
            if self._active and self._token is not None:
                _CURRENT_SPAN.reset(self._token)
        except Exception:
            pass
        # Return False -> never suppress the wrapped exception (transparent).
        return False


def span(name: str, **attributes: Any) -> _SpanCtx:
    """Context manager that records a REAL-timed child span under the active trace.

    Usage (wrap each node probe / feed fetch in the fan-out):

        with span("chaski", node="chaski", endpoint="chaski:443"):
            result = probe_chaski()   # real call; duration measured honestly

    If no trace is active (code path outside a request), it is a safe no-op. On
    an exception the span is marked TIMEOUT (timeout-family) or ERROR and the
    exception is RE-RAISED unchanged. Attribute values are sanitized so no
    secret / body / private address can leak into the served span (a raw 100.x
    tailnet IP or :11434 port in a value is scrubbed to "(private)").
    """
    return _SpanCtx(str(name), _sanitize_attrs(attributes))


# ===========================================================================
# Percentiles + per-surface SLO summary (the RED method, from the ring buffer).
# ===========================================================================
def _percentile(sorted_vals: List[float], pct: float) -> Optional[float]:
    """Nearest-rank percentile of an already-sorted list (None if empty)."""
    if not sorted_vals:
        return None
    if len(sorted_vals) == 1:
        return round(sorted_vals[0], 3)
    k = max(0, min(len(sorted_vals) - 1, int(round((pct / 100.0) * (len(sorted_vals) - 1)))))
    return round(sorted_vals[k], 3)


def health_summary() -> Dict[str, Any]:
    """Per-surface p50/p95 latency + error rate, computed from the ring buffer.

    Honest: every number is derived from REAL measured trace durations and REAL
    span statuses currently retained in the bounded ring. A surface with no
    completed traces simply does not appear. This is the at-a-glance SLO view.
    """
    per: Dict[str, Dict[str, Any]] = {}
    try:
        traces = TRACES.all()
        bucket: Dict[str, List[float]] = {}
        errors: Dict[str, int] = {}
        counts: Dict[str, int] = {}
        for tr in traces:
            try:
                surface = tr.name
                d = tr.duration_ms
                counts[surface] = counts.get(surface, 0) + 1
                if d is not None:
                    bucket.setdefault(surface, []).append(d)
                if tr.status() in ("ERROR", "TIMEOUT"):
                    errors[surface] = errors.get(surface, 0) + 1
            except Exception:
                continue
        for surface, ds in bucket.items():
            ds_sorted = sorted(ds)
            n = counts.get(surface, len(ds_sorted))
            err = errors.get(surface, 0)
            per[surface] = {
                "requests": n,
                "errors": err,
                "error_rate": round(err / n, 4) if n else 0.0,
                "p50_ms": _percentile(ds_sorted, 50),
                "p95_ms": _percentile(ds_sorted, 95),
                "max_ms": round(max(ds_sorted), 3) if ds_sorted else None,
            }
    except Exception:
        pass
    return {
        "surfaces": per,
        "window": f"last {len(TRACES)} traces (bounded ring, cap={TRACES.capacity})",
        "method": "RED (Rate/Errors/Duration); p50/p95 nearest-rank from real durations",
        "generated_at": _now_iso(),
        "doctrine": dict(DOCTRINE),
    }


def recent_traces(limit: int = 50, slowest_first: bool = True) -> List[Dict[str, Any]]:
    """Summaries of recent traces, slowest-first by default (real durations)."""
    try:
        traces = TRACES.all()
        summaries = []
        for tr in traces:
            try:
                summaries.append({
                    "trace_id": tr.trace_id,
                    "name": tr.name,
                    "started_at": tr.started_at,
                    "duration_ms": tr.duration_ms,
                    "status": tr.status(),
                    "span_count": len(tr.spans),
                })
            except Exception:
                continue
        if slowest_first:
            summaries.sort(key=lambda s: (s["duration_ms"] if s["duration_ms"] is not None else -1.0),
                           reverse=True)
        else:
            summaries.reverse()  # most-recent-first
        return summaries[: max(1, int(limit))]
    except Exception:
        return []


# ===========================================================================
# serve.py wiring — ADDITIVE, try/except-guarded. Tracing routes only.
# ===========================================================================
def register(app: Any, ns: str = "a11oy") -> List[str]:
    """ADDITIVE: attach read-only tracing/observability routes.

    Never replaces an existing route (uses add_api_route only if the path is
    free). Returns the list of route paths actually attached. The whole thing is
    guarded: if routes cannot be wired, the app is returned untouched.

    Routes:
      GET /api/<ns>/v1/observability/traces           recent traces, slowest-first
      GET /api/<ns>/v1/observability/trace/{trace_id} one trace's full span tree
      GET /api/<ns>/v1/observability/health-summary   per-surface p50/p95 + errors
    """
    paths: List[str] = []
    try:
        from fastapi.responses import JSONResponse
    except Exception:
        _stderr("[a11oy:observability] fastapi not available; skipping route registration")
        return paths

    existing = {getattr(r, "path", None)
                for r in getattr(getattr(app, "router", None), "routes", [])}

    def _add(path: str, handler: Any) -> None:
        if path in existing:
            _stderr(f"[a11oy:observability] route present; skipped: {path}")
            return
        app.add_api_route(path, handler, methods=["GET"], include_in_schema=False)
        existing.add(path)
        paths.append(path)

    async def _traces():  # noqa: ANN202
        return JSONResponse({
            "ns": ns,
            "traces": recent_traces(limit=50, slowest_first=True),
            "order": "slowest-first",
            "ring": {"size": len(TRACES), "capacity": TRACES.capacity},
            "pattern": "OpenTelemetry-style traces (our stdlib impl; no otel SDK dep)",
            "ts": _now_iso(),
            "doctrine": dict(DOCTRINE),
        }, status_code=200)

    async def _trace(trace_id: str):  # noqa: ANN202
        tr = TRACES.get(trace_id)
        if tr is None:
            return JSONResponse({
                "ns": ns,
                "error": "trace_not_found",
                "trace_id": trace_id,
                "note": "trace not in the bounded ring (dropped as oldest, or never recorded)",
                "ts": _now_iso(),
            }, status_code=404)
        return JSONResponse({
            "ns": ns,
            "trace": tr.to_dict(),
            "ts": _now_iso(),
            "doctrine": dict(DOCTRINE),
        }, status_code=200)

    async def _health_summary():  # noqa: ANN202
        return JSONResponse({"ns": ns, **health_summary()}, status_code=200)

    _add(f"/api/{ns}/v1/observability/traces", _traces)
    _add(f"/api/{ns}/v1/observability/trace/{{trace_id}}", _trace)
    _add(f"/api/{ns}/v1/observability/health-summary", _health_summary)

    _stderr(f"[a11oy:observability] tracing routes registered: {paths}")
    return paths


# ===========================================================================
# Self-test — pure stdlib, OFFLINE. No network, no FastAPI required.
# ===========================================================================
def _selftest() -> Dict[str, Any]:
    checks: List = []

    def chk(name: str, cond: bool) -> None:
        checks.append((name, bool(cond)))

    # A span records a REAL, positive duration.
    tr = start_trace("unit-test")
    with span("work-a") as s:
        time.sleep(0.005)
    chk("span_real_duration", s is not None and s.duration_ms is not None and s.duration_ms > 0)

    # Nested spans share the trace_id and form a parent/child tree.
    with span("parent") as p:
        with span("child") as c:
            pass
    chk("nested_same_trace", p.trace_id == c.trace_id == tr.trace_id)
    chk("nested_is_child", c.parent_id == p.span_id)
    finish_trace(tr, record=True)

    # Ring buffer is bounded (drops oldest past capacity).
    ring = TraceRing(capacity=3)
    for i in range(10):
        t = Trace(f"r{i}")
        t.end()
        ring.add(t)
    chk("ring_bounded", len(ring) == 3)
    chk("ring_dropped_oldest", ring.all()[0].name == "r7")

    # No secret leaks into attributes (key-name screened, body coerced).
    with span("leaky", api_key="SUPERSECRET", authorization="Bearer abc",
              note="ok", body={"password": "x"}) as ls:
        pass
    chk("secret_redacted_apikey", ls.attributes.get("api_key") == "[redacted]")
    chk("secret_redacted_auth", ls.attributes.get("authorization") == "[redacted]")
    chk("body_not_stored_raw", "SUPERSECRET" not in repr(ls.attributes))
    chk("safe_attr_kept", ls.attributes.get("note") == "ok")

    # Fail-open: span() outside any trace is a harmless no-op, never raises.
    _CURRENT_TRACE.set(None)
    _CURRENT_SPAN.set(None)
    raised = False
    try:
        with span("orphan"):
            pass
    except Exception:
        raised = True
    chk("fail_open_no_trace", raised is False)

    ok = all(p for _, p in checks)
    return {"ok": ok, "checks": len(checks),
            "failed": [n for n, p in checks if not p], "doctrine": dict(DOCTRINE)}


if __name__ == "__main__":
    import json
    print(json.dumps(_selftest(), indent=2))
