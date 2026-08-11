from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from .benchmark import BenchmarkResult


STAGE_ORDER = (
    "corpus_prep",
    "retrieval_indexing",
    "batch_prefill",
    "interactive",
)


@dataclass(frozen=True)
class PromotionDecision:
    state: str
    promotable: bool
    stage: str
    reasons: tuple[str, ...]

    def record(self) -> dict:
        return {
            "schema": "szl.tokenizer-promotion-decision/v1",
            "state": self.state,
            "promotable": self.promotable,
            "stage": self.stage,
            "reasons": list(self.reasons),
        }


def decide_promotion(
    *,
    stage: str,
    candidate: BenchmarkResult,
    oracle: BenchmarkResult,
    prior_stage_receipts: Mapping[str, str] | None = None,
    minimum_speedup: float = 1.0,
) -> PromotionDecision:
    if stage not in STAGE_ORDER:
        raise ValueError(f"unsupported promotion stage: {stage}")
    if minimum_speedup < 1.0:
        raise ValueError("minimum_speedup cannot weaken the oracle baseline")

    reasons: list[str] = []
    if not candidate.measured or not oracle.measured:
        reasons.append("BENCHMARK_UNAVAILABLE")
    if not candidate.semantic_gate.get("promotable"):
        reasons.append("SEMANTIC_MISMATCH")
    if candidate.workload != oracle.workload:
        reasons.append("WORKLOAD_MISMATCH")

    speedup = (
        candidate.bytes_per_second / oracle.bytes_per_second
        if oracle.bytes_per_second > 0
        else 0.0
    )
    if speedup < minimum_speedup:
        reasons.append("THROUGHPUT_GATE_FAILED")

    if stage == "interactive":
        receipts = dict(prior_stage_receipts or {})
        for required in STAGE_ORDER[:-1]:
            if receipts.get(required) != "VERIFIED":
                reasons.append(f"PRIOR_STAGE_NOT_VERIFIED:{required}")

    promotable = not reasons
    return PromotionDecision(
        state="VERIFIED" if promotable else "BLOCKED",
        promotable=promotable,
        stage=stage,
        reasons=tuple(reasons),
    )
