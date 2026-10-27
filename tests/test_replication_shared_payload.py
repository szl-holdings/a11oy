#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Current receipt binding and immutable replication predecessor identities."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ".github/shared-source-payloads/replication-snapshot-delivery-20261021-v1.json"


def test_snapshot_replication_payload_preserves_prior_manifest_and_source():
    archive = ".github/shared-source-payloads/bonsai-model-catalog-20261017-v1.json"
    prior = (ROOT / archive).read_bytes()
    assert hashlib.sha256(prior).hexdigest() == "6cee005bcd706c7c74cf8439ed87769ad020ae2e44aa1d61beb915eeccc19ccc"
    raw = (ROOT / SNAPSHOT).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == "af144993e51a7348ee008f0ffa1bbb771759583b0281ac95580f1a4687ec9166"
    manifest = json.loads(raw)
    assert manifest["schema"] == "szl-shared-source-payload/v1"
    assert manifest["payload_id"] == "replication-snapshot-delivery-20261021-v1"
    assert set(manifest["files"]) == set(json.loads(prior)["files"]) | {
        archive, "szl_khipu_delivery_routes.py", "szl_operator_auth.py", "docs/replication-snapshot-delivery.md",
        "tests/test_khipu_delivery_routes.py", "tests/test_replication_shared_payload.py",
        "tests/test_gitleaks_archived_payload_digest.py",
        "khipu_lmdb/__init__.py", "khipu_lmdb/core.py", "khipu_lmdb/outbox.py", "khipu_lmdb/delivery.py",
    }
    historical = {
        "a11oy_code_engine.py": "5994454fb6b699f94aec417ea637dec4459a6d2abcc1654df4a7f4bfba0ee67c",
        "tests/test_replication_shared_payload.py": "44e6b7436ac9d927712dabe3f8d811f37ccb82de6048d2ccd62db20b8893aace",
        "tests/test_gitleaks_archived_payload_digest.py": "d41d4a9e0b4ec19446c8fbc643b1b9f792b12701fc4fb1a51024385fd12e4b4c",
    }
    for relative, expected in manifest["files"].items():
        if relative in historical:
            assert expected == historical[relative]
        else:
            assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == expected


def test_receipt_binding_successor_binds_every_current_file_and_snapshot():
    prior = (ROOT / SNAPSHOT).read_bytes()
    assert hashlib.sha256(prior).hexdigest() == "af144993e51a7348ee008f0ffa1bbb771759583b0281ac95580f1a4687ec9166"
    manifest = json.loads((ROOT / ".github/shared-source-payload-manifest.json").read_bytes())
    assert manifest["schema"] == "szl-shared-source-payload/v1"
    assert manifest["payload_id"] == "code-receipt-binding-20261023-v1"
    assert set(manifest["files"]) == set(json.loads(prior)["files"]) | {
        SNAPSHOT, "tests/test_code_receipt_binding.py",
    }
    for relative, expected in manifest["files"].items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == expected
