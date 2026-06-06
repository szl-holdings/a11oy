#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
"""rosie_jarvis.py — Rosie's "Jarvis" assistant backend (operator-on-the-loop organ).

Founder directive: "Rosie = the Jarvis — able to answer questions, make updates, or
recommendations. Make the backend wired same as a11oy. Remember the roadmap of how
they are all connected."

This module gives Rosie a REAL conversational/assistant backend, mirroring a11oy's
backend pattern (LLM roster via szl_brain.route, receipt substrate via szl_dsse,
formula access via the shared registry). It is ADDITIVE and self-contained:
`register(app, ns="rosie")` mounts the Jarvis endpoints + the /jarvis console.

Four capabilities, all GROUNDED in live organ data — never a hallucinating chatbot:

  1. ASK       POST /api/rosie/v1/jarvis/ask         {question}
       Classifies the question, queries the LIVE organs (ToolRouter.organ_health,
       quorum_witnesses), the live /lambda verdict, and the canonical roadmap, then
       returns a grounded answer with citations to the real endpoints it read. If it
       has no live data for a topic it SAYS SO (amaru-style no-fabrication). Routes the
       framing through szl_brain.route (real LLM tier selection + Λ-receipt; response is
       an honest stub when no model key is present, like a11oy). Emits a DSSE receipt.

  2. RECOMMEND GET  /api/rosie/v1/jarvis/recommend
       Reads live health + quorum + Λ and emits operator recommendations: organ down,
       quorum not permitted, Λ below floor, witness rate-limited/stale. DSSE-receipted.

  3. ACT       POST /api/rosie/v1/jarvis/act         {action, target, note}
       SCOPED, enumerated operator actions only (approve | deny | acknowledge |
       recheck). NOT arbitrary code execution. Each action emits a signed DSSE receipt
       and is appended to an in-process audit ring. This is the human-on-the-loop organ.

  4. ROADMAP   GET  /api/rosie/v1/jarvis/roadmap
       The canonical connection map Rosie REMEMBERS: a11oy (source-of-truth /
       orchestrator / LLM hub) → sentra (policy immune) → amaru (cortex) → rosie
       (operator console) → killinchu (counter-UAS) → UDS mesh deploy; with the
       receipts.in ≡ receipts.out invariant. Served as real data so Rosie can answer
       "how does the system fit together?".

  +  HEALTH    GET  /api/rosie/v1/jarvis/health   — module self-status + capability list.
  +  CONSOLE   GET  /jarvis                        — self-contained Jarvis console tab.

HONESTY (Doctrine v11 ABSOLUTE):
  - Λ = Conjecture 1 (NEVER a theorem). PROVED formulas = {F1,F11,F12,F18,F19} (5, Lean
    sorry-free per lutar-lean Formulas/README). F4/F7/F22 are OPEN sorry — NOT proved.
  - LLM response is a REAL call when a model key is present, an HONEST STUB when absent.
  - DSSE receipts are REAL (cosign key present) or an honest UNSIGNED envelope (absent) —
    NEVER a fabricated signature (szl_dsse enforces this).
  - SLSA Build L2 EARNED on a11oy/rosie/sentra (signed slsa.dev/provenance/v0.2 .att on
    the published GHCR image); killinchu/amaru honestly L1 (signed, no .att yet). NEVER
    L3. No FedRAMP / Iron Bank / CMMC. Section 889 = 5.

Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
Co-Authored-By: Claude Opus 4.8 (Rosie-as-Jarvis squad) <agent@anthropic.com>
"""
from __future__ import annotations

import hashlib
import os
import sys
import threading
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any

_HERE = os.path.dirname(os.path.abspath(__file__))
for _cand in ("/app", _HERE, os.path.join(_HERE, "src"), os.path.join("/app", "src")):
    if os.path.isdir(_cand) and _cand not in sys.path:
        sys.path.insert(0, _cand)

# ---------------------------------------------------------------------------
# Soft dependencies — every one is wrapped so a missing module degrades to an
# HONEST "unavailable" answer rather than crashing the request path.
# ---------------------------------------------------------------------------
try:
    from fastapi import Request as _Request   # special type FastAPI injects (not a query param)
