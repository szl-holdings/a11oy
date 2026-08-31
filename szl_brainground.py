#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED · Λ = Conjecture 1
# Sign-off: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
"""szl_brainground.py — BRAINGROUND: a governed grounding-confidence + honest-abstention layer
over the brain's retrieval.

WHAT IT IS. A deterministic, explainable read on ONE question the brain must answer honestly
before it speaks: *do I have enough grounding to answer this query, or should I abstain?* It
scores the REAL grounding_subgraph the brain returns for a query (szl_brain_api.BrainIndex.ask,
hippoRAG-PPR local ⊕ graphRAG-community global) and, when the grounding is weak, returns the
honest verdict INSUFFICIENT-GROUNDING — the point being that the brain can truthfully say
"I don't have enough grounding" rather than answer anyway.

This is PURE honesty / provenance capability over knowledge-graph retrieval. It advances NO
detection / fusion / effector / targeting / cueing capability. It computes nothing about the
world — only about how well the estate's OWN knowledge graph grounds a query.

THE SCORE (0..1 grounding_confidence, every component reported separately — no black box):
  (a) seed_coverage       — fraction of query terms that matched a retrieved seed node.
  (b) subgraph_cohesion   — link density of the grounding nodes (edges / max simple edges).
  (c) salience_mass       — PPR mass concentrated in the top grounding nodes (normalized).
  (d) community_consistency — dominant-community share of the grounding nodes (few vs scattered).
The four are combined by a fixed, published weight vector into grounding_confidence; the math
is shown honestly and each component is emitted verbatim so the number can never hide a weak
part.

HONEST ABSTENTION. If grounding_confidence < WEAK_THRESHOLD OR node_count < MIN_GROUNDING_NODES,
the verdict is INSUFFICIENT-GROUNDING and the surface states the brain SHOULD ABSTAIN. A middle
band is WEAK-GROUNDING (answer with caution); only a strong grounding is GROUNDED. High
confidence is NEVER claimed when the components are weak.

RECEIPTS — RECEIPT-ON-WRITE, NOT ON-READ. The GET info/ground reads mint NOTHING. Only the POST
receipt endpoint emits an UNSIGNED SHA-256 content digest over the computed result (mirrors the
honestywall content-digest pattern) — a plain content hash, never a fabricated signature.

DOCTRINE v11:
  - Adds NOTHING to the locked-8 {F1,F4,F7,F11,F12,F18,F19,F22}; touches no locked formula and
    no kernel. Reuses the brain's OWN honest labels (LBL_MODELED / LBL_UNAVAILABLE) VERBATIM and
    never upgrades a label. grounding_confidence is MODELED (a deterministic graph statistic,
    never a MEASURED semantic truth).
  - Λ stays Conjecture 1; introduces no theorem, no green/1.0. Khipu BFT stays Conjecture 2.
    Trust ceiling 0.97, never 100%.
  - Pure stdlib + numpy. Additive routes, registered before the SPA catch-all; 0 runtime CDN.
"""

import datetime
import hashlib
import json
import math
import re
from typing import Any

import numpy as np

# Honest Doctrine v11 labels — reuse the brain's OWN vocabulary VERBATIM (never upgraded).
# Restated as a guarded fallback so a broken import can never silently blank the label.
try:
    from szl_brain_api import LBL_MODELED, LBL_UNAVAILABLE
except Exception:  # pragma: no cover — label vocabulary must never be blank
    LBL_MODELED = "MODELED"
    LBL_UNAVAILABLE = "UNAVAILABLE"

# This surface's own id (must match szl3d_holographic.SURFACES + holographic.html).
SURFACE_ID = "brainground"

# Doctrine constants (never inflated).
LOCKED_SET = ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]
LOCKED_COUNT = 8
TRUST_CEILING = 0.97

# Verdicts (honest abstention band).
VERDICT_GROUNDED = "GROUNDED"
VERDICT_WEAK = "WEAK-GROUNDING"
VERDICT_INSUFFICIENT = "INSUFFICIENT-GROUNDING"

# Component weights — fixed and PUBLISHED (sum to 1.0). Deterministic; no tuning at request time.
WEIGHTS = {
    "seed_coverage": 0.30,
    "subgraph_cohesion": 0.25,
    "salience_mass": 0.25,
    "community_consistency": 0.20,
}

