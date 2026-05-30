#!/usr/bin/env python3
"""Read-only GitHub access audit for cross-repo execution readiness.

This script observes the current gh authentication context and target-repo
viewer permissions from docs/github-enterprise-access-checklist.json. It never
pushes, opens pull requests, edits repos, mutates teams, or calls write-method
GitHub APIs.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
CHECKLIST = REPO_ROOT / "docs" / "github-enterprise-access-checklist.json"
PERMISSION_RANK = {
    "": 0,
    "NONE": 0,
    "READ": 1,
    "TRIAGE": 1,
    "WRITE": 2,
    "MAINTAIN": 3,
    "ADMIN": 4,
}
WRITE_READY = {"WRITE", "MAINTAIN", "ADMIN"}
ALLOWED_STATUSES = {"write-ready", "read-only", "unavailable", "error"}


def run_gh(args: list[str]) -> tuple[int, str, str]:
    command = ["gh", *args]
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return completed.returncode, completed.stdout.strip(), completed.stderr.strip()


def sanitize_error(value: str) -> str:
    return value.replace("\n", " ")[:500]


def permission_meets_minimum(viewer_permission: str, minimum: str) -> bool:
    minimum = minimum.upper()
    viewer = viewer_permission.upper()
    if minimum == "WRITE":
        return viewer in WRITE_READY
    return PERMISSION_RANK.get(viewer, 0) >= PERMISSION_RANK.get(minimum, 0)


def repo_status(viewer_permission: str, exit_code: int) -> str:
    if exit_code != 0:
        return "unavailable"
    permission = viewer_permission.upper()
    if permission in WRITE_READY:
        return "write-ready"
    return "read-only"


def audit(checklist_path: Path) -> dict[str, Any]:
    checklist = json.loads(checklist_path.read_text(encoding="utf-8"))

    auth_code, auth_stdout, auth_stderr = run_gh(["auth", "status"])
    user_code, user_stdout, user_stderr = run_gh(["api", "user", "-q", ".login"])
    viewer = {
        "login": user_stdout if user_code == 0 else None,
        "source": "gh api user -q .login",
        "error": sanitize_error(user_stderr) if user_code != 0 else None,
    }

    repos = []
    for target in checklist.get("targetRepos", []):
        repo = target["repo"]
        command_args = [
            "repo",
            "view",
            repo,
            "--json",
            "viewerPermission,nameWithOwner,isPrivate,defaultBranchRef",
        ]
        code, stdout, stderr = run_gh(command_args)
        viewer_permission = ""
        raw: dict[str, Any] | None = None
        if code == 0 and stdout:
            try:
                raw = json.loads(stdout)
                viewer_permission = str(raw.get("viewerPermission") or "")
            except json.JSONDecodeError:
                code = 1
                stderr = "gh returned non-JSON output"

        minimum = target.get("minimumPermission", "write")
        meets = permission_meets_minimum(viewer_permission, minimum)
        repos.append(
            {
                "repo": repo,
                "minimumPermission": minimum,
                "viewerPermission": viewer_permission or None,
                "meetsMinimumPermission": meets,
                "phaseUnlocked": target.get("phaseUnlocked"),
                "currentFallback": target.get("currentFallback"),
                "ghCommand": "gh " + " ".join(command_args),
                "status": repo_status(viewer_permission, code) if code == 0 else "unavailable",
                "error": sanitize_error(stderr) if code != 0 else None,
                "isPrivate": raw.get("isPrivate") if raw else None,
                "defaultBranch": raw.get("defaultBranchRef", {}).get("name") if raw and raw.get("defaultBranchRef") else None,
            }
        )

    summary = {
        "total": len(repos),
        "writeReady": sum(1 for repo in repos if repo["status"] == "write-ready"),
        "readOnly": sum(1 for repo in repos if repo["status"] == "read-only"),
        "unavailable": sum(1 for repo in repos if repo["status"] == "unavailable"),
        "errors": sum(1 for repo in repos if repo["status"] == "error"),
    }

    return {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "checklistPath": str(checklist_path.relative_to(REPO_ROOT)),
        "viewer": viewer,
        "auth": {
            "ghAuthStatusExitCode": auth_code,
            "authenticated": auth_code == 0,
            "stdout": auth_stdout,
            "error": sanitize_error(auth_stderr) if auth_code != 0 else None,
        },
        "repos": repos,
        "summary": summary,
        "failureBoundaries": checklist.get("doctrineBoundaries", []),
    }


def validate_output(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required_top = {"schemaVersion", "generatedAt", "checklistPath", "viewer", "auth", "repos", "summary", "failureBoundaries"}
    missing = sorted(required_top - data.keys())
    if missing:
        errors.append(f"missing top-level fields: {', '.join(missing)}")

    repos = data.get("repos", [])
    if not isinstance(repos, list) or not repos:
        errors.append("repos must be a non-empty list")
        repos = []

    for repo in repos:
        status = repo.get("status")
        if status not in ALLOWED_STATUSES:
            errors.append(f"{repo.get('repo', '<unknown>')}: unknown status {status!r}")
        if repo.get("minimumPermission") == "write":
            permission = str(repo.get("viewerPermission") or "").upper()
            expected = permission in WRITE_READY
            if bool(repo.get("meetsMinimumPermission")) != expected:
                errors.append(f"{repo.get('repo', '<unknown>')}: meetsMinimumPermission does not match viewerPermission")
        command = str(repo.get("ghCommand") or "")
        if not command.startswith("gh repo view "):
            errors.append(f"{repo.get('repo', '<unknown>')}: ghCommand must be read-only repo view")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checklist", default=str(CHECKLIST), help="Path to access checklist JSON")
    parser.add_argument("--output", required=True, help="Where to write audit JSON")
    parser.add_argument("--validate", action="store_true", help="Validate the emitted output shape")
    args = parser.parse_args()

    checklist_path = Path(args.checklist)
    if not checklist_path.is_absolute():
        checklist_path = REPO_ROOT / checklist_path
    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = REPO_ROOT / output_path

    data = audit(checklist_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    if args.validate:
        errors = validate_output(data)
        if errors:
            print("GitHub access live audit output validation failed:")
            for error in errors:
                print(f"  - {error}")
            return 1

    print(f"Wrote GitHub access audit: {output_path}")
    print(
        "Summary: "
        f"{data['summary']['writeReady']} write-ready, "
        f"{data['summary']['readOnly']} read-only, "
        f"{data['summary']['unavailable']} unavailable"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
