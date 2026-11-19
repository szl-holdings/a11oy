#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 SZL Holdings — research only, no execution authority.
"""Small, explicit radical-pair spin model for flavin-inspired research.

Taxonomy: services/research. This is NOT a calibrated flavin molecule,
an experimental observation, or a qubit demonstration. No inference,
training, device access, or receipt signing happens on GET.

Basis: two spin-1/2 electrons + one spin-1/2 nucleus (Hilbert dimension 8).
Hamiltonian (angular radians per microsecond; hbar = 1):
  H = gamma_e B (S1 + S2).n + 2*pi*sum_i A_i S1_i I_i
      + 2*pi*J (S1 dot S2)
Singlet/triplet selective loss is the Haberkorn anticommutator.
We Trotter-split the coherent, reaction, singlet-triplet dephasing
and local bit-flip channels to retain positive semidefinite rho and
explicit product probabilities. Both noise channels are PHENOMENOLOGICAL.

Primary background:
  Sirenko & Bartolome, Low Temp. Phys. 52, 760-783 (2026).
  DOI:10.1063/10.0044249 (accessible abstract/figure previews only).
Methods:
  RadicalPy, JCTC 20, 9488 (2024). DOI:10.1021/acs.jctc.4c00887.
  Flavin biradical spin-chemistry, PMC11652833.
These citations are prior art, not numerical parameter validation.
"""
import hashlib
import json
import math
from typing import Any

try:
    import numpy as np
except ImportError:
    np = None

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

SCHEMA = "szl.flavin-radical-pair-research/v1"
ELECTRON_GAMMA_MHZ_PER_UT = 0.02802495164  # |gamma_e|/(2*pi), MHz per microtesla
SOURCE_REVIEW = "https://doi.org/10.1063/10.0044249"
SOURCE_METHOD = "https://doi.org/10.1021/acs.jctc.4c00887"
SOURCE_FLAVIN = "https://pmc.ncbi.nlm.nih.gov/articles/PMC11652833/"
SOURCE_SENSOR = "https://doi.org/10.1038/s41586-025-09971-3"
MAX_TOTAL_STEPS = 6000
MAX_ANGLES = 7
MAX_STEP_COUNT = 1200
CLAIM_BOUNDARY = (
    "Numerical toy model; no measured flavin rates, no fitted hyperfine tensor, "
    "no temperature dependence, no observed quantum coherence, no biological "
    "sensor qualification, no quantum advantage and no action authority."
)


class InputHold(ValueError):
    """Stable input/research limitation code, no source paths."""


def _real(value: Any, key: str, lo: float, hi: float) -> float:
    if type(value) not in (float, int) or not math.isfinite(value):
        raise InputHold("NONFINITE_OR_NONTYPED_" + key.upper())
    if not lo <= value <= hi:
        raise InputHold("OUT_OF_RANGE_" + key.upper())
    return float(value)


def _angles(value: Any) -> tuple[float, ...]:
    if isinstance(value, str):
        items = value.split(",")
        if not 1 <= len(items) <= MAX_ANGLES:
            raise InputHold("ANGLE_COUNT_EXCEEDS_BUDGET")
        if any(not item.strip() for item in items):
            raise InputHold("ANGLE_FORMAT_INVALID")
        try:
            return tuple(_real(float(item), "angle_deg", 0.0, 180.0)
                         for item in items)
        except (ValueError, OverflowError):
            raise InputHold("ANGLE_FORMAT_INVALID") from None
    if type(value) not in (list, tuple) or not 1 <= len(value) <= MAX_ANGLES:
        raise InputHold("ANGLE_COUNT_EXCEEDS_BUDGET")
    return tuple(_real(item, "angle_deg", 0.0, 180.0) for item in value)


