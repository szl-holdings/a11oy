#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Decide whether the canonical Space deploy window is open.

The window stays closed unless one of three proofs holds:

* the runtime stage is PAUSED
* this run is an operator dispatch with open_deploy_window
* anonymous GET /api/a11oy/v1/storage/status proves ADR-0001 fenced local
  stores, so a deploy is a handover and not an overlap of SQLite on the
  bucket mount

A closed window may skip only when live /api/build-info already equals the
protected main SHA. Every other closed state fails the run. This script has
no provider write, sends no token, and does not follow redirects.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from typing import Any, Callable, Mapping

ALLOWED_ORIGIN = "https://szlholdings-a11oy.hf.space"
SCHEMA = "szl.a11oy-storage-status/v2"
HANDOVER_ROLES = frozenset({
    "WRITER", "HANDING_OVER", "FENCED", "RELEASED", "BLOCKED",
})
LOCAL_ORIGINS = frozenset({
    "RESTORED", "ADOPTED_UNFENCED_SNAPSHOT", "FRESH",
})
# A store still bootstrapped from the bucket mount is the overlap hazard.
EXCLUDED_ORIGINS = frozenset({"LEGACY_BOOTSTRAP"})
REQUIRED_STORES = {
    "gdw": "sqlite",
    "series_a": "sqlite",
    "khipu": "sqlite",
    "khipu_council": "sqlite",
    "unay": "sqlite",
    "khipu_lmdb": "lmdb",
    "khipu_repl": "lmdb",
}
_SHA = re.compile(r"[0-9a-f]{40}\Z")
_MAX_BYTES = 1_000_000


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ARG002
        return None


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def fetch_json(url: str, timeout: float = 20.0) -> Any:
    """Anonymous GET. No proxy, no redirect, no credential header."""
    request = urllib.request.Request(url, method="GET", headers={
        "Accept": "application/json",
        "User-Agent": "SZL-Canonical-Deploy-Window/1",
        "Cache-Control": "no-cache",
    })
    opener = urllib.request.build_opener(_NoRedirect, urllib.request.ProxyHandler({}))
    try:
        with opener.open(request, timeout=timeout) as response:
            if response.status != 200 or response.geturl() != url:
                return None
            raw = response.read(_MAX_BYTES + 1)
    except Exception:
        return None
    if len(raw) > _MAX_BYTES:
        return None
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs)
    except (UnicodeError, ValueError, RecursionError):
        return None


def live_revision(build_info: Any) -> str | None:
    if not isinstance(build_info, Mapping):
        return None
    build = build_info.get("build")
    if not isinstance(build, Mapping):
        return None
    revision = build.get("revision")
    if isinstance(revision, str) and _SHA.fullmatch(revision):
        return revision
    return None


def storage_gap(status: Any) -> str | None:
    """Return None when status proves a fenced local store, else a short code."""
    if not isinstance(status, Mapping):
        return "STORAGE_FETCH_FAILED"
    if status.get("schema") != SCHEMA:
        return "STORAGE_SCHEMA"
    if status.get("mode") != "FENCED" or status.get("unfenced") is not False:
        return "STORAGE_UNFENCED"
    if status.get("role") not in HANDOVER_ROLES:
        return "STORAGE_ROLE"
    epoch = status.get("epoch")
    if type(epoch) is not int or epoch < 1:
        return "STORAGE_EPOCH"
    durable = status.get("durable_v1")
    if (not isinstance(durable, Mapping) or durable.get("status") != "RETIRED"
            or durable.get("env_ignored") is not False):
        return "STORAGE_DURABLE_V1"
    stores = status.get("stores")
    if not isinstance(stores, Mapping) or set(stores) != set(REQUIRED_STORES):
        return "STORAGE_STORES"
    for label, kind in REQUIRED_STORES.items():
        entry = stores.get(label)
        origin = entry.get("origin") if isinstance(entry, Mapping) else None
        if (not isinstance(entry, Mapping) or entry.get("kind") != kind
                or origin in EXCLUDED_ORIGINS or origin not in LOCAL_ORIGINS):
            return "STORAGE_STORES"
    return None


def decide(*, stage: str, dispatch_window: bool, github_sha: str,
           build_info: Any, storage_status: Any) -> tuple[str, str]:
    """Return (open|skip|block, detail). Pure: no network and no output."""
    if not _SHA.fullmatch(github_sha or ""):
        return "block", "SHA_UNBOUND"
    if stage == "PAUSED" or dispatch_window is True:
        return "open", "operator-window"
    revision = live_revision(build_info)
    if revision == github_sha:
        return "skip", revision
    gap = storage_gap(storage_status)
    if gap is None:
        return "open", "fenced-local"
    return "block", gap


def _append_output(path: str, value: str) -> None:
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(value + "\n")


def main(argv: list[str] | None = None,
         fetch: Callable[[str], Any] = fetch_json) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", required=True)
    parser.add_argument("--dispatch-window", required=True)
    parser.add_argument("--github-sha", required=True)
    parser.add_argument("--origin", required=True)
    parser.add_argument("--github-output", required=True)
    args = parser.parse_args(argv)
    stage = args.stage
    dispatch = args.dispatch_window == "true"
    sha = args.github_sha
    if args.origin != ALLOWED_ORIGIN or not _SHA.fullmatch(sha or ""):
        detail = "ORIGIN_UNBOUND" if args.origin != ALLOWED_ORIGIN else "SHA_UNBOUND"
        print(
            "::error::PUBLICATION_BLOCKED_DEPLOY_WINDOW_CLOSED: "
            f"stage={stage or 'UNKNOWN'} protected_main={sha or 'UNBOUND'} "
            f"live_revision=UNAVAILABLE storage={detail}. Pause the Space, or "
            "dispatch hf-sync.yml on main with open_deploy_window=true, inside "
            "an agreed maintenance window.",
            file=sys.stderr,
        )
        return 1
    build_info = None
    storage_status = None
    if stage != "PAUSED" and not dispatch:
        build_info = fetch(ALLOWED_ORIGIN + "/api/build-info")
        storage_status = fetch(ALLOWED_ORIGIN + "/api/a11oy/v1/storage/status")
    action, detail = decide(
        stage=stage, dispatch_window=dispatch, github_sha=sha,
        build_info=build_info, storage_status=storage_status,
    )
    if action == "skip":
        print(
            "::notice::Deploy window closed; live /api/build-info already "
            f"equals protected main {sha}."
        )
        _append_output(args.github_output, "open=false")
        return 0
    if action == "open":
        if detail == "fenced-local":
            print(
                "::notice::Deploy window open: anonymous storage status proved "
                "a fenced local state store, so the bucket-mount SQLite overlap "
                "window is not required."
            )
        _append_output(args.github_output, "open=true")
        return 0
    revision = live_revision(build_info) or "UNAVAILABLE"
    print(
        "::error::PUBLICATION_BLOCKED_DEPLOY_WINDOW_CLOSED: "
        f"stage={stage or 'UNKNOWN'} protected_main={sha} "
        f"live_revision={revision} storage={detail}. Pause the Space, or "
        "dispatch hf-sync.yml on main with open_deploy_window=true, inside "
        "an agreed maintenance window."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
