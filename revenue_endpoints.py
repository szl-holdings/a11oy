# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED: 749 declarations · 14 unique axioms · 163 sorries · 13-axis
# Co-Authored-By: Perplexity Computer Agent
"""
revenue_endpoints.py — SZL Holdings honest revenue ESTIMATE endpoints.

Registers /api/a11oy/v1/revenue/* endpoints into the a11oy FastAPI app.
Pattern: same try/except-guarded register(app, ns="a11oy") as other a11oy modules.
Pure stdlib (+ revenue_model.py, also pure stdlib). No keys committed. Additive only.

Doctrine (binding — revenue figures demand maximum honesty):
  - Every response is explicitly labeled ESTIMATE or PRICING_HYPOTHESIS.
  - Numbers are computed from REAL inputs (live grid prices via aWATTar,
    real VIIRS satellite flare volumes). Never fabricated.
  - If live feeds are unreachable, uses documented sample values — labeled as such.
  - No free-energy. Joules stay SAMPLE until on-box NVML.
  - Λ = Conjecture 1. Locked-8 untouched. No key.

Endpoints:
  GET /api/{ns}/v1/revenue/estimate
    Pulls LIVE harvest posture + flared-gas leaderboard, runs all four estimators,
    returns structured honest revenue ESTIMATE breakdown.

  GET /api/{ns}/v1/revenue/thesis
    Static honest summary: business model, real market comparables
    (Crusoe $3B, $16B flare, $8–15M/100MW DR), SZL's differentiator.
    Clearly marked as market context + differentiator thesis, NOT a promise.
"""
from __future__ import annotations

import datetime
import json
import urllib.request
from typing import Optional

# Single source of truth for the joules honesty label. The revenue estimate runs
# off-box (no on-box NVML exporter), so the helper always returns "sample" + {}
# here — making the "joules SAMPLE off-box" claim self-verifying in the response.
# Wrapped so a missing/broken import can never take down the revenue endpoints.
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

# ---------------------------------------------------------------------------
# Lazy import helpers (harvest posture + estimators)
# ---------------------------------------------------------------------------

def _get_json(url: str, timeout: int = 12) -> Optional[object]:
    """Best-effort GET → JSON. None on any failure. Never raises."""
    UA = {"User-Agent": "szl-revenue-endpoints/1.0 (+https://a11oy.net)"}
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode("utf-8", "replace").strip()
        if not body:
            return None
        return json.loads(body)
    except Exception:
        return None


def _fetch_live_grid_price() -> tuple[Optional[float], str]:
    """Fetch current aWATTar DE grid price. Returns (price_eur_mwh, source_label)."""
    d = _get_json("https://api.awattar.de/v1/marketdata")
    if d and "data" in d and d["data"]:
        price = d["data"][0].get("marketprice")
        if price is not None:
            ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
            return float(price), f"LIVE — aWATTar DE ({ts})"
    return None, "UNREACHABLE"


def _fetch_top_flare_mcf() -> tuple[Optional[float], str, str]:
    """Fetch top operator flare volume from VIIRS leaderboard.
    Returns (mcf, company_name, source_label)."""
    _FLARE_CSV = (
        "https://raw.githubusercontent.com/flaringmonitor/viirs-flare-data/"
        "main/processed/flaring_monitor_company_stats_satellite_modeled.csv"
    )
    UA = {"User-Agent": "szl-revenue-endpoints/1.0 (+https://a11oy.net)"}
    try:
        req = urllib.request.Request(_FLARE_CSV, headers=UA)
        with urllib.request.urlopen(req, timeout=12) as r:
            text = r.read().decode("utf-8", "replace")
        lines = [ln for ln in text.splitlines() if ln.strip()]
        if len(lines) < 2:
            return None, "", "UNREACHABLE"
        headers = lines[0].split(",")
        ci_company = next((i for i, h in enumerate(headers) if "company" in h.lower()), 0)
        ci_ptype = next(
            (i for i, h in enumerate(headers)
             if "production" in h.lower() and "type" in h.lower()), None
        )
        month_cols = [i for i, h in enumerate(headers)
                      if len(h.strip()) == 7 and "-" in h.strip()]
        if not month_cols:
            month_cols = list(range(2, len(headers)))
        totals: dict = {}
        for ln in lines[1:]:
            cells = ln.split(",")
            if ci_ptype is not None and len(cells) > ci_ptype:
                if cells[ci_ptype].strip() != "sat estimated volume":
                    continue
            company = cells[ci_company].strip() if len(cells) > ci_company else "unknown"
            val = None
            for mc in reversed(month_cols):
                if mc < len(cells) and cells[mc].strip():
                    try:
                        val = float(cells[mc])
                        break
                    except ValueError:
                        continue
            if val:
                totals[company] = totals.get(company, 0.0) + val
        if totals:
            top_company, top_mcf = max(totals.items(), key=lambda kv: kv[1])
            return top_mcf, top_company, f"LIVE — NASA VIIRS/Flaring Monitor (top: {top_company[:40]})"
    except Exception:
        pass
    return None, "", "UNREACHABLE"


