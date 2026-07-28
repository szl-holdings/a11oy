#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173

"""End-to-end contract tests for the Wave 26 Governed Delta Workspace."""

from __future__ import annotations

import base64
from hashlib import sha256
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from szl_gdw.api import register
from szl_gdw.kernel_adapter import GovernedWorkspaceKernel


def _allow_governance(_action):
    return {
        "allowed": True,
        "decision": "ALLOW",
        "reason_codes": ["TEST_FILE_BACKED_GOVERNANCE_PASS"],
    }


def _client(tmp_path: Path) -> TestClient:
    app = FastAPI()
    registration = register(
        app,
        kernel=GovernedWorkspaceKernel(),
        governance_gate=_allow_governance,
        db_path=tmp_path / "workspace.sqlite3",
        persistent_required=False,
    )
    assert registration["runtime_ready"] is True
    assert registration["storage_ready"] is True
    return TestClient(app)


def test_create_step_replay_read_and_aggregate(tmp_path):
    client = _client(tmp_path)
    status = client.get("/api/a11oy/v1/gdw/status")
    assert status.status_code == 200
    assert status.json()["label"] == "MODELED"
    assert status.json()["runtime_ready"] is True

    created = client.post(
        "/api/a11oy/v1/gdw/sessions",
        json={"session_id": "series-a-test", "risk_budget": 0.5},
    )
    assert created.status_code == 201
    create_body = created.json()
    assert create_body["receipt"]["dsse"]["signed"] in (True, False)
    assert create_body["receipt"]["receipt"]["receipt_type"] == "session.create"
    state_hash_before = create_body["state_hash"]

    request = {
        "idempotency_key": "step-1",
        "request": "compute a bounded governed delta",
        "evidence": [],
        "allowed_experts": ["expert-a"],
        "risk_budget": 0.5,
    }
    stepped = client.post(
        "/api/a11oy/v1/gdw/sessions/series-a-test/step",
        json=request,
    )
    assert stepped.status_code == 200
    body = stepped.json()
    assert body["decision"] == "ACCEPT"
    assert body["state"]["step"] == 1
    assert body["state_hash"] != state_hash_before
    assert body["khipu_receipt"]["signed"] in (True, False)
    assert body["replayed"] is False

    read_once = client.get(
        "/api/a11oy/v1/gdw/sessions/series-a-test"
    ).json()
    replayed = client.post(
        "/api/a11oy/v1/gdw/sessions/series-a-test/step",
        json=request,
    )
    read_twice = client.get(
        "/api/a11oy/v1/gdw/sessions/series-a-test"
    ).json()
    assert replayed.status_code == 200
    assert replayed.json()["replayed"] is True
    assert replayed.json()["state_hash"] == body["state_hash"]
    assert replayed.json()["khipu_receipt"] == body["khipu_receipt"]
    assert read_once["revision"] == read_twice["revision"] == 1
    assert read_once["state_hash"] == read_twice["state_hash"]

    conflict = client.post(
        "/api/a11oy/v1/gdw/sessions/series-a-test/step",
        json={**request, "request": "different payload"},
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"] == "IDEMPOTENCY_CONFLICT"

    aggregate = client.post(
        "/api/a11oy/v1/gdw/aggregate",
        json={
            "sources": [[[[1.0, 4.0], [4.0, 1.0]]]],
            "lam": 0.25,
            "egyptian": True,
            "depth": 2,
        },
    )
    assert aggregate.status_code == 200
    aggregate_body = aggregate.json()
    assert aggregate_body["label"] == "MODELED"
    assert aggregate_body["performance_claim"] == "UNAVAILABLE"
    assert aggregate_body["certificate"]["cert_sha256"]


def test_request_bounds_and_read_only_routes(tmp_path):
    client = _client(tmp_path)
    assert (
        client.post(
            "/api/a11oy/v1/gdw/aggregate",
            content=b"{" + b"x" * 1_100_000 + b"}",
            headers={"content-type": "application/json"},
        ).status_code
        == 422
    )
    client.post(
        "/api/a11oy/v1/gdw/sessions",
        json={"session_id": "read-only", "risk_budget": 1.0},
    )
    before = client.get("/api/a11oy/v1/gdw/telemetry").json()["storage"][
        "counts"
    ]
    client.get("/api/a11oy/v1/gdw/status")
    client.get("/api/a11oy/v1/gdw/sessions/read-only")
    after = client.get("/api/a11oy/v1/gdw/telemetry").json()["storage"][
        "counts"
    ]
    assert before == after


def test_missing_required_mount_registers_honest_degraded_routes(tmp_path):
    app = FastAPI()
    register(
        app,
        kernel=GovernedWorkspaceKernel(),
        db_path=tmp_path / "not-mounted" / "workspace.sqlite3",
        persistent_required=True,
        required_mount=tmp_path / "not-mounted",
    )
    client = TestClient(app)
    status = client.get("/api/a11oy/v1/gdw/status")
    assert status.status_code == 200
    assert status.json()["runtime_ready"] is False
    assert status.json()["storage"]["status"] == "UNAVAILABLE"
    refused = client.post(
        "/api/a11oy/v1/gdw/sessions",
        json={"session_id": "must-not-persist"},
    )
    assert refused.status_code == 503


def test_operator_assets_are_exact_byte_digest_and_gets_mint_nothing():
    import serve

    client = TestClient(serve.app)
    telemetry_path = "/api/a11oy/v1/gdw/telemetry"
    before = client.get(telemetry_path)
    page = client.get("/gdw")
    script = client.get("/gdw/app.js")
    styles = client.get("/gdw/styles.css")
    after = client.get(telemetry_path)

    assert page.status_code == script.status_code == styles.status_code == 200
    assert page.headers["cache-control"] == "no-store"
    for response in (page, script, styles):
        expected = "sha-256=:" + base64.b64encode(
            sha256(response.content).digest()
        ).decode("ascii") + ":"
        assert response.headers["content-digest"] == expected
        assert response.headers["x-content-type-options"] == "nosniff"
    assert {"GET", "HEAD"}.issubset(
        {
            method
            for route in serve.app.router.routes
            if getattr(route, "path", None) == "/gdw"
            for method in getattr(route, "methods", set())
        }
    )
    # On an attached store telemetry remains byte-stable except wall-clock-free
    # counters; without the mount both reads fail identically and mint nothing.
    assert before.status_code == after.status_code
    if before.status_code == 200:
        assert before.json()["storage"]["counts"] == after.json()["storage"]["counts"]
