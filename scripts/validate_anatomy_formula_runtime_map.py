#!/usr/bin/env python3
"""Validate the anatomy/formula/runtime map.

The validator is intentionally lightweight and offline. It verifies that the
map has the expected structure, that referenced theorem-runtime IDs exist, and
that active local runtime/test paths are present in this checkout.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MAP_PATH = REPO_ROOT / "docs" / "anatomy-formula-runtime-map.json"
THEOREM_MANIFEST_PATH = REPO_ROOT / "docs" / "theorem-runtime-manifest.json"

ALLOWED_CLAIM_STATUSES = {
    "verified-runtime",
    "release-payload",
    "lean-backed-current-green",
    "lean-backed-needs-upstream-ci",
    "lean-backed-needs-runtime",
    "thesis-anchor",
    "historical",
    "historical-roadmap",
    "roadmap",
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    errors: list[str] = []
    data = load_json(MAP_PATH)
    theorem_manifest = load_json(THEOREM_MANIFEST_PATH)
    theorem_ids = {entry["id"] for entry in theorem_manifest.get("entries", [])}

    required_top = {
        "schemaVersion",
        "generatedBy",
        "observedAt",
        "canonicalHub",
        "canonicalRule",
        "autonomousLearningDoctrine",
        "organs",
    }
    missing_top = sorted(required_top - data.keys())
    if missing_top:
        errors.append(f"missing top-level fields: {', '.join(missing_top)}")

    if data.get("canonicalHub") != "a11oy":
        errors.append("canonicalHub must be a11oy")

    doctrine = data.get("autonomousLearningDoctrine", {})
    if doctrine.get("promotionModel") != "human_promotion_required":
        errors.append("autonomousLearningDoctrine.promotionModel must require human promotion")
    forbidden_modes = set(doctrine.get("forbiddenModes", []))
    for mode in ["self_approve", "self_promote", "deploy", "publish"]:
        if mode not in forbidden_modes:
            errors.append(f"autonomousLearningDoctrine.forbiddenModes missing {mode}")

    organs = data.get("organs", [])
    if not isinstance(organs, list) or not organs:
        errors.append("organs must be a non-empty list")

    repos = set()
    required_organ = {
        "repo",
        "anatomyRole",
        "formulaRuntime",
        "theoremAnchors",
        "receiptSurface",
        "testEvidence",
        "udsStage",
        "hfStage",
        "claimStatus",
        "autonomousLearningRole",
        "gaps",
    }

    for organ in organs:
        repo = organ.get("repo", "<missing>")
        if repo in repos:
            errors.append(f"duplicate organ repo: {repo}")
        repos.add(repo)

        missing = sorted(required_organ - organ.keys())
        if missing:
            errors.append(f"{repo}: missing fields: {', '.join(missing)}")

        status = organ.get("claimStatus")
        if status not in ALLOWED_CLAIM_STATUSES:
            errors.append(f"{repo}: unsupported claimStatus {status!r}")

        for collection_name in [
            "formulaRuntime",
            "theoremAnchors",
            "receiptSurface",
            "testEvidence",
            "gaps",
        ]:
            if not isinstance(organ.get(collection_name), list):
                errors.append(f"{repo}: {collection_name} must be a list")

        for formula in organ.get("formulaRuntime", []):
            formula_status = formula.get("claimStatus")
            if formula_status not in ALLOWED_CLAIM_STATUSES:
                errors.append(
                    f"{repo}/{formula.get('formula', '<formula>')}: unsupported claimStatus {formula_status!r}"
                )

            manifest_id = formula.get("theoremRuntimeManifestId")
            if manifest_id is not None and manifest_id not in theorem_ids:
                errors.append(
                    f"{repo}/{formula.get('formula', '<formula>')}: unknown theoremRuntimeManifestId {manifest_id}"
                )

            runtime_file = formula.get("runtimeFile")
            if runtime_file and not (REPO_ROOT / runtime_file).exists():
                errors.append(
                    f"{repo}/{formula.get('formula', '<formula>')}: runtimeFile does not exist: {runtime_file}"
                )

    required_repos = {"a11oy", "lutar-lean", "ouroboros-thesis", "agi-forecast"}
    missing_repos = sorted(required_repos - repos)
    if missing_repos:
        errors.append(f"missing required organ repos: {', '.join(missing_repos)}")

    if errors:
        print("Anatomy/formula/runtime map validation failed:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print(f"Validated {MAP_PATH.relative_to(REPO_ROOT)} ({len(organs)} organs)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
