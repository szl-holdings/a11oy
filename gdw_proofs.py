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
) -> Dict[str, Any]:
    root.mkdir(parents=True, exist_ok=True)
    destination = root / filename
    encoded = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    if destination.exists():
        if destination.read_bytes() != encoded:
            raise FileExistsError(
                "refusing to overwrite an existing non-identical GDW artifact"
            )
        return {
            "status": "EXPORTED",
            "path": str(destination),
            "sha256": hashlib.sha256(encoded).hexdigest(),
            "reused": True,
        }
    handle, temporary = tempfile.mkstemp(prefix=".gdw-artifact-", suffix=".tmp", dir=root)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, destination)
        except FileExistsError:
            if destination.read_bytes() != encoded:
                raise FileExistsError(
                    "refusing to overwrite a concurrently created "
                    "non-identical GDW artifact"
                )
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return {
        "status": "EXPORTED",
        "path": str(destination),
        "sha256": hashlib.sha256(encoded).hexdigest(),
        "reused": False,
    }


def export_proof_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    root = Path(os.environ.get("GDW_PROOF_DIR", "output/proofs")).resolve()
    proposal_id = payload["proposal_id"]
    if not proposal_id or any(ch not in "0123456789abcdef" for ch in proposal_id):
        raise ValueError("proposal_id is not a canonical lowercase hexadecimal id")
    claimed_digest = payload.get("payload_sha256")
    unsigned_payload = dict(payload)
    unsigned_payload.pop("payload_sha256", None)
    if claimed_digest != sha256_json(unsigned_payload):
        raise ValueError("proof payload_sha256 does not match canonical payload")
    artifact = _export_json_artifact(root, f"{proposal_id}.json", payload)
    artifact.update({"status": "INPUT_EXPORTED", "formal_status": "NOT_RUN"})
    return artifact


def export_receipt_projection(
    payload: Dict[str, Any],
    idempotency_key: str,
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
    artifact = _export_json_artifact(root, f"{idempotency_key}.json", payload)
    artifact.update(
        {
            "status": "RECEIPT_PROJECTED",
            "receipt_status": "UNSIGNED_ATOMIC",
        }
    )
    return artifact