# Abstention thresholds. Below WEAK_THRESHOLD (or too few nodes) -> abstain honestly.
WEAK_THRESHOLD = 0.45        # < this OR too few nodes => INSUFFICIENT-GROUNDING (abstain)
GROUNDED_THRESHOLD = 0.62    # >= this => GROUNDED; in-between => WEAK-GROUNDING
MIN_GROUNDING_NODES = 3      # fewer grounding nodes than this => abstain regardless of score

# Fraction of grounding nodes treated as "top" when measuring salience concentration.
TOP_MASS_FRACTION = 0.30

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _terms(text: str) -> list:
    """Lowercase alnum tokens (len >= 2) — the query terms we test for grounding coverage."""
    return [t for t in _TOKEN_RE.findall((text or "").lower()) if len(t) >= 2]


def _clamp01(x: float) -> float:
    if x != x:  # NaN
        return 0.0
    return float(min(1.0, max(0.0, x)))


# --------------------------------------------------------------------------- #
# The four grounding-confidence components (each explainable, each in [0,1]).
# All operate on the brain's OWN ask() output; nothing about the world is invented.
# --------------------------------------------------------------------------- #
def _seed_coverage(query: str, seeds: list) -> dict:
    """(a) Fraction of query terms that matched a retrieved seed node's text."""
    terms = _terms(query)
    if not terms:
        return {"value": 0.0, "matched_terms": 0, "query_terms": 0,
                "note": "no usable query terms -> 0 coverage (honest)"}
    seed_text = " ".join(
        f"{s.get('id', '')} {s.get('title', '')}" for s in (seeds or [])
    ).lower()
    seed_tokens = set(_TOKEN_RE.findall(seed_text))
    matched = sum(1 for t in set(terms) if t in seed_tokens)
    distinct = len(set(terms))
    return {"value": _clamp01(matched / distinct), "matched_terms": matched,
            "query_terms": distinct,
            "note": "fraction of distinct query terms with a matching seed node"}


def _subgraph_cohesion(node_count: int, link_count: int) -> dict:
    """(b) Link density of the grounding nodes: edges / max simple undirected edges."""
    if node_count < 2:
        return {"value": 0.0, "node_count": node_count, "link_count": link_count,
                "max_edges": 0, "note": "fewer than 2 nodes -> no cohesion (honest 0)"}
    max_edges = node_count * (node_count - 1) / 2.0
    return {"value": _clamp01(link_count / max_edges), "node_count": node_count,
            "link_count": link_count, "max_edges": int(max_edges),
            "note": "actual edges / maximum simple undirected edges among grounding nodes"}


def _salience_mass(nodes: list) -> dict:
    """(c) PPR mass concentrated in the top grounding nodes (normalized to [0,1])."""
    ppr = np.array([float(n.get("ppr", 0.0) or 0.0) for n in (nodes or [])], dtype=float)
    used = "ppr"
    if ppr.size == 0 or float(ppr.sum()) <= 0.0:
        # honest fallback: if no PPR mass, use the node salience field (still MODELED).
        ppr = np.array([float(n.get("salience", 0.0) or 0.0) for n in (nodes or [])], dtype=float)
        used = "salience"
    total = float(ppr.sum())
    n = int(ppr.size)
    if n == 0 or total <= 0.0:
        return {"value": 0.0, "top_k": 0, "node_count": n, "mass_field": used,
                "note": "no retrieval mass on the grounding nodes -> 0 (honest)"}
    top_k = max(1, int(math.ceil(n * TOP_MASS_FRACTION)))
    top_sum = float(np.sort(ppr)[::-1][:top_k].sum())
    return {"value": _clamp01(top_sum / total), "top_k": top_k, "node_count": n,
            "mass_field": used,
            "note": f"share of retrieval mass held by the top {top_k} of {n} grounding nodes"}


