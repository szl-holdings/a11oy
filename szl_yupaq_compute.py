# SPDX-License-Identifier: Apache-2.0
"""Yupaq governed computation plane.

Yupaq ("the one who counts") binds the existing A11oy numerical, quant,
formal, evidence, and trust organs behind one strict job contract.  It is an
orchestrator, not a new calculator: every operation delegates to an existing
versioned implementation and retains that implementation's honesty label.

The public contract deliberately accepts no source code, expressions, paths,
URLs, packages, shell arguments, provider credentials, or arbitrary function
names.  A completed job produces a canonical result digest, an optional DSSE
envelope, a Lake chain record, and OpenTelemetry-shaped timing spans.  Missing
engines remain UNAVAILABLE and never receive synthetic proof or trust uplift.
"""

from __future__ import annotations

import asyncio
import copy
import hashlib
import hmac
import json
import math
import os
import re
import threading
import time
from collections import OrderedDict
from contextlib import nullcontext
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from fastapi import Request  # noqa: F401
    from fastapi.responses import JSONResponse  # noqa: F401
except Exception:  # pragma: no cover - register() is not called without FastAPI
    Request = JSONResponse = Any  # type: ignore


ROOT = Path(__file__).resolve().parent
JOB_SCHEMA = "szl.compute-job/v1"
RESULT_SCHEMA = "szl.compute-result/v1"
RECEIPT_SCHEMA = "szl.compute-receipt/v1"
PAYLOAD_TYPE = "application/vnd.szl.compute-receipt+json"
MAX_BODY_BYTES = 128 * 1024
MAX_OUTPUT_BYTES = 256 * 1024
MAX_RUNTIME_MS = 8_000
MAX_JOBS_IN_MEMORY = 256
MAX_PROCESS_BINDINGS = 4_096
ZERO_UPLIFT = {"proof_uplift": 0, "trust_uplift": 0}
JOB_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,95}$")

OPERATIONS = (
    "formula.org_lambda.weighted_geomean",
    "quant.sample.pipeline",
    "quantum.qubo.exact_baseline",
    "numerics.external.run",
    "numerics.external.compare",
    "proof.lean.inventory",
    "formula.admission.inventory",
    "brain.corpus.inventory",
    "lake.evidence.inventory",
)

_STORE: "OrderedDict[tuple[str, str], dict[str, Any]]" = OrderedDict()
_REQUEST_BINDINGS: dict[tuple[str, str], str] = {}
_STORE_LOCK = threading.RLock()


class ContractError(ValueError):
    """A compute job violates the fixed, data-only contract."""


class AuthenticationError(PermissionError):
    """A compute route has no valid configured bearer authority."""


class BodyTooLarge(ContractError):
    """A request exceeded the compute plane's fixed pre-parse body limit."""


def _authorize_request(request: Any) -> str:
    """Return a non-secret owner id for a configured compute bearer token.

    The runtime stores only the expected SHA-256 in
    ``A11OY_COMPUTE_TOKEN_SHA256``.  If it is absent, stateful compute routes
    fail closed rather than becoming an unauthenticated public executor.
    """
    expected = os.environ.get("A11OY_COMPUTE_TOKEN_SHA256", "").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise AuthenticationError("compute authority is not configured")
    authorization = (request.headers.get("authorization") or "").strip()
    if not authorization.lower().startswith("bearer "):
        raise AuthenticationError("missing compute bearer authority")
    token = authorization.split(" ", 1)[1].strip()
    observed = hashlib.sha256(token.encode("utf-8")).hexdigest()
    if not hmac.compare_digest(observed, expected):
        raise AuthenticationError("invalid compute bearer authority")
    return f"sha256:{expected[:16]}"


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def digest_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ContractError(f"{name} must be an object")
    return value


def _strict(value: Mapping[str, Any], allowed: set[str], required: set[str], name: str) -> None:
    extras = sorted(set(value) - allowed)
    missing = sorted(required - set(value))
    if extras:
        raise ContractError(f"{name} has unsupported fields: {', '.join(extras)}")
    if missing:
        raise ContractError(f"{name} is missing fields: {', '.join(missing)}")


