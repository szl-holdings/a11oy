#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Advertised MCP requests match the handlers. Payment headers are not receipts."""

from pathlib import Path

from starlette.applications import Starlette
from starlette.testclient import TestClient

import szl_agentic_loop as loop

ROOT = Path(__file__).resolve().parents[1]
_DOCS = (
    ROOT / "docs/developers/MCP_INTEGRATION.md",
    ROOT / "docs/developers/API_REFERENCE.md",
    ROOT / "docs/developers/EXAMPLES/mcp_claude_config.json",
)


def test_advertised_mcp_contract_matches_the_handler():
    text = "\n".join(path.read_text(encoding="utf-8") for path in _DOCS)
    assert '{"tool":' not in text
    assert "HTTP 405" not in text
    assert "HTML landing page" not in text
    assert '"name":"lambda_score"' in text or "`name` and `arguments`" in text
    assert "operator" in text.lower()


def _signer(payload):
    return {"signed": True, "payloadType": "application/vnd.szl.receipt+json",
            "payload": "synthetic-payload", "honesty": "fixture signer, not a payment settlement",
            "signatures": [{"keyid": "fixture", "sig": "MOCKED-SIGNATURE-BYTES"}]}


def _client():
    app = Starlette()
    loop.register(app, "a11oy", _signer, signer_label="fixture signer")
    return TestClient(app)


_SPOOF = {"payment-signature": "not-a-real-signature", "x-payment-verified": "true"}


def test_policy_check_is_anonymous_and_mints_no_receipt():
    response = _client().post("/mcp/", headers=_SPOOF, json={
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": "policy_check", "arguments": {
            "severity": "low", "confidence": 0.9, "reversible": True}}})
    assert response.status_code == 200
    body = response.json()["result"]["structuredContent"]
    assert body["allow"] is True
    assert "receipt" not in body and "signature" not in body
    assert "payment-response" not in {name.lower() for name in response.headers}


def test_payment_header_does_not_authorize_sign_receipt():
    response = _client().post("/mcp/", headers=_SPOOF, json={
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": "sign_receipt", "arguments": {"payload": {"x": 1}}}})
    assert response.status_code == 401
    assert "BLOCKED" in response.json()["error"]["message"]


def test_agent_run_receipt_is_not_a_payment_settlement():
    response = _client().post("/api/a11oy/v1/agent/run", headers=_SPOOF, json={
        "action": "summarize a public report", "severity": "low",
        "confidence": 0.9, "reversible": True})
    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == "ALLOW"
    receipt = body["signed_receipt"]
    assert receipt["honesty"] == "fixture signer, not a payment settlement"
    assert "payment" not in receipt
    assert "payment-response" not in {name.lower() for name in response.headers}


def test_anonymous_rest_mcp_call_is_refused_by_the_app_gate(monkeypatch):
    """The bare Starlette app above does not install the operator middleware."""
    import serve

    calls = {"body": 0}
    real = serve._safe_json_body

    async def counted(request):
        calls["body"] += 1
        return await real(request)

    monkeypatch.setattr(serve, "_safe_json_body", counted)
    with TestClient(serve.app) as client:
        response = client.post("/api/a11oy/v1/mcp/call", json={
            "name": "lambda_score", "arguments": {"axes": ["consistency"]}})
    body = response.json()
    assert response.status_code == 401
    assert body["status"] == "BLOCKED"
    assert "signature" not in body
    assert calls["body"] == 0
