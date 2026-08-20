#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 SZL Holdings
"""Resolve fail-closed peer evidence for the shared-source drift guard.

Legacy coordinated PRs may still pin an exact peer head:

    Shared-source-peer: owner/repository#123@<40-lowercase-hex-commit>

New coordinated PRs bind a stable reciprocal PR identity to a content-addressed
manifest.  The workflow resolves the peer's exact head at run time, so unrelated
peer commits do not create a circular pin update:

    Shared-source-peer: owner/repository#123
    Shared-source-payload: sha256:<64-lowercase-hex-digest>
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys
from typing import Any


PEER_PREFIX = "Shared-source-peer:"
PAYLOAD_PREFIX = "Shared-source-payload:"
LEGACY_PEER_RE = re.compile(
    r"^Shared-source-peer:\s*"
    r"(?P<repository>[a-z0-9_.-]+/[a-z0-9_.-]+)"
    r"#(?P<pull_request>[1-9][0-9]*)"
    r"@(?P<commit>[0-9a-f]{40})\s*$"
)
CONTENT_PEER_RE = re.compile(
    r"^Shared-source-peer:\s*"
    r"(?P<repository>[a-z0-9_.-]+/[a-z0-9_.-]+)"
    r"#(?P<pull_request>[1-9][0-9]*)\s*$"
)
PAYLOAD_RE = re.compile(r"^Shared-source-payload:\s*sha256:(?P<digest>[0-9a-f]{64})\s*$")
SHA_RE = re.compile(r"[0-9a-f]{40}")


def fail(message: str) -> int:
    print(f"::error::{message}", file=sys.stderr)
    return 2


def append_output(path: Path, values: dict[str, str]) -> None:
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        for key, value in values.items():
            handle.write(f"{key}={value}\n")


def marker_lines(body: str, prefix: str) -> list[str]:
    return [line.strip() for line in body.splitlines() if line.strip().startswith(prefix)]


def load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} is unreadable: {type(exc).__name__}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} root must be an object")
    return value


def parse_pr_body(body: str, expected_repository: str) -> tuple[dict[str, str] | None, str | None]:
    peers = marker_lines(body, PEER_PREFIX)
    payloads = marker_lines(body, PAYLOAD_PREFIX)
    if not peers:
        if payloads:
            return None, "Shared-source-payload requires exactly one Shared-source-peer marker"
        return None, None
    if len(peers) != 1:
        return None, "exactly one Shared-source-peer marker is permitted"
    if len(payloads) > 1:
        return None, "at most one Shared-source-payload marker is permitted"

    legacy = LEGACY_PEER_RE.fullmatch(peers[0])
    if legacy is not None:
        if payloads:
            return None, "legacy exact-head peer pins cannot also declare a payload manifest"
        if legacy.group("repository") != expected_repository:
            return None, f"Shared-source-peer repository must be {expected_repository}"
        return {
            "ref": legacy.group("commit"),
            "source": "legacy-pinned-peer-pr",
            "repository": legacy.group("repository"),
            "pull_request": legacy.group("pull_request"),
            "payload_sha256": "",
        }, None

    content = CONTENT_PEER_RE.fullmatch(peers[0])
    if content is None:
        return None, "Shared-source-peer must use owner/repository#PR with an optional legacy @commit"
    if content.group("repository") != expected_repository:
        return None, f"Shared-source-peer repository must be {expected_repository}"
    if len(payloads) != 1:
        return None, "content-bound peer markers require exactly one Shared-source-payload marker"
    payload = PAYLOAD_RE.fullmatch(payloads[0])
    if payload is None:
        return None, "Shared-source-payload must be sha256 followed by 64 lowercase hexadecimal characters"
    return {
        "ref": "",
        "source": "content-bound-peer-pr",
        "repository": content.group("repository"),
        "pull_request": content.group("pull_request"),
        "payload_sha256": payload.group("digest"),
    }, None


def parse_event(args: argparse.Namespace) -> int:
    values = {
        "ref": "main",
        "source": "sibling-main",
        "repository": args.expected_repository,
        "pull_request": "",
        "payload_sha256": "",
    }
    if args.event_name != "pull_request":
        append_output(args.output, values)
        return 0
    if args.event_path is None or not args.event_path.is_file():
        return fail("pull_request event payload is missing")
    try:
        payload = load_json(args.event_path, "pull_request event payload")
    except ValueError as exc:
        return fail(str(exc))
    pull_request = payload.get("pull_request")
    if not isinstance(pull_request, dict):
        return fail("pull_request event payload lacks a pull_request object")
    body = pull_request.get("body") or ""
    if not isinstance(body, str):
        return fail("pull_request body must be a string or null")
    parsed, error = parse_pr_body(body, args.expected_repository)
    if error:
        return fail(error)
    if parsed is not None:
        values.update(parsed)
    append_output(args.output, values)
    return 0


def resolve_peer(args: argparse.Namespace) -> int:
    if not args.current_repository or not args.current_pull_request:
        return fail("peer resolution requires current repository and pull request")
    if not PAYLOAD_RE.fullmatch(f"Shared-source-payload: sha256:{args.expected_payload_sha256}"):
        return fail("peer resolution requires a lowercase SHA-256 payload digest")
    try:
        peer = load_json(args.peer_pr_path, "peer pull request payload")
    except ValueError as exc:
        return fail(str(exc))

    base = peer.get("base") if isinstance(peer.get("base"), dict) else {}
    head = peer.get("head") if isinstance(peer.get("head"), dict) else {}
    base_repo = base.get("repo") if isinstance(base.get("repo"), dict) else {}
    head_repo = head.get("repo") if isinstance(head.get("repo"), dict) else {}
    if base.get("ref") != "main" or base_repo.get("full_name") != args.expected_repository:
        return fail("peer pull request must target main in the expected repository")
    if head_repo.get("full_name") != args.expected_repository:
        return fail("peer pull request head must come from the expected repository, not a fork")

    peer_body = peer.get("body") or ""
    if not isinstance(peer_body, str):
        return fail("peer pull request body must be a string or null")
    parsed, error = parse_pr_body(peer_body, args.current_repository)
    if error:
        return fail(f"peer reciprocal marker is invalid: {error}")
    if parsed is None or parsed["source"] != "content-bound-peer-pr":
        return fail("peer pull request must carry reciprocal content-bound markers")
    if parsed["pull_request"] != str(args.current_pull_request):
        return fail("peer reciprocal marker points to a different pull request")
    if parsed["payload_sha256"] != args.expected_payload_sha256:
        return fail("peer reciprocal marker declares a different payload digest")

    state = peer.get("state")
    if state == "open":
        ref = head.get("sha")
        source = "content-bound-peer-pr"
    elif state == "closed" and peer.get("merged") is True and peer.get("merged_at"):
        ref = args.peer_main_ref
        source = "content-bound-peer-main"
    else:
        return fail("peer pull request must be open or already merged into main")
    if not isinstance(ref, str) or not SHA_RE.fullmatch(ref):
        return fail("resolved peer ref must be an exact lowercase 40-character commit")

    append_output(
        args.output,
        {
            "ref": ref,
            "source": source,
            "repository": args.expected_repository,
            "pull_request": str(peer.get("number") or ""),
            "payload_sha256": args.expected_payload_sha256,
        },
    )
    return 0


def main() -> int:
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    output_path = os.environ.get("GITHUB_OUTPUT")
    parser = argparse.ArgumentParser()
    parser.add_argument("--event-name", default=os.environ.get("GITHUB_EVENT_NAME", ""))
    parser.add_argument("--event-path", type=Path, default=Path(event_path) if event_path else None)
    parser.add_argument("--output", type=Path, default=Path(output_path) if output_path else None)
    parser.add_argument("--expected-repository", required=True)
    parser.add_argument("--peer-pr-path", type=Path)
    parser.add_argument("--peer-main-ref", default="")
    parser.add_argument("--current-repository")
    parser.add_argument("--current-pull-request", type=int)
    parser.add_argument("--expected-payload-sha256", default="")
    args = parser.parse_args()
    if args.output is None:
        return fail("GITHUB_OUTPUT (or --output) is required")
    if args.peer_pr_path is not None:
        return resolve_peer(args)
    return parse_event(args)


if __name__ == "__main__":
    raise SystemExit(main())
