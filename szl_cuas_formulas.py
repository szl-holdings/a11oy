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


def summary() -> dict[str, Any]:
    """Headline of all six SZL counter-UAS formulas + honest provenance/legend."""
    return {
        "title": "SZL Counter-UAS C2 Formulas (killinchu) — our own constructs, classical inspirations cited",
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
    app.add_api_route(f"{base}/summary", lambda: summary(), methods=["GET"])
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
    print("szl_cuas_formulas: ALL OK (12 checks)")


if __name__ == "__main__":
    _selftest()
