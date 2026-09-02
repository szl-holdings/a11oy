#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Normalize the managed alert endpoint without exposing its opaque topic.

The historical managed secret used the static proof-registry host
``a11oy.net``.  That host must remain non-receiving for ordinary traffic.  The
source-controlled alert relay owns ``ntfy.a11oy.net`` instead.  This module
performs one narrow, explicit migration of the exact legacy hostname while
preserving the opaque path and query byte-for-byte.  Lookalikes are never
rewritten.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import urllib.parse

LEGACY_MANAGED_HOST = "a11oy.net"
MANAGED_RELAY_HOST = "ntfy.a11oy.net"
_TOPIC_HOSTS = {MANAGED_RELAY_HOST, "ntfy.sh"}


class ManagedAlertEndpointError(ValueError):
    """The managed endpoint cannot safely be used for delivery."""


def normalize_managed_endpoint(raw: str) -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise ManagedAlertEndpointError("managed alert endpoint is missing")
    value = raw.strip()
    if len(value) > 4096:
        raise ManagedAlertEndpointError("managed alert endpoint exceeds the length bound")
    if any(character.isspace() for character in value):
        raise ManagedAlertEndpointError("managed alert endpoint contains whitespace")

    try:
        parsed = urllib.parse.urlsplit(value)
        port = parsed.port
    except ValueError as error:
        raise ManagedAlertEndpointError("managed alert endpoint has an invalid port") from error

    if parsed.scheme != "https":
        raise ManagedAlertEndpointError("managed alert endpoint must use HTTPS")
    if not parsed.hostname:
        raise ManagedAlertEndpointError("managed alert endpoint has no hostname")
    if parsed.username or parsed.password:
        raise ManagedAlertEndpointError("embedded endpoint credentials are forbidden")
    if parsed.fragment:
        raise ManagedAlertEndpointError("endpoint fragments are forbidden")

    hostname = parsed.hostname.rstrip(".").lower()
    target_host = MANAGED_RELAY_HOST if hostname == LEGACY_MANAGED_HOST else hostname
    if target_host in _TOPIC_HOSTS and parsed.path in {"", "/"}:
        raise ManagedAlertEndpointError("managed ntfy endpoint requires an opaque topic path")

    if target_host == hostname:
        return value

    netloc = target_host + (f":{port}" if port is not None else "")
    return urllib.parse.urlunsplit(
        (parsed.scheme, netloc, parsed.path, parsed.query, "")
    )


def write_private(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value + "\n", encoding="utf-8")
    path.chmod(0o600)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--env", default="SLACK_WEBHOOK_URL")
    args = parser.parse_args()
    try:
        normalized = normalize_managed_endpoint(os.environ.get(args.env, ""))
    except ManagedAlertEndpointError as error:
        # The error deliberately contains no endpoint, path, query, or token.
        raise SystemExit(f"managed alert endpoint rejected: {error}")
    write_private(args.output, normalized)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
