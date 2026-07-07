# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
# Doctrine v11 LOCKED: locked-proven=8 · Λ=Conjecture 1 · SLSA L1 honest / L2 attested / L3 roadmap
# Co-Authored-By: Perplexity Computer Agent
"""
szl_kv_cache.py — ADDITIVE a11oy-NATIVE KV-CACHE / LONG-CONTEXT EFFICIENCY backend
for the holographic frontier surface static/3d/surfaces/kvcache.js.

WHY THIS EXISTS
    kvcache.js previously read ONLY the isolated killinchu Space
    (/api/killinchu/v1/kvcache/h2o-evict) cross-origin, so a11oy had NO self-hosted
    twin: a killinchu flap darkened the surface. This module is the a11oy-native honest
    primary — a REAL, deterministic implementation of the H2O heavy-hitter eviction
    policy (and a StreamingLLM recency/attention-sink baseline + a full-cache oracle)
    run over a seeded attention-mass trace.

METHOD (H2O heavy-hitter + StreamingLLM — MODELED on a synthetic trace; NO real cache)
    Long-context decoding is dominated by the KV cache, which grows with sequence
    length. H2O (Heavy-Hitter Oracle, Zhang et al. 2023) observes that a SMALL set of
    tokens ("heavy hitters") accumulate most of the attention mass, so a fixed-budget
    cache can KEEP the heavy hitters + a recent window and EVICT the rest with little
    quality loss. StreamingLLM (Xiao et al. 2023) keeps a few "attention-sink" tokens
    at the start + a recent sliding window. We implement all three policies exactly and
    report the fraction of TRUE (full-cache oracle) attention mass each retains.

MATH (all REAL computations over the seeded mass trace; NOT a trained model)
    * mass[i] = seeded per-token accumulated attention mass, i in [0, seq_len).
    * FULL oracle: keeps every token -> retains 100% of the mass (baseline).
    * H2O(capacity C, window W): always keep the last W tokens (recency); fill the
      remaining C-W budget with the highest-mass ("heavy hitter") tokens among the rest.
      h2o_mass_retained = sum(mass[kept]) / sum(mass[all]).
    * StreamingLLM(sink S, window W): keep the first S sink tokens + the last W tokens.
      sliding_mass_retained = sum(mass[kept]) / sum(mass[all]).
    * memory_ratio = C / seq_len (the cache-budget compression).
    * h2o_vs_sliding_gain = h2o_mass_retained - sliding_mass_retained (H2O's advantage
      from catching heavy hitters the pure recency window misses).
    * per_token[i] = {mass, h2o_kept, sliding_kept} so the surface can colour kept
      heavy-hitters vs the recent window vs evicted tokens.

LEADERS ADOPTED & CITED (clean-room; NOT claimed as SZL's own; VERIFY real):
    * Zhang, Sheng, Zhou, Chen, Zheng, Cai, Song, Tian, Ré, Barrett, Wang, Chen (2023)
      "H2O: Heavy-Hitter Oracle for Efficient Generative Inference of LLMs",
      arXiv:2306.14048.  https://arxiv.org/abs/2306.14048
    * Xiao, Tian, Chen, Han, Lewis (2023) "Efficient Streaming Language Models with
      Attention Sinks" (StreamingLLM), arXiv:2309.17453.
      https://arxiv.org/abs/2309.17453
    * Beltagy, Peters, Cohan (2020) "Longformer: The Long-Document Transformer",
      arXiv:2004.05150 (windowed-attention lineage).  https://arxiv.org/abs/2004.05150

HONESTY SPINE (Doctrine v11)
    * Label "MODELED" — returned VERBATIM, read verbatim by kvcache.js, NEVER upgraded.
      The EVICTION POLICIES are implemented exactly and run for real; the ATTENTION-MASS
      TRACE they run over is SEEDED synthetic data, NOT a real KV cache / trained model /
      GPU. Retained-mass figures are properties of the modeled trace, honestly labelled.
    * Advisory only. Λ = Conjecture 1; adds NOTHING to the locked-8; trust never 100%.

ENDPOINT (mounted BEFORE the SPA catch-all; front-moved to router position 0 by serve.py)
    GET /api/a11oy/v1/kvcache/h2o-evict?seed=&seq_len=&capacity=&window=
        -> renderable 200 JSON compatible with kvcache.js:
           {label:"MODELED", seq_len, capacity, window, memory_ratio,
            h2o_mass_retained, sliding_mass_retained, full_mass_retained,
            h2o_vs_sliding_gain, evicted_count, per_token[], receipt{...}, citations[]}
"""
from __future__ import annotations

