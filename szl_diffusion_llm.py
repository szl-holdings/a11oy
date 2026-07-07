# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
# Doctrine v11 LOCKED: locked-proven=8 · Λ=Conjecture 1 · SLSA L1 honest / L2 attested / L3 roadmap
# Sign-off: Stephen P. Lutar <stephenlutar2@gmail.com>
"""
szl_diffusion_llm.py — ADDITIVE a11oy-NATIVE DIFFUSION-LLM PARALLEL-DECODING backend
for the holographic frontier surface static/3d/surfaces/dllm.js.

WHY THIS EXISTS
    dllm.js previously read ONLY the isolated killinchu Space
    (/api/killinchu/v1/dllm/denoise) cross-origin, so a11oy had NO self-hosted twin: a
    killinchu flap darkened the surface. This module is the a11oy-native honest primary —
    a REAL, deterministic re-derivation of the masked-diffusion reverse-process DECODING
    SCHEDULE (LLaDA / Mercury / block-diffusion style), run over a seeded per-position
    confidence field. The SCHEDULE math is exact; the confidence field is synthetic.

METHOD (masked-diffusion parallel decoding — MODELED on a seeded confidence field)
    Autoregressive LLMs decode ONE token per step (length steps for a length-token
    answer). A masked diffusion LLM instead starts from a FULLY-MASKED sequence and, over
    a fixed number of `steps` reverse-diffusion rounds, UNMASKS a batch of positions IN
    PARALLEL each round. LLaDA (Nie et al. 2025) uses a linear masking schedule: the number
    of tokens that remain masked falls linearly from `length` at t=1 to 0 at t=steps, so
    each round commits a batch. Which positions unmask each round follows a
    HIGHEST-CONFIDENCE-FIRST rule (the low-confidence-remasking / confidence-aware schedule
    used by LLaDA & MaskGIT), NOT left-to-right order.

MATH (all REAL computations over the seeded confidence field; NOT a trained model)
    * conf[i]  = seeded per-position model confidence in [0,1], i in [0, length).
    * revealed(t) = round(length * t / steps)  — LLaDA linear reverse schedule; the
      cumulative count of committed (unmasked) positions after round t. revealed(0)=0,
      revealed(steps)=length (exact, by construction).
    * tokens_per_round[t] = revealed(t) - revealed(t-1)   (the parallel batch size at
      round t; sums to `length`).
    * unmask order = positions sorted by conf DESC (confidence-first). cumulative_unmasked
      is the running committed count; the batch committed at round t is the next
      tokens_per_round[t] positions in that order.
    * confidence_trajectory[t] = MEAN conf of the batch committed at round t. Because the
      schedule commits the most-confident positions first, this trajectory is
      (weakly) DECREASING — an honest signal that later rounds fill in the harder,
      lower-confidence positions.
    * parallelism_factor = length / steps  — average tokens decided per round; contrast the
      autoregressive baseline of exactly 1.0 token/step.
    * final_sequence[i] = seeded synthetic token id (vocab-bounded) so the surface can show
      a concrete decoded row. NOT text from a trained model.

LEADERS ADOPTED & CITED (clean-room; NOT claimed as SZL's own; VERIFY real):
    * Nie, Zhu, Dong, Wang, Chen, Zhang, Li, Zhang (2025) "Large Language Diffusion
      Models" (LLaDA), arXiv:2502.09992.  https://arxiv.org/abs/2502.09992
      Reference impl: https://github.com/ML-GSAI/LLaDA
    * Inception Labs (2025) "Mercury: Ultra-Fast Language Models Based on Diffusion",
      arXiv:2506.17298.  https://arxiv.org/abs/2506.17298
    * Austin, Johnson, Ho, Tarlow, van den Berg (2021) "Structured Denoising Diffusion
      Models in Discrete State-Spaces" (D3PM), arXiv:2107.03006.
      https://arxiv.org/abs/2107.03006

HONESTY SPINE (Doctrine v11)
    * Label "MODELED" — returned VERBATIM, read verbatim by dllm.js, NEVER upgraded.
      The DECODING SCHEDULE (linear reverse process + confidence-first unmask order) is
      computed exactly; the CONFIDENCE FIELD it runs over is SEEDED synthetic data, NOT a
      trained diffusion LLM / real logits / GPU. NEVER claimed-as Mercury or LLaDA.
    * Advisory only. Λ = Conjecture 1; adds NOTHING to the locked-8; trust never 100%.

ENDPOINT (mounted BEFORE the SPA catch-all; front-moved to router position 0 by serve.py)
    GET /api/a11oy/v1/dllm/denoise?seed=&steps=&length=
        -> renderable 200 JSON compatible with dllm.js:
           {label:"MODELED", length, steps, parallelism_factor, tokens_per_round[],
            cumulative_unmasked[], confidence_trajectory[], final_sequence[],
            receipt{...}, citations[]}
"""
from __future__ import annotations

