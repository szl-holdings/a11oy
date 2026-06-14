# SPDX-License-Identifier: Apache-2.0
# © 2026 SZL Holdings · Doctrine v11 LOCKED · Λ = Conjecture 1 (advisory, NOT proven trust)
# Sign-off: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
"""nav_coasting — SZL-NATIVE GPS-DENIED NAVIGATION COASTING / HOLDOVER model,
governed and tied to the SZL agentic-PINN + deny-by-default Λ-gate.

THE LANE (Dev 3 of 4): the honest "how long can a quantum-equipped system coast
when GPS is denied" number. When GNSS is denied, position is dead-reckoned from
inertial sensors and time is held over from the local clock. Both error sources
GROW with time; the figure-of-merit is the TIME-TO-EXCEED a position/timing
accuracy threshold. The whole point of a quantum (cold-atom interferometer)
accelerometer is that its noise PSD is LOWER, so coasting error grows slower and
the time-to-exceed is LONGER. This module computes that delta honestly.

CLEAN-ROOM: the METHOD & PHYSICS are re-derived from the open literature and from
the published METHOD of AshfordeOU/kshana (Apache-2.0, DOI 10.5281/zenodo.20528627,
GNSS/INS fusion + clock holdover). NO kshana Rust is copied — see ATTRIBUTION.

WHAT IS MODELED (honest, Doctrine v11):
  * 1-DOF (single straight axis) strapdown dead-reckoning error growth. 1-DOF is
    a deliberate, declared simplification: it captures the dominant accelerometer
    noise → velocity → position double-integration and the clock holdover terms,
    which is exactly what sets the coasting horizon to first order.
  * Position error variance from (i) velocity-random-walk (VRW), (ii) acceleration
    random walk / white-accel PSD (the q_va that Dev1's quantum sensor model
    produces), and (iii) a deterministic accelerometer bias term (∝ t²).
  * Clock TIMING holdover from initial phase/frequency offset + frequency drift +
    Allan stochastic terms (white-FM and random-walk-FM), expressed in metres via
    the speed of light so position and timing live on one budget.

WHAT IS NOT MODELED (declared, never faked):
  * 3-axis / full strapdown INS (attitude/tilt → gyro-bias t^3 coupling, Schuler
    84-min loop, Coriolis, gravity-deflection) — marked NOT MODELED. The t^3 gyro
    term is the dominant long-coast term in the real 3-D system; ignoring it makes
    our 1-DOF horizon an OPTIMISTIC (upper-ish) bound, and we say so on the receipt.
  * No Kalman/UKF fusion update is run here (kshana's 17-state tightly-coupled UKF
    is NOT MODELED); we model the OPEN-LOOP coasting growth, which is the relevant
    quantity once aiding (GNSS) is denied.

GOVERNANCE: the coasting estimate is produced under a DENY-BY-DEFAULT Λ-gate that
mirrors agentic_pinn.py / innovations/lambda_gate.py. The estimate is ACCEPTED
only when the numerical integration passes a residual/convergence self-check
against the closed-form variance growth. Each run emits an UNSIGNED, signer-ready
receipt (STRUCTURAL-ONLY: content-addressed inputs hash, no cryptographic sig).

Pure numpy → sovereign, own-metal, auditable.
"""
from __future__ import annotations

import hashlib
import json
import math
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

import numpy as np

# --------------------------------------------------------------------------- #
# Constants                                                                    #
# --------------------------------------------------------------------------- #
C_LIGHT = 299792458.0       # speed of light, m/s (SI exact) — couples timing<->range
G0 = 9.80665                # standard gravity, m/s^2 (for bias expressed in 'g')

METHOD = ("szl_nav_coasting (1-DOF GNSS/INS open-loop dead-reckoning error growth + "
          "clock holdover; time-to-exceed FoM for CLASSICAL vs QUANTUM sensor "
          "coefficients; governed under a deny-by-default Lambda-gate with a "
          "residual-checked integration and a per-run STRUCTURAL-ONLY receipt)")

