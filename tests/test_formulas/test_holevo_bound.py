# SPDX-License-Identifier: Apache-2.0
"""Tests for a11oy.formulas.holevo_bound (Holevo 1973). thesis_v22.pdf §2."""
import math
import pytest
from a11oy.formulas import holevo_bound as hb


def test_capacity_binding_bound():
    out = hb.holevo_capacity(dim=4, snr=1.0)  # log2(4)=2 vs log2(2)=1 -> binding=1
    assert abs(out["value"] - 1.0) < 1e-9
    assert out["binding_bound_bits"] == out["value"]


def test_capacity_dim_binds_when_low_dim():
    out = hb.holevo_capacity(dim=2, snr=100.0)  # log2(2)=1 vs log2(101)~6.66 -> binding=1
    assert abs(out["value"] - 1.0) < 1e-9


def test_chi_zero_for_identical_states():
    # identical pure states -> chi = 0
    spec = [1.0, 0.0]
    chi = hb.holevo_chi([0.5, 0.5], [spec, spec])
    assert abs(chi) < 1e-9


def test_chi_orthogonal_pure_states():
    # two orthogonal pure states, equal prob -> chi = 1 bit
    chi = hb.holevo_chi([0.5, 0.5], [[1.0, 0.0], [0.0, 1.0]])
    assert abs(chi - 1.0) < 1e-9


def test_schema():
    out = hb.holevo_capacity(8, 3.0)
    assert out["citation"] == "thesis_v22.pdf §2"
    assert "Holevo" in out["lean_theorem"]


@pytest.mark.parametrize("dim,snr", [(0, 1.0), (2, -1.0)])
def test_invalid(dim, snr):
    with pytest.raises(ValueError):
        hb.holevo_capacity(dim, snr)
