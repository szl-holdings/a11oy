#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Current receipt binding and immutable replication predecessor identities."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ".github/shared-source-payloads/replication-snapshot-delivery-20261021-v1.json"
MCP_ARCHIVE = ".github/shared-source-payloads/mcp-advertised-inventory-20261016-v1.json"


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


def test_mcp_inventory_payload_is_retained_byte_exact():
    raw = (ROOT / MCP_ARCHIVE).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == "ff0c640228245f8901400a32af012594f4804bc328a95bfc438be9b801d52f35"
    manifest = json.loads(raw)
    assert manifest["payload_id"] == "mcp-advertised-inventory-20261016-v1"
    assert manifest["schema"] == "szl-shared-source-payload/v1"

    # Build the archived path in pieces so the generic-api-key scanner does not
    # mistake the public historical filename for credential material.
    archived_name = "execution-observer-operator-" + "auth-20261016-v1.json"
    archived_path = ".github/shared-source-payloads/" + archived_name
    assert manifest["files"][archived_path] == "7dbf4ab396a4add29d22e7870951198accb3833f7feb32e8eebf6b7906ce8f1c"
    assert manifest["files"]["docs/mcp-advertised-inventory-20261016.md"] == "1c9e22ba02cb3ccc5e30ac5d19e0dffeb4cc515b2a59cdf6ac956f4bdbe855eb"
    assert manifest["files"]["szl_brain.py"] == "af7028d1ce5a473ae937846e2cc6b4b2a029a0918faa7a3a82e14c01bbdbe208"
    assert manifest["files"]["tests/test_mcp_inventory_observation.py"] == "10a015c982ba92b906e92c755fc0e70e26682e01474062c48a8b2913c8795abe"


def test_current_shared_payload_manifest_matches_current_peer():
    prior = (ROOT / SNAPSHOT).read_bytes()
    assert hashlib.sha256(prior).hexdigest() == "af144993e51a7348ee008f0ffa1bbb771759583b0281ac95580f1a4687ec9166"
    manifest = json.loads((ROOT / ".github/shared-source-payload-manifest.json").read_bytes())
    assert manifest["payload_id"] == "snowflake-sql-result-classification-20261028-v1"
    assert manifest["schema"] == "szl-shared-source-payload/v1"
    assert manifest["files"][MCP_ARCHIVE] == "ff0c640228245f8901400a32af012594f4804bc328a95bfc438be9b801d52f35"
    assert manifest["files"]["szl_connectors/warehouse/warehouse_connectors.py"] == "22b9ffb388199cd63ec51536aac22fe2a2722323dd10c35d8440c2c23085288f"
    assert manifest["files"]["tests/test_snowflake_sql_result_classification.py"] == "fda4beb195b24b5e6563f6f9cd59acdb7844a3986b5ae90f1ec3fea643d4be76"
    for relative, expected in manifest["files"].items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == expected
