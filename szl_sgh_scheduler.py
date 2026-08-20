# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · Doctrine v11
"""szl_sgh_scheduler.py — an explicit node state machine that WRAPS (never
replaces) the governed Ouroboros cycle with inspectable, structured control flow.

INSPIRATION (own-code reimplementation, NOT vendored): the *pattern* from
"From Agent Loops to Structured Graphs" (Hu Wei, arXiv:2604.11378 — a cs.AI
POSITION PAPER with no code; ideas freely adoptable). The paper argues naive
agent loops have three weaknesses — (1) unbounded recovery loops, (2) mutable
execution history, (3) opaque next-step choice — and proposes SGH: an explicit
node state machine over a STATIC, IMMUTABLE plan DAG with separated
PLAN / EXECUTE / VERIFY / RECOVER layers, strict bounded escalation, and
*advisory* termination + soundness.

What this module adds to the existing governed cycle (which already has a
bounded budget ≤ 64, immutable hash-chained DSSE receipts, an inspectable
Λ-gate, and converge/halt): EXPLICIT, INSPECTABLE control flow —
  * a plan DAG fixed ONCE at plan time (a new plan version is a NEW immutable
    plan; there is NO mid-run mutation of the plan),
  * a node state machine PLAN → EXECUTE → VERIFY → RECOVER → HALT,
  * STRICT BOUNDED escalation in RECOVER (bounded retries → escalate → HALT;
    NEVER unbounded), and
  * a per-transition receipt (node, from_state, to_state, plan_version) that is
    hash-chained and folds in the cycle's own chain hash.

ADVISORY DISCIPLINE (doctrine v11): this is labelled advisory / experimental.
Termination here is BOUNDED BY CONSTRUCTION (finite budget × finite recover
attempts) but is NEVER claimed "provably terminating/sound" — the source is a
spec, not a proof, and a real Lean termination theorem is a SEPARATE future
task. This module NEVER overrides the deny-by-default gate, NEVER moves Λ off
Conjecture 1, and NEVER touches the locked-8 kernel.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Optional, Sequence

# Explicit, inspectable node states. HALT is the single terminal state.
STATES = ("PLAN", "EXECUTE", "VERIFY", "RECOVER", "HALT")

# Cycle final_status values that VERIFY treats as a satisfied terminal outcome
# (no recovery). A deny-by-default gate halt is terminal and is NOT retried —
# retrying a safety denial would defeat deny-by-default.
_SATISFIED = ("converged", "halted_by_gate")

# Hard ceiling on recovery escalation. The loop can NEVER recover unboundedly:
# total executions ≤ 1 + MAX_RECOVER_CEILING, each itself a bounded cycle.
MAX_RECOVER_CEILING = 8

_LABEL = ("SGH structured-graph control · advisory · experimental "
          "(inspiration: arXiv:2604.11378, own-code reimplementation)")
_TERMINATION_NOTE = (
    "advisory — termination is BOUNDED BY CONSTRUCTION (finite budget × finite "
    "recover attempts), so the machine ALWAYS reaches HALT. This is NOT a formal "
    "termination/soundness proof; a real Lean termination theorem is future work.")


def _sha(obj: Any) -> str:
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def build_plan(tasks: Optional[Sequence[str]] = None,
               meta: Optional[Mapping[str, Any]] = None) -> dict:
    """Build the IMMUTABLE plan DAG, fixed once at plan time.

    The plan is a linear-by-default dependency DAG over ``tasks`` (each task
    depends on the previous one). The default single-task plan wraps the one
    governed cycle. ``plan_version`` is derived from the plan body, so any
    change to the tasks/meta yields a DIFFERENT plan version — a new immutable
    plan, never an in-place mutation. Returns a fresh dict each call.
    """
    task_tuple = tuple(tasks) if tasks else ("governed-cycle",)
    nodes = []
    edges = []
    for idx, name in enumerate(task_tuple):
        deps = [task_tuple[idx - 1]] if idx > 0 else []
        nodes.append({"id": name, "index": idx, "deps": list(deps)})
        if deps:
            edges.append({"from": deps[0], "to": name})
    body = {"nodes": nodes, "edges": edges, "meta": dict(meta or {})}
    plan_version = "sgh-plan-" + _sha(body)[:16]
    return {
        "plan_version": plan_version,
        "immutable": True,
        "nodes": nodes,
        "edges": edges,
        "meta": dict(meta or {}),
        "note": ("plan DAG fixed at plan time; a new plan version is a NEW "
                 "immutable plan — there is no mid-run mutation."),
    }


def _cycle_final_status(cycle: Any) -> Optional[str]:
    if isinstance(cycle, Mapping):
        st = cycle.get("final_status")
        return st if isinstance(st, str) else None
    return None


def _cycle_chain_hash(cycle: Any) -> Optional[str]:
    if isinstance(cycle, Mapping):
        h = cycle.get("cycle_chain_final_hash")
        return h if isinstance(h, str) else None
    return None


def wrap_governed_cycle(first_cycle: Mapping[str, Any],
                        reexecute: Callable[[], Mapping[str, Any]],
                        *,
                        sha_fn: Callable[[Any], str] = _sha,
                        max_recover: int = 2,
                        plan: Optional[Mapping[str, Any]] = None,
                        plan_tasks: Optional[Sequence[str]] = None) -> dict:
    """Run the SGH node state machine over an ALREADY-EXECUTED governed cycle.

    ``first_cycle`` is the result of the first (already run) governed cycle;
    ``reexecute`` re-runs the SAME bounded governed cycle for a RECOVER attempt.
    The plan DAG is built ONCE (immutable) and the same ``plan_version`` is used
    across all recover attempts — NO mid-run plan mutation.

    Escalation is STRICTLY BOUNDED: at most ``max_recover`` (clamped to
    ``MAX_RECOVER_CEILING``) re-executions; when exhausted the machine escalates
    and HALTs. It therefore ALWAYS reaches HALT. Returns the SGH trace fields
    plus the wrapped cycle result under ``cycle``. NEVER raises: any failure in
    ``reexecute`` is recorded as an honest RECOVER→HALT escalation.
    """
    try:
        max_recover = int(max_recover)
    except Exception:
        max_recover = 0
    if max_recover < 0:
        max_recover = 0
    max_recover = min(max_recover, MAX_RECOVER_CEILING)

    the_plan = dict(plan) if isinstance(plan, Mapping) else build_plan(plan_tasks)
    plan_version = the_plan.get("plan_version", "sgh-plan-unknown")
    # The node the machine executes. Default single-node plan → the governed cycle.
    node_id = (the_plan.get("nodes") or [{"id": "governed-cycle"}])[0].get("id", "governed-cycle")

    trace: list[dict] = []
    prev_hash = "SGH-GENESIS"

    def emit(node: str, from_state: str, to_state: str, extra: Optional[dict] = None) -> None:
        nonlocal prev_hash
        body = {"seq": len(trace), "node": node, "from_state": from_state,
                "to_state": to_state, "plan_version": plan_version}
        if extra:
            body.update(extra)
        h = sha_fn({"kind": "sgh_transition", "body": body, "prev_hash": prev_hash})
        trace.append({**body, "kind": "sgh_transition", "prev_hash": prev_hash, "hash": h})
        prev_hash = h

    # PLAN — the immutable plan DAG exists; enter the machine.
    emit(node_id, "INIT", "PLAN", {"plan_immutable": bool(the_plan.get("immutable"))})

    cycle = first_cycle
    recover_attempts = 0
    escalated = False
    halt_reason: str

    while True:
        # EXECUTE — the governed cycle has produced (or re-produced) a result.
        emit(node_id, "PLAN" if not recover_attempts else "RECOVER", "EXECUTE",
             {"execution": recover_attempts, "cycle_chain_final_hash": _cycle_chain_hash(cycle)})
        # VERIFY — inspect the honest cycle final_status (the Λ-gate verdict and
        # convergence/halt reason). This does NOT rewrite the verdict.
        status = _cycle_final_status(cycle)
        emit(node_id, "EXECUTE", "VERIFY", {"cycle_final_status": status})
        if status in _SATISFIED:
            halt_reason = status or "unknown"
            emit(node_id, "VERIFY", "HALT", {"halt_reason": halt_reason, "escalated": False})
            break
        # Not satisfied → RECOVER (bounded).
        emit(node_id, "VERIFY", "RECOVER",
             {"cycle_final_status": status, "recover_attempts": recover_attempts,
              "max_recover": max_recover})
        if recover_attempts >= max_recover:
            # Strict bound reached → escalate and HALT. NEVER unbounded.
            escalated = True
            halt_reason = "escalated_after_%d_recover_attempts:%s" % (recover_attempts, status)
            emit(node_id, "RECOVER", "HALT", {"halt_reason": halt_reason, "escalated": True})
            break
        recover_attempts += 1
        try:
            nxt = reexecute()
            cycle = nxt if isinstance(nxt, Mapping) else cycle
        except Exception as exc:  # a recover attempt must never crash the machine
            escalated = True
            halt_reason = "escalated_on_reexecute_error:%s" % (type(exc).__name__,)
            emit(node_id, "RECOVER", "HALT", {"halt_reason": halt_reason, "escalated": True})
            break
        # loop back → EXECUTE with the re-run cycle (same immutable plan_version)

    return {
        "sgh": True,
        "label": _LABEL,
        "plan_version": plan_version,
        "plan_dag": the_plan,
        "node_state_trace": trace,
        "sgh_final_state": "HALT",
        "sgh_halt_reason": halt_reason,
        "recover_attempts": recover_attempts,
        "max_recover": max_recover,
        "escalated": escalated,
        "bounded": True,
        "sgh_chain_final_hash": prev_hash,
        "termination": _TERMINATION_NOTE,
        "inspiration": "arXiv:2604.11378 (position paper; own-code reimplementation, not vendored)",
        "issued_at": datetime.now(timezone.utc).isoformat(),
        "cycle": first_cycle,
    }
