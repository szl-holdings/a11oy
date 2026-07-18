#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Independently verify a Sigstore One Lathe snapshot receipt."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from sign_lathe_snapshot import (  # noqa: E402
    ARTIFACT_PATH,
    MAX_SNAPSHOT_BYTES,
    PAYLOAD_TYPE,
    RECEIPT_SUBJECT_SCHEMA,
    SUBJECT_NAME,
    _read_regular_file,
    load_validated_snapshot,
    receipt_subject,
)
import lathe_snapshot as lathe  # noqa: E402
from szl_formulas import verify_dsse_real  # noqa: E402


OIDC_ISSUER = "https://token.actions.githubusercontent.com"
IN_TOTO_PAYLOAD_TYPE = "application/vnd.in-toto+json"
IN_TOTO_STATEMENT_TYPE = "https://in-toto.io/Statement/v1"
GOVERNANCE_PREDICATE_TYPE = (
    "https://szl-holdings.dev/attestations/governance-receipt/v1"
)
MAX_RECEIPT_BYTES = 32 * 1024 * 1024


def load_receipt_envelope(path: Path) -> dict:
    """Load one bounded, duplicate-free regular receipt file."""

    raw = _read_regular_file(path, max_bytes=MAX_RECEIPT_BYTES)
    try:
        envelope = json.loads(raw, object_pairs_hook=lathe._json_object)
    except (json.JSONDecodeError, UnicodeDecodeError, lathe.LatheSnapshotError) as exc:
        raise ValueError("receipt is not valid duplicate-free UTF-8 JSON") from exc
    if not isinstance(envelope, dict):
        raise ValueError("receipt root must be a JSON object")
    return envelope


def _verified_dsse_envelope(envelope: dict) -> dict:
    """Return the bundle's verified DSSE envelope and reject outer-field splicing."""

    bundled = ((envelope.get("_sigstore") or {}).get("bundle") or {}).get(
        "dsseEnvelope"
    )
    if not isinstance(bundled, dict):
        raise ValueError("receipt does not contain a bundled DSSE envelope")
    for field in ("payloadType", "payload", "signatures"):
        if envelope.get(field) != bundled.get(field):
            raise ValueError(f"outer {field} does not match the verified Sigstore bundle")
    if bundled.get("payloadType") != IN_TOTO_PAYLOAD_TYPE:
        raise ValueError("bundled DSSE payload type is not in-toto JSON")
    return bundled


def _decode_statement(envelope: dict) -> dict:
    bundled = _verified_dsse_envelope(envelope)
    try:
        statement = json.loads(base64.b64decode(bundled["payload"], validate=True))
    except (KeyError, ValueError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("envelope does not contain a valid in-toto statement") from exc
    if not isinstance(statement, dict):
        raise ValueError("in-toto statement must be a JSON object")
    if statement.get("_type") != IN_TOTO_STATEMENT_TYPE:
        raise ValueError("signed statement uses the wrong in-toto type")
    if statement.get("predicateType") != GOVERNANCE_PREDICATE_TYPE:
        raise ValueError("signed statement uses the wrong predicate type")
    return statement


def verified_rekor_log_index(envelope: dict) -> int:
    """Read the Rekor index from the same bundle verified by Sigstore."""

    entries = (
        ((envelope.get("_sigstore") or {}).get("bundle") or {})
        .get("verificationMaterial", {})
        .get("tlogEntries", [])
    )
    if not isinstance(entries, list) or len(entries) != 1:
        raise ValueError("verified Sigstore bundle must contain exactly one Rekor entry")
    log_index = entries[0].get("logIndex")
    if not isinstance(log_index, int) or isinstance(log_index, bool) or log_index < 0:
        raise ValueError("verified Sigstore bundle has an invalid Rekor log index")
    return log_index


def verify_subject(
    envelope: dict,
    snapshot: dict,
    *,
    repository: str,
    source_revision: str,
    workflow_identity: str,
    artifact_path: str = ARTIFACT_PATH,
) -> None:
    statement = _decode_statement(envelope)
    predicate = statement.get("predicate") or {}
    if predicate.get("dsse_payload_type") != PAYLOAD_TYPE:
        raise ValueError("signed predicate uses the wrong Lathe payload type")
    try:
        signed_payload = base64.b64decode(predicate["payload_b64"], validate=True)
    except (KeyError, ValueError, TypeError) as exc:
        raise ValueError("signed predicate does not contain a valid snapshot payload") from exc
    expected_subject = receipt_subject(
        snapshot,
        repository=repository,
        source_revision=source_revision,
        workflow_identity=workflow_identity,
        artifact_path=artifact_path,
    )
    expected_payload = json.dumps(
        expected_subject,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    if signed_payload != expected_payload:
        raise ValueError("signed payload does not match the canonical provenance-bound subject")

    decoded_subject = json.loads(signed_payload)
    if decoded_subject.get("schemaVersion") != RECEIPT_SUBJECT_SCHEMA:
        raise ValueError("signed receipt-subject schema is not recognized")

    expected_sha256 = hashlib.sha256(expected_payload).hexdigest()
    subjects = statement.get("subject") or []
    if len(subjects) != 1:
        raise ValueError("signed statement must contain exactly one subject")
    subject = subjects[0]
    if subject.get("name") != SUBJECT_NAME:
        raise ValueError("signed statement subject name does not match One Lathe")
    if (subject.get("digest") or {}).get("sha256") != expected_sha256:
        raise ValueError("signed subject digest does not match the canonical snapshot")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("envelope")
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--identity", required=True)
    parser.add_argument("--issuer", default=OIDC_ISSUER)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--artifact-path", default=ARTIFACT_PATH)
    args = parser.parse_args(argv)

    try:
        envelope = load_receipt_envelope(Path(args.envelope))
        if envelope.get("_mode") != "SIGSTORE-KEYLESS":
            raise ValueError("receipt is not a real Sigstore keyless envelope")
        verify_dsse_real(
            envelope,
            identity=args.identity,
            issuer=args.issuer,
        )
        rekor_log_index = verified_rekor_log_index(envelope)
        snapshot = load_validated_snapshot(Path(args.snapshot))
        verify_subject(
            envelope,
            snapshot,
            repository=args.repository,
            source_revision=args.source_revision,
            workflow_identity=args.identity,
            artifact_path=args.artifact_path,
        )
    except Exception as exc:  # verification must fail closed on every malformed input
        print(f"[lathe-verify] FAILED: {exc}", file=sys.stderr)
        return 1

    print("[lathe-verify] VERIFIED")
    print(f"[lathe-verify] snapshot_digest={snapshot['digest']}")
    print(f"[lathe-verify] rekor_log_index={rekor_log_index}")
    print(f"[lathe-verify] identity={args.identity}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
