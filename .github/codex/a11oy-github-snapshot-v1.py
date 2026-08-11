#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Write bounded read-only GitHub and public-surface evidence for Codex.

GITHUB_TOKEN is used only as an Authorization header for the GitHub API. It is
never written, hashed, logged, or included in output or exception messages.
"""

import argparse
import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

REPOSITORIES = (
    "szl-holdings/a11oy",
    "szl-holdings/.github",
    "szl-holdings/platform",
    "szl-holdings/killinchu",
    "szl-holdings/hatun-mcp",
    "szl-holdings/szl-forge",
)
SPECIFIC_ISSUES = (
    ("szl-holdings/.github", 415),
    ("szl-holdings/a11oy", 1266),
    ("szl-holdings/a11oy", 1034),
)
PUBLIC_SURFACES = (
    ("a11oy_honesty", "https://a-11-oy.com/api/a11oy/v1/honest", "json"),
    ("a11oy_status", "https://a-11-oy.com/status", "text"),
    ("a11oy_gap_report", "https://a-11-oy.com/gap-report", "text"),
    ("a11oy_net", "https://a11oy.net/", "text"),
)
MAX_BODY_BYTES = 2_000_000


def request_bytes(url: str, token: str = "") -> tuple[int, dict[str, str], bytes]:
    headers = {
        "Accept": "application/vnd.github+json" if "api.github.com" in url else "*/*",
        "User-Agent": "a11oy-codex-finish-build-v2",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
        headers["X-GitHub-Api-Version"] = "2022-11-28"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=20) as response:
        body = response.read(MAX_BODY_BYTES + 1)
        if len(body) > MAX_BODY_BYTES:
            raise ValueError("response exceeded bounded body limit")
        return int(response.status), dict(response.headers.items()), body


def get_json(url: str, token: str) -> Any:
    _, _, body = request_bytes(url, token)
    return json.loads(body.decode("utf-8"))


def safe_repo(full_name: str, token: str) -> dict[str, Any]:
    encoded = urllib.parse.quote(full_name, safe="/")
    try:
        metadata = get_json(f"https://api.github.com/repos/{encoded}", token)
        default_branch = str(metadata.get("default_branch") or "main")
        commit = get_json(f"https://api.github.com/repos/{encoded}/commits/{urllib.parse.quote(default_branch)}", token)
        pulls = get_json(f"https://api.github.com/repos/{encoded}/pulls?state=open&per_page=50", token)
        return {
            "repository": full_name,
            "default_branch": default_branch,
            "default_head_sha": commit.get("sha"),
            "visibility": metadata.get("visibility"),
            "archived": bool(metadata.get("archived", False)),
            "open_pull_requests": [
                {
                    "number": item.get("number"),
                    "draft": bool(item.get("draft", False)),
                    "head_sha": (item.get("head") or {}).get("sha"),
                    "base_sha": (item.get("base") or {}).get("sha"),
                    "updated_at": item.get("updated_at"),
                }
                for item in pulls
            ],
            "observation": "AUTHENTICATED_READ_ONLY",
        }
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, TypeError) as error:
        return {
            "repository": full_name,
            "state": "UNAVAILABLE",
            "observation": "READ_FAILED",
            "error_type": type(error).__name__,
        }


def safe_issue(full_name: str, number: int, token: str) -> dict[str, Any]:
    encoded = urllib.parse.quote(full_name, safe="/")
    try:
        data = get_json(f"https://api.github.com/repos/{encoded}/issues/{number}", token)
        return {
            "repository": full_name,
            "number": number,
            "state": str(data.get("state", "UNKNOWN")).upper(),
            "title": data.get("title"),
            "updated_at": data.get("updated_at"),
            "pull_request": bool(data.get("pull_request")),
            "observation": "AUTHENTICATED_READ_ONLY",
        }
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, TypeError) as error:
        return {
            "repository": full_name,
            "number": number,
            "state": "UNAVAILABLE",
            "observation": "READ_FAILED",
            "error_type": type(error).__name__,
        }


def safe_public(name: str, url: str, kind: str) -> dict[str, Any]:
    try:
        status, headers, body = request_bytes(url)
        text = body.decode("utf-8", errors="replace")
        result: dict[str, Any] = {
            "name": name,
            "url": url,
            "http_status": status,
            "content_type": headers.get("Content-Type"),
            "body_bytes": len(body),
            "sha256": hashlib.sha256(body).hexdigest(),
            "observation": "PUBLIC_READ_ONLY",
        }
        if kind == "json":
            parsed = json.loads(text)
            result["selected"] = {
                key: parsed.get(key)
                for key in ("git_sha", "commit", "doctrine", "lambda", "status")
                if isinstance(parsed, dict) and key in parsed
            }
        else:
            lowered = text.lower()
            result["markers"] = {
                "checking": "checking" in lowered,
                "loading": "loading" in lowered,
                "probing": "probing" in lowered,
                "killinchu": "killinchu" in lowered,
                "spec_only_not_deployed": "spec only" in lowered and "not deployed" in lowered,
            }
        return result
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, TypeError, json.JSONDecodeError) as error:
        return {
            "name": name,
            "url": url,
            "state": "UNAVAILABLE",
            "observation": "READ_FAILED",
            "error_type": type(error).__name__,
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    token = os.environ.get("GITHUB_TOKEN", "")
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "schema_version": "a11oy.codex.current-state.v2",
        "observed_at_epoch": int(time.time()),
        "secret_values_recorded": False,
        "github_status": "OBSERVED" if token else "UNAVAILABLE",
        "github_reason": None if token else "GITHUB_TOKEN_NOT_PRESENT",
        "repositories": [safe_repo(repo, token) for repo in REPOSITORIES] if token else [],
        "issues": [safe_issue(repo, number, token) for repo, number in SPECIFIC_ISSUES] if token else [],
        "public_surfaces": [safe_public(*target) for target in PUBLIC_SURFACES],
    }
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {output} github_status={payload['github_status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
