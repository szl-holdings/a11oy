# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
"""
szl_cuas_formulas.py — SZL counter-UAS C2 formula module (killinchu spine), real
deterministic Python. SHARED module: byte-identical in a11oy AND killinchu.

Six SZL formulas, each OUR OWN construct but citing the classical inspiration. Every
function is pure + deterministic with a built-in self-test asserting a known numeric.
NOTHING here is fabricated; nothing claims a classical result as SZL's discovery.

DOCTRINE: killinchu effector is SIMULATED (these compute solutions/feasibility, they do
NOT actuate). locked-proven = EXACTLY 8 {F1,F4,F7,F11,F12,F18,F19,F22} @ c7c0ba17 —
this module adds NOTHING to the locked 8 and is EXPERIMENTAL-tier. Λ = Conjecture 1.
Trust never 100%. No runtime CDN. Label SIMULATED/PROXY/SAMPLE where not live.

Inspirations (cited, NOT reclaimed):
  - Proportional Navigation: Zarchan, Tactical & Strategic Missile Guidance (AIAA 2012);
    Palumbo et al., JHU APL Tech Digest 29(1) 2018.
  - GNSS plausibility (innovation chi-square): Joerger & Pervan, ION PLANS 2014.
  - Covariance Intersection: Julier & Uhlmann 1997.
  - Multi-target tracking / Mahalanobis gating: Bar-Shalom, Estimation w/ Applications
    to Tracking & Navigation (Wiley 2001).
  - Graph-Laplacian consensus / boids: Reynolds 1987; Olfati-Saber 2007; Zelazo 2014.
  - Weapon-Target Assignment: Manne, Operations Research 1958.
  - Post-Quantum: NIST FIPS 203 (ML-KEM), 204 (ML-DSA), 205 (SLH-DSA).

Register:  register(app, ns="killinchu")  /  register(app, ns="a11oy")
Routes:    GET /api/<ns>/v1/cuas/{summary,engage,plausibility,fusion,consensus,wta,pqbus}
"""
from __future__ import annotations
import math
import hashlib
from typing import Any

STATUS_LEGEND = {
    "SIMULATED": "killinchu effector is simulated; these compute feasibility/solutions, never actuate",
    "VERIFIED": "deterministic computation reproduces a documented numeric on call",
    "EXPERIMENTAL": "EXPERIMENTAL-tier SZL construct; NOT in the locked 8; Λ stays Conjecture 1",
}

SOURCES = {
    "Proportional Navigation (Zarchan; Palumbo JHU APL 2018)": "https://secwww.jhuapl.edu/techdigest/content/techdigest/pdf/V29-N01/29-01-Palumbo_Principles_Rev2018.pdf",
    "GNSS innovation chi-square (Joerger PLANS 2014)": "http://www.navlab.iit.edu/uploads/5/9/7/3/59735535/joerger_plans2014.pdf",
    "Covariance Intersection (Julier & Uhlmann 1997)": "https://dsp-book.narod.ru/HMDF/2379ch12.pdf",
    "Tracking / Mahalanobis (Bar-Shalom 2001)": "https://dl.acm.org/doi/10.5555/560900",
    "Graph-Laplacian consensus (Olfati-Saber 2007; Zelazo 2014)": "https://zelazo.net.technion.ac.il/files/2014/07/StuttgartMAS2014_L3.pdf",
    "Weapon-Target Assignment (Manne 1958)": "https://www.jstor.org/stable/167053",
    "NIST PQC FIPS 203/204/205 (ML-KEM/ML-DSA/SLH-DSA)": "https://csrc.nist.gov/pubs/fips/203/final",
    # Active-flux sensorless observer (F-η) — adopted-and-generalized, see below.
    "Active-flux sensorless control (Boldea et al., APEC 2001)": "https://doi.org/10.1109/APEC.2001.911711",
    "Li Yu (李彧) — PI-correction bandwidth in an active-flux observer (LinkedIn 2026)": "https://www.linkedin.com/pulse/how-should-bandwidth-pi-correction-loop-active-flux-observer-%E5%BD%A7-%E6%9D%8E-qxksc",
    "Revised Hybrid Active-Flux encoderless PMSM control (IEEE)": "https://ieeexplore.ieee.org/document/9319155",
    "TI InstaSPIN-FOC / FAST flux observer (SPRUHJ1)": "https://www.ti.com/lit/ug/spruhj1h/spruhj1h.pdf",
    # Platform dynamics (F-θ) — 6DOF quadcopter MBD + Moore-Penrose control allocation.
    "Ahmed Hassan — Quadcopter Modeling/Control/Simulation (Simulink 6DOF, Aerospace Blockset; LinkedIn 2026)": "https://www.linkedin.com/posts/ahmedhassan2002_aerospaceengineering-aerospace-uav-activity-7348481891039129600-TbmA",
    "Moore-Penrose pseudo-inverse control allocation (overview)": "https://en.wikipedia.org/wiki/Moore%E2%80%93Penrose_inverse",
    "Control allocation survey (Johansen & Fossen, Automatica 2013)": "https://doi.org/10.1016/j.automatica.2013.01.035",
    "Model-Based Design / V-cycle, MIL/SIL/HIL (MathWorks)": "https://www.mathworks.com/solutions/model-based-design.html",
}


# ---------------------------------------------------------------------------
# F-α  SZL-PN Engageability Gate (proportional navigation, SIMULATED effector)
# ---------------------------------------------------------------------------
def pn_accel_cmd(N: float, Vc: float, los_rate: float) -> float:
    """True Proportional Navigation lateral accel command  a_cmd = N * Vc * λ̇.
    N = effective navigation ratio (3-5 typical; Astral used 3.5), Vc = closing speed
    (m/s), los_rate = line-of-sight rate (rad/s). Cite Zarchan/Palumbo. [EXPERIMENTAL]"""
    return N * Vc * los_rate


def zero_effort_miss(rel_pos: float, rel_vel: float, t_go: float, a_T: float = 0.0) -> float:
    """Zero-Effort Miss  ZEM = R_rel + V_rel*t_go + 0.5*a_T*t_go^2 (1-D scalar form)."""
    return rel_pos + rel_vel * t_go + 0.5 * a_T * (t_go ** 2)


