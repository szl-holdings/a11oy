# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Synthetic managed-store inspection bounds; no production receipts are read."""
import base64
from contextlib import closing
import hashlib
import sqlite3

import pytest

import a11oy_state_store as ss
import szl_provenance as provenance
from oro.source_adapters import project_source_snapshots
from tests.state_store_support import FakeClock, FakeHeadBackend, replica


def make_nodes(count, padding=None):
    nodes = []
    for index in range(count):
        receipt = {"schema": "test/inspection-window", "index": index,
                   "private_note": "synthetic-body-must-not-leave"}
        if padding and index in padding:
            receipt["padding"] = "x" * padding[index]
        body = provenance.szl_dsse.canonical_json(receipt)
        parents = [nodes[-1]["digest"]] if nodes else []
        digest = hashlib.sha256(body + b"".join(p.encode() for p in parents)).hexdigest()
        nodes.append({"index": index, "space": "a11oy", "wire": "F", "parents": parents,
                      "digest": digest, "receipt": receipt, "signed": False, "keyid": None,
                      "dsse": {"payloadType": provenance.szl_dsse.KHIPU_PAYLOAD_TYPE,
                               "payload": base64.b64encode(body).decode("ascii"),
                               "signed": False, "signatures": []}})
    return nodes


def seed(path, nodes, *, utf16=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path)) as db, db:
        if utf16:
            db.execute("PRAGMA encoding='UTF-16le'")
        db.execute("CREATE TABLE provenance_nodes (space TEXT NOT NULL, "
                   "sequence INTEGER NOT NULL, digest TEXT NOT NULL, node_json TEXT NOT NULL, "
                   "node_sha256 TEXT NOT NULL, PRIMARY KEY(space, sequence), UNIQUE(space, digest))")
        db.execute("CREATE TABLE provenance_heads (space TEXT PRIMARY KEY, "
                   "last_index INTEGER NOT NULL, digest TEXT NOT NULL)")
        for node in nodes:
            raw = ss.canonical(node)
            db.execute("INSERT INTO provenance_nodes VALUES (?,?,?,?,?)",
                       ("a11oy", node["index"], node["digest"], raw.decode("utf-8"),
                        hashlib.sha256(raw).hexdigest()))
        if nodes:
            db.execute("INSERT INTO provenance_heads VALUES (?,?,?)",
                       ("a11oy", nodes[-1]["index"], nodes[-1]["digest"]))


@pytest.fixture
def world(tmp_path, monkeypatch):
    manager = replica(tmp_path, "reader", ss.LocalDirObjectStore(tmp_path / "objects"),
                      FakeHeadBackend(), FakeClock())
    manager.role = ss.ROLE_WRITER
    manager.stores["khipu"].health = "OK"
    path = manager.local_path("khipu")
    nodes = make_nodes(40)
    seed(path, nodes)
    monkeypatch.setenv("A11OY_STATE_STORE", "v2")
    monkeypatch.setattr(ss, "_ACTIVE", manager)
    dag = provenance._KhipuDAG("a11oy")
    assert dag.managed
    return manager, dag, path, nodes


def trace_reads(monkeypatch):
    original = sqlite3.connect
    queries, connections = [], []
    def connect(*args, **kwargs):
        connections.append((args, kwargs))
        connection = original(*args, **kwargs)
        connection.set_trace_callback(queries.append)
        return connection
    monkeypatch.setattr(ss.sqlite3, "connect", connect)
    return queries, connections