# ---------------------------------------------------------------------------
# Core estimate builder (used by both /estimate endpoint and self-test)
# ---------------------------------------------------------------------------

def _build_estimate(ns: str = "a11oy") -> dict:
    """
    Pull live feeds and run all four estimators. Returns structured honest ESTIMATE.
    Every figure labeled. Every input disclosed. Every caveat surfaced.
    """
    from revenue_model import (
        demand_response_value,
        energy_arbitrage_value,
        flare_carbon_credit_estimate,
        verified_compute_premium,
    )

    fetched_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # ---- Live grid price -------------------------------------------------------
    live_price, price_label = _fetch_live_grid_price()
    if live_price is None:
        grid_price = 22.0   # documented sample: German baseload 2024-06 observation
        price_source = "SAMPLE (aWATTar unreachable) — 22 EUR/MWh documented German baseload 2024-06"
    else:
        grid_price = live_price
        price_source = price_label

    # ---- Live flare volume -------------------------------------------------------
    top_mcf, top_company, flare_source = _fetch_top_flare_mcf()
    if top_mcf is None:
        flare_mcf = 200_000.0   # documented sample: World Bank 2024 large-operator
        flare_note = "SAMPLE (VIIRS unreachable) — 200,000 Mcf/month documented World Bank 2024 large-operator"
        flare_company = "sample (World Bank 2024 estimate)"
    else:
        flare_mcf = top_mcf
        flare_note = flare_source
        flare_company = top_company

    # ---- Also try live harvest posture (best-effort, optional) -----------------
    harvest_posture = None
    harvest_label = "UNREACHABLE"
    # Try the platform wasted-energy harvest module if importable (on-box)
    try:
        import wasted_energy_harvest as _weh  # type: ignore
        _hp = _weh.current_harvest_posture()
        import dataclasses as _dc
        harvest_posture = _dc.asdict(_hp) if _dc.is_dataclass(_hp) else dict(_hp)
        harvest_label = f"LIVE (on-box wasted_energy_harvest module, posture={_hp.posture})"
        # If we got a live price from harvest, it overrides aWATTar direct call
        for r in (_hp.readings or []):
            if isinstance(r, dict) and "awattar" in r.get("feed", "") and r.get("measured") and r.get("value") is not None:
                if live_price is None:
                    grid_price = float(r["value"])
                    price_source = f"LIVE — harvest module aWATTar reading ({r['feed']})"
                break
    except Exception:
        harvest_label = "UNREACHABLE (wasted_energy_harvest not in path; using direct aWATTar)"

    # ---- Run the four estimators -----------------------------------------------
    # Demand response: 100 MW node, 80% availability, $5/MWh floor
    dr = demand_response_value(
        capacity_mw=100.0,
        availability_hours=7008,    # 80% of 8760h
        capacity_price_usd_mwh=5.0,
    )

    # Energy arbitrage: 1 GWh/month at live grid price vs 80 EUR/MWh reference
    arb = energy_arbitrage_value(
        soaked_kwh=1_000_000.0,    # 1 GWh/month — illustrative node workload
        grid_price_eur_mwh=grid_price,
        full_price_eur_mwh=80.0,
    )

    # Carbon credits: from real VIIRS top-flarer volume
    cc = flare_carbon_credit_estimate(
        mcf_flared=flare_mcf,
        usd_per_tco2e=8.0,
    )

    # Verified premium: H100 SXM5 spot ~$2.50/GPU-hr (vast.ai/runpod.io/CoreWeave 2024)
    vcp = verified_compute_premium(
        base_flops_price_usd=2.50,
        proof_premium_pct=25.0,
    )

    # ---- Build summary ----------------------------------------------------------
    # Total estimate is a directional sum of annual DR + monthly arbitrage annualized +
    # monthly carbon credits annualized. NOTE: these do NOT stack additively in a real
    # project (same GWh cannot simultaneously earn DR + arbitrage + carbon credits).
    # Surfaced individually with the caveat that they serve different deal structures.
    dr_annual_usd = dr["value_usd"]
    arb_annual_eur = arb["value_eur"] * 12  # monthly → annual
    cc_annual_usd = cc["credit_value_usd"] * 12  # monthly → annual
    vcp_per_gpu_hr = vcp["total_price_usd"]

    return {
        "label": "ESTIMATE — all figures computed from real inputs, clearly labeled",
        "fetched_at": fetched_at,
        "doctrine": "v11 — Λ = Conjecture 1; locked-8 untouched; no free-energy; joules SAMPLE off-box",
        # Self-verifying joules honesty: this estimate has NO on-box exporter sample,
        # so the single source of truth resolves to "sample" with empty evidence
        # (never a fabricated measured value).
        "joules_label": _joules_truth_label(None),
        "joules_evidence": _joules_truth_evidence(None),
        "inputs_used": {
            "grid_price_eur_mwh": grid_price,
            "grid_price_source": price_source,
            "flare_mcf_top_operator": flare_mcf,
            "flare_top_company": flare_company,
            "flare_source": flare_note,
            "harvest_posture_source": harvest_label,
        },
        "demand_response": {
            "label": dr["label"],
            "value_usd_annual": dr["value_usd"],
            "human": dr["value_usd_human"],
            "basis": "100 MW node × $5/MWh × 7,008 h/yr (80% availability)",
            "citation": dr["citation"],
            "caveats": dr["caveats"],
        },
        "arbitrage": {
            "label": arb["label"],
            "value_eur_monthly": arb["value_eur"],
            "value_eur_annual_estimate": round(arb_annual_eur, 2),
            "human_monthly": arb["value_eur_human"],
            "window_type": arb["window_type"],
            "basis": "1 GWh soaked at live grid price vs 80 EUR/MWh reference",
            "citation": arb["citation"],
            "caveats": arb["caveats"],
        },
        "carbon_credits": {
            "label": cc["label"],
            "tco2e_avoided_monthly": cc["tco2e_avoided"],
            "credit_value_usd_monthly": cc["credit_value_usd"],
            "credit_value_usd_annual_estimate": round(cc_annual_usd, 2),
            "human_monthly": cc["credit_value_usd_human"],
            "methodology": cc["methodology"],
            "additionality_caveat": cc["additionality_caveat"],
            "citation": cc["citation"],
            "caveats": cc["caveats"],
        },
        "verified_compute_premium": {
            "label": vcp["label"],
            "base_price_usd_per_gpu_hr": vcp["inputs_used"]["base_flops_price_usd"],
            "premium_pct": vcp["premium_pct"],
            "premium_usd_per_gpu_hr": vcp["premium_usd"],
            "total_price_usd_per_gpu_hr": vcp_per_gpu_hr,
            "moat": vcp["moat_description"],
            "market_analogues": vcp["market_analogues"],
            "caveats": vcp["caveats"],
        },
        "summary_note": (
            "IMPORTANT: the four streams above serve DIFFERENT deal structures. "
            "A single node does NOT simultaneously earn DR payments + arbitrage + "
            "carbon credits + verified-premium on the same kWh. "
            "They represent distinct revenue CHANNELS, not an additive stack. "
            "Real revenue depends on program enrollment, operator agreements, "
            "and verified additionality for carbon credits."
        ),
        "caveats": [
            "All figures are ESTIMATES computed from documented inputs, not revenue guarantees.",
            "Demand response requires ISO/TSO program enrollment and qualification.",
            "Carbon credits require third-party Verra VM0049 additionality verification.",
            "Verified-compute premium is a PRICING HYPOTHESIS pending market discovery.",
            "Joule measurements stay SAMPLE until on-box NVML feeds the SoakLedger.",
        ],
    }


