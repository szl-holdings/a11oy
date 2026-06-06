"""Shared pytest fixtures for rosie tests.

Provides ``a11oy_server``: a real stdlib http.server on an ephemeral port that
mimics a11oy's `serve` route contract, used by the a11oy-client integration
tests so every call crosses a real socket (no mocked transport).

SPDX-License-Identifier: Apache-2.0
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest


class _A11oyLikeHandler(BaseHTTPRequestHandler):
    """Mimics the a11oy `serve` route surface."""

    def log_message(self, *args):  # silence test output
        return

    def _send(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        if self.path == "/healthz":
            return self._send(200, {"status": "ok", "sha": "abc123", "ts": "2026-05-31T00:00:00Z"})
        if self.path == "/readyz":
            return self._send(200, {"status": "ready", "ledger": "/tmp/x.jsonl"})
        if self.path.startswith("/v1/ledger/"):
            h = self.path[len("/v1/ledger/"):]
            return self._send(200, {"receipt": {"receipt_id": h}})
        if self.path.startswith("/v1/ledger"):
            limit = 20
            if "limit=" in self.path:
                limit = int(self.path.split("limit=")[1])
            return self._send(200, {"count": 1, "total": 1,
                                    "receipts": [{"receipt_id": "r-1", "limit": limit}]})
        return self._send(404, {"error": "not found", "path": self.path})

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("content-length", 0))
        body = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        if self.path == "/v1/verify":
            ledger = body.get("ledger", [])
            valid = isinstance(ledger, list) and len(ledger) > 0
            return self._send(200, {"valid": valid, "broken_at": None if valid else 0,
                                    "errors": [] if valid else ["position 0: empty"]})
        if self.path == "/v1/policy/evaluate":
            sev = body.get("action", {}).get("severity", "medium")
            allow = sev in ("low", "medium")
            return self._send(200, {"decision": "allow" if allow else "deny",
                                    "gate": "thresholdPolicySeverity",
                                    "receipt_hash": "sig-xyz" if allow else "",
                                    "rationale": f"severity={sev}"})
        return self._send(404, {"error": "not found", "path": self.path})


@pytest.fixture()
def a11oy_server():
    server = HTTPServer(("127.0.0.1", 0), _A11oyLikeHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        yield base
    finally:
        server.shutdown()
        server.server_close()