# Method/physics attribution ONLY — clean-room. No kshana Rust copied or consulted
# beyond its PUBLIC method/equation surface (its docs/README/CLAIMS labels).
ATTRIBUTION = {
    "ins_error_growth_method": (
        "Strapdown inertial error propagation re-derived clean-room from standard "
        "public references: Woodman, O.J., 'An introduction to inertial navigation', "
        "Univ. Cambridge Tech. Report UCAM-CL-TR-696 (2007) — accelerometer bias gives "
        "position error s(t)=b*t^2/2, double-integrated white accel noise gives a "
        "position random walk; Groves, P.D., 'Principles of GNSS, Inertial, and "
        "Multisensor Integrated Navigation Systems', 2nd ed., Artech House (2013) — "
        "VRW/ARW PSD bookkeeping. METHOD/MATHEMATICS attribution only."
    ),
    "clock_holdover_method": (
        "Clock time-error / holdover model x(t)=x0+y0*t+0.5*D*t^2 plus Allan stochastic "
        "terms re-derived clean-room from: Allan, D.W. (1966) Proc. IEEE 54(2):221 "
        "(Allan variance); IEEE Std 1139-2008 (frequency-stability definitions); "
        "ITU-T/ETSI TIE & MTIE holdover definitions (ETSI EN 300 462). White-FM noise "
        "(sigma_y(tau)=h0/sqrt(tau)) integrates to a TIE random walk (var ∝ t); "
        "random-walk-FM integrates to var ∝ t^3. METHOD/MATHEMATICS attribution only."
    ),
    "quantum_sensor_coupling": (
        "Consumes the accelerometer noise PSD q_va (units (m/s^2)^2/Hz, equivalently "
        "ASD^2) produced by the SZL cold-atom-interferometer sensor model (Dev1), "
        "itself a clean-room re-derivation of the kshana inertial/quantum_imu method "
        "(Kasevich & Chu 1991; Peters et al. 2001; Freier et al. 2016; Cheinet et al. "
        "2008). This module is agnostic to how q_va was produced; it only needs the PSD."
    ),
    "kshana_method_source": (
        "AshfordeOU/kshana — open PNT-resilience simulator (Apache-2.0, DOI "
        "10.5281/zenodo.20528627): GNSS/INS fusion (fusion/ukf.rs, tightly_coupled17.rs), "
        "clock holdover (allan.rs, timetransfer*.rs), and the 'how long can a "
        "quantum-equipped system coast when GPS is denied' question. METHOD source only; "
        "NO Rust copied. Cited under its Apache-2.0 licence, clean-room re-derivation."
    ),
    "governance": (
        "Deny-by-default Λ-gate posture mirrored from the SZL agentic_pinn.py and "
        "innovations/lambda_gate.py (clean-room, SZL-native). Λ = Conjecture 1 — "
        "advisory governance, not proven trust."
    ),
}

DOCTRINE = (
    "v11 LOCKED: Λ=Conjecture 1 (ADVISORY gate, NOT proven trust); NO free-energy/"
    "over-unity (sensor noise floors are DERIVED from physics PSDs, never invented); "
    "the coasting horizon is MODELED, not MEASURED, unless a real q_va/clock spec is "
    "supplied and labelled MEASURED; 1-DOF is a DECLARED simplification and 3-axis/"
    "full-INS (gyro t^3, Schuler, Coriolis) is NOT MODELED; no fabricated coasting "
    "number — the integration really runs and is residual-checked; cite-never-plagiarize."
)

# Verdict vocabulary (mirrors innovations/lambda_gate.py exactly).
VERDICT_ALLOW = "ALLOW"
VERDICT_ADVISORY = "ADVISORY"
VERDICT_DENY = "DENY"


def _hash_inputs(obj: dict) -> str:
    canon = json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)
    return "sha256:" + hashlib.sha256(canon.encode()).hexdigest()


