#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Focused contracts for the shared operator control dock."""

import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
WIDGET_PATH = ROOT / "static-vendor" / "a11oy-operator-widget.js"
ALLOWLIST_PATH = ROOT / ".github" / "shared-file-drift-allow.txt"
EXPECTED_WIDGET_BYTES = 40_737
EXPECTED_WIDGET_SHA256 = "50fbf93caba2439d06a5cb340a66166cdf401f91f2ec36104e22364462a09681"


def _extract_braced_function(source: str, name: str) -> str:
    marker = f"  function {name}("
    start = source.index(marker)
    brace = source.index("{", start)
    depth = 0
    for index in range(brace, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
    raise AssertionError(f"unterminated JavaScript function: {name}")


def _extract_investor_click_listener(source: str) -> str:
    marker = "  document.addEventListener('click', function (e) {"
    start = source.index(marker)
    terminator = "  }, true);"
    end = source.index(terminator, start) + len(terminator)
    return source[start:end]


def _run_node(script: str) -> None:
    node = os.environ.get("SZL_NODE_BINARY") or shutil.which("node")
    if not node:
        if os.environ.get("CI", "").lower() == "true":
            raise AssertionError(
                "Node.js must be provisioned for the CI behavioral focus contract"
            )
        raise unittest.SkipTest(
            "Node.js unavailable; set SZL_NODE_BINARY to run the focus contract"
        )
    result = subprocess.run(
        [node, "-"],
        input=script,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    if result.returncode:
        raise AssertionError(
            f"JavaScript behavioral contract failed ({result.returncode}):\n"
            f"{result.stdout}{result.stderr}"
        )


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
            '@media (max-height:480px) and (min-width:600px)',
            'right:calc(env(safe-area-inset-right,0px) + 176px)',
            'max-width:calc(100vw - 192px)',
            '@media (max-height:480px) and (max-width:599px)',
            'bottom:calc(env(safe-area-inset-bottom,0px) + 72px)',
            'left:calc(env(safe-area-inset-left,0px) + 8px)',
            'html[data-aow-panel-open="true"] [data-szl-dock-control="cop"]',
            'html[data-aow-panel-open="true"] [data-szl-dock-control="investor"]',
            "document.documentElement.removeAttribute('data-aow-panel-open')",
            "target.closest('[data-szl-dock-control=\"investor\"]')",
            "close(false)",
            "focusControlledDialog(investorControl)",
            "control.getAttribute('aria-expanded') !== 'true'",
            "dialog.getAttribute('aria-modal') !== 'true'",
            "[data-szl-initial-focus]",
            '.aow-root[data-open="true"] .aow-toasts{display:none;}',
            "pushMsg('op'",
        ):
            self.assertIn(token, source)

    def test_investor_handoff_moves_focus_into_the_open_modal(self) -> None:
        source = WIDGET_PATH.read_text(encoding="utf-8")
        focus_function = _extract_braced_function(source, "focusControlledDialog")
        click_listener = _extract_investor_click_listener(source)
        script = r"""
const timers = [];
let isOpen = true;
let expanded = false;
let closedWith = "not-called";
let activeElement = null;
const initialFocus = { focus() { activeElement = this; } };
const dialog = {
  getAttribute(name) { return name === "aria-modal" ? "true" : null; },
  querySelector(selector) {
    if (!selector.includes("[data-szl-initial-focus]")) throw new Error("missing initial-focus selector");
    return initialFocus;
  },
  hasAttribute() { return false; },
  setAttribute() {},
};
const controlledInvestor = {
  getAttribute(name) {
    if (name === "aria-controls") return "szl-ceo";
    if (name === "aria-expanded") return expanded ? "true" : "false";
    return null;
  },
};
const document = {
  clickListener: null,
  getElementById(id) { return id === "szl-ceo" ? dialog : null; },
  addEventListener(type, listener, capture) {
    if (type === "click") this.clickListener = { listener, capture };
  },
};
function setTimeout(callback) { timers.push(callback); }
function close(restoreFocus) { closedWith = restoreFocus; isOpen = false; }
""" + focus_function + "\n" + click_listener + r"""
if (!document.clickListener || document.clickListener.capture !== true) {
  throw new Error("investor handoff is not capture-phase");
}
document.clickListener.listener({
  target: {
    closest(selector) {
      return selector === '[data-szl-dock-control="investor"]' ? controlledInvestor : null;
    },
  },
});
if (closedWith !== false) throw new Error("operator did not close without stealing focus");
expanded = true; // The investor target handler opens its controlled modal next.
while (timers.length) timers.shift()();
if (activeElement !== initialFocus) throw new Error("focus did not enter the controlled modal");
"""
        _run_node(script)

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
