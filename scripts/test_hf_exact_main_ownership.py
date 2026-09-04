from __future__ import annotations

import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

SCRIPT = pathlib.Path(__file__).with_name("hf_exact_main_ownership.py")
SPEC = importlib.util.spec_from_file_location("hf_exact_main_ownership", SCRIPT)
assert SPEC and SPEC.loader
ownership = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = ownership
SPEC.loader.exec_module(ownership)

EXPECTED = "a" * 40
NEWER = "b" * 40
DIVERGED = "c" * 40
TOKEN = "github_example_secret_value"


class ExactMainOwnershipTests(unittest.TestCase):
    def run_case(self, responder, *, expected: str = EXPECTED):
        with tempfile.TemporaryDirectory() as directory:
            receipt = pathlib.Path(directory) / "ownership.json"
            outputs = pathlib.Path(directory) / "github-output.txt"
            with mock.patch.object(ownership, "request_json", side_effect=responder):
                result = ownership.execute(
                    repository="szl-holdings/a11oy",
                    expected_sha=expected,
                    receipt_path=receipt,
                    github_output=outputs,
                    token=TOKEN,
                )
            return (
                result,
                json.loads(receipt.read_text(encoding="utf-8")),
                outputs.read_text(encoding="utf-8"),
            )

    def test_exact_main_is_owned_and_publishable(self) -> None:
        calls: list[str] = []

        def responder(path: str, _token: str):
            calls.append(path)
            return {"commit": {"sha": EXPECTED}}

        result, report, outputs = self.run_case(responder)
        self.assertEqual(0, result)
        self.assertEqual("OWNED", report["status"])
        self.assertTrue(report["publish"])
        self.assertTrue(report["source_verified"])
        self.assertTrue(report["expected_is_ancestor_of_observed"])
        self.assertFalse(report["external_writes_performed"])
        self.assertEqual(1, len(calls))
        self.assertIn("publish=true\n", outputs)
        self.assertIn(f"observed_main_sha={EXPECTED}\n", outputs)

    def test_strict_ancestor_is_verified_neutral_supersession(self) -> None:
        calls: list[str] = []

        def responder(path: str, _token: str):
            calls.append(path)
            if "/branches/main" in path:
                return {"commit": {"sha": NEWER}}
            return {
                "status": "ahead",
                "ahead_by": 3,
                "behind_by": 0,
                "merge_base_commit": {"sha": EXPECTED},
            }

        result, report, outputs = self.run_case(responder)
        self.assertEqual(0, result)
        self.assertEqual("SUPERSEDED_BY_NEWER_MAIN", report["status"])
        self.assertFalse(report["publish"])
        self.assertTrue(report["source_verified"])
        self.assertTrue(report["expected_is_ancestor_of_observed"])
        self.assertEqual(NEWER, report["observed_main_sha"])
        self.assertEqual(2, len(calls))
        self.assertIn(f"/compare/{EXPECTED}...{NEWER}", calls[1])
        self.assertIn("publish=false\n", outputs)
        self.assertIn("ownership_status=SUPERSEDED_BY_NEWER_MAIN\n", outputs)

    def test_diverged_source_is_not_neutralized(self) -> None:
        def responder(path: str, _token: str):
            if "/branches/main" in path:
                return {"commit": {"sha": DIVERGED}}
            return {
                "status": "diverged",
                "ahead_by": 2,
                "behind_by": 1,
                "merge_base_commit": {"sha": NEWER},
            }

        result, report, outputs = self.run_case(responder)
        self.assertEqual(1, result)
        self.assertEqual("ERROR", report["status"])
        self.assertFalse(report["publish"])
        self.assertFalse(report["source_verified"])
        self.assertFalse(report["expected_is_ancestor_of_observed"])
        self.assertEqual("OwnershipError", report["error"]["type"])
        self.assertIn("ownership_status=ERROR\n", outputs)

    def test_malformed_branch_response_fails_closed(self) -> None:
        result, report, outputs = self.run_case(lambda _path, _token: {"commit": {}})
        self.assertEqual(1, result)
        self.assertEqual("ERROR", report["status"])
        self.assertFalse(report["publish"])
        self.assertFalse(report["source_verified"])
        self.assertIn("ownership_status=ERROR\n", outputs)

    def test_provider_failure_receipt_contains_no_secret(self) -> None:
        def responder(_path: str, _token: str):
            raise ownership.OwnershipError("provider failed with " + TOKEN)

        result, report, _outputs = self.run_case(responder)
        encoded = json.dumps(report, sort_keys=True)
        self.assertEqual(1, result)
        self.assertEqual("ERROR", report["status"])
        self.assertFalse(report["secret_values_recorded"])
        self.assertNotIn(TOKEN, encoded)
        self.assertEqual(64, len(report["error"]["message_sha256"]))

    def test_invalid_expected_sha_is_rejected_before_provider_read(self) -> None:
        calls = 0

        def responder(_path: str, _token: str):
            nonlocal calls
            calls += 1
            return {"commit": {"sha": EXPECTED}}

        result, report, _outputs = self.run_case(responder, expected="A" * 40)
        self.assertEqual(1, result)
        self.assertEqual(0, calls)
        self.assertEqual("ERROR", report["status"])

    def test_request_surface_is_get_only_and_bounded(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('method="GET"', source)
        for method in ("POST", "PUT", "PATCH", "DELETE"):
            self.assertNotIn(f'method="{method}"', source)
        self.assertIn("MAX_RESPONSE_BYTES", source)
        self.assertNotIn("huggingface", source.lower())


if __name__ == "__main__":
    unittest.main(verbosity=2)
