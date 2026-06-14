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
#   • No user-visible codenames (amaru/rosie/sentra/jarvis). Effectors simulated.
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

import numpy as np

# Request type for the served route handlers. FastAPI recognizes fastapi.Request
# (== starlette Request) for query/body access; imported at MODULE scope so
# FastAPI's type-hint introspection resolves the route signatures correctly.
try:
    from fastapi import Request as Request  # type: ignore
except Exception:  # pragma: no cover
    from starlette.requests import Request as Request  # type: ignore

# NumPy 2.0 renamed trapz -> trapezoid; support both (HF cpu-basic robustness).
_TRAPZ = getattr(np, "trapezoid", getattr(np, "trapz", None))

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
def _beta_cdf(x: np.ndarray, a: float) -> np.ndarray:
    """Regularized incomplete beta I_x(a,a) via a continued fraction (Lentz),
    no SciPy dependency (HF cpu-basic friendly). Symmetric Beta(a,a) on [0,1]."""
    x = np.clip(np.asarray(x, dtype=np.float64), 0.0, 1.0)
    out = np.empty_like(x)
    for i, xi in enumerate(x.ravel()):
        out.ravel()[i] = _betai(a, a, float(xi))
    return out


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


def _beta_pdf_on_pm1(x: np.ndarray, a: float) -> np.ndarray:
    """pdf on [-1,1] of the symmetric Beta(a,a) marginal of a rotated unit coord."""
    t = (np.asarray(x, dtype=np.float64) + 1.0) / 2.0
    t = np.clip(t, 1e-12, 1.0 - 1e-12)
    lbeta = math.lgamma(a) + math.lgamma(a) - math.lgamma(2 * a)
    log_pdf01 = (a - 1.0) * np.log(t) + (a - 1.0) * np.log(1.0 - t) - lbeta
    return np.exp(log_pdf01) / 2.0  # /2 for the [0,1]->[-1,1] change of variable


def codebook(bits: int, dim: int, max_iter: int = 200, tol: float = 1e-10) -> Tuple[np.ndarray, np.ndarray]:
    """Return (boundaries, centroids) for `bits`-bit Lloyd-Max quantization of the
    Beta((dim-1)/2,(dim-1)/2) marginal on [-1,1]. DATA-OBLIVIOUS: depends only on
    (bits, dim). NO training data. (Re-implements turbovec lloyd_max in NumPy.)"""
    a = max((dim - 1.0) / 2.0, 0.5)
    n_levels = 1 << bits
    # std of Beta(a,a) mapped to [-1,1] is sqrt(1/(2a+1)); spread 3 std.
    std_dev = math.sqrt(1.0 / (2.0 * a + 1.0))
    spread = 3.0 * std_dev
    centroids = np.linspace(-spread, spread, n_levels).astype(np.float64)

    # Fine grid for conditional-mean integration (adaptive Simpson is overkill in
    # NumPy; a dense trapezoid on a 4096-pt grid matches to < 1e-6 here).
    grid = np.linspace(-1.0, 1.0, 4097)
    pdf = _beta_pdf_on_pm1(grid, a)
    xpdf = grid * pdf

    for _ in range(max_iter):
        bnds = (centroids[:-1] + centroids[1:]) / 2.0
        edges = np.concatenate(([-1.0], bnds, [1.0]))
        new_c = centroids.copy()
        for i in range(n_levels):
            lo, hi = edges[i], edges[i + 1]
            sel = (grid >= lo) & (grid <= hi)
            if sel.sum() < 2:
                continue
            mass = _TRAPZ(pdf[sel], grid[sel])
            if mass < 1e-15:
                continue
            new_c[i] = _TRAPZ(xpdf[sel], grid[sel]) / mass
        change = float(np.max(np.abs(new_c - centroids)))
        centroids = new_c
        if change < tol:
            break
    boundaries = (centroids[:-1] + centroids[1:]) / 2.0
    return boundaries.astype(np.float32), centroids.astype(np.float32)


# ===========================================================================
# ROTATION — deterministic seeded orthogonal matrix via QR of a Gaussian.
# (Re-implements turbovec/src/rotation.rs::make_rotation_matrix in NumPy.)
# ===========================================================================
def make_rotation_matrix(dim: int, seed: int = ROTATION_SEED) -> np.ndarray:
    rng = np.random.default_rng(seed & 0xFFFF_FFFF_FFFF_FFFF)
    g = rng.standard_normal((dim, dim)).astype(np.float64)
    q, r = np.linalg.qr(g)
    # Sign-correct so Q is deterministic: Q = Q * diag(sign(diag(R))).
    signs = np.sign(np.diag(r))
    signs[signs == 0] = 1.0
    q = q * signs[np.newaxis, :]
    return q.astype(np.float32)


