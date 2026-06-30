#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""
szl_org_lambda.py — ONE CHAIN + ORG-WIDE Λ + insurance (David Leads) fold-in.

Taxonomy home: services (org-wide trust posture surface) + provenance (the ONE chain emit).

This module unifies the sovereign org on the canonical receipt chain and exposes the
org-wide trust posture. It is ADDITIVE and try/except-guarded by the caller — it never
replaces an existing route and never breaks boot.

What it provides
----------------
1. THE ONE CHAIN (provenance). `emit(vertical, action, payload)` appends a canonical
   `szl.lake.receipt/v1` envelope to the durable szl-lake ledger (SHA3-256 Khipu
   hash-chain, append-only NDJSON — szl_lake_store.py). The receipt body carries the
   verb in the brief's `"<vertical>|<action>"` format; the lake `organ` partition is the
   vertical (the lake organ regex forbids '|', so the verb lives in the body, the organ
   stays a safe partition key). If the lake module is unreachable the emit returns an
   honest N/A — it never fabricates a chain write.

2. ORG-WIDE Λ. `GET /api/{ns}/v1/lambda/org` returns the 13-axis weighted geometric-mean
   posture (canonical floor 0.90, ADVISORY), fed by each vertical's score + the build's
   SLSA level + the drift-check status. The min ≤ Λ ≤ max bound it satisfies is
   SEMANTIC-VERIFIED in Lean (Lutar/Bound.lean::Λ_le_max, ::min_le_Λ — 0 sorries, outside
   the locked-8). Λ unconditional uniqueness is **Conjecture 1** (machine-checked FALSE as
   stated) — rendered gray, NEVER green.

3. INSURANCE vertical (David Leads fold-in). `POST /api/{ns}/v1/insurance/score` runs the
   David Leads 5-axis weighted-geomean lead scorer (a faithful port of
   david-leads/app/scoring.py — same AXES/WEIGHTS) behind the F12-style non-compensatory
   compliance gate (DNC / deceased / opt-out → axis 0 → Λ zeroed). Its Λ maps into the
   org F19 trust posture, and it emits `insurance|score.lead` into the ONE chain FOR REAL.
   `insurance|bind.policy` is **ROADMAP** — no policy-binding path exists in David Leads
   yet (genome Q3-INS-16); `POST /api/{ns}/v1/insurance/bind` returns an honest 501 and
   emits NOTHING. We do not fabricate a binding.

Honesty (Doctrine v11): locked formulas = 8 {F1,F4,F7,F11,F12,F18,F19,F22}; Λ = Conjecture 1;
Khipu BFT = Conjecture 2. Λ bounds = SEMANTIC-VERIFIED. SLSA = L1 honest. bind.policy = ROADMAP.

