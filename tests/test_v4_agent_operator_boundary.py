# SPDX-License-Identifier: Apache-2.0
"""Offline checks for the public v4 voter boundary; no model network calls."""

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

import a11oy_v4_agent as agent
import a11oy_v4_hickok as hickok


@pytest.fixture
def agent_client(monkeypatch):
    calls = []

    class StubVoter:
        def __init__(self, voter_id):
            self.VOTER_ID = voter_id

        async def vote(self, **kwargs):
            calls.append((self.VOTER_ID, kwargs))
            return {
                "voter_id": self.VOTER_ID,
                "status": "ok",
                "text": "fixture response",
                "provenance": {},
            }

    sovereign = StubVoter(agent.SOVEREIGN_VOTER_ID)
    cloud = StubVoter("hf-inference-llama")

    def resolve(requested):
        return [sovereign, cloud] if requested and cloud.VOTER_ID in requested else [sovereign]

    monkeypatch.setattr(agent, "resolve_voters", resolve)
    monkeypatch.setattr(agent, "_make_receipt", lambda payload: {"signed": False})
    monkeypatch.setenv("A11OY_CODE_ADMIN_KEY", "test-only-operator-key")
    app = FastAPI()
    agent.register(app)
    return TestClient(app), calls


@pytest.mark.parametrize("authorization", [None, "Bearer wrong-test-key"])
def test_anonymous_or_wrong_key_cannot_run_cloud_voter(agent_client, authorization):
    client, calls = agent_client
    headers = {"Authorization": authorization} if authorization else {}
    response = client.post(
        "/api/a11oy/v4/agent/ask",
        json={"prompt": "hello", "voters": ["hf-inference-llama"]},
        headers=headers,
    )
    assert response.status_code == 401
    assert response.json()["status"] == "BLOCKED"
    assert response.headers["cache-control"] == "no-store"
    assert calls == []


def test_operator_still_blocked_without_hard_budget_admission(agent_client):
    client, calls = agent_client
    response = client.post(
        "/api/a11oy/v4/agent/ask",
        json={"prompt": "hello", "voters": ["hf-inference-llama"]},
        headers={"Authorization": "Bearer test-only-operator-key"},
    )
    assert response.status_code == 503
    assert response.json()["status"] == "BLOCKED"
    assert "hard budget admission unavailable" in response.json()["reason"]
    assert response.headers["cache-control"] == "no-store"
    assert calls == []


@pytest.mark.parametrize("voters", [None, ["khipu-gguf"]])
def test_public_sovereign_only_demo_still_works(agent_client, voters):
    client, calls = agent_client
    response = client.post(
        "/api/a11oy/v4/agent/ask",
        json={"prompt": "hello", "voters": voters},
    )
    assert response.status_code == 200
    assert [voter_id for voter_id, _ in calls] == [agent.SOVEREIGN_VOTER_ID]


@pytest.mark.parametrize("body", [
    {"prompt": "x" * 4097},
    {"prompt": "hello", "system": "x" * 1025},
    {"prompt": "hello", "voters": ["khipu-gguf"] * (agent.VOTER_COUNT + 1)},
])
def test_oversized_fields_reject_before_any_vote(agent_client, body):
    client, calls = agent_client
    response = client.post("/api/a11oy/v4/agent/ask", json=body)
    assert response.status_code == 422
    assert calls == []


def test_oversized_body_rejected_before_json_parse_or_vote(agent_client):
    client, calls = agent_client
    response = client.post(
        "/api/a11oy/v4/agent/ask",
        json={"prompt": "x" * agent.AGENT_ASK_MAX_BODY_BYTES},
    )
    assert response.status_code == 413
    assert response.json()["status"] == "BLOCKED"
    assert calls == []