def szl_engageability(N: float, Vc: float, los_rate: float, t_go: float,
                      a_max: float, a_T: float = 0.0) -> dict[str, Any]:
    """SZL Engageability Gate: is an intercept feasible within accel limits?
    Returns the PN command, ZEM-implied required accel, and a feasibility verdict.
    EFFECTOR SIMULATED — this is a feasibility solver, not an actuation. [SIMULATED]"""
    a_cmd = pn_accel_cmd(N, Vc, los_rate)
    # ZEM-optimal command magnitude a = N/t_go^2 * ZEM (use rel kinematics proxy)
    zem = zero_effort_miss(Vc * t_go, -Vc, t_go, a_T)
    a_req = abs((N / max(t_go, 1e-6) ** 2) * zem)
    feasible = abs(a_cmd) <= a_max and a_req <= a_max
    return {"a_cmd": round(a_cmd, 4), "a_required": round(a_req, 4),
            "a_max": a_max, "feasible": bool(feasible), "N": N,
            "status": "SIMULATED", "effector": "SIMULATED"}


# ---------------------------------------------------------------------------
# F-β  SZL Plausibility Residual (GNSS spoof detection via innovation chi-square)
# ---------------------------------------------------------------------------
def innovation_chi_square(innovation: list[float], S_diag: list[float]) -> float:
    """Chi-square innovation statistic  χ² = γᵀ S⁻¹ γ  (diagonal S approximation).
    γ = measurement innovation, S = innovation covariance. Cite Joerger PLANS 2014."""
    if len(innovation) != len(S_diag):
        return float("nan")
    return sum((g * g) / s for g, s in zip(innovation, S_diag) if s > 0)


def szl_plausibility(innovation: list[float], S_diag: list[float],
                     threshold: float = 33.1) -> dict[str, Any]:
    """SZL Plausibility Residual: flag GNSS spoofing when χ² exceeds the detection
    threshold (default 33.1 ≈ χ²(3, P_FA=1e-5)). Honest detector, never fabricates a
    fix. [EXPERIMENTAL]"""
    chi2 = innovation_chi_square(innovation, S_diag)
    spoof = chi2 > threshold
    return {"chi_square": round(chi2, 4), "threshold": threshold,
            "spoof_suspected": bool(spoof),
            "recommendation": "switch to dead-reckoning" if spoof else "GNSS plausible",
            "status": "EXPERIMENTAL"}


# ---------------------------------------------------------------------------
# F-γ  SZL Track-Fusion Confidence (covariance intersection + Mahalanobis gate)
# ---------------------------------------------------------------------------
def covariance_intersection_1d(var_a: float, var_b: float, omega: float = 0.5) -> float:
    """Covariance Intersection (scalar)  P_C⁻¹ = ω P_A⁻¹ + (1-ω) P_B⁻¹  → returns P_C.
    Consistent decentralized fusion w/ unknown cross-correlation. Julier-Uhlmann 1997."""
    if var_a <= 0 or var_b <= 0:
        return float("inf")
    inv = omega / var_a + (1 - omega) / var_b
    return 1.0 / inv if inv > 0 else float("inf")


def mahalanobis_gate(z: list[float], z_hat: list[float], S_diag: list[float],
                     gate: float = 9.21) -> dict[str, Any]:
    """Mahalanobis association gate  d² = (z-ẑ)ᵀ S⁻¹ (z-ẑ) ≤ gate (χ²(2,0.99)=9.21).
    Cite Bar-Shalom 2001. [EXPERIMENTAL]"""
    d2 = sum(((a - b) ** 2) / s for a, b, s in zip(z, z_hat, S_diag) if s > 0)
    return {"d2": round(d2, 4), "gate": gate, "associate": bool(d2 <= gate),
            "status": "EXPERIMENTAL"}


def szl_fusion(var_a: float, var_b: float, omega: float = 0.5) -> dict[str, Any]:
    """SZL Track-Fusion Confidence: CI-fused variance + a normalized confidence in
    [0,1] (tighter fused variance ⇒ higher confidence). Honest uncertainty. Trust
    never 100% — confidence is hard-capped < 1.0. [EXPERIMENTAL]"""
    p_c = covariance_intersection_1d(var_a, var_b, omega)
    conf = min(0.999, 1.0 / (1.0 + p_c)) if p_c != float("inf") else 0.0
    return {"fused_variance": round(p_c, 6), "confidence": round(conf, 4),
            "trust_note": "never 100% by doctrine", "status": "EXPERIMENTAL"}


# ---------------------------------------------------------------------------
# F-δ  SZL Swarm-Consensus Λ (urgency-weighted graph-Laplacian, Khipu-quorum analogue)
# ---------------------------------------------------------------------------
def fiedler_value(adjacency: list[list[float]]) -> float:
    """Algebraic connectivity λ₂ (Fiedler value) of the graph Laplacian L = D - A,
    via power iteration on the deflated Laplacian. Convergence rate of consensus
    ẋ = -Lx. Cite Olfati-Saber 2007 / Zelazo 2014. Pure stdlib (no numpy)."""
    n = len(adjacency)
    if n < 2:
        return 0.0
    # Laplacian L = D - A
    L = [[0.0] * n for _ in range(n)]
    for i in range(n):
        deg = sum(adjacency[i])
        for j in range(n):
            L[i][j] = (deg if i == j else 0.0) - adjacency[i][j]
    # λ₁=0 with eigenvector 1; estimate λ₂ via inverse-free Rayleigh quotient on a
    # vector orthogonal to 1 (deterministic seed), few Laplacian power steps.
    v = [math.sin(i + 1.0) for i in range(n)]
    mean = sum(v) / n
    v = [x - mean for x in v]  # orthogonalize to the all-ones vector
    for _ in range(60):
        Lv = [sum(L[i][j] * v[j] for j in range(n)) for i in range(n)]
        m = sum(Lv) / n
        Lv = [x - m for x in Lv]
        nrm = math.sqrt(sum(x * x for x in Lv))
        if nrm < 1e-12:
            break
        v = [x / nrm for x in Lv]
    Lv = [sum(L[i][j] * v[j] for j in range(n)) for i in range(n)]
    num = sum(v[i] * Lv[i] for i in range(n))
    den = sum(x * x for x in v) or 1.0
    return abs(num / den)


