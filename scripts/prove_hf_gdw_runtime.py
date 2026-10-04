#!/usr/bin/env python3
"""Exercise the exact live GDW successor without recording bearer material."""

from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import json
import os
import re
import stat
import time
from datetime import datetime, timezone
from pathlib import Path

import sys
from typing import Any


_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(_REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPOSITORY_ROOT))

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import hf_live_proof_bounds as bounds  # noqa: E402
from hf_live_proof_bounds import ProofBoundaryError  # noqa: E402


# Transient admission only: a booting Space (502/503/504) or a momentarily
# saturated GDW admission ceiling / pending drain (429, and the 503 the runtime
# returns while write admission is pending). Every other status, transport
# error or malformed body fails closed on the first response. Integrity
# verdicts arrive as HTTP 200 bodies and are asserted, unretried, below.
_TRANSIENT_HTTP_STATUSES = bounds.TRANSIENT_HTTP_STATUSES
_REQUEST_ATTEMPTS = bounds.MAX_ATTEMPTS
# Calls made from inside a convergence loop already have an outer retry
# budget, so they only absorb a single hiccup and let the loop re-poll.
_POLL_ATTEMPTS = 2
# Proof-wide deadline (drain convergence + write + receipt verification).
DEFAULT_DEADLINE_SECONDS = bounds.RETRY_WINDOW_SECONDS
MAX_DEADLINE_SECONDS = bounds.RETRY_WINDOW_SECONDS
# Effect scope: every GDW call stays under the a11oy namespace prefix, and
# writes are limited to these three reviewed routes.
GDW_PREFIX = "/api/a11oy/v1/gdw/"
_READ_PATHS = ("/api/build-info",)
_WRITE_PATHS = (
    GDW_PREFIX + "step",
    GDW_PREFIX + "drain",
    GDW_PREFIX + "recovery/transient-effects",
)
_TRANSPORT: bounds.BoundedTransport | None = None
_MANAGED_CONTEXT: Any = None
_MANAGED_LATEST: dict | None = None


def load_managed_proof_context(receipt_path: Path, *, source_revision: str,
                               deadline: float) -> Any:
    """Use the fixed sibling to independently verify immutable provider authority."""
    path = Path(__file__).resolve().with_name("configure_hf_gdw_runtime.py")
    spec = importlib.util.spec_from_file_location("gdw_managed_proof_config", path)
    if spec is None or spec.loader is None:
        raise ProofBoundaryError("EFFECT_SCOPE_REJECTED")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.load_managed_proof_context(
        receipt_path, source_revision=source_revision, deadline=deadline)


def _managed_health(health: dict) -> dict | None:
    """Validate every managed health observation, including pre-write readbacks."""
    global _MANAGED_LATEST
    persistence = health.get("persistence") if isinstance(health, dict) else None
    storage = persistence.get("storage") if isinstance(persistence, dict) else None
    if not isinstance(storage, dict):
        if _MANAGED_CONTEXT is not None:
            raise ProofBoundaryError("EFFECT_SCOPE_REJECTED")
        return None
    present = any(key in storage for key in
                  ("durable_storage", "managed_admission", "durability_authority"))
    if _MANAGED_CONTEXT is None:
        if present:
            raise ProofBoundaryError("EFFECT_SCOPE_REJECTED")
        return None
    try:
        if (storage.get("durable_storage") != "private-dataset-v1"
                or storage.get("durability_authority") != "verified-private-dataset-head"
                or storage.get("required_mount") is not None
                or storage.get("mount_verified") is not False
                or storage.get("persistence_required") is not True
                or storage.get("journal_mode_observed") != "DELETE"):
            raise ValueError("managed health contract")
        _MANAGED_LATEST = _MANAGED_CONTEXT.validate(storage.get("managed_admission"),
            label="gdw", generation=storage.get("database_generation_id"))
        return _MANAGED_LATEST
    except Exception:
        raise ProofBoundaryError("EFFECT_SCOPE_REJECTED") from None


class TransientRequestError(ProofBoundaryError):
    """A readiness/capacity condition that survived the whole retry budget."""

    def __init__(self, *, http_status: int | None = None) -> None:
        super().__init__("TRANSIENT_RETRY_EXHAUSTED", http_status=http_status)


def configure_transport(transport: bounds.BoundedTransport | None) -> None:
    """Bind the proof-wide transport (and its shared deadline)."""

    global _TRANSPORT
    _TRANSPORT = transport


def _transport() -> bounds.BoundedTransport:
    return _TRANSPORT if _TRANSPORT is not None else bounds.BoundedTransport()


def _sleep(seconds: float) -> None:
    if _TRANSPORT is not None:
        _TRANSPORT.sleep(seconds)
    else:
        time.sleep(seconds)


def _reraise_hard(error: BaseException) -> None:
    if bounds.is_hard_failure(error):
        raise error


def _check_gdw_scope(method: str, url: str) -> None:
    bounds.check_destination(url)
    path = url.split("://", 1)[-1].split("/", 1)[-1]
    path = "/" + path.split("?", 1)[0]
    if not url.startswith(bounds.CANONICAL_ORIGIN + "/"):
        raise ProofBoundaryError("DESTINATION_REJECTED")
    if method == "POST":
        if path not in _WRITE_PATHS:
            raise ProofBoundaryError("EFFECT_SCOPE_REJECTED")
    elif not (path in _READ_PATHS or path.startswith(GDW_PREFIX)):
        raise ProofBoundaryError("NAMESPACE_SCOPE_REJECTED")


def request_json(
    method: str,
    url: str,
    *,
    token: str | None = None,
    attempts: int = _REQUEST_ATTEMPTS,
    **kwargs,
):
    """Perform one bounded JSON call, retrying only transient admission.

    Mutating calls in this proof carry an ``X-Request-Id`` / ``Idempotency-Key``
    so a retried POST is replayed by the runtime instead of duplicated. The
    destination, namespace and write route are checked before any network
    access; redirects are refused; provider bodies are never read on error.
    """

    headers = dict(kwargs.pop("headers", {}))
    payload = kwargs.pop("json", None)
    if kwargs:
        raise TypeError("unsupported request options")
    _check_gdw_scope(method, url)
    if method == "POST" and _MANAGED_CONTEXT is not None:
        # The immutable witness is refreshed next to every governed write,
        # including idempotent replay/recovery paths; an earlier healthy read
        # cannot authorize a later write after admission or writer loss.
        request_json("GET", bounds.CANONICAL_ORIGIN + GDW_PREFIX + "healthz",
                     attempts=_POLL_ATTEMPTS)
    try:
        _status, value = _transport().request(
            method, url, token=token, headers=headers, json_body=payload,
            attempts=attempts,
        )
    except ProofBoundaryError as exc:
        if exc.code == "TRANSIENT_RETRY_EXHAUSTED":
            raise TransientRequestError(http_status=exc.http_status) from None
        raise
    if method == "GET" and url.split("?", 1)[0] == bounds.CANONICAL_ORIGIN + GDW_PREFIX + "healthz":
        _managed_health(value)
    return value


