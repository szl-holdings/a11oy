#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
"""HNSW k-NN retrieval — cortex companion helper (amaru OWNS retrieval).

HONEST OWNERSHIP NOTE: the cortex/RAG retrieval organ is **amaru** (``amaru/szl_rag.py``
+ ``amaru/szl_rag_hnsw.py``). a11oy is the brand-orchestration front door and does NOT
host the corpus. This module is therefore a thin, HONEST companion: if FAISS is present
it builds a real HNSW index for an in-process companion corpus; if FAISS is absent (the
normal a11oy Space case) it returns an honest ``backend_available: False`` and defers to
amaru — it never fabricates retrieval results.

Published form (thesis_v22.pdf §2 — RAG retrieval): HNSW greedy navigable-small-world
search visits ~O(log N) nodes vs O(N) flat scan. Malkov & Yashunin, arXiv:1603.09320
(2016); IEEE TPAMI 42(4):824–836 (2020).

Lean theorem (round11): ``Lutar/Innovations/round11/FrontierHNSWNavigability.lean ::
greedy_search_terminates`` (monotone descent + well-foundedness → greedy search terminates).

CITATION: thesis_v22.pdf §2  ·  LEAN: Lutar/Innovations/round11/FrontierHNSWNavigability.lean::greedy_search_terminates
"""
from __future__ import annotations

from typing import Any, Optional

CITATION = "thesis_v22.pdf §2"
LEAN_THEOREM = "Lutar/Innovations/round11/FrontierHNSWNavigability.lean::greedy_search_terminates"

DEFAULT_M = 32
DEFAULT_EF_CONSTRUCTION = 200
DEFAULT_EF_SEARCH = 64

OWNER = "amaru"  # cortex/retrieval organ — a11oy delegates corpus retrieval here.


def backend_available() -> bool:
    try:
        import faiss  # type: ignore  # noqa: F401

        return True
    except Exception:
        return False


def build_hnsw_index(embeddings: "Any", *, M: int = DEFAULT_M,
                     ef_construction: int = DEFAULT_EF_CONSTRUCTION,
                     ef_search: int = DEFAULT_EF_SEARCH) -> Optional["Any"]:
    """Build a real FAISS IndexHNSWFlat (cosine via inner product on normalized vectors).

    Returns the index, or None if FAISS is unavailable (caller defers to amaru). Never
    raises into the request path; never fabricates an index.
    """
    try:
        import faiss  # type: ignore

        emb = embeddings.astype("float32")
        index = faiss.IndexHNSWFlat(emb.shape[1], M, faiss.METRIC_INNER_PRODUCT)
        index.hnsw.efConstruction = ef_construction
        index.hnsw.efSearch = ef_search
        index.add(emb)
        return index
    except Exception:
        return None


def search_hnsw(index: "Any", query_embedding: "Any", k: int) -> Optional[tuple]:
    try:
        return index.search(query_embedding, k)
    except Exception:
        return None


def status() -> dict:
    """Honest status surface — declares amaru ownership and backend availability."""
    avail = backend_available()
    return {
        "value": avail,
        "backend_available": avail,
        "owner_organ": OWNER,
        "note": ("FAISS present — a11oy can build a companion HNSW index"
                 if avail else
                 "FAISS absent — a11oy defers retrieval to amaru (honest stub, no fabrication)"),
        "citation": CITATION,
        "lean_theorem": LEAN_THEOREM,
    }


__all__ = ["backend_available", "build_hnsw_index", "search_hnsw", "status",
           "OWNER", "CITATION", "LEAN_THEOREM"]

# Doctrine v11 LOCKED — 749/14/163 — c7c0ba17 · Λ = Conjecture 1 (NEVER a theorem)
# SLSA L1 honest + L2 attested (public Sigstore+Rekor) where slsa-verifier confirms.
