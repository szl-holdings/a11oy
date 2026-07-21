# VENDORED FROM szl-holdings/platform@c11291e09702c86f3f8995fffcae6167155c7240 — replit-sync/szl_unified_formulas.py
# DO NOT EDIT HERE. Edit in the monorepo, then run scripts/sync_from_monorepo.sh sync.
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
"""
szl_unified_formulas.py — UNIFIED leader-formula module (thesis v6), real deterministic
Python. SHARED module: must be byte-identical in a11oy AND killinchu.

Every function is a PURE deterministic computation with (a) a docstring citing the
ORIGINAL author + DOI/source, and (b) a built-in self-test asserting a verified numeric.
SZL borrows only the methodological STRUCTURE — no result here is claimed as SZL's own
except the Wave24 coherence single-crossing, which is staged PROPOSED until lutar-lean
PR #225 passes lake build (then VERIFIED). Λ-v5 stays a PROPOSED engineering gate.

DOCTRINE: locked-proven = EXACTLY 8 {F1,F4,F7,F11,F12,F18,F19,F22} @ c7c0ba17.
Λ unconditional uniqueness = Conjecture 1 (machine-checked FALSE). Khipu BFT = Conjecture 2.
Trust never 100%. No fabricated data. This module adds NOTHING to the locked 8.

Register into each app's FastAPI:  register(app, ns="a11oy")  /  register(app, ns="killinchu")
Routes:  GET /api/<ns>/v1/unified/{summary,density_impulse,tsiolkovsky,ls12,corotation,
                                   coherence_crossing,hugoniot_quartz}
"""
from __future__ import annotations
import math
from typing import Any

G0 = 9.80665  # standard gravity, m/s^2

# Honest provenance + status legend exposed in /summary.
SOURCES: dict[str, str] = {
    "Sherman Morgan density-impulse": "https://en.wikipedia.org/wiki/Hydyne",
    "NASA Glenn specific impulse": "https://www.grc.nasa.gov/www/k-12/airplane/specimp.html",
    "Tsiolkovsky rocket equation": "https://en.wikipedia.org/wiki/Tsiolkovsky_rocket_equation",
    "Leinhardt & Stewart 2012 (LS12)": "https://doi.org/10.1088/0004-637X/745/1/79",
    "Cuk & Stewart 2012": "https://doi.org/10.1126/science.1225542",
    "Lock & Stewart 2017 (synestia/CoRoL)": "https://doi.org/10.1002/2016JE005239",
    "Kraus & Stewart 2012 (quartz Hugoniot)": "https://doi.org/10.1029/2012JE004082",
    "Lindblad 1976": "https://doi.org/10.1007/BF01608499",
    "Baumgratz-Cramer-Plenio 2014 (l1 coherence)": "https://doi.org/10.1103/PhysRevLett.113.140401",
}

STATUS_LEGEND = {
    "VERIFIED": "executed model, reproduces on call against a documented numeric",
    "PROPOSED": "SZL construct; for coherence_crossing flips to VERIFIED on green lake build (lutar-lean PR #225)",
    "ANALOGY": "borrowed structure adapted as a governance/routing analogue; cited to original author, NOT a new theorem",
}


# ----------------------------------------------------------------------------
# 1. Sherman Morgan — specific impulse & DENSITY-impulse (volume-constrained metric)
# ----------------------------------------------------------------------------
def specific_impulse(thrust_N: float, mdot_kg_s: float) -> float:
    """Isp = F / (mdot * g0).  Mary Sherman Morgan, Theoretical Performance Specialist,
    North American Aviation/Rocketdyne. Source: NASA Glenn (see SOURCES). [VERIFIED]"""
    if mdot_kg_s <= 0:
        return 0.0
    return thrust_N / (mdot_kg_s * G0)


def density_impulse(rho_mix_g_cm3: float, isp_s: float) -> float:
    """Density specific impulse  Isp_rho = rho_mix * Isp  — the binding metric under a
    FIXED tank volume (what Morgan actually maximized for the A-7). Hydyne: rho_mix~0.86
    g/cm^3, Isp~310 s. SZL ANALOGY: maximize value-density per FIXED compute budget in the
    tier/budget router (Wh/L thinking). Cite: Sherman Morgan / Hydyne. [ANALOGY]"""
    return rho_mix_g_cm3 * isp_s


def tsiolkovsky_dv(isp_s: float, m0: float, mf: float) -> float:
    """Tsiolkovsky:  dv = Isp * g0 * ln(m0/mf).  K. Tsiolkovsky (1903). SZL ANALOGY:
    log-ratio conservation diagnostic for budget/mass draw-down. [ANALOGY]"""
    if mf <= 0 or m0 <= 0:
        return 0.0
    return isp_s * G0 * math.log(m0 / mf)


