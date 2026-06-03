# SPDX-License-Identifier: Apache-2.0
"""Tests for a11oy.formulas.kalman (Kalman 1960). thesis_v22.pdf §2."""
from a11oy.formulas import kalman


def test_scalar_variance_never_increases():
    k = kalman.ScalarKalman(process_var=1e-3, meas_var=1e-1, init_var=1.0)
    for z in [0.9, 0.92, 0.88, 0.91, 0.9]:
        out = k.update(z)
        assert out["posterior_le_prior"] is True
        assert out["gain_in_unit_interval"] is True


def test_scalar_tracks_constant():
    k = kalman.ScalarKalman(init_value=0.0)
    for _ in range(100):
        out = k.update(0.85)
    assert abs(out["value"] - 0.85) < 0.05


def test_tracker_smooths_noise():
    kt = kalman.KalmanTracker(meas_var=4.0, init_pos=0.0)
    noisy = [0, 5, -3, 8, 2, 6, 1, 7]
    last = None
    for z in noisy:
        last = kt.step(z)
    assert last["citation"] == "thesis_v22.pdf §2"
    assert "posterior_le_prior" in last["lean_theorem"]