import hashlib
import time
from typing import Any, Dict, List

from fastapi import FastAPI
from fastapi.responses import JSONResponse

DOCTRINE = {"version": "v11", "counts": "749/14/163", "lambda": "Conjecture 1",
            "locked_proven": 8}

CITATIONS = [
    {"id": "llada_2025",
     "cite": ("Nie, Zhu, Dong et al. (2025) Large Language Diffusion Models (LLaDA)."),
     "url": "https://arxiv.org/abs/2502.09992"},
    {"id": "mercury_2025",
     "cite": ("Inception Labs (2025) Mercury: Ultra-Fast Language Models Based on "
              "Diffusion."),
     "url": "https://arxiv.org/abs/2506.17298"},
    {"id": "d3pm_2021",
     "cite": ("Austin, Johnson, Ho, Tarlow, van den Berg (2021) Structured Denoising "
              "Diffusion Models in Discrete State-Spaces (D3PM)."),
     "url": "https://arxiv.org/abs/2107.03006"},
]

_VOCAB = 32000  # synthetic token-id ceiling (display only; NOT a real tokenizer)


def _rng(seed: int):
    state = (seed * 6364136223846793005 + 1442695040888963407) & ((1 << 64) - 1)

    def nxt() -> float:
        nonlocal state
        state = (state * 6364136223846793005 + 1442695040888963407) & ((1 << 64) - 1)
        return ((state >> 11) & ((1 << 53) - 1)) / float(1 << 53)

    return nxt


def _simulate(seed: int, steps: int, length: int) -> Dict[str, Any]:
    length = max(4, min(int(length), 512))
    steps = max(1, min(int(steps), length))
    rnd = _rng(seed)

    # seeded per-position confidence in [0,1] and a synthetic decoded token id
    conf = [round(rnd(), 6) for _ in range(length)]
    final_seq = [int(rnd() * _VOCAB) for _ in range(length)]

    # LLaDA linear reverse schedule: cumulative revealed count after each round.
    cumulative = [round(length * t / steps) for t in range(1, steps + 1)]
    cumulative[-1] = length  # exact endpoint (guard rounding)
    tokens_per_round: List[int] = []
    prev = 0
    for c in cumulative:
        tokens_per_round.append(c - prev)
        prev = c

    # confidence-first unmask order (highest-confidence positions commit first).
    order = sorted(range(length), key=lambda i: conf[i], reverse=True)

    # per-round batch mean confidence (weakly decreasing — harder positions come later).
    confidence_trajectory: List[float] = []
    cursor = 0
    for n in tokens_per_round:
        batch = order[cursor:cursor + n]
        cursor += n
        mean_c = sum(conf[i] for i in batch) / n if n else 0.0
        confidence_trajectory.append(round(mean_c, 6))

    return {
        "length": length,
        "steps": steps,
        "parallelism_factor": round(length / steps, 6),
        "tokens_per_round": tokens_per_round,
        "cumulative_unmasked": cumulative,
        "confidence_trajectory": confidence_trajectory,
        "final_sequence": final_seq,
    }


