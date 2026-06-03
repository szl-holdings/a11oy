# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
"""Tests for a11oy.formulas.pac_bayes (Catoni/McAllester). thesis_v22.pdf §2."""
import math
import pytest
from a11oy.formulas import pac_bayes


def test_halfwidth_shrinks_with_n():
    hw_small = pac_bayes.pac_bayes_halfwidth(100, 0.05)
    hw_large = pac_bayes.pac_bayes_halfwidth(10000, 0.05)
    assert hw_large < hw_small


def test_halfwidth_matches_closed_form():
    n, eps, kl = 1000, 0.05, 0.0
    expected = math.sqrt((kl + math.log(2 * math.sqrt(n) / eps)) / (2 * n))
    assert abs(pac_bayes.pac_bayes_halfwidth(n, eps, kl) - expected) < 1e-12


def test_kl_increases_bound():
    assert pac_bayes.pac_bayes_halfwidth(1000, 0.05, 2.0) > pac_bayes.pac_bayes_halfwidth(1000, 0.05, 0.0)


def test_bound_schema_and_clamp():
    out = pac_bayes.pac_bayes_bound(0.95, 100, 0.05)
    assert out["value"] <= 1.0
    assert out["citation"] == "thesis_v22.pdf §2"
    assert "PACBayes.lean" in out["lean_theorem"]


@pytest.mark.parametrize("n,eps", [(0, 0.05), (100, 0.0), (100, 1.0)])
def test_invalid_inputs(n, eps):
    with pytest.raises(ValueError):
        pac_bayes.pac_bayes_halfwidth(n, eps)
