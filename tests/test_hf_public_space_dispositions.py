# SPDX-License-Identifier: Apache-2.0
"""Validate the dated public Space disposition receipt without live API calls."""

from collections import Counter
import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
RECEIPT = ROOT / "docs/estate/hf-public-space-dispositions-20261003.json"
KEEP_POLICY = ROOT / "docs/estate/hf-nine-flagship-keep.yaml"
SHA40 = re.compile(r"[0-9a-f]{40}\Z")
PUBLIC_SPACE_ID = re.compile(r"SZLHOLDINGS/[A-Za-z0-9][A-Za-z0-9_.-]*\Z")


class PublicSpaceDispositionsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))

    def test_scope_and_counts_remain_review_only(self):
        receipt = self.receipt
        collection = receipt["collection"]
        self.assertEqual(receipt["schema"], "szl.hf-public-space-dispositions/v1")
        self.assertEqual(receipt["receipt_effect"], "OBSERVATION_ONLY")
        self.assertEqual(collection["inventory_state"], "DEGRADED")
        self.assertEqual(collection["organization_policy_keepers"], 8)
        self.assertEqual(collection["missing_keepers"], 0)
        self.assertEqual(collection["unexpected_public_spaces"], 25)
        self.assertEqual(collection["public_application_spaces"], 33)
        self.assertEqual(
            collection["public_application_spaces"],
            collection["organization_policy_keepers"]
            + collection["unexpected_public_spaces"],
        )
        self.assertRegex(collection["observed_at_utc"], r"\A\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ\Z")
        for name in ("source_revision", "keep_policy_git_blob", "inventory_source_git_blob"):
            self.assertRegex(collection[name], SHA40)
        self.assertIn("separate", collection["runtime_scope"].lower())

    def test_rows_are_unique_revision_pinned_and_review_gated(self):
        receipt = self.receipt
        rows = receipt["items"]
        ids = [item["id"] for item in rows]
        self.assertEqual(len(rows), 25)
        self.assertEqual(ids, sorted(ids))
        self.assertEqual(len(set(ids)), len(ids))
        self.assertEqual(Counter(item["class"] for item in rows), receipt["class_counts"])
        self.assertEqual(
            receipt["class_counts"],
            {
                "runtime_policy_conflict": 2,
                "retirement_candidate": 1,
                "source_hub_conflict": 4,
                "public_showcase": 18,
            },
        )
        for item in rows:
            with self.subTest(space=item["id"]):
                self.assertRegex(item["id"], PUBLIC_SPACE_ID)
                self.assertRegex(item["hub_revision"], SHA40)
                self.assertIn(item["review_gate"], receipt["review_gates"])
                self.assertTrue(item["source_action"])
                self.assertIs(item["admitted_to_keep"], False)

    def test_no_record_is_an_implicit_permanent_keeper(self):
        policy = KEEP_POLICY.read_text(encoding="utf-8")
        keep_block = policy.split("\nkeep:\n", 1)[1].split("\nretire_into_killinchu:\n", 1)[0]
        keeper_ids = set(re.findall(r"^  - id: (SZLHOLDINGS/[^\s]+)$", keep_block, re.MULTILINE))
        receipt_ids = {item["id"] for item in self.receipt["items"]}
        self.assertEqual(len(keeper_ids), 8)
        self.assertTrue(receipt_ids.isdisjoint(keeper_ids))


if __name__ == "__main__":
    unittest.main()
