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
import secrets
import time
from pathlib import Path
from typing import Any, Optional

from routers.governed_graph_operations import (
    EXECUTION_MODE,
    GraphContractError,
    analyse_graph,
)
from szl_action_identity import (
    canonical as identity_canonical,
    digest as identity_digest,
    identity as action_identity,
    logical_digest,
    require_id,
)
from szl_lake_store import (
    CHAIN_HASH,
    SCHEMA as LAKE_SCHEMA,
    ReceiptLedger,
    canonical_hash,
)

SCHEMA = "szl.a11oy.code-runloop-receipt/v2"
SCHEMA_V3 = "szl.a11oy.code-runloop-receipt/v3"
RESULT_SCHEMA = "szl.code-runstep-result/v1"
PLAN_ADMISSION_SCHEMA = "szl.code-runloop-plan-admission/v1"
DESTINATION = "governed-turn"
DESTINATION_CONTRACT = "governed-turn/v1"
ORGAN = "code-runloop"
STORE = "szl_lake_store.ReceiptLedger"
_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{1,80}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_LOCK_ATTEMPTS = 25
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
_V3_EXTRA = (
    "logical_action_id",
    "plan_revision",
    "result_schema",
    "result_sha256",
    "result_state",
    "run_id",
    "semantics_digest",
    "step_id",
)
_BODY_KEYS_V3 = tuple(sorted(set(_BODY_KEYS) | set(_V3_EXTRA)))
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


def _keys_for(record: dict) -> tuple:
    if record.get("schema") == SCHEMA_V3:
        return _BODY_KEYS_V3
    return _BODY_KEYS


def plan_revision(mode: str, steps: list[dict]) -> str:
    """Stable revision of the planned steps. It does not include run_id."""
    payload = {
        "schema": "szl.code-plan-revision/v1",
        "mode": mode,
        "steps": [
            {
                "operation": step["mode"],
                "prompt": step["prompt"],
                "sandbox": bool(step["sandbox"]),
                "state_changing": bool(step["state_changing"]),
                "step_id": step["step_id"],
            }
            for step in steps
        ],
    }
    return "rev-" + identity_digest(payload)[:32]


def _option_text(value: Any, limit: int = 128) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValueError("execution option must be a string")
    text = value.strip()
    if len(text) > limit or any(ord(ch) < 32 for ch in text):
        raise ValueError("execution option is not admitted")
    return text


def _plans_dir(root: str) -> Path:
    return Path(root) / "code-runloop-plans"


def _results_dir(root: str) -> Path:
    return Path(root) / "code-runloop-results"


def _contained(directory: Path, name: str) -> Path:
    base = directory.resolve()
    path = (base / name).resolve()
    if os.path.normcase(str(path.parent)) != os.path.normcase(str(base)):
        raise ValueError("path escaped the receipt root")
    if path.is_symlink():
        raise ValueError("symlink result is not admitted")
    return path


def persist_plan_admission(root: str, tenant: str, plan_body: dict) -> bool:
    """Bind a server-issued run to this tenant before any step can use it."""
    if not root or not isinstance(plan_body, dict):
        return False
    run_id = require_id(plan_body.get("run_id"))
    revision = require_id(plan_body.get("plan_revision"))
    scope = tenant_scope(tenant)
    steps_in = plan_body.get("plan")
    if not isinstance(steps_in, list) or not steps_in:
        raise ValueError("plan has no steps")
    steps: dict[str, dict] = {}
    for step in steps_in:
        if not isinstance(step, dict):
            raise ValueError("plan step is not an object")
        step_id = require_id(step.get("step_id"))
        operation = require_id(step.get("mode"))
        prompt = step.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("plan prompt is not admitted")
        logical_id = logical_digest(scope, run_id, step_id)
        steps[step_id] = {
            "logical_action_id": logical_id,
            "operation": operation,
            "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "sandbox": bool(step.get("sandbox")),
            "state_changing": bool(step.get("state_changing")),
        }
    record = {
        "schema": PLAN_ADMISSION_SCHEMA,
        "run_id": run_id,
        "tenant_sha256": scope,
        "plan_revision": revision,
        "steps": steps,
    }
    encoded = identity_canonical(record)
    os.makedirs(root, exist_ok=True)
    directory = _plans_dir(root)
    directory.mkdir(parents=True, exist_ok=True)
    target = _contained(directory, run_id + ".json")
    if target.exists():
        return False
    temporary = _contained(directory, run_id + ".json.tmp")
    temporary.write_bytes(encoded)
    os.replace(temporary, target)
    return True


