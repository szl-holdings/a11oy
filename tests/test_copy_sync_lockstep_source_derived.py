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


class SourceDerivedCopySyncTests(unittest.TestCase):
    def test_pinned_dockerfile_deployer_is_recognized(self) -> None:
        workflow = textwrap.dedent(
            """
            jobs:
              deploy:
                uses: szl-holdings/.github/.github/workflows/reusable-hf-deploy.yml@9aa36ed914e88bdef2873b26c022e0cecb1e6ec8
                with:
                  dockerfile-path: Dockerfile
            """
        )
        self.assertTrue(CHECKER.has_source_derived_deploy_contract(workflow))

    def test_unpinned_or_implicit_dockerfile_deployer_is_rejected(self) -> None:
        cases = (
            """
            uses: szl-holdings/.github/.github/workflows/reusable-hf-deploy.yml@main
            with:
              dockerfile-path: Dockerfile
            """,
            """
            uses: szl-holdings/.github/.github/workflows/reusable-hf-deploy.yml@9aa36ed914e88bdef2873b26c022e0cecb1e6ec8
            """,
        )
        for workflow in cases:
            with self.subTest(workflow=workflow):
                self.assertFalse(
                    CHECKER.has_source_derived_deploy_contract(
                        textwrap.dedent(workflow)
                    )
                )

    def test_shipped_repository_passes_the_real_lockstep_guard(self) -> None:
        with mock.patch.object(sys, "argv", ["check_copy_sync_lockstep.py", str(ROOT)]):
            self.assertEqual(0, CHECKER.main())


if __name__ == "__main__":
    unittest.main(verbosity=2)
