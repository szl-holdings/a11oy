"""
collector/app.py — vsp-otel OTLP collector exporter shim.

Layer 4 (Λ-gate exporter) of the SZL 7-layer architecture.

Drop-in for any OTel-instrumented org: point your OTLP/HTTP exporter at this
service. For every span it:
  1. receives spans on /v1/traces (OTLP/HTTP JSON, the standard OTel endpoint),
  2. computes Λ over the span's A1–A5 attributes (collector/lambda_gate.py),
  3. REJECTS spans with Λ < LAMBDA_FLOOR (0.90 — a11oy doctrine constant),
  4. signs accepted spans with a DSSE in-toto attestation (collector/dsse.py;
     cosign keyless OIDC in production),
  5. tracks span-latency online mean/variance (Welford) and unique-trace
     cardinality (HyperLogLog),
  6. forwards accepted+signed spans to a downstream OTLP endpoint
     (Tempo / Jaeger / any OTLP collector) set by VSP_FORWARD_ENDPOINT.

FastAPI if available; falls back to a stdlib http.server so the shim runs anywhere.

SPDX-License-Identifier: Apache-2.0
Author: Yachay (CTO authority) · Built by Perplexity Computer Agent · SZL Holdings
Doctrine v11 LOCKED — 749 / 14 / 163. SLSA L1+L2.
"""
from __future__ import annotations

import json
import os
import urllib.request
from typing import Any

from .dsse import DsseSigner
from .lambda_gate import LAMBDA_FLOOR, evaluate
from .stats import HyperLogLog, Welford

FORWARD_ENDPOINT = os.environ.get("VSP_FORWARD_ENDPOINT", "")  # e.g. http://tempo:4318/v1/traces
SERVICE_NAME = "vsp-otel"

# ── shared collector state ────────────────────────────────────────────────────
LATENCY = Welford()
TRACE_HLL = HyperLogLog(p=14)
COUNTERS = {"received": 0, "accepted": 0, "rejected": 0, "forwarded": 0}
SIGNER = DsseSigner()


def _otlp_attr_to_dict(attributes: list[dict]) -> dict[str, Any]:
    """Flatten OTLP KeyValue attribute list to a plain dict."""
    out: dict[str, Any] = {}
    for kv in attributes or []:
        k = kv.get("key")
        v = kv.get("value", {})
        if "doubleValue" in v:
            out[k] = float(v["doubleValue"])
        elif "intValue" in v:
            out[k] = int(v["intValue"])
        elif "boolValue" in v:
            out[k] = bool(v["boolValue"])
        elif "stringValue" in v:
            out[k] = v["stringValue"]
    return out


def _span_latency_ms(span: dict) -> float:
    try:
        start = int(span.get("startTimeUnixNano", 0))
        end = int(span.get("endTimeUnixNano", 0))
        return max(0.0, (end - start) / 1e6)
    except (TypeError, ValueError):
        return 0.0


def process_otlp(payload: dict) -> dict:
    """Process an OTLP/HTTP ExportTraceServiceRequest. Returns a summary dict.

    Mutates an internal forward buffer of accepted+signed spans.
    """
    accepted_resource_spans: list[dict] = []
    for rs in payload.get("resourceSpans", []):
        kept_scope_spans = []
        for ss in rs.get("scopeSpans", []):
            kept_spans = []
            for span in ss.get("spans", []):
                COUNTERS["received"] += 1
                attrs = _otlp_attr_to_dict(span.get("attributes", []))
                gate = evaluate(attrs)
                tid = span.get("traceId", "")
                if tid:
                    TRACE_HLL.add(tid)
                LATENCY.update(_span_latency_ms(span))
                if not gate.passed:
                    COUNTERS["rejected"] += 1
                    continue
                COUNTERS["accepted"] += 1
                # attach Λ-gate attributes + DSSE attestation
                ga = gate.as_attributes()
                span.setdefault("attributes", [])
                for k, v in ga.items():
                    span["attributes"].append({"key": k, "value": _wrap_val(v)})
                envelope = SIGNER.sign_span(
                    {"trace_id": tid, "span_id": span.get("spanId", ""),
                     "name": span.get("name", "")},
                    {"lambda_value": gate.lambda_value, "floor": gate.floor,
                     "passed": gate.passed, "axes": gate.axes},
                )
                span["attributes"].append(
                    {"key": "szl.dsse.receipt_hash",
                     "value": {"stringValue": envelope["receipt_hash"]}})
                span["attributes"].append(
                    {"key": "szl.dsse.keyid",
                     "value": {"stringValue": envelope["signatures"][0]["keyid"]}})
                kept_spans.append(span)
            if kept_spans:
                kept_scope_spans.append({**ss, "spans": kept_spans})
        if kept_scope_spans:
            accepted_resource_spans.append({**rs, "scopeSpans": kept_scope_spans})

    forwarded = 0
    if accepted_resource_spans and FORWARD_ENDPOINT:
        forwarded = _forward({"resourceSpans": accepted_resource_spans})
        COUNTERS["forwarded"] += forwarded

    return {
        "received": COUNTERS["received"],
        "accepted": COUNTERS["accepted"],
        "rejected": COUNTERS["rejected"],
        "forwarded": COUNTERS["forwarded"],
        "lambda_floor": LAMBDA_FLOOR,
        "unique_traces_est": TRACE_HLL.count(),
        "latency_ms": LATENCY.snapshot(),
    }


