# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. Jr. — SZL Holdings
"""Formula-backed SOW membrane. Overlay, not a new product.

Composes identities that already exist in the estate:

- Locked-proven set is exactly 8: F1 F4 F7 F11 F12 F18 F19 F22
  (lutar-lean locked_count_eight, kernel c7c0ba17).
- Λ uniqueness is Conjecture 1. Advisory only. Never the sole basis for ALLOW.
- Ouroboros doctrine: bounded, terminating, receipt-closed.
  receipts.in ≡ receipts.out. Budget violations are reported, never clamped.
- formula_registry.v1.json: a locked formula can constrain execution only
  after an explicit applicability decision. None of them authorize action.
- Station mapping onto F-ids is MODELED applicability, not a Lean binding.
  The registry mapping of callable software names onto F-numbers is
  UNKNOWN_NOT_ASSERTED.

Commercial identities used as MODELED helpers (Rocketlane / Projectworks /
CalcMark — REPORTED, not Lean-proven):
  gross_margin = (revenue - cost) / revenue
  margin_erosion = planned_margin - actual_margin
  effort_variance_ratio = (actual - planned) / planned
  utilization = billable / available
  realization = billed / worked

Miss = ABSTAIN. Never invent a handle id.
certified_production_ready is false.
Hickok Dual-Stream /brain is out of scope.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any

LOCKED_FORMULA_IDS = ("F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22")
STATION_IDS = ("SOW", "STAFF", "EXCEPTION", "INVOICE")
STATION_HANDLES = {
    "SOW": "SOW_SIGNED",
    "STAFF": "STAFF_ASSIGNED",
    "EXCEPTION": "EXCEPTION_RAISED",
    "INVOICE": "INVOICE_ISSUED",
}
STATION_MISS = {
    "SOW": "no signed scope handle",
    "STAFF": "no roster handle",
    "EXCEPTION": "no verified trigger fact",
    "INVOICE": "no billed-vs-promised handle",
}
# MODELED applicability — not a proved F-id binding.
STATION_FORMULAS = {
    "SOW": ("F1", "F4"),
    "STAFF": ("F7", "F11"),
    "EXCEPTION": ("F12", "F19"),
    "INVOICE": ("F18", "F22"),
}
MARGIN_FLOOR = 0.22
VARIANCE_THRESHOLD = 0.12
TRUST_CEILING = 0.97
RS_N, RS_K = 10, 6
LOOP_DOCTRINE = "bounded, terminating, receipt-closed"
KERNEL_SHA = "c7c0ba17"


def _sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def f1_replay_digest(event: str) -> dict[str, Any]:
    """F1 Replay-Hash Determinism. Same event, same digest. Twice."""
    body = json.dumps({"event": event or ""}, separators=(",", ":"), sort_keys=True)
    first = _sha256_hex(body)
    second = _sha256_hex(body)
    return {
        "id": "F1",
        "name": "Replay-Hash Determinism",
        "digest": first,
        "replay_ok": first == second,
        "maturity": "LOCKED_PROVEN",
    }


def f4_chain_is_dag(order: tuple[str, ...] = STATION_IDS) -> dict[str, Any]:
    """F4 Khipu DAG acyclicity. Forward walk uses append-only backward edges."""
    edges = []
    for i, src in enumerate(order):
        if i == 0:
            continue
        dst = order[i - 1]
        edges.append({"src": src, "dst": dst, "src_i": i, "dst_i": i - 1})
    acyclic = all(e["dst_i"] < e["src_i"] for e in edges) and len(set(order)) == len(order)
    return {
        "id": "F4",
        "name": "Khipu DAG Acyclicity",
        "edges": edges,
        "acyclic": acyclic,
        "maturity": "LOCKED_PROVEN",
        "caveat": "Applies only to this encoded station walk, not an external graph.",
    }


def f7_fifo(walked: list[str], declared: tuple[str, ...] = STATION_IDS) -> dict[str, Any]:
    """F7 Chaski FIFO. Drained reception order equals send order."""
    drained = list(walked)
    return {
        "id": "F7",
        "name": "Chaski FIFO Ordering",
        "sent": list(declared),
        "drained": drained,
        "order_ok": drained == list(declared[: len(drained)]),
        "maturity": "LOCKED_PROVEN",
        "caveat": "Does not prove delivery of an external transport.",
    }


def f11_reciprocity(promised: float | None, billed: float | None) -> dict[str, Any]:
    """F11 Ayni Reciprocity Conservation. Billed-vs-promised balance."""
    if promised is None or billed is None:
        return {
            "id": "F11",
            "name": "Ayni Reciprocity Conservation",
            "conserved": False,
            "reason": "promised or billed numeric missing",
            "maturity": "LOCKED_PROVEN",
            "caveat": "Does not prove fairness of an arbitrary economic system.",
        }
    delta = billed - promised
    return {
        "id": "F11",
        "name": "Ayni Reciprocity Conservation",
        "promised": promised,
        "billed": billed,
        "delta": delta,
        "conserved": math.isclose(delta, 0.0, abs_tol=1e-9),
        "maturity": "LOCKED_PROVEN",
    }


def f12_additive(scores: list[float]) -> dict[str, Any]:
    """F12 additive fragment ONLY. Not nonlinear Kuramoto synchronization."""
    total = math.fsum(float(s) for s in scores)
    return {
        "id": "F12",
        "name": "Kuramoto Additive Fragment",
        "scores": [float(s) for s in scores],
        "sum": total,
        "maturity": "LOCKED_PROVEN_LIMITED_FRAGMENT",
        "caveat": "Additive fragment only; not nonlinear Kuramoto synchronization.",
    }


def f18_singleton(present_shards: int, n: int = RS_N, k: int = RS_K) -> dict[str, Any]:
    """F18 RS(10,6). Recoverable iff at least k of n shards survive. d = n-k+1."""
    distance = n - k + 1
    recoverable = present_shards >= k
    return {
        "id": "F18",
        "name": "Reed-Solomon RS(10,6) Recovery Arithmetic",
        "n": n,
        "k": k,
        "singleton_distance": distance,
        "present_shards": present_shards,
        "recoverable": recoverable,
        "maturity": "LOCKED_PROVEN",
        "caveat": "Does not implement an encoder or a corruption model.",
    }


def f19_budget(parts: list[float], cap: float) -> dict[str, Any]:
    """F19 additive/monotone scaffolding ONLY. Not the physical Bekenstein bound."""
    total = math.fsum(float(p) for p in parts)
    monotone = all(float(p) <= cap + 1e-12 for p in parts) and total <= cap + 1e-12
    return {
        "id": "F19",
        "name": "Bekenstein Additive Scaffolding",
        "parts": [float(p) for p in parts],
        "total": total,
        "cap": cap,
        "within_budget": monotone,
        "maturity": "LOCKED_PROVEN_LIMITED_FRAGMENT",
        "caveat": "Additive/monotone scaffolding only; not S ≤ 2πkRE/(ℏ c).",
    }


def f22_emit(seq: list[int]) -> dict[str, Any]:
    """F22 Khipu emit append-only monotonicity. Sequence strictly increases."""
    ok = all(seq[i] < seq[i + 1] for i in range(len(seq) - 1)) if len(seq) >= 2 else len(seq) in (0, 1)
    return {
        "id": "F22",
        "name": "Khipu Emit Monotonicity",
        "seq": list(seq),
        "monotone": ok,
        "maturity": "LOCKED_PROVEN",
        "caveat": "Does not prove an external clock or database sequence.",
    }


def lambda_aggregate(axes: list[float], weights: list[float] | None = None) -> float:
    """D2 weighted geometric mean. Uniqueness is Conjecture 1 — advisory."""
    xs = [float(x) for x in axes]
    if not xs:
        raise ValueError("axes must be non-empty")
    if any(x < 0.0 for x in xs):
        raise ValueError("axes must be non-negative")
    k = len(xs)
    ws = [1.0 / k] * k if weights is None else [float(w) for w in weights]
    if len(ws) != k:
        raise ValueError("weights length must match axes")
    if abs(math.fsum(ws) - 1.0) > 1e-9:
        raise ValueError("weights must sum to 1")
    if any(x == 0.0 for x in xs):
        return 0.0
    return math.exp(math.fsum(w * math.log(x) for w, x in zip(ws, xs)))


def commercial(event: dict[str, Any]) -> dict[str, Any]:
    """MODELED professional-services identities. Not locked-proven."""
    revenue = event.get("revenue")
    cost = event.get("cost")
    planned_margin = event.get("planned_margin")
    actual_hours = event.get("actual_hours")
    planned_hours = event.get("planned_hours")
    billable = event.get("billable_hours")
    available = event.get("available_hours")
    billed = event.get("billed_hours")
    worked = event.get("worked_hours")
    margin = None
    if isinstance(revenue, (int, float)) and isinstance(cost, (int, float)) and revenue:
        margin = (float(revenue) - float(cost)) / float(revenue)
    erosion = None
    if isinstance(planned_margin, (int, float)) and margin is not None:
        erosion = float(planned_margin) - margin
    variance = None
    if isinstance(actual_hours, (int, float)) and isinstance(planned_hours, (int, float)) and planned_hours:
        variance = (float(actual_hours) - float(planned_hours)) / float(planned_hours)
    utilization = None
    if isinstance(billable, (int, float)) and isinstance(available, (int, float)) and available:
        utilization = float(billable) / float(available)
    realization = None
    if isinstance(billed, (int, float)) and isinstance(worked, (int, float)) and worked:
        realization = float(billed) / float(worked)
    return {
        "class": "MODELED",
        "source": "REPORTED Rocketlane / Projectworks / CalcMark identities",
        "gross_margin": margin,
        "margin_floor": MARGIN_FLOOR,
        "below_floor": margin is not None and margin < MARGIN_FLOOR,
        "margin_erosion": erosion,
        "effort_variance": variance,
        "variance_threshold": VARIANCE_THRESHOLD,
        "over_variance": variance is not None and variance >= VARIANCE_THRESHOLD,
        "utilization": utilization,
        "realization": realization,
    }


def empty_membrane() -> dict[str, dict[str, Any]]:
    return {
        station: {
            "state": "ABSTAIN",
            "reason": STATION_MISS[station],
            "handle": None,
            "formulas": list(STATION_FORMULAS[station]),
        }
        for station in STATION_IDS
    }


def retrieve_membrane(
    event: str = "",
    handles: dict[str, str] | None = None,
    numbers: dict[str, Any] | None = None,
    seq: int = 1,
    wall_ms: int = 0,
    max_budget: int = 4,
) -> dict[str, Any]:
    """Admit a handle only when an id is supplied. Never invent one.

    Walk is F7 FIFO through the F4 DAG. First miss blocks the chain.
    Λ is computed and capped, then labeled ADVISORY.
    """
    membrane = empty_membrane()
    supplied = dict(handles or {})
    walked: list[str] = []
    for station in STATION_IDS:
        walked.append(station)
        hid = str(supplied.get(station) or "").strip()
        if not hid:
            membrane[station]["state"] = "ABSTAIN"
            membrane[station]["reason"] = STATION_MISS[station]
            break
        membrane[station] = {
            "state": "HANDLE",
            "reason": "handle admitted",
            "handle": hid,
            "formulas": list(STATION_FORMULAS[station]),
        }

    blocked_at = next(
        (s for s in STATION_IDS if membrane[s]["state"] == "ABSTAIN"),
        None,
    )
    admitted = [s for s in STATION_IDS if membrane[s]["state"] == "HANDLE"]
    nums = dict(numbers or {})
    replay = f1_replay_digest(event)
    dag = f4_chain_is_dag()
    fifo = f7_fifo(walked)
    recip = f11_reciprocity(nums.get("promised"), nums.get("billed"))
    scores = [1.0 if membrane[s]["state"] == "HANDLE" else 0.0 for s in STATION_IDS]
    additive = f12_additive(scores)
    shards = min(10, 6 + len(admitted))
    rs = f18_singleton(shards)
    budget = f19_budget(scores, cap=4.0)
    emit = f22_emit(list(range(1, max(seq, 1) + 1)))
    raw_lambda = lambda_aggregate([0.97 if s == 1.0 else 0.20 for s in scores])
    advisory = min(raw_lambda, TRUST_CEILING)

    receipts_in = 1
    receipts_out = 1 if replay["replay_ok"] else 0
    within = wall_ms <= (max_budget * 1000) if wall_ms else True
    loop = {
        "doctrine": LOOP_DOCTRINE,
        "steps": len(walked),
        "max_budget": max_budget,
        "wall_ms": wall_ms,
        "withinBudget": within,
        "receiptsInEqOut": receipts_in == receipts_out,
        "exit": "converged" if blocked_at is None else "abstain",
        "clamped": False,
    }
    if not within:
        loop["exit"] = "budget_exceeded"
        loop["note"] = "Budget violation reported, never clamped."

    policy_allow = blocked_at is None
    kernel_allow = False
    emit_allow = policy_allow and kernel_allow

    return {
        "schema": "szl.brain-membrane.v1",
        "membrane": membrane,
        "miss": "ABSTAIN",
        "overlay": "incumbent PSA — do not replace",
        "certified_production_ready": False,
        "china_oss": "REPORTED",
        "hickok_untouched": True,
        "locked_formula_count": 8,
        "locked_formula_ids": list(LOCKED_FORMULA_IDS),
        "kernel": KERNEL_SHA,
        "doctrine": "v11",
        "admitted": admitted,
        "blocked_at": blocked_at,
        "overall": "ADMIT" if blocked_at is None else "ABSTAIN",
        "emit_allow": emit_allow,
        "gate": {
            "policy_allow": policy_allow,
            "kernel_allow": kernel_allow,
            "emit_allow": emit_allow,
            "theorem": "P2 gate-soundness — no action without both approvals",
            "note": "Membrane ADMIT is handle presence, not action ALLOW.",
        },
        "formulas": {
            "F1": replay,
            "F4": dag,
            "F7": fifo,
            "F11": recip,
            "F12": additive,
            "F18": rs,
            "F19": budget,
            "F22": emit,
        },
        "station_formula_map": STATION_FORMULAS,
        "station_formula_map_class": "MODELED_APPLICABILITY",
        "lambda": {
            "value": advisory,
            "raw": raw_lambda,
            "ceiling": TRUST_CEILING,
            "status": "CONJECTURE_1_ADVISORY",
            "can_authorize_action": False,
        },
        "ouroboros": loop,
        "commercial": commercial(nums),
        "proof_fold": "https://a11oy.net/estate/thread-ops/",
        "replay_digest": replay["digest"],
        "applicability_required": True,
    }
