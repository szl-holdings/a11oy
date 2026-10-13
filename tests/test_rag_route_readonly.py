#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""The public Brain GET is a read; only an explicit POST can mint an answer receipt."""
from __future__ import annotations

import ast
from copy import deepcopy
import functools
import hashlib
import json
from pathlib import Path
import secrets
import sqlite3
import sys
from types import ModuleType, SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient


def _readiness_status_labels() -> set[str]:
    matrix = json.loads((Path(__file__).resolve().parents[1] /
                         "tools/readiness-harness/tabs.json").read_text(encoding="utf-8"))
    return {label.lower() for label in matrix["endpoints"]
            ["/api/a11oy/v1/rag/status"]["degradedRules"]["allowLabels"]}


@pytest.mark.parametrize("index_state", ["built", "absent", "failed"])
def test_rag_status_scopes_persisted_metadata_without_refresh_or_receipt(index_state):
    # Exercise the actual handler without booting the whole application or its
    # background workers. The existing full-app cases below cover registration.
    source = (Path(__file__).resolve().parents[1] / "serve.py").read_text(encoding="utf-8")
    handlers = [node for node in ast.walk(ast.parse(source))
                if isinstance(node, ast.AsyncFunctionDef) and node.name == "_rag_status_get"]
    assert len(handlers) == 1
    calls = []
    metadata = {"built": index_state == "built", "mode": "seed",
                "build_state": {"finished": 123.0, "generation_id": "stored-generation"}}
    configured = {"repositories": ["example/configured-only"]}
    original_metadata = deepcopy(metadata)
    original_configured = deepcopy(configured)

    def status():
        calls.append("status")
        if index_state == "failed":
            raise OSError("synthetic unavailable index")
        return metadata

    def manifest():
        calls.append("manifest")
        return configured

    def forbidden(*_args, **_kwargs):
        raise AssertionError("status read attempted work or minted a receipt")

    def envelope(payload, *, status, citations):
        return {**payload, "status": status, "citations": citations}

    identity = {"module": "a11oy_org_rag", "origin": "vendored",
                "file_sha256": "e" * 64, "lexical_reference": "SUPPORTED"}
    auth_state = {"authentication": "UNCONFIGURED", "reason_code": "REFERENCE_SCOPE_UNCONFIGURED"}
    app = FastAPI()
    namespace = {
        "app": app, "_RAGJSON": JSONResponse, "gov_envelope": envelope,
        "_rag_engine_identity": lambda: dict(identity),
        "_rag_reference_auth_state": lambda: dict(auth_state),
        "_rag_emit_receipt": forbidden,
        "_rag_engine": SimpleNamespace(
            status=status, corpus_manifest=manifest, query=forbidden,
            build_index=forbidden, build_seed_index=forbidden,
            build_full_corpus=forbidden, start_background_build=forbidden,
        ),
    }
    exec(compile(ast.Module(body=handlers, type_ignores=[]), "<rag-status-handler>", "exec"), namespace)
    response = TestClient(app).get("/api/a11oy/v1/rag/status")
    assert response.status_code == 200
    body = response.json()
    assert calls == ["status", "manifest"]
    assert body["data_kind"] == ("cached" if index_state == "built" else "unavailable")
    assert body["data_kind"] in _readiness_status_labels()
    assert body["observation_scope"] == "stored_index_metadata_and_configured_corpus"
    assert "does not establish source freshness or complete corpus coverage" in body["honesty"]
    assert body["corpus"] == original_configured
    assert configured == original_configured
    assert metadata == original_metadata
    assert body["index_built"] is (index_state == "built")
    assert body["status"] == ("REAL" if index_state == "built" else "DEGRADED")
    if index_state == "failed":
        assert body["index"] == {"built": False, "honest_error": "status unavailable: OSError"}
    else:
        assert body["index"] == original_metadata
    assert body["receipt_method"] == "POST"
    assert body["receipt_authority"] == "operator"
    assert "receipt" not in body
    assert body["engine"] == identity
    assert body["lexical_reference_query"] == "/api/a11oy/v1/rag/query?mode=lexical"
    assert body["lexical_reference_auth"] == auth_state


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
    lexical_flags: list[object] = []
    receipts: list[tuple[str, dict]] = []
    monkeypatch.setattr(serve._rag_engine, "status", lambda: {"built": True})

    def query(_q, **kwargs):
        calls.append((kwargs.get("emit_receipt"), kwargs.get("load_embedder")))
        lexical_flags.append(kwargs.get("lexical_only", "absent"))
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
    assert status.json()["data_kind"] == "cached"
    assert status.json()["data_kind"] in _readiness_status_labels()
    assert status.json()["status"] == "REAL"
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
    # The default read and the receipted POST keep their behaviour unchanged.
    assert lexical_flags == ["absent", "absent"]
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
    status = client.get("/api/a11oy/v1/rag/status")
    assert status.status_code == 200
    assert status.json()["data_kind"] == "unavailable"
    assert status.json()["data_kind"] in _readiness_status_labels()
    assert status.json()["status"] == "DEGRADED"
    assert status.json()["index_built"] is False


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


# --------------------------------------------------------------------------- #
# Explicit model-free reference mode (GET mode=lexical). Case IDs refer to the
# first A11oy journey contract; these are source-level tests, not that journey.
# --------------------------------------------------------------------------- #
_QUERY = "/api/a11oy/v1/rag/query"
_LEXICAL = {"q": "anchor evidence", "mode": "lexical"}
# 25 ASCII bytes, then 4-byte code points: byte 2048 lands inside one of them.
_UNICODE_BODY = "unicode anchor evidence: " + "\U0001d518" * 600
_MIXED_BODY = "mixed anchor evidence café € 漢字 " * 3
_ASCII_BODY = "plain anchor evidence for the lexical reference"
_CHUNKS = (
    ("docs/unicode.md", "bundled:szl-holdings/szl-papers@0123456789ab:docs/unicode.md",
     _UNICODE_BODY),
    ("docs/mixed.md", "bundled:szl-holdings/lutar-lean@" + "a" * 40 + ":docs/mixed.md",
     _MIXED_BODY),
    ("docs/plain.md", "gh:szl-holdings/a11oy", _ASCII_BODY),
)

# mode=lexical requires a gdw_auth bearer with the reference read scope. Tokens
# are generated per test; the registry stores only their SHA-256 digests.
_READ_SCOPE = "rag-reference:read"
_REFERENCE_ENV = ("A11OY_RAG_REFERENCE_CREDENTIALS_JSON", "A11OY_RAG_REFERENCE_PRINCIPALS_JSON",
                  "A11OY_RAG_REFERENCE_SCOPE_JSON", "GDW_CREDENTIALS_JSON", "GDW_PRINCIPALS_JSON")
_FIXTURE_NAMESPACE = "reference-fixture"
_FIXTURE_SOURCES = tuple(source for _path, source, _body in _CHUNKS)


def _scope_json(namespace: str, repo: str, sources) -> str:
    return json.dumps({"version": 1, "tenants": {namespace: {"repo": repo,
                                                             "sources": list(sources)}}})


def _credential(namespace: str, *, owner: str, key: str, scopes=(_READ_SCOPE,),
                revoked: bool = False) -> tuple[str, dict]:
    token = secrets.token_urlsafe(32)
    entry = {"owner_id": owner, "namespace": namespace, "key_id": key,
             "token_sha256": hashlib.sha256(token.encode("utf-8")).hexdigest(),
             "scopes": list(scopes)}
    if revoked:
        entry["revoked"] = True
    return token, entry


def _registry_json(entries) -> str:
    return json.dumps({"version": 1, "credentials": list(entries)})


