#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Preserve prior payload evidence when the active shared payload advances."""

import ast
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / ".github/shared-source-payloads/code-engine-attested-sandbox-20261013-v1.json"


def test_prior_active_manifest_is_retained_byte_exact():
    raw = ARCHIVE.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == "e22e38f740b2b0279a52f5caba6f99362b89f01575e44e9a32b3f2643cbb46bb"
    manifest = json.loads(raw)
    assert manifest["payload_id"] == "code-engine-attested-sandbox-20261013-v1"
    assert manifest["schema"] == "szl-shared-source-payload/v1"
    assert set(manifest["files"]) == {
        ".github/shared-source-payloads/code-engine-mandatory-rlimits-20261013-v1.json",
        "a11oy_code_engine.py",
        "tests/test_code_engine_mandatory_limits.py",
    }
    # Historical code hashes remain observations of the old source. Only the
    # archived predecessor is immutable across future runtime source changes.
    predecessor = ".github/shared-source-payloads/code-engine-mandatory-rlimits-20261013-v1.json"
    assert hashlib.sha256((ROOT / predecessor).read_bytes()).hexdigest() == manifest["files"][predecessor]


def test_prior_meter_manifest_fixture_retains_its_original_content_address():
    # Reproduce the earlier exact public manifest bytes. The historical source
    # remains in Git; this fixture is not a claim that the active slot is unchanged.
    prior = {
        "files": {"szl_meter_access.py": hashlib.sha256((ROOT / "szl_meter_access.py").read_bytes()).hexdigest()},
        "payload_id": "meter-selector-20261011-v1",
        "schema": "szl-shared-source-payload/v1",
    }
    raw = (json.dumps(prior, indent=2) + "\n").encode("utf-8")
    assert hashlib.sha256(raw).hexdigest() == "b8be768d9a012a941375ca852a7559dac02bdef530cfcd4e32abecfc0d74c1e0"


def test_archived_meter_and_bounded_engine_payload_remains_content_bound():
    raw = (ROOT / ".github/shared-source-payloads/code-engine-bounded-model-20261015-v1.json").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == "d8e50108743e7f02ac7b3c2af17e70c47e38922be3f4e214c5d98d1561c54ea6"
    manifest = json.loads(raw)
    assert manifest["payload_id"] == "code-engine-bounded-model-20261015-v1"
    assert manifest["schema"] == "szl-shared-source-payload/v1"
    assert manifest["files"] == {
        "a11oy_code_engine.py": "a03aa1c294b69c8dfe3ce20d85aaf2347fac93ad7cba3544c1697d381639ac6f",
        "szl_meter_access.py": hashlib.sha256((ROOT / "szl_meter_access.py").read_bytes()).hexdigest(),
    }
    for relative, expected in manifest["files"].items():
        if relative == "a11oy_code_engine.py":
            continue  # Historical engine bytes stay pinned above; the successor changes source.
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == expected


def test_archived_write_boundary_payload_preserves_prior_evidence():
    archive = ROOT / ".github/shared-source-payloads/execution-observer-operator-auth-20261016-v1.json"
    raw = archive.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == "7dbf4ab396a4add29d22e7870951198accb3833f7feb32e8eebf6b7906ce8f1c"
    manifest = json.loads(raw)
    assert manifest["schema"] == "szl-shared-source-payload/v1"
    assert manifest["payload_id"] == "execution-observer-operator-auth-20261016-v1"
    assert {
        ".github/shared-source-payloads/code-engine-bounded-model-20261015-v1.json",
        "szl_operator_auth.py", "szl_khipu_replicate.py", "szl_unay_routes.py",
    } <= set(manifest["files"])
    assert manifest["files"]["szl_khipu_replicate.py"] == "c3f1a5e76e7c6df0c19b932afca30d99fbdd12e508e95ed9f7dfa9fd798dbbf1"
    for relative, expected in manifest["files"].items():
        if relative == "szl_khipu_replicate.py":
            continue  # The original source remains pinned in this immutable archive.
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == expected


def test_archived_credential_payload_preserves_predecessor_and_source_digest():
    raw = (ROOT / ".github/shared-source-payloads/model-credential-origin-20261017-v1.json").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == "e0aefafd777d957b4bebee9a438dfea023f00fb6be5cb2863c255c4540c7b71c"
    manifest = json.loads(raw)
    assert manifest["schema"] == "szl-shared-source-payload/v1"
    assert manifest["payload_id"] == "model-credential-origin-20261017-v1"
    assert set(manifest["files"]) == {
        ".github/shared-source-payloads/execution-observer-operator-auth-20261016-v1.json",
        "a11oy_code_engine.py", "szl_khipu_replicate.py",
    }
    for relative, expected in manifest["files"].items():
        if relative == "a11oy_code_engine.py":
            assert expected == "60b196bc7118ffb08a9ddf3ca1a006026aec969d3a1a8f10a5b8a0e454acc8b7"
            continue  # The predecessor remains immutable while the catalog advances.
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == expected
    prior = {**manifest, "files": {key: value for key, value in manifest["files"].items()
                                  if key != "a11oy_code_engine.py"},
             "payload_id": "replication-payload-integrity-20261017-v1"}
    assert hashlib.sha256((json.dumps(prior, indent=2) + "\n").encode()).hexdigest() == (
        "1b8a4693d35e342ef47088d9fbebad580d05b8425cf9f3f90d32f0c00466c1cc"
    )


def test_active_bonsai_payload_preserves_prior_evidence_and_current_source():
    manifest = json.loads((ROOT / ".github/shared-source-payload-manifest.json").read_bytes())
    assert manifest["schema"] == "szl-shared-source-payload/v1"
    assert manifest["payload_id"] == "bonsai-model-catalog-20261017-v1"
    assert set(manifest["files"]) == {
        ".github/shared-source-payloads/execution-observer-operator-auth-20261016-v1.json",
        ".github/shared-source-payloads/model-credential-origin-20261017-v1.json",
        "a11oy_code_engine.py", "szl_khipu_replicate.py",
        "tests/test_model_endpoint_credentials.py", "docs/bonsai-model-binding.md",
    }
    for relative, expected in manifest["files"].items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == expected


def test_meter_selector_is_inactive_without_importing_the_runtime():
    source = ast.parse((ROOT / "szl_meter_access.py").read_text())
    assignments = [
        node for node in source.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "ACTIVE_METER2_TARGETS_SECRET"
                for target in node.targets)
    ]
    assert len(assignments) == 1
    assert isinstance(assignments[0].value, ast.Constant)
    assert assignments[0].value.value is None
