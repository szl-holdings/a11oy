#!/usr/bin/env python3
"""Fail-closed GitHub/Hugging Face repository parity orchestration.

The pinned organization comparator is retained for its Dockerfile COPY
expansion. Protected-base proof remains strict. A candidate may pass one
explicit, same-checkout allowlist whose bytes are snapshotted once and whose
warning set must exactly match the comparator report. The comparator's known
dot-prefixed normalization gap is always covered by an independent byte
comparison of ``.well-known/security.txt``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path, PurePosixPath
from typing import Any, Callable

SHA_RE = re.compile(r"^[0-9a-f]{40}$")
REPO_ROOT = Path(__file__).resolve().parents[2]
ALLOWLIST_RELATIVE_PATH = Path(".github/hf-module-drift-allow.json")
CANONICAL_GITHUB_REPO = "szl-holdings/a11oy"
CANONICAL_HF_REPO = "SZLHOLDINGS/a11oy"
MAX_ALLOW_PATH_LENGTH = 512
MAX_ALLOW_REASON_LENGTH = 500
MAX_ALLOW_COMMENT_LENGTH = 2_000
ALLOWED_ALLOWLIST_KEYS = frozenset(
    {"_comment", "ignore_paths", "ignore_extensions", "accepted_divergences"}
)
PROTECTED_IGNORE_PATHS = frozenset(
    {"console/assets/**", "console/static/**", "pages/claims/**"}
)
PROTECTED_IGNORE_EXTENSIONS = frozenset(
    {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
        ".ico",
        ".svg",
        ".wasm",
        ".woff",
        ".woff2",
        ".ttf",
        ".eot",
        ".mp4",
        ".mp3",
        ".pdf",
        ".zip",
        ".gz",
        ".br",
        ".map",
    }
)
EXPECTED_COMPATIBILITY_WARNING = {
    "kind": "missing-both",
    "path": "well-known/security.txt",
    "severity": "warn",
}


class ParityError(RuntimeError):
    """Raised when immutable repository parity cannot be proved."""


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ParityError(f"duplicate JSON key is forbidden: {key}")
        result[key] = value
    return result


def _parse_json_bytes(raw: bytes, *, label: str) -> object:
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ParityError(f"{label} must not contain a UTF-8 BOM")
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ParityError(f"{label} is not strict UTF-8: {exc}") from exc
    try:
        return json.loads(text, object_pairs_hook=_unique_object)
    except json.JSONDecodeError as exc:
        raise ParityError(f"{label} is not valid JSON: {exc}") from exc


def _validate_exclusion_subset(
    payload: dict[str, object],
    *,
    key: str,
    protected: frozenset[str],
) -> None:
    values = payload.get(key, [])
    if type(values) is not list or any(type(value) is not str for value in values):
        raise ParityError(f"{key} must be an array of strings")
    if len(values) != len(set(values)):
        raise ParityError(f"{key} must not contain duplicates")
    unexpected = sorted(set(values) - protected)
    if unexpected:
        raise ParityError(f"{key} broadens protected exclusions: {unexpected!r}")


def parse_allowlist_snapshot(raw: bytes) -> dict[str, str]:
    payload = _parse_json_bytes(raw, label="HF parity allowlist")
    if not isinstance(payload, dict):
        raise ParityError("HF parity allowlist must be one JSON object")
    unknown_keys = sorted(set(payload) - ALLOWED_ALLOWLIST_KEYS)
    if unknown_keys:
        raise ParityError(f"HF parity allowlist contains unknown policy keys: {unknown_keys!r}")
    comment = payload.get("_comment")
    if comment is not None and (
        type(comment) is not str
        or len(comment) > MAX_ALLOW_COMMENT_LENGTH
        or any(ord(character) < 32 and character not in "\t\n\r" for character in comment)
    ):
        raise ParityError("HF parity allowlist comment must be bounded text")
    _validate_exclusion_subset(
        payload,
        key="ignore_paths",
        protected=PROTECTED_IGNORE_PATHS,
    )
    _validate_exclusion_subset(
        payload,
        key="ignore_extensions",
        protected=PROTECTED_IGNORE_EXTENSIONS,
    )
    accepted = payload.get("accepted_divergences")
    if not isinstance(accepted, dict):
        raise ParityError("accepted_divergences must be one JSON object")

    normalized: dict[str, str] = {}
    forbidden = {".well-known/security.txt", "well-known/security.txt"}
    for path, reason in accepted.items():
        if not isinstance(path, str) or not path or len(path) > MAX_ALLOW_PATH_LENGTH:
            raise ParityError("allowlist paths must be non-empty bounded strings")
        if "\\" in path or any(ord(character) < 32 or ord(character) == 127 for character in path):
            raise ParityError(f"allowlist path is not normalized POSIX text: {path!r}")
        parsed = PurePosixPath(path)
        if (
            parsed.is_absolute()
            or parsed.as_posix() != path
            or any(part in {"", ".", ".."} for part in parsed.parts)
        ):
            raise ParityError(f"allowlist path is not a normalized relative path: {path!r}")
        if path in forbidden:
            raise ParityError("the mandatory security.txt byte proof cannot be allowlisted")
        if (
            not isinstance(reason, str)
            or not reason.strip()
            or len(reason) > MAX_ALLOW_REASON_LENGTH
            or any(ord(character) < 32 and character not in "\t\n\r" for character in reason)
        ):
            raise ParityError(f"allowlist reason must be a non-empty bounded string: {path}")
        normalized[path] = reason
    return normalized


def _checkout_head(root: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _committed_blob(root: Path, github_ref: str, relative_path: str) -> bytes:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "show", f"{github_ref}:{relative_path}"],
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ParityError(f"cannot read admitted allowlist blob: {exc}") from exc
    return result.stdout


def load_candidate_allowlist(
    path: Path,
    *,
    github_ref: str,
    head_resolver: Callable[[Path], str] = _checkout_head,
    blob_resolver: Callable[[Path, str, str], bytes] = _committed_blob,
) -> tuple[bytes, dict[str, str]]:
    expected = (REPO_ROOT / ALLOWLIST_RELATIVE_PATH).resolve()
    supplied = path.resolve()
    if supplied != expected:
        raise ParityError(
            "candidate allowlist must be .github/hf-module-drift-allow.json "
            "from the wrapper's own checkout"
        )
    if not supplied.is_file():
        raise ParityError("candidate HF parity allowlist is absent")
    if head_resolver(REPO_ROOT) != github_ref:
        raise ParityError("candidate checkout HEAD is not the admitted github-ref")
    try:
        raw = supplied.read_bytes()
    except OSError as exc:
        raise ParityError(f"cannot read candidate allowlist: {exc}") from exc
    committed = blob_resolver(
        REPO_ROOT,
        github_ref,
        ALLOWLIST_RELATIVE_PATH.as_posix(),
    )
    if raw != committed:
        raise ParityError("candidate allowlist bytes do not match the admitted commit blob")
    return raw, parse_allowlist_snapshot(raw)


def validate_repository_identity(github_repo: str, hf_repo: str) -> None:
    if github_repo != CANONICAL_GITHUB_REPO:
        raise ParityError("github-repo is not the canonical a11oy repository")
    if hf_repo != CANONICAL_HF_REPO:
        raise ParityError("hf-repo is not the canonical a11oy Space")


def run_comparator(
    command: list[str],
    *,
    allow_bytes: bytes | None,
    runner: Callable[..., Any] = subprocess.run,
) -> None:
    if allow_bytes is None:
        runner(command, check=True)
        return
    with tempfile.TemporaryDirectory(prefix="a11oy-hf-allow-") as temp_dir:
        snapshot = Path(temp_dir) / "hf-module-drift-allow.json"
        snapshot.write_bytes(allow_bytes)
        snapshot.chmod(0o400)
        runner([*command, "--allow", str(snapshot)], check=True)


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


def validate_report(
    report: object,
    *,
    github_ref: str,
    hf_ref: str,
    accepted_divergences: dict[str, str] | None = None,
) -> None:
    if not isinstance(report, dict):
        raise ParityError("comparator report must be an object")
    for counter in ("error_count", "warn_count", "files_compared"):
        if type(report.get(counter)) is not int:
            raise ParityError(f"comparator {counter} must be an exact integer")
    if report.get("status") != "ok" or report.get("error_count") != 0:
        raise ParityError("comparator did not produce an exact zero-error result")
    if report.get("github_ref") != github_ref or report.get("hf_ref") != hf_ref:
        raise ParityError(
            "comparator report is not bound to the admitted immutable revisions"
        )
    if report["files_compared"] <= 0:
        raise ParityError("comparator did not prove any managed files")

    findings = report.get("findings")
    if not isinstance(findings, list):
        raise ParityError("comparator findings must be an array")
    if not all(isinstance(finding, dict) for finding in findings):
        raise ParityError("every comparator finding must be one object")

    accepted = accepted_divergences or {}
    observed_allowed: dict[str, str] = {}
    observed_paths: set[str] = set()
    compatibility_count = 0
    for finding in findings:
        path = finding.get("path")
        if not isinstance(path, str) or path in observed_paths:
            raise ParityError("comparator finding paths must be unique strings")
        observed_paths.add(path)
        normalized = {
            key: finding.get(key) for key in ("kind", "path", "severity")
        }
        if normalized == EXPECTED_COMPATIBILITY_WARNING:
            compatibility_count += 1
            continue
        if finding.get("kind") != "drift" or finding.get("severity") != "warn":
            raise ParityError(f"unexpected comparator finding: {normalized!r}")
        expected_reason = accepted.get(path)
        if expected_reason is None or finding.get("reason") != expected_reason:
            raise ParityError(f"unbound comparator warning: {path}")
        observed_allowed[path] = expected_reason

    if compatibility_count != 1:
        raise ParityError("the guarded security.txt compatibility warning is not exact")
    if observed_allowed != accepted:
        missing = sorted(set(accepted) - set(observed_allowed))
        extra = sorted(set(observed_allowed) - set(accepted))
        raise ParityError(
            f"allowlist/report warning set mismatch: missing={missing!r} extra={extra!r}"
        )
    expected_warn_count = len(accepted) + 1
    if report.get("warn_count") != expected_warn_count or len(findings) != expected_warn_count:
        raise ParityError("comparator warning count does not match the exact admitted set")


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
    parser.add_argument("--allow", type=Path)
    parser.add_argument("--report-out", type=Path, required=True)
    args = parser.parse_args(argv)

    if not SHA_RE.fullmatch(args.github_ref):
        raise ParityError("github-ref must be an exact lowercase 40-character SHA")
    validate_repository_identity(args.github_repo, args.hf_repo)
    if not args.tools_script.is_file():
        raise ParityError("pinned comparator script is absent")

    allow_bytes: bytes | None = None
    accepted_divergences: dict[str, str] = {}
    if args.allow is not None:
        allow_bytes, accepted_divergences = load_candidate_allowlist(
            args.allow,
            github_ref=args.github_ref,
        )

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
    run_comparator(command, allow_bytes=allow_bytes)
    try:
        report_bytes = args.report_out.read_bytes()
    except OSError as exc:
        raise ParityError(f"cannot read comparator report: {exc}") from exc
    report = _parse_json_bytes(report_bytes, label="comparator report")
    validate_report(
        report,
        github_ref=args.github_ref,
        hf_ref=hf_ref,
        accepted_divergences=accepted_divergences,
    )
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
