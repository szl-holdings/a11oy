# SPDX-License-Identifier: Apache-2.0
"""Governed inference-engine registry for A11oy.

The registry is intentionally policy/data only: it never claims an engine is
production-qualified merely because it is configured or importable. Promotion
requires measured benchmark evidence plus governance/reproducibility checks.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable

MATURITY_EXPERIMENTAL = "EXPERIMENTAL"
MATURITY_CANDIDATE = "CANDIDATE"
MATURITY_COMPATIBILITY = "COMPATIBILITY_ONLY"
MATURITY_QUALIFIED = "PRODUCTION_QUALIFIED"


@dataclass(frozen=True)
class EngineSpec:
    id: str
    display_name: str
    api_family: str
    maturity: str
    sovereign: bool
    priority: int
    notes: str


_ENGINE_SPECS = (
    EngineSpec(
        id="vllm",
        display_name="vLLM",
        api_family="openai-compatible",
        maturity=MATURITY_CANDIDATE,
        sovereign=True,
        priority=10,
        notes="Primary high-throughput production candidate; must win measured SZL bakeoff.",
    ),
    EngineSpec(
        id="sglang",
        display_name="SGLang",
        api_family="openai-compatible",
        maturity=MATURITY_CANDIDATE,
        sovereign=True,
        priority=20,
        notes="Secondary high-performance candidate for structured/tool-heavy workloads.",
    ),
    EngineSpec(
        id="transformers-v5-serve",
        display_name="Transformers v5 Serve",
        api_family="openai-compatible",
        maturity=MATURITY_EXPERIMENTAL,
        sovereign=True,
        priority=30,
        notes="Reference/compatibility baseline for modern Transformers-native serving.",
    ),
    EngineSpec(
        id="llama-cpp",
        display_name="llama.cpp",
        api_family="openai-compatible",
        maturity=MATURITY_CANDIDATE,
        sovereign=True,
        priority=40,
        notes="Local/edge sovereign lane, especially GGUF workloads.",
    ),
    EngineSpec(
        id="mlx",
        display_name="MLX",
        api_family="openai-compatible-adapter",
        maturity=MATURITY_EXPERIMENTAL,
        sovereign=True,
        priority=50,
        notes="Apple-silicon sovereign lane; qualify only on measured target hardware.",
    ),
    EngineSpec(
        id="tgi",
        display_name="Text Generation Inference",
        api_family="openai-compatible",
        maturity=MATURITY_COMPATIBILITY,
        sovereign=True,
        priority=90,
        notes="Compatibility-only lane; no new default investment without contrary evidence.",
    ),
)

_REQUIRED_PROMOTION_FIELDS = (
    "p50_latency_ms",
    "p95_latency_ms",
    "p99_latency_ms",
    "time_to_first_token_ms",
    "tokens_per_second",
    "peak_memory_mb",
    "structured_output_pass_rate",
    "refusal_parity_pass",
    "governance_pass",
    "reproducibility_pass",
    "source_revision",
    "hardware_fingerprint",
)


def engines() -> tuple[EngineSpec, ...]:
    return tuple(sorted(_ENGINE_SPECS, key=lambda x: x.priority))


def engine(engine_id: str) -> EngineSpec | None:
    wanted = (engine_id or "").strip().lower()
    return next((item for item in _ENGINE_SPECS if item.id == wanted), None)


def public_registry() -> list[dict]:
    return [asdict(item) for item in engines()]


def missing_promotion_evidence(evidence: dict | None) -> list[str]:
    evidence = evidence or {}
    return [field for field in _REQUIRED_PROMOTION_FIELDS if field not in evidence]


def eligible_for_promotion(evidence: dict | None) -> bool:
    """Fail-closed promotion predicate.

    This does not choose a winner; it only determines whether the minimum
    evidence contract is complete and the two governance gates are explicitly
    true. Benchmark comparison happens in the benchmark layer.
    """
    if missing_promotion_evidence(evidence):
        return False
    return bool(evidence.get("governance_pass")) and bool(evidence.get("reproducibility_pass"))


def choose_candidates(ids: Iterable[str] | None = None) -> tuple[EngineSpec, ...]:
    if ids is None:
        return tuple(item for item in engines() if item.maturity != MATURITY_COMPATIBILITY)
    wanted = {str(x).strip().lower() for x in ids}
    return tuple(item for item in engines() if item.id in wanted)
