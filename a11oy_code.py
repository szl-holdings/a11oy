# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
"""
a11oy.code — the 7-tier organ-mapped LLM router baked into the anatomy.

Doctrine v11 §14. ADDITIVE, self-contained module dropped beside serve.py in the
a11oy Space. Maps 7 LLM tiers to 7 organs; selects a tier from the 13-axis Λ trust
vector + organ_context; returns a DSSE-PLACEHOLDER Λ-receipt (honest: signing not
wired into CI), an in-process traceparent (honest: Wire D cross-mesh not yet
implemented), latency and a deterministic cost estimate.

The `response` is an HONEST STUB — no model key is wired in this Space. Tier
selection, organ routing, Λ-signal and the Λ-receipt hash chain are real,
deterministic math.
"""
from __future__ import annotations

import math
import time
from hashlib import sha256
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# 7 TIERS mapped to 7 organs (Doctrine v11 §14, founder LinkedIn anatomy).
# Ranked by escalation cost (0 = cheapest/fastest, 6 = frontier).
# ---------------------------------------------------------------------------
TIERS: List[Dict[str, Any]] = [
    {"tier": "FAST",     "rank": 0, "organ": "KALLPA",       "model_id": "gemini_3_1_pro|gpt_5_4_mini",
     "role": "wire propagation",       "cost_per_1k_usd": 0.0003},
    {"tier": "RECEIPT",  "rank": 1, "organ": "YAWAR",        "model_id": "claude_sonnet_4_6|llama_4",
     "role": "receipt synthesis",      "cost_per_1k_usd": 0.0030},
    {"tier": "MEMORY",   "rank": 2, "organ": "UNAY",         "model_id": "embeddings+claude_sonnet_4_6",
     "role": "cross-session recall",   "cost_per_1k_usd": 0.0020},
    {"tier": "HEART",    "rank": 3, "organ": "YUYAY",        "model_id": "claude_sonnet_4_6",
     "role": "13-axis evaluation",     "cost_per_1k_usd": 0.0030},
    {"tier": "IMMUNE",   "rank": 4, "organ": "SENTRA",       "model_id": "gpt_5_4_reasoning",
     "role": "adversarial detection",  "cost_per_1k_usd": 0.0100},
    {"tier": "PRIME",    "rank": 5, "organ": "AMARU_CORTEX", "model_id": "claude_opus_4_8",
     "role": "high-stakes reasoning",  "cost_per_1k_usd": 0.0150},
    {"tier": "FRONTIER", "rank": 6, "organ": "SUMAQ",        "model_id": "alphaproof",
     "role": "theorem discharge",      "cost_per_1k_usd": 0.0500},
]
_BY_TIER = {t["tier"]: t for t in TIERS}
_BY_ORGAN = {t["organ"]: t for t in TIERS}
_BY_RANK = {t["rank"]: t for t in TIERS}

# Organ_context keyword → preferred organ (auto-route).
_ORGAN_HINTS = {
    "AMARU_CORTEX": ["reason", "orchestrat", "plan", "strateg", "high-stakes", "complex"],
    "YUYAY":        ["eval", "axis", "gate", "critique", "score", "trust"],
    "KALLPA":       ["wire", "propagat", "route", "fast", "relay"],
    "SENTRA":       ["adversar", "threat", "attack", "inject", "malic", "immune", "security"],
    "YAWAR":        ["receipt", "ledger", "attest", "provenance", "sign"],
    "UNAY":         ["memory", "recall", "history", "embed", "retriev", "session"],
    "SUMAQ":        ["theorem", "proof", "lean", "discharge", "prove", "lemma"],
}

EPS = 1e-9


def lambda_signal(axis_scores: Optional[List[float]]) -> float:
    """13-axis Λ trust signal = weighted (uniform) geometric mean, zero-pinned."""
    if not axis_scores:
        return 0.0
    xs = [max(0.0, float(x)) for x in axis_scores]
    if any(x == 0.0 for x in xs):
        return 0.0
    return math.exp(sum(math.log(x) for x in xs) / len(xs))


