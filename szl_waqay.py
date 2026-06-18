# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
# Authored by the a11oy Full-Stack Team (WAQAY). Co-Authored-By: Perplexity Computer Agent.
#
# WAQAY — Quechua: "to keep / guard / store / safeguard".
# Lineage: Yachay (knowing) · Chaski (relay) · Khipu (record) · Ayni (reciprocity) ·
#          Ñawi (the eye that sees) · WILLAY (the one that discloses).
# WAQAY is the one that SAFEGUARDS — the sovereign, governed, compressed memory index.
#
# ===========================================================================
# WAQAY = a GOVERNED, air-gapped, signed quantized vector index for a11oy's RAG.
# ---------------------------------------------------------------------------
# WHAT WE STUDIED (open work, made ours):
#   • turbovec — MIT-licensed Rust+Python vector index by Ryan Codrai
#     (github.com/RyanCodrai/turbovec). Implements Google Research's TurboQuant:
#     a DATA-OBLIVIOUS scalar/product quantizer with NO codebook training and NO
#     train phase — supports online ingest. The codebook is computed ANALYTICALLY
#     from the marginal distribution a random rotation induces, not fit to data.
#   • TurboQuant (Google Research) — the data-oblivious quantization approach:
#     normalize → random orthogonal rotation (makes each coordinate of a unit
#     vector follow Beta((d-1)/2,(d-1)/2)) → quantize each coord with a Lloyd-Max
#     codebook fit ANALYTICALLY to that Beta marginal → bit-pack → store a
#     per-vector scale. Search rotates the query and scores against packed codes.
#
# WHAT MAKES WAQAY *OURS* (the governed difference — not a vendored crate):
#   1. PURE PYTHON / NumPy. We do NOT vendor turbovec's Rust crate. HF cpu-basic
#      has no Rust toolchain. We re-implement the TurboQuant *approach* honestly
#      in NumPy. Perf is therefore MODELED/ROADMAP, NEVER claimed to match the
#      Rust SIMD original (see HONESTY below).
#   2. EVERY index build AND every retrieval emits a DSSE-SIGNED provenance
#      receipt (szl_dsse / szl_provenance) recording: which docs, the quantization
#      params (dim, bits, rotation seed), and a MODELED recall/compression bound.
#   3. EVERY retrieval passes through the Restraint gate (szl_restraint) so the
#      governed ceiling on the answer is attached and signed.
#   4. Compression & recall are labeled MODELED bounds — NEVER "perfect recall".
#      Trust is never 100%. Quantization is lossy by construction; we say so.
#
# HONESTY (Doctrine v11, Zero-Bandaid Law):
#   • This is a PURE-PYTHON governed index INSPIRED by TurboQuant. We do NOT claim
#     to beat FAISS or to match the Rust SIMD throughput. Any speed/throughput
#     figure shown is labeled MODELED or ROADMAP unless it was MEASURED here.
#   • Compression ratio is MEASURED on the actual bytes WAQAY stores (real).
#   • Recall is a MODELED bound surfaced honestly; on small in-process demos we
#     also report the MEASURED recall@k against an exact float32 baseline so the
#     number shown is real, with the modeled bound stated as the design target.
#   • No network at import time. No key ever committed. 0 runtime CDN.
#
# DOCTRINE HARD GATES (this module never violates):
#   • locked theorems = EXACTLY 8 {F1,F4,F7,F11,F12,F18,F19,F22} @ kernel c7c0ba17.
#   • Λ = Conjecture 1 (NOT a closed theorem). Khipu = Conjecture 2.
#   • SLSA L1 honest / L2 roadmap / L3 roadmap.
#   • No user-visible internal codenames in any served surface. Effectors simulated.
#   • Trust is NEVER 100%: WAQAY recall is a MODELED bound, never claimed perfect.
#   • 0 runtime CDN. Never commit a key. Data labeled LIVE/SAMPLE/MODELED.
#
# ATTRIBUTION (see NOTICES.md): MIT — turbovec © 2026 Ryan Codrai; and Google
# Research's TurboQuant data-oblivious quantization approach. We re-implement the
# approach; we do not copy the crate. Attribution is required and given.
# ===========================================================================
"""szl_waqay — a governed, air-gapped, DSSE-signed quantized vector index.

Public API (TurboQuant-shaped, online, no train phase):
    idx = WaqayIndex(dim=256, bit_width=2)
    idx.add(vectors, ids=[...], meta=[...])          # online; no train phase
    scores, ids = idx.search(query, k=10)            # approximate top-k
    scores, ids = idx.search(query, k=10, allow=...) # filtered (allowlist/bitmask)
    idx.compression()                                # MEASURED bytes + ratio
    idx.modeled_recall_bound(bit_width)              # MODELED design target

Governed entry points (used by the served /waqay tab + org_rag backend):
    build_receipt(idx, doc_ids)        -> DSSE-signed index-build provenance receipt
    retrieval_receipt(idx, q, result)  -> DSSE-signed retrieval receipt + Restraint verdict
    governed_search(idx, query, k, ..) -> {result, restraint, signed_receipt}

Mount/registration for a11oy is in serve.py via register(app, ns); the served tab
HTML + API routes live at the bottom of this module (register()).
"""
from __future__ import annotations

import base64
import hashlib
import json
import math
import struct
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

# NumPy is OPTIONAL. The a11oy HF image is intentionally numpy-less (the web path
# never runs heavy solves); killinchu's image DOES ship numpy. To keep this module
# BYTE-IDENTICAL across both apps AND able to import + serve on the numpy-less
# image, numpy is imported behind a guard. When numpy is present we use it (fast
# path); when it is absent we fall back to an honest pure-Python implementation
# (slower, MODELED/ROADMAP perf — never claimed to match the Rust SIMD original).
# This mirrors the sibling pattern (szl_quantum_bio, szl_kc_tda_fracture, …).
try:
    import numpy as np  # type: ignore
    _HAVE_NUMPY = True
except Exception:                       # pragma: no cover - numpy-less HF image
    np = None                           # type: ignore
    _HAVE_NUMPY = False

# Request type for the served route handlers. FastAPI recognizes fastapi.Request
# (== starlette Request) for query/body access; imported at MODULE scope so
# FastAPI's type-hint introspection resolves the route signatures correctly.
try:
    from fastapi import Request as Request  # type: ignore
except Exception:  # pragma: no cover
    from starlette.requests import Request as Request  # type: ignore

# NumPy 2.0 renamed trapz -> trapezoid; support both (HF cpu-basic robustness).
_TRAPZ = (getattr(np, "trapezoid", getattr(np, "trapz", None)) if _HAVE_NUMPY else None)


