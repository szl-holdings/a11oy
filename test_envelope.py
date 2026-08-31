# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · Doctrine v11 LOCKED 749/14/163.
# Author: Yachay <yachay@szlholdings.dev>
# Co-Authored-By: Perplexity Computer Agent
"""pytest suite for the optional `envelope` param on POST /api/a11oy/v4/agent/ask.

Covers the chatml | openai | anthropic wire formats, the schema-strict
fail-CLOSED path for an invalid ChatML <tool_call>, the unknown-envelope guard,
and the preserved legacy `prompt` path. The deterministic ensemble runs locally
(qwen-local stub) so these tests need no network or model keys.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import szl_bridge as bridge
import a11oy_v4_agent as agent


@pytest.fixture(scope="module")
def client() -> TestClient:
    app = FastAPI()
    agent.register(app)
    return TestClient(app)


def test_chatml_envelope_round_trips(client: TestClient):
    """A Hermes ChatML envelope is accepted and re-emitted as an assistant
    ChatML turn (round-trip through /agent/ask)."""
    cm = bridge.build_chatml(
        "be terse", "What is 2+2?", "Simple arithmetic.",
        {"name": "search", "arguments": {"q": "2+2"}},
    )
    r = client.post("/api/a11oy/v4/agent/ask", json={"envelope": "chatml", "chatml": cm})
    assert r.status_code == 200
    body = r.json()
    assert body["envelope"] == "chatml"
    assert "<|im_start|>assistant" in body["chatml"]


def test_chatml_schema_mismatch_fails_closed(client: TestClient):
    """An invalid inline <tool_call> (additionalProperties) fails-CLOSED 422
    with a schema_mismatch receipt."""
    bad = bridge.build_chatml(
        "", "hi", "t", {"name": "search", "arguments": {"q": "x", "bad": 1}},
    )
    r = client.post("/api/a11oy/v4/agent/ask", json={"envelope": "chatml", "chatml": bad})
    assert r.status_code == 422
    assert r.json()["schema_mismatch"] is True


def test_openai_envelope(client: TestClient):
    r = client.post("/api/a11oy/v4/agent/ask",
                    json={"envelope": "openai", "messages": [{"role": "user", "content": "hello"}]})
    assert r.status_code == 200
    assert r.json()["openai"]["choices"]


def test_anthropic_envelope(client: TestClient):
    r = client.post("/api/a11oy/v4/agent/ask",
                    json={"envelope": "anthropic", "messages": [{"role": "user", "content": "hello"}]})
    assert r.status_code == 200
    assert r.json()["anthropic"]["content"]


def test_unknown_envelope_rejected(client: TestClient):
    r = client.post("/api/a11oy/v4/agent/ask", json={"envelope": "klingon", "prompt": "x"})
    assert r.status_code == 400


def test_legacy_prompt_path_preserved(client: TestClient):
    """No `envelope` -> the original deterministic ensemble path is unchanged."""
    r = client.post("/api/a11oy/v4/agent/ask", json={"prompt": "hello world"})
    assert r.status_code == 200
    assert "winner" in r.json()