def _organ_from_context(query: str, organ_context: str) -> Optional[str]:
    oc = (organ_context or "").strip().upper().replace("-", "_")
    if oc in _BY_ORGAN:
        return oc
    text = f"{organ_context} {query}".lower()
    best, score = None, 0
    for organ, kws in _ORGAN_HINTS.items():
        hits = sum(1 for kw in kws if kw in text)
        if hits > score:
            best, score = organ, hits
    return best


def _tier_from_lambda(L: float) -> str:
    """Trust→tier escalation. High Λ → FAST/cheap; low Λ → PRIME/extra-gates."""
    if L >= 0.95:
        return "FAST"
    if L >= 0.90:
        return "HEART"
    if L >= 0.75:
        return "IMMUNE"
    return "PRIME"  # low-trust / adversarial → premium + extra gates


def _cap_tier(tier_name: str, max_tier: Optional[str]) -> str:
    if not max_tier:
        return tier_name
    cap = _BY_TIER.get(str(max_tier).strip().upper())
    if not cap:
        return tier_name
    chosen = _BY_TIER[tier_name]
    if chosen["rank"] > cap["rank"]:
        return cap["tier"]
    return tier_name


def make_lambda_receipt(query: str, axis_scores: Optional[List[float]],
                        tier: Dict[str, Any], organ: str,
                        traceparent: Optional[str]) -> Dict[str, Any]:
    """DSSE PLACEHOLDER Λ-receipt (Doctrine v11: signing not wired into CI)."""
    L = lambda_signal(axis_scores)
    payload = {
        "query_digest": sha256(query.encode()).hexdigest(),
        "axis_scores": [round(float(x), 6) for x in (axis_scores or [])],
        "lambda_signal": round(L, 9),
        "tier_used": tier["tier"],
        "organ_routed": organ,
        "model_id": tier["model_id"],
        "traceparent": traceparent,
    }
    pae = f"DSSEv1 application/vnd.szl.code+json {payload}".encode()
    sig = "PLACEHOLDER:" + sha256(pae).hexdigest()
    return {
        "payloadType": "application/vnd.szl.code+json",
        "payload": payload,
        "signatures": [{"keyid": "a11oy.code", "sig": sig}],
        "signature_status": "PLACEHOLDER — Sigstore signing not yet wired into CI (Doctrine v11)",
    }


def route(query: str, axis_scores: Optional[List[float]] = None,
          organ_context: str = "", max_tier: Optional[str] = None,
          require_lambda_receipt: bool = True, traceparent: Optional[str] = None,
          auto: bool = False) -> Dict[str, Any]:
    """Route a query to an organ + tier, return the full a11oy.code response.

    auto=True → ignore organ_context, derive organ+tier purely from query + Λ.
    """
    t0 = time.time()
    L = lambda_signal(axis_scores)

    # organ selection
    organ = None if auto else _organ_from_context(query, organ_context)
    if organ is None:
        organ = _organ_from_context(query, "") or "YUYAY"

    # tier selection: organ's native tier, escalated by Λ if low-trust.
    organ_tier = _BY_ORGAN.get(organ, _BY_TIER["HEART"])
    lambda_tier = _BY_TIER[_tier_from_lambda(L)]
    # take the MORE cautious (higher rank) of organ-native vs Λ-escalation
    chosen = organ_tier if organ_tier["rank"] >= lambda_tier["rank"] else lambda_tier
    chosen_name = _cap_tier(chosen["tier"], max_tier)
    tier = _BY_TIER[chosen_name]

    response = (
        f"[HONEST STUB] a11oy.code routed to organ {organ} via tier {tier['tier']} "
        f"(model {tier['model_id']}). No model key wired in this Space; organ routing, "
        f"tier selection, Λ-signal and Λ-receipt are real deterministic math. "
        f"Role: {tier['role']}."
    )

    out: Dict[str, Any] = {
        "organ_routed": organ,
        "tier_used": tier["tier"],
        "llm_model_id": tier["model_id"],
        "response": response,
        "λ_signal": round(L, 9),
        "lambda_signal": round(L, 9),
        "latency_ms": round((time.time() - t0) * 1000.0, 3),
        "cost_estimate_usd": round(tier["cost_per_1k_usd"] * (len(query) / 1000.0 + 0.5), 6),
        "traceparent_propagated": traceparent,
        "traceparent_note": "in-process only — Wire D (cross-mesh traceparent) NOT yet implemented (Doctrine v11)",
        "doctrine": "v11",
        "service": "a11oy.code",
    }
    if require_lambda_receipt:
        out["λ_receipt"] = make_lambda_receipt(query, axis_scores, tier, organ, traceparent)
        out["lambda_receipt"] = out["λ_receipt"]
    return out


