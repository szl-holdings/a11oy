from __future__ import annotations

import copy
import unittest

import a11oy_n25_organs as organs


class N25OrgansContractTests(unittest.TestCase):
    def test_catalog_is_complete_unique_and_evidence_scoped(self) -> None:
        self.assertEqual(len(organs.ORGANS), 25)
        self.assertEqual(len({row["id"] for row in organs.ORGANS}), 25)
        self.assertEqual(
            {row["id"] for row in organs.ORGANS},
            {f"N{i}" for i in range(1, 26)},
        )
        allowed = {"SIMULATED", "MODELED", "MEASURED", "UNAVAILABLE"}
        self.assertTrue(
            all(row["evidence_class"] in allowed for row in organs.ORGANS)
        )
        catalog = organs.catalog()
        self.assertEqual(
            catalog["honesty"], "PER_ORGAN_EVIDENCE_CLASS"
        )
        self.assertFalse(catalog["admitted_public"])
        self.assertEqual(catalog["count"], 25)
        self.assertTrue(
            all(
                row["honesty"] == row["evidence_class"]
                for row in catalog["items"]
            )
        )

    def test_receipt_honesty_matches_each_organ_evidence_class(self) -> None:
        for row in organs.ORGANS:
            with self.subTest(row=row["id"]):
                receipt = organs.run_organ(row["id"], "")
                self.assertEqual(
                    receipt["honesty"], row["evidence_class"]
                )
                self.assertEqual(
                    receipt["evidence_class"], row["evidence_class"]
                )
                self.assertFalse(receipt["formula_grants_authority"])

    def test_tune_remains_denied_and_unavailable(self) -> None:
        receipt = organs.run_organ("N11", "sha256:example")
        self.assertEqual(receipt["status"], "DENIED")
        self.assertEqual(receipt["honesty"], "UNAVAILABLE")
        self.assertEqual(receipt["output"]["gpu"], "UNAVAILABLE")
        self.assertEqual(receipt["output"]["job"], "not-queued")

    def test_guard_and_sandbox_fail_closed(self) -> None:
        guarded = organs.run_organ("N3", "weapon targeting private-data")
        self.assertEqual(guarded["status"], "DENIED")
        sandbox = organs.run_organ(
            "N21", "__import__('os').system('id')"
        )
        self.assertEqual(sandbox["status"], "DENIED")
        self.assertIsNone(sandbox["output"].get("value"))

    def test_hash_binds_the_complete_receipt_body(self) -> None:
        receipt = organs.run_organ("N25", "tool=quote resource=lyte")
        body = {
            key: value
            for key, value in receipt.items()
            if key != "hash"
        }
        self.assertEqual(
            receipt["hash"], organs._sha(organs._canonical(body))
        )
        tampered = copy.deepcopy(body)
        tampered["output"]["allow"] = not tampered["output"]["allow"]
        self.assertNotEqual(
            receipt["hash"], organs._sha(organs._canonical(tampered))
        )

    def test_unknown_organ_is_rejected(self) -> None:
        with self.assertRaises(KeyError):
            organs.run_organ("N26", "")


if __name__ == "__main__":
    unittest.main()
