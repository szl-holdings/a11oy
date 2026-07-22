# SPDX-License-Identifier: Apache-2.0
"""Real-socket regression tests for the bounded Wire-D cross-mesh slice."""

from __future__ import annotations

import json
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from fastapi import FastAPI
from fastapi.testclient import TestClient

import szl_provenance as provenance


@contextmanager
def _peer(*, preserve_trace_id: bool, redirect_to: str | None = None):
    class PeerHandler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            if redirect_to:
                self.send_response(302)
                self.send_header("Location", redirect_to)
                self.end_headers()
                return
            incoming = self.headers.get("traceparent")
            parsed = provenance.parse_traceparent(incoming)
            trace_id = (
                parsed["trace_id"]
                if preserve_trace_id and parsed.get("valid")
                else provenance.new_trace_id()
            )
            echoed = f"00-{trace_id}-{provenance.new_span_id()}-01"
            body = json.dumps({"state": "READY", "traceparent": echoed}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("traceparent", echoed)
            self.send_header("x-szl-space", "test-peer")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):  # noqa: A002
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), PeerHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/api/test-peer/wires/D"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def _client(monkeypatch, target_url: str) -> TestClient:
    monkeypatch.setenv("A11OY_WIRE_D_TARGETS", json.dumps({"peer": target_url}))
    monkeypatch.setenv("A11OY_WIRE_D_ALLOWED_HOSTS", "127.0.0.1")
    monkeypatch.delenv("SZL_COSIGN_PRIVATE_PEM", raising=False)
    app = FastAPI()
    provenance.register_provenance(app, "a11oy")
    return TestClient(app)


def test_real_peer_hop_preserves_trace_id_and_mints_honest_receipt(monkeypatch):
    parent = "00-0123456789abcdef0123456789abcdef-0123456789abcdef-01"
    with _peer(preserve_trace_id=True) as target_url:
        with _client(monkeypatch, target_url) as client:
            before = client.get("/api/a11oy/v1/wire-d/status").json()
            assert before["state"] == "READY_UNMEASURED"
            assert before["measured_hops"] == 0
            assert before["receipt_minted_on_get"] is False

            response = client.post(
                "/api/a11oy/v1/wire-d/probe",
                headers={"traceparent": parent},
                json={"target": "peer"},
            )
            assert response.status_code == 200
            body = response.json()
            assert body["state"] == "MEASURED"
            assert body["trace_id_continuity"] is True
            assert provenance.parse_traceparent(body["traceparent_sent"])["trace_id"] == parent.split("-")[1]
            assert provenance.parse_traceparent(body["traceparent_echoed"])["trace_id"] == parent.split("-")[1]
            assert body["latency_ms"] >= 0
            assert body["receipt_digest"]
            assert body["receipt_signed"] is False
            assert "127.0.0.1" not in str(body)

            after = client.get("/api/a11oy/v1/wire-d/status").json()
            assert after["state"] == "MEASURED"
            assert after["measured_hops"] == 1
            assert after["recent"][0]["digest"] == body["receipt_digest"]
            assert after["recent"][0]["trace_id_continuity"] is True
            assert after["anatomy"]["current"] == "v5"
            assert after["anatomy"]["v6"] == "NOT_CLAIMED"
            assert "127.0.0.1" not in str(after)


def test_peer_trace_id_conflict_fails_closed_and_is_receipted(monkeypatch):
    with _peer(preserve_trace_id=False) as target_url:
        with _client(monkeypatch, target_url) as client:
            response = client.post("/api/a11oy/v1/wire-d/probe", json={"target": "peer"})
            assert response.status_code == 502
            body = response.json()
            assert body["state"] == "CONFLICT"
            assert body["trace_id_continuity"] is False
            assert body["receipt_digest"]
            status = client.get("/api/a11oy/v1/wire-d/status").json()
            assert status["state"] == "DEGRADED"
            assert status["conflicted_or_unavailable_hops"] == 1


def test_request_cannot_supply_an_arbitrary_target_url(monkeypatch):
    with _peer(preserve_trace_id=True) as target_url:
        with _client(monkeypatch, target_url) as client:
            response = client.post(
                "/api/a11oy/v1/wire-d/probe",
                json={"target": "unknown", "url": "http://169.254.169.254/latest/meta-data"},
            )
            assert response.status_code == 422
            assert response.json()["state"] == "DENIED"
            ledger = client.get("/api/a11oy/khipu/ledger").json()
            assert ledger["count"] == 0


def test_configured_peer_redirect_is_not_followed_and_is_receipted_as_conflict(monkeypatch):
    metadata_url = "http://169.254.169.254/latest/meta-data"
    with _peer(preserve_trace_id=True, redirect_to=metadata_url) as target_url:
        with _client(monkeypatch, target_url) as client:
            response = client.post("/api/a11oy/v1/wire-d/probe", json={"target": "peer"})
            assert response.status_code == 502
            body = response.json()
            assert body["state"] == "CONFLICT"
            assert body["http_status"] == 302
            assert metadata_url not in str(body)
            status = client.get("/api/a11oy/v1/wire-d/status").json()
            assert status["conflicted_or_unavailable_hops"] == 1


def test_wire_d_parser_rejects_non_v00_or_unsupported_flags():
    valid = "00-0123456789abcdef0123456789abcdef-0123456789abcdef-01"
    assert provenance.parse_traceparent(valid)["valid"] is True
    assert provenance.parse_traceparent("01" + valid[2:])["valid"] is False
    assert provenance.parse_traceparent(valid[:-2] + "03")["valid"] is False