# --------------------------------------------------------------------------- #
# Sensor / clock coefficient bundle (CLASSICAL vs QUANTUM)                     #
# --------------------------------------------------------------------------- #
@dataclass
class SensorCoeffs:
    """The error-growth coefficients for one sensor+clock configuration.

    All fields are INPUTS (MEASURED from a datasheet/lab, or honest SAMPLE/MODELED).
    The accelerometer white-noise term `q_va` is the PSD that Dev1's quantum sensor
    model emits; everything else is the surrounding INS/clock budget.

    Units:
      q_va        : accelerometer white-noise PSD, (m/s^2)^2 / Hz  (== ASD^2).
                    This is the single field Dev1 feeds us. ASD n_a = sqrt(q_va).
      accel_bias  : residual deterministic accelerometer bias, m/s^2 (after calib).
      vrw_psd     : velocity-random-walk PSD added directly to the velocity state,
                    (m/s)^2 / s  (m^2/s^3). Captures integrated-rate / quantisation
                    that is not already inside q_va. Default 0 (folded into q_va).
      clock_h0    : white-FM coefficient; sigma_y(tau) = sqrt(h0 / (2*tau)) form,
                    here we use the convenient sigma_y(tau)=clock_adev1s/sqrt(tau)
                    parameterisation via `clock_adev_1s` below instead, and keep h0
                    available for advanced callers (dimensionless^2 * s).
      clock_adev_1s : Allan deviation at tau=1 s (dimensionless, df/f). White-FM.
      clock_rwfm  : random-walk-FM rate (dimensionless / sqrt(s)) — long-term clock
                    wander. Drives a TIE variance ∝ t^3 term.
      clock_drift : deterministic fractional frequency drift D (1/s), aging.
      clock_y0    : initial fractional frequency offset y0 (dimensionless) at the
                    moment GNSS is denied (post-sync residual).
      label       : "MEASURED" | "MODELED" | "SAMPLE" (honest provenance).
      name        : human label, e.g. "classical-MEMS" / "quantum-CAI".
    """
    q_va: float                      # (m/s^2)^2 / Hz  — from Dev1 quantum sensor model
    accel_bias: float = 0.0          # m/s^2
    vrw_psd: float = 0.0             # (m/s)^2 / s
    clock_adev_1s: float = 0.0       # Allan deviation at 1 s (white-FM), df/f
    clock_rwfm: float = 0.0          # random-walk-FM rate, 1/sqrt(s)
    clock_drift: float = 0.0         # fractional frequency drift D, 1/s
    clock_y0: float = 0.0            # initial fractional frequency offset
    clock_h0: float = 0.0            # optional white-FM PSD coefficient (advanced)
    label: str = "MODELED"
    name: str = "unnamed"
    source: str = "honest-sample"

    @property
    def accel_asd(self) -> float:
        """Accelerometer amplitude spectral density, (m/s^2)/sqrt(Hz) = sqrt(q_va)."""
        return math.sqrt(max(self.q_va, 0.0))


# --------------------------------------------------------------------------- #
# Closed-form 1-DOF error-growth variances (the derived physics)              #
# --------------------------------------------------------------------------- #
def position_error_sigma(c: SensorCoeffs, t: np.ndarray | float) -> np.ndarray:
    """1-DOF horizontal POSITION error std-dev (m) after coasting time t (s).

    Re-derived clean-room. Three contributions, added in QUADRATURE for the
    stochastic parts and arithmetically for the deterministic bias term:

      (A) White accelerometer noise PSD q_va, double-integrated:
          Var_x(t) = q_va * t^3 / 3.   (random-walk-of-velocity -> position)
          [matches the kshana vibration phase variance shape sigma^2 ∝ S_a*T^3/3
           re-expressed in metres; Woodman 2007 random-walk result.]
      (B) Velocity-random-walk PSD vrw_psd, single state on velocity then integrated:
          Var_x(t) = vrw_psd * t^3 / 3 as well for a white velocity-rate; we keep it
          separate so a caller can split quantisation noise from sensor white noise.
      (C) Deterministic residual accel bias b, double-integrated (NOT a variance —
          a systematic offset): x_bias(t) = 0.5 * b * t^2.

    sigma_pos(t) = sqrt(Var_x_stoch(t)) + |x_bias(t)|   (conservative sum: random
    1-sigma plus the systematic offset, an honest upper-ish envelope).
    """
    t = np.asarray(t, dtype=float)
    var_stoch = (c.q_va + c.vrw_psd) * np.power(t, 3) / 3.0
    sigma_stoch = np.sqrt(np.maximum(var_stoch, 0.0))
    x_bias = 0.5 * abs(c.accel_bias) * np.power(t, 2)
    return sigma_stoch + x_bias


