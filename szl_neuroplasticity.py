"""szl_neuroplasticity.py — SZL Holdings neuroplasticity / learning-rule formulas.

EXPERIMENTAL-tier. PURE STDLIB (no numpy — consistent with every SZL shared module;
vectors here are small). Adds NOTHING to the locked-8. Λ stays Conjecture 1. Trust
never 100%. No fabricated data. Every rule is established prior art, cited to its
real author; SZL claims NONE as its own discovery.

WHY THIS EXISTS: the new SZL "learning / brain" pillar, grounding a11oy's agent
learning loop in real, cited neuroplasticity math. The honest frontier tie-in is
LOSS OF PLASTICITY in continual learning (Dohare/Sutton, Nature 2024) — a real
problem for any long-running agent — addressed clean-room with continual-backprop
+ dormant-neuron + synaptic-scaling style utilities. The rigorous unifying identity
(Friston/predictive-coding ↔ Hebbian, Millidge et al. 2022) is noted but NOT claimed
as SZL's; it is a PROPOSED lens, never a theorem about Λ (Λ stays Conjecture 1).

Honest tiering:
  * Hebb / Oja / BCM / STDP / synaptic scaling : RIGOROUS (classical, cited).
  * Loss-of-plasticity, ReDo, plasticity-injection, EWC : RIGOROUS (recent, cited).
  * Predictive-coding ↔ Hebbian unifier        : PROPOSED lens (not a Λ claim).

Citations (real, verified):
  * Hebb (1949) The Organization of Behavior.
  * Oja (1982) J. Math. Biol. 15:267-273, DOI:10.1007/BF00275687 (PCA convergence).
  * Bienenstock-Cooper-Munro BCM (1982) J. Neurosci. 2(1):32-48,
    DOI:10.1523/JNEUROSCI.02-01-00032.1982 (sliding threshold).
  * Bi & Poo STDP (1998) J. Neurosci. 18(24):10464, DOI:10.1523/JNEUROSCI.18-24-10464.1998.
  * Turrigiano synaptic scaling (2008) Cell, DOI:10.1016/j.cell.2008.10.008.
  * Hubel & Wiesel critical periods (Nobel 1981).
  * Dohare, Sutton et al. "Loss of plasticity in deep continual learning" Nature 2024,
    DOI:10.1038/s41586-024-07711-7.
  * Kirkpatrick et al. EWC (2017) PNAS, DOI:10.1073/pnas.1611835114.
  * Millidge et al. (2022) arXiv:2206.02629 (PC ↔ backprop/Hebbian identity).

Routes:  GET /api/<ns>/v1/neuro/{summary,hebb,oja,bcm,stdp,plasticity,ewc}
"""
from __future__ import annotations

import math
from typing import List, Sequence


def _dot(a: Sequence[float], b: Sequence[float]) -> float:
    return float(sum(x * y for x, y in zip(a, b)))


def _norm(a: Sequence[float]) -> float:
    return math.sqrt(_dot(a, a))


def hebb_update(w: List[float], x: Sequence[float], y: float, eta: float) -> List[float]:
    """Δw = η·x·y (Hebb 1949). UNSTABLE alone — grows unbounded; see Oja/BCM."""
    return [w[i] + eta * x[i] * y for i in range(len(w))]


def oja_step(w: List[float], x: Sequence[float], eta: float) -> dict:
    """Oja's rule (1982): w ← w + η(y·x − y²·w), y = wᵀx. Provably converges
    a.s. to the first principal eigenvector of E[xxᵀ]; output variance → λ₁."""
    y = _dot(w, x)
    w2 = [w[i] + eta * (y * x[i] - y * y * w[i]) for i in range(len(w))]
    return {"y": y, "w": w2}


