# SPDX-License-Identifier: Apache-2.0
"""Governed inference-engine registry for A11oy.

The registry is intentionally policy/data only: it never claims an engine is
production-qualified merely because it is configured or importable. Promotion
requires measured benchmark evidence plus governance/reproducibility checks.
"""
from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass
from typing import Iterable, Mapping

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
    "benchmark_status",
    "engine_id",
    "model_revision",
    "tokenizer_revision",
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
    "baseline_improvement_pass",
    "source_revision",
    "hardware_fingerprint",
    "receipt_sha256",
    "receipt_signature_status",
    "rollback_instructions",
)

_UNAVAILABLE_VALUES = {
    "",
    "BLOCKED",
    "NOT_AVAILABLE",
    "NOT_MEASURED",
    "UNKNOWN",
    "UNAVAILABLE",
}
_IMMUTABLE_REVISION_RE = re.compile(
    r"^(?:[0-9a-f]{40}|[0-9a-f]{64}|sha256:[0-9a-f]{64})$"
)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def engines() -> tuple[EngineSpec, ...]:
    return tuple(sorted(_ENGINE_SPECS, key=lambda x: x.priority))


def engine(engine_id: str) -> EngineSpec | None:
    wanted = (engine_id or "").strip().lower()
    return next((item for item in _ENGINE_SPECS if item.id == wanted), None)


def public_registry() -> list[dict]:
    return [asdict(item) for item in engines()]


def _finite_number(value: object, *, positive: bool = False) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    number = float(value)
    return math.isfinite(number) and (number > 0 if positive else number >= 0)


def _immutable_revision(value: object) -> bool:
    return isinstance(value, str) and bool(
        _IMMUTABLE_REVISION_RE.fullmatch(value.strip().lower())
    )


def _available_text(value: object, *, minimum_length: int = 1) -> bool:
    if not isinstance(value, str):
        return False
    normalized = value.strip()
    return (
        len(normalized) >= minimum_length
        and normalized.upper() not in _UNAVAILABLE_VALUES
    )


def invalid_promotion_evidence(evidence: Mapping[str, object] | None) -> list[str]:
    """Return missing or invalid promotion fields.

    Presence alone is not evidence.  Every field is type- and value-checked so
    strings such as ``"false"`` and sentinels such as ``UNAVAILABLE`` cannot
    make a candidate eligible.
    """
    if not isinstance(evidence, Mapping):
        return list(_REQUIRED_PROMOTION_FIELDS)

    invalid = [field for field in _REQUIRED_PROMOTION_FIELDS if field not in evidence]

    def reject(field: str, condition: bool) -> None:
        if not condition and field not in invalid:
            invalid.append(field)

    reject("benchmark_status", evidence.get("benchmark_status") == "MEASURED")

    candidate = engine(str(evidence.get("engine_id", "")))
    reject(
        "engine_id",
        candidate is not None and candidate.maturity != MATURITY_COMPATIBILITY,
    )
    for field in ("model_revision", "tokenizer_revision", "source_revision"):
        reject(field, _immutable_revision(evidence.get(field)))

    for field in (
        "p50_latency_ms",
        "p95_latency_ms",
        "p99_latency_ms",
        "time_to_first_token_ms",
    ):
        reject(field, _finite_number(evidence.get(field)))
    reject("tokens_per_second", _finite_number(evidence.get("tokens_per_second"), positive=True))
    reject("peak_memory_mb", _finite_number(evidence.get("peak_memory_mb"), positive=True))

    structured_rate = evidence.get("structured_output_pass_rate")
    reject(
        "structured_output_pass_rate",
        _finite_number(structured_rate)
        and float(structured_rate) <= 1.0,
    )

    for field in (
        "refusal_parity_pass",
        "governance_pass",
        "reproducibility_pass",
        "baseline_improvement_pass",
    ):
        reject(field, evidence.get(field) is True)

    percentiles = [
        evidence.get("p50_latency_ms"),
        evidence.get("p95_latency_ms"),
        evidence.get("p99_latency_ms"),
    ]
    if all(_finite_number(value) for value in percentiles):
        reject(
            "p50_latency_ms",
            float(percentiles[0]) <= float(percentiles[1]) <= float(percentiles[2]),
        )

    reject(
        "hardware_fingerprint",
        _available_text(evidence.get("hardware_fingerprint"), minimum_length=3),
    )
    receipt_sha256 = evidence.get("receipt_sha256")
    reject(
        "receipt_sha256",
        isinstance(receipt_sha256, str)
        and bool(_SHA256_RE.fullmatch(receipt_sha256.strip().lower())),
    )
    reject(
        "receipt_signature_status",
        evidence.get("receipt_signature_status") in {"SIGNED", "UNSIGNED"},
    )
    reject(
        "rollback_instructions",
        _available_text(evidence.get("rollback_instructions"), minimum_length=10),
    )
    return invalid


def missing_promotion_evidence(evidence: Mapping[str, object] | None) -> list[str]:
    """Backward-compatible alias that now rejects invalid evidence too."""
    return invalid_promotion_evidence(evidence)


def eligible_for_promotion(evidence: Mapping[str, object] | None) -> bool:
    """Fail-closed promotion predicate.

    This does not choose a winner; it only determines whether the minimum
    evidence contract is complete and the two governance gates are explicitly
    true. Benchmark comparison happens in the benchmark layer.
    """
    return not invalid_promotion_evidence(evidence)


def choose_candidates(ids: Iterable[str] | None = None) -> tuple[EngineSpec, ...]:
    if ids is None:
        return tuple(item for item in engines() if item.maturity != MATURITY_COMPATIBILITY)
    wanted = {str(x).strip().lower() for x in ids}
    return tuple(item for item in engines() if item.id in wanted)
