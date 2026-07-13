"""Wave 22 Brain evidence-reranker, full-node ledger, feed, and Anatomy guards."""

import hashlib
import json
import pathlib
import types

import pytest

import szl_brain_reranker as rr


def _json_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def _write(path: pathlib.Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_json_bytes(value))


@pytest.fixture(scope="module")
def brain_doc():
    docs, error = rr._brain_docs("a11oy")
    assert error is None and docs
    return next(iter(docs.values()))


def _example(doc, example_id, example_type, entity_id, query):
    return {
        "example_id": example_id,
        "example_type": example_type,
        "target_relevance": rr.TARGETS[example_type],
        "query": query,
        "evidence_text": doc["text"],
        "entity_id": entity_id,
        "brain_node_id": doc["id"],
        "brain_node_sha256": rr._sha({"id": doc["id"], "text": doc["text"],
                                       "source": doc["source"]}),
        "brain_source_sha256": rr._sha_text(doc["source"]),
    }


def _canonical_tree(root: pathlib.Path, doc):
    assignments = {
        "szl_lake": [
            _example(doc, "lake-positive", "positive", "entity-lake-a",
                     "Which evidence directly supports the node?"),
            _example(doc, "lake-negative", "negative", "entity-lake-b",
                     "Which unrelated claim should be rejected?"),
        ],
        "lean_mathlib": [
            _example(doc, "lean-abstain", "abstention", "entity-lean-a",
                     "When must the reranker abstain?"),
        ],
        "formula": [
            _example(doc, "formula-refute", "refutation", "entity-formula-a",
                     "Which refuted candidate must not be admitted?"),
        ],
    }
    for source_type, examples in assignments.items():
        artifact_rel = pathlib.Path("artifacts") / f"{source_type}.json"
        artifact = root / artifact_rel
        _write(artifact, {"schema_version": rr.SOURCE_SCHEMA, "examples": examples})
        artifact_sha = hashlib.sha256(artifact.read_bytes()).hexdigest()
        manifest = {
            "schema_version": rr._corpus_admission.SCHEMA_VERSION,
            "source_type": source_type,
            "version": "fixture-v1",
            "entries": [{
                "id": f"fixture-{source_type}",
                "evidence_class": "EXPERIMENTAL",
                "source_path": artifact_rel.as_posix(),
                "artifact_sha256": artifact_sha,
                "sorry_count": 0,
            }],
        }
        _write(root / rr._corpus_admission.DEFAULT_MANIFESTS[source_type], manifest)
    return rr._canonical_context(root, {})


def test_missing_canonical_manifests_fail_closed_with_zero_rows(tmp_path):
    result = rr.build_dataset(repo_root=tmp_path, environ={}, ledger_path=tmp_path / "rows.jsonl")
    assert result["dataset_readiness"]["status"] == rr.BLOCKED
    assert result["rows"] == []
    assert result["dataset_sha256"] is None
    assert result["training_triggered"] is False
    assert result["model_readiness"]["status"] == rr.BLOCKED
    assert result["evaluation_readiness"]["status"] == rr.BLOCKED


def test_all_raw_nodes_receive_an_honest_decision(tmp_path):
    raw_nodes, graph_error = rr._graph_nodes("a11oy")
    assert graph_error is None and raw_nodes
    expected_count = len(raw_nodes)
    result = rr.build_inventory(repo_root=tmp_path, environ={})
    assert result["ok"] is True
    assert result["inventory"]["raw_node_count"] == expected_count
    assert result["inventory"]["decision_count"] == expected_count
    assert len(result["decisions"]) == expected_count
    assert result["inventory"]["quarantined_node_count"] == expected_count
    first = result["decisions"][0]
    for key in ("node_content_sha256", "source_identity", "source_url",
                "source_revision", "license", "retrieved_at", "canonical_node_id",
                "admission_decision", "reason_codes", "split_assignment",
                "anatomy_record_sha256"):
        assert key in first
    assert first["training_eligible"] is False


