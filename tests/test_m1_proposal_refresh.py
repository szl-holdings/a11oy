# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Current source projections cannot rewrite the existing adapter's history."""

import copy
import json

import pytest

import a11oy_brain_graph as brain
import szl_m1_corpus_manifest as m1


def _write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


@pytest.fixture
def proposal(tmp_path, monkeypatch):
    for name in ("ROOT", "OUT_DIR"):
        monkeypatch.setattr(m1, name, tmp_path)
    for name, basename in (
        ("GRAPH_LEDGER", "brain-ingest-ledger.jsonl"),
        ("FORMULA_LEDGER", "formula-curriculum-ledger.jsonl"),
        ("CORPUS_MANIFEST", "corpus-ingestion-manifest.json"),
        ("EVALUATION_MANIFEST", "evaluation-manifest.json"),
    ):
        monkeypatch.setattr(m1, name, tmp_path / basename)
    candidate = {
        "candidate_id": "a11oy-evidence-1.5b-sft-lora",
        "release_state": "NOT_PROMOTED", "quality_claim": "NOT_ESTABLISHED",
        "base_model": {"revision": "immutable-base-revision"},
        "adapter": {"sha256": "a" * 64, "bytes": 18516456},
        "dataset": {"train_sha256": "b" * 64, "records": 167},
        "training_receipt": {"sha256": "c" * 64, "trained_at": "retained-training-date"},
        "promotion": {"decision": "BLOCKED", "human_approval": False},
        "external_mutations": {"model_pushed": False},
        "full_corpus_proposal": {
            "relation": "PROPOSAL_ONLY_NOT_USED_BY_EXISTING_ADAPTER",
            "training_state": "NOT_RUN", "manifest_path": m1.CORPUS_MANIFEST.name,
            "manifest_sha256": "old-corpus", "brain_raw_nodes": 1,
            "brain_distinct_artifacts": 1, "formula_records": 1,
        },
    }
    operational = {
        "candidate_id": candidate["candidate_id"],
        "release_state": "NOT_PROMOTED", "quality_claim": "NOT_ESTABLISHED",
        "provider": {"mode": "local-only", "expected_gpu": "RTX 5050"},
        "policy": {"production": False},
        "base_files": [{"sha256": "d" * 64}],
        "adapter_files": [{"sha256": "e" * 64}],
        "corpus_policy": {
            "training_relation": "PROPOSAL_ONLY_NOT_USED_BY_EXISTING_ADAPTER",
            "require_raw_brain_training_quarantine": True,
            "expected_raw_nodes": 1, "expected_distinct_artifacts": 1,
            "expected_formula_records": 1,
        },
        "evidence": {
            "candidate_manifest": {"path": "candidate-manifest.json", "sha256": "old", "bytes": 1},
            "corpus_ingestion_manifest": {"path": m1.CORPUS_MANIFEST.name, "sha256": "old", "bytes": 1},
            "brain_ingest_ledger": {"path": m1.GRAPH_LEDGER.name, "sha256": "old", "bytes": 1, "rows": 1},
            "formula_curriculum_ledger": {"path": m1.FORMULA_LEDGER.name, "sha256": "old", "bytes": 1, "rows": 1},
            "training_receipt": {"path": "training-receipt.json", "sha256": "f" * 64, "bytes": 13},
            "reload_receipt": {"path": "reload-receipt.json", "sha256": "0" * 64, "bytes": 17},
            "evaluation_manifest": {"path": m1.EVALUATION_MANIFEST.name, "sha256": "1" * 64, "bytes": 19},
        },
    }
    _write_json(tmp_path / "candidate-manifest.json", candidate)
    _write_json(tmp_path / "operational-manifest.json", operational)
    _write_json(m1.EVALUATION_MANIFEST, {"state": "INCOMPLETE", "trained_at": "retained-evaluation-date"})
    _write_json(tmp_path / "knowledge.json", {"formulas": [
        {"id": f"F{i}", "latex": f"historical fragment {i}", "proof_status": "PROVED"}
        for i in range(1, 101)
    ]})
    nodes = [
        {"id": "formula:F1", "formula_id": "F1", "kind": "formula", "layer": 2,
         "formula_namespace": m1.NUMERIC_NAMESPACE, "title": "Euler demonstration"},
        {"id": "formal-formula:F1", "formula_id": "F1", "kind": "formal_formula", "layer": 2,
         "formula_namespace": "lutar-lean.formal-f-id.v2", "title": "Replay-Hash Determinism"},
        {"id": "person:one", "kind": "person", "layer": -1, "title": "Attribution metadata"},
    ]
    monkeypatch.setattr(brain, "get_brain_graph", lambda **kwargs: {"nodes": nodes, "link_count": 0})
    return tmp_path, candidate, operational


