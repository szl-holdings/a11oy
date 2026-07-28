"""Export durable GDW proof-outbox rows to atomic JSON artifacts."""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gdw_proofs import export_proof_payload
from gdw_workspace import GDWWorkspace


def main(limit):
    workspace = GDWWorkspace()
    exported = 0
    for row in workspace.pending_proofs(limit):
        artifact = export_proof_payload(row["payload"])
        workspace.mark_proof_exported(
            row["proposal_id"],
            artifact,
            datetime.now(timezone.utc).isoformat(),
        )
        exported += 1
    integrity = workspace.integrity()
    print(
        {
            "exported": exported,
            "pending": integrity["pending_proofs"],
            "sqlite_integrity": integrity["sqlite_integrity"],
        }
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=1000)
    args = parser.parse_args()
    main(args.limit)
