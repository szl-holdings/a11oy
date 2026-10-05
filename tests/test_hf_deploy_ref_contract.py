"""Exact-source, push-only canonical recovery/deployment regression contract."""

from pathlib import Path

import pytest

from tests.test_hf_sync_supersession_contract import (
    assert_manual_dependency_graph,
    explicit_condition_allows,
    successful_dependency_context,
    workflow_document,
)

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "hf-sync.yml"


def test_canonical_push_has_no_path_filter_and_deploys_exact_checked_out_commit() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    document = workflow_document(text)
    assert document["on"]["push"] == {"branches": ["main"]}
    jobs = assert_manual_dependency_graph(text)
    deploy = jobs["deploy"]
    assert deploy["uses"] == "szl-holdings/.github/.github/workflows/reusable-hf-deploy.yml@e3ec47ad2e99a535839afe0f30fefbd8973d52da"
    assert deploy["with"]["ref"] == "${{ github.sha }}"
    assert deploy["with"]["hf-repo"] == "SZLHOLDINGS/a11oy"
    assert deploy["with"]["dockerfile-path"] == "Dockerfile"
    assert deploy["with"]["require-default-branch-tip"] is True
    assert document["concurrency"]["cancel-in-progress"] is False
    for name in ("source-admission", "recovery-reconciliation", "manual-prerequisites", "durable-acquisition", "runtime-config"):
        checkouts = [step for step in jobs[name]["steps"]
                     if step.get("uses", "").startswith("actions/checkout@")
                     and "repository" not in step.get("with", {})]
        assert len(checkouts) == 1
        assert checkouts[0]["with"]["ref"] == "${{ github.sha }}"
        assert checkouts[0]["with"]["persist-credentials"] is False


@pytest.mark.parametrize("event", ["workflow_dispatch", "pull_request", "schedule"])
def test_other_events_cannot_reuse_successful_canonical_push_admission(event) -> None:
    jobs = assert_manual_dependency_graph(WORKFLOW.read_text(encoding="utf-8"))
    context = successful_dependency_context(jobs, event=event)
    for name in ("recovery-reconciliation", "manual-prerequisites", "durable-acquisition", "deploy", "runtime-config"):
        assert explicit_condition_allows(jobs[name], context) is False


@pytest.mark.parametrize("attempt", [0, 2, 3])
def test_full_or_partial_reruns_cannot_reuse_canonical_push_admission(attempt) -> None:
    jobs = assert_manual_dependency_graph(WORKFLOW.read_text(encoding="utf-8"))
    context = successful_dependency_context(jobs, attempt=attempt)
    for name in ("recovery-reconciliation", "manual-prerequisites", "durable-acquisition", "deploy", "runtime-config"):
        assert explicit_condition_allows(jobs[name], context) is False
