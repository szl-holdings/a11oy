"""Token-fenced, idempotent drain for durable GDW effect-outbox rows."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from gdw_proofs import export_proof_payload, export_receipt_projection
from gdw_workspace import GDWWorkspace


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
    return {
        "schema": "szl.gdw-effect-drain/v1",
        "exported": exported,
        "failed": failed,
        "error_classes": error_classes,
        "pending_effects": integrity["pending_effects"],
        "integrity_ok": integrity["ok"],
        "generation_id": integrity["generation_id"],
        "credential_values_recorded": False,
    }