def _wrap_val(v: Any) -> dict:
    if isinstance(v, bool):
        return {"boolValue": v}
    if isinstance(v, int):
        return {"intValue": v}
    if isinstance(v, float):
        return {"doubleValue": v}
    return {"stringValue": str(v)}


def _forward(payload: dict) -> int:
    try:
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            FORWARD_ENDPOINT, data=data,
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=5):
            pass
        return sum(len(ss.get("spans", []))
                   for rs in payload["resourceSpans"]
                   for ss in rs.get("scopeSpans", []))
    except Exception:
        return 0  # forwarding is best-effort; gate decision already recorded


def metrics_text() -> str:
    s = LATENCY.snapshot()
    return (
        f"# HELP vsp_spans_total Spans seen by the Λ-gate by verdict\n"
        f"# TYPE vsp_spans_total counter\n"
        f'vsp_spans_total{{verdict="received"}} {COUNTERS["received"]}\n'
        f'vsp_spans_total{{verdict="accepted"}} {COUNTERS["accepted"]}\n'
        f'vsp_spans_total{{verdict="rejected"}} {COUNTERS["rejected"]}\n'
        f'vsp_spans_total{{verdict="forwarded"}} {COUNTERS["forwarded"]}\n'
        f"# HELP vsp_lambda_floor Configured Λ floor\n"
        f"# TYPE vsp_lambda_floor gauge\n"
        f"vsp_lambda_floor {LAMBDA_FLOOR}\n"
        f"# HELP vsp_span_latency_ms_mean Welford online mean span latency (ms)\n"
        f"# TYPE vsp_span_latency_ms_mean gauge\n"
        f"vsp_span_latency_ms_mean {s['mean']}\n"
        f"# HELP vsp_unique_traces_estimate HyperLogLog distinct trace-id count\n"
        f"# TYPE vsp_unique_traces_estimate gauge\n"
        f"vsp_unique_traces_estimate {TRACE_HLL.count()}\n"
    )


# ── FastAPI app (preferred) ────────────────────────────────────────────────────
def build_fastapi():
    # Imported inside the factory so the stdlib fallback path needs no FastAPI.
    # Globals (not the string-ified local annotations from `from __future__ import
    # annotations`) so FastAPI can resolve the Request type at decoration time.
    global FastAPI, Request, JSONResponse, PlainTextResponse
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse, PlainTextResponse

    api = FastAPI(title="vsp-otel", version="0.1.0",
                  description="Λ-signed OpenTelemetry collector exporter shim.")

    @api.get("/healthz")
    async def healthz():
        return {"status": "ok", "service": SERVICE_NAME, "lambda_floor": LAMBDA_FLOOR}

    @api.get("/metrics")
    async def metrics():
        return PlainTextResponse(metrics_text())

    @api.post("/v1/traces")
    async def traces(req: Request):
        raw = await req.body()
        payload = json.loads(raw or b"{}")
        summary = process_otlp(payload)
        return JSONResponse({"partialSuccess": {}, "szl": summary})

    return api


# stdlib fallback so the shim runs with zero deps
def run_stdlib(host: str = "0.0.0.0", port: int = 4318):  # pragma: no cover
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class H(BaseHTTPRequestHandler):
        def _send(self, code, body, ctype="application/json"):
            b = body.encode() if isinstance(body, str) else body
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)

        def do_GET(self):
            if self.path == "/healthz":
                self._send(200, json.dumps({"status": "ok", "lambda_floor": LAMBDA_FLOOR}))
            elif self.path == "/metrics":
                self._send(200, metrics_text(), "text/plain")
            else:
                self._send(404, "{}")

        def do_POST(self):
            if self.path != "/v1/traces":
                self._send(404, "{}")
                return
            n = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(n) or b"{}")
            summary = process_otlp(payload)
            self._send(200, json.dumps({"partialSuccess": {}, "szl": summary}))

        def log_message(self, *a):
            pass

    HTTPServer((host, port), H).serve_forever()


try:  # uvicorn entrypoint: `uvicorn collector.app:app`
    app = build_fastapi()
except Exception:  # pragma: no cover
    app = None

if __name__ == "__main__":  # pragma: no cover
    if app is not None:
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "4318")))
    else:
        run_stdlib(port=int(os.environ.get("PORT", "4318")))
