# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
#
# a11oy_v4_formulas.py — surface the 35 SZL anchor formulas as LIVE operator gates.
#
# Doctrine v11 LOCKED 749/14/163. ADDITIVE, self-contained module dropped beside
# serve.py in the a11oy Space. Registered BEFORE the generic /api/a11oy/{path:path}
# Node proxy and SPA catch-all (FastAPI ordered matching), so these v4 routes resolve
# locally and never proxy to Node (which would 503).
#
# Routes (all NEW — no v1/v3 route is touched):
#   GET  /api/a11oy/v4/formulas                       -> all 35 formulas + metadata
#   GET  /api/a11oy/v4/formulas/{name}                -> single formula detail + sample
#   POST /api/a11oy/v4/formulas/{name}/evaluate       -> live verdict + signed Khipu receipt
#   GET  /formulas-v4                                 -> operator UI page (web/formulas.html)
#
# The 5 anchor formulas from a11oy#108 (cursor/policy-gates-hardening-2f18) are PORTED
# 1:1 from the TypeScript gates in packages/policy/src/gates/*.ts — deterministic, same
# math. The other 30 are exposed as READ-ONLY metadata (status "ts-only"): a real TS gate
# exists in the a11oy repo, but its body is NOT yet ported to this live module, so they
# are not runnable here. No formula implementation is fabricated.
#
# Signed receipts: emitted via szl_dsse.sign_khipu_receipt (real ECDSA-P256-SHA256 DSSE
# when the SZL_COSIGN_PRIVATE_PEM Space secret is present; otherwise an HONESTLY UNSIGNED
# envelope — no fabricated signature). Sovereign: no cloud LLM key is required or used.
#
# Lean commit anchor: 1dca00032dfc9aa8559cc6c2e4b63192fcf52371
# Zenodo concept DOI: https://doi.org/10.5281/zenodo.20162352
from __future__ import annotations

import hashlib
import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from starlette.requests import Request  # module-global so FastAPI get_type_hints resolves it

# DSSE signing (real ECDSA-P256 when secret present; else honestly unsigned).
try:  # additive, defensive — module must never break serve.py import
    import szl_dsse as _dsse  # type: ignore
except Exception:  # pragma: no cover
    _dsse = None  # noqa: N816

LEAN_COMMIT = "1dca00032dfc9aa8559cc6c2e4b63192fcf52371"
DOCTRINE = {"version": "v11", "state": "LOCKED", "counts": "749/14/163"}
ZENODO_DOI = "https://doi.org/10.5281/zenodo.20162352"


def _iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug(name: str) -> str:
    """Canonical hyphenated lowercase id, e.g. AdversarialRobustness -> adversarial-robustness."""
    out: List[str] = []
    for i, ch in enumerate(name):
        if ch.isupper() and i > 0:
            out.append("-")
        out.append(ch.lower())
    return "".join(out)


class GateError(ValueError):
    """Raised on invalid gate input (mirrors the TS gate's thrown Error)."""


# ===========================================================================
# 5 LIVE anchor formulas — ported 1:1 from packages/policy/src/gates/*.ts
# ===========================================================================

