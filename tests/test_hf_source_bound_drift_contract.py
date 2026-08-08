from __future__ import annotations

import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
DRIFT_WORKFLOW = ROOT / ".github" / "workflows" / "hf-module-drift.yml"
SYNC_WORKFLOW = ROOT / ".github" / "workflows" / "hf-sync.yml"
DOCKERFILE = ROOT / "Dockerfile"
LEGACY_LOCK = ROOT / ".github" / "hf-deployment-lock.json"
LEGACY_RELOCK_WORKFLOW = ROOT / ".github" / "workflows" / "hf-relock-evidence.yml"
LEGACY_RUNTIME_VERIFIER = ROOT / "scripts" / "check_hf_runtime_revision.py"
LEGACY_RUNTIME_VERIFIER_TEST = ROOT / "scripts" / "test_check_hf_runtime_revision.py"


class RepositoryBoundDriftWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.drift = DRIFT_WORKFLOW.read_text(encoding="utf-8")
        cls.sync = SYNC_WORKFLOW.read_text(encoding="utf-8")
        cls.dockerfile = DOCKERFILE.read_text(encoding="utf-8")

    def test_pull_requests_use_the_exact_repository_parity_controller(self) -> None:
        self.assertIn(
            "uses: szl-holdings/.github/.github/workflows/reusable-hf-module-drift-check.yml@96573c9049c0c705072cf51024d5ef12ccbee98c",
            self.drift,
        )
        self.assertIn("mode: direct", self.drift)
        self.assertIn("github.event.pull_request.base.sha", self.drift)
        self.assertNotIn("github.event.pull_request.head.sha", self.drift)
        self.assertNotIn("source-probe-path:", self.drift)

    def test_pr_uses_exact_base_and_manual_schedule_use_exact_main(self) -> None:
        github_ref = (
            "github-ref: ${{ github.event_name == 'pull_request' && "
            "github.event.pull_request.base.sha || github.sha }}"
        )
        self.assertIn(github_ref, self.drift)
        self.assertNotIn("\n  push:", self.drift)
        self.assertIn("hf-ref: main", self.drift)
        self.assertIn("workflow_dispatch:", self.drift)
        self.assertIn("schedule:", self.drift)

    def test_repository_proof_does_not_overclaim_runtime_readiness(self) -> None:
        self.assertIn("runtime is paused", self.drift)
        self.assertIn("Runtime readiness is a separate fail-closed responsibility", self.drift)
        self.assertIn("hf-sync", self.drift)
        self.assertNotIn("source-bound-baseline", self.drift)

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

    def test_successful_deploy_dispatches_strict_repository_parity(self) -> None:
        self.assertIn("actions: write", self.sync)
        enforce = self.sync.index("Enforce exact live state")
        dispatch = self.sync.index("Trigger strict post-deployment GitHub/HF parity")
        self.assertLess(enforce, dispatch)
        self.assertIn(
            'gh workflow run hf-module-drift.yml --repo "$GITHUB_REPOSITORY" --ref main',
            self.sync,
        )

    def test_every_main_push_enters_deployment_before_strict_parity(self) -> None:
        trigger, _ = self.sync.split("\npermissions:", 1)
        self.assertIn("push:\n    branches: [main]", trigger)
        self.assertNotIn("\n    paths:", trigger)
        self.assertNotIn("\n    paths-ignore:", trigger)
        self.assertIn("COPY .well-known/security.txt", self.dockerfile)
        self.assertIn("hf-sync without a path filter", self.drift)

    def test_no_custom_credential_enters_the_drift_guard(self) -> None:
        self.assertIn("permissions:\n  contents: read", self.drift)
        self.assertNotIn("secrets.", self.drift)
        self.assertNotIn("GH_TOKEN", self.drift)
        self.assertNotIn("HF_TOKEN", self.drift)


if __name__ == "__main__":
    unittest.main(verbosity=2)
