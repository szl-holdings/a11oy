# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
# Doctrine v11 LOCKED: locked-proven=8 · Λ=Conjecture 1 · SLSA L1 honest / L2 attested / L3 roadmap
# Sign-off: Stephen P. Lutar <stephenlutar2@gmail.com>
"""
szl_latent_attention.py — ADDITIVE a11oy-NATIVE MULTI-HEAD LATENT ATTENTION (MLA)
KV-COMPRESSION backend for the holographic frontier surface static/3d/surfaces/mla.js.

WHY THIS EXISTS
    mla.js previously read ONLY the isolated killinchu Space
    (/api/killinchu/v1/mla/latent-compress) cross-origin, so a11oy had NO self-hosted
    twin: a killinchu flap darkened the surface. This module is the a11oy-native honest
    primary — a REAL, deterministic low-rank down/up-projection of a seeded KV matrix
    (DeepSeek-V2/V3 Multi-Head Latent Attention idea). The compression ARITHMETIC and the
    reconstruction RESIDUAL are computed exactly; the KV matrix + projection weights are
    seeded synthetic data (an UNTRAINED projection), NOT DeepSeek's trained weights.

METHOD (MLA low-rank joint KV compression — MODELED, untrained seeded projection)
    Standard multi-head attention (MHA) caches, per token, a Key and a Value vector for
    EACH of `n_heads` heads (width `d_head`) — the KV cache grows as
    seq_len · 2 · n_heads · d_head and dominates long-context memory. MLA (DeepSeek-V2,
    2024) JOINTLY down-projects the per-token keys/values of all heads into ONE shared
    low-rank LATENT vector of width `d_latent` (only this is cached), then up-projects it
    back to full K/V on demand. The cache then grows as only seq_len · d_latent.

MATH (all REAL computations over the seeded matrices; NOT trained weights)
    * d_model = n_heads · d_head  (full concatenated KV width per token).
    * X ∈ R^{seq_len × d_model}  = seeded per-token KV rows (synthetic activations).
    * W_down ∈ R^{d_model × d_latent}, W_up ∈ R^{d_latent × d_model}  = seeded projections
      (scaled by 1/sqrt(d) for a stable operator norm; NOT trained).
    * latent = X · W_down                (the cached compressed representation)
    * X_hat  = latent · W_up             (the up-projected reconstruction)
    * reconstruction_error = mean over tokens of || X_row − X_hat_row ||_2  (real L2).
    * mha_cache_size = seq_len · 2 · n_heads · d_head    (elements cached by MHA).
    * mla_cache_size = seq_len · d_latent                (elements cached by MLA).
    * compression_ratio = mha_cache_size / mla_cache_size  (how much smaller the cache is).
    (The residual is computed over a representative capped sample of token rows so the
     endpoint stays fast and pure-stdlib; it is an honest estimate of the per-token L2.)

LEADERS ADOPTED & CITED (clean-room; NOT claimed as SZL's own; VERIFY real):
    * DeepSeek-AI (2024) "DeepSeek-V2: A Strong, Economical, and Efficient Mixture-of-
      Experts Language Model" — introduces Multi-Head Latent Attention (low-rank joint
      KV compression), arXiv:2405.04434.  https://arxiv.org/abs/2405.04434
    * DeepSeek-AI (2024) "DeepSeek-V3 Technical Report" — adopts & validates MLA at
      larger scale, arXiv:2412.19437.  https://arxiv.org/abs/2412.19437

HONESTY SPINE (Doctrine v11)
    * Label "MODELED" — returned VERBATIM, read verbatim by mla.js, NEVER upgraded.
      The compression arithmetic + reconstruction residual are REAL linear algebra; the
      KV matrix and projection weights are SEEDED synthetic data (untrained), NOT
      DeepSeek's trained weights / a real model / GPU. NEVER claimed-as DeepSeek-V2/V3.
      In a real MLA the projection is TRAINED so the residual is far smaller; the honest
      untrained residual here is deliberately larger and labelled as such.
    * Advisory only. Λ = Conjecture 1; adds NOTHING to the locked-8; trust never 100%.

ENDPOINT (mounted BEFORE the SPA catch-all; front-moved to router position 0 by serve.py)
    GET /api/a11oy/v1/mla/latent-compress?seed=&seq_len=&n_heads=&d_head=&d_latent=
        -> renderable 200 JSON compatible with mla.js:
           {label:"MODELED", seq_len, n_heads, d_head, d_latent, mha_cache_size,
            mla_cache_size, compression_ratio, reconstruction_error, receipt{...},
            citations[]}
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
    {"id": "deepseek_v2_2024",
     "cite": ("DeepSeek-AI (2024) DeepSeek-V2 — introduces Multi-Head Latent Attention "
              "(low-rank joint KV compression)."),
     "url": "https://arxiv.org/abs/2405.04434"},
    {"id": "deepseek_v3_2024",
     "cite": ("DeepSeek-AI (2024) DeepSeek-V3 Technical Report — adopts & validates MLA "
              "at larger scale."),
     "url": "https://arxiv.org/abs/2412.19437"},
]

# Cap on the number of token rows over which the reconstruction residual is computed,
# so the endpoint stays fast and pure-stdlib (no numpy dependency). The residual is a
# representative per-token estimate; cache-size arithmetic uses the FULL seq_len.
_ROW_SAMPLE_CAP = 24


def _rng(seed: int):
    state = (seed * 6364136223846793005 + 1442695040888963407) & ((1 << 64) - 1)

    def nxt() -> float:
        nonlocal state
        state = (state * 6364136223846793005 + 1442695040888963407) & ((1 << 64) - 1)
        return ((state >> 11) & ((1 << 53) - 1)) / float(1 << 53)

    return nxt


def _gauss(nxt) -> float:
    """Box-Muller standard-normal draw from the uniform LCG (deterministic)."""
    u1 = max(1e-12, nxt())
    u2 = nxt()
    return math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)


def _simulate(seed: int, seq_len: int, n_heads: int, d_head: int,
              d_latent: int) -> Dict[str, Any]:
    seq_len = max(8, min(int(seq_len), 512))
    n_heads = max(1, min(int(n_heads), 64))
    d_head = max(4, min(int(d_head), 256))
    d_model = n_heads * d_head
    # a compressed latent must actually compress: keep d_latent strictly below d_model.
    d_latent = max(4, min(int(d_latent), d_model - 1))

    nxt = _rng(seed)

    # seeded projection weights (untrained), scaled for a stable operator norm.
    down_scale = 1.0 / math.sqrt(d_model)
    up_scale = 1.0 / math.sqrt(d_latent)
    # W_down: d_model x d_latent ; W_up: d_latent x d_model
    w_down: List[List[float]] = [[_gauss(nxt) * down_scale for _ in range(d_latent)]
                                 for _ in range(d_model)]
    w_up: List[List[float]] = [[_gauss(nxt) * up_scale for _ in range(d_model)]
                               for _ in range(d_latent)]

    # reconstruction residual over a representative capped sample of token rows.
    n_rows = min(seq_len, _ROW_SAMPLE_CAP)
    total_err = 0.0
    for _r in range(n_rows):
        x = [_gauss(nxt) for _ in range(d_model)]
        # latent = x · W_down   (length d_latent)
        latent = [0.0] * d_latent
        for j in range(d_model):
            xj = x[j]
            if xj == 0.0:
                continue
            wrow = w_down[j]
            for k in range(d_latent):
                latent[k] += xj * wrow[k]
        # x_hat = latent · W_up   (length d_model)
        x_hat = [0.0] * d_model
        for k in range(d_latent):
            lk = latent[k]
            if lk == 0.0:
                continue
            wrow = w_up[k]
            for j in range(d_model):
                x_hat[j] += lk * wrow[j]
        # per-row L2 residual
        s = 0.0
        for j in range(d_model):
            d = x[j] - x_hat[j]
            s += d * d
        total_err += math.sqrt(s)
    recon_err = total_err / n_rows if n_rows else 0.0

    mha_cache = seq_len * 2 * n_heads * d_head
    mla_cache = seq_len * d_latent
    ratio = mha_cache / mla_cache if mla_cache else 0.0

    return {
        "seq_len": seq_len,
        "n_heads": n_heads,
        "d_head": d_head,
        "d_model": d_model,
        "d_latent": d_latent,
        "mha_cache_size": mha_cache,
        "mla_cache_size": mla_cache,
        "compression_ratio": round(ratio, 6),
        "reconstruction_error": round(recon_err, 6),
        "residual_rows_sampled": n_rows,
    }


def _receipt(payload: Dict[str, Any], seed: int) -> Dict[str, Any]:
    blob = repr(sorted(payload.items())).encode("utf-8")
    return {
        "digest_sha256": hashlib.sha256(blob).hexdigest(),
        "seed": seed,
        "signature": "UNSIGNED-LOCAL",
        "note": ("content digest over the MODELED compression result; deterministic in "
                 "the seed. No DSSE signature claimed locally (UNSIGNED-LOCAL)."),
    }


def register(app: FastAPI, ns: str = "a11oy") -> str:
    @app.get(f"/api/{ns}/v1/mla/latent-compress", include_in_schema=False)
    async def _latent_compress(seed: int = 42, seq_len: int = 128, n_heads: int = 8,
                               d_head: int = 64, d_latent: int = 128) -> JSONResponse:
        t0 = time.time()
        try:
            sim = _simulate(int(seed), int(seq_len), int(n_heads), int(d_head),
                            int(d_latent))
        except Exception as e:
            return JSONResponse({"label": "UNAVAILABLE",
                                 "detail": f"latent compress failed: {type(e).__name__}",
                                 "doctrine": DOCTRINE, "citations": CITATIONS},
                                status_code=200)
        body = {
            "label": "MODELED",
            "surface": "mla",
            "title": "Multi-Head Latent Attention · KV Compression (MODELED)",
            "method": ("real low-rank down/up-projection of a SEEDED KV matrix with "
                       "SEEDED untrained weights. Compression arithmetic + reconstruction "
                       "L2 residual are exact; the matrix + weights are synthetic. NOT "
                       "DeepSeek's trained weights / a real model / GPU."),
            **sim,
            "receipt": _receipt(sim, int(seed)),
            "citations": CITATIONS,
            "doctrine": DOCTRINE,
            "honesty": ("MODELED: the compression math + reconstruction residual are real; "
                        "the KV matrix and projection weights are synthetic and UNTRAINED "
                        "(so the residual is deliberately larger than a trained MLA). Not "
                        "a measured claim about DeepSeek; NEVER claimed-as DeepSeek-V2/V3. "
                        "Λ=Conjecture 1; adds nothing to the locked-8; trust never 100%."),
            "elapsed_ms": round((time.time() - t0) * 1000, 2),
        }
        return JSONResponse(body, status_code=200)

    return (f"multi-head latent attention compress mounted: "
            f"GET /api/{ns}/v1/mla/latent-compress (label MODELED)")


def _selftest() -> None:
    sim = _simulate(42, 128, 8, 64, 128)
    # invariants any correct low-rank KV compression MUST satisfy
    assert sim["d_model"] == sim["n_heads"] * sim["d_head"], "d_model = heads*d_head"
    assert sim["d_latent"] < sim["d_model"], "latent must be strictly lower-rank"
    assert sim["mla_cache_size"] < sim["mha_cache_size"], "MLA cache must be smaller"
    assert sim["compression_ratio"] > 1.0, "compression must actually compress"
    assert sim["reconstruction_error"] >= 0.0, "L2 residual cannot be negative"
    # untrained random projection loses information => strictly-positive residual
    assert sim["reconstruction_error"] > 0.0, "untrained projection must lose some info"
    # determinism
    assert _simulate(42, 128, 8, 64, 128) == sim, "non-deterministic for fixed seed"
    # a wider latent compresses less (monotonicity of the ratio)
    wide = _simulate(42, 128, 8, 64, 256)
    assert wide["compression_ratio"] < sim["compression_ratio"], \
        "wider latent must give a smaller compression ratio"
    r = _receipt(sim, 42)
    assert r["signature"] == "UNSIGNED-LOCAL", "must not fabricate a signature"
    print("szl_latent_attention: ALL OK (lower-rank latent, cache compressed, ratio>1, "
          "positive residual, wider-latent<ratio, deterministic, UNSIGNED-LOCAL)")


if __name__ == "__main__":
    _selftest()
