#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED · Λ = Conjecture 1
# Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>
"""szl_brainexplain.py — BRAIN EXPLAIN: a transparent, human-readable explanation of
WHY the brain retrieved what it did for a query.

Brain Explain is an explainability trace over the REAL retrieval subgraph. For a
query it reuses the SAME honest retrieval the brain already runs
(szl_brain_api.get_index().ask) and turns it into a deterministic, plain-language
account of the retrieval — never a rationale it invents. It is PURE honesty /
observability over the knowledge graph: it advances NO detection / fusion /
effector / targeting / cueing capability. It only DESCRIBES the retrieval the
estate's own brain already performed.

WHAT IT DESCRIBES, at request time (all read VERBATIM from the live retrieval; this
module invents no node, harvests nothing, and ranks nothing anew):
  * seed matches       — which query terms literally matched which seed nodes
                         (exact token overlap / substring / MODELED vector proxy).
  * per-node rationale — for each supporting node: its rank, its personalized
                         PageRank (ppr) and how much that lifted it above its
                         baseline salience (ppr_gain), and the honest BASIS for its
                         inclusion (direct-term-match / substring-match /
                         vector-similarity / graph-traversal / unattributed).
  * communities        — which knowledge-graph communities the grounding traversed.
  * honest labels      — every supporting node's OWN label VERBATIM, never upgraded.

The explanation is DESCRIPTIVE of the real retrieval. Where a node has no
attributable signal it is reported as `unattributed` honestly, not rationalized.
The trace label is MODELED (a derived account over a real subgraph, never a
MEASURED fact about the world).

VERDICT over the reachable evidence:
  EXPLAINABLE           — at least one supporting node traces to a direct query-term
                          match and every supporting node has an attributable basis.
  PARTIALLY-EXPLAINABLE — the retrieval is traceable but rests only on a MODELED
                          similarity proxy / traversal (no direct term anchor), or
                          some supporting node is unattributed.
  OPAQUE                — retrieval returned too little to explain (no query-matched
                          seed, or no supporting nodes): the grounding would be
                          generic global salience, not query-driven, so no
                          query-relevance rationale is fabricated.
An OPAQUE/PARTIAL result is never softened to EXPLAINABLE; a truthful OPAQUE beats a
fabricated rationale.

RECEIPTS — RECEIPT-ON-WRITE, NOT ON-READ. The GET info/explain reads mint NOTHING.
Only the POST receipt endpoint emits an UNSIGNED SHA-256 content digest over the
explanation trace (mirrors the govern/honestywall content-digest pattern) — a plain
content hash, never a fabricated signature, never a receipt on a GET.

DOCTRINE v11:
  * Adds NOTHING to the locked-8 {F1,F4,F7,F11,F12,F18,F19,F22}; it only DESCRIBES.
    Touches no locked formula and no kernel.
  * Λ stays Conjecture 1 (advisory); introduces no theorem, no green/1.0, no proof
    of Λ. Khipu BFT remains Conjecture 2. Trust ceiling 0.97, never 100%.
  * No label is ever upgraded; an OPAQUE trace can never be reported as EXPLAINABLE.
  * Pure stdlib (+numpy tolerated, not required). Additive routes, registered before
    the SPA catch-all; canonical domain a-11-oy.com; 0 runtime CDN.
"""

import datetime
import hashlib
import json
import re

# Honesty-label vocabulary (doctrine v11). Re-stated here (not imported) so a broken
# import can never silently blank the vocabulary; tests grep these exact strings.
HONEST_LABELS = (
    "LIVE", "MEASURED", "MODELED", "SAMPLE", "SIMULATED", "CACHED", "PROVEN",
    "CONJECTURE", "ROADMAP", "DEGRADED", "REPLAY", "STRUCTURAL-ONLY", "HONEST-STUB",
    "UNSIGNED-LOCAL", "UNAVAILABLE",
)

