"""Release-contract validation for the Khipu compound Second Brain."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

jsonschema = pytest.importorskip("jsonschema")


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "model_release" / "szl-khipu-second-brain.json"
SCHEMA_PATH = ROOT / "model_release" / "szl-khipu-second-brain.schema.json"
LIVE_RECEIPT_PATH = (
    ROOT / "attestations" / "forge-second-brain-live-2026-07-15.json"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_second_brain_manifest_validates_and_preserves_hard_boundaries() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.Draft202012Validator(schema).validate(manifest)

    policy = manifest["brain_training_policy"]
    assert policy["raw_nodes_admitted_to_gradients"] <= policy["raw_nodes_observed"]
    assert manifest["claims_boundary"]["index_is_model_weights"] is False
    assert manifest["claims_boundary"]["retrieval_is_training"] is False
    assert manifest["promotion"]["automatic"] is False
    assert manifest["promotion"]["requires_human_approval"] is True
    assert policy["admission_evidence_security"] == {
        "signature": "ED25519",
        "trust_model": "ALLOWLISTED_ISSUER_TOOL_KEY_TRIPLE",
        "content_binding": (
            "EXACT_CONTENT_SOURCE_REVISION_RIGHTS_AND_CONTAMINATION"
        ),
        "cross_run_isolation": "SIGNED_DETERMINISTIC_SPLIT_LEDGER",
        "self_attestation_allowed": False,
    }
    assert set(policy["required_admission_inputs"]) == {
        "protected_eval_content_sha256_list",
        "signed_evidence_trust_store",
        "signed_prior_split_ledger_descriptor",
    }


def test_inventory_evidence_is_content_addressed_and_present() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    inventory = manifest["brain_training_policy"]["current_inventory_evidence"]
    observed_rows = None
    for name, evidence in inventory.items():
        path = ROOT / evidence["path"]
        assert path.is_file(), f"missing {name}: {path}"
        assert _sha256(path) == evidence["file_sha256"]
        if "rows" in evidence:
            observed_rows = sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line)
            assert observed_rows == evidence["rows"]
    assert observed_rows == manifest["brain_training_policy"]["raw_nodes_observed"]


def test_turn_receipt_contract_binds_model_grounding_and_output() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    required = set(manifest["required_turn_receipts"])
    assert {
        "model_attestation_sha256",
        "evidence_set_sha256",
        "grounding_sha256",
        "turn_output_sha256",
    } <= required


def test_live_second_brain_receipt_is_content_addressed_and_privacy_safe() -> None:
    receipt = json.loads(LIVE_RECEIPT_PATH.read_text(encoding="utf-8"))
    assert _sha256(LIVE_RECEIPT_PATH) == (
        "0cfc363216624561f8faa080908fef4757db8267c40dafe07526b1cc502c9d8a"
    )
    assert receipt["verification_state"] == "PASS"
    assert receipt["second_brain"]["handle_plane"]["expected_count"] == 9464
    assert receipt["second_brain"]["handle_plane"]["state"] == "VERIFIED"
    assert receipt["second_brain"]["raw_brain_nodes_admitted_to_gradients"] == 0
    assert set(receipt["privacy"].values()) == {False}
    assert {turn["exact_served_model"] for turn in receipt["turns"]} == {
        "khipu:latest",
        "receiptagent:latest",
    }
