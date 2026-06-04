#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
"""Kalman (1960) verdict state estimator for streaming Λ.

a11oy streams a sequence of noisy Λ verdict scores. A scalar Kalman filter fuses the
stream into a smoothed Λ estimate whose posterior uncertainty NEVER increases on an
update (proved in Lean) — steadier streaming verdicts, fewer single-sample swings. The
same constant-velocity tracker smooths killinchu's noisy RF/MAVLink position tracks.

Published form (thesis_v22.pdf §2, formula table — "Kalman"):
    predict:  x⁻ = F x ;  P⁻ = F P Fᵀ + Q
    update :  S = H P⁻ Hᵀ + R ;  K = P⁻ Hᵀ S⁻¹ ;  x⁺ = x⁻ + K(z − H x⁻) ;  P⁺ = (I − KH) P⁻
R. E. Kalman (1960), "A New Approach to Linear Filtering and Prediction Problems",
Trans. ASME J. Basic Eng. 82(1):35–45.

Lean theorems (round11): ``Lutar/Innovations/round11/FrontierKalmanGain.lean ::
posterior_le_prior, posterior_strict_decrease, gain_in_unit_interval``.

CITATION: thesis_v22.pdf §2  ·  LEAN: Lutar/Innovations/round11/FrontierKalmanGain.lean::posterior_le_prior
"""
from __future__ import annotations

CITATION = "thesis_v22.pdf §2"
LEAN_THEOREM = "Lutar/Innovations/round11/FrontierKalmanGain.lean::posterior_le_prior"


class ScalarKalman:
    """Scalar Kalman estimator for a streaming Λ verdict (H = 1, random-walk model)."""

    def __init__(self, process_var: float = 1e-3, meas_var: float = 1e-1,
                 init_value: float = 0.0, init_var: float = 1.0) -> None:
        self.q = float(process_var)
        self.r = float(meas_var)
        self.x = float(init_value)
        self.p = float(init_var)

    def update(self, z: float) -> dict:
        """One predict (random-walk) + update cycle on measurement z. Honest schema."""
        # predict: x unchanged, P grows by Q
        p_prior = self.p + self.q
        # update
        s = p_prior + self.r
        k = p_prior / s  # gain in [0,1) for q,r>0  (Lean gain_in_unit_interval)
        innovation = z - self.x
        self.x = self.x + k * innovation
        self.p = (1.0 - k) * p_prior  # posterior <= prior (Lean posterior_le_prior)
        return {
            "value": round(self.x, 6),
            "estimate": round(self.x, 6),
            "posterior_variance": round(self.p, 8),
            "prior_variance": round(p_prior, 8),
            "gain": round(k, 6),
            "innovation": round(innovation, 6),
            "gain_in_unit_interval": 0.0 <= k < 1.0,
            "posterior_le_prior": self.p <= p_prior + 1e-12,
            "citation": CITATION,
            "lean_theorem": LEAN_THEOREM,
        }


class KalmanTracker:
    """Constant-velocity 1-D Kalman tracker (position+velocity), per-axis for killinchu."""

    def __init__(self, process_var: float = 1e-2, meas_var: float = 1.0,
                 init_pos: float = 0.0, init_vel: float = 0.0, init_var: float = 1e3) -> None:
        self.q = float(process_var)
        self.r = float(meas_var)
        self.pos = float(init_pos)
        self.vel = float(init_vel)
        self.p00 = float(init_var); self.p01 = 0.0; self.p10 = 0.0; self.p11 = float(init_var)

    def predict(self, dt: float = 1.0) -> None:
        self.pos = self.pos + self.vel * dt
        p00 = self.p00 + dt * (self.p10 + self.p01) + dt * dt * self.p11
        p01 = self.p01 + dt * self.p11
        p10 = self.p10 + dt * self.p11
        self.p00 = p00 + self.q; self.p01 = p01; self.p10 = p10; self.p11 = self.p11 + self.q

    def update(self, z: float) -> float:
        innovation = z - self.pos
        s = self.p00 + self.r
        if s <= 0.0:
            return innovation
        k0 = self.p00 / s; k1 = self.p10 / s
        self.pos += k0 * innovation; self.vel += k1 * innovation
        p00 = (1.0 - k0) * self.p00; p01 = (1.0 - k0) * self.p01
        p10 = self.p10 - k1 * self.p00; p11 = self.p11 - k1 * self.p01
        self.p00, self.p01, self.p10, self.p11 = p00, p01, p10, p11
        return innovation

    def step(self, z: float, dt: float = 1.0) -> dict:
        prior_var = self.p00 + self.q
        self.predict(dt)
        innovation = self.update(z)
        return {
            "value": round(self.pos, 6),
            "smoothed_position": round(self.pos, 6),
            "velocity": round(self.vel, 6),
            "position_variance": round(self.p00, 6),
            "innovation": round(innovation, 6),
            "gain_in_unit_interval": 0.0 <= (prior_var / (prior_var + self.r)) < 1.0,
            "citation": CITATION,
            "lean_theorem": LEAN_THEOREM,
        }


__all__ = ["ScalarKalman", "KalmanTracker", "CITATION", "LEAN_THEOREM"]

# Doctrine v11 LOCKED — 749/14/163 — c7c0ba17 · Λ = Conjecture 1 (NEVER a theorem)
# SLSA L1 honest. L2 build-provenance attestation = roadmap (Wire D) — not yet claimed. L3 not claimed.
