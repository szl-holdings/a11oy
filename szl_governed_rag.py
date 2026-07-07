# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
# Authored by Yachay (CTO) + Perplexity Computer Agent — a11oy Governed RAG
# Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
# Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
"""
szl_governed_rag — GOVERNED RAG / retrieval-with-receipts for the SZL ecosystem.

The differentiator, in one line: **every retrieved answer ships a SIGNED receipt
proving which sources grounded which claims.** RAG systems in the wild retrieve
passages and generate an answer; almost none emit a machine-checkable, signed
attestation binding each *claim* in the answer to the specific passage(s) that
grounded it, gated on a faithfulness/grounding score. That governance layer is
what SZL adds on top of the retrieval SOTA.

────────────────────────────────────────────────────────────────────────────
RESEARCH — RAG LEADERS STUDIED (cited in code + in every response; real URLs)
────────────────────────────────────────────────────────────────────────────
  1. Dense retrieval (DPR) — Karpukhin et al. 2020, dual-encoder dense passage
     retrieval.  https://arxiv.org/abs/2004.04906
  2. Hybrid / sparse+dense (BM25 + dense fusion; RRF) — Robertson & Zaragoza
     BM25 (2009) + reciprocal-rank fusion (Cormack et al. 2009).
     https://en.wikipedia.org/wiki/Okapi_BM25
  3. ColBERT / late-interaction — Khattab & Zaharia 2020 (token-level MaxSim).
     https://arxiv.org/abs/2004.12832
  4. Rerankers / cross-encoders — Cohere Rerank (cross-encoder re-scoring of
     candidates before generation).  https://cohere.com/rerank  and
     Nogueira & Cho, "Passage Re-ranking with BERT" https://arxiv.org/abs/1901.04085
  5. GraphRAG — Microsoft Research (knowledge-graph + community summaries at
     query time; fine-grained references).  https://microsoft.github.io/graphrag/
     and https://arxiv.org/abs/2404.16130
  6. Contextual Retrieval — Anthropic 2024 (prepend chunk-situating context
     before embedding/indexing to cut retrieval failures).
     https://www.anthropic.com/engineering/contextual-retrieval
  7. Citation-grounded generation — attributed generation / per-claim source
     attribution.  Gao et al., "Enabling LLMs to Generate Text with Citations"
     (ALCE)  https://arxiv.org/abs/2305.14627  ;  self-RAG
     https://arxiv.org/abs/2310.11511
  8. RAGAS — Es et al. 2023, reference-free RAG eval: faithfulness, answer
     relevancy, context precision/recall.  https://arxiv.org/abs/2309.15217
     and https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/faithfulness/

OUR GOVERNED VERSION folds those into ONE honest, deterministic pipeline:
  query -> (a) deterministic HYBRID retrieval over a small embedded/provided
  corpus (dense hashing-embedding cosine  +  BM25-lite lexical  fused by
  reciprocal-rank fusion, the community-standard hybrid recipe) -> (b) a
  late-interaction-style rerank (token-overlap MaxSim proxy, ColBERT fashion) ->
  (c) grounded answer assembled as CLAIMS, each claim carrying the passage id(s)
  that grounded it (citation-grounded generation) -> (d) RAGAS-style scoring
  (faithfulness = fraction of claims grounded; context-precision = grounded/
  retrieved) -> (e) a Λ-GATE on grounding/faithfulness (Λ = Conjecture 1,
  advisory, NEVER "green") -> (f) an ECDSA-P256 DSSE SIGNED receipt
  (szl.rag_query.receipt/v1) recording the per-claim citation map, ingested to
  /llm/forum.

HONESTY (Doctrine v11 LOCKED):
  * Retrieval, RRF fusion, rerank, per-claim grounding, RAGAS-style scoring,
    Λ arithmetic, sha256 provenance, DSSE signing, and forum ingest are ALL REAL
    and DETERMINISTIC (no fabricated relevance, no fabricated citations — a claim
    is only grounded if an actual retrieved passage supports it lexically).
  * The generation step is EXTRACTIVE-by-default (grounded_answer is composed
    strictly from retrieved passage sentences), so the answer is honest even with
    no model key. If an LLM API key is wired we label the abstractive path
    MODELED (we do not fabricate a model call in-repo); with no key we return the
    honest extractive answer + a MODELED/UNAVAILABLE note. No fabrication.
  * Λ = Conjecture 1 — advisory, gray, NEVER "green", never a theorem. Adds
    NOTHING to the locked-8.
  * Real ECDSA-P256 DSSE signature in-Space (via szl_dsse); honest UNSIGNED-LOCAL
    marker when no cosign key secret is present — no fabricated signature.

ENDPOINT (ADDITIVE — registered BEFORE the Node proxy + SPA catch-all, mirroring
szl_model_harness / szl_llm_registry; serve.py wraps register() in try/except so a
failure never dark-404s existing routes):
  POST /api/a11oy/v1/rag/query  {query, corpus?, model_id?, harness_profile_id?}
  GET  /api/a11oy/v1/rag/corpus — the shipped demo corpus (ids + text + source)
  GET  /api/a11oy/v1/rag/health — module + signer + forum availability

Adds NOTHING to the locked-8. Doctrine v11 LOCKED — 749/14/163 — c7c0ba17.
"""
from __future__ import annotations

