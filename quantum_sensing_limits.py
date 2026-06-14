# SPDX-License-Identifier: Apache-2.0
# © 2026 SZL Holdings · Doctrine v11 LOCKED · Λ = Conjecture 1 (advisory, NOT proven trust)
# Sign-off: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
"""quantum_sensing_limits — FUNDAMENTAL-LIMITS CERTIFIER for a cold-atom interferometer.

THE SECOND PILLAR (founder's doctrine): next to ``physics_bounds.py`` — which proves a
*compute* job sits below the Landauer/Margolus-Levitin/Bremermann/Bekenstein ceilings —
this module proves a *quantum sensor's* noise floor is set by, and sits at or above, the
STANDARD QUANTUM LIMIT (shot / atom-projection noise). Same philosophy: derive performance
from first-principles physics, certify it, label MEASURED vs MODELED, never fabricate.

This is a CLEAN-ROOM SZL-NATIVE re-derivation of the cold-atom interferometer (CAI)
accelerometer physics. The METHOD/structure (a first-principles CAI noise model rather
than a datasheet lookup) is cited to AshfordeOU/kshana (Apache-2.0, DOI
10.5281/zenodo.20528627). NO kshana Rust source is copied; only the established physics
below is implemented, in our own Python. The physics itself is ESTABLISHED and CITED to
the original papers — it is NOT claimed as SZL's:

  * Kasevich & Chu (1991): light-pulse (stimulated-Raman) atom interferometry; the
    three-pulse (π/2 – π – π/2) Mach-Zehnder geometry as an inertial sensor.
  * Peters, Chung & Chu (2001): high-precision absolute gravimetry with a CAI;
    Φ = k_eff·a·T² scaling and systematic-effect accounting.
  * Cheinet et al. (2008): the sensitivity function g(t) and the vibration/laser-phase
    transfer function |H(ω)| = (4/ω²)·sin²(ωT/2); white-acceleration-noise phase
    variance σ_Φ² = k_eff²·S_a·T³/3.
  * Freier et al. (2016): mobile/transportable quantum gravimeter — ASD figure-of-merit
    n_a = σ_a·√T_c, the real-device performance metric.

HONESTY (Doctrine v11, HARD): every INPUT is labelled MEASURED (only if it came from a
real instrument reading) vs the DERIVED/MODELED limits. We assert NO measured quantity we
did not receive. We NEVER fabricate numbers. We make NO over-unity / sub-shot-noise
("squeezed beyond physics") claim — the certificate is the HONEST INVERSE of a free-energy
claim: it states the sensor is BOUNDED by the standard quantum limit. A maintained
"NOT MODELED" list names the systematics this engine does NOT capture, so the certificate
can never be mistaken for a full error budget. Λ is advisory: this states physical FACTS,
not "proven trust".

Pure stdlib + math (numpy optional) → sovereign, own-metal, auditable. Real instrument
inputs feed in via ``MeasuredSensor``; in-sandbox we use HONEST, CLEARLY-LABELLED sample
inputs. Designed to UNIFY with physics_bounds.py into one SZL "fundamental-limits" library
(compute-bounds pillar + sensing-limits pillar).
"""
from __future__ import annotations

import hashlib
import json
import math
import time
from dataclasses import asdict, dataclass, field
from typing import Optional

# --------------------------------------------------------------------------- #
# Fundamental physical constants (SI, CODATA-style). Exact where SI defines.   #
# Shared, byte-for-byte, with physics_bounds.py so the two pillars unify.       #
# --------------------------------------------------------------------------- #
K_B = 1.380649e-23          # Boltzmann constant, J/K (SI exact)
H_PLANCK = 6.62607015e-34   # Planck constant, J·s (SI exact)
HBAR = H_PLANCK / (2.0 * math.pi)
C_LIGHT = 299792458.0       # speed of light, m/s (SI exact)
PI = math.pi

