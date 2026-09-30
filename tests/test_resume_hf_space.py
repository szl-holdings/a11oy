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
        self.runtime_reads: list[str] = []
        self.pause_calls: list[dict[str, object]] = []

    def get_space_runtime(self, *, repo_id: str):
        self.runtime_reads.append(repo_id)
        self.repo_id = repo_id
        return SimpleNamespace(stage=SimpleNamespace(value=self.stage))

    def restart_space(self, **kwargs):
        self.restart_calls.append(kwargs)
        return SimpleNamespace(
            runtime=SimpleNamespace(
                stage=SimpleNamespace(value=self.response_stage),
            )
        )

    def pause_space(self, **kwargs):
        self.pause_calls.append(kwargs)
        raise AssertionError("resume must never pause a capacity donor")


class QuotaError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("403 Forbidden: cpu-basic quota limit")
        self.response = SimpleNamespace(status_code=403)


class QuotaApi(RecordingApi):
    def __init__(self) -> None:
        super().__init__("PAUSED")

    def restart_space(self, **kwargs):
        self.restart_calls.append(kwargs)
        raise QuotaError()


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
        self.assertEqual(api.pause_calls, [])

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
                self.assertEqual(api.pause_calls, [])

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

    def test_quota_failure_propagates_without_donor_pause_or_retry(self) -> None:
        api = QuotaApi()
        report: dict[str, object] = {}
        with self.assertRaises(QuotaError):
            MODULE.resume_if_paused(api, repo_id="SZLHOLDINGS/a11oy", report=report)
        self.assertEqual(api.runtime_reads, ["SZLHOLDINGS/a11oy"])
        self.assertEqual(api.restart_calls,
                         [{"repo_id": "SZLHOLDINGS/a11oy", "factory_reboot": False}])
        self.assertEqual(api.pause_calls, [])
        self.assertNotIn("capacity_donor", report)

    def test_non_quota_restart_failure_never_pauses_another_space(self) -> None:
        api = RecordingApi("PAUSED")

        def denied_restart(**kwargs):
            api.restart_calls.append(kwargs)
            raise RuntimeError("403 Forbidden: unrelated policy")

        api.restart_space = denied_restart
        with self.assertRaisesRegex(RuntimeError, "unrelated policy"):
            MODULE.resume_if_paused(
                api,
                repo_id="SZLHOLDINGS/a11oy",
                report={},
            )
        self.assertEqual(api.runtime_reads, ["SZLHOLDINGS/a11oy"])
        self.assertEqual(len(api.restart_calls), 1)
        self.assertEqual(api.pause_calls, [])

    def test_noncanonical_target_is_rejected_before_any_provider_call(self) -> None:
        api = RecordingApi("PAUSED")
        with self.assertRaises(RuntimeError):
            MODULE.resume_if_paused(api, repo_id="SZLHOLDINGS/other", report={})
        self.assertEqual(api.runtime_reads, [])
        self.assertEqual(api.restart_calls, [])
        self.assertEqual(api.pause_calls, [])

    def test_removed_donor_option_is_rejected_before_provider_calls(self) -> None:
        api = RecordingApi("PAUSED")
        with self.assertRaises(TypeError):
            MODULE.resume_if_paused(api, repo_id="SZLHOLDINGS/a11oy", report={},
                                    capacity_donor="SZLHOLDINGS/other")
        self.assertEqual(api.runtime_reads, [])
        self.assertEqual(api.restart_calls, [])
        self.assertEqual(api.pause_calls, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
