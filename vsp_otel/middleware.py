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
     server span only when OTEL_EXPORTER_OTLP_ENDPOINT passes the private endpoint policy;
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
import hashlib
import ipaddress
import re
import secrets
import time
from contextlib import contextmanager
from urllib.parse import urlsplit

_VERSION = "0.2.0"
# Honest gating: a real collector endpoint is used ONLY when the operator sets
# OTEL_EXPORTER_OTLP_ENDPOINT. When it is unset there is no collector to export
# to (prod is a single HF Space, not the k8s mesh the collector config targets),
# so we stay honestly in-process-only rather than shipping spans into the void.
_ENDPOINT = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT") or None
_LOWER_HEX_RE = re.compile(r"^[0-9a-f]+$")


def _endpoint_policy(raw: str | None, allowed_hosts: str | None = None):
    """Admit a secret-free private OTLP endpoint or fail closed."""
    if not raw:
        return {"allowed": False, "endpoint": None, "state": "NOT-CONFIGURED",
                "fingerprint": None, "reason": "OTEL_EXPORTER_OTLP_ENDPOINT is unset"}
    try:
        parsed = urlsplit(str(raw).strip())
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("scheme must be http or https")
        if parsed.username or parsed.password:
            raise ValueError("credentials in endpoint URL are forbidden")
        if parsed.query or parsed.fragment or parsed.path not in {"", "/"}:
            raise ValueError("query, fragment, and non-root path are forbidden")
        host = (parsed.hostname or "").lower().rstrip(".")
        if not host:
            raise ValueError("host is required")
        port = parsed.port or (443 if parsed.scheme == "https" else 4317)
        if not 1 <= int(port) <= 65535:
            raise ValueError("port is outside 1..65535")
        allow = {h.strip().lower().rstrip(".") for h in
                 str(allowed_hosts if allowed_hosts is not None else
                     os.environ.get("A11OY_OTEL_ALLOWED_HOSTS", "")).split(",") if h.strip()}
        if host == "localhost":
            basis = "LOOPBACK"
        else:
            try:
                addr = ipaddress.ip_address(host)
            except ValueError:
                if host not in allow:
                    raise ValueError("DNS host is not in A11OY_OTEL_ALLOWED_HOSTS")
                basis = "OPERATOR-ALLOWLISTED-DNS"
            else:
                if (not addr.is_loopback and
                        (addr.is_unspecified or addr.is_multicast or addr.is_reserved or addr.is_link_local)):
                    raise ValueError("unspecified, multicast, reserved, and link-local endpoints are forbidden")
                if not (addr.is_loopback or addr.is_private):
                    raise ValueError("public IP endpoints are forbidden")
                basis = "LOOPBACK" if addr.is_loopback else "PRIVATE-IP"
        authority_host = f"[{host}]" if ":" in host else host
        canonical = f"{parsed.scheme}://{authority_host}:{port}"
        fingerprint = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
        return {"allowed": True, "endpoint": canonical, "state": "CONFIGURED",
                "fingerprint": fingerprint, "reason": basis,
                "transport_security": "TLS" if parsed.scheme == "https" else "PLAINTEXT"}
    except (TypeError, ValueError) as exc:
        return {"allowed": False, "endpoint": None, "state": "POLICY-DENIED",
                "fingerprint": None, "reason": str(exc)[:160]}


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
    # Stable v00 only. Future versions need a version-specific parser; ff is invalid.
    if ver != "00" or flags not in {"00", "01"}:
        return None
    if not all(_LOWER_HEX_RE.fullmatch(part) for part in (ver, tid, pid, flags)):
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
        self.endpoint_policy = _endpoint_policy(endpoint)
        self.endpoint = self.endpoint_policy["endpoint"]
        self.endpoint_fingerprint = self.endpoint_policy["fingerprint"]
        self._tracer = None
        if not self.endpoint_policy["allowed"]:
            # No OTLP endpoint configured — do NOT spin up an exporter that would
            # silently drop spans. Traceparent propagation still works in-process.
            self.exporter = f"in-process-only:{self.endpoint_policy['state'].lower()}"
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
                BatchSpanProcessor(OTLPSpanExporter(
                    endpoint=self.endpoint,
                    insecure=self.endpoint_policy["transport_security"] != "TLS")))
            trace.set_tracer_provider(provider)
            self._tracer = trace.get_tracer(f"vsp-otel.{service_name}")
            self.exporter = f"otlp-grpc:configured:{self.endpoint_fingerprint}"
        except Exception as e:  # SDK absent — propagation still works
            self.exporter = f"in-process-only ({type(e).__name__})"

    @contextmanager
    def server_span(self, name: str, incoming_traceparent: str | None, attrs: dict):
        if self._tracer is None:
            yield None
            return
        try:
            from opentelemetry import propagate, trace
            parent = (propagate.extract({"traceparent": incoming_traceparent})
                      if incoming_traceparent else None)
            span_context = self._tracer.start_as_current_span(
                name, context=parent, kind=trace.SpanKind.SERVER)
        except Exception:
            yield None
            return
        with span_context as span:
            for key, value in attrs.items():
                span.set_attribute(key, str(value))
            yield span


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
        start_attrs = {
            "http.method": request.method,
            "http.route": request.url.path,
            "szl.service": svc,
            "szl.parent_trace_id": parsed["trace_id"] if parsed else "(root)",
        }
        accepted_parent = incoming if parsed else None
        with tracer.server_span(
                f"{svc} {request.method} {request.url.path}", accepted_parent, start_attrs) as span:
            if span is not None:
                ctx = span.get_span_context()
                trace_id = f"{ctx.trace_id:032x}"
                span_id = f"{ctx.span_id:016x}"
                sampled = bool(ctx.trace_flags & 0x01)
            else:
                trace_id = parsed["trace_id"] if parsed else _hex(16)
                span_id = _hex(8)
                sampled = parsed["sampled"] if parsed else True
            request.state.trace_id = trace_id
            request.state.traceparent = make_traceparent(trace_id, span_id, sampled)
            request.state.vsp_otel_exporter = tracer.exporter
            t0 = time.time_ns()
            response = await call_next(request)
            if span is not None:
                span.set_attribute("http.status_code", getattr(response, "status_code", 0))
                span.set_attribute("duration_ns", time.time_ns() - t0)
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
    app._vsp_otel_endpoint_policy = {
        k: v for k, v in tracer.endpoint_policy.items() if k != "endpoint"
    }
    return app


def status(app):
    """Machine-readable, secret-free observability posture; this read mints nothing."""
    installed = bool(getattr(app, "_vsp_otel_installed", False))
    exporter = str(getattr(app, "_vsp_otel_exporter", "UNAVAILABLE"))
    policy = dict(getattr(app, "_vsp_otel_endpoint_policy", {}) or {})
    export_active = exporter.startswith("otlp-grpc:configured:")
    return {
        "ok": True,
        "service": "a11oy.vsp-otel",
        "version": _VERSION,
        "label": "MEASURED",
        "propagation": "READY" if installed else "UNAVAILABLE",
        "export": "CONFIGURED" if export_active else "IN-PROCESS-ONLY",
        "exporter": exporter,
        "endpoint": {
            "state": policy.get("state", "UNKNOWN"),
            "fingerprint": policy.get("fingerprint"),
            "admission_basis": policy.get("reason", "UNKNOWN"),
            "transport_security": policy.get("transport_security", "UNKNOWN"),
        },
        "receipt_minted": False,
        "note": "trace propagation readiness is separate from OTLP export delivery",
    }
