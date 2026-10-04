#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Atomic-generation and retrieval-only Brain-handle regression tests."""
from __future__ import annotations

import json
import hashlib
import sqlite3
import threading
from pathlib import Path

import a11oy_org_rag as rag
import pytest


def _reset_runtime(monkeypatch, db_path: Path) -> None:
    monkeypatch.setattr(rag, "RAG_DB_PATH", str(db_path))
    monkeypatch.setattr(rag, "_GRAPH", rag.OrgGraph())
    monkeypatch.setattr(rag, "_BUILD_META", {"built": False})
    monkeypatch.setattr(rag, "_REHYDRATE_ATTEMPTED", False)
    monkeypatch.setattr(rag, "_BUILD_STATE", {
        "phase": "idle", "started": None, "finished": None,
        "last_seed": None, "last_full": None, "error": None,
    })
    monkeypatch.setattr(rag, "_build_thread", None)
    monkeypatch.setattr(rag, "_maybe_embedder", lambda load=True: None)


def _write_ledger(path: Path, count: int = 3) -> Path:
    rows = []
    for index in range(count):
        rows.append({
            "node_id": f"author:researcher_{index}",
            "receipt_id": f"brain-node:sha256:{index:064x}",
            "canonical_text": (
                f"title: Researcher {index}\nkind: person\n"
                "evidence_label: HARVESTED\nsource: arxiv-author"
            ),
            "kind": "person",
            "provenance": {
                "source": "arxiv-author",
                "url": f"https://arxiv.org/a/researcher_{index}",
                "evidence_label": "HARVESTED",
            },
            "license": {"state": "UNKNOWN_ITEM_LEVEL_LICENSE"},
            "freshness": {"state": "UNKNOWN_NO_SOURCE_TIMESTAMP"},
            "safety_decision": "QUARANTINE_PERSON_METADATA",
            "training_decision": "QUARANTINE",
            # One source row deliberately says eligible. The retrieval plane must
            # preserve that source claim without acquiring training authority.
            "training_eligible": index == count - 1,
        })
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    return path


def _stage(conn, generation_id: str, title: str) -> rag.OrgGraph:
    graph = rag.OrgGraph()
    graph.add_node("szl-holdings/a11oy", "repo", repo="a11oy")
    rag._ingest_text(
        graph, conn, repo="a11oy", path="README.md", raw=title,
        source="test:fixture", category="app_code", embed_fn=None,
        generation_id=generation_id,
    )
    return graph


def _storage_fingerprint(directory: Path) -> dict:
    return {
        path.name: (hashlib.sha256(path.read_bytes()).hexdigest(),
                    path.stat().st_mtime_ns)
        for path in directory.iterdir() if path.is_file()
    }


def test_seed_reader_uses_canonical_runtime_alias_and_keeps_anonymous_fallback(monkeypatch):
    for name in rag._GH_ENV_KEYS:
        monkeypatch.delenv(name, raising=False)
    assert rag._gh_token() == ""
    monkeypatch.setenv("GITHUB_TOKEN", "test-local-reader")
    assert rag._gh_token() == "test-local-reader"
    monkeypatch.setenv("A11OY_GITHUB_PUBLIC_READ_TOKEN", "test-canonical-public-reader")
    assert rag._gh_token() == "test-canonical-public-reader"


def test_seed_repository_count_measures_indexed_sources_not_declared_categories(monkeypatch, tmp_path):
    _reset_runtime(monkeypatch, tmp_path / "seed.sqlite3")
    monkeypatch.setattr(rag, "SZL_CORPUS", {
        "one": {"label": "One", "seed": ["README.md"], "gh_repos": ["one-repo"]},
        "two": {"label": "Two", "seed": ["POLICY.md"], "gh_repos": ["one-repo"]},
        "unavailable": {"label": "Unavailable", "seed": ["missing.md"], "gh_repos": ["missing-repo"]},
    })
    monkeypatch.setattr(rag, "_gh_raw", lambda repo, path, token:
                        f"Real fixture bytes for {path}" if repo == "one-repo" else None)
    monkeypatch.setattr(rag, "_resolve_m1_ledger", lambda: None)
    result = rag.build_seed_index()
    assert result["built"] is True
    assert result["repos"] == 1
    assert result["files"] == result["chunks"] == 2
    assert result["per_category"]["unavailable"] == {"files": 0, "chunks": 0}
    assert rag.status()["repos"] == 1


