# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
"""a11oy_experimental_tier — ADDITIVE "Experimental Tier" surface for a11oy console.

Wires the full experimental (CI-green, NOT in locked-8) knowledge into a single
navigable console endpoint so the "Experimental (CI-green)" nav group in the SPA
can display real, honestly-labelled data.

HONESTY DOCTRINE (machine-relevant, doctrine v11):
  * LOCKED baseline = EXACTLY 8 {F1,F4,F7,F11,F12,F18,F19,F22} @ kernel c7c0ba17.
    This endpoint NEVER touches that count. It cannot grow it.
  * EXPERIMENTAL main @ dc64dd80 = CI-green, kernel-verified, ~80+ theorems
    (Waves 5-24, Theorem U conditional, Theorem 9 Merkle Functor, PAC-Bayes
    routing, agentic loop, binary_pinsker, etc.). NEVER folded into the locked 8.
  * Every item surfaced here carries the exact badge:
      "EXPERIMENTAL · CI-green · NOT in locked-8 · kernel c7c0ba17 unchanged"
  * Λ = Conjecture 1 — never a theorem on this surface.
  * The half-state (experimental items appearing as locked/proven) is the only
    unacceptable outcome. This module prevents that by always carrying tier labels.

Data is pulled IN-PROCESS from the already-live endpoints:
  - /api/a11oy/v1/proven/index  (Wave9/10 — 12 theorems, szl_wave910_proofs)
  - /api/a11oy/v1/honest        (experimental_scope summary from the locked endpoint)
  The "frontier 5 theorems" come from FORMULA_CORPUS_MASTER.md (static, baked in).
  PDDInjective 3 new axioms are surfaced as FOUNDER-GATED (not shown as proven).

Endpoints:
  GET /api/a11oy/v1/experimental/index   — full experimental tier JSON

Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>
Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
DCO: I certify that I contributed this work under the Apache-2.0 license.
"""
from __future__ import annotations

import datetime
from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse

# ---------------------------------------------------------------------------
# Doctrine constants — SINGLE SOURCE, never edit these silently.
# ---------------------------------------------------------------------------
_LOCKED_EIGHT = ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]
_LOCKED_KERNEL = "c7c0ba17"
_EXP_KERNEL = "dc64dd80"
_HONESTY_BADGE = (
    "EXPERIMENTAL \u00b7 CI-green \u00b7 NOT in locked-8 "
    "\u00b7 kernel c7c0ba17 unchanged"
)

