from __future__ import annotations

import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
DRIFT_WORKFLOW = ROOT / ".github" / "workflows" / "hf-module-drift.yml"
SYNC_WORKFLOW = ROOT / ".github" / "workflows" / "hf-sync.yml"
LIFECYCLE_VALIDATOR = ROOT / "scripts" / "validate_hf_parity_lifecycle.py"
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
        self.assertIn("name: Protected base matches immutable HF repository", self.pr_job)
        self.assertIn("if: github.event_name == 'pull_request'", self.pr_job)
        self.assertIn("github.event.pull_request.base.sha", self.pr_job)
        self.assertNotIn("github.event.pull_request.head.sha", self.pr_job)
        self.assertIn("verify_hf_repository_parity.py", self.pr_job)
        self.assertIn('--github-ref "$SOURCE_REF"', self.pr_job)
        self.assertIn("hf-current-base-parity.out.json", self.pr_job)
        self.assertNotIn("source-probe-path", self.pr_job)

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
        self.assertIn("github-ref: ${{ github.sha }}", self.live_job)

    def test_immutable_repository_byte_parity_runs_only_after_publication(self) -> None:
        self.assertIn("name: Immutable HF repository byte parity", self.repository_job)
        self.assertIn("if: github.event_name != 'pull_request'", self.repository_job)
        self.assertIn("path: source", self.repository_job)
        self.assertIn("ref: ${{ github.sha }}", self.repository_job)
        self.assertIn("SOURCE_REF: ${{ github.sha }}", self.repository_job)
        self.assertIn(
            "source/.github/scripts/verify_hf_repository_parity.py",
            self.repository_job,
        )
        self.assertIn('--github-ref "$SOURCE_REF"', self.repository_job)
        self.assertIn(
            "hf-post-deployment-repository-parity.out.json",
            self.repository_job,
        )
        self.assertIn("name: hf-post-deployment-repository-parity", self.repository_job)
        self.assertIn(
            "ref: 0816263f1e83734658d6e5a8a7cd3834f36a2054",
            self.repository_job,
        )
        self.assertNotIn("github.event.pull_request.", self.repository_job)
        self.assertNotIn("BASE_REF", self.repository_job)
        self.assertNotIn("--base-ref", self.repository_job)
        self.assertNotIn("select_hf_candidate_admission.py", self.repository_job)
        self.assertNotIn("hf-module-drift-allow", self.repository_job)

    def test_runtime_reachability_and_repository_bytes_are_separate_proofs(self) -> None:
        self.assertIn(
            "Pull-request and deployed-runtime checks are deliberately separated.",
            self.drift,
        )
        self.assertIn("An unmerged candidate", self.drift)
        self.assertIn("only then dispatches this workflow", self.drift)
        self.assertIn("source-probe-path: /api/build-info", self.live_job)
        self.assertNotIn("source-probe-path", self.repository_job)

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

    def test_successful_deploy_dispatches_strict_live_and_repository_parity(self) -> None:
        self.assertIn("actions: write", self.sync)
        enforce = self.sync.index("Enforce exact live state")
        dispatch = self.sync.index("Trigger strict post-deployment GitHub/HF parity")
        self.assertLess(enforce, dispatch)
        self.assertIn(
            'gh workflow run hf-module-drift.yml --repo "$GITHUB_REPOSITORY" --ref main',
            self.sync,
        )
        self.assertIn("if: github.event_name != 'pull_request'", self.repository_job)

    def test_every_main_push_enters_deployment_before_strict_post_deploy_parity(
        self,
    ) -> None:
        trigger, _ = self.sync.split("\npermissions:", 1)
        self.assertIn("push:\n    branches: [main]", trigger)
        self.assertNotIn("\n    paths:", trigger)
        self.assertNotIn("\n    paths-ignore:", trigger)
        self.assertIn("COPY .well-known/security.txt", self.dockerfile)
        self.assertIn("hf-sync without a path filter", self.drift)
        drift_trigger, _ = self.drift.split("\npermissions:", 1)
        self.assertNotIn("\n  push:", drift_trigger)

    def test_no_custom_credential_enters_the_pr_drift_guard(self) -> None:
        self.assertIn("permissions:\n  contents: read", self.drift)
        self.assertNotIn("secrets.", self.drift)
        self.assertNotIn("GH_TOKEN", self.drift)
        self.assertNotIn("HF_TOKEN", self.drift)

    def test_dedicated_lifecycle_validator_is_committed(self) -> None:
        self.assertTrue(LIFECYCLE_VALIDATOR.is_file())
        source = LIFECYCLE_VALIDATOR.read_text(encoding="utf-8")
        self.assertIn("post-deployment-repository-parity/v1", source)
        self.assertIn("pre-merge candidate selector must not execute", source)
        self.assertIn("post-deployment parity must not consume pull-request event fields", source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
