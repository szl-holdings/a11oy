# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v10
"""
szl_brain — shared per-app BRAIN + UNIFIED LLM ROUTER, deployed identically on
every SZL Space.  Python port of the canonical TypeScript source-of-truth at
szl-holdings/platform/packages/llm-router/ (llm_router.ts).

Two things every Space gets from this one module:

  1. UNIFIED LLM ROUTER  — pick an LLM *tier* from the 13-axis Λ trust vector and
     emit a Λ-receipt for every routed call.  Mounted at /api/<space>/v1/llm/route.

  2. PER-APP BRAIN       — a thesis/formula slice keyed by the Space's anatomy role,
     served at /api/<space>/v1/brain/* and rendered at /brain.

HONESTY (Doctrine v10):
  - The Λ-receipt `signature` field is a PLACEHOLDER.  Sigstore CI (cosign/DSSE
    keyless) signing is NOT yet wired.  Labeled explicitly everywhere.
  - No model API key is wired into the HF Spaces, so the router returns an HONEST
    STUB for `response`; the tier-selection + Λ-receipt are real, deterministic math.
  - Canonical numbers are the locked Doctrine v10 set: 749 declarations / 14 unique
    axioms (15 raw, 1 dup) / 163 sorries (112 baseline + 51 Putnam) @ lutar-lean c7c0ba17.
"""
from __future__ import annotations

import math
import time
from datetime import datetime, timezone
from typing import Any

DOCTRINE = "v10"
CANONICAL = {
    "lutar_lean_ref": "lutar-v18.0.0 @ c7c0ba17",
    "declarations": 749,
    "axioms_unique": 14,
    "axioms_raw": 15,
    "axioms_dup": 1,
    "sorries": 163,
    "sorries_baseline": 112,
    "sorries_putnam": 51,
    "mcp_tools": 12,
    "policy_gates": 46,
    "anchor_formula_gates": 44,
    "lambda_uniqueness": "Conjecture (CAUCHY_ND sorry @ Uniqueness.lean:120 + missing symmetry axiom)",
    "source": "HONEST_SNAPSHOT from lean_numbers.json @ c7c0ba17 (lean_numbers.py canonical counter)",
}

SIGNATURE_PLACEHOLDER = "PLACEHOLDER — Sigstore CI signing not yet wired (Doctrine v10)"

# ---------------------------------------------------------------------------
# 5 LLM tiers — founder-locked (ROSIE_FULL_CAPABILITY_BRIEF_2026-05-31_2135.md §2)
# ---------------------------------------------------------------------------
TIERS: list[dict[str, Any]] = [
    {"id": "claude_sonnet_4_6", "rank": 0, "use": "default reasoning / explain-this-Space / casual Q&A", "why": "200K context, fast, cost-efficient"},
    {"id": "gemini_3_1_pro",    "rank": 1, "use": "long-form research / multi-source synthesis",          "why": "cost-efficient research"},
    {"id": "gpt_5_4",           "rank": 2, "use": "math / structured logic / Λ-gate eval / theorem citation", "why": "best at structured reasoning + math"},
    {"id": "claude_opus_4_8",   "rank": 3, "use": "complex multi-step orchestration / PRs / Lean proofs",  "why": "top-tier reasoning, 200K context"},
    {"id": "gpt_5_5",           "rank": 4, "use": "highest-stakes investor diligence answers",             "why": "top quality (tie with opus_4_8)"},
]
_BY_RANK = {t["rank"]: t for t in TIERS}


def lambda_aggregate(axis: list[float] | None) -> float:
    """Λ aggregator = geometric mean (matches Lutar.Λ k; A2 IsHomogeneous, A4 IsBounded)."""
    if not axis:
        return 0.5
    clamped = [min(1.0, max(1e-9, float(x))) for x in axis]
    logmean = sum(math.log(x) for x in clamped) / len(clamped)
    return math.exp(logmean)


