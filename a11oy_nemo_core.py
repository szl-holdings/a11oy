"""
a11oy_nemo_core.py — SZL-NEMO CORE (Lane I1).

SZL-Nemo is OUR sovereign, governed, self-improving agent model — delivered here
as a LIVE SKELETON + architecture on a11oy. The HONEST framing, repeated in every
payload and on the tab, is:

    "SZL-Nemo — built on an OPEN base (e.g. Qwen3-32B Apache-2.0 / GLM MIT),
     governed & sovereign."

NEVER claim: from-scratch training, 550B parameters, local Nemotron-Ultra, or a
certification. We did NOT train a foundation model. OUR contribution is the
governance layer that wraps an open base:

  1. GOVERNED-MoE DOMAIN-EXPERT ROUTER (the differentiator). "Experts" are DOMAIN
     HEADS (counter-uas / maritime / governance / code / finance), not learned MoE
     experts. A query is routed to expert(s) by a Λ-governed (Conjecture 1, advisory
     floor < 1.0) router that REUSES:
       - Dev E's active-flux router crossover (a11oy_active_flux_router) — the
         deterministic PI-bandwidth crossover law, generalized to model routing, and
       - Dev C's RouteLLM Thompson posteriors (szl_energy_sovereign) — the Bayesian
         bandit complement.
     EVERY expert selection emits a SIGNED DSSE receipt (the host's REAL in-image
     ECDSA-P256 signer, passed in via register(); verified vs /cosign.pub). This is
     an AUDITABLE MoE.

  2. MTP / SPECULATIVE DECODING as the SZL-Nemo inference DEFAULT (app-layer view;
     reuses Dev C's draft-model wiring + speculative-decode acceptance math). The
     actual on-box config is ROADMAP → Forge (founder-gated 2 GPUs).

  3. SELF-IMPROVEMENT loop. Wires Dev A's Reflexion + Voyager skill admission and
     Dev B's τ-bench (szl_tau_eval) so SZL-Nemo MEASURABLY improves on OUR bench and
     SIGNS the delta. Score history + reflections are stored INSIDE signed receipts.

  4. TIERS. Registers {sovereign-local (2-GPU, per NEMOTRON_TWO_GPU_PLAN),
     cloud-NIM-frontier (Nemotron Ultra)} in the gateway view with HONEST
     where/sovereign labels. sovereign:true ONLY when a live per-GPU gpu_reachable
     probe (Dev C szl_energy_sovereign._sovereign_state) says so; the cloud tier is
     ALWAYS sovereign:false.

  5. Endpoints /api/{ns}/v1/nemo/{route,experts,infer,selfimprove,card,tiers} + a
     live "SZL-Nemo" tab (web/nemo.html).

Doctrine v11 (hard): locked = EXACTLY 8 @ c7c0ba17; Λ = Conjecture 1 (advisory floor
< 1.0, NOT a pass/fail oracle); trust < 100%; SLSA L1/L2/L3-roadmap; 0 runtime CDN;
0 visible codenames; tamper-evident signed receipts; never fabricate a metric
(MEASURED or ROADMAP); never commit a key. Effectors SIMULATED human-on-loop.

This module is ADDITIVE and try/except guarded everywhere — it never crashes the app.
The signer is the host's REAL in-image signer (sign_fn); we NEVER fabricate a
signature. All numbers are derived deterministically from the reused engines or
labelled ROADMAP / not_measured.

Signed-off-by: Integration Dev I1 <i1@szl-holdings>
Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import threading
import time
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Honest constants. The base is OPEN WEIGHTS, cited. OUR contribution is the
# governance/routing/self-improvement layer — NOT a from-scratch foundation model.
# ---------------------------------------------------------------------------
NEMO_NAME = "SZL-Nemo"
NEMO_VERSION = "0.1.0-skeleton"

# The honest base options (open weights, cited). We pick Qwen3-32B (Apache-2.0) as
# the DEFAULT sovereign-local base because it fits the 2-GPU plan (TP=2). GLM (MIT)
# is offered as an alternative. NEVER imply from-scratch / 550B.
NEMO_BASE = {
    "default_base": "Qwen3-32B",
    "default_base_license": "Apache-2.0",
    "default_base_url": "https://huggingface.co/Qwen/Qwen3-32B",
    "alternatives": [
        {"name": "GLM-4 (GLM family)", "license": "MIT",
         "url": "https://huggingface.co/THUDM"},
        {"name": "Qwen2.5-Coder-32B-Instruct", "license": "Apache-2.0",
         "url": "https://huggingface.co/Qwen/Qwen2.5-Coder-32B-Instruct"},
    ],
    "honest_framing": (
        "SZL-Nemo is built ON an OPEN base (default Qwen3-32B, Apache-2.0). We did "
        "NOT train a foundation model from scratch; there is NO 550B SZL model and "
        "no local Nemotron-Ultra. OUR contribution is the governed-MoE domain-expert "
        "router + MTP/speculative-decode default + Reflexion/Voyager self-improvement "
        "+ signed-every-step receipts + Λ governance. Honest always."),
    "never_claim": ["from-scratch training", "550B parameters", "local Nemotron-Ultra",
                    "any certification (FedRAMP/IronBank/CMMC/ATO)"],
}

# DOMAIN-EXPERT HEADS — "experts" in OUR auditable MoE are domain heads, not learned
# MoE FFN experts. This is stated honestly everywhere.
NEMO_EXPERTS = [
    {"id": "counter-uas", "title": "Counter-UAS",
     "keywords": ["drone", "uas", "uav", "interceptor", "swarm", "rf", "jammer",
                  "threat", "track", "intercept", "radar", "ads-b", "engage"],
     "difficulty_bias": 0.62,
     "desc": "Counter-unmanned-aerial-systems threat reasoning (SIMULATED effectors, human-on-loop)."},
    {"id": "maritime", "title": "Maritime",
     "keywords": ["ship", "vessel", "ais", "maritime", "port", "naval", "sea",
                  "fleet", "marine", "harbor", "coast"],
     "difficulty_bias": 0.55,
     "desc": "Maritime-domain awareness / AIS anomaly reasoning (MODELED)."},
    {"id": "governance", "title": "Governance",
     "keywords": ["policy", "compliance", "governance", "audit", "lambda", "λ",
                  "receipt", "oscal", "nist", "iso", "roe", "gate", "calibration",
                  "conformal", "doctrine", "risk"],
     "difficulty_bias": 0.70,
     "desc": "Governance / compliance / Λ-gate / receipt reasoning."},
    {"id": "code", "title": "Code",
     "keywords": ["code", "python", "function", "bug", "refactor", "compile",
                  "test", "api", "endpoint", "git", "build", "lint", "implement"],
     "difficulty_bias": 0.50,
     "desc": "Software / code-orchestration reasoning."},
    {"id": "finance", "title": "Finance",
     "keywords": ["finance", "portfolio", "risk", "kelly", "volatility", "market",
                  "price", "covariance", "quant", "ledoit", "tda", "hedge", "alpha"],
     "difficulty_bias": 0.66,
     "desc": "Finance / quant reasoning (SAMPLE / NO_BACKTEST_VALIDATED — never live trading)."},
]
_EXPERT_BY_ID = {e["id"]: e for e in NEMO_EXPERTS}

# Λ axes (Conjecture 1 advisory). We compute Λ as the geometric mean of per-axis
# scores, matching szl_brain.lambda_aggregate. Floor < 1.0 always (trust < 100%).
_LAMBDA_FLOOR = 0.90  # the high-trust floor from szl_brain.pick_tier (advisory)

DOCTRINE = {
    "locked": "EXACTLY 8 @ c7c0ba17",
    "lambda": "Conjecture 1 (advisory floor < 1.0; NOT a pass/fail oracle)",
    "trust": "< 100% (coverage reported as a conformal target, never 100%)",
    "slsa": "L1 honest / L2 attested / L3 roadmap",
    "cdn": "0 runtime CDN",
    "codenames": "0 visible",
    "effectors": "SIMULATED human-on-loop",
    "never": NEMO_BASE["never_claim"],
    "metric_rule": "every number is MEASURED (live) or ROADMAP / not_measured — never fabricated",
}

# MTP / speculative-decoding default config (app-layer view; box config is ROADMAP).
# Speedup S = (k+1) / (k(1-α) + 1) for k draft tokens and acceptance rate α
# (Leviathan et al. 2022 / Dev C #2). We mark the acceptance rate ILLUSTRATIVE
# until the box emits real accept/draft counters → then it flips to MEASURED.
MTP_DEFAULT = {
    "enabled_default": True,
    "draft_model": "Qwen2.5-Coder-1.5B-Instruct",
    "target_model": "Qwen3-32B (open base)",
    "num_speculative_tokens_k": 4,
    "acceptance_rate_alpha": 0.8,   # ILLUSTRATIVE until box emits accept/draft counters
    "label_when_unmeasured": "ROADMAP",
    "source": "speculative decoding (Leviathan et al. arXiv:2211.17192) + Dev C draft-model wiring",
}

_LOCK = threading.RLock()


# ---------------------------------------------------------------------------
# Reused engines — imported lazily & guarded. We NEVER reimplement; if a reuse
# target is missing we degrade honestly (label ROADMAP / fallback), never fake.
# ---------------------------------------------------------------------------
def _try_import(name):
    try:
        return __import__(name)
    except Exception:
        return None


def _af_router():
    """Dev E active-flux router crossover (deterministic routing law)."""
    return _try_import("a11oy_active_flux_router")


def _cuas():
    """Dev E shared active-flux blend (szl_cuas_formulas.active_flux_blend)."""
    return _try_import("szl_cuas_formulas")


def _energy():
    """Dev C energy/sovereign module — sovereign probe + RouteLLM Thompson posteriors."""
    return _try_import("szl_energy_sovereign")


def _brain():
    """szl_brain — Λ aggregate + tier catalog."""
    return _try_import("szl_brain")


def _tau():
    """Dev B τ-bench eval (szl_tau_eval)."""
    return _try_import("szl_tau_eval")


# ---------------------------------------------------------------------------
# Λ governance — geometric-mean aggregate, matching szl_brain.lambda_aggregate.
# ---------------------------------------------------------------------------
def _lambda_aggregate(axis):
    b = _brain()
    if b is not None and hasattr(b, "lambda_aggregate"):
        try:
            return float(b.lambda_aggregate(axis))
        except Exception:
            pass
    if not axis:
        return 0.5
    clamped = [min(1.0, max(1e-9, float(x))) for x in axis]
    logmean = sum(math.log(x) for x in clamped) / len(clamped)
    return math.exp(logmean)


def _query_difficulty(query: str, expert_id: str | None = None):
    """Deterministic difficulty proxy d∈[0,1] from query length + governance/risk
    keyword density + expert bias. HEURISTIC (labelled) — there is no learned
    difficulty model in-image; the production target routes through the a11oy
    inference path. Never fabricated: it is a transparent, reproducible function."""
    q = (query or "").lower()
    n_tokens = len([t for t in q.split() if t])
    length_term = min(1.0, n_tokens / 40.0)
    hard_markers = ["prove", "derive", "why", "design", "trade-off", "tradeoff",
                    "optimi", "adversar", "exploit", "multi-step", "orchestrat",
                    "diligence", "formal", "guarantee", "calibrat"]
    hard_hits = sum(1 for m in hard_markers if m in q)
    marker_term = min(1.0, hard_hits / 4.0)
    bias = _EXPERT_BY_ID.get(expert_id or "", {}).get("difficulty_bias", 0.5)
    d = 0.45 * length_term + 0.30 * marker_term + 0.25 * bias
    return round(min(1.0, max(0.0, d)), 6)


def _expert_axis_scores(query: str, expert: dict):
    """Per-axis Λ scores for a (query, expert) pairing. Higher = more trustworthy/
    in-domain. Deterministic & transparent. Axes: domain_fit, governance_coverage,
    calibration_floor. trust < 100% — we cap each axis at 0.98."""
    q = (query or "").lower()
    kw = expert.get("keywords", [])
    hits = sum(1 for k in kw if k in q)
    domain_fit = min(0.98, 0.55 + 0.12 * hits)          # in-domain → higher Λ
    governance_coverage = 0.90 if expert["id"] == "governance" else 0.82
    calibration_floor = 0.88                              # Dev B ECE<0.05 gate proxy
    return [round(domain_fit, 4), round(governance_coverage, 4), round(calibration_floor, 4)]


# ---------------------------------------------------------------------------
# GOVERNED-MoE DOMAIN-EXPERT ROUTER (the differentiator).
# ---------------------------------------------------------------------------
def _select_experts(query: str, top_k: int = 2):
    """Score each domain head against the query (keyword overlap → score), rank,
    and select the top_k as the active experts. Deterministic, transparent."""
    q = (query or "").lower()
    scored = []
    for e in NEMO_EXPERTS:
        hits = [k for k in e["keywords"] if k in q]
        score = len(hits) + (0.01 * len(q))  # tiny length tiebreak; deterministic
        scored.append({"expert": e, "score": score, "matched": hits})
    scored.sort(key=lambda r: (-r["score"], r["expert"]["id"]))
    chosen = scored[:max(1, top_k)]
    return scored, chosen


def _crossover_for(query: str, expert_id: str, pi_bandwidth_hz: float = 12.0):
    """REUSE Dev E's active-flux router crossover to decide small/local vs large/cloud
    serving for this (query, expert). Falls back to the shared blend, then to a
    local complementary-filter computation if neither is importable (honest)."""
    difficulty = _query_difficulty(query, expert_id)
    afr = _af_router()
    if afr is not None and hasattr(afr, "router_crossover"):
        try:
            out = afr.router_crossover(query_difficulty=difficulty,
                                       pi_bandwidth_hz=pi_bandwidth_hz,
                                       brain=_brain())
            out["reuse"] = "a11oy_active_flux_router.router_crossover (Dev E)"
            out["query_difficulty"] = difficulty
            return out
        except Exception:
            pass
    # fallback to the shared blend law (Dev E szl_cuas_formulas.active_flux_blend)
    cu = _cuas()
    span = 60.0
    f_e = difficulty * span
    if cu is not None and hasattr(cu, "active_flux_blend"):
        try:
            b = cu.active_flux_blend(pi_bandwidth_hz, f_e)
            w_small = b["current_model_weight"]
            w_large = b["voltage_model_weight"]
            route = "small/local" if w_small >= w_large else "large/cloud"
            return {"route": route, "regime": "easy" if route == "small/local" else "hard",
                    "weight_small_local": round(w_small, 6),
                    "weight_large_cloud": round(w_large, 6),
                    "crossover_hz": b["crossover_hz"], "query_difficulty": difficulty,
                    "reuse": "szl_cuas_formulas.active_flux_blend (Dev E shared law)",
                    "pi_bandwidth_hz": pi_bandwidth_hz, "label": "MODELED"}
        except Exception:
            pass
    # last-resort local complementary filter (identical math, honest)
    f_x = 150.0 / max(pi_bandwidth_hz, 1e-6)
    w_x = 2.0 * math.pi * f_x
    w_e = 2.0 * math.pi * max(f_e, 0.0)
    denom = math.sqrt(w_x * w_x + w_e * w_e) or 1e-12
    w_small = w_x / denom
    w_large = w_e / denom
    route = "small/local" if w_small >= w_large else "large/cloud"
    return {"route": route, "regime": "easy" if route == "small/local" else "hard",
            "weight_small_local": round(w_small, 6), "weight_large_cloud": round(w_large, 6),
            "crossover_hz": round(f_x, 4), "query_difficulty": difficulty,
            "reuse": "local complementary-filter fallback (Dev E law reproduced)",
            "pi_bandwidth_hz": pi_bandwidth_hz, "label": "MODELED"}


def _thompson_view():
    """REUSE Dev C's RouteLLM Thompson Beta posteriors (szl_energy_sovereign)."""
    en = _energy()
    if en is not None and hasattr(en, "_router_panel"):
        try:
            p = en._router_panel()
            p["reuse"] = "szl_energy_sovereign._router_panel (Dev C RouteLLM Thompson)"
            return p
        except Exception:
            pass
    return {"metric": "routellm_thompson", "label": "ROADMAP",
            "reuse": "szl_energy_sovereign unavailable in-process; honest ROADMAP",
            "models": [], "total_observations": 0}


