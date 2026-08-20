# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
# Doctrine v11 LOCKED: locked-proven=8 · Λ=Conjecture 1 · SLSA L1 honest / L2 attested / L3 roadmap
# Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
# Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
"""
szl_retrieval_attn.py — ADDITIVE a11oy-NATIVE RETRIEVAL-MODULATED LONG-CONTEXT
ATTENTION backend for the holographic frontier surface
static/3d/surfaces/retrievalattn.js.

WHY THIS EXISTS
    A local / sparse attention window is cheap but structurally BLIND to any fact
    that sits outside the window — a long-context "needle" more than W tokens back
    is silently dropped, and no amount of recency weighting brings it back. The
    MATCH line of work (Ma et al. 2026) MODULATES a sparse window with an in-context
    RETRIEVAL step that re-injects the long-range tokens the window dropped, chosen
    by CONTENT similarity to the query rather than by position. This module is the
    a11oy-native honest twin: a REAL, deterministic implementation of four read
    policies (full-dense oracle, local sparse window, exponentially-decaying-memory
    baseline, retrieval-augmented window) run over a SEEDED synthetic needle task,
    quantifying exactly how much long-range recall the retrieval step recovers over a
    plain sparse window — distinct from episodic / graphmem / s3search.

METHOD (MODELED on a seeded needle task — NO trained model, NO GPU, NO real corpus)
    * A query vector q and seq_len token key vectors live in R^dim (seeded, unit-norm).
    * N "needles" are planted at distinct positions; a needle's key is deliberately
      aligned with q (high cos similarity) so it is the retrievable long-range signal.
      Non-needle "distractor" tokens carry a weak q-component + noise.
    * A needle is "in-window" if its position is within the last W tokens, else it is
      "long-range" (the interesting case the sparse window cannot reach).
    * FULL (dense oracle): attends every token -> recalls every needle (100%).
    * SPARSE (local window W): attends only the last W tokens -> recalls ONLY in-window
      needles; long-range recall is structurally 0.
    * EDM (exponentially-decaying memory, Wei & Gulcehre 2026): window + a
      position-decayed memory weight exp(-lambda * age); a long-range needle is
      recovered only if its decayed weight clears a threshold -> recency-biased, blind
      to far content.
    * RETRIEVAL (MATCH, Ma et al. 2026): window + an in-context retrieval step that
      scores the DROPPED tokens by cos(q, k_i) and re-injects the Top-k; a needle is
      recovered if it is in-window OR ranks in the retrieved Top-k. CONTENT-based, so
      it reaches far needles the decay baseline misses.

MATH (all REAL computations over the seeded task; NOT a trained attention layer)
    * cos(q, k_i) = <q, k_i> / (||q|| ||k_i||)  — the retrieval score.
    * long_range_recall(policy) = |recalled long-range needles| / |long-range needles|.
    * long_range_recall_recovery = retrieval_long_range_recall - sparse_long_range_recall
      (the MATCH recovery over a plain sparse window — always >= 0).
    * retrieval_vs_edm_gain = retrieval_long_range_recall - edm_long_range_recall
      (content-retrieval advantage over position-decay).
    * attend_frac(policy) = attended tokens / seq_len  (compute the policy pays):
      sparse = W/seq_len ; retrieval = (W+k)/seq_len ; full = 1.0. Retrieval stays
      sub-dense while recovering most of the long-range recall.

LEADERS ADOPTED & CITED (clean-room; NOT claimed as SZL's own; arXiv ids VERIFIED):
    * Ma, Lo, Wang, Lu, Yuan, Chen, Han, Chen, Zhan, Xu, Yin, Shang, Wen, Chen, Cui
      (2026) "MATCH: Modulating Attention via In-Context Retrieval for Long-Context
      Transformers", arXiv:2606.29844 (ACL 2026 Main).
      https://arxiv.org/abs/2606.29844
    * Wei, Gulcehre (2026) "Augmenting Attention with Exponentially Decaying Memory
      Improves Query-Aware KV Sparsity", arXiv:2605.28640.
      https://arxiv.org/abs/2605.28640

HONESTY SPINE (Doctrine v11)
    * Label "MODELED" — returned VERBATIM, read verbatim by retrievalattn.js, NEVER
      upgraded. The four read policies + the cosine retrieval math run for real; the
      needle task they run over is SEEDED synthetic data, NOT a real trained model /
      corpus / GPU. Recall figures are properties of the modeled task, honestly
      labelled — not a MEASURED claim about a deployed engine.
    * Advisory only. Λ = Conjecture 1; adds NOTHING to the locked-8; trust never 100%.

ENDPOINT (mounted BEFORE the SPA catch-all; front-moved to router position 0 by serve.py)
    GET /api/a11oy/v1/retrievalattn/recall?seed=&seq_len=&window=&n_needles=&retrieval_k=&dim=&decay=
        -> renderable 200 JSON compatible with retrievalattn.js:
           {label:"MODELED", seq_len, window, n_needles, retrieval_k, dim, decay,
            full_long_range_recall, sparse_long_range_recall, edm_long_range_recall,
            retrieval_long_range_recall, long_range_recall_recovery,
            retrieval_vs_edm_gain, *_recall (overall), attend_frac_*,
            n_long_range_needles, n_window_needles, per_needle[], receipt{...}, citations[]}
"""
import hashlib
import math
import time
from typing import Any, Dict, List