def _community_consistency(nodes: list) -> dict:
    """(d) Dominant-community share of the grounding nodes (clustered vs scattered)."""
    comms = [n.get("community") for n in (nodes or []) if n.get("community") is not None]
    total = len(comms)
    if total == 0:
        return {"value": 0.0, "distinct_communities": 0, "grounded_nodes": 0,
                "note": "no community assignments on grounding nodes -> 0 (honest)"}
    counts: dict = {}
    for c in comms:
        counts[c] = counts.get(c, 0) + 1
    dominant = max(counts.values())
    return {"value": _clamp01(dominant / total), "distinct_communities": len(counts),
            "grounded_nodes": total, "dominant_community_share": round(dominant / total, 6),
            "note": "share of grounding nodes in the single dominant community (few vs scattered)"}


def compute_confidence(ask_result: dict) -> dict:
    """Deterministic grounding-confidence over ONE brain ask() result.

    Returns the four components (each verbatim, each in [0,1]), the weighted
    grounding_confidence in [0,1], the honest verdict, and whether the brain
    SHOULD ABSTAIN. Pure computation — mints nothing, invents nothing."""
    ask_result = ask_result or {}
    query = str(ask_result.get("query", "") or "")
    seeds = ask_result.get("seeds") or []
    grounding = ask_result.get("grounding_subgraph") or {}
    nodes = grounding.get("nodes") or []
    node_count = int(grounding.get("node_count", len(nodes)) or 0)
    link_count = int(grounding.get("link_count", 0) or 0)

    comp = {
        "seed_coverage": _seed_coverage(query, seeds),
        "subgraph_cohesion": _subgraph_cohesion(node_count, link_count),
        "salience_mass": _salience_mass(nodes),
        "community_consistency": _community_consistency(nodes),
    }

    confidence = 0.0
    for name, w in WEIGHTS.items():
        confidence += w * float(comp[name]["value"])
    confidence = _clamp01(confidence)

    too_few = node_count < MIN_GROUNDING_NODES
    if confidence < WEAK_THRESHOLD or too_few:
        verdict = VERDICT_INSUFFICIENT
        abstain = True
    elif confidence < GROUNDED_THRESHOLD:
        verdict = VERDICT_WEAK
        abstain = False
    else:
        verdict = VERDICT_GROUNDED
        abstain = False

    reason = {
        VERDICT_GROUNDED: (f"grounding_confidence {confidence:.3f} >= {GROUNDED_THRESHOLD} "
                           f"with {node_count} grounding nodes"),
        VERDICT_WEAK: (f"grounding_confidence {confidence:.3f} in "
                       f"[{WEAK_THRESHOLD}, {GROUNDED_THRESHOLD}) — answer with caution"),
        VERDICT_INSUFFICIENT: (
            f"grounding_confidence {confidence:.3f} < {WEAK_THRESHOLD}"
            + (f" and node_count {node_count} < {MIN_GROUNDING_NODES}" if too_few else "")
            + " — the brain SHOULD ABSTAIN rather than answer"),
    }[verdict]

    return {
        "label": LBL_MODELED,
        "surface_id": SURFACE_ID,
        "query": query,
        "grounding_confidence": round(confidence, 6),
        "verdict": verdict,
        "should_abstain": abstain,
        "verdict_reason": reason,
        "components": comp,
        "weights": dict(WEIGHTS),
        "thresholds": {
            "weak_threshold": WEAK_THRESHOLD,
            "grounded_threshold": GROUNDED_THRESHOLD,
            "min_grounding_nodes": MIN_GROUNDING_NODES,
        },
        "grounding_stats": {
            "node_count": node_count,
            "link_count": link_count,
            "seed_count": len(seeds),
            "community_context_count": len(ask_result.get("community_context") or []),
        },
        "formula": ("grounding_confidence = "
                    "0.30·seed_coverage + 0.25·subgraph_cohesion + "
                    "0.25·salience_mass + 0.20·community_consistency; "
                    "each component ∈ [0,1], reported verbatim; "
                    "abstain if confidence < 0.45 or node_count < 3"),
        "note": ("grounding_confidence is MODELED — a deterministic statistic over the brain's "
                 "REAL grounding_subgraph, NEVER a MEASURED semantic truth. A weak grounding "
                 "yields INSUFFICIENT-GROUNDING so the brain can honestly abstain; high "
                 "confidence is never claimed when the components are weak."),
    }


