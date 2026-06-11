# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
"""
szl_scaling.py — SZL metabolic-scaling module. Real deterministic Python.
SHARED module: byte-identical in a11oy AND killinchu (and read by anatomy via API).

Implements Kleiber's law + the Metabolic Theory of Ecology temperature form + the
quantum-metabolism (PMF/coherence) bridge, and SZL's OWN unification Φ that couples
network scaling (M^3/4), thermodynamic activation (Boltzmann/PMF), and quantum
coherence (τc) — a combination no single source assembles. We CITE every classical
result and reclaim NONE; the SZL contribution is the unified Φ + the compute-allometry
analogue, both clearly labeled PROPOSED.

DOCTRINE: locked-proven = EXACTLY 8 {F1,F4,F7,F11,F12,F18,F19,F22} @ c7c0ba17 — this
module adds NOTHING to the locked 8 (EXPERIMENTAL-tier). Λ = Conjecture 1. The SZL Φ is
PROPOSED, NOT the formal Λ. Trust never 100%. No fabricated data (live dataset values
are labeled SAMPLE/attributed; nothing invented).

Citations (cited, NOT reclaimed):
  - Kleiber 1932, Hilgardia (B = B0·M^3/4): https://pdodds.w3.uvm.edu/files/papers/others/1932/kleiber1932a.pdf
  - West, Brown & Enquist 1997, Science 276:122 (fractal network): https://www.science.org/doi/10.1126/science.276.5309.122
  - Banavar, Maritan & Rinaldo 1999, Nature (efficient network, B~M^{D/(D+1)}): https://www.nature.com/articles/20144
  - Brown, Gillooly, Allen, Savage, West 2004, Ecology 85:1771 (MTE, Boltzmann factor): https://doi.org/10.1890/03-9000
  - Demetrius & Tuszynski 2010, J R Soc Interface (quantum metabolism / PMF bridge): https://pmc.ncbi.nlm.nih.gov/articles/PMC2842802/
  - Kaplan et al. 2020, arXiv:2001.08361 (neural scaling laws — compute analogue): https://arxiv.org/abs/2001.08361

Register:  register(app, ns="a11oy")  /  register(app, ns="killinchu")
Routes:    GET /api/<ns>/v1/scaling/{summary,kleiber,mte,unified,heart,compute,exponents}
"""
from __future__ import annotations
import math
from typing import Any

# Physical constants
K_EV = 8.617333262e-5     # Boltzmann constant, eV/K
R_GAS = 8.314             # J/(mol·K)
F_FARADAY = 96485.0       # C/mol

STATUS_LEGEND = {
    "VERIFIED": "deterministic computation reproduces a documented numeric on call",
    "PROPOSED": "SZL construct (unified Φ / compute-allometry); NOT in locked 8; Λ stays Conjecture 1",
    "SAMPLE": "illustrative values from public datasets (AnAge/PanTHERIA), attributed, not invented",
    "PROVEN_CORE": "the MATHEMATICAL CORE of this item is a sorry-free, kernel-verified Lean theorem "
                   "in lutar-lean (Mathlib v4.18, axioms [propext, Classical.choice, Quot.sound]). "
                   "This proves a PROPERTY of the function (positivity / monotonicity / an algebraic "
                   "identity) — NOT the empirical law itself, which stays cited & experimental. Λ stays Conjecture 1.",
}

