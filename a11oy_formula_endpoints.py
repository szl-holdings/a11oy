#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
"""a11oy_formula_endpoints.py — live HTTP surface for src/a11oy/formulas/*.

ADDITIVE, self-contained. Registered EARLY in serve.py (before the Node proxy + SPA
catch-all) so these /api/a11oy/v1/formula/* routes resolve LOCALLY. Every response uses
the HONEST schema {value, citation, lean_theorem, ...} — citation is a real
thesis_v22.pdf section, lean_theorem is a real Lean declaration/obligation name.

Endpoints:
  GET  /api/a11oy/v1/formula/pacbayes?n=&epsilon=[&kl=&empirical=]
  POST /api/a11oy/v1/formula/welford   {"sample": x}   -> fold + running stats
  GET  /api/a11oy/v1/formula/welford                   -> running mean+variance
  GET  /api/a11oy/v1/formula/quorum?n=5&f=1
  GET  /api/a11oy/v1/formula/holevo?dim=&snr=
  POST /api/a11oy/v1/formula/bloom     {"key": "..."}  -> insert
  GET  /api/a11oy/v1/formula/bloom?key=...             -> membership
  GET  /api/a11oy/v1/formula/kalman?z=                 -> streaming Λ estimate
  GET  /api/a11oy/v1/formula/reidemeister?a=1,-1&b=    -> braid equivalence
  GET  /api/a11oy/v1/formula/hnsw                      -> honest amaru-delegate status
  GET  /api/a11oy/v1/formula/bls                       -> BLS backend availability (honest)
  GET  /api/a11oy/v1/formulas/index                    -> list of wired formulas + citations

Doctrine v11 LOCKED — 749/14/163 — c7c0ba17 · Λ = Conjecture 1 (NEVER a theorem).
"""
from __future__ import annotations

import os
import sys
import threading

# Path bootstrap (robust): modules live at /app/src/a11oy/formulas/* with WORKDIR /app.
# Ensure the package root (the dir that CONTAINS the ``a11oy`` package) is importable,
# regardless of how serve.py invokes register(). Tries /app/src and the dir-relative
# ``src`` next to this file. Idempotent and side-effect-light.
for _cand in (
    "/app/src",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"),
):
    if os.path.isdir(os.path.join(_cand, "a11oy")) and _cand not in sys.path:
        sys.path.insert(0, _cand)

try:
    from starlette.requests import Request  # module-global so type hints resolve
except Exception:  # pragma: no cover
    Request = None  # type: ignore

try:
    from a11oy.formulas import (
        bloom_filter,
        bls_aggregate,
        byzantine_quorum,
        hnsw_retrieval,
        holevo_bound,
        kalman,
        pac_bayes,
        reidemeister,
        welford,
    )

    _OK = True
except Exception as _imp_e:  # pragma: no cover
    _OK = False
    print(f"[a11oy] formulas package import failed: {_imp_e!r}", file=sys.stderr)

# Per-process live accumulators (honest: in-memory, reset on rebuild).
_WELFORD = welford.Welford() if _OK else None
_BLOOM = bloom_filter.BloomFilter() if _OK else None
_KALMAN = kalman.ScalarKalman() if _OK else None
_LOCK = threading.Lock()

_INDEX = [
    {"name": "pacbayes", "citation": "thesis_v22.pdf §2", "lean_theorem": "Lutar/PACBayes.lean::pac_bayes_bound (TH13)"},
    {"name": "welford", "citation": "thesis_v22.pdf §2", "lean_theorem": "FrontierWelfordVariance.lean::welford_mean_exact"},
    {"name": "quorum", "citation": "thesis_v22.pdf §2", "lean_theorem": "KhipuConsensus.lean::khipu_consensus_safety (Conjecture 2)"},
    {"name": "holevo", "citation": "thesis_v22.pdf §2", "lean_theorem": "QuantumHolevoReceipt.lean::holevo_chi_nonneg (PR #176)"},
    {"name": "bloom", "citation": "thesis_v22.pdf §2", "lean_theorem": "FrontierBloomCacheBypass.lean::query_after_insert"},
    {"name": "kalman", "citation": "thesis_v22.pdf §2", "lean_theorem": "FrontierKalmanGain.lean::posterior_le_prior"},
    {"name": "bls", "citation": "thesis_v22.pdf §2", "lean_theorem": "FrontierBLSAggregation.lean::aggregate_verify"},
    {"name": "reidemeister", "citation": "thesis_v22.pdf §2", "lean_theorem": "KnotCalculus (v15, scaffolding)"},
    {"name": "hnsw", "citation": "thesis_v22.pdf §2", "lean_theorem": "FrontierHNSWNavigability.lean::greedy_search_terminates"},
]