def _spin_operators():
    if np is None:
        raise InputHold("NUMPY_UNAVAILABLE")
    eye = np.eye(2, dtype=complex)
    pauli = (
        np.array([[0, 1], [1, 0]], dtype=complex),
        np.array([[0, -1j], [1j, 0]], dtype=complex),
        np.array([[1, 0], [0, -1]], dtype=complex),
    )

    def at(axis: int, position: int):
        factors = [eye, eye, eye]
        factors[position] = pauli[axis] / 2
        return np.kron(np.kron(factors[0], factors[1]), factors[2])

    s1 = tuple(at(i, 0) for i in range(3))
    s2 = tuple(at(i, 1) for i in range(3))
    nucleus = tuple(at(i, 2) for i in range(3))
    full = np.eye(8, dtype=complex)
    ps = full / 4 - sum((a @ b for a, b in zip(s1, s2)),
                         np.zeros((8, 8), dtype=complex))
    pt = full - ps
    x1, x2 = 2 * s1[0], 2 * s2[0]
    return s1, s2, nucleus, ps, pt, x1, x2, full


def _one_angle(*, B_uT: float, angle_deg: float, hyperfine_xy_MHz: float,
               hyperfine_z_MHz: float, exchange_MHz: float,
               k_s_per_us: float, k_t_per_us: float,
               gamma_st_per_us: float, gamma_flip_per_us: float,
               dt_us: float, steps: int, ops) -> dict[str, float]:
    s1, s2, nucleus, ps, pt, x1, x2, eye = ops
    theta = math.radians(angle_deg)
    zeeman = 2 * math.pi * ELECTRON_GAMMA_MHZ_PER_UT * B_uT * (
        math.sin(theta) * (s1[0] + s2[0])
        + math.cos(theta) * (s1[2] + s2[2])
    )
    hyperfine = (2 * math.pi) * (
        hyperfine_xy_MHz * (s1[0] @ nucleus[0] + s1[1] @ nucleus[1])
        + hyperfine_z_MHz * (s1[2] @ nucleus[2])
    )
    exchange = 2 * math.pi * exchange_MHz * sum(
        (left @ right for left, right in zip(s1, s2)),
        np.zeros((8, 8), dtype=complex),
    )
    h = zeeman + hyperfine + exchange
    # A coarse time step cannot be treated as converged numerical physics.
    if dt_us * float(np.max(np.abs(np.linalg.eigvalsh(h)))) > 0.4:
        raise InputHold("TIME_STEP_COARSE_FOR_HAMILTONIAN")
    eigenvalues, vectors = np.linalg.eigh(h)
    half = (vectors * np.exp(-0.5j * dt_us * eigenvalues)) @ vectors.conj().T
    half_dag = half.conj().T
    loss_s = -math.expm1(-k_s_per_us * dt_us)
    loss_t = -math.expm1(-k_t_per_us * dt_us)
    decay = (math.exp(-k_s_per_us * dt_us / 2) * ps
             + math.exp(-k_t_per_us * dt_us / 2) * pt)
    coherence_survival = math.exp(-gamma_st_per_us * dt_us)
    # Lindbladian gamma_flip (X rho X - rho) => p=(1-exp(-2 gamma dt))/2.
    flip_probability = -math.expm1(-2 * gamma_flip_per_us * dt_us) / 2
    rho = ps / 2  # nuclear spin maximally mixed, electron singlet
    singlet = triplet = 0.0
    for _ in range(steps):
        rho = half @ rho @ half_dag
        singlet += loss_s * float(np.trace(ps @ rho).real)
        triplet += loss_t * float(np.trace(pt @ rho).real)
        rho = decay @ rho @ decay
        # Projective S/T channel suppresses OFF-DIAGONAL coherence only.
        rho = (coherence_survival * rho
               + (1 - coherence_survival) * (ps @ rho @ ps + pt @ rho @ pt))
        if flip_probability:
            rho = (1 - flip_probability) * rho + flip_probability * (x1 @ rho @ x1)
            rho = (1 - flip_probability) * rho + flip_probability * (x2 @ rho @ x2)
        rho = half @ rho @ half_dag
    surviving = float(np.trace(rho).real)
    minimum_eigenvalue = float(np.min(np.linalg.eigvalsh((rho + rho.conj().T) / 2)))
    residual = singlet + triplet + surviving - 1
    if (not all(math.isfinite(x) for x in
                (singlet, triplet, surviving, residual, minimum_eigenvalue))
            or minimum_eigenvalue < -1e-9
            or min(singlet, triplet, surviving) < -1e-9
            or abs(residual) > 1e-8):
        raise InputHold("MODEL_CONSERVATION_FAILURE")
    return {
        "angle_deg": angle_deg,
        "singlet_product_probability": singlet,
        "triplet_product_probability": triplet,
        "surviving_pair_probability": surviving,
        "probability_mass_residual": residual,
        "minimum_surviving_density_eigenvalue": minimum_eigenvalue,
    }


