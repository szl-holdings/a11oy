#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""The public Brain GET is a read; only an explicit POST can mint an answer receipt."""
from __future__ import annotations

from fastapi.testclient import TestClient


def _grounded_result() -> dict:
    return {
        "ok": True,
        "i_dont_know": False,
        "chunks": [{
            "corpus": "doctrine", "source": "test:published", "path": "doctrine.md",
            "repo": "a11oy", "sha256": "a" * 64, "lambda": 0.7,
            "text": "Evidence from a published generation.",
            "evidence": {"citation": "test:published/doctrine.md"},
        }],
        "grounded_count": 1, "recall_count": 1, "lambda_floor": 0.3,
        "dense_used": False, "evidence_set_sha256": "b" * 64,
    }


def test_rag_get_never_builds_loads_or_mints_and_post_mints_once(monkeypatch):
    import serve
    import szl_operator_auth

    calls: list[tuple[object, object]] = []
    receipts: list[tuple[str, dict]] = []
    monkeypatch.setattr(serve._rag_engine, "status", lambda: {"built": True})

    def query(_q, **kwargs):
        calls.append((kwargs.get("emit_receipt"), kwargs.get("load_embedder")))
        return _grounded_result()

    def emit(kind, body):
        receipts.append((kind, body))
        return {"hash": "c" * 64, "signed": False, "dsse": {"signed": False}}

    monkeypatch.setattr(serve._rag_engine, "query", query)
    monkeypatch.setattr(serve, "_rag_emit_receipt", emit)
    monkeypatch.setenv(szl_operator_auth.OPERATOR_KEY_ENV, "estate-rag-test-operator")
    client = TestClient(serve.app, raise_server_exceptions=False)

    read = client.get("/api/a11oy/v1/rag/query", params={"q": "published evidence"})
    assert read.status_code == 200
    assert read.json()["receipt_state"] == "NOT_MINTED_ON_READ"
    assert read.json()["receipt_hash"] is None
    assert calls == [(None, False)]
    assert receipts == []

    status = client.get("/api/a11oy/v1/rag/status")
    assert status.status_code == 200
    assert status.json()["query_endpoint"] == "/api/a11oy/v1/rag/query"
    assert status.json()["query_method"] == "GET"
    assert status.json()["receipt_endpoint"] == "/api/a11oy/v1/rag/estate/query"
    assert receipts == []

    anonymous = client.post("/api/a11oy/v1/rag/estate/query",
                            json={"q": "published evidence"})
    assert anonymous.status_code == 401
    assert receipts == []

    write = client.post("/api/a11oy/v1/rag/estate/query",
                        headers={"Authorization": "Bearer estate-rag-test-operator"},
                        json={"q": "published evidence"})
    assert write.status_code == 200, write.text
    assert write.json()["receipt_state"] == "UNSIGNED"
    assert write.json()["receipt_hash"] == "c" * 64
    assert calls == [(None, False), (None, True)]
    assert len(receipts) == 1
    assert receipts[0][0] == "org_rag.answer"
    assert receipts[0][1]["evidence_set_sha256"] == "b" * 64


def test_estate_query_bounds_reject_oversized_work_before_query(monkeypatch):
    import serve
    import szl_operator_auth

    monkeypatch.setenv(szl_operator_auth.OPERATOR_KEY_ENV, "estate-rag-test-operator")
    monkeypatch.setattr(serve._rag_engine, "query", lambda *_a, **_k: (
        (_ for _ in ()).throw(AssertionError("unbounded query ran"))))
    client = TestClient(serve.app, raise_server_exceptions=False)
    assert client.get("/api/a11oy/v1/rag/query", params={"q": "x", "k": 999}).status_code == 422
    assert client.get("/api/a11oy/v1/rag/query", params={"q": "x" * 1025}).status_code == 422
    headers = {"Authorization": "Bearer estate-rag-test-operator"}
    assert client.post("/api/a11oy/v1/rag/estate/query", headers=headers,
                       json={"q": "x", "k": 999}).status_code == 400
    assert client.post("/api/a11oy/v1/rag/estate/query", headers=headers,
                       json={"q": "x" * 1025}).status_code == 400


def test_legacy_governed_post_keeps_its_own_contract(monkeypatch):
    import serve
    import szl_governed_rag

    def legacy_query(**kwargs):
        assert kwargs["query_text"] == "existing console question"
        return {"ok": True, "grounded_answer": "legacy grounded answer",
                "claims": [{"text": "legacy claim"}], "ragas": {"faithfulness": 0.8},
                "receipt": {"signed": False, "hash": "d" * 64}}

    monkeypatch.setattr(szl_governed_rag, "query", legacy_query)
    monkeypatch.setattr(serve, "_rag_emit_receipt", lambda *_a, **_k: (
        (_ for _ in ()).throw(AssertionError("estate receipt hook ran"))))
    client = TestClient(serve.app, raise_server_exceptions=False)
    response = client.post("/api/a11oy/v1/rag/query",
                           json={"query": "existing console question", "top_k": 4})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["grounded_answer"] == "legacy grounded answer"
    assert body["claims"] == [{"text": "legacy claim"}]
    assert body["ragas"] == {"faithfulness": 0.8}
    assert body["rag_receipt"]["hash"] == "d" * 64
    assert "answer" not in body


def test_rag_missing_index_returns_503_without_a_lazy_write(monkeypatch):
    import serve

    monkeypatch.setattr(serve._rag_engine, "status", lambda: {
        "built": False, "build_state": {"phase": "seeding"},
    })
    monkeypatch.setattr(serve._rag_engine, "query", lambda *_a, **_k: (
        (_ for _ in ()).throw(AssertionError("query ran without index"))))
    monkeypatch.setattr(serve, "_rag_emit_receipt", lambda *_a, **_k: (
        (_ for _ in ()).throw(AssertionError("GET minted a receipt"))))
    client = TestClient(serve.app, raise_server_exceptions=False)

    response = client.get("/api/a11oy/v1/rag/query", params={"q": "unbuilt"})
    assert response.status_code == 503
    assert response.headers["retry-after"] == "5"
    assert response.json()["index"]["built"] is False
    assert response.json()["receipt_state"] == "NOT_MINTED_INDEX_UNAVAILABLE"


def test_rag_legacy_wal_reports_typed_unavailable_without_query_or_receipt(monkeypatch):
    import serve

    monkeypatch.setattr(serve._rag_engine, "status", lambda: {
        "built": False, "storage_state": "LEGACY_WAL_REQUIRES_LIFECYCLE_WRITE",
        "honest_error": "legacy WAL requires an explicit lifecycle/operator write",
    })
    monkeypatch.setattr(serve._rag_engine, "query", lambda *_a, **_k: (
        (_ for _ in ()).throw(AssertionError("legacy index read ran"))))
    monkeypatch.setattr(serve, "_rag_emit_receipt", lambda *_a, **_k: (
        (_ for _ in ()).throw(AssertionError("legacy index read minted receipt"))))
    client = TestClient(serve.app, raise_server_exceptions=False)
    response = client.get("/api/a11oy/v1/rag/query", params={"q": "legacy evidence"})
    assert response.status_code == 503
    assert response.json()["index"]["storage_state"] == "LEGACY_WAL_REQUIRES_LIFECYCLE_WRITE"
    assert response.json()["receipt_state"] == "NOT_MINTED_INDEX_UNAVAILABLE"
