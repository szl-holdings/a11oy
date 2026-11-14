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
import math
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


# This is a local, serial executor for the separate governed-graph contract.
# It does not alter the legacy cycle wrapper or grant production authority.
MAX_LOCAL_NODE_ATTEMPTS = 1 + MAX_RECOVER_CEILING
MAX_LOCAL_TOTAL_ATTEMPTS = 256
_LOCAL_ROLES = frozenset({
    "scope", "planner", "worker", "reducer", "verifier", "synthesizer",
})
_LOCAL_GENESIS = "SGH-LOCAL-GENESIS"


def _local_json_copy(value: Any) -> Any:
    """Copy strict JSON data, rejecting Python-only and non-finite values."""
    if value is None or type(value) in (str, bool, int):
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError("non-finite JSON number")
        return value
    if type(value) is list:
        return [_local_json_copy(item) for item in value]
    if type(value) is dict:
        if any(type(key) is not str for key in value):
            raise ValueError("non-string JSON key")
        return {key: _local_json_copy(item) for key, item in value.items()}
    raise ValueError("non-JSON value")


def _local_not_invoked(reason: str, digest: Optional[str] = None,
                       node_ids: Sequence[str] = (),
                       blockers: Sequence[str] = ()) -> dict:
    return {
        "disposition": "NOT_INVOKED",
        "reason": reason,
        "contract_digest": digest,
        "plan_id": "ggp-" + digest[:20] if digest else None,
        "nodes": {
            node_id: {"status": "NOT_INVOKED", "reason": reason,
                      "attempts": 0, "outputs": None, "receipt_id": None}
            for node_id in node_ids
        },
        "transitions": [],
        "chain_final_hash": _LOCAL_GENESIS,
        "attempts_used": 0,
        "implementation_invocations": 0,
        "blockers": list(blockers),
        "mode": "LOCAL_READ_ONLY",
        "durable": False,
    }


