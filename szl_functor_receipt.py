"""
szl_functor_receipt.py — Compositional soundness property test for DSSE receipts

EMERALD CODEX ROUND 5 INSTILLATION: F-03 HERMES-FUNCTOR-RECEIPT
Primary source: S. Mac Lane, Categories for the Working Mathematician,
    2nd ed., Springer-Verlag, 1998, Chapter II.
    Also: Eilenberg & Mac Lane, Trans. AMS 58:231-294, 1945. DOI: 10.2307/1990284
Lean stub: https://github.com/szl-holdings/lutar-lean/blob/feat/innovations-round5/Lutar/Innovations/round5/HermesFunctorReceipt.lean
Lake receipt: https://github.com/szl-holdings/szl-lake/blob/main/attestations/innovations/round5/HermesFunctorReceipt.json
Doctrine: v11 LOCKED 749/14/163 · Λ = Conjecture 1 · lives in Innovations/round5/ outside locked kernel
Signed-off-by: Yachay <yachay@szlholdings.ai>
Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>

Mathematical guarantee (Mac Lane 1998, Ch.II — Functor axioms):
    A functor F : ActionMonoid → ReceiptMonoid must satisfy:
    1. F(id) = empty_receipt                     (identity preservation)
    2. F(a ∘ b) = chain(F(a), F(b))              (composition preservation)

This module provides a property-based test for the compositional soundness
of the DSSE receipt generation function. Any violation catches bugs in
receipt chaining (compositional receipt bugs are not detectable by individual
receipt validation alone).
"""

import hashlib
import json
import logging
from typing import Callable, Any

logger = logging.getLogger(__name__)


def receipt_hash(receipt: dict) -> str:
    """Canonical hash of a receipt (order-independent via sorted keys)."""
    return hashlib.sha256(
        json.dumps(receipt, sort_keys=True).encode()
    ).hexdigest()


def check_functor_identity(
    generate_receipt: Callable[[str], dict],
    empty_receipt: dict,
    id_action: str = "__identity__",
) -> bool:
    """
    Check functor identity law: F(id) = empty_receipt.
    Source: Mac Lane (1998), Ch.II, Functor axiom 1.
    """
    r = generate_receipt(id_action)
    ok = receipt_hash(r) == receipt_hash(empty_receipt)
    if not ok:
        logger.warning(
            f"[FUNCTOR-RECEIPT] Identity law VIOLATED: "
            f"F(id) hash={receipt_hash(r)[:8]} != empty hash={receipt_hash(empty_receipt)[:8]}. "
            f"Source: Mac Lane (1998) DOI:10.2307/1990284"
        )
    return ok


def check_functor_composition(
    generate_receipt: Callable[[str], dict],
    chain_receipts: Callable[[dict, dict], dict],
    compose_actions: Callable[[str, str], str],
    action_a: str,
    action_b: str,
) -> bool:
    """
    Check functor composition law: F(a . b) = chain(F(a), F(b)).
    Source: Mac Lane (1998), Ch.II, Functor axiom 2.
    """
    composed = generate_receipt(compose_actions(action_a, action_b))
    chained = chain_receipts(generate_receipt(action_a), generate_receipt(action_b))
    ok = receipt_hash(composed) == receipt_hash(chained)
    if not ok:
        logger.warning(
            f"[FUNCTOR-RECEIPT] Composition law VIOLATED for ({action_a}, {action_b}): "
            f"F(a.b) hash != chain(F(a),F(b)) hash. "
            f"Source: Mac Lane (1998) DOI:10.2307/1990284"
        )
    return ok
