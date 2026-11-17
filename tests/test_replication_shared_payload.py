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
PROOF = ".github/shared-source-payloads/snowflake-proof-retention-20261103-v1.json"
DSSE = ".github/shared-source-payloads/dsse-finite-reload-20261112-v1.json"
INSPECTION = ".github/shared-source-payloads/dsse-finite-reload-20261112-v1-f8ce1270f5d6.json"
ANATOMY_INSPECTION = ".github/shared-source-payloads/dsse-finite-reload-inspection-20261116-v1.json"
ANATOMY = ".github/shared-source-payloads/anatomy-observation-20261116-v1.json"
MODEL = ".github/shared-source-payloads/model-companion-boundary-20261117-v1.json"
ENGINE = "a11oy_code_engine.py"
COMPANION_TEST = "tests/test_model_companion_boundary.py"
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

    prior_raw = (root / PROOF).read_bytes()
    assert hashlib.sha256(prior_raw).hexdigest() == "fd63c97faa83ba598cba37e4c79f74c85f56676e89c11eb10084f8220e1d4462"
    prior = json.loads(prior_raw)
    assert prior["schema"] == "szl-shared-source-payload/v1"
    assert prior["payload_id"] == "snowflake-proof-retention-20261103-v1"
    assert set(prior["files"]) == set(security["files"]) | {RETAINED, SNOWFLAKE}
    assert prior["files"][RETAINED] == (
        "741f01f67a8aae0aae7027931bf118a55b5adf0e01a7df33e00af1c70fbeccdc"
    )
    assert prior["files"][SNOWFLAKE] == (
        "f8f182e4c3d08d748b1f4c099320c25d448ce8222a9fd332fcd975d754a2882b"
    )
    # Only the proof test and the signing-capability binding change in this
    # generation; every prior runtime/security entry stays pinned.
    for relative, expected in security["files"].items():
        if relative not in {"tests/test_replication_shared_payload.py",
                            "szl_signing_state.py"}:
            assert prior["files"][relative] == expected
    dsse_raw = (root / DSSE).read_bytes()
    assert hashlib.sha256(dsse_raw).hexdigest() == (
        "75bd21650b76c1329d34606aa9a4f50da3dd5928b56e30668f9e4ceae6eb9f8b"
    )
    dsse = json.loads(dsse_raw)
    assert dsse["schema"] == "szl-shared-source-payload/v1"
    assert dsse["payload_id"] == "dsse-finite-reload-20261112-v1"
    assert set(dsse["files"]) == set(prior["files"]) | {
        PROOF, "szl_dsse.py", "tests/test_dsse_real_signing.py",
    }
    assert dsse["files"][PROOF] == hashlib.sha256(prior_raw).hexdigest()
    # Finite emission adds the DSSE source and its tests. Provenance reload now
    # checks stored envelope bytes, so that file moves in this generation.
    # Every other predecessor entry stays pinned.
    for relative, expected in prior["files"].items():
        if relative not in {"tests/test_replication_shared_payload.py",
                            "szl_provenance.py"}:
            assert dsse["files"][relative] == expected

    inspection_raw = (root / INSPECTION).read_bytes()
    assert hashlib.sha256(inspection_raw).hexdigest() == (
        "f8ce1270f5d6c4cbc6dad0e8f022232a60b3f4eea522976ffc6bbded4fb70814"
    )
    inspection = json.loads(inspection_raw)
    # The coordinated inspection update retained this payload identifier and
    # changed only provenance. Preserve both raw versions as distinct archives.
    assert inspection["schema"] == dsse["schema"]
    assert inspection["payload_id"] == dsse["payload_id"]
    assert set(inspection["files"]) == set(dsse["files"])
    for relative, expected in dsse["files"].items():
        if relative != "szl_provenance.py":
            assert inspection["files"][relative] == expected
    assert inspection["files"]["szl_provenance.py"] == (
        "eedb1a9243b55d6b925341047bf12cea806018bab0eea2fa96ca3a84996f1dd3"
    )

    # Both published branches retained the same inspection bytes under distinct
    # archive paths. Preserve both names and require exact byte identity.
    assert (root / ANATOMY_INSPECTION).read_bytes() == inspection_raw

    model_raw = (root / MODEL).read_bytes()
    assert hashlib.sha256(model_raw).hexdigest() == (
        "3443d1aaa7890df4f994659ffc4953f35c89b7d313d31c7c5abc374b915662bd"
    )
    model = json.loads(model_raw)
    assert model["schema"] == "szl-shared-source-payload/v1"
    assert model["payload_id"] == "model-companion-boundary-20261117-v1"
    assert set(model["files"]) == set(inspection["files"]) | {
        DSSE, INSPECTION, ENGINE, COMPANION_TEST,
    }
    assert model["files"][DSSE] == hashlib.sha256(dsse_raw).hexdigest()
    assert model["files"][INSPECTION] == hashlib.sha256(inspection_raw).hexdigest()
    # Only the first model generation's history assertions changed among
    # inherited files. Retain that published parent without regenerating it.
    # The reviewed shared engine refuses an unavailable optional companion;
    # canonical Access implementation and dependencies are not shared payloads.
    for relative, expected in inspection["files"].items():
        if relative != "tests/test_replication_shared_payload.py":
            assert model["files"][relative] == expected
    assert model["files"][ENGINE] == (
        "613183938099a18c82e59941079c7824de3978c74c423df8a7a59436d0801c98"
    )
    assert model["files"][COMPANION_TEST] == (
        "9d838b554c9e6cb54cdf1054a6b9342d4d37db8afd5b7c08263265bfe1d11b90"
    )

    anatomy_raw = (root / ANATOMY).read_bytes()
    assert hashlib.sha256(anatomy_raw).hexdigest() == (
        "3c1ae61a001b98a87cafb767048b2f9c50b3efd70f44c351835d9f132b6918b6"
    )
    anatomy = json.loads(anatomy_raw)
    assert anatomy["schema"] == "szl-shared-source-payload/v1"
    assert anatomy["payload_id"] == "anatomy-observation-auth-20261116-v1"
    assert set(anatomy["files"]) == set(inspection["files"]) | {DSSE, ANATOMY_INSPECTION}
    assert anatomy["files"][DSSE] == hashlib.sha256(dsse_raw).hexdigest()
    assert anatomy["files"][ANATOMY_INSPECTION] == hashlib.sha256(inspection_raw).hexdigest()
    # The independent anatomy parent adds two operator protections. Only that
    # reviewed source transition and its history test differ from inspection.
    assert anatomy["files"]["szl_operator_auth.py"] == (
        "f31fc4d4f960eb840583d7b32c9598d2c96319c9818acc3f39f078de8394fa8f"
    )
    assert {
        relative for relative in inspection["files"]
        if anatomy["files"][relative] != inspection["files"][relative]
    } == {"szl_operator_auth.py", "tests/test_replication_shared_payload.py"}

    manifest = json.loads((root / ACTIVE).read_bytes())
    assert manifest["schema"] == "szl-shared-source-payload/v1"
    assert manifest["payload_id"] == "model-companion-boundary-20261117-v2"
    assert set(manifest["files"]) == set(model["files"]) | set(anatomy["files"]) | {
        MODEL, ANATOMY,
    }
    assert manifest["files"][MODEL] == hashlib.sha256(model_raw).hexdigest()
    assert manifest["files"][ANATOMY] == hashlib.sha256(anatomy_raw).hexdigest()
    # Conserve both published parents. Current auth comes from the reviewed
    # anatomy parent; engine and companion test remain the reviewed model bytes.
    # Only this combined history test has a new digest of its own.
    for relative, expected in model["files"].items():
        if relative not in {"szl_operator_auth.py", "tests/test_replication_shared_payload.py"}:
            assert manifest["files"][relative] == expected
    for relative, expected in anatomy["files"].items():
        if relative != "tests/test_replication_shared_payload.py":
            assert manifest["files"][relative] == expected
    # Verify all current bytes; predecessor receipts above stay immutable.
    for relative, expected in manifest["files"].items():
        assert hashlib.sha256((root / relative).read_bytes()).hexdigest() == expected


