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
        # An unchanged payload creates no commit, so the publisher restarts it.
        for stage in ("RUNTIME_ERROR", "BUILD_ERROR"):
            with self.subTest(stage=stage):
                api = RecordingApi(stage)
                decision, report = classify(api)
                self.assertEqual(decision, {"restart_required": "true", "converge": "false"})
                self.assertEqual(report["action"], "REBUILD_ON_PUBLICATION")
                self.assertEqual(api.effects, [])

    def test_starting_space_settles_without_provider_effect(self) -> None:
        cases = (
            (["RUNNING_APP_STARTING", "RUNNING"], "ALREADY_ACTIVE", "true", "false"),
            (["RUNTIME_ERROR"], "REBUILD_ON_PUBLICATION", "false", "true"),
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
        self.assertEqual(decision, {"restart_required": "true", "converge": "false"})
        self.assertEqual(report["action"], "REBUILD_ON_PUBLICATION")
        # The evidence report records the decision on this branch too.
        self.assertEqual(report["restart_required"], "true")
        self.assertEqual(report["converge"], "false")
        self.assertEqual(report["rechecks"], MODULE.STARTING_RECHECKS)
        self.assertEqual(sleep.call_count, MODULE.STARTING_RECHECKS)
        self.assertEqual(api.effects, [])

    def test_app_starting_settles_like_running_app_starting(self) -> None:
        api = RecordingApi("APP_STARTING", later_stages=["RUNNING"])
        with patch.object(MODULE.time, "sleep"):
            decision, report = classify(api)
        self.assertEqual(decision, {"restart_required": "false", "converge": "true"})
        self.assertEqual(report["final_stage"], "RUNNING")
        self.assertEqual(api.effects, [])

    def test_sleeping_or_stopped_space_is_started_once_after_publication(self) -> None:
        for stage in ("SLEEPING", "STOPPED"):
            with self.subTest(stage=stage):
                api = RecordingApi(stage)
                decision, report = classify(api)
                self.assertEqual(decision, {"restart_required": "true", "converge": "false"})
                self.assertEqual(report["action"], "START_AFTER_PUBLICATION")
                self.assertEqual(api.effects, [])

    def test_unknown_or_terminal_stages_fail_closed(self) -> None:
        for stage in ("UNKNOWN", "DELETING", "NO_APP_FILE", "CONFIG_ERROR"):
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
                             ["restart_required=true", "converge=false", "stage=PAUSED"])

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


AWAIT_SCRIPT = ROOT / ".github" / "scripts" / "await_hf_runtime_serving.py"
AWAIT_SPEC = importlib.util.spec_from_file_location("await_hf_runtime_serving", AWAIT_SCRIPT)
assert AWAIT_SPEC and AWAIT_SPEC.loader
AWAIT = importlib.util.module_from_spec(AWAIT_SPEC)
AWAIT_SPEC.loader.exec_module(AWAIT)
SOURCE = "c" * 40


class StagedApi:
    def __init__(self, stages: list[str]) -> None:
        self.stages = list(stages)
        self.effects: list[str] = []

    def get_space_runtime(self, *, repo_id: str):
        assert repo_id == CANONICAL
        stage = self.stages.pop(0) if len(self.stages) > 1 else self.stages[0]
        return SimpleNamespace(stage=SimpleNamespace(value=stage))

    def __getattr__(self, name: str):
        def effect(**_kwargs):
            self.effects.append(name)
            raise AssertionError(f"the wait must not call {name}")
        return effect


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds

    def clock(self) -> float:
        return self.now


class AwaitServingAfterConvergenceTests(unittest.TestCase):
    def wait(self, api, fetch, clock, **kwargs):
        return AWAIT.await_serving(api, fetch, repo_id=CANONICAL,
                                   origin="https://szlholdings-a11oy.hf.space",
                                   source_sha=SOURCE, sleep=clock.sleep,
                                   clock=clock.clock, **kwargs)

    def test_only_a_recorded_convergence_write_requires_a_wait(self) -> None:
        self.assertFalse(AWAIT.convergence_wrote([
            {"variables_changed": [], "volume_changed": False}, {"variables_changed": []}]))
        self.assertTrue(AWAIT.convergence_wrote([{"variables_changed": ["A11OY_SERIES_A_DB"]}]))
        self.assertTrue(AWAIT.convergence_wrote([{"variables_changed": [], "volume_changed": True}]))

    def test_no_write_means_no_provider_read_at_all(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            report = Path(temporary) / "config.json"
            report.write_text(json.dumps({"variables_changed": [], "volume_changed": False}))
            with patch.dict("sys.modules", {"huggingface_hub": None, "requests": None}):
                self.assertEqual(AWAIT.main(["--repo-id", CANONICAL, "--origin",
                                             "https://szlholdings-a11oy.hf.space",
                                             "--source-sha", SOURCE, "--report", str(report)]), 0)

    def test_waits_through_the_restart_until_the_source_serves_consecutively(self) -> None:
        api = StagedApi(["RUNNING", "APP_STARTING", "RUNNING", "RUNNING", "RUNNING"])
        served = iter([{"build": {"revision": SOURCE}}] * 10)
        clock = FakeClock()
        polls = self.wait(api, lambda _url: next(served), clock)
        # A pre-restart RUNNING read is discarded by the APP_STARTING reset.
        self.assertEqual(polls, 5)
        self.assertEqual(clock.sleeps[0], AWAIT.INITIAL_DELAY_SECONDS)
        self.assertEqual(api.effects, [])

    def test_wrong_source_or_unreachable_never_settles_and_fails_closed(self) -> None:
        def unreachable(_url):
            raise ConnectionError("reset")
        for fetch in (lambda _url: {"build": {"revision": "d" * 40}}, unreachable):
            with self.subTest(fetch=fetch):
                api = StagedApi(["RUNNING"])
                with self.assertRaises(AWAIT.AwaitError):
                    self.wait(api, fetch, FakeClock(), timeout=120)
                self.assertEqual(api.effects, [])

    def test_wait_helper_has_no_provider_write_call(self) -> None:
        tree = ast.parse(AWAIT_SCRIPT.read_text(encoding="utf-8"))
        called = {node.func.attr for node in ast.walk(tree)
                  if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)}
        for method in ("restart_space", "pause_space", "add_space_variable",
                       "delete_space_variable", "request_space_hardware", "set_space_volumes"):
            self.assertNotIn(method, called)


if __name__ == "__main__":
    unittest.main(verbosity=2)