def _load_plan(root: str, run_id: str) -> Optional[dict]:
    if not root or not os.path.isdir(root):
        return None
    path = _contained(_plans_dir(root), require_id(run_id) + ".json")
    if not path.is_file():
        return None
    value = json.loads(path.read_text(encoding="ascii"))
    if not isinstance(value, dict) or value.get("schema") != PLAN_ADMISSION_SCHEMA:
        return None
    return value


def admit_planned_step(
    root: str,
    tenant: str,
    *,
    run_id: Any,
    step_id: Any,
    plan_revision_value: Any,
    query: str,
    purpose: str,
    sandbox: bool,
    state_changing: bool,
    profile: Any,
    model: Any,
) -> tuple[Optional[dict], Optional[dict]]:
    """Return (action, refusal). Refusal is not an engine result.

    Omitted run and step stay on the legacy query key. A presented identity
    must match a plan this server issued for the current tenant.
    """
    if run_id is None and step_id is None and plan_revision_value is None:
        return None, None
    try:
        admitted_run = require_id(run_id)
        admitted_step = require_id(step_id)
        admitted_revision = require_id(plan_revision_value)
        profile_text = _option_text(profile)
        model_text = _option_text(model)
    except ValueError:
        return None, {"status": 400, "error": "run identity is not admitted"}
    plan = _load_plan(root, admitted_run) if root else None
    if plan is None or plan.get("tenant_sha256") != tenant_scope(tenant):
        return None, {"status": 409, "error": "run is not admitted"}
    recorded = (plan.get("steps") or {}).get(admitted_step)
    if not isinstance(recorded, dict):
        return None, {"status": 409, "error": "step is not admitted"}
    prompt_sha = hashlib.sha256(query.encode("utf-8")).hexdigest()
    bound_ok = (
        plan.get("plan_revision") == admitted_revision
        and recorded.get("operation") == purpose
        and recorded.get("prompt_sha256") == prompt_sha
        and recorded.get("sandbox") is sandbox
        and recorded.get("state_changing") is state_changing
    )
    if not bound_ok:
        return None, {"status": 409, "error": "semantics conflict"}
    scope = tenant_scope(tenant)
    execution_options = {
        "destination_contract": DESTINATION_CONTRACT,
        "model": model_text,
        "profile": profile_text,
        "sandbox": sandbox,
        "state_changing": state_changing,
    }
    try:
        bound = action_identity(
            tenant_id=scope,
            run_id=admitted_run,
            step_id=admitted_step,
            plan_revision=admitted_revision,
            operation=purpose,
            destination=DESTINATION,
            arguments={"prompt": query},
            execution_options=execution_options,
        )
    except ValueError:
        return None, {"status": 400, "error": "run identity is not admitted"}
    if bound.logical_id != recorded.get("logical_action_id"):
        return None, {"status": 409, "error": "run is not admitted"}
    return {
        "run_id": admitted_run,
        "step_id": admitted_step,
        "plan_revision": admitted_revision,
        "logical_id": bound.logical_id,
        "semantics_digest": bound.semantics_digest,
        "comparison": "REPLAY_CANDIDATE_REQUIRES_STATE_RIGHTS_AND_RESULT_CHECKS",
    }, None


def new_attempt_id() -> str:
    return "attempt-" + secrets.token_hex(8)


def note_attempt(root: str, logical_id: str, semantics: str, attempt_id: str,
                 outcome: str) -> None:
    """Append one attempt outside the receipt chain. Failure is not authority."""
    if not root:
        return
    try:
        os.makedirs(root, exist_ok=True)
        line = identity_canonical({
            "schema": "szl.code-runloop-attempt/v1",
            "attempt_id": attempt_id,
            "logical_action_id": logical_id,
            "outcome": outcome,
            "semantics_digest": semantics,
        })
        path = Path(root) / "code-runloop-attempts.ndjson"
        with path.open("ab") as handle:
            handle.write(line + b"\n")
    except (OSError, ValueError):
        return


