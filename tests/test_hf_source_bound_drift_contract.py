from __future__ import annotations

import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
DRIFT_WORKFLOW = ROOT / ".github" / "workflows" / "hf-module-drift.yml"
SYNC_WORKFLOW = ROOT / ".github" / "workflows" / "hf-sync.yml"
LEGACY_LOCK = ROOT / ".github" / "hf-deployment-lock.json"
LEGACY_RELOCK_WORKFLOW = ROOT / ".github" / "workflows" / "hf-relock-evidence.yml"
LEGACY_RUNTIME_VERIFIER = ROOT / "scripts" / "check_hf_runtime_revision.py"
LEGACY_RUNTIME_VERIFIER_TEST = ROOT / "scripts" / "test_check_hf_runtime_revision.py"


class SourceBoundDriftWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.drift = DRIFT_WORKFLOW.read_text(encoding="utf-8")
        cls.sync = SYNC_WORKFLOW.read_text(encoding="utf-8")

    def test_pull_requests_use_the_exact_source_bound_reusable_controller(self) -> None:
        self.assertIn(
            "uses: szl-holdings/.github/.github/workflows/reusable-hf-module-drift-check.yml@96573c9049c0c705072cf51024d5ef12ccbee98c",
            self.drift,
        )
        self.assertIn("source-bound-baseline", self.drift)
        self.assertIn("source-probe-path: /api/build-info", self.drift)
        self.assertIn("dockerfile-path: Dockerfile", self.drift)
        self.assertIn("github.event.pull_request.base.sha", self.drift)
        self.assertIn("github.event.pull_request.head.sha", self.drift)

    def test_predeploy_push_is_source_bound_and_manual_schedule_are_strict(self) -> None:
        expression = (
            "mode: ${{ (github.event_name == 'pull_request' || "
            "github.event_name == 'push') && 'source-bound-baseline' || 'direct' }}"
        )
        self.assertIn(expression, self.drift)
        self.assertIn("github-ref: ${{ github.sha }}", self.drift)
        self.assertIn("hf-ref: main", self.drift)
        self.assertIn("workflow_dispatch:", self.drift)
        self.assertIn("schedule:", self.drift)

    def test_fixed_revision_lock_and_relock_lane_are_permanently_removed(self) -> None:
        for path in (
            LEGACY_LOCK,
            LEGACY_RELOCK_WORKFLOW,
            LEGACY_RUNTIME_VERIFIER,
            LEGACY_RUNTIME_VERIFIER_TEST,
        ):
            with self.subTest(path=path):
                self.assertFalse(path.exists())
        self.assertNotIn("deployment-lock", self.drift)
        self.assertNotIn("trusted-baseline", self.drift)
        self.assertNotIn("hf-module-drift-allow", self.drift)
        self.assertNotIn("hf-relock-evidence", self.sync)
        self.assertNotIn("check_hf_runtime_revision", self.sync)

    def test_successful_source_bound_deploy_dispatches_strict_parity(self) -> None:
        self.assertIn("actions: write", self.sync)
        enforce = self.sync.index("Enforce exact live state")
        dispatch = self.sync.index("Trigger strict post-deployment GitHub/HF parity")
        self.assertLess(enforce, dispatch)
        self.assertIn(
            'gh workflow run hf-module-drift.yml --repo "$GITHUB_REPOSITORY" --ref main',
            self.sync,
        )

    def test_no_custom_credential_enters_the_drift_guard(self) -> None:
        self.assertIn("permissions:\n  contents: read", self.drift)
        self.assertNotIn("secrets.", self.drift)
        self.assertNotIn("GH_TOKEN", self.drift)
        self.assertNotIn("HF_TOKEN", self.drift)


if __name__ == "__main__":
    unittest.main(verbosity=2)
