#!/usr/bin/env python3
"""Validate an inert, digest-bound front-door delta from protected-base bytes."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import urllib.request
from pathlib import Path, PurePosixPath
from typing import Any, Callable


SHA_RE = re.compile(r"^[0-9a-f]{40}$")
MONITORED_PATHS = frozenset(
    {
        "a11oy_landing.html",
        "govern_showcase.html",
        "pages/assurance.html",
        "pages/chaski.html",
        "pages/console.html",
        "pages/fabric.html",
        "pages/landing.html",
        "pages/pinn-console.html",
        "pages/pricing.html",
        "pages/substrate.html",
        "pages/verify.html",
    }
)
MOJIBAKE_LEADERS = ("\u00c2", "\u00c3", "\u00ce", "\u00cf", "\u00e2", "\u00f0", "\ufffd")
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_TOTAL_CHANGED_PATHS = 10_000


class AdmissionError(RuntimeError):
    """Raised when the protected controller cannot admit the candidate."""


def _exact_sha(value: object, label: str) -> str:
    if not isinstance(value, str) or not SHA_RE.fullmatch(value):
        raise AdmissionError(f"{label} must be an exact lowercase 40-character SHA")
    return value


def _read_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AdmissionError(f"cannot read event JSON: {exc}") from exc


def parse_event(path: Path) -> dict[str, object]:
    payload = _read_json(path)
    if not isinstance(payload, dict):
        raise AdmissionError("event payload must be an object")
    action = payload.get("action")
    if action not in {"opened", "synchronize", "reopened", "edited", "ready_for_review"}:
        raise AdmissionError(f"unsupported pull request action: {action!r}")
    pull = payload.get("pull_request")
    repository = payload.get("repository")
    if not isinstance(pull, dict) or not isinstance(repository, dict):
        raise AdmissionError("event lacks pull_request or repository object")
    if pull.get("state") != "open":
        raise AdmissionError("pull request is not open")
    if repository.get("full_name") != "szl-holdings/a11oy":
        raise AdmissionError("event repository is not szl-holdings/a11oy")
    base = pull.get("base")
    head = pull.get("head")
    if not isinstance(base, dict) or not isinstance(head, dict):
        raise AdmissionError("event lacks base or head object")
    base_repo = base.get("repo")
    head_repo = head.get("repo")
    if not isinstance(base_repo, dict) or not isinstance(head_repo, dict):
        raise AdmissionError("event lacks governed repository identity")
    if base.get("ref") != "main" or base_repo.get("full_name") != "szl-holdings/a11oy":
        raise AdmissionError("pull request does not target governed main")
    number = pull.get("number")
    if type(number) is not int or number <= 0:
        raise AdmissionError("pull request number must be a positive exact integer")
    head_repo_name = head_repo.get("full_name")
    if not isinstance(head_repo_name, str) or not head_repo_name:
        raise AdmissionError("event lacks an exact head repository identity")
    return {
        "number": number,
        "base_sha": _exact_sha(base.get("sha"), "base SHA"),
        "head_sha": _exact_sha(head.get("sha"), "head SHA"),
        "head_repo": head_repo_name,
        "action": action,
    }


def _api_json(
    url: str,
    *,
    opener: Callable[..., Any] = urllib.request.urlopen,
) -> object:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "szl-protected-hf-admission/1",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with opener(request, timeout=30) as response:
            return json.loads(response.read())
    except Exception as exc:
        raise AdmissionError(f"GitHub API read failed: {exc}") from exc


def verify_live_pr(
    event: dict[str, object],
    *,
    opener: Callable[..., Any] = urllib.request.urlopen,
) -> None:
    number = event["number"]
    payload = _api_json(
        f"https://api.github.com/repos/szl-holdings/a11oy/pulls/{number}",
        opener=opener,
    )
    if not isinstance(payload, dict):
        raise AdmissionError("live pull request response must be an object")
    if payload.get("state") != "open" or payload.get("number") != number:
        raise AdmissionError("live pull request is absent, closed, or ambiguous")
    base = payload.get("base")
    head = payload.get("head")
    if not isinstance(base, dict) or not isinstance(head, dict):
        raise AdmissionError("live pull request lacks exact refs")
    base_repo = base.get("repo")
    head_repo = head.get("repo")
    if not isinstance(base_repo, dict) or not isinstance(head_repo, dict):
        raise AdmissionError("live pull request lacks repository identity")
    observed = {
        "base_sha": base.get("sha"),
        "head_sha": head.get("sha"),
        "head_repo": head_repo.get("full_name"),
    }
    expected = {key: event[key] for key in observed}
    if observed != expected:
        raise AdmissionError(f"live pull request moved or was retargeted: {observed!r}")
    if base.get("ref") != "main" or base_repo.get("full_name") != "szl-holdings/a11oy":
        raise AdmissionError("live pull request no longer targets governed main")
    protected_ref = _api_json(
        "https://api.github.com/repos/szl-holdings/a11oy/git/ref/heads/main",
        opener=opener,
    )
    if not isinstance(protected_ref, dict):
        raise AdmissionError("protected-main response must be an object")
    protected_object = protected_ref.get("object")
    if not isinstance(protected_object, dict) or protected_object.get("sha") != event["base_sha"]:
        raise AdmissionError("pull request base is not the exact current protected main")
    associated = _api_json(
        f"https://api.github.com/repos/szl-holdings/a11oy/commits/{event['head_sha']}/pulls?per_page=100",
        opener=opener,
    )
    if not isinstance(associated, list):
        raise AdmissionError("head association response must be an array")
    if len(associated) >= 100:
        raise AdmissionError("head association response is not provably complete")
    open_numbers = [
        item.get("number")
        for item in associated
        if isinstance(item, dict) and item.get("state") == "open"
    ]
    if open_numbers != [number]:
        raise AdmissionError(
            f"head must belong to exactly this open pull request: {open_numbers!r}"
        )


def _run_git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *args],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    if completed.returncode:
        raise AdmissionError(
            f"git {' '.join(args)} failed: {completed.stderr.strip()}"
        )
    return completed.stdout.strip()


def _run_git_bytes(root: Path, *args: str) -> bytes:
    completed = subprocess.run(
        ["git", "-C", str(root), *args],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode:
        raise AdmissionError(
            f"git {' '.join(args)} failed: "
            f"{completed.stderr.decode('utf-8', errors='replace').strip()}"
        )
    return completed.stdout


def verify_checkout(root: Path, expected: str, label: str) -> None:
    observed = _run_git(root, "rev-parse", "HEAD")
    if observed != expected:
        raise AdmissionError(f"{label} checkout mismatch: {observed} != {expected}")
    if _run_git(root, "status", "--porcelain"):
        raise AdmissionError(f"{label} checkout is dirty")


def exact_delta(base_root: Path, candidate_root: Path) -> list[tuple[str, str]]:
    base_sha = _run_git(base_root, "rev-parse", "HEAD")
    head_sha = _run_git(candidate_root, "rev-parse", "HEAD")
    _run_git(candidate_root, "merge-base", "--is-ancestor", base_sha, head_sha)
    output = _run_git_bytes(
        candidate_root,
        "diff",
        "--name-status",
        "--no-renames",
        "-z",
        base_sha,
        head_sha,
        "--",
    )
    fields = output.split(b"\0")
    if fields and fields[-1] == b"":
        fields.pop()
    if len(fields) % 2:
        raise AdmissionError("exact Git delta has an incomplete status/path record")
    changes: list[tuple[str, str]] = []
    for offset in range(0, len(fields), 2):
        try:
            status = fields[offset].decode("ascii")
            raw = fields[offset + 1].decode("utf-8")
        except UnicodeDecodeError as exc:
            raise AdmissionError(f"exact Git delta contains invalid path bytes: {exc}") from exc
        if not status or len(status) > 2:
            raise AdmissionError(f"exact Git delta has invalid status: {status!r}")
        normalized = PurePosixPath(raw).as_posix()
        if normalized != raw or raw.startswith("/") or ".." in PurePosixPath(raw).parts:
            raise AdmissionError(f"non-canonical changed path: {raw!r}")
        if any(ord(character) < 32 or ord(character) == 127 for character in raw):
            raise AdmissionError(f"changed path contains a control character: {raw!r}")
        changes.append((status, raw))
    if len(changes) > MAX_TOTAL_CHANGED_PATHS:
        raise AdmissionError(f"candidate changes too many paths: {len(changes)}")
    paths = [path for _, path in changes]
    if len(paths) != len(set(paths)):
        raise AdmissionError("changed path set contains duplicates")
    return changes


def classify_delta(
    base_root: Path, candidate_root: Path
) -> tuple[list[str], list[str]]:
    changes = exact_delta(base_root, candidate_root)
    monitored = sorted(path for _, path in changes if path in MONITORED_PATHS)
    unmanaged = sorted(path for _, path in changes if path not in MONITORED_PATHS)
    if not monitored:
        return [], unmanaged
    if unmanaged:
        raise AdmissionError(
            "managed front-door delta must be isolated from ordinary changes: "
            + ", ".join(unmanaged[:20])
        )
    for status, path in changes:
        if status != "M":
            raise AdmissionError(
                f"managed delta must contain modifications only: {status} {path}"
            )
    return monitored, []


def validate_frontdoor(path: Path) -> dict[str, object]:
    if path.is_symlink() or not path.is_file():
        raise AdmissionError(f"managed path is not a regular file: {path.as_posix()}")
    raw = path.read_bytes()
    if not raw or len(raw) > MAX_FILE_BYTES:
        raise AdmissionError(f"managed file has invalid size: {path.as_posix()}")
    if raw.startswith(b"\xef\xbb\xbf"):
        raise AdmissionError(f"UTF-8 BOM is forbidden: {path.as_posix()}")
    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise AdmissionError(f"invalid UTF-8 in {path.as_posix()}: {exc}") from exc
    for marker in MOJIBAKE_LEADERS:
        if marker in content:
            raise AdmissionError(
                f"mojibake marker U+{ord(marker):04X} in {path.as_posix()}"
            )
    lowered = content.casefold()
    if "<html" not in lowered or "</html>" not in lowered:
        raise AdmissionError(f"managed front-door file is not complete HTML: {path.as_posix()}")
    return {
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
        "git_blob": hashlib.sha1(
            f"blob {len(raw)}\0".encode("ascii") + raw,
            usedforsecurity=False,
        ).hexdigest(),
    }


def admit(
    *,
    event_path: Path,
    base_root: Path,
    candidate_root: Path,
    opener: Callable[..., Any] = urllib.request.urlopen,
) -> dict[str, object]:
    event = parse_event(event_path)
    verify_live_pr(event, opener=opener)
    verify_checkout(base_root, str(event["base_sha"]), "protected base")
    verify_checkout(candidate_root, str(event["head_sha"]), "candidate")
    paths, unmanaged = classify_delta(base_root, candidate_root)
    admitted: dict[str, object] = {}
    for relative in paths:
        admitted[relative] = validate_frontdoor(candidate_root / relative)
    return {
        "status": "PASS",
        "policy": "protected-base-frontdoor-delta-v1",
        "pull_request": event["number"],
        "base_sha": event["base_sha"],
        "head_sha": event["head_sha"],
        "head_repo": event["head_repo"],
        "action": event["action"],
        "changed_paths": paths,
        "unmanaged_path_count": len(unmanaged),
        "files": admitted,
        "post_merge_publication_required": bool(paths),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event-json", type=Path, required=True)
    parser.add_argument("--base-root", type=Path, required=True)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--report-out", type=Path, required=True)
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args()
    try:
        report = admit(
            event_path=args.event_json.resolve(),
            base_root=args.base_root.resolve(),
            candidate_root=args.candidate_root.resolve(),
        )
    except AdmissionError as exc:
        report = {"status": "FAIL", "error": str(exc)}
        args.report_out.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(json.dumps(report, indent=2, sort_keys=True))
        return 1
    args.report_out.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if args.github_output is not None:
        with args.github_output.open("a", encoding="utf-8", newline="\n") as output:
            output.write(
                "managed_delta="
                + ("true" if report["post_merge_publication_required"] else "false")
                + "\n"
            )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
