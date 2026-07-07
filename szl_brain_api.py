# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11 LOCKED
# Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>
"""szl_brain_api.py — make the estate brain QUERYABLE / TRAVERSABLE.

WAVE 1 of the frontier program. a11oy_brain_graph.py already HARVESTS the real
estate into a node/link graph (GET /api/<ns>/v1/brain/graph) — but until now that
graph was build-only: you could render it in 3D, not *ask* it anything. This
module turns the SAME honest graph into a real server-side retrieval API:

  GET /api/<ns>/v1/brain/search    ?q=&k=      hybrid exact+vector top-k nodes
  GET /api/<ns>/v1/brain/neighbors ?id=&hops=  k-hop neighbourhood subgraph
  GET /api/<ns>/v1/brain/community ?id=        community of a node + summary
  GET /api/<ns>/v1/brain/subgraph  ?ids=       induced subgraph over ids
  GET /api/<ns>/v1/brain/salience  ?top=       PageRank salience ranking
  GET /api/<ns>/v1/brain/ask       ?q=         PPR grounding subgraph (+answer IF
                                               a sovereign model is reachable, ELSE
                                               honest UNAVAILABLE — never fabricated)
  GET /api/<ns>/v1/brain/stats                 node/edge/community counts, honest
                                               distinct-vs-total framing
  GET /api/<ns>/v1/brain/index                 index build status: stack chosen +
                                               fallbacks + honest tier labels

REUSE, NEVER RE-HARVEST: every node/edge comes from
a11oy_brain_graph.get_brain_graph(ns). This module invents no nodes, harvests
nothing, and restates no counts — it slices, ranks and traverses the honest graph.

EMBEDDED, ZERO EXTERNAL DB. Best-available stack, each tier honestly labelled and
degrading in the open (a truthful fallback beats a fake dependency):

  vectors      sqlite-vec IF importable ELSE numpy cosine ELSE pure-python cosine
  embeddings   local Ollama nomic-embed-text IF SZL_LOCAL_LLM_URL reachable
               ELSE deterministic hash-embedding  (labelled MODELED — a
               hash-embedding similarity is NEVER presented as MEASURED)
  communities  python-igraph Leiden IF importable
               ELSE networkx greedy_modularity_communities
  local RAG    HippoRAG-style Personalized PageRank (networkx.pagerank seeded by
               query-matched nodes)
  global RAG   GraphRAG-style community summaries
  merge        LightRAG-'mix' style (local subgraph ⊕ global community context)

Deterministic: the index is cached keyed by the CONTENT HASH of the graph, so it
rebuilds only when the underlying graph changes. Pure read — signs nothing,
appends to no provenance chain (receipts belong on writes, never on GETs).
"""

import datetime
import hashlib
import json
import math
import os
import re
import urllib.error
import urllib.request

from fastapi import FastAPI
from fastapi.responses import JSONResponse

import a11oy_brain_graph as _brain

# --------------------------------------------------------------------------- #
# Best-available libraries — each import is guarded; the tier is labelled by
# what actually loaded, never by what we wish had loaded.
# --------------------------------------------------------------------------- #
try:
    import networkx as _nx  # graph algorithms (pagerank, ego, communities)
    _HAVE_NX = True
except Exception:  # pragma: no cover - networkx is a core dep, but stay honest
    _nx = None
    _HAVE_NX = False

try:
    import numpy as _np
    _HAVE_NUMPY = True
except Exception:  # pragma: no cover
    _np = None
    _HAVE_NUMPY = False

try:  # optional embedded vector index
    import sqlite3
    import sqlite_vec as _sqlite_vec
    _HAVE_SQLITE_VEC = True
except Exception:
    _sqlite_vec = None
    _HAVE_SQLITE_VEC = False

try:  # optional Leiden community detection
    import igraph as _igraph
    _HAVE_IGRAPH = True
except Exception:
    _igraph = None
    _HAVE_IGRAPH = False

# Honest Doctrine v11 labels (verbatim — never upgraded).
LBL_MODELED = "MODELED"
LBL_UNAVAILABLE = "UNAVAILABLE"

EMBED_DIM = 256
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_PERSON_KINDS = _brain._PERSON_KINDS


