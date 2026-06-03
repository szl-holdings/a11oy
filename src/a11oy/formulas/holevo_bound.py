#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
"""Holevo (1973) capacity bound — bounds the post-quantum claim in /honest.

The Holevo quantity χ upper-bounds the classical (accessible) information that can be
extracted from an ensemble of quantum states. a11oy uses it to put an HONEST ceiling on
any "post-quantum" channel claim surfaced by /honest: we never assert more accessible
information than χ permits.

Published form (thesis_v22.pdf §2, formula table — "Holevo bound"):
    χ(η) = S( Σ_i p_i ρ_i ) − Σ_i p_i S( ρ_i )
where S(·) is the von Neumann entropy. A. S. Holevo (1973), "Bounds for the quantity of
information transmissible by a quantum communication channel."

For the operational a11oy use we evaluate the standard scalar capacity ceiling of a
single bosonic mode under additive noise, C ≤ log2(1 + SNR) (Holevo capacity of a
thermal-noise channel reduces to this Shannon-form ceiling at high dimension), and the
discrete-ensemble χ for an arbitrary set of density matrices.

Lean theorem: ``Lutar/QuantumHolevoReceipt.lean :: holevo_chi_nonneg`` (PR #176). The
Gibbs-inequality step is an HONEST hardness/assumption tag, not a closed proof
(thesis_v22.pdf §4). NOT fabricated.

CITATION: thesis_v22.pdf §2  ·  LEAN: Lutar/QuantumHolevoReceipt.lean::holevo_chi_nonneg (PR #176)
"""
from __future__ import annotations

import math
from typing import Sequence

CITATION = "thesis_v22.pdf §2"
LEAN_THEOREM = "Lutar/QuantumHolevoReceipt.lean::holevo_chi_nonneg (PR #176)"


def _von_neumann_entropy(eigenvalues: Sequence[float]) -> float:
    """S(ρ) = -Σ λ_i log2 λ_i over the (nonneg, sum-1) eigenvalues of ρ."""
    s = 0.0
    for lam in eigenvalues:
        if lam > 0.0:
            s -= lam * math.log2(lam)
    return s


def holevo_chi(probs: Sequence[float], state_spectra: Sequence[Sequence[float]]) -> float:
    """χ = S(Σ p_i ρ_i) − Σ p_i S(ρ_i) for diagonal (commuting) density matrices.

    ``state_spectra[i]`` is the eigenvalue list of ρ_i; for the diagonal/commuting case
    the average state's spectrum is the probability-weighted mixture.
    """
    if len(probs) != len(state_spectra):
        raise ValueError("probs/state_spectra length mismatch")
    if abs(sum(probs) - 1.0) > 1e-9:
        raise ValueError("probs must sum to 1")
    dim = len(state_spectra[0])
    avg = [0.0] * dim
    for p, spec in zip(probs, state_spectra):
        if len(spec) != dim:
            raise ValueError("all spectra must share dimension (commuting case)")
        for j in range(dim):
            avg[j] += p * spec[j]
    s_avg = _von_neumann_entropy(avg)
    s_mix = sum(p * _von_neumann_entropy(spec) for p, spec in zip(probs, state_spectra))
    return s_avg - s_mix


def holevo_capacity(dim: int, snr: float) -> dict:
    """Holevo/Shannon capacity ceiling C ≤ log2(dim) and C ≤ log2(1+SNR).

    The accessible information is bounded by BOTH the Hilbert-space dimension
    (χ ≤ log2 dim) and the thermal-noise SNR ceiling. We return the binding (min) bound.
    """
    if dim < 1:
        raise ValueError("dim must be >= 1")
    if snr < 0.0:
        raise ValueError("snr must be >= 0")
    dim_ceiling = math.log2(dim)
    snr_ceiling = math.log2(1.0 + snr)
    binding = min(dim_ceiling, snr_ceiling)
    return {
        "value": binding,
        "dim_ceiling_bits": dim_ceiling,
        "snr_ceiling_bits": snr_ceiling,
        "binding_bound_bits": binding,
        "dim": dim,
        "snr": snr,
        "citation": CITATION,
        "lean_theorem": LEAN_THEOREM,
    }


__all__ = ["holevo_chi", "holevo_capacity", "CITATION", "LEAN_THEOREM"]

# Doctrine v11 LOCKED — 749/14/163 — c7c0ba17 · Λ = Conjecture 1 (NEVER a theorem)
# SLSA L1 honest + L2 attested (public Sigstore+Rekor) where slsa-verifier confirms.
