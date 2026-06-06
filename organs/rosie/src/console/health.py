"""rosie.console.health — /healthz payload + stdlib HTTP server.

A dependency-free health surface for the operator-console backend. The
payload carries build identity (git SHA + boot timestamp), an ``otel`` flag,
and the live mesh-health summary so a probe confirms not just "process up"
but "console can compute". The two consequential reads exposed here
(``verify_receipt`` and ``mesh query``) are wrapped in telemetry spans.

Run standalone:

    python -m src.console.health           # serves on 0.0.0.0:$ROSIE_PORT (8800)

Endpoints:
    GET /healthz   -> 200 build identity + mesh summary
    GET /mesh      -> 200 full mesh-health rollup
    GET /spans     -> 200 span fixture (with provenance)
    POST /verify   -> 200 receipt verdict (body = DSSE envelope JSON)

SPDX-License-Identifier: Apache-2.0
"""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from . import mesh as mesh_mod
from . import spans as spans_mod
from . import version as version_mod
from .receipt_verifier import verify_receipt_json
from .telemetry import get_logger, otel_active, span


def health_payload() -> dict[str, Any]:
    """Build the /healthz JSON payload. Never raises."""
    info = version_mod.build_info()
    fixture = spans_mod.generate_spans()
    summary = mesh_mod.mesh_health(fixture)
    return {
        "ok": True,
        **info,
        "otel": otel_active(),
        "components": list(spans_mod.COMPONENTS),
        "mesh": {
            "total_spans": summary.total_spans,
            "total_errors": summary.total_errors,
            "overall_error_rate_pct": summary.overall_error_rate_pct,
            "alert": summary.alert,
        },
    }


def mesh_query() -> dict[str, Any]:
    """Consequential read: compute the full mesh-health rollup (span-wrapped)."""
    with span("mesh_query"):
        fixture = spans_mod.generate_spans()
        result = mesh_mod.mesh_health(fixture)
        get_logger().info(
            "mesh_query",
            extra={"total_spans": result.total_spans, "alert": result.alert},
        )
        return result.as_dict()


def verify_receipt(envelope_json: str) -> dict[str, Any]:
    """Consequential read: verify a DSSE envelope (span-wrapped)."""
    with span("verify_receipt"):
        result = verify_receipt_json(envelope_json)
        get_logger().info(
            "verify_receipt",
            extra={"verdict": result.verdict.value, "ok": result.ok},
        )
        return {
            "verdict": result.verdict.value,
            "ok": result.ok,
            "message": result.message,
            "keyid": result.keyid,
            "payload": result.payload,
        }


def spans_view(limit: int = spans_mod.DEFAULT_SPAN_COUNT) -> dict[str, Any]:
    """Span Explorer read: fixture spans + explicit provenance."""
    fixture = spans_mod.filter_spans(spans_mod.generate_spans(), limit=limit)
    return {
        "provenance": spans_mod.provenance(),
        "count": len(fixture),
        "spans": [s.as_dict() for s in fixture],
    }


class HealthHandler(BaseHTTPRequestHandler):
    """Minimal stdlib request handler for the health surface."""

    server_version = "rosie-console/0.0.1"

    def _send(self, code: int, body: dict[str, Any]) -> None:
        payload = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args: Any) -> None:  # noqa: D401
        """Route access logs through the structured logger."""
        get_logger().info("http", extra={"path": getattr(self, "path", "?")})

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/healthz":
            self._send(200, health_payload())
        elif self.path == "/mesh":
            self._send(200, mesh_query())
        elif self.path.startswith("/spans"):
            self._send(200, spans_view())
        else:
            self._send(404, {"ok": False, "error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/verify":
            self._send(404, {"ok": False, "error": "not found"})
            return
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8") if length else ""
        self._send(200, verify_receipt(body))


def serve(host: str = "0.0.0.0", port: int | None = None) -> None:
    """Start the stdlib health server (blocking)."""
    get_logger()
    port = port if port is not None else int(os.environ.get("ROSIE_PORT", "8800"))
    httpd = ThreadingHTTPServer((host, port), HealthHandler)
    get_logger().info("serving", extra={"host": host, "port": port})
    httpd.serve_forever()


if __name__ == "__main__":
    serve()
