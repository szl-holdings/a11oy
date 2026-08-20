#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Verify TEST_RECEIPT claims against trusted GitHub Actions job metadata."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from szl_public_claim_manifest import (
    MAX_EVIDENCE_BYTES,
    PublicClaimContractError,
    canonical_utc_timestamp,
    parse_public_claim_manifest,
    strict_json_loads,
)


MAX_MANIFEST_BYTES = 256 * 1024
MAX_GITHUB_RESPONSE_BYTES = 1024 * 1024
_GITHUB_JOB_URL_RE = re.compile(
    r"^https://github\.com/(?P<owner>[A-Za-z0-9_.-]+)/"
    r"(?P<repo>[A-Za-z0-9_.-]+)/actions/runs/(?P<run_id>[1-9][0-9]*)/"
    r"job/(?P<job_id>[1-9][0-9]*)$"
)


ApiGet = Callable[[str], Mapping[str, Any]]


def _error(message: str) -> PublicClaimContractError:
    return PublicClaimContractError(f"GitHub evidence verification: {message}")


def _read_bounded(path: Path, maximum: int, label: str) -> bytes:
    if not path.is_file():
        raise _error(f"{label} is missing")
    with path.open("rb") as handle:
        content = handle.read(maximum + 1)
    if len(content) > maximum:
        raise _error(f"{label} exceeds the {maximum}-byte limit")
    return content


def _json_object(content: bytes, label: str) -> Mapping[str, Any]:
    try:
        value = strict_json_loads(content.decode("utf-8"))
    except (UnicodeError, PublicClaimContractError) as exc:
        raise _error(f"{label} is not strict JSON: {exc}") from exc
    if not isinstance(value, Mapping):
        raise _error(f"{label} must be a JSON object")
    return value


def _string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _error(f"{label} must be a nonblank string")
    return value


