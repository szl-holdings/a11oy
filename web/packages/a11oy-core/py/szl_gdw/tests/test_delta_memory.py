#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173

import pytest

from szl_gdw.math_core import delta_update, governed_depth_attention
from szl_gdw.models import DepthSummary


def test_zero_error_no_update_with_full_retention():
    previous = [1.0, 2.0]
    output = delta_update(
        previous,
        list(previous),
        list(previous),
        retention=1.0,
        learning_rate=0.5,
        novelty=1.0,
        risk=0.0,
    )
    assert output == pytest.approx(previous)
    assert output is not previous


def test_delta_shape_and_finite_gates():
    with pytest.raises(ValueError):
        delta_update(
            [0.0, 0.0],
            [0.0, 0.0, 0.0],
            [0.0, 0.0],
            retention=1.0,
            learning_rate=0.5,
            novelty=1.0,
            risk=0.0,
        )
    with pytest.raises(ValueError):
        delta_update(
            [float("nan")],
            [0.0],
            [0.0],
            retention=1.0,
            learning_rate=0.5,
            novelty=1.0,
            risk=0.0,
        )


def test_depth_attention_validates_shape_and_closes_weights():
    summaries = (
        DepthSummary("a", 0, (1.0, 0.0), 0.9, 0.1, ("e1",)),
        DepthSummary("b", 1, (0.0, 1.0), 0.8, 0.2, ("e2",)),
    )
    retrieved, weights = governed_depth_attention(
        [1.0, 0.0], summaries
    )
    assert len(retrieved) == 2
    assert sum(weights.values()) == pytest.approx(1.0)
    with pytest.raises(ValueError):
        governed_depth_attention([1.0], summaries)