def simulate(*, B_uT=50.0, angles_deg=(0.0, 45.0, 90.0),
             hyperfine_xy_MHz=0.25, hyperfine_z_MHz=1.25,
             exchange_MHz=0.0, k_s_per_us=1.0, k_t_per_us=1.0,
             gamma_st_per_us=0.2, gamma_flip_per_us=0.0,
             dt_us=0.02, steps=500) -> dict[str, Any]:
    """Deterministic 8x8 spin-chemistry sweep, not an experimental prediction."""
    B_uT = _real(B_uT, "b_ut", 0, 100)
    angles_deg = _angles(angles_deg)
    hyperfine_xy_MHz = _real(hyperfine_xy_MHz, "hyperfine_xy_mhz", 0, 5)
    hyperfine_z_MHz = _real(hyperfine_z_MHz, "hyperfine_z_mhz", 0, 5)
    exchange_MHz = _real(exchange_MHz, "exchange_mhz", -2, 2)
    k_s_per_us = _real(k_s_per_us, "k_s_per_us", 0.05, 20)
    k_t_per_us = _real(k_t_per_us, "k_t_per_us", 0.05, 20)
    gamma_st_per_us = _real(gamma_st_per_us, "gamma_st_per_us", 0, 20)
    gamma_flip_per_us = _real(gamma_flip_per_us, "gamma_flip_per_us", 0, 20)
    dt_us = _real(dt_us, "dt_us", 0.0005, 0.05)
    if type(steps) is not int or not 20 <= steps <= MAX_STEP_COUNT:
        raise InputHold("STEP_COUNT_OUT_OF_RANGE")
    if steps * len(angles_deg) > MAX_TOTAL_STEPS:
        raise InputHold("COMPUTE_BUDGET_EXCEEDED")
    if dt_us * max(k_s_per_us, k_t_per_us,
                   gamma_st_per_us, gamma_flip_per_us) > 0.25:
        raise InputHold("TIME_STEP_COARSE_FOR_RATES")
    if np is None:
        raise InputHold("NUMPY_UNAVAILABLE")
    ops = _spin_operators()
    observations = [
        _one_angle(
            B_uT=B_uT, angle_deg=angle, hyperfine_xy_MHz=hyperfine_xy_MHz,
            hyperfine_z_MHz=hyperfine_z_MHz, exchange_MHz=exchange_MHz,
            k_s_per_us=k_s_per_us, k_t_per_us=k_t_per_us,
            gamma_st_per_us=gamma_st_per_us, gamma_flip_per_us=gamma_flip_per_us,
            dt_us=dt_us, steps=steps, ops=ops,
        )
        for angle in angles_deg
    ]
    probabilities = [row["singlet_product_probability"] for row in observations]
    freq = ELECTRON_GAMMA_MHZ_PER_UT * B_uT
    output = {
        "schema": SCHEMA,
        "state": "MODELED",
        "verification_scope": "NUMERICAL_INVARIANTS_ONLY",
        "claims_verified": False,
        "execution_authorized": False,
        "model_class": "2_electron_1_nuclear_spin_axial_hyperfine_Haberkorn",
        "mechanisms": [
            "anisotropic electron-nuclear hyperfine + Zeeman + optional exchange",
            "spin-selective first-order recombination to explicit product sinks",
            "phenomenological singlet-triplet dephasing",
            "phenomenological local electron bit-flip noise",
        ],
        "inputs": {
            "B_uT": B_uT, "angles_deg": list(angles_deg),
            "hyperfine_xy_MHz": hyperfine_xy_MHz,
            "hyperfine_z_MHz": hyperfine_z_MHz,
            "exchange_MHz": exchange_MHz,
            "k_s_per_us": k_s_per_us, "k_t_per_us": k_t_per_us,
            "gamma_st_per_us": gamma_st_per_us,
            "gamma_flip_per_us": gamma_flip_per_us,
            "dt_us": dt_us, "steps": steps,
            "time_window_us": dt_us * steps,
            "parameter_origin": "ILLUSTRATIVE_NOT_EXPERIMENTALLY_FITTED",
        },
        "earth_field_electron_larmor_period_ns":
            1000.0 / freq if freq > 0 else None,
        "singlet_yield_angular_contrast": max(probabilities) - min(probabilities),
        "results": observations,
        "conservation_max_absolute_residual": max(
            abs(row["probability_mass_residual"]) for row in observations
        ),
        "boundaries": CLAIM_BOUNDARY,
        "sources": {
            "review": SOURCE_REVIEW,
            "simulation_prior_art": SOURCE_METHOD,
            "flavin_spin_physics": SOURCE_FLAVIN,
            "in_cell_biosensors": SOURCE_SENSOR,
        },
    }
    # Deterministic content hash, NOT a signature, signed receipt or live proof.
    encoded = json.dumps(output, sort_keys=True, ensure_ascii=False,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
    output["digest_sha256"] = hashlib.sha256(encoded).hexdigest()
    output["digest_semantics"] = "UNSIGNED_CONTENT_HASH_ONLY"
    return output


def _parse_query(request):
    params = request.query_params
    # Bounds prevent oversized public query strings from consuming unbounded
    # parsing time or building excess allocation in the ASGI worker pool.
    if len(request.scope.get("query_string", b"")) > 512:
        raise InputHold("QUERY_TOO_LARGE")
    supported = {
        "B_uT", "angles", "hyperfine_xy_MHz", "hyperfine_z_MHz",
        "exchange_MHz", "k_s_per_us", "k_t_per_us",
        "gamma_st_per_us", "gamma_flip_per_us", "dt_us", "steps",
    }
    if set(params) - supported:
        raise InputHold("UNKNOWN_INPUT_PARAMETER")
    if any(len(params.getlist(key)) != 1 for key in params):
        raise InputHold("DUPLICATE_INPUT_PARAMETER")

    def n(name: str, default: float) -> float:
        raw = params.get(name)
        if raw is None:
            return default
        try:
            return float(raw)
        except (ValueError, OverflowError):
            raise InputHold("INPUT_NOT_NUMERIC_" + name.upper()) from None

    raw_steps = params.get("steps")
    if raw_steps is None:
        steps = 500
    elif len(raw_steps) > 4 or not raw_steps.isascii() or not raw_steps.isdigit():
        raise InputHold("STEP_COUNT_NOT_INTEGER")
    else:
        steps = int(raw_steps)
    return {
        "B_uT": n("B_uT", 50.0),
        "angles_deg": params.get("angles", "0,45,90"),
        "hyperfine_xy_MHz": n("hyperfine_xy_MHz", 0.25),
        "hyperfine_z_MHz": n("hyperfine_z_MHz", 1.25),
        "exchange_MHz": n("exchange_MHz", 0.0),
        "k_s_per_us": n("k_s_per_us", 1.0),
        "k_t_per_us": n("k_t_per_us", 1.0),
        "gamma_st_per_us": n("gamma_st_per_us", 0.2),
        "gamma_flip_per_us": n("gamma_flip_per_us", 0.0),
        "dt_us": n("dt_us", 0.02),
        "steps": steps,
    }


def _handler(request: Request):
    try:
        result = simulate(**_parse_query(request))
    except InputHold as exc:
        reason = str(exc)
        return JSONResponse(
            {"schema": SCHEMA, "state": "UNAVAILABLE", "reason": reason,
             "execution_authorized": False},
            status_code=503 if reason == "NUMPY_UNAVAILABLE" else 422,
            headers={"Cache-Control": "no-store"},
        )
    return JSONResponse(
        result, headers={"Cache-Control": "no-store"},
    )


def register(app, *, ns="a11oy") -> str:
    path = f"/api/{ns}/v1/qbio/flavin-spin-research"
    register_route = getattr(app, "add_api_route", None)
    if callable(register_route):
        register_route(path, _handler, methods=["GET"], include_in_schema=True)
    else:
        app.router.routes.append(Route(path, _handler, methods=["GET"]))
    return path
