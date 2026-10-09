# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""One run-step witness committed through the existing receipt ledger.

The in-memory Khipu DAG is not this store. Platform KhipuOS is not selected:
its constructor can open a store and still starts with empty graph indexes, and
runner persistence stays off unless a persist path is configured. This module
does not grant leases, does not retry an append, and does not claim
distributed exactly-once execution.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import time
from pathlib import Path
from typing import Any, Optional

from routers.governed_graph_operations import (
    EXECUTION_MODE,
    GraphContractError,
    analyse_graph,
)
import szl_action_identity as action_identity
from szl_lake_store import (
    CHAIN_HASH,
    SCHEMA as LAKE_SCHEMA,
    ReceiptLedger,
    canonical_hash,
)

SCHEMA = "szl.a11oy.code-runloop-receipt/v2"
ORGAN = "code-runloop"
STORE = "szl_lake_store.ReceiptLedger"
_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{1,80}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_LOCK_ATTEMPTS = 3
_APPEND_ATTEMPTS = 1
_BODY_KEYS = (
    "commit_policy",
    "configuration",
    "evidence_class",
    "evidence_set_sha256",
    "execution",
    "graph_digest",
    "guard_results",
    "id",
    "organ",
    "parent_receipt_id",
    "planning",
    "purpose",
    "query_sha256",
    "receipt_chain",
    "request_id",
    "retention",
    "retrieval",
    "schema",
    "signature_envelope",
    "signer",
    "source_revisions",
    "tenant_sha256",
    "test_result",
    "verification",
)
_ENVELOPE_KEYS = {
    "chain_alg",
    "chain_hash",
    "chain_index",
    "energy",
    "ingested_at",
    "organ",
    "prev_hash",
    "receipt",
    "receipt_id",
    "schema",
    "ts",
}
_COMMIT_POLICY = {
    "acknowledgement": "returned only after fsync",
    "exactly_once": False,
    "external_actions": "not admitted",
    "lease": "NOT_USED",
    "lock_acquire_attempts": _LOCK_ATTEMPTS,
    "max_append_attempts": _APPEND_ATTEMPTS,
    "terminal_states": ["COMMITTED", "DUPLICATE", "REJECTED"],
}
_RETENTION = {
    "audit": "the NDJSON envelope is the audit record",
    "automatic_expiry": False,
    "deletion": "not performed by this adapter",
    "partial_write": "a later verifier fail-closes and does not truncate the line",
    "policy": "append-only",
    "restart": "a new process replays the partitions and recomputes the chain",
    "stale_lock": "a leftover commit lock fail-closes new commits and is not stolen",
}
_NOT_APPLICABLE = (
    (
        "F4",
        "Nat backward-edge DAG property",
        "not durable workflow recovery",
    ),
    (
        "F7",
        "list FIFO order",
        "not retry, deduplication, or persistence",
    ),
    (
        "F22",
        "List.range",
        "not a distributed log",
    ),
)


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(65536)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def _root_file(name: str) -> Path:
    return Path(__file__).resolve().parent / name


def valid_request_id(value: Any) -> bool:
    return isinstance(value, str) and _REQUEST_ID.fullmatch(value) is not None


def tenant_scope(tenant: str) -> str:
    return hashlib.sha256(tenant.encode("utf-8")).hexdigest()


def request_component(request_id: Optional[str]) -> str:
    """Omitted ids share the key component 'derived' without becoming one client id."""
    if isinstance(request_id, str) and request_id:
        return request_id
    return "derived"


def idempotency_key(tenant_sha256: str, purpose: str, query_sha256: str,
                    request_id: str) -> str:
    return _sha256({
        "purpose": purpose,
        "query_sha256": query_sha256,
        "request_id": request_id,
        "tenant_sha256": tenant_sha256,
    })


PLAN_SCHEMA = "szl.code-plan-binding/v1"
_PLANS: dict[tuple[str, str], dict] = {}
_EXECUTION_OPTION_KEYS = (
    "destination_contract",
    "model",
    "profile",
    "sandbox",
    "state_changing",
    "state_changing_class",
)


def _bounded_text(value: Any, limit: int) -> str:
    if not isinstance(value, str):
        return ""
    return value[:limit]


def _execution_options(step: dict) -> dict:
    return {
        "sandbox": step.get("sandbox") is True,
        "state_changing": step.get("state_changing") is True,
        "profile": "",
        "model": "",
        "state_changing_class": "state-changing" if step.get("state_changing") else "read",
        "destination_contract": "governed-turn/v1",
    }


def _operation_for(step: dict) -> str:
    if step.get("n") == 1:
        return "ground"
    if step.get("sandbox") is True:
        return "execute"
    if step.get("mode") == "code":
        return "synthesize"
    if step.get("mode") == "research":
        return "cite"
    return "answer"


def bind_plan(body: dict) -> dict:
    """Stamp server step identity onto a modeled plan. This does not execute it."""
    steps = body.get("plan")
    if not isinstance(steps, list):
        return body
    material = []
    for step in steps:
        if not isinstance(step, dict):
            continue
        number = step.get("n")
        step["step_id"] = "step-%s" % number
        step["operation"] = _operation_for(step)
        step["destination"] = "governed-engine"
        step["execution_options"] = _execution_options(step)
        prompt = step.get("prompt") if isinstance(step.get("prompt"), str) else ""
        material.append({
            "step_id": step["step_id"],
            "operation": step["operation"],
            "destination": step["destination"],
            "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "execution_options": step["execution_options"],
        })
    revision = "rev-" + action_identity.digest({
        "mode": body.get("mode") if isinstance(body.get("mode"), str) else "",
        "steps": material,
    })
    body["plan_revision"] = revision
    for step in steps:
        if isinstance(step, dict):
            step["plan_revision"] = revision
    return body