def test_streamed_oversized_body_rejected_without_content_length(agent_client):
    client, calls = agent_client
    chunks = iter([b'{"prompt":"', b"x" * agent.AGENT_ASK_MAX_BODY_BYTES, b'"}'])
    response = client.post(
        "/api/a11oy/v4/agent/ask",
        content=chunks,
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 413
    assert response.json()["status"] == "BLOCKED"
    assert calls == []


def test_hickok_middleware_caps_body_and_reinjects_normal_request(agent_client, monkeypatch):
    _, calls = agent_client
    assert hickok.AGENT_ASK_MAX_BODY_BYTES == agent.AGENT_ASK_MAX_BODY_BYTES
    monkeypatch.setattr(hickok, "_sign", lambda *_args, **_kwargs: {"dsse": {"signed": False}})
    app = FastAPI()
    agent.register(app)
    hickok.register(app)
    client = TestClient(app)

    too_large = client.post(
        "/api/a11oy/v4/agent/ask",
        json={"prompt": "x" * agent.AGENT_ASK_MAX_BODY_BYTES},
    )
    assert too_large.status_code == 413
    assert calls == []

    normal = client.post("/api/a11oy/v4/agent/ask", json={"prompt": "hello"})
    assert normal.status_code == 200, normal.text
    assert [voter_id for voter_id, _ in calls] == [agent.SOVEREIGN_VOTER_ID]


def test_hickok_does_not_sign_denied_or_oversized_agent_requests(agent_client, monkeypatch):
    _, voter_calls = agent_client
    emissions = []

    def sign(*args, **kwargs):
        emissions.append((args, kwargs))
        return {"dsse": {"signed": False}}

    monkeypatch.setattr(hickok, "_sign", sign)
    app = FastAPI()
    agent.register(app)
    hickok.register(app)
    client = TestClient(app)
    cloud_request = {"prompt": "hello", "voters": ["hf-inference-llama"]}

    anonymous = client.post("/api/a11oy/v4/agent/ask", json=cloud_request)
    assert anonymous.status_code == 401
    assert emissions == []
    assert voter_calls == []

    operator = client.post(
        "/api/a11oy/v4/agent/ask",
        json=cloud_request,
        headers={"Authorization": "Bearer test-only-operator-key"},
    )
    assert operator.status_code == 503
    assert emissions == []
    assert voter_calls == []

    oversized = client.post(
        "/api/a11oy/v4/agent/ask",
        json={"prompt": "x" * agent.AGENT_ASK_MAX_BODY_BYTES},
    )
    assert oversized.status_code == 413
    assert emissions == []
    assert voter_calls == []

    sovereign = client.post("/api/a11oy/v4/agent/ask", json={"prompt": "hello"})
    assert sovereign.status_code == 200
    assert [voter_id for voter_id, _ in voter_calls] == [agent.SOVEREIGN_VOTER_ID]
    assert len(emissions) == 1
    assert emissions[0][0][0] == "router_classify"


def test_public_page_does_not_offer_unauthorized_cloud_selection():
    html = agent._build_agent_html()
    assert 'value="khipu-gguf" checked disabled' in html
    assert 'value="hf-inference-llama" disabled' in html
    assert "This public page runs only the sovereign voter" in html
    assert "Additional fan-out is BLOCKED" in html
    assert "a11oy · Governed Agent" in html
    assert "1 public voter" in html
    assert "Ask Khipu" in html
    assert "Ask the ensemble" not in html
    assert "A11OY_CODE_ADMIN_KEY" not in html
    assert "Authorization" not in html


def test_voter_catalog_distinguishes_provider_and_caller_availability(agent_client):
    client, _ = agent_client
    response = client.get("/api/a11oy/v4/agent/voters")
    assert response.status_code == 200
    by_id = {v["voter_id"]: v for v in response.json()["voters"]}
    assert by_id["khipu-gguf"]["requires_operator"] is False
    assert by_id["khipu-gguf"]["anonymous_permitted"] is True
    assert by_id["hf-inference-llama"]["requires_operator"] is True
    assert by_id["hf-inference-llama"]["anonymous_permitted"] is False
    assert by_id["hf-inference-llama"]["hard_budget_admission"] == "UNAVAILABLE"
    assert by_id["hf-inference-llama"]["status"] == "BLOCKED"


def test_configured_cloud_voter_is_still_reported_blocked(agent_client, monkeypatch):
    client, _ = agent_client

    class CatalogVoter:
        def __init__(self, voter_id):
            self.VOTER_ID = voter_id

        def is_available(self):
            return True

        def metadata(self):
            return {"voter_id": self.VOTER_ID, "status": "available"}

    monkeypatch.setattr(agent, "get_all_voters", lambda: [
        CatalogVoter(agent.SOVEREIGN_VOTER_ID),
        CatalogVoter("hf-inference-llama"),
    ])
    by_id = {v["voter_id"]: v for v in client.get(
        "/api/a11oy/v4/agent/voters"
    ).json()["voters"]}
    assert by_id["khipu-gguf"]["status"] == "available"
    assert by_id["hf-inference-llama"]["status"] == "BLOCKED"
    assert by_id["hf-inference-llama"]["anonymous_permitted"] is False