# An explanation trace is a derived account over a real subgraph — MODELED, never
# MEASURED. Absent retrieval degrades honestly to UNAVAILABLE.
LBL_MODELED = "MODELED"
LBL_UNAVAILABLE = "UNAVAILABLE"

# Explainability verdicts.
EXPLAINABLE = "EXPLAINABLE"
PARTIALLY_EXPLAINABLE = "PARTIALLY-EXPLAINABLE"
OPAQUE = "OPAQUE"

# Inclusion bases (the honest reason a node is in the grounding set).
BASIS_DIRECT = "direct-term-match"
BASIS_SUBSTRING = "substring-match"
BASIS_VECTOR = "vector-similarity"
BASIS_TRAVERSAL = "graph-traversal"
BASIS_UNATTRIBUTED = "unattributed"

TRUST_CEILING = 0.97
LOCKED_SET = ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]
LOCKED_COUNT = 8
KERNEL_COMMIT = "c7c0ba17"

# This surface's own id (must match szl3d_holographic.SURFACES + holographic.html).
SURFACE_ID = "brainexplain"

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _tokens(*parts) -> list:
    """Lowercase alnum tokens (len>=2) from the given strings, in order. Mirrors the
    tokenizer szl_brain_api uses so a matched term is a term that literally appears in
    the node's own text — never one this module invents."""
    out = []
    for p in parts:
        for t in _TOKEN_RE.findall((str(p) or "").lower()):
            if len(t) >= 2:
                out.append(t)
    return out


def _doctrine_block(note: str = "") -> dict:
    d = {
        "version": "v11",
        "label_top": LBL_MODELED,
        "locked_proven": LOCKED_COUNT,
        "locked_set": list(LOCKED_SET),
        "kernel_commit": KERNEL_COMMIT,
        "adds_to_locked_8": 0,
        "lambda": "Conjecture 1",
        "khipu_bft": "Conjecture 2",
        "trust_ceiling": TRUST_CEILING,
        "trust_100_percent": False,
        "runtime_cdn": 0,
    }
    if note:
        d["note"] = note
    return d


def _node_label(v) -> str:
    """A node's OWN honesty label, VERBATIM. A missing label is 'UNLABELLED' — never
    fabricated up to MEASURED/PROVEN."""
    return str(v) if v is not None else "UNLABELLED"


# --------------------------------------------------------------------------- #
# The explanation trace — a PURE, deterministic account of one real retrieval.
# --------------------------------------------------------------------------- #