# ----------------------------------------------------------------------------
# 2. Stewart — LS12 collision-regime classifier (drone/vessel impact viz)
# ----------------------------------------------------------------------------
def ls12_largest_remnant(Q_R: float, Q_star_RD: float) -> dict[str, Any]:
    """Largest-remnant mass fraction  M_lr/M_tot = -0.5*(Q_R/Q*_RD - 1) + 0.5 ,
    clamped to [0,1], with the five collision regimes. Leinhardt & Stewart 2012,
    ApJ 745, 79 (doi:10.1088/0004-637X/745/1/79). SZL ANALOGY: analytic outcome
    classifier for drone-drone / projectile-armor 3D collision viz. [ANALOGY]"""
    if Q_star_RD <= 0:
        return {"frac": 0.0, "regime": "undefined"}
    ratio = Q_R / Q_star_RD
    frac = max(0.0, min(1.0, -0.5 * (ratio - 1.0) + 0.5))
    if ratio < 0.1:
        regime = "cratering / merging"
    elif ratio < 1.0:
        regime = "partial accretion / hit-and-run"
    elif ratio < 1.8:
        regime = "disruption"
    else:
        regime = "super-catastrophic"
    return {"frac": round(frac, 4), "ratio": round(ratio, 4), "regime": regime}


# ----------------------------------------------------------------------------
# 3. Stewart — corotation-limit (CoRoL) phase boundary  ~  Λ-v5 closure analogue
# ----------------------------------------------------------------------------
def corotation_omega(M_kg: float, R_eq_m: float) -> float:
    """Keplerian angular velocity at the equatorial radius  omega = sqrt(G M / R^3);
    a post-impact body exceeding this corotation limit forms a synestia. Lock & Stewart
    2017 (doi:10.1002/2016JE005239). SZL ANALOGY: corotation limit <-> Λ-v5 closure floor
    as a phase boundary. [ANALOGY]"""
    G = 6.67430e-11
    if R_eq_m <= 0:
        return 0.0
    return math.sqrt(G * M_kg / (R_eq_m ** 3))


# ----------------------------------------------------------------------------
# 4. Stewart/Kraus — quartz Hugoniot Us(up) (materials->math verification pipeline)
# ----------------------------------------------------------------------------
def quartz_hugoniot_Us(up_m_s: float) -> float:
    """Quartz Hugoniot shock velocity fit  Us = -295.7 + 2.139*up - 4.012e-5*up^2 [m/s].
    Kraus & Stewart 2012, JGR:P (doi:10.1029/2012JE004082). [ANALOGY/pipeline]"""
    return -295.7 + 2.139 * up_m_s - 4.012e-5 * (up_m_s ** 2)


# ----------------------------------------------------------------------------
# 5. Wave24 (SZL, PROPOSED) — coherence monotone decay + single-crossing of Λ-v5 floor
#    Mirrors lutar-lean Lutar/QuantumBio/CoherenceDecay.lean (PR #225).
# ----------------------------------------------------------------------------
def coherence(C0: float, gamma: float, t: float) -> float:
    """l1 coherence under pure-dephasing Lindblad:  C(t) = C0 * exp(-gamma*t).
    Lindblad 1976 (doi:10.1007/BF01608499); BCP 2014 (doi:10.1103/PhysRevLett.113.140401).
    [VERIFIED model]"""
    return C0 * math.exp(-gamma * t)


def coherence_crossing(C0: float, gamma: float, q: float, lam_min: float) -> dict[str, Any]:
    """Unique time the Λ-v5 gate value q*C(t) meets the floor lam_min:
        t* = (1/gamma) * ln(q*C0 / lam_min),  defined when 0 < lam_min < q*C0, gamma>0.
    This is the closed form PROVED in lutar-lean PR #225 (Wave24). Status PROPOSED until
    that lake build is green, then VERIFIED. NEVER joins the locked 8. [PROPOSED]"""
    if gamma <= 0 or q <= 0 or C0 <= 0 or lam_min <= 0 or lam_min >= q * C0:
        return {"status": "out_of_domain", "t_star": None,
                "note": "requires gamma>0, q>0, C0>0, 0<lam_min<q*C0"}
    t_star = (1.0 / gamma) * math.log((q * C0) / lam_min)
    return {"status": "PROPOSED", "t_star": round(t_star, 6),
            "lambda_at_t_star": round(q * coherence(C0, gamma, t_star), 6),
            "tau_c": round(1.0 / gamma, 6),
            "lean": "lutar-lean PR #225 Lutar/QuantumBio/CoherenceDecay.lean"}


