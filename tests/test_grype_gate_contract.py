from pathlib import Path
import unittest


WORKFLOW = Path(".github/workflows/trivy.yml")


def _grype_gate_block() -> str:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    start = workflow.index("- name: Scan with Grype (fail build on HIGH/CRITICAL)")
    end = workflow.index("- name: Upload Grype SARIF", start)
    return workflow[start:end]


class GrypeGateContractTests(unittest.TestCase):
    def test_grype_gate_cannot_swallow_scanner_failure(self) -> None:
        block = _grype_gate_block()
        self.assertNotIn("continue-on-error", block)

    def test_grype_gate_fails_on_high_and_critical_findings(self) -> None:
        block = _grype_gate_block()
        self.assertIn("fail-build: true", block)
        self.assertIn("severity-cutoff: high", block)

    def test_grype_action_is_pinned_to_an_immutable_revision(self) -> None:
        block = _grype_gate_block()
        action_line = next(
            line for line in block.splitlines() if "uses: anchore/scan-action@" in line
        )
        revision = action_line.split("@", 1)[1].split()[0]
        self.assertEqual(len(revision), 40)
        self.assertTrue(all(character in "0123456789abcdef" for character in revision))


if __name__ == "__main__":
    unittest.main()