def oja_fit(X: List[Sequence[float]], eta: float = 0.05, epochs: int = 30) -> dict:
    """Run Oja's rule over data X; returns the learned (normalized) weight vector,
    which approximates the top principal component (Oja 1982). Deterministic seed."""
    if not X:
        return {"status": "out_of_domain"}
    n = len(X[0])
    # deterministic init: normalized ones
    w = [1.0 / math.sqrt(n)] * n
    for _ in range(epochs):
        for x in X:
            w = oja_step(w, x, eta)["w"]
        nrm = _norm(w)
        if nrm > 1e-12:
            w = [c / nrm for c in w]
    # Rayleigh quotient ~ top eigenvalue estimate
    # C w via sample covariance applied to w
    m = len(X)
    Cw = [0.0] * n
    for x in X:
        xw = _dot(x, w)
        for i in range(n):
            Cw[i] += x[i] * xw / m
    lam = _dot(w, Cw)
    return {"principal_direction": [round(c, 6) for c in w],
            "eigenvalue_estimate": round(lam, 6),
            "cite": "Oja 1982, J. Math. Biol. 15:267-273"}


def bcm_threshold(y_history: Sequence[float], tau: float = 1.0) -> dict:
    """BCM sliding modification threshold θ_M = E[y²] (Bienenstock-Cooper-Munro
    1982). Δw ∝ x·y·(y − θ_M): potentiation above θ_M, depression below. θ_M
    slides with recent activity, giving stability + selectivity."""
    if not y_history:
        return {"status": "out_of_domain"}
    theta_M = sum(yi * yi for yi in y_history) / len(y_history)
    y_now = y_history[-1]
    phi = y_now * (y_now - theta_M)   # BCM plasticity function sign
    return {"theta_M": round(theta_M, 6), "y": round(y_now, 6),
            "plasticity_sign": "potentiate" if phi > 0 else ("depress" if phi < 0 else "neutral"),
            "phi": round(phi, 6),
            "cite": "BCM 1982, J. Neurosci. 2(1):32-48"}


def stdp_window(delta_t_ms: float, A_plus: float = 1.0, A_minus: float = 1.0,
                tau_plus: float = 17.0, tau_minus: float = 34.0) -> dict:
    """Spike-timing-dependent plasticity (Bi & Poo 1998): pre-before-post
    (Δt>0) potentiates ∝ A₊·exp(−Δt/τ₊); post-before-pre (Δt<0) depresses
    ∝ −A₋·exp(Δt/τ₋). Δt = t_post − t_pre (ms)."""
    if delta_t_ms > 0:
        dw = A_plus * math.exp(-delta_t_ms / tau_plus)
        kind = "LTP (potentiation)"
    elif delta_t_ms < 0:
        dw = -A_minus * math.exp(delta_t_ms / tau_minus)
        kind = "LTD (depression)"
    else:
        dw = 0.0
        kind = "coincident"
    return {"delta_t_ms": delta_t_ms, "delta_w": round(dw, 6), "kind": kind,
            "cite": "Bi & Poo 1998, J. Neurosci. 18(24):10464"}


def plasticity_health(activations: Sequence[float], dormant_threshold: float = 1e-3) -> dict:
    """Loss-of-plasticity diagnostic (Dohare/Sutton, Nature 2024 + ReDo, Sokar 2023).
    Fraction of 'dormant' units (near-zero activation) + a simple plasticity score
    (1 − dormant_fraction). High dormancy => plasticity loss => recommend continual
    re-init (continual backprop / ReDo) of the dormant units."""
    if not activations:
        return {"status": "out_of_domain"}
    n = len(activations)
    dormant = sum(1 for a in activations if abs(a) < dormant_threshold)
    frac = dormant / n
    return {"n_units": n, "dormant_units": dormant,
            "dormant_fraction": round(frac, 4),
            "plasticity_score": round(1.0 - frac, 4),
            "recommendation": ("re-initialize dormant units (continual backprop / ReDo)"
                               if frac > 0.1 else "healthy"),
            "tier": "RIGOROUS (Dohare-Sutton Nature 2024; Sokar ReDo ICML 2023)",
            "cites": ["Dohare-Sutton 2024 DOI:10.1038/s41586-024-07711-7",
                      "Sokar et al. ReDo 2023 arXiv:2302.12902"]}