def pick_tier(axis_scores: list[float] | None, max_tier: int = 4, task_hint: str = "") -> dict[str, Any]:
    """Trust→tier policy. high Λ → cheap fast; low Λ/adversarial → premium + extra gates."""
    L = lambda_aggregate(axis_scores)
    cap = min(4, max_tier if max_tier is not None else 4)
    if L >= 0.90:
        rank, reason = 0, f"Λ={L:.3f} ≥ 0.90 floor → high-trust fast tier"
    elif L >= 0.75:
        rank, reason = 2, f"Λ={L:.3f} in [0.75,0.90) → mid-trust structured tier"
    else:
        rank, reason = 3, f"Λ={L:.3f} < 0.75 (low-trust / adversarial) → premium tier + extra gates"
    hint = (task_hint or "").lower()
    floor = {"math": 2, "research": 1, "orchestration": 3, "diligence": 4}.get(hint)
    if floor is not None:
        rank = max(rank, floor)
        reason += f"; task_hint='{hint}' raised floor to rank {floor}"
    if rank > cap:
        rank = cap
        reason += f"; capped at max_tier={cap}"
    tier = _BY_RANK.get(rank, TIERS[0])
    return {"tier": tier, "reason": reason, "lambda": L}


def make_receipt(axis_scores: list[float] | None, max_tier: int = 4, task_hint: str = "") -> dict[str, Any]:
    sel = pick_tier(axis_scores, max_tier, task_hint)
    return {
        "schema": "szl.llm_route.lambda_receipt/v1",
        "lambda": round(sel["lambda"], 6),
        "axis_scores": axis_scores or [],
        "tier_used": sel["tier"]["id"],
        "tier_rank": sel["tier"]["rank"],
        "reason": sel["reason"],
        "doctrine": DOCTRINE,
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "signature": SIGNATURE_PLACEHOLDER,  # HONEST: not CI-signed yet
    }


def route(prompt: str, axis_scores: list[float] | None = None, max_tier: int = 4,
          require_lambda_receipt: bool = True, task_hint: str = "") -> dict[str, Any]:
    """Unified router: choose tier, (would) call LLM, return response + tier + Λ-receipt + latency."""
    t0 = time.time()
    receipt = make_receipt(axis_scores, max_tier, task_hint)
    response = (
        f"[HONEST STUB] would route to {receipt['tier_used']} (rank {receipt['tier_rank']}). "
        f"No model key wired in this Space; tier selection + Λ-receipt are real. "
        f"Reason: {receipt['reason']}"
    )
    out = {
        "response": response,
        "tier_used": receipt["tier_used"],
        "tier_rank": receipt["tier_rank"],
        "latency_ms": round((time.time() - t0) * 1000, 3),
        "doctrine": DOCTRINE,
    }
    if require_lambda_receipt:
        out["lambda_receipt"] = receipt
    return out


# ---------------------------------------------------------------------------
# PER-APP BRAIN — thesis/formula slice keyed by anatomy role.
# Each Space passes its role to brain_payload(role); the shared corpus lives here
# so the slices stay consistent across Spaces and Rosie can mirror ALL of them.
# ---------------------------------------------------------------------------

# Cortex theorems (amaru). Honest status from Doctrine v10 reconciliation.
THEOREMS = {
    "TH1": {"name": "Λ Conjecture (unique 13-axis aggregator)", "status": "CONJECTURE",
            "lean": "Lutar/Uniqueness.lean:120 (lutar_is_geomean, CAUCHY_ND sorry)",
            "note": "Open: Aczel 1966 Thm 5.1 + missing symmetry axiom. NOT a closed theorem."},
    "TH8": {"name": "GLR — Governed Loop Reachability", "status": "PROVEN",
            "lean": "Lutar/* (GLR proven on main @ c7c0ba17)",
            "note": "Bounded governed loops terminate at a receipt-attested fixpoint."},
    "TH10": {"name": "Conjecture 1 (not Theorem)", "status": "CONJECTURE",
             "lean": "tracked sorry",
             "note": "v9 mistakenly promoted to Theorem; v10 reverts to Conjecture 1 per org card."},
    "TH6": {"name": "DPI Soundness (Bekenstein bound, UN-BANNED)", "status": "PROVEN",
            "lean": "TH6_DPI_Soundness.lean:103", "note": "Real Lean proof; Bekenstein un-banned in v9, retained v10."},
    "TH13": {"name": "PAC-Bayes receipt-DAG bound", "status": "PARTIAL",
             "lean": "Lutar/PACBayes.lean (4 sorries), MadhavaBound.lean (2 sorries)",
             "note": "Lean-backed with tracked discharge sorries."},
}