# ---------------------------------------------------------------------------
# Frontier theorems — top 5 from FORMULA_CORPUS_MASTER.md §2.
# These are baked-in (the Lean repo is source-of-truth; no live fetch needed).
# ---------------------------------------------------------------------------
_FRONTIER_FIVE: list[dict[str, Any]] = [
    {
        "id": "lambda_unique_of_factors",
        "wave": "Waves 5-8 (Λ-uniqueness)",
        "name": "Conditional Λ uniqueness",
        "plain": (
            "Λ is the unique aggregator GIVEN factorisation Φ x = ∏ xᵢ^αᵢ. "
            "The gap to unconditional uniqueness is exactly A6 bisymmetry (OPEN). "
            "Conjecture 1 remains OPEN unconditionally."
        ),
        "status": "EXPERIMENTAL \u00b7 conditional-proven \u00b7 CI-green on main",
        "lean_file": "Lutar/Wave8/LambdaUnique.lean",
        "note": "\u039b = Conjecture 1; unconditional uniqueness machine-checked FALSE",
        "honesty_badge": _HONESTY_BADGE,
        "founder_gated": False,
    },
    {
        "id": "khipu_quorum_safety_conditional",
        "wave": "Khipu BFT (Conjecture 2 surface)",
        "name": "Conditional Khipu quorum safety",
        "plain": (
            "BFT safety under n\u22653f+1 and honest non-equivocation. "
            "Conjecture 2 (unconditional) is still OPEN."
        ),
        "status": "EXPERIMENTAL \u00b7 conditional-proven \u00b7 CI-green on main",
        "lean_file": "Lutar/Khipu/QuorumSafety.lean",
        "note": "Khipu BFT safety = Conjecture 2 \u2014 unconditional liveness = Conjecture 3",
        "honesty_badge": _HONESTY_BADGE,
        "founder_gated": False,
    },
    {
        "id": "binary_pinsker",
        "wave": "Waves 5-8 (information theory)",
        "name": "Binary Pinsker inequality",
        "plain": (
            "2(p\u2212q)\u00b2 \u2264 KL_bin(p,q). Axiom-free (no propext / choice needed)."
        ),
        "status": "EXPERIMENTAL \u00b7 axiom-free \u00b7 CI-green on main",
        "lean_file": "Lutar/Wave5/BinaryPinsker.lean",
        "note": "Axiom-free; NOT in locked-8; NEVER adds to locked count",
        "honesty_badge": _HONESTY_BADGE,
        "founder_gated": False,
    },
    {
        "id": "khipuReceiptChains_compositionalClosure",
        "wave": "Theorem 9 (Merkle Functor)",
        "name": "Khipu receipt functor \u2014 Theorem 9",
        "plain": (
            "Khipu receipt chains form a valid CategoryTheory.Functor; "
            "receipt chains are compositionally closed (Theorem 9)."
        ),
        "status": "EXPERIMENTAL \u00b7 CI-green on main",
        "lean_file": "Lutar/Wave9/KhipuFunctor.lean",
        "note": "Category-theoretic backing for the receipt chain; NOT in locked-8",
        "honesty_badge": _HONESTY_BADGE,
        "founder_gated": False,
    },
    {
        "id": "monotone_additive_linear",
        "wave": "Waves 5-8 (Cauchy / Acz\u00e9l)",
        "name": "Cauchy linearity via rational squeeze",
        "plain": (
            "Closes the Acz\u00e9l 1966 obligation: monotone + additive \u21d2 linear "
            "(proved via rational squeeze, no measure theory)."
        ),
        "status": "EXPERIMENTAL \u00b7 CI-green on main",
        "lean_file": "Lutar/Wave6/MonotoneAdditive.lean",
        "note": "Closes the Acz\u00e9l obligation; NOT in locked-8",
        "honesty_badge": _HONESTY_BADGE,
        "founder_gated": False,
    },
]

# ---------------------------------------------------------------------------
# Founder-gated items (surfaced as GATED, never as proven).
# ---------------------------------------------------------------------------
_FOUNDER_GATED: list[dict[str, Any]] = [
    {
        "id": "PDDInjective_3_axioms",
        "name": "PDDInjective.lean \u2014 3 new axioms",
        "plain": (
            "Three new axioms (CrystalIsometryClass, PDDFingerprint, pdd) in "
            "PDDInjective.lean. Need founder approval and a reviewable PR to bump "
            ".github/data/lean_numbers.json (drift gate currently fails at HEAD "
            "per Doctrine v7 \u00a73)."
        ),
        "status": "FOUNDER-GATED \u00b7 not yet approved",
        "note": "DO NOT surface as proven or experimental-CI-green until founder approves",
        "honesty_badge": "FOUNDER-GATED \u00b7 awaiting review",
        "founder_gated": True,
    },
]

