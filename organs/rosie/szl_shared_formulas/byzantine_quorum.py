#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
"""Byzantine quorum helper (n ≥ 3f+1) — Lamport / PBFT classic BFT bound.

a11oy uses this to decide whether the 5-organ mesh can tolerate ``f`` Byzantine
organs and what live-quorum (2f+1) is required to outvote them.

DEDUP NOTE: the canonical implementation lives in ``szl-holdings/uds-mesh``
(``src/mesh/quorum.py``, ADR-0001 canonical home, PR #73 lineage). If that package is
importable in the runtime we re-export its ``max_byzantine_faults`` / ``quorum_size``
so there is a single source of truth; otherwise we provide an identical, doctested
fallback (same math, same doctrine). No fabricated consensus is ever claimed — live
cluster polling is OUT OF SCOPE (heartbeats are injected by the caller).

Published form (thesis_v22.pdf §2 — "Byzantine quorum"): a mesh of ``n`` organs
tolerating ``f`` faults is BFT-feasible iff ``n ≥ 3f+1``; an agreement quorum needs
``≥ 2f+1`` live organs. Lamport, Shostak, Pease (1982) / PBFT (Castro–Liskov 1999).

Lean theorem: ``Lutar/KhipuConsensus.lean :: khipu_consensus_safety`` — this is
**Conjecture 2** (BFT safety), an HONEST open ``sorry`` obligation, NOT a closed
theorem (thesis_v22.pdf §1, §4). The arithmetic helpers below are runtime-doctested.

CITATION: thesis_v22.pdf §2  ·  LEAN: Lutar/KhipuConsensus.lean::khipu_consensus_safety (Conjecture 2, open)
"""
from __future__ import annotations

CITATION = "thesis_v22.pdf §2"
LEAN_THEOREM = "Lutar/KhipuConsensus.lean::khipu_consensus_safety (Conjecture 2, open obligation)"

# Prefer the canonical uds-mesh implementation (single source of truth).
try:  # pragma: no cover - import-path dependent
    from mesh.quorum import max_byzantine_faults as _mbf  # type: ignore
    from mesh.quorum import quorum_size as _qs

    _SOURCE = "uds-mesh (mesh.quorum)"
except Exception:  # pragma: no cover
    try:
        from quorum import max_byzantine_faults as _mbf  # type: ignore
        from quorum import quorum_size as _qs

        _SOURCE = "uds-mesh (quorum)"
    except Exception:
        _mbf = None
        _qs = None
        _SOURCE = "a11oy local fallback (identical math)"


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


def quorum_size(f: int) -> int:
    """Agreement quorum (2f+1) needed to outvote f Byzantine organs.

    >>> [quorum_size(f) for f in (0, 1, 2, 3)]
    [1, 3, 5, 7]
    """
    if _qs is not None:
        return _qs(f)
    return 2 * f + 1


def quorum_threshold(n: int, f: int | None = None) -> dict:
    """Honest-schema quorum decision for an n-organ mesh tolerating f faults."""
    if n < 1:
        raise ValueError("n must be >= 1")
    if f is None:
        f = max_byzantine_faults(n)
    if f < 0:
        raise ValueError("f must be >= 0")
    bft_feasible = n >= 3 * f + 1
    required = quorum_size(f)
    return {
        "value": required,
        "n": n,
        "f": f,
        "required_quorum": required,
        "bft_feasible": bft_feasible,
        "rule": "n >= 3f+1 ; quorum = 2f+1",
        "source": _SOURCE,
        "citation": CITATION,
        "lean_theorem": LEAN_THEOREM,
    }


__all__ = [
    "max_byzantine_faults",
    "quorum_size",
    "quorum_threshold",
    "CITATION",
    "LEAN_THEOREM",
]

if __name__ == "__main__":  # pragma: no cover
    import doctest

    fails, _ = doctest.testmod()
    print("✓ byzantine_quorum doctests passed" if fails == 0 else f"✗ {fails} failed")

# Doctrine v11 LOCKED — 749/14/163 — c7c0ba17 · Λ = Conjecture 1 (NEVER a theorem)
# SLSA L1 honest (cosign-signed; verifiable via cosign verify). L2 build-provenance attestation is roadmap (Wire D) — not yet earned.
