#!/usr/bin/env python3
"""Validate the original A11oy action-contract manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shlex
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = REPO_ROOT / "docs" / "action-contract-manifest.json"
PATTERNS_PATH = REPO_ROOT / "docs" / "public-pattern-source-manifest.json"
RUNTIME_EVIDENCE_SCHEMA = "a11oy.action-contract.runtime-evidence.v1"
REQUIRED_RUNTIME_TESTS = {
    "test_authenticated_operator_execution",
    "test_server_side_idempotency_enforcement",
    "test_durable_receipt_persistence_across_restart",
    "test_operator_confirmation_gate",
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_evidence_command(command: str) -> str | None:
    try:
        parts = shlex.split(command)
    except ValueError:
        return f"evidence command is not parseable: {command}"
    if len(parts) != 2 or parts[0] not in {"python", "python3"}:
        return (
            "evidence commands must be direct Python validators with no shell "
            f"indirection: {command}"
        )
    scripts_root = (REPO_ROOT / "scripts").resolve()
    script_path = (REPO_ROOT / parts[1]).resolve()
    if (
        not script_path.is_relative_to(scripts_root)
        or script_path.suffix != ".py"
        or not script_path.is_file()
    ):
        return f"evidence command target does not exist: {command}"
    return None


def current_source_commit() -> str | None:
    """Read HEAD from Git metadata without requiring a git executable."""
    dot_git = REPO_ROOT / ".git"
    try:
        if dot_git.is_file():
            marker = dot_git.read_text(encoding="utf-8").strip()
            if not marker.startswith("gitdir:"):
                return None
            git_dir = Path(marker.removeprefix("gitdir:").strip())
            if not git_dir.is_absolute():
                git_dir = (REPO_ROOT / git_dir).resolve()
        elif dot_git.is_dir():
            git_dir = dot_git
        else:
            return None

        common_dir = git_dir
        common_marker = git_dir / "commondir"
        if common_marker.is_file():
            relative_common = common_marker.read_text(encoding="utf-8").strip()
            common_dir = (git_dir / relative_common).resolve()

        head = (git_dir / "HEAD").read_text(encoding="utf-8").strip()
        if not head.startswith("ref:"):
            commit = head.lower()
            return commit if re.fullmatch(r"[0-9a-f]{40}", commit) else None

        ref = head.removeprefix("ref:").strip()
        for root in (git_dir, common_dir):
            ref_path = root / ref
            if ref_path.is_file():
                commit = ref_path.read_text(encoding="utf-8").strip().lower()
                return commit if re.fullmatch(r"[0-9a-f]{40}", commit) else None

        packed_refs = common_dir / "packed-refs"
        if packed_refs.is_file():
            for line in packed_refs.read_text(encoding="utf-8").splitlines():
                if not line or line.startswith(("#", "^")):
                    continue
                parts = line.split(" ", 1)
                if len(parts) != 2:
                    continue
                commit, packed_ref = parts
                if packed_ref == ref and re.fullmatch(r"[0-9a-f]{40}", commit):
                    return commit.lower()
    except OSError:
        return None
    return None


def validate_runtime_evidence(
    report_path: Path | None,
    contract: dict,
) -> list[str]:
    """Validate independent, commit-bound JUnit evidence for runtime promotion."""
    if report_path is None:
        return [
            "verified-runtime requires independent runtime evidence via "
            "--runtime-evidence-junit; execution flags in the manifest are not proof"
        ]

    if not report_path.is_absolute():
        return ["verified-runtime evidence path must be absolute"]
    try:
        resolved_report = report_path.resolve(strict=True)
    except OSError:
        return [f"verified-runtime evidence report does not exist: {report_path}"]
    if not resolved_report.is_file():
        return [f"verified-runtime evidence report is not a file: {report_path}"]
    if resolved_report.is_relative_to(REPO_ROOT.resolve()):
        return [
            "verified-runtime evidence must be generated outside the repository; "
            "a committed same-change report is not independent"
        ]

    try:
        root = ET.parse(resolved_report).getroot()
    except (ET.ParseError, OSError) as exc:
        return [f"verified-runtime evidence is not valid JUnit XML: {exc}"]

    errors: list[str] = []
    properties: dict[str, str] = {}
    for node in root.findall(".//property"):
        name = node.get("name")
        value = node.get("value")
        if not name or value is None:
            continue
        if name in properties:
            errors.append(f"verified-runtime evidence property is duplicated: {name}")
            continue
        properties[name] = value

    expected_commit = current_source_commit()
    expected_contract_sha = hashlib.sha256(CONTRACT_PATH.read_bytes()).hexdigest()
    expected_properties = {
        "evidence_schema": RUNTIME_EVIDENCE_SCHEMA,
        "contract_id": str(contract.get("contractId", "")),
        "contract_sha256": expected_contract_sha,
        "source_commit": expected_commit,
    }
    if expected_commit is None:
        errors.append("verified-runtime evidence cannot be bound: git HEAD is unavailable")
    for name, expected in expected_properties.items():
        if properties.get(name) != expected:
            errors.append(
                f"verified-runtime evidence property {name} does not match "
                "the checked-out contract and commit"
            )

    observed_tests: dict[str, list[ET.Element]] = {}
    for testcase in root.findall(".//testcase"):
        name = testcase.get("name")
        if name:
            observed_tests.setdefault(name, []).append(testcase)
    for name in sorted(REQUIRED_RUNTIME_TESTS):
        cases = observed_tests.get(name, [])
        if len(cases) != 1:
            errors.append(
                f"verified-runtime evidence must contain exactly one passing {name}"
            )
            continue
        if any(
            cases[0].find(tag) is not None
            for tag in ("failure", "error", "skipped")
        ):
            errors.append(f"verified-runtime evidence test did not pass: {name}")

    if any(root.findall(f".//{tag}") for tag in ("failure", "error")):
        errors.append("verified-runtime evidence report contains failing tests")
    return errors


def main(runtime_evidence_junit: Path | None = None) -> int:
    errors: list[str] = []
    contract = load_json(CONTRACT_PATH)
    patterns = load_json(PATTERNS_PATH)
    pattern_ids = {pattern["id"] for pattern in patterns.get("patterns", [])}

    if contract.get("schemaVersion") != "a11oy.action-contract.v0.1":
        errors.append("schemaVersion must be a11oy.action-contract.v0.1")

    if contract.get("claimStatus") not in {"roadmap", "verified-runtime", "release-payload"}:
        errors.append("claimStatus must be roadmap, verified-runtime, or release-payload")

    clean_room = contract.get("cleanRoom", {})
    if clean_room.get("copyingRule") != "pattern-only":
        errors.append("cleanRoom.copyingRule must be pattern-only")
    if "endorsement" not in clean_room.get("endorsementBoundary", "").lower():
        errors.append("cleanRoom.endorsementBoundary must reject implied endorsement")
    for pattern_id in clean_room.get("sourcePatternIds", []):
        if pattern_id not in pattern_ids:
            errors.append(f"unknown source pattern ID: {pattern_id}")

    identity = contract.get("identity", {})
    for field in ["actorId", "actorKind", "sessionId", "signerVerifier"]:
        if not identity.get(field):
            errors.append(f"identity.{field} is required")

    intent = contract.get("intent", {})
    if intent.get("regime") != "doctrine-v11":
        errors.append("intent.regime must match the current doctrine-v11 contract")

    policy = contract.get("policy", {})
    for field in ["policyDocumentRef", "policyHash", "mandatoryAxes", "minimumLambdaCoverage", "approvalGate"]:
        if field not in policy:
            errors.append(f"policy.{field} is required")
    policy_ref = policy.get("policyDocumentRef")
    if policy_ref and not (REPO_ROOT / policy_ref).exists():
        errors.append(f"policyDocumentRef does not exist: {policy_ref}")
    if not isinstance(policy.get("mandatoryAxes", []), list) or not policy.get("mandatoryAxes"):
        errors.append("policy.mandatoryAxes must be a non-empty list")
    if float(policy.get("minimumLambdaCoverage", 0)) < 0.0:
        errors.append("policy.minimumLambdaCoverage must be non-negative")

    evidence = contract.get("evidence", {})
    for collection in ["manifestRefs", "attestationRefs", "testCommands", "localEvidenceRefs", "claimRefs"]:
        if not isinstance(evidence.get(collection), list):
            errors.append(f"evidence.{collection} must be a list")
    commands = evidence.get("testCommands", [])
    if not commands:
        errors.append("evidence.testCommands must contain executable validators")
    for command in commands:
        if not isinstance(command, str):
            errors.append("evidence.testCommands entries must be strings")
            continue
        command_error = validate_evidence_command(command)
        if command_error:
            errors.append(command_error)
    for collection in ["manifestRefs", "attestationRefs", "localEvidenceRefs", "claimRefs"]:
        for ref in evidence.get(collection, []):
            if not (REPO_ROOT / ref).exists():
                errors.append(f"evidence ref does not exist: {ref}")
    if "do not prove" not in str(evidence.get("evidenceBoundary", "")).lower():
        errors.append("evidence.evidenceBoundary must state what validation does not prove")

    receipt_sinks = contract.get("receiptSinks", {})
    if receipt_sinks.get("chainMode") != "hash-chain":
        errors.append("receiptSinks.chainMode must be hash-chain")
    if int(receipt_sinks.get("retentionDays", 0)) < 365:
        errors.append("receiptSinks.retentionDays must be at least 365")
    for field in ["primaryJsonl", "payloadBundlePath", "udsManifestRef"]:
        if not receipt_sinks.get(field):
            errors.append(f"receiptSinks.{field} is required")

    replay = contract.get("replayBounds", {})
    if not replay.get("idempotencyKey"):
        errors.append("replayBounds.idempotencyKey is required")
    if int(replay.get("maxReplays", 0)) < 1:
        errors.append("replayBounds.maxReplays must be >= 1")
    if int(replay.get("replayWindowSeconds", 0)) < 1:
        errors.append("replayBounds.replayWindowSeconds must be >= 1")
    for ref in replay.get("deterministicInputs", []):
        if not (REPO_ROOT / ref).exists():
            errors.append(f"deterministic input does not exist: {ref}")

    egress = contract.get("egressLimits", {})
    if egress.get("defaultDeny") is not True:
        errors.append("egressLimits.defaultDeny must be true")
    denied = set(egress.get("deniedCapabilities", []))
    for capability in ["secret-export", "private-repo-ingestion", "self-approval"]:
        if capability not in denied:
            errors.append(f"egressLimits.deniedCapabilities missing {capability}")

    uds = contract.get("udsProofPoint", {})
    forbidden_text = " ".join(uds.get("forbiddenClaims", [])).lower()
    for phrase in ["endorsed", "catalog accepted", "deploys to every uds"]:
        if phrase not in forbidden_text:
            errors.append(f"udsProofPoint.forbiddenClaims missing boundary phrase: {phrase}")
    if "proof point" not in uds.get("wording", "").lower():
        errors.append("udsProofPoint.wording must use proof point language")

    execution = contract.get("execution", {})
    runtime_status = execution.get("runtimeStatus")
    if contract.get("claimStatus") == "roadmap":
        if runtime_status != "roadmap":
            errors.append("roadmap action contracts require execution.runtimeStatus=roadmap")
        if execution.get("runtimeImplemented") is not False:
            errors.append("roadmap action contracts require execution.runtimeImplemented=false")
    if contract.get("claimStatus") == "verified-runtime":
        if runtime_status != "live":
            errors.append("verified-runtime requires execution.runtimeStatus=live")
        for field in [
            "runtimeImplemented",
            "authenticatedExecution",
            "idempotencyEnforced",
            "durableReceiptLifecycle",
        ]:
            if execution.get(field) is not True:
                errors.append(f"verified-runtime requires execution.{field}=true")
        errors.extend(validate_runtime_evidence(runtime_evidence_junit, contract))
    if "do not constitute" not in str(execution.get("evidenceBoundary", "")).lower():
        errors.append("execution.evidenceBoundary must reject manifest-only runtime proof")

    if errors:
        print("Action contract manifest validation failed:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print(f"Validated {CONTRACT_PATH.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--runtime-evidence-junit",
        type=Path,
        help=(
            "external JUnit XML from the protected runtime suite; required only "
            "for verified-runtime promotion"
        ),
    )
    args = parser.parse_args()
    sys.exit(main(args.runtime_evidence_junit))