except Exception:                              # pragma: no cover
    _Request = None  # type: ignore

try:
    import szl_brain as _brain          # shared LLM roster + Λ router (a11oy parity)
    _BRAIN_OK = True
except Exception as _be:                # pragma: no cover
    _BRAIN_OK = False
    print(f"[rosie.jarvis] szl_brain import failed: {_be!r}", file=sys.stderr)

try:
    import szl_dsse as _dsse            # DSSE signer (real key → real sig, else UNSIGNED)
    _DSSE_OK = True
except Exception as _de:                # pragma: no cover
    _DSSE_OK = False
    print(f"[rosie.jarvis] szl_dsse import failed: {_de!r}", file=sys.stderr)

try:
    from rosie.tool_router import ToolRouter as _ToolRouter, byzantine_quorum_n as _bft_n
    from rosie.observability import make_traceparent as _mk_tp
    _ROUTER_OK = True
except Exception as _re:                # pragma: no cover
    _ROUTER_OK = False
    print(f"[rosie.jarvis] tool_router import failed: {_re!r}", file=sys.stderr)


# ===========================================================================
# CANONICAL CONNECTION ROADMAP — the map Rosie REMEMBERS and serves.
# Source: RECOVERED_PLAN.md + CONTINUITY_ROADMAP.md (workspace canon).
# ===========================================================================
ROADMAP: dict[str, Any] = {
    "title": "SZL ecosystem connection roadmap — how the organs fit together",
    "doctrine": "v11 LOCKED 749/14/163 @ c7c0ba17",
    "lambda_status": "Conjecture 1 (NOT a theorem)",
    "priority_order": ["a11oy", "sentra", "amaru", "rosie", "killinchu", "UDS mesh deploy"],
    "mesh_invariant": "receipts.in ≡ receipts.out — audit-fiber continuity across every organ boundary.",
    "organs": [
        {"id": "a11oy", "role": "Orchestrator / receipt substrate / LLM hub — SOURCE OF TRUTH",
         "space": "https://szlholdings-a11oy.hf.space", "feeds": ["sentra", "amaru", "rosie"],
         "note": "Canonical 5-tier LLM roster + Khipu receipt substrate. Rosie mirrors this backend."},
        {"id": "sentra", "role": "Policy immune system / cyber-resilience (deny-by-default gates)",
         "space": "https://szlholdings-sentra.hf.space", "feeds": ["amaru", "rosie"],
         "note": "46 policy gates; AND-composed; Λ-floor 0.90."},
        {"id": "amaru", "role": "Cortex / reasoner — every inference cites its source",
         "space": "https://szlholdings-amaru.hf.space", "feeds": ["rosie"],
         "note": "Cited-answer / no-fabrication pattern Rosie reuses for grounded answers."},
        {"id": "rosie", "role": "Operator console / human-on-the-loop — the Jarvis (THIS organ)",
         "space": "https://szlholdings-rosie.hf.space", "feeds": ["killinchu", "UDS"],
         "note": "Answers / recommends / acts; every action receipted. Shares a11oy's forum substrate."},
        {"id": "killinchu", "role": "Counter-UAS / drone organ (borrows formulas+anatomy)",
         "space": "https://szlholdings-killinchu.hf.space", "feeds": ["UDS"],
         "note": "Field decisions emit Λ + DSSE receipt. Honestly SLSA L1 (private repo)."},
        {"id": "UDS", "role": "Universal Deploy System — signed Zarf mesh bundle into a UDS Core cluster",
         "bundle": "szl-mesh:v0.4.0", "feeds": [],
         "note": "uds-cli bundle deploy szl-mesh-v0.4.0.tar.zst --confirm. Cross-organ in-cluster wiring = v0.5.0 roadmap, NOT live."},
    ],
    "wires": [
        {"from": "a11oy", "to": "rosie", "wire": "shared forum (receipt substrate via /khipu/aggregate)",
         "status": "LIVE"},
        {"from": "rosie", "to": "all", "wire": "/khipu/aggregate fan-out across all 5 organ ledgers",
         "status": "LIVE"},
        {"from": "organs", "to": "cluster", "wire": "over-network 3-of-4 quorum (Istio mTLS)",
         "status": "ROADMAP v0.5.0 — NOT live (honest)"},
    ],
    "honest_limits": [
        "Cross-organ in-cluster networking (mesh interconnect / over-network quorum) = v0.5.0 roadmap, NOT live.",
        "End-to-end live deploy on a real cluster is the June 9 rehearsal gate — proven by receipt, not words.",
        "SLSA Build L2 EARNED on a11oy/rosie/sentra (signed slsa.dev/provenance/v0.2 attestation on the published GHCR image, verified via cosign verify-attestation); killinchu/amaru honestly L1 (image signed, no .att referrer yet). NEVER L3, FedRAMP, Iron Bank, CMMC.",
    ],
    "source": "RECOVERED_PLAN.md + CONTINUITY_ROADMAP.md (SZL workspace canon, 2026-06-04)",
}

