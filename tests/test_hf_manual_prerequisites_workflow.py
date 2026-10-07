#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Offline deploy-path, restart-drill, bounded live-proof and CLI boundaries; no network.

The deploy path (hf-sync.yml) converges configuration before its single Space
start and never pauses or restarts the Space afterwards. The bounded Series-A
pause/restart and GDW restart proofs run only in the manual restart-drill.yml.
"""

from __future__ import annotations

import ast
import hashlib
import io
import json
import os
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

if __package__ in (None, ""):
    # Native CI invokes this file directly; its sibling is on sys.path.
    from test_hf_sync_supersession_contract import (
        ROOT, WORKFLOW, WorkflowContractError, assert_deploy_dependency_graph,
        workflow_document,
    )
else:
    from .test_hf_sync_supersession_contract import (
        ROOT, WORKFLOW, WorkflowContractError, assert_deploy_dependency_graph,
        workflow_document,
    )

CHECKER = ROOT / "scripts/check_hf_manual_prerequisites.py"
RESTART_WORKFLOW = ROOT / ".github/workflows/series-a-restart-proof.yml"
DRILL_WORKFLOW = ROOT / ".github/workflows/restart-drill.yml"
PROOFS = (
    ("prove_hf_series_a_restart.py", "szl.series-a-restart-proof/v1", "secret_values_recorded"),
    ("prove_hf_gdw_runtime.py", "szl.hf-gdw-live-proof/v1", "credential_values_recorded"),
)


def named_step(job, name):
    matches = [step for step in job.get("steps", []) if step.get("name") == name]
    if len(matches) != 1:
        raise WorkflowContractError("missing or duplicate step: " + name)
    return matches[0]


def compact(value):
    return " ".join(value.split())


def exact_step(actual, expected, diagnostic):
    """Reject added keys/effects while tolerating only shell whitespace layout."""
    actual, expected = dict(actual), dict(expected)
    for value in (actual, expected):
        if "run" in value:
            if type(value["run"]) is not str:
                raise WorkflowContractError(diagnostic)
            value["run"] = compact(value["run"])
    if actual != expected:
        raise WorkflowContractError(diagnostic)


CHECKOUT = "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1"
SETUP_PYTHON = "actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97"
UPLOAD = "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a"
HF_CREDENTIAL = "${{ secrets.HF_ORG_TOKEN || secrets.HF_TOKEN }}"
CONTROL_CLIENT = 'python -m pip install --disable-pip-version-check "huggingface_hub==1.31.0" "requests==2.32.5" "cryptography==50.0.1"'
EXACT_CHECKOUT = {"name": "Checkout exact protected source", "uses": CHECKOUT,
                  "with": {"ref": "${{ github.sha }}", "persist-credentials": False, "fetch-depth": "1"}}
PYTHON_312 = {"name": "Set up Python", "uses": SETUP_PYTHON, "with": {"python-version": "3.12"}}
CLASSIFY_RUN = '''python -B .github/scripts/resume_hf_space.py
--repo-id "$CANONICAL_SPACE"
--output "$PREFLIGHT_REPORT"
--github-output "$GITHUB_OUTPUT"'''
CONVERGE_RUN = r'''set -euo pipefail
if [ "${CONVERGE:-false}" != 'true' ]; then
  echo '::notice::The canonical runtime is not serving; configuration converges against the deployed revision.'
  echo 'converged=false' >> "$GITHUB_OUTPUT"
  exit 0
fi
python3 -B scripts/hf_exact_main_ownership.py \
  --repository "$GITHUB_REPOSITORY" --expected-sha "$GITHUB_SHA" \
  --receipt "$RUNNER_TEMP/preflight-series-config-admission.json" \
  --github-output "$RUNNER_TEMP/preflight-series-config-admission.out"
if ! grep -Fqx 'publish=true' "$RUNNER_TEMP/preflight-series-config-admission.out"; then
  echo '::error::Protected main changed before Series-A configuration.'
  exit 1
fi
python -B scripts/configure_hf_series_a_runtime.py \
  --repo-id "$CANONICAL_SPACE" --bucket "SZLHOLDINGS/szl-evidence" \
  --output "$RUNTIME_CONFIG_REPORT"
python3 -B scripts/hf_exact_main_ownership.py \
  --repository "$GITHUB_REPOSITORY" --expected-sha "$GITHUB_SHA" \
  --receipt "$RUNNER_TEMP/preflight-gdw-config-admission.json" \
  --github-output "$RUNNER_TEMP/preflight-gdw-config-admission.out"
if ! grep -Fqx 'publish=true' "$RUNNER_TEMP/preflight-gdw-config-admission.out"; then
  echo '::error::Protected main changed before GDW configuration.'
  exit 1
fi
python -B scripts/configure_hf_gdw_runtime.py \
  --repo-id "$CANONICAL_SPACE" --output "$GDW_CONFIG_REPORT"
echo 'converged=true' >> "$GITHUB_OUTPUT"'''
ADMIT_RUN = r'''set -euo pipefail
python3 -B scripts/hf_exact_main_ownership.py \
  --repository "$GITHUB_REPOSITORY" --expected-sha "$GITHUB_SHA" \
  --receipt "$RUNNER_TEMP/preflight-admission.json" \
  --github-output "$GITHUB_OUTPUT"'''
WINDOW_RUN = r'''set -euo pipefail
if [ "${STAGE:-}" = 'PAUSED' ] || [ "${DISPATCH_WINDOW:-false}" = 'true' ]; then
  echo 'open=true' >> "$GITHUB_OUTPUT"
  exit 0
fi
echo "::warning::Deploy window closed (stage=${STAGE:-UNKNOWN}); nothing was written or deployed. Pause the Space, or dispatch hf-sync.yml on main with open_deploy_window=true, inside an agreed maintenance window."
echo 'open=false' >> "$GITHUB_OUTPUT"'''
WINDOW_ENV = {"STAGE": "${{ steps.runtime.outputs.stage }}",
              "DISPATCH_WINDOW": "${{ github.event_name == 'workflow_dispatch' && inputs.open_deploy_window == true }}"}
ADMITTED = "${{ steps.admit.outputs.publish == 'true' }}"
WINDOW_OPEN = "${{ steps.window.outputs.open == 'true' }}"
AWAIT_RUN = '''python -B .github/scripts/await_hf_runtime_serving.py
--repo-id "$CANONICAL_SPACE"
--origin "$CANONICAL_ORIGIN"
--source-sha "$GITHUB_SHA"
--report "$RUNTIME_CONFIG_REPORT"
--report "$GDW_CONFIG_REPORT"'''
OWNER_RUN = r'''set -euo pipefail
python3 -B scripts/hf_exact_main_ownership.py \
  --repository "$GITHUB_REPOSITORY" --expected-sha "$GITHUB_SHA" \
  --receipt "$RUNNER_TEMP/preflight-source-admission.json" \
  --github-output "$GITHUB_OUTPUT"'''
VERIFY_RUN = r'''set -euo pipefail
mode=()
if [ "${PREDEPLOY_CONVERGED:-false}" = 'true' ]; then
  mode=(--check-only)
else
  echo '::notice::Configuration was not converged before deploy; converging against the deployed revision.'
  python3 -B scripts/hf_exact_main_ownership.py \
    --repository "$GITHUB_REPOSITORY" --expected-sha "$GITHUB_SHA" \
    --receipt "$RUNNER_TEMP/runtime-series-config-admission.json" \
    --github-output "$RUNNER_TEMP/runtime-series-config-admission.out"
  if ! grep -Fqx 'publish=true' "$RUNNER_TEMP/runtime-series-config-admission.out"; then
    echo '::error::Protected main changed before post-deploy Series-A configuration.'
    exit 1
  fi
fi
python -B scripts/configure_hf_series_a_runtime.py \
  --repo-id "$CANONICAL_SPACE" --bucket "SZLHOLDINGS/szl-evidence" \
  "${mode[@]}" --output "$RUNTIME_CONFIG_REPORT"
if [ "${PREDEPLOY_CONVERGED:-false}" != 'true' ]; then
  python3 -B scripts/hf_exact_main_ownership.py \
    --repository "$GITHUB_REPOSITORY" --expected-sha "$GITHUB_SHA" \
    --receipt "$RUNNER_TEMP/runtime-gdw-config-admission.json" \
    --github-output "$RUNNER_TEMP/runtime-gdw-config-admission.out"
  if ! grep -Fqx 'publish=true' "$RUNNER_TEMP/runtime-gdw-config-admission.out"; then
    echo '::error::Protected main changed before post-deploy GDW configuration.'
    exit 1
  fi
fi
python -B scripts/configure_hf_gdw_runtime.py \
  --repo-id "$CANONICAL_SPACE" \
  "${mode[@]}" --output "$GDW_CONFIG_REPORT"'''
# Post-deploy jobs may read and verify, never restart, pause or write variables.
POST_DEPLOY_JOBS = ("runtime-config", "readiness-verdict", "relock",
                    "post-deployment-parity", "terminal-source-authorization")
RESTART_EFFECT_TOKENS = ("restart_space", "restart-space", "pause_space", "add_space_variable",
                         "prove_hf_series_a_restart.py",
                         "prove_hf_gdw_runtime.py", "--managed-acquisition", "acquire_gdw_durable_storage.py",
                         "reconcile_gdw_diagnostic_continuation.py")
REMOVED_CREDENTIAL_TOKENS = ("DOCS_READ_TOKEN", "--github-read-token", "--operator-token", "--capacity-donor",
                             "HF_CAPACITY_DONOR", "add_space_secret", "delete_space_secret", "gh issue",
                             "issues: write", "OPERATOR_TOKEN", "actions: write")


VERDICT_PUBLISH = re.compile(r"publish_readiness_verdict\.py(?!\s+--validate-only\b)")
VERDICT_VALIDATE_RUN = '''python .github/scripts/publish_readiness_verdict.py
--validate-only
--input "$VERDICT_PATH"
--expected-origin "$CANONICAL_ORIGIN"
--expected-source-sha "$SOURCE_SHA"
--github-output "$GITHUB_OUTPUT"'''
RUN_VERDICT = "${{ needs.readiness-verdict.outputs.verdict }}"


def job_strings(value):
    """Yield every decoded string inside a parsed job (shell bodies included)."""
    if isinstance(value, dict):
        for child in value.values():
            yield from job_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from job_strings(child)
    elif isinstance(value, str):
        yield value


def assert_deploy_path_contract(source):
    """The deploy path converges first, starts once, then only verifies."""
    jobs = assert_deploy_dependency_graph(source)
    admission = jobs["source-admission"]
    if [step.get("name") for step in admission["steps"]] != [
            "Checkout the immutable queued source", "Require main and classify current source ownership",
            "Retain the source admission decision"] or "secrets." in json.dumps(admission):
        raise WorkflowContractError("source admission must remain read only")

    preflight = jobs["preflight"]
    if (preflight.get("permissions") != {"contents": "read"}
            or preflight.get("env", {}).get("HF_TOKEN") != HF_CREDENTIAL
            or preflight.get("outputs") != {
                "publish": "${{ steps.window.outputs.open == 'true' && steps.owner.outputs.publish == 'true' }}",
                "restart_required": "${{ steps.runtime.outputs.restart_required }}",
                "converged": "${{ steps.converge.outputs.converged }}"}):
        raise WorkflowContractError("preflight authority, permission or output scope changed")
    names = [step.get("name") for step in preflight["steps"]]
    if names != ["Checkout exact protected source",
                 "Require current protected main before any provider effect",
                 "Set up Python", "Install exact Hugging Face control client",
                 "Classify the runtime stage without restarting it",
                 "Require an open deploy window while SQLite lives on the bucket mount",
                 "Converge runtime configuration before the single deploy start",
                 "Re-admit current protected main immediately before deploy",
                 "Skip a superseded source with a notice", "Retain secret-free preflight evidence"]:
        raise WorkflowContractError("preflight step order")
    exact_step(preflight["steps"][0], EXACT_CHECKOUT, "preflight checkout")
    # A superseded (or re-run) source is refused before any provider effect.
    exact_step(preflight["steps"][1], {"name": names[1], "id": "admit", "shell": "bash",
                                       "env": {"GITHUB_TOKEN": "${{ github.token }}"}, "run": ADMIT_RUN},
               "preflight must admit current main before any provider effect")
    exact_step(preflight["steps"][2], {**PYTHON_312, "if": ADMITTED}, "preflight interpreter")
    exact_step(preflight["steps"][3], {"name": names[3], "if": ADMITTED, "run": CONTROL_CLIENT},
               "preflight control client")
    exact_step(preflight["steps"][4], {"name": names[4], "id": "runtime", "if": ADMITTED, "run": CLASSIFY_RUN},
               "preflight classification must stay read-only")
    exact_step(preflight["steps"][5], {"name": names[5], "id": "window", "if": ADMITTED, "shell": "bash",
                                       "env": WINDOW_ENV, "run": WINDOW_RUN}, "deploy window")
    exact_step(preflight["steps"][6], {"name": names[6], "id": "converge", "if": WINDOW_OPEN, "shell": "bash",
                                       "env": {"CONVERGE": "${{ steps.runtime.outputs.converge }}",
                                               "GITHUB_TOKEN": "${{ github.token }}"},
                                       "run": CONVERGE_RUN}, "preflight convergence")
    exact_step(preflight["steps"][7], {"name": names[7], "id": "owner", "if": WINDOW_OPEN, "shell": "bash",
                                       "env": {"GITHUB_TOKEN": "${{ github.token }}"}, "run": OWNER_RUN},
               "preflight must re-admit current main")
    window_input = workflow_document(source)["on"]["workflow_dispatch"]["inputs"].get("open_deploy_window", {})
    if window_input.get("type") != "boolean" or window_input.get("default") is not False:
        raise WorkflowContractError("deploy window must default closed")

    deploy = jobs["deploy"]
    inputs = deploy.get("with", {})
    if (inputs.get("restart-space") != "${{ needs.preflight.outputs.restart_required == 'true' }}"
            or inputs.get("require-default-branch-tip") is not True
            or inputs.get("ref") != "${{ github.sha }}"
            or inputs.get("source-revision-variable") != "SZL_GIT_SHA"
            or inputs.get("source-revision-probe-path") != "/api/build-info"):
        raise WorkflowContractError("deploy must start the Space once and bind exact source")

    runtime = jobs["runtime-config"]
    if (runtime.get("permissions") != {"contents": "read"}
            or [step.get("name") for step in runtime["steps"]] != [
                "Checkout exact protected source", "Set up Python", "Install exact Hugging Face control client",
                "Verify or converge runtime configuration against the deployed revision",
                "Await the deployed revision serving again after any convergence write",
                "Upload secret-free runtime configuration evidence"]):
        raise WorkflowContractError("runtime-config step order")
    exact_step(runtime["steps"][3], {
        "name": "Verify or converge runtime configuration against the deployed revision",
        "shell": "bash", "env": {"PREDEPLOY_CONVERGED": "${{ needs.preflight.outputs.converged }}",
                                "GITHUB_TOKEN": "${{ github.token }}"},
        "run": VERIFY_RUN}, "runtime-config must verify, fail closed")
    exact_step(runtime["steps"][4], {
        "name": "Await the deployed revision serving again after any convergence write",
        "run": AWAIT_RUN}, "runtime-config must await the restarted revision")
    paths = tuple(runtime["steps"][5].get("with", {}).get("path", "").splitlines())
    if paths != ("${{ env.RUNTIME_CONFIG_REPORT }}", "${{ env.GDW_CONFIG_REPORT }}",
                 "${{ runner.temp }}/runtime-series-config-admission.json",
                 "${{ runner.temp }}/runtime-gdw-config-admission.json"):
        raise WorkflowContractError("runtime-config artifact allowlist")

    for name in POST_DEPLOY_JOBS:
        for text in job_strings(jobs[name]):
            for token in RESTART_EFFECT_TOKENS:
                if token in text:
                    raise WorkflowContractError("post-deploy restart or variable effect: " + name + ": " + token)
            if VERDICT_PUBLISH.search(text):
                raise WorkflowContractError("post-deploy restart or variable effect: " + name + ": verdict publish")
    readiness = jobs["readiness-verdict"]
    if "HF_TOKEN" in json.dumps(readiness) or [step.get("name") for step in readiness["steps"]] != [
            "Checkout exact protected source", "Set up Node.js", "Set up Python",
            "Probe the exact canonical deployment", "Upload immutable full probe evidence",
            "Validate the source-bound verdict without a Space write"]:
        raise WorkflowContractError("readiness verdict must stay evidence-only")
    exact_step(readiness["steps"][-1], {"name": "Validate the source-bound verdict without a Space write",
                                        "id": "gate", "run": VERDICT_VALIDATE_RUN},
               "readiness verdict gate must fail closed without a Space write")
    if readiness.get("outputs") != {"verdict": "${{ steps.gate.outputs.verdict }}"}:
        raise WorkflowContractError("readiness verdict gate must hand its verdict to relock")

    relock = jobs["relock"]
    # The deploy path never writes the verdict into the Space, so relock must
    # re-validate this run's verdict rather than require a served one.
    evaluate = named_step(relock, "Evaluate the canonical application contract")
    evaluate_run = compact(evaluate.get("run", ""))
    if (relock.get("needs") != ["runtime-config", "readiness-verdict"]
            or evaluate.get("env") != {"RUN_READINESS_VERDICT": RUN_VERDICT}
            or 'printf \'%s\' "$RUN_READINESS_VERDICT" > "$RUNNER_TEMP/run-readiness-verdict.json"' not in evaluate_run
            or '--readiness-verdict-file "$RUNNER_TEMP/run-readiness-verdict.json"' not in evaluate_run):
        raise WorkflowContractError("relock must re-validate this run's readiness verdict")
    enforce = named_step(relock, "Enforce exact live state")
    expected_enforce = r'''code="${EXIT_CODE:-2}"
if [ "$code" -ne 0 ]; then
  echo "::error::Canonical A11oy relock failed with exit ${code}."
  exit "$code"
fi
if [ "${CURRENT_MAIN:-false}" != 'true' ]; then
  echo '::notice::A newer protected main superseded this verified source; that run deploys and relocks it.'
  exit 0
fi
echo 'Canonical A11oy is source-bound, singleton, and route-operational.' '''
    if (compact(enforce.get("run", "")) != compact(expected_enforce)
            or enforce.get("if") != "always()"
            or enforce.get("env") != {"EXIT_CODE": "${{ steps.verify.outputs.exit_code }}",
                                      "CURRENT_MAIN": "${{ steps.post_deploy_owner.outputs.publish }}"}
            or relock.get("outputs") != {"current_main": "${{ steps.post_deploy_owner.outputs.publish }}"}):
        raise WorkflowContractError("actual verification exit must be enforced")
    parity = jobs["post-deployment-parity"]
    if (parity.get("needs") != "relock" or parity.get("uses") != "./.github/workflows/hf-module-drift.yml"
            or parity.get("permissions") != {"contents": "read"}):
        raise WorkflowContractError("parity must follow successful verification")
    terminal = jobs["terminal-source-authorization"]
    if (terminal.get("permissions") != {"contents": "read"} or "secrets." in json.dumps(terminal)
            or terminal["steps"][-1].get("name") != "Re-read and enforce exact protected-main ownership as the final step"):
        raise WorkflowContractError("terminal source authorization must fail closed")

    for token in REMOVED_CREDENTIAL_TOKENS:
        if token in source:
            raise WorkflowContractError("removed credential or donor effect: " + token)
    document = workflow_document(source)
    if document["on"]["workflow_dispatch"]["inputs"]["publish_vertical_flagships"]["default"] is not False:
        raise WorkflowContractError("vertical publication requires explicit opt in")
    vertical = jobs["publish-vertical-flagships"]
    owned = "${{ steps.exact_main_owner.outputs.publish == 'true' }}"
    approved = "${{ steps.exact_main_owner.outputs.publish == 'true' && steps.vertical_plan.outputs.vertical_flagships == 'true' }}"
    for name, condition in (("Set up Python", owned), ("Require the approved plan for the actual vertical source", owned),
                            ("Install pinned vertical publisher", approved), ("Publish and verify the v4 vertical estate", approved)):
        if named_step(vertical, name).get("if") != condition:
            raise WorkflowContractError("vertical source and plan gate: " + name)
    return jobs


ADMITTED_GDW_SECRET_LINE = "          GDW_OPERATOR_TOKEN: ${{ secrets.GDW_OPERATOR_TOKEN }}\n"
PROOF_ATTEMPTED = "(steps.series_a_proof.outcome == 'success' || steps.series_a_proof.outcome == 'failure')"
DRILL_PROOF_CONDITION = "${{ always() && " + PROOF_ATTEMPTED + " }}"
BOUNDED_RUNS = {
    "series_a": r'''set +e
python -B scripts/prove_hf_series_a_restart.py \
  --repo-id "$CANONICAL_SPACE" --origin "$CANONICAL_ORIGIN" \
  --run-context "${{ github.run_id }}:${{ github.run_attempt }}" \
  --source-sha "${{ github.sha }}" --output "$SERIES_A_LIVE_REPORT"
code=$?
echo "exit_code=$code" >> "$GITHUB_OUTPUT"
exit "$code"''',
    "gdw": r'''set +e
python -B scripts/prove_hf_gdw_runtime.py \
  --series-a-proof "$SERIES_A_LIVE_REPORT" \
  --run-context "${{ github.run_id }}:${{ github.run_attempt }}" \
  --origin "$CANONICAL_ORIGIN" \
  --source-sha "${{ github.sha }}" --output "$GDW_LIVE_REPORT"
code=$?
echo "exit_code=$code" >> "$GITHUB_OUTPUT"
exit "$code"''',
    "admission": r'''set -euo pipefail
python -B scripts/check_hf_manual_prerequisites.py --admit-live-proofs \
  --series-a-proof "$SERIES_A_LIVE_REPORT" --series-a-proof-exit "${SERIES_A_PROOF_EXIT:-2}" \
  --gdw-proof "$GDW_LIVE_REPORT" --gdw-proof-exit "${GDW_PROOF_EXIT:-2}" \
  --source-sha "${{ github.sha }}" --output "$LIVE_PROOF_ADMISSION_REPORT"''',
}
DRILL_LIVE_RUN = '''set -euo pipefail
python3 -B - "$CANONICAL_ORIGIN/api/build-info" "$GITHUB_SHA" <<'PY'
import json, sys, urllib.request
url, sha = sys.argv[1], sys.argv[2]
request = urllib.request.Request(url, headers={"Cache-Control": "no-cache"})
with urllib.request.urlopen(request, timeout=30) as response:
    build = json.load(response).get("build") or {}
if str(build.get("revision") or "").lower() != sha:
    print("::error::The live Space does not serve current main; deploy it with hf-sync.yml before the drill.")
    sys.exit(1)
PY'''
DRILL_GDW_OWNER_RUN = r'''set -euo pipefail
python3 -B scripts/hf_exact_main_ownership.py \
  --repository "$GITHUB_REPOSITORY" --expected-sha "$GITHUB_SHA" \
  --receipt "$RUNNER_TEMP/restart-drill-gdw-admission.json" \
  --github-output "$RUNNER_TEMP/restart-drill-gdw-admission.out"
if ! grep -Fqx 'publish=true' "$RUNNER_TEMP/restart-drill-gdw-admission.out"; then
  echo '::error::Main moved during the drill; the GDW proof is not run against a superseded revision.'
  exit 1
fi'''
GDW_AFTER_OWNER = "${{ always() && steps.gdw_owner.outcome == 'success' }}"
DRILL_OWNER_RUN = r'''set -euo pipefail
test "$GITHUB_REF" = refs/heads/main
python3 -B scripts/hf_exact_main_ownership.py \
  --repository "$GITHUB_REPOSITORY" --expected-sha "$GITHUB_SHA" \
  --receipt "$RUNNER_TEMP/restart-drill-source-admission.json" \
  --github-output "$RUNNER_TEMP/restart-drill-source-admission.out"
if ! grep -Fqx 'publish=true' "$RUNNER_TEMP/restart-drill-source-admission.out"; then
  echo '::error::The restart drill must target the current protected main revision.'
  exit 1
fi'''


def assert_restart_drill_contract(source):
    """The manual drill owns every pause/restart proof; it is bounded and fails closed."""
    document = workflow_document(source)
    if set(document.get("on", {})) != {"workflow_dispatch"}:
        raise WorkflowContractError("restart drill must be manual-only")
    # Shared with hf-sync.yml: GitHub never runs the drill alongside a deploy.
    if document.get("concurrency") != {"group": "sync-relock-canonical-a11oy", "cancel-in-progress": False}:
        raise WorkflowContractError("restart drill concurrency")
    if document.get("permissions") != {"contents": "read"}:
        raise WorkflowContractError("restart drill permission scope")
    jobs = document.get("jobs", {})
    if set(jobs) != {"restart-drill"}:
        raise WorkflowContractError("restart drill job set requires review")
    job = jobs["restart-drill"]
    if "continue-on-error" in job or "if" in job or job.get("permissions") != {"contents": "read"}:
        raise WorkflowContractError("restart drill job cannot ignore failure")
    env = job.get("env", {})
    if env.get("HF_TOKEN") != HF_CREDENTIAL or "GDW_OPERATOR_TOKEN" in env:
        raise WorkflowContractError("live proof must be bounded and fail closed: job")
    names = [step.get("name") for step in job.get("steps", [])]
    if names != ["Checkout exact protected source", "Require the drill to target current protected main",
                 "Require the exact current main revision to be the live one",
                 "Set up Python", "Install exact Hugging Face control client",
                 "Prove live Series-A restart persistence (bounded)",
                 "Re-require current protected main before the GDW proof",
                 "Prove live GDW write, drain, and receipt integrity (bounded)",
                 "Admit bounded live proof reports and fail closed",
                 "Upload secret-free restart drill evidence"]:
        raise WorkflowContractError("restart drill step order")
    steps = job["steps"]
    exact_step(steps[0], EXACT_CHECKOUT, "restart drill checkout")
    exact_step(steps[1], {"name": names[1], "shell": "bash", "env": {"GITHUB_TOKEN": "${{ github.token }}"},
                          "run": DRILL_OWNER_RUN}, "restart drill must target current main")
    exact_step(steps[2], {"name": names[2], "shell": "bash", "run": DRILL_LIVE_RUN},
               "restart drill must require the live revision")
    exact_step(steps[4], {"name": names[4], "run": CONTROL_CLIENT}, "restart drill control client")
    exact_step(steps[6], {"name": names[6], "id": "gdw_owner", "if": DRILL_PROOF_CONDITION, "shell": "bash",
                          "env": {"GITHUB_TOKEN": "${{ github.token }}"}, "run": DRILL_GDW_OWNER_RUN},
               "restart drill must re-require current main before gdw")
    for kind, step, step_id, condition, step_env in (
        ("series-a", steps[5], "series_a_proof", None, None),
        ("gdw", steps[7], "gdw_proof", GDW_AFTER_OWNER, {"GDW_OPERATOR_TOKEN": "${{ secrets.GDW_OPERATOR_TOKEN }}"}),
        ("admission", steps[8], None, DRILL_PROOF_CONDITION, {
            "SERIES_A_PROOF_EXIT": "${{ steps.series_a_proof.outputs.exit_code }}",
            "GDW_PROOF_EXIT": "${{ steps.gdw_proof.outputs.exit_code }}"}),
    ):
        key = {"series-a": "series_a"}.get(kind, kind)
        if (compact(step.get("run", "")) != compact(BOUNDED_RUNS[key]) or step.get("if") != condition
                or step.get("env") != step_env or step.get("id") != step_id
                or "continue-on-error" in step or step.get("shell") != "bash"):
            raise WorkflowContractError("live proof must be bounded and fail closed: " + kind)
    paths = tuple(steps[9].get("with", {}).get("path", "").splitlines())
    if paths != ("${{ env.SERIES_A_LIVE_REPORT }}", "${{ env.GDW_LIVE_REPORT }}",
                 "${{ env.LIVE_PROOF_ADMISSION_REPORT }}",
                 "${{ runner.temp }}/restart-drill-source-admission.json",
                 "${{ runner.temp }}/restart-drill-gdw-admission.json"):
        raise WorkflowContractError("live proof reports must be retained")
    if steps[9].get("if") != "${{ always() }}" or steps[9].get("with", {}).get("if-no-files-found") != "error":
        raise WorkflowContractError("live proof reports must be retained")
    scanned = source.replace(ADMITTED_GDW_SECRET_LINE, "", 1)
    for token in ("--blocked-proof", "--managed-acquisition") + REMOVED_CREDENTIAL_TOKENS:
        if token in scanned:
            raise WorkflowContractError("removed credential or donor effect: " + token)
    if source.count("prove_hf_series_a_restart.py") != 1 or source.count("prove_hf_gdw_runtime.py") != 1:
        raise WorkflowContractError("live proof must be bounded and fail closed: duplicate call")
    return job


def assert_blocked_restart_workflow(source):
    document = workflow_document(source)
    jobs = document.get("jobs", {})
    if set(jobs) != {"restart-proof"}:
        raise WorkflowContractError("restart job set requires review")
    job = jobs["restart-proof"]
    blocked = named_step(job, "Fail explicitly while live restart effects remain unreviewed")
    expected = 'python -B scripts/check_hf_manual_prerequisites.py --blocked-proof series-a --source-sha "$GITHUB_SHA" --output "$PROOF_PATH"'
    if compact(blocked.get("run", "")) != expected or "if" in blocked or "continue-on-error" in blocked:
        raise WorkflowContractError("restart workflow must fail explicitly")
    if "continue-on-error" in job:
        raise WorkflowContractError("restart job cannot ignore failure")
    for token in ("secrets.", "HF_TOKEN", "huggingface_hub", "pip install", "prove_hf_series_a_restart.py", "gh issue", "pause_space", "restart_space"):
        if token in source:
            raise WorkflowContractError("restart workflow has unreviewed authority")
    receipt = named_step(job, "Upload immutable blocked restart evidence")
    if receipt.get("if") != "always()" or receipt.get("with", {}).get("if-no-files-found") != "error":
        raise WorkflowContractError("blocked restart receipt missing")


PROOF_SECRET_NAMES = {"prove_hf_series_a_restart.py": "HF_TOKEN", "prove_hf_gdw_runtime.py": "GDW_OPERATOR_TOKEN"}
PERMITTED_PROOF_IMPORTS = {"__future__", "argparse", "base64", "hashlib", "json", "os", "re", "stat", "sys", "time", "datetime", "pathlib", "typing", "urllib", "hf_live_proof_bounds"}
FORBIDDEN_PROVIDER_EFFECTS = ("delete_space_secret", "add_space_secret", "add_space_variable", "delete_space_variable", "delete_space_storage", "request_space_storage", "request_space_hardware", "upload_file", "delete_repo", "factory_reboot=True")
MANAGED_READER_AST_SHA256 = {
    "prove_hf_gdw_runtime.py": "32c1d01f93f7232aa45ff5d7585866bbaa37e28ee3bb27be088a4351bd644888",
    "prove_hf_series_a_restart.py": "abd42697546d52d4cd71c88022bf0e51f9ccdf531f58a87ad62d831533acb508",
    "check_hf_manual_prerequisites.py": "74f9216997efab3b1b5663f7e9c76f9d0b356fc55fff74f4f5dcc5cc6aa22d5e",
}


def fixed_managed_reader_contract(tree, filename):
    """Admit only the reviewed fixed-sibling immutable reader import closure."""
    loaders = [node for node in tree.body if isinstance(node, ast.FunctionDef)
               and node.name == "load_managed_proof_context"]
    if (len(loaders) != 1 or hashlib.sha256(ast.dump(loaders[0], include_attributes=False).encode()).hexdigest()
            != MANAGED_READER_AST_SHA256[filename]):
        raise WorkflowContractError("managed provider reader differs from exact reviewed loader")
    members = set(ast.walk(loaders[0]))
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for item in node.names:
                if item.name.startswith("importlib"):
                    if node not in tree.body or item.name != "importlib.util" or item.asname is not None:
                        raise WorkflowContractError("managed provider import is outside reviewed reader")
                    imports.append(item)
        elif isinstance(node, ast.ImportFrom) and (node.module or "").startswith("importlib"):
            raise WorkflowContractError("managed provider import is outside reviewed reader")
        elif isinstance(node, ast.Name) and node.id == "importlib" and node not in members:
            raise WorkflowContractError("managed provider import is outside reviewed reader")
    if len(imports) != 1:
        raise WorkflowContractError("managed provider import is outside reviewed reader")


def bounded_proof_cli_contract(path):
    """Static boundary of an admitted live proof CLI (and the shared bounds)."""
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    mains = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "main"]
    entries = [node for node in tree.body if isinstance(node, ast.If) and
               ast.dump(node.test) == ast.dump(ast.parse('__name__ == "__main__"', mode="eval").body)]
    if len(mains) != 1 or len(entries) != 1 or tree.body[-1] is not entries[0]:
        raise WorkflowContractError("proof CLI requires one terminal main entrypoint")
    if ast.dump(entries[0].body[0]) != ast.dump(ast.parse("raise SystemExit(main())").body[0]) or len(entries[0].body) != 1:
        raise WorkflowContractError("proof CLI requires one terminal main entrypoint")
    fixed_managed_reader_contract(tree, path.name)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if len(node.names) == 1 and node.names[0].name == "importlib.util":
                continue  # Exact import and every reference were constrained above.
            imported = [name.name.split(".", 1)[0] for name in node.names]
        elif isinstance(node, ast.ImportFrom):
            imported = [(node.module or "").split(".", 1)[0]]
        else:
            continue
        if any(name not in PERMITTED_PROOF_IMPORTS for name in imported):
            raise WorkflowContractError("provider import in bounded proof")
    for token in FORBIDDEN_PROVIDER_EFFECTS:
        if token in source.replace("factory_reboot=False", ""):
            raise WorkflowContractError("unreviewed provider effect: " + token)
    reads = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and ast.unparse(node.func) in {"os.environ.get", "os.getenv", "os.environ.__getitem__"}:
            reads.append(ast.unparse(node.args[0]) if node.args else "")
        if isinstance(node, ast.Subscript) and ast.unparse(node.value) == "os.environ":
            reads.append(ast.unparse(node.slice))
    expected_name = PROOF_SECRET_NAMES[path.name]
    constants = {
        node.targets[0].id: node.value.value for node in tree.body
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
        and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)
    }
    resolved = [constants.get(name, name.strip("'\"")) for name in reads]
    if resolved != [expected_name]:
        raise WorkflowContractError("proof reads an unreviewed environment name")
    return tree


class DeployPathWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = WORKFLOW.read_text(encoding="utf-8")

    def test_actual_deploy_path_contract(self):
        jobs = assert_deploy_path_contract(self.source)
        self.assertNotIn("secrets.", json.dumps(jobs["source-admission"]))

    def test_post_deploy_jobs_cannot_restart_pause_or_write_variables(self):
        for job_name, marker in (
            ("runtime-config", '            "${mode[@]}" --output "$GDW_CONFIG_REPORT"\n'),
            ("relock", "            --retry-seconds 10\n"),
        ):
            for injected in (
                "          python -B scripts/prove_hf_series_a_restart.py --source-sha \"$GITHUB_SHA\" --output /tmp/p.json\n",
                "          python -B scripts/prove_hf_gdw_runtime.py --source-sha \"$GITHUB_SHA\" --output /tmp/p.json\n",
                "          python -c 'import huggingface_hub; huggingface_hub.HfApi().restart_space(\"SZLHOLDINGS/a11oy\")'\n",
                "          python .github/scripts/publish_readiness_verdict.py --input x --repo-id y\n",
                "          python .github/scripts/publish_readiness_verdict.py\n",
            ):
                with self.subTest(job=job_name, injected=injected):
                    self.assertIn(marker, self.source)
                    changed = self.source.replace(marker, marker + injected, 1)
                    with self.assertRaises(WorkflowContractError):
                        assert_deploy_path_contract(changed)

    def test_readiness_verdict_gate_stays_fail_closed_without_a_space_write(self):
        cases = (
            ("          --validate-only\n", '          --repo-id "$CANONICAL_SPACE"\n', "post-deploy restart or variable effect"),
            ('          --expected-source-sha "$SOURCE_SHA"\n', '          --expected-source-sha "$SOURCE_SHA" || true\n', "readiness verdict gate"),
            ("      - name: Validate the source-bound verdict without a Space write\n",
             "      - name: Validate the source-bound verdict without a Space write\n        continue-on-error: true\n", "step failure bypass"),
        )
        for original, replacement, diagnostic in cases:
            with self.subTest(replacement=replacement):
                self.assertIn(original, self.source)
                with self.assertRaisesRegex(WorkflowContractError, re.escape(diagnostic)):
                    assert_deploy_path_contract(self.source.replace(original, replacement, 1))

    def test_preflight_classification_and_convergence_cannot_be_weakened(self):
        cases = (
            ("python -B .github/scripts/resume_hf_space.py", "python -B .github/scripts/resume_hf_space.py --restart", "preflight classification"),
            ('          python -B scripts/configure_hf_series_a_runtime.py \\\n            --repo-id "$CANONICAL_SPACE" --bucket "SZLHOLDINGS/szl-evidence" \\\n            --output "$RUNTIME_CONFIG_REPORT"\n',
             '          true\n', "preflight convergence"),
            ('--receipt "$RUNNER_TEMP/preflight-series-config-admission.json"',
             '--receipt /tmp/forged.json', "preflight convergence"),
            ('--receipt "$RUNNER_TEMP/preflight-gdw-config-admission.json"',
             '--receipt /tmp/forged.json', "preflight convergence"),
            ("echo 'converged=true' >> \"$GITHUB_OUTPUT\"", "echo 'converged=true' >> \"$GITHUB_OUTPUT\" || true", "preflight convergence"),
            ('--receipt "$RUNNER_TEMP/preflight-source-admission.json"', '--receipt /tmp/forged.json', "re-admit current main"),
            ("      publish: ${{ steps.window.outputs.open == 'true' && steps.owner.outputs.publish == 'true' }}\n", "      publish: ${{ steps.owner.outputs.publish == 'true' }}\n", "output scope"),
            ("      contents: read\n    outputs:\n      publish: ${{ steps.window", "      contents: write\n    outputs:\n      publish: ${{ steps.window", "permission"),
            ("if [ \"${STAGE:-}\" = 'PAUSED' ] ||", "if true ||", "deploy window"),
            ("        id: converge\n        if: ${{ steps.window.outputs.open == 'true' }}\n", "        id: converge\n", "preflight convergence"),
            ("        id: runtime\n        if: ${{ steps.admit.outputs.publish == 'true' }}\n", "        id: runtime\n", "preflight classification"),
            ('--receipt "$RUNNER_TEMP/preflight-admission.json"', '--receipt /tmp/forged.json', "admit current main before any provider effect"),
            ("        type: boolean\n        default: false\n\npermissions:", "        type: boolean\n        default: true\n\npermissions:", "deploy window must default closed"),
            ("python -B .github/scripts/await_hf_runtime_serving.py", "true", "runtime-config must await"),
            ('restart-space: ${{ needs.preflight.outputs.restart_required == \'true\' }}', "restart-space: true", "start the Space once"),
            ("require-default-branch-tip: true", "require-default-branch-tip: false", "start the Space once"),
            ("mode=(--check-only)", "mode=(--check-only --unverified)", "runtime-config must verify"),
        )
        for original, replacement, diagnostic in cases:
            with self.subTest(diagnostic=diagnostic, replacement=replacement):
                self.assertIn(original, self.source)
                with self.assertRaisesRegex(WorkflowContractError, re.escape(diagnostic)):
                    assert_deploy_path_contract(self.source.replace(original, replacement, 1))

    def test_relock_must_revalidate_this_runs_verdict(self):
        cases = (
            ('            --readiness-verdict-file "$RUNNER_TEMP/run-readiness-verdict.json" \\\n', ""),
            ("          RUN_READINESS_VERDICT: ${{ needs.readiness-verdict.outputs.verdict }}\n",
             "          RUN_READINESS_VERDICT: '{}'\n"),
        )
        for original, replacement in cases:
            with self.subTest(replacement=replacement):
                self.assertIn(original, self.source)
                with self.assertRaisesRegex(WorkflowContractError, "relock must re-validate"):
                    assert_deploy_path_contract(self.source.replace(original, replacement, 1))
        output = "    outputs:\n      verdict: ${{ steps.gate.outputs.verdict }}\n"
        self.assertIn(output, self.source)
        with self.assertRaisesRegex(WorkflowContractError, "hand its verdict to relock"):
            assert_deploy_path_contract(self.source.replace(output, "", 1))

    def test_superseded_relock_is_neutral_but_failed_verification_stays_red(self):
        cases = (
            ('            exit "$code"\n          fi\n          if [ "${CURRENT_MAIN', '            exit 0\n          fi\n          if [ "${CURRENT_MAIN'),
            ("            exit 0\n          fi\n          echo 'Canonical A11oy is source-bound", "            exit 3\n          fi\n          echo 'Canonical A11oy is source-bound"),
            ("CURRENT_MAIN:-false", "CURRENT_MAIN:-true"),
        )
        for original, replacement in cases:
            with self.subTest(replacement=replacement):
                self.assertIn(original, self.source)
                with self.assertRaisesRegex(WorkflowContractError, "actual verification exit must be enforced"):
                    assert_deploy_path_contract(self.source.replace(original, replacement, 1))

    def test_credential_forwarding_donor_and_issue_mutations_stay_removed(self):
        for token in ("DOCS_READ_TOKEN", "--github-read-token", "--operator-token", "--capacity-donor",
                      "gh issue", "issues: write", "add_space_secret", "delete_space_secret", "OPERATOR_TOKEN"):
            with self.subTest(token=token), self.assertRaisesRegex(WorkflowContractError, "removed credential or donor effect"):
                assert_deploy_path_contract(self.source + "\n# " + token + "\n")

    def test_vertical_publication_keeps_owned_source_and_plan_gates(self):
        before = "        if: ${{ steps.exact_main_owner.outputs.publish == 'true' && steps.vertical_plan.outputs.vertical_flagships == 'true' }}\n        run: python scripts/hf_publish_vertical_flagships_v4.py\n"
        self.assertIn(before, self.source)
        changed = self.source.replace(before, "        run: python scripts/hf_publish_vertical_flagships_v4.py\n", 1)
        with self.assertRaisesRegex(WorkflowContractError, "vertical source and plan gate"):
            assert_deploy_path_contract(changed)


class RestartDrillWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = DRILL_WORKFLOW.read_text(encoding="utf-8")

    def test_actual_restart_drill_contract(self):
        assert_restart_drill_contract(self.source)

    def test_restart_drill_is_never_an_automatic_writer(self):
        for trigger in ("  push:\n    branches: [main]\n", "  schedule:\n    - cron: '0 3 * * 1'\n",
                        "  workflow_run:\n    workflows: [Sync and Relock Canonical Hugging Face Space]\n"):
            with self.subTest(trigger=trigger):
                changed = self.source.replace("on:\n  workflow_dispatch: {}\n", "on:\n  workflow_dispatch: {}\n" + trigger, 1)
                self.assertNotEqual(changed, self.source)
                with self.assertRaisesRegex(WorkflowContractError, "manual-only"):
                    assert_restart_drill_contract(changed)

    def test_weakened_bounded_live_proof_steps_are_rejected(self):
        cases = (
            ('            --series-a-proof "$SERIES_A_LIVE_REPORT" \\\n', '', "gdw"),
            ('--run-context "${{ github.run_id }}:${{ github.run_attempt }}"', '--run-context "1:1"', "series-a"),
            ('          exit "$code"\n\n      # Writes only', '          exit 0\n\n      # Writes only', "series-a"),
            ('--origin "$CANONICAL_ORIGIN" \\\n            --source-sha', '--origin "https://a-11-oy.com" \\\n            --source-sha', "gdw"),
            ('--admit-live-proofs \\', '--admit-live-proofs || true \\', "admission"),
            ("        id: gdw_proof\n", "        id: gdw_proof\n        continue-on-error: true\n", "gdw"),
            ("            ${{ env.LIVE_PROOF_ADMISSION_REPORT }}\n", "", "retained"),
            ("      LIVE_PROOF_ADMISSION_REPORT: /tmp/live-proof-admission.json\n",
             "      LIVE_PROOF_ADMISSION_REPORT: /tmp/live-proof-admission.json\n      GDW_OPERATOR_TOKEN: ${{ secrets.GDW_OPERATOR_TOKEN }}\n", "job"),
            ("          if ! grep -Fqx 'publish=true'", "          if false && ! grep -Fqx 'publish=true'", "current main"),
            ("    timeout-minutes: 45\n", "    timeout-minutes: 45\n    continue-on-error: true\n", "cannot ignore failure"),
            ("  group: sync-relock-canonical-a11oy\n", "  group: restart-drill-canonical-a11oy\n", "concurrency"),
            ("        if: ${{ always() && steps.gdw_owner.outcome == 'success' }}\n",
             "        if: ${{ always() && (steps.series_a_proof.outcome == 'success' || steps.series_a_proof.outcome == 'failure') }}\n", "gdw"),
            ("--receipt \"$RUNNER_TEMP/restart-drill-gdw-admission.json\"", "--receipt /tmp/forged.json", "re-require current main"),
            ("          if str(build.get(\"revision\") or \"\").lower() != sha:", "          if False:", "live revision"),
        )
        for original, replacement, diagnostic in cases:
            with self.subTest(diagnostic=diagnostic, original=original):
                self.assertIn(original, self.source)
                with self.assertRaisesRegex(WorkflowContractError, diagnostic):
                    assert_restart_drill_contract(self.source.replace(original, replacement, 1))

    def test_blocked_proof_fallback_or_managed_selector_is_rejected(self):
        for before, after in (
            ("python -B scripts/prove_hf_gdw_runtime.py \\", "python -B scripts/check_hf_manual_prerequisites.py --blocked-proof gdw \\"),
            ('--origin "$CANONICAL_ORIGIN" \\\n            --source-sha',
             '--origin "$CANONICAL_ORIGIN" \\\n            --managed-acquisition "$RUNNER_TEMP/gdw-durable-acquisition.json" \\\n            --source-sha'),
        ):
            with self.subTest(after=after):
                self.assertIn(before, self.source)
                with self.assertRaises(WorkflowContractError):
                    assert_restart_drill_contract(self.source.replace(before, after, 1))

    def test_standalone_blocked_restart_workflow_has_no_provider_or_secret_path(self):
        source = RESTART_WORKFLOW.read_text(encoding="utf-8")
        assert_blocked_restart_workflow(source)
        cases = (
            ("--blocked-proof series-a", "--blocked-proof series-a || true", "must fail explicitly"),
            ("      - name: Fail explicitly while live restart effects remain unreviewed\n", "      - name: Fail explicitly while live restart effects remain unreviewed\n        continue-on-error: true\n", "must fail explicitly"),
            ("    timeout-minutes: 25\n", "    timeout-minutes: 25\n    continue-on-error: true\n", "cannot ignore failure"),
            ("      PROOF_PATH:", "      HF_TOKEN: ${{ secrets.HF_TOKEN }}\n      PROOF_PATH:", "unreviewed authority"),
        )
        for original, replacement, diagnostic in cases:
            with self.subTest(diagnostic=diagnostic), self.assertRaisesRegex(WorkflowContractError, diagnostic):
                assert_blocked_restart_workflow(source.replace(original, replacement, 1))


class PureAggregateWorkflowBoundaryTests(unittest.TestCase):
    def checker_namespace(self):
        # Legacy/predeploy remains pure parsing. Explicit managed live admission
        # can use only the exact reviewed immutable-reader sibling, never an SDK
        # import or a generic dynamic loader added elsewhere in the aggregate.
        tree = ast.parse(CHECKER.read_text(encoding="utf-8"), filename=str(CHECKER))
        fixed_managed_reader_contract(tree, CHECKER.name)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                self.assertTrue(all(item.name in {"argparse", "json", "re", "time", "importlib.util"} for item in node.names))
            elif isinstance(node, ast.ImportFrom):
                self.assertEqual(node.module, "pathlib")
        namespace = {"__name__": "offline_manual_prerequisites", "__file__": str(CHECKER)}
        exec(compile(tree, str(CHECKER), "exec"), namespace)
        return namespace

    def test_each_workflow_blocked_proof_kind_retains_its_schema_without_effect_evidence(self):
        namespace = self.checker_namespace()
        for kind, schema, value_field in (("series-a", PROOFS[0][1], PROOFS[0][2]), ("gdw", PROOFS[1][1], PROOFS[1][2])):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temporary:
                output = Path(temporary) / "blocked.json"
                code = namespace["main"](["--blocked-proof", kind, "--source-sha", "../private?token=must-not-echo", "--output", str(output)])
                encoded = output.read_text(encoding="utf-8")
                report = json.loads(encoded)
                self.assertEqual(code, 1)
                self.assertEqual(report["schema"], schema)
                self.assertEqual(report["status"], "FAIL")
                self.assertIs(report["ok"], False)
                self.assertEqual(report["evidence"], {})
                self.assertEqual(report["credential_authority_state"], "UNKNOWN")
                self.assertEqual(report["source_revision"], "UNVALIDATED")
                self.assertIs(report[value_field], False)
                other_field = "credential_values_recorded" if kind == "series-a" else "secret_values_recorded"
                self.assertNotIn(other_field, report)
                self.assertNotIn("must-not-echo", encoded)
                self.assertLess(len(encoded.encode()), 16 * 1024)

    def test_unknown_and_forged_reports_never_admit_effects(self):
        namespace = self.checker_namespace()
        for forged in (False, True):
            with self.subTest(forged=forged), tempfile.TemporaryDirectory() as temporary:
                base = Path(temporary)
                series, gdw, output = base / "series.json", base / "gdw.json", base / "aggregate.json"
                for target, schema in ((series, "szl.hf-series-a-runtime-config/v1"), (gdw, "szl.hf-gdw-runtime-config/v1")):
                    report = {"schema": schema, "repo_id": "SZLHOLDINGS/a11oy", "state": "SETUP_REQUIRED", "credential_authority_state": "UNKNOWN", "converged": False, "secret_values_read": False, "secret_values_written": False}
                    if forged:
                        report.update(state="PASS", credential_authority_state="VERIFIED", converged=True, approved=True, signature="untrusted-fixture", token="must-not-echo")
                    target.write_text(json.dumps(report), encoding="utf-8")
                code = namespace["main"](["--series-a", str(series), "--gdw", str(gdw), "--series-a-exit", "1", "--gdw-exit", "1", "--source-sha", "a" * 40, "--output", str(output)])
                raw = output.read_text(encoding="utf-8")
                result = json.loads(raw)
                self.assertEqual(code, 1)
                self.assertEqual(result["state"], "SETUP_REQUIRED")
                self.assertEqual(result["credential_authority_state"], "UNKNOWN")
                self.assertIs(result["converged"], False)
                self.assertEqual(result["series_a"]["report_valid"], not forged)
                self.assertEqual(result["gdw"]["report_valid"], not forged)
                self.assertNotIn("must-not-echo", raw)
                self.assertNotIn("approved", result)
                self.assertNotIn("publish", result)
                self.assertLess(len(raw.encode()), 16 * 1024)

    def test_missing_malformed_duplicate_oversized_and_wrongly_typed_reports_fail_closed(self):
        namespace = self.checker_namespace()
        fixture = {"schema": "szl.hf-series-a-runtime-config/v1", "repo_id": "SZLHOLDINGS/a11oy", "state": "SETUP_REQUIRED", "credential_authority_state": "UNKNOWN", "converged": False, "secret_values_read": False, "secret_values_written": False}
        raw = json.dumps(fixture)
        cases = (
            ("missing", None, "1"),
            ("malformed", '{"poison":"must-not-echo",', "1"),
            ("duplicate", raw[:-1] + ', "schema":"szl.hf-series-a-runtime-config/v1", "poison":"must-not-echo"}', "1"),
            ("oversized", json.dumps(dict(fixture, poison="must-not-echo" + "x" * (16 * 1024))), "1"),
            ("converged-integer", json.dumps(dict(fixture, converged=0, poison="must-not-echo")), "1"),
            ("secret-read-integer", json.dumps(dict(fixture, secret_values_read=0, poison="must-not-echo")), "1"),
            ("secret-write-integer", json.dumps(dict(fixture, secret_values_written=0, poison="must-not-echo")), "1"),
            ("successful-exit", raw, "0"),
            ("non-object", '["must-not-echo"]', "1"),
        )
        for name, value, exit_code in cases:
            with self.subTest(case=name), tempfile.TemporaryDirectory() as temporary:
                base = Path(temporary)
                series, gdw, output = base / "series.json", base / "gdw.json", base / "aggregate.json"
                if value is not None:
                    series.write_text(value, encoding="utf-8")
                gdw.write_text(json.dumps(dict(fixture, schema="szl.hf-gdw-runtime-config/v1")), encoding="utf-8")
                code = namespace["main"](["--series-a", str(series), "--gdw", str(gdw), "--series-a-exit", exit_code, "--gdw-exit", "1", "--source-sha", "a" * 40, "--output", str(output)])
                encoded = output.read_text(encoding="utf-8")
                report = json.loads(encoded)
                self.assertEqual(code, 1)
                self.assertEqual(report["series_a"], {"report_valid": False, "state": "SETUP_REQUIRED", "credential_authority_state": "UNKNOWN"})
                self.assertEqual(report["gdw"]["report_valid"], True)
                self.assertEqual(report["state"], "SETUP_REQUIRED")
                self.assertEqual(report["credential_authority_state"], "UNKNOWN")
                self.assertIs(report["converged"], False)
                self.assertNotIn("must-not-echo", encoded)
                self.assertLess(len(encoded.encode()), 16 * 1024)
        with tempfile.TemporaryDirectory() as temporary:
            report = Path(temporary) / "report.json"
            report.write_text(raw, encoding="utf-8")
            self.assertIs(namespace["inspect_report"](report, fixture["schema"], True)["report_valid"], False)


PINNED_FINGERPRINT = "8e2d106c6995e11dbf7cbedfa9e5800bb50c82a635756e40dcd330364f6ea8ba"


def verified_report(schema):
    authority = {
        "schema": "szl.hf-installed-authority/v1", "credential_authority_state": "VERIFIED",
        "diagnostic_code": "INSTALLED_AUTHORITY_VERIFIED", "public_variable_collision": False,
        "signing_secret_name_present": True, "secret_values_read": False, "secret_values_written": False,
        "signing": {"state": "VERIFIED_PINNED_RUNTIME_KEY", "served_fingerprint_sha256": PINNED_FINGERPRINT,
                    "pinned_fingerprint_sha256": PINNED_FINGERPRINT},
        "gdw": {"state": "NAME_PRESENT_RUNTIME_PROVEN_DOWNSTREAM", "blocking": False},
        "github_public_reader": {"state": "PUBLIC_ANONYMOUS", "blocking": False},
    }
    return {"schema": schema, "repo_id": "SZLHOLDINGS/a11oy", "state": "READY",
            "credential_authority_state": "VERIFIED", "diagnostic_code": "INSTALLED_AUTHORITY_VERIFIED",
            "converged": True, "missing_secret_names": [], "installed_authority": authority,
            "secret_values_read": False, "secret_values_written": False}


class VerifiedAuthorityAggregateTests(unittest.TestCase):
    checker_namespace = PureAggregateWorkflowBoundaryTests.checker_namespace
    SERIES = "szl.hf-series-a-runtime-config/v1"
    GDW = "szl.hf-gdw-runtime-config/v1"

    def run_aggregate(self, series_report, gdw_report, series_exit="0", gdw_exit="0", source="a" * 40):
        namespace = self.checker_namespace()
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            series, gdw, output = base / "series.json", base / "gdw.json", base / "aggregate.json"
            series.write_text(series_report if isinstance(series_report, str) else json.dumps(series_report), encoding="utf-8")
            gdw.write_text(gdw_report if isinstance(gdw_report, str) else json.dumps(gdw_report), encoding="utf-8")
            code = namespace["main"](["--series-a", str(series), "--gdw", str(gdw), "--series-a-exit", series_exit,
                                      "--gdw-exit", gdw_exit, "--source-sha", source, "--output", str(output)])
            raw = output.read_text(encoding="utf-8")
        return code, json.loads(raw), raw

    def test_two_genuine_verified_reports_admit_provider_writes(self):
        code, result, raw = self.run_aggregate(verified_report(self.SERIES), verified_report(self.GDW))
        self.assertEqual(code, 0)
        self.assertEqual(result["state"], "READY")
        self.assertEqual(result["credential_authority_state"], "VERIFIED")
        self.assertIs(result["converged"], True)
        self.assertEqual(result["diagnostic_code"], "INSTALLED_AUTHORITY_VERIFIED")
        self.assertEqual(result["series_a"], {"report_valid": True, "state": "READY", "credential_authority_state": "VERIFIED"})
        self.assertLess(len(raw.encode()), 16 * 1024)

    def test_any_weakened_verified_report_stays_setup_required(self):
        def mutate(path, value):
            report = verified_report(self.SERIES)
            target = report
            for key in path[:-1]:
                target = target[key]
            if value is KeyError:
                del target[path[-1]]
            else:
                target[path[-1]] = value
            return report

        cases = (
            ("nonzero-exit", verified_report(self.SERIES), "1"),
            ("bool-exit", verified_report(self.SERIES), "True"),
            ("state", mutate(("state",), "PASS"), "0"),
            ("authority", mutate(("credential_authority_state",), "UNKNOWN"), "0"),
            ("converged-int", mutate(("converged",), 1), "0"),
            ("diagnostic", mutate(("diagnostic_code",), "INSTALLED_AUTHORITY_UNKNOWN"), "0"),
            ("missing-name", mutate(("missing_secret_names",), ["SZL_COSIGN_PRIVATE_PEM"]), "0"),
            ("no-authority", mutate(("installed_authority",), KeyError), "0"),
            ("wrong-served-key", mutate(("installed_authority", "signing", "served_fingerprint_sha256"), "0" * 64), "0"),
            ("wrong-pin", mutate(("installed_authority", "signing", "pinned_fingerprint_sha256"), "0" * 64), "0"),
            ("not-installed", mutate(("installed_authority", "signing", "state"), "SIGNING_KEY_NOT_INSTALLED"), "0"),
            ("gdw-missing", mutate(("installed_authority", "gdw", "blocking"), True), "0"),
            ("collision", mutate(("installed_authority", "public_variable_collision"), True), "0"),
            ("secret-read", mutate(("secret_values_read",), True), "0"),
            ("inner-secret-read", mutate(("installed_authority", "secret_values_read"), 0), "0"),
            ("duplicate", json.dumps(verified_report(self.SERIES))[:-1] + ', "state": "READY"}', "0"),
            ("oversized", mutate(("padding",), "x" * (16 * 1024)), "0"),
            ("wrong-schema", verified_report(self.GDW), "0"),
        )
        for name, report, exit_code in cases:
            with self.subTest(case=name):
                if exit_code == "True":
                    namespace = self.checker_namespace()
                    with tempfile.TemporaryDirectory() as temporary:
                        path = Path(temporary) / "r.json"
                        path.write_text(json.dumps(report), encoding="utf-8")
                        self.assertIs(namespace["inspect_report"](path, self.SERIES, True)["report_valid"], False)
                    continue
                code, result, _ = self.run_aggregate(report, verified_report(self.GDW), series_exit=exit_code)
                self.assertEqual(code, 1)
                self.assertEqual(result["state"], "SETUP_REQUIRED")
                self.assertEqual(result["credential_authority_state"], "UNKNOWN")
                self.assertIs(result["converged"], False)
                self.assertNotEqual(result["series_a"]["state"], "READY")

    def test_one_verified_report_or_invalid_source_is_not_enough(self):
        unknown = {"schema": self.GDW, "repo_id": "SZLHOLDINGS/a11oy", "state": "SETUP_REQUIRED",
                   "credential_authority_state": "UNKNOWN", "converged": False,
                   "secret_values_read": False, "secret_values_written": False}
        code, result, _ = self.run_aggregate(verified_report(self.SERIES), unknown, gdw_exit="1")
        self.assertEqual((code, result["state"]), (1, "SETUP_REQUIRED"))
        self.assertEqual(result["series_a"]["state"], "READY")
        code, result, _ = self.run_aggregate(verified_report(self.SERIES), verified_report(self.GDW), source="../x")
        self.assertEqual((code, result["state"], result["source_revision"]), (1, "SETUP_REQUIRED", "UNVALIDATED"))


class BoundedProofCLIBoundaryTests(unittest.TestCase):
    def test_bounded_proof_modules_have_no_provider_client_or_other_secret(self):
        for filename, _schema, _field in PROOFS:
            with self.subTest(script=filename):
                bounded_proof_cli_contract(ROOT / "scripts" / filename)
        bounds_source = (ROOT / "scripts/hf_live_proof_bounds.py").read_text(encoding="utf-8")
        for token in FORBIDDEN_PROVIDER_EFFECTS + ("os.environ",):
            self.assertNotIn(token, bounds_source.replace("factory_reboot=False", ""))

    def test_provider_import_is_a_rejected_negative_fixture(self):
        path = ROOT / "scripts" / PROOFS[0][0]
        changed = path.read_text(encoding="utf-8").replace("import argparse\n", "import argparse\nfrom huggingface_hub import HfApi\n", 1)
        with mock.patch.object(Path, "read_text", return_value=changed), self.assertRaisesRegex(WorkflowContractError, "provider import"):
            bounded_proof_cli_contract(path)

    def test_extra_secret_read_is_a_rejected_negative_fixture(self):
        path = ROOT / "scripts" / PROOFS[1][0]
        source = path.read_text(encoding="utf-8")
        changed = source.replace("    args = parser.parse_args(argv)\n", "    args = parser.parse_args(argv)\n    os.environ.get('HF_TOKEN')\n", 1)
        self.assertNotEqual(changed, source)
        with mock.patch.object(Path, "read_text", return_value=changed), self.assertRaisesRegex(WorkflowContractError, "unreviewed environment name"):
            bounded_proof_cli_contract(path)

    def test_secret_deletion_is_a_rejected_negative_fixture(self):
        path = ROOT / "scripts" / PROOFS[0][0]
        changed = path.read_text(encoding="utf-8") + "\n# api.delete_space_secret(repo_id=x, key=y)\n"
        with mock.patch.object(Path, "read_text", return_value=changed), self.assertRaisesRegex(WorkflowContractError, "unreviewed provider effect"):
            bounded_proof_cli_contract(path)

    def test_actual_cli_without_secret_is_setup_required_before_any_network(self):
        for filename, schema, value_field in PROOFS:
            path = ROOT / "scripts" / filename
            secret_name = PROOF_SECRET_NAMES[filename]
            with self.subTest(script=filename), tempfile.TemporaryDirectory() as temporary:
                output = Path(temporary) / "proof.json"
                attempts = []

                def forbidden(*args, **kwargs):
                    attempts.append("network")
                    raise AssertionError("SETUP_REQUIRED crossed the network boundary")

                class OnlyReviewedName(dict):
                    default_names = {"LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG", "COLUMNS", "LINES", "NO_COLOR", "FORCE_COLOR", "PYTHON_COLORS", "TERM"}

                    def get(self, key, default=None):
                        if key in self.default_names or key == secret_name:
                            return default
                        return forbidden()

                    def __getitem__(self, key):
                        if key in self.default_names:
                            raise KeyError(key)
                        return forbidden()

                    def __contains__(self, key):
                        return False

                argv = [str(path), "--source-sha", "a" * 40, "--output", str(output)]
                saved_path = list(sys.path)
                captured = io.StringIO()
                environment = OnlyReviewedName()
                try:
                    with mock.patch.object(sys, "argv", argv), mock.patch.object(os, "environ", environment), \
                            mock.patch.object(os, "getenv", environment.get), \
                            mock.patch("urllib.request.OpenerDirector.open", forbidden), \
                            mock.patch("urllib.request.urlopen", forbidden), redirect_stdout(captured):
                        with self.assertRaises(SystemExit) as exit_result:
                            exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"),
                                 {"__name__": "__main__", "__file__": str(path)})
                finally:
                    sys.path[:] = saved_path
                self.assertEqual(exit_result.exception.code, 1)
                raw = output.read_text(encoding="utf-8")
                result = json.loads(raw)
                self.assertEqual(captured.getvalue(), raw)
                self.assertEqual(result["schema"], schema)
                self.assertEqual(result["state"], "SETUP_REQUIRED")
                self.assertEqual(result["missing_secret_names"], [secret_name])
                self.assertIs(result["ok"], False)
                self.assertEqual(result["evidence"], {})
                self.assertEqual(result["credential_authority_state"], "UNKNOWN")
                self.assertIs(result[value_field], False)
                self.assertEqual(attempts, [])
                self.assertLess(len(raw.encode()), 16 * 1024)

    def test_wrong_destination_or_space_fails_before_credentials(self):
        cases = (
            ("prove_hf_series_a_restart.py", ["--repo-id", "untrusted/fixture"], "SPACE_SCOPE_REJECTED"),
            ("prove_hf_series_a_restart.py", ["--origin", "https://untrusted.invalid/?token=must-not-echo"], "DESTINATION_REJECTED"),
            ("prove_hf_gdw_runtime.py", ["--origin", "https://untrusted.invalid/?token=must-not-echo"], "DESTINATION_REJECTED"),
        )
        for filename, extra, code in cases:
            path = ROOT / "scripts" / filename
            with self.subTest(script=filename, code=code), tempfile.TemporaryDirectory() as temporary:
                output = Path(temporary) / "proof.json"

                def forbidden(*args, **kwargs):
                    raise AssertionError("credential or network access before scope check")

                class NoCredentials(dict):
                    default_names = {"LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG", "COLUMNS", "LINES", "NO_COLOR", "FORCE_COLOR", "PYTHON_COLORS", "TERM"}

                    def get(self, key, default=None):
                        if key in self.default_names:
                            return default
                        return forbidden()

                    def __contains__(self, key):
                        return False

                argv = [str(path), "--source-sha", "a" * 40, "--output", str(output), *extra]
                saved_path = list(sys.path)
                environment = NoCredentials()
                try:
                    with mock.patch.object(sys, "argv", argv), mock.patch.object(os, "environ", environment), \
                            mock.patch.object(os, "getenv", environment.get), \
                            mock.patch("urllib.request.OpenerDirector.open", forbidden), redirect_stdout(io.StringIO()):
                        with self.assertRaises(SystemExit) as exit_result:
                            exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"),
                                 {"__name__": "__main__", "__file__": str(path)})
                finally:
                    sys.path[:] = saved_path
                self.assertEqual(exit_result.exception.code, 1)
                raw = output.read_text(encoding="utf-8")
                self.assertEqual(json.loads(raw)["diagnostic_code"], code)
                self.assertNotIn("must-not-echo", raw)


class LiveProofAdmissionCheckerTests(unittest.TestCase):
    def checker(self):
        namespace = {"__name__": "offline_live_proof_admission", "__file__": str(CHECKER)}
        exec(compile(CHECKER.read_text(encoding="utf-8"), str(CHECKER), "exec"), namespace)
        return namespace

    def run_admission(self, series_raw, gdw_raw, series_exit="0", gdw_exit="0", source="a" * 40):
        namespace = self.checker()
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            series, gdw, output = base / "s.json", base / "g.json", base / "out.json"
            if series_raw is not None:
                series.write_text(series_raw, encoding="utf-8")
            if gdw_raw is not None:
                gdw.write_text(gdw_raw, encoding="utf-8")
            code = namespace["main"]([
                "--admit-live-proofs", "--series-a-proof", str(series), "--series-a-proof-exit", series_exit,
                "--gdw-proof", str(gdw), "--gdw-proof-exit", gdw_exit,
                "--source-sha", source, "--output", str(output),
            ])
            return code, json.loads(output.read_text(encoding="utf-8")), output.read_text(encoding="utf-8")

    def blocked(self, kind):
        namespace = self.checker()
        return json.dumps(namespace["blocked_proof_report"](kind, "a" * 40))

    def test_blocked_or_missing_reports_are_never_admitted(self):
        for series, gdw in ((self.blocked("series-a"), self.blocked("gdw")), (None, None), ("", "")):
            code, result, _ = self.run_admission(series, gdw)
            self.assertEqual((code, result["state"], result["admitted"]), (1, "NOT_ADMITTED", False))

    def test_malformed_duplicate_oversized_and_wrong_schema_reports_fail_closed(self):
        fixture = {"schema": "szl.series-a-restart-proof/v1", "repo_id": "SZLHOLDINGS/a11oy", "status": "PASS", "ok": True}
        raw = json.dumps(fixture)
        for label, value in (
            ("malformed", "{"),
            ("duplicate", raw[:-1] + ', "status": "PASS", "poison": "must-not-echo"}'),
            ("oversized", json.dumps(dict(fixture, padding="x" * (17 * 1024)))),
            ("array", "[]"),
            ("wrong_schema", json.dumps(dict(fixture, schema="szl.other/v1"))),
            ("wrong_space", json.dumps(dict(fixture, repo_id="SZLHOLDINGS/other"))),
        ):
            with self.subTest(label=label):
                code, result, encoded = self.run_admission(value, value)
                self.assertEqual(code, 1)
                self.assertEqual(result["series_a"], {"report_valid": False, "state": "UNPROVEN"})
                self.assertNotIn("must-not-echo", encoded)

    def test_non_integer_or_nonzero_exit_and_invalid_source_are_not_admitted(self):
        for series_exit, source in (("1", "a" * 40), ("0", "../x")):
            code, result, _ = self.run_admission(self.blocked("series-a"), self.blocked("gdw"), series_exit=series_exit, source=source)
            self.assertEqual(code, 1)
            self.assertFalse(result["admitted"])


class ManagedLiveProofAdmissionTests(unittest.TestCase):
    def fixtures(self):
        import importlib.util
        from types import SimpleNamespace
        checker = LiveProofAdmissionCheckerTests().checker()
        helper_path = ROOT / "scripts/configure_hf_gdw_runtime.py"
        spec = importlib.util.spec_from_file_location("aggregate_actual_managed_context", helper_path)
        helper = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(helper)
        admission = {"source": {"revision": "a" * 40}, "qualification": {"report_sha256": "b" * 64},
            "snapshots": {"gdw": {"generation": "c" * 32}, "series_a": {"generation": "store_" + "d" * 32}}}
        records, calls = {}, []
        def read_at(revision, operation, deadline):
            calls.append((revision, operation))
            head = records[(revision, operation)]
            return head, head.body
        backend = SimpleNamespace(read_at=read_at)
        context = helper.ManagedProofContext(admission, "f" * 64, backend,
                                             deadline=helper.time.monotonic() + 10)
        witnesses = []
        for index in (1, 2, 3):
            revision, operation = str(index) * 40, str(index) * 32
            value = {"operation_id": operation, "kind": "COMMIT", "epoch": index,
                "qualification_sha256": "f" * 64, "source_revision": "a" * 40,
                "snapshots": admission["snapshots"]}
            records[(revision, operation)] = SimpleNamespace(revision=revision, value=value,
                                                              body=("native-head-" + str(index)).encode())
            witnesses.append({"schema": "szl.gdw-managed-runtime/v1", "mode": helper.MANAGED_MODE,
                **context.identity, "dataset_revision": revision, "operation_id": operation,
                "writer_epoch": index, "actual_host_full_state_ack_ms": 500,
                "startup_state": "RESTORED_AND_ACKNOWLEDGED", "throughput_claim": "NOT_CLAIMED"})
        bounds = {"max_attempts": 8, "retry_window_seconds": 600, "deadline_seconds": 600,
            "transient_http_statuses": [429, 502, 503, 504], "redirects_allowed": False,
            "destinations": [checker["CANONICAL_ORIGIN"], "https://huggingface.co/api/spaces/SZLHOLDINGS/a11oy"]}
        common = {"repo_id": "SZLHOLDINGS/a11oy", "status": "PASS", "ok": True, "state": "PROVEN",
            "diagnostic_code": "LIVE_PROOF_PASSED", "origin": checker["CANONICAL_ORIGIN"],
            "source_revision": "a" * 40, "credential_authority_state": "VERIFIED", "bounds": bounds}
        series = {**common, "schema": checker["LIVE_PROOF_SCHEMAS"]["series_a"],
            "secret_values_read": False, "secret_values_recorded": False,
            "proof": dict.fromkeys(checker["SERIES_A_PROOF_FLAGS"], True),
            "durability_running": {"stage": "RUNNING", "git_sha": "a" * 40},
            "effects": [{"effect": "pause_space", "repo_id": "SZLHOLDINGS/a11oy"}],
            "managed_identity": context.identity, "managed_admission": witnesses[1],
            "before": {"source_revision": "a" * 40, "storage": {"instance_id": "store_" + "d" * 32,
                "managed_admission": witnesses[0]}},
            "after": {"source_revision": "a" * 40, "storage": {"instance_id": "store_" + "d" * 32,
                "managed_admission": witnesses[1]}}}
        gdw = {**common, "schema": checker["LIVE_PROOF_SCHEMAS"]["gdw"], "namespace": "a11oy",
            "credential_values_recorded": False,
            "evidence": {"namespace": "a11oy", "runtime_source_revision": "a" * 40,
                "database_generation_id": "c" * 32, "managed_identity": context.identity,
                "managed_admission": witnesses[2], "signed_receipt": {"namespace": "a11oy",
                    "receipt_status": "SIGNED_KHIPU_DSSE", "signature_verified": True,
                    "verified_against": checker["PINNED_RUNTIME_KEY_PATH"],
                    "pinned_key_der_sha256": checker["PINNED_SIGNING_KEY_DER_SHA256"]}}}
        return checker, series, gdw, context, backend, calls

    def evaluate(self, checker, series, gdw, context):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            s, g = root / "series.json", root / "gdw.json"
            s.write_text(json.dumps(series)); g.write_text(json.dumps(gdw))
            return checker["live_proof_admission"](s, g, "a" * 40, 0, 0, managed_context=context)

    def test_dynamic_reader_target_and_unscoped_import_drift_are_rejected(self):
        for name in MANAGED_READER_AST_SHA256:
            source = (ROOT / "scripts" / name).read_text()
            mutations = [source.replace('with_name("configure_hf_gdw_runtime.py")', 'with_name("other.py")', 1),
                source + "\nimportlib.import_module('huggingface_hub')\n",
                source + "\nimport importlib.util as another_loader\n"]
            for changed in mutations:
                with self.subTest(name=name, mutation=mutations.index(changed)):
                    self.assertNotEqual(changed, source)
                    with self.assertRaises(WorkflowContractError):
                        fixed_managed_reader_contract(ast.parse(changed), name)

    def test_pair_binds_same_immutable_admission_but_allows_later_cooperative_heads(self):
        checker, series, gdw, context, backend, calls = self.fixtures()
        result = self.evaluate(checker, series, gdw, context)
        self.assertTrue(result["admitted"])
        self.assertEqual(result["managed_identity"], context.identity)
        self.assertEqual(set(calls), {(str(i) * 40, str(i) * 32) for i in (1, 2, 3)})

    def test_mode_labels_without_provider_context_are_not_admitted(self):
        checker, series, gdw, context, *_ = self.fixtures()
        result = self.evaluate(checker, series, gdw, None)
        self.assertFalse(result["admitted"])
        self.assertEqual(result["series_a"]["state"], "UNPROVEN")
        self.assertEqual(result["gdw"]["state"], "UNPROVEN")

    def test_every_static_identity_mismatch_blocks_pair(self):
        for kind in ("series_a", "gdw"):
            for field in ("source_revision", "admission_sha256", "qualification_sha256", "generations"):
                with self.subTest(kind=kind, field=field):
                    checker, series, gdw, context, *_ = self.fixtures()
                    payload = series if kind == "series_a" else gdw["evidence"]
                    payload["managed_identity"][field] = {} if field == "generations" else "wrong"
                    self.assertFalse(self.evaluate(checker, series, gdw, context)["admitted"])

    def test_each_native_series_flag_and_gdw_signature_still_required(self):
        checker, *_ = self.fixtures()
        for flag in (*checker["SERIES_A_PROOF_FLAGS"], "signature"):
            with self.subTest(flag=flag):
                checker, series, gdw, context, *_ = self.fixtures()
                if flag == "signature": gdw["evidence"]["signed_receipt"]["signature_verified"] = False
                else: series["proof"][flag] = False
                self.assertFalse(self.evaluate(checker, series, gdw, context)["admitted"])

    def test_readback_missing_history_changed_generation_and_failed_host_ack_block(self):
        for defect in ("history", "gdw_generation", "series_generation", "source", "host_ack", "final_witness", "missing"):
            with self.subTest(defect=defect):
                checker, series, gdw, context, backend, _ = self.fixtures()
                if defect == "history":
                    original = backend.read_at
                    backend.read_at = lambda *args: (original(*args)[0], b"not-native-history")
                elif defect == "gdw_generation": gdw["evidence"]["database_generation_id"] = "0" * 32
                elif defect == "series_generation": series["before"]["storage"]["instance_id"] = "other"
                elif defect == "source": gdw["evidence"]["runtime_source_revision"] = "0" * 40
                elif defect == "host_ack": gdw["evidence"]["managed_admission"]["actual_host_full_state_ack_ms"] = 60001
                elif defect == "final_witness": series["managed_admission"] = series["before"]["storage"]["managed_admission"]
                else: del gdw["evidence"]["managed_admission"]
                self.assertFalse(self.evaluate(checker, series, gdw, context)["admitted"])

    def test_explicit_managed_loader_failure_cannot_fall_back_or_leak(self):
        checker, series, gdw, context, *_ = self.fixtures()
        # Even otherwise valid legacy-looking reports cannot replace a failed
        # explicitly requested immutable managed authority read.
        for payload in (series, gdw["evidence"]):
            payload.pop("managed_identity"); payload.pop("managed_admission")
        def denied(*_args, **_kwargs): raise RuntimeError("private-provider-secret-canary")
        checker["load_managed_proof_context"] = denied
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); s, g, output = root / "s", root / "g", root / "out"
            s.write_text(json.dumps(series)); g.write_text(json.dumps(gdw))
            code = checker["main"](["--admit-live-proofs", "--managed-acquisition", str(root / "locator"),
                "--series-a-proof", str(s), "--gdw-proof", str(g), "--series-a-proof-exit", "0",
                "--gdw-proof-exit", "0", "--source-sha", "a" * 40, "--output", str(output)])
            self.assertEqual(code, 1)
            self.assertFalse(json.loads(output.read_text())["admitted"])
            self.assertNotIn("private-provider", output.read_text())

    def test_managed_argument_cannot_admit_predeploy_configuration(self):
        checker, *_ = self.fixtures()
        with self.assertRaises(SystemExit) as caught:
            checker["main"](["--managed-acquisition", "locator", "--source-sha", "a" * 40, "--output", "unused"])
        self.assertEqual(caught.exception.code, 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
