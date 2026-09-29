#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Fail-closed check that the audit closure IS the runtime install set.

requirements-runtime.txt is the single source of truth for the image's primary
Python pins. The Dockerfile must install it with ``pip install -r`` and
requirements-audit.txt must include it with ``-r``. Neither file may re-list a
runtime pin, because a copied pin is exactly how the audit closure drifted from
the image before (Dependabot bumps the requirements file it can see and leaves
the Dockerfile RUN line alone).

Exit 0 when the closure holds, 1 with one ``::error::`` line per violation.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

RUNTIME = "requirements-runtime.txt"
AUDIT = "requirements-audit.txt"
DOCKERFILE = "Dockerfile"

PIN = re.compile(r"^([A-Za-z0-9][A-Za-z0-9_.-]*)(\[[A-Za-z0-9_,.-]+\])?==([0-9][^\s;#]*)$")
DOCKER_INLINE_PIN = re.compile(r"[\"']?([A-Za-z0-9][A-Za-z0-9_.-]*)(?:\[[A-Za-z0-9_,.-]+\])?==[0-9]")
DOCKER_COPY = re.compile(r"^COPY\s+(?:--\S+\s+)*requirements-runtime\.txt\s+(\S+)\s*$", re.MULTILINE)
DOCKER_INSTALL = re.compile(r"^RUN\s+pip install\s+--no-cache-dir\s+-r\s+(\S+)\s*$", re.MULTILINE)
AUDIT_INCLUDE = re.compile(r"^-r\s+requirements-runtime\.txt\s*$", re.MULTILINE)


def normalize(name: str) -> str:
    """PEP 503 name normalization (huggingface_hub == huggingface-hub)."""
    return re.sub(r"[-_.]+", "-", name).lower()


def requirement_lines(text: str) -> list[str]:
    lines = []
    for raw in text.splitlines():
        line = raw.split(" #", 1)[0].strip()
        if line and not line.startswith("#"):
            lines.append(line)
    return lines


def runtime_pins(text: str) -> tuple[dict[str, str], list[str]]:
    """Return (normalized name -> version, errors) for requirements-runtime.txt."""
    pins: dict[str, str] = {}
    errors: list[str] = []
    for line in requirement_lines(text):
        match = PIN.fullmatch(line)
        if match is None:
            errors.append(f"{RUNTIME}: '{line}' is not an exact == pin")
            continue
        name = normalize(match.group(1))
        if name in pins:
            errors.append(f"{RUNTIME}: {match.group(1)} is pinned twice")
        pins[name] = match.group(3)
    if not pins:
        errors.append(f"{RUNTIME}: no runtime pins found")
    return pins, errors


def check(root: Path) -> list[str]:
    errors: list[str] = []
    try:
        runtime_text = (root / RUNTIME).read_text(encoding="utf-8")
        audit_text = (root / AUDIT).read_text(encoding="utf-8")
        docker_text = (root / DOCKERFILE).read_text(encoding="utf-8")
    except OSError as exc:
        return [f"missing closure input: {exc}"]

    pins, pin_errors = runtime_pins(runtime_text)
    errors.extend(pin_errors)

    copies = DOCKER_COPY.findall(docker_text)
    installs = DOCKER_INSTALL.findall(docker_text)
    if len(copies) != 1:
        errors.append(f"{DOCKERFILE}: expected exactly one COPY of {RUNTIME}, found {len(copies)}")
    if len(installs) != 1:
        errors.append(f"{DOCKERFILE}: expected exactly one 'RUN pip install --no-cache-dir -r <file>', found {len(installs)}")
    if len(copies) == 1 and len(installs) == 1 and copies[0] != installs[0]:
        errors.append(f"{DOCKERFILE}: installs {installs[0]} but copies {RUNTIME} to {copies[0]}")

    for match in DOCKER_INLINE_PIN.finditer(docker_text):
        if normalize(match.group(1)) in pins:
            errors.append(f"{DOCKERFILE}: runtime pin {match.group(1)} is re-listed inline; install it from {RUNTIME} only")

    if AUDIT_INCLUDE.search(audit_text) is None:
        errors.append(f"{AUDIT}: must include '-r {RUNTIME}'")
    for line in requirement_lines(audit_text):
        match = PIN.fullmatch(line)
        if match is not None and normalize(match.group(1)) in pins:
            errors.append(f"{AUDIT}: runtime pin {match.group(1)} is copied; include it via -r {RUNTIME} only")
    return errors


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    root = Path(args[0]) if args else Path(__file__).resolve().parents[1]
    errors = check(root)
    for error in errors:
        print(f"::error::{error}")
    if errors:
        return 1
    print(f"audit closure includes {RUNTIME}; the Dockerfile installs exactly that file")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
