#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Evidence transport must not hide the fabrication monitor's verdict."""
import json
import os
from pathlib import Path
import re
import subprocess

import pytest
import szl_braineval as braineval
from scripts import check_fabrication_gate as gate

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/fabrication-gate.yml"


def enforce(outcome):
    workflow = WORKFLOW.read_text(encoding="utf-8")
    final_step = workflow.split("      - name: Enforce the recorded gate result\n", 1)[1]
    assert "if: always()" in final_step
    command = re.search(r"^        run: (.+)$", final_step, re.M).group(1)
    return subprocess.run(
        ["bash", "-e", "-c", command],
        env={**os.environ, "GATE_OUTCOME": outcome},
        capture_output=True,
        check=False,
    ).returncode


@pytest.mark.parametrize(
    "result,expected_exit,expected_verdict",
    [
        ({"label": "MEASURED", "verdict": "FABRICATION-DETECTED", "refusal_rate": 0.5}, 1, "FAIL"),
        ({"label": "MEASURED", "verdict": braineval.VERDICT_HONEST, "refusal_rate": 0.97}, 0, "PASS"),
        ({"label": "UNAVAILABLE", "verdict": braineval.VERDICT_UNAVAILABLE, "refusal_rate": None}, 0, "SKIP"),
    ],
)
def test_uploaded_verdict_preserves_monitor_result(monkeypatch, tmp_path, result, expected_exit, expected_verdict):
    monkeypatch.setattr(braineval, "evaluate", lambda **kwargs: result)
    path = tmp_path / "fabrication-gate-verdict.json"
    monkeypatch.setattr(gate, "OUT_PATH", path)

    code = gate.main()

    assert code == expected_exit
    verdict = json.loads(path.read_text(encoding="utf-8"))
    assert verdict["gate_outcome"] == expected_verdict
    assert verdict["refusal_rate"] == result["refusal_rate"]
    assert enforce("failure" if code else "success") == expected_exit


@pytest.mark.parametrize("outcome", ["skipped", "cancelled", ""])
def test_missing_evaluation_cannot_finish_green(outcome):
    assert enforce(outcome) != 0


def test_artifact_transport_is_allowed_without_disabling_egress_controls():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "egress-policy: block" in workflow
    endpoints = workflow.split("          allowed-endpoints: >\n", 1)[1].split("      - name:", 1)[0].split()
    assert "results-receiver.actions.githubusercontent.com:443" in endpoints
    assert all("*" not in endpoint and endpoint.endswith(":443") for endpoint in endpoints)
    artifact = workflow.split("      - name: Upload immutable verdict\n", 1)[1].split("      - name:", 1)[0]
    assert "if: always()" in artifact
    assert "if-no-files-found: error" in artifact
    assert "continue-on-error" not in artifact
    assert workflow.index("Upload immutable verdict") < workflow.index("Enforce the recorded gate result")


def test_pull_requests_exercise_contract_without_live_model_or_issue_writes():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    triggers = workflow.split("\npermissions:", 1)[0]
    assert "  pull_request:\n" in triggers
    assert "'tests/test_fabrication_gate_workflow.py'" in triggers
    contract, monitor = workflow.split("\n  fabrication-gate:\n", 1)
    assert "if: github.event_name == 'pull_request'" in contract
    assert "python -m pytest -q tests/test_fabrication_gate_workflow.py tests/test_braineval.py" in contract
    assert "issues: write" not in contract
    assert "secrets." not in contract
    assert "if: github.event_name != 'pull_request'" in monitor
    assert "issues: write" in monitor
