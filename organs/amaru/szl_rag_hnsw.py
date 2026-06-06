#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. -- SZL Holdings
# ORCID: 0009-0001-0110-4173
#
# szl_rag_hnsw.py -- AMARU /v1/brain: HNSW approximate-nearest-neighbor index helper.
#
# Frontier formula F4 (round11): HNSW greedy-search navigability.
#   Malkov & Yashunin, "Efficient and robust approximate nearest neighbor search using
#   Hierarchical Navigable Small World graphs", arXiv:1603.09320 (2016);
#   IEEE TPAMI 42(4):824-836 (2020). https://www.pinecone.io/learn/series/faiss/hnsw/
#
# Lean proof of greedy-search termination (monotone descent + well-foundedness):
#   szl-holdings/lutar-lean
#   Lutar/Innovations/round11/FrontierHNSWNavigability.lean :: greedy_search_terminates
#
# Why this helps the running software:
#   amaru/szl_rag.py::search currently does a FLAT FAISS scan -- O(N) per query. As the
#   rag-corpus-v1 grows this is the retrieval bottleneck. Building a FAISS HNSW index
#   makes each greedy descent visit ~O(log N) nodes -> /v1/brain returns top-k cites
#   faster at high recall.
#
# HONESTY: ADDITIVE. Builds an IndexHNSWFlat when FAISS is available; on any failure it
# returns None so the caller transparently falls back to the existing flat index. Cited
# chunk_ids remain real (this only changes which index does the lookup, not the corpus).

from __future__ import annotations

from typing import Any, Optional

# Tuned defaults (Malkov-Yashunin): M = graph degree, efConstruction = build breadth,
# efSearch = query-time breadth (recall/latency knob).
DEFAULT_M = 32
DEFAULT_EF_CONSTRUCTION = 200
DEFAULT_EF_SEARCH = 64


def build_hnsw_index(
    embeddings: "Any",
    *,
    M: int = DEFAULT_M,
    ef_construction: int = DEFAULT_EF_CONSTRUCTION,
    ef_search: int = DEFAULT_EF_SEARCH,
) -> Optional["Any"]:
    """Build a FAISS IndexHNSWFlat over L2-normalized embeddings (cosine via inner
    product on the normalized vectors).

    Returns the index, or None if FAISS is unavailable / build fails (caller falls back
    to the existing flat index). Never raises into the request path.
    """
    try:
        import faiss  # type: ignore
        import numpy as np  # noqa: F401

        emb = embeddings.astype("float32")
        dim = emb.shape[1]
        # METRIC_INNER_PRODUCT on normalized vectors == cosine similarity, matching the
        # existing flat index semantics in szl_rag.search.
        index = faiss.IndexHNSWFlat(dim, M, faiss.METRIC_INNER_PRODUCT)
        index.hnsw.efConstruction = ef_construction
        index.hnsw.efSearch = ef_search
        index.add(emb)
        return index
    except Exception:
        return None


def search_hnsw(index: "Any", query_embedding: "Any", k: int) -> Optional[tuple]:
    """Greedy ANN search. Returns (D, I) like faiss flat search, or None on failure.

    The greedy descent provably terminates at a local optimum (Lean
    FrontierHNSWNavigability.greedy_search_terminates) -- the returned top-k cite.
    """
    try:
        D, I = index.search(query_embedding, k)
        return D, I
    except Exception:
        return None


def index_meta(index: "Any") -> dict:
    """Report the HNSW knobs for the /v1/brain debug surface."""
    try:
        return {
            "kind": "hnsw",
            "efSearch": int(index.hnsw.efSearch),
            "efConstruction": int(index.hnsw.efConstruction),
            "ntotal": int(index.ntotal),
            "formula": "hnsw-navigable-small-world",
            "lean_ref": "Lutar/Innovations/round11/FrontierHNSWNavigability.lean",
        }
    except Exception:
        return {"kind": "hnsw", "formula": "hnsw-navigable-small-world"}


__all__ = ["build_hnsw_index", "search_hnsw", "index_meta",
           "DEFAULT_M", "DEFAULT_EF_CONSTRUCTION", "DEFAULT_EF_SEARCH"]
