#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Evidence transport must not hide the fabrication monitor's verdict."""
import json
from pathlib import Path
import re
import shlex
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
    # Stdin preserves shell quoting on Windows Bash launchers as well as CI.
    script = "GATE_OUTCOME=" + shlex.quote(outcome) + "\n" + command + "\n"
    return subprocess.run(
        ["bash", "-e", "-s"],
        input=script.encode("utf-8"),
        capture_output=True,
        check=False,
    ).returncode


def test_retired_monitor_emits_unavailable_without_inference(monkeypatch, tmp_path):
    def forbidden(**kwargs):
        pytest.fail("retired monitor called the legacy model evaluator")
    monkeypatch.setattr(braineval, "evaluate", forbidden)
    path = tmp_path / "fabrication-gate-verdict.json"
    monkeypatch.setattr(gate, "OUT_PATH", path)

    code = gate.main()

    assert code == 2
    verdict = json.loads(path.read_text(encoding="utf-8"))
    assert verdict["gate_outcome"] == "RETIRED"
    assert verdict["label"] == verdict["model_verdict"] == "UNAVAILABLE"
    assert verdict["inference_performed"] is False
    assert verdict["evaluation_performed"] is False
    assert verdict["refusal_rate"] is None and verdict["probes"] == []
    assert verdict["successor"]["path"] == "/api/a11oy/v1/atelier/cpu-lab/turn"
    assert verdict["successor"]["operator_authentication_required"] is True
    assert verdict["successor"]["public_share_acknowledged"] is True
    assert verdict["successor"]["declared"] == "PUBLIC"
    assert gate.issue_eligible(verdict) is False
    assert enforce("failure") != 0


@pytest.mark.parametrize("verdict,eligible", [
    ({"gate_outcome": "FAIL", "label": "MEASURED",
      "model_verdict": "FABRICATION-DETECTED"}, True),
    ({"gate_outcome": "RETIRED", "label": "UNAVAILABLE",
      "model_verdict": "UNAVAILABLE"}, False),
    ({"gate_outcome": "SKIP", "label": "UNAVAILABLE"}, False),
    ({"gate_outcome": "FAIL", "label": "UNAVAILABLE",
      "model_verdict": "FABRICATION-DETECTED"}, False),
    ({"gate_outcome": "PASS", "label": "MEASURED",
      "model_verdict": "FABRICATION-DETECTED"}, False),
    ({"gate_outcome": "FAIL", "label": "MEASURED",
      "model_verdict": "REFUSAL-HONEST"}, False),
    ({"gate_outcome": "FAIL"}, False),
    (None, False), ([], False),
])
def test_only_declared_measured_fabrication_can_file_issue(verdict, eligible):
    assert gate.issue_eligible(verdict) is eligible


def test_issue_step_uses_evidence_not_generic_process_failure():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    issue = workflow.split("      - name: File or update the fabrication finding\n", 1)[1]
    issue = issue.split("      - name: Upload immutable verdict\n", 1)[0]
    assert "if: steps.evidence.outputs.fabrication_detected == 'true'" in issue
    assert "steps.gate.outcome == 'failure'" not in issue
    classification = workflow.split("      - name: Classify recorded fabrication evidence\n", 1)[1]
    classification = classification.split("      - name: File or update", 1)[0]
    assert "from scripts.check_fabrication_gate import issue_eligible" in classification
    assert "str(issue_eligible(verdict)).lower()" in classification
    assert enforce("success") == 0
    assert enforce("failure") != 0


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
