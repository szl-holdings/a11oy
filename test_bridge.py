# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · Doctrine v11 LOCKED 749/14/163.
# Author: Yachay <yachay@szlholdings.dev>
# Co-Authored-By: Perplexity Computer Agent
"""pytest suite for the Cross-Harness Receipt Bridge (Hermes + OpenClaw)."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import szl_bridge as bridge
import szl_bridge_schemas as schemas


@pytest.fixture(scope="module")
def client() -> TestClient:
    app = FastAPI()
    bridge.register(app)
    return TestClient(app)


def test_hermes_chatml_round_trips():
    """1. A Hermes ChatML transcript parses back to its system/user/assistant
    turns, the <think> block, and the <tool_call> JSON — losslessly."""
    cm = bridge.build_chatml(
        system="You are a schema-strict tool agent.",
        user="Search the web for Andean textiles.",
        think="The user wants a web search; the search tool fits.",
        tool_call={"name": "search", "arguments": {"q": "Andean textiles"}},
    )
    parsed = bridge.parse_chatml(cm)
    assert [t["role"] for t in parsed["turns"]] == ["system", "user", "assistant"]
    assert parsed["think_blocks"] == ["The user wants a web search; the search tool fits."]
    assert parsed["tool_calls"] == [{"name": "search", "arguments": {"q": "Andean textiles"}}]
    assert parsed["parse_errors"] == []


def test_schema_mismatch_fails_closed(client: TestClient):
    """2. A tool call that violates the registered schema fails-CLOSED (HTTP 422)
    and mints a kind:"schema_mismatch" receipt that is publicly retrievable."""
    # additionalProperties:false violation
    r = client.post("/api/a11oy/v4/bridge/hermes",
                    json={"name": "search", "arguments": {"q": "x", "bogus": 1}})
    assert r.status_code == 422
    body = r.json()
    assert body["schema_mismatch"] is True
    assert body["receipt_id"].startswith("or-")

    # the schema_mismatch receipt is public and records decision=deny / fail-closed
    rec = client.get(f"/api/a11oy/v4/bridge/receipt/{body['receipt_id']}")
    assert rec.status_code == 200
    payload = rec.json()["receipt"]["envelope"]["payload"]
    assert payload["kind"] == "schema_mismatch"
    assert payload["decision"] == "deny"
    assert payload["fail_mode"] == "fail-closed"

    # unknown tool name also fails-closed
    r2 = client.post("/api/a11oy/v4/bridge/hermes",
                     json={"name": "frobnicate", "arguments": {}})
    assert r2.status_code == 422
    assert r2.json()["schema_mismatch"] is True


def test_deliberation_signed_separately_from_action(client: TestClient):
    """3. When a <think> block is present, TWO distinct receipts are minted:
    a kind:"deliberation" (hash(prompt)+reasoning, no raw user data) and a
    kind:"action" — with different receipt ids, both retrievable."""
    r = client.post("/api/a11oy/v4/bridge/hermes", json={
        "name": "fetch",
        "arguments": {"url": "https://example.com"},
        "think": "I should fetch the page the user named.",
        "user_prompt": "Please read https://example.com for me.",
    })
    assert r.status_code == 200
    body = r.json()
    action_id = body["receipt_id"]
    delib_id = body["deliberation_receipt_id"]
    assert action_id != delib_id

    delib = client.get(f"/api/a11oy/v4/bridge/receipt/{delib_id}").json()["receipt"]
    dpayload = delib["envelope"]["payload"]
    assert dpayload["kind"] == "deliberation"
    # deliberation carries ONLY hash(user_prompt) + reasoning — never the raw prompt
    assert "user_prompt_sha256" in dpayload
    assert dpayload["reasoning_text"] == "I should fetch the page the user named."
    assert "Please read https://example.com" not in str(dpayload)

    action = client.get(f"/api/a11oy/v4/bridge/receipt/{action_id}").json()["receipt"]
    apayload = action["envelope"]["payload"]
    assert apayload["kind"] == "action"
    # the action receipt links back to its deliberation receipt
    assert apayload["deliberation_receipt_id"] == delib_id


def test_bridge_endpoint_produces_valid_public_receipt_url(client: TestClient):
    """4. The bridge endpoints (hermes + openclaw) return a valid, public,
    DSSE-shaped receipt URL with the canonical response shape, and GET /bridge
    serves the landing page."""
    for harness, payload in (
        ("hermes", {"name": "search", "arguments": {"q": "test"}}),
        ("openclaw", {"soul_hash": "abc",
                      "event": {"name": "write_file",
                                "arguments": {"path": "/tmp/x", "content": "hi"}}}),
    ):
        r = client.post(f"/api/a11oy/v4/bridge/{harness}", json=payload)
        assert r.status_code == 200, r.text
        body = r.json()
        # canonical response shape
        for k in ("receipt_id", "signed_url", "doctrine_v", "lutar_anchor", "neuro_citation"):
            assert k in body
        assert body["doctrine_v"] == "11"
        assert body["signed_url"].endswith(f"/bridge/receipt/{body['receipt_id']}")
        assert "szlholdings-a11oy.hf.space" in body["signed_url"]
        # the receipt is publicly retrievable with no auth header
        rec = client.get(f"/api/a11oy/v4/bridge/receipt/{body['receipt_id']}")
        assert rec.status_code == 200
        assert rec.json()["public"] is True

    # landing page
    page = client.get("/bridge")
    assert page.status_code == 200
    assert "We sign the truth" in page.text
    assert "bridge/hermes" in page.text and "bridge/openclaw" in page.text


def test_schema_registry_has_six_tools():
    """Bonus: the registry exposes >=6 JSON Schema 2020-12 tools, all with
    additionalProperties:false."""
    tools = schemas.registered_tools()
    assert set(["search", "fetch", "write_file", "exec", "sign_receipt", "predict"]).issubset(tools)
    assert len(tools) >= 6
    for name in tools:
        s = schemas.get_schema(name)
        assert s["$schema"] == schemas.JSON_SCHEMA_DIALECT
        assert s["additionalProperties"] is False


def test_doctrine_v11_locked_unchanged():
    """The bridge carries Doctrine v11 LOCKED 749/14/163 verbatim and never mutates it."""
    assert bridge.DOCTRINE_V == "11"
    assert bridge.DOCTRINE_LOCKED == "749/14/163"
    assert "749/14/163" in bridge.LUTAR_ANCHOR