def test_brain_handles_are_searchable_but_never_training_authority(monkeypatch, tmp_path):
    _reset_runtime(monkeypatch, tmp_path / "rag.sqlite3")
    ledger = _write_ledger(tmp_path / "brain-ingest-ledger.jsonl")
    conn = rag._db()
    rag._init_schema(conn)
    generation_id = rag._begin_generation(conn, "test")
    graph = _stage(conn, generation_id, "atomic corpus alpha")
    handle_stats = rag._ingest_brain_handles(conn, generation_id, ledger)
    meta = {"built": True, "mode": "test", "ts": 1.0, "repos": 1, "chunks": 1,
            "brain_handle_plane": handle_stats}
    rag._persist_runtime_state(conn, graph, meta, generation_id)
    conn.close()

    assert handle_stats["count"] == 3
    assert handle_stats["source_training_eligible_rows"] == 1
    assert handle_stats["gradient_authority_rows"] == 0
    result = rag.query("Researcher 1", k=3)
    handles = [row for row in result["chunks"] if row["retrieval_plane"] == "brain_handle"]
    assert handles
    assert handles[0]["evidence"]["source_url"].startswith("https://arxiv.org/")
    assert handles[0]["evidence"]["receipt_id"].startswith("brain-node:sha256:")
    assert handles[0]["evidence"]["safety_decision"] == "QUARANTINE_PERSON_METADATA"
    assert handles[0]["evidence"]["gradient_authority"] is False
    assert result["brain_handle_count"] == 3
    assert result["training_authority_rows"] == 0


def test_interrupted_staging_generation_never_replaces_active_snapshot(monkeypatch, tmp_path):
    _reset_runtime(monkeypatch, tmp_path / "rag.sqlite3")
    conn = rag._db()
    rag._init_schema(conn)
    first = rag._begin_generation(conn, "first")
    first_graph = _stage(conn, first, "stable alpha evidence")
    rag._persist_runtime_state(
        conn, first_graph,
        {"built": True, "mode": "first", "ts": 1.0, "repos": 1, "chunks": 1},
        first,
    )
    # Simulate a process crash: the next generation is partly written but never
    # sealed or swapped active.
    interrupted = rag._begin_generation(conn, "interrupted")
    _stage(conn, interrupted, "partial beta evidence")
    conn.commit()
    conn.close()

    stable = rag.query("stable alpha", k=2)
    partial = rag.query("partial beta", k=2)
    assert stable["generation_id"] == first
    assert stable["grounded_count"] == 1
    assert partial["generation_id"] == first
    assert partial["grounded_count"] == 0


def test_rehydrate_detects_tampering_and_requires_rebuild(monkeypatch, tmp_path):
    db_path = tmp_path / "rag.sqlite3"
    _reset_runtime(monkeypatch, db_path)
    conn = rag._db()
    rag._init_schema(conn)
    generation_id = rag._begin_generation(conn, "sealed")
    graph = _stage(conn, generation_id, "sealed evidence")
    rag._persist_runtime_state(
        conn, graph,
        {"built": True, "mode": "sealed", "ts": 1.0, "repos": 1, "chunks": 1},
        generation_id,
    )
    conn.execute(
        "UPDATE org_chunks_gen SET body='tampered' WHERE generation_id=?",
        (generation_id,),
    )
    conn.commit()
    conn.close()

    _reset_runtime(monkeypatch, db_path)
    assert rag._rehydrate_runtime_state() is False
    state = rag.status()
    assert state["built"] is False
    assert state["integrity_state"] == "FAILED_CLOSED"
    assert state["rehydration_state"] == "INTEGRITY_MISMATCH_REBUILD_REQUIRED"
    refused = rag.query("sealed", k=1)
    assert refused["ok"] is False
    assert refused["i_dont_know"] is True


