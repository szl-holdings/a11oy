"""Commercial evidence scopes must not upgrade stale inventory into current coverage.

Offline source contract only. No Hub API, model downloads, billing, or account reads.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "COMMERCIAL_LEDGER.yaml"
GENERATOR = ROOT / "tools" / "_templates" / "content_data.py"
STRATEGY = (
    ROOT / "docs" / "strategy" / "proof-carrying-agent-commercial-wedge-2026-11-19.md"
)
SCOPE_ROWS = ("model_bom_status", "dataset_license_register")


def _load_ledger():
    spec = importlib.util.spec_from_file_location(
        "szl_miniyaml_inventory_truth", ROOT / "tools" / "szl_miniyaml.py"
    )
    assert spec is not None and spec.loader is not None
    parser = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(parser)
    return parser.load(LEDGER.read_text(encoding="utf-8"))


class CommercialInventoryTruthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ledger = _load_ledger()
        cls.rows = {row["id"]: row for row in cls.ledger["rows"]}

    def test_historical_inventory_rows_do_not_assert_current_completeness(self):
        for key in SCOPE_ROWS:
            with self.subTest(row=key):
                row = self.rows[key]
                self.assertEqual(row["state"], "UNKNOWN")
                self.assertIsNone(row["value"])
                self.assertIs(row["blocks_raise"], True)
                self.assertIsNone(row["evidence"])
                self.assertEqual(str(row["last_audited"]), "2026-11-19")
                self.assertIn("Historical", row["why_unknown"])
                self.assertIn("reconcil", row["why_unknown"].lower())

    def test_old_scope_numbers_are_not_currently_verified(self):
        raw = LEDGER.read_text(encoding="utf-8")
        self.assertNotIn("covers all 43 public models", raw)
        self.assertNotIn("covers 28 public datasets", raw)
        for key in SCOPE_ROWS:
            self.assertIn("id: " + key, raw)

    def test_published_launch_prices_have_source_scoped_evidence_not_customer_claim(self):
        price = self.rows["published_price"]
        self.assertEqual(price["state"], "VERIFIED")
        self.assertIs(price["blocks_raise"], True)
        self.assertIsNone(price["why_unknown"])
        self.assertIn("Team USD 2500", price["value"])
        self.assertIn("Pilot USD 15000", price["value"])
        self.assertIn("not contracts", price["value"])
        self.assertTrue(
            any(
                e.get("status") == "supports"
                and e.get("uri") == "https://a-11-oy.com/pricing"
                and "279d8c71b7d2e8ca11b5f70a0b037e9dfb957d8739e890168682126a951f7bc5"
                in e.get("note", "")
                for e in price["evidence"]
            )
        )
        self.assertEqual(self.rows["arr"]["state"], "UNKNOWN")
        self.assertEqual(self.rows["paying_customers"]["state"], "UNKNOWN")

    def test_scaffold_fallback_does_not_claim_no_register_exists(self):
        generator = GENERATOR.read_text(encoding="utf-8")
        self.assertNotIn("no Model BOM register has been created", generator)
        self.assertNotIn("no license register has been created", generator)
        self.assertIn("historical model BOM exists", generator)
        self.assertIn("historical dataset license register exists", generator)

    def test_blocking_gate_continues_to_hold_unreconciled_rows(self):
        module_path = ROOT / "tools" / "commercial_release_gate.py"
        spec = importlib.util.spec_from_file_location("commercial_inventory_gate", module_path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        findings = module.check_commercial_ledger(self.ledger)
        for key in SCOPE_ROWS:
            with self.subTest(key=key):
                self.assertTrue(
                    any(key in finding and "raise blocked" in finding for finding in findings),
                    f"{key} must remain a commercial release hold",
                )

    def test_market_hypotheses_not_promoted_to_revenue_or_production_claims(self):
        strategy = STRATEGY.read_text(encoding="utf-8")
        self.assertIn("Not a revenue claim or release approval", strategy)
        self.assertIn("targets, not actuals", strategy)
        self.assertIn("2026-11-19", strategy)
        self.assertIn("operational_readiness.ready=false", strategy)
        self.assertIn("Published 30-day governed evidence pilot", strategy)
        self.assertIn("An HTTP 402 is a challenge", strategy)


if __name__ == "__main__":
    unittest.main()
