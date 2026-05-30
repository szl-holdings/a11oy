#!/usr/bin/env python3
"""Validate the GitHub Enterprise access checklist."""

from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CHECKLIST = REPO_ROOT / "docs" / "github-enterprise-access-checklist.json"


def main() -> int:
    errors: list[str] = []
    data = json.loads(CHECKLIST.read_text(encoding="utf-8"))

    if data.get("seatsAloneGrantWriteAccess") is not False:
        errors.append("seatsAloneGrantWriteAccess must be false")

    if data.get("currentKnownWritableRepo") != "szl-holdings/a11oy":
        errors.append("currentKnownWritableRepo must be szl-holdings/a11oy")

    rule = data.get("canonicalRule", "").lower()
    for phrase in ["accepted org membership", "repo/team write permission", "token or github app scope"]:
        if phrase not in rule:
            errors.append(f"canonicalRule must mention {phrase!r}")

    scopes = " ".join(data.get("requiredTokenScopes", [])).lower()
    for required in ["contents: read and write", "sso authorization"]:
        if required not in scopes:
            errors.append(f"requiredTokenScopes must mention {required!r}")

    checks = data.get("readOnlyChecks", [])
    if not isinstance(checks, list) or not checks:
        errors.append("readOnlyChecks must be a non-empty list")
    for command in checks:
        if not isinstance(command, str) or not command.startswith("gh "):
            errors.append(f"readOnlyChecks must use gh read-only commands, got {command!r}")
        forbidden = [" pr create", " pr merge", " issue create", " repo edit", " api -X PATCH", " api -X POST", " api -X PUT", " api -X DELETE"]
        if any(token in command for token in forbidden):
            errors.append(f"readOnlyChecks contains write-like command: {command}")

    targets = data.get("targetRepos", [])
    if not isinstance(targets, list) or len(targets) < 8:
        errors.append("targetRepos must include the sibling repos needed for cross-repo phases")
        targets = []

    repos = set()
    for target in targets:
        repo = target.get("repo")
        if repo in repos:
            errors.append(f"duplicate target repo: {repo}")
        repos.add(repo)
        if target.get("minimumPermission") != "write":
            errors.append(f"{repo}: minimumPermission must be write")
        for field in ["phaseUnlocked", "currentFallback"]:
            if not target.get(field):
                errors.append(f"{repo}: missing {field}")

    for required_repo in [
        "szl-holdings/.github",
        "szl-holdings/lutar-lean",
        "szl-holdings/agi-forecast",
        "szl-holdings/uds-mesh",
        "szl-holdings/vessels",
    ]:
        if required_repo not in repos:
            errors.append(f"missing target repo: {required_repo}")

    boundaries = " ".join(data.get("doctrineBoundaries", [])).lower()
    for phrase in ["do not commit tokens", "do not claim all lean green", "do not claim defense unicorns endorsement"]:
        if phrase not in boundaries:
            errors.append(f"doctrineBoundaries must include {phrase!r}")

    if errors:
        print("GitHub access checklist validation failed:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print(f"Validated {CHECKLIST.relative_to(REPO_ROOT)} ({len(targets)} target repos)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
