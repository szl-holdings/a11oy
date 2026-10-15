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


def test_active_meter_payload_remains_content_bound():
    raw = (ROOT / ".github/shared-source-payload-manifest.json").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == "b8be768d9a012a941375ca852a7559dac02bdef530cfcd4e32abecfc0d74c1e0"
    manifest = json.loads(raw)
    assert manifest["payload_id"] == "meter-selector-20261011-v1"
    assert set(manifest["files"]) == {"szl_meter_access.py"}
    assert hashlib.sha256((ROOT / "szl_meter_access.py").read_bytes()).hexdigest() == manifest["files"]["szl_meter_access.py"]


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
