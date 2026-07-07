# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
# Doctrine v11 LOCKED: locked-proven=8 · Λ=Conjecture 1 · SLSA L1 honest / L2 attested / L3 roadmap
# Co-Authored-By: Perplexity Computer Agent
"""
szl_circuit_graphs.py — ADDITIVE a11oy-NATIVE ATTRIBUTION-GRAPH / CIRCUIT-TRACING
backend for the holographic frontier ring (surface: static/3d/surfaces/circuits.js).

WHY THIS EXISTS
    The interpretability surface (szl_a11oy_interpretability.py) resolves a residual
    stream into a SPARSE set of monosemantic FEATURES (dictionary/SAE encode). That is
    step ONE of mechanistic interpretability. This organ is step TWO: it wires those
    features into a CIRCUIT — an ATTRIBUTION GRAPH whose nodes are features (plus token
    embeddings, a transcoder error node, and the output logit) and whose edges are the
    DIRECT LINEAR EFFECT of one node on another. A backward, threshold-pruned trace from
    the output logit recovers the sub-graph that actually drives a given prediction, and
    a MODELED causal-ablation check reports how much the output moves when a node is
    zeroed — the honest signal the surface visualises.

MATH (deterministic MODELED trace; seeded; NO trained model, NO GPU, NO live weights)
    * Seed a small "replacement model": L layers, F candidate features per layer.
      A feature f in layer l has a seeded activation a[l,f] >= 0 (ReLU of a seeded
      pre-activation) and a seeded read/write direction in a d-dim residual space.
    * The DIRECT EFFECT edge weight from source node s to target node t is the linear
      contribution of s's activation, along its write direction, to t's pre-activation
      via t's read direction (a dot product scaled by a[s]). This mirrors the
      "direct linear effect" attribution used to build attribution-graph edges
      (Ameisen/Lindsey et al. 2025) — for a fixed input the feature-feature
      interactions are made linear so attribution is well-defined.
    * BACKWARD TRACE from the output logit: keep an edge iff |effect| >= tau * max_effect
      (threshold pruning), recurse toward the input embeddings, so the returned graph is
      the pruned attribution sub-graph — the primary object the surface renders.
    * completeness = (sum of |kept edge effects|) / (sum of |all edge effects| into
      retained nodes): the fraction of the logit's incoming influence the pruned graph
      explains (an "attribution completeness" proxy; NEVER a certainty claim).
    * MODELED causal ablation: for each retained feature, recompute the output
      pre-activation with that node zeroed; delta_logit = |logit - logit_ablated|
      is the node's causal weight (validates edge importance the way perturbation
      experiments validate attribution-graph claims — here on seeded inputs only).

LEADERS ADOPTED & CITED (clean-room; NOT claimed as SZL's own; VERIFY real):
    * Ameisen, Lindsey, Pearce, Gurnee, Turner, Chen, ... Olah, Batson (2025)
      "Circuit Tracing: Revealing Computational Graphs in Language Models",
      Transformer Circuits Thread.
      https://transformer-circuits.pub/2025/attribution-graphs/methods.html
      (cross-layer transcoders + backward Jacobian tracing -> pruned attribution graphs;
       nodes=features/error/embedding/logit, edges=linear direct effects.)
    * Anthropic (2025) companion "On the Biology of a Large Language Model"
      https://transformer-circuits.pub/2025/attribution-graphs/biology.html
    * Marks, Rager, Michaud, Belinkov, Bau, Mueller (2024) "Sparse Feature Circuits:
      Discovering and Editing Interpretable Causal Graphs in Language Models",
      arXiv:2406.02395. https://arxiv.org/abs/2406.02395
      (greedy attribution over SAE features -> sparse causal circuits; ablation edits.)
    * Cunningham, Ewart, Riggs, Huben, Sharkey (2023) "Sparse Autoencoders Find Highly
      Interpretable Features in Language Models", arXiv:2309.08600 (feature substrate).

HONESTY SPINE (Doctrine v11)
    * Label "MODELED" — returned VERBATIM, read verbatim by the frontend, NEVER upgraded.
      This is a deterministic SIMULATION of the circuit-tracing METHOD on seeded inputs;
      it is NOT a trained cross-layer transcoder, NOT a real attribution graph of any
      real model, NO live weights / activations / GPU. The graph is a hypothesis object
      about a MODELED replacement model — never a certainty claim about a real LLM (the
      real method itself only yields hypotheses about ~a quarter of prompts).
    * completeness / delta_logit / edge effects are properties of the seeded trace,
      honestly labelled — not measured claims about any deployed model.
    * Advisory only. Λ = Conjecture 1; adds NOTHING to the locked-8; trust never 100%.

ENDPOINT (mounted BEFORE the SPA catch-all; front-moved to router position 0 by serve.py)
    GET /api/a11oy/v1/circuits/attribution?seed=&layers=&features=&tau=
        -> renderable 200 JSON: {label:"MODELED", nodes[], edges[], completeness,
           top_causal[], receipt{...}, citations[], doctrine{...}}
"""
from __future__ import annotations

