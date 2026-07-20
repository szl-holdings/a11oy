# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED: locked-proven=8 · Λ=Conjecture 1 · SLSA L1 honest / L2 attested / L3 roadmap
# Co-Authored-By: Perplexity Computer Agent
"""
szl_gpu_quant.py — ADDITIVE Sovereign GPU-Quant Engine for a11oy's finance vertical.

The VRAM-resident, three-layer quant pipeline validated in GPU_QUANT_RESEARCH.md
(after Nathaniel Brodetsky's hybrid pipeline; math cited to primary sources):

  Layer 1 — PCA RISK  (Ledoit-Wolf shrinkage + Marchenko-Pastur eigenvalue filter)
      Σ̂_LW = (1−ρ)Σ̂ + ρ·μI,  μ = tr(Σ̂)/N           (Ledoit & Wolf 2003)
      λ± = σ²(1 ± 1/√q)²,  q = T/N                      (Marchenko-Pastur / RMT)
      Discard eigenvalues ≤ λ⁺ as noise; rebuild cleaned covariance.

  Layer 2 — TDA FRACTURE  (correlation-distance + persistent homology Betti β0/β1)
      d_ij = √(2(1−ρ_ij))                                (econophysics metric)
      f_t = |Δβ0| + |Δβ1|   (fracture score)             (Brodetsky)
      z_t = (f_t − μ_f)/σ_f,  |z_t| > 2.5 ⇒ anomaly      (Gidea & Katz 2017)

  Layer 3 — HJB-KELLY SIZING  (log-utility / Merton; TDA-augmented variance)
      σ²_eff = σ²_PCA·(1+γ|f_t|)·(1+κ·1_{z>2.5})         (Brodetsky augmentation)
      w* = μ̄ / σ²_eff                                    (Merton/Kelly, log-utility)

HONESTY SPINE (doctrine v11 — the non-negotiable part of this build):
  * EVERY output is a SAMPLE_SIGNAL: synthetic / illustrative returns, NOT a live feed,
    NO_BACKTEST_VALIDATED. We have NOT run a backtest. We do NOT claim live-trading.
  * The compute path here is the HONEST CPU REFERENCE (pure-Python linear algebra +
    a pure-Python Vietoris-Rips β0/β1 over a thresholded distance graph). The GPU path
    (cuML LedoitWolf + cuPy eigh + giotto-tda / Ripser++) is labeled ROADMAP. GPU
    reachability and dependency imports are readiness only; MEASURED requires a distinct
    accelerated path plus device/kernel/timing execution evidence.
  * Every receipt is wrapped by szl_dsse.sign_payload (verified ECDSA when the cosign key
    is present in the runtime; explicitly UNSIGNED otherwise — never a fabricated
    signature). The label SAMPLE_SIGNAL | NOT_LIVE | NO_BACKTEST_VALIDATED is embedded
    in the content-addressed payload and its signature state is reported separately.
  * No fabricated metric. No live-trading claim. No backtest claim. cuML speedups are
    cited to NVIDIA/STAC docs, never asserted as SZL-measured.

Routes (NEW; never collide):
  GET  /api/{ns}/v1/quant/pca        — Layer 1 PCA-Risk (LW + MP) on a SAMPLE universe
  GET  /api/{ns}/v1/quant/tda        — Layer 2 TDA fracture score f_t, z_t, Betti β0/β1
  GET  /api/{ns}/v1/quant/kelly      — Layer 3 HJB-Kelly weights w* with σ²_eff
  GET  /api/{ns}/v1/quant/pipeline   — full 3-layer pass + ONE DSSE-bearing SAMPLE receipt
  GET  /api/{ns}/v1/quant/tiers      — 2-GPU serve tier panel (TP=2 / role-split / NIM cloud)
  GET  /api/{ns}/v1/quant/verify-claims — NVIDIA datasheet vs SZL-MEASURED (honest, empty/ROADMAP)
  GET  /quant                        — unified mobile-first "Quant Engine" tab (0 CDN)

Pure stdlib. Defensive: a compute failure NEVER raises out of a handler.
"""
from __future__ import annotations

import base64 as _base64
import hashlib as _hashlib
import json as _json
import math as _math
import os as _os
from pathlib import Path as _Path
import random as _random
import time as _time
from datetime import datetime, timezone

# --- signed receipts: the SINGLE source of truth (never fabricate a signature) ----
try:
    from szl_dsse import sign_payload as _sign_payload  # REAL ECDSA when key present
    from szl_dsse import verify_envelope as _verify_envelope
    _SIGN_AVAILABLE = True
except Exception:  # pragma: no cover — defensive; honest unsigned fallback below
    _SIGN_AVAILABLE = False

    def _sign_payload(payload_obj, payload_type="application/vnd.szl.quant.receipt+json"):  # type: ignore
        body = _json.dumps(payload_obj, sort_keys=True, separators=(",", ":")).encode()
        return {
            "payloadType": payload_type,
            "payload": __import__("base64").b64encode(body).decode("ascii"),
            "_dsse": "DSSEv1",
            "_pae_sha256": _hashlib.sha256(body).hexdigest(),
            "_signed_at": datetime.now(timezone.utc).isoformat(),
            "signatures": [],
            "signed": False,
            "honesty": ("UNSIGNED — szl_dsse not importable in this runtime; "
                        "no signature fabricated."),
        }

    def _verify_envelope(_envelope):  # type: ignore
        return {"verified": False, "reason": "szl_dsse verifier is unavailable"}

_QUANT_PAYLOAD_TYPE = "application/vnd.szl.quant.receipt+json"

# --- optional acceleration probes (honest GPU-path labels) ------------------------
def _gpu_libs_present() -> dict:
    """Probe for the GPU quant stack WITHOUT importing heavy modules at request time
    on the hot path more than once. Honest: absent libs => ROADMAP path, never faked."""
    present = {}
    for name in ("cupy", "cuml", "cudf", "gtda", "ripser_plusplus"):
        try:
            __import__(name)
            present[name] = True
        except Exception:
            present[name] = False
    present["numpy"] = _np_present()
    return present


def _np_present() -> bool:
    try:
        __import__("numpy")
        return True
    except Exception:
        return False


def _sovereign_state() -> dict:
    """LIVE sovereign-inference posture (delegated to the orchestrator — the authority).
    Honest default not-sovereign on any failure. This state is reachability evidence,
    never proof that the finance quant pipeline executed on a GPU."""
    try:
        import a11oy_code_orchestrator as _orch  # type: ignore
        st = _orch._sovereign_inference_state()
        if isinstance(st, dict):
            return st
    except Exception:
        pass
    return {"inference": "unknown", "mode": "unknown", "backend": "unknown",
            "sovereign": False, "base_url": None,
            "honest_note": "orchestrator sovereign-state unavailable in-process; honest default not-sovereign."}


def _gpu_reachable(state: dict | None = None) -> bool:
    st = state if state is not None else _sovereign_state()
    return bool(st.get("sovereign") is True and st.get("inference") == "self-hosted-gpu")


def _compute_backend() -> dict:
    """Which compute path actually ran, honestly labeled.

    The numerical layer implementations in this module are currently the pure-Python
    reference path.  Dependency availability is *readiness*, not execution evidence:
    merely finding a sovereign GPU and importing cuML/cuPy must never relabel CPU
    results as GPU-MEASURED.  When an accelerated implementation is added it must
    supply execution evidence (device, kernel/implementation id, and timing receipt)
    before this contract can emit a MEASURED GPU label.
    """
    libs = _gpu_libs_present()
    reachable = _gpu_reachable()
    acceleration_dependencies_ready = bool(
        reachable and libs.get("cuml") and libs.get("cupy")
    )
    return {
        "backend": "CPU pure-Python reference",
        "compute_path": "CPU_REFERENCE",
        "label": "SAMPLE",
        "gpu_reachable": reachable,
        "gpu_libs_present": libs,
        "acceleration_dependencies_ready": acceleration_dependencies_ready,
        "acceleration_implementation_wired": False,
        "execution_evidence": None,
        "honest_note": (
            "Pure-Python reference implementation executed: Jacobi eigensolver plus "
            "pure-Python Vietoris-Rips β0/β1. GPU reachability and importable RAPIDS "
            "dependencies indicate readiness only. The accelerated cuML/cuPy/Ripser++ "
            "implementation is ROADMAP and cannot be labeled MEASURED until a distinct "
            "device-executed path emits execution evidence."),
    }


DOCTRINE = {
    "version": "v11",
    "locked_proven": ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"],
    "locked_count": 8,
    "corpus": "749/14/163",
    "kernel_commit": "c7c0ba17",
    "lambda": "Conjecture 1 (advisory floor; uniqueness machine-checked FALSE unconditionally; NOT a theorem)",
    "slsa": "L1 honest / L2 attested (.att emitted, not independently verified) / L3 roadmap",
}

# The label EVERY quant output must carry. Non-negotiable doctrine string.
SAMPLE_LABEL = "SAMPLE_SIGNAL | NOT_LIVE | NO_BACKTEST_VALIDATED"