from fastapi import FastAPI
from fastapi.responses import JSONResponse

DOCTRINE = {"version": "v11", "counts": "749/14/163", "lambda": "Conjecture 1",
            "locked_proven": 8}

CITATIONS = [
    {"id": "match_2026",
     "cite": ("Ma, Lo, Wang et al. (2026) MATCH: Modulating Attention via In-Context "
              "Retrieval for Long-Context Transformers (ACL 2026 Main)."),
     "url": "https://arxiv.org/abs/2606.29844"},
    {"id": "edm_2026",
     "cite": ("Wei, Gulcehre (2026) Augmenting Attention with Exponentially Decaying "
              "Memory Improves Query-Aware KV Sparsity."),
     "url": "https://arxiv.org/abs/2605.28640"},
]


def _rng(seed: int):
    state = (seed * 6364136223846793005 + 1442695040888963407) & ((1 << 64) - 1)

    def nxt() -> float:
        nonlocal state
        state = (state * 6364136223846793005 + 1442695040888963407) & ((1 << 64) - 1)
        return ((state >> 11) & ((1 << 53) - 1)) / float(1 << 53)

    return nxt


def _unit(v: List[float]) -> List[float]:
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def _dot(a: List[float], b: List[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _build_task(seed: int, seq_len: int, n_needles: int, dim: int):
    """Seed a query vector q and seq_len token key vectors. n_needles positions carry a
    key deliberately aligned with q (retrievable signal); the rest are weak distractors.
    Returns (q, keys, needle_positions)."""
    rnd = _rng(seed)

    def gauss() -> float:
        # Box–Muller from the seeded uniform stream (deterministic).
        u1 = max(1e-12, rnd())
        u2 = rnd()
        return math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)

    q = _unit([gauss() for _ in range(dim)])

    # choose distinct needle positions across the whole sequence
    needle_pos: List[int] = []
    seen = set()
    guard = 0
    while len(needle_pos) < n_needles and guard < seq_len * 20:
        guard += 1
        p = int(rnd() * seq_len)
        if p not in seen:
            seen.add(p)
            needle_pos.append(p)
    needle_pos.sort()
    needle_set = set(needle_pos)

    keys: List[List[float]] = []
    for i in range(seq_len):
        noise = [gauss() for _ in range(dim)]
        if i in needle_set:
            # strong, varied alignment with q -> high, but not uniform, cos similarity
            alpha = 0.55 + 0.4 * rnd()
            vec = [alpha * q[d] + (1.0 - alpha) * 0.6 * noise[d] for d in range(dim)]
        else:
            # weak distractor: small q-component so a few distractors are near-miss
            beta = 0.05 + 0.22 * rnd()
            vec = [beta * q[d] + noise[d] for d in range(dim)]
        keys.append(_unit(vec))
    return q, keys, needle_pos


def _simulate(seed: int, seq_len: int, window: int, n_needles: int,
              retrieval_k: int, dim: int, decay: float) -> Dict[str, Any]:
    seq_len = max(32, min(int(seq_len), 4096))
    dim = max(4, min(int(dim), 64))
    window = max(1, min(int(window), seq_len - 1))
    n_needles = max(1, min(int(n_needles), max(1, seq_len // 4)))
    retrieval_k = max(1, min(int(retrieval_k), seq_len - window))
    decay = min(1.0, max(1e-4, float(decay)))

    q, keys, needle_pos = _build_task(seed, seq_len, n_needles, dim)
    sims = [_dot(q, keys[i]) for i in range(seq_len)]

    window_lo = seq_len - window                      # first index inside the window
    in_window = {p for p in needle_pos if p >= window_lo}
    long_range = [p for p in needle_pos if p < window_lo]

    # RETRIEVAL: score the DROPPED region (outside window) by cos(q, k), re-inject Top-k.
    dropped = [i for i in range(seq_len) if i < window_lo]
    retrieved = set(sorted(dropped, key=lambda i: sims[i], reverse=True)[:retrieval_k])

    # EDM: a position-decayed memory clears a fixed threshold only for recent-enough
    # tokens; content is ignored, so far needles fade regardless of similarity.
    edm_thresh = 0.05
    def _edm_weight(pos: int) -> float:
        age = (seq_len - 1) - pos                      # 0 == most recent
        return math.exp(-decay * age)
    edm_recovered = {i for i in dropped if _edm_weight(i) >= edm_thresh}

    def _recalled(pos: int, policy: str) -> bool:
        if pos >= window_lo:
            return True                                # every policy keeps the window
        if policy == "full":
            return True
        if policy == "sparse":
            return False
        if policy == "edm":
            return pos in edm_recovered
        if policy == "retrieval":
            return pos in retrieved
        return False

    def _lr_recall(policy: str) -> float:
        if not long_range:
            return 1.0
        hit = sum(1 for p in long_range if _recalled(p, policy))
        return hit / len(long_range)

    def _overall_recall(policy: str) -> float:
        hit = sum(1 for p in needle_pos if _recalled(p, policy))
        return hit / len(needle_pos)

    full_lr     = _lr_recall("full")
    sparse_lr   = _lr_recall("sparse")
    edm_lr      = _lr_recall("edm")
    retr_lr     = _lr_recall("retrieval")

    per_needle = []
    for p in needle_pos:
        per_needle.append({
            "pos": p,
            "in_window": p in in_window,
            "sim": round(sims[p], 4),
            "retrieved": p in retrieved,
            "edm_weight": round(_edm_weight(p), 4),
            "recalled_sparse": _recalled(p, "sparse"),
            "recalled_edm": _recalled(p, "edm"),
            "recalled_retrieval": _recalled(p, "retrieval"),
        })

    return {
        "seq_len": seq_len,
        "window": window,
        "n_needles": n_needles,
        "retrieval_k": retrieval_k,
        "dim": dim,
        "decay": round(decay, 4),
        "n_long_range_needles": len(long_range),
        "n_window_needles": len(in_window),
        "full_long_range_recall": round(full_lr, 4),
        "sparse_long_range_recall": round(sparse_lr, 4),
        "edm_long_range_recall": round(edm_lr, 4),
        "retrieval_long_range_recall": round(retr_lr, 4),
        "long_range_recall_recovery": round(retr_lr - sparse_lr, 4),
        "retrieval_vs_edm_gain": round(retr_lr - edm_lr, 4),
        "full_recall": round(_overall_recall("full"), 4),
        "sparse_recall": round(_overall_recall("sparse"), 4),
        "edm_recall": round(_overall_recall("edm"), 4),
        "retrieval_recall": round(_overall_recall("retrieval"), 4),
        "attend_frac_sparse": round(window / seq_len, 4),
        "attend_frac_retrieval": round((window + retrieval_k) / seq_len, 4),
        "attend_frac_full": 1.0,
        "per_needle": per_needle,
    }


def _receipt(payload: Dict[str, Any], seed: int) -> Dict[str, Any]:
    blob = repr(sorted(payload.items())).encode("utf-8")
    return {
        "digest_sha256": hashlib.sha256(blob).hexdigest(),
        "seed": seed,
        "signature": "UNSIGNED-LOCAL",
        "note": ("content digest over the MODELED recall result; deterministic in the "
                 "seed. No DSSE signature claimed locally (UNSIGNED-LOCAL)."),
    }


def register(app: FastAPI, ns: str = "a11oy") -> str:
    @app.get(f"/api/{ns}/v1/retrievalattn/recall", include_in_schema=False)
    async def _recall(seed: int = 42, seq_len: int = 512, window: int = 64,
                      n_needles: int = 12, retrieval_k: int = 16, dim: int = 16,
                      decay: float = 0.08) -> JSONResponse:
        t0 = time.time()
        try:
            sim = _simulate(int(seed), int(seq_len), int(window), int(n_needles),
                            int(retrieval_k), int(dim), float(decay))
        except Exception as e:
            return JSONResponse({"label": "UNAVAILABLE",
                                 "detail": f"recall sim failed: {type(e).__name__}",
                                 "doctrine": DOCTRINE, "citations": CITATIONS},
                                status_code=200)
        digest_src = {k: v for k, v in sim.items() if k != "per_needle"}
        body = {
            "label": "MODELED",
            "surface": "retrievalattn",
            "title": "Retrieval-Modulated Long-Context Attention · needle recall (MODELED)",
            "method": ("real full / sparse-window / exponentially-decaying-memory / "
                       "retrieval-augmented read policies run over a SEEDED synthetic "
                       "needle task; cosine retrieval + recall math are exact, the task "
                       "is synthetic. NOT a real trained model / corpus / GPU."),
            **sim,
            "receipt": _receipt(digest_src, int(seed)),
            "citations": CITATIONS,
            "doctrine": DOCTRINE,
            "honesty": ("MODELED: the read policies + cosine retrieval are real; the "
                        "needle task they run over is synthetic. Not a measured claim "
                        "about a deployed engine. Λ=Conjecture 1; adds nothing to the "
                        "locked-8; trust never 100%."),
            "elapsed_ms": round((time.time() - t0) * 1000, 2),
        }
        return JSONResponse(body, status_code=200)

    return (f"retrieval-modulated attention mounted: "
            f"GET /api/{ns}/v1/retrievalattn/recall (label MODELED)")


def _selftest() -> None:
    sim = _simulate(42, 512, 64, 12, 16, 16, 0.08)
    # invariants any correct set of policies MUST satisfy
    assert sim["full_long_range_recall"] == 1.0, "full oracle must recall all long-range"
    assert sim["sparse_long_range_recall"] == 0.0, "sparse window cannot reach long-range"
    assert 0.0 <= sim["retrieval_long_range_recall"] <= 1.0, "retrieval LR out of range"
    # MATCH recovers long-range recall a plain sparse window structurally cannot
    assert sim["retrieval_long_range_recall"] >= sim["sparse_long_range_recall"], \
        "retrieval must recover >= sparse long-range recall"
    assert sim["long_range_recall_recovery"] >= 0.0, "recovery cannot be negative"
    assert sim["retrieval_long_range_recall"] > 0.0, \
        "content retrieval should recover some long-range needles"
    # retrieval stays sub-dense (cheaper than the full oracle) yet beats sparse cost-blind
    assert sim["attend_frac_retrieval"] < sim["attend_frac_full"], "retrieval not sub-dense"
    assert sim["attend_frac_sparse"] <= sim["attend_frac_retrieval"], "sparse costs more?"
    assert sim["n_long_range_needles"] + sim["n_window_needles"] == sim["n_needles"], \
        "needle partition must be exhaustive"
    assert len(sim["per_needle"]) == sim["n_needles"], "per_needle length mismatch"
    # determinism
    assert _simulate(42, 512, 64, 12, 16, 16, 0.08) == sim, "non-deterministic for fixed seed"
    r = _receipt({k: v for k, v in sim.items() if k != "per_needle"}, 42)
    assert r["signature"] == "UNSIGNED-LOCAL", "must not fabricate a signature"
    print("szl_retrieval_attn: ALL OK (full=1.0, sparse LR=0, retrieval recovers "
          f"{sim['long_range_recall_recovery']:.2f} LR-recall, sub-dense, deterministic, "
          "UNSIGNED-LOCAL receipt)")


if __name__ == "__main__":
    _selftest()