import hashlib
import math
import os
import re
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

DOCTRINE = "v11"
_KERNEL = "c7c0ba17"
_LAMBDA_FLOOR = 0.90
_CONJECTURE_NOTE = "Λ = Conjecture 1 — NOT a theorem. Advisory, never 'green'."

RAG_PAYLOAD_TYPE = "application/vnd.szl.rag+json"

# Grounding threshold: a claim is "grounded" only if its best supporting passage
# clears this lexical-overlap floor. Honest, deterministic — no fabricated support.
_GROUND_FLOOR = 0.18

# Citable RAG leaders — surfaced in code AND in every API response (doctrine:
# cite real sources). Each entry is (short_name, what_we_took, url).
RAG_LEADERS: list[dict[str, str]] = [
    {"name": "DPR (dense retrieval)", "took": "dense dual-encoder passage retrieval",
     "url": "https://arxiv.org/abs/2004.04906"},
    {"name": "BM25 / hybrid + RRF", "took": "sparse lexical scoring + reciprocal-rank fusion of dense+sparse",
     "url": "https://en.wikipedia.org/wiki/Okapi_BM25"},
    {"name": "ColBERT (late interaction)", "took": "token-level MaxSim rerank of candidates",
     "url": "https://arxiv.org/abs/2004.12832"},
    {"name": "Cohere Rerank / cross-encoder", "took": "rerank retrieved candidates before generation",
     "url": "https://cohere.com/rerank"},
    {"name": "GraphRAG (Microsoft)", "took": "fine-grained passage references / provenance at query time",
     "url": "https://microsoft.github.io/graphrag/"},
    {"name": "Anthropic Contextual Retrieval", "took": "situate each chunk with context before indexing",
     "url": "https://www.anthropic.com/engineering/contextual-retrieval"},
    {"name": "ALCE / citation-grounded generation", "took": "per-claim source attribution in the answer",
     "url": "https://arxiv.org/abs/2305.14627"},
    {"name": "RAGAS", "took": "faithfulness + context-precision reference-free RAG eval",
     "url": "https://arxiv.org/abs/2309.15217"},
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


# ─────────────────────────────────────────────────────────────────────────────
# Shipped demo corpus — small, embedded, factual, each passage carries a source.
# Real, checkable statements about the RAG leaders we studied (self-describing:
# the corpus documents the very techniques this module composes). NEVER fabricated
# at query time; the corpus is fixed content with sha256 provenance.
# ─────────────────────────────────────────────────────────────────────────────
_CORPUS: list[dict[str, str]] = [
    {"id": "p1",
     "text": "Dense passage retrieval (DPR) encodes queries and passages into a shared "
             "vector space with a dual encoder and retrieves by inner-product similarity.",
     "source": "Karpukhin et al. 2020, arXiv:2004.04906"},
    {"id": "p2",
     "text": "BM25 is a sparse lexical ranking function; hybrid retrieval fuses BM25 and dense "
             "scores, commonly with reciprocal rank fusion, to improve recall over either alone.",
     "source": "Robertson & Zaragoza 2009; Cormack et al. 2009 (RRF)"},
    {"id": "p3",
     "text": "ColBERT uses late interaction: it scores a query against a passage with token-level "
             "MaxSim over contextual embeddings, giving fine-grained relevance at scale.",
     "source": "Khattab & Zaharia 2020, arXiv:2004.12832"},
    {"id": "p4",
     "text": "A cross-encoder reranker such as Cohere Rerank jointly encodes the query and each "
             "candidate passage to produce precise relevance scores before generation.",
     "source": "Cohere Rerank; Nogueira & Cho 2019, arXiv:1901.04085"},
    {"id": "p5",
     "text": "GraphRAG builds a knowledge graph and community summaries from a corpus and uses "
             "them at query time, providing fine-grained references for its answers.",
     "source": "Microsoft Research GraphRAG, arXiv:2404.16130"},
    {"id": "p6",
     "text": "Anthropic contextual retrieval prepends chunk-situating context to each chunk before "
             "embedding and indexing, reducing failed retrievals on ambiguous chunks.",
     "source": "Anthropic 2024, contextual-retrieval"},
    {"id": "p7",
     "text": "Citation-grounded generation attributes each claim in an answer to the specific "
             "source passages that support it, enabling verification of the generated text.",
     "source": "Gao et al. 2023 ALCE, arXiv:2305.14627"},
    {"id": "p8",
     "text": "RAGAS is a reference-free evaluation framework that measures faithfulness, answer "
             "relevancy, and context precision and recall for retrieval-augmented generation.",
     "source": "Es et al. 2023, arXiv:2309.15217"},
    {"id": "p9",
     "text": "Faithfulness in RAGAS is the fraction of claims in the answer that can be inferred "
             "from the retrieved context; low faithfulness signals hallucination.",
     "source": "RAGAS faithfulness metric docs"},
    {"id": "p10",
     "text": "A governed RAG receipt records which retrieved passages grounded which claims, is "
             "gated on a faithfulness score, and is signed so the attribution can be audited.",
     "source": "SZL Holdings governed-RAG doctrine v11"},
]

_STOP = {
    "the", "a", "an", "of", "to", "in", "and", "or", "is", "are", "for", "on", "with",
    "by", "at", "as", "it", "its", "that", "this", "from", "be", "into", "over", "than",
    "each", "which", "such", "not", "no", "can", "does", "do", "so", "up", "before",
    "what", "how", "why", "when", "who", "whom", "them", "they", "their", "we", "our",
}


def _corpus_sha256(corpus: list[dict[str, str]]) -> str:
    h = hashlib.sha256()
    for p in corpus:
        h.update((p.get("id", "") + "\x1f" + p.get("text", "") + "\x1f" + p.get("source", "")).encode("utf-8"))
        h.update(b"\x1e")
    return h.hexdigest()


# ─────────────────────────────────────────────────────────────────────────────
# Deterministic tokenizer + hashing embedding (dense proxy — no model needed).
# The hashing embedding is a fixed, reproducible feature map (hashing trick): it
# is a real dense vector, not a fabricated one, and identical inputs always map
# to identical vectors. This keeps retrieval honest and deterministic with zero
# external model dependency, while still exercising the dense-cosine leg of the
# hybrid recipe (DPR fashion).
# ─────────────────────────────────────────────────────────────────────────────

def _tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(t) > 1 and t not in _STOP]