def test_grounded_rows_cover_all_example_types_and_never_leak_groups(tmp_path, brain_doc):
    _canonical_tree(tmp_path, brain_doc)
    result = rr.build_dataset(repo_root=tmp_path, environ={}, ledger_path=tmp_path / "rows.jsonl")
    assert result["dataset_readiness"] == {"status": rr.READY, "reasons": []}
    assert len(result["rows"]) == 4
    assert result["example_type_counts"] == {name: 1 for name in rr.EXAMPLE_TYPES}
    assert result["split_leakage_group_count"] == 0
    assert result["model_readiness"]["status"] == rr.BLOCKED
    assert result["evaluation_readiness"]["status"] == rr.BLOCKED
    for row in result["rows"]:
        assert row["evidence_text"] == brain_doc["text"]
        for key in ("source_manifest_sha256", "source_artifact_sha256",
                    "source_receipt_sha256", "brain_node_sha256",
                    "brain_source_sha256", "row_receipt_sha256"):
            assert rr._is_sha(row[key])


def test_local_append_revalidates_hashes_and_is_hash_chained(tmp_path, brain_doc):
    canonical = _canonical_tree(tmp_path, brain_doc)
    source = canonical["source_map"][("szl_lake", "fixture-szl_lake")]
    payload = _example(brain_doc, "local-positive", "positive", "entity-local-a",
                       "What locally reviewed evidence supports this node?")
    payload.update({
        "source_type": "szl_lake", "source_entry_id": "fixture-szl_lake",
        "source_manifest_sha256": source["manifest_sha256"],
        "source_artifact_sha256": source["artifact_sha256"],
    })
    ledger = tmp_path / "rows.jsonl"
    body, status = rr.append_validated_row(payload, repo_root=tmp_path, environ={},
                                           ledger_path=ledger)
    assert status == 201 and body["ok"] is True
    assert rr._is_sha(body["row"]["ledger_entry_sha256"])
    duplicate, duplicate_status = rr.append_validated_row(
        payload, repo_root=tmp_path, environ={}, ledger_path=ledger,
    )
    assert duplicate_status == 200 and duplicate["duplicate"] is True
    bad = dict(payload); bad["source_artifact_sha256"] = "0" * 64
    denied, denied_status = rr.append_validated_row(
        bad, repo_root=tmp_path, environ={}, ledger_path=ledger,
    )
    assert denied_status == 422 and "source_artifact_sha256_MISMATCH" in denied["reasons"]
    dataset = rr.build_dataset(repo_root=tmp_path, environ={}, ledger_path=ledger)
    assert dataset["ledger"]["chain_valid"] is True
    assert dataset["ledger"]["record_count"] == 1
    assert len(dataset["rows"]) == 5


def test_feed_is_kill_switched_bounded_and_receipted_on_write(tmp_path, brain_doc):
    raw_nodes, graph_error = rr._graph_nodes("a11oy")
    assert graph_error is None and raw_nodes
    _canonical_tree(tmp_path, brain_doc)
    disabled, disabled_status = rr.refresh_feed(
        repo_root=tmp_path, environ={}, feed_path=tmp_path / "feed.jsonl",
    )
    assert disabled_status == 503 and disabled["reason"] == "FEED_DISABLED_OR_KILLED"
    env = {"A11OY_BRAIN_FEED_ENABLED": "1", "A11OY_BRAIN_FEED_KILL_SWITCH": "0",
           "A11OY_RUNTIME_STATE_DIR": str(tmp_path / "runtime")}
    feed_path = tmp_path / "feed.jsonl"
    written, written_status = rr.refresh_feed(
        repo_root=tmp_path, environ=env, feed_path=feed_path,
    )
    assert written_status == 201 and written["ok"] is True
    receipt = written["receipt"]
    assert receipt["raw_node_count"] == len(raw_nodes)
    assert receipt["training_triggered"] is False
    assert rr._is_sha(receipt["receipt_sha256"])
    status = rr.feed_status(repo_root=tmp_path, environ=env, feed_path=feed_path)
    assert status["receipt_chain"]["chain_valid"] is True
    assert status["last_successful_receipt"] == receipt["receipt_sha256"]
    limited, limited_status = rr.refresh_feed(
        repo_root=tmp_path, environ=env, feed_path=feed_path,
    )
    assert limited_status == 429 and limited["reason"] == "REFRESH_RATE_LIMITED"
    anatomy, code = rr.anatomy_receipt(
        brain_doc["id"], repo_root=tmp_path, environ=env, feed_path=feed_path,
    )
    assert code == 200
    assert anatomy["receipt_sha256"] == receipt["receipt_sha256"]
    assert anatomy["receipt_anatomy"]["model_receipt_sha256"] == rr.UNKNOWN