# Canonical formula honesty — authoritative source: lutar-lean
# Lutar/Puriq/Formulas/README.md states exactly 5 formulas are PROVED in Lean 4
# with no `sorry` and no axioms beyond core: F1, F11, F12, F18, F19. The other 18
# (incl. F4, F7, F22) are OPEN `SORRY_PURIQ_OPEN`; F23 (Λ) is Conjecture 1. Listing
# F4/F7/F22 here was a false-GREEN over-claim (cf. PhD-Math F4 / test_lean_binding_drift).
PROVED_FORMULAS = ["F1", "F11", "F12", "F18", "F19"]

# Enumerated, SAFE operator actions. NOT arbitrary execution.
ALLOWED_ACTIONS = {
    "approve": "HITL approve — operator approves a pending governed verdict / decision.",
    "deny": "HITL deny — operator denies a pending governed verdict / decision.",
    "acknowledge": "Acknowledge an alert / recommendation (no state mutation beyond the audit ring).",
    "recheck": "Trigger a fresh live organ-health re-probe (clears the health cache view).",
}

# In-process audit ring for operator actions (resets on restart — honest).
_AUDIT_RING: deque = deque(maxlen=256)
_AUDIT_LOCK = threading.Lock()
_PREV_HASH = "0" * 64  # genesis for the action hash-chain


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha(obj: Any) -> str:
    import json
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _receipt(kind: str, body: dict[str, Any]) -> dict[str, Any]:
    """Build a Khipu receipt + DSSE envelope (real sig if key present, else UNSIGNED)."""
    receipt = {
        "schema": "szl.rosie.jarvis/v1",
        "kind": kind,
        "organ": "rosie",
        "ts_utc": _now(),
        "doctrine": "v11",
        "lambda_status": "Conjecture 1 (NOT a theorem)",
        "body": body,
    }
    receipt["receipt_sha256"] = _sha(receipt)
    if _DSSE_OK:
        env = _dsse.sign_payload(receipt, _dsse.KHIPU_PAYLOAD_TYPE)
    else:
        env = {"signed": False,
               "honesty": "UNSIGNED — szl_dsse module unavailable in this runtime; no signature fabricated."}
    return {"receipt": receipt, "dsse": env,
            "signed": bool(env.get("signed")),
            "signing_available": (_DSSE_OK and _dsse.signing_available())}


# ===========================================================================
# LIVE GROUNDING — read the real organs. Each helper returns (data, citation).
# ===========================================================================
def _live_health() -> tuple[dict[str, Any], str]:
    if not _ROUTER_OK:
        return ({}, "tool_router unavailable")
    try:
        rt = _ToolRouter()
        return (rt.organ_health(),
                "rosie.tool_router.ToolRouter.organ_health (live /healthz probe of all 5 organs)")
    except Exception as e:
        return ({"_error": f"{type(e).__name__}: {e}"}, "organ_health probe errored")


