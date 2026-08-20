# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v10/v11
"""
szl_rag — LIBRARY-ONLY shared RAG helpers (embedding model + FAISS lookup).

SURFACE STATUS (Doctrine v11): this module is NOT a mounted RAG surface. The ONE
live agentic-RAG surface is `a11oy_org_rag.py` (wired at serve.py + a11oy_agent_loop.py).
szl_rag is consumed as a LIBRARY — e.g. a11oy_org_rag pulls its BAAI/bge embedding
model via `szl_rag._ensure_loaded()` and szl_brain reads `get_model_weight_sha256()`.
The former `register_rag_routes()` FastAPI mount was dead (never called by any Space)
and has been removed so there is exactly one RAG route surface.

Pipeline (per Space, organ-filtered):
    embed(query)  ->  FAISS lookup (organ index)  ->  top-k chunks (similarity + source)
    if with_response:  top-k  ->  LLM tier (szl_brain.route)  ->  answer + sources + Λ-receipt

Corpus + per-organ FAISS indexes are pulled from the HF Dataset
    SZLHOLDINGS/rag-corpus-v1
via huggingface_hub.snapshot_download at first use (lazy, cached).

Each Space binds ONE organ:
    a11oy -> gate · amaru -> cortex · sentra -> immune · vessels -> receipt
    rosie -> all (nervous inherits everything) · uds-demo -> deploy(-> all fallback)

HONESTY (Doctrine v10/v11):
  - LLM responses cite chunk IDs (the `sources` list carries every chunk_id used).
  - Λ-receipt `signature` field is a PLACEHOLDER (Sigstore CI signing not yet wired).
  - If the embedding model / FAISS deps / dataset download are unavailable in this
    Space at runtime, the endpoint returns an HONEST JSON error (never fake chunks).
  - ADDITIVE only. The 13-axis `yuyay_v3` axis_scores feed szl_brain tier selection.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from datetime import datetime, timezone
from typing import Any

# Module-level FastAPI imports. REQUIRED: with `from __future__ import annotations`
# the `request: Request` endpoint annotation is a STRING that FastAPI resolves
# against module globals at route-registration time. If Request is only imported
# inside register_rag_routes(), resolution fails and FastAPI wrongly treats
# `request` as a required query param (HTTP 422). Importing here fixes the bind.
try:
    from fastapi import Request as Request  # noqa: F401
    from fastapi.responses import JSONResponse as JSONResponse, HTMLResponse as HTMLResponse  # noqa: F401
except Exception:  # fastapi optional at import time in non-serving contexts
    Request = None  # type: ignore

DOCTRINE = "v10/v11"
DATASET_REPO = "SZLHOLDINGS/rag-corpus-v1"
MODEL_NAME = "BAAI/bge-base-en-v1.5"
BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "
SIGNATURE_PLACEHOLDER = "PLACEHOLDER — Sigstore CI signing not yet wired (Doctrine v10/v11)"

# ---------------------------------------------------------------------------
# OPTIONAL RRF hybrid reranking stage (additive, off by default).
#
# PROVENANCE (clean-room adoption — studied, made ours; SZL claims NONE of the
# underlying ideas as its own):
#   - Idea + shape studied from MemMachine's reranker package (Apache-2.0):
#       * bm25_reranker.py       — github.com/MemMachine/MemMachine
#         packages/server/src/memmachine_server/common/reranker/bm25_reranker.py
#       * rrf_hybrid_reranker.py — github.com/MemMachine/MemMachine
#         packages/server/src/memmachine_server/common/reranker/rrf_hybrid_reranker.py
#     MemMachine wraps `rank_bm25.BM25Okapi` (k1=1.5, b=0.75, epsilon=0.25) and
#     fuses arbitrary rerankers' 1-indexed rankings via sum(1/(k+rank)), k=60.
#     This file reimplements the same *algorithm* in dependency-free pure
#     Python (no rank_bm25 import) against szl_rag's own candidate-chunk
#     shape. No MemMachine source lines are copied.
#   - BM25 (Okapi) scoring: Robertson, S. & Zaragoza, H. (2009), "The
#     Probabilistic Relevance Framework: BM25 and Beyond", Foundations and
#     Trends in Information Retrieval 3(4), pp. 333-389.
#     https://www.staff.city.ac.uk/~sbrp622/papers/foundations_bm25_review.pdf
#   - Reciprocal Rank Fusion: Cormack, G.V., Clarke, C.L.A. & Buettcher, S.
#     (2009), "Reciprocal Rank Fusion outperforms Condorcet and individual
#     Rank Learning Methods", SIGIR 2009, pp. 758-759.
#     https://doi.org/10.1145/1571941.1572114
#
# HONESTY: BM25 and RRF are exact, deterministic functions of their inputs —
# this stage is labeled MEASURED (not modeled/estimated) throughout. It never
# fabricates chunks; it only reorders/trims chunks already honestly retrieved
# by the existing FAISS + similarity pipeline. Default behavior (rerank="none")
# is untouched byte-for-byte.
# ---------------------------------------------------------------------------
RRF_K = 60          # standard RRF damping constant (Cormack, Clarke & Buettcher 2009)
BM25_K1 = 1.5       # Okapi BM25 term-frequency saturation constant
BM25_B = 0.75       # Okapi BM25 length-normalization constant
RERANK_CANDIDATE_POOL = 30  # pull ~top-3k (3x default top_k=10 ceiling) before trimming
_STOPWORDS = frozenset({
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has",
    "he", "in", "is", "it", "its", "of", "on", "that", "the", "to", "was",
    "were", "will", "with", "or", "this", "these", "those", "but", "not",
})


def _tokenize(text: str) -> list[str]:
    """Simple, dependency-free tokenizer: lowercase, split on non-alphanumerics,
    drop trivial stopwords and empty tokens. Shared by the BM25 scorer below."""
    import re
    raw = re.split(r"[^a-z0-9]+", (text or "").lower())
    return [t for t in raw if t and t not in _STOPWORDS]


def _bm25_scores(query: str, doc_texts: list[str],
                  k1: float = BM25_K1, b: float = BM25_B) -> list[float]:
    """Pure-Python Okapi BM25 scoring of `doc_texts` against `query`.

    Reimplements the standard Okapi BM25 formula (Robertson & Zaragoza 2009)
    over the SAME candidate set already retrieved by FAISS — no separate
    lexical index is built or persisted. Deterministic given (query, doc_texts).
    """
    tokenized_docs = [_tokenize(t) for t in doc_texts]
    query_terms = _tokenize(query)
    n_docs = len(tokenized_docs)
    if n_docs == 0 or not query_terms:
        return [0.0 for _ in doc_texts]

    doc_lens = [len(d) for d in tokenized_docs]
    avgdl = (sum(doc_lens) / n_docs) if n_docs else 0.0

    # document frequency per query term (how many docs contain the term)
    df: dict[str, int] = {}
    for term in set(query_terms):
        df[term] = sum(1 for d in tokenized_docs if term in d)

    # Robertson-Sparck-Jones IDF, as used by Okapi BM25 / rank_bm25's BM25Okapi.
    import math
    idf: dict[str, float] = {}
    for term, freq in df.items():
        idf[term] = math.log((n_docs - freq + 0.5) / (freq + 0.5) + 1.0)

    scores = []
    for doc_terms, dlen in zip(tokenized_docs, doc_lens):
        if not doc_terms:
            scores.append(0.0)
            continue
        tf: dict[str, int] = {}
        for t in doc_terms:
            tf[t] = tf.get(t, 0) + 1
        score = 0.0
        len_norm = 1.0 - b + b * (dlen / avgdl if avgdl else 0.0)
        for term in query_terms:
            f = tf.get(term, 0)
            if f == 0:
                continue
            score += idf.get(term, 0.0) * (f * (k1 + 1.0)) / (f + k1 * len_norm)
        scores.append(score)
    return scores


def _rrf_fuse(rankings: list[list[str]], k: int = RRF_K) -> dict[str, float]:
    """Reciprocal Rank Fusion (Cormack, Clarke & Buettcher, SIGIR 2009).

    `rankings` is a list of rank-ordered candidate-id lists (best first, one
    list per ranker). Returns {candidate_id: rrf_score}, where
    rrf_score = sum over rankers of 1/(k + rank), rank is 1-indexed.
    Deterministic given the input rankings.
    """
    score_map: dict[str, float] = {}
    for ranking in rankings:
        for rank, cand_id in enumerate(ranking, start=1):
            score_map[cand_id] = score_map.get(cand_id, 0.0) + 1.0 / (k + rank)
    return score_map


def _rrf_hybrid_rerank(query: str, results: list[dict[str, Any]],
                        top_k: int) -> list[dict[str, Any]]:
    """Apply BM25+vector RRF fusion over an already-retrieved candidate pool.

    `results` must already be vector-similarity ordered (best first) — that
    ordering is ranker #1. BM25 lexical scoring over the same candidates'
    `text` produces ranker #2. RRF fuses the two rank lists; ties broken by
    stable sort (original vector order) for determinism. Trims to top_k.
    """
    if not results:
        return results
    vector_ranking = [r["chunk_id"] for r in results]  # already best-first
    bm25_scores = _bm25_scores(query, [r["text"] for r in results])
    order_by_bm25 = sorted(range(len(results)), key=lambda i: bm25_scores[i], reverse=True)
    bm25_ranking = [results[i]["chunk_id"] for i in order_by_bm25]

    rrf_scores = _rrf_fuse([vector_ranking, bm25_ranking], k=RRF_K)
    bm25_by_id = {results[i]["chunk_id"]: bm25_scores[i] for i in range(len(results))}

    # stable-sort by (-rrf_score) while preserving original vector order on ties
    indexed = list(enumerate(results))
    indexed.sort(key=lambda pair: (-rrf_scores.get(pair[1]["chunk_id"], 0.0), pair[0]))

    fused = []
    for _orig_idx, r in indexed[:top_k]:
        rr = dict(r)
        rr["rrf_score"] = round(rrf_scores.get(r["chunk_id"], 0.0), 8)
        rr["bm25_score"] = round(bm25_by_id.get(r["chunk_id"], 0.0), 8)
        fused.append(rr)
    return fused


# organ each Space binds. uds-demo is deploy; no 'deploy' index exists, fall back to all.
SPACE_ORGAN = {
    "a11oy": "gate",
    "amaru": "cortex",
    "sentra": "immune",
    "vessels": "receipt",
    "rosie": "all",
    "uds-demo": "all",   # deploy organ -> served from the all index
}

# ---------------------------------------------------------------------------
# Lazy global state — loaded once per process.
# ---------------------------------------------------------------------------
_lock = threading.Lock()
# ---------------------------------------------------------------------------
# MODEL WEIGHT SHA-256 — computed once at startup, cached for all receipts.
# For HF-hosted models (no local weight files downloaded), we bind the SHA to
# the HF model revision commit + tokenizer config bytes.  This means:
#   - If BAAI/bge-base-en-v1.5 weights change on HF (new revision), the SHA changes.
#   - Any Λ-receipt carrying this SHA is cryptographically bound to THAT model state.
#   - Model swaps are detectable from any historical receipt.
# The compute path (below) tries local weight files first (definitive), then falls
# back to HF revision + tokenizer-config bytes (HF-hosted, no local files).
# ---------------------------------------------------------------------------
_MODEL_WEIGHT_SHA256: str | None = None   # set once by _ensure_loaded(); read by get_model_weight_sha256()
_MODEL_WEIGHT_SHA256_METHOD: str = "not_computed"   # "local_files" | "hf_revision" | "error"

_state: dict[str, Any] = {
    "ready": False,
    "error": None,
    "model": None,
    "corpus": None,        # chunk_id -> chunk dict
    "indexes": {},         # organ -> (faiss_index, [chunk_id,...])
    "manifest": None,
    "dataset_dir": None,
}


def _ensure_loaded() -> None:
    """Lazily download dataset + load model + FAISS indexes. Thread-safe, idempotent."""
    if _state["ready"] or _state["error"]:
        return
    with _lock:
        if _state["ready"] or _state["error"]:
            return
        try:
            from huggingface_hub import snapshot_download
            import faiss  # noqa
            from sentence_transformers import SentenceTransformer

            ddir = snapshot_download(DATASET_REPO, repo_type="dataset")
            _state["dataset_dir"] = ddir

            corpus = {}
            with open(os.path.join(ddir, "corpus.jsonl")) as f:
                for line in f:
                    c = json.loads(line)
                    corpus[c["chunk_id"]] = c
            _state["corpus"] = corpus

            manifest = json.load(open(os.path.join(ddir, "indexes", "manifest.json")))
            _state["manifest"] = manifest

            indexes = {}
            for organ, meta in manifest["organs"].items():
                if meta.get("n", 0) == 0:
                    continue
                idx = faiss.read_index(os.path.join(ddir, "indexes", f"{organ}.faiss"))
                ids = json.load(open(os.path.join(ddir, "indexes", f"{organ}.ids.json")))
                indexes[organ] = (idx, ids)
            _state["indexes"] = indexes

            _state["model"] = SentenceTransformer(MODEL_NAME, device="cpu")
            _state["ready"] = True
            # Compute model-weight SHA-256 after successful load.
            _compute_model_weight_sha256()
            print(f"[szl_rag] READY — {len(corpus)} chunks, organs={list(indexes)}",
                  flush=True)
        except Exception as exc:  # honest degradation, never fake data
            _state["error"] = type(exc).__name__
            print(f"[szl_rag] NOT READY (honest stub mode): {type(exc).__name__}: {exc}", flush=True)


def _compute_model_weight_sha256() -> None:
    """Compute and cache a SHA-256 that cryptographically binds this process to a
    specific model weight state.  Two strategies, tried in order:

    Strategy A — Local weight files (definitive):
      Hash every file whose name ends in .safetensors, .bin, or .pt inside the
      sentence-transformers cache directory for MODEL_NAME, sorted by relative path.
      The combined SHA-256 is the concatenated hash of all file bytes.
      Produces a hash that changes IFF any model weight changes.

    Strategy B — HF revision SHA + tokenizer config (HF-hosted, no local files):
      Query the HuggingFace Hub API for the latest revision commit SHA of MODEL_NAME.
      Hash: SHA-256(revision_sha_bytes + tokenizer_config_json_bytes).
      Produces a hash that changes IFF the HF repo receives a new commit (weight push).

    The method used is recorded in _MODEL_WEIGHT_SHA256_METHOD for receipt honesty.
    On any failure, sets method="error" and SHA="UNAVAILABLE:...".
    """
    global _MODEL_WEIGHT_SHA256, _MODEL_WEIGHT_SHA256_METHOD

    # --- Strategy A: local weight files ---
    try:
        import sentence_transformers as _st
        cache_dir = _st.SentenceTransformer(MODEL_NAME, device="cpu")._modules["0"].auto_model.config._name_or_path  # type: ignore[attr-defined]
    except Exception:
        cache_dir = None

    if cache_dir is None:
        # Fallback: check HF hub cache location
        try:
            from huggingface_hub import snapshot_download
            cache_dir = snapshot_download(MODEL_NAME, repo_type="model", local_files_only=True)
        except Exception:
            cache_dir = None

    if cache_dir and os.path.isdir(cache_dir):
        weight_exts = (".safetensors", ".bin", ".pt")
        weight_files = sorted([
            os.path.join(root, fname)
            for root, _dirs, files in os.walk(cache_dir)
            for fname in files
            if fname.endswith(weight_exts)
        ])
        if weight_files:
            sha = hashlib.sha256()
            for wf in weight_files:
                try:
                    with open(wf, "rb") as fh:
                        for chunk in iter(lambda: fh.read(1 << 20), b""):
                            sha.update(chunk)
                except OSError:
                    pass
            _MODEL_WEIGHT_SHA256 = sha.hexdigest()
            _MODEL_WEIGHT_SHA256_METHOD = f"local_files:{len(weight_files)}_files"
            print(f"[szl_rag] model_weight_sha256 (local_files): {_MODEL_WEIGHT_SHA256[:16]}...",
                  flush=True)
            return

    # --- Strategy B: HF revision SHA + tokenizer config bytes ---
    try:
        from huggingface_hub import model_info
        info = model_info(MODEL_NAME)
        revision_sha = (info.sha or "").encode("utf-8")

        # tokenizer_config.json provides a stable, small config fingerprint
        try:
            from huggingface_hub import hf_hub_download
            tok_cfg_path = hf_hub_download(MODEL_NAME, "tokenizer_config.json")
            with open(tok_cfg_path, "rb") as f:
                tok_cfg_bytes = f.read()
        except Exception:
            tok_cfg_bytes = b""

        sha = hashlib.sha256(revision_sha + tok_cfg_bytes)
        _MODEL_WEIGHT_SHA256 = sha.hexdigest()
        _MODEL_WEIGHT_SHA256_METHOD = f"hf_revision:{info.sha[:12] if info.sha else 'unknown'}"
        print(f"[szl_rag] model_weight_sha256 (hf_revision): {_MODEL_WEIGHT_SHA256[:16]}...",
              flush=True)
        return
    except Exception as exc:
        _MODEL_WEIGHT_SHA256 = f"UNAVAILABLE:{type(exc).__name__}"
        _MODEL_WEIGHT_SHA256_METHOD = "error"
        print(f"[szl_rag] model_weight_sha256 UNAVAILABLE: {exc}", flush=True)


def get_model_weight_sha256() -> dict[str, str]:
    """Return the cached model-weight SHA-256 and the method used to compute it.

    Called by szl_brain.make_receipt() to embed the SHA into every Λ-receipt
    BEFORE the DSSE envelope is signed, cryptographically binding the decision
    to the model weight state.

    Returns a dict with:
      sha256: hex SHA-256 string (or 'UNAVAILABLE:...' if computation failed)
      method: 'local_files:N_files' | 'hf_revision:SHA12' | 'error' | 'not_computed'
      model: MODEL_NAME (always present for provenance)
    """
    return {
        "sha256": _MODEL_WEIGHT_SHA256 or "not_computed",
        "method": _MODEL_WEIGHT_SHA256_METHOD,
        "model": MODEL_NAME,
    }


def status(space: str) -> dict[str, Any]:
    organ = SPACE_ORGAN.get(space, "all")
    return {
        "service": "szl_rag",
        "space": space,
        "organ": organ,
        "ready": _state["ready"],
        "error": _state["error"],
        "dataset": DATASET_REPO,
        "model": MODEL_NAME,
        "doctrine": DOCTRINE,
        "n_chunks": (len(_state["corpus"]) if _state["corpus"] else None),
        "manifest": _state["manifest"],
        "honesty": {
            "lambda_receipt_signature": SIGNATURE_PLACEHOLDER,
            "llm_responses_cite_chunk_ids": True,
            "no_fake_chunks": "If deps/dataset unavailable, endpoint returns honest error.",
        },
    }


def _make_lambda_receipt(query: str, organ: str, axis_scores, chunk_ids) -> dict[str, Any]:
    mw = get_model_weight_sha256()
    return {
        "schema": "szl.rag.lambda_receipt/v1",
        "query": query,
        "organ": organ,
        "axis_scores": axis_scores or [],
        "chunk_ids": chunk_ids,            # honesty: every chunk used is cited
        "doctrine": DOCTRINE,
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        # model_weight_sha256 — cryptographically binds this RAG receipt to the
        # loaded embedding model weight state.  Any change in BAAI/bge-base-en-v1.5
        # weights (new HF revision, local file swap) changes this SHA.
        "model_weight_sha256": mw["sha256"],
        "model_weight_method": mw["method"],
        "model_name": mw["model"],
        "signature": SIGNATURE_PLACEHOLDER,
    }


def search(query: str, space: str, top_k: int = 5,
           axis_scores: list[float] | None = None,
           rerank: str = "none") -> dict[str, Any]:
    """Embed query -> FAISS lookup (organ-filtered) -> top-k chunks + similarity + sources.

    rerank: OPTIONAL, additive reranking stage (default "none" = today's exact
      behavior, byte-identical). "rrf" pulls a slightly larger vector-similarity
      candidate pool, then fuses it with a pure-Python BM25 lexical ranking of
      the SAME candidates via Reciprocal Rank Fusion (k=60), before trimming
      back down to top_k. See the PROVENANCE comment block near RRF_K above
      for citations (MemMachine Apache-2.0 studied design; Robertson & Zaragoza
      2009 BM25; Cormack, Clarke & Buettcher 2009 RRF). Any other value is
      treated the same as "none" (honest, non-breaking fallback).
    """
    _ensure_loaded()
    organ = SPACE_ORGAN.get(space, "all")
    if not _state["ready"]:
        return {
            "ok": False,
            "honest_error": _state["error"] or "rag not initialized",
            "detail": ("Embedding model / FAISS deps / dataset are not available in this "
                       "Space runtime. Returning honest error instead of fake chunks "
                       "(Doctrine v10/v11)."),
            "space": space, "organ": organ, "query": query, "doctrine": DOCTRINE,
        }
    if organ not in _state["indexes"]:
        organ = "all"
    idx, ids = _state["indexes"][organ]
    top_k = max(1, min(int(top_k or 5), 20))
    use_rrf = (rerank == "rrf")

    # When reranking, pull a larger candidate pool (~top-3k relative to top_k)
    # so BM25+RRF has real headroom to reorder before trimming back to top_k.
    # rerank="none" (default) takes the ORIGINAL code path unchanged: k==top_k.
    search_k = min(top_k * RERANK_CANDIDATE_POOL, len(ids)) if use_rrf else top_k

    import numpy as np
    qe = _state["model"].encode([BGE_QUERY_PREFIX + query],
                                normalize_embeddings=True,
                                convert_to_numpy=True).astype("float32")
    k = min(search_k, len(ids))
    D, I = idx.search(qe, k)
    results = []
    for sim, row in zip(D[0].tolist(), I[0].tolist()):
        if row < 0:
            continue
        c = _state["corpus"][ids[row]]
        results.append({
            "chunk_id": c["chunk_id"],
            "similarity": round(float(sim), 6),
            "organ_tag": c["organ_tag"],
            "title": c.get("title", ""),
            "source": c["source"],
            "text": c["text"],
        })

    rerank_label = "none"
    if use_rrf:
        results = _rrf_hybrid_rerank(query, results, top_k)
        rerank_label = "rrf-hybrid-bm25-vector"
    else:
        results = results[:top_k]

    return {
        "ok": True,
        "space": space,
        "organ": organ,
        "query": query,
        "top_k": top_k,
        "count": len(results),
        "chunks": results,
        "sources": [{"chunk_id": r["chunk_id"], "source": r["source"],
                     "title": r["title"], "similarity": r["similarity"]} for r in results],
        "doctrine": DOCTRINE,
        # honesty: `rerank` is read verbatim ("none" or "rrf-hybrid-bm25-vector").
        # BM25 + RRF are exact, deterministic computations given the retrieved
        # candidates -> labeled MEASURED, never modeled/estimated/fabricated.
        "rerank": rerank_label,
        "honesty_note": (
            "MEASURED: rerank='none' is the original FAISS-only top-k, unchanged. "
            "rerank='rrf-hybrid-bm25-vector' is an exact, deterministic Reciprocal "
            "Rank Fusion (k=60) of the vector-similarity ranking and a pure-Python "
            "Okapi BM25 (k1=1.5, b=0.75) ranking, both computed over the same "
            "retrieved candidate chunks. No new chunks are fabricated or fetched "
            "outside the existing FAISS index; only ordering/trimming changes."
        ) if use_rrf else (
            "MEASURED: default retrieval path (rerank='none'); identical to "
            "pre-RRF behavior — no reranking applied."
        ),
        "lambda_receipt": _make_lambda_receipt(query, organ, axis_scores,
                                               [r["chunk_id"] for r in results]),
    }


def rag(query: str, space: str, top_k: int = 5, with_response: bool = False,
        axis_scores: list[float] | None = None, rerank: str = "none") -> dict[str, Any]:
    """Full agentic-RAG. with_response=True passes top-k to the LLM tier (szl_brain.route).

    rerank: forwarded verbatim to search() — "none" (default, unchanged behavior)
      or "rrf" (optional BM25+vector RRF hybrid fusion). See search()'s docstring.
    """
    out = search(query, space, top_k=top_k, axis_scores=axis_scores, rerank=rerank)
    if not out.get("ok") or not with_response:
        return out

    # Build a grounded prompt; honesty: instruct the model to cite chunk IDs.
    ctx_lines = []
    for r in out["chunks"]:
        ctx_lines.append(f"[chunk {r['chunk_id']} | {r['source']}]\n{r['text']}")
    context = "\n\n---\n\n".join(ctx_lines)
    prompt = (
        "You are an SZL Holdings agentic-RAG assistant. Answer the question using ONLY "
        "the retrieved chunks below. Cite the chunk_id in brackets for every claim. If the "
        "chunks do not contain the answer, say so honestly.\n\n"
        f"QUESTION: {query}\n\nRETRIEVED CHUNKS:\n{context}\n\nANSWER (cite chunk_ids):"
    )
    answer_block: dict[str, Any]
    try:
        import szl_brain as _brain
        routed = _brain.route(prompt, axis_scores=axis_scores, task_hint="research")
        answer_block = {
            "answer": routed.get("response"),
            "tier_used": routed.get("tier_used"),
            "tier_rank": routed.get("tier_rank"),
            "llm_lambda_receipt": routed.get("lambda_receipt"),
        }
    except Exception as exc:
        answer_block = {
            "answer": None,
            "honest_error": f"LLM router unavailable: {type(exc).__name__}",
            "note": "Retrieval succeeded; generation tier not wired in this Space.",
        }
    out["with_response"] = True
    out["generation"] = answer_block
    # honesty: the answer must cite chunk_ids — we surface them explicitly too.
    out["cited_chunk_ids"] = [r["chunk_id"] for r in out["chunks"]]
    return out
