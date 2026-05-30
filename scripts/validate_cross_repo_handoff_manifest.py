#!/usr/bin/env python3
"""Validate the cross-repo handoff manifest."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = REPO_ROOT / "docs" / "cross-repo-handoff-manifest.json"
ACCESS = REPO_ROOT / "docs" / "github-enterprise-access-checklist.json"

ALLOWED_ACCESS_STATES = {"blocked-by-access", "write-ready"}
ALLOWED_HANDOFF_STATES = {
    "ready-for-owner-apply",
    "needs-target-runner",
    "blocked-by-access",
    "complete",
}
ALLOWED_CLAIM_STATUSES = {
    "verified-runtime",
    "release-payload",
    "lean-backed-needs-upstream-ci",
    "roadmap",
}
FORBIDDEN_COMPLETE_PHRASES = [
    "production-ready",
    "all green",
    "zero sorry",
    "catalog accepted",
    "endorsed",
    "deployed to target repo",
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    errors: list[str] = []
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    access = json.loads(ACCESS.read_text(encoding="utf-8"))
    target_repos = {entry["repo"] for entry in access.get("targetRepos", [])}

    rule = manifest.get("canonicalRule", "").lower()
    if "not complete until" not in rule or "target repo" not in rule:
        errors.append("canonicalRule must say handoffs are not complete until target repo evidence exists")

    forbidden_claims = {claim.lower() for claim in manifest.get("forbiddenClaims", [])}
    for phrase in FORBIDDEN_COMPLETE_PHRASES:
        if phrase not in forbidden_claims:
            errors.append(f"forbiddenClaims missing {phrase!r}")

    handoffs = manifest.get("handoffs", [])
    if not isinstance(handoffs, list) or not handoffs:
        errors.append("handoffs must be a non-empty list")
        handoffs = []

    seen: set[str] = set()
    required_fields = {
        "handoffId",
        "targetRepo",
        "targetBranch",
        "patchPath",
        "statusPath",
        "patchSha256",
        "accessState",
        "handoffState",
        "localValidation",
        "targetValidationRequired",
        "completionRequires",
        "claimStatus",
    }

    for handoff in handoffs:
        handoff_id = handoff.get("handoffId", "<missing>")
        if handoff_id in seen:
            errors.append(f"duplicate handoffId: {handoff_id}")
        seen.add(handoff_id)

        missing = sorted(required_fields - handoff.keys())
        if missing:
            errors.append(f"{handoff_id}: missing fields: {', '.join(missing)}")

        target_repo = handoff.get("targetRepo")
        if target_repo not in target_repos:
            errors.append(f"{handoff_id}: targetRepo not in access checklist: {target_repo}")

        if handoff.get("accessState") not in ALLOWED_ACCESS_STATES:
            errors.append(f"{handoff_id}: unsupported accessState {handoff.get('accessState')!r}")
        if handoff.get("handoffState") not in ALLOWED_HANDOFF_STATES:
            errors.append(f"{handoff_id}: unsupported handoffState {handoff.get('handoffState')!r}")
        if handoff.get("claimStatus") not in ALLOWED_CLAIM_STATUSES:
            errors.append(f"{handoff_id}: unsupported claimStatus {handoff.get('claimStatus')!r}")

        patch_path = REPO_ROOT / str(handoff.get("patchPath", ""))
        status_path = REPO_ROOT / str(handoff.get("statusPath", ""))
        if not patch_path.exists():
            errors.append(f"{handoff_id}: patchPath does not exist: {handoff.get('patchPath')}")
        else:
            actual = sha256_file(patch_path)
            if actual != handoff.get("patchSha256"):
                errors.append(f"{handoff_id}: patchSha256 mismatch: expected {handoff.get('patchSha256')}, got {actual}")
        if not status_path.exists():
            errors.append(f"{handoff_id}: statusPath does not exist: {handoff.get('statusPath')}")

        for list_field in ["localValidation", "targetValidationRequired", "completionRequires"]:
            if not isinstance(handoff.get(list_field), list) or not handoff.get(list_field):
                errors.append(f"{handoff_id}: {list_field} must be a non-empty list")

        if handoff.get("handoffState") == "complete":
            completion = " ".join(handoff.get("completionRequires", [])).lower()
            if "target ci green" not in completion or "target pr" not in completion:
                errors.append(f"{handoff_id}: complete handoff requires target PR and target CI evidence")

        if target_repo == "szl-holdings/lutar-lean":
            target_validation = " ".join(handoff.get("targetValidationRequired", [])).lower()
            if "lake build" not in target_validation:
                errors.append(f"{handoff_id}: lutar-lean handoff must require lake build")

    if errors:
        print("Cross-repo handoff manifest validation failed:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print(f"Validated {MANIFEST.relative_to(REPO_ROOT)} ({len(handoffs)} handoffs)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
