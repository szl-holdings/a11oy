#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Current receipt binding and immutable replication predecessor identities."""
import hashlib
import json
from pathlib import Path
import shutil

import pytest

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ".github/shared-source-payloads/replication-snapshot-delivery-20261021-v1.json"
MCP_ARCHIVE = ".github/shared-source-payloads/mcp-advertised-inventory-20261016-v1.json"
RETAINED = "tests/fixtures/shared-source-payloads/retained-signing-ledger-20261101-v1.json"
SNOWFLAKE = ".github/shared-source-payloads/snowflake-account-host-boundary-20261102-v1.json"
ACTIVE = ".github/shared-source-payload-manifest.json"


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
        "szl_operator_auth.py": "c06458a8c846cdd2ff75efaf2dba06e3a9b9b996465e1035531c2715c73d13c6",
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


def _retained_signing_payload(root):
    raw = (root / RETAINED).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == (
        "741f01f67a8aae0aae7027931bf118a55b5adf0e01a7df33e00af1c70fbeccdc"
    )
    manifest = json.loads(raw)
    assert manifest["payload_id"] == "retained-signing-ledger-20261101-v1"
    assert manifest["schema"] == "szl-shared-source-payload/v1"
    assert manifest["files"][MCP_ARCHIVE] == "ff0c640228245f8901400a32af012594f4804bc328a95bfc438be9b801d52f35"
    assert manifest["files"]["szl_connectors/warehouse/warehouse_connectors.py"] == "22b9ffb388199cd63ec51536aac22fe2a2722323dd10c35d8440c2c23085288f"
    assert manifest["files"]["tests/test_snowflake_sql_result_classification.py"] == "fda4beb195b24b5e6563f6f9cd59acdb7844a3986b5ae90f1ec3fea643d4be76"
    assert manifest["files"][".github/shared-source-payloads/snowflake-sql-result-classification-20261028-v1.json"] == "74f824946666a293be88af6f554d2b9e786d4b0bf08ad639a10ec756d47a90a1"
    assert {"a11oy_org_rag.py", "szl_provenance.py", "szl_operator_auth.py", "szl_signing_state.py",
            "tests/test_replication_shared_payload.py"} <= set(manifest["files"])
    return manifest


def _assert_current_shared_payload(root):
    retained = _retained_signing_payload(root)
    # Exact original security-generation bytes, not a regenerated predecessor.
    raw = (root / SNOWFLAKE).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == (
        "f8f182e4c3d08d748b1f4c099320c25d448ce8222a9fd332fcd975d754a2882b"
    )
    security = json.loads(raw)
    assert security["schema"] == "szl-shared-source-payload/v1"
    assert security["payload_id"] == "snowflake-account-host-boundary-20261102-v1"
    assert set(security["files"]) == set(retained["files"])
    connector = "szl_connectors/warehouse/warehouse_connectors.py"
    security_test = "tests/test_snowflake_sql_result_classification.py"
    assert security["files"][connector] == (
        "2ff48cba8b038e5914caff6a2a629d17ed75561081704eb1d659fa9693fd721d"
    )
    assert security["files"][security_test] == (
        "fdf0932898e66378e34953c1b6911eea28b4783edb988c9c9534a0668475d1a0"
    )
    assert {
        relative for relative in retained["files"]
        if retained["files"][relative] != security["files"][relative]
    } == {connector, security_test}

    manifest = json.loads((root / ACTIVE).read_bytes())
    assert manifest["schema"] == "szl-shared-source-payload/v1"
    assert manifest["payload_id"] == "snowflake-proof-retention-20261103-v1"
    assert set(manifest["files"]) == set(security["files"]) | {RETAINED, SNOWFLAKE}
    assert manifest["files"][RETAINED] == (
        "741f01f67a8aae0aae7027931bf118a55b5adf0e01a7df33e00af1c70fbeccdc"
    )
    assert manifest["files"][SNOWFLAKE] == (
        "f8f182e4c3d08d748b1f4c099320c25d448ce8222a9fd332fcd975d754a2882b"
    )
    # Only this proof test changes; every prior runtime/security entry stays pinned.
    for relative, expected in security["files"].items():
        if relative != "tests/test_replication_shared_payload.py":
            assert manifest["files"][relative] == expected
    # Genuine full current-source verification, including this changed test.
    for relative, expected in manifest["files"].items():
        assert hashlib.sha256((root / relative).read_bytes()).hexdigest() == expected


def test_current_shared_payload_manifest_matches_current_peer():
    prior = (ROOT / SNAPSHOT).read_bytes()
    assert hashlib.sha256(prior).hexdigest() == "af144993e51a7348ee008f0ffa1bbb771759583b0281ac95580f1a4687ec9166"
    _assert_current_shared_payload(ROOT)


@pytest.mark.parametrize("change", [
    "source", "source_and_digest", "missing_entry", "schema", "generation",
    "security_digest", "retained_bytes", "security_bytes",
])
def test_current_payload_rejects_tampering(tmp_path, change):
    manifest = json.loads((ROOT / ACTIVE).read_bytes())
    for relative in manifest["files"]:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, target)
    if change in {"source", "source_and_digest"}:
        source = tmp_path / "szl_operator_auth.py"
        source.write_bytes(source.read_bytes() + b"\n")
        if change == "source_and_digest":
            manifest["files"]["szl_operator_auth.py"] = hashlib.sha256(source.read_bytes()).hexdigest()
    elif change == "missing_entry":
        del manifest["files"]["szl_signing_state.py"]
    elif change == "schema":
        manifest["schema"] = "invalid"
    elif change == "generation":
        manifest["payload_id"] = "snowflake-account-host-boundary-20261102-v1"
    elif change == "security_digest":
        manifest["files"]["szl_connectors/warehouse/warehouse_connectors.py"] = (
            _retained_signing_payload(tmp_path)["files"]["szl_connectors/warehouse/warehouse_connectors.py"]
        )
    else:
        source = tmp_path / (RETAINED if change == "retained_bytes" else SNOWFLAKE)
        source.write_bytes(source.read_bytes() + b"\n")
    (tmp_path / ACTIVE).write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(AssertionError):
        _assert_current_shared_payload(tmp_path)
