#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Focused contracts for the shared operator control dock."""

import hashlib
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
WIDGET_PATH = ROOT / "static-vendor" / "a11oy-operator-widget.js"
ALLOWLIST_PATH = ROOT / ".github" / "shared-file-drift-allow.txt"
EXPECTED_WIDGET_BYTES = 37_373
EXPECTED_WIDGET_SHA256 = "11ea2344c63e11f19d454df14d3c081b17f3b37af1995a83e70ca40bf270f465"


class OperatorControlDockContractTests(unittest.TestCase):
    def test_payload_is_content_addressed(self) -> None:
        payload = WIDGET_PATH.read_bytes()
        self.assertEqual(len(payload), EXPECTED_WIDGET_BYTES)
        self.assertEqual(hashlib.sha256(payload).hexdigest(), EXPECTED_WIDGET_SHA256)

    def test_safe_area_and_dynamic_dock_contracts_are_present(self) -> None:
        source = WIDGET_PATH.read_text(encoding="utf-8")
        for token in (
            "max-height:calc(100vh - 120px - env(safe-area-inset-bottom,0px))",
            "max-height:calc(100vh - 168px - env(safe-area-inset-bottom,0px))",
            "new window.MutationObserver(syncDockPosition)",
            "{ childList: true, subtree: true }",
            'data-dock-has-investor="true"',
            "max-height:calc(100vh - 228px - env(safe-area-inset-bottom,0px))",
            "document.querySelector('[data-szl-dock-control=\"investor\"]')",
            '.aow-root[data-dock-has-investor="true"] .aow-toasts{bottom:calc(env(safe-area-inset-bottom,0px) + 200px);}',
            '@media (max-height:480px)',
            'right:calc(env(safe-area-inset-right,0px) + 176px)',
            'max-width:calc(100vw - 192px)',
            '.aow-root[data-open="true"] .aow-toasts{display:none;}',
            "pushMsg('op'",
        ):
            self.assertIn(token, source)

    def test_immutable_widget_urls_use_the_payload_hash(self) -> None:
        source = (ROOT / "serve.py").read_text(encoding="utf-8")
        versioned_url = (
            "/vendor/a11oy-operator-widget.js?v=" + EXPECTED_WIDGET_SHA256
        )
        self.assertGreaterEqual(source.count(f'src="{versioned_url}"'), 2)
        web_shell = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        self.assertIn(f'src="{versioned_url}"', web_shell)

    def test_shared_widget_is_not_allowlisted(self) -> None:
        paths = {
            line.split("#", 1)[0].strip()
            for line in ALLOWLIST_PATH.read_text(encoding="utf-8").splitlines()
            if line.split("#", 1)[0].strip()
        }
        self.assertNotIn("static-vendor/a11oy-operator-widget.js", paths)


if __name__ == "__main__":
    unittest.main(verbosity=2)
