"""Fail-closed signature verification in szl_agentic_loop.

Without a host verifier, a caller-supplied ``signed`` flag must never make a
receipt verified, on the HTTP route or through the MCP tool. With a verifier,
only an explicit ``signature_valid is True`` counts.
"""
from __future__ import annotations

import pytest

pytest.importorskip("starlette")
from starlette.applications import Starlette  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

import szl_agentic_loop as loop  # noqa: E402

NS = "a11oy"
RUN = {"action": "summarize a public report", "severity": "low", "confidence": 0.9,
       "reversible": True}


def _signer(payload):
    return {"signed": True, "payloadType": "application/vnd.szl.receipt+json",
            "payload": "synthetic-payload",
            "signatures": [{"keyid": "fixture", "sig": "MOCKED-SIGNATURE-BYTES"}]}


def _client(verify_fn=None):
    app = Starlette()
    loop.register(app, NS, _signer, verify_fn=verify_fn, signer_label="fixture signer")
    return TestClient(app)


def _run(client):
    response = client.post("/api/%s/v1/agent/run" % NS, json=RUN)
    assert response.status_code == 200
    return response.json()


def _verify(client, run):
    response = client.post("/api/%s/v1/agent/verify-chain" % NS, json=run)
    assert response.status_code == 200
    return response.json()


def _mcp_verify(client, receipt):
    response = client.post("/mcp/", json={
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": "verify_receipt", "arguments": {"receipt": receipt}}})
    assert response.status_code == 200
    return response.json()["result"]["structuredContent"]


def test_forged_signed_flag_without_verifier_is_not_verified():
    client = _client()
    run = _run(client)
    run["signed_receipt"] = {"signed": True}
    result = _verify(client, run)
    assert result["verified"] is False
    assert result["signature_valid"] is None
    assert result["signature_detail"].startswith("NO_VERIFIER")


def test_signed_envelope_without_verifier_is_reported_not_checked():
    client = _client()
    result = _verify(client, _run(client))
    assert result["chain_intact"] is True
    assert result["signature_valid"] is None
    assert result["verified"] is False


def test_verifier_true_verifies_an_intact_chain():
    client = _client(lambda env: {"signature_valid": True, "detail": "fixture verifier"})
    result = _verify(client, _run(client))
    assert result["chain_intact"] is True
    assert result["verified"] is True


@pytest.mark.parametrize("value", [False, None, "yes", 1])
def test_only_an_explicit_true_counts(value):
    client = _client(lambda env: {"signature_valid": value, "detail": "fixture verifier"})
    assert _verify(client, _run(client))["verified"] is False


def test_mcp_verify_receipt_without_verifier_is_not_valid():
    client = _client()
    result = _mcp_verify(client, {"signed": True,
                                  "signatures": [{"sig": "MOCKED-SIGNATURE-BYTES"}]})
    assert result.get("signature_valid") is None
    assert result.get("detail", "").startswith("NO_VERIFIER")


def test_mcp_verify_receipt_delegates_to_the_verifier():
    client = _client(lambda env: {"signature_valid": True, "detail": "fixture verifier"})
    assert _mcp_verify(client, {"signed": True})["signature_valid"] is True
