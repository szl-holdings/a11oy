"""Third-eye chakra (ajna) — predictive insight kernel.

insight = clamp(pattern_strength * (1 - uncertainty), 0, 1). Verdict is
`foresee` at or above 0.5, `peek` between 0.25 and 0.5, `blind` below.
"""

from __future__ import annotations

from typing import Any, Mapping

STUBBED = False
NAME = "third_eye"


def evaluate(envelope: Mapping[str, Any]) -> dict[str, Any]:
    signals = envelope.get("signals", {}) or {}
    pattern = float(signals.get("pattern_strength", 0.0))
    uncertainty = max(0.0, min(1.0, float(signals.get("uncertainty", 0.0))))
    insight = max(0.0, min(1.0, pattern * (1.0 - uncertainty)))
    if insight >= 0.5:
        verdict = "foresee"
    elif insight >= 0.25:
        verdict = "peek"
    else:
        verdict = "blind"
    return {
        "chakra": NAME,
        "insight": insight,
        "verdict": verdict,
        "inputs": {"pattern_strength": pattern, "uncertainty": uncertainty},
    }
