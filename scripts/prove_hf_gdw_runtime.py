#!/usr/bin/env python3
"""Exercise the exact live GDW successor without recording bearer material."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import sys
from pathlib import Path


_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(_REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPOSITORY_ROOT))

import szl_dsse


# Statuses that describe a runtime that is not ready to answer *yet* rather
# than a runtime that answered with a contract violation. A freshly deployed
# docker Space is still booting (502/503/504), and the GDW successor rejects
# admission with 429 while an owner/global ceiling is momentarily saturated and
# the outbox drain / retention compactor has not yet released the slots.
# Every one of these is a capacity or readiness condition, never an integrity
# verdict: integrity verdicts arrive as HTTP 200 bodies (or as 4xx contract
# errors) and are still asserted, unretried, by the callers below.
_TRANSIENT_HTTP_STATUSES = frozenset({408, 425, 429, 502, 503, 504})
_REQUEST_ATTEMPTS = 6
# Calls made from inside a convergence loop already have an outer retry
# budget, so they only absorb a single hiccup and let the loop re-poll.
_POLL_ATTEMPTS = 2
_REQUEST_BACKOFF_SECONDS = 2.0
_REQUEST_BACKOFF_CAP_SECONDS = 30.0
_RETRY_AFTER_CAP_SECONDS = 60.0


class TransientRequestError(RuntimeError):
    """A readiness/capacity condition that survived the whole retry budget."""


def _retry_after_seconds(headers) -> float | None:
    try:
        raw = headers.get("Retry-After") if headers is not None else None
    except AttributeError:
        raw = None
    if raw is None:
        return None
    try:
        seconds = float(str(raw).strip())
    except (TypeError, ValueError):
        return None
    if seconds < 0:
        return None
    return min(seconds, _RETRY_AFTER_CAP_SECONDS)


def _backoff_seconds(attempt: int) -> float:
    return min(
        _REQUEST_BACKOFF_CAP_SECONDS,
        _REQUEST_BACKOFF_SECONDS * (2 ** (attempt - 1)),
    )


def request_json(
    method: str,
    url: str,
    *,
    token: str | None = None,
    attempts: int = _REQUEST_ATTEMPTS,
    **kwargs,
):
    """Perform one JSON call, retrying only readiness/capacity conditions.

    Mutating calls in this proof carry an ``X-Request-Id`` idempotency key, so
    a retried POST is replayed by the runtime instead of duplicated. Any
    non-transient status (contract, authorization, lifecycle, or fail-closed
    500 responses) is raised immediately and unchanged.
    """

    headers = dict(kwargs.pop("headers", {}))
    payload = kwargs.pop("json", None)
    if kwargs:
        raise TypeError("unsupported request options")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    budget = max(1, int(attempts))
    last_transient = ""
    for attempt in range(1, budget + 1):
        request = Request(
            url,
            data=data,
            headers=headers,
            method=method,
        )
        try:
            with urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            response_body = exc.read().decode("utf-8", errors="replace")
            detail = f"HTTP {exc.code} {method} {url}: {response_body[:2048]}"
            if exc.code not in _TRANSIENT_HTTP_STATUSES:
                raise RuntimeError(detail) from exc
            last_transient = detail
            delay = _retry_after_seconds(getattr(exc, "headers", None))
        except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            last_transient = (
                f"{type(exc).__name__} {method} {url}"
            )
            delay = None
        if attempt >= budget:
            break
        time.sleep(delay if delay is not None else _backoff_seconds(attempt))
    raise TransientRequestError(
        f"transient condition persisted across {budget} attempts: "
        f"{last_transient}"
    )


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


def _recover_transient_effects(
    *,
    base: str,
    operator_token: str,
    source_sha: str,
    database_generation_id: str,
    evidence: dict,
) -> dict:
    call_number = evidence["calls"] + 1
    evidence["calls"] = call_number
    recovery_id = (
        f"gdw-recovery-{source_sha[:12]}-"
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
    signature_verification = (
        szl_dsse.verify_envelope(envelope)
        if envelope_signed is True and type(envelope) is dict
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
            == szl_dsse.KHIPU_PAYLOAD_TYPE
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
        last_error = f"INITIAL_DRAIN_{type(exc).__name__}"

    for _attempt in range(1, attempts + 1):
        try:
            health = request_json(
                "GET", health_url, attempts=_POLL_ATTEMPTS
            )
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
                    time.sleep(delay_seconds)
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
                time.sleep(delay_seconds)
                continue
            if supervisor_success == last_supervisor_success:
                last_error = "AWAITING_SUCCESSIVE_SUPERVISOR_COMPLETION"
                time.sleep(delay_seconds)
                continue
            last_supervisor_success = supervisor_success
            stable_samples += 1
            if stable_samples < required_stable_samples:
                last_error = "AWAITING_STABLE_SUPERVISOR_SAMPLES"
                time.sleep(delay_seconds)
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
            last_error = f"CONVERGENCE_{type(exc).__name__}"
            stable_samples = 0
            last_supervisor_success = None
        time.sleep(delay_seconds)

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
    """Restart the Space and prove GDW state and artifacts survived."""

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
    time.sleep(max(10, delay_seconds))

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
            last_error = type(exc).__name__
        time.sleep(delay_seconds)
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


def prove(*, origin: str, source_sha: str, operator_token: str) -> dict:
    if len(source_sha) != 40 or any(ch not in "0123456789abcdef" for ch in source_sha):
        raise RuntimeError("source SHA must be canonical lowercase hexadecimal")
    if len(operator_token.encode("utf-8")) < 32:
        raise RuntimeError("GDW_OPERATOR_TOKEN is unavailable")
    base = origin.rstrip("/")
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
                time.sleep(5)
                continue
            try:
                candidate = request_json(
                    "GET",
                    f"{base}/api/a11oy/v1/gdw/healthz",
                    attempts=_POLL_ATTEMPTS,
                )
            except Exception:
                candidate = {}
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
                time.sleep(5)
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
            last_error = type(exc).__name__
        time.sleep(5)
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--origin", required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--output")
    parser.add_argument("--restart-repo-id")
    args = parser.parse_args()
    report = prove(
        origin=args.origin,
        source_sha=args.source_sha,
        operator_token=os.environ.get("GDW_OPERATOR_TOKEN", ""),
    )
    if args.restart_repo_id:
        hf_token = os.environ.get("HF_TOKEN", "")
        if not hf_token:
            raise RuntimeError("HF_TOKEN is unavailable for restart proof")
        from huggingface_hub import HfApi

        report["restart"] = prove_restart(
            api=HfApi(token=hf_token),
            repo_id=args.restart_repo_id,
            base=args.origin.rstrip("/"),
            source_sha=args.source_sha,
            operator_token=os.environ.get("GDW_OPERATOR_TOKEN", ""),
            session_id=report["transition"]["session_id"],
        )
    encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