# --------------------------------------------------------------------------- #
# Retrieval bridge — run the brain's OWN ask() (guarded; honest UNAVAILABLE on failure).
# --------------------------------------------------------------------------- #
def _run_ask(q: str, k: int, ns: str) -> tuple:
    """Return (ask_result, error). Never raises: an unreachable brain degrades honestly."""
    try:
        import szl_brain_api as brain
        idx = brain.get_index(ns)
        return idx.ask(q, max(1, int(k))), None
    except Exception as exc:  # brain graph unavailable -> honest UNAVAILABLE, never fabricated
        return None, str(exc)[:200]


def evaluate(q: str, k: int = 12, ns: str = "a11oy") -> dict:
    """Run retrieval via the brain and compute the grounding-confidence result. PURE READ."""
    ask_result, err = _run_ask(q, k, ns)
    if ask_result is None:
        return {
            "ok": False,
            "label": LBL_UNAVAILABLE,
            "surface_id": SURFACE_ID,
            "endpoint": "brain/ground",
            "query": q,
            "verdict": VERDICT_INSUFFICIENT,
            "should_abstain": True,
            "verdict_reason": "brain retrieval unavailable — no grounding to score; brain SHOULD ABSTAIN",
            "error": err,
            "note": "no grounding could be retrieved; no confidence fabricated (honest UNAVAILABLE).",
            "timestamp_utc": _now_iso(),
        }
    out = compute_confidence(ask_result)
    out["ok"] = True
    out["endpoint"] = "brain/ground"
    out["k"] = max(1, int(k))
    out["retrieval"] = ask_result.get("retrieval")
    out["answer_label"] = ask_result.get("answer_label")
    out["cited_node_ids"] = ask_result.get("cited_node_ids")
    out["timestamp_utc"] = _now_iso()
    return out


# --------------------------------------------------------------------------- #
# Receipt — UNSIGNED SHA-256 content digest. RECEIPT-ON-WRITE (POST), NEVER on a GET read.
# --------------------------------------------------------------------------- #
def _canonical_core(result: dict) -> str:
    """Deterministic canonical serialization of the grounding-bearing content (excludes the
    volatile timestamp), so the digest attests the VERDICT + confidence + components."""
    comp = result.get("components", {}) or {}
    core = {
        "query": result.get("query"),
        "verdict": result.get("verdict"),
        "should_abstain": result.get("should_abstain"),
        "grounding_confidence": result.get("grounding_confidence"),
        "components": {k: round(float(comp.get(k, {}).get("value", 0.0)), 6) for k in WEIGHTS},
        "weights": result.get("weights"),
        "thresholds": result.get("thresholds"),
        "grounding_stats": result.get("grounding_stats"),
        "label": result.get("label"),
    }
    return json.dumps(core, sort_keys=True, separators=(",", ":"), default=str)


def content_receipt(result: dict) -> dict:
    """An UNSIGNED SHA-256 content-digest receipt over a grounding result (no signature)."""
    canonical = _canonical_core(result)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return {
        "kind": "szl.brainground.grounding",
        "algorithm": "sha256",
        "content_sha256": digest,
        "signed": False,
        "mode": "UNSIGNED-CONTENT-DIGEST",
        "receipt_on": "write (POST ground/receipt)",
        "note": ("unsigned SHA-256 content digest of the grounding result; "
                 "RECEIPT-ON-WRITE, never on a GET read. No signature fabricated."),
        "computed_at": _now_iso(),
    }


