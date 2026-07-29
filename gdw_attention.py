"""Governed Delta Workspace attention-route policy and eager Torch dispatcher.

The HTTP service uses the deterministic policy below. The optional Torch router is
an executable research hook; it is not loaded unless a caller explicitly uses it.
"""

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional


ROUTE_NAMES = ("kda_local", "laguna_hybrid", "mla_global")
ROUTE_IDS = {name: route_id for route_id, name in enumerate(ROUTE_NAMES)}


@dataclass(frozen=True)
class AttentionFeatures:
    novelty: float
    disagreement: float
    risk: float
    context_tokens: int
    active_tool_count: int
    memory_pressure: float


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def choose_attention_mode(
    features: AttentionFeatures,
    mode_hint: str = "auto",
) -> Dict[str, Any]:
    """Choose a governed local, mixed, or global attention budget."""
    if mode_hint in ROUTE_NAMES:
        probabilities = {name: 1.0 if name == mode_hint else 0.0 for name in ROUTE_NAMES}
        return {
            "mode": mode_hint,
            "score": None,
            "probabilities": probabilities,
            "reason": "explicit_validated_hint",
        }

    context = _clamp(features.context_tokens / 32768.0)
    tools = _clamp(features.active_tool_count / 16.0)
    memory = _clamp(features.memory_pressure)
    score = _clamp(
        0.20 * _clamp(features.novelty)
        + 0.25 * _clamp(features.disagreement)
        + 0.30 * _clamp(features.risk)
        + 0.15 * context
        + 0.10 * tools
        - 0.25 * memory
    )

    if memory >= 0.85:
        mode = "kda_local"
        reason = "memory_pressure_guard"
    elif score < 0.33:
        mode = "kda_local"
        reason = "bounded_local_budget"
    elif score < 0.66:
        mode = "laguna_hybrid"
        reason = "mixed_local_global_budget"
    else:
        mode = "mla_global"
        reason = "global_context_budget"

    centers = (0.16, 0.50, 0.84)
    weights = [max(0.0, 1.0 - abs(score - center) / 0.5) for center in centers]
    total = sum(weights) or 1.0
    probabilities = {
        name: round(weight / total, 6)
        for name, weight in zip(ROUTE_NAMES, weights)
    }
    return {
        "mode": mode,
        "score": round(score, 6),
        "probabilities": probabilities,
        "reason": reason,
    }


try:
    import torch
    from torch import nn
except Exception:
    torch = None
    nn = None


if nn is not None:

    class HybridAttentionRouter(nn.Module):
        """Trainable eager-mode KDA/Laguna/MLA route selector."""

        def __init__(self, d_model: int):
            super().__init__()
            if d_model <= 0:
                raise ValueError("d_model must be positive")
            self.mode_proj = nn.Linear(d_model, 3)

        def forward(self, summary_state):
            logits = self.mode_proj(summary_state)
            probabilities = torch.softmax(logits, dim=-1)
            return probabilities.argmax(dim=-1), probabilities

else:

    class HybridAttentionRouter:
        def __init__(self, d_model: int):
            raise RuntimeError("Torch is required for HybridAttentionRouter")


def hybrid_attention_dispatch(
    mode,
    x,
    kda_fn: Callable,
    mla_fn: Callable,
    laguna_fn: Callable,
):
    """Batch samples by route before dispatch to reduce per-sample divergence."""
    if torch is None:
        raise RuntimeError("Torch is required for hybrid_attention_dispatch")
    if mode.ndim != 1 or mode.shape[0] != x.shape[0]:
        raise ValueError("mode must be a one-dimensional tensor matching batch size")

    output: Optional[Any] = None
    route_functions = {
        "kda_local": kda_fn,
        "laguna_hybrid": laguna_fn,
        "mla_global": mla_fn,
    }
    for route_name in ROUTE_NAMES:
        route_id = ROUTE_IDS[route_name]
        route_fn = route_functions[route_name]
        indexes = torch.nonzero(mode == route_id, as_tuple=False).flatten()
        if indexes.numel() == 0:
            continue
        routed = route_fn(x.index_select(0, indexes))
        if output is None:
            output = torch.empty(
                (x.shape[0],) + tuple(routed.shape[1:]),
                dtype=routed.dtype,
                device=routed.device,
            )
        output.index_copy_(0, indexes, routed)
    if output is None:
        raise ValueError("mode contains no valid route ids")
    return output
