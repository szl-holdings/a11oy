#!/usr/bin/env python3
"""Validate the original A11oy controls evidence map."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MAP_PATH = REPO_ROOT / "docs" / "controls-evidence-map.json"

ALLOWED_STATUSES = {
    "verified-runtime",
    "release-payload",
    "lean-backed-current-green",
    "lean-backed-needs-upstream-ci",
    "thesis-anchor",
    "historical",
    "roadmap",
}
CONTROL_ID = re.compile(r"^A11OY-CE-\d{3}$")
FORBIDDEN_HF = {"canonical", "source-of-truth"}
FORBIDDEN_UDS = {"catalog-grade", "catalog-accepted", "endorsed"}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    errors: list[str] = []
    data = load_json(MAP_PATH)

    if "no external control catalog" not in data.get("cleanRoomRule", "").lower():
        errors.append("cleanRoomRule must reject copied external control catalogs")

    controls = data.get("controls", [])
    if not isinstance(controls, list) or len(controls) < 5:
        errors.append("controls must contain at least five controls")
        controls = []

    seen: set[str] = set()
    required_fields = {
        "controlId",
        "title",
        "description",
        "claimStatus",
        "evidencePaths",
        "validationCommands",
        "receiptHook",
        "hfExposure",
        "udsExposure",
        "invariants",
    }

    for control in controls:
        control_id = control.get("controlId", "<missing>")
        if control_id in seen:
            errors.append(f"duplicate controlId: {control_id}")
        seen.add(control_id)

        if not CONTROL_ID.match(control_id):
            errors.append(f"{control_id}: controlId must match A11OY-CE-###")

        missing = sorted(required_fields - control.keys())
        if missing:
            errors.append(f"{control_id}: missing fields: {', '.join(missing)}")

        status = control.get("claimStatus")
        if status not in ALLOWED_STATUSES:
            errors.append(f"{control_id}: unsupported claimStatus {status!r}")

        evidence_paths = control.get("evidencePaths", [])
        if not isinstance(evidence_paths, list) or not evidence_paths:
            errors.append(f"{control_id}: evidencePaths must be a non-empty list")
        for evidence in evidence_paths:
            if not (REPO_ROOT / evidence).exists():
                errors.append(f"{control_id}: evidence path does not exist: {evidence}")

        commands = control.get("validationCommands", [])
        if not isinstance(commands, list) or not commands:
            errors.append(f"{control_id}: validationCommands must be a non-empty list")

        receipt_hook = control.get("receiptHook", {})
        if not receipt_hook.get("eventType") or not receipt_hook.get("status"):
            errors.append(f"{control_id}: receiptHook requires eventType and status")
        if receipt_hook.get("status") not in {"runtime-available", "roadmap", "staged"}:
            errors.append(f"{control_id}: unsupported receiptHook.status {receipt_hook.get('status')!r}")

        if status == "verified-runtime" and receipt_hook.get("status") != "runtime-available":
            errors.append(f"{control_id}: verified-runtime controls need runtime-available receipt hook")

        hf_exposure = control.get("hfExposure", "").lower()
        if hf_exposure in FORBIDDEN_HF:
            errors.append(f"{control_id}: hfExposure cannot be canonical/source-of-truth")

        uds_exposure = control.get("udsExposure", "").lower()
        if uds_exposure in FORBIDDEN_UDS:
            errors.append(f"{control_id}: udsExposure cannot imply catalog/endorsement")

        invariants = control.get("invariants", [])
        if not isinstance(invariants, list) or not invariants:
            errors.append(f"{control_id}: invariants must be a non-empty list")

    required = {"A11OY-CE-001", "A11OY-CE-002", "A11OY-CE-005", "A11OY-CE-008"}
    missing_required = sorted(required - seen)
    if missing_required:
        errors.append(f"missing required controls: {', '.join(missing_required)}")

    if errors:
        print("Controls evidence map validation failed:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print(f"Validated {MAP_PATH.relative_to(REPO_ROOT)} ({len(controls)} controls)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