def test_inspection_fetches_only_indexed_tail_and_creates_no_files(world, monkeypatch):
    manager, dag, path, nodes = world
    before = path.read_bytes()
    files = set(path.parent.iterdir())
    queries, connections = trace_reads(monkeypatch)
    monkeypatch.setattr(manager, "provenance_nodes",
                        lambda *_args: pytest.fail("full reader must not be called"))
    monkeypatch.setattr(manager, "begin_write",
                        lambda: pytest.fail("inspection must not admit a write"))
    monkeypatch.setattr(provenance.szl_dsse, "sign_payload",
                        lambda *_args: pytest.fail("inspection must not sign"))
    observed = dag.evidence_window(33)
    assert observed == nodes[-33:]
    selections = [q for q in queries if "FROM provenance_nodes" in q]
    assert len(selections) == 2
    assert all("ORDER BY sequence DESC LIMIT 33" in q for q in selections)
    assert "octet_length(node_json)" in selections[0]
    assert "SELECT sequence, digest, node_json, node_sha256" in selections[1]
    assert queries[0] == "BEGIN"
    assert len(connections) == 1
    assert connections[0][0][0].endswith("?mode=ro")
    assert connections[0][1] == {"uri": True, "timeout": 2.0}
    assert path.read_bytes() == before
    assert set(path.parent.iterdir()) == files
    with closing(sqlite3.connect(path)) as db, db:
        plan = db.execute("EXPLAIN QUERY PLAN SELECT sequence, digest, node_json, node_sha256 "
                          "FROM provenance_nodes WHERE space=? ORDER BY sequence DESC LIMIT ?",
                          ("a11oy", 33)).fetchall()
    assert any("SEARCH" in row[3] and "INDEX" in row[3] and "space=?" in row[3] for row in plan)
    assert not any("TEMP B-TREE" in row[3] for row in plan)


@pytest.mark.parametrize("padding", [{39: 600000}, {38: 300000, 39: 300000}])
def test_cumulative_byte_budget_refuses_before_any_body_fetch(world, monkeypatch, padding):
    manager, dag, path, _nodes = world
    path.unlink()
    seed(path, make_nodes(40, padding))
    with closing(sqlite3.connect(path)) as db, db:
        sizes = [row[0] for row in db.execute(
            "SELECT octet_length(node_json) FROM provenance_nodes "
            "WHERE space='a11oy' ORDER BY sequence DESC LIMIT 33")]
    assert sum(sizes) > ss.MAX_PROVENANCE_WINDOW_BYTES
    if len(padding) == 2:
        assert max(sizes) < ss.MAX_PROVENANCE_WINDOW_BYTES
    queries, _connections = trace_reads(monkeypatch)
    monkeypatch.setattr(ss.json, "loads", lambda *_args: pytest.fail("oversized bodies must not be decoded"))
    with pytest.raises(ss.StorageBlocked, match="PROVENANCE_WINDOW_BYTE_LIMIT"):
        manager.provenance_window("a11oy", 33, dag._validate_window)
    assert not any("SELECT sequence, digest, node_json, node_sha256" in q for q in queries)


@pytest.mark.parametrize("table,column", [
    ("provenance_heads", "digest"), ("provenance_heads", "last_index"),
    ("provenance_nodes", "digest"), ("provenance_nodes", "node_sha256"),
    ("provenance_nodes", "sequence"),
])
@pytest.mark.parametrize("storage_type", ["text", "blob"])
def test_oversized_metadata_is_not_returned_to_python_before_refusal(world, monkeypatch, table, column, storage_type):
    manager, dag, path, _nodes = world
    value = "x" * (ss.MAX_PROVENANCE_WINDOW_BYTES + 1)
    if storage_type == "blob":
        value = value.encode("ascii")
    with closing(sqlite3.connect(path)) as db, db:
        # The field names are this test's closed parametrization, not user input.
        where = "space='a11oy'" if table == "provenance_heads" else "sequence=39"
        db.execute(f"UPDATE {table} SET {column}=? WHERE {where}", (value,))
    before = path.read_bytes()
    files = set(path.parent.iterdir())
    original = sqlite3.connect
    queries, returned_metadata = [], []

    class Cursor:
        def __init__(self, cursor, sql):
            self.cursor, self.sql = cursor, sql

        def check(self, row):
            if row is not None and ("FROM provenance_heads" in self.sql
                    or "octet_length(node_json)" in self.sql):
                # Observe values at the DB/Python boundary, before the reader
                # can reject them with its own type or digest validation.
                assert all(value is None or type(value) is int
                           or (isinstance(value, str) and len(value.encode("utf-8")) <= 64)
                           for value in row), "unbounded or untyped metadata was materialized"
                returned_metadata.append(row)
            return row

        def fetchone(self):
            return self.check(self.cursor.fetchone())

        def fetchall(self):
            return [self.check(row) for row in self.cursor.fetchall()]

        def __iter__(self):
            return (self.check(row) for row in self.cursor)

    class Connection:
        def __init__(self, *args, **kwargs):
            self.connection = original(*args, **kwargs)

        def execute(self, sql, parameters=()):
            queries.append(sql)
            return Cursor(self.connection.execute(sql, parameters), sql)

        def close(self):
            self.connection.close()

    monkeypatch.setattr(ss.sqlite3, "connect", Connection)
    monkeypatch.setattr(manager, "begin_write", lambda: pytest.fail("inspection must not admit a write"))
    monkeypatch.setattr(provenance.szl_dsse, "sign_payload",
                        lambda *_args: pytest.fail("inspection must not sign"))
    with pytest.raises(ss.StorageBlocked):
        manager.provenance_window("a11oy", 33, dag._validate_window)
    assert returned_metadata
    assert not any("SELECT sequence, digest, node_json, node_sha256" in q for q in queries)
    assert path.read_bytes() == before
    assert set(path.parent.iterdir()) == files
    assert manager.role == ss.ROLE_WRITER and manager.stores["khipu"].health == "OK"


