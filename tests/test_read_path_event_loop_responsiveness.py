# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Real read handlers must yield the ASGI loop while their probe transports wait."""
import ast
import sys
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import MethodType, SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

import szl_backend_hardening as bh
import szl_energy_operator as operator
import szl_frontier_manifest as manifest
import szl_llm_registry as registry
import szl_sovereign_panel as sovereign_panel

ROOT = Path(__file__).resolve().parents[1]


def compile_handlers(filename, names, scope):
    source = ROOT / filename
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    nodes = [node for node in ast.walk(tree)
             if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names]
    assert len(nodes) == len(names)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), "exec"), scope)


def configure_fabric(monkeypatch, wait):
    def blocked_connect(*args, **kwargs):
        wait()
        return False, "synthetic unreachable transport"

    monkeypatch.setattr(bh, "_tcp_connect_once", blocked_connect)
    monkeypatch.setattr(bh, "_FABRIC_CACHE", bh.TTLCache(ttl=30))
    monkeypatch.setattr(bh, "DEFAULT_FABRIC_NODES", [
        {"name": "synthetic", "kind": "cpu", "probe": ("127.0.0.1", 9), "sovereign": False}])
    monkeypatch.setattr(bh, "rented_gpu_nodes", lambda: ([], []))
    monkeypatch.setattr(manifest, "_TILE_SPECS", [
        (manifest._tile_compute_fabric, "Sovereign compute fabric", "compute", {})])
    monkeypatch.setattr(manifest, "_concept_tile_inference_provenance", lambda: {
        "name": "synthetic", "category": "test", "label": "UNAVAILABLE", "ok": False})
    monkeypatch.setattr(manifest, "_tile_governance", lambda app: {
        "signature_verified": False, "signer_health": {}})


@pytest.mark.parametrize("lane", [
    "readyz", "health_frontier", "health_sovereign", "sovereign_health",
    "compute_pool", "compute_pool_hardened", "compute_anchor", "frontier_manifest",
    "frontier_sovereign",
])
def test_blocked_probe_does_not_stall_unrelated_async_request(monkeypatch, lane):
    app = FastAPI()
    entered = threading.Event()
    release = threading.Event()

    def wait():
        entered.set()
        assert release.wait(10), "test did not release transport"

    @app.get("/audit/ping")
    async def ping():
        return {"ok": True}

    if lane == "readyz":
        class Response:
            status = 200
            def getcode(self): return 200
            def __enter__(self): return self
            def __exit__(self, *args): return None

        class Opener:
            def open(self, *args, **kwargs):
                wait()
                return Response()

        monkeypatch.setattr(urllib.request, "build_opener", lambda *args: Opener())
        op = SimpleNamespace(nodes=[SimpleNamespace(base_url="http://127.0.0.1:9/v1")],
                             is_running=lambda: False)
        op.any_lung_reachable = MethodType(operator.OperatorDaemon.any_lung_reachable, op)
        monkeypatch.setattr(operator, "get_operator", lambda: op)
        monkeypatch.setattr(operator, "operator_required", lambda: False)
        monkeypatch.setitem(sys.modules, "a11oy_state_store", SimpleNamespace(enabled=lambda: False))
        scope = {"app": app, "JSONResponse": JSONResponse,
                 "os": SimpleNamespace(environ={}), "sys": SimpleNamespace(modules={})}
        compile_handlers("serve.py", {"readyz"}, scope)
        path = "/api/a11oy/readyz"
    elif lane in {"health_frontier", "health_sovereign"}:
        async def dependency():
            return {"status": "ok", "backend_alive": True}

        scope = {
            "app": app, "JSONResponse": JSONResponse, "_healthz_dep_ping": dependency,
            "_ledger_storage_signal": lambda: {"status": "available"},
            "_signer_availability_signal": lambda: {"status": "ABSENT"},
            "_frontier_liveness_signal": lambda: {"status": "unavailable"},
            "_sovereign_health_signal": lambda: {}, "_brain_health_signal": lambda: {},
            "_preflight_signal": lambda: {"overall": "DEGRADED"},
            "sys": SimpleNamespace(modules={}), "_hz_time": time,
            "_A11OY_START_TIME": time.time(), "_gates_list": [],
            "_A11OY_SLSA_TEXT": "SLSA L1 source-declared",
            "_SOVEREIGN_HZ_CACHE": {}, "_SOVEREIGN_HZ_LOCK": threading.Lock(),
        }
        if lane == "health_frontier":
            configure_fabric(monkeypatch, wait)
            helper = "_frontier_liveness_signal"
        else:
            def blocked_http(*args, **kwargs):
                wait()
                return None, "TIMEOUT"
            monkeypatch.setattr(registry, "_bounded_http_json", blocked_http)
            helper = "_sovereign_health_signal"
        compile_handlers("serve.py", {helper, "healthz"}, scope)
        path = "/api/a11oy/healthz"
    elif lane in {"sovereign_health", "frontier_sovereign"}:
        def blocked_http(*args, **kwargs):
            wait()
            return None, "TIMEOUT"
        monkeypatch.setattr(registry, "_bounded_http_json", blocked_http)
        monkeypatch.setattr(registry, "_sovereign_node_urls", lambda: ["http://127.0.0.1:9/v1"])
        if lane == "sovereign_health":
            scope = {**vars(registry), "app": app, "JSONResponse": JSONResponse}
            compile_handlers("szl_llm_registry.py", {"llm_sovereign_health"}, scope)
            path = "/api/a11oy/v1/llm/sovereign/health"
        else:
            sovereign_panel.register(app)
            path = "/api/a11oy/v1/frontier/sovereign"
    else:
        configure_fabric(monkeypatch, wait)
        if lane == "frontier_manifest":
            manifest.register(app)
            path = "/api/a11oy/v1/frontier/manifest"
        else:
            bh.register(app)
            path = "/api/a11oy/v1/" + lane.replace("_", "-")

    # Both requests use the same persistent ASGI portal, not separate event loops.
    with TestClient(app) as client, ThreadPoolExecutor(max_workers=2) as workers:
        probe = workers.submit(client.get, path)
        try:
            assert entered.wait(5), "route did not reach its probe transport"
            other = workers.submit(client.get, "/audit/ping")
            try:
                assert other.result(timeout=2).json() == {"ok": True}
            except TimeoutError:
                pytest.fail("probe transport blocked the shared ASGI event loop")
            assert not probe.done()
        finally:
            release.set()
        response = probe.result(timeout=5)

    assert response.status_code == (503 if lane == "readyz" else 200)
    body = response.json()
    if lane == "readyz":
        assert body["operator"]["reason"] == "operator_stopped_while_lung_reachable"
    elif lane == "health_sovereign":
        assert body["rollup"]["sovereign"]["label"] == "UNAVAILABLE"
    elif lane == "sovereign_health":
        assert body["reachable"] is False
        assert body["label"] == "UNAVAILABLE"
    elif lane == "frontier_sovereign":
        assert body["endpoint_reachable"] is False
        assert body["label"] == "UNAVAILABLE"
        assert body["receipt_status"]["receipt_minted"] is False
    elif lane == "frontier_manifest":
        assert body["summary"]["operational_readiness"]["ready"] is False