def _configure_reference(monkeypatch, *, scope: str | None, credentials=None) -> None:
    for name in _REFERENCE_ENV:
        monkeypatch.delenv(name, raising=False)
    if scope is not None:
        monkeypatch.setenv("A11OY_RAG_REFERENCE_SCOPE_JSON", scope)
    if credentials is not None:
        monkeypatch.setenv("A11OY_RAG_REFERENCE_CREDENTIALS_JSON", _registry_json(credentials))


def _bearer(token: str) -> dict:
    return {"Authorization": "Bearer " + token}


def _reference_auth(monkeypatch) -> dict:
    """Admit the three-chunk fixture corpus for one reader; return its header."""
    token, entry = _credential(_FIXTURE_NAMESPACE, owner="fixture-reviewer", key="reader-1")
    _configure_reference(monkeypatch, credentials=[entry], scope=_scope_json(
        _FIXTURE_NAMESPACE, "a11oy", _FIXTURE_SOURCES))
    return _bearer(token)


def _isolated_client(serve) -> TestClient:
    """A separate client address keeps these many reads out of the per-IP
    sliding-window budget that later files in the same CI job share."""
    return TestClient(serve.app, raise_server_exceptions=False,
                      client=("rag-reference-auth", 50000))


def _reset_engine(monkeypatch, rag, db_path: Path) -> None:
    monkeypatch.setattr(rag, "RAG_DB_PATH", str(db_path))
    monkeypatch.setattr(rag, "_GRAPH", rag.OrgGraph())
    monkeypatch.setattr(rag, "_BUILD_META", {"built": False})
    monkeypatch.setattr(rag, "_REHYDRATE_ATTEMPTED", False)


def _publish(rag, chunks=_CHUNKS, mode: str = "lexical-test") -> str:
    conn = rag._db()
    try:
        rag._init_schema(conn)
        generation_id = rag._begin_generation(conn, mode)
        graph = rag.OrgGraph()
        for path, source, body in chunks:
            rag._ingest_text(graph, conn, repo="a11oy", path=path, raw=body, source=source,
                             category="doctrine", embed_fn=None, generation_id=generation_id)
        rag._persist_runtime_state(
            conn, graph, {"built": True, "mode": mode, "ts": 1.0, "repos": 1,
                          "chunks": len(chunks)}, generation_id)
    finally:
        conn.close()
    return generation_id


def _published_engine(monkeypatch, tmp_path, rag=None):
    """Publish one generation, then forget it so the read rehydrates from disk."""
    if rag is None:
        import a11oy_org_rag as rag
    db_path = tmp_path / "lexical.sqlite3"
    _reset_engine(monkeypatch, rag, db_path)
    generation_id = _publish(rag)
    _reset_engine(monkeypatch, rag, db_path)
    return rag, db_path, generation_id


def _storage_fingerprint(directory: Path) -> dict:
    return {path.name: (hashlib.sha256(path.read_bytes()).hexdigest(), path.stat().st_mtime_ns)
            for path in directory.iterdir() if path.is_file()}


def _forbid(label):
    def forbidden(*_args, **_kwargs):
        raise AssertionError(label)
    return forbidden


def _forbid_engine_work(monkeypatch, rag, *, embedder: bool = True) -> None:
    for name in ("_db", "_init_schema", "_begin_generation", "_persist_runtime_state",
                 "build_index", "build_seed_index", "build_full_corpus",
                 "start_background_build", "start_seed_bootstrap", "refresh_tick",
                 "embed_and_store_chunk", "_gh_get", "_gh_raw", "_hf_raw",
                 "_hf_space_files"):
        monkeypatch.setattr(rag, name, _forbid(f"lexical read reached {name}"))
    if embedder:
        monkeypatch.setattr(rag, "_maybe_embedder", _forbid("lexical read looked up an embedder"))


def _canonical_sha256(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode("utf-8")).hexdigest()


def _active_generation_row(db_path: Path) -> tuple[str, str]:
    conn = sqlite3.connect(db_path.as_uri() + "?mode=ro", uri=True)
    try:
        return conn.execute(
            "SELECT g.generation_id, g.digest_sha256 FROM org_active_generation a "
            "JOIN org_generations g ON g.generation_id=a.generation_id").fetchone()
    finally:
        conn.close()


def _stored_bodies(db_path: Path, generation_id: str) -> dict[str, str]:
    conn = sqlite3.connect(db_path.as_uri() + "?mode=ro", uri=True)
    try:
        return dict(conn.execute(
            "SELECT chunk_id, body FROM org_chunks_gen WHERE generation_id=?",
            (generation_id,)).fetchall())
    finally:
        conn.close()


def test_utf8_prefix_end_never_splits_a_code_point():
    import a11oy_org_rag as rag

    for text in ("abc", "é" * 9, "€" * 9, "\U0001d518" * 9, "a€\U0001d518é" * 5):
        raw = text.encode("utf-8")
        for limit in range(len(raw) + 2):
            end = rag._utf8_prefix_end(raw, limit)
            assert end <= min(limit, len(raw))
            raw[:end].decode("utf-8")
            assert end == len(raw) or (raw[end] & 0xC0) != 0x80
            assert min(limit, len(raw)) - end < 4


def test_engine_lexical_switch_refuses_hyde_receipts_and_model_load_before_reading(monkeypatch):
    import a11oy_org_rag as rag

    monkeypatch.setattr(rag, "_rehydrate_runtime_state", _forbid("refused call read state"))
    monkeypatch.setattr(rag, "_maybe_embedder", _forbid("refused call looked up an embedder"))
    receipts = []
    for kwargs in ({"hyde_text": "hypothetical"},
                   {"emit_receipt": lambda *a: receipts.append(a) or {}},
                   {"load_embedder": True}):
        refused = rag.query("anchor", lexical_only=True, **kwargs)
        assert refused["ok"] is False
        assert refused["reason_code"] == "LEXICAL_ONLY_ARGUMENT_CONFLICT"
        assert refused["inference"] == "NOT_INVOKED"
        assert refused["router_dispatch_count"] == 0
    assert rag.query("anchor", lexical_only="yes")["reason_code"] == "LEXICAL_ONLY_FLAG_INVALID"
    assert receipts == []


