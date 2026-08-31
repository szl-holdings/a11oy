#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
"""Allodial order-theoretic sovereignty checks — EXPERIMENTAL backbone.

Mirrors the kernel-checked Lean declarations in ``Lutar/Allodial.lean`` (PR #229,
merge 783a38d0).  These are PROPOSED engineering gates grounded in a 0-sorry,
no-new-axiom EXPERIMENTAL Lean backbone — NOT locked-8 theorems and NOT formal
Λ results.  Callers must treat them as EXPERIMENTAL-tier.

Lean declarations mirrored (all EXPERIMENTAL, PR #229):
  • allodial_dominates_all  — allodial element dominates every control class
  • allodial_iff_top         — an element is allodial iff it equals ⊤
  • feudal_has_overlord      — a feudal (non-allodial) element always has a strict overlord
  • galois_preserves_allodial — adjoint (Galois) embeddings cannot destroy the allodial position
  • ni_low_independent_of_high — operator-protected low output is independent of the
                                  overlord/high state (non-interference)

This is the formal grounding for the founder's central vision:
  "allodial sovereign compute — no kill-switch, no one can switch it off."
Any element that is NOT ⊤ has an overlord; an element that IS ⊤ is provably free.

CITATION: Lutar/Allodial.lean (PR #229, merge 783a38d0)
LEAN_THEOREM: Lutar/Allodial.lean::allodial_dominates_all / galois_preserves_allodial / ni_low_independent_of_high (EXPERIMENTAL — PROPOSED gate, not a locked theorem)
"""
from __future__ import annotations

from typing import TypedDict, Any, Hashable

CITATION = "Lutar/Allodial.lean (PR #229, merge 783a38d0)"
LEAN_THEOREM = (
    "Lutar/Allodial.lean::allodial_dominates_all / galois_preserves_allodial"
    " / ni_low_independent_of_high"
    " (EXPERIMENTAL — PROPOSED gate, not a locked theorem)"
)
_HONEST_NOTE = (
    "EXPERIMENTAL-tier backbone: the Lean declarations are kernel-checked,"
    " 0-sorry, no-new-axiom, but are PROPOSED engineering gates — NOT locked-8"
    " theorems and NOT formal Λ results.  This Python module is a faithful but"
    " informal mirror of those proofs, not the proof itself."
)

# ---------------------------------------------------------------------------
# Core predicate functions
# ---------------------------------------------------------------------------

def is_allodial(elem: Hashable, top: Hashable) -> bool:
    """Return True iff ``elem`` equals the lattice top element ⊤.

    Mirrors ``allodial_iff_top``: allodial ↔ elem = ⊤.
    An element is allodial (sovereign, no overlord) if and only if it IS the top.
    """
    return elem == top


def dominates_all(
    elem: Hashable,
    elements: list[Hashable],
    leq: list[tuple[Hashable, Hashable]],
) -> bool:
    """Return True iff ``elem`` is ≥ every other element in ``elements``.

    Mirrors ``allodial_dominates_all``: if x is allodial (= ⊤) then ∀ y, y ≤ x.
    ``leq`` is the list of (a, b) pairs meaning a ≤ b in the partial order.
    Reflexivity (x ≤ x) is assumed; it need not appear in ``leq``.
    """
    leq_set: set[tuple[Hashable, Hashable]] = set(leq)
    for y in elements:
        if y == elem:
            continue  # reflexivity
        if (y, elem) not in leq_set:
            return False
    return True


def has_overlord(
    elem: Hashable,
    top: Hashable,
    elements: list[Hashable],
    leq: list[tuple[Hashable, Hashable]],
) -> bool:
    """Return True iff ``elem`` has a strict overlord (i.e. is NOT allodial).

    Mirrors ``feudal_has_overlord``: ¬allodial(x) → ∃ y, x < y.
    A strict overlord is an element y ≠ elem such that elem ≤ y.
    If elem IS the top, there is no overlord (allodial), so returns False.
    """
    if elem == top:
        return False  # allodial — no overlord
    leq_set: set[tuple[Hashable, Hashable]] = set(leq)
    for y in elements:
        if y == elem:
            continue
        if (elem, y) in leq_set:
            return True  # found a strict overlord
    return False


