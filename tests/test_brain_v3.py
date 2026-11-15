"""tests/test_brain_v3.py — BRAIN v3 Anthropic router (fail-closed contract).

Covers the serve.py honesty contract: no fabricated output, exact unblock
actions, workspace-header wiring for user-scoped Claude Platform keys, and the
model_not_found-only fallback ladder. No network access (the HTTP boundary is
stubbed at the module seam _post_messages).
"""
import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import szl_brain_v3 as bv3


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_WORKSPACE_ID", raising=False)
    app = FastAPI()
    bv3.register(app, "a11oy", "a11oy", build_sha="test")
    return TestClient(app)


def test_no_key_is_honest_503(client):
    r = client.post("/api/a11oy/v3/brain/chat", json={"messages": [{"role": "user", "content": "hi"}]})
    assert r.status_code == 503
    body = r.json()
    assert body["fabricated_output"] is False
    assert "ANTHROPIC_API_KEY" in body["unblock"]


def test_workspace_header_sent_when_set(client, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-usr-TESTKEY")
    monkeypatch.setenv("ANTHROPIC_WORKSPACE_ID", "wrkspc_TEST")
    seen = {}

    def fake_post(payload):
        seen.update(payload)
        hdrs = bv3._headers()
        assert hdrs["anthropic-workspace-id"] == "wrkspc_TEST"
        assert hdrs["x-api-key"] == "sk-ant-usr-TESTKEY"
        assert hdrs["anthropic-version"] == bv3.ANTHROPIC_VERSION
        return 200, {"model": payload["model"], "content": [{"type": "text", "text": "ok"}],
                     "stop_reason": "end_turn", "usage": {"input_tokens": 3, "output_tokens": 1}}

    monkeypatch.setattr(bv3, "_post_messages", fake_post)
    r = client.post("/api/a11oy/v3/brain/chat", json={"messages": [{"role": "user", "content": "hi"}]})
    assert r.status_code == 200
    assert r.json()["content"] == "ok"
    assert r.json()["model"] == bv3.DEFAULT_MODEL


def test_workspace_missing_degrades_with_exact_unblock(client, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-usr-TESTKEY")
    monkeypatch.delenv("ANTHROPIC_WORKSPACE_ID", raising=False)

    def fake_post(payload):
        return 400, {"error": {"type": "invalid_request_error",
                                "message": "This API key is not scoped to a workspace, so this request must include the anthropic-workspace-id header"}}

    monkeypatch.setattr(bv3, "_post_messages", fake_post)
    r = client.post("/api/a11oy/v3/brain/chat", json={"messages": [{"role": "user", "content": "hi"}]})
    assert r.status_code == 503
    assert "ANTHROPIC_WORKSPACE_ID" in r.json()["unblock"]


def test_ladder_falls_on_model_not_found_only(client, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-TESTKEY")
    calls = []

    def fake_post(payload):
        calls.append(payload["model"])
        if len(calls) == 1:
            return 404, {"error": {"message": "model not found"}}
        return 200, {"model": payload["model"], "content": [{"type": "text", "text": "fallback"}],
                     "usage": {"input_tokens": 1, "output_tokens": 1}}

    monkeypatch.setattr(bv3, "_post_messages", fake_post)
    r = client.post("/api/a11oy/v3/brain/chat", json={"messages": [{"role": "user", "content": "hi"}]})
    assert r.status_code == 200
    assert calls[0] == bv3.BRAIN_V3_MODELS[0]
    assert calls[1] == bv3.BRAIN_V3_MODELS[1]


def test_auth_error_fails_closed_no_ladder(client, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-TESTKEY")
    calls = []

    def fake_post(payload):
        calls.append(payload["model"])
        return 401, {"error": {"message": "invalid x-api-key"}}

    monkeypatch.setattr(bv3, "_post_messages", fake_post)
    r = client.post("/api/a11oy/v3/brain/chat", json={"messages": [{"role": "user", "content": "hi"}]})
    assert r.status_code == 503
    assert len(calls) == 1  # NO ladder walk on auth errors


def test_models_usage_and_converse_shape(client, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-TESTKEY")
    m = client.get("/api/a11oy/v3/brain/models")
    assert m.status_code == 200
    assert m.json()["default_model"] == bv3.DEFAULT_MODEL
    u = client.get("/api/a11oy/v3/brain/usage")
    assert u.status_code == 200
    assert "totals" in u.json()
    c = client.post("/api/a11oy/v3/brain/converse", json={})
    assert c.status_code == 400
