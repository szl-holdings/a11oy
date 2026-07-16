"""Fail-closed tests for the external frontier-model adoption registry."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
FRONTIER = ROOT / "model_release" / "frontier-qualification"
REGISTRY_PATH = FRONTIER / "frontier-adoption.json"
SCHEMA_PATH = FRONTIER / "frontier-adoption.schema.json"
GUARD_PATH = FRONTIER / "frontier_admission_guard.py"

SPEC = importlib.util.spec_from_file_location("frontier_admission_guard", GUARD_PATH)
assert SPEC and SPEC.loader
guard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guard)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _candidate(repository_id: str) -> dict:
    registry = _load(REGISTRY_PATH)
    return next(
        item for item in registry["candidates"]
        if item["upstream"]["repository_id"] == repository_id
    )


def _unsigned_evidence(candidate: dict, operation: str) -> dict:
    evidence: dict[str, str] = {}
    for field in candidate["required_evidence_by_operation"].get(operation, []):
        if field == "exact_revision" or field == "method_source_revision":
            evidence[field] = candidate["upstream"]["revision"]
        elif field == "runtime_revision":
            evidence[field] = candidate["runtime"]["revision"]
        elif field == "artifact_sha256":
            evidence[field] = candidate["upstream"]["artifact_inventory"][0]["sha256"]
        elif field.endswith("_sha256"):
            evidence[field] = "a" * 64
        else:
            evidence[field] = "present"
    return {
        "dsse": {
            "payloadType": "application/vnd.szl.frontier-operation-evidence.v1+json",
            "payload": "e30=",
            "signatures": [],
        },
        "declared_evidence": evidence,
    }


def _signed_evidence(
    candidate: dict,
    operation: str,
    monkeypatch,
    payload_type: str = guard.EVIDENCE_PAYLOAD_TYPE,
) -> dict:
    from cryptography.hazmat.primitives.asymmetric import ec
    import szl_dsse

    private_key = ec.generate_private_key(ec.SECP256R1())
    monkeypatch.setattr(szl_dsse, "_load_private_key", lambda: private_key)
    monkeypatch.setattr(szl_dsse, "_load_public_key", lambda: private_key.public_key())
    payload = {
        "schema_version": "szl.frontier-operation-evidence.v1",
        "repository_id": candidate["upstream"]["repository_id"],
        "revision": candidate["upstream"]["revision"],
        "operation": operation,
        "evidence": _unsigned_evidence(candidate, operation)["declared_evidence"],
    }
    return {
        "dsse": szl_dsse.sign_payload(
            payload,
            payload_type,
        )
    }


def test_registry_is_strict_draft_2020_12_valid() -> None:
    schema = _load(SCHEMA_PATH)
    registry = _load(REGISTRY_PATH)
    Draft202012Validator.check_schema(schema)
    errors = sorted(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(registry),
        key=lambda error: list(error.absolute_path),
    )
    assert not errors, "\n".join(
        f"{'.'.join(map(str, error.absolute_path)) or '<root>'}: {error.message}"
        for error in errors
    )


def test_brain_and_flagship_truth_are_explicit() -> None:
    registry = _load(REGISTRY_PATH)
    brain = registry["brain_model_truth"]
    assert brain["raw_nodes_observed"] == 9464
    assert brain["raw_nodes_admitted_to_gradients"] == 0
    assert brain["current_weight_model"] == "SZLHOLDINGS/SZL-Khipu-1.5B-BrainNavigator"
    assert brain["current_weight_model_relation"] == (
        "TRAINED_ON_SYNTHETIC_HANDLE_NAVIGATION_NOT_RAW_BRAIN_NODE_CONTENT"
    )
    assert "2_OF_6_ABSTENTION_CORRECT" in brain["current_release_limit"]
    flagship = registry["flagship_strategy"]
    assert flagship["unification_mode"] == "ONE_PRODUCT_FAMILY_ROUTER_COLLECTION_AND_SHARED_EVALS"
    assert flagship["tensor_merge_authorized"] is False
    joined_strategy = " ".join(flagship["strategy"])
    assert "ReceiptAgent emits signed receipts" not in joined_strategy
    assert "target role and behavior are not established" in joined_strategy
    assert "external signer must emit DSSE receipts" in joined_strategy
    assert "artifact-binding conflict" in joined_strategy


def test_github_estate_is_layered_without_turning_code_into_weights() -> None:
    estate = _load(REGISTRY_PATH)["github_estate_strategy"]
    assert estate["source_reported_repository_count"] == 54
    assert estate["attachment_entries_observed"] == 30
    assert estate["inventory_complete"] is False
    assert estate["public_github_repositories_observed"] == 50
    assert estate["public_archived_observed"] == 9
    assert set(estate["reported_not_publicly_readback"]) == {
        "szl-org-health", "szl-substrate", "pitch-collateral"
    }
    assert estate["code_to_weight_policy"] == (
        "CODE_REPOSITORIES_ARE_SERVICES_LIBRARIES_OR_EVIDENCE_NOT_MODEL_WEIGHTS"
    )
    assert estate["unclassified_repository_policy"] == (
        "DISCOVER_CLASSIFY_FAIL_CLOSED_NO_ARCHIVE"
    )
    repositories = {
        repo
        for layer in estate["layers"]
        for repo in layer["canonical_repositories"]
    }
    assert {"a11oy", "szl-router", "szl-forge", "szl-lake", "lutar-lean", "anatomy", "killinchu"} <= repositories


def test_receipt_agent_status_matches_canonical_release_manifests() -> None:
    registry = _load(REGISTRY_PATH)
    receipt_release = _load(ROOT / "model_release" / "receipt-agent" / "release-manifest.json")
    forge_family = _load(ROOT / "model_release" / "szl-forge-family.json")

    assert receipt_release["quality_claim"] == "NOT_ESTABLISHED"
    assert receipt_release["artifact_relation"] == (
        "PROPOSED_PROGRAM_EXISTING_ADAPTER_NOT_YET_ESTABLISHED_AS_RECEIPT_AGENT"
    )
    target = next(
        item for item in receipt_release["hf_artifact_family"]
        if item["target_id"] == "SZLHOLDINGS/SZL-Forge-1.5B-ReceiptAgent"
    )
    assert target["state"] == "PLANNED_NOT_CREATED"

    forge_profile = next(
        item for item in forge_family["profiles"]
        if item["profile_id"] == "ReceiptAgent-v1"
    )
    assert forge_profile["state"] == "SIGNED_RECEIPTS_VALID_ARTIFACT_BINDING_CONFLICT"
    assert "model is never the signer" in forge_profile["role"]

    strategy = " ".join(registry["flagship_strategy"]["strategy"])
    assert "target role and behavior are not established" in strategy
    estate_record = next(
        item for item in registry["hf_estate"]["repositories"]
        if item["repository_id"] == "SZLHOLDINGS/SZL-Forge-1.5B-ReceiptAgent"
    )
    assert estate_record["strategy"] == (
        "KEEP_LABELED_ARTIFACT_TARGET_ROLE_UNESTABLISHED_BINDING_CONFLICT"
    )


def test_exact_frontier_decisions_and_pins_are_present() -> None:
    registry = _load(REGISTRY_PATH)
    decisions = {
        item["upstream"]["repository_id"]: (item["decision"], item["upstream"]["revision"])
        for item in registry["candidates"]
    }
    assert decisions == {
        "OpenMOSS-Team/MOSS-Transcribe-Diarize": (
            "LOCAL_QUALIFY", "e6d68cdfcddbdad1a7e8454f0cb859cad76e2502"
        ),
        "prism-ml/Bonsai-27B-gguf": (
            "LOCAL_QUALIFY", "0cf7e3d21581b169b4df1de8bf01316000e2fbb7"
        ),
        "prism-ml/Ternary-Bonsai-27B-gguf": (
            "EVALUATION_ONLY_INFERENCE_ARTIFACT", "20e435f518bd5b882795954aba81e80a91894321"
        ),
        "thinkingmachines/Inkling": (
            "REMOTE_ONLY", "86b4d430ab871652a707666b89203a866888c5e5"
        ),
        "zai-org/GLM-5.2": (
            "REMOTE_ONLY", "b4734de4facf877f85769a911abafc5283eab3d9"
        ),
        "tencent/Hy3": (
            "REMOTE_ONLY", "89ffd53fb6d74429378ba77b39c91c8cba02d288"
        ),
        "bottlecapai/ThinkingCap-Qwen3.6-27B": (
            "METHODS_ONLY", "2cbd89d3fff9274633aa7b979643c75a9a81cabd"
        ),
        "empero-ai/Qwythos-9B-Claude-Mythos-5-1M": (
            "QUARANTINE_PROVENANCE_UNRESOLVED", "14a29bae5143091aeaf87ad37120de4cd57d592c"
        ),
        "conradlocke/krea2-identity-edit": (
            "QUARANTINE_RESTRICTED_IDENTITY_MODEL", "8f3856364fcee7db52116f72558fce0c233eaac4"
        ),
    }


def test_local_artifacts_are_exactly_hash_pinned() -> None:
    moss = _candidate("OpenMOSS-Team/MOSS-Transcribe-Diarize")
    assert moss["upstream"]["artifact_inventory"] == [{
        "filename": "model-00000-of-00001.safetensors",
        "bytes": 1817113576,
        "sha256": "9a0ceb4ab7330357db3ff583dba8d83625d5b733b00e1d55d6970e11b07026c4",
    }]
    bonsai = _candidate("prism-ml/Bonsai-27B-gguf")
    assert bonsai["upstream"]["artifact_inventory"][0]["sha256"] == (
        "17ef842e47450caeb8eaa3ebfbbab5d2f2278b62b79be107985fb69a2f819aa0"
    )


def test_unknown_or_unpinned_repository_fails_closed() -> None:
    with pytest.raises(guard.FrontierAdmissionError, match="unknown or ambiguous"):
        guard.assert_operation_allowed("unknown/example", "0" * 40, "READ_METADATA")
    moss = _candidate("OpenMOSS-Team/MOSS-Transcribe-Diarize")
    with pytest.raises(guard.FrontierAdmissionError, match="revision mismatch"):
        guard.assert_operation_allowed(
            moss["upstream"]["repository_id"], "0" * 40, "READ_METADATA"
        )


def test_local_download_and_evaluation_require_exact_evidence() -> None:
    moss = _candidate("OpenMOSS-Team/MOSS-Transcribe-Diarize")
    repo = moss["upstream"]["repository_id"]
    revision = moss["upstream"]["revision"]
    with pytest.raises(guard.FrontierAdmissionError, match="signed DSSE"):
        guard.assert_operation_allowed(repo, revision, "DOWNLOAD_PINNED")
    with pytest.raises(guard.FrontierAdmissionError, match="verification failed"):
        guard.assert_operation_allowed(
            repo,
            revision,
            "DOWNLOAD_PINNED",
            _unsigned_evidence(moss, "DOWNLOAD_PINNED"),
        )
    with pytest.raises(guard.FrontierAdmissionError, match="signed DSSE"):
        guard.assert_operation_allowed(repo, revision, "EVALUATE_SANDBOXED")


def test_real_dsse_roundtrip_binds_exact_operation(monkeypatch) -> None:
    moss = _candidate("OpenMOSS-Team/MOSS-Transcribe-Diarize")
    repo = moss["upstream"]["repository_id"]
    revision = moss["upstream"]["revision"]
    document = _signed_evidence(moss, "DOWNLOAD_PINNED", monkeypatch)
    admitted = guard.assert_operation_allowed(
        repo, revision, "DOWNLOAD_PINNED", document
    )
    assert admitted["operation_authorized"] is False
    assert admitted["operation_preflight_admitted"] is True
    assert admitted["execution_authority"] is False
    assert admitted["replay_protected"] is False
    assert admitted["evidence_verified"] is True
    assert admitted["dsse_pae_sha256"]
    assert admitted["model_qualified"] is False
    assert admitted["training_authorized"] is False
    assert admitted["promotion_authorized"] is False

    with pytest.raises(guard.FrontierAdmissionError, match="binding mismatch: operation"):
        guard.assert_operation_allowed(
            repo, revision, "EVALUATE_SANDBOXED", document
        )

    wrong_domain = _signed_evidence(
        moss,
        "DOWNLOAD_PINNED",
        monkeypatch,
        payload_type="application/vnd.szl.unrelated-receipt.v1+json",
    )
    with pytest.raises(guard.FrontierAdmissionError, match="payloadType mismatch"):
        guard.assert_operation_allowed(
            repo, revision, "DOWNLOAD_PINNED", wrong_domain
        )


def test_quarantined_models_cannot_download_train_or_promote() -> None:
    for repo in (
        "empero-ai/Qwythos-9B-Claude-Mythos-5-1M",
        "conradlocke/krea2-identity-edit",
    ):
        candidate = _candidate(repo)
        metadata = guard.assert_operation_allowed(
            repo, candidate["upstream"]["revision"], "READ_METADATA"
        )
        assert metadata["operation_authorized"] is True
        assert metadata["execution_boundary"] == "METADATA_READ_ONLY"
        for operation in ("DOWNLOAD_PINNED", "TRAIN", "SERVE_PRODUCTION", "PROMOTE", "MERGE_WEIGHTS"):
            with pytest.raises(guard.FrontierAdmissionError):
                guard.assert_operation_allowed(repo, candidate["upstream"]["revision"], operation)


def test_ternary_is_evaluation_only_and_runtime_bound() -> None:
    candidate = _candidate("prism-ml/Ternary-Bonsai-27B-gguf")
    repo = candidate["upstream"]["repository_id"]
    revision = candidate["upstream"]["revision"]
    with pytest.raises(guard.FrontierAdmissionError, match="hard-denied"):
        guard.assert_operation_allowed(repo, revision, "TRAIN")
    with pytest.raises(guard.FrontierAdmissionError, match="signed DSSE"):
        guard.assert_operation_allowed(repo, revision, "EVALUATE_SANDBOXED", {})


def test_method_adoption_requires_an_independent_ablation_contract() -> None:
    candidate = _candidate("bottlecapai/ThinkingCap-Qwen3.6-27B")
    repo = candidate["upstream"]["repository_id"]
    revision = candidate["upstream"]["revision"]
    with pytest.raises(guard.FrontierAdmissionError, match="signed DSSE"):
        guard.assert_operation_allowed(repo, revision, "ADOPT_METHOD")
    with pytest.raises(guard.FrontierAdmissionError, match="verification failed"):
        guard.assert_operation_allowed(
            repo,
            revision,
            "ADOPT_METHOD",
            _unsigned_evidence(candidate, "ADOPT_METHOD"),
        )


def test_registry_with_mutation_or_missing_structure_fails_closed(tmp_path: Path) -> None:
    mutated = _load(REGISTRY_PATH)
    mutated["external_mutations"]["model_trained"] = True
    mutation_path = tmp_path / "mutated.json"
    mutation_path.write_text(json.dumps(mutated), encoding="utf-8")
    with pytest.raises(guard.FrontierAdmissionError, match="external mutation"):
        guard.load_registry(mutation_path)

    malformed = _load(REGISTRY_PATH)
    malformed.pop("hf_estate")
    malformed_path = tmp_path / "malformed.json"
    malformed_path.write_text(json.dumps(malformed), encoding="utf-8")
    with pytest.raises(guard.FrontierAdmissionError, match="estate is incomplete"):
        guard.load_registry(malformed_path)

    malformed_candidate = _load(REGISTRY_PATH)
    malformed_candidate["candidates"][0] = None
    malformed_candidate_path = tmp_path / "malformed-candidate.json"
    malformed_candidate_path.write_text(json.dumps(malformed_candidate), encoding="utf-8")
    with pytest.raises(guard.FrontierAdmissionError, match="candidate record is malformed"):
        guard.load_registry(malformed_candidate_path)

    policy_bypass = _load(REGISTRY_PATH)
    candidate = policy_bypass["candidates"][0]
    candidate["allowed_operations"].append("TRAIN")
    candidate["prohibited_operations"].remove("TRAIN")
    policy_bypass_path = tmp_path / "policy-bypass.json"
    policy_bypass_path.write_text(json.dumps(policy_bypass), encoding="utf-8")
    with pytest.raises(guard.FrontierAdmissionError, match="hard-deny boundary"):
        guard.assert_operation_allowed(
            candidate["upstream"]["repository_id"],
            candidate["upstream"]["revision"],
            "TRAIN",
            registry_path=policy_bypass_path,
        )

    empty_evidence = _load(REGISTRY_PATH)
    empty_evidence["candidates"][0]["required_evidence_by_operation"]["DOWNLOAD_PINNED"] = []
    empty_evidence_path = tmp_path / "empty-evidence.json"
    empty_evidence_path.write_text(json.dumps(empty_evidence), encoding="utf-8")
    with pytest.raises(guard.FrontierAdmissionError, match="requirements missing"):
        guard.load_registry(empty_evidence_path)


def test_hf_estate_is_classified_without_deletion_authority() -> None:
    registry = _load(REGISTRY_PATH)
    estate = registry["hf_estate"]["repositories"]
    assert len(estate) == 15
    assert sum(bool(item["weight_bearing"]) for item in estate) == 3
    assert all(item["delete_authorized"] is False for item in estate)
    unknown = guard.classify_hf_repository("SZLHOLDINGS/not-in-registry")
    assert unknown["classification"] == "UNCLASSIFIED_FAIL_CLOSED"
    assert unknown["delete_authorized"] is False


def test_registry_internal_audit_passes_without_external_mutation() -> None:
    report = guard.audit_registry()
    assert report["state"] == "PASS"
    assert report["candidate_count"] == 9
    assert report["estate_repository_count"] == 15
    assert report["github_source_report_count"] == 54
    assert report["github_public_readback_count"] == 50
    assert report["github_inventory_complete"] is False
    assert report["local_measurements_present"] is False
    assert report["promotion_authority"] is False
    assert report["external_mutation_performed"] is False


def test_runtime_image_copies_frontier_contract() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert (
        "COPY model_release/frontier-qualification/ "
        "./model_release/frontier-qualification/"
    ) in dockerfile
