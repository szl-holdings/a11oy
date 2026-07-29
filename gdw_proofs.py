"""Structured theorem-input export for asynchronous Lean checking."""

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def build_proof_payload(
    proposal_id: str,
    request_id: str,
    request_digest: str,
    owner_id: str,
    generation_id: str,
    step: int,
    before_hash: str,
    after_hash: str,
    decision: str,
    scheduler_mode: str,
    receipt_hash: str,
    dry_run: bool,
    governance: Dict[str, Any],
) -> Dict[str, Any]:
    mutates = decision == "ACCEPT" and not dry_run
    governance_digest = sha256_json(governance)
    payload = {
        "schema": "szl.gdw.proof-input/v1",
        "proposal_id": proposal_id,
        "request_id": request_id,
        "request_digest": request_digest,
        "owner_id": owner_id,
        "generation_id": generation_id,
        "step_id": step,
        "state_before_hash": before_hash,
        "state_after_hash": after_hash,
        "decision": decision,
        "scheduler_mode": scheduler_mode,
        "delta_update_receipt_hash": receipt_hash,
        "governance": governance,
        "governance_evidence_sha256": governance_digest,
        "invariants": {
            "step_nonnegative": step >= 0,
            "accepted_write_has_receipt": (not mutates) or bool(receipt_hash),
            "accepted_write_has_governance_allow": (
                (not mutates) or governance.get("allowed") is True
            ),
            "non_mutating_preserves_state": mutates or before_hash == after_hash,
            "scheduler_mode_valid": scheduler_mode
            in {"kda_local", "laguna_hybrid", "mla_global"},
        },
        "formal_status": "NOT_RUN",
    }
    payload["payload_sha256"] = sha256_json(payload)
    return payload


def _export_json_artifact(
    root: Path,
    filename: str,
    payload: Dict[str, Any],
    owner_id: str,
) -> Dict[str, Any]:
    if not owner_id:
        raise ValueError("owner_id is required for artifact isolation")
    owner_scope = hashlib.sha256(owner_id.encode("utf-8")).hexdigest()[:32]
    owner_root = root / owner_scope
    owner_root.mkdir(parents=True, exist_ok=True)
    destination = owner_root / filename
    encoded = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    expected_sha256 = hashlib.sha256(encoded).hexdigest()

    if destination.exists():
        existing = destination.read_bytes()
        if existing != encoded:
            raise FileExistsError(
                f"immutable artifact identity collision: {destination.name}"
            )
        return {
            "status": "EXISTS_IDENTICAL",
            "path": str(destination),
            "sha256": expected_sha256,
            "immutable": True,
            "owner_scope": owner_scope,
        }

    owner_limit = int(os.environ.get("GDW_OWNER_MAX_ARTIFACTS", "10000"))
    global_limit = int(os.environ.get("GDW_GLOBAL_MAX_ARTIFACTS", "100000"))
    if owner_limit < 1 or owner_limit > 100000:
        raise RuntimeError("GDW owner artifact quota is invalid")
    if global_limit < owner_limit or global_limit > 1000000:
        raise RuntimeError("GDW global artifact quota is invalid")
    if sum(1 for _ in owner_root.glob("*.json")) >= owner_limit:
        raise RuntimeError("per-owner artifact quota exceeded")
    if sum(1 for _ in root.glob("*/*.json")) >= global_limit:
        raise RuntimeError("global artifact quota exceeded")

    handle, temporary = tempfile.mkstemp(
        prefix=".gdw-artifact-", suffix=".tmp", dir=owner_root
    )
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, destination)
        except FileExistsError:
            existing = destination.read_bytes()
            if existing != encoded:
                raise FileExistsError(
                    f"immutable artifact identity collision: {destination.name}"
                )
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return {
        "status": "EXPORTED",
        "path": str(destination),
        "sha256": expected_sha256,
        "immutable": True,
        "owner_scope": owner_scope,
    }


def export_proof_payload(
    payload: Dict[str, Any],
    artifact_identity: str | None = None,
    owner_id: str | None = None,
) -> Dict[str, Any]:
    root = Path(os.environ.get("GDW_PROOF_DIR", "output/proofs")).resolve()
    proposal_id = payload["proposal_id"]
    if not proposal_id or any(ch not in "0123456789abcdef" for ch in proposal_id):
        raise ValueError("proposal_id is not a canonical lowercase hexadecimal id")
    claimed_digest = payload.get("payload_sha256")
    unsigned_payload = dict(payload)
    unsigned_payload.pop("payload_sha256", None)
    if claimed_digest != sha256_json(unsigned_payload):
        raise ValueError("proof payload_sha256 does not match canonical payload")
    identity = artifact_identity or proposal_id
    if (
        len(identity) != 64
        or any(ch not in "0123456789abcdef" for ch in identity)
    ):
        raise ValueError("artifact_identity must be a lowercase SHA-256 digest")
    artifact = _export_json_artifact(
        root,
        f"{identity}.json",
        payload,
        owner_id or str(payload.get("owner_id") or ""),
    )
    artifact["artifact_identity"] = identity
    artifact.update({"status": "INPUT_EXPORTED", "formal_status": "NOT_RUN"})
    return artifact


def export_receipt_projection(
    payload: Dict[str, Any],
    idempotency_key: str,
    owner_id: str | None = None,
) -> Dict[str, Any]:
    root = Path(
        os.environ.get("GDW_RECEIPT_PROJECTION_DIR", "output/gdw/receipts")
    ).resolve()
    if (
        len(idempotency_key) != 64
        or any(ch not in "0123456789abcdef" for ch in idempotency_key)
    ):
        raise ValueError("idempotency_key must be a lowercase SHA-256 digest")
    claimed_digest = payload.get("receipt_hash")
    unsigned_payload = dict(payload)
    unsigned_payload.pop("receipt_hash", None)
    if claimed_digest != sha256_json(unsigned_payload):
        raise ValueError("receipt_hash does not match canonical receipt")
    artifact = _export_json_artifact(
        root,
        f"{idempotency_key}.json",
        payload,
        owner_id or str(payload.get("owner_id") or ""),
    )
    artifact["artifact_identity"] = idempotency_key
    artifact.update(
        {
            "status": "RECEIPT_PROJECTED",
            "receipt_status": "UNSIGNED_ATOMIC",
        }
    )
    return artifact
