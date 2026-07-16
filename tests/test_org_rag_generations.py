"""Atomic-generation and retrieval-only Brain-handle regression tests."""
from __future__ import annotations

import json
from pathlib import Path

import a11oy_org_rag as rag


def _reset_runtime(monkeypatch, db_path: Path) -> None:
    monkeypatch.setattr(rag, "RAG_DB_PATH", str(db_path))
    monkeypatch.setattr(rag, "_GRAPH", rag.OrgGraph())
    monkeypatch.setattr(rag, "_BUILD_META", {"built": False})
    monkeypatch.setattr(rag, "_REHYDRATE_ATTEMPTED", False)
    monkeypatch.setattr(rag, "_maybe_embedder", lambda: None)


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


def test_m1_release_manifest_reports_all_9464_handles_without_copying_fixture(tmp_path):
    # This reads the versioned ledger once; the generation tests above stay tiny.
    verified = rag._verify_m1_ledger(rag._M1_LEDGER_DEFAULT)
    assert verified["manifest_verified"] is True
    assert verified["rows"] == 9464
    assert len(verified["sha256"]) == 64