def _finite(value: Any, name: str, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ContractError(f"{name} must be a finite number")
    result = float(value)
    if not math.isfinite(result) or not minimum <= result <= maximum:
        raise ContractError(f"{name} must be between {minimum} and {maximum}")
    return result


def _integer(value: Any, name: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ContractError(f"{name} must be an integer between {minimum} and {maximum}")
    return value


def _json_object(path: Path, name: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ContractError(f"{name} is unavailable") from exc
    if not isinstance(value, dict):
        raise ContractError(f"{name} must be a JSON object")
    return value


def _file_receipt(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def _parse_lambda_inputs(value: Mapping[str, Any]) -> dict[str, Any]:
    _strict(value, {"axes", "weights"}, {"axes", "weights"}, "inputs")
    axes = value["axes"]
    weights = value["weights"]
    if (
        not isinstance(axes, Sequence)
        or isinstance(axes, (str, bytes, bytearray))
        or not 1 <= len(axes) <= 32
    ):
        raise ContractError("inputs.axes must contain 1..32 scores")
    if (
        not isinstance(weights, Sequence)
        or isinstance(weights, (str, bytes, bytearray))
        or len(weights) != len(axes)
    ):
        raise ContractError("inputs.weights must match inputs.axes")
    parsed_axes = [_finite(item, f"inputs.axes[{index}]", 0.0, 1.0) for index, item in enumerate(axes)]
    parsed_weights = [
        _finite(item, f"inputs.weights[{index}]", 0.0, 1.0)
        for index, item in enumerate(weights)
    ]
    if sum(parsed_weights) <= 0.0:
        raise ContractError("inputs.weights must have a positive sum")
    return {"axes": parsed_axes, "weights": parsed_weights}


def _parse_inputs(operation: str, raw: Mapping[str, Any]) -> dict[str, Any]:
    value = dict(raw)
    if operation == "formula.org_lambda.weighted_geomean":
        return _parse_lambda_inputs(value)
    if operation == "quant.sample.pipeline":
        _strict(value, {"stress", "gamma", "kappa"}, {"stress", "gamma", "kappa"}, "inputs")
        if not isinstance(value["stress"], bool):
            raise ContractError("inputs.stress must be a boolean")
        return {
            "stress": value["stress"],
            "gamma": _finite(value["gamma"], "inputs.gamma", 0.0, 10.0),
            "kappa": _finite(value["kappa"], "inputs.kappa", 0.0, 10.0),
        }
    if operation == "quantum.qubo.exact_baseline":
        _strict(value, {"request"}, {"request"}, "inputs")
        return {"request": dict(_mapping(value["request"], "inputs.request"))}
    if operation == "numerics.external.run":
        _strict(value, {"engine", "request"}, {"engine", "request"}, "inputs")
        if value["engine"] not in ("octave", "matlab"):
            raise ContractError("inputs.engine must be octave or matlab")
        return {"engine": value["engine"], "request": dict(_mapping(value["request"], "inputs.request"))}
    if operation == "numerics.external.compare":
        _strict(value, {"request"}, {"request"}, "inputs")
        return {"request": dict(_mapping(value["request"], "inputs.request"))}
    if operation in {
        "proof.lean.inventory",
        "formula.admission.inventory",
        "brain.corpus.inventory",
        "lake.evidence.inventory",
    }:
        _strict(value, set(), set(), "inputs")
        return {}
    raise ContractError("unsupported operation")


def parse_job(payload: Mapping[str, Any]) -> dict[str, Any]:
    obj = _mapping(payload, "job")
    allowed = {"schema", "job_id", "operation", "inputs", "resource_budget"}
    _strict(obj, allowed, allowed, "job")
    if obj["schema"] != JOB_SCHEMA:
        raise ContractError(f"schema must be {JOB_SCHEMA}")
    job_id = obj["job_id"]
    if not isinstance(job_id, str) or not JOB_ID_RE.fullmatch(job_id):
        raise ContractError("job_id must be a bounded identifier")
    operation = obj["operation"]
    if operation not in OPERATIONS:
        raise ContractError("operation is not registered")
    budget = _mapping(obj["resource_budget"], "resource_budget")
    _strict(
        budget,
        {"max_runtime_ms", "max_output_bytes"},
        {"max_runtime_ms", "max_output_bytes"},
        "resource_budget",
    )
    return {
        "schema": JOB_SCHEMA,
        "job_id": job_id,
        "operation": operation,
        "inputs": _parse_inputs(operation, _mapping(obj["inputs"], "inputs")),
        "resource_budget": {
            "max_runtime_ms": _integer(budget["max_runtime_ms"], "resource_budget.max_runtime_ms", 1, MAX_RUNTIME_MS),
            "max_output_bytes": _integer(budget["max_output_bytes"], "resource_budget.max_output_bytes", 1_024, MAX_OUTPUT_BYTES),
        },
    }


def _lambda_job(inputs: Mapping[str, Any]) -> dict[str, Any]:
    from szl_org_lambda import weighted_geomean

    value = weighted_geomean(inputs["axes"], inputs["weights"])
    return {
        "value": value,
        "label": "ADVISORY",
        "runtime_binding": "szl_org_lambda.weighted_geomean",
        "formula_namespace": "org-lambda.weighted-geomean",
        "zero_absorption": any(item == 0.0 for item in inputs["axes"]),
        "uniqueness": "CONJECTURE_1_OPEN",
        "proof_transfer": "DENIED_NAMESPACE_SCOPED",
        **ZERO_UPLIFT,
    }


def _quant_job(inputs: Mapping[str, Any]) -> dict[str, Any]:
    from szl_gpu_quant import run_pipeline

    return run_pipeline(
        stress=inputs["stress"],
        gamma=inputs["gamma"],
        kappa=inputs["kappa"],
    )


def _quantum_job(inputs: Mapping[str, Any]) -> dict[str, Any]:
    from szl_quantum_utility import run_with_receipt

    return run_with_receipt("QUBO_EXACT_BASELINE", inputs["request"])


def _numerics_run(inputs: Mapping[str, Any], budget: Mapping[str, int]) -> dict[str, Any]:
    from szl_numerics_adapter import run_engine

    timeout = max(1, min(8, math.ceil(budget["max_runtime_ms"] / 1_000)))
    return run_engine(inputs["engine"], inputs["request"], timeout_seconds=timeout)


def _numerics_compare(inputs: Mapping[str, Any]) -> dict[str, Any]:
    from szl_numerics_adapter import compare_engines

    return compare_engines(inputs["request"])


def _lean_inventory() -> dict[str, Any]:
    path = ROOT / "proofs" / "lean-theorem-tree.json"
    source = _json_object(path, "Lean theorem inventory")
    meta = source.get("meta") or {}
    return {
        "state": "INVENTORY_ONLY_NOT_FRESH_KERNEL_EXECUTION",
        "toolchain": "Lean 4.13.0 + mathlib 4.13.0 (repository pin)",
        "commit": str(meta.get("commit") or "UNKNOWN"),
        "total_declarations": int(meta.get("total_declarations") or 0),
        "inventory": _file_receipt(path),
        "kernel_execution_this_job": False,
        **ZERO_UPLIFT,
    }


def _formula_inventory() -> dict[str, Any]:
    path = ROOT / "research" / "formula-training-admission" / "admission-manifest.json"
    source = _json_object(path, "formula admission manifest")
    summary = source.get("decision_summary") or {}
    thesis = ((source.get("source_snapshot") or {}).get("thesis") or {})
    return {
        "state": source.get("status", "UNKNOWN"),
        "admission": summary.get("training_admission", "UNKNOWN"),
        "crosswalk_rows": summary.get("formula_crosswalk_rows", 0),
        "holdout_rows": summary.get("holdout_rows", 0),
        "train_rows": summary.get("train_rows", 0),
        "resolved_status_counts": summary.get("resolved_status_counts", {}),
        "thesis_extracted_formula_count": thesis.get("extracted_formula_count", 0),
        "requested_200_status": "NOT_VERIFIED_BY_CURRENT_VERSIONED_SOURCES",
        "manifest": _file_receipt(path),
        **ZERO_UPLIFT,
    }


def _brain_inventory() -> dict[str, Any]:
    path = ROOT / "model_release" / "m1" / "corpus-ingestion-manifest.json"
    source = _json_object(path, "Brain corpus manifest")
    coverage = source.get("coverage") or {}
    return {
        "state": "RETRIEVAL_AND_EVAL_AVAILABLE_TRAINING_QUARANTINED",
        "raw_nodes": int(coverage.get("node_decisions_total") or 0),
        "distinct_artifacts": int(coverage.get("distinct_artifacts") or 0),
        "training_eligible_nodes": int(coverage.get("training_eligible_nodes") or 0),
        "missing_item_level_license_nodes": int(coverage.get("missing_item_level_license_nodes") or 0),
        "missing_source_timestamp_nodes": int(coverage.get("missing_source_timestamp_nodes") or 0),
        "manifest": _file_receipt(path),
        **ZERO_UPLIFT,
    }


def _lake_inventory() -> dict[str, Any]:
    path = ROOT / "data" / "szl-lake" / "evidence-manifest.json"
    source = _json_object(path, "SZL Lake evidence manifest")
    entries = source.get("entries") or []
    return {
        "state": "EVIDENCE_AND_RECEIPT_SUBSTRATE",
        "entry_count": len(entries),
        "proof_statuses": sorted(
            {
                str(((entry.get("artifact_receipt") or {}).get("proof_status") or "UNKNOWN"))
                for entry in entries
                if isinstance(entry, Mapping)
            }
        ),
        "manifest": _file_receipt(path),
        **ZERO_UPLIFT,
    }


def _execute(operation: str, inputs: Mapping[str, Any], budget: Mapping[str, int]) -> dict[str, Any]:
    if operation == "formula.org_lambda.weighted_geomean":
        return _lambda_job(inputs)
    if operation == "quant.sample.pipeline":
        return _quant_job(inputs)
    if operation == "quantum.qubo.exact_baseline":
        return _quantum_job(inputs)
    if operation == "numerics.external.run":
        return _numerics_run(inputs, budget)
    if operation == "numerics.external.compare":
        return _numerics_compare(inputs)
    if operation == "proof.lean.inventory":
        return _lean_inventory()
    if operation == "formula.admission.inventory":
        return _formula_inventory()
    if operation == "brain.corpus.inventory":
        return _brain_inventory()
    if operation == "lake.evidence.inventory":
        return _lake_inventory()
    raise ContractError("operation is not registered")


def _state_for(operation: str, output: Mapping[str, Any]) -> tuple[str, str]:
    if operation == "numerics.external.run" and output.get("state") == "UNAVAILABLE":
        return "UNAVAILABLE", "UNKNOWN"
    if operation == "numerics.external.compare" and output.get("comparison_state") == "UNAVAILABLE":
        return "UNAVAILABLE", "UNKNOWN"
    if operation == "quant.sample.pipeline":
        return "COMPLETED", "SAMPLE"
    if operation.startswith("proof."):
        return "COMPLETED", "INVENTORY"
    if operation.startswith(("formula.admission", "brain.", "lake.")):
        return "COMPLETED", "VERSIONED_LOCAL_EVIDENCE"
    if operation.startswith("quantum."):
        return "COMPLETED", "MEASURED_CLASSICAL_BASELINE"
    return "COMPLETED", "COMPUTED_ADVISORY"


def _span(name: str, operation: str):
    try:
        from szl_observability import span

        return span(name, operation=operation, component="yupaq-compute")
    except Exception:
        return nullcontext()


def _sign_receipt(body: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        from szl_dsse import sign_payload, verify_envelope

        envelope = sign_payload(dict(body), PAYLOAD_TYPE)
        verification = verify_envelope(envelope)
        return envelope, verification
    except Exception as exc:
        return (
            {
                "payloadType": PAYLOAD_TYPE,
                "payload": "",
                "signatures": [],
                "signed": False,
                "honesty": f"UNSIGNED: DSSE unavailable ({type(exc).__name__})",
            },
            {"verified": False, "reason": "DSSE_UNAVAILABLE"},
        )


def _append_to_lake(record: Mapping[str, Any]) -> dict[str, Any]:
    try:
        from szl_lake_store import get_default_ledger

        return get_default_ledger().append(dict(record))
    except Exception as exc:
        return {
            "accepted": False,
            "duplicate": False,
            "state": "UNAVAILABLE",
            "reason": type(exc).__name__,
        }


def _lookup_memory(owner_id: str, job_id: str) -> dict[str, Any] | None:
    key = (owner_id, job_id)
    with _STORE_LOCK:
        found = _STORE.get(key)
        if found is None:
            return None
        _STORE.move_to_end(key)
        return copy.deepcopy(found)


def _remember(owner_id: str, job: Mapping[str, Any]) -> None:
    key = (owner_id, str(job["job_id"]))
    with _STORE_LOCK:
        _STORE[key] = copy.deepcopy(dict(job))
        _STORE.move_to_end(key)
        while len(_STORE) > MAX_JOBS_IN_MEMORY:
            _STORE.popitem(last=False)


def run_job(
    payload: Mapping[str, Any],
    *,
    persist: bool = True,
    owner_id: str = "local-direct",
) -> dict[str, Any]:
    """Execute one strict, bounded job and return its result plus receipts."""

    request = parse_job(payload)
    request_sha256 = digest_json(request)
    owner = str(owner_id or "").strip()
    if not owner or len(owner) > 96:
        raise ContractError("owner_id must be a bounded non-empty identifier")
    key = (owner, request["job_id"])
    with _STORE_LOCK:
        existing = _STORE.get(key)
        if existing is not None:
            if existing["request_sha256"] != request_sha256:
                raise ContractError("job_id is already bound to a different request")
            replay = copy.deepcopy(existing)
            replay["idempotent_replay"] = True
            return replay
        prior = _REQUEST_BINDINGS.get(key)
        if prior is not None:
            if prior != request_sha256:
                raise ContractError("job_id is already bound to a different request")
            raise ContractError("job_id is already in progress or retained by the replay guard")
        if len(_REQUEST_BINDINGS) >= MAX_PROCESS_BINDINGS:
            raise ContractError("process-local replay guard is at capacity")
        _REQUEST_BINDINGS[key] = request_sha256

    try:
        started = time.perf_counter()
        with _span("yupaq.compute", request["operation"]):
            output = _execute(request["operation"], request["inputs"], request["resource_budget"])
        duration_ms = round((time.perf_counter() - started) * 1_000, 3)
    except Exception:
        with _STORE_LOCK:
            _REQUEST_BINDINGS.pop(key, None)
        raise

    output_bytes = canonical_json(output)
    if len(output_bytes) > request["resource_budget"]["max_output_bytes"]:
        state = "FAILED"
        evidence_label = "OUTPUT_BUDGET_EXCEEDED"
        output = {
            "error": "output exceeded the declared byte budget",
            "observed_output_bytes": len(output_bytes),
        }
    else:
        state, evidence_label = _state_for(request["operation"], output)
    if duration_ms > request["resource_budget"]["max_runtime_ms"]:
        state = "FAILED"
        evidence_label = "RUNTIME_BUDGET_EXCEEDED"

    result = {
        "schema": RESULT_SCHEMA,
        "job_id": request["job_id"],
        "operation": request["operation"],
        "state": state,
        "evidence_label": evidence_label,
        "request_sha256": request_sha256,
        "duration_ms": duration_ms,
        "output": output,
        "resource_budget": request["resource_budget"],
        "runtime_budget_enforcement": "POST_HOC_EXCEPT_ENGINE_SPECIFIC_TIMEOUT",
        "arbitrary_code_allowed": False,
        "network_requested": False,
        **ZERO_UPLIFT,
    }
    result_sha256 = digest_json(result)
    receipt_body = {
        "schema": RECEIPT_SCHEMA,
        "organ": "yupaq-compute",
        "owner_id": owner,
        "job_id": request["job_id"],
        "operation": request["operation"],
        "request_sha256": request_sha256,
        "result_sha256": result_sha256,
        "code_commit": os.environ.get("A11OY_GIT_COMMIT", "UNKNOWN"),
        "trace_id": os.environ.get("A11OY_TRACE_ID", "UNKNOWN"),
        "created_at": _now_iso(),
        "state": state,
        "evidence_label": evidence_label,
        "lambda_uniqueness": "CONJECTURE_1_OPEN",
        **ZERO_UPLIFT,
    }
    receipt_body["receipt_sha256"] = digest_json(receipt_body)
    dsse, dsse_verification = _sign_receipt(receipt_body)
    response = {
        "job_id": request["job_id"],
        "owner_id": owner,
        "request": request,
        "request_sha256": request_sha256,
        "result": result,
        "result_sha256": result_sha256,
        "receipt": receipt_body,
        "dsse": dsse,
        "dsse_verification": dsse_verification,
        "idempotent_replay": False,
    }
    if persist:
        response["lake"] = _append_to_lake(
            {
                "organ": "yupaq-compute",
                "action": "compute.job",
                "ts": receipt_body["created_at"],
                "job_id": request["job_id"],
                "request_sha256": request_sha256,
                "result_sha256": result_sha256,
                "receipt": receipt_body,
                "dsse": dsse,
            }
        )
    else:
        response["lake"] = {"state": "NOT_REQUESTED"}
    _remember(owner, response)
    return copy.deepcopy(response)


def get_job(job_id: str, *, owner_id: str = "local-direct") -> dict[str, Any] | None:
    if not JOB_ID_RE.fullmatch(job_id):
        raise ContractError("job_id must be a bounded identifier")
    return _lookup_memory(owner_id, job_id)


def verify_job_record(value: Mapping[str, Any]) -> dict[str, Any]:
    obj = _mapping(value, "job record")
    required = {
        "job_id", "owner_id", "request", "request_sha256", "result",
        "result_sha256", "receipt", "dsse",
    }
    missing = sorted(required - set(obj))
    if missing:
        raise ContractError(f"job record is missing fields: {', '.join(missing)}")
    request_obj = _mapping(obj["request"], "request")
    result_obj = _mapping(obj["result"], "result")
    request_match = digest_json(request_obj) == obj["request_sha256"]
    result_match = digest_json(result_obj) == obj["result_sha256"]
    receipt = _mapping(obj["receipt"], "receipt")
    receipt_material = dict(receipt)
    claimed_receipt_sha256 = receipt_material.pop("receipt_sha256", None)
    receipt_digest_match = (
        isinstance(claimed_receipt_sha256, str)
        and digest_json(receipt_material) == claimed_receipt_sha256
    )
    schema_match = (
        request_obj.get("schema") == JOB_SCHEMA
        and result_obj.get("schema") == RESULT_SCHEMA
        and receipt.get("schema") == RECEIPT_SCHEMA
    )
    semantic_links = (
        receipt.get("owner_id") == obj.get("owner_id")
        and receipt.get("job_id") == obj.get("job_id")
        == request_obj.get("job_id")
        == result_obj.get("job_id")
        and receipt.get("operation") == request_obj.get("operation")
        == result_obj.get("operation")
        and receipt.get("state") == result_obj.get("state")
        and receipt.get("evidence_label") == result_obj.get("evidence_label")
        and result_obj.get("request_sha256") == obj.get("request_sha256")
    )
    receipt_links = (
        receipt.get("request_sha256") == obj["request_sha256"]
        and receipt.get("result_sha256") == obj["result_sha256"]
    )
    try:
        from szl_dsse import verify_envelope

        dsse = verify_envelope(dict(_mapping(obj["dsse"], "dsse")))
    except Exception:
        dsse = {"verified": False, "reason": "DSSE_UNAVAILABLE"}
    payload_match = dsse.get("payload_decoded") == dict(receipt)
    return {
        "valid": bool(
            request_match
            and result_match
            and receipt_links
            and receipt_digest_match
            and schema_match
            and semantic_links
            and payload_match
            and dsse.get("verified")
        ),
        "request_hash_match": request_match,
        "result_hash_match": result_match,
        "receipt_links_match": receipt_links,
        "receipt_digest_match": receipt_digest_match,
        "schema_match": schema_match,
        "semantic_links_match": semantic_links,
        "dsse_payload_match": payload_match,
        "signature_verified": bool(dsse.get("verified")),
        "unsigned_records_are_valid": False,
    }


def capabilities() -> dict[str, Any]:
    try:
        from szl_numerics_adapter import engine_status

        numerics = engine_status()
    except Exception:
        numerics = {"mode": "UNAVAILABLE", "substrate_evidence": "UNKNOWN", **ZERO_UPLIFT}
    brain = _brain_inventory()
    formulas = _formula_inventory()
    lean = _lean_inventory()
    return {
        "schema": "szl.compute-capabilities/v1",
        "name": "Yupaq Governed Computation Plane",
        "mode": "BOUNDED_TYPED_OPERATIONS_ONLY",
        "operations": list(OPERATIONS),
        "lanes": {
            "quant": "CPU_REFERENCE_SAMPLE_ONLY",
            "quantum_utility": "CLASSICAL_BASELINE_PROPOSAL_ONLY",
            "numerics": numerics,
            "lean_mathlib": lean,
            "formula_registry": formulas,
            "brain": brain,
            "szl_lake": "BEST_EFFORT_LOCAL_KHIPU_APPEND_REDEPLOY_DURABILITY_NOT_VERIFIED",
            "ouroboros": "ORCHESTRATION_LOOP_OUTSIDE_WEIGHTS",
            "codex_workers": "PROPOSAL_BUILD_TEST_REVIEW_WITH_SIGNED_HANDOFFS",
            "invariant": "NOT_WIRED_TO_RUN_JOB",
            "lambda": "ADVISORY_CONJECTURE_1_OPEN",
        },
        "formula_accounting": {
            "requested_200": "NOT_VERIFIED",
            "thesis_extracted": formulas["thesis_extracted_formula_count"],
            "crosswalk_rows": formulas["crosswalk_rows"],
            "holdout_rows": formulas["holdout_rows"],
            "train_rows": formulas["train_rows"],
            "lean_declarations": lean["total_declarations"],
        },
        "brain_nodes": brain["raw_nodes"],
        "brain_nodes_in_gradients": brain["training_eligible_nodes"],
        "arbitrary_code_allowed": False,
        "arbitrary_urls_allowed": False,
        "model_weight_role": "MODEL_PROPOSES_TYPED_JOB; PLANE_VALIDATES_AND_EXECUTES",
        "authorization": {
            "stateful_routes_require_bearer": True,
            "configured": bool(re.fullmatch(
                r"[0-9a-f]{64}",
                os.environ.get("A11OY_COMPUTE_TOKEN_SHA256", "").strip().lower(),
            )),
            "secret_name": "A11OY_COMPUTE_TOKEN_SHA256",
            "owner_isolation": "TOKEN_SHA256_PREFIX",
            "replay_scope": "PROCESS_LOCAL_BOUNDED",
        },
        **ZERO_UPLIFT,
    }


async def _bounded_body(request: Any) -> dict[str, Any]:
    declared = request.headers.get("content-length")
    if declared is not None:
        try:
            size = int(declared)
        except ValueError as exc:
            raise ContractError("content-length must be a non-negative integer") from exc
        if size < 0 or size > MAX_BODY_BYTES:
            raise BodyTooLarge("request body exceeds 128 KiB")
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > MAX_BODY_BYTES:
            raise BodyTooLarge("request body exceeds 128 KiB")
        data.extend(chunk)
    try:
        value = json.loads(bytes(data).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractError("request body must be one JSON object") from exc
    if not isinstance(value, dict):
        raise ContractError("request body must be one JSON object")
    return value


def register(app: Any, ns: str = "a11oy") -> dict[str, Any]:
    """Register the computation plane before proxy and SPA catch-alls."""

    from fastapi import Request
    from fastapi.responses import JSONResponse

    prefix = f"/api/{ns}/v1/compute"

    @app.get(f"{prefix}/capabilities")
    async def compute_capabilities() -> JSONResponse:
        return JSONResponse(capabilities())

    @app.post(f"{prefix}/jobs")
    async def compute_jobs(request: Request) -> JSONResponse:
        try:
            owner_id = _authorize_request(request)
        except AuthenticationError as exc:
            status = 503 if "not configured" in str(exc) else 401
            return JSONResponse(
                {"state": "UNAVAILABLE" if status == 503 else "UNAUTHORIZED",
                 "error": str(exc), **ZERO_UPLIFT},
                status_code=status,
            )
        try:
            payload = await _bounded_body(request)
            record = await asyncio.to_thread(
                run_job, payload, persist=True, owner_id=owner_id)
        except BodyTooLarge as exc:
            return JSONResponse(
                {"state": "REJECTED", "error": str(exc), **ZERO_UPLIFT},
                status_code=413,
            )
        except ContractError as exc:
            return JSONResponse({"state": "REJECTED", "error": str(exc), **ZERO_UPLIFT}, status_code=422)
        except Exception as exc:
            return JSONResponse(
                {"state": "UNAVAILABLE", "reason": type(exc).__name__, **ZERO_UPLIFT},
                status_code=503,
            )
        status = 503 if record["result"]["state"] == "UNAVAILABLE" else 200
        return JSONResponse(record, status_code=status)

    @app.get(f"{prefix}/jobs/{{job_id}}")
    async def compute_job(request: Request, job_id: str) -> JSONResponse:
        try:
            owner_id = _authorize_request(request)
        except AuthenticationError as exc:
            status = 503 if "not configured" in str(exc) else 401
            return JSONResponse(
                {"state": "UNAVAILABLE" if status == 503 else "UNAUTHORIZED",
                 "error": str(exc), **ZERO_UPLIFT},
                status_code=status,
            )
        try:
            record = get_job(job_id, owner_id=owner_id)
        except ContractError as exc:
            return JSONResponse({"state": "REJECTED", "error": str(exc), **ZERO_UPLIFT}, status_code=422)
        if record is None:
            return JSONResponse({"state": "NOT_FOUND", "job_id": job_id, **ZERO_UPLIFT}, status_code=404)
        return JSONResponse(record)

    @app.get(f"{prefix}/receipts/{{job_id}}")
    async def compute_receipt(request: Request, job_id: str) -> JSONResponse:
        try:
            owner_id = _authorize_request(request)
        except AuthenticationError as exc:
            status = 503 if "not configured" in str(exc) else 401
            return JSONResponse(
                {"state": "UNAVAILABLE" if status == 503 else "UNAUTHORIZED",
                 "error": str(exc), **ZERO_UPLIFT},
                status_code=status,
            )
        try:
            record = get_job(job_id, owner_id=owner_id)
        except ContractError as exc:
            return JSONResponse({"state": "REJECTED", "error": str(exc), **ZERO_UPLIFT}, status_code=422)
        if record is None:
            return JSONResponse({"state": "NOT_FOUND", "job_id": job_id, **ZERO_UPLIFT}, status_code=404)
        return JSONResponse(
            {
                "job_id": job_id,
                "receipt": record["receipt"],
                "dsse": record["dsse"],
                "dsse_verification": record["dsse_verification"],
                "lake": record["lake"],
            }
        )

    @app.post(f"{prefix}/receipts/verify")
    async def compute_verify(request: Request) -> JSONResponse:
        try:
            verdict = verify_job_record(await _bounded_body(request))
        except ContractError as exc:
            return JSONResponse({"valid": False, "error": str(exc), **ZERO_UPLIFT}, status_code=422)
        return JSONResponse(verdict, status_code=200 if verdict["valid"] else 409)

    return {
        "registered": True,
        "routes": [
            f"{prefix}/capabilities",
            f"{prefix}/jobs",
            f"{prefix}/jobs/{{job_id}}",
            f"{prefix}/receipts/{{job_id}}",
            f"{prefix}/receipts/verify",
        ],
        "operation_count": len(OPERATIONS),
        "stateful_routes_require_auth": True,
        "auth_secret": "A11OY_COMPUTE_TOKEN_SHA256",
        **ZERO_UPLIFT,
    }


__all__ = [
    "ContractError",
    "JOB_SCHEMA",
    "OPERATIONS",
    "RECEIPT_SCHEMA",
    "RESULT_SCHEMA",
    "capabilities",
    "digest_json",
    "get_job",
    "parse_job",
    "register",
    "run_job",
    "verify_job_record",
]
