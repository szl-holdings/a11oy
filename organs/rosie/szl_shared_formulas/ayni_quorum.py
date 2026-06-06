#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
"""Ayni / Ubuntu quorum-intersection — Round-12 frontier formula (PROVED, sorry-free).

This module EXPOSES (does not re-prove) the sorry-free Lean theorem
``Lutar.Round12.AyniQuorum.quorum_intersection_honest`` from
``szl-holdings/lutar-lean`` (branch ``feat/round12-frontier-unification``,
file ``Lutar/Innovations/round12/Identity_Ayni_Quorum.lean``, theorem at L69).

Proved fact (sorry-free): for ``n`` organs with fault budget ``f`` obeying the Ubuntu
charter ``n ≥ 3f+1``, any two committable quorums of size ``≥ n − f`` intersect in
strictly MORE than ``f`` organs — hence they share at least one *honest* organ:

    |Q1 ∩ Q2| ≥ q1 + q2 − n ≥ 2(n−f) − n = n − 2f ≥ f+1 > f.

This is the Andean *Ayni* (balanced reciprocity) / African *Ubuntu*
("umuntu ngumuntu ngabantu" — a person is a person through other persons) reading of
the classic Byzantine quorum-intersection lemma. It is the proved companion to
``byzantine_quorum`` (whose ``khipu_consensus_safety`` BFT-safety form remains the OPEN
Khipu Conjecture 2). The endpoint EVALUATES the proved bound for caller (n, f, q1, q2);
it never claims the open conjecture and never polls a live cluster.

CITATION: thesis_v22.pdf §2 (Byzantine quorum) + Round-12 frontier (PR #181 Lean)
LEAN:     Lutar.Round12.AyniQuorum.quorum_intersection_honest (sorry-free)
"""
from __future__ import annotations

CITATION = "thesis_v22.pdf §2 (Byzantine quorum) · Round-12 frontier"
LEAN_THEOREM = (
    "Lutar/Innovations/round12/Identity_Ayni_Quorum.lean::"
    "quorum_intersection_honest (Round-12, sorry-free)"
)
LEAN_REPO = "szl-holdings/lutar-lean"
LEAN_BRANCH = "feat/round12-frontier-unification"
CITATIONS = [
    "Ramose, African Philosophy through Ubuntu (Mond Books, 1999)",
    "Metz, 'Toward an African Moral Theory', J. Political Philosophy 15(3) (2007)",
    "Webb (ed.), Yanantin and Masintin in the Andean World (UNM Press, 2012)",
    "Lamport, Shostak, Pease, 'The Byzantine Generals Problem', ACM TOPLAS 4(3) (1982)",
    "Castro & Liskov, 'Practical Byzantine Fault Tolerance', OSDI (1999)",
]


def ayni_quorum_intersection(n: int = 5, f: int | None = None,
                             q1: int | None = None, q2: int | None = None) -> dict:
    """Apply the PROVED Ayni/Ubuntu intersection bound. No re-proving, no network.

    >>> r = ayni_quorum_intersection(5, 1)
    >>> r["honest_organ_guaranteed"], r["intersection_lower_bound"]
    (True, 3)
    >>> ayni_quorum_intersection(3, 1)["ubuntu_charter_n_ge_3f_plus_1"]
    False
    """
    if n < 1:
        raise ValueError("n must be >= 1")
    if f is None:
        f = (n - 1) // 3  # largest f with n >= 3f+1
    if f < 0:
        raise ValueError("f must be >= 0")
    if q1 is None:
        q1 = n - f
    if q2 is None:
        q2 = n - f
    charter_ok = n >= 3 * f + 1
    quorum_ok = (q1 >= n - f) and (q2 >= n - f)
    inter_lower_bound = max(0, q1 + q2 - n)
    guarantee = charter_ok and quorum_ok and inter_lower_bound > f
    return {
        "value": guarantee,
        "n_organs": n,
        "fault_budget_f": f,
        "quorum_sizes": {"q1": q1, "q2": q2},
        "ubuntu_charter_n_ge_3f_plus_1": charter_ok,
        "quorums_committable_ge_n_minus_f": quorum_ok,
        "intersection_lower_bound": inter_lower_bound,
        "honest_organ_guaranteed": guarantee,
        "explanation": (
            "Two committable quorums share strictly more than f organs, hence at least "
            "one honest organ in common — no two conflicting verdicts can both commit."
            if guarantee else
            "Inputs do not satisfy the Ubuntu charter (n>=3f+1) and/or quorum sizes "
            "(>=n-f); the proved guarantee does not apply to these inputs."
        ),
        "proof_status": "sorry-free (Round-12 quorum_intersection_honest)",
        "open_companion": "ubuntu_quorum_safety / khipu_consensus_safety stays Conjecture 2",
        "citation": CITATION,
        "lean_theorem": LEAN_THEOREM,
        "lean_repo": LEAN_REPO,
        "lean_branch": LEAN_BRANCH,
        "references": CITATIONS,
    }


__all__ = [
    "ayni_quorum_intersection",
    "CITATION",
    "LEAN_THEOREM",
    "LEAN_REPO",
    "LEAN_BRANCH",
    "CITATIONS",
]

if __name__ == "__main__":  # pragma: no cover
    import doctest

    fails, _ = doctest.testmod()
    print("✓ ayni_quorum doctests passed" if fails == 0 else f"✗ {fails} failed")

# Doctrine v11 LOCKED — 749/14/163 — c7c0ba17 · Λ = Conjecture 1 (NEVER a theorem)
# SLSA L1 honest (cosign-signed; verifiable via cosign verify). L2 build-provenance attestation is roadmap (Wire D) — not yet earned.