# Lean cores proven for the scaling items (lutar-lean Lutar/Scaling/MetabolicScaling.lean).
# Each entry maps an item to the EXACT sorry-free theorem proving its mathematical core,
# plus an honest scope line. Empirical laws remain experimental; only the named theorem is
# 'proven'. Source of truth: lutar-lean@main + szl-lake anchor.
LEAN_THEOREMS = {
    "power_law": {
        "theorems": ["Lutar.Scaling.powerLaw_pos", "Lutar.Scaling.powerLaw_strictMono"],
        "proves": "B0·M^β > 0 and strictly increasing for β>0",
        "not_proven": "that any real organism obeys Kleiber's 3/4 exponent (empirical; Kleiber 1932 / WBE 1997)",
    },
    "heart": {
        "theorems": ["Lutar.Scaling.lifetime_heartbeats_invariant"],
        "proves": "(f0·M^(-1/4))·(L0·M^(1/4)) = f0·L0 — lifetime heartbeats independent of mass M (algebraic identity; the ±1/4 exponents cancel)",
        "not_proven": "that mammalian heart-rate/lifespan exponents are exactly ±1/4 in nature (empirical; MTE 2004)",
    },
    "compute": {
        "theorems": ["Lutar.Scaling.computeLoss_pos", "Lutar.Scaling.computeLoss_strictAnti"],
        "proves": "L0·N^(-α) is positive and strictly decreasing on (0,∞) for α>0",
        "not_proven": "that LM loss follows N^(-0.076) (empirical; Kaplan et al. 2020 — we claim only the allometric FRAMING)",
    },
    "exponents": {
        "theorems": ["Lutar.Scaling.exponent_additivity"],
        "proves": "M^a·M^b = M^(a+b) for M>0 — the composition/cancellation law underpinning the exponent comparator",
        "not_proven": "that the tabulated cross-domain exponents are physically correct (each cited to its author)",
    },
    "unified": {
        "theorems": ["Lutar.Scaling.szlPhi_pos", "Lutar.Scaling.szlPhi_strictMono_pmf"],
        "proves": "SZL-Φ (our construct) is > 0 and strictly increases with the proton-motive force Δp (structural properties)",
        "not_proven": "that Φ predicts real reaction rates (PROPOSED engineering construct, NOT the formal Λ; Λ stays Conjecture 1)",
    },
}
LEAN_PROVENANCE = {
    "repo": "szl-holdings/lutar-lean",
    "file": "Lutar/Scaling/MetabolicScaling.lean",
    "toolchain": "Lean 4.18.0 + Mathlib v4.18.0",
    "axiom_footprint": ["propext", "Classical.choice", "Quot.sound"],
    "status": "sorry-free, kernel-verified",
    "pr": "https://github.com/szl-holdings/lutar-lean/pull/228",
    "doctrine": "v11 — these prove function PROPERTIES, not empirical laws; Λ = Conjecture 1",
}

SOURCES = {
    "Kleiber 1932 (B=B0·M^3/4)": "https://pdodds.w3.uvm.edu/files/papers/others/1932/kleiber1932a.pdf",
    "West-Brown-Enquist 1997 (fractal network)": "https://www.science.org/doi/10.1126/science.276.5309.122",
    "Banavar-Maritan-Rinaldo 1999 (efficient network)": "https://www.nature.com/articles/20144",
    "Brown et al. 2004 MTE (Boltzmann factor)": "https://doi.org/10.1890/03-9000",
    "Demetrius-Tuszynski 2010 (quantum metabolism/PMF)": "https://pmc.ncbi.nlm.nih.gov/articles/PMC2842802/",
    "Kaplan et al. 2020 (neural scaling laws)": "https://arxiv.org/abs/2001.08361",
    "AnAge / HAGR dataset": "https://genomics.senescence.info/species/",
}


# ---------------------------------------------------------------------------
# [K] Kleiber's law — B = B0 · M^β  (β = 3/4)
# ---------------------------------------------------------------------------
def kleiber(M_kg: float, B0: float = 70.0, beta: float = 0.75) -> float:
    """Kleiber's law metabolic rate  B = B0 · M^β  (kcal/day; B0≈70 for mammals, M in kg).
    Cite Kleiber 1932. [VERIFIED model]"""
    if M_kg <= 0:
        return 0.0
    return B0 * (M_kg ** beta)


def banavar_exponent(D: int = 3) -> float:
    """Banavar-Maritan-Rinaldo dimensional exponent  β = D/(D+1)  (D=3 ⇒ 3/4).
    Cite Banavar et al. 1999. [VERIFIED]"""
    return D / (D + 1)


# ---------------------------------------------------------------------------
# [MTE] Temperature-corrected metabolic rate  B = b0 · M^3/4 · e^(−E/kT)
# ---------------------------------------------------------------------------
def mte_rate(M_kg: float, T_kelvin: float, b0: float = 70.0,
             E_eV: float = 0.65, beta: float = 0.75) -> float:
    """Metabolic Theory of Ecology rate  B = b0 · M^β · exp(−E/kT).
    E≈0.65 eV activation energy, k=8.617e-5 eV/K. Cite Brown et al. 2004. [VERIFIED model]"""
    if M_kg <= 0 or T_kelvin <= 0:
        return 0.0
    return b0 * (M_kg ** beta) * math.exp(-E_eV / (K_EV * T_kelvin))


