"""Preflight classification of the canonical Space: read-only, never a restart.

The deploy path starts the Space exactly once. These tests pin that the
preflight helper never calls a provider write, that it never blocks the deploy
that repairs a crashed or failed-build Space, and that a PAUSED Space is
started once by the publisher after the commit, not before it.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".github" / "scripts" / "resume_hf_space.py"
SPEC = importlib.util.spec_from_file_location("resume_hf_space", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

CANONICAL = "SZLHOLDINGS/a11oy"


class RecordingApi:
    def __init__(self, stage: str, later_stages: list[str] | None = None) -> None:
        self.stage = stage
        self.later_stages = list(later_stages or [])
        self.runtime_reads: list[str] = []
        self.effects: list[str] = []

    def get_space_runtime(self, *, repo_id: str):
        self.runtime_reads.append(repo_id)
        if len(self.runtime_reads) > 1 and self.later_stages:
            self.stage = self.later_stages.pop(0)
        return SimpleNamespace(stage=SimpleNamespace(value=self.stage))

    def __getattr__(self, name: str):
        # Any provider method other than the runtime read is a write effect.
        def effect(**_kwargs):
            self.effects.append(name)
            raise AssertionError(f"preflight must not call {name}")
        return effect


def classify(api: RecordingApi, repo_id: str = CANONICAL) -> tuple[dict, dict]:
    report: dict[str, object] = {}
    decision = MODULE.classify_runtime(api, repo_id=repo_id, report=report)
    return decision, report


class PreflightClassificationTests(unittest.TestCase):
    def test_paused_space_is_started_once_by_the_publisher_after_commit(self) -> None:
        api = RecordingApi("PAUSED")
        decision, report = classify(api)
        self.assertEqual(decision, {"restart_required": "true", "converge": "false"})
        self.assertEqual(report["action"], "START_AFTER_PUBLICATION")
        self.assertEqual(api.effects, [])

    def test_serving_space_converges_and_is_rebuilt_by_the_commit(self) -> None:
        api = RecordingApi("RUNNING")
        decision, report = classify(api)
        self.assertEqual(decision, {"restart_required": "false", "converge": "true"})
        self.assertEqual(report["action"], "ALREADY_ACTIVE")
        self.assertEqual(api.effects, [])

    def test_building_space_is_not_restarted_and_defers_convergence(self) -> None:
        for stage in ("BUILDING", "RUNNING_BUILDING"):
            with self.subTest(stage=stage):
                api = RecordingApi(stage)
                decision, _ = classify(api)
                self.assertEqual(decision, {"restart_required": "false", "converge": "false"})
                self.assertEqual(api.effects, [])

    def test_crashed_or_failed_build_space_never_blocks_its_repairing_deploy(self) -> None:
        # Gate G16: the deploy that fixes a crash-looping Space must proceed.
        for stage in ("RUNTIME_ERROR", "BUILD_ERROR"):
            with self.subTest(stage=stage):
                api = RecordingApi(stage)
                decision, report = classify(api)
                self.assertEqual(decision, {"restart_required": "false", "converge": "false"})
                self.assertEqual(report["action"], "REBUILD_ON_PUBLICATION")
                self.assertEqual(api.effects, [])

    def test_starting_space_settles_without_provider_effect(self) -> None:
        cases = (
            (["RUNNING_APP_STARTING", "RUNNING"], "ALREADY_ACTIVE", "true", "false"),
            (["RUNTIME_ERROR"], "REBUILD_ON_PUBLICATION", "false", "false"),
            (["PAUSED"], "START_AFTER_PUBLICATION", "false", "true"),
        )
        for later, action, converge, restart in cases:
            with self.subTest(later=later):
                api = RecordingApi("RUNNING_APP_STARTING", later_stages=list(later))
                with patch.object(MODULE.time, "sleep") as sleep:
                    decision, report = classify(api)
                self.assertEqual(report["action"], action)
                self.assertEqual(decision, {"restart_required": restart, "converge": converge})
                self.assertEqual(report["final_stage"], later[-1])
                self.assertEqual(sleep.call_count, len(later))
                self.assertEqual(api.effects, [])

    def test_start_that_never_settles_is_repaired_by_the_deploy(self) -> None:
        api = RecordingApi("RUNNING_APP_STARTING")
        with patch.object(MODULE.time, "sleep") as sleep:
            decision, report = classify(api)
        self.assertEqual(decision, {"restart_required": "false", "converge": "false"})
        self.assertEqual(report["action"], "REBUILD_ON_PUBLICATION")
        self.assertEqual(report["rechecks"], MODULE.STARTING_RECHECKS)
        self.assertEqual(sleep.call_count, MODULE.STARTING_RECHECKS)
        self.assertEqual(api.effects, [])

    def test_unknown_or_terminal_stages_fail_closed(self) -> None:
        for stage in ("UNKNOWN", "DELETING", "NO_APP_FILE", "CONFIG_ERROR", "STOPPED", "SLEEPING"):
            with self.subTest(stage=stage):
                api = RecordingApi(stage)
                with self.assertRaisesRegex(RuntimeError, "not deployable"):
                    classify(api)
                self.assertEqual(api.effects, [])

    def test_noncanonical_target_is_rejected_before_any_provider_call(self) -> None:
        api = RecordingApi("PAUSED")
        with self.assertRaises(RuntimeError):
            classify(api, repo_id="SZLHOLDINGS/other")
        self.assertEqual(api.runtime_reads, [])
        self.assertEqual(api.effects, [])

    def test_helper_has_no_provider_write_call(self) -> None:
        tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
        called = {node.func.attr for node in ast.walk(tree)
                  if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)}
        for method in ("restart_space", "pause_space", "add_space_variable",
                       "delete_space_variable", "request_space_hardware", "set_space_volumes"):
            self.assertNotIn(method, called)

    def test_cli_writes_report_and_github_outputs(self) -> None:
        api = RecordingApi("PAUSED")
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "report.json"
            github_output = Path(temporary) / "github-output"
            with patch.dict("os.environ", {"HF_TOKEN": "fixture"}), \
                    patch.dict("sys.modules", {"huggingface_hub": SimpleNamespace(HfApi=lambda token: api)}):
                self.assertEqual(MODULE.main(["--repo-id", CANONICAL, "--output", str(output),
                                              "--github-output", str(github_output)]), 0)
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(report["action"], "START_AFTER_PUBLICATION")
            self.assertIs(report["provider_writes_performed"], False)
            self.assertEqual(github_output.read_text(encoding="utf-8").splitlines(),
                             ["restart_required=true", "converge=false"])

    def test_cli_failure_still_writes_report_and_no_outputs(self) -> None:
        api = RecordingApi("DELETING")
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "report.json"
            github_output = Path(temporary) / "github-output"
            with patch.dict("os.environ", {"HF_TOKEN": "fixture"}), \
                    patch.dict("sys.modules", {"huggingface_hub": SimpleNamespace(HfApi=lambda token: api)}), \
                    self.assertRaises(RuntimeError):
                MODULE.main(["--repo-id", CANONICAL, "--output", str(output),
                             "--github-output", str(github_output)])
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(report["error"], "RuntimeError")
            self.assertFalse(github_output.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
