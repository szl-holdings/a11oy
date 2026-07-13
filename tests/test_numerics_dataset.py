# SPDX-License-Identifier: Apache-2.0
import hashlib
import json
from pathlib import Path

import pytest

import szl_numerics_dataset as dataset


def _case(operation="MATRIX_SOLVE", family="DIAGONAL_GEOMETRIC"):
    listed = dataset.list_cases(limit=100, family=family, operation=operation)
    assert listed["items"]
    return dataset.get_case(listed["items"][0]["case_id"])


def _payload(case, engine="octave", values=None, run_id="run-001", *, network="DENIED", reference=None):
    if values is None:
        values = case["construction_reference"].get("values", [0.0] * case["dimension"])
    return {
        "schema": dataset.INGEST_SCHEMA,
        "run_id": run_id,
        "case_id": case["case_id"],
        "engine": engine,
        "outcome": {"state": "RESULT", "values": values},
        "engine_evidence": {
            "version": "test-engine 1.0",
            "version_evidence_sha256": "a" * 64,
            "executable_sha256": "b" * 64,
            "license_state": "OPERATOR_REVIEWED",
            "offline_license_state": "CONFIGURED" if engine == "matlab" else "NOT_APPLICABLE",
        },
        "containment": {"network_state": network, "evidence_sha256": "c" * 64 if network == "DENIED" else None},
        "resources": {
            "wall_time_ns": 1200,
            "child_user_cpu_ns": None,
            "child_system_cpu_ns": None,
            "peak_resident_bytes": None,
            "request_bytes": 100,
            "response_bytes": 80,
            "log_bytes": 0,
        },
        "reference": reference or {"state": "SOURCE_UNAVAILABLE"},
        "observed_at_utc": "2026-07-12T12:00:00Z",
    }


def test_preregistration_and_case_index_are_exact_and_result_free():
    manifest = dataset.preregistration()
    assert manifest["matrix_dimensions"] == [2, 4, 8, 16, 32, 64]
    assert manifest["deterministic_seeds"] == [1729, 57721, 271828, 314159, 1618033]
    assert [item["id"] for item in manifest["condition_number_strata"]] == ["K0", "K4", "K8", "K12"]
    assert dataset.list_cases(limit=1)["total"] == 1328
    assert manifest["results_present"] is False
    assert manifest["evidence_boundary"]["proof_uplift"] == 0
    assert manifest["evidence_boundary"]["trust_uplift"] == 0


