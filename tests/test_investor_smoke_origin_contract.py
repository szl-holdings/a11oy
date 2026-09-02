# Copyright 2026 SZL Holdings
# SPDX-License-Identifier: Apache-2.0
"""Lock the two-origin investor-smoke contract.

The public apex is a static product front door. Runtime HTTP and API assertions
belong to the canonical source-bound Hugging Face Space until an independently
proved edge proxy changes that architecture.
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
