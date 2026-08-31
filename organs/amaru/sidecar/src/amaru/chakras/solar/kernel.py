"""Solar chakra (manipura) — will / decisive action kernel.

Computes a will scalar = clamp(intent * agency - friction, 0, 1).
Verdict is `act` at or above 0.5, `defer` between 0.2 and 0.5, `block`
below 0.2.
"""

from __future__ import annotations

from typing import Any, Mapping

STUBBED = False
NAME = "solar"


def evaluate(envelope: Mapping[str, Any]) -> dict[str, Any]:
    signals = envelope.get("signals", {}) or {}
    intent = float(signals.get("intent", 0.0))
    agency = float(signals.get("agency", 0.0))
    friction = float(signals.get("friction", 0.0))
    will = max(0.0, min(1.0, intent * agency - friction))
    if will >= 0.5:
        verdict = "act"
    elif will >= 0.2:
        verdict = "defer"
    else:
        verdict = "block"
    return {
        "chakra": NAME,
        "will": will,
        "verdict": verdict,
        "inputs": {"intent": intent, "agency": agency, "friction": friction},
    }
