#!/usr/bin/env python3
"""Packet 8 Decision Integrity Kernel tests. Network-free."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import a11oy_kernel as kernel  # noqa: E402


class KernelContractTests(unittest.TestCase):
    def test_version_and_schema(self) -> None:
        self.assertEqual(kernel.VERSION, "8.0.0")
        self.assertEqual(kernel.SCHEMA, "szl.decision-integrity-kernel/v8")

    def test_every_formula_authority_is_none(self) -> None:
        result = kernel.evaluate(
            {
                "vertical_id": "terra",
                "case_id": "unit-empty",
                "proposed_action": "draft committee memo",
                "allowed_actions": ["draft committee memo"],
                "prohibited_actions": ["automatic offer"],
                "sources": [],
                "evidence": [],
                "contradictions": [],
                "used_fuel": 1,
                "prior_approval": False,
                "graph": {"nodes": [], "edges": []},
            }
        )
        for item in result["formulas"]:
            self.assertEqual(item["authority"], "NONE")
        self.assertFalse(result["policy"]["model_grants_authority"])
        self.assertFalse(result["policy"]["formula_grants_authority"])
        self.assertFalse(result["policy"]["market_signal_grants_authority"])
        self.assertEqual(result["receipt"]["formula_authority"], "NONE")

    def test_lambda_is_advisory_conjectural(self) -> None:
        result = kernel.evaluate({"graph": {"nodes": [], "edges": []}})
        lam = [item for item in result["formulas"] if item["id"] == "LAMBDA"][0]
        self.assertEqual(lam["status"], "ADVISORY_CONJECTURAL")
        self.assertEqual(lam["authority"], "NONE")

    def test_scan_catches_authority_phrase(self) -> None:
        scan = kernel.scan_memo("this is legal advice and you should buy")
        self.assertTrue(scan["claimed_authority"])
        self.assertIn("this is legal advice", scan["hits"])

    def test_replay_hold(self) -> None:
        result = kernel.evaluate(
            {
                "proposed_action": "draft committee memo",
                "allowed_actions": ["draft committee memo"],
                "prohibited_actions": [],
                "prior_approval": True,
                "sources": [
                    {
                        "id": "s",
                        "name": "src",
                        "rights": "ADMITTED",
                        "freshness": "LIVE",
                    }
                ],
                "evidence": [{"id": "e", "source_id": "s", "weight": 0.5}],
                "graph": {"nodes": [{"id": "n"}], "edges": []},
            }
        )
        replay = kernel.replay_receipt(result["receipt"])
        self.assertTrue(replay["hold"])
        tampered = dict(result["receipt"])
        tampered["state"] = "APPROVED" if tampered["state"] != "APPROVED" else "DENIED"
        self.assertFalse(kernel.replay_receipt(tampered)["hold"])


class FrozenEvalTests(unittest.TestCase):
    def test_all_frozen_evals(self) -> None:
        eval_root = ROOT
        files = sorted(eval_root.glob("*/evals/*.json"))
        self.assertGreaterEqual(len(files), 12)
        for path in files:
            with self.subTest(path=str(path)):
                case = json.loads(path.read_text(encoding="utf-8"))
                result = kernel.evaluate(case["payload"])
                self.assertEqual(result["state"], case["expected_state"], path.name)
                self.assertEqual(
                    result["reason_codes"],
                    case["expected_reason_codes"],
                    path.name,
                )
                self.assertEqual(result["receipt"]["formula_authority"], "NONE")


if __name__ == "__main__":
    unittest.main()