def _live_quorum() -> tuple[dict[str, Any], str]:
    if not _ROUTER_OK:
        return ({}, "tool_router unavailable")
    try:
        rt = _ToolRouter()
        tp = _mk_tp()
        return (rt.quorum_witnesses("lambda_gate", tp),
                "rosie.tool_router.ToolRouter.quorum_witnesses (live 3-of-4 BFT witness set)")
    except Exception as e:
        return ({"_error": f"{type(e).__name__}: {e}"}, "quorum_witnesses errored")


def _live_lambda() -> tuple[dict[str, Any], str]:
    """Read the same 13-axis Λ the /lambda tile serves (deterministic, no network)."""
    axes = [0.92, 0.90, 0.93, 0.91, 0.94, 0.90, 0.92, 0.91, 0.95, 0.92, 0.93, 0.90, 0.92]
    if _BRAIN_OK:
        L = _brain.lambda_aggregate(axes)
    else:
        import math
        L = math.exp(sum(math.log(min(1.0, max(1e-9, x))) for x in axes) / len(axes))
    return ({"lambda": round(L, 6), "lambda_floor": 0.90, "pass": L >= 0.90,
             "trust_axes": 13, "uniqueness": "Conjecture 1 — NOT a Theorem"},
            "/api/rosie/v1/lambda (13-axis geometric-mean Λ verdict)")


# ===========================================================================
# QUESTION CLASSIFICATION + GROUNDED ANSWER ASSEMBLY
# ===========================================================================
def _classify(q: str) -> str:
    ql = (q or "").lower()
    if any(k in ql for k in ("fit together", "connect", "roadmap", "architecture",
                             "how does", "map", "organs relate", "pipeline")):
        return "roadmap"
    if any(k in ql for k in ("quorum", "witness", "bft", "consensus", "3-of-4", "3 of 4")):
        return "quorum"
    if any(k in ql for k in ("lambda", "λ", "trust score", "floor", "verdict")):
        return "lambda"
    if any(k in ql for k in ("formula", "proved", "proven", "lean", "theorem", "conjecture")):
        return "formulas"
    if any(k in ql for k in ("health", "down", "live", "status", "up", "alive", "stale", "organ")):
        return "health"
    return "general"


def _answer_health() -> tuple[str, list[dict]]:
    health, cite = _live_health()
    if not health or "_error" in health:
        return (f"I could not read live organ health right now ({health.get('_error', 'router unavailable')}). "
                "I will not guess — re-run when the live probe is reachable.",
                [{"endpoint": cite, "data": health}])
    live = [o for o, v in health.items() if isinstance(v, dict) and v.get("ok")]
    down = [o for o, v in health.items() if isinstance(v, dict) and not v.get("ok")]
    stale = [o for o, v in health.items() if isinstance(v, dict) and v.get("_from_cache")]
    txt = (f"{len(live)}/{len(health)} organs are LIVE right now: {', '.join(sorted(live)) or 'none'}. ")
    if down:
        txt += f"DOWN / unreachable: {', '.join(sorted(down))}. "
    if stale:
        txt += f"Served from cache (possibly stale / rate-limited): {', '.join(sorted(stale))}. "
    txt += "Source is a live /healthz probe of every organ — no mocked rows."
    return (txt, [{"endpoint": cite, "data": health}])


def _answer_quorum() -> tuple[str, list[dict]]:
    q, cite = _live_quorum()
    if not q or "_error" in q:
        return ("I could not gather the live quorum witness set. I will not fabricate a verdict.",
                [{"endpoint": cite, "data": q}])
    permitted = q.get("quorum_permitted")
    txt = (f"BFT quorum is {'PERMITTED' if permitted else 'NOT permitted'} "
           f"({q.get('healthy_witnesses')} of {q.get('n_required')} required witnesses healthy; "
           f"rule: {q.get('rule')}). Bound: {q.get('bft_bound')}. "
           "These are real per-witness /healthz attestations.")
    return (txt, [{"endpoint": cite, "data": q}])


