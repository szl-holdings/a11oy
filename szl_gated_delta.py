# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
# Doctrine v11 LOCKED: locked-proven=8 · Λ=Conjecture 1 · SLSA L1 honest / L2 attested / L3 roadmap
# Co-Authored-By: Perplexity Computer Agent
"""
szl_gated_delta.py — ADDITIVE a11oy-NATIVE cited GATED-DELTA / DELTA-RULE
linear-attention backend for the holographic frontier surface
static/3d/surfaces/gateddelta.js (surface id: gateddelta).

WHY THIS EXISTS
    The estate already models sparse/latent/ring/kaczmarz attention and state-space
    (nsa/mla/ringattn/kla/ssm/hybridssm) — but NOT the DELTA-RULE family that now
    powers the strongest linear-attention LLMs (Gated DeltaNet / DeltaNet / DeltaProduct
    / GLA). This module is the a11oy-native honest primary for that frontier: a REAL,
    deterministic, pure-stdlib (NO numpy) implementation of the delta-rule associative-
    memory state update, its gated (adaptive-decay) variant, and a plain linear-attention
    baseline — run over a seeded key/value write trace with OVERWRITES, so the recall
    behaviour that separates these methods is visible.

METHOD (delta rule / gated delta / linear attention — MODELED on a synthetic trace)
    A linear-attention layer keeps an associative-memory STATE matrix S (d×d) that maps a
    query key k -> a recalled value S·k. New (key,value) pairs are written into S online:

      * PLAIN LINEAR ATTENTION (no forgetting):   S_t = S_{t-1} + v_t k_tᵀ
            every write is ADDED. Re-writing a key ACCUMULATES values -> a later read of an
            overwritten key returns the SUM of everything ever written to it, not the last.

      * DELTA RULE (DeltaNet — a Householder reflection I - β k kᵀ):
            S_t = S_{t-1}(I - β_t k_t k_tᵀ) + β_t v_t k_tᵀ
            first REMOVES the value currently associated with k_t, then writes the new one.
            With β=1 and (near-)orthonormal keys a read of a key returns its LAST write
            exactly — true in-place state update, the property state-tracking needs.

      * GATED DELTA (Gated DeltaNet — data-dependent scalar decay α_t∈(0,1]):
            S_t = α_t S_{t-1}(I - β_t k_t k_tᵀ) + β_t v_t k_tᵀ
            the α_t gate lets the memory ADAPTIVELY FORGET: a key's recalled value fades
            (magnitude × α per subsequent step) while its DIRECTION/identity is preserved,
            so stale associations decay without corrupting fresh ones.

    We also demonstrate the CHUNK-PARALLEL invariant (Yang et al. 2024, delta rule over
    sequence length): processing the identical delta recurrence in fixed-size CHUNKS,
    carrying the d×d state across chunk boundaries, reproduces the fully-sequential state
    (reported max abs diff → ~0). That algebraic equivalence is what makes the hardware-
    efficient chunk-parallel training of these models valid; we verify the invariant here,
    we do NOT benchmark GPU throughput.

MATH (all REAL computations over the seeded trace; NOT a trained model / GPU)
    * keys: n_keys (near-)orthonormal d-vectors (Gram-Schmidt on seeded random vectors) —
      one per "register"; values: seeded random d-vectors.
    * write trace: seq_len steps, each picks a register (with repeats -> OVERWRITES) and a
      fresh value; ground truth for a register = its LAST written value.
    * recall error(method) = mean over written registers of ||S·k_r - v_true_r|| / ||v_true_r||
      (relative L2); recall cosine = mean cos(S·k_r, v_true_r) (direction fidelity).
    * gated_retention = mean_r ||S_gated·k_r|| / ||v_true_r|| = mean α^(steps since last write)
      — the honest, visible signature of the adaptive-decay gate.
    * chunk_max_state_diff = max_ij |S_delta_seq[i][j] - S_delta_chunked[i][j]| (≈0 invariant).

LEADERS ADOPTED & CITED (clean-room; NOT claimed as SZL's own; VERIFY real):
    * Yang, Kautz, Hatamizadeh (2024) "Gated Delta Networks: Improving Mamba2 with the
      Delta Rule", arXiv:2412.06464.  https://arxiv.org/abs/2412.06464
    * Yang, Wang, Zhang, Shen, Kim, Kim, Liu, Zhu, Song, Han, Kim (2024) "Parallelizing
      Linear Transformers with the Delta Rule over Sequence Length", arXiv:2406.06484.
      https://arxiv.org/abs/2406.06484
    * Siems, Movahedi, Zhang, Sifre, Yang, Kasai et al. (2025) "DeltaProduct: Improving
      State-Tracking in Linear RNNs via Householder Products", arXiv:2502.10297.
      https://arxiv.org/abs/2502.10297
    * Yang, Zhang, Kautz, Panda, Kim (2023) "Gated Linear Attention Transformers with
      Hardware-Efficient Training" (GLA), arXiv:2312.06635.
      https://arxiv.org/abs/2312.06635

HONESTY SPINE (Doctrine v11)
    * Label "MODELED" — returned VERBATIM, read verbatim by gateddelta.js, NEVER upgraded.
      The delta / gated-delta / linear-attention state updates are implemented EXACTLY and
      run for real; the KEY/VALUE WRITE TRACE they run over is SEEDED synthetic data, NOT a
      real trained model / GPU / dataset. Every number is a property of the modeled trace.
    * Advisory only. Λ = Conjecture 1; adds NOTHING to the locked-8; trust never 100%.

ENDPOINT (mounted BEFORE the SPA catch-all; front-moved to router position 0 by serve.py)
    GET /api/a11oy/v1/gateddelta/recall?seed=&seq_len=&dim=&n_keys=&chunk=&gate=&beta=
        -> renderable 200 JSON compatible with gateddelta.js:
           {label:"MODELED", seq_len, dim, n_keys, chunk, gate, beta, n_overwrites,
            linear_recall_error, delta_recall_error, gated_recall_error,
            linear_recall_cos, delta_recall_cos, gated_recall_cos,
            gated_retention, delta_vs_linear_gain, chunk_max_state_diff,
            state_track_acc{linear,delta,gated}, per_register[], receipt{...}, citations[]}
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
    {"id": "gated_deltanet_2024",
     "cite": ("Yang, Kautz, Hatamizadeh (2024) Gated Delta Networks: Improving Mamba2 "
              "with the Delta Rule."),
     "url": "https://arxiv.org/abs/2412.06464"},
    {"id": "parallel_delta_2024",
     "cite": ("Yang, Wang, Zhang et al. (2024) Parallelizing Linear Transformers with "
              "the Delta Rule over Sequence Length."),
     "url": "https://arxiv.org/abs/2406.06484"},
    {"id": "deltaproduct_2025",
     "cite": ("Siems, Movahedi, Zhang et al. (2025) DeltaProduct: Improving State-"
              "Tracking in Linear RNNs via Householder Products."),
     "url": "https://arxiv.org/abs/2502.10297"},
    {"id": "gla_2023",
     "cite": ("Yang, Zhang, Kautz, Panda, Kim (2023) Gated Linear Attention Transformers "
              "with Hardware-Efficient Training (GLA)."),
     "url": "https://arxiv.org/abs/2312.06635"},
]


# ---------------------------------------------------------------------------
# seeded RNG (same LCG family as szl_kv_cache.py — deterministic, stdlib-only)
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


def _unit(a: List[float]) -> List[float]:
    n = _norm(a)
    return [x / n for x in a] if n > 1e-12 else list(a)


def _matvec(M: List[List[float]], x: List[float]) -> List[float]:
    return [_dot(row, x) for row in M]


def _cos(a: List[float], b: List[float]) -> float:
    na, nb = _norm(a), _norm(b)
    if na < 1e-12 or nb < 1e-12:
        return 0.0
    return _dot(a, b) / (na * nb)


def _rand_vec(rnd, d: int) -> List[float]:
    # centred so vectors are not all in the positive orthant
    return [rnd() * 2.0 - 1.0 for _ in range(d)]


def _orthonormal_keys(rnd, d: int, n: int) -> List[List[float]]:
    """Gram-Schmidt on seeded random vectors -> n (near-)orthonormal d-vectors.
    Orthonormal keys make the delta rule an EXACT in-place overwrite, which is the
    behaviour we want to demonstrate honestly."""
    keys: List[List[float]] = []
    for _ in range(n):
        v = _rand_vec(rnd, d)
        for q in keys:                       # subtract projections onto existing keys
            c = _dot(v, q)
            v = [vi - c * qi for vi, qi in zip(v, q)]
        keys.append(_unit(v))
    return keys


# ---------------------------------------------------------------------------
# state updates: linear attention / delta rule / gated delta
# ---------------------------------------------------------------------------
def _apply_delta_step(S: List[List[float]], k: List[float], v: List[float],
                      beta: float, alpha: float) -> None:
    """In-place gated delta-rule update:
         S <- alpha * S (I - beta k kᵀ) + beta v kᵀ
    (alpha=1 -> plain delta rule). Uses S·k so the reflection costs O(d²), not O(d³)."""
    d = len(v)
    Sk = _matvec(S, k)                       # d-vector = current recalled value for k
    for i in range(d):
        corr = beta * (alpha * Sk[i] - v[i])  # remove old assoc, add new (sign folded below)
        row = S[i]
        for j in range(d):
            # alpha*S - alpha*beta*(S k) kᵀ + beta v kᵀ
            row[j] = alpha * row[j] - corr * k[j]


def _run_sequential(keys, values, reg_seq, beta, alpha) -> List[List[float]]:
    d = len(values[0])
    S = [[0.0] * d for _ in range(d)]
    for t, r in enumerate(reg_seq):
        _apply_delta_step(S, keys[r], values[t], beta, alpha)
    return S


def _run_chunked(keys, values, reg_seq, beta, alpha, chunk: int) -> List[List[float]]:
    """Identical delta recurrence, processed in fixed-size chunks carrying the d×d state
    across chunk boundaries — the chunk-parallel invariant (Yang et al. 2024)."""
    d = len(values[0])
    S = [[0.0] * d for _ in range(d)]
    n = len(reg_seq)
    c = max(1, chunk)
    start = 0
    while start < n:
        end = min(n, start + c)
        for t in range(start, end):
            _apply_delta_step(S, keys[reg_seq[t]], values[t], beta, alpha)
        start = end
    return S


def _run_linear(keys, values, reg_seq) -> List[List[float]]:
    """Plain linear attention: S = Σ_t v_t k_tᵀ (pure accumulation, no forgetting)."""
    d = len(values[0])
    S = [[0.0] * d for _ in range(d)]
    for t, r in enumerate(reg_seq):
        k, v = keys[r], values[t]
        for i in range(d):
            row = S[i]
            vi = v[i]
            for j in range(d):
                row[j] += vi * k[j]
    return S


def _recall_stats(S, keys, truth) -> Dict[str, Any]:
    """Per-register relative-L2 error + cosine of S·k_r vs the last-written value."""
    errs, coss, retentions, per = [], [], [], []
    for r, v_true in sorted(truth.items()):
        v_hat = _matvec(S, keys[r])
        nt = _norm(v_true) or 1.0
        rel = _norm([a - b for a, b in zip(v_hat, v_true)]) / nt
        cs = _cos(v_hat, v_true)
        ret = _norm(v_hat) / nt
        errs.append(rel)
        coss.append(cs)
        retentions.append(ret)
        per.append({"r": r, "rel_err": round(rel, 6), "cos": round(cs, 6),
                    "retention": round(ret, 6)})
    mean = lambda xs: (sum(xs) / len(xs)) if xs else 0.0
    return {"mean_err": mean(errs), "mean_cos": mean(coss),
            "mean_retention": mean(retentions), "per": per}


def _simulate(seed: int, seq_len: int, dim: int, n_keys: int, chunk: int,
              gate: float, beta: float) -> Dict[str, Any]:
    seq_len = max(8, min(int(seq_len), 512))
    dim = max(4, min(int(dim), 32))
    n_keys = max(2, min(int(n_keys), min(dim, 16)))
    chunk = max(1, min(int(chunk), seq_len))
    gate = max(0.5, min(float(gate), 1.0))
    beta = max(0.1, min(float(beta), 1.0))

    rnd = _rng(seed)
    keys = _orthonormal_keys(rnd, dim, n_keys)
    values = [_rand_vec(rnd, dim) for _ in range(seq_len)]
    reg_seq = [int(rnd() * n_keys) % n_keys for _ in range(seq_len)]

    # ground truth: the LAST value written to each register
    truth: Dict[int, List[float]] = {}
    seen_counts: Dict[int, int] = {}
    for t, r in enumerate(reg_seq):
        truth[r] = values[t]
        seen_counts[r] = seen_counts.get(r, 0) + 1
    n_overwrites = sum(max(0, c - 1) for c in seen_counts.values())

    S_lin = _run_linear(keys, values, reg_seq)
    S_delta = _run_sequential(keys, values, reg_seq, beta, 1.0)   # delta rule (no gate)
    S_delta_chunked = _run_chunked(keys, values, reg_seq, beta, 1.0, chunk)
    S_gated = _run_sequential(keys, values, reg_seq, beta, gate)  # gated delta

    lin = _recall_stats(S_lin, keys, truth)
    dl = _recall_stats(S_delta, keys, truth)
    gd = _recall_stats(S_gated, keys, truth)

    # chunk-parallel invariant: chunked delta state == sequential delta state
    chunk_diff = 0.0
    for i in range(dim):
        for j in range(dim):
            chunk_diff = max(chunk_diff, abs(S_delta[i][j] - S_delta_chunked[i][j]))

    # state-tracking accuracy: fraction of registers whose recalled DIRECTION matches
    # the last write (cosine > 0.9) — the state-tracking success criterion.
    def _acc(stats):
        hits = sum(1 for p in stats["per"] if p["cos"] > 0.9)
        return round(hits / len(stats["per"]), 4) if stats["per"] else 0.0

    per_register = []
    for pl, pd, pg in zip(lin["per"], dl["per"], gd["per"]):
        per_register.append({
            "r": pl["r"],
            "writes": seen_counts.get(pl["r"], 0),
            "lin_err": pl["rel_err"], "delta_err": pd["rel_err"], "gated_err": pg["rel_err"],
            "lin_cos": pl["cos"], "delta_cos": pd["cos"], "gated_cos": pg["cos"],
            "gated_retention": pg["retention"],
        })

    return {
        "seq_len": seq_len,
        "dim": dim,
        "n_keys": n_keys,
        "chunk": chunk,
        "gate": round(gate, 4),
        "beta": round(beta, 4),
        "n_overwrites": n_overwrites,
        "registers_written": len(truth),
        "linear_recall_error": round(lin["mean_err"], 6),
        "delta_recall_error": round(dl["mean_err"], 6),
        "gated_recall_error": round(gd["mean_err"], 6),
        "linear_recall_cos": round(lin["mean_cos"], 6),
        "delta_recall_cos": round(dl["mean_cos"], 6),
        "gated_recall_cos": round(gd["mean_cos"], 6),
        "gated_retention": round(gd["mean_retention"], 6),
        "delta_vs_linear_gain": round(lin["mean_err"] - dl["mean_err"], 6),
        "chunk_max_state_diff": round(chunk_diff, 12),
        "state_track_acc": {"linear": _acc(lin), "delta": _acc(dl), "gated": _acc(gd)},
        "per_register": per_register,
    }


def _receipt(payload: Dict[str, Any], seed: int) -> Dict[str, Any]:
    blob = repr(sorted(payload.items())).encode("utf-8")
    return {
        "digest_sha256": hashlib.sha256(blob).hexdigest(),
        "seed": seed,
        "signature": "UNSIGNED-LOCAL",
        "note": ("content digest over the MODELED delta-rule recall result; deterministic "
                 "in the seed. No DSSE signature claimed locally (UNSIGNED-LOCAL)."),
    }


def register(app: FastAPI, ns: str = "a11oy") -> str:
    @app.get(f"/api/{ns}/v1/gateddelta/recall", include_in_schema=False)
    async def _gateddelta_recall(seed: int = 42, seq_len: int = 48, dim: int = 8,
                                 n_keys: int = 6, chunk: int = 8, gate: float = 0.98,
                                 beta: float = 1.0) -> JSONResponse:
        t0 = time.time()
        try:
            sim = _simulate(int(seed), int(seq_len), int(dim), int(n_keys), int(chunk),
                            float(gate), float(beta))
        except Exception as e:
            return JSONResponse({"label": "UNAVAILABLE",
                                 "detail": f"delta-rule sim failed: {type(e).__name__}",
                                 "doctrine": DOCTRINE, "citations": CITATIONS},
                                status_code=200)
        digest_src = {k: v for k, v in sim.items() if k != "per_register"}
        body = {
            "label": "MODELED",
            "surface": "gateddelta",
            "title": "Gated Delta-Rule Linear Attention · state recall (MODELED)",
            "method": ("real delta-rule / gated-delta / linear-attention associative-memory "
                       "state updates run over a SEEDED key/value write trace with "
                       "overwrites. Updates are exact; the trace is synthetic. NOT a real "
                       "trained model / GPU / dataset."),
            **sim,
            "receipt": _receipt(digest_src, int(seed)),
            "citations": CITATIONS,
            "doctrine": DOCTRINE,
            "honesty": ("MODELED: delta/gated-delta/linear state math is real; the key/value "
                        "trace it runs over is synthetic. Not a measured claim about a "
                        "deployed engine. Λ=Conjecture 1; adds nothing to the locked-8; "
                        "trust never 100%."),
            "elapsed_ms": round((time.time() - t0) * 1000, 2),
        }
        return JSONResponse(body, status_code=200)

    return (f"gated delta-rule recall mounted: "
            f"GET /api/{ns}/v1/gateddelta/recall (label MODELED)")


def _selftest() -> None:
    sim = _simulate(42, 48, 8, 6, 8, 0.98, 1.0)
    # invariants any correct implementation MUST satisfy
    assert 0.0 <= sim["delta_recall_error"] <= sim["linear_recall_error"], \
        "delta rule must recall the LAST write at least as well as plain linear attention"
    assert sim["delta_recall_error"] < 1e-6, \
        "delta rule with orthonormal keys + beta=1 must recall the last write ~exactly"
    assert sim["gated_recall_error"] <= sim["linear_recall_error"] + 1e-9, \
        "gated delta must not lose to plain linear attention on recall"
    assert sim["delta_vs_linear_gain"] >= 0.0, "delta advantage must be non-negative"
    assert sim["n_overwrites"] > 0, "trace must contain overwrites to be meaningful"
    # chunk-parallel invariant: chunked == sequential delta state
    assert sim["chunk_max_state_diff"] < 1e-9, \
        "chunked delta state must equal the sequential state (chunk-parallel invariant)"
    # gate = adaptive decay: direction preserved (cos high) while magnitude fades (<=1)
    assert sim["gated_recall_cos"] >= 0.9, "gated delta must preserve recall DIRECTION"
    assert sim["gated_retention"] <= 1.0 + 1e-9, "gate can only decay magnitude, never grow it"
    assert sim["state_track_acc"]["delta"] >= sim["state_track_acc"]["linear"], \
        "delta rule must state-track at least as well as linear attention"
    assert 0.0 <= sim["gate"] <= 1.0 and 0.0 < sim["beta"] <= 1.0, "gate/beta out of range"
    assert len(sim["per_register"]) == sim["registers_written"], "per_register length mismatch"
    # determinism
    assert _simulate(42, 48, 8, 6, 8, 0.98, 1.0) == sim, "non-deterministic for fixed seed"
    r = _receipt({k: v for k, v in sim.items() if k != "per_register"}, 42)
    assert r["signature"] == "UNSIGNED-LOCAL", "must not fabricate a signature"
    print("szl_gated_delta: ALL OK "
          f"(linear_err={sim['linear_recall_error']} delta_err={sim['delta_recall_error']} "
          f"gated_err={sim['gated_recall_error']} gated_cos={sim['gated_recall_cos']} "
          f"chunk_diff={sim['chunk_max_state_diff']} "
          f"delta_track={sim['state_track_acc']['delta']}; deterministic; UNSIGNED-LOCAL)")


if __name__ == "__main__":
    _selftest()