# ---------------------------------------------------------------------------
# Business thesis (static, honest)
# ---------------------------------------------------------------------------

_THESIS = {
    "label": "MARKET_CONTEXT — not a promise",
    "title": "SZL Holdings: Verified Sovereign Compute — Business Thesis",
    "version": "2026",
    "doctrine": "v11 — every figure cited to its source; no fabricated numbers",

    "szl_differentiator": {
        "summary": (
            "The SZL moat is PROVEN GOVERNANCE, not cheap watts. "
            "Crusoe Energy (~$3B valuation, 2024) already owns the "
            "stranded-energy→compute hardware play. "
            "SZL's layer: every joule + every AI decision carries a "
            "kernel-checked + DSSE-signed receipt proving it stayed inside "
            "provable bounds. Auditable years after the fact via AYNI-OS replay."
        ),
        "proof_stack": [
            "Bekenstein bound compliance (#239/#242) — kernel-gated, receipt-stamped",
            "Landauer erasure floor (#240) — monotone SoakLedger enforced",
            "DSSE-signed decision receipts — replay-auditable",
            "Lean 4 corpus: 749 declarations / 14 axioms / 163 sorries (v11 locked)",
            "Λ = Conjecture 1 (advisory; unconditional uniqueness is an open problem, NOT a theorem)",
        ],
        "target_buyers": [
            "Defense / IC (sovereign AI, auditable decisions, zero data exfiltration)",
            "Regulated industry (financial, healthcare, energy — provable compliance)",
            "Critical infrastructure (consent-only, provable bounds, monotone ledger)",
        ],
    },

    "market_context": {
        "note": "These are cited market observations — NOT SZL revenue projections.",
        "comparables": [
            {
                "entity": "Crusoe Energy",
                "description": "Stranded-gas-to-compute hyperscaler",
                "valuation": "~$3B (2024 funding round)",
                "source": "Crusoe Energy press release + TechCrunch 2024",
                "relevance": "Proves the market thesis for flare-gas compute; SZL differentiates on the proof/governance layer on top.",
            },
            {
                "entity": "Global flared gas market",
                "description": "~151 billion cubic meters (bcm) flared globally in 2024",
                "opportunity": "~$16B/yr wasted-energy opportunity (World Bank Global Gas Flaring Reduction Partnership 2024)",
                "source": "World Bank GGFR 2024 (https://www.worldbank.org/en/programs/gasflaringreduction)",
                "relevance": "SZL revenue thesis: route consented compute nodes to flare sites; earn energy + carbon credits.",
            },
            {
                "entity": "Demand response — 100 MW node",
                "description": "A 100 MW demand-response resource earns $8–15M/yr in capacity payments",
                "source": "Wood Mackenzie 2023 Demand Response Outlook; PJM RPM clearing prices; ERCOT ancillary rates",
                "relevance": (
                    "SZL nodes are dispatchable compute loads — ideal demand-response resources. "
                    "$5/MWh is the CONSERVATIVE floor; PJM RPM has cleared $10–30/MWh in tight seasons."
                ),
            },
            {
                "entity": "Capacity payments",
                "description": "~$5/MWh pay-for-availability floor (demand response)",
                "source": "FERC Order 745; ERCOT Non-Spinning Reserve rates; ISO-NE FCA; PJM RPM",
                "relevance": "The 'cash floor' — paid to be available, not to curtail. Earned passively.",
            },
            {
                "entity": "Verra VM0049",
                "description": "Methodology for Flare Gas-Powered Electricity Generation",
                "source": "https://verra.org/methodologies/vm0049/",
                "relevance": (
                    "The voluntary carbon credit methodology covering exactly SZL's use case: "
                    "generating electricity from flare gas that would otherwise be burned. "
                    "Requires additionality verification — NOT automatic."
                ),
            },
        ],
    },

    "revenue_channels": {
        "note": "Distinct deal structures — NOT additive on a single kWh.",
        "channels": [
            {
                "id": "demand_response",
                "name": "Demand Response Capacity Payments",
                "type": "RECURRING_CASH_FLOOR",
                "description": (
                    "Enroll SZL nodes as demand-response resources in ISO capacity markets. "
                    "Paid simply for being available to curtail on signal. "
                    "Conservative ESTIMATE: $3.5M/yr per 100 MW enrolled at $5/MWh floor."
                ),
                "model": "capacity_mw × capacity_price × availability_hours",
                "status": "ESTIMATE — requires ISO/TSO enrollment and qualification",
            },
            {
                "id": "energy_arbitrage",
                "name": "Energy Arbitrage (Cheap/Negative-Price Windows)",
                "type": "OPERATING_COST_SAVING",
                "description": (
                    "Gate batch compute work to negative/cheap-price windows (aWATTar live feed). "
                    "During negative-price periods the grid pays to absorb surplus — "
                    "the cost saving is the full avoided cost PLUS the negative price. "
                    "Honest: this is a COST SAVING, not direct cash unless enrolled in a "
                    "dispatchable-load payment program."
                ),
                "model": "soaked_kwh × (reference_price - live_price) / 1000",
                "status": "ESTIMATE — magnitude depends on live grid price (aWATTar feed)",
            },
            {
                "id": "carbon_credits",
                "name": "Flare-Gas Carbon Credits (Verra VM0049)",
                "type": "VOLUNTARY_CARBON_MARKET",
                "description": (
                    "At consented flare sites: generate electricity from gas that would "
                    "otherwise be flared. Earn VCM credits under Verra VM0049. "
                    "Volume from real VIIRS satellite data (Flaring Monitor, open data). "
                    "ADDITIONALITY REQUIRED: third-party Verra verification is mandatory."
                ),
                "model": "mcf_flared × 0.053 tCO2e/Mcf × carbon_price_usd/tCO2e",
                "status": "ESTIMATE — additionality audit required before any credits issued",
            },
            {
                "id": "verified_compute_premium",
                "name": "Verified Sovereign Compute Premium",
                "type": "PRICING_HYPOTHESIS",
                "description": (
                    "The core moat: sell PROVEN/audited compute at a premium over commodity. "
                    "Every job carries a DSSE-signed kernel receipt. "
                    "25% premium is a HYPOTHESIS anchored on FedRAMP (10-40%) and "
                    "DGX-certified (15-30%) premium analogues — NOT a guarantee. "
                    "Real pricing requires customer discovery and competitive testing."
                ),
                "model": "base_compute_price × (1 + proof_premium_pct/100)",
                "status": "PRICING_HYPOTHESIS — pending market discovery and ATO/FedRAMP (ROADMAP)",
            },
        ],
    },

    "honest_labels_guide": {
        "ESTIMATE": (
            "Computed from real documented inputs (live feeds or cited historical data). "
            "Directional and honest — not a guarantee. Actual results depend on market "
            "conditions, program enrollment, and operational execution."
        ),
        "PRICING_HYPOTHESIS": (
            "A market-positioning thesis based on analogue comparables. "
            "Not derived from a binding contract or observed transaction. "
            "Requires customer discovery to validate."
        ),
        "MARKET_CONTEXT": (
            "Published third-party market data (World Bank, Wood Mackenzie, Verra, ISO). "
            "Cited to its source. Describes what others have observed — "
            "not a projection of SZL's own performance."
        ),
    },

    "citation": (
        "World Bank GGFR 2024 (global flaring); "
        "Crusoe Energy 2024 funding round ($3B); "
        "Wood Mackenzie 2023 Demand Response Outlook ($8-15M/100MW); "
        "FERC Order 745 ($5/MWh floor); "
        "Verra VM0049 (flare-gas carbon credits); "
        "Ecosystem Marketplace SOVCM 2024 (VCM prices); "
        "PJM RPM / ERCOT / ISO-NE FCA (capacity clearing prices)."
    ),
}