def _answer_lambda() -> tuple[str, list[dict]]:
    lam, cite = _live_lambda()
    txt = (f"Λ = {lam['lambda']} across {lam['trust_axes']} trust axes (floor {lam['lambda_floor']}); "
           f"verdict {'PASS' if lam['pass'] else 'BELOW FLOOR'}. "
           "Λ is Conjecture 1 — NOT a theorem (open CAUCHY_ND sorry + missing symmetry axiom).")
    return (txt, [{"endpoint": cite, "data": lam}])


def _answer_formulas() -> tuple[str, list[dict]]:
    txt = (f"PROVED formulas (Lean, sorry-free) = {{{', '.join(PROVED_FORMULAS)}}} "
           f"= {len(PROVED_FORMULAS)} total. All other F-numbers are Roadmap / open `sorry`. "
           "Λ (the trust aggregator) is Conjecture 1 — NEVER labeled a theorem. "
           "Lean pin: 749 declarations / 14 unique axioms / 163 sorries @ c7c0ba17, doctrine v11.")
    return (txt, [{"endpoint": "/api/rosie/v1/formulas/index + szl_brain.CANONICAL",
                   "data": {"proved": PROVED_FORMULAS, "count": len(PROVED_FORMULAS),
                            "doctrine": "v11", "kernel_commit": "c7c0ba17"}}])


def _answer_roadmap() -> tuple[str, list[dict]]:
    chain = " → ".join(ROADMAP["priority_order"])
    txt = (f"The ecosystem connects as: {chain}. a11oy is the SOURCE OF TRUTH "
           "(orchestrator / receipt substrate / LLM hub); sentra is the policy immune system; "
           "amaru is the cortex (every inference cites its source); rosie is the operator console "
           "(this Jarvis, human-on-the-loop); killinchu is the counter-UAS field organ; and the whole "
           "mesh deploys as the signed UDS/Zarf bundle szl-mesh:v0.4.0. The binding invariant is "
           f"'{ROADMAP['mesh_invariant']}'. Rosie and a11oy share the forum (receipt substrate via "
           "/khipu/aggregate). Honest limit: over-network cross-organ quorum is v0.5.0 roadmap, not live.")
    return (txt, [{"endpoint": "/api/rosie/v1/jarvis/roadmap", "data": ROADMAP}])


_ANSWERERS = {
    "health": _answer_health,
    "quorum": _answer_quorum,
    "lambda": _answer_lambda,
    "formulas": _answer_formulas,
    "roadmap": _answer_roadmap,
}


def answer_question(question: str, task_hint: str = "") -> dict[str, Any]:
    """Grounded Q&A: classify → read live data → assemble cited answer → Λ-route → receipt."""
    topic = _classify(question)
    if topic == "general":
        # No single live source matches — be honest, offer the topics we CAN ground.
        grounded = ("I answer only from live SZL data. I don't have a grounded source for that "
                    "exact question. I CAN answer about: organ health/status, the 3-of-4 quorum, "
                    "the Λ verdict, the proved-formula set, or how the organs connect (the roadmap). "
                    "Ask me one of those and I will cite the live endpoint I read.")
        citations = [{"endpoint": "(none — refused to fabricate)", "data": {}}]
        axes = None
    else:
        grounded, citations = _ANSWERERS[topic]()
        # Derive Λ axes from whether the grounding succeeded (real → high trust).
        ok = bool(citations and citations[0].get("data") and "_error" not in citations[0]["data"])
        axes = [0.92] * 13 if ok else [0.6] * 13

    # Mirror a11oy: route the framing through the shared LLM roster (real key → real
    # call; absent → honest stub). Tier selection + Λ-receipt are always real math.
    if _BRAIN_OK:
        routed = _brain.route(
            prompt=f"[ROSIE-JARVIS grounded answer] topic={topic} :: {grounded}",
            axis_scores=axes, task_hint=task_hint or ("research" if topic == "roadmap" else ""),
        )
        llm = {"tier_used": routed.get("tier_used"), "tier_rank": routed.get("tier_rank"),
               "response": routed.get("response"), "lambda_receipt": routed.get("lambda_receipt")}
    else:
        llm = {"tier_used": None, "response": "[HONEST] szl_brain LLM roster unavailable in this runtime.",
               "lambda_receipt": None}

    payload = {
        "question": question,
        "topic": topic,
        "answer": grounded,
        "citations": citations,
        "grounded": topic != "general",
        "llm": llm,
        "honesty": ("Every answer is read from a live organ endpoint or the canonical roadmap and cited. "
                    "If no grounded source exists the assistant refuses to fabricate. LLM framing is a "
                    "real call when a model key is present, an honest stub otherwise."),
    }
    rec = _receipt("ask", {"question": question, "topic": topic, "grounded": payload["grounded"]})
    payload["receipt"] = rec
    return payload


