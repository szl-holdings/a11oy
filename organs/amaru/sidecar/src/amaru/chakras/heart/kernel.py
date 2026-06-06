"""Heart chakra (anahata) — coherence / harm-avoidance kernel.

coherence = clamp(care - harm, 0, 1). Verdict is `open` when coherence
≥ 0.3, otherwise `guard`.
"""

from __future__ import annotations

from typing import Any, Mapping

STUBBED = False
NAME = "heart"


def evaluate(envelope: Mapping[str, Any]) -> dict[str, Any]:
    signals = envelope.get("signals", {}) or {}
    care = float(signals.get("care", 0.0))
    harm = float(signals.get("harm", 0.0))
    coherence = max(0.0, min(1.0, care - harm))
    return {
        "chakra": NAME,
        "coherence": coherence,
        "verdict": "open" if coherence >= 0.3 else "guard",
        "inputs": {"care": care, "harm": harm},
    }