def register(app, ns: str = "a11oy") -> str:
    """Mount the formula endpoints on the FastAPI ``app``. Returns a status string."""
    if not _OK:
        return "formulas-unavailable"
    from fastapi.responses import JSONResponse

    base = f"/api/{ns}/v1/formula"

    @app.get(f"/api/{ns}/v1/formulas/index")
    async def _formulas_index():
        return JSONResponse({"wired": _INDEX, "count": len(_INDEX), "doctrine": "v11"})

    @app.get(f"{base}/pacbayes")
    async def _pacbayes(n: int = 1000, epsilon: float = 0.05, kl: float = 0.0,
                        empirical: float = 0.0):
        try:
            return JSONResponse(pac_bayes.pac_bayes_bound(empirical, n, epsilon, kl))
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=400)

    @app.get(f"{base}/welford")
    async def _welford_get():
        with _LOCK:
            return JSONResponse(_WELFORD.snapshot())

    @app.post(f"{base}/welford")
    async def _welford_post(req: Request):
        body = await req.json()
        x = float(body.get("sample"))
        with _LOCK:
            return JSONResponse(_WELFORD.observe(x))

    @app.get(f"{base}/quorum")
    async def _quorum(n: int = 5, f: int | None = None):
        try:
            return JSONResponse(byzantine_quorum.quorum_threshold(n, f))
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=400)

    @app.get(f"{base}/holevo")
    async def _holevo(dim: int = 2, snr: float = 1.0):
        try:
            return JSONResponse(holevo_bound.holevo_capacity(dim, snr))
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=400)

    @app.get(f"{base}/bloom")
    async def _bloom_get(key: str | None = None):
        with _LOCK:
            if key is None:
                return JSONResponse(_BLOOM.stats())
            return JSONResponse({
                "value": not _BLOOM.definitely_absent(key),
                "key": key,
                "probably_present": _BLOOM.probably_present(key),
                "definitely_absent": _BLOOM.definitely_absent(key),
                "citation": bloom_filter.CITATION,
                "lean_theorem": bloom_filter.LEAN_THEOREM,
            })

    @app.post(f"{base}/bloom")
    async def _bloom_post(req: Request):
        body = await req.json()
        key = str(body.get("key"))
        with _LOCK:
            _BLOOM.add(key)
            stats = _BLOOM.stats()
        stats["inserted"] = key
        return JSONResponse(stats)

    @app.get(f"{base}/kalman")
    async def _kalman(z: float):
        with _LOCK:
            return JSONResponse(_KALMAN.update(z))

    @app.get(f"{base}/reidemeister")
    async def _reidemeister(a: str = "", b: str = ""):
        def parse(s):
            return [int(t) for t in s.split(",") if t.strip()]
        return JSONResponse(reidemeister.equivalent(parse(a), parse(b)))

    @app.get(f"{base}/hnsw")
    async def _hnsw():
        return JSONResponse(hnsw_retrieval.status())

    @app.get(f"{base}/bls")
    async def _bls():
        v = bls_aggregate.BLSAggregate()
        return JSONResponse({
            "value": v.available,
            "backend_available": v.available,
            "honest_note": (None if v.available else v.err),
            "citation": bls_aggregate.CITATION,
            "lean_theorem": bls_aggregate.LEAN_THEOREM,
        })

    return f"formulas-wired:{len(_INDEX)}"


__all__ = ["register"]

# Doctrine v11 LOCKED — 749/14/163 — c7c0ba17 · Λ = Conjecture 1 (NEVER a theorem)
# SLSA L1 honest. L2 build-provenance attestation = roadmap (Wire D) — not yet claimed. L3 not claimed.
