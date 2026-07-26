import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "action-contract-promotion-guard.yml"


class ActionContractPromotionGuardTests(unittest.TestCase):
    def test_uses_protected_validator_and_untrusted_candidate_data(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("pull_request_target:", text)
        self.assertIn("permissions:\n  contents: read", text)
        self.assertIn("ref: ${{ github.event.pull_request.base.sha }}", text)
        self.assertIn("persist-credentials: false", text)
        self.assertNotIn("Checkout candidate as untrusted data", text)
        self.assertIn("actions/github-script@", text)
        self.assertIn("ref: process.env.CANDIDATE_SHA", text)
        self.assertIn('candidate.type !== "file"', text)
        self.assertIn('candidate.encoding !== "base64"', text)
        self.assertIn("candidate manifest exceeds the 1 MiB validation limit", text)
        self.assertIn('"protected-base/docs/action-contract-manifest.json"', text)
        self.assertIn("python3 scripts/validate_action_contract_manifest.py", text)

    def test_live_promotion_rejects_candidate_runtime_changes(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("github.paginate(", text)
        self.assertIn("github.rest.pulls.listFiles", text)
        self.assertIn('manifest.claimStatus === "verified-runtime"', text)
        self.assertIn('execution.runtimeStatus === "live"', text)
        self.assertIn(
            'name !== "docs/action-contract-manifest.json"',
            text,
        )
        self.assertIn("live runtime promotion must be manifest-only", text)

    def test_never_executes_candidate_code(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")

        run_block = text.split("run: |", maxsplit=1)[1]
        self.assertNotIn("candidate/scripts/", run_block)
        self.assertNotIn("cd candidate", run_block)
        self.assertNotIn("python3 candidate/", run_block)
        self.assertNotIn(
            "actions/checkout@",
            text.split("- name: Set up Python", maxsplit=1)[1],
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
