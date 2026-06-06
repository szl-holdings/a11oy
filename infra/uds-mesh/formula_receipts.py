#!/usr/bin/env python3
# =====================================================================
# formula_receipts.py — DSSE PAE v1 + HMAC-SHA-256 receipt layer
#                       for the 5 anchor SZL formulas
# =====================================================================
#
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings
# ORCID: 0009-0001-0110-4173
#
# Doctrine v6 — Layer 5 of the 7-layer formula instillation.
#
# Receipt schema (per Doctrine v6 §DSSE):
#   {
#     formula:         str   — one of the 5 anchor formula names
#     inputs_hash:     str   — SHA-256 of canonical JSON inputs
#     output:          Any   — the scalar return value
#     lean_theorem:    str   — Lean theorem name (grep-verifiable)
#     lean_file:       str   — relative path in lutar-lean
#     lean_commit_sha: str   — lutar-lean@main commit SHA
#     timestamp:       str   — ISO-8601 UTC
#     signature:       str   — base64(HMAC-SHA-256(PAE(payload_type, payload)))
#   }
#
# DSSE PAE v1 encoding (https://github.com/secure-systems-lab/dsse):
#   PAE(type, payload) = "DSSEv1 " + len(type) + " " + type + " "
#                        + len(payload) + " " + payload
#
# HMAC key: env var FORMULA_HMAC_KEY (dev default: szl-formula-hmac-dev-v1)
#
# References:
#   DSSE spec: https://github.com/secure-systems-lab/dsse/blob/master/protocol.md
#   Rosie app.py: SZLHOLDINGS/rosie-operator-console (uses same PAE scheme)
#   uds_v18_24_substrate.py: SZL Holdings uds-mesh@main
# =====================================================================

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import math
import os
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any

# ── HMAC key (dev default matches rosie-operator-console) ────────────────────

_HMAC_KEY: bytes = os.environ.get(
    "FORMULA_HMAC_KEY", "szl-formula-hmac-dev-v1"
).encode()

# ── Lean anchor registry ──────────────────────────────────────────────────────

LEAN_COMMIT_SHA = "1dca00032dfc9aa8559cc6c2e4b63192fcf52371"

ANCHOR_REGISTRY: dict[str, dict[str, str]] = {
    "MadhavaBound": {
        "lean_theorem":    "madhavaRemainderBound_nonneg",
        "lean_file":       "Lutar/PACBayes/MadhavaBound.lean",
        "lean_blob_sha":   "c8c07dc93a5dbfd6350673065c81b50eb28b940b",
        "lean_commit_sha": LEAN_COMMIT_SHA,
    },
    "FalsePosition": {
        "lean_theorem":    "false_position_correct",
        "lean_file":       "Lutar/Calibration/FalsePosition.lean",
        "lean_blob_sha":   "8a6624ce183ede9d634f4d251f53c57f54ffaae4",
        "lean_commit_sha": LEAN_COMMIT_SHA,
    },
    "LiuHuiPi": {
        "lean_theorem":    "sideSquared_bounds",
        "lean_file":       "Lutar/Banach/LiuHuiPi.lean",
        "lean_blob_sha":   "3c98c3a608d2d204900737b72fac60e51025083b",
        "lean_commit_sha": LEAN_COMMIT_SHA,
    },
    "AdversarialRobustness": {
        "lean_theorem":    "robustness_preserved_by_composition",
        "lean_file":       "Lutar/Composition/AdversarialRobustness.lean",
        "lean_blob_sha":   "a96e448f83da40f06f005e7f8ff0492e0870e819",
        "lean_commit_sha": LEAN_COMMIT_SHA,
    },
    "SummationInvariant": {
        "lean_theorem":    "khipuReceipt_checksum_invariant",
        "lean_file":       "Lutar/Khipu/SummationInvariant.lean",
        "lean_blob_sha":   "a661e6b41d9f1f756f7746a83c3e5d9fbe11ba5c",
        "lean_commit_sha": LEAN_COMMIT_SHA,
    },
}

# ── DSSE PAE v1 helper ────────────────────────────────────────────────────────

PAYLOAD_TYPE = "application/vnd.szl.formula-receipt+json;v=1"


def _pae(payload_type: str, payload: bytes) -> bytes:
    """
    DSSE Pre-Authentication Encoding v1.
    PAE(type, payload) = "DSSEv1 " + len(type) + " " + type + " " + len(payload) + " " + payload
    Ref: https://github.com/secure-systems-lab/dsse/blob/master/protocol.md
    """
    pt = payload_type.encode("utf-8")
    return (
        b"DSSEv1 "
        + str(len(pt)).encode() + b" " + pt + b" "
        + str(len(payload)).encode() + b" " + payload
    )


def _b64url(b: bytes) -> str:
    return base64.b64encode(b).decode("ascii")