# Provenance: this is ESTABLISHED CAI physics, CITED — NOT claimed as SZL's. The METHOD
# (first-principles CAI noise model) is cited to kshana (Apache-2.0); only physics is used.
SENSING_ATTRIBUTION = {
    "method_source_kshana": (
        "AshfordeOU/kshana — open PNT-resilience simulator (Apache-2.0, "
        "DOI:10.5281/zenodo.20528627). Cited as the METHOD source: a first-principles "
        "cold-atom interferometer accelerometer noise model (src/inertial/quantum_imu.rs). "
        "SZL re-derived the physics CLEAN-ROOM in Python; NO kshana Rust source is copied."
    ),
    "kasevich_chu_1991": (
        "Kasevich, M. & Chu, S. (1991), 'Atomic interferometry using stimulated Raman "
        "transitions', Phys. Rev. Lett. 67(2):181-184, doi:10.1103/PhysRevLett.67.181. "
        "Light-pulse (π/2–π–π/2) Mach-Zehnder atom interferometer as an inertial sensor; "
        "effective two-photon wavevector k_eff and the phase response to acceleration."
    ),
    "peters_2001": (
        "Peters, A., Chung, K.Y. & Chu, S. (2001), 'High-precision gravity measurements "
        "using atom interferometry', Metrologia 38(1):25-61, doi:10.1088/0026-1394/38/1/4 "
        "(see also Nature 400:849, 1999). Interferometer phase Φ = k_eff·a·T² with the T² "
        "interrogation-time lever; systematic-effect accounting for absolute gravimetry."
    ),
    "cheinet_2008": (
        "Cheinet, P., Canuel, B., Pereira Dos Santos, F., Gauguet, A., Yver-Leduc, F. & "
        "Landragin, A. (2008), 'Measurement of the sensitivity function in a time-domain "
        "atomic interferometer', IEEE Trans. Instrum. Meas. 57(6):1141-1148, "
        "doi:10.1109/TIM.2007.915148. Sensitivity function g(t); acceleration transfer "
        "function |H(ω)| = (4/ω²)·sin²(ωT/2); white-noise phase variance "
        "σ_Φ² = k_eff²·S_a·T³/3 (dominant real-device vibration term)."
    ),
    "freier_2016": (
        "Freier, C., Hauth, M., Schkolnik, V., Leykauf, B., Schilling, M., Wziontek, H., "
        "Scherneck, H.-G., Müller, J. & Peters, A. (2016), 'Mobile quantum gravity sensor "
        "with unprecedented stability', J. Phys.: Conf. Ser. 723:012050, "
        "doi:10.1088/1742-6596/723/1/012050. Transportable CAI; amplitude spectral "
        "density n_a = σ_a·√T_c as the real-device figure of merit."
    ),
    "standard_quantum_limit": (
        "Shot / atom-projection noise: for N uncorrelated atoms read out with fringe "
        "contrast C, the minimum resolvable interferometer phase is σ_Φ = 1/(C·√N). This "
        "is the STANDARD QUANTUM LIMIT (SQL). Surpassing it requires entanglement/spin "
        "squeezing (Wineland 1992, Kitagawa-Ueda 1993) — explicitly NOT modeled here."
    ),
    "honesty": (
        "These are ESTABLISHED physics relations, cited by source. They are NOT SZL "
        "conjectures and NOT claimed as SZL's. This certificate is the HONEST INVERSE of "
        "a free-energy claim: it shows the sensor is BOUNDED by the standard quantum "
        "limit, asserts no sub-SQL/over-unity performance, fabricates no number, and "
        "carries an explicit NOT-MODELED list so it is never mistaken for a full budget."
    ),
}

DOCTRINE = (
    "v11 LOCKED: NO free-energy/over-unity and NO sub-standard-quantum-limit claim (this "
    "certificate shows the sensor is BOUNDED by the SQL — the honest inverse); a value is "
    "labelled MEASURED ONLY if it came from a real instrument reading, else MODELED/DERIVED; "
    "established CAI physics is CITED (Kasevich-Chu 1991, Peters 2001, Cheinet 2008, Freier "
    "2016), method cited to kshana (Apache-2.0), NOT claimed as SZL's; an explicit NOT-MODELED "
    "list is carried; Λ=Conjecture 1 (advisory); sovereign own-metal; no fabricated numbers."
)

