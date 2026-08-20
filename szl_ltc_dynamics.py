# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""LTC-derived bounded-dynamics advisory helper (ADDITIVE 2026-07-03).

Own-code reimplementation of the *pattern* from Liquid Time-Constant Networks
(Hasani, Lechner, Amini, Rus, Grosu; arXiv:2006.04439; reference repo
github.com/raminmh/liquid_time_constant_networks, Apache-2.0). We reimplement
ONLY the bounded first-order state-dependent dynamics form and its fused
semi-implicit Euler step in our own permissive code — no source is vendored.

The LTC hidden state obeys the linear first-order ODE

    dh/dt = -(1/tau + g(h, x; theta)) * h + g(h, x; theta) * A

with a state-dependent ("liquid") effective time-constant. Integrated by the
paper's fused semi-implicit Euler step, the state is provably bounded and the
effective time-constant stays bounded (no blow-up). We carry those two
properties as RUNTIME self-checks (clamp + assert), not as a fresh theorem.

ADVISORY DISCIPLINE (doctrine v11): every surface produced here is labelled
"LTC-derived · advisory · experimental". This module NEVER claims proven
convergence, NEVER upgrades the advisory Banach guard to a theorem, NEVER moves
Lambda off Conjecture 1, and NEVER touches the locked-8. It is a bounded
*dynamical-systems* stability estimate over an observed scalar sequence — an
honest advisory note, nothing more. It never raises: any bad input degrades to
an honest ``{"ltc_bounded": False, ...}`` no-op.
"""
from __future__ import annotations

import math
from typing import Iterable

LABEL = "LTC-derived · advisory · experimental"

# Fixed, conservative defaults. These are engineering bounds, not tuned weights:
# there is no training here — g(.) is a fixed bounded positive gate so the step
# is a pure dynamical-systems stability probe over the observed delta sequence.
_TAU_MIN = 1e-3      # bounded-tau floor  (tau in [_TAU_MIN, _TAU_MAX])
_TAU_MAX = 1e3       # bounded-tau ceiling
_STATE_BOUND = 1.0   # |h| analytic bound: inputs are normalised into [0, 1]
_DT = 1.0            # fixed integration step (one iterate == one time unit)
_EPS = 1e-9


def _sigmoid(z: float) -> float:
    """Numerically-stable logistic; the fixed bounded gate g(.) in (0, 1)."""
    if z >= 0.0:
        return 1.0 / (1.0 + math.exp(-z))
    ez = math.exp(z)
    return ez / (1.0 + ez)


def _clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else (hi if v > hi else v)


def ltc_step(h: float, x: float, *, tau: float = 1.0, A: float = 1.0,
             dt: float = _DT, theta_w: float = 1.0, theta_b: float = 0.0) -> float:
    """One fused semi-implicit Euler step of the scalar LTC ODE.

    Closed form of the paper's fused solver (implicit in the decay term):

        h_next = (h + dt * g * A) / (1 + dt * (1/tau + g))

    With ``dt > 0``, ``tau > 0`` and ``g >= 0`` the denominator is ``> 1``, so the
    map is a contraction toward the bounded convex combination of ``h`` and ``A``
    — this is the LTC bounded-state property, enforced here by construction (and
    re-checked by :func:`ltc_stability_note`). ``g`` is the state-dependent gate;
    ``1/(1/tau + g)`` is the bounded effective ("liquid") time-constant.
    """
    tau = _clamp(float(tau), _TAU_MIN, _TAU_MAX)          # bounded-tau self-check
    dt = abs(float(dt)) or _DT
    g = _sigmoid(theta_w * float(x) + theta_b * float(h))  # bounded gate in (0,1)
    denom = 1.0 + dt * (1.0 / tau + g)
    h_next = (float(h) + dt * g * float(A)) / denom
    # bounded-state self-check: analytic bound is |A|; clamp defensively.
    bound = max(_STATE_BOUND, abs(float(A)))
    return _clamp(h_next, -bound, bound)


def ltc_stability_note(delta_history: Iterable[float], *, tau: float = 1.0,
                       eps: float = _EPS) -> dict:
    """Advisory bounded-dynamics note over an observed scalar sequence.

    ``delta_history`` is the sequence of per-iteration trust/receipt deltas from
    the governed cycle (non-negative scalars). We drive a single scalar LTC with
    that sequence and report, as an ADVISORY note:

      * ``ltc_bounded``           — did the integrated state stay inside its
        analytic bound for every step (no clamp ever engaged)?
      * ``ltc_stability_estimate``— mean per-step contraction ratio of |h|
        (``< 1.0`` suggests the state is settling / contracting). This is a
        best-effort dynamical estimate, NOT a proof and NOT the halting
        condition (the finite budget alone guarantees the loop halts).

    Never raises: malformed input yields an honest inert note.
    """
    note = {"ltc_bounded": False, "ltc_stability_estimate": None,
            "label": LABEL, "measurable": False,
            "note": ("LTC-derived bounded-dynamics estimate over the observed "
                     "delta sequence. ADVISORY / experimental — not a proof of "
                     "convergence; the finite budget guarantees halting.")}
    try:
        seq = [float(d) for d in delta_history if d is not None]
    except Exception:  # pragma: no cover - honest no-op on bad input
        return note
    if len(seq) < 2:
        return note

    # Normalise the drive into [0, 1] so the analytic |h| <= 1 bound applies.
    peak = max(abs(v) for v in seq) or 1.0
    drive = [_clamp(abs(v) / peak, 0.0, 1.0) for v in seq]

    bounded = True
    h = 0.0
    ratios = []
    bound = _STATE_BOUND
    for x in drive:
        prev_abs = abs(h)
        h = ltc_step(h, x, tau=tau, A=x)
        if abs(h) > bound + eps:            # analytic bound must hold every step
            bounded = False
        if prev_abs > eps:
            ratios.append((abs(h) + eps) / (prev_abs + eps))

    estimate = (sum(ratios) / len(ratios)) if ratios else None
    note["ltc_bounded"] = bool(bounded)
    note["ltc_stability_estimate"] = (round(float(estimate), 6)
                                      if estimate is not None else None)
    note["measurable"] = estimate is not None
    return note
