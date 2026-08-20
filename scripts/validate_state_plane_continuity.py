#!/usr/bin/env python3
"""Validate the checked-in state-plane ownership and claim boundaries."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "docs" / "state-plane-continuity.v1.json"
MATURITY_LABELS = {"PROVEN", "MEASURED", "MODELED", "CONJECTURE", "OPEN"}


class ContinuityError(ValueError):
    """Raised when a state-plane manifest collapses independent authorities."""


def validate_manifest(document: dict[str, Any]) -> dict[str, Any]:
    if document.get("schema") != "szl.state-plane-continuity/v1":
        raise ContinuityError("unsupported state-plane continuity schema")

    planes = document.get("planes")
    if not isinstance(planes, list) or not planes:
        raise ContinuityError("planes must be a non-empty list")

    plane_ids = [plane.get("id") for plane in planes]
    if len(plane_ids) != len(set(plane_ids)):
        raise ContinuityError("plane ids must be unique")

    by_id = {plane["id"]: plane for plane in planes}
    required = {
        "a11oy-product",
        "a11oy-net-public-pages",
        "unified-control-hub-replit",
    }
    missing = sorted(required - set(by_id))
    if missing:
        raise ContinuityError(f"missing required planes: {', '.join(missing)}")

    for plane in planes:
        if plane.get("maturity") not in MATURITY_LABELS:
            raise ContinuityError(f"invalid maturity for {plane.get('id')}")

    pages = by_id["a11oy-net-public-pages"]
    if pages.get("canonical_url") != "https://a11oy.net":
        raise ContinuityError("the public Pages plane must own https://a11oy.net")
    if pages.get("owner") != "szl-holdings/a11oy-net":
        raise ContinuityError("the public Pages plane must remain repo-owned")

    replit = by_id["unified-control-hub-replit"]
    if replit.get("canonical_url") == "https://a11oy.net":
        raise ContinuityError("Replit must not claim the public Pages host")
    if replit.get("maturity") != "OPEN":
        raise ContinuityError("unverified Replit runtime must remain OPEN")
    if "UNVERIFIED" not in str(replit.get("operational_state")):
        raise ContinuityError("Replit operational state must disclose no receipt")

    selected = document.get("selected_replit_app") or {}
    if selected.get("source_identity") != {
        "repository": None,
        "branch": None,
        "commit": None,
    }:
        raise ContinuityError("unknown Replit source identity must stay explicit")
    if selected.get("runtime_state") != "UNVERIFIED":
        raise ContinuityError("Replit runtime may not be promoted without evidence")
    if selected.get("connector_inspection_state") not in {
        "EMPTY_RESPONSE",
        "PAUSED_EMPTY_RESPONSE",
    }:
        raise ContinuityError("unexpected Replit connector evidence state")

    anatomy = document.get("anatomy_v6") or {}
    if anatomy.get("maturity") != "MEASURED":
        raise ContinuityError("Anatomy v6 must remain MEASURED while alignment is open")
    deployment = anatomy.get("deployment") or {}
    if deployment.get("alignment_state") != "PENDING_GITHUB_SYNC":
        raise ContinuityError("update the snapshot and evidence before changing alignment")
    if deployment.get("declared_source_commit") == anatomy.get("source_commit"):
        raise ContinuityError("snapshot says alignment is pending but commits match")

    return {
        "schema": document["schema"],
        "plane_count": len(planes),
        "plane_ids": plane_ids,
        "replit_state": selected["runtime_state"],
        "anatomy_state": anatomy["operational_state"],
        "valid": True,
    }


def load_and_validate(path: Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return validate_manifest(json.load(handle))


if __name__ == "__main__":
    print(json.dumps(load_and_validate(), indent=2, sort_keys=True))
