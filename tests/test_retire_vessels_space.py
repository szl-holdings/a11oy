# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import ast
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".github" / "scripts" / "retire_vessels_space.py"
WORKFLOW = ROOT / ".github" / "workflows" / "retire-vessels-space.yml"


def secret_access_violations(source: str) -> list[str]:
    forbidden = {
        "get_space_secrets", "get_space_variables", "list_secrets",
        "secret_value", "token_value",
    }
    violations = []
    for node in ast.walk(ast.parse(source)):
        identity = (node.id if isinstance(node, ast.Name) else
                    node.attr if isinstance(node, ast.Attribute) else
                    node.value if isinstance(node, ast.Constant) and isinstance(node.value, str)
                    else "")
        if identity.lower() in forbidden:
            violations.append(identity)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in {"print", "repr"} and any(
                isinstance(child, ast.Name) and child.id == "token"
                for child in ast.walk(node)
            ):
                violations.append("token output")
        if isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                if isinstance(key, ast.Constant) and key.value == "secret_values_read":
                    if not isinstance(value, ast.Constant) or value.value is not False:
                        violations.append("secret_values_read must be false")
    return violations


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
        self.assertEqual(secret_access_violations(self.script), [])
        self.assertIn('"token_recorded": False', self.script)
        self.assertIn('"secret_values_read": False', self.script)
        self.assertIn('text.replace(token, "<redacted>")', self.script)

    def test_secret_access_guard_rejects_values_but_accepts_false_metadata(self) -> None:
        self.assertEqual(secret_access_violations('{"secret_values_read": False}'), [])
        for source in (
            'api.get_space_secrets("fixture")', 'api.get_space_variables("fixture")',
            'list_secrets()', 'secret_value', 'item.token_value',
            '{"secret_value": "fixture"}', '{"secret_values_read": True}',
            '{"secret_values_read": observed}', 'print(token)', 'repr(token)',
            'print(f"value={token}")',
        ):
            with self.subTest(source=source):
                self.assertTrue(secret_access_violations(source))

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
        self.assertIn("actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9", self.workflow)
        self.assertIn("actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1", self.workflow)
        self.assertIn("actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97", self.workflow)
        uses = re.findall(r"^\s*uses:\s*(\S+)", self.workflow, re.MULTILINE)
        self.assertTrue(uses)
        for value in uses:
            self.assertRegex(value, r"@(?:[0-9a-f]{40})$")


if __name__ == "__main__":
    unittest.main()