def _immutable_candidate(document):
    result = copy.deepcopy(document)
    for key in ("manifest_sha256", "brain_raw_nodes", "brain_distinct_artifacts", "formula_records"):
        result["full_corpus_proposal"].pop(key)
    return result


def _immutable_operational(document):
    result = copy.deepcopy(document)
    for key in ("expected_raw_nodes", "expected_distinct_artifacts", "expected_formula_records"):
        result["corpus_policy"].pop(key)
    for key in ("candidate_manifest", "corpus_ingestion_manifest", "brain_ingest_ledger", "formula_curriculum_ledger"):
        result["evidence"][key].pop("sha256")
        result["evidence"][key].pop("bytes")
    for key in ("brain_ingest_ledger", "formula_curriculum_ledger"):
        result["evidence"][key].pop("rows")
    return result


def test_build_refreshes_exact_proposal_references_and_preserves_training_history(proposal):
    directory, old_candidate, old_operational = proposal
    evaluation_bytes = m1.EVALUATION_MANIFEST.read_bytes()
    manifest = m1.build()
    candidate = json.loads((directory / "candidate-manifest.json").read_text())
    operational = json.loads((directory / "operational-manifest.json").read_text())
    assert _immutable_candidate(candidate) == _immutable_candidate(old_candidate)
    assert _immutable_operational(operational) == _immutable_operational(old_operational)
    assert m1.EVALUATION_MANIFEST.read_bytes() == evaluation_bytes
    assert candidate["full_corpus_proposal"]["brain_raw_nodes"] == 3
    assert candidate["full_corpus_proposal"]["brain_distinct_artifacts"] == 2
    assert candidate["full_corpus_proposal"]["formula_records"] == 123
    assert candidate["full_corpus_proposal"]["manifest_sha256"] == m1._sha_file(m1.CORPUS_MANIFEST)
    assert operational["corpus_policy"]["expected_raw_nodes"] == 3
    assert operational["corpus_policy"]["expected_distinct_artifacts"] == 2
    assert operational["corpus_policy"]["expected_formula_records"] == 123
    for key in ("candidate_manifest", "corpus_ingestion_manifest", "brain_ingest_ledger", "formula_curriculum_ledger"):
        evidence = operational["evidence"][key]
        path = directory / evidence["path"]
        assert evidence["sha256"] == m1._sha_file(path)
        assert evidence["bytes"] == path.stat().st_size
    assert operational["evidence"]["brain_ingest_ledger"]["rows"] == 3
    assert operational["evidence"]["formula_curriculum_ledger"]["rows"] == 123
    assert manifest["coverage"]["training_eligible_nodes"] == 0
    assert manifest["coverage"]["formula_status"] == {
        "KERNEL_ACCEPTED": 0, "CONDITIONAL": 0, "OPEN": 123, "REFUTED": 0,
    }
    node_rows = [json.loads(line) for line in m1.GRAPH_LEDGER.read_text().splitlines()]
    person = next(row for row in node_rows if row["kind"] == "person")
    assert "formula_namespace" not in person and "formal_binding" not in person
    artifact_paths = [m1.GRAPH_LEDGER, m1.FORMULA_LEDGER, m1.CORPUS_MANIFEST,
                      directory / "candidate-manifest.json", directory / "operational-manifest.json"]
    before = {path: path.read_bytes() for path in artifact_paths}
    assert m1.build() == manifest
    assert {path: path.read_bytes() for path in artifact_paths} == before


@pytest.mark.parametrize("mutation,expected", [
    ("promoted", "M1_PROPOSAL_REFRESH_REQUIRES_UNPROMOTED_CANDIDATE"),
    ("trained", "M1_PROPOSAL_REFRESH_CANNOT_REBIND_TRAINED_DATA"),
    ("relation", "M1_PROPOSAL_REFRESH_CANNOT_REBIND_TRAINED_DATA"),
    ("path", "M1_PROPOSAL_EVIDENCE_PATH_MISMATCH"),
])
def test_build_refuses_to_rebind_trained_or_out_of_scope_artifacts(proposal, mutation, expected):
    directory, candidate, operational = proposal
    if mutation == "promoted":
        candidate["release_state"] = "PROMOTED"
    elif mutation == "trained":
        candidate["full_corpus_proposal"]["training_state"] = "TRAINED"
    elif mutation == "relation":
        operational["corpus_policy"]["training_relation"] = "USED_BY_EXISTING_ADAPTER"
    else:
        operational["evidence"]["formula_curriculum_ledger"]["path"] = "../frozen/formula-curriculum-ledger.jsonl"
    _write_json(directory / "candidate-manifest.json", candidate)
    _write_json(directory / "operational-manifest.json", operational)
    before = {path.name: path.read_bytes() for path in directory.iterdir()}
    with pytest.raises(ValueError, match=expected):
        m1.build()
    assert {path.name: path.read_bytes() for path in directory.iterdir()} == before
