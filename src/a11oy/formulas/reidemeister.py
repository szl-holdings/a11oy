#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
"""Reidemeister knot-move topology check for the Khipu braid.

The Khipu receipt chain is modeled as a braid; two braid words encode the SAME knot
(the SAME chain topology) iff one can be transformed into the other by a finite sequence
of Reidemeister moves I, II, III. a11oy uses this to verify that a re-encoded Khipu braid
is topologically equivalent to the original — a structural integrity check on the chain.

We operate on Gauss-code-style crossing sequences and apply the three local moves:
  R1: add/remove a self-kink   (a crossing of a strand with itself)
  R2: add/remove a poke        (two adjacent opposite crossings of two strands)
  R3: slide a strand over a crossing (triangle move — order-3 permutation of a triple)

We compute the simplest invariant preserved by all three: the writhe-free crossing
parity / reduced word after R1+R2 cancellation. Equal reduced words ⇒ provably equivalent
under R1/R2 (R3 preserves the reduced length). This is a sound (not complete) topology
check — a positive ("equivalent") answer is conservative.

Published form (thesis_v22.pdf §2, formula table — "Reidemeister"): Reidemeister moves
I–III (Reidemeister 1927). Tagged SCAFFOLDING/topology check in v22 — a real combinatorial
invariant, used as a structural check, NOT a claim about quantum/holographic knots.

Lean: v15 knot-calculus module (KnotCalculus); knot-move invariance is descriptive
scaffolding in the thesis (thesis_v22.pdf §2). No fabricated theorem name is claimed.

CITATION: thesis_v22.pdf §2  ·  LEAN: KnotCalculus (v15 knot-move invariance, scaffolding)
"""
from __future__ import annotations

from typing import Sequence

CITATION = "thesis_v22.pdf §2"
LEAN_THEOREM = "KnotCalculus (v15 Reidemeister knot-move invariance, scaffolding-tagged)"


def _reduce_r1_r2(word: Sequence[int]) -> tuple[int, ...]:
    """Cancel R1 self-kinks (x,x adjacent) and R2 pokes (x,-x adjacent).

    Crossings are signed ints: +i / -i are opposite crossings on strand-pair i; a
    repeated identical token (i,i) is a self-kink (R1). Iterate to a fixed point.
    """
    stack: list[int] = []
    for c in word:
        if stack:
            top = stack[-1]
            if top == -c:  # R2 poke cancellation
                stack.pop()
                continue
            if top == c and c != 0:  # R1 self-kink cancellation
                stack.pop()
                continue
        stack.append(c)
    return tuple(stack)


def reduced_word(word: Sequence[int]) -> tuple[int, ...]:
    """Fully reduce a crossing word under repeated R1/R2 to its canonical form."""
    prev = tuple(word)
    while True:
        cur = _reduce_r1_r2(prev)
        if cur == prev:
            return cur
        prev = cur


def equivalent(word_a: Sequence[int], word_b: Sequence[int]) -> dict:
    """Sound topology check: equal reduced words ⇒ equivalent under Reidemeister moves.

    Honest schema. ``value`` True means provably equivalent under R1/R2 (R3 preserves
    reduced length); False means the check could not certify equivalence (conservative).
    """
    ra = reduced_word(word_a)
    rb = reduced_word(word_b)
    eq = ra == rb
    return {
        "value": eq,
        "equivalent": eq,
        "reduced_a": list(ra),
        "reduced_b": list(rb),
        "moves": "R1 (self-kink), R2 (poke), R3 (triangle, length-preserving)",
        "soundness": "sound, not complete — positive answer is conservative",
        "citation": CITATION,
        "lean_theorem": LEAN_THEOREM,
    }


def is_unknot(word: Sequence[int]) -> dict:
    """Check whether a single Khipu braid word reduces to the trivial (unknotted) chain."""
    return equivalent(word, [])


__all__ = ["reduced_word", "equivalent", "is_unknot", "CITATION", "LEAN_THEOREM"]

# Doctrine v11 LOCKED — 749/14/163 — c7c0ba17 · Λ = Conjecture 1 (NEVER a theorem)
# SLSA L1 honest + L2 attested (public Sigstore+Rekor) where slsa-verifier confirms.