def build_trace(*, query: str, seeds: list, grounding_nodes: list,
                community_summaries: list, ns: str = "a11oy",
                content_hash: str = "") -> dict:
    """Build a deterministic, plain-language explanation of a single retrieval.

    Pure and deterministic: given the same retrieval primitives it returns the same
    trace. It DESCRIBES the retrieval — it never re-ranks, and it never invents a
    rationale for a node that has no attributable signal.

    Args:
      query:               the raw query string.
      seeds:               the retrieval's seed hits — dicts with id/title/kind/score
                           and a 'match' block {exact_token_overlap, vector_cosine,
                           substring}. May be empty (no query match => OPAQUE).
      grounding_nodes:     the grounding subgraph node views — dicts with id/title/
                           kind/node_label/salience/community and a per-query 'ppr'.
      community_summaries: the community context covering the grounding set.
      content_hash:        the graph content hash (for correlating traces).
    """
    q_tokens = set(_tokens(query))
    seeds = list(seeds or [])
    seeds_by_id = {s.get("id"): s for s in seeds}
    seed_ids = set(seeds_by_id)

    # Deterministic ordering: strongest personalized rank first, id as tiebreak.
    gnodes = sorted(
        list(grounding_nodes or []),
        key=lambda n: (-float(n.get("ppr") or 0.0), str(n.get("id"))))

    supporting = []
    for rank, n in enumerate(gnodes, 1):
        nid = n.get("id")
        text_tokens = set(_tokens(n.get("title", ""), n.get("kind", ""), nid))
        matched = sorted(q_tokens & text_tokens)
        ppr = round(float(n.get("ppr") or 0.0), 8)
        sal = round(float(n.get("salience") or 0.0), 8)
        ppr_gain = round(ppr - sal, 8)
        is_seed = nid in seed_ids
        match_info = (seeds_by_id.get(nid, {}) or {}).get("match", {}) or {}
        vec = float(match_info.get("vector_cosine") or 0.0)
        substr = bool(match_info.get("substring"))

        if matched:
            basis = BASIS_DIRECT
            why = ("query term(s) [" + ", ".join(matched) + "] appear in this node's "
                   "own text; ranked #%d by personalized PageRank (ppr=%s, %+0.8f vs "
                   "baseline salience %s)" % (rank, ppr, ppr_gain, sal))
        elif is_seed and substr:
            basis = BASIS_SUBSTRING
            why = ("the query is a substring of this node's title/id; ranked #%d "
                   "(ppr=%s, %+0.8f vs baseline salience %s)" % (rank, ppr, ppr_gain, sal))
        elif is_seed and vec > 0.0:
            basis = BASIS_VECTOR
            why = ("no exact term overlap; included via a MODELED hash-embedding "
                   "similarity proxy (cosine=%s); ranked #%d (ppr=%s)"
                   % (round(vec, 6), rank, ppr))
        elif ppr > 0.0:
            basis = BASIS_TRAVERSAL
            why = ("not a direct query match; reached by graph traversal from the "
                   "matched seed node(s) (personalized PageRank ppr=%s, %+0.8f vs "
                   "baseline salience %s)" % (ppr, ppr_gain, sal))
        else:
            basis = BASIS_UNATTRIBUTED
            why = ("present in the grounding set with no query-term match, similarity, "
                   "or traversal signal to attribute — reported honestly, not rationalized")

        supporting.append({
            "rank": rank,
            "id": nid,
            "title": n.get("title", nid),
            "kind": n.get("kind"),
            "node_label": _node_label(n.get("node_label")),  # VERBATIM
            "community": n.get("community"),
            "ppr": ppr,
            "salience": sal,
            "ppr_gain": ppr_gain,
            "is_seed": is_seed,
            "matched_terms": matched,
            "basis": basis,
            "why": why,
        })

    # ---- seed-term matches (which query terms matched which seed) ---------- #
    seed_matches = []
    for s in seeds:
        st = set(_tokens(s.get("title", ""), s.get("kind", ""), s.get("id")))
        m = sorted(q_tokens & st)
        sm = s.get("match", {}) or {}
        seed_matches.append({
            "id": s.get("id"),
            "title": s.get("title", s.get("id")),
            "node_label": _node_label(s.get("node_label")),  # VERBATIM
            "matched_terms": m,
            "exact_token_overlap": sm.get("exact_token_overlap"),
            "vector_cosine": sm.get("vector_cosine"),
            "substring": bool(sm.get("substring")),
            "score": s.get("score"),
        })

    # ---- communities traversed by the grounding set ----------------------- #
    comm_by_id = {c.get("id"): c for c in (community_summaries or []) if isinstance(c, dict)}
    traversed: dict = {}
    for n in gnodes:
        cid = n.get("community")
        if cid is None:
            continue
        traversed[cid] = traversed.get(cid, 0) + 1
    communities = []
    for cid, cnt in sorted(traversed.items(), key=lambda kv: (-kv[1], str(kv[0]))):
        c = comm_by_id.get(cid, {})
        communities.append({
            "id": cid,
            "nodes_in_grounding": cnt,
            "size": c.get("size"),
            "summary": c.get("summary"),
        })

    # ---- honest verdict over the reachable evidence ----------------------- #
    n_support = len(supporting)
    direct = [s for s in supporting if s["basis"] in (BASIS_DIRECT, BASIS_SUBSTRING)]
    unattributed = [s for s in supporting if s["basis"] == BASIS_UNATTRIBUTED]

    if not seeds or n_support == 0:
        verdict = OPAQUE
        reason = (("no query-matched seed node" if not seeds
                   else "no supporting node in the grounding set")
                  + " — retrieval returned too little to explain; the grounding would "
                    "be generic global salience, not query-driven, so no query-relevance "
                    "rationale is fabricated.")
    elif unattributed:
        verdict = PARTIALLY_EXPLAINABLE
        reason = ("%d of %d supporting node(s) have no attributable retrieval signal; "
                  "the retrieval is only partially explainable and is reported honestly."
                  % (len(unattributed), n_support))
    elif not direct:
        verdict = PARTIALLY_EXPLAINABLE
        reason = ("no exact query-term match anchors the retrieval; the explanation "
                  "rests only on a MODELED similarity proxy and graph traversal, so it "
                  "is partially explainable.")
    else:
        verdict = EXPLAINABLE
        reason = ("%d of %d supporting node(s) trace to a direct query-term match; the "
                  "rest are reached by transparent graph traversal from those matches."
                  % (len(direct), n_support))

    explainable_share = (round((n_support - len(unattributed)) / n_support, 6)
                         if n_support else 0.0)

    return {
        "label": LBL_MODELED,
        "surface_id": SURFACE_ID,
        "ns": ns,
        "query": query,
        "content_hash": content_hash,
        "verdict": verdict,
        "verdict_reason": reason,
        "retrieval": ("hippoRAG-PPR(local) ⊕ graphRAG-community(global) — the SAME "
                      "honest retrieval szl_brain_api runs; this trace only describes it."),
        "seed_matches": seed_matches,
        "supporting_nodes": supporting,
        "communities_traversed": communities,
        "summary": {
            "seed_count": len(seeds),
            "supporting_count": n_support,
            "direct_match_count": len(direct),
            "unattributed_count": len(unattributed),
            "community_count": len(communities),
            "explainable_share": explainable_share,
        },
        "method": ("descriptive explainability trace over the real retrieval subgraph: "
                   "seed-term matches, per-node ppr-vs-salience rationale, communities "
                   "traversed, and each supporting node's OWN label VERBATIM. MODELED — "
                   "never invents a rationale."),
        "honest_labels_vocabulary": list(HONEST_LABELS),
        "doctrine": _doctrine_block(
            "additive DESCRIBE-only surface over the knowledge graph; touches no locked "
            "formula and no kernel; Λ = Conjecture 1, never a theorem."),
        "timestamp_utc": _now_iso(),
    }


