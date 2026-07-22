#!/usr/bin/env python3
from __future__ import annotations

import inspect
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

import szl_brain_capabilities

ROOT = Path(__file__).resolve().parents[1]


def _methods(app: FastAPI, path: str) -> set[str]:
    return {
        method
        for route in app.routes
        if getattr(route, "path", None) == path
        for method in getattr(route, "methods", set())
    }


def test_brain_manifest_and_operational_head_routes_are_real() -> None:
    app = FastAPI()
    result = szl_brain_capabilities.register(app, runtime_status={})
    assert result == "brain-capabilities-wired:4"

    assert {"GET", "HEAD"}.issubset(
        _methods(app, "/api/a11oy/v1/brain/capabilities")
    )
    assert {"GET", "HEAD"}.issubset(
        _methods(app, "/api/a11oy/v1/brain/capabilities/info")
    )
    assert "HEAD" in _methods(app, "/api/livez")
    assert "HEAD" in _methods(app, "/api/build-info")
    assert "HEAD" in _methods(app, "/api/a11oy/v1/readiness/tab-matrix")

    client = TestClient(app)
    get_response = client.get("/api/a11oy/v1/brain/capabilities")
    head_response = client.head("/api/a11oy/v1/brain/capabilities")
    assert get_response.status_code == 200
    assert get_response.json()["schema"] == "szl.brain-capabilities.v1"
    assert head_response.status_code == 200
    assert head_response.content == b""


def test_holographic_operations_surface_is_deployed_and_accessible() -> None:
    page = ROOT / "console" / "3d" / "holographic.html"
    source = page.read_text(encoding="utf-8")
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert 'lang="en"' in source
    assert 'name="viewport"' in source
    assert 'class="skip"' in source
    assert 'aria-live="polite"' in source
    assert "prefers-reduced-motion" in source
    assert "A11oy Holographic Operations" in source
    assert "The estate, observed—not assumed." in source
    assert "/api/livez" in source
    assert "/api/build-info" in source
    assert "/api/a11oy/v1/brain/capabilities" in source
    assert "/api/a11oy/v1/readiness/tab-matrix?view=summary" in source
    assert "https://" not in source
    assert "http://" not in source
    assert "COPY console/ ./static/" in dockerfile


def test_permanent_sync_binds_source_and_relocks_live_routes() -> None:
    workflow = (ROOT / ".github" / "workflows" / "hf-sync.yml").read_text(
        encoding="utf-8"
    )
    for required in (
        "key='SZL_GIT_SHA'",
        "needs: bind-source",
        "needs: deploy",
        "/api/livez",
        "/api/build-info",
        "/api/a11oy/v1/brain/capabilities",
        "/api/a11oy/v1/readiness/tab-matrix?view=summary",
        "/static/3d/holographic.html",
        "requests.head(",
        "requests.get(",
        "szl.a11oy-deployment-relock/v3",
        "RELOCK_ISSUE: \"1043\"",
        "a11oy-clone-{index}",
    ):
        assert required in workflow

    for forbidden in (
        "duplicate_repo(",
        "create_repo(",
        "delete_repo(",
        "update_repo_settings(",
        "restart_space(",
        "request_space_hardware(",
        "set_space_hardware(",
    ):
        assert forbidden not in workflow


def test_capability_source_has_no_mutation_route() -> None:
    source = inspect.getsource(szl_brain_capabilities.register)
    for method in ("POST", "PUT", "PATCH", "DELETE"):
        assert f'"{method}"' not in source