import hashlib
import math
import time
from typing import Any, Dict, List, Tuple

from fastapi import FastAPI
from fastapi.responses import JSONResponse

DOCTRINE = {"version": "v11", "counts": "749/14/163", "lambda": "Conjecture 1",
            "locked_proven": 8}

CITATIONS = [
    {"key": "circuit_tracing",
     "cite": ("Ameisen, Lindsey, Pearce, Gurnee et al. (2025) Circuit Tracing: Revealing "
              "Computational Graphs in Language Models. Transformer Circuits Thread."),
     "url": "https://transformer-circuits.pub/2025/attribution-graphs/methods.html"},
    {"key": "biology",
     "cite": "Anthropic (2025) On the Biology of a Large Language Model (companion).",
     "url": "https://transformer-circuits.pub/2025/attribution-graphs/biology.html"},
    {"key": "marks_sfc",
     "cite": ("Marks, Rager, Michaud, Belinkov, Bau, Mueller (2024) Sparse Feature "
              "Circuits: Discovering and Editing Interpretable Causal Graphs in LMs."),
     "url": "https://arxiv.org/abs/2406.02395"},
    {"key": "cunningham_sae",
     "cite": ("Cunningham, Ewart, Riggs, Huben, Sharkey (2023) Sparse Autoencoders Find "
              "Highly Interpretable Features in Language Models."),
     "url": "https://arxiv.org/abs/2309.08600"},
]


# --------------------------- deterministic seeded PRNG ---------------------------
def _rng(seed: int):
    """Tiny deterministic LCG -> uniform floats in [0,1). Pure stdlib, reproducible."""
    state = (seed * 6364136223846793005 + 1442695040888963407) & ((1 << 64) - 1)

    def nxt() -> float:
        nonlocal state
        state = (state * 6364136223846793005 + 1442695040888963407) & ((1 << 64) - 1)
        return ((state >> 11) & ((1 << 53) - 1)) / float(1 << 53)

    return nxt


def _unit(vec: List[float]) -> List[float]:
    n = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / n for v in vec]


