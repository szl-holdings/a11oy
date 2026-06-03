# SPDX-License-Identifier: Apache-2.0
"""Tests for a11oy.formulas.byzantine_quorum (n>=3f+1). thesis_v22.pdf §2."""
import pytest
from a11oy.formulas import byzantine_quorum as bq


def test_max_faults():
    assert [bq.max_byzantine_faults(n) for n in (1, 3, 4, 5, 6, 7, 10)] == [0, 0, 1, 1, 1, 2, 3]


def test_quorum_size():
    assert [bq.quorum_size(f) for f in (0, 1, 2, 3)] == [1, 3, 5, 7]


def test_threshold_5_organ_mesh():
    out = bq.quorum_threshold(5, 1)
    assert out["value"] == 3
    assert out["bft_feasible"] is True
    assert out["citation"] == "thesis_v22.pdf §2"


def test_infeasible_when_too_few():
    out = bq.quorum_threshold(3, 1)  # 3 < 3*1+1=4
    assert out["bft_feasible"] is False


def test_invalid():
    with pytest.raises(ValueError):
        bq.quorum_threshold(0)
