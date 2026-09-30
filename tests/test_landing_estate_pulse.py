#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Execute the landing-page fetch/render path against backend contract cases."""
import json
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
READINESS = "/api/a11oy/v1/readiness/tab-matrix?view=summary"
MESH = "/api/a11oy/v1/mesh/state"


def responses():
    # Synthetic counts follow backend fields observed again on 2026-09-29.
    return {
        "/healthz": {"status": "ok"},
        READINESS: {"matrix_available": True, "probe_verdict_available": False,
                    "available": False, "matrix_summary": {"tabs": 141, "endpoints": 100}},
        "/api/a11oy/v1/ledger": {"count": 0, "receipts": []},
        MESH: {"mesh_organs": ["a11oy", "Reasoning", "Policy / Safety", "Operator", "Receipts", "Knowledge"],
               "khipu_nodes": []},
    }


def probe_case(data, **changes):
    # Synthetic probe outcomes exercise the rendering boundary; never live evidence.
    data[READINESS].update(available=True, probe_verdict_available=True,
        verdict_summary={"endpoints": 100, "ok": 98, "skippedStateChanging": 2,
                         "lies": 0, "unreachable": 0, "throttled": 0},
        verdict_source_revision="a" * 40, verdict_checked_at="2026-09-08T02:37:17Z",
        verdict_base="https://szlholdings-a11oy.hf.space/",
        verdict_expected_base="https://szlholdings-a11oy.hf.space")
    data[READINESS].update(changes)


class LandingEstatePulseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.node = shutil.which("node")
        if cls.node is None:
            raise RuntimeError("Node is required to execute the actual landing JavaScript")
        html = (ROOT / "a11oy_landing.html").read_text(encoding="utf-8")
        cls.code = html.split("  // ---- live estate pulse:", 1)[1].split("  // ---- (C) living body:", 1)[0]
        cls.code = "// ---- live estate pulse:" + cls.code

    def render(self, data):
        harness = r"""
const vm = require('node:vm');
const input = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));
const elements = {};
const calls = [];
const scope = {URL, AbortController, setTimeout, clearTimeout,
  $: id => elements[id] ||= {textContent:'',className:''},
  setHeroReceiptsFromLedger: () => {},
  fetch: async (url, options) => {
    calls.push({url,cache:options.cache,signal:!!options.signal});
    const body = input.data[url];
    return {ok: body?.httpError !== true, status: body?.httpError ? 503 : 200,
            json: async () => {if(body?.html) throw Error('not JSON'); return body;}};
  }};
vm.createContext(scope);
vm.runInContext(input.code, scope);
scope.loadEstatePulse().then(() => process.stdout.write(JSON.stringify({elements,calls})));
"""
        result = subprocess.run([self.node, "-e", harness],
            input=json.dumps({"code": self.code, "data": data}), text=True, encoding="utf-8",
            capture_output=True, check=True, timeout=20)
        return json.loads(result.stdout)

    def test_actual_backend_fields_render_counts_and_scope(self):
        result = self.render(responses())
        nodes = result["elements"]
        self.assertEqual(nodes["pulse-contract-state"]["textContent"], "SNAPSHOT")
        self.assertIn("141 tabs · 100 endpoint contracts", nodes["pulse-contract-detail"]["textContent"])
        self.assertIn("6 declared organs · 0 recent receipt nodes returned", nodes["pulse-mesh-detail"]["textContent"])
        self.assertIn("does not verify cross-Space", nodes["pulse-mesh-detail"]["textContent"])
        self.assertTrue(all(call["cache"] == "no-store" and call["signal"] for call in result["calls"]))

    def test_zero_counts_do_not_become_placeholder_text(self):
        data = responses()
        data[READINESS]["matrix_summary"] = {"tabs": 0, "endpoints": 0}
        data[MESH]["mesh_organs"] = []
        nodes = self.render(data)["elements"]
        self.assertIn("0 tabs · 0 endpoint contracts", nodes["pulse-contract-detail"]["textContent"])
        self.assertIn("0 declared organs", nodes["pulse-mesh-detail"]["textContent"])

    def test_failed_probe_cannot_show_a_green_reachability_label(self):
        data = responses()
        probe_case(data)
        data[READINESS]["verdict_summary"].update(ok=95, lies=1, unreachable=1, throttled=1)
        nodes = self.render(data)["elements"]
        self.assertEqual(nodes["pulse-contract-state"]["textContent"], "DEGRADED")
        self.assertIn("3 failed/throttled", nodes["pulse-contract-detail"]["textContent"])

    def test_accepted_probe_is_observed_with_skips_and_timestamp(self):
        data = responses()
        probe_case(data)
        nodes = self.render(data)["elements"]
        self.assertEqual(nodes["pulse-contract-state"]["textContent"], "OBSERVED")
        self.assertIn("98 probe passes", nodes["pulse-contract-detail"]["textContent"])
        self.assertIn("2 state-changing checks skipped", nodes["pulse-contract-detail"]["textContent"])

    def test_incomplete_or_wrong_origin_probe_is_unavailable(self):
        for change in ({"verdict_summary": {}}, {"verdict_base": "https://example.org/"},
                       {"verdict_checked_at": "unknown"}, {"available": "true"},
                       {"probe_verdict_available": "true"}, {"verdict_summary": {"endpoints": 100}}):
            with self.subTest(change=change):
                data = responses()
                probe_case(data, **change)
                nodes = self.render(data)["elements"]
                self.assertEqual(nodes["pulse-contract-state"]["textContent"], "UNAVAILABLE")

    def test_wrong_shapes_and_html_fallback_fail_closed(self):
        for readiness in ({"matrix_available": True, "matrix_summary": {"tabs": "141", "endpoints": 100}},
                          {"html": True}, {"httpError": True}):
            with self.subTest(readiness=readiness):
                data = responses()
                data[READINESS] = readiness
                data[MESH] = {"nodes": [1, 2], "peers": [1]}
                nodes = self.render(data)["elements"]
                self.assertEqual(nodes["pulse-contract-state"]["textContent"], "UNAVAILABLE")
                self.assertEqual(nodes["pulse-mesh-state"]["textContent"], "UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