def execute_governed_plan(
    contract: Mapping[str, Any], expected_digest: str, *,
    input_values: Mapping[str, Any],
    admissions: Mapping[str, Callable[[dict], bool]],
    implementations: Mapping[str, Callable[[dict], dict]],
    verifiers: Mapping[str, Callable[[dict], bool]],
    max_attempts_per_node: int = 2,
    max_total_attempts: int = MAX_LOCAL_TOTAL_ATTEMPTS,
    cancelled: Optional[Callable[[], bool]] = None,
    clock: Optional[Callable[[], float]] = None,
    deadline: Optional[float] = None,
) -> dict:
    """Execute one analyzed graph using explicitly supplied local capabilities.

    Each implementation receives an isolated context and returns either
    ``{"status": "SUCCEEDED", "outputs": {...}}`` or the explicit local-only
    ``{"status": "RETRYABLE_FAILURE", "failure_kind": "LOCAL"}`` (also
    ``SYNTHETIC``). Admission and verification must return exact booleans.
    Callables are trusted Python code; this function is not an I/O sandbox.
    The returned receipts are deterministic, in-memory records, not signatures
    or durable effect receipts. A synchronous callback cannot be preempted.
    """
    try:
        from routers.governed_graph_operations import analyse_graph

        frozen_request = _local_json_copy(contract)
        # Check serializability before invoking the analyzer or any capability.
        json.dumps(frozen_request, allow_nan=False)
        analysis = analyse_graph(frozen_request)
        frozen = _local_json_copy(analysis["normalized_contract"])
        digest = _sha(frozen)
    except Exception:
        return _local_not_invoked("INVALID_CONTRACT")

    schedule = [node_id for batch in analysis["topology"]["schedule"]
                for node_id in batch["nodes"]]
    by_id = {node["id"]: node for node in frozen["nodes"]}
    if len(schedule) != len(by_id) or set(schedule) != set(by_id):
        return _local_not_invoked("INVALID_SCHEDULE", digest)
    if digest != analysis["contract_digest"]:
        return _local_not_invoked("ANALYSIS_DIGEST_MISMATCH", digest, schedule)
    if type(expected_digest) is not str or digest != expected_digest:
        return _local_not_invoked("DIGEST_MISMATCH", digest, schedule)
    if analysis["gates"]["pass"] is not True:
        blocker_codes = [issue["code"] for issue in analysis["gates"]["blockers"]]
        return _local_not_invoked("ANALYSIS_BLOCKED", digest, schedule,
                                  blocker_codes)

    if (type(max_attempts_per_node) is not int
            or not 1 <= max_attempts_per_node <= MAX_LOCAL_NODE_ATTEMPTS
            or type(max_total_attempts) is not int
            or not 1 <= max_total_attempts <= MAX_LOCAL_TOTAL_ATTEMPTS):
        return _local_not_invoked("INVALID_ATTEMPT_BUDGET", digest, schedule)
    attempt_budget = min(max_total_attempts,
                         frozen["budget"]["max_total_iterations"])
    if len(schedule) > attempt_budget:
        return _local_not_invoked("ATTEMPT_BUDGET_INSUFFICIENT", digest, schedule)
    if cancelled is not None and not callable(cancelled):
        return _local_not_invoked("INVALID_CANCELLATION_CAPABILITY", digest,
                                  schedule)
    if deadline is not None:
        if (type(deadline) not in (int, float) or not math.isfinite(deadline)
                or not callable(clock)):
            return _local_not_invoked("INVALID_DEADLINE_CAPABILITY", digest,
                                      schedule)

    try:
        values = _local_json_copy(input_values)
        json.dumps(values, allow_nan=False)
    except Exception:
        return _local_not_invoked("INVALID_INPUT_VALUES", digest, schedule)
    if (type(values) is not dict
            or set(values) != set(frozen["external_inputs"])):
        return _local_not_invoked("INPUT_VALUES_MISMATCH", digest, schedule)

    try:
        admitted = {node_id: admissions[node_id] for node_id in schedule}
        implemented = {node_id: implementations[node_id] for node_id in schedule}
        verified = {node_id: verifiers[node_id] for node_id in schedule}
    except (KeyError, TypeError):
        return _local_not_invoked("MISSING_CAPABILITY", digest, schedule)
    if any(not callable(capability) for capabilities in
           (admitted, implemented, verified)
           for capability in capabilities.values()):
        return _local_not_invoked("MISSING_CAPABILITY", digest, schedule)

    # Resolve every consumed artifact to exactly one declared source before any
    # callback. Control predecessors are never data providers.
    sources = {}
    external = set(frozen["external_inputs"])
    for node_id in schedule:
        node = by_id[node_id]
        if (node["role"] not in _LOCAL_ROLES or node["max_iterations"] is not None
                or node["exit_conditions"]):
            return _local_not_invoked("UNSUPPORTED_NODE_SEMANTICS", digest,
                                      schedule)
        if (node["side_effecting"] or node["writes"]
                or node["authority"] in ("WRITE_GOVERNED", "HUMAN")):
            return _local_not_invoked("EFFECTS_UNSUPPORTED", digest, schedule)
        for predecessor in node["depends_on"]:
            if not set(by_id[predecessor]["produces"]) & set(node["consumes"]):
                return _local_not_invoked("FAKE_DATA_EDGE_UNSUPPORTED", digest,
                                          schedule)
        for key in node["consumes"]:
            providers = (["external"] if key in external else []) + [
                predecessor for predecessor in node["depends_on"]
                if key in by_id[predecessor]["produces"]
            ]
            if len(providers) != 1:
                return _local_not_invoked(
                    "INPUT_PROVIDER_AMBIGUOUS" if providers else "INPUT_UNAVAILABLE",
                    digest, schedule)
            sources[(node_id, key)] = providers[0]

    states = {
        node_id: {"status": "PENDING", "reason": None, "attempts": 0,
                  "outputs": None, "receipt_id": None}
        for node_id in schedule
    }
    transitions = []
    chain = _LOCAL_GENESIS
    attempts_used = 0
    implementation_invocations = 0

    def predecessor_receipts(node: dict) -> list[dict]:
        return [
            {"node_id": predecessor,
             "receipt_id": states[predecessor]["receipt_id"]}
            for predecessor in sorted(set(node["depends_on"] +
                                          node["control_after"]))
            if states[predecessor]["receipt_id"] is not None
        ]

    def emit(node_id: str, attempt: int, predecessors: list[dict],
             inputs: Any, outputs: Any, result: str,
             reason: str, terminal: bool) -> str:
        nonlocal chain
        body = {
            "sequence": len(transitions),
            "contract_digest": digest,
            "node_id": node_id,
            "attempt": attempt,
            "predecessor_receipts": _local_json_copy(predecessors),
            "input_hash": _sha(inputs),
            "output_hash": _sha(outputs),
            "result": result,
            "reason": reason,
            "terminal": terminal,
        }
        receipt_id = _sha({"kind": "sgh_local_transition/v1",
                           "body": body, "previous_receipt_id": chain})
        transitions.append({**body, "kind": "sgh_local_transition/v1",
                            "previous_receipt_id": chain,
                            "receipt_id": receipt_id})
        chain = receipt_id
        return receipt_id

    halt_reason = None
    for node_id in schedule:
        node = by_id[node_id]
        predecessors = predecessor_receipts(node)
        if any(states[dep]["status"] != "SUCCEEDED" for dep in
               node["depends_on"] + node["control_after"]):
            halt_reason = "PREDECESSOR_UNVERIFIED"
            states[node_id].update(status="BLOCKED", reason=halt_reason)
            break

        inputs = {}
        for key in node["consumes"]:
            provider = sources[(node_id, key)]
            if provider == "external":
                inputs[key] = _local_json_copy(values[key])
            else:
                predecessor_outputs = states[provider]["outputs"]
                if (states[provider]["status"] != "SUCCEEDED"
                        or predecessor_outputs is None
                        or key not in predecessor_outputs):
                    halt_reason = "PREDECESSOR_OUTPUT_UNAVAILABLE"
                    states[node_id].update(status="BLOCKED", reason=halt_reason)
                    break
                inputs[key] = _local_json_copy(predecessor_outputs[key])
        if halt_reason:
            break

        for attempt in range(1, max_attempts_per_node + 1):
            if attempts_used >= attempt_budget:
                halt_reason = "ATTEMPT_BUDGET_EXHAUSTED"
            if halt_reason is None and cancelled is not None:
                try:
                    cancellation = cancelled()
                    if cancellation is True:
                        halt_reason = "CANCELLED"
                    elif cancellation is not False:
                        halt_reason = "CANCELLATION_AMBIGUOUS"
                except Exception:
                    halt_reason = "CANCELLATION_CHECK_ERROR"
            if halt_reason is None and deadline is not None:
                try:
                    observed = clock()
                    if (type(observed) not in (int, float)
                            or not math.isfinite(observed)):
                        halt_reason = "CLOCK_INVALID"
                    elif observed >= deadline:
                        halt_reason = "DEADLINE_REACHED"
                except Exception:
                    halt_reason = "CLOCK_ERROR"
            if halt_reason is not None:
                states[node_id].update(status="BLOCKED", reason=halt_reason)
                break

            attempts_used += 1
            states[node_id]["attempts"] = attempt
            context = {
                "contract_digest": digest,
                "node": _local_json_copy(node),
                "inputs": _local_json_copy(inputs),
                "attempt": attempt,
                "predecessor_receipts": _local_json_copy(predecessors),
            }
            try:
                permission = admitted[node_id](_local_json_copy(context))
            except Exception:
                permission = None
                reason = "ADMISSION_EXCEPTION"
            else:
                reason = ("ADMISSION_DENIED" if permission is False
                          else "ADMISSION_AMBIGUOUS")
            if permission is not True:
                status = "DENIED" if permission is False else "FAILED"
                states[node_id].update(status=status, reason=reason)
                states[node_id]["receipt_id"] = emit(
                    node_id, attempt, predecessors, inputs, None,
                    status, reason, True)
                halt_reason = reason
                break

            implementation_invocations += 1
            try:
                raw_outcome = implemented[node_id](_local_json_copy(context))
            except Exception:
                outcome = None
                reason = "IMPLEMENTATION_EXCEPTION"
            else:
                try:
                    outcome = _local_json_copy(raw_outcome)
                except Exception:
                    outcome = None
                reason = "AMBIGUOUS_OUTCOME"

            if (type(outcome) is dict and set(outcome) == {"status", "failure_kind"}
                    and outcome["status"] == "RETRYABLE_FAILURE"
                    and outcome["failure_kind"] in ("LOCAL", "SYNTHETIC")):
                if (attempt < max_attempts_per_node
                        and attempts_used < attempt_budget):
                    emit(node_id, attempt, predecessors, inputs, None,
                         "RETRYABLE_FAILURE", "LOCAL_RETRYABLE_FAILURE", False)
                    continue
                reason = "RETRY_BUDGET_EXHAUSTED"
                states[node_id].update(status="FAILED", reason=reason)
                states[node_id]["receipt_id"] = emit(
                    node_id, attempt, predecessors, inputs, None,
                    "FAILED", reason, True)
                halt_reason = reason
                break

            if (type(outcome) is not dict or set(outcome) != {"status", "outputs"}
                    or outcome["status"] != "SUCCEEDED"):
                states[node_id].update(status="FAILED", reason=reason)
                states[node_id]["receipt_id"] = emit(
                    node_id, attempt, predecessors, inputs, None,
                    "FAILED", reason, True)
                halt_reason = reason
                break
            try:
                outputs = _local_json_copy(outcome["outputs"])
                json.dumps(outputs, allow_nan=False)
            except Exception:
                outputs = None
            if (type(outputs) is not dict
                    or set(outputs) != set(node["produces"])):
                reason = "OUTPUT_CONTRACT_VIOLATION"
                states[node_id].update(status="FAILED", reason=reason)
                states[node_id]["receipt_id"] = emit(
                    node_id, attempt, predecessors, inputs, None,
                    "FAILED", reason, True)
                halt_reason = reason
                break

            verification_context = {**context, "outputs": outputs}
            try:
                accepted = verified[node_id](
                    _local_json_copy(verification_context))
            except Exception:
                accepted = None
                reason = "VERIFIER_EXCEPTION"
            else:
                reason = ("VERIFIER_REJECTED" if accepted is False
                          else "VERIFIER_AMBIGUOUS")
            if accepted is not True:
                states[node_id].update(status="FAILED", reason=reason)
                states[node_id]["receipt_id"] = emit(
                    node_id, attempt, predecessors, inputs, outputs,
                    "FAILED", reason, True)
                halt_reason = reason
                break

            receipt_id = emit(node_id, attempt, predecessors, inputs, outputs,
                              "SUCCEEDED", "VERIFIED", True)
            states[node_id].update(status="SUCCEEDED", reason="VERIFIED",
                                   outputs=_local_json_copy(outputs),
                                   receipt_id=receipt_id)
            break
        if halt_reason is not None:
            break

    if halt_reason is not None:
        for node_id in schedule:
            state = states[node_id]
            if state["status"] not in ("PENDING", "BLOCKED"):
                continue
            node = by_id[node_id]
            if state["status"] == "PENDING":
                reason = ("PREDECESSOR_UNVERIFIED" if any(
                    states[dep]["status"] != "SUCCEEDED"
                    for dep in node["depends_on"] + node["control_after"])
                    else "RUN_HALTED")
                state.update(status="BLOCKED", reason=reason)
            state["receipt_id"] = emit(
                node_id, 0, predecessor_receipts(node), None, None,
                "BLOCKED", state["reason"], True)

    return {
        "disposition": "BLOCKED" if halt_reason else "SUCCEEDED",
        "reason": halt_reason or "COMPLETED",
        "contract_digest": digest,
        "plan_id": analysis["plan_id"],
        "nodes": states,
        "transitions": transitions,
        "chain_final_hash": chain,
        "attempts_used": attempts_used,
        "implementation_invocations": implementation_invocations,
        "attempt_budget": attempt_budget,
        "blockers": [],
        "mode": "LOCAL_READ_ONLY",
        "durable": False,
    }
