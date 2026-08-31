"""Sacral chakra (svadhisthana) — generative flow kernel.

Convex blend of `fluency` (weight 0.6) and `novelty` (weight 0.4),
clamped to [0, 1]. Verdict is `generate` at or above 0.4, otherwise
`rest`.
"""

from __future__ import annotations

from typing import Any, Mapping

STUBBED = False
NAME = "sacral"


def evaluate(envelope: Mapping[str, Any]) -> dict[str, Any]:
    signals = envelope.get("signals", {}) or {}
    novelty = float(signals.get("novelty", 0.0))
    fluency = float(signals.get("fluency", 0.0))
    flow = max(0.0, min(1.0, 0.6 * fluency + 0.4 * novelty))
    return {
        "chakra": NAME,
        "flow": flow,
        "verdict": "generate" if flow >= 0.4 else "rest",
        "inputs": {"novelty": novelty, "fluency": fluency},
    }