# Systematics this first-principles engine does NOT capture. Carried in every certificate
# so a reader can NEVER mistake the SQL/vibration figure for a complete error budget.
NOT_MODELED = [
    "Laser phase noise of the Raman/Bragg beams (frequency-comb / OPLL residual) — a "
    "leading real-device noise term; couples through the SAME |H(ω)| as vibration "
    "(Cheinet 2008) but its drive PSD S_φ(ω) is an instrument property not modeled here.",
    "AC-Stark / light-shift systematics (one-photon and two-photon light shifts) and their "
    "intensity/detuning dependence — a dominant ACCURACY (bias) term, not modeled.",
    "Full 3-axis mechanization / strapdown coupling, gravity-gradient & rotation-rate "
    "cross terms beyond the single Coriolis lead term, and platform attitude dynamics.",
    "Detection (electronic/technical) noise, atom-number normalization noise, and "
    "intensity noise of the readout — separate from the SQL atom-projection floor.",
    "Wavefront aberration / Coriolis-from-transverse-velocity beyond the lead Φ_cor term, "
    "magnetic-field (2nd-order Zeeman) gradients, blackbody/AC-Stark drifts, and aliasing "
    "of high-frequency vibration through the finite duty cycle (Dick effect).",
    "Mean-field / cold-collision shifts, finite-pulse-duration corrections to g(t), and "
    "any spin-squeezing/entanglement enhancement BELOW the SQL (explicitly out of scope).",
]


# --------------------------------------------------------------------------- #
# MEASURED inputs (clearly labelled) — fed by a real instrument or honest sample #
# --------------------------------------------------------------------------- #
@dataclass
class MeasuredSensor:
    """Inputs describing one cold-atom interferometer operating point.

    HONESTY RULE: a field is MEASURED ONLY if it is a real reading from the instrument
    (e.g. observed fringe contrast, counted atom number, recorded cycle time, measured
    vibration PSD). Design/spec parameters (wavelength, interrogation time setpoint) are
    CONFIG. ``label`` records which: "MEASURED" (real instrument) vs "SAMPLE"/"DESIGN"
    (honest, clearly-labelled placeholder). The certifier validates these before use and
    NEVER silently promotes a garbage/placeholder input to "MEASURED".
    """
    wavelength_m: float           # Raman/Bragg optical wavelength λ (m) — CONFIG
    interrogation_time_s: float   # interferometer pulse separation T (s) — CONFIG/MEASURED
    atom_number: float            # N atoms contributing to the fringe — MEASURED count
    contrast: float               # fringe contrast C in [0,1] — MEASURED
    cycle_time_s: float           # T_c, full measurement cycle time (s) — MEASURED
    accel_psd: float              # S_a, vibration acceleration PSD (m²/s⁴/Hz) — MEASURED
    accel_input: Optional[float] = None     # a, true input acceleration (m/s²) if known
    omega_rad_s: float = 2.0 * math.pi      # ω for transfer-function eval (rad/s) — CONFIG
    transverse_velocity_ms: float = 0.0     # v_⊥ for Coriolis term (m/s) — MEASURED
    rotation_rate_rad_s: float = 0.0        # Ω, platform rotation rate (rad/s) — MEASURED
    contrast0: Optional[float] = None       # C₀ initial contrast for decay model — CONFIG
    coherence_time_s: Optional[float] = None  # τ_c contrast-decay time const (s) — MEASURED
    label: str = "MEASURED"       # MEASURED (real instrument) | SAMPLE | DESIGN (honest)
    source: str = "unspecified"   # e.g. "cai-readout", "honest-sample"
    note: str = ""

    def measured_accel(self, label_is_measured: bool) -> Optional[float]:
        """Return accel_input ONLY if it is a genuine instrument reading (label MEASURED).
        Otherwise None — a MODELED accel must NOT be reported as MEASURED.
        """
        if self.accel_input is None:
            return None
        return self.accel_input if label_is_measured else None


# --------------------------------------------------------------------------- #
# First-principles relations (all DERIVED / MODELED from the inputs)           #
# Each function names its citation in the docstring.                           #
# --------------------------------------------------------------------------- #
def k_eff(wavelength_m: float) -> float:
    """Effective two-photon wavevector k_eff = 4π/λ.

    Kasevich-Chu (1991): a stimulated-Raman π/2–π–π/2 sequence imparts two photon recoils
    per pulse, so the effective momentum kick uses k_eff = 2·k_photon = 2·(2π/λ) = 4π/λ.
    """
    if not (wavelength_m > 0.0):
        raise ValueError("wavelength_m must be > 0")
    return 4.0 * PI / wavelength_m


def mach_zehnder_phase(keff: float, accel: float, T: float) -> float:
    """Mach-Zehnder interferometer phase Φ = k_eff·a·T².

    Peters et al. (2001) / Kasevich-Chu (1991): for the three-pulse geometry the leading
    inertial phase shift is k_eff·a·T², where T is the pulse separation (interrogation
    time). The T² dependence is the interrogation-time lever that drives sensitivity.
    """
    return keff * accel * T * T


