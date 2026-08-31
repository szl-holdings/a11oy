#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. -- SZL Holdings
# ORCID: 0009-0001-0110-4173
#
# szl_bls_aggregate.py -- AMARU cortex: BLS aggregate verification fast-path for
# cross-organ DSSE receipt chains.
#
# Frontier formula F3 (round11): BLS aggregate signatures.
#   Boneh-Lynch-Shacham, "Short signatures from the Weil pairing", J.Cryptology (2004).
#   Boneh-Drijvers-Neven, "BLS Multi-Signatures With Public-Key Aggregation" (2018):
#     https://crypto.stanford.edu/~dabo/pubs/papers/BLSmultisig
#   Eth2 Book 2.9.1: verify N aggregated sigs in 2 (same msg) or N+1 (distinct) pairings
#     instead of 2N: https://eth2book.info/latest/part2/building_blocks/signatures/
#
# Lean proof of the aggregation identity (sum of org sigs == summed-key sig):
#   szl-holdings/lutar-lean
#   Lutar/Innovations/round11/FrontierBLSAggregation.lean :: agg_sig_eq_agg_key_sig,
#   aggregate_verify, pairing_strict_savings
#
# Why this helps the running software:
#   amaru verifies a DSSE chain of N organ receipts (a11oy + sentra + amaru + killinchu).
#   Verifying each separately costs 2N pairings. When organs sign a common chain root,
#   BLS aggregation verifies the whole chain with TWO pairings (a 4-organ chain: 8 -> 2).
#   Pairings dominate cost; point additions are ~free -> sustained chain-verification
#   throughput goes UP.
#
# HONESTY: this is an ADDITIVE fast-path. It uses py_ecc (the Ethereum BLS reference) if
# available; if the optional dep is missing it returns an HONEST error and the caller
# falls back to the existing ECDSA receipt path (amaru/szl_dsse.py) -- never a fake
# "verified". The existing ECDSA receipts remain the source of truth until Sigstore CI
# signing is wired (Doctrine v11 honesty label).

from __future__ import annotations

from typing import Any


def _bls():
    """Lazy import of the BLS backend. Returns (module, None) or (None, error)."""
    try:
        from py_ecc.bls import G2ProofOfPossession as bls  # type: ignore
        return bls, None
    except Exception as exc:  # optional dep absent in this Space runtime
        return None, (
            f"py_ecc BLS backend unavailable ({exc.__class__.__name__}): "
            "falling back to per-receipt ECDSA verification (szl_dsse.verify_envelope). "
            "No fake 'verified' returned (Doctrine v11 honesty)."
        )


class BLSAggregateVerifier:
    """Aggregate-verify N organ DSSE signatures with O(1)/O(N) pairings.

    Two modes (mirroring the Lean theorems):
      * same-message (all organs sign the same chain root)  -> 2 pairings
      * distinct-message (each organ signs its own receipt) -> N+1 pairings
    vs the 2N pairings of naive per-signature verification.
    """

    def __init__(self) -> None:
        self.bls, self.err = _bls()

    @property
    def available(self) -> bool:
        return self.bls is not None

    def aggregate(self, signatures: list[bytes]) -> dict[str, Any]:
        """Aggregate per-organ signatures into one (group-sum in G1).

        Mirrors Lean `aggSig = sum_i (sk_i . h)`.
        """
        if not self.available:
            return {"ok": False, "honest_error": self.err}
        if not signatures:
            return {"ok": False, "honest_error": "no signatures to aggregate"}
        agg = self.bls.Aggregate(signatures)
        return {"ok": True, "aggregate_signature": agg, "n": len(signatures)}

    def verify_same_message(
        self, pubkeys: list[bytes], message: bytes, aggregate_signature: bytes
    ) -> dict[str, Any]:
        """Same chain root signed by all organs -> verify with two pairings.

        Mirrors Lean `aggregate_verify` (sigma == aggKeySig on the common message).
        """
        if not self.available:
            return {"ok": False, "honest_error": self.err}
        ok = self.bls.FastAggregateVerify(pubkeys, message, aggregate_signature)
        n = len(pubkeys)
        return {
            "ok": True,
            "verified": bool(ok),
            "mode": "same-message",
            "pairings_used": 2,
            "pairings_naive": 2 * n,
            "n_organs": n,
            "formula": "bls-aggregate-same-message",
            "lean_ref": "Lutar/Innovations/round11/FrontierBLSAggregation.lean",
        }

    def verify_distinct_messages(
        self, pubkeys: list[bytes], messages: list[bytes], aggregate_signature: bytes
    ) -> dict[str, Any]:
        """Each organ signs its own receipt -> verify with N+1 pairings."""
        if not self.available:
            return {"ok": False, "honest_error": self.err}
        if len(pubkeys) != len(messages):
            return {"ok": False, "honest_error": "pubkeys/messages length mismatch"}
        ok = self.bls.AggregateVerify(pubkeys, messages, aggregate_signature)
        n = len(pubkeys)
        return {
            "ok": True,
            "verified": bool(ok),
            "mode": "distinct-messages",
            "pairings_used": n + 1,
            "pairings_naive": 2 * n,
            "n_organs": n,
            "formula": "bls-aggregate-distinct-message",
            "lean_ref": "Lutar/Innovations/round11/FrontierBLSAggregation.lean",
        }


__all__ = ["BLSAggregateVerifier"]
