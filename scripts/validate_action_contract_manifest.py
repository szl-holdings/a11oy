#!/usr/bin/env python3
"""Validate the original A11oy action-contract manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = REPO_ROOT / "docs" / "action-contract-manifest.json"
PATTERNS_PATH = REPO_ROOT / "docs" / "public-pattern-source-manifest.json"
PINNED_RUNTIME_SUITE_PATH = (
    REPO_ROOT / "scripts" / "qualify_action_contract_runtime.py"
)
PINNED_RUNTIME_SUITE_SHA256 = (
    "fd8749d15c5bd6e8e3e75f378c1c035d7f09fff392965d698c35fd98c4c7f01d"
)
PROTECTED_BASE_REF = "origin/main"
RUNTIME_SUITE_TIMEOUT_SECONDS = 300
REQUIRED_EVIDENCE_COMMANDS = [
    "python3 scripts/validate_action_contract_manifest.py",
    "python3 scripts/test_validate_action_contract_manifest.py",
]
RUNTIME_CLAIM_FIELDS = [
    "runtimeImplemented",
    "authenticatedExecution",
    "idempotencyEnforced",
    "durableReceiptLifecycle",
]


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


def protected_runtime_suite_bytes() -> bytes | None:
    """Read the pinned suite from the protected base, never from PR evidence."""
    try:
        merge_base = subprocess.run(
            ["git", "merge-base", "HEAD", PROTECTED_BASE_REF],
            cwd=REPO_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=30,
        )
        if merge_base.returncode != 0:
            return None
        base_commit = merge_base.stdout.decode("ascii", errors="strict").strip()
        if not re.fullmatch(r"[0-9a-f]{40}", base_commit):
            return None
        relative_suite = PINNED_RUNTIME_SUITE_PATH.relative_to(REPO_ROOT).as_posix()
        base_suite = subprocess.run(
            ["git", "show", f"{base_commit}:{relative_suite}"],
            cwd=REPO_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=30,
        )
        return base_suite.stdout if base_suite.returncode == 0 else None
    except (OSError, subprocess.SubprocessError, UnicodeError):
        return None


def _qualification_environment(runtime_root: Path) -> dict[str, str]:
    """Build a minimal environment with no inherited CI credentials."""

    allowed = (
        "PATH",
        "SystemRoot",
        "WINDIR",
        "TEMP",
        "TMP",
        "TMPDIR",
        "LANG",
        "LC_ALL",
        "LC_CTYPE",
        "LD_LIBRARY_PATH",
    )
    environment = {
        name: os.environ[name] for name in allowed if name in os.environ
    }
    environment["ACTION_CONTRACT_RUNTIME_ROOT"] = str(runtime_root)
    return environment


def validate_pinned_runtime_suite(
    runtime_root: Path = REPO_ROOT,
) -> list[str]:
    """Run protected suite bytes against an explicit candidate checkout."""

    unresolved_root = Path(runtime_root)
    if unresolved_root.is_symlink():
        return ["verified-runtime candidate root must not be a symlink"]
    try:
        candidate_root = unresolved_root.resolve(strict=True)
    except OSError as exc:
        return [f"verified-runtime candidate root is unavailable: {exc}"]
    if not candidate_root.is_dir():
        return ["verified-runtime candidate root must be a directory"]

    try:
        current_suite = PINNED_RUNTIME_SUITE_PATH.read_bytes()
    except OSError:
        return ["verified-runtime pinned qualification suite is unavailable"]

    current_digest = hashlib.sha256(current_suite).hexdigest()
    if current_digest != PINNED_RUNTIME_SUITE_SHA256:
        return [
            "verified-runtime pinned qualification suite digest does not match "
            "the validator"
        ]

    protected_suite = protected_runtime_suite_bytes()
    if protected_suite is None:
        return [
            "verified-runtime requires the pinned qualification suite to exist "
            "on protected origin/main before the promotion change"
        ]
    if protected_suite != current_suite:
        return [
            "verified-runtime qualification suite differs from protected "
            "origin/main; land suite changes separately before promotion"
        ]

    try:
        completed = subprocess.run(
            [
                sys.executable,
                "-I",
                str(PINNED_RUNTIME_SUITE_PATH),
                "--runtime-root",
                str(candidate_root),
            ],
            cwd=candidate_root,
            env=_qualification_environment(candidate_root),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            timeout=RUNTIME_SUITE_TIMEOUT_SECONDS,
            text=True,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return [f"verified-runtime pinned qualification suite could not run: {exc}"]
    if completed.returncode != 0:
        first_line = (completed.stdout or "").strip().splitlines()
        detail = first_line[0] if first_line else "no diagnostic output"
        return [
            "verified-runtime pinned qualification suite failed "
            f"(exit {completed.returncode}): {detail}"
        ]
    return []


def main(*, runtime_root: Path = REPO_ROOT) -> int:
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
    if commands != REQUIRED_EVIDENCE_COMMANDS:
        errors.append(
            "evidence.testCommands must be exactly the action-contract manifest "
            "validator and its adversarial self-test"
        )
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
    claim_status = contract.get("claimStatus")
    if claim_status != "verified-runtime":
        if runtime_status != "roadmap":
            errors.append(
                "non-verified action contracts require "
                "execution.runtimeStatus=roadmap"
            )
        for field in RUNTIME_CLAIM_FIELDS:
            if execution.get(field) is not False:
                errors.append(
                    f"non-verified action contracts require execution.{field}=false"
                )
    if claim_status == "verified-runtime":
        if runtime_status != "live":
            errors.append("verified-runtime requires execution.runtimeStatus=live")
        for field in RUNTIME_CLAIM_FIELDS:
            if execution.get(field) is not True:
                errors.append(f"verified-runtime requires execution.{field}=true")
        errors.extend(validate_pinned_runtime_suite(runtime_root))
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
        "--runtime-root",
        type=Path,
        default=REPO_ROOT,
        help=(
            "Candidate checkout evaluated by the protected, digest-pinned "
            "runtime qualification suite."
        ),
    )
    args = parser.parse_args()
    sys.exit(main(runtime_root=args.runtime_root))
