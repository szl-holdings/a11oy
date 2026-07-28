"""Network-free truth lock for ReceiptAgent artifact reconciliation."""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
PROGRAM = ROOT / "model_release" / "receipt-agent"
RECONCILIATION = PROGRAM / "reconciliation"
SCRIPT = RECONCILIATION / "reconcile_artifact_binding.py"
FIXTURE = RECONCILIATION / "observed-hf-tree-fixture.v1.json"
ARTIFACT = RECONCILIATION / "receipt-agent-artifact-reconciliation.v1.json"
SCHEMA = RECONCILIATION / "artifact-reconciliation.schema.json"
QUALIFICATION = (
    PROGRAM / "qualification" / "fa73dc1-cpu-qualification-receipt.json"
)

SPEC = importlib.util.spec_from_file_location("receipt_agent_reconciliation", SCRIPT)
assert SPEC and SPEC.loader
RECON = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RECON)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_stored_reconciliation_regenerates_exactly_and_validates_schema():
    fixture = load(FIXTURE)
    qualification = load(QUALIFICATION)
    stored = load(ARTIFACT)
    generated = RECON.reconcile(fixture, qualification)

    assert generated == stored
    Draft202012Validator(load(SCHEMA)).validate(stored)
    assert (
        RECON.self_digest(stored, "reconciliation_sha256")
        == stored["reconciliation_sha256"]
    )
    assert stored["state"] == "ARTIFACT_BYTES_RECONCILED_MEASURED_NOT_PROMOTED"
    assert set(stored["authorization"].values()) == {False}


def test_signature_artifact_and_public_head_claims_remain_distinct():
    stored = load(ARTIFACT)
    assert set(stored["receipt_signature_validity"]) == {
        "training",
        "evaluation",
        "key_id",
        "trust_boundary",
    }
    assert stored["exact_qualified_artifact_binding"]["verified"] is True
    assert stored["current_public_head_equivalence"]["verified"] is True
    assert (
        stored["current_public_head_equivalence"][
            "qualified_commit_git_object_verified"
        ]
        is True
    )
    assert (
        stored["current_public_head_equivalence"][
            "public_head_commit_git_object_verified"
        ]
        is True
    )
    assert (
        stored["current_public_head_equivalence"][
            "complete_revision_tree_delta_verified"
        ]
        is True
    )
    assert (
        stored["exact_qualified_artifact_binding"]["model_raw_sha256"]
        != stored["exact_qualified_artifact_binding"][
            "model_receipt_directory_sha256"
        ]
    )
    assert (
        stored["exact_qualified_artifact_binding"]["adapter_raw_sha256"]
        != stored["exact_qualified_artifact_binding"][
            "adapter_receipt_directory_sha256"
        ]
    )


def test_digest_domain_vectors_prove_basename_is_part_of_receipt_digest():
    fixture = load(FIXTURE)
    vectors = fixture["digest_test_vectors"]
    content = __import__("base64").b64decode(vectors[0]["content_base64"])
    model = RECON.raw_and_receipt_digest("model.safetensors", content)
    adapter = RECON.raw_and_receipt_digest("adapter_model.safetensors", content)
    assert model[0] == adapter[0]
    assert model[1] != adapter[1]
    assert model == (
        vectors[0]["raw_sha256"],
        vectors[0]["receipt_directory_sha256"],
    )
    assert adapter == (
        vectors[1]["raw_sha256"],
        vectors[1]["receipt_directory_sha256"],
    )


def test_inference_bearing_public_head_drift_refuses():
    fixture = load(FIXTURE)
    qualification = load(QUALIFICATION)
    fixture["inference_bearing_blobs"][0]["public_head_git_blob_sha1"] = "0" * 40
    with pytest.raises(RECON.ReconciliationRefusal, match="inference-bearing public-head drift"):
        RECON.reconcile(fixture, qualification)


def test_exact_coordinated_zero_blob_ids_refuse_against_revision_tree():
    fixture = load(FIXTURE)
    qualification = load(QUALIFICATION)
    entry = next(
        item
        for item in fixture["inference_bearing_blobs"]
        if item["path"] == "config.json"
    )
    entry["qualified_git_blob_sha1"] = "0" * 40
    entry["public_head_git_blob_sha1"] = "0" * 40

    with pytest.raises(
        RECON.ReconciliationRefusal,
        match="qualified path/blob is not bound to the declared revision: config.json",
    ):
        RECON.reconcile(fixture, qualification)


