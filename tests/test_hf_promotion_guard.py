"""Offline safety tests for SZL Hugging Face promotion contracts."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest


_ROOT = Path(__file__).resolve().parents[1]
_GUARD_PATH = _ROOT / "model_release" / "hf-promotion" / "promotion_guard.py"
_SPEC = importlib.util.spec_from_file_location("szl_hf_promotion_guard", _GUARD_PATH)
assert _SPEC and _SPEC.loader
_GUARD = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _GUARD
_SPEC.loader.exec_module(_GUARD)

DEFAULT_MANIFEST = _GUARD.DEFAULT_MANIFEST
PromotionGuardError = _GUARD.PromotionGuardError
ROOT = _GUARD.ROOT
audit_contract = _GUARD.audit_contract
build_stage_plan = _GUARD.build_stage_plan
inventory_payload = _GUARD.inventory_payload
validate_peft_payload = _GUARD.validate_peft_payload


def _load_manifest() -> dict:
    return json.loads(DEFAULT_MANIFEST.read_text(encoding="utf-8"))


def _write_manifest(tmp_path: Path, value: dict) -> Path:
    path = tmp_path / "promotion-manifest.json"
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    return path


def test_contract_hashes_cards_prefixes_and_blocked_decisions_pass_offline() -> None:
    report = audit_contract()
    assert report["contract_integrity"] == "PASS", report["errors"]
    assert report["offline"] is True
    assert report["network_accessed"] is False
    assert report["credentials_accessed"] is False
    assert report["promotion_performed"] is False
    manifest = _load_manifest()
    expected_artifacts = sum(len(candidate["local_artifacts"]) for candidate in manifest["candidates"])
    assert len(report["observed_artifacts"]) == expected_artifacts
    assert {item["hash_basis"] for item in report["observed_artifacts"]} <= {
        "UTF8_LF",
        "RAW_BYTES",
    }
    assert set(report["candidate_decisions"]) == {
        "SZL-Nemo-runtime-recipe-v1",
        "SZL-Nemo-Governed-Adapter-v1",
        "SZL-Forge-1.5B-ReceiptAgent-v1",
    }
    assert all(value.startswith("BLOCKED_") for value in report["candidate_decisions"].values())


def test_manifest_text_identity_is_clone_stable_across_line_endings(tmp_path: Path) -> None:
    lf = tmp_path / "lf.json"
    crlf = tmp_path / "crlf.json"
    lf.write_bytes(b'{"state":"PASS"}\n')
    crlf.write_bytes(b'{"state":"PASS"}\r\n')
    assert _GUARD._artifact_identity(lf) == _GUARD._artifact_identity(crlf)


def test_manifest_validates_against_draft_2020_12_schema() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    manifest = _load_manifest()
    schema = json.loads((DEFAULT_MANIFEST.parent / "promotion-manifest.schema.json").read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.Draft202012Validator(schema).validate(manifest)


def test_nemo_release_manifest_validates_and_stays_recipe_only() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    folder = ROOT / "model_release" / "szl-nemo"
    manifest = json.loads((folder / "release-manifest.json").read_text(encoding="utf-8"))
    schema = json.loads((folder / "release-manifest.schema.json").read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(manifest)
    assert manifest["release_state"] == "RUNTIME_QUALIFIED_RECIPE_NOT_FINE_TUNED"
    assert manifest["weights_present_in_repository"] is False
    assert manifest["szl_fine_tuned"] is False
    assert manifest["training_state"] == "NOT_FINE_TUNED"
    assert manifest["promotion"]["recipe_runtime_ready"] is True
    assert manifest["promotion"]["trained_candidate_ready"] is False
    assert manifest["promotion"]["canonical_model_upload_allowed"] is False


def test_candidate_qualification_schema_is_draft_2020_12_valid() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(
        (DEFAULT_MANIFEST.parent / "candidate-qualification.schema.json").read_text(
            encoding="utf-8"
        )
    )
    jsonschema.Draft202012Validator.check_schema(schema)


def test_any_hash_or_model_card_truth_drift_fails_contract(tmp_path: Path) -> None:
    manifest = _load_manifest()
    manifest["candidates"][0]["local_artifacts"][0]["sha256"] = "0" * 64
    manifest["candidates"][1]["model_card_truth"]["required_literals"].append("not-present-truth-field")
    report = audit_contract(manifest_path=_write_manifest(tmp_path, manifest))
    assert report["contract_integrity"] == "FAIL"
    assert any("sha256 mismatch" in error for error in report["errors"])
    assert any("missing truth literal" in error for error in report["errors"])


def test_bucket_prefix_must_bind_candidate_slug_and_never_use_alias(tmp_path: Path) -> None:
    manifest = _load_manifest()
    manifest["candidates"][0]["bucket_prefixes"]["build"] = "attempts/{attempt_id}/payload/latest/"
    report = audit_contract(manifest_path=_write_manifest(tmp_path, manifest))
    assert report["contract_integrity"] == "FAIL"
    assert any("invalid build bucket prefix" in error for error in report["errors"])


def test_stage_plan_refuses_before_touching_missing_payload() -> None:
    with pytest.raises(PromotionGuardError, match="candidate remains blocked"):
        build_stage_plan(
            "SZL-Forge-1.5B-ReceiptAgent-v1",
            Path("this-payload-deliberately-does-not-exist"),
            "019f-safe-never-reused",
        )


def test_payload_inventory_rejects_pickle_checkpoint_and_symlink(tmp_path: Path) -> None:
    unsafe = tmp_path / "candidate"
    unsafe.mkdir()
    (unsafe / "adapter_model.bin").write_bytes(b"unsafe")
    with pytest.raises(PromotionGuardError, match="forbidden payload extension"):
        inventory_payload(unsafe, {".bin"})

    (unsafe / "adapter_model.bin").unlink()
    target = unsafe / "adapter_config.json"
    target.write_text("{}", encoding="utf-8")
    link = unsafe / "linked.json"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("host does not permit creating a symlink for this regression")
    with pytest.raises(PromotionGuardError, match="symlink payload is forbidden"):
        inventory_payload(unsafe, {".bin"})


def test_peft_qualification_must_hash_exact_adapter_and_config(tmp_path: Path) -> None:
    payload = tmp_path / "candidate"
    payload.mkdir()
    adapter = payload / "adapter_model.safetensors"
    config = payload / "adapter_config.json"
    adapter.write_bytes(b"not-real-weights-test-fixture")
    config.write_text(
        json.dumps({"base_model_name_or_path": "unsloth/Qwen2.5-1.5B-Instruct-bnb-4bit"}),
        encoding="utf-8",
    )
    qualification = {
        "schema_version": "szl.hf-candidate-qualification.v1",
        "candidate_id": "SZL-Forge-1.5B-ReceiptAgent-v1",
        "artifact_class": "PEFT_ADAPTER",
        "decision": "QUALIFIED_FOR_NAMED_HUMAN_PROMOTION_REVIEW",
        "base_repository": "unsloth/Qwen2.5-1.5B-Instruct-bnb-4bit",
        "base_revision": "d2f2dd02b071701d5100a04a7a49d6fb0bd305b7",
        "adapter_model_sha256": hashlib.sha256(adapter.read_bytes()).hexdigest(),
        "adapter_config_sha256": hashlib.sha256(config.read_bytes()).hexdigest(),
        "base_file_set_sha256": "1" * 64,
        "training_receipt_sha256": "2" * 64,
        "reload_receipt_sha256": "3" * 64,
        "evaluation_receipt_sha256": "4" * 64,
        "license_review_sha256": "5" * 64,
        "human_approval_sha256": "6" * 64,
        "dsse_attestation_sha256": "7" * 64,
        "evaluation": {
            "all_required_suites_passed": True,
            "catastrophic_errors_observed": 0,
            "held_out_split_sha256": "8" * 64,
        },
        "external_mutations": {
            "bucket_objects_uploaded": False,
            "hub_repository_mutated": False,
            "published": False,
            "promoted": False,
        },
    }
    (payload / "candidate-qualification.json").write_text(
        json.dumps(qualification), encoding="utf-8"
    )
    inventory = inventory_payload(payload, {".bin", ".pkl", ".pt"})
    validate_peft_payload(payload, inventory, qualification["candidate_id"])

    tampered = copy.deepcopy(qualification)
    tampered["adapter_model_sha256"] = "0" * 64
    (payload / "candidate-qualification.json").write_text(json.dumps(tampered), encoding="utf-8")
    inventory = inventory_payload(payload, {".bin", ".pkl", ".pt"})
    with pytest.raises(PromotionGuardError, match="adapter_model_sha256"):
        validate_peft_payload(payload, inventory, qualification["candidate_id"])


def test_no_upload_or_network_api_exists_in_guard_source() -> None:
    source = (DEFAULT_MANIFEST.parent / "promotion_guard.py").read_text(encoding="utf-8")
    forbidden_imports = ("huggingface_hub", "requests", "httpx", "boto3")
    assert all(f"import {name}" not in source and f"from {name}" not in source for name in forbidden_imports)
    assert "upload_file(" not in source
    assert "create_repo(" not in source
    assert "HF_TOKEN" not in source
