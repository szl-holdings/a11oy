# SPDX-License-Identifier: Apache-2.0
"""D1: the org RAG store binds a tenant to every chunk at ingestion.

Before this change ``org_chunks_gen`` had no tenant column, ``_ingest_text``
took no tenant, chunk ids were derived from ``source:fid:j`` only, and the
generation digest sealed no tenant. The same file ingested for two tenants
therefore produced colliding chunk ids, and ``INSERT OR REPLACE`` on
``org_vectors_gen`` let the second tenant's vector replace the first.

Synthetic fixtures only. No network, no credentials, no model calls.
"""
from __future__ import annotations

import base64
import hashlib
import inspect
import json
import sqlite3

import pytest

import a11oy_org_rag as rag

TENANT_ENV = "A11OY_ORG_RAG_TENANT"
BODY = "def alpha():\n    return 1\n\n\ndef beta():\n    return 2\n"
ORIGINAL = "owned-token stable alpha evidence"
CHANGED = "owned-token stable alpha evidence beta-only"
REGRESSION = "stable alpha evidence"
HOLDOUT = "owned-token holdout evidence"
_CHUNK_COLUMNS = ("chunk_id", "node_id", "repo", "path", "kind", "corpus", "source",
                  "title", "body", "sha256")


@pytest.fixture
def env(monkeypatch, tmp_path):
    db_path = tmp_path / "rag.sqlite3"
    monkeypatch.setattr(rag, "RAG_DB_PATH", str(db_path))
    monkeypatch.setattr(rag, "_GRAPH", rag.OrgGraph())
    monkeypatch.setattr(rag, "_BUILD_META", {"built": False})
    monkeypatch.setattr(rag, "_REHYDRATE_ATTEMPTED", False)
    monkeypatch.setattr(rag, "_build_thread", None)
    monkeypatch.setattr(rag, "_maybe_embedder", lambda load=True: None)
    monkeypatch.setattr(rag, "_resolve_m1_ledger", lambda: None)
    monkeypatch.delenv(TENANT_ENV, raising=False)
    return db_path


@pytest.fixture(params=["fts5", "plain"])
def conn(request, monkeypatch, env):
    if request.param == "plain":
        monkeypatch.setattr(rag, "_fts5_available", lambda _conn: False)
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    has_fts5 = rag._init_schema(connection)
    if request.param == "fts5" and not has_fts5:
        pytest.skip("SQLite FTS5 unavailable in this runtime")
    yield connection
    connection.close()


def _ingest(conn, tenant, *, generation="g1", path="pkg/a.py", embed_fn=None, graph=None):
    return rag._ingest_text(
        graph if graph is not None else rag.OrgGraph(), conn, repo="fixture", path=path,
        raw=BODY, source="fixture:owned", category="app_code", embed_fn=embed_fn,
        generation_id=generation, tenant_id=tenant)


def _forbid_network(monkeypatch):
    calls = []

    def record(name):
        return lambda *args, **kwargs: calls.append(name)

    monkeypatch.setattr(rag, "_gh_token", lambda: "synthetic-not-a-credential")
    for name in ("_gh_get", "_gh_raw", "_hf_raw", "_hf_space_files"):
        monkeypatch.setattr(rag, name, record(name))
    monkeypatch.setattr(rag, "_corpus_root", lambda: None)
    return calls


