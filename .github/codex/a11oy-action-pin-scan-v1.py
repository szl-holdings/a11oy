#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Require immutable SHA pins for external Actions in changed workflow files."""

import re
import subprocess
import sys
from pathlib import Path

USES = re.compile(r"^\s*-?\s*uses:\s*([^\s#]+)", re.MULTILINE)
FULL_SHA = re.compile(r"^[0-9a-fA-F]{40}$")


def changed_workflows() -> list[Path]:
    paths: list[Path] = []
    for command in (
        ["git", "diff", "--name-only", "--diff-filter=ACMR", "--", ".github/workflows/*.yml", ".github/workflows/*.yaml"],
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR", "--", ".github/workflows/*.yml", ".github/workflows/*.yaml"],
    ):
        proc = subprocess.run(command, check=False, text=True, capture_output=True)
        if proc.returncode not in (0, 1):
            print(proc.stderr, file=sys.stderr)
            raise SystemExit(2)
        paths.extend(Path(line) for line in proc.stdout.splitlines() if line.strip())
    default = Path(".github/workflows/a11oy-codex-finish-build-v1.yml")
    if default.exists() and default not in paths:
        paths.append(default)
    return sorted(set(paths))


def main() -> int:
    failures: list[str] = []
    checked = 0
    for path in changed_workflows():
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for match in USES.finditer(text):
            value = match.group(1).strip("'\"")
            if value.startswith("./") or value.startswith("docker://"):
                continue
            checked += 1
            if "@" not in value:
                failures.append(f"{path}: missing @ref: {value}")
                continue
            ref = value.rsplit("@", 1)[1]
            if not FULL_SHA.fullmatch(ref):
                failures.append(f"{path}: mutable action ref: {value}")
    if failures:
        for failure in failures:
            print(f"BLOCKED {failure}")
        return 1
    print(f"PASS immutable external action refs checked={checked}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
