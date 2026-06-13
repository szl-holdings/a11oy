#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
"""Coherence-decay entanglement-generating-capacity bound — EXPERIMENTAL backbone.

Mirrors the kernel-checked Lean declarations in ``Lutar/Entanglement.lean``
(PR #230, merge 3a7f222ed3bb).  These are PROPOSED engineering gates grounded
in a 0-sorry, no-new-axiom EXPERIMENTAL Lean backbone — NOT locked-8 theorems
and NOT formal Λ results.  This is a CAPACITY BOUND, not a claimed rate.

Lean declarations mirrored (all EXPERIMENTAL, PR #230):
  • capBound C₀ γ t = C₀ · exp(−γ·t)   — the capacity-bound formula
  • capBound_nonneg    — bound is ≥ 0 for non-negative inputs
  • capBound_zero      — bound = 0 when C₀ = 0
  • capBound_antitone  — bound is antitone (strictly decreasing) in t for γ > 0
  • entanglement_decays_under_bound — entanglement-generating capacity stays ≤ capBound

Physical interpretation: as coherence decays exponentially at rate γ, the upper
bound on entanglement-generating capacity also decays.  This is a CEILING, not a
guarantee of any specific entanglement rate.

CITATION: Lutar/Entanglement.lean (PR #230, merge 3a7f222ed3bb)
LEAN_THEOREM: Lutar/Entanglement.lean::capBound_antitone / entanglement_decays_under_bound (EXPERIMENTAL — PROPOSED gate, not a locked theorem)
"""
from __future__ import annotations

import math
from typing import TypedDict

CITATION = "Lutar/Entanglement.lean (PR #230, merge 3a7f222ed3bb)"
LEAN_THEOREM = (
    "Lutar/Entanglement.lean::capBound_antitone"
    " / entanglement_decays_under_bound"
    " (EXPERIMENTAL — PROPOSED gate, not a locked theorem)"
)
_HONEST_NOTE = (
    "EXPERIMENTAL-tier backbone: the Lean declarations are kernel-checked,"
    " 0-sorry, no-new-axiom, but are PROPOSED engineering gates — NOT locked-8"
    " theorems and NOT formal Λ results.  This is a CAPACITY UPPER BOUND on"
    " entanglement-generating capacity under coherence decay; it does not"
    " guarantee any specific entanglement rate.  The Python module is a"
    " faithful but informal mirror of those proofs, not the proof itself."
)


class CapBoundOut(TypedDict):
    value: float
    cap_bound: float
    c0: float
    gamma: float
    t: float
    nonneg: bool
    antitone_check: bool
    citation: str
    lean_theorem: str
    tier: str
    honest_note: str


def cap_bound(c0: float, gamma: float, t: float) -> float:
    """Coherence→entanglement-generating-capacity upper bound: C₀ · exp(−γ·t).

    Mirrors ``capBound C₀ γ t`` in Lutar/Entanglement.lean.

    Parameters
    ----------
    c0    : initial capacity (≥ 0)
    gamma : decay rate (≥ 0; γ=0 → constant bound)
    t     : time (≥ 0)

    Returns the scalar bound value ≥ 0.
    """
    if c0 < 0.0:
        raise ValueError("c0 must be >= 0 (initial capacity is non-negative)")
    if gamma < 0.0:
        raise ValueError("gamma must be >= 0 (decay rate is non-negative)")
    if t < 0.0:
        raise ValueError("t must be >= 0 (time is non-negative)")
    return c0 * math.exp(-gamma * t)


def cap_bound_nonneg(c0: float, gamma: float, t: float) -> bool:
    """Return True iff cap_bound(c0, gamma, t) >= 0.

    Mirrors ``capBound_nonneg``.  Always True for non-negative inputs (trivially
    follows from exp being positive), but exposed as an explicit gate.
    """
    return cap_bound(c0, gamma, t) >= 0.0


