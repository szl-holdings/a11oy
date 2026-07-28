#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173

"""Numerical primitives for the MODELED Governed Delta Workspace."""

from __future__ import annotations

import math
from typing import Dict, Sequence, Tuple

from .models import DepthSummary


EPS = 1e-8
RETENTION_MIN, RETENTION_MAX = 0.0, 1.0


def sigmoid(x: float) -> float:
    if not math.isfinite(x):
        raise ValueError("sigmoid input must be finite")
    bounded = max(-60.0, min(60.0, x))
    return 1.0 / (1.0 + math.exp(-bounded))


def delta_update(
    previous: Sequence[float],
    observed: Sequence[float],
    predicted: Sequence[float],
    retention: float,
    learning_rate: float,
    novelty: float,
    risk: float,
) -> Tuple[float, ...]:
    """Apply a bounded delta-rule update without mutating any input vector."""

    try:
        previous_values = tuple(float(value) for value in previous)
        observed_values = tuple(float(value) for value in observed)
        predicted_values = tuple(float(value) for value in predicted)
    except (TypeError, ValueError) as exc:
        raise ValueError("delta vectors must be one-dimensional numeric values") from exc
    if (
        len(previous_values) != len(observed_values)
        or len(previous_values) != len(predicted_values)
    ):
        raise ValueError("delta vectors have incompatible shapes")
    if not previous_values:
        raise ValueError("delta vectors must be non-empty and one-dimensional")
    if not RETENTION_MIN <= retention <= RETENTION_MAX:
        raise ValueError("retention must be in [0, 1]")
    if not 0.0 <= learning_rate <= 1.0:
        raise ValueError("learning_rate must be in [0, 1]")
    if not all(math.isfinite(v) for v in (retention, learning_rate, novelty, risk)):
        raise ValueError("delta parameters must be finite")
    if not all(
        math.isfinite(value)
        for vector in (previous_values, observed_values, predicted_values)
        for value in vector
    ):
        raise ValueError("delta vectors must be finite")

    gate = sigmoid(novelty - risk)
    return tuple(
        retention * prior + learning_rate * gate * (actual - expected)
        for prior, actual, expected in zip(
            previous_values, observed_values, predicted_values
        )
    )


def governed_depth_attention(
    query: Sequence[float],
    summaries: Sequence[DepthSummary],
    epsilon: float = EPS,
) -> Tuple[Tuple[float, ...], Dict[str, float]]:
    """Retrieve prior depth state with explicit trust and risk modulation."""

    try:
        query_values = tuple(float(value) for value in query)
    except (TypeError, ValueError) as exc:
        raise ValueError("query must be a finite non-empty vector") from exc
    if not query_values or not all(math.isfinite(value) for value in query_values):
        raise ValueError("query must be a finite non-empty vector")
    if not math.isfinite(epsilon) or epsilon <= 0.0:
        raise ValueError("epsilon must be finite and positive")
    if not summaries:
        return tuple(0.0 for _ in query_values), {}

    try:
        matrix = tuple(
            tuple(float(value) for value in summary.vector)
            for summary in summaries
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("summary vectors must be numeric") from exc
    if any(len(vector) != len(query_values) for vector in matrix):
        raise ValueError("summary and query dimensions differ")
    if not all(math.isfinite(value) for vector in matrix for value in vector):
        raise ValueError("summary vectors must be finite")
    if len({summary.summary_id for summary in summaries}) != len(summaries):
        raise ValueError("summary identifiers must be unique")

    if not all(
        math.isfinite(float(value))
        for summary in summaries
        for value in (summary.trust, summary.risk)
    ):
        raise ValueError("summary trust and risk must be finite")
    q_norm = max(math.sqrt(sum(value * value for value in query_values)), epsilon)
    logits = []
    for summary, vector in zip(summaries, matrix):
        vector_norm = max(math.sqrt(sum(value * value for value in vector)), epsilon)
        similarity = (
            sum(value * query_value for value, query_value in zip(vector, query_values))
            / (vector_norm * q_norm)
        )
        trust = min(1.0, max(0.0, float(summary.trust)))
        risk = max(0.0, float(summary.risk))
        logits.append(similarity + math.log(epsilon + trust) - risk)
    peak = max(logits)
    unnormalized = tuple(math.exp(logit - peak) for logit in logits)
    weight_sum = sum(unnormalized)
    if not math.isfinite(weight_sum) or weight_sum <= 0.0:
        raise ValueError("depth attention normalization failed")
    weights = tuple(weight / weight_sum for weight in unnormalized)
    retrieved = tuple(
        sum(weight * vector[index] for weight, vector in zip(weights, matrix))
        for index in range(len(query_values))
    )
    return retrieved, {
        summary.summary_id: float(weight)
        for summary, weight in zip(summaries, weights)
    }