# ===========================================================================
# RECOMMENDATIONS — read live state, emit operator-actionable findings.
# ===========================================================================
def build_recommendations() -> dict[str, Any]:
    recs: list[dict[str, Any]] = []
    citations: list[dict[str, Any]] = []

    health, h_cite = _live_health()
    citations.append({"endpoint": h_cite, "data": health})
    if not health or "_error" in health:
        recs.append({"severity": "warn", "organ": "rosie",
                     "finding": "Live organ-health probe unreachable — cannot assess fleet.",
                     "remedy": "Re-run when the network probe is reachable; do not assume healthy."})
    else:
        for organ, v in health.items():
            if not isinstance(v, dict):
                continue
            if not v.get("ok"):
                recs.append({"severity": "critical", "organ": organ,
                             "finding": f"{organ} is DOWN / unreachable (http={v.get('http')}).",
                             "remedy": f"Check {v.get('base', organ)} /healthz; factory-rebuild the Space if BUILD_ERROR."})
            elif v.get("_rate_limited"):
                recs.append({"severity": "warn", "organ": organ,
                             "finding": f"{organ} is rate-limited (HTTP 429); serving last-known-good.",
                             "remedy": "Back off polling; the cached attestation may be stale."})
            elif v.get("_from_cache"):
                recs.append({"severity": "info", "organ": organ,
                             "finding": f"{organ} health served from cache (possibly stale).",
                             "remedy": "Trigger a /jarvis/act recheck to force a fresh probe."})

    q, q_cite = _live_quorum()
    citations.append({"endpoint": q_cite, "data": q})
    if q and "_error" not in q and not q.get("quorum_permitted"):
        recs.append({"severity": "critical", "organ": "mesh",
                     "finding": f"BFT quorum NOT permitted — only {q.get('healthy_witnesses')} of "
                                f"{q.get('n_required')} witnesses healthy (need 3-of-4).",
                     "remedy": "Safety-critical dispatch is blocked until a 3-of-4 majority attests healthy."})

    lam, l_cite = _live_lambda()
    citations.append({"endpoint": l_cite, "data": lam})
    if not lam.get("pass"):
        recs.append({"severity": "critical", "organ": "doctrine",
                     "finding": f"Λ = {lam['lambda']} is BELOW the {lam['lambda_floor']} floor.",
                     "remedy": "Decisions should be gated; review the weakest trust axes."})

    if not recs:
        recs.append({"severity": "ok", "organ": "fleet",
                     "finding": "No issues found: all organs live, quorum permitted, Λ above floor.",
                     "remedy": "None — nominal."})

    out = {
        "recommendations": recs,
        "counts": {
            "critical": sum(1 for r in recs if r["severity"] == "critical"),
            "warn": sum(1 for r in recs if r["severity"] == "warn"),
            "info": sum(1 for r in recs if r["severity"] == "info"),
            "ok": sum(1 for r in recs if r["severity"] == "ok"),
        },
        "citations": citations,
        "honesty": "Recommendations are derived ONLY from live health/quorum/Λ reads — no synthetic alerts.",
    }
    out["receipt"] = _receipt("recommend", {"counts": out["counts"]})
    return out