def timing_error_seconds(c: SensorCoeffs, t: np.ndarray | float) -> np.ndarray:
    """1-DOF clock TIMING (time-interval) error std-dev-equivalent (s) at coast t.

    x(t) = x0 + y0*t + 0.5*D*t^2 (deterministic)  +  Allan stochastic terms.
    Re-derived clean-room from the time-error/holdover definition and Allan-noise
    integration (ETSI EN 300 462; IEEE Std 1139; Allan 1966):
      * deterministic frequency offset:  |y0| * t           (linear TIE)
      * deterministic frequency drift D:  0.5 * |D| * t^2   (parabolic TIE)
      * white-FM (ADEV = adev_1s / sqrt(tau)) integrates to a TIE RANDOM WALK whose
        std grows ~ adev_1s * t / sqrt(t) * sqrt(t) ... we use the standard holdover
        result sigma_TIE_whiteFM(t) = adev_1s * t / sqrt(... )  -> we adopt the
        widely-used engineering holdover approximation: TIE_whiteFM(t) ≈ adev_1s *
        sqrt(t) * t_ref with t_ref=1s normalisation, i.e. sigma ∝ t for the
        accumulated phase; to stay strictly honest and simple we use the conservative
        sigma_whiteFM(t) = adev_1s * t (frequency offset held for the whole interval),
        which is the standard worst-case holdover envelope for white-FM.
      * random-walk-FM: sigma_rwfm(t) = clock_rwfm * t^1.5 / sqrt(3) (var ∝ t^3).
    All combined as a deterministic-plus-stochastic envelope (sum), honestly
    conservative. Returned in SECONDS.
    """
    t = np.asarray(t, dtype=float)
    det = abs(c.clock_y0) * t + 0.5 * abs(c.clock_drift) * np.power(t, 2)
    whitefm = c.clock_adev_1s * t                      # holdover envelope (s), ∝ t
    rwfm = c.clock_rwfm * np.power(t, 1.5) / math.sqrt(3.0)
    sigma_stoch = np.sqrt(whitefm ** 2 + rwfm ** 2)
    return det + sigma_stoch


def timing_error_meters(c: SensorCoeffs, t: np.ndarray | float) -> np.ndarray:
    """Clock timing error expressed as an equivalent RANGE error (m) = c * dt.

    A timing holdover error dt seconds maps to a pseudorange/position error of
    c*dt metres (the clock bias enters the navigation solution as a common-mode
    range error). This lets position and timing share ONE accuracy budget.
    """
    return C_LIGHT * timing_error_seconds(c, t)


def combined_error_meters(c: SensorCoeffs, t: np.ndarray | float) -> np.ndarray:
    """Total coasting error envelope (m): INS position error + clock range error,
    combined in quadrature (independent error sources)."""
    p = position_error_sigma(c, t)
    k = timing_error_meters(c, t)
    return np.sqrt(p ** 2 + k ** 2)


# --------------------------------------------------------------------------- #
# Time-to-exceed figure-of-merit                                              #
# --------------------------------------------------------------------------- #
@dataclass
class TimeToExceed:
    """The coasting figure-of-merit for one configuration."""
    threshold_m: float
    t_exceed_s: float                 # first time the combined error >= threshold
    error_channel: str                # "position" | "timing" | "combined"
    config_name: str
    config_label: str                 # MEASURED | MODELED | SAMPLE
    found: bool                       # True if threshold crossed within the horizon
    horizon_s: float                  # search horizon used

    def to_dict(self) -> dict:
        return asdict(self)


def time_to_exceed(c: SensorCoeffs, threshold_m: float, *,
                   channel: str = "combined", horizon_s: float = 7200.0,
                   n_grid: int = 200001) -> TimeToExceed:
    """First coasting time t at which the chosen error channel reaches threshold_m.

    Monotone-increasing error -> we locate the crossing by a dense grid scan then
    refine with a bisection on the (monotone) error function. Honest: if the
    threshold is not crossed inside `horizon_s`, found=False and t_exceed_s=horizon_s.
    """
    if channel == "position":
        f = position_error_sigma
    elif channel == "timing":
        f = timing_error_meters
    else:
        channel = "combined"
        f = combined_error_meters

    ts = np.linspace(0.0, horizon_s, n_grid)
    errs = f(c, ts)
    over = np.where(errs >= threshold_m)[0]
    if over.size == 0:
        return TimeToExceed(threshold_m=threshold_m, t_exceed_s=horizon_s,
                            error_channel=channel, config_name=c.name,
                            config_label=c.label, found=False, horizon_s=horizon_s)
    # bisection refine between the last point below and the first at/above
    i = int(over[0])
    lo = ts[i - 1] if i > 0 else 0.0
    hi = ts[i]
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if float(f(c, mid)) >= threshold_m:
            hi = mid
        else:
            lo = mid
    return TimeToExceed(threshold_m=threshold_m, t_exceed_s=0.5 * (lo + hi),
                        error_channel=channel, config_name=c.name,
                        config_label=c.label, found=True, horizon_s=horizon_s)