def szl_consensus(adjacency: list[list[float]], min_tti: float = 1e9,
                  gamma: float = 1.0) -> dict[str, Any]:
    """SZL Swarm-Consensus Λ: urgency-weighted algebraic connectivity. Edge weights are
    boosted by (1 + γ/min_tti) so the swarm converges faster as the nearest threat's
    time-to-intercept shrinks. Returns λ₂ (convergence rate) + a Khipu-quorum analogue
    flag (connected ⇔ quorum-coherent). [EXPERIMENTAL]"""
    boost = 1.0 + (gamma / max(min_tti, 1e-6))
    A = [[w * boost for w in row] for row in adjacency]
    lam2 = fiedler_value(A)
    return {"lambda2": round(lam2, 6), "urgency_boost": round(boost, 4),
            "connected_quorum": bool(lam2 > 1e-6),
            "note": "Khipu-quorum analogue: connected ⇔ consensus reachable",
            "status": "EXPERIMENTAL"}


# ---------------------------------------------------------------------------
# F-ε  SZL-WTA Threat Triage (weapon-target assignment, SIMULATED)
# ---------------------------------------------------------------------------
def threat_value(base_value: float, tti: float) -> float:
    """Composite threat score  V = base / max(1, TTI)  (closer threats score higher)."""
    return base_value / max(1.0, tti)


def szl_wta(threats: list[dict], n_interceptors: int,
            p_kill: float = 0.7) -> dict[str, Any]:
    """SZL-WTA Threat Triage: greedy weapon-target assignment maximizing expected
    destroyed value Σ V_j(1 - (1-p_kill)^{x_j}). Cite Manne 1958. Allocation is a
    PLAN only — effector SIMULATED, never fires. [SIMULATED]"""
    scored = sorted(
        ({"id": t.get("id", i), "V": threat_value(t.get("base_value", 1.0), t.get("tti", 1.0)),
          "tti": t.get("tti", 1.0)} for i, t in enumerate(threats)),
        key=lambda x: x["V"], reverse=True)
    alloc = []
    remaining = max(0, int(n_interceptors))
    exp_value = 0.0
    for s in scored:
        if remaining <= 0:
            break
        shots = 1
        remaining -= shots
        exp_value += s["V"] * (1 - (1 - p_kill) ** shots)
        alloc.append({"threat": s["id"], "interceptors": shots, "V": round(s["V"], 4)})
    return {"allocation": alloc, "expected_destroyed_value": round(exp_value, 4),
            "unassigned_interceptors": remaining, "effector": "SIMULATED",
            "status": "SIMULATED"}


# ---------------------------------------------------------------------------
# F-ζ  SZL-PQ Receipt Bus (post-quantum-secure receipt over the Khipu chain)
# ---------------------------------------------------------------------------
PQ_SUITE = {
    "kem": "ML-KEM-768 (FIPS 203)", "sig": "ML-DSA-65 (FIPS 204)",
    "longterm_sig": "SLH-DSA-SHAKE-128s (FIPS 205)",
}


def szl_pq_receipt(command: str, prev_hash: str = "0" * 64) -> dict[str, Any]:
    """SZL-PQ Receipt Bus: an append-only, hash-chained command receipt designed for a
    post-quantum signature suite (ML-DSA-65 / ML-KEM-768 session / SLH-DSA timestamp).
    This computes the REAL SHA3-256 chain link now; the PQ SIGNATURE is labeled a
    PROXY until oqs-python keys are wired (founder/Forge-gated, never faked). [EXPERIMENTAL]"""
    digest = hashlib.sha3_256((prev_hash + "|" + command).encode()).hexdigest()
    return {"prev_hash": prev_hash, "command": command, "receipt_hash": digest,
            "pq_suite": PQ_SUITE,
            "pq_signature": "PROXY — real ML-DSA-65 signature pending oqs-python key (gated)",
            "chain": "SHA3-256 append-only (Khipu-compatible)",
            "status": "EXPERIMENTAL"}


# ---------------------------------------------------------------------------
# F-η  SZL Active-Flux Hybrid Observer (sensorless PMSM rotor estimation)
#
# ADOPTED-AND-GENERALIZED, not invented here. We borrow the active-flux observer
# blending law from the motor-control literature and re-express it as OUR own
# deterministic, citable crossover. NOTHING here is added to the locked-8;
# Λ stays Conjecture 1; the killinchu effector stays SIMULATED; there is NO live
# motor on the demo floor so every rotor/speed/flux number is MODELED/SIMULATED.
#
# Sources (cited, NOT reclaimed as an SZL theorem):
#   - Active flux ψ_act = ψ_f + (Ld − Lq)·id carries the rotor-angle information and
#     is the basis of the observer:  Boldea/Andreescu/Blaabjerg, "Active-flux"
#     sensorless control, IEEE/APEC 2001 — https://doi.org/10.1109/APEC.2001.911711
#   - The HYBRID current-model / voltage-model blend, driven by a PI correction loop
#     whose BANDWIDTH ω_c sets the crossover between the two models:
#     Li Yu (李彧), "How should the bandwidth of the PI correction loop in an
#     Active-Flux observer be selected?" (LinkedIn, 2026). Design rule: a LOWER PI
#     bandwidth lets the CURRENT model dominate to higher electrical frequency
#     (better LOW-speed accuracy); a HIGHER PI bandwidth hands off to the VOLTAGE
#     (back-EMF) model sooner (better HIGH-speed accuracy, if the voltage signal is
#     clean, e.g. TI InstaSPIN-FAST terminal-voltage sampling, SPRUHJ1).
#     Li Yu's reported Bode reference points (at f_e = 40 Hz electrical): 5 Hz BW →
#     current model ≈ −12.2 dB (voltage dominant); 30 Hz BW → current ≈ +0.163 dB,
#     voltage ≈ −3.72 dB (current still dominant at crossover). We surface those as
#     his published REFERENCE values; our own live curve below is a MODELED 1st-order
#     complementary blend (documented transfer function), not a refit of his plant.
#   - "Revised Hybrid Active Flux" encoderless PMSM technique (IEEE).
# ---------------------------------------------------------------------------
LI_YU_REFERENCE_BODE = {
    "note": "Li Yu (李彧) LinkedIn 2026 published reference points, at f_e = 40 Hz electrical",
    "bw_5hz": {"current_model_dB": -12.2, "comment": "voltage model dominant low-bandwidth at 40 Hz"},
    "bw_30hz": {"current_model_dB": 0.163, "voltage_model_dB": -3.72,
                "comment": "current model still dominant at the crossover"},
}


