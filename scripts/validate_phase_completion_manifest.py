#!/usr/bin/env python3
"""Validate A11oy phase completion manifest."""

from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = REPO_ROOT / "docs" / "phase-completion-manifest.json"
REPORT = REPO_ROOT / "docs" / "PHASE_COMPLETION_REPORT.md"

ALLOWED_STATUSES = {
    "complete-for-current-branch",
    "runtime-helper-complete",
    "runtime-helper-complete-harness-staged",
    "schema-complete-no-live-score",
    "access-pending-handoff-queued",
    "generated-payload-ready",
}


def main() -> int:
    errors: list[str] = []
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))

    if not REPORT.exists():
        errors.append("PHASE_COMPLETION_REPORT.md is missing")

    rule = data.get("canonicalRule", "").lower()
    if "sibling repo phases remain access-pending" not in rule:
        errors.append("canonicalRule must keep sibling repo phases access-pending")
    if data.get("a11oyLocalStatus") != "complete-for-current-branch":
        errors.append("a11oyLocalStatus must be complete-for-current-branch")
    if data.get("crossRepoStatus") != "access-pending-handoff-queued":
        errors.append("crossRepoStatus must be access-pending-handoff-queued")

    forbidden = " ".join(data.get("forbiddenClaims", [])).lower()
    for phrase in ["zero sorry", "solved the benchmark", "uds catalog accepted", "hf is canonical"]:
        if phrase not in forbidden:
            errors.append(f"forbiddenClaims missing {phrase!r}")

    phases = data.get("phases", [])
    if not isinstance(phases, list) or len(phases) < 7:
        errors.append("phases must contain at least seven phase entries")
        phases = []

    seen: set[str] = set()
    for phase in phases:
        phase_id = phase.get("id", "<missing>")
        if phase_id in seen:
            errors.append(f"duplicate phase id: {phase_id}")
        seen.add(phase_id)
        if phase.get("status") not in ALLOWED_STATUSES:
            errors.append(f"{phase_id}: unsupported status {phase.get('status')!r}")
        artifacts = phase.get("artifacts", [])
        if not isinstance(artifacts, list) or not artifacts:
            errors.append(f"{phase_id}: artifacts must be non-empty")
        for artifact in artifacts:
            if not (REPO_ROOT / artifact).exists():
                errors.append(f"{phase_id}: artifact does not exist: {artifact}")
        commands = phase.get("validationCommands", [])
        if not isinstance(commands, list) or not commands:
            errors.append(f"{phase_id}: validationCommands must be non-empty")

    requires = " ".join(data.get("completionRequiresForSiblingRepos", [])).lower()
    for phrase in ["target repo write-ready access", "target ci green"]:
        if phrase not in requires:
            errors.append(f"completionRequiresForSiblingRepos missing {phrase!r}")

    if errors:
        print("Phase completion manifest validation failed:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print(f"Validated {MANIFEST.relative_to(REPO_ROOT)} ({len(phases)} phases)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
