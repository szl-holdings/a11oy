# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Current source projections cannot rewrite the existing adapter's history."""

import copy
import importlib.util
import json
from pathlib import Path

import pytest

import a11oy_brain_graph as brain
import szl_m1_corpus_manifest as m1
import szl_formula_training_admission as admission


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


@pytest.fixture
def current_inventory(proposal, monkeypatch):
    directory, _, _ = proposal
    corpus = m1.build()
    # The real producer's artifacts are in its standard relative paths when the
    # downstream admission writer runs. Keep its exact bytes in this fixture.
    for source, relative in ((m1.GRAPH_LEDGER, m1.CURRENT_BRAIN_LEDGER_PATH),
                             (m1.CORPUS_MANIFEST, m1.CURRENT_M1_MANIFEST_PATH)):
        destination = directory / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())
    repository = Path(__file__).resolve().parents[1]
    relative_paths = (
        "model_release/frontier-qualification/frontier-adoption.json",
        "model_release/frontier-qualification/frontier-adoption.schema.json",
        "model_release/szl-khipu-second-brain.json",
        m1.HISTORICAL_ADMISSION_PATH,
    )
    for relative in relative_paths:
        destination = directory / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((repository / relative).read_bytes())
    frontier = json.loads((directory / relative_paths[0]).read_text())
    schema = json.loads((directory / relative_paths[1]).read_text())
    ayllu = json.loads((directory / relative_paths[2]).read_text())
    # Start at the historical boundary even if the checked-in current proposal
    # has already been refreshed by an earlier producer invocation.
    policy = ayllu["brain_training_policy"]
    historical = (policy.get("historical_inventory_evidence") or {}).get("source_admission_manifest")
    if historical:
        policy["current_inventory_evidence"]["source_admission_manifest"] = historical
    policy.pop("historical_inventory_evidence", None)
    _write_json(directory / relative_paths[2], ayllu)
    manifest = {
        "schema_version": "szl.formula-training-admission-manifest.v1",
        "status": "COMPLETE_FAIL_CLOSED_HOLDOUT_ONLY",
        "claims_boundary": {"training_triggered": False, "model_promoted": False, "raw_node_text_emitted": False},
        "decision_summary": {"train_rows": 0, "raw_brain_rows_emitted": 0, "raw_brain_nodes_quarantined": 3},
        "source_snapshot": {
            "brain": {"raw_node_count": 3, "quarantined_node_count": 3, "training_text_rows_emitted": 0,
                      "reason_counts": {"LICENSE_UNKNOWN": 3, "REVISION_UNKNOWN": 3,
                                        "FRESHNESS_UNKNOWN": 2, "DUPLICATE_CANONICAL_KEY": 1,
                                        "PROVENANCE_UNKNOWN": 1}},
            "m1_alignment": {
                "aligned": True, "current_raw_nodes": 3, "brain_ledger_rows": 3,
                "training_state": "NOT_RUN",
                "admission": "CURRENT_INVENTORY_ONLY_ALL_ROWS_QUARANTINED",
                "raw_training_eligible_rows": 0, "current_only_node_ids": [], "m1_only_node_ids": [],
                "manifest_path": m1.CURRENT_M1_MANIFEST_PATH,
                "manifest_sha256": m1._sha_file(directory / m1.CURRENT_M1_MANIFEST_PATH),
                "brain_ledger_path": m1.CURRENT_BRAIN_LEDGER_PATH,
                "brain_ledger_sha256": corpus["ledgers"]["brain_nodes"]["sha256"],
            },
        },
    }
    manifest["manifest_receipt_sha256"] = m1._sha(m1._canonical(manifest))
    artifacts = {"crosswalk": {}, "tranche_rows": [], "manifest": manifest,
                 "receipt": {"artifact_receipt_sha256": "fixture-receipt"}}
    monkeypatch.setattr(admission, "build_artifacts", lambda root: artifacts)
    return directory, artifacts, frontier, schema, ayllu


