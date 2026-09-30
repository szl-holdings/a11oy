# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "console" / "3d" / "aegis-proof-cells.html"
ASSET_DIR = ROOT / "console" / "3d" / "aegis-proof-cells"
REGISTRY = ASSET_DIR / "registry.json"
SCRIPT = ASSET_DIR / "app.mjs"
STYLES = ASSET_DIR / "styles.css"
DOC = ROOT / "docs" / "third-party" / "bricklayer-ai-intake-v1.md"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_registry_is_original_defensive_and_fail_closed() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    boundary = registry["bricklayer_boundary"]
    authority = registry["authority"]

    assert registry["schema"] == "szl.aegis-proof-cells.registry/v1"
    assert registry["operating_mode"] == "DEFENSIVE_READ_ONLY_INVESTIGATION_PLANNER"
    assert boundary["classification"] == "REFERENCE_ONLY_CLEAN_ROOM"
    assert boundary["official_public_code_repository_found"] is False
    assert boundary["proprietary_implementation_available"] is False
    assert boundary["source_code_copied"] is False
    assert boundary["website_copy_copied"] is False
    assert boundary["visual_identity_copied"] is False
    assert boundary["brand_identity_reused"] is False
    assert boundary["affiliation"] == "NONE"

    assert authority["default_effect"] == "DENY"
    assert authority["external_writes"] == "DISABLED"
    assert authority["effectors"] == []
    assert authority["automatic_retries"] == 0
    assert authority["credentials_accepted"] is False
    assert authority["secrets_persisted"] is False
    assert authority["cross_tenant_access"] == "DENIED"
    assert authority["offensive_intrusion"] == "DENIED"
    assert authority["destructive_remediation"] == "DENIED"
    assert authority["production_authorization"] is False


def test_cells_capsules_and_context_contract_are_complete() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    cells = registry["proof_cells"]
    capsules = registry["procedure_capsules"]
    cell_ids = {cell["id"] for cell in cells}

    assert len(cells) == 11
    assert len(cell_ids) == 11
    assert len(capsules) == 6
    assert registry["context_types"] == [
        "EVIDENTIARY",
        "PROCEDURAL",
        "INVESTIGATIVE",
        "DECISION",
        "OUTCOME",
    ]
    assert {capsule["mission"] for capsule in capsules} == {
        "alert-triage",
        "phishing",
        "endpoint",
        "vulnerability",
        "cloud",
        "threat-intel",
    }
    for capsule in capsules:
        assert capsule["cells"]
        assert set(capsule["cells"]) <= cell_ids


def test_public_references_are_bounded_and_no_code_is_claimed() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    observations = registry["public_architecture_observations"]
    standards = registry["standards_and_public_code"]

    assert len(observations) >= 6
    assert all(item["reuse_policy"] == "REFERENCE_ONLY" for item in observations)
    assert all(item["source"].startswith("https://www.bricklayer.ai/") for item in observations)
    assert all(item["source_code_copied"] is False for item in standards)
    assert {item["name"] for item in standards} == {
        "Open Cybersecurity Schema Framework",
        "MITRE ATT&CK STIX Data",
        "OpenTelemetry Specification",
        "Open Policy Agent",
    }

    doc = DOC.read_text(encoding="utf-8")
    assert "REFERENCE_ONLY_CLEAN_ROOM" in doc
    assert "No official public Bricklayer implementation repository was identified" in doc
    assert "No source from these projects is copied" in doc


def test_page_is_local_digest_bound_and_accessible() -> None:
    html = HTML.read_text(encoding="utf-8")
    css = STYLES.read_text(encoding="utf-8")
    js = SCRIPT.read_text(encoding="utf-8")

    assert 'data-szl-public-experience-v3="true"' in html
    assert 'data-aegis-proof-cells="v1"' in html
    assert 'class="skip"' in html
    assert 'aria-live="polite"' in html
    assert f"styles.css?v={_sha(STYLES)}" in html
    assert f"app.mjs?v={_sha(SCRIPT)}" in html
    assert _sha(REGISTRY) in html

    assert "https://" not in js
    assert "http://" not in js
    assert "innerHTML" not in js
    assert "eval(" not in js
    assert "new Function" not in js
    assert "credentials: \"same-origin\"" in js
    assert "redirect: \"error\"" in js

    for token in (
        "min-height: 48px",
        "overflow-x: hidden",
        "prefers-reduced-motion",
        "prefers-contrast: more",
        "forced-colors: active",
    ):
        assert token in css


def test_runtime_policy_markers_are_explicit() -> None:
    js = SCRIPT.read_text(encoding="utf-8")
    for token in (
        "TENANT_PASSPORT_REQUIRED",
        "CROSS_TENANT_SCOPE",
        "UNSUPPORTED_DEFENSIVE_MISSION",
        "PROHIBITED_ACTION",
        "EVIDENCE_NOT_FRESH",
        "HUMAN_APPROVAL_REQUIRED",
        "DEFENSIVE_PLAN_READY",
        "external_writes: \"DISABLED\"",
        "effectors: []",
        "production_authorization: false",
        "trust_ceiling: 0.97",
    ):
        assert token in js

    prohibited = re.search(r"const PROHIBITED_TOKENS = \[(.*?)\];", js, re.S)
    assert prohibited is not None
    for required in ("exploit", "exfiltrate", "credential theft", "deploy malware", "destructive"):
        assert required in prohibited.group(1)
