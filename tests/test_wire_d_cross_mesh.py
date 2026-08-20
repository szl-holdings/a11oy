# SPDX-License-Identifier: Apache-2.0
"""Real-socket regression tests for the bounded Wire-D cross-mesh slice."""

from __future__ import annotations

import hashlib
import json
import socket
import threading
import time
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from fastapi import FastAPI
from fastapi.testclient import TestClient

import szl_provenance as provenance

_TEST_TOKEN = "wire-d-operator-test-token"


def _auth_headers() -> dict[str, str]:
    return {"authorization": f"Bearer {_TEST_TOKEN}"}


@contextmanager
def _peer(
    *, preserve_trace_id: bool, redirect_to: str | None = None,
    advertised_host: str = "127.0.0.1", slow_headers: bool = False,
):
    class PeerHandler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            if slow_headers:
                try:
                    self.wfile.write(b"HTTP/1.1 200 OK\r\nX-Slow: ")
                    self.wfile.flush()
                    for _ in range(40):
                        self.wfile.write(b"a")
                        self.wfile.flush()
                        time.sleep(0.05)
                except (BrokenPipeError, ConnectionResetError):
                    pass
                return
            if redirect_to:
                self.send_response(302)
                self.send_header("Location", redirect_to)
                self.end_headers()
                return
            incoming = self.headers.get("traceparent")
            parsed = provenance.parse_traceparent(incoming)
            trace_id = (f"{int(parsed['trace_id'], 16):032x}"
                        if preserve_trace_id and parsed.get("valid")
                        else provenance.new_trace_id())
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
        yield f"http://{advertised_host}:{server.server_port}/api/test-peer/wires/D"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def _client(monkeypatch, target_url: str) -> TestClient:
    monkeypatch.setenv("A11OY_WIRE_D_TARGETS", json.dumps({"peer": target_url}))
    monkeypatch.setenv("A11OY_WIRE_D_ALLOWED_HOSTS", target_url.split("//", 1)[1].split(":", 1)[0])
    monkeypatch.setenv("A11OY_COMPUTE_TOKEN_SHA256", hashlib.sha256(_TEST_TOKEN.encode()).hexdigest())
    monkeypatch.delenv("SZL_COSIGN_PRIVATE_PEM", raising=False)
    app = FastAPI()
    provenance.register_provenance(app, "a11oy")
    return TestClient(app)


def test_real_peer_hop_preserves_trace_id_and_mints_honest_receipt(monkeypatch):
    parent = "00-0123456789abcdef0123456789abcdef-0123456789abcdef-03"
    with _peer(preserve_trace_id=True) as target_url:
        with _client(monkeypatch, target_url) as client:
            before = client.get("/api/a11oy/v1/wire-d/status").json()
            assert before["state"] == "READY_UNMEASURED"
            assert before["measured_hops"] == 0
            assert before["receipt_minted_on_get"] is False

            response = client.post(
                "/api/a11oy/v1/wire-d/probe",
                headers={"traceparent": parent, **_auth_headers()},
                json={"target": "peer"},
            )
            assert response.status_code == 200
            body = response.json()
            assert body["state"] == "MEASURED"
            assert body["trace_id_continuity"] is True
            assert provenance.parse_traceparent(body["traceparent_sent"])["trace_id"] == parent.split("-")[1]
            assert provenance.parse_traceparent(body["traceparent_echoed"])["trace_id"] == parent.split("-")[1]
            assert body["traceparent_sent"].endswith("-03")
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
            in_process = client.get("/api/a11oy/wires/D").json()
            assert in_process["status"] == "LIVE"
            assert in_process["cross_mesh_status"] == "MEASURED"


def test_peer_trace_id_conflict_fails_closed_and_is_receipted(monkeypatch):
    with _peer(preserve_trace_id=False) as target_url:
        with _client(monkeypatch, target_url) as client:
            response = client.post(
                "/api/a11oy/v1/wire-d/probe", headers=_auth_headers(), json={"target": "peer"}
            )
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
                headers=_auth_headers(),
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
            response = client.post(
                "/api/a11oy/v1/wire-d/probe", headers=_auth_headers(), json={"target": "peer"}
            )
            assert response.status_code == 502
            body = response.json()
            assert body["state"] == "CONFLICT"
            assert body["http_status"] == 302
            assert metadata_url not in str(body)
            status = client.get("/api/a11oy/v1/wire-d/status").json()
            assert status["conflicted_or_unavailable_hops"] == 1


