#!/usr/bin/env python3
"""Validate the doctrine-safe benchmark map."""

from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_MAP = REPO_ROOT / "benchmarks" / "benchmark-map.json"
THEOREM_MANIFEST = REPO_ROOT / "docs" / "theorem-runtime-manifest.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    errors: list[str] = []
    data = load_json(BENCHMARK_MAP)
    theorem_manifest = load_json(THEOREM_MANIFEST)
    theorem_ids = {entry["id"] for entry in theorem_manifest.get("entries", [])}

    if data.get("publication", {}).get("publishMode") != "mirror-not-canonical":
        errors.append("publication.publishMode must be mirror-not-canonical")

    entries = data.get("entries")
    if not isinstance(entries, list) or not entries:
        errors.append("entries must be a non-empty list")
        entries = []

    for entry in entries:
        entry_id = entry.get("id", "<missing>")
        if "mathcomp" in entry_id.lower():
            scoring = entry.get("scoring", {})
            if scoring.get("scoreType") != "raw_points":
                errors.append(f"{entry_id}: competition-math benchmark entries must use raw_points")

            honesty = entry.get("honesty", {})
            disallowed = set(honesty.get("disallowedClaims", []))
            for phrase in ["solved the benchmark", "beat the benchmark", "AGI proven"]:
                if phrase not in disallowed:
                    errors.append(f"{entry_id}: disallowedClaims missing {phrase!r}")

            allowed_claim = honesty.get("allowedClaim", "").lower()
            if "cracked" in allowed_claim or "solved" in allowed_claim:
                errors.append(f"{entry_id}: allowedClaim contains unsupported benchmark language")

        corpus = entry.get("corpus", {})
        if corpus.get("sealed") and corpus.get("digestStatus") != "sealed":
            errors.append(f"{entry_id}: sealed corpus must have digestStatus=sealed")

        judges = entry.get("judges", [])
        judge_ids = {judge.get("id") for judge in judges}
        for required_judge in ["raw_grader", "proof_judge", "provenance_judge"]:
            if required_judge not in judge_ids:
                errors.append(f"{entry_id}: missing judge {required_judge}")

        receipts = entry.get("receipts", {})
        if receipts.get("required") is not True:
            errors.append(f"{entry_id}: receipts.required must be true")
        if receipts.get("chain") != "hash_chain":
            errors.append(f"{entry_id}: receipts.chain must be hash_chain")

        for route in entry.get("formulaRoutes", []):
            manifest_id = route.get("theoremRuntimeManifestId")
            if manifest_id not in theorem_ids:
                errors.append(f"{entry_id}: unknown formula route manifest ID {manifest_id}")

        gates = set(entry.get("ciGates", []))
        for gate in [
            "validate-benchmark-map",
            "verify-formula-routes",
            "reject-unsupported-benchmark-claims",
        ]:
            if gate not in gates:
                errors.append(f"{entry_id}: missing CI gate {gate}")

    if errors:
        print("Benchmark map validation failed:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print(f"Validated {BENCHMARK_MAP.relative_to(REPO_ROOT)} ({len(entries)} entries)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
