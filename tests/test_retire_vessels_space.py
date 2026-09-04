# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import ast
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".github" / "scripts" / "retire_vessels_space.py"
WORKFLOW = ROOT / ".github" / "workflows" / "retire-vessels-space.yml"


class VesselsRetirementContract(unittest.TestCase):
    def setUp(self) -> None:
        self.script = SCRIPT.read_text(encoding="utf-8")
        self.workflow = WORKFLOW.read_text(encoding="utf-8")
        ast.parse(self.script)

    def test_target_and_confirmation_are_fixed(self) -> None:
        self.assertIn('TARGET = "SZLHOLDINGS/vessels"', self.script)
        self.assertIn('CONFIRM = "RETIRE-SZLHOLDINGS-VESSELS"', self.script)
        self.assertNotIn('parser.add_argument("--target"', self.script)
        self.assertEqual(self.script.count("api.delete_repo("), 1)
        self.assertIn('repo_id=TARGET, repo_type="space"', self.script)

    def test_replacement_is_killinchu_and_all_maritime_contracts_are_proved(self) -> None:
        required = (
            'REPLACEMENT_REPO = "SZLHOLDINGS/killinchu"',
            'REPLACEMENT_SOURCE = "szl-holdings/killinchu"',
            'REPLACEMENT_ORIGIN = "https://szlholdings-killinchu.hf.space"',
            '"/maritime-intel"',
            '"/api/vessels/healthz"',
            '"/api/build-info"',
            "prove_local_controls",
            "prove_replacement",
            "PUBLIC_FLAGSHIP_SLUGS",
            "FOLDED_INTO_KILLINCHU",
            "obsolete duplicate Hugging Face writer still exists",
            "Packet 8 publisher can recreate the Vessels Space",
        )
        for marker in required:
            self.assertIn(marker, self.script)

    def test_no_provider_secret_or_space_secret_value_is_read_or_recorded(self) -> None:
        forbidden = (
            "get_space_secrets",
            "get_space_variables",
            "list_secrets",
            "secret_value",
            "token_value",
            "print(token",
            "repr(token",
        )
        lowered = self.script.lower()
        for marker in forbidden:
            self.assertNotIn(marker.lower(), lowered)
        self.assertIn('"token_recorded": False', self.script)
        self.assertIn('"secret_values_read": False', self.script)
        self.assertIn('text.replace(token, "<redacted>")', self.script)

    def test_deletion_is_verified_and_receipted(self) -> None:
        self.assertGreaterEqual(self.script.count("repo_exists(TARGET"), 4)
        self.assertIn('report["status"] = "RETIRED_VERIFIED"', self.script)
        self.assertIn('report["status"] = "ALREADY_ABSENT"', self.script)
        self.assertIn('report["status"] = "VALIDATED"', self.script)
        self.assertIn('report["target_after_exists"]', self.script)
        self.assertIn("readme_sha256", self.script)
        self.assertIn("secret_values_read", self.script)

    def test_workflow_is_manual_protected_and_exactly_pinned(self) -> None:
        self.assertIn("workflow_dispatch:", self.workflow)
        self.assertNotIn("\n  push:", self.workflow)
        self.assertIn("environment: production", self.workflow)
        self.assertIn("RETIRE-SZLHOLDINGS-VESSELS", self.workflow)
        self.assertIn("inputs.dry_run", self.workflow)
        self.assertIn("inputs.confirm", self.workflow)
        self.assertIn("HF_ORG_TOKEN", self.workflow)
        self.assertIn("HF_WRITE_TOKEN", self.workflow)
        self.assertIn("HF_TOKEN", self.workflow)
        self.assertIn("retire_vessels_space.py", self.workflow)
        self.assertIn("actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a", self.workflow)
        self.assertIn("actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1", self.workflow)
        self.assertIn("actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97", self.workflow)
        uses = re.findall(r"^\s*uses:\s*(\S+)", self.workflow, re.MULTILINE)
        self.assertTrue(uses)
        for value in uses:
            self.assertRegex(value, r"@(?:[0-9a-f]{40})$")


if __name__ == "__main__":
    unittest.main()
