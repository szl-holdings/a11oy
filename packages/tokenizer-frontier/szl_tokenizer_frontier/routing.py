from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class IngressNode:
    node_id: str
    tokenizer_bytes_per_second: float
    cache_warmth: float
    cpu_ingress: float
    prefill_capacity: float
    health: str = "REACHABLE"


@dataclass(frozen=True)
class IngressRequest:
    prefix_heavy: bool = False
    corpus_heavy: bool = False
    prefill_heavy: bool = False


def rank_ingress(nodes: Iterable[IngressNode], request: IngressRequest) -> dict:
    eligible = [node for node in nodes if node.health in {"VERIFIED", "REACHABLE"}]
    if not eligible:
        return {"state": "UNAVAILABLE", "reason": "no healthy ingress node"}

    def score(node: IngressNode) -> float:
        result = 0.0
        if request.prefix_heavy:
            result += 0.40 * node.cache_warmth + 0.30 * node.cpu_ingress
        if request.corpus_heavy:
            result += 0.45 * node.tokenizer_bytes_per_second + 0.25 * node.cpu_ingress
        if request.prefill_heavy:
            result += 0.40 * node.prefill_capacity + 0.20 * node.cache_warmth
        return result

    ranked = sorted(((score(node), node) for node in eligible), key=lambda item: (-item[0], item[1].node_id))
    best_score, best = ranked[0]
    return {
        "state": "VERIFIED",
        "node_id": best.node_id,
        "routing_score_v1": round(best_score, 6),
        "candidates": [
            {"node_id": node.node_id, "score": round(value, 6)}
            for value, node in ranked
        ],
        "limitation": "routing_score_v1 is an operational heuristic, not the owner-authored RVO",
    }
