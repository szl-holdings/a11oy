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
    PAYLOAD_TYPE,
    RECEIPT_SUBJECT_SCHEMA,
    SUBJECT_NAME,
    load_validated_snapshot,
    receipt_subject,
)
from szl_formulas import verify_dsse_real  # noqa: E402


OIDC_ISSUER = "https://token.actions.githubusercontent.com"


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
    return bundled


def _decode_statement(envelope: dict) -> dict:
    bundled = _verified_dsse_envelope(envelope)
    try:
        statement = json.loads(base64.b64decode(bundled["payload"], validate=True))
    except (KeyError, ValueError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("envelope does not contain a valid in-toto statement") from exc
    if not isinstance(statement, dict):
        raise ValueError("in-toto statement must be a JSON object")
    return statement


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
        envelope = json.loads(Path(args.envelope).read_text(encoding="utf-8"))
        if envelope.get("_mode") != "SIGSTORE-KEYLESS":
            raise ValueError("receipt is not a real Sigstore keyless envelope")
        result = verify_dsse_real(
            envelope,
            identity=args.identity,
            issuer=args.issuer,
        )
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
    print(f"[lathe-verify] rekor_log_index={result.get('rekor_log_index')}")
    print(f"[lathe-verify] identity={args.identity}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