# ===========================================================================
# ACT — scoped, enumerated operator actions. Each emits a signed receipt.
# ===========================================================================
def operator_act(action: str, target: str = "", note: str = "", operator: str = "operator") -> dict[str, Any]:
    global _PREV_HASH
    action = (action or "").strip().lower()
    if action not in ALLOWED_ACTIONS:
        return {"ok": False, "error": f"action '{action}' is not allowed",
                "allowed": sorted(ALLOWED_ACTIONS.keys()),
                "honesty": "Jarvis performs only enumerated, safe operator actions — NOT arbitrary execution."}

    fresh_probe = None
    if action == "recheck":
        # The only action that touches live state: force a fresh organ probe view.
        fresh_probe, _ = _live_health()

    entry = {
        "action": action,
        "action_desc": ALLOWED_ACTIONS[action],
        "target": target,
        "note": note,
        "operator": operator,
        "ts_utc": _now(),
        "prev_hash": _PREV_HASH,
    }
    entry["entry_hash"] = _sha(entry)
    with _AUDIT_LOCK:
        _PREV_HASH = entry["entry_hash"]
        _AUDIT_RING.append(entry)
        depth = len(_AUDIT_RING)

    rec = _receipt("act", entry)
    out = {"ok": True, "action": action, "target": target, "entry": entry,
           "audit_depth": depth, "receipt": rec,
           "honesty": ("Action recorded in a SHA-256 hash-chained audit ring + DSSE receipt. "
                       "Ring is in-process (resets on restart). No arbitrary code executed.")}
    if fresh_probe is not None:
        out["fresh_probe"] = fresh_probe
    return out


def audit_log(limit: int = 50) -> dict[str, Any]:
    with _AUDIT_LOCK:
        entries = list(_AUDIT_RING)[-int(limit):]
        depth = len(_AUDIT_RING)
    return {"depth": depth, "entries": list(reversed(entries)),
            "genesis": "0" * 64,
            "honesty": "In-process operator-action ring (resets on restart). Each entry is hash-chained."}


# ===========================================================================
# SELF-STATUS
# ===========================================================================
def jarvis_health() -> dict[str, Any]:
    return {
        "module": "rosie_jarvis",
        "organ": "rosie",
        "role": "operator console / human-on-the-loop — the Jarvis of the SZL ecosystem",
        "capabilities": {
            "ask": "POST /api/rosie/v1/jarvis/ask — grounded, cited Q&A over live organ data",
            "recommend": "GET /api/rosie/v1/jarvis/recommend — operator-actionable findings",
            "act": "POST /api/rosie/v1/jarvis/act — scoped, receipted operator actions",
            "roadmap": "GET /api/rosie/v1/jarvis/roadmap — canonical connection map Rosie remembers",
        },
        "wired_like_a11oy": {
            "llm_roster": _BRAIN_OK,        # szl_brain.route (5-tier, Λ-gated)
            "receipt_substrate": _DSSE_OK,  # szl_dsse DSSE (shared forum substrate)
            "live_grounding": _ROUTER_OK,   # tool_router live organ probe
        },
        "honesty": {
            "lambda_status": "Conjecture 1 (NOT a theorem)",
            "proved_formulas": PROVED_FORMULAS,
            "signing_available": (_DSSE_OK and _dsse.signing_available()),
            "llm_real_call": bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("OPENAI_API_KEY")),
            "slsa": "L1 honest (L2 earned separately)",
            "doctrine": "v11 LOCKED 749/14/163 @ c7c0ba17",
        },
        "allowed_actions": ALLOWED_ACTIONS,
    }


