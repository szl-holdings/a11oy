# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 — Materials ("Q'allariy") verifiable crystal-discovery surface.
"""
szl_materials.py — the HONEST `/api/a11oy/v1/materials/*` surface on a11oy.

This module is the SHARED home of the Materials surface. It is structured so
that several route groups can be appended cleanly:

    register(app, ns)            -> DEV 1: Crystal Novelty Certificate  (THIS FILE)
    register_certify(app, ns)    -> DEV 2: PAC-Bayes certified bound     (appended later)
    register_screen(app, ns)     -> DEV 3: Immune-gated + energy pipeline (appended later)

DEV 1 OWNS this file and the novelty endpoints below. DEV 2/DEV 3 append their
own `register_*` helpers + section blocks WITHOUT touching the DEV-1 section.
`register()` is the single entry serve.py imports; it mounts the novelty group
and (if the later helpers are present) calls them too, so one import in serve.py
wires every group.

============================================================================
DEV 1 — CRYSTAL NOVELTY CERTIFICATE  [answers the GNoME silent-duplicate scandal]
============================================================================
WHAT IT DOES:
  POST /api/a11oy/v1/materials/novelty
     Input a crystal {a,b,c,alpha,beta,gamma, sites:[{el,x,y,z}]} (lattice
     params in Å + degrees; sites in FRACTIONAL coordinates). Compute an
     ISOMETRY-INVARIANT fingerprint — a sorted Pointwise-Distance-Distribution
     (PDD)-style histogram of pairwise interatomic distances within a cutoff,
     evaluated over periodic images of the lattice. Compare it against an
     append-only in-process registry (dict + list, thread-locked). Return
     {novel, nearest_match_id, distance, fingerprint_digest, fingerprint} plus a
     SIGNED Khipu receipt (SZL.Materials.NoveltyCert.v1) into the SHARED
     szl_khipu DAG (organ="materials"). On novel=true the fingerprint is
     registered.
  GET /api/a11oy/v1/materials/novelty/registry
     List registered fingerprint ids + chain head + count.

WHY THE FINGERPRINT IS ISOMETRY-INVARIANT (honest math note):
  A rigid motion (rotation + translation) of a crystal leaves every INTERATOMIC
  DISTANCE unchanged, and leaves the lattice GRAM/METRIC tensor G = LᵀL
  (from a,b,c,α,β,γ) unchanged. We never use the absolute Cartesian frame: we
  build distances purely from fractional-coordinate differences contracted with
  G over periodic images. So the multiset of pairwise distances — and therefore
  the sorted histogram — is invariant to rotation, translation, and choice of
  Cartesian orientation. This is the construction behind Kurlin & Widdowson's
  Pointwise Distance Distribution (PDD), the continuous isometry invariant used
  to find the GNoME / Materials-Project duplicates.
  Cite: Widdowson, Mosca, Pulido, Cooper & Kurlin, "Average Minimum Distances of
  periodic point sets" (MATCH Commun. Math. Comput. Chem. 87, 2022); Widdowson &
  Kurlin, "Resolving the data ambiguity for periodic crystals" (NeurIPS 2022,
  arXiv:2108.04798). GNoME duplicate finding: Kurlin/Widdowson et al., reported
  in C&EN, "Duplicate structures haunt crystallography databases" (Dec 2025),
  https://cen.acs.org/research-integrity/Duplicate-structures-haunt-crystallography-databases/103/web/2025/12

HONESTY (Doctrine v11 — NEVER violate):
  - PROVEN here: the receipt hash-chain integrity (szl_khipu), and the fact that
    the fingerprint + nearest-neighbour comparison is REAL, deterministic, and
    isometry-invariant by the construction above. A duplicate of an already-seen
    crystal IS detected (distance ≈ 0).
  - CONJECTURE / ROADMAP — NOT proven, NOT in locked-8: the fingerprint
    INJECTIVITY claim (no two DISTINCT crystals ever produce the same
    fingerprint). The Lean target is `Lutar/Materials/PDDInjective.lean`, status
    "ROADMAP/CONJECTURE — NOT proven, NOT in locked-8". The locked-proven set is
    EXACTLY 8 {F1,F4,F7,F11,F12,F18,F19,F22} @ kernel c7c0ba17 and this module
    NEVER adds to it. Khipu = Conjecture 2; trust is never 100%.
  - No fabricated data. Every datum is labeled LIVE / REAL / CONJECTURE /
    ROADMAP. The receipt SIGNATURE is the szl_khipu DSSE PLACEHOLDER (chain
    integrity is real; Sigstore not wired) — honestly carried, not overclaimed.

Stdlib only (math, hashlib, json, threading, time) + the existing szl_khipu.
No new pip dep, no CDN, no Node. Additive; try/except-guarded; registered
BEFORE the SPA catch-all.
"""
from __future__ import annotations