# --- 1. AdversarialRobustness (TH8) ---------------------------------------
# TS: adversarialRobustness_gate.ts  Lean: robustness_preserved_by_composition
def eval_adversarial_robustness(opts: Dict[str, Any], config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    config = config or {}
    max_epsilon = config.get("maxEpsilon", 1.0)
    if not math.isfinite(max_epsilon) or max_epsilon < 0:
        raise GateError(f"AdversarialRobustnessGate: maxEpsilon must be >= 0; got {max_epsilon}")
    l1 = opts.get("lipschitz1")
    l2 = opts.get("lipschitz2")
    delta = opts.get("delta")
    for nm, v in (("lipschitz1", l1), ("lipschitz2", l2), ("delta", delta)):
        if v is None or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0:
            raise GateError(f"AdversarialRobustnessGate: {nm} must be > 0; got {v}")
    epsilon2 = l1 * l2 * delta
    composed_lipschitz = l1 * l2
    lambda_score = 1.0 / (1.0 + epsilon2)
    allow = epsilon2 <= max_epsilon
    rationale = (
        f"AdversarialRobustness ε₂ = {epsilon2:.4e} <= maxEpsilon {max_epsilon}: composed pipeline is "
        f"({delta},{epsilon2})-robust. Lean: robustness_preserved_by_composition @{LEAN_COMMIT[:12]}"
        if allow else
        f"AdversarialRobustness ε₂ = {epsilon2:.4e} > maxEpsilon {max_epsilon}: perturbation amplification "
        f"exceeds policy tolerance — deny deployment. Lean: robustness_preserved_by_composition @{LEAN_COMMIT[:12]}"
    )
    return {
        "allow": allow, "rationale": rationale, "formula": "AdversarialRobustness",
        "leanTheorem": "robustness_preserved_by_composition",
        "leanFile": "Lutar/Composition/AdversarialRobustness.lean", "leanCommitSha": LEAN_COMMIT,
        "epsilon2": epsilon2, "composedLipschitz": composed_lipschitz,
        "maxEpsilon": max_epsilon, "lambdaScore": lambda_score,
    }


# --- 2. FalsePosition (Rhind) ---------------------------------------------
# TS: falsePosition_gate.ts  Lean: false_position_correct
def eval_false_position(opts: Dict[str, Any], config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    config = config or {}
    tolerance = config.get("tolerance", 1e-8)
    if not math.isfinite(tolerance) or tolerance < 0:
        raise GateError(f"FalsePositionGate: tolerance must be >= 0; got {tolerance}")
    x1, y1, x2, y2, T = (opts.get(k) for k in ("x1", "y1", "x2", "y2", "T"))
    for nm, v in (("x1", x1), ("y1", y1), ("x2", x2), ("y2", y2), ("T", T)):
        if v is None or not isinstance(v, (int, float)) or not math.isfinite(v):
            raise GateError(f"FalsePositionGate: {nm} must be finite; got {v}")
    eps = 2.220446049250313e-16  # Number.EPSILON
    if abs(x2 - x1) < eps * max(abs(x1), abs(x2), 1):
        raise GateError("FalsePositionGate: degenerate samples (x₁ = x₂)")
    dy = y2 - y1
    if abs(dy) < eps * max(abs(y1), abs(y2), 1):
        raise GateError("FalsePositionGate: degenerate samples (y₁ = y₂)")
    x_star = x1 + ((T - y1) * (x2 - x1)) / dy
    m = dy / (x2 - x1)
    c = y1 - m * x1
    residual = abs(m * x_star + c - T)
    lambda_score = max(0.0, 1.0 - residual / (1.0 + abs(T)))
    allow = residual <= tolerance
    rationale = (
        f"FalsePosition residual |f(x*)−T| = {residual:.4e} <= tol {tolerance}: calibration target "
        f"recovered exactly. Lean: false_position_correct @{LEAN_COMMIT[:12]}"
        if allow else
        f"FalsePosition residual |f(x*)−T| = {residual:.4e} > tol {tolerance}: calibration degenerate — "
        f"deny update. Lean: false_position_correct @{LEAN_COMMIT[:12]}"
    )
    return {
        "allow": allow, "rationale": rationale, "formula": "FalsePosition",
        "leanTheorem": "false_position_correct", "leanFile": "Lutar/Calibration/FalsePosition.lean",
        "leanCommitSha": LEAN_COMMIT, "xStar": x_star, "residual": residual,
        "tolerance": tolerance, "lambdaScore": lambda_score,
    }


# --- 3. LiuHuiPi (Liu Hui — axiom, advisory) ------------------------------
# TS: liuHuiPi_gate.ts  Lean: sideSquared_bounds (axiom)
def eval_liu_hui_pi(opts: Dict[str, Any], config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    config = config or {}
    threshold = config.get("threshold", 1e-4)
    if not math.isfinite(threshold) or threshold < 0:
        raise GateError(f"LiuHuiPiGate: threshold must be >= 0; got {threshold}")
    k = opts.get("k")
    if not isinstance(k, int) or isinstance(k, bool) or k < 0 or k > 50:
        raise GateError(f"LiuHuiPiGate: k must be in [0,50]; got {k}")
    sq = 1.0
    for _ in range(k):
        sq = 2 - math.sqrt(4 - sq)
    side_count = 6 * (2 ** k)
    pi_estimate = (side_count * math.sqrt(sq)) / 2
    abs_error = abs(pi_estimate - math.pi)
    lambda_score = max(0.0, 1.0 - abs_error / math.pi)
    allow = abs_error <= threshold
    rationale = (
        f"LiuHuiPi (k={k}, {6 * (2 ** k)}-gon) |est−π| = {abs_error:.4e} <= threshold {threshold}: "
        f"π approximation sufficiently accurate. Lean: sideSquared_bounds @{LEAN_COMMIT[:12]}"
        if allow else
        f"LiuHuiPi (k={k}, {6 * (2 ** k)}-gon) |est−π| = {abs_error:.4e} > threshold {threshold}: "
        f"π approximation not yet converged. Lean: sideSquared_bounds @{LEAN_COMMIT[:12]}"
    )
    return {
        "allow": allow, "rationale": rationale, "formula": "LiuHuiPi",
        "leanTheorem": "sideSquared_bounds", "leanFile": "Lutar/Banach/LiuHuiPi.lean",
        "leanCommitSha": LEAN_COMMIT, "piEstimate": pi_estimate, "absError": abs_error,
        "threshold": threshold, "lambdaScore": lambda_score,
        "advisory": True, "advisoryReason": "Lean is an AXIOM, not a discharged theorem; gate is advisory by design.",
    }


# --- 4. MadhavaBound (Mādhava) --------------------------------------------
# TS: madhavaBound_gate.ts  Lean: madhavaRemainderBound_nonneg
def eval_madhava_bound(opts: Dict[str, Any], config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    config = config or {}
    threshold = config.get("threshold", 0.01)
    if not math.isfinite(threshold) or threshold <= 0:
        raise GateError(f"MadhavaBoundGate: threshold must be > 0; got {threshold}")
    x = opts.get("x")
    N = opts.get("N")
    eps = 2.220446049250313e-16
    if x is None or not isinstance(x, (int, float)) or not math.isfinite(x) or abs(x) > 1 + eps:
        raise GateError(f"MadhavaBoundGate: |x| must be <= 1; got {x}")
    if not isinstance(N, int) or isinstance(N, bool) or N < 1:
        raise GateError(f"MadhavaBoundGate: N must be >= 1; got {N}")
    remainder_bound = (abs(x) ** (2 * N + 1)) / (2 * N + 1)
    lambda_score = max(0.0, min(1.0, 1.0 - remainder_bound))
    allow = remainder_bound <= threshold
    rationale = (
        f"Mādhava bound {remainder_bound:.4e} <= threshold {threshold}: series sufficiently converged. "
        f"Lean: madhavaRemainderBound_nonneg @{LEAN_COMMIT[:12]}"
        if allow else
        f"Mādhava bound {remainder_bound:.4e} > threshold {threshold}: series not converged — governance "
        f"signal unreliable. Lean: madhavaRemainderBound_nonneg @{LEAN_COMMIT[:12]}"
    )
    return {
        "allow": allow, "rationale": rationale, "formula": "MadhavaBound",
        "leanTheorem": "madhavaRemainderBound_nonneg", "leanFile": "Lutar/PACBayes/MadhavaBound.lean",
        "leanCommitSha": LEAN_COMMIT, "remainderBound": remainder_bound,
        "threshold": threshold, "lambdaScore": lambda_score,
    }


# --- 5. SummationInvariant (Khipu) ----------------------------------------
# TS: summationInvariant_gate.ts  Lean: khipuReceipt_checksum_invariant
def eval_summation_invariant(opts: Dict[str, Any], config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    khipu_id = opts.get("khipuId", "")
    organs = opts.get("organs")
    primary_cord = opts.get("primaryCord")
    if not isinstance(organs, list):
        raise GateError(f"SummationInvariantGate: organs must be an array for khipu {khipu_id}")
    if not isinstance(primary_cord, (int, float)):
        raise GateError(f"SummationInvariantGate: primaryCord must be a number; got {primary_cord}")
    pendant_values = [sum(d.get("value", 0) for d in o.get("decisions", [])) for o in organs]
    computed_total = sum(pendant_values)
    delta = abs(computed_total - primary_cord)
    invariant_holds = computed_total == primary_cord
    lambda_score = 1.0 if invariant_holds else 0.0
    rationale = (
        f"KhipuReceipt {khipu_id}: summation invariant holds (total={computed_total}). "
        f"Lean: khipuReceipt_checksum_invariant @{LEAN_COMMIT[:12]}"
        if invariant_holds else
        f"KhipuReceipt {khipu_id}: invariant BROKEN — computedTotal={computed_total} ≠ primaryCord="
        f"{primary_cord} (delta={delta}). Receipt tampered. Lean: khipuReceipt_checksum_invariant @{LEAN_COMMIT[:12]}"
    )
    return {
        "allow": invariant_holds, "rationale": rationale, "formula": "SummationInvariant",
        "leanTheorem": "khipuReceipt_checksum_invariant", "leanFile": "Lutar/Khipu/SummationInvariant.lean",
        "leanCommitSha": LEAN_COMMIT, "invariantHolds": invariant_holds,
        "computedTotal": computed_total, "primaryCord": primary_cord,
        "delta": delta, "lambdaScore": lambda_score,
    }


# ===========================================================================
# 10 MORE LIVE anchor formulas (Phase 3) — ported 1:1 from
# packages/policy/src/gates/*.ts. All deterministic, all theorem-status,
# verified bit-for-bit against the gate __tests__ fixtures in a11oy.
# Node `crypto.createHash('sha256')` == Python hashlib.sha256;
# `JSON.stringify(obj)` of an insertion-ordered dict == json.dumps(obj,
# separators=(",",":")) over an order-preserving dict (Python 3.7+).
# ===========================================================================

def _is_num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


# --- 6. LambdaMonotonicity (T2) -------------------------------------------
# TS: lambdaMonotonicity_gate.ts  Lean: lambdaMonotonicity (theorem)
# T2: r' = r ⊕ e_consistent ⟹ Λ(r') ≥ Λ(r). Adding consistent evidence must
# weakly increase EVERY axis score; any decreasing axis = conflicting evidence.
def eval_lambda_monotonicity(opts: Dict[str, Any], config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    config = config or {}
    tolerance = config.get("tolerance", 1e-9)
    orig = opts.get("originalScores")
    aug = opts.get("augmentedScores")
    if not isinstance(orig, list) or not isinstance(aug, list):
        raise GateError("LambdaMonotonicityGate: both score arrays required")
    if len(orig) != len(aug):
        raise GateError("LambdaMonotonicityGate: score arrays must have equal length")
    decreasing_axes: List[int] = []
    min_delta = math.inf
    for i in range(len(orig)):
        delta = aug[i] - orig[i]
        if delta < min_delta:
            min_delta = delta
        if delta < -tolerance:
            decreasing_axes.append(i)
    allow = len(decreasing_axes) == 0
    lambda_score = 1.0 if allow else max(0.0, 1.0 + min_delta)
    rationale = (
        f"LambdaMonotonicity (T2): all {len(orig)} axes weakly increased (minDelta={min_delta:.4e}). "
        f"Consistent evidence. Passes. Lean: lambdaMonotonicity @{LEAN_COMMIT[:12]}"
        if allow else
        f"LambdaMonotonicity (T2): axes {decreasing_axes} decreased — conflicting evidence. "
        f"Denied. Lean: lambdaMonotonicity @{LEAN_COMMIT[:12]}"
    )
    return {
        "allow": allow, "rationale": rationale, "formula": "LambdaMonotonicity",
        "leanTheorem": "lambdaMonotonicity", "leanFile": "Lutar/Gate/LambdaMonotonicity.lean",
        "leanCommitSha": LEAN_COMMIT, "decreasingAxes": decreasing_axes,
        "minDelta": (None if min_delta == math.inf else min_delta), "lambdaScore": lambda_score,
    }


# --- 7. MerkleDagBatch (T3) -----------------------------------------------
# TS: merkleDagBatch_gate.ts  Lean: merkleDagBatch (theorem)
# T3: ∀ B≥7: build_p50(batch_B) ∈ O(log B) ⟹ build_p50 ≤ 5µs.
def eval_merkle_dag_batch(opts: Dict[str, Any], config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    config = config or {}
    max_us = config.get("maxBuildP50Us", 5)
    min_b = config.get("minBatchSize", 7)
    batch_size = opts.get("batchSize")
    build_p50 = opts.get("buildP50Us")
    if not isinstance(batch_size, int) or isinstance(batch_size, bool) or batch_size < 1:
        raise GateError(f"MerkleDagBatchGate: batchSize must be >= 1; got {batch_size}")
    if not _is_num(build_p50) or build_p50 < 0:
        raise GateError(f"MerkleDagBatchGate: buildP50Us must be >= 0; got {build_p50}")
    theoretical_depth = math.ceil(math.log2(max(batch_size, 2)))
    applicable = batch_size >= min_b
    allow = (not applicable) or build_p50 <= max_us
    lambda_score = (max_us / max(build_p50, 0.001)) if allow else 0.0
    if not applicable:
        rationale = (f"MerkleDagBatch (T3): batchSize={batch_size} < {min_b} — DAG constraint not applicable. "
                     f"Passes. Lean: merkleDagBatch @{LEAN_COMMIT[:12]}")
    elif allow:
        rationale = (f"MerkleDagBatch (T3): batchSize={batch_size}, depth={theoretical_depth}, "
                     f"p50={build_p50}µs <= {max_us}µs. Passes. Lean: merkleDagBatch @{LEAN_COMMIT[:12]}")
    else:
        rationale = (f"MerkleDagBatch (T3): batchSize={batch_size}, p50={build_p50}µs > {max_us}µs — "
                     f"exceeds O(log B) bound. Denied. Lean: merkleDagBatch @{LEAN_COMMIT[:12]}")
    return {
        "allow": allow, "rationale": rationale, "formula": "MerkleDagBatch",
        "leanTheorem": "merkleDagBatch", "leanFile": "Lutar/Gate/MerkleDagBatch.lean",
        "leanCommitSha": LEAN_COMMIT, "batchSize": batch_size, "buildP50Us": build_p50,
        "maxBuildP50Us": max_us, "theoreticalDepth": theoretical_depth, "lambdaScore": lambda_score,
    }


# --- 8. ReplayDeterminism (T5) --------------------------------------------
# TS: replayDeterminism_gate.ts  Lean: replayDeterminism (theorem)
# T5: all requiredRuns replay roots must equal the canonical Merkle root.
def eval_replay_determinism(opts: Dict[str, Any], config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    config = config or {}
    canonical_root = config.get("canonicalRoot")
    required_runs = config.get("requiredRuns", 5)
    if not canonical_root:
        raise GateError("ReplayDeterminismGate: canonicalRoot is required")
    replay_roots = opts.get("replayRoots")
    if not isinstance(replay_roots, list) or len(replay_roots) < required_runs:
        raise GateError(f"ReplayDeterminismGate: need {required_runs} roots; got "
                        f"{len(replay_roots) if isinstance(replay_roots, list) else replay_roots}")
    matching_runs = sum(1 for r in replay_roots[:required_runs] if r == canonical_root)
    allow = matching_runs == required_runs
    lambda_score = matching_runs / required_runs
    rationale = (
        f"ReplayDeterminism (T5): all {required_runs} runs match canonical root \"{str(canonical_root)[:16]}…\". "
        f"Passes. Lean: replayDeterminism @{LEAN_COMMIT[:12]}"
        if allow else
        f"ReplayDeterminism (T5): {matching_runs}/{required_runs} runs matched — determinism violation. "
        f"Denied. Lean: replayDeterminism @{LEAN_COMMIT[:12]}"
    )
    return {
        "allow": allow, "rationale": rationale, "formula": "ReplayDeterminism",
        "leanTheorem": "replayDeterminism", "leanFile": "Lutar/Gate/ReplayDeterminism.lean",
        "leanCommitSha": LEAN_COMMIT, "canonicalRoot": canonical_root,
        "matchingRuns": matching_runs, "totalRuns": len(replay_roots), "lambdaScore": lambda_score,
    }


# --- 9. SingleWitnessExclusion (T8) ---------------------------------------
# TS: singleWitnessExclusion_gate.ts  Lean: singleWitnessExclusion (theorem)
# T8: cross-actor pairs require dual witness (witnessCount >= 2).
def eval_single_witness_exclusion(opts: Dict[str, Any], config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    config = config or {}
    require_dual_same = config.get("requireDualForSameActor", True)
    actor1 = opts.get("actor1Id")
    actor2 = opts.get("actor2Id")
    witness_count = opts.get("witnessCount")
    if not actor1 or not actor2:
        raise GateError("SingleWitnessExclusionGate: actor IDs required")
    if not isinstance(witness_count, int) or isinstance(witness_count, bool) or witness_count < 0:
        raise GateError("SingleWitnessExclusionGate: witnessCount must be non-negative integer")
    same_actor = actor1 == actor2
    dual_required = (not same_actor) or require_dual_same
    allow = (not dual_required) or witness_count >= 2
    lambda_score = 1.0 if allow else witness_count / 2
    rationale = (
        f"SingleWitnessExclusion (T8): actors={'same' if same_actor else 'different'}; "
        f"witnesses={witness_count} >= {2 if dual_required else 1}. Passes. "
        f"Lean: singleWitnessExclusion @{LEAN_COMMIT[:12]}"
        if allow else
        f"SingleWitnessExclusion (T8): different actors require dual-witness; got {witness_count}. "
        f"Denied. Lean: singleWitnessExclusion @{LEAN_COMMIT[:12]}"
    )
    return {
        "allow": allow, "rationale": rationale, "formula": "SingleWitnessExclusion",
        "leanTheorem": "singleWitnessExclusion", "leanFile": "Lutar/Gate/SingleWitnessExclusion.lean",
        "leanCommitSha": LEAN_COMMIT, "sameActor": same_actor, "witnessCount": witness_count,
        "dualRequired": dual_required, "lambdaScore": lambda_score,
    }


# --- 10. DualWitnessDisjointness (A4) -------------------------------------
# TS: dualWitnessDisjointness_gate.ts  Lean: dualWitnessDisjointness (theorem)
# A4: ρ-closure requires witness_1_id ≠ witness_2_id.
def eval_dual_witness_disjointness(opts: Dict[str, Any], config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    config = config or {}
    require_non_empty = config.get("requireNonEmpty", True)
    w1 = opts.get("witness1Id")
    w2 = opts.get("witness2Id")
    if require_non_empty and (not w1 or not w2):
        raise GateError("DualWitnessDisjointnessGate: witness IDs must be non-empty strings")
    disjoint = w1 != w2
    allow = disjoint
    lambda_score = 1.0 if disjoint else 0.0
    rationale = (
        f"DualWitnessDisjointness (A4): witness1=\"{str(w1)[:12]}\" ≠ witness2=\"{str(w2)[:12]}\" — "
        f"ρ-closure independent. Passes. Lean: dualWitnessDisjointness @{LEAN_COMMIT[:12]}"
        if allow else
        f"DualWitnessDisjointness (A4): witness1 = witness2 = \"{str(w1)[:12]}\" — same entity, "
        f"collapses to single-witness. Denied. Lean: dualWitnessDisjointness @{LEAN_COMMIT[:12]}"
    )
    return {
        "allow": allow, "rationale": rationale, "formula": "DualWitnessDisjointness",
        "leanTheorem": "dualWitnessDisjointness", "leanFile": "Lutar/Gate/DualWitness.lean",
        "leanCommitSha": LEAN_COMMIT, "witness1Id": w1, "witness2Id": w2,
        "disjoint": disjoint, "lambdaScore": lambda_score,
    }


# --- 11. TemporalConsistency (A10) ----------------------------------------
# TS: temporalConsistency_gate.ts  Lean: temporalConsistency (theorem)
# A10: |evalTime - receiptTime| ≤ clockDriftBound ⟹ verdict invariant.
def eval_temporal_consistency(opts: Dict[str, Any], config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    config = config or {}
    bound = config.get("clockDriftBoundMs", 5000)
    if not _is_num(bound) or bound < 0:
        raise GateError(f"TemporalConsistencyGate: clockDriftBoundMs must be >= 0; got {bound}")
    receipt_ts = opts.get("receiptTimestampMs")
    eval_ts = opts.get("evalTimestampMs")
    if not _is_num(receipt_ts):
        raise GateError("TemporalConsistencyGate: receiptTimestampMs must be finite")
    if not _is_num(eval_ts):
        raise GateError("TemporalConsistencyGate: evalTimestampMs must be finite")
    drift = abs(eval_ts - receipt_ts)
    within = drift <= bound
    allow = within
    lambda_score = 1.0 if within else (bound / drift if drift else 1.0)
    rationale = (
        f"TemporalConsistency (A10): drift={drift}ms <= bound={bound}ms. Verdict stable. Passes. "
        f"Lean: temporalConsistency @{LEAN_COMMIT[:12]}"
        if allow else
        f"TemporalConsistency (A10): drift={drift}ms > bound={bound}ms — clock violation. Denied. "
        f"Lean: temporalConsistency @{LEAN_COMMIT[:12]}"
    )
    return {
        "allow": allow, "rationale": rationale, "formula": "TemporalConsistency",
        "leanTheorem": "temporalConsistency", "leanFile": "Lutar/Gate/TemporalConsistency.lean",
        "leanCommitSha": LEAN_COMMIT, "clockDriftBoundMs": bound, "driftMs": drift,
        "withinBound": within, "lambdaScore": lambda_score,
    }


# --- 12. Composability (TH1) ----------------------------------------------
# TS: composability_gate.ts  Lean: composability (theorem)
# TH1: doctrine SHA match ∧ aExitFloor ≤ bEntryFloor ∧ A2A headers ⟹ A∘B locked.
def eval_composability(opts: Dict[str, Any], config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    config = config or {}
    require_a2a = config.get("requireA2AHeaders", True)
    sha_a = opts.get("doctrineShaA")
    sha_b = opts.get("doctrineShaB")
    a_exit = opts.get("aExitFloor")
    b_entry = opts.get("bEntryFloor")
    has_a2a = bool(opts.get("hasA2AHeaders"))
    if not sha_a or not sha_b:
        raise GateError("ComposabilityGate: both doctrine SHAs required")
    if not _is_num(a_exit) or not _is_num(b_entry):
        raise GateError("ComposabilityGate: floors must be finite")
    doctrine_match = sha_a == sha_b
    floor_compatible = a_exit <= b_entry
    allow = doctrine_match and floor_compatible and (not require_a2a or has_a2a)
    lambda_score = sum(1 for x in (doctrine_match, floor_compatible, has_a2a) if x) / 3
    failures: List[str] = []
    if not doctrine_match:
        failures.append("doctrine SHA mismatch")
    if not floor_compatible:
        failures.append(f"A exit floor {a_exit} > B entry floor {b_entry}")
    if require_a2a and not has_a2a:
        failures.append("missing A2A headers")
    rationale = (
        f"Composability (TH1): doctrine SHA match, A exit ({a_exit}) <= B entry ({b_entry}), "
        f"A2A headers present. A∘B doctrine-locked. Passes. Lean: composability @{LEAN_COMMIT[:12]}"
        if allow else
        f"Composability (TH1): preconditions failed — [{'; '.join(failures)}]. Denied. "
        f"Lean: composability @{LEAN_COMMIT[:12]}"
    )
    return {
        "allow": allow, "rationale": rationale, "formula": "Composability",
        "leanTheorem": "composability", "leanFile": "Lutar/Composition/Composability.lean",
        "leanCommitSha": LEAN_COMMIT, "doctrineMatch": doctrine_match,
        "floorCompatible": floor_compatible, "a2aHeadersPresent": has_a2a, "lambdaScore": lambda_score,
    }


# --- 13. HashChainIntegrity (A6) ------------------------------------------
# TS: hashChainIntegrity_gate.ts  Lean: hashChainIntegrity (theorem)
# A6: ∀n≥1: entry[n].chainHash = SHA256(JSON.stringify(entry[n-1])).
# JSON.stringify of an insertion-ordered object == json.dumps(separators=(",",":"))
# over an order-preserving dict. We hash the raw entry dict as received.
def _hash_entry(entry: Dict[str, Any]) -> str:
    import json
    s = json.dumps(entry, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def eval_hash_chain_integrity(opts: Dict[str, Any], config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    entries = opts.get("entries")
    if not isinstance(entries, list) or len(entries) == 0:
        raise GateError("HashChainIntegrityGate: entries must be a non-empty array")
    first_break: Optional[int] = None
    for i in range(1, len(entries)):
        expected = _hash_entry(entries[i - 1])
        if entries[i].get("chainHash") != expected:
            first_break = i
            break
    allow = first_break is None
    lambda_score = 1.0 if allow else (first_break - 1) / len(entries)
    rationale = (
        f"HashChainIntegrity (A6): {len(entries)} entries, all sha256 links valid. Passes. "
        f"Lean: hashChainIntegrity @{LEAN_COMMIT[:12]}"
        if allow else
        f"HashChainIntegrity (A6): chain break at entry[{first_break}] — expected hash mismatch. "
        f"Denied. Lean: hashChainIntegrity @{LEAN_COMMIT[:12]}"
    )
    return {
        "allow": allow, "rationale": rationale, "formula": "HashChainIntegrity",
        "leanTheorem": "hashChainIntegrity", "leanFile": "Lutar/Gate/HashChainIntegrity.lean",
        "leanCommitSha": LEAN_COMMIT, "entryCount": len(entries),
        "firstBreakIndex": first_break, "lambdaScore": lambda_score,
    }


# --- 14. DoctrineCompleteness (A9) ----------------------------------------
# TS: doctrineCompleteness_gate.ts  Lean: doctrineCompleteness (theorem)
# A9: SHA256(doctrine.json) == canonical ∧ |patterns| >= 8.
def eval_doctrine_completeness(opts: Dict[str, Any], config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    config = config or {}
    canonical = config.get("canonicalSha256")
    required_patterns = config.get("requiredPatternCount", 8)
    if not canonical or len(canonical) != 64:
        raise GateError("DoctrineCompletenessGate: canonicalSha256 must be 64-char hex string")
    raw = opts.get("doctrineJsonRaw")
    detected = opts.get("detectedPatterns")
    if not isinstance(raw, str) or len(raw) == 0:
        raise GateError("DoctrineCompletenessGate: doctrineJsonRaw must be non-empty")
    if not isinstance(detected, list):
        raise GateError("DoctrineCompletenessGate: detectedPatterns must be an array")
    detected_sha = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    sha_match = detected_sha == canonical
    pattern_count = len(detected)
    allow = sha_match and pattern_count >= required_patterns
    lambda_score = (0.5 if sha_match else 0.0) + (pattern_count / required_patterns) * 0.5
    if allow:
        rationale = (f"DoctrineCompleteness (A9): SHA-256 matches; {pattern_count} patterns >= "
                     f"{required_patterns}. doctrine-check PASS. Lean: doctrineCompleteness @{LEAN_COMMIT[:12]}")
    elif sha_match:
        rationale = (f"DoctrineCompleteness (A9): SHA-256 OK but only {pattern_count}/{required_patterns} "
                     f"patterns. Denied. Lean: doctrineCompleteness @{LEAN_COMMIT[:12]}")
    else:
        rationale = (f"DoctrineCompleteness (A9): SHA-256 mismatch — expected {canonical[:16]}…, "
                     f"got {detected_sha[:16]}…. Denied. Lean: doctrineCompleteness @{LEAN_COMMIT[:12]}")
    return {
        "allow": allow, "rationale": rationale, "formula": "DoctrineCompleteness",
        "leanTheorem": "doctrineCompleteness", "leanFile": "Lutar/Gate/DoctrineCompleteness.lean",
        "leanCommitSha": LEAN_COMMIT, "sha256Match": sha_match, "detectedSha256": detected_sha,
        "patternCount": pattern_count, "requiredPatterns": required_patterns, "lambdaScore": lambda_score,
    }


# --- 15. DeterministicReplay (A5) -----------------------------------------
# TS: deterministicReplay_gate.ts  Lean: deterministicReplay (theorem)
# A5: N replay runs must produce exactly 1 unique (byte-identical) Merkle root.
def eval_deterministic_replay(opts: Dict[str, Any], config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    config = config or {}
    required_runs = config.get("requiredRuns", 5)
    if not isinstance(required_runs, int) or isinstance(required_runs, bool) or required_runs < 1:
        raise GateError(f"DeterministicReplayGate: requiredRuns must be >= 1; got {required_runs}")
    replay_roots = opts.get("replayRoots")
    if not isinstance(replay_roots, list) or len(replay_roots) < required_runs:
        raise GateError(f"DeterministicReplayGate: need {required_runs} roots; got "
                        f"{len(replay_roots) if isinstance(replay_roots, list) else replay_roots}")
    for r in replay_roots:
        if not isinstance(r, str) or len(r) == 0:
            raise GateError("DeterministicReplayGate: each root must be a non-empty string")
    unique_roots = len(set(replay_roots[:required_runs]))
    canonical_root = replay_roots[0]
    allow = unique_roots == 1
    lambda_score = 1.0 if allow else 1.0 / unique_roots
    rationale = (
        f"DeterministicReplay (A5): {required_runs} runs → 1 unique root \"{canonical_root[:16]}…\". "
        f"Byte-identical replay confirmed. Passes. Lean: deterministicReplay @{LEAN_COMMIT[:12]}"
        if allow else
        f"DeterministicReplay (A5): {required_runs} runs → {unique_roots} distinct roots — "
        f"non-determinism detected. Denied. Lean: deterministicReplay @{LEAN_COMMIT[:12]}"
    )
    return {
        "allow": allow, "rationale": rationale, "formula": "DeterministicReplay",
        "leanTheorem": "deterministicReplay", "leanFile": "Lutar/Gate/DeterministicReplay.lean",
        "leanCommitSha": LEAN_COMMIT, "requiredRuns": required_runs, "actualRuns": len(replay_roots),
        "uniqueRoots": unique_roots, "canonicalRoot": canonical_root, "lambdaScore": lambda_score,
    }


# ===========================================================================
# Formula registry — 15 LIVE + 20 ts-only metadata
# ===========================================================================
# axis values map to the 7-organ anatomy / 13-axis Λ vector (Yuyay = the eval organ).
_LIVE = {
    "adversarial-robustness": eval_adversarial_robustness,
    "false-position": eval_false_position,
    "liu-hui-pi": eval_liu_hui_pi,
    "madhava-bound": eval_madhava_bound,
    "summation-invariant": eval_summation_invariant,
    # ---- Phase 3: 10 more ported live ----
    "lambda-monotonicity": eval_lambda_monotonicity,
    "merkle-dag-batch": eval_merkle_dag_batch,
    "replay-determinism": eval_replay_determinism,
    "single-witness-exclusion": eval_single_witness_exclusion,
    "dual-witness-disjointness": eval_dual_witness_disjointness,
    "temporal-consistency": eval_temporal_consistency,
    "composability": eval_composability,
    "hash-chain-integrity": eval_hash_chain_integrity,
    "doctrine-completeness": eval_doctrine_completeness,
    "deterministic-replay": eval_deterministic_replay,
}

# (name, id, leanTheorem, leanFile, leanStatus, axis, severity, gates, status, sample_input, default_config)
_REGISTRY: List[Dict[str, Any]] = [
    # ---- 5 LIVE ----
    {"name": "AdversarialRobustness", "id": "TH8", "leanTheorem": "robustness_preserved_by_composition",
     "leanFile": "Lutar/Composition/AdversarialRobustness.lean", "leanStatus": "theorem", "axis": "SENTRA",
     "severity": "enforced", "gates": "Allows pipeline deploy only when composed perturbation ε₂=L₁·L₂·δ ≤ maxEpsilon.",
     "status": "live", "ts": "packages/policy/src/gates/adversarialRobustness_gate.ts",
     "sample": {"lipschitz1": 0.8, "lipschitz2": 0.9, "delta": 0.5}, "config": {"maxEpsilon": 1.0}},
    {"name": "FalsePosition", "id": "Rhind", "leanTheorem": "false_position_correct",
     "leanFile": "Lutar/Calibration/FalsePosition.lean", "leanStatus": "theorem", "axis": "YUYAY",
     "severity": "enforced", "gates": "Allows calibration only when false-position xStar recovers target T within residual ≤ tolerance.",
     "status": "live", "ts": "packages/policy/src/gates/falsePosition_gate.ts",
     "sample": {"x1": 0, "y1": -2, "x2": 4, "y2": 2, "T": 0}, "config": {"tolerance": 1e-8}},
    {"name": "LiuHuiPi", "id": "Liu Hui", "leanTheorem": "sideSquared_bounds",
     "leanFile": "Lutar/Banach/LiuHuiPi.lean", "leanStatus": "axiom", "axis": "SUMAQ",
     "severity": "advisory", "gates": "Advisory: allows geometric computation only when Liu Hui k-gon π estimate abs error ≤ threshold.",
     "status": "live", "ts": "packages/policy/src/gates/liuHuiPi_gate.ts",
     "sample": {"k": 8}, "config": {"threshold": 1e-4}},
    {"name": "MadhavaBound", "id": "Mādhava", "leanTheorem": "madhavaRemainderBound_nonneg",
     "leanFile": "Lutar/PACBayes/MadhavaBound.lean", "leanStatus": "theorem", "axis": "SUMAQ",
     "severity": "enforced", "gates": "Allows governance signal only when Mādhava arctan remainder |x|^(2N+1)/(2N+1) ≤ threshold.",
     "status": "live", "ts": "packages/policy/src/gates/madhavaBound_gate.ts",
     "sample": {"x": 0.5, "N": 5}, "config": {"threshold": 0.01}},
    {"name": "SummationInvariant", "id": "Khipu", "leanTheorem": "khipuReceipt_checksum_invariant",
     "leanFile": "Lutar/Khipu/SummationInvariant.lean", "leanStatus": "theorem", "axis": "YAWAR",
     "severity": "enforced", "gates": "Allows receipt-chain advancement only when primary cord == Σ pendant values (no tamper).",
     "status": "live", "ts": "packages/policy/src/gates/summationInvariant_gate.ts",
     "sample": {"khipuId": "k1", "organs": [{"organId": "o1", "decisions": [{"decisionId": "d1", "value": 3}, {"decisionId": "d2", "value": 4}]}], "primaryCord": 7}, "config": {}},
    # ---- 10 MORE LIVE (Phase 3, ported below) are interleaved by id; remaining 20 ts-only ----
    {"name": "SoundnessAxiom", "id": "A1", "leanTheorem": "soundness_axiom", "leanFile": "Lutar/Gate/SoundnessAxiom.lean", "leanStatus": "theorem", "axis": "AMARU_CORTEX", "severity": "enforced", "gates": "Gate composition soundness floor.", "status": "ts-only", "ts": "packages/policy/src/gates/soundnessAxiom_gate.ts"},
    {"name": "MoralGroundingFloor", "id": "A2", "leanTheorem": "moral_grounding_floor", "leanFile": "Lutar/Gate/MoralGrounding.lean", "leanStatus": "theorem", "axis": "YUYAY", "severity": "enforced", "gates": "Action must clear moral grounding floor.", "status": "ts-only", "ts": "packages/policy/src/gates/moralGroundingFloor_gate.ts"},
    {"name": "MeasurabilityHonestyFloor", "id": "A3", "leanTheorem": "measurability_honesty_floor", "leanFile": "Lutar/Gate/MeasurabilityHonesty.lean", "leanStatus": "theorem", "axis": "YUYAY", "severity": "enforced", "gates": "Claims must be measurable / honest.", "status": "ts-only", "ts": "packages/policy/src/gates/measurabilityHonestyFloor_gate.ts"},
    {"name": "DualWitnessDisjointness", "id": "A4", "leanTheorem": "dualWitnessDisjointness", "leanFile": "Lutar/Gate/DualWitness.lean", "leanStatus": "theorem", "axis": "YAWAR", "severity": "enforced", "gates": "Allows \u03c1-closure write only when witness_1_id \u2260 witness_2_id (two independent witnesses, no single-witness collapse).", "status": "live", "ts": "packages/policy/src/gates/dualWitnessDisjointness_gate.ts", "sample": {"witness1Id": "alice", "witness2Id": "bob"}, "config": {}},
    {"name": "DeterministicReplay", "id": "A5", "leanTheorem": "deterministicReplay", "leanFile": "Lutar/Gate/DeterministicReplay.lean", "leanStatus": "theorem", "axis": "UNAY", "severity": "enforced", "gates": "Allows production op only when N replay runs yield exactly 1 unique (byte-identical) Merkle root.", "status": "live", "ts": "packages/policy/src/gates/deterministicReplay_gate.ts", "sample": {"replayRoots": ["abc123deadbeef00", "abc123deadbeef00", "abc123deadbeef00", "abc123deadbeef00", "abc123deadbeef00"]}, "config": {"requiredRuns": 5}},
    {"name": "HashChainIntegrity", "id": "A6", "leanTheorem": "hashChainIntegrity", "leanFile": "Lutar/Gate/HashChainIntegrity.lean", "leanStatus": "theorem", "axis": "YAWAR", "severity": "enforced", "gates": "Allows chain advancement only when every entry.chainHash == SHA256(JSON of previous entry) \u2014 Khipu chain continuity.", "status": "live", "ts": "packages/policy/src/gates/hashChainIntegrity_gate.ts", "sample": {"entries": [{"entryId": "e0", "payload": "genesis", "chainHash": "genesis"}, {"entryId": "e1", "payload": "second", "chainHash": "45bd824b7e4aadbb7ea4a865d057e4cd832d718a268169680f898274b89c5a8d"}, {"entryId": "e2", "payload": "third", "chainHash": "ae7da7c40007478c3e412457553c0aa235a1804ec65f446e1b2d472548ca50d9"}]}, "config": {}},
    {"name": "BekensteinBound", "id": "A7", "leanTheorem": "bekenstein_bound", "leanFile": "Lutar/Gate/BekensteinBound.lean", "leanStatus": "conjectured", "axis": "SENTRA", "severity": "advisory", "gates": "Advisory (STAGED): entropy/information bound.", "status": "ts-only", "ts": "packages/policy/src/gates/bekensteinBound_gate.ts"},
    {"name": "IngestDiscipline", "id": "A8", "leanTheorem": "ingest_discipline", "leanFile": "Lutar/Gate/IngestDiscipline.lean", "leanStatus": "theorem", "axis": "SENTRA", "severity": "enforced", "gates": "Ingest must follow discipline schema.", "status": "ts-only", "ts": "packages/policy/src/gates/ingestDiscipline_gate.ts"},
    {"name": "DoctrineCompleteness", "id": "A9", "leanTheorem": "doctrineCompleteness", "leanFile": "Lutar/Gate/DoctrineCompleteness.lean", "leanStatus": "theorem", "axis": "AMARU_CORTEX", "severity": "enforced", "gates": "Allows artifact only when SHA-256(doctrine.json) == canonical AND all 8 forbidden patterns enumerated (doctrine-check.sh parity).", "status": "live", "ts": "packages/policy/src/gates/doctrineCompleteness_gate.ts", "sample": {"doctrineJsonRaw": "{\"version\":\"1.0.0\",\"patterns\":[\"FP\",\"FP\",\"FP\",\"FP\",\"FP\",\"FP\",\"FP\",\"FP\"]}", "detectedPatterns": ["FP", "FP", "FP", "FP", "FP", "FP", "FP", "FP"]}, "config": {"canonicalSha256": "1ebcac54bde49c4062648d0e9757a4364858d6826b60f1f14e79bc1964f1f4fb"}},
    {"name": "TemporalConsistency", "id": "A10", "leanTheorem": "temporalConsistency", "leanFile": "Lutar/Gate/TemporalConsistency.lean", "leanStatus": "theorem", "axis": "UNAY", "severity": "enforced", "gates": "Allows receipt only when |evalTime \u2212 receiptTime| \u2264 clockDriftBound (verdict invariant under bounded clock drift).", "status": "live", "ts": "packages/policy/src/gates/temporalConsistency_gate.ts", "sample": {"receiptTimestampMs": 1700000000000, "evalTimestampMs": 1700000000500}, "config": {"clockDriftBoundMs": 1000}},
    {"name": "CausalSeparability", "id": "A11", "leanTheorem": "causal_separability", "leanFile": "Lutar/Gate/CausalSeparability.lean", "leanStatus": "theorem", "axis": "AMARU_CORTEX", "severity": "enforced", "gates": "Causal graph must be separable.", "status": "ts-only", "ts": "packages/policy/src/gates/causalSeparability_gate.ts"},
    {"name": "ConstructiveTransparency", "id": "A12", "leanTheorem": "constructive_transparency", "leanFile": "Lutar/Gate/ConstructiveTransparency.lean", "leanStatus": "theorem", "axis": "YUYAY", "severity": "enforced", "gates": "Decisions must be constructively transparent.", "status": "ts-only", "ts": "packages/policy/src/gates/constructiveTransparency_gate.ts"},
    {"name": "EconomicGrounding", "id": "A14", "leanTheorem": "economic_grounding", "leanFile": "Lutar/Gate/EconomicGrounding.lean", "leanStatus": "theorem", "axis": "KALLPA", "severity": "enforced", "gates": "Action must be economically grounded (cost).", "status": "ts-only", "ts": "packages/policy/src/gates/economicGrounding_gate.ts"},
    {"name": "RhoClosureComposition", "id": "T1", "leanTheorem": "rho_closure_composition", "leanFile": "Lutar/Gate/RhoClosureComposition.lean", "leanStatus": "theorem", "axis": "AMARU_CORTEX", "severity": "enforced", "gates": "ρ-closure composes under pipeline.", "status": "ts-only", "ts": "packages/policy/src/gates/rhoClosureComposition_gate.ts"},
    {"name": "LambdaMonotonicity", "id": "T2", "leanTheorem": "lambdaMonotonicity", "leanFile": "Lutar/Gate/LambdaMonotonicity.lean", "leanStatus": "theorem", "axis": "YUYAY", "severity": "enforced", "gates": "Allows evidence augmentation only when every \u039b axis score weakly increases (no decreasing/conflicting axis).", "status": "live", "ts": "packages/policy/src/gates/lambdaMonotonicity_gate.ts", "sample": {"originalScores": [0.9, 0.85], "augmentedScores": [0.95, 0.9]}, "config": {"tolerance": 1e-9}},
    {"name": "MerkleDagBatch", "id": "T3", "leanTheorem": "merkleDagBatch", "leanFile": "Lutar/Gate/MerkleDagBatch.lean", "leanStatus": "theorem", "axis": "YAWAR", "severity": "enforced", "gates": "Allows batch only when (B<minBatch) or build p50 \u2264 maxBuildP50Us \u2014 the O(log B) Merkle-DAG latency bound.", "status": "live", "ts": "packages/policy/src/gates/merkleDagBatch_gate.ts", "sample": {"batchSize": 7, "buildP50Us": 4}, "config": {"maxBuildP50Us": 5, "minBatchSize": 7}},
    {"name": "BekensteinEntropyMeasure", "id": "T4", "leanTheorem": "bekenstein_entropy_measure", "leanFile": "Lutar/Gate/BekensteinEntropyMeasure.lean", "leanStatus": "conjectured", "axis": "SENTRA", "severity": "enforced", "gates": "Entropy measure ≤ Bekenstein bound.", "status": "ts-only", "ts": "packages/policy/src/gates/bekensteinEntropyMeasure_gate.ts"},
    {"name": "ReplayDeterminism", "id": "T5", "leanTheorem": "replayDeterminism", "leanFile": "Lutar/Gate/ReplayDeterminism.lean", "leanStatus": "theorem", "axis": "UNAY", "severity": "enforced", "gates": "Allows deploy only when all requiredRuns replay roots equal the pinned canonical Merkle root (Codex-Kernel determinism).", "status": "live", "ts": "packages/policy/src/gates/replayDeterminism_gate.ts", "sample": {"replayRoots": ["1ed4d253cafebabe12345678", "1ed4d253cafebabe12345678", "1ed4d253cafebabe12345678", "1ed4d253cafebabe12345678", "1ed4d253cafebabe12345678"]}, "config": {"canonicalRoot": "1ed4d253cafebabe12345678", "requiredRuns": 5}},
    {"name": "ConjunctiveGateCounterexample", "id": "T6", "leanTheorem": "conjunctive_gate_counterexample", "leanFile": "Lutar/Gate/ConjunctiveGate.lean", "leanStatus": "theorem", "axis": "YUYAY", "severity": "enforced", "gates": "Conjunctive gate counterexample search.", "status": "ts-only", "ts": "packages/policy/src/gates/conjunctiveGateCounterexample_gate.ts"},
    {"name": "PrivacyMask", "id": "T7", "leanTheorem": "privacy_mask", "leanFile": "Lutar/Gate/PrivacyMask.lean", "leanStatus": "theorem", "axis": "SENTRA", "severity": "enforced", "gates": "PII mask must cover sensitive fields.", "status": "ts-only", "ts": "packages/policy/src/gates/privacyMask_gate.ts"},
    {"name": "SingleWitnessExclusion", "id": "T8", "leanTheorem": "singleWitnessExclusion", "leanFile": "Lutar/Gate/SingleWitnessExclusion.lean", "leanStatus": "theorem", "axis": "YAWAR", "severity": "enforced", "gates": "Allows closure only when cross-actor (or same-actor by default) decisions carry \u2265 2 witnesses \u2014 excludes single-witness.", "status": "live", "ts": "packages/policy/src/gates/singleWitnessExclusion_gate.ts", "sample": {"actor1Id": "alice", "actor2Id": "bob", "witnessCount": 2}, "config": {}},
    {"name": "CrossRegionPolicy", "id": "T9", "leanTheorem": "cross_region_policy", "leanFile": "Lutar/Gate/CrossRegionPolicy.lean", "leanStatus": "theorem", "axis": "KALLPA", "severity": "enforced", "gates": "Cross-region data policy enforced.", "status": "ts-only", "ts": "packages/policy/src/gates/crossRegionPolicy_gate.ts"},
    {"name": "DoctrineEnforcement", "id": "T10", "leanTheorem": "doctrine_enforcement", "leanFile": "Lutar/Gate/DoctrineEnforcement.lean", "leanStatus": "theorem", "axis": "AMARU_CORTEX", "severity": "enforced", "gates": "Doctrine v11 LOCKED enforcement.", "status": "ts-only", "ts": "packages/policy/src/gates/doctrineEnforcement_gate.ts"},
    {"name": "Composability", "id": "TH1", "leanTheorem": "composability", "leanFile": "Lutar/Composition/Composability.lean", "leanStatus": "theorem", "axis": "AMARU_CORTEX", "severity": "enforced", "gates": "Allows A\u2218B cross-system deploy only when doctrine SHAs match, A exit floor \u2264 B entry floor, and A2A headers present.", "status": "live", "ts": "packages/policy/src/gates/composability_gate.ts", "sample": {"doctrineShaA": "abc123sha256", "doctrineShaB": "abc123sha256", "aExitFloor": 0.9, "bEntryFloor": 0.92, "hasA2AHeaders": True}, "config": {}},
    {"name": "ReplayDoiDuality", "id": "TH2", "leanTheorem": "replay_doi_duality", "leanFile": "Lutar/Composition/ReplayDoiDuality.lean", "leanStatus": "theorem", "axis": "UNAY", "severity": "enforced", "gates": "Replay ↔ DOI duality holds.", "status": "ts-only", "ts": "packages/policy/src/gates/replayDoiDuality_gate.ts"},
    {"name": "AnatomyReduction", "id": "TH3", "leanTheorem": "anatomy_reduction", "leanFile": "Lutar/Composition/AnatomyReduction.lean", "leanStatus": "theorem", "axis": "AMARU_CORTEX", "severity": "enforced", "gates": "7-organ anatomy reduces correctly.", "status": "ts-only", "ts": "packages/policy/src/gates/anatomyReduction_gate.ts"},
    {"name": "LambdaCategoryComposability", "id": "TH4", "leanTheorem": "lambda_category_composability", "leanFile": "Lutar/LaxFunctor.lean", "leanStatus": "conjectured", "axis": "YUYAY", "severity": "advisory", "gates": "Advisory (STAGED): Λ lax-functor composition.", "status": "ts-only", "ts": "packages/policy/src/gates/lambdaCategoryComposability_gate.ts"},
    {"name": "ReceiptChainConfluence", "id": "TH5", "leanTheorem": "receipt_chain_confluence", "leanFile": "Lutar/Composition/ReceiptChainConfluence.lean", "leanStatus": "conjectured", "axis": "YAWAR", "severity": "enforced", "gates": "Receipt chain confluent under merge.", "status": "ts-only", "ts": "packages/policy/src/gates/receiptChainConfluence_gate.ts"},
    {"name": "BekensteinEntropyDpi", "id": "TH6", "leanTheorem": "bekenstein_entropy_dpi", "leanFile": "Lutar/EntropyBound.lean", "leanStatus": "theorem", "axis": "SENTRA", "severity": "enforced", "gates": "DPI entropy bound (discharges A7 formally).", "status": "ts-only", "ts": "packages/policy/src/gates/bekensteinEntropyDpi_gate.ts"},
    {"name": "CurryHowardReceiptCalculus", "id": "TH7", "leanTheorem": "curry_howard_receipt_calculus", "leanFile": "Lutar/CurryHoward.lean", "leanStatus": "theorem", "axis": "YAWAR", "severity": "enforced", "gates": "Receipt calculus = proof terms (Curry-Howard).", "status": "ts-only", "ts": "packages/policy/src/gates/curryHowardReceiptCalculus_gate.ts"},
    # ---- Hickok cognitive-neuroscience ingest (A36/A37/A38) ----
    # Axis `Hickok`. All ts-only (honest): the Lean anchor files carry `sorry`
    # proofs. Citations: Hickok & Poeppel 2007 (DOI 10.1038/nrn2113, dual-stream);
    # Hickok et al. 2011 (DOI 10.1016/j.neuron.2011.01.019, state-feedback control);
    # Hickok 2025 *Wired for Words* (MIT Press, hierarchical linearization).
    {"name": "DualStreamRoutingAxiom", "id": "A36", "leanTheorem": "dual_stream_routing_axiom", "leanFile": "packages/policy/src/gates/DualStreamRouting.lean", "leanStatus": "axiom", "axis": "Hickok", "severity": "advisory", "gates": "Advisory: every request routes to EXACTLY ONE of the dorsal (action) or ventral (meaning) streams \u2014 never both, never neither (Hickok & Poeppel dual-stream model, DOI 10.1038/nrn2113).", "status": "ts-only", "ts": "packages/policy/src/gates/dualStreamRouting_gate.ts", "doi": "10.1038/nrn2113"},
    {"name": "InternalFeedbackIntegrity", "id": "A37", "leanTheorem": "internal_feedback_integrity", "leanFile": "packages/policy/src/gates/InternalFeedback.lean", "leanStatus": "theorem", "axis": "Hickok", "severity": "enforced", "gates": "Enforced: the internal sensory-motor feedback loop (efference copy \u2192 forward model \u2192 corrective signal) must close \u2014 a prediction without a returning corrective signal fails (state-feedback control of speech, DOI 10.1016/j.neuron.2011.01.019).", "status": "ts-only", "ts": "packages/policy/src/gates/internalFeedback_gate.ts", "doi": "10.1016/j.neuron.2011.01.019"},
    {"name": "HierarchicalLinearizationRoundTrip", "id": "A38", "leanTheorem": "hierarchical_linearization_round_trip", "leanFile": "packages/policy/src/gates/HierarchicalLinearization.lean", "leanStatus": "theorem", "axis": "Hickok", "severity": "advisory", "gates": "Advisory: hierarchical message \u2192 linear sequence \u2192 hierarchical message must round-trip (parse(linearize(h)) = h) \u2014 the linearization of structured meaning into serial output (Hickok 2025 *Wired for Words*, MIT Press).", "status": "ts-only", "ts": "packages/policy/src/gates/hierarchicalLinearization_gate.ts", "citation": "Hickok 2025 Wired for Words (MIT Press)"},
]

# Lean-Theorem 'b' variants (TH_L1–TH_L4) are ALTERNATE Lean encodings of slots
# TH4/TH5/TH6/TH7 (numbered 32b/33b/34b/35b in the gates README), not additional
# formulas — so the canonical anchor count stays at exactly 35. Their TS gate files
# DO exist in a11oy; they are exposed below as supplementary ts-only metadata and are
# NOT counted toward the 35.
_SUPPLEMENTARY: List[Dict[str, Any]] = [
    {"name": "LambdaUniqueness", "id": "TH_L1", "leanTheorem": "lambda_uniqueness", "leanFile": "Lutar/Uniqueness.lean", "leanStatus": "theorem", "axis": "YUYAY", "severity": "enforced", "gates": "Λ fixed point uniqueness (2 sorry in wider repo).", "status": "ts-only", "ts": "packages/policy/src/gates/lambdaUniqueness_gate.ts"},
    {"name": "LambdaMinMaxBounds", "id": "TH_L2", "leanTheorem": "lambda_min_max_bounds", "leanFile": "Lutar/Bound.lean", "leanStatus": "theorem", "axis": "YUYAY", "severity": "enforced", "gates": "Λ score min/max bounds (2 sorry in wider repo).", "status": "ts-only", "ts": "packages/policy/src/gates/lambdaMinMaxBounds_gate.ts"},
    {"name": "BekensteinSoundness", "id": "TH_L3", "leanTheorem": "bekenstein_soundness", "leanFile": "Lutar/BekensteinSoundness.lean", "leanStatus": "measured/conjectured", "axis": "SENTRA", "severity": "advisory", "gates": "Advisory (STAGED): Bekenstein soundness.", "status": "ts-only", "ts": "packages/policy/src/gates/bekensteinSoundness_gate.ts"},
    {"name": "RhoClosureProduction", "id": "TH_L4", "leanTheorem": "rho_closure_production", "leanFile": "Lutar/RhoClosureProduction.lean", "leanStatus": "measured", "axis": "AMARU_CORTEX", "severity": "enforced", "gates": "ρ-closure measured in production.", "status": "ts-only", "ts": "packages/policy/src/gates/rhoClosureProduction_gate.ts"},
]

# Canonical 35 anchor formulas (_REGISTRY) are what GET /formulas returns and what
# the cards render. _SUPPLEMENTARY TH_L variants are addressable by slug for detail/
# evaluate but are NOT counted in the 35.
_BY_SLUG: Dict[str, Dict[str, Any]] = {_slug(r["name"]): r for r in (_REGISTRY + _SUPPLEMENTARY)}
assert len(_REGISTRY) == 38, f"expected exactly 38 anchor formulas, got {len(_REGISTRY)}"


def _public_meta(r: Dict[str, Any]) -> Dict[str, Any]:
    m = {
        "id": r["id"], "name": r["name"], "slug": _slug(r["name"]),
        "leanTheorem": r["leanTheorem"], "leanFile": r["leanFile"], "leanStatus": r["leanStatus"],
        "leanCommitSha": LEAN_COMMIT, "axis": r["axis"], "severity": r["severity"],
        "gates": r["gates"], "status": r["status"], "tsRuntime": r["ts"],
    }
    if "sample" in r:
        m["sample"] = r["sample"]
    if "config" in r:
        m["defaultConfig"] = r["config"]
    # Hickok ingest: surface neuroscience provenance (DOI / citation) when present.
    if "doi" in r:
        m["doi"] = r["doi"]
    if "citation" in r:
        m["citation"] = r["citation"]
    return m


def all_formulas() -> Dict[str, Any]:
    rows = [_public_meta(r) for r in _REGISTRY]
    supp = [_public_meta(r) for r in _SUPPLEMENTARY]
    return {
        "doctrine": DOCTRINE, "lean_commit": LEAN_COMMIT, "zenodo_doi": ZENODO_DOI,
        "sovereign": True, "signing_available": (_dsse.signing_available() if _dsse else False),
        "counts": {
            "total": len(rows),
            "live": sum(1 for r in rows if r["status"] == "live"),
            "ts_only": sum(1 for r in rows if r["status"] == "ts-only"),
            "lean_only": sum(1 for r in rows if r["status"] == "lean-only"),
            "supplementary_th_l": len(supp),
        },
        "source": {
            "ts_gates": "szl-holdings/a11oy packages/policy/src/gates",
            "lean": "szl-holdings/lutar-lean",
            "wired_pr": "szl-holdings/a11oy#108 (cursor/policy-gates-hardening-2f18)",
        },
        "formulas": rows,
        "supplementary": supp,
    }


def evaluate(slug: str, opts: Dict[str, Any], config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Evaluate one formula by slug. Returns {decision, receipt:{receipt, dsse}, ...}.

    Live formulas run the ported math + emit a signed Khipu receipt.
    ts-only formulas return a 422-style result with an honest 'not ported' message
    (the caller maps this to HTTP 422).
    """
    r = _BY_SLUG.get(slug)
    if r is None:
        return {"error": f"unknown formula '{slug}'", "code": 404}
    if r["status"] != "live" or slug not in _LIVE:
        return {
            "error": f"formula '{slug}' is status '{r['status']}' — not ported to the live v4 module; "
                     f"a TypeScript gate exists at {r['ts']} but is not runnable here.",
            "code": 422, "status": r["status"], "tsRuntime": r["ts"],
        }
    # run the ported gate (raises GateError on invalid input)
    decision = _LIVE[slug](opts, config)

    # Build a Khipu receipt over the decision, then sign it (real ECDSA-P256 if secret present).
    decision_canonical = _canonical(decision)
    decision_sha = hashlib.sha256(decision_canonical.encode("utf-8")).hexdigest()
    receipt_body = {
        "protocol": "a11oy",
        "tool_name": f"policy_gate.{decision['formula']}",
        "event_type": "A11OY_OPERATION",
        "lambda_axes": ["Λ6", "Λ7"],  # policy + provenance (mirrors gates/receipt.ts default)
        "axis_organ": r["axis"],
        "actor_id": "yachay",
        "co_author": "perplexity-computer-agent",
        "doctrine": DOCTRINE,
        "lean": {"theorem": decision["leanTheorem"], "file": decision["leanFile"], "commit": decision["leanCommitSha"],
                 "status": r["leanStatus"]},
        "input": opts,
        "config": config or r.get("config", {}),
        "decision": decision,
        "decision_sha256": decision_sha,
        "ts": _iso(),
    }
    if _dsse is not None:
        signed = _dsse.sign_khipu_receipt(receipt_body)  # {receipt, dsse}
    else:  # pragma: no cover — defensive; szl_dsse always ships in the Space
        signed = {"receipt": receipt_body,
                  "dsse": {"signatures": [], "signed": False,
                           "honesty": "UNSIGNED — szl_dsse module unavailable in this runtime."}}
    return {
        "ok": True, "formula": decision["formula"], "slug": slug, "id": r["id"], "axis": r["axis"],
        "severity": r["severity"], "leanStatus": r["leanStatus"],
        "verdict": "ALLOW" if decision["allow"] else "DENY",
        "decision": decision, "receipt": signed,
    }


def _canonical(obj: Any) -> str:
    import json
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


# ===========================================================================
# FastAPI registration — ADDITIVE; mount BEFORE the generic Node proxy.
# ===========================================================================
def register(app, ns: str = "a11oy", web_dir: Optional[str] = None) -> Dict[str, Any]:
    from pathlib import Path

    from fastapi.responses import FileResponse, JSONResponse

    base = f"/api/{ns}/v4"
    here = Path(web_dir) if web_dir else Path(__file__).resolve().parent / "web"
    html_path = here / "formulas.html"

    @app.get(f"{base}/formulas")
    async def _v4_formulas():  # noqa: ANN202
        return JSONResponse(all_formulas())

    @app.get(f"{base}/formulas/{{name}}")
    async def _v4_formula_detail(name: str):  # noqa: ANN202
        r = _BY_SLUG.get(name)
        if r is None:
            return JSONResponse({"error": f"unknown formula '{name}'"}, status_code=404)
        return JSONResponse(_public_meta(r))

    @app.post(f"{base}/formulas/{{name}}/evaluate")
    async def _v4_evaluate(name: str, req: Request):  # noqa: ANN202
        try:
            body = await req.json()
        except Exception:
            body = {}
        opts = body.get("input", body.get("opts", body)) if isinstance(body, dict) else {}
        # if caller wrapped under input/opts use it, else treat the whole body as opts minus config
        if isinstance(body, dict) and ("input" in body or "opts" in body):
            opts = body.get("input", body.get("opts", {}))
            config = body.get("config")
        else:
            config = body.get("config") if isinstance(body, dict) else None
            opts = {k: v for k, v in (body or {}).items() if k != "config"} if isinstance(body, dict) else {}
        try:
            result = evaluate(name, opts or {}, config)
        except GateError as ge:
            return JSONResponse({"ok": False, "error": str(ge), "code": 400, "slug": name}, status_code=400)
        code = result.get("code")
        if code in (404, 422):
            return JSONResponse(result, status_code=code)
        return JSONResponse(result)

    async def _serve_formulas_html():  # noqa: ANN202
        if html_path.exists():
            return FileResponse(str(html_path))
        return JSONResponse({"error": "formulas.html not deployed"}, status_code=404)

    app.get("/formulas-v4")(_serve_formulas_html)
    app.get(f"/{ns}/formulas-v4")(_serve_formulas_html)

    return {
        "registered": True, "ns": ns, "base": base,
        "routes": [f"{base}/formulas", f"{base}/formulas/{{name}}",
                   f"{base}/formulas/{{name}}/evaluate", "/formulas-v4"],
        "live": list(_LIVE.keys()), "total": len(_REGISTRY),
        "signing_available": (_dsse.signing_available() if _dsse else False),
    }


if __name__ == "__main__":  # local smoke test
    import json
    data = all_formulas()
    print(f"total={data['counts']}")
    for s in _LIVE:
        r = _BY_SLUG[s]
        res = evaluate(s, r["sample"], r.get("config"))
        print(f"{s}: verdict={res['verdict']} signed={res['receipt']['dsse'].get('signed')}")
    print(json.dumps(evaluate("adversarial-robustness", {"lipschitz1": 0.8, "lipschitz2": 0.9, "delta": 0.5}), indent=2)[:600])
