#!/usr/bin/env python3
"""Refresh derived Brain-count contracts from the measured registry value."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "model_release/frontier-qualification/frontier-adoption.json"
SCHEMA = ROOT / "model_release/frontier-qualification/frontier-adoption.schema.json"
FRONTIER_TEST = ROOT / "tests/test_frontier_model_admission.py"
ESTATE_TEST = ROOT / "tests/test_model_intel_frontier_estate.py"
PROOF = ROOT / "docs/proofs/hf-source-brain-reconciliation-2026-08-31.json"


class ContractRefreshError(RuntimeError):
    """Raised when a derived count contract cannot be updated exactly."""


def _canonical_digest(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _replace_once(path: Path, pattern: str, replacement: str) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    matches = list(re.finditer(pattern, text, flags=re.MULTILINE))
    if len(matches) != 1:
        raise ContractRefreshError(
            f"expected one exact match in {path.relative_to(ROOT)}, found {len(matches)}: {pattern!r}"
        )
    previous = matches[0].group(0)
    updated, count = re.subn(pattern, lambda _match: replacement, text, count=1, flags=re.MULTILINE)
    if count != 1:
        raise ContractRefreshError(f"replacement failed for {path.relative_to(ROOT)}")
    path.write_text(updated, encoding="utf-8")
    return {
        "path": str(path.relative_to(ROOT)),
        "previous": previous.strip(),
        "current": replacement.strip(),
    }


def main() -> int:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    truth = registry.get("brain_model_truth")
    if not isinstance(truth, dict):
        raise ContractRefreshError("registry is missing brain_model_truth")
    observed = truth.get("raw_nodes_observed")
    available = truth.get("raw_nodes_available_to_retrieval_and_evaluation")
    if not isinstance(observed, int) or observed <= 0 or available != observed:
        raise ContractRefreshError(
            f"registry count is not a single positive measured value: observed={observed!r}, available={available!r}"
        )
    node_count = observed

    changes = [
        _replace_once(
            SCHEMA,
            r'"raw_nodes_observed": \{"const": \d+\}',
            f'"raw_nodes_observed": {{"const": {node_count}}}',
        ),
        _replace_once(
            SCHEMA,
            r'"raw_nodes_available_to_retrieval_and_evaluation": \{"const": \d+\}',
            f'"raw_nodes_available_to_retrieval_and_evaluation": {{"const": {node_count}}}',
        ),
        _replace_once(
            FRONTIER_TEST,
            r'^    assert brain\["raw_nodes_observed"\] == \d+$',
            f'    assert brain["raw_nodes_observed"] == {node_count}',
        ),
        _replace_once(
            ESTATE_TEST,
            r'^    assert registry\["brain_model_truth"\]\["raw_nodes_observed"\] == \d+$',
            f'    assert registry["brain_model_truth"]["raw_nodes_observed"] == {node_count}',
        ),
    ]

    proof = json.loads(PROOF.read_text(encoding="utf-8"))
    proof.pop("proof_sha256", None)
    proof["derived_count_contracts"] = {
        "measured_raw_nodes": node_count,
        "schema_constants_refreshed": True,
        "test_expectations_refreshed": True,
        "changes": changes,
    }
    proof["proof_sha256"] = _canonical_digest(proof)
    PROOF.write_text(
        json.dumps(proof, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "ok": True,
                "decision": "ALLOW",
                "measured_raw_nodes": node_count,
                "changes": changes,
                "proof_sha256": proof["proof_sha256"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
