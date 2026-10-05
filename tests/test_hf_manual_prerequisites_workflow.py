#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Offline workflow, bounded live-proof and blocked CLI boundaries; no network."""

from __future__ import annotations

import ast
import builtins
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
        ROOT, WORKFLOW, WorkflowContractError, assert_manual_dependency_graph,
        workflow_document,
    )
else:
    from .test_hf_sync_supersession_contract import (
        ROOT, WORKFLOW, WorkflowContractError, assert_manual_dependency_graph,
        workflow_document,
    )

CHECKER = ROOT / "scripts/check_hf_manual_prerequisites.py"
RESTART_WORKFLOW = ROOT / ".github/workflows/series-a-restart-proof.yml"
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


ADMITTED_GDW_SECRET_LINE = "          GDW_OPERATOR_TOKEN: ${{ secrets.GDW_OPERATOR_TOKEN }}\n"
ADMISSION_CONDITION = "${{ always() && needs.manual-prerequisites.result == 'success' && needs.deploy.result == 'success' }}"
GDW_CONDITION = ADMISSION_CONDITION[:-3] + " && (steps.series_a_proof.outcome == 'success' || steps.series_a_proof.outcome == 'failure') }}"
BOUNDED_RUNS = {
    "series_a": r'''set +e
python -B scripts/prove_hf_series_a_restart.py \
  --repo-id "$CANONICAL_SPACE" --origin "$CANONICAL_ORIGIN" \
  --managed-acquisition "$RUNNER_TEMP/gdw-durable-acquisition.json" \
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
  --managed-acquisition "$RUNNER_TEMP/gdw-durable-acquisition.json" \
  --source-sha "${{ github.sha }}" --output "$GDW_LIVE_REPORT"
code=$?
echo "exit_code=$code" >> "$GITHUB_OUTPUT"
exit "$code"''',
    "admission": r'''set -euo pipefail
python -B scripts/check_hf_manual_prerequisites.py --admit-live-proofs \
  --managed-acquisition "$RUNNER_TEMP/gdw-durable-acquisition.json" \
  --series-a-proof "$SERIES_A_LIVE_REPORT" --series-a-proof-exit "${SERIES_A_PROOF_EXIT:-2}" \
  --gdw-proof "$GDW_LIVE_REPORT" --gdw-proof-exit "${GDW_PROOF_EXIT:-2}" \
  --source-sha "${{ github.sha }}" --output "$LIVE_PROOF_ADMISSION_REPORT"''',
}

CHECKOUT = "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1"
SETUP_PYTHON = "actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97"
UPLOAD = "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a"
MANAGED_MODE = "managed-recovery"
LEGACY_MODE_CONDITION = "${{ needs.manual-prerequisites.outputs.mode != 'managed-recovery' }}"
CLASSIFIER_RUN = '''python -B scripts/acquire_gdw_durable_storage.py --classify-prerequisites
--preservation "${{ runner.temp }}/gdw-store-preservation.json"
--qualification "${{ runner.temp }}/gdw-store-recovery-qualification.json"
--github-output "$GITHUB_OUTPUT"
--output "${{ runner.temp }}/manual-prerequisites.json"'''
RECONCILIATION_RUN = '''python -B scripts/acquire_gdw_durable_storage.py --reconcile-supervised-acquisition
--github-output "$GITHUB_OUTPUT"
--output "$RUNNER_TEMP/gdw-supervised-reconciliation.json"'''
ACQUISITION_RUN = '''python -B scripts/acquire_gdw_durable_storage.py --inspect-held-acquisition
--output "$RUNNER_TEMP/gdw-durable-acquisition.json"'''

PAIR_CONFIGURATION_RUN = '''python -B scripts/configure_hf_gdw_runtime.py
--managed-acquisition "$RUNNER_TEMP/gdw-durable-acquisition.json"
--source-sha "$GITHUB_SHA" --managed-deadline-seconds 120
--output "$RUNNER_TEMP/gdw-managed-configuration.json"'''
FETCH_LOCATOR_RUN = '''python -B scripts/acquire_gdw_durable_storage.py --fetch-locator
--acquisition-artifact-id "${{ needs.durable-acquisition.outputs.artifact_id }}"
--acquisition-artifact-sha256 "${{ needs.durable-acquisition.outputs.artifact_sha256 }}"
--output "$RUNNER_TEMP/gdw-durable-acquisition.json"'''


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


def assert_reconciliation_contract(jobs):
    """Retain the disabled preflight's exact read-only authority and manual ABI."""
    job = jobs["recovery-reconciliation"]
    if (set(job) != {"name", "needs", "if", "runs-on", "timeout-minutes", "permissions", "outputs", "env", "steps"}
            or job["name"] != "Reconcile the held acquisition before provider mutation"
            or job["runs-on"] != "ubuntu-latest" or job["timeout-minutes"] != "5"
            or job["permissions"] != {"contents": "read", "actions": "read"}
            or job["env"] != {"HF_TOKEN": "${{ secrets.HF_ORG_TOKEN || secrets.HF_TOKEN }}", "PYTHONDONTWRITEBYTECODE": "1"}
            or job["outputs"] != {"admitted": "${{ steps.reconciliation.outputs.admitted }}"}):
        raise WorkflowContractError("reconciliation authority, permission or output scope changed")
    expected_steps = [
        {"name": "Checkout the exact protected source", "uses": CHECKOUT,
         "with": {"ref": "${{ github.sha }}", "persist-credentials": False, "fetch-depth": "1"}},
        {"name": "Set up the isolated reconciliation interpreter", "uses": SETUP_PYTHON,
         "with": {"python-version": "3.12"}},
        {"name": "Install the exact read-only reconciliation ABI",
         "run": 'python -m pip install --disable-pip-version-check --no-cache-dir "huggingface_hub==1.31.0" "requests==2.32.5" "cryptography==50.0.1"'},
        {"name": "Require the fixed inspection and unchanged absent private fence", "id": "reconciliation",
         "run": RECONCILIATION_RUN},
        {"name": "Retain the bounded read-only reconciliation decision", "if": "${{ always() }}", "uses": UPLOAD,
         "with": {"name": "canonical-supervised-reconciliation-${{ github.run_id }}-${{ github.run_attempt }}",
                  "path": "${{ runner.temp }}/gdw-supervised-reconciliation.json",
                  "if-no-files-found": "error", "retention-days": "90"}},
    ]
    if len(job["steps"]) != len(expected_steps):
        raise WorkflowContractError("reconciliation must retain its exact source, read-only check and artifact order")
    for actual, expected in zip(job["steps"], expected_steps):
        exact_step(actual, expected, "reconciliation exact step contract: " + expected["name"])


