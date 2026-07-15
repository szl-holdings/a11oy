#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Fail-closed formal-conjecture attempt and kernel-receipt ledger.

Taxonomy home: services/provenance.  This module does not execute a prover.  It
stores bounded declarations and formal artifacts, then accepts only a DSSE
kernel-result receipt that verifies against the published SZL cosign public
key and binds the exact server-computed statement and artifact hashes.

``KERNEL_ACCEPTED`` means only that the configured external Lean 4 checker
reported exit code zero with no sorries or unsafe declarations.  It does not
promote a conjecture, add a locked formula, establish novelty, or authorize a
publication claim.  Reads never mint receipts; every successful write appends
one hash-chained, honestly unsigned DSSE-shaped Khipu event.
"""

import base64
import binascii
import datetime
import hashlib
import json
import os
import re
import threading
from pathlib import Path
from typing import Any, Mapping


ATTEMPT_SCHEMA = "szl.formal-conjecture-attempt/v1"
KERNEL_SCHEMA = "szl.formal-kernel-result/v1"
KERNEL_PAYLOAD_TYPE = "application/vnd.szl.formal-kernel-result+json"
LOCAL_PAYLOAD_TYPE = "application/vnd.szl.khipu+json"

DECLARED = "DECLARED"
KERNEL_UNCHECKED = "KERNEL_UNCHECKED"
KERNEL_ACCEPTED = "KERNEL_ACCEPTED"
KERNEL_REJECTED = "KERNEL_REJECTED"
UNAVAILABLE = "UNAVAILABLE"
STATES = (DECLARED, KERNEL_UNCHECKED, KERNEL_ACCEPTED, KERNEL_REJECTED, UNAVAILABLE)

MAX_BODY_BYTES = 384 * 1024
MAX_STATEMENT_CHARS = 32 * 1024
MAX_ARTIFACT_CHARS = 256 * 1024
MAX_TITLE_CHARS = 256
MAX_BRAIN_REFS = 64
MAX_EVENTS = 2048
MAX_LEDGER_BYTES = 8 * 1024 * 1024
GENESIS = "0" * 64
LOCKED_SET = ("F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22")
ARTIFACT_FORMATS = ("LEAN4", "COQ", "ISABELLE", "TEXT")
SOURCE_KINDS = ("OPERATOR_DECLARED", "CONJECTURE_FACTORY_CACHE")

_STATE_PATH = Path(
    os.environ.get(
        "A11OY_FORMAL_CONJECTURE_LAB_PATH",
        str(Path(__file__).resolve().parent / ".a11oy-state" / "formal-conjecture-lab.jsonl"),
    )
)
_WRITE_LOCK = threading.RLock()
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")


class ContractError(ValueError):
    """The caller supplied a malformed or hidden-field-bearing contract."""


class StateConflict(RuntimeError):
    """The requested transition conflicts with the recorded attempt state."""


class LabUnavailable(RuntimeError):
    """A required local integrity or public-key verification boundary is absent."""


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def _sha256(value: Any) -> str:
    raw = value.encode("utf-8") if isinstance(value, str) else _canonical_bytes(value)
    return hashlib.sha256(raw).hexdigest()


def _sha3(value: Any) -> str:
    return hashlib.sha3_256(_canonical_bytes(value)).hexdigest()


def _mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ContractError(f"{name} must be one JSON object")
    return value


def _strict_keys(value: Mapping[str, Any], expected: set[str], name: str) -> None:
    actual = set(value)
    if actual != expected:
        raise ContractError(
            f"{name} fields must be exactly {sorted(expected)}; got {sorted(actual)}"
        )


def _text(value: Any, name: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{name} must be a non-empty string")
    clean = value.strip()
    if len(clean) > maximum:
        raise ContractError(f"{name} exceeds {maximum} characters")
    if "\x00" in clean:
        raise ContractError(f"{name} contains a NUL byte")
    return clean


def _hex64(value: Any, name: str) -> str:
    if not isinstance(value, str) or not _HEX64_RE.fullmatch(value):
        raise ContractError(f"{name} must be one lowercase SHA-256 hex digest")
    return value


def _parse_brain_refs(value: Any) -> list[str]:
    if not isinstance(value, list) or len(value) > MAX_BRAIN_REFS:
        raise ContractError(f"brain_node_ids must be an array of at most {MAX_BRAIN_REFS} ids")
    refs: list[str] = []
    for index, item in enumerate(value):
        ref = _text(item, f"brain_node_ids[{index}]", 256)
        if ref in refs:
            raise ContractError("brain_node_ids must not contain duplicates")
        refs.append(ref)
    return refs


def _factory_crosscheck(conjecture_id: str, title: str, statement: str) -> dict[str, Any]:
    """Cross-check only the on-disk factory cache; this never performs a fetch."""
    try:
        import szl_conjecture_factory

        item = szl_conjecture_factory.load_conjecture(conjecture_id, force_refresh=False)
    except Exception as exc:
        raise LabUnavailable(
            f"conjecture factory cache unavailable ({type(exc).__name__}); no source match assumed"
        ) from exc
    if item is None:
        raise LabUnavailable("conjecture id is absent from the local factory cache")
    if str(item.get("statement") or "").strip() != statement:
        raise ContractError("statement does not exactly match the cached conjecture statement")
    cached_title = str(item.get("title") or "").strip()
    if cached_title and cached_title != title:
        raise ContractError("title does not exactly match the cached conjecture title")
    return {
        "factory_receipt_id": item.get("receipt", {}).get("receipt_id"),
        "factory_envelope_status": item.get("_envelope_status"),
        "factory_statement_sha256": _sha256(statement),
        "crosscheck": "EXACT_LOCAL_CACHE_MATCH",
    }


def normalize_attempt_request(request: Mapping[str, Any]) -> dict[str, Any]:
    obj = _mapping(request, "attempt")
    expected = {
        "schema_version", "source_kind", "conjecture_id", "title", "statement",
        "artifact", "artifact_format", "brain_node_ids",
    }
    _strict_keys(obj, expected, "attempt")
    if obj.get("schema_version") != ATTEMPT_SCHEMA:
        raise ContractError(f"schema_version must be {ATTEMPT_SCHEMA}")
    source_kind = _text(obj.get("source_kind"), "source_kind", 64)
    if source_kind not in SOURCE_KINDS:
        raise ContractError(f"source_kind must be one of {SOURCE_KINDS}")
    conjecture_id = _text(obj.get("conjecture_id"), "conjecture_id", 128)
    if not _ID_RE.fullmatch(conjecture_id):
        raise ContractError("conjecture_id contains unsupported characters")
    title = _text(obj.get("title"), "title", MAX_TITLE_CHARS)
    statement = _text(obj.get("statement"), "statement", MAX_STATEMENT_CHARS)
    artifact_value = obj.get("artifact")
    if artifact_value is None:
        artifact = None
    elif isinstance(artifact_value, str):
        artifact = artifact_value
        if len(artifact) > MAX_ARTIFACT_CHARS:
            raise ContractError(f"artifact exceeds {MAX_ARTIFACT_CHARS} characters")
        if "\x00" in artifact:
            raise ContractError("artifact contains a NUL byte")
        if not artifact.strip():
            artifact = None
    else:
        raise ContractError("artifact must be a string or null")
    artifact_format = _text(obj.get("artifact_format"), "artifact_format", 32)
    if artifact_format not in ARTIFACT_FORMATS:
        raise ContractError(f"artifact_format must be one of {ARTIFACT_FORMATS}")
    if artifact is None and artifact_format != "TEXT":
        raise ContractError("artifact_format must be TEXT when artifact is null")
    brain_refs = _parse_brain_refs(obj.get("brain_node_ids"))
    source_crosscheck = None
    if source_kind == "CONJECTURE_FACTORY_CACHE":
        source_crosscheck = _factory_crosscheck(conjecture_id, title, statement)
    return {
        "schema_version": ATTEMPT_SCHEMA,
        "source_kind": source_kind,
        "conjecture_id": conjecture_id,
        "title": title,
        "statement": statement,
        "statement_sha256": _sha256(statement),
        "artifact": artifact,
        "artifact_sha256": _sha256(artifact) if artifact is not None else None,
        "artifact_format": artifact_format,
        "brain_node_ids": brain_refs,
        "brain_refs_evidence": "DECLARED_REFERENCES_ONLY",
        "source_crosscheck": source_crosscheck,
    }


def _read_events() -> list[dict[str, Any]]:
    if not _STATE_PATH.exists():
        return []
    try:
        if _STATE_PATH.stat().st_size > MAX_LEDGER_BYTES:
            raise LabUnavailable("formal lab ledger exceeds its bounded size")
        lines = _STATE_PATH.read_text(encoding="utf-8").splitlines()
    except LabUnavailable:
        raise
    except OSError as exc:
        raise LabUnavailable(f"formal lab ledger unreadable ({type(exc).__name__})") from exc
    if len(lines) > MAX_EVENTS:
        raise LabUnavailable("formal lab ledger exceeds its bounded event count")
    events: list[dict[str, Any]] = []
    try:
        for line in lines:
            if line.strip():
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise ValueError("ledger event is not an object")
                events.append(value)
    except (json.JSONDecodeError, ValueError) as exc:
        raise LabUnavailable("formal lab ledger is structurally invalid") from exc
    verdict = verify_event_chain(events)
    if not verdict["valid"]:
        raise LabUnavailable(f"formal lab ledger chain invalid at event {verdict['broken_at']}")
    return events


def verify_event_chain(events: list[dict[str, Any]]) -> dict[str, Any]:
    prev = GENESIS
    for index, event in enumerate(events):
        try:
            payload = event["payload"]
            receipt = event["receipt"]["khipu"]
            dsse = event["receipt"]["dsse"]
            body = {key: receipt[key] for key in (
                "organ", "ns", "seq", "action", "payload_digest", "ts", "prev"
            )}
            receipt_core = {**body, "digest": receipt["digest"],
                            "signature": receipt["signature"],
                            "chain_verified": receipt["chain_verified"]}
            dsse_payload = base64.b64decode(dsse["payload"], validate=True)
            ok = (
                receipt["seq"] == index
                and receipt["prev"] == prev
                and receipt["payload_digest"] == _sha3(payload)
                and receipt["digest"] == _sha3(body)
                and receipt["signature"] == "UNSIGNED"
                and receipt["chain_verified"] is True
                and dsse["payloadType"] == LOCAL_PAYLOAD_TYPE
                and dsse["signatures"] == []
                and dsse.get("signed") is False
                and dsse_payload == _canonical_bytes(receipt_core)
            )
        except (KeyError, TypeError, ValueError, binascii.Error):
            ok = False
        if not ok:
            return {"valid": False, "depth": len(events), "broken_at": index}
        prev = receipt["digest"]
    return {"valid": True, "depth": len(events), "broken_at": None, "head": prev}


def _unsigned_dsse(receipt: dict[str, Any]) -> dict[str, Any]:
    return {
        "payloadType": LOCAL_PAYLOAD_TYPE,
        "payload": base64.b64encode(_canonical_bytes(receipt)).decode("ascii"),
        "signatures": [],
        "signed": False,
        "honesty": "UNSIGNED - this local write receipt is hash-chained; no secret or signature fabricated.",
    }


def _append_event(ns: str, action: str, payload: dict[str, Any]) -> dict[str, Any]:
    with _WRITE_LOCK:
        events = _read_events()
        if len(events) >= MAX_EVENTS:
            raise LabUnavailable("formal lab event bound reached; archival is required")
        prev = events[-1]["receipt"]["khipu"]["digest"] if events else GENESIS
        body = {
            "organ": "formal-conjecture-lab",
            "ns": ns,
            "seq": len(events),
            "action": action,
            "payload_digest": _sha3(payload),
            "ts": datetime.datetime.now(datetime.timezone.utc).timestamp(),
            "prev": prev,
        }
        receipt = {
            **body,
            "digest": _sha3(body),
            "signature": "UNSIGNED",
            "chain_verified": True,
        }
        event = {"payload": payload, "receipt": {"khipu": receipt, "dsse": _unsigned_dsse(receipt)}}
        encoded = "\n".join(
            json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            for row in [*events, event]
        ) + "\n"
        if len(encoded.encode("utf-8")) > MAX_LEDGER_BYTES:
            raise LabUnavailable("formal lab ledger byte bound reached; archival is required")
        try:
            _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
            tmp = _STATE_PATH.with_suffix(_STATE_PATH.suffix + ".tmp")
            with tmp.open("w", encoding="utf-8", newline="\n") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, _STATE_PATH)
        except OSError as exc:
            raise LabUnavailable(f"formal lab ledger write failed ({type(exc).__name__})") from exc
        return event


def _fold_attempts(events: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    attempts: dict[str, dict[str, Any]] = {}
    for event in events:
        payload = event["payload"]
        if event["receipt"]["khipu"]["action"] == "formal.attempt.declare":
            attempt = dict(payload["attempt"])
            attempt["write_receipt"] = event["receipt"]
            attempts[attempt["attempt_id"]] = attempt
        elif event["receipt"]["khipu"]["action"] == "formal.kernel-receipt.ingest":
            attempt_id = payload["attempt_id"]
            if attempt_id in attempts:
                attempts[attempt_id]["state"] = payload["derived_state"]
                attempts[attempt_id]["kernel_result"] = payload["kernel_result"]
                attempts[attempt_id]["kernel_receipt_verification"] = payload["verification"]
                attempts[attempt_id]["write_receipt"] = event["receipt"]
    return attempts


def list_attempts(limit: int = 100) -> dict[str, Any]:
    if not isinstance(limit, int) or not 1 <= limit <= 200:
        raise ContractError("limit must be an integer from 1 through 200")
    events = _read_events()
    attempts = list(_fold_attempts(events).values())
    attempts.sort(key=lambda row: (row.get("declared_at", ""), row["attempt_id"]), reverse=True)
    chain = verify_event_chain(events)
    return {
        "service": "formal-conjecture-lab",
        "attempts": attempts[:limit],
        "count": len(attempts),
        "ledger": chain,
        "read_receipt_minted": False,
        "proof_promotion": "DISABLED",
    }


def get_attempt(attempt_id: str) -> dict[str, Any] | None:
    if not isinstance(attempt_id, str) or not _ID_RE.fullmatch(attempt_id):
        raise ContractError("attempt_id is malformed")
    return _fold_attempts(_read_events()).get(attempt_id)


def declare_attempt(request: Mapping[str, Any], ns: str = "a11oy") -> dict[str, Any]:
    normalized = normalize_attempt_request(request)
    identity = {
        "conjecture_id": normalized["conjecture_id"],
        "statement_sha256": normalized["statement_sha256"],
        "artifact_sha256": normalized["artifact_sha256"],
    }
    attempt_id = "fcl-" + _sha256(identity)[:24]
    with _WRITE_LOCK:
        prior = get_attempt(attempt_id)
        if prior is not None:
            return {"created": False, "attempt": prior, "write_receipt_minted": False}
        state = KERNEL_UNCHECKED if normalized["artifact"] is not None else DECLARED
        attempt = {
            **normalized,
            "attempt_id": attempt_id,
            "state": state,
            "declared_at": _now(),
            "kernel_result": None,
            "kernel_receipt_verification": None,
            "automatic_proof_promotion": False,
            "proof_status": "NOT_PROMOTED",
            "publication_claim_authorized": False,
            "locked_proven_count": len(LOCKED_SET),
            "locked_set": list(LOCKED_SET),
            "lambda_uniqueness": "Conjecture 1",
            "khipu_bft_safety": "Conjecture 2",
        }
        event = _append_event(ns, "formal.attempt.declare", {"attempt": attempt})
        stored = dict(attempt)
        stored["write_receipt"] = event["receipt"]
        return {"created": True, "attempt": stored, "write_receipt_minted": True}


def _kernel_verifier_status() -> dict[str, Any]:
    try:
        import cryptography  # noqa: F401
        import szl_dsse

        fingerprint = szl_dsse.public_key_fingerprint()
        return {
            "available": True,
            "state": KERNEL_UNCHECKED,
            "trust_anchor": "SZL_COSIGN_PUBLIC_KEY_EMBEDDED",
            "public_key_fingerprint_sha256": fingerprint,
        }
    except Exception as exc:
        return {
            "available": False,
            "state": UNAVAILABLE,
            "reason": f"public-key receipt verifier unavailable ({type(exc).__name__})",
        }


def _decode_verified_kernel_receipt(envelope: Mapping[str, Any], attempt: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    verifier = _kernel_verifier_status()
    if not verifier["available"]:
        raise LabUnavailable(verifier["reason"])
    env = _mapping(envelope, "dsse_envelope")
    allowed = {
        "payloadType", "payload", "signatures", "_dsse", "_pae_sha256", "_signed_at",
        "honesty", "signed", "verify_key_url",
    }
    required = {"payloadType", "payload", "signatures"}
    if not required <= set(env) or not set(env) <= allowed:
        raise ContractError("dsse_envelope fields are incomplete or unsupported")
    if env.get("payloadType") != KERNEL_PAYLOAD_TYPE:
        raise ContractError(f"payloadType must be {KERNEL_PAYLOAD_TYPE}")
    signatures = env.get("signatures")
    if not isinstance(signatures, list) or len(signatures) != 1:
        raise ContractError("one SZL cosign signature is required")
    signature = _mapping(signatures[0], "signature")
    _strict_keys(signature, {"sig", "keyid"}, "signature")
    if signature.get("keyid") != "szlholdings-cosign":
        raise ContractError("signature keyid is not the configured SZL cosign key")
    try:
        raw = base64.b64decode(str(env.get("payload")), validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ContractError("payload is not strict base64") from exc
    if len(raw) > MAX_BODY_BYTES:
        raise ContractError("kernel receipt payload exceeds the bounded body size")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractError("kernel receipt payload is not one UTF-8 JSON object") from exc
    payload = dict(_mapping(payload, "kernel receipt payload"))
    fields = {
        "schema_version", "attempt_id", "conjecture_id", "statement_sha256",
        "artifact_sha256", "checker_id", "checker_version", "kernel_commit_sha256",
        "exit_code", "sorry_count", "unsafe_declaration_count", "compiler_output_sha256",
        "checked_at", "claimed_verdict",
    }
    _strict_keys(payload, fields, "kernel receipt payload")
    if payload.get("schema_version") != KERNEL_SCHEMA:
        raise ContractError(f"kernel schema_version must be {KERNEL_SCHEMA}")
    if payload.get("attempt_id") != attempt["attempt_id"]:
        raise ContractError("kernel receipt attempt_id does not match the stored attempt")
    if payload.get("conjecture_id") != attempt["conjecture_id"]:
        raise ContractError("kernel receipt conjecture_id does not match the stored attempt")
    if payload.get("statement_sha256") != attempt["statement_sha256"]:
        raise ContractError("kernel receipt statement hash does not match the stored statement")
    if payload.get("artifact_sha256") != attempt["artifact_sha256"]:
        raise ContractError("kernel receipt artifact hash does not match the stored artifact")
    if payload.get("checker_id") != "LEAN4":
        raise ContractError("checker_id must be LEAN4")
    _text(payload.get("checker_version"), "checker_version", 128)
    _hex64(payload.get("kernel_commit_sha256"), "kernel_commit_sha256")
    _hex64(payload.get("compiler_output_sha256"), "compiler_output_sha256")
    for name in ("exit_code", "sorry_count", "unsafe_declaration_count"):
        value = payload.get(name)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0 or value > 1_000_000:
            raise ContractError(f"{name} must be a bounded non-negative integer")
    _text(payload.get("checked_at"), "checked_at", 96)
    claimed = _text(payload.get("claimed_verdict"), "claimed_verdict", 32)
    if claimed not in ("ACCEPTED", "REJECTED"):
        raise ContractError("claimed_verdict must be ACCEPTED or REJECTED")
    import szl_dsse

    verification = szl_dsse.verify_envelope(dict(env))
    if verification.get("verified") is not True:
        raise ContractError(
            "kernel DSSE signature did not verify: " + str(verification.get("reason") or "unknown")[:160]
        )
    if verification.get("keyid_expected") != "szlholdings-cosign":
        raise ContractError("kernel receipt verification used an unexpected trust anchor")
    return payload, verification


def ingest_kernel_receipt(attempt_id: str, request: Mapping[str, Any], ns: str = "a11oy") -> dict[str, Any]:
    obj = _mapping(request, "kernel receipt request")
    _strict_keys(obj, {"schema_version", "dsse_envelope"}, "kernel receipt request")
    if obj.get("schema_version") != KERNEL_SCHEMA:
        raise ContractError(f"schema_version must be {KERNEL_SCHEMA}")
    with _WRITE_LOCK:
        attempt = get_attempt(attempt_id)
        if attempt is None:
            raise StateConflict("attempt does not exist")
        if attempt.get("artifact_sha256") is None:
            raise StateConflict("attempt has no formal artifact to check")
        payload, verification = _decode_verified_kernel_receipt(obj.get("dsse_envelope"), attempt)
        derived = (
            KERNEL_ACCEPTED
            if payload["exit_code"] == 0
            and payload["sorry_count"] == 0
            and payload["unsafe_declaration_count"] == 0
            else KERNEL_REJECTED
        )
        envelope_digest = _sha256(dict(_mapping(obj.get("dsse_envelope"), "dsse_envelope")))
        prior_result = attempt.get("kernel_result")
        if attempt["state"] in (KERNEL_ACCEPTED, KERNEL_REJECTED):
            if prior_result and prior_result.get("envelope_sha256") == envelope_digest:
                return {"updated": False, "attempt": attempt, "write_receipt_minted": False}
            raise StateConflict("attempt already has a different terminal kernel receipt")
        if attempt["state"] != KERNEL_UNCHECKED:
            raise StateConflict("attempt is not ready for a kernel receipt")
        kernel_result = {
            "derived_state": derived,
            "derived_from": "SIGNED_EXIT_CODE_AND_SIGNED_SORRY_UNSAFE_COUNTS",
            "client_claimed_verdict": payload["claimed_verdict"],
            "client_label_trusted": False,
            "label_conflict": payload["claimed_verdict"] != (
                "ACCEPTED" if derived == KERNEL_ACCEPTED else "REJECTED"
            ),
            "checker_id": payload["checker_id"],
            "checker_version": payload["checker_version"],
            "kernel_commit_sha256": payload["kernel_commit_sha256"],
            "exit_code": payload["exit_code"],
            "sorry_count": payload["sorry_count"],
            "unsafe_declaration_count": payload["unsafe_declaration_count"],
            "compiler_output_sha256": payload["compiler_output_sha256"],
            "checked_at": payload["checked_at"],
            "envelope_sha256": envelope_digest,
            "proof_promoted": False,
            "publication_claim_authorized": False,
            "note": "Kernel acceptance is recorded evidence only; it is not automatic proof promotion.",
        }
        event_payload = {
            "attempt_id": attempt_id,
            "derived_state": derived,
            "kernel_result": kernel_result,
            "verification": {
                "verified": True,
                "keyid_expected": verification.get("keyid_expected"),
                "pub_fingerprint_sha256": verification.get("pub_fingerprint_sha256"),
                "pae_sha256": verification.get("pae_sha256"),
            },
        }
        event = _append_event(ns, "formal.kernel-receipt.ingest", event_payload)
        updated = get_attempt(attempt_id)
        if updated is None:
            raise LabUnavailable("attempt disappeared after a successful ledger write")
        updated["write_receipt"] = event["receipt"]
        return {"updated": True, "attempt": updated, "write_receipt_minted": True}


def status() -> dict[str, Any]:
    verifier = _kernel_verifier_status()
    try:
        bundle = list_attempts(limit=200)
        attempts = bundle["attempts"]
        ledger = bundle["ledger"]
        storage_state = "READY"
        reason = None
    except LabUnavailable as exc:
        attempts = []
        ledger = {"valid": False, "depth": 0, "broken_at": None}
        storage_state = UNAVAILABLE
        reason = str(exc)
    counts = {state: 0 for state in STATES}
    for attempt in attempts:
        counts[attempt["state"]] = counts.get(attempt["state"], 0) + 1
    return {
        "service": "formal-conjecture-lab",
        "ready": storage_state == "READY",
        "storage_state": storage_state,
        "reason": reason,
        "states": list(STATES),
        "attempt_state_counts": counts,
        "ledger": ledger,
        "kernel_execution": {
            "state": UNAVAILABLE,
            "reason": "no in-process prover execution path; arbitrary commands and network are disabled",
        },
        "kernel_receipt_verification": verifier,
        "kernel_receipt_contract": {
            "schema_version": KERNEL_SCHEMA,
            "payload_type": KERNEL_PAYLOAD_TYPE,
            "checker_id": "LEAN4",
            "signature_keyid": "szlholdings-cosign",
            "exact_bindings": [
                "attempt_id", "conjecture_id", "statement_sha256", "artifact_sha256"
            ],
            "derived_acceptance": (
                "verified DSSE AND exit_code == 0 AND sorry_count == 0 AND "
                "unsafe_declaration_count == 0"
            ),
            "client_claimed_verdict_controls_state": False,
        },
        "endpoints": {
            "status": "GET /api/a11oy/v1/formal-conjecture-lab/status",
            "list": "GET /api/a11oy/v1/formal-conjecture-lab/attempts?limit=100",
            "get": "GET /api/a11oy/v1/formal-conjecture-lab/attempts/{attempt_id}",
            "declare": "POST /api/a11oy/v1/formal-conjecture-lab/attempts",
            "ingest_kernel_receipt": (
                "POST /api/a11oy/v1/formal-conjecture-lab/attempts/{attempt_id}/kernel-receipts"
            ),
        },
        "controls": {
            "network_calls": "DISABLED",
            "command_execution": "DISABLED",
            "arbitrary_code": "DISABLED",
            "secret_reads": "DISABLED",
            "strict_contracts": True,
            "body_limit_bytes": MAX_BODY_BYTES,
            "max_events": MAX_EVENTS,
            "max_ledger_bytes": MAX_LEDGER_BYTES,
        },
        "proof_policy": {
            "automatic_promotion": False,
            "kernel_accepted_means_proved": False,
            "publication_claim_authorized": False,
            "locked_proven_count": len(LOCKED_SET),
            "locked_set": list(LOCKED_SET),
            "lambda_uniqueness": "Conjecture 1",
            "khipu_bft_safety": "Conjecture 2",
        },
        "receipt_policy": "RECEIPT-ON-WRITE-NOT-ON-READ",
    }


async def _read_body(request: Any) -> dict[str, Any]:
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            declared = int(content_length)
        except ValueError as exc:
            raise ContractError("content-length must be a non-negative integer") from exc
        if declared < 0:
            raise ContractError("content-length must be a non-negative integer")
        if declared > MAX_BODY_BYTES:
            raise ContractError(f"request body exceeds {MAX_BODY_BYTES} bytes")
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > MAX_BODY_BYTES:
            raise ContractError(f"request body exceeds {MAX_BODY_BYTES} bytes")
        data.extend(chunk)
    try:
        value = json.loads(bytes(data).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractError("request body must be one UTF-8 JSON object") from exc
    return dict(_mapping(value, "request body"))


def register(app: Any, ns: str = "a11oy") -> dict[str, Any]:
    """Register bounded read/write routes before both application catch-alls."""
    from fastapi import Request
    from fastapi.responses import JSONResponse

    base = f"/api/{ns}/v1/formal-conjecture-lab"

    @app.get(base + "/status")
    async def _formal_lab_status() -> JSONResponse:
        return JSONResponse(status())

    @app.get(base + "/attempts")
    async def _formal_lab_attempts(limit: int = 100) -> JSONResponse:
        try:
            return JSONResponse(list_attempts(limit))
        except ContractError as exc:
            return JSONResponse({"state": UNAVAILABLE, "error": str(exc)}, status_code=422)
        except LabUnavailable as exc:
            return JSONResponse({"state": UNAVAILABLE, "error": str(exc)}, status_code=503)

    @app.get(base + "/attempts/{attempt_id}")
    async def _formal_lab_attempt(attempt_id: str) -> JSONResponse:
        try:
            attempt = get_attempt(attempt_id)
        except ContractError as exc:
            return JSONResponse({"state": UNAVAILABLE, "error": str(exc)}, status_code=422)
        except LabUnavailable as exc:
            return JSONResponse({"state": UNAVAILABLE, "error": str(exc)}, status_code=503)
        if attempt is None:
            return JSONResponse({"state": UNAVAILABLE, "error": "attempt not found"}, status_code=404)
        return JSONResponse({"attempt": attempt, "read_receipt_minted": False})

    @app.post(base + "/attempts")
    async def _formal_lab_declare(request: Request) -> JSONResponse:
        try:
            result = declare_attempt(await _read_body(request), ns)
            return JSONResponse(result, status_code=201 if result["created"] else 200)
        except ContractError as exc:
            code = 413 if "body exceeds" in str(exc) else 422
            return JSONResponse({"state": UNAVAILABLE, "error": str(exc)}, status_code=code)
        except LabUnavailable as exc:
            return JSONResponse({"state": UNAVAILABLE, "error": str(exc)}, status_code=503)

    @app.post(base + "/attempts/{attempt_id}/kernel-receipts")
    async def _formal_lab_kernel_receipt(attempt_id: str, request: Request) -> JSONResponse:
        try:
            return JSONResponse(ingest_kernel_receipt(attempt_id, await _read_body(request), ns))
        except ContractError as exc:
            code = 413 if "body exceeds" in str(exc) else 422
            return JSONResponse({"state": UNAVAILABLE, "error": str(exc)}, status_code=code)
        except StateConflict as exc:
            return JSONResponse({"state": UNAVAILABLE, "error": str(exc)}, status_code=409)
        except LabUnavailable as exc:
            return JSONResponse({"state": UNAVAILABLE, "error": str(exc)}, status_code=503)

    return {
        "registered": True,
        "base": base,
        "kernel_execution": UNAVAILABLE,
        "proof_promotion": "DISABLED",
    }