def test_docker_and_frontend_wiring_present():
    root = pathlib.Path(__file__).resolve().parents[1]
    docker = (root / "Dockerfile").read_text(encoding="utf-8")
    serve = (root / "serve.py").read_text(encoding="utf-8")
    registry = (root / "static/3d/holographic.html").read_text(encoding="utf-8")
    backend_registry = (root / "szl3d_holographic.py").read_text(encoding="utf-8")
    anatomy = (root / "szl_anatomy_3d.py").read_text(encoding="utf-8")
    assert "COPY szl_braincorpus.py szl_brain_reranker.py ./" in docker
    assert "import szl_brain_reranker" in serve
    assert 'id: "brainreranker"' in registry
    assert '"id": "brainreranker"' in backend_registry
    assert "/body-3d-v6" in anatomy


def test_local_write_guard_rejects_public_host_behind_loopback_proxy():
    public = types.SimpleNamespace(
        client=types.SimpleNamespace(host="127.0.0.1"),
        url=types.SimpleNamespace(hostname="a-11-oy.com"),
    )
    local = types.SimpleNamespace(
        client=types.SimpleNamespace(host="127.0.0.1"),
        url=types.SimpleNamespace(hostname="localhost"),
    )
    assert rr._local_request(public) is False
    assert rr._local_request(local) is True


def test_routes_are_json_and_precede_catchalls():
    pytest.importorskip("starlette.testclient")
    from fastapi.testclient import TestClient
    import serve

    paths = [
        "/api/a11oy/v1/brain/reranker/info",
        "/api/a11oy/v1/brain/reranker/status",
        "/api/a11oy/v1/brainreranker/status",
        "/api/a11oy/v1/brain/reranker/inventory",
        "/api/a11oy/v1/brain/reranker/dataset",
        "/api/a11oy/v1/brain/reranker/feed",
    ]
    route_paths = [getattr(route, "path", "") for route in serve.app.router.routes]
    catchalls = [i for i, path in enumerate(route_paths)
                 if path in {"/{full_path:path}", "/api/a11oy/{path:path}"}]
    for path in paths:
        assert path in route_paths
        if catchalls: assert route_paths.index(path) < min(catchalls)
    with TestClient(serve.app) as client:
        info = client.get(paths[0]); assert info.status_code == 200
        surface = client.get(paths[2]); assert surface.status_code == 200
        assert surface.json()["status"] == rr.BLOCKED
        assert surface.json()["label"] == rr.UNAVAILABLE
        inventory = client.get(paths[3], params={"limit": 3}); assert inventory.status_code == 200
        assert inventory.headers["content-type"].startswith("application/json")
        assert inventory.json()["limit"] == 3
        status = client.get(paths[1]); assert status.status_code == 200
        assert status.json()["dataset"]["status"] == rr.BLOCKED
        v6 = client.get("/body-3d-v6", follow_redirects=False)
        assert v6.status_code == 307 and "brainreranker" in v6.headers["location"]