def heart_rate_scaling(M_kg: float, f0: float = 241.0) -> float:
    """Heart-rate allometry  f ∝ M^(−1/4)  (bpm; f0≈241 for M in kg, mammals).
    Ties to anatomy HEART/YUYAY organ. The 'lifetime heartbeats ≈ constant' result
    follows since lifespan ∝ M^(+1/4). Cite MTE/West. [VERIFIED model]"""
    if M_kg <= 0:
        return 0.0
    return f0 * (M_kg ** -0.25)


def lifespan_scaling(M_kg: float, L0: float = 11.8) -> float:
    """Lifespan allometry  L ∝ M^(+1/4)  (years; L0≈11.8 for M in kg, mammals)."""
    if M_kg <= 0:
        return 0.0
    return L0 * (M_kg ** 0.25)


# ---------------------------------------------------------------------------
# PMF (our bioenergetics lineage) — Δp = ΔΨ − (2.303 RT/F) ΔpH
# ---------------------------------------------------------------------------
def proton_motive_force(delta_psi_mV: float, delta_pH: float,
                        T_kelvin: float = 310.0) -> float:
    """Proton-motive force  Δp = ΔΨ − (2.303 RT/F) ΔpH  (mV). Mitchell chemiosmosis.
    Reuses SZL's verified bioenergetics term. [VERIFIED model]"""
    coeff_mV = 2.303 * R_GAS * T_kelvin / F_FARADAY * 1000.0  # → mV
    return delta_psi_mV - coeff_mV * delta_pH


# ---------------------------------------------------------------------------
# [SZL-Φ] THE UNIFICATION (PROPOSED — our own construct)
#   Φ = Φ0 · M^3/4 · exp(−(E − η·Δp_eV)/kT) · (τc/τ0)^(1/4)
#   network scaling × (Boltzmann activation reduced by PMF) × coherence modulation
# ---------------------------------------------------------------------------
def szl_phi(M_kg: float, T_kelvin: float, delta_p_mV: float, tau_c: float,
            Phi0: float = 70.0, E_eV: float = 0.65, eta: float = 1.0,
            tau0: float = 6.05, beta: float = 0.75) -> dict[str, Any]:
    """SZL unified metabolic-coherence scaling Φ (PROPOSED — our own; cites WBE+MTE+
    Demetrius-Tuszynski). Couples: M^β network scaling, a Boltzmann-Arrhenius activation
    whose barrier is LOWERED by the proton-motive force (η·Δp converted eV), and a
    coherence modulation (τc/τ0)^(1/4) tying to our Lindblad τc / Λ-v5 lineage.

    Δp is given in mV; converted to eV per elementary charge (mV/1000 = volts = eV/charge).
    This is a PROPOSED engineering construct, NOT the formal Λ; Λ stays Conjecture 1. [PROPOSED]"""
    if M_kg <= 0 or T_kelvin <= 0 or tau_c <= 0 or tau0 <= 0:
        return {"phi": 0.0, "status": "out_of_domain"}
    delta_p_eV = (delta_p_mV / 1000.0) * eta          # mV→V→eV per unit charge × coupling η
    barrier = (E_eV - delta_p_eV)
    # Activation term as a PMF-ENHANCEMENT factor: the rate is lifted relative to the
    # no-PMF baseline at the SAME operating temperature by exp(+ηΔp/kT). This isolates the
    # PMF effect honestly (more PMF → lower barrier → higher rate) without the bare exp(-E/kT)
    # underflow. exp(−barrier/kT)/exp(−E/kT) = exp(+ηΔp_eV/kT).
    boltz = math.exp(delta_p_eV / (K_EV * T_kelvin))
    coh = (tau_c / tau0) ** 0.25
    phi = Phi0 * (M_kg ** beta) * boltz * coh
    return {"phi": round(phi, 6),
            "terms": {"network_M^beta": round(M_kg ** beta, 6),
                      "pmf_enhancement_exp(eta*dp/kT)": round(boltz, 6),
                      "coherence_(tau_c/tau0)^0.25": round(coh, 6),
                      "effective_barrier_eV": round(barrier, 6),
                      "delta_p_eV": round(delta_p_eV, 6)},
            "inputs": {"M_kg": M_kg, "T_K": T_kelvin, "delta_p_mV": delta_p_mV, "tau_c": tau_c},
            "status": "PROPOSED",
            "note": "SZL unification (WBE network × MTE/PMF activation × coherence); Λ=Conjecture 1",
            "lean_core": {"theorems": ["Lutar.Scaling.szlPhi_pos","Lutar.Scaling.szlPhi_strictMono_pmf"], "proves": "Phi>0 and strictly increases with PMF Delta-p (structural)", "not_proven": "that Phi predicts real rates; Phi is PROPOSED, not the formal Lambda"}}


