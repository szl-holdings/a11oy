# SPDX-License-Identifier: Apache-2.0
"""Hatun's mesh uses the same observed backend as the Ayllu brain contract."""
import asyncio
import sys
from types import SimpleNamespace

import pytest
from starlette.applications import Starlette
from starlette.testclient import TestClient

from ayllu import backend
from ayllu.model_binding import second_brain_binding
import szl_agentic_loop as loop


@pytest.mark.parametrize("available", [True, False])
def test_mesh_uses_exact_backend_observation_without_minting(monkeypatch, available):
    runtime = {"forge_profiles": {"profiles": {"BrainNavigator-v1": {
        "expected_model": "khipu:latest",
        "available": available,
        "served_model": "khipu:latest" if available else None,
    }}}}
    rag = {"built": True, "chunks": 4, "state": "READY"}
    calls = {"backend": 0, "signer": 0}

    def observed_backend():
        calls["backend"] += 1
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            calls["outside_event_loop"] = True
        else:
            calls["outside_event_loop"] = False
        return runtime

    def signer(_payload):
        calls["signer"] += 1
        raise AssertionError("read-only mesh must not sign")

    monkeypatch.setattr(backend, "backend_status", observed_backend)
    monkeypatch.setitem(sys.modules, "a11oy_org_rag", SimpleNamespace(status=lambda: rag))
    monkeypatch.setitem(sys.modules, "szl_formulas", SimpleNamespace(FORMULA_NAMES=[]))
    monkeypatch.setitem(sys.modules, "szl_anatomy_routes", SimpleNamespace(CHAKRAS=[]))
    app = Starlette()
    loop.register(app, "a11oy", signer)
    with TestClient(app) as client:
        response = client.get("/api/a11oy/v1/hatun/mesh")
    assert response.status_code == 200
    mesh = response.json()
    expected = second_brain_binding(namespace="a11oy", backend_status=runtime, rag_status=rag)
    assert mesh["second_brain"]["state"] == expected["state"]
    assert mesh["second_brain"]["ready_for_grounded_navigation"] is available
    assert mesh["get_mints_receipt"] is False
    assert calls == {"backend": 1, "signer": 0, "outside_event_loop": True}


def test_backend_read_failure_keeps_built_index_unavailable(monkeypatch):
    def unavailable():
        raise RuntimeError("backend status unavailable")

    monkeypatch.setattr(backend, "backend_status", unavailable)
    monkeypatch.setitem(sys.modules, "a11oy_org_rag", SimpleNamespace(
        status=lambda: {"built": True, "chunks": 4, "state": "READY"}))
    monkeypatch.setitem(sys.modules, "szl_formulas", SimpleNamespace(FORMULA_NAMES=[]))
    monkeypatch.setitem(sys.modules, "szl_anatomy_routes", SimpleNamespace(CHAKRAS=[]))
    app = Starlette()
    loop.register(app, "a11oy", None)
    with TestClient(app) as client:
        response = client.get("/api/a11oy/v1/hatun/mesh")
    brain = response.json()["second_brain"]
    assert brain["state"] == "UNAVAILABLE"
    assert brain["ready_for_grounded_navigation"] is False
    assert brain["index_built"] is True