def assert_acquisition_contract(jobs):
    """The native job selects only fixed inspection; its pair stays disabled."""
    job = jobs["durable-acquisition"]
    if (set(job) != {"name", "needs", "if", "runs-on", "timeout-minutes", "permissions", "outputs", "env", "steps"}
            or job["name"] != "Acquire qualified private storage through the canonical publisher"
            or job["runs-on"] != "ubuntu-latest" or job["timeout-minutes"] != "20"
            or job["permissions"] != {"contents": "read", "actions": "read"}
            or job["env"] != {"HF_TOKEN": "${{ secrets.HF_ORG_TOKEN || secrets.HF_TOKEN }}", "PYTHONDONTWRITEBYTECODE": "1"}
            or job["outputs"] != {
                "artifact_id": "${{ steps.acquisition_artifact.outputs.artifact-id }}",
                "artifact_sha256": "${{ steps.acquisition_artifact.outputs.artifact-digest }}"}):
        raise WorkflowContractError("acquisition authority, permission or output scope changed")
    expected_steps = [
        {"name": "Checkout the exact protected source", "uses": CHECKOUT,
         "with": {"ref": "${{ github.sha }}", "persist-credentials": False, "fetch-depth": "1"}},
        {"name": "Read the existing immutable COPY publisher", "uses": CHECKOUT,
         "with": {"repository": "szl-holdings/.github", "ref": "e3ec47ad2e99a535839afe0f30fefbd8973d52da",
                  "path": ".gdw-source-publisher", "persist-credentials": False, "fetch-depth": "1"}},
        {"name": "Set up the isolated acquisition interpreter", "uses": SETUP_PYTHON,
         "with": {"python-version": "3.12"}},
        {"name": "Install the exact managed acquisition ABI",
         "run": 'python -m pip install --disable-pip-version-check --no-cache-dir "huggingface_hub==1.31.0" "requests==2.32.5" "cryptography==50.0.1"'},
        {"name": "Inspect the held prior acquisition without provider mutation", "run": ACQUISITION_RUN},
        {"name": "Install the persistent old-source guard and both managed configurations once",
         "if": "${{ github.ref == 'refs/heads/main' && false }}", "run": PAIR_CONFIGURATION_RUN},
        {"name": "Retain only the bounded inspection metadata report", "id": "acquisition_artifact",
         "if": "${{ always() }}", "uses": UPLOAD,
         "with": {"name": "canonical-durable-acquisition-${{ github.run_id }}-${{ github.run_attempt }}",
                  "path": "${{ runner.temp }}/gdw-durable-acquisition.json",
                  "if-no-files-found": "error", "retention-days": "90"}},
    ]
    if len(job["steps"]) != len(expected_steps):
        raise WorkflowContractError("acquisition must retain its exact source, held inspection, disabled pair and artifact order")
    for actual, expected in zip(job["steps"], expected_steps):
        exact_step(actual, expected, "acquisition exact step contract: " + expected["name"])
    runtime = jobs["runtime-config"]
    runtime_names = [
        "Checkout exact protected source", "Set up Python", "Install exact Hugging Face control client",
        "Read the exact same-run managed selector without granting local-file authority",
        "Converge fail-closed runtime configuration", "Converge isolated GDW successor configuration",
        "Prove live Series-A restart persistence (bounded)", "Prove live GDW write, drain, and receipt integrity (bounded)",
        "Admit bounded live proof reports and fail closed", "Upload secret-free runtime configuration evidence",
    ]
    if ([step.get("name") for step in runtime["steps"]] != runtime_names
            or runtime.get("permissions") != {"contents": "read", "actions": "read"}):
        raise WorkflowContractError("managed runtime must retain its exact read, proof and artifact order")
    exact_step(named_step(runtime, runtime_names[2]), {
        "name": runtime_names[2],
        "run": 'python -m pip install --disable-pip-version-check "huggingface_hub==1.31.0" "requests==2.32.5" "cryptography==50.0.1"'},
        "managed runtime interpreter must remain separate from manual 1.23")
    exact_step(named_step(runtime, runtime_names[3]), {"name": runtime_names[3], "run": FETCH_LOCATOR_RUN},
        "managed runtime requires the exact same-run read-only selector")
    for name, expected in (
        (runtime_names[4], 'python scripts/configure_hf_series_a_runtime.py --repo-id "$CANONICAL_SPACE" --bucket "SZLHOLDINGS/szl-evidence" --output "$RUNTIME_CONFIG_REPORT"'),
        (runtime_names[5], 'python scripts/configure_hf_gdw_runtime.py --repo-id "$CANONICAL_SPACE" --output "$GDW_CONFIG_REPORT"'),
    ):
        exact_step(named_step(runtime, name), {"name": name, "if": LEGACY_MODE_CONDITION, "run": expected},
            "managed runtime cannot repeat legacy configuration or add an override")
    upload = named_step(runtime, runtime_names[-1])
    expected_paths = tuple("${{ env." + name + " }}" for name in (
        "RUNTIME_CONFIG_REPORT", "SERIES_A_LIVE_REPORT", "GDW_CONFIG_REPORT", "GDW_LIVE_REPORT", "LIVE_PROOF_ADMISSION_REPORT"))
    if tuple(upload.get("with", {}).get("path", "").splitlines()) != expected_paths:
        raise WorkflowContractError("live proof reports must be retained: managed runtime artifact allowlist changed")


def assert_bounded_live_proof_steps(runtime, source):
    """The two live proofs run bounded, fail closed and are admitted by the checker."""
    env = runtime.get("env", {})
    if env.get("CANONICAL_SPACE") is not None or "GDW_OPERATOR_TOKEN" in env or "continue-on-error" in runtime:
        raise WorkflowContractError("live proof must be bounded and fail closed: job")
    series = named_step(runtime, "Prove live Series-A restart persistence (bounded)")
    gdw = named_step(runtime, "Prove live GDW write, drain, and receipt integrity (bounded)")
    admission = named_step(runtime, "Admit bounded live proof reports and fail closed")
    for kind, step, condition, step_env in (
        ("series-a", series, None, None),
        ("gdw", gdw, GDW_CONDITION, {"GDW_OPERATOR_TOKEN": "${{ secrets.GDW_OPERATOR_TOKEN }}"}),
        ("admission", admission, ADMISSION_CONDITION, {
            "SERIES_A_PROOF_EXIT": "${{ steps.series_a_proof.outputs.exit_code }}",
            "GDW_PROOF_EXIT": "${{ steps.gdw_proof.outputs.exit_code }}",
        }),
    ):
        key = {"series-a": "series_a"}.get(kind, kind)
        if (
            compact(step.get("run", "")) != compact(BOUNDED_RUNS[key])
            or step.get("if") != condition
            or step.get("env") != step_env
            or "continue-on-error" in step
            or step.get("shell") != "bash"
        ):
            raise WorkflowContractError("live proof must be bounded and fail closed: " + kind)
    if series.get("id") != "series_a_proof" or gdw.get("id") != "gdw_proof":
        raise WorkflowContractError("live proof must be bounded and fail closed: ids")
    steps = runtime["steps"]
    if not steps.index(series) < steps.index(gdw) < steps.index(admission):
        raise WorkflowContractError("live proof must be bounded and fail closed: order")
    upload = named_step(runtime, "Upload secret-free runtime configuration evidence")
    paths = upload.get("with", {}).get("path", "")
    for name in ("SERIES_A_LIVE_REPORT", "GDW_LIVE_REPORT", "LIVE_PROOF_ADMISSION_REPORT"):
        if "${{ env." + name + " }}" not in paths:
            raise WorkflowContractError("live proof reports must be retained")
    if "--blocked-proof" in source:
        raise WorkflowContractError("hf-sync must not fall back to the blocked proof")
    if source.count("prove_hf_series_a_restart.py") != 1 or source.count("prove_hf_gdw_runtime.py") != 1:
        raise WorkflowContractError("live proof must be bounded and fail closed: duplicate call")