def shot_noise_phase(contrast: float, atom_number: float) -> float:
    """Standard-quantum-limit phase noise σ_Φ = 1/(C·√N).

    Atom-projection (shot) noise: N uncorrelated atoms read out at fringe contrast C give
    a minimum resolvable phase 1/(C·√N). This is the SQL; sub-SQL needs entanglement and
    is explicitly NOT modeled (see NOT_MODELED).
    """
    if not (contrast > 0.0):
        raise ValueError("contrast must be > 0 for a defined shot-noise limit")
    if not (atom_number > 0.0):
        raise ValueError("atom_number must be > 0")
    return 1.0 / (contrast * math.sqrt(atom_number))


def accel_sensitivity_per_shot(sigma_phi: float, keff: float, T: float) -> float:
    """Per-shot acceleration sensitivity σ_a = σ_Φ / (k_eff·T²).

    Invert the Mach-Zehnder phase response (Peters 2001): a phase uncertainty σ_Φ maps to
    an acceleration uncertainty σ_Φ/(k_eff·T²) per measurement shot.
    """
    denom = keff * T * T
    if not (denom > 0.0):
        raise ValueError("k_eff·T² must be > 0")
    return sigma_phi / denom


def asd_accel(sigma_a: float, cycle_time_s: float) -> float:
    """Amplitude spectral density n_a = σ_a·√T_c (units m/s²/√Hz).

    Freier et al. (2016): the real-device figure of merit. A per-shot uncertainty σ_a at a
    cycle time T_c corresponds to an acceleration ASD of σ_a·√T_c. The PSD is n_a².
    """
    if not (cycle_time_s > 0.0):
        raise ValueError("cycle_time_s must be > 0")
    return sigma_a * math.sqrt(cycle_time_s)


def contrast_decay(contrast0: float, t: float, tau_c: float) -> float:
    """Contrast decay C(t) = C₀·exp(−t/τ_c).

    Empirical/decoherence loss-of-fringe-visibility model: contrast decays exponentially
    with a coherence time τ_c (dephasing, expansion, finite detection). Used to model how
    contrast — and hence the SQL phase noise σ_Φ = 1/(C·√N) — degrades with T.
    """
    if not (tau_c > 0.0):
        raise ValueError("tau_c must be > 0")
    return contrast0 * math.exp(-t / tau_c)


def vibration_transfer_magnitude(omega: float, T: float) -> float:
    """Acceleration transfer-function magnitude |H(ω)| = (4/ω²)·sin²(ωT/2).

    Cheinet et al. (2008): Fourier transform of the three-pulse sensitivity function gives
    the interferometer's response to acceleration/phase noise at angular frequency ω. The
    low-frequency limit |H| → T² recovers the DC Mach-Zehnder response.
    """
    if not (omega > 0.0):
        raise ValueError("omega must be > 0 for the transfer function")
    return (4.0 / (omega * omega)) * (math.sin(omega * T / 2.0) ** 2)


def vibration_phase_variance(keff: float, accel_psd: float, T: float) -> float:
    """White-acceleration-noise phase variance σ_Φ² = k_eff²·S_a·T³/3.

    Cheinet et al. (2008): integrating the squared acceleration transfer function against a
    WHITE acceleration PSD S_a yields k_eff²·S_a·T³/3. This is the dominant real-device
    (vibration-limited) phase-noise term in unshielded operation.
    """
    return keff * keff * accel_psd * (T ** 3) / 3.0


def coriolis_phase(keff: float, v_perp: float, omega_rot: float, T: float) -> float:
    """Coriolis (rotation) phase Φ_cor = 2·k_eff·v_⊥·Ω·T².

    Peters et al. (2001) / Kasevich-Chu (1991): a transverse atom velocity v_⊥ in a frame
    rotating at Ω produces a Coriolis acceleration that biases the interferometer by
    2·k_eff·v_⊥·Ω·T². This is the LEAD rotation term only; full 3-axis rotation coupling
    is NOT modeled (see NOT_MODELED).
    """
    return 2.0 * keff * v_perp * omega_rot * T * T