def _make_pre_tenant_db(db_path):
    """A database file written before the tenant column existed."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    if rag._fts5_available(conn):
        conn.execute(
            "CREATE VIRTUAL TABLE org_chunks_gen USING fts5(generation_id UNINDEXED, "
            "chunk_id UNINDEXED, node_id UNINDEXED, repo UNINDEXED, path UNINDEXED, "
            "kind UNINDEXED, corpus UNINDEXED, source UNINDEXED, title, body, sha256 UNINDEXED)")
    else:
        conn.execute(
            "CREATE TABLE org_chunks_gen(generation_id TEXT, chunk_id TEXT, node_id TEXT, "
            "repo TEXT, path TEXT, kind TEXT, corpus TEXT, source TEXT, title TEXT, body TEXT, "
            "sha256 TEXT)")
    rag._init_schema(conn)  # every other table is unchanged by tenant binding
    return conn


def test_chunk_table_has_a_tenant_column(conn):
    columns = [row[1] for row in conn.execute("PRAGMA table_info(org_chunks_gen)")]
    assert "tenant_id" in columns


def test_plain_chunk_table_refuses_a_row_without_tenant(monkeypatch, env):
    monkeypatch.setattr(rag, "_fts5_available", lambda _conn: False)
    connection = sqlite3.connect(":memory:")
    try:
        assert rag._init_schema(connection) is False
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO org_chunks_gen(generation_id,chunk_id,node_id,repo,path,kind,"
                "corpus,source,title,body,sha256) VALUES('g','c','n','r','p','file','app_code',"
                "'s','t','b','x')")
    finally:
        connection.close()


def test_ingest_text_requires_a_keyword_only_tenant():
    params = inspect.signature(rag._ingest_text).parameters
    assert "tenant_id" in params
    assert params["tenant_id"].kind is inspect.Parameter.KEYWORD_ONLY
    assert params["tenant_id"].default is inspect.Parameter.empty


def test_ingested_rows_carry_the_supplied_tenant(conn):
    assert _ingest(conn, "tenant-a") >= 1
    tenants = {row[0] for row in conn.execute(
        "SELECT tenant_id FROM org_chunks_gen WHERE generation_id='g1'")}
    assert tenants == {"tenant-a"}


@pytest.mark.parametrize("bad", ["", "   ", None, 7, "a\x00b", "t\u00e9nant", "x" * 129,
                                 "../etc", " tenant-a", "tenant-a\n", "a:b", "a/b"])
def test_invalid_tenant_is_refused_before_any_write(conn, bad):
    # ValueError specifically: an unknown keyword raises TypeError, which must not pass.
    graph = rag.OrgGraph()
    with pytest.raises(ValueError):
        _ingest(conn, bad, graph=graph)
    assert conn.execute("SELECT COUNT(*) FROM org_chunks_gen").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM org_vectors_gen").fetchone()[0] == 0
    assert not graph.nodes


def test_one_file_for_two_tenants_keeps_distinct_rows_and_vectors(conn):
    vectors = {"tenant-a": [1.0, 0.0], "tenant-b": [0.0, 1.0]}
    for tenant, vec in vectors.items():
        _ingest(conn, tenant, embed_fn=lambda _segment, vec=vec: vec)
    ids: dict[str, set] = {}
    for row in conn.execute("SELECT tenant_id, chunk_id FROM org_chunks_gen"):
        ids.setdefault(row[0], set()).add(row[1])
    assert set(ids) == {"tenant-a", "tenant-b"}
    assert ids["tenant-a"] and ids["tenant-a"].isdisjoint(ids["tenant-b"])
    stored = {row[0]: json.loads(row[1]) for row in conn.execute(
        "SELECT chunk_id, vec FROM org_vectors_gen WHERE generation_id='g1'")}
    assert len(stored) == len(ids["tenant-a"]) + len(ids["tenant-b"])
    for tenant, chunk_ids in ids.items():
        assert all(stored[chunk_id] == vectors[tenant] for chunk_id in chunk_ids)


def test_generation_digest_seals_the_tenant(conn):
    # Same chunk ids and bytes in two generations; only tenant_id differs.
    _ingest(conn, "tenant-a", generation="ga")
    conn.execute(
        "INSERT INTO org_chunks_gen(generation_id,chunk_id,node_id,repo,path,kind,corpus,"
        "source,title,body,sha256,tenant_id) SELECT 'gb',chunk_id,node_id,repo,path,kind,"
        "corpus,source,title,body,sha256,'tenant-b' FROM org_chunks_gen WHERE generation_id='ga'")
    digest_a, counts_a = rag._generation_digest(conn, "ga", {})
    digest_b, counts_b = rag._generation_digest(conn, "gb", {})
    assert counts_a["chunks"] == counts_b["chunks"] >= 1
    assert digest_a != digest_b


@pytest.mark.parametrize("value", [None, "", "   ", "a:b", "bad tenant"])
def test_build_tenant_unset_or_invalid_is_refused(monkeypatch, env, value):
    if value is not None:
        monkeypatch.setenv(TENANT_ENV, value)
    with pytest.raises(RuntimeError, match=TENANT_ENV):
        rag._ingest_tenant()


def test_build_tenant_is_taken_verbatim_when_valid(monkeypatch, env):
    monkeypatch.setenv(TENANT_ENV, "tenant-a")
    assert rag._ingest_tenant() == "tenant-a"


@pytest.mark.parametrize("builder", ["index", "seed", "full"])
def test_build_paths_refuse_without_a_tenant_before_any_read_or_write(monkeypatch, env, builder):
    calls = _forbid_network(monkeypatch)
    if builder == "index":
        out = rag.build_index(repos=["pubrepo"])
    elif builder == "seed":
        out = rag.build_seed_index()
    else:
        out = rag.build_full_corpus()
    assert out["ok"] is False and out["built"] is False
    assert TENANT_ENV in out["honest_error"]
    assert calls == []
    assert not env.exists()


def test_build_index_rows_and_chunk_ids_follow_the_build_tenant(monkeypatch, env):
    files = {"README.md": b"tenant bound retrieval notes alpha\n"}
    prefix = f"/repos/{rag.ORG}/pubrepo"

    def fake_get(path, token, params=None):
        if path == prefix:
            return {"default_branch": "main"}
        if path == f"{prefix}/git/trees/main":
            return {"sha": "f" * 40, "tree": [
                {"path": name, "type": "blob", "size": len(data), "sha": "0" * 40}
                for name, data in files.items()]}
        if path.startswith(f"{prefix}/contents/"):
            data = files[path[len(f"{prefix}/contents/"):]]
            return {"content": base64.b64encode(data).decode("ascii")}
        raise AssertionError(path)

    monkeypatch.setattr(rag, "_gh_token", lambda: "synthetic-not-a-credential")
    monkeypatch.setattr(rag, "_gh_get", fake_get)
    generations = {}
    for tenant in ("tenant-a", "tenant-b"):
        monkeypatch.setenv(TENANT_ENV, tenant)
        out = rag.build_index(repos=["pubrepo"])
        assert out["ok"] is True
        generations[tenant] = out["generation_id"]
    db = sqlite3.connect(env)
    try:
        rows = {tenant: db.execute(
            "SELECT chunk_id, tenant_id FROM org_chunks_gen WHERE generation_id=?",
            (generation,)).fetchall() for tenant, generation in generations.items()}
    finally:
        db.close()
    for tenant, tenant_rows in rows.items():
        assert tenant_rows and {row[1] for row in tenant_rows} == {tenant}
    assert {row[0] for row in rows["tenant-a"]}.isdisjoint({row[0] for row in rows["tenant-b"]})


def test_pre_tenant_database_takes_no_new_generation(monkeypatch, env):
    conn = _make_pre_tenant_db(env)
    try:
        with pytest.raises(RuntimeError, match="tenant_id"):
            rag._begin_generation(conn, "after-upgrade")
        assert conn.execute("SELECT COUNT(*) FROM org_generations").fetchone()[0] == 0
    finally:
        conn.close()
    monkeypatch.setenv(TENANT_ENV, "tenant-a")
    calls = _forbid_network(monkeypatch)
    with pytest.raises(RuntimeError, match="tenant_id"):
        rag.build_seed_index()
    assert calls == []


def test_pre_tenant_database_fails_closed_on_rehydrate(env):
    # An ACTIVE generation sealed with the pre-tenant digest (columns without tenant_id).
    conn = _make_pre_tenant_db(env)
    body = "legacy tenantless evidence"
    row = ("c-legacy", "szl-holdings/a11oy:README.md", "a11oy", "README.md", "file",
           "app_code", "test:fixture", "README.md", body, hashlib.sha256(body.encode()).hexdigest())
    conn.execute("INSERT INTO org_chunks_gen(generation_id," + ",".join(_CHUNK_COLUMNS) + ") "
                 "VALUES(?,?,?,?,?,?,?,?,?,?,?)", ("g-legacy", *row))
    graph_data = {"edges": [], "nodes": []}
    digest = hashlib.sha256(rag._canonical_json(graph_data).encode("utf-8"))
    digest.update(b"chunks\0" + rag._canonical_json(list(row)).encode("utf-8") + b"\n")
    conn.execute(
        "INSERT INTO org_generations(generation_id,status,mode,created_at,activated_at,"
        "chunk_count,vector_count,brain_handle_count,graph_json,meta_json,digest_sha256) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        ("g-legacy", "ACTIVE", "legacy", 1.0, 1.0, 1, 0, 0, rag._canonical_json(graph_data),
         rag._canonical_json({"built": True, "mode": "legacy", "chunks": 1}), digest.hexdigest()))
    conn.execute("INSERT INTO org_active_generation(singleton,generation_id) VALUES(1,?)",
                 ("g-legacy",))
    conn.commit()
    conn.close()
    before = hashlib.sha256(env.read_bytes()).hexdigest()
    assert rag._rehydrate_runtime_state() is False
    assert rag.status()["built"] is False
    refused = rag.query("legacy tenantless", k=1)
    assert refused["ok"] is False and refused["i_dont_know"] is True
    assert hashlib.sha256(env.read_bytes()).hexdigest() == before


def _recover(tmp_path, tenant, operation_id):
    return rag.run_stale_index_recovery(
        source_path="fixture/owned-source.txt", source_revision="rev-1",
        original_body=ORIGINAL, changed_body=CHANGED, actor="fixture-actor", tenant=tenant,
        auth_scope="recovery:isolate", operation_id=operation_id,
        incident_id=f"inc-{operation_id}", required_tokens=("owned-token",),
        holdout_body=HOLDOUT, regression_body=REGRESSION, now=1_700_000_000.0,
        anatomy_path=str(tmp_path / f"{operation_id}.json"))


def test_recovery_staging_binds_the_operation_tenant(env, tmp_path):
    result = _recover(tmp_path, "tenant-a", "op-tenant-1")
    assert result["status"] == "VERIFIED"
    db = sqlite3.connect(env)
    try:
        tenants = {row[0] for row in db.execute("SELECT DISTINCT tenant_id FROM org_chunks_gen")}
    finally:
        db.close()
    assert tenants == {"tenant-a"}


def test_recovery_refuses_a_tenant_that_cannot_bind_rows(env, tmp_path):
    result = _recover(tmp_path, "tenant a", "op-tenant-2")
    assert result["status"] == "UNBOUND" and result["reason"] == "tenant"
    assert not env.exists()
