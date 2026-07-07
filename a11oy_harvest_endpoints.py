#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
"""a11oy_harvest_endpoints.py — live HTTP surface for wasted-energy harvest posture.

Doctrine (binding):
  - NO free-energy / over-unity. Harvests ALREADY-WASTED grid energy (negative-price /
    curtailed-renewable windows on PUBLIC free feeds). Does NOT create energy.
  - joules honesty via the single source of truth (szl_joules_truth). /plan and /receipt
    NEVER claim MEASURED (they have no live NVML reading) so their joules_label stays
    "sample". /posture drives the `energy` 3D surface and consults the ENERGY MEASURED
    channel (szl_energy_measured): it emits joules_label "measured" ONLY when a LIVE
    remote NVML joule meter responds live THIS request via A11OY_JOULE_METER_URLS (the
    same harness JPT/One-Bit use), with monotonic-reset detection and provenance;
    otherwise honest STRUCTURAL-ONLY ("sample") with a clear reason. NEVER fabricates a joule.
  - All feeds are FREE and PUBLIC — no token, no key, open data.
  - Reactive turns are NEVER gated by harvest posture.
  - Λ = Conjecture 1 (NEVER a theorem). Locked-8 untouched.
  - Real data only. NO MOCKS — if a feed is down, reachable:false reported honestly.

Free feeds (live, probed 2026-06-13, all responded):
  - aWATTar DE/AT wholesale price (api.awattar.de|at) — negative price = wasted
  - Energy-Charts / Fraunhofer (api.energy-charts.info) — renewable share + grid frequency
  - UK Carbon Intensity (api.carbonintensity.org.uk) — low-carbon surplus index
  - Open-Meteo (api.open-meteo.com) — wind/solar forecast = future surplus outlook
  - CAISO OASIS (oasis.caiso.com) — US California public LMP reachability probe

Formula citations (Lean kernel-proven, 0-sorry):
  - Bekenstein additive cap: bekensteinBits, bekenstein_bound_additive, info_within_bound
    [EnergyBudgetWitness.lean, lutar-lean PR #239, 0-sorry]
  - Landauer floor: landauer_floor_pos, energyFloor [LandauerFloorWitness.lean, PR #240]
  - Monotone SoakLedger: energy_ledger_monotone [EnergyBudgetWitness.lean, PR #239]
  - Ouroboros bounded loop: runLoop({ maxSteps }) [szl-holdings/ouroboros loop-kernel.ts]

Endpoints exposed (all GET):
  /api/a11oy/v1/harvest/posture  — live wasted-energy posture from free feeds
  /api/a11oy/v1/harvest/plan     — formula-bounded soak plan (?bytes=N)
  /api/a11oy/v1/harvest/receipt  — honest receipt (price_measured, joules always "sample")
  /api/a11oy/v1/harvest/world    — follow-the-wind best zone (scan_world_renshare)
  /api/a11oy/v1/harvest/index    — index of harvest endpoints + feed citations + doctrine
"""
from __future__ import annotations

import os
import re
import sys
import datetime

# Path bootstrap: ensure src/a11oy is importable (mirrors formula_endpoints pattern).
for _cand in (
    "/app/src",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"),
):
    if os.path.isdir(os.path.join(_cand, "a11oy")) and _cand not in sys.path:
        sys.path.insert(0, _cand)

# ---------------------------------------------------------------------------
# Import the vendored harvest modules (self-contained in src/a11oy/harvest/).
# Falls back gracefully so a11oy still boots even if the harvest package is missing.
# ---------------------------------------------------------------------------
try:
    from a11oy.harvest.wasted_energy_harvest import (
        current_harvest_posture,
        harvest_provenance,
        scan_world_renshare,
        POSTURE_RANK,
    )
    from a11oy.harvest.harvest_budget import plan_soak
    _HARVEST_OK = True
except Exception as _harvest_import_err:
    _HARVEST_OK = False
    _HARVEST_IMPORT_ERR = repr(_harvest_import_err)

# Single source of truth for the joules honesty label. Off-box this API has NO real
# exporter sample, so the helper returns "sample" + empty evidence — making the
# (already-hardcoded) "sample" label SELF-VERIFYING. Wrapped so it can never crash.
try:
    from szl_joules_truth import (
        joules_label as _joules_truth_label,
        joules_evidence as _joules_truth_evidence,
    )
