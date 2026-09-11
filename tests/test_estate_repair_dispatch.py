from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "estate_repair_dispatch.py"
SPEC = importlib.util.spec_from_file_location("estate_repair_dispatch", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
dispatch = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(dispatch)

ESTATE = ROOT / ".github" / "workflows" / "estate-release-train.yml"
HF_SYNC = ROOT / ".github" / "workflows" / "hf-sync.yml"
SHA = "a" * 40


class RepairDispatchContractTests(unittest.TestCase):
    def test_ordinary_push_does_not_publish_verticals(self) -> None:
        text = HF_SYNC.read_text(encoding="utf-8")
        self.assertIn("publish_vertical_flagships", text)
        self.assertIn(
            "github.event_name == 'workflow_dispatch' && inputs.publish_vertical_flagships",
            text,
        )
        self.assertIn("default: false", text)

    def test_estate_caller_does_not_default_verticals_on(self) -> None:
        text = ESTATE.read_text(encoding="utf-8")
        self.assertIn("publish_vertical_flagships", text)
        self.assertIn("default: false", text)
        self.assertIn("-f publish_vertical_flagships=true", text)
        self.assertIn("estate_repair_dispatch.py", text)

    def test_product_only_repair_does_not_forward_vertical_flag(self) -> None:
        decision = dispatch.plan_repair_dispatch(
            repair=True,
            vertical_requested=False,
            current_sha=SHA,
            expected_sha=SHA,
        )
        self.assertTrue(decision["dispatch"])
        self.assertTrue(decision["product_scope"])
        self.assertFalse(decision["vertical_flagships"])
        self.assertEqual(decision["vertical_state"], "NOT_REQUESTED")
        self.assertEqual(decision["reason"], "PRODUCT_ONLY")
        command = dispatch.hf_sync_command(decision, repo="szl-holdings/a11oy")
        self.assertIsNotNone(command)
        self.assertNotIn("publish_vertical_flagships=true", " ".join(command or []))

    def test_complete_authorized_vertical_plan_forwards_input(self) -> None:
        decision = dispatch.plan_repair_dispatch(
            repair=True,
            vertical_requested=True,
            current_sha=SHA,
            expected_sha=SHA,
            plan={"complete": True, "approved": True, "expected_source_revision": SHA},
        )
        self.assertEqual(decision["reason"], "PRODUCT_AND_VERTICAL")
        self.assertTrue(decision["vertical_flagships"])
        self.assertEqual(decision["vertical_state"], "REQUESTED")
        command = dispatch.hf_sync_command(decision, repo="szl-holdings/a11oy")
        self.assertIn("-f", command or [])
        self.assertIn("publish_vertical_flagships=true", command or [])

    def test_unapproved_plan_stays_not_requested(self) -> None:
        for plan in (
            {"complete": False, "approved": True},
            {"complete": True, "approved": False},
            {"complete": True, "approved": "true"},
            {"complete": 1, "approved": True},
            {},
        ):
            with self.subTest(plan=plan):
                decision = dispatch.plan_repair_dispatch(
                    repair=True,
                    vertical_requested=True,
                    current_sha=SHA,
                    expected_sha=SHA,
                    plan=plan,
                )
                self.assertFalse(decision["vertical_flagships"])
                self.assertEqual(decision["vertical_state"], "NOT_REQUESTED")
                self.assertEqual(
                    decision["reason"], "VERTICAL_PLAN_INCOMPLETE_OR_UNAPPROVED"
                )
                self.assertIs(decision["production_authorization"], False)

    def test_explicit_vertical_input_without_plan_file_is_the_authorization(self) -> None:
        decision = dispatch.plan_repair_dispatch(
            repair=True,
            vertical_requested="true",
            current_sha=SHA,
            expected_sha=SHA,
            plan=None,
        )
        self.assertTrue(decision["vertical_flagships"])
        self.assertEqual(decision["vertical_state"], "REQUESTED")

    def test_source_moved_before_dispatch_refuses_writer(self) -> None:
        decision = dispatch.plan_repair_dispatch(
            repair=True,
            vertical_requested=True,
            current_sha="b" * 40,
            expected_sha=SHA,
        )
        self.assertFalse(decision["dispatch"])
        self.assertEqual(decision["reason"], "SOURCE_MOVED_BEFORE_DISPATCH")
        self.assertIsNone(
            dispatch.hf_sync_command(decision, repo="szl-holdings/a11oy")
        )

    def test_duplicate_dispatch_refused(self) -> None:
        decision = dispatch.plan_repair_dispatch(
            repair=True,
            vertical_requested=True,
            duplicate_dispatch=True,
        )
        self.assertFalse(decision["dispatch"])
        self.assertEqual(decision["reason"], "DUPLICATE_DISPATCH_REFUSED")

    def test_repair_not_requested_does_not_dispatch(self) -> None:
        decision = dispatch.plan_repair_dispatch(repair=False, vertical_requested=True)
        self.assertFalse(decision["dispatch"])
        self.assertEqual(decision["vertical_state"], "NOT_REQUESTED")
        self.assertEqual(decision["reason"], "REPAIR_NOT_REQUESTED")

    def test_not_requested_never_equals_pass(self) -> None:
        decision = dispatch.plan_repair_dispatch(repair=True, vertical_requested=False)
        self.assertEqual(decision["vertical_state"], "NOT_REQUESTED")
        self.assertNotEqual(decision["vertical_state"], "PASS")
        self.assertIs(decision["production_authorization"], False)

    def test_cli_writes_github_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "out.txt"
            code = dispatch.main(
                [
                    "--repair",
                    "true",
                    "--vertical-requested",
                    "false",
                    "--expected-sha",
                    SHA,
                    "--current-sha",
                    SHA,
                    "--github-output",
                    str(output),
                ]
            )
            self.assertEqual(code, 0)
            text = output.read_text(encoding="utf-8")
            self.assertIn("vertical_flagships=false", text)
            self.assertIn("vertical_state=NOT_REQUESTED", text)


class WorkflowContractTests(unittest.TestCase):
    def test_hf_sync_vertical_job_remains_opt_in(self) -> None:
        text = HF_SYNC.read_text(encoding="utf-8")
        self.assertIn("if: ${{ github.event_name == 'workflow_dispatch' && inputs.publish_vertical_flagships }}", text)

    def test_estate_offline_suite_includes_dispatch_helper(self) -> None:
        text = ESTATE.read_text(encoding="utf-8")
        self.assertIn("python tests/test_estate_repair_dispatch.py", text)
        self.assertIn("python -m py_compile scripts/estate_repair_dispatch.py", text)


if __name__ == "__main__":
    unittest.main()