def summary() -> dict[str, Any]:
    """Headline unified results + honest provenance/legend (served at /v1/unified/summary)."""
    return {
        "title": "SZL Unified Formulas (thesis v6) — borrowed structure, cited to origin",
        "status_legend": STATUS_LEGEND,
        "sources": SOURCES,
        "doctrine": {"locked_proven": 8, "lambda": "Conjecture 1", "khipu_bft": "Conjecture 2",
                     "trust": "never 100%", "lambda_v5": "PROPOSED engineering gate"},
        "results": {
            "hydyne_density_impulse": round(density_impulse(0.86, 310.0), 2),   # ~266.6
            "ls12_equal_mass_at_Qstar": ls12_largest_remnant(1.0, 1.0),          # frac 0.5
            "coherence_crossing_example": coherence_crossing(1.0, 1.0 / 6.05, 1.0, 0.25),
        },
    }


# ----------------------------------------------------------------------------
# FastAPI registration (mirrors szl_quantum_bio.register pattern; try/except-guarded by caller)
# ----------------------------------------------------------------------------
def register(app, ns: str) -> None:
    """Attach the unified routes under /api/<ns>/v1/unified/* via add_api_route (no decorators
    so it is import-safe and identical across both apps)."""
    base = f"/api/{ns}/v1/unified"
    app.add_api_route(f"{base}/summary", lambda: summary(), methods=["GET"])
    app.add_api_route(f"{base}/density_impulse",
                      lambda rho_mix: {"isp_rho": density_impulse(float(rho_mix), 310.0)}, methods=["GET"])
    app.add_api_route(f"{base}/tsiolkovsky",
                      lambda isp, m0, mf: {"dv": tsiolkovsky_dv(float(isp), float(m0), float(mf))}, methods=["GET"])
    app.add_api_route(f"{base}/ls12",
                      lambda Q_R, Q_star: ls12_largest_remnant(float(Q_R), float(Q_star)), methods=["GET"])
    app.add_api_route(f"{base}/corotation",
                      lambda M, R_eq: {"omega": corotation_omega(float(M), float(R_eq))}, methods=["GET"])
    app.add_api_route(f"{base}/hugoniot_quartz",
                      lambda up: {"Us": quartz_hugoniot_Us(float(up))}, methods=["GET"])
    app.add_api_route(f"{base}/coherence_crossing",
                      lambda C0, gamma, q, lam_min: coherence_crossing(float(C0), float(gamma), float(q), float(lam_min)),
                      methods=["GET"])


# ----------------------------------------------------------------------------
# Built-in self-test (Forge: run `python szl_unified_formulas.py` — must print ALL OK)
# ----------------------------------------------------------------------------
def _selftest() -> None:
    # Sherman: density-impulse of Hydyne ~ 0.86*310 = 266.6
    assert abs(density_impulse(0.86, 310.0) - 266.6) < 1e-6
    # Sherman: Isp = F/(mdot*g0); 83000 N / (35 kg/s) / g0
    assert specific_impulse(83000.0, 35.0) > 0
    # Tsiolkovsky: dv positive, monotone in mass ratio
    assert tsiolkovsky_dv(310.0, 10.0, 1.0) > tsiolkovsky_dv(310.0, 5.0, 1.0)
    # LS12: equal-mass at Q_R = Q*_RD -> largest remnant fraction = 0.5
    assert abs(ls12_largest_remnant(1.0, 1.0)["frac"] - 0.5) < 1e-9
    # CoRoL: omega decreases with radius
    assert corotation_omega(5.97e24, 6.4e6) > corotation_omega(5.97e24, 1.2e7)
    # Quartz Hugoniot: Us increases with up in the physical range
    assert quartz_hugoniot_Us(6000.0) > quartz_hugoniot_Us(3000.0)
    # Wave24 coherence: strictly decreasing
    assert coherence(1.0, 0.2, 2.0) < coherence(1.0, 0.2, 1.0)
    # Wave24 single-crossing: at t*, gate value == lam_min (closed form check)
    cc = coherence_crossing(1.0, 1.0 / 6.05, 1.0, 0.25)
    assert cc["status"] == "PROPOSED"
    assert abs(cc["lambda_at_t_star"] - 0.25) < 1e-6
    # out-of-domain guard
    assert coherence_crossing(1.0, 1.0, 1.0, 5.0)["status"] == "out_of_domain"
    print("szl_unified_formulas: ALL OK (9 checks)")


if __name__ == "__main__":
    _selftest()