# --------------------------------------------------------------------------- #
# Handlers.
# --------------------------------------------------------------------------- #
def handle_info(ns: str = "a11oy") -> dict:
    """GET /brain/ground/info — static self-describing manifest (no compute). PURE READ."""
    base = f"/api/{ns}/v1/brain/ground"
    return {
        "ok": True,
        "endpoint": "brain/ground/info",
        "service": "a11oy.brain.ground",
        "surface_id": SURFACE_ID,
        "title": "Brainground — grounding-confidence + honest abstention over brain retrieval",
        "label": LBL_MODELED,
        "what": ("scores the brain's REAL grounding_subgraph for a query and returns an honest "
                 "verdict — GROUNDED / WEAK-GROUNDING / INSUFFICIENT-GROUNDING. When the "
                 "grounding is weak, the brain SHOULD ABSTAIN rather than answer. Pure "
                 "honesty/provenance over knowledge-graph retrieval; advances no "
                 "detection/fusion/effector/targeting/cueing capability."),
        "endpoints": {
            "info": f"GET  {base}/info",
            "ground": f"GET  {base}?q=&k=",
            "receipt": f"POST {base}/receipt?q=&k=",
        },
        "verdicts": [VERDICT_GROUNDED, VERDICT_WEAK, VERDICT_INSUFFICIENT],
        "components": {
            "seed_coverage": "fraction of query terms with a matching seed node",
            "subgraph_cohesion": "link density of the grounding nodes",
            "salience_mass": "PPR mass concentrated in the top grounding nodes",
            "community_consistency": "dominant-community share of the grounding nodes",
        },
        "weights": dict(WEIGHTS),
        "thresholds": {
            "weak_threshold": WEAK_THRESHOLD,
            "grounded_threshold": GROUNDED_THRESHOLD,
            "min_grounding_nodes": MIN_GROUNDING_NODES,
        },
        "formula": ("grounding_confidence = 0.30·seed_coverage + 0.25·subgraph_cohesion + "
                    "0.25·salience_mass + 0.20·community_consistency ∈ [0,1]; "
                    "abstain if confidence < 0.45 or node_count < 3"),
        "doctrine": {
            "label_top": LBL_MODELED,
            "locked_proven": LOCKED_COUNT,
            "locked_set": LOCKED_SET,
            "adds_to_locked_8": 0,
            "lambda": "Conjecture 1",
            "khipu_bft": "Conjecture 2",
            "trust_ceiling": TRUST_CEILING,
            "trust_100_percent": False,
            "runtime_cdn": 0,
            "note": ("additive read-only surface over knowledge-graph retrieval; reuses the "
                     "brain's honest labels VERBATIM, never upgraded; confidence is MODELED, "
                     "never MEASURED; GET reads mint nothing; POST receipt digests only."),
        },
        "receipt_policy": ("RECEIPT-ON-WRITE-NOT-ON-READ — GET info/ground mint nothing; "
                           "POST receipt emits an unsigned SHA-256 content digest."),
        "honest_labels_reused": [LBL_MODELED, LBL_UNAVAILABLE],
        "timestamp_utc": _now_iso(),
    }


def handle_ground(q: str = "", k: int = 12, ns: str = "a11oy") -> dict:
    """GET /brain/ground — compute grounding confidence + verdict. PURE READ (mints nothing)."""
    return evaluate(q, k, ns)


def handle_receipt(q: str = "", k: int = 12, ns: str = "a11oy") -> dict:
    """POST /brain/ground/receipt — compute + mint an UNSIGNED SHA-256 receipt (RECEIPT-ON-WRITE)."""
    result = evaluate(q, k, ns)
    out = dict(result)
    out["endpoint"] = "brain/ground/receipt"
    out["receipt"] = content_receipt(result)
    return out


# --------------------------------------------------------------------------- #
# FastAPI registration.
#   GET  info/ground — normal FastAPI GET handlers.
#   POST receipt     — raw-Request handler via app.router.add_route (Starlette passes the
#                      Request positionally), with app.add_api_route as the fallback. The
#                      handler is annotated request: fastapi.Request. Registered BEFORE the
#                      SPA catch-all by serve.py.
# --------------------------------------------------------------------------- #
def register(app, ns: str = "a11oy") -> str:
    from fastapi.responses import JSONResponse

    base = f"/api/{ns}/v1/brain/ground"

    @app.get(f"{base}/info")
    def _brainground_info():
        """Self-describing brainground manifest (pure read; mints nothing)."""
        return JSONResponse(handle_info(ns))

    @app.get(base)
    def _brainground_ground(q: str = "", k: int = 12):  # noqa: ANN202
        """Grounding-confidence + honest verdict for a query (pure read; mints nothing)."""
        return JSONResponse(handle_ground(q, k, ns))

    async def _brainground_receipt(request):
        """POST: compute + UNSIGNED SHA-256 content digest (RECEIPT-ON-WRITE)."""
        q = request.query_params.get("q", "")
        try:
            k = int(request.query_params.get("k", "12"))
        except Exception:
            k = 12
        return JSONResponse(handle_receipt(q, k, ns))

    # Annotate the raw-Request handler as fastapi.Request so any FastAPI signature analysis (in
    # the add_api_route fallback path) treats the param as the request object.
    try:
        import fastapi as _fastapi
        _brainground_receipt.__annotations__["request"] = _fastapi.Request
    except Exception:  # noqa: BLE001 — annotation is best-effort only
        pass

    rec_path = f"{base}/receipt"
    add_route = getattr(getattr(app, "router", None), "add_route", None)
    add_api_route = getattr(app, "add_api_route", None)
    try:
        if callable(add_route):
            app.router.add_route(rec_path, _brainground_receipt, methods=["POST"])
        elif callable(add_api_route):
            app.add_api_route(rec_path, _brainground_receipt, methods=["POST"])
        else:  # pragma: no cover — last-resort Starlette Route append
            from starlette.routing import Route
            app.router.routes.append(Route(rec_path, _brainground_receipt, methods=["POST"]))
    except Exception as exc:  # additive register must never break boot
        print(f"[{ns}] brainground receipt POST route NOT wired (guarded): {exc!r}",
              file=__import__("sys").stderr)
        return "brainground-wired:2(get-only)"

    return "brainground-wired:3"


