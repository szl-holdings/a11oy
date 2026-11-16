#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""SIMULATED producers test the actual manifest-to-browser readiness boundary."""

from copy import deepcopy
import json
import re
import shutil
import subprocess

import pytest

import a11oy_frontier_page as page
import szl_frontier_manifest as manifest


@pytest.fixture(scope="module")
def browser_validator():
    html = page._page_html("a11oy")
    schema = re.search(r"const CAPABILITY_READINESS_SCHEMA = [^;]+;", html)
    function = re.search(
        r"function capabilityReadiness\(value\) \{.*?^\}", html, re.M | re.S
    )
    assert schema and function, "the served page must expose its readiness validator"
    return (
        "const fs = require('node:fs');\n"
        + schema.group() + "\n" + function.group()
        + "\nprocess.stdout.write(JSON.stringify(capabilityReadiness("
        "JSON.parse(fs.readFileSync(0, 'utf8')))));"
    )


@pytest.mark.parametrize(
    "reasons,expected",
    [
        (["   "], ["invalid_operational_evidence_reason"]),
        ([""], ["invalid_operational_evidence_reason"]),
        ([None], ["invalid_operational_evidence_reason"]),
        ([7], ["invalid_operational_evidence_reason"]),
        ([False], ["invalid_operational_evidence_reason"]),
        ([{}], ["invalid_operational_evidence_reason"]),
        ([["nested"]], ["invalid_operational_evidence_reason"]),
        (
            ["operator_stopped", "  ", 7, "operator_stopped", "signer_not_ready"],
            ["operator_stopped", "invalid_operational_evidence_reason", "signer_not_ready"],
        ),
        ([], ["explicit_operational_evidence_not_satisfied"]),
        (None, ["explicit_operational_evidence_not_satisfied"]),
        ("unstructured", ["explicit_operational_evidence_not_satisfied"]),
    ],
)
def test_unmet_reason_projection_is_accepted_by_the_actual_browser_validator(
    monkeypatch, browser_validator, reasons, expected
):
    source = {
        "name": "SIMULATED blocked source",
        "category": "test",
        "label": manifest.MEASURED,
        "status": "OK",
        "ok": True,
        "provenance": {"endpoint": "/api/test/evidence"},
        "operational_evidence": {
            "predicate": "SIMULATED bounded condition",
            "satisfied": False,
            "reasons": reasons,
        },
    }
    original = deepcopy(source)
    sibling = {
        **source,
        "name": "SIMULATED available sibling",
        "operational_evidence": {
            "predicate": "SIMULATED sibling condition", "satisfied": True, "reasons": []
        },
    }
    monkeypatch.setattr(
        manifest, "_TILE_SPECS",
        [(lambda: source, source["name"], "test", source["provenance"])],
    )
    monkeypatch.setattr(manifest, "_concept_tile_inference_provenance", lambda: sibling)

    result = manifest._build_manifest()
    explanation = result["capabilities"][0]["operational_readiness"]
    summary = result["summary"]["operational_readiness"]

    assert source == original
    assert explanation["ready"] is False and explanation["state"] == "NOT_READY"
    assert explanation["source_reachable"] is True
    assert explanation["reasons"] == expected
    assert summary["ready"] is False
    assert summary["blocked_tiles"] == [
        {"name": source["name"], "ready": False, "reasons": expected}
    ]
    assert summary["ready_tiles"] == [sibling["name"]]

    node = shutil.which("node")
    assert node, "Node is required to execute the served browser readiness validator"
    run = subprocess.run(
        [node, "-e", browser_validator],
        input=json.dumps(explanation),
        text=True,
        encoding="utf-8",
        capture_output=True,
        timeout=15,
        check=False,
    )
    assert run.returncode == 0, run.stdout + run.stderr
    assert json.loads(run.stdout) == explanation
