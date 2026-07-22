#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""
a11oy_formula_tiers.py — served projection of the canonical formula registry
formulas and the real trust-math theorems that sit *outside* the locked baseline.

The proof-carrying formula registry is the source of truth for locked maturity;
this endpoint adds served explanations of what each Lean obligation ACTUALLY proves.
It exists because historical console copy described a locked set with semantic
governance meanings (F18 "DSSE seal", F19 "13-axis Λ geomean", F1 "gate-pass ⇒
Λ≥0.90", …) and cited anchor files (Lutar/Soundness.lean, STL.lean, Gates.lean,
Receipt.lean, Lambda.lean) that DO NOT EXIST in lutar-lean. The locked formulas in
Lutar/Puriq/Formulas/ProvedFormulas.lean prove conservative Nat/Int surrogates;
labelling them with the governance semantics they merely *motivate* is overclaiming.

The tiers (verify-it-yourself, never overclaim):
  1. LOCKED-PROVEN     — the five formulas admitted by formula-registry.v1,
                         labelled with WHAT IT ACTUALLY PROVES.
  2. SEMANTIC-VERIFIED — sorry-free real theorem proving a governance property, but
                         NOT in the locked set. This is where the real trust math
                         lives; present it proudly, but distinctly from the baseline.
  3. evidence-backed   — real runtime/algorithmic code, no Lean proof claim.
  4. CONJECTURE        — Λ unconditional uniqueness (machine-checked FALSE as stated),
                         Khipu BFT safety/liveness. Gray, NEVER green.