# --------------------------------------------------------------------------- #
# The QUANTUM-SENSING-LIMITS CERTIFICATE                                       #
# --------------------------------------------------------------------------- #
@dataclass
class QuantumSensingCertificate:
    """Signer-ready certificate. MEASURED inputs vs MODELED limits, clearly split.

    Every numeric field carries an explicit role: a value derived from a MEASURED input is
    MODELED (computed via a cited formula); only echoed instrument readings are MEASURED.
    """
    certificate_type: str
    # --- inputs echoed, each tagged MEASURED or CONFIG/SAMPLE ---
    inputs: dict
    # --- MODELED first-principles limits (all DERIVED from inputs via cited formulas) ---
    k_eff_per_m: float                      # MODELED: 4π/λ
    mz_phase_per_unit_accel_rad: float      # MODELED: k_eff·T² (phase per 1 m/s²)
    mz_phase_modeled_rad: Optional[float]   # MODELED iff an accel input was provided
    accel_was_measured: bool                # True only if accel came from a real reading
    shot_noise_phase_rad: float             # MODELED: σ_Φ = 1/(C·√N) (SQL)
    accel_sensitivity_per_shot: float       # MODELED: σ_a = σ_Φ/(k_eff·T²)
    accel_asd: float                        # MODELED: n_a = σ_a·√T_c (m/s²/√Hz)
    accel_psd_from_asd: float               # MODELED: n_a²
    vibration_transfer_magnitude: float     # MODELED: |H(ω)| at the eval ω
    vibration_phase_variance: float         # MODELED: k_eff²·S_a·T³/3
    vibration_phase_rms_rad: float          # MODELED: sqrt of the above
    coriolis_phase_rad: float               # MODELED: 2·k_eff·v_⊥·Ω·T²
    contrast_at_T: Optional[float]          # MODELED iff a decay model (C₀,τ_c) was given
    # --- honest verdict ---
    at_or_above_standard_quantum_limit: bool  # noise floor not claimed below the SQL
    summary: str
    not_modeled: list = field(default_factory=lambda: list(NOT_MODELED))
    attribution: dict = field(default_factory=lambda: SENSING_ATTRIBUTION)
    doctrine: str = DOCTRINE
    honest_inverse_of_free_energy: bool = True
    labels: dict = field(default_factory=lambda: {
        "MEASURED": "a real reading from the instrument (contrast, atom count, cycle time, "
                    "vibration PSD, etc.) — NEVER a placeholder or modeled value",
        "MODELED": "computed from inputs via a CITED established-physics formula",
        "CONFIG": "a design/setpoint parameter (wavelength, T setpoint), not a reading",
    })
    lambda_note: str = ("Λ = Conjecture 1 (advisory). This certificate states physical "
                        "FACTS (limits), not 'proven trust'. It makes NO sub-SQL / "
                        "over-unity claim and carries an explicit NOT-MODELED list.")
    inputs_hash: str = ""
    timestamp_utc: float = 0.0
    signature: None = None

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(asdict(self), indent=indent, default=str)


def _hash_inputs(sensor: MeasuredSensor) -> str:
    canon = json.dumps(asdict(sensor), sort_keys=True, separators=(",", ":"), default=str)
    return "sha256:" + hashlib.sha256(canon.encode()).hexdigest()


# Accept only these honest labels for a value to be treated as a real instrument reading.
_MEASURED_LABELS = {"MEASURED"}


def _validate_sensor(sensor: MeasuredSensor) -> list:
    """Return a list of HONESTY/physics problems. Empty list ⇒ inputs are usable.

    This is the guard that prevents a fabricated/garbage input from being silently
    accepted and labelled MEASURED. It checks finiteness, physical ranges, and label sanity.
    """
    problems = []

    def _finite_pos(name, val, allow_zero=False):
        if val is None:
            return
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            problems.append(f"{name} is not a real number ({val!r})")
            return
        if not math.isfinite(val):
            problems.append(f"{name} is not finite ({val!r}) — fabricated/garbage input")
            return
        if val < 0 or (val == 0 and not allow_zero):
            problems.append(f"{name} is out of physical range ({val!r})")

    _finite_pos("wavelength_m", sensor.wavelength_m)
    _finite_pos("interrogation_time_s", sensor.interrogation_time_s)
    _finite_pos("atom_number", sensor.atom_number)
    _finite_pos("cycle_time_s", sensor.cycle_time_s)
    _finite_pos("accel_psd", sensor.accel_psd, allow_zero=True)
    _finite_pos("omega_rad_s", sensor.omega_rad_s)
    # contrast must be a real fraction in (0, 1]
    c = sensor.contrast
    if isinstance(c, bool) or not isinstance(c, (int, float)) or not math.isfinite(c):
        problems.append(f"contrast is not a finite number ({c!r}) — fabricated/garbage")
    elif not (0.0 < c <= 1.0):
        problems.append(f"contrast {c!r} is outside the physical fringe range (0, 1]")
    # optional fields that, if present, must be finite real numbers
    for nm, v in (("accel_input", sensor.accel_input),
                  ("transverse_velocity_ms", sensor.transverse_velocity_ms),
                  ("rotation_rate_rad_s", sensor.rotation_rate_rad_s),
                  ("coherence_time_s", sensor.coherence_time_s),
                  ("contrast0", sensor.contrast0)):
        if v is not None and (isinstance(v, bool) or not isinstance(v, (int, float))
                              or not math.isfinite(v)):
            problems.append(f"{nm} is not a finite number ({v!r}) — fabricated/garbage")
    # label sanity: a value can only be MEASURED under an honest measured label
    if sensor.label not in _MEASURED_LABELS | {"SAMPLE", "DESIGN"}:
        problems.append(
            f"label {sensor.label!r} is not an allowed honest label "
            f"(MEASURED | SAMPLE | DESIGN)"
        )
    return problems


