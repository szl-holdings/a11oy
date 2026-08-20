"""Throat chakra (vishuddha) — expressive fidelity kernel.

fidelity = clamp(sqrt(clarity * truth), 0, 1). Geometric mean penalises
one-sided expression. Verdict is `speak` at or above 0.5, otherwise
`hold`.
"""

from __future__ import annotations

import math
from typing import Any, Mapping

STUBBED = False
NAME = "throat"


def evaluate(envelope: Mapping[str, Any]) -> dict[str, Any]:
    signals = envelope.get("signals", {}) or {}
    clarity = max(0.0, float(signals.get("clarity", 0.0)))
    truth = max(0.0, float(signals.get("truth", 0.0)))
    fidelity = max(0.0, min(1.0, math.sqrt(clarity * truth)))
    return {
        "chakra": NAME,
        "fidelity": fidelity,
        "verdict": "speak" if fidelity >= 0.5 else "hold",
        "inputs": {"clarity": clarity, "truth": truth},
    }