def active_flux(psi_f: float, Ld: float, Lq: float, id_cur: float) -> float:
    """Active flux  ψ_act = ψ_f + (Ld − Lq)·id  (Wb). For a PMSM this fictitious flux
    is aligned with the rotor d-axis and so carries the rotor-angle information; it is
    the quantity the hybrid observer estimates. Cite Boldea et al. APEC 2001
    (https://doi.org/10.1109/APEC.2001.911711). [EXPERIMENTAL · MODELED]"""
    return psi_f + (Ld - Lq) * id_cur


def pi_crossover_freq(pi_bandwidth_hz: float, ref_const: float = 150.0) -> float:
    """Map the PI correction-loop bandwidth ω_c (here as f_c in Hz) to the electrical
    crossover frequency f_x (Hz) at which the observer hands off from the CURRENT model
    to the VOLTAGE model. Per Li Yu's design rule the crossover moves DOWN as the PI
    bandwidth rises (higher BW → voltage trusted sooner): f_x = ref_const / f_c.
    ref_const is calibrated so the brief's reference pair {5 Hz BW → 30 Hz crossover,
    30 Hz BW → 5 Hz crossover} holds (5·30 = 30·5 = 150). MODELED. [EXPERIMENTAL]"""
    return ref_const / max(pi_bandwidth_hz, 1e-6)


def active_flux_blend(pi_bandwidth_hz: float, f_elec_hz: float,
                      ref_const: float = 150.0) -> dict[str, Any]:
    """Hybrid current-model / voltage-model active-flux blend at electrical frequency
    f_elec, for a PI correction bandwidth pi_bandwidth_hz. We model the blend as a
    1st-order complementary filter with corner ω_x = 2π·f_x (f_x = pi_crossover_freq):
        current-model weight  H_c = ω_x / √(ω_x² + ω_e²)   (low-pass: dominant for f_e < f_x)
        voltage-model weight  H_v = ω_e / √(ω_x² + ω_e²)   (high-pass: dominant for f_e > f_x)
    so |H_c|² + |H_v|² = 1 and the −3 dB crossover sits exactly at f_e = f_x. This is
    the textbook active-flux / InstaSPIN hand-off shape; magnitudes are reported in dB
    for a Bode-style plot. MODELED/SIMULATED — there is no live motor; this reproduces
    Li Yu's QUALITATIVE design rule, not his exact plant fit. [EXPERIMENTAL · MODELED]"""
    f_x = pi_crossover_freq(pi_bandwidth_hz, ref_const)
    w_x = 2.0 * math.pi * f_x
    w_e = 2.0 * math.pi * max(f_elec_hz, 0.0)
    denom = math.sqrt(w_x * w_x + w_e * w_e) or 1e-12
    h_c = w_x / denom
    h_v = w_e / denom
    def _dB(x: float) -> float:
        return round(20.0 * math.log10(x), 4) if x > 1e-12 else -120.0
    dominant = "current_model" if h_c >= h_v else "voltage_model"
    return {
        "pi_bandwidth_hz": round(pi_bandwidth_hz, 4),
        "f_elec_hz": round(f_elec_hz, 4),
        "crossover_hz": round(f_x, 4),
        "current_model_weight": round(h_c, 6),
        "voltage_model_weight": round(h_v, 6),
        "current_model_dB": _dB(h_c),
        "voltage_model_dB": _dB(h_v),
        "dominant": dominant,
        "regime": "low_speed" if f_elec_hz < f_x else "high_speed",
        "status": "MODELED",
    }


def szl_active_flux_observer(psi_f: float = 0.09, Ld: float = 0.0085, Lq: float = 0.012,
                             id_cur: float = -2.0, iq_cur: float = 18.0,
                             f_elec_hz: float = 40.0, pi_bandwidth_hz: float = 12.0,
                             pole_pairs: int = 4, ref_const: float = 150.0) -> dict[str, Any]:
    """SZL Active-Flux Hybrid Observer (MODELED/SIMULATED — no live motor).
    Computes the active flux ψ_act, a MODELED rotor electrical angle/speed estimate, and
    the current-vs-voltage model blend at the operating electrical frequency for the
    chosen PI-correction bandwidth. The angle estimate is the arctangent of the active-
    flux vector built from a deterministic, phase-consistent flux model (NOT a real
    encoder read). Mechanical speed = electrical speed / pole_pairs. Trust never 100%;
    effector SIMULATED; adds NOTHING to the locked-8. Cite Boldea APEC 2001 / Li Yu /
    Revised Hybrid Active Flux / TI InstaSPIN-FAST. [EXPERIMENTAL · MODELED]"""
    psi_act = active_flux(psi_f, Ld, Lq, id_cur)
    blend = active_flux_blend(pi_bandwidth_hz, f_elec_hz, ref_const)
    w_e = 2.0 * math.pi * f_elec_hz                       # electrical angular speed (rad/s)
    # MODELED rotor electrical angle from the active-flux vector components. The d-axis
    # active flux is ψ_act; a small q-axis leakage Lq·iq perturbs the apparent angle so the
    # observer has a non-trivial arctangent (purely illustrative, deterministic).
    psi_alpha = psi_act
    psi_beta = Lq * iq_cur
    theta_e = math.atan2(psi_beta, psi_alpha)            # rad, electrical
    rpm_mech = (w_e / max(pole_pairs, 1)) * 60.0 / (2.0 * math.pi)
    return {
        "psi_active_Wb": round(psi_act, 6),
        "rotor_angle_elec_rad": round(theta_e, 6),
        "rotor_angle_elec_deg": round(math.degrees(theta_e), 4),
        "speed_elec_rad_s": round(w_e, 4),
        "speed_mech_rpm": round(rpm_mech, 4),
        "pole_pairs": int(pole_pairs),
        "blend": blend,
        "li_yu_reference": LI_YU_REFERENCE_BODE,
        "effector": "SIMULATED",
        "data_label": "MODELED/SIMULATED — no live motor on the demo floor",
        "doctrine": "adopted active-flux observer-blending law (Li Yu / APEC 2001 911711); "
                    "generalized under SZL governance; NOT added to the locked-8",
        "status": "MODELED",
    }


