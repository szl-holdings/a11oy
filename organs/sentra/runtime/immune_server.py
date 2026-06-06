#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. -- SZL Holdings
# ORCID: 0009-0001-0110-4173
#
# immune_server.py -- SENTRA's inbound immune endpoint (Wire B of the anatomy mesh).
#
# The mining report found sentra (the immune organ) wire-isolated: no sibling
# repo calls it at runtime (anatomy-alive layer 7 = NOT-YET-WIRED). This module
# gives sentra a small HTTP surface so a11oy can delegate egress/threat verdicts
# to the immune system before admitting an action -- without a11oy duplicating
# the threat logic.
#
# Stdlib only (http.server) -- no FastAPI/uvicorn dependency, so the immune
# endpoint boots with zero install. It wraps the *real* sentra_inspect() from
# src/sentra_immune.py; there is no mocked verdict path.
#
# Route:
#   GET  /healthz             -> 200 {"status":"ok"}
#   POST /v1/inspect          -> 200 PolicyDecision-shaped verdict
#       request:  {"action": {... arbitrary action body ...},
#                  "actionId": "...", "traceparent": "00-...-...-01"}
#       response: {"actionId","decision":"allow"|"deny","gate":"sentra.immune.signature-scan",
#                  "decidedBy":"sentra.immune","rationale":"...","lambdaScore":0|1,
#                  "receiptHash":"","traceparent":"<child of inbound>"}
#
# The response is shaped to @szl-holdings/anatomy-contracts PolicyDecision so
# a11oy can surface a sentra deny verbatim. traceparent is propagated: the
# response carries a child span-id of the inbound traceparent (same trace-id),
# which is how the nervous-system wire (Wire E) ties the immune call into the
# parent trace.

from __future__ import annotations

import json
import os
import re
import secrets
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

# Import the real immune function from the sibling module.
_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from sentra_immune import sentra_inspect  # noqa: E402  (path set above)

# Frontier F1 (round11): O(1)-memory online latency anomaly gate (Welford 1962).
# Additive observability only -- it NEVER changes an allow/deny decision. Enabled when
# SENTRA_IMMUNE_LATENCY_GATE is set; off by default so the PolicyDecision shape is
# unchanged for existing callers.
# Lean: Lutar/Innovations/round11/FrontierWelfordVariance.lean
try:
    from welford_gate import WelfordGate  # noqa: E402  (sibling runtime module)
except Exception:  # pragma: no cover - module optional in minimal deployments
    WelfordGate = None  # type: ignore

_LATENCY_GATE = (
    WelfordGate(z_threshold=4.0)
    if (WelfordGate is not None and os.environ.get("SENTRA_IMMUNE_LATENCY_GATE"))
    else None
)

_TRACEPARENT_RE = re.compile(r"^00-[0-9a-f]{32}-[0-9a-f]{16}-[0-9a-f]{2}$")


def is_valid_traceparent(value: str) -> bool:
    if not isinstance(value, str) or not _TRACEPARENT_RE.match(value):
        return False
    trace_id = value[3:35]
    parent_id = value[36:52]
    if trace_id == "0" * 32 or parent_id == "0" * 16:
        return False
    return True


def new_traceparent() -> str:
    return f"00-{secrets.token_hex(16)}-{secrets.token_hex(8)}-01"


def child_traceparent(parent: str) -> str:
    """Same trace-id as parent, fresh span-id. Establishes parent->child."""
    if not is_valid_traceparent(parent):
        return new_traceparent()
    trace_id = parent[3:35]
    flags = parent[53:55]
    return f"00-{trace_id}-{secrets.token_hex(8)}-{flags}"


def inspect_action(action: Any, action_id: str, inbound_traceparent: str) -> dict[str, Any]:
    """Run the real immune inspection and return a PolicyDecision-shaped dict."""
    packet = action if isinstance(action, dict) else {"value": action}
    clean = sentra_inspect(packet)
    return {
        "actionId": action_id,
        "decision": "allow" if clean else "deny",
        "gate": "sentra.immune.signature-scan",
        "decidedBy": "sentra.immune",
        "rationale": (
            "no threat signature detected by the immune system"
            if clean
            else "immune system rejected: threat signature or size guard tripped"
        ),
        "lambdaScore": 1 if clean else 0,
        "receiptHash": "",
        "traceparent": child_traceparent(inbound_traceparent),
    }


class ImmuneHandler(BaseHTTPRequestHandler):
    server_version = "sentra-immune/0.1"

    def _send(self, status: int, body: dict[str, Any]) -> None:
        payload = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json; charset=utf-8")
        self.send_header("content-length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args: Any) -> None:  # quiet by default
        if os.environ.get("SENTRA_IMMUNE_VERBOSE"):
            super().log_message(*args)

    def do_GET(self) -> None:
        if self.path == "/healthz":
            self._send(200, {"status": "ok"})
            return
        self._send(404, {"error": "not found", "path": self.path})

    def do_POST(self) -> None:
        if self.path != "/v1/inspect":
            self._send(404, {"error": "not found", "path": self.path})
            return
        length = int(self.headers.get("content-length", "0") or "0")
        if length > 8 * 1024 * 1024:
            self._send(413, {"error": "request body too large"})
            return
        raw = self.rfile.read(length) if length else b"{}"
        try:
            parsed = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self._send(400, {"error": "invalid JSON body"})
            return
        if not isinstance(parsed, dict) or "action" not in parsed:
            self._send(400, {"error": "body must be {action: {...}}"})
            return
        # traceparent may come in the header or the body; header wins.
        inbound = self.headers.get("traceparent") or parsed.get("traceparent", "")
        action_id = str(parsed.get("actionId", "unspecified-action"))
        t0 = time.perf_counter()
        verdict = inspect_action(parsed["action"], action_id, inbound or "")
        # Frontier F1: record /verdict latency online and annotate (never gate on) drift.
        if _LATENCY_GATE is not None:
            latency_ms = (time.perf_counter() - t0) * 1000.0
            ann = _LATENCY_GATE.observe(latency_ms)
            verdict["latencyMs"] = round(latency_ms, 4)
            verdict["latencyAnomaly"] = ann["anomaly"]
            verdict["latencyZScore"] = ann["zscore"]
        self._send(200, verdict)


def make_server(host: str = "0.0.0.0", port: int = 8090) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), ImmuneHandler)


def main() -> None:
    host = os.environ.get("SENTRA_IMMUNE_HOST", "0.0.0.0")
    port = int(os.environ.get("SENTRA_IMMUNE_PORT", "8090"))
    srv = make_server(host, port)
    bound = srv.server_address
    print(
        json.dumps({"msg": "sentra immune listening", "host": bound[0], "port": bound[1]}),
        flush=True,
    )
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()


if __name__ == "__main__":
    main()
