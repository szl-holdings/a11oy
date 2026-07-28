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
) -> Dict[str, Any]:
    mutates = decision == "ACCEPT" and not dry_run
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
        "invariants": {
            "step_nonnegative": step >= 0,
            "accepted_write_has_receipt": (not mutates) or bool(receipt_hash),
            "non_mutating_preserves_state": mutates or before_hash == after_hash,
            "scheduler_mode_valid": scheduler_mode
            in {"kda_local", "laguna_hybrid", "mla_global"},
        },
        "formal_status": "NOT_RUN",
    }
    payload["payload_sha256"] = sha256_json(payload)
    return payload


def export_proof_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    root = Path(os.environ.get("GDW_PROOF_DIR", "output/proofs")).resolve()
    root.mkdir(parents=True, exist_ok=True)
    proposal_id = payload["proposal_id"]
    if not proposal_id or any(ch not in "0123456789abcdef" for ch in proposal_id):
        raise ValueError("proposal_id is not a canonical lowercase hexadecimal id")
    destination = root / f"{proposal_id}.json"
    encoded = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    handle, temporary = tempfile.mkstemp(prefix=".gdw-proof-", suffix=".tmp", dir=root)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return {
        "status": "INPUT_EXPORTED",
        "path": str(destination),
        "sha256": hashlib.sha256(encoded).hexdigest(),
        "formal_status": "NOT_RUN",
    }
