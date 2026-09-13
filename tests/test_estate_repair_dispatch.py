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
        self.assertIn("VERTICAL_PLAN_JSON: ${{ inputs.vertical_plan_json }}", text)
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

    def test_explicit_vertical_input_without_plan_file_is_not_authorization(self) -> None:
        decision = dispatch.plan_repair_dispatch(
            repair=True,
            vertical_requested="true",
            current_sha=SHA,
            expected_sha=SHA,
            plan=None,
        )
        self.assertFalse(decision["vertical_flagships"])
        self.assertEqual(decision["vertical_state"], "NOT_REQUESTED")

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


class CommandBoundaryTests(unittest.TestCase):
    """The last argv boundary must not trust an incomplete/tampered decision."""

    def decision(self, vertical: bool = True) -> dict:
        return dispatch.plan_repair_dispatch(
            repair=True, vertical_requested=vertical, expected_sha=SHA,
            current_sha=SHA,
            plan={"complete": True, "approved": True, "expected_source_revision": SHA},
        )

    def command(self, decision: dict) -> list[str] | None:
        return dispatch.hf_sync_command(decision, repo="szl-holdings/a11oy")

    def test_generated_decisions_retain_the_observed_source(self) -> None:
        for vertical in (True, False):
            with self.subTest(vertical=vertical):
                self.assertEqual(self.decision(vertical)["expected_source_revision"], SHA)

    def test_incomplete_vertical_plan_retains_product_source(self) -> None:
        result = dispatch.plan_repair_dispatch(
            repair=True, vertical_requested=True, expected_sha=SHA, current_sha=SHA,
        )
        self.assertEqual(result["expected_source_revision"], SHA)
        self.assertEqual(self.command(result), [
            "gh", "workflow", "run", "hf-sync.yml", "--repo",
            "szl-holdings/a11oy", "--ref", "main",
        ])

    def test_missing_decision_source_cannot_construct_a_command(self) -> None:
        value = self.decision()
        value.pop("expected_source_revision", None)
        with self.assertRaises(ValueError):
            self.command(value)

    def test_invalid_decision_source_cannot_construct_a_command(self) -> None:
        for source in (None, "", "g" * 40, SHA + "\n", 1, True, "A" * 40):
            with self.subTest(source=source), self.assertRaises(ValueError):
                self.command({**self.decision(), "expected_source_revision": source})

    def test_substituted_plan_cannot_validate_against_its_own_sha(self) -> None:
        value = self.decision()
        value["approved_plan"]["expected_source_revision"] = "b" * 40
        with self.assertRaises(ValueError):
            self.command(value)

    def test_product_scope_must_be_explicit_boolean_true(self) -> None:
        for scope in (None, False, 0, 1, "true", [], {}):
            with self.subTest(scope=scope), self.assertRaises(ValueError):
                self.command({**self.decision(), "product_scope": scope})

    def test_vertical_scope_cannot_silently_coerce_to_product_only(self) -> None:
        for scope in (None, 0, 1, "true", "false", [], {}):
            with self.subTest(scope=scope), self.assertRaises(ValueError):
                self.command({**self.decision(), "vertical_flagships": scope})

    def test_production_authorization_remains_explicitly_false(self) -> None:
        for value in (None, True, 0, 1, "false", [], {}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.command({**self.decision(), "production_authorization": value})

    def test_scope_and_readiness_labels_cannot_contradict_each_other(self) -> None:
        for vertical, state in ((True, "NOT_REQUESTED"), (False, "REQUESTED"),
                                (True, "PASS"), (False, "LIVE"), (False, None)):
            with self.subTest(vertical=vertical, state=state), self.assertRaises(ValueError):
                self.command({**self.decision(vertical), "vertical_state": state})

    def test_reason_must_agree_with_the_requested_scope(self) -> None:
        for vertical, reason in ((True, "PRODUCT_ONLY"), (False, "PRODUCT_AND_VERTICAL"),
                                 (True, "SOURCE_MOVED_BEFORE_DISPATCH"), (False, None),
                                 (True, []), (False, {})):
            with self.subTest(vertical=vertical, reason=reason), self.assertRaises(ValueError):
                self.command({**self.decision(vertical), "reason": reason})

    def test_product_only_receipt_cannot_smuggle_a_vertical_plan(self) -> None:
        value = self.decision(False)
        value["approved_plan"] = self.decision()["approved_plan"]
        with self.assertRaises(ValueError):
            self.command(value)

    def test_bare_dispatch_true_is_not_sufficient(self) -> None:
        with self.assertRaises(ValueError):
            self.command({"dispatch": True})

    def test_false_or_truthy_nonboolean_dispatch_never_builds_argv(self) -> None:
        for value in (False, None, 0, 1, "true", "false", [], {}):
            with self.subTest(value=value):
                self.assertIsNone(self.command({**self.decision(), "dispatch": value}))

    def test_nonmapping_decision_never_builds_argv(self) -> None:
        for value in (None, [], "true", 1):
            with self.subTest(value=value):
                self.assertIsNone(self.command(value))

    def test_repository_cannot_select_a_url_host_or_flag(self) -> None:
        for repo in ("https://example.invalid/o/r", "example.invalid/o/r", "-Rother/repo",
                     "szl-holdings/a11oy\n", "szl-holdings/a11oy?x=y", "o/..", "o/r#x", None):
            with self.subTest(repo=repo), self.assertRaises(ValueError):
                dispatch.hf_sync_command(self.decision(), repo=repo)

    def test_repository_owner_name_form_is_preserved_exactly(self) -> None:
        for repo in ("szl-holdings/a11oy", "a/r", "other-owner/repo_name.v2", "szl-holdings/.github"):
            with self.subTest(repo=repo):
                argv = dispatch.hf_sync_command(self.decision(False), repo=repo)
                self.assertEqual(argv, ["gh", "workflow", "run", "hf-sync.yml",
                                        "--repo", repo, "--ref", "main"])

    def test_builder_does_not_forward_extra_plan_fields(self) -> None:
        value = self.decision()
        value["approved_plan"]["operator_note"] = "do-not-forward-this-canary"
        argv = self.command(value)
        serialized = next(arg.split("=", 1)[1] for arg in argv if arg.startswith("vertical_plan_json="))
        self.assertEqual(json.loads(serialized), {
            "complete": True, "approved": True, "expected_source_revision": SHA,
        })
        self.assertNotIn("do-not-forward-this-canary", json.dumps(argv))
        self.assertEqual(value["approved_plan"]["operator_note"], "do-not-forward-this-canary")

    def test_command_construction_does_not_mutate_a_decision(self) -> None:
        value = self.decision()
        before = json.dumps(value, sort_keys=True)
        self.command(value)
        self.assertEqual(json.dumps(value, sort_keys=True), before)

    def test_product_downgrade_does_not_carry_a_plan_or_vertical_flag(self) -> None:
        value = dispatch.plan_repair_dispatch(
            repair=True, vertical_requested=True, expected_sha=SHA,
            current_sha=SHA, plan={"complete": False, "approved": True},
        )
        argv = self.command(value)
        self.assertNotIn("publish_vertical_flagships=true", argv)
        self.assertTrue(all(not arg.startswith("vertical_plan_json=") for arg in argv))

    def test_overflowed_numbers_in_nested_plan_data_are_rejected(self) -> None:
        for token in ("1e9999", "-1e9999", "1.7976931348623159e308"):
            text = '{"complete":true,"approved":true,"expected_source_revision":"' + SHA + '\", "extra":[{"value":' + token + '}]} '
            with self.subTest(token=token):
                self.assertIsNone(dispatch.parse_plan(text))

    def test_finite_optional_plan_numbers_remain_supported(self) -> None:
        for token in ("0.0", "-0.0", "1.25", "1e20"):
            with self.subTest(token=token):
                self.assertIsNotNone(dispatch.parse_plan('{"extra":' + token + '}'))

    def test_parser_nontext_inputs_fail_closed(self) -> None:
        for text in (None, 1, True, {}, [], b"{}"):
            with self.subTest(text=text):
                self.assertIsNone(dispatch.parse_plan(text))

    def test_missing_required_decision_fields_are_not_defaulted(self) -> None:
        for field in ("product_scope", "vertical_flagships", "production_authorization",
                      "vertical_state", "reason"):
            value = self.decision()
            value.pop(field)
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.command(value)


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
