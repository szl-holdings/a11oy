#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) Stephen P. Lutar Jr. (ORCID 0009-0001-0110-4173) - Doctrine v11 LOCKED
"""provenance_stub.py - signed-receipt schema for the sovereign fine-tune (szl-lake).

Emits a chain-of-title receipt describing a TRACK C training run: the input
corpora (sha256 + %synthetic), the base model sha, the LoRA/ORPO config, the
exported GGUF sha256, and the refusal-to-fabricate eval scores. This is the
record szl-lake ingests so a third party can re-verify what produced the weights.

DOCTRINE (honest by construction):
  * The weights' provenance is labelled MODELED until a REAL training run fills
    the gguf_sha256 and the eval scores. A stub receipt (no real run yet) is
    explicitly ``status="MODELED"`` / ``weights_provenance="MODELED"``; it never
    claims MEASURED eval numbers or a real signature.
  * %synthetic is computed HONESTLY from the corpora: the seed is derived from
    real in-tree text (hand-verifiable), the ORPO 'rejected' side is authored
    negative examples. We report the fraction, not a flattering rounding.
  * The DSSE-style ``signature`` block is a PLACEHOLDER unless a signing key is
    supplied - same honest posture as the a11oy Khipu receipt substrate
    (HONEST_DISCLOSURE.md): the hash chain (corpus/base/gguf sha256) is real; the
    cryptographic signature is absent (non_repudiation=false) without a key.

Pure standard library only. Deterministic given the same inputs.

Usage:
    # Stub receipt (no real run yet - provenance MODELED):
    python training/provenance_stub.py > training/provenance_receipt.json

    # After a real run, fill measured fields:
    python training/provenance_stub.py \
        --gguf-sha256 <sha> --base-sha256 <sha> \
        --eval training/eval_scores.json
"""
import argparse
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SEED = os.path.join(HERE, "szl_seed.jsonl")
ORPO = os.path.join(HERE, "szl_orpo.jsonl")
ORPO_EVAL = os.path.join(HERE, "szl_orpo_eval.jsonl")

SCHEMA_ID = "szl-lake/chain-of-title/sovereign-finetune@v1"


def _sha256_file(path):
    if not os.path.exists(path):
        return None
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def _count(path):
    if not os.path.exists(path):
        return 0
    with open(path, "r", encoding="utf-8") as fh:
        return sum(1 for line in fh if line.strip())


def _pct_synthetic():
    """Honest synthetic fraction of the training text.

    Seed rows are DERIVED from real in-tree text (counted as non-synthetic,
    hand-verifiable). ORPO 'rejected' strings are authored negative examples
    (counted as synthetic); 'chosen' strings are doctrine-grounded (non-synthetic).
    Returns (pct_synthetic, breakdown)."""
    seed_n = _count(SEED)
    orpo_n = _count(ORPO)
    # per ORPO pair: prompt + chosen (grounded) + rejected (synthetic negative)
    grounded = seed_n + orpo_n * 2   # seed rows + (prompt,chosen) per pair
    synthetic = orpo_n               # one authored 'rejected' per pair
    total = grounded + synthetic
    pct = round(100.0 * synthetic / total, 2) if total else 0.0
    return pct, {"grounded_units": grounded, "synthetic_units": synthetic,
                 "total_units": total}


def build_receipt(gguf_sha256=None, base_sha256=None, eval_scores=None,
                  lora_cfg=None):
    have_run = bool(gguf_sha256 and eval_scores)
    pct, syn_breakdown = _pct_synthetic()
    corpus = {
        "seed_jsonl": {"path": "training/szl_seed.jsonl",
                       "sha256": _sha256_file(SEED), "examples": _count(SEED)},
        "orpo_jsonl": {"path": "training/szl_orpo.jsonl",
                       "sha256": _sha256_file(ORPO), "pairs": _count(ORPO)},
        "orpo_eval_jsonl": {"path": "training/szl_orpo_eval.jsonl",
                            "sha256": _sha256_file(ORPO_EVAL),
                            "pairs": _count(ORPO_EVAL)},
        "pct_synthetic": pct,
        "synthetic_breakdown": syn_breakdown,
    }
    receipt = {
        "schema": SCHEMA_ID,
        "doctrine": "v11",
        "status": "MEASURED" if have_run else "MODELED",
        "weights_provenance": "MEASURED" if have_run else "MODELED",
        "corpus": corpus,
        "base_model_sha256": base_sha256,   # None until a real run records it
        "lora_orpo_cfg": lora_cfg or {
            "method": "QLoRA (nf4) + LoRA(all-linear) + ORPO",
            "cites": ["arXiv:2305.14314", "unsloth", "arXiv:2403.07691"],
            "note": "see training/train_sovereign.py DEFAULTS for the full config",
        },
        "gguf_sha256": gguf_sha256,          # None until export
        "eval": eval_scores or {
            "refusal_to_fabricate": None,
            "note": ("eval scores are UNAVAILABLE until a real run scores "
                     "training/szl_orpo_eval.jsonl; never fabricated"),
        },
        "signature": {
            "alg": "ecdsa-p256-dsse",
            "value": "PLACEHOLDER",
            "non_repudiation": False,
            "note": ("PLACEHOLDER unless a signing key is supplied; the corpus/"
                     "base/gguf sha256 hash chain is real regardless "
                     "(HONEST_DISCLOSURE.md)."),
        },
        "chain_of_title": [
            "corpus.seed_jsonl.sha256",
            "corpus.orpo_jsonl.sha256",
            "base_model_sha256",
            "lora_orpo_cfg",
            "gguf_sha256",
            "eval.refusal_to_fabricate",
        ],
    }
    return receipt


def main():
    ap = argparse.ArgumentParser(description="Emit the szl-lake chain-of-title receipt.")
    ap.add_argument("--gguf-sha256", default=None)
    ap.add_argument("--base-sha256", default=None)
    ap.add_argument("--eval", default=None,
                    help="path to a JSON file of measured eval scores")
    args = ap.parse_args()

    eval_scores = None
    if args.eval and os.path.exists(args.eval):
        with open(args.eval, "r", encoding="utf-8") as fh:
            eval_scores = json.load(fh)

    receipt = build_receipt(gguf_sha256=args.gguf_sha256,
                            base_sha256=args.base_sha256,
                            eval_scores=eval_scores)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
