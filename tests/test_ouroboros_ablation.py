from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "benchmarks" / "ouroboros_ablation" / "protocol-v0.1.0.json"
RUNNER = ROOT / "scripts" / "run_ouroboros_ablation.py"


def _load_runner():
    spec = importlib.util.spec_from_file_location("run_ouroboros_ablation", RUNNER)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_protocol_is_preregistered_and_non_promoting():
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    assert protocol["schema"] == "szl.ouroboros-governance-ablation/v1"
    assert protocol["status"] == "PREREGISTERED_LOCAL"
    assert len(protocol["scenarios"]) == 4
    assert {row["expected_decision"] for row in protocol["scenarios"]} == {"ALLOW", "DENY"}
    assert "task accuracy" in protocol["scope"]["not_measured"]
    assert "mathematical convergence" in protocol["scope"]["not_measured"]
    controls = {row["id"]: row for row in protocol["variants"]}
    assert controls["gate_removed_negative_control"]["kind"] == "proposal_only_simulation"
    assert controls["self_feed_removed_trace_ablation"]["kind"] == "evidence_removal"


def test_independent_chain_verifier_detects_body_mutation():
    runner = _load_runner()
    body = {"iteration": 0, "decision": "ALLOW"}
    entry = {"seq": 0, "kind": "cycle_iteration", "body": body, "prev_hash": "GENESIS"}
    entry["hash"] = runner._sha(entry)
    chain = [entry]
    assert runner.verify_cycle_chain(chain)
    mutated = copy.deepcopy(chain)
    mutated[0]["body"]["decision"] = "DENY"
    assert not runner.verify_cycle_chain(mutated)


@pytest.mark.filterwarnings("ignore")
def test_preregistered_ablation_passes_against_real_routes():
    pytest.importorskip("starlette.testclient")
    runner = _load_runner()
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    import serve
    from starlette.testclient import TestClient

    with TestClient(serve.app) as client:
        result = runner.run_protocol(protocol, client)
    acceptance = runner.evaluate_acceptance(protocol, result["metrics"])
    assert acceptance["passed"], acceptance
    assert result["metrics"]["task_accuracy_measured"] is False
    assert result["metrics"]["operational_outcomes_measured"] is False
    assert result["metrics"]["mathematical_convergence_claimed"] is False