# Immune theorems / witnesses (sentra).
IMMUNE = {
    "HUKLLA_SBOMProvenance": "SBOM provenance attestation gate (supply-chain integrity).",
    "drone_deny": "Default-deny posture for un-attested autonomous actors.",
    "OVERWATCH_R0513": "Rule R0513 — tamper / anomaly tripwire in the OVERWATCH ruleset.",
    "KS-18_contextuality_witness": "Kochen–Specker 18-vector contextuality witness (non-classical tamper detect).",
}

# Receipt structure (vessels) — Khipu Merkle DAG + DSSE envelope.
RECEIPT_STRUCT = {
    "khipu_merkle_dag": "Append-only Merkle DAG of receipts; each node = sha256(payload || parent_hashes).",
    "dsse_envelope": {
        "payloadType": "application/vnd.szl.receipt+json",
        "payload": "<base64 receipt>",
        "signatures": [{"sig": SIGNATURE_PLACEHOLDER, "keyid": "PENDING — Sigstore keyless not wired"}],
    },
    "summation_checked_integrity": "Σ(child digests) folded into parent; verify = recompute root digest.",
}

UDS = {
    "uds_bundle_integrity": "Universal Deploy System bundle = signed tarball + manifest digest.",
    "zarf_package_contract": "Zarf package: declared images + manifests; airgap-transferable; checksummed.",
    "deploy_contract": "deploy.yaml pins image digests + Λ-gate floor; refuse on digest mismatch.",
}

# a11oy gate composition rules (Brand Orchestration).
GATE_COMPOSITION = {
    "policy_gates": 46,
    "anchor_formula_gates": 44,
    "lambda_floor": 0.90,
    "composition_rules": [
        "AND-compose: a decision passes only if EVERY fired gate passes (conjunctive safety).",
        "Λ-floor: geometric-mean Λ across 13 axes must be ≥ 0.90 (soundnessAxiom).",
        "severity-indexed witnesses: higher severity ⇒ more attested witnesses required (thresholdPolicySeverity).",
        "monotone composition: adding a gate can only lower or keep Λ, never raise it (TH8 GLR-consistent).",
    ],
}

ROLE_SLICES = {
    "a11oy":   {"role": "Brand Orchestration / gates", "gate_composition": GATE_COMPOSITION,
                "formulas": "46 policy gates + 44 anchor formula gates", "lambda_floor": 0.90},
    "amaru":   {"role": "cortex / reasoning", "theorems": {k: THEOREMS[k] for k in ("TH1", "TH8", "TH10")},
                "chakras": ["root", "sacral", "solar", "heart", "throat", "third_eye", "crown"]},
    "sentra":  {"role": "immune", "immune": IMMUNE,
                "theorems": {k: THEOREMS[k] for k in ("TH1", "TH8")},
                "lambda_floor": 0.90},
    "vessels": {"role": "data pipeline / receipts", "receipt_structure": RECEIPT_STRUCT,
                "theorems": {k: THEOREMS[k] for k in ("TH8", "TH13")},
                "note": "Receipts chain into a Khipu Merkle DAG; PAC-Bayes bound (TH13) governs receipt-DAG generalization; GLR (TH8) ensures replay fixpoint."},
    "rosie":   {"role": "nervous system / cross-session — inherits EVERYTHING",
                "inherits": ["a11oy", "amaru", "sentra", "vessels", "uds-demo"]},
    "uds-demo": {"role": "deploy", "uds": UDS},
}


def brain_payload(space: str) -> dict[str, Any]:
    slice_ = ROLE_SLICES.get(space, {"role": "unknown"})
    return {
        "space": space,
        "brain": slice_,
        "llm_tiers": TIERS,
        "canonical": CANONICAL,
        "doctrine": DOCTRINE,
        "honesty": {
            "lambda_receipt_signature": SIGNATURE_PLACEHOLDER,
            "lambda_uniqueness": CANONICAL["lambda_uniqueness"],
            "numbers_source": CANONICAL["source"],
        },
    }
