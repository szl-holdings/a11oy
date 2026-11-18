#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Ensure the proposal client reaches the served Ask view and exercise behavior."""
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class GovernedProposalClientTests(unittest.TestCase):
    def test_assets_reach_the_canonical_console(self):
        html = (ROOT / "pages/console.html").read_text(encoding="utf-8")
        serve = (ROOT / "serve.py").read_text(encoding="utf-8")
        docker = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        self.assertTrue('f = PAGES_DIR / "console.html"' in serve or 'f=PAGES_DIR/"console.html"' in serve)
        self.assertIn('app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR))', serve)
        self.assertIn("COPY console/ ./static/", docker)
        for name in ("szl-governed-proposal.js", "szl-governed-proposal.css"):
            self.assertTrue((ROOT / "console/assets" / name).is_file())
            self.assertIn(f'"/assets/{name}"', html)
        ask = html[html.index("V.ask={"):html.index("/* =============== demo", html.index("V.ask={"))]
        self.assertLess(ask.index("window.SZLGovernedProposal.mount(c)"), ask.index("await window._gdwDraftPlane(draft,'ask')"))
        self.assertIn("c.appendChild(draft)", ask)
        self.assertNotIn("_gdwDraftPlane(c,'ask')", ask)
        self.assertIn("c.isConnected", ask)

    def test_behaviors_against_actual_worker_contract(self):
        node = shutil.which("node")
        self.assertIsNotNone(node, "Node is required to verify the served proposal client.")
        result = subprocess.run(
            [node, "--test", str(ROOT / "tests/test_governed_proposal_client.mjs")],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=60,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