def test_rehydrate_and_query_use_readonly_published_generation(monkeypatch, tmp_path):
    db_path = tmp_path / "rag.sqlite3"
    _reset_runtime(monkeypatch, db_path)
    conn = rag._db()
    rag._init_schema(conn)
    generation_id = rag._begin_generation(conn, "sealed")
    graph = _stage(conn, generation_id, "side effect free retrieval evidence")
    rag._persist_runtime_state(
        conn, graph,
        {"built": True, "mode": "sealed", "ts": 1.0, "repos": 1, "chunks": 1},
        generation_id,
    )
    conn.close()
    before_hash = hashlib.sha256(db_path.read_bytes()).hexdigest()
    before_mtime = db_path.stat().st_mtime_ns
    before_files = _storage_fingerprint(tmp_path)
    assert set(before_files) == {"rag.sqlite3"}

    _reset_runtime(monkeypatch, db_path)
    monkeypatch.setattr(rag, "_db", lambda: (_ for _ in ()).throw(
        AssertionError("writer connection used by read")))
    monkeypatch.setattr(rag, "_init_schema", lambda _conn: (_ for _ in ()).throw(
        AssertionError("schema initialization used by read")))
    embedder_calls: list[bool] = []
    monkeypatch.setattr(rag, "_maybe_embedder",
                        lambda load=True: embedder_calls.append(load) or None)

    assert rag.status()["generation_id"] == generation_id
    result = rag.query("side effect free retrieval", k=2)
    assert result["ok"] is True
    assert embedder_calls == [False]
    assert hashlib.sha256(db_path.read_bytes()).hexdigest() == before_hash
    assert db_path.stat().st_mtime_ns == before_mtime
    assert _storage_fingerprint(tmp_path) == before_files


@pytest.mark.parametrize("existing_sidecars", [False, True])
def test_legacy_wal_reads_are_unavailable_without_creating_or_changing_files(
    monkeypatch, tmp_path, existing_sidecars,
):
    db_path = tmp_path / "legacy.sqlite3"
    _reset_runtime(monkeypatch, db_path)
    writer = rag._db()
    rag._init_schema(writer)
    generation_id = rag._begin_generation(writer, "legacy")
    graph = _stage(writer, generation_id, "published legacy evidence")
    rag._persist_runtime_state(
        writer, graph,
        {"built": True, "mode": "legacy", "ts": 1.0, "repos": 1, "chunks": 1},
        generation_id,
    )
    writer.close()

    legacy = sqlite3.connect(db_path)
    assert legacy.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
    legacy.execute("SELECT * FROM org_active_generation").fetchall()
    if not existing_sidecars:
        legacy.close()
    before = _storage_fingerprint(tmp_path)
    expected = {"legacy.sqlite3"}
    if existing_sidecars:
        expected |= {"legacy.sqlite3-wal", "legacy.sqlite3-shm"}
    assert set(before) == expected

    try:
        _reset_runtime(monkeypatch, db_path)
        state = rag.status()
        assert state["built"] is False
        assert state["integrity_state"] == "UNAVAILABLE"
        assert state["storage_state"] == "LEGACY_WAL_REQUIRES_LIFECYCLE_WRITE"
        result = rag.query("published legacy", k=1)
        assert result["ok"] is False
        assert result["storage_state"] == "LEGACY_WAL_REQUIRES_LIFECYCLE_WRITE"
        assert rag.chunk_count() == rag.dense_vector_count() == 0
        assert rag.next_unembedded_chunks() == []
        assert _storage_fingerprint(tmp_path) == before
    finally:
        if existing_sidecars:
            legacy.close()


def test_lifecycle_seed_migrates_legacy_wal_before_readonly_retrieval(monkeypatch, tmp_path):
    db_path = tmp_path / "legacy.sqlite3"
    legacy = sqlite3.connect(db_path)
    legacy.execute("PRAGMA journal_mode=WAL")
    legacy.execute("CREATE TABLE legacy_marker(value TEXT)")
    legacy.commit()
    legacy.close()
    _reset_runtime(monkeypatch, db_path)
    monkeypatch.setattr(rag, "SZL_CORPUS", {
        "one": {"label": "One", "seed": ["README.md"], "gh_repos": ["a11oy"]},
    })
    monkeypatch.setattr(rag, "_gh_raw", lambda *_args: "migrated lifecycle evidence")
    monkeypatch.setattr(rag, "_resolve_m1_ledger", lambda: None)
    receipts = []

    assert rag.status()["storage_state"] == "LEGACY_WAL_REQUIRES_LIFECYCLE_WRITE"
    started = rag.start_seed_bootstrap(
        emit_receipt=lambda kind, payload: receipts.append((kind, payload)) or {},
    )
    assert started["phase"] == "seeding"
    rag._build_thread.join(timeout=5)
    assert not rag._build_thread.is_alive()
    assert rag.build_state()["phase"] == "seed"
    assert len(receipts) == 1
    assert receipts[0][0] == "org_rag.index.seed"
    assert db_path.read_bytes()[18:20] == b"\x01\x01"
    before = _storage_fingerprint(tmp_path)
    assert set(before) == {"legacy.sqlite3"}
    assert rag.query("migrated lifecycle", k=1)["grounded_count"] == 1
    assert _storage_fingerprint(tmp_path) == before