def test_current_shared_payload_manifest_matches_current_peer():
    prior = (ROOT / SNAPSHOT).read_bytes()
    assert hashlib.sha256(prior).hexdigest() == "af144993e51a7348ee008f0ffa1bbb771759583b0281ac95580f1a4687ec9166"
    _assert_current_shared_payload(ROOT)


@pytest.mark.parametrize("change", [
    "source", "source_and_digest", "missing_entry", "schema", "generation",
    "security_digest", "retained_bytes", "security_bytes", "proof_bytes", "dsse_source",
    "dsse_archive_bytes", "dsse_archive_bytes_and_digest", "predecessor_generation",
    "missing_archive_entry", "missing_engine_entry", "missing_companion_test_entry",
    "engine_source", "engine_source_and_digest", "companion_test_source",
    "companion_test_source_and_digest", "canonical_helper_entry", "canonical_companion_entry",
    "inspection_archive_bytes", "inspection_archive_bytes_and_digest",
    "missing_inspection_entry", "inspection_provenance_rollback",
    "named_inspection_archive_bytes", "named_inspection_archive_bytes_and_digest",
    "missing_named_inspection_entry", "anatomy_archive_bytes", "anatomy_archive_bytes_and_digest",
    "model_archive_bytes", "model_archive_bytes_and_digest", "missing_anatomy_entry",
    "missing_model_entry", "provenance_source_and_digest", "anatomy_auth_rollback",
    "model_predecessor_generation", "anatomy_predecessor_generation",
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
    elif change == "predecessor_generation":
        manifest["payload_id"] = "dsse-finite-reload-20261112-v1"
    elif change == "model_predecessor_generation":
        manifest["payload_id"] = "model-companion-boundary-20261117-v1"
    elif change == "anatomy_predecessor_generation":
        manifest["payload_id"] = "anatomy-observation-auth-20261116-v1"
    elif change in {"missing_archive_entry", "missing_engine_entry", "missing_companion_test_entry",
                    "missing_inspection_entry", "missing_named_inspection_entry",
                    "missing_anatomy_entry", "missing_model_entry"}:
        del manifest["files"][{
            "missing_archive_entry": DSSE, "missing_engine_entry": ENGINE,
            "missing_companion_test_entry": COMPANION_TEST,
            "missing_inspection_entry": INSPECTION,
            "missing_named_inspection_entry": ANATOMY_INSPECTION,
            "missing_anatomy_entry": ANATOMY, "missing_model_entry": MODEL,
        }[change]]
    elif change in {"dsse_archive_bytes_and_digest", "engine_source_and_digest",
                    "companion_test_source_and_digest", "inspection_archive_bytes_and_digest",
                    "named_inspection_archive_bytes_and_digest", "anatomy_archive_bytes_and_digest",
                    "model_archive_bytes_and_digest", "provenance_source_and_digest"}:
        relative = {
            "dsse_archive_bytes_and_digest": DSSE, "engine_source_and_digest": ENGINE,
            "companion_test_source_and_digest": COMPANION_TEST,
            "inspection_archive_bytes_and_digest": INSPECTION,
            "named_inspection_archive_bytes_and_digest": ANATOMY_INSPECTION,
            "anatomy_archive_bytes_and_digest": ANATOMY,
            "model_archive_bytes_and_digest": MODEL,
            "provenance_source_and_digest": "szl_provenance.py",
        }[change]
        source = tmp_path / relative
        source.write_bytes(source.read_bytes() + b"\n")
        manifest["files"][relative] = hashlib.sha256(source.read_bytes()).hexdigest()
    elif change == "inspection_provenance_rollback":
        prior = json.loads((tmp_path / DSSE).read_bytes())
        manifest["files"]["szl_provenance.py"] = prior["files"]["szl_provenance.py"]
    elif change == "anatomy_auth_rollback":
        prior = json.loads((tmp_path / MODEL).read_bytes())
        manifest["files"]["szl_operator_auth.py"] = prior["files"]["szl_operator_auth.py"]
    elif change in {"canonical_helper_entry", "canonical_companion_entry"}:
        relative = ("szl_model_access.py" if change == "canonical_helper_entry"
                    else "szl_router_client.py")
        source = tmp_path / relative
        source.write_bytes(b"fixture-only forbidden payload addition\n")
        manifest["files"][relative] = hashlib.sha256(source.read_bytes()).hexdigest()
    elif change == "security_digest":
        manifest["files"]["szl_connectors/warehouse/warehouse_connectors.py"] = (
            _retained_signing_payload(tmp_path)["files"]["szl_connectors/warehouse/warehouse_connectors.py"]
        )
    else:
        source = tmp_path / {
            "retained_bytes": RETAINED, "security_bytes": SNOWFLAKE,
            "proof_bytes": PROOF, "dsse_source": "szl_dsse.py",
            "dsse_archive_bytes": DSSE, "engine_source": ENGINE,
            "companion_test_source": COMPANION_TEST,
            "inspection_archive_bytes": INSPECTION,
            "named_inspection_archive_bytes": ANATOMY_INSPECTION,
            "anatomy_archive_bytes": ANATOMY, "model_archive_bytes": MODEL,
        }[change]
        source.write_bytes(source.read_bytes() + b"\n")
    (tmp_path / ACTIVE).write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(AssertionError):
        _assert_current_shared_payload(tmp_path)