# ---------------------------------------------------------------------------
# [SZL-COMPUTE] allometry analogue — neural/agent scaling as a 'metabolism'
# ---------------------------------------------------------------------------
def szl_compute_allometry(params_B: float, alpha: float = 0.076,
                          L0: float = 1.69) -> dict[str, Any]:
    """SZL compute-allometry analogue: model loss L(N) ≈ L0 · N^(−α) (Kaplan et al. 2020,
    α≈0.076 for params). We frame model 'capability metabolism' allometrically — compute
    cost vs capability scales like a metabolic network. PROPOSED analogy, cited to Kaplan;
    we claim only the allometric FRAMING, not the scaling law. [PROPOSED]"""
    if params_B <= 0:
        return {"loss": None, "status": "out_of_domain"}
    N = params_B * 1e9
    loss = L0 * (N ** -alpha)
    return {"params_billions": params_B, "predicted_loss": round(loss, 6),
            "exponent_alpha": alpha, "cite": "Kaplan et al. 2020 arXiv:2001.08361",
            "framing": "compute capability as metabolic-network allometry (PROPOSED analogy)",
            "lean_core": {"theorems": ["Lutar.Scaling.computeLoss_pos","Lutar.Scaling.computeLoss_strictAnti"], "proves": "L0*N^(-alpha) positive + strictly decreasing on (0,inf)", "not_proven": "the N^(-0.076) law itself (Kaplan 2020)"},
            "status": "PROPOSED"}


# Universal scaling exponents across domains (for the comparator tab) — all CITED.
UNIVERSAL_EXPONENTS = [
    {"domain": "biology", "quantity": "metabolic rate vs mass", "exponent": 0.75, "cite": "Kleiber 1932 / WBE 1997"},
    {"domain": "biology", "quantity": "heart rate vs mass", "exponent": -0.25, "cite": "MTE 2004"},
    {"domain": "biology", "quantity": "lifespan vs mass", "exponent": 0.25, "cite": "MTE 2004"},
    {"domain": "urban", "quantity": "GDP vs population", "exponent": 1.15, "cite": "Bettencourt-West 2007"},
    {"domain": "urban", "quantity": "infrastructure vs population", "exponent": 0.85, "cite": "Bettencourt-West 2007"},
    {"domain": "compute", "quantity": "LM loss vs parameters", "exponent": -0.076, "cite": "Kaplan et al. 2020"},
]


def summary() -> dict[str, Any]:
    """Headline of the SZL scaling module + honest provenance/legend."""
    return {
        "title": "SZL Metabolic-Scaling — Kleiber/WBE/MTE + quantum-metabolism, unified (our own Φ)",
        "status_legend": STATUS_LEGEND, "sources": SOURCES,
        "doctrine": {"locked_proven": 8, "lambda": "Conjecture 1", "phi": "PROPOSED (not the formal Λ)",
                     "trust": "never 100%"},
        "examples": {
            "kleiber_70kg_human": round(kleiber(70.0), 2),
            "heart_rate_70kg": round(heart_rate_scaling(70.0), 2),
            "heart_rate_mouse_0.02kg": round(heart_rate_scaling(0.02), 2),
            "szl_phi_demo": szl_phi(70.0, 310.0, 121.5, 6.05),
        },
        "universal_exponents": UNIVERSAL_EXPONENTS,
        "lean_proven_cores": LEAN_THEOREMS,
        "lean_provenance": LEAN_PROVENANCE,
    }


def proven_cores() -> dict[str, Any]:
    """The experimental->PROVEN-CORE promotion record. Each scaling item is mapped to the
    EXACT sorry-free Lean theorem(s) proving its mathematical core, with an explicit
    not_proven scope line. Honesty doctrine v11: only the named theorem is proven; the
    empirical law stays cited & experimental; Λ stays Conjecture 1."""
    return {
        "status": "PROVEN_CORE",
        "legend": STATUS_LEGEND["PROVEN_CORE"],
        "items": LEAN_THEOREMS,
        "provenance": LEAN_PROVENANCE,
        "doctrine": "v11 — locked-proven=8; Λ=Conjecture 1; these cores prove function PROPERTIES, never the empirical laws.",
    }