def _tokens(*parts: str) -> list:
    """Lowercase alnum tokens (len>=2) from the given strings, in order."""
    out = []
    for p in parts:
        for t in _TOKEN_RE.findall((p or "").lower()):
            if len(t) >= 2:
                out.append(t)
    return out


# --------------------------------------------------------------------------- #
# Embeddings
# --------------------------------------------------------------------------- #
def _local_llm_url() -> str:
    return (os.environ.get("SZL_LOCAL_LLM_URL")
            or os.environ.get("OLLAMA_URL")
            or "").rstrip("/")


def _ollama_embed(texts: list, url: str, model: str = "nomic-embed-text",
                  timeout: float = 2.0):
    """Embed via a local Ollama server. Returns list[list[float]] or raises."""
    vecs = []
    for text in texts:
        body = json.dumps({"model": model, "prompt": text}).encode("utf-8")
        req = urllib.request.Request(
            f"{url}/api/embeddings", data=body,
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        emb = payload.get("embedding")
        if not emb:
            raise ValueError("ollama returned no embedding")
        vecs.append([float(x) for x in emb])
    return vecs


def _hash_embed_one(text: str, dim: int = EMBED_DIM) -> list:
    """Deterministic feature-hashed bag-of-tokens embedding (MODELED).

    A hash-embedding similarity is NEVER a MEASURED semantic similarity — it is a
    deterministic token-overlap proxy. Labelled MODELED everywhere it surfaces."""
    vec = [0.0] * dim
    for tok in _tokens(text):
        h = int(hashlib.blake2b(tok.encode("utf-8"), digest_size=8).hexdigest(), 16)
        idx = h % dim
        sign = 1.0 if (h >> 63) & 1 else -1.0
        vec[idx] += sign
    return vec


def _l2_normalize(vec: list) -> list:
    norm = math.sqrt(sum(x * x for x in vec))
    if norm == 0.0:
        return vec
    return [x / norm for x in vec]


class _Embedder:
    """Chooses the best embedding source at build time and stays there."""

    def __init__(self):
        self.model = "nomic-embed-text"
        url = _local_llm_url()
        self.source = "hash-fallback"
        self.tier = LBL_MODELED
        self.dim = EMBED_DIM
        self._use_ollama = False
        if url:
            try:  # probe once with a trivial text
                probe = _ollama_embed(["a11oy"], url, self.model, timeout=2.0)
                self._url = url
                self.dim = len(probe[0])
                self.source = f"ollama:{self.model}"
                self._use_ollama = True
            except Exception:
                self._use_ollama = False

    def embed(self, texts: list) -> list:
        if self._use_ollama:
            try:
                raw = _ollama_embed(texts, self._url, self.model, timeout=4.0)
                return [_l2_normalize(v) for v in raw]
            except Exception:
                # A mid-flight failure downgrades honestly rather than erroring.
                self._use_ollama = False
                self.source = "hash-fallback"
        return [_l2_normalize(_hash_embed_one(t, self.dim)) for t in texts]


def _cosine(a: list, b: list) -> float:
    return sum(x * y for x, y in zip(a, b))


# --------------------------------------------------------------------------- #
# The queryable index over the honest graph.
# --------------------------------------------------------------------------- #
class BrainIndex:
    """A retrieval index built over a11oy_brain_graph.get_brain_graph(ns).

    Holds: node table, a directed weighted graph (for PageRank), an undirected
    graph (for neighbourhoods/communities), node embeddings + a vector backend,
    and community assignments + summaries. Deterministic; keyed by content hash."""

    def __init__(self, ns: str, graph: dict):
        self.ns = ns
        self.graph = graph
        self.content_hash = _content_hash(graph)
        self.nodes = graph.get("nodes", [])
        self.links = graph.get("links", [])
        self.by_id = {n["id"]: n for n in self.nodes}
        self.ids = [n["id"] for n in self.nodes]
        self._pos = {nid: i for i, nid in enumerate(self.ids)}

        self._build_graphs()
        self._build_embeddings()
        self._build_communities()
        self._pagerank_global = self._compute_pagerank(None)

    # ---- graph structures -------------------------------------------------- #
    def _build_graphs(self):
        if _HAVE_NX:
            dg = _nx.DiGraph()
            dg.add_nodes_from(self.ids)
            for l in self.links:
                s, t = l["source"], l["target"]
                if s in self.by_id and t in self.by_id:
                    w = dg.get_edge_data(s, t, {}).get("weight", 0.0) + 1.0
                    dg.add_edge(s, t, weight=w)
            self.DG = dg
            self.UG = dg.to_undirected(as_view=False)
        else:  # pragma: no cover - networkx is present in this estate
            self.DG = None
            self.UG = None
        # Pure-python adjacency (used for neighbours if networkx is absent).
        adj: dict = {nid: set() for nid in self.ids}
        for l in self.links:
            s, t = l["source"], l["target"]
            if s in adj and t in adj:
                adj[s].add(t)
                adj[t].add(s)
        self.adj = adj

    # ---- embeddings + vector backend -------------------------------------- #
    def _node_text(self, n: dict) -> str:
        return " ".join(str(x) for x in (
            n.get("kind", ""), n.get("title", ""), n.get("id", ""),
            n.get("axis") or "", n.get("source") or "") if x)

    def _build_embeddings(self):
        self.embedder = _Embedder()
        texts = [self._node_text(n) for n in self.nodes]
        self.embeddings = self.embedder.embed(texts) if texts else []
        self.embed_source = self.embedder.source
        self.embed_tier = self.embedder.tier  # always MODELED
        self.embed_dim = self.embedder.dim
        self._init_vector_backend()

    def _init_vector_backend(self):
        self.vector_backend = "python-cosine"
        self._np_matrix = None
        self._vec_db = None
        if _HAVE_SQLITE_VEC and self.embeddings:
            try:
                db = sqlite3.connect(":memory:")
                db.enable_load_extension(True)
                _sqlite_vec.load(db)
                db.enable_load_extension(False)
                db.execute(
                    f"CREATE VIRTUAL TABLE vec USING vec0("
                    f"emb float[{self.embed_dim}])")
                for i, emb in enumerate(self.embeddings):
                    db.execute("INSERT INTO vec(rowid, emb) VALUES (?, ?)",
                               (i, json.dumps(emb)))
                db.commit()
                self._vec_db = db
                self.vector_backend = "sqlite-vec"
                return
            except Exception:
                self._vec_db = None
        if _HAVE_NUMPY and self.embeddings:
            self._np_matrix = _np.asarray(self.embeddings, dtype="float32")
            self.vector_backend = "numpy-cosine"

    def _vector_scores(self, qvec: list) -> list:
        """Cosine of qvec against every node embedding (index-aligned)."""
        if not self.embeddings:
            return []
        if self.vector_backend == "sqlite-vec" and self._vec_db is not None:
            try:
                rows = self._vec_db.execute(
                    "SELECT rowid, distance FROM vec "
                    "WHERE emb MATCH ? ORDER BY distance LIMIT ?",
                    (json.dumps(qvec), len(self.ids))).fetchall()
                scores = [0.0] * len(self.ids)
                for rowid, dist in rows:
                    # vec0 default is L2; embeddings are L2-normalised so
                    # cosine = 1 - dist^2 / 2.
                    scores[rowid] = 1.0 - (float(dist) ** 2) / 2.0
                return scores
            except Exception:
                pass
        if self.vector_backend == "numpy-cosine" and self._np_matrix is not None:
            q = _np.asarray(qvec, dtype="float32")
            return list(map(float, self._np_matrix @ q))
        return [_cosine(qvec, e) for e in self.embeddings]

    # ---- communities ------------------------------------------------------- #
    def _build_communities(self):
        self.community_of: dict = {}
        self.communities: dict = {}
        self.community_algo = "none"
        if not self.ids:
            return
        parts = None
        if _HAVE_IGRAPH and self.UG is not None:
            try:
                g = _igraph.Graph()
                g.add_vertices(self.ids)
                g.add_edges([(s, t) for s, t in self.UG.edges()])
                clustering = g.community_leiden(
                    objective_function="modularity")
                parts = [[g.vs[v]["name"] for v in comm] for comm in clustering]
                self.community_algo = "igraph-leiden"
            except Exception:
                parts = None
        if parts is None and _HAVE_NX and self.UG is not None:
            try:
                from networkx.algorithms.community import (
                    greedy_modularity_communities)
                comms = greedy_modularity_communities(self.UG)
                parts = [sorted(c) for c in comms]
                self.community_algo = "networkx-greedy-modularity"
            except Exception:
                parts = None
        if parts is None:  # last resort: connected components
            if _HAVE_NX and self.UG is not None:
                parts = [sorted(c) for c in _nx.connected_components(self.UG)]
            else:
                parts = self._components_purepy()
            self.community_algo = "connected-components"

        parts = sorted(parts, key=lambda c: (-len(c), c[0] if c else ""))
        for cidx, members in enumerate(parts):
            cid = f"c{cidx}"
            self.communities[cid] = members
            for m in members:
                self.community_of[m] = cid
        self.community_summaries = {
            cid: self._summarize_community(cid, members)
            for cid, members in self.communities.items()}

    def _components_purepy(self) -> list:
        seen = set()
        comps = []
        for start in self.ids:
            if start in seen:
                continue
            stack = [start]
            comp = []
            while stack:
                x = stack.pop()
                if x in seen:
                    continue
                seen.add(x)
                comp.append(x)
                stack.extend(self.adj.get(x, ()))
            comps.append(sorted(comp))
        return comps

    def _summarize_community(self, cid: str, members: list) -> dict:
        kinds: dict = {}
        for m in members:
            n = self.by_id.get(m, {})
            kinds[n.get("kind", "?")] = kinds.get(n.get("kind", "?"), 0) + 1
        top = sorted(
            members,
            key=lambda m: (-(self.by_id.get(m, {}).get("degree", 0)), m))[:8]
        top_nodes = [{"id": m,
                      "title": self.by_id.get(m, {}).get("title", m),
                      "kind": self.by_id.get(m, {}).get("kind"),
                      "degree": self.by_id.get(m, {}).get("degree", 0)}
                     for m in top]
        labels = sorted({self.by_id.get(m, {}).get("title", "")
                         for m in top if self.by_id.get(m, {}).get("title")})[:5]
        return {
            "id": cid,
            "label": LBL_MODELED,
            "size": len(members),
            "by_kind": dict(sorted(kinds.items(), key=lambda kv: (-kv[1], kv[0]))),
            "top_nodes": top_nodes,
            "summary": (f"community {cid}: {len(members)} nodes, "
                        f"dominant kinds {', '.join(list(kinds)[:3])}; "
                        f"anchors: {', '.join(labels)}"),
        }

    # ---- pagerank ---------------------------------------------------------- #
    def _compute_pagerank(self, personalization) -> dict:
        if _HAVE_NX and self.DG is not None and self.DG.number_of_nodes():
            try:
                return _nx.pagerank(self.DG, alpha=0.85,
                                    personalization=personalization,
                                    weight="weight")
            except Exception:
                pass
        # Pure-python power iteration fallback on the undirected adjacency.
        return self._pagerank_purepy(personalization)

    def _pagerank_purepy(self, personalization, iters: int = 50,
                         damping: float = 0.85) -> dict:
        n = len(self.ids)
        if n == 0:
            return {}
        if personalization:
            tot = sum(personalization.values()) or 1.0
            teleport = {nid: personalization.get(nid, 0.0) / tot
                        for nid in self.ids}
        else:
            teleport = {nid: 1.0 / n for nid in self.ids}
        rank = {nid: 1.0 / n for nid in self.ids}
        for _ in range(iters):
            nxt = {nid: (1.0 - damping) * teleport[nid] for nid in self.ids}
            dangling = 0.0
            for nid in self.ids:
                nbrs = self.adj.get(nid, ())
                if not nbrs:
                    dangling += rank[nid]
                    continue
                share = damping * rank[nid] / len(nbrs)
                for m in nbrs:
                    nxt[m] += share
            if dangling:
                for nid in self.ids:
                    nxt[nid] += damping * dangling * teleport[nid]
            rank = nxt
        return rank

    # ---- retrieval primitives --------------------------------------------- #
    def search(self, q: str, k: int = 10) -> list:
        """Hybrid exact(token/substring) + vector(cosine) top-k nodes."""
        qtokens = set(_tokens(q))
        qlower = (q or "").lower().strip()
        qvec = self.embedder.embed([q])[0] if q else None
        vscores = self._vector_scores(qvec) if qvec else [0.0] * len(self.ids)
        results = []
        for i, n in enumerate(self.nodes):
            ntokens = set(_tokens(self._node_text(n)))
            overlap = len(qtokens & ntokens)
            exact = 0.0
            if qtokens:
                exact = overlap / max(1, len(qtokens))
            substr = 0.0
            if qlower and (qlower in str(n.get("title", "")).lower()
                           or qlower in str(n.get("id", "")).lower()):
                substr = 1.0
            vec = vscores[i] if i < len(vscores) else 0.0
            score = 0.5 * exact + 0.35 * vec + 0.15 * substr
            if score <= 0.0:
                continue
            results.append((score, exact, vec, substr, n))
        results.sort(key=lambda r: (-r[0], r[4]["id"]))
        out = []
        for score, exact, vec, substr, n in results[:max(1, k)]:
            out.append({
                "id": n["id"], "title": n.get("title", n["id"]),
                "kind": n.get("kind"), "layer": n.get("layer"),
                "degree": n.get("degree", 0),
                "node_label": n.get("label"),
                "score": round(score, 6),
                "match": {"exact_token_overlap": round(exact, 4),
                          "vector_cosine": round(vec, 6),
                          "substring": bool(substr)},
                "community": self.community_of.get(n["id"]),
            })
        return out

    def neighbors(self, nid: str, hops: int = 1) -> dict:
        hops = max(1, min(hops, 4))
        if nid not in self.by_id:
            return {}
        frontier = {nid}
        seen = {nid}
        for _ in range(hops):
            nxt = set()
            for x in frontier:
                for m in self.adj.get(x, ()):
                    if m not in seen:
                        nxt.add(m)
            seen |= nxt
            frontier = nxt
            if not frontier:
                break
        return self._induced(seen, center=nid, hops=hops)

    def subgraph(self, ids: list) -> dict:
        present = [i for i in ids if i in self.by_id]
        return self._induced(set(present), requested=ids)

    def _induced(self, id_set: set, **meta) -> dict:
        nodes = [self._node_view(self.by_id[i]) for i in self.ids if i in id_set]
        links = [dict(l) for l in self.links
                 if l["source"] in id_set and l["target"] in id_set]
        out = {
            "label": LBL_MODELED,
            "node_count": len(nodes),
            "link_count": len(links),
            "nodes": nodes, "links": links,
        }
        out.update(meta)
        return out

    def _node_view(self, n: dict) -> dict:
        v = {"id": n["id"], "title": n.get("title", n["id"]),
             "kind": n.get("kind"), "layer": n.get("layer"),
             "degree": n.get("degree", 0),
             "salience": round(self._pagerank_global.get(n["id"], 0.0), 8),
             "community": self.community_of.get(n["id"]),
             "node_label": n.get("label")}
        for opt in ("url", "source", "axis", "formula_id", "locked",
                    "conjecture", "proof_status"):
            if n.get(opt) is not None:
                v[opt] = n[opt]
        return v

    def salience(self, top: int = 25) -> list:
        ranked = sorted(self._pagerank_global.items(),
                        key=lambda kv: (-kv[1], kv[0]))[:max(1, top)]
        return [{"id": nid,
                 "title": self.by_id.get(nid, {}).get("title", nid),
                 "kind": self.by_id.get(nid, {}).get("kind"),
                 "salience": round(score, 8),
                 "degree": self.by_id.get(nid, {}).get("degree", 0),
                 "community": self.community_of.get(nid)}
                for nid, score in ranked]

    def community(self, nid: str) -> dict:
        cid = self.community_of.get(nid)
        if cid is None:
            return {}
        summ = dict(self.community_summaries.get(cid, {}))
        summ["members"] = self.communities.get(cid, [])
        summ["queried_node"] = nid
        return summ

    def ask(self, q: str, k: int = 12) -> dict:
        """HippoRAG-style PPR local retrieval ⊕ GraphRAG community context.

        Returns a REAL grounding subgraph regardless. Generated prose is ONLY
        produced if a sovereign model is reachable; otherwise it is honestly
        UNAVAILABLE — never fabricated."""
        seeds = self.search(q, k=max(5, k))
        seed_ids = [s["id"] for s in seeds]
        personalization = None
        if seed_ids:
            personalization = {nid: 0.0 for nid in self.ids}
            for s in seeds:
                personalization[s["id"]] = max(s["score"], 1e-6)
        ppr = self._compute_pagerank(personalization)
        ranked = sorted(ppr.items(), key=lambda kv: (-kv[1], kv[0]))
        # Grounding node set: seeds + top PPR nodes (local retrieval).
        ground_ids = list(dict.fromkeys(
            seed_ids + [nid for nid, _ in ranked[:k]]))
        grounding = self._induced(set(ground_ids))
        for n in grounding["nodes"]:
            n["ppr"] = round(ppr.get(n["id"], 0.0), 8)
        grounding["nodes"].sort(key=lambda n: (-n.get("ppr", 0.0), n["id"]))
        # Global retrieval: community summaries covering the grounding set.
        cids = []
        for nid in ground_ids:
            cid = self.community_of.get(nid)
            if cid and cid not in cids:
                cids.append(cid)
        global_ctx = [self.community_summaries[c] for c in cids[:5]
                      if c in self.community_summaries]

        answer, answer_label, model = self._maybe_generate(q, grounding, global_ctx)
        return {
            "label": LBL_MODELED,
            "query": q,
            "retrieval": "hippoRAG-PPR(local) ⊕ graphRAG-community(global), "
                         "LightRAG-mix merge",
            "seeds": seeds,
            "grounding_subgraph": grounding,
            "cited_node_ids": ground_ids,
            "community_context": global_ctx,
            "answer": answer,
            "answer_label": answer_label,
            "answer_model": model,
            "note": ("grounding_subgraph is REAL (retrieved from the honest brain "
                     "graph) whether or not a sovereign model was reachable; "
                     "generated prose is UNAVAILABLE unless a local model answered."),
        }

    def _maybe_generate(self, q, grounding, global_ctx):
        """Return (answer, label, model). Never fabricates — no model => None."""
        url = _local_llm_url()
        model = os.environ.get("SZL_LOCAL_LLM_MODEL", "").strip()
        if not url or not model:
            return None, LBL_UNAVAILABLE, None
        cited = ", ".join(n["id"] for n in grounding["nodes"][:12])
        ctx_lines = [f"- {n['id']}: {n.get('title')}"
                     for n in grounding["nodes"][:12]]
        ctx = "\n".join(ctx_lines)
        prompt = (
            "Answer ONLY from the grounding nodes below. Cite node ids you use. "
            "If they do not contain the answer, say so.\n\n"
            f"Question: {q}\n\nGrounding nodes:\n{ctx}\n\n"
            f"(available node ids: {cited})")
        try:
            body = json.dumps({"model": model, "prompt": prompt,
                               "stream": False}).encode("utf-8")
            req = urllib.request.Request(
                f"{url}/api/generate", data=body,
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=20.0) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            text = (payload.get("response") or "").strip()
            if not text:
                return None, LBL_UNAVAILABLE, None
            # A locally-generated, graph-grounded answer is MODELED, never
            # MEASURED — it is a model's prose over a real subgraph.
            return text, LBL_MODELED, f"{url.split('//')[-1]}:{model}"
        except Exception:
            return None, LBL_UNAVAILABLE, None

    def stats(self) -> dict:
        g = self.graph
        comm_sizes = sorted((len(m) for m in self.communities.values()),
                            reverse=True)
        return {
            "label": LBL_MODELED,
            "ns": self.ns,
            "content_hash": self.content_hash,
            "node_count": g.get("node_count", len(self.nodes)),
            "link_count": g.get("link_count", len(self.links)),
            "distinct_artifacts": g.get("distinct_artifacts"),
            "person_node_count": g.get("person_node_count"),
            "artifact_note": g.get("artifact_note"),
            "community_count": len(self.communities),
            "community_algo": self.community_algo,
            "largest_communities": comm_sizes[:10],
            "by_kind": g.get("summary", {}).get("by_kind"),
            "by_layer": g.get("summary", {}).get("by_layer"),
            "index": self.index_status(),
            "note": ("counts are the honest totals from a11oy_brain_graph "
                     "(reused, never restated). distinct_artifacts excludes arXiv "
                     "co-author person nodes; never present the raw total as all "
                     "distinct work."),
        }

    def index_status(self) -> dict:
        return {
            "label": LBL_MODELED,
            "content_hash": self.content_hash,
            "node_count": len(self.nodes),
            "link_count": len(self.links),
            "embed_source": self.embed_source,
            "embed_tier": self.embed_tier,
            "embed_dim": self.embed_dim,
            "vector_backend": self.vector_backend,
            "community_algo": self.community_algo,
            "community_count": len(self.communities),
            "pagerank": "networkx" if (_HAVE_NX and self.DG is not None)
                        else "pure-python",
            "stack": {
                "networkx": _HAVE_NX,
                "numpy": _HAVE_NUMPY,
                "sqlite_vec": _HAVE_SQLITE_VEC,
                "igraph": _HAVE_IGRAPH,
                "ollama_embeddings": self.embed_source.startswith("ollama"),
            },
            "note": ("hash-embedding similarity is MODELED (a deterministic "
                     "token-overlap proxy), NEVER MEASURED."),
        }


def _content_hash(graph: dict) -> str:
    h = hashlib.sha256()
    for n in graph.get("nodes", []):
        h.update(n["id"].encode("utf-8"))
        h.update(b"\x00")
    h.update(b"||links||")
    for l in graph.get("links", []):
        h.update(f"{l['source']}>{l['target']}:{l.get('rel','')}".encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()[:16]


# --------------------------------------------------------------------------- #
# Cache — one index per (ns, content_hash); rebuilt only when the graph changes.
# --------------------------------------------------------------------------- #
_INDEX_CACHE: dict = {}


def get_index(ns: str = "a11oy", *, refresh: bool = False) -> BrainIndex:
    graph = _brain.get_brain_graph(ns, refresh=refresh)
    chash = _content_hash(graph)
    cached = _INDEX_CACHE.get(ns)
    if cached is None or cached.content_hash != chash or refresh:
        _INDEX_CACHE[ns] = BrainIndex(ns, graph)
    return _INDEX_CACHE[ns]


# --------------------------------------------------------------------------- #
# FastAPI registration — additive, before the SPA catch-all. Pure reads.
# --------------------------------------------------------------------------- #
def register(app: FastAPI, ns: str = "a11oy") -> str:
    base = f"/api/{ns}/v1/brain"

    @app.get(f"{base}/search")
    async def brain_search(q: str = "", k: int = 10):  # noqa: ANN202
        idx = get_index(ns)
        return JSONResponse({"label": LBL_MODELED, "query": q, "k": k,
                             "results": idx.search(q, k),
                             "index": idx.index_status()})

    @app.get(f"{base}/neighbors")
    async def brain_neighbors(id: str = "", hops: int = 1):  # noqa: ANN202,A002
        idx = get_index(ns)
        sub = idx.neighbors(id, hops)
        if not sub:
            return JSONResponse(
                {"label": LBL_UNAVAILABLE, "error": f"unknown node id: {id!r}",
                 "id": id}, status_code=404)
        return JSONResponse(sub)

    @app.get(f"{base}/community")
    async def brain_community(id: str = ""):  # noqa: ANN202,A002
        idx = get_index(ns)
        c = idx.community(id)
        if not c:
            return JSONResponse(
                {"label": LBL_UNAVAILABLE, "error": f"unknown node id: {id!r}",
                 "id": id}, status_code=404)
        return JSONResponse(c)

    @app.get(f"{base}/subgraph")
    async def brain_subgraph(ids: str = ""):  # noqa: ANN202
        idx = get_index(ns)
        id_list = [x for x in re.split(r"[,\s]+", ids.strip()) if x]
        return JSONResponse(idx.subgraph(id_list))

    @app.get(f"{base}/salience")
    async def brain_salience(top: int = 25):  # noqa: ANN202
        idx = get_index(ns)
        return JSONResponse({"label": LBL_MODELED, "top": top,
                             "ranking": idx.salience(top),
                             "method": "PageRank (α=0.85)"})

    @app.get(f"{base}/ask")
    async def brain_ask(q: str = "", k: int = 12):  # noqa: ANN202
        idx = get_index(ns)
        return JSONResponse(idx.ask(q, k))

    @app.get(f"{base}/stats")
    async def brain_stats():  # noqa: ANN202
        return JSONResponse(get_index(ns).stats())

    @app.get(f"{base}/index")
    async def brain_index():  # noqa: ANN202
        return JSONResponse(get_index(ns).index_status())

    idx = get_index(ns)
    st = idx.index_status()
    return (f"brain-api mounted: GET {base}/"
            f"{{search,neighbors,community,subgraph,salience,ask,stats,index}} "
            f"({st['node_count']} nodes, {st['community_count']} communities via "
            f"{st['community_algo']}; vectors={st['vector_backend']}, "
            f"embeddings={st['embed_source']} [{st['embed_tier']}]; "
            f"0 sign-on-read)")


# --------------------------------------------------------------------------- #
# Self-test — runs against the REAL reused graph.
# --------------------------------------------------------------------------- #
def _selftest() -> None:
    idx = get_index("a11oy")
    assert idx.nodes, "index must reuse a non-empty brain graph"
    assert idx.content_hash and len(idx.content_hash) == 16, "content hash"

    st = idx.index_status()
    assert st["embed_tier"] == LBL_MODELED, "embeddings are MODELED, never MEASURED"
    assert st["vector_backend"] in (
        "sqlite-vec", "numpy-cosine", "python-cosine"), st["vector_backend"]
    assert st["community_count"] >= 1, "at least one community"

    # search: a token that exists in the estate graph.
    res = idx.search("brain graph", k=5)
    assert res, "search must return results for an estate term"
    assert all("score" in r and "match" in r for r in res), "honest scoring"
    assert res == sorted(res, key=lambda r: (-r["score"], r["id"])), "sorted"

    # neighbors: pick the highest-degree node and expand 1 hop.
    hub = max(idx.nodes, key=lambda n: n.get("degree", 0))["id"]
    nb = idx.neighbors(hub, hops=1)
    assert nb["node_count"] >= 1, "hub must have a neighbourhood"
    ids = {n["id"] for n in nb["nodes"]}
    assert all(l["source"] in ids and l["target"] in ids
               for l in nb["links"]), "induced links stay within the subgraph"

    # community lookup + summary.
    c = idx.community(hub)
    assert c and c["size"] >= 1 and c["label"] == LBL_MODELED, "community summary"

    # subgraph over explicit ids.
    some = [n["id"] for n in idx.nodes[:5]]
    sg = idx.subgraph(some)
    assert sg["node_count"] == len(some), "induced subgraph over requested ids"

    # salience: PageRank ranking is sorted and sums≈1 over all nodes.
    sal = idx.salience(top=10)
    assert sal and sal == sorted(sal, key=lambda r: (-r["salience"], r["id"]))
    tot = sum(idx._pagerank_global.values())
    assert abs(tot - 1.0) < 1e-3, f"pagerank must sum to ~1, got {tot}"

    # ask: grounding subgraph is REAL; prose UNAVAILABLE without a model.
    a = idx.ask("what proves the estate thesis", k=8)
    assert a["grounding_subgraph"]["node_count"] >= 1, "real grounding subgraph"
    assert a["cited_node_ids"], "cited node ids present"
    if a["answer_model"] is None:
        assert a["answer"] is None and a["answer_label"] == LBL_UNAVAILABLE, \
            "no model => UNAVAILABLE, never a fabricated answer"

    # stats: honest distinct-vs-total framing reused from the builder.
    s = idx.stats()
    assert s["node_count"] == idx.graph["node_count"], "reuse builder node_count"
    assert s["distinct_artifacts"] == idx.graph["distinct_artifacts"], \
        "reuse builder distinct_artifacts (never restated)"
    assert s["community_count"] == len(idx.communities)

    # cache: same content hash => same object (no needless rebuild).
    assert get_index("a11oy") is idx, "index cached by content hash"

    print(f"szl_brain_api: ALL OK — {st['node_count']} nodes, "
          f"{st['community_count']} communities via {st['community_algo']}; "
          f"vectors={st['vector_backend']}, embeddings={st['embed_source']} "
          f"[{st['embed_tier']}]; pagerank sum={tot:.6f}; "
          f"content_hash={idx.content_hash}")


if __name__ == "__main__":
    _selftest()