# --- governed-turn + policy-gate wiring (T002, additive) --------------------
# a11oy.code is a pure library: route() does REAL organ/tier/Λ math but returns a
# clearly-labelled honest stub for the *model-authored text* when no backend is
# wired. governed_route() lets a caller upgrade a routed turn into a REAL governed
# answer via the nemo governed-turn engine and attach the live /v1/policy/gates
# posture — WITHOUT changing route()'s default (stub-honest) behaviour. Endpoint
# values are relative path templates only (no external URL — 0-CDN).
NEMO_TURN_ENDPOINT = "/api/{ns}/v1/code/turn"
POLICY_GATES_ENDPOINT = "/api/{ns}/v1/policy/gates"


def governed_route(query: str, axis_scores: Optional[List[float]] = None,
                   organ_context: str = "", *, governed_turn=None,
                   policy_gates=None, traceparent: Optional[str] = None,
                   **route_kw) -> Dict[str, Any]:
    """route() enriched with an (optional, dependency-injected) REAL nemo
    governed-turn answer and the live /v1/policy/gates posture.

    Mirrors this codebase's dependency-injection convention (see a11oy_agent_loop):
    the caller wires the real backends. With no backend injected, the honest stub
    from route() is preserved verbatim — this NEVER fabricates a model answer.

        governed_turn(query, organ) -> dict | str   (optional real answer source)
        policy_gates                -> dict | callable() -> dict  (/v1/policy/gates)
    """
    out = route(query, axis_scores, organ_context=organ_context,
                traceparent=traceparent, **route_kw)
    out["governed_turn_endpoint"] = NEMO_TURN_ENDPOINT
    out["policy_gates_endpoint"] = POLICY_GATES_ENDPOINT
    if callable(governed_turn):
        try:
            turn = governed_turn(query, out["organ_routed"])
        except TypeError:
            turn = governed_turn(query)
        if isinstance(turn, dict):
            out["governed_turn"] = turn
            ans = turn.get("answer") or turn.get("text") or turn.get("response")
            if ans and not turn.get("stub"):
                out["response"] = ans
                out["response_source"] = "nemo governed-turn (real, injected)"
        elif isinstance(turn, str) and turn:
            out["response"] = turn
            out["response_source"] = "nemo governed-turn (real, injected)"
    else:
        out["response_source"] = "honest stub (no governed-turn backend injected)"
    gates = policy_gates() if callable(policy_gates) else policy_gates
    if gates is not None:
        out["policy_gates"] = gates
    return out


def tiers_payload() -> Dict[str, Any]:
    return {
        "count": len(TIERS),
        "tiers": TIERS,
        "organ_mapping": {t["organ"]: t["tier"] for t in TIERS},
        "doctrine": "v11",
        "service": "a11oy.code",
        "honesty": {
            "lambda_receipt_signature": "PLACEHOLDER (Sigstore not wired into CI)",
            "traceparent": "in-process only (Wire D cross-mesh not yet implemented)",
        },
    }


if __name__ == "__main__":
    import json
    print(json.dumps(tiers_payload(), indent=2)[:400])
    r = route("prove the lambda boundedness lemma in Lean", [0.99] * 13,
              organ_context="theorem", traceparent="00-abc-def-01")
    print("route organ:", r["organ_routed"], "tier:", r["tier_used"], "Λ:", r["λ_signal"])
    r2 = route("detect prompt injection attack", [0.6] * 13, auto=True)
    print("auto organ:", r2["organ_routed"], "tier:", r2["tier_used"], "Λ:", r2["λ_signal"])
    assert len(TIERS) == 7
    assert r["organ_routed"] == "SUMAQ"
    print("OK — a11oy.code 7-tier router self-check passed.")