def _receipt(payload: Dict[str, Any], seed: int) -> Dict[str, Any]:
    blob = repr(sorted(payload.items())).encode("utf-8")
    return {
        "digest_sha256": hashlib.sha256(blob).hexdigest(),
        "seed": seed,
        "signature": "UNSIGNED-LOCAL",
        "note": ("content digest over the MODELED decoding schedule; deterministic in the "
                 "seed. No DSSE signature claimed locally (UNSIGNED-LOCAL)."),
    }


def register(app: FastAPI, ns: str = "a11oy") -> str:
    @app.get(f"/api/{ns}/v1/dllm/denoise", include_in_schema=False)
    async def _denoise(seed: int = 42, steps: int = 8, length: int = 64) -> JSONResponse:
        t0 = time.time()
        try:
            sim = _simulate(int(seed), int(steps), int(length))
        except Exception as e:
            return JSONResponse({"label": "UNAVAILABLE",
                                 "detail": f"denoise sim failed: {type(e).__name__}",
                                 "doctrine": DOCTRINE, "citations": CITATIONS},
                                status_code=200)
        digest_src = {k: v for k, v in sim.items()
                      if k not in ("final_sequence", "confidence_trajectory")}
        body = {
            "label": "MODELED",
            "surface": "dllm",
            "title": "Diffusion-LLM · Masked Parallel Denoising (MODELED)",
            "method": ("real LLaDA-style linear reverse schedule + confidence-first "
                       "parallel-unmask order over a SEEDED confidence field. Schedule is "
                       "exact; the confidence field is synthetic. NOT a trained diffusion "
                       "LLM / real logits / GPU."),
            **sim,
            "autoregressive_baseline": 1.0,
            "receipt": _receipt(digest_src, int(seed)),
            "citations": CITATIONS,
            "doctrine": DOCTRINE,
            "honesty": ("MODELED: the parallel-decoding schedule is real; the per-position "
                        "confidence field it runs over is synthetic. Not a measured claim "
                        "about a deployed diffusion model; NEVER claimed-as Mercury/LLaDA. "
                        "Λ=Conjecture 1; adds nothing to the locked-8; trust never 100%."),
            "elapsed_ms": round((time.time() - t0) * 1000, 2),
        }
        return JSONResponse(body, status_code=200)

    return (f"diffusion-LLM parallel denoise mounted: "
            f"GET /api/{ns}/v1/dllm/denoise (label MODELED)")


def _selftest() -> None:
    sim = _simulate(42, 8, 64)
    # invariants any correct masked-diffusion schedule MUST satisfy
    assert sum(sim["tokens_per_round"]) == sim["length"], "batches must sum to length"
    assert sim["cumulative_unmasked"][-1] == sim["length"], "all positions must unmask"
    assert len(sim["tokens_per_round"]) == sim["steps"], "one batch per round"
    assert all(b >= 0 for b in sim["tokens_per_round"]), "no negative batch"
    # cumulative is non-decreasing
    cu = sim["cumulative_unmasked"]
    assert all(cu[i] <= cu[i + 1] for i in range(len(cu) - 1)), "cumulative not monotone"
    # parallelism factor is length/steps and beats the autoregressive 1.0 baseline here
    assert abs(sim["parallelism_factor"] - sim["length"] / sim["steps"]) < 1e-9
    assert sim["parallelism_factor"] > 1.0, "parallel decode should beat 1 tok/step"
    # confidence-first schedule => weakly decreasing per-round mean confidence
    ct = sim["confidence_trajectory"]
    assert all(ct[i] + 1e-9 >= ct[i + 1] for i in range(len(ct) - 1)), \
        "confidence-first order must give non-increasing batch confidence"
    assert len(sim["final_sequence"]) == sim["length"], "final_sequence length mismatch"
    # determinism
    assert _simulate(42, 8, 64) == sim, "non-deterministic for fixed seed"
    r = _receipt({k: v for k, v in sim.items()
                  if k not in ("final_sequence", "confidence_trajectory")}, 42)
    assert r["signature"] == "UNSIGNED-LOCAL", "must not fabricate a signature"
    print("szl_diffusion_llm: ALL OK (batches sum to length, monotone cumulative, "
          "parallel>1, confidence-first non-increasing, deterministic, UNSIGNED-LOCAL)")


if __name__ == "__main__":
    _selftest()
