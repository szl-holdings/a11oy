"""Deterministic draft-to-envelope bridge for SZL-Forge ReceiptAgent.

The model emits ``szl.forge-receipt-draft.v1``.  This module never trusts the
model to admit evidence, determine formula proof status, authorize a tool, or
sign a receipt.  It resolves those facts from caller-supplied immutable
snapshots and only returns an ANSWERED final envelope when an external receipt
has already been verified against the exact computed bindings.

This module performs no network calls, tool execution, signing, or secret
access.  Those remain deployment boundaries of the A11oy runtime.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import threading
from copy import deepcopy
from typing import Any, Mapping


DRAFT_SCHEMA_VERSION = "szl.forge-receipt-draft.v1"
FINAL_SCHEMA_VERSION = "szl.receipt-agent-output.v1"
CANONICAL_CANDIDATE_ID = "SZL-Forge-1.5B-ReceiptAgent-v1"
RECEIPT_PAYLOAD_TYPE = "application/vnd.szl.receipt-agent-binding+json"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
EVIDENCE_ID_RE = re.compile(r"^(fixture|brain|artifact|source|receipt):[A-Za-z0-9._:/-]+$")
FINAL_EVIDENCE_ID_RE = re.compile(r"^(brain|artifact|source|receipt):[A-Za-z0-9._:/-]+$")
FORMULA_STATUS = {"KERNEL_ACCEPTED", "CONDITIONAL", "OPEN", "REFUTED", "NOT_EVALUATED"}
ABSTENTION_CODES = {
    "NONE",
    "MODEL_UNAVAILABLE",
    "EVIDENCE_NOT_ADMITTED",
    "EVIDENCE_INSUFFICIENT",
    "FORMULA_NAMESPACE_CONFLICT",
    "RECEIPT_INVALID",
    "POLICY_DENIED",
    "UNCERTAINTY_TOO_HIGH",
}


class ReceiptRuntimeError(ValueError):
    """Raised when an input violates the deterministic runtime contract."""


class ReceiptReplayGuard:
    """Process-local single-use guard; deployments must back this with durable storage."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._consumed: set[str] = set()

    def consume(self, receipt_id: str) -> bool:
        with self._lock:
            if receipt_id in self._consumed:
                return False
            self._consumed.add(receipt_id)
            return True


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _dsse_pae(payload_type: str, payload: bytes) -> bytes:
    payload_type_bytes = payload_type.encode("utf-8")
    return b"DSSEv1 %d %b %d %b" % (
        len(payload_type_bytes),
        payload_type_bytes,
        len(payload),
        payload,
    )


def _verify_hmac_dsse(envelope: Any, key: bytes) -> dict[str, Any]:
    """Verify a non-stub HMAC-SHA256 DSSE envelope and return its JSON payload."""

    _require(isinstance(key, bytes) and len(key) >= 32, "receipt HMAC key must contain at least 32 bytes")
    _require(isinstance(envelope, dict), "receipt envelope must be an object")
    _require_exact_keys(envelope, {"payloadType", "payload", "signatures"}, "receipt envelope")
    _require(envelope["payloadType"] == RECEIPT_PAYLOAD_TYPE, "unexpected receipt payload type")
    _require(isinstance(envelope["payload"], str), "receipt payload must be base64 text")
    _require(isinstance(envelope["signatures"], list) and len(envelope["signatures"]) == 1, "exactly one receipt signature is required")
    signature = envelope["signatures"][0]
    _require(isinstance(signature, dict), "receipt signature must be an object")
    _require_exact_keys(signature, {"keyid", "scheme", "sig"}, "receipt signature")
    _require(signature["scheme"] == "hmac-sha256", "stub or unsupported receipt signature scheme")
    _require(isinstance(signature["keyid"], str) and bool(signature["keyid"]), "receipt key id required")
    try:
        payload = base64.b64decode(envelope["payload"], validate=True)
        actual = base64.b64decode(signature["sig"], validate=True)
    except Exception as exc:  # pragma: no cover - exact decoder exception is platform-specific
        raise ReceiptRuntimeError("invalid receipt base64") from exc
    expected = hmac.new(key, _dsse_pae(RECEIPT_PAYLOAD_TYPE, payload), hashlib.sha256).digest()
    _require(hmac.compare_digest(actual, expected), "receipt DSSE signature verification failed")
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReceiptRuntimeError("receipt payload is not canonical JSON") from exc
    _require(canonical_bytes(value) == payload, "receipt payload is not canonically encoded")
    _require(isinstance(value, dict), "receipt payload must be an object")
    return value


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ReceiptRuntimeError(message)


