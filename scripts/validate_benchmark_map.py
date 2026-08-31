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

        if entry_id == "governed-agent-bench-v0":
            honesty = entry.get("honesty", {})
            disallowed = set(honesty.get("disallowedClaims", []))
            if "eligible model leaderboard results published" not in disallowed:
                errors.append(
                    f"{entry_id}: disallowedClaims must preserve the zero-model-results boundary"
                )
            if "public leaderboard published" in disallowed:
                errors.append(
                    f"{entry_id}: published reference leaderboard contradicts disallowedClaims"
                )

            publication = entry.get("publication", {})
            if publication.get("state") != "PUBLISHED_PROTECTED":
                errors.append(f"{entry_id}: publication.state must be PUBLISHED_PROTECTED")
            for field in ("dataset", "space"):
                if publication.get(field) != "SZLHOLDINGS/governed-agent-bench":
                    errors.append(
                        f"{entry_id}: publication.{field} must name the governed-agent-bench Hub repository"
                    )
            first_verified = publication.get("firstVerified", {})
            for field in ("sourceRevision", "datasetRevision", "spaceRevision"):
                revision = first_verified.get(field)
                if (
                    not isinstance(revision, str)
                    or len(revision) != 40
                    or any(ch not in "0123456789abcdef" for ch in revision)
                ):
                    errors.append(
                        f"{entry_id}: publication.firstVerified.{field} must be a 40-character lowercase hex revision"
                    )
            if first_verified.get("workflowRun") != (
                "https://github.com/szl-holdings/a11oy/actions/runs/30382562989"
            ):
                errors.append(
                    f"{entry_id}: publication.firstVerified.workflowRun must preserve the observed protected run"
                )
            if first_verified.get("status") != "VERIFIED_IMMUTABLE_READBACK":
                errors.append(
                    f"{entry_id}: publication.firstVerified.status must be VERIFIED_IMMUTABLE_READBACK"
                )
            truth_boundary = str(publication.get("truthBoundary", "")).lower()
            for phrase in ("zero eligible model submissions", "not a model ranking"):
                if phrase not in truth_boundary:
                    errors.append(
                        f"{entry_id}: publication.truthBoundary missing {phrase!r}"
                    )

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
        for route in entry.get("formulaRoutes", []):
            manifest_id = route.get("theoremRuntimeManifestId")
            if manifest_id not in theorem_ids:
                errors.append(f"{entry_id}: unknown formula route manifest ID {manifest_id}")

        gates = set(entry.get("ciGates", []))
        receipt_chain = receipts.get("chain")
        if receipt_chain not in {"hash_chain", "not_verified"}:
            errors.append(
                f"{entry_id}: receipts.chain must be hash_chain or not_verified"
            )
        if receipt_chain == "hash_chain" and "verify-receipt-chain" not in gates:
            errors.append(
                f"{entry_id}: hash_chain receipts require verify-receipt-chain"
            )
        if receipt_chain == "not_verified" and "verify-receipt-chain" in gates:
            errors.append(
                f"{entry_id}: unverified receipts cannot claim verify-receipt-chain"
            )
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
