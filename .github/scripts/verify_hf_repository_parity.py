#!/usr/bin/env python3
"""Fail-closed GitHub/Hugging Face repository parity orchestration.

The pinned organization comparator is retained for its Dockerfile COPY
expansion, but this wrapper removes three unsafe ambiguities from proof mode:
the HF branch is resolved twice to one immutable commit, no allowlist is
passed, and the comparator's known dot-prefixed normalization gap is covered by
an explicit byte comparison of ``.well-known/security.txt``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable

SHA_RE = re.compile(r"^[0-9a-f]{40}$")
EXPECTED_COMPATIBILITY_WARNING = {
    "kind": "missing-both",
    "path": "well-known/security.txt",
    "severity": "warn",
}


class ParityError(RuntimeError):
    """Raised when immutable repository parity cannot be proved."""


def _read_url(
    url: str,
    *,
    opener: Callable[..., Any] = urllib.request.urlopen,
) -> bytes:
    headers = {"User-Agent": "szl-hf-parity/1"}
    token = os.environ.get("GITHUB_TOKEN")
    if token and url.startswith("https://api.github.com/"):
        headers["Authorization"] = f"Bearer {token}"
        headers["Accept"] = "application/vnd.github+json"
    request = urllib.request.Request(url, headers=headers)
    with opener(request, timeout=30) as response:
        return response.read()


def _space_revision(
    hf_repo: str,
    *,
    opener: Callable[..., Any] = urllib.request.urlopen,
) -> str:
    url = f"https://huggingface.co/api/spaces/{hf_repo}"
    try:
        payload = json.loads(_read_url(url, opener=opener))
    except Exception as exc:  # urllib and malformed JSON both fail closed
        raise ParityError(
            f"cannot resolve Hugging Face repository revision: {exc}"
        ) from exc
    revision = payload.get("sha") if isinstance(payload, dict) else None
    if not isinstance(revision, str) or not SHA_RE.fullmatch(revision):
        raise ParityError(
            "Hugging Face API did not return an exact lowercase 40-character SHA"
        )
    return revision


def resolve_stable_revision(
    hf_repo: str,
    *,
    opener: Callable[..., Any] = urllib.request.urlopen,
    pause: Callable[[float], None] = time.sleep,
) -> str:
    first = _space_revision(hf_repo, opener=opener)
    pause(1.0)
    second = _space_revision(hf_repo, opener=opener)
    if first != second:
        raise ParityError(
            f"Hugging Face repository moved during admission: {first} -> {second}"
        )
    return first


def validate_report(report: object, *, github_ref: str, hf_ref: str) -> None:
    if not isinstance(report, dict):
        raise ParityError("comparator report must be an object")
    if report.get("status") != "ok" or report.get("error_count") != 0:
        raise ParityError("comparator did not produce an exact zero-error result")
    if report.get("github_ref") != github_ref or report.get("hf_ref") != hf_ref:
        raise ParityError(
            "comparator report is not bound to the admitted immutable revisions"
        )
    if (
        not isinstance(report.get("files_compared"), int)
        or report["files_compared"] <= 0
    ):
        raise ParityError("comparator did not prove any managed files")

    findings = report.get("findings")
    if not isinstance(findings, list):
        raise ParityError("comparator findings must be an array")
    normalized = [
        {key: finding.get(key) for key in ("kind", "path", "severity")}
        for finding in findings
        if isinstance(finding, dict)
    ]
    if normalized != [EXPECTED_COMPATIBILITY_WARNING]:
        raise ParityError(f"unexpected comparator findings: {normalized!r}")
    if report.get("warn_count") != 1:
        raise ParityError(
            "comparator warning count does not match the guarded compatibility gap"
        )


def verify_github_tree_complete(
    github_repo: str,
    *,
    github_ref: str,
    opener: Callable[..., Any] = urllib.request.urlopen,
) -> None:
    url = (
        f"https://api.github.com/repos/{github_repo}/git/trees/{github_ref}?recursive=1"
    )
    try:
        tree = json.loads(_read_url(url, opener=opener))
    except Exception as exc:
        raise ParityError(f"cannot read exact GitHub tree: {exc}") from exc
    if not isinstance(tree, dict) or tree.get("truncated") is not False:
        raise ParityError("exact GitHub recursive tree is absent or truncated")
    entries = tree.get("tree")
    if not isinstance(entries, list) or not entries:
        raise ParityError("exact GitHub recursive tree contains no entries")
    matches = [
        entry
        for entry in entries
        if isinstance(entry, dict)
        and entry.get("path") == ".well-known/security.txt"
        and entry.get("type") == "blob"
    ]
    if len(matches) != 1:
        raise ParityError(
            "exact GitHub tree does not contain one dot-prefixed security source"
        )


def verify_leading_dot_copy(
    *,
    github_repo: str,
    github_ref: str,
    hf_repo: str,
    hf_ref: str,
    opener: Callable[..., Any] = urllib.request.urlopen,
) -> str:
    relative = ".well-known/security.txt"
    encoded_path = urllib.parse.quote(relative, safe="/")
    github_url = (
        f"https://raw.githubusercontent.com/{github_repo}/{github_ref}/{encoded_path}"
    )
    hf_url = f"https://huggingface.co/spaces/{hf_repo}/resolve/{hf_ref}/{encoded_path}"
    try:
        github_bytes = _read_url(github_url, opener=opener)
        hf_bytes = _read_url(hf_url, opener=opener)
    except Exception as exc:
        raise ParityError(f"cannot read immutable dot-prefixed sources: {exc}") from exc
    if github_bytes != hf_bytes:
        raise ParityError(
            "dot-prefixed COPY source drift: "
            f"github={hashlib.sha256(github_bytes).hexdigest()} "
            f"hf={hashlib.sha256(hf_bytes).hexdigest()}"
        )
    return hashlib.sha256(github_bytes).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tools-script", type=Path, required=True)
    parser.add_argument("--github-repo", required=True)
    parser.add_argument("--github-ref", required=True)
    parser.add_argument("--hf-repo", required=True)
    parser.add_argument("--report-out", type=Path, required=True)
    args = parser.parse_args(argv)

    if not SHA_RE.fullmatch(args.github_ref):
        raise ParityError("github-ref must be an exact lowercase 40-character SHA")
    if not args.tools_script.is_file():
        raise ParityError("pinned comparator script is absent")

    hf_ref = resolve_stable_revision(args.hf_repo)
    verify_github_tree_complete(args.github_repo, github_ref=args.github_ref)
    command = [
        sys.executable,
        str(args.tools_script),
        "--github-remote",
        "--github-repo",
        args.github_repo,
        "--hf-repo",
        args.hf_repo,
        "--github-ref",
        args.github_ref,
        "--hf-ref",
        hf_ref,
        "--report-out",
        str(args.report_out),
    ]
    subprocess.run(command, check=True)
    report = json.loads(args.report_out.read_text(encoding="utf-8"))
    validate_report(report, github_ref=args.github_ref, hf_ref=hf_ref)
    dot_sha256 = verify_leading_dot_copy(
        github_repo=args.github_repo,
        github_ref=args.github_ref,
        hf_repo=args.hf_repo,
        hf_ref=hf_ref,
    )
    report["immutable_hf_ref"] = hf_ref
    report["leading_dot_copy"] = {
        "path": ".well-known/security.txt",
        "sha256": dot_sha256,
        "status": "exact",
    }
    report["proof_status"] = "exact"
    args.report_out.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"HF repository parity exact: github={args.github_ref} "
        f"hf={hf_ref} files={report['files_compared']}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ParityError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
