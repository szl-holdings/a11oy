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
    """
)


class SourceDerivedCopySyncTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.reviewed_workflow = (ROOT / ".github/workflows/hf-sync.yml").read_text(encoding="utf-8")
        cls.ownership = (ROOT / "scripts/hf_exact_main_ownership.py").read_bytes()
        cls.manual_helpers = {path: (ROOT / path).read_bytes() for path in (
            "scripts/check_hf_manual_prerequisites.py",
            "scripts/configure_hf_series_a_runtime.py",
            "scripts/configure_hf_gdw_runtime.py",
            "scripts/verify_installed_authority.py",
            "scripts/preserve_hf_gdw_store.py",
            "scripts/gdw_orphan_forensics.py",
            "scripts/qualify_gdw_store_recovery.py",
            "docs/operations/evidence/gdw-capture-37223162231.json",
            "docs/operations/evidence/gdw-recovery-historical-anchors.json",
            "ayllu/keys/council-runtime-2026-07-21.pub",
            "scripts/acquire_gdw_durable_storage.py",
            "scripts/inspect_gdw_held_acquisition.py",
            "scripts/reconcile_gdw_supervised_acquisition.py",
            "scripts/gdw_acquisition_evidence.py",
            "scripts/build_gdw_installed_source_manifest.py",
            "scripts/probe_gdw_runtime_base.py",
            "scripts/probe_gdw_legacy_startup.py",
            "scripts/prove_hf_series_a_restart.py",
            "scripts/prove_hf_gdw_runtime.py",
            "scripts/hf_live_proof_bounds.py",
            "gdw_durable_storage.py",
            "gdw_durable_startup.py",
            "gdw_durable_runtime.py",
            "gdw_durable_source.py",
            "gdw_durable_guard.py",
            "gdw_durable_image.py",
            "gdw_durable_artifacts.py",
            "gdw_auth.py",
            "gdw_workspace.py",
            "gdw_proofs.py",
            "szl_dsse.py",
            "a11oy_signing_key.py",
            "szl_content_address.py",
            "szl_corpus_publish.py",
            "szl_formulas.py",
            "szl_hf_bucket.py",
        )}
        cls.deploy_needs = "[source-admission, manual-prerequisites, durable-acquisition, resume-paused-space]"
        cls.deploy_if = "${{ github.event_name == 'push' && github.run_attempt == 1 && always() && needs.source-admission.outputs.publish == 'true' && needs.manual-prerequisites.result == 'success' && ((needs.manual-prerequisites.outputs.mode == 'managed-recovery' && needs.durable-acquisition.result == 'success') || (needs.manual-prerequisites.outputs.mode != 'managed-recovery' && needs.resume-paused-space.result == 'success')) }}"

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
        inputs = {"ownership_helper": self.ownership, "manual_helpers": self.manual_helpers}
        inputs.update(overrides)
        return CHECKER.has_source_derived_deploy_contract(workflow, **inputs)

    def fixture_contract(self, workflow: str, **inputs) -> bool:
        # Existing controller/COPY/trigger fixtures now use the reviewed graph.
        # Actual workflow and bypass mutations use strict_contract unchanged.
        if "\n  source-admission:\n" not in workflow:
            jobs = "".join(self.fixture_job(name) + "\n" for name in (
                "source-admission", "recovery-reconciliation", "manual-prerequisites", "durable-acquisition",
                "resume-paused-space", "runtime-config"))
            workflow = workflow.replace("\njobs:\n", "\njobs:\n" + jobs, 1)
            workflow = workflow.replace("\n  deploy:\n", "\n  deploy:\n"
                + "    needs: " + self.deploy_needs + "\n"
                + "    if: " + self.deploy_if + "\n", 1)
            workflow = re.sub(r"(?m)^    with:$", "    with:\n"
                + "      require-default-branch-tip: true", workflow)
            inputs.setdefault("ownership_helper", self.ownership)
        inputs.setdefault("manual_helpers", self.manual_helpers)
        return CHECKER.has_source_derived_deploy_contract(workflow, **inputs)

    def test_ungated_and_old_source_only_deploy_cannot_bypass_prerequisites(self) -> None:
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
        for value in ("[source-admission, resume-paused-space]", "[manual-prerequisites, resume-paused-space]",
                      "[source-admission, manual-prerequisites]", "[]",
                      "[source-admission, manual-prerequisites, resume-paused-space]",
                      "[source-admission, manual-prerequisites, durable-acquisition]",
                      "[source-admission, manual-prerequisites, resume-paused-space, arbitrary]",
                      "[source-admission, manual-prerequisites, resume-paused-space, source-admission]",
                      "[manual-prerequisites, source-admission, resume-paused-space]"):
            with self.subTest(value=value):
                self.assertFalse(self.strict_contract(self.reviewed_workflow.replace(self.deploy_needs, value, 1)))
        self.assertFalse(self.strict_contract(self.reviewed_workflow.replace(
            "    needs: " + self.deploy_needs + "\n", "", 1)))

    def test_missing_or_bypassed_deploy_success_condition_fails(self) -> None:
        for value in ("true", "false", "always()", "${{ needs.manual-prerequisites.result == 'success' }}",
                      "${{ needs.source-admission.outputs.publish == 'true' }}"):
            with self.subTest(value=value):
                self.assertFalse(self.strict_contract(self.reviewed_workflow.replace(self.deploy_if, value, 1)))
        self.assertFalse(self.strict_contract(self.reviewed_workflow.replace(
            "    if: " + self.deploy_if + "\n", "", 1)))

    def test_manual_job_and_each_metadata_helper_are_bound(self) -> None:
        job = self.fixture_job("manual-prerequisites")
        self.assertFalse(self.strict_contract(self.reviewed_workflow.replace(job, job.replace("--check-only", ""), 1)))
        for path in self.manual_helpers:
            with self.subTest(path=path):
                changed = dict(self.manual_helpers)
                changed[path] += b"\n# changed prerequisite implementation\n"
                self.assertFalse(self.strict_contract(self.reviewed_workflow, manual_helpers=changed))
                del changed[path]
                self.assertFalse(self.strict_contract(self.reviewed_workflow, manual_helpers=changed))

    def test_missing_malformed_or_extra_manual_helper_bindings_fail(self) -> None:
        for helpers in (None, {}, {**self.manual_helpers, "scripts/unknown.py": b""},
                        {**self.manual_helpers, "scripts/check_hf_manual_prerequisites.py": "not bytes"}):
            self.assertFalse(self.strict_contract(self.reviewed_workflow, manual_helpers=helpers))
        self.assertTrue(self.strict_contract(self.reviewed_workflow, manual_helpers={
            path: data.replace(b"\n", b"\r\n") for path, data in self.manual_helpers.items()}))

    def test_preservation_target_privacy_and_no_admission_implementation_are_byte_bound(self) -> None:
        path = "scripts/preserve_hf_gdw_store.py"
        source = self.manual_helpers[path]
        cases = (
            (b'BUCKET = "SZLHOLDINGS/szl-evidence"', b'BUCKET = "SZLHOLDINGS/public"'),
            (b'PRIVATE_PREFIX = "a11oy/incident-preservation/v1"', b'PRIVATE_PREFIX = "a11oy/gdw"'),
            (b'_value(bucket, "private") is not True', b'False'),
            (b"if occupied:", b"if False:"),
            (b"require_owned_source()", b"pass  # ownership check removed"),
            (b"return 2\n", b"return 0\n"),
        )
        for original, replacement in cases:
            with self.subTest(original=original):
                self.assertIn(original, source)
                changed = dict(self.manual_helpers)
                changed[path] = source.replace(original, replacement, 1)
                self.assertFalse(self.strict_contract(self.reviewed_workflow, manual_helpers=changed))
        # The helper's one local source import has a separate required digest.
        self.assertFalse(self.strict_contract(
            self.reviewed_workflow, ownership_helper=self.ownership + b"\n# unreviewed transitive edit\n"))

    def test_preservation_workflow_overrides_and_private_artifact_widening_are_byte_bound(self) -> None:
        marker = "      - name: Preserve stopped private stores before any runtime mutation\n"
        cases = (
            ("scripts/preserve_hf_gdw_store.py", "scripts/unknown_preservation.py"),
            (marker, marker + "        if: false\n"),
            (marker, marker + "        env:\n          HF_TOKEN: unreviewed-authority\n"),
            ('--output "${{ runner.temp }}/gdw-store-preservation.json"', '--output "${{ runner.temp }}/gdw-store-preservation.json" || true'),
            ("            ${{ runner.temp }}/gdw-store-preservation.json\n", "            ${{ runner.temp }}/**\n"),
        )
        for original, replacement in cases:
            with self.subTest(replacement=replacement):
                self.assertIn(original, self.reviewed_workflow)
                self.assertFalse(self.strict_contract(self.reviewed_workflow.replace(original, replacement, 1)))

    def test_recovery_implementation_and_all_reference_inputs_are_byte_bound(self) -> None:
        path = "scripts/qualify_gdw_store_recovery.py"
        source = self.manual_helpers[path]
        for original, replacement in (
            (b"import preserve_hf_gdw_store as preservation", b"import unreviewed_provider as preservation"),
            (b"import gdw_orphan_forensics as orphan_forensics", b"import unreviewed_forensics as orphan_forensics"),
            (b'_value(bucket, "private") is not True', b"False"),
            (b"require_owned_source()", b"pass  # removed ownership check"),
            (b'return 0 if report["state"] == "LOGICAL_CONTINUITY_VERIFIED" else 2',
             b'return 0 if report["state"] == "LOGICAL_CONTINUITY_VERIFIED" else 0'),
        ):
            with self.subTest(original=original):
                self.assertIn(original, source)
                changed = dict(self.manual_helpers)
                changed[path] = source.replace(original, replacement, 1)
                self.assertFalse(self.strict_contract(self.reviewed_workflow, manual_helpers=changed))
        capture_path = "docs/operations/evidence/gdw-capture-37223162231.json"
        capture = json.loads(self.manual_helpers[capture_path])
        capture["private_manifest"]["sha256"] = "0" * 64
        anchors_path = "docs/operations/evidence/gdw-recovery-historical-anchors.json"
        anchors = json.loads(self.manual_helpers[anchors_path])
        anchors["capture_report_sha256"] = "0" * 64
        # Valid JSON substitutions must fail even when every helper is unchanged.
        for reference_path, value in ((capture_path, capture), (anchors_path, anchors)):
            with self.subTest(reference_path=reference_path):
                changed = dict(self.manual_helpers)
                changed[reference_path] = json.dumps(value, sort_keys=True).encode()
                self.assertFalse(self.strict_contract(self.reviewed_workflow, manual_helpers=changed))
        key_path = "ayllu/keys/council-runtime-2026-07-21.pub"
        changed = dict(self.manual_helpers)
        changed[key_path] += b"\n# unreviewed verification input\n"
        self.assertFalse(self.strict_contract(self.reviewed_workflow, manual_helpers=changed))

    def test_recovery_step_inputs_condition_and_artifact_scope_are_byte_bound(self) -> None:
        marker = "      - name: Qualify the pinned private capture without admitting restore\n"
        for original, replacement in (
            ("scripts/qualify_gdw_store_recovery.py", "scripts/unreviewed_recovery.py"),
            ("docs/operations/evidence/gdw-capture-37223162231.json", "docs/operations/evidence/unreviewed-capture.json"),
            ("docs/operations/evidence/gdw-recovery-historical-anchors.json", "docs/operations/evidence/unreviewed-anchors.json"),
            ("${{ always() && steps.preserve_stores.outcome == 'failure' }}", "always()"),
            ("        id: preserve_stores\n", "        id: unreviewed_preservation\n"),
            (marker, marker + "        continue-on-error: true\n"),
            (marker, marker + "        env:\n          HF_TOKEN: unreviewed-authority\n"),
            ('--output "${{ runner.temp }}/gdw-store-recovery-qualification.json"', '--output "${{ runner.temp }}/gdw-store-recovery-qualification.json" || true'),
            ("            ${{ runner.temp }}/gdw-store-recovery-qualification.json\n", "            ${{ runner.temp }}/**\n"),
        ):
            with self.subTest(replacement=replacement):
                self.assertIn(original, self.reviewed_workflow)
                self.assertFalse(self.strict_contract(self.reviewed_workflow.replace(original, replacement, 1)))

    def test_resume_requires_the_exact_source_and_manual_success_graph(self) -> None:
        resume = self.fixture_job("resume-paused-space")
        mutations = (
            ("needs: [source-admission, manual-prerequisites]", "needs: source-admission"),
            ("needs: [source-admission, manual-prerequisites]", "needs: [manual-prerequisites]"),
            ("if: ${{ github.event_name == 'push' && github.run_attempt == 1 && needs.source-admission.outputs.publish == 'true' && needs.manual-prerequisites.result == 'success' && needs.manual-prerequisites.outputs.mode != 'managed-recovery' }}", "if: true"),
            ("    runs-on:", "    continue-on-error: true\n    runs-on:"),
        )
        for before, after in mutations:
            with self.subTest(after=after):
                self.assertIn(before, resume)
                self.assertFalse(self.strict_contract(self.reviewed_workflow.replace(resume, resume.replace(before, after), 1)))

    def test_acquisition_and_managed_runtime_job_effects_are_exactly_bound(self) -> None:
        cases = {
            "recovery-reconciliation": (
                ("needs: source-admission", "needs: []"),
                ("github.run_attempt == 1", "github.run_attempt >= 1"),
                ("github.event_name == 'push'", "true"),
                (" && false }}", " }}"),
                (" && false }}", " && true }}"),
                ("      actions: read", "      actions: write"),
                ("--reconcile-supervised-acquisition", "--acquire"),
                ('--github-output "$GITHUB_OUTPUT"', '--github-output "$GITHUB_OUTPUT" --source-artifact-id 1'),
                ("${{ runner.temp }}/gdw-supervised-reconciliation.json", "${{ runner.temp }}/**"),
            ),
            "durable-acquisition": (
                ("needs: [source-admission, recovery-reconciliation, manual-prerequisites]", "needs: source-admission"),
                ("needs.manual-prerequisites.result == 'skipped'", "true"),
                ("needs.recovery-reconciliation.result == 'skipped' && ", ""),
                ("needs.source-admission.result == 'success' && ", ""),
                ("needs.source-admission.outputs.publish == 'true'", "true"),
                ("github.run_attempt == 1", "github.run_attempt >= 1"),
                ("    timeout-minutes: 20", "    continue-on-error: true\n    timeout-minutes: 20"),
                ("      actions: read", "      actions: write"),
                ("ref: e3ec47ad2e99a535839afe0f30fefbd8973d52da", "ref: main"),
                ('"huggingface_hub==1.31.0"', '"huggingface_hub==1.23.0"'),
                ("scripts/acquire_gdw_durable_storage.py --inspect-held-acquisition", "scripts/unknown.py --inspect-held-acquisition"),
                ("--inspect-held-acquisition", "--acquire"),
                ("--inspect-held-acquisition", "--fetch-locator"),
                ("--inspect-held-acquisition", "--reconcile-supervised-acquisition"),
                ('--output "$RUNNER_TEMP/gdw-durable-acquisition.json"', '--output "$RUNNER_TEMP/gdw-durable-acquisition.json" || true'),
                ("--inspect-held-acquisition", '--inspect-held-acquisition --source-artifact-id "1"'),
                ("--inspect-held-acquisition", '--inspect-held-acquisition --qualification-artifact-sha256 unreviewed'),
                ("--inspect-held-acquisition", '--inspect-held-acquisition --publisher-script scripts/unreviewed.py'),
                ("--inspect-held-acquisition", '--inspect-held-acquisition --github-output "$GITHUB_OUTPUT"'),
                ("--inspect-held-acquisition", '--inspect-held-acquisition --retry'),
                ("        if: ${{ github.ref == 'refs/heads/main' && false }}\n", ""),
                ("        if: ${{ github.ref == 'refs/heads/main' && false }}\n", "        if: ${{ github.ref == 'refs/heads/main' && true }}\n"),
                ("scripts/configure_hf_gdw_runtime.py", "scripts/configure_hf_series_a_runtime.py"),
                ("--managed-deadline-seconds 120", "--managed-deadline-seconds 120 --force"),
                ("${{ runner.temp }}/gdw-managed-configuration.json", "${{ runner.temp }}/**"),
                ("--output \"$RUNNER_TEMP/gdw-managed-configuration.json\"", "--output \"$RUNNER_TEMP/gdw-managed-configuration.json\" || true"),
            ),
            "runtime-config": (
                ("needs: [manual-prerequisites, durable-acquisition, deploy]", "needs: [manual-prerequisites, deploy]"),
                ("needs.durable-acquisition.result == 'success'", "true"),
                ("--fetch-locator", "--acquire"),
                ('--acquisition-artifact-id "${{ needs.durable-acquisition.outputs.artifact_id }}"', '--acquisition-artifact-id "1"'),
                ('--managed-acquisition "$RUNNER_TEMP/gdw-durable-acquisition.json"', ""),
                ("needs.manual-prerequisites.outputs.mode != 'managed-recovery'", "true"),
                ("${{ env.LIVE_PROOF_ADMISSION_REPORT }}", "${{ runner.temp }}/**"),
            ),
        }
        for name, mutations in cases.items():
            job = self.fixture_job(name)
            for before, after in mutations:
                with self.subTest(job=name, before=before):
                    self.assertIn(before, job)
                    changed = self.reviewed_workflow.replace(job, job.replace(before, after, 1), 1)
                    self.assertFalse(self.strict_contract(changed))

    def test_preservation_cannot_bypass_reconciliation_or_first_attempt(self) -> None:
        job = self.fixture_job("manual-prerequisites")
        for before, after in (
            ("needs.recovery-reconciliation.result == 'success'", "true"),
            ("needs.recovery-reconciliation.outputs.admitted == 'true'", "true"),
            ("github.run_attempt == 1", "github.run_attempt >= 1"),
            (" && false }}", " }}"),
            (" && false }}", " && true }}"),
            ("--supervised-acquisition", ""),
        ):
            with self.subTest(before=before):
                self.assertIn(before, job)
                changed = job.replace(before, after, 1)
                self.assertFalse(self.strict_contract(self.reviewed_workflow.replace(job, changed, 1)))

    def test_native_authority_and_private_storage_boundaries_require_reviewed_source(self) -> None:
        cases = (
            ("scripts/acquire_gdw_durable_storage.py", b"evidence.require_active_acquisition()", b"pass"),
            ("scripts/acquire_gdw_durable_storage.py", b"reproduced == selected", b"True"),
            ("scripts/acquire_gdw_durable_storage.py", b"reconciliation.verify_native_prerequisite(evidence)", b"pass"),
            ("scripts/preserve_hf_gdw_store.py", b"reconciliation.require_expected_absent(self._api, self._evidence, self._deadline)", b"pass"),
            ("scripts/reconcile_gdw_supervised_acquisition.py", b'listing["total_count"] == 1', b"True"),
            ("scripts/reconcile_gdw_supervised_acquisition.py", b'parents[0].get("sha") == PARENT_SOURCE', b"True"),
            ("scripts/reconcile_gdw_supervised_acquisition.py", b'len(raw) == 640 and hashlib.sha256(raw).hexdigest() == REPORT_SHA256', b"True"),
            ("scripts/reconcile_gdw_supervised_acquisition.py", b'type(paths) is list and not paths', b"True"),
            ("scripts/acquire_gdw_durable_storage.py", b'value["diagnostic_code"] in _DIAGNOSTICS', b"True"),
            ("scripts/acquire_gdw_durable_storage.py", b"return 2 if inspect_only else 0", b"return 0"),
            ("scripts/probe_gdw_runtime_base.py", b"if _capture_failure and process.returncode == 2:", b"if True:"),
            ("scripts/acquire_gdw_durable_storage.py", b"backend.empty_parent(deadline)", b"pass"),
            ("scripts/acquire_gdw_durable_storage.py", b"import gdw_durable_storage as storage", b"import unknown_storage as storage"),
            ("scripts/gdw_acquisition_evidence.py", b'self.run.get("status") == "in_progress"', b"True"),
            ("scripts/gdw_acquisition_evidence.py", b'branch.get("protected") is True', b"True"),
            ("scripts/gdw_acquisition_evidence.py", b'"ARTIFACT_MEMBER_MISMATCH"', b'"UNREVIEWED_DECODER"'),
            ("gdw_durable_storage.py", b"parent_commit=parent", b"parent_commit=None"),
            ("gdw_durable_storage.py", b"if not 200 <= response.status_code < 300:", b"if False:"),
        )
        for path, before, after in cases:
            with self.subTest(path=path, before=before):
                self.assertIn(before, self.manual_helpers[path])
                changed = dict(self.manual_helpers)
                changed[path] = changed[path].replace(before, after, 1)
                self.assertFalse(self.strict_contract(self.reviewed_workflow, manual_helpers=changed))
        for path in ("scripts/gdw_acquisition_evidence.py", "scripts/build_gdw_installed_source_manifest.py"):
            changed = dict(self.manual_helpers)
            changed[path] = b"\xff\xfeunreviewed source"
            self.assertFalse(self.strict_contract(self.reviewed_workflow, manual_helpers=changed))

    def test_prerequisite_classifier_cannot_become_a_generic_authority_or_sdk_upgrade(self) -> None:
        job = self.fixture_job("manual-prerequisites")
        for before, after in (
            ("--classify-prerequisites", "--acquire"),
            ("scripts/acquire_gdw_durable_storage.py", "scripts/unreviewed_classifier.py"),
            ('"huggingface_hub==1.23.0"', '"huggingface_hub==1.31.0"'),
            ("mode: ${{ steps.recovery_mode.outputs.mode }}", "mode: managed-recovery"),
            ("steps.recovery_mode.outcome == 'success'", "true"),
            ("        id: recovery_mode\n", "        id: recovery_mode\n        continue-on-error: true\n"),
        ):
            with self.subTest(before=before):
                self.assertIn(before, job)
                self.assertFalse(self.strict_contract(self.reviewed_workflow.replace(job, job.replace(before, after, 1), 1)))

    def test_missing_duplicate_jobs_and_duplicate_controller_fields_fail(self) -> None:
        for name in ("source-admission", "recovery-reconciliation", "manual-prerequisites", "durable-acquisition",
                     "resume-paused-space", "runtime-config", "deploy"):
            job = self.fixture_job(name)
            self.assertFalse(self.strict_contract(self.reviewed_workflow.replace(job, "", 1)))
            self.assertFalse(self.strict_contract(self.reviewed_workflow + "\n" + job))
        deploy = self.fixture_job("deploy")
        for header in ("    needs: " + self.deploy_needs + "\n", "    if: " + self.deploy_if + "\n",
                       "    uses: szl-holdings/.github/.github/workflows/reusable-hf-deploy.yml@e3ec47ad2e99a535839afe0f30fefbd8973d52da\n",
                       "    <<: *hidden\n", "    continue-on-error: true\n"):
            self.assertFalse(self.strict_contract(self.reviewed_workflow.replace(deploy,
                deploy.replace("  deploy:\n", "  deploy:\n" + header, 1), 1)))

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
                uses: szl-holdings/.github/.github/workflows/reusable-hf-deploy.yml@e3ec47ad2e99a535839afe0f30fefbd8973d52da
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
                uses: szl-holdings/.github/.github/workflows/reusable-hf-deploy.yml@e3ec47ad2e99a535839afe0f30fefbd8973d52da
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
                uses: szl-holdings/.github/.github/workflows/reusable-hf-deploy.yml@e3ec47ad2e99a535839afe0f30fefbd8973d52da
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
                uses: szl-holdings/.github/.github/workflows/reusable-hf-deploy.yml@e3ec47ad2e99a535839afe0f30fefbd8973d52da
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
                    uses: szl-holdings/.github/.github/workflows/reusable-hf-deploy.yml@e3ec47ad2e99a535839afe0f30fefbd8973d52da
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
                name: Exact source-derived deployment
                uses: szl-holdings/.github/.github/workflows/reusable-hf-deploy.yml@e3ec47ad2e99a535839afe0f30fefbd8973d52da
                with:
                  hf-repo: SZLHOLDINGS/a11oy
                  ref: ${{ github.sha }}
                  dockerfile-path: "Dockerfile"
                  prune: true
                secrets:
                  HF_TOKEN: ${{ secrets.HF_TOKEN }}
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
                        uses: szl-holdings/.github/.github/workflows/reusable-hf-deploy.yml@e3ec47ad2e99a535839afe0f30fefbd8973d52da
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
                    uses: szl-holdings/.github/.github/workflows/reusable-hf-deploy.yml@e3ec47ad2e99a535839afe0f30fefbd8973d52da
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
                    uses: szl-holdings/.github/.github/workflows/reusable-hf-deploy.yml@e3ec47ad2e99a535839afe0f30fefbd8973d52da
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
                uses: szl-holdings/.github/.github/workflows/reusable-hf-deploy.yml@e3ec47ad2e99a535839afe0f30fefbd8973d52da
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
                uses: szl-holdings/.github/.github/workflows/reusable-hf-deploy.yml@e3ec47ad2e99a535839afe0f30fefbd8973d52da
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
                uses: szl-holdings/.github/.github/workflows/reusable-hf-deploy.yml@e3ec47ad2e99a535839afe0f30fefbd8973d52da
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