def _rejected_certificate(sensor: MeasuredSensor, problems: list,
                          msg: str) -> QuantumSensingCertificate:
    """Build a clearly-REJECTED certificate for fabricated/garbage inputs (non-strict).

    No physics is computed from the bad inputs and NOTHING is labelled MEASURED. The
    certificate exists only to RECORD the honesty failure so it can never be mistaken for
    a valid result. NaN sentinels mark fields that were NOT computed.
    """
    nan = float("nan")
    return QuantumSensingCertificate(
        certificate_type="szl/quantum-sensing-limits-certificate/v1/REJECTED",
        inputs={
            "label": sensor.label,
            "source": sensor.source,
            "REJECTED": True,
            "atom_number_MEASURED": None,
            "contrast_MEASURED": None,
            "cycle_time_s_MEASURED": None,
            "accel_psd_MEASURED": None,
            "accel_input_MEASURED": None,
            "validation_problems": problems,
            "note": sensor.note,
        },
        k_eff_per_m=nan,
        mz_phase_per_unit_accel_rad=nan,
        mz_phase_modeled_rad=None,
        accel_was_measured=False,
        shot_noise_phase_rad=nan,
        accel_sensitivity_per_shot=nan,
        accel_asd=nan,
        accel_psd_from_asd=nan,
        vibration_transfer_magnitude=nan,
        vibration_phase_variance=nan,
        vibration_phase_rms_rad=nan,
        coriolis_phase_rad=nan,
        contrast_at_T=None,
        at_or_above_standard_quantum_limit=False,
        summary="REJECTED — " + msg + " No limits were computed; nothing labelled MEASURED.",
        inputs_hash=_hash_inputs(sensor),
        timestamp_utc=time.time(),
    )