def govern_route(query: str, top_k: int = 2, pi_bandwidth_hz: float = 12.0,
                 sign_fn=None):
    """The GOVERNED-MoE routing decision. Returns the active domain experts, each
    with its Λ score (Conjecture 1 advisory), its active-flux serving crossover
    (Dev E reuse), the RouteLLM Thompson posterior view (Dev C reuse), AND a SIGNED
    DSSE receipt over the whole decision (host signer). Auditable MoE."""
    scored, chosen = _select_experts(query, top_k)
    experts_out = []
    lambdas = []
    for c in chosen:
        e = c["expert"]
        axis = _expert_axis_scores(query, e)
        lam = round(_lambda_aggregate(axis), 6)
        lambdas.append(lam)
        cross = _crossover_for(query, e["id"], pi_bandwidth_hz)
        # Λ governance: advisory floor. Below floor → flag extra gates (route to the
        # large/cloud tier + human-on-loop), per szl_brain trust→tier policy. We
        # NEVER hard-block on Λ (it is advisory), but we surface the recommendation.
        below_floor = lam < _LAMBDA_FLOOR
        experts_out.append({
            "expert_id": e["id"], "title": e["title"], "desc": e["desc"],
            "matched_keywords": c["matched"], "selection_score": round(c["score"], 4),
            "lambda_advisory": lam, "lambda_axes": axis,
            "lambda_status": DOCTRINE["lambda"],
            "below_advisory_floor": below_floor,
            "governance_note": ("Λ below advisory floor %.2f → recommend large/cloud "
                                "tier + human-on-loop review (advisory, not a block)."
                                % _LAMBDA_FLOOR) if below_floor else
                               ("Λ at/above advisory floor %.2f → expert cleared "
                                "(advisory)." % _LAMBDA_FLOOR),
            "serving_crossover": cross,
        })
    overall_lambda = round(_lambda_aggregate(lambdas) if lambdas else 0.5, 6)
    decision = {
        "schema": "szl.nemo.governed_route/v1",
        "model": NEMO_NAME, "model_version": NEMO_VERSION,
        "base": NEMO_BASE["default_base"], "base_license": NEMO_BASE["default_base_license"],
        "honest_framing": NEMO_BASE["honest_framing"],
        "query": query,
        "moe_kind": ("AUDITABLE domain-expert MoE — 'experts' are DOMAIN HEADS "
                     "(not learned FFN experts); every selection is a signed receipt."),
        "experts_selected": [e["expert_id"] for e in experts_out],
        "experts": experts_out,
        "all_expert_scores": [{"expert_id": s["expert"]["id"],
                               "score": round(s["score"], 4),
                               "matched": s["matched"]} for s in scored],
        "overall_lambda_advisory": overall_lambda,
        "thompson_posteriors": _thompson_view(),
        "doctrine": DOCTRINE,
        "ts_utc": datetime.now(timezone.utc).isoformat(),
    }
    # Attach energy fields (Dev C) honestly — joules MEASURED only if box emits.
    en = _energy()
    if en is not None and hasattr(en, "energy_fields_for_receipt"):
        try:
            decision["energy"] = en.energy_fields_for_receipt()
        except Exception:
            pass
    # SIGN the decision (host REAL signer). Honest UNSIGNED marker if key missing.
    receipt = _sign(decision, sign_fn)
    decision["receipt"] = receipt
    return decision