def _plan_document(tenant: str, body: dict) -> dict:
    steps = []
    for step in body.get("plan") or []:
        if not isinstance(step, dict):
            continue
        steps.append({
            "n": step.get("n"),
            "step_id": step.get("step_id"),
            "mode": step.get("mode"),
            "prompt": step.get("prompt") if isinstance(step.get("prompt"), str) else "",
            "operation": step.get("operation"),
            "destination": step.get("destination"),
            "sandbox": step.get("sandbox") is True,
            "state_changing": step.get("state_changing") is True,
            "execution_options": step.get("execution_options"),
        })
    return {
        "schema": PLAN_SCHEMA,
        "tenant_sha256": tenant_scope(tenant),
        "run_id": body.get("run_id"),
        "plan_revision": body.get("plan_revision"),
        "purpose": body.get("purpose") or body.get("mode"),
        "steps": steps,
    }


def _plan_path(root: str, tenant_sha: str, run_id: str) -> str:
    return os.path.join(root, ORGAN, "plans", tenant_sha, run_id + ".json")


def save_plan(root: str, tenant: str, body: dict) -> str:
    """Remember a server-issued plan. An existing run id is not rewritten."""
    document = _plan_document(tenant, body)
    run_id = document.get("run_id")
    scope = document.get("tenant_sha256")
    if not isinstance(run_id, str) or not isinstance(scope, str):
        return "unavailable"
    key = (scope, run_id)
    if key not in _PLANS:
        _PLANS[key] = document
    if not root:
        return "memory"
    path = _plan_path(root, scope, run_id)
    if os.path.exists(path):
        return "persisted"
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        temporary = path + ".tmp"
        with open(temporary, "w", encoding="utf-8") as handle:
            json.dump(document, handle, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except OSError:
        return "memory"
    return "persisted"


def load_plan(root: str, tenant: str, run_id: str) -> Optional[dict]:
    scope = tenant_scope(tenant)
    key = (scope, run_id)
    cached = _PLANS.get(key)
    if isinstance(cached, dict):
        return cached
    if not root:
        return None
    path = _plan_path(root, scope, run_id)
    try:
        with open(path, "r", encoding="utf-8") as handle:
            document = json.loads(handle.read())
    except (OSError, json.JSONDecodeError):
        return None
    if (not isinstance(document, dict) or document.get("schema") != PLAN_SCHEMA
            or document.get("tenant_sha256") != scope or document.get("run_id") != run_id):
        return None
    _PLANS[key] = document
    return document


def admit_planned_step(root: str, tenant: str, body: dict, query: str, purpose: str) -> dict:
    """Admit a planned step from the server binding. A client id alone is not enough."""
    if not isinstance(body, dict) or "run_id" not in body:
        return {"ok": True, "legacy": True}
    try:
        run_id = action_identity.require_id(body.get("run_id"))
        step_id = action_identity.require_id(body.get("step_id"))
        plan_revision = action_identity.require_id(body.get("plan_revision"))
    except ValueError:
        return {"ok": False, "status": 400, "error": "run identity is not admitted"}
    plan = load_plan(root, tenant, run_id)
    if plan is None:
        return {"ok": False, "status": 409, "error": "run is not admitted"}
    step = None
    for item in plan.get("steps") or []:
        if isinstance(item, dict) and item.get("step_id") == step_id:
            step = item
            break
    if step is None:
        return {"ok": False, "status": 409, "error": "step is not admitted"}
    options = step.get("execution_options")
    if (purpose != step.get("mode") or query != step.get("prompt")
            or plan_revision != plan.get("plan_revision")
            or not isinstance(options, dict)
            or set(options) != set(_EXECUTION_OPTION_KEYS)):
        return {"ok": False, "status": 409, "error": "semantics conflict"}
    if "sandbox" in body and body.get("sandbox") is not options.get("sandbox"):
        return {"ok": False, "status": 409, "error": "semantics conflict"}
    if "state_changing" in body and body.get("state_changing") is not options.get("state_changing"):
        return {"ok": False, "status": 409, "error": "semantics conflict"}
    profile = body.get("harness_profile_id") if "harness_profile_id" in body else body.get("profile_id", "")
    model = body.get("model") if "model" in body else body.get("want_model", "")
    if profile is None:
        profile = ""
    if model is None:
        model = ""
    if not isinstance(profile, str) or not isinstance(model, str):
        return {"ok": False, "status": 409, "error": "semantics conflict"}
    if profile != options.get("profile") or model != options.get("model"):
        return {"ok": False, "status": 409, "error": "semantics conflict"}
    operation = step.get("operation")
    destination = step.get("destination")
    try:
        bound = action_identity.identity(
            tenant_id=str(plan.get("tenant_sha256") or ""),
            run_id=run_id,
            step_id=step_id,
            plan_revision=plan_revision,
            operation=str(operation or ""),
            destination=str(destination or ""),
            arguments={"prompt": step.get("prompt")},
            execution_options=options,
        )
    except ValueError:
        return {"ok": False, "status": 400, "error": "run identity is not admitted"}
    return {
        "ok": True,
        "legacy": False,
        "logical_id": bound.logical_id,
        "semantics_digest": bound.semantics_digest,
        "run_id": run_id,
        "step_id": step_id,
        "plan_revision": plan_revision,
        "operation": operation,
        "destination": destination,
        "query": step.get("prompt"),
        "purpose": step.get("mode"),
        "sandbox": options.get("sandbox") is True,
        "state_changing": options.get("state_changing") is True,
        "profile": options.get("profile") or "",
        "model": options.get("model") or "",
        "execution_options": options,
    }


def _result_record(run: dict) -> dict:
    if not isinstance(run, dict):
        run = {}
    code = run.get("code") if isinstance(run.get("code"), dict) else None
    code_out = None
    if code is not None:
        code_out = {
            "language": _bounded_text(code.get("language"), 40),
            "description": _bounded_text(code.get("description"), 500),
            "code": _bounded_text(code.get("code"), 8000),
        }
    sandbox = run.get("sandbox") if isinstance(run.get("sandbox"), dict) else None
    sandbox_out = None
    if sandbox is not None:
        sandbox_out = {
            "stdout": _bounded_text(sandbox.get("stdout"), 4000),
            "stderr": _bounded_text(sandbox.get("stderr"), 4000),
            "executed": sandbox.get("executed") is True,
            "blocked": sandbox.get("blocked") is True,
            "isolation": _bounded_text(sandbox.get("isolation"), 240),
        }
    historical = _bounded_text(run.get("execution_status"), 160) or "UNKNOWN"
    body = {
        "schema": "szl.runstep-result/v1",
        "availability": "AVAILABLE",
        "historical_execution": historical,
        "decision": _bounded_text(run.get("decision"), 80),
        "execution_status": historical,
        "summary": _bounded_text(run.get("summary"), 2000),
        "answer": _bounded_text(run.get("answer"), 8000),
        "code": code_out,
        "sandbox": sandbox_out,
    }
    try:
        body["digest"] = action_identity.digest(
            {key: value for key, value in body.items() if key != "digest"}
        )
    except ValueError:
        return {
            "schema": "szl.runstep-result/v1",
            "availability": "RESULT_UNAVAILABLE",
            "historical_execution": historical,
            "reason": "result could not be canonically stored",
        }
    return body


def restore_result(receipt: dict) -> dict:
    """Separate a stored execution status from whether its output can be shown."""
    config = receipt.get("configuration") if isinstance(receipt, dict) else None
    record = config.get("result_record") if isinstance(config, dict) else None
    historical = "UNKNOWN"
    if isinstance(record, dict) and isinstance(record.get("historical_execution"), str):
        historical = record["historical_execution"]
    unavailable = {
        "run": None,
        "result_availability": "RESULT_UNAVAILABLE",
        "historical_execution": historical,
    }
    if not isinstance(record, dict) or record.get("availability") != "AVAILABLE":
        return unavailable
    try:
        expect = action_identity.digest(
            {key: value for key, value in record.items() if key != "digest"}
        )
    except ValueError:
        return unavailable
    if record.get("digest") != expect:
        return unavailable
    return {
        "run": {
            "decision": record.get("decision") or "",
            "answer": record.get("answer") or "",
            "code": record.get("code"),
            "sandbox": record.get("sandbox"),
            "execution_status": record.get("execution_status") or "",
            "summary": record.get("summary") or "",
            "restored": True,
            "result_schema": record.get("schema"),
            "result_digest": record.get("digest"),
        },
        "result_availability": "AVAILABLE",
        "historical_execution": historical,
    }


def note_attempt(root: str, logical_id: str, attempt_id: str, kind: str) -> bool:
    """Record a delivery attempt outside the effect ledger."""
    if not root or not isinstance(logical_id, str) or not logical_id:
        return False
    try:
        action_identity.require_id(attempt_id)
    except ValueError:
        return False
    if kind not in {"execute", "replay"}:
        return False
    directory = os.path.join(root, ORGAN + "-attempts")
    path = os.path.join(directory, "attempts.jsonl")
    try:
        os.makedirs(directory, exist_ok=True)
        line = json.dumps({
            "schema": "szl.action-attempt/v1",
            "logical_id": logical_id,
            "attempt_id": attempt_id,
            "kind": kind,
        }, sort_keys=True, separators=(",", ":"))
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(line + "\n")
            handle.flush()
            os.fsync(handle.fileno())
    except OSError:
        return False
    return True


def admit_measure(measure: Any) -> dict:
    """Domain guard for an optional numeric measure. Absence is not applicability."""
    identity = "a11oy_code_runloop_journey.admit_measure"
    if measure is None:
        return {
            "name": "numeric-measure",
            "role": "NOT_APPLICABLE",
            "result": "NOT_APPLICABLE",
            "implementation": identity,
            "reason": "this request has no numeric measure",
        }
    rejected = {
        "name": "numeric-measure",
        "role": "enforcement",
        "result": "REJECTED",
        "implementation": identity,
    }
    if isinstance(measure, dict):
        if set(measure) - {"value", "unit"}:
            rejected["reason"] = "unexpected measure fields"
            return rejected
        value = measure.get("value")
        unit = measure.get("unit")
    else:
        value = measure
        unit = None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        rejected["reason"] = "measure value is not a real number"
        return rejected
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        rejected["reason"] = "measure is not finite"
        return rejected
    if isinstance(value, int) and value.bit_length() > 32:
        rejected["reason"] = "measure overflows the admitted integer domain"
        return rejected
    if isinstance(value, float) and abs(value) > 1000000:
        rejected["reason"] = "measure overflows the admitted magnitude"
        return rejected
    if unit is not None:
        rejected["reason"] = "this path admits no unit and does not invent joules"
        return rejected
    rejected["reason"] = "this path has no numeric formula input"
    return rejected


def _formula_guards() -> list[dict]:
    formulas = _root_file("szl_formulas.py")
    file_sha = _file_sha256(formulas) if formulas.is_file() else "ABSENT"
    rows = []
    for name, statement, reason in _NOT_APPLICABLE:
        rows.append({
            "name": name,
            "statement": statement,
            "role": "NOT_APPLICABLE",
            "result": "NOT_APPLICABLE",
            "reason": reason,
            "callable": None,
            "caller": None,
            "loaded_package": "NOT_ATTRIBUTED",
            "inlined_file_sha256": file_sha,
            "standalone_package": "szl-formulas@0784a8c1 bytes were not matched",
        })
    return rows


def _limit_guards(query: str, purpose: str) -> list[dict]:
    encoded = query.encode("utf-8")
    chars_ok = 0 < len(query) <= 2000
    bytes_ok = len(encoded) <= 8192
    purpose_ok = purpose in {"chat", "code", "research"}
    return [
        {
            "name": "query-character-limit",
            "role": "enforcement",
            "result": "PASS" if chars_ok else "FAIL",
            "implementation": "a11oy_code_runloop._admit_query",
            "limit": 2000,
            "observed": len(query),
        },
        {
            "name": "query-utf8-byte-limit",
            "role": "enforcement",
            "result": "PASS" if bytes_ok else "FAIL",
            "implementation": "a11oy_code_runloop._admit_query",
            "limit": 8192,
            "observed": len(encoded),
        },
        {
            "name": "purpose-closed-set",
            "role": "enforcement",
            "result": "PASS" if purpose_ok else "FAIL",
            "implementation": "a11oy_code_runloop._admit_query",
            "admitted": ["chat", "code", "research"],
        },
    ]


def _evidence_graph(handles: list[str]) -> dict:
    reads = []
    for handle in handles:
        text = str(handle).strip()
        if text and text not in reads and len(text) <= 128 and len(reads) < 8:
            reads.append(text)
    return {
        "schema": "szl.governed-graph/v1",
        "graph_id": "code-runloop-evidence",
        "goal": "Plan authorized evidence handles without execution.",
        "external_inputs": ["query.sha256"],
        "nodes": [
            {
                "id": "retrieve",
                "label": "Authorized evidence handles",
                "role": "worker",
                "consumes": ["query.sha256"],
                "produces": ["evidence.handles"],
                "reads": reads,
                "authority": "READ_ONLY",
                "side_effecting": False,
            },
            {
                "id": "plan",
                "label": "Plan only",
                "role": "planner",
                "depends_on": ["retrieve"],
                "consumes": ["evidence.handles"],
                "produces": ["plan.digest"],
                "authority": "READ_ONLY",
                "side_effecting": False,
            },
        ],
        "anchors": [
            {
                "id": "evidence-handles",
                "type": "source",
                "nodes": ["retrieve", "plan"],
                "required": True,
                "description": "The plan terminal is bound to the handles this request retrieved.",
            }
        ],
        "budget": {
            "max_nodes": 8,
            "max_parallel": 1,
            "max_depth": 4,
            "max_total_iterations": 4,
        },
    }


def _planning(handles: list[str]) -> dict:
    try:
        analysis = analyse_graph(_evidence_graph(handles))
    except GraphContractError as exc:
        return {
            "ok": False,
            "error": "graph contract rejected",
            "detail": str(exc)[:240],
            "execution_mode": EXECUTION_MODE,
            "effectors": 0,
        }
    execution = analysis.get("execution") or {}
    gates = analysis.get("gates") if isinstance(analysis.get("gates"), dict) else {}
    blockers = gates.get("blockers")
    if not isinstance(blockers, list):
        blockers = analysis.get("blockers") if isinstance(analysis.get("blockers"), list) else []
    ok = (
        analysis.get("ok") is True
        and gates.get("pass") is True
        and analysis.get("decision") == "READY_TO_ORCHESTRATE"
        and execution.get("mode") == "PLAN_ONLY"
        and execution.get("authorized") is False
        and execution.get("effectors") == 0
        and execution.get("writes") == 0
        and execution.get("provider_calls") == 0
        and not blockers
    )
    graph_path = _root_file("routers") / "governed_graph_operations.py"
    return {
        "ok": ok,
        "schema": analysis.get("schema"),
        "execution_mode": execution.get("mode"),
        "authorized": False,
        "effectors": execution.get("effectors"),
        "writes": execution.get("writes"),
        "provider_calls": execution.get("provider_calls"),
        "decision": analysis.get("decision"),
        "plan_id": analysis.get("plan_id"),
        "graph_digest": analysis.get("contract_digest"),
        "implementation": "routers.governed_graph_operations.analyse_graph",
        "implementation_sha256": _file_sha256(graph_path),
        "blockers": blockers,
    }


def _unknown_retrieval() -> dict:
    return {
        "backend": "UNKNOWN",
        "corpus_generation": "UNKNOWN",
        "source_handles": [],
        "fallback": "UNKNOWN",
        "abstention": "UNKNOWN",
        "plane": "UNKNOWN",
        "outcome": "UNKNOWN",
    }


def _retrieval_from_run(run: dict) -> dict:
    raw = run.get("retrieval") if isinstance(run, dict) else None
    if not isinstance(raw, dict):
        return _unknown_retrieval()
    found = _unknown_retrieval()
    for key in found:
        if key in raw and raw[key] is not None:
            found[key] = raw[key]
    handles = found.get("source_handles")
    if not isinstance(handles, list):
        found["source_handles"] = []
    else:
        found["source_handles"] = [str(item)[:128] for item in handles[:8]]
    return found


def _guard_rows(query: str, purpose: str, planning: dict, measure: Any) -> list[dict]:
    rows = _limit_guards(query, purpose)
    rows.append({
        "name": "graph-budget",
        "role": "enforcement",
        "result": "PASS" if planning.get("ok") is True else "FAIL",
        "implementation": planning.get("implementation"),
        "implementation_sha256": planning.get("implementation_sha256"),
        "execution_mode": planning.get("execution_mode"),
        "effectors": planning.get("effectors"),
    })
    if measure is None:
        rows.append(admit_measure(None))
    rows.extend(_formula_guards())
    return rows


def _enforcement_ok(rows: list[dict]) -> bool:
    for row in rows:
        if row.get("role") == "enforcement" and row.get("result") != "PASS":
            return False
    return True


def _signature_parts(run: dict) -> tuple[dict, dict, str, str]:
    envelope = run.get("signed_receipt") if isinstance(run, dict) else None
    if not isinstance(envelope, dict):
        envelope = {"signed": False, "signatures": []}
    signed = envelope.get("signed") is True
    evidence = "DECLARED" if signed else "SIMULATED"
    signer = "HOST" if signed else "SIMULATED"
    try:
        import a11oy_code_engine as engine
        verdict = engine.verify_run({
            "receipt_chain": run.get("receipt_chain") or [],
            "signed_receipt": envelope,
        })
    except Exception:
        verdict = {}
    verification = {
        "chain_intact": verdict.get("chain_intact") is True,
        "signature_valid": False,
        "verified": False,
        "signature_check": "host verifier not supplied",
        "evidence_class": evidence,
        "signer": signer,
    }
    return envelope, verification, evidence, signer


def _configuration(run: dict) -> dict:
    flag = (os.environ.get("SZL_SECOND_BRAIN_RAG") or "").strip().lower()
    build = (os.environ.get("A11OY_BUILD_SHA") or "").strip()
    inference = run.get("inference") if isinstance(run, dict) else None
    if not isinstance(inference, dict):
        inference = {}
    return {
        "authorization_handoff": (
            "caller Bearer only; this route does not inject a server credential"
        ),
        "build_sha": build if re.fullmatch(r"[0-9a-f]{40}", build) else "UNKNOWN",
        "khipu_dag": "in-memory; not selected",
        "khipu_os": "not selected; constructor leaves graph indexes empty",
        "model_mode": inference.get("mode") or "UNKNOWN",
        "second_brain_bridge": "not called by this route",
        "second_brain_rag": "ON" if flag in {"1", "true", "yes"} else "OFF",
        "store": STORE,
        "store_schema": LAKE_SCHEMA,
        "chain_alg": CHAIN_HASH,
    }


def _execution(run: dict) -> dict:
    inference = run.get("inference") if isinstance(run, dict) else {}
    if not isinstance(inference, dict):
        inference = {}
    mode = inference.get("mode")
    if mode == "generative":
        provider_calls = 1
    elif mode == "unavailable":
        provider_calls = inference.get("attempts") or 1
    else:
        provider_calls = 0
    return {
        "status": (run or {}).get("execution_status") or "UNKNOWN",
        "provider_calls": provider_calls,
        "executed": (run or {}).get("executed") is True,
    }


def build_record(query: str, purpose: str, tenant: str, request_id: Optional[str],
                 run: dict, measure: Any = None, action: Optional[dict] = None) -> dict:
    retrieval = _retrieval_from_run(run)
    planning = _planning(list(retrieval.get("source_handles") or []))
    guards = _guard_rows(query, purpose, planning, measure)
    envelope, verification, evidence, signer = _signature_parts(run)
    scope = tenant_scope(tenant)
    query_sha = hashlib.sha256(query.encode("utf-8")).hexdigest()
    stored_request_id = request_id if isinstance(request_id, str) and request_id else None
    evidence_digest = _sha256({
        "abstention": retrieval.get("abstention"),
        "backend": retrieval.get("backend"),
        "corpus_generation": retrieval.get("corpus_generation"),
        "fallback": retrieval.get("fallback"),
        "outcome": retrieval.get("outcome"),
        "source_handles": retrieval.get("source_handles"),
    })
    passed = _enforcement_ok(guards) and verification.get("chain_intact") is True
    configuration = _configuration(run)
    configuration["result_record"] = _result_record(run)
    if isinstance(action, dict):
        configuration["action_identity"] = {
            "schema": "szl.logical-action/v1",
            "logical_id": action.get("logical_id"),
            "semantics_digest": action.get("semantics_digest"),
            "run_id": action.get("run_id"),
            "step_id": action.get("step_id"),
            "plan_revision": action.get("plan_revision"),
            "operation": action.get("operation"),
        }
    return {
        "schema": SCHEMA,
        "id": idempotency_key(scope, purpose, query_sha, request_component(stored_request_id)),
        "request_id": stored_request_id,
        "tenant_sha256": scope,
        "purpose": purpose,
        "query_sha256": query_sha,
        "organ": ORGAN,
        "parent_receipt_id": None,
        "retrieval": retrieval,
        "evidence_set_sha256": evidence_digest,
        "graph_digest": planning.get("graph_digest"),
        "planning": {
            "authorized": False,
            "decision": planning.get("decision"),
            "effectors": planning.get("effectors"),
            "execution_mode": planning.get("execution_mode"),
            "plan_id": planning.get("plan_id"),
            "provider_calls": 0,
            "writes": 0,
        },
        "configuration": configuration,
        "guard_results": guards,
        "test_result": {
            "enforcement": "PASS" if passed else "FAIL",
            "label": "request-path guards",
            "suite": "NOT_RUN",
        },
        "execution": _execution(run),
        "signature_envelope": envelope,
        "verification": verification,
        "evidence_class": evidence,
        "signer": signer,
        "receipt_chain": (run or {}).get("receipt_chain") or [],
        "source_revisions": {
            "build_sha": _configuration(run)["build_sha"],
            "corpus_generation": retrieval.get("corpus_generation") or "UNKNOWN",
            "journey_schema": SCHEMA,
            "store_schema": LAKE_SCHEMA,
        },
        "commit_policy": dict(_COMMIT_POLICY),
        "retention": dict(_RETENTION),
        "_planning_ok": planning.get("ok") is True,
    }


def _digest(record: dict) -> str:
    payload = {key: record[key] for key in _BODY_KEYS}
    return hashlib.sha256(_canonical(payload)).hexdigest()


def _lock_path(root: str) -> str:
    return os.path.join(root, ORGAN + ".commit.lock")


def commit_lock_held(root: str) -> bool:
    """A leftover lock is not stolen and must not be treated as a lease."""
    return bool(root) and os.path.exists(_lock_path(root))


def _acquire_lock(path: str) -> bool:
    for _attempt in range(_LOCK_ATTEMPTS):
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            time.sleep(0.01)
            continue
        else:
            os.close(fd)
            return True
    return False


def _release_lock(path: str) -> None:
    try:
        os.remove(path)
    except FileNotFoundError:
        return


def _partition_files(root: str) -> list[str]:
    organ_dir = os.path.join(root, ORGAN)
    if not os.path.isdir(organ_dir):
        return []
    names = [name for name in os.listdir(organ_dir) if name.endswith(".ndjson")]
    return [os.path.join(organ_dir, name) for name in sorted(names)]


def _load_lines(root: str) -> tuple[Optional[list[dict]], Optional[str]]:
    rows: list[dict] = []
    for path in _partition_files(root):
        try:
            raw = open(path, "rb").read()
        except OSError as exc:
            return None, type(exc).__name__
        for line in raw.splitlines():
            if not line.strip():
                continue
            try:
                env = json.loads(line.decode("utf-8"))
            except (UnicodeError, json.JSONDecodeError):
                return None, "malformed receipt line"
            if not isinstance(env, dict):
                return None, "malformed receipt line"
            rows.append(env)
    return rows, None


def _check_envelope(env: dict, prev_hash: Optional[str], prev_index: int,
                    prev_id: Optional[str]) -> Optional[str]:
    if set(env) != _ENVELOPE_KEYS:
        return "unexpected ledger envelope"
    if env.get("schema") != LAKE_SCHEMA or env.get("chain_alg") != CHAIN_HASH:
        return "unexpected ledger schema"
    if env.get("organ") != ORGAN:
        return "unexpected organ"
    if env.get("energy") != {"label": "UNAVAILABLE"}:
        return "energy is not an unavailable label"
    receipt = env.get("receipt")
    if not isinstance(receipt, dict) or set(receipt) != set(_BODY_KEYS) | {"record_sha256"}:
        return "unexpected receipt fields"
    if receipt.get("schema") != SCHEMA:
        return "unexpected receipt schema"
    expect = _digest(receipt)
    stored = str(receipt.get("record_sha256") or "")
    if not _HEX64.fullmatch(stored) or stored != expect:
        return "record digest mismatch"
    rid = env.get("receipt_id")
    if rid != receipt.get("id"):
        return "receipt id mismatch"
    raw_request = receipt.get("request_id")
    if raw_request is not None and not isinstance(raw_request, str):
        return "request_id is not admitted"
    recomputed = idempotency_key(
        str(receipt.get("tenant_sha256") or ""),
        str(receipt.get("purpose") or ""),
        str(receipt.get("query_sha256") or ""),
        request_component(raw_request if isinstance(raw_request, str) else None),
    )
    if rid != recomputed:
        return "idempotency key mismatch"
    if receipt.get("parent_receipt_id") != prev_id:
        return "missing or unexpected parent"
    chain_index = env.get("chain_index")
    if chain_index != prev_index + 1:
        return "chain index is out of order"
    if env.get("prev_hash") != prev_hash:
        return "parent hash mismatch"
    chain_hash = canonical_hash({
        "prev_hash": prev_hash,
        "receipt_id": rid,
        "organ": ORGAN,
        "ts": env.get("ts"),
        "chain_index": chain_index,
    })
    if env.get("chain_hash") != chain_hash:
        return "ledger chain hash mismatch"
    return None


def _check_receipt_body(receipt: dict) -> Optional[str]:
    if receipt.get("purpose") not in {"chat", "code", "research"}:
        return "purpose is not admitted"
    query_sha = receipt.get("query_sha256")
    tenant_sha = receipt.get("tenant_sha256")
    if not isinstance(query_sha, str) or not _HEX64.fullmatch(query_sha):
        return "query digest is absent"
    if not isinstance(tenant_sha, str) or not _HEX64.fullmatch(tenant_sha):
        return "tenant scope is absent"
    envelope = receipt.get("signature_envelope")
    verification = receipt.get("verification")
    if not isinstance(envelope, dict) or "signed" not in envelope:
        return "signature envelope is absent"
    if not isinstance(verification, dict):
        return "verification state is absent"
    signed = envelope.get("signed") is True
    evidence = "DECLARED" if signed else "SIMULATED"
    signer = "HOST" if signed else "SIMULATED"
    if receipt.get("evidence_class") != evidence or receipt.get("signer") != signer:
        return "evidence class does not match the signature flag"
    if (verification.get("evidence_class") != evidence
            or verification.get("signer") != signer):
        return "verification state does not match the signature flag"
    try:
        import a11oy_code_engine as engine
        verdict = engine.verify_run({
            "receipt_chain": receipt.get("receipt_chain") or [],
            "signed_receipt": envelope,
        })
    except Exception as exc:
        return type(exc).__name__
    if verdict.get("chain_intact") is not True:
        return "chain mismatch"
    if verification.get("chain_intact") is not True:
        return "stored chain verification does not match"
    if verification.get("signature_valid") is not False or verification.get("verified") is not False:
        return "signature was not checked by a host verifier"
    if verification.get("signature_check") != "host verifier not supplied":
        return "signature check is not recorded"
    planning = receipt.get("planning") or {}
    if planning.get("execution_mode") != "PLAN_ONLY" or planning.get("effectors") != 0:
        return "planning was not plan-only"
    if planning.get("authorized") is not False or planning.get("writes") != 0:
        return "planning was not plan-only"
    if planning.get("decision") != "READY_TO_ORCHESTRATE":
        return "planning was not accepted"
    return None


def verify_ledger(root: str) -> dict:
    """Fail closed on a corrupt, reordered, or partially written ledger."""
    if not root:
        return {"ok": False, "status": "UNAVAILABLE", "reason": "receipt log is not configured"}
    if not os.path.isdir(root):
        return {"ok": False, "status": "UNAVAILABLE", "reason": "receipt log is absent"}
    rows, reason = _load_lines(root)
    if reason:
        return {"ok": False, "status": "BLOCKED", "reason": reason}
    if not rows:
        return {"ok": False, "status": "UNAVAILABLE", "reason": "empty receipt log"}
    prev_hash = None
    prev_id = None
    checked = []
    seen = set()
    request_ids: dict[str, str] = {}
    for index, env in enumerate(rows):
        reason = _check_envelope(env, prev_hash, index, prev_id)
        if reason:
            return {"ok": False, "status": "BLOCKED", "reason": reason}
        receipt = env["receipt"]
        reason = _check_receipt_body(receipt)
        if reason:
            return {"ok": False, "status": "BLOCKED", "reason": reason}
        rid = env["receipt_id"]
        if rid in seen:
            return {"ok": False, "status": "BLOCKED", "reason": "duplicate receipt id stored"}
        seen.add(rid)
        request_id = receipt.get("request_id")
        if isinstance(request_id, str) and request_id:
            prior = request_ids.get(request_id)
            if prior is not None and prior != rid:
                return {"ok": False, "status": "BLOCKED", "reason": "request_id conflict"}
            request_ids[request_id] = rid
        prev_hash = env["chain_hash"]
        prev_id = rid
        checked.append({
            "record_sha256": receipt["record_sha256"],
            "evidence_class": receipt["evidence_class"],
            "signer": receipt["signer"],
            "query_sha256": receipt["query_sha256"],
            "purpose": receipt["purpose"],
            "chain_intact": True,
            "signature_valid": receipt["verification"].get("signature_valid") is True,
            "receipt_id": rid,
            "chain_index": env["chain_index"],
            "chain_hash": env["chain_hash"],
            "graph_digest": receipt.get("graph_digest"),
            "backend": (receipt.get("retrieval") or {}).get("backend"),
            "request_id": request_id,
        })
    return {"ok": True, "status": "CHECKED", "count": len(checked), "receipts": checked}


def verify_acknowledgement(root: str, ack: dict) -> dict:
    """An acknowledgement matches one committed record. It does not create one."""
    verdict = verify_ledger(root)
    if verdict.get("ok") is not True:
        return {"ok": False, "acknowledged": False, "reason": verdict.get("reason")}
    if not isinstance(ack, dict):
        return {"ok": False, "acknowledged": False, "reason": "acknowledgement is absent"}
    for receipt in verdict["receipts"]:
        if receipt["receipt_id"] != ack.get("receipt_id"):
            continue
        if (receipt["chain_index"] != ack.get("chain_index")
                or receipt["chain_hash"] != ack.get("chain_head")):
            return {
                "ok": False,
                "acknowledged": False,
                "reason": "acknowledgement does not match the committed chain",
            }
        return {"ok": True, "acknowledged": True, "duplicate": True,
                "chain_index": receipt["chain_index"], "chain_head": receipt["chain_hash"]}
    return {"ok": False, "acknowledged": False,
            "reason": "acknowledgement is not a committed record"}


def commit_record(root: str, record: dict) -> dict:
    """Append one record under a commit lock. One append attempt. No lease."""
    evidence = record.get("evidence_class")
    signer = record.get("signer")
    if not root:
        return {
            "persisted": False,
            "restart_verifiable": False,
            "duplicate": False,
            "evidence_class": evidence,
            "signer": signer,
            "reason": "receipt log is not configured",
            "store": STORE,
            "state": "REJECTED",
        }
    if record.get("_planning_ok") is not True or record.get("test_result", {}).get("enforcement") != "PASS":
        return {
            "persisted": False,
            "restart_verifiable": False,
            "duplicate": False,
            "evidence_class": evidence,
            "signer": signer,
            "reason": "guards did not pass",
            "store": STORE,
            "state": "REJECTED",
        }
    try:
        os.makedirs(root, exist_ok=True)
    except OSError as exc:
        return {
            "persisted": False, "restart_verifiable": False, "duplicate": False,
            "evidence_class": evidence, "signer": signer,
            "reason": type(exc).__name__, "store": STORE, "state": "REJECTED",
        }
    lock = _lock_path(root)
    if not _acquire_lock(lock):
        return {
            "persisted": False,
            "restart_verifiable": False,
            "duplicate": False,
            "evidence_class": evidence,
            "signer": signer,
            "reason": "commit lock held",
            "store": STORE,
            "state": "REJECTED",
            "attempts": _LOCK_ATTEMPTS,
        }
    try:
        rows, reason = _load_lines(root)
        if reason:
            return {
                "persisted": False,
                "restart_verifiable": False,
                "duplicate": False,
                "evidence_class": evidence,
                "signer": signer,
                "reason": reason,
                "store": STORE,
                "state": "REJECTED",
            }
        rows = rows or []
        if rows:
            verdict = verify_ledger(root)
            if verdict.get("ok") is not True:
                return {
                    "persisted": False, "restart_verifiable": False, "duplicate": False,
                    "evidence_class": evidence, "signer": signer,
                    "reason": verdict.get("reason"), "store": STORE, "state": "REJECTED",
                }
            for existing in verdict["receipts"]:
                if existing["receipt_id"] == record.get("id"):
                    return {
                        "persisted": True,
                        "restart_verifiable": True,
                        "duplicate": True,
                        "evidence_class": evidence,
                        "signer": signer,
                        "record_sha256": existing["record_sha256"],
                        "receipt_id": existing["receipt_id"],
                        "chain_index": existing["chain_index"],
                        "chain_head": existing["chain_hash"],
                        "store": STORE,
                        "state": "DUPLICATE",
                        "attempts": _APPEND_ATTEMPTS,
                    }
                if (isinstance(existing.get("request_id"), str)
                        and existing.get("request_id")
                        and existing.get("request_id") == record.get("request_id")
                        and existing["receipt_id"] != record.get("id")):
                    return {
                        "persisted": False, "restart_verifiable": False, "duplicate": False,
                        "evidence_class": evidence, "signer": signer,
                        "reason": "request_id conflict", "store": STORE, "state": "REJECTED",
                    }
            parent = verdict["receipts"][-1]["receipt_id"]
        else:
            parent = None
        stored = {key: record[key] for key in _BODY_KEYS}
        stored["parent_receipt_id"] = parent
        stored["record_sha256"] = _digest(stored)
        ledger = ReceiptLedger(root=root)
        try:
            ack = ledger.append(stored)
        except (OSError, TypeError, ValueError) as exc:
            return {
                "persisted": False, "restart_verifiable": False, "duplicate": False,
                "evidence_class": evidence, "signer": signer,
                "reason": type(exc).__name__, "store": STORE, "state": "REJECTED",
                "attempts": _APPEND_ATTEMPTS,
            }
        return {
            "persisted": bool(ack.get("accepted") or ack.get("duplicate")),
            "restart_verifiable": bool(ack.get("accepted") or ack.get("duplicate")),
            "duplicate": bool(ack.get("duplicate")),
            "evidence_class": evidence,
            "signer": signer,
            "record_sha256": stored["record_sha256"],
            "receipt_id": ack.get("receipt_id"),
            "chain_index": ack.get("chain_index"),
            "chain_head": ack.get("chain_head"),
            "store": STORE,
            "organ": ORGAN,
            "state": "DUPLICATE" if ack.get("duplicate") else "COMMITTED",
            "attempts": _APPEND_ATTEMPTS,
        }
    finally:
        _release_lock(lock)


def replay_if_committed(root: str, query: str, purpose: str, tenant: str,
                        request_id: Optional[str],
                        expected_semantics: Optional[str] = None) -> Optional[dict]:
    """Return the committed witness without running retrieval again."""
    if not root or not os.path.isdir(root):
        return None
    verdict = verify_ledger(root)
    if verdict.get("ok") is not True:
        return None
    component = request_component(request_id)
    key = idempotency_key(
        tenant_scope(tenant),
        purpose,
        hashlib.sha256(query.encode("utf-8")).hexdigest(),
        component,
    )
    match = None
    for receipt in verdict["receipts"]:
        if receipt["receipt_id"] == key:
            match = receipt
            break
    if match is None:
        if request_id:
            for receipt in verdict["receipts"]:
                if receipt.get("request_id") == request_id:
                    return {"conflict": True, "reason": "request_id conflict"}
        return None
    rows, reason = _load_lines(root)
    if reason or not rows:
        return None
    stored = None
    for env in rows:
        if env.get("receipt_id") == key and isinstance(env.get("receipt"), dict):
            stored = env["receipt"]
            break
    if stored is None:
        return None
    action = (stored.get("configuration") or {}).get("action_identity") or {}
    if not isinstance(action, dict):
        action = {}
    if expected_semantics is not None and action.get("semantics_digest") != expected_semantics:
        return {"conflict": True, "reason": "semantics conflict"}
    restored = restore_result(stored)
    retrieval = stored.get("retrieval") or _unknown_retrieval()
    journey = {
        "retrieval": retrieval,
        "planning": stored.get("planning") or {},
        "execution": stored.get("execution") or {},
        "signature": {
            "signed": (stored.get("signature_envelope") or {}).get("signed") is True,
            "evidence_class": stored.get("evidence_class"),
            "signer": stored.get("signer"),
            "signature_valid": (stored.get("verification") or {}).get("signature_valid") is True,
            "chain_intact": (stored.get("verification") or {}).get("chain_intact") is True,
        },
        "durability": {
            "store": STORE,
            "persisted": True,
            "restart_verifiable": True,
            "duplicate": True,
            "state": "DUPLICATE",
        },
        "guards": stored.get("guard_results") or [],
    }
    restart = {
        "persisted": True,
        "restart_verifiable": True,
        "duplicate": True,
        "evidence_class": stored.get("evidence_class"),
        "signer": stored.get("signer"),
        "record_sha256": match["record_sha256"],
        "store": STORE,
        "state": "DUPLICATE",
        "receipt_id": key,
        "chain_index": match["chain_index"],
        "chain_head": match["chain_hash"],
    }
    return {
        "duplicate": True,
        "restart_receipt": restart,
        "journey": journey,
        "run": restored["run"],
        "result_availability": restored["result_availability"],
        "historical_execution": restored["historical_execution"],
        "logical_id": action.get("logical_id") or key,
        "step_id": action.get("step_id"),
        "run_id": action.get("run_id"),
    }


def finish(root: str, query: str, purpose: str, tenant: str, request_id: Optional[str],
           run: dict, measure: Any = None, action: Optional[dict] = None) -> dict:
    """Build the witness and, when a root is configured, commit it."""
    record = build_record(query, purpose, tenant, request_id, run, measure, action)
    planning_ok = record.pop("_planning_ok")
    record_for_commit = dict(record)
    record_for_commit["_planning_ok"] = planning_ok
    ack = commit_record(root, record_for_commit)
    retrieval = record["retrieval"]
    journey = {
        "retrieval": retrieval,
        "planning": record["planning"],
        "execution": record["execution"],
        "signature": {
            "signed": record["signature_envelope"].get("signed") is True,
            "evidence_class": record["evidence_class"],
            "signer": record["signer"],
            "signature_valid": record["verification"].get("signature_valid") is True,
            "chain_intact": record["verification"].get("chain_intact") is True,
        },
        "durability": {
            "store": STORE,
            "persisted": ack.get("persisted"),
            "restart_verifiable": ack.get("restart_verifiable"),
            "duplicate": ack.get("duplicate"),
            "state": ack.get("state"),
            "reason": ack.get("reason"),
        },
        "guards": record["guard_results"],
    }
    restart = {
        "persisted": ack.get("persisted"),
        "restart_verifiable": ack.get("restart_verifiable"),
        "duplicate": ack.get("duplicate") is True,
        "evidence_class": record["evidence_class"],
        "signer": record["signer"],
        "record_sha256": ack.get("record_sha256"),
        "chain_final_hash": (run or {}).get("chain_final_hash"),
        "store": STORE,
        "state": ack.get("state"),
        "receipt_id": ack.get("receipt_id"),
        "chain_index": ack.get("chain_index"),
        "chain_head": ack.get("chain_head"),
    }
    if ack.get("reason"):
        restart["reason"] = ack["reason"]
    result_record = record["configuration"].get("result_record") or {}
    return {
        "restart_receipt": restart,
        "journey": journey,
        "result_availability": result_record.get("availability") or "RESULT_UNAVAILABLE",
        "historical_execution": result_record.get("historical_execution") or "UNKNOWN",
    }