def assert_manual_step_contract(source):
    jobs = assert_manual_dependency_graph(source)
    assert_reconciliation_contract(jobs)
    admission = jobs["source-admission"]
    admission_names = [step.get("name") for step in admission["steps"]]
    if admission_names != ["Checkout the immutable queued source", "Require main and classify current source ownership", "Retain the source admission decision"]:
        raise WorkflowContractError("source admission must remain read only")
    admission_run = named_step(admission, "Require main and classify current source ownership")["run"]
    expected_admission = r'''set -euo pipefail
test "$GITHUB_REF" = refs/heads/main
python3 -B scripts/hf_exact_main_ownership.py \
  --repository "$GITHUB_REPOSITORY" --expected-sha "$GITHUB_SHA" \
  --receipt "$RUNNER_TEMP/canonical-source-admission.json" \
  --github-output "$GITHUB_OUTPUT"'''
    if compact(admission_run) != compact(expected_admission) or "secrets." in json.dumps(admission):
        raise WorkflowContractError("source admission must remain read only")
    if admission.get("outputs") != {
        "publish": "${{ steps.owner.outputs.publish }}",
        "artifact_id": "${{ steps.source_artifact.outputs.artifact-id }}",
        "artifact_sha256": "${{ steps.source_artifact.outputs.artifact-digest }}",
    }:
        raise WorkflowContractError("source admission outputs must bind its exact native artifact")
    job = jobs["manual-prerequisites"]
    if job.get("permissions") != {"contents": "read"}:
        raise WorkflowContractError("manual authority or permission scope changed")
    if [step.get("name") for step in job["steps"]] != ["Checkout the immutable admitted source", "Set up Python", "Install exact metadata client", "Preserve stopped private stores before any runtime mutation", "Qualify the pinned private capture without admitting restore", "Classify the exact native candidate without admitting deployment", "Retain metadata checks and fail closed on UNKNOWN authority", "Retain bounded prerequisite decision"]:
        raise WorkflowContractError("manual job permits only the reviewed preservation effect, read-only qualification and candidate classifier")
    exact_step(named_step(job, "Set up Python"), {"name": "Set up Python", "uses": SETUP_PYTHON,
        "with": {"python-version": "3.12"}}, "manual interpreter must remain separate and pinned")
    exact_step(named_step(job, "Install exact metadata client"), {"name": "Install exact metadata client",
        "run": 'python -m pip install --disable-pip-version-check "huggingface_hub==1.23.0" "requests==2.32.5" "cryptography==50.0.1"'},
        "manual interpreter must retain the exact 1.23 metadata dependencies")
    preservation = named_step(job, "Preserve stopped private stores before any runtime mutation")
    expected_preservation = 'python -B scripts/preserve_hf_gdw_store.py --supervised-acquisition --output "${{ runner.temp }}/gdw-store-preservation.json"'
    if (set(preservation) != {"name", "id", "continue-on-error", "run"}
            or preservation.get("id") != "preserve_stores"
            or preservation.get("continue-on-error") is not True
            or compact(preservation.get("run", "")) != expected_preservation
            or job.get("env") != {"HF_TOKEN": "${{ secrets.HF_ORG_TOKEN || secrets.HF_TOKEN }}"}):
        raise WorkflowContractError("preservation step must retain its exact invocation and credential scope")
    recovery = named_step(job, "Qualify the pinned private capture without admitting restore")
    expected_recovery = (
        "python -B scripts/qualify_gdw_store_recovery.py "
        "--capture-report docs/operations/evidence/gdw-capture-37223162231.json "
        "--historical-anchors docs/operations/evidence/gdw-recovery-historical-anchors.json "
        '--output "${{ runner.temp }}/gdw-store-recovery-qualification.json"'
    )
    if (set(recovery) != {"name", "id", "if", "continue-on-error", "run"}
            or recovery.get("id") != "qualify_stores"
            or recovery.get("continue-on-error") is not True
            or recovery.get("if") != "${{ always() && steps.preserve_stores.outcome == 'failure' }}"
            or compact(recovery.get("run", "")) != expected_recovery):
        raise WorkflowContractError("recovery qualification must retain its exact read-only invocation and failed-preservation condition")
    classifier = named_step(job, "Classify the exact native candidate without admitting deployment")
    exact_step(classifier, {"name": "Classify the exact native candidate without admitting deployment",
        "id": "recovery_mode", "if": "${{ always() }}", "run": CLASSIFIER_RUN},
        "candidate classifier must validate the exact reports without failure tolerance or overrides")
    step = named_step(job, "Retain metadata checks and fail closed on UNKNOWN authority")
    expected = r'''set +e
python -B scripts/configure_hf_series_a_runtime.py \
  --repo-id "$CANONICAL_SPACE" --check-only \
  --output "$RUNNER_TEMP/manual-series-a.json"
series_code=$?
python -B scripts/configure_hf_gdw_runtime.py \
  --repo-id "$CANONICAL_SPACE" --check-only \
  --output "$RUNNER_TEMP/manual-gdw.json"
gdw_code=$?
set -euo pipefail
python -B scripts/check_hf_manual_prerequisites.py \
  --series-a "$RUNNER_TEMP/manual-series-a.json" --series-a-exit "$series_code" \
  --gdw "$RUNNER_TEMP/manual-gdw.json" --gdw-exit "$gdw_code" \
  --source-sha "$GITHUB_SHA" --output "$RUNNER_TEMP/manual-prerequisites.json"'''
    if (set(step) != {"name", "if", "shell", "run"} or step.get("shell") != "bash"
            or compact(step.get("run", "")) != compact(expected)
            or step.get("if") != "${{ steps.recovery_mode.outputs.mode != 'managed-recovery' && steps.recovery_mode.outcome == 'success' }}"):
        raise WorkflowContractError("manual aggregate must fail before effects")
    if job.get("outputs") != {
        "mode": "${{ steps.recovery_mode.outputs.mode }}",
        "artifact_id": "${{ steps.prerequisite_artifact.outputs.artifact-id }}",
        "artifact_sha256": "${{ steps.prerequisite_artifact.outputs.artifact-digest }}",
    }:
        raise WorkflowContractError("metadata cannot emit authority")
    receipt = named_step(job, "Retain bounded prerequisite decision")
    if receipt.get("if") != "always()" or receipt.get("with", {}).get("if-no-files-found") != "error":
        raise WorkflowContractError("manual decision must be retained")
    artifact_paths = receipt.get("with", {}).get("path", "")
    if not isinstance(artifact_paths, str) or tuple(artifact_paths.splitlines()) != (
        "${{ runner.temp }}/manual-prerequisites.json",
        "${{ runner.temp }}/gdw-store-preservation.json",
        "${{ runner.temp }}/gdw-store-recovery-qualification.json",
    ):
        raise WorkflowContractError("preservation artifacts must retain the exact public metadata allowlist")
    if (set(receipt) != {"name", "id", "if", "uses", "with"}
            or receipt.get("id") != "prerequisite_artifact" or receipt.get("uses") != UPLOAD
            or set(receipt.get("with", {})) != {"name", "path", "if-no-files-found", "retention-days"}
            or receipt["with"].get("name") != "canonical-manual-prerequisites-${{ github.run_id }}-${{ github.run_attempt }}"
            or receipt["with"].get("retention-days") != "90"):
        raise WorkflowContractError("manual decision must retain its exact same-run metadata artifact")
    assert_acquisition_contract(jobs)
    # The GDW operator credential may appear exactly once: as the step-level
    # env of the bounded GDW proof step. Anywhere else it is a removed effect.
    scanned = source.replace(ADMITTED_GDW_SECRET_LINE, "", 1)
    for token in ("DOCS_READ_TOKEN", "--github-read-token", "--operator-token", "--capacity-donor", "HF_CAPACITY_DONOR", "add_space_secret", "delete_space_secret", "gh issue", "issues: write", "OPERATOR_TOKEN"):
        if token in scanned:
            raise WorkflowContractError("removed credential or donor effect: " + token)
    assert_bounded_live_proof_steps(jobs["runtime-config"], source)
    document = workflow_document(source)
    if document["on"]["workflow_dispatch"]["inputs"]["publish_vertical_flagships"]["default"] is not False:
        raise WorkflowContractError("vertical publication requires explicit opt in")
    vertical = jobs["publish-vertical-flagships"]
    owned = "${{ steps.exact_main_owner.outputs.publish == 'true' }}"
    approved = "${{ steps.exact_main_owner.outputs.publish == 'true' && steps.vertical_plan.outputs.vertical_flagships == 'true' }}"
    for name, condition in (("Set up Python", owned), ("Require the approved plan for the actual vertical source", owned), ("Install pinned vertical publisher", approved), ("Publish and verify the v4 vertical estate", approved)):
        if named_step(vertical, name).get("if") != condition:
            raise WorkflowContractError("vertical source and plan gate: " + name)
    finance = jobs["publish-finance-projection"]
    for name in ("Set up Python", "Install the established pinned publisher", "Publish exactly Finance and require public functional evidence"):
        if named_step(finance, name).get("if") != "${{ steps.owner.outputs.publish == 'true' }}":
            raise WorkflowContractError("finance source gate: " + name)
    relock = jobs["relock"]
    enforce = named_step(relock, "Enforce exact live state")
    expected_enforce = r'''code="${EXIT_CODE:-2}"
if [ "$code" -ne 0 ]; then
  echo "::error::Canonical A11oy relock failed with exit ${code}."
  exit "$code"
fi
if [ "${CURRENT_MAIN:-false}" != 'true' ]; then
  echo '::error::Canonical A11oy relock source is no longer current protected main.'
  exit 3
fi
echo 'Canonical A11oy is source-bound, singleton, and route-operational.' '''
    expected_enforce_env = {
        "EXIT_CODE": "${{ steps.verify.outputs.exit_code }}",
        "CURRENT_MAIN": "${{ steps.post_deploy_owner.outputs.publish }}",
    }
    if (
        compact(enforce.get("run", "")) != compact(expected_enforce)
        or enforce.get("if") != "always()"
        or enforce.get("env") != expected_enforce_env
    ):
        raise WorkflowContractError("actual verification exit must be enforced")
    parity = jobs["post-deployment-parity"]
    if (
        parity.get("needs") != "relock"
        or parity.get("uses") != "./.github/workflows/hf-module-drift.yml"
        or parity.get("permissions") != {"contents": "read"}
        or "if" in parity
    ):
        raise WorkflowContractError("parity must follow successful verification")
    terminal = jobs["terminal-source-authorization"]
    terminal_condition = "${{ always() && needs.post-deployment-parity.result == 'success' && (needs.publish-vertical-flagships.result == 'success' || needs.publish-vertical-flagships.result == 'skipped') && (needs.publish-finance-projection.result == 'success' || needs.publish-finance-projection.result == 'skipped') }}"
    if (
        terminal.get("needs")
        != [
            "post-deployment-parity",
            "publish-vertical-flagships",
            "publish-finance-projection",
        ]
        or terminal.get("if") != terminal_condition
        or terminal.get("permissions") != {"contents": "read"}
    ):
        raise WorkflowContractError("terminal source authorization dependencies drifted")
    terminal_owner = named_step(
        terminal, "Re-authorize exact protected main after awaited parity"
    )
    terminal_receipt = named_step(terminal, "Retain terminal source authorization")
    terminal_enforce = named_step(
        terminal, "Re-read and enforce exact protected-main ownership as the final step"
    )
    if (
        "scripts/hf_exact_main_ownership.py" not in terminal_owner.get("run", "")
        or '--expected-sha "$GITHUB_SHA"' not in terminal_owner.get("run", "")
        or terminal_owner.get("env") != {"GITHUB_TOKEN": "${{ github.token }}"}
        or terminal_receipt.get("if") != "always()"
        or terminal_receipt.get("with", {}).get("if-no-files-found") != "error"
        or terminal_enforce.get("if") != "always()"
        or terminal_enforce.get("env")
        != {"GITHUB_TOKEN": "${{ github.token }}"}
        or "scripts/hf_exact_main_ownership.py" not in terminal_enforce.get("run", "")
        or '--expected-sha "$GITHUB_SHA"' not in terminal_enforce.get("run", "")
        or "terminal-source-authorization-final.json"
        not in terminal_enforce.get("run", "")
        or "grep -Fqx 'publish=true'" not in terminal_enforce.get("run", "")
        or terminal.get("steps", [])[-1].get("name")
        != "Re-read and enforce exact protected-main ownership as the final step"
    ):
        raise WorkflowContractError("terminal source authorization must fail closed")
    return jobs


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


class ManualPrerequisiteWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = WORKFLOW.read_text(encoding="utf-8")

    def test_actual_workflow_metadata_cannot_enable_publication(self):
        jobs = assert_manual_step_contract(self.source)
        self.assertNotIn("secrets.", json.dumps(jobs["source-admission"]))
        self.assertEqual(jobs["manual-prerequisites"]["permissions"], {"contents": "read"})
        self.assertEqual(jobs["recovery-reconciliation"]["permissions"], {"contents": "read", "actions": "read"})
        self.assertEqual(jobs["recovery-reconciliation"]["env"]["HF_TOKEN"], jobs["durable-acquisition"]["env"]["HF_TOKEN"])

    def test_reconciliation_cannot_gain_provider_commands_credentials_or_write_permissions(self):
        start = self.source.index("  recovery-reconciliation:\n")
        end = self.source.index("  manual-prerequisites:\n", start)
        job = self.source[start:end]
        marker = "      - name: Require the fixed inspection and unchanged absent private fence\n"
        mutations = (
            ("      contents: read\n", "      contents: write\n"),
            ("      actions: read\n", "      actions: write\n"),
            ("      actions: read\n", "      actions: read\n      id-token: write\n"),
            ("${{ secrets.HF_ORG_TOKEN || secrets.HF_TOKEN }}", "${{ secrets.ALTERNATE_TOKEN }}"),
            ('      PYTHONDONTWRITEBYTECODE: "1"\n', '      PYTHONDONTWRITEBYTECODE: "1"\n      EXTRA_TOKEN: ${{ secrets.EXTRA_TOKEN }}\n'),
            ("--reconcile-supervised-acquisition", "--acquire"),
            ("--reconcile-supervised-acquisition", "--inspect-held-acquisition"),
            ("--reconcile-supervised-acquisition", "--reconcile-supervised-acquisition --source-artifact-id 1"),
            ("--reconcile-supervised-acquisition", "--reconcile-supervised-acquisition --retry"),
            ("--reconcile-supervised-acquisition", "--reconcile-supervised-acquisition --repo-id SZLHOLDINGS/another-space"),
            ('--github-output "$GITHUB_OUTPUT"', '--github-output "$RUNNER_TEMP/forged-admission"'),
            ('--output "$RUNNER_TEMP/gdw-supervised-reconciliation.json"', '--output "$RUNNER_TEMP/gdw-supervised-reconciliation.json" || true'),
            ("scripts/acquire_gdw_durable_storage.py", "scripts/unreviewed_reconciliation.py"),
            ("          ref: ${{ github.sha }}\n", "          ref: main\n"),
            ("          persist-credentials: false\n", "          persist-credentials: true\n"),
            ('"huggingface_hub==1.31.0"', '"huggingface_hub==1.23.0"'),
            ("      admitted: ${{ steps.reconciliation.outputs.admitted }}\n", "      admitted: 'true'\n"),
            (marker, marker + "        if: always()\n"),
            (marker, marker + "        continue-on-error: true\n"),
            (marker, marker + "        working-directory: unreviewed\n"),
            (marker, marker + "        env:\n          HF_TOKEN: alternate\n"),
        )
        for before, after in mutations:
            with self.subTest(before=before, after=after):
                self.assertIn(before, job)
                changed = self.source.replace(job, job.replace(before, after, 1), 1)
                with self.assertRaisesRegex(WorkflowContractError, "reconciliation"):
                    assert_manual_step_contract(changed)

    def test_reconciliation_retains_only_its_same_attempt_safe_decision(self):
        start = self.source.index("  recovery-reconciliation:\n")
        end = self.source.index("  manual-prerequisites:\n", start)
        job = self.source[start:end]
        path = "          path: ${{ runner.temp }}/gdw-supervised-reconciliation.json\n"
        mutations = (
            (path, "          path: ${{ runner.temp }}/**\n"),
            (path, "          path: /tmp/szl-private-store-*\n"),
            (path, "          path: |\n            ${{ runner.temp }}/gdw-supervised-reconciliation.json\n            ${{ runner.temp }}/candidate.sqlite3\n"),
            (path, "          path: |\n            ${{ runner.temp }}/gdw-supervised-reconciliation.json\n            ${{ runner.temp }}/gdw-supervised-reconciliation.json\n"),
            (path, ""),
            ("canonical-supervised-reconciliation-${{ github.run_id }}-${{ github.run_attempt }}", "canonical-supervised-reconciliation-${{ github.run_id }}-1"),
            ("        if: ${{ always() }}\n", ""),
            ("          if-no-files-found: error\n", "          if-no-files-found: ignore\n"),
            ("          retention-days: 90\n", "          retention-days: 1\n"),
        )
        for before, after in mutations:
            with self.subTest(before=before, after=after):
                self.assertIn(before, job)
                changed = self.source.replace(job, job.replace(before, after, 1), 1)
                with self.assertRaisesRegex(WorkflowContractError, "reconciliation"):
                    assert_manual_step_contract(changed)

    def test_reconciliation_cannot_be_removed_duplicated_reordered_or_joined_by_a_publisher(self):
        start = self.source.index("  recovery-reconciliation:\n")
        end = self.source.index("  manual-prerequisites:\n", start)
        job = self.source[start:end]
        check_start = job.index("      - name: Require the fixed inspection")
        check_end = job.index("      - name: Retain the bounded read-only", check_start)
        check = job[check_start:check_end]
        removed = job[:check_start] + job[check_end:]
        candidates = (
            removed,
            job.replace(check, check + check, 1),
            removed.replace("      - name: Checkout the exact protected source", check + "      - name: Checkout the exact protected source", 1),
            job.replace(check, check + "      - name: Unreviewed publisher\n        run: python .github/scripts/hf_deploy.py\n", 1),
        )
        for index, candidate in enumerate(candidates):
            with self.subTest(index=index), self.assertRaisesRegex(WorkflowContractError, "reconciliation"):
                assert_manual_step_contract(self.source.replace(job, candidate, 1))

    def test_preservation_invocation_has_no_unknown_helper_overrides_or_failure_bypass(self):
        marker = "      - name: Preserve stopped private stores before any runtime mutation\n"
        cases = (
            ("scripts/preserve_hf_gdw_store.py", "scripts/unreviewed_preservation.py"),
            ("scripts/preserve_hf_gdw_store.py", "scripts/preserve_hf_gdw_store.py --bucket SZLHOLDINGS/another-bucket"),
            ("scripts/preserve_hf_gdw_store.py", "scripts/preserve_hf_gdw_store.py --overwrite"),
            ("          --supervised-acquisition\n", ""),
            ("          --supervised-acquisition\n", "          --supervised-acquisition --supervised-acquisition\n"),
            ('--output "${{ runner.temp }}/gdw-store-preservation.json"', '--output "${{ runner.temp }}/gdw-store-preservation.json" || true'),
            (marker, marker + "        if: false\n"),
            ("        id: preserve_stores\n        continue-on-error: true\n", "        id: preserve_stores\n        continue-on-error: false\n"),
            (marker, marker + "        shell: python\n"),
            (marker, marker + "        working-directory: unreviewed-source\n"),
            (marker, marker + "        env:\n          HF_TOKEN: alternate-authority\n"),
        )
        for original, replacement in cases:
            with self.subTest(replacement=replacement):
                self.assertIn(original, self.source)
                with self.assertRaisesRegex(WorkflowContractError, "preservation|step failure bypass"):
                    assert_manual_step_contract(self.source.replace(original, replacement, 1))

    def test_preservation_cannot_be_removed_duplicated_moved_or_joined_by_another_effect(self):
        start = self.source.index("      - name: Preserve stopped private stores")
        end = self.source.index("      - name: Qualify the pinned private capture", start)
        block = self.source[start:end]
        removed = self.source[:start] + self.source[end:]
        receipt = "      - name: Retain bounded prerequisite decision\n"
        candidates = (
            removed,
            self.source.replace(block, block + block, 1),
            removed.replace(receipt, block + receipt, 1),
            self.source.replace(block, block + "      - name: Unreviewed provider effect\n        run: python scripts/unreviewed.py\n", 1),
        )
        for index, candidate in enumerate(candidates):
            with self.subTest(index=index), self.assertRaisesRegex(WorkflowContractError, "reviewed preservation effect|duplicate step id"):
                assert_manual_step_contract(candidate)

    def test_recovery_qualification_cannot_change_inputs_condition_or_gain_overrides(self):
        marker = "      - name: Qualify the pinned private capture without admitting restore\n"
        condition = "${{ always() && steps.preserve_stores.outcome == 'failure' }}"
        cases = (
            ("scripts/qualify_gdw_store_recovery.py", "scripts/unknown_recovery.py"),
            ("--capture-report docs/operations/evidence/gdw-capture-37223162231.json", "--capture-report https://unreviewed.example/capture.json"),
            ("--capture-report docs/operations/evidence/gdw-capture-37223162231.json", "--capture-report ${{ runner.temp }}/gdw-store-preservation.json"),
            ("--historical-anchors docs/operations/evidence/gdw-recovery-historical-anchors.json", "--historical-anchors docs/operations/evidence/unreviewed-anchors.json"),
            ("--historical-anchors docs/operations/evidence/gdw-recovery-historical-anchors.json", ""),
            ('--output "${{ runner.temp }}/gdw-store-recovery-qualification.json"', '--output "${{ runner.temp }}/gdw-store-recovery-qualification.json" --restore'),
            ('--output "${{ runner.temp }}/gdw-store-recovery-qualification.json"', '--output "${{ runner.temp }}/gdw-store-recovery-qualification.json" || true'),
            (condition, "always()"),
            (condition, "${{ always() && steps.preserve_stores.outcome == 'success' }}"),
            (condition, "${{ always() && steps.unknown.outcome == 'failure' }}"),
            ("        id: qualify_stores\n", "        id: unreviewed_qualification\n"),
            (marker, marker + "        shell: python\n"),
            (marker, marker + "        working-directory: unreviewed-source\n"),
            (marker, marker + "        env:\n          HF_TOKEN: alternate-authority\n"),
            ("        id: preserve_stores\n", "        id: unreviewed_preservation\n"),
        )
        for original, replacement in cases:
            with self.subTest(replacement=replacement):
                self.assertIn(original, self.source)
                with self.assertRaisesRegex(WorkflowContractError, "recovery qualification|preservation step|step failure bypass"):
                    assert_manual_step_contract(self.source.replace(original, replacement, 1))

    def test_recovery_qualification_cannot_be_removed_duplicated_or_reordered(self):
        start = self.source.index("      - name: Qualify the pinned private capture")
        end = self.source.index("      - name: Retain metadata checks", start)
        block = self.source[start:end]
        removed = self.source[:start] + self.source[end:]
        preservation = "      - name: Preserve stopped private stores"
        receipt = "      - name: Retain bounded prerequisite decision\n"
        candidates = (
            removed,
            self.source.replace(block, block + block, 1),
            removed.replace(preservation, block + preservation, 1),
            removed.replace(receipt, block + receipt, 1),
        )
        for index, candidate in enumerate(candidates):
            with self.subTest(index=index), self.assertRaisesRegex(WorkflowContractError, "reviewed preservation effect|duplicate step id"):
                assert_manual_step_contract(candidate)

    def test_recovery_artifact_cannot_export_private_candidates_or_extra_files(self):
        original = "            ${{ runner.temp }}/gdw-store-recovery-qualification.json\n"
        self.assertIn(original, self.source)
        for replacement in (
            "            ${{ runner.temp }}/**\n",
            "            /tmp/szl-gdw-recovery-*\n",
            "",
            original + original,
            original + "            ${{ runner.temp }}/candidate.sqlite3\n",
        ):
            with self.subTest(replacement=replacement), self.assertRaisesRegex(WorkflowContractError, "public metadata allowlist"):
                assert_manual_step_contract(self.source.replace(original, replacement, 1))

    def test_preservation_artifacts_cannot_include_raw_captures_or_duplicate_paths(self):
        original = "            ${{ runner.temp }}/gdw-store-preservation.json\n"
        self.assertIn(original, self.source)
        candidates = (
            "            ${{ runner.temp }}/**\n",
            "            /tmp/szl-private-store-*\n",
            "",
            original + original,
            original + "            ${{ runner.temp }}/private-capture.sqlite3\n",
        )
        for replacement in candidates:
            with self.subTest(replacement=replacement), self.assertRaisesRegex(WorkflowContractError, "public metadata allowlist"):
                assert_manual_step_contract(self.source.replace(original, replacement, 1))

    def test_preservation_job_cannot_gain_alternate_credentials(self):
        start = self.source.index("  manual-prerequisites:\n")
        end = self.source.index("  resume-paused-space:\n", start)
        block = self.source[start:end]
        original = "      HF_TOKEN: ${{ secrets.HF_ORG_TOKEN || secrets.HF_TOKEN }}\n"
        self.assertIn(original, block)
        for replacement in (
            "      HF_TOKEN: ${{ secrets.ALTERNATE_TOKEN }}\n",
            original + "      UNREVIEWED_EFFECT_TOKEN: ${{ secrets.EXTRA_TOKEN }}\n",
        ):
            with self.subTest(replacement=replacement), self.assertRaisesRegex(WorkflowContractError, "credential scope"):
                assert_manual_step_contract(self.source.replace(block, block.replace(original, replacement, 1), 1))
        permissions = "    permissions:\n      contents: read\n"
        self.assertIn(permissions, block)
        with self.assertRaisesRegex(WorkflowContractError, "manual authority or permission scope"):
            assert_manual_step_contract(self.source.replace(block, block.replace(
                permissions, permissions + "      actions: read\n", 1), 1))

    def test_removed_checker_check_only_and_exit_propagation_are_detected(self):
        cases = (
            ("scripts/check_hf_manual_prerequisites.py", "scripts/deleted_checker.py"),
            ('--repo-id "$CANONICAL_SPACE" --check-only', '--repo-id "$CANONICAL_SPACE"'),
            ("series_code=$?", "series_code=0"),
            ("gdw_code=$?", "gdw_code=0"),
            ("set -euo pipefail\n          python -B scripts/check_hf_manual_prerequisites.py", "set +e\n          python -B scripts/check_hf_manual_prerequisites.py"),
            ('--source-sha "$GITHUB_SHA" --output "$RUNNER_TEMP/manual-prerequisites.json"', '--source-sha "$GITHUB_SHA" --output "$RUNNER_TEMP/manual-prerequisites.json" || true'),
            ("        if: ${{ steps.recovery_mode.outputs.mode != 'managed-recovery' && steps.recovery_mode.outcome == 'success' }}\n", "        if: false\n"),
        )
        for original, replacement in cases:
            with self.subTest(original=original):
                self.assertIn(original, self.source)
                with self.assertRaisesRegex(WorkflowContractError, "manual aggregate must fail before effects"):
                    assert_manual_step_contract(self.source.replace(original, replacement, 1))

    def test_credential_forwarding_donor_and_issue_mutations_stay_removed(self):
        for token in ("DOCS_READ_TOKEN", "--github-read-token", "--operator-token", "--capacity-donor", "gh issue", "issues: write", "add_space_secret", "delete_space_secret"):
            with self.subTest(token=token), self.assertRaisesRegex(WorkflowContractError, "removed credential or donor effect"):
                assert_manual_step_contract(self.source + "\n# " + token + "\n")

    def test_weakened_bounded_live_proof_steps_are_rejected(self):
        cases = (
            ('            --series-a-proof "$SERIES_A_LIVE_REPORT" \\\n', '', "gdw"),
            ('--run-context "${{ github.run_id }}:${{ github.run_attempt }}"', '--run-context "1:1"', "series-a"),
            ('          exit "$code"\n\n      # Writes only', '          exit 0\n\n      # Writes only', "series-a"),
            ('--origin "$CANONICAL_ORIGIN" \\\n            --managed-acquisition "$RUNNER_TEMP/gdw-durable-acquisition.json" \\\n            --source-sha "${{ github.sha }}" --output "$GDW_LIVE_REPORT"', '--origin "https://a-11-oy.com" \\\n            --managed-acquisition "$RUNNER_TEMP/gdw-durable-acquisition.json" \\\n            --source-sha "${{ github.sha }}" --output "$GDW_LIVE_REPORT"', "gdw"),
            ('--admit-live-proofs \\', '--admit-live-proofs || true \\', "admission"),
            ("        id: gdw_proof\n", "        id: gdw_proof\n        continue-on-error: true\n", "gdw|step failure bypass"),
            ("      - name: Admit bounded live proof reports and fail closed\n", "      - name: Admit bounded live proof reports and fail closed\n        continue-on-error: true\n", "admission|step failure bypass"),
            ("            ${{ env.LIVE_PROOF_ADMISSION_REPORT }}\n", "", "retained"),
            ("      GDW_LIVE_REPORT: /tmp/gdw-live-proof.json\n", "      GDW_LIVE_REPORT: /tmp/gdw-live-proof.json\n      GDW_OPERATOR_TOKEN: ${{ secrets.GDW_OPERATOR_TOKEN }}\n", "removed credential"),
        )
        for original, replacement, diagnostic in cases:
            with self.subTest(diagnostic=diagnostic, original=original):
                self.assertIn(original, self.source)
                with self.assertRaisesRegex(WorkflowContractError, diagnostic):
                    assert_manual_step_contract(self.source.replace(original, replacement, 1))

    def test_blocked_proof_fallback_in_hf_sync_is_rejected(self):
        changed = self.source.replace(
            "python -B scripts/prove_hf_gdw_runtime.py \\",
            "python -B scripts/check_hf_manual_prerequisites.py --blocked-proof gdw \\", 1)
        with self.assertRaises(WorkflowContractError):
            assert_manual_step_contract(changed)

    def test_standalone_restart_workflow_has_no_provider_or_secret_path(self):
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

    def test_enforcement_finance_opt_in_and_parity_remain_ordered(self):
        jobs = assert_manual_step_contract(self.source)
        enforce = named_step(jobs["relock"], "Enforce exact live state")
        parity = jobs["post-deployment-parity"]
        self.assertIn('code="${EXIT_CODE:-2}"', enforce["run"])
        self.assertIn('exit "$code"', enforce["run"])
        self.assertNotIn("if", parity)
        self.assertEqual(parity["needs"], "relock")
        self.assertEqual(parity["uses"], "./.github/workflows/hf-module-drift.yml")
        self.assertEqual(parity["permissions"], {"contents": "read"})
        self.assertIn("relock", jobs["publish-finance-projection"]["needs"])
        self.assertIn("inputs.publish_vertical_flagships", jobs["publish-vertical-flagships"]["if"])
        terminal = jobs["terminal-source-authorization"]
        self.assertEqual(
            terminal["needs"],
            [
                "post-deployment-parity",
                "publish-vertical-flagships",
                "publish-finance-projection",
            ],
        )
        self.assertIn("needs.post-deployment-parity.result == 'success'", terminal["if"])
        self.assertEqual(terminal["permissions"], {"contents": "read"})

    def test_comment_only_or_weakened_source_plan_and_exit_gates_are_rejected(self):
        cases = (
            ('--github-output "$GITHUB_OUTPUT"\n', '--github-output "$GITHUB_OUTPUT"\n          python .github/scripts/resume_hf_space.py\n', "source admission must remain read only"),
            ("        default: false\n", "        default: true\n", "vertical publication requires explicit opt in"),
            ("        if: ${{ steps.exact_main_owner.outputs.publish == 'true' && steps.vertical_plan.outputs.vertical_flagships == 'true' }}\n", "        if: always() # steps.exact_main_owner.outputs.publish == 'true' && steps.vertical_plan.outputs.vertical_flagships == 'true'\n", "vertical source and plan gate"),
            ('            exit "$code"\n', '            true # exit "$code"\n', "actual verification exit must be enforced"),
        )
        for original, replacement, diagnostic in cases:
            with self.subTest(diagnostic=diagnostic):
                self.assertIn(original, self.source)
                with self.assertRaisesRegex(WorkflowContractError, diagnostic):
                    assert_manual_step_contract(self.source.replace(original, replacement, 1))

    def test_unknown_metadata_cannot_gain_an_authority_output(self):
        changed = self.source.replace("      mode: ${{ steps.recovery_mode.outputs.mode }}\n",
            "      mode: ${{ steps.recovery_mode.outputs.mode }}\n      publish: 'true'\n", 1)
        with self.assertRaisesRegex(WorkflowContractError, "metadata cannot emit authority"):
            assert_manual_step_contract(changed)

    def test_first_cutover_classifier_cannot_gain_authority_or_skip_verification(self):
        mutations = (
            ("--classify-prerequisites", "--acquire"),
            ('--qualification "${{ runner.temp }}/gdw-store-recovery-qualification.json"', '--qualification "unreviewed.json"'),
            ("        id: recovery_mode\n", "        id: recovery_mode\n        env:\n          HF_TOKEN: alternate\n"),
            ("      mode: ${{ steps.recovery_mode.outputs.mode }}", "      mode: managed-recovery"),
            ('"huggingface_hub==1.23.0"', '"huggingface_hub==1.31.0"'),
        )
        for before, after in mutations:
            with self.subTest(before=before):
                self.assertIn(before, self.source)
                with self.assertRaisesRegex(WorkflowContractError, "classifier|metadata cannot emit authority|manual interpreter"):
                    assert_manual_step_contract(self.source.replace(before, after, 1))

    def test_inspection_keeps_native_identity_disabled_pair_and_private_artifact_scope(self):
        start = self.source.index("  durable-acquisition:\n")
        end = self.source.index("  resume-paused-space:\n", start)
        job = self.source[start:end]
        mutations = (
            ("      actions: read", "      actions: write"),
            ("          ref: e3ec47ad2e99a535839afe0f30fefbd8973d52da", "          ref: main"),
            ("--inspect-held-acquisition", '--inspect-held-acquisition --source-artifact-id "1"'),
            ("--inspect-held-acquisition", '--inspect-held-acquisition --source-artifact-sha256 "unreviewed"'),
            ("--inspect-held-acquisition", '--inspect-held-acquisition --qualification-artifact-id "1"'),
            ("--inspect-held-acquisition", '--inspect-held-acquisition --qualification-artifact-sha256 "unreviewed"'),
            ("--inspect-held-acquisition", '--inspect-held-acquisition --publisher-script "$GITHUB_WORKSPACE/scripts/unreviewed.py"'),
            ("--inspect-held-acquisition", '--inspect-held-acquisition --github-output "$GITHUB_OUTPUT"'),
            ("--inspect-held-acquisition", '--inspect-held-acquisition --retry'),
            ("scripts/acquire_gdw_durable_storage.py --inspect-held-acquisition", "scripts/unknown.py --inspect-held-acquisition"),
            ("--inspect-held-acquisition", "--acquire"),
            ("--inspect-held-acquisition", "--fetch-locator"),
            ("--inspect-held-acquisition", "--reconcile-supervised-acquisition"),
            ('--output "$RUNNER_TEMP/gdw-durable-acquisition.json"', '--output "$RUNNER_TEMP/gdw-durable-acquisition.json" || true'),
            ("        if: ${{ github.ref == 'refs/heads/main' && false }}\n", "        if: ${{ always() }}\n"),
            ("        if: ${{ github.ref == 'refs/heads/main' && false }}\n", ""),
            ("        if: ${{ github.ref == 'refs/heads/main' && false }}\n", "        if: ${{ github.ref == 'refs/heads/main' && true }}\n"),
            ("scripts/configure_hf_gdw_runtime.py", "scripts/configure_hf_series_a_runtime.py"),
            ("--managed-deadline-seconds 120", "--managed-deadline-seconds 120 --force"),
            ('--output "$RUNNER_TEMP/gdw-managed-configuration.json"', '--output "$RUNNER_TEMP/gdw-managed-configuration.json" || true'),
            ("          path: ${{ runner.temp }}/gdw-durable-acquisition.json", "          path: ${{ runner.temp }}/**"),
            ("        id: acquisition_artifact", "        id: arbitrary_artifact"),
        )
        for before, after in mutations:
            with self.subTest(before=before):
                self.assertIn(before, job)
                with self.assertRaisesRegex(WorkflowContractError, "acquisition"):
                    assert_manual_step_contract(self.source.replace(job, job.replace(before, after, 1), 1))

    def test_pair_configuration_cannot_precede_acquisition_or_be_repeated(self):
        start = self.source.index("  durable-acquisition:\n")
        end = self.source.index("  resume-paused-space:\n", start)
        job = self.source[start:end]
        config_start = job.index("      - name: Install the persistent old-source guard")
        config_end = job.index("      - name: Retain only the bounded inspection metadata report", config_start)
        config = job[config_start:config_end]
        removed = job[:config_start] + job[config_end:]
        acquire_marker = "      - name: Inspect the held prior acquisition without provider mutation"
        for candidate in (removed, job.replace(config, config + config, 1),
                          removed.replace(acquire_marker, config + acquire_marker, 1)):
            with self.subTest(candidate=candidate), self.assertRaisesRegex(WorkflowContractError, "acquisition"):
                assert_manual_step_contract(self.source.replace(job, candidate, 1))

    def test_managed_runtime_selector_cannot_acquire_or_repeat_configuration(self):
        start = self.source.index("  runtime-config:\n")
        end = self.source.index("  deploy:\n", start)
        job = self.source[start:end]
        for before, after in (
            ("--fetch-locator", "--acquire"),
            ('--acquisition-artifact-id "${{ needs.durable-acquisition.outputs.artifact_id }}"', '--acquisition-artifact-id "1"'),
            (LEGACY_MODE_CONDITION, "always()"),
            ("            ${{ env.LIVE_PROOF_ADMISSION_REPORT }}", "            ${{ runner.temp }}/**"),
        ):
            with self.subTest(before=before):
                self.assertIn(before, job)
                with self.assertRaisesRegex(WorkflowContractError, "managed runtime"):
                    assert_manual_step_contract(self.source.replace(job, job.replace(before, after, 1), 1))


