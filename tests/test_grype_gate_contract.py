from datetime import date
from pathlib import Path
import re
import unittest


WORKFLOW = Path(".github/workflows/trivy.yml")
IGNORE_CONFIG = Path(".github/grype-gate-ignore.yaml")
IGNORE_REVIEW_BY = re.compile(r"^#\s*review-by:\s*(\d{4}-\d{2}-\d{2})\s*$", re.MULTILINE)


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

    def test_grype_gate_uses_supported_db_and_sarif_inputs(self) -> None:
        block = _grype_gate_block()
        self.assertNotIn("update-db:", block)
        self.assertIn("cache-db: true", block)
        self.assertIn("output-file: grype-results.sarif", block)
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("sarif_file: grype-results.sarif", workflow)

    def test_grype_action_is_pinned_to_an_immutable_revision(self) -> None:
        block = _grype_gate_block()
        action_line = next(
            line for line in block.splitlines() if "uses: anchore/scan-action@" in line
        )
        revision = action_line.split("@", 1)[1].split()[0]
        self.assertEqual(len(revision), 40)
        self.assertTrue(all(character in "0123456789abcdef" for character in revision))


class GrypeGateAllowlistContractTests(unittest.TestCase):
    """The gate allowlist must stay evidence-linked, package-scoped, and self-expiring."""

    def test_gate_loads_the_allowlist_config(self) -> None:
        block = _grype_gate_block()
        self.assertIn("config: .github/grype-gate-ignore.yaml", block)

    def _ignore_body(self) -> str:
        raw = IGNORE_CONFIG.read_text(encoding="utf-8")
        self.assertIn("\nignore:", raw, "allowlist config missing an ignore section")
        return raw.split("\nignore:", 1)[1]

    def _entries(self) -> list:
        body_lines = [
            line
            for line in self._ignore_body().splitlines()
            if not line.lstrip().startswith("#")
        ]
        body = "\n".join(body_lines)
        return [
            chunk for chunk in body.split("  - vulnerability:") if chunk.strip()
        ]

    def test_allowlist_entries_are_package_scoped_with_reasons(self) -> None:
        entries = self._entries()
        self.assertGreaterEqual(len(entries), 1, "allowlist unexpectedly empty")
        for entry in entries:
            self.assertRegex(
                entry,
                r"(?m)^      name:\s*\S+",
                "entry is not package-scoped: " + entry[:80],
            )
            self.assertRegex(
                entry,
                r"(?m)^    reason:\s*\S+",
                "entry lacks an evidence reason: " + entry[:80],
            )

    def test_allowlist_review_window_has_not_elapsed(self) -> None:
        match = IGNORE_REVIEW_BY.search(IGNORE_CONFIG.read_text(encoding="utf-8"))
        self.assertIsNotNone(
            match, "allowlist config missing a '# review-by: YYYY-MM-DD' window"
        )
        review_by = date.fromisoformat(match.group(1))
        self.assertGreaterEqual(
            review_by,
            date.today(),
            "allowlist review window elapsed: re-review or remove the ignores",
        )


if __name__ == "__main__":
    unittest.main()
