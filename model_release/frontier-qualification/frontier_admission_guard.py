"""Offline, fail-closed admission guard for external frontier models.

The registry is research and qualification policy, not a downloader, trainer,
router, publisher, or deletion tool.  Unknown repositories and unpinned
revisions are denied. A permitted operation is only a preflight admission of a
signed declaration after its exact evidence requirements are supplied; it never
grants execution authority or implies model quality or promotion eligibility.
"""

from __future__ import annotations

import argparse
import importlib
import json
import re
import sys
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
DEFAULT_REGISTRY = HERE / "frontier-adoption.json"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
REPO_ROOT = HERE.parents[1]
EVIDENCE_PAYLOAD_TYPE = "application/vnd.szl.frontier-operation-evidence.v1+json"
UNSIGNED_OPERATION_ALLOWLIST = frozenset({"READ_METADATA"})
HARD_DENIED_OPERATIONS = frozenset({
    "TRAIN",
    "SERVE_PRODUCTION",
    "PROMOTE",
    "MERGE_WEIGHTS",
    "INGEST_UPSTREAM_TRAINING_TRACES",
    "IDENTITY_EDIT_REAL_PERSON",
})


class FrontierAdmissionError(RuntimeError):
    """The requested external-model operation failed closed."""


def _load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise FrontierAdmissionError(f"expected JSON object: {path}")
    return value


def load_registry(path: Path = DEFAULT_REGISTRY) -> dict[str, Any]:
    if not path.is_file():
        raise FrontierAdmissionError(f"frontier adoption registry missing: {path}")
    registry = _load_object(path)
    if registry.get("schema_version") != "szl.frontier-adoption.v1":
        raise FrontierAdmissionError("unsupported frontier adoption registry schema")
    if registry.get("status") != "GOVERNED_PLAN_NOT_LOCAL_QUALIFICATION":
        raise FrontierAdmissionError("frontier registry honesty state changed")
    policy = registry.get("evidence_policy", {})
    required_policy = {
        "local_measurements_present": False,
        "download_performed_by_this_contract": False,
        "promotion_authority": False,
        "unknown_repository_policy": "DENY",
        "zero_download_policy": "ZERO_DOWNLOADS_ALONE_NEVER_AUTHORIZES_DELETE_OR_ARCHIVE",
    }
    for field, expected in required_policy.items():
        if policy.get(field) != expected:
            raise FrontierAdmissionError(f"registry policy mismatch: {field}")
    mutations = registry.get("external_mutations")
    if not isinstance(mutations, dict) or not mutations:
        raise FrontierAdmissionError("registry external_mutations contract is missing")
    if any(value is not False for value in mutations.values()):
        raise FrontierAdmissionError("registry reports an external mutation")
    brain = registry.get("brain_model_truth")
    if not isinstance(brain, dict):
        raise FrontierAdmissionError("registry brain_model_truth is missing")
    if brain.get("raw_nodes_observed") != 9464:
        raise FrontierAdmissionError("registry Brain node observation changed")
    if brain.get("raw_nodes_admitted_to_gradients") != 0:
        raise FrontierAdmissionError("registry reports unadmitted Brain gradient rows")
    github_estate = registry.get("github_estate_strategy")
    if not isinstance(github_estate, dict):
        raise FrontierAdmissionError("registry github_estate_strategy is missing")
    if github_estate.get("source_reported_repository_count") != 54:
        raise FrontierAdmissionError("registry GitHub source count changed")
    if github_estate.get("inventory_complete") is not False:
        raise FrontierAdmissionError("registry overclaims a complete GitHub inventory")
    if github_estate.get("public_github_repositories_observed") != 50:
        raise FrontierAdmissionError("registry public GitHub readback count changed")
    if github_estate.get("public_archived_observed") != 9:
        raise FrontierAdmissionError("registry public GitHub archive count changed")
    if github_estate.get("reconciliation_state") != (
        "SOURCE_REPORT_54_PUBLIC_READBACK_50_ATTACHMENT_TRUNCATED_REVIEW_REQUIRED"
    ):
        raise FrontierAdmissionError("registry GitHub reconciliation state changed")
    if github_estate.get("code_to_weight_policy") != (
        "CODE_REPOSITORIES_ARE_SERVICES_LIBRARIES_OR_EVIDENCE_NOT_MODEL_WEIGHTS"
    ):
        raise FrontierAdmissionError("registry code-to-weight boundary changed")
    if github_estate.get("unclassified_repository_policy") != (
        "DISCOVER_CLASSIFY_FAIL_CLOSED_NO_ARCHIVE"
    ):
        raise FrontierAdmissionError("registry unclassified repository policy changed")
    layers = github_estate.get("layers")
    if not isinstance(layers, list) or len(layers) < 8:
        raise FrontierAdmissionError("registry GitHub estate layer map is incomplete")
    candidates = registry.get("candidates")
    if not isinstance(candidates, list) or len(candidates) < 9:
        raise FrontierAdmissionError("registry candidate inventory is incomplete")
    for candidate in candidates:
        if not isinstance(candidate, dict):
            raise FrontierAdmissionError("registry candidate record is malformed")
        required_candidate = {
            "id", "decision", "upstream", "runtime", "allowed_operations",
            "prohibited_operations", "required_evidence_by_operation",
        }
        if not required_candidate.issubset(candidate):
            raise FrontierAdmissionError("registry candidate record is incomplete")
        upstream = candidate.get("upstream")
        if not isinstance(upstream, dict) or not {
            "repository_id", "revision", "artifact_inventory"
        }.issubset(upstream):
            raise FrontierAdmissionError("registry candidate upstream record is incomplete")
        allowed = candidate.get("allowed_operations")
        prohibited = candidate.get("prohibited_operations")
        requirements = candidate.get("required_evidence_by_operation")
        if not isinstance(allowed, list) or not allowed:
            raise FrontierAdmissionError("registry candidate operation allowlist is missing")
        if not isinstance(prohibited, list) or not HARD_DENIED_OPERATIONS.issubset(prohibited):
            raise FrontierAdmissionError("registry candidate hard-deny boundary changed")
        if set(allowed) & set(prohibited):
            raise FrontierAdmissionError("registry candidate operation is both allowed and prohibited")
        if not isinstance(requirements, dict):
            raise FrontierAdmissionError("registry candidate evidence policy is missing")
        for permitted in allowed:
            if permitted in UNSIGNED_OPERATION_ALLOWLIST:
                continue
            fields = requirements.get(permitted)
            if not isinstance(fields, list) or not fields:
                raise FrontierAdmissionError(
                    f"registry candidate signed evidence requirements missing: {permitted}"
                )
    estate = registry.get("hf_estate")
    repositories = estate.get("repositories") if isinstance(estate, dict) else None
    if not isinstance(repositories, list) or len(repositories) < 15:
        raise FrontierAdmissionError("registry Hugging Face estate is incomplete")
    return registry