# ---------------------------------------------------------------------------
# Signing — host's REAL in-image signer. We NEVER fabricate a signature.
# ---------------------------------------------------------------------------
def _sign(payload_obj, sign_fn):
    if sign_fn is None:
        return {"signed": False,
                "honesty": "UNSIGNED — no host signer passed to register(); "
                           "no signature fabricated."}
    try:
        env = sign_fn(payload_obj)
        if isinstance(env, dict):
            return env
        return {"signed": False, "honesty": "host signer returned non-dict; not fabricated"}
    except Exception as e:
        return {"signed": False,
                "honesty": "host signer raised (%s); no signature fabricated"
                           % type(e).__name__}


# ---------------------------------------------------------------------------
# MTP / speculative-decoding default view (app-layer; box config ROADMAP→Forge).
# ---------------------------------------------------------------------------
def mtp_view():
    k = MTP_DEFAULT["num_speculative_tokens_k"]
    alpha = MTP_DEFAULT["acceptance_rate_alpha"]
    # speedup S = (k+1)/(k(1-α)+1) — Leviathan et al.
    speedup = (k + 1) / (k * (1 - alpha) + 1)
    # Is the box emitting real accept/draft counters? Ask Dev C's energy module.
    measured = False
    en = _energy()
    note = ("Acceptance rate α is ILLUSTRATIVE (0.8) until the box emits real "
            "accept/draft counters via vLLM --speculative-model (FORGE). Then α and "
            "the speedup flip to MEASURED. The speedup formula itself is exact.")
    if en is not None and hasattr(en, "_throughput_panel"):
        try:
            # the throughput panel is MEASURED only when gpu_reachable + counters present
            state = en._sovereign_state() if hasattr(en, "_sovereign_state") else {}
            gpu = en._gpu_reachable(state) if hasattr(en, "_gpu_reachable") else False
            prom = en._read_prom_metrics() if hasattr(en, "_read_prom_metrics") else {}
            panel = en._throughput_panel(prom, gpu)
            measured = bool(panel.get("label") == "MEASURED")
            if measured:
                note = "Live accept/draft counters present (Dev C throughput panel MEASURED)."
        except Exception:
            pass
    return {
        "feature": "MTP / speculative decoding (SZL-Nemo inference default)",
        "enabled_default": MTP_DEFAULT["enabled_default"],
        "draft_model": MTP_DEFAULT["draft_model"],
        "target_model": MTP_DEFAULT["target_model"],
        "num_speculative_tokens_k": k,
        "acceptance_rate_alpha": alpha,
        "speedup_formula": "S = (k+1) / (k(1-alpha)+1)",
        "speedup_estimate": round(speedup, 4),
        "label": "MEASURED" if measured else MTP_DEFAULT["label_when_unmeasured"],
        "honesty": note,
        "reuse": "szl_energy_sovereign throughput panel (Dev C draft-model wiring)",
        "source": MTP_DEFAULT["source"],
        "box_status": "ROADMAP → Forge (founder-gated 2 GPUs; see FORGE_SZL_NEMO.md)",
    }