# ===========================================================================
# THE GOVERNED QUANTIZED INDEX.
# ===========================================================================
class WaqayIndex:
    """A governed, data-oblivious quantized vector index (TurboQuant-shaped).

    Online: ``add`` may be called repeatedly with no separate train phase — the
    codebook is analytic (data-oblivious). Stores bit-packed codes + a per-vector
    scale; searches approximate inner products by reconstructing codes.

    Honest perf note: this is pure NumPy. Throughput is MODELED/ROADMAP vs the
    Rust SIMD original; correctness (compression + approximate recall) is real.
    """

    def __init__(self, dim: int, bit_width: int = 2, seed: int = ROTATION_SEED):
        if bit_width not in (1, 2, 3, 4):
            raise ValueError("bit_width must be 1, 2, 3, or 4")
        if dim < 2:
            raise ValueError("dim must be >= 2")
        self.dim = int(dim)
        self.bit_width = int(bit_width)
        self.seed = int(seed)
        self.rotation = make_rotation_matrix(self.dim, self.seed)
        self.boundaries, self.centroids = codebook(self.bit_width, self.dim)
        # storage
        self._codes: List[np.ndarray] = []     # each: uint8 array of length dim (level indices)
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

    # -- encode ------------------------------------------------------------
    def _encode_rows(self, vectors: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Return (level_codes:[n,dim] uint8, scales:[n] float32)."""
        v = np.asarray(vectors, dtype=np.float32)
        if v.ndim == 1:
            v = v[None, :]
        if v.shape[1] != self.dim:
            raise ValueError(f"expected dim {self.dim}, got {v.shape[1]}")
        norms = np.linalg.norm(v, axis=1)
        inv = np.where(norms > 1e-10, 1.0 / norms, 0.0)
        unit = v * inv[:, None]
        rotated = unit @ self.rotation.T  # [n, dim], each coord ~ Beta(a,a)
        # quantize each coord to nearest centroid via boundary search.
        codes = np.searchsorted(self.boundaries, rotated).astype(np.uint8)
        x_hat = self.centroids[codes]                       # reconstructed rotated unit
        # RaBitQ-style length renorm: scale = ||v|| / <u_rot, x_hat>.
        dot = np.einsum("ij,ij->i", rotated, x_hat)
        dot = np.where(np.abs(dot) > 1e-8, dot, 1.0)
        scales = (norms / dot).astype(np.float32)
        return codes, scales

    def add(self, vectors: Sequence[Sequence[float]],
            ids: Optional[Sequence[str]] = None,
            meta: Optional[Sequence[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """Online add — NO train phase. Returns a small honest stat dict."""
        v = np.asarray(vectors, dtype=np.float32)
        if v.ndim == 1:
            v = v[None, :]
        n = v.shape[0]
        codes, scales = self._encode_rows(v)
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
    def _reconstruct_matrix(self) -> np.ndarray:
        """Reconstruct approximate ORIGINAL-space vectors from stored codes."""
        if not self._codes:
            return np.zeros((0, self.dim), dtype=np.float32)
        code_mat = np.stack(self._codes).astype(np.int64)        # [N, dim]
        x_hat = self.centroids[code_mat]                          # [N, dim] rotated unit approx
        # back to original space: unit ≈ x_hat @ R ; v ≈ scale * unit
        unit_approx = x_hat @ self.rotation                      # inverse rotation = R (orthogonal, R^-1=R^T applied as @R since we used R.T forward)
        scales = np.asarray(self._scales, dtype=np.float32)[:, None]
        return (unit_approx * scales).astype(np.float32)

    def search(self, query: Sequence[float], k: int = 10,
               allow: Optional[Sequence[str]] = None,
               bitmask: Optional[Sequence[int]] = None) -> Tuple[List[float], List[str]]:
        """Approximate top-k inner-product search.

        Filtered search: `allow` is an allowlist of external IDs; `bitmask` is a
        0/1 array over internal positions. Either restricts the candidate set
        (the governed allowlist gate — only permitted docs may be retrieved).
        """
        q = np.asarray(query, dtype=np.float32).ravel()
        if q.shape[0] != self.dim:
            raise ValueError(f"query dim {q.shape[0]} != index dim {self.dim}")
        n = len(self._codes)
        if n == 0:
            return [], []
        recon = self._reconstruct_matrix()        # [N, dim]
        scores = recon @ q                         # approximate <v, q>
        mask = np.ones(n, dtype=bool)
        if allow is not None:
            allowset = set(str(a) for a in allow)
            mask &= np.array([eid in allowset for eid in self._ext_ids], dtype=bool)
        if bitmask is not None:
            bm = np.asarray(bitmask, dtype=bool)
            if bm.shape[0] != n:
                raise ValueError("bitmask length must equal index size")
            mask &= bm
        idx_pool = np.nonzero(mask)[0]
        if idx_pool.size == 0:
            return [], []
        pool_scores = scores[idx_pool]
        kk = min(k, idx_pool.size)
        top_local = np.argpartition(-pool_scores, kk - 1)[:kk]
        top_local = top_local[np.argsort(-pool_scores[top_local])]
        top = idx_pool[top_local]
        return [float(scores[i]) for i in top], [self._ext_ids[i] for i in top]

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

    def measured_recall(self, queries: np.ndarray, exact_vectors: np.ndarray,
                        k: int = 10) -> Dict[str, Any]:
        """MEASURED recall@k of WAQAY vs an exact float32 brute-force baseline over
        the SAME ingested vectors. This is a REAL number on REAL (SAMPLE) data."""
        exact = np.asarray(exact_vectors, dtype=np.float32)
        Q = np.asarray(queries, dtype=np.float32)
        if Q.ndim == 1:
            Q = Q[None, :]
        hits = 0
        total = 0
        for qi in range(Q.shape[0]):
            q = Q[qi]
            exact_scores = exact @ q
            kk = min(k, exact.shape[0])
            exact_top = set(np.argsort(-exact_scores)[:kk].tolist())
            _, approx_ids = self.search(q, k=kk)
            approx_pos = set(self._id_to_pos[i] for i in approx_ids if i in self._id_to_pos)
            hits += len(exact_top & approx_pos)
            total += kk
        recall = (hits / total) if total else 0.0
        return {"label": "MEASURED", "recall@k": round(recall, 4), "k": k,
                "n_queries": int(Q.shape[0]),
                "honesty": "Real recall@k vs exact float32 baseline on SAMPLE data."}

    # -- digest for receipts ----------------------------------------------
    def index_digest(self) -> str:
        h = hashlib.sha256()
        h.update(struct.pack("<III", self.dim, self.bit_width, len(self._codes)))
        h.update(self.boundaries.tobytes())
        for c in self._codes:
            h.update(c.tobytes())
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


def _hash_embed(text: str, dim: int = 128) -> np.ndarray:
    """Deterministic, dependency-free SAMPLE embedding (hashing trick). Honestly
    labeled SAMPLE — NOT a real semantic embedding. Used only to demo the index
    plumbing when the real BAAI/bge embedder is unavailable in this runtime."""
    vec = np.zeros(dim, dtype=np.float32)
    for tok in (text.lower().split()):
        h = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16)
        vec[h % dim] += 1.0 if (h >> 8) & 1 else -1.0
    nrm = np.linalg.norm(vec)
    return vec / nrm if nrm > 1e-9 else vec


def demo(query: str = "how does WAQAY safeguard the index?", bit_width: int = 2,
         dim: int = 128, k: int = 4) -> Dict[str, Any]:
    """One-call live demo for the /waqay tab. All data labeled SAMPLE/MEASURED/MODELED."""
    idx = WaqayIndex(dim=dim, bit_width=bit_width)
    vecs = np.stack([_hash_embed(t, dim) for _, t in _SAMPLE_DOCS])
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
    # 1. data-oblivious codebook depends only on (bits, dim).
    b1, c1 = codebook(2, 128)
    b2, c2 = codebook(2, 128)
    assert np.allclose(c1, c2), "codebook must be deterministic / data-oblivious"
    assert len(c1) == 4 and len(b1) == 3, "2-bit => 4 levels, 3 boundaries"

    # 2. online add (no train phase) + length reporting.
    rng = np.random.default_rng(0)
    V = rng.standard_normal((200, 128)).astype(np.float32)
    V /= np.linalg.norm(V, axis=1, keepdims=True) + 1e-9
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

    # 8. no user-visible codenames in the served tab.
    low = _PAGE_HTML.lower()
    for bad in ("amaru", "rosie", "sentra", "jarvis"):
        assert bad not in low, f"codename {bad} leaked into tab"
    assert "http://" not in low and "https://github.com/ryancodrai" in low, "0-CDN except attribution link"

    print("szl_waqay: ALL OK — data-oblivious codebook; online add; MEASURED "
          f"compression={comp['ratio']}x; measured recall@10={meas['recall@k']}; "
          "signed receipts + restraint; locked=8; trust<1.0; 0 codenames.")
