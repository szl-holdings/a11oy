# SPDX-License-Identifier: Apache-2.0
# © 2026 SZL Holdings · Doctrine v11 LOCKED · Λ = Conjecture 1 (advisory, NOT proven trust)
# Sign-off: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
"""pnt_resilience — SZL-NATIVE fused GNSS SPOOF-DETECTION / PNT-RESILIENCE engine.

WHAT THIS IS
============
A deny-by-default, multi-layer GNSS spoof detector. Four INDEPENDENT monitor
layers each emit a calibrated statistic + a fire/no-fire decision; a
Λ-gate-style governor fuses them. The governor is DENY-BY-DEFAULT: it returns
ALLOW only when NO layer fires AND a fused-confidence floor is cleared. The Λ
verdict is ADVISORY governance (Λ = Conjecture 1), it is NEVER "proven trust".

The four layers (each grounded in published method, cited below):
  1. multi-SV RAIM consistency  — pseudorange-residual parity / χ² test
  2. AGC / power-advantage      — received-power-advantage (dB) of a spoofer
  3. SQM (signal-quality)       — early/late correlator + carrier-phase alignment
  4. clock-aided time-spoof     — clock-bias vs position-push self-consistency

HONEST SCOPE (Doctrine v11, HARD — read this)
=============================================
This is a SIMULATOR that operates on **PARAMETERISED OBSERVABLES**, NOT raw IQ.
It is NOT an SDR and does NOT process baseband samples, correlator I/Q, or live
RF. The inputs are *summary observables* a real receiver would expose:
pseudorange residuals, an AGC-derived power-advantage estimate in dB, an SQM
early-minus-late metric, a carrier-phase-alignment flag, and clock-bias/position
push terms. A TEXBAT record is described to us by three classifier knobs (power
advantage dB, carrier-phase alignment, time/position push); we map those knobs
onto the observables the same way the literature characterises the records.
Anything we cannot derive from these observables is labelled NOT MODELED. We
NEVER label a record "detected" without a real triggering statistic crossing a
documented threshold (see SpoofVerdict.detected and the honesty test).

CLEAN-ROOM
==========
Method/physics re-derived from the open literature and cited. We studied the
EXISTENCE and SHAPE of kshana's fused multi-layer detector (Apache-2.0) as prior
art and CITE it; we copied NONE of its Rust. This is the SDA bridge into our
khipu-sda-core / mosaic anomaly engine and sits under the Λ-gate governor.

Pure stdlib (math + random) → sovereign, own-metal, auditable; runs in the
numpy-less web image (no numpy/scipy dependency).
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field, asdict
from typing import Optional


def _clip01(x: float) -> float:
    """Clamp x into [0, 1] (numpy.clip(x, 0.0, 1.0) analog)."""
    return max(0.0, min(1.0, float(x)))

# --------------------------------------------------------------------------- #
# Provenance — method/physics CITED, never claimed as SZL's own.               #
# --------------------------------------------------------------------------- #
ATTRIBUTION = {
    "kshana": (
        "Baweja, C. (2026). 'Kshana — a PNT-resilience simulator with quantum-sensor "
        "performance models', Ashforde OÜ, Apache-2.0, DOI:10.5281/zenodo.20528627 "
        "(v0.16.0). Studied as PRIOR ART for the SHAPE of a fused multi-layer GNSS "
        "spoof detector (RAIM-consistency parity + RF AGC-power monitor + SQM "
        "early-minus-late monitor, χ²/Neyman-Pearson statistics). CLEAN-ROOM: no Rust "
        "copied; re-derived from the cited primary literature below."
    ),
    "texbat": (
        "Humphreys, T.E. et al. (2012), 'The Texas Spoofing Test Battery (TEXBAT)', "
        "ION GNSS 2012. Defines the canonical spoofing records (ds1..ds8) classified "
        "by power advantage, carrier-phase alignment, and time/position push — the "
        "parameterisation used here to drive the monitor observables."
    ),
    "texbat_hifi": (
        "ION (2016), 'Detailed Analysis of the TEXBAT Datasets Using a High Fidelity "
        "Receiver' — characterises per-scenario power biases and time offsets; basis "
        "for the dB / time-push numbers attached to each scenario class."
    ),
    "raim": (
        "RTCA DO-229 / Receiver Autonomous Integrity Monitoring: redundant-pseudorange "
        "parity / least-squares-residual chi-square fault detection over >=5 SVs. "
        "Re-derived here as the RAIM-consistency layer."
    ),
    "agc_rpm": (
        "Garbin & Manfredini (2018, ION ITM), 'Effective GPS Spoofing Detection "
        "Utilizing Metrics from Commercial Receivers'; and ENAC hal-02907360 (2020), "
        "'Assessment of GPS Spoofing Detection via Radio Power and Signal Quality' — "
        "AGC / received-power monitoring detects overpowered spoofers."
    ),
    "sqm": (
        "Phelts; Garbin & Manfredini (2018) — Signal Quality Monitoring observes "
        "early-minus-late correlator asymmetry; powerful against power-matched "
        "spoofers during the code-phase pull-off (transient indicator)."
    ),
    "clock": (
        "Sensors (2023) PMC10007427, 'Characterization of the Ability of Low-Cost "
        "GNSS Receiver to Detect Spoofing' and SCV-RCS (Sensors 2026, PMC12845604): "
        "a spoofing attack induces a leap/inconsistency in the receiver clock bias "
        "vs the position solution — clock-aided time-spoof detection."
    ),
    "doctrine": (
        "SZL Doctrine v11 — clean-room, cite-never-plagiarize, MEASURED/MODELED "
        "labels, deny-by-default, Λ = Conjecture 1 (advisory governance gate, NOT "
        "proven trust). Λ-gate posture matches agentic_pinn / physics_bounds estate."
    ),
}

# Λ verdict labels (match the estate's lambda_gate vocabulary).
VERDICT_ALLOW = "ALLOW"        # no layer fired AND fused confidence passed
VERDICT_ADVISORY = "ADVISORY"  # ambiguous: weak/conflicting evidence -> hold
VERDICT_DENY = "DENY"          # >=1 layer fired -> deny-by-default

LAMBDA_LABEL = (
    "Λ = Conjecture 1 — the spoof governor is ADVISORY governance, NOT 'proven "
    "trust'. ALLOW means the PNT fix passed SZL admission policy (no monitor fired "
    "and fused confidence cleared the floor); it does NOT certify the signal is "
    "authentic. DENY/ADVISORY are deny-by-default holds."
)

SCOPE_LABEL = (
    "OBSERVABLE-DOMAIN SIMULATOR — operates on parameterised receiver observables "
    "(pseudorange residuals, AGC power-advantage dB, SQM early-minus-late, "
    "carrier-phase-alignment flag, clock-bias/position push). NOT an SDR; does NOT "
    "process raw IQ / baseband. Items not derivable are labelled NOT MODELED."
)


# --------------------------------------------------------------------------- #
# Calibrated thresholds. All DOCUMENTED, all tunable, none magic.              #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class DetectorConfig:
    # RAIM: false-alarm prob for the chi-square test on the residual sum-of-squares.
    raim_pfa: float = 1e-3
    raim_sigma_m: float = 3.0          # nominal 1-sigma pseudorange noise [m] (MODELED)
    # AGC/power: a spoofer must overpower; below ~1.5 dB is within nominal AGC drift.
    agc_advantage_db_thresh: float = 1.5   # power-advantage fire threshold [dB]
    agc_nominal_sigma_db: float = 0.4      # nominal AGC fluctuation 1-sigma [dB]
    # SQM: early-minus-late metric is ~0 for a clean symmetric correlation peak.
    sqm_metric_thresh: float = 0.12        # dimensionless asymmetry fire threshold
    sqm_nominal_sigma: float = 0.03        # nominal SQM fluctuation 1-sigma
    # Clock/time: inconsistency between clock-bias leap and position push [m-equiv].
    clock_resid_thresh_m: float = 8.0      # clock-bias/position self-consistency [m]
    clock_nominal_sigma_m: float = 2.0     # nominal clock-residual 1-sigma [m]
    # Fused-confidence floor: ALLOW requires fused confidence >= this AND no fire.
    fused_confidence_floor: float = 0.60


CFG = DetectorConfig()


# --------------------------------------------------------------------------- #
# Observable container — the parameterised inputs (NOT raw IQ).                 #
# --------------------------------------------------------------------------- #
@dataclass
class PntObservables:
    """Summary observables a real receiver exposes. NOT baseband IQ."""
    # RAIM layer: per-SV pseudorange residuals [m] after the LS position fix,
    # and the number of redundant SVs (DOF = n_sv - 4 for a 3D+clock fix).
    pr_residuals_m: list
    n_sv: int
    # AGC/power layer: estimated received-power advantage of the strongest
    # component over the nominal authentic floor [dB]. ~0 dB when clean.
    power_advantage_db: float = 0.0
    # SQM layer: early-minus-late correlator asymmetry metric (dimensionless),
    # plus a carrier-phase-alignment flag (True => spoofer phase-aligned to truth,
    # which SUPPRESSES SQM asymmetry — the hard, stealthy case).
    sqm_early_minus_late: float = 0.0
    carrier_phase_aligned: bool = False
    # Clock/time layer: the directly-estimated clock-bias leap [m-equiv] and the
    # clock-bias implied by integrating clock drift over the window [m-equiv];
    # their difference is the self-consistency residual. A time-push attack
    # breaks this consistency even with no obvious position jump.
    clock_bias_leap_m: float = 0.0
    clock_drift_implied_m: float = 0.0

    def __post_init__(self):
        self.pr_residuals_m = [float(x) for x in self.pr_residuals_m]


# --------------------------------------------------------------------------- #
# Per-layer result.                                                            #
# --------------------------------------------------------------------------- #
@dataclass
class LayerResult:
    name: str
    statistic: float          # the calibrated detection statistic
    threshold: float          # documented fire threshold for this statistic
    fired: bool               # statistic crossed threshold
    confidence: float         # in [0,1]: how confident this layer is the fix is CLEAN
    detail: str               # human-readable, honest detail
    modeled: bool = True      # False => NOT MODELED placeholder


@dataclass
class SpoofVerdict:
    verdict: str                          # ALLOW | ADVISORY | DENY
    advisory: bool                        # Λ is always advisory governance
    detected: bool                        # True ONLY if >=1 layer fired on a real stat
    fired_layers: list                    # names of layers that fired
    fused_confidence: float               # fused clean-confidence in [0,1]
    layers: list                          # list[LayerResult] as dicts
    reason: str
    lambda_label: str = LAMBDA_LABEL
    scope_label: str = SCOPE_LABEL
    attribution: dict = field(default_factory=lambda: ATTRIBUTION)


# --------------------------------------------------------------------------- #
# Layer 1 — multi-SV RAIM consistency (pseudorange-residual chi-square).       #
# --------------------------------------------------------------------------- #
def _chi2_threshold(dof: int, pfa: float) -> float:
    """Upper-tail chi-square threshold for given DOF and false-alarm prob.

    Pure-numpy Wilson-Hilferty inverse-CDF approximation (no scipy). The
    chi-square parity test is the textbook RAIM fault-detection statistic:
    a spoofer that is not perfectly self-consistent across SVs inflates the
    sum-of-squared pseudorange residuals beyond the noise-only chi-square tail.
    """
    if dof <= 0:
        return float("inf")  # cannot run RAIM without redundancy
    # Standard-normal upper quantile for pfa via inverse erf.
    z = math.sqrt(2.0) * _erfinv(1.0 - 2.0 * pfa) if pfa < 0.5 else 0.0
    # Wilson-Hilferty: chi2 ~ dof*(1 - 2/(9 dof) + z*sqrt(2/(9 dof)))^3
    t = 1.0 - 2.0 / (9.0 * dof) + z * math.sqrt(2.0 / (9.0 * dof))
    return dof * t ** 3


def _erfinv(y: float) -> float:
    """Inverse error function (rational approx, Winitzki). Pure-stdlib."""
    if y <= -1.0:
        return -float("inf")
    if y >= 1.0:
        return float("inf")
    a = 0.147
    ln = math.log(1.0 - y * y)
    term = 2.0 / (math.pi * a) + ln / 2.0
    return math.copysign(math.sqrt(math.sqrt(term * term - ln / a) - term), y)


def raim_layer(obs: PntObservables, cfg: DetectorConfig = CFG) -> LayerResult:
    """RAIM-consistency parity test on pseudorange residuals.

    Statistic: SSE/sigma^2 ~ chi^2_(n_sv-4). Fires if it exceeds the upper-tail
    threshold at the configured false-alarm probability. DOF = n_sv - 4
    (3 position + 1 clock unknowns). With <5 SVs there is no redundancy ->
    NOT MODELED (cannot run RAIM); we honestly do not fire on it.
    """
    dof = int(obs.n_sv) - 4
    sse = float(sum((r / cfg.raim_sigma_m) ** 2 for r in obs.pr_residuals_m))
    if dof <= 0:
        return LayerResult(
            name="raim_consistency",
            statistic=sse,
            threshold=float("inf"),
            fired=False,
            confidence=0.5,  # cannot vouch either way without redundancy
            detail="NOT MODELED: <5 SV, no RAIM redundancy (DOF<=0); cannot test.",
            modeled=False,
        )
    thr = _chi2_threshold(dof, cfg.raim_pfa)
    fired = sse > thr
    # confidence the fix is CLEAN: how far below threshold we sit (smooth).
    conf = _clip01(1.0 - sse / (thr + 1e-12))
    return LayerResult(
        name="raim_consistency",
        statistic=sse,
        threshold=thr,
        fired=fired,
        confidence=conf,
        detail=(f"chi2 parity SSE={sse:.2f} vs thr={thr:.2f} (DOF={dof}, "
                f"Pfa={cfg.raim_pfa:g}); fired={fired}."),
    )


# --------------------------------------------------------------------------- #
# Layer 2 — AGC / received-power-advantage monitor.                            #
# --------------------------------------------------------------------------- #
def agc_power_layer(obs: PntObservables, cfg: DetectorConfig = CFG) -> LayerResult:
    """Received-power-advantage monitor (AGC-derived).

    An overpowered spoofer drives the receiver AGC and shows up as a positive
    power advantage in dB over the authentic floor. Statistic is the dB
    advantage; fires above the configured threshold. Power-MATCHED spoofers
    (advantage ~0 dB) intentionally evade this layer — that is the documented
    blind spot SQM/RAIM/clock layers cover (defence-in-depth).
    """
    adv = float(obs.power_advantage_db)
    thr = cfg.agc_advantage_db_thresh
    fired = adv > thr
    # z-score of advantage vs nominal AGC drift -> clean-confidence.
    z = adv / max(cfg.agc_nominal_sigma_db, 1e-9)
    conf = _clip01(1.0 - z / 4.0)  # 4-sigma -> 0 confidence
    return LayerResult(
        name="agc_power_advantage",
        statistic=adv,
        threshold=thr,
        fired=fired,
        confidence=conf,
        detail=(f"power advantage={adv:.2f} dB vs thr={thr:.2f} dB; fired={fired}. "
                f"Power-matched (~0 dB) spoofers evade this layer by design."),
    )


# --------------------------------------------------------------------------- #
# Layer 3 — SQM (signal-quality / carrier-phase alignment) monitor.            #
# --------------------------------------------------------------------------- #
def sqm_layer(obs: PntObservables, cfg: DetectorConfig = CFG) -> LayerResult:
    """SQM early-minus-late correlator asymmetry monitor.

    During a spoofer's code-phase pull-off the authentic and counterfeit
    correlation peaks coexist and distort the correlation function, producing
    a measurable early-minus-late asymmetry. Statistic is the |asymmetry|;
    fires above threshold.

    HONEST CAVEAT: if the spoofer is carrier-phase-aligned to the truth
    (the stealthy power-matched, phase-aligned case, e.g. TEXBAT ds7), the two
    peaks merge and SQM asymmetry collapses -> this layer cannot fire. We model
    that by suppressing the effective metric when carrier_phase_aligned=True,
    and we say so. That blind spot is precisely why fusion + deny-by-default
    matters; we do NOT pretend SQM caught it.
    """
    raw = abs(float(obs.sqm_early_minus_late))
    # Phase-aligned merge collapses the observable asymmetry.
    eff = 0.0 if obs.carrier_phase_aligned else raw
    thr = cfg.sqm_metric_thresh
    fired = eff > thr
    z = eff / max(cfg.sqm_nominal_sigma, 1e-9)
    conf = _clip01(1.0 - z / 4.0)
    if obs.carrier_phase_aligned:
        detail = ("carrier-phase-aligned: peaks merged, SQM asymmetry suppressed "
                  "(eff=0); this layer CANNOT fire on a phase-aligned spoofer.")
        conf = 0.5  # honest: SQM neither vouches nor accuses here
    else:
        detail = (f"SQM early-minus-late |asym|={eff:.3f} vs thr={thr:.3f}; "
                  f"fired={fired}.")
    return LayerResult(
        name="sqm_signal_quality",
        statistic=eff,
        threshold=thr,
        fired=fired,
        confidence=conf,
        detail=detail,
    )


# --------------------------------------------------------------------------- #
# Layer 4 — clock-aided time-spoof monitor.                                    #
# --------------------------------------------------------------------------- #
def clock_time_layer(obs: PntObservables, cfg: DetectorConfig = CFG) -> LayerResult:
    """Clock-bias vs position-push self-consistency (time-spoof) monitor.

    A time-push attack injects a clock-bias leap that is NOT consistent with the
    clock bias implied by integrating the receiver's own clock drift. The
    self-consistency residual |clock_bias_leap - clock_drift_implied| (in
    metre-equivalents, 1 ns ~ 0.2998 m) is the statistic; fires above threshold.
    This is the layer that catches a stealthy time-only push that leaves the
    position solution and power untouched.
    """
    resid = abs(float(obs.clock_bias_leap_m) - float(obs.clock_drift_implied_m))
    thr = cfg.clock_resid_thresh_m
    fired = resid > thr
    z = resid / max(cfg.clock_nominal_sigma_m, 1e-9)
    conf = _clip01(1.0 - z / 4.0)
    return LayerResult(
        name="clock_time_spoof",
        statistic=resid,
        threshold=thr,
        fired=fired,
        confidence=conf,
        detail=(f"clock-bias/position self-consistency residual={resid:.2f} m "
                f"vs thr={thr:.2f} m; fired={fired}."),
    )


# --------------------------------------------------------------------------- #
# Λ-gate-style fusion governor — DENY-BY-DEFAULT.                              #
# --------------------------------------------------------------------------- #
def fuse(layers: list, cfg: DetectorConfig = CFG) -> SpoofVerdict:
    """Fuse independent monitor layers under a deny-by-default Λ governor.

    POLICY (deny-by-default):
      * If ANY layer fired on a real triggering statistic  -> DENY (detected=True).
      * Else if fused clean-confidence >= floor            -> ALLOW (advisory).
      * Else (no fire, but weak/ambiguous confidence)      -> ADVISORY (hold).

    Fused clean-confidence is the MINIMUM across MODELED layers (a chain is only
    as trustworthy as its weakest honest monitor) blended toward the mean; using
    the min keeps the gate conservative. NOT-MODELED layers are excluded from the
    confidence floor (we don't let an un-runnable layer manufacture trust) but a
    record is NEVER marked detected without a real fire.
    """
    fired = [L.name for L in layers if L.fired]
    modeled_conf = [L.confidence for L in layers if L.modeled]
    if modeled_conf:
        # conservative blend: weight the weakest layer heavily.
        fused_conf = 0.7 * min(modeled_conf) + 0.3 * (sum(modeled_conf) / len(modeled_conf))
    else:
        fused_conf = 0.0  # nothing runnable -> cannot vouch -> deny-by-default holds

    if fired:
        verdict = VERDICT_DENY
        detected = True
        reason = (f"DENY (deny-by-default): {len(fired)} monitor layer(s) fired "
                  f"-> {', '.join(fired)}. Λ advisory: spoof indicated.")
    elif fused_conf >= cfg.fused_confidence_floor:
        verdict = VERDICT_ALLOW
        detected = False
        reason = (f"ALLOW: no layer fired and fused clean-confidence "
                  f"{fused_conf:.2f} >= floor {cfg.fused_confidence_floor:.2f}. "
                  f"Λ advisory ONLY — not proven trust.")
    else:
        verdict = VERDICT_ADVISORY
        detected = False
        reason = (f"ADVISORY HOLD (deny-by-default): no layer fired but fused "
                  f"clean-confidence {fused_conf:.2f} < floor "
                  f"{cfg.fused_confidence_floor:.2f}; insufficient evidence to ALLOW.")

    return SpoofVerdict(
        verdict=verdict,
        advisory=True,                 # Λ is ALWAYS advisory governance
        detected=detected,
        fired_layers=fired,
        fused_confidence=float(fused_conf),
        layers=[asdict(L) for L in layers],
        reason=reason,
    )


def detect(obs: PntObservables, cfg: DetectorConfig = CFG) -> SpoofVerdict:
    """Run all four independent layers and fuse under the deny-by-default Λ gate."""
    layers = [
        raim_layer(obs, cfg),
        agc_power_layer(obs, cfg),
        sqm_layer(obs, cfg),
        clock_time_layer(obs, cfg),
    ]
    return fuse(layers, cfg)


# --------------------------------------------------------------------------- #
# TEXBAT-style scenario parameterisation.                                      #
# --------------------------------------------------------------------------- #
@dataclass
class TexbatScenario:
    """A TEXBAT-style record described by the three classifier knobs the
    literature uses: power advantage (dB), carrier-phase alignment, and
    time/position push. We map those knobs onto receiver observables. These
    numbers are MODELED parameterisations of the published record classes
    (Humphreys 2012; ION 2016 hi-fi analysis), NOT measured IQ captures.
    """
    name: str
    power_advantage_db: float
    carrier_phase_aligned: bool
    position_push_m: float        # how hard the fix is pulled in space [m]
    time_push_m: float            # clock-bias leap injected [m-equiv]
    description: str = ""


# Canonical TEXBAT-style classes (parameterised from the cited characterisations).
TEXBAT_LIBRARY = {
    "clean": TexbatScenario(
        name="clean", power_advantage_db=0.0, carrier_phase_aligned=False,
        position_push_m=0.0, time_push_m=0.0,
        description="Authentic signal, no spoofer. Expect ALLOW.",
    ),
    "ds2_time_push": TexbatScenario(
        name="ds2_time_push", power_advantage_db=8.0, carrier_phase_aligned=False,
        position_push_m=0.0, time_push_m=40.0,
        description="Overpowered time-push, no phase alignment (TEXBAT ds2 class).",
    ),
    "ds3_overpower": TexbatScenario(
        name="ds3_overpower", power_advantage_db=10.0, carrier_phase_aligned=False,
        position_push_m=60.0, time_push_m=0.0,
        description="Gradual/strong power-advantage takeover (TEXBAT ds3 class).",
    ),
    "ds4_seamless": TexbatScenario(
        name="ds4_seamless", power_advantage_db=2.0, carrier_phase_aligned=False,
        position_push_m=80.0, time_push_m=0.0,
        description="Seamless lift-off; modest power, code-phase pull (ds4 class).",
    ),
    "ds7_matched_aligned": TexbatScenario(
        name="ds7_matched_aligned", power_advantage_db=0.4,
        carrier_phase_aligned=True, position_push_m=70.0, time_push_m=0.0,
        description=("Power-matched, carrier-phase-aligned stealth spoof "
                     "(TEXBAT ds7 class) — defeats AGC and SQM; caught only by "
                     "RAIM-consistency parity on the position push."),
    ),
}


def observables_from_scenario(sc: TexbatScenario, n_sv: int = 8,
                              seed: int = 0,
                              cfg: DetectorConfig = CFG) -> PntObservables:
    """Synthesise parameterised observables for a TEXBAT-style scenario.

    Mapping (MODELED, documented):
      * position_push -> inflates pseudorange residuals (RAIM sees inconsistency).
        A counterfeit constellation that pushes the fix by D metres leaves a
        residual signature ~ D scattered across SVs; we model the per-SV residual
        as nominal noise + a push-driven inconsistency term.
      * power_advantage_db -> AGC layer observable directly.
      * code-phase pull -> SQM early-minus-late asymmetry, UNLESS phase-aligned.
      * time_push -> clock-bias leap inconsistent with clock-drift integration.
    """
    rng = random.Random(seed)
    # Nominal clean residuals: zero-mean Gaussian at the modelled sigma.
    resid = [rng.gauss(0.0, cfg.raim_sigma_m) for _ in range(n_sv)]
    if sc.position_push_m > 0:
        # A spoofer pulling the fix injects a coherent-but-inconsistent push:
        # part of it is absorbed by the LS fix, the inconsistent remainder
        # (~30% of the push, spread over redundant SVs) shows in residuals.
        inconsistency = 0.30 * sc.position_push_m
        push_sig = [rng.gauss(0.0, inconsistency / math.sqrt(max(n_sv, 1)))
                    for _ in range(n_sv)]
        resid = [r + ps + inconsistency / n_sv for r, ps in zip(resid, push_sig)]
    # SQM asymmetry tracks the code-phase pull; scale with position push,
    # suppressed if phase-aligned (handled inside sqm_layer too).
    sqm_metric = 0.0
    if sc.position_push_m > 0 and not sc.carrier_phase_aligned:
        sqm_metric = min(0.5, 0.004 * sc.position_push_m + abs(rng.gauss(0, 0.01)))
    # Clock: bias leap = time_push; drift-implied stays at the clean value.
    clock_leap = sc.time_push_m + rng.gauss(0.0, cfg.clock_nominal_sigma_m * 0.3)
    clock_drift_implied = rng.gauss(0.0, cfg.clock_nominal_sigma_m * 0.3)
    return PntObservables(
        pr_residuals_m=resid,
        n_sv=n_sv,
        power_advantage_db=sc.power_advantage_db + rng.gauss(0, cfg.agc_nominal_sigma_db * 0.2),
        sqm_early_minus_late=sqm_metric,
        carrier_phase_aligned=sc.carrier_phase_aligned,
        clock_bias_leap_m=clock_leap,
        clock_drift_implied_m=clock_drift_implied,
    )


def assess_scenario(sc: TexbatScenario, n_sv: int = 8, seed: int = 0,
                    cfg: DetectorConfig = CFG) -> SpoofVerdict:
    """Convenience: parameterise a TEXBAT-style record and run the fused detector."""
    obs = observables_from_scenario(sc, n_sv=n_sv, seed=seed, cfg=cfg)
    return detect(obs, cfg)


# --------------------------------------------------------------------------- #
# Demo / CLI.                                                                  #
# --------------------------------------------------------------------------- #
def _print_verdict(name: str, v: SpoofVerdict) -> None:
    print(f"\n=== {name} ===")
    print(f"  verdict   : {v.verdict}  (detected={v.detected}, advisory={v.advisory})")
    print(f"  fired     : {v.fired_layers or 'none'}")
    print(f"  fused conf: {v.fused_confidence:.3f}")
    for L in v.layers:
        flag = "FIRE" if L["fired"] else ("n/m" if not L["modeled"] else "ok ")
        print(f"    [{flag}] {L['name']:<22} stat={L['statistic']:.3f} "
              f"thr={L['threshold']:.3f}")
    print(f"  reason    : {v.reason}")


if __name__ == "__main__":
    print("SZL PNT-RESILIENCE — fused deny-by-default GNSS spoof detector")
    print(SCOPE_LABEL)
    print(LAMBDA_LABEL)
    for key, sc in TEXBAT_LIBRARY.items():
        v = assess_scenario(sc, seed=42)
        _print_verdict(f"{sc.name} — {sc.description}", v)
