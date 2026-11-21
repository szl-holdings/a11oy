# SPDX-License-Identifier: Apache-2.0
"""Behavioral Ayllu Second Brain UI honesty tests, without provider calls.

Read the exact served HTML template out of Python AST, then run only the
embedded Second Brain display function in an isolated Node VM. No network,
credentials, model invocation, or application import is required.
"""
from __future__ import annotations

import ast
import json
import shutil
import subprocess
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "a11oy_ayllu.py"
NODE = shutil.which("node")
DRIVER = r"""
"use strict";
const vm = require("node:vm");
const input = JSON.parse(require("node:fs").readFileSync(0, "utf8"));
const elements = {
  "sb-badge": {textContent: ""},
  "sb-out": {innerHTML: ""}
};
const escape = (value) => String(value).replace(/[&<>"']/g, (ch) =>
  ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[ch]));
const ctx = {
  document: {getElementById: (id) => elements[id]},
  j: async () => input.response,
  api: (name) => "/api/a11oy/v1/ayllu/" + name,
  esc: escape,
  unavailable: (el, status) => {
    el.innerHTML = "endpoint unavailable (" + escape(status) + ")";
  }
};
vm.createContext(ctx);
vm.runInContext(input.source, ctx, {timeout: 1000});
ctx.loadSecondBrain().then(() => process.stdout.write(JSON.stringify({
  badge: elements["sb-badge"].textContent,
  html: elements["sb-out"].innerHTML
}))).catch((e) => { console.error(String(e)); process.exitCode = 1; });
"""

def display_function() -> str:
    module = ast.parse(SOURCE.read_text(encoding="utf-8"))
    pages = [
        node.value.value
        for node in module.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "_PAGE"
                for target in node.targets)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    ]
    if len(pages) != 1:
        raise AssertionError("Exactly one source-owned Ayllu page required")
    page = pages[0]
    start = page.index("async function loadSecondBrain(){")
    end = page.index("\nasync function loadFormulas(){", start)
    return page[start:end]


def sample() -> dict:
    return {
        "schema": "szl.khipu.compound-second-brain.v1",
        "system_id": "SZL-Khipu-Second-Brain-v1",
        "ready_for_grounded_navigation": False,
        "live_grounded_turn_verified_this_request": False,
        "promotion_state": "BLOCKED_ARTIFACT_AND_EVAL_GATES",
        "profile": {
            "expected_model": "khipu:latest",
            "served_model": None,
            "exact_tag_observed": False,
            "artifact_binding": "UNBOUND",
        },
        "memory": {
            "built": True, "document_count": 55, "chunk_count": 484,
            "node_count": 743, "brain_handle_count": 9465,
            "training_authority_rows": 0,
        },
        "training_boundary": {
            "raw_brain_nodes_admitted_to_gradients": 0,
            "raw_brain_nodes_observed": 9465,
        },
    }


@unittest.skipUnless(NODE, "Node required for embedded-browser behavioral replay")
class SecondBrainDisplayContract(unittest.TestCase):
    def render(self, response: dict) -> dict:
        result = subprocess.run(
            [NODE, "-e", DRIVER],
            input=json.dumps({"source": display_function(), "response": response}),
            capture_output=True, text=True, timeout=10, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_realistic_memory_online_and_model_missing_are_distinct(self) -> None:
        view = self.render({"ok": True, "status": 200, "data": sample()})
        self.assertEqual(view["badge"], "inference held")
        self.assertIn("MEMORY BUILT / INFERENCE HELD", view["html"])
        self.assertIn("expected model khipu:latest", view["html"])
        self.assertIn("served model NOT OBSERVED", view["html"])
        self.assertIn("exact tag NOT VERIFIED", view["html"])
        self.assertIn("artifact UNBOUND", view["html"])
        self.assertNotIn("NAVIGATION API READY", view["html"])
        self.assertIn("0 / 9465", view["html"])

    def test_api_navigation_does_not_claim_signed_turn_or_artifact(self) -> None:
        response = sample()
        response["ready_for_grounded_navigation"] = True
        response["profile"].update({
            "served_model": "khipu:latest", "exact_tag_observed": True,
        })
        view = self.render({"ok": True, "status": 200, "data": response})
        self.assertEqual(view["badge"], "API navigation only")
        self.assertIn("NAVIGATION API READY / TURN UNVERIFIED", view["html"])
        self.assertIn("served model khipu:latest", view["html"])
        self.assertIn("artifact UNBOUND", view["html"])
        self.assertIn("do NOT independently verify a signed model completion", view["html"])

    def test_inconsistent_200_and_mismatched_tag_fail_closed(self) -> None:
        for mismatch in ("wrong-model", None):
            with self.subTest(mismatch=mismatch):
                response = sample()
                response["ready_for_grounded_navigation"] = True
                response["profile"]["exact_tag_observed"] = True
                response["profile"]["served_model"] = mismatch
                view = self.render({"ok": True, "status": 200, "data": response})
                self.assertEqual(view["badge"], "inference held")
                self.assertNotIn("NAVIGATION API READY", view["html"])

    def test_string_truthiness_does_not_promote_memory_or_model(self) -> None:
        response = sample()
        response["ready_for_grounded_navigation"] = "true"
        response["profile"]["exact_tag_observed"] = "true"
        response["memory"]["built"] = "true"
        view = self.render({"ok": True, "status": 200, "data": response})
        self.assertEqual(view["badge"], "inference held")
        self.assertIn("MEMORY / INFERENCE NOT READY", view["html"])
        self.assertNotIn("NAVIGATION API READY", view["html"])

    def test_success_with_malformed_body_is_not_a_green(self) -> None:
        for value in (None, [], "ok"):
            with self.subTest(value=value):
                view = self.render({"ok": True, "status": 200, "data": value})
                self.assertEqual(view["badge"], "offline")
                self.assertIn("INVALID_RESPONSE", view["html"])

    def test_user_controlled_fields_are_html_escaped(self) -> None:
        response = sample()
        response["profile"]["expected_model"] = "<img src=x onerror=alert(1)>"
        response["system_id"] = "<script>alert(1)</script>"
        view = self.render({"ok": True, "status": 200, "data": response})
        self.assertNotIn("<script>", view["html"])
        self.assertNotIn("<img", view["html"])
        self.assertIn("&lt;script&gt;", view["html"])
        self.assertIn("&lt;img", view["html"])


if __name__ == "__main__":
    unittest.main()