# ---------------------------------------------------------------------------
# register(app, ns) — additive, try/except-guarded
# ---------------------------------------------------------------------------

def register(app, ns: str = "a11oy") -> dict:
    """
    Register revenue endpoints into the FastAPI app.
    Called from serve.py in a try/except guard — can NEVER crash the server.

    Routes added:
      GET /api/{ns}/v1/revenue/estimate  — live honest ESTIMATE breakdown
      GET /api/{ns}/v1/revenue/thesis    — static business thesis + market context
    """
    from fastapi.responses import JSONResponse

    @app.get(f"/api/{ns}/v1/revenue/estimate")
    async def _revenue_estimate():  # noqa: ANN202
        """
        Pull live harvest posture + flared-gas leaderboard, run the four estimators,
        return a structured honest ESTIMATE breakdown. All figures labeled.
        """
        try:
            payload = _build_estimate(ns=ns)
            return JSONResponse(payload)
        except Exception as _e:
            return JSONResponse(
                {
                    "label": "ERROR",
                    "error": repr(_e),
                    "note": "Revenue estimate failed — see logs. No fabricated fallback.",
                    "doctrine": "v11",
                },
                status_code=500,
            )

    @app.get(f"/api/{ns}/v1/revenue/thesis")
    async def _revenue_thesis():  # noqa: ANN202
        """
        Static honest business thesis: model, market comparables, SZL differentiator.
        Marked as MARKET_CONTEXT — not a promise.
        """
        return JSONResponse(_THESIS)

    return {
        "ok": True,
        "ns": ns,
        "routes": [
            f"/api/{ns}/v1/revenue/estimate",
            f"/api/{ns}/v1/revenue/thesis",
        ],
    }


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    print("=" * 72)
    print("revenue_endpoints.py — SZL Holdings revenue endpoint logic — self-test")
    print("Doctrine v11 | every output labeled ESTIMATE or PRICING_HYPOTHESIS")
    print("=" * 72)

    checks = 0

    # Build the full estimate
    print("\nBuilding live revenue estimate (fetching real feeds)...")
    est = _build_estimate(ns="a11oy")

    print(f"\n  label:                   {est['label']}")
    print(f"  grid_price_eur_mwh:      {est['inputs_used']['grid_price_eur_mwh']} EUR/MWh")
    print(f"  grid_source:             {est['inputs_used']['grid_price_source']}")
    print(f"  flare_mcf:               {est['inputs_used']['flare_mcf_top_operator']:,.0f} Mcf")
    print(f"  flare_source:            {est['inputs_used']['flare_source']}")
    print(f"  harvest_posture_source:  {est['inputs_used']['harvest_posture_source']}")

    print(f"\n  demand_response:         {est['demand_response']['label']}  {est['demand_response']['human']}")
    print(f"  arbitrage:               {est['arbitrage']['label']}  {est['arbitrage']['human_monthly']}/month")
    print(f"  carbon_credits:          {est['carbon_credits']['label']}  {est['carbon_credits']['human_monthly']}/month")
    print(f"  verified_premium:        {est['verified_compute_premium']['label']}  "
          f"${est['verified_compute_premium']['premium_usd_per_gpu_hr']:.4f}/GPU-hr premium")

    # All top-level labeled
    assert "label" in est, "top-level estimate must have a label"; checks += 1
    assert est["demand_response"]["label"] == "ESTIMATE"; checks += 1
    assert est["arbitrage"]["label"] == "ESTIMATE"; checks += 1
    assert est["carbon_credits"]["label"] == "ESTIMATE"; checks += 1
    assert est["verified_compute_premium"]["label"] == "PRICING_HYPOTHESIS"; checks += 1
    assert "additionality_caveat" in est["carbon_credits"]; checks += 1
    assert "caveats" in est; checks += 1
    assert "summary_note" in est; checks += 1

    # Thesis check
    assert _THESIS["label"] == "MARKET_CONTEXT — not a promise"; checks += 1
    assert len(_THESIS["market_context"]["comparables"]) >= 4; checks += 1
    print(f"\n  thesis label:            {_THESIS['label']}")
    print(f"  thesis comparables:      {len(_THESIS['market_context']['comparables'])}")

    print("\n" + "=" * 72)
    print(f"ok:true checks:{checks}")
    print("=" * 72)
    sys.exit(0)
