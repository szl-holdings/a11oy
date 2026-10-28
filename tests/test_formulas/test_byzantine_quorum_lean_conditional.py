# SPDX-License-Identifier: Apache-2.0
"""Fail-closed + Lean-correspondence tests for a11oy.formulas.byzantine_quorum.

Stdlib only (unittest; pytest collects it too). The rule under test is the hypothesis
set of lutar-lean Lutar/Wave23/QuorumSafety.lean::khipu_quorum_safety_conditional:
n >= 3f+1, |faulty| <= f, quorums of size >= n-f. Synthetic organ indices only.
"""
import itertools
import math
import unittest

from a11oy.formulas import byzantine_quorum as bq


def split_brain_witness(n, f, q):
    """Return (Q1, Q2, faulty) with |Qi| = q and Q1 & Q2 a subset of faulty (|faulty| <= f),
    i.e. two quorums that can certify different values with honest non-equivocation,
    or None if no such witness exists. Brute force; intended for n <= 9."""
    if q < 1 or q > n:
        return None
    organs = range(n)
    for q1 in itertools.combinations(organs, q):
        s1 = set(q1)
        for q2 in itertools.combinations(organs, q):
            inter = s1.intersection(q2)
            if len(inter) <= f:
                return (q1, q2, tuple(sorted(inter)))
    return None


def old_rule_quorum(f):
    """Pre-patch rule (2f+1), kept here only as the regression witness."""
    return 2 * f + 1


class SplitBrainRegression(unittest.TestCase):
    def test_old_rule_admits_split_brain_on_5_organ_mesh(self):
        w = split_brain_witness(5, 1, old_rule_quorum(1))
        self.assertIsNotNone(w)
        q1, q2, faulty = w
        self.assertEqual(len(faulty), 1)
        # the concrete witness from the Lean-correspondence audit
        self.assertTrue(set((0, 1, 2)) & set((0, 3, 4)) == {0})

    def test_patched_rule_has_no_witness_on_5_organ_mesh(self):
        out = bq.quorum_threshold(5, 1)
        self.assertEqual(out["value"], 4)
        self.assertIsNone(split_brain_witness(5, 1, out["value"]))

    def test_old_rule_witness_set_matches_audit(self):
        bad = [n for n in range(1, 10)
               if split_brain_witness(n, bq.max_byzantine_faults(n),
                                      old_rule_quorum(bq.max_byzantine_faults(n)))]
        self.assertEqual(bad, [2, 3, 5, 6, 8, 9])

    def test_patched_rule_exhaustive_no_witness(self):
        for n in range(1, 10):
            for f in range(0, (n - 1) // 3 + 1):
                q = bq.quorum_threshold(n, f)["value"]
                self.assertEqual(q, n - f)
                self.assertEqual(bq.quorum_size(f, n=n), n - f)
                self.assertIsNone(split_brain_witness(n, f, q), (n, f, q))


class Boundaries(unittest.TestCase):
    def test_n_equals_3f_is_refused(self):
        for f in (1, 2, 3):
            with self.assertRaises(ValueError):
                bq.quorum_threshold(3 * f, f)
            with self.assertRaises(ValueError):
                bq.quorum_size(f, n=3 * f)

    def test_n_equals_3f_plus_1_is_accepted(self):
        for f in (0, 1, 2, 3):
            out = bq.quorum_threshold(3 * f + 1, f)
            self.assertEqual(out["value"], 2 * f + 1)
            self.assertIs(out["bft_feasible"], True)

    def test_f_zero(self):
        self.assertEqual(bq.quorum_threshold(1, 0)["value"], 1)
        self.assertEqual(bq.quorum_threshold(2, 0)["value"], 2)
        self.assertEqual(bq.quorum_threshold(7, 0)["value"], 7)
        self.assertEqual(bq.quorum_size(0), 1)

    def test_default_f(self):
        out = bq.quorum_threshold(5)
        self.assertEqual((out["f"], out["value"]), (1, 4))

    def test_minimal_mesh_quorum_size_unchanged(self):
        self.assertEqual([bq.quorum_size(f) for f in (0, 1, 2, 3)], [1, 3, 5, 7])


class MalformedInput(unittest.TestCase):
    def test_threshold_rejects_malformed_n(self):
        for n in (0, -1, None, True, False, 5.0, "5", math.nan, math.inf):
            with self.assertRaises(ValueError, msg=repr(n)):
                bq.quorum_threshold(n, 1)

    def test_threshold_rejects_malformed_f(self):
        for f in (-1, True, 1.0, "1", math.nan):
            with self.assertRaises(ValueError, msg=repr(f)):
                bq.quorum_threshold(5, f)

    def test_quorum_size_rejects_malformed(self):
        for args, kw in (((-1,), {}), ((True,), {}), ((1.0,), {}), (("1",), {}),
                         ((1,), {"n": 3}), ((1,), {"n": True}), ((1,), {"n": 5.0})):
            with self.assertRaises(ValueError, msg=repr((args, kw))):
                bq.quorum_size(*args, **kw)

    def test_schema_is_additive(self):
        out = bq.quorum_threshold(4, 1)
        for k in ("value", "n", "f", "required_quorum", "bft_feasible", "rule",
                  "source", "citation", "lean_theorem"):
            self.assertIn(k, out)
        self.assertEqual(out["lean_theorem"], bq.LEAN_THEOREM)
        self.assertIn("khipu_quorum_safety_conditional", out["lean_conditional_theorem"])


if __name__ == "__main__":
    unittest.main()