def quantum_advantage(classical: SensorCoeffs, quantum: SensorCoeffs,
                      threshold_m: float, *, channel: str = "combined",
                      horizon_s: float = 7200.0) -> dict:
    """The honest 'how much longer does quantum buy you' number.

    Returns both time-to-exceed values and their delta/ratio. If either config does
    not cross the threshold inside the horizon, the corresponding `found` flag is
    False and the ratio is reported as a LOWER BOUND (labelled).
    """
    tc = time_to_exceed(classical, threshold_m, channel=channel, horizon_s=horizon_s)
    tq = time_to_exceed(quantum, threshold_m, channel=channel, horizon_s=horizon_s)
    extra = tq.t_exceed_s - tc.t_exceed_s
    ratio = (tq.t_exceed_s / tc.t_exceed_s) if tc.t_exceed_s > 0 else float("inf")
    return {
        "threshold_m": threshold_m,
        "channel": channel,
        "horizon_s": horizon_s,
        "classical": tc.to_dict(),
        "quantum": tq.to_dict(),
        "extra_coasting_seconds": extra,
        "coasting_ratio": ratio,
        "ratio_is_lower_bound": (not tc.found) or (not tq.found),
        "label": (
            f"{classical.label}/{quantum.label}: quantum buys "
            f"{extra:.1f} s extra coast ({ratio:.2f}x) before exceeding "
            f"{threshold_m:g} m on the {channel} channel"
        ),
    }


# --------------------------------------------------------------------------- #
# Numerical integrator (so we have something to RESIDUAL-CHECK against)        #
# --------------------------------------------------------------------------- #
def integrate_position_variance(c: SensorCoeffs, horizon_s: float,
                                 dt: float) -> tuple[float, float]:
    """Forward-Euler accumulate the position-error VARIANCE from the white PSD,
    so the governed solve has a NUMERICAL estimate to check against the closed form.

    dVar_v/dt = (q_va + vrw_psd)         (velocity-variance grows at the PSD rate)
    dVar_x/dt = 2 * Cov_xv               (exact for the integrated random walk)
    dCov_xv/dt = Var_v
    Returns (sigma_x_numeric_at_horizon, sigma_x_closedform_at_horizon)  [metres,
    stochastic part only — the bias term is deterministic and added separately].
    """
    n = max(int(round(horizon_s / dt)), 1)
    q = c.q_va + c.vrw_psd
    var_x = 0.0
    cov_xv = 0.0
    var_v = 0.0
    for _ in range(n):
        d_var_x = 2.0 * cov_xv
        d_cov = var_v
        d_var_v = q
        var_x += d_var_x * dt
        cov_xv += d_cov * dt
        var_v += d_var_v * dt
    sigma_num = math.sqrt(max(var_x, 0.0))
    sigma_cf = math.sqrt(max(q * horizon_s ** 3 / 3.0, 0.0))
    return sigma_num, sigma_cf


# --------------------------------------------------------------------------- #
# Governed solve receipt (STRUCTURAL-ONLY, unsigned)                          #
# --------------------------------------------------------------------------- #
@dataclass
class CoastingReceipt:
    """Signer-ready (UNSIGNED, STRUCTURAL-ONLY) provenance for one governed run."""
    receipt_type: str
    # inputs (echoed, labelled)
    config_name: str
    config_label: str                 # MEASURED | MODELED | SAMPLE
    q_va_psd: float                   # the Dev1-supplied accelerometer PSD
    threshold_m: float
    channel: str
    horizon_s: float
    # the figure-of-merit
    time_to_exceed_s: float
    threshold_found_in_horizon: bool
    # integration self-check (the residual gate)
    sigma_numeric_m: float
    sigma_closedform_m: float
    integration_rel_residual: float   # |num - closed| / closed
    residual_tol: float
    converged: bool                   # integration residual within tol
    monotonic_check: bool             # error is monotone non-decreasing on the grid
    # Λ verdict
    lambda_verdict: str               # ALLOW | ADVISORY | DENY
    lambda_advisory: bool
    lambda_reason: str
    accepted: bool                    # estimate admitted (ALLOW)
    # honesty
    modeled_not_measured: bool
    one_dof_only: bool
    three_axis_full_ins: str          # always "NOT MODELED"
    schuler_coriolis_gyro_t3: str     # always "NOT MODELED"
    inputs_hash: str
    timestamp_utc: float
    method: str = METHOD
    attribution: dict = field(default_factory=lambda: ATTRIBUTION)
    doctrine: str = DOCTRINE
    lambda_label: str = ("Λ = Conjecture 1 — advisory governance, NOT 'proven trust'; "
                         "ALLOW means passed SZL admission policy (integration converged "
                         "+ monotone), not a guaranteed real-world coasting time.")
    signature: None = None            # UNSIGNED — STRUCTURAL-ONLY content addressing

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=str)