def project_result(run: dict) -> dict:
    """JSON-safe projection. Floats are omitted rather than claimed exact."""
    inference = run.get("inference") if isinstance(run.get("inference"), dict) else {}
    code = run.get("code") if isinstance(run.get("code"), dict) else None
    sandbox = run.get("sandbox") if isinstance(run.get("sandbox"), dict) else None
    gate = run.get("gate") if isinstance(run.get("gate"), dict) else {}
    reasons = gate.get("reasons") if isinstance(gate.get("reasons"), list) else []
    chain = run.get("receipt_chain") if isinstance(run.get("receipt_chain"), list) else []
    hops = []
    for hop in chain[:32]:
        if not isinstance(hop, dict):
            continue
        seq = hop.get("seq")
        kind = hop.get("kind")
        digest = hop.get("hash")
        if type(seq) is not int or not isinstance(kind, str) or not isinstance(digest, str):
            continue
        hops.append({"hash": digest, "kind": kind, "seq": seq})
    signed = run.get("signed_receipt") if isinstance(run.get("signed_receipt"), dict) else {}
    code_out = None
    if isinstance(code, dict) and isinstance(code.get("code"), str):
        code_out = {
            "code": code.get("code"),
            "description": code.get("description") if isinstance(code.get("description"), str) else "",
        }
    sandbox_out = None
    if isinstance(sandbox, dict):
        sandbox_out = {
            "blocked": sandbox.get("blocked") is True,
            "isolation": sandbox.get("isolation") if isinstance(sandbox.get("isolation"), str) else "",
            "stderr": sandbox.get("stderr") if isinstance(sandbox.get("stderr"), str) else "",
            "stdout": sandbox.get("stdout") if isinstance(sandbox.get("stdout"), str) else "",
        }
    return {
        "schema": RESULT_SCHEMA,
        "answer": run.get("answer") if isinstance(run.get("answer"), str) else None,
        "code": code_out,
        "decision": run.get("decision") if isinstance(run.get("decision"), str) else "UNKNOWN",
        "executed": run.get("executed") is True,
        "execution_status": (
            run.get("execution_status")
            if isinstance(run.get("execution_status"), str) else "UNKNOWN"
        ),
        "gate": {
            "allow": gate.get("allow") is True,
            "reasons": [item for item in reasons if isinstance(item, str)][:20],
            "severity": gate.get("severity") if isinstance(gate.get("severity"), str) else "UNKNOWN",
        },
        "honesty": run.get("honesty") if isinstance(run.get("honesty"), str) else "",
        "inference_mode": inference.get("mode") if isinstance(inference.get("mode"), str) else "UNKNOWN",
        "receipt_chain": hops,
        "sandbox": sandbox_out,
        "signed_receipt": {"signed": signed.get("signed") is True},
        "summary": run.get("summary") if isinstance(run.get("summary"), str) else "",
    }


def bind_result(run: dict) -> dict:
    try:
        projection = project_result(run)
        encoded = identity_canonical(projection)
        return {
            "bytes": encoded,
            "projection": projection,
            "schema": RESULT_SCHEMA,
            "sha256": hashlib.sha256(encoded).hexdigest(),
            "state": "AVAILABLE",
        }
    except ValueError:
        marker = {"schema": RESULT_SCHEMA, "state": "RESULT_UNAVAILABLE"}
        encoded = identity_canonical(marker)
        return {
            "bytes": None,
            "projection": None,
            "schema": RESULT_SCHEMA,
            "sha256": hashlib.sha256(encoded).hexdigest(),
            "state": "RESULT_UNAVAILABLE",
        }


def _write_result_bytes(root: str, sha: str, payload: bytes) -> None:
    directory = _results_dir(root)
    directory.mkdir(parents=True, exist_ok=True)
    target = _contained(directory, sha + ".json")
    if target.exists():
        if target.read_bytes() != payload:
            raise ValueError("result digest already names different bytes")
        return
    temporary = _contained(directory, sha + ".json.tmp")
    temporary.write_bytes(payload)
    os.replace(temporary, target)


def _read_result(root: str, sha: str) -> Optional[dict]:
    if not isinstance(sha, str) or _HEX64.fullmatch(sha) is None:
        return None
    path = _contained(_results_dir(root), sha + ".json")
    if not path.is_file():
        return None
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != sha:
        return None
    value = json.loads(raw.decode("ascii"))
    if not isinstance(value, dict) or value.get("schema") != RESULT_SCHEMA:
        return None
    return value


def _historical(execution: Any) -> dict:
    status = execution.get("status") if isinstance(execution, dict) else None
    executed = execution.get("executed") is True if isinstance(execution, dict) else False
    if not isinstance(status, str) or not status:
        status = "UNKNOWN"
    return {
        "historical_execution_status": status,
        "historical_execution_succeeded": status == "SUCCEEDED" and executed,
    }


