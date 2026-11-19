"""Release-contract validation for the Khipu compound Second Brain."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from ayllu import model_binding

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
        "trust_model": "ROOT_SIGNED_PURPOSE_SCOPED_ISSUER_TOOL_KEY",
        "content_binding": (
            "EXACT_CONTENT_SOURCE_IDENTITY_REVISION_AUTHOR_RIGHTSHOLDER_"
            "PERMISSION_PRIVACY_REVIEW_AND_CONTAMINATION"
        ),
        "cross_run_isolation": "POLICY_PINNED_SIGNED_SPLIT_LEDGER_HEAD",
        "review_signer_binding": "REVIEWER_OWNED_KEY",
        "terminal_artifact": "ED25519_SIGNED_MANIFEST",
        "self_attestation_allowed": False,
    }
    assert set(policy["required_admission_inputs"]) == {
        "protected_eval_content_sha256_list",
        "purpose_scoped_evidence_trust_store",
        "policy_root_signer",
        "root_signed_policy_bundle",
        "signed_prior_split_ledger_descriptor",
        "exact_split_ledger_head_sha256",
        "reviewer_allowlist",
        "artifact_signing_key",
        "explicit_train_admission_switch",
    }
    assert {
        "source.identity",
        "rights.author",
        "rights.rightsholder",
        "rights.permission_scope",
        "privacy.pii_result",
        "review.reviewer",
        "review.reasons",
    } <= set(policy["candidate_required_inputs"])
    assert {
        "privacy.status",
        "review.status",
        "reason_codes",
        "decision_receipt_sha256",
    } <= set(policy["derived_decision_fields"])
    assert "ENABLE_TRAIN_ADMISSION_BY_DEFAULT" in policy["forbidden_shortcuts"]


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
    assert {name: item["path"] for name, item in inventory.items()} == {
        "source_admission_manifest": "research/formula-training-admission/admission-manifest.json",
        "m1_brain_ingest_ledger": "model_release/m1/brain-ingest-ledger.jsonl",
        "m1_corpus_manifest": "model_release/m1/corpus-ingestion-manifest.json",
    }
    observed = model_binding.current_brain_inventory()
    assert observed["state"] == "OBSERVED"
    assert observed["raw_nodes_observed"] == observed_rows
    assert observed["execution_authority"] is False
    historical = manifest["brain_training_policy"]["historical_inventory_evidence"][
        "source_admission_manifest"]
    assert historical == {
        "path": "dataset_release/szl-proof-obligation-queue/data/source-admission-manifest.json",
        "file_sha256": "37c3ded4d6d5590157f93f7e926ff942e398e46c44c9e277c8ed846bc518bff8",
    }
    assert _sha256(ROOT / historical["path"]) == historical["file_sha256"]


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def _receipt(value: dict) -> str:
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")).hexdigest()


@pytest.fixture
def current_inventory(tmp_path, monkeypatch):
    """Tiny current artifacts with a separately retained historical count."""
    ledger_path = tmp_path / "model_release/m1/brain-ingest-ledger.jsonl"
    ledger_path.parent.mkdir(parents=True)
    ledger_path.write_bytes(b''.join(
        (json.dumps({"node_id": node_id, "training_eligible": False,
                     "training_decision": "QUARANTINE"}) + "\n").encode("utf-8")
        for node_id in ("current-a", "current-b")
    ))
    manifest_path = ledger_path.with_name("corpus-ingestion-manifest.json")
    _write_json(manifest_path, {
        "release_state": "NOT_PROMOTED", "training_state": "NOT_RUN",
        "training_relation": "PROPOSAL_ONLY_NOT_USED_BY_EXISTING_ADAPTER",
        "source_snapshot": {"raw_node_count": 2},
        "coverage": {
            "node_decisions_total": 2, "node_decisions_expected": 2,
            "raw_nodes_training_quarantined": 2, "quarantined_or_excluded_nodes": 2,
            "training_eligible_nodes": 0, "node_decisions": {"QUARANTINE": 2},
        },
        "ledgers": {"brain_nodes": {
            "path": ledger_path.name, "sha256": _sha256(ledger_path),
            "rows": 2, "bytes": ledger_path.stat().st_size,
        }},
    })
    admission_path = tmp_path / "research/formula-training-admission/admission-manifest.json"
    admission = {"status": "COMPLETE_FAIL_CLOSED_HOLDOUT_ONLY",
                 "source_snapshot": {"m1_alignment": {
        "aligned": True,
        "brain_ledger_path": ledger_path.relative_to(tmp_path).as_posix(),
        "brain_ledger_sha256": _sha256(ledger_path),
        "brain_ledger_rows": 2,
        "manifest_path": manifest_path.relative_to(tmp_path).as_posix(),
        "manifest_sha256": _sha256(manifest_path),
        "current_raw_nodes": 2,
        "raw_training_eligible_rows": 0, "current_only_node_ids": [],
        "m1_only_node_ids": [], "training_state": "NOT_RUN",
        "admission": "CURRENT_INVENTORY_ONLY_ALL_ROWS_QUARANTINED",
    }, "brain": {"raw_node_count": 2, "quarantined_node_count": 2,
                  "training_text_rows_emitted": 0}},
        "decision_summary": {"train_rows": 0, "raw_brain_rows_emitted": 0,
                             "raw_brain_nodes_quarantined": 2},
        "claims_boundary": {"training_triggered": False, "model_promoted": False,
                            "raw_node_text_emitted": False}}
    admission["manifest_receipt_sha256"] = _receipt(admission)
    _write_json(admission_path, admission)
    paths = {
        "m1_brain_ingest_ledger": ledger_path,
        "m1_corpus_manifest": manifest_path,
        "source_admission_manifest": admission_path,
    }
    policy = {
        "raw_nodes_observed": 2,
        "raw_nodes_admitted_to_gradients": 0,
        "current_state": "ROW_LEVEL_ADMISSION_ENGINE_IMPLEMENTED_CURRENT_RAW_ROWS_QUARANTINED",
        "current_inventory_evidence": {
            name: {"path": path.relative_to(tmp_path).as_posix(),
                   "file_sha256": _sha256(path)}
            for name, path in paths.items()
        },
        "historical_inventory_evidence": {"raw_nodes_observed": 9465},
    }
    policy["current_inventory_evidence"]["m1_brain_ingest_ledger"]["rows"] = 2
    document = {"schema_version": model_binding.SECOND_BRAIN_SCHEMA,
                "brain_training_policy": policy}
    policy_path = tmp_path / "model_release/szl-khipu-second-brain.json"
    _write_json(policy_path, document)
    monkeypatch.setattr(model_binding, "_INVENTORY_ROOT", tmp_path)
    return document, policy_path, paths


def test_current_inventory_observation_keeps_runtime_and_training_planes_separate(
    current_inventory,
) -> None:
    observed = model_binding.current_brain_inventory()
    assert observed["state"] == "OBSERVED"
    assert observed["raw_nodes_observed"] == 2
    assert observed["execution_authority"] is False
    runtime = model_binding.second_brain_binding(rag_status={"brain_handle_count": 17})
    assert runtime["memory"]["brain_handle_count"] == 17
    assert runtime["training_boundary"]["raw_brain_nodes_observed"] == 2
    assert runtime["training_boundary"]["raw_brain_nodes_admitted_to_gradients"] == 0
    assert runtime["training_boundary"]["training_admission_authorized"] is False


@pytest.mark.parametrize("failure", [
    "missing_policy", "missing_ledger", "ledger_tampered", "manifest_tampered",
    "admission_tampered", "wrong_path", "wrong_policy_count", "boolean_count",
    "missing_current_evidence", "wrong_admission_receipt", "wrong_admission_alignment",
])
def test_current_inventory_evidence_fails_closed(current_inventory, failure) -> None:
    document, policy_path, paths = current_inventory
    policy = document["brain_training_policy"]
    evidence = policy["current_inventory_evidence"]
    if failure == "missing_policy":
        policy_path.unlink()
    elif failure == "missing_ledger":
        paths["m1_brain_ingest_ledger"].unlink()
    elif failure in {"ledger_tampered", "manifest_tampered", "admission_tampered"}:
        name = {"ledger_tampered": "m1_brain_ingest_ledger",
                "manifest_tampered": "m1_corpus_manifest",
                "admission_tampered": "source_admission_manifest"}[failure]
        with paths[name].open("ab") as stream:
            stream.write(b" ")
    else:
        if failure == "wrong_path":
            evidence["source_admission_manifest"]["path"] = (
                "dataset_release/szl-proof-obligation-queue/data/source-admission-manifest.json")
        elif failure == "wrong_policy_count":
            policy["raw_nodes_observed"] = 9465
        elif failure == "boolean_count":
            policy["raw_nodes_observed"] = True
        elif failure == "missing_current_evidence":
            del policy["current_inventory_evidence"]
        else:
            path = paths["source_admission_manifest"]
            admission = json.loads(path.read_text())
            if failure == "wrong_admission_receipt":
                admission["manifest_receipt_sha256"] = "0" * 64
            else:
                admission.pop("manifest_receipt_sha256")
                admission["source_snapshot"]["m1_alignment"]["aligned"] = False
                admission["manifest_receipt_sha256"] = _receipt(admission)
            _write_json(path, admission)
            evidence["source_admission_manifest"]["file_sha256"] = _sha256(path)
        _write_json(policy_path, document)
    observed = model_binding.current_brain_inventory()
    assert observed["state"] == "UNAVAILABLE"
    assert observed["raw_nodes_observed"] is None
    assert observed["execution_authority"] is False
    runtime = model_binding.second_brain_binding(rag_status={"brain_handle_count": 17})
    boundary = runtime["training_boundary"]
    assert boundary["raw_brain_nodes_observed"] is None
    assert boundary["current_state"] == "CURRENT_INVENTORY_UNAVAILABLE"
    assert boundary["raw_brain_nodes_admitted_to_gradients"] is None
    assert boundary["training_admission_authorized"] is False
    assert runtime["memory"]["brain_handle_count"] == 17


@pytest.mark.parametrize(("source", "field", "value"), [
    ("policy", ("raw_nodes_admitted_to_gradients",), 1),
    ("policy", ("raw_nodes_admitted_to_gradients",), False),
    ("policy", ("raw_nodes_admitted_to_gradients",), 0.0),
    ("admission", ("source_snapshot", "m1_alignment", "raw_training_eligible_rows"), 1),
    ("admission", ("source_snapshot", "m1_alignment", "raw_training_eligible_rows"), False),
    ("corpus", ("coverage", "training_eligible_nodes"), 1),
    ("corpus", ("coverage", "training_eligible_nodes"), False),
    ("corpus", ("coverage", "raw_nodes_training_quarantined"), 1),
    ("corpus", ("coverage", "quarantined_or_excluded_nodes"), 1),
    ("corpus", ("coverage", "node_decisions_total"), 1),
    ("corpus", ("coverage", "node_decisions_expected"), 1),
    ("corpus", ("coverage", "node_decisions"), {"QUARANTINE": 1, "TRAIN": 1}),
    ("corpus", ("source_snapshot", "raw_node_count"), 1),
    ("admission", ("source_snapshot", "brain", "raw_node_count"), 1),
    ("admission", ("source_snapshot", "brain", "quarantined_node_count"), 1),
    ("admission", ("source_snapshot", "brain", "training_text_rows_emitted"), 1),
    ("admission", ("decision_summary", "train_rows"), 1),
    ("admission", ("decision_summary", "raw_brain_rows_emitted"), 1),
    ("admission", ("decision_summary", "raw_brain_nodes_quarantined"), 1),
    ("admission", ("source_snapshot", "m1_alignment", "current_only_node_ids"), ["new"]),
    ("admission", ("source_snapshot", "m1_alignment", "m1_only_node_ids"), ["removed"]),
    ("corpus", ("release_state",), "PROMOTED"),
    ("corpus", ("training_state",), "TRAINED"),
    ("corpus", ("training_relation",), "USED_BY_EXISTING_ADAPTER"),
    ("admission", ("source_snapshot", "m1_alignment", "training_state"), "TRAINED"),
    ("admission", ("claims_boundary", "training_triggered"), True),
    ("admission", ("claims_boundary", "model_promoted"), True),
    ("admission", ("claims_boundary", "raw_node_text_emitted"), True),
    ("ledger", ("training_eligible",), True),
    ("ledger", ("training_eligible",), 0),
    ("ledger", ("training_decision",), "TRAIN"),
])
def test_rehashed_inventory_cannot_contradict_quarantine_claim(
    current_inventory, source, field, value,
) -> None:
    """Valid byte/content receipts do not override contradictory admission facts."""
    document, policy_path, paths = current_inventory
    corpus = json.loads(paths["m1_corpus_manifest"].read_text())
    admission = json.loads(paths["source_admission_manifest"].read_text())
    rows = [json.loads(line) for line in paths["m1_brain_ingest_ledger"].read_bytes().splitlines()]
    target = {"policy": document["brain_training_policy"], "corpus": corpus,
              "admission": admission, "ledger": rows[0]}[source]
    for key in field[:-1]:
        target = target[key]
    target[field[-1]] = value

    # Rebind the entire chain after mutation, so rejection must be semantic.
    paths["m1_brain_ingest_ledger"].write_bytes(b''.join(
        (json.dumps(row, sort_keys=True) + "\n").encode("utf-8") for row in rows
    ))
    ledger_entry = corpus["ledgers"]["brain_nodes"]
    ledger_entry["sha256"] = _sha256(paths["m1_brain_ingest_ledger"])
    ledger_entry["bytes"] = paths["m1_brain_ingest_ledger"].stat().st_size
    _write_json(paths["m1_corpus_manifest"], corpus)
    alignment = admission["source_snapshot"]["m1_alignment"]
    alignment["brain_ledger_sha256"] = ledger_entry["sha256"]
    alignment["manifest_sha256"] = _sha256(paths["m1_corpus_manifest"])
    admission.pop("manifest_receipt_sha256")
    admission["manifest_receipt_sha256"] = _receipt(admission)
    _write_json(paths["source_admission_manifest"], admission)
    for name, path in paths.items():
        document["brain_training_policy"]["current_inventory_evidence"][name]["file_sha256"] = _sha256(path)
    _write_json(policy_path, document)

    observed = model_binding.current_brain_inventory()
    assert observed["state"] == "UNAVAILABLE"
    assert observed["raw_nodes_observed"] is None
    assert observed["execution_authority"] is False
    runtime = model_binding.second_brain_binding(rag_status={"brain_handle_count": 17})
    boundary = runtime["training_boundary"]
    assert boundary["current_state"] == "CURRENT_INVENTORY_UNAVAILABLE"
    assert boundary["raw_brain_nodes_observed"] is None
    assert boundary["raw_brain_nodes_admitted_to_gradients"] is None
    assert boundary["training_admission_authorized"] is False
    assert runtime["memory"]["brain_handle_count"] == 17


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
    # Preserve the first versioned July 15 observation from commit
    # 0f4df9e83e4ae65dfed80570264c9f35fc06dfff: 9,464 historical handles.
    # Current inventory is validated independently above.
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