def test_a05_a07_a08_lexical_reference_binds_generation_chunk_and_excerpt(monkeypatch, tmp_path):
    import serve

    rag, db_path, generation_id = _published_engine(monkeypatch, tmp_path, serve._rag_engine)
    # A part-built successor must stay invisible (A05).
    writer = sqlite3.connect(db_path)
    writer.row_factory = sqlite3.Row
    staging = rag._begin_generation(writer, "interrupted")
    rag._ingest_text(rag.OrgGraph(), writer, repo="a11oy", path="docs/partial.md",
                     raw="partial staging evidence", source="test:partial",
                     category="doctrine", embed_fn=None, generation_id=staging)
    writer.commit()
    writer.close()
    active_id, active_digest = _active_generation_row(db_path)
    assert active_id == generation_id
    bodies = _stored_bodies(db_path, generation_id)
    headers = _reference_auth(monkeypatch)
    _forbid_engine_work(monkeypatch, rag)
    monkeypatch.setattr(serve, "_rag_emit_receipt", _forbid("lexical GET minted a receipt"))
    client = TestClient(serve.app, raise_server_exceptions=False)

    response = client.get(_QUERY, params={**_LEXICAL, "k": 6}, headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["mode"] == "lexical"
    assert body["result_state"] == "REFERENCE_RETURNED"
    assert body["retrieval_method"] == "lexical"
    assert body["inference"] == "NOT_INVOKED"
    assert body["router_dispatch_count"] == 0
    assert body["embedder_invoked"] is False
    assert body["receipt_state"] == "NOT_MINTED_ON_READ"
    assert body["receipt_hash"] is None
    assert body["answer"] is None
    assert "confidence" not in body
    assert body["confidence_state"] == "NOT_REPORTED_UNCALIBRATED"
    assert "not verified factual support" in body["support_statement"]
    assert body["retrieval"]["dense_used"] is False
    assert body["retrieval"]["hyde_used"] is False
    assert body["retrieval"]["retrieval_planes"] == ["corpus"]
    assert body["generation"] == {"generation_id": active_id,
                                  "generation_digest_sha256": active_digest,
                                  "status": "ACTIVE"}

    engine_file = Path(rag.__file__).read_bytes()
    assert body["engine"]["module"] == rag.__name__
    assert body["engine"]["file_sha256"] == hashlib.sha256(engine_file).hexdigest()
    assert body["engine"]["lexical_reference"] == "SUPPORTED"
    assert body["engine"]["origin"] == (
        "vendored" if rag.__name__ == "a11oy_org_rag" else "installed_package")
    assert body["principal"] == {"owner_id": "fixture-reviewer", "key_id": "reader-1",
                                 "namespace": _FIXTURE_NAMESPACE}
    assert body["corpus_scope"]["repo"] == "a11oy"
    assert body["corpus_scope"]["sources"] == sorted(_FIXTURE_SOURCES)
    assert body["corpus_scope"]["request_fields_grant_authority"] is False
    assert body["authentication"]["required_scope"] == _READ_SCOPE
    assert body["authentication"]["session_expiry"] == "NOT_IMPLEMENTED"
    assert body["limitations"]["session_expiry"] == "NOT_IMPLEMENTED"
    assert body["limitations"]["tenant_storage_isolation"] == "NOT_ESTABLISHED"
    assert "credential expiry or session lifecycle" in body["not_claimed"]
    assert headers["Authorization"].split(" ", 1)[1] not in response.text

    citations = body["citations"]
    assert {c["path"] for c in citations} == {path for path, _s, _b in _CHUNKS}
    assert "docs/partial.md" not in {c["path"] for c in citations}
    assert [c["rank"] for c in citations] == list(range(1, len(citations) + 1))
    for citation in citations:
        raw = bodies[citation["chunk_id"]].encode("utf-8")
        start, end = citation["excerpt_utf8_span"]
        assert citation["chunk_sha256"] == hashlib.sha256(raw).hexdigest()
        assert citation["chunk_utf8_bytes"] == len(raw)
        assert start == 0 and end <= 2048
        assert citation["excerpt"].encode("utf-8") == raw[start:end]
        assert citation["excerpt_sha256"] == hashlib.sha256(raw[start:end]).hexdigest()
        assert citation["excerpt_truncated"] is (end < len(raw))
        assert isinstance(citation["lexical_score"], float)
    by_path = {c["path"]: c for c in citations}
    unicode_cite = by_path["docs/unicode.md"]
    unicode_raw = _UNICODE_BODY.encode("utf-8")
    with pytest.raises(UnicodeDecodeError):
        unicode_raw[:2048].decode("utf-8")
    assert unicode_cite["excerpt_utf8_span"] == [0, 2045]
    assert unicode_cite["excerpt_truncated"] is True
    assert unicode_cite["excerpt_sha256"] != unicode_cite["chunk_sha256"]
    assert (unicode_cite["source_revision"], unicode_cite["source_revision_state"]) == (
        "0123456789ab", "ABBREVIATED_COMMIT")
    assert (by_path["docs/mixed.md"]["source_revision"],
            by_path["docs/mixed.md"]["source_revision_state"]) == ("a" * 40, "FULL_COMMIT")
    assert by_path["docs/mixed.md"]["excerpt_truncated"] is False
    assert (by_path["docs/plain.md"]["source_revision"],
            by_path["docs/plain.md"]["source_revision_state"]) == (
        None, "NOT_RECORDED_IN_GENERATION")

    evidence = body["evidence_set"]
    assert body["evidence_set_sha256"] == _canonical_sha256(evidence)
    assert [e["chunk_id"] for e in evidence] == [c["chunk_id"] for c in citations]
    for entry, citation in zip(evidence, citations):
        assert entry["generation_id"] == active_id
        assert entry["generation_digest_sha256"] == active_digest
        assert entry["sha256"] == citation["chunk_sha256"]
        assert entry["excerpt_sha256"] == citation["excerpt_sha256"]
        assert entry["excerpt_utf8_span"] == citation["excerpt_utf8_span"]

    alias = client.get("/org/rag", params=_LEXICAL, headers=headers)
    assert alias.status_code == 200
    assert alias.json()["evidence_set_sha256"] == body["evidence_set_sha256"]
    partial = client.get(_QUERY, params={"q": "partial staging", "mode": "lexical"},
                         headers=headers)
    assert partial.status_code == 200
    assert partial.json()["result_state"] == "ABSTAINED"
    assert partial.json()["generation"]["generation_id"] == active_id


def test_a07_lexical_citation_identity_hydrates_the_exact_chunk(monkeypatch, tmp_path):
    import serve
    from a11oy_agent_loop import SynthesisHandle, SynthesisSubject

    rag, _db_path, _generation_id = _published_engine(monkeypatch, tmp_path, serve._rag_engine)
    body = TestClient(serve.app, raise_server_exceptions=False).get(
        _QUERY, params=_LEXICAL, headers=_reference_auth(monkeypatch)).json()
    generation = body["generation"]
    handles = tuple(SynthesisHandle(
        generation_id=generation["generation_id"],
        generation_digest_sha256=generation["generation_digest_sha256"],
        chunk_id=c["chunk_id"], node_id=c["node_id"], repo=c["repo"], path=c["path"],
        source=c["source"], sha256=c["chunk_sha256"]) for c in body["citations"])
    # Synthetic controller identity for this fixture only; it grants nothing.
    subject = SynthesisSubject(principal_id="fixture-reviewer", tenant_id="fixture-tenant",
                               policy_revision="0" * 40, authenticated=True)
    hydrated = rag.hydrate_answer_evidence(subject, handles, authorizer=lambda *_a: True)
    assert len(hydrated) == len(body["citations"]) == 3
    for item, citation in zip(hydrated, body["citations"]):
        raw = item["content"].encode("utf-8")
        start, end = citation["excerpt_utf8_span"]
        assert hashlib.sha256(raw).hexdigest() == citation["chunk_sha256"]
        assert raw[start:end] == citation["excerpt"].encode("utf-8")


def test_a06_lexical_mode_never_executes_an_already_loaded_embedder(monkeypatch, tmp_path):
    import serve

    rag, _db_path, _generation_id = _published_engine(monkeypatch, tmp_path, serve._rag_engine)

    class _Vector(list):
        def astype(self, _dtype):
            return self

        def tolist(self):
            return list(self)

    class _LoadedModel:
        def __init__(self):
            self.calls = []

        def encode(self, texts, **_kwargs):
            self.calls.append(list(texts))
            return [_Vector([1.0, 0.0])]

    model = _LoadedModel()
    monkeypatch.setitem(sys.modules, "szl_rag", SimpleNamespace(
        _state={"ready": True, "model": model},
        _ensure_loaded=_forbid("read attempted a model load")))
    lookups = []
    original = rag._maybe_embedder
    monkeypatch.setattr(rag, "_maybe_embedder",
                        lambda load=True: lookups.append(load) or original(load=load))
    headers = _reference_auth(monkeypatch)
    client = TestClient(serve.app, raise_server_exceptions=False)

    # Positive control: the unchanged default read reuses the loaded embedder.
    default = client.get(_QUERY, params={"q": "anchor evidence"})
    assert default.status_code == 200, default.text
    assert default.json()["retrieval"]["dense_used"] is True
    assert lookups == [False]
    assert model.calls == [["anchor evidence"]]

    for route in (_QUERY, "/org/rag"):
        lexical = client.get(route, params=_LEXICAL, headers=headers)
        assert lexical.status_code == 200, lexical.text
        assert lexical.json()["embedder_invoked"] is False
        assert lexical.json()["retrieval"]["dense_used"] is False
    assert lookups == [False]
    assert model.calls == [["anchor evidence"]]


@pytest.mark.parametrize("state", ["missing", "legacy_wal", "unversioned"])
def test_a05_unavailable_index_fails_honestly_without_write_or_fallback(
    monkeypatch, tmp_path, state,
):
    import serve

    rag = serve._rag_engine
    db_path = tmp_path / "lexical.sqlite3"
    _reset_engine(monkeypatch, rag, db_path)
    if state == "legacy_wal":
        _publish(rag)
        legacy = sqlite3.connect(db_path)
        assert legacy.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
        legacy.close()
    elif state == "unversioned":
        legacy = sqlite3.connect(db_path)
        legacy.execute("CREATE TABLE org_chunks(chunk_id TEXT, body TEXT)")
        legacy.execute("CREATE TABLE org_active_generation(singleton INTEGER, generation_id TEXT)")
        legacy.execute("INSERT INTO org_chunks VALUES('c', 'anchor evidence')")
        legacy.commit()
        legacy.close()
    _reset_engine(monkeypatch, rag, db_path)
    before = _storage_fingerprint(tmp_path)
    headers = _reference_auth(monkeypatch)
    _forbid_engine_work(monkeypatch, rag)
    monkeypatch.setattr(serve, "_rag_emit_receipt", _forbid("unavailable read minted a receipt"))
    client = TestClient(serve.app, raise_server_exceptions=False)

    for route in (_QUERY, "/org/rag"):
        response = client.get(route, params=_LEXICAL, headers=headers)
        assert response.status_code == 503, response.text
        body = response.json()
        assert body["result_state"] == "UNAVAILABLE"
        assert body["reason_code"] == "LEXICAL_REFERENCE_INDEX_UNAVAILABLE"
        assert body["retrieval_method"] == "lexical"
        assert body["inference"] == "NOT_INVOKED"
        assert body["router_dispatch_count"] == 0
        assert body["receipt_state"] == "NOT_MINTED_INDEX_UNAVAILABLE"
        assert body["answer"] is None
        assert body["citations"] == []
        if state == "legacy_wal":
            assert body["index"]["storage_state"] == "LEGACY_WAL_REQUIRES_LIFECYCLE_WRITE"
    assert _storage_fingerprint(tmp_path) == before
    assert db_path.exists() is (state != "missing")


@pytest.mark.parametrize("fault", ["chunk_tampered", "generation_digest_changed",
                                   "successor_published", "suppression_unreadable"])
def test_a07_changed_generation_or_tampered_chunk_denies_before_release(
    monkeypatch, tmp_path, fault,
):
    import serve

    rag, db_path, generation_id = _published_engine(monkeypatch, tmp_path, serve._rag_engine)
    assert rag.status()["generation_id"] == generation_id  # verified rehydration
    snapshot = (rag._GRAPH, dict(rag._BUILD_META))
    if fault == "successor_published":
        _publish(rag, chunks=(("docs/next.md", "test:next", "successor anchor evidence"),))
        monkeypatch.setattr(rag, "_GRAPH", snapshot[0])
        monkeypatch.setattr(rag, "_BUILD_META", snapshot[1])
    else:
        writer = sqlite3.connect(db_path)
        if fault == "chunk_tampered":
            writer.execute("UPDATE org_chunks_gen SET body=body || ' tampered' "
                           "WHERE generation_id=? AND path='docs/plain.md'", (generation_id,))
        elif fault == "generation_digest_changed":
            writer.execute("UPDATE org_generations SET digest_sha256=? WHERE generation_id=?",
                           ("f" * 64, generation_id))
        else:
            writer.execute("DROP TABLE org_source_revocations")
        writer.commit()
        writer.close()
    expected = {
        "chunk_tampered": "LEXICAL_REFERENCE_CHUNK_DIGEST_MISMATCH",
        "generation_digest_changed": "LEXICAL_REFERENCE_GENERATION_DIGEST_MISMATCH",
        "successor_published": "LEXICAL_REFERENCE_GENERATION_CHANGED",
        "suppression_unreadable": "LEXICAL_REFERENCE_SUPPRESSION_STATE_UNAVAILABLE",
    }[fault]
    headers = _reference_auth(monkeypatch)
    _forbid_engine_work(monkeypatch, rag)
    response = TestClient(serve.app, raise_server_exceptions=False).get(
        _QUERY, params=_LEXICAL, headers=headers)
    assert response.status_code == 503, response.text
    body = response.json()
    assert body["reason_code"] == expected
    assert body["integrity_state"] == "FAILED_CLOSED"
    assert body["citations"] == []
    assert "anchor evidence for the lexical" not in response.text


def test_lexical_reference_keeps_digest_suppression_without_a_rights_claim(monkeypatch, tmp_path):
    import serve

    rag, db_path, generation_id = _published_engine(monkeypatch, tmp_path, serve._rag_engine)
    plain_sha = hashlib.sha256(_ASCII_BODY.encode("utf-8")).hexdigest()
    writer = sqlite3.connect(db_path)
    writer.execute(
        "INSERT INTO org_source_revocations VALUES(?,?,?,?,?,?,?)",
        ("fixture-revocation", "docs/plain.md", plain_sha, "fixture", "fixture", 1.0, "fixture"))
    writer.commit()
    writer.close()
    body = TestClient(serve.app, raise_server_exceptions=False).get(
        _QUERY, params=_LEXICAL, headers=_reference_auth(monkeypatch)).json()
    assert body["generation"]["generation_id"] == generation_id
    assert plain_sha not in {c["chunk_sha256"] for c in body["citations"]}
    assert body["retrieval"]["revoked_suppressed"] == 1
    assert "source rights, admission or withdrawal enforcement" in body["not_claimed"]


def test_a08_empty_evidence_abstains_without_prose_or_citation(monkeypatch, tmp_path):
    import serve

    rag, _db_path, generation_id = _published_engine(monkeypatch, tmp_path, serve._rag_engine)
    _forbid_engine_work(monkeypatch, rag)
    response = TestClient(serve.app, raise_server_exceptions=False).get(
        _QUERY, params={"q": "zebra quasar", "mode": "lexical"},
        headers=_reference_auth(monkeypatch))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["result_state"] == "ABSTAINED"
    assert body["i_dont_know"] is True
    assert body["answer"] is None
    assert body["citations"] == []
    assert body["evidence_set"] == []
    assert body["evidence_set_sha256"] == hashlib.sha256(b"[]").hexdigest()
    assert body["generation"]["generation_id"] == generation_id
    assert "not verified factual support" in body["support_statement"]


def test_a09_repeated_lexical_reads_have_no_receipt_signing_or_state_write(monkeypatch, tmp_path):
    import serve

    rag, _db_path, _generation_id = _published_engine(monkeypatch, tmp_path, serve._rag_engine)
    before = _storage_fingerprint(tmp_path)
    _forbid_engine_work(monkeypatch, rag)
    monkeypatch.setattr(serve, "_rag_emit_receipt", _forbid("lexical GET minted a receipt"))
    monkeypatch.setattr(serve, "_a11oy_sign_receipt", _forbid("lexical GET signed"),
                        raising=False)
    client = TestClient(serve.app, raise_server_exceptions=False)
    headers = _reference_auth(monkeypatch)
    seen = []
    for route in (_QUERY, "/org/rag", _QUERY, "/org/rag"):
        response = client.get(route, params=_LEXICAL, headers=headers)
        assert response.status_code == 200, response.text
        body = response.json()
        body.pop("fetchedAt", None)
        seen.append(body)
        status = client.get("/api/a11oy/v1/rag/status")
        assert status.status_code == 200
        assert status.json()["engine"]["lexical_reference"] == "SUPPORTED"
    assert all(body == seen[0] for body in seen)
    assert seen[0]["receipt_hash"] is None
    assert _storage_fingerprint(tmp_path) == before


def test_a15_lexical_reference_records_zero_dispatch_without_network(monkeypatch, tmp_path):
    import http.client
    import socket
    import urllib.request
    import serve

    rag, _db_path, _generation_id = _published_engine(monkeypatch, tmp_path, serve._rag_engine)
    _forbid_engine_work(monkeypatch, rag)
    monkeypatch.setattr(socket, "create_connection", _forbid("network connection"))
    monkeypatch.setattr(http.client.HTTPConnection, "connect", _forbid("HTTP dispatch"))
    monkeypatch.setattr(urllib.request, "urlopen", _forbid("URL dispatch"))
    try:
        import a11oy_code_orchestrator
    except Exception:  # pragma: no cover - optional module in a stripped runtime
        a11oy_code_orchestrator = None
    if a11oy_code_orchestrator is not None:
        monkeypatch.setattr(a11oy_code_orchestrator, "agent_model_complete",
                            _forbid("model completion dispatched"))
    response = TestClient(serve.app, raise_server_exceptions=False).get(
        _QUERY, params=_LEXICAL, headers=_reference_auth(monkeypatch))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["router_dispatch_count"] == 0
    assert body["inference"] == "NOT_INVOKED"
    assert body["embedder_invoked"] is False
    assert "provider" not in body and "model" not in body
    assert "factual support, entailment or calibrated confidence" in body["not_claimed"]


def _legacy_engine(name: str, calls: list, *, contract=None, query=None) -> ModuleType:
    engine = ModuleType(name)

    def legacy_query(q, k=6, repo=None, hyde_text=None, emit_receipt=None,
                     load_embedder=False, source_witness=None):
        calls.append(q)
        return _grounded_result()

    engine.query = query or legacy_query
    engine.status = lambda: {"built": True}
    engine.corpus_manifest = lambda: {"repositories": []}
    if contract is not None:
        engine.LEXICAL_REFERENCE_CONTRACT = contract
    return engine


def test_lexical_mode_fails_closed_when_the_imported_engine_lacks_the_switch(monkeypatch):
    import serve

    calls: list = []
    monkeypatch.setattr(serve, "_rag_engine",
                        _legacy_engine("szl_substrate.a11oy_org_rag", calls))
    monkeypatch.setattr(serve, "_rag_emit_receipt", _forbid("fail-closed read minted"))
    headers = _reference_auth(monkeypatch)
    client = TestClient(serve.app, raise_server_exceptions=False)

    for route in (_QUERY, "/org/rag"):
        response = client.get(route, params=_LEXICAL, headers=headers)
        assert response.status_code == 503, response.text
        body = response.json()
        assert body["reason_code"] == "LEXICAL_REFERENCE_UNSUPPORTED_BY_ENGINE"
        assert body["result_state"] == "UNAVAILABLE"
        assert body["citations"] == [] and body["answer"] is None
        assert body["engine"]["lexical_reference"] == "UNSUPPORTED"
        assert body["engine"]["lexical_reference_reason"] == "LEXICAL_REFERENCE_CONTRACT_ABSENT"
    assert calls == []
    status = client.get("/api/a11oy/v1/rag/status").json()
    assert status["engine"]["lexical_reference"] == "UNSUPPORTED"
    # The default read of the same engine is unchanged; lexical never borrowed it.
    default = client.get(_QUERY, params={"q": "published evidence"})
    assert default.status_code == 200
    assert calls == ["published evidence"]


def test_lexical_mode_rejects_an_engine_that_ignores_the_switch(monkeypatch):
    import serve

    calls: list = []

    def ignoring(q, k=6, repo=None, lexical_only=False, **_kwargs):
        calls.append(lexical_only)
        return _grounded_result()

    monkeypatch.setattr(serve, "_rag_engine", _legacy_engine(
        "a11oy_org_rag", calls, contract=serve._RAG_LEXICAL_CONTRACT, query=ignoring))
    response = TestClient(serve.app, raise_server_exceptions=False).get(
        _QUERY, params=_LEXICAL, headers=_reference_auth(monkeypatch))
    assert response.status_code == 503, response.text
    body = response.json()
    assert body["reason_code"] == "LEXICAL_REFERENCE_ENGINE_CONTRACT_VIOLATION"
    assert body["citations"] == []
    assert "Evidence from a published generation" not in response.text
    assert calls == [True]


def test_engine_identity_names_an_installed_package_by_file_digest(tmp_path):
    import serve

    module_file = tmp_path / "a11oy_org_rag.py"
    module_file.write_bytes(b"# older installed copy\n")
    stub = SimpleNamespace(__name__="szl_substrate.a11oy_org_rag", __file__=str(module_file))
    identity = serve._rag_engine_file_identity(stub)
    assert identity["origin"] == "installed_package"
    assert identity["distribution"] == "szl-substrate"
    assert identity["file_name"] == "a11oy_org_rag.py"
    assert identity["file_sha256"] == hashlib.sha256(b"# older installed copy\n").hexdigest()
    vendored = serve._rag_engine_file_identity(SimpleNamespace(__name__="a11oy_org_rag"))
    assert vendored["origin"] == "vendored" and vendored["file_sha256"] is None


def test_lexical_mode_bounds_and_unknown_modes_reject_before_query(monkeypatch):
    import serve

    monkeypatch.setattr(serve._rag_engine, "query", _forbid("rejected mode ran a query"))
    monkeypatch.setattr(serve._rag_engine, "status", _forbid("rejected mode read status"))
    headers = _reference_auth(monkeypatch)
    client = TestClient(serve.app, raise_server_exceptions=False)
    for route in (_QUERY, "/org/rag"):
        unknown = client.get(route, params={"q": "anchor", "mode": "hybrid"})
        assert unknown.status_code == 400
        assert unknown.json()["reason_code"] == "RAG_MODE_UNSUPPORTED"
        wide = client.get(route, params={**_LEXICAL, "k": 7}, headers=headers)
        assert wide.status_code == 400
        assert wide.json()["reason_code"] == "LEXICAL_REFERENCE_K_OUT_OF_BOUNDS"
        # Authentication precedes the reference bounds check.
        assert client.get(route, params={**_LEXICAL, "k": 7}).status_code == 401
        assert client.get(route, params={**_LEXICAL, "mode": "x" * 17}).status_code == 422


# --------------------------------------------------------------------------- #
# Packet 2: gdw_auth bearer + controller corpus scope on mode=lexical. Case IDs
# refer to the first A11oy journey contract; these are source-level tests only.
# --------------------------------------------------------------------------- #
_TENANT_A = ("tenant-a", "tenant-a-corpus", "fixture:tenant-a")
_TENANT_B = ("tenant-b", "tenant-b-corpus", "fixture:tenant-b")
_TENANT_ENTRIES = tuple(
    (repo, f"docs/{label}{index}.md", source, f"tenant {label} anchor evidence note {index}")
    for (_ns, repo, source), label in ((_TENANT_A, "alpha"), (_TENANT_B, "beta"))
    for index in range(3))


def _tenant_engine(monkeypatch, directory: Path, rag, entries=_TENANT_ENTRIES):
    """One shared generation holding two synthetic tenants' corpora."""
    directory.mkdir(parents=True, exist_ok=True)
    db_path = directory / "tenants.sqlite3"
    _reset_engine(monkeypatch, rag, db_path)
    conn = rag._db()
    try:
        rag._init_schema(conn)
        generation_id = rag._begin_generation(conn, "tenant-fixture")
        graph = rag.OrgGraph()
        for repo, path, source, body in entries:
            rag._ingest_text(graph, conn, repo=repo, path=path, raw=body, source=source,
                             category="doctrine", embed_fn=None, generation_id=generation_id)
        rag._persist_runtime_state(
            conn, graph, {"built": True, "mode": "tenant-fixture", "ts": 1.0, "repos": 2,
                          "chunks": len(entries)}, generation_id)
    finally:
        conn.close()
    _reset_engine(monkeypatch, rag, db_path)
    return db_path


def _instrument_store(monkeypatch, serve, rag, db_path: Path) -> list:
    """Record each engine, read-helper and SQLite entry that could touch content."""
    seen: list = []

    def wrap(owner, name):
        original = getattr(owner, name)

        @functools.wraps(original)
        def recorded(*args, **kwargs):
            seen.append(name)
            return original(*args, **kwargs)
        monkeypatch.setattr(owner, name, recorded)

    for name in ("query", "status", "corpus_manifest", "graph_dict", "repo_map",
                 "hydrate_answer_evidence", "_rehydrate_runtime_state", "_db_readonly",
                 "_db", "_active_generation", "_revoked_source_digests"):
        wrap(rag, name)
    for name in ("_rag_index_status", "_rag_lexical_reference", "_rag_answer",
                 "_rag_lexical_capability", "_rag_emit_receipt"):
        wrap(serve, name)
    real_connect = sqlite3.connect

    def connect(database, *args, **kwargs):
        if db_path.name in str(database):
            seen.append("sqlite3.connect")
        return real_connect(database, *args, **kwargs)
    monkeypatch.setattr(sqlite3, "connect", connect)
    return seen


_AUTHORITY_CLAIMS = {"tenant": "tenant-b", "namespace": "tenant-b", "principal": "reviewer-b",
                     "owner_id": "reviewer-b", "key_id": "key-b", "scope": _READ_SCOPE,
                     "corpus": "tenant-b-corpus", "source": "fixture:tenant-b"}
_AUTHORITY_HEADERS = {"X-SZL-Tenant": "tenant-b", "X-Tenant-Id": "tenant-b",
                      "X-Forwarded-User": "reviewer-b", "X-SZL-Principal": "reviewer-b"}


@pytest.mark.parametrize("case", ["missing", "malformed_scheme", "malformed_empty",
                                  "malformed_space", "forged", "revoked",
                                  "foreign_namespace", "missing_scope"])
def test_a02_bad_credentials_deny_before_any_index_or_content_access(
    monkeypatch, tmp_path, case,
):
    import serve

    rag, db_path, _generation_id = _published_engine(monkeypatch, tmp_path, serve._rag_engine)
    good, good_entry = _credential(_FIXTURE_NAMESPACE, owner="fixture-reviewer", key="reader-1")
    revoked, revoked_entry = _credential(_FIXTURE_NAMESPACE, owner="fixture-reviewer",
                                         key="reader-0", revoked=True)
    foreign, foreign_entry = _credential("other-tenant", owner="other-reviewer", key="reader-b")
    unscoped, unscoped_entry = _credential(_FIXTURE_NAMESPACE, owner="fixture-operator",
                                           key="ops-1", scopes=("gdw:read", "session:read"))
    _configure_reference(
        monkeypatch, scope=_scope_json(_FIXTURE_NAMESPACE, "a11oy", _FIXTURE_SOURCES),
        credentials=[good_entry, revoked_entry, foreign_entry, unscoped_entry])
    authorization, status, code = {
        "missing": (None, 401, "missing_authorization"),
        "malformed_scheme": ("Basic " + good, 401, "invalid_authorization"),
        "malformed_empty": ("Bearer", 401, "invalid_authorization"),
        "malformed_space": ("Bearer " + good + " extra", 401, "invalid_authorization"),
        "forged": ("Bearer " + secrets.token_urlsafe(32), 401, "invalid_bearer_token"),
        "revoked": ("Bearer " + revoked, 403, "credential_revoked"),
        "foreign_namespace": ("Bearer " + foreign, 403, "foreign_namespace"),
        "missing_scope": ("Bearer " + unscoped, 403, "missing_scopes"),
    }[case]
    headers = dict(_AUTHORITY_HEADERS)
    if authorization is not None:
        headers["Authorization"] = authorization
    before = _storage_fingerprint(tmp_path)
    seen = _instrument_store(monkeypatch, serve, rag, db_path)
    client = _isolated_client(serve)

    for route in (_QUERY, "/org/rag"):
        # Request-supplied principal, tenant and scope claims grant nothing.
        for params in (_LEXICAL, {**_LEXICAL, **_AUTHORITY_CLAIMS, "repo": "a11oy",
                                  "namespace": _FIXTURE_NAMESPACE},
                       {"mode": "lexical"}, {**_LEXICAL, "k": 7}):
            response = client.get(route, params=params, headers=headers)
            assert response.status_code == status, response.text
            body = response.json()
            assert body["state"] == "denied"
            assert body["error"] == code
            assert body["reason_code"] == "LEXICAL_REFERENCE_AUTHENTICATION_DENIED"
            assert body["result_state"] == "DENIED"
            assert body["citations"] == [] and body["answer"] is None
            assert "principal" not in body and "corpus_scope" not in body
            assert "generation" not in body and "engine" not in body
            for token in (good, revoked, foreign, unscoped):
                assert token not in response.text
            assert "docs/plain.md" not in response.text
            assert _ASCII_BODY not in response.text
            assert (response.headers.get("www-authenticate") == "Bearer") is (status == 401)
            assert response.headers["cache-control"] == "no-store"
    assert seen == []
    assert _storage_fingerprint(tmp_path) == before

    # Positive control: the same instrumentation observes a valid read reach the store.
    allowed = client.get(_QUERY, params=_LEXICAL, headers=_bearer(good))
    assert allowed.status_code == 200, allowed.text
    assert {"query", "_db_readonly", "sqlite3.connect"} <= set(seen)


def test_a03_partial_second_namespace_cannot_read_the_admitted_corpus(monkeypatch, tmp_path):
    """Two synthetic namespaces over ONE shared store. This shows the access
    contract on mode=lexical only; tenant storage isolation is not established."""
    import serve

    rag = serve._rag_engine
    db_path = _tenant_engine(monkeypatch, tmp_path, rag)
    token_a, entry_a = _credential("tenant-a", owner="reviewer-a", key="key-a")
    token_b, entry_b = _credential("tenant-b", owner="reviewer-b", key="key-b")
    credentials = [entry_a, entry_b]
    scope_a = _scope_json(*_TENANT_A[:2], [_TENANT_A[2]])
    scope_b = _scope_json(*_TENANT_B[:2], [_TENANT_B[2]])
    query = {"q": "anchor evidence", "mode": "lexical"}
    client = _isolated_client(serve)

    _configure_reference(monkeypatch, scope=scope_a, credentials=credentials)
    seen = _instrument_store(monkeypatch, serve, rag, db_path)
    for route in (_QUERY, "/org/rag"):
        for params in (query, {**query, "repo": "tenant-a-corpus"},
                       {**query, "tenant": "tenant-a", "namespace": "tenant-a"}):
            denied = client.get(route, params=params,
                                headers={**_bearer(token_b), "X-SZL-Tenant": "tenant-a"})
            assert denied.status_code == 403, denied.text
            assert denied.json()["error"] == "foreign_namespace"
            assert "tenant alpha" not in denied.text and "docs/alpha" not in denied.text
    assert seen == []

    for route in (_QUERY, "/org/rag"):
        own = client.get(route, params=query, headers=_bearer(token_a))
        assert own.status_code == 200, own.text
        body = own.json()
        assert body["result_state"] == "REFERENCE_RETURNED"
        assert body["principal"] == {"owner_id": "reviewer-a", "key_id": "key-a",
                                     "namespace": "tenant-a"}
        assert body["corpus_scope"]["repo"] == "tenant-a-corpus"
        assert {(c["repo"], c["source"]) for c in body["citations"]} == {
            ("tenant-a-corpus", "fixture:tenant-a")}
        assert {e["repo"] for e in body["evidence_set"]} == {"tenant-a-corpus"}
        assert "tenant beta" not in own.text and "tenant-b-corpus" not in own.text
        assert token_a not in own.text

    # Swap the admitted tenant: B now reads only B's corpus and A is foreign.
    _configure_reference(monkeypatch, scope=scope_b, credentials=credentials)
    for route in (_QUERY, "/org/rag"):
        foreign = client.get(route, params=query, headers=_bearer(token_a))
        assert foreign.status_code == 403
        assert foreign.json()["error"] == "foreign_namespace"
        own = client.get(route, params=query, headers=_bearer(token_b))
        assert own.status_code == 200, own.text
        assert {c["repo"] for c in own.json()["citations"]} == {"tenant-b-corpus"}
        assert "tenant alpha" not in own.text and "docs/alpha" not in own.text
        crossing = client.get(route, params={**query, "repo": "tenant-a-corpus"},
                              headers=_bearer(token_b))
        assert crossing.status_code == 403
        assert crossing.json()["reason_code"] == "LEXICAL_REFERENCE_REQUEST_SCOPE_DENIED"
        assert "tenant alpha" not in crossing.text


def test_a03_limit_default_read_is_not_a_tenant_boundary(monkeypatch, tmp_path):
    """Limitation witness, not a guarantee: the unchanged public default GET reads
    the same shared store, so only public or synthetic corpora may be admitted.
    Update this test when the default read is closed or scoped."""
    import serve

    _tenant_engine(monkeypatch, tmp_path, serve._rag_engine)
    _configure_reference(monkeypatch, scope=_scope_json(*_TENANT_A[:2], [_TENANT_A[2]]),
                         credentials=[_credential("tenant-a", owner="reviewer-a", key="key-a")[1]])
    default = _isolated_client(serve).get(
        _QUERY, params={"q": "anchor evidence", "repo": "tenant-a-corpus"})
    assert default.status_code == 200, default.text
    assert {c["repo"] for c in default.json()["citations"]} == {"tenant-a-corpus"}


def test_a04_request_fields_cannot_widen_the_admitted_scope(monkeypatch, tmp_path):
    import serve

    rag = serve._rag_engine
    db_path = _tenant_engine(monkeypatch, tmp_path / "shared", rag)
    token_a, entry_a = _credential("tenant-a", owner="reviewer-a", key="key-a")
    _configure_reference(monkeypatch, scope=_scope_json(*_TENANT_A[:2], [_TENANT_A[2]]),
                         credentials=[entry_a])
    query = {"q": "anchor evidence", "mode": "lexical"}
    client = _isolated_client(serve)
    baseline = client.get(_QUERY, params=query, headers=_bearer(token_a)).json()
    baseline.pop("fetchedAt", None)
    assert {c["repo"] for c in baseline["citations"]} == {"tenant-a-corpus"}

    # A request repo naming anything but the admitted corpus is refused before any read.
    seen = _instrument_store(monkeypatch, serve, rag, db_path)
    for route in (_QUERY, "/org/rag"):
        for repo in ("tenant-b-corpus", "m1-brain-ledger", "a11oy", "TENANT-A-CORPUS",
                     "tenant-a-corpus "):
            refused = client.get(route, params={**query, "repo": repo}, headers=_bearer(token_a))
            assert refused.status_code == 403, (repo, refused.text)
            assert refused.json()["reason_code"] == "LEXICAL_REFERENCE_REQUEST_SCOPE_DENIED"
            assert "tenant beta" not in refused.text and "tenant alpha" not in refused.text
    assert seen == []

    # Tenant, principal and corpus claims in the query or headers are ignored.
    for route in (_QUERY, "/org/rag"):
        claimed = client.get(route, params={**query, **_AUTHORITY_CLAIMS,
                                            "repo": "tenant-a-corpus"},
                             headers={**_bearer(token_a), **_AUTHORITY_HEADERS})
        assert claimed.status_code == 200, claimed.text
        body = claimed.json()
        body.pop("fetchedAt", None)
        assert body == baseline
        assert "tenant beta" not in claimed.text

    # Exact admitted sources only: an unadmitted source inside the admitted repo
    # fails closed and releases nothing, rather than being silently filtered.
    mixed = _TENANT_ENTRIES + (("tenant-a-corpus", "docs/stray.md", "fixture:unadmitted",
                                "stray unadmitted anchor evidence"),)
    _tenant_engine(monkeypatch, tmp_path / "mixed", rag, entries=mixed)
    for route in (_QUERY, "/org/rag"):
        stray = client.get(route, params=query, headers=_bearer(token_a))
        assert stray.status_code == 503, stray.text
        body = stray.json()
        assert body["reason_code"] == "LEXICAL_REFERENCE_SCOPE_VIOLATION"
        assert body["integrity_state"] == "FAILED_CLOSED"
        assert body["citations"] == [] and body["answer"] is None
        assert "evidence_set" not in body
        assert "stray unadmitted" not in stray.text and "tenant alpha" not in stray.text
        assert "fixture:unadmitted" not in stray.text


def test_a09_authenticated_and_denied_repeat_reads_have_no_side_effects(monkeypatch, tmp_path):
    import serve

    rag, _db_path, _generation_id = _published_engine(monkeypatch, tmp_path, serve._rag_engine)
    headers = _reference_auth(monkeypatch)
    before = _storage_fingerprint(tmp_path)
    _forbid_engine_work(monkeypatch, rag)
    monkeypatch.setattr(serve, "_rag_emit_receipt", _forbid("lexical GET minted a receipt"))
    monkeypatch.setattr(serve, "_a11oy_sign_receipt", _forbid("lexical GET signed"),
                        raising=False)
    client = _isolated_client(serve)
    allowed, denied = [], []
    for _round in range(3):
        for route in (_QUERY, "/org/rag"):
            refused = client.get(route, params=_LEXICAL)
            assert refused.status_code == 401
            denied.append(refused.json())
            response = client.get(route, params=_LEXICAL, headers=headers)
            assert response.status_code == 200, response.text
            # No shared or browser cache may replay an authenticated reference.
            assert response.headers["cache-control"] == "no-store"
            assert "authorization" in response.headers["vary"].lower()
            body = response.json()
            body.pop("fetchedAt", None)
            allowed.append(body)
        status = client.get("/api/a11oy/v1/rag/status")
        assert status.json()["lexical_reference_auth"]["authentication"] == "REQUIRED"
    assert all(body == allowed[0] for body in allowed)
    assert all(body == denied[0] for body in denied)
    assert allowed[0]["receipt_hash"] is None
    assert _storage_fingerprint(tmp_path) == before


@pytest.mark.parametrize("config,reason", [
    ("nothing", "REFERENCE_SCOPE_UNCONFIGURED"),
    ("credentials_only", "REFERENCE_SCOPE_UNCONFIGURED"),
    ("scope_only", "REFERENCE_CREDENTIALS_UNCONFIGURED"),
    ("scope_two_tenants", "REFERENCE_SCOPE_INVALID"),
    ("scope_extra_field", "REFERENCE_SCOPE_INVALID"),
    ("scope_duplicate_key", "REFERENCE_SCOPE_INVALID"),
    ("scope_empty_sources", "REFERENCE_SCOPE_INVALID"),
    ("registry_malformed", "REFERENCE_CREDENTIALS_INVALID"),
    ("registry_and_principals", "REFERENCE_CREDENTIALS_INVALID"),
])
def test_unconfigured_reference_is_503_without_any_fallback(monkeypatch, tmp_path, config, reason):
    import serve

    rag, db_path, _generation_id = _published_engine(monkeypatch, tmp_path, serve._rag_engine)
    token, entry = _credential(_FIXTURE_NAMESPACE, owner="fixture-reviewer", key="reader-1")
    scope = _scope_json(_FIXTURE_NAMESPACE, "a11oy", _FIXTURE_SOURCES)
    tenant = {"repo": "a11oy", "sources": list(_FIXTURE_SOURCES)}
    _configure_reference(monkeypatch, scope=None)
    env = {
        "nothing": {},
        "credentials_only": {"A11OY_RAG_REFERENCE_CREDENTIALS_JSON": _registry_json([entry])},
        "scope_only": {"A11OY_RAG_REFERENCE_SCOPE_JSON": scope},
        "scope_two_tenants": {"A11OY_RAG_REFERENCE_SCOPE_JSON": json.dumps(
            {"version": 1, "tenants": {_FIXTURE_NAMESPACE: tenant, "other-tenant": tenant}})},
        "scope_extra_field": {"A11OY_RAG_REFERENCE_SCOPE_JSON": json.dumps(
            {"version": 1, "tenants": {_FIXTURE_NAMESPACE: {**tenant, "visibility": "all"}}})},
        "scope_duplicate_key": {"A11OY_RAG_REFERENCE_SCOPE_JSON": scope[:-1] + ', "version": 1}'},
        "scope_empty_sources": {"A11OY_RAG_REFERENCE_SCOPE_JSON": _scope_json(
            _FIXTURE_NAMESPACE, "a11oy", [])},
        "registry_malformed": {"A11OY_RAG_REFERENCE_SCOPE_JSON": scope,
                               "A11OY_RAG_REFERENCE_CREDENTIALS_JSON": "{not json"},
        "registry_and_principals": {
            "A11OY_RAG_REFERENCE_SCOPE_JSON": scope,
            "A11OY_RAG_REFERENCE_CREDENTIALS_JSON": _registry_json([entry]),
            "A11OY_RAG_REFERENCE_PRINCIPALS_JSON": json.dumps({"fixture-reviewer": {
                "token_sha256": entry["token_sha256"], "roles": ["user"]}})},
    }[config]
    if config in {"scope_two_tenants", "scope_extra_field", "scope_duplicate_key",
                  "scope_empty_sources"}:
        env["A11OY_RAG_REFERENCE_CREDENTIALS_JSON"] = _registry_json([entry])
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    seen = _instrument_store(monkeypatch, serve, rag, db_path)
    client = _isolated_client(serve)
    for route in (_QUERY, "/org/rag"):
        for headers in ({}, _bearer(token)):
            response = client.get(route, params=_LEXICAL, headers=headers)
            assert response.status_code == 503, response.text
            body = response.json()
            assert body["reason_code"] == reason
            assert body["authentication"] == "UNCONFIGURED"
            assert body["result_state"] == "UNAVAILABLE"
            assert body["citations"] == [] and body["answer"] is None
            assert "grounded" not in body and "retrieval" not in body
            assert _ASCII_BODY not in response.text and token not in response.text
    assert seen == []
    status = client.get("/api/a11oy/v1/rag/status").json()["lexical_reference_auth"]
    assert status["authentication"] == "UNCONFIGURED"
    assert status["reason_code"] == reason
    # The default read is unchanged and stays public.
    default = client.get(_QUERY, params={"q": "anchor evidence"})
    assert default.status_code == 200, default.text
    assert default.json()["grounded"] is True


def test_reference_reuses_the_gdw_registry_only_without_a_dedicated_one(monkeypatch, tmp_path):
    import serve

    _published_engine(monkeypatch, tmp_path, serve._rag_engine)
    gdw_reader, gdw_reader_entry = _credential(_FIXTURE_NAMESPACE, owner="gdw-reader",
                                               key="gdw-1")
    gdw_writer, gdw_writer_entry = _credential(_FIXTURE_NAMESPACE, owner="gdw-writer",
                                               key="gdw-2", scopes=("gdw:read", "gdw:write"))
    dedicated, dedicated_entry = _credential(_FIXTURE_NAMESPACE, owner="fixture-reviewer",
                                             key="reader-1")
    _configure_reference(monkeypatch, scope=_scope_json(
        _FIXTURE_NAMESPACE, "a11oy", _FIXTURE_SOURCES))
    monkeypatch.setenv("GDW_CREDENTIALS_JSON", _registry_json([gdw_reader_entry,
                                                               gdw_writer_entry]))
    client = _isolated_client(serve)
    shared = client.get(_QUERY, params=_LEXICAL, headers=_bearer(gdw_reader))
    assert shared.status_code == 200, shared.text
    assert shared.json()["principal"]["owner_id"] == "gdw-reader"
    unscoped = client.get(_QUERY, params=_LEXICAL, headers=_bearer(gdw_writer))
    assert unscoped.status_code == 403
    assert unscoped.json()["error"] == "missing_scopes"

    monkeypatch.setenv("A11OY_RAG_REFERENCE_CREDENTIALS_JSON", _registry_json([dedicated_entry]))
    assert client.get(_QUERY, params=_LEXICAL, headers=_bearer(dedicated)).status_code == 200
    ignored = client.get(_QUERY, params=_LEXICAL, headers=_bearer(gdw_reader))
    assert ignored.status_code == 401
    assert ignored.json()["error"] == "invalid_bearer_token"


def test_rag_status_reports_reference_auth_without_tenant_or_credential_content(
    monkeypatch, tmp_path,
):
    import serve

    # No index: the status body then carries only the new auth state plus config.
    _reset_engine(monkeypatch, serve._rag_engine, tmp_path / "absent.sqlite3")
    token, entry = _credential("tenant-a", owner="reviewer-a", key="key-a")
    _configure_reference(monkeypatch, scope=_scope_json(*_TENANT_A[:2], [_TENANT_A[2]]),
                         credentials=[entry])
    response = _isolated_client(serve).get(
        "/api/a11oy/v1/rag/status")
    assert response.status_code == 200
    assert response.json()["lexical_reference_auth"] == {
        "authentication": "REQUIRED", "reason_code": None, "scheme": "bearer",
        "required_scope": _READ_SCOPE, "session_expiry": "NOT_IMPLEMENTED"}
    for private in ("tenant-a", "fixture:tenant-a", "reviewer-a", "key-a", token,
                    entry["token_sha256"], "tenant alpha"):
        assert private not in response.text


@pytest.mark.parametrize("document", [
    "", "[]", '{"version": 1}', '{"version": true, "tenants": {}}',
    '{"version": 2, "tenants": {"t": {"repo": "r", "sources": ["s"]}}}',
    '{"version": 1, "tenants": {}}',
    '{"version": 1, "tenants": {"Tenant": {"repo": "r", "sources": ["s"]}}}',
    '{"version": 1, "tenants": {"t": {"repo": "a/b", "sources": ["s"]}}}',
    '{"version": 1, "tenants": {"t": {"repo": "", "sources": ["s"]}}}',
    '{"version": 1, "tenants": {"t": {"repo": "r", "sources": "s"}}}',
    '{"version": 1, "tenants": {"t": {"repo": "r", "sources": ["s", "s"]}}}',
    '{"version": 1, "tenants": {"t": {"repo": "r", "sources": ["has space"]}}}',
    '{"version": 1, "tenants": {"t": {"repo": "r"}}}',
])
def test_reference_scope_parser_is_strict(document):
    import a11oy_rag_reference_auth as reference

    with pytest.raises(reference.ReferenceScopeError):
        reference.parse_reference_scope(document)
    parsed = reference.parse_reference_scope(
        '{"version": 1, "tenants": {"t": {"repo": "r", "sources": ["s2", "s1"]}}}')
    assert parsed == reference.ReferenceScope(namespace="t", repo="r", sources=("s1", "s2"))