def _result_view(root: str, receipt: dict) -> dict:
    history = _historical(receipt.get("execution"))
    state = receipt.get("result_state")
    sha = receipt.get("result_sha256")
    loaded = None
    if state == "AVAILABLE":
        try:
            loaded = _read_result(root, sha)
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
            loaded = None
    available = loaded is not None
    view = {
        "schema": RESULT_SCHEMA,
        "sha256": sha if isinstance(sha, str) else None,
        "state": "AVAILABLE" if available else "RESULT_UNAVAILABLE",
    }
    view.update(history)
    return {"result": view, "run": loaded if available else None}


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
                 run: dict, measure: Any = None, action: Optional[dict] = None,
                 result_binding: Optional[dict] = None) -> dict:
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
    schema = SCHEMA_V3 if action else SCHEMA
    record_id = (
        action["logical_id"] if action else
        idempotency_key(scope, purpose, query_sha, request_component(stored_request_id))
    )
    record = {
        "schema": schema,
        "id": record_id,
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
        "configuration": _configuration(run),
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
            "journey_schema": schema,
            "store_schema": LAKE_SCHEMA,
        },
        "commit_policy": dict(_COMMIT_POLICY),
        "retention": dict(_RETENTION),
        "_planning_ok": planning.get("ok") is True,
    }
    if action is not None:
        binding = result_binding or {}
        record.update({
            "logical_action_id": action["logical_id"],
            "plan_revision": action["plan_revision"],
            "result_schema": binding.get("schema") or RESULT_SCHEMA,
            "result_sha256": binding.get("sha256"),
            "result_state": binding.get("state") or "RESULT_UNAVAILABLE",
            "run_id": action["run_id"],
            "semantics_digest": action["semantics_digest"],
            "step_id": action["step_id"],
        })
    return record


def _digest(record: dict) -> str:
    payload = {key: record[key] for key in _keys_for(record)}
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
            time.sleep(0.02)
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


def _check_v3_identity(receipt: dict, rid: Any) -> Optional[str]:
    try:
        expected = logical_digest(
            require_id(receipt.get("tenant_sha256")),
            require_id(receipt.get("run_id")),
            require_id(receipt.get("step_id")),
        )
        require_id(receipt.get("plan_revision"))
        require_id(receipt.get("purpose"))
    except ValueError:
        return "run identity is not admitted"
    if rid != expected or receipt.get("logical_action_id") != expected:
        return "idempotency key mismatch"
    semantics = receipt.get("semantics_digest")
    result_sha = receipt.get("result_sha256")
    if not isinstance(semantics, str) or _HEX64.fullmatch(semantics) is None:
        return "semantics digest is absent"
    if not isinstance(result_sha, str) or _HEX64.fullmatch(result_sha) is None:
        return "result digest is absent"
    if receipt.get("result_schema") != RESULT_SCHEMA:
        return "result schema is not admitted"
    if receipt.get("result_state") not in {"AVAILABLE", "RESULT_UNAVAILABLE"}:
        return "result state is not admitted"
    return None


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
    if not isinstance(receipt, dict):
        return "unexpected receipt fields"
    schema = receipt.get("schema")
    if schema not in {SCHEMA, SCHEMA_V3}:
        return "unexpected receipt schema"
    if set(receipt) != set(_keys_for(receipt)) | {"record_sha256"}:
        return "unexpected receipt fields"
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
    if schema == SCHEMA_V3:
        reason = _check_v3_identity(receipt, rid)
        if reason:
            return reason
    else:
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
            "semantics_digest": receipt.get("semantics_digest"),
            "run_id": receipt.get("run_id"),
            "step_id": receipt.get("step_id"),
            "result_sha256": receipt.get("result_sha256"),
            "result_state": receipt.get("result_state"),
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


def commit_record(root: str, record: dict, result_bytes: Optional[bytes] = None) -> dict:
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
                    if (record.get("schema") == SCHEMA_V3
                            and existing.get("semantics_digest") != record.get("semantics_digest")):
                        return {
                            "persisted": False,
                            "restart_verifiable": False,
                            "duplicate": False,
                            "evidence_class": evidence,
                            "signer": signer,
                            "reason": "semantics conflict",
                            "store": STORE,
                            "state": "REJECTED",
                        }
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
        stored = {key: record[key] for key in _keys_for(record)}
        stored["parent_receipt_id"] = parent
        stored["record_sha256"] = _digest(stored)
        if result_bytes is not None and stored.get("result_state") == "AVAILABLE":
            try:
                _write_result_bytes(root, stored["result_sha256"], result_bytes)
            except (OSError, ValueError) as exc:
                return {
                    "persisted": False, "restart_verifiable": False, "duplicate": False,
                    "evidence_class": evidence, "signer": signer,
                    "reason": type(exc).__name__, "store": STORE,
                    "state": "OUTCOME_UNCERTAIN",
                }
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
                        request_id: Optional[str]) -> Optional[dict]:
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
    return {"duplicate": True, "restart_receipt": restart, "journey": journey, "run": None}