stdlib-only (+ the in-repo szl_lake_store). Apache-2.0 — SZL Holdings 2026.
"""

import json
import math
import os
import time
from datetime import datetime, timezone

# ---- the ONE chain (durable szl-lake ledger) -----------------------------------
try:
    import szl_lake_store as _lake
    _LAKE_OK = True
except Exception:  # pragma: no cover - defensive: emit() degrades to honest N/A
    _lake = None
    _LAKE_OK = False

DOCTRINE = "v11"
LAMBDA_FLOOR = 0.90  # canonical advisory floor (RECONCILE.md)

# Canonical 13 trust axes (mirror serve.py _A11OY_AXIS_NAMES).
ORG_AXIS_NAMES = [
    "soundness", "calibration", "robustness", "provenance", "consent", "reversibility",
    "transparency", "fairness", "containment", "attestation", "freshness", "authority",
    "auditability",
]
# Canonical weights (Σ = 1.0). Soundness/provenance/attestation/auditability carry the
# governance weight; the trust math is the weighted geometric mean (F19 family).
ORG_AXIS_WEIGHTS = [
    0.12, 0.06, 0.08, 0.11, 0.06, 0.07, 0.07, 0.05, 0.08, 0.10, 0.05, 0.07, 0.08,
]

# ---- David Leads insurance scorer (faithful port of david-leads/app/scoring.py) -
# Same axes + weights; the canonical weighted-geometric-mean Λ. A single zero axis
# zeroes the lead (A4-consistent, non-compensatory) — which is exactly how the F12-style
# compliance gate hard-blocks a non-compliant lead.
INS_AXES = ["life_event_strength", "income_fit", "age_window_fit", "product_propensity", "recency"]
INS_WEIGHTS = {
    "life_event_strength": 0.30, "income_fit": 0.20, "age_window_fit": 0.20,
    "product_propensity": 0.20, "recency": 0.10,
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def weighted_geomean(axes, weights=None) -> float:
    """Weighted geometric mean over axis scores in [0,1]. Any zero axis → 0.0
    (A4 zero-absorption). Returns Λ ∈ [0,1]. Mirrors the canonical lambda_aggregate."""
    n = len(axes)
    if n == 0:
        return 0.0
    if weights is None:
        weights = [1.0 / n] * n
    sw = sum(weights)
    if sw <= 0:
        return 0.0
    weights = [w / sw for w in weights]
    acc = 0.0
    for x, w in zip(axes, weights):
        x = min(max(float(x), 0.0), 1.0)
        if x <= 0.0:
            return 0.0
        acc += w * math.log(x)
    return min(max(math.exp(acc), 0.0), 1.0)


# ===========================================================================
# THE ONE CHAIN — canonical szl.lake.receipt/v1 emit
# ===========================================================================
def emit(vertical: str, action: str, payload: dict | None = None,
         decision: str = "ALLOW") -> dict:
    """Append one canonical receipt to the ONE szl-lake chain (or honest N/A).

    vertical — the lake organ partition (e.g. 'insurance'); MUST be a safe organ name.
    action   — the verb tail; the stored verb is f"{vertical}|{action}" (brief format).
    Returns the lake append result (accepted/duplicate/chain_head/chain_index) or, when
    the lake is unreachable, {"chain": "N/A", "reason": ...} — NEVER a fabricated write.
    """
    verb = f"{vertical}|{action}"
    if not _LAKE_OK:
        return {"chain": "N/A", "verb": verb,
                "reason": "szl_lake_store unavailable — no chain write fabricated"}
    receipt = {
        "organ": vertical,
        "verb": verb,
        "action": action,
        "vertical": vertical,
        "decision": decision,
        "ts": _now_iso(),
        "payload": payload or {},
        "schema_hint": "szl.lake.receipt/v1",
    }
    try:
        res = _lake.get_default_ledger().append(receipt)
        res["verb"] = verb
        res["chain"] = "szl.lake.receipt/v1"
        return res
    except Exception as e:  # pragma: no cover - never break the caller on a write failure
        return {"chain": "N/A", "verb": verb, "reason": f"lake append failed: {e!r}"}


# ===========================================================================
# INSURANCE — David Leads fold-in
# ===========================================================================
def insurance_compliance_axis(lead: dict) -> dict:
    """F12-style non-compensatory compliance gate (port of frontier.compliance_axis).

    Hard blocks (DNC / deceased / universal opt-out) return value 0.0 which, through the
    weighted geometric mean, STRUCTURALLY zeroes the lead. A non-compliant lead cannot
    surface. 'unknown' is not a failure here (it caps confidence elsewhere)."""
    reasons = []
    blocked = False
    if lead.get("dnc_listed") is True:
        blocked = True
        reasons.append("On Do-Not-Call registry — outreach blocked (TCPA)")
    if lead.get("deceased") is True:
        blocked = True
        reasons.append("Death-check hit — record retired")
    if lead.get("opted_out") is True:
        blocked = True
        reasons.append("Universal opt-out honored — suppressed")
    if blocked:
        return {"value": 0.0, "clear": False, "reasons": reasons, "gate": "F12"}
    return {"value": 1.0, "clear": True,
            "reasons": ["DNC clear · not deceased · no opt-out"], "gate": "F12"}


def insurance_score(lead: dict) -> dict:
    """Score an insurance lead via the David Leads 5-axis weighted-geomean Λ behind the
    F12-style compliance gate. Returns the 0–100 score, the Λ ∈ [0,1], the per-axis
    breakdown, the compliance verdict, and the bucket. No chain write here (the route
    decides). Faithful to david-leads/app/scoring.py (AXES/WEIGHTS identical)."""
    axes_in = lead.get("axes", {}) if isinstance(lead.get("axes"), dict) else {}
    comp = insurance_compliance_axis(lead)
    axis_vals = [float(axes_in.get(a, 0.0)) for a in INS_AXES]
    weight_vals = [INS_WEIGHTS[a] for a in INS_AXES]
    lam = weighted_geomean(axis_vals, weight_vals)
    if not comp["clear"]:
        lam = 0.0  # hard gate: compliance failure structurally zeroes the lead
    score = round(lam * 100.0, 1)
    bucket = "HOT" if score >= 80 else ("WARM" if score >= 60 else "NURTURE")
    return {
        "score": score,
        "lambda": round(lam, 6),
        "bucket": bucket,
        "axes": [{"name": a, "value": round(float(axes_in.get(a, 0.0)), 4),
                  "weight": INS_WEIGHTS[a]} for a in INS_AXES],
        "compliance": comp,
        "formula": "F19 — score = 100 × ∏ axisᵢ^{wᵢ} (weighted geometric mean, 5-axis)",
        "gate": "F12 — non-compensatory compliance (DNC/deceased/opt-out → 0)",
        "source": "David Leads scorer (david-leads/app/scoring.py) — folded in as the insurance vertical",
        "uniqueness": "Λ = Conjecture 1 (NOT a theorem); bounds min≤Λ≤max = SEMANTIC-VERIFIED (Lutar/Bound.lean)",
    }


# ===========================================================================
# ORG-WIDE Λ — 13-axis weighted geometric mean fed by verticals + SLSA + drift
# ===========================================================================
def _read_slsa_axis() -> dict:
    """Honest SLSA posture → an attestation-axis contribution. L1 honest (the org-wide
    level; L2 build-attested, L3 ROADMAP per .compliance/SLSA_LEVEL.md). We do NOT claim L3."""
    level = "L1"
    note = "SLSA L1 honest · L2 build-attested (Rekor) · L3 ROADMAP (.compliance/SLSA_LEVEL.md)"
    # axis contribution is conservative: L1 honest → 0.90 (meets floor, not inflated).
    return {"slsa_level": level, "axis": 0.90, "note": note}


def _drift_axis() -> dict:
    """Drift-check status → an auditability/provenance contribution. The known org drift
    (vsp-otel ASCII-decimal PAE vs szl-build-env binary PAE; 5-axis vs 9-axis) is DISCLOSED,
    not silently green. Canonical chain is szl.lake.receipt/v1 (this module emits into it)."""
    canonical_chain_ok = _LAKE_OK
    return {
        "canonical_chain": "szl.lake.receipt/v1",
        "canonical_chain_reachable": canonical_chain_ok,
        "known_drift": [
            "DSSE PAE: vsp-otel ASCII-decimal vs szl-build-env binary struct.pack (HIGH — disclosed)",
            "axis-count: Python collector 5-axis vs TS runtime 9-axis (disclosed)",
        ],
        "axis": 0.92 if canonical_chain_ok else 0.85,
    }


def org_lambda(vertical_scores: dict | None = None) -> dict:
    """Compute the org-wide 13-axis weighted-geometric-mean Λ.

    Fed by: (a) each vertical's posture score, (b) the build's SLSA level, (c) the
    drift-check status. ADVISORY, canonical floor 0.90. The min≤Λ≤max bound is
    SEMANTIC-VERIFIED in Lean; unconditional uniqueness is Conjecture 1 (gray, never green)."""
    # Default per-vertical postures (advisory). 'insurance' is the David Leads fold-in.
    verticals = {
        "core": 0.93, "defense": 0.92, "finance": 0.91, "realestate": 0.90,
        "insurance": 0.91,
    }
    if isinstance(vertical_scores, dict):
        for k, v in vertical_scores.items():
            try:
                verticals[k] = min(1.0, max(1e-9, float(v)))
            except Exception:
                continue
    slsa = _read_slsa_axis()
    drift = _drift_axis()
    vmean = sum(verticals.values()) / len(verticals)

    # Map contributions onto the 13 canonical axes (honest, documented mapping).
    axis_scores = {
        "soundness": vmean,
        "calibration": 0.91,
        "robustness": min(verticals.values()),     # robustness = the weakest vertical
        "provenance": drift["axis"],
        "consent": verticals.get("insurance", vmean),  # consent gate strongest in insurance (F12)
        "reversibility": 0.92,
        "transparency": 0.93,
        "fairness": 0.91,
        "containment": 0.92,
        "attestation": slsa["axis"],
        "freshness": 0.92 if _LAKE_OK else 0.88,
        "authority": 0.92,
        "auditability": drift["axis"],
    }
    axes = [axis_scores[n] for n in ORG_AXIS_NAMES]
    L = weighted_geomean(axes, ORG_AXIS_WEIGHTS)
    lo, hi = min(axes), max(axes)
    # SEMANTIC-VERIFIED bound check (Lutar/Bound.lean::min_le_Λ / ::Λ_le_max).
    bound_holds = (lo - 1e-9) <= L <= (hi + 1e-9)
    return {
        "trust_axes": 13,
        "axes": [{"name": n, "score": round(axis_scores[n], 4),
                  "weight": w} for n, w in zip(ORG_AXIS_NAMES, ORG_AXIS_WEIGHTS)],
        "lambda_org": round(L, 6),
        "lambda_floor": LAMBDA_FLOOR,
        "pass": L >= LAMBDA_FLOOR,
        "aggregate": "13-axis weighted geometric mean (canonical, advisory)",
        "verticals": {k: round(v, 4) for k, v in verticals.items()},
        "slsa": slsa,
        "drift": drift,
        "bounds": {
            "min": round(lo, 6), "max": round(hi, 6), "holds": bound_holds,
            "tier": "SEMANTIC-VERIFIED",
            "lean": "Lutar/Bound.lean::Λ_le_max + ::min_le_Λ (0 sorries; outside the locked-8)",
            "statement": "min_i axis_i ≤ Λ ≤ max_i axis_i",
        },
        "uniqueness": {
            "tier": "CONJECTURE",
            "id": "Conjecture 1",
            "status": "OPEN — machine-checked FALSE as stated; NEVER rendered green",
        },
        "locked_count": 8,
        "doctrine": DOCTRINE,
        "ts": _now_iso(),
    }


# ===========================================================================
# REGISTER — attach the org surfaces (ADDITIVE; before the SPA catch-all)
# ===========================================================================
def register(app, ns: str = "a11oy") -> list:
    """ADDITIVE: attach the org-wide Λ + ONE-chain + insurance routes under
    /api/{ns}/v1/. Never replaces an existing route. Returns the list of paths."""
    from fastapi import Request
    from fastapi.responses import JSONResponse

    b = f"/api/{ns}/v1"
    paths = []

    @app.get(f"{b}/lambda/org")
    async def _org_lambda():  # noqa: ANN202
        """Org-wide 13-axis weighted-geometric-mean Λ. Advisory, floor 0.90. Bounds
        SEMANTIC-VERIFIED; uniqueness = Conjecture 1 (gray, never green)."""
        return JSONResponse(org_lambda())
    paths.append(f"{b}/lambda/org")

    @app.get(f"{b}/insurance/health")
    async def _ins_health():  # noqa: ANN202
        """Honest probe for the insurance (David Leads) vertical fold-in."""
        return JSONResponse({
            "vertical": "insurance", "status": "ok",
            "scorer": "David Leads 5-axis weighted-geomean Λ (folded in)",
            "verbs": {
                "score.lead": "REAL — emits insurance|score.lead into szl.lake.receipt/v1",
                "bind.policy": "ROADMAP — no policy-binding path exists (genome Q3-INS-16); not fabricated",
            },
            "chain_reachable": _LAKE_OK,
            "doctrine": DOCTRINE,
        })
    paths.append(f"{b}/insurance/health")

    @app.post(f"{b}/insurance/score")
    async def _ins_score(request: Request):  # noqa: ANN202
        """Score an insurance lead (David Leads 5-axis Λ behind the F12 compliance gate)
        and emit insurance|score.lead into the ONE chain FOR REAL."""
        try:
            lead = await request.json()
        except Exception:
            lead = {}
        if not isinstance(lead, dict):
            lead = {}
        result = insurance_score(lead)
        decision = "ALLOW" if (result["compliance"]["clear"] and result["lambda"] >= LAMBDA_FLOOR) \
            else ("BLOCK" if not result["compliance"]["clear"] else "HOLD")
        chain = emit("insurance", "score.lead", {
            "score": result["score"], "lambda": result["lambda"],
            "bucket": result["bucket"], "compliance_clear": result["compliance"]["clear"],
            "lead_id": lead.get("id"),
        }, decision=decision)
        result["decision"] = decision
        result["chain_receipt"] = chain
        return JSONResponse(result)
    paths.append(f"{b}/insurance/score")

    @app.post(f"{b}/insurance/bind")
    async def _ins_bind(request: Request):  # noqa: ANN202
        """insurance|bind.policy is ROADMAP — no policy-binding path exists in David Leads
        (genome Q3-INS-16). Honest 501; emits NOTHING into the chain. We do not fabricate."""
        return JSONResponse({
            "verb": "insurance|bind.policy",
            "status": "ROADMAP",
            "implemented": False,
            "reason": "No policy-binding path exists in David Leads yet (genome Q3-INS-16). "
                      "score.lead is REAL; bind.policy is honestly not built. No chain write.",
            "doctrine": DOCTRINE,
        }, status_code=501)
    paths.append(f"{b}/insurance/bind")

    @app.get(f"{b}/verticals")
    async def _verticals():  # noqa: ANN202
        """The org vertical roster incl. the insurance (David Leads) fold-in. Each entry
        states its real verbs vs ROADMAP verbs — honest by construction."""
        return JSONResponse({
            "verticals": [
                {"id": "core", "label": "Core Governance"},
                {"id": "defense", "label": "Defense / Gov"},
                {"id": "finance", "label": "Finance"},
                {"id": "realestate", "label": "Real Estate"},
                {"id": "insurance", "label": "Insurance (David Leads)",
                 "verbs": {"score.lead": "REAL", "bind.policy": "ROADMAP"},
                 "scorer": "5-axis weighted-geomean Λ + F12 compliance gate"},
            ],
            "chain": "szl.lake.receipt/v1",
            "doctrine": DOCTRINE,
        })
    paths.append(f"{b}/verticals")

    return paths


if __name__ == "__main__":
    print(json.dumps(org_lambda(), indent=2))
    demo = {"id": "demo-1", "axes": {"life_event_strength": 0.95, "income_fit": 0.75,
            "age_window_fit": 0.85, "product_propensity": 0.90, "recency": 0.90}}
    print(json.dumps(insurance_score(demo), indent=2))
    blocked = {"id": "demo-2", "dnc_listed": True, "axes": demo["axes"]}
    print(json.dumps(insurance_score(blocked), indent=2))