# --------------------------------------------------------------------------- #
# Live trace — reuse the AUDITED brain index / ask() (never re-harvest, never re-rank).
# --------------------------------------------------------------------------- #

def live_explanation(ns: str = "a11oy", q: str = "", k: int = 12) -> dict:
    """Read the live retrieval for q and build its explanation trace.

    Fully guarded: if the brain index/retrieval is unavailable, returns an honest
    UNAVAILABLE/OPAQUE trace rather than raising or fabricating a rationale."""
    try:
        import szl_brain_api as _brain_api
        idx = _brain_api.get_index(ns)
        a = idx.ask(q, k=max(1, int(k)))
        grounding = a.get("grounding_subgraph", {}) or {}
        return build_trace(
            query=q,
            seeds=a.get("seeds", []) or [],
            grounding_nodes=grounding.get("nodes", []) or [],
            community_summaries=a.get("community_context", []) or [],
            ns=ns,
            content_hash=getattr(idx, "content_hash", ""),
        )
    except Exception as exc:  # honest degrade — never a fabricated rationale
        return {
            "label": LBL_UNAVAILABLE,
            "surface_id": SURFACE_ID,
            "ns": ns,
            "query": q,
            "verdict": OPAQUE,
            "verdict_reason": ("brain retrieval unavailable this request; no explanation "
                               "fabricated (honest OPAQUE/UNAVAILABLE)."),
            "error": str(exc)[:200],
            "seed_matches": [],
            "supporting_nodes": [],
            "communities_traversed": [],
            "summary": {"seed_count": 0, "supporting_count": 0, "direct_match_count": 0,
                        "unattributed_count": 0, "community_count": 0,
                        "explainable_share": 0.0},
            "doctrine": _doctrine_block("retrieval unavailable; no rationale fabricated."),
            "timestamp_utc": _now_iso(),
        }