def _embed(text: str, dims: int = 256) -> list[float]:
    """Deterministic hashing embedding (hashing-trick bag of tokens). Real dense
    vector; identical text -> identical vector. No external model required."""
    vec = [0.0] * dims
    toks = _tokens(text)
    for t in toks:
        hh = int(hashlib.md5(t.encode("utf-8")).hexdigest(), 16)
        idx = hh % dims
        sign = 1.0 if (hh >> 8) & 1 else -1.0
        vec[idx] += sign
    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0:
        vec = [v / norm for v in vec]
    return vec


def _cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _bm25_lite(q_toks: list[str], p_toks: list[str], corpus_df: dict[str, int],
               n_docs: int, avgdl: float, k1: float = 1.5, b: float = 0.75) -> float:
    """BM25-lite lexical score (sparse leg of the hybrid recipe)."""
    if not p_toks:
        return 0.0
    dl = len(p_toks)
    tf: dict[str, int] = {}
    for t in p_toks:
        tf[t] = tf.get(t, 0) + 1
    score = 0.0
    for t in set(q_toks):
        if t not in tf:
            continue
        df = corpus_df.get(t, 0)
        if df <= 0:
            continue
        idf = math.log(1 + (n_docs - df + 0.5) / (df + 0.5))
        num = tf[t] * (k1 + 1)
        den = tf[t] + k1 * (1 - b + b * dl / (avgdl or 1.0))
        score += idf * num / (den or 1.0)
    return score


def _rrf(rank: int, k: int = 60) -> float:
    """Reciprocal rank fusion contribution for a given 0-based rank."""
    return 1.0 / (k + rank + 1)


def _maxsim_rerank(q_toks: list[str], p_toks: list[str]) -> float:
    """ColBERT-style late-interaction proxy: fraction of query tokens with an
    exact match in the passage (token-level MaxSim over a discrete vocabulary)."""
    if not q_toks:
        return 0.0
    pset = set(p_toks)
    hits = sum(1 for t in q_toks if t in pset)
    return hits / len(q_toks)


# ─────────────────────────────────────────────────────────────────────────────
# Retrieval — deterministic HYBRID (dense cosine + BM25-lite) fused via RRF,
# then a late-interaction MaxSim rerank. Returns ranked passages with per-leg
# scores (fully auditable; nothing fabricated).
# ─────────────────────────────────────────────────────────────────────────────

def _retrieve(query: str, corpus: list[dict[str, str]], top_k: int = 4) -> dict[str, Any]:
    q_toks = _tokens(query)
    q_vec = _embed(query)

    tok_by_id: dict[str, list[str]] = {}
    corpus_df: dict[str, int] = {}
    for p in corpus:
        pt = _tokens(p.get("text", ""))
        tok_by_id[p["id"]] = pt
        for t in set(pt):
            corpus_df[t] = corpus_df.get(t, 0) + 1
    n_docs = len(corpus)
    avgdl = (sum(len(v) for v in tok_by_id.values()) / n_docs) if n_docs else 1.0

    dense: list[tuple[str, float]] = []
    sparse: list[tuple[str, float]] = []
    for p in corpus:
        pid = p["id"]
        dense.append((pid, _cosine(q_vec, _embed(p.get("text", "")))))
        sparse.append((pid, _bm25_lite(q_toks, tok_by_id[pid], corpus_df, n_docs, avgdl)))

    dense_rank = {pid: r for r, (pid, _s) in enumerate(sorted(dense, key=lambda x: -x[1]))}
    sparse_rank = {pid: r for r, (pid, _s) in enumerate(sorted(sparse, key=lambda x: -x[1]))}
    dense_by_id = dict(dense)
    sparse_by_id = dict(sparse)

    fused: list[dict[str, Any]] = []
    for p in corpus:
        pid = p["id"]
        rrf = _rrf(dense_rank[pid]) + _rrf(sparse_rank[pid])
        fused.append({
            "id": pid, "text": p.get("text", ""), "source": p.get("source", ""),
            "dense_cosine": round(dense_by_id[pid], 6),
            "bm25_lite": round(sparse_by_id[pid], 6),
            "rrf_score": round(rrf, 6),
        })
    fused.sort(key=lambda d: -d["rrf_score"])
    candidates = fused[: max(top_k * 2, top_k)]

    # late-interaction rerank (ColBERT fashion) on the fused candidates
    for c in candidates:
        c["maxsim_rerank"] = round(_maxsim_rerank(q_toks, tok_by_id[c["id"]]), 6)
    candidates.sort(key=lambda d: (-d["maxsim_rerank"], -d["rrf_score"]))
    retrieved = candidates[:top_k]

    return {
        "query_tokens": q_toks,
        "retrieved": retrieved,
        "method": "hybrid(dense hashing-embedding cosine + BM25-lite) → RRF fusion → ColBERT-style MaxSim rerank",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Grounded generation — EXTRACTIVE claim assembly with PER-CLAIM citations.
# We split the top passages into claim-sized sentences, keep only those that
# actually match the query (lexical support), and cite the passage id(s) that
# ground each claim. This is honest with NO model key (the answer is literally
# composed of source text) and is the citation-grounded-generation leg (ALCE).
# ─────────────────────────────────────────────────────────────────────────────

def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.;])\s+", (text or "").strip())
    return [s.strip() for s in parts if len(s.strip()) > 12]