import hashlib
import json
import math
import threading
import time
from typing import Any, Optional

from fastapi import Request
from fastapi.responses import JSONResponse

# ===========================================================================
# DEV 1 SECTION — Crystal Novelty Certificate  (OWNED by DEV 1)
# ===========================================================================

_NOVELTY_RECEIPT_TYPE = "SZL.Materials.NoveltyCert.v1"
_KHIPU_ORGAN = "materials"

# PDD-style histogram configuration. The cutoff bounds the periodic image search;
# the bin width discretizes the distance distribution. Both are part of the
# fingerprint contract (so two fingerprints are only comparable under the same
# config — which they always are here, fixed module-level constants).
_PDD_CUTOFF_ANG = 8.0      # Å — interatomic distance cutoff
_PDD_BIN_ANG = 0.10        # Å — histogram bin width
_PDD_MAX_IMAGE = 3         # search periodic images in [-3..3] per axis (ample for 8 Å)
_NOVELTY_TANI_EPS = 1e-6   # distance below which two fingerprints are "the same crystal"

# Honest Lean backing — ROADMAP/CONJECTURE, explicitly NOT in locked-8.
_LEAN_ROADMAP = {
    "ref": "Lutar/Materials/PDDInjective.lean",
    "claim": "PDD/sorted-distance fingerprint is injective on isometry classes "
             "(no two distinct crystals collide)",
    "status": "ROADMAP/CONJECTURE — NOT proven, NOT in locked-8",
}
_LOCKED8 = ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]
_LOCKED8_KERNEL = "c7c0ba17"

# Append-only in-process registry: list of records + dict index by id.
# Thread-locked. (Stateless across Space restarts — the DISCIPLINE, not durable
# storage, is what is load-bearing; mirrors szl_khipu's honest note.)
_REG_LOCK = threading.Lock()
_REGISTRY: list[dict[str, Any]] = []
_REGISTRY_BY_ID: dict[str, dict[str, Any]] = {}


# ---------------------------------------------------------------------------
# Lattice metric tensor from (a,b,c,α,β,γ). G = Lᵀ L is isometry-invariant:
# squared distance of a fractional difference Δf is Δfᵀ G Δf. We never need the
# absolute Cartesian L — only G — so rotation/translation of the crystal cannot
# change any computed distance. (Honest, deterministic, real.)
# ---------------------------------------------------------------------------
def _metric_tensor(a: float, b: float, c: float,
                   alpha: float, beta: float, gamma: float) -> list[list[float]]:
    ca = math.cos(math.radians(alpha))
    cb = math.cos(math.radians(beta))
    cg = math.cos(math.radians(gamma))
    return [
        [a * a,      a * b * cg, a * c * cb],
        [a * b * cg, b * b,      b * c * ca],
        [a * c * cb, b * c * ca, c * c],
    ]


def _frac_dist2(df: tuple[float, float, float], G: list[list[float]]) -> float:
    """Squared Cartesian distance of a fractional difference df via the metric G."""
    x, y, z = df
    gx = G[0][0] * x + G[0][1] * y + G[0][2] * z
    gy = G[1][0] * x + G[1][1] * y + G[1][2] * z
    gz = G[2][0] * x + G[2][1] * y + G[2][2] * z
    d2 = x * gx + y * gy + z * gz
    return d2 if d2 > 0.0 else 0.0