# --------------------------------------------------------------------------- #
# Receipt — UNSIGNED SHA-256 content digest. RECEIPT-ON-WRITE (POST), never GET.
# --------------------------------------------------------------------------- #

def _canonical_core(trace: dict) -> str:
    """Deterministic canonical serialization of the explanation-bearing content
    (excludes the volatile timestamp), so the digest attests the VERDICT + evidence,
    not the clock."""
    core = {
        "query": trace.get("query"),
        "verdict": trace.get("verdict"),
        "content_hash": trace.get("content_hash"),
        "seed_matches": [
            {"id": s.get("id"), "matched_terms": s.get("matched_terms"),
             "node_label": s.get("node_label")}
            for s in trace.get("seed_matches", [])
        ],
        "supporting_nodes": [
            {"id": s.get("id"), "rank": s.get("rank"), "basis": s.get("basis"),
             "node_label": s.get("node_label"), "matched_terms": s.get("matched_terms"),
             "ppr": s.get("ppr"), "salience": s.get("salience")}
            for s in trace.get("supporting_nodes", [])
        ],
        "communities_traversed": [c.get("id") for c in trace.get("communities_traversed", [])],
    }
    return json.dumps(core, sort_keys=True, separators=(",", ":"), default=str)


def _content_receipt(trace: dict) -> dict:
    """An UNSIGNED SHA-256 content-digest receipt over the explanation trace (no
    signature fabricated). RECEIPT-ON-WRITE — only the POST receipt path calls this."""
    canonical = _canonical_core(trace)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return {
        "kind": "szl.brainexplain.trace",
        "algorithm": "sha256",
        "content_sha256": digest,
        "signed": False,
        "mode": "UNSIGNED-CONTENT-DIGEST",
        "receipt_on": "write (POST receipt)",
        "note": ("unsigned SHA-256 content digest of the explanation trace; "
                 "RECEIPT-ON-WRITE, never on a GET read. No signature fabricated."),
        "computed_at": _now_iso(),
    }


# --------------------------------------------------------------------------- #
# Handlers.
# --------------------------------------------------------------------------- #

