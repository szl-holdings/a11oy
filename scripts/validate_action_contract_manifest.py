#!/usr/bin/env python3
"""Validate the original A11oy action-contract manifest."""

from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = REPO_ROOT / "docs" / "action-contract-manifest.json"
PATTERNS_PATH = REPO_ROOT / "docs" / "public-pattern-source-manifest.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
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
    for collection in ["manifestRefs", "attestationRefs", "localEvidenceRefs", "claimRefs"]:
        for ref in evidence.get(collection, []):
            if not (REPO_ROOT / ref).exists():
                errors.append(f"evidence ref does not exist: {ref}")

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

    if errors:
        print("Action contract manifest validation failed:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print(f"Validated {CONTRACT_PATH.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