# --------------------------------------------------------------------------- #
# Self-test — honest verdicts, components in range, abstention fires, receipt only on write.
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    import sys as _sys

    print("=" * 72)
    print("szl_brainground — self-test (grounding-confidence + honest abstention)")
    print("=" * 72)

    # 1) empty grounding -> every component 0, INSUFFICIENT, abstain.
    empty = compute_confidence({"query": "anything", "seeds": [],
                                "grounding_subgraph": {"node_count": 0, "link_count": 0, "nodes": []}})
    assert 0.0 <= empty["grounding_confidence"] <= 1.0
    assert empty["verdict"] == VERDICT_INSUFFICIENT and empty["should_abstain"] is True
    print(f"[1] empty grounding -> {empty['verdict']}, abstain, conf={empty['grounding_confidence']}  OK")

    # 2) a strong synthetic grounding -> GROUNDED, all components in [0,1].
    nodes = [{"id": f"n{i}", "title": "brain graph node", "ppr": 0.5 if i == 0 else 0.05,
              "salience": 0.1, "community": "c1"} for i in range(6)]
    strong = compute_confidence({
        "query": "brain graph",
        "seeds": [{"id": "n0", "title": "brain graph node"}],
        "grounding_subgraph": {"node_count": 6, "link_count": 13, "nodes": nodes},
    })
    for name in WEIGHTS:
        v = strong["components"][name]["value"]
        assert 0.0 <= v <= 1.0, f"{name} out of range: {v}"
    assert strong["verdict"] == VERDICT_GROUNDED, strong["verdict"]
    print(f"[2] strong grounding -> {strong['verdict']}, conf={strong['grounding_confidence']}  OK")

    # 3) receipt is a deterministic sha256 (RECEIPT-ON-WRITE); same result -> same digest.
    r1 = content_receipt(strong)
    r2 = content_receipt(strong)
    assert r1["algorithm"] == "sha256" and len(r1["content_sha256"]) == 64
    assert r1["signed"] is False and r1["content_sha256"] == r2["content_sha256"]
    print(f"[3] receipt sha256={r1['content_sha256'][:16]}… unsigned, deterministic  OK")

    # 4) labels are the brain's OWN vocabulary, never upgraded.
    assert strong["label"] == LBL_MODELED == "MODELED"
    print("[4] label MODELED (brain vocabulary, never upgraded)  OK")

    # 5) doctrine: locked-8 exact, Λ Conjecture 1, trust 0.97 not 100%.
    info = handle_info("a11oy")
    d = info["doctrine"]
    assert d["locked_proven"] == 8 and d["locked_set"] == LOCKED_SET
    assert d["adds_to_locked_8"] == 0 and d["lambda"] == "Conjecture 1"
    assert d["trust_ceiling"] == 0.97 and d["trust_100_percent"] is False
    print("[5] doctrine: locked-8 exact, +0, Λ=Conjecture 1, trust 0.97 (not 100%)  OK")

    print("\nok:true checks:5")
    _sys.exit(0)