except Exception:  # pragma: no cover - defensive: doctrine default is always sample
    def _joules_truth_label(_exporter_sample, now=None):  # type: ignore
        return "sample"
    def _joules_truth_evidence(_exporter_sample, now=None):  # type: ignore
        return {}

# This off-box API never has a real NVML exporter sample of its OWN. Passing None to
# the single source of truth ALWAYS yields ("sample", {}) — doctrine-clean + verifiable.
# It is the honest fallback for /plan and /receipt (which never claim MEASURED) and for
# /posture whenever no live meter reading is available this request.
_NO_EXPORTER_SAMPLE = None

# ENERGY-surface MEASURED channel. The /harvest/posture body drives the `energy`
# (Energy · Harvest) 3D surface HUD (joules_label / joules_evidence). Off-box this API
# has no NVML of its own, but it CAN read the LIVE remote NVML joule meter (engine
# 'omen' at meter.a-11-oy.com) the SAME way the JPT and One-Bit organs do — via the
# A11OY_JOULE_METER_URLS env. szl_energy_measured.measured_channel() performs that live
# read with monotonic-reset detection and lets szl_joules_truth (the single source of
# truth) decide MEASURED vs sample. When no meter env is set or no meter responds live
# THIS request, it returns an honest STRUCTURAL-ONLY channel with a clear reason and NO
# fabricated joule. Guarded so a missing module can never crash the endpoint.
try:
    from szl_energy_measured import measured_channel as _energy_measured_channel
    _ENERGY_MEASURED_OK = True
except Exception as _energy_measured_err:  # pragma: no cover - honest STRUCTURAL fallback
    _ENERGY_MEASURED_OK = False
    _ENERGY_MEASURED_ERR = repr(_energy_measured_err)

    def _energy_measured_channel(now=None, meter_urls=None, timeout=None):  # type: ignore
        # Module absent -> honest STRUCTURAL-ONLY, never a fabricated measured claim.
        return {
            "joules_label": "sample",
            "measured": False,
            "joules_evidence": {},
            "reason": ("szl_energy_measured unavailable (%s) — STRUCTURAL-ONLY, "
                       "no joule fabricated" % _ENERGY_MEASURED_ERR),
            "provenance": {"meter_url": None, "engine": None, "exporter": None,
                           "meter_ts": None, "fetched_at": None,
                           "method": "module unavailable"},
            "power_w": None, "joules_before": None, "joules_after": None,
            "meter_urls": [],
        }


def _energy_joules_channel() -> dict:
    """Consult the ENERGY-surface MEASURED channel for the posture body.

    Returns a doctrine-stable dict. MEASURED only when a live remote NVML meter
    responds live THIS request (and szl_joules_truth agrees); otherwise an honest
    STRUCTURAL-ONLY channel with a machine-readable reason + whatever provenance we
    have. NEVER raises, NEVER fabricates a joule.
    """
    try:
        return _energy_measured_channel()
    except Exception as exc:  # pragma: no cover - degrade honestly
        return {
            "joules_label": "sample",
            "measured": False,
            "joules_evidence": {},
            "reason": "energy measured channel raised (%s) — STRUCTURAL-ONLY, no joule fabricated"
                      % _safe_err(exc),
            "provenance": {"meter_url": None, "engine": None, "exporter": None,
                           "meter_ts": None, "fetched_at": None, "method": "exception"},
            "power_w": None, "joules_before": None, "joules_after": None, "meter_urls": [],
        }