def _require_exact_keys(value: Mapping[str, Any], keys: set[str], label: str) -> None:
    actual = set(value)
    _require(actual == keys, f"{label} keys mismatch: expected {sorted(keys)}, got {sorted(actual)}")


def validate_draft(draft: Any) -> None:
    """Validate the full checked-in draft contract without optional packages."""

    _require(isinstance(draft, dict), "draft must be an object")
    _require_exact_keys(
        draft,
        {
            "schema_version",
            "status",
            "answer",
            "evidence_ids",
            "formula_refs",
            "uncertainty",
            "abstention",
            "tool_proposal",
        },
        "draft",
    )
    _require(draft["schema_version"] == DRAFT_SCHEMA_VERSION, "unsupported draft schema")
    status = draft["status"]
    _require(status in {"ANSWER_PROPOSED", "ABSTAINED", "UNAVAILABLE"}, "invalid draft status")

    evidence_ids = draft["evidence_ids"]
    _require(isinstance(evidence_ids, list), "evidence_ids must be an array")
    _require(len(evidence_ids) == len(set(evidence_ids)), "evidence_ids must be unique")
    _require(
        all(isinstance(item, str) and EVIDENCE_ID_RE.fullmatch(item) for item in evidence_ids),
        "invalid evidence id",
    )

    formula_refs = draft["formula_refs"]
    _require(isinstance(formula_refs, list), "formula_refs must be an array")
    formula_keys: set[tuple[str, str]] = set()
    for index, formula in enumerate(formula_refs):
        _require(isinstance(formula, dict), f"formula_refs[{index}] must be an object")
        _require_exact_keys(formula, {"namespace", "formula_id", "claimed_status"}, f"formula_refs[{index}]")
        namespace = formula["namespace"]
        formula_id = formula["formula_id"]
        _require(isinstance(namespace, str) and bool(namespace), "formula namespace required")
        _require(isinstance(formula_id, str) and bool(formula_id), "formula id required")
        _require(formula["claimed_status"] in FORMULA_STATUS, "invalid claimed formula status")
        key = (namespace, formula_id)
        _require(key not in formula_keys, "formula references must be unique")
        formula_keys.add(key)

    uncertainty = draft["uncertainty"]
    _require(isinstance(uncertainty, dict), "uncertainty must be an object")
    _require_exact_keys(uncertainty, {"band", "basis"}, "uncertainty")
    _require(uncertainty["band"] in {"LOW", "MEDIUM", "HIGH", "NOT_EVALUATED"}, "invalid uncertainty band")
    _require(isinstance(uncertainty["basis"], str) and bool(uncertainty["basis"]), "uncertainty basis required")

    abstention = draft["abstention"]
    _require(isinstance(abstention, dict), "abstention must be an object")
    _require_exact_keys(abstention, {"required", "code", "detail"}, "abstention")
    _require(isinstance(abstention["required"], bool), "abstention.required must be boolean")
    _require(abstention["code"] in ABSTENTION_CODES, "invalid abstention code")
    _require(isinstance(abstention["detail"], str) and bool(abstention["detail"]), "abstention detail required")

    tool = draft["tool_proposal"]
    _require(isinstance(tool, dict), "tool_proposal must be an object")
    _require_exact_keys(tool, {"state", "tool_id", "arguments"}, "tool_proposal")
    _require(tool["state"] in {"NONE", "PROPOSED"}, "invalid tool state")
    if tool["state"] == "NONE":
        _require(tool["tool_id"] is None and tool["arguments"] is None, "NONE tool must have null identity and arguments")
    else:
        _require(status == "ANSWER_PROPOSED", "only an answer proposal may contain a tool proposal")
        _require(isinstance(tool["tool_id"], str) and bool(tool["tool_id"]), "proposed tool id required")
        _require(isinstance(tool["arguments"], dict) and bool(tool["arguments"]), "proposed tool arguments required")

    if status == "ANSWER_PROPOSED":
        _require(isinstance(draft["answer"], str) and bool(draft["answer"]), "answer proposal requires text")
        _require(bool(evidence_ids), "answer proposal requires evidence")
        _require(uncertainty["band"] in {"LOW", "MEDIUM"}, "answer proposal uncertainty is too high")
        _require(abstention["required"] is False and abstention["code"] == "NONE", "answer proposal cannot abstain")
    elif status == "ABSTAINED":
        _require(draft["answer"] is None, "abstention cannot carry answer text")
        _require(not evidence_ids and not formula_refs, "abstention cannot carry model-selected evidence or formulae")
        _require(uncertainty["band"] == "HIGH", "abstention must report HIGH uncertainty")
        _require(abstention["required"] is True and abstention["code"] not in {"NONE", "MODEL_UNAVAILABLE"}, "invalid abstention state")
        _require(tool["state"] == "NONE", "abstention cannot propose a tool")
    else:
        _require(draft["answer"] is None, "unavailable response cannot carry answer text")
        _require(not evidence_ids and not formula_refs, "unavailable response cannot carry evidence or formulae")
        _require(uncertainty["band"] == "NOT_EVALUATED", "unavailable response must be NOT_EVALUATED")
        _require(abstention["required"] is True and abstention["code"] == "MODEL_UNAVAILABLE", "invalid unavailable state")
        _require(tool["state"] == "NONE", "unavailable response cannot propose a tool")


