#!/usr/bin/env python3
# Copyright 2026 SZL Holdings - SPDX-License-Identifier: Apache-2.0
"""Classify exact protected-main ownership before an optional HF publication.

Only two verified states return successfully:

* ``OWNED`` — the workflow source is the exact current ``main`` tip;
* ``SUPERSEDED_BY_NEWER_MAIN`` — GitHub proves the workflow source is an
  ancestor of the current ``main`` tip.

Divergence, authentication failure, malformed provider state, redirects, and
transport uncertainty remain hard failures. This module performs authenticated
GET requests only and never receives Hugging Face credentials.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import HTTPRedirectHandler, Request, build_opener

SCHEMA = "szl.hf-main-ownership/v1"
API_ORIGIN = "https://api.github.com"
MAIN_BRANCH = "main"
SHA40 = re.compile(r"^[0-9a-f]{40}$")
REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
MAX_RESPONSE_BYTES = 2 * 1024 * 1024


class OwnershipError(RuntimeError):
    """Exact protected-main ownership could not be established."""


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        raise OwnershipError(f"GitHub API unexpectedly redirected with HTTP {code}")


def validate_repository(value: str) -> str:
    repository = str(value or "").strip()
    if REPOSITORY.fullmatch(repository) is None:
        raise OwnershipError("repository must be an exact owner/name identifier")
    return repository


def validate_sha(value: str, *, label: str) -> str:
    candidate = str(value or "").strip()
    if SHA40.fullmatch(candidate) is None:
        raise OwnershipError(f"{label} must be exact 40-character lowercase hex")
    return candidate


def request_json(path: str, token: str, *, timeout: float = 20.0) -> Mapping[str, Any]:
    """Read one bounded, same-origin GitHub API object without redirects."""

    if not token:
        raise OwnershipError("GITHUB_TOKEN is required for exact-main verification")
    if not path.startswith("/repos/") or "//" in path or "?" in path or "#" in path:
        raise OwnershipError("GitHub API path is outside the bounded repository surface")
    request = Request(
        API_ORIGIN + path,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "szl-hf-main-ownership/1",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        method="GET",
    )
    opener = build_opener(_NoRedirect)
    try:
        with opener.open(request, timeout=timeout) as response:  # noqa: S310
            status = int(getattr(response, "status", 0))
            payload = response.read(MAX_RESPONSE_BYTES + 1)
    except HTTPError as exc:
        raise OwnershipError(f"GitHub API returned HTTP {int(exc.code)}") from exc
    except URLError as exc:
        raise OwnershipError(
            f"GitHub API transport failed: {type(exc.reason).__name__}"
        ) from exc
    except TimeoutError as exc:
        raise OwnershipError("GitHub API request timed out") from exc
    if not 200 <= status < 300:
        raise OwnershipError(f"GitHub API returned HTTP {status}")
    if len(payload) > MAX_RESPONSE_BYTES:
        raise OwnershipError("GitHub API response exceeded the bounded size")
    try:
        value = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OwnershipError("GitHub API did not return valid JSON") from exc
    if not isinstance(value, Mapping):
        raise OwnershipError("GitHub API did not return a JSON object")
    return value


def fetch_main_sha(repository: str, token: str) -> str:
    repository = validate_repository(repository)
    owner, name = repository.split("/", 1)
    path = (
        f"/repos/{quote(owner, safe='')}/{quote(name, safe='')}/branches/"
        f"{quote(MAIN_BRANCH, safe='')}"
    )
    payload = request_json(path, token)
    commit = payload.get("commit")
    if not isinstance(commit, Mapping):
        raise OwnershipError("GitHub branch response lacks a commit object")
    return validate_sha(str(commit.get("sha") or ""), label="observed main SHA")


def prove_ancestor(repository: str, expected_sha: str, observed_sha: str, token: str) -> None:
    """Require GitHub to prove ``expected`` is a strict ancestor of ``observed``."""

    repository = validate_repository(repository)
    expected = validate_sha(expected_sha, label="expected source SHA")
    observed = validate_sha(observed_sha, label="observed main SHA")
    owner, name = repository.split("/", 1)
    path = (
        f"/repos/{quote(owner, safe='')}/{quote(name, safe='')}/compare/"
        f"{quote(expected, safe='')}...{quote(observed, safe='')}"
    )
    payload = request_json(path, token)
    merge_base = payload.get("merge_base_commit")
    if not isinstance(merge_base, Mapping):
        raise OwnershipError("GitHub compare response lacks a merge-base commit")
    merge_base_sha = validate_sha(
        str(merge_base.get("sha") or ""), label="compare merge-base SHA"
    )
    status = payload.get("status")
    ahead_by = payload.get("ahead_by")
    behind_by = payload.get("behind_by")
    if (
        status != "ahead"
        or not isinstance(ahead_by, int)
        or isinstance(ahead_by, bool)
        or ahead_by < 1
        or behind_by != 0
        or merge_base_sha != expected
    ):
        raise OwnershipError(
            "observed main is not a verified strict descendant of the workflow source"
        )


def classify(repository: str, expected_sha: str, observed_sha: str, token: str) -> tuple[str, bool]:
    expected = validate_sha(expected_sha, label="expected source SHA")
    observed = validate_sha(observed_sha, label="observed main SHA")
    if expected == observed:
        return "OWNED", True
    prove_ancestor(repository, expected, observed, token)
    return "SUPERSEDED_BY_NEWER_MAIN", False


def atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=path.name + ".", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(dict(payload), handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def append_outputs(path: Path, values: Mapping[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for key, value in values.items():
            if any(character in key + value for character in "\r\n"):
                raise OwnershipError("GitHub output values must be single-line")
            handle.write(f"{key}={value}\n")


def base_receipt(repository: str, expected_sha: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repository": repository,
        "branch": MAIN_BRANCH,
        "expected_sha": expected_sha,
        "observed_main_sha": None,
        "status": "ERROR",
        "publish": False,
        "source_verified": False,
        "expected_is_ancestor_of_observed": False,
        "external_writes_performed": False,
        "secret_values_recorded": False,
    }


def execute(
    *,
    repository: str,
    expected_sha: str,
    receipt_path: Path,
    github_output: Path,
    token: str,
) -> int:
    safe_repository = str(repository or "").strip() or "UNVALIDATED"
    safe_expected = str(expected_sha or "").strip() or "UNVALIDATED"
    report = base_receipt(safe_repository, safe_expected)
    try:
        normalized_repository = validate_repository(repository)
        normalized_expected = validate_sha(expected_sha, label="expected source SHA")
        observed = fetch_main_sha(normalized_repository, token)
        status, publish = classify(
            normalized_repository, normalized_expected, observed, token
        )
        report.update(
            {
                "repository": normalized_repository,
                "expected_sha": normalized_expected,
                "observed_main_sha": observed,
                "status": status,
                "publish": publish,
                "source_verified": True,
                "expected_is_ancestor_of_observed": True,
                "reason": (
                    "workflow source exactly equals protected main"
                    if publish
                    else "workflow source is a verified ancestor of protected main"
                ),
            }
        )
        atomic_json(receipt_path, report)
        append_outputs(
            github_output,
            {
                "publish": "true" if publish else "false",
                "ownership_status": status,
                "observed_main_sha": observed,
                "receipt_path": str(receipt_path),
            },
        )
        print(json.dumps(report, sort_keys=True))
        return 0
    except Exception as exc:  # noqa: BLE001 - fail-closed evidence boundary
        message = str(exc)
        if token:
            message = message.replace(token, "[REDACTED]")
        report["error"] = {
            "type": type(exc).__name__,
            "message_sha256": hashlib.sha256(message.encode("utf-8")).hexdigest(),
        }
        atomic_json(receipt_path, report)
        append_outputs(
            github_output,
            {
                "publish": "false",
                "ownership_status": "ERROR",
                "observed_main_sha": "UNVERIFIED",
                "receipt_path": str(receipt_path),
            },
        )
        print(json.dumps(report, sort_keys=True))
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--github-output", required=True, type=Path)
    args = parser.parse_args()
    return execute(
        repository=args.repository,
        expected_sha=args.expected_sha,
        receipt_path=args.receipt,
        github_output=args.github_output,
        token=os.environ.get("GITHUB_TOKEN", ""),
    )


if __name__ == "__main__":
    raise SystemExit(main())