def cap_bound_antitone(
    c0: float, gamma: float, t1: float, t2: float
) -> bool:
    """Return True iff cap_bound is antitone: t1 < t2 → cap_bound(t1) ≥ cap_bound(t2).

    Mirrors ``capBound_antitone``.  For γ > 0 and t1 < t2 the bound strictly decreases.
    For γ = 0 the bound is constant (weakly antitone, i.e. ≥ holds with equality).
    """
    if t1 >= t2:
        raise ValueError("antitone check requires t1 < t2")
    return cap_bound(c0, gamma, t1) >= cap_bound(c0, gamma, t2) - 1e-15


def entanglement_decays_under_bound(
    c0: float, gamma: float, t: float, observed_capacity: float
) -> bool:
    """Return True iff observed_capacity ≤ cap_bound(c0, gamma, t).

    Mirrors ``entanglement_decays_under_bound``: the actual entanglement-generating
    capacity is bounded above by the exponential decay envelope.  Use this as an
    operational sanity gate on a measured or claimed capacity figure.
    """
    return observed_capacity <= cap_bound(c0, gamma, t) + 1e-15


def cap_bound_full(c0: float, gamma: float, t: float) -> CapBoundOut:
    """Full HONEST schema response for the capacity-bound endpoint."""
    val = cap_bound(c0, gamma, t)
    nonneg = val >= 0.0
    # Antitone check: bound at t+1 should be <= bound at t (for t >= 0)
    antitone = cap_bound_antitone(c0, gamma, t, t + 1.0) if gamma > 0.0 else True
    return CapBoundOut(
        value=val,
        cap_bound=val,
        c0=c0,
        gamma=gamma,
        t=t,
        nonneg=nonneg,
        antitone_check=antitone,
        citation=CITATION,
        lean_theorem=LEAN_THEOREM,
        tier="experimental",
        honest_note=_HONEST_NOTE,
    )


__all__ = [
    "cap_bound",
    "cap_bound_nonneg",
    "cap_bound_antitone",
    "entanglement_decays_under_bound",
    "cap_bound_full",
    "CITATION",
    "LEAN_THEOREM",
]

# Doctrine v11 LOCKED — 749/14/163 — c7c0ba17 · Λ = Conjecture 1 (NEVER a theorem)
# SLSA L1 honest. L2 build-provenance attestation = roadmap (Wire D) — not yet claimed. L3 not claimed.


if __name__ == "__main__":
    # -----------------------------------------------------------------------
    # Self-tests for cap_bound and derivative predicates
    # -----------------------------------------------------------------------
    checks = 0

    # 1. cap_bound(C0, γ, 0) == C0 (mirrors capBound_nonneg + zero-time identity)
    assert abs(cap_bound(2.5, 0.3, 0.0) - 2.5) < 1e-12, "cap_bound at t=0 must equal C0"
    assert abs(cap_bound(0.0, 0.5, 10.0) - 0.0) < 1e-12, "cap_bound with C0=0 must be 0"
    checks += 2

    # 2. nonneg: always true for non-negative inputs
    assert cap_bound_nonneg(1.0, 0.5, 5.0) is True, "bound must be non-negative"
    assert cap_bound_nonneg(0.0, 0.0, 0.0) is True, "zero bound is non-negative"
    checks += 2

    # 3. antitone: bound at t+1 <= bound at t for γ > 0
    assert cap_bound_antitone(1.0, 0.5, 0.0, 1.0) is True, "antitone: t=0 >= t=1"
    assert cap_bound_antitone(3.0, 0.1, 2.0, 5.0) is True, "antitone: t=2 >= t=5"
    checks += 2

    # 4. entanglement_decays_under_bound
    # Observed at the bound itself: must pass
    cb = cap_bound(1.0, 0.5, 2.0)
    assert entanglement_decays_under_bound(1.0, 0.5, 2.0, cb) is True, "at bound: ok"
    # Observed above the bound: must fail
    assert entanglement_decays_under_bound(1.0, 0.5, 2.0, cb + 0.1) is False, "above bound: fail"
    checks += 2

    # 5. Strict decay check: cap_bound(1, 1, 1) < cap_bound(1, 1, 0)
    assert cap_bound(1.0, 1.0, 1.0) < cap_bound(1.0, 1.0, 0.0), "strictly decays for γ>0"
    checks += 1

    print(f"ok:true checks:{checks}")