def _validate_model_identity(model_identity: Any) -> dict[str, Any]:
    _require(isinstance(model_identity, dict), "model identity must be an object")
    required = {"candidate_id", "release_state", "base_repository", "base_revision", "adapter_sha256"}
    _require_exact_keys(model_identity, required, "model_identity")
    _require(model_identity["candidate_id"] == CANONICAL_CANDIDATE_ID, "unexpected candidate identity")
    _require(model_identity["release_state"] in {"EXPERIMENTAL", "PROMOTED"}, "a trained runtime identity is required")
    _require(isinstance(model_identity["base_repository"], str) and bool(model_identity["base_repository"]), "base repository required")
    _require(isinstance(model_identity["base_revision"], str) and re.fullmatch(r"[0-9a-f]{40}", model_identity["base_revision"]), "invalid base revision")
    _require(isinstance(model_identity["adapter_sha256"], str) and SHA256_RE.fullmatch(model_identity["adapter_sha256"]), "verified adapter digest required")
    return deepcopy(model_identity)


def _empty_final(
    *,
    draft: Mapping[str, Any],
    request: Any,
    policy_snapshot: Any,
    model_identity: Mapping[str, Any],
    status: str,
    code: str,
    detail: str,
    calibration_state: str,
) -> dict[str, Any]:
    response_seed = {"draft": draft, "request": request, "policy": policy_snapshot, "model": model_identity}
    return {
        "schema_version": FINAL_SCHEMA_VERSION,
        "response_id": f"response:{canonical_sha256(response_seed)[:24]}",
        "model_identity": deepcopy(model_identity),
        "status": status,
        "answer": None,
        "evidence": [],
        "formulae": [],
        "uncertainty": {
            "confidence": None,
            "calibration_state": calibration_state,
            "basis": draft["uncertainty"]["basis"],
        },
        "abstention": {"required": True, "code": code, "detail": detail},
        "tool_proposal": {
            "state": "NONE",
            "tool_id": None,
            "arguments_sha256": None,
            "requires_human_approval": True,
            "execution_receipt_id": None,
        },
        "receipt_binding": {
            "state": "NOT_AVAILABLE",
            "request_sha256": canonical_sha256(request),
            "evidence_set_sha256": None,
            "policy_snapshot_sha256": canonical_sha256(policy_snapshot),
            "receipt_id": None,
        },
    }


