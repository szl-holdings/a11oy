from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "alert-channel-watch.yml"


def workflow() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_pull_requests_run_only_the_secret_free_contract() -> None:
    value = workflow()
    contract, watch = value.split("\n  watch:", 1)
    assert "if: github.event_name == 'pull_request'" in contract
    assert "tests/test_alert_channel_canary.py" in contract
    assert "secrets." not in contract
    assert "if: github.event_name != 'pull_request'" in watch
    assert "SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}" in watch


def test_protected_merge_triggers_a_real_canary() -> None:
    value = workflow()
    trigger, _ = value.split("\npermissions:", 1)
    assert "push:\n    branches: [main]" in trigger
    plan = value.split("Decide whether this run performs a real delivery canary", 1)[1].split(
        "Run one bounded, protocol-aware canary", 1
    )[0]
    assert 'if [ "${EVENT_NAME}" = \'push\' ]; then' in plan
    assert "send=true" in plan


def test_presence_only_state_cannot_close_the_incident() -> None:
    value = workflow()
    assert "if (state === 'PRESENT_UNPROBED')" in value
    presence_block = value.split("if (state === 'PRESENT_UNPROBED')", 1)[1].split(
        "if (state === 'HEALTHY')", 1
    )[0]
    assert "cannot close" in presence_block
    assert "issues.update" not in presence_block
    assert "issues.createComment" not in presence_block


def test_only_a_real_healthy_canary_closes_the_issue() -> None:
    value = workflow()
    healthy_block = value.split("if (state === 'HEALTHY')", 1)[1].split(
        "if (!failures.has(state))", 1
    )[0]
    assert "real one-attempt 2xx delivery canary" in healthy_block
    assert "state: 'closed'" in healthy_block
    assert "state_reason: 'completed'" in healthy_block


def test_real_canary_failure_remains_red_after_issue_sync() -> None:
    value = workflow()
    assert "continue-on-error: true" in value
    assert "Reconcile deterministic incident without false recovery" in value
    assert "Enforce delivery health when a real canary was required" in value
    assert "Shared alert channel did not prove a healthy delivery" in value


def test_all_third_party_actions_are_immutable_sha_pinned() -> None:
    for line in workflow().splitlines():
        if "uses:" not in line:
            continue
        ref = line.split("@", 1)[1].split()[0]
        assert re.fullmatch(r"[0-9a-f]{40}", ref), line


def test_browser_or_issue_evidence_never_contains_the_endpoint_value() -> None:
    value = workflow()
    assert 'echo "${SLACK_WEBHOOK_URL}"' not in value
    assert "set -x" not in value
    assert "endpoint path, query, webhook token, secret value" in value
