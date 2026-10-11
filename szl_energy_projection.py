#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED · Λ = Conjecture 1 · sovereign=false on this path
"""szl_energy_projection.py — SZL Energy: honest 1-day + scale projection engine.

Dev 3 (backend). Projects only from an explicitly verified, current, aligned
operator energy window. Ledger lifetime totals and historical samples are not
substitutes for a live rate.

DOCTRINE v11 (this module is the one most at risk of dishonest numbers — be ruthless):
  - The MEASURED inputs are the live joules/tokens/jobs and the window seconds. Those
    are MEASURED and only MEASURED. Anything we multiply forward in time is a
    PROJECTION and is labeled MODELED.
  - A PROJECTED DOLLAR IS NEVER "MEASURED". The compute-resale line is the big number
    and it is an ESTIMATE built on a clearly-labeled ESTIMATE input (45¢/kWh resale).
    The grid-arbitrage credit is tiny and derived from MEASURED joules × grid price,
    but the forward-extrapolated dollar is still MODELED (a projection of a measured
    rate), never MEASURED.
  - Every value carries a label: MEASURED | MODELED | ESTIMATE | STRUCTURAL-ONLY.
  - FLOPs are MODELED with the formula string shown so the number is re-derivable:
        FLOPs = tokens × model_params × 2   (the standard ~2N-per-token dense-
        transformer inference estimate; cf. Kaplan et al. 2020, "Scaling Laws for
        Neural Language Models", and forge_pinn_measure.py:62 in this repo).
  - The scale lines (3 / 10 / 100 / 1000 nodes) are DERIVED from the live single-node
    measured rate (× nodes × time), all MODELED. They re-derive the founder's
    energy_revenue_model.csv lines from live data instead of restating the CSV.
  - NO fabricated joules / FLOPs / tokens / dollars. If the qualified operator
    window is unavailable, projections and current measured fields are null.
    A documented historical sample is exposed separately as SAMPLE context.

Endpoint (existing pattern, dual-register — handler functions + FastAPI register()):
  GET /api/a11oy/v1/energy/projection?window=running
    Returns the 1-day projection + the 1/3/10/100/1000-node scale projections, with
    every value labeled and the formula strings included.

Contracts consumed (built against the spec's endpoint shapes; graceful if absent):
  - Dev1 operator status:  GET /api/a11oy/v1/energy/operator/status
        { running, window_seconds, joules_measured_total, jobs_completed,
          power_w_sample, exporter_node, exporter_last_seen_ts, ... }
  - Dev2 ledger totals:    GET /api/a11oy/v1/energy/ledger
        { totals: { tokens_total, jobs_total, joules_total }, grid_price_eur_mwh, ... }
"""
from __future__ import annotations

import datetime
import importlib
import os
import time
from typing import Any, Mapping, Optional

# ---------------------------------------------------------------------------
# Honesty label constants (doctrine v11 vocabulary). These exact strings are
# what the tests grep for; a projected dollar must NEVER carry MEASURED.
# ---------------------------------------------------------------------------
MEASURED = "MEASURED"           # a real, currently-observable reading
MODELED = "MODELED"             # extrapolated/projected from a measured rate
ESTIMATE = "ESTIMATE"           # depends on an assumed (non-measured) input, e.g. resale price
STRUCTURAL_ONLY = "STRUCTURAL-ONLY"
UNAVAILABLE = "UNAVAILABLE"
SAMPLE = "SAMPLE"
REPORTED = "REPORTED"
UNKNOWN = "UNKNOWN"

# Physical / model constants.
JOULES_PER_KWH = 3_600_000.0
SECONDS_PER_HOUR = 3600.0
SECONDS_PER_DAY = 86_400.0
HOURS_PER_DAY = 24.0