def handle_info(ns: str = "a11oy") -> dict:
    """GET /brain/explain/info — static self-describing manifest (no compute). PURE READ."""
    base = f"/api/{ns}/v1/brain/explain"
    return {
        "ok": True,
        "service": "a11oy.brain.explain",
        "endpoint": "brain/explain/info",
        "surface_id": SURFACE_ID,
        "label": LBL_MODELED,
        "title": "Brain Explain — why the brain retrieved what it did",
        "what": ("produces a deterministic, plain-language explanation trace over the "
                 "REAL retrieval subgraph for a query: which query terms matched which "
                 "seed nodes, why each supporting node ranked where it did (ppr vs "
                 "salience), which communities were traversed, and each supporting "
                 "node's OWN honesty label VERBATIM. Pure honesty/observability over "
                 "the knowledge graph; advances no detection/fusion/effector/targeting/"
                 "cueing capability. DESCRIBES the retrieval — never invents a rationale; "
                 "never upgrades a label."),
        "endpoints": {
            "info": f"GET  {base}/info",
            "explain": f"GET  {base}?q=&k=",
            "receipt": f"POST {base}/receipt",
        },
        "method": ("reuses szl_brain_api.get_index().ask (invents no node, re-ranks "
                   "nothing); describes the seeds, the grounding subgraph's per-node "
                   "personalized-PageRank rationale, and the communities traversed."),
        "verdicts": [EXPLAINABLE, PARTIALLY_EXPLAINABLE, OPAQUE],
        "verdict_legend": {
            EXPLAINABLE: ("a direct query-term match anchors the retrieval and every "
                          "supporting node has an attributable basis"),
            PARTIALLY_EXPLAINABLE: ("traceable but rests only on a MODELED similarity "
                                    "proxy / traversal, or some node is unattributed"),
            OPAQUE: ("retrieval returned too little to explain (no query-matched seed "
                     "or no supporting nodes); no rationale fabricated"),
        },
        "inclusion_bases": [BASIS_DIRECT, BASIS_SUBSTRING, BASIS_VECTOR,
                            BASIS_TRAVERSAL, BASIS_UNATTRIBUTED],
        "receipt_policy": ("RECEIPT-ON-WRITE-NOT-ON-READ — only POST /receipt emits an "
                           "unsigned SHA-256 content digest; GET mints nothing."),
        "honest_labels_vocabulary": list(HONEST_LABELS),
        "doctrine": _doctrine_block(
            "additive DESCRIBE-only surface over the knowledge graph; touches no locked "
            "formula and no kernel; Λ = Conjecture 1, never a theorem."),
        "timestamp_utc": _now_iso(),
    }


def handle_explain(ns: str = "a11oy", q: str = "", k: int = 12) -> dict:
    """GET /brain/explain?q=&k= — the explanation trace for q. PURE READ (mints nothing)."""
    trace = live_explanation(ns, q, k)
    trace["ok"] = trace.get("label") != LBL_UNAVAILABLE
    trace["endpoint"] = "brain/explain"
    trace["receipt_policy"] = ("RECEIPT-ON-WRITE-NOT-ON-READ — GET mints nothing; "
                               "POST /receipt digests.")
    return trace


def handle_receipt(ns: str = "a11oy", q: str = "", k: int = 12) -> dict:
    """POST /brain/explain/receipt — the explanation trace + an UNSIGNED SHA-256
    content-digest receipt (RECEIPT-ON-WRITE). Never 500s: honest degraded response."""
    try:
        trace = live_explanation(ns, q, k)
        out = dict(trace)
        out["ok"] = True
        out["endpoint"] = "brain/explain/receipt"
        out["receipt"] = _content_receipt(trace)
        return out
    except Exception as exc:
        return {
            "ok": False, "endpoint": "brain/explain/receipt", "label": LBL_UNAVAILABLE,
            "verdict": OPAQUE, "error": str(exc)[:200],
            "doctrine": "v11: receipt unavailable; no fabricated verdict/receipt emitted.",
            "timestamp_utc": _now_iso(),
        }


# --------------------------------------------------------------------------- #
# FastAPI router registration.
#   GET  info/explain — normal FastAPI GET handlers (pure reads; mint nothing).
#   POST receipt      — raw-Request handler via app.router.add_route (Starlette passes
#                       the Request positionally, version-proof under fastapi==0.137.x),
#                       with app.add_api_route as the fallback. The handler is annotated
#                       request: fastapi.Request. Registered BEFORE the SPA catch-all.
# --------------------------------------------------------------------------- #

