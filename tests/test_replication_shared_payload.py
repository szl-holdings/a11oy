#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Current replication contribution and immutable predecessor source identities."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_snapshot_replication_payload_binds_current_files_and_prior_manifest():
    archive = ".github/shared-source-payloads/bonsai-model-catalog-20261017-v1.json"
    prior = (ROOT / archive).read_bytes()
    assert hashlib.sha256(prior).hexdigest() == "6cee005bcd706c7c74cf8439ed87769ad020ae2e44aa1d61beb915eeccc19ccc"
    manifest = json.loads((ROOT / ".github/shared-source-payload-manifest.json").read_bytes())
    assert manifest["schema"] == "szl-shared-source-payload/v1"
    assert manifest["payload_id"] == "replication-snapshot-delivery-20261021-v1"
    assert set(manifest["files"]) == set(json.loads(prior)["files"]) | {
        archive, "szl_khipu_delivery_routes.py", "szl_operator_auth.py", "szl_operator_auth.py", "docs/replication-snapshot-delivery.md",
        "tests/test_khipu_delivery_routes.py", "tests/test_replication_shared_payload.py",
        "tests/test_gitleaks_archived_payload_digest.py",
        "khipu_lmdb/__init__.py", "khipu_lmdb/core.py", "khipu_lmdb/outbox.py", "khipu_lmdb/delivery.py",
    }
    for relative, expected in manifest["files"].items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == expected