def test_wire_d_parser_rejects_non_v00_and_accepts_reserved_flag_bits():
    valid = "00-0123456789abcdef0123456789abcdef-0123456789abcdef-01"
    assert provenance.parse_traceparent(valid)["valid"] is True
    assert provenance.parse_traceparent("01" + valid[2:])["valid"] is False
    assert provenance.parse_traceparent(valid[:-2] + "03")["valid"] is True
    assert provenance.parse_traceparent(valid[:-2] + "ff")["valid"] is True
    assert provenance.parse_traceparent(valid[:-2] + "FF")["valid"] is False


def test_probe_requires_configured_valid_operator_authority(monkeypatch):
    with _peer(preserve_trace_id=True) as target_url:
        with _client(monkeypatch, target_url) as client:
            missing = client.post("/api/a11oy/v1/wire-d/probe", json={"target": "peer"})
            assert missing.status_code == 401
            assert missing.json()["state"] == "DENIED"
            invalid = client.post(
                "/api/a11oy/v1/wire-d/probe",
                headers={"authorization": "Bearer wrong"},
                json={"target": "peer"},
            )
            assert invalid.status_code == 401
            monkeypatch.delenv("A11OY_COMPUTE_TOKEN_SHA256")
            unavailable = client.post(
                "/api/a11oy/v1/wire-d/probe", headers=_auth_headers(), json={"target": "peer"}
            )
            assert unavailable.status_code == 503
            assert client.get("/api/a11oy/khipu/ledger").json()["count"] == 0


def test_probe_uses_the_policy_admitted_ip_after_dns_changes(monkeypatch):
    with _peer(preserve_trace_id=True, advertised_host="peer.test") as target_url:
        port = int(target_url.split(":")[2].split("/", 1)[0])

        def initial_resolution(host, resolved_port, *args, **kwargs):
            assert host == "peer.test"
            assert resolved_port == port
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", port))]

        monkeypatch.setattr(provenance.socket, "getaddrinfo", initial_resolution)
        with _client(monkeypatch, target_url) as client:
            def rebound_resolution(*args, **kwargs):
                return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("169.254.169.254", port))]

            monkeypatch.setattr(provenance.socket, "getaddrinfo", rebound_resolution)
            response = client.post(
                "/api/a11oy/v1/wire-d/probe", headers=_auth_headers(), json={"target": "peer"}
            )
            assert response.status_code == 200
            assert response.json()["state"] == "MEASURED"


def test_peer_hop_enforces_a_wall_clock_deadline(monkeypatch):
    monkeypatch.setattr(provenance, "_WIRE_D_HOP_TIMEOUT_SECONDS", 0.2)
    with _peer(preserve_trace_id=True, slow_headers=True) as target_url:
        with _client(monkeypatch, target_url) as client:
            started = time.monotonic()
            response = client.post(
                "/api/a11oy/v1/wire-d/probe", headers=_auth_headers(), json={"target": "peer"}
            )
            assert time.monotonic() - started < 1.0
            assert response.status_code == 502
            assert response.json()["state"] == "UNAVAILABLE"
            assert response.json()["error_type"] == "TimeoutError"


def test_wire_d_evidence_survives_unrelated_ledger_writes(monkeypatch):
    with _peer(preserve_trace_id=True) as target_url:
        with _client(monkeypatch, target_url) as client:
            response = client.post(
                "/api/a11oy/v1/wire-d/probe", headers=_auth_headers(), json={"target": "peer"}
            )
            assert response.status_code == 200
            for index in range(55):
                client.app.state.szl_emit_signed_receipt({"schema": "test.noise/v1", "index": index})
            status = client.get("/api/a11oy/v1/wire-d/status").json()
            assert status["state"] == "MEASURED"
            assert status["measured_hops"] == 1
            assert status["recent"][0]["digest"] == response.json()["receipt_digest"]