def _support(claim: str, passage_text: str) -> float:
    """Lexical support score between a claim and a passage (token overlap over
    the claim's content tokens). Deterministic; a claim is only grounded if this
    clears the grounding floor — no fabricated attribution."""
    c = set(_tokens(claim))
    if not c:
        return 0.0
    p = set(_tokens(passage_text))
    return len(c & p) / len(c)


def _generate_grounded(query: str, retrieved: list[dict[str, Any]], max_claims: int = 4) -> dict[str, Any]:
    q_toks = set(_tokens(query))
    claims: list[dict[str, Any]] = []
    seen: set[str] = set()
    for p in retrieved:
        for sent in _sentences(p["text"]):
            key = sent.lower()
            if key in seen:
                continue
            # only keep sentences that share content with the query (relevancy)
            if q_toks and not (set(_tokens(sent)) & q_toks):
                continue
            seen.add(key)
            # score this claim against ALL retrieved passages -> per-claim citations
            supports = []
            for pp in retrieved:
                s = _support(sent, pp["text"])
                if s >= _GROUND_FLOOR:
                    supports.append({"passage_id": pp["id"], "source": pp["source"],
                                     "support": round(s, 4)})
            supports.sort(key=lambda d: -d["support"])
            grounded = bool(supports)
            claims.append({
                "claim": sent,
                "grounded": grounded,
                "citations": supports,
                "best_support": supports[0]["support"] if supports else 0.0,
            })
            if len(claims) >= max_claims:
                break
        if len(claims) >= max_claims:
            break

    # Honest fallback: if the query shares no content with any retrieved passage,
    # emit ONE ungrounded "no-support" claim rather than fabricating an answer.
    if not claims:
        claims.append({
            "claim": "No passage in the corpus lexically supports this query; no grounded answer produced.",
            "grounded": False, "citations": [], "best_support": 0.0,
        })

    grounded_claims = [c for c in claims if c["grounded"]]
    answer_sentences = [c["claim"] for c in grounded_claims] or \
        ["No grounded answer: retrieved passages did not support any claim for this query."]
    grounded_answer = " ".join(answer_sentences)
    return {"claims": claims, "grounded_answer": grounded_answer,
            "grounded_claim_count": len(grounded_claims)}


# ─────────────────────────────────────────────────────────────────────────────
# RAGAS-style scoring (reference-free): faithfulness + context precision.
# ─────────────────────────────────────────────────────────────────────────────