Pure-Python STDLIB only. Doctrine-safe: try/except-guarded register(app); the route
is pushed to the FRONT of app.router.routes so it wins over the Node proxy and SPA
catch-all. Λ = Conjecture 1 (NEVER a theorem). 0 runtime CDN. No key, no signing.
"""

from szl_formula_registry import (
    FORMULA_REGISTRY_DIGEST,
    FORMULA_REGISTRY_SIGNATURE_STATUS,
    LOCKED_PROVEN_COUNT,
    LOCKED_PROVEN_IDS,
    PAYLOAD as FORMULA_REGISTRY_PAYLOAD,
)

# lutar-lean files verified MISSING at depth-1 clone (2026-06-30). Never cite as anchors.
PHANTOM_ANCHORS = [
    "Lutar/Soundness.lean", "Lutar/STL.lean", "Lutar/Gates.lean",
    "Lutar/Receipt.lean", "Lutar/Lambda.lean",
]

# Tier 1 — LOCKED-PROVEN. Derived from the proof-carrying canonical registry.
# Conservative surrogates in Lutar/Puriq/Formulas/ProvedFormulas.lean.
LOCKED_PROVEN = [
    {"id": "F1", "proves": "Replay-hash determinism — identical canonical input ⇒ identical receipt hash.",
     "not": "NOT 'gate-pass ⇒ Λ ≥ 0.90'.",
     "lean_file": "Lutar/Puriq/Formulas/ProvedFormulas.lean", "lean_name": "f1_replay_hash_determinism"},
    {"id": "F11", "proves": "Ayni reciprocity conservation — b + c balance over Int.",
     "not": "NOT 'STL robustness ρ envelope'.",
     "lean_file": "Lutar/Puriq/Formulas/ProvedFormulas.lean", "lean_name": "f11_ayni_reciprocity_conservation"},
    {"id": "F12", "proves": "Kuramoto additive (p1 + p2 over k phases) — additivity, by decide.",
     "not": "NOT 'deny-by-default gate monotonicity'.",
     "lean_file": "Lutar/Puriq/Formulas/ProvedFormulas.lean", "lean_name": "f12_kuramoto_additive"},
    {"id": "F18", "proves": "Reed-Solomon parity count — (10-6 : Nat) = 4, erasure-tolerance arithmetic, by decide.",
     "not": "NOT 'DSSE seal binds canonical payload'.",
     "lean_file": "Lutar/Puriq/Formulas/ProvedFormulas.lean", "lean_name": "f18_reed_solomon_parity_count"},
    {"id": "F19", "proves": "Bekenstein additive — s1 ≤ s1 + s2, entropy-budget monotonicity over Nat.",
     "not": "NOT '13-axis Λ geometric-mean aggregate'.",
     "lean_file": "Lutar/Puriq/Formulas/ProvedFormulas.lean", "lean_name": "f19_bekenstein_additive"},
]

# Source-present theorems that the canonical registry keeps experimental.  They
# remain visible and useful; source presence alone never promotes them to locked.
EXPERIMENTAL = [
    {"id": entry["id"], "maturity": entry["maturity"],
     "locked_proven": entry["locked_proven"],
     "theorem_refs": entry["theorem_refs"], "source_path": entry["source_path"],
     "evidence_status": entry["evidence_status"]}
    for entry in FORMULA_REGISTRY_PAYLOAD["formulas"]
    if entry["maturity"] == "EXPERIMENTAL"
]

# Tier 2 — SEMANTIC-VERIFIED. Sorry-free real theorems (except where a residual sorry
# is disclosed) that prove the governance property, OUTSIDE the locked set. This is the
# real trust math: present proudly as "machine-checked, outside the frozen baseline."
SEMANTIC_VERIFIED = [
    {"id": "Λ-bound-max", "proves": "Λ ≤ max(axes) — aggregate upper bound. 0 sorries.",
     "lean_file": "Lutar/Bound.lean", "lean_name": "Λ_le_max", "sorries": 0},
    {"id": "Λ-bound-min", "proves": "min(axes) ≤ Λ — aggregate lower bound. 0 sorries.",
     "lean_file": "Lutar/Bound.lean", "lean_name": "min_le_Λ", "sorries": 0},
    {"id": "Λ-normalize", "proves": "Λ definition + axis normalization well-formed. 0 sorries.",
     "lean_file": "Lutar/Invariant.lean", "lean_name": "a3_normalize_proof", "sorries": 0},
    {"id": "Theorem-U", "proves": "Λ uniqueness CONDITIONAL on separability (the honest, proven conditional).",
     "lean_file": "Lutar/Round13/LambdaSeparable.lean", "lean_name": "lambda_unique_of_separable", "sorries": 0},
    {"id": "robustness", "proves": "STL/adversarial robustness preserved under composition.",
     "lean_file": "Lutar/Composition/AdversarialRobustness.lean", "lean_name": "robustness_preserved_by_composition", "sorries": 0},
    {"id": "F14-DSSE", "proves": "DSSE verifiability — under DISCLOSED axiom ecdsa_unforgeable.",
     "lean_file": "Lutar/Puriq/Formulas/PuriqFormulaLean.lean", "lean_name": "f14_dsse_verifiable", "sorries": 0,
     "axiom": "ecdsa_unforgeable (disclosed)"},
    {"id": "receipt-transduction", "proves": "Receipt transduction invariant (receipts.in ≡ receipts.out).",
     "lean_file": "Lutar/Transduction/ReceiptInvariant.lean", "lean_name": "receipt_transduction_invariant", "sorries": 1},
]

# Tier 4 — CONJECTURE / ADVISORY. Gray, NEVER green. The canonical Λ is a 13-axis
# weighted geometric mean, advisory, floor 0.90 — its unconditional uniqueness is FALSE
# as stated (machine-checked). Theorem U above is the proven *conditional* (Tier 2).
CONJECTURE = [
    {"id": "Conjecture-1", "claim": "Λ unconditional uniqueness.",
     "status": "machine-checked FALSE as stated; Theorem U is the proven conditional.", "color": "gray"},
    {"id": "Conjecture-2", "claim": "Khipu BFT safety.", "status": "conjecture, never proven.", "color": "gray"},
    {"id": "Conjecture-3", "claim": "Khipu BFT liveness.", "status": "conjecture, never proven.", "color": "gray"},
]

LAMBDA = {
    "definition": "13-axis weighted geometric mean",
    "role": "advisory",
    "floor": 0.90,
    "bounds": "SEMANTIC-VERIFIED (Λ_le_max / min_le_Λ, 0 sorries)",
    "uniqueness": "Theorem U conditional (SEMANTIC-VERIFIED) / Conjecture 1 unconditional (machine-checked FALSE)",
}

TIERS = {
    "model": "canonical registry-backed maturity model",
    "locked_count": LOCKED_PROVEN_COUNT,
    "locked_ids": list(LOCKED_PROVEN_IDS),
    "registry_digest": FORMULA_REGISTRY_DIGEST,
    "signature_status": FORMULA_REGISTRY_SIGNATURE_STATUS,
    "coverage_scope": FORMULA_REGISTRY_PAYLOAD["coverage_scope"],
    "phantom_anchors_never_cited": PHANTOM_ANCHORS,
    "lambda": LAMBDA,
    "tiers": {
        "LOCKED-PROVEN": LOCKED_PROVEN,
        "EXPERIMENTAL": EXPERIMENTAL,
        "SEMANTIC-VERIFIED": SEMANTIC_VERIFIED,
        "evidence-backed": [{"note": "runtime/algorithmic rules with real code, no Lean proof claim."}],
        "CONJECTURE": CONJECTURE,
    },
    "honest": ("Every locked entry is labelled with what its Lean obligation ACTUALLY proves "
               "(conservative Nat/Int surrogates), NOT the governance semantics it motivates. "
               "The real trust math (Λ bounds, Theorem U conditional, DSSE verifiability) is "
               "SEMANTIC-VERIFIED, machine-checked OUTSIDE the locked baseline. Conjectures are "
               "gray and NEVER rendered green. Verify it yourself: clone lutar-lean, open the "
               "cited file, count the sorries."),
}


def register(app):
    """Mount GET /api/a11oy/v1/formula-tiers at the FRONT of the router. Returns route list."""
    from fastapi.responses import JSONResponse
    added = []

    @app.get("/api/a11oy/v1/formula-tiers")
    async def _a11oy_formula_tiers():
        return JSONResponse(TIERS)

    try:
        r = app.router.routes.pop()
        app.router.routes.insert(0, r)
    except Exception:
        pass
    added.append("/api/a11oy/v1/formula-tiers")
    return added