def _candidate_for_repo(registry: dict[str, Any], repository_id: str) -> dict[str, Any]:
    matches = [
        candidate
        for candidate in registry.get("candidates", [])
        if candidate.get("upstream", {}).get("repository_id") == repository_id
    ]
    if len(matches) != 1:
        raise FrontierAdmissionError(
            f"repository is unknown or ambiguous and is denied: {repository_id}"
        )
    return matches[0]


def _validate_evidence(
    candidate: dict[str, Any],
    operation: str,
    revision: str,
    evidence: dict[str, Any],
) -> None:
    requirements = candidate.get("required_evidence_by_operation", {}).get(operation, [])
    missing = [field for field in requirements if not evidence.get(field)]
    if missing:
        raise FrontierAdmissionError(
            f"{operation} missing required evidence: {','.join(sorted(missing))}"
        )

    upstream = candidate["upstream"]
    runtime = candidate["runtime"]
    if "exact_revision" in requirements and evidence["exact_revision"] != revision:
        raise FrontierAdmissionError("evidence exact_revision does not match requested revision")
    if "method_source_revision" in requirements and evidence["method_source_revision"] != revision:
        raise FrontierAdmissionError("method source revision does not match the pinned model card")
    if "runtime_revision" in requirements:
        expected_runtime = runtime["revision"]
        if expected_runtime == "MODEL_CARD_ONLY" or evidence["runtime_revision"] != expected_runtime:
            raise FrontierAdmissionError("runtime revision is absent or does not match the pinned runtime")
    if "artifact_sha256" in requirements:
        allowlisted = {
            item["sha256"] for item in upstream.get("artifact_inventory", [])
        }
        if evidence["artifact_sha256"] not in allowlisted:
            raise FrontierAdmissionError("artifact digest is not in the pinned candidate inventory")

    for field in requirements:
        if field.endswith("_sha256") and not SHA256_RE.fullmatch(str(evidence[field])):
            raise FrontierAdmissionError(f"invalid SHA-256 evidence value: {field}")