def test_qualification_receipt_self_digest_tamper_refuses():
    fixture = load(FIXTURE)
    qualification = load(QUALIFICATION)
    qualification["counts"]["catastrophic_events"] = 1
    with pytest.raises(RECON.ReconciliationRefusal, match="self-digest mismatch"):
        RECON.reconcile(fixture, qualification)


def test_coordinated_artifact_metadata_tamper_cannot_escape_lfs_binding():
    fixture = load(FIXTURE)
    qualification = load(QUALIFICATION)
    content = b"x"
    raw_sha256, receipt_directory_sha256 = RECON.raw_and_receipt_digest(
        "model.safetensors",
        content,
    )
    tampered_claim = {
        "path": "model.safetensors",
        "bytes": len(content),
        "sha256": raw_sha256,
        "receipt_directory_sha256": receipt_directory_sha256,
    }
    qualification["candidate"]["model_file"] = tampered_claim
    qualification["receipt_sha256"] = RECON.receipt_digest(qualification)
    fixture["qualification_receipt"]["receipt_sha256"] = qualification[
        "receipt_sha256"
    ]
    fixture["qualification_receipt"]["artifact_binding"]["model_file"] = {
        "path": tampered_claim["path"],
        "bytes": tampered_claim["bytes"],
        "raw_sha256": tampered_claim["sha256"],
        "receipt_directory_sha256": tampered_claim[
            "receipt_directory_sha256"
        ],
    }

    with pytest.raises(
        RECON.ReconciliationRefusal,
        match="raw artifact claim does not bind to the frozen LFS pointer",
    ):
        RECON.reconcile(fixture, qualification)


def test_coordinated_blob_transcription_cannot_escape_revision_tree_binding():
    fixture = load(FIXTURE)
    qualification = load(QUALIFICATION)
    for entry in fixture["inference_bearing_blobs"]:
        if entry["path"] == "config.json":
            entry["qualified_git_blob_sha1"] = "0" * 40
            entry["public_head_git_blob_sha1"] = "0" * 40
    for revision in ("qualified", "public_head"):
        root = fixture["git_object_evidence"][revision]["trees"][0]
        for entry in root["entries"]:
            if entry["name"] == "config.json":
                entry["object_sha1"] = "0" * 40

    with pytest.raises(
        RECON.ReconciliationRefusal,
        match="tree object identity mismatch",
    ):
        RECON.reconcile(fixture, qualification)


def test_commit_object_tamper_cannot_preserve_declared_revision():
    fixture = load(FIXTURE)
    qualification = load(QUALIFICATION)
    encoded = fixture["git_object_evidence"]["qualified"]["commit_object_base64"]
    raw = bytearray(__import__("base64").b64decode(encoded))
    raw[-1] ^= 1
    fixture["git_object_evidence"]["qualified"]["commit_object_base64"] = (
        __import__("base64").b64encode(raw).decode("ascii")
    )

    with pytest.raises(
        RECON.ReconciliationRefusal,
        match="commit object identity mismatch",
    ):
        RECON.reconcile(fixture, qualification)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda fixture: fixture["signature_evidence"]["training"].update(
                {"verified": False}
            ),
            "training signature is not verified",
        ),
        (
            lambda fixture: fixture["qualification_receipt"]["artifact_binding"][
                "model_file"
            ].update({"raw_sha256": "0" * 64}),
            "model_file differs",
        ),
        (
            lambda fixture: fixture["digest_test_vectors"][0].update(
                {"receipt_directory_sha256": "0" * 64}
            ),
            "basename-plus-bytes digest domain",
        ),
        (
            lambda fixture: fixture["authorization"].update({"promoted": True}),
            "cannot authorize",
        ),
        (
            lambda fixture: fixture["inference_bearing_blobs"].pop(),
            "inference-bearing path set mismatch",
        ),
        (
            lambda fixture: fixture.update({"public_head_revision": "0" * 40}),
            "public-head revision mismatch",
        ),
    ],
)
def test_reconciliation_negative_controls_refuse(mutation, message):
    fixture = copy.deepcopy(load(FIXTURE))
    mutation(fixture)
    with pytest.raises(RECON.ReconciliationRefusal, match=message):
        RECON.reconcile(fixture, load(QUALIFICATION))


def test_reconciliation_program_has_no_network_or_mutating_hub_client():
    source = SCRIPT.read_text(encoding="utf-8")
    for forbidden in (
        "urllib",
        "requests",
        "httpx",
        "huggingface_hub",
        "HfApi",
        "upload_file",
        "create_commit",
    ):
        assert forbidden not in source