def register(app, ns: str = "a11oy") -> str:
    from fastapi.responses import JSONResponse

    base = f"/api/{ns}/v1/brain/explain"

    @app.get(f"{base}/info")
    def _brainexplain_info():
        """Self-describing brain-explain manifest (pure read; mints nothing)."""
        return JSONResponse(handle_info(ns))

    @app.get(base)
    def _brainexplain_explain(q: str = "", k: int = 12):
        """Explanation trace for q; MODELED (pure read; mints nothing)."""
        return JSONResponse(handle_explain(ns, q, k))

    async def _brainexplain_receipt(request):
        """POST: the explanation trace for the query (q/k from the JSON body or query
        params) + an UNSIGNED SHA-256 content digest (RECEIPT-ON-WRITE)."""
        q, k = "", 12
        try:
            raw = await request.body()
            if raw:
                body = json.loads(raw)
                if isinstance(body, dict):
                    q = str(body.get("q", body.get("query", "")) or "")
                    k = int(body.get("k", 12) or 12)
        except Exception:  # a malformed body degrades to an empty query, never a 500
            q, k = "", 12
        # query params win when present (parity with the GET path).
        try:
            qp = request.query_params
            if qp.get("q") is not None:
                q = str(qp.get("q"))
            if qp.get("k") is not None:
                k = int(qp.get("k"))
        except Exception:
            pass
        return JSONResponse(handle_receipt(ns, q, k))

    # Annotate the raw-Request handler as fastapi.Request so any FastAPI signature
    # analysis (in the add_api_route fallback path) treats the param as the request
    # object (0.137.x gotcha).
    try:
        import fastapi as _fastapi
        _brainexplain_receipt.__annotations__["request"] = _fastapi.Request
    except Exception:  # noqa: BLE001 — annotation is best-effort only
        pass

    rcpt_path = f"{base}/receipt"
    add_route = getattr(getattr(app, "router", None), "add_route", None)
    add_api_route = getattr(app, "add_api_route", None)
    try:
        if callable(add_route):
            app.router.add_route(rcpt_path, _brainexplain_receipt, methods=["POST"])
        elif callable(add_api_route):
            app.add_api_route(rcpt_path, _brainexplain_receipt, methods=["POST"])
        else:  # pragma: no cover — last-resort Starlette Route append
            from starlette.routing import Route
            app.router.routes.append(Route(rcpt_path, _brainexplain_receipt, methods=["POST"]))
    except Exception as exc:  # additive register must never break boot
        print(f"[{ns}] brainexplain receipt POST route NOT wired (guarded): {exc!r}",
              file=__import__("sys").stderr)
        return "brainexplain-wired:2(get-only)"

    return "brainexplain-wired:3"