# Primary-source citations for the math (GPU_QUANT_RESEARCH.md).
CITATIONS = {
    "ledoit_wolf": "Ledoit & Wolf (2003) Honey, I Shrunk the Sample Covariance Matrix — http://www.ledoit.net/honey.pdf",
    "marchenko_pastur": "Laloux, Cizeau, Bouchaud, Potters (2000) — https://math.nyu.edu/~avellane/LalouxPCA.pdf ; Bun, Bouchaud, Potters arXiv:1610.08104",
    "tda_crashes": "Gidea & Katz (2017) TDA of Financial Time Series: Landscapes of Crashes — arXiv:1703.04385 (Physica A 2018)",
    "tda_crypto": "Gidea, Goldsmith, Katz, Roldan, Shmalo (2018) TDA of Cryptocurrencies — arXiv:1809.00695",
    "merton_kelly": "Merton (1969/71) continuous-time portfolio; Kelly criterion (log-utility): w* = (μ−r)/σ²",
    "rapids_cuml": "RAPIDS cuML benchmarks — https://docs.rapids.ai/api/cuml/stable/cuml-accel/benchmarks/",
    "ripserpp": "Zhang, Xiao, Wang — GPU Vietoris-Rips persistence (Ripser++) arXiv:2003.07989",
    "giotto_tda": "giotto-tda — https://github.com/giotto-ai/giotto-tda",
    "brodetsky": "N. Brodetsky — 'Pandas and NumPy aren't broken...' (LinkedIn thought-leadership; NOT peer-reviewed)",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# =====================================================================================
# Pure-stdlib linear algebra (honest CPU fallback). No numpy required.
# =====================================================================================
def _zeros(n, m=None):
    if m is None:
        return [0.0] * n
    return [[0.0] * m for _ in range(n)]


def _matmul(A, B):
    n, k, m = len(A), len(B), len(B[0])
    out = _zeros(n, m)
    for i in range(n):
        Ai = A[i]
        Oi = out[i]
        for t in range(k):
            a = Ai[t]
            if a == 0.0:
                continue
            Bt = B[t]
            for j in range(m):
                Oi[j] += a * Bt[j]
    return out


def _transpose(A):
    return [list(col) for col in zip(*A)]


def _identity(n):
    I = _zeros(n, n)
    for i in range(n):
        I[i][i] = 1.0
    return I


def _sample_covariance(returns):
    """returns: list of T rows × N cols (already de-meaned per-column inside).
    Returns the N×N sample covariance with the standard 1/(T-1) normalisation."""
    T = len(returns)
    N = len(returns[0])
    means = [sum(returns[t][j] for t in range(T)) / T for j in range(N)]
    cov = _zeros(N, N)
    denom = max(1, T - 1)
    for i in range(N):
        for j in range(i, N):
            s = 0.0
            for t in range(T):
                s += (returns[t][i] - means[i]) * (returns[t][j] - means[j])
            v = s / denom
            cov[i][j] = v
            cov[j][i] = v
    return cov, means


def _jacobi_eigen(A, max_sweeps=100, tol=1e-10):
    """Classic Jacobi eigenvalue algorithm for a symmetric matrix A (pure Python).
    Returns (eigenvalues list, eigenvectors as columns of V). Robust for small N."""
    n = len(A)
    a = [row[:] for row in A]
    V = _identity(n)
    for _ in range(max_sweeps):
        off = 0.0
        p, q = 0, 1
        for i in range(n):
            for j in range(i + 1, n):
                if abs(a[i][j]) > off:
                    off = abs(a[i][j])
                    p, q = i, j
        if off < tol:
            break
        app, aqq, apq = a[p][p], a[q][q], a[p][q]
        if abs(apq) < 1e-300:
            continue
        phi = 0.5 * _math.atan2(2 * apq, (aqq - app)) if (aqq - app) != 0 else _math.pi / 4
        c = _math.cos(phi)
        s = _math.sin(phi)
        for k in range(n):
            akp = a[k][p]
            akq = a[k][q]
            a[k][p] = c * akp - s * akq
            a[k][q] = s * akp + c * akq
        for k in range(n):
            apk = a[p][k]
            aqk = a[q][k]
            a[p][k] = c * apk - s * aqk
            a[q][k] = s * apk + c * aqk
        for k in range(n):
            vkp = V[k][p]
            vkq = V[k][q]
            V[k][p] = c * vkp - s * vkq
            V[k][q] = s * vkp + c * vkq
    eig = [a[i][i] for i in range(n)]
    return eig, V


def _solve_spd(A, b):
    """Solve A x = b for symmetric positive-definite A via Gaussian elimination
    with partial pivoting (pure Python). Returns x."""
    n = len(A)
    M = [A[i][:] + [b[i]] for i in range(n)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(M[r][col]))
        if abs(M[piv][col]) < 1e-15:
            M[piv][col] += 1e-12  # tiny ridge to avoid singular blow-up (honest reg.)
        M[col], M[piv] = M[piv], M[col]
        pivval = M[col][col]
        for r in range(n):
            if r == col:
                continue
            factor = M[r][col] / pivval
            for k in range(col, n + 1):
                M[r][k] -= factor * M[col][k]
    return [M[i][n] / M[i][i] for i in range(n)]


# =====================================================================================
# SAMPLE universe generator (deterministic, honestly synthetic).
# =====================================================================================
def _sample_returns(n_assets=12, n_obs=120, n_factors=2, seed=7, stress=False):
    """Deterministic SAMPLE returns: a low-rank factor structure + idiosyncratic noise.
    `stress=True` injects a correlated regime-break in the back half (drives TDA fracture).
    This is ILLUSTRATIVE synthetic data — NOT a live feed and NOT a historical series."""
    rng = _random.Random(seed)
    betas = [[rng.uniform(0.3, 1.2) for _ in range(n_factors)] for _ in range(n_assets)]
    returns = []
    for t in range(n_obs):
        factors = [rng.gauss(0, 0.012) for _ in range(n_factors)]
        if stress and t > n_obs // 2:
            # regime break: a single dominant shock raises cross-asset correlation
            shock = rng.gauss(0, 0.05)
            factors = [f + shock for f in factors]
        row = []
        for i in range(n_assets):
            sysret = sum(betas[i][k] * factors[k] for k in range(n_factors))
            idio = rng.gauss(0, 0.008)
            row.append(sysret + idio)
        returns.append(row)
    return returns


# =====================================================================================
# LAYER 1 — PCA RISK: Ledoit-Wolf shrinkage + Marchenko-Pastur eigenvalue filter.
# =====================================================================================
def _ledoit_wolf(returns):
    """Ledoit-Wolf shrinkage covariance (analytic optimal intensity ρ).
    Σ̂_LW = (1−ρ)Σ̂ + ρ·μI,  μ = tr(Σ̂)/N. Closed-form ρ minimising Frobenius loss
    (Ledoit & Wolf 2003). Pure Python — the honest CPU realisation of cuml.covariance.LedoitWolf."""
    T = len(returns)
    N = len(returns[0])
    cov, means = _sample_covariance(returns)
    mu = sum(cov[i][i] for i in range(N)) / N  # tr(Σ̂)/N = grand-mean eigenvalue target

    # de-meaned matrix X (T×N)
    X = [[returns[t][j] - means[j] for j in range(N)] for t in range(T)]

    # pi_hat = sum over i,j of Var(x_i x_j); the LW asymptotic numerator
    pi_mat = _zeros(N, N)
    for i in range(N):
        for j in range(N):
            s = 0.0
            sij = cov[i][j]
            for t in range(T):
                d = X[t][i] * X[t][j] - sij
                s += d * d
            pi_mat[i][j] = s / T
    pi_hat = sum(pi_mat[i][j] for i in range(N) for j in range(N))

    # rho_hat (off-diagonal term) is small for the scaled-identity target; LW reduces to
    # the diagonal/identity case here. gamma_hat = ||Σ̂ − μI||_F^2 (the dispersion target).
    gamma_hat = 0.0
    for i in range(N):
        for j in range(N):
            tij = mu if i == j else 0.0
            d = cov[i][j] - tij
            gamma_hat += d * d
    kappa = (pi_hat - 0.0) / gamma_hat if gamma_hat > 0 else 0.0
    rho = max(0.0, min(1.0, kappa / T))

    sigma_lw = _zeros(N, N)
    for i in range(N):
        for j in range(N):
            tij = mu if i == j else 0.0
            sigma_lw[i][j] = (1.0 - rho) * cov[i][j] + rho * tij
    return sigma_lw, rho, mu, means, cov


def _marchenko_pastur_upper(sigma2, q):
    """MP upper bulk edge λ⁺ = σ²(1 + 1/√q)², q = T/N (RMT noise threshold)."""
    return sigma2 * (1.0 + 1.0 / _math.sqrt(q)) ** 2


def _mp_filter(sigma_lw, T, N):
    """Eigendecompose Σ̂_LW, discard eigenvalues ≤ λ⁺ as RMT noise, rebuild cleaned cov.
    Σ̂_clean = Σ_{λ>λ⁺} λ v vᵀ + λ_avg Σ_{λ≤λ⁺} v vᵀ  (trace-preserving)."""
    q = float(T) / float(N)
    eig, V = _jacobi_eigen(sigma_lw)
    avg_eig = sum(eig) / len(eig)
    # MP edge is defined for unit-variance (correlation) entries; scale by the mean
    # eigenvalue so the threshold is comparable to the covariance spectrum (honest scaling).
    lam_plus = _marchenko_pastur_upper(avg_eig, q)
    signal_idx = [i for i in range(N) if eig[i] > lam_plus]
    noise_idx = [i for i in range(N) if eig[i] <= lam_plus]
    noise_mean = (sum(eig[i] for i in noise_idx) / len(noise_idx)) if noise_idx else avg_eig
    eig_clean = [eig[i] if eig[i] > lam_plus else noise_mean for i in range(N)]
    # rebuild Σ_clean = V diag(eig_clean) Vᵀ
    VD = [[V[i][k] * eig_clean[k] for k in range(N)] for i in range(N)]
    sigma_clean = _matmul(VD, _transpose(V))
    return {
        "q_ratio": round(q, 4),
        "lambda_plus": round(lam_plus, 8),
        "eigenvalues": [round(e, 8) for e in sorted(eig, reverse=True)],
        "signal_eigenvalues": len(signal_idx),
        "noise_eigenvalues": len(noise_idx),
        "noise_bulk_mean": round(noise_mean, 8),
        "sigma_clean": sigma_clean,
        "eig_clean": eig_clean,
    }


def layer1_pca_risk(returns=None, stress=False):
    """Layer 1 — PCA Risk. Returns the cleaned covariance + factor structure (SAMPLE)."""
    if returns is None:
        returns = _sample_returns(stress=stress)
    T, N = len(returns), len(returns[0])
    backend = _compute_backend()
    sigma_lw, rho, mu, means, cov = _ledoit_wolf(returns)
    mp = _mp_filter(sigma_lw, T, N)
    return {
        "layer": 1,
        "name": "PCA Risk (Ledoit-Wolf + Marchenko-Pastur)",
        "label": SAMPLE_LABEL,
        "data_source": "SAMPLE_SYNTHETIC",
        "n_assets": N,
        "n_obs": T,
        "shrinkage_rho": round(rho, 6),
        "shrinkage_target_mu": round(mu, 8),
        "q_ratio_N_over_T": round(N / T, 4),
        "marchenko_pastur": {k: v for k, v in mp.items()
                             if k not in ("sigma_clean", "eig_clean")},
        "compute_backend": backend,
        "formulas": {
            "ledoit_wolf": "Σ̂_LW = (1−ρ)Σ̂ + ρ·μI,  μ = tr(Σ̂)/N",
            "marchenko_pastur": "λ± = σ²(1 ± 1/√q)²,  q = T/N",
        },
        "citations": [CITATIONS["ledoit_wolf"], CITATIONS["marchenko_pastur"], CITATIONS["rapids_cuml"]],
        "honest_note": ("Ledoit-Wolf shrinkage intensity ρ and the MP noise edge λ⁺ are computed "
                        "exactly per the cited formulas on a SAMPLE synthetic universe. cuML/cuPy "
                        "GPU acceleration is ROADMAP (CPU fallback ran here). NO backtest."),
        "_internal": {"sigma_lw": sigma_lw, "sigma_clean": mp["sigma_clean"],
                      "means": means, "cov": cov, "mp": mp, "returns_TN": (T, N)},
    }


# =====================================================================================
# LAYER 2 — TDA FRACTURE: correlation-distance + persistent homology Betti β0/β1.
# =====================================================================================
def _correlation_matrix(cov):
    N = len(cov)
    std = [_math.sqrt(cov[i][i]) if cov[i][i] > 0 else 1e-12 for i in range(N)]
    corr = _zeros(N, N)
    for i in range(N):
        for j in range(N):
            corr[i][j] = max(-1.0, min(1.0, cov[i][j] / (std[i] * std[j])))
    return corr


def _correlation_distance(corr):
    """d_ij = √(2(1−ρ_ij)) — the standard econophysics correlation metric."""
    N = len(corr)
    d = _zeros(N, N)
    for i in range(N):
        for j in range(N):
            d[i][j] = _math.sqrt(max(0.0, 2.0 * (1.0 - corr[i][j])))
    return d


def _betti_numbers(dist, eps):
    """Pure-Python Betti numbers of the Vietoris-Rips complex at filtration radius eps.

    β0 = number of connected components of the ε-neighborhood graph (union-find).
    β1 = independent loops (cycle rank) of that 1-skeleton: E − V + C  (Euler relation
    for a graph; an honest, fast approximation of H1 over the 1-skeleton — the genuine
    Vietoris-Rips H1 fills triangles, which the GPU Ripser++/giotto path computes exactly).
    """
    N = len(dist)
    parent = list(range(N))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    edges = 0
    for i in range(N):
        for j in range(i + 1, N):
            if dist[i][j] <= eps:
                edges += 1
                union(i, j)
    comps = len({find(i) for i in range(N)})
    # cycle rank of the 1-skeleton (upper bound on β1 of the VR complex)
    beta1 = max(0, edges - N + comps)
    return comps, beta1, edges


def _persistence_betti(dist, n_steps=24, eps_fixed=None):
    """Sweep the filtration ε over a grid and report β0/β1 at a representative
    'persistence' radius plus the full curve.

    When `eps_fixed` is given, β0/β1 are read at THAT common radius so Δβ across two
    windows reflects genuine reorganization (not each window's own median)."""
    flat = sorted(dist[i][j] for i in range(len(dist)) for j in range(i + 1, len(dist)))
    if not flat:
        return {"beta0": 1, "beta1": 0, "eps_star": 0.0, "curve": []}
    lo, hi = flat[0], flat[-1]
    curve = []
    for s in range(n_steps + 1):
        eps = lo + (hi - lo) * s / n_steps
        b0, b1, e = _betti_numbers(dist, eps)
        curve.append({"eps": round(eps, 5), "beta0": b0, "beta1": b1, "edges": e})
    # representative radius: median pairwise distance (a stable persistence probe)
    eps_star = eps_fixed if eps_fixed is not None else flat[len(flat) // 2]
    b0s, b1s, _ = _betti_numbers(dist, eps_star)
    return {"beta0": b0s, "beta1": b1s, "eps_star": round(eps_star, 5), "curve": curve}


def layer2_tda_fracture(returns=None, prev=None, stress=False):
    """Layer 2 — TDA fracture score f_t = |Δβ0| + |Δβ1|, z-score, anomaly flag (SAMPLE).

    `prev` (optional) = a previous-window {beta0, beta1, fracture_history:[...]} so Δβ and
    the z-score are computed against a real prior. With no prior we compare a calm window
    to a stressed window to make the fracture mechanism demonstrable (honestly synthetic).
    """
    if returns is None:
        returns = _sample_returns(stress=stress)
    backend = _compute_backend()
    cov, _ = _sample_covariance(returns)
    corr = _correlation_matrix(cov)
    dist = _correlation_distance(corr)
    cur = _persistence_betti(dist)

    if prev is None:
        # demonstrate Δβ: compare calm vs stressed SAMPLE windows at a COMMON fixed radius
        # (the calm window's median pairwise distance) so Δβ is a genuine reorganization.
        calm_dist = _correlation_distance(
            _correlation_matrix(_sample_covariance(_sample_returns(stress=False))[0]))
        cflat = sorted(calm_dist[i][j] for i in range(len(calm_dist))
                       for j in range(i + 1, len(calm_dist)))
        eps_common = cflat[len(cflat) // 2] if cflat else None
        calm = _persistence_betti(calm_dist, eps_fixed=eps_common)
        stressed = _persistence_betti(_correlation_distance(
            _correlation_matrix(_sample_covariance(_sample_returns(stress=True))[0])), eps_fixed=eps_common)
        prev_b0, prev_b1 = calm["beta0"], calm["beta1"]
        cur = stressed if stress else _persistence_betti(dist, eps_fixed=eps_common)
        cur_b0, cur_b1 = (cur["beta0"], cur["beta1"])
        # synthetic fracture history for an honest z-score baseline (labeled SAMPLE)
        rng = _random.Random(11)
        history = [abs(rng.gauss(1.2, 0.6)) for _ in range(40)]
    else:
        prev_b0 = int(prev.get("beta0", cur["beta0"]))
        prev_b1 = int(prev.get("beta1", cur["beta1"]))
        cur_b0, cur_b1 = cur["beta0"], cur["beta1"]
        history = list(prev.get("fracture_history", [])) or [0.0]

    fracture = abs(cur_b0 - prev_b0) + abs(cur_b1 - prev_b1)
    mu_f = sum(history) / len(history)
    var_f = sum((h - mu_f) ** 2 for h in history) / max(1, len(history) - 1)
    sigma_f = _math.sqrt(var_f) if var_f > 0 else 1.0
    z = (fracture - mu_f) / sigma_f if sigma_f > 0 else 0.0
    anomaly = abs(z) > 2.5

    return {
        "layer": 2,
        "name": "TDA Fracture (persistent homology Betti β0/β1)",
        "label": SAMPLE_LABEL,
        "data_source": "SAMPLE_SYNTHETIC",
        "beta0_prev": prev_b0, "beta1_prev": prev_b1,
        "beta0_cur": cur_b0, "beta1_cur": cur_b1,
        "fracture_score_f_t": round(float(fracture), 4),
        "z_score": round(float(z), 4),
        "z_threshold": 2.5,
        "anomaly": bool(anomaly),
        "eps_star": cur["eps_star"],
        "betti_curve": cur["curve"],
        "compute_backend": backend,
        "formulas": {
            "distance": "d_ij = √(2(1−ρ_ij))",
            "fracture": "f_t = |Δβ0| + |Δβ1|",
            "zscore": "z_t = (f_t − μ_f)/σ_f,  |z_t| > 2.5 ⇒ anomaly",
        },
        "citations": [CITATIONS["tda_crashes"], CITATIONS["tda_crypto"],
                      CITATIONS["ripserpp"], CITATIONS["giotto_tda"]],
        "honest_note": ("β0 (components) is exact via union-find; β1 is the 1-skeleton cycle rank "
                        "(E−V+C), an honest fast proxy for the genuine Vietoris-Rips H1 that the "
                        "GPU giotto-tda/Ripser++ path (ROADMAP) computes exactly. Synthetic SAMPLE "
                        "windows; z-score baseline is illustrative. NOT calibrated on real data."),
        "_internal": {"dist": dist, "fracture": float(fracture), "z": float(z), "anomaly": bool(anomaly)},
    }


# =====================================================================================
# LAYER 3 — HJB-KELLY SIZING: TDA-augmented effective variance.
# =====================================================================================
def layer3_hjb_kelly(l1=None, l2=None, gamma=0.5, kappa=1.0, stress=False):
    """Layer 3 — HJB/Kelly weights w* = μ̄ / σ²_eff with TDA-augmented variance.

    σ²_eff = σ²_PCA·(1+γ|f_t|)·(1+κ·1_{z>2.5}). Under log-utility (Merton), the optimal
    multi-asset weight is w* = Σ_clean⁻¹ μ̄, scaled by the TDA inflation so de-risking is
    automatic when fracture/anomaly fire. SAMPLE — γ,κ are free, UNcalibrated (no backtest).
    """
    if l1 is None:
        l1 = layer1_pca_risk(stress=stress)
    if l2 is None:
        l2 = layer2_tda_fracture(stress=stress)
    backend = _compute_backend()
    sigma_clean = l1["_internal"]["sigma_clean"]
    means = l1["_internal"]["means"]
    N = len(sigma_clean)
    f_t = abs(l2["_internal"]["fracture"])
    z = l2["_internal"]["z"]
    anomaly = l2["_internal"]["anomaly"]

    inflation = (1.0 + gamma * f_t) * (1.0 + kappa * (1.0 if z > 2.5 else 0.0))

    # Σ_eff = inflation · Σ_clean (scalar variance inflation channel, per the formula)
    sigma_eff = [[sigma_clean[i][j] * inflation for j in range(N)] for i in range(N)]
    # excess-return vector μ̄ (SAMPLE: use sample means as the drift proxy)
    mu_bar = means
    # w* = Σ_eff⁻¹ μ̄  (solve, with tiny ridge inside _solve_spd)
    try:
        w_star = _solve_spd(sigma_eff, mu_bar)
    except Exception:
        w_star = [0.0] * N
    # uninflated baseline for the de-risking ratio
    try:
        w_base = _solve_spd(sigma_clean, mu_bar)
    except Exception:
        w_base = w_star
    gross = sum(abs(w) for w in w_star)
    gross_base = sum(abs(w) for w in w_base) or 1e-12
    derisk_ratio = gross / gross_base if gross_base else 1.0

    return {
        "layer": 3,
        "name": "HJB-Kelly Sizing (TDA-augmented variance)",
        "label": SAMPLE_LABEL,
        "data_source": "SAMPLE_SYNTHETIC",
        "gamma": gamma, "kappa": kappa,
        "fracture_score_f_t": round(f_t, 4),
        "z_score": round(z, 4),
        "anomaly_active": bool(anomaly),
        "sigma_eff_inflation": round(inflation, 4),
        "kelly_weights_w_star": [round(w, 6) for w in w_star],
        "kelly_gross_exposure": round(gross, 6),
        "derisk_ratio_vs_uninflated": round(derisk_ratio, 4),
        "compute_backend": backend,
        "formulas": {
            "sigma_eff": "σ²_eff = σ²_PCA·(1+γ|f_t|)·(1+κ·1_{z>2.5})",
            "kelly": "w* = μ̄ / σ²_eff  (Merton log-utility; w* = Σ_eff⁻¹ μ̄ multi-asset)",
        },
        "citations": [CITATIONS["merton_kelly"], CITATIONS["brodetsky"]],
        "honest_note": ("Weights auto-compress when fracture/anomaly fire (derisk_ratio<1) — the "
                        "elegant property of the TDA-Kelly channel. BUT γ and κ are free, "
                        "UNcalibrated hyperparameters: this is MODELED architecture, NOT a "
                        "backtested strategy. NEVER a live-trading instruction."),
    }


# =====================================================================================
# FULL PIPELINE -> ONE DSSE-bearing SAMPLE receipt.
# =====================================================================================
def run_pipeline(stress=False, gamma=0.5, kappa=1.0) -> dict:
    """Full 3-layer pass plus a DSSE envelope whose signature state is explicit."""
    returns = _sample_returns(stress=stress)
    l1 = layer1_pca_risk(returns=returns, stress=stress)
    l2 = layer2_tda_fracture(returns=returns, stress=stress)
    l3 = layer3_hjb_kelly(l1=l1, l2=l2, gamma=gamma, kappa=kappa, stress=stress)
    backend = _compute_backend()

    receipt = {
        "bar_timestamp": _now_iso(),
        "data_source": "SAMPLE_SYNTHETIC",
        "pipeline_version": "szl-gpu-quant-v0.1",
        "gpu_device": backend["backend"],
        "compute_label": backend["label"],
        "scenario": "stress" if stress else "calm",
        "layer1": {
            "shrinkage_rho": l1["shrinkage_rho"],
            "shrinkage_target_mu": l1["shrinkage_target_mu"],
            "signal_eigenvalues": l1["marchenko_pastur"]["signal_eigenvalues"],
            "noise_bulk_edge_lambda_plus": l1["marchenko_pastur"]["lambda_plus"],
        },
        "layer2": {
            "fracture_score_f_t": l2["fracture_score_f_t"],
            "z_score": l2["z_score"],
            "anomaly": l2["anomaly"],
            "beta0_cur": l2["beta0_cur"], "beta1_cur": l2["beta1_cur"],
        },
        "layer3": {
            "sigma_eff_inflation": l3["sigma_eff_inflation"],
            "kelly_gross_exposure": l3["kelly_gross_exposure"],
            "derisk_ratio": l3["derisk_ratio_vs_uninflated"],
        },
        "label": SAMPLE_LABEL,
        "doctrine": DOCTRINE["version"],
        "lambda": "Conjecture 1 (advisory, NOT a theorem)",
        "citations": [CITATIONS["ledoit_wolf"], CITATIONS["marchenko_pastur"],
                      CITATIONS["tda_crashes"], CITATIONS["merton_kelly"],
                      CITATIONS["rapids_cuml"], CITATIONS["brodetsky"]],
        "honesty": ("Synthetic SAMPLE universe. NOT live-trading. NO backtest run. "
                    "GPU (cuML/cuPy/giotto) path is ROADMAP; CPU fallback ran here. "
                    "Math validated to primary sources; calibration MODELED."),
    }
    dsse = _sign_payload(receipt, _QUANT_PAYLOAD_TYPE)
    return {
        "service": "gpu-quant-engine",
        "doctrine": DOCTRINE,
        "scenario": "stress" if stress else "calm",
        "compute_backend": backend,
        "layer1": l1,
        "layer2": {k: v for k, v in l2.items() if k != "_internal"},
        "layer3": l3,
        "signed_receipt": {"receipt": receipt, "dsse": dsse},
        "label": SAMPLE_LABEL,
        "computed_at": _now_iso(),
    }


# =====================================================================================
# 2-GPU SOVEREIGN SERVE TIER PANEL (per NEMOTRON_TWO_GPU_PLAN.md).
# =====================================================================================
def _energy_fields():
    """Reuse Dev C's per-GPU energy fields if the module is present (honest ROADMAP else)."""
    try:
        import szl_energy_sovereign as _es  # type: ignore
        return _es.energy_fields_for_receipt()
    except Exception:
        return {"joules_consumed": None, "carbon_g_co2eq": None, "energy_label": "ROADMAP",
                "joules_honesty": "sample",
                "energy_source_note": "szl_energy_sovereign not importable; energy honestly ROADMAP."}


def tiers_panel() -> dict:
    """2-GPU serve tier panel: TP=2 / role-split (local, sovereign-gated) + NIM cloud (sovereign:false).

    sovereign:true ONLY with a live per-GPU gpu_reachable probe. Per-GPU joules reuse Dev C
    energy (ROADMAP until the on-box exporter emits). Tokens/s / power-cap watts are MEASURED
    only when the box emits them — else honestly ROADMAP. NEVER fabricated."""
    state = _sovereign_state()
    reachable = _gpu_reachable(state)
    energy = _energy_fields()
    nim_configured = bool((_os.environ.get("A11OY_NIM_API_KEY") or _os.environ.get("NVIDIA_NIM_API_KEY") or "").strip())

    def per_gpu(label):
        return {
            "gpu": label,
            "gpu_reachable": reachable,
            "joules_consumed": energy.get("joules_consumed"),
            "joules_label": energy.get("energy_label", "ROADMAP"),
            "power_cap_watts": None,          # set by `nvidia-smi -pl <w>` on-box (ROADMAP)
            "power_cap_label": "ROADMAP",
            "tokens_per_s": None,             # from vLLM /metrics on-box (ROADMAP)
            "tokens_per_s_label": "ROADMAP",
        }

    tiers = [
        {
            "tier": "sovereign-local · TENSOR-PARALLEL TP=2",
            "where": "gpu",
            "sovereign": bool(reachable),
            "config": "vLLM --tensor-parallel-size 2 shards ONE larger model across a-11-oy.com GPU + RTX 4000",
            "fits": "e.g. Qwen3-32B comfortably, or a quantized Nemotron-3-Super across combined VRAM",
            "gpus": [per_gpu("a-11-oy.com GPU"), per_gpu("NVIDIA RTX 4000 (Ada, ~20GB)")],
            "label": "LIVE_REACHABLE" if reachable else "ROADMAP",
            "execution_evidence": None,
        },
        {
            "tier": "sovereign-local · ROLE-SPLIT (recommended for agent loops)",
            "where": "gpu",
            "sovereign": bool(reachable),
            "config": ("main GPU = primary agent model; RTX 4000 = dedicated governance/draft GPU: "
                       "Auto-Review CLASSIFIER + speculative-decode DRAFT (Qwen2.5-Coder-1.5B) + embeddings"),
            "fits": "keeps the main GPU from stalling on inline review/draft — best fit for our agent+Auto-Review arch",
            "gpus": [per_gpu("a-11-oy.com GPU · primary model"),
                     per_gpu("RTX 4000 · classifier+draft+embeddings")],
            "label": "LIVE_REACHABLE" if reachable else "ROADMAP",
            "execution_evidence": None,
        },
        {
            "tier": "cloud · NVIDIA NIM (Nemotron 3 Ultra) — frontier/hard tier",
            "where": "cloud",
            "sovereign": False,  # NEVER sovereign — honest; routed via LiteLLM/RouteLLM gateway
            "config": "Route via build.nvidia.com NIM through our LiteLLM/RouteLLM gateway",
            "fits": ("Ultra (550B-A55B) needs ~768GB VRAM (4×GB200-class) — CANNOT run on 2 local GPUs. "
                     "NEVER claim local Ultra. Verify NVIDIA claims on OUR τ-bench+J/token harness."),
            "nim_key_configured": nim_configured,
            "label": "LIVE" if nim_configured else "ROADMAP",
        },
    ]
    return {
        "service": "two-gpu-sovereign-serve",
        "doctrine": DOCTRINE["version"],
        "sovereign": bool(reachable),
        "gpu_reachable": reachable,
        "inference_state": state,
        "tiers": tiers,
        "energy_fields": energy,
        "honesty": ("sovereign:true ONLY with a live per-GPU gpu_reachable probe. Per-GPU joules reuse "
                    "the Dev C energy layer (ROADMAP until the 2-GPU power.draw exporter emits). NIM is "
                    "a cloud tier (sovereign:false) — Ultra never runs on 2 local GPUs. The exact box "
                    "commands (vLLM TP=2 / role-split, nvidia-smi -pl, MPS/MIG, 2-GPU exporter, NIM key) "
                    "are in team/AUDIT/elevate/FORGE_2GPU_ENERGY.md (founder-gated; box NOT touched)."),
        "box_order": "FORGE_2GPU_ENERGY.md",
        "computed_at": _now_iso(),
    }


# =====================================================================================
# VERIFY-THE-CLAIMS panel: NVIDIA datasheet vs SZL-MEASURED (honest; empty/ROADMAP).
# =====================================================================================
def _legacy_verify_claims_panel() -> dict:
    """Side-by-side NVIDIA datasheet numbers vs SZL-MEASURED (signed). Honest: SZL columns
    are empty/ROADMAP until we actually measure on OUR harness. NEVER print the datasheet
    number as if it were ours."""
    reachable = _gpu_reachable()
    rows = [
        {"claim": "Nemotron speedup vs prior frontier", "nvidia_datasheet": "up to 5×",
         "szl_measured": None, "szl_label": "ROADMAP",
         "how": "OUR τ-bench + J/token harness on the NIM-routed Ultra tier"},
        {"claim": "Reasoning/accuracy uplift", "nvidia_datasheet": "+30%",
         "szl_measured": None, "szl_label": "ROADMAP",
         "how": "OUR τ-bench score (MEASURED-by-SZL), signed receipt"},
        {"claim": "Benchmark accuracy", "nvidia_datasheet": "91%",
         "szl_measured": None, "szl_label": "ROADMAP",
         "how": "OUR eval set, ECE/Brier calibrated"},
        {"claim": "Long-context retrieval", "nvidia_datasheet": "1M-token retrieval",
         "szl_measured": None, "szl_label": "ROADMAP",
         "how": "OUR needle-in-haystack probe, signed"},
        {"claim": "cuML PCA speedup (quant Layer 1)", "nvidia_datasheet": "10–50× (S&P 500 scale); ~100× genomic",
         "szl_measured": None, "szl_label": "ROADMAP",
         "how": "OUR Layer-1 LedoitWolf on the sovereign GPU vs CPU fallback, signed J/bar"},
        {"claim": "Ripser++ persistence (quant Layer 2)", "nvidia_datasheet": "up to 30× vs CPU Ripser",
         "szl_measured": None, "szl_label": "ROADMAP",
         "how": "OUR Layer-2 VR persistence on the sovereign GPU, signed bar latency"},
    ]
    return {
        "service": "verify-the-claims",
        "doctrine": DOCTRINE["version"],
        "summary": ("EMPTY / ROADMAP until SZL measures on its own harness — this is the differentiator: "
                    "we publish SZL-MEASURED (signed), never the datasheet number."),
        "gpu_reachable": reachable,
        "rows": rows,
        "honesty": ("The 'NVIDIA datasheet' column is the vendor's published claim (cited, not endorsed). "
                    "The 'SZL-MEASURED' column stays null/ROADMAP until we run OUR τ-bench + J/token + "
                    "J/bar harness and SIGN the result. measured > datasheet, always. Never fabricated."),
        "citations": [CITATIONS["rapids_cuml"], CITATIONS["ripserpp"]],
        "computed_at": _now_iso(),
    }


# =====================================================================================
# Receipt-gated local verification. The legacy static panel above is retained only as
# historical code; this definition is authoritative for routes and the UI.
# =====================================================================================
_QUANT_RECEIPT_SCHEMA = "szl.quant-live-benchmark-receipt.v1"
_QUANT_RECEIPT_SCOPE = "bounded local execution; not a replication of vendor-scale claims"
_QUANT_RECEIPT_PAYLOAD_TYPE = "application/vnd.szl.quant-live-benchmark+json"


def _dsse_signature_state(dsse):
    """Classify a DSSE envelope from cryptographic evidence, not its flag."""
    if not isinstance(dsse, dict):
        return "INVALID_SIGNATURE"
    signatures = dsse.get("signatures")
    if not isinstance(signatures, list):
        return "INVALID_SIGNATURE"
    if dsse.get("signed") is True:
        verdict = _verify_envelope(dsse)
        if isinstance(verdict, dict) and verdict.get("verified") is True:
            return "SIGNED_VERIFIED"
        return "INVALID_SIGNATURE"
    if signatures:
        return "INVALID_SIGNATURE"
    return "UNSIGNED_CONTENT_ADDRESSED"


def _finite_number(value, field, minimum=None, maximum=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not _math.isfinite(float(value)):
        raise ValueError("%s must be a finite number" % field)
    number = float(value)
    if minimum is not None and number < minimum:
        raise ValueError("%s is below its allowed minimum" % field)
    if maximum is not None and number > maximum:
        raise ValueError("%s exceeds its allowed maximum" % field)
    return number


def _bounded_int(value, field, minimum=0, maximum=1_000_000):
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ValueError("%s must be an integer between %s and %s" % (field, minimum, maximum))
    return value


def _aware_timestamp(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("%s missing" % field)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("%s is not an ISO-8601 timestamp" % field) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("%s must include a timezone" % field)
    return parsed.astimezone(timezone.utc)


def _validate_model_identity(identity, measurement, role):
    if not isinstance(identity, dict):
        raise ValueError("%s identity missing" % role)
    if not isinstance(measurement, dict):
        raise ValueError("%s measurement missing" % role)
    requested = identity.get("requested_model")
    if not isinstance(requested, str) or not requested.strip() or requested != measurement.get("model"):
        raise ValueError("%s identity does not match measured model" % role)
    manifest_hash = identity.get("show_response_sha256")
    if not isinstance(manifest_hash, str) or len(manifest_hash) != 64:
        raise ValueError("%s identity manifest hash missing" % role)
    try:
        int(manifest_hash, 16)
    except ValueError as exc:
        raise ValueError("%s identity manifest hash is not SHA-256" % role) from exc
    lineage = identity.get("base_lineage")
    if not isinstance(lineage, dict) or not any(
        isinstance(lineage.get(key), str) and lineage.get(key).strip()
        for key in ("base_ref", "parent_model", "base_digest")
    ):
        raise ValueError("%s base lineage missing" % role)
    wall_ms = identity.get("show_wall_ms")
    if wall_ms is not None:
        _finite_number(wall_ms, "%s identity show_wall_ms" % role, 0.0)
    return manifest_hash.lower()


def _validate_model_measurement(measurement, role):
    if not isinstance(measurement, dict):
        raise ValueError("%s measurement missing" % role)
    exact = measurement.get("exact_match")
    retrieval = measurement.get("bounded_retrieval")
    runtime = measurement.get("runtime")
    if not isinstance(exact, dict) or not isinstance(retrieval, dict) or not isinstance(runtime, dict):
        raise ValueError("%s semantic measurement sections missing" % role)
    total = _bounded_int(exact.get("tasks_total"), "%s tasks_total" % role, 1, 10_000)
    passed = _bounded_int(exact.get("tasks_passed"), "%s tasks_passed" % role, 0, total)
    accuracy = _finite_number(exact.get("accuracy_pct"), "%s accuracy_pct" % role, 0.0, 100.0)
    expected_accuracy = 100.0 * passed / total
    if abs(accuracy - expected_accuracy) > 0.001:
        raise ValueError("%s accuracy_pct is inconsistent with pass counts" % role)
    probes_total = _bounded_int(retrieval.get("probes_total"), "%s probes_total" % role, 1, 10_000)
    _bounded_int(retrieval.get("probes_passed"), "%s probes_passed" % role, 0, probes_total)
    _bounded_int(
        retrieval.get("max_prompt_eval_tokens"), "%s max_prompt_eval_tokens" % role, 0, 10_000_000
    )
    _bounded_int(runtime.get("requests"), "%s runtime requests" % role, 1, 100_000)
    latency = _finite_number(runtime.get("p50_wall_ms"), "%s p50_wall_ms" % role, 0.000001)
    tps = runtime.get("p50_tokens_per_second")
    if tps is not None:
        _finite_number(tps, "%s p50_tokens_per_second" % role, 0.000001)
    return {"accuracy": accuracy, "latency": latency}


def _validate_cpu_reference(reference, field):
    if not isinstance(reference, dict):
        raise ValueError("%s missing" % field)
    _bounded_int(reference.get("repeats"), "%s repeats" % field, 1, 20)
    minimum = _finite_number(reference.get("min_ms"), "%s min_ms" % field, 0.0)
    p50 = _finite_number(reference.get("p50_ms"), "%s p50_ms" % field, 0.0)
    maximum = _finite_number(reference.get("max_ms"), "%s max_ms" % field, 0.0)
    if minimum > p50 or p50 > maximum:
        raise ValueError("%s latency order is inconsistent" % field)
    if reference.get("compute_path") != "CPU_REFERENCE":
        raise ValueError("%s is not an explicit CPU reference" % field)
    return p50


def _validate_quant_receipt(envelope):
    if not isinstance(envelope, dict):
        raise ValueError("receipt envelope missing")
    receipt = envelope.get("receipt")
    if not isinstance(receipt, dict):
        raise ValueError("receipt object missing")
    if receipt.get("schema_version") != _QUANT_RECEIPT_SCHEMA:
        raise ValueError("unsupported receipt schema")
    if receipt.get("measurement_class") != "MEASURED":
        raise ValueError("receipt is not a completed MEASURED execution")
    if receipt.get("scope") != _QUANT_RECEIPT_SCOPE:
        raise ValueError("receipt scope is not the bounded local harness")

    claimed_digest = receipt.get("content_sha256")
    unsigned_body = dict(receipt)
    unsigned_body.pop("content_sha256", None)
    observed_digest = _hashlib.sha256(
        _json.dumps(unsigned_body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    if claimed_digest != observed_digest:
        raise ValueError("content digest mismatch")

    started = _aware_timestamp(receipt.get("started_at"), "started_at")
    completed = _aware_timestamp(receipt.get("completed_at"), "completed_at")
    now = datetime.now(timezone.utc)
    if completed < started:
        raise ValueError("completed_at precedes started_at")
    if completed.timestamp() > now.timestamp() + 300:
        raise ValueError("completed_at is implausibly in the future")

    ollama = receipt.get("ollama")
    if not isinstance(ollama, dict) or ollama.get("base_url_class") != "loopback-local":
        raise ValueError("receipt is not bound to a loopback-local Ollama endpoint")
    candidate = ollama.get("candidate")
    baseline = ollama.get("baseline")
    c_identity = _validate_model_identity(ollama.get("candidate_identity"), candidate, "candidate")
    b_identity = _validate_model_identity(ollama.get("baseline_identity"), baseline, "baseline")
    if c_identity == b_identity:
        raise ValueError("candidate and baseline resolve to the same manifest")
    stability = ollama.get("identity_stability")
    if not isinstance(stability, dict) or stability.get("stable") is not True:
        raise ValueError("model identity stability is not proven")
    if not (
        stability.get("candidate_before_sha256") == c_identity
        and stability.get("candidate_after_sha256") == c_identity
        and stability.get("baseline_before_sha256") == b_identity
        and stability.get("baseline_after_sha256") == b_identity
    ):
        raise ValueError("model identity drift detected in receipt")

    candidate_metrics = _validate_model_measurement(candidate, "candidate")
    baseline_metrics = _validate_model_measurement(baseline, "baseline")
    comparisons = receipt.get("comparisons")
    if not isinstance(comparisons, dict):
        raise ValueError("comparison metrics missing")
    speed = _finite_number(
        comparisons.get("candidate_vs_baseline_wall_speed_ratio"), "wall speed ratio", 0.000001
    )
    expected_speed = baseline_metrics["latency"] / candidate_metrics["latency"]
    if abs(speed - expected_speed) > 0.0001:
        raise ValueError("wall speed ratio is inconsistent with measured latency")
    uplift = _finite_number(
        comparisons.get("candidate_minus_baseline_exact_match_points"), "accuracy uplift", -100.0, 100.0
    )
    expected_uplift = candidate_metrics["accuracy"] - baseline_metrics["accuracy"]
    if abs(uplift - expected_uplift) > 0.001:
        raise ValueError("accuracy uplift is inconsistent with measured accuracy")

    quant_reference = receipt.get("quant_reference")
    if not isinstance(quant_reference, dict):
        raise ValueError("quant reference section missing")
    _validate_cpu_reference(quant_reference.get("pca_pipeline"), "pca_pipeline")
    _validate_cpu_reference(quant_reference.get("tda_stress_pipeline"), "tda_stress_pipeline")
    gpu_comparison = quant_reference.get("gpu_acceleration_comparison")
    if not isinstance(gpu_comparison, str) or not gpu_comparison.startswith("UNAVAILABLE:"):
        raise ValueError("GPU acceleration status is not an explicit structured refusal")

    dsse = envelope.get("dsse")
    if not isinstance(dsse, dict):
        raise ValueError("DSSE status missing")
    signatures = dsse.get("signatures")
    if not isinstance(signatures, list):
        raise ValueError("DSSE signatures must be a list")
    embedded = dsse.get("payload")
    if embedded is not None:
        if dsse.get("payloadType") != _QUANT_RECEIPT_PAYLOAD_TYPE:
            raise ValueError("DSSE payload type mismatch")
        try:
            decoded = _base64.b64decode(embedded, validate=True)
        except Exception as exc:
            raise ValueError("DSSE payload is not valid base64") from exc
        expected = _json.dumps(receipt, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        if decoded != expected:
            raise ValueError("DSSE payload does not match receipt")
    if dsse.get("signed") is True:
        if not signatures or embedded is None:
            raise ValueError("DSSE claims signed without signatures and payload")
        verdict = _verify_envelope(dsse)
        if not isinstance(verdict, dict) or verdict.get("verified") is not True:
            reason = verdict.get("reason") if isinstance(verdict, dict) else None
            suffix = ": " + str(reason) if reason else ""
            raise ValueError("DSSE signature verification failed" + suffix)
        signature_state = "SIGNED_VERIFIED"
    elif signatures:
        raise ValueError("unsigned DSSE contains signatures")
    else:
        signature_state = "UNSIGNED_CONTENT_ADDRESSED"

    raw_fresh_seconds = _os.environ.get("SZL_QUANT_BENCH_FRESH_SECONDS", "604800")
    try:
        fresh_seconds = int(raw_fresh_seconds)
    except ValueError as exc:
        raise ValueError("SZL_QUANT_BENCH_FRESH_SECONDS must be an integer") from exc
    if not 60 <= fresh_seconds <= 2_678_400:
        raise ValueError("SZL_QUANT_BENCH_FRESH_SECONDS is outside the allowed range")
    age_seconds = max(0, int((now - completed).total_seconds()))
    return {
        "envelope": envelope,
        "age_seconds": age_seconds,
        "freshness_state": "CURRENT" if age_seconds <= fresh_seconds else "HISTORICAL",
        "candidate_manifest_sha256": c_identity,
        "baseline_manifest_sha256": b_identity,
        "signature_state": signature_state,
    }


def verify_claims_panel() -> dict:
    """Read a bounded local benchmark receipt without producing side effects.

    Missing, semantically inconsistent, stale-looking, or tampered data never
    becomes a live claim. Valid old receipts remain visible as HISTORICAL.
    """
    configured_path = _os.environ.get("SZL_QUANT_BENCH_RECEIPT", "").strip()
    receipt_candidates = ([_Path(configured_path)] if configured_path else [
        _Path.home() / ".a11oy" / "receipts" / "quant-live-benchmark.json",
        _Path(__file__).resolve().parent / "benchmarks" / "quant_live" / "receipts" / "latest.json",
    ])
    receipt_path = next((path for path in receipt_candidates if path.is_file()), receipt_candidates[0])
    measured = None
    validation = None
    receipt_error = None
    try:
        if receipt_path.is_file() and receipt_path.stat().st_size <= 2_000_000:
            envelope = _json.loads(receipt_path.read_text(encoding="utf-8"))
            validation = _validate_quant_receipt(envelope)
            measured = validation["envelope"]
        else:
            receipt_error = "measurement receipt absent"
    except (OSError, ValueError, TypeError, _json.JSONDecodeError) as exc:
        receipt_error = "%s: %s" % (type(exc).__name__, exc)

    local = measured.get("receipt") if measured else {}
    ollama = local.get("ollama", {})
    candidate = ollama.get("candidate", {})
    baseline = ollama.get("baseline", {})
    comparisons = local.get("comparisons", {})
    quant_reference = local.get("quant_reference", {})
    freshness = (validation or {}).get("freshness_state", "NO_RECEIPT")
    signature_state = (validation or {}).get("signature_state", "NO_RECEIPT")
    signed = signature_state == "SIGNED_VERIFIED"

    def cell(value, how):
        if measured is None:
            return {"szl_measured": None, "szl_label": "NOT_MEASURED", "how": how,
                    "comparison_status": "NO_RECEIPT", "freshness_label": freshness}
        return {"szl_measured": value, "szl_label": "MEASURED", "how": how,
                "comparison_status": "BOUNDED_LOCAL_NOT_VENDOR_REPLICATION",
                "freshness_label": freshness}

    def no_gpu_claim(local_reference, how):
        return {
            "szl_measured": None,
            "szl_label": "NOT_MEASURED",
            "local_reference": local_reference if measured else None,
            "local_reference_label": "MEASURED" if measured else "NOT_MEASURED",
            "how": how,
            "comparison_status": "NO_GPU_COMPARISON_RECEIPT" if measured else "NO_RECEIPT",
            "freshness_label": freshness,
        }

    def vendor_row(claim, reported, values):
        return {"claim": claim, "nvidia_datasheet": reported, "nvidia_label": "REPORTED", **values}

    c_acc = candidate.get("exact_match", {})
    c_ret = candidate.get("bounded_retrieval", {})
    speed = comparisons.get("candidate_vs_baseline_wall_speed_ratio")
    uplift = comparisons.get("candidate_minus_baseline_exact_match_points")
    pca = quant_reference.get("pca_pipeline", {})
    tda = quant_reference.get("tda_stress_pipeline", {})
    rows = [
        vendor_row("Nemotron speedup vs prior frontier", "up to 5x", no_gpu_claim(
            ("%sx local Ollama wall-speed ratio vs %s" % (speed, baseline.get("model"))) if speed is not None else None,
            "Local Ollama p50 wall latency is separate evidence; no vendor-frontier or GPU comparison receipt exists.")),
        vendor_row("Reasoning/accuracy uplift", "+30%", cell(
            ("%s percentage points vs local baseline" % uplift) if uplift is not None else None,
            "Six preregistered deterministic exact-match operational probes; not a general reasoning benchmark.")),
        vendor_row("Benchmark accuracy", "91%", cell(
            ("%s%% (%s/%s exact match)" % (c_acc.get("accuracy_pct"), c_acc.get("tasks_passed"), c_acc.get("tasks_total"))) if c_acc else None,
            "Bounded SZL exact-match operational suite; not NVIDIA's benchmark.")),
        vendor_row("Long-context retrieval", "1M-token retrieval", cell(
            ("%s/%s needles; max %s evaluated prompt tokens" % (c_ret.get("probes_passed"), c_ret.get("probes_total"), c_ret.get("max_prompt_eval_tokens"))) if c_ret else None,
            "Bounded local needle probes; no one-million-token claim.")),
        vendor_row("cuML PCA speedup (quant Layer 1)", "10-50x (S&P 500 scale); about 100x genomic", no_gpu_claim(
            ("CPU reference p50 %s ms; GPU comparison UNAVAILABLE" % pca.get("p50_ms")) if pca else None,
            "Measured CPU reference only; no distinct cuML execution receipt exists.")),
        vendor_row("Ripser++ persistence (quant Layer 2)", "up to 30x vs CPU Ripser", no_gpu_claim(
            ("CPU stress reference p50 %s ms; GPU comparison UNAVAILABLE" % tda.get("p50_ms")) if tda else None,
            "Measured CPU reference only; no distinct Ripser++ execution receipt exists.")),
    ]
    for row in rows:
        row.setdefault("local_reference", None)
        row.setdefault("local_reference_label", "NOT_MEASURED")
    return {
        "service": "verify-the-claims",
        "doctrine": DOCTRINE["version"],
        "summary": (("Current" if freshness == "CURRENT" else "Historical")
                    + " bounded %s receipt loaded; vendor-scale and GPU comparisons remain out of scope."
                    % ("cryptographically verified DSSE" if signed else "unsigned content-addressed")
                    if measured else "No valid local measurement receipt is available; no number is invented."),
        "gpu_reachable": _gpu_reachable(),
        "rows": rows,
        "receipt": {"path_class": "operator-local", "loaded": bool(measured), "error": receipt_error,
                    "content_sha256": local.get("content_sha256"), "completed_at": local.get("completed_at"),
                    "dsse_signed": signed,
                    "signature_state": signature_state,
                    "freshness_state": freshness, "age_seconds": (validation or {}).get("age_seconds"),
                    "candidate_manifest_sha256": (validation or {}).get("candidate_manifest_sha256"),
                    "baseline_manifest_sha256": (validation or {}).get("baseline_manifest_sha256")},
        "honesty": ("The NVIDIA column is a cited vendor claim, not an endorsement. The SZL column comes from a "
                    "bounded local execution receipt and is not presented as a vendor-scale replication. Signature "
                    "state is derived from cryptographic verification; unsigned content-addressed evidence is never "
                    "displayed as signed."),
        "citations": [CITATIONS["rapids_cuml"], CITATIONS["ripserpp"]],
        "computed_at": _now_iso(),
    }


# =====================================================================================
# Unified "Quant Engine" HTML tab (0 CDN; window.SZLLabels).
# =====================================================================================
def _html(pipe: dict, tiers: dict, verify: dict) -> str:
    l1 = pipe["layer1"]; l2 = pipe["layer2"]; l3 = pipe["layer3"]
    backend = pipe["compute_backend"]
    d = DOCTRINE

    def row(k, v):
        return ('<div class="kv"><span class="k">%s</span><span class="v">%s</span></div>' % (k, v))

    def fmt(v):
        return "—" if v is None else str(v)

    def card(title, label, body, note):
        return ('<article class="card"><div class="row"><h3>%s</h3>'
                '<span class="pill-slot" data-label="%s"></span></div>%s'
                '<p class="note">%s</p></article>' % (title, label, body, note))

    l1_body = (row("Ledoit-Wolf ρ", fmt(l1["shrinkage_rho"]))
               + row("MP edge λ⁺", fmt(l1["marchenko_pastur"]["lambda_plus"]))
               + row("signal eigenvalues", fmt(l1["marchenko_pastur"]["signal_eigenvalues"]))
               + row("noise eigenvalues", fmt(l1["marchenko_pastur"]["noise_eigenvalues"]))
               + row("N×T", "%s × %s" % (l1["n_assets"], l1["n_obs"]))
               + row("backend", "<code>%s</code>" % backend["backend"]))
    l2_body = (row("fracture f_t", fmt(l2["fracture_score_f_t"]))
               + row("z-score", fmt(l2["z_score"]))
               + row("anomaly |z|&gt;2.5", fmt(l2["anomaly"]))
               + row("β0 (components)", "%s → %s" % (l2["beta0_prev"], l2["beta0_cur"]))
               + row("β1 (loops)", "%s → %s" % (l2["beta1_prev"], l2["beta1_cur"])))
    l3_body = (row("σ²_eff inflation", fmt(l3["sigma_eff_inflation"]))
               + row("Kelly gross exposure", fmt(l3["kelly_gross_exposure"]))
               + row("de-risk ratio", fmt(l3["derisk_ratio_vs_uninflated"]))
               + row("γ, κ", "%s, %s <small>(uncalibrated)</small>" % (l3["gamma"], l3["kappa"])))
    dsse = pipe["signed_receipt"]["dsse"]
    pipeline_signature_state = _dsse_signature_state(dsse)
    pipeline_signed = pipeline_signature_state == "SIGNED_VERIFIED"
    pipeline_receipt_title = (
        "Verified Signed SAMPLE Receipt" if pipeline_signed else
        "Unsigned SAMPLE Receipt" if pipeline_signature_state == "UNSIGNED_CONTENT_ADDRESSED" else
        "Invalid DSSE SAMPLE Receipt"
    )
    pipeline_receipt_note = (
        "DSSE signature verified against the configured SZL public key."
        if pipeline_signed else
        "Content-addressed DSSE envelope; no verified signature is present."
        if pipeline_signature_state == "UNSIGNED_CONTENT_ADDRESSED" else
        "DSSE signature is invalid or unverifiable; this receipt is not presented as signed."
    )
    rc_body = (row("data source", "SAMPLE_SYNTHETIC")
               + row("pipeline", "<code>szl-gpu-quant-v0.1</code>")
               + row("signature state", pipeline_signature_state)
               + row("PAE sha256", "<code>%s…</code>" % str(dsse.get("_pae_sha256", ""))[:16])
               + row("label", "<small>%s</small>" % SAMPLE_LABEL))

    tier_cards = ""
    for t in tiers["tiers"]:
        gpus = ""
        for g in t.get("gpus", []):
            gpus += row(g["gpu"], "joules=%s <small>(%s)</small> · tok/s=%s · cap=%sW" % (
                fmt(g["joules_consumed"]), g["joules_label"],
                fmt(g["tokens_per_s"]), fmt(g["power_cap_watts"])))
        body = (row("where", t["where"]) + row("sovereign", fmt(t["sovereign"]))
                + ('<div class="kv"><span class="k">config</span></div><p class="cfg">%s</p>' % t["config"])
                + gpus)
        tier_cards += card(t["tier"], t["label"], body, t.get("fits", ""))

    vrows = ""
    for r in verify["rows"]:
        vrows += ('<tr><td>%s</td><td class="ds"><span class="pill-slot" data-label="%s"></span> %s</td>'
                  '<td class="ms"><span class="pill-slot" data-label="%s"></span> %s<br><small>%s</small></td>'
                  '<td class="ms"><span class="pill-slot" data-label="%s"></span> %s</td></tr>' % (
                      r["claim"], r["nvidia_label"], r["nvidia_datasheet"],
                      r["szl_label"], fmt(r["szl_measured"]), r.get("freshness_label", "NO_RECEIPT"),
                      r["local_reference_label"], fmt(r["local_reference"])))
    verify_tbl = ('<table class="vt"><thead><tr><th>Claim</th><th>NVIDIA published</th>'
                  '<th>SZL comparison</th><th>Separate local evidence</th></tr></thead>'
                  '<tbody>%s</tbody></table>' % vrows)
    receipt_view = verify.get("receipt", {})
    receipt_line = ("loaded=%s · completed_at=%s · signature=%s · content_sha256=%s" % (
        receipt_view.get("loaded"), receipt_view.get("completed_at") or "—",
        receipt_view.get("signature_state") or "UNKNOWN",
        (str(receipt_view.get("content_sha256") or "—")[:20] + "…")
        if receipt_view.get("content_sha256") else "—"))

    cards = "".join([
        card("Layer 1 · PCA Risk (LW + MP)", l1["label"].split(" | ")[0].replace("_SIGNAL", ""), l1_body, l1["honest_note"]),
        card("Layer 2 · TDA Fracture (β0/β1)", "SAMPLE", l2_body, l2["honest_note"]),
        card("Layer 3 · HJB-Kelly Sizing", "MODELED", l3_body, l3["honest_note"]),
        card(pipeline_receipt_title, "SAMPLE", rc_body, pipeline_receipt_note),
    ])

    return """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
<meta name="theme-color" content="#0a0e14"><title>Quant Engine — a11oy</title>
<style>
 :root{color-scheme:dark} *{box-sizing:border-box}
 body{margin:0;background:#0a0e14;color:#e6edf3;font:16px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
   padding:max(16px,env(safe-area-inset-top)) 16px calc(24px + env(safe-area-inset-bottom))}
 header,section{max-width:1040px;margin:0 auto}
 h1{font-size:clamp(1.4rem,5vw,2rem);margin:0 0 6px}
 h2{font-size:1.05rem;margin:22px auto 10px;max-width:1040px;color:#9fd0ff}
 .summary{font-weight:700;font-size:1.02rem;color:#42d392;margin:0 0 4px}
 .sub{color:#9aa7b4;font-size:.85rem;margin:.2rem 0}
 .state{font-family:ui-monospace,monospace;font-size:.76rem;color:#6b7785;word-break:break-word}
 .grid{display:grid;gap:14px;grid-template-columns:1fr}
 @media(min-width:720px){.grid{grid-template-columns:1fr 1fr}}
 .card{background:#111722;border:1px solid #1e2a3a;border-radius:14px;padding:15px}
 .row{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:8px}
 h3{font-size:.98rem;margin:0}
 .kv{display:flex;justify-content:space-between;gap:12px;font-size:.83rem;padding:3px 0;border-bottom:1px solid #18222e}
 .kv .k{color:#9aa7b4} .kv .v{color:#e6edf3;font-family:ui-monospace,monospace;text-align:right;word-break:break-word}
 .kv .v code,.cfg code{font-size:.76rem;color:#9fd0ff} .kv .v small,.cfg small{color:#6b7785}
 .cfg{color:#c4cdd6;font-size:.78rem;margin:2px 0 6px}
 .note{color:#c4cdd6;font-size:.79rem;margin:10px 0 0}
 table.vt{display:block;max-width:1040px;margin:0 auto;border-collapse:collapse;font-size:.82rem;overflow-x:auto}
 table.vt th,table.vt td{text-align:left;padding:7px 8px;border-bottom:1px solid #18222e;vertical-align:top}
 table.vt th{color:#9aa7b4;font-weight:600} table.vt td.ds{color:#c9a227} table.vt td.ms{color:#9aa7b4}
 footer{max-width:1040px;margin:22px auto 0;color:#6b7785;font-size:.76rem}
 .lock{font-family:ui-monospace,monospace;color:#9aa7b4}
</style></head><body>
<header>
  <h1>Sovereign Quant Engine</h1>
  <p class="summary">__SUMMARY__</p>
  <p class="sub">Three orthogonal risk signals per bar — PCA-Risk · TDA-Fracture · HJB-Kelly — with receipt state <b>__PIPE_SIG__</b>, honestly labeled <b>SAMPLE_SIGNAL · NOT_LIVE · NO_BACKTEST_VALIDATED</b>. Not a trading instruction.</p>
  <p class="state">backend=__BACKEND__ · gpu_reachable=__REACH__ · scenario=__SCEN__</p>
</header>
<h2>3-Layer Pipeline (DSSE receipt: __PIPE_SIG__)</h2>
<section class="grid">__CARDS__</section>
<h2>2-GPU Sovereign Serve · Throttle Both</h2>
<section class="grid">__TIERS__</section>
<h2>Verify the Claims — vendor statement vs bounded local receipt</h2>
<section>__VERIFY__<p class="state">__VRECEIPT__</p><p class="note">__VNOTE__</p></section>
<footer>
  <p class="lock">Doctrine __DV__ LOCKED · locked-proven=__LC__ {__LP__} · __CORPUS__ @ __KC__ · Λ = Conjecture 1 (NOT a theorem) · __SLSA__</p>
  <p>SAMPLE = honest synthetic fixture (not live) · MODELED = labeled model output (uncalibrated) · ROADMAP = wiring ready, not measured yet (never faked). Cites: Brodetsky (LinkedIn) · Ledoit-Wolf (honey.pdf) · Laloux/Bouchaud/Potters · Gidea-Katz arXiv:1703.04385 · RAPIDS/cuML · giotto-tda · Ripser++ arXiv:2003.07989.</p>
</footer>
<script src="/static/shared/szl_label_engine.js"></script>
<script>
(function(){
  function pill(label){
    var key = label;
    if (label === "ROADMAP") key = "EXPERIMENTAL";
    if (window.SZLLabels && window.SZLLabels.badgeHTML){
      return window.SZLLabels.badgeHTML(key, {label: label,
        title: (label === "SAMPLE") ? "Honest synthetic fixture — not a live feed, no backtest." :
               (label === "MODELED") ? "Labeled model output — uncalibrated, not measured." :
               (label === "LIVE") ? "Real backend wired and live." :
               (label === "NOT_MEASURED") ? "No valid execution receipt is loaded; no value is invented." :
               "Capability state reported by the live surface."});
    }
    return '<span>' + label + '</span>';
  }
  if (window.SZLLabels && window.SZLLabels.ensureStyle){ window.SZLLabels.ensureStyle(document); }
  var slots = document.querySelectorAll('.pill-slot');
  for (var i=0;i<slots.length;i++){ slots[i].innerHTML = pill(slots[i].getAttribute('data-label')); }
})();
</script>
</body></html>""" \
        .replace("__SUMMARY__", "Operational bounded quant pipeline; CPU reference measured, GPU comparison requires a kernel receipt") \
        .replace("__BACKEND__", str(backend["backend"])) \
        .replace("__REACH__", str(backend["gpu_reachable"])) \
        .replace("__SCEN__", str(pipe["scenario"])) \
        .replace("__PIPE_SIG__", pipeline_signature_state) \
        .replace("__CARDS__", cards) \
        .replace("__TIERS__", tier_cards) \
        .replace("__VERIFY__", verify_tbl) \
        .replace("__VRECEIPT__", receipt_line) \
        .replace("__VNOTE__", verify["honesty"]) \
        .replace("__DV__", d["version"]) \
        .replace("__LC__", str(d["locked_count"])) \
        .replace("__LP__", ", ".join(d["locked_proven"])) \
        .replace("__CORPUS__", d["corpus"]) \
        .replace("__KC__", d["kernel_commit"]) \
        .replace("__SLSA__", d["slsa"])


# =====================================================================================
# Registration (additive; mirrors szl_energy_sovereign.register).
# =====================================================================================
def register(app, ns: str = "a11oy") -> dict:
    from fastapi.responses import HTMLResponse, JSONResponse

    base = "/api/%s/v1/quant" % ns

    @app.get("%s/pca" % base)
    async def _q_pca(stress: bool = False):  # noqa: ANN202
        l1 = layer1_pca_risk(stress=stress)
        return JSONResponse({k: v for k, v in l1.items() if k != "_internal"})

    @app.get("%s/tda" % base)
    async def _q_tda(stress: bool = False):  # noqa: ANN202
        l2 = layer2_tda_fracture(stress=stress)
        return JSONResponse({k: v for k, v in l2.items() if k != "_internal"})

    @app.get("%s/kelly" % base)
    async def _q_kelly(stress: bool = False, gamma: float = 0.5, kappa: float = 1.0):  # noqa: ANN202
        return JSONResponse(layer3_hjb_kelly(gamma=gamma, kappa=kappa, stress=stress))

    @app.get("%s/pipeline" % base)
    async def _q_pipeline(stress: bool = False, gamma: float = 0.5, kappa: float = 1.0):  # noqa: ANN202
        return JSONResponse(run_pipeline(stress=stress, gamma=gamma, kappa=kappa))

    @app.get("%s/tiers" % base)
    async def _q_tiers():  # noqa: ANN202
        return JSONResponse(tiers_panel())

    @app.get("%s/verify-claims" % base)
    async def _q_verify():  # noqa: ANN202
        return JSONResponse(verify_claims_panel())

    @app.get("/quant", response_class=HTMLResponse)
    async def _q_panel(stress: bool = False):  # noqa: ANN202
        pipe = run_pipeline(stress=stress)
        return HTMLResponse(_html(pipe, tiers_panel(), verify_claims_panel()))

    return {"ok": True, "ns": ns,
            "routes": ["%s/pca" % base, "%s/tda" % base, "%s/kelly" % base,
                       "%s/pipeline" % base, "%s/tiers" % base, "%s/verify-claims" % base,
                       "/quant"]}


# =====================================================================================
# No-server self-test (proves the honesty gates + the math without a live GPU).
# =====================================================================================
def _selftest() -> dict:
    out: dict = {}
    # (a) Layer 1: ρ ∈ [0,1], MP edge positive, label SAMPLE.
    l1 = layer1_pca_risk()
    assert 0.0 <= l1["shrinkage_rho"] <= 1.0, l1["shrinkage_rho"]
    assert l1["marchenko_pastur"]["lambda_plus"] > 0, l1
    assert l1["label"] == SAMPLE_LABEL, l1["label"]
    out["layer1_lw_mp_honest"] = True

    # (b) Layer 2: fracture >= 0, anomaly is bool, label SAMPLE.
    l2 = layer2_tda_fracture(stress=True)
    assert l2["fracture_score_f_t"] >= 0.0, l2
    assert isinstance(l2["anomaly"], bool), l2
    assert l2["label"] == SAMPLE_LABEL, l2
    out["layer2_tda_fracture"] = {"f_t": l2["fracture_score_f_t"], "z": l2["z_score"], "anomaly": l2["anomaly"]}

    # (c) Layer 3: de-risk ratio <= ~1 when anomaly fires (variance inflated => smaller weights).
    l3 = layer3_hjb_kelly(stress=True)
    assert l3["sigma_eff_inflation"] >= 1.0, l3
    assert l3["label"] == SAMPLE_LABEL, l3
    out["layer3_kelly"] = {"inflation": l3["sigma_eff_inflation"], "derisk": l3["derisk_ratio_vs_uninflated"]}

    # (d) Pipeline produces a SIGNED receipt with the honest label embedded.
    pipe = run_pipeline()
    rc = pipe["signed_receipt"]["receipt"]
    dsse = pipe["signed_receipt"]["dsse"]
    assert rc["label"] == SAMPLE_LABEL, rc["label"]
    assert "NO_BACKTEST_VALIDATED" in rc["label"], rc["label"]
    assert dsse.get("_pae_sha256"), dsse
    # signed True (key present) OR explicit UNSIGNED honesty marker — never fabricated.
    assert dsse.get("signed") is True or "UNSIGNED" in (dsse.get("honesty") or ""), dsse
    out["pipeline_signed_receipt"] = {"signed": dsse.get("signed"), "label_ok": True}

    # (e) Tiers: NIM tier is sovereign:false; local tiers sovereign only via reachable probe.
    tp = tiers_panel()
    nim = [t for t in tp["tiers"] if t["where"] == "cloud"][0]
    assert nim["sovereign"] is False, nim
    locals_ = [t for t in tp["tiers"] if t["where"] == "gpu"]
    for t in locals_:
        assert t["sovereign"] == tp["gpu_reachable"], t
    out["tiers_sovereign_honest"] = True

    # (f) Verify-claims: without a receipt no measured number is invented.
    vc = verify_claims_panel()
    if not vc["receipt"]["loaded"]:
        assert all(r["szl_measured"] is None and r["szl_label"] == "NOT_MEASURED" for r in vc["rows"]), vc
    out["verify_claims_receipt_gate"] = True

    # (g) HTML renders, non-trivial, no forbidden raw claims.
    h = _html(pipe, tp, vc)
    assert "Sovereign Quant Engine" in h and len(h) > 3000, len(h)
    low = h.lower()
    # forbid affirmative over-claims (we DO carry honest NOT_LIVE / NO_BACKTEST labels).
    assert "100%" not in h and "guaranteed" not in low and "tamper-proof" not in low, "forbidden claim"
    out["html_bytes"] = len(h)

    out["ok"] = True
    return out


if __name__ == "__main__":
    import sys
    print(_json.dumps(_selftest(), indent=2), file=sys.stderr)
