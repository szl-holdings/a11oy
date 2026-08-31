#!/usr/bin/env python3
"""Validate the tracked SZL ecosystem registry and optional local checkouts."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


REPO_ROOT = Path.cwd()
REGISTRY_PATH = REPO_ROOT / "docs" / "ecosystem-registry.json"
LOCAL_ROOT = REPO_ROOT / ".repos" / "szl-holdings"


def git_head(path: Path) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "-C", str(path), "rev-parse", "--short=12", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-local", action="store_true")
    args = parser.parse_args()

    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    repos = registry.get("repos", [])
    names = [repo["name"] for repo in repos]

    errors: list[str] = []
    if registry.get("canonicalHub") != "a11oy":
        errors.append("canonicalHub must be a11oy")
    if len(names) != len(set(names)):
        errors.append("repo names must be unique")
    if len(repos) < 19:
        errors.append("registry should cover all 19 visible public org repos")

    for repo in repos:
        for field in ["name", "tier", "readiness", "role", "github", "defaultBranch"]:
            if not repo.get(field):
                errors.append(f"{repo.get('name', '<unknown>')} missing {field}")
        if not str(repo.get("github", "")).startswith("https://github.com/szl-holdings/"):
            errors.append(f"{repo.get('name')} has non-SZL GitHub URL")

        local_name = repo["name"]
        local_path = LOCAL_ROOT / local_name
        if local_name == ".github":
            local_path = LOCAL_ROOT / ".github"
        if args.require_local and not (local_path / ".git").exists():
            errors.append(f"missing local checkout: {local_path}")

    if errors:
        print("Ecosystem audit failed:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print(f"Ecosystem audit passed: {len(repos)} repos tracked")
    if LOCAL_ROOT.exists():
        present = 0
        for repo in repos:
            local_path = LOCAL_ROOT / repo["name"]
            if repo["name"] == ".github":
                local_path = LOCAL_ROOT / ".github"
            head = git_head(local_path)
            if head:
                present += 1
        print(f"Local checkouts present: {present}/{len(repos)} under {LOCAL_ROOT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
