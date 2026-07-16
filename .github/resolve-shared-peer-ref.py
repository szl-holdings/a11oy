#!/usr/bin/env python3
"""Resolve an optional immutable sibling PR head for the shared drift guard.

Normal push, schedule, and workflow-dispatch runs always compare main to main.
Pull requests may opt into a staged cross-repository synchronization by adding
exactly one line to the PR body:

    Shared-source-peer: owner/repository#123@<40-lowercase-hex-commit>

The resolver accepts only the configured sibling repository and emits fields
safe for use by actions/checkout.  It never accepts a branch or tag as a pin.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys


MARKER_PREFIX = "Shared-source-peer:"
MARKER_RE = re.compile(
    r"^Shared-source-peer:\s*"
    r"(?P<repository>[a-z0-9_.-]+/[a-z0-9_.-]+)"
    r"#(?P<pull_request>[1-9][0-9]*)"
    r"@(?P<commit>[0-9a-f]{40})\s*$"
)


def fail(message: str) -> int:
    print(f"::error::{message}", file=sys.stderr)
    return 2


def append_output(path: Path, values: dict[str, str]) -> None:
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        for key, value in values.items():
            handle.write(f"{key}={value}\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event-name", default=os.environ.get("GITHUB_EVENT_NAME", ""))
    parser.add_argument("--event-path", type=Path, default=os.environ.get("GITHUB_EVENT_PATH"))
    parser.add_argument("--output", type=Path, default=os.environ.get("GITHUB_OUTPUT"))
    parser.add_argument("--expected-repository", required=True)
    args = parser.parse_args()

    if args.output is None:
        return fail("GITHUB_OUTPUT (or --output) is required")

    values = {
        "ref": "main",
        "source": "sibling-main",
        "repository": args.expected_repository,
        "pull_request": "",
    }
    if args.event_name != "pull_request":
        append_output(args.output, values)
        return 0

    if args.event_path is None or not args.event_path.is_file():
        return fail("pull_request event payload is missing")
    try:
        payload = json.loads(args.event_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return fail(f"pull_request event payload is unreadable: {type(exc).__name__}")

    body = payload.get("pull_request", {}).get("body") or ""
    marker_lines = [line.strip() for line in body.splitlines() if line.strip().startswith(MARKER_PREFIX)]
    if not marker_lines:
        append_output(args.output, values)
        return 0
    if len(marker_lines) != 1:
        return fail("exactly one Shared-source-peer marker is permitted")

    match = MARKER_RE.fullmatch(marker_lines[0])
    if match is None:
        return fail("Shared-source-peer marker must pin owner/repository#PR@40-lowercase-hex-commit")
    if match.group("repository") != args.expected_repository:
        return fail(
            f"Shared-source-peer repository must be {args.expected_repository}, "
            f"not {match.group('repository')}"
        )

    values.update(
        {
            "ref": match.group("commit"),
            "source": "pinned-peer-pr",
            "pull_request": match.group("pull_request"),
        }
    )
    append_output(args.output, values)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
