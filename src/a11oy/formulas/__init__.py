#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
"""a11oy.formulas — thesis-v22 formulas instilled into the front-door organ.

Every module is a REAL implementation (no production stubs) carrying a thesis_v22.pdf
citation + a real Lean theorem/obligation name in its docstring. a11oy is the front door
that instills these first; the other 4 organs echo a shared subset (see each organ's
``feat/import-shared-formulas`` PR).

Modules:
  pac_bayes        — Catoni/McAllester PAC-Bayes Λ-confidence interval
  bls_aggregate    — BLS12-381 aggregate signatures (py_ecc) over the Khipu chain
  welford          — online mean/variance accumulator (per request)
  byzantine_quorum — n≥3f+1 helper (dedups uds-mesh PR #73 when importable)
  holevo_bound     — quantum capacity bound for the post-quantum /honest claim
  bloom_filter     — rotation-safe Bloom for receipt-membership checks
  kalman           — verdict state estimator for streaming Λ
  hnsw_retrieval   — k-NN retrieval companion (amaru owns retrieval — honest delegate)
  reidemeister     — knot-move topology check for the Khipu braid

Doctrine v11 LOCKED — 749/14/163 — c7c0ba17 · Λ = Conjecture 1 (NEVER a theorem).
"""
from __future__ import annotations

from . import (
    bloom_filter,
    bls_aggregate,
    byzantine_quorum,
    hnsw_retrieval,
    holevo_bound,
    kalman,
    pac_bayes,
    reidemeister,
    welford,
)

__all__ = [
    "pac_bayes",
    "bls_aggregate",
    "welford",
    "byzantine_quorum",
    "holevo_bound",
    "bloom_filter",
    "kalman",
    "hnsw_retrieval",
    "reidemeister",
]

# SLSA L1 honest + L2 attested (public Sigstore+Rekor) where slsa-verifier confirms.
