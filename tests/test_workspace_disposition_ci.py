# SPDX-License-Identifier: Apache-2.0
"""Ensure hosted CI keeps exercising the receipt's source-owned contracts."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/truth-gates.yml"
MARKER = "  workspace-disposition-contract:\n"


def contract_job():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert text.count(MARKER) == 1
    return text.split(MARKER, 1)[1]


def test_both_semantic_and_identity_regressions_are_hosted():
    job = contract_job()
    for name in ("test_workspace_disposition.py", "test_workspace_disposition_identity.py",
                 "test_workspace_disposition_ci.py"):
        assert f"tests/{name}" in job
    assert "python -m pytest -q" in job
    assert 'python: ["3.11", "3.12"]' in job


def test_workspace_results_are_not_observe_only_or_suppressed():
    job = contract_job()
    assert "continue-on-error" not in job
    assert "|| true" not in job
    assert "timeout-minutes: 5" in job
    assert "--require-hashes -r .github/requirements/ci-core.txt" in job
    assert "secrets." not in job


def test_workspace_job_and_checkout_are_exact_candidate_bound():
    job = contract_job()
    assert "ref: ${{ github.event.pull_request.head.sha || github.sha }}" in job
    assert "persist-credentials: false" in job
    assert 'test "$(git rev-parse HEAD)" = "$EXPECTED_SOURCE_SHA"' in job


def test_failed_test_reports_are_retained():
    job = contract_job()
    assert "--junitxml=workspace-disposition-tests.xml" in job
    assert "if: always()" in job
    assert "path: workspace-disposition-tests.xml" in job
    assert "if-no-files-found: error" in job
