"""
collector/lambda_gate.py — the Λ-gate that vsp-otel applies to every span.

Layer 4 (Λ-gate exporter) of the SZL 7-layer architecture. Pure-stdlib so it runs
in the collector hot path with no heavy deps.

Λ over a span's A1–A5 axes (a11oy doctrine constant LAMBDA_FLOOR = 0.90):
  Λ(span) = geometric mean of the per-axis scores, clamped to [0,1].
Spans with Λ < LAMBDA_FLOOR are rejected (fail-closed).

Λ is **Conjecture 1**, never a theorem. The geometric-mean aggregation mirrors the
a11oy graph-Λ construction (Lutar/GraphLambda.lean) but Λ itself remains conjectural.

SPDX-License-Identifier: Apache-2.0
Author: Yachay (CTO authority) · Built by Perplexity Computer Agent · SZL Holdings
Doctrine v11 LOCKED — 749 / 14 / 163.
"""
from __future__ import annotations

import math
import os
from dataclasses import dataclass
from typing import Any

# a11oy doctrine constant — the production Λ floor for vsp-otel.
LAMBDA_FLOOR = float(os.environ.get("LAMBDA_FLOOR", "0.90"))

# A1–A5: the five axes the gate scores. (The full doctrine has A1–A14; the
# span-level Λ-gate uses the five measurable-at-span-time axes.)
A_AXES = (
    "a1_moral_grounding",
    "a2_measurability_honesty",
    "a3_epistemic_humility",
    "a4_harm_avoidance",
    "a5_logical_coherence",
)

# OTel attribute keys the gate reads, in priority order (snake_case SemConv first).
_AXIS_KEYS = {
    "a1_moral_grounding":      ("lambda.a1", "lambda.moral_grounding", "szl.a1"),
    "a2_measurability_honesty":("lambda.a2", "lambda.measurability_honesty", "szl.a2"),
    "a3_epistemic_humility":   ("lambda.a3", "lambda.epistemic_humility", "szl.a3"),
    "a4_harm_avoidance":       ("lambda.a4", "lambda.harm_avoidance", "szl.a4"),
    "a5_logical_coherence":    ("lambda.a5", "lambda.logical_coherence", "szl.a5"),
}

# Default axis value when an instrumented org omits an axis: the floor itself, so a
# silent span neither passes for free nor is unfairly rejected below the floor.
_DEFAULT_AXIS = LAMBDA_FLOOR


@dataclass
class GateResult:
    lambda_value: float
    axes: dict[str, float]
    passed: bool
    floor: float = LAMBDA_FLOOR

    def as_attributes(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "szl.mesh.lambda_value": f"{self.lambda_value:.6f}",
            "szl.mesh.governance_drift": not self.passed,
            "szl.lambda.floor": f"{self.floor:.2f}",
        }
        for k, v in self.axes.items():
            d[f"lambda.{k.split('_')[0]}"] = round(v, 6)
        return d


def _clamp01(x: float) -> float:
    return min(1.0, max(0.0, x))


def axes_from_attributes(attrs: dict[str, Any]) -> dict[str, float]:
    out: dict[str, float] = {}
    for axis, keys in _AXIS_KEYS.items():
        val = None
        for k in keys:
            if k in attrs:
                try:
                    val = float(attrs[k])
                    break
                except (TypeError, ValueError):
                    continue
        out[axis] = _clamp01(val) if val is not None else _DEFAULT_AXIS
    return out


def compute_lambda(axes: dict[str, float]) -> float:
    """Λ = geometric mean of the A1–A5 axes, clamped to [0,1] (Λ Conjecture 1)."""
    vals = [max(1e-12, axes[a]) for a in A_AXES]
    log_mean = sum(math.log(v) for v in vals) / len(vals)
    return _clamp01(math.exp(log_mean))


def evaluate(attrs: dict[str, Any], floor: float = LAMBDA_FLOOR) -> GateResult:
    axes = axes_from_attributes(attrs)
    lam = compute_lambda(axes)
    return GateResult(lambda_value=lam, axes=axes, passed=lam >= floor, floor=floor)
