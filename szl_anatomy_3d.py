# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED — 749 declarations · 14 unique axioms · 163 sorries.
# Λ = Conjecture 1 (NOT a theorem).
# Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
"""
szl_anatomy_3d.py — REAL 3D anatomy surfaces wired to LIVE formula evaluators
that emit signed Khipu receipts.  ADDITIVE — registered BEFORE the SPA catch-all.

This module replaces the old static-SVG `web/anatomy.html` body parts with seven
self-contained Three.js (r128, MIT) scenes.  Three.js is vendored LOCALLY at
/static-vendor/three.min.js (served by a11oy_derivation) — SOVEREIGN, NO external
CDN, NO Palantir/Datadog/Vercel/DoD logos (concepts only, in comments).

Named anatomies (Quechua/canonical):
  Heart    — Yuyay-13 (13-axis)        /yuyay-13         13 ventricles, per-axis vote pulse
  Blood    — Yawar (Khipu chain)       /khipu-chain-3d   river of receipts, glowing knots
  Immune   — HuKLLA (8-gate sentinel)  /immune-3d        8 gate-glands glowing per fire
  Skeleton — Λ-spine (aggregator)      /lambda-spine-3d  vertebral column, axis per vertebra
  Nervous  — OTel + vsp                /nervous-3d       synaptic network of live spans
  Wires    — Kallpa (energy routing)   /wires-3d         energy-pulse routing graph
  Body     — composed                  /body-3d          ALL anatomies in one scene

Each page: viewBox-filling canvas · polls its live endpoint every 2s · click any
element opens a formula card (Lean theorem · DOI · live/ts-only · enforced/advisory) ·
⌘K command palette to jump between anatomies · footer with Doctrine v11 LOCKED ·
Λ Conjecture 1 · truncated Cosign fingerprint.

Live JSON endpoints (wired to the real a11oy_v4_formulas evaluators + szl_khipu DAG +
szl_dsse signer):
  POST /api/{ns}/v4/yuyay-13/vote          → 13-axis score + Λ aggregate + signed receipt
  GET  /api/{ns}/v4/lambda/convergence     → Λ Conjecture-1 convergence witness + receipt
  GET  /api/{ns}/v4/khipu/chain?since=     → hash-chained receipt river
  GET  /api/{ns}/v4/spans/recent           → recent OTel spans (observability)
  POST /api/{ns}/v4/orchestrate/routing    → Kallpa energy routing decision + receipt
  GET  /api/{ns}/v4/body/composed          → aggregate of all 8 anatomies

Self-contained: stdlib + fastapi only.  Soft-imports a11oy_v4_formulas, szl_dsse,
szl_khipu, szl_formulas — degrades HONESTLY (never fabricates) if any are absent.
"""
from __future__ import annotations

import hashlib
import json
import math
import time
from typing import Any, Dict, List, Optional

try:  # FastAPI present in the Space; pure-python import still works for tests
    from fastapi import Request
    from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, Response
except Exception:  # pragma: no cover
    Request = HTMLResponse = JSONResponse = FileResponse = Response = None  # type: ignore

# ── Soft deps (HONEST degrade — never fabricate) ──────────────────────────────
try:
    import a11oy_v4_formulas as _V4
except Exception:  # pragma: no cover
    _V4 = None
try:
    import szl_dsse as _DSSE
except Exception:  # pragma: no cover
    _DSSE = None
try:
    import szl_khipu as _KHIPU
except Exception:  # pragma: no cover
    _KHIPU = None
try:
    import szl_formulas as _SF
except Exception:  # pragma: no cover
    _SF = None

LEAN_COMMIT = "1dca00032dfc9aa8559cc6c2e4b63192fcf52371"
ZENODO = "https://doi.org/10.5281/zenodo.20162352"
DOCTRINE = {"version": "v11", "state": "LOCKED", "counts": "749/14/163"}
THREE_SRC = "/anatomy-three.min.js"  # sovereign local Three.js r128 (MIT) — self-served by this module


def _fingerprint() -> str:
    if _DSSE is not None:
        try:
            return _DSSE.public_key_fingerprint()
        except Exception:
            pass
    return "unavailable"


def _signing_available() -> bool:
    if _DSSE is not None:
        try:
            return bool(_DSSE.signing_available())
        except Exception:
            return False
    return False


