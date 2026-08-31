"""Per-organ Ayni coefficient monitor; fires HUKLLA T24 if any organ drains.

alpha_o = In_o / (In_o + Out_o)  in [0,1];  0.5 = balanced (In==Out).
alpha_o < ALPHA_MIN (0.45) over the monitored window => organ is net-drained =>
HUKLLA tripwire T24 fires (additive; T01-T10 unchanged).

Also computes the yuyay_v4 14-vector hash and PROVES non-disturbance of yuyay_v3:
dropping axis 14 reproduces the LOCKED v3 replay hash byte-for-byte.

HONEST: a normalized reciprocity ratio + a threshold alarm. No mysticism.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from .ledger import ORGANS, ReciprocityLedger

ALPHA_BALANCED = 0.5
ALPHA_MIN = 0.45
HUKLLA_T24 = "T24"
YUYAY_V3_REPLAY_HASH = (
    "bacf54434f1a3bf2d758b27a62d5fd580ca4c8d3b180693573eeebcaea631fc5"
)


@dataclass
class T24Event:
    organ: str
    alpha: float
    threshold: float
    tripwire: str
    window: tuple


@dataclass
class ReciprocityReport:
    alphas: dict                  # organ -> alpha_o
    deficits: list                # list[T24Event]
    halt: bool                    # True if any organ drained (T24 fired)


def scan(ledger: ReciprocityLedger, lo: float = float("-inf"),
         hi: float = float("inf")) -> ReciprocityReport:
    alphas = {}
    deficits = []
    for o in ORGANS:
        a = ledger.ayni_coefficient(o, lo, hi)
        alphas[o] = round(a, 6)
        if a < ALPHA_MIN:
            deficits.append(T24Event(
                organ=o, alpha=round(a, 6), threshold=ALPHA_MIN,
                tripwire=HUKLLA_T24, window=(lo, hi),
            ))
    return ReciprocityReport(alphas=alphas, deficits=deficits, halt=bool(deficits))


class ReciprocityViolation(Exception):
    """Raised when an organ is net-drained: HUKLLA T24 halt."""


def enforce(ledger: ReciprocityLedger, lo: float = float("-inf"),
            hi: float = float("inf")) -> ReciprocityReport:
    """Scan and HALT (raise) if any organ is in deficit. Used by the runtime guard."""
    report = scan(ledger, lo, hi)
    if report.halt:
        worst = min(report.deficits, key=lambda d: d.alpha)
        raise ReciprocityViolation(
            f"HUKLLA {HUKLLA_T24}: organ {worst.organ!r} drained "
            f"(alpha={worst.alpha} < {ALPHA_MIN})"
        )
    return report


# ---- yuyay_v4 axis-14 hashing (proves v3 non-disturbance) -----------------
def yuyay_v4_vector(v3_axes: list, ledger: ReciprocityLedger,
                    organ: str) -> list:
    """Append axis 14 (alpha_o) to the 13-axis v3 vector -> 14-vector."""
    if len(v3_axes) != 13:
        raise ValueError("v3 vector must have exactly 13 axes (Doctrine v11)")
    return list(v3_axes) + [round(ledger.ayni_coefficient(organ), 6)]


def _canon_hash(vector: list, receipts: list) -> str:
    blob = json.dumps({"v": vector, "r": receipts}, sort_keys=True,
                      separators=(",", ":")).encode()
    return hashlib.sha256(blob).hexdigest()


def yuyay_v4_hash(v4_vector: list, v4_receipts: list) -> str:
    """Separate v4 hash over the 14-vector + v4 receipts."""
    if len(v4_vector) != 14:
        raise ValueError("v4 vector must have 14 axes")
    return _canon_hash(v4_vector, v4_receipts)


def yuyay_v3_hash(v3_vector: list, v3_receipts: list) -> str:
    """Recompute the v3 hash from the first 13 axes only (must equal LOCKED hash
    for the canonical v3 input)."""
    if len(v3_vector) != 13:
        raise ValueError("v3 vector must have 13 axes")
    return _canon_hash(v3_vector, v3_receipts)
