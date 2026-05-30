#!/usr/bin/env python3
"""Validate the staged Hugging Face test-results manifest."""

from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "huggingface" / "test-results" / "MANIFEST.json"
BENCHMARK_MAP = REPO_ROOT / "benchmarks" / "benchmark-map.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    errors: list[str] = []
    manifest = load_json(MANIFEST_PATH)
    benchmark_map = load_json(BENCHMARK_MAP)

    publication = manifest.get("publication", {})
    if publication.get("repo_type") != "dataset":
        errors.append("publication.repo_type must be dataset")
    if publication.get("publish_mode") != "mirror-not-canonical":
        errors.append("publication.publish_mode must be mirror-not-canonical")
    if publication.get("canonical_source") != "https://github.com/szl-holdings/a11oy":
        errors.append("publication.canonical_source must point to a11oy GitHub")

    if manifest.get("claim_status") != "staged-no-live-score":
        errors.append("claim_status must remain staged-no-live-score until sealed results exist")

    disallowed = {claim.lower() for claim in manifest.get("disallowed_claims", [])}
    for phrase in ["solved the benchmark", "beat the benchmark", "agi proven", "hf is canonical"]:
        if phrase not in disallowed:
            errors.append(f"disallowed_claims missing {phrase!r}")

    allowed_text = " ".join(manifest.get("allowed_public_wording", [])).lower()
    for forbidden in ["cracked", "solved", "leaderboard"]:
        if forbidden in allowed_text:
            errors.append(f"allowed_public_wording contains unsupported word {forbidden!r}")

    benchmark_ref = manifest.get("benchmark_map", {})
    if benchmark_ref.get("path") != "benchmarks/benchmark-map.json":
        errors.append("benchmark_map.path must be benchmarks/benchmark-map.json")
    entry_id = benchmark_ref.get("entry_id")
    map_entry_ids = {entry.get("id") for entry in benchmark_map.get("entries", [])}
    if entry_id not in map_entry_ids:
        errors.append(f"benchmark_map.entry_id not found in benchmark map: {entry_id}")

    corpus = manifest.get("corpus", {})
    if corpus.get("sealed") is not False:
        errors.append("corpus.sealed must be false in staged manifest")
    if corpus.get("problem_text_included") is not False:
        errors.append("corpus.problem_text_included must be false")
    if int(corpus.get("problem_count", -1)) != 0:
        errors.append("corpus.problem_count must be 0 until corpus is sealed")

    runs = manifest.get("runs", [])
    if runs:
        errors.append("runs must be empty until a sealed receipt-backed run exists")

    # Guard against accidentally adding live-looking result/receipt files before
    # the benchmark doctrine gates are implemented.
    for forbidden_dir in [
        REPO_ROOT / "huggingface" / "test-results" / "results",
        REPO_ROOT / "huggingface" / "test-results" / "receipts",
    ]:
        if forbidden_dir.exists() and any(forbidden_dir.rglob("*")):
            errors.append(f"{forbidden_dir.relative_to(REPO_ROOT)} must remain empty in staged manifest")

    commands = manifest.get("validation", {}).get("commands", [])
    for command in ["npm run hf:test-results:audit", "npm run benchmark:audit"]:
        if command not in commands:
            errors.append(f"validation.commands missing {command}")

    if errors:
        print("HF test-results manifest validation failed:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print(f"Validated {MANIFEST_PATH.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
