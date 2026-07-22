from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts.validate_state_plane_continuity import (
    ContinuityError,
    DEFAULT_MANIFEST,
    load_and_validate,
    validate_manifest,
)


def _manifest() -> dict:
    return json.loads(Path(DEFAULT_MANIFEST).read_text(encoding="utf-8"))


def test_checked_in_state_planes_are_separated() -> None:
    result = load_and_validate()
    assert result["valid"] is True
    assert result["plane_count"] == 3
    assert result["replit_state"] == "UNVERIFIED"
    assert result["anatomy_state"] == "MEASURED_LIVE_WITH_SOURCE_ALIGNMENT_OPEN"
    manifest = _manifest()
    assert manifest["selected_replit_app"]["connector_inspection_state"] == "PAUSED_EMPTY_RESPONSE"
    harness = manifest["anatomy_v6"]["alive_harness"]
    assert harness["signature_verified"] is True
    assert harness["verdict"] == "GREEN"
    assert harness["assertions"] == "32/32"
    assert harness["formula_gates"] == "10/10"
    module_match = manifest["anatomy_v6"]["deployment"]["v6_module_exact_match"]
    assert module_match["state"] == "MATCH"
    assert module_match["github_sha256"] == module_match["live_sha256"]


def test_replit_cannot_claim_public_pages_host() -> None:
    manifest = copy.deepcopy(_manifest())
    replit = next(
        plane for plane in manifest["planes"] if plane["id"] == "unified-control-hub-replit"
    )
    replit["canonical_url"] = "https://a11oy.net"
    with pytest.raises(ContinuityError, match="must not claim"):
        validate_manifest(manifest)


def test_unverified_replit_cannot_be_promoted() -> None:
    manifest = copy.deepcopy(_manifest())
    manifest["selected_replit_app"]["runtime_state"] = "LIVE_VERIFIED"
    with pytest.raises(ContinuityError, match="may not be promoted"):
        validate_manifest(manifest)


def test_anatomy_alignment_gap_cannot_be_hidden() -> None:
    manifest = copy.deepcopy(_manifest())
    manifest["anatomy_v6"]["maturity"] = "PROVEN"
    with pytest.raises(ContinuityError, match="must remain MEASURED"):
        validate_manifest(manifest)