def _verified_evidence_payload(
    evidence_document: dict[str, Any],
    repository_id: str,
    revision: str,
    operation: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Verify a signed evidence envelope and bind it to this exact operation.

    Digest-looking strings are not receipts.  Every evidence-bearing operation
    requires an ECDSA-P256 DSSE envelope verifiable by the checked-in SZL public
    key.  The signed payload must bind repository, revision, operation, and the
    complete evidence object before any bounded preflight admission can be emitted.
    """

    envelope = evidence_document.get("dsse")
    if not isinstance(envelope, dict):
        raise FrontierAdmissionError("signed DSSE evidence envelope is required")
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    try:
        verifier = importlib.import_module("szl_dsse")
        verdict = verifier.verify_envelope(envelope)
    except Exception as exc:
        raise FrontierAdmissionError(
            f"DSSE verifier unavailable: {type(exc).__name__}"
        ) from exc
    if verdict.get("verified") is not True:
        raise FrontierAdmissionError(
            f"DSSE evidence verification failed: {verdict.get('reason', 'signature mismatch')}"
        )
    if verdict.get("payloadType") != EVIDENCE_PAYLOAD_TYPE:
        raise FrontierAdmissionError("signed evidence DSSE payloadType mismatch")
    signatures = verdict.get("signatures") or []
    if not any(
        item.get("verified") is True
        and item.get("keyid") == verdict.get("keyid_expected")
        for item in signatures
        if isinstance(item, dict)
    ):
        raise FrontierAdmissionError("signed evidence key identity mismatch")
    payload = verdict.get("payload_decoded")
    if not isinstance(payload, dict):
        raise FrontierAdmissionError("signed DSSE evidence payload is not a JSON object")
    expected_binding = {
        "schema_version": "szl.frontier-operation-evidence.v1",
        "repository_id": repository_id,
        "revision": revision,
        "operation": operation,
    }
    for field, expected in expected_binding.items():
        if payload.get(field) != expected:
            raise FrontierAdmissionError(f"signed evidence binding mismatch: {field}")
    evidence = payload.get("evidence")
    if not isinstance(evidence, dict):
        raise FrontierAdmissionError("signed evidence payload has no evidence object")
    return evidence, verdict


def assert_operation_allowed(
    repository_id: str,
    revision: str,
    operation: str,
    evidence: dict[str, Any] | None = None,
    registry_path: Path = DEFAULT_REGISTRY,
) -> dict[str, Any]:
    """Preflight-admit one bounded operation declaration or fail closed.

    The return value is deliberately explicit that this check is not a model
    qualification, execution, or promotion decision. Metadata reads are the only
    directly authorized operation; signed declarations still require a separate
    replay-protected executor admission.
    """

    registry = load_registry(registry_path)
    candidate = _candidate_for_repo(registry, repository_id)
    pinned_revision = candidate["upstream"]["revision"]
    if revision != pinned_revision:
        raise FrontierAdmissionError(
            f"revision mismatch for {repository_id}: expected {pinned_revision}"
        )
    if operation in HARD_DENIED_OPERATIONS:
        raise FrontierAdmissionError(
            f"operation is hard-denied by executable policy: {operation}"
        )
    if operation in candidate.get("prohibited_operations", []):
        raise FrontierAdmissionError(
            f"operation is explicitly prohibited for {repository_id}: {operation}"
        )
    if operation not in candidate.get("allowed_operations", []):
        raise FrontierAdmissionError(
            f"operation is not allowlisted for {repository_id}: {operation}"
        )
    requirements = candidate.get("required_evidence_by_operation", {}).get(operation, [])
    if operation not in UNSIGNED_OPERATION_ALLOWLIST and not requirements:
        raise FrontierAdmissionError(
            f"operation lacks mandatory signed evidence requirements: {operation}"
        )
    evidence_verified = False
    dsse_pae_sha256 = None
    evidence_values: dict[str, Any] = {}
    if requirements:
        evidence_values, verdict = _verified_evidence_payload(
            evidence or {}, repository_id, revision, operation
        )
        evidence_verified = True
        dsse_pae_sha256 = verdict.get("pae_sha256")
    _validate_evidence(candidate, operation, revision, evidence_values)
    metadata_read = operation in UNSIGNED_OPERATION_ALLOWLIST
    return {
        "schema_version": "szl.frontier-operation-admission.v1",
        "repository_id": repository_id,
        "revision": revision,
        "candidate_id": candidate["id"],
        "decision": candidate["decision"],
        "operation": operation,
        "operation_allowed_by_registry": True,
        "operation_authorized": metadata_read,
        "operation_preflight_admitted": metadata_read or evidence_verified,
        "execution_authority": False,
        "replay_protected": False,
        "execution_boundary": (
            "METADATA_READ_ONLY"
            if metadata_read
            else "SIGNED_DECLARATION_ONLY_REQUIRES_RUN_BOUND_EXECUTOR_ADMISSION"
        ),
        "evidence_verified": evidence_verified,
        "signed_evidence_declaration_verified": evidence_verified,
        "underlying_receipt_content_recomputed": False,
        "dsse_pae_sha256": dsse_pae_sha256,
        "model_qualified": False,
        "training_authorized": False,
        "production_serving_authorized": False,
        "promotion_authorized": False,
        "external_mutation_performed": False,
    }


def classify_hf_repository(
    repository_id: str,
    registry_path: Path = DEFAULT_REGISTRY,
) -> dict[str, Any]:
    registry = load_registry(registry_path)
    matches = [
        item
        for item in registry.get("hf_estate", {}).get("repositories", [])
        if item.get("repository_id") == repository_id
    ]
    if len(matches) != 1:
        return {
            "repository_id": repository_id,
            "classification": "UNCLASSIFIED_FAIL_CLOSED",
            "delete_authorized": False,
        }
    return dict(matches[0])


def audit_registry(registry_path: Path = DEFAULT_REGISTRY) -> dict[str, Any]:
    registry = load_registry(registry_path)
    errors: list[str] = []
    candidates = registry.get("candidates", [])
    ids = [candidate.get("id") for candidate in candidates]
    repos = [candidate.get("upstream", {}).get("repository_id") for candidate in candidates]
    if len(ids) != len(set(ids)):
        errors.append("duplicate candidate id")
    if len(repos) != len(set(repos)):
        errors.append("duplicate candidate repository")

    for candidate in candidates:
        allowed = set(candidate.get("allowed_operations", []))
        prohibited = set(candidate.get("prohibited_operations", []))
        if allowed & prohibited:
            errors.append(f"{candidate.get('id')}: operation both allowed and prohibited")
        if candidate.get("decision", "").startswith("QUARANTINE_") and allowed != {"READ_METADATA"}:
            errors.append(f"{candidate.get('id')}: quarantine may only allow metadata reads")
        if candidate.get("decision") in {"LOCAL_QUALIFY", "EVALUATION_ONLY_INFERENCE_ARTIFACT"}:
            if not candidate.get("required_evidence_by_operation", {}).get("EVALUATE_SANDBOXED"):
                errors.append(f"{candidate.get('id')}: sandbox evaluation lacks evidence requirements")
        if "TRAIN" not in prohibited or "PROMOTE" not in prohibited or "MERGE_WEIGHTS" not in prohibited:
            errors.append(f"{candidate.get('id')}: frontier candidates must deny train/promote/merge")

    estate = registry.get("hf_estate", {}).get("repositories", [])
    estate_ids = [item.get("repository_id") for item in estate]
    if len(estate_ids) != len(set(estate_ids)):
        errors.append("duplicate Hugging Face estate repository")
    if any(item.get("delete_authorized") is not False for item in estate):
        errors.append("an estate record authorizes deletion")

    policy = registry["evidence_policy"]
    mutations = registry["external_mutations"]
    github_estate = registry["github_estate_strategy"]
    return {
        "schema_version": "szl.frontier-adoption-audit.v1",
        "state": "PASS" if not errors else "FAIL",
        "candidate_count": len(candidates),
        "estate_repository_count": len(estate),
        "github_source_report_count": github_estate["source_reported_repository_count"],
        "github_public_readback_count": github_estate["public_github_repositories_observed"],
        "github_inventory_complete": github_estate["inventory_complete"],
        "local_measurements_present": bool(policy["local_measurements_present"]),
        "promotion_authority": bool(policy["promotion_authority"]),
        "external_mutation_performed": any(bool(value) for value in mutations.values()),
        "errors": errors,
    }


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("audit")
    check = subparsers.add_parser("check")
    check.add_argument("--repository", required=True)
    check.add_argument("--revision", required=True)
    check.add_argument("--operation", required=True)
    check.add_argument("--evidence-json", type=Path)
    classify = subparsers.add_parser("classify-estate")
    classify.add_argument("--repository", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "audit":
            result = audit_registry(args.registry)
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0 if result["state"] == "PASS" else 2
        if args.command == "classify-estate":
            print(json.dumps(classify_hf_repository(args.repository, args.registry), indent=2, sort_keys=True))
            return 0
        evidence = _load_object(args.evidence_json) if args.evidence_json else {}
        result = assert_operation_allowed(
            args.repository,
            args.revision,
            args.operation,
            evidence,
            args.registry,
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, FrontierAdmissionError) as exc:
        print(json.dumps({
            "state": "BLOCKED",
            "reason": str(exc),
            "external_mutation_performed": False,
        }, indent=2, sort_keys=True))
        return 3


if __name__ == "__main__":
    raise SystemExit(_main())
