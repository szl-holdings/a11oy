"""Focused contracts for the shared operator control dock."""

import hashlib
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
WIDGET_PATH = ROOT / "static-vendor" / "a11oy-operator-widget.js"
ALLOWLIST_PATH = ROOT / ".github" / "shared-file-drift-allow.txt"
EXPECTED_WIDGET_BYTES = 36_741
EXPECTED_WIDGET_SHA256 = "94ce0ff1aadc311b396d26193a670acaacfdce9f53bc907d15c45253d5a3ea12"


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
            '.aow-root[data-dock-has-cop="true"][data-open="true"]',
        ):
            self.assertIn(token, source)

    def test_immutable_widget_urls_use_the_payload_hash(self) -> None:
        source = (ROOT / "serve.py").read_text(encoding="utf-8")
        versioned_url = (
            "/vendor/a11oy-operator-widget.js?v=" + EXPECTED_WIDGET_SHA256
        )
        self.assertGreaterEqual(source.count(f'src="{versioned_url}"'), 2)

    def test_shared_widget_is_not_allowlisted(self) -> None:
        paths = {
            line.split("#", 1)[0].strip()
            for line in ALLOWLIST_PATH.read_text(encoding="utf-8").splitlines()
            if line.split("#", 1)[0].strip()
        }
        self.assertNotIn("static-vendor/a11oy-operator-widget.js", paths)


if __name__ == "__main__":
    unittest.main(verbosity=2)