# FLOPs/token: the standard dense-transformer inference estimate ~2N per generated
# token (N = parameter count). Formula string is emitted in the response so the
# number is re-derivable. Cite: Kaplan et al. 2020; forge_pinn_measure.py:62.
FLOPS_PER_PARAM_PER_TOKEN = 2.0
FLOP_FORMULA = "FLOPs = tokens × model_params × 2"
FLOP_FORMULA_CITATION = (
    "standard ~2N-per-token dense-transformer inference FLOP estimate "
    "(2 FLOPs/param/token: one multiply + one add); "
    "cf. Kaplan et al. 2020 'Scaling Laws for Neural Language Models', "
    "and forge_pinn_measure.py:62 in this repo"
)

# Resale price — an ESTIMATE input (the founder's CSV/PAYLOAD use 45¢/kWh). Swap a
# real power contract + resale rate to make the dollar true. NEVER a measured number.
RESALE_CENTS_PER_KWH = float(os.environ.get("STRIPE_PRICE_PER_KWH_CENTS", "45"))

# Model parameter count for the FLOP estimate. Default mirrors the rig's 7B-class
# coder model (qwen2.5-coder:7b ≈ 7.6e9 params). ESTIMATE input, overridable.
DEFAULT_MODEL_PARAMS = float(os.environ.get("MODEL_PARAMS", "7.6e9"))
DEFAULT_MODEL_NAME = os.environ.get("MODEL_NAME", "qwen2.5-coder:7b")

# CSV scale lines the founder charts (energy_revenue_model.csv). We RE-DERIVE these
# from the live measured single-node rate rather than restate the CSV numbers.
SCALE_NODES = (1, 3, 10, 100, 1000)

# Documented historical single-node sample (BUILD_SPEC §GROUND TRUTH, 2026-06-14
# 13:26 EDT). Its owner record is not a fresh reading or a current rate and is
# not independently replayed here. Expose it only as SAMPLE reference context.
_GROUND_TRUTH_JOULES = 78_369.586
_GROUND_TRUTH_POWER_W = 9.74
_GROUND_TRUTH_GRID_EUR_MWH = 62.08
_GROUND_TRUTH_NODE = "betterwithage"
# Historical display reference only. This arbitrary duration is NEVER a
# denominator for a current rate or 1-day/scale projection.
_GROUND_TRUTH_WINDOW_S = float(os.environ.get("GROUND_TRUTH_WINDOW_S", "3600.0"))
# Tokens/jobs are NOT in the ground-truth joules sample; without Dev2's ledger we
# cannot know them, so the fallback reports them as None (honest unknown) and the
# token/FLOP projection is omitted rather than fabricated.


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


# ---------------------------------------------------------------------------
# MEASURED-rate reader: pull the live window from Dev1 operator + Dev2 ledger.
# In-process import of the sibling handlers (no network); graceful fallback to the
# documented ground-truth single-node sample, ALWAYS saying which source was used.
# ---------------------------------------------------------------------------

def _try_operator_status() -> Optional[Mapping[str, Any]]:
    """Best-effort in-process call to Dev1's operator status handler. None if absent."""
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