@pytest.mark.parametrize("table,column", [
    ("provenance_heads", "digest"), ("provenance_nodes", "digest"),
    ("provenance_nodes", "node_sha256"),
])
def test_invalid_utf8_metadata_refuses_without_loading_json_or_altering_store(world, monkeypatch, table, column):
    manager, dag, path, _nodes = world
    with closing(sqlite3.connect(path)) as db, db:
        where = "space='a11oy'" if table == "provenance_heads" else "sequence=39"
        # Invalid UTF-8 can inhabit SQLite TEXT even with the expected byte size.
        db.execute(f"UPDATE {table} SET {column}=CAST(? AS TEXT) WHERE {where}", (b"\x80" * 64,))
    before = path.read_bytes()
    files = set(path.parent.iterdir())
    queries, _connections = trace_reads(monkeypatch)
    with pytest.raises(ss.StorageBlocked):
        manager.provenance_window("a11oy", 33, dag._validate_window)
    assert not any("SELECT sequence, digest, node_json, node_sha256" in q for q in queries)
    assert path.read_bytes() == before
    assert set(path.parent.iterdir()) == files
    assert manager.role == ss.ROLE_WRITER and manager.stores["khipu"].health == "OK"


def test_earlier_corruption_is_outside_window_but_full_reader_still_refuses(world):
    manager, dag, path, nodes = world
    with closing(sqlite3.connect(path)) as db, db:
        db.execute("UPDATE provenance_nodes SET node_json='invalid' WHERE sequence=0")
    observed = dag.evidence_window(33)
    assert observed == nodes[-33:]
    projected = project_source_snapshots(canonical_khipu_dag=dag)
    source = projected["sources"]["canonical_khipu"]
    assert source["read_method"] == "evidence_window"
    assert source["validation_scope"] == "BOUNDED_WINDOW_ONLY"
    assert source["history_validation"] == "NOT_PERFORMED"
    assert source["window_complete"] is False
    assert all(node["evidence"]["proof_status"] == "UNVERIFIED" for node in projected["nodes"])
    assert "synthetic-body-must-not-leave" not in str(projected)
    with pytest.raises(provenance._LedgerUnavailable):
        dag.recent(33)
    with pytest.raises(ss.StorageBlocked):
        manager.provenance_nodes("a11oy", dag._validate)


@pytest.mark.parametrize("damage", [
    "UPDATE provenance_nodes SET node_sha256='bad' WHERE sequence=39",
    "UPDATE provenance_nodes SET node_json='' WHERE sequence=39",
    "UPDATE provenance_nodes SET node_json='{}' WHERE sequence=39",
    "DELETE FROM provenance_nodes WHERE sequence=38",
    "UPDATE provenance_heads SET last_index=38",
    "UPDATE provenance_heads SET digest='bad'",
    "DELETE FROM provenance_heads",
    "DROP TABLE provenance_heads",
])
def test_selected_corruption_or_tail_disagreement_is_unavailable(world, damage):
    _manager, dag, path, _nodes = world
    with closing(sqlite3.connect(path)) as db, db:
        db.execute(damage)
    with pytest.raises(provenance._LedgerUnavailable):
        dag.evidence_window(33)


