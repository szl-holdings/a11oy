#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Offline workflow and blocked CLI boundaries; no live proof module imports."""

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
    for token in ("DOCS_READ_TOKEN", "--github-read-token", "--operator-token", "--capacity-donor", "HF_CAPACITY_DONOR", "add_space_secret", "delete_space_secret", "gh issue", "issues: write", "OPERATOR_TOKEN"):
        if token in source:
            raise WorkflowContractError("removed credential or donor effect: " + token)
    runtime = jobs["runtime-config"]
    for name, kind, output in (
        ("Block unreviewed live Series-A restart effects", "series-a", "$SERIES_A_LIVE_REPORT"),
        ("Block unreviewed live GDW write effects", "gdw", "$GDW_LIVE_REPORT"),
    ):
        blocked = named_step(runtime, name)
        expected = f'python -B scripts/check_hf_manual_prerequisites.py --blocked-proof {kind} --source-sha "${{{{ github.sha }}}}" --output "{output}"'
        if compact(blocked.get("run", "")) != expected:
            raise WorkflowContractError("live proof remains unadmitted: " + kind)
    if "prove_hf_series_a_restart.py" in source or "prove_hf_gdw_runtime.py" in source:
        raise WorkflowContractError("workflow cannot call retained live proof library")
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
    parity = named_step(relock, "Trigger strict post-deployment GitHub/HF parity")
    expected_enforce = r'''code="${EXIT_CODE:-2}"
if [ "$code" -ne 0 ]; then
  echo "::error::Canonical A11oy relock failed with exit ${code}."
  exit "$code"
fi
echo 'Canonical A11oy is source-bound, singleton, and route-operational.' '''
    if compact(enforce.get("run", "")) != compact(expected_enforce) or enforce.get("if") != "always()":
        raise WorkflowContractError("actual verification exit must be enforced")
    if relock["steps"].index(enforce) >= relock["steps"].index(parity) or "if" in parity:
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


def proof_cli_prefix(path):
    """Return the actual startup prefix only; retained live functions are excluded."""
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    mains = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "main"]
    entries = [node for node in tree.body if isinstance(node, ast.If) and
               ast.dump(node.test) == ast.dump(ast.parse('__name__ == "__main__"', mode="eval").body)]
    if len(mains) != 1 or len(entries) != 1:
        raise WorkflowContractError("proof CLI requires one early main and entrypoint")
    entry = entries[0]
    if mains[0].lineno >= entry.lineno or len(entry.body) != 1 or entry.orelse:
        raise WorkflowContractError("proof CLI entrypoint is not terminal")
    if ast.dump(entry.body[0]) != ast.dump(ast.parse("raise SystemExit(main())").body[0]):
        raise WorkflowContractError("proof CLI entrypoint is not terminal")
    permitted = {"__future__", "argparse", "base64", "hashlib", "json", "os", "re", "time", "datetime", "pathlib", "typing", "urllib", "sys"}
    prefix = ast.Module(body=[node for node in tree.body if node.lineno <= entry.lineno], type_ignores=[])
    for node in ast.walk(prefix):
        if isinstance(node, ast.Import):
            imported = [name.name.split(".", 1)[0] for name in node.names]
        elif isinstance(node, ast.ImportFrom):
            imported = [(node.module or "").split(".", 1)[0]]
        else:
            continue
        if any(name not in permitted for name in imported):
            raise WorkflowContractError("provider import before blocked CLI")
    calls = {ast.unparse(node.func) for node in ast.walk(mains[0]) if isinstance(node, ast.Call)}
    permitted_calls = {"argparse.ArgumentParser", "parser.add_argument", "parser.parse_args", "args.source_sha.strip().lower", "args.source_sha.strip", "re.fullmatch", "Path", "output.parent.mkdir", "json.dumps", "output.write_text", "print"}
    if not calls.issubset(permitted_calls):
        raise WorkflowContractError("blocked CLI has an unreviewed call")
    startup_calls = {ast.unparse(node.func) for node in ast.walk(prefix) if isinstance(node, ast.Call)}
    if not startup_calls.issubset(permitted_calls | {"Path(__file__).resolve", "str", "sys.path.insert", "SystemExit", "main"}):
        raise WorkflowContractError("proof startup has an unreviewed call")
    return prefix, permitted


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

    def test_live_proof_call_cannot_replace_blocked_report_step(self):
        changed = self.source.replace("--blocked-proof series-a", "--admit-live-proof series-a", 1)
        with self.assertRaisesRegex(WorkflowContractError, "live proof remains unadmitted: series-a"):
            assert_manual_step_contract(changed)
        changed = self.source.replace("--blocked-proof gdw", "--admit-live-proof gdw", 1)
        with self.assertRaisesRegex(WorkflowContractError, "live proof remains unadmitted: gdw"):
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
        steps = jobs["relock"]["steps"]
        enforce = named_step(jobs["relock"], "Enforce exact live state")
        parity = named_step(jobs["relock"], "Trigger strict post-deployment GitHub/HF parity")
        self.assertLess(steps.index(enforce), steps.index(parity))
        self.assertIn('code="${EXIT_CODE:-2}"', enforce["run"])
        self.assertIn('exit "$code"', enforce["run"])
        self.assertNotIn("if", parity)
        self.assertEqual(parity["run"], 'gh workflow run hf-module-drift.yml --repo "$GITHUB_REPOSITORY" --ref main')
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


