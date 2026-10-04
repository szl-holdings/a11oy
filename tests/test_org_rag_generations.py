"""Atomic-generation and retrieval-only Brain-handle regression tests."""
from __future__ import annotations

import json
import hashlib
import threading
from pathlib import Path

import a11oy_org_rag as rag


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
