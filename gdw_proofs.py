"""Structured theorem-input export for asynchronous Lean checking."""

import hashlib
import json
import os
import threading
from pathlib import Path
from typing import Any, Dict


_ARTIFACT_QUOTA_LOCK = threading.RLock()


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def build_proof_payload(
    proposal_id: str,
    request_id: str,
    request_digest: str,
    namespace: str,
    owner_id: str,
    database_generation_id: str,
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
        "namespace": namespace,
        "owner_id": owner_id,
        "database_generation_id": database_generation_id,
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


def _export_json_artifact_unlocked(
    root: Path,
    filename: str,
    payload: Dict[str, Any],
    owner_id: str,
) -> Dict[str, Any]:
    if type(owner_id) is not str or not owner_id:
        raise ValueError("owner_id is required for artifact isolation")
    root.mkdir(parents=True, exist_ok=True)
    root = root.resolve()
    owner_scope = hashlib.sha256(owner_id.encode("utf-8")).hexdigest()[:32]
    owner_candidate = root / owner_scope
    owner_candidate.mkdir(parents=True, exist_ok=True)
    owner_root = owner_candidate.resolve()
    if owner_root.parent != root or owner_root.name != owner_scope:
        raise ValueError("artifact owner scope escapes the configured root")
    destination = owner_root / filename
    encoded = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    expected_sha256 = hashlib.sha256(encoded).hexdigest()
    if destination.exists():
        if destination.read_bytes() != encoded:
            raise FileExistsError(
                "refusing to overwrite an existing non-identical GDW artifact"
            )
        return {
            "status": "EXPORTED",
            "path": str(destination),
            "sha256": expected_sha256,
            "reused": True,
            "immutable": True,
            "owner_scope": owner_scope,
            "publication_mode": "REUSED",
        }
    owner_limit = _bounded_artifact_limit(
        "GDW_OWNER_MAX_ARTIFACTS", default=10_000, maximum=100_000
    )
    global_limit = _bounded_artifact_limit(
        "GDW_GLOBAL_MAX_ARTIFACTS", default=100_000, maximum=1_000_000
    )
    if global_limit < owner_limit:
        raise ValueError(
            "GDW_GLOBAL_MAX_ARTIFACTS must be at least GDW_OWNER_MAX_ARTIFACTS"
        )
    if sum(1 for _ in owner_root.glob("*.json")) >= owner_limit:
        raise RuntimeError("per-owner artifact quota exceeded")
    if sum(1 for _ in root.glob("*/*.json")) >= global_limit:
        raise RuntimeError("global artifact quota exceeded")
    reused = False
    try:
        destination_handle = os.open(
            destination,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
    except FileExistsError:
        if destination.read_bytes() != encoded:
            raise FileExistsError(
                "refusing to overwrite a concurrently created "
                "non-identical GDW artifact"
            )
        reused = True
    else:
        stream = None
        try:
            stream = os.fdopen(destination_handle, "wb")
            with stream:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
        except BaseException:
            if stream is None:
                os.close(destination_handle)
            try:
                os.unlink(destination)
            except FileNotFoundError:
                pass
            raise
    return {
        "status": "EXPORTED",
        "path": str(destination),
        "sha256": expected_sha256,
        "reused": reused,
        "immutable": True,
        "owner_scope": owner_scope,
        "publication_mode": (
            "REUSED" if reused else "EXCLUSIVE_CREATE"
        ),
    }


def _bounded_artifact_limit(name: str, *, default: int, maximum: int) -> int:
    raw = os.environ.get(name)
    try:
        value = int(raw) if raw not in (None, "") else default
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value < 1 or value > maximum:
        raise ValueError(f"{name} must be between 1 and {maximum}")
    return value


def _export_json_artifact(
    root: Path,
    filename: str,
    payload: Dict[str, Any],
    owner_id: str,
) -> Dict[str, Any]:
    with _ARTIFACT_QUOTA_LOCK:
        return _export_json_artifact_unlocked(
            root,
            filename,
            payload,
            owner_id,
        )


def _validate_artifact_id(artifact_id: str) -> None:
    if (
        len(artifact_id) != 64
        or any(ch not in "0123456789abcdef" for ch in artifact_id)
    ):
        raise ValueError("artifact_id must be a lowercase SHA-256 digest")


def export_proof_payload(
    payload: Dict[str, Any],
    *,
    artifact_id: str | None = None,
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
    resolved_artifact_id = artifact_id or claimed_digest
    _validate_artifact_id(resolved_artifact_id)
    artifact = _export_json_artifact(
        root,
        f"{resolved_artifact_id}.json",
        payload,
        owner_id or str(payload.get("owner_id") or ""),
    )
    artifact["artifact_identity"] = resolved_artifact_id
    artifact.update({"status": "INPUT_EXPORTED", "formal_status": "NOT_RUN"})
    return artifact


def export_receipt_projection(
    payload: Dict[str, Any],
    artifact_id: str,
    owner_id: str | None = None,
) -> Dict[str, Any]:
    root = Path(
        os.environ.get("GDW_RECEIPT_PROJECTION_DIR", "output/gdw/receipts")
    ).resolve()
    _validate_artifact_id(artifact_id)
    claimed_digest = payload.get("receipt_hash")
    unsigned_payload = dict(payload)
    unsigned_payload.pop("receipt_hash", None)
    if claimed_digest != sha256_json(unsigned_payload):
        raise ValueError("receipt_hash does not match canonical receipt")
    artifact = _export_json_artifact(
        root,
        f"{artifact_id}.json",
        payload,
        owner_id or str(payload.get("owner_id") or ""),
    )
    artifact["artifact_identity"] = artifact_id
    artifact.update(
        {
            "status": "RECEIPT_PROJECTED",
            "receipt_status": "UNSIGNED_ATOMIC",
        }
    )
    return artifact
