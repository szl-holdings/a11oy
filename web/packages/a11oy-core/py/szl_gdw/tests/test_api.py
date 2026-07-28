#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173

import sys

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

import szl_dsse
from szl_gdw import api
from szl_gdw.persistence import PersistenceError


@pytest.fixture(autouse=True)
def unsigned_runtime(monkeypatch):
    monkeypatch.setattr(szl_dsse, "_load_private_key", lambda: None)


@pytest.fixture
def client(tmp_path):
    app = FastAPI()
    api.register(app, db_path=tmp_path / "api.sqlite3")
    return TestClient(app)


def _step_body(request="advance", key="idem-1"):
    return {
        "idempotency_key": key,
        "request": request,
        "evidence": [
            {
                "evidence_id": "evidence-1",
                "uri": "urn:szl:test:evidence-1",
                "content_hash": "a" * 64,
                "trust": 0.8,
                "observed_at": "2026-07-28T00:00:00+00:00",
            }
        ],
        "allowed_experts": ["modeled-expert"],
        "risk_budget": 0.5,
    }


def test_status_session_step_receipt_and_exact_replay(client):
    status = client.get("/api/a11oy/v1/gdw/status")
    assert status.status_code == 200
    assert status.json()["label"] == "MODELED"
    assert status.json()["runtime_ready"] is True
    assert status.json()["storage_ready"] is True
    assert status.json()["citations"][0]["identifier"].startswith("arXiv:")

    created = client.post(
        "/api/a11oy/v1/gdw/sessions",
        json={"session_id": "api-1", "risk_budget": 0.5},
    )
    assert created.status_code == 201
    assert created.json()["receipt"]["dsse"]["signed"] is False

    first = client.post(
        "/api/a11oy/v1/gdw/sessions/api-1/step", json=_step_body()
    )
    replay = client.post(
        "/api/a11oy/v1/gdw/sessions/api-1/step", json=_step_body()
    )
    assert first.status_code == 200, first.text
    assert first.json()["decision"] == "ACCEPT"
    assert first.json()["replayed"] is False
    assert replay.status_code == 200
    assert replay.json()["replayed"] is True
    expected = first.json()
    expected["replayed"] = True
    assert replay.json() == expected

    receipt_id = first.json()["khipu_receipt"]["receipt_id"]
    receipt = client.get(f"/api/a11oy/v1/gdw/receipts/{receipt_id}")
    assert receipt.status_code == 200
    assert receipt.json()["receipt"]["request_digest"]
    assert receipt.json()["dsse"]["signed"] is False
    assert receipt.json()["label"] == "MODELED"


def test_gets_and_aggregate_do_not_mint_or_change_storage(
    client, monkeypatch
):
    calls = 0
    original = szl_dsse.sign_khipu_receipt

    def counted(payload):
        nonlocal calls
        calls += 1
        return original(payload)

    monkeypatch.setattr(szl_dsse, "sign_khipu_receipt", counted)
    created = client.post(
        "/api/a11oy/v1/gdw/sessions", json={"session_id": "read-only"}
    )
    receipt_id = created.json()["receipt"]["receipt"]["receipt_id"]
    assert calls == 1
    before = client.get("/api/a11oy/v1/gdw/telemetry").json()["storage"][
        "counts"
    ]

    for path in (
        "/api/a11oy/v1/gdw/status",
        "/api/a11oy/v1/gdw/sessions/read-only",
        f"/api/a11oy/v1/gdw/receipts/{receipt_id}",
        "/api/a11oy/v1/gdw/telemetry",
    ):
        response = client.get(path)
        assert response.status_code == 200
        assert response.json()["label"] == "MODELED"

    aggregate = client.post(
        "/api/a11oy/v1/gdw/aggregate",
        json={"sources": [[[[1.0, 2.0]]]]},
    )
    assert aggregate.status_code in (200, 503)
    assert calls == 1
    after = client.get("/api/a11oy/v1/gdw/telemetry").json()["storage"][
        "counts"
    ]
    assert after == before


def test_aggregate_bounds_and_backend_unavailable(client, monkeypatch):
    oversized = [[[[1.0]]]] * (api.MAX_BATCH + 1)
    response = client.post(
        "/api/a11oy/v1/gdw/aggregate", json={"sources": oversized}
    )
    assert response.status_code == 422
    assert response.json()["label"] == "MODELED"

    monkeypatch.setitem(sys.modules, "torch", None)
    unavailable = client.post(
        "/api/a11oy/v1/gdw/aggregate",
        json={"sources": [[[[1.0, 2.0]]]]},
    )
    assert unavailable.status_code == 503
    assert unavailable.json()["status"] == "UNAVAILABLE"
    assert unavailable.json()["performance_claim"] == "UNAVAILABLE"


def test_raw_request_body_limit_is_checked_before_json_validation(client):
    oversized = b'{"sources":[],"padding":"' + (
        b"x" * api.MAX_BODY_BYTES
    ) + b'"}'

    response = client.post(
        "/api/a11oy/v1/gdw/aggregate",
        content=oversized,
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 422
    assert response.json()["label"] == "MODELED"
    assert response.json()["error"] == "INVALID_INPUT"


def test_aggregate_success_when_torch_is_installed(client):
    pytest.importorskip("torch")
    response = client.post(
        "/api/a11oy/v1/gdw/aggregate",
        json={"sources": [[[[1.0, 2.0], [3.0, 4.0]]]], "lam": 0.25},
    )
    assert response.status_code == 200, response.text
    assert response.json()["label"] == "MODELED"
    assert response.json()["shape"] == [1, 1, 2]
    assert response.json()["certificate"]["label"] == "MODELED"


def test_degraded_registration_keeps_routes_and_fails_writes(
    monkeypatch,
):
    def unavailable(*args, **kwargs):
        raise PersistenceError("unavailable")

    monkeypatch.setattr(api, "SQLiteWorkspaceStore", unavailable)
    app = FastAPI()
    registration = api.register(app)
    degraded = TestClient(app)

    status = degraded.get("/api/a11oy/v1/gdw/status")
    write = degraded.post(
        "/api/a11oy/v1/gdw/sessions", json={"session_id": "blocked"}
    )

    assert registration["storage_ready"] is False
    assert status.status_code == 200
    assert status.json()["storage_ready"] is False
    assert status.json()["runtime_ready"] is False
    assert status.json()["storage"]["status"] == "UNAVAILABLE"
    assert write.status_code == 503
    assert write.json()["label"] == "MODELED"