# ---------------------------------------------------------------------------
# Experimental scope summary (from FORMULA_CORPUS_MASTER.md §2 + serve.py)
# These numbers are baked-in from the verified source; the live /honest endpoint
# also carries experimental_scope for cross-check.
# ---------------------------------------------------------------------------
_EXP_SCOPE: dict[str, Any] = {
    "kernel_commit": _EXP_KERNEL,
    "lean": "v4.18.0",
    "declarations": 1401,  # source-counted HEAD (FORMULA_CORPUS_MASTER §2)
    "axioms_unique": 25,
    "sorries": 270,
    "theorems_ci_green_approx": "80+",  # Waves 5-24 + Theorem U + Theorem 9 + agentic + binary_pinsker etc.
    "wave_range": "Waves 5-24",
    "notable_campaigns": [
        "agentic_loop (P1-P6)",
        "coder_formulas",
        "PAC-Bayes routing envelope",
        "stochastic processes / optional-stopping (Ville MC-4)",
        "Theorem 9 (Khipu Merkle Functor)",
        "Theorem U (conditional \u039b uniqueness)",
        "binary_pinsker (axiom-free)",
        "Wave9: Gershgorin, Merkle, Ville, RobustDeclass, PAC-Bayes, CovarianceIntersection",
        "Wave10: QuorumIntersection, DSSE-Token, NI-Composition, ReplayDeterminism, STL, ReachabilityRedundancy",
    ],
    "note": (
        "CI-green, kernel-verified (Waves 5-24 + agentic P1-P6 + airtight \u039b + coder + Theorem 9); "
        "NEVER folded into the locked count of 8; \u039b stays Conjecture 1"
    ),
}


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def handle_experimental_index(wave910_data: dict | None = None) -> dict:
    """Compose the full experimental tier index response.

    wave910_data: optional pre-fetched result from /api/a11oy/v1/proven/index
    so the caller can inject live data; None triggers a stub with the frontier 5.
    """
    wave910_cards: list[dict] = []
    wave910_count = 0
    wave910_status = "live"

    if wave910_data and isinstance(wave910_data, dict):
        wave910_cards = wave910_data.get("cards", [])
        wave910_count = wave910_data.get("count", len(wave910_cards))
        wave910_status = "live"
    else:
        wave910_status = "unavailable (szl_wave910_proofs not loaded)"

    return {
        "doctrine": {
            "version": "v11",
            "locked_kernel": _LOCKED_KERNEL,
            "locked_proven": _LOCKED_EIGHT,
            "locked_count": 8,
            "experimental_kernel": _EXP_KERNEL,
            "lambda_status": "Conjecture 1 \u2014 NOT a theorem",
        },
        "honesty_badge": _HONESTY_BADGE,
        "experimental_scope": _EXP_SCOPE,
        "frontier_five": _FRONTIER_FIVE,
        "wave910": {
            "status": wave910_status,
            "count": wave910_count,
            "endpoint": "/api/a11oy/v1/proven/index",
            "page": "/proven-formulas",
            "cards": wave910_cards,
            "note": (
                "Wave9 + Wave10 \u2014 12 theorems, each carrying verbatim #print axioms "
                "and an EXPERIMENTAL \u00b7 CI-green on main chip. "
                "LOCKED-proven = EXACTLY 8 {F1,F4,F7,F11,F12,F18,F19,F22}."
            ),
        },
        "founder_gated": _FOUNDER_GATED,
        "total_experimental_items": (
            len(_FRONTIER_FIVE)
            + wave910_count
            + len(_FOUNDER_GATED)
        ),
        "live_pages": {
            "proven_formulas": "/proven-formulas",
            "frontier_showcase": "/frontier",
        },
        "live_endpoints": {
            "wave910_index": "/api/a11oy/v1/proven/index",
            "wave910_gershgorin": "/api/a11oy/v1/proven/gershgorin",
            "wave910_ville": "/api/a11oy/v1/proven/ville",
            "wave910_replay": "/api/a11oy/v1/proven/replay",
            "wave910_quorum": "/api/a11oy/v1/proven/quorum",
            "wave910_dsse": "/api/a11oy/v1/proven/dsse",
            "wave910_stl": "/api/a11oy/v1/proven/stl",
            "wave910_covariance": "/api/a11oy/v1/proven/covariance",
            "wave910_mesh": "/api/a11oy/v1/proven/mesh",
            "frontier_manifest": "/api/a11oy/v1/frontier/manifest",
            "honest": "/api/a11oy/v1/honest",
        },
        "generated_at": _now_iso(),
    }


def register(app: FastAPI, ns: str = "a11oy") -> str:
    """Mount /api/<ns>/v1/experimental/index on the FastAPI app.

    Returns a status string for serve.py logging.
    Registered BEFORE the SPA catch-all; try/except-guarded in serve.py.
    """
    base = f"/api/{ns}/v1/experimental"

    @app.get(f"{base}/index", include_in_schema=False)
    async def _experimental_index() -> JSONResponse:
        """Full experimental tier manifest — honestly labelled, not in locked-8."""
        # Pull live Wave9/10 data from the in-process module if available.
        wave910_data: dict | None = None
        try:
            import szl_wave910_proofs as _w910
            wave910_data = _w910.MANIFEST  # type: ignore[attr-defined]
        except Exception:
            try:
                # Fallback: build from CARDS directly if MANIFEST attr is absent
                import szl_wave910_proofs as _w910  # noqa: F811
                wave910_data = {
                    "count": len(_w910.CARDS),
                    "cards": _w910.CARDS,
                    "doctrine": _w910.DOCTRINE,
                }
            except Exception:
                wave910_data = None

        return JSONResponse(handle_experimental_index(wave910_data))

    return (
        f"experimental tier mounted: GET {base}/index "
        f"(frontier-5 + Wave9/10 live pull + honest labels)"
    )
