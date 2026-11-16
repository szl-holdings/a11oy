# SPDX-License-Identifier: Apache-2.0
from vsp_otel.task_shape import classify_task


def test_parallel_mode_requires_measured_decomposability():
    out = classify_task(independent_units=4, dependency_depth=1, tool_count=6)
    assert out["mode"] == "PARALLEL_EVIDENCE"
    assert out["reason"] == "decomposable_low_dependency"
    assert out["authorization_effect"] == "NONE"


def test_proof_and_human_boundaries_force_central_sequential():
    assert classify_task(
        independent_units=8, dependency_depth=0, tool_count=2, proof_chain=True
    )["mode"] == "CENTRAL_SEQUENTIAL"
    assert classify_task(
        independent_units=8, dependency_depth=0, tool_count=2, human_approval_required=True
    )["mode"] == "CENTRAL_SEQUENTIAL"


def test_tool_dense_or_deep_tasks_stay_sequential():
    assert classify_task(independent_units=8, dependency_depth=2, tool_count=4)["mode"] == "CENTRAL_SEQUENTIAL"
    assert classify_task(independent_units=8, dependency_depth=0, tool_count=13)["mode"] == "CENTRAL_SEQUENTIAL"


def test_invalid_task_shape_is_rejected():
    try:
        classify_task(independent_units=-1, dependency_depth=0, tool_count=1)
    except ValueError:
        pass
    else:
        raise AssertionError("negative task shape must be rejected")