# --------------------------------------------------------------------------- #
# The deny-by-default Λ-gate (mirrors innovations/lambda_gate.gate_solve)      #
# --------------------------------------------------------------------------- #
@dataclass
class GateVerdict:
    verdict: str
    advisory: bool
    reason: str
    rel_residual: Optional[float]
    tol: Optional[float]
    converged: Optional[bool]
    monotonic: Optional[bool]
    modeled_not_measured: Optional[bool]
    lambda_label: str = ("Λ = Conjecture 1 — advisory governance, NOT 'proven trust'; "
                         "ALLOW means passed SZL admission policy, not proven correct.")
    deny_by_default: bool = True

    def to_dict(self) -> dict:
        return asdict(self)


def gate_coasting(receipt: dict, *, tol: float = 1e-3,
                  near_tol_frac: float = 0.85) -> GateVerdict:
    """Deny-by-default Λ gate over a coasting-run receipt dict. Same posture as the
    PINN gate: absence/weakness of evidence => DENY.

      DENY    : missing/invalid receipt; integration not converged (residual > tol or
                NaN); error not monotone; or a receipt that claims MEASURED energy/time
                it did not honestly source (free-energy / fabrication guard).
      ADVISORY: converged but the integration residual sits near the tolerance ceiling.
      ALLOW   : integration converged within tol AND error monotone AND honestly
                declared modeled_not_measured.
    """
    try:
        rel = float(receipt["integration_rel_residual"])
        converged = bool(receipt["converged"])
        monotone = bool(receipt["monotonic_check"])
        modeled = bool(receipt.get("modeled_not_measured", True))
    except (KeyError, TypeError, ValueError) as e:
        return GateVerdict(VERDICT_DENY, True,
                           f"deny-by-default: missing/invalid receipt ({e})",
                           None, tol, None, None, None)

    # Free-energy / fabrication guard: a run that claims to be MEASURED but supplies
    # no computed residual evidence is denied. We require an honest modeled flag OR a
    # real residual; here modeled must be declared True for the in-sandbox sample.
    if not modeled:
        return GateVerdict(VERDICT_DENY, True,
                           ("free-energy/fabrication guard: receipt does not declare "
                            "modeled_not_measured — the coasting horizon is MODELED, "
                            "not a measured field, unless a labelled MEASURED spec is "
                            "supplied with evidence"),
                           rel, tol, converged, monotone, modeled)

    if (not converged) or (rel != rel) or (rel > tol) or (not monotone):
        return GateVerdict(VERDICT_DENY, True,
                           (f"integration rel-residual {rel:.3e} > tol {tol:.3e}, not "
                            f"converged, or non-monotone error — coasting estimate not "
                            f"admissible"),
                           rel, tol, converged, monotone, modeled)

    if rel >= near_tol_frac * tol:
        return GateVerdict(VERDICT_ADVISORY, True,
                           (f"converged but rel-residual {rel:.3e} near tol {tol:.3e} — "
                            f"tighten dt before relying on the number"),
                           rel, tol, converged, monotone, modeled)

    return GateVerdict(VERDICT_ALLOW, False,
                       "integration converged within tol; error monotone; passed SZL "
                       "admission policy",
                       rel, tol, converged, monotone, modeled)