def register(app, ns: str) -> None:
    """Attach the scaling routes under /api/<ns>/v1/scaling/* via add_api_route."""
    base = f"/api/{ns}/v1/scaling"
    app.add_api_route(f"{base}/summary", lambda: summary(), methods=["GET"])
    app.add_api_route(f"{base}/kleiber", lambda M: {"M_kg": float(M), "B_kcal_day": kleiber(float(M))}, methods=["GET"])
    app.add_api_route(f"{base}/mte",
                      lambda M, T="310": {"M_kg": float(M), "T_K": float(T), "B": mte_rate(float(M), float(T))},
                      methods=["GET"])
    app.add_api_route(f"{base}/heart",
                      lambda M: {"M_kg": float(M), "bpm": round(heart_rate_scaling(float(M)), 2),
                                 "lifespan_yr": round(lifespan_scaling(float(M)), 2),
                                 "lifetime_beats_billion": round(heart_rate_scaling(float(M)) * 60 * 24 * 365 *
                                                                 lifespan_scaling(float(M)) / 1e9, 3)},
                      methods=["GET"])
    app.add_api_route(f"{base}/unified",
                      lambda M, T="310", dp="121.5", tau_c="6.05": szl_phi(float(M), float(T), float(dp), float(tau_c)),
                      methods=["GET"])
    app.add_api_route(f"{base}/compute",
                      lambda params="70": szl_compute_allometry(float(params)), methods=["GET"])
    app.add_api_route(f"{base}/exponents",
                      lambda: {"exponents": UNIVERSAL_EXPONENTS,
                               "lean_core": LEAN_THEOREMS["exponents"]}, methods=["GET"])
    # Experimental->PROVEN-CORE promotion record (the Lean-theorem tags per item).
    app.add_api_route(f"{base}/proven", lambda: proven_cores(), methods=["GET"])


def _selftest() -> None:
    # Kleiber: 70kg human ≈ 70 * 70^0.75 ≈ 1693 kcal/day (basal-ish ballpark)
    h = kleiber(70.0)
    assert 1500 < h < 1900, h
    # Banavar D=3 -> 0.75
    assert abs(banavar_exponent(3) - 0.75) < 1e-12
    # MTE rate positive and increases with temperature
    assert mte_rate(70.0, 310.0) > mte_rate(70.0, 300.0) > 0
    # heart-rate scaling: mouse beats far faster than human
    assert heart_rate_scaling(0.02) > heart_rate_scaling(70.0) > 0
    # lifetime heartbeats ~ roughly invariant order of magnitude (mouse vs human within ~3x)
    def beats(M): return heart_rate_scaling(M) * 60 * 24 * 365 * lifespan_scaling(M)
    r = beats(0.02) / beats(70.0)
    assert 0.3 < r < 3.0, r   # near-constant lifetime beats (the famous result)
    # pmf reproduces SZL verified two-ion value ballpark (121.5 mV at dΨ=150, dpH≈0.47)
    p = proton_motive_force(150.0, 0.47, 310.0)
    assert 110 < p < 135, p
    # SZL Φ: PROPOSED, positive, PMF lowers barrier so Φ(with pmf) > Φ(no pmf)
    phi_pmf = szl_phi(70.0, 310.0, 121.5, 6.05)["phi"]
    phi_nopmf = szl_phi(70.0, 310.0, 0.0, 6.05)["phi"]
    assert phi_pmf > phi_nopmf > 0, (phi_pmf, phi_nopmf)
    # longer coherence -> higher Φ (coherence modulation monotone)
    assert szl_phi(70.0, 310.0, 121.5, 12.0)["phi"] > szl_phi(70.0, 310.0, 121.5, 3.0)["phi"]
    # compute allometry: bigger model -> lower loss
    assert szl_compute_allometry(700)["predicted_loss"] < szl_compute_allometry(7)["predicted_loss"]
    # out-of-domain guards
    assert szl_phi(0, 310, 121.5, 6.05)["status"] == "out_of_domain"
    print("szl_scaling: ALL OK (11 checks)")


if __name__ == "__main__":
    _selftest()
