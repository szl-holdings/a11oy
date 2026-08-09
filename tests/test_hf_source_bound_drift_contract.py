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
        cls.live_job, cls.repository_job = cls.drift.split(
            "\n  hf-repository-parity:", 1
        )

    def test_pull_requests_keep_the_exact_live_source_bound_controller(self) -> None:
        self.assertIn(
            "uses: szl-holdings/.github/.github/workflows/reusable-hf-module-drift-check.yml@96573c9049c0c705072cf51024d5ef12ccbee98c",
            self.drift,
        )
        self.assertIn("mode: source-bound-baseline", self.live_job)
        self.assertIn("source-probe-path: /api/build-info", self.live_job)
        self.assertIn("dockerfile-path: Dockerfile", self.live_job)
        self.assertIn("github.event.pull_request.head.sha", self.live_job)
        self.assertNotIn("mode: direct", self.live_job)

    def test_pull_requests_add_exact_repository_parity_without_waiving_live_gate(
        self,
    ) -> None:
        self.assertIn("hf-repository-parity:", self.drift)
        self.assertIn("Immutable HF repository byte parity", self.repository_job)
        self.assertIn("verify_hf_repository_parity.py", self.repository_job)
        self.assertIn("github.event.pull_request.base.sha", self.repository_job)
        self.assertIn("github.event.pull_request.head.sha", self.repository_job)
        self.assertIn(
            "ref: 96573c9049c0c705072cf51024d5ef12ccbee98c", self.repository_job
        )
        self.assertNotIn("mode: direct", self.repository_job)
        self.assertNotIn("hf-module-drift-allow", self.repository_job)

    def test_pr_uses_exact_base_and_manual_schedule_use_exact_main(self) -> None:
        source_ref = (
            "SOURCE_REF: ${{ github.event_name == 'pull_request' && "
            "github.event.pull_request.base.sha || github.sha }}"
        )
        self.assertIn(source_ref, self.repository_job)
        self.assertNotIn("\n  push:", self.drift)
        self.assertIn("hf-ref: main", self.live_job)
        self.assertIn("workflow_dispatch:", self.drift)
        self.assertIn("schedule:", self.drift)

    def test_repository_proof_does_not_overclaim_runtime_readiness(self) -> None:
        self.assertIn("A paused or unmeasured runtime stays red", self.drift)
        self.assertIn("source-identity proof", self.drift)
        self.assertIn("never waives the live gate", self.drift)
        self.assertIn("hf-sync", self.drift)

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

    def test_sync_resumes_only_an_explicitly_paused_space_before_deploy(
        self,
    ) -> None:
        self.assertIn("resume-paused-space:", self.sync)
        self.assertIn(".github/scripts/resume_hf_space.py", self.sync)
        self.assertIn(
            "CAPACITY_DONOR_SPACE: SZLHOLDINGS/holographic",
            self.sync,
        )
        self.assertIn('--capacity-donor "$CAPACITY_DONOR_SPACE"', self.sync)
        self.assertIn("Checkout exact protected source", self.sync)
        self.assertNotIn("python - <<'PY'", self.sync)
        deploy = self.sync.split("\n  deploy:", 1)[1].split("\n  readiness-verdict:", 1)[0]
        self.assertNotIn("needs:", deploy)
        self.assertNotIn("request_space_hardware", self.sync)
        self.assertNotIn("add_space_secret", self.sync)
        self.assertNotIn("delete_space_secret", self.sync)

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