def test_fixture_generation_is_deterministic_and_operation_shaped():
    solve = _case("MATRIX_SOLVE", "SPD_GIVENS")
    repeated = dataset.get_case(solve["case_id"])
    assert solve == repeated
    assert solve["fixture_sha256"] == repeated["fixture_sha256"]
    assert solve["request"]["operation"] == "MATRIX_SOLVE"
    assert set(solve["request"]["inputs"]) == {"matrix", "rhs"}
    assert solve["primary_reference"] == {"state": "SOURCE_UNAVAILABLE"}
    assert solve["condition_number_reference"] == {"state": "NOT_EVALUATED"}
    matrix = solve["request"]["inputs"]["matrix"]
    assert all(matrix[row][column] == pytest.approx(matrix[column][row], abs=1e-12) for row in range(len(matrix)) for column in range(len(matrix)))

    eigen = _case("SYMMETRIC_EIGENVALUES", "DIAGONAL_GEOMETRIC")
    assert set(eigen["request"]["inputs"]) == {"matrix"}
    assert eigen["construction_reference"] == {"state": "NOT_APPLICABLE"}

    general = _case("MATRIX_SOLVE", "GENERAL_SVD_GIVENS")
    assert general["symmetric"] is False
    assert general["request_sha256"] == hashlib.sha256(
        json.dumps(general["request"], sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
    ).hexdigest()


def test_append_only_ingestion_computes_diagnostics_and_cross_engine_states(tmp_path, monkeypatch):
    monkeypatch.setenv("A11OY_NUMERICS_DATASET_LEDGER", str(tmp_path / "runs.ndjson"))
    case = _case()
    expected = case["construction_reference"]["values"]

    first = dataset.ingest_result(_payload(case, "octave", expected, "run-octave"))
    assert first["row_state"] == "RESULT"
    assert first["comparison_state"] == "NOT_EVALUATED"
    assert first["diagnostics"]["quality_gate"] == "PASS"
    assert first["diagnostics"]["absolute_residual_norm2"] == pytest.approx(0.0)
    assert first["evidence_label"] == "MEASURED"
    assert first["proof_uplift"] == first["trust_uplift"] == 0

    second = dataset.ingest_result(_payload(case, "matlab", expected, "run-matlab"))
    assert second["comparison_state"] == "MATCH"
    assert second["compared_to_run_id"] == "run-octave"
    assert second["previous_row_sha256"] == first["row_sha256"]

    rows = dataset.list_results(limit=10)
    assert rows["total"] == 2
    assert [item["sequence"] for item in rows["items"]] == [2, 1]
    with pytest.raises(dataset.DatasetContractError, match="already exists"):
        dataset.ingest_result(_payload(case, "matlab", expected, "run-matlab"))


def test_conflict_unavailable_and_missing_network_evidence_never_become_match(tmp_path, monkeypatch):
    monkeypatch.setenv("A11OY_NUMERICS_DATASET_LEDGER", str(tmp_path / "runs.ndjson"))
    case = _case()
    expected = case["construction_reference"]["values"]
    dataset.ingest_result(_payload(case, "octave", expected, "run-good"))

    conflict = dataset.ingest_result(_payload(case, "matlab", [0.0] * case["dimension"], "run-conflict"))
    assert conflict["comparison_state"] == "CONFLICT"
    assert conflict["diagnostics"]["quality_gate"] == "FAIL"

    refused = dataset.ingest_result(_payload(case, "octave", expected, "run-no-net", network="UNKNOWN"))
    assert refused["row_state"] == "REFUSED"
    assert refused["comparison_state"] == "REFUSED"
    assert refused["reason"] == "NETWORK_DENIAL_EVIDENCE_UNAVAILABLE"
    assert refused["values"] is None
    assert refused["evidence_label"] == "UNKNOWN"

    unavailable_payload = _payload(case, "matlab", expected, "run-unavailable")
    unavailable_payload["outcome"] = {"state": "UNAVAILABLE", "reason": "ENGINE_OR_ISOLATION_CONTROL_UNAVAILABLE"}
    unavailable = dataset.ingest_result(unavailable_payload)
    assert unavailable["row_state"] == "UNAVAILABLE"
    assert unavailable["comparison_state"] == "UNAVAILABLE"
    assert unavailable["values"] is None
    assert unavailable["diagnostics"] is None


def test_forward_error_is_only_computed_with_pinned_primary_reference(tmp_path, monkeypatch):
    monkeypatch.setenv("A11OY_NUMERICS_DATASET_LEDGER", str(tmp_path / "runs.ndjson"))
    case = _case()
    expected = case["construction_reference"]["values"]
    measured_reference = {
        "state": "MEASURED",
        "implementation": "PYTHON_MPMATH_100DP",
        "values": expected,
        "evidence_sha256": "d" * 64,
    }
    row = dataset.ingest_result(_payload(case, values=expected, run_id="run-reference", reference=measured_reference))
    assert row["diagnostics"]["reference_state"] == "REFERENCE_MATCH"
    assert row["diagnostics"]["forward_error"] == pytest.approx(0.0)
    assert row["reference"] == {
        "state": "MEASURED",
        "implementation": "PYTHON_MPMATH_100DP",
        "evidence_sha256": "d" * 64,
    }


def test_status_separates_local_runtime_from_ingested_rows(tmp_path, monkeypatch):
    monkeypatch.setenv("A11OY_NUMERICS_DATASET_LEDGER", str(tmp_path / "runs.ndjson"))
    monkeypatch.delenv("A11OY_NUMERICS_DATASET_INGEST_TOKEN_SHA256", raising=False)
    monkeypatch.setattr(dataset._adapter, "engine_status", lambda: {
        "engines": {"octave": {"execution_state": "UNAVAILABLE"}, "matlab": {"execution_state": "UNAVAILABLE"}},
        "controls": {"network_isolation": "SOURCE_UNAVAILABLE"},
    })
    status = dataset.dataset_status()
    assert status["service_state"] == "READY"
    assert status["preregistration"]["case_count"] == 1328
    assert status["result_ledger"]["row_count"] == 0
    assert status["result_ledger"]["ingest_gate"] == "UNAVAILABLE"
    assert status["local_runtime"] == {
        "octave": "UNAVAILABLE",
        "matlab": "UNAVAILABLE",
        "network_isolation": "SOURCE_UNAVAILABLE",
        "network_denial_evidence": "NOT_EVALUATED",
        "substrate_evidence": "UNKNOWN",
    }


def test_contract_files_are_strict_and_do_not_claim_engine_bundling():
    root = Path(__file__).resolve().parents[1]
    schema = json.loads((root / "numerics" / "dataset-contract.json").read_text(encoding="utf-8"))
    manifest = json.loads((root / "numerics" / "dataset_preregistration.json").read_text(encoding="utf-8"))
    assert schema["additionalProperties"] is False
    assert schema["properties"]["outcome"]["oneOf"][0]["additionalProperties"] is False
    assert manifest["state"] == "FROZEN_INPUT_DESIGN_NO_ENGINE_RESULTS"
    assert manifest["evidence_boundary"]["local_engine_execution"] == "DEPENDENT_ON_RUNTIME_PREFLIGHT"


def test_formula_curriculum_accounts_for_all_ids_without_proof_uplift():
    curriculum = dataset.formula_curriculum()
    assert curriculum["schema"] == dataset.CURRICULUM_SCHEMA
    assert curriculum["counts"]["expected"] == 23
    assert curriculum["counts"]["eligible"] + curriculum["counts"]["quarantined"] == 23
    assert curriculum["formula_contract"]["locked_proven_ids"] == [
        "F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22",
    ]
    by_id = {item["formula_id"]: item for item in curriculum["eligible"]}
    assert set(by_id) == {f"F{index}" for index in range(1, 24)}
    assert {item["formula_id"] for item in curriculum["eligible"] if item["proof_status"] == "PROVED"} == {
        "F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22",
    }
    assert by_id["F23"]["proof_status"] == "CONJECTURE_1"
    assert by_id["F23"]["claim_scope"] == "CONJECTURE_1_OPEN_NOT_A_THEOREM"
    assert all(item["proof_receipt_sha256"] is None for item in curriculum["eligible"])
    assert all(item["refutation_receipt_sha256"] is None for item in curriculum["eligible"])
    assert all(item["proof_uplift"] == item["trust_uplift"] == 0 for item in curriculum["eligible"])
    family_splits = {}
    for item in curriculum["eligible"]:
        family_splits.setdefault(item["source_family"], set()).add(item["split"])
    assert all(len(splits) == 1 for splits in family_splits.values())
