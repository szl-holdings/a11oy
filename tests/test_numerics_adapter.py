# SPDX-License-Identifier: Apache-2.0
"""Unit contract for the fail-closed numerical-engine frontier."""

import json
from pathlib import Path

import pytest

import szl_numerics_adapter as adapter


def request(operation="MATRIX_SOLVE"):
    inputs = {"matrix": [[2, 0], [0, 4]], "rhs": [2, 8]}
    if operation == "SYMMETRIC_EIGENVALUES":
        inputs = {"matrix": [[2, 0], [0, 4]]}
    if operation == "VALIDATE_REFERENCE_VECTOR":
        inputs["expected"] = [1, 2]
    return {
        "schema": adapter.REQUEST_SCHEMA,
        "request_id": "fixture-1",
        "operation": operation,
        "inputs": inputs,
        "tolerance": {"absolute": 1e-9, "relative": 1e-9},
    }


def response(operation, values):
    return {
        "schema": adapter.ENGINE_RESPONSE_SCHEMA,
        "state": "RESULT",
        "operation": operation,
        "values": values,
        "substrate_evidence": "UNKNOWN",
    }


def executor(values):
    return lambda parsed: response(parsed["operation"], values)


def test_parser_accepts_only_the_three_fixed_operations_and_strict_fields():
    assert adapter.parse_request(request())["operation"] == "MATRIX_SOLVE"
    assert adapter.parse_request(request("SYMMETRIC_EIGENVALUES"))["operation"] == "SYMMETRIC_EIGENVALUES"
    assert adapter.parse_request(request("VALIDATE_REFERENCE_VECTOR"))["operation"] == "VALIDATE_REFERENCE_VECTOR"

    hidden = request()
    hidden["code"] = "system('curl example.com')"
    with pytest.raises(adapter.ContractError, match="unsupported fields"):
        adapter.parse_request(hidden)

    arbitrary = request()
    arbitrary["operation"] = "EVAL"
    with pytest.raises(adapter.ContractError, match="operation must be"):
        adapter.parse_request(arbitrary)


def test_numeric_schema_rejects_nonfinite_oversize_nonsquare_and_nonsymmetric():
    nonfinite = request()
    nonfinite["inputs"]["matrix"][0][0] = float("nan")
    with pytest.raises(adapter.ContractError, match="finite"):
        adapter.parse_request(nonfinite)

    nonsquare = request()
    nonsquare["inputs"]["matrix"] = [[1, 2], [3]]
    with pytest.raises(adapter.ContractError, match="exactly 2"):
        adapter.parse_request(nonsquare)

    nonsymmetric = request("SYMMETRIC_EIGENVALUES")
    nonsymmetric["inputs"]["matrix"] = [[1, 2], [0, 1]]
    with pytest.raises(adapter.ContractError, match="symmetric"):
        adapter.parse_request(nonsymmetric)


def test_engine_result_and_receipt_are_deterministic_unsigned_and_zero_uplift():
    first = adapter.run_engine("octave", request(), executor=executor([1, 2]))
    second = adapter.run_engine("octave", request(), executor=executor([1, 2]))
    assert first == second
    assert first["state"] == "RESULT"
    assert first["substrate_evidence"] == "UNKNOWN"
    assert first["proof_uplift"] == first["trust_uplift"] == 0
    assert first["receipt"]["signature_state"] == "UNSIGNED_DETERMINISTIC_DIGEST_ONLY"
    assert first["receipt"]["proof_uplift"] == first["receipt"]["trust_uplift"] == 0


def test_reference_vector_validation_is_match_or_conflict_without_uplift():
    matched = adapter.run_engine(
        "octave", request("VALIDATE_REFERENCE_VECTOR"), executor=executor([1 + 1e-12, 2])
    )
    conflict = adapter.run_engine(
        "octave", request("VALIDATE_REFERENCE_VECTOR"), executor=executor([1.1, 2])
    )
    assert matched["reference_validation"] == "MATCH"
    assert conflict["reference_validation"] == "CONFLICT"
    assert conflict["proof_uplift"] == conflict["trust_uplift"] == 0


def test_cross_engine_match_and_conflict_follow_declared_tolerance():
    matched = adapter.compare_engines(
        request(), executors={"octave": executor([1, 2]), "matlab": executor([1 + 1e-12, 2])}
    )
    conflict = adapter.compare_engines(
        request(), executors={"octave": executor([1, 2]), "matlab": executor([1.01, 2])}
    )
    assert matched["comparison_state"] == "MATCH"
    assert conflict["comparison_state"] == "CONFLICT"
    assert matched["proof_uplift"] == matched["trust_uplift"] == 0
    assert conflict["receipt"]["signature_state"] == "UNSIGNED_DETERMINISTIC_DIGEST_ONLY"


def test_default_status_is_honest_and_never_imports_or_bundles_engines():
    status = adapter.engine_status()
    assert status["mode"] == "EXTERNAL_ENGINES_ONLY"
    assert status["substrate_evidence"] == "UNKNOWN"
    assert status["engines"]["octave"]["license_boundary"] == "EXTERNAL_GPL_PROCESS_NOT_BUNDLED"
    assert status["engines"]["matlab"]["license_boundary"] == "EXTERNAL_PROPRIETARY_SERVICE_NOT_BUNDLED"
    assert status["engines"]["matlab"]["python_engine_package"] in (
        "PRESENT_STATUS_ONLY_NOT_IMPORTED", "SOURCE_UNAVAILABLE"
    )
    assert status["controls"]["package_installs"] == "DISABLED"
    assert status["controls"]["arbitrary_code"] == "DISABLED"
    assert status["proof_uplift"] == status["trust_uplift"] == 0


def test_no_external_engine_is_executed_when_posix_isolation_is_unavailable(monkeypatch):
    monkeypatch.setattr(adapter.os, "name", "nt")
    result = adapter.run_engine("octave", request())
    assert result["state"] == "UNAVAILABLE"
    assert result["reason"] == "POSIX_RESOURCE_AND_NETWORK_ISOLATION_UNAVAILABLE"
    assert result["receipt"]["signature_state"] == "UNSIGNED_DETERMINISTIC_DIGEST_ONLY"


def test_fixed_octave_script_contains_no_dynamic_or_network_effectors():
    source = (Path(__file__).resolve().parents[1] / "numerics" / "octave_adapter.m").read_text(encoding="utf-8")
    lowered = source.lower()
    for forbidden in ("eval(", "source(", "system(", "urlread(", "webread(", "pkg install"):
        assert forbidden not in lowered
    assert "matrix \\ request.inputs.rhs" in source
    assert "sort(eig(matrix))" in source


def test_published_json_contract_is_strict_and_matches_runtime_schemas():
    contract = json.loads((Path(__file__).resolve().parents[1] / "numerics" / "contract.json").read_text(encoding="utf-8"))
    assert contract["request_schema"]["additionalProperties"] is False
    assert contract["engine_response_schema"]["additionalProperties"] is False
    assert set(contract["request_schema"]["properties"]["operation"]["enum"]) == set(adapter.OPERATIONS)
    assert {"code", "expression", "function", "command", "package", "url"} <= set(contract["prohibited_fields"])


def test_canonical_payload_has_no_nan_or_hidden_dynamic_content():
    normalized = adapter.parse_request(request())
    encoded = adapter.canonical_json(normalized)
    assert json.loads(encoded) == normalized
    assert b"code" not in encoded and b"command" not in encoded
