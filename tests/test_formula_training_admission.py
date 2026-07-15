"""Fail-closed guards for the formula training-data admission tranche."""

import json
import pathlib

import szl_formula_training_admission as admission


ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_committed_artifacts_rebuild_byte_for_byte():
    result = admission.verify_committed(ROOT)
    assert result["ok"] is True
    assert result["mismatches"] == []
    assert len(result["manifest_receipt_sha256"]) == 64
    assert len(result["artifact_receipt_sha256"]) == 64


def test_current_brain_and_m1_are_aligned_and_raw_rows_remain_quarantined():
    artifacts = admission.build_artifacts(ROOT)
    source = artifacts["manifest"]["source_snapshot"]
    assert source["brain"]["raw_node_count"] == 9464
    assert source["brain"]["quarantined_node_count"] == 9464
    assert source["brain"]["training_text_rows_emitted"] == 0
    assert source["m1_alignment"]["brain_ledger_rows"] == 9464
    assert source["m1_alignment"]["aligned"] is True
    assert source["m1_alignment"]["current_only_node_ids"] == []
    assert source["m1_alignment"]["m1_only_node_ids"] == []
    assert source["m1_alignment"]["raw_training_eligible_rows"] == 0


def test_crosswalk_scopes_colliding_ids_and_covers_every_status():
    crosswalk = admission.build_artifacts(ROOT)["crosswalk"]
    summary = crosswalk["summary"]
    assert summary["record_count"] == 146
    assert summary["namespace_counts"] == {
        admission.PROOF_NAMESPACE: 23,
        admission.RUNTIME_NAMESPACE: 23,
        admission.THESIS_NAMESPACE: 100,
    }
    assert summary["resolved_status_counts"] == {
        "KERNEL_ACCEPTED": 2,
        "CONDITIONAL": 28,
        "OPEN": 115,
        "REFUTED": 1,
    }
    assert summary["executable_records"] == 23
    assert summary["training_eligible_records"] == 0
    assert summary["same_id_cross_namespace_collisions"] == 23
    assert crosswalk["namespace_policy"]["proof_transfer_requires_explicit_semantic_binding"]
    runtime = [
        row for row in crosswalk["records"]
        if row["formula_namespace"] == admission.RUNTIME_NAMESPACE
    ]
    assert all(row["executable"] for row in runtime)
    assert all(row["proof_transfer_allowed"] is False for row in runtime)
    assert all(row["semantic_relation"] == "ID_COLLISION_DIFFERENT_STATEMENT" for row in runtime)


def test_status_boundaries_do_not_inflate_proofs():
    records = {
        row["record_id"]: row
        for row in admission.build_artifacts(ROOT)["crosswalk"]["records"]
    }
    assert records[f"{admission.RUNTIME_NAMESPACE}:F23"]["resolved_status"] == "OPEN"
    proof_f23 = records[f"{admission.PROOF_NAMESPACE}:F23"]
    assert proof_f23["resolved_status"] == "REFUTED"
    assert proof_f23["conditional_variant"] == {
        "lean_ref": "lambda_unique_of_factors",
        "status": "CONDITIONAL",
        "unconditional_counterexample": "maxAgg_ne_Lambda",
    }
    assert records[f"{admission.PROOF_NAMESPACE}:F11"]["resolved_status"] == "KERNEL_ACCEPTED"
    assert records[f"{admission.PROOF_NAMESPACE}:F18"]["resolved_status"] == "KERNEL_ACCEPTED"
    unresolved_locked = {
        "F1", "F4", "F7", "F12", "F19", "F22"
    }
    assert all(
        records[f"{admission.PROOF_NAMESPACE}:{formula_id}"]["resolved_status"]
        == "CONDITIONAL"
        for formula_id in unresolved_locked
    )
    assert records[f"{admission.PROOF_NAMESPACE}:F14"]["resolved_status"] == "CONDITIONAL"


def test_tranche_is_holdout_only_and_contains_no_raw_brain_text():
    artifacts = admission.build_artifacts(ROOT)
    rows = artifacts["tranche_rows"]
    summary = artifacts["manifest"]["decision_summary"]
    assert len(rows) == 148
    assert summary["train_rows"] == 0
    assert summary["holdout_rows"] == 148
    assert summary["raw_brain_nodes_quarantined"] == 9464
    assert summary["raw_brain_rows_emitted"] == 0
    assert all(row["split"] == "HOLDOUT" for row in rows)
    assert all(row["training_eligible"] is False for row in rows)
    encoded = b"".join(admission._canonical_bytes(row) for row in rows)
    assert b"canonical_text" not in encoded
    assert b"brain_node_text" not in encoded


def test_szl_lake_and_query_context_remain_evaluation_only():
    artifacts = admission.build_artifacts(ROOT)
    lake_rows = [
        row for row in artifacts["tranche_rows"]
        if row["record_kind"] == "SZL_LAKE_EVIDENCE"
    ]
    assert len(lake_rows) == 2
    assert {row["evidence_status"] for row in lake_rows} == {"NOT_EVALUATED"}
    assert {row["admission_decision"] for row in lake_rows} == {
        "HOLDOUT_EVIDENCE_ONLY"
    }
    workflow = artifacts["manifest"]["workflow"]["stages"]
    query = next(stage for stage in workflow if stage["stage"] == "QUERY_READY_CONTEXT")
    assert query["document_count"] == 5
    assert query["training_eligible"] is False
    assert query["latency"] == {"status": "NOT_EVALUATED", "milliseconds": None}


def test_receipts_cover_exact_artifact_bytes():
    artifacts = admission.build_artifacts(ROOT)
    crosswalk = dict(artifacts["crosswalk"])
    crosswalk_receipt = crosswalk.pop("crosswalk_receipt_sha256")
    assert admission._sha_value(crosswalk) == crosswalk_receipt
    manifest = dict(artifacts["manifest"])
    manifest_receipt = manifest.pop("manifest_receipt_sha256")
    assert admission._sha_value(manifest) == manifest_receipt
    receipt = dict(artifacts["receipt"])
    receipt_sha = receipt.pop("artifact_receipt_sha256")
    assert admission._sha_value(receipt) == receipt_sha
    committed = json.loads((ROOT / admission.RECEIPT).read_text(encoding="utf-8"))
    assert committed["signature_status"] == "UNSIGNED_CONTENT_RECEIPT"
    assert committed["training_triggered"] is False