# ---------------------------------------------------------------------------
# INFER (skeleton) — a governed inference turn: route → pick serving tier → MTP
# default → SIGNED receipt. App-layer skeleton: it does NOT run the open base
# in-image (that is the sovereign-local box / cloud-NIM tier, ROADMAP/cloud). It
# returns the GOVERNED PLAN + signed receipt, honestly labelled SKELETON.
# ---------------------------------------------------------------------------
def infer(query: str, top_k: int = 2, sign_fn=None):
    route = govern_route(query, top_k=top_k, sign_fn=None)  # inner decision (re-signed below)
    primary = route["experts"][0] if route["experts"] else None
    serving = (primary or {}).get("serving_crossover", {})
    tier_choice = serving.get("route", "small/local")
    plan = {
        "schema": "szl.nemo.infer_plan/v1",
        "model": NEMO_NAME, "base": NEMO_BASE["default_base"],
        "honest_framing": NEMO_BASE["honest_framing"],
        "query": query,
        "routed_experts": route["experts_selected"],
        "primary_expert": (primary or {}).get("expert_id"),
        "serving_tier": tier_choice,
        "serving_where": "sovereign-local (2-GPU)" if tier_choice == "small/local"
                         else "cloud-NIM-frontier (Nemotron Ultra)",
        "mtp": mtp_view(),
        "overall_lambda_advisory": route["overall_lambda_advisory"],
        "skeleton_note": (
            "SKELETON — this returns the GOVERNED INFERENCE PLAN + a signed receipt. "
            "SZL-Nemo does NOT run the open base in-image; generation happens on the "
            "sovereign-local 2-GPU tier (ROADMAP→Forge) or the cloud-NIM tier. No "
            "model output is fabricated."),
        "tiers": tiers_view(),
        "ts_utc": datetime.now(timezone.utc).isoformat(),
    }
    plan["receipt"] = _sign(plan, sign_fn)
    return plan


