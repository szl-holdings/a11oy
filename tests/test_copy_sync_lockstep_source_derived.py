from __future__ import annotations

# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings
# Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>

import importlib.util
import pathlib
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
        self.assertTrue(CHECKER.has_source_derived_deploy_contract(workflow))

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
                    CHECKER.has_source_derived_deploy_contract(
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
        self.assertFalse(CHECKER.has_source_derived_deploy_contract(workflow))

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
        self.assertFalse(CHECKER.has_source_derived_deploy_contract(workflow))

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
        self.assertTrue(CHECKER.has_source_derived_deploy_contract(workflow))

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
                    CHECKER.has_source_derived_deploy_contract(workflow)
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
                    CHECKER.has_source_derived_deploy_contract(workflow)
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
                    CHECKER.has_source_derived_deploy_contract(workflow)
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
                    CHECKER.has_source_derived_deploy_contract(trigger + deploy)
                )

        reinclude = textwrap.dedent(
            """
            on:
              push:
                branches: [m*, '!m*', main]
            """
        )
        self.assertTrue(
            CHECKER.has_source_derived_deploy_contract(reinclude + deploy)
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
            CHECKER.has_source_derived_deploy_contract(block_comment + deploy)
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
                    CHECKER.has_source_derived_deploy_contract(extended + deploy)
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
                    CHECKER.has_source_derived_deploy_contract(trigger + deploy)
                )

        quoted_main = textwrap.dedent(
            """
            on:
              push:
                branches: ["feature,only", "main"]
            """
        )
        self.assertTrue(
            CHECKER.has_source_derived_deploy_contract(quoted_main + deploy)
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
                    CHECKER.has_source_derived_deploy_contract(
                        textwrap.dedent(trigger) + deploy
                    )
                )

    def test_shipped_repository_passes_the_real_lockstep_guard(self) -> None:
        with mock.patch.object(sys, "argv", ["check_copy_sync_lockstep.py", str(ROOT)]):
            self.assertEqual(0, CHECKER.main())


if __name__ == "__main__":
    unittest.main(verbosity=2)
