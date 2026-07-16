"""Dependency-light checks for the verified public preprint surfaces."""

from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PublicationSurfaceLinkTests(unittest.TestCase):
    def test_readme_exposes_both_verified_preprint_dois(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("https://doi.org/10.5281/zenodo.21332317", readme)
        self.assertIn("https://doi.org/10.5281/zenodo.21332338", readme)

    def test_company_surface_types_preprints_and_links_release_packages(self) -> None:
        company = (ROOT / "pages" / "company.html").read_text(encoding="utf-8")
        required = (
            "https://doi.org/10.5281/zenodo.21332317",
            "https://doi.org/10.5281/zenodo.21332338",
            "evidence-typed-formula-governance/releases/tag/v0.1.0",
            "fail-closed-governed-ai-services/releases/tag/v0.1.0",
            "From Build Success to Admissible Proof",
            "Readiness Is Not Evidence",
        )
        for marker in required:
            with self.subTest(marker=marker):
                self.assertIn(marker, company)
        self.assertGreaterEqual(company.count("NOT PEER REVIEWED"), 2)
        self.assertGreaterEqual(company.lower().count("not peer reviewed"), 4)


if __name__ == "__main__":
    unittest.main()