def _try_ledger_totals() -> Optional[Mapping[str, Any]]:
    """Best-effort in-process call to Dev2's ledger handler. None if absent."""
    for modname, fn in (
        ("szl_energy_ledger", "handle_ledger"),
        ("szl_energy_ledger", "ledger_totals"),
        ("a11oy_energy_ledger", "handle_ledger"),
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


def _extract_window(op: Optional[Mapping[str, Any]],
                    led: Optional[Mapping[str, Any]]) -> dict:
    """Accept only an attributed, verified operator window for projection.

    `led` remains an API-compatibility parameter but lifetime ledger totals are
    deliberately not mixed with the operator's running-window denominator.
    Current operator status lacks the required attribution/window proof fields,
    so it returns the unavailable branch rather than asserting a live rate.
    """
    if isinstance(op, Mapping):
        joules = _coerce_float(op.get("joules_measured_total"))
        window_s = _coerce_float(op.get("window_seconds"))
        version = op.get("attribution_version")
        method = op.get("attribution_method")
        window_id = op.get("measurement_window_id")
        window_start = _coerce_float(op.get("measurement_window_start_ts"))
        window_end = _coerce_float(op.get("measurement_window_end_ts"))
        now = time.time()
        qualified = (
            op.get("running") is True
            and op.get("joules_measured_label") == MEASURED
            and op.get("attribution_verified") is True
            and isinstance(method, str) and bool(method.strip())
            and isinstance(version, int) and not isinstance(version, bool)
            and version >= 1
            and op.get("measurement_window_verified") is True
            and isinstance(window_id, str) and bool(window_id.strip())
            and joules is not None and joules > 0
            and window_s is not None and window_s > 0
            and window_start is not None and window_end is not None
            and window_start < window_end
            and abs((window_end - window_start) - window_s) <= 1.0
            and 0 <= now - window_end <= 12.0
        )
        if qualified:
            tokens = _coerce_float(op.get("tokens_total"))
            jobs = _coerce_float(op.get("jobs_completed"))
            if jobs is None:
                jobs = _coerce_float(op.get("jobs_done"))
            grid = _coerce_float(op.get("grid_price_eur_mwh"))
            grid_label = (MEASURED if grid is not None
                          and op.get("grid_price_label") == MEASURED else SAMPLE)
            return {
                "measured_source": "live:operator:verified-window",
                "operator_running": True,
                "qualified_window": True,
                "joules_measured": joules,
                "window_seconds": window_s,
                "tokens_measured": tokens if tokens is not None and tokens >= 0 else None,
                "jobs_measured": jobs if jobs is not None and jobs >= 0 else None,
                "tokens_label": (MEASURED if op.get("tokens_measured_label") == MEASURED
                                 else REPORTED),
                "jobs_label": (MEASURED if op.get("jobs_measured_label") == MEASURED
                               else REPORTED),
                "power_w_sample": _coerce_float(op.get("power_w_sample")),
                "grid_price_eur_mwh": grid if grid is not None else _GROUND_TRUTH_GRID_EUR_MWH,
                "grid_price_label": grid_label,
                "node": op.get("exporter_node") or op.get("node"),
                "attribution_method": method,
                "attribution_version": version,
                "measurement_window_id": window_id,
                "measurement_window_start_ts": window_start,
                "measurement_window_end_ts": window_end,
            }

    return {
        "measured_source": "unavailable:no-verified-current-window",
        "operator_running": bool(op.get("running")) if isinstance(op, Mapping) else False,
        "qualified_window": False,
        "joules_measured": None,
        "window_seconds": None,
        "tokens_measured": None,
        "jobs_measured": None,
        "power_w_sample": None,
        "grid_price_eur_mwh": None,
        "grid_price_label": UNAVAILABLE,
        "node": None,
        "historical_reference": {
            "label": SAMPLE,
            "source": "BUILD_SPEC 2026-06-14 13:26 EDT; not independently replayed",
            "joules": _GROUND_TRUTH_JOULES,
            "power_w": _GROUND_TRUTH_POWER_W,
            "grid_price_eur_mwh": _GROUND_TRUTH_GRID_EUR_MWH,
            "node": _GROUND_TRUTH_NODE,
            "rate_denominator_s": None,
        },
    }


# ---------------------------------------------------------------------------
# Core math — every projected quantity is rate × time, fully re-derivable.
# ---------------------------------------------------------------------------

def _rate_per_hour(value: Optional[float], window_s: float) -> Optional[float]:
    if value is None or window_s <= 0:
        return None
    return value * (SECONDS_PER_HOUR / window_s)


def _grid_arb_usd(joules: float, grid_eur_mwh: float,
                  eur_usd: float = 1.08) -> float:
    """Grid-arbitrage credit from MEASURED joules × grid price.

    kWh = joules / 3.6e6 ; cost(or credit) = kWh × (grid_eur_mwh/1000) EUR → USD.
    A negative grid price means the grid paid us to compute (credit positive).
    The dollar is tiny by design — this is the pennies line, not the headline.
    """
    kwh = joules / JOULES_PER_KWH
    eur_per_kwh = grid_eur_mwh / 1000.0
    usd = kwh * eur_per_kwh * eur_usd
    # Arbitrage *credit*: when grid price is negative we are paid; flip sign so a
    # negative price yields a positive credit. When positive, it is our energy cost.
    return -usd


def _resale_usd(joules: float, cents_per_kwh: float) -> float:
    """Compute-resale ESTIMATE: joules → kWh × resale rate. The BIG line — ESTIMATE.

    This is the founder's CSV resale_usd column logic: kWh × 45¢. The 45¢/kWh is an
    ESTIMATE input, so this dollar is ESTIMATE/MODELED and NEVER MEASURED.
    """
    kwh = joules / JOULES_PER_KWH
    return kwh * (cents_per_kwh / 100.0)


def _flops(tokens: Optional[float], model_params: float) -> Optional[float]:
    if tokens is None:
        return None
    return tokens * model_params * FLOPS_PER_PARAM_PER_TOKEN


def _labeled(value, label, formula=None, **extra):
    d = {"value": value, "label": label}
    if formula is not None:
        d["formula"] = formula
    d.update(extra)
    return d


def _unavailable_projection(window: str, m: Mapping[str, Any]) -> dict:
    """Retain response shape while withholding every unsupported current rate."""
    missing = _labeled(None, UNAVAILABLE)
    return {
        "ok": False,
        "status": UNAVAILABLE,
        "endpoint": "energy/projection",
        "window": window,
        "reason": "NO_VERIFIED_CURRENT_ATTRIBUTED_WINDOW",
        "measured_inputs": {
            "label": UNAVAILABLE,
            "measured_source": m.get("measured_source"),
            "joules_measured": dict(missing),
            "window_seconds": dict(missing),
            "tokens_measured": dict(missing),
            "jobs_measured": dict(missing),
            "grid_price_eur_mwh": dict(missing),
            "measured_rates_per_hour": {
                "joules_per_hr": dict(missing),
                "tokens_per_hr": dict(missing),
                "jobs_per_hr": dict(missing),
            },
            "historical_reference": m.get("historical_reference"),
        },
        "projection_1day_single_node": {
            "label": UNAVAILABLE,
            "basis": "requires a verified current attributed window",
            "compute_done": {"joules": dict(missing), "tokens": dict(missing),
                             "jobs": dict(missing), "flops": dict(missing)},
            "earnings": {"grid_arbitrage_credit_usd": dict(missing),
                         "compute_resale_usd": dict(missing),
                         "total_usd": dict(missing)},
        },
        "flop_estimate": {"label": MODELED, "formula": FLOP_FORMULA,
                          "citation": FLOP_FORMULA_CITATION, "value": None},
        "scale_projection": {"label": UNAVAILABLE, "lines": []},
        "honesty": {
            "sovereign": False,
            "lambda": "Conjecture 1",
            "free_energy": False,
            "projected_revenue_label": UNAVAILABLE,
            "resale_input_label": ESTIMATE,
            "note": "Historical SAMPLE is not a current rate; no energy, carbon, or revenue projection issued.",
        },
        "timestamp_utc": _now_iso(),
    }


def build_projection(window: str = "running",
                     model_params: float = DEFAULT_MODEL_PARAMS,
                     model_name: str = DEFAULT_MODEL_NAME,
                     resale_cents_per_kwh: float = RESALE_CENTS_PER_KWH,
                     _measured: Optional[Mapping[str, Any]] = None) -> dict:
    """Build the honest 1-day + scale projection from the live MEASURED rate.

    ``_measured`` lets local tests inject a synthetic qualified window; otherwise
    read the operator only. Historical and unqualified windows produce nulls.
    """
    m = dict(_measured) if _measured is not None else _extract_window(
        _try_operator_status(), None
    )

    qualified = (m.get("qualified_window") is True or
                 (_measured is not None and m.get("all_measured") is True))
    joules_input = _coerce_float(m.get("joules_measured"))
    window_input = _coerce_float(m.get("window_seconds"))
    if (not qualified or joules_input is None or joules_input <= 0 or
            window_input is None or window_input <= 0):
        return _unavailable_projection(window, m)

    joules = joules_input
    window_s = window_input
    tokens = _coerce_float(m.get("tokens_measured"))
    jobs = _coerce_float(m.get("jobs_measured"))
    grid = _coerce_float(m.get("grid_price_eur_mwh"))
    if grid is None:
        grid = _GROUND_TRUTH_GRID_EUR_MWH
    grid_label = m.get("grid_price_label")
    if grid_label not in (MEASURED, REPORTED, SAMPLE):
        grid_label = MEASURED if _measured is not None and m.get("all_measured") is True else SAMPLE
    tokens_label = (m.get("tokens_label") if m.get("tokens_label") in
                    (MEASURED, REPORTED) else
                    (MEASURED if _measured is not None and m.get("all_measured") is True else REPORTED))
    jobs_label = (m.get("jobs_label") if m.get("jobs_label") in
                  (MEASURED, REPORTED) else
                  (MEASURED if _measured is not None and m.get("all_measured") is True else REPORTED))
    all_inputs_measured = (grid_label == MEASURED
                           and (tokens is None or tokens_label == MEASURED)
                           and (jobs is None or jobs_label == MEASURED))

    # --- MEASURED rates (per hour) — these are observations, not projections ---
    joules_per_hr = _rate_per_hour(joules, window_s)
    tokens_per_hr = _rate_per_hour(tokens, window_s)
    jobs_per_hr = _rate_per_hour(jobs, window_s)

    # --- 1-DAY single-node projection: rate × 24h (MODELED) ---
    joules_day = joules * (SECONDS_PER_DAY / window_s)
    tokens_day = tokens * (SECONDS_PER_DAY / window_s) if tokens is not None else None
    jobs_day = jobs * (SECONDS_PER_DAY / window_s) if jobs is not None else None
    flops_day = _flops(tokens_day, model_params)

    # --- earnings/day (MODELED), split EXACTLY like the founder's CSV/chart ---
    # grid-arbitrage credit: tiny, derived from MEASURED joules-rate × grid price.
    arb_day_usd = _grid_arb_usd(joules_day, grid)
    # compute-resale: the BIG line, ESTIMATE input (45¢/kWh). NEVER MEASURED.
    resale_day_usd = _resale_usd(joules_day, resale_cents_per_kwh)
    total_day_usd = arb_day_usd + resale_day_usd

    earnings_day = {
        "grid_arbitrage_credit_usd": _labeled(
            round(arb_day_usd, 9), MODELED if grid_label == MEASURED else ESTIMATE,
            formula="(-1) × (joules/day ÷ 3.6e6 kWh) × (grid_EUR_per_MWh ÷ 1000) × EUR→USD",
            derived_from="qualified current joules-rate × source-labeled grid price",
            note="forward estimate; a SAMPLE grid input is not a live price",
        ),
        "compute_resale_usd": _labeled(
            round(resale_day_usd, 6), ESTIMATE,
            formula=f"(joules/day ÷ 3.6e6 kWh) × ({resale_cents_per_kwh}¢/kWh ÷ 100)",
            estimate_input=f"{resale_cents_per_kwh}¢/kWh resale rate (ASSUMED — swap your real contract)",
            note="the headline line. ESTIMATE input → ESTIMATE dollar (an assumption, not an observation).",
        ),
        "total_usd": _labeled(
            round(total_day_usd, 6), ESTIMATE,
            formula="grid_arbitrage_credit_usd + compute_resale_usd",
            note="ESTIMATE projection; contains an assumed resale price",
        ),
    }

    compute_day = {
        "tokens": _labeled(
            round(tokens_day, 3) if tokens_day is not None else None,
            MODELED if tokens_day is not None else STRUCTURAL_ONLY,
            formula="tokens/hr (source-labeled rate) × 24 h",
            note=("source-labeled count-rate extrapolated → MODELED" if tokens_day is not None
                  else "tokens unknown without Dev2 ledger — not fabricated"),
        ),
        "flops": _labeled(
            flops_day, MODELED if flops_day is not None else STRUCTURAL_ONLY,
            formula=FLOP_FORMULA,
            formula_expanded=(f"{round(tokens_day,3)} tokens × {model_params:g} params × "
                              f"{FLOPS_PER_PARAM_PER_TOKEN} FLOPs/param"
                              if tokens_day is not None else None),
            citation=FLOP_FORMULA_CITATION,
            model=model_name,
            model_params=model_params,
            note=("FLOPs are MODELED with the formula shown" if flops_day is not None
                  else "no measured tokens → FLOPs not derivable, not fabricated"),
        ),
        "joules": _labeled(
            round(joules_day, 3), MODELED,
            formula="joules/hr (measured rate) × 24 h",
            note="measured-rate-extrapolated → MODELED",
        ),
        "jobs": _labeled(
            round(jobs_day, 3) if jobs_day is not None else None,
            MODELED if jobs_day is not None else STRUCTURAL_ONLY,
            formula="jobs/hr (measured rate) × 24 h",
        ),
    }

    # --- scale-out: re-derive the CSV's 1/3/10/100/1000-node lines from the live
    #     single-node measured rate (× nodes × 1 year for the CSV columns, and the
    #     1-day resale/arb for the daily view). ALL MODELED. ---
    scale = []
    for n in SCALE_NODES:
        # CSV columns are annual; re-derive kwh/yr, resale_usd/yr, arb_usd/yr from
        # the live single-node measured rate so the founder's chart is data-backed.
        joules_yr_node = joules * (SECONDS_PER_DAY * 365.0 / window_s)
        kwh_yr = (joules_yr_node / JOULES_PER_KWH) * n
        resale_yr = _resale_usd(joules_yr_node, resale_cents_per_kwh) * n
        arb_yr = _grid_arb_usd(joules_yr_node, grid) * n
        scale.append({
            "nodes": n,
            "label": MODELED,
            "derivation": "live single-node measured joules-rate × nodes × 365 d",
            "kwh_yr": _labeled(round(kwh_yr, 6), MODELED,
                               formula="(joules/yr ÷ 3.6e6) × nodes"),
            "compute_resale_usd_yr": _labeled(
                round(resale_yr, 6), ESTIMATE,
                formula=f"kwh_yr × {resale_cents_per_kwh}¢/kWh",
                estimate_input=f"{resale_cents_per_kwh}¢/kWh resale (ASSUMED)"),
            "grid_arbitrage_usd_yr": _labeled(
                round(arb_yr, 9), MODELED if grid_label == MEASURED else ESTIMATE,
                formula="(-1) × kwh_yr × grid_price"),
            "total_usd_yr": _labeled(round(resale_yr + arb_yr, 6), ESTIMATE,
                                     formula="compute_resale_usd_yr + grid_arbitrage_usd_yr"),
        })

    return {
        "ok": True,
        "endpoint": "energy/projection",
        "window": window,
        "doctrine": (
            "v11: MEASURED inputs are the live joules/tokens/jobs over the running "
            "window; everything extrapolated forward is MODELED. The compute-resale "
            "dollar is an ESTIMATE (45¢/kWh assumed) and is NEVER labeled MEASURED. "
            "Grid arbitrage is the tiny pennies line. Λ = Conjecture 1; sovereign=false."
        ),
        "measured_inputs": {
            "label": MEASURED if all_inputs_measured else UNKNOWN,
            "measured_source": m.get("measured_source"),
            "joules_measured": _labeled(joules, MEASURED, note="verified current attributed window"),
            "window_seconds": _labeled(window_s, MEASURED),
            "tokens_measured": _labeled(tokens, tokens_label if tokens is not None else UNAVAILABLE),
            "jobs_measured": _labeled(jobs, jobs_label if jobs is not None else UNAVAILABLE),
            "grid_price_eur_mwh": _labeled(grid, grid_label,
                                            note="historical default" if grid_label == SAMPLE
                                            else "source-labeled live price"),
            "node": m.get("node"),
            "attribution_method": m.get("attribution_method"),
            "attribution_version": m.get("attribution_version"),
            "measurement_window_id": m.get("measurement_window_id"),
            "measurement_window_start_ts": m.get("measurement_window_start_ts"),
            "measurement_window_end_ts": m.get("measurement_window_end_ts"),
            "measured_rates_per_hour": {
                "joules_per_hr": _labeled(round(joules_per_hr, 6) if joules_per_hr is not None else None, MEASURED),
                "tokens_per_hr": _labeled(round(tokens_per_hr, 6) if tokens_per_hr is not None else None,
                                          MEASURED if tokens_per_hr is not None else STRUCTURAL_ONLY),
                "jobs_per_hr": _labeled(round(jobs_per_hr, 6) if jobs_per_hr is not None else None,
                                        MEASURED if jobs_per_hr is not None else STRUCTURAL_ONLY),
            },
        },
        "projection_1day_single_node": {
            "label": MODELED,
            "basis": "single-node measured rate × 24 h",
            "compute_done": compute_day,
            "earnings": earnings_day,
        },
        "flop_estimate": {
            "formula": FLOP_FORMULA,
            "flops_per_param_per_token": FLOPS_PER_PARAM_PER_TOKEN,
            "model": model_name,
            "model_params": model_params,
            "citation": FLOP_FORMULA_CITATION,
            "label": MODELED,
        },
        "scale_projection": {
            "label": MODELED,
            "basis": "re-derived from the live single-node measured rate (not the CSV restated)",
            "csv_reference": "energy_revenue_model.csv (founder's 1/10/100/1000-node chart)",
            "resale_estimate_input_cents_per_kwh": resale_cents_per_kwh,
            "lines": scale,
        },
        "honesty": {
            "sovereign": False,
            "lambda": "Conjecture 1",
            "free_energy": False,
            "projected_revenue_label": ESTIMATE,
            "resale_input_label": ESTIMATE,
            "note": ("A projection is MODELED with its formula shown. A projected "
                     "dollar is NEVER MEASURED. Revenue is MEASURED only when a real "
                     "charge clears (joule_billing.py)."),
        },
        "timestamp_utc": _now_iso(),
    }


def handle_projection(window: str = "running") -> dict:
    """GET /energy/projection?window=running — handler used by FastAPI and __main__."""
    try:
        return build_projection(window=window)
    except Exception as exc:  # never 500: honest degraded response
        return {
            "ok": False,
            "endpoint": "energy/projection",
            "error": str(exc),
            "doctrine": "v11: projection unavailable; no fabricated numbers emitted.",
            "timestamp_utc": _now_iso(),
        }


# ---------------------------------------------------------------------------
# FastAPI router registration — mirrors a11oy_harvest_endpoints.register() exactly.
# ---------------------------------------------------------------------------

def register(app, ns: str = "a11oy") -> str:
    """Mount the projection endpoint on the FastAPI ``app``. Returns a status string."""
    from fastapi.responses import JSONResponse

    base = f"/api/{ns}/v1/energy"

    @app.get(f"{base}/projection")
    async def _energy_projection(window: str = "running"):
        """Honest 1-day + scale projection from the live MEASURED rate (every value labeled)."""
        return JSONResponse(handle_projection(window=window))

    return "energy-projection-wired:1"


# ---------------------------------------------------------------------------
# Self-test — verifies the projection math, labels, FLOP formula, and scale lines.
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json as _json
    import sys as _sys

    print("=" * 72)
    print("szl_energy_projection — self-test (math, labels, FLOP formula, scale)")
    print("=" * 72)

    # Inject an exact measured window so the projection is deterministic.
    measured = {
        "measured_source": "selftest:injected",
        "joules_measured": 78_369.586,
        "window_seconds": 3600.0,     # 1 h window → daily = ×24
        "tokens_measured": 120_000.0,
        "jobs_measured": 40.0,
        "power_w_sample": 9.74,
        "grid_price_eur_mwh": -2.90,  # negative → grid paid us → positive arb credit
        "node": "betterwithage",
        "all_measured": True,
    }
    proj = build_projection(window="running", _measured=measured)

    # 1) projection == measured_rate × time (EXACT)
    j_day = proj["projection_1day_single_node"]["compute_done"]["joules"]["value"]
    assert abs(j_day - 78_369.586 * 24.0) < 1e-6, f"joules/day not exact: {j_day}"
    t_day = proj["projection_1day_single_node"]["compute_done"]["tokens"]["value"]
    assert abs(t_day - 120_000.0 * 24.0) < 1e-6, f"tokens/day not exact: {t_day}"
    print(f"[1] EXACT rate×time: joules/day={j_day}  tokens/day={t_day}  OK")

    # 2) FLOPs formula present + correct
    flops = proj["projection_1day_single_node"]["compute_done"]["flops"]
    assert flops["formula"] == FLOP_FORMULA, "FLOP formula string missing"
    expect_flops = t_day * DEFAULT_MODEL_PARAMS * 2.0
    assert abs(flops["value"] - expect_flops) < 1.0, "FLOPs value not re-derivable"
    print(f"[2] FLOPs formula '{flops['formula']}' → {flops['value']:.3e}  OK")

    # 3) every projected DOLLAR labeled MODELED/ESTIMATE (never MEASURED)
    earn = proj["projection_1day_single_node"]["earnings"]
    assert earn["compute_resale_usd"]["label"] == ESTIMATE
    assert earn["grid_arbitrage_credit_usd"]["label"] == MODELED
    assert earn["total_usd"]["label"] == ESTIMATE
    print(f"[3] resale={earn['compute_resale_usd']['label']} "
          f"arb={earn['grid_arbitrage_credit_usd']['label']} "
          f"total={earn['total_usd']['label']}  OK")

    # 4) scale lines derive from the single-node rate (3 must be 3× node-1 resale)
    lines = {l["nodes"]: l for l in proj["scale_projection"]["lines"]}
    r1 = lines[1]["compute_resale_usd_yr"]["value"]
    r3 = lines[3]["compute_resale_usd_yr"]["value"]
    r1000 = lines[1000]["compute_resale_usd_yr"]["value"]
    assert abs(r3 - 3 * r1) < 1e-6, "3-node resale not 3× single-node"
    assert abs(r1000 - 1000 * r1) < 1e-3, "1000-node resale not 1000× single-node"
    print(f"[4] scale derives: 1-node=${r1:.4f}/yr  3-node=${r3:.4f}/yr  "
          f"1000-node=${r1000:,.2f}/yr  OK")

    # 5) NO projected revenue may be labeled MEASURED (grep the whole output)
    blob = _json.dumps(proj)
    # measured_inputs legitimately carry MEASURED. Projected revenue must not.
    for path in ("projection_1day_single_node", "scale_projection"):
        sub = _json.dumps(proj[path])
        assert MEASURED not in sub, f"DOCTRINE VIOLATION: '{MEASURED}' in projected block {path}"
    print(f"[5] no '{MEASURED}' label inside any projected block  OK")

    print("\n--- example 1-day output (single node, injected selftest window) ---")
    print(_json.dumps(proj["projection_1day_single_node"], indent=2))
    print("\nok:true checks:5")
    _sys.exit(0)
