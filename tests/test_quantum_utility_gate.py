# SPDX-License-Identifier: Apache-2.0
"""Fail-closed contracts for the proposal-only SZL Quantum Utility Gate."""

import copy
import hashlib

import pytest

import szl_quantum_utility as q


SHA_A = "a" * 64
SHA_B = "b" * 64


def _qubo(variable_count=2):
    variables = [f"x{i}" for i in range(variable_count)]
    return {
        "kind": "QUBO",
        "problem_id": "fixture-min-cut",
        "variables": variables,
        "offset": 0,
        "linear": {name: -1 for name in variables},
        "quadratic": ([{"left": "x0", "right": "x1", "coefficient": 2}] if variable_count > 1 else []),
    }


def _baseline():
    return q.run_with_receipt(
        "QUBO_EXACT_BASELINE", {"problem": _qubo(), "max_runtime_ms": 1_000}
    )["receipt"]


def _datum(value, label="MEASURED", unit="USD", source="fixture:1"):
    return {"value": value, "label": label, "unit": unit, "source_ref": source}


def _candidate(candidate_id, *, value=10, compute=1, accuracy=0.9, unknown=False):
    inputs = {
        "bounded_value_usd": _datum(value),
        "compute_cost_usd": _datum(compute),
        "queue_cost_usd": _datum(1),
        "energy_cost_usd": _datum(1),
        "verification_cost_usd": _datum(1),
        "operational_risk_cost_usd": _datum(1),
        "estimated_accuracy": _datum(accuracy, unit="ratio"),
    }
    if unknown:
        inputs["energy_cost_usd"] = _datum(None, label="UNKNOWN")
    return {
        "candidate_id": candidate_id,
        "backend_id": f"backend:{candidate_id}",
        "compile_plan_id": f"compiler:{candidate_id}",
        "inputs": inputs,
    }


def _claim(*, margin=4, task_digest=None):
    baseline = _baseline()
    task_digest = task_digest or baseline["input_sha256"]
    return {
        "claim_type": "QUANTUM_ADVANTAGE",
        "claim_id": "claim:fixture-1",
        "claim_owner": "operator:accountable-human",
        "classical_baseline_receipt": baseline,
        "quantum_observations": [
            {
                "run_id": f"qpu-external-{index}",
                "task_digest": task_digest,
                "backend_id": "external:declared-backend",
                "shots": 1_000,
                "raw_result_sha256": hashlib.sha256(str(index).encode()).hexdigest(),
                "label": "MEASURED",
            }
            for index in range(3)
        ],
        "uncertainty": {
            "label": "MEASURED",
            "method": "external repeated-run bootstrap",
            "source_ref": "external:measurement-bundle",
            "lower_margin_usd": 2,
            "upper_margin_usd": 6,
            "confidence": 0.95,
        },
        "provenance": [
            {"source_uri": "urn:external:run-bundle", "content_sha256": SHA_A, "observed_at": "2026-07-12T00:00:00Z"}
        ],
        "utility_margin": _datum(margin),
    }


def test_manifest_draws_hard_boundaries_and_keeps_finance_separate():
    out = q.info()
    assert out["mode"] == "PROPOSAL_ONLY"
    assert out["label"] == "STRUCTURAL-ONLY"
    assert out["effectors"] == out["provider_calls"] == out["qpu_calls"] == 0
    assert out["finance_quant_engine_imported"] is False
    assert out["existing_simulator_boundary"] == {
        "module": "szl_vqc.py",
        "label": "MODELED",
        "sim_kind": "SIMULATED",
        "used_as_hardware_evidence": False,
        "used_as_advantage_evidence": False,
    }


def test_exact_qubo_baseline_is_complete_small_and_deterministic():
    request = {"problem": _qubo(), "max_runtime_ms": 1_000}
    one = q.run_with_receipt("QUBO_EXACT_BASELINE", request)
    two = q.run_with_receipt("QUBO_EXACT_BASELINE", request)
    assert one == two
    assert one["result"]["states_evaluated"] == 4
    assert one["result"]["objective"] == -1
    assert one["result"]["assignment"] == {"x0": 0, "x1": 1}
    assert one["result"]["evidence_label"] == "MEASURED"
    assert one["result"]["measurement_scope"] == "deterministic classical computation"
    assert one["result"]["quantum_hardware_used"] is False


