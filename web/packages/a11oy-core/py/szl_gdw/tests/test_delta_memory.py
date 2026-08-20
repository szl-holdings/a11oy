import numpy as np
import pytest
from szl_gdw.math_core import delta_update, governed_depth_attention
from szl_gdw.models import DepthSummary


def test_zero_error_no_update_when_retention_is_one():
    previous = np.array([1.0, 2.0])
    output = delta_update(
        previous,
        previous.copy(),
        previous.copy(),
        retention=1.0,
        learning_rate=0.5,
        novelty=1.0,
        risk=0.0,
    )
    assert np.array_equal(output, previous)


def test_delta_update_rejects_shape_drift():
    with pytest.raises(ValueError, match="incompatible"):
        delta_update(
            np.zeros(2),
            np.zeros(3),
            np.zeros(2),
            retention=1.0,
            learning_rate=0.5,
            novelty=1.0,
            risk=0.0,
        )


def test_governed_depth_attention_returns_auditable_simplex():
    summaries = (
        DepthSummary("trusted", 1, (1.0, 0.0), 1.0, 0.0, ("e1",)),
        DepthSummary("risky", 2, (0.0, 1.0), 0.5, 1.0, ("e2",)),
    )
    retrieved, audit = governed_depth_attention(np.array([1.0, 0.0]), summaries)
    assert retrieved.shape == (2,)
    assert sum(audit.values()) == pytest.approx(1.0)
    assert audit["trusted"] > audit["risky"]


def test_governed_depth_attention_rejects_dimension_drift():
    summary = DepthSummary("depth", 1, (1.0, 0.0), 1.0, 0.0, ())
    with pytest.raises(ValueError, match="dimensions"):
        governed_depth_attention(np.array([1.0]), (summary,))
