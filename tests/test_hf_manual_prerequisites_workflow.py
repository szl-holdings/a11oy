#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Offline workflow, bounded live-proof and blocked CLI boundaries; no network."""

from __future__ import annotations

import ast
import builtins
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

from test_hf_sync_supersession_contract import (
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
  --source-sha "${{ github.sha }}" --output "$SERIES_A_LIVE_REPORT"
code=$?
echo "exit_code=$code" >> "$GITHUB_OUTPUT"
exit "$code"''',
    "gdw": r'''set +e
python -B scripts/prove_hf_gdw_runtime.py \
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
    job = jobs["manual-prerequisites"]
    if [step.get("name") for step in job["steps"]] != ["Checkout the immutable admitted source", "Set up Python", "Install exact metadata client", "Retain metadata checks and fail closed on UNKNOWN authority", "Retain bounded prerequisite decision"]:
        raise WorkflowContractError("manual job must not gain effects")
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
    if compact(step.get("run", "")) != compact(expected) or "if" in step:
        raise WorkflowContractError("manual aggregate must fail before effects")
    if "outputs" in job:
        raise WorkflowContractError("metadata cannot emit authority")
    receipt = named_step(job, "Retain bounded prerequisite decision")
    if receipt.get("if") != "always()" or receipt.get("with", {}).get("if-no-files-found") != "error":
        raise WorkflowContractError("manual decision must be retained")
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
PERMITTED_PROOF_IMPORTS = {"__future__", "argparse", "base64", "hashlib", "json", "os", "re", "sys", "time", "datetime", "pathlib", "typing", "urllib", "hf_live_proof_bounds"}
FORBIDDEN_PROVIDER_EFFECTS = ("delete_space_secret", "add_space_secret", "add_space_variable", "delete_space_variable", "delete_space_storage", "request_space_storage", "request_space_hardware", "upload_file", "delete_repo", "factory_reboot=True")


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
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
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

    def test_removed_checker_check_only_and_exit_propagation_are_detected(self):
        cases = (
            ("scripts/check_hf_manual_prerequisites.py", "scripts/deleted_checker.py"),
            ('--repo-id "$CANONICAL_SPACE" --check-only', '--repo-id "$CANONICAL_SPACE"'),
            ("series_code=$?", "series_code=0"),
            ("gdw_code=$?", "gdw_code=0"),
            ("set -euo pipefail\n          python -B scripts/check_hf_manual_prerequisites.py", "set +e\n          python -B scripts/check_hf_manual_prerequisites.py"),
            ('--source-sha "$GITHUB_SHA" --output "$RUNNER_TEMP/manual-prerequisites.json"', '--source-sha "$GITHUB_SHA" --output "$RUNNER_TEMP/manual-prerequisites.json" || true'),
            ("      - name: Retain metadata checks and fail closed on UNKNOWN authority\n", "      - name: Retain metadata checks and fail closed on UNKNOWN authority\n        if: false\n"),
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
            ('          exit "$code"\n\n      # Writes only', '          exit 0\n\n      # Writes only', "series-a"),
            ('--origin "$CANONICAL_ORIGIN" \\\n            --source-sha "${{ github.sha }}" --output "$GDW_LIVE_REPORT"', '--origin "https://a-11-oy.com" \\\n            --source-sha "${{ github.sha }}" --output "$GDW_LIVE_REPORT"', "gdw"),
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
        changed = self.source.replace("  manual-prerequisites:\n", "  manual-prerequisites:\n    outputs:\n      publish: 'true'\n", 1)
        with self.assertRaisesRegex(WorkflowContractError, "metadata cannot emit authority"):
            assert_manual_step_contract(changed)


class PureAggregateWorkflowBoundaryTests(unittest.TestCase):
    def checker_namespace(self):
        # This module contains only stdlib report parsing, never an HF client.
        tree = ast.parse(CHECKER.read_text(encoding="utf-8"), filename=str(CHECKER))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                self.assertTrue(all(item.name in {"argparse", "json", "re"} for item in node.names))
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
