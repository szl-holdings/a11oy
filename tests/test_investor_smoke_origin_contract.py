# Copyright 2026 SZL Holdings
# SPDX-License-Identifier: Apache-2.0
"""Lock the two-origin investor-smoke contract.

The public apex is a static product front door. Runtime HTTP and API assertions
belong to the canonical source-bound Hugging Face Space until an independently
proved edge proxy changes that architecture. Provider liveness is measured after
protected merge and on schedule, not used to deadlock an unrelated source PR.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "investor-smoke-gate.yml"
RUNBOOK = ROOT / "docs" / "INVESTOR_SMOKE_GATE.md"
PRODUCT_FRONT_DOOR = "https://a-11-oy.com"
RUNTIME_ORIGIN = "https://szlholdings-a11oy.hf.space"


def test_workflow_separates_static_front_door_from_runtime() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert f"PRODUCT_FRONT_DOOR: {PRODUCT_FRONT_DOOR}" in text
    assert f"RUNTIME_ORIGIN: {RUNTIME_ORIGIN}" in text
    assert '--origin "$RUNTIME_ORIGIN"' in text
    assert "os.environ[\"PRODUCT_FRONT_DOOR\"]" in text
    assert f"--origin {PRODUCT_FRONT_DOOR}" not in text


def test_runbook_names_both_origins_without_overclaiming() -> None:
    text = RUNBOOK.read_text(encoding="utf-8")
    assert f"Static product front door: `{PRODUCT_FRONT_DOOR}`" in text
    assert f"Canonical application runtime: `{RUNTIME_ORIGIN}`" in text
    assert f"--origin {RUNTIME_ORIGIN}" in text
    assert "The static front door is not an API origin." in text


def test_gate_remains_read_only_and_fail_closed() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "Runtime GET/HEAD probes (no POST)" in text
    assert "--mode live" in text
    assert "curl -X POST" not in text
    assert "continue-on-error" not in text


def test_provider_liveness_is_post_merge_and_scheduled_not_pr_admission() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "pull_request:\n    branches: [main]" in text
    assert "push:\n    branches: [main]" in text
    assert 'schedule:\n    - cron: "17 */6 * * *"' in text
    assert "workflow_dispatch: {}" in text
    assert "name: Investor smoke live probes\n    if: github.event_name != 'pull_request'" in text
    assert "A skipped live job on a pull request is an explicit lifecycle state" in text


def test_runbook_preserves_provider_failure_visibility() -> None:
    text = RUNBOOK.read_text(encoding="utf-8")
    assert "Provider liveness is not a pull-request admission check." in text
    assert "protected-main push" in text
    assert "six-hour schedule" in text
    assert "must remain red" in text