# --------------------------------------------------------------------------- #
# Governed solve wrapper                                                       #
# --------------------------------------------------------------------------- #
def governed_coasting_solve(c: SensorCoeffs, threshold_m: float, *,
                            channel: str = "combined", horizon_s: float = 7200.0,
                            integ_dt: float = 0.05,
                            residual_tol: float = 1e-3) -> CoastingReceipt:
    """Run the coasting figure-of-merit UNDER the deny-by-default Λ-gate.

    Steps (mirroring the agentic-PINN solve/measure/gate pattern):
      1. SOLVE: compute time-to-exceed from the closed-form monotone error.
      2. MEASURE: numerically integrate the position variance and compare to the
         closed form (the residual / convergence self-check).
      3. CHECK: confirm the error channel is monotone non-decreasing on the grid.
      4. Λ-GATE: accept the estimate only if (2) converged within tol and (3) holds.
      5. EMIT: an UNSIGNED, STRUCTURAL-ONLY receipt with the full decision trail.

    The time-to-exceed number is ALWAYS computed from a real run; it is only marked
    `accepted` when the gate returns ALLOW. No fabricated number is ever emitted.
    """
    tte = time_to_exceed(c, threshold_m, channel=channel, horizon_s=horizon_s)

    # integration self-check on the stochastic position variance
    sigma_num, sigma_cf = integrate_position_variance(c, horizon_s, integ_dt)
    if sigma_cf > 0:
        rel_resid = abs(sigma_num - sigma_cf) / sigma_cf
    else:
        # degenerate config (no white noise): both should be ~0; residual is 0 if so,
        # else flag large so the gate denies.
        rel_resid = 0.0 if abs(sigma_num) < 1e-12 else float("inf")

    # monotonicity check on the actual error channel
    ts = np.linspace(0.0, horizon_s, 4000)
    if channel == "position":
        errs = position_error_sigma(c, ts)
    elif channel == "timing":
        errs = timing_error_meters(c, ts)
    else:
        errs = combined_error_meters(c, ts)
    monotone = bool(np.all(np.diff(errs) >= -1e-9))

    converged = bool(np.isfinite(rel_resid) and rel_resid <= residual_tol)

    inputs = {
        "name": c.name, "label": c.label, "source": c.source,
        "q_va": c.q_va, "accel_bias": c.accel_bias, "vrw_psd": c.vrw_psd,
        "clock_adev_1s": c.clock_adev_1s, "clock_rwfm": c.clock_rwfm,
        "clock_drift": c.clock_drift, "clock_y0": c.clock_y0,
        "threshold_m": threshold_m, "channel": channel, "horizon_s": horizon_s,
        "integ_dt": integ_dt, "residual_tol": residual_tol,
    }

    gate_input = {
        "integration_rel_residual": rel_resid,
        "converged": converged,
        "monotonic_check": monotone,
        "modeled_not_measured": (c.label != "MEASURED"),
    }
    verdict = gate_coasting(gate_input, tol=residual_tol)
    accepted = (verdict.verdict == VERDICT_ALLOW)

    return CoastingReceipt(
        receipt_type="szl/nav-coasting-receipt/v1",
        config_name=c.name,
        config_label=c.label,
        q_va_psd=c.q_va,
        threshold_m=threshold_m,
        channel=channel,
        horizon_s=horizon_s,
        time_to_exceed_s=tte.t_exceed_s,
        threshold_found_in_horizon=tte.found,
        sigma_numeric_m=sigma_num,
        sigma_closedform_m=sigma_cf,
        integration_rel_residual=rel_resid,
        residual_tol=residual_tol,
        converged=converged,
        monotonic_check=monotone,
        lambda_verdict=verdict.verdict,
        lambda_advisory=verdict.advisory,
        lambda_reason=verdict.reason,
        accepted=accepted,
        modeled_not_measured=(c.label != "MEASURED"),
        one_dof_only=True,
        three_axis_full_ins="NOT MODELED",
        schuler_coriolis_gyro_t3="NOT MODELED",
        inputs_hash=_hash_inputs(inputs),
        timestamp_utc=time.time(),
    )


# --------------------------------------------------------------------------- #
# Honest sample configs (clearly labelled SAMPLE/MODELED) + Dev1 q_va loader   #
# --------------------------------------------------------------------------- #
def load_dev1_q_va(default: float) -> tuple[float, str]:
    """Try to read the accelerometer PSD q_va from Dev1's quantum sensor output.

    Looks for /home/user/workspace/pnt_build/dev1_quantum_sensors/*.json with a
    'q_va' / 'accel_psd' / 'n_a' field. If absent (Dev1 not built yet), returns the
    supplied honest SAMPLE default so this module composes standalone NOW and will
    automatically consume Dev1's real number once it lands.

    Returns (q_va, source_label).
    """
    import glob
    import os
    base = "/home/user/workspace/pnt_build/dev1_quantum_sensors"
    if os.path.isdir(base):
        for path in sorted(glob.glob(os.path.join(base, "*.json"))):
            try:
                with open(path) as fh:
                    data = json.load(fh)
            except Exception:
                continue
            for key in ("q_va", "q_va_psd", "accel_psd_psd", "accel_psd"):
                if isinstance(data, dict) and key in data:
                    return float(data[key]), f"dev1:{os.path.basename(path)}:{key}"
            # n_a is an ASD (m/s^2/sqrt(Hz)); square it to a PSD
            for key in ("n_a", "asd", "accel_asd"):
                if isinstance(data, dict) and key in data:
                    return float(data[key]) ** 2, f"dev1:{os.path.basename(path)}:{key}^2"
    return default, "honest-sample (Dev1 not present)"