def test_rollback_reader_snapshot_stays_coherent_during_successor_publication(
    monkeypatch, tmp_path,
):
    _reset_runtime(monkeypatch, tmp_path / "rag.sqlite3")
    writer = rag._db()
    rag._init_schema(writer)
    first = rag._begin_generation(writer, "first")
    first_graph = _stage(writer, first, "original snapshot evidence")
    rag._persist_runtime_state(
        writer, first_graph,
        {"built": True, "mode": "first", "ts": 1.0, "repos": 1, "chunks": 1},
        first,
    )
    successor = rag._begin_generation(writer, "successor")
    successor_graph = _stage(writer, successor, "successor published evidence")
    writer.commit()
    assert writer.execute("PRAGMA synchronous").fetchone()[0] == 2
    assert writer.execute("PRAGMA busy_timeout").fetchone()[0] == 15_000
    writer.close()

    reader = rag._db_readonly()
    reader.execute("BEGIN")
    assert rag._active_generation(reader) == first
    assert reader.execute("PRAGMA busy_timeout").fetchone()[0] == 15_000
    publishing = threading.Event()
    completed = threading.Event()
    errors = []
    original_digest = rag._generation_digest

    def observe_digest(connection, generation_id, graph_data):
        result = original_digest(connection, generation_id, graph_data)
        publishing.set()
        return result

    monkeypatch.setattr(rag, "_generation_digest", observe_digest)

    def publish():
        connection = None
        try:
            connection = rag._db()
            rag._persist_runtime_state(
                connection, successor_graph,
                {"built": True, "mode": "successor", "ts": 2.0, "repos": 1, "chunks": 1},
                successor,
            )
        except Exception as exc:
            errors.append(exc)
        finally:
            if connection is not None:
                connection.close()
            completed.set()

    thread = threading.Thread(target=publish)
    thread.start()
    try:
        assert publishing.wait(timeout=5)
        assert not completed.is_set()
        assert rag._active_generation(reader) == first
        assert reader.execute(
            "SELECT body FROM org_chunks_gen WHERE generation_id=?", (first,),
        ).fetchone()[0] == "original snapshot evidence"
    finally:
        reader.close()
        thread.join(timeout=5)
    assert not thread.is_alive()
    assert completed.is_set()
    assert errors == []
    result = rag.query("successor published", k=1)
    assert result["generation_id"] == successor
    assert result["grounded_count"] == 1


def test_seed_bootstrap_is_single_flight_and_receipts_once(monkeypatch, tmp_path):
    _reset_runtime(monkeypatch, tmp_path / "missing.sqlite3")
    entered = threading.Event()
    release = threading.Event()
    calls: list[str] = []
    receipts: list[tuple[str, dict]] = []
    monkeypatch.setattr(rag, "status", lambda: {"built": False})

    def fake_seed(emit_receipt=None):
        calls.append("seed")
        entered.set()
        assert release.wait(timeout=5)
        receipt = emit_receipt("org_rag.index.seed", {"built": True})
        return {"ok": True, "generation_id": "gen-test",
                "khipu_hash": receipt["hash"]}

    def emit(kind, body):
        receipts.append((kind, body))
        return {"hash": "receipt-test"}

    monkeypatch.setattr(rag, "build_seed_index", fake_seed)
    first = rag.start_seed_bootstrap(emit_receipt=emit)
    assert entered.wait(timeout=5)
    second = rag.start_seed_bootstrap(emit_receipt=emit)
    assert first["phase"] == second["phase"] == "seeding"
    assert calls == ["seed"]
    release.set()
    assert rag._build_thread is not None
    rag._build_thread.join(timeout=5)
    assert not rag._build_thread.is_alive()
    assert receipts == [("org_rag.index.seed", {"built": True})]
    assert rag.build_state()["phase"] == "seed"


def test_m1_release_manifest_reports_all_9465_handles_without_copying_fixture(tmp_path):
    # This reads the versioned ledger once; the generation tests above stay tiny.
    verified = rag._verify_m1_ledger(rag._M1_LEDGER_DEFAULT)
    assert verified["manifest_verified"] is True
    assert verified["rows"] == 9465
    assert len(verified["sha256"]) == 64
