#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED 749/14/163 · SLSA L1 (unchanged)
"""Exercise the vessels Khipu ingest consumer so it records a REAL DSSE envelope in CI.

Issue #194 — the deploy/release pipelines must prove that the consumer side of
Wire F (szl_wire.ingest_receipt) records a GENUINE Sigstore keyless DSSE signature
when run in CI (id-token: write), not the honest off-CI placeholder.

This builds an a11oy gate-decision receipt (szl_wire.emit_gate_decision_receipt),
ingests it into the Khipu Merkle DAG (szl_wire.ingest_receipt), and writes the
resulting node — including the real DSSE envelope produced at ingest time — to
attestations/khipu/. By default it REFUSES (exit 2) if the ingest produced only a
placeholder, so a release pipeline cannot silently ship an unsigned consumer
receipt; pass --allow-placeholder for the honest off-CI placeholder.

HONESTY: this only upgrades the receipt SIGNATURE; the SLSA claim is unchanged
(still L1). Outside CI there is no ambient OIDC token, so ingest_receipt() keeps
the honest dsse_envelope() placeholder and this tool declines rather than fabricate.

Outputs:
  attestations/khipu/<digest>.dsse.json   (the DSSE envelope recorded at ingest)
  attestations/khipu/<digest>.node.json   (the full Khipu DAG node)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from szl_wire import emit_gate_decision_receipt, ingest_receipt  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--action-id", default=None,
        help="gate-decision action id (default: CI run id, else local-dev-run)",
    )
    ap.add_argument(
        "--gate", default="ci-deploy-release",
        help="gate name recorded on the receipt",
    )
    ap.add_argument(
        "--out-dir", default=str(REPO_ROOT / "attestations" / "khipu"),
        help="directory to write the signed Khipu node + DSSE envelope into",
    )
    ap.add_argument(
        "--allow-placeholder", action="store_true",
        help="accept the honest placeholder instead of failing when real signing is unavailable",
    )
    args = ap.parse_args(argv)

    action_id = args.action_id or os.environ.get("GITHUB_RUN_ID", "local-dev-run")

    # a11oy side of Wire F: build the gate-decision receipt...
    receipt = emit_gate_decision_receipt(
        action_id=str(action_id),
        gate=args.gate,
        lambda_score=0.0,
        fired=[],
        passed=True,
    )
    # ...vessels side of Wire F: ingest it, DSSE-signing the receipt at ingest time.
    node = ingest_receipt(receipt)
    dsse = node.get("dsse", {})
    mode = dsse.get("_mode", "?")
    digest = node.get("digest", "unknown")

    print(f"[khipu] ingested receipt action_id={action_id} digest={digest}")
    print(f"[khipu] dsse mode={mode}")

    if mode != "SIGSTORE-KEYLESS" and not args.allow_placeholder:
        print(
            "[khipu] REFUSING: ingest produced a PLACEHOLDER, not a real Sigstore "
            "keyless signature. Run inside GitHub Actions with `id-token: write`, "
            "or pass --allow-placeholder for the honest placeholder.",
            file=sys.stderr,
        )
        return 2

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    env_path = out_dir / f"{digest}.dsse.json"
    node_path = out_dir / f"{digest}.node.json"
    env_path.write_text(json.dumps(dsse, indent=2, sort_keys=True), encoding="utf-8")
    node_path.write_text(json.dumps(node, indent=2, sort_keys=True), encoding="utf-8")
    print(f"[khipu] wrote {env_path}")
    print(f"[khipu] wrote {node_path}")
    if mode == "SIGSTORE-KEYLESS":
        sig = dsse.get("_sigstore", {})
        print(f"[khipu] rekor_log_index={sig.get('rekor_log_index')}")
        print(f"[khipu] certificate_fpr_sha256={sig.get('certificate_fpr_sha256')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
