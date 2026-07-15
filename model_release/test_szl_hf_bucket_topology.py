"""Honesty and integrity tests for the verified HF Bucket topology."""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


HERE = Path(__file__).resolve().parent
CONTRACT_PATH = HERE / "szl-hf-bucket-topology.json"
SCHEMA_PATH = HERE / "szl-hf-bucket-topology.schema.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_bucket_topology_is_draft_2020_12_valid() -> None:
    schema = _load(SCHEMA_PATH)
    contract = _load(CONTRACT_PATH)
    Draft202012Validator.check_schema(schema)
    errors = sorted(
        Draft202012Validator(
            schema, format_checker=FormatChecker()
        ).iter_errors(contract),
        key=lambda error: list(error.absolute_path),
    )
    assert not errors, "\n".join(
        f"{'.'.join(map(str, error.absolute_path)) or '<root>'}: {error.message}"
        for error in errors
    )


def test_all_buckets_are_private_empty_mutable_and_noncanonical() -> None:
    contract = _load(CONTRACT_PATH)
    assert contract["status"] == "CREATED_PRIVATE_EMPTY_VERIFIED"
    assert contract["scope"]["canonical_release_store"] is False
    assert contract["scope"]["remote_creation_performed_by_this_contract"] is True
    assert contract["scope"]["remote_mutation_performed_by_this_contract"] is True
    assert contract["scope"]["credential_use_performed_by_this_contract"] is True

    qualified_names = [item["qualified_name"] for item in contract["topology"]]
    assert len(qualified_names) == len(set(qualified_names))
    assert len(qualified_names) == 3
    for bucket in contract["topology"]:
        assert bucket["status"] == "CREATED_PRIVATE_EMPTY_VERIFIED"
        assert bucket["remote_observation"]["private"] is True
        assert bucket["remote_observation"]["size_bytes"] == 0
        assert bucket["remote_observation"]["total_files"] == 0
        assert bucket["canonical"] is False
        assert bucket["mutability"] == "MUTABLE_NON_VERSIONED"
        assert bucket["may_publish_canonical_release"] is False
        assert bucket["key_layout"]["completion_marker_key"].endswith(
            "/_control/COMPLETED.json"
        )


def test_completion_is_two_phase_signed_and_readback_bound() -> None:
    protocol = _load(CONTRACT_PATH)["two_phase_completion_protocol"]
    phase_1 = " ".join(protocol["phase_1_stage_and_verify"]).lower()
    phase_2 = " ".join(protocol["phase_2_complete"]).lower()
    acceptance = " ".join(protocol["consumer_acceptance_predicate"]).lower()

    assert protocol["hash_algorithm"] == "SHA-256"
    assert protocol["signature_envelope"] == "DSSE_PAE"
    assert "upload the signed manifest" in phase_1
    assert "get every payload object" in phase_1
    assert "recompute their sha-256" in phase_1
    assert "creates completed.json last" in phase_2
    assert "conditional create operation that refuses overwrite" in phase_2
    assert "marker and manifest dsse signatures" in acceptance
    assert "no undeclared object" in acceptance
    assert protocol["bucket_audit_log_is_release_proof"] is False


def test_forbidden_content_is_exact_and_has_no_exceptions() -> None:
    forbidden = _load(CONTRACT_PATH)["forbidden_content"]
    assert {item["code"] for item in forbidden} == {
        "ACCESS_TOKEN_OR_CREDENTIAL",
        "SIGNING_PRIVATE_KEY",
        "RAW_PII_PHI_PCI",
        "CUSTOMER_CONFIDENTIAL_RAW_CONTENT",
        "RIGHTS_UNKNOWN_OR_UNLICENSED_CORPUS",
        "UNADMITTED_BRAIN_ROWS",
        "PROTECTED_EVAL_ANSWER_KEY_IN_TRAINING",
        "UNQUALIFIED_MODEL_WEIGHT_OR_ADAPTER",
        "MALWARE_OR_UNTRUSTED_EXECUTABLE",
        "UNSANITIZED_RUNTIME_TELEMETRY",
        "CANONICAL_RELEASE_ONLY_COPY",
        "MUTABLE_ALIAS_AS_ARTIFACT_IDENTITY",
    }
    assert all(item["exception_allowed"] is False for item in forbidden)


def test_authorities_are_separated_and_bucket_never_approves_release() -> None:
    contract = _load(CONTRACT_PATH)
    authorities = {item["role_id"]: item for item in contract["release_authorities"]}
    assert set(authorities) == {
        "bucket-stager",
        "independent-readback-verifier",
        "release-approver",
        "canonical-hub-publisher",
        "runtime-evidence-writer",
    }
    assert authorities["bucket-stager"]["may_stage_payload"] is True
    assert authorities["bucket-stager"]["may_write_completion_marker"] is False
    assert authorities["independent-readback-verifier"]["may_stage_payload"] is False
    assert authorities["independent-readback-verifier"]["may_write_completion_marker"] is True
    assert authorities["release-approver"]["may_approve_release"] is True
    assert authorities["release-approver"]["may_publish_canonical_repo"] is False
    assert authorities["canonical-hub-publisher"]["may_approve_release"] is False
    assert authorities["canonical-hub-publisher"]["may_publish_canonical_repo"] is True

    for authority in authorities.values():
        assert not (
            authority["may_stage_payload"]
            and authority["may_write_completion_marker"]
        )
        assert not (
            authority["may_approve_release"]
            and authority["may_publish_canonical_repo"]
        )

    assert contract["canonical_promotion"]["automatic_promotion"] is False
    assert contract["claims_boundary"]["completed_marker_is_release_approval"] is False


def test_sources_are_official_and_contract_contains_no_secret_values() -> None:
    contract = _load(CONTRACT_PATH)
    assert all(
        source["url"].startswith("https://huggingface.co/docs/")
        and source["evidence_label"] == "PRIMARY_REPORTED"
        for source in contract["primary_sources"]
    )
    serialized = json.dumps(contract).lower()
    for forbidden_key_name in (
        "access_token_value",
        "secret_value",
        "private_key_pem",
        "aws_secret_access_key",
    ):
        assert forbidden_key_name not in serialized
    assert contract["external_mutations"] == {
        "hugging_face_bucket_create": True,
        "hugging_face_bucket_write": False,
        "hugging_face_bucket_delete": False,
        "hugging_face_repo_publish": False,
        "github_push_or_release": False,
        "zenodo_deposit_or_publish": False,
        "token_or_secret_use": True,
    }
