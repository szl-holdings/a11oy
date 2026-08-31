# SPDX-License-Identifier: Apache-2.0
"""Tests for a11oy.formulas.welford (Welford 1962). thesis_v22.pdf §2."""
import statistics
from a11oy.formulas import welford


def test_mean_variance_matches_numpy_style():
    data = [10.0, 12.0, 23.0, 23.0, 16.0, 23.0, 21.0, 16.0]
    w = welford.Welford()
    for x in data:
        w.update(x)
    assert abs(w.mean - statistics.mean(data)) < 1e-9
    assert abs(w.variance - statistics.variance(data)) < 1e-9


def test_zero_variance_before_two_samples():
    w = welford.Welford()
    w.update(5.0)
    assert w.variance == 0.0
    assert w.zscore(99.0) == 0.0


def test_anomaly_flag():
    w = welford.Welford(z_threshold=3.0)
    for _ in range(50):
        w.update(100.0)
    w.update(100.5)
    assert w.is_anomaly(1000.0) is True


def test_observe_schema():
    w = welford.Welford()
    out = w.observe(1.0)
    assert out["citation"] == "thesis_v22.pdf §2"
    assert "welford_mean_exact" in out["lean_theorem"]
    assert out["count"] == 1