@pytest.mark.parametrize("field,value", [
    ("parents", ["0" * 64]), ("index", True), ("space", "other"),
    ("receipt", {"changed": True}),
])
def test_selected_identity_and_local_chain_are_checked_even_with_updated_checksum(world, field, value):
    _manager, dag, path, nodes = world
    node = dict(nodes[-1])
    node[field] = value
    raw = ss.canonical(node)
    with closing(sqlite3.connect(path)) as db, db:
        db.execute("UPDATE provenance_nodes SET node_json=?,node_sha256=? WHERE sequence=39",
                   (raw.decode("utf-8"), hashlib.sha256(raw).hexdigest()))
    with pytest.raises(provenance._LedgerUnavailable):
        dag.evidence_window(33)


@pytest.mark.parametrize("limit", [0, -1, 34, True, 3.5, "33"])
def test_invalid_window_limit_is_refused_before_opening_store(world, monkeypatch, limit):
    manager, dag, _path, _nodes = world
    monkeypatch.setattr(manager, "_provenance_path", lambda: pytest.fail("invalid limit opened storage"))
    with pytest.raises(ValueError):
        manager.provenance_window("a11oy", limit, dag._validate_window)
    with pytest.raises(ValueError):
        dag.evidence_window(limit)


@pytest.mark.parametrize("case", ["booting", "unhealthy", "missing", "wal"])
def test_existing_passive_read_admission_remains_enforced(world, case):
    manager, dag, path, _nodes = world
    connection = None
    try:
        if case == "booting":
            manager.role = ss.ROLE_BOOTING
        elif case == "unhealthy":
            manager.stores["khipu"].health = "BLOCKED"
        elif case == "missing":
            path.unlink()
        else:
            connection = sqlite3.connect(path)
            assert connection.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
        with pytest.raises(provenance._LedgerUnavailable):
            dag.evidence_window(33)
        if case == "missing":
            assert not path.exists()
    finally:
        if connection is not None:
            connection.close()


def test_empty_existing_schema_is_an_observed_empty_window(world):
    _manager, dag, path, _nodes = world
    with closing(sqlite3.connect(path)) as db, db:
        db.execute("DELETE FROM provenance_nodes")
        db.execute("DELETE FROM provenance_heads")
    assert dag.evidence_window(33) == []


def test_unavailable_metadata_size_function_refuses_inspection_without_fallback(world, monkeypatch):
    manager, dag, path, nodes = world
    before = path.read_bytes()
    files = set(path.parent.iterdir())
    original = sqlite3.connect
    queries = []
    class NoOctetLength:
        def __init__(self, *args, **kwargs):
            self.connection = original(*args, **kwargs)
        def execute(self, sql, parameters=()):
            queries.append(sql)
            if "octet_length(" in sql:
                raise sqlite3.OperationalError("no such function: octet_length")
            return self.connection.execute(sql, parameters)
        def close(self):
            self.connection.close()
    monkeypatch.setattr(ss.sqlite3, "connect", NoOctetLength)
    monkeypatch.setattr(manager, "begin_write",
                        lambda: pytest.fail("missing inspection capability must not admit a write"))
    monkeypatch.setattr(provenance.szl_dsse, "sign_payload",
                        lambda *_args: pytest.fail("missing inspection capability must not sign"))
    with pytest.raises(provenance._LedgerUnavailable):
        dag.evidence_window(33)
    assert any("octet_length(" in q for q in queries)
    assert not any("SELECT sequence, digest, node_json, node_sha256" in q for q in queries)
    assert not any("CAST(" in q or "length(" in q.replace("octet_length(", "") for q in queries)
    assert path.read_bytes() == before
    assert set(path.parent.iterdir()) == files
    # This missing inspection capability must not fence the store or alter the
    # full-history API, which does not require the metadata-only size function.
    assert dag.recent(33) == nodes[-33:]
    assert manager.role == ss.ROLE_WRITER
    assert manager.stores["khipu"].health == "OK"


