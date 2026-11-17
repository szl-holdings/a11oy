# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Legacy Khipu routes expose metadata and retire inference without side effects."""
import asyncio
import json
import socket
import urllib.request

import httpx
import pytest
from fastapi import FastAPI
from starlette.requests import Request
from starlette.testclient import TestClient

import a11oy_khipu_chat as chat
from szl_be_hardening import DOCTRINE_LOCK


@pytest.fixture(autouse=True)
def no_egress(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("retired Khipu route attempted outbound transport")
    monkeypatch.setattr(httpx, "AsyncClient", forbidden)
    monkeypatch.setattr(urllib.request, "urlopen", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)


@pytest.fixture
def proxy_client():
    app = FastAPI()
    chat.register(app)
    with TestClient(app) as client:
        yield client, app


def _assert_retired(body):
    assert body["state"] == body["lab_status"] == "RETIRED"
    assert body["ok"] is False and body["operational"] is False
    assert body["inference_performed"] is False
    assert body["receipt_emitted"] is False
    assert body["automatically_forwarded"] is False
    assert body["text"] is None and body["elapsed_ms"] is None
    assert body["record_sha256"] == body["signature"] == "UNKNOWN"
    assert body["receipt_evidence_label"] == "UNAVAILABLE"
    assert "receipt" not in body and "signatures" not in body
    successor = body["successor"]
    assert successor["method"] == "POST"
    assert successor["path"] == "/api/a11oy/v1/atelier/cpu-lab/turn"
    assert successor["ui"] == "/command-centre#cpu-work"
    assert successor["operator_authentication_required"] is True
    assert successor["public_share_acknowledged"] is True
    assert successor["declared"] == "PUBLIC"
    assert successor["max_output_tokens"] == 32
    assert successor["grounding_required"] is True
    assert successor["authority"] == "PROPOSAL_ONLY"
    assert successor["automatic_forwarding"] is False


@pytest.mark.parametrize("method", ["get", "head"])
def test_status_is_metadata_only_without_egress(proxy_client, method):
    client, _ = proxy_client
    response = getattr(client, method)("/api/a11oy/v1/khipu/status")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    if method == "get":
        body = response.json()
        _assert_retired(body)
        assert body["healthz"] is None
        assert body["health_observation"] == "NOT_PROBED"
        assert body["pin"]["generation_state"] == "RETIRED"
        assert body["pin"]["operational"] is False
        assert body["pin"]["model_rev"] == "67d60ec577730747055491640cfb91fc4a4b5d25"
        assert body["measured_probe"]["label"] == "UNAVAILABLE"
        assert body["doctrine"]["state"] == "LOCKED"
        assert body["doctrine"]["locked_formula_ids"] == DOCTRINE_LOCK["locked_formula_ids"]
        assert body["doctrine"]["lambda"] == DOCTRINE_LOCK["lambda"]


@pytest.mark.parametrize("payload", [
    {},
    {"prompt": "private prompt must not be forwarded"},
    {"prompt": "ack cannot revive legacy routing", "declared": "PUBLIC",
     "public_share_acknowledged": True},
])
def test_legacy_post_is_410_without_forwarding_or_receipt(proxy_client, payload):
    client, _ = proxy_client
    for _ in range(2):
        response = client.post("/api/a11oy/v1/khipu/chat", json=payload,
                               headers={"Authorization": "Bearer test-only"})
        assert response.status_code == 410
        assert response.headers["cache-control"] == "no-store"
        assert "location" not in response.headers
        _assert_retired(response.json())
        assert "prompt" not in response.json()


def test_retired_post_never_reads_body():
    async def forbidden_receive():
        pytest.fail("retirement handler consumed a prompt body")
    request = Request({"type": "http", "method": "POST", "path": "/legacy", "headers": []},
                      receive=forbidden_receive)
    response = asyncio.run(chat._handle_chat(request))
    assert response.status_code == 410
    _assert_retired(json.loads(response.body))


def test_registration_is_idempotent_and_precedes_fallback():
    app = FastAPI()
    app.add_api_route("/api/a11oy/{path:path}", lambda path: {"fallback": True})
    chat.register(app)
    chat.register(app)
    for path in (chat._STATUS_PATH, chat._CHAT_PATH):
        matches = [route for route in app.router.routes if getattr(route, "path", None) == path]
        assert len(matches) == 1
    with TestClient(app) as client:
        response = client.post(chat._CHAT_PATH, json={"prompt": "never forwarded"})
        assert response.status_code == 410
        _assert_retired(response.json())


@pytest.mark.parametrize("ids,count", [
    ([{}], 1), ([[]], 1), (["F1"], True), (["F1", "F1"], 2),
    (["invalid"], 1), (["F1"], 2),
    (["F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9"], 9),
    (["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F23"], 8),
])
def test_malformed_doctrine_is_unavailable(proxy_client, monkeypatch, ids, count):
    client, _ = proxy_client
    monkeypatch.setattr(chat, "DOCTRINE_LOCK", {
        **DOCTRINE_LOCK, "locked_formula_ids": ids, "locked_formula_count": count,
    })
    response = client.get("/api/a11oy/v1/khipu/status")
    doctrine = response.json()["doctrine"]
    assert doctrine["state"] == doctrine["version"] == "UNAVAILABLE"
    assert doctrine["locked_formula_count"] is None
    assert doctrine["locked_formula_ids"] == []