def test_qubo_contract_rejects_size_duplicates_unknowns_and_diagonal_terms():
    too_large = _qubo(q.MAX_QUBO_VARIABLES + 1)
    duplicate = {**_qubo(), "variables": ["x0", "x0"]}
    unknown = {**_qubo(), "linear": {"missing": 1}}
    diagonal = {**_qubo(), "quadratic": [{"left": "x0", "right": "x0", "coefficient": 1}]}
    for payload in [too_large, duplicate, unknown, diagonal]:
        with pytest.raises(q.ContractError):
            q.parse_qubo(payload)


def test_qubo_contract_rejects_hidden_fields_and_non_finite_numbers():
    with pytest.raises(q.ContractError):
        q.parse_qubo({**_qubo(), "provider": "hidden-call"})
    bad = _qubo()
    bad["linear"]["x0"] = float("nan")
    with pytest.raises(q.ContractError):
        q.parse_qubo(bad)


def test_hamiltonian_importance_and_largest_remainder_are_deterministic():
    request = {
        "hamiltonian": {
            "kind": "HAMILTONIAN",
            "problem_id": "h2-fixture",
            "qubit_count": 2,
            "terms": [
                {"term_id": "zz", "pauli": "ZZ", "coefficient": -2, "declared_priority": 1},
                {"term_id": "xi", "pauli": "XI", "coefficient": 1, "declared_priority": 1},
            ],
        },
        "shot_budget": 101,
    }
    one = q.allocate_hamiltonian_shots(request)
    two = q.allocate_hamiltonian_shots(request)
    assert one == two
    assert one["shots_allocated"] == 101
    assert one["allocation"][1]["importance"] == 4
    assert one["method_evidence_label"] == "DECLARED"
    assert one["scientific_optimality_claimed"] is False


def test_hamiltonian_zero_weights_still_allocates_every_term():
    out = q.allocate_hamiltonian_shots({
        "hamiltonian": {
            "kind": "HAMILTONIAN", "problem_id": "zero", "qubit_count": 1,
            "terms": [
                {"term_id": "a", "pauli": "I", "coefficient": 0, "declared_priority": 0},
                {"term_id": "b", "pauli": "Z", "coefficient": 0, "declared_priority": 0},
            ],
        },
        "shot_budget": 3,
    })
    assert [row["shots"] for row in out["allocation"]] == [2, 1]


def test_hamiltonian_contract_rejects_bad_paulis_and_underfunded_shots():
    bad = {
        "kind": "HAMILTONIAN", "problem_id": "bad", "qubit_count": 2,
        "terms": [{"term_id": "bad", "pauli": "ZAQ", "coefficient": 1, "declared_priority": 1}],
    }
    with pytest.raises(q.ContractError):
        q.parse_hamiltonian(bad)
    valid = {**bad, "terms": [
        {"term_id": "a", "pauli": "ZI", "coefficient": 1, "declared_priority": 1},
        {"term_id": "b", "pauli": "IZ", "coefficient": 1, "declared_priority": 1},
    ]}
    with pytest.raises(q.ContractError):
        q.allocate_hamiltonian_shots({"hamiltonian": valid, "shot_budget": 1})


def test_counterfactual_unknown_never_becomes_a_numeric_score():
    out = q.score_counterfactuals({"workload_digest": SHA_A, "candidates": [_candidate("unknown", unknown=True)]})
    row = out["candidates"][0]
    assert row["utility_margin_usd"] is None
    assert row["score_evidence_label"] == "UNKNOWN"
    assert row["unknown_inputs"] == ["energy_cost_usd"]
    assert out["pareto_front_candidate_ids"] == []
    assert out["universal_provider_ranking_claimed"] is False


