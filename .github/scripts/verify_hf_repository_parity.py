#!/usr/bin/env python3
"""Fail-closed GitHub/Hugging Face repository parity orchestration.

The pinned organization comparator is retained for its Dockerfile COPY
expansion. Strict mode proves exact protected-source parity. Candidate mode
first proves that same exact baseline, then permits only comparator drift that
is byte-bound to the reviewed GitHub base-to-head delta. Neither mode accepts a
persisted allowlist, and the comparator's known dot-prefixed normalization gap
is covered by an explicit byte comparison of ``.well-known/security.txt``.
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
from pathlib import Path
from typing import Any, Callable

SHA_RE = re.compile(r"^[0-9a-f]{40}$")
REPORT_SCHEMA = 1
CANDIDATE_AHEAD_VALUES = frozenset(
    {"github", "github?", "huggingface", "huggingface?", "tied", "unknown"}
)
EXPECTED_COMPATIBILITY_WARNING = {
    "kind": "missing-both",
    "path": "well-known/security.txt",
    "severity": "warn",
}
PROTECTED_CANDIDATE_INPUTS = (
    "Dockerfile",
    ".well-known/security.txt",
    ".github/scripts/verify_hf_repository_parity.py",
)


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


def validate_report(
    report: object,
    *,
    github_repo: str,
    github_ref: str,
    hf_repo: str,
    hf_ref: str,
) -> None:
    if not isinstance(report, dict):
        raise ParityError("comparator report must be an object")
    if type(report.get("schema")) is not int or report["schema"] != REPORT_SCHEMA:
        raise ParityError(
            f"comparator schema must be the exact integer {REPORT_SCHEMA}"
        )
    if (
        report.get("github_repo") != github_repo
        or report.get("hf_repo") != hf_repo
    ):
        raise ParityError("comparator report is not bound to the admitted repositories")
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
    if len(findings) != 1 or not all(
        isinstance(finding, dict) for finding in findings
    ):
        raise ParityError("comparator findings must contain exactly one object")
    normalized = [
        {key: finding.get(key) for key in ("kind", "path", "severity")}
        for finding in findings
    ]
    if normalized != [EXPECTED_COMPATIBILITY_WARNING]:
        raise ParityError(f"unexpected comparator findings: {normalized!r}")
    if report.get("warn_count") != 1:
        raise ParityError(
            "comparator warning count does not match the guarded compatibility gap"
        )


def validate_candidate_report(
    report: object,
    *,
    base_ref: str,
    github_repo: str,
    github_ref: str,
    hf_repo: str,
    hf_ref: str,
    base_tree: dict[str, str],
    head_tree: dict[str, str],
    expected_files_compared: int,
) -> list[str]:
    """Return the exact review-bound drift paths or fail closed.

    The protected base has already been proved byte-identical to ``hf_ref``.
    Consequently, a candidate finding is admissible only when it is an ordinary
    byte modification on a path whose Git blob changed between the exact
    reviewed base and head. The comparator's ``ahead`` label is date-derived
    metadata, not content authority. Additions, deletions, lineage conflicts
    and drift on unchanged paths remain hard failures.
    """

    if not isinstance(report, dict):
        raise ParityError("candidate comparator report must be an object")
    if base_ref == github_ref:
        raise ParityError(
            "candidate head must be a strict descendant of the reviewed protected base"
        )
    if type(report.get("schema")) is not int or report["schema"] != REPORT_SCHEMA:
        raise ParityError(
            f"candidate comparator schema must be the exact integer {REPORT_SCHEMA}"
        )
    if (
        report.get("github_repo") != github_repo
        or report.get("hf_repo") != hf_repo
    ):
        raise ParityError(
            "candidate comparator report is not bound to the admitted repositories"
        )
    for counter in ("error_count", "warn_count", "files_compared"):
        if type(report.get(counter)) is not int:
            raise ParityError(f"candidate comparator {counter} must be an exact integer")
    if report.get("github_ref") != github_ref or report.get("hf_ref") != hf_ref:
        raise ParityError(
            "candidate comparator report is not bound to the admitted immutable revisions"
        )
    if report["files_compared"] != expected_files_compared:
        raise ParityError(
            "candidate comparator managed-file count does not match the "
            f"proved protected base: expected {expected_files_compared}, "
            f"received {report['files_compared']}"
        )

    findings = report.get("findings")
    if not isinstance(findings, list) or not all(
        isinstance(finding, dict) for finding in findings
    ):
        raise ParityError("candidate comparator findings must be an object array")

    warnings = [finding for finding in findings if finding.get("severity") == "warn"]
    errors = [finding for finding in findings if finding.get("severity") == "error"]
    if len(warnings) != 1:
        raise ParityError("candidate comparator must contain one guarded compatibility warning")
    normalized_warning = {
        key: warnings[0].get(key) for key in ("kind", "path", "severity")
    }
    if normalized_warning != EXPECTED_COMPATIBILITY_WARNING:
        raise ParityError(f"unexpected candidate comparator warning: {normalized_warning!r}")
    if report["warn_count"] != 1 or report["error_count"] != len(errors):
        raise ParityError("candidate comparator counters do not match its findings")
    if len(findings) != len(warnings) + len(errors):
        raise ParityError("candidate comparator contains an untyped finding")

    expected_status = "drift" if errors else "ok"
    if report.get("status") != expected_status:
        raise ParityError(
            f"candidate comparator status must be {expected_status!r} for its findings"
        )

    reviewed_paths = {
        path
        for path in set(base_tree) | set(head_tree)
        if base_tree.get(path) != head_tree.get(path)
    }
    admitted: list[str] = []
    for finding in errors:
        path = finding.get("path")
        ahead = finding.get("ahead")
        if (
            finding.get("kind") != "drift"
            or not isinstance(ahead, str)
            or ahead not in CANDIDATE_AHEAD_VALUES
            or finding.get("lineage_conflict") is not False
            or not isinstance(path, str)
        ):
            raise ParityError(f"unexplained candidate comparator finding: {finding!r}")
        if (
            path not in reviewed_paths
            or path not in base_tree
            or path not in head_tree
        ):
            raise ParityError(
                f"candidate drift is not an exact reviewed byte modification: {path!r}"
            )
        if (
            finding.get("github_sha") != head_tree[path]
            or finding.get("hf_oid") != base_tree[path]
        ):
            raise ParityError(
                f"candidate drift hashes are not bound to the reviewed trees: {path!r}"
            )
        admitted.append(path)

    if len(admitted) != len(set(admitted)):
        raise ParityError("candidate comparator repeated a drift path")
    return sorted(admitted)


def validate_candidate_exit_code(returncode: int, admitted: list[str]) -> None:
    """Bind the comparator process result to the validated report semantics."""

    if type(returncode) is not int:
        raise ParityError("candidate comparator exit code must be an exact integer")
    expected = 1 if admitted else 0
    if returncode != expected:
        raise ParityError(
            "candidate comparator exit/report mismatch: "
            f"expected {expected}, received {returncode}"
        )


def validate_protected_candidate_inputs(
    base_tree: dict[str, str], head_tree: dict[str, str]
) -> None:
    """Prevent a candidate from changing the authority used to admit it."""

    for protected_path in PROTECTED_CANDIDATE_INPUTS:
        base_sha = base_tree.get(protected_path)
        head_sha = head_tree.get(protected_path)
        if (
            not isinstance(base_sha, str)
            or not SHA_RE.fullmatch(base_sha)
            or head_sha != base_sha
        ):
            raise ParityError(
                f"candidate protected admission input is missing or changed: "
                f"{protected_path!r}; "
                "use a dedicated deployment-contract successor"
            )


def github_blob_tree(
    github_repo: str,
    *,
    github_ref: str,
    opener: Callable[..., Any] = urllib.request.urlopen,
) -> dict[str, str]:
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

    blobs: dict[str, str] = {}
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("type") != "blob":
            continue
        path = entry.get("path")
        sha = entry.get("sha")
        if not isinstance(path, str) or not isinstance(sha, str) or not SHA_RE.fullmatch(sha):
            raise ParityError("exact GitHub tree contains an invalid blob entry")
        if path in blobs:
            raise ParityError(f"exact GitHub tree repeats blob path: {path}")
        blobs[path] = sha
    if not blobs:
        raise ParityError("exact GitHub recursive tree contains no blobs")
    return blobs


def verify_ancestry(
    github_repo: str,
    *,
    base_ref: str,
    github_ref: str,
    opener: Callable[..., Any] = urllib.request.urlopen,
) -> None:
    if base_ref == github_ref:
        raise ParityError(
            "candidate head must be a strict descendant of the reviewed protected base"
        )
    url = f"https://api.github.com/repos/{github_repo}/compare/{base_ref}...{github_ref}"
    try:
        comparison = json.loads(_read_url(url, opener=opener))
    except Exception as exc:
        raise ParityError(f"cannot prove exact GitHub ancestry: {exc}") from exc
    if not isinstance(comparison, dict) or comparison.get("status") != "ahead":
        raise ParityError(
            "candidate head is not a strict descendant of the reviewed protected base"
        )


def verify_github_tree_complete(
    github_repo: str,
    *,
    github_ref: str,
    opener: Callable[..., Any] = urllib.request.urlopen,
) -> None:
    blobs = github_blob_tree(
        github_repo, github_ref=github_ref, opener=opener
    )
    if ".well-known/security.txt" not in blobs:
        raise ParityError(
            "exact GitHub tree does not contain one dot-prefixed security source"
        )


def run_comparator(
    *,
    tools_script: Path,
    github_repo: str,
    github_ref: str,
    hf_repo: str,
    hf_ref: str,
    report_out: Path,
    capture: bool = False,
) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        str(tools_script),
        "--github-remote",
        "--github-repo",
        github_repo,
        "--hf-repo",
        hf_repo,
        "--github-ref",
        github_ref,
        "--hf-ref",
        hf_ref,
        "--allow",
        "",
        "--report-out",
        str(report_out),
    ]
    return subprocess.run(
        command,
        check=False,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.STDOUT if capture else None,
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
    parser.add_argument("--base-ref", default="")
    parser.add_argument("--github-ref", required=True)
    parser.add_argument("--hf-repo", required=True)
    parser.add_argument("--report-out", type=Path, required=True)
    args = parser.parse_args(argv)

    if not SHA_RE.fullmatch(args.github_ref):
        raise ParityError("github-ref must be an exact lowercase 40-character SHA")
    if args.base_ref and not SHA_RE.fullmatch(args.base_ref):
        raise ParityError("base-ref must be an exact lowercase 40-character SHA")
    if args.base_ref and args.base_ref == args.github_ref:
        raise ParityError(
            "candidate head must be a strict descendant of the reviewed protected base"
        )
    if not args.tools_script.is_file():
        raise ParityError("pinned comparator script is absent")

    args.report_out.unlink(missing_ok=True)

    hf_ref = resolve_stable_revision(args.hf_repo)
    head_tree = github_blob_tree(args.github_repo, github_ref=args.github_ref)

    if args.base_ref:
        verify_ancestry(
            args.github_repo,
            base_ref=args.base_ref,
            github_ref=args.github_ref,
        )
        base_tree = github_blob_tree(args.github_repo, github_ref=args.base_ref)
        validate_protected_candidate_inputs(base_tree, head_tree)

        with tempfile.TemporaryDirectory() as temporary:
            base_report_path = Path(temporary) / "base-parity.json"
            base_run = run_comparator(
                tools_script=args.tools_script,
                github_repo=args.github_repo,
                github_ref=args.base_ref,
                hf_repo=args.hf_repo,
                hf_ref=hf_ref,
                report_out=base_report_path,
                capture=True,
            )
            try:
                base_report = json.loads(base_report_path.read_text(encoding="utf-8"))
                validate_report(
                    base_report,
                    github_repo=args.github_repo,
                    github_ref=args.base_ref,
                    hf_repo=args.hf_repo,
                    hf_ref=hf_ref,
                )
            except (OSError, json.JSONDecodeError, ParityError):
                if base_run.stdout:
                    print(base_run.stdout, file=sys.stderr)
                raise
            if base_run.returncode != 0:
                raise ParityError("protected-base comparator exited non-zero")

        dot_sha256 = verify_leading_dot_copy(
            github_repo=args.github_repo,
            github_ref=args.base_ref,
            hf_repo=args.hf_repo,
            hf_ref=hf_ref,
        )
        with tempfile.TemporaryDirectory() as temporary:
            candidate_report_path = Path(temporary) / "candidate-parity.json"
            candidate_run = run_comparator(
                tools_script=args.tools_script,
                github_repo=args.github_repo,
                github_ref=args.github_ref,
                hf_repo=args.hf_repo,
                hf_ref=hf_ref,
                report_out=candidate_report_path,
                capture=True,
            )
            try:
                report = json.loads(
                    candidate_report_path.read_text(encoding="utf-8")
                )
                admitted = validate_candidate_report(
                    report,
                    base_ref=args.base_ref,
                    github_repo=args.github_repo,
                    github_ref=args.github_ref,
                    hf_repo=args.hf_repo,
                    hf_ref=hf_ref,
                    base_tree=base_tree,
                    head_tree=head_tree,
                    expected_files_compared=base_report["files_compared"],
                )
            except (OSError, json.JSONDecodeError, ParityError):
                if candidate_run.stdout:
                    print(candidate_run.stdout, file=sys.stderr)
                raise
        validate_candidate_exit_code(candidate_run.returncode, admitted)
        report["admission_status"] = "ok"
        report["base_ref"] = args.base_ref
        report["candidate_changed_path_count"] = sum(
            base_tree.get(path) != head_tree.get(path)
            for path in set(base_tree) | set(head_tree)
        )
        report["review_bound_drift_paths"] = admitted
        report["proof_status"] = "review-bound-candidate-delta"
    else:
        with tempfile.TemporaryDirectory() as temporary:
            strict_report_path = Path(temporary) / "strict-parity.json"
            strict_run = run_comparator(
                tools_script=args.tools_script,
                github_repo=args.github_repo,
                github_ref=args.github_ref,
                hf_repo=args.hf_repo,
                hf_ref=hf_ref,
                report_out=strict_report_path,
                capture=True,
            )
            if strict_run.returncode != 0:
                if strict_run.stdout:
                    print(strict_run.stdout, file=sys.stderr)
                raise ParityError("strict repository comparator exited non-zero")
            report = json.loads(strict_report_path.read_text(encoding="utf-8"))
            validate_report(
                report,
                github_repo=args.github_repo,
                github_ref=args.github_ref,
                hf_repo=args.hf_repo,
                hf_ref=hf_ref,
            )
        dot_sha256 = verify_leading_dot_copy(
            github_repo=args.github_repo,
            github_ref=args.github_ref,
            hf_repo=args.hf_repo,
            hf_ref=hf_ref,
        )
        report["proof_status"] = "exact"

    report["immutable_hf_ref"] = hf_ref
    report["leading_dot_copy"] = {
        "path": ".well-known/security.txt",
        "sha256": dot_sha256,
        "status": "exact",
    }
    args.report_out.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if args.base_ref:
        print(
            f"HF candidate delta review-bound: base={args.base_ref} "
            f"head={args.github_ref} hf={hf_ref} "
            f"admitted={len(report['review_bound_drift_paths'])}"
        )
        for path in report["review_bound_drift_paths"]:
            print(f"::notice title=Review-bound HF candidate drift::{path}")
    else:
        print(
            f"HF repository parity exact: github={args.github_ref} "
            f"hf={hf_ref} files={report['files_compared']}"
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ParityError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
