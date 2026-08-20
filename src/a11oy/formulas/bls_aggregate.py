#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
"""BLS12-381 aggregate signatures (py_ecc) over the Khipu receipt chain.

a11oy verifies a DSSE chain of N organ receipts. Verifying each separately costs 2N
pairings; when organs sign a common chain root, BLS aggregation verifies the whole chain
with TWO pairings (a 5-organ chain: 10 → 2). Pairings dominate cost; point additions are
~free → sustained chain-verification throughput goes UP.

Published form (thesis_v22.pdf §2, formula table — "BLS aggregate"):
    bilinear pairing e: G₁×G₂→G_T ; aggregate-verify N sigs in 2 (same msg) or N+1
    (distinct) pairings. Boneh–Lynn–Shacham (2001/2004); Boneh–Drijvers–Neven (2018).

Lean theorems (round11, on-branch PR #179): ``Lutar/Innovations/round11/
FrontierBLSAggregation.lean :: agg_sig_eq_agg_key_sig, aggregate_verify,
pairing_strict_savings``.

HONESTY: real implementation via ``py_ecc`` (Ethereum BLS reference, BLS12-381). If the
optional dep is missing the module returns an HONEST error and the caller falls back to
the existing ECDSA receipt path — NEVER a fake "verified". ECDSA receipts remain the
source of truth until Sigstore CI signing is wired (Doctrine v11 honesty label).

CITATION: thesis_v22.pdf §2  ·  LEAN: Lutar/Innovations/round11/FrontierBLSAggregation.lean::aggregate_verify
"""
from __future__ import annotations

from typing import Any

CITATION = "thesis_v22.pdf §2"
LEAN_THEOREM = "Lutar/Innovations/round11/FrontierBLSAggregation.lean::aggregate_verify"


def _bls():
    try:
        from py_ecc.bls import G2ProofOfPossession as bls  # type: ignore

        return bls, None
    except Exception as exc:  # optional dep absent
        return None, (
            f"py_ecc BLS12-381 backend unavailable ({exc.__class__.__name__}): "
            "falling back to per-receipt ECDSA verification. No fake 'verified' "
            "returned (Doctrine v11 honesty)."
        )


class BLSAggregate:
    """Aggregate-verify N organ DSSE signatures with O(1)/O(N) pairings over BLS12-381."""

    def __init__(self) -> None:
        self.bls, self.err = _bls()

    @property
    def available(self) -> bool:
        return self.bls is not None

    def keygen(self, ikm: bytes) -> dict[str, Any]:
        if not self.available:
            return {"ok": False, "honest_error": self.err}
        sk = self.bls.KeyGen(ikm)
        return {"ok": True, "sk": sk, "pk": self.bls.SkToPk(sk)}

    def sign(self, sk: int, message: bytes) -> dict[str, Any]:
        if not self.available:
            return {"ok": False, "honest_error": self.err}
        return {"ok": True, "signature": self.bls.Sign(sk, message)}

    def aggregate(self, signatures: list[bytes]) -> dict[str, Any]:
        if not self.available:
            return {"ok": False, "honest_error": self.err}
        if not signatures:
            return {"ok": False, "honest_error": "no signatures to aggregate"}
        return {"ok": True, "aggregate_signature": self.bls.Aggregate(signatures),
                "n": len(signatures)}

    def verify_same_message(
        self, pubkeys: list[bytes], message: bytes, aggregate_signature: bytes
    ) -> dict[str, Any]:
        if not self.available:
            return {"ok": False, "honest_error": self.err}
        ok = self.bls.FastAggregateVerify(pubkeys, message, aggregate_signature)
        n = len(pubkeys)
        return {
            "ok": True,
            "value": bool(ok),
            "verified": bool(ok),
            "mode": "same-message",
            "pairings_used": 2,
            "pairings_naive": 2 * n,
            "n_organs": n,
            "citation": CITATION,
            "lean_theorem": LEAN_THEOREM,
        }

    def verify_distinct_messages(
        self, pubkeys: list[bytes], messages: list[bytes], aggregate_signature: bytes
    ) -> dict[str, Any]:
        if not self.available:
            return {"ok": False, "honest_error": self.err}
        if len(pubkeys) != len(messages):
            return {"ok": False, "honest_error": "pubkeys/messages length mismatch"}
        ok = self.bls.AggregateVerify(pubkeys, messages, aggregate_signature)
        n = len(pubkeys)
        return {
            "ok": True,
            "value": bool(ok),
            "verified": bool(ok),
            "mode": "distinct-messages",
            "pairings_used": n + 1,
            "pairings_naive": 2 * n,
            "n_organs": n,
            "citation": CITATION,
            "lean_theorem": LEAN_THEOREM,
        }


__all__ = ["BLSAggregate", "CITATION", "LEAN_THEOREM"]

# Doctrine v11 LOCKED — 749/14/163 — c7c0ba17 · Λ = Conjecture 1 (NEVER a theorem)
# SLSA L1 honest. L2 build-provenance attestation = roadmap (Wire D) — not yet claimed. L3 not claimed.
