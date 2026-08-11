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
        cls.pr_job, remainder = cls.drift.split("\n  hf-runtime-live:", 1)
        cls.live_job, cls.repository_job = remainder.split(
            "\n  hf-repository-parity:", 1
        )

    def test_pull_requests_prove_the_exact_protected_base_without_live_queue_dependency(
        self,
    ) -> None:
        self.assertIn("name: Source in sync with the live HF Space", self.pr_job)
        self.assertIn("if: github.event_name == 'pull_request'", self.pr_job)
        self.assertIn("github.event.pull_request.base.sha", self.pr_job)
        self.assertIn("verify_hf_repository_parity.py", self.pr_job)
        self.assertIn("hf-current-base-parity.out.json", self.pr_job)
        self.assertNotIn("source-probe-path", self.pr_job)
        self.assertNotIn("/api/build-info", self.pr_job)

    def test_scheduled_manual_and_post_deploy_checks_keep_the_strict_live_controller(
        self,
    ) -> None:
        self.assertIn("if: github.event_name != 'pull_request'", self.live_job)
        self.assertIn(
            "uses: szl-holdings/.github/.github/workflows/reusable-hf-module-drift-check.yml@0816263f1e83734658d6e5a8a7cd3834f36a2054",
            self.live_job,
        )
        self.assertIn("mode: source-bound-baseline", self.live_job)
        self.assertIn("source-probe-path: /api/build-info", self.live_job)
        self.assertIn("trusted-base-ref: ${{ github.sha }}", self.live_job)
        self.assertIn("candidate-ref: ${{ github.sha }}", self.live_job)

    def test_pull_requests_also_prove_candidate_managed_byte_parity(self) -> None:
        self.assertIn("Immutable HF repository byte parity", self.repository_job)
        self.assertIn("if: github.event_name == 'pull_request'", self.repository_job)
        self.assertIn("github.event.pull_request.head.sha", self.repository_job)
        self.assertIn("verify_hf_repository_parity.py", self.repository_job)
        self.assertIn(
            "ref: 0816263f1e83734658d6e5a8a7cd3834f36a2054",
            self.repository_job,
        )
        self.assertNotIn("mode: direct", self.repository_job)
        self.assertNotIn("hf-module-drift-allow", self.repository_job)

    def test_runtime_reachability_is_not_overclaimed_by_pr_repository_proof(
        self,
    ) -> None:
        self.assertIn("separate lifecycle proofs", self.drift)
        self.assertIn("does not depend on an", self.drift)
        self.assertIn("live request queue", self.drift)
        self.assertIn("stays red at the release/runtime boundary", self.drift)
        self.assertIn("hf-sync deploys, restarts, relocks", self.drift)

    def test_fixed_revision_lock_and_legacy_relock_lane_remain_removed(self) -> None:
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

    def test_successful_deploy_dispatches_strict_live_parity(self) -> None:
        self.assertIn("actions: write", self.sync)
        enforce = self.sync.index("Enforce exact live state")
        dispatch = self.sync.index("Trigger strict post-deployment GitHub/HF parity")
        self.assertLess(enforce, dispatch)
        self.assertIn(
            'gh workflow run hf-module-drift.yml --repo "$GITHUB_REPOSITORY" --ref main',
            self.sync,
        )

    def test_every_main_push_enters_deployment_before_strict_live_parity(self) -> None:
        trigger, _ = self.sync.split("\npermissions:", 1)
        self.assertIn("push:\n    branches: [main]", trigger)
        self.assertNotIn("\n    paths:", trigger)
        self.assertNotIn("\n    paths-ignore:", trigger)
        self.assertIn("COPY .well-known/security.txt", self.dockerfile)
        self.assertIn("hf-sync without a path filter", self.drift)

    def test_no_custom_credential_enters_the_pr_drift_guard(self) -> None:
        self.assertIn("permissions:\n  contents: read", self.drift)
        self.assertNotIn("secrets.", self.drift)
        self.assertNotIn("GH_TOKEN", self.drift)
        self.assertNotIn("HF_TOKEN", self.drift)


if __name__ == "__main__":
    unittest.main(verbosity=2)
