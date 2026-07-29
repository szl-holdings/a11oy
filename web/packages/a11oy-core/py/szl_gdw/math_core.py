"""Numerical primitives for the MODELED governed workspace."""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np

from .models import DepthSummary

EPS = 1e-8


def sigmoid(value: float) -> float:
    if not math.isfinite(value):
        raise ValueError("sigmoid input must be finite")
    bounded = max(-60.0, min(60.0, value))
    return 1.0 / (1.0 + math.exp(-bounded))


def delta_update(
    previous: np.ndarray,
    observed: np.ndarray,
    predicted: np.ndarray,
    retention: float,
    learning_rate: float,
    novelty: float,
    risk: float,
) -> np.ndarray:
    """Apply a bounded, auditable delta-memory update."""
    previous = np.asarray(previous, dtype=np.float64)
    observed = np.asarray(observed, dtype=np.float64)
    predicted = np.asarray(predicted, dtype=np.float64)
    if previous.shape != observed.shape or previous.shape != predicted.shape:
        raise ValueError("delta vectors have incompatible shapes")
    if previous.ndim != 1:
        raise ValueError("delta vectors must be one-dimensional")
    if previous.size == 0:
        raise ValueError("delta vectors must be non-empty")
    if not 0.0 <= retention <= 1.0:
        raise ValueError("retention must be in [0, 1]")
    if not 0.0 <= learning_rate <= 1.0:
        raise ValueError("learning_rate must be in [0, 1]")
    if not math.isfinite(novelty) or not math.isfinite(risk):
        raise ValueError("novelty and risk must be finite")
    if not all(np.isfinite(value).all() for value in (previous, observed, predicted)):
        raise ValueError("delta vectors must contain only finite values")

    gate = sigmoid(novelty - risk)
    return retention * previous + learning_rate * gate * (observed - predicted)


def governed_depth_attention(
    query: np.ndarray,
    summaries: Sequence[DepthSummary],
    epsilon: float = EPS,
) -> tuple[np.ndarray, dict[str, float]]:
    """Attend over explicit depth summaries with trust and risk in the audit."""
    query = np.asarray(query, dtype=np.float64)
    if query.ndim != 1 or not np.isfinite(query).all():
        raise ValueError("query must be a finite one-dimensional vector")
    if not math.isfinite(epsilon) or epsilon <= 0.0:
        raise ValueError("epsilon must be finite and positive")
    if not summaries:
        return np.zeros_like(query), {}

    matrix = np.asarray([summary.vector for summary in summaries], dtype=np.float64)
    if matrix.ndim != 2 or matrix.shape != (len(summaries), query.shape[0]):
        raise ValueError("summary and query dimensions differ")
    if not np.isfinite(matrix).all():
        raise ValueError("summary vectors must contain only finite values")

    query_norm = max(float(np.linalg.norm(query)), epsilon)
    vector_norms = np.maximum(np.linalg.norm(matrix, axis=1), epsilon)
    similarities = (matrix @ query) / (vector_norms * query_norm)
    trust = np.asarray([summary.trust for summary in summaries], dtype=np.float64)
    risk = np.asarray([summary.risk for summary in summaries], dtype=np.float64)

    logits = similarities + np.log(epsilon + trust) - risk
    logits -= float(logits.max())
    weights = np.exp(logits)
    weights /= float(weights.sum())

    retrieved = weights @ matrix
    audit = {
        summary.summary_id: float(weight) for summary, weight in zip(summaries, weights)
    }
    return retrieved, audit