def test_other_database_encoding_refuses_inspection_before_body_read_only(world, monkeypatch):
    manager, dag, path, nodes = world
    path.unlink()
    seed(path, nodes, utf16=True)
    before = path.read_bytes()
    queries, _connections = trace_reads(monkeypatch)
    with pytest.raises(ss.StorageBlocked, match="PROVENANCE_WINDOW_ENCODING_UNSUPPORTED"):
        manager.provenance_window("a11oy", 33, dag._validate_window)
    assert "PRAGMA encoding" in queries
    assert not any("FROM provenance_nodes" in q for q in queries)
    assert path.read_bytes() == before
    assert dag.recent(33) == nodes[-33:]
    assert manager.role == ss.ROLE_WRITER
    assert manager.stores["khipu"].health == "OK"


def test_managed_owner_to_http_inspection_and_corrupt_tail_refusal_are_passive(world, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from oro import evidence_api

    manager, dag, path, _nodes = world
    monkeypatch.setattr(manager, "provenance_nodes",
                        lambda *_args: pytest.fail("HTTP inspection must use the bounded owner API"))
    effects = []
    def refuse_effect(*_args, **_kwargs):
        effects.append("unexpected mutation")
        raise AssertionError("inspection attempted a mutation")
    monkeypatch.setattr(manager, "begin_write", refuse_effect)
    monkeypatch.setattr(dag, "append_signed", refuse_effect)
    monkeypatch.setattr(provenance.szl_dsse, "sign_payload", refuse_effect)
    monkeypatch.setattr(evidence_api, "_read_anatomy_snapshot", lambda: {
        "schema": "szl.anatomy.evidence/v6", "evidence_class": "MODELED",
        "mode": "READ_ONLY", "content_access": "SUMMARY_ONLY", "storage_writes": 0,
        "receipt_minted_on_get": False, "model_invoked": False, "gradient_training": False,
        "authority": {key: "NONE" for key in ("training", "promotion", "execution", "provider_write")},
        "audit": {"chain_ok": True, "receipts_checked": 0, "broken_receipts": 0, "proposed_demotions": 0},
        "overlay": {"nodes": 0, "reinforced_edges": 0},
    })
    app = FastAPI()
    app.state.szl_khipu_dag = dag
    evidence_api.register(app)
    before = path.read_bytes()
    files = set(path.parent.iterdir())
    with TestClient(app) as client:
        observed = client.get(evidence_api.API_PATH)
        assert observed.status_code == 200
        body = observed.json()
        assert body["status"] == "OBSERVED"
        assert body["sources"]["canonical_khipu"]["count"] == 32
        assert body["sources"]["canonical_khipu"]["read_method"] == "evidence_window"
        assert body["sources"]["canonical_khipu"]["history_validation"] == "NOT_PERFORMED"
        assert len(body["projection"]["nodes"]) == 32
        assert all(row["evidence"]["proof_status"] == "UNVERIFIED"
                   for row in body["projection"]["nodes"])
        assert "synthetic-body-must-not-leave" not in observed.text
        assert all(body[key] is False for key in (
            "execution_authority", "promotion_authority", "signing_authority", "receipt_minted_on_get"))
        assert path.read_bytes() == before
        assert set(path.parent.iterdir()) == files
        assert effects == []

        # Deliberate fixture damage between the two read-only requests.
        with closing(sqlite3.connect(path)) as db, db:
            db.execute("UPDATE provenance_nodes SET node_json='{}' WHERE sequence=39")
        damaged = path.read_bytes()
        refused = client.get(evidence_api.API_PATH)
        assert refused.status_code == 503
        body = refused.json()
        assert body["status"] == "UNAVAILABLE"
        assert body["sources"]["canonical_khipu"]["reason"] == "OWNER_READ_FAILED"
        assert body["projection"]["nodes"] == []
        assert "synthetic-body-must-not-leave" not in refused.text
        assert str(path) not in refused.text
        assert path.read_bytes() == damaged
        assert set(path.parent.iterdir()) == files
        assert effects == []