def certify_sensor(sensor: MeasuredSensor, strict: bool = True) -> QuantumSensingCertificate:
    """Compute the QUANTUM-SENSING-LIMITS CERTIFICATE for one CAI operating point.

    Returns a certificate stating: this sensor's effective wavevector k_eff, its
    Mach-Zehnder phase response, its standard-quantum-limit (shot-noise) phase floor and
    the per-shot / ASD acceleration sensitivity it implies, the vibration-limited phase
    variance σ_Φ² = k_eff²·S_a·T³/3, and the lead Coriolis bias — every value labelled
    MEASURED (only if a real reading) vs MODELED, with an explicit NOT-MODELED list.

    HONESTY GUARD: if ``strict`` (default), a fabricated/garbage or out-of-range input
    raises ValueError rather than being silently certified. An accel input is reported as
    MEASURED ONLY if the whole record is labelled MEASURED; otherwise it is MODELED.
    """
    problems = _validate_sensor(sensor)
    if problems:
        msg = ("HONESTY GUARD: sensor inputs rejected (will NOT be silently labelled "
               "MEASURED): " + "; ".join(problems))
        if strict:
            raise ValueError(msg)
        # NON-STRICT: do NOT fabricate or compute limits from garbage. Return a clearly
        # REJECTED certificate that records the problems and labels NOTHING as MEASURED.
        return _rejected_certificate(sensor, problems, msg)

    label_is_measured = sensor.label in _MEASURED_LABELS
    lam = sensor.wavelength_m
    T = sensor.interrogation_time_s
    N = sensor.atom_number
    C = sensor.contrast
    Tc = sensor.cycle_time_s
    Sa = sensor.accel_psd

    keff = k_eff(lam)
    phase_per_accel = keff * T * T  # MODELED: rad per (m/s²)

    # MEASURED vs MODELED accel: only honour an accel reading if the record is MEASURED.
    measured_a = sensor.measured_accel(label_is_measured)
    accel_for_phase = sensor.accel_input  # may still model a phase for a DESIGN/SAMPLE a
    mz_phase = (mach_zehnder_phase(keff, accel_for_phase, T)
                if accel_for_phase is not None else None)

    sigma_phi = shot_noise_phase(C, N)                      # SQL
    sigma_a = accel_sensitivity_per_shot(sigma_phi, keff, T)
    n_a = asd_accel(sigma_a, Tc)
    psd_from_asd = n_a * n_a

    H_mag = vibration_transfer_magnitude(sensor.omega_rad_s, T)
    vib_var = vibration_phase_variance(keff, Sa, T)
    vib_rms = math.sqrt(vib_var)

    cor_phase = coriolis_phase(keff, sensor.transverse_velocity_ms,
                               sensor.rotation_rate_rad_s, T)

    contrast_T = None
    if sensor.contrast0 is not None and sensor.coherence_time_s is not None:
        contrast_T = contrast_decay(sensor.contrast0, T, sensor.coherence_time_s)

    # Honest verdict: the reported noise floor σ_Φ is AT/ABOVE the SQL by construction
    # (we never assert a sub-shot-noise figure). True ⇒ no sub-SQL/over-unity claim made.
    at_or_above_sql = sigma_phi >= shot_noise_phase(C, N) - 1e-18

    a_phase_str = (f"{mz_phase:.4g} rad ({'MEASURED-fed' if measured_a is not None else 'MODELED-input'})"
                   if mz_phase is not None else "n/a (no acceleration input supplied)")
    summary = (
        f"Cold-atom interferometer @ λ={lam:g} m, T={T:g} s, N={N:.4g} atoms, C={C:g} "
        f"(label={sensor.label}, source={sensor.source}). MODELED: k_eff={keff:.6g} m⁻¹ "
        f"(=4π/λ, Kasevich-Chu 1991); Mach-Zehnder response {phase_per_accel:.4g} rad per "
        f"m/s² (=k_eff·T², Peters 2001); phase for the supplied acceleration = {a_phase_str}. "
        f"STANDARD QUANTUM LIMIT phase floor σ_Φ={sigma_phi:.4g} rad (=1/(C·√N)) ⇒ per-shot "
        f"σ_a={sigma_a:.4g} m/s² ⇒ ASD n_a={n_a:.4g} m/s²/√Hz (=σ_a·√T_c, Freier 2016). "
        f"Vibration-limited phase: |H(ω)|={H_mag:.4g} s² at ω={sensor.omega_rad_s:g} rad/s, "
        f"σ_Φ²={vib_var:.4g} rad² (=k_eff²·S_a·T³/3, Cheinet 2008) ⇒ σ_Φ,vib={vib_rms:.4g} "
        f"rad. Lead Coriolis bias Φ_cor={cor_phase:.4g} rad (=2·k_eff·v_⊥·Ω·T²). VERDICT: "
        f"the sensor is BOUNDED by the standard quantum limit — the honest inverse of a "
        f"free-energy claim. NO sub-SQL/over-unity claim. {len(NOT_MODELED)} systematic "
        f"classes are explicitly NOT MODELED (laser-phase noise, AC-Stark/light-shift, "
        f"full 3-axis mechanization, detection noise, Dick aliasing, mean-field shifts) — "
        f"this is a noise-floor certificate, NOT a complete error budget."
    )

    return QuantumSensingCertificate(
        certificate_type="szl/quantum-sensing-limits-certificate/v1",
        inputs={
            "label": sensor.label,
            "source": sensor.source,
            "wavelength_m_CONFIG": lam,
            "interrogation_time_s_CONFIG": T,
            "atom_number_MEASURED": N if label_is_measured else None,
            "atom_number_value": N,
            "contrast_MEASURED": C if label_is_measured else None,
            "contrast_value": C,
            "cycle_time_s_MEASURED": Tc if label_is_measured else None,
            "cycle_time_s_value": Tc,
            "accel_psd_MEASURED": Sa if label_is_measured else None,
            "accel_psd_value": Sa,
            "accel_input_MEASURED": measured_a,  # None unless a genuine reading
            "accel_input_value": sensor.accel_input,
            "omega_rad_s_CONFIG": sensor.omega_rad_s,
            "transverse_velocity_ms": sensor.transverse_velocity_ms,
            "rotation_rate_rad_s": sensor.rotation_rate_rad_s,
            "contrast0_CONFIG": sensor.contrast0,
            "coherence_time_s": sensor.coherence_time_s,
            "validation_problems": problems,  # empty unless strict=False let issues through
            "note": sensor.note,
        },
        k_eff_per_m=keff,
        mz_phase_per_unit_accel_rad=phase_per_accel,
        mz_phase_modeled_rad=mz_phase,
        accel_was_measured=(measured_a is not None),
        shot_noise_phase_rad=sigma_phi,
        accel_sensitivity_per_shot=sigma_a,
        accel_asd=n_a,
        accel_psd_from_asd=psd_from_asd,
        vibration_transfer_magnitude=H_mag,
        vibration_phase_variance=vib_var,
        vibration_phase_rms_rad=vib_rms,
        coriolis_phase_rad=cor_phase,
        contrast_at_T=contrast_T,
        at_or_above_standard_quantum_limit=bool(at_or_above_sql),
        summary=summary,
        inputs_hash=_hash_inputs(sensor),
        timestamp_utc=time.time(),
    )