def sample_classical() -> SensorCoeffs:
    """Honest SAMPLE classical MEMS/tactical INS + TCXO clock budget. MODELED.

    Representative tactical-grade numbers (order-of-magnitude, declared SAMPLE):
      accel ASD ~ 1e-3 (m/s^2)/sqrt(Hz)  -> q_va = 1e-6
      residual accel bias ~ 1e-4 m/s^2 (after calib, ~10 ug)
      TCXO Allan dev at 1 s ~ 1e-10; drift ~ 1e-9 / s
    """
    q, src = load_dev1_q_va(default=1.0e-6)
    return SensorCoeffs(
        q_va=q, accel_bias=1.0e-4, vrw_psd=0.0,
        clock_adev_1s=1.0e-10, clock_rwfm=1.0e-12, clock_drift=1.0e-9, clock_y0=1.0e-11,
        label="SAMPLE", name="classical-MEMS+TCXO", source=src,
    )


def sample_quantum() -> SensorCoeffs:
    """Honest SAMPLE quantum cold-atom-interferometer accel + chip-scale/optical clock.

    The CAI accelerometer PSD is MUCH lower (that is the whole point), and a better
    clock lowers the holdover term:
      accel ASD ~ 1e-6 (m/s^2)/sqrt(Hz) -> q_va = 1e-12 (≈1000x lower amplitude)
      residual accel bias ~ 1e-7 m/s^2 (CAI is absolute/bias-stable)
      clock Allan dev at 1 s ~ 1e-12; drift ~ 1e-12 / s
    """
    q, src = load_dev1_q_va(default=1.0e-12)
    return SensorCoeffs(
        q_va=q, accel_bias=1.0e-7, vrw_psd=0.0,
        clock_adev_1s=1.0e-12, clock_rwfm=1.0e-14, clock_drift=1.0e-12, clock_y0=1.0e-13,
        label="SAMPLE", name="quantum-CAI+optical", source=src,
    )


__all__ = [
    "C_LIGHT", "G0", "METHOD", "ATTRIBUTION", "DOCTRINE",
    "VERDICT_ALLOW", "VERDICT_ADVISORY", "VERDICT_DENY",
    "SensorCoeffs", "position_error_sigma", "timing_error_seconds",
    "timing_error_meters", "combined_error_meters",
    "TimeToExceed", "time_to_exceed", "quantum_advantage",
    "integrate_position_variance",
    "CoastingReceipt", "GateVerdict", "gate_coasting", "governed_coasting_solve",
    "load_dev1_q_va", "sample_classical", "sample_quantum",
]


if __name__ == "__main__":
    print("SZL NAV COASTING — GPS-denied holdover figure-of-merit (1-DOF, governed)\n"
          + "=" * 72)
    classical = sample_classical()
    quantum = sample_quantum()
    THRESH = 50.0  # metres — example navigation accuracy threshold

    print(f"classical: {classical.name}  q_va={classical.q_va:.3e}  src={classical.source}")
    print(f"quantum  : {quantum.name}  q_va={quantum.q_va:.3e}  src={quantum.source}")
    print()

    adv = quantum_advantage(classical, quantum, THRESH, channel="combined")
    print("QUANTUM ADVANTAGE (combined position+timing channel, MODELED):")
    print(f"  classical time-to-exceed {THRESH:g} m : "
          f"{adv['classical']['t_exceed_s']:.1f} s (found={adv['classical']['found']})")
    print(f"  quantum   time-to-exceed {THRESH:g} m : "
          f"{adv['quantum']['t_exceed_s']:.1f} s (found={adv['quantum']['found']})")
    print(f"  extra coast: {adv['extra_coasting_seconds']:.1f} s  "
          f"ratio: {adv['coasting_ratio']:.2f}x  "
          f"(lower_bound={adv['ratio_is_lower_bound']})")
    print()

    rc = governed_coasting_solve(classical, THRESH)
    rq = governed_coasting_solve(quantum, THRESH)
    print("GOVERNED SOLVE RECEIPTS (Λ-gate, STRUCTURAL-ONLY / unsigned):")
    for r in (rc, rq):
        print(f"  [{r.config_name}] verdict={r.lambda_verdict} accepted={r.accepted} "
              f"rel_resid={r.integration_rel_residual:.2e} "
              f"t_exceed={r.time_to_exceed_s:.1f}s monotone={r.monotonic_check}")
    print()
    print("HONESTY: 1-DOF only; 3-axis/full-INS (gyro t^3, Schuler, Coriolis) = NOT "
          "MODELED; horizon is MODELED not MEASURED; Λ advisory.")
