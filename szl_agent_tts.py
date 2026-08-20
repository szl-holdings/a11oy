# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
# Doctrine v11 LOCKED: locked-proven=8 · Λ=Conjecture 1 · SLSA L1 honest / L2 attested / L3 roadmap
# Sign-off: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
"""
szl_agent_tts.py — ADDITIVE a11oy-NATIVE AGENT TEST-TIME-COMPUTE (multi-agent TTC)
backend for the holographic frontier surface static/3d/surfaces/agenttts.js.

WHY THIS EXISTS (distinct from the single-model `testtime` surface)
    The `testtime` surface (szl_testtime_scaling.py) models test-time compute for a
    SINGLE model answering a single question: parallel best-of-N sampling with a PERFECT
    verifier + sequential revision. This surface models test-time compute applied to LLM
    AGENTS — multi-step tool-use / coordinated reasoning — where two honest facts change
    the scaling story:
      1. An agent's single-attempt success COMPOUNDS over a multi-step trajectory: a task
         of depth D with per-step success s succeeds end-to-end only with p = s**D. Depth
         is the agent-specific tax the single-model view does not have.
      2. Selection is done by a REAL, imperfect verifier (not a perfect oracle). Parallel
         breadth (best-of-N agents) only helps to the extent a verifier of precision v can
         actually pick a correct trajectory out of the N candidates. The honest ceiling of
         verifier-guided best-of-N is bounded by v, never 1.0.
    Three levers, modelled exactly and combined:
      * PARALLEL BREADTH  — N independent agents (best-of-N agents).
      * SEQUENTIAL DEPTH  — R revision rounds re-attempting the failed steps.
      * VERIFIER-GUIDED SELECTION — a verifier of precision v picks the winner.

METHOD (agent-TTC scaling — MODELED closed form; NO agent runs, NO LLM calls)
    * p_single = s**D
          single-agent single-attempt end-to-end success; compounding per-step tool-use.
    * PARALLEL BREADTH (best-of-N AGENTS):
          coverage(N)  = 1 − (1 − p_single)**N            (a correct trajectory EXISTS)
          selected(N)  = min(ceiling, coverage(N) · v)     (verifier of precision v picks it)
      coverage is the perfect-oracle upper bound; selected is what an imperfect verifier
      realises. The gap coverage−selected is the honest COST of an imperfect verifier.
    * SEQUENTIAL DEPTH (revision rounds):
          acc(r) = A − (A − p_single)·(1 − γ)**r
      each round closes a fixed fraction γ of the remaining error toward an asymptote A;
      diminishing returns. A = min(0.97, …) — the doctrine trust ceiling; NEVER 1.0.
    * scaling_exponent = least-squares slope of log10(1 − selected(n)) vs log10(n) over the
      breadth curve: a REAL regression quantifying how fast breadth drives agent failure
      down (negative). effective_oom_multiplier = log10(N·(R+1)) — orders of magnitude of
      extra agent invocations vs. one single-shot agent.

HONEST SCALING CURVE — capped at trust 0.97 (NEVER 1.0)
    Both the verifier-guided selected-success and the revision asymptote are clamped to
    _TRUST_CEILING = 0.97. More compute buys more success with diminishing returns, but the
    modelled curve never reaches certainty — an agent stack is never "proven" correct.

LEADERS ADOPTED & CITED (clean-room; NOT claimed as SZL's own; VERIFY real):
    * Snell, Lee, Xu, Kumar (2024) "Scaling LLM Test-Time Compute Optimally can be More
      Effective than Scaling Model Parameters", arXiv:2408.03314.
      https://arxiv.org/abs/2408.03314
    * Brown, Juravsky, Ehrlich, Clark, Le, Ré, Mirhoseini (2024) "Large Language Monkeys:
      Scaling Inference Compute with Repeated Sampling", arXiv:2407.21787.
      https://arxiv.org/abs/2407.21787
    * Hu et al. (2026) "PaCoRe: Learning to Scale Test-Time Compute with Parallel
      Coordinated Reasoning", arXiv:2601.05593 (test-time compute via massive parallel
      coordinated trajectories; ACL 2026). https://arxiv.org/abs/2601.05593

HONESTY SPINE (Doctrine v11)
    * Label "MODELED" — returned VERBATIM, read verbatim by agenttts.js, NEVER upgraded.
      The scaling-law formulas are computed exactly; there is NO agent run, NO LLM call, NO
      benchmark. Success is capped below 1.0 (trust ceiling 0.97) — never a fabricated
      MEASURED number.
    * Λ is ADVISORY-ONLY here (lambda_advisory): the agent-TTC curve informs a restraint
      hint; it is NEVER "proven"/"green". Λ = Conjecture 1; adds NOTHING to the locked-8.

ENDPOINT (mounted BEFORE the SPA catch-all; front-moved to router position 0 by serve.py)
    GET /api/a11oy/v1/agenttts/scaling?seed=&s=&depth=&N=&revisions=&verifier=
        -> renderable 200 JSON compatible with agenttts.js:
           {label:"MODELED", step_success, task_depth, p_single, verifier_precision,
            N_agents, coverage_at_N, selected_at_N, verifier_gap, breadth_curve[],
            revisions, revised_accuracy, revision_curve[], scaling_exponent,
            effective_oom_multiplier, advisory_trust, lambda_advisory, receipt{...},
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

# Doctrine trust ceiling — modelled agent success is NEVER allowed to reach 1.0.
_TRUST_CEILING = 0.97

CITATIONS = [
    {"id": "snell_2024",
     "cite": ("Snell, Lee, Xu, Kumar (2024) Scaling LLM Test-Time Compute Optimally can "
              "be More Effective than Scaling Model Parameters."),
     "url": "https://arxiv.org/abs/2408.03314"},
    {"id": "monkeys_2024",
     "cite": ("Brown, Juravsky, Ehrlich et al. (2024) Large Language Monkeys: Scaling "
              "Inference Compute with Repeated Sampling."),
     "url": "https://arxiv.org/abs/2407.21787"},
    {"id": "pacore_2026",
     "cite": ("Hu et al. (2026) PaCoRe: Learning to Scale Test-Time Compute with Parallel "
              "Coordinated Reasoning (ACL 2026)."),
     "url": "https://arxiv.org/abs/2601.05593"},
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


def _simulate(seed: int, s: float, depth: int, N: int, revisions: int,
              verifier: float) -> Dict[str, Any]:
    # clamp inputs to sane open intervals so p_single>0, coverage<1 (never a perfect agent).
    s = float(s)
    if not math.isfinite(s):
        s = 0.7
    s = min(0.99, max(0.05, s))
    depth = max(1, min(int(depth), 32))
    N = max(1, min(int(N), 4096))
    revisions = max(1, min(int(revisions), 64))
    verifier = float(verifier)
    if not math.isfinite(verifier):
        verifier = 0.85
    verifier = min(0.98, max(0.30, verifier))

    # single-agent single-attempt end-to-end success COMPOUNDS over the trajectory.
    p_single = s ** depth

    # a tiny seeded jitter on the revision error-closing rate γ, so different seeds give
    # visibly distinct (still deterministic) revision curves. Breadth coverage is the exact
    # closed form (no jitter) — it is a hard probability identity.
    gamma = 0.30 + 0.20 * _rng(seed)()   # in [0.30, 0.50): fraction of error closed / round
    ceiling = min(_TRUST_CEILING, p_single + (1.0 - p_single) * 0.9)  # capped asymptote

    # --- PARALLEL BREADTH: best-of-N agents + verifier-guided selection ---
    breadth_curve: List[Dict[str, float]] = []
    for n in _powers_up_to(N):
        coverage = 1.0 - (1.0 - p_single) ** n
        selected = min(_TRUST_CEILING, coverage * verifier)
        breadth_curve.append({"n": n,
                              "coverage": round(coverage, 6),
                              "selected": round(selected, 6)})
    coverage_at_N = 1.0 - (1.0 - p_single) ** N
    selected_at_N = min(_TRUST_CEILING, coverage_at_N * verifier)

    # --- SEQUENTIAL DEPTH: revision rounds with diminishing returns ---
    revision_curve: List[Dict[str, float]] = []
    for r in range(0, revisions + 1):
        acc = ceiling - (ceiling - p_single) * ((1.0 - gamma) ** r)
        revision_curve.append({"r": r, "revised_accuracy": round(acc, 6)})
    revised_accuracy = revision_curve[-1]["revised_accuracy"]

    # --- scaling exponent: LS slope of log10(failure) vs log10(n) over the breadth curve ---
    xs = [math.log10(row["n"]) for row in breadth_curve if row["n"] >= 1]
    ys = [math.log10(max(1e-12, 1.0 - row["selected"])) for row in breadth_curve]
    m = len(xs)
    mean_x = sum(xs) / m
    mean_y = sum(ys) / m
    denom = sum((x - mean_x) ** 2 for x in xs)
    slope = (sum((xs[i] - mean_x) * (ys[i] - mean_y) for i in range(m)) / denom
             if denom > 1e-12 else 0.0)

    # advisory trust = the better of the two levers, honestly capped below certainty.
    advisory_trust = min(_TRUST_CEILING, max(selected_at_N, revised_accuracy))

    return {
        "step_success": round(s, 6),
        "task_depth": depth,
        "p_single": round(p_single, 6),
        "verifier_precision": round(verifier, 6),
        "N_agents": N,
        "coverage_at_N": round(coverage_at_N, 6),
        "selected_at_N": round(selected_at_N, 6),
        "verifier_gap": round(coverage_at_N - selected_at_N, 6),
        "breadth_curve": breadth_curve,
        "revisions": revisions,
        "revised_accuracy": revised_accuracy,
        "revision_curve": revision_curve,
        "error_closing_rate": round(gamma, 6),
        "asymptotic_ceiling": round(ceiling, 6),
        "scaling_exponent": round(slope, 6),
        "effective_oom_multiplier": round(math.log10(N * (revisions + 1)), 6),
        "advisory_trust": round(advisory_trust, 6),
        "trust_ceiling": _TRUST_CEILING,
    }


def _receipt(payload: Dict[str, Any], seed: int) -> Dict[str, Any]:
    digest_src = {k: v for k, v in payload.items()
                  if k not in ("breadth_curve", "revision_curve")}
    blob = repr(sorted(digest_src.items())).encode("utf-8")
    return {
        "digest_sha256": hashlib.sha256(blob).hexdigest(),
        "seed": seed,
        "signature": "UNSIGNED-LOCAL",
        "note": ("content digest over the MODELED agent-TTC result; deterministic in the "
                 "seed. No DSSE signature claimed locally (UNSIGNED-LOCAL)."),
    }


def register(app: FastAPI, ns: str = "a11oy") -> str:
    @app.get(f"/api/{ns}/v1/agenttts/scaling", include_in_schema=False)
    async def _scaling(seed: int = 42, s: float = 0.7, depth: int = 5, N: int = 64,
                       revisions: int = 8, verifier: float = 0.85) -> JSONResponse:
        t0 = time.time()
        try:
            sim = _simulate(int(seed), float(s), int(depth), int(N), int(revisions),
                            float(verifier))
        except Exception as e:
            return JSONResponse({"label": "UNAVAILABLE",
                                 "detail": f"agent-TTC sim failed: {type(e).__name__}",
                                 "doctrine": DOCTRINE, "citations": CITATIONS},
                                status_code=200)
        body = {
            "label": "MODELED",
            "surface": "agenttts",
            "title": "Agent Test-Time Compute · Multi-Agent TTC Scaling (MODELED)",
            "method": ("exact closed-form best-of-N AGENTS with compounding per-step "
                       "tool-use (p=s^depth), verifier-guided selection (selected = "
                       "coverage * verifier_precision) + sequential revision "
                       "(A-(A-p)(1-gamma)^r). NO agent run / LLM call; success capped "
                       "below 1.0 (trust ceiling 0.97)."),
            **sim,
            "receipt": _receipt(sim, int(seed)),
            "citations": CITATIONS,
            "doctrine": DOCTRINE,
            "lambda_advisory": ("ADVISORY-ONLY: the agent-TTC curve informs a restraint "
                                "hint, it is NEVER proven/green. Λ = Conjecture 1."),
            "honesty": ("MODELED: closed-form agent-TTC scaling laws computed exactly; NO "
                        "agent runs, NO LLM calls, NO benchmark. Distinct from single-model "
                        "`testtime`: models compounding multi-step tool-use depth + an "
                        "IMPERFECT verifier, so best-of-N is bounded by verifier precision. "
                        "Success capped below 1.0 (trust ceiling 0.97). Λ advisory-only "
                        "(never proven); adds nothing to the locked-8; trust never 100%."),
            "elapsed_ms": round((time.time() - t0) * 1000, 2),
        }
        return JSONResponse(body, status_code=200)

    return (f"agent test-time-compute scaling mounted: "
            f"GET /api/{ns}/v1/agenttts/scaling (label MODELED)")


def _selftest() -> None:
    sim = _simulate(42, 0.7, 5, 64, 8, 0.85)
    # compounding depth: single-attempt success = s**depth
    assert abs(sim["p_single"] - 0.7 ** 5) < 1e-9, "p_single must equal s**depth"
    # best-of-1 coverage == p_single (a single agent is one attempt)
    assert abs(sim["breadth_curve"][0]["coverage"] - sim["p_single"]) < 1e-6, \
        "coverage@1 must equal p_single"
    # coverage monotone increasing and strictly < 1 (never a perfect agent)
    cov = [row["coverage"] for row in sim["breadth_curve"]]
    assert all(cov[i] <= cov[i + 1] + 1e-12 for i in range(len(cov) - 1)), \
        "coverage not monotone"
    assert 0.0 < sim["coverage_at_N"] < 1.0, "coverage@N must be a probability below 1"
    # verifier-guided selection can NEVER beat the perfect-oracle coverage, and the gap>=0
    sel = [row["selected"] for row in sim["breadth_curve"]]
    assert all(sel[i] <= cov[i] + 1e-9 for i in range(len(sel))), \
        "selected must not exceed oracle coverage"
    assert sim["verifier_gap"] >= -1e-9, "verifier gap (oracle - verifier) must be >= 0"
    # every modelled success honours the trust ceiling (never 1.0)
    assert sim["selected_at_N"] <= _TRUST_CEILING + 1e-9, "selected must honour ceiling"
    assert sim["revised_accuracy"] <= _TRUST_CEILING + 1e-9, "revision must honour ceiling"
    assert sim["advisory_trust"] <= _TRUST_CEILING + 1e-9, "advisory trust <= ceiling"
    assert sim["advisory_trust"] < 1.0, "advisory trust must be strictly below 1.0"
    # sequential revision: monotone up, starts at p_single (r=0)
    rc = [row["revised_accuracy"] for row in sim["revision_curve"]]
    assert all(rc[i] <= rc[i + 1] + 1e-12 for i in range(len(rc) - 1)), \
        "revision not monotone"
    assert abs(rc[0] - sim["p_single"]) < 1e-9, "revision starts at p_single (r=0)"
    # more breadth drives failure down => negative scaling exponent
    assert sim["scaling_exponent"] < 0.0, "failure should fall with more agents"
    # deeper tasks are HARDER: p_single decreases with depth (agent-specific tax)
    deeper = _simulate(42, 0.7, 8, 64, 8, 0.85)
    assert deeper["p_single"] < sim["p_single"], "deeper task must lower single success"
    # determinism
    assert _simulate(42, 0.7, 5, 64, 8, 0.85) == sim, "non-deterministic for fixed seed"
    r = _receipt(sim, 42)
    assert r["signature"] == "UNSIGNED-LOCAL", "must not fabricate a signature"
    print("szl_agent_tts: ALL OK (p=s^depth, coverage@1=p, selected<=coverage, "
          "ceiling<1.0, revision monotone, negative exponent, depth-tax, deterministic, "
          "UNSIGNED-LOCAL)")


if __name__ == "__main__":
    _selftest()
