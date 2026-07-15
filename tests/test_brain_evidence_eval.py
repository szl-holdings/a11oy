"""Content-addressed Brain evidence-admission pilot guards."""

import json
import pathlib

import pytest

import szl_brain_evidence_eval as evidence


ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_committed_artifacts_rebuild_byte_for_byte():
    result = evidence.verify_committed(ROOT)
    assert result["ok"] is True
    assert result["mismatches"] == []
    assert len(result["manifest_receipt_sha256"]) == 64


def test_canonical_index_excludes_every_raw_node_and_all_labels():
    index = evidence.build_canonical_index(ROOT)
    assert index["canonical_rows_observed"] == 8
    assert index["unique_document_count"] == 5
    assert index["raw_graph"]["observed_node_count"] >= 9_000
    assert index["raw_graph"]["admitted_to_index"] == 0
    assert index["raw_graph"]["excluded_from_index"] == index["raw_graph"]["observed_node_count"]
    encoded = json.dumps(index, sort_keys=True)
    for forbidden in ("query_id", "expected_action", "relevant_document_ids",
                      "target_relevance", "example_type"):
        assert forbidden not in encoded
    assert index["admission_boundary"]["evaluation_labels_present"] is False
    assert all(document["training_eligible"] is False for document in index["documents"])
    assert all(document["proof_credit"] == 0 for document in index["documents"])
    assert all(document["trust_uplift_eligible"] is False for document in index["documents"])


def test_result_receipts_and_honesty_boundaries_are_valid():
    artifacts = evidence.build_artifacts(ROOT)
    index = dict(artifacts["index"])
    index_receipt = index.pop("index_receipt_sha256")
    assert evidence._sha(index) == index_receipt
    results = dict(artifacts["results"])
    results_receipt = results.pop("results_receipt_sha256")
    assert evidence._sha(results) == results_receipt
    manifest = dict(artifacts["manifest"])
    manifest_receipt = manifest.pop("manifest_receipt_sha256")
    assert evidence._sha(manifest) == manifest_receipt
    boundary = artifacts["manifest"]["claims_boundary"]
    assert boundary == {
        "proof_credit": 0,
        "model_trust_delta": 0,
        "model_promotion_allowed": False,
        "training_triggered": False,
        "network_used": False,
        "doi_minted": False,
        "peer_reviewed": False,
    }


def test_preregistered_metrics_report_success_and_missing_freshness():
    metrics = evidence.build_artifacts(ROOT)["results"]["metrics"]
    assert metrics["query_count"] == 15
    assert metrics["answerable_query_count"] == 10
    assert metrics["unanswerable_query_count"] == 5
    assert metrics["recall_at_1"] == 1.0
    assert metrics["recall_at_3"] == 1.0
    assert metrics["unanswerable_abstention_accuracy"] == 1.0
    assert metrics["answerable_abstention_rate"] == 0.2
    assert metrics["overall_action_accuracy"] == pytest.approx(13 / 15)
    assert metrics["canonical_license_coverage"] == 1.0
    assert metrics["canonical_source_timestamp_coverage"] == 0.0
    assert 0.0 < metrics["raw_graph_source_timestamp_coverage"] < 0.01


def test_protocol_rejects_training_eligible_qrels(tmp_path):
    protocol_dir = tmp_path / evidence.OUTPUT_DIR
    protocol_dir.mkdir(parents=True)
    prereg = json.loads((ROOT / evidence.PREREGISTRATION).read_text(encoding="utf-8"))
    qrels = json.loads((ROOT / evidence.QRELS).read_text(encoding="utf-8"))
    qrels["training_eligible"] = True
    (protocol_dir / "preregistration.json").write_text(
        json.dumps(prereg), encoding="utf-8"
    )
    (protocol_dir / "qrels.json").write_text(json.dumps(qrels), encoding="utf-8")
    with pytest.raises(evidence.EvidenceEvaluationError,
                       match="EVALUATION_LABELS_MUST_NOT_BE_TRAINING_ELIGIBLE"):
        evidence._protocol(tmp_path)


def test_qrels_file_is_bound_but_never_embedded_in_index():
    artifacts = evidence.build_artifacts(ROOT)
    receipts = artifacts["manifest"]["artifact_receipts"]
    qrels_path = evidence.QRELS.as_posix()
    assert receipts[qrels_path] == evidence._bytes_sha((ROOT / evidence.QRELS).read_bytes())
    qrels = json.loads((ROOT / evidence.QRELS).read_text(encoding="utf-8"))
    assert qrels["training_eligible"] is False
    index_bytes = evidence._json_file_bytes(artifacts["index"])
    for query in qrels["queries"]:
        assert query["query"].encode("utf-8") not in index_bytes