def _canonical_hash(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _canonical_utc_timestamp(value) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return False
    return (
        parsed.tzinfo is not None
        and parsed.utcoffset() == timezone.utc.utcoffset(parsed)
        and parsed.isoformat() == value
    )


def _drain_converged(candidate: dict) -> bool:
    return (
        candidate.get("ok") is True
        and candidate.get("pending_effects") == 0
        and candidate.get("claimed_effects") == 0
        and candidate.get("dead_letter_effects") == 0
    )


def _drain_contract_is_valid(
    drain: dict,
    database_generation_id: str,
) -> bool:
    return (
        drain.get("failed") == 0
        and drain.get("legacy_pending_proofs") == 0
        and drain.get("integrity_ok") is True
        and drain.get("database_generation_id") == database_generation_id
    )


def _global_integrity_is_complete(
    integrity: dict,
    database_generation_id: str,
) -> bool:
    return (
        _drain_converged(integrity)
        and integrity.get("database_generation_id") == database_generation_id
        and integrity.get("journal_mode") == "DELETE"
        and integrity.get("pending_proofs") == 0
        and integrity.get("invalid_effect_bindings") == 0
        and integrity.get("invalid_exported_artifacts") == 0
        and integrity.get("invalid_recovery_audits") == 0
    )


def _health_is_write_ready(health: dict, database_generation_id: str) -> bool:
    _managed_health(health)
    return (
        health.get("status") == "REAL"
        and health.get("write_ready") is True
        and not health.get("write_blockers")
        and (
            (health.get("persistence") or {})
            .get("storage", {})
            .get("database_generation_id")
            == database_generation_id
        )
        and (
            (health.get("persistence") or {})
            .get("drain", {})
            .get("last_outcome")
            == "SUCCEEDED"
        )
    )


def _safe_convergence_state(
    *,
    reason: str,
    health: dict | None,
    drain: dict | None,
    global_integrity: dict | None,
    stable_samples: int,
) -> dict:
    health = health or {}
    persistence = health.get("persistence") or {}
    supervisor = persistence.get("drain") or {}
    drain = drain or {}
    global_integrity = global_integrity or {}
    return {
        "reason": reason,
        "health_status": health.get("status"),
        "write_ready": health.get("write_ready"),
        "write_blockers": health.get("write_blockers"),
        "supervisor_outcome": supervisor.get("last_outcome"),
        "supervisor_attempt_at": supervisor.get("last_attempt_at"),
        "supervisor_success_at": supervisor.get("last_success_at"),
        "supervisor_errors": [
            value
            for value in (
                (supervisor.get("last_report") or {}).get("errors") or []
            )
            if isinstance(value, str)
            and len(value) <= 96
            and all(ch.isalnum() or ch in "_:" for ch in value)
        ],
        "stable_samples": stable_samples,
        "drain_failed": drain.get("failed"),
        "drain_errors": [
            value
            for value in (drain.get("errors") or [])
            if isinstance(value, str)
            and len(value) <= 96
            and all(ch.isalnum() or ch in "_:" for ch in value)
        ],
        "drain_pending_effects": drain.get("pending_effects"),
        "drain_legacy_pending_proofs": drain.get(
            "legacy_pending_proofs"
        ),
        "global_pending_proofs": global_integrity.get("pending_proofs"),
        "global_pending_effects": global_integrity.get("pending_effects"),
        "global_claimed_effects": global_integrity.get("claimed_effects"),
        "global_dead_letter_effects": global_integrity.get(
            "dead_letter_effects"
        ),
        "global_invalid_effect_bindings": global_integrity.get(
            "invalid_effect_bindings"
        ),
        "global_invalid_exported_artifacts": global_integrity.get(
            "invalid_exported_artifacts"
        ),
        "global_invalid_recovery_audits": global_integrity.get(
            "invalid_recovery_audits"
        ),
    }


def _new_recovery_evidence() -> dict:
    return {
        "schema": "szl.hf-gdw-transient-recovery-evidence/v1",
        "calls": 0,
        "applied_rounds": 0,
        "rescheduled_effects": 0,
        "last_status": "NOT_CALLED",
        "selection_sha256": [],
        "receipt_sha256": [],
        "replayed_calls": 0,
        "attempt_accounting_preserved": True,
        "credential_values_recorded": False,
    }


PROOF_RECOVERY_PREFIX = "gdw-proof"


def _pinned_key_der() -> bytes:
    """DER of ``ayllu/keys/council-runtime-2026-07-21.pub`` (fingerprint-checked)."""

    return bounds._load_pinned_key_der(bounds.REPO_ROOT)


def _verify_signed_envelope(envelope) -> dict:
    return bounds.verify_envelope_against_pinned_key(
        envelope, public_key_der=_pinned_key_der()
    )


def _recover_transient_effects(
    *,
    base: str,
    operator_token: str,
    source_sha: str,
    database_generation_id: str,
    evidence: dict,
    recovery_prefix: str = "gdw-recovery",
) -> dict:
    if recovery_prefix not in {"gdw-recovery", PROOF_RECOVERY_PREFIX}:
        raise ProofBoundaryError("EFFECT_SCOPE_REJECTED")
    call_number = evidence["calls"] + 1
    evidence["calls"] = call_number
    recovery_id = (
        f"{recovery_prefix}-{source_sha[:12]}-"
        f"{database_generation_id[:12]}-{call_number}"
    )
    report = request_json(
        "POST",
        f"{base}/api/a11oy/v1/gdw/recovery/transient-effects?limit=100",
        token=operator_token,
        headers={
            "X-Expected-Source-Revision": source_sha,
            "Idempotency-Key": recovery_id,
        },
    )
    outcome_fields = {
        "schema",
        "status",
        "recovery_id",
        "source_revision",
        "requested_limit",
        "failure_class",
        "database_generation_id",
        "inspected_pending_effects",
        "eligible_effects",
        "rescheduled_effects",
        "attempts_before",
        "attempts_after",
        "selection",
        "selection_sha256",
        "sqlite_integrity",
        "claimed_effects",
        "dead_letter_effects",
        "invalid_effect_bindings",
        "invalid_exported_artifacts",
        "invalid_recovery_audits",
        "credential_values_recorded",
    }
    receipt_payload_fields = {
        "schema",
        "operator",
        "recovery_id",
        "source_revision",
        "database_generation_id",
        "request_sha256",
        "outcome_sha256",
        "governance_sha256",
        "selection_sha256",
        "rescheduled_effects",
        "attempts_before",
        "attempts_after",
        "sequence",
        "previous_receipt_sha256",
        "previous_chain_sha256",
        "atomic_with_mutation",
        "created_at",
        "credential_values_recorded",
    }
    receipt_fields = receipt_payload_fields | {
        "receipt_status",
        "receipt_sha256",
        "dsse_envelope_sha256",
        "chain_sha256",
        "dsse_envelope",
    }
    report_is_object = type(report) is dict
    report_shape_ok = report_is_object and set(report) == outcome_fields | {
        "governance",
        "audit_receipt",
        "replayed",
    }
    outcome = (
        {field: report[field] for field in outcome_fields}
        if report_shape_ok
        else {}
    )
    replayed = report.get("replayed") if report_is_object else None
    receipt = report.get("audit_receipt") if report_is_object else None
    receipt = dict(receipt) if type(receipt) is dict else {}
    receipt_shape_ok = set(receipt) == receipt_fields
    claimed_receipt_sha256 = receipt.get("receipt_sha256")
    receipt_payload = (
        {field: receipt[field] for field in receipt_payload_fields}
        if receipt_shape_ok
        else {}
    )
    governance = report.get("governance") if report_is_object else None
    counts = {
        field: outcome.get(field)
        for field in (
            "inspected_pending_effects",
            "eligible_effects",
            "rescheduled_effects",
            "attempts_before",
            "attempts_after",
            "claimed_effects",
            "dead_letter_effects",
            "invalid_effect_bindings",
            "invalid_exported_artifacts",
            "invalid_recovery_audits",
        )
    }
    selection = outcome.get("selection")
    operator = receipt_payload.get("operator")
    operator_pattern = re.compile(r"[a-z0-9][a-z0-9._:-]{0,127}")
    selection_identifier_pattern = re.compile(r"[A-Za-z0-9._:-]{1,128}")
    receipt_created_at = (
        datetime.fromisoformat(receipt_payload["created_at"])
        if _canonical_utc_timestamp(receipt_payload.get("created_at"))
        else None
    )
    operator_ok = (
        type(operator) is dict
        and set(operator) == {"namespace", "owner_id", "credential_key_id"}
        and operator.get("namespace") == "a11oy"
        and all(
            type(value) is str and operator_pattern.fullmatch(value) is not None
            for value in operator.values()
        )
    )
    expected_governance_binding = (
        {
            "schema": "szl.gdw.transient-effect-recovery-authorization/v1",
            "action_type": "gdw.transient-effect-recovery",
            "namespace": operator["namespace"],
            "owner_id": operator["owner_id"],
            "credential_key_id": operator["credential_key_id"],
            "recovery_id": recovery_id,
            "source_revision": source_sha,
            "database_generation_id": database_generation_id,
            "limit": 100,
            "failure_class": "hf-hard-link-enotsup/v1",
        }
        if operator_ok
        else None
    )
    governance_binding_sha256 = (
        _canonical_hash(expected_governance_binding)
        if expected_governance_binding is not None
        else None
    )
    gateway = governance.get("policy_gateway") if type(governance) is dict else None
    governance_ok = (
        operator_ok
        and type(governance) is dict
        and set(governance) == {
            "schema",
            "decision",
            "binding",
            "binding_sha256",
            "policy_gateway",
        }
        and governance.get("schema")
        == "szl.gdw.transient-effect-recovery-governance/v1"
        and governance.get("decision") == "ALLOW"
        and governance.get("binding") == expected_governance_binding
        and governance.get("binding_sha256") == governance_binding_sha256
        and type(gateway) is dict
        and set(gateway) == {
            "decision",
            "gate",
            "receipt_hash",
            "receipt_signed",
            "receipts_in_eq_out",
            "action_id",
            "witnesses",
        }
        and gateway.get("decision") == "ALLOW"
        and gateway.get("gate") == "ThresholdPolicySeverity"
        and re.fullmatch(r"[0-9a-f]{64}", str(gateway.get("receipt_hash") or ""))
        is not None
        and gateway.get("receipt_signed") is True
        and gateway.get("receipts_in_eq_out") is True
        and gateway.get("action_id")
        == f"gdw-recovery:{governance_binding_sha256}"
        and gateway.get("witnesses")
        == [
            {
                "id": (
                    f"principal:{operator['namespace']}:"
                    f"{operator['owner_id']}:{operator['credential_key_id']}"
                ),
                "role": "operator",
                "attested": True,
            },
            {
                "id": f"workload:szl-holdings/a11oy@{source_sha}",
                "role": "workload",
                "attested": True,
            },
        ]
    )
    expected_request = (
        {
            "schema": "szl.gdw.transient-effect-recovery-request/v1",
            "namespace": operator["namespace"],
            "owner_id": operator["owner_id"],
            "credential_key_id": operator["credential_key_id"],
            "recovery_id": recovery_id,
            "source_revision": source_sha,
            "database_generation_id": database_generation_id,
            "limit": 100,
            "failure_class": "hf-hard-link-enotsup/v1",
            "governance_binding_sha256": governance_binding_sha256,
        }
        if operator_ok
        else None
    )
    selection_fields = {
        "namespace",
        "owner_id",
        "idempotency_key",
        "database_generation_id",
        "request_id",
        "kind",
        "receipt_hash",
        "payload_sha256",
        "intent_sha256",
        "attempts",
        "max_attempts",
        "next_attempt_at",
        "claim_generation",
        "last_error_sha256",
    }

    def is_digest(value, length=64):
        return type(value) is str and re.fullmatch(
            rf"[0-9a-f]{{{length}}}", value
        ) is not None

    selection_ok = type(selection) is list
    if selection_ok:
        for item in selection:
            if (
                type(item) is not dict
                or set(item) != selection_fields
                or item.get("database_generation_id") != database_generation_id
                or item.get("kind") not in {"receipt_projection", "proof_export"}
                or any(
                    type(item.get(field)) is not str
                    or selection_identifier_pattern.fullmatch(item[field])
                    is None
                    for field in (
                        "namespace",
                        "owner_id",
                        "idempotency_key",
                        "request_id",
                    )
                )
                or (
                    item.get("receipt_hash") is not None
                    and not is_digest(item.get("receipt_hash"))
                )
                or any(
                    not is_digest(item.get(field))
                    for field in (
                        "payload_sha256",
                        "intent_sha256",
                        "last_error_sha256",
                    )
                )
                or type(item.get("attempts")) is not int
                or type(item.get("max_attempts")) is not int
                or not 0 < item["attempts"] < item["max_attempts"]
                or type(item.get("claim_generation")) is not int
                or item["claim_generation"] < 0
                or not _canonical_utc_timestamp(item.get("next_attempt_at"))
                or receipt_created_at is None
                or datetime.fromisoformat(item["next_attempt_at"])
                <= receipt_created_at
            ):
                selection_ok = False
                break
    observed_outcome_sha256 = _canonical_hash(outcome)
    observed_receipt_sha256 = _canonical_hash(receipt_payload)
    envelope = receipt.get("dsse_envelope") if receipt_shape_ok else None
    try:
        decoded_envelope_payload = json.loads(
            base64.b64decode(
                str(envelope.get("payload") or ""),
                validate=True,
            ).decode("utf-8")
        )
    except (AttributeError, TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
        decoded_envelope_payload = None
    envelope_signed = (
        envelope.get("signed") if type(envelope) is dict else None
    )
    signatures = envelope.get("signatures") if type(envelope) is dict else None
    # A signed receipt is accepted only when its signature verifies against
    # the pinned runtime key; no other trusted-key source is consulted.
    try:
        pinned_verification = (
            _verify_signed_envelope(envelope)
            if envelope_signed is True and type(envelope) is dict
            else {}
        )
    except ProofBoundaryError:
        pinned_verification = {}
    signature_verification = (
        {
            "verified": pinned_verification.get("signature_verified") is True,
            "payloadType": envelope.get("payloadType"),
        }
        if pinned_verification
        else {}
    )
    dsse_status_ok = (
        (
            envelope_signed is True
            and receipt.get("receipt_status") == "SIGNED_KHIPU_DSSE"
            and type(signatures) is list
            and len(signatures) == 1
            and signature_verification.get("verified") is True
            and signature_verification.get("payloadType")
            == bounds.KHIPU_PAYLOAD_TYPE
        )
        or (
            envelope_signed is False
            and receipt.get("receipt_status") == "UNSIGNED_KHIPU_DSSE"
            and signatures == []
            and "UNSIGNED" in str(envelope.get("honesty") or "")
        )
    )
    observed_envelope_sha256 = (
        _canonical_hash(envelope) if type(envelope) is dict else None
    )
    observed_chain_sha256 = _canonical_hash(
        {
            "previous_chain_sha256": receipt_payload.get(
                "previous_chain_sha256"
            ),
            "receipt_sha256": observed_receipt_sha256,
            "receipt_status": receipt.get("receipt_status"),
            "dsse_envelope_sha256": observed_envelope_sha256,
        }
    )
    observed_selection_sha256 = (
        _canonical_hash(selection) if type(selection) is list else None
    )
    if (
        not report_shape_ok
        or not receipt_shape_ok
        or not operator_ok
        or not governance_ok
        or not selection_ok
        or outcome.get("schema")
        != "szl.gdw.transient-effect-recovery/v2"
        or outcome.get("status")
        not in {
            "RESCHEDULED",
            "NO_ELIGIBLE_EFFECTS",
            "DEFERRED_ACTIVE_CLAIM",
        }
        or outcome.get("database_generation_id")
        != database_generation_id
        or outcome.get("recovery_id") != recovery_id
        or outcome.get("source_revision") != source_sha
        or outcome.get("requested_limit") != 100
        or outcome.get("failure_class") != "hf-hard-link-enotsup/v1"
        or outcome.get("sqlite_integrity") != "ok"
        or outcome.get("credential_values_recorded") is not False
        or any(
            type(value) is not int or value < 0
            for value in counts.values()
        )
        or counts["rescheduled_effects"] > counts["eligible_effects"]
        or counts["eligible_effects"]
        > counts["inspected_pending_effects"]
        or counts["attempts_before"] != counts["attempts_after"]
        or counts["dead_letter_effects"] != 0
        or counts["invalid_effect_bindings"] != 0
        or counts["invalid_exported_artifacts"] != 0
        or counts["invalid_recovery_audits"] != 0
        or not is_digest(outcome.get("selection_sha256"))
        or outcome.get("selection_sha256") != observed_selection_sha256
        or len(selection) != counts["rescheduled_effects"]
        or counts["attempts_before"]
        != sum(item["attempts"] for item in selection)
        or type(replayed) is not bool
        or receipt_payload.get("schema")
        != "szl.gdw.transient-effect-recovery-receipt/v2"
        or receipt_payload.get("recovery_id") != recovery_id
        or receipt_payload.get("source_revision") != source_sha
        or receipt_payload.get("database_generation_id")
        != database_generation_id
        or receipt_payload.get("operator") != operator
        or receipt_payload.get("request_sha256")
        != _canonical_hash(expected_request)
        or not _canonical_utc_timestamp(receipt_payload.get("created_at"))
        or receipt_payload.get("credential_values_recorded") is not False
        or receipt_payload.get("atomic_with_mutation") is not True
        or type(receipt_payload.get("sequence")) is not int
        or receipt_payload["sequence"] < 0
        or not is_digest(receipt_payload.get("previous_receipt_sha256"))
        or not is_digest(receipt_payload.get("previous_chain_sha256"))
        or receipt_payload.get("governance_sha256")
        != _canonical_hash(governance)
        or receipt_payload.get("selection_sha256")
        != outcome.get("selection_sha256")
        or receipt_payload.get("rescheduled_effects")
        != counts["rescheduled_effects"]
        or receipt_payload.get("attempts_before")
        != counts["attempts_before"]
        or receipt_payload.get("attempts_after")
        != counts["attempts_after"]
        or receipt_payload.get("outcome_sha256")
        != observed_outcome_sha256
        or receipt.get("receipt_sha256") != observed_receipt_sha256
        or receipt.get("dsse_envelope_sha256")
        != observed_envelope_sha256
        or receipt.get("chain_sha256") != observed_chain_sha256
        or type(envelope) is not dict
        or envelope.get("payloadType") != "application/vnd.szl.khipu+json"
        or decoded_envelope_payload != receipt_payload
        or not dsse_status_ok
        or (
            outcome.get("status") == "RESCHEDULED"
            and (
                counts["rescheduled_effects"] == 0
                or counts["eligible_effects"]
                != counts["rescheduled_effects"]
                or counts["claimed_effects"] != 0
            )
        )
        or (
            outcome.get("status") == "NO_ELIGIBLE_EFFECTS"
            and (
                counts["eligible_effects"] != 0
                or counts["rescheduled_effects"] != 0
                or counts["claimed_effects"] != 0
            )
        )
        or (
            outcome.get("status") == "DEFERRED_ACTIVE_CLAIM"
            and (
                counts["claimed_effects"] == 0
                or counts["eligible_effects"] != 0
                or counts["rescheduled_effects"] != 0
            )
        )
    ):
        raise RuntimeError("GDW transient recovery contract failed")
    evidence["rescheduled_effects"] += counts["rescheduled_effects"]
    evidence["last_status"] = report["status"]
    evidence["receipt_sha256"].append(claimed_receipt_sha256)
    if replayed:
        evidence["replayed_calls"] += 1
    if counts["rescheduled_effects"]:
        evidence["applied_rounds"] += 1
        evidence["selection_sha256"].append(report["selection_sha256"])
    return report


def _prove_drain_convergence(
    *,
    base: str,
    operator_token: str,
    database_generation_id: str,
    source_sha: str | None = None,
    recovery_evidence: dict | None = None,
    attempts: int = 120,
    delay_seconds: float = 5,
    required_stable_samples: int = 3,
) -> tuple[dict, dict]:
    """Prove a protected drain after the supervised outbox reaches quiescence."""

    drain_url = f"{base}/api/a11oy/v1/gdw/drain?limit=100"
    global_integrity_url = (
        f"{base}/api/a11oy/v1/gdw/integrity/global"
    )
    health_url = f"{base}/api/a11oy/v1/gdw/healthz"
    last_error = "NOT_ATTEMPTED"
    last_health = None
    last_drain = None
    last_global_integrity = None
    last_supervisor_success = None
    stable_samples = 0

    try:
        initial_drain = request_json(
            "POST",
            drain_url,
            token=operator_token,
        )
        last_drain = initial_drain
        last_error = (
            "INITIAL_DRAIN_COMPLETE"
            if _drain_contract_is_valid(
                initial_drain,
                database_generation_id,
            )
            else "INITIAL_DRAIN_INCOMPLETE"
        )
    except Exception as exc:
        _reraise_hard(exc)
        last_error = f"INITIAL_DRAIN_{type(exc).__name__}"

    for _attempt in range(1, attempts + 1):
        try:
            health = request_json(
                "GET", health_url, attempts=_POLL_ATTEMPTS
            )
            _managed_health(health)
            last_health = health
            global_integrity = request_json(
                "GET",
                global_integrity_url,
                token=operator_token,
                attempts=_POLL_ATTEMPTS,
            )
            last_global_integrity = global_integrity
            if (
                source_sha is not None
                and recovery_evidence is not None
                and recovery_evidence.get("calls", 0) < 8
                and not _global_integrity_is_complete(
                    global_integrity,
                    database_generation_id,
                )
                and global_integrity.get("pending_effects", 0) > 0
                and global_integrity.get("claimed_effects") == 0
                and global_integrity.get("dead_letter_effects") == 0
                and global_integrity.get("invalid_effect_bindings") == 0
                and global_integrity.get("invalid_exported_artifacts") == 0
            ):
                recovery = _recover_transient_effects(
                    base=base,
                    operator_token=operator_token,
                    source_sha=source_sha,
                    database_generation_id=database_generation_id,
                    evidence=recovery_evidence,
                )
                if recovery.get("status") == "RESCHEDULED":
                    stable_samples = 0
                    last_supervisor_success = None
                    last_error = "TRANSIENT_EFFECTS_RESCHEDULED"
                    _sleep(delay_seconds)
                    continue
            supervisor_success = str(
                (
                    (health.get("persistence") or {})
                    .get("drain", {})
                    .get("last_success_at")
                    or ""
                )
            )
            if not (
                _health_is_write_ready(health, database_generation_id)
                and _global_integrity_is_complete(
                    global_integrity,
                    database_generation_id,
                )
                and supervisor_success
            ):
                stable_samples = 0
                last_supervisor_success = None
                last_error = "SUPERVISOR_NOT_QUIESCENT"
                _sleep(delay_seconds)
                continue
            if supervisor_success == last_supervisor_success:
                last_error = "AWAITING_SUCCESSIVE_SUPERVISOR_COMPLETION"
                _sleep(delay_seconds)
                continue
            last_supervisor_success = supervisor_success
            stable_samples += 1
            if stable_samples < required_stable_samples:
                last_error = "AWAITING_STABLE_SUPERVISOR_SAMPLES"
                _sleep(delay_seconds)
                continue

            confirmed_drain = request_json(
                "POST",
                drain_url,
                token=operator_token,
                attempts=_POLL_ATTEMPTS,
            )
            last_drain = confirmed_drain
            if _drain_contract_is_valid(
                confirmed_drain,
                database_generation_id,
            ):
                confirmed_integrity = request_json(
                    "GET",
                    global_integrity_url,
                    token=operator_token,
                    attempts=_POLL_ATTEMPTS,
                )
                last_global_integrity = confirmed_integrity
                if _global_integrity_is_complete(
                    confirmed_integrity,
                    database_generation_id,
                ):
                    return confirmed_drain, confirmed_integrity
            last_error = "CONFIRMATION_DRAIN_INCOMPLETE"
            stable_samples = 0
            last_supervisor_success = None
        except Exception as exc:
            _reraise_hard(exc)
            last_error = f"CONVERGENCE_{type(exc).__name__}"
            stable_samples = 0
            last_supervisor_success = None
        _sleep(delay_seconds)

    safe_state = _safe_convergence_state(
        reason=last_error,
        health=last_health,
        drain=last_drain,
        global_integrity=last_global_integrity,
        stable_samples=stable_samples,
    )
    raise RuntimeError(
        "GDW protected drain did not converge: "
        + json.dumps(safe_state, sort_keys=True)
    )


def _session_sha256(session: dict) -> str:
    return hashlib.sha256(
        json.dumps(
            session,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
    ).hexdigest()


def prove_restart(
    *,
    api,
    repo_id: str,
    base: str,
    source_sha: str,
    operator_token: str,
    session_id: str,
    attempts: int = 120,
    delay_seconds: float = 5,
) -> dict:
    """Restart the Space and prove GDW state and artifacts survived.

    Library-only (the admitted CLI never restarts from the GDW proof); still
    scoped to exactly ``SZLHOLDINGS/a11oy`` and the canonical origin.
    """

    bounds.require_canonical_space(repo_id)
    bounds.require_canonical_origin(base)

    if (
        not session_id
        or len(session_id) > 128
        or any(
            ch not in "abcdefghijklmnopqrstuvwxyz0123456789-_."
            for ch in session_id
        )
    ):
        raise RuntimeError("GDW restart session identity is invalid")

    health_url = f"{base}/api/a11oy/v1/gdw/healthz"
    global_integrity_url = (
        f"{base}/api/a11oy/v1/gdw/integrity/global"
    )
    owner_integrity_url = f"{base}/api/a11oy/v1/gdw/integrity"
    session_url = f"{base}/api/a11oy/v1/gdw/sessions/{session_id}"
    before_health = request_json("GET", health_url)
    before_global = request_json(
        "GET",
        global_integrity_url,
        token=operator_token,
    )
    before_session = request_json(
        "GET",
        session_url,
        token=operator_token,
    )
    before_persistence = before_health.get("persistence") or {}
    before_storage = before_persistence.get("storage") or {}
    database_generation_id = before_storage.get("database_generation_id")
    before_prepared_at = str(
        before_persistence.get("prepared_at") or ""
    )
    if (
        not before_prepared_at
        or not _health_is_write_ready(
            before_health,
            database_generation_id,
        )
        or not _global_integrity_is_complete(
            before_global,
            database_generation_id,
        )
        or before_session.get("database_generation_id")
        != database_generation_id
    ):
        raise RuntimeError("GDW pre-restart contract is incomplete")
    before_session_sha256 = _session_sha256(before_session)

    restart = api.restart_space(repo_id=repo_id, factory_reboot=False)
    stage = getattr(getattr(restart, "runtime", None), "stage", None)
    stage = getattr(stage, "value", stage)
    _sleep(max(10, delay_seconds))

    after_health = None
    last_error = "NOT_OBSERVED"
    for _attempt in range(1, attempts + 1):
        try:
            build_info = request_json(
                "GET",
                f"{base}/api/build-info",
                attempts=_POLL_ATTEMPTS,
            )
            revision = str(
                (build_info.get("build") or {}).get("revision") or ""
            ).lower()
            candidate = request_json(
                "GET", health_url, attempts=_POLL_ATTEMPTS
            )
            _managed_health(candidate)
            persistence = candidate.get("persistence") or {}
            storage = persistence.get("storage") or {}
            if (
                revision == source_sha
                and str(persistence.get("prepared_at") or "")
                and persistence.get("prepared_at") != before_prepared_at
                and storage.get("database_generation_id")
                == database_generation_id
            ):
                after_health = candidate
                break
            last_error = "RESTART_IDENTITY_NOT_CHANGED"
        except Exception as exc:
            _reraise_hard(exc)
            last_error = type(exc).__name__
        _sleep(delay_seconds)
    if after_health is None:
        raise RuntimeError(
            f"GDW restart was not observed: {last_error}"
        )

    _drain, after_global = _prove_drain_convergence(
        base=base,
        operator_token=operator_token,
        database_generation_id=database_generation_id,
        attempts=attempts,
        delay_seconds=delay_seconds,
    )
    after_owner = request_json(
        "GET",
        owner_integrity_url,
        token=operator_token,
    )
    after_session = request_json(
        "GET",
        session_url,
        token=operator_token,
    )
    after_session_sha256 = _session_sha256(after_session)
    if (
        after_owner.get("ok") is not True
        or after_owner.get("database_generation_id")
        != database_generation_id
        or after_owner.get("journal_mode") != "DELETE"
        or after_owner.get("pending_effects") != 0
        or after_owner.get("invalid_effect_bindings") != 0
        or after_owner.get("invalid_exported_artifacts") != 0
        or after_session.get("database_generation_id")
        != database_generation_id
        or after_session_sha256 != before_session_sha256
    ):
        raise RuntimeError("GDW post-restart persistence contract failed")

    return {
        "schema": "szl.hf-gdw-restart-proof/v1",
        "restart_requested": True,
        "restart_response_stage": str(stage or "UNKNOWN"),
        "source_revision": source_sha,
        "database_generation_id": database_generation_id,
        "before_prepared_at": before_prepared_at,
        "after_prepared_at": (
            (after_health.get("persistence") or {}).get("prepared_at")
        ),
        "session_sha256": after_session_sha256,
        "global_integrity": {
            "ok": True,
            "pending_proofs": after_global["pending_proofs"],
            "pending_effects": after_global["pending_effects"],
            "claimed_effects": after_global["claimed_effects"],
            "dead_letter_effects": after_global[
                "dead_letter_effects"
            ],
            "invalid_effect_bindings": after_global[
                "invalid_effect_bindings"
            ],
            "invalid_exported_artifacts": after_global[
                "invalid_exported_artifacts"
            ],
            "invalid_recovery_audits": after_global[
                "invalid_recovery_audits"
            ],
        },
        "credential_values_recorded": False,
    }


def prove_signed_receipt(
    *,
    base: str,
    operator_token: str,
    source_sha: str,
    database_generation_id: str,
    recovery_evidence: dict,
) -> dict:
    """Write one proof-tagged audit record and verify its pinned signature.

    The only GDW write that yields a DSSE-signed record is the governed
    transient-effect recovery audit. After drain convergence it is issued
    once with a ``gdw-proof-`` idempotency key (so a retry replays instead of
    duplicating), must be written in namespace ``a11oy``, must be
    ``SIGNED_KHIPU_DSSE``, and its signature must verify against
    ``ayllu/keys/council-runtime-2026-07-21.pub``. Unsigned or mismatched
    receipts fail closed (``RECEIPT_UNSIGNED`` / ``RECEIPT_SIGNATURE_INVALID``).
    """

    report = _recover_transient_effects(
        base=base,
        operator_token=operator_token,
        source_sha=source_sha,
        database_generation_id=database_generation_id,
        evidence=recovery_evidence,
        recovery_prefix=PROOF_RECOVERY_PREFIX,
    )
    receipt = report.get("audit_receipt") or {}
    operator = receipt.get("operator") or {}
    if operator.get("namespace") != bounds.GDW_NAMESPACE:
        raise ProofBoundaryError("NAMESPACE_SCOPE_REJECTED")
    if receipt.get("receipt_status") != "SIGNED_KHIPU_DSSE":
        raise ProofBoundaryError("RECEIPT_UNSIGNED")
    verification = _verify_signed_envelope(receipt.get("dsse_envelope"))
    return {
        "recovery_id": receipt.get("recovery_id"),
        "status": report.get("status"),
        "namespace": operator.get("namespace"),
        "owner_id": operator.get("owner_id"),
        "receipt_status": receipt.get("receipt_status"),
        "receipt_sha256": receipt.get("receipt_sha256"),
        "chain_sha256": receipt.get("chain_sha256"),
        "sequence": receipt.get("sequence"),
        **verification,
    }


def _prove(
    *,
    origin: str,
    source_sha: str,
    operator_token: str,
    require_signed_receipt: bool = True,
) -> dict:
    if len(source_sha) != 40 or any(ch not in "0123456789abcdef" for ch in source_sha):
        raise ProofBoundaryError("INVALID_ARGUMENTS")
    if len(operator_token.encode("utf-8")) < 32:
        raise ProofBoundaryError("SETUP_REQUIRED")
    # Destination: exactly the canonical Space origin, compared exactly.
    base = bounds.require_canonical_origin(origin)
    health = None
    deployed_revision = ""
    last_error = None
    recovery_evidence = _new_recovery_evidence()
    for attempt in range(1, 121):
        try:
            build_info = request_json(
                "GET",
                f"{base}/api/build-info",
                attempts=_POLL_ATTEMPTS,
            )
            deployed_revision = str(
                (build_info.get("build") or {}).get("revision") or ""
            ).lower()
            if deployed_revision != source_sha:
                last_error = "SOURCE_REVISION_MISMATCH"
                _sleep(5)
                continue
            try:
                candidate = request_json(
                    "GET",
                    f"{base}/api/a11oy/v1/gdw/healthz",
                    attempts=_POLL_ATTEMPTS,
                )
            except Exception as health_exc:  # noqa: BLE001
                _reraise_hard(health_exc)
                candidate = {}
            if candidate:
                _managed_health(candidate)
            candidate_global = request_json(
                "GET",
                f"{base}/api/a11oy/v1/gdw/integrity/global",
                token=operator_token,
                attempts=_POLL_ATTEMPTS,
            )
            candidate_persistence = candidate.get("persistence") or {}
            candidate_storage = candidate_persistence.get("storage") or {}
            health_generation_id = str(
                candidate_storage.get("database_generation_id") or ""
            )
            candidate_generation_id = str(
                candidate_global.get("database_generation_id") or ""
            )
            if health_generation_id and (
                health_generation_id != candidate_generation_id
            ):
                last_error = "DATABASE_GENERATION_MISMATCH"
                _sleep(5)
                continue
            if (
                candidate.get("status") == "REAL"
                and candidate.get("write_ready") is True
                and candidate_storage.get("journal_mode_observed") == "DELETE"
                and _global_integrity_is_complete(
                    candidate_global,
                    candidate_generation_id,
                )
            ):
                health = candidate
                break
            if (
                recovery_evidence["calls"] < 8
                and re.fullmatch(
                    r"[0-9a-f]{32}",
                    candidate_generation_id,
                )
                is not None
                and candidate_global.get("ok") is True
                and candidate_global.get("sqlite_integrity") == "ok"
                and candidate_global.get("journal_mode") == "DELETE"
                and candidate_global.get("pending_proofs") == 0
                and candidate_global.get("pending_effects", 0) > 0
                and candidate_global.get("claimed_effects") == 0
                and candidate_global.get("dead_letter_effects") == 0
                and candidate_global.get("invalid_effect_bindings") == 0
                and candidate_global.get("invalid_exported_artifacts") == 0
                and candidate_global.get("invalid_recovery_audits") == 0
            ):
                recovery = _recover_transient_effects(
                    base=base,
                    operator_token=operator_token,
                    source_sha=source_sha,
                    database_generation_id=candidate_generation_id,
                    evidence=recovery_evidence,
                )
                last_error = f"RECOVERY_{recovery['status']}"
            else:
                last_error = json.dumps(
                    _safe_convergence_state(
                        reason="INITIAL_READINESS_NOT_CONVERGED",
                        health=candidate,
                        drain=None,
                        global_integrity=candidate_global,
                        stable_samples=0,
                    ),
                    sort_keys=True,
                )
        except Exception as exc:
            _reraise_hard(exc)
            last_error = type(exc).__name__
        _sleep(5)
    if health is None:
        raise RuntimeError(f"GDW health did not converge: {last_error}")

    request_id = f"promotion-{source_sha[:32]}"
    session_id = f"protected-promotion-{source_sha[:16]}"
    step = request_json(
        "POST",
        f"{base}/api/a11oy/v1/gdw/step",
        token=operator_token,
        headers={"X-Request-Id": request_id},
        json={
            "session_id": session_id,
            "request": "verify durable governed successor",
            "allowed_experts": ["planner", "auditor", "verifier"],
            "risk_budget": 0.1,
            "mode_hint": "auto",
            "dry_run": False,
        },
    )
    if (
        step.get("decision") != "ACCEPT"
        or step.get("receipt_status") != "UNSIGNED_ATOMIC"
        or step.get("proof", {}).get("status") != "OUTBOX_PENDING"
        or step.get("database_generation_id")
        != (health.get("persistence") or {})
        .get("storage", {})
        .get("database_generation_id")
    ):
        raise RuntimeError("GDW protected transition contract failed")

    database_generation_id = (
        (health.get("persistence") or {})
        .get("storage", {})
        .get("database_generation_id")
    )
    if (
        not isinstance(database_generation_id, str)
        or len(database_generation_id) != 32
        or any(
            ch not in "0123456789abcdef"
            for ch in database_generation_id
        )
    ):
        raise RuntimeError("GDW database generation is not canonical")
    drain, global_integrity = _prove_drain_convergence(
        base=base,
        operator_token=operator_token,
        database_generation_id=database_generation_id,
        source_sha=source_sha,
        recovery_evidence=recovery_evidence,
    )
    integrity = request_json(
        "GET",
        f"{base}/api/a11oy/v1/gdw/integrity",
        token=operator_token,
    )
    session = request_json(
        "GET",
        f"{base}/api/a11oy/v1/gdw/sessions/{session_id}",
        token=operator_token,
    )
    if (
        integrity.get("ok") is not True
        or integrity.get("journal_mode") != "DELETE"
        or session.get("database_generation_id")
        != (health.get("persistence") or {})
        .get("storage", {})
        .get("database_generation_id")
    ):
        raise RuntimeError("GDW live persistence contract failed")
    # Effect scope: the written session must live in the a11oy namespace.
    if "namespace" in session and session.get("namespace") != bounds.GDW_NAMESPACE:
        raise ProofBoundaryError("NAMESPACE_SCOPE_REJECTED")
    signed_receipt = None
    if require_signed_receipt:
        if session.get("namespace") != bounds.GDW_NAMESPACE:
            raise ProofBoundaryError("NAMESPACE_SCOPE_REJECTED")
        signed_receipt = prove_signed_receipt(
            base=base,
            operator_token=operator_token,
            source_sha=source_sha,
            database_generation_id=database_generation_id,
            recovery_evidence=recovery_evidence,
        )

    return {
        "schema": "szl.hf-gdw-live-proof/v1",
        "source_revision": source_sha,
        "runtime_source_revision": deployed_revision,
        "health": health,
        "transition": {
            "session_id": session_id,
            "decision": step["decision"],
            "receipt_status": step["receipt_status"],
            "proof_status": step["proof"]["status"],
            "replayed": bool(step.get("replayed")),
        },
        "drain": drain,
        "global_integrity": {
            "ok": True,
            "journal_mode": global_integrity["journal_mode"],
            "pending_proofs": global_integrity["pending_proofs"],
            "pending_effects": global_integrity["pending_effects"],
            "claimed_effects": global_integrity["claimed_effects"],
            "dead_letter_effects": global_integrity["dead_letter_effects"],
            "invalid_effect_bindings": global_integrity[
                "invalid_effect_bindings"
            ],
            "invalid_exported_artifacts": global_integrity[
                "invalid_exported_artifacts"
            ],
            "invalid_recovery_audits": global_integrity[
                "invalid_recovery_audits"
            ],
        },
        "transient_recovery": recovery_evidence,
        "namespace": session.get("namespace"),
        "signed_receipt": signed_receipt,
        "integrity": {
            "ok": True,
            "journal_mode": integrity["journal_mode"],
            "pending_effects": integrity["pending_effects"],
            "invalid_effect_bindings": integrity[
                "invalid_effect_bindings"
            ],
            "invalid_exported_artifacts": integrity[
                "invalid_exported_artifacts"
            ],
            "invalid_recovery_audits": integrity[
                "invalid_recovery_audits"
            ],
        },
        "credential_values_recorded": False,
    }


def prove(*, origin: str, source_sha: str, operator_token: str,
          require_signed_receipt: bool = True, managed_context: Any = None) -> dict:
    """Bind one proof to one independently verified managed authority context."""
    global _MANAGED_CONTEXT, _MANAGED_LATEST
    if _MANAGED_CONTEXT is not None:
        raise ProofBoundaryError("EFFECT_SCOPE_REJECTED")
    if managed_context is not None and managed_context.identity.get("source_revision") != source_sha:
        raise ProofBoundaryError("EFFECT_SCOPE_REJECTED")
    _MANAGED_CONTEXT, _MANAGED_LATEST = managed_context, None
    try:
        result = _prove(origin=origin, source_sha=source_sha, operator_token=operator_token,
                        require_signed_receipt=require_signed_receipt)
        if managed_context is not None:
            final_health = request_json("GET", bounds.CANONICAL_ORIGIN + GDW_PREFIX + "healthz",
                                        attempts=_POLL_ATTEMPTS)
            _managed_health(final_health)
            if _MANAGED_LATEST is None:
                raise ProofBoundaryError("EFFECT_SCOPE_REJECTED")
            result["managed_identity"] = dict(managed_context.identity)
            result["managed_admission"] = dict(_MANAGED_LATEST)
        return result
    finally:
        _MANAGED_CONTEXT, _MANAGED_LATEST = None, None


SCHEMA = "szl.hf-gdw-live-proof/v1"
# Existing live GDW bearer. Explicit managed mode also uses HF_TOKEN through
# the fixed immutable-admission reader; neither credential enters the report.
GDW_TOKEN_NAME = "GDW_OPERATOR_TOKEN"
MAX_REPORT_BYTES = 12 * 1024
MAX_UPSTREAM_TERMINAL_AGE_SECONDS = 120


def _terminal_series_a_evidence(path: str | None, *, source: str,
                                run_context: str | None) -> dict:
    """Accept only a fresh same-run failure after an owned canonical restart.

    This local report can stop redundant polling, never admit a live proof.
    Missing or inadmissible evidence leaves all existing GDW checks active.
    """

    if not path or not run_context or bounds.WORKFLOW_RUN_CONTEXT.fullmatch(run_context) is None:
        return {}

    def unique_object(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("duplicate key")
            value[key] = item
        return value

    def reject_constant(_value):
        raise ValueError("non-JSON constant")

    try:
        # Reject a FIFO/device before reading: this local evidence check runs
        # before the GDW transport exists and must not create a blocking wait.
        descriptor = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > MAX_REPORT_BYTES:
                return {}
            raw = os.read(descriptor, MAX_REPORT_BYTES + 1)
        finally:
            os.close(descriptor)
        if len(raw) > MAX_REPORT_BYTES:
            return {}
        report = json.loads(raw, object_pairs_hook=unique_object, parse_constant=reject_constant)
        if not isinstance(report, dict) or any((
            report.get("schema") != "szl.series-a-restart-proof/v1",
            report.get("status") != "FAIL",
            report.get("ok") is not False,
            report.get("diagnostic_code") != "PROVIDER_TERMINAL_STATE",
            report.get("repo_id") != bounds.CANONICAL_SPACE,
            report.get("requested_repo_id_admitted") is not True,
            report.get("origin") != bounds.CANONICAL_ORIGIN,
            report.get("source_revision") != source,
            report.get("workflow_run_context") != run_context,
            report.get("secret_values_recorded") is not False,
            report.get("credential_authority_state") != "UNKNOWN",
        )):
            return {}
        evidence = report.get("evidence")
        terminal = evidence.get("terminal_provider_state") if isinstance(evidence, dict) else None
        if not isinstance(terminal, dict):
            return {}
        phase = terminal.get("phase")
        if phase not in ("activation", "durability") or any((
            terminal.get("stage") not in bounds.TERMINAL_PROVIDER_ERROR_STAGES,
            terminal.get("expected_source_revision") != source,
            terminal.get("runtime_source_verified") is not False,
            type(terminal.get("attempt")) is not int,
        )):
            return {}
        if not 1 <= terminal["attempt"] <= 90:
            return {}
        control = evidence.get(f"{phase}_restart_control")
        if not isinstance(control, dict) or any((
            control.get("phase") != phase,
            control.get("pause_requested") is not True,
            control.get("pause_confirmed") is not True,
            control.get("confirmed_pause_stage") != "PAUSED",
            control.get("restart_requested") is not True,
            control.get("writer_overlap_prevented") is not True,
            evidence.get(f"{phase}_restart_requested") is not True,
        )):
            return {}
        observed = datetime.fromisoformat(terminal["observed_at"])
        generated = datetime.fromisoformat(report["generated_at"])
        now = datetime.now(timezone.utc)
        if observed.utcoffset() is None or generated.utcoffset() is None:
            return {}
        if not observed <= generated <= now or not 0 <= (now - observed).total_seconds() <= MAX_UPSTREAM_TERMINAL_AGE_SECONDS:
            return {}
        return {
            key: terminal[key] for key in (
                "stage", "phase", "attempt", "observed_at",
                "expected_source_revision", "runtime_source_verified",
            )
        } | {"observed_at": observed.astimezone(timezone.utc).isoformat()}
    except (OSError, ValueError, TypeError, KeyError, RecursionError, OverflowError):
        return {}


def _summary(result: dict) -> dict:
    health = result.get("health") or {}
    storage = (health.get("persistence") or {}).get("storage") or {}
    return bounds.bounded_report({
        "runtime_source_revision": result.get("runtime_source_revision"),
        "database_generation_id": storage.get("database_generation_id"),
        "namespace": result.get("namespace"),
        "transition": result.get("transition"),
        "drain": {
            key: (result.get("drain") or {}).get(key)
            for key in ("failed", "pending_effects", "legacy_pending_proofs",
                        "integrity_ok", "database_generation_id")
        },
        "global_integrity": result.get("global_integrity"),
        "integrity": result.get("integrity"),
        "transient_recovery": {
            key: (result.get("transient_recovery") or {}).get(key)
            for key in ("calls", "applied_rounds", "rescheduled_effects",
                        "replayed_calls", "last_status")
        },
        "signed_receipt": result.get("signed_receipt"),
        **({"managed_identity": result["managed_identity"],
            "managed_admission": result["managed_admission"]}
           if "managed_identity" in result else {}),
    })


def _report(*, source: str, status: str, code: str, evidence: dict,
            missing: list | None = None, deadline_seconds: int | None = None) -> dict:
    report = {
        "schema": SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "ok": status == "PASS",
        "state": "PROVEN" if status == "PASS" else (
            "SETUP_REQUIRED" if code == "SETUP_REQUIRED" else "FAILED"),
        "diagnostic_code": code,
        "repo_id": bounds.CANONICAL_SPACE,
        "origin": bounds.CANONICAL_ORIGIN,
        "namespace": bounds.GDW_NAMESPACE,
        "source_revision": source if re.fullmatch(r"[0-9a-f]{40}", source) else "UNVALIDATED",
        "evidence": evidence,
        "credential_authority_state": "VERIFIED" if status == "PASS" else "UNKNOWN",
        "credential_values_recorded": False,
    }
    if missing is not None:
        report["missing_secret_names"] = list(missing)
    if deadline_seconds is not None:
        report["bounds"] = bounds.bounds_record(deadline_seconds=deadline_seconds)
    return report


def main(argv: list | None = None, *, transport_factory: Any = None) -> int:
    parser = argparse.ArgumentParser(
        description="Bounded live GDW write, drain, and pinned-receipt proof (a11oy namespace only)."
    )
    parser.add_argument("--origin", default=bounds.CANONICAL_ORIGIN)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--managed-acquisition", type=Path)
    parser.add_argument("--deadline-seconds", type=int, default=DEFAULT_DEADLINE_SECONDS)
    parser.add_argument("--run-context", help="GitHub workflow run ID and attempt, ID:ATTEMPT")
    parser.add_argument("--series-a-proof", help="Bounded same-job Series-A proof report")
    args = parser.parse_args(argv)
    source = str(args.source_sha or "").strip().lower()
    token = ""
    managed_context = None
    failure_evidence: dict[str, Any] = {}
    deadline_seconds = min(max(1, int(args.deadline_seconds)), MAX_DEADLINE_SECONDS)
    try:
        if re.fullmatch(r"[0-9a-f]{40}", source) is None:
            raise ProofBoundaryError("INVALID_ARGUMENTS")
        bounds.require_canonical_origin(args.origin)
        if args.run_context is not None and bounds.WORKFLOW_RUN_CONTEXT.fullmatch(args.run_context) is None:
            raise ProofBoundaryError("INVALID_ARGUMENTS")
        terminal = _terminal_series_a_evidence(
            args.series_a_proof, source=source, run_context=args.run_context,
        )
        if terminal:
            failure_evidence["terminal_provider_state"] = terminal
            raise ProofBoundaryError("PROVIDER_TERMINAL_STATE")
        token = os.environ.get(GDW_TOKEN_NAME, "")
        if len(token.strip().encode("utf-8")) < 32:
            report = _report(source=source, status="FAIL", code="SETUP_REQUIRED",
                             evidence={}, missing=[GDW_TOKEN_NAME])
            token = ""
            code = 1
        else:
            deadline = time.monotonic() + deadline_seconds
            if args.managed_acquisition is not None:
                managed_context = load_managed_proof_context(
                    args.managed_acquisition, source_revision=source, deadline=deadline)
                if time.monotonic() >= deadline:
                    raise ProofBoundaryError("DEADLINE_EXHAUSTED")
            make_transport = transport_factory or bounds.BoundedTransport
            configure_transport(make_transport(deadline_seconds=(deadline - time.monotonic())
                                if managed_context is not None else deadline_seconds))
            result = prove(origin=bounds.CANONICAL_ORIGIN, source_sha=source,
                           operator_token=token, require_signed_receipt=True,
                           **({"managed_context": managed_context} if managed_context is not None else {}))
            report = _report(source=source, status="PASS", code="LIVE_PROOF_PASSED",
                             evidence=_summary(result), deadline_seconds=deadline_seconds)
            code = 0
    except Exception as exc:  # noqa: BLE001 - every failure is a fixed code
        report = _report(
            source=source, status="FAIL",
            code=bounds.diagnostic_code(exc, "GDW_CONTRACT_FAILED"),
            evidence=failure_evidence, deadline_seconds=deadline_seconds,
        )
        code = 1
    finally:
        configure_transport(None)
        if managed_context is not None:
            try:
                managed_context.close()
            except Exception:
                report = _report(source=source, status="FAIL", code="EFFECT_SCOPE_REJECTED", evidence={})
                code = 1
    if args.run_context is not None and bounds.WORKFLOW_RUN_CONTEXT.fullmatch(args.run_context):
        report["workflow_run_context"] = args.run_context
    encoded = json.dumps(report, sort_keys=True)
    if (token and token in encoded) or len(encoded.encode("utf-8")) > MAX_REPORT_BYTES:
        report = _report(source=source, status="FAIL", code="UNEXPECTED_FAILURE", evidence={})
        code = 1
    output = Path(args.output)
    encoded = bounds.write_json(output, report)
    print(encoded, end="")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