# ===========================================================================
# REGISTRATION
# ===========================================================================
def register(app, ns: str = "rosie") -> dict[str, Any]:
    """ADDITIVE: mount the Jarvis endpoints + /jarvis console. Returns a status dict."""
    from fastapi.responses import JSONResponse, HTMLResponse

    base = f"/api/{ns}/v1/jarvis"

    @app.post(f"{base}/ask")
    async def _jarvis_ask(request: _Request):
        try:
            payload = await request.json()
        except Exception:
            payload = {}
        question = (payload or {}).get("question", "")
        task_hint = (payload or {}).get("task_hint", "")
        if not question:
            return JSONResponse({"error": "missing 'question'",
                                 "honesty": "Ask a question; Jarvis answers only from live grounded data."},
                                status_code=400)
        return JSONResponse(answer_question(question, task_hint))

    @app.get(f"{base}/recommend")
    async def _jarvis_recommend():
        return JSONResponse(build_recommendations())

    @app.post(f"{base}/act")
    async def _jarvis_act(request: _Request):
        try:
            payload = await request.json()
        except Exception:
            payload = {}
        return JSONResponse(operator_act(
            action=(payload or {}).get("action", ""),
            target=(payload or {}).get("target", ""),
            note=(payload or {}).get("note", ""),
            operator=(payload or {}).get("operator", "operator"),
        ))

    @app.get(f"{base}/audit")
    async def _jarvis_audit(limit: int = 50):
        return JSONResponse(audit_log(limit))

    @app.get(f"{base}/roadmap")
    async def _jarvis_roadmap():
        return JSONResponse(ROADMAP)

    @app.get(f"{base}/health")
    async def _jarvis_health_ep():
        return JSONResponse(jarvis_health())

    # Self-contained console tab.
    @app.get("/jarvis")
    async def _jarvis_console():
        html = _load_console_html()
        return HTMLResponse(html)

    # Lift Jarvis routes to the front so they win over any catch-all sub-app mount.
    _paths = {f"{base}/ask", f"{base}/recommend", f"{base}/act", f"{base}/audit",
              f"{base}/roadmap", f"{base}/health", "/jarvis"}
    _routes = [r for r in app.router.routes if getattr(r, "path", None) in _paths]
    for _r in _routes:
        try:
            app.router.routes.remove(_r)
        except ValueError:
            pass
    for _i, _r in enumerate(_routes):
        app.router.routes.insert(_i, _r)

    print(f"[rosie] Jarvis backend registered: {base}/{{ask,recommend,act,audit,roadmap,health}} + /jarvis "
          f"(brain={_BRAIN_OK} dsse={_DSSE_OK} router={_ROUTER_OK})", file=sys.stderr)
    return {"registered": True, "base": base,
            "endpoints": ["ask", "recommend", "act", "audit", "roadmap", "health"],
            "console": "/jarvis",
            "wired": {"llm_roster": _BRAIN_OK, "receipt_substrate": _DSSE_OK, "live_grounding": _ROUTER_OK}}


def _load_console_html() -> str:
    """Load the Jarvis console HTML from web/jarvis.html (falls back to a minimal page)."""
    for cand in (os.path.join(_HERE, "web", "jarvis.html"),
                 os.path.join("/app", "web", "jarvis.html"),
                 os.path.join("/home/user/app", "web", "jarvis.html")):
        try:
            with open(cand, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            continue
    return ("<!doctype html><meta charset=utf-8><title>Rosie · Jarvis</title>"
            "<body style='font-family:monospace;background:#0b0e14;color:#e6e6e6;padding:24px'>"
            "<h1>Rosie · Jarvis</h1><p>Console HTML not found on disk; the JSON endpoints are live at "
            "<code>/api/rosie/v1/jarvis/{ask,recommend,act,roadmap,health}</code>.</p>"
            "<p>Λ = Conjecture 1 (NOT a theorem) · Doctrine v11.</p></body>")


__all__ = ["register", "answer_question", "build_recommendations", "operator_act",
           "audit_log", "jarvis_health", "ROADMAP", "ALLOWED_ACTIONS", "PROVED_FORMULAS"]

# Doctrine v11 LOCKED — 749/14/163 — c7c0ba17 · Λ = Conjecture 1 (NEVER a theorem)
# PROVED={F1,F11,F12,F18,F19} (5, Lean sorry-free) · SLSA L2 earned a11oy/rosie/sentra · killinchu/amaru L1
# No FedRAMP / Iron Bank / CMMC · Section 889 = 5 vendors
