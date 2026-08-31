# SPDX-License-Identifier: Apache-2.0

import json
from pathlib import Path

import pytest

import szl_numerics_experiment as experiment


def _blocked_status():
    return {
        "engines": {
            "octave": {"execution_state": "UNAVAILABLE", "executable_path": None},
            "matlab": {
                "execution_state": "UNAVAILABLE",
                "service_executable_path": None,
                "offline_license_configuration": "SOURCE_UNAVAILABLE",
            },
        },
        "controls": {
            "network_isolation": "SOURCE_UNAVAILABLE",
            "network_launcher": None,
            "resource_limits": "SOURCE_UNAVAILABLE",
            "memory_limit_bytes": 536870912,
            "output_limit_bytes": 262144,
            "timeout_limit_seconds": 8,
        },
    }


def test_plan_is_the_exact_frozen_1328_case_design():
    plan = experiment.experiment_plan()
    assert plan["frozen_before_execution"] is True
    assert plan["dimensions"] == [2, 4, 8, 16, 32, 64]
    assert plan["seeds"] == [1729, 57721, 271828, 314159, 1618033]
    assert [item["id"] for item in plan["condition_number_strata"]] == ["K0", "K4", "K8", "K12"]
    assert plan["case_counts"] == {"confirmatory": 1320, "exploratory": 8, "total": 1328}
    assert plan["planned_engine_runs"] == 2656
    assert plan["result_claim"] == "NO_ENGINE_RESULT_IN_PLAN"


def test_evidence_child_environment_is_fixed_and_secret_free(tmp_path):
    assert experiment._child_env(tmp_path) == {
        "HOME": str(tmp_path),
        "TMPDIR": str(tmp_path),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PATH": "/usr/bin:/bin",
    }


def test_preflight_blocks_missing_engines_controls_reference_and_reviews():
    receipt = experiment.preflight(
        status=_blocked_status(),
        environ={},
        os_name="nt",
        mpmath_status={"state": "UNAVAILABLE", "version": None},
    )
    assert receipt["state"] == "BLOCKED"
    assert receipt["engine_invocations"] == receipt["result_rows"] == 0
    assert receipt["network_denial_evidence"] == "NOT_EVALUATED"
    assert receipt["substrate_evidence"] == "UNKNOWN"
    assert receipt["proof_uplift"] == receipt["trust_uplift"] == 0
    assert receipt["blockers"] == sorted(receipt["blockers"])
    assert {
        "POSIX_RESOURCE_AND_NETWORK_ISOLATION_UNAVAILABLE",
        "NETWORK_NAMESPACE_LAUNCHER_UNAVAILABLE",
        "POSIX_RESOURCE_LIMITS_UNAVAILABLE",
        "OCTAVE_ENGINE_UNAVAILABLE",
        "MATLAB_ENGINE_UNAVAILABLE",
        "OCTAVE_LICENSE_REVIEW_UNAVAILABLE",
        "MATLAB_LICENSE_REVIEW_UNAVAILABLE",
        "MPMATH_100DP_REFERENCE_UNAVAILABLE",
    }.issubset(set(receipt["blockers"]))


def test_blocked_run_never_calls_engine_or_claims_results(monkeypatch):
    blocked = experiment.preflight(
        status=_blocked_status(),
        environ={},
        os_name="nt",
        mpmath_status={"state": "UNAVAILABLE", "version": None},
    )
    monkeypatch.setattr(experiment, "preflight", lambda: blocked)
    monkeypatch.setattr(experiment._adapter, "run_engine", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("engine called")))
    receipt = experiment.run_preregistered(execute_all=True)
    assert receipt["state"] == "BLOCKED"
    assert receipt["engine_invocations"] == 0
    assert receipt["result_rows"] == 0
    assert receipt["pair_outcomes"] == {"MATCH": 0, "CONFLICT": 0, "UNAVAILABLE": 0}
    assert receipt["receipt_sha256"]