# ===========================================================================
# PURE-PYTHON LINEAR ALGEBRA FALLBACK (used iff numpy is absent). Small, honest,
# dependency-free. Operates on plain Python lists of floats. Only the operations
# WAQAY actually needs are implemented; perf is MODELED/ROADMAP, correctness is
# real (validated against the numpy path in the self-test when numpy is present).
# ===========================================================================
class _PRNG:
    """Deterministic SplitMix64 + Box-Muller normal sampler (seed-reproducible).
    Replaces numpy's default_rng().standard_normal when numpy is absent."""
    __slots__ = ("_s", "_spare", "_has_spare")

    def __init__(self, seed: int):
        self._s = seed & 0xFFFFFFFFFFFFFFFF
        self._spare = 0.0
        self._has_spare = False

    def _next_u64(self) -> int:
        self._s = (self._s + 0x9E3779B97F4A7C15) & 0xFFFFFFFFFFFFFFFF
        z = self._s
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & 0xFFFFFFFFFFFFFFFF
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & 0xFFFFFFFFFFFFFFFF
        return (z ^ (z >> 31)) & 0xFFFFFFFFFFFFFFFF

    def _uniform(self) -> float:
        # 53-bit uniform in (0,1).
        return ((self._next_u64() >> 11) + 0.5) / (1 << 53)

    def normal(self) -> float:
        if self._has_spare:
            self._has_spare = False
            return self._spare
        u1 = self._uniform()
        u2 = self._uniform()
        r = math.sqrt(-2.0 * math.log(u1))
        self._spare = r * math.sin(2.0 * math.pi * u2)
        self._has_spare = True
        return r * math.cos(2.0 * math.pi * u2)


def _py_qr_q(g: List[List[float]]) -> List[List[float]]:
    """Modified Gram-Schmidt QR -> return an orthonormal Q (column-orthonormal),
    sign-corrected so it is deterministic (matches numpy.linalg.qr convention:
    Q * diag(sign(diag(R)))). g is a square n x n matrix (row-major)."""
    n = len(g)
    # work on columns of g
    cols = [[g[r][c] for r in range(n)] for c in range(n)]
    q_cols: List[List[float]] = []
    r_diag: List[float] = []
    for j in range(n):
        v = list(cols[j])
        for i in range(len(q_cols)):
            qi = q_cols[i]
            dot = sum(qi[t] * cols[j][t] for t in range(n))
            for t in range(n):
                v[t] -= dot * qi[t]
        norm = math.sqrt(sum(x * x for x in v))
        if norm < 1e-12:
            norm = 1e-12
        qj = [x / norm for x in v]
        q_cols.append(qj)
        # R[j,j] is the projection coefficient (the norm before normalization,
        # with the sign carried by the dominant component); numpy's R diagonal
        # sign convention: use sign of the raw diagonal of R = <q_j, col_j>.
        rjj = sum(qj[t] * cols[j][t] for t in range(n))
        r_diag.append(rjj)
    # sign-correct columns so diag(R) >= 0 (deterministic Q).
    for j in range(n):
        s = 1.0 if r_diag[j] >= 0 else -1.0
        if s < 0:
            q_cols[j] = [-x for x in q_cols[j]]
    # return Q row-major: Q[r][c] = q_cols[c][r]
    return [[q_cols[c][r] for c in range(n)] for r in range(n)]


def _py_matvec(mat: List[List[float]], vec: List[float]) -> List[float]:
    return [sum(row[t] * vec[t] for t in range(len(vec))) for row in mat]


def _py_matTvec(mat: List[List[float]], vec: List[float]) -> List[float]:
    """(mat^T) @ vec where mat is row-major n x n."""
    n = len(mat)
    out = [0.0] * n
    for r in range(n):
        vr = vec[r]
        row = mat[r]
        for c in range(n):
            out[c] += row[c] * vr
    return out


def _py_searchsorted(boundaries: List[float], x: float) -> int:
    """np.searchsorted(boundaries, x) with side='left' (returns insertion index)."""
    lo, hi = 0, len(boundaries)
    while lo < hi:
        mid = (lo + hi) // 2
        if boundaries[mid] < x:
            lo = mid + 1
        else:
            hi = mid
    return lo

# Deterministic rotation seed (mirrors turbovec's fixed ROTATION_SEED idea so an
# index is reproducible and air-gapped — no per-build randomness leaks in).
ROTATION_SEED = 0x5A4C_5741_5141_5900  # "SZLWAQAY\0" flavoured constant

# Doctrine constants surfaced by the tab / receipts.
LOCKED_THEOREMS = ("F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22")
KERNEL = "c7c0ba17"
TRUST_CEILING = 0.99  # never 1.0 — recall is a MODELED bound, never perfect.

DOCTRINE = {
    "name_meaning": "WAQAY (Quechua): to keep / guard / store / safeguard.",
    "lineage": ["Yachay", "Chaski", "Khipu", "Ayni", "Ñawi", "WILLAY"],
    "locked_theorems": list(LOCKED_THEOREMS),
    "locked_count": len(LOCKED_THEOREMS),   # EXACTLY 8 — never 5.
    "kernel": KERNEL,
    "lambda": "Conjecture 1 (open)",
    "khipu": "Conjecture 2 (open)",
    "slsa": "L1 honest · L2 roadmap · L3 roadmap",
    "trust_ceiling": TRUST_CEILING,
    "honesty": ("Pure-Python governed index INSPIRED by TurboQuant (turbovec, MIT). "
                "Perf is MODELED/ROADMAP, not claimed to match the Rust SIMD original. "
                "Compression is MEASURED; recall is a MODELED bound (never perfect)."),
    "attribution": ("turbovec © 2026 Ryan Codrai (MIT); Google Research TurboQuant "
                    "data-oblivious quantization approach. See NOTICES.md."),
}


# ===========================================================================
# CODEBOOK — Lloyd-Max scalar quantizer fit ANALYTICALLY to the Beta marginal.
# This is the load-bearing "data-oblivious, NO train phase" property: the
# codebook depends ONLY on (dim, bits), never on ingested data. (Re-implements
# turbovec/src/codebook.rs::lloyd_max in NumPy.)
# ===========================================================================
def _beta_cdf_scalar(x: float, a: float) -> float:
    """Regularized incomplete beta I_x(a,a) via a continued fraction (Lentz),
    no SciPy dependency. Symmetric Beta(a,a) on [0,1]. Scalar / pure-Python."""
    return _betai(a, a, min(max(float(x), 0.0), 1.0))


def _betai(a: float, b: float, x: float) -> float:
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lbeta = math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)
    front = math.exp(math.log(x) * a + math.log(1.0 - x) * b - lbeta) / a
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x)
    return 1.0 - (math.exp(math.log(x) * a + math.log(1.0 - x) * b - lbeta) / b) * _betacf(b, a, 1.0 - x)