def test_admission_writer_refreshes_current_inventory_after_final_bytes_and_preserves_history(current_inventory):
    from jsonschema import Draft202012Validator

    directory, artifacts, old_frontier, old_schema, old_ayllu = current_inventory
    history_bytes = (directory / m1.HISTORICAL_ADMISSION_PATH).read_bytes()
    repository = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location(
        "frontier_refresh_guard", repository / "model_release/frontier-qualification/frontier_admission_guard.py")
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)
    frontier_path = directory / "model_release/frontier-qualification/frontier-adoption.json"
    with pytest.raises(guard.FrontierAdmissionError, match="Brain node observation changed"):
        guard.load_registry(frontier_path)

    admission.write_artifacts(directory)
    assert admission.verify_committed(directory)["ok"] is True
    frontier = guard.load_registry(frontier_path)
    schema = json.loads((directory / "model_release/frontier-qualification/frontier-adoption.schema.json").read_text())
    ayllu = json.loads((directory / "model_release/szl-khipu-second-brain.json").read_text())
    Draft202012Validator(schema).validate(frontier)
    assert frontier["as_of"] == old_frontier["as_of"]
    for key in ("raw_nodes_observed", "raw_nodes_available_to_retrieval_and_evaluation"):
        assert frontier["brain_model_truth"][key] == 3
        assert schema["$defs"]["brainTruth"]["properties"][key] == {"const": 3}
        frontier["brain_model_truth"][key] = old_frontier["brain_model_truth"][key]
        schema["$defs"]["brainTruth"]["properties"][key] = old_schema["$defs"]["brainTruth"]["properties"][key]
    assert frontier["brain_model_truth"]["raw_observation_scope"] == m1.CURRENT_INVENTORY_SCOPE
    for document in (frontier, old_frontier):
        document["brain_model_truth"].pop("raw_observation_scope", None)
    for document in (schema, old_schema):
        document["$defs"]["brainTruth"]["properties"].pop("raw_observation_scope", None)
        document["$defs"]["brainTruth"]["required"] = [
            key for key in document["$defs"]["brainTruth"]["required"] if key != "raw_observation_scope"]
    assert frontier == old_frontier
    assert schema == old_schema

    policy = ayllu["brain_training_policy"]
    old_policy = old_ayllu["brain_training_policy"]
    assert policy["raw_nodes_observed"] == 3
    assert policy["raw_nodes_admitted_to_gradients"] == 0
    assert policy["current_inventory_obligations"] == {
        "license_or_rights_unknown": 3, "author_or_rightsholder_permission_unknown": 3,
        "privacy_or_pii_clearance_unknown": 3, "allowlisted_review_unknown": 3,
        "immutable_source_revision_unknown": 3, "freshness_unknown": 2,
        "duplicate_candidates": 1, "provenance_unknown": 1,
    }
    assert policy["historical_inventory_evidence"]["source_admission_manifest"] == (
        old_policy["current_inventory_evidence"]["source_admission_manifest"])
    assert (directory / m1.HISTORICAL_ADMISSION_PATH).read_bytes() == history_bytes
    for key, relative in (("source_admission_manifest", m1.CURRENT_ADMISSION_PATH),
                          ("m1_brain_ingest_ledger", m1.CURRENT_BRAIN_LEDGER_PATH),
                          ("m1_corpus_manifest", m1.CURRENT_M1_MANIFEST_PATH)):
        entry = policy["current_inventory_evidence"][key]
        assert entry["path"] == relative
        assert entry["file_sha256"] == m1._sha_file(directory / relative)
    assert policy["current_inventory_evidence"]["m1_brain_ingest_ledger"]["rows"] == 3
    assert (directory / m1.CURRENT_ADMISSION_PATH).read_bytes() == admission._json_bytes(artifacts["manifest"])
    for document in (ayllu, old_ayllu):
        for key in ("raw_nodes_observed", "current_inventory_observation_scope", "current_inventory_obligations",
                    "current_inventory_evidence", "historical_inventory_evidence"):
            document["brain_training_policy"].pop(key, None)
    assert ayllu == old_ayllu
    before = {path.relative_to(directory): path.read_bytes() for path in directory.rglob("*") if path.is_file()}
    admission.write_artifacts(directory)
    assert {path.relative_to(directory): path.read_bytes() for path in directory.rglob("*") if path.is_file()} == before
    assert admission.verify_committed(directory)["ok"] is True


@pytest.mark.parametrize("mutation,expected", [
    ("path", "CURRENT_INVENTORY_EVIDENCE_PATH_MISMATCH"),
    ("historical", "CURRENT_INVENTORY_HISTORICAL_SOURCE_BINDING_INVALID"),
    ("schema", "CURRENT_INVENTORY_EXACT_SCHEMA_BOUNDARY_CHANGED"),
    ("authority", "CURRENT_INVENTORY_AUTHORITY_BOUNDARY_CHANGED"),
    ("receipt", "CURRENT_INVENTORY_ADMISSION_RECEIPT_INVALID"),
])
def test_current_inventory_preflight_refuses_before_any_admission_or_policy_write(current_inventory, mutation, expected):
    directory, artifacts, _, _, _ = current_inventory
    policy_path = directory / "model_release/szl-khipu-second-brain.json"
    document = json.loads(policy_path.read_text())
    if mutation == "path":
        document["brain_training_policy"]["current_inventory_evidence"]["m1_brain_ingest_ledger"]["path"] = "../outside.jsonl"
        _write_json(policy_path, document)
    elif mutation == "authority":
        document["brain_training_policy"]["raw_nodes_admitted_to_gradients"] = 1
        _write_json(policy_path, document)
    elif mutation == "historical":
        (directory / m1.HISTORICAL_ADMISSION_PATH).write_text("tampered historical source")
    elif mutation == "schema":
        path = directory / "model_release/frontier-qualification/frontier-adoption.schema.json"
        schema = json.loads(path.read_text())
        schema["$defs"]["brainTruth"]["properties"]["raw_nodes_observed"] = {"type": "integer"}
        _write_json(path, schema)
    else:
        artifacts["manifest"]["manifest_receipt_sha256"] = "0" * 64
    before = {path.relative_to(directory): path.read_bytes() for path in directory.rglob("*") if path.is_file()}
    with pytest.raises(ValueError, match=expected):
        admission.write_artifacts(directory)
    assert {path.relative_to(directory): path.read_bytes() for path in directory.rglob("*") if path.is_file()} == before


