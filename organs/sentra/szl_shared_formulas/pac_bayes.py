#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
"""PAC-Bayes (Catoni 2007 / McAllester 2003) generalization bound.

Computes the Λ-confidence interval half-width for every honest verdict: given an
empirical risk over ``n`` samples and a confidence ``1-δ``, the true risk is bounded
with high probability by the empirical risk plus a complexity penalty. a11oy attaches
this half-width as the honest confidence interval around each Λ verdict.

Published form (thesis_v22.pdf §2, formula table — "PAC-Bayes (Catoni/McAllester)"):

    Pr[ R(Q) ≤ R̂_S(Q) + √( (KL(Q‖P) + ln(2√n/δ)) / (2n) ) ] ≥ 1 - δ

matching McAllester (2003, Machine Learning 51(1):5–21) and Bégin et al. (2016, Cor. 6).
The sharper Catoni (2007, IMS Lecture Notes — PAC-Bayesian Supervised Classification)
variant is the named anchor.

Lean theorem: ``Lutar/PACBayes.lean :: pac_bayes_bound`` (TH13). Honest: the Lean proof
takes ``BoundedIntegrability`` and ``ChernoffOptimisation`` as explicit hypotheses
because Mathlib v4.13.0 lacks the sub-Gaussian MGF lemma — these are honest open
obligations, NOT fabricated theorems (thesis_v22.pdf §4).

CITATION: thesis_v22.pdf §2  ·  LEAN: Lutar/PACBayes.lean::pac_bayes_bound (TH13)
"""
from __future__ import annotations

import math
from typing import TypedDict

CITATION = "thesis_v22.pdf §2"
LEAN_THEOREM = "Lutar/PACBayes.lean::pac_bayes_bound (TH13)"


class PACBayesOut(TypedDict):
    value: float
    half_width: float
    n: int
    epsilon: float
    kl: float
    citation: str
    lean_theorem: str


def pac_bayes_halfwidth(n: int, epsilon: float, kl: float = 0.0) -> float:
    """Half-width √((KL + ln(2√n/δ)) / (2n)) of the PAC-Bayes interval.

    ``epsilon`` is δ (the 1-δ confidence complement); ``kl`` is KL(Q‖P) ≥ 0
    (0 for the prior-equals-posterior reference case).
    """
    if n < 1:
        raise ValueError("n must be >= 1")
    if not (0.0 < epsilon < 1.0):
        raise ValueError("epsilon (delta) must be in (0,1)")
    if kl < 0.0:
        raise ValueError("kl must be >= 0")
    numerator = kl + math.log((2.0 * math.sqrt(n)) / epsilon)
    return math.sqrt(numerator / (2.0 * n))


def pac_bayes_bound(
    empirical_risk: float, n: int, epsilon: float, kl: float = 0.0
) -> PACBayesOut:
    """Upper bound on the true risk: R̂_S(Q) + half_width, honest schema."""
    hw = pac_bayes_halfwidth(n, epsilon, kl)
    return PACBayesOut(
        value=min(1.0, empirical_risk + hw),
        half_width=hw,
        n=n,
        epsilon=epsilon,
        kl=kl,
        citation=CITATION,
        lean_theorem=LEAN_THEOREM,
    )


__all__ = ["pac_bayes_halfwidth", "pac_bayes_bound", "CITATION", "LEAN_THEOREM"]

# Doctrine v11 LOCKED — 749/14/163 — c7c0ba17 · Λ = Conjecture 1 (NEVER a theorem)
# SLSA L1 honest (cosign-signed; public Sigstore+Rekor). L2 build-provenance attestation roadmap via Wire D — not yet earned (cosign verify-attestation returns "no matching attestations").