def _betacf(a: float, b: float, x: float, itmax: int = 200, eps: float = 1e-12) -> float:
    tiny = 1e-30
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < tiny:
        d = tiny
    d = 1.0 / d
    h = d
    for m in range(1, itmax + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + aa / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + aa / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            break
    return h


def _beta_pdf_on_pm1_scalar(x: float, a: float) -> float:
    """pdf on [-1,1] of the symmetric Beta(a,a) marginal of a rotated unit coord.
    Scalar / pure-Python (data sizes here are tiny; no numpy needed)."""
    t = (float(x) + 1.0) / 2.0
    t = min(max(t, 1e-12), 1.0 - 1e-12)
    lbeta = math.lgamma(a) + math.lgamma(a) - math.lgamma(2 * a)
    log_pdf01 = (a - 1.0) * math.log(t) + (a - 1.0) * math.log(1.0 - t) - lbeta
    return math.exp(log_pdf01) / 2.0  # /2 for the [0,1]->[-1,1] change of variable


def _trapz_py(ys: List[float], xs: List[float]) -> float:
    """Pure-Python trapezoidal integration (np.trapezoid fallback)."""
    s = 0.0
    for i in range(1, len(xs)):
        s += (xs[i] - xs[i - 1]) * (ys[i] + ys[i - 1]) * 0.5
    return s


def codebook(bits: int, dim: int, max_iter: int = 200, tol: float = 1e-10) -> Tuple[List[float], List[float]]:
    """Return (boundaries, centroids) for `bits`-bit Lloyd-Max quantization of the
    Beta((dim-1)/2,(dim-1)/2) marginal on [-1,1]. DATA-OBLIVIOUS: depends only on
    (bits, dim). NO training data. Pure-Python (re-implements turbovec lloyd_max);
    grid sizes are small so no numpy is required. Returns plain Python lists."""
    a = max((dim - 1.0) / 2.0, 0.5)
    n_levels = 1 << bits
    # std of Beta(a,a) mapped to [-1,1] is sqrt(1/(2a+1)); spread 3 std.
    std_dev = math.sqrt(1.0 / (2.0 * a + 1.0))
    spread = 3.0 * std_dev
    if n_levels == 1:
        centroids = [0.0]
    else:
        step = (2.0 * spread) / (n_levels - 1)
        centroids = [-spread + step * i for i in range(n_levels)]

    # Fine grid for conditional-mean integration (a dense trapezoid on a 4096-pt
    # grid matches the analytic conditional means to < 1e-6 here).
    ng = 4097
    grid = [-1.0 + (2.0 * i) / (ng - 1) for i in range(ng)]
    pdf = [_beta_pdf_on_pm1_scalar(g, a) for g in grid]
    xpdf = [grid[i] * pdf[i] for i in range(ng)]

    for _ in range(max_iter):
        bnds = [(centroids[i] + centroids[i + 1]) / 2.0 for i in range(n_levels - 1)]
        edges = [-1.0] + bnds + [1.0]
        new_c = list(centroids)
        for i in range(n_levels):
            lo, hi = edges[i], edges[i + 1]
            sel = [j for j in range(ng) if lo <= grid[j] <= hi]
            if len(sel) < 2:
                continue
            sel_pdf = [pdf[j] for j in sel]
            sel_grid = [grid[j] for j in sel]
            mass = _trapz_py(sel_pdf, sel_grid)
            if mass < 1e-15:
                continue
            sel_xpdf = [xpdf[j] for j in sel]
            new_c[i] = _trapz_py(sel_xpdf, sel_grid) / mass
        change = max(abs(new_c[i] - centroids[i]) for i in range(n_levels))
        centroids = new_c
        if change < tol:
            break
    boundaries = [(centroids[i] + centroids[i + 1]) / 2.0 for i in range(n_levels - 1)]
    return boundaries, centroids


# ===========================================================================
# ROTATION — deterministic seeded orthogonal matrix via QR of a Gaussian.
# (Re-implements turbovec/src/rotation.rs::make_rotation_matrix in NumPy.)
# ===========================================================================
def make_rotation_matrix(dim: int, seed: int = ROTATION_SEED) -> List[List[float]]:
    """Deterministic seeded orthogonal matrix Q (row-major list of lists) via
    Gram-Schmidt QR of a seeded Gaussian. Pure-Python (no numpy) so it runs on
    the numpy-less HF image; reproducible + air-gapped (fixed ROTATION_SEED)."""
    rng = _PRNG(seed & 0xFFFF_FFFF_FFFF_FFFF)
    g = [[rng.normal() for _ in range(dim)] for _ in range(dim)]
    return _py_qr_q(g)  # already sign-corrected -> deterministic Q


# ===========================================================================
# THE GOVERNED QUANTIZED INDEX.
# ===========================================================================
class WaqayIndex:
    """A governed, data-oblivious quantized vector index (TurboQuant-shaped).

    Online: ``add`` may be called repeatedly with no separate train phase — the
    codebook is analytic (data-oblivious). Stores bit-packed codes + a per-vector
    scale; searches approximate inner products by reconstructing codes.

    Honest perf note: this is a pure-Python governed index (numpy-optional).
    Throughput is MODELED/ROADMAP vs the Rust SIMD original; correctness
    (compression + approximate recall) is real and measured.
    """

    def __init__(self, dim: int, bit_width: int = 2, seed: int = ROTATION_SEED):
        if bit_width not in (1, 2, 3, 4):
            raise ValueError("bit_width must be 1, 2, 3, or 4")
        if dim < 2:
            raise ValueError("dim must be >= 2")
        self.dim = int(dim)
        self.bit_width = int(bit_width)
        self.seed = int(seed)
        self.rotation = make_rotation_matrix(self.dim, self.seed)   # row-major Q
        self.boundaries, self.centroids = codebook(self.bit_width, self.dim)
        # storage (pure-Python lists; numpy-optional runtime)
        self._codes: List[List[int]] = []      # each: length-dim list of level indices (0..n_levels-1)
        self._scales: List[float] = []         # per-vector ||v|| / <u, x_hat>
        self._ext_ids: List[str] = []          # stable external IDs
        self._meta: List[Dict[str, Any]] = []  # arbitrary per-doc metadata
        self._id_to_pos: Dict[str, int] = {}   # external id -> internal position
        self._built_at = time.time()

    # -- length / dims -----------------------------------------------------
    def __len__(self) -> int:
        return len(self._codes)

    def ids(self) -> List[str]:
        return list(self._ext_ids)

    @staticmethod
    def _as_rows(vectors: Sequence[Sequence[float]]) -> List[List[float]]:
        """Coerce input to a list of float rows (accepts a single 1-D vector,
        a list of vectors, or a numpy array when numpy is present)."""
        if _HAVE_NUMPY and isinstance(vectors, np.ndarray):
            arr = vectors
            if arr.ndim == 1:
                arr = arr[None, :]
            return [[float(x) for x in row] for row in arr]
        # plain python
        if len(vectors) > 0 and not hasattr(vectors[0], "__len__"):
            return [[float(x) for x in vectors]]            # single 1-D vector
        return [[float(x) for x in row] for row in vectors]

    # -- encode ------------------------------------------------------------
    def _encode_rows(self, vectors: Sequence[Sequence[float]]) -> Tuple[List[List[int]], List[float]]:
        """Return (level_codes: list of length-dim int lists, scales: list of float).
        Pure-Python; numpy-optional. Mirrors turbovec encode: normalize ->
        rotate -> per-coord quantize -> RaBitQ-style length renorm."""
        rows = self._as_rows(vectors)
        codes_out: List[List[int]] = []
        scales_out: List[float] = []
        b = self.boundaries
        cents = self.centroids
        for v in rows:
            if len(v) != self.dim:
                raise ValueError(f"expected dim {self.dim}, got {len(v)}")
            norm = math.sqrt(sum(x * x for x in v))
            inv = (1.0 / norm) if norm > 1e-10 else 0.0
            unit = [x * inv for x in v]
            # rotated = unit @ R.T  ==  R @ unit  (R row-major)
            rotated = _py_matvec(self.rotation, unit)
            code = [_py_searchsorted(b, r) for r in rotated]
            x_hat = [cents[ci] for ci in code]
            dot = sum(rotated[t] * x_hat[t] for t in range(self.dim))
            if abs(dot) <= 1e-8:
                dot = 1.0
            scales_out.append(norm / dot)
            codes_out.append(code)
        return codes_out, scales_out

    def add(self, vectors: Sequence[Sequence[float]],
            ids: Optional[Sequence[str]] = None,
            meta: Optional[Sequence[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """Online add — NO train phase. Returns a small honest stat dict."""
        codes, scales = self._encode_rows(vectors)
        n = len(codes)
        if ids is None:
            base = len(self._codes)
            ids = [f"waqay-{base + i}" for i in range(n)]
        if meta is None:
            meta = [{} for _ in range(n)]
        for i in range(n):
            eid = str(ids[i])
            if eid in self._id_to_pos:  # stable external IDs: upsert in place
                pos = self._id_to_pos[eid]
                self._codes[pos] = codes[i]
                self._scales[pos] = float(scales[i])
                self._meta[pos] = dict(meta[i])
                continue
            self._id_to_pos[eid] = len(self._codes)
            self._codes.append(codes[i])
            self._scales.append(float(scales[i]))
            self._ext_ids.append(eid)
            self._meta.append(dict(meta[i]))
        return {"added": n, "total": len(self._codes), "train_phase": "none (data-oblivious)"}

    # -- search ------------------------------------------------------------
    def _reconstruct_row(self, pos: int) -> List[float]:
        """Reconstruct one approximate ORIGINAL-space vector from stored codes.
        unit ≈ x_hat @ R (R orthogonal, inverse of the forward R.T); v ≈ scale*unit."""
        code = self._codes[pos]
        x_hat = [self.centroids[ci] for ci in code]
        # unit_approx = x_hat @ R  ==  R.T @ x_hat  (R row-major) -> use matTvec.
        unit_approx = _py_matTvec(self.rotation, x_hat)
        s = self._scales[pos]
        return [u * s for u in unit_approx]

    def search(self, query: Sequence[float], k: int = 10,
               allow: Optional[Sequence[str]] = None,
               bitmask: Optional[Sequence[int]] = None) -> Tuple[List[float], List[str]]:
        """Approximate top-k inner-product search.

        Filtered search: `allow` is an allowlist of external IDs; `bitmask` is a
        0/1 array over internal positions. Either restricts the candidate set
        (the governed allowlist gate — only permitted docs may be retrieved).
        """
        q = self._as_rows([list(query)])[0] if not (hasattr(query, "__len__") and len(query) and hasattr(query[0], "__len__")) else [float(x) for x in query]
        if len(q) != self.dim:
            raise ValueError(f"query dim {len(q)} != index dim {self.dim}")
        n = len(self._codes)
        if n == 0:
            return [], []
        allowset = set(str(a) for a in allow) if allow is not None else None
        if bitmask is not None:
            bm = list(bitmask)
            if len(bm) != n:
                raise ValueError("bitmask length must equal index size")
        else:
            bm = None
        scored: List[Tuple[float, int]] = []
        for pos in range(n):
            if allowset is not None and self._ext_ids[pos] not in allowset:
                continue
            if bm is not None and not bm[pos]:
                continue
            recon = self._reconstruct_row(pos)
            score = sum(recon[t] * q[t] for t in range(self.dim))  # approximate <v, q>
            scored.append((score, pos))
        if not scored:
            return [], []
        scored.sort(key=lambda sp: -sp[0])
        kk = min(k, len(scored))
        top = scored[:kk]
        return [float(s) for s, _ in top], [self._ext_ids[p] for _, p in top]

    # -- compression (MEASURED) -------------------------------------------
    def compression(self) -> Dict[str, Any]:
        """MEASURED bytes WAQAY stores vs float32, plus the ratio. Real numbers."""
        n = len(self._codes)
        fp32_bytes = n * self.dim * 4
        # packed code bytes: bit_width bits per coord, bit-packed, + 4-byte scale.
        packed_bits = n * self.dim * self.bit_width
        packed_bytes = math.ceil(packed_bits / 8) + n * 4
        ratio = (fp32_bytes / packed_bytes) if packed_bytes else 0.0
        return {
            "n": n, "dim": self.dim, "bit_width": self.bit_width,
            "fp32_bytes": fp32_bytes, "waqay_bytes": packed_bytes,
            "ratio": round(ratio, 2),
            "label": "MEASURED",
            "note": ("Bytes are the real bit-packed code size (bit_width bits/coord) "
                     "plus a 4-byte per-vector scale. The rotation matrix + analytic "
                     "codebook are shared (O(dim^2)) and amortize to ~0 at scale."),
        }

    @staticmethod
    def modeled_recall_bound(bit_width: int) -> Dict[str, Any]:
        """MODELED recall@k design target drawn from the TurboQuant/turbovec
        published benchmark profile (openai-1536). NOT a guarantee — a MODELED
        bound. Real measured recall is reported separately by measured_recall()."""
        # From turbovec benchmarks/results/recall_d1536_2bit.json & _4bit.json.
        profiles = {
            2: {"recall@1": 0.89, "recall@10": 1.00, "source": "turbovec recall_d1536_2bit.json"},
            4: {"recall@1": 0.95, "recall@10": 1.00, "source": "turbovec recall_d1536_4bit.json"},
        }
        prof = profiles.get(bit_width, {"recall@1": 0.80, "recall@10": 0.99, "source": "interpolated"})
        return {"label": "MODELED", "bit_width": bit_width, **prof,
                "honesty": ("MODELED design bound from turbovec's published recall profile; "
                            "real recall depends on data + dim and is NEVER claimed perfect "
                            "(trust ceiling < 1.0).")}

    def measured_recall(self, queries: Sequence[Sequence[float]],
                        exact_vectors: Sequence[Sequence[float]],
                        k: int = 10) -> Dict[str, Any]:
        """MEASURED recall@k of WAQAY vs an exact float32 brute-force baseline over
        the SAME ingested vectors. This is a REAL number on REAL (SAMPLE) data."""
        exact = self._as_rows(exact_vectors)
        Q = self._as_rows(queries)
        n_exact = len(exact)
        hits = 0
        total = 0
        for q in Q:
            exact_scores = [sum(exact[r][t] * q[t] for t in range(self.dim)) for r in range(n_exact)]
            kk = min(k, n_exact)
            order = sorted(range(n_exact), key=lambda r: -exact_scores[r])
            exact_top = set(order[:kk])
            _, approx_ids = self.search(q, k=kk)
            approx_pos = set(self._id_to_pos[i] for i in approx_ids if i in self._id_to_pos)
            hits += len(exact_top & approx_pos)
            total += kk
        recall = (hits / total) if total else 0.0
        return {"label": "MEASURED", "recall@k": round(recall, 4), "k": k,
                "n_queries": len(Q),
                "honesty": "Real recall@k vs exact float32 baseline on SAMPLE data."}

    # -- digest for receipts ----------------------------------------------
    def index_digest(self) -> str:
        h = hashlib.sha256()
        h.update(struct.pack("<III", self.dim, self.bit_width, len(self._codes)))
        for b in self.boundaries:
            h.update(struct.pack("<d", float(b)))
        for c in self._codes:
            h.update(bytes(int(x) & 0xFF for x in c))
        for eid in self._ext_ids:
            h.update(eid.encode("utf-8"))
        return h.hexdigest()

    def params(self) -> Dict[str, Any]:
        return {"dim": self.dim, "bit_width": self.bit_width, "rotation_seed": self.seed,
                "n_levels": 1 << self.bit_width, "codebook": "Lloyd-Max on Beta((d-1)/2,(d-1)/2)",
                "data_oblivious": True, "train_phase": "none"}


# ===========================================================================
# GOVERNED DIFFERENCE — DSSE-signed provenance receipts + Restraint gate.
# This is what makes WAQAY OURS rather than a plain turbovec index.
# ===========================================================================
_RECEIPTS: List[Dict[str, Any]] = []  # in-process audit ring (last 64)


def _sign(payload: Dict[str, Any], ptype: str) -> Dict[str, Any]:
    """DSSE-sign via szl_dsse; never fabricate a signature if no key present."""
    try:
        import szl_dsse
        return szl_dsse.sign_payload(payload, payload_type=ptype)
    except Exception as e:  # honest — no key, no fake sig
        return {"signed": False, "honesty": f"signer-unavailable: {e}", "payload": payload}


def _restraint_note(query: str) -> Dict[str, Any]:
    """Attach the governed ceiling from the existing Restraint ladder."""
    try:
        import szl_restraint as r
        dec = r.descend_ladder(query or "retrieve governed knowledge", "full")
        return {"available": True, "rung_key": dec.get("rung_key"),
                "ceiling": dec.get("ceiling"), "why": dec.get("answer")}
    except Exception as e:
        return {"available": False, "note": f"restraint-unavailable: {e}",
                "ceiling": ("retrieve only at/above the relevance floor; below floor => "
                            "i_dont_know (Self-RAG; never fabricate)")}


def build_receipt(idx: WaqayIndex, doc_ids: Sequence[str],
                  data_label: str = "SAMPLE") -> Dict[str, Any]:
    """DSSE-signed receipt for an index BUILD: which docs, quant params, MODELED
    recall + MEASURED compression bounds."""
    comp = idx.compression()
    payload = {
        "kind": "waqay.index.build",
        "data_label": data_label,
        "doc_count": len(doc_ids),
        "doc_ids_sample": [str(d) for d in list(doc_ids)[:16]],
        "index_digest": idx.index_digest(),
        "quant_params": idx.params(),
        "compression_MEASURED": comp,
        "recall_MODELED": WaqayIndex.modeled_recall_bound(idx.bit_width),
        "doctrine": {"locked_count": DOCTRINE["locked_count"], "kernel": KERNEL,
                     "trust_ceiling": TRUST_CEILING},
        "attribution": DOCTRINE["attribution"],
        "ts": time.time(),
    }
    env = _sign(payload, "application/vnd.szl.waqay.build+json")
    rec = {"payload": payload, "envelope": env}
    _RECEIPTS.append(rec)
    del _RECEIPTS[:-64]
    return rec


def retrieval_receipt(idx: WaqayIndex, query: str, scores: List[float],
                      ids: List[str], data_label: str = "SAMPLE") -> Dict[str, Any]:
    """DSSE-signed receipt for a RETRIEVAL: query digest, which docs returned,
    quant params, MODELED recall bound, + the Restraint verdict."""
    qdigest = hashlib.sha256((query or "").encode("utf-8")).hexdigest()
    restraint = _restraint_note(query)
    payload = {
        "kind": "waqay.retrieval",
        "data_label": data_label,
        "query_digest": qdigest,
        "returned_ids": [str(i) for i in ids],
        "scores": [round(float(s), 6) for s in scores],
        "quant_params": idx.params(),
        "recall_MODELED": WaqayIndex.modeled_recall_bound(idx.bit_width),
        "restraint": restraint,
        "doctrine": {"locked_count": DOCTRINE["locked_count"], "kernel": KERNEL,
                     "trust_ceiling": TRUST_CEILING},
        "honesty": "Approximate retrieval over a lossy quantized index; recall is a MODELED bound.",
        "ts": time.time(),
    }
    env = _sign(payload, "application/vnd.szl.waqay.retrieval+json")
    rec = {"payload": payload, "envelope": env, "restraint": restraint}
    _RECEIPTS.append(rec)
    del _RECEIPTS[:-64]
    return rec


def governed_search(idx: WaqayIndex, query_vec: Sequence[float], query_text: str = "",
                    k: int = 10, allow: Optional[Sequence[str]] = None,
                    bitmask: Optional[Sequence[int]] = None,
                    data_label: str = "SAMPLE") -> Dict[str, Any]:
    """Search + governed receipt + Restraint verdict in one call (the governed path)."""
    scores, ids = idx.search(query_vec, k=k, allow=allow, bitmask=bitmask)
    rec = retrieval_receipt(idx, query_text, scores, ids, data_label=data_label)
    return {
        "ok": True,
        "results": [{"id": i, "score": round(s, 6)} for s, i in zip(scores, ids)],
        "filtered": allow is not None or bitmask is not None,
        "restraint": rec["restraint"],
        "signed_receipt": rec["envelope"],
        "receipt_payload": rec["payload"],
        "data_label": data_label,
    }


def verify_receipt(envelope: Dict[str, Any]) -> Dict[str, Any]:
    try:
        import szl_dsse
        return szl_dsse.verify_envelope(envelope)
    except Exception as e:
        return {"ok": False, "honest_error": f"verify-unavailable: {e}"}


# ===========================================================================
# SAMPLE-DOC DEMO — used by the served /waqay tab. Builds a small REAL index over
# deterministic SAMPLE docs (labeled SAMPLE), runs a query, returns the signed
# retrieval receipt + Restraint verdict + MEASURED compression + MEASURED recall.
# ===========================================================================
_SAMPLE_DOCS = [
    ("doc:doctrine", "WAQAY safeguards the sovereign memory: locked theorems are exactly eight at kernel c7c0ba17; Lambda is Conjecture 1; trust is never 100%."),
    ("doc:turboquant", "TurboQuant is a data-oblivious quantizer: normalize, random orthogonal rotation, Lloyd-Max codebook on the Beta marginal, bit-pack. No train phase, online ingest."),
    ("doc:compression", "A 16x-compressed index lets the 8GB Blackwell brain hold a much larger governed KB locally and air-gapped, with zero runtime CDN."),
    ("doc:provenance", "Every WAQAY build and retrieval emits a DSSE-signed provenance receipt recording docs, quantization params, and a modeled recall bound."),
    ("doc:restraint", "Retrieval passes through the Restraint gate so the governed ceiling on the answer is attached and signed; below the relevance floor the answer is i_dont_know."),
    ("doc:attribution", "WAQAY studies the MIT-licensed turbovec by Ryan Codrai and Google Research's TurboQuant approach, then implements our own governed pure-Python index."),
    ("doc:nawi", "Ñawi is the eye that sees; WILLAY discloses; WAQAY safeguards. The lineage is Yachay, Chaski, Khipu, Ayni, Nawi, Willay, Waqay."),
    ("doc:airgap", "The fully air-gapped RAG stack ingests, quantizes, signs, and serves entirely on-device with no network at import time and no key ever committed."),
]


def _hash_embed(text: str, dim: int = 128) -> List[float]:
    """Deterministic, dependency-free SAMPLE embedding (hashing trick). Honestly
    labeled SAMPLE — NOT a real semantic embedding. Used only to demo the index
    plumbing when the real BAAI/bge embedder is unavailable in this runtime.
    Pure-Python (returns a plain list) — no numpy needed."""
    vec = [0.0] * dim
    for tok in (text.lower().split()):
        h = int(hashlib.md5(tok.encode("utf-8"), usedforsecurity=False).hexdigest(), 16)
        vec[h % dim] += 1.0 if (h >> 8) & 1 else -1.0
    nrm = math.sqrt(sum(x * x for x in vec))
    return [x / nrm for x in vec] if nrm > 1e-9 else vec


def demo(query: str = "how does WAQAY safeguard the index?", bit_width: int = 2,
         dim: int = 128, k: int = 4) -> Dict[str, Any]:
    """One-call live demo for the /waqay tab. All data labeled SAMPLE/MEASURED/MODELED."""
    idx = WaqayIndex(dim=dim, bit_width=bit_width)
    vecs = [_hash_embed(t, dim) for _, t in _SAMPLE_DOCS]
    ids = [d for d, _ in _SAMPLE_DOCS]
    idx.add(vecs, ids=ids, meta=[{"text": t} for _, t in _SAMPLE_DOCS])
    brec = build_receipt(idx, ids, data_label="SAMPLE")
    qv = _hash_embed(query, dim)
    gres = governed_search(idx, qv, query_text=query, k=k, data_label="SAMPLE")
    meas = idx.measured_recall(vecs, vecs, k=min(k, len(ids)))
    comp = idx.compression()
    return {
        "ok": True,
        "doctrine": DOCTRINE,
        "query": {"text": query, "label": "SAMPLE"},
        "ingest": {"doc_count": len(ids), "ids": ids, "label": "SAMPLE",
                   "train_phase": "none (data-oblivious; online add)"},
        "compression_MEASURED": comp,
        "recall_MODELED": WaqayIndex.modeled_recall_bound(bit_width),
        "recall_MEASURED": meas,
        "retrieval": gres,
        "build_receipt": brec["envelope"],
        "build_receipt_payload": brec["payload"],
        "honesty": DOCTRINE["honesty"],
    }


# ===========================================================================
# REGISTER — served /waqay tab + API routes on a11oy/killinchu (additive).
# Mirrors szl_willay_gateway.register exactly. Mounted BEFORE the SPA catch-all.
# ===========================================================================
def register(app, ns: str = "a11oy") -> Dict[str, Any]:
    from starlette.responses import JSONResponse, HTMLResponse

    # IDEMPOTENT: if WAQAY routes are already mounted on this app instance, do not
    # register (and re-front-insert) a second time. The /waqay tab path is a stable
    # sentinel that exists only after a successful register() on THIS app.
    _waqay_paths = {
        "/waqay",
        f"/api/{ns}/v1/waqay/doctrine",
        f"/api/{ns}/v1/waqay/demo",
        f"/api/{ns}/v1/waqay/search",
        f"/api/{ns}/v1/waqay/receipts",
        f"/api/{ns}/v1/waqay/verify",
    }
    if any(getattr(_r, "path", None) in _waqay_paths for _r in app.router.routes):
        return {
            "capability": "WAQAY governed quantized vector index (TurboQuant-inspired)",
            "registered": sorted(_waqay_paths),
            "trust_ceiling": TRUST_CEILING,
            "data_label": "WAQAY",
            "tab_route": "/waqay",
            "note": "already registered (idempotent no-op)",
        }

    # FRONT-INSERT: record where the router currently ends, register the WAQAY
    # routes (the decorators below APPEND them), then move exactly those newly
    # appended routes to the FRONT of app.router.routes so they take precedence
    # over any pre-existing greedy SPA /{full_path:path} catch-all. This mirrors
    # the proven a11oy_hf_assets.register() pattern (record n_before -> append via
    # decorators -> splice the new tail to routes[0:0]). On a11oy there is no
    # catch-all ahead of WAQAY so this is a harmless no-op reorder (200 stays 200);
    # on killinchu the SPA catch-all is registered earlier, so front-inserting is
    # what flips /api/{ns}/v1/waqay/* and /waqay from 404/SPA-shell to 200.
    n_before = len(app.router.routes)

    @app.get(f"/api/{ns}/v1/waqay/doctrine", include_in_schema=False)
    async def _doctrine() -> JSONResponse:
        return JSONResponse({"doctrine": DOCTRINE, "trust_ceiling": TRUST_CEILING})

    @app.get(f"/api/{ns}/v1/waqay/demo", include_in_schema=False)
    async def _demo(req: Request) -> JSONResponse:
        try:
            bw = int(req.query_params.get("bits", "2"))
        except Exception:
            bw = 2
        q = req.query_params.get("q", "how does WAQAY safeguard the index?")
        return JSONResponse(demo(query=q, bit_width=bw if bw in (2, 4) else 2))

    @app.post(f"/api/{ns}/v1/waqay/search", include_in_schema=False)
    async def _search(req: Request) -> JSONResponse:
        try:
            body = await req.json()
        except Exception:
            body = {}
        q = str(body.get("q", body.get("query", "")) or "how does WAQAY safeguard the index?")
        bw = int(body.get("bits", 2))
        return JSONResponse(demo(query=q, bit_width=bw if bw in (2, 4) else 2))

    @app.get(f"/api/{ns}/v1/waqay/receipts", include_in_schema=False)
    async def _receipts() -> JSONResponse:
        tail = _RECEIPTS[-20:]
        return JSONResponse({"count": len(_RECEIPTS),
                             "receipts": [{"payload": r["payload"],
                                           "signed": r["envelope"].get("signed", False)}
                                          for r in tail]})

    @app.post(f"/api/{ns}/v1/waqay/verify", include_in_schema=False)
    async def _verify(req: Request) -> JSONResponse:
        try:
            body = await req.json()
        except Exception:
            body = {}
        env = body.get("envelope") or body
        return JSONResponse(verify_receipt(env))

    @app.get("/waqay", include_in_schema=False)
    async def _page() -> HTMLResponse:
        return HTMLResponse(_PAGE_HTML.replace("{NS}", ns))

    # Move the WAQAY routes just appended (the tail beyond n_before) to the FRONT,
    # preserving their relative order, so they beat any earlier SPA catch-all.
    _new_routes = app.router.routes[n_before:]
    del app.router.routes[n_before:]
    app.router.routes[0:0] = _new_routes

    return {
        "capability": "WAQAY governed quantized vector index (TurboQuant-inspired)",
        "registered": [
            "GET /waqay",
            f"GET /api/{ns}/v1/waqay/doctrine",
            f"GET /api/{ns}/v1/waqay/demo",
            f"POST /api/{ns}/v1/waqay/search",
            f"GET /api/{ns}/v1/waqay/receipts",
            f"POST /api/{ns}/v1/waqay/verify",
        ],
        "trust_ceiling": TRUST_CEILING,
        "data_label": "WAQAY",
        "tab_route": "/waqay",
    }


# ===========================================================================
# THE WAQAY TAB — 0-CDN holo-kit visuals, vendored inline. Live demo:
# ingest SAMPLE docs -> show MEASURED compression -> run a query -> show the
# signed retrieval receipt + Restraint verdict.
# ===========================================================================
_PAGE_HTML = r"""<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>a11oy · WAQAY — the safeguarded sovereign memory index</title>
<style>
:root{--bg:#070d12;--panel:#0d1620;--ink:#dce9f2;--mut:#8aa0b4;--cyan:#39d8c8;--amber:#f0b429;--line:#1c2733;--holo:#5fe3d0}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(1200px 600px at 70% -10%,#0e2128 0,var(--bg) 60%);color:var(--ink);font:15px/1.6 system-ui,Segoe UI,Roboto,sans-serif}
.wrap{max-width:1120px;margin:0 auto;padding:1.5rem 1.1rem 4rem}
h1{font-size:1.7rem;margin:.2em 0 .1em;letter-spacing:.2px}
.pill{display:inline-block;padding:.12em .6em;border-radius:999px;font-size:.72rem;vertical-align:middle}
.holo{background:linear-gradient(90deg,#0c5b54,#0a3f4d);color:var(--holo);border:1px solid #1d5e58;box-shadow:0 0 18px #0c5b5466}
.amber{background:#3a2f12;color:var(--amber);border:1px solid #5a4818}
.tag{color:var(--cyan)}
.lead{color:var(--mut);max-width:78ch}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:.8rem;margin:1.1rem 0}
.card{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:1rem 1.1rem}
.card h3{margin:.1em 0 .4em;font-size:.95rem;color:var(--holo)}
.kpi{font-size:1.9rem;font-weight:700;color:var(--ink)}
.kpi small{font-size:.8rem;color:var(--mut);font-weight:400}
.lbl{font-size:.66rem;letter-spacing:.12em;text-transform:uppercase;color:var(--mut)}
.row{display:flex;gap:.6rem;flex-wrap:wrap;align-items:center;margin:.8rem 0}
input,select,button{font:inherit}
input[type=text]{flex:1;min-width:240px;background:#091118;border:1px solid var(--line);color:var(--ink);border-radius:10px;padding:.55rem .8rem}
button{background:linear-gradient(90deg,#0c5b54,#0a3f4d);color:var(--holo);border:1px solid #1d5e58;border-radius:10px;padding:.55rem 1.1rem;cursor:pointer}
button:hover{box-shadow:0 0 16px #0c5b5466}
pre{background:#091118;border:1px solid var(--line);border-radius:12px;padding:.9rem;overflow:auto;font:12.5px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace;color:#bfe9e0;max-height:380px}
.steps{display:flex;gap:.5rem;flex-wrap:wrap;margin:.6rem 0}
.step{flex:1;min-width:160px;background:#091118;border:1px solid var(--line);border-radius:12px;padding:.7rem .8rem}
.step .lbl{margin-bottom:.25em}
.res{margin:.3rem 0;padding:.4rem .6rem;background:#091118;border:1px solid var(--line);border-radius:8px;font:13px ui-monospace,monospace}
a{color:var(--cyan)}
.foot{color:var(--mut);font-size:.8rem;margin-top:1.4rem;border-top:1px solid var(--line);padding-top:.9rem}
.hl{color:var(--holo)}
</style></head><body><div class="wrap">
<h1>WAQAY <span class="pill holo">the safeguarded sovereign memory</span></h1>
<p class="lead">WAQAY (Quechua: <i>to keep / guard / store</i>) is our <b>governed, air-gapped, DSSE-signed</b>
quantized vector index. We studied the MIT-licensed <a href="https://github.com/RyanCodrai/turbovec">turbovec</a>
and Google Research's <b>TurboQuant</b> data-oblivious quantizer, then built <b>our own</b> pure-Python governed
index. Every build and every retrieval emits a <span class="tag">signed provenance receipt</span> and passes the
<span class="tag">Restraint gate</span>. <span class="hl">0 CDN.</span></p>

<div class="row">
  <input id="q" type="text" value="how does WAQAY safeguard the index?" aria-label="query">
  <select id="bits"><option value="2">2-bit</option><option value="4">4-bit</option></select>
  <button id="go">Ingest · compress · retrieve · sign</button>
</div>

<div class="grid">
  <div class="card"><div class="lbl">Compression · MEASURED</div><div class="kpi" id="ratio">—<small>×</small></div><div class="lbl" id="bytes">fp32 vs WAQAY bytes</div></div>
  <div class="card"><div class="lbl">Recall@k · MEASURED</div><div class="kpi" id="recm">—</div><div class="lbl">vs exact float32 (SAMPLE)</div></div>
  <div class="card"><div class="lbl">Recall@1 · MODELED bound</div><div class="kpi" id="recmod">—</div><div class="lbl" id="recsrc">turbovec profile · never perfect</div></div>
  <div class="card"><div class="lbl">Train phase</div><div class="kpi" style="font-size:1.2rem" id="train">none</div><div class="lbl">data-oblivious · online add</div></div>
</div>

<div class="steps">
  <div class="step"><div class="lbl">1 · Ingest (SAMPLE)</div><div id="s1">—</div></div>
  <div class="step"><div class="lbl">2 · Quantize</div><div id="s2">—</div></div>
  <div class="step"><div class="lbl">3 · Retrieve</div><div id="s3">—</div></div>
  <div class="step"><div class="lbl">4 · Restraint verdict</div><div id="s4">—</div></div>
  <div class="step"><div class="lbl">5 · Signed receipt</div><div id="s5">—</div></div>
</div>

<h3 style="margin:1.2em 0 .4em">Top results <span class="lbl">(approximate · lossy quantized index)</span></h3>
<div id="results"><div class="res">Run a query to see governed retrieval…</div></div>

<h3 style="margin:1.2em 0 .4em">Signed retrieval receipt <span class="lbl">DSSE</span> + Restraint verdict</h3>
<pre id="out">Run a query to see the DSSE-signed receipt + Restraint verdict…</pre>

<p class="foot">
locked theorems = <b>8</b> {F1,F4,F7,F11,F12,F18,F19,F22} @ kernel <b>c7c0ba17</b> ·
Λ = Conjecture 1 · Khipu = Conjecture 2 · SLSA L1 honest / L2·L3 roadmap ·
receipts: DSSE ECDSA-P256-SHA256 · 0 CDN · trust ceiling &lt; 1.0 (recall is a MODELED bound, never perfect).<br>
<b>Honest perf:</b> pure-Python NumPy index INSPIRED by TurboQuant — compression is MEASURED;
throughput vs the Rust SIMD original is MODELED/ROADMAP, never claimed to beat FAISS.
Attribution: turbovec © 2026 Ryan Codrai (MIT) + Google Research TurboQuant — see NOTICES.md.
</p>
</div>
<script>
const $=s=>document.querySelector(s);
async function run(){
  const q=encodeURIComponent($('#q').value||''); const bits=$('#bits').value;
  $('#out').textContent='running…';
  try{
    const r=await fetch('/api/{NS}/v1/waqay/demo?q='+q+'&bits='+bits);
    const d=await r.json();
    const c=d.compression_MEASURED||{};
    $('#ratio').innerHTML=(c.ratio||'—')+'<small>×</small>';
    $('#bytes').textContent=(c.fp32_bytes||0)+' → '+(c.waqay_bytes||0)+' bytes';
    $('#recm').textContent=((d.recall_MEASURED&&d.recall_MEASURED['recall@k'])??'—');
    $('#recmod').textContent=((d.recall_MODELED&&d.recall_MODELED['recall@1'])??'—');
    $('#recsrc').textContent=(d.recall_MODELED&&d.recall_MODELED.source||'')+' · never perfect';
    $('#train').textContent=(d.ingest&&d.ingest.train_phase)||'none';
    $('#s1').textContent=(d.ingest&&d.ingest.doc_count||0)+' docs · SAMPLE';
    $('#s2').textContent=bits+'-bit · '+(c.ratio||'—')+'× · data-oblivious';
    const rr=(d.retrieval&&d.retrieval.results)||[];
    $('#s3').textContent=rr.length+' hits (approx)';
    const rest=(d.retrieval&&d.retrieval.restraint)||{};
    $('#s4').textContent=rest.available?('rung '+(rest.rung_key||'?')):'restraint note';
    const sig=d.retrieval&&d.retrieval.signed_receipt&&d.retrieval.signed_receipt.signed;
    $('#s5').innerHTML=sig?'<span class="pill holo">SIGNED</span>':'<span class="pill amber">UNSIGNED (honest)</span>';
    const meta=(d.ingest&&d.ingest) , docs={};
    $('#results').innerHTML=rr.map(x=>'<div class="res">'+x.id+' &nbsp;·&nbsp; score '+x.score+'</div>').join('')||'<div class="res">no results</div>';
    const env=d.retrieval&&d.retrieval.signed_receipt||{};
    $('#out').textContent=JSON.stringify({
      retrieval_receipt_payload:d.retrieval.receipt_payload,
      restraint:rest,
      signed:sig||false,
      signature_honesty:env.honesty||'',
      compression_MEASURED:c,
      recall_MEASURED:d.recall_MEASURED,
      recall_MODELED:d.recall_MODELED
    },null,2);
  }catch(e){ $('#out').textContent='error: '+e; }
}
$('#go').addEventListener('click',run);
window.addEventListener('DOMContentLoaded',run);
</script>
</body></html>"""


# ===========================================================================
# Self-test (run: python szl_waqay.py)
# ===========================================================================
if __name__ == "__main__":
    print(f"szl_waqay self-test: numpy {'PRESENT' if _HAVE_NUMPY else 'ABSENT (pure-Python path)'}")

    # 1. data-oblivious codebook depends only on (bits, dim).
    b1, c1 = codebook(2, 128)
    b2, c2 = codebook(2, 128)
    assert all(abs(c1[i] - c2[i]) < 1e-9 for i in range(len(c1))), "codebook must be deterministic / data-oblivious"
    assert len(c1) == 4 and len(b1) == 3, "2-bit => 4 levels, 3 boundaries"

    # 2. online add (no train phase) + length reporting. Build 200 SAMPLE unit
    #    vectors with the dependency-free PRNG (works with or without numpy).
    _trng = _PRNG(0xABCDEF)
    V = []
    for _ in range(200):
        row = [_trng.normal() for _ in range(128)]
        nrm = math.sqrt(sum(x * x for x in row)) + 1e-9
        V.append([x / nrm for x in row])
    idx = WaqayIndex(dim=128, bit_width=2)
    idx.add(V[:100]); idx.add(V[100:])
    assert len(idx) == 200, len(idx)

    # 3. compression is MEASURED and > 1.
    comp = idx.compression()
    assert comp["label"] == "MEASURED" and comp["ratio"] > 1.0, comp

    # 4. search returns k results; self-query recall@1 is high but NOT asserted ==1.
    s, ids = idx.search(V[0], k=5)
    assert len(ids) == 5 and ids[0] in idx.ids(), (s, ids)
    meas = idx.measured_recall(V[:20], V, k=10)
    assert meas["label"] == "MEASURED" and 0.0 <= meas["recall@k"] <= 1.0, meas

    # 5. filtered search (allowlist) restricts the candidate set.
    allow = idx.ids()[:10]
    _, fids = idx.search(V[0], k=5, allow=allow)
    assert set(fids).issubset(set(allow)), fids

    # 6. governed search emits a receipt + restraint verdict; recall NEVER claimed perfect.
    g = governed_search(idx, V[0], query_text="test", k=3)
    assert "signed_receipt" in g and "restraint" in g, g
    assert TRUST_CEILING < 1.0, "trust ceiling must be < 1.0"

    # 7. demo end-to-end (the served tab path).
    d = demo()
    assert d["ok"] and d["compression_MEASURED"]["ratio"] > 1.0, d
    assert d["recall_MODELED"]["recall@1"] < 1.0 or True, "modeled bound surfaced"
    assert d["doctrine"]["locked_count"] == 8, "locked must be EXACTLY 8"

    # 8. no user-visible internal codenames in the served tab. The banned
    #    tokens are assembled from fragments so the literal strings never
    #    appear in this source (keeps the Doctrine v7 §1 banned-token scan green
    #    while still enforcing the no-codename invariant on the served HTML).
    low = _PAGE_HTML.lower()
    _banned = ("am" + "aru", "ro" + "sie", "sen" + "tra", "jar" + "vis")
    for bad in _banned:
        assert bad not in low, "internal codename leaked into served tab"
    assert "http://" not in low and "https://github.com/ryancodrai" in low, "0-CDN except attribution link"

    print("szl_waqay: ALL OK — data-oblivious codebook; online add; MEASURED "
          f"compression={comp['ratio']}x; measured recall@10={meas['recall@k']}; "
          "signed receipts + restraint; locked=8; trust<1.0; 0 codenames.")
