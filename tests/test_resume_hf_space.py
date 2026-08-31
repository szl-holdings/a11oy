from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".github" / "scripts" / "resume_hf_space.py"
SPEC = importlib.util.spec_from_file_location("resume_hf_space", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class RecordingApi:
    def __init__(self, stage: str, response_stage: str = "BUILDING") -> None:
        self.stage = stage
        self.response_stage = response_stage
        self.restart_calls: list[dict[str, object]] = []

    def get_space_runtime(self, *, repo_id: str):
        self.repo_id = repo_id
        return SimpleNamespace(stage=SimpleNamespace(value=self.stage))

    def restart_space(self, **kwargs):
        self.restart_calls.append(kwargs)
        return SimpleNamespace(
            runtime=SimpleNamespace(
                stage=SimpleNamespace(value=self.response_stage),
            )
        )


class QuotaError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("403 Forbidden: cpu-basic quota limit")
        self.response = SimpleNamespace(status_code=403)


class CapacityApi:
    def __init__(self, quota_failures: int = 1) -> None:
        self.runtimes = {
            "SZLHOLDINGS/a11oy": {"stage": "PAUSED", "hardware": None},
            "SZLHOLDINGS/governed-agent-bench": {
                "stage": "RUNNING",
                "hardware": "cpu-basic",
            },
        }
        self.restart_calls: list[dict[str, object]] = []
        self.pause_calls: list[dict[str, object]] = []
        self.quota_failures = quota_failures

    def get_space_runtime(self, *, repo_id: str):
        runtime = self.runtimes[repo_id]
        return SimpleNamespace(
            stage=SimpleNamespace(value=runtime["stage"]),
            hardware=runtime["hardware"],
        )

    def restart_space(self, **kwargs):
        self.restart_calls.append(kwargs)
        if len(self.restart_calls) <= self.quota_failures:
            raise QuotaError()
        return SimpleNamespace(
            runtime=SimpleNamespace(stage=SimpleNamespace(value="BUILDING"))
        )

    def pause_space(self, **kwargs):
        self.pause_calls.append(kwargs)
        donor = self.runtimes[str(kwargs["repo_id"])]
        donor["stage"] = "PAUSED"
        donor["hardware"] = None


class ResumeHfSpaceTests(unittest.TestCase):
    def test_paused_space_is_restarted_without_factory_reboot(self) -> None:
        api = RecordingApi("PAUSED")
        report: dict[str, object] = {}

        MODULE.resume_if_paused(api, repo_id="SZLHOLDINGS/a11oy", report=report)

        self.assertEqual(api.repo_id, "SZLHOLDINGS/a11oy")
        self.assertEqual(
            api.restart_calls,
            [{"repo_id": "SZLHOLDINGS/a11oy", "factory_reboot": False}],
        )
        self.assertEqual(report["observed_stage"], "PAUSED")
        self.assertEqual(report["action"], "RESTART_REQUESTED")
        self.assertEqual(report["response_stage"], "BUILDING")

    def test_active_space_is_not_restarted(self) -> None:
        for stage in MODULE.ACTIVE_STAGES:
            with self.subTest(stage=stage):
                api = RecordingApi(stage)
                report: dict[str, object] = {}
                MODULE.resume_if_paused(
                    api,
                    repo_id="SZLHOLDINGS/a11oy",
                    report=report,
                )
                self.assertEqual(api.restart_calls, [])
                self.assertEqual(report["action"], "ALREADY_ACTIVE")

    def test_unexpected_runtime_stage_fails_closed(self) -> None:
        api = RecordingApi("RUNTIME_ERROR")
        report: dict[str, object] = {}

        with self.assertRaisesRegex(RuntimeError, "neither paused nor active"):
            MODULE.resume_if_paused(
                api,
                repo_id="SZLHOLDINGS/a11oy",
                report=report,
            )

        self.assertEqual(report["observed_stage"], "RUNTIME_ERROR")
        self.assertEqual(api.restart_calls, [])

    def test_exact_quota_failure_releases_allowlisted_capacity_then_restarts(self) -> None:
        api = CapacityApi()
        report: dict[str, object] = {}

        MODULE.resume_if_paused(
            api,
            repo_id="SZLHOLDINGS/a11oy",
            capacity_donor="SZLHOLDINGS/governed-agent-bench",
            report=report,
            sleep=lambda _: None,
        )

        self.assertEqual(
            api.pause_calls,
            [{"repo_id": "SZLHOLDINGS/governed-agent-bench"}],
        )
        self.assertEqual(len(api.restart_calls), 2)
        self.assertEqual(report["initial_restart_blocker"], "CPU_BASIC_QUOTA")
        self.assertEqual(
            report["action"],
            "RESTART_REQUESTED_AFTER_CAPACITY_RELEASE",
        )
        donor = report["capacity_donor"]
        self.assertEqual(donor["observed_stage"], "RUNNING")
        self.assertEqual(donor["observed_hardware"], "cpu-basic")
        self.assertEqual(donor["final_stage"], "PAUSED")
        self.assertIsNone(donor["final_hardware"])
        self.assertEqual(donor["canonical_restart_attempts"], 1)

    def test_quota_release_propagation_is_retried_within_a_bound(self) -> None:
        api = CapacityApi(quota_failures=3)
        report: dict[str, object] = {}
        sleeps: list[float] = []

        MODULE.resume_if_paused(
            api,
            repo_id="SZLHOLDINGS/a11oy",
            capacity_donor="SZLHOLDINGS/governed-agent-bench",
            report=report,
            sleep=sleeps.append,
            capacity_restart_attempts=4,
            capacity_restart_delay=5.0,
        )

        self.assertEqual(len(api.restart_calls), 4)
        self.assertEqual(sleeps, [5.0, 5.0])
        self.assertEqual(
            report["capacity_donor"]["canonical_restart_attempts"],
            3,
        )
        self.assertEqual(
            report["action"],
            "RESTART_REQUESTED_AFTER_CAPACITY_RELEASE",
        )

    def test_non_quota_restart_failure_never_pauses_capacity_donor(self) -> None:
        api = CapacityApi()

        def denied_restart(**_kwargs):
            raise RuntimeError("403 Forbidden: unrelated policy")

        api.restart_space = denied_restart
        with self.assertRaisesRegex(RuntimeError, "unrelated policy"):
            MODULE.resume_if_paused(
                api,
                repo_id="SZLHOLDINGS/a11oy",
                capacity_donor="SZLHOLDINGS/governed-agent-bench",
                report={},
                sleep=lambda _: None,
            )
        self.assertEqual(api.pause_calls, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
