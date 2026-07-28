#!/usr/bin/env python3
"""Verify one fresh owner-GPU receipt and its immutable Hub readback."""

import argparse
import base64
import hashlib
import json
import os
import pathlib
from datetime import datetime, timezone
from typing import Any


ALLOWED_FILES = {
    "blocked_receipt.signed.json",
    "nemo-v3-qualified.signed.json",
    "nemo-v3-terminal.signed.json",
}
ALLOWED_NEMO_STATES = {
    "EVALUATION_FAILED_NOT_PROMOTED_NOT_SIGNED",
    "QUALIFIED_FOR_SEPARATE_PROMOTION_REVIEW",
}


class VerificationError(ValueError):
    """A receipt failed a fail-closed verification check."""


def canonicalize(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def parse_timestamp(value: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise VerificationError("receipt timestamp is missing")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise VerificationError("receipt timestamp is invalid") from exc
    if parsed.tzinfo is None:
        raise VerificationError("receipt timestamp has no timezone")
    return parsed.astimezone(timezone.utc)


def decode_base64(value: Any, label: str) -> bytes:
    if not isinstance(value, str) or not value:
        raise VerificationError(f"{label} is missing")
    try:
        return base64.b64decode(value, validate=True)
    except (ValueError, TypeError) as exc:
        raise VerificationError(f"{label} is not valid base64") from exc


def verify_local_receipt(
    receipt_path: pathlib.Path,
    expected_key_path: pathlib.Path,
    job_id: str,
    since: datetime,
) -> dict[str, Any]:
    from nacl.exceptions import BadSignatureError
    from nacl.signing import VerifyKey

    try:
        signed = json.loads(receipt_path.read_text(encoding="utf-8-sig"))
        expected_key = json.loads(expected_key_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise VerificationError("receipt or expected key is unreadable") from exc

    if signed.get("scheme") != "ed25519-over-exact-bytes-v2":
        raise VerificationError("receipt signature scheme is not admitted")

    spki = decode_base64(signed.get("publicKeySpkiBase64"), "public key")
    expected_spki = decode_base64(
        expected_key.get("publicKeySpkiBase64"), "expected public key"
    )
    expected_key_id = hashlib.sha256(expected_spki).hexdigest()[:16]
    if (
        spki != expected_spki
        or signed.get("keyId") != expected_key.get("keyId")
        or expected_key.get("keyId") != expected_key_id
    ):
        raise VerificationError("receipt key does not match the enrolled owner key")

    body = decode_base64(signed.get("bodyBase64"), "receipt body")
    signature = decode_base64(signed.get("signatureBase64"), "receipt signature")
    try:
        VerifyKey(spki[-32:]).verify(body, signature)
    except BadSignatureError as exc:
        raise VerificationError("receipt signature is invalid") from exc

    receipt = signed.get("receipt")
    if not isinstance(receipt, dict) or body != canonicalize(receipt):
        raise VerificationError("signed body and receipt object are not byte-identical")
    try:
        decoded_body = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VerificationError("signed receipt body is not canonical JSON") from exc
    if decoded_body != receipt or receipt.get("jobId") != job_id:
        raise VerificationError("receipt body does not bind the expected job")

    observed_at = parse_timestamp(receipt.get("at"))
    if observed_at < since:
        raise VerificationError("receipt predates this dispatch invocation")

    kind = receipt.get("kind")
    if kind == "szl-frontier-training-blocked":
        if receipt.get("verdict") != "BLOCKED":
            raise VerificationError("blocked receipt has no BLOCKED verdict")
        state = "BLOCKED"
    elif kind == "szl-nemo-v3-governed-training":
        state = receipt.get("state")
        if state not in ALLOWED_NEMO_STATES:
            raise VerificationError("Nemo receipt is not in an admitted terminal state")
    else:
        raise VerificationError("receipt kind is not admitted for Nemo v3")

    return {
        "jobId": job_id,
        "state": state,
        "keyId": expected_key_id,
        "observedAt": observed_at.isoformat().replace("+00:00", "Z"),
    }


def immutable_readback(
    receipt_path: pathlib.Path, repo_id: str, job_id: str, token: str
) -> dict[str, str]:
    from huggingface_hub import HfApi, hf_hub_download

    if not token:
        raise VerificationError("HF_TOKEN is missing")
    api = HfApi(token=token)
    revision = api.repo_info(repo_id, repo_type="dataset").sha
    if not revision:
        raise VerificationError("receipt dataset returned no immutable revision")
    remote_path = f"{job_id}/{receipt_path.name}"
    downloaded = pathlib.Path(
        hf_hub_download(
            repo_id=repo_id,
            filename=remote_path,
            repo_type="dataset",
            revision=revision,
            token=token,
            force_download=True,
        )
    )
    local_bytes = receipt_path.read_bytes()
    remote_bytes = downloaded.read_bytes()
    if local_bytes != remote_bytes:
        raise VerificationError("immutable Hub readback differs from the local receipt")
    return {
        "receiptRevision": revision,
        "receiptSha256": hashlib.sha256(local_bytes).hexdigest(),
        "receiptPath": remote_path,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt-dir", type=pathlib.Path, required=True)
    parser.add_argument("--expected-key", type=pathlib.Path, required=True)
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--since", required=True)
    parser.add_argument("--repo-id", required=True)
    args = parser.parse_args()

    since = parse_timestamp(args.since)
    candidates = [
        path
        for path in args.receipt_dir.glob("*.signed.json")
        if path.name in ALLOWED_FILES
        and datetime.fromtimestamp(path.stat().st_mtime, timezone.utc) >= since
    ]
    if len(candidates) != 1:
        raise VerificationError(
            f"expected one fresh terminal receipt, found {len(candidates)}"
        )

    verified = verify_local_receipt(
        candidates[0], args.expected_key, args.job_id, since
    )
    verified.update(
        immutable_readback(
            candidates[0],
            args.repo_id,
            args.job_id,
            os.environ.get("HF_TOKEN", ""),
        )
    )
    verified["verdict"] = "VERIFIED_FRESH_IMMUTABLE_SIGNED_RECEIPT"
    print(json.dumps(verified, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