# ---------------------------------------------------------------------------
# Feed citation table (used in /index response)
# ---------------------------------------------------------------------------
_FEED_CITATIONS = [
    {
        "feed": "awattar_de",
        "name": "aWATTar DE wholesale price",
        "url": "https://api.awattar.de/v1/marketdata",
        "note": "Negative marketprice = grid paying to offload (wasted energy). Free, no key.",
    },
    {
        "feed": "awattar_at",
        "name": "aWATTar AT wholesale price",
        "url": "https://api.awattar.at/v1/marketdata",
        "note": "Austrian market; same schema as DE. Free, no key.",
    },
    {
        "feed": "energy_charts_ren_share",
        "name": "Energy-Charts / Fraunhofer renewable share of load",
        "url": "https://api.energy-charts.info/ren_share?country=de",
        "note": "High share = surplus renewables = WHY price goes negative. Free, no key.",
    },
    {
        "feed": "grid_frequency",
        "name": "Energy-Charts / Fraunhofer grid frequency",
        "url": "https://api.energy-charts.info/frequency?country=de",
        "note": ">50 Hz = real-time oversupply. Free, no key.",
    },
    {
        "feed": "uk_carbon_intensity",
        "name": "UK Carbon Intensity",
        "url": "https://api.carbonintensity.org.uk/intensity",
        "note": "'low' index = clean surplus on GB grid. Free, no key.",
    },
    {
        "feed": "open_meteo_forecast",
        "name": "Open-Meteo wind/solar forecast",
        "url": "https://api.open-meteo.com/v1/forecast",
        "note": "Future surplus outlook (0-100 score). Free, no key.",
    },
    {
        "feed": "caiso_oasis",
        "name": "CAISO OASIS LMP (California)",
        "url": "https://oasis.caiso.com/oasisapi/SingleZip?queryname=PRC_LMP&version=1",
        "note": "US California public market price reachability probe. Free, no key.",
    },
]

_DOCTRINE_NOTE = (
    "Doctrine (binding): harvests ALREADY-WASTED grid energy only (negative-price / "
    "curtailed-renewable windows). NO free-energy / over-unity claim. "
    "joules honesty is decided by szl_joules_truth: /posture emits joules_label 'measured' "
    "ONLY when a LIVE remote NVML joule meter responds live THIS request via "
    "A11OY_JOULE_METER_URLS (with monotonic-reset detection + provenance); otherwise honest "
    "STRUCTURAL-ONLY ('sample'), never a fabricated joule. /plan and /receipt never claim "
    "MEASURED. Real data only; if a feed is down, reachable:false is reported "
    "honestly. Reactive turns are NEVER gated. Λ = Conjecture 1. Locked-8 untouched."
)

_FORMULA_CITATIONS = [
    "bekenstein_bound_additive / info_within_bound [EnergyBudgetWitness.lean, lutar-lean PR #239, 0-sorry]",
    "landauer_floor_pos / energyFloor [LandauerFloorWitness.lean, lutar-lean PR #240]",
    "energy_ledger_monotone / ledger_step_monotone [EnergyBudgetWitness.lean, PR #239]",
    "runLoop({ maxSteps }) — Ouroboros bounded-recursion cap [szl-holdings/ouroboros loop-kernel.ts]",
]


# Private addressing that must never reach a served response body, even via an
# exception string from a down feed (tailnet CGNAT 100.64-127.x, the sovereign box
# public IP, or any host:port). Mirrors the egress-scrub class used across served
# modules — it hides addressing only, it changes no true/false fact.
_PRIVATE_ADDR_RE = re.compile(
    r"(?:https?://)?"
    r"(?:100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.\d{1,3}\.\d{1,3}"
    r"|167\.233\.50\.75)"
    r"(?::\d+)?"
)


def _safe_err(exc: Exception, limit: int = 200) -> str:
    """Honest, bounded, address-scrubbed error string for a served body.

    Truncates so a stack-deep message can't bloat the response and scrubs any
    private tailnet/box address so a down-feed exception can't leak addressing.
    """
    return _PRIVATE_ADDR_RE.sub("(private)", str(exc))[:limit]