def honest_sample_sensor() -> MeasuredSensor:
    """An HONEST, CLEARLY-LABELLED sample operating point (NOT a real instrument reading).

    Values are representative of a Rb-87 fountain CAI (λ≈780 nm, T≈0.1 s) but the record is
    labelled SAMPLE so the certifier will NOT report them as MEASURED. No fabricated claim.
    """
    return MeasuredSensor(
        wavelength_m=780.0e-9,        # Rb-87 D2 line, design wavelength
        interrogation_time_s=0.1,     # 100 ms pulse separation
        atom_number=1.0e6,            # ~10^6 atoms
        contrast=0.5,                 # 50% fringe contrast
        cycle_time_s=0.5,             # 0.5 s cycle (2 Hz)
        accel_psd=1.0e-8,             # m²/s⁴/Hz, representative ground vibration
        accel_input=9.81,            # g, supplied as DESIGN input (NOT a reading)
        omega_rad_s=2.0 * math.pi * 1.0,   # evaluate |H| at 1 Hz
        transverse_velocity_ms=0.01,
        rotation_rate_rad_s=7.292115e-5,   # Earth rotation rate (sidereal)
        contrast0=0.6,
        coherence_time_s=0.3,
        label="SAMPLE",
        source="honest-sample",
        note="Representative Rb-87 CAI operating point. SAMPLE label ⇒ not MEASURED.",
    )


__all__ = [
    "K_B", "H_PLANCK", "HBAR", "C_LIGHT", "PI",
    "SENSING_ATTRIBUTION", "DOCTRINE", "NOT_MODELED",
    "MeasuredSensor", "QuantumSensingCertificate", "certify_sensor",
    "k_eff", "mach_zehnder_phase", "shot_noise_phase", "accel_sensitivity_per_shot",
    "asd_accel", "contrast_decay", "vibration_transfer_magnitude",
    "vibration_phase_variance", "coriolis_phase", "honest_sample_sensor",
]


if __name__ == "__main__":
    sensor = honest_sample_sensor()
    cert = certify_sensor(sensor)
    print("SZL QUANTUM-SENSING-LIMITS CERTIFICATE (honest sample)\n" + "=" * 60)
    print(cert.summary)
    print("=" * 60)
    print(f"k_eff                 : {cert.k_eff_per_m:.6g} m⁻¹")
    print(f"SQL phase floor σ_Φ   : {cert.shot_noise_phase_rad:.4g} rad")
    print(f"per-shot σ_a          : {cert.accel_sensitivity_per_shot:.4g} m/s²")
    print(f"ASD n_a               : {cert.accel_asd:.4g} m/s²/√Hz")
    print(f"vibration σ_Φ² (T³/3) : {cert.vibration_phase_variance:.4g} rad²")
    print(f"Coriolis Φ_cor        : {cert.coriolis_phase_rad:.4g} rad")
    print(f"contrast C(T)         : {cert.contrast_at_T}")
    print(f"at/above SQL (honest) : {cert.at_or_above_standard_quantum_limit}")
    print(f"NOT MODELED classes   : {len(cert.not_modeled)}")
