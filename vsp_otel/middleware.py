# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
"""vsp_otel.middleware — real W3C-traceparent + OTLP/gRPC middleware for FastAPI/Starlette organs.

Field leaders harnessed (cited):
  - W3C Trace Context §3.2 (traceparent)   https://www.w3.org/TR/trace-context/
  - OpenTelemetry OTLP exporter spec         https://opentelemetry.io/docs/specs/otel/protocol/exporter/

`install(app)` adds an ASGI middleware that, for every request:
  1. parses any incoming `traceparent` (W3C §3.2), validating shape/non-zero ids;
  2. mints a child span id, keeping the same trace-id (cross-pod continuity);
  3. if the OpenTelemetry SDK + OTLP/gRPC exporter are installed, emits a real
     server span to OTEL_EXPORTER_OTLP_ENDPOINT (default localhost:4317);
  4. ALWAYS echoes a valid outbound `traceparent` response header so the next
     organ continues the SAME trace-id (this is what cross_pod_trace_test asserts).

Honest disclosure: if the OTel SDK is absent the span is NOT exported to a
collector — but the traceparent propagation (the cross-pod contract) still works
purely in-process. We never claim "exported" when the exporter is unavailable;
the middleware sets request.state.vsp_otel_exporter to the real status string.

Doctrine v11 LOCKED 749/14/163 @ c7c0ba17 · Λ = Conjecture 1.
"""
from __future__ import annotations

import os
import secrets
import time

_VERSION = "0.1.0"
# Honest gating: a real collector endpoint is used ONLY when the operator sets
# OTEL_EXPORTER_OTLP_ENDPOINT. When it is unset there is no collector to export
# to (prod is a single HF Space, not the k8s mesh the collector config targets),
# so we stay honestly in-process-only rather than shipping spans into the void.
_ENDPOINT = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT") or None


def _hex(n: int) -> str:
    return secrets.token_hex(n)


def parse_traceparent(tp):
    """Parse/validate a W3C traceparent. Returns dict or None (W3C §3.2)."""
    if not tp or not isinstance(tp, str):
        return None
    parts = tp.strip().split("-")
    if len(parts) != 4:
        return None
    ver, tid, pid, flags = parts
    if len(ver) != 2 or len(tid) != 32 or len(pid) != 16 or len(flags) != 2:
        return None
    if tid == "0" * 32 or pid == "0" * 16:
        return None
    try:
        int(tid, 16); int(pid, 16); int(flags, 16)
    except ValueError:
        return None
    return {"trace_id": tid, "parent_id": pid, "flags": flags,
            "sampled": bool(int(flags, 16) & 0x01)}


def make_traceparent(trace_id=None, parent_id=None, sampled=True):
    tid = trace_id or _hex(16)
    pid = parent_id or _hex(8)
    return f"00-{tid}-{pid}-{'01' if sampled else '00'}"


class _Tracer:
    """Lazily initialises a real OTel TracerProvider + OTLP/gRPC exporter."""

    def __init__(self, service_name: str, endpoint: str | None = _ENDPOINT):
        self.service_name = service_name
        self.endpoint = endpoint
        self._tracer = None
        if not endpoint:
            # No OTLP endpoint configured — do NOT spin up an exporter that would
            # silently drop spans. Traceparent propagation still works in-process.
            self.exporter = "in-process-only (no OTLP export configured)"
            return
        self.exporter = "in-process-only"
        try:
            from opentelemetry import trace
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter,
            )

            resource = Resource.create({
                "service.name": service_name,
                "szl.doctrine": "v11-749-14-163",
                "szl.kernel_commit": "c7c0ba17",
                "szl.lambda": "Conjecture-1",
            })
            provider = TracerProvider(resource=resource)
            provider.add_span_processor(
                BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, insecure=True)))
            trace.set_tracer_provider(provider)
            self._tracer = trace.get_tracer(f"vsp-otel.{service_name}")
            self.exporter = f"otlp-grpc:{endpoint}"
        except Exception as e:  # SDK absent — propagation still works
            self.exporter = f"in-process-only ({type(e).__name__})"

    def server_span(self, name: str, attrs: dict):
        if self._tracer is None:
            return
        try:
            with self._tracer.start_as_current_span(name) as s:
                for k, v in attrs.items():
                    s.set_attribute(k, str(v))
        except Exception:
            pass


def install(app, service_name: str | None = None, endpoint: str | None = _ENDPOINT):
    """Install the vsp-otel middleware on a FastAPI/Starlette `app`.

    Idempotent: a second install() on the same app is a no-op.
    """
    if getattr(app, "_vsp_otel_installed", False):
        return app
    svc = service_name or os.environ.get("OTEL_SERVICE_NAME") \
        or getattr(app, "title", "organ").split()[0].lower()
    tracer = _Tracer(svc, endpoint)

    @app.middleware("http")
    async def _vsp_otel_mw(request, call_next):
        incoming = request.headers.get("traceparent")
        parsed = parse_traceparent(incoming)
        trace_id = parsed["trace_id"] if parsed else _hex(16)
        span_id = _hex(8)
        sampled = parsed["sampled"] if parsed else True
        request.state.trace_id = trace_id
        request.state.traceparent = make_traceparent(trace_id, span_id, sampled)
        request.state.vsp_otel_exporter = tracer.exporter
        t0 = time.time_ns()
        response = await call_next(request)
        tracer.server_span(f"{svc} {request.method} {request.url.path}", {
            "http.method": request.method,
            "http.route": request.url.path,
            "http.status_code": getattr(response, "status_code", 0),
            "szl.service": svc,
            "szl.parent_trace_id": parsed["trace_id"] if parsed else "(root)",
            "duration_ns": time.time_ns() - t0,
        })
        # Echo a continuing traceparent so the next organ keeps the trace-id.
        response.headers["traceparent"] = request.state.traceparent
        response.headers["x-vsp-otel"] = f"{_VERSION};{tracer.exporter}"
        return response

    app._vsp_otel_installed = True
    app._vsp_otel_service = svc
    # Honest, machine-readable status of what was actually wired: either an OTLP
    # collector endpoint or "in-process-only (...)". Callers log this verbatim so
    # they never claim an exporter that isn't there.
    app._vsp_otel_exporter = tracer.exporter
    return app