# --------------------------------------------------------------------------- #
# Self-test — descriptive trace, honest verdicts, receipt only on write.
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    import sys as _sys

    print("=" * 72)
    print("szl_brainexplain — self-test (retrieval explainability trace)")
    print("=" * 72)

    # A small, fully synthetic retrieval fixture (no network, no heavy index build).
    seeds = [
        {"id": "n1", "title": "brain graph harvest", "kind": "module", "score": 0.8,
         "node_label": "HARVESTED",
         "match": {"exact_token_overlap": 0.5, "vector_cosine": 0.3, "substring": False}},
    ]
    grounding = [
        {"id": "n1", "title": "brain graph harvest", "kind": "module",
         "node_label": "HARVESTED", "community": "c0", "salience": 0.10, "ppr": 0.30},
        {"id": "n2", "title": "estate ledger", "kind": "module",
         "node_label": "MODELED", "community": "c0", "salience": 0.05, "ppr": 0.12},
    ]
    comms = [{"id": "c0", "size": 2, "summary": "community c0: 2 nodes"}]

    trace = build_trace(query="brain graph", seeds=seeds, grounding_nodes=grounding,
                        community_summaries=comms, ns="a11oy", content_hash="deadbeef")

    # 1) descriptive + MODELED + EXPLAINABLE with a direct match anchoring it.
    assert trace["label"] == LBL_MODELED
    assert trace["verdict"] == EXPLAINABLE, trace["verdict"]
    sup = trace["supporting_nodes"]
    assert sup[0]["id"] == "n1" and sup[0]["basis"] == BASIS_DIRECT
    assert "graph" in sup[0]["matched_terms"] and "brain" in sup[0]["matched_terms"]
    assert sup[1]["basis"] == BASIS_TRAVERSAL  # reached via PPR, not a direct match
    # node labels are VERBATIM.
    assert sup[0]["node_label"] == "HARVESTED" and sup[1]["node_label"] == "MODELED"
    print(f"[1] EXPLAINABLE, MODELED; n1 direct-term-match, n2 graph-traversal; "
          f"labels verbatim  OK")

    # 2) determinism: same inputs => identical trace (minus the volatile timestamp).
    t2 = build_trace(query="brain graph", seeds=seeds, grounding_nodes=grounding,
                     community_summaries=comms, ns="a11oy", content_hash="deadbeef")
    a = dict(trace); a.pop("timestamp_utc")
    b = dict(t2); b.pop("timestamp_utc")
    assert a == b, "trace must be deterministic"
    print("[2] deterministic trace (same retrieval => same account)  OK")

    # 3) OPAQUE when retrieval returns too little (no query-matched seed).
    op = build_trace(query="brain graph", seeds=[], grounding_nodes=grounding,
                     community_summaries=comms, ns="a11oy", content_hash="deadbeef")
    assert op["verdict"] == OPAQUE and op["summary"]["seed_count"] == 0
    print("[3] no query-matched seed => OPAQUE (no rationale fabricated)  OK")

    # 4) PARTIALLY-EXPLAINABLE when only a MODELED similarity proxy anchors it.
    #    (seed matched by vector only; its text carries none of the query terms.)
    vseeds = [{"id": "v1", "title": "alpha", "kind": "module", "score": 0.2,
               "node_label": "MODELED",
               "match": {"exact_token_overlap": 0.0, "vector_cosine": 0.4,
                         "substring": False}}]
    vground = [{"id": "v1", "title": "alpha", "kind": "module", "node_label": "MODELED",
                "community": "c1", "salience": 0.05, "ppr": 0.20}]
    part = build_trace(query="zulu quebec", seeds=vseeds, grounding_nodes=vground,
                       community_summaries=[], ns="a11oy", content_hash="beef")
    assert part["verdict"] == PARTIALLY_EXPLAINABLE, part["verdict"]
    assert part["supporting_nodes"][0]["basis"] == BASIS_VECTOR
    print("[4] vector-only anchor => PARTIALLY-EXPLAINABLE  OK")

    # 5) RECEIPT-ON-WRITE: deterministic unsigned sha256; GET explain mints nothing.
    r1 = _content_receipt(trace)
    r2 = _content_receipt(trace)
    assert r1["algorithm"] == "sha256" and len(r1["content_sha256"]) == 64
    assert r1["signed"] is False and r1["mode"] == "UNSIGNED-CONTENT-DIGEST"
    assert r1["content_sha256"] == r2["content_sha256"], "digest must be deterministic"
    g = handle_explain("a11oy", "")  # live read (may be OPAQUE off-box) — mints nothing
    assert "receipt" not in g, "GET explain must NOT mint a receipt (receipt-on-write)"
    print(f"[5] POST digest={r1['content_sha256'][:16]}… unsigned + deterministic; "
          f"GET explain mints nothing  OK")

    # 6) doctrine: locked-8 exact, +0, Λ Conjecture 1, trust 0.97 not 100%.
    d = trace["doctrine"]
    assert d["locked_proven"] == 8 and d["locked_set"] == LOCKED_SET
    assert d["adds_to_locked_8"] == 0
    assert d["lambda"] == "Conjecture 1" and d["khipu_bft"] == "Conjecture 2"
    assert d["trust_ceiling"] == 0.97 and d["trust_100_percent"] is False
    assert d["runtime_cdn"] == 0
    assert LBL_MODELED in HONEST_LABELS and LBL_UNAVAILABLE in HONEST_LABELS
    print("[6] doctrine: locked-8 exact, +0, Λ=Conjecture 1, trust 0.97 (not 100%)  OK")

    print("\nok:true checks:6")
    _sys.exit(0)
