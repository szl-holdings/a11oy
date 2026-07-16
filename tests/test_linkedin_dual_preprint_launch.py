"""Focused content contract for the verified dual-preprint LinkedIn launch."""

from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
POST = ROOT / "docs" / "communications" / "LINKEDIN_DUAL_PREPRINT_LAUNCH.md"


class LinkedInDualPreprintLaunchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = POST.read_text(encoding="utf-8")

    def test_verified_publication_and_product_links_are_complete(self) -> None:
        required_links = (
            "https://doi.org/10.5281/zenodo.21332317",
            "https://doi.org/10.5281/zenodo.21332338",
            "https://github.com/szl-holdings/evidence-typed-formula-governance/releases/tag/v0.1.0",
            "https://github.com/szl-holdings/fail-closed-governed-ai-services/releases/tag/v0.1.0",
            "https://github.com/szl-holdings/a11oy",
            "https://a-11-oy.com",
            "https://a11oy.net",
        )
        for link in required_links:
            with self.subTest(link=link):
                self.assertIn(link, self.text)

    def test_honesty_boundary_and_engineering_substrates_are_explicit(self) -> None:
        required_content = (
            "two 24-page public preprints",
            "PREPRINTS; NOT PEER REVIEWED",
            "SZL Lake",
            "Lean/mathlib-linked formula governance",
            "sovereign inference gates",
            "execution receipts",
            "9,464 raw nodes",
            "training_eligible=false",
            "NOT_PROMOTED",
            "NOT_ESTABLISHED",
            "ReceiptAgent is currently a release contract, not a promoted model",
            "MEASURED",
            "BLOCKED",
            "does not claim that either domain serves the repository revision",
        )
        for marker in required_content:
            with self.subTest(marker=marker):
                self.assertIn(marker, self.text)

    def test_hashtag_set_is_high_signal_and_bounded(self) -> None:
        publish_ready = self.text.split("## Publication boundary", maxsplit=1)[0]
        hashtags = re.findall(r"(?<!\w)#[A-Za-z][A-Za-z0-9]+", publish_ready)
        self.assertGreaterEqual(len(hashtags), 8)
        self.assertLessEqual(len(hashtags), 12)
        self.assertEqual(len(hashtags), len(set(hashtags)))


if __name__ == "__main__":
    unittest.main()