def finalize_draft(
    draft: Any,
    *,
    request: Any,
    evidence_catalog: Mapping[str, Mapping[str, Any]],
    formula_catalog: Mapping[str, Mapping[str, Any]],
    policy_snapshot: Mapping[str, Any],
    model_identity: Mapping[str, Any],
    calibration: Mapping[str, Any] | None = None,
    receipt_envelope: Mapping[str, Any] | None = None,
    receipt_hmac_key: bytes | None = None,
    replay_guard: ReceiptReplayGuard | None = None,
) -> dict[str, Any]:
    """Resolve an unsigned model draft into a fail-closed final envelope.

    The receipt must be a canonically encoded DSSE envelope with a valid
    HMAC-SHA256 signature over every decision-bearing component.  HMAC is an
    experimental local-runtime mechanism; public promotion still requires an
    asymmetric DSSE/in-toto attestation and transparency-log record.
    """

    validate_draft(draft)
    identity = _validate_model_identity(model_identity)
    _require(isinstance(request, (dict, list, str)), "request must be canonical JSON data")
    _require(isinstance(policy_snapshot, dict), "policy snapshot must be an object")
    allowed_tools = policy_snapshot.get("allowed_tool_ids", [])
    _require(isinstance(allowed_tools, list) and all(isinstance(x, str) for x in allowed_tools), "allowed_tool_ids must be strings")

    if draft["status"] == "UNAVAILABLE":
        return _empty_final(
            draft=draft,
            request=request,
            policy_snapshot=policy_snapshot,
            model_identity=identity,
            status="UNAVAILABLE",
            code="MODEL_UNAVAILABLE",
            detail=draft["abstention"]["detail"],
            calibration_state="NOT_EVALUATED",
        )
    if draft["status"] == "ABSTAINED":
        return _empty_final(
            draft=draft,
            request=request,
            policy_snapshot=policy_snapshot,
            model_identity=identity,
            status="ABSTAINED",
            code=draft["abstention"]["code"],
            detail=draft["abstention"]["detail"],
            calibration_state="UNCALIBRATED",
        )

    resolved_evidence: list[dict[str, Any]] = []
    for evidence_id in draft["evidence_ids"]:
        record = evidence_catalog.get(evidence_id)
        if not isinstance(record, Mapping):
            return _empty_final(
                draft=draft, request=request, policy_snapshot=policy_snapshot,
                model_identity=identity, status="ABSTAINED", code="EVIDENCE_NOT_ADMITTED",
                detail=f"Evidence {evidence_id} is absent from the immutable admitted snapshot.",
                calibration_state="UNCALIBRATED",
            )
        required = {"content_sha256", "support_role", "admission_state", "freshness_state", "final_evidence_id"}
        if not required.issubset(record):
            raise ReceiptRuntimeError(f"evidence catalog record {evidence_id} is incomplete")
        final_id = record["final_evidence_id"]
        if (
            record["admission_state"] != "ADMITTED_REFERENCE"
            or record["freshness_state"] not in {"CURRENT", "NOT_APPLICABLE"}
            or not isinstance(final_id, str)
            or not FINAL_EVIDENCE_ID_RE.fullmatch(final_id)
            or not isinstance(record["content_sha256"], str)
            or not SHA256_RE.fullmatch(record["content_sha256"])
            or record["support_role"] not in {"SUPPORTS", "CONTRADICTS", "CONTEXT"}
        ):
            return _empty_final(
                draft=draft, request=request, policy_snapshot=policy_snapshot,
                model_identity=identity, status="ABSTAINED", code="EVIDENCE_NOT_ADMITTED",
                detail=f"Evidence {evidence_id} failed admission, freshness, or identity validation.",
                calibration_state="UNCALIBRATED",
            )
        item = {
            "evidence_id": final_id,
            "content_sha256": record["content_sha256"],
            "support_role": record["support_role"],
            "admission_state": "ADMITTED_REFERENCE",
        }
        source_uri = record.get("source_uri")
        if source_uri is not None:
            _require(isinstance(source_uri, str) and source_uri.startswith("https://"), "invalid source URI")
            item["source_uri"] = source_uri
        resolved_evidence.append(item)

    resolved_formulae: list[dict[str, Any]] = []
    for claimed in draft["formula_refs"]:
        key = f"{claimed['namespace']}::{claimed['formula_id']}"
        authoritative = formula_catalog.get(key)
        if not isinstance(authoritative, Mapping) or authoritative.get("status") != claimed["claimed_status"]:
            return _empty_final(
                draft=draft, request=request, policy_snapshot=policy_snapshot,
                model_identity=identity, status="ABSTAINED", code="FORMULA_NAMESPACE_CONFLICT",
                detail=f"Formula reference {key} does not match the authoritative snapshot.",
                calibration_state="UNCALIBRATED",
            )
        receipt_hash = authoritative.get("formula_receipt_sha256")
        semantic_binding = authoritative.get("semantic_binding_sha256")
        proof_allowed = (
            claimed["claimed_status"] == "KERNEL_ACCEPTED"
            and authoritative.get("verification_state") == "KERNEL_VERIFIED"
            and isinstance(receipt_hash, str)
            and bool(SHA256_RE.fullmatch(receipt_hash))
            and isinstance(semantic_binding, str)
            and bool(SHA256_RE.fullmatch(semantic_binding))
        )
        if claimed["claimed_status"] == "KERNEL_ACCEPTED" and not proof_allowed:
            return _empty_final(
                draft=draft, request=request, policy_snapshot=policy_snapshot,
                model_identity=identity, status="ABSTAINED", code="FORMULA_NAMESPACE_CONFLICT",
                detail=f"Formula reference {key} lacks a kernel verification and semantic binding.",
                calibration_state="UNCALIBRATED",
            )
        resolved_formulae.append(
            {
                "formula_id": claimed["formula_id"],
                "namespace": claimed["namespace"],
                "status": claimed["claimed_status"],
                "proof_transfer_allowed": proof_allowed,
                "formula_receipt_sha256": receipt_hash if proof_allowed else None,
            }
        )

    tool = draft["tool_proposal"]
    if tool["state"] == "PROPOSED" and tool["tool_id"] not in allowed_tools:
        return _empty_final(
            draft=draft, request=request, policy_snapshot=policy_snapshot,
            model_identity=identity, status="ABSTAINED", code="POLICY_DENIED",
            detail=f"Tool {tool['tool_id']} is not allowed by the bound policy snapshot.",
            calibration_state="UNCALIBRATED",
        )

    if not isinstance(calibration, Mapping):
        return _empty_final(
            draft=draft, request=request, policy_snapshot=policy_snapshot,
            model_identity=identity, status="ABSTAINED", code="UNCERTAINTY_TOO_HIGH",
            detail="No externally measured calibration value is bound to this response.",
            calibration_state="UNCALIBRATED",
        )
    confidence = calibration.get("confidence")
    _require(isinstance(confidence, (int, float)) and not isinstance(confidence, bool) and 0 <= confidence <= 1, "invalid calibrated confidence")
    _require(isinstance(calibration.get("basis"), str) and bool(calibration["basis"]), "calibration basis required")

    final_tool = {
        "state": tool["state"],
        "tool_id": tool["tool_id"],
        "arguments_sha256": canonical_sha256(tool["arguments"]) if tool["state"] == "PROPOSED" else None,
        "requires_human_approval": True,
        "execution_receipt_id": None,
    }
    evidence_hash = canonical_sha256(sorted(resolved_evidence, key=lambda item: item["evidence_id"]))
    formula_hash = canonical_sha256(sorted(resolved_formulae, key=lambda item: (item["namespace"], item["formula_id"])))
    request_hash = canonical_sha256(request)
    policy_hash = canonical_sha256(policy_snapshot)
    draft_hash = canonical_sha256(draft)
    identity_hash = canonical_sha256(identity)
    calibration_hash = canonical_sha256(calibration)
    tool_hash = canonical_sha256(final_tool)
    binding_payload = {
        "schema_version": "szl.receipt-agent-binding.v1",
        "draft_sha256": draft_hash,
        "answer_sha256": canonical_sha256(draft["answer"]),
        "model_identity_sha256": identity_hash,
        "request_sha256": request_hash,
        "evidence_set_sha256": evidence_hash,
        "formula_set_sha256": formula_hash,
        "calibration_sha256": calibration_hash,
        "tool_proposal_sha256": tool_hash,
        "policy_snapshot_sha256": policy_hash,
    }
    binding_hash = canonical_sha256(binding_payload)
    if receipt_envelope is None or receipt_hmac_key is None or replay_guard is None:
        return _empty_final(
            draft=draft, request=request, policy_snapshot=policy_snapshot,
            model_identity=identity, status="ABSTAINED", code="RECEIPT_INVALID",
            detail="No cryptographically verified, replay-protected receipt binds the complete response payload.",
            calibration_state="CALIBRATED",
        )
    receipt = _verify_hmac_dsse(receipt_envelope, receipt_hmac_key)
    receipt_fields = {
        "schema_version",
        "receipt_id",
        "nonce",
        "binding_payload_sha256",
        "draft_sha256",
        "answer_sha256",
        "model_identity_sha256",
        "request_sha256",
        "evidence_set_sha256",
        "formula_set_sha256",
        "calibration_sha256",
        "tool_proposal_sha256",
        "policy_snapshot_sha256",
    }
    _require_exact_keys(receipt, receipt_fields, "receipt payload")
    _require(receipt["schema_version"] == "szl.receipt-agent-verifier-result.v1", "unsupported receipt result schema")
    _require(isinstance(receipt["receipt_id"], str) and bool(receipt["receipt_id"]), "receipt id required")
    _require(isinstance(receipt["nonce"], str) and len(receipt["nonce"]) >= 16, "receipt nonce required")
    expected_bindings = dict(binding_payload)
    expected_bindings["binding_payload_sha256"] = binding_hash
    for field, expected in expected_bindings.items():
        if field == "schema_version":
            continue
        _require(receipt.get(field) == expected, f"receipt {field} mismatch")
    _require(replay_guard.consume(receipt["receipt_id"]), "receipt replay detected")

    response_seed = {
        "binding_payload_sha256": binding_hash,
        "receipt_id": receipt["receipt_id"],
        "nonce": receipt["nonce"],
    }
    return {
        "schema_version": FINAL_SCHEMA_VERSION,
        "response_id": f"response:{canonical_sha256(response_seed)[:24]}",
        "model_identity": identity,
        "status": "ANSWERED",
        "answer": draft["answer"],
        "evidence": resolved_evidence,
        "formulae": resolved_formulae,
        "uncertainty": {
            "confidence": confidence,
            "calibration_state": "CALIBRATED",
            "basis": calibration["basis"],
        },
        "abstention": {"required": False, "code": "NONE", "detail": "All deterministic gates passed."},
        "tool_proposal": final_tool,
        "receipt_binding": {
            "state": "SIGNED",
            "request_sha256": request_hash,
            "evidence_set_sha256": evidence_hash,
            "policy_snapshot_sha256": policy_hash,
            "receipt_id": receipt["receipt_id"],
        },
    }
