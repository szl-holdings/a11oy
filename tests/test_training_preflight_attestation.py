"""Truth-contract checks for the measured local Forge preflight refusal."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_training_preflight_is_bound_to_contract_and_remains_blocked() -> None:
    receipt = json.loads(
        (ROOT / "attestations/forge-training-preflight-local-2026-07-15.json")
        .read_text(encoding="utf-8")
    )
    contract = json.loads(
        (ROOT / "model_release/szl-forge/training-contract.json")
        .read_text(encoding="utf-8")
    )
    model = json.loads(
        (ROOT / "model_release/m1/operational-manifest.json")
        .read_text(encoding="utf-8")
    )

    assert receipt["state"] == "BLOCKED"
    assert receipt["contract_id"] == contract["contract_id"]
    immutable = receipt["checks"]["immutable_base"]
    assert immutable["revision"] == contract["base"]["revision"]
    expected_weight = next(
        item for item in model["base"]["files"]
        if item["path"] == "model.safetensors"
    )
    assert immutable["model_safetensors_sha256"] == expected_weight["sha256"]
    assert immutable["model_safetensors_bytes"] == expected_weight["bytes"]

    gpu = receipt["checks"]["gpu_admission"]
    assert gpu["state"] == "BLOCKED"
    assert gpu["memory_free_mib"] < gpu["minimum_free_memory_mib"]
    assert gpu["thresholds_may_be_weakened"] is False
    assert gpu["processes_may_be_stopped_automatically"] is False
    assert set(receipt["external_mutations"].values()) == {False}
