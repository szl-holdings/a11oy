"""Token-fenced, idempotent drain for durable GDW effect-outbox rows."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from gdw_proofs import (
    delete_exported_artifact,
    export_proof_payload,
    export_receipt_projection,
)
from gdw_workspace import GDWWorkspace


def _drain_artifact_gc(
    workspace: GDWWorkspace,
    *,
    limit: int,
    worker_id: str,
) -> Dict[str, Any]:
    deleted = 0
    failed = 0
    error_classes = []
    while deleted + failed < limit:
        rows = workspace.claim_artifact_gc(worker_id, limit=1)
        if not rows:
            break
        row = rows[0]
        try:
            workspace.validate_claimed_artifact_gc(row)
            delete_exported_artifact(row)
            if not workspace.complete_artifact_gc(
                row["idempotency_key"],
                worker_id,
                row["claim_token"],
            ):
                raise RuntimeError("artifact GC claim expired before acknowledgement")
            deleted += 1
        except Exception as exc:
            workspace.release_artifact_gc(
                row["idempotency_key"],
                worker_id,
                row["claim_token"],
                f"{type(exc).__name__}: {exc}",
            )
            failed += 1
            error_classes.append(type(exc).__name__)
            break
    return {
        "deleted": deleted,
        "failed": failed,
        "error_classes": error_classes,
    }


def drain_effects(
    workspace: GDWWorkspace,
    *,
    limit: int = 100,
    worker_id: Optional[str] = None,
) -> Dict[str, Any]:
    bounded = int(limit)
    if bounded < 1 or bounded > 1000:
        raise ValueError("drain limit must be between 1 and 1000")
    worker = worker_id or f"gdw-runtime-{os.getpid()}-{uuid.uuid4().hex[:12]}"
    exported = 0
    failed = 0
    error_classes = []
    reclaimed = workspace.reclaim_expired_now()
    gc_result = _drain_artifact_gc(
        workspace,
        limit=bounded,
        worker_id=f"{worker}-artifact-gc",
    )

    while exported + failed < bounded:
        rows = workspace.claim_effects(worker, limit=1)
        if not rows:
            break
        row = rows[0]
        try:
            workspace.validate_claimed_effect(row)
            if row["kind"] == "proof_export":
                artifact = export_proof_payload(
                    row["payload"],
                    artifact_identity=row["idempotency_key"],
                    owner_id=row["owner_id"],
                )
            elif row["kind"] == "receipt_projection":
                artifact = export_receipt_projection(
                    row["payload"],
                    row["idempotency_key"],
                    owner_id=row["owner_id"],
                )
            else:
                raise ValueError("unsupported effect kind")
            workspace.mark_effect_exported(
                row["idempotency_key"],
                worker,
                row["claim_token"],
                artifact,
                datetime.now(timezone.utc).isoformat(),
            )
            exported += 1
        except Exception as exc:
            workspace.release_effect(
                row["idempotency_key"],
                worker,
                row["claim_token"],
                f"{type(exc).__name__}: {exc}",
            )
            failed += 1
            error_classes.append(type(exc).__name__)
            break

    integrity = workspace.integrity()
    complete = (
        failed == 0
        and gc_result["failed"] == 0
        and integrity["pending_effects"] == 0
        and integrity["pending_artifact_gc"] == 0
    )
    return {
        "schema": "szl.gdw-effect-drain/v1",
        "limit": bounded,
        "exported": exported,
        "failed": failed,
        "error_classes": error_classes,
        "reclaimed": reclaimed,
        "gc_deleted": gc_result["deleted"],
        "gc_failed": gc_result["failed"],
        "gc_error_classes": gc_result["error_classes"],
        "pending_effects": integrity["pending_effects"],
        "pending_artifact_gc": integrity["pending_artifact_gc"],
        "complete": complete,
        "limit_exhausted": (
            (exported >= bounded and integrity["pending_effects"] > 0)
            or (
                gc_result["deleted"] >= bounded
                and integrity["pending_artifact_gc"] > 0
            )
        ),
        "integrity_ok": integrity["ok"],
        "generation_id": integrity["generation_id"],
        "credential_values_recorded": False,
    }