def test_counterfactual_declared_input_keeps_score_declared():
    candidate = _candidate("declared")
    candidate["inputs"]["queue_cost_usd"]["label"] = "DECLARED"
    out = q.score_counterfactuals({"workload_digest": SHA_A, "candidates": [candidate]})
    assert out["candidates"][0]["utility_margin_usd"] == 5
    assert out["candidates"][0]["score_evidence_label"] == "DECLARED"


def test_counterfactual_pareto_front_is_workload_specific_and_deterministic():
    out = q.score_counterfactuals({
        "workload_digest": SHA_A,
        "candidates": [
            _candidate("dominated", value=9, compute=2, accuracy=0.8),
            _candidate("margin", value=12, compute=1, accuracy=0.8),
            _candidate("accuracy", value=10, compute=1, accuracy=0.99),
        ],
    })
    assert out["pareto_front_candidate_ids"] == ["accuracy", "margin"]


def test_counterfactual_requires_every_labeled_input_and_valid_accuracy():
    candidate = _candidate("missing")
    candidate["inputs"].pop("energy_cost_usd")
    with pytest.raises(q.ContractError):
        q.score_counterfactuals({"workload_digest": SHA_A, "candidates": [candidate]})
    invalid = _candidate("invalid", accuracy=1.1)
    with pytest.raises(q.ContractError):
        q.score_counterfactuals({"workload_digest": SHA_A, "candidates": [invalid]})


def test_receipt_replay_is_exact_and_tamper_evident():
    receipt = _baseline()
    assert q.replay_receipt(receipt)["valid"] is True
    tampered = copy.deepcopy(receipt)
    tampered["output"]["objective"] = 999
    check = q.replay_receipt(tampered)
    assert check["valid"] is False
    assert check["output_digest_valid"] is False
    assert check["replay_equal"] is False


def test_receipt_cannot_relabel_effectors_or_signature_state():
    for field, value in [("effectors", 1), ("provider_calls", 1), ("mode", "EXECUTE"), ("signature_state", "SIGNED")]:
        receipt = _baseline()
        receipt[field] = value
        with pytest.raises(q.ContractError):
            q.replay_receipt(receipt)


def test_advantage_gate_fails_closed_without_all_evidence():
    out = q.evaluate_advantage_claim({"claim_type": "QUANTUM_ADVANTAGE"})
    assert out["gate_passed"] is False
    assert out["evidence_state"] == "UNKNOWN"
    assert out["eligible_for_human_review"] is False
    assert len(out["reasons"]) >= 6


def test_advantage_gate_only_marks_complete_bundle_supported_for_review():
    out = q.evaluate_advantage_claim(_claim())
    assert out["gate_passed"] is True
    assert out["evidence_state"] == "SUPPORTED"
    assert out["eligible_for_human_review"] is True
    assert out["quantum_advantage_verified"] is False
    assert out["claim_authorized"] is False
    assert out["publication_authorized"] is False
    assert out["execution_authorized"] is False
    assert out["effectors"] == out["provider_calls"] == 0


def test_advantage_gate_rejects_nonpositive_margin_and_refutes_it():
    claim = _claim(margin=0)
    claim["uncertainty"]["lower_margin_usd"] = 0
    out = q.evaluate_advantage_claim(claim)
    assert out["gate_passed"] is False
    assert out["evidence_state"] == "REFUTED"
    assert any(reason.startswith("QUG-006") for reason in out["reasons"])


def test_advantage_gate_rejects_incomparable_or_duplicate_measurements():
    mismatch = _claim(task_digest=SHA_B)
    assert q.evaluate_advantage_claim(mismatch)["gate_passed"] is False
    duplicate = _claim()
    duplicate["quantum_observations"][1]["run_id"] = duplicate["quantum_observations"][0]["run_id"]
    assert q.evaluate_advantage_claim(duplicate)["gate_passed"] is False


def test_advantage_receipt_itself_is_deterministically_replayable():
    wrapped = q.run_with_receipt("QUANTUM_ADVANTAGE_GATE", _claim())
    assert wrapped["result"]["gate_passed"] is True
    assert q.replay_receipt(wrapped["receipt"])["valid"] is True