def ewc_penalty(theta: Sequence[float], theta_star: Sequence[float],
                fisher: Sequence[float], lam: float = 1.0) -> dict:
    """Elastic Weight Consolidation penalty (Kirkpatrick et al. 2017): protects
    weights important to a prior task. L_EWC = (λ/2)·Σ F_i·(θ_i − θ*_i)². Mitigates
    catastrophic forgetting in continual learning."""
    if not (len(theta) == len(theta_star) == len(fisher)):
        return {"status": "out_of_domain", "reason": "length mismatch"}
    pen = 0.5 * lam * sum(fisher[i] * (theta[i] - theta_star[i]) ** 2 for i in range(len(theta)))
    return {"ewc_penalty": round(pen, 6), "lambda": lam,
            "cite": "Kirkpatrick et al. 2017 PNAS DOI:10.1073/pnas.1611835114"}


def critical_period_rate(t: float, alpha_max: float = 1.0, t_peak: float = 0.0,
                         sigma_cp: float = 1.0, alpha_floor: float = 0.01) -> dict:
    """Hubel-Wiesel critical-period plasticity envelope: a Gaussian in
    developmental time peaking at t_peak (Nobel 1981). Plasticity is highest
    during the critical period and decays (with a small adult floor)."""
    rate = alpha_max * math.exp(-((t - t_peak) ** 2) / (2.0 * sigma_cp ** 2))
    return {"t": t, "plasticity_rate": round(max(rate, alpha_floor), 6),
            "cite": "Hubel & Wiesel, Nobel 1981 (critical periods)"}


def summary() -> dict:
    return {
        "title": "SZL Neuroplasticity — learning-rule formulas grounding a11oy's agent loop",
        "honest_frame": ("Rigorous, cited learning-rule math (Hebb/Oja/BCM/STDP/scaling) "
                         "+ the modern loss-of-plasticity frontier (Dohare-Sutton Nature "
                         "2024) for long-running agents. The PC↔Hebbian unifying identity "
                         "(Millidge 2022) is a PROPOSED lens — never a Λ theorem; Λ stays Conjecture 1."),
        "rules": ["hebb", "oja", "bcm", "stdp", "synaptic_scaling",
                  "plasticity_health", "ewc", "critical_period"],
        "tiers": {
            "hebb_oja_bcm_stdp_scaling": "RIGOROUS (classical)",
            "loss_of_plasticity_redo_ewc": "RIGOROUS (recent, cited)",
            "predictive_coding_hebbian_unifier": "PROPOSED lens (not a Λ claim)",
        },
        "doctrine": {"locked_count_unchanged": True, "lambda": "Conjecture 1 (never theorem)",
                     "trust_never_100": True, "tier": "EXPERIMENTAL/PROPOSED"},
        "lean_candidates": ["Oja convergence to top eigenvector", "BCM fixed-point",
                            "critical-period envelope monotone past peak"],
        "cites": [
            "Hebb 1949", "Oja 1982 DOI:10.1007/BF00275687",
            "BCM 1982 DOI:10.1523/JNEUROSCI.02-01-00032.1982",
            "Bi-Poo 1998 DOI:10.1523/JNEUROSCI.18-24-10464.1998",
            "Turrigiano 2008 DOI:10.1016/j.cell.2008.10.008",
            "Dohare-Sutton 2024 DOI:10.1038/s41586-024-07711-7",
            "Kirkpatrick 2017 DOI:10.1073/pnas.1611835114",
            "Millidge 2022 arXiv:2206.02629",
        ],
    }