def _dot(a: List[float], b: List[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


# --------------------------- MODELED replacement model ---------------------------
def _build_graph(seed: int, layers: int, feats: int, tau: float,
                 d: int = 12) -> Dict[str, Any]:
    """Seed a small replacement model, compute direct-effect edges, trace backward
    from the output logit with threshold pruning, and run a MODELED causal ablation.
    Everything is a deterministic function of (seed, layers, feats, tau, d)."""
    rnd = _rng(seed)
    layers = max(2, min(int(layers), 8))
    feats = max(2, min(int(feats), 8))
    tau = max(0.02, min(float(tau), 0.9))

    # token-embedding node (input) and per-layer features -------------------------
    def _vec() -> List[float]:
        return _unit([rnd() * 2.0 - 1.0 for _ in range(d)])

    emb_write = _vec()                                   # input embedding direction
    logit_read = _vec()                                  # output logit read direction

    # feature[l][f] = {act, read, write}
    feature: List[List[Dict[str, Any]]] = []
    for l in range(layers):
        row = []
        for f in range(feats):
            pre = rnd() * 2.0 - 0.6                       # seeded pre-activation
            act = pre if pre > 0.0 else 0.0              # ReLU (sparse: many die)
            row.append({"act": act, "read": _vec(), "write": _vec()})
        feature.append(row)

    def _nid(l: int, f: int) -> str:
        return f"L{l}F{f}"

    # ALL candidate direct-effect edges (source -> target) ------------------------
    # edge s->t weight = act[s] * <write[s], read[t]>  (direct linear effect)
    all_edges: List[Dict[str, Any]] = []
    # embedding -> layer-0 features
    for f in range(feats):
        t = feature[0][f]
        w = _dot(emb_write, t["read"]) * 1.0
        all_edges.append({"src": "EMB", "dst": _nid(0, f), "effect": w})
    # feature[l] -> feature[l+1]
    for l in range(layers - 1):
        for fs in range(feats):
            s = feature[l][fs]
            if s["act"] <= 0.0:
                continue
            for ft in range(feats):
                t = feature[l + 1][ft]
                w = s["act"] * _dot(s["write"], t["read"])
                all_edges.append({"src": _nid(l, fs), "dst": _nid(l + 1, ft),
                                  "effect": w})
    # last-layer features -> output logit
    for f in range(feats):
        s = feature[layers - 1][f]
        if s["act"] <= 0.0:
            continue
        w = s["act"] * _dot(s["write"], logit_read)
        all_edges.append({"src": _nid(layers - 1, f), "dst": "LOGIT", "effect": w})
    # a single transcoder ERROR node -> logit (honest: the replacement is imperfect)
    err_effect = (rnd() * 2.0 - 1.0) * 0.15
    all_edges.append({"src": "ERROR", "dst": "LOGIT", "effect": err_effect})

    # BACKWARD TRACE from LOGIT with threshold pruning ----------------------------
    max_abs = max((abs(e["effect"]) for e in all_edges), default=1.0) or 1.0
    thresh = tau * max_abs
    incoming: Dict[str, List[Dict[str, Any]]] = {}
    for e in all_edges:
        incoming.setdefault(e["dst"], []).append(e)

    kept_edges: List[Dict[str, Any]] = []
    kept_nodes = set()
    frontier = ["LOGIT"]
    seen = set()
    while frontier:
        node = frontier.pop()
        if node in seen:
            continue
        seen.add(node)
        kept_nodes.add(node)
        for e in incoming.get(node, []):
            if abs(e["effect"]) >= thresh:
                kept_edges.append(e)
                kept_nodes.add(e["src"])
                if e["src"] not in seen:
                    frontier.append(e["src"])

    # attribution completeness into retained nodes --------------------------------
    kept_ids = {id(e) for e in kept_edges}
    into_retained = [e for e in all_edges if e["dst"] in kept_nodes]
    denom = sum(abs(e["effect"]) for e in into_retained) or 1.0
    numer = sum(abs(e["effect"]) for e in kept_edges)
    completeness = numer / denom

    # baseline output logit pre-activation (sum of incoming effects) --------------
    def _logit_value(drop: str = "") -> float:
        v = 0.0
        for e in incoming.get("LOGIT", []):
            if e["src"] == drop:
                continue
            v += e["effect"]
        return v

    base_logit = _logit_value()

    # MODELED causal ablation of each retained FEATURE node (zero it) -------------
    feature_nodes = [n for n in kept_nodes if n not in ("EMB", "LOGIT", "ERROR")]
    top_causal: List[Dict[str, Any]] = []
    for n in feature_nodes:
        # zero this feature: remove its contribution to the logit (direct path) and
        # to any downstream feature it fed. For the MODELED proxy we recompute the
        # logit's direct incoming sum with any edge whose src==n removed one hop.
        drop_delta = 0.0
        for e in incoming.get("LOGIT", []):
            if e["src"] == n:
                drop_delta += e["effect"]
        # indirect (one-hop): edges n->mid->LOGIT
        for e in kept_edges:
            if e["src"] == n and e["dst"] not in ("LOGIT",):
                for e2 in incoming.get("LOGIT", []):
                    if e2["src"] == e["dst"]:
                        drop_delta += e["effect"] * e2["effect"]
        top_causal.append({"node": n, "delta_logit": round(abs(drop_delta), 6)})
    top_causal.sort(key=lambda x: x["delta_logit"], reverse=True)
    top_causal = top_causal[:8]

    # emit a compact, renderable node/edge list -----------------------------------
    def _kind(nid: str) -> str:
        if nid == "EMB":
            return "embedding"
        if nid == "LOGIT":
            return "output_logit"
        if nid == "ERROR":
            return "transcoder_error"
        return "feature"

    nodes = []
    for nid in sorted(kept_nodes):
        act = 0.0
        if nid not in ("EMB", "LOGIT", "ERROR"):
            l = int(nid[1:nid.index("F")]); f = int(nid[nid.index("F") + 1:])
            act = round(feature[l][f]["act"], 6)
        nodes.append({"id": nid, "kind": _kind(nid), "activation": act})
    edges = [{"src": e["src"], "dst": e["dst"], "effect": round(e["effect"], 6)}
             for e in kept_edges]
    edges.sort(key=lambda e: abs(e["effect"]), reverse=True)

    return {
        "layers": layers, "features_per_layer": feats, "residual_dim": d,
        "prune_threshold_tau": round(tau, 4),
        "n_nodes_total": layers * feats + 3,
        "n_edges_total": len(all_edges),
        "n_nodes_kept": len(kept_nodes),
        "n_edges_kept": len(kept_edges),
        "attribution_completeness": round(completeness, 4),
        "output_logit": round(base_logit, 6),
        "transcoder_error_share": round(abs(err_effect) / (abs(base_logit) or 1.0), 4),
        "nodes": nodes,
        "edges": edges,
        "top_causal": top_causal,
    }


def _receipt(payload: Dict[str, Any], seed: int) -> Dict[str, Any]:
    """Honest local receipt: a content digest over the modeled result. UNSIGNED-LOCAL
    unless a real in-Space signer wraps it later; we never fabricate a signature."""
    blob = repr(sorted(payload.items())).encode("utf-8")
    digest = hashlib.sha256(blob).hexdigest()
    return {
        "digest_sha256": digest,
        "seed": seed,
        "signature": "UNSIGNED-LOCAL",
        "note": ("content digest over the MODELED attribution trace; deterministic in "
                 "the seed. No DSSE signature is claimed locally (UNSIGNED-LOCAL)."),
    }


def register(app: FastAPI, ns: str = "a11oy") -> str:
    @app.get(f"/api/{ns}/v1/circuits/attribution", include_in_schema=False)
    async def _attribution(seed: int = 42, layers: int = 5, features: int = 6,
                           tau: float = 0.12) -> JSONResponse:
        t0 = time.time()
        try:
            g = _build_graph(int(seed), int(layers), int(features), float(tau))
        except Exception as e:  # never 500 the surface
            return JSONResponse({
                "label": "UNAVAILABLE",
                "detail": f"circuit trace failed: {type(e).__name__}",
                "doctrine": DOCTRINE, "citations": CITATIONS,
            }, status_code=200)
        digest_src = {k: v for k, v in g.items() if k not in ("nodes", "edges")}
        body = {
            "label": "MODELED",
            "surface": "circuits",
            "title": "Attribution Graph · Circuit Tracing (MODELED)",
            "method": ("deterministic simulation of cross-layer-transcoder circuit "
                       "tracing: seeded replacement model, direct-linear-effect edges, "
                       "backward threshold-pruned trace from the output logit, MODELED "
                       "causal ablation. NOT a trained transcoder; NO live model/GPU."),
            **g,
            "receipt": _receipt(digest_src, int(seed)),
            "citations": CITATIONS,
            "doctrine": DOCTRINE,
            "honesty": ("MODELED simulation of the circuit-tracing METHOD on seeded "
                        "inputs; a HYPOTHESIS object about a modeled replacement model, "
                        "never a certainty claim about a real LLM. Λ=Conjecture 1; adds "
                        "nothing to the locked-8; trust never 100%."),
            "elapsed_ms": round((time.time() - t0) * 1000, 2),
        }
        return JSONResponse(body, status_code=200)

    return (f"circuits attribution-graph mounted: "
            f"GET /api/{ns}/v1/circuits/attribution (label MODELED)")


# --------------------------- module self-test ---------------------------
def _selftest() -> None:
    g = _build_graph(42, 5, 6, 0.12)
    assert g["n_edges_kept"] >= 1, "no edges kept"
    assert "LOGIT" in {n["id"] for n in g["nodes"]}, "logit node missing"
    assert 0.0 <= g["attribution_completeness"] <= 1.0, "completeness out of range"
    # determinism
    g2 = _build_graph(42, 5, 6, 0.12)
    assert g == g2, "non-deterministic for a fixed seed"
    # different seed -> different graph
    g3 = _build_graph(43, 5, 6, 0.12)
    assert g3["edges"] != g["edges"], "seed had no effect"
    r = _receipt({k: v for k, v in g.items() if k not in ("nodes", "edges")}, 42)
    assert r["signature"] == "UNSIGNED-LOCAL", "must not fabricate a signature"
    print("szl_circuit_graphs: ALL OK (deterministic attribution trace, honest MODELED, "
          "UNSIGNED-LOCAL receipt)")


if __name__ == "__main__":
    _selftest()