def _integer(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise _error(f"{label} must be an integer")
    return value


def _equal(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise _error(f"{label} does not match trusted metadata")


def parse_github_job_url(value: Any) -> tuple[str, int, int]:
    raw = _string(value, "verification_ref")
    match = _GITHUB_JOB_URL_RE.fullmatch(raw)
    if match is None:
        raise _error("verification_ref must be an exact github.com Actions job URL")
    repository = f"{match.group('owner')}/{match.group('repo')}"
    return repository, int(match.group("run_id")), int(match.group("job_id"))


def _github_api_get(url: str, *, token: str) -> Mapping[str, Any]:
    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "a11oy-public-claim-gate",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urlopen(request, timeout=20) as response:
            content = response.read(MAX_GITHUB_RESPONSE_BYTES + 1)
    except (HTTPError, URLError, TimeoutError) as exc:
        raise _error(f"trusted GitHub API request failed for {url}: {exc}") from exc
    if len(content) > MAX_GITHUB_RESPONSE_BYTES:
        raise _error("trusted GitHub API response exceeds the bounded size")
    return _json_object(content, f"GitHub API response from {url}")


def verify_manifest_github_jobs(
    *,
    manifest_path: Path,
    repository_root: Path,
    expected_repository: str,
    api_get: ApiGet,
) -> dict[str, Any]:
    """Cross-bind every TEST_RECEIPT to the authoritative job and run APIs."""
    raw_manifest = _json_object(
        _read_bounded(manifest_path, MAX_MANIFEST_BYTES, "manifest"),
        "manifest",
    )
    manifest = parse_public_claim_manifest(raw_manifest)
    root = repository_root.resolve()
    expected_repository = _string(expected_repository, "expected_repository")
    verifications: list[dict[str, Any]] = []

    for claim in manifest["claims"]:
        source = claim["source"]
        if source["repository"].casefold() != expected_repository.casefold():
            raise _error("claim source repository is outside the workflow repository")
        for evidence in claim["evidence"]:
            if evidence["kind"] != "TEST_RECEIPT":
                continue

            url_repository, run_id, job_id = parse_github_job_url(
                evidence["verification_ref"]
            )
            if url_repository.casefold() != expected_repository.casefold():
                raise _error("verification_ref repository is outside the workflow repository")

            receipt_path = (
                root / Path(*PurePosixPath(evidence["path"]).parts)
            ).resolve()
            try:
                receipt_path.relative_to(root)
            except ValueError as exc:
                raise _error("receipt path escapes the repository root") from exc
            receipt_content = _read_bounded(
                receipt_path, MAX_EVIDENCE_BYTES, f"receipt {evidence['evidence_id']}"
            )
            _equal(
                hashlib.sha256(receipt_content).hexdigest(),
                evidence["content_sha256"],
                "receipt content digest",
            )
            receipt = _json_object(receipt_content, f"receipt {evidence['evidence_id']}")

            _equal(
                _string(receipt.get("repository"), "receipt.repository").casefold(),
                expected_repository.casefold(),
                "receipt repository",
            )
            _equal(
                _string(receipt.get("source_revision"), "receipt.source_revision"),
                source["revision"],
                "receipt source revision",
            )
            _equal(
                _string(receipt.get("source_url"), "receipt.source_url"),
                evidence["verification_ref"],
                "receipt source URL",
            )
            receipt_completed_at = canonical_utc_timestamp(
                receipt.get("completed_at"), "$receipt.completed_at"
            )
            _equal(
                receipt_completed_at,
                evidence["collected_at"],
                "receipt completion time",
            )
            workflow_name = _string(receipt.get("workflow"), "receipt.workflow")
            job_name = _string(receipt.get("job"), "receipt.job")

            api_repository = expected_repository.casefold()
            job_api_url = (
                f"https://api.github.com/repos/{api_repository}/actions/jobs/{job_id}"
            )
            run_api_url = (
                f"https://api.github.com/repos/{api_repository}/actions/runs/{run_id}"
            )
            job = api_get(job_api_url)
            run = api_get(run_api_url)
            if not isinstance(job, Mapping) or not isinstance(run, Mapping):
                raise _error("trusted GitHub API responses must be JSON objects")

            _equal(_integer(job.get("id"), "job.id"), job_id, "job ID")
            _equal(_integer(job.get("run_id"), "job.run_id"), run_id, "job run ID")
            _equal(_string(job.get("html_url"), "job.html_url"), evidence["verification_ref"], "job URL")
            _equal(_string(job.get("head_sha"), "job.head_sha"), source["revision"], "job head SHA")
            _equal(_string(job.get("status"), "job.status"), "completed", "job status")
            _equal(_string(job.get("conclusion"), "job.conclusion"), "success", "job conclusion")
            _equal(_string(job.get("name"), "job.name"), job_name, "job name")
            trusted_completed_at = canonical_utc_timestamp(
                job.get("completed_at"), "$github_job.completed_at"
            )
            _equal(trusted_completed_at, receipt_completed_at, "job completion time")

            expected_run_url = (
                f"https://github.com/{url_repository}/actions/runs/{run_id}"
            )
            _equal(_integer(run.get("id"), "run.id"), run_id, "run ID")
            _equal(_string(run.get("html_url"), "run.html_url").casefold(), expected_run_url.casefold(), "run URL")
            _equal(_string(run.get("head_sha"), "run.head_sha"), source["revision"], "run head SHA")
            _equal(_string(run.get("status"), "run.status"), "completed", "run status")
            _equal(_string(run.get("conclusion"), "run.conclusion"), "success", "run conclusion")
            _equal(_string(run.get("name"), "run.name"), workflow_name, "workflow name")

            verifications.append({
                "evidence_id": evidence["evidence_id"],
                "repository": expected_repository,
                "source_revision": source["revision"],
                "run_id": run_id,
                "job_id": job_id,
                "workflow": workflow_name,
                "job": job_name,
                "completed_at": trusted_completed_at,
                "verification_ref": evidence["verification_ref"],
            })

    if not verifications:
        raise _error("manifest contains no TEST_RECEIPT evidence to verify")
    return {
        "schema_version": "github-actions-evidence-verification.v1",
        "repository": expected_repository,
        "verified_receipt_count": len(verifications),
        "verifications": sorted(verifications, key=lambda row: row["evidence_id"]),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--repository-root", default=".", type=Path)
    parser.add_argument("--expected-repository", required=True)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args(argv)

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        print("GitHub evidence verification: REFUSE (GITHUB_TOKEN is required)", file=sys.stderr)
        return 2
    try:
        report = verify_manifest_github_jobs(
            manifest_path=args.manifest,
            repository_root=args.repository_root,
            expected_repository=args.expected_repository,
            api_get=lambda url: _github_api_get(url, token=token),
        )
    except (OSError, UnicodeError, PublicClaimContractError) as exc:
        print(f"GitHub evidence verification: REFUSE ({exc})", file=sys.stderr)
        return 2

    rendered = json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(rendered, encoding="utf-8")
    print(
        "GitHub evidence verification: PASS "
        f"receipts={report['verified_receipt_count']} repository={report['repository']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