# ---------------------------------------------------------------------------
# Fingerprint: sorted PDD-style histogram of pairwise interatomic distances
# within _PDD_CUTOFF_ANG, over periodic images. Returns (histogram, n_dist).
# The histogram is a list of ints (counts per distance bin) — deterministic and
# isometry-invariant by construction. The histogram is L1-normalized into a
# float vector for comparison so it is independent of how many atoms / images
# happen to fall in the cutoff shell density.
# ---------------------------------------------------------------------------
def _compute_fingerprint(crystal: dict[str, Any]) -> dict[str, Any]:
    a = float(crystal["a"]); b = float(crystal["b"]); c = float(crystal["c"])
    alpha = float(crystal.get("alpha", 90.0))
    beta = float(crystal.get("beta", 90.0))
    gamma = float(crystal.get("gamma", 90.0))
    sites = crystal.get("sites") or []
    if not sites:
        raise ValueError("crystal.sites must be a non-empty list of {el,x,y,z}")
    if a <= 0 or b <= 0 or c <= 0:
        raise ValueError("lattice lengths a,b,c must be positive")

    G = _metric_tensor(a, b, c, alpha, beta, gamma)
    fr = [(float(s["x"]), float(s["y"]), float(s["z"])) for s in sites]

    nbins = int(math.ceil(_PDD_CUTOFF_ANG / _PDD_BIN_ANG))
    cutoff2 = _PDD_CUTOFF_ANG * _PDD_CUTOFF_ANG
    hist = [0] * nbins
    n_dist = 0

    rng = range(-_PDD_MAX_IMAGE, _PDD_MAX_IMAGE + 1)
    images = [(i, j, k) for i in rng for j in rng for k in rng]

    # All ordered pairs (i in central cell) -> (j over all periodic images),
    # excluding the self-distance (same atom, zero image). Ordered pairs keep the
    # construction simple and still isometry-invariant; self-pairs (d=0) excluded.
    for ai in range(len(fr)):
        xi, yi, zi = fr[ai]
        for aj in range(len(fr)):
            xj, yj, zj = fr[aj]
            for (ix, iy, iz) in images:
                dx = (xj + ix) - xi
                dy = (yj + iy) - yi
                dz = (zj + iz) - zi
                if ai == aj and ix == 0 and iy == 0 and iz == 0:
                    continue
                d2 = _frac_dist2((dx, dy, dz), G)
                if d2 <= 0.0 or d2 > cutoff2:
                    continue
                d = math.sqrt(d2)
                bidx = int(d / _PDD_BIN_ANG)
                if bidx >= nbins:
                    bidx = nbins - 1
                hist[bidx] += 1
                n_dist += 1

    total = float(sum(hist)) or 1.0
    vec = [h / total for h in hist]

    # Compact short form for display: bin_index:weight for nonzero bins, rounded.
    short_pairs = [(i, round(vec[i], 4)) for i in range(nbins) if hist[i] > 0]
    short = ";".join(f"{i}:{w}" for i, w in short_pairs[:24])
    if len(short_pairs) > 24:
        short += f";+{len(short_pairs) - 24}more"

    digest = hashlib.sha3_256(
        json.dumps({"cfg": [_PDD_CUTOFF_ANG, _PDD_BIN_ANG, _PDD_MAX_IMAGE],
                    "vec": [round(v, 9) for v in vec]},
                   sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    return {
        "vector": vec,
        "histogram_counts": hist,
        "n_pairwise_distances": n_dist,
        "n_sites": len(fr),
        "fingerprint_digest": digest,
        "fingerprint_short": short,
        "config": {"cutoff_ang": _PDD_CUTOFF_ANG, "bin_ang": _PDD_BIN_ANG,
                   "max_image": _PDD_MAX_IMAGE},
        "invariant_kind": "Kurlin-style Pointwise Distance Distribution (sorted "
                          "pairwise-distance histogram); isometry-invariant via "
                          "lattice metric tensor G=LᵀL",
    }


def _l1_distance(u: list[float], v: list[float]) -> float:
    """L1 (Manhattan) distance between two equal-length normalized histograms.
    Deterministic, symmetric, 0 iff identical. Range [0, 2] for L1-normalized."""
    n = max(len(u), len(v))
    s = 0.0
    for i in range(n):
        ui = u[i] if i < len(u) else 0.0
        vi = v[i] if i < len(v) else 0.0
        s += abs(ui - vi)
    return s


def _nearest(vec: list[float]) -> tuple[Optional[str], Optional[float]]:
    """Find the registered fingerprint with minimum L1 distance to vec."""
    best_id: Optional[str] = None
    best_d: Optional[float] = None
    for rec in _REGISTRY:
        d = _l1_distance(vec, rec["vector"])
        if best_d is None or d < best_d:
            best_d = d
            best_id = rec["id"]
    return best_id, best_d


def _novelty_honesty() -> dict[str, Any]:
    return {
        "fingerprint_comparison": "REAL (deterministic, isometry-invariant)",
        "receipt_chain": "REAL (szl_khipu SHA3-256 hash chain; tamper-evident)",
        "receipt_signature": "DSSE_PLACEHOLDER (Sigstore not wired; honest)",
        "injectivity_claim": _LEAN_ROADMAP["status"],
        "lean_roadmap_ref": _LEAN_ROADMAP["ref"],
        "khipu": "Conjecture 2",
        "lambda": "Conjecture 1",
        "trust_ceiling": "never 100%",
        "fabricated_data": False,
        "locked8": _LOCKED8,
        "locked8_kernel": _LOCKED8_KERNEL,
        "locked8_note": "novelty fingerprint is NOT added to locked-8",
    }


def _do_novelty(crystal: dict[str, Any]) -> dict[str, Any]:
    """Core novelty computation: fingerprint, compare, sign Khipu receipt, and
    (if novel) register. Returns the full honest response dict."""
    import szl_khipu  # imported here (same idiom as kverify/_run_benchmark)

    fp = _compute_fingerprint(crystal)
    vec = fp["vector"]
    dag = szl_khipu.get_dag(_KHIPU_ORGAN, ns="a11oy")

    with _REG_LOCK:
        nearest_id, nearest_d = _nearest(vec)
        novel = (nearest_d is None) or (nearest_d > _NOVELTY_TANI_EPS)

        new_id: Optional[str] = None
        if novel:
            new_id = f"mat-{len(_REGISTRY):06d}-{fp['fingerprint_digest'][:12]}"
            rec = {
                "id": new_id,
                "vector": vec,
                "fingerprint_digest": fp["fingerprint_digest"],
                "fingerprint_short": fp["fingerprint_short"],
                "n_sites": fp["n_sites"],
                "registered_ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            _REGISTRY.append(rec)
            _REGISTRY_BY_ID[new_id] = rec

        registry_count = len(_REGISTRY)

    # Sign a Khipu receipt into the SHARED materials chain (tamper-evident).
    receipt_payload = {
        "receipt_type": _NOVELTY_RECEIPT_TYPE,
        "organ": _KHIPU_ORGAN,
        "operation": "novelty_certificate",
        "novel": novel,
        "registered_id": new_id,
        "nearest_match_id": nearest_id,
        "nearest_distance": nearest_d,
        "distance_metric": "L1 over L1-normalized PDD histogram",
        "fingerprint_digest": fp["fingerprint_digest"],
        "fingerprint_short": fp["fingerprint_short"],
        "n_sites": fp["n_sites"],
        "n_pairwise_distances": fp["n_pairwise_distances"],
        "invariant_kind": fp["invariant_kind"],
        "config": fp["config"],
        "honesty": _novelty_honesty(),
        "lean_roadmap": _LEAN_ROADMAP,
        "doctrine": "v11",
    }
    receipt = dag.emit("materials.novelty", receipt_payload)

    return {
        "ok": True,
        "service": "materials.novelty",
        "novel": novel,
        "nearest_match_id": nearest_id,
        "distance": nearest_d,
        "registered_id": new_id,
        "registry_count": registry_count,
        "fingerprint_digest": fp["fingerprint_digest"],
        "fingerprint": fp["fingerprint_short"],
        "invariant": fp["invariant_kind"],
        "receipt": {
            "receipt_type": _NOVELTY_RECEIPT_TYPE,
            "organ": _KHIPU_ORGAN,
            "seq": receipt["seq"],
            "digest": receipt["digest"],
            "prev": receipt["prev"],
            "payload_digest": receipt["payload_digest"],
            "signature": receipt["signature"],
            "chain_head": dag.head(),
            "chain_depth": dag.depth(),
        },
        "honesty": _novelty_honesty(),
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def _registry_view() -> dict[str, Any]:
    """List registered fingerprint ids + chain head + count."""
    import szl_khipu
    dag = szl_khipu.get_dag(_KHIPU_ORGAN, ns="a11oy")
    chain = dag.verify_chain()
    with _REG_LOCK:
        ids = [
            {"id": r["id"], "fingerprint_digest": r["fingerprint_digest"],
             "fingerprint_short": r["fingerprint_short"], "n_sites": r["n_sites"],
             "registered_ts": r["registered_ts"]}
            for r in _REGISTRY
        ]
        count = len(_REGISTRY)
    return {
        "ok": True,
        "service": "materials.novelty.registry",
        "organ": _KHIPU_ORGAN,
        "ns": "a11oy",
        "count": count,
        "registered": ids,
        "chain_head": dag.head(),
        "chain_depth": dag.depth(),
        "chain_verified": chain.get("ok"),
        "chain_broken_at": chain.get("broken_at"),
        "receipt_type": _NOVELTY_RECEIPT_TYPE,
        "honesty": _novelty_honesty(),
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


# ---------------------------------------------------------------------------
# Novelty route group. Pulled out of register() so it can be mounted on its own
# and so DEV 2/DEV 3 append parallel mount helpers without editing this one.
# ---------------------------------------------------------------------------
def _register_novelty(app, ns: str = "a11oy") -> list[str]:
    # NOTE: Request/JSONResponse are imported at MODULE level (top of file) — NOT
    # here — because this module uses `from __future__ import annotations`, which
    # stringizes annotations; FastAPI resolves a handler's `request: Request`
    # annotation via module globals, so a function-local import would leave it
    # unresolved and FastAPI would (wrongly) treat `request` as a required query
    # param (HTTP 422). Module-level import keeps `Request` in globals.
    async def _novelty(request: Request):  # noqa: ANN202
        try:
            if request.method == "POST":
                crystal = await request.json()
            else:
                crystal = {}
                # allow ?a=&b=... only minimally; primary path is POST JSON
            if not isinstance(crystal, dict) or not crystal.get("sites"):
                return JSONResponse(
                    {"ok": False, "error": "POST a JSON crystal "
                     "{a,b,c,alpha,beta,gamma,sites:[{el,x,y,z}]}",
                     "honesty": _novelty_honesty()},
                    status_code=400,
                )
            result = _do_novelty(crystal)
            return JSONResponse(result, headers={
                "x-szl-materials-novel": "true" if result["novel"] else "false",
                "x-szl-receipt-digest": result["receipt"]["digest"],
            })
        except ValueError as ve:
            return JSONResponse(
                {"ok": False, "error": str(ve), "honesty": _novelty_honesty()},
                status_code=400,
            )
        except Exception as e:  # noqa: BLE001
            return JSONResponse(
                {"ok": False, "error": f"{e!r}", "honesty": _novelty_honesty()},
                status_code=500,
            )

    async def _registry():  # noqa: ANN202
        return JSONResponse(_registry_view())

    prefixes = [f"/api/{ns}/v1/materials", "/v1/materials"]
    routes: list[str] = []
    for p in prefixes:
        app.add_api_route(f"{p}/novelty", _novelty, methods=["POST", "GET"],
                          include_in_schema=True)
        app.add_api_route(f"{p}/novelty/registry", _registry, methods=["GET"],
                          include_in_schema=True)
        routes.extend([f"{p}/novelty", f"{p}/novelty/registry"])
    return routes


# ===========================================================================
# DEV 2 SECTION — PAC-Bayes certified prediction bound  [frontier gap #2]
# ===========================================================================
# WHAT IT DOES:
#   POST /api/a11oy/v1/materials/certify
#     Accept EITHER explicit {empirical_risk, kl, n, delta} OR a named preset
#     {family: "oxides"|"intermetallics"|"refractory_hea"} (or {model, family}).
#     Compute the McAllester (1999) PAC-Bayes generalization bound by IMPORTING
#     `pac_bayes_mcallester` from szl_formulas (NOT reimplemented here). Return
#     {bound, inputs, certificate_text, proof_status} + a SIGNED Khipu receipt
#     (SZL.Materials.PACBayesCert.v1) into the SHARED szl_khipu DAG
#     (organ="materials"), reusing the exact get_dag/emit pattern DEV 1 used.
#   GET /api/a11oy/v1/materials/certify/presets
#     List the presets, each explicitly labeled SAMPLE/MODELED illustrative input.
#
# HONESTY (Doctrine v11 — NEVER violate):
#   - The McAllester bound FORMULA is PROVEN ON PAPER (McAllester 1999, COLT) and
#     the bound COMPUTATION here is numerically EXACT (delegated to szl_formulas).
#   - The LEAN proof is an OPEN SORRY / ROADMAP (Lutar/Materials/PACBayesMaterials.lean,
#     a.k.a. the PACBayes ×4 tracked sorries). We NEVER claim Lean-proven.
#   - Presets are EXPLICITLY labeled SAMPLE/MODELED illustrative inputs — they are
#     NOT measured empirical risks of any deployed model. No fabricated empirics.
#   - Khipu = Conjecture 2; locked-8 unchanged @ c7c0ba17 (this NEVER adds to it);
#     trust never 100%; receipt signature is the szl_khipu DSSE PLACEHOLDER.
#
# Stdlib only + szl_formulas (existing) + szl_khipu (shared). Additive,
# self-contained, exception-safe; register_certify is auto-called by register().
# ===========================================================================

_PACBAYES_RECEIPT_TYPE = "SZL.Materials.PACBayesCert.v1"

# Lean backing for the McAllester bound — OPEN SORRY / ROADMAP, NOT in locked-8.
_PACBAYES_PROOF_STATUS = (
    "bound formula PROVEN on paper (McAllester 1999, COLT); "
    "Lean proof = SORRY/ROADMAP (Lutar/Materials/PACBayesMaterials.lean); "
    "bound COMPUTATION exact"
)
_PACBAYES_LEAN_ROADMAP = {
    "ref": "Lutar/Materials/PACBayesMaterials.lean",
    "claim": "McAllester (1999) PAC-Bayes generalization bound, "
             "R(Q) <= Rhat(Q) + sqrt((KL + ln(2*sqrt(n)/delta)) / (2n))",
    "status": "SORRY/ROADMAP — NOT Lean-proven, NOT in locked-8; "
              "formula PROVEN on paper, computation exact",
}

# Honest, clearly-labeled SAMPLE/MODELED presets. These are ILLUSTRATIVE inputs
# (NOT measured empirical risks of any deployed SZL model) chosen so each family
# yields a sensible, distinct certified bound. risk units are normalized risk
# (dimensionless, in [0,1]); for an energy-prediction surrogate the same machinery
# applies with risk measured in eV/atom — labeled per call.
_PACBAYES_PRESETS: dict[str, dict[str, Any]] = {
    "oxides": {
        "empirical_risk": 0.04, "kl": 2.5, "n": 50000, "delta": 0.05,
        "risk_units": "normalized risk (dimensionless, [0,1])",
        "label": "SAMPLE/MODELED — illustrative inputs for an oxide formation-"
                 "energy surrogate; NOT a measured empirical risk",
    },
    "intermetallics": {
        "empirical_risk": 0.06, "kl": 3.2, "n": 20000, "delta": 0.05,
        "risk_units": "normalized risk (dimensionless, [0,1])",
        "label": "SAMPLE/MODELED — illustrative inputs for an intermetallic "
                 "stability surrogate; NOT a measured empirical risk",
    },
    "refractory_hea": {
        "empirical_risk": 0.09, "kl": 5.0, "n": 8000, "delta": 0.10,
        "risk_units": "normalized risk (dimensionless, [0,1])",
        "label": "SAMPLE/MODELED — illustrative inputs for a refractory high-"
                 "entropy-alloy surrogate; NOT a measured empirical risk",
    },
}


def _pacbayes_honesty() -> dict[str, Any]:
    return {
        "bound_formula": "PROVEN on paper (McAllester 1999, COLT)",
        "bound_computation": "EXACT (delegated to szl_formulas.pac_bayes_mcallester)",
        "lean_proof": _PACBAYES_LEAN_ROADMAP["status"],
        "lean_roadmap_ref": _PACBAYES_LEAN_ROADMAP["ref"],
        "presets_label": "SAMPLE/MODELED — illustrative inputs, NOT measured empirics",
        "receipt_chain": "REAL (szl_khipu SHA3-256 hash chain; tamper-evident)",
        "receipt_signature": "DSSE_PLACEHOLDER (Sigstore not wired; honest)",
        "khipu": "Conjecture 2",
        "lambda": "Conjecture 1",
        "trust_ceiling": "never 100%",
        "fabricated_data": False,
        "locked8": _LOCKED8,
        "locked8_kernel": _LOCKED8_KERNEL,
        "locked8_note": "McAllester PAC-Bayes is NOT added to locked-8 "
                        "(Lean proof is an open SORRY/ROADMAP)",
    }


def _resolve_pacbayes_inputs(body: dict[str, Any]) -> dict[str, Any]:
    """Resolve {empirical_risk,kl,n,delta} either explicitly or from a preset.

    Explicit inputs win if all four are present. Otherwise a {family} (or
    {model, family}) preset is looked up. Returns a dict with the four numeric
    inputs plus provenance metadata (source, family, risk_units, input_label).
    Raises ValueError on bad/missing inputs.
    """
    explicit_keys = ("empirical_risk", "kl", "n", "delta")
    has_all_explicit = all(k in body and body[k] is not None for k in explicit_keys)

    if has_all_explicit:
        try:
            er = float(body["empirical_risk"])
            kl = float(body["kl"])
            n = int(body["n"])
            delta = float(body["delta"])
        except (TypeError, ValueError):
            raise ValueError(
                "empirical_risk, kl, delta must be numeric and n an integer")
        return {
            "empirical_risk": er, "kl": kl, "n": n, "delta": delta,
            "source": "explicit",
            "family": body.get("family"),
            "model": body.get("model"),
            "risk_units": body.get("risk_units",
                                   "normalized risk (dimensionless, [0,1]) "
                                   "unless otherwise specified by caller"),
            "input_label": "CALLER-SUPPLIED — labeling/validity is the caller's "
                           "responsibility; bound computation is exact",
        }

    family = body.get("family") or body.get("preset") or body.get("model")
    if family in _PACBAYES_PRESETS:
        p = _PACBAYES_PRESETS[family]
        return {
            "empirical_risk": float(p["empirical_risk"]),
            "kl": float(p["kl"]),
            "n": int(p["n"]),
            "delta": float(p["delta"]),
            "source": "preset",
            "family": family,
            "model": body.get("model"),
            "risk_units": p["risk_units"],
            "input_label": p["label"],
        }

    raise ValueError(
        "supply either explicit {empirical_risk, kl, n, delta} OR a known "
        "{family} preset (one of: " + ", ".join(sorted(_PACBAYES_PRESETS)) + ")")


def _do_certify(body: dict[str, Any]) -> dict[str, Any]:
    """Core PAC-Bayes certification: resolve inputs, compute the McAllester bound
    via szl_formulas (IMPORTED, not reimplemented), sign a Khipu receipt into the
    SHARED materials chain, and return the full honest response dict."""
    import szl_formulas  # IMPORT the proven-on-paper bound; do NOT reimplement
    import szl_khipu      # same idiom DEV 1 used (get_dag/emit on shared DAG)

    inp = _resolve_pacbayes_inputs(body)

    # Compute the McAllester PAC-Bayes bound — exact, delegated to szl_formulas.
    bound = float(szl_formulas.pac_bayes_mcallester(
        inp["empirical_risk"], inp["kl"], inp["n"], inp["delta"]))

    delta = inp["delta"]
    units = inp["risk_units"]
    certificate_text = (
        f"With probability >= 1 - delta (delta = {delta:g}) over training "
        f"distributions, the population risk <= {bound:.6g} "
        f"({units}). McAllester (1999) PAC-Bayes bound; computation exact; "
        f"Lean proof is an open SORRY/ROADMAP (not Lean-proven)."
    )

    dag = szl_khipu.get_dag(_KHIPU_ORGAN, ns="a11oy")
    receipt_payload = {
        "receipt_type": _PACBAYES_RECEIPT_TYPE,
        "organ": _KHIPU_ORGAN,
        "operation": "pac_bayes_certificate",
        "bound": bound,
        "inputs": {
            "empirical_risk": inp["empirical_risk"],
            "kl": inp["kl"],
            "n": inp["n"],
            "delta": inp["delta"],
            "source": inp["source"],
            "family": inp.get("family"),
            "model": inp.get("model"),
            "risk_units": units,
            "input_label": inp["input_label"],
        },
        "bound_formula": "R(Q) <= Rhat(Q) + sqrt((KL + ln(2*sqrt(n)/delta)) / (2n))",
        "certificate_text": certificate_text,
        "proof_status": _PACBAYES_PROOF_STATUS,
        "honesty": _pacbayes_honesty(),
        "lean_roadmap": _PACBAYES_LEAN_ROADMAP,
        "doctrine": "v11",
    }
    receipt = dag.emit("materials.certify", receipt_payload)

    return {
        "ok": True,
        "service": "materials.certify",
        "bound": bound,
        "inputs": receipt_payload["inputs"],
        "bound_formula": receipt_payload["bound_formula"],
        "certificate_text": certificate_text,
        "proof_status": _PACBAYES_PROOF_STATUS,
        "receipt": {
            "receipt_type": _PACBAYES_RECEIPT_TYPE,
            "organ": _KHIPU_ORGAN,
            "seq": receipt["seq"],
            "digest": receipt["digest"],
            "prev": receipt["prev"],
            "payload_digest": receipt["payload_digest"],
            "signature": receipt["signature"],
            "chain_head": dag.head(),
            "chain_depth": dag.depth(),
        },
        "honesty": _pacbayes_honesty(),
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def _presets_view() -> dict[str, Any]:
    """List the PAC-Bayes presets, each honestly labeled SAMPLE/MODELED."""
    presets = {}
    for fam, p in _PACBAYES_PRESETS.items():
        presets[fam] = {
            "empirical_risk": p["empirical_risk"],
            "kl": p["kl"],
            "n": p["n"],
            "delta": p["delta"],
            "risk_units": p["risk_units"],
            "label": p["label"],
        }
    return {
        "ok": True,
        "service": "materials.certify.presets",
        "organ": _KHIPU_ORGAN,
        "ns": "a11oy",
        "count": len(presets),
        "presets": presets,
        "presets_label": "SAMPLE/MODELED — illustrative inputs only; NOT measured "
                         "empirical risks of any deployed model",
        "bound_formula": "R(Q) <= Rhat(Q) + sqrt((KL + ln(2*sqrt(n)/delta)) / (2n))",
        "proof_status": _PACBAYES_PROOF_STATUS,
        "honesty": _pacbayes_honesty(),
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def register_certify(app, ns: str = "a11oy") -> list[str]:
    # NOTE: Request/JSONResponse are imported at MODULE level (top of file) for
    # the same reason DEV 1 documented — `from __future__ import annotations`
    # stringizes the `request: Request` annotation, so FastAPI must resolve it
    # from module globals; a function-local import would yield HTTP 422.
    async def _certify(request: Request):  # noqa: ANN202
        try:
            if request.method == "POST":
                try:
                    body = await request.json()
                except Exception:  # noqa: BLE001
                    body = {}
            else:
                body = dict(request.query_params)
                for k in ("empirical_risk", "kl", "delta"):
                    if k in body:
                        try:
                            body[k] = float(body[k])
                        except (TypeError, ValueError):
                            pass
                if "n" in body:
                    try:
                        body["n"] = int(float(body["n"]))
                    except (TypeError, ValueError):
                        pass
            if not isinstance(body, dict):
                body = {}
            result = _do_certify(body)
            return JSONResponse(result, headers={
                "x-szl-materials-bound": f"{result['bound']:.6g}",
                "x-szl-receipt-digest": result["receipt"]["digest"],
            })
        except ValueError as ve:
            return JSONResponse(
                {"ok": False, "error": str(ve),
                 "proof_status": _PACBAYES_PROOF_STATUS,
                 "honesty": _pacbayes_honesty()},
                status_code=400,
            )
        except Exception as e:  # noqa: BLE001 — self-contained, never crash register
            return JSONResponse(
                {"ok": False, "error": f"{e!r}",
                 "proof_status": _PACBAYES_PROOF_STATUS,
                 "honesty": _pacbayes_honesty()},
                status_code=500,
            )

    async def _presets():  # noqa: ANN202
        return JSONResponse(_presets_view())

    prefixes = [f"/api/{ns}/v1/materials", "/v1/materials"]
    routes: list[str] = []
    for p in prefixes:
        app.add_api_route(f"{p}/certify", _certify, methods=["POST", "GET"],
                          include_in_schema=True)
        app.add_api_route(f"{p}/certify/presets", _presets, methods=["GET"],
                          include_in_schema=True)
        routes.extend([f"{p}/certify", f"{p}/certify/presets"])
    return routes


# ===========================================================================
# DEV 3 SECTION — Immune-gated + energy-metered pipeline  (APPEND BELOW)
# ---------------------------------------------------------------------------
# DEV 3: define your routes in a `register_screen(app, ns)` helper here and add
# a call to it inside register() under the marked hook. Do NOT modify the DEV 1
# section.
# ===========================================================================
# (DEV 3 routes go here)


# ===========================================================================
# SHARED REGISTRATION — the single entry serve.py imports. Mounts the novelty
# group, then calls the later helpers IF they have been appended. One import in
# serve.py wires every group. Registered BEFORE the SPA catch-all so these JSON
# routes resolve LOCALLY and win ordering.
# ===========================================================================
def register(app, ns: str = "a11oy") -> dict:
    routes: list[str] = []
    routes.extend(_register_novelty(app, ns))

    # --- DEV 2/DEV 3 append hooks (no-op until their helpers are defined) ---
    for helper in ("register_certify", "register_screen"):
        fn = globals().get(helper)
        if callable(fn):
            try:
                extra = fn(app, ns)
                if isinstance(extra, (list, tuple)):
                    routes.extend(extra)
            except Exception as e:  # noqa: BLE001 — one group must not break others
                print(f"[{ns}] szl_materials {helper} FAILED: {e!r}", flush=True)

    print(f"[{ns}] szl_materials routes registered "
          f"(Crystal Novelty Certificate + appended groups, {len(routes)} routes)",
          flush=True)
    return {"ok": True, "ns": ns, "routes": routes}


# ---------------------------------------------------------------------------
# No-server self-test (proves fingerprint isometry-invariance + duplicate
# detection + chain honesty without a live server).
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    out: dict[str, Any] = {}

    # FCC aluminium, conventional cell (4 atoms), cubic 4.05 Å.
    al = {"a": 4.05, "b": 4.05, "c": 4.05, "alpha": 90, "beta": 90, "gamma": 90,
          "sites": [{"el": "Al", "x": 0, "y": 0, "z": 0},
                    {"el": "Al", "x": 0.5, "y": 0.5, "z": 0},
                    {"el": "Al", "x": 0.5, "y": 0, "z": 0.5},
                    {"el": "Al", "x": 0, "y": 0.5, "z": 0.5}]}
    fp1 = _compute_fingerprint(al)

    # Same crystal, TRANSLATED by (0.137, 0.5, 0.91) frac — must be identical fp.
    sh = 0.137, 0.5, 0.91
    al_t = dict(al, sites=[{"el": s["el"], "x": s["x"] + sh[0],
                            "y": s["y"] + sh[1], "z": s["z"] + sh[2]}
                           for s in al["sites"]])
    fp2 = _compute_fingerprint(al_t)
    assert fp1["fingerprint_digest"] == fp2["fingerprint_digest"], \
        "translation must not change the fingerprint"
    assert _l1_distance(fp1["vector"], fp2["vector"]) < 1e-9
    out["translation_invariant"] = True

    # A genuinely different crystal (different lattice param) -> different fp.
    cu = dict(al, a=3.61, b=3.61, c=3.61)
    fp3 = _compute_fingerprint(cu)
    assert fp3["fingerprint_digest"] != fp1["fingerprint_digest"]
    assert _l1_distance(fp1["vector"], fp3["vector"]) > _NOVELTY_TANI_EPS
    out["distinct_crystal_distinguished"] = True

    # Novelty flow against the shared registry + Khipu chain.
    r1 = _do_novelty(al)
    assert r1["novel"] is True and r1["registered_id"], r1
    r2 = _do_novelty(al)  # exact same crystal -> duplicate
    assert r2["novel"] is False and (r2["distance"] or 0.0) <= _NOVELTY_TANI_EPS, r2
    r3 = _do_novelty(cu)  # different -> novel again
    assert r3["novel"] is True, r3
    out["novel_then_duplicate_then_novel"] = [r1["novel"], r2["novel"], r3["novel"]]

    reg = _registry_view()
    assert reg["count"] == 2, reg
    assert reg["chain_verified"] is True, reg
    out["registry_count"] = reg["count"]
    out["chain_head"] = reg["chain_head"]

    print("szl_materials — self-test (PDD fingerprint + novelty + Khipu chain)")
    print(json.dumps(out, indent=2))
