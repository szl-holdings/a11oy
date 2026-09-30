"""Contract tests for the governed-admission documentation flow."""
from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "GOVERNED_ADMISSION_FLOW.md"


class GovernedAdmissionFlowDocumentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = DOC.read_text(encoding="utf-8")
        match = re.search(r"```mermaid\n(?P<body>.*?)\n```", cls.text, re.DOTALL)
        if match is None:
            raise AssertionError("the governed-admission Mermaid diagram is missing")
        cls.diagram = match.group("body")

    def test_mermaid_records_the_required_gate_order(self) -> None:
        required_edges = (
            "C[Claim plus evidence] --> L{Evidence label valid?}",
            "L -- valid --> T{Banned-token scan clean?}",
            "T -- clean --> O{Overclaim-pattern guard clean?}",
            "O -- clean --> S{Signing material and stable payload available?}",
            "S -- available --> E[Create DSSE envelope]",
            "E --> P[Publish with explicit evidence label]",
            "P --> V{Public verification passes?}",
            "V -- valid signature, digest, signer, and label --> A[ADMITTED / PUBLISHED]",
        )
        positions = []
        for edge in required_edges:
            self.assertEqual(self.diagram.count(edge), 1, edge)
            positions.append(self.diagram.index(edge))
        self.assertEqual(positions, sorted(positions))

    def test_blocked_is_a_first_class_terminal_outcome(self) -> None:
        self.assertIn("B[BLOCKED<br/>honest terminal outcome]", self.diagram)
        for edge in (
            "L -- missing or unavailable evidence --> B",
            "S -- unavailable --> B",
            "V -- verifier or required evidence unavailable --> B",
        ):
            self.assertIn(edge, self.diagram)
        self.assertIn("first-class honest outcome, not an exception", self.text)
        self.assertIn("It is never converted to", self.text)

    def test_denial_paths_are_distinct_from_unavailability(self) -> None:
        self.assertIn("D[DENIED<br/>policy terminal outcome]", self.diagram)
        self.assertIn("T -- policy violation --> D", self.diagram)
        self.assertIn("O -- unsupported claim --> D", self.diagram)
        self.assertIn("V -- contradictory or invalid evidence --> D", self.diagram)

    def test_source_map_points_to_real_current_implementations(self) -> None:
        paths = (
            "tools/page-claim-guard/check_page_claims.py",
            ".github/workflows/doctrine-grep.yml",
            "scripts/check_banned_tokens.py",
            ".github/workflows/overclaim-guard.yml",
            "szl_dsse.py",
            "szl_provenance.py",
        )
        for relative in paths:
            with self.subTest(path=relative):
                self.assertIn(f"`{relative}`", self.text)
                self.assertTrue((ROOT / relative).is_file(), relative)

    def test_document_does_not_collapse_publish_into_verification(self) -> None:
        self.assertIn("Publication is not proof", self.text)
        self.assertIn("Public verification", self.text)
        self.assertLess(
            self.diagram.index("E --> P[Publish with explicit evidence label]"),
            self.diagram.index("P --> V{Public verification passes?}"),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