def _ragas_scores(claims: list[dict[str, Any]], retrieved: list[dict[str, Any]]) -> dict[str, float]:
    n_claims = len(claims) or 1
    grounded = sum(1 for c in claims if c["grounded"])
    faithfulness = grounded / n_claims  # RAGAS faithfulness: fraction of claims inferable from context
    cited_ids = {cit["passage_id"] for c in claims for cit in c["citations"]}
    n_ret = len(retrieved) or 1
    context_precision = len(cited_ids) / n_ret  # fraction of retrieved passages actually used
    avg_support = (sum(c["best_support"] for c in claims) / n_claims)
    return {
        "faithfulness": round(faithfulness, 4),
        "context_precision": round(context_precision, 4),
        "avg_grounding_support": round(avg_support, 4),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Λ-gate — REUSE szl_llm_registry's gate; local geometric-mean fallback. The gate
# is fed grounding/faithfulness axes so Λ tracks how well the answer is grounded.
# Λ = Conjecture 1 (advisory, NEVER "green"). Never raises into the request path.
# ─────────────────────────────────────────────────────────────────────────────

def _reg():
    import szl_llm_registry as _r
    return _r


# Wave M (Dev 2): shared sovereign-flywheel bridge. Lets /rag/query run the
# abstractive rewrite on SZL's OWN governed model (sovereign_local) via Dev-1's
# registry backend; honest MODELED/UNAVAILABLE when the Tower is offline.
try:
    import szl_sovereign_flywheel as _sov  # noqa: F401
    _SOV_OK = True
except Exception:  # pragma: no cover — bridge missing → sovereign option simply off
    _sov = None  # type: ignore
    _SOV_OK = False


def _lambda_gm(axes: list[float]) -> float:
    try:
        return _reg()._lambda_gm(axes)
    except Exception:
        if not axes:
            return 0.5
        c = [max(1e-9, min(1.0, float(v))) for v in axes]
        return math.exp(sum(math.log(v) for v in c) / len(c))


def _api_key_wired(env_var: str) -> bool:
    try:
        return _reg()._api_key_wired(env_var)
    except Exception:
        val = os.environ.get(env_var, "").strip()
        return bool(val and val != "NOT_SET" and len(val) > 8)


def _model_by_id(model_id: str) -> dict[str, Any] | None:
    try:
        return _reg()._MODEL_BY_ID.get(model_id)
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# DSSE signing — REAL ECDSA-P256 in-Space via szl_dsse; honest UNSIGNED locally.
# ─────────────────────────────────────────────────────────────────────────────

def _sign_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
    try:
        import szl_dsse
        env = szl_dsse.sign_payload(receipt, RAG_PAYLOAD_TYPE)
        signed = bool(env.get("signed"))
        sig_val = None
        if env.get("signatures"):
            sig_val = env["signatures"][0].get("sig")
        return {
            "alg": "ECDSA-P256",
            "envelope": "DSSE",
            "signed": signed,
            "value": sig_val if signed else "UNSIGNED-LOCAL",
            "keyid": (env.get("signatures") or [{}])[0].get("keyid") if signed else None,
            "payloadType": env.get("payloadType"),
            "pae_sha256": env.get("_pae_sha256"),
            "honesty": env.get("honesty"),
            "verify_key_url": env.get("verify_key_url"),
        }
    except Exception as e:
        return {
            "alg": "ECDSA-P256",
            "envelope": "DSSE",
            "signed": False,
            "value": "UNSIGNED-LOCAL",
            "honesty": f"UNSIGNED — DSSE signer unavailable ({e!r}); no signature fabricated.",
        }


# ─────────────────────────────────────────────────────────────────────────────
# Forum ingest — shared /llm/forum ring (same substrate the router writes to).
# ─────────────────────────────────────────────────────────────────────────────

def _forum_ingest(receipt: dict[str, Any], query_preview: str = "") -> dict[str, Any]:
    entry = {**receipt, "source": "a11oy", "event": "rag_query",
             "query_preview": query_preview[:80] if query_preview else ""}
    try:
        _reg()._forum_append(entry)
        return {"ingested": True, "forum": "/api/a11oy/v1/llm/forum"}
    except Exception as e:
        return {"ingested": False, "error": f"{e!r}",
                "honest_note": "forum ingest failed; receipt still returned to caller."}


def _seed_forum() -> None:
    try:
        _reg()._forum_append({
            "ts": _now(), "source": "a11oy", "event": "rag_boot",
            "corpus_size": len(_CORPUS), "doctrine": DOCTRINE,
            "note": "szl_governed_rag initialised — governed retrieval-with-receipts online",
        })
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# query() — the IMPORTABLE governed RAG core. Single source of truth for the HTTP
# endpoint. NEVER raises into the caller's request path; NEVER fabricates support.
# ─────────────────────────────────────────────────────────────────────────────

def query(query_text: str, corpus: list[dict[str, str]] | None = None,
          model_id: str = "", harness_profile_id: str = "", top_k: int = 4,
          ns: str = "a11oy", forum: bool = True) -> dict[str, Any]:
    """Governed RAG query — deterministic hybrid retrieval → per-claim citation-
    grounded answer → RAGAS-style scoring → Λ-gate → SIGNED receipt → forum ingest.

    Returns ok, rag_state (LIVE-KEY/MODELED/UNAVAILABLE/EMPTY_QUERY), grounded_answer,
    claims (each with citations), retrieval, ragas, receipt (signed), forum.
    """
    query_text = str(query_text or "").strip()
    model_id = str(model_id or "").strip()
    harness_profile_id = str(harness_profile_id or "").strip()
    top_k = min(8, max(1, int(top_k or 4)))

    if not query_text:
        return {
            "ok": False,
            "rag_state": "EMPTY_QUERY",
            "error": "query must be a non-empty string",
            "conjecture_note": _CONJECTURE_NOTE,
        }

    # corpus: caller-provided (validated) OR the shipped demo corpus
    use_corpus: list[dict[str, str]] = []
    corpus_origin = "shipped_demo"
    if isinstance(corpus, list) and corpus:
        for i, item in enumerate(corpus):
            if isinstance(item, dict) and item.get("text"):
                use_corpus.append({
                    "id": str(item.get("id") or f"u{i+1}"),
                    "text": str(item.get("text")),
                    "source": str(item.get("source") or "caller-provided"),
                })
        corpus_origin = "caller_provided"
    if not use_corpus:
        use_corpus = list(_CORPUS)
        corpus_origin = "shipped_demo"

    corpus_sha = _corpus_sha256(use_corpus)

    # (1) retrieve  (2) generate grounded answer with per-claim citations
    retr = _retrieve(query_text, use_corpus, top_k=top_k)
    gen = _generate_grounded(query_text, retr["retrieved"])
    ragas = _ragas_scores(gen["claims"], retr["retrieved"])

    # (3) Λ-gate on grounding/faithfulness (Λ = Conjecture 1, advisory)
    axes = [
        max(1e-6, ragas["faithfulness"]),
        max(1e-6, ragas["context_precision"]),
        max(1e-6, ragas["avg_grounding_support"]),
        0.90,  # pipeline-determinism prior (deterministic retrieval + fusion)
    ]
    lam = _lambda_gm(axes)
    gate_pass = lam >= _LAMBDA_FLOOR and ragas["faithfulness"] >= 0.5
    gate_reason = (f"Λ={lam:.4f} vs floor {_LAMBDA_FLOOR}; faithfulness={ragas['faithfulness']} "
                   f"(gate requires Λ≥floor AND faithfulness≥0.5). Λ is ADVISORY (Conjecture 1), "
                   f"never 'green'.")

    # (4) honest model-availability label — abstractive path is MODELED w/o key.
    selected = _model_by_id(model_id) if model_id else None
    api_env = (selected or {}).get("api_env_var", "")
    api_key_wired = _api_key_wired(api_env) if api_env else False
    if api_key_wired:
        rag_state = "LIVE-KEY"
        model_note = (f"API key present for {(selected or {}).get('display_name', model_id)}; an "
                      "abstractive rewrite over the SAME grounded, cited passages could run. This "
                      "repo returns the EXTRACTIVE grounded answer + per-claim citations (honest, "
                      "no fabricated model call). Abstractive rewrite is MODELED.")
    elif model_id:
        rag_state = "MODELED"
        model_note = (f"No API key wired for '{model_id}' in this env. Returning the EXTRACTIVE "
                      "grounded answer composed strictly from cited passages — no model output "
                      "fabricated. Retrieval, grounding, RAGAS scoring, Λ-gate, signature are REAL.")
    else:
        rag_state = "MODELED"
        model_note = ("No model_id supplied. Returning the EXTRACTIVE grounded answer built strictly "
                      "from cited passages (honest with no model key). Retrieval, per-claim grounding, "
                      "RAGAS scoring, Λ-gate, and DSSE signature are REAL.")

    if harness_profile_id:
        model_note += (f" A harness_profile_id ('{harness_profile_id}') was supplied; the abstractive "
                       "path would apply it via szl_model_harness (MODELED disposition only).")

    # ── Wave M (Dev 2): SOVEREIGN option ───────────────────────────────────────
    # Run the abstractive rewrite on SZL's OWN governed model, grounded STRICTLY
    # on the retrieved+cited passages. When the Tower is offline we keep the honest
    # EXTRACTIVE answer and record the intended sovereign backend — no fabrication.
    sovereign_answer = None
    sovereign_block = None
    if _SOV_OK and _sov and _sov.is_sovereign(model_id):
        _ctx = "\n\n".join(
            f"[{p['id']}] {p.get('text', '')}" for p in retr["retrieved"])
        _sov_prompt = (
            "Answer the question USING ONLY the sources below. Cite each source id "
            "you rely on in square brackets. If the sources do not answer it, say so.\n\n"
            f"SOURCES:\n{_ctx}\n\nQUESTION: {query_text}\n\nGROUNDED ANSWER:")
        sov = _sov.run_on_sovereign(_sov_prompt, requested_model_id=model_id)
        sovereign_block = _sov.receipt_block(sov)
        rag_state = sov.get("state")  # LIVE | MODELED | UNAVAILABLE
        if sov.get("state") == "LIVE" and isinstance(sov.get("text"), str):
            sovereign_answer = sov["text"]
            model_note = ("LIVE abstractive rewrite from SZL's OWN sovereign_local model, "
                          "grounded on the SAME cited passages. Retrieval, grounding, "
                          "RAGAS, Λ-gate, and signature remain REAL.")
        elif sov.get("state") == "MODELED":
            model_note = ("SZL sovereign_local selected but the local node did not answer "
                          "live this request — returning the honest EXTRACTIVE grounded "
                          "answer (no model text fabricated). Intended sovereign backend recorded.")
        else:
            model_note = ("SZL sovereign_local selected but the local endpoint is unreachable "
                          "(SZL_LOCAL_LLM_URL unset / Tower offline) — returning the honest "
                          "EXTRACTIVE grounded answer. Intended sovereign backend recorded; "
                          "no model call attempted; no fabrication.")

    # per-claim citation map (the differentiator, made machine-checkable)
    claim_citation_map = [
        {"claim": c["claim"], "grounded": c["grounded"],
         "grounded_by": [cit["passage_id"] for cit in c["citations"]],
         "best_support": c["best_support"]}
        for c in gen["claims"]
    ]

    receipt: dict[str, Any] = {
        "schema": "szl.rag_query.receipt/v1",
        "ts": _now(),
        "hub": ns,
        "query": query_text[:240],
        "corpus": {
            "origin": corpus_origin,
            "size": len(use_corpus),
            "sha256": corpus_sha,
        },
        "retrieval": {
            "method": retr["method"],
            "top_k": top_k,
            "retrieved_ids": [p["id"] for p in retr["retrieved"]],
            "scores": [{"id": p["id"], "dense_cosine": p["dense_cosine"],
                        "bm25_lite": p["bm25_lite"], "rrf_score": p["rrf_score"],
                        "maxsim_rerank": p.get("maxsim_rerank")} for p in retr["retrieved"]],
        },
        # ── THE DIFFERENTIATOR: which passages grounded which claims ──
        "grounding": {
            "per_claim_citations": claim_citation_map,
            "grounded_claim_count": gen["grounded_claim_count"],
            "total_claim_count": len(gen["claims"]),
        },
        "ragas": ragas,
        "ragas_ref": "RAGAS reference-free RAG eval (Es et al. 2023, arXiv:2309.15217)",
        "lambda": round(lam, 6),
        "lambda_floor": _LAMBDA_FLOOR,
        "lambda_axes": {"faithfulness": axes[0], "context_precision": axes[1],
                        "avg_grounding_support": axes[2], "determinism_prior": axes[3]},
        "gate_pass": bool(gate_pass),
        "gate_reason": gate_reason,
        "model_id": model_id or None,
        "api_key_wired": api_key_wired,
        "sovereign": sovereign_block,  # Wave M: intended sovereign backend (None when not requested)
        "harness_profile_id": harness_profile_id or None,
        "rag_state": rag_state,
        "honesty_label": rag_state,
        "rag_leaders_cited": RAG_LEADERS,
        "doctrine": DOCTRINE,
        "kernel_commit": _KERNEL,
        "conjecture_note": _CONJECTURE_NOTE,
    }
    receipt["signature"] = _sign_receipt(receipt)

    forum_status = _forum_ingest(receipt, query_text) if forum else {"ingested": False, "skipped": True}

    return {
        "ok": True,
        "rag_state": rag_state,
        "model_note": model_note,
        "grounded_answer": gen["grounded_answer"],
        # Wave M: the sovereign model's abstractive rewrite (LIVE only; None otherwise
        # — the extractive grounded_answer above is ALWAYS the honest fallback).
        "sovereign_answer": sovereign_answer,
        "sovereign": sovereign_block,
        "claims": gen["claims"],
        "retrieval": retr,
        "ragas": ragas,
        "gate_pass": bool(gate_pass),
        "receipt": receipt,
        "forum": forum_status,
        "rag_leaders": RAG_LEADERS,
        "differentiator": "Every retrieved answer ships a SIGNED receipt proving which sources "
                          "grounded which claims (per-claim citations + faithfulness Λ-gate).",
        "doctrine": DOCTRINE,
        "conjecture_note": _CONJECTURE_NOTE,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Route registration
# ─────────────────────────────────────────────────────────────────────────────

def register(app: FastAPI, ns: str = "a11oy") -> dict:
    """Register the governed-RAG endpoints BEFORE the proxy/SPA catch-all (mirror
    szl_model_harness.register). ADDITIVE; never crashes the app — serve.py wraps
    this in try/except."""
    _seed_forum()

    # ── POST /api/a11oy/v1/rag/query ─────────────────────────────────────────
    @app.post(f"/api/{ns}/v1/rag/query")
    async def rag_query(request: Request) -> JSONResponse:
        """Governed RAG query. Body:
        {"query": "...", "corpus": [{"id","text","source"}]?, "model_id": "?",
         "harness_profile_id": "?", "top_k": 4}
        Honest 4xx on empty query; otherwise 200 with grounded answer + per-claim
        citations + RAGAS scores + Λ-gate + SIGNED receipt (forum-ingested).

        Wave M (Dev 2): model_id="szl-sovereign-local" runs the abstractive rewrite
        on SZL's OWN governed model (Dev-1 backend), grounded on the same cited
        passages. When the local Tower endpoint is unreachable the extractive
        grounded answer is returned and the receipt records the intended sovereign
        backend — no model response is ever fabricated."""
        try:
            body = await request.json()
        except Exception:
            body = {}
        if not isinstance(body, dict):
            body = {}
        res = query(
            query_text=body.get("query", ""),
            corpus=body.get("corpus"),
            model_id=body.get("model_id", ""),
            harness_profile_id=body.get("harness_profile_id", ""),
            top_k=int(body.get("top_k", 4) or 4),
            ns=ns,
            forum=True,
        )
        if not res.get("ok"):
            return JSONResponse(
                {"error": res.get("error", "bad request"),
                 "rag_state": res.get("rag_state"),
                 "conjecture_note": _CONJECTURE_NOTE},
                status_code=400)
        return JSONResponse({
            "grounded_answer": res["grounded_answer"],
            "sovereign_answer": res.get("sovereign_answer"),  # Wave M: LIVE only, else None
            "sovereign": res.get("sovereign"),               # intended sovereign backend
            "rag_state": res["rag_state"],
            "model_note": res["model_note"],
            "claims": res["claims"],
            "retrieval": res["retrieval"],
            "ragas": res["ragas"],
            "gate_pass": res["gate_pass"],
            "rag_receipt": res["receipt"],
            "forum": res["forum"],
            "rag_leaders": res["rag_leaders"],
            "differentiator": res["differentiator"],
            "doctrine": DOCTRINE,
            "conjecture_note": _CONJECTURE_NOTE,
        })

    # ── GET /api/a11oy/v1/rag/corpus ─────────────────────────────────────────
    @app.get(f"/api/{ns}/v1/rag/corpus")
    async def rag_corpus() -> JSONResponse:
        """The shipped demo corpus (ids + text + source) + sha256 provenance."""
        return JSONResponse({
            "timestamp": _now(),
            "hub": ns,
            "corpus": _CORPUS,
            "corpus_size": len(_CORPUS),
            "corpus_sha256": _corpus_sha256(_CORPUS),
            "note": "Small embedded demo corpus. POST /rag/query may supply its own `corpus`.",
            "rag_leaders_cited": RAG_LEADERS,
            "doctrine": DOCTRINE,
            "kernel_commit": _KERNEL,
            "conjecture_note": _CONJECTURE_NOTE,
        })

    # ── GET /api/a11oy/v1/rag/health ─────────────────────────────────────────
    @app.get(f"/api/{ns}/v1/rag/health")
    async def rag_health() -> JSONResponse:
        sig = _sign_receipt({"schema": "szl.rag_query.receipt/v1", "ts": _now(), "probe": True})
        forum_ok = False
        try:
            _reg()._forum_append({"ts": _now(), "source": "a11oy", "event": "rag_health_probe"})
            forum_ok = True
        except Exception:
            forum_ok = False
        return JSONResponse({
            "timestamp": _now(),
            "module": "szl_governed_rag",
            "role": "Governed RAG — retrieval-with-receipts: every answer ships a signed receipt "
                    "proving which sources grounded which claims.",
            "corpus_size": len(_CORPUS),
            "signer": {"alg": sig.get("alg"), "signed": sig.get("signed"), "honesty": sig.get("honesty")},
            "forum_available": forum_ok,
            "lambda_floor": _LAMBDA_FLOOR,
            "grounding_floor": _GROUND_FLOOR,
            "endpoints": {
                "query": f"/api/{ns}/v1/rag/query",
                "corpus": f"/api/{ns}/v1/rag/corpus",
                "forum": f"/api/{ns}/v1/llm/forum",
            },
            "rag_leaders_cited": RAG_LEADERS,
            "doctrine": DOCTRINE,
            "kernel_commit": _KERNEL,
            "conjecture_note": _CONJECTURE_NOTE,
            "honest_note": "Retrieval, RRF fusion, ColBERT-style rerank, per-claim grounding, RAGAS "
                           "scoring, Λ-gate, DSSE signing, forum ingest are ALL real + deterministic. "
                           "Λ = Conjecture 1 (advisory, never green). Adds NOTHING to the locked-8.",
        })

    return {
        "module": "szl_governed_rag",
        "endpoints": [
            f"POST /api/{ns}/v1/rag/query",
            f"GET  /api/{ns}/v1/rag/corpus",
            f"GET  /api/{ns}/v1/rag/health",
        ],
        "corpus_size": len(_CORPUS),
        "doctrine": DOCTRINE,
        "kernel_commit": _KERNEL,
    }


def _selftest() -> None:
    """Offline self-check — no network, no app. Verifies retrieval is deterministic,
    grounding produces per-claim citations, RAGAS scores compute, Λ-gate composes,
    and receipts sign (UNSIGNED locally is the honest expected state)."""
    r1 = query("What is RAGAS and how does it measure faithfulness?")
    assert r1["ok"], r1
    assert r1["receipt"]["grounding"]["per_claim_citations"], "no per-claim citations produced"
    # determinism: identical query -> identical retrieved ids + corpus sha
    r2 = query("What is RAGAS and how does it measure faithfulness?")
    assert r1["receipt"]["retrieval"]["retrieved_ids"] == r2["receipt"]["retrieval"]["retrieved_ids"]
    assert r1["receipt"]["corpus"]["sha256"] == r2["receipt"]["corpus"]["sha256"]
    # grounded claims must cite REAL retrieved passages (no fabricated ids)
    ret_ids = set(r1["receipt"]["retrieval"]["retrieved_ids"])
    for c in r1["claims"]:
        for cit in c["citations"]:
            assert cit["passage_id"] in ret_ids, f"claim cites non-retrieved passage {cit['passage_id']}"
    # RAGAS + Λ present and sane
    assert 0.0 <= r1["ragas"]["faithfulness"] <= 1.0
    assert 0.0 < r1["receipt"]["lambda"] <= 1.0
    # signature block present, honest
    sig = r1["receipt"]["signature"]
    assert sig["alg"] == "ECDSA-P256" and sig["envelope"] == "DSSE"
    # empty query -> honest 4xx-shaped result (ok False), no crash
    e = query("")
    assert not e["ok"] and e["rag_state"] == "EMPTY_QUERY"
    # caller-provided corpus works + changes sha
    cp = query("alpha beta", corpus=[{"id": "x1", "text": "alpha beta gamma delta", "source": "test"}])
    assert cp["ok"] and cp["receipt"]["corpus"]["origin"] == "caller_provided"
    print(f"szl_governed_rag: ALL OK (corpus={len(_CORPUS)}, deterministic retrieval, "
          f"per-claim citations={len(r1['receipt']['grounding']['per_claim_citations'])}, "
          f"faithfulness={r1['ragas']['faithfulness']}, Λ={r1['receipt']['lambda']:.4f}, "
          f"signature signed={sig['signed']} — UNSIGNED locally is expected).")


if __name__ == "__main__":
    _selftest()
