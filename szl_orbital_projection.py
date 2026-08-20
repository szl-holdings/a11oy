#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED · Λ = Conjecture 1 · sovereign=false on this path
"""szl_orbital_projection.py — SZL Orbital Compute Tier: MODELED energy projection.

ROADMAP / MODELED ONLY. Extends the honest ground-energy story to orbit: a MODELED
joules + thermal figure for a MODELED orbital node, computed FROM the REAL MEASURED
ground J/token coefficient (pulled in-process from the live energy operator). The
ground coefficient is MEASURED; the orbital figure derived from it is MODELED, and
the payload cites the MEASURED ground source so the two are never confused.

DOCTRINE v11 (this surface multiplies a real number into a roadmap — be ruthless):
  - The ONLY MEASURED input is the ground J/token coefficient (measured_token_joules
    / measured_tokens) read from the live operator status. It is labeled MEASURED and
    its source (the ground exporter node) is cited in the payload.
  - EVERYTHING orbital is MODELED: the orbital node is a MODELED node (modeled:true /
    reachable:false — no on-orbit hardware), the workload token count is a MODELED
    assumption, and the resulting orbital joules/thermal are MODELED. A MODELED
    orbital joule is NEVER labeled MEASURED.
  - The orbital overhead factor (extra joules for a watt in space vs on the ground:
    radiation hardening, thermal management margin, comms) is an explicit MODELED
    ASSUMPTION with its value shown so the number is re-derivable. It is not measured.
  - If the live operator has no MEASURED tokens yet, fall back to the documented
    ground-truth coefficient sample and SAY SO via measured_source — never fabricate
    a measured coefficient, and never present the fallback as a live reading.
  - "no on-orbit hardware" is stated in the payload so the demo is honest at a glance.

Coefficient source (in-process, no network), mirroring szl_energy_projection.py:
  - szl_energy_operator.handle_status() → measured_token_joules, measured_tokens,
    exporter_node. J/token = measured_token_joules / measured_tokens (MEASURED).

Endpoint (existing dual-register pattern — handler functions + FastAPI register()):
  GET /api/a11oy/v1/orbital/projection?tokens=<int>
    Returns the MODELED orbital joules/thermal for a MODELED node, derived from the
    MEASURED ground J/token coefficient (cited), every value labeled.
"""
from __future__ import annotations

import datetime
import importlib
import os
from typing import Any, Mapping, Optional

# ---------------------------------------------------------------------------
# Honesty labels (doctrine v11). Tests grep these exact strings. A derived
# orbital joule must NEVER carry MEASURED — only the ground coefficient does.
# ---------------------------------------------------------------------------
MEASURED = "MEASURED"     # the ground J/token coefficient ONLY
MODELED = "MODELED"       # everything orbital derived from it
ESTIMATE = "ESTIMATE"     # an assumed (non-measured) input (overhead factor, token count)
DATA_KIND = "MODELED-roadmap"
ROADMAP = "ROADMAP"
NO_HARDWARE_NOTE = (
    "MODELED orbital roadmap — no on-orbit hardware. The J/token coefficient is "
    "MEASURED on the REAL ground GPU fabric; the orbital joules/thermal below are "
    "MODELED (ground coefficient × MODELED workload × MODELED space-overhead factor)."
)

JOULES_PER_KWH = 3_600_000.0

# MODELED space-overhead factor: extra joules per ground-joule for operating compute
# in orbit (radiation-hardened parts efficiency loss + active thermal management margin
# + comms overhead). An ESTIMATE input — value shown, swap a real bus power budget to
# make it true. NOT measured. Default 1.6 (≈60% overhead) is a conservative roadmap
# placeholder, overridable via env.
ORBITAL_OVERHEAD_FACTOR = float(os.environ.get("ORBITAL_OVERHEAD_FACTOR", "1.6"))

# MODELED default workload size (tokens for one MODELED orbital inference job). An
# ESTIMATE input — the demo's "one job in orbit" size. Overridable per request.
DEFAULT_ORBITAL_TOKENS = float(os.environ.get("ORBITAL_TOKENS", "100000"))

# Thermal: in steady state essentially all electrical joules become heat that the
# spacecraft must reject. We MODEL thermal_joules == orbital_joules (a 1:1 heat-load
# MODEL, stated as such) — a roadmap placeholder, not a measured radiator figure.
THERMAL_HEAT_FRACTION = 1.0

