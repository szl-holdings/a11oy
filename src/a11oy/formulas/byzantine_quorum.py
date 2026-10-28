#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
"""Byzantine quorum helper (n ≥ 3f+1) — Lamport / PBFT classic BFT bound.

a11oy uses this to decide whether the 5-organ mesh can tolerate ``f`` Byzantine
organs and what agreement quorum (n-f) is required to outvote them. Meshes with
``n < 3f+1`` are REFUSED (``ValueError``): no quorum size is safe there.

DEDUP NOTE: the canonical implementation lives in ``szl-holdings/uds-mesh``
(``src/mesh/quorum.py``, ADR-0001 canonical home, PR #73 lineage). If that package is
importable in the runtime we re-export its ``max_byzantine_faults`` / ``quorum_size``
so there is a single source of truth; otherwise we provide an identical, doctested
fallback (same math, same doctrine). No fabricated consensus is ever claimed — live
cluster polling is OUT OF SCOPE (heartbeats are injected by the caller).

Published form (thesis_v22.pdf §2 — "Byzantine quorum"): a mesh of ``n`` organs
tolerating ``f`` faults is BFT-feasible iff ``n ≥ 3f+1``; an agreement quorum needs
``≥ n-f`` live organs (this equals ``2f+1`` only at the minimal mesh ``n = 3f+1``; for
larger ``n`` a ``2f+1`` quorum admits split-brain, e.g. n=5, f=1: {0,1,2} and {0,3,4}
meet only in organ 0). Lamport, Shostak, Pease (1982) / PBFT (Castro–Liskov 1999).

Conditional Lean theorem for the rule implemented here (n ≥ 3f+1, quorum = n-f):
``Lutar/Wave23/QuorumSafety.lean :: khipu_quorum_safety_conditional`` (lutar-lean
@ 3b41221f3eb2ad89fd5acfbc2d250463bc451cc8). It needs ``|faulty| ≤ f``, quorums of size
``≥ n-f`` and honest non-equivocation; it is NOT unconditional BFT safety.

Lean theorem: ``Lutar/KhipuConsensus.lean :: khipu_consensus_safety`` — this is
**Conjecture 2** (BFT safety), an HONEST open ``sorry`` obligation, NOT a closed
theorem (thesis_v22.pdf §1, §4). The arithmetic helpers below are runtime-doctested.

CITATION: thesis_v22.pdf §2  ·  LEAN: Lutar/KhipuConsensus.lean::khipu_consensus_safety (Conjecture 2, open)
"""
from __future__ import annotations

CITATION = "thesis_v22.pdf §2"
LEAN_THEOREM = "Lutar/KhipuConsensus.lean::khipu_consensus_safety (Conjecture 2, open obligation)"
LEAN_CONDITIONAL_THEOREM = (
    "lutar-lean@3b41221f3eb2ad89fd5acfbc2d250463bc451cc8:"
    "Lutar/Wave23/QuorumSafety.lean::khipu_quorum_safety_conditional "
    "(conditional: n >= 3f+1, |faulty| <= f, quorums >= n-f, honest non-equivocation)"
)

# Prefer the canonical uds-mesh implementation (single source of truth).
try:  # pragma: no cover - import-path dependent
    from mesh.quorum import max_byzantine_faults as _mbf, quorum_size as _qs  # type: ignore

    _SOURCE = "uds-mesh (mesh.quorum)"
except Exception:  # pragma: no cover
    try:
        from quorum import max_byzantine_faults as _mbf, quorum_size as _qs  # type: ignore

        _SOURCE = "uds-mesh (quorum)"
    except Exception:
        _mbf = None
        _qs = None
        _SOURCE = "a11oy local fallback (identical math)"


def _require_int(name: str, value: object) -> int:
    """Fail closed on anything that is not a plain int (bool, float, str, None)."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an int, got {type(value).__name__}")
    return value


def max_byzantine_faults(n: int) -> int:
    """Largest f such that n >= 3f+1, i.e. floor((n-1)/3).

    >>> [max_byzantine_faults(n) for n in (1, 3, 4, 5, 6, 7, 10)]
    [0, 0, 1, 1, 1, 2, 3]
    """
    if _mbf is not None:
        return _mbf(n)
    if n < 1:
        return 0
    return (n - 1) // 3


def quorum_size(f: int, n: int | None = None) -> int:
    """Agreement quorum (n-f) needed to outvote f Byzantine organs in an n-organ mesh.

    Without ``n`` the minimal mesh ``n = 3f+1`` is assumed, where ``n-f = 2f+1``.
    Refuses (``ValueError``) when ``n < 3f+1``.

    >>> [quorum_size(f) for f in (0, 1, 2, 3)]
    [1, 3, 5, 7]
    >>> quorum_size(1, n=5)
    4
    """
    _require_int("f", f)
    if f < 0:
        raise ValueError("f must be >= 0")
    if n is None:
        if _qs is not None:
            return _qs(f)
        n = 3 * f + 1
    _require_int("n", n)
    if n < 3 * f + 1:
        raise ValueError(f"refused: n={n} < 3f+1={3 * f + 1}; no quorum size is Byzantine-safe")
    return n - f


def quorum_threshold(n: int, f: int | None = None) -> dict:
    """Honest-schema quorum decision for an n-organ mesh tolerating f faults.

    Fail-closed: refuses (``ValueError``) malformed input and any mesh with
    ``n < 3f+1``. The returned quorum is ``n-f`` (the Wave23 conditional rule).
    """
    _require_int("n", n)
    if n < 1:
        raise ValueError("n must be >= 1")
    if f is None:
        f = max_byzantine_faults(n)
    _require_int("f", f)
    if f < 0:
        raise ValueError("f must be >= 0")
    if n < 3 * f + 1:
        raise ValueError(f"refused: n={n} < 3f+1={3 * f + 1}; no quorum size is Byzantine-safe")
    bft_feasible = True
    required = n - f
    return {
        "value": required,
        "n": n,
        "f": f,
        "required_quorum": required,
        "bft_feasible": bft_feasible,
        "rule": "n >= 3f+1 (else refused) ; quorum = n-f",
        "source": _SOURCE,
        "citation": CITATION,
        "lean_theorem": LEAN_THEOREM,
        "lean_conditional_theorem": LEAN_CONDITIONAL_THEOREM,
    }


__all__ = [
    "max_byzantine_faults",
    "quorum_size",
    "quorum_threshold",
    "CITATION",
    "LEAN_THEOREM",
    "LEAN_CONDITIONAL_THEOREM",
]

if __name__ == "__main__":  # pragma: no cover
    import doctest

    fails, _ = doctest.testmod()
    print("✓ byzantine_quorum doctests passed" if fails == 0 else f"✗ {fails} failed")

# Doctrine v11 LOCKED — 749/14/163 — c7c0ba17 · Λ = Conjecture 1 (NEVER a theorem)
# SLSA L1 honest. L2 build-provenance attestation = roadmap (Wire D) — not yet claimed. L3 not claimed.
