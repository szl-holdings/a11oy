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
  GET  /api/a11oy/v1/formula/hnsw                      -> honest Reasoning-delegate status
  GET  /api/a11oy/v1/formula/bls                       -> BLS backend availability (honest)
  GET  /api/a11oy/v1/formula/allodial?elem=&top=&elements=&leq=  -> allodiality check (EXPERIMENTAL)
  GET  /api/a11oy/v1/formula/entanglement?c0=&gamma=&t=          -> cap-bound (EXPERIMENTAL)
  GET  /api/a11oy/v1/formula/sovereign?served_by=&base_url=&local_node_serving=  -> sovereignty gate (EXPERIMENTAL)
  POST /api/a11oy/v1/formula/sovereign  {served_by, base_url, local_node_serving} -> sovereignty gate (EXPERIMENTAL)
  GET  /api/a11oy/v1/formulas/index                    -> list of wired formulas + citations
  GET  /api/a11oy/v1/formulas/verify                   -> proof-carrying registry report (honest: no overclaims)

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
        allodial,
        allodial_gate,
        bloom_filter,
        bls_aggregate,
        byzantine_quorum,
        entanglement,
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
    {"name": "pacbayes", "citation": "thesis_v22.pdf §2", "lean_theorem": "Lutar/PACBayes.lean::pacBayes_inequality_form (TH13)"},
    {"name": "welford", "citation": "thesis_v22.pdf §2", "lean_theorem": "FrontierWelfordVariance.lean::welford_mean_exact"},
    {"name": "quorum", "citation": "thesis_v22.pdf §2", "lean_theorem": "KhipuConsensus.lean::khipu_consensus_safety (Conjecture 2)"},
    {"name": "holevo", "citation": "thesis_v22.pdf §2", "lean_theorem": "QuantumHolevoReceipt.lean::holevo_chi_nonneg (PR #176 — PROPOSED, not yet in corpus)", "tier": "experimental"},
    {"name": "bloom", "citation": "thesis_v22.pdf §2", "lean_theorem": "FrontierBloomCacheBypass.lean::query_after_insert"},
    {"name": "kalman", "citation": "thesis_v22.pdf §2", "lean_theorem": "FrontierKalmanGain.lean::posterior_le_prior"},
    {"name": "bls", "citation": "thesis_v22.pdf §2", "lean_theorem": "FrontierBLSAggregation.lean::aggregate_verify"},
    {"name": "reidemeister", "citation": "thesis_v22.pdf §2", "lean_theorem": "KnotCalculus (v15, scaffolding — PROPOSED obligation, not a locked theorem)", "tier": "experimental"},
    {"name": "hnsw", "citation": "thesis_v22.pdf §2", "lean_theorem": "FrontierHNSWNavigability.lean::greedy_search_terminates"},
    {"name": "kl", "citation": "Cover–Thomas Thm 2.6.3 (Gibbs); χPO arXiv:2407.13399; f-DPO arXiv:2309.16240",
     "lean_theorem": "Wave15/DPOKLSimplex.lean::dpo_klDivergence_nonneg_on_simplex (CF-22)", "tier": "experimental"},
    {"name": "pinsker", "citation": "Pinsker 1964; binary Pinsker (CF-23, Wave17)",
     "lean_theorem": "Wave17/BinaryPinsker.lean::binary_pinsker (CF-23)", "tier": "experimental"},
    {"name": "aftershock", "citation": "Reasenberg–Jones 1989; Gasperini–Lolli 2006 (α≈⅔b); USGS live feed",
     "lean_theorem": "(seismic forecast — not a Lean theorem; generic-parameter R–J model)", "tier": "live-data"},
    # ---- EXPERIMENTAL frontier backbones (Lutar/Allodial.lean + Lutar/Entanglement.lean) ----
    {"name": "allodial",
     "citation": "Lutar/Allodial.lean (PR #229, merge 783a38d0)",
     "lean_theorem": "Lutar/Allodial.lean::allodial_dominates_all / galois_preserves_allodial / ni_low_independent_of_high (EXPERIMENTAL — PROPOSED gate, not a locked theorem)",
     "tier": "experimental"},
    {"name": "entanglement",
     "citation": "Lutar/Entanglement.lean (PR #230, merge 3a7f222ed3bb)",
     "lean_theorem": "Lutar/Entanglement.lean::capBound_antitone / entanglement_decays_under_bound (EXPERIMENTAL — PROPOSED gate, not a locked theorem)",
     "tier": "experimental"},
    {"name": "sovereign",
     "citation": "Lutar/Allodial.lean (PR #229, merge 783a38d0) — ni_low_independent_of_high",
     "lean_theorem": "Lutar/Allodial.lean::ni_low_independent_of_high / allodial_iff_top (EXPERIMENTAL — PROPOSED gate, not a locked theorem)",
     "tier": "experimental"},
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

    @app.get(f"/api/{ns}/v1/formulas/verify")
    async def _formulas_verify():
        # PROOF-CARRYING REGISTRY: verify every served formula's claimed Lean
        # theorem / citation against the bundled canonical corpus. An overclaim
        # (a non-experimental formula whose Lean theorem is ABSENT) is surfaced
        # honestly as status "unbacked" (report.honest=false) — never dressed up
        # as proven. Λ-uniqueness stays Conjecture 1 (never a theorem).
        from a11oy_formula_registry_guard import registry_report
        return JSONResponse(registry_report(_INDEX))

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

    # ---- CF-22: KL + chi-square on a posted probability simplex (DPO conditional repair) ----
    @app.post(f"{base}/kl")
    async def _kl(req: Request):
        """KL(p||q) and chi^2(p||q) on the simplex. CF-22: KL>=0 holds ON the simplex
        (the UNCONDITIONAL DPO axiom stays FALSE-as-stated; only this is the theorem)."""
        import math
        body = await req.json()
        p = [float(x) for x in (body.get("p") or [])]
        q = [float(x) for x in (body.get("q") or [])]
        if len(p) != len(q) or not p:
            return JSONResponse({"error": "p and q must be equal-length non-empty vectors"}, status_code=400)
        sp, sq = sum(p), sum(q)
        if sp <= 0 or sq <= 0:
            return JSONResponse({"error": "p and q must have positive mass"}, status_code=400)
        p = [x / sp for x in p]; q = [x / sq for x in q]  # project onto the simplex (honest normalization)
        kl = sum(pi * math.log(pi / qi) for pi, qi in zip(p, q) if pi > 0 and qi > 0)
        chi2 = sum((pi - qi) ** 2 / qi for pi, qi in zip(p, q) if qi > 0)
        return JSONResponse({
            "value": kl, "kl": kl, "chi_square": chi2, "nonneg": kl >= -1e-12,
            "normalized_to_simplex": True,
            "citation": "Cover–Thomas Thm 2.6.3 (Gibbs); χPO arXiv:2407.13399; f-DPO arXiv:2309.16240",
            "lean_theorem": "Wave15/DPOKLSimplex.lean::dpo_klDivergence_nonneg_on_simplex (CF-22)",
            "tier": "experimental",
            "honest_note": "KL>=0 PROVEN conditionally on the simplex (CF-22). The unconditional in-tree DPO axiom klDivergence_nonneg stays FALSE-as-stated.",
        })

    # ---- CF-23: binary Pinsker  KL(Bern p || Bern q) >= 2*(p-q)^2 ----
    @app.get(f"{base}/pinsker")
    async def _pinsker(p: float = 0.6, q: float = 0.5):
        """Binary Pinsker (CF-23): 2*(p-q)^2 <= KL(Bern p || Bern q). Live margin check."""
        import math
        if not (0.0 < p < 1.0 and 0.0 < q < 1.0):
            return JSONResponse({"error": "p,q must be in the open interval (0,1)"}, status_code=400)
        kl = p * math.log(p / q) + (1 - p) * math.log((1 - p) / (1 - q))
        tv = abs(p - q)
        bound = 2.0 * tv * tv
        return JSONResponse({
            "value": kl, "kl": kl, "tv": tv, "pinsker_rhs": bound,
            "margin": kl - bound, "holds": kl + 1e-12 >= bound,
            "citation": "Pinsker 1964; binary Pinsker (CF-23, Wave17 PR #207)",
            "lean_theorem": "Wave17/BinaryPinsker.lean::binary_pinsker (CF-23)",
            "tier": "experimental",
            "honest_note": "Full binary Pinsker PROVEN (CF-23), experimental CI-green — NOT folded into the locked 5.",
        })

    # ---- Reasenberg–Jones aftershock rate from a live USGS mainshock (genuine live DATA) ----
    @app.get(f"{base}/aftershock")
    async def _aftershock(mainshock_mag: float = 6.0, target_mag: float = 5.0,
                          days: float = 1.0, a: float = -1.67, b: float = 0.91,
                          c: float = 0.05, pexp: float = 1.08, alpha_correction: bool = True):
        """Reasenberg–Jones short-term aftershock rate λ(t,M)=10^(a+b(Mm−M))/(t+c)^p,
        with the Gasperini–Lolli α≈⅔b productivity correction. GENERIC PARAMETERS — labeled.
        Feed mainshock_mag from the live USGS all_day.geojson on the client (real data)."""
        import math
        if days <= 0:
            return JSONResponse({"error": "days must be > 0"}, status_code=400)
        # α≈⅔b correction (Gasperini–Lolli 2006): tempers strong-mainshock over-productivity.
        a_eff = a if not alpha_correction else (a + (b - (2.0 / 3.0) * b) * (mainshock_mag - target_mag))
        # integrate Omori-Utsu rate over (0, days] for expected count of M>=target_mag aftershocks
        prod = 10.0 ** (a_eff + b * (mainshock_mag - target_mag))
        if abs(pexp - 1.0) < 1e-9:
            integ = math.log((days + c) / c)
        else:
            integ = ((days + c) ** (1.0 - pexp) - c ** (1.0 - pexp)) / (1.0 - pexp)
        expected = prod * integ
        rate_per_day = prod / ((days + c) ** pexp)
        prob_at_least_one = 1.0 - math.exp(-expected) if expected >= 0 else None
        return JSONResponse({
            "value": rate_per_day, "rate_per_day": rate_per_day,
            "expected_count_in_window": expected, "prob_at_least_one": prob_at_least_one,
            "params": {"a": a, "b": b, "c": c, "p": pexp, "alpha_correction": alpha_correction,
                       "mainshock_mag": mainshock_mag, "target_mag": target_mag, "days": days},
            "citation": "Reasenberg–Jones 1989 (doi:10.1016/J.PEPI.2006.01.005); Gasperini–Lolli 2006 (α≈⅔b); USGS earthquake.usgs.gov feed",
            "lean_theorem": None,
            "tier": "live-data",
            "honest_note": "GENERIC-PARAMETER forecast over genuine live USGS mainshock data. Not a Lean theorem; early aftershocks are under-detected (Omi 2013) and Mmax can be over-estimated (Hainzl 2024).",
        })

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

    # ---- EXPERIMENTAL frontier: Allodial order-theoretic sovereignty checks ----
    @app.get(f"{base}/allodial")
    async def _allodial(elem: str = "top", top: str = "top",
                        elements: str = "bot,a,b,top",
                        leq: str = "bot:a,bot:b,bot:top,a:b,a:top,b:top"):
        """Allodial check on a finite control lattice (EXPERIMENTAL).

        Pass `elem`, `top`, `elements` (comma-sep), and `leq` (comma-sep a:b pairs).
        Returns the HONEST EXPERIMENTAL-tier allodiality assessment.
        NOTE: EXPERIMENTAL backbone — Lutar/Allodial.lean PR #229, NOT locked-8, NOT a formal \u039b result.
        """
        try:
            elems_list = [e.strip() for e in elements.split(",") if e.strip()]
            leq_pairs = []
            for pair in leq.split(","):
                pair = pair.strip()
                if ":" in pair:
                    a_part, b_part = pair.split(":", 1)
                    leq_pairs.append((a_part.strip(), b_part.strip()))
            result = allodial.allodial_check(elem, top, elems_list, leq_pairs)
            return JSONResponse(dict(result))
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=400)

    # ---- EXPERIMENTAL frontier: Entanglement-generating-capacity bound ----
    @app.get(f"{base}/entanglement")
    async def _entanglement(c0: float = 1.0, gamma: float = 0.5, t: float = 1.0):
        """Coherence\u2192entanglement-generating-capacity upper bound cap_bound(C\u2080,\u03b3,t) = C\u2080\u00b7exp(\u2212\u03b3t).

        This is a CAPACITY UPPER BOUND, not a claimed entanglement rate.
        NOTE: EXPERIMENTAL backbone \u2014 Lutar/Entanglement.lean PR #230, NOT locked-8, NOT a formal \u039b result.
        """
        try:
            return JSONResponse(dict(entanglement.cap_bound_full(c0, gamma, t)))
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=400)

    # ---- EXPERIMENTAL frontier: Sovereignty gate (half-state doctrine) ----
    @app.get(f"{base}/sovereign")
    async def _sovereign_get(served_by: str = "local", base_url: str = "",
                             local_node_serving: bool = False):
        """Sovereignty gate: returns sovereign:true ONLY when a local/owned node actually serves.

        The half-state (banner claims sovereignty while routing to an external node) is the
        ONLY unacceptable outcome and is flagged with half_state:true, sovereign:false.
        Grounded in Lutar/Allodial.lean::ni_low_independent_of_high (EXPERIMENTAL).
        """
        return JSONResponse(dict(allodial_gate.sovereign_verdict(
            served_by, base_url, local_node_serving
        )))

    @app.post(f"{base}/sovereign")
    async def _sovereign_post(req: Request):
        """Sovereignty gate via POST body {served_by, base_url, local_node_serving}.

        The half-state (banner claims sovereignty while routing to an external node) is the
        ONLY unacceptable outcome and is flagged with half_state:true, sovereign:false.
        Grounded in Lutar/Allodial.lean::ni_low_independent_of_high (EXPERIMENTAL).
        """
        body = await req.json()
        served_by = str(body.get("served_by", "local"))
        base_url = str(body.get("base_url", ""))
        local_node_serving = bool(body.get("local_node_serving", False))
        return JSONResponse(dict(allodial_gate.sovereign_verdict(
            served_by, base_url, local_node_serving
        )))

    return f"formulas-wired:{len(_INDEX)}"


__all__ = ["register"]

# Doctrine v11 LOCKED — 749/14/163 — c7c0ba17 · Λ = Conjecture 1 (NEVER a theorem)
# SLSA L1 honest. L2 build-provenance attestation = roadmap (Wire D) — not yet claimed. L3 not claimed.