import hashlib
import math
import time
from typing import Any, Dict, List

from fastapi import FastAPI
from fastapi.responses import JSONResponse

DOCTRINE = {"version": "v11", "counts": "749/14/163", "lambda": "Conjecture 1",
            "locked_proven": 8}

CITATIONS = [
    {"key": "h2o_2023",
     "cite": ("Zhang, Sheng, Zhou et al. (2023) H2O: Heavy-Hitter Oracle for Efficient "
              "Generative Inference of Large Language Models."),
     "url": "https://arxiv.org/abs/2306.14048"},
    {"key": "streamingllm_2023",
     "cite": ("Xiao, Tian, Chen, Han, Lewis (2023) Efficient Streaming Language Models "
              "with Attention Sinks (StreamingLLM)."),
     "url": "https://arxiv.org/abs/2309.17453"},
    {"key": "longformer_2020",
     "cite": "Beltagy, Peters, Cohan (2020) Longformer: The Long-Document Transformer.",
     "url": "https://arxiv.org/abs/2004.05150"},
]


def _rng(seed: int):
    state = (seed * 6364136223846793005 + 1442695040888963407) & ((1 << 64) - 1)

    def nxt() -> float:
        nonlocal state
        state = (state * 6364136223846793005 + 1442695040888963407) & ((1 << 64) - 1)
        return ((state >> 11) & ((1 << 53) - 1)) / float(1 << 53)

    return nxt


def _mass_trace(seed: int, seq_len: int) -> List[float]:
    """Seeded per-token attention mass. A few tokens are HEAVY HITTERS (large mass),
    early tokens carry a mild attention-sink bump, the rest are light — the empirical
    shape H2O / StreamingLLM exploit."""
    rnd = _rng(seed)
    mass = []
    # designate ~8% of positions as heavy hitters
    n_heavy = max(1, int(seq_len * 0.08))
    heavy_idx = set()
    while len(heavy_idx) < n_heavy:
        heavy_idx.add(int(rnd() * seq_len))
    for i in range(seq_len):
        base = 0.15 + 0.85 * rnd() * rnd()          # light background mass
        if i in heavy_idx:
            base += 3.0 + 4.0 * rnd()               # heavy hitter spike
        if i < 4:
            base += 1.5                             # attention-sink bump (first tokens)
        mass.append(base)
    return mass


def _simulate(seed: int, seq_len: int, capacity: int, window: int) -> Dict[str, Any]:
    seq_len = max(16, min(int(seq_len), 4096))
    capacity = max(4, min(int(capacity), seq_len))
    window = max(1, min(int(window), capacity))
    mass = _mass_trace(seed, seq_len)
    total = sum(mass) or 1.0
    idx = list(range(seq_len))

    # FULL oracle keeps everything -> 100% of the mass.
    full_retained = 1.0

    # H2O: keep last `window` (recency) + fill remaining budget with heavy hitters.
    recent = set(idx[seq_len - window:])
    budget_left = max(0, capacity - len(recent))
    rest = [i for i in idx if i not in recent]
    rest_by_mass = sorted(rest, key=lambda i: mass[i], reverse=True)
    heavy_kept = set(rest_by_mass[:budget_left])
    h2o_kept = recent | heavy_kept
    h2o_retained = sum(mass[i] for i in h2o_kept) / total

    # StreamingLLM: keep first `sink` sink tokens + last `window` tokens.
    sink = max(1, min(4, capacity - window)) if capacity > window else 0
    sink_set = set(idx[:sink])
    sliding_kept = sink_set | recent
    sliding_retained = sum(mass[i] for i in sliding_kept) / total

    evicted = seq_len - len(h2o_kept)
    per_token = [{"i": i,
                  "mass": round(mass[i] / (max(mass) or 1.0), 4),
                  "h2o_kept": i in h2o_kept,
                  "sliding_kept": i in sliding_kept}
                 for i in idx]

    return {
        "seq_len": seq_len,
        "capacity": capacity,
        "window": window,
        "sink_tokens": sink,
        "memory_ratio": round(capacity / seq_len, 4),
        "h2o_mass_retained": round(h2o_retained, 4),
        "sliding_mass_retained": round(sliding_retained, 4),
        "full_mass_retained": round(full_retained, 4),
        "h2o_vs_sliding_gain": round(h2o_retained - sliding_retained, 4),
        "evicted_count": evicted,
        "n_heavy_hitters_kept": len(heavy_kept),
        "per_token": per_token,
    }