# The predecessor workflow class above records the deliberately held acquisition
# contract.  The accepted read-only v2 diagnostic superseded that exact state.
ManualPrerequisiteWorkflowTests.__test__ = False


class ManualPrerequisiteWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.source = WORKFLOW.read_text(encoding="utf-8")
        self.jobs = assert_manual_dependency_graph(self.source)

    def test_no_preservation_or_ambiguous_acquisition_replay(self):
        recovery = self.jobs["recovery-reconciliation"]
        manual = self.jobs["manual-prerequisites"]
        acquisition = self.jobs["durable-acquisition"]
        selected = json.dumps([recovery, manual, acquisition], sort_keys=True)
        self.assertNotIn("preserve_hf_gdw_store.py", selected)
        self.assertNotIn("--supervised-acquisition", selected)
        self.assertNotIn("--inspect-held-acquisition", selected)
        self.assertNotIn("--reconcile-supervised-acquisition", selected)
        self.assertNotIn("--retry", selected)
        self.assertNotIn("--restore", selected)

    def test_only_native_read_step_receives_hf_credential(self):
        expected = "${{ secrets.HF_ORG_TOKEN || secrets.HF_TOKEN }}"
        bindings = []
        def visit(value, path=()):
            if isinstance(value, dict):
                for key, child in value.items():
                    visit(child, path + (key,))
            elif isinstance(value, list):
                for index, child in enumerate(value):
                    visit(child, path + (index,))
            elif isinstance(value, str) and (
                    "secrets.HF_ORG_TOKEN" in value or "secrets.HF_TOKEN" in value):
                bindings.append((path, value))
        visit({name: self.jobs[name] for name in (
            "recovery-reconciliation", "manual-prerequisites", "durable-acquisition")})
        self.assertEqual([value for _path, value in bindings], [expected, expected])
        self.assertNotIn("env", self.jobs["manual-prerequisites"])

    def test_closed_artifact_allowlists_exclude_candidates_and_captures(self):
        recovery = self.jobs["recovery-reconciliation"]["steps"][-1]["with"]["path"]
        manual = self.jobs["manual-prerequisites"]["steps"][-1]["with"]["path"]
        acquisition = self.jobs["durable-acquisition"]["steps"][-1]["with"]["path"]
        self.assertEqual(set(recovery.splitlines()), {
            "${{ runner.temp }}/gdw-diagnostic-continuation.json",
            "${{ runner.temp }}/gdw-continuation-qualification.json"})
        self.assertEqual(manual, "${{ runner.temp }}/manual-prerequisites.json")
        self.assertEqual(set(acquisition.splitlines()), {
            "${{ runner.temp }}/gdw-durable-acquisition.json",
            "${{ runner.temp }}/gdw-managed-configuration.json"})
        self.assertNotRegex(recovery + manual + acquisition,
            r"candidate\.sqlite|capture-|private-store|hub-cache|/\*\*|\\\*\\\*")

    def test_managed_configuration_requires_acknowledged_locator(self):
        steps = self.jobs["durable-acquisition"]["steps"]
        continuation = next(index for index, step in enumerate(steps)
            if step.get("name") == "Continue once from the accepted diagnostic and verified capture")
        configuration = next(index for index, step in enumerate(steps)
            if step.get("name") == "Install the persistent old-source guard and both managed configurations once")
        self.assertLess(continuation, configuration)
        self.assertNotIn("if", steps[configuration])
        self.assertIn('--managed-acquisition "$RUNNER_TEMP/gdw-durable-acquisition.json"',
                      steps[configuration]["run"])

    def test_unknown_metadata_cannot_gain_an_authority_output(self):
        for before, after in (
            ("outputs.mode == 'managed-recovery'", "outputs.mode != 'managed-recovery'"),
            ("outputs.admitted == 'true'", "outputs.admitted != 'true'"),
            ("gdw-continuation-qualification.json", "candidate.sqlite3"),
            ("actions: read", "actions: write"),
        ):
            with self.subTest(after=after):
                candidate = self.source.replace(before, after, 1)
                with self.assertRaises(WorkflowContractError):
                    assert_manual_dependency_graph(candidate)

    def test_removed_credentials_and_external_coordination_stay_removed(self):
        for token in ("DOCS_READ_TOKEN", "--github-read-token", "--operator-token",
                      "--capacity-donor", "gh issue", "issues: write",
                      "add_space_secret", "delete_space_secret"):
            self.assertNotIn(token, self.source)

    def test_unrelated_finance_publisher_is_unreachable(self):
        job = self.jobs["publish-finance-projection"]
        self.assertEqual(job["if"],
            "${{ github.event_name == 'push' && github.run_attempt == 1 && "
            "needs.manual-prerequisites.result == 'success' && false }}")
        with self.assertRaises(WorkflowContractError):
            assert_manual_dependency_graph(self.source.replace(
                "needs.manual-prerequisites.result == 'success' && false",
                "needs.manual-prerequisites.result == 'success' && true", 1))


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
