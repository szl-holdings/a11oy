"""Focused contracts for the shared operator control dock."""

import hashlib
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
WIDGET_PATH = ROOT / "static-vendor" / "a11oy-operator-widget.js"
ALLOWLIST_PATH = ROOT / ".github" / "shared-file-drift-allow.txt"
EXPECTED_WIDGET_BYTES = 36_965
EXPECTED_WIDGET_SHA256 = "0e270225adc0ed21de48b9224e3b8f10bcd0c9a78ea9472cd7d4af1cfecff38c"


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