def _receipt(payload: Dict[str, Any], seed: int) -> Dict[str, Any]:
    blob = repr(sorted(payload.items())).encode("utf-8")
    return {
        "digest_sha256": hashlib.sha256(blob).hexdigest(),
        "seed": seed,
        "signature": "UNSIGNED-LOCAL",
        "note": ("content digest over the MODELED eviction result; deterministic in the "
                 "seed. No DSSE signature claimed locally (UNSIGNED-LOCAL)."),
    }


def register(app: FastAPI, ns: str = "a11oy") -> str:
    @app.get(f"/api/{ns}/v1/kvcache/h2o-evict", include_in_schema=False)
    async def _h2o_evict(seed: int = 42, seq_len: int = 512, capacity: int = 128,
                         window: int = 32) -> JSONResponse:
        t0 = time.time()
        try:
            sim = _simulate(int(seed), int(seq_len), int(capacity), int(window))
        except Exception as e:
            return JSONResponse({"label": "UNAVAILABLE",
                                 "detail": f"eviction sim failed: {type(e).__name__}",
                                 "doctrine": DOCTRINE, "citations": CITATIONS},
                                status_code=200)
        digest_src = {k: v for k, v in sim.items() if k != "per_token"}
        body = {
            "label": "MODELED",
            "surface": "kvcache",
            "title": "KV-Cache · H2O Heavy-Hitter Eviction (MODELED)",
            "method": ("real H2O / StreamingLLM / full-oracle eviction policies run over "
                       "a SEEDED synthetic attention-mass trace. Policies are exact; the "
                       "trace is synthetic. NOT a real KV cache / trained model / GPU."),
            **sim,
            "receipt": _receipt(digest_src, int(seed)),
            "citations": CITATIONS,
            "doctrine": DOCTRINE,
            "honesty": ("MODELED: eviction math is real; the attention-mass trace it runs "
                        "over is synthetic. Not a measured claim about a deployed engine. "
                        "Λ=Conjecture 1; adds nothing to the locked-8; trust never 100%."),
            "elapsed_ms": round((time.time() - t0) * 1000, 2),
        }
        return JSONResponse(body, status_code=200)

    return (f"kv-cache H2O eviction mounted: "
            f"GET /api/{ns}/v1/kvcache/h2o-evict (label MODELED)")


def _selftest() -> None:
    sim = _simulate(42, 512, 128, 32)
    # invariants that any correct policy MUST satisfy
    assert sim["full_mass_retained"] == 1.0, "full oracle must retain all mass"
    assert 0.0 <= sim["h2o_mass_retained"] <= 1.0, "h2o retained out of range"
    assert sim["h2o_mass_retained"] <= sim["full_mass_retained"], "h2o cannot beat full"
    # H2O keeps heavy hitters the pure recency window misses -> should not lose to sliding
    assert sim["h2o_mass_retained"] >= sim["sliding_mass_retained"], "H2O should win vs sliding"
    assert sim["memory_ratio"] < 1.0, "capacity must compress the cache"
    assert len(sim["per_token"]) == sim["seq_len"], "per_token length mismatch"
    # determinism
    assert _simulate(42, 512, 128, 32) == sim, "non-deterministic for fixed seed"
    r = _receipt({k: v for k, v in sim.items() if k != "per_token"}, 42)
    assert r["signature"] == "UNSIGNED-LOCAL", "must not fabricate a signature"
    print("szl_kv_cache: ALL OK (H2O>=sliding<=full, compresses cache, deterministic, "
          "UNSIGNED-LOCAL receipt)")


if __name__ == "__main__":
    _selftest()