# ---------------------------------------------------------------------------
# F-θ  SZL Platform Dynamics — 6DOF quadcopter/interceptor model + Moore-Penrose
#       pseudo-inverse CONTROL ALLOCATION (thrust distribution). MODELED/SIMULATED.
#
# ADOPTED-AND-GENERALIZED, NOT invented here. Ahmed Hassan's Simulink Quadcopter MBD
# project (full 6DOF model in Aerospace Blockset; control ALLOCATION via the
# Moore-Penrose pseudo-inverse for optimal thrust distribution; MIL/SIL via Embedded
# Coder) is the on-domain technique we fold in: it rounds out the killinchu drone-
# platform puzzle — estimate (active-flux, F-η) → 6DOF dynamics + control allocation
# (this) → CBF-QP safety clamp (autonomy) → BFT multi-sensor fusion → governed/ROE
# engage (SIMULATED human-on-loop). Pure stdlib (no numpy): the 4-rotor mixing matrix
# is small and fixed, so we compute the pseudo-inverse in closed form.
#
# HONEST: there is NO live airframe on the demo floor. Every angular rate, attitude,
# rotor thrust here is a MODELED model output, NOT live telemetry. The effector stays
# SIMULATED human-on-loop — this computes a thrust allocation + a one-step state
# derivative, it NEVER actuates a motor or a vessel. EXPERIMENTAL-tier; adds NOTHING
# to the locked-8; Λ stays Conjecture 1; trust never 100%.
# ---------------------------------------------------------------------------
def quad_mixing_matrix(arm_length: float = 0.25, k_thrust: float = 1.0,
                       k_torque: float = 0.02) -> list[list[float]]:
    """Quadcopter (X-config) control-effectiveness / mixing matrix B (4×4) mapping the
    four rotor thrusts f = [f1,f2,f3,f4] (front-right, back-left, front-left, back-right)
    to the body wrench tau = [T, L, M, N] = [total thrust, roll, pitch, yaw torque]:
        T = f1 + f2 + f3 + f4
        L (roll, about x)  =  arm · ( -f1 + f2 - f3 + f4 ) · k_thrust   (right rotors down)
        M (pitch, about y) =  arm · ( f1 + f2 - f3 - f4 ) · k_thrust    (front rotors up)
        N (yaw, about z)   =  k_torque · ( f1 + f2 - f3 - f4 )  via reaction torque sign
    The exact signs encode the X-frame geometry + the CW/CCW spin pattern. This is the
    standard quadrotor control-allocation matrix. MODELED. [EXPERIMENTAL]"""
    a = arm_length * k_thrust
    kt = k_torque
    # rows: [T, L(roll), M(pitch), N(yaw)] ; cols: f1 f2 f3 f4
    return [
        [1.0,  1.0,  1.0,  1.0],     # total thrust
        [-a,   a,   -a,    a],        # roll torque
        [a,    a,   -a,   -a],        # pitch torque
        [kt,  -kt,  -kt,   kt],       # yaw reaction torque (CW/CCW pattern)
    ]


def _mat_mul(A: list[list[float]], B: list[list[float]]) -> list[list[float]]:
    return [[sum(A[i][k] * B[k][j] for k in range(len(B)))
             for j in range(len(B[0]))] for i in range(len(A))]


def _transpose(A: list[list[float]]) -> list[list[float]]:
    return [[A[i][j] for i in range(len(A))] for j in range(len(A[0]))]


