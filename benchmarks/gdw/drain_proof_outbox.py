"""Lease and export durable GDW effect-outbox rows idempotently."""

import argparse
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gdw_proofs import export_proof_payload, export_receipt_projection  # noqa: E402
from gdw_workspace import GDWWorkspace  # noqa: E402


def main(limit):
    workspace = GDWWorkspace()
    exported = 0
    failed = 0

    # Drain rows created by the first Wave-28 schema. The deterministic proof
    # filename makes a retry after write-before-mark safe.
    for row in workspace.pending_proofs(limit):
        artifact = export_proof_payload(row["payload"])
        workspace.mark_proof_exported(
            row["proposal_id"],
            artifact,
            datetime.now(timezone.utc).isoformat(),
        )
        exported += 1

    worker_id = f"gdw-drain-{os.getpid()}-{uuid.uuid4().hex[:12]}"
    stop_after_failure = False
    while exported < limit:
        rows = workspace.claim_effects(
            worker_id,
            limit=min(100, limit - exported),
        )
        if not rows:
            break
        for row in rows:
            try:
                if row["kind"] == "proof_export":
                    artifact = export_proof_payload(row["payload"])
                elif row["kind"] == "receipt_projection":
                    artifact = export_receipt_projection(
                        row["payload"],
                        row["idempotency_key"],
                    )
                else:  # schema constraint makes this defensive only
                    raise ValueError(f"unsupported effect kind: {row['kind']}")
                workspace.mark_effect_exported(
                    row["idempotency_key"],
                    worker_id,
                    artifact,
                    datetime.now(timezone.utc).isoformat(),
                )
                exported += 1
            except Exception as exc:
                workspace.release_effect(
                    row["idempotency_key"],
                    worker_id,
                    f"{type(exc).__name__}: {exc}",
                )
                failed += 1
                stop_after_failure = True
        if stop_after_failure:
            break
    integrity = workspace.integrity()
    print(
        {
            "exported": exported,
            "failed": failed,
            "pending": integrity["pending_effects"],
            "legacy_pending_proofs": integrity["pending_proofs"],
            "sqlite_integrity": integrity["sqlite_integrity"],
        }
    )
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=1000)
    args = parser.parse_args()
    main(args.limit)