def _stored_receipt(root: str, receipt_id: str) -> Optional[dict]:
    rows, reason = _load_lines(root)
    if reason or not rows:
        return None
    for env in rows:
        if env.get("receipt_id") == receipt_id and isinstance(env.get("receipt"), dict):
            return env["receipt"]
    return None


def replay_planned(root: str, tenant: str, action: dict) -> Optional[dict]:
    """Replay one admitted step. A digest match is not permission to dispatch."""
    if not root or not os.path.isdir(root) or not action:
        return None
    verdict = verify_ledger(root)
    if verdict.get("ok") is not True:
        if verdict.get("status") == "BLOCKED":
            return {"blocked": True, "reason": verdict.get("reason") or "receipt log is blocked"}
        return None
    match = None
    for receipt in verdict["receipts"]:
        if receipt["receipt_id"] == action["logical_id"]:
            match = receipt
            break
    if match is None:
        return None
    if match.get("semantics_digest") != action["semantics_digest"]:
        return {"conflict": True, "reason": "semantics conflict"}
    stored = _stored_receipt(root, action["logical_id"])
    if stored is None or stored.get("tenant_sha256") != tenant_scope(tenant):
        return {"blocked": True, "reason": "committed result is not readable"}
    viewed = _result_view(root, stored)
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
        "receipt_id": action["logical_id"],
        "chain_index": match["chain_index"],
        "chain_head": match["chain_hash"],
    }
    return {
        "duplicate": True,
        "restart_receipt": restart,
        "journey": journey,
        "run": viewed["run"],
        "result": viewed["result"],
        "identity": {
            "run_id": action["run_id"],
            "step_id": action["step_id"],
            "plan_revision": action["plan_revision"],
            "logical_action_id": action["logical_id"],
            "semantics_digest": action["semantics_digest"],
            "comparison": action["comparison"],
        },
    }


def restore_committed_result(root: str, tenant: str, run_id: str, step_id: str) -> dict:
    """Read one committed step in this process. It does not call the engine."""
    try:
        logical_id = logical_digest(tenant_scope(tenant), require_id(run_id), require_id(step_id))
    except ValueError:
        return {"ok": False, "result": {"state": "RESULT_UNAVAILABLE"}, "run": None}
    verdict = verify_ledger(root)
    if verdict.get("ok") is not True:
        return {
            "ok": False,
            "result": {"state": "RESULT_UNAVAILABLE", "reason": verdict.get("reason")},
            "run": None,
        }
    if not any(item["receipt_id"] == logical_id for item in verdict["receipts"]):
        return {"ok": False, "result": {"state": "RESULT_UNAVAILABLE"}, "run": None}
    stored = _stored_receipt(root, logical_id)
    if stored is None or stored.get("tenant_sha256") != tenant_scope(tenant):
        return {"ok": False, "result": {"state": "RESULT_UNAVAILABLE"}, "run": None}
    viewed = _result_view(root, stored)
    return {"ok": viewed["result"]["state"] == "AVAILABLE", **viewed}


def finish(root: str, query: str, purpose: str, tenant: str, request_id: Optional[str],
           run: dict, measure: Any = None, action: Optional[dict] = None) -> dict:
    """Build the witness and, when a root is configured, commit it."""
    binding = bind_result(run) if action is not None else None
    record = build_record(
        query, purpose, tenant, request_id, run, measure, action, binding)
    planning_ok = record.pop("_planning_ok")
    record_for_commit = dict(record)
    record_for_commit["_planning_ok"] = planning_ok
    ack = commit_record(
        root,
        record_for_commit,
        None if binding is None else binding.get("bytes"),
    )
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
    witnessed = {"restart_receipt": restart, "journey": journey}
    if binding is not None:
        result = {
            "schema": binding["schema"],
            "sha256": binding["sha256"],
            "state": binding["state"] if ack.get("persisted") else "RESULT_UNAVAILABLE",
        }
        result.update(_historical(record.get("execution")))
        witnessed["result"] = result
    return witnessed