def _inputs_hash(inputs: Any) -> str:
    """SHA-256 of the canonical (sorted-key) JSON encoding of inputs."""
    canonical = json.dumps(inputs, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ── Receipt dataclass ─────────────────────────────────────────────────────────

@dataclass
class FormulaReceipt:
    formula:         str
    inputs_hash:     str
    output:          Any
    lean_theorem:    str
    lean_file:       str
    lean_commit_sha: str
    timestamp:       str
    signature:       str

    def to_dsse_envelope(self) -> dict:
        """
        Return a DSSE envelope wrapping this receipt.
        The payload is the receipt dict WITHOUT the signature field
        (signature is in the DSSE signatures array, not the payload body).
        Compatible with rosie-operator-console's dsse_verify_envelope().
        """
        receipt_body = {
            "formula":         self.formula,
            "inputs_hash":     self.inputs_hash,
            "output":          self.output,
            "lean_theorem":    self.lean_theorem,
            "lean_file":       self.lean_file,
            "lean_commit_sha": self.lean_commit_sha,
            "timestamp":       self.timestamp,
        }
        payload = json.dumps(receipt_body, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return {
            "payload":     _b64url(payload),
            "payloadType": PAYLOAD_TYPE,
            "signatures": [{
                "keyid": "szl-formula-hmac-sha256-v1",
                "sig":   self.signature,
            }],
        }

    @staticmethod
    def verify(envelope: dict, hmac_key: bytes = _HMAC_KEY) -> tuple[bool, str]:
        """Verify a DSSE envelope. Returns (valid, message)."""
        try:
            raw = base64.b64decode(envelope["payload"])
            pae = _pae(envelope["payloadType"], raw)
            for sig_entry in envelope.get("signatures", []):
                sig_bytes = base64.b64decode(sig_entry["sig"])
                expected = hmac.new(hmac_key, pae, hashlib.sha256).digest()
                if hmac.compare_digest(expected, sig_bytes):
                    return True, "HMAC-SHA-256 signature valid — PAE verified"
            return False, "No matching signature"
        except Exception as exc:
            return False, f"Verification error: {exc}"


# ── Formula implementations ───────────────────────────────────────────────────

def _madhava_bound(x: float, N: int) -> dict:
    """Mādhava arctan remainder bound. Lean: madhavaRemainderBound_nonneg."""
    if abs(x) > 1 + 1e-12:
        raise ValueError(f"|x| must be ≤ 1; got {abs(x)}")
    if N < 1:
        raise ValueError("N must be ≥ 1")
    partial = sum(
        ((-1) ** n) * (x ** (2 * n + 1)) / (2 * n + 1)
        for n in range(N)
    )
    remainder_bound = (abs(x) ** (2 * N + 1)) / (2 * N + 1)
    lambda_score = max(0.0, min(1.0, 1.0 - remainder_bound))
    return {"partial": partial, "remainder_bound": remainder_bound, "lambda_score": lambda_score}


def _false_position(x1: float, y1: float, x2: float, y2: float, T: float) -> dict:
    """False-position correction. Lean: false_position_correct."""
    dy = y2 - y1
    if abs(dy) < 1e-14 * max(abs(y1), abs(y2), 1):
        raise ValueError("Degenerate samples: y1 = y2")
    x_star = x1 + (T - y1) * (x2 - x1) / dy
    m = dy / (x2 - x1)
    c = y1 - m * x1
    residual = abs(m * x_star + c - T)
    lambda_score = max(0.0, 1.0 - residual / (1 + abs(T)))
    return {"x_star": x_star, "lambda_score": lambda_score}


def _liu_hui_pi(k: int) -> dict:
    """Liu Hui polygon π estimate. Lean: sideSquared_bounds, liuHuiPi."""
    if k < 0 or k > 50:
        raise ValueError("k must be in [0, 50]")
    sq = 1.0
    for _ in range(k):
        sq = 2.0 - math.sqrt(4.0 - sq)
    side_count = 6 * (2 ** k)
    pi_est = side_count * math.sqrt(sq) / 2.0
    abs_error = abs(pi_est - math.pi)
    lambda_score = max(0.0, 1.0 - abs_error / math.pi)
    return {"pi_estimate": pi_est, "side_count": side_count, "abs_error": abs_error, "lambda_score": lambda_score}


def _adversarial_robustness(l1: float, l2: float, delta: float) -> dict:
    """Adversarial robustness composition bound. Lean: robustness_preserved_by_composition."""
    if l1 <= 0 or l2 <= 0 or delta <= 0:
        raise ValueError("l1, l2, delta must all be > 0")
    eps1 = l1 * delta
    eps2 = l2 * eps1
    lambda_score = 1.0 / (1.0 + eps2)
    return {"epsilon1": eps1, "epsilon2": eps2, "composed_lipschitz": l1 * l2, "lambda_score": lambda_score}


def _summation_invariant(organs: list[dict], primary_cord: int) -> dict:
    """Khipu summation invariant. Lean: khipuReceipt_checksum_invariant."""
    pendant_values = [sum(d["value"] for d in o["decisions"]) for o in organs]
    computed_total = sum(pendant_values)
    invariant_holds = computed_total == primary_cord
    return {
        "pendant_values": pendant_values,
        "computed_total": computed_total,
        "invariant_holds": invariant_holds,
        "lambda_score": 1 if invariant_holds else 0,
    }


# ── Receipt factory ───────────────────────────────────────────────────────────

def _sign_payload(payload_bytes: bytes, hmac_key: bytes = _HMAC_KEY) -> str:
    pae = _pae(PAYLOAD_TYPE, payload_bytes)
    sig = hmac.new(hmac_key, pae, hashlib.sha256).digest()
    return _b64url(sig)


def emit_formula_receipt(
    formula: str,
    inputs: Any,
    hmac_key: bytes = _HMAC_KEY,
) -> tuple[FormulaReceipt, dict]:
    """
    Run the named formula with the given inputs and emit a DSSE receipt.

    Parameters
    ----------
    formula : str
        One of the 5 anchor formula names.
    inputs : Any
        Dict of formula inputs (must be JSON-serialisable).
    hmac_key : bytes
        HMAC key for signing (default: env FORMULA_HMAC_KEY or dev default).

    Returns
    -------
    (FormulaReceipt, dsse_envelope)
    """
    if formula not in ANCHOR_REGISTRY:
        raise ValueError(f"Unknown formula: {formula!r}. Valid: {list(ANCHOR_REGISTRY)}")

    anchor = ANCHOR_REGISTRY[formula]

    # Dispatch to the inline implementation
    if formula == "MadhavaBound":
        output = _madhava_bound(**inputs)
    elif formula == "FalsePosition":
        output = _false_position(**inputs)
    elif formula == "LiuHuiPi":
        output = _liu_hui_pi(**inputs)
    elif formula == "AdversarialRobustness":
        output = _adversarial_robustness(**inputs)
    elif formula == "SummationInvariant":
        output = _summation_invariant(**inputs)
    else:
        raise RuntimeError(f"Dispatch not implemented for {formula}")

    ts = datetime.now(timezone.utc).isoformat()
    ih = _inputs_hash(inputs)

    # Build the receipt (without signature first to compute payload)
    receipt_dict = {
        "formula":         formula,
        "inputs_hash":     ih,
        "output":          output,
        "lean_theorem":    anchor["lean_theorem"],
        "lean_file":       anchor["lean_file"],
        "lean_commit_sha": anchor["lean_commit_sha"],
        "timestamp":       ts,
    }
    payload_bytes = json.dumps(receipt_dict, sort_keys=True, separators=(",", ":")).encode("utf-8")
    sig = _sign_payload(payload_bytes, hmac_key)

    receipt = FormulaReceipt(
        formula=formula,
        inputs_hash=ih,
        output=output,
        lean_theorem=anchor["lean_theorem"],
        lean_file=anchor["lean_file"],
        lean_commit_sha=anchor["lean_commit_sha"],
        timestamp=ts,
        signature=sig,
    )
    return receipt, receipt.to_dsse_envelope()


# ── Self-test / demo ──────────────────────────────────────────────────────────

def _selftest() -> None:
    """Run one receipt per anchor formula and verify each envelope. Exit 0 on pass."""
    test_cases: list[tuple[str, dict]] = [
        ("MadhavaBound",          {"x": 1.0, "N": 10}),
        ("FalsePosition",         {"x1": 0.0, "y1": 0.0, "x2": 1.0, "y2": 2.0, "T": 4.0}),
        ("LiuHuiPi",              {"k": 4}),
        ("AdversarialRobustness", {"l1": 2.0, "l2": 3.0, "delta": 0.1}),
        ("SummationInvariant",    {
            "organs": [
                {"organId": "o1", "decisions": [{"decisionId": "d1", "value": 10}, {"decisionId": "d2", "value": 20}]},
                {"organId": "o2", "decisions": [{"decisionId": "d3", "value": 5}]},
            ],
            "primary_cord": 35,
        }),
    ]

    all_pass = True
    for formula, inputs in test_cases:
        receipt, envelope = emit_formula_receipt(formula, inputs)
        valid, msg = FormulaReceipt.verify(envelope)
        status = "PASS" if valid else "FAIL"
        if not valid:
            all_pass = False
        print(f"[{status}] {formula}: {msg} | Λ={receipt.output.get('lambda_score', '?'):.4f}")

    if not all_pass:
        raise SystemExit(1)
    print("\n✓ All 5 formula receipts verified (DSSE PAE v1 + HMAC-SHA-256)")


if __name__ == "__main__":
    _selftest()
