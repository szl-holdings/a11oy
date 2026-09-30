from __future__ import annotations

# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings
# Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>

import importlib.util
import pathlib
import re
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
        )}
        cls.deploy_needs = "[source-admission, manual-prerequisites, resume-paused-space]"
        cls.deploy_if = "${{ needs.source-admission.outputs.publish == 'true' && needs.manual-prerequisites.result == 'success' && needs.resume-paused-space.result == 'success' }}"

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
                "source-admission", "manual-prerequisites", "resume-paused-space"))
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

    def test_resume_requires_the_exact_source_and_manual_success_graph(self) -> None:
        resume = self.fixture_job("resume-paused-space")
        mutations = (
            ("needs: [source-admission, manual-prerequisites]", "needs: source-admission"),
            ("needs: [source-admission, manual-prerequisites]", "needs: [manual-prerequisites]"),
            ("if: ${{ needs.source-admission.outputs.publish == 'true' && needs.manual-prerequisites.result == 'success' }}", "if: true"),
            ("    runs-on:", "    continue-on-error: true\n    runs-on:"),
        )
        for before, after in mutations:
            with self.subTest(after=after):
                self.assertIn(before, resume)
                self.assertFalse(self.strict_contract(self.reviewed_workflow.replace(resume, resume.replace(before, after), 1)))

    def test_missing_duplicate_jobs_and_duplicate_controller_fields_fail(self) -> None:
        for name in ("source-admission", "manual-prerequisites", "resume-paused-space", "deploy"):
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