class BlockedProofCLIBoundaryTests(unittest.TestCase):
    def test_actual_startup_prefix_fails_before_credentials_providers_or_live_functions(self):
        for filename, schema, value_field in PROOFS:
            path = ROOT / "scripts" / filename
            prefix, permitted = proof_cli_prefix(path)
            for source_sha in ("a" * 40, "../private-fixture?token=must-not-echo"):
                with self.subTest(script=filename, source_sha=source_sha), tempfile.TemporaryDirectory() as temporary:
                    output = Path(temporary) / "blocked.json"
                    attempts = []

                    def forbidden(*args, **kwargs):
                        attempts.append("unreviewed access")
                        raise AssertionError("blocked CLI crossed its pure boundary")

                    original_import = builtins.__import__

                    def restricted_import(name, *args, **kwargs):
                        if name.split(".", 1)[0] not in permitted | sys.stdlib_module_names:
                            return forbidden()
                        return original_import(name, *args, **kwargs)

                    class NoCredentialEnvironment(dict):
                        # argparse/gettext/shutil may inspect locale and display
                        # defaults. Never consult the real environment; every
                        # other name, including all credential names, is rejected.
                        default_names = {"LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG", "COLUMNS", "LINES"}

                        def get(self, key, default=None):
                            if key in self.default_names:
                                return default
                            return forbidden()

                        def __getitem__(self, key):
                            if key in self.default_names:
                                raise KeyError(key)
                            return forbidden()

                        __iter__ = keys = items = values = forbidden

                    argv = [str(path), "--source-sha", source_sha, "--output", str(output), "--origin", "https://untrusted.invalid/?token=must-not-echo"]
                    if filename == "prove_hf_series_a_restart.py":
                        argv.extend(["--repo-id", "untrusted/fixture"])
                    else:
                        argv.extend(["--restart-repo-id", "untrusted/fixture"])
                    namespace = {"__name__": "__main__", "__file__": str(path), "HfApi": forbidden, "prove": forbidden, "request_json": forbidden, "urlopen": forbidden}
                    saved_path = list(sys.path)
                    captured = io.StringIO()
                    try:
                        environment = NoCredentialEnvironment()
                        with mock.patch.object(sys, "argv", argv), mock.patch.object(os, "environ", environment), mock.patch.object(os, "getenv", environment.get), mock.patch.object(builtins, "__import__", restricted_import), redirect_stdout(captured):
                            with self.assertRaises(SystemExit) as exit_result:
                                exec(compile(prefix, str(path), "exec"), namespace)
                    finally:
                        sys.path[:] = saved_path
                    self.assertEqual(exit_result.exception.code, 1)
                    raw = output.read_text(encoding="utf-8")
                    result = json.loads(raw)
                    self.assertEqual(captured.getvalue(), raw)
                    self.assertEqual(result["schema"], schema)
                    self.assertEqual(result["status"], "FAIL")
                    self.assertIs(result["ok"], False)
                    self.assertEqual(result["evidence"], {})
                    self.assertEqual(result["credential_authority_state"], "UNKNOWN")
                    self.assertIs(result[value_field], False)
                    self.assertEqual(result["source_revision"], source_sha if source_sha == "a" * 40 else "UNVALIDATED")
                    self.assertNotIn("must-not-echo", raw)
                    self.assertEqual(attempts, [])
                    self.assertLess(len(raw.encode()), 16 * 1024)

    def test_provider_import_before_entrypoint_is_a_rejected_negative_fixture(self):
        path = ROOT / "scripts" / PROOFS[0][0]
        source = path.read_text(encoding="utf-8")
        changed = source.replace("import argparse\n", "import argparse\nfrom huggingface_hub import HfApi\n", 1)
        with mock.patch.object(Path, "read_text", return_value=changed), self.assertRaisesRegex(WorkflowContractError, "provider import before blocked CLI"):
            proof_cli_prefix(path)

    def test_live_call_in_early_main_is_a_rejected_negative_fixture(self):
        path = ROOT / "scripts" / PROOFS[1][0]
        source = path.read_text(encoding="utf-8")
        changed = source.replace("def main() -> int:\n", "def main() -> int:\n    request_json('POST', 'https://untrusted.invalid')\n", 1)
        with mock.patch.object(Path, "read_text", return_value=changed), self.assertRaisesRegex(WorkflowContractError, "blocked CLI has an unreviewed call"):
            proof_cli_prefix(path)

    def test_top_level_live_call_before_main_is_a_rejected_negative_fixture(self):
        path = ROOT / "scripts" / PROOFS[1][0]
        source = path.read_text(encoding="utf-8")
        changed = source.replace("def main() -> int:\n", "request_json('POST', 'https://untrusted.invalid')\n\ndef main() -> int:\n", 1)
        with mock.patch.object(Path, "read_text", return_value=changed), self.assertRaisesRegex(WorkflowContractError, "proof startup has an unreviewed call"):
            proof_cli_prefix(path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