def test_cli_writes_an_atomic_blocker_receipt(tmp_path, monkeypatch):
    blocked = experiment.preflight(
        status=_blocked_status(),
        environ={},
        os_name="nt",
        mpmath_status={"state": "UNAVAILABLE", "version": None},
    )
    monkeypatch.setattr(experiment, "preflight", lambda: blocked)
    target = tmp_path / "preflight.json"
    assert experiment.main(["--execute-all", "--output", str(target)]) == 2
    value = json.loads(target.read_text(encoding="utf-8"))
    assert value["state"] == "BLOCKED"
    assert value["receipt_sha256"]
    assert not Path(str(target) + ".tmp").exists()


def test_observation_run_id_stays_inside_ledger_boundary(monkeypatch):
    captured = {}
    case = {
        "case_id": "case-" + ("x" * 115),
        "request_sha256": "a" * 64,
        "request": {"operation": "SOLVE_LINEAR", "inputs": {"matrix": [[1.0]], "rhs": [1.0]}},
    }
    monkeypatch.setattr(experiment._adapter, "run_engine", lambda *_: {"state": "RESULT", "values": [1.0]})
    monkeypatch.setattr(
        experiment,
        "_reference",
        lambda _: (
            {"state": "MEASURED", "implementation": "TEST", "values": [1.0], "evidence_sha256": "b" * 64},
            {"case_id": case["case_id"]},
        ),
    )
    monkeypatch.setattr(
        experiment._dataset,
        "ingest_result",
        lambda payload: captured.setdefault("payload", payload) or {"comparison_state": "WAITING_FOR_PEER"},
    )
    monkeypatch.setattr(experiment, "_child_cpu_snapshot", lambda: (0, 0))
    experiment._observe_case(
        "octave",
        case,
        {"version": "test", "version_evidence_sha256": "c" * 64, "executable_sha256": "d" * 64},
        {"evidence_sha256": "e" * 64},
    )
    run_id = captured["payload"]["run_id"]
    assert len(run_id) <= 96
    assert run_id.endswith("-" + ("a" * 16))


@pytest.mark.parametrize(
    ("comparison_state", "expected_state"),
    [("MATCH", "COMPLETE"), ("CONFLICT", "COMPLETE"), ("UNAVAILABLE", "INCOMPLETE")],
)
def test_complete_requires_two_rows_and_no_unavailable_pair(monkeypatch, comparison_state, expected_state):
    plan = {
        "planned_engine_runs": 2,
        "case_counts": {"confirmatory": 1, "exploratory": 0, "total": 1},
    }
    preflight = {
        "state": "READY_TO_PROBE",
        "receipt_sha256": "f" * 64,
        "plan": plan,
    }
    monkeypatch.setattr(experiment, "preflight", lambda: preflight)
    monkeypatch.setattr(experiment._adapter, "engine_status", lambda: {})
    monkeypatch.setattr(experiment, "_isolation_probe", lambda _: {"evidence_sha256": "1" * 64})
    monkeypatch.setattr(
        experiment,
        "_probe_engine_version",
        lambda engine, _: {"version": engine, "version_evidence_sha256": "2" * 64, "executable_sha256": "3" * 64},
    )
    monkeypatch.setattr(experiment, "_iter_cases", lambda: iter([{"case_id": "case-1"}]))

    calls = iter(["WAITING_FOR_PEER", comparison_state])
    monkeypatch.setattr(
        experiment,
        "_observe_case",
        lambda *args: ({"comparison_state": next(calls)}, {"case_id": "case-1"}),
    )
    receipt = experiment.run_preregistered(execute_all=True)
    assert receipt["state"] == expected_state
    assert receipt["engine_invocations"] == 2
    assert receipt["result_rows"] == 2
    assert receipt["pair_outcomes"][comparison_state] == 1
    assert receipt["reference_rows"] == 1
    assert receipt["reference_evidence"] == [{"case_id": "case-1"}]
    assert receipt["reference_chain_sha256"]
