#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Verify artifact bytes and exact workflow identity with the local GitHub CLI.

Only successful invocations create process-local evidence. Saved JSON reports
are audit material and cannot recreate authority. See the verifier contract at
https://cli.github.com/manual/gh_attestation_verify.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import pathlib
import re
import subprocess
import sys
from typing import Any

MAX_VERIFIER_BYTES = 4 * 1024 * 1024
_AUTHORITY = object()


class VerificationError(ValueError):
    """No verified evidence was established."""


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode()


def _file_digest(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class VerifiedEvidence:
    """A process-local verifier result; not a serializable trust token."""

    __slots__ = ("_statement_bytes", "_metadata_bytes", "_authority")

    def __init__(
        self, statement: dict[str, Any], metadata: dict[str, Any], *, _token=None
    ):
        if _token is not _AUTHORITY:
            raise VerificationError("Evidence must originate from verify_artifact")
        self._statement_bytes = _canonical(statement)
        self._metadata_bytes = _canonical(metadata)
        self._authority = _token

    @property
    def statement(self) -> dict[str, Any]:
        return json.loads(self._statement_bytes)

    @property
    def metadata(self) -> dict[str, Any]:
        return json.loads(self._metadata_bytes)


def proof_metadata(proof: Any, statement: Any) -> dict[str, Any]:
    """Never infer authority from dictionaries, subclasses, or saved reports."""
    if type(proof) is not VerifiedEvidence or proof._authority is not _AUTHORITY:
        return {"verified": False, "source": "untrusted-input"}
    try:
        matches = _canonical(statement) == proof._statement_bytes
    except (TypeError, ValueError, RecursionError):
        matches = False
    if not matches:
        return {"verified": False, "source": "statement-mismatch"}
    return proof.metadata


def verify_artifact(
    artifact: pathlib.Path,
    repository: str,
    workflow: str,
    ref: str,
    *,
    gh: str = "gh",
    source_revision: str | None = None,
    timeout: float = 60,
) -> list[VerifiedEvidence]:
    """Verify current bytes, certificate identity, and source repository/ref.

    The executable path is operator configuration, never HTTP input. This API
    accepts neither saved verifier output nor persisted verified flags.
    """
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise VerificationError("Expected an owner/repository identity")
    if not re.fullmatch(r"\.github/workflows/[A-Za-z0-9_-]+\.ya?ml", workflow):
        raise VerificationError("Expected a .github/workflows/<name>.yml identity")
    if not re.fullmatch(r"refs/(heads|tags)/[A-Za-z0-9_./-]+", ref) or ".." in ref:
        raise VerificationError("Expected a full heads/tags ref identity")
    if source_revision is not None and not re.fullmatch(
        r"[a-fA-F0-9]{40}", source_revision
    ):
        raise VerificationError("Source revision must be a full Git SHA")
    artifact = pathlib.Path(artifact).resolve(strict=True)
    if not artifact.is_file():
        raise VerificationError("Artifact must be a regular file")
    expected_digest = _file_digest(artifact)
    identity = f"https://github.com/{repository}/{workflow}@{ref}"
    command = [
        str(gh),
        "attestation",
        "verify",
        str(artifact),
        "--repo",
        repository,
        "--hostname",
        "github.com",
        "--cert-identity",
        identity,
        "--cert-oidc-issuer",
        "https://token.actions.githubusercontent.com",
        "--source-ref",
        ref,
        "--predicate-type",
        "https://slsa.dev/provenance/v1",
        "--digest-alg",
        "sha256",
        "--limit",
        "10",
        "--format",
        "json",
    ]
    if source_revision:
        command.extend(["--source-digest", source_revision])
    try:
        result = subprocess.run(
            command, text=True, capture_output=True, check=False, timeout=timeout
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise VerificationError(
            f"GitHub verifier unavailable or timed out: {type(exc).__name__}"
        ) from exc
    if result.returncode != 0:
        raise VerificationError(f"GitHub verifier failed with exit {result.returncode}")
    if _file_digest(artifact) != expected_digest:
        raise VerificationError("Artifact changed during verification")
    if len(result.stdout.encode("utf-8")) > MAX_VERIFIER_BYTES:
        raise VerificationError("Verifier result exceeds size limit")
    try:
        entries = json.loads(result.stdout)
    except (ValueError, RecursionError) as exc:
        raise VerificationError("Verifier returned invalid JSON") from exc
    if not isinstance(entries, list) or not 1 <= len(entries) <= 10:
        raise VerificationError("Verifier returned no bounded verified statement list")
    proofs = []
    for entry in entries:
        verified = entry.get("verificationResult") if isinstance(entry, dict) else None
        if not isinstance(verified, dict):
            raise VerificationError("Verifier result has no verificationResult")
        signature = verified.get("signature")
        certificate = (
            signature.get("certificate") if isinstance(signature, dict) else None
        )
        timestamps = verified.get("verifiedTimestamps")
        if (
            not isinstance(certificate, dict)
            or not certificate
            or not isinstance(timestamps, list)
            or not timestamps
        ):
            raise VerificationError(
                "Verifier result lacks certificate or witnessed timestamps"
            )
        statement = verified.get("statement")
        if (
            not isinstance(statement, dict)
            or statement.get("_type") != "https://in-toto.io/Statement/v1"
        ):
            raise VerificationError("Verifier result has no in-toto Statement/v1")
        if statement.get("predicateType") != "https://slsa.dev/provenance/v1":
            raise VerificationError(
                "Verifier statement has an unexpected predicate type"
            )
        subjects = statement.get("subject")
        if not isinstance(subjects, list) or not subjects:
            raise VerificationError("Verifier statement has no subjects")
        matches = any(
            isinstance(subject, dict)
            and isinstance(subject.get("digest"), dict)
            and subject["digest"].get("sha256") == expected_digest
            for subject in subjects
        )
        if not matches:
            raise VerificationError(
                "Verified statement does not bind the artifact SHA-256"
            )
        metadata = {
            "verified": True,
            "source": "in-process-gh-attestation-verify",
            "verifier": "gh attestation verify",
            "repository": repository,
            "workflow": workflow,
            "ref": ref,
            "certificateIdentity": identity,
            "artifactSha256": expected_digest,
            "statementSha256": hashlib.sha256(_canonical(statement)).hexdigest(),
            "sourceRevision": source_revision,
            "verifiedAt": dt.datetime.now(dt.timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
        }
        proofs.append(VerifiedEvidence(statement, metadata, _token=_AUTHORITY))
    return proofs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--workflow", required=True)
    parser.add_argument("--ref", required=True)
    parser.add_argument("--source-revision")
    parser.add_argument("--gh", default="gh")
    parser.add_argument("--opa")
    parser.add_argument(
        "--output", default="anatomy-ledger/evidence/verified/github-verification.json"
    )
    args = parser.parse_args()
    try:
        # Import by the canonical module name so proof identity survives CLI use.
        from verify_release import verify_artifact as run_verifier
        from evaluate_supply_chain import evaluate

        proofs = run_verifier(
            pathlib.Path(args.artifact),
            args.repo,
            args.workflow,
            args.ref,
            gh=args.gh,
            source_revision=args.source_revision,
        )
        records = [
            {
                "statement": proof.statement,
                "verification": proof.metadata,
                "policy": evaluate(
                    {"statement": proof.statement}, opa=args.opa, proof=proof
                ),
            }
            for proof in proofs
        ]
        report = {
            "schema": "szl.anatomy.verifier-report.v1",
            "records": records,
            "disclosure": "Saved report is UNSIGNED audit material; reverify the artifact to establish authority.",
        }
        output = pathlib.Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(output)
        return 0
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
