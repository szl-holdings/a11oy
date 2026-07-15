# SPDX-License-Identifier: Apache-2.0
"""Assembled-app and container wiring checks for Yupaq compute."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from unittest.mock import patch

from starlette.testclient import TestClient

import serve
import szl_yupaq_compute as compute


ROOT = Path(__file__).resolve().parents[1]
CLIENT = TestClient(serve.app)
TEST_TOKEN = "yupaq-route-test-authority"
AUTH_ENV = {"A11OY_COMPUTE_TOKEN_SHA256": hashlib.sha256(
    TEST_TOKEN.encode("utf-8")).hexdigest()}
AUTH_HEADERS = {"Authorization": f"Bearer {TEST_TOKEN}"}
ROUTES = {
    "/api/a11oy/v1/compute/capabilities",
    "/api/a11oy/v1/compute/jobs",
    "/api/a11oy/v1/compute/jobs/{job_id}",
    "/api/a11oy/v1/compute/receipts/{job_id}",
    "/api/a11oy/v1/compute/receipts/verify",
}


def payload(job_id: str = "route-lambda-1") -> dict:
    return {
        "schema": compute.JOB_SCHEMA,
        "job_id": job_id,
        "operation": "formula.org_lambda.weighted_geomean",
        "inputs": {"axes": [0.9, 0.8], "weights": [0.5, 0.5]},
        "resource_budget": {"max_runtime_ms": 2_000, "max_output_bytes": 64 * 1024},
    }


def test_routes_are_real_local_and_precede_both_catchalls():
    ordered = [getattr(route, "path", None) for route in serve.app.router.routes]
    assert ROUTES <= set(ordered)
    proxy = ordered.index("/api/a11oy/{path:path}")
    spa = ordered.index("/{full_path:path}")
    assert all(ordered.index(path) < proxy and ordered.index(path) < spa for path in ROUTES)
    assert "v1/compute/" in serve._LOCAL_ONLY_A11OY_PREFIXES


def test_capabilities_disclose_real_boundaries():
    response = CLIENT.get("/api/a11oy/v1/compute/capabilities")
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "BOUNDED_TYPED_OPERATIONS_ONLY"
    assert body["arbitrary_code_allowed"] is False
    assert body["arbitrary_urls_allowed"] is False
    assert body["brain_nodes"] == 9464
    assert body["brain_nodes_in_gradients"] == 0
    assert body["lanes"]["lambda"] == "ADVISORY_CONJECTURE_1_OPEN"
    assert body["authorization"]["stateful_routes_require_bearer"] is True
    assert body["authorization"]["replay_scope"] == "PROCESS_LOCAL_BOUNDED"


def test_job_route_executes_and_exposes_receipt_without_touching_real_lake():
    with compute._STORE_LOCK:
        compute._STORE.clear()
        compute._REQUEST_BINDINGS.clear()
    fake_lake = {
        "accepted": True,
        "duplicate": False,
        "receipt_id": "fixture",
        "organ": "yupaq-compute",
        "chain_index": 1,
        "chain_head": "a" * 64,
    }
    with patch.dict(os.environ, AUTH_ENV), patch.object(
        compute, "_append_to_lake", return_value=fake_lake
    ):
        response = CLIENT.post(
            "/api/a11oy/v1/compute/jobs", json=payload(), headers=AUTH_HEADERS)
    assert response.status_code == 200
    body = response.json()
    assert body["result"]["state"] == "COMPLETED"
    assert body["receipt"]["request_sha256"] == body["request_sha256"]
    assert body["receipt"]["result_sha256"] == body["result_sha256"]
    assert body["lake"]["accepted"] is True

    with patch.dict(os.environ, AUTH_ENV):
        fetched = CLIENT.get(
            "/api/a11oy/v1/compute/jobs/route-lambda-1", headers=AUTH_HEADERS)
    assert fetched.status_code == 200
    assert fetched.json()["result_sha256"] == body["result_sha256"]


def test_route_rejects_hidden_effectors_and_oversize_bodies():
    hidden = payload("hidden-effector")
    hidden["inputs"]["url"] = "https://example.com"
    with patch.dict(os.environ, AUTH_ENV):
        rejected = CLIENT.post(
            "/api/a11oy/v1/compute/jobs", json=hidden, headers=AUTH_HEADERS)
    assert rejected.status_code == 422
    assert rejected.json()["proof_uplift"] == rejected.json()["trust_uplift"] == 0

    with patch.dict(os.environ, AUTH_ENV):
        oversized = CLIENT.post(
            "/api/a11oy/v1/compute/jobs",
            content=b'{"padding":"' + b"x" * (128 * 1024) + b'"}',
            headers={"content-type": "application/json", **AUTH_HEADERS},
        )
    assert oversized.status_code == 413
    assert "128 KiB" in oversized.json()["error"]


def test_stateful_routes_fail_closed_without_compute_authority():
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("A11OY_COMPUTE_TOKEN_SHA256", None)
        unavailable = CLIENT.post("/api/a11oy/v1/compute/jobs", json=payload("no-auth"))
    assert unavailable.status_code == 503
    assert unavailable.json()["state"] == "UNAVAILABLE"

    with patch.dict(os.environ, AUTH_ENV):
        denied = CLIENT.post(
            "/api/a11oy/v1/compute/jobs",
            json=payload("wrong-auth"),
            headers={"Authorization": "Bearer wrong"},
        )
    assert denied.status_code == 401
    assert denied.json()["state"] == "UNAUTHORIZED"


def test_container_explicitly_copies_compute_plane_without_new_engine_installs():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "COPY szl_yupaq_compute.py ./" in dockerfile
    yupaq_block = "\n".join(
        line for line in dockerfile.splitlines() if "yupaq" in line.lower()
    )
    assert "pip install" not in yupaq_block
    assert "apt-get install" not in yupaq_block
