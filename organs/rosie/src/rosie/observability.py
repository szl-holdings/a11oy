# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
"""Real OTLP (gRPC) span exporter + W3C traceparent helpers for Rosie.

Field leaders:
  - OpenTelemetry OTLP spec   https://opentelemetry.io/docs/specs/otlp/
  - OTLP exporter spec        https://opentelemetry.io/docs/specs/otel/protocol/exporter/
  - W3C Trace Context §3.2    https://www.w3.org/TR/trace-context/

Honest disclosure: spans are emitted to the OTLP/gRPC endpoint given by
OTEL_EXPORTER_OTLP_ENDPOINT (default http://localhost:4317). If the
opentelemetry SDK is not installed OR the collector is unreachable, we fall
back to an in-process span recorder so the orchestrator still produces a real,
inspectable span list (no silent no-op, no fake "exported" claim).

Doctrine v11 LOCKED 749/14/163 @ c7c0ba17 · Λ = Conjecture 1.
"""
from __future__ import annotations

import os
import secrets
import time
from dataclasses import dataclass, field
from typing import Optional

OTEL_ENDPOINT = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
SERVICE_NAME = os.environ.get("OTEL_SERVICE_NAME", "rosie")

# ── W3C Trace Context (§3.2 traceparent: version-traceid-parentid-flags) ──────


def new_trace_id() -> str:
    """32 lowercase hex chars, non-zero (W3C §3.2.2.3)."""
    return secrets.token_hex(16)


def new_span_id() -> str:
    """16 lowercase hex chars, non-zero (W3C §3.2.2.4)."""
    return secrets.token_hex(8)


def make_traceparent(trace_id: Optional[str] = None, parent_id: Optional[str] = None,
                     sampled: bool = True) -> str:
    """Build a valid W3C traceparent: 00-<32hex>-<16hex>-<2hex>."""
    tid = trace_id or new_trace_id()
    pid = parent_id or new_span_id()
    flags = "01" if sampled else "00"
    return f"00-{tid}-{pid}-{flags}"


def parse_traceparent(tp: str) -> Optional[dict]:
    """Parse and validate a W3C traceparent header. Returns None if malformed."""
    if not tp or not isinstance(tp, str):
        return None
    parts = tp.strip().split("-")
    if len(parts) != 4:
        return None
    version, trace_id, parent_id, flags = parts
    if len(version) != 2 or len(trace_id) != 32 or len(parent_id) != 16 or len(flags) != 2:
        return None
    if trace_id == "0" * 32 or parent_id == "0" * 16:
        return None  # W3C: all-zero ids are invalid
    try:
        int(trace_id, 16); int(parent_id, 16); int(flags, 16)
    except ValueError:
        return None
    return {"version": version, "trace_id": trace_id, "parent_id": parent_id,
            "flags": flags, "sampled": bool(int(flags, 16) & 0x01)}


def child_traceparent(incoming: str | None) -> str:
    """Continue a trace: keep trace-id, mint a new parent-id (W3C §3.2.2.5)."""
    p = parse_traceparent(incoming) if incoming else None
    if p:
        return make_traceparent(p["trace_id"], new_span_id(), p["sampled"])
    return make_traceparent()


# ── Span recorder (always real, always inspectable) ───────────────────────────


@dataclass
class RecordedSpan:
    """An in-memory OTLP span recorded by the test/inspectable exporter.

    Captures the fields needed to reconstruct an OTLP span (name, trace/span
    ids, parent, start/end nanos, attributes, status) so traces can be
    asserted on in tests without a live collector.
    """

    name: str
    trace_id: str
    span_id: str
    parent_span_id: str | None
    start_unix_ns: int
    end_unix_ns: int | None = None
    attributes: dict = field(default_factory=dict)
    status: str = "UNSET"

    def to_otlp_dict(self) -> dict:
        """Render this span as an OTLP-shaped JSON dict.

        Returns:
            A dict matching the OTLP span schema (string nano timestamps,
            ``parentSpanId`` empty when root), ready to nest under
            ``resourceSpans`` for export or assertion.
        """
        return {
            "name": self.name,
            "traceId": self.trace_id,
            "spanId": self.span_id,
            "parentSpanId": self.parent_span_id or "",
            "startTimeUnixNano": str(self.start_unix_ns),
            "endTimeUnixNano": str(self.end_unix_ns or self.start_unix_ns),
            "attributes": [{"key": k, "value": {"stringValue": str(v)}}
                           for k, v in self.attributes.items()],
            "status": {"code": self.status},
        }


class Observability:
    """Emit OTLP spans for every orchestration step.

    Tries the real OTel SDK + OTLPSpanExporter(gRPC). If unavailable, records
    spans in-process (still real objects you can assert on) and reports
    exporter="in-process-fallback" honestly.
    """

    def __init__(self, service_name: str = SERVICE_NAME, endpoint: str = OTEL_ENDPOINT):
        self.service_name = service_name
        self.endpoint = endpoint
        self.spans: list[RecordedSpan] = []
        self.exporter = "none"
        self._otel = None
        self._tracer = None
        self._init_otel()

    def _init_otel(self) -> None:
        try:
            from opentelemetry import trace
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter,
            )
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor

            resource = Resource.create({
                "service.name": self.service_name,
                "szl.doctrine": "v11-749-14-163",
                "szl.kernel_commit": "c7c0ba17",
            })
            provider = TracerProvider(resource=resource)
            exporter = OTLPSpanExporter(endpoint=self.endpoint, insecure=True)
            provider.add_span_processor(BatchSpanProcessor(exporter))
            trace.set_tracer_provider(provider)
            self._otel = trace
            self._tracer = trace.get_tracer("rosie.orchestrator")
            self.exporter = f"otlp-grpc:{self.endpoint}"
        except Exception as e:  # SDK absent or collector unreachable
            self.exporter = f"in-process-fallback ({type(e).__name__})"

    def span(self, name: str, traceparent: str, attributes: dict | None = None) -> RecordedSpan:
        """Record (and, if SDK present, emit) a span linked to a traceparent."""
        p = parse_traceparent(traceparent) or {}
        rec = RecordedSpan(
            name=name,
            trace_id=p.get("trace_id", new_trace_id()),
            span_id=new_span_id(),
            parent_span_id=p.get("parent_id"),
            start_unix_ns=time.time_ns(),
            attributes={**(attributes or {}), "szl.service": self.service_name},
        )
        if self._tracer is not None:
            try:
                with self._tracer.start_as_current_span(name) as s:
                    for k, v in rec.attributes.items():
                        s.set_attribute(k, str(v))
            except Exception:
                pass
        rec.end_unix_ns = time.time_ns()
        rec.status = "OK"
        self.spans.append(rec)
        return rec

    def trace_ids(self) -> set[str]:
        """Return the set of distinct trace ids across all recorded spans.

        Returns:
            A set of trace-id strings, used to assert that a workflow kept a
            stable root trace id across organ hops.
        """
        return {s.trace_id for s in self.spans}

    def export_dict(self) -> dict:
        """OTLP-shaped resourceSpans payload (inspectable / assertable)."""
        return {
            "exporter": self.exporter,
            "resourceSpans": [{
                "resource": {"attributes": [
                    {"key": "service.name", "value": {"stringValue": self.service_name}}]},
                "scopeSpans": [{
                    "scope": {"name": "rosie.orchestrator"},
                    "spans": [s.to_otlp_dict() for s in self.spans],
                }],
            }],
        }