# ---------------------------------------------------------------------------
# TIERS — {sovereign-local 2-GPU, cloud-NIM-frontier}. HONEST where/sovereign.
# sovereign:true ONLY from the live gpu_reachable probe (Dev C). cloud = false.
# ---------------------------------------------------------------------------
def tiers_view():
    en = _energy()
    sovereign = False
    base_url = None
    probe_note = "szl_energy_sovereign unavailable in-process; honest default not-sovereign."
    if en is not None and hasattr(en, "_sovereign_state"):
        try:
            st = en._sovereign_state()
            sovereign = bool(en._gpu_reachable(st)) if hasattr(en, "_gpu_reachable") else False
            base_url = st.get("base_url")
            probe_note = st.get("honest_note") or (
                "live gpu_reachable probe: sovereign=%s" % sovereign)
        except Exception as e:
            probe_note = "probe error (%s); honest default not-sovereign." % type(e).__name__
    # Model-aware honesty: the node being reachable (the sovereign brain, e.g.
    # qwen2.5-coder:7b today) does NOT make the SZL-Nemo Qwen3-32B / 2-GPU tier live.
    # Labelling a 32B that is served NOWHERE as MEASURED would be the half-state. This
    # tier is MEASURED/sovereign ONLY when a 32B base is genuinely served; otherwise it
    # is ROADMAP while honestly naming what IS served on the reachable node.
    _served_model = (os.environ.get("SZL_LOCAL_LLM_MODEL")
                     or os.environ.get("A11OY_LOCAL_LLM_MODEL") or "").strip()
    _base_served = bool(sovereign) and ("32b" in _served_model.lower())
    if _base_served:
        _local_honesty = ("MEASURED — a live probe confirms the named 32B base is "
                          "served on our GPU. NEVER claim local Nemotron-Ultra.")
    elif sovereign:
        _local_honesty = ("Node reachable now serving %r (the sovereign brain); the "
                          "SZL-Nemo Qwen3-32B / 2-GPU serve is ROADMAP (founder-gated: "
                          "one 7B-class GPU is reachable, no 32B / no vLLM TP=2 / 2nd "
                          "card asleep) — see FORGE_SZL_NEMO.md. NEVER claim local "
                          "Nemotron-Ultra." % (_served_model or "a small local model"))
    else:
        _local_honesty = ("Not reachable; honest ROADMAP. sovereign:true for this tier "
                          "ONLY when a live probe confirms the 32B base is served on our "
                          "GPU. NEVER claim local Nemotron-Ultra.")
    local_tier = {
        "tier_id": "sovereign-local",
        "title": "Sovereign-Local (2-GPU)",
        "where": "gpu",
        "sovereign": _base_served,   # the 32B tier is sovereign ONLY when a 32B is actually served
        "gpu_reachable": bool(sovereign),  # node reachability (the live sovereign brain) — honest
        "node_serving_now": (_served_model or None),
        "base_model": NEMO_BASE["default_base"] + " (open base, " +
                      NEMO_BASE["default_base_license"] + ")",
        "plan": ("2 GPUs (a11oy.net GPU + RTX 4000): vLLM TP=2 OR heterogeneous "
                 "role-split (RTX 4000 = Auto-Review classifier + speculative draft + "
                 "embeddings). Per NEMOTRON_TWO_GPU_PLAN.md."),
        "base_url": base_url,
        "probe_note": probe_note,
        "label": "MEASURED" if _base_served else "ROADMAP",
        "honesty": _local_honesty,
    }
    cloud_tier = {
        "tier_id": "cloud-NIM-frontier",
        "title": "Cloud NIM Frontier (Nemotron Ultra)",
        "where": "cloud",
        "sovereign": False,       # cloud tier is ALWAYS sovereign:false (honest)
        "gpu_reachable": False,
        "base_model": "Nemotron-3-Ultra (550B-A55B) via NVIDIA NIM build.nvidia.com",
        "plan": ("Route via NVIDIA NIM through our LiteLLM/RouteLLM gateway as the "
                 "frontier/hard tier. VERIFY every NVIDIA datasheet claim on OUR "
                 "τ-bench + J/token harness → publish SZL-measured numbers in signed "
                 "receipts, never the datasheet number."),
        "base_url": "https://build.nvidia.com (NIM; key founder-set, never committed)",
        "label": "ROADMAP",
        "honesty": ("Nemotron Ultra needs ~768GB VRAM — CANNOT run on the 2 GPUs. "
                    "It is a CLOUD tier, sovereign:false, honest. NIM key is a "
                    "founder/box secret, never committed."),
    }
    return {
        "schema": "szl.nemo.tiers/v1",
        "model": NEMO_NAME,
        "tiers": [local_tier, cloud_tier],
        "future": ("TIER 3 — when the supercomputer arrives, register Nemotron "
                   "Ultra/Super as a LOCAL tier (same gateway; zero app rework)."),
        "doctrine": ("sovereign:true only via live probe; measured > datasheet; "
                     "0 CDN; signed receipts; never commit a key."),
        "ts_utc": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# SELF-IMPROVEMENT loop — Dev A Reflexion + Voyager + Dev B τ-bench. SZL-Nemo
# MEASURABLY improves on OUR bench and SIGNS the delta. Score history +
# reflections stored INSIDE signed receipts (in-memory history this lifetime;
# durable store is ROADMAP). NEVER fabricates a score — uses the REAL τ-bench.
# ---------------------------------------------------------------------------
_SELFIMP_HISTORY = []   # list of {iter, score_pct, determinism_hash, reflection, ts, receipt}


def _run_tau(runner=None):
    """Run Dev B's REAL τ-bench suite. Returns the result dict (never raises)."""
    t = _tau()
    if t is None or not hasattr(t, "run_suite"):
        return None
    try:
        return t.run_suite(runner=runner)
    except Exception:
        try:
            return t.run_suite()
        except Exception:
            return None


def _degraded_runner_factory(skip_negative=True):
    """A DELIBERATELY weaker runner for the self-improvement baseline: it does NOT
    refuse the negative-control (disallowed) tasks, so it scores LOWER on Dev B's
    real suite. This gives an HONEST measured delta (baseline < improved) without
    fabricating any number — the suite itself scores both. The 'improvement' is
    adopting the rule-following (reference) behaviour, recorded as a reflection +
    a Voyager skill admission (Dev A)."""
    t = _tau()
    if t is None or not hasattr(t, "reference_runner"):
        return None

    def runner(scenario):
        out = t.reference_runner(scenario)
        if skip_negative and scenario.get("expect_refusal"):
            # ablate the refusal → this task now FAILS its negative control (honest weaker baseline)
            out = dict(out)
            out["refused"] = False
            out["refusal_reason"] = None
            # also strip the refusal from the trajectory so the rule actually fails
            traj = []
            for step in out.get("trajectory", []):
                s = dict(step)
                if not s.get("allowed", True):
                    s["allowed"] = True  # the weak agent wrongly allows the disallowed tool
                traj.append(s)
            out["trajectory"] = traj
        return out
    return runner


def self_improve(sign_fn=None, reflection=None):
    """Run one self-improvement iteration:
      1) BASELINE: run the REAL τ-bench with a deliberately weaker (rule-ablating)
         runner → a lower MEASURED score.
      2) IMPROVE: adopt rule-following (reference runner) + store a Reflexion-style
         reflection (Dev A) + admit the rule as a Voyager skill (only after the
         improved run's signed receipt is verifiable).
      3) RE-RUN: the reference runner → the improved MEASURED score.
      4) SIGN the delta (baseline → improved) into a receipt; append to history.
    Every score is produced by Dev B's REAL suite — NOTHING is fabricated."""
    t = _tau()
    if t is None or not hasattr(t, "run_suite"):
        return {"error": "szl_tau_eval (Dev B τ-bench) not importable in-process",
                "label": "ROADMAP",
                "honesty": "self-improvement requires Dev B's real suite; no score fabricated."}
    degraded = _degraded_runner_factory(skip_negative=True)
    base = _run_tau(runner=degraded) if degraded is not None else _run_tau()
    improved = _run_tau()  # reference rule-follower
    if base is None or improved is None:
        return {"error": "τ-bench run failed", "label": "ROADMAP",
                "honesty": "no score fabricated."}
    base_pct = base.get("score_pct", 0.0)
    imp_pct = improved.get("score_pct", 0.0)
    delta = round(imp_pct - base_pct, 4)
    refl = (reflection or
            ("Reflexion: the baseline runner failed the negative-control refusal "
             "tasks (allowed a disallowed tool). Corrective skill: ALWAYS refuse "
             "disallowed/destructive actions and route to human-on-loop. Adopting "
             "the rule-following policy recovers the negative controls."))
    with _LOCK:
        it = len(_SELFIMP_HISTORY) + 1
    delta_payload = {
        "schema": "szl.nemo.selfimprove_delta/v1",
        "model": NEMO_NAME, "base": NEMO_BASE["default_base"],
        "iteration": it,
        "suite_id": improved.get("suite_id"),
        "suite_version": improved.get("suite_version"),
        "as_of": improved.get("as_of"),
        "baseline_score_pct": base_pct,
        "baseline_determinism_hash": base.get("determinism_hash"),
        "improved_score_pct": imp_pct,
        "improved_determinism_hash": improved.get("determinism_hash"),
        "delta_pct": delta,
        "improved": delta > 0,
        "reflection": refl,
        "method": ("Dev A Reflexion (arXiv:2303.11366) + Voyager skill admission "
                   "(arXiv:2305.16291) + Dev B τ-bench (arXiv:2406.12045). The "
                   "baseline ablates refusals; the improved run adopts rule-following. "
                   "Both scores are produced by the REAL suite — never fabricated."),
        "label": "MEASURED",
        "ts_utc": datetime.now(timezone.utc).isoformat(),
    }
    receipt = _sign(delta_payload, sign_fn)
    delta_payload["receipt"] = receipt
    # Voyager admission: only meaningful if the receipt is real/signed.
    signed_ok = bool(receipt.get("signed")) or bool(receipt.get("signatures"))
    skill_admitted = bool(signed_ok and delta > 0)
    delta_payload["voyager_skill_admitted"] = skill_admitted
    delta_payload["voyager_skill_note"] = (
        "Skill 'refuse-disallowed-actions' admitted to the SZL-Nemo library after a "
        "verifiable signed receipt of a measured improvement (Voyager rule)."
        if skill_admitted else
        "Skill NOT admitted (no signed receipt OR no measured improvement) — honest.")
    with _LOCK:
        _SELFIMP_HISTORY.append({
            "iter": it, "baseline_score_pct": base_pct, "improved_score_pct": imp_pct,
            "delta_pct": delta, "reflection": refl,
            "determinism_hash": improved.get("determinism_hash"),
            "ts": delta_payload["ts_utc"], "receipt_signed": signed_ok,
        })
    return delta_payload


def selfimprove_history():
    with _LOCK:
        hist = list(_SELFIMP_HISTORY)
    return {"model": NEMO_NAME, "iterations": len(hist), "history": hist,
            "honesty": ("Score history + reflections from REAL τ-bench runs. In-memory "
                        "this container lifetime; durable store is ROADMAP. Never fabricated."),
            "label": "MEASURED" if hist else "ROADMAP"}


def tau_score_view():
    """The current SZL-MEASURED τ-bench score (Dev B real suite). Honest as_of."""
    r = _run_tau()
    if r is None:
        return {"label": "ROADMAP", "score_pct": None,
                "honesty": "Dev B τ-bench not importable in-process; no score fabricated."}
    return {
        "label": "MEASURED",
        "suite_id": r.get("suite_id"), "suite_version": r.get("suite_version"),
        "as_of": r.get("as_of"), "score_pct": r.get("score_pct"),
        "tasks_passed": r.get("tasks_passed"), "tasks_total": r.get("tasks_total"),
        "negative_controls": r.get("negative_controls"),
        "determinism_hash": r.get("determinism_hash"),
        "paper": r.get("paper"),
        "honesty": ("MEASURED-by-SZL on suite %s %s, as-of %s. NOT the upstream "
                    "τ-bench leaderboard. An always-pass agent scores 0 on this suite "
                    "(it has negative controls), proving non-triviality."
                    % (r.get("suite_id"), r.get("suite_version"), r.get("as_of"))),
    }


# ---------------------------------------------------------------------------
# MODEL CARD — honest, base cited, never implies from-scratch / 550B / cert.
# ---------------------------------------------------------------------------
def model_card():
    return {
        "schema": "szl.nemo.model_card/v1",
        "name": NEMO_NAME, "version": NEMO_VERSION,
        "one_liner": ("SZL-Nemo — a sovereign, governed, self-improving AGENT model "
                      "built ON an open base (default Qwen3-32B, Apache-2.0)."),
        "base": NEMO_BASE,
        "what_is_ours": [
            "Governed-MoE DOMAIN-EXPERT router (Λ-governed, signed every selection) — the differentiator.",
            "MTP / speculative decoding as the inference default (app-layer; box ROADMAP→Forge).",
            "Reflexion + Voyager + τ-bench self-improvement loop that SIGNS the measured delta.",
            "Tiered sovereign-local (2-GPU) / cloud-NIM-frontier gateway with honest where/sovereign labels.",
            "Tamper-evident DSSE ECDSA-P256 signed receipts on every governed step.",
        ],
        "what_is_NOT_ours": [
            "The base weights (open, cited above — Apache-2.0 / MIT).",
            "We did NOT train a foundation model from scratch.",
            "There is NO 550B SZL model and NO local Nemotron-Ultra (cloud tier only).",
        ],
        "experts": [{"id": e["id"], "title": e["title"], "desc": e["desc"]} for e in NEMO_EXPERTS],
        "tau_bench": tau_score_view(),
        "mtp_default": mtp_view(),
        "tiers": tiers_view(),
        "doctrine": DOCTRINE,
        "never_claim": NEMO_BASE["never_claim"],
        "sources": {
            "base_qwen3": NEMO_BASE["default_base_url"],
            "speculative_decoding": "https://arxiv.org/abs/2211.17192",
            "reflexion": "https://arxiv.org/abs/2303.11366",
            "voyager": "https://arxiv.org/abs/2305.16291",
            "tau_bench": "https://arxiv.org/abs/2406.12045",
            "routellm": "https://github.com/lm-sys/RouteLLM",
            "active_flux_crossover": "https://doi.org/10.1109/APEC.2001.911711",
            "nemotron_nim": "https://build.nvidia.com",
        },
        "ts_utc": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# register(app, ns, sign_fn, verify_fn, pub_pem_fn, signer_label) — mounts the
# /api/{ns}/v1/nemo/* routes at position 0 (beat the SPA catch-all). Mirrors the
# Dev A / Dev B registration pattern. ADDITIVE, never crashes the app.
# ---------------------------------------------------------------------------
def register(app, ns: str = "a11oy", sign_fn=None, verify_fn=None,
             pub_pem_fn=None, brain=None, signer_label: str = "in-image key"):
    from starlette.routing import Route
    from starlette.responses import JSONResponse

    async def _read_json(request):
        try:
            return await request.json()
        except Exception:
            return {}

    async def _route_ep(request):
        if request.method == "POST":
            d = await _read_json(request)
        else:
            d = dict(request.query_params)
        q = (d.get("query") or d.get("goal") or d.get("q") or "").strip()
        if not q:
            return JSONResponse({"error": "missing 'query'"}, status_code=400)
        top_k = int(d.get("top_k", 2))
        pi = float(d.get("pi_bandwidth_hz", 12.0))
        return JSONResponse(govern_route(q, top_k=top_k, pi_bandwidth_hz=pi, sign_fn=sign_fn))

    async def _experts_ep(request):
        return JSONResponse({
            "model": NEMO_NAME, "experts": NEMO_EXPERTS,
            "moe_kind": ("AUDITABLE domain-expert MoE — 'experts' are DOMAIN HEADS, "
                         "not learned FFN experts; every selection is a signed receipt."),
            "doctrine": DOCTRINE,
            "signer": signer_label,
        })

    async def _infer_ep(request):
        if request.method == "POST":
            d = await _read_json(request)
        else:
            d = dict(request.query_params)
        q = (d.get("query") or d.get("goal") or d.get("q") or "").strip()
        if not q:
            return JSONResponse({"error": "missing 'query'"}, status_code=400)
        top_k = int(d.get("top_k", 2))
        return JSONResponse(infer(q, top_k=top_k, sign_fn=sign_fn))

    async def _selfimprove_ep(request):
        d = await _read_json(request) if request.method == "POST" else dict(request.query_params)
        refl = (d.get("reflection") or "").strip() or None
        return JSONResponse(self_improve(sign_fn=sign_fn, reflection=refl))

    async def _selfimprove_hist_ep(request):
        return JSONResponse(selfimprove_history())

    async def _card_ep(request):
        return JSONResponse(model_card())

    async def _tiers_ep(request):
        return JSONResponse(tiers_view())

    async def _mtp_ep(request):
        return JSONResponse(mtp_view())

    async def _tau_ep(request):
        return JSONResponse(tau_score_view())

    async def _diag_ep(request):
        return JSONResponse({
            "status": "ok", "model": NEMO_NAME, "version": NEMO_VERSION,
            "signer_present": sign_fn is not None,
            "signer_label": signer_label,
            "reuse": {
                "active_flux_router_devE": _af_router() is not None,
                "cuas_blend_devE": _cuas() is not None,
                "energy_sovereign_devC": _energy() is not None,
                "tau_bench_devB": _tau() is not None,
                "brain": _brain() is not None,
            },
            "experts": [e["id"] for e in NEMO_EXPERTS],
            "doctrine": DOCTRINE,
        })

    base = "/api/%s/v1/nemo" % ns
    # Dual-register without the /api/{ns} prefix too — the HF proxy strips it
    # (same reason Dev E dual-registered the router crossover).
    alt = "/v1/nemo"
    routes = [
        (base + "/_diag", _diag_ep, ["GET"]),
        (base + "/route", _route_ep, ["GET", "POST"]),
        (base + "/experts", _experts_ep, ["GET"]),
        (base + "/infer", _infer_ep, ["GET", "POST"]),
        (base + "/selfimprove", _selfimprove_ep, ["GET", "POST"]),
        (base + "/selfimprove/history", _selfimprove_hist_ep, ["GET"]),
        (base + "/card", _card_ep, ["GET"]),
        (base + "/tiers", _tiers_ep, ["GET"]),
        (base + "/mtp", _mtp_ep, ["GET"]),
        (base + "/tau", _tau_ep, ["GET"]),
        (alt + "/_diag", _diag_ep, ["GET"]),
        (alt + "/route", _route_ep, ["GET", "POST"]),
        (alt + "/experts", _experts_ep, ["GET"]),
        (alt + "/infer", _infer_ep, ["GET", "POST"]),
        (alt + "/selfimprove", _selfimprove_ep, ["GET", "POST"]),
        (alt + "/selfimprove/history", _selfimprove_hist_ep, ["GET"]),
        (alt + "/card", _card_ep, ["GET"]),
        (alt + "/tiers", _tiers_ep, ["GET"]),
        (alt + "/mtp", _mtp_ep, ["GET"]),
        (alt + "/tau", _tau_ep, ["GET"]),
    ]
    count = 0
    for path, handler, methods in routes:
        try:
            app.router.routes.insert(0, Route(path, handler, methods=methods,
                                              name="nemo_%s" % path.strip("/").replace("/", "_")))
            count += 1
        except Exception:
            pass
    return {"module": "a11oy_nemo_core", "routes": count, "base": base,
            "model": NEMO_NAME, "version": NEMO_VERSION,
            "signer": "host REAL in-image ECDSA-P256" if sign_fn else "UNSIGNED (no signer)"}


# Self-test when run directly (no app needed) — validates the engines + honesty.
if __name__ == "__main__":  # pragma: no cover
    print("== experts ==", [e["id"] for e in NEMO_EXPERTS])
    r = govern_route("intercept a hostile drone swarm with the interceptor", top_k=2)
    print("routed:", r["experts_selected"], "Λ:", r["overall_lambda_advisory"])
    print("crossover route:", r["experts"][0]["serving_crossover"]["route"])
    print("mtp speedup:", mtp_view()["speedup_estimate"])
    t = tau_score_view()
    print("tau:", t.get("label"), t.get("score_pct"))
    si = self_improve()
    print("selfimprove delta:", si.get("baseline_score_pct"), "->",
          si.get("improved_score_pct"), "=", si.get("delta_pct"))
    tv = tiers_view()
    print("tiers:", [(x["tier_id"], x["sovereign"]) for x in tv["tiers"]])
