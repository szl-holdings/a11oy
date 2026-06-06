"""Crown chakra (sahasrara) — closure / ouroboros kernel.

Aggregates upstream scalar readings into a single closure ∈ [0, 1]
(arithmetic mean over the numeric values supplied under
`envelope.upstream`). Emits the ouroboros handoff back to `root`.
"""

from __future__ import annotations

from typing import Any, Mapping

STUBBED = False
NAME = "crown"


def evaluate(envelope: Mapping[str, Any]) -> dict[str, Any]:
    upstream = envelope.get("upstream", {}) or {}
    scalars = [float(v) for v in upstream.values() if isinstance(v, (int, float))]
    if scalars:
        closure = max(0.0, min(1.0, sum(scalars) / len(scalars)))
    else:
        closure = 0.0
    return {
        "chakra": NAME,
        "closure": closure,
        "verdict": "close" if closure >= 0.5 else "spin",
        "n_upstream_scalars": len(scalars),
        "handoff": {"to": "root", "via": "ouroboros"},
    }