@pytest.mark.parametrize("target", ["frontier", "schema", "policy"])
def test_verification_includes_current_inventory_outputs_and_rejects_stale_valid_targets(current_inventory, target):
    directory, _, _, _, _ = current_inventory
    admission.write_artifacts(directory)
    paths = {
        "frontier": "model_release/frontier-qualification/frontier-adoption.json",
        "schema": "model_release/frontier-qualification/frontier-adoption.schema.json",
        "policy": "model_release/szl-khipu-second-brain.json",
    }
    path = directory / paths[target]
    document = json.loads(path.read_text())
    if target == "frontier":
        document["brain_model_truth"]["raw_nodes_observed"] = 4
    elif target == "schema":
        document["$defs"]["brainTruth"]["properties"]["raw_nodes_observed"]["const"] = 4
    else:
        document["brain_training_policy"]["current_inventory_evidence"]["m1_corpus_manifest"]["file_sha256"] = "0" * 64
    _write_json(path, document)
    result = admission.verify_committed(directory)
    assert result["ok"] is False
    assert result["mismatches"] == [paths[target]]
    admission.write_artifacts(directory)
    assert admission.verify_committed(directory)["ok"] is True


@pytest.mark.parametrize("mutation,expected", [
    ("boolean_gradient", "CURRENT_INVENTORY_AUTHORITY_BOUNDARY_CHANGED"),
    ("boolean_eligible", "CURRENT_INVENTORY_ADMISSION_ALIGNMENT_INVALID"),
    ("trained_corpus", "CURRENT_INVENTORY_M1_BINDING_INVALID"),
    ("training_claim", "CURRENT_INVENTORY_ADMISSION_AUTHORITY_CONFLICT"),
    ("training_row", "CURRENT_INVENTORY_LEDGER_NOT_QUARANTINED"),
])
def test_rehashed_evidence_cannot_contradict_current_inventory_quarantine(current_inventory, mutation, expected):
    directory, artifacts, _, _, _ = current_inventory
    manifest = artifacts["manifest"]
    alignment = manifest["source_snapshot"]["m1_alignment"]
    if mutation == "boolean_gradient":
        path = directory / "model_release/szl-khipu-second-brain.json"
        document = json.loads(path.read_text())
        document["brain_training_policy"]["raw_nodes_admitted_to_gradients"] = False
        _write_json(path, document)
    elif mutation == "boolean_eligible":
        alignment["raw_training_eligible_rows"] = False
    elif mutation == "training_claim":
        manifest["claims_boundary"]["training_triggered"] = True
    else:
        path = directory / m1.CURRENT_M1_MANIFEST_PATH
        corpus = json.loads(path.read_text())
        if mutation == "trained_corpus":
            corpus["training_state"] = "TRAINED"
        else:
            ledger_path = directory / m1.CURRENT_BRAIN_LEDGER_PATH
            rows = [json.loads(line) for line in ledger_path.read_text().splitlines()]
            rows[0].update({"training_eligible": True, "training_decision": "TRAIN"})
            m1._write_jsonl(ledger_path, rows)
            corpus["ledgers"]["brain_nodes"].update({
                "sha256": m1._sha_file(ledger_path), "bytes": ledger_path.stat().st_size,
            })
            alignment["brain_ledger_sha256"] = m1._sha_file(ledger_path)
        _write_json(path, corpus)
        alignment["manifest_sha256"] = m1._sha_file(path)
    payload = {key: value for key, value in manifest.items() if key != "manifest_receipt_sha256"}
    manifest["manifest_receipt_sha256"] = m1._sha(m1._canonical(payload))
    before = {path.relative_to(directory): path.read_bytes() for path in directory.rglob("*") if path.is_file()}
    for operation in (admission.write_artifacts, admission.verify_committed):
        with pytest.raises(ValueError, match=expected):
            operation(directory)
        assert {path.relative_to(directory): path.read_bytes() for path in directory.rglob("*") if path.is_file()} == before