# Documented ground-truth J/token fallback (used ONLY when the live operator has no
# MEASURED tokens yet). Derived from the BUILD_SPEC ground sample; labeled as a
# fallback via measured_source, NEVER presented as a live reading. The numbers below
# are the documented MEASURED ground sample, not a fabricated value.
_GROUND_TRUTH_JOULES = 78_369.586
_GROUND_TRUTH_TOKENS = float(os.environ.get("GROUND_TRUTH_TOKENS", "120000"))
_GROUND_TRUTH_NODE = "betterwithage"


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _coerce_float(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if f != f or f in (float("inf"), float("-inf")):
        return None
    return f


def _try_operator_status() -> Optional[Mapping[str, Any]]:
    """Best-effort in-process call to the live operator status handler. None if absent."""
    for modname, fn in (
        ("szl_energy_operator", "handle_status"),
        ("szl_energy_operator", "operator_status"),
        ("a11oy_energy_operator", "handle_status"),
    ):
        try:
            mod = importlib.import_module(modname)
        except Exception:
            continue
        handler = getattr(mod, fn, None)
        if callable(handler):
            try:
                out = handler()
                if isinstance(out, Mapping):
                    return out
            except Exception:
                continue
    return None


def _ground_coefficient(op: Optional[Mapping[str, Any]]) -> dict:
    """Extract the REAL MEASURED ground J/token coefficient from the live operator.

    Returns the MEASURED coefficient (joules per token) and its source. Falls back to
    the documented ground sample ONLY when no MEASURED tokens exist live — labeled via
    ``measured_source`` so the fallback is never silently presented as a live reading.
    """
    if op is not None:
        m_joules = _coerce_float(op.get("measured_token_joules"))
        m_tokens = _coerce_float(op.get("measured_tokens"))
        node = op.get("exporter_node") or op.get("node")
        if m_joules is not None and m_tokens is not None and m_tokens > 0 and m_joules > 0:
            return {
                "measured_source": "live:operator (measured jobs)",
                "j_per_token": m_joules / m_tokens,
                "ground_joules_measured": m_joules,
                "ground_tokens_measured": m_tokens,
                "ground_node": node or _GROUND_TRUTH_NODE,
                "is_live": True,
            }

    # Documented ground-truth fallback (labeled, never silent).
    return {
        "measured_source": "fallback:ground-truth-sample (BUILD_SPEC 2026-06-14 13:26 EDT)",
        "j_per_token": _GROUND_TRUTH_JOULES / _GROUND_TRUTH_TOKENS,
        "ground_joules_measured": _GROUND_TRUTH_JOULES,
        "ground_tokens_measured": _GROUND_TRUTH_TOKENS,
        "ground_node": _GROUND_TRUTH_NODE,
        "is_live": False,
    }


def _labeled(value, label, formula=None, **extra):
    d = {"value": value, "label": label}
    if formula is not None:
        d["formula"] = formula
    d.update(extra)
    return d


def build_projection(tokens: float = DEFAULT_ORBITAL_TOKENS,
                     overhead_factor: float = ORBITAL_OVERHEAD_FACTOR,
                     _op: Optional[Mapping[str, Any]] = None) -> dict:
    """Build the MODELED orbital energy projection from the MEASURED ground coefficient.

    ``_op`` lets tests inject an exact operator status; otherwise we read it live.
    """
    op = _op if _op is not None else _try_operator_status()
    coeff = _ground_coefficient(op)
    j_per_token = float(coeff["j_per_token"])

    tokens = float(tokens) if tokens and float(tokens) > 0 else DEFAULT_ORBITAL_TOKENS
    overhead = float(overhead_factor) if overhead_factor and float(overhead_factor) > 0 else ORBITAL_OVERHEAD_FACTOR

    # --- MODELED orbital energy: ground J/token × MODELED tokens × MODELED overhead ---
    ground_joules_for_workload = j_per_token * tokens          # MODELED (ground-equiv)
    orbital_joules = ground_joules_for_workload * overhead     # MODELED (in orbit)
    orbital_thermal_joules = orbital_joules * THERMAL_HEAT_FRACTION  # MODELED heat load
    orbital_kwh = orbital_joules / JOULES_PER_KWH              # MODELED

    return {
        "ok": True,
        "endpoint": "orbital/projection",
        "data_kind": DATA_KIND,
        "status": ROADMAP,
        "on_orbit_hardware": False,
        "label": MODELED,
        "doctrine": (
            "v11: the J/token coefficient is MEASURED on the REAL ground GPU fabric "
            "(source cited). The orbital joules/thermal are MODELED — ground "
            "coefficient × MODELED workload × MODELED space-overhead factor — for a "
            "MODELED orbital node (modeled:true / reachable:false, no on-orbit "
            "hardware). A MODELED orbital joule is NEVER MEASURED. Λ = Conjecture 1; "
            "sovereign=false."
        ),
        # The single MEASURED input, with its ground source cited.
        "ground_measured_coefficient": {
            "label": MEASURED,
            "measured_source": coeff["measured_source"],
            "ground_node": coeff["ground_node"],
            "is_live_measurement": coeff["is_live"],
            "j_per_token": _labeled(
                round(j_per_token, 9), MEASURED,
                formula="measured_token_joules ÷ measured_tokens (from the live energy operator)",
                note="REAL ground-measured joules-per-token; the only MEASURED value here"),
            "ground_joules_measured": _labeled(
                round(float(coeff["ground_joules_measured"]), 6), MEASURED,
                note="MEASURED joules over the measured-token jobs on the ground fabric"),
            "ground_tokens_measured": _labeled(
                round(float(coeff["ground_tokens_measured"]), 3), MEASURED),
        },
        # The MODELED orbital node this projection is for (no on-orbit hardware).
        "orbital_node": {
            "id": "leo-edge-00",
            "tier": "LEO-edge",
            "modeled": True,
            "reachable": False,
            "data_kind": DATA_KIND,
            "note": "MODELED orbital node — not reachable, no on-orbit hardware",
        },
        "modeled_assumptions": {
            "workload_tokens": _labeled(
                tokens, ESTIMATE,
                note="MODELED workload size for one orbital inference job (assumed, not measured)"),
            "space_overhead_factor": _labeled(
                overhead, ESTIMATE,
                formula="orbital_joules ÷ ground_equivalent_joules",
                note=("MODELED extra-joules-per-ground-joule in orbit (rad-hard efficiency "
                      "loss + thermal margin + comms). ASSUMED — swap a real bus power "
                      "budget to make it true.")),
            "thermal_heat_fraction": _labeled(
                THERMAL_HEAT_FRACTION, ESTIMATE,
                note="MODELED 1:1 steady-state electrical→heat load (roadmap placeholder)"),
        },
        "orbital_projection": {
            "label": MODELED,
            "basis": "MEASURED ground J/token × MODELED tokens × MODELED space-overhead",
            "ground_equivalent_joules": _labeled(
                round(ground_joules_for_workload, 6), MODELED,
                formula="j_per_token (MEASURED) × workload_tokens (MODELED)",
                note="what the same workload would cost on the ground — MODELED from a measured rate"),
            "orbital_joules": _labeled(
                round(orbital_joules, 6), MODELED,
                formula="ground_equivalent_joules × space_overhead_factor",
                note="MODELED in-orbit energy — NEVER a measured orbital reading (no hardware)"),
            "orbital_thermal_joules": _labeled(
                round(orbital_thermal_joules, 6), MODELED,
                formula="orbital_joules × thermal_heat_fraction",
                note="MODELED heat the MODELED spacecraft must reject"),
            "orbital_kwh": _labeled(
                round(orbital_kwh, 9), MODELED,
                formula="orbital_joules ÷ 3.6e6"),
        },
        "honesty": {
            "sovereign": False,
            "lambda": "Conjecture 1",
            "on_orbit_hardware": False,
            "measured_label": MEASURED,
            "measured_is": "the ground J/token coefficient ONLY (source cited)",
            "modeled_label": MODELED,
            "modeled_is": "all orbital joules/thermal — derived from the measured ground rate",
            "note": NO_HARDWARE_NOTE,
        },
        "timestamp_utc": _now_iso(),
    }


def handle_projection(tokens: float = DEFAULT_ORBITAL_TOKENS) -> dict:
    """GET /orbital/projection?tokens=<int> — handler used by FastAPI and __main__."""
    try:
        return build_projection(tokens=tokens)
    except Exception as exc:  # never 500: honest degraded response
        return {
            "ok": False,
            "endpoint": "orbital/projection",
            "data_kind": DATA_KIND,
            "error": str(exc),
            "doctrine": "v11: orbital projection unavailable; no fabricated orbital joule emitted.",
            "timestamp_utc": _now_iso(),
        }


# ---------------------------------------------------------------------------
# FastAPI router registration — mirrors szl_energy_projection.register() exactly.
# ---------------------------------------------------------------------------

def register(app, ns: str = "a11oy") -> str:
    """Mount the orbital projection endpoint on the FastAPI ``app``. Returns a status string."""
    from fastapi.responses import JSONResponse

    base = f"/api/{ns}/v1/orbital"

    @app.get(f"{base}/projection")
    async def _orbital_projection(tokens: float = DEFAULT_ORBITAL_TOKENS):
        """MODELED orbital joules/thermal from the MEASURED ground J/token coefficient (cited)."""
        return JSONResponse(handle_projection(tokens=tokens))

    return "orbital-projection-wired:1"


# ---------------------------------------------------------------------------
# Self-test — verifies the coefficient is MEASURED, orbital values are MODELED,
# the math re-derives, and no orbital joule is ever labeled MEASURED.
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json as _json
    import sys as _sys

    print("=" * 72)
    print("szl_orbital_projection — self-test (MEASURED ground coeff → MODELED orbit)")
    print("=" * 72)

    # Inject an exact operator status so the projection is deterministic.
    op = {
        "running": True,
        "measured_token_joules": 600.0,
        "measured_tokens": 1000.0,        # → 0.6 J/token MEASURED
        "exporter_node": "betterwithage",
    }
    proj = build_projection(tokens=1000.0, overhead_factor=1.5, _op=op)

    # 1) the ground coefficient is MEASURED and equals numerator/denominator
    coeff = proj["ground_measured_coefficient"]
    assert coeff["label"] == MEASURED
    assert abs(coeff["j_per_token"]["value"] - 0.6) < 1e-9, coeff["j_per_token"]
    assert coeff["is_live_measurement"] is True
    print(f"[1] ground J/token={coeff['j_per_token']['value']} label={coeff['label']} (live)  OK")

    # 2) orbital joules = ground_equiv × overhead, all MODELED
    op_proj = proj["orbital_projection"]
    ground_equiv = op_proj["ground_equivalent_joules"]["value"]
    orbital_j = op_proj["orbital_joules"]["value"]
    assert abs(ground_equiv - 0.6 * 1000.0) < 1e-6, ground_equiv      # 600 J ground-equiv
    assert abs(orbital_j - 600.0 * 1.5) < 1e-6, orbital_j             # 900 J in orbit
    assert op_proj["orbital_joules"]["label"] == MODELED
    assert op_proj["ground_equivalent_joules"]["label"] == MODELED
    assert op_proj["orbital_thermal_joules"]["label"] == MODELED
    print(f"[2] ground_equiv={ground_equiv}J → orbital={orbital_j}J (×1.5), all MODELED  OK")

    # 3) the orbital node is modeled:true / reachable:false
    node = proj["orbital_node"]
    assert node["modeled"] is True and node["reachable"] is False, node
    assert proj["on_orbit_hardware"] is False
    print("[3] orbital_node modeled:true reachable:false, on_orbit_hardware=False  OK")

    # 4) NO orbital VALUE may carry a MEASURED label (the "label" field specifically;
    #    formula strings may legitimately *reference* the MEASURED ground input).
    def _labels(obj):
        if isinstance(obj, dict):
            if "label" in obj and not isinstance(obj["label"], (dict, list)):
                yield obj["label"]
            for v in obj.values():
                yield from _labels(v)
        elif isinstance(obj, list):
            for v in obj:
                yield from _labels(v)
    for blk in ("orbital_projection", "modeled_assumptions"):
        for lab in _labels(proj[blk]):
            assert lab != MEASURED, f"DOCTRINE VIOLATION: '{MEASURED}' label in {blk}"
    print(f"[4] no value carries a '{MEASURED}' label inside the MODELED orbital block  OK")

    # 5) honest no-hardware note present
    assert "no on-orbit hardware" in _json.dumps(proj), "no-hardware note missing"
    print("[5] 'no on-orbit hardware' stated in payload  OK")

    # 6) fallback path (no measured tokens) is labeled as a fallback, still MODELED orbit
    fb = build_projection(tokens=1000.0, _op={"running": False})
    assert fb["ground_measured_coefficient"]["is_live_measurement"] is False
    assert "fallback" in fb["ground_measured_coefficient"]["measured_source"]
    assert fb["orbital_projection"]["orbital_joules"]["label"] == MODELED
    print(f"[6] no-measured-tokens → labeled fallback source, orbit still MODELED  OK")

    print("\n--- example orbital projection ---")
    print(_json.dumps(proj["orbital_projection"], indent=2))
    print("\nok:true checks:6")
    _sys.exit(0)