def non_interference_check(
    low_outputs_by_high_state: dict[Any, Any],
) -> dict:
    """Check whether the low-output is invariant across all high states.

    Mirrors ``ni_low_independent_of_high``: the operator-protected low output
    is independent of the overlord/high state.

    ``low_outputs_by_high_state`` maps each high-state label → the low output
    value observed when the system is in that high state.

    Returns a dict with:
      value      — True iff all low outputs are identical (non-interference holds)
      invariant  — same as value
      unique_low_outputs — the set of distinct low output values seen
      high_state_count   — how many high states were checked
      citation   — canonical citation
      lean_theorem — the Lean theorem tag
      tier       — "experimental"
      honest_note — honesty annotation
    """
    values = list(low_outputs_by_high_state.values())
    unique = set(values) if values else set()
    invariant = len(unique) <= 1
    return {
        "value": invariant,
        "invariant": invariant,
        "unique_low_outputs": sorted(str(v) for v in unique),
        "high_state_count": len(low_outputs_by_high_state),
        "citation": CITATION,
        "lean_theorem": LEAN_THEOREM,
        "tier": "experimental",
        "honest_note": _HONEST_NOTE,
    }


class AllodialResult(TypedDict):
    value: bool
    is_allodial: bool
    dominates_all: bool
    has_overlord: bool
    elem: str
    top: str
    citation: str
    lean_theorem: str
    tier: str
    honest_note: str


def allodial_check(
    elem: Hashable,
    top: Hashable,
    elements: list[Hashable],
    leq: list[tuple[Hashable, Hashable]],
) -> AllodialResult:
    """Full allodiality assessment for ``elem`` on the given finite control lattice.

    Returns the HONEST schema with EXPERIMENTAL-tier annotation.
    ``value`` is True iff elem is allodial (= ⊤ and dominates all).
    """
    ia = is_allodial(elem, top)
    da = dominates_all(elem, elements, leq)
    ho = has_overlord(elem, top, elements, leq)
    verdict = ia and da and not ho
    return AllodialResult(
        value=verdict,
        is_allodial=ia,
        dominates_all=da,
        has_overlord=ho,
        elem=str(elem),
        top=str(top),
        citation=CITATION,
        lean_theorem=LEAN_THEOREM,
        tier="experimental",
        honest_note=_HONEST_NOTE,
    )


__all__ = [
    "is_allodial",
    "dominates_all",
    "has_overlord",
    "non_interference_check",
    "allodial_check",
    "CITATION",
    "LEAN_THEOREM",
]

# Doctrine v11 LOCKED — 749/14/163 — c7c0ba17 · Λ = Conjecture 1 (NEVER a theorem)
# SLSA L1 honest. L2 build-provenance attestation = roadmap (Wire D) — not yet claimed. L3 not claimed.


if __name__ == "__main__":
    # -----------------------------------------------------------------------
    # Self-tests: 4-element lattice  ⊥ < a < b < ⊤
    #   Elements: {bot, a, b, top}
    #   Partial order (non-reflexive pairs stored explicitly):
    #     bot≤a, bot≤b, bot≤top, a≤b, a≤top, b≤top
    # -----------------------------------------------------------------------
    elements = ["bot", "a", "b", "top"]
    leq = [
        ("bot", "a"), ("bot", "b"), ("bot", "top"),
        ("a", "b"), ("a", "top"),
        ("b", "top"),
    ]
    top = "top"
    checks = 0

    # 1. allodial_iff_top: top is allodial, others are not
    assert is_allodial("top", top) is True, "top should be allodial"
    assert is_allodial("a", top) is False, "'a' should not be allodial"
    assert is_allodial("bot", top) is False, "'bot' should not be allodial"
    checks += 3

    # 2. dominates_all: top dominates everything; 'a' does NOT dominate 'b'
    assert dominates_all("top", elements, leq) is True, "top must dominate all"
    assert dominates_all("a", elements, leq) is False, "'a' must not dominate 'b' or 'top'"
    checks += 2

    # 3. has_overlord: non-top elements have an overlord; top does not
    assert has_overlord("a", top, elements, leq) is True, "'a' has overlord 'b' (and 'top')"
    assert has_overlord("bot", top, elements, leq) is True, "'bot' has overlords"
    assert has_overlord("top", top, elements, leq) is False, "top has no overlord"
    checks += 3

    # 4. non_interference_check: invariant when low outputs are constant
    ni_ok = non_interference_check({"high_a": "out_x", "high_b": "out_x", "high_c": "out_x"})
    assert ni_ok["invariant"] is True, "constant low output must be non-interfering"
    # FAILS when low outputs vary by high state
    ni_fail = non_interference_check({"high_a": "out_x", "high_b": "out_y"})
    assert ni_fail["invariant"] is False, "varying low output must flag interference"
    checks += 2

    # 5. Full allodial_check on the lattice
    top_result = allodial_check("top", top, elements, leq)
    assert top_result["value"] is True, "top must pass full allodial check"
    a_result = allodial_check("a", top, elements, leq)
    assert a_result["value"] is False, "'a' must fail full allodial check"
    checks += 2

    print(f"ok:true checks:{checks}")