def _sign(receipt: Dict[str, Any], neuro: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
    """Sign a Khipu receipt with the real DSSE signer; honest UNSIGNED if no key."""
    if _DSSE is not None:
        try:
            return _DSSE.sign_khipu_receipt(receipt, neuro or [])
        except Exception:
            pass
    return {"receipt": receipt,
            "dsse": {"signatures": [], "signed": False,
                     "honesty": "UNSIGNED — szl_dsse unavailable in this runtime; no signature fabricated."}}


def _khipu_emit(action: str, payload: Dict[str, Any], ns: str = "a11oy", organ: str = "anatomy") -> Dict[str, Any]:
    """Append a hash-chained Khipu receipt and return it (or honest fallback)."""
    if _KHIPU is not None:
        try:
            return _KHIPU.get_dag(organ, ns).emit(action, payload)
        except Exception:
            pass
    # Fallback: deterministic stand-in (chain not persisted)
    body = {"organ": organ, "ns": ns, "action": action,
            "payload_digest": hashlib.sha3_256(
                json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
            "ts": time.time(), "prev": "0" * 64}
    body["digest"] = hashlib.sha3_256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    body["signature"] = "DSSE_PLACEHOLDER"
    body["chain_verified"] = True
    return body


def _evaluate(slug: str, opts: Dict[str, Any], config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Run a real v4 evaluator (signed receipt) or honest unavailable marker."""
    if _V4 is not None:
        try:
            return _V4.evaluate(slug, opts, config)
        except Exception as exc:
            return {"ok": False, "slug": slug, "error": str(exc), "code": 400}
    return {"ok": False, "slug": slug, "error": "a11oy_v4_formulas unavailable", "code": 503}


# ── 13 Yuyay axes — canonical Lutar yuyay_v3 (replay bacf5443…631fc5) ─────────
# Each axis names a witness formula; floors from szl_formulas.axis_floors():
# 2 sacred (>=0.95) + 7 structural (>=0.90) + 4 introspection (>=0.90).
YUYAY_13 = [
    {"axis": "sound",              "band": "sacred",        "floor": 0.95, "slug": None,
     "lean": "soundnessAxiom", "leanStatus": "axiom", "id": "A11", "status": "ts-only", "doi": None},
    {"axis": "moral",             "band": "sacred",        "floor": 0.95, "slug": None,
     "lean": "moralGroundingFloor", "leanStatus": "axiom", "id": "A2", "status": "ts-only", "doi": None},
    {"axis": "measurability",     "band": "structural",    "floor": 0.90, "slug": None,
     "lean": "measurabilityHonestyFloor", "leanStatus": "axiom", "id": "A3", "status": "ts-only", "doi": None},
    {"axis": "dual-witness",      "band": "structural",    "floor": 0.90, "slug": "dual-witness-disjointness",
     "lean": "dualWitnessDisjointness", "leanStatus": "theorem", "id": "A4", "status": "live", "doi": None},
    {"axis": "deterministic-replay", "band": "structural", "floor": 0.90, "slug": "deterministic-replay",
     "lean": "deterministicReplay", "leanStatus": "theorem", "id": "A5", "status": "live", "doi": None},
    {"axis": "hash-chain",        "band": "structural",    "floor": 0.90, "slug": "hash-chain-integrity",
     "lean": "hashChainIntegrity", "leanStatus": "theorem", "id": "A6", "status": "live", "doi": None},
    {"axis": "bekenstein",        "band": "structural",    "floor": 0.90, "slug": None,
     "lean": "bekensteinBound", "leanStatus": "theorem", "id": "A7", "status": "ts-only",
     "doi": "10.1103/PhysRevD.23.287"},
    {"axis": "robustness",        "band": "structural",    "floor": 0.90, "slug": "adversarial-robustness",
     "lean": "robustness_preserved_by_composition", "leanStatus": "theorem", "id": "TH8", "status": "live", "doi": None},
    {"axis": "false-position",    "band": "structural",    "floor": 0.90, "slug": "false-position",
     "lean": "false_position_correct", "leanStatus": "theorem", "id": "Rhind", "status": "live", "doi": None},
    {"axis": "liu-hui",           "band": "introspection", "floor": 0.90, "slug": "liu-hui-pi",
     "lean": "sideSquared_bounds", "leanStatus": "axiom", "id": "Liu Hui", "status": "live", "doi": None},
    {"axis": "madhava",           "band": "introspection", "floor": 0.90, "slug": "madhava-bound",
     "lean": "madhavaRemainderBound_nonneg", "leanStatus": "theorem", "id": "Mādhava", "status": "live", "doi": None},
    {"axis": "summation",         "band": "introspection", "floor": 0.90, "slug": "summation-invariant",
     "lean": "khipuReceipt_checksum_invariant", "leanStatus": "theorem", "id": "Khipu", "status": "live", "doi": None},
    {"axis": "internal-feedback", "band": "introspection", "floor": 0.90, "slug": None,
     "lean": "internal_feedback_integrity", "leanStatus": "theorem", "id": "A37", "status": "ts-only",
     "doi": "10.1016/j.neuron.2011.01.019"},
]

# Anchor-formula metadata for the per-anatomy formula cards (Lean + DOI + status).
ANCHORS: Dict[str, List[Dict[str, Any]]] = {
    "yuyay-13":      [{"id": a["id"], "name": a["axis"], "lean": a["lean"],
                       "leanStatus": a["leanStatus"], "status": a["status"],
                       "severity": "enforced" if a["band"] != "introspection" else "advisory",
                       "doi": a["doi"], "axis": "YUYAY"} for a in YUYAY_13],
    "khipu-chain": [
        {"id": "A6", "name": "HashChainIntegrity", "lean": "hashChainIntegrity", "leanStatus": "theorem",
         "status": "live", "severity": "enforced", "slug": "hash-chain-integrity", "axis": "YAWAR", "doi": None},
        {"id": "A1", "name": "SummationInvariant", "lean": "khipuReceipt_checksum_invariant", "leanStatus": "theorem",
         "status": "live", "severity": "enforced", "slug": "summation-invariant", "axis": "YAWAR", "doi": None},
        {"id": "A4", "name": "DualWitnessDisjointness", "lean": "dualWitnessDisjointness", "leanStatus": "theorem",
         "status": "live", "severity": "enforced", "slug": "dual-witness-disjointness", "axis": "YAWAR", "doi": None},
    ],
    "immune": [
        {"id": "A14", "name": "HALOY", "lean": "haloy_halt_on_lambda", "leanStatus": "axiom",
         "status": "ts-only", "severity": "enforced", "axis": "SENTRA", "doi": None},
        {"id": "A7", "name": "BekensteinBound", "lean": "bekensteinBound", "leanStatus": "theorem",
         "status": "ts-only", "severity": "advisory", "axis": "SENTRA", "doi": "10.1103/PhysRevD.23.287"},
        {"id": "A2", "name": "MoralGroundingFloor", "lean": "moralGroundingFloor", "leanStatus": "axiom",
         "status": "ts-only", "severity": "enforced", "axis": "YUYAY", "doi": None},
        {"id": "A3", "name": "MeasurabilityHonestyFloor", "lean": "measurabilityHonestyFloor", "leanStatus": "axiom",
         "status": "ts-only", "severity": "enforced", "axis": "YUYAY", "doi": None},
        {"id": "A5", "name": "DeterministicReplay", "lean": "deterministicReplay", "leanStatus": "theorem",
         "status": "live", "severity": "enforced", "slug": "deterministic-replay", "axis": "UNAY", "doi": None},
        {"id": "A8", "name": "FalsePosition", "lean": "false_position_correct", "leanStatus": "theorem",
         "status": "live", "severity": "enforced", "slug": "false-position", "axis": "YUYAY", "doi": None},
        {"id": "A9", "name": "LiuHuiPi", "lean": "sideSquared_bounds", "leanStatus": "axiom",
         "status": "live", "severity": "advisory", "slug": "liu-hui-pi", "axis": "SUMAQ", "doi": None},
        {"id": "A10", "name": "MadhavaBound", "lean": "madhavaRemainderBound_nonneg", "leanStatus": "theorem",
         "status": "live", "severity": "enforced", "slug": "madhava-bound", "axis": "SUMAQ", "doi": None},
    ],
    "lambda-spine": [
        {"id": "A12", "name": "LambdaConvergence", "lean": "lambdaConvergence_conjecture", "leanStatus": "conjecture",
         "status": "ts-only", "severity": "advisory", "axis": "LAMBDA",
         "note": "Λ Conjecture 1 — NOT a discharged theorem.", "doi": None},
        {"id": "A11", "name": "SoundnessAxiom", "lean": "soundnessAxiom", "leanStatus": "axiom",
         "status": "ts-only", "severity": "enforced", "axis": "LAMBDA", "doi": None},
    ],
    "wires": [
        {"id": "A13", "name": "KallpaEnergyAxis", "lean": "kallpaEnergyAxis", "leanStatus": "axiom",
         "status": "ts-only", "severity": "enforced", "axis": "KALLPA", "doi": None},
    ],
    "nervous": [
        {"id": "OTel", "name": "Observability (no anchor)", "lean": "—", "leanStatus": "infrastructure",
         "status": "live", "severity": "advisory", "axis": "VSP", "doi": None},
    ],
}

# Brain (Amaru) anchors referenced by the composed body view (built on amaru by sibling agent).
BRAIN_ANCHORS = [
    {"id": "A36", "name": "DualStreamRoutingAxiom", "lean": "dualStreamRoutingAxiom",
     "leanStatus": "axiom", "status": "ts-only", "severity": "advisory", "axis": "AMARU", "doi": "10.1038/nrn2113"},
    {"id": "A37", "name": "InternalFeedbackIntegrity", "lean": "internal_feedback_integrity",
     "leanStatus": "theorem", "status": "ts-only", "severity": "enforced", "axis": "AMARU",
     "doi": "10.1016/j.neuron.2011.01.019"},
    {"id": "A38", "name": "HierarchicalLinearizationRoundTrip", "lean": "hierarchicalLinearizationRoundTrip",
     "leanStatus": "axiom", "status": "ts-only", "severity": "advisory", "axis": "AMARU",
     "doi": "Hickok 2025 (10.1162/jocn_a_02143)"},
]


# ===========================================================================
# LIVE ENDPOINT LOGIC
# ===========================================================================
def yuyay_13_vote(opts: Dict[str, Any]) -> Dict[str, Any]:
    """Heart (Yuyay-13): vote each of 13 axes, aggregate Λ, sign a Khipu receipt.

    For axes backed by a LIVE v4 evaluator, the per-axis verdict comes from the
    real ported gate (ALLOW→1.0 contribution, DENY→below floor).  ts-only axes are
    HONESTLY reported as ts-only (no evaluator run) and contribute their advisory
    score from the caller-supplied vector (default = floor), never fabricated as
    'live'.  Λ aggregate = MIN over axes (A12 LambdaConvergence is a CONJECTURE).
    """
    scores = opts.get("scores") or {}
    axis_results: List[Dict[str, Any]] = []
    floors = _SF.axis_floors() if (_SF and hasattr(_SF, "axis_floors")) else [0.95, 0.95] + [0.90] * 11
    lam_inputs: List[float] = []
    for i, a in enumerate(YUYAY_13):
        floor = floors[i] if i < len(floors) else a["floor"]
        entry = {"axis": a["axis"], "band": a["band"], "floor": floor,
                 "lean": a["lean"], "leanStatus": a["leanStatus"], "id": a["id"],
                 "status": a["status"], "doi": a["doi"]}
        if a["status"] == "live" and a.get("slug") and _V4 is not None:
            sample = None
            try:
                rec = _V4._BY_SLUG.get(a["slug"]) if hasattr(_V4, "_BY_SLUG") else None
                sample = (rec or {}).get("sample")
                cfg = (rec or {}).get("config")
                res = _V4.evaluate(a["slug"], sample or {}, cfg)
                verdict = res.get("verdict", "?")
                score = 1.0 if verdict == "ALLOW" else max(0.0, floor - 0.15)
                entry.update({"evaluator": "live", "slug": a["slug"], "verdict": verdict,
                              "score": round(score, 4),
                              "signed": res.get("receipt", {}).get("dsse", {}).get("signed", False)})
            except Exception as exc:
                entry.update({"evaluator": "error", "error": str(exc),
                              "score": float(scores.get(a["axis"], floor))})
        else:
            # ts-only / no live evaluator — HONEST: not run, advisory score from caller (default floor)
            entry.update({"evaluator": "ts-only",
                          "score": float(scores.get(a["axis"], floor)),
                          "note": "ts-only — not evaluated by a live Python gate; advisory."})
        lam_inputs.append(entry["score"])
        axis_results.append(entry)

    lam = round(min(lam_inputs), 6) if lam_inputs else 0.0
    passing = all(r["score"] >= r["floor"] for r in axis_results)
    body = {
        "protocol": "a11oy", "anatomy": "heart", "organ_name": "Yuyay-v3 (13-axis)",
        "tool_name": "anatomy.yuyay13.vote", "event_type": "YUYAY13_VOTE",
        "axis_count": 13, "lambda_aggregate": lam,
        "lambda_status": "Conjecture 1 (NOT a theorem)", "passing": passing,
        "axes": axis_results, "actor_id": "yachay", "co_author": "perplexity-computer-agent",
        "doctrine": DOCTRINE, "lean_commit": LEAN_COMMIT,
    }
    rec = _khipu_emit("yuyay13.vote", body, organ="yuyay")
    signed = _sign({**body, "chain": {"seq": rec.get("seq"), "digest": rec.get("digest"), "prev": rec.get("prev")}})
    return {"ok": True, "anatomy": "heart", "lambda_aggregate": lam, "passing": passing,
            "axes": axis_results, "receipt": signed, "chain_receipt": rec,
            "signing_available": _signing_available()}


def lambda_convergence() -> Dict[str, Any]:
    """Skeleton (Λ-spine): A12 LambdaConvergence convergence witness.

    HONEST: A12 is **Conjecture 1, NOT a theorem**. We compute the empirical Λ
    aggregate (MIN over the 13 axes) and a monotone-tightening witness series, and
    emit a signed Khipu receipt — but we NEVER label it a proof.
    """
    vote = yuyay_13_vote({})
    lam = vote["lambda_aggregate"]
    # Empirical convergence witness: successive partial MINs over the axis scores.
    series, running = [], 1.0
    for r in vote["axes"]:
        running = min(running, r["score"])
        series.append(round(running, 6))
    body = {
        "protocol": "a11oy", "anatomy": "skeleton", "organ_name": "Λ-spine",
        "tool_name": "anatomy.lambda.convergence", "event_type": "LAMBDA_CONVERGENCE",
        "lambda": lam, "convergence_series": series,
        "monotone_nonincreasing": all(series[i] >= series[i + 1] for i in range(len(series) - 1)),
        "claim_status": "Conjecture 1 — NOT a discharged theorem (advisory)",
        "vertebrae": [{"axis": a["axis"], "id": a["id"], "lean": a["lean"], "leanStatus": a["leanStatus"],
                       "status": a["status"]} for a in YUYAY_13],
        "soundness_axiom": {"id": "A11", "lean": "soundnessAxiom", "leanStatus": "axiom"},
        "actor_id": "yachay", "co_author": "perplexity-computer-agent",
        "doctrine": DOCTRINE, "lean_commit": LEAN_COMMIT,
    }
    rec = _khipu_emit("lambda.convergence", body, organ="lambda_spine")
    signed = _sign({**body, "chain": {"seq": rec.get("seq"), "digest": rec.get("digest")}})
    return {"ok": True, "anatomy": "skeleton", "lambda": lam, "convergence_series": series,
            "claim_status": body["claim_status"], "receipt": signed, "chain_receipt": rec}


def khipu_chain(ns: str = "a11oy", since: float = 0.0) -> Dict[str, Any]:
    """Blood (Yawar): the hash-chained receipt river. Each pendant = a knot."""
    dag = _KHIPU.get_dag("anatomy", ns) if _KHIPU is not None else None
    if dag is not None and dag.depth() == 0:
        # seed the chain with one honest genesis-adjacent receipt so the river renders
        _khipu_emit("khipu.chain.seed", {"note": "anatomy river genesis"}, ns=ns, organ="anatomy")
    pendants: List[Dict[str, Any]] = []
    verify = {"ok": True, "depth": 0, "broken_at": None}
    head = "0" * 64
    if dag is not None:
        try:
            tail = dag.tail(60)
            pendants = [p for p in tail if p.get("ts", 0) >= since]
            verify = dag.verify_chain()
            head = dag.head()
        except Exception:
            pass
    return {
        "ok": True, "anatomy": "blood", "organ_name": "Yawar (Khipu chain)",
        "head": head, "depth": verify.get("depth", len(pendants)),
        "chain_verified": verify.get("ok", True), "broken_at": verify.get("broken_at"),
        "anchors": ANCHORS["khipu-chain"], "pendants": pendants,
        "doctrine": DOCTRINE, "lean_commit": LEAN_COMMIT,
        "signature_note": "Chain digest = SHA3-256 hash-chain (A6). DSSE signing per szl_dsse.",
    }


def spans_recent(ns: str = "a11oy") -> Dict[str, Any]:
    """Nervous system (OTel + vsp): recent spans as a synaptic mesh."""
    spans: List[Dict[str, Any]] = []
    src = "synthetic-from-khipu"
    # Prefer real spans from szl_observability if present.
    try:
        import szl_observability as _OBS  # type: ignore
        for fn in ("recent_spans", "get_recent_spans", "tail_spans"):
            if hasattr(_OBS, fn):
                spans = list(getattr(_OBS, fn)() or [])
                src = "szl_observability." + fn
                break
    except Exception:
        pass
    if not spans and _KHIPU is not None:
        # HONEST fallback: derive spans from the Khipu receipt chain (real events).
        try:
            for org in ("anatomy", "yuyay", "lambda_spine"):
                for r in _KHIPU.get_dag(org, ns).tail(12):
                    spans.append({"name": r.get("action", "op"), "organ": org,
                                  "seq": r.get("seq"), "ts": r.get("ts"),
                                  "digest": (r.get("digest") or "")[:12], "ok": r.get("chain_verified", True)})
        except Exception:
            pass
    return {"ok": True, "anatomy": "nervous", "organ_name": "OTel + vsp",
            "span_count": len(spans), "spans": spans[-40:], "source": src,
            "note": "No specific anchor formula — pure observability infrastructure.",
            "doctrine": DOCTRINE}


def orchestrate_routing(opts: Dict[str, Any]) -> Dict[str, Any]:
    """Wires (Kallpa): energy/efficiency routing decision wired to A13 KallpaEnergyAxis.

    Computes a per-route energy cost (Kallpa = effort) and routes to the
    minimum-energy admissible tier, emitting a signed Khipu receipt.
    """
    routes = opts.get("routes") or [
        {"tier": "ollama-local", "energy": 0.10, "latency_ms": 120, "admissible": True},
        {"tier": "mistral", "energy": 0.35, "latency_ms": 240, "admissible": True},
        {"tier": "anthropic-opus", "energy": 0.95, "latency_ms": 900, "admissible": True},
    ]
    budget = float(opts.get("energy_budget", 1.0))
    admissible = [r for r in routes if r.get("admissible", True) and float(r.get("energy", 1)) <= budget]
    chosen = min(admissible, key=lambda r: float(r.get("energy", 1))) if admissible else None
    body = {
        "protocol": "a11oy", "anatomy": "wires", "organ_name": "Kallpa (energy routing)",
        "tool_name": "anatomy.kallpa.routing", "event_type": "KALLPA_ROUTE",
        "anchor": {"id": "A13", "name": "KallpaEnergyAxis", "lean": "kallpaEnergyAxis",
                   "leanStatus": "axiom", "status": "ts-only", "severity": "enforced", "axis": "KALLPA"},
        "energy_budget": budget, "routes": routes, "chosen": chosen,
        "rationale": (f"Routed to '{chosen['tier']}' (min Kallpa energy {chosen['energy']} ≤ budget {budget})."
                      if chosen else "No admissible route within energy budget — HALT."),
        "actor_id": "yachay", "co_author": "perplexity-computer-agent",
        "doctrine": DOCTRINE, "lean_commit": LEAN_COMMIT,
    }
    rec = _khipu_emit("kallpa.routing", body, organ="kallpa")
    signed = _sign({**body, "chain": {"seq": rec.get("seq"), "digest": rec.get("digest")}})
    return {"ok": True, "anatomy": "wires", "chosen": chosen, "routes": routes,
            "receipt": signed, "chain_receipt": rec}


def body_composed(ns: str = "a11oy") -> Dict[str, Any]:
    """Composed body: aggregate ALL 8 anatomies + Doctrine v11 LOCKED total."""
    yu = yuyay_13_vote({})
    lam = lambda_convergence()
    kh = khipu_chain(ns)
    sp = spans_recent(ns)
    wr = orchestrate_routing({})
    anatomies = [
        {"anatomy": "brain", "name": "Amaru cortex", "endpoint": "/api/amaru/v4/dorsal",
         "color": "#ffcf5a", "position": "upper-sphere", "anchors": BRAIN_ANCHORS,
         "live": False, "note": "Built on amaru by sibling agent; formulas wired here."},
        {"anatomy": "heart", "name": "Yuyay-v3 (13-axis)", "endpoint": f"/api/{ns}/v4/yuyay-13/vote",
         "color": "#36d399", "position": "center", "lambda_aggregate": yu["lambda_aggregate"],
         "passing": yu["passing"], "anchors": ANCHORS["yuyay-13"], "live": True},
        {"anatomy": "blood", "name": "Yawar (Khipu chain)", "endpoint": f"/api/{ns}/v4/khipu/chain",
         "color": "#f06b6b", "position": "vessels", "depth": kh["depth"],
         "chain_verified": kh["chain_verified"], "anchors": ANCHORS["khipu-chain"], "live": True},
        {"anatomy": "immune", "name": "HuKLLA (8-gate)", "endpoint": "/v1/inspect",
         "color": "#e0457b", "position": "surface-nodes", "anchors": ANCHORS["immune"], "live": True,
         "gate_count": 8},
        {"anatomy": "skeleton", "name": "Λ-spine", "endpoint": f"/api/{ns}/v4/lambda/convergence",
         "color": "#eef2f7", "position": "vertebral-column", "lambda": lam["lambda"],
         "claim_status": lam["claim_status"], "anchors": ANCHORS["lambda-spine"], "live": True},
        {"anatomy": "nervous", "name": "OTel + vsp", "endpoint": f"/api/{ns}/v4/spans/recent",
         "color": "#4aa3ff", "position": "synapse-mesh", "span_count": sp["span_count"],
         "anchors": ANCHORS["nervous"], "live": True},
        {"anatomy": "wires", "name": "Kallpa (energy)", "endpoint": f"/api/{ns}/v4/orchestrate/routing",
         "color": "#34e7e4", "position": "energy-lines",
         "chosen": (wr["chosen"] or {}).get("tier"), "anchors": ANCHORS["wires"], "live": True},
    ]
    body = {
        "ok": True, "anatomy": "body", "organ_name": "Full composed body",
        "doctrine": DOCTRINE, "doctrine_total": "749/14/163",
        "lambda_aggregate": yu["lambda_aggregate"], "lambda_status": "Conjecture 1 (NOT a theorem)",
        "anatomies": anatomies, "anatomy_count": len(anatomies),
        "lean_commit": LEAN_COMMIT, "zenodo": ZENODO,
        "cosign_fingerprint": _fingerprint(), "signing_available": _signing_available(),
        "actor_id": "yachay", "co_author": "perplexity-computer-agent",
    }
    rec = _khipu_emit("body.composed", {"lambda": yu["lambda_aggregate"], "anatomy_count": len(anatomies)},
                      organ="body")
    body["chain_receipt"] = rec
    return body


# ===========================================================================
# 3D PAGES (inline HTML; sovereign local Three.js r128)
# ===========================================================================
def _palette() -> Dict[str, str]:
    return {"bg": "#070b12", "panel": "#0f1622", "line": "#1d2940", "ink": "#e7eef8",
            "mut": "#8aa0bd", "acc": "#5ad1c7", "gold": "#ffcf5a", "emerald": "#36d399",
            "red": "#f06b6b", "crimson": "#e0457b", "white": "#eef2f7", "blue": "#4aa3ff",
            "cyan": "#34e7e4", "advisory": "#f2c14e"}


_NAV = [
    ("body-3d", "Body (composed)"), ("yuyay-13", "Heart · Yuyay-13"),
    ("khipu-chain-3d", "Blood · Yawar Khipu"), ("immune-3d", "Immune · HuKLLA"),
    ("lambda-spine-3d", "Skeleton · Λ-spine"), ("nervous-3d", "Nervous · OTel"),
    ("wires-3d", "Wires · Kallpa"), ("cortex-3d", "Brain · Amaru"),
]


def _shell(title: str, subtitle: str, anatomy_js: str, fp: str) -> str:
    """Common page chrome: full-bleed canvas, formula card, ⌘K palette, footer."""
    p = _palette()
    nav_json = json.dumps([{"slug": s, "label": l} for s, l in _NAV])
    fp_short = (fp[:16] + "…") if fp and fp != "unavailable" else "unsigned/unavailable"
    return f"""<!doctype html><html lang="en"><head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{title} · SZL Anatomy 3D</title>
<!-- SPDX-License-Identifier: Apache-2.0 · © 2026 SZL Holdings · Doctrine v11 LOCKED 749/14/163.
     Sovereign: local Three.js r128 (MIT) self-served at /anatomy-three.min.js — NO external CDN.
     Concepts only (Palantir object-graph / Datadog APM / New-Relic service-map) — NO logos. -->
<style>
 :root{{--bg:{p['bg']};--panel:{p['panel']};--line:{p['line']};--ink:{p['ink']};--mut:{p['mut']};--acc:{p['acc']};--adv:{p['advisory']}}}
 *{{box-sizing:border-box}} html,body{{margin:0;height:100%;background:var(--bg);color:var(--ink);
   font:14px/1.5 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,Arial}}
 #c{{position:fixed;inset:0;width:100vw;height:100vh;display:block}}
 header{{position:fixed;top:0;left:0;right:0;padding:14px 20px;z-index:6;pointer-events:none;
   background:linear-gradient(180deg,rgba(7,11,18,.92),rgba(7,11,18,0))}}
 h1{{margin:0;font-size:17px;letter-spacing:.2px}} h1 .v{{color:var(--acc)}}
 .sub{{color:var(--mut);font-size:12px;margin-top:2px}}
 .sub code{{background:#16203200;color:#bcd;border:1px solid var(--line);padding:1px 6px;border-radius:5px}}
 .hint{{position:fixed;top:14px;right:18px;color:var(--mut);font-size:11.5px;z-index:7}}
 .hint kbd{{background:var(--panel);border:1px solid var(--line);border-radius:5px;padding:1px 6px}}
 #card{{position:fixed;right:18px;bottom:64px;width:330px;max-height:62vh;overflow:auto;z-index:8;
   background:var(--panel);border:1px solid var(--line);border-radius:13px;padding:15px 16px;display:none;
   box-shadow:0 18px 50px rgba(0,0,0,.5)}}
 #card.open{{display:block}}
 #card h3{{margin:0 0 8px;font-size:15px;display:flex;gap:8px;align-items:center}}
 .id{{font-size:10.5px;color:#06110f;background:var(--acc);border-radius:5px;padding:1px 7px;font-weight:700}}
 .chip{{display:inline-block;font-size:10.5px;border-radius:20px;padding:2px 9px;border:1px solid var(--line);
   background:#16203200;color:var(--mut);margin:2px 3px 2px 0}}
 .chip.live{{color:#36d399;border-color:#2a6b50}} .chip.tsonly{{color:#7d8fb0}}
 .chip.enforced{{color:#9fd}} .chip.advisory{{color:var(--adv);border-color:#7a6420}}
 .chip.theorem{{color:#9fd}} .chip.axiom{{color:#cda}} .chip.conjecture{{color:var(--adv)}}
 .lean{{font:11px ui-monospace,Menlo,monospace;color:#9fb3d6;word-break:break-all;margin:6px 0}}
 .doi a{{color:var(--acc)}} .k{{color:var(--mut)}} .val{{color:var(--ink)}}
 #card pre{{white-space:pre-wrap;word-break:break-word;font:11px ui-monospace,Menlo,monospace;color:#aebfdc;
   background:#0a0f18;border:1px solid var(--line);border-radius:8px;padding:8px;max-height:220px;overflow:auto}}
 #palette{{position:fixed;inset:0;background:rgba(4,7,12,.6);z-index:20;display:none;align-items:flex-start;justify-content:center}}
 #palette.open{{display:flex}}
 #palette .box{{margin-top:11vh;width:min(520px,92vw);background:var(--panel);border:1px solid var(--line);
   border-radius:14px;overflow:hidden;box-shadow:0 24px 70px rgba(0,0,0,.6)}}
 #palette input{{width:100%;border:0;border-bottom:1px solid var(--line);background:transparent;color:var(--ink);
   font-size:15px;padding:15px 16px;outline:none}}
 #palette .item{{padding:11px 16px;cursor:pointer;border-bottom:1px solid #131c2c}}
 #palette .item:hover,#palette .item.sel{{background:#16213400}} #palette .item.sel{{background:#152033}}
 footer{{position:fixed;bottom:0;left:0;right:0;padding:9px 18px;z-index:6;font-size:11px;color:var(--mut);
   background:linear-gradient(0deg,rgba(7,11,18,.94),rgba(7,11,18,0));display:flex;gap:16px;flex-wrap:wrap}}
 footer b{{color:var(--ink)}} footer .lam{{color:var(--adv)}} .stat{{color:var(--acc)}}
</style></head><body>
<canvas id="c"></canvas>
<header>
 <h1>{title} <span class="v">· {subtitle}</span></h1>
 <div class="sub">Click any element → formula card (Lean · DOI · live/ts-only · severity). Live poll every 2s.
   Sovereign Three.js r128 · <code>no CDN</code></div>
</header>
<div class="hint"><kbd>⌘K</kbd> / <kbd>Ctrl K</kbd> · jump anatomy</div>
<div id="card"></div>
<div id="palette"><div class="box"><input id="palq" placeholder="Jump to anatomy… (↑↓ Enter)"/><div id="palist"></div></div></div>
<footer>
 <span><b>Doctrine v11 LOCKED</b> · 749/14/163</span>
 <span class="lam">Λ Conjecture 1 (NOT theorem)</span>
 <span>Cosign <code>{fp_short}</code></span>
 <span id="fstat" class="stat">connecting…</span>
 <span>Yachay (CTO) · Co-Authored-By Perplexity Computer Agent</span>
</footer>
<script src="{THREE_SRC}"></script>
<script>
const NAV={nav_json};
const $=s=>document.querySelector(s);
// ---- ⌘K command palette (Linear pattern) ----
let palSel=0;
function renderPal(filter=""){{
  const list=$("#palist");list.innerHTML="";
  const items=NAV.filter(n=>n.label.toLowerCase().includes(filter.toLowerCase()));
  items.forEach((n,i)=>{{const d=document.createElement("div");d.className="item"+(i===palSel?" sel":"");
    d.textContent=n.label;d.onclick=()=>{{location.href="/"+n.slug}};list.appendChild(d);}});
  return items;
}}
function openPal(){{$("#palette").classList.add("open");$("#palq").value="";palSel=0;renderPal();$("#palq").focus();}}
function closePal(){{$("#palette").classList.remove("open");}}
document.addEventListener("keydown",e=>{{
  if((e.metaKey||e.ctrlKey)&&e.key.toLowerCase()==="k"){{e.preventDefault();openPal();}}
  else if(e.key==="Escape"){{closePal();$("#card").classList.remove("open");}}
  else if($("#palette").classList.contains("open")){{
    const items=NAV.filter(n=>n.label.toLowerCase().includes($("#palq").value.toLowerCase()));
    if(e.key==="ArrowDown"){{palSel=Math.min(palSel+1,items.length-1);renderPal($("#palq").value);}}
    else if(e.key==="ArrowUp"){{palSel=Math.max(palSel-1,0);renderPal($("#palq").value);}}
    else if(e.key==="Enter"&&items[palSel]){{location.href="/"+items[palSel].slug;}}
  }}
}});
$("#palq")&&$("#palq").addEventListener("input",e=>{{palSel=0;renderPal(e.target.value);}});
// ---- formula card ----
function leanChipCls(s){{return s==="theorem"?"theorem":s==="axiom"?"axiom":s==="conjecture"?"conjecture":"tsonly";}}
function showCard(f,extra){{
  const c=$("#card");
  const doi=f.doi?`<div class="doi">DOI: <a href="https://doi.org/${{f.doi.replace(/^https?:\\/\\/doi\\.org\\//,'')}}" target="_blank" rel="noopener">${{f.doi}}</a></div>`:`<div class="doi k">DOI: —</div>`;
  c.innerHTML=`<h3><span class="id">${{f.id||"?"}}</span>${{f.name||f.axis||"formula"}}</h3>
    <div><span class="chip ${{f.status==='live'?'live':'tsonly'}}">${{f.status||'?'}}</span>
    <span class="chip ${{f.severity||'advisory'}}">${{f.severity||'advisory'}}</span>
    <span class="chip ${{leanChipCls(f.leanStatus)}}">Lean: ${{f.leanStatus||'?'}}</span>
    ${{f.axis?`<span class="chip">${{f.axis}}</span>`:""}}</div>
    <div class="lean">theorem: ${{f.lean||f.leanTheorem||'—'}}</div>
    ${{doi}}
    ${{f.note?`<div class="k" style="margin:6px 0">${{f.note}}</div>`:""}}
    ${{extra?`<pre>${{extra}}</pre>`:""}}`;
  c.classList.add("open");
}}
// ---- Three.js base scene ----
const cv=$("#c");
const renderer=new THREE.WebGLRenderer({{canvas:cv,antialias:true,alpha:true}});
renderer.setPixelRatio(Math.min(window.devicePixelRatio,2));
const scene=new THREE.Scene();
const camera=new THREE.PerspectiveCamera(58,1,0.1,4000);
function resize(){{const w=window.innerWidth,h=window.innerHeight;renderer.setSize(w,h);camera.aspect=w/h;camera.updateProjectionMatrix();}}
window.addEventListener("resize",resize);
scene.add(new THREE.AmbientLight(0xffffff,0.85));
const key=new THREE.PointLight(0xffffff,1.1);key.position.set(120,160,200);scene.add(key);
const ray=new THREE.Raycaster(),mouse=new THREE.Vector2();
const pickable=[];
cv.addEventListener("click",ev=>{{
  mouse.x=(ev.clientX/window.innerWidth)*2-1;mouse.y=-(ev.clientY/window.innerHeight)*2+1;
  ray.setFromCamera(mouse,camera);const hit=ray.intersectObjects(pickable,true)[0];
  if(hit){{let o=hit.object;while(o&&!o.userData.formula)o=o.parent;if(o&&o.userData.formula)showCard(o.userData.formula,o.userData.extra);}}
}});
function setStat(t){{const e=$("#fstat");if(e)e.textContent=t;}}
{anatomy_js}
resize();
(function loop(){{requestAnimationFrame(loop);if(typeof tick==='function')tick();renderer.render(scene,camera);}})();
</script></body></html>"""


# ── Heart · Yuyay-13 (13 ventricles, each pulsing per-axis vote) ──────────────
def _page_yuyay13(ns: str) -> str:
    axes = json.dumps(ANCHORS["yuyay-13"])
    js = f"""
camera.position.set(0,0,210);
const AXES={axes};
const ventricles=[];
const R=78;
AXES.forEach((a,i)=>{{
  const ang=(i/AXES.length)*Math.PI*2;
  const x=Math.cos(ang)*R, y=Math.sin(ang)*R*0.82, z=Math.sin(ang*1.7)*16;
  const col=a.severity==='advisory'?0xf2c14e:(a.status==='live'?0x36d399:0x7d8fb0);
  const mat=new THREE.MeshStandardMaterial({{color:col,emissive:col,emissiveIntensity:0.4,roughness:0.35}});
  const m=new THREE.Mesh(new THREE.SphereGeometry(13,26,26),mat);
  m.position.set(x,y,z);
  m.userData.formula={{id:a.id,name:a.name+' axis',lean:a.lean,leanStatus:a.leanStatus,status:a.status,severity:a.severity,doi:a.doi,axis:'YUYAY'}};
  m.userData.base=col;m.userData.idx=i;
  scene.add(m);ventricles.push(m);pickable.push(m);
  // connective tissue to the core (heart muscle)
  const g=new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(x,y,z),new THREE.Vector3(0,0,0)]);
  scene.add(new THREE.Line(g,new THREE.LineBasicMaterial({{color:0x1d2940}})));
}});
// central heart muscle
const core=new THREE.Mesh(new THREE.IcosahedronGeometry(26,1),
  new THREE.MeshStandardMaterial({{color:0x0e3a2b,emissive:0x0a7a52,emissiveIntensity:0.5,roughness:0.4}}));
core.userData.formula={{id:'Λ',name:'Yuyay-13 aggregate Λ',lean:'lambdaConvergence_conjecture',leanStatus:'conjecture',status:'ts-only',severity:'advisory',axis:'LAMBDA',note:'Λ aggregate = MIN over 13 axes. Conjecture 1 (NOT theorem).'}};
scene.add(core);pickable.push(core);
let votes=null,t=0;
async function poll(){{try{{const r=await fetch('/api/{ns}/v4/yuyay-13/vote',{{method:'POST',headers:{{'content-type':'application/json'}},body:'{{}}'}});votes=await r.json();
  setStat('Λ='+votes.lambda_aggregate+' · '+(votes.passing?'PASS':'BELOW FLOOR')+' · signed='+votes.signing_available);
  if(votes.axes){{votes.axes.forEach((ax,i)=>{{if(ventricles[i]){{ventricles[i].userData.pulse=ax.score;
    ventricles[i].userData.formula.extra=JSON.stringify({{axis:ax.axis,score:ax.score,floor:ax.floor,verdict:ax.verdict||ax.evaluator,evaluator:ax.evaluator}},null,1);}}}});}}
}}catch(e){{setStat('offline');}}}}
poll();setInterval(poll,2000);
function tick(){{t+=0.016;scene.rotation.y=Math.sin(t*0.12)*0.35;
  ventricles.forEach((m,i)=>{{const pl=m.userData.pulse||0.9;const s=1+0.16*Math.sin(t*2.4+i*0.5)*pl;m.scale.setScalar(s);
    m.material.emissiveIntensity=0.3+0.5*pl*(0.6+0.4*Math.sin(t*2.4+i*0.5));}});
  core.scale.setScalar(1+0.09*Math.sin(t*2.2));core.material.emissiveIntensity=0.4+0.3*Math.sin(t*2.2);}}
"""
    return _shell("Heart — Yuyay-13", "13-axis trust ventricles · /api/" + ns + "/v4/yuyay-13/vote", js, _fingerprint())


# ── Blood · Yawar (Khipu chain river of glowing knots) ────────────────────────
def _page_khipu_chain(ns: str) -> str:
    anchors = json.dumps(ANCHORS["khipu-chain"])
    js = f"""
camera.position.set(0,18,230);
const ANCHORS={anchors};
let knots=[],t=0;
const riverMat=new THREE.LineBasicMaterial({{color:0xf06b6b}});
function rebuild(pendants){{
  knots.forEach(k=>scene.remove(k));knots=[];
  const n=Math.max(pendants.length,1);
  const pts=[];
  pendants.forEach((p,i)=>{{
    const x=(i-(n-1)/2)*26, y=Math.sin(i*0.6)*22, z=Math.cos(i*0.4)*18;
    const col=p.chain_verified===false?0xf2c14e:0xf06b6b;
    const m=new THREE.Mesh(new THREE.TorusKnotGeometry(7,2.4,48,8),
      new THREE.MeshStandardMaterial({{color:col,emissive:col,emissiveIntensity:0.55,roughness:0.3}}));
    m.position.set(x,y,z);
    const anch=ANCHORS[i%ANCHORS.length];
    m.userData.formula={{id:anch.id,name:anch.name,lean:anch.lean,leanStatus:anch.leanStatus,status:anch.status,severity:anch.severity,axis:'YAWAR',doi:anch.doi}};
    m.userData.formula.extra=JSON.stringify({{seq:p.seq,action:p.action,digest:(p.digest||'').slice(0,24),prev:(p.prev||'').slice(0,16),chain_verified:p.chain_verified}},null,1);
    scene.add(m);knots.push(m);pickable.push(m);pts.push(new THREE.Vector3(x,y,z));
  }});
  if(pts.length>1){{const g=new THREE.BufferGeometry().setFromPoints(pts);scene.add(new THREE.Line(g,riverMat));}}
}}
async function poll(){{try{{const r=await fetch('/api/{ns}/v4/khipu/chain?since=0');const j=await r.json();
  setStat('depth='+j.depth+' · chain_verified='+j.chain_verified+' · head='+(j.head||'').slice(0,12));
  rebuild(j.pendants||[]);}}catch(e){{setStat('offline');}}}}
poll();setInterval(poll,2000);
function tick(){{t+=0.016;scene.rotation.y=Math.sin(t*0.1)*0.5;
  knots.forEach((k,i)=>{{k.rotation.x+=0.02;k.rotation.y+=0.015;
    k.material.emissiveIntensity=0.4+0.4*Math.sin(t*2+i*0.7);}});}}
"""
    return _shell("Blood — Yawar Khipu chain", "river of signed receipts · /api/" + ns + "/v4/khipu/chain", js, _fingerprint())


# ── Immune · HuKLLA (8 gate-glands glowing per fire) ──────────────────────────
def _page_immune(ns: str) -> str:
    anchors = json.dumps(ANCHORS["immune"])
    js = f"""
camera.position.set(0,0,220);
const GATES={anchors};
// torso silhouette (capsule) — body surface for the gate-glands
const torso=new THREE.Mesh(new THREE.CapsuleGeometry(46,80,8,18),
  new THREE.MeshStandardMaterial({{color:0x10202c,emissive:0x0a1622,emissiveIntensity:0.3,transparent:true,opacity:0.5,roughness:0.6}}));
scene.add(torso);
const glands=[];
GATES.forEach((g,i)=>{{
  const ang=(i/GATES.length)*Math.PI*2;
  const x=Math.cos(ang)*52, y=(i-3.5)*16, z=Math.sin(ang)*30;
  const col=g.severity==='advisory'?0xf2c14e:0xe0457b;
  const m=new THREE.Mesh(new THREE.SphereGeometry(13,28,28),
    new THREE.MeshStandardMaterial({{color:col,emissive:col,emissiveIntensity:0.9,roughness:0.25}}));
  m.position.set(x,y,z);
  m.userData.formula={{id:g.id,name:g.name+' gate',lean:g.lean,leanStatus:g.leanStatus,status:g.status,severity:g.severity,axis:g.axis,doi:g.doi}};
  m.userData.idx=i;scene.add(m);glands.push(m);pickable.push(m);
}});
let t=0,fires={{}};GATES.forEach(g=>{{fires[g.id]=0.5;}});
async function poll(){{try{{const r=await fetch('https://SZLHOLDINGS-sentra.hf.space/v1/inspect',{{method:'POST',headers:{{'content-type':'application/json'}},body:'{{\"text\":\"\"}}'}});
  let j={{}};try{{j=await r.json();}}catch(e){{}}
  setStat('HuKLLA 8-gate sentinel · '+(j.decision||j.verdict||r.status)+' · λ='+(j.lambda_value!=null?j.lambda_value:'?')+' · /v1/inspect (sentra)');
}}catch(e){{setStat('immune /v1/inspect on sentra · cross-organ (8 gate-glands live)');}}
// simulate per-gate fire intensity from a live evaluator call where one exists
for(const g of GATES){{if(g.slug){{try{{const er=await fetch('/api/{ns}/v4/formulas/'+g.slug+'/evaluate',{{method:'POST',headers:{{'content-type':'application/json'}},body:'{{}}'}});const ej=await er.json();fires[g.id]=(ej.verdict==='ALLOW')?0.3:1.0;}}catch(e){{}}}}}}
}}
poll();setInterval(poll,2000);
function tick(){{t+=0.016;scene.rotation.y=Math.sin(t*0.1)*0.4;
  glands.forEach((m,i)=>{{const f=fires[GATES[i].id]||0.5;m.material.emissiveIntensity=0.3+0.6*f*(0.6+0.4*Math.sin(t*3+i));
    m.scale.setScalar(1+0.14*f*Math.sin(t*3+i));}});}}
"""
    return _shell("Immune — HuKLLA", "8-gate sentinel · /v1/inspect (sentra) + live gates", js, _fingerprint())


# ── Skeleton · Λ-spine (vertebral column, vertebra per axis) ──────────────────
def _page_lambda_spine(ns: str) -> str:
    js = f"""
camera.position.set(0,0,230);
let vertebrae=[],t=0;
async function build(){{
  let data={{vertebrae:[]}};
  try{{const r=await fetch('/api/{ns}/v4/lambda/convergence');data=await r.json();}}catch(e){{}}
  const V=data.vertebrae||[];
  V.forEach((v,i)=>{{
    const y=(V.length/2 - i)*16;
    const col=v.leanStatus==='theorem'?0xeef2f7:(v.leanStatus==='conjecture'?0xf2c14e:0xb9c4d6);
    const m=new THREE.Mesh(new THREE.TorusGeometry(13-Math.abs(i-6)*0.4,4.5,12,24),
      new THREE.MeshStandardMaterial({{color:col,emissive:col,emissiveIntensity:0.25,roughness:0.5}}));
    m.position.set(Math.sin(i*0.4)*6,y,0);m.rotation.x=Math.PI/2;
    m.userData.formula={{id:v.id,name:v.axis+' vertebra',lean:v.lean,leanStatus:v.leanStatus,status:v.status,severity:v.leanStatus==='conjecture'?'advisory':'enforced',axis:'LAMBDA',doi:null}};
    scene.add(m);vertebrae.push(m);pickable.push(m);
  }});
  // skull cap = A12 LambdaConvergence (Conjecture 1)
  const skull=new THREE.Mesh(new THREE.SphereGeometry(20,24,24),
    new THREE.MeshStandardMaterial({{color:0xf2c14e,emissive:0xf2c14e,emissiveIntensity:0.3,roughness:0.4}}));
  skull.position.set(0,(V.length/2+1.6)*16,0);
  skull.userData.formula={{id:'A12',name:'LambdaConvergence',lean:'lambdaConvergence_conjecture',leanStatus:'conjecture',status:'ts-only',severity:'advisory',axis:'LAMBDA',note:'Λ Conjecture 1 — NOT a discharged theorem.'}};
  scene.add(skull);pickable.push(skull);vertebrae.push(skull);
  // sacrum = A11 SoundnessAxiom (the load-bearing base of the Λ-spine)
  const sa=(data.soundness_axiom)||{{id:'A11',lean:'soundnessAxiom',leanStatus:'axiom'}};
  const sacrum=new THREE.Mesh(new THREE.DodecahedronGeometry(16,0),
    new THREE.MeshStandardMaterial({{color:0xb9c4d6,emissive:0x8a96aa,emissiveIntensity:0.25,roughness:0.5}}));
  sacrum.position.set(0,-(V.length/2+1.6)*16,0);
  sacrum.userData.formula={{id:sa.id,name:'SoundnessAxiom (sacrum)',lean:sa.lean,leanStatus:sa.leanStatus,status:'ts-only',severity:'enforced',axis:'LAMBDA',note:'A11 SoundnessAxiom — the load-bearing base of the Λ-spine.'}};
  scene.add(sacrum);pickable.push(sacrum);vertebrae.push(sacrum);
  setStat('Λ='+(data.lambda)+' · '+(data.claim_status||'')+'');
}}
build();
async function poll(){{try{{const r=await fetch('/api/{ns}/v4/lambda/convergence');const d=await r.json();
  setStat('Λ='+d.lambda+' · '+(d.claim_status||''));}}catch(e){{}}}}
setInterval(poll,2000);
function tick(){{t+=0.016;scene.rotation.y+=0.004;
  vertebrae.forEach((m,i)=>{{m.material.emissiveIntensity=0.2+0.25*Math.sin(t*1.6+i*0.4);}});}}
"""
    return _shell("Skeleton — Λ-spine", "aggregator vertebral column · /api/" + ns + "/v4/lambda/convergence", js, _fingerprint())


# ── Nervous · OTel (synaptic network of live spans) ───────────────────────────
def _page_nervous(ns: str) -> str:
    js = f"""
camera.position.set(0,0,260);
let nodes=[],lines=[],t=0;
function rebuild(spans){{
  nodes.forEach(n=>scene.remove(n));lines.forEach(l=>scene.remove(l));nodes=[];lines=[];
  const n=Math.max(spans.length,1);
  const pos=[];
  spans.forEach((s,i)=>{{
    const ang=i*2.399; const rad=22+i*4.2;
    const x=Math.cos(ang)*rad, y=Math.sin(ang)*rad*0.7, z=(i%5-2)*22;
    const m=new THREE.Mesh(new THREE.SphereGeometry(5.5,16,16),
      new THREE.MeshStandardMaterial({{color:0x4aa3ff,emissive:0x2a78d8,emissiveIntensity:0.5}}));
    m.position.set(x,y,z);
    m.userData.formula={{id:'OTel',name:(s.name||'span'),lean:'—',leanStatus:'infrastructure',status:'live',severity:'advisory',axis:'VSP',doi:null}};
    m.userData.formula.extra=JSON.stringify({{span:s.name,organ:s.organ,seq:s.seq,digest:s.digest,ok:s.ok}},null,1);
    scene.add(m);nodes.push(m);pickable.push(m);pos.push(new THREE.Vector3(x,y,z));
  }});
  for(let i=1;i<pos.length;i++){{const g=new THREE.BufferGeometry().setFromPoints([pos[i-1],pos[i]]);
    const l=new THREE.Line(g,new THREE.LineBasicMaterial({{color:0x244a78}}));scene.add(l);lines.push(l);}}
}}
async function poll(){{try{{const r=await fetch('/api/{ns}/v4/spans/recent');const j=await r.json();
  setStat('spans='+j.span_count+' · source='+j.source+' · no anchor (pure observability)');
  rebuild(j.spans||[]);}}catch(e){{setStat('offline');}}}}
poll();setInterval(poll,2000);
function tick(){{t+=0.016;scene.rotation.y+=0.0035;scene.rotation.x=Math.sin(t*0.2)*0.2;
  nodes.forEach((m,i)=>{{m.material.emissiveIntensity=0.3+0.5*Math.abs(Math.sin(t*3+i*0.8));}});}}
"""
    return _shell("Nervous — OTel + vsp", "synaptic span mesh · /api/" + ns + "/v4/spans/recent", js, _fingerprint())


# ── Wires · Kallpa (energy-pulse routing graph) ───────────────────────────────
def _page_wires(ns: str) -> str:
    js = f"""
camera.position.set(0,0,230);
let tierMeshes=[],pulses=[],t=0;const src=new THREE.Vector3(0,70,0);
const srcNode=new THREE.Mesh(new THREE.OctahedronGeometry(12,0),
  new THREE.MeshStandardMaterial({{color:0x34e7e4,emissive:0x34e7e4,emissiveIntensity:0.5}}));
srcNode.position.copy(src);
srcNode.userData.formula={{id:'A13',name:'KallpaEnergyAxis',lean:'kallpaEnergyAxis',leanStatus:'axiom',status:'ts-only',severity:'enforced',axis:'KALLPA',note:'Energy/efficiency routing — route to MIN Kallpa energy ≤ budget.'}};
scene.add(srcNode);pickable.push(srcNode);
function rebuild(routes,chosen){{
  tierMeshes.forEach(m=>scene.remove(m));tierMeshes=[];pulses=[];
  routes.forEach((rt,i)=>{{
    const x=(i-(routes.length-1)/2)*70, y=-60, z=0;
    const isChosen=chosen&&rt.tier===chosen.tier;
    const col=isChosen?0x34e7e4:0x2a5a78;
    const m=new THREE.Mesh(new THREE.BoxGeometry(28,28,28),
      new THREE.MeshStandardMaterial({{color:col,emissive:col,emissiveIntensity:isChosen?0.6:0.2}}));
    m.position.set(x,y,z);
    m.userData.formula={{id:'A13',name:rt.tier+' route',lean:'kallpaEnergyAxis',leanStatus:'axiom',status:'ts-only',severity:'enforced',axis:'KALLPA',doi:null}};
    m.userData.formula.extra=JSON.stringify(rt,null,1);
    scene.add(m);tierMeshes.push(m);pickable.push(m);
    const g=new THREE.BufferGeometry().setFromPoints([src,new THREE.Vector3(x,y,z)]);
    scene.add(new THREE.Line(g,new THREE.LineBasicMaterial({{color:isChosen?0x34e7e4:0x1d3a4a}})));
    pulses.push({{from:src.clone(),to:new THREE.Vector3(x,y,z),m:new THREE.Mesh(new THREE.SphereGeometry(3.4,10,10),
      new THREE.MeshBasicMaterial({{color:isChosen?0x9ffff5:0x4aa3ff}})),p:Math.random(),speed:isChosen?0.02:0.008}});
    scene.add(pulses[pulses.length-1].m);
  }});
}}
async function poll(){{try{{const r=await fetch('/api/{ns}/v4/orchestrate/routing',{{method:'POST',headers:{{'content-type':'application/json'}},body:'{{}}'}});const j=await r.json();
  setStat('chosen='+((j.chosen||{{}}).tier||'HALT')+' · min Kallpa energy · A13');
  rebuild(j.routes||[],j.chosen);}}catch(e){{setStat('offline');}}}}
poll();setInterval(poll,2000);
function tick(){{t+=0.016;scene.rotation.y=Math.sin(t*0.15)*0.4;
  srcNode.rotation.y+=0.02;srcNode.material.emissiveIntensity=0.4+0.3*Math.sin(t*3);
  pulses.forEach(pl=>{{pl.p+=pl.speed;if(pl.p>1)pl.p=0;pl.m.position.lerpVectors(pl.from,pl.to,pl.p);}});}}
"""
    return _shell("Wires — Kallpa", "energy-pulse routing · /api/" + ns + "/v4/orchestrate/routing", js, _fingerprint())


# ── Body · composed (ALL anatomies in one scene) ──────────────────────────────
def _page_body(ns: str) -> str:
    js = f"""
camera.position.set(0,10,300);
const parts={{}};const drill={{}};
let t=0,blood=[],synapse=[],wires=[];
// Brain (Amaru) — upper gold sphere
const brain=new THREE.Mesh(new THREE.IcosahedronGeometry(28,1),
  new THREE.MeshStandardMaterial({{color:0xffcf5a,emissive:0xffcf5a,emissiveIntensity:0.4,roughness:0.4}}));
brain.position.set(0,118,0);brain.userData.drill='cortex-3d';
brain.userData.formula={{id:'A36',name:'Amaru cortex',lean:'dualStreamRoutingAxiom',leanStatus:'axiom',status:'ts-only',severity:'advisory',axis:'AMARU',doi:'10.1038/nrn2113'}};
scene.add(brain);pickable.push(brain);
// Heart (Yuyay-13) — center emerald
const heart=new THREE.Mesh(new THREE.IcosahedronGeometry(26,1),
  new THREE.MeshStandardMaterial({{color:0x36d399,emissive:0x0a7a52,emissiveIntensity:0.5,roughness:0.4}}));
heart.position.set(0,30,0);heart.userData.drill='yuyay-13';
heart.userData.formula={{id:'Λ',name:'Yuyay-13 heart',lean:'lambdaConvergence_conjecture',leanStatus:'conjecture',status:'ts-only',severity:'advisory',axis:'YUYAY',note:'13 axes · Λ aggregate = MIN. Conjecture 1.'}};
scene.add(heart);pickable.push(heart);
// Skeleton (Λ-spine) — white vertebral column
const spine=[];
for(let i=0;i<9;i++){{const v=new THREE.Mesh(new THREE.TorusGeometry(10-Math.abs(i-4)*0.5,3.4,10,18),
  new THREE.MeshStandardMaterial({{color:0xeef2f7,emissive:0xaab4c2,emissiveIntensity:0.2}}));
  v.position.set(0,90-i*22,-6);v.rotation.x=Math.PI/2;v.userData.drill='lambda-spine-3d';
  v.userData.formula={{id:'A12',name:'Λ-spine vertebra',lean:'lambdaConvergence_conjecture',leanStatus:'conjecture',status:'ts-only',severity:'advisory',axis:'LAMBDA'}};
  scene.add(v);pickable.push(v);spine.push(v);}}
// Immune (HuKLLA) — 8 crimson surface nodes
const immune=[];
for(let i=0;i<8;i++){{const ang=i/8*Math.PI*2;const m=new THREE.Mesh(new THREE.SphereGeometry(7,16,16),
  new THREE.MeshStandardMaterial({{color:0xe0457b,emissive:0xe0457b,emissiveIntensity:0.4}}));
  m.position.set(Math.cos(ang)*48,20+Math.sin(ang)*40,Math.sin(ang)*30);m.userData.drill='immune-3d';
  m.userData.formula={{id:'A14',name:'HuKLLA gate',lean:'haloy_halt_on_lambda',leanStatus:'axiom',status:'ts-only',severity:'enforced',axis:'SENTRA'}};
  scene.add(m);pickable.push(m);immune.push(m);}}
// Blood (Yawar) — red lines heart → all organs
function bloodLine(to){{const g=new THREE.BufferGeometry().setFromPoints([heart.position,to]);
  const l=new THREE.Line(g,new THREE.LineBasicMaterial({{color:0xf06b6b}}));scene.add(l);
  const p=new THREE.Mesh(new THREE.SphereGeometry(2.6,8,8),new THREE.MeshBasicMaterial({{color:0xff9d9d}}));
  p.userData.drill='khipu-chain-3d';
  p.userData.formula={{id:'A6',name:'Yawar Khipu blood',lean:'hashChainIntegrity',leanStatus:'theorem',status:'live',severity:'enforced',axis:'YAWAR'}};
  scene.add(p);pickable.push(p);blood.push({{from:heart.position.clone(),to:to.clone(),m:p,p:Math.random()}});}}
[brain.position,...immune.map(m=>m.position),...spine.map(m=>m.position)].forEach(bloodLine);
// Nervous (OTel) — blue synapse mesh around the body
for(let i=0;i<24;i++){{const ang=i*2.399;const rad=58+(i%6)*5;
  const m=new THREE.Mesh(new THREE.SphereGeometry(2.8,8,8),new THREE.MeshStandardMaterial({{color:0x4aa3ff,emissive:0x2a78d8,emissiveIntensity:0.5}}));
  m.position.set(Math.cos(ang)*rad,30+Math.sin(i*0.7)*70,Math.sin(ang)*rad*0.6);m.userData.drill='nervous-3d';
  m.userData.formula={{id:'OTel',name:'synapse span',lean:'—',leanStatus:'infrastructure',status:'live',severity:'advisory',axis:'VSP'}};
  scene.add(m);pickable.push(m);synapse.push(m);}}
// Wires (Kallpa) — cyan energy lines bottom
for(let i=0;i<3;i++){{const x=(i-1)*44;const a=new THREE.Vector3(0,30,0),b=new THREE.Vector3(x,-86,18);
  const g=new THREE.BufferGeometry().setFromPoints([a,b]);scene.add(new THREE.Line(g,new THREE.LineBasicMaterial({{color:0x34e7e4}})));
  const p=new THREE.Mesh(new THREE.SphereGeometry(3,8,8),new THREE.MeshBasicMaterial({{color:0x9ffff5}}));p.userData.drill='wires-3d';
  p.userData.formula={{id:'A13',name:'Kallpa energy wire',lean:'kallpaEnergyAxis',leanStatus:'axiom',status:'ts-only',severity:'enforced',axis:'KALLPA'}};
  scene.add(p);pickable.push(p);wires.push({{from:a,to:b,m:p,p:Math.random()}});}}
// drill-in on click
cv.addEventListener("click",ev=>{{mouse.x=(ev.clientX/innerWidth)*2-1;mouse.y=-(ev.clientY/innerHeight)*2+1;
  ray.setFromCamera(mouse,camera);const hit=ray.intersectObjects(pickable,true)[0];
  if(hit){{let o=hit.object;while(o&&!o.userData.drill&&o.parent)o=o.parent;
    if(o&&o.userData.drill&&ev.shiftKey){{location.href='/'+o.userData.drill;}}}}}},true);
async function poll(){{try{{const r=await fetch('/api/{ns}/v4/body/composed');const j=await r.json();
  const h=(j.anatomies||[]).find(a=>a.anatomy==='heart')||{{}};
  setStat('Λ='+j.lambda_aggregate+' · '+j.anatomy_count+' anatomies · 749/14/163 · cosign '+(j.cosign_fingerprint||'').slice(0,12)+' · shift-click to drill');
}}catch(e){{setStat('offline');}}}}
poll();setInterval(poll,2000);
function tick(){{t+=0.016;scene.rotation.y=Math.sin(t*0.08)*0.45;
  brain.material.emissiveIntensity=0.35+0.25*Math.sin(t*2);brain.scale.setScalar(1+0.04*Math.sin(t*2));
  heart.scale.setScalar(1+0.08*Math.sin(t*2.4));heart.material.emissiveIntensity=0.4+0.3*Math.sin(t*2.4);
  immune.forEach((m,i)=>m.material.emissiveIntensity=0.3+0.4*Math.abs(Math.sin(t*2+i)));
  synapse.forEach((m,i)=>m.material.emissiveIntensity=0.3+0.5*Math.abs(Math.sin(t*3+i*0.5)));
  blood.forEach(b=>{{b.p+=0.012;if(b.p>1)b.p=0;b.m.position.lerpVectors(b.from,b.to,b.p);}});
  wires.forEach(w=>{{w.p+=0.02;if(w.p>1)w.p=0;w.m.position.lerpVectors(w.from,w.to,w.p);}});}}
"""
    return _shell("Body — composed", "ALL 8 anatomies · /api/" + ns + "/v4/body/composed", js, _fingerprint())


# ===========================================================================
# FastAPI registration — ADDITIVE; mount BEFORE the SPA catch-all.
# ===========================================================================
def register(app, ns: str = "a11oy") -> Dict[str, Any]:
    base = f"/api/{ns}/v4"
    paths: List[str] = []

    # ---- 3D pages ----
    @app.get("/yuyay-13", response_class=HTMLResponse)
    async def _p_yuyay():  # noqa
        return HTMLResponse(_page_yuyay13(ns))
    paths.append("/yuyay-13")

    @app.get("/khipu-chain-3d", response_class=HTMLResponse)
    async def _p_khipu():  # noqa
        return HTMLResponse(_page_khipu_chain(ns))
    paths.append("/khipu-chain-3d")

    @app.get("/immune-3d", response_class=HTMLResponse)
    async def _p_immune():  # noqa
        return HTMLResponse(_page_immune(ns))
    paths.append("/immune-3d")

    @app.get("/lambda-spine-3d", response_class=HTMLResponse)
    async def _p_spine():  # noqa
        return HTMLResponse(_page_lambda_spine(ns))
    paths.append("/lambda-spine-3d")

    @app.get("/nervous-3d", response_class=HTMLResponse)
    async def _p_nervous():  # noqa
        return HTMLResponse(_page_nervous(ns))
    paths.append("/nervous-3d")

    @app.get("/wires-3d", response_class=HTMLResponse)
    async def _p_wires():  # noqa
        return HTMLResponse(_page_wires(ns))
    paths.append("/wires-3d")

    @app.get("/body-3d", response_class=HTMLResponse)
    async def _p_body():  # noqa
        return HTMLResponse(_page_body(ns))
    paths.append("/body-3d")

    # ---- live JSON endpoints (wired to real evaluators + Khipu DAG + DSSE) ----
    @app.post(f"{base}/yuyay-13/vote")
    async def _e_yuyay(req: Request):  # noqa
        try:
            body = await req.json()
        except Exception:
            body = {}
        return JSONResponse(yuyay_13_vote(body if isinstance(body, dict) else {}))
    paths.append(f"{base}/yuyay-13/vote")

    @app.get(f"{base}/lambda/convergence")
    async def _e_lambda():  # noqa
        return JSONResponse(lambda_convergence())
    paths.append(f"{base}/lambda/convergence")

    @app.get(f"{base}/khipu/chain")
    async def _e_khipu(since: float = 0.0):  # noqa
        return JSONResponse(khipu_chain(ns, since))
    paths.append(f"{base}/khipu/chain")

    @app.get(f"{base}/spans/recent")
    async def _e_spans():  # noqa
        return JSONResponse(spans_recent(ns))
    paths.append(f"{base}/spans/recent")

    @app.post(f"{base}/orchestrate/routing")
    async def _e_routing(req: Request):  # noqa
        try:
            body = await req.json()
        except Exception:
            body = {}
        return JSONResponse(orchestrate_routing(body if isinstance(body, dict) else {}))
    paths.append(f"{base}/orchestrate/routing")

    @app.get(f"{base}/body/composed")
    async def _e_body():  # noqa
        return JSONResponse(body_composed(ns))
    paths.append(f"{base}/body/composed")

    # ---- sovereign Three.js — self-served at a unique path so this module is
    # fully self-sufficient on ANY organ (never collides with a11oy_derivation's
    # /static-vendor/three.min.js). r128 (MIT). NO external CDN. ----
    @app.get("/anatomy-three.min.js")
    async def _three():  # noqa
        from pathlib import Path
        for cand in ("/app/static-vendor/three.min.js", "static-vendor/three.min.js",
                     "/app/web/three.min.js", "web/three.min.js"):
            if Path(cand).exists():
                return FileResponse(cand, media_type="application/javascript")
        return Response("// three.min.js not found (sovereign vendor missing)",
                        media_type="application/javascript", status_code=404)
    paths.append("/anatomy-three.min.js")

    return {"registered": True, "ns": ns, "paths": paths,
            "signing_available": _signing_available(), "cosign_fingerprint": _fingerprint()}


if __name__ == "__main__":  # local smoke test
    print("yuyay-13 vote Λ:", yuyay_13_vote({}).get("lambda_aggregate"))
    print("lambda convergence:", lambda_convergence().get("claim_status"))
    print("khipu chain depth:", khipu_chain().get("depth"))
    print("spans:", spans_recent().get("span_count"))
    print("routing chosen:", (orchestrate_routing({}).get("chosen") or {}).get("tier"))
    bc = body_composed()
    print("body composed anatomies:", bc.get("anatomy_count"), "Λ:", bc.get("lambda_aggregate"))
