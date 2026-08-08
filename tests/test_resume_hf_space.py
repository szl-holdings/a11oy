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


if __name__ == "__main__":
    unittest.main(verbosity=2)
