#!/usr/bin/env python3
"""Offline regression tests for the Hugging Face runtime verifier."""

from check_hf_runtime_revision import evaluate_metadata


EXPECTED = "a" * 40


def _metadata(*, repository=EXPECTED, runtime=EXPECTED, stage="RUNNING"):
    return {"sha": repository, "runtime": {"sha": runtime, "stage": stage}}


def test_matching_repository_and_runtime_pass() -> None:
    result = evaluate_metadata(_metadata(), EXPECTED)
    assert result["status"] == "PASS"
    assert result["repository_runtime_relation"] == "SAME_REVISION"


def test_metadata_only_repository_advance_passes_runtime_gate() -> None:
    result = evaluate_metadata(_metadata(repository="b" * 40), EXPECTED)
    assert result["status"] == "PASS"
    assert result["repository_runtime_relation"] == "DISTINCT_REVISIONS"
    assert result["source_parity_evaluated_here"] is False


def test_runtime_mismatch_fails() -> None:
    result = evaluate_metadata(_metadata(runtime="c" * 40), EXPECTED)
    assert result["status"] == "FAIL"
    assert "runtime revision mismatch" in result["failures"][0]


def test_nonrunning_stage_fails() -> None:
    result = evaluate_metadata(_metadata(stage="BUILDING"), EXPECTED)
    assert result["status"] == "FAIL"
    assert any("not RUNNING" in failure for failure in result["failures"])


def test_missing_revisions_fail() -> None:
    result = evaluate_metadata({"runtime": {"stage": "RUNNING"}}, EXPECTED)
    assert result["status"] == "FAIL"
    assert "repository revision is missing" in result["failures"]
    assert "runtime revision is missing" in result["failures"]


if __name__ == "__main__":
    tests = [
        test_matching_repository_and_runtime_pass,
        test_metadata_only_repository_advance_passes_runtime_gate,
        test_runtime_mismatch_fails,
        test_nonrunning_stage_fails,
        test_missing_revisions_fail,
    ]
    for test in tests:
        test()
    print(f"{len(tests)} runtime revision checks passed")
