#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Verify the supervisor's source manifest without executing its startup."""

import ast
import hashlib
import pathlib
import unittest

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]


class SupervisorSourcePinTests(unittest.TestCase):
    def test_manifest_pins_all_runtime_sources_to_exact_bytes(self):
        tree = ast.parse((HERE / "windows-supervisor.py").read_text(encoding="utf-8"))
        manifest = next(
            ast.literal_eval(node.value)
            for node in tree.body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "EXPECTED"
                    for target in node.targets)
        )
        self.assertEqual(set(manifest), {
            "ops/vm-model-gateway/gateway.py",
            "ops/vm-model-gateway/runtime_config.py",
            "szl_dsse.py",
            "szl_content_address.py",
        })
        for relative_path, expected in manifest.items():
            with self.subTest(path=relative_path):
                actual = hashlib.sha256((ROOT / relative_path).read_bytes()).hexdigest()
                self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
