"""Root chakra (muladhara) — substrate grounding kernel.

Projects an envelope onto its grounding / integrity components and emits
a bounded stability scalar in [0, 1]. Verdict is `ground` at or above
0.5, otherwise `destabilize`.
"""

from __future__ import annotations

from typing import Any, Mapping

STUBBED = False
NAME = "root"


def evaluate(envelope: Mapping[str, Any]) -> dict[str, Any]:
    signals = envelope.get("signals", {}) or {}
    grounded = float(signals.get("grounded", 0.0))
    integrity = float(signals.get("integrity", 0.0))
    stability = max(0.0, min(1.0, 0.5 * (grounded + integrity)))
    return {
        "chakra": NAME,
        "stability": stability,
        "verdict": "ground" if stability >= 0.5 else "destabilize",
        "inputs": {"grounded": grounded, "integrity": integrity},
    }