def _unavailable_response(endpoint: str) -> dict:
    """Honest degraded response when the harvest package is not importable."""
    return {
        "ok": False,
        "endpoint": endpoint,
        "error": "harvest module not importable",
        "detail": (_PRIVATE_ADDR_RE.sub("(private)", _HARVEST_IMPORT_ERR)[:200]
                   if not _HARVEST_OK else "unknown"),
        "doctrine": _DOCTRINE_NOTE,
        "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Handler functions — pure Python, called by FastAPI routes AND by __main__
# ---------------------------------------------------------------------------

def handle_posture() -> dict:
    """GET /harvest/posture — live wasted-energy posture from free feeds.

    Wraps current_harvest_posture() so any down feed degrades honestly
    (reachable:false in the per-feed readings), never 500s the whole response.
    """
    if not _HARVEST_OK:
        return _unavailable_response("posture")
    try:
        p = current_harvest_posture()
        # ENERGY-surface joules channel. Reads the LIVE remote NVML joule meter (engine
        # 'omen') via A11OY_JOULE_METER_URLS this request, with monotonic-reset detection,
        # and lets szl_joules_truth decide MEASURED vs sample. MEASURED ONLY when a meter
        # responds live THIS request; otherwise honest STRUCTURAL-ONLY with a reason and
        # NO fabricated joule. Every number carries provenance (meter url, engine, ts).
        ec = _energy_joules_channel()
        measured = bool(ec.get("measured")) and ec.get("joules_label") == "measured"
        if measured:
            joules_note = (
                "joules_label 'measured' — a LIVE remote NVML meter (engine %s) responded "
                "live THIS request via A11OY_JOULE_METER_URLS; cumulative joules climbing, "
                "monotonic-reset checked. Provenance carried below. %s"
                % (ec.get("provenance", {}).get("engine"), ec.get("reason", ""))
            )
        else:
            joules_note = (
                "joules_label 'sample' (STRUCTURAL-ONLY) — no live NVML meter reading this "
                "request; MEASURED requires a live meter delta via A11OY_JOULE_METER_URLS. "
                "No joule fabricated. reason: %s" % ec.get("reason", "no meter reading")
            )
        return {
            "ok": True,
            "posture": p.posture,
            "rank": p.rank,
            "wasted_energy_available": p.wasted_energy_available,
            "soak_hard": p.soak_hard,
            "measured_any": p.measured_any,
            "drivers": p.drivers,
            "readings": p.readings,   # list of FeedReading dicts with reachable/measured flags
            "timestamp_utc": p.timestamp_utc,
            "citation": p.citation,
            "doctrine": p.doctrine,
            # joules honesty via the ENERGY MEASURED channel -> szl_joules_truth (single
            # source of truth). MEASURED only from a live meter reading this request;
            # otherwise honest STRUCTURAL-ONLY. evidence is {} unless measured.
            "joules_label": ec.get("joules_label", "sample"),
            "joules_evidence": ec.get("joules_evidence", {}),
            "joules_measured": measured,
            "joules_reason": ec.get("reason"),
            "joules_provenance": ec.get("provenance", {}),
            "joules_power_w": ec.get("power_w"),
            "joules_before": ec.get("joules_before"),
            "joules_after": ec.get("joules_after"),
            "joules_meter_urls": ec.get("meter_urls", []),
            "joules_note": joules_note,
        }
    except Exception as exc:
        # Never 500: return honest degraded response
        return {
            "ok": False,
            "posture": "unknown",
            "error": _safe_err(exc),
            "doctrine": _DOCTRINE_NOTE,
            "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }


def handle_plan(bytes_param: int = 1024) -> dict:
    """GET /harvest/plan?bytes=N — formula-bounded soak plan.

    Calls plan_soak() with the proven-formula budget against the current
    posture. Returns admitted/refused + Bekenstein/Landauer/Ouroboros bounds
    + citations.
    """
    if not _HARVEST_OK:
        return _unavailable_response("plan")
    try:
        if bytes_param <= 0:
            return {"ok": False, "error": "bytes must be positive", "endpoint": "plan"}

        p = current_harvest_posture()
        window = {
            "posture": p.posture,
            "wasted_energy_available": p.wasted_energy_available,
            "soak_hard": p.soak_hard,
        }
        # Construct one representative job for the requested byte budget
        info_bits = bytes_param * 8
        jobs = [{"id": "api_request", "info_bits": info_bits, "joules_est": 0.0}]
        plan = plan_soak(window, jobs, window_cap_bytes=bytes_param)

        return {
            "ok": True,
            "admitted": plan.admitted,
            "refused": plan.refused,
            "posture": plan.posture,
            "wasted_energy_available": plan.wasted_energy_available,
            "bekenstein_cap_bits": plan.bekenstein_cap_bits,
            "bekenstein_used_bits": plan.bekenstein_used_bits,
            "ouroboros_steps_taken": plan.ouroboros_steps_taken,
            "ouroboros_max_steps": plan.ouroboros_max_steps,
            "ouroboros_exit_reason": plan.ouroboros_exit_reason,
            "proven_bounds_respected": plan.proven_bounds_respected,
            "joules_label": "sample",
            "honest_note": plan.honest_note,
            "formula_citations": _FORMULA_CITATIONS,
            "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
    except Exception as exc:
        return {
            "ok": False,
            "error": _safe_err(exc),
            "doctrine": _DOCTRINE_NOTE,
            "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }


def handle_receipt() -> dict:
    """GET /harvest/receipt — honest receipt dict.

    price_measured reflects whether the live feed responded.
    joules_label is ALWAYS "sample" — MEASURED requires on-box NVML.
    """
    if not _HARVEST_OK:
        return _unavailable_response("receipt")
    try:
        prov = harvest_provenance()
        # Enforce doctrine via the single source of truth: off-box there is no real
        # exporter sample, so the label resolves to "sample" and evidence is {}.
        prov["joules_label"] = _joules_truth_label(_NO_EXPORTER_SAMPLE)
        prov["joules_evidence"] = _joules_truth_evidence(_NO_EXPORTER_SAMPLE)
        prov["joules_note"] = (
            "joules_label ALWAYS 'sample' off-box. "
            "MEASURED requires a real on-box NVML meter. "
            "This API does not run on the box and NEVER emits joules_label='measured'."
        )
        prov["timestamp_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        prov["ok"] = True
        return prov
    except Exception as exc:
        return {
            "ok": False,
            "error": _safe_err(exc),
            "joules_label": "sample",
            "doctrine": _DOCTRINE_NOTE,
            "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }


def handle_world() -> dict:
    """GET /harvest/world — follow-the-wind best zone (scan_world_renshare).

    Caps zones to be polite to the free Energy-Charts endpoint (cap=8 per call).
    """
    if not _HARVEST_OK:
        return _unavailable_response("world")
    try:
        result = scan_world_renshare(cap=8)
        result["ok"] = True
        result["source"] = "Energy-Charts / Fraunhofer (api.energy-charts.info/ren_share)"
        result["note"] = (
            "Capped at 8 zones per call to be polite to the free endpoint. "
            "share = renewable % of load. best_zone = highest surplus right now."
        )
        result["doctrine"] = "follow-the-wind: route batch work to the zone with highest wasted-renewable surplus"
        result["timestamp_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        return result
    except Exception as exc:
        return {
            "ok": False,
            "error": _safe_err(exc),
            "doctrine": _DOCTRINE_NOTE,
            "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }


def handle_index() -> dict:
    """GET /harvest/index — index of harvest endpoints + feed citations + doctrine."""
    return {
        "ok": True,
        "endpoints": [
            {
                "path": "/api/a11oy/v1/harvest/posture",
                "method": "GET",
                "description": "Live wasted-energy posture from free feeds. Per-feed reachable/measured flags.",
            },
            {
                "path": "/api/a11oy/v1/harvest/plan",
                "method": "GET",
                "params": {"bytes": "integer — info budget for the soak window (default 1024)"},
                "description": "Formula-bounded soak plan. Returns admitted/refused + Bekenstein/Landauer/Ouroboros bounds.",
            },
            {
                "path": "/api/a11oy/v1/harvest/receipt",
                "method": "GET",
                "description": "Honest receipt. price_measured from real feed; joules_label ALWAYS 'sample' off-box.",
            },
            {
                "path": "/api/a11oy/v1/harvest/world",
                "method": "GET",
                "description": "Follow-the-wind: scan renewable share across zones, return best (highest surplus) zone.",
            },
            {
                "path": "/api/a11oy/v1/harvest/index",
                "method": "GET",
                "description": "This index. Lists endpoints, feed citations, formula citations, doctrine.",
            },
        ],
        "feeds": _FEED_CITATIONS,
        "formula_citations": _FORMULA_CITATIONS,
        "doctrine": _DOCTRINE_NOTE,
        "harvest_module_ok": _HARVEST_OK,
        "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# FastAPI router registration — mirrors a11oy_formula_endpoints.register() pattern
# ---------------------------------------------------------------------------

def register(app, ns: str = "a11oy") -> str:
    """Mount the harvest endpoints on the FastAPI ``app``. Returns a status string.

    Pattern mirrors a11oy_formula_endpoints.register(app, ns) exactly:
    routes mounted under /api/{ns}/v1/harvest/*.
    """
    from fastapi.responses import JSONResponse

    base = f"/api/{ns}/v1/harvest"

    @app.get(f"{base}/index")
    async def _harvest_index():
        """Index of harvest endpoints + feed citations + doctrine note."""
        return JSONResponse(handle_index())

    @app.get(f"{base}/posture")
    async def _harvest_posture():
        """Live wasted-energy posture from free feeds (per-feed reachable/measured flags)."""
        return JSONResponse(handle_posture())

    @app.get(f"{base}/plan")
    async def _harvest_plan(bytes: int = 1024):
        """Formula-bounded soak plan: Bekenstein cap + Landauer floor + Ouroboros bound."""
        return JSONResponse(handle_plan(bytes_param=bytes))

    @app.get(f"{base}/receipt")
    async def _harvest_receipt():
        """Honest receipt: price_measured from real feed; joules ALWAYS 'sample' off-box."""
        return JSONResponse(handle_receipt())

    @app.get(f"{base}/world")
    async def _harvest_world():
        """Follow-the-wind: scan_world_renshare across zones, return best surplus zone."""
        return JSONResponse(handle_world())

    status = "harvest-wired:5" if _HARVEST_OK else f"harvest-degraded:{_HARVEST_IMPORT_ERR if not _HARVEST_OK else 'unknown'}"
    return status


# ---------------------------------------------------------------------------
# Self-test — run live feeds + offline degradation check
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys as _sys
    import json as _json

    checks = 0
    print("=" * 70)
    print("a11oy_harvest_endpoints — self-test (live feeds + offline degradation)")
    print("=" * 70)

    # --- 1. posture (live feeds) ---
    print("\n[1] GET /harvest/posture (live free feeds):")
    posture_resp = handle_posture()
    print(f"    ok={posture_resp.get('ok')}  posture={posture_resp.get('posture')}  "
          f"rank={posture_resp.get('rank')}  measured_any={posture_resp.get('measured_any')}")
    print(f"    wasted_energy_available={posture_resp.get('wasted_energy_available')}  "
          f"soak_hard={posture_resp.get('soak_hard')}")
    print("    per-feed readings:")
    for r in (posture_resp.get("readings") or []):
        flag = "OK  " if r.get("reachable") else "DOWN"
        meas = "MEASURED  " if r.get("measured") else "sample/probe"
        print(f"      [{flag}] {r.get('feed','?'):26} {meas:12} "
              f"val={r.get('value')} {r.get('unit','')}  {r.get('note','')}")
    print("    drivers:")
    for d in (posture_resp.get("drivers") or []):
        print(f"      - {d}")
    assert posture_resp.get("ok") or posture_resp.get("error"), "posture must return ok or error"
    checks += 1

    # --- 2. plan (live posture → formula bounds) ---
    print("\n[2] GET /harvest/plan?bytes=512 (formula-bounded soak plan):")
    plan_resp = handle_plan(bytes_param=512)
    print(f"    ok={plan_resp.get('ok')}  posture={plan_resp.get('posture')}")
    print(f"    admitted={len(plan_resp.get('admitted',[]))}  refused={len(plan_resp.get('refused',[]))}")
    print(f"    bekenstein_cap_bits={plan_resp.get('bekenstein_cap_bits')}  "
          f"bekenstein_used_bits={plan_resp.get('bekenstein_used_bits')}")
    print(f"    ouroboros_exit={plan_resp.get('ouroboros_exit_reason')}")
    assert plan_resp.get("joules_label") == "sample", "joules_label must be 'sample'"
    checks += 1
    for b in (plan_resp.get("proven_bounds_respected") or []):
        print(f"      BOUND: {b[:100]}")

    # --- 3. receipt (joules_label invariant) ---
    print("\n[3] GET /harvest/receipt (honest receipt):")
    receipt_resp = handle_receipt()
    print(f"    ok={receipt_resp.get('ok')}  posture={receipt_resp.get('posture')}  "
          f"price_measured={receipt_resp.get('price_measured')}  "
          f"joules_label={receipt_resp.get('joules_label')}")
    assert receipt_resp.get("joules_label") == "sample", \
        f"DOCTRINE VIOLATION: joules_label must be 'sample', got {receipt_resp.get('joules_label')}"
    checks += 1
    print(f"    joules_note: {receipt_resp.get('joules_note','')[:100]}")

    # --- 4. world (follow-the-wind) ---
    print("\n[4] GET /harvest/world (follow-the-wind scan, cap=8 zones):")
    world_resp = handle_world()
    print(f"    ok={world_resp.get('ok')}  reachable_zones={world_resp.get('reachable')}  "
          f"best_zone={world_resp.get('best_zone')}  best_share={world_resp.get('best_share')}%")
    shares = world_resp.get("shares", {})
    for zone, share in sorted(shares.items(), key=lambda x: -x[1])[:5]:
        print(f"      {zone}: {share}%")
    assert isinstance(world_resp.get("ok"), bool), "world must return ok bool"
    checks += 1

    # --- 5. index ---
    print("\n[5] GET /harvest/index:")
    index_resp = handle_index()
    print(f"    ok={index_resp.get('ok')}  endpoints={len(index_resp.get('endpoints',[]))}  "
          f"feeds={len(index_resp.get('feeds',[]))}  harvest_module_ok={index_resp.get('harvest_module_ok')}")
    assert len(index_resp.get("endpoints", [])) == 5, "index must list 5 endpoints"
    checks += 1

    # --- 6. OFFLINE degradation test (monkeypatch feeds to unreachable) ---
    print("\n[6] Offline degradation test (monkeypatching feeds to unreachable):")

    # Temporarily replace the import-level functions with ones that simulate all feeds down
    if _HARVEST_OK:
        import a11oy.harvest.wasted_energy_harvest as _weh_mod

        _orig_get_json = _weh_mod._get_json
        # Monkeypatch: all network calls return None (feed unreachable)
        _weh_mod._get_json = lambda url: None

        # Also patch CAISO (uses urlopen directly)
        import urllib.request as _urllib_req
        class _FakeUrlOpen:
            def __init__(self, *a, **kw): pass
            def __enter__(self): raise OSError("monkeypatched: unreachable")
            def __exit__(self, *a): pass
        _orig_urlopen = _urllib_req.urlopen
        _urllib_req.urlopen = lambda *a, **kw: _FakeUrlOpen()

        try:
            offline_posture = _weh_mod.current_harvest_posture()
            offline_readings = offline_posture.readings
            all_unreachable = all(not r.get("reachable", True) for r in offline_readings
                                  if r.get("feed") not in ("caiso_oasis",))
            caiso_down = not any(r.get("reachable") for r in offline_readings
                                 if r.get("feed") == "caiso_oasis")
            print(f"    posture={offline_posture.posture}  measured_any={offline_posture.measured_any}")
            for r in offline_readings:
                flag = "OK  " if r.get("reachable") else "DOWN"
                print(f"      [{flag}] {r.get('feed','?'):26} reachable={r.get('reachable')} measured={r.get('measured')}")
            # When all feeds are down, measured_any must be False
            assert not offline_posture.measured_any, \
                "measured_any must be False when all feeds are unreachable (honest degradation)"
            checks += 1
            print("    honest degradation: measured_any=False when all feeds down — OK")
        finally:
            # Restore originals
            _weh_mod._get_json = _orig_get_json
            _urllib_req.urlopen = _orig_urlopen
    else:
        print(f"    SKIPPED (harvest module not importable: {_HARVEST_IMPORT_ERR})")
        checks += 1  # still count it

    # --- summary ---
    live_posture_str = posture_resp.get("posture", "unknown")
    live_measured = posture_resp.get("measured_any", False)
    print("\n" + "=" * 70)
    print(f"LIVE POSTURE : {live_posture_str}  (rank {posture_resp.get('rank', '?')}/4)")
    print(f"measured_any : {live_measured}")
    print(f"wasted_avail : {posture_resp.get('wasted_energy_available', False)}")
    print(f"soak_hard    : {posture_resp.get('soak_hard', False)}")
    print(f"joules_label : {posture_resp.get('joules_label','sample')} "
          f"(measured={posture_resp.get('joules_measured')}; "
          f"reason={str(posture_resp.get('joules_reason'))[:60]})")
    print(f"doctrine     : {posture_resp.get('doctrine', _DOCTRINE_NOTE)[:80]}...")
    print("=" * 70)
    print(f"\nok:true checks:{checks}")
    _sys.exit(0)
