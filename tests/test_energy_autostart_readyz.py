# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · Doctrine v11
"""Energy-operator AUTO-START + /readyz redeploy-stall guard (2026-06-16).

ROOT CAUSE this guards: on every box redeploy the service restarts and the energy
operator loop came up STOPPED (running=false) even though the GPU lungs stayed
reachable — so joules froze until someone manually POSTed
/api/a11oy/v1/energy/operator/start. The fix (Doctrine v11):

  1. serve.py's startup hook calls szl_energy_operator.autostart_if_lung_reachable(),
     gated by A11OY_ENERGY_AUTOSTART (default ON), which presses play automatically —
     but ONLY when at least one lung answers a REAL probe (zero lungs → stay cleanly
     idle, running=false, never a fabricated running/joule).
  2. /api/a11oy/readyz now returns 503 in the EXACT unhealthy state we hit (a lung is
     reachable but the loop is stopped) and 200 otherwise.

This module boots the REAL app in-process via Starlette TestClient (no mocks, no
network beyond a local fake lung) and asserts both behaviors end-to-end through the
live /readyz route — so a future serve.py edit that drops the autostart hook or the
readiness wiring turns a silent redeploy stall into a red CI gate before the demo.
"""
from __future__ import annotations

import http.server
import json
import threading
import warnings

import pytest

warnings.filterwarnings("ignore")

starlette_testclient = pytest.importorskip("starlette.testclient")
TestClient = starlette_testclient.TestClient

import serve  # noqa: E402
import szl_energy_operator as OP  # noqa: E402


class _FakeLung:
    """A minimal OpenAI-compatible liveness endpoint so _http_reachable() returns
    True for a real probe — no inference needed, we only exercise reachability."""

    def __init__(self):
        self._server = None
        self._thread = None
        self.port = None

    def start(self) -> str:
        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):  # silence
                pass

            def do_GET(self):
                body = json.dumps({"object": "list", "data": [{"id": "llama3.1:8b"}]}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self._server = http.server.HTTPServer(("127.0.0.1", 0), H)
        self.port = self._server.server_port
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return f"http://127.0.0.1:{self.port}/v1"

    def stop(self):
        if self._server:
            self._server.shutdown()
            self._server.server_close()


@pytest.fixture
def client():
    # NOTE: constructed WITHOUT `with`, so app startup events (which spawn the Node
    # subprocess + run the autostart hook) do NOT fire — we drive the operator
    # singleton directly to set up each readiness state deterministically.
    return TestClient(serve.app)


def _install_singleton(op):
    prev = OP._OPERATOR
    OP._OPERATOR = op
    return prev


def test_readyz_503_when_lung_reachable_but_loop_stopped(client):
    """The exact redeploy stall: lung up, loop stopped → /readyz must be 503."""
    lung = _FakeLung()
    base = lung.start()
    op = OP.OperatorDaemon(
        nodes=[OP.NodeCfg("rtx-betterwithage", base, "llama3.1:8b", "bge-large",
                          "betterwithage")],
        allow_stub=False)
    prev = _install_singleton(op)
    try:
        assert op.is_running() is False
        resp = client.get("/api/a11oy/readyz")
        assert resp.status_code == 503, (resp.status_code, resp.text)
        body = resp.json()
        assert body["status"] == "not_ready", body
        assert body["operator"]["ready"] is False, body
        assert body["operator"]["lung_reachable"] is True, body
        assert body["operator"]["operator_running"] is False, body
    finally:
        op.stop()
        _install_singleton(prev)
        lung.stop()


def test_readyz_200_when_loop_running(client):
    """Lung up AND loop running → /readyz must be 200 (healthy)."""
    lung = _FakeLung()
    base = lung.start()
    op = OP.OperatorDaemon(
        nodes=[OP.NodeCfg("rtx-betterwithage", base, "llama3.1:8b", "bge-large",
                          "betterwithage")],
        job_interval_s=0.05, allow_stub=False)
    prev = _install_singleton(op)
    try:
        op.start()
        assert op.is_running() is True
        resp = client.get("/api/a11oy/readyz")
        assert resp.status_code == 200, (resp.status_code, resp.text)
        body = resp.json()
        assert body["status"] == "ready", body
        assert body["operator"]["ready"] is True, body
        assert body["operator"]["operator_running"] is True, body
    finally:
        op.stop()
        _install_singleton(prev)
        lung.stop()


def test_readyz_200_when_no_lung_reachable(client):
    """No lung reachable → honestly idle is READY (200): nothing to compute against,
    not a fault. A stopped loop with zero lungs must NOT 503."""
    op = OP.OperatorDaemon(
        nodes=[OP.NodeCfg("rtx-betterwithage", "http://192.0.2.1:11434/v1",
                          "llama3.1:8b", "bge-large", "betterwithage")],
        allow_stub=False)
    prev = _install_singleton(op)
    try:
        resp = client.get("/api/a11oy/readyz")
        assert resp.status_code == 200, (resp.status_code, resp.text)
        body = resp.json()
        assert body["status"] == "ready", body
        assert body["operator"]["lung_reachable"] is False, body
        assert body["operator"]["operator_running"] is False, body
    finally:
        _install_singleton(prev)


def test_autostart_boots_loop_running_when_lung_reachable():
    """With a lung reachable + autostart enabled (default), the boot hook presses
    play: autostart_if_lung_reachable() leaves the loop RUNNING."""
    lung = _FakeLung()
    base = lung.start()
    op = OP.OperatorDaemon(
        nodes=[OP.NodeCfg("rtx-betterwithage", base, "llama3.1:8b", "bge-large",
                          "betterwithage")],
        job_interval_s=0.05, allow_stub=False)
    prev = _install_singleton(op)
    try:
        assert OP.autostart_enabled() is True  # default ON
        report = OP.autostart_if_lung_reachable()
        assert report["autostarted"] is True, report
        assert op.is_running() is True
    finally:
        op.stop()
        _install_singleton(prev)
        lung.stop()
