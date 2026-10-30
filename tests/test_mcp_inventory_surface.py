# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Manifest changes propagate to advertised counts without health network reads."""
import ast
import io
import json
import sys
import time
import urllib.request
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

import szl_brain as brain


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(brain, "_MCP_INVENTORY_OBSERVATION", None)
    monkeypatch.setitem(sys.modules, "szl_anatomy_routes", SimpleNamespace())
    app = FastAPI()

    async def dependency():
        return {"status": "ok", "backend_alive": True}

    # Execute the real handlers, excluding unrelated startup integrations.
    scope = {
        "app": app, "JSONResponse": JSONResponse,
        "_healthz_dep_ping": dependency,
        "_ledger_storage_signal": lambda: {"status": "available"},
        "_signer_availability_signal": lambda: {"status": "ABSENT"},
        "_frontier_liveness_signal": lambda: {"status": "unavailable"},
        "_sovereign_health_signal": lambda: {},
        "_brain_health_signal": lambda: {},
        "_preflight_signal": lambda: {"overall": "DEGRADED"},
        "sys": SimpleNamespace(modules={}), "_hz_time": time,
        "_A11OY_START_TIME": time.time(), "_gates_list": [],
        "_A11OY_SLSA_TEXT": "SLSA L1 source-declared",
    }
    source = Path(__file__).resolve().parents[1] / "serve.py"
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    nodes = [node for node in tree.body if isinstance(node, ast.AsyncFunctionDef)
             and node.name in {"healthz", "list_gates", "a11oy_mcp_tools_inline"}]
    assert len(nodes) == 3
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), "exec"), scope)
    return TestClient(app)


def advertisements(client):
    health = client.get("/api/a11oy/healthz")
    gates = client.get("/api/a11oy/v1/gates")
    assert health.status_code == gates.status_code == 200
    return [health.json(), gates.json()["canonical"],
            brain.brain_payload("a11oy")["canonical"]]


def forbid_network(*args, **kwargs):
    raise AssertionError("Health and summary reads must not probe sibling tools")


def test_unobserved_inventory_is_unknown_without_network_reads(client, monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", forbid_network)
    for body in advertisements(client):
        assert body["mcp_tools"] is None
        assert body["mcp_inventory"]["reason"] == "MCP_MANIFEST_NOT_OBSERVED"
        assert body["mcp_inventory"]["capability_readiness_asserted"] is False


def test_manifest_growth_and_sibling_loss_update_every_count(client, monkeypatch):
    for sibling_count in (1, 3, 0):
        def sibling_response(*args, **kwargs):
            if sibling_count == 0:
                raise OSError("synthetic sibling outage")
            return io.BytesIO(json.dumps({"tools": [
                {"name": "synthetic-tool-%d" % i} for i in range(sibling_count)
            ]}).encode())

        monkeypatch.setattr(urllib.request, "urlopen", sibling_response)
        manifest = client.get("/api/a11oy/v1/mcp/tools").json()
        assert manifest["count"] == len(manifest["tools"]) == 7 + sibling_count
        monkeypatch.setattr(urllib.request, "urlopen", forbid_network)
        for body in advertisements(client):
            assert body["mcp_tools"] == manifest["count"]
            assert body["mcp_inventory"]["label"] == "CACHED"
            assert body["mcp_inventory"]["source"] == "/api/a11oy/v1/mcp/tools"


def test_unavailable_formula_module_is_not_counted(client, monkeypatch):
    monkeypatch.setitem(sys.modules, "szl_anatomy_routes", None)
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda *args, **kwargs: io.BytesIO(b'{"tools":[]}'))
    manifest = client.get("/api/a11oy/v1/mcp/tools").json()
    assert manifest["count"] == len(manifest["tools"]) == 4
    assert all(body["mcp_tools"] == manifest["count"] for body in advertisements(client))


def test_expired_observation_cannot_remain_an_advertised_count(client, monkeypatch):
    brain.observe_mcp_inventory({"tools": [{"name": "synthetic"}], "count": 9000}, space="a11oy")
    assert brain.mcp_inventory_snapshot("a11oy")["count"] == 1
    previous = brain._MCP_INVENTORY_OBSERVATION
    monkeypatch.setattr(brain, "_MCP_INVENTORY_OBSERVATION",
                        (previous[0] - brain._MCP_INVENTORY_MAX_AGE_S - 1, *previous[1:]))
    monkeypatch.setattr(urllib.request, "urlopen", forbid_network)
    for body in advertisements(client):
        assert body["mcp_tools"] is None
        assert body["mcp_inventory"]["reason"] == "MCP_MANIFEST_OBSERVATION_EXPIRED"


@pytest.mark.parametrize("tools", [None, {}, [None], [{"name": 12}], [{"name": " "}]])
def test_invalid_observation_cannot_retain_a_previous_count(client, tools):
    brain.observe_mcp_inventory({"tools": [{"name": "synthetic"}]}, space="a11oy")
    brain.observe_mcp_inventory({"tools": tools}, space="a11oy")
    assert brain.mcp_inventory_snapshot("a11oy")["count"] is None


@pytest.mark.parametrize("clock", [float("nan"), float("inf"), float("-inf"), -1.0])
def test_clock_anomalies_are_unavailable_and_json_safe(client, monkeypatch, clock):
    brain.observe_mcp_inventory({"tools": [{"name": "synthetic"}]}, space="a11oy")
    monkeypatch.setattr(brain, "time", SimpleNamespace(monotonic=lambda: clock))
    for body in advertisements(client):
        assert body["mcp_tools"] is None
        assert body["mcp_inventory"]["age_s"] is None
        assert body["mcp_inventory"]["reason"] == "MCP_MANIFEST_CLOCK_UNAVAILABLE"


def test_observation_clock_failure_cannot_break_manifest_serving(client, monkeypatch):
    def failed_clock():
        raise OSError("synthetic clock failure")

    monkeypatch.setattr(brain, "time", SimpleNamespace(monotonic=failed_clock))
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda *args, **kwargs: io.BytesIO(b'{"tools":[]}'))
    response = client.get("/api/a11oy/v1/mcp/tools")
    assert response.status_code == 200
    assert response.json()["count"] == len(response.json()["tools"])
    assert all(body["mcp_tools"] is None for body in advertisements(client))


def test_readiness_contract_describes_variable_inventory():
    root = Path(__file__).resolve().parents[1]
    matrix = json.loads((root / "tools/readiness-harness/tabs.json").read_text())
    note = matrix["endpoints"]["/api/a11oy/v1/mcp/tools"]["note"]
    assert "count is derived from the returned inventory" in note
    assert "4 real" not in note and "fabricated 12" not in note


def test_manifest_is_serialized_before_inventory_observation():
    source = (Path(__file__).resolve().parents[1] / "serve.py").read_text(encoding="utf-8")
    response_at = source.index("response = JSONResponse(manifest)")
    observe_at = source.index("observe_mcp_inventory(manifest, space=\"a11oy\")")
    assert response_at < observe_at
