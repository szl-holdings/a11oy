# SPDX-License-Identifier: Apache-2.0
# Signed-off-by: Lutar, Stephen P. <stephenlutar2@gmail.com>
"""Unit tests for N1–N25 product organs. No serve.app import."""
from __future__ import annotations

import unittest

import szl_n25_organs as organs


class N25OrganTests(unittest.TestCase):
    def test_catalog_is_twenty_five_live(self):
        cat = organs.catalog()
        self.assertEqual(cat["count"], 25)
        self.assertEqual(cat["honesty"], "LIVE")
        self.assertIs(cat["admitted_public"], False)
        self.assertEqual(len(cat["items"]), 25)
        self.assertEqual(cat["items"][0]["id"], "N1")
        self.assertEqual(cat["items"][-1]["id"], "N25")

    def test_sandbox_math(self):
        rec = organs.run_organ("N21", "(2+3)*4")
        self.assertEqual(rec["status"], "EXECUTED")
        self.assertEqual(rec["output"]["value"], 20)
        self.assertEqual(len(rec["hash"]), 64)

    def test_guard_denies_weapons(self):
        rec = organs.run_organ("N3", "weapon targeting")
        self.assertEqual(rec["status"], "DENIED")
        self.assertEqual(rec["output"]["action"], "DENY")

    def test_tune_gpu_unavailable(self):
        rec = organs.run_organ("N11", "sha256:abc")
        self.assertEqual(rec["status"], "DENIED")
        self.assertEqual(rec["output"]["gpu"], "UNAVAILABLE")

    def test_policy_approves_lyte_quote(self):
        rec = organs.run_organ("N25", "tool=quote resource=lyte")
        self.assertEqual(rec["status"], "APPROVED")
        self.assertIs(rec["formula_grants_authority"], False)

    def test_unknown_raises(self):
        with self.assertRaises(KeyError):
            organs.run_organ("N99", "nope")


if __name__ == "__main__":
    unittest.main()
