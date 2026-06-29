# SPDX-License-Identifier: Apache-2.0
# © Stephen P. Lutar Jr. (ORCID 0009-0001-0110-4173) · Doctrine v11 LOCKED
"""szl_e8 — E8-lattice ENCODING + verification layer over receipt digests.

Maps a 256-bit receipt digest (sha3_256 hex, schema szl.lake.receipt/v1) to eight
32-bit lattice coordinates, then snaps/verifies that 8-vector against the E8 lattice
using the Conway & Sloane closest-point algorithm (decode-to-D8 and decode-to-D8+glue,
pick the nearer). Reports lattice membership, the nearest lattice point, and the
minimum squared distance — i.e. error-DETECTION geometry over the receipt ledger.

E8 is the unique even unimodular lattice in R^8: the set of all integer-or-half-integer
8-vectors whose coordinates are all-integer or all-half-integer AND sum to an even
integer (D8 ∪ (D8 + glue), glue = (1/2,...,1/2)). Kissing number 240; minimal squared
distance 2.

────────────────────────────────────────────────────────────────────────────────────
DO NOT CLAIM (doctrine v11 — read twice)
────────────────────────────────────────────────────────────────────────────────────
WHAT WE MAY HONESTLY CITE:
  • The OPTIMALITY of E8 as the densest sphere packing in R^8 was PROVEN by Maryna
    Viazovska (2016, Annals of Mathematics) — a Fields-Medal result — and was later
    FORMALIZED / machine-checked in Lean (EPFL/Viazovska formalization). Our receipt
    encoding uses the E8 lattice, whose optimality is machine-checked (Viazovska 2016).
  • This is an EXTERNAL proof we CITE as prior art for the encoding geometry.

WHAT WE MUST NOT CLAIM:
  • The Viazovska proof is NOT ours. We cite it; we did not produce it.
  • E8 gives SPHERE-PACKING / minimum-distance error-DETECTION geometry ONLY.
  • E8 does NOT give adversarial-substitution resistance, tamper-proofing, or BFT
    safety. Adversarial substitution is Conjecture 2 (Khipu BFT) — NOT proven.
  • This module adds ZERO to the locked-proven count (which stays 8). It is an
    engineering encoding citing an external proof — not a new theorem of ours.
  • Λ = Conjecture 1. Never a theorem.
────────────────────────────────────────────────────────────────────────────────────
"""
from __future__ import annotations

import hashlib
from typing import Any

try:
    import numpy as np
    _NUMPY = True
except Exception:  # pragma: no cover - guarded; callers degrade honestly
    np = None  # type: ignore
    _NUMPY = False

SCHEMA = "szl.a11oy.e8.block/v1"
GLUE = 0.5  # E8 glue-vector coordinate: (1/2, 1/2, ..., 1/2)
DIM = 8
COORD_BITS = 32
E8_MIN_SQ_DISTANCE = 2  # minimal squared distance (kissing number 240)

DO_NOT_CLAIM = {
    "may_cite": (
        "E8 optimality (densest sphere packing in R^8) was PROVEN by Viazovska (2016, "
        "Annals of Math) and FORMALIZED in Lean (EPFL/Viazovska formalization) — a "
        "machine-checked, Fields-Medal-level result. We CITE it as prior art for the "
        "encoding geometry."
    ),
    "must_not_claim": [
        "The Viazovska proof is NOT ours — cited, not produced here.",
        "E8 gives sphere-packing / minimum-distance error-DETECTION geometry ONLY.",
        "E8 does NOT give adversarial-substitution resistance, tamper-proofing, or BFT "
        "safety. Adversarial substitution = Conjecture 2 (Khipu BFT), NOT proven.",
        "This encoding adds ZERO to the locked-proven count (stays 8).",
        "Λ = Conjecture 1, never a theorem.",
    ],
    "citation": (
        "M. Viazovska, 'The sphere packing problem in dimension 8', Annals of "
        "Mathematics 185 (2017), 991-1015. Lean formalization: EPFL/Viazovska."
    ),
}


def _require_numpy() -> None:
    if not _NUMPY:
        raise RuntimeError("numpy unavailable — E8 layer degrades honestly (no fabrication)")


def normalize_digest(digest_or_receipt: Any) -> str:
    """Accept a hex digest string or a receipt-like dict and return a 64-char sha3_256 hex.

    A receipt dict may carry the digest under 'chain_head', 'digest', 'sha3_256',
    'receipt_digest', or 'hash'. Any other value is sha3_256-hashed deterministically so
    the caller always gets a 256-bit digest to encode (never fabricated — derived).
    """
    if isinstance(digest_or_receipt, dict):
        for k in ("chain_head", "digest", "sha3_256", "receipt_digest", "hash"):
            v = digest_or_receipt.get(k)
            if isinstance(v, str) and v:
                digest_or_receipt = v
                break
        else:
            import json
            blob = json.dumps(digest_or_receipt, sort_keys=True,
                              separators=(",", ":"), ensure_ascii=False).encode("utf-8")
            return hashlib.sha3_256(blob).hexdigest()
    s = str(digest_or_receipt).strip().lower()
    if s.startswith("0x"):
        s = s[2:]
    # If it is already a 64-char hex digest, use it verbatim; otherwise hash to 256 bits.
    if len(s) == 64 and all(c in "0123456789abcdef" for c in s):
        return s
    return hashlib.sha3_256(s.encode("utf-8")).hexdigest()


