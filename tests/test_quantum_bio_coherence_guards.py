# SPDX-License-Identifier: Apache-2.0
"""Fail-closed input guards for szl_quantum_bio.lindblad_coherence_series.

Matches the hypotheses of lutar-lean Lutar/QuantumBio/CoherenceDecay.lean
(coh_strictAnti / lambda_single_crossing: 0 < C0, 0 < gamma = 1/tau_c).
Stdlib unittest; synthetic parameters only.
"""
import json
import math
import unittest

import szl_quantum_bio as qbio


class _Req:
    def __init__(self, **params):
        self.query_params = {k: str(v) for k, v in params.items()}


BAD_REAL = (0, 0.0, -0.0, -1, -6.05, math.nan, math.inf, -math.inf, True, False, "6.05", None)


class CoherenceGuards(unittest.TestCase):
    def test_default_series_is_unchanged_shape(self):
        s = qbio.lindblad_coherence_series()
        self.assertEqual(len(s["t"]), 60)
        self.assertEqual(s["C"][0], 1.0)
        self.assertEqual(s["tau_c"], 6.05)
        self.assertTrue(all(a >= b for a, b in zip(s["C"], s["C"][1:])))

    def test_refuses_bad_tau_c(self):
        for v in BAD_REAL:
            with self.assertRaises(ValueError, msg=repr(v)):
                qbio.lindblad_coherence_series(tau_c=v)

    def test_refuses_bad_c0(self):
        for v in BAD_REAL:
            with self.assertRaises(ValueError, msg=repr(v)):
                qbio.lindblad_coherence_series(c0=v)

    def test_accepts_small_positive_boundary(self):
        s = qbio.lindblad_coherence_series(tau_c=1e-3, c0=1e-9, steps=3)
        self.assertEqual(len(s["C"]), 3)
        self.assertEqual(qbio.lindblad_coherence_series(tau_c=1, c0=2, steps=2)["C"][0], 2.0)


class CoherenceHandler(unittest.TestCase):
    def test_handler_refuses_with_400_and_valid_json(self):
        for tau in ("0", "-1", "nan", "inf", "-inf"):
            r = qbio._h_coherence(_Req(tau_c=tau))
            self.assertEqual(r.status_code, 400, tau)
            body = json.loads(r.body)
            self.assertEqual(body["status"], "REFUSED")

    def test_handler_default_still_verified(self):
        r = qbio._h_coherence(_Req())
        self.assertEqual(r.status_code, 200)
        body = json.loads(r.body)
        self.assertEqual(body["status"], "VERIFIED")
        self.assertEqual(body["verification_scope"], "COMPUTATIONAL_REPRODUCIBILITY_ONLY")


if __name__ == "__main__":
    unittest.main()