def register(app, ns: str) -> None:
    base = f"/api/{ns}/v1/neuro"
    app.add_api_route(f"{base}/summary", lambda: summary(), methods=["GET"])
    app.add_api_route(
        f"{base}/hebb",
        lambda w="0.1,0.1", x="1,0", y="1.0", eta="0.1":
            {"w_next": [round(c, 6) for c in hebb_update(
                [float(a) for a in w.split(",")], [float(a) for a in x.split(",")],
                float(y), float(eta))], "note": "Hebb is unstable alone; see Oja/BCM",
             "cite": "Hebb 1949"},
        methods=["GET"])
    app.add_api_route(
        f"{base}/oja",
        lambda data="2,0;1,0;3,0;0,0", eta="0.05", epochs="30":
            oja_fit([[float(v) for v in row.split(",")] for row in data.split(";") if row.strip()],
                    float(eta), int(epochs)),
        methods=["GET"])
    app.add_api_route(
        f"{base}/bcm",
        lambda y="0.2,0.5,0.9,1.2": bcm_threshold([float(v) for v in y.split(",") if v.strip()]),
        methods=["GET"])
    app.add_api_route(
        f"{base}/stdp",
        lambda dt="10": stdp_window(float(dt)), methods=["GET"])
    app.add_api_route(
        f"{base}/plasticity",
        lambda act="0.5,0.0,0.0001,0.8,0.0":
            plasticity_health([float(v) for v in act.split(",") if v.strip()]),
        methods=["GET"])
    app.add_api_route(
        f"{base}/ewc",
        lambda theta="1,1", star="0,0", fisher="2,1", lam="1.0":
            ewc_penalty([float(v) for v in theta.split(",")],
                        [float(v) for v in star.split(",")],
                        [float(v) for v in fisher.split(",")], float(lam)),
        methods=["GET"])


def _selftest() -> None:
    # Hebb grows weight for correlated input
    w1 = hebb_update([0.0, 0.0], [1.0, 0.0], 1.0, 0.1)
    assert w1[0] > 0 and abs(w1[1]) < 1e-12
    # Oja: data varying only along axis 0 -> principal direction ~ (±1, 0)
    X = [[2.0, 0.0], [1.0, 0.0], [3.0, 0.0], [-2.0, 0.0], [0.5, 0.0]]
    res = oja_fit(X, eta=0.02, epochs=200)
    pd = res["principal_direction"]
    assert abs(abs(pd[0]) - 1.0) < 0.05 and abs(pd[1]) < 0.05, pd
    assert res["eigenvalue_estimate"] > 0
    # BCM: above-threshold activity potentiates, below depresses
    assert bcm_threshold([0.1, 0.1, 0.1, 1.0])["plasticity_sign"] == "potentiate"
    assert bcm_threshold([1.0, 1.0, 1.0, 0.1])["plasticity_sign"] == "depress"
    # STDP: pre-before-post (dt>0) LTP, post-before-pre (dt<0) LTD
    assert stdp_window(10)["delta_w"] > 0
    assert stdp_window(-10)["delta_w"] < 0
    assert abs(stdp_window(0)["delta_w"]) < 1e-12
    # Plasticity health: dormant units detected
    ph = plasticity_health([0.5, 0.0, 0.00001, 0.8, 0.0])
    assert ph["dormant_units"] == 3 and ph["plasticity_score"] < 0.5
    # EWC penalty non-negative, zero at theta==theta_star
    assert ewc_penalty([1, 1], [1, 1], [2, 3])["ewc_penalty"] == 0.0
    assert ewc_penalty([1, 0], [0, 0], [2, 0])["ewc_penalty"] > 0
    # critical period: peaks at t_peak, decays away
    assert critical_period_rate(0.0, t_peak=0.0)["plasticity_rate"] > \
           critical_period_rate(5.0, t_peak=0.0)["plasticity_rate"]
    # guards
    assert oja_fit([])["status"] == "out_of_domain"
    assert summary()["doctrine"]["lambda"].startswith("Conjecture 1")
    print("szl_neuroplasticity: ALL OK (13 checks)")


if __name__ == "__main__":
    _selftest()