def _inv(A: list[list[float]]) -> list[list[float]]:
    """Gauss-Jordan inverse of a small square matrix (no numpy). Raises on singular."""
    n = len(A)
    M = [list(map(float, A[i])) + [1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(M[r][col]))
        if abs(M[piv][col]) < 1e-12:
            raise ValueError("singular matrix")
        M[col], M[piv] = M[piv], M[col]
        pv = M[col][col]
        M[col] = [x / pv for x in M[col]]
        for r in range(n):
            if r != col:
                fac = M[r][col]
                M[r] = [a - fac * b for a, b in zip(M[r], M[col])]
    return [row[n:] for row in M]


def moore_penrose_pinv(B: list[list[float]]) -> list[list[float]]:
    """Moore-Penrose pseudo-inverse B+ of a (possibly non-square) matrix, pure stdlib.
    For a wide/tall full-rank B we use the closed forms:
        right pinv (rows<=cols, full row rank):  B+ = B^T (B B^T)^-1
        left  pinv (rows> cols, full col rank):  B+ = (B^T B)^-1 B^T
    For a square invertible B both reduce to B^-1. This is the minimum-norm /
    least-squares control allocator. Cite Moore-Penrose; Johansen & Fossen (2013).
    [EXPERIMENTAL]"""
    rows, cols = len(B), len(B[0])
    Bt = _transpose(B)
    if rows <= cols:
        # right inverse: B^T (B B^T)^-1
        BBt = _mat_mul(B, Bt)
        return _mat_mul(Bt, _inv(BBt))
    else:
        # left inverse: (B^T B)^-1 B^T
        BtB = _mat_mul(Bt, B)
        return _mat_mul(_inv(BtB), Bt)


def szl_control_allocation(tau_cmd: list[float], arm_length: float = 0.25,
                           k_thrust: float = 1.0, k_torque: float = 0.02,
                           f_min: float = 0.0, f_max: float = 12.0) -> dict[str, Any]:
    """Moore-Penrose pseudo-inverse CONTROL ALLOCATION: given a commanded body wrench
    tau_cmd = [T, L, M, N] (total thrust + roll/pitch/yaw torque), solve for the
    minimum-norm rotor-thrust vector f = B+ · tau that realizes it, then saturate each
    rotor to [f_min, f_max] and report the achieved wrench tau_ach = B · f_sat and the
    allocation residual. This is the optimal (least-norm) thrust distribution — the
    classic Moore-Penrose allocator from Hassan's Simulink MBD project. MODELED/SIMULATED:
    NO live airframe; this computes a solution, it never actuates. [EXPERIMENTAL · MODELED]"""
    B = quad_mixing_matrix(arm_length, k_thrust, k_torque)
    Bp = moore_penrose_pinv(B)
    tau = [float(x) for x in (list(tau_cmd) + [0.0, 0.0, 0.0, 0.0])[:4]]
    # f = B+ tau
    f_raw = [sum(Bp[i][j] * tau[j] for j in range(4)) for i in range(4)]
    f_sat = [min(max(v, f_min), f_max) for v in f_raw]
    saturated = [bool(abs(v - s) > 1e-9) for v, s in zip(f_raw, f_sat)]
    # achieved wrench tau_ach = B f_sat
    tau_ach = [sum(B[i][j] * f_sat[j] for j in range(4)) for i in range(4)]
    resid = [round(tau_ach[i] - tau[i], 6) for i in range(4)]
    resid_norm = math.sqrt(sum(r * r for r in resid))
    labels = ["thrust_T", "roll_L", "pitch_M", "yaw_N"]
    rotors = ["f1_front_right", "f2_back_left", "f3_front_left", "f4_back_right"]
    return {
        "tau_cmd": {labels[i]: round(tau[i], 4) for i in range(4)},
        "rotor_thrust_raw": {rotors[i]: round(f_raw[i], 6) for i in range(4)},
        "rotor_thrust_sat": {rotors[i]: round(f_sat[i], 6) for i in range(4)},
        "any_rotor_saturated": any(saturated),
        "tau_achieved": {labels[i]: round(tau_ach[i], 4) for i in range(4)},
        "allocation_residual": {labels[i]: resid[i] for i in range(4)},
        "residual_norm": round(resid_norm, 6),
        "method": "Moore-Penrose pseudo-inverse f = B⁺·τ (minimum-norm least-squares), then saturate",
        "mixing_matrix_B": B,
        "effector": "SIMULATED",
        "data_label": "MODELED/SIMULATED — no live airframe; computes a thrust solution, never actuates",
        "doctrine": "adopted Hassan quadcopter MBD control-allocation; NOT added to the locked-8; Λ Conjecture 1",
        "status": "MODELED",
    }


def szl_6dof_step(state: dict[str, float] | None = None, tau: list[float] | None = None,
                  mass: float = 1.2, ixx: float = 0.015, iyy: float = 0.015,
                  izz: float = 0.028, dt: float = 0.01, g: float = 9.81) -> dict[str, Any]:
    """One-step 6DOF rigid-body dynamics for a quad/interceptor (MODELED/SIMULATED).
    State = body-frame translational velocity (u,v,w), angular rates (p,q,r), and
    Euler attitude (phi,theta,psi). Given a body wrench tau=[T,L,M,N] (total thrust
    along body -z + roll/pitch/yaw torques), integrate ONE Euler step of the Newton-
    Euler equations:
        translational:  m(ẇ + ...)  — here reported as body accelerations
            u̇ = r*v - q*w - g*sin(theta)
            v̇ = p*w - r*u + g*cos(theta)*sin(phi)
            ẇ = q*u - p*v + g*cos(theta)*cos(phi) - T/m
        rotational (Euler):
            ṗ = (L - (izz-iyy)*q*r)/ixx
            q̇ = (M - (ixx-izz)*p*r)/iyy
            ṙ = (N - (iyy-ixx)*p*q)/izz
        attitude kinematics:  phi̇ = p + ... (small-angle body-rate ≈ Euler-rate).
    Returns the derivatives + the integrated next state. This is the standard
    Aerospace-Blockset 6DOF body model (Hassan MBD). NO live airframe; deterministic
    model output, never actuated. [EXPERIMENTAL · MODELED]"""
    s = {"u": 0.0, "v": 0.0, "w": 0.0, "p": 0.0, "q": 0.0, "r": 0.0,
         "phi": 0.0, "theta": 0.0, "psi": 0.0}
    if state:
        s.update({k: float(v) for k, v in state.items() if k in s})
    T, L, M, N = ([float(x) for x in (list(tau or []) + [0.0] * 4)[:4]])
    u, v, w = s["u"], s["v"], s["w"]
    p, q, r = s["p"], s["q"], s["r"]
    phi, theta, psi = s["phi"], s["theta"], s["psi"]
    # translational body accelerations
    du = r * v - q * w - g * math.sin(theta)
    dv = p * w - r * u + g * math.cos(theta) * math.sin(phi)
    dw = q * u - p * v + g * math.cos(theta) * math.cos(phi) - T / max(mass, 1e-9)
    # rotational (Newton-Euler)
    dp = (L - (izz - iyy) * q * r) / max(ixx, 1e-9)
    dq = (M - (ixx - izz) * p * r) / max(iyy, 1e-9)
    dr = (N - (iyy - ixx) * p * q) / max(izz, 1e-9)
    # attitude kinematics (Euler-angle rates; full transport matrix)
    dphi = p + math.sin(phi) * math.tan(theta) * q + math.cos(phi) * math.tan(theta) * r
    dtheta = math.cos(phi) * q - math.sin(phi) * r
    dpsi = (math.sin(phi) / max(math.cos(theta), 1e-6)) * q + (math.cos(phi) / max(math.cos(theta), 1e-6)) * r
    deriv = {"du": du, "dv": dv, "dw": dw, "dp": dp, "dq": dq, "dr": dr,
             "dphi": dphi, "dtheta": dtheta, "dpsi": dpsi}
    nxt = {
        "u": u + du * dt, "v": v + dv * dt, "w": w + dw * dt,
        "p": p + dp * dt, "q": q + dq * dt, "r": r + dr * dt,
        "phi": phi + dphi * dt, "theta": theta + dtheta * dt, "psi": psi + dpsi * dt,
    }
    return {
        "state_in": {k: round(val, 6) for k, val in s.items()},
        "tau": {"thrust_T": round(T, 4), "roll_L": round(L, 4),
                "pitch_M": round(M, 4), "yaw_N": round(N, 4)},
        "derivatives": {k: round(val, 6) for k, val in deriv.items()},
        "state_next": {k: round(val, 6) for k, val in nxt.items()},
        "params": {"mass": mass, "Ixx": ixx, "Iyy": iyy, "Izz": izz, "dt": dt, "g": g},
        "model": "Newton-Euler rigid-body 6DOF (body frame); Aerospace-Blockset shape (Hassan MBD)",
        "effector": "SIMULATED",
        "data_label": "MODELED/SIMULATED — no live airframe; deterministic model step, never actuated",
        "doctrine": "adopted Hassan quadcopter 6DOF MBD; NOT added to the locked-8; Λ Conjecture 1",
        "status": "MODELED",
    }


def summary(ns: str = "killinchu") -> dict[str, Any]:
    """Headline of all six SZL counter-UAS formulas + honest provenance/legend.
    `ns` names the serving app so the title is accurate on both killinchu and a11oy."""
    return {
        "title": f"SZL Counter-UAS C2 Formulas ({ns}) — our own constructs, classical inspirations cited",
        "status_legend": STATUS_LEGEND, "sources": SOURCES,
        "doctrine": {"locked_proven": 8, "lambda": "Conjecture 1", "khipu_bft": "Conjecture 2",
                     "effector": "SIMULATED", "trust": "never 100%"},
        "formulas": {
            "engage": "SZL-PN Engageability Gate (proportional navigation)",
            "plausibility": "SZL Plausibility Residual (GNSS spoof chi-square)",
            "fusion": "SZL Track-Fusion Confidence (covariance intersection)",
            "consensus": "SZL Swarm-Consensus Λ (urgency-weighted Laplacian)",
            "wta": "SZL-WTA Threat Triage (weapon-target assignment, SIMULATED)",
            "pqbus": "SZL-PQ Receipt Bus (post-quantum receipt chain)",
            "active_flux": "SZL Active-Flux Hybrid Observer (sensorless PMSM; ADOPTED Li Yu/APEC 2001, MODELED)",
            "platform_allocation": "SZL Platform Dynamics — Moore-Penrose control allocation (ADOPTED Hassan MBD, MODELED)",
            "platform_6dof": "SZL Platform Dynamics — 6DOF Newton-Euler quad/interceptor step (ADOPTED Hassan MBD, MODELED)",
        },
        "examples": {
            "engage": szl_engageability(N=3.5, Vc=300.0, los_rate=0.02, t_go=4.0, a_max=200.0),
            "plausibility": szl_plausibility([1.0, 1.0, 1.0], [0.1, 0.1, 0.1]),
            "consensus": szl_consensus([[0, 1, 0], [1, 0, 1], [0, 1, 0]], min_tti=5.0),
        },
    }


def register(app, ns: str) -> None:
    """Attach the counter-UAS routes under /api/<ns>/v1/cuas/* via add_api_route."""
    base = f"/api/{ns}/v1/cuas"
    app.add_api_route(f"{base}/summary", lambda: summary(ns), methods=["GET"])
    app.add_api_route(f"{base}/engage",
                      lambda N, Vc, los_rate, t_go, a_max: szl_engageability(
                          float(N), float(Vc), float(los_rate), float(t_go), float(a_max)),
                      methods=["GET"])
    app.add_api_route(f"{base}/plausibility",
                      lambda chi="3.0": {"demo": szl_plausibility([float(chi) ** 0.5] * 3, [1.0, 1.0, 1.0])},
                      methods=["GET"])
    app.add_api_route(f"{base}/fusion",
                      lambda var_a, var_b, omega="0.5": szl_fusion(float(var_a), float(var_b), float(omega)),
                      methods=["GET"])
    app.add_api_route(f"{base}/consensus",
                      lambda min_tti="5.0": szl_consensus([[0, 1, 0], [1, 0, 1], [0, 1, 0]], float(min_tti)),
                      methods=["GET"])
    app.add_api_route(f"{base}/wta",
                      lambda n="3": szl_wta([{"id": "T1", "base_value": 5, "tti": 2},
                                              {"id": "T2", "base_value": 3, "tti": 1},
                                              {"id": "T3", "base_value": 8, "tti": 4}], int(n)),
                      methods=["GET"])
    app.add_api_route(f"{base}/pqbus",
                      lambda cmd="intercept T1": szl_pq_receipt(str(cmd)), methods=["GET"])
    # F-η Active-Flux Hybrid Observer (ADOPTED Li Yu/APEC 2001; MODELED/SIMULATED — no live motor).
    app.add_api_route(
        f"{base}/active-flux",
        lambda f_elec="40.0", bw="12.0", id_cur="-2.0", iq_cur="18.0", pole_pairs="4":
            szl_active_flux_observer(f_elec_hz=float(f_elec), pi_bandwidth_hz=float(bw),
                                     id_cur=float(id_cur), iq_cur=float(iq_cur),
                                     pole_pairs=int(pole_pairs)),
        methods=["GET"])
    # Bode-style sweep: blend vs electrical frequency for a chosen PI bandwidth (MODELED).
    def _active_flux_bode(bw: str = "12.0", f_min: str = "1.0", f_max: str = "120.0",
                          points: str = "60"):
        bwf = float(bw); fmn = float(f_min); fmx = float(f_max); n = max(2, int(points))
        # logarithmic sweep over electrical frequency
        lo = math.log10(max(fmn, 1e-3)); hi = math.log10(max(fmx, fmn + 1e-3))
        curve = []
        for i in range(n):
            fe = 10.0 ** (lo + (hi - lo) * i / (n - 1))
            curve.append(active_flux_blend(bwf, fe))
        return {"pi_bandwidth_hz": bwf, "crossover_hz": round(pi_crossover_freq(bwf), 4),
                "points": n, "curve": curve, "li_yu_reference": LI_YU_REFERENCE_BODE,
                "data_label": "MODELED/SIMULATED — no live motor", "status": "MODELED"}
    app.add_api_route(f"{base}/active-flux/bode", _active_flux_bode, methods=["GET"])
    # F-θ Platform Dynamics — Moore-Penrose control allocation + 6DOF step (ADOPTED Hassan MBD; MODELED).
    def _alloc(T: str = "11.8", L: str = "0.2", M: str = "0.0", N: str = "0.05",
               arm: str = "0.25", k_torque: str = "0.02", f_max: str = "12.0"):
        try:
            return szl_control_allocation([float(T), float(L), float(M), float(N)],
                                          arm_length=float(arm), k_torque=float(k_torque),
                                          f_max=float(f_max))
        except (ValueError, TypeError) as e:
            return {"error": {"code": "validation_error", "detail": str(e)}}
    app.add_api_route(f"{base}/allocation", _alloc, methods=["GET"])

    def _sixdof(T: str = "11.77", L: str = "0.0", M: str = "0.0", N: str = "0.0",
                p: str = "0.0", q: str = "0.0", r: str = "0.0",
                phi: str = "0.0", theta: str = "0.1", psi: str = "0.0", dt: str = "0.01"):
        try:
            return szl_6dof_step(
                state={"p": float(p), "q": float(q), "r": float(r),
                       "phi": float(phi), "theta": float(theta), "psi": float(psi)},
                tau=[float(T), float(L), float(M), float(N)], dt=float(dt))
        except (ValueError, TypeError) as e:
            return {"error": {"code": "validation_error", "detail": str(e)}}
    app.add_api_route(f"{base}/dynamics", _sixdof, methods=["GET"])


def _selftest() -> None:
    # PN: a_cmd = N*Vc*los = 3.5*300*0.02 = 21.0
    assert abs(pn_accel_cmd(3.5, 300.0, 0.02) - 21.0) < 1e-9
    # engageability feasible at high a_max, infeasible at tiny a_max
    assert szl_engageability(3.5, 300.0, 0.02, 4.0, 200.0)["feasible"] is True
    assert szl_engageability(3.5, 300.0, 0.5, 4.0, 1.0)["feasible"] is False
    # plausibility: large innovation trips spoof flag
    assert szl_plausibility([10, 10, 10], [0.1, 0.1, 0.1])["spoof_suspected"] is True
    assert szl_plausibility([0.1, 0.1, 0.1], [1, 1, 1])["spoof_suspected"] is False
    # covariance intersection: fused var <= min(var_a,var_b)/... is tighter than worst
    assert covariance_intersection_1d(4.0, 4.0, 0.5) <= 4.0
    # mahalanobis gate
    assert mahalanobis_gate([0, 0], [0, 0], [1, 1])["associate"] is True
    assert mahalanobis_gate([10, 10], [0, 0], [1, 1])["associate"] is False
    # fusion confidence strictly < 1 (trust never 100%)
    assert szl_fusion(0.001, 0.001)["confidence"] < 1.0
    # consensus: connected triangle path has lambda2 > 0
    assert szl_consensus([[0, 1, 0], [1, 0, 1], [0, 1, 0]], 5.0)["connected_quorum"] is True
    # disconnected graph -> lambda2 ~ 0
    assert szl_consensus([[0, 0], [0, 0]], 5.0)["connected_quorum"] is False
    # WTA: highest-value/nearest threat gets an interceptor; effector simulated
    w = szl_wta([{"id": "A", "base_value": 5, "tti": 1}, {"id": "B", "base_value": 1, "tti": 10}], 1)
    assert w["allocation"][0]["threat"] == "A" and w["effector"] == "SIMULATED"
    # PQ receipt: deterministic SHA3 chain, signature labeled PROXY
    r = szl_pq_receipt("intercept T1")
    assert len(r["receipt_hash"]) == 64 and "PROXY" in r["pq_signature"]
    # F-η Active-Flux observer (ADOPTED Li Yu/APEC 2001; MODELED): ψ_act and crossover law.
    assert abs(active_flux(0.09, 0.0085, 0.012, -2.0) - (0.09 + (0.0085 - 0.012) * -2.0)) < 1e-12
    # crossover law: 5 Hz BW -> 30 Hz crossover; 30 Hz BW -> 5 Hz crossover (Li Yu reference pair)
    assert abs(pi_crossover_freq(5.0) - 30.0) < 1e-9
    assert abs(pi_crossover_freq(30.0) - 5.0) < 1e-9
    # design rule: LOWER bandwidth keeps the current model dominant to higher f_elec.
    b_lowbw = active_flux_blend(5.0, 20.0)   # 20 Hz < 30 Hz crossover -> current dominant
    b_hibw = active_flux_blend(30.0, 20.0)   # 20 Hz > 5 Hz crossover  -> voltage dominant
    assert b_lowbw["dominant"] == "current_model" and b_lowbw["regime"] == "low_speed"
    assert b_hibw["dominant"] == "voltage_model" and b_hibw["regime"] == "high_speed"
    # weights are a unit complementary pair: H_c^2 + H_v^2 = 1
    assert abs(b_lowbw["current_model_weight"] ** 2 + b_lowbw["voltage_model_weight"] ** 2 - 1.0) < 1e-4
    obs = szl_active_flux_observer()
    assert obs["status"] == "MODELED" and obs["effector"] == "SIMULATED"
    assert "MODELED/SIMULATED" in obs["data_label"]
    # F-θ Platform Dynamics (ADOPTED Hassan MBD; MODELED): pseudo-inverse round-trip.
    B = quad_mixing_matrix()
    Bp = moore_penrose_pinv(B)
    # B is 4x4 invertible -> B B+ = I (within tolerance)
    BBp = _mat_mul(B, Bp)
    for i in range(4):
        for j in range(4):
            assert abs(BBp[i][j] - (1.0 if i == j else 0.0)) < 1e-6
    # pure-thrust command -> equal rotor split, zero torque residual
    al = szl_control_allocation([12.0, 0.0, 0.0, 0.0])
    rs = al["rotor_thrust_sat"]
    assert abs(rs["f1_front_right"] - 3.0) < 1e-6 and al["residual_norm"] < 1e-6
    assert al["status"] == "MODELED" and al["effector"] == "SIMULATED"
    # roll command on a hover baseline (so no rotor saturates) -> achieved wrench == commanded
    al2 = szl_control_allocation([8.0, 0.5, 0.0, 0.0])
    assert not al2["any_rotor_saturated"]
    assert abs(al2["tau_achieved"]["roll_L"] - 0.5) < 1e-6
    assert abs(al2["tau_achieved"]["thrust_T"] - 8.0) < 1e-6 and al2["residual_norm"] < 1e-6
    # 6DOF: hover thrust ~ m*g cancels gravity in w-dot (theta=0)
    st = szl_6dof_step(state={"theta": 0.0}, tau=[1.2 * 9.81, 0.0, 0.0, 0.0])
    assert abs(st["derivatives"]["dw"]) < 1e-6 and st["status"] == "MODELED"
    # roll torque produces a positive p-dot
    st2 = szl_6dof_step(tau=[0.0, 0.01, 0.0, 0.0])
    assert st2["derivatives"]["dp"] > 0.0 and st2["effector"] == "SIMULATED"
    print("szl_cuas_formulas: ALL OK (27 checks)")


if __name__ == "__main__":
    _selftest()
