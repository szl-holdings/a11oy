# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
# Doctrine v11 LOCKED: locked-proven=8 · Λ=Conjecture 1 · SLSA L1 honest / L2 attested / L3 roadmap
# Sign-off: Stephen P. Lutar <stephenlutar2@gmail.com>
"""
szl_testtime_scaling.py — ADDITIVE a11oy-NATIVE TEST-TIME-COMPUTE / REASONING-SCALING
backend for the holographic frontier surface static/3d/surfaces/testtime.js.

WHY THIS EXISTS
    testtime.js previously read ONLY the isolated killinchu Space
    (/api/killinchu/v1/testtime/scaling) cross-origin, so a11oy had NO self-hosted twin:
    a killinchu flap darkened the surface. This module is the a11oy-native honest primary
    — a REAL, deterministic closed-form evaluation of the two canonical test-time-compute
    scaling laws (parallel best-of-N coverage + sequential revision with diminishing
    returns). The formulas are computed exactly; there is NO LLM call / live model eval.

METHOD (test-time-compute scaling laws — MODELED closed form; no model calls)
    The THIRD scaling axis (alongside pretrain- and post-train-scaling): trade extra
    INFERENCE-time compute for accuracy, in two regimes —
    1. PARALLEL (best-of-N / repeated sampling, "Large Language Monkeys", Brown et al.
       2024): with per-sample success probability p and a perfect verifier, drawing N
       independent samples and keeping any correct one gives coverage
           pass@N = 1 − (1 − p)^N
       which rises monotonically toward 1 as N grows.
    2. SEQUENTIAL (revision / long chain-of-thought, DeepSeek-R1 2025; optimal test-time
       compute, Snell et al. 2024): each revision step closes a fixed FRACTION γ of the
       remaining error toward an asymptotic ceiling A, giving diminishing returns
           acc(k) = A − (A − p)·(1 − γ)^k
       so accuracy climbs fast then flattens.

MATH (all REAL closed-form computations; deterministic; NO LLM eval)
    * base_accuracy = p  (input; clamped to a sane open interval).
    * pass_at_N_curve = [{n, pass_at_n = 1 − (1 − p)^n} for n in 1,2,4,...,≤N].
    * pass_at_N = 1 − (1 − p)^N.
    * revised_accuracy_curve = [{k, revised_accuracy = A − (A − p)(1 − γ)^k} for k in
      0..steps], with ceiling A = min(0.97, ...) — the doctrine trust ceiling is honoured,
      accuracy is NEVER modelled at 1.0.
    * scaling_exponent = least-squares slope of log10(error) vs log10(n) over the
      pass@N curve (error = 1 − pass@n): a REAL regression on the modelled data,
      quantifying how fast parallel sampling drives error down.
    * effective_oom_multiplier = log10(N): the orders of magnitude of extra inference
      compute spent relative to a single sample.

LEADERS ADOPTED & CITED (clean-room; NOT claimed as SZL's own; VERIFY real):
    * DeepSeek-AI (2025) "DeepSeek-R1: Incentivizing Reasoning Capability in LLMs via
      Reinforcement Learning", arXiv:2501.12948.  https://arxiv.org/abs/2501.12948
    * Snell, Lee, Xu, Kumar (2024) "Scaling LLM Test-Time Compute Optimally can be More
      Effective than Scaling Model Parameters", arXiv:2408.03314.
      https://arxiv.org/abs/2408.03314
    * Brown, Juravsky, Ehrlich, Clark, Le, Ré, Mirhoseini (2024) "Large Language Monkeys:
      Scaling Inference Compute with Repeated Sampling", arXiv:2407.21787.
      https://arxiv.org/abs/2407.21787

HONESTY SPINE (Doctrine v11)
    * Label "MODELED" — returned VERBATIM, read verbatim by testtime.js, NEVER upgraded.
      The scaling-law formulas are computed exactly; there is NO LLM call, NO live model
      eval, NO benchmark run. Accuracy is capped BELOW 1.0 (trust ceiling 0.97) — never a
      fabricated MEASURED benchmark number.
    * Advisory only. Λ = Conjecture 1; adds NOTHING to the locked-8; trust never 100%.

ENDPOINT (mounted BEFORE the SPA catch-all; front-moved to router position 0 by serve.py)
    GET /api/a11oy/v1/testtime/scaling?seed=&p=&N=&steps=
        -> renderable 200 JSON compatible with testtime.js:
           {label:"MODELED", base_accuracy, N_samples, pass_at_N, pass_at_N_curve[],
            sequential_steps, revised_accuracy, revised_accuracy_curve[],
            scaling_exponent, effective_oom_multiplier, receipt{...}, citations[]}
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

# Doctrine trust ceiling — modelled accuracy is NEVER allowed to reach 1.0.
_TRUST_CEILING = 0.97

CITATIONS = [
    {"id": "deepseek_r1_2025",
     "cite": ("DeepSeek-AI (2025) DeepSeek-R1: Incentivizing Reasoning Capability in "
              "LLMs via Reinforcement Learning."),
     "url": "https://arxiv.org/abs/2501.12948"},
    {"id": "snell_2024",
     "cite": ("Snell, Lee, Xu, Kumar (2024) Scaling LLM Test-Time Compute Optimally can "
              "be More Effective than Scaling Model Parameters."),
     "url": "https://arxiv.org/abs/2408.03314"},
    {"id": "monkeys_2024",
     "cite": ("Brown, Juravsky, Ehrlich et al. (2024) Large Language Monkeys: Scaling "
              "Inference Compute with Repeated Sampling."),
     "url": "https://arxiv.org/abs/2407.21787"},
]


def _rng(seed: int):
    state = (seed * 6364136223846793005 + 1442695040888963407) & ((1 << 64) - 1)

    def nxt() -> float:
        nonlocal state
        state = (state * 6364136223846793005 + 1442695040888963407) & ((1 << 64) - 1)
        return ((state >> 11) & ((1 << 53) - 1)) / float(1 << 53)

    return nxt


def _powers_up_to(n_max: int) -> List[int]:
    """1, 2, 4, 8, ... up to and including n_max (n_max appended if not a power of 2)."""
    out: List[int] = []
    n = 1
    while n < n_max:
        out.append(n)
        n *= 2
    out.append(n_max)
    return out


def _simulate(seed: int, p: float, N: int, steps: int) -> Dict[str, Any]:
    # clamp p to an open interval so error>0 and pass<1 (honest: never a perfect model).
    p = float(p)
    if not math.isfinite(p):
        p = 0.2
    p = min(0.95, max(0.01, p))
    N = max(1, min(int(N), 4096))
    steps = max(1, min(int(steps), 64))

    # a tiny seeded jitter on the sequential error-closing rate γ, so different seeds
    # give visibly distinct (still deterministic) revision curves. Parallel coverage is
    # the exact closed form (no jitter) — it is a hard probability identity.
    gamma = 0.35 + 0.20 * _rng(seed)()   # in [0.35, 0.55): fraction of error closed per step
    ceiling = min(_TRUST_CEILING, p + (1.0 - p) * 0.9)  # asymptote, capped by trust ceiling

    # --- parallel best-of-N coverage: pass@n = 1 - (1-p)^n ---
    pass_curve: List[Dict[str, float]] = []
    for n in _powers_up_to(N):
        pass_curve.append({"n": n, "pass_at_n": round(1.0 - (1.0 - p) ** n, 6)})
    pass_at_N = round(1.0 - (1.0 - p) ** N, 6)

    # --- sequential revision: acc(k) = A - (A-p)(1-gamma)^k ---
    rev_curve: List[Dict[str, float]] = []
    for k in range(0, steps + 1):
        acc = ceiling - (ceiling - p) * ((1.0 - gamma) ** k)
        rev_curve.append({"k": k, "revised_accuracy": round(acc, 6)})
    revised_accuracy = rev_curve[-1]["revised_accuracy"]

    # --- scaling exponent: LS slope of log10(error) vs log10(n) over the pass curve ---
    xs = [math.log10(r["n"]) for r in pass_curve if r["n"] >= 1]
    ys = [math.log10(max(1e-12, 1.0 - r["pass_at_n"])) for r in pass_curve]
    m = len(xs)
    mean_x = sum(xs) / m
    mean_y = sum(ys) / m
    denom = sum((x - mean_x) ** 2 for x in xs)
    slope = (sum((xs[i] - mean_x) * (ys[i] - mean_y) for i in range(m)) / denom
             if denom > 1e-12 else 0.0)

    return {
        "base_accuracy": round(p, 6),
        "N_samples": N,
        "pass_at_N": pass_at_N,
        "pass_at_N_curve": pass_curve,
        "sequential_steps": steps,
        "revised_accuracy": revised_accuracy,
        "revised_accuracy_curve": rev_curve,
        "error_closing_rate": round(gamma, 6),
        "asymptotic_ceiling": round(ceiling, 6),
        "scaling_exponent": round(slope, 6),
        "effective_oom_multiplier": round(math.log10(N), 6),
    }


def _receipt(payload: Dict[str, Any], seed: int) -> Dict[str, Any]:
    digest_src = {k: v for k, v in payload.items()
                  if k not in ("pass_at_N_curve", "revised_accuracy_curve")}
    blob = repr(sorted(digest_src.items())).encode("utf-8")
    return {
        "digest_sha256": hashlib.sha256(blob).hexdigest(),
        "seed": seed,
        "signature": "UNSIGNED-LOCAL",
        "note": ("content digest over the MODELED scaling result; deterministic in the "
                 "seed. No DSSE signature claimed locally (UNSIGNED-LOCAL)."),
    }


def register(app: FastAPI, ns: str = "a11oy") -> str:
    @app.get(f"/api/{ns}/v1/testtime/scaling", include_in_schema=False)
    async def _scaling(seed: int = 42, p: float = 0.2, N: int = 64,
                       steps: int = 8) -> JSONResponse:
        t0 = time.time()
        try:
            sim = _simulate(int(seed), float(p), int(N), int(steps))
        except Exception as e:
            return JSONResponse({"label": "UNAVAILABLE",
                                 "detail": f"scaling sim failed: {type(e).__name__}",
                                 "doctrine": DOCTRINE, "citations": CITATIONS},
                                status_code=200)
        body = {
            "label": "MODELED",
            "surface": "testtime",
            "title": "Test-Time Compute · Reasoning-Scaling Laws (MODELED)",
            "method": ("exact closed-form best-of-N coverage (1-(1-p)^N) + sequential "
                       "revision with diminishing returns (A-(A-p)(1-gamma)^k). NO LLM "
                       "call / live model eval; accuracy capped below 1.0 (trust ceiling "
                       "0.97)."),
            **sim,
            "receipt": _receipt(sim, int(seed)),
            "citations": CITATIONS,
            "doctrine": DOCTRINE,
            "honesty": ("MODELED: closed-form scaling laws computed exactly; NO model "
                        "calls, NO benchmark run. Accuracy is capped below 1.0 (trust "
                        "ceiling 0.97) — never a fabricated MEASURED benchmark number. "
                        "Λ=Conjecture 1; adds nothing to the locked-8; trust never 100%."),
            "elapsed_ms": round((time.time() - t0) * 1000, 2),
        }
        return JSONResponse(body, status_code=200)

    return (f"test-time-compute scaling mounted: "
            f"GET /api/{ns}/v1/testtime/scaling (label MODELED)")


def _selftest() -> None:
    sim = _simulate(42, 0.2, 64, 8)
    # invariants any correct test-time-compute scaling MUST satisfy
    assert abs(sim["base_accuracy"] - 0.2) < 1e-9, "base accuracy = input p"
    # pass@1 == p (best-of-1 is a single sample)
    assert abs(sim["pass_at_N_curve"][0]["pass_at_n"] - 0.2) < 1e-6, "pass@1 must equal p"
    # pass@N monotonically increasing and strictly < 1 (never a perfect model)
    pc = [r["pass_at_n"] for r in sim["pass_at_N_curve"]]
    assert all(pc[i] <= pc[i + 1] + 1e-12 for i in range(len(pc) - 1)), "pass@N not monotone"
    assert 0.0 < sim["pass_at_N"] < 1.0, "pass@N must be a probability strictly below 1"
    # sequential revision: monotone up, capped by the trust ceiling
    rc = [r["revised_accuracy"] for r in sim["revised_accuracy_curve"]]
    assert all(rc[i] <= rc[i + 1] + 1e-12 for i in range(len(rc) - 1)), "revision not monotone"
    assert sim["revised_accuracy"] <= _TRUST_CEILING + 1e-9, "must honour trust ceiling"
    assert rc[0] <= sim["base_accuracy"] + 1e-9, "revision starts at base accuracy (k=0)"
    # more parallel samples drive error down => negative scaling exponent
    assert sim["scaling_exponent"] < 0.0, "error should fall with more samples"
    # determinism
    assert _simulate(42, 0.2, 64, 8) == sim, "non-deterministic for fixed seed"
    r = _receipt(sim, 42)
    assert r["signature"] == "UNSIGNED-LOCAL", "must not fabricate a signature"
    print("szl_testtime_scaling: ALL OK (pass@1=p, monotone pass@N<1, revision<=ceiling, "
          "negative scaling exponent, deterministic, UNSIGNED-LOCAL)")


if __name__ == "__main__":
    _selftest()