def digest_to_coords(digest_or_receipt: Any):
    """Map a 256-bit digest to eight 32-bit integer lattice coordinates.

    Splits the 64 hex chars into 8 groups of 8 hex digits; each group is one unsigned
    32-bit integer coordinate of the encoded 8-vector.
    """
    _require_numpy()
    hexd = normalize_digest(digest_or_receipt)
    coords = [int(hexd[i:i + 8], 16) for i in range(0, 64, 8)]
    return np.asarray(coords, dtype=np.float64)


def _decode_Dn(x):
    """Closest point of the checkerboard lattice D_n (integer vectors, even coord-sum).

    Conway & Sloane: round each coord; if the rounded sum is even we are done, else flip
    the single worst-rounded coordinate the other way (changes parity by ±1).
    """
    f = np.round(x)
    if int(round(float(f.sum()))) % 2 == 0:
        return f
    delta = x - f
    i = int(np.argmax(np.abs(delta)))
    g = f.copy()
    g[i] = g[i] + 1.0 if delta[i] >= 0 else g[i] - 1.0
    return g


def closest_e8_point(x):
    """Closest E8 lattice point to x and its squared distance (Conway & Sloane).

    E8 = D8 ∪ (D8 + glue). Decode x to D8, decode (x - glue) to D8 then add glue back,
    and return whichever candidate is nearer to x.
    """
    _require_numpy()
    x = np.asarray(x, dtype=np.float64)
    y0 = _decode_Dn(x)
    d0 = float(np.sum((x - y0) ** 2))
    y1 = _decode_Dn(x - GLUE) + GLUE
    d1 = float(np.sum((x - y1) ** 2))
    return (y0, d0) if d0 <= d1 else (y1, d1)


def on_e8(p, tol: float = 1e-9) -> bool:
    """True iff p is exactly an E8 lattice point (all-integer or all-half-integer, even sum)."""
    _require_numpy()
    p = np.asarray(p, dtype=np.float64)
    # all-integer branch
    r = np.round(p)
    if np.all(np.abs(p - r) < tol) and int(round(float(p.sum()))) % 2 == 0:
        return True
    # all-half-integer branch (each coord in Z + 1/2)
    h = np.round(p - GLUE) + GLUE
    s = float(p.sum())
    if (np.all(np.abs(p - h) < tol) and abs(s - round(s)) < tol
            and int(round(s)) % 2 == 0):
        return True
    return False


def verify(digest_or_receipt: Any) -> dict:
    """Encode a digest to its E8 block and verify lattice membership + min-distance.

    Returns the encoded coordinates, the nearest E8 lattice point, the minimum squared
    distance (error-DETECTION metric), and an honest membership/interpretation. Pure
    sphere-packing geometry — NOT adversarial / tamper-proof (see DO_NOT_CLAIM).
    """
    if not _NUMPY:
        return {
            "schema": SCHEMA,
            "status": "DEGRADED",
            "label": "ROADMAP — numpy unavailable in this build; E8 layer offline",
            "fabricated": False,
            "do_not_claim": DO_NOT_CLAIM,
        }
    digest = normalize_digest(digest_or_receipt)
    coords = digest_to_coords(digest)
    nearest, sq_dist = closest_e8_point(coords)
    member = bool(on_e8(coords))
    return {
        "schema": SCHEMA,
        "digest": digest,
        "digest_alg": "sha3_256",
        "encoding": {
            "dim": DIM,
            "coord_bits": COORD_BITS,
            "scheme": "64 hex chars split into 8 × 8-hex (32-bit) unsigned int coordinates",
            "coords": [int(c) for c in coords.tolist()],
        },
        "lattice": "E8",
        "lattice_def": ("integer-or-half-integer 8-vectors, all-integer or all-half-integer, "
                        "with even coordinate sum — D8 ∪ (D8 + glue), glue=(1/2,...,1/2)"),
        "nearest_lattice_point": [float(v) for v in nearest.tolist()],
        "min_squared_distance": sq_dist,
        "min_distance": float(sq_dist) ** 0.5,
        "e8_min_squared_distance": E8_MIN_SQ_DISTANCE,
        "on_lattice": member,
        "error_detection": {
            "is_member": member,
            "interpretation": (
                "min_squared_distance == 0 ⇒ the encoded 8-vector lies exactly on E8 "
                "(lattice member). Otherwise it is off-lattice by the reported distance; "
                "E8's minimal squared distance (2) is the error-DETECTION separation between "
                "distinct codepoints. This is sphere-packing geometry — error DETECTION only."
            ),
        },
        "algorithm": "Conway & Sloane E8 closest-point (decode D8 and D8+glue, pick nearer)",
        "do_not_claim": DO_NOT_CLAIM,
    }


def encode_receipt(receipt: dict) -> dict:
    """Attach an E8 block + its lattice-distance to a receipt (additive, non-mutating)."""
    out = dict(receipt) if isinstance(receipt, dict) else {"value": receipt}
    out["e8"] = verify(receipt)
    return out


if __name__ == "__main__":  # pragma: no cover
    import json
    sample = "d0361e9f2c8d8ac96a1cdab46a6f45de3ed697a9e767d7ccccce2d69b60ae73c"
    print(json.dumps(verify(sample), indent=2))
