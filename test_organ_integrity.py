# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 SZL Holdings
"""Fail-closed organ-integrity kernel tests. Stdlib only."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from szl_organ_integrity import (  # noqa: E402
    KERNEL_COMMIT,
    envelope,
    evaluate_anatomy,
    evaluate_lambda,
    selftest,
    wgm,
    yawar_chain,
)


class KernelTests(unittest.TestCase):
    def test_selftest(self) -> None:
        self.assertTrue(selftest()["ok"])

    def test_healthy_body(self) -> None:
        ev = evaluate_anatomy(seed=11)
        self.assertEqual(ev["live_count"], 5)
        self.assertFalse(ev["blocked"])
        self.assertEqual(ev["verdict"], "ADVISORY_BODY")
        self.assertEqual(ev["energy"], "UNAVAILABLE")
        self.assertIsNone(ev["energy_j"])
        self.assertFalse(ev["proven_trust"])
        self.assertEqual(ev["locked_proven"], 8)
        self.assertTrue(ev["lambda_advisory"])
        self.assertEqual(ev["conjecture_1"], "OPEN")
        self.assertEqual(ev["kernel_commit"], KERNEL_COMMIT)
        self.assertEqual(len(ev["chain_head"]), 64)
        self.assertTrue(ev["chain_ok"])

    def test_zero_heart_fail_closes(self) -> None:
        ev = evaluate_anatomy(zero_heart=True, seed=11)
        heart = next(o for o in ev["organs"] if o["id"] == "heart")
        self.assertEqual(heart["status"], "DOWN")
        self.assertEqual(heart["metric"], 0.0)
        self.assertTrue(ev["blocked"])
        self.assertEqual(ev["verdict"], "BLOCKED")

    def test_tamper_chain_fail_closes(self) -> None:
        clean = yawar_chain(11, False)
        broken = yawar_chain(11, True)
        self.assertTrue(clean["ok"])
        self.assertFalse(broken["ok"])
        ev = evaluate_anatomy(tamper_chain=True, seed=11)
        yawar = next(o for o in ev["organs"] if o["id"] == "circulatory")
        self.assertEqual(yawar["status"], "DOWN")
        self.assertTrue(ev["blocked"])

    def test_fabricated_joule_refused(self) -> None:
        ev = evaluate_anatomy(fabricate_joule=True, seed=11)
        nervous = next(o for o in ev["organs"] if o["id"] == "nervous")
        self.assertEqual(nervous["status"], "DOWN")
        self.assertEqual(ev["energy"], "UNAVAILABLE")
        self.assertIsNone(ev["energy_j"])
        self.assertTrue(ev["blocked"])

    def test_sorry_cannot_be_green(self) -> None:
        ev = evaluate_anatomy(break_skeleton=True, seed=11)
        skel = next(o for o in ev["organs"] if o["id"] == "skeleton")
        self.assertEqual(skel["status"], "DOWN")
        self.assertEqual(skel["metric"], 7)
        self.assertTrue(ev["blocked"])

    def test_willay_veto_with_live_organs(self) -> None:
        ev = evaluate_anatomy(willay_fire=True, seed=11)
        self.assertEqual(ev["live_count"], 5)
        self.assertTrue(ev["willay"]["refused"])
        self.assertTrue(ev["blocked"])

    def test_wgm_zero_routes(self) -> None:
        w = tuple(1 / 4 for _ in range(4))
        self.assertEqual(wgm((0.9, 0.9, 0.0, 0.9), w), 0.0)
        self.assertEqual(wgm((0.5, float("nan"), 0.5), (1 / 3,) * 3), 0.0)

    def test_lambda_advisory_at_floors(self) -> None:
        ev = evaluate_lambda((0.95, 0.95) + (0.90,) * 11)
        self.assertFalse(ev["blocked"])
        self.assertGreater(ev["value"], 0.9)
        self.assertIn("Conjecture 1", ev["reason"])

    def test_envelope_is_structural_not_signed(self) -> None:
        env = envelope(evaluate_anatomy(seed=11))
        self.assertTrue(env["ok"])
        self.assertEqual(len(env["receipt_sha256"]), 64)
        self.assertIn("STRUCTURAL-ONLY", env["signing"])
        json.dumps(env)


if __name__ == "__main__":
    unittest.main()
