#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""The served console DevPlatform chunk labels its seeded figures and makes no
unpublished-SDK or certification claim.

console/assets/DevPlatform-*.js is a vendored Vite build of
szl-holdings/platform artifacts/a11oy/src/pages/DevPlatform.tsx; the page source
is not in this repository. The chunk is served as a static asset, so whatever it
says is published. Its workspace spend, API-key usage, fine-tune cost and
evaluation figures are seeded demonstration values, not measurements, and none
of its SDK package names is published. stdlib only.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "console" / "assets"

REQUIRED = (
    # Page-level label, verbatim from platform main's DevPlatform.tsx.
    "status:`DEMO`",
    "Product exploration surface. Registries and evaluation values below are seeded "
    "demonstrations unless a linked receipt explicitly marks them MEASURED.",
    "children:`Seeded demonstration · not live evidence`",
    "label:`SEEDED EVALS`",
    "% demo pass",
    # Seeded commercial figures carry SAMPLE where they are shown.
    "children:`Workspaces — SAMPLE data: not customers, not spend`",
    "`Spend (SAMPLE)`",
    "children:`API Keys — SAMPLE data: not issued keys, not usage`",
    "` calls (SAMPLE)`",
    "children:`Data Residency — SAMPLE data: no regions admitted`",
    "`Accuracy (SAMPLE)`,`Cost (SAMPLE)`",
    "`Calls (SAMPLE)`",
    "children:`Recent Traces — SAMPLE data`",
    "`Unified Billing`}),` — ROADMAP: no billing system is live`",
    # Certifications are targets, verbatim from platform main.
    "`SOC 2 target — not attested`",
    "`IL5 target — not certified`",
    "`FedRAMP target — not authorized`",
    "metric:`No production proof set`",
    # No SDK is published.
    "ROADMAP: no a11oy client SDK is published.",
)

FORBIDDEN = (
    "status:`LIVE`",
    "the complete developer platform",
    "label:`EVAL TESTS`",
    "`SOC 2 Type II`",
    "`ISO 27001`,",
    "`FedRAMP High`,",
    "`IL5 certified`",
    "`ITAR compliant`",
    "IL5-certified",
    "court-admissible.`",
    "4.2M proofs verified",
    "5 regions active",
    "metric:`100% verified`",
    "single invoice regardless of underlying cloud provider",
    "Anthropic exceeded",
)

INSTALL_COMMAND = re.compile(
    r"install:`(?:pip install|npm install|cargo add|gem install|composer require|"
    r"dotnet add|go get|maven:|gradle:|SPM:)")


def _chunk() -> str:
    chunks = sorted(ASSETS.glob("DevPlatform-*.js"))
    if len(chunks) != 1:
        raise AssertionError(f"expected exactly one DevPlatform chunk, found {chunks}")
    return chunks[0].read_text(encoding="utf-8")


class DevPlatformChunkHonesty(unittest.TestCase):
    def setUp(self):
        self.text = _chunk()

    def test_required_labels_present(self):
        missing = [s for s in REQUIRED if s not in self.text]
        self.assertEqual(missing, [])

    def test_unlabeled_claims_absent(self):
        present = [s for s in FORBIDDEN if s in self.text]
        self.assertEqual(present, [])

    def test_no_install_command_for_an_unpublished_sdk(self):
        self.assertEqual(INSTALL_COMMAND.findall(self.text), [])
        self.assertEqual(self.text.count("install:`not published`"), 10)
        self.assertNotIn("repo:`github.com/szl-holdings/a11oy-sdk", self.text)


if __name__ == "__main__":
    unittest.main()
