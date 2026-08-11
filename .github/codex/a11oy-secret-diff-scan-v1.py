#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Reject high-confidence credential material added to the current Git diff.

The scanner checks strong credential shapes and private-key blocks only. It never
reads environment-variable values.
"""

import re
import subprocess
import sys

PATTERNS = {
    "github_token": re.compile(r"(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})"),
    "openai_key": re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b"),
    "huggingface_token": re.compile(r"\bhf_[A-Za-z0-9]{20,}\b"),
    "aws_access_key": re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    "bearer_material": re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{24,}\b", re.IGNORECASE),
}


def added_lines() -> list[str]:
    commands = [
        ["git", "diff", "--no-ext-diff", "--unified=0", "--", "."],
        ["git", "diff", "--cached", "--no-ext-diff", "--unified=0", "--", "."],
    ]
    lines: list[str] = []
    for command in commands:
        proc = subprocess.run(command, check=False, text=True, capture_output=True)
        if proc.returncode not in (0, 1):
            print(proc.stderr, file=sys.stderr)
            raise SystemExit(2)
        for line in proc.stdout.splitlines():
            if line.startswith("+++"):
                continue
            if line.startswith("+"):
                lines.append(line[1:])
    return lines


def main() -> int:
    findings: list[tuple[str, int]] = []
    for index, line in enumerate(added_lines(), start=1):
        for name, pattern in PATTERNS.items():
            if pattern.search(line):
                findings.append((name, index))
    if findings:
        for name, line_number in findings:
            print(f"BLOCKED credential-shaped material: pattern={name} added_line={line_number}")
        return 1
    print("PASS no high-confidence credential material found in added lines")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
