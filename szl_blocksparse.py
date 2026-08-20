# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
# Doctrine v11 LOCKED: locked-proven=8 · Λ=Conjecture 1 · SLSA L1 honest / L2 attested / L3 roadmap
# Co-Authored-By: Perplexity Computer Agent
"""
szl_blocksparse.py — ADDITIVE a11oy-NATIVE cited LEARNED BLOCKWISE TOP-k KV
SPARSE-ATTENTION backend for the holographic frontier surface
static/3d/surfaces/blocksparse.js (surface id: blocksparse).

WHY THIS EXISTS
    The estate already models native sparse attention (nsa) and semantic-entropy
    (sement) — but NOT the LEARNED BLOCKWISE selection frontier that now powers the
    strongest long-context decoders: DeepSeek-style Native Sparse Attention and the
    MiniMax Sparse Attention (MSA) / SparDA family. Their shared idea: instead of the
    O(L) dense KV scan, a cheap INDEX BRANCH scores KV BLOCKS, a per-GQA-group Top-k
    keeps only the most relevant blocks, and EXACT attention runs over just those
    blocks. This module is the a11oy-native honest primary for that frontier: a REAL,
    deterministic, pure-stdlib (NO numpy) implementation of the index-branch block
    scorer, the per-group Top-k selection, and the resulting block-sparse attention —
    run over a SEEDED long-context KV cache, so the compute-reduction vs dense and the
    recall/quality tradeoff are visible and reproducible.

METHOD (learned blockwise Top-k selection — MODELED on a synthetic KV cache)
    A decode query attends over a KV cache of length L. The cache is partitioned into
    B = ceil(L / block_size) contiguous BLOCKS. For each GQA group (a set of query
    heads sharing one KV head — selection is done ONCE per group so the loaded KV
    positions are coalesced, exactly as NSA/MSA require):

      * INDEX BRANCH (cheap, O(B)):  each block b gets a compressed representation
            k̄_b = mean-pool of the keys in block b. The index score for the group query
            q is s_b = q · k̄_b. This is the "learned" cheap proxy for block importance;
            it costs B dot-products instead of L.

      * TOP-k SELECTION:  keep the k blocks with the highest index score (the most-
            recent / local block is always kept — the sliding-window component). Only
            those k·block_size positions are read.

      * BLOCK-SPARSE ATTENTION (exact over selected blocks):  softmax(q·k_i) over the
            positions inside the selected blocks only, then Σ p_i v_i. Dense attention
            is the same softmax over ALL L positions; block-sparse == dense EXACTLY when
            k = B.

    We report, per group and averaged:
      * compute_fraction = selected_positions / L  (and its reciprocal, the reduction ×)
      * index_recall   = attention-probability MASS (under the DENSE softmax) that falls
                         inside the index-branch-selected blocks — how much of what the
                         dense model actually attends to the cheap selector captured.
      * oracle_recall  = the same mass for the TRUE top-k blocks (ranked by real mass);
                         index_recall ≤ oracle_recall is the honest cost of the cheap
                         index vs an exact-but-expensive ranker.
      * output_cos / output_rel_err = fidelity of the block-sparse output vector to the
                         dense output vector.
      * a TRADEOFF CURVE sweeping k = 1..B: (compute_fraction, index_recall, output_cos)
                         — the recall/quality ↔ compute tradeoff these methods trade on.

MATH (all REAL computations over the seeded cache; NOT a trained model / GPU)
    * keys/values: L seeded d-vectors; the query is correlated with a few "hot" blocks
      (a seeded mixture) so the selection problem is non-trivial (mass concentrates).
    * softmax with max-subtraction for numerical stability; probabilities sum to 1.
    * recall/precision/cosine are exact properties of the modeled cache, reported as-is.

LEADERS ADOPTED & CITED (clean-room; NOT claimed as SZL's own; VERIFIED real ids):
    * MiniMax et al. (2026) "MiniMax Sparse Attention (MSA)", arXiv:2606.13392.
      https://arxiv.org/abs/2606.13392
    * (2026) "SparDA: Sparse Decoupled Attention", arXiv:2606.04511.
      https://arxiv.org/abs/2606.04511
    * Yuan, Gao, Dai et al. (2025) "Native Sparse Attention: Hardware-Aligned and
      Natively Trainable Sparse Attention" (NSA, DeepSeek), arXiv:2502.11089.
      https://arxiv.org/abs/2502.11089

HONESTY SPINE (Doctrine v11)
    * Label "MODELED" — returned VERBATIM, read verbatim by blocksparse.js, NEVER
      upgraded. The index-branch / Top-k / block-sparse attention math is implemented
      EXACTLY and runs for real; the KV CACHE it runs over is SEEDED synthetic data,
      NOT a real trained model / GPU / dataset. Every number is a property of the
      modeled cache.
    * Advisory only. Λ = Conjecture 1; adds NOTHING to the locked-8; trust never 100%.
    * Distinct from nsa (fixed local/dilated pattern demo) and sement (uncertainty):
      this surface is specifically the LEARNED index-branch blockwise Top-k selection.

ENDPOINT (mounted BEFORE the SPA catch-all; front-moved to router position 0 by serve.py)
    GET /api/a11oy/v1/blocksparse/select?seed=&seq_len=&block_size=&top_k=&n_groups=&group_share=&dim=
        -> renderable 200 JSON compatible with blocksparse.js:
           {label:"MODELED", seq_len, block_size, n_blocks, top_k, n_groups, group_share,
            dim, dense_positions, sparse_positions, compute_fraction, compute_reduction,
            index_recall, oracle_recall, selection_precision, output_cos, output_rel_err,
            tradeoff[], per_group[], receipt{...}, citations[]}
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
    {"id": "minimax_msa_2026",
     "cite": "MiniMax et al. (2026) MiniMax Sparse Attention (MSA).",
     "url": "https://arxiv.org/abs/2606.13392"},
    {"id": "sparda_2026",
     "cite": "(2026) SparDA: Sparse Decoupled Attention.",
     "url": "https://arxiv.org/abs/2606.04511"},
    {"id": "nsa_deepseek_2025",
     "cite": ("Yuan, Gao, Dai et al. (2025) Native Sparse Attention: Hardware-Aligned "
              "and Natively Trainable Sparse Attention (NSA)."),
     "url": "https://arxiv.org/abs/2502.11089"},
]


# ---------------------------------------------------------------------------
# seeded RNG (same LCG family as szl_gated_delta.py — deterministic, stdlib-only)
# ---------------------------------------------------------------------------
def _rng(seed: int):
    state = (seed * 6364136223846793005 + 1442695040888963407) & ((1 << 64) - 1)

    def nxt() -> float:
        nonlocal state
        state = (state * 6364136223846793005 + 1442695040888963407) & ((1 << 64) - 1)
        return ((state >> 11) & ((1 << 53) - 1)) / float(1 << 53)

    return nxt


# ---------------------------------------------------------------------------
# tiny pure-stdlib linear-algebra helpers (no numpy)
# ---------------------------------------------------------------------------
def _dot(a: List[float], b: List[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _norm(a: List[float]) -> float:
    return math.sqrt(_dot(a, a))


def _cos(a: List[float], b: List[float]) -> float:
    na, nb = _norm(a), _norm(b)
    if na < 1e-12 or nb < 1e-12:
        return 0.0
    return _dot(a, b) / (na * nb)


def _rand_vec(rnd, d: int) -> List[float]:
    return [rnd() * 2.0 - 1.0 for _ in range(d)]


def _softmax(scores: List[float]) -> List[float]:
    if not scores:
        return []
    m = max(scores)
    exps = [math.exp(s - m) for s in scores]
    z = sum(exps) or 1.0
    return [e / z for e in exps]


def _blocks(n: int, block_size: int) -> List[Tuple[int, int]]:
    """Contiguous [start, end) block ranges covering [0, n)."""
    out: List[Tuple[int, int]] = []
    start = 0
    while start < n:
        out.append((start, min(n, start + block_size)))
        start += block_size
    return out


# ---------------------------------------------------------------------------
# core: index-branch blockwise Top-k selection + block-sparse attention
# ---------------------------------------------------------------------------
def _block_means(keys: List[List[float]], blocks: List[Tuple[int, int]], d: int) -> List[List[float]]:
    """Index-branch compressed key: mean-pool of the keys in each block (O(L), cheap)."""
    means: List[List[float]] = []
    for (s, e) in blocks:
        acc = [0.0] * d
        for i in range(s, e):
            ki = keys[i]
            for j in range(d):
                acc[j] += ki[j]
        n = max(1, e - s)
        means.append([a / n for a in acc])
    return means


def _dense_attend(q: List[float], keys: List[List[float]], values: List[List[float]],
                  scale: float, d: int) -> Tuple[List[float], List[float]]:
    """Exact dense attention over all positions. Returns (output_vec, per_position_probs)."""
    scores = [scale * _dot(q, k) for k in keys]
    probs = _softmax(scores)
    out = [0.0] * d
    for p, v in zip(probs, values):
        for j in range(d):
            out[j] += p * v[j]
    return out, probs


def _sparse_attend(q: List[float], keys: List[List[float]], values: List[List[float]],
                   selected: List[Tuple[int, int]], scale: float, d: int) -> List[float]:
    """Exact softmax attention restricted to positions inside the selected blocks."""
    idx: List[int] = []
    for (s, e) in selected:
        idx.extend(range(s, e))
    scores = [scale * _dot(q, keys[i]) for i in idx]
    probs = _softmax(scores)
    out = [0.0] * d
    for p, i in zip(probs, idx):
        vi = values[i]
        for j in range(d):
            out[j] += p * vi[j]
    return out


def _mass_in_blocks(probs: List[float], blocks: List[Tuple[int, int]],
                    chosen: List[int]) -> float:
    """Dense attention-probability MASS that falls inside the chosen block indices."""
    total = 0.0
    for bi in chosen:
        s, e = blocks[bi]
        total += sum(probs[s:e])
    return total


def _select_topk(scores: List[float], k: int, force_last: int) -> List[int]:
    """Indices of the top-k scores (desc). force_last (the local/sliding block) is
    always included; ties broken by lower index for determinism."""
    order = sorted(range(len(scores)), key=lambda b: (-scores[b], b))
    chosen = order[:max(0, k)]
    if force_last not in chosen:
        # drop the weakest chosen block to make room for the mandatory local block
        if chosen:
            chosen[-1] = force_last
        else:
            chosen = [force_last]
    return sorted(set(chosen))


def _simulate(seed: int, seq_len: int, block_size: int, top_k: int,
              n_groups: int, group_share: int, dim: int) -> Dict[str, Any]:
    seq_len = max(16, min(int(seq_len), 1024))
    block_size = max(2, min(int(block_size), 64))
    dim = max(4, min(int(dim), 32))
    n_groups = max(1, min(int(n_groups), 8))
    group_share = max(1, min(int(group_share), 16))

    blocks = _blocks(seq_len, block_size)
    n_blocks = len(blocks)
    top_k = max(1, min(int(top_k), n_blocks))
    scale = 1.0 / math.sqrt(dim)

    rnd = _rng(seed)
    keys = [_rand_vec(rnd, dim) for _ in range(seq_len)]
    values = [_rand_vec(rnd, dim) for _ in range(seq_len)]

    # Per group: a query correlated with a seeded subset of "hot" blocks, so attention
    # mass concentrates (the selection problem is non-trivial but learnable).
    def _group_query(g: int) -> List[float]:
        gr = _rng(seed * 131 + g * 977)
        q = _rand_vec(gr, dim)
        n_hot = 1 + int(gr() * 3)
        for _ in range(n_hot):
            hb = int(gr() * n_blocks) % n_blocks
            s, e = blocks[hb]
            anchor = keys[s + (e - s) // 2]
            w = 1.0 + gr() * 2.0
            for j in range(dim):
                q[j] += w * anchor[j]
        return q

    def _metrics_for_k(q: List[float], probs: List[float], index_scores: List[float],
                       block_mass: List[float], k: int) -> Dict[str, Any]:
        local = n_blocks - 1
        chosen = _select_topk(index_scores, k, force_last=local)
        oracle = _select_topk(block_mass, k, force_last=local)
        sel_ranges = [blocks[b] for b in chosen]
        sel_positions = sum(e - s for (s, e) in sel_ranges)
        idx_recall = _mass_in_blocks(probs, blocks, chosen)
        orc_recall = _mass_in_blocks(probs, blocks, oracle)
        out_sparse = _sparse_attend(q, keys, values, sel_ranges, scale, dim)
        return {"chosen": chosen, "oracle": oracle, "sel_positions": sel_positions,
                "index_recall": idx_recall, "oracle_recall": orc_recall,
                "out_sparse": out_sparse}

    per_group: List[Dict[str, Any]] = []
    tradeoff_acc: List[Dict[str, List[float]]] = [
        {"cf": [], "ir": [], "orc": [], "cos": []} for _ in range(n_blocks + 1)]

    agg = {"cf": 0.0, "ir": 0.0, "orc": 0.0, "cos": 0.0, "relerr": 0.0,
           "prec": 0.0, "sel_pos": 0.0}

    for g in range(n_groups):
        q = _group_query(g)
        out_dense, probs = _dense_attend(q, keys, values, scale, dim)
        index_means = _block_means(keys, blocks, dim)
        index_scores = [_dot(q, km) for km in index_means]
        block_mass = [sum(probs[s:e]) for (s, e) in blocks]

        # tradeoff curve for this group (k = 1..n_blocks), averaged across groups below
        for k in range(1, n_blocks + 1):
            mk = _metrics_for_k(q, probs, index_scores, block_mass, k)
            cf = mk["sel_positions"] / seq_len
            cos = _cos(mk["out_sparse"], out_dense)
            tradeoff_acc[k]["cf"].append(cf)
            tradeoff_acc[k]["ir"].append(mk["index_recall"])
            tradeoff_acc[k]["orc"].append(mk["oracle_recall"])
            tradeoff_acc[k]["cos"].append(cos)

        # the reported operating point at the requested top_k
        m = _metrics_for_k(q, probs, index_scores, block_mass, top_k)
        cos = _cos(m["out_sparse"], out_dense)
        nd = _norm(out_dense) or 1.0
        relerr = _norm([a - b for a, b in zip(m["out_sparse"], out_dense)]) / nd
        cf = m["sel_positions"] / seq_len
        # selection precision: overlap of index-selected vs oracle top-k blocks
        inter = len(set(m["chosen"]) & set(m["oracle"]))
        prec = inter / max(1, len(m["chosen"]))

        agg["cf"] += cf
        agg["ir"] += m["index_recall"]
        agg["orc"] += m["oracle_recall"]
        agg["cos"] += cos
        agg["relerr"] += relerr
        agg["prec"] += prec
        agg["sel_pos"] += m["sel_positions"]

        per_group.append({
            "group": g,
            "heads": group_share,
            "selected_blocks": m["chosen"],
            "oracle_blocks": m["oracle"],
            "index_recall": round(m["index_recall"], 6),
            "oracle_recall": round(m["oracle_recall"], 6),
            "output_cos": round(cos, 6),
            "output_rel_err": round(relerr, 6),
        })

    ng = float(n_groups)
    mean = lambda xs: (sum(xs) / len(xs)) if xs else 0.0
    tradeoff: List[Dict[str, Any]] = []
    for k in range(1, n_blocks + 1):
        t = tradeoff_acc[k]
        tradeoff.append({
            "top_k": k,
            "compute_fraction": round(mean(t["cf"]), 6),
            "index_recall": round(mean(t["ir"]), 6),
            "oracle_recall": round(mean(t["orc"]), 6),
            "output_cos": round(mean(t["cos"]), 6),
        })

    sparse_positions = agg["sel_pos"] / ng
    compute_fraction = agg["cf"] / ng
    compute_reduction = (1.0 / compute_fraction) if compute_fraction > 1e-12 else float(n_blocks)

    return {
        "seq_len": seq_len,
        "block_size": block_size,
        "n_blocks": n_blocks,
        "top_k": top_k,
        "n_groups": n_groups,
        "group_share": group_share,
        "dim": dim,
        "dense_positions": seq_len,
        "sparse_positions": round(sparse_positions, 3),
        "compute_fraction": round(compute_fraction, 6),
        "compute_reduction": round(compute_reduction, 4),
        "index_recall": round(agg["ir"] / ng, 6),
        "oracle_recall": round(agg["orc"] / ng, 6),
        "selection_precision": round(agg["prec"] / ng, 6),
        "output_cos": round(agg["cos"] / ng, 6),
        "output_rel_err": round(agg["relerr"] / ng, 6),
        "tradeoff": tradeoff,
        "per_group": per_group,
    }


def _receipt(payload: Dict[str, Any], seed: int) -> Dict[str, Any]:
    blob = repr(sorted(payload.items())).encode("utf-8")
    return {
        "digest_sha256": hashlib.sha256(blob).hexdigest(),
        "seed": seed,
        "signature": "UNSIGNED-LOCAL",
        "note": ("content digest over the MODELED blockwise Top-k selection result; "
                 "deterministic in the seed. No DSSE signature claimed locally "
                 "(UNSIGNED-LOCAL)."),
    }


def register(app: FastAPI, ns: str = "a11oy") -> str:
    @app.get(f"/api/{ns}/v1/blocksparse/select", include_in_schema=False)
    async def _blocksparse_select(seed: int = 42, seq_len: int = 256, block_size: int = 16,
                                  top_k: int = 4, n_groups: int = 4, group_share: int = 4,
                                  dim: int = 8) -> JSONResponse:
        t0 = time.time()
        try:
            sim = _simulate(int(seed), int(seq_len), int(block_size), int(top_k),
                            int(n_groups), int(group_share), int(dim))
        except Exception as e:
            return JSONResponse({"label": "UNAVAILABLE",
                                 "detail": f"blocksparse sim failed: {type(e).__name__}",
                                 "doctrine": DOCTRINE, "citations": CITATIONS},
                                status_code=200)
        digest_src = {k: v for k, v in sim.items() if k not in ("per_group", "tradeoff")}
        body = {
            "label": "MODELED",
            "surface": "blocksparse",
            "title": "Learned Blockwise Top-k KV Sparse Attention · selection (MODELED)",
            "method": ("real index-branch block scoring + per-GQA-group Top-k selection + "
                       "exact block-sparse attention run over a SEEDED long-context KV "
                       "cache. The attention math is exact; the cache is synthetic. NOT a "
                       "real trained model / GPU / dataset."),
            **sim,
            "receipt": _receipt(digest_src, int(seed)),
            "citations": CITATIONS,
            "doctrine": DOCTRINE,
            "honesty": ("MODELED: index-branch / Top-k / block-sparse attention math is "
                        "real; the KV cache it runs over is synthetic. Distinct from "
                        "nsa/sement. Not a measured claim about a deployed engine. "
                        "Λ=Conjecture 1; adds nothing to the locked-8; trust never 100%."),
            "elapsed_ms": round((time.time() - t0) * 1000, 2),
        }
        return JSONResponse(body, status_code=200)

    return (f"learned blockwise Top-k KV selection mounted: "
            f"GET /api/{ns}/v1/blocksparse/select (label MODELED)")


def _selftest() -> None:
    sim = _simulate(42, 256, 16, 4, 4, 4, 8)
    n_blocks = sim["n_blocks"]

    # basic shape / range invariants
    assert 0.0 < sim["compute_fraction"] <= 1.0, "compute fraction must be a fraction of dense"
    assert sim["compute_reduction"] >= 1.0, "sparse must not read more positions than dense"
    assert sim["sparse_positions"] <= sim["dense_positions"] + 1e-9, "sparse ≤ dense positions"
    assert 0.0 <= sim["index_recall"] <= 1.0 + 1e-9, "recall is a probability mass fraction"
    assert 0.0 <= sim["oracle_recall"] <= 1.0 + 1e-9, "oracle recall is a mass fraction"
    # the cheap index branch can NEVER capture more mass than the exact oracle top-k
    assert sim["index_recall"] <= sim["oracle_recall"] + 1e-9, \
        "index-branch recall must not exceed the exact oracle top-k recall"
    assert -1.0 - 1e-9 <= sim["output_cos"] <= 1.0 + 1e-9, "cosine in [-1,1]"

    # tradeoff curve honesty: recall / cosine are non-decreasing in k; at k=n_blocks the
    # block-sparse attention is EXACTLY dense (recall=1, cos=1, compute_fraction=1).
    tr = {row["top_k"]: row for row in sim["tradeoff"]}
    assert len(sim["tradeoff"]) == n_blocks, "tradeoff must sweep k=1..n_blocks"
    for k in range(2, n_blocks + 1):
        assert tr[k]["oracle_recall"] >= tr[k - 1]["oracle_recall"] - 1e-9, \
            "oracle recall must be non-decreasing as k grows"
        assert tr[k]["compute_fraction"] >= tr[k - 1]["compute_fraction"] - 1e-9, \
            "compute fraction must be non-decreasing as k grows"
    full = tr[n_blocks]
    assert full["oracle_recall"] > 0.999, "k=all blocks must recall ~all attention mass"
    assert full["index_recall"] > 0.999, "k=all blocks must recall ~all attention mass"
    assert full["output_cos"] > 0.999, "k=all blocks must reproduce dense output exactly"
    assert abs(full["compute_fraction"] - 1.0) < 1e-6, "k=all blocks reads every position"

    # a real reduction exists at the requested operating point (k < n_blocks)
    assert sim["compute_fraction"] < 1.0, "requested top_k must be genuinely sparse"
    assert sim["index_recall"] > sim["compute_fraction"], \
        "selection must capture MORE mass than the compute fraction it spends (it works)"
    assert 0.0 <= sim["selection_precision"] <= 1.0 + 1e-9, "precision in [0,1]"
    assert len(sim["per_group"]) == sim["n_groups"], "per_group length mismatch"

    # determinism + honest receipt
    assert _simulate(42, 256, 16, 4, 4, 4, 8) == sim, "non-deterministic for fixed seed"
    r = _receipt({k: v for k, v in sim.items() if k not in ("per_group", "tradeoff")}, 42)
    assert r["signature"] == "UNSIGNED-LOCAL", "must not fabricate a signature"

    print("szl_blocksparse: ALL OK "
          f"(n_blocks={n_blocks} top_k={sim['top_k']} "
          f"compute_fraction={sim['compute_fraction']} reduction={sim['compute_reduction']}x "
          f"index_recall={sim['index_recall']} oracle_recall={sim['oracle_recall']} "
          f"out_cos={sim['output_cos']}; deterministic; UNSIGNED-LOCAL)")


if __name__ == "__main__":
    _selftest()
