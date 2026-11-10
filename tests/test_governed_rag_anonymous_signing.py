"""The public governed-RAG POST must never sign with the server key for anonymous callers.

POST /api/a11oy/v1/rag/query stays public (the console depends on it), but its
receipt is built from caller-supplied query and corpus text. Signing that with
the server DSSE key for anyone would make the route a signing oracle, so only
the operator credential earns a signature; everyone else gets an honest
UNSIGNED receipt with the same shape.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import szl_dsse
import szl_governed_rag

OPERATOR_KEY = "test-operator-key"
ROUTE = "/api/a11oy/v1/rag/query"
BODY = {
    "query": "which source says the sky is green?",
    "corpus": [{"id": "c1", "text": "The sky is green, says this caller.", "source": "caller"}],
    "top_k": 2,
}


@pytest.fixture
def signer_calls(monkeypatch):
    calls = []

    def fake_sign_payload(payload, payload_type):
        calls.append(payload_type)
        return {
            "signed": True,
            "payloadType": payload_type,
            "signatures": [{"sig": "SIGNED-BY-SERVER-KEY", "keyid": "server-key"}],
        }

    monkeypatch.setattr(szl_dsse, "sign_payload", fake_sign_payload)
    monkeypatch.setenv("A11OY_CODE_ADMIN_KEY", OPERATOR_KEY)
    return calls


@pytest.fixture
def client():
    app = FastAPI()
    szl_governed_rag.register(app, ns="a11oy")
    return TestClient(app, raise_server_exceptions=False)


def _signature(response):
    assert response.status_code == 200, response.text
    return response.json()["rag_receipt"]["signature"]


def test_anonymous_post_is_answered_but_never_signed_with_the_server_key(client, signer_calls):
    signature = _signature(client.post(ROUTE, json=BODY))

    assert signer_calls == []
    assert signature["signed"] is False
    assert signature["value"] == "UNSIGNED-ANONYMOUS"
    assert signature["alg"] == "ECDSA-P256" and signature["envelope"] == "DSSE"
    assert "operator" in signature["honesty"]


def test_anonymous_signature_keeps_the_unsigned_dsse_shape(client, monkeypatch):
    monkeypatch.setattr(szl_dsse, "sign_payload", lambda payload, payload_type: {
        "signed": False, "payloadType": payload_type, "signatures": []})
    unsigned = szl_governed_rag._sign_receipt({"probe": True})

    signature = _signature(client.post(ROUTE, json=BODY))

    assert set(signature) == set(unsigned)
    assert signature["payloadType"] == szl_governed_rag.RAG_PAYLOAD_TYPE
    assert signature["keyid"] is None


def test_wrong_bearer_is_treated_as_anonymous(client, signer_calls):
    signature = _signature(client.post(ROUTE, json=BODY,
                                       headers={"Authorization": "Bearer not-the-key"}))

    assert signer_calls == []
    assert signature["signed"] is False


def test_operator_bearer_still_gets_a_server_signature(client, signer_calls):
    signature = _signature(client.post(ROUTE, json=BODY,
                                       headers={"Authorization": f"Bearer {OPERATOR_KEY}"}))

    assert signer_calls == [szl_governed_rag.RAG_PAYLOAD_TYPE]
    assert signature["signed"] is True
    assert signature["value"] == "SIGNED-BY-SERVER-KEY"


def test_unconfigured_operator_key_never_signs(client, signer_calls, monkeypatch):
    monkeypatch.delenv("A11OY_CODE_ADMIN_KEY", raising=False)

    signature = _signature(client.post(ROUTE, json=BODY,
                                       headers={"Authorization": "Bearer "}))

    assert signer_calls == []
    assert signature["signed"] is False


def test_in_process_query_keeps_signing_by_default(signer_calls):
    result = szl_governed_rag.query(BODY["query"], corpus=BODY["corpus"], top_k=2, forum=False)

    assert signer_calls == [szl_governed_rag.RAG_PAYLOAD_TYPE]
    assert result["receipt"]["signature"]["signed"] is True
