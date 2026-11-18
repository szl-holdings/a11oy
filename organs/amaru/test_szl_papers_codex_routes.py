# SPDX-License-Identifier: Apache-2.0
"""Regression: FastAPI mounted sub-app paths must not duplicate their mount prefix."""
from __future__ import annotations

import importlib.util
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

SOURCE = Path(__file__).with_name("szl_papers_codex.py")
spec = importlib.util.spec_from_file_location("_szl_papers_codex_under_test", SOURCE)
assert spec is not None and spec.loader is not None
codex = importlib.util.module_from_spec(spec)
spec.loader.exec_module(codex)


def test_mounted_api_is_reachable_at_exact_public_urls():
    root, subapp = FastAPI(), FastAPI()
    root.mount("/api/amaru", subapp)
    registered = codex.register(root, ns="amaru", api_app=subapp)
    with TestClient(root) as client:
        for route in ("/api/amaru/v1/papers", "/api/amaru/v1/codex-kernel",
                      "/api/amaru/v1/papers/healthz", "/papers"):
            response = client.get(route)
            assert response.status_code == 200, (route, response.status_code)
        assert client.get("/api/amaru/v1/papers").json()["count"] == len(codex.PAPERS)
        assert client.get("/api/amaru/v1/codex-kernel").json()["codex_kernel"]["package"] == "@workspace/codex-kernel"
        assert client.get("/api/amaru/v1/papers/healthz").json()["ok"] is True
        for duplicate in ("/api/amaru/api/amaru/v1/papers",
                          "/api/amaru/api/amaru/v1/codex-kernel",
                          "/api/amaru/api/amaru/v1/papers/healthz"):
            assert client.get(duplicate).status_code == 404
    assert "/api/amaru/v1/papers" in registered["routes"]


def test_root_registration_keeps_full_prefix():
    root = FastAPI()
    codex.register(root, ns="amaru")
    with TestClient(root) as client:
        assert client.get("/api/amaru/v1/papers").status_code == 200
        assert client.get("/api/amaru/v1/codex-kernel").status_code == 200
        assert client.get("/api/amaru/v1/papers/healthz").status_code == 200
        assert client.get("/v1/papers").status_code == 404
