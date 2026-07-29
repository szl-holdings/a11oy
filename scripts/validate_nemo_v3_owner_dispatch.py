#!/usr/bin/env python3
"""Fail-closed admission for one owner-authorized Nemo v3 GPU dispatch.

The repository-dispatch payload selects only immutable identifiers and hashes.
The signed bridge envelope remains the authority for the training contract.
Nothing in this module dispatches work, fetches a mutable ref, or weakens the
existing create-new replay barriers.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import os
import pathlib
import re
import stat
import sys
from dataclasses import asdict, dataclass
from typing import Any


DISPATCH_CONTRACT_VERSION = "szl-nemo-owner-dispatch.v2"
WORKFLOW_VERSION = "nemo-v3-owner-dispatch.v2"
WORKFLOW_RELATIVE_PATH = (
    ".github/workflows/nemo-v3-isolated-owner-dispatch.yml"
)
WORKFLOW_IDENTITY = (
    "szl-holdings/a11oy/"
    ".github/workflows/nemo-v3-isolated-owner-dispatch.yml"
    "@refs/heads/main"
)
NEMO_V3_PAYLOAD_TYPE = (
    "application/vnd.szl.gpu-bridge.nemo-v3.jobspec.v1+json"
)
TRAINING_IMAGE = (
    "unsloth/unsloth@"
    "sha256:9cc97606fc386b4b13455285eb7bd2668f51530988a9c2578707fe6cdfc46123"
)
RECEIPTS_REPOSITORY = "SZLHOLDINGS/szl-training-receipts"
QUARANTINED_JOB_ID = "job-2026-nemo-v3-governed-attempt-1"
QUARANTINED_BRIDGE_REVISION = "38ba3100b2e20075b6ac0c3e62745c0f811de370"

# This is the public Ed25519 owner-engine key already pinned by the bridge.
OWNER_KEY_ID = "5c6cf59741ade920"
OWNER_PUBLIC_KEY_SPKI_BASE64 = (
    "MCowBQYDK2VwAyEArBOmZZSDK+n7Qq1HJYbqNuX9YymnsRWbzSGHHnhsERM="
)
ED25519_SPKI_PREFIX = bytes.fromhex("302a300506032b6570032100")

_FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_NEW_JOB_ID = re.compile(
    r"^job-[0-9]{4}-nemo-v3-governed-attempt-"
    r"(?:[2-9]|[1-9][0-9]+)$"
)
_POSITIVE_INTEGER = re.compile(r"^[1-9][0-9]*$")

_DISPATCH_FIELDS = {
    "contractVersion",
    "jobId",
    "bridgeRevision",
    "envelopeSha256",
    "payloadSha256",
    "sourceRevision",
    "workflowIdentity",
    "workflowBlob",
    "workflowVersion",
    "trainingImage",
    "candidateUpload",
    "modelCardUpload",
    "datasetUpload",
    "receiptsRepoId",
}
_OWNER_BINDING_FIELDS = {
    "workflowIdentity",
    "workflowBlob",
    "workflowVersion",
    "trainingImage",
    "candidateUpload",
    "modelCardUpload",
    "datasetUpload",
    "receiptsRepoId",
}
_ENVELOPE_FIELDS = {
    "payloadType",
    "payload",
    "signatures",
    "publicKeySpkiBase64",
}
_SIGNATURE_FIELDS = {"keyid", "sig"}
_SOURCE_FIELDS = {"repoId", "revision", "licenseId"}
_OUTPUT_FIELDS = {
    "candidateId",
    "private",
    "publishCandidate",
    "receiptsRepoId",
}


class DispatchValidationError(ValueError):
    """An owner dispatch or signed envelope failed closed."""


@dataclass(frozen=True)
class DispatchSelection:
    contract_version: str
    job_id: str
    bridge_revision: str
    envelope_sha256: str
    payload_sha256: str
    source_revision: str
    workflow_identity: str
    workflow_blob: str
    workflow_version: str
    training_image: str
    receipts_repo_id: str


@dataclass(frozen=True)
class EnvelopeEvidence:
    job_id: str
    bridge_revision: str
    source_revision: str
    envelope_sha256: str
    payload_sha256: str
    owner_key_id: str
    workflow_identity: str
    workflow_blob: str
    workflow_version: str


def _pairs_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise DispatchValidationError(f"duplicate JSON field: {key}")
        value[key] = item
    return value


def _reject_nonfinite(value: str) -> None:
    raise DispatchValidationError(f"non-finite JSON number is forbidden: {value}")


def strict_json_loads(raw: str | bytes, field: str) -> Any:
    if isinstance(raw, bytes):
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise DispatchValidationError(
                f"{field} is not exact UTF-8 JSON"
            ) from exc
    else:
        text = raw
    try:
        return json.loads(
            text,
            object_pairs_hook=_pairs_without_duplicates,
            parse_constant=_reject_nonfinite,
        )
    except DispatchValidationError:
        raise
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise DispatchValidationError(f"{field} is not valid JSON") from exc


def _exact_object(
    value: Any,
    *,
    field: str,
    required: set[str],
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise DispatchValidationError(f"{field} must be an object")
    missing = required - value.keys()
    extra = value.keys() - required
    if missing:
        raise DispatchValidationError(
            f"{field} missing required fields: {sorted(missing)}"
        )
    if extra:
        raise DispatchValidationError(
            f"{field} contains unsupported fields: {sorted(extra)}"
        )
    return value


def _string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise DispatchValidationError(f"{field} must be a non-empty string")
    return value


def _full_sha(value: Any, field: str) -> str:
    if not isinstance(value, str) or _FULL_SHA.fullmatch(value) is None:
        raise DispatchValidationError(
            f"{field} must be an immutable full lowercase Git SHA"
        )
    return value


def _sha256(value: Any, field: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise DispatchValidationError(
            f"{field} must be lowercase SHA-256 hex"
        )
    return value


def _must_be_false(value: Any, field: str) -> None:
    if value is not False:
        raise DispatchValidationError(f"{field} must remain false")


def git_blob_sha(path: pathlib.Path) -> str:
    data = path.read_bytes()
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data, usedforsecurity=False).hexdigest()


def validate_dispatch(
    payload: Any,
    *,
    github_sha: str,
    workflow_path: pathlib.Path,
    workflow_blob: str | None = None,
) -> DispatchSelection:
    dispatch = _exact_object(
        payload,
        field="client_payload",
        required=_DISPATCH_FIELDS,
    )
    source_revision = _full_sha(
        dispatch["sourceRevision"], "client_payload.sourceRevision"
    )
    expected_source = _full_sha(github_sha, "github.sha")
    if source_revision != expected_source:
        raise DispatchValidationError(
            "client_payload source revision does not equal github.sha"
        )

    job_id = _string(dispatch["jobId"], "client_payload.jobId")
    if _NEW_JOB_ID.fullmatch(job_id) is None:
        raise DispatchValidationError(
            "client_payload.jobId must identify a new governed attempt"
        )
    if job_id == QUARANTINED_JOB_ID:
        raise DispatchValidationError("quarantined attempt-1 cannot be selected")

    bridge_revision = _full_sha(
        dispatch["bridgeRevision"], "client_payload.bridgeRevision"
    )
    if bridge_revision == QUARANTINED_BRIDGE_REVISION:
        raise DispatchValidationError(
            "the quarantined attempt-1 bridge revision cannot be selected"
        )

    if (
        dispatch["contractVersion"] != DISPATCH_CONTRACT_VERSION
        or dispatch["workflowVersion"] != WORKFLOW_VERSION
    ):
        raise DispatchValidationError(
            "client_payload contract or workflow version is not admitted"
        )
    if dispatch["workflowIdentity"] != WORKFLOW_IDENTITY:
        raise DispatchValidationError(
            "client_payload workflow identity is not the protected main workflow"
        )
    if not workflow_path.is_file() or workflow_path.is_symlink():
        raise DispatchValidationError(
            "protected workflow path must be a regular non-symlink file"
        )
    observed_blob = (
        git_blob_sha(workflow_path)
        if workflow_blob is None
        else _full_sha(workflow_blob, "checked-out workflow blob")
    )
    workflow_blob = _full_sha(
        dispatch["workflowBlob"], "client_payload.workflowBlob"
    )
    if workflow_blob != observed_blob:
        raise DispatchValidationError(
            "client_payload workflow blob does not match checked-out bytes"
        )
    if dispatch["trainingImage"] != TRAINING_IMAGE:
        raise DispatchValidationError(
            "client_payload training image is not the immutable approved digest"
        )
    for field in ("candidateUpload", "modelCardUpload", "datasetUpload"):
        _must_be_false(dispatch[field], f"client_payload.{field}")
    if dispatch["receiptsRepoId"] != RECEIPTS_REPOSITORY:
        raise DispatchValidationError(
            "client_payload receipt repository is not admitted"
        )

    return DispatchSelection(
        contract_version=DISPATCH_CONTRACT_VERSION,
        job_id=job_id,
        bridge_revision=bridge_revision,
        envelope_sha256=_sha256(
            dispatch["envelopeSha256"], "client_payload.envelopeSha256"
        ),
        payload_sha256=_sha256(
            dispatch["payloadSha256"], "client_payload.payloadSha256"
        ),
        source_revision=source_revision,
        workflow_identity=WORKFLOW_IDENTITY,
        workflow_blob=workflow_blob,
        workflow_version=WORKFLOW_VERSION,
        training_image=TRAINING_IMAGE,
        receipts_repo_id=RECEIPTS_REPOSITORY,
    )


def _decode_base64(value: Any, field: str) -> bytes:
    text = _string(value, field)
    try:
        return base64.b64decode(text, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise DispatchValidationError(f"{field} is not strict base64") from exc


def dsse_pae(payload_type: str, payload: bytes) -> bytes:
    encoded_type = payload_type.encode("utf-8")
    return b"DSSEv1 %d %s %d %s" % (
        len(encoded_type),
        encoded_type,
        len(payload),
        payload,
    )


def _verify_ed25519(
    public_key: bytes,
    message: bytes,
    signature: bytes,
) -> None:
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PublicKey,
        )

        try:
            Ed25519PublicKey.from_public_bytes(public_key).verify(
                signature, message
            )
        except InvalidSignature as exc:
            raise DispatchValidationError(
                "owner DSSE signature verification failed"
            ) from exc
        return
    except ImportError:
        pass

    try:
        from nacl.exceptions import BadSignatureError
        from nacl.signing import VerifyKey
    except ImportError as exc:
        raise DispatchValidationError(
            "no approved Ed25519 verifier is installed"
        ) from exc
    try:
        VerifyKey(public_key).verify(message, signature)
    except BadSignatureError as exc:
        raise DispatchValidationError(
            "owner DSSE signature verification failed"
        ) from exc


def _envelope_path(
    bridge_source: pathlib.Path,
    job_id: str,
) -> pathlib.Path:
    source = bridge_source.resolve(strict=True)
    pending = (source / "queue" / "pending").resolve(strict=True)
    try:
        pending.relative_to(source)
    except ValueError as exc:
        raise DispatchValidationError(
            "bridge pending queue escapes the exact checkout"
        ) from exc
    candidate = pending / f"{job_id}.json"
    if candidate.parent != pending:
        raise DispatchValidationError(
            "envelope path is not controlled by the validated job ID"
        )
    try:
        mode = candidate.lstat().st_mode
    except FileNotFoundError as exc:
        raise DispatchValidationError(
            "selected signed envelope is absent from the exact bridge revision"
        ) from exc
    if not stat.S_ISREG(mode) or candidate.is_symlink():
        raise DispatchValidationError(
            "selected signed envelope must be a regular non-symlink file"
        )
    return candidate


def verify_owner_envelope(
    selection: DispatchSelection,
    *,
    bridge_source: pathlib.Path,
    owner_key_id: str = OWNER_KEY_ID,
    owner_spki_base64: str = OWNER_PUBLIC_KEY_SPKI_BASE64,
) -> EnvelopeEvidence:
    envelope_path = _envelope_path(bridge_source, selection.job_id)
    envelope_bytes = envelope_path.read_bytes()
    observed_envelope_hash = hashlib.sha256(envelope_bytes).hexdigest()
    if observed_envelope_hash != selection.envelope_sha256:
        raise DispatchValidationError(
            "selected envelope bytes do not match client_payload envelopeSha256"
        )

    envelope = _exact_object(
        strict_json_loads(envelope_bytes, "signed envelope"),
        field="signed envelope",
        required=_ENVELOPE_FIELDS,
    )
    if envelope["payloadType"] != NEMO_V3_PAYLOAD_TYPE:
        raise DispatchValidationError("signed envelope payloadType is not admitted")

    expected_spki = _decode_base64(owner_spki_base64, "pinned owner SPKI")
    observed_spki = _decode_base64(
        envelope["publicKeySpkiBase64"], "envelope.publicKeySpkiBase64"
    )
    if observed_spki != expected_spki:
        raise DispatchValidationError(
            "signed envelope public key is not the pinned owner key"
        )
    if (
        len(observed_spki) != len(ED25519_SPKI_PREFIX) + 32
        or not observed_spki.startswith(ED25519_SPKI_PREFIX)
    ):
        raise DispatchValidationError("owner key is not exact Ed25519 SPKI")
    derived_key_id = hashlib.sha256(observed_spki).hexdigest()[:16]
    if derived_key_id != owner_key_id:
        raise DispatchValidationError(
            "pinned owner key ID does not bind the pinned owner SPKI"
        )

    signatures = envelope["signatures"]
    if not isinstance(signatures, list) or len(signatures) != 1:
        raise DispatchValidationError(
            "signed envelope must contain exactly one owner signature"
        )
    signature_row = _exact_object(
        signatures[0],
        field="signed envelope signature",
        required=_SIGNATURE_FIELDS,
    )
    if signature_row["keyid"] != owner_key_id:
        raise DispatchValidationError(
            "signed envelope key ID is not the pinned owner key"
        )

    payload_bytes = _decode_base64(envelope["payload"], "envelope.payload")
    observed_payload_hash = hashlib.sha256(payload_bytes).hexdigest()
    if observed_payload_hash != selection.payload_sha256:
        raise DispatchValidationError(
            "signed payload bytes do not match client_payload payloadSha256"
        )
    signature = _decode_base64(signature_row["sig"], "envelope.signatures[0].sig")
    _verify_ed25519(
        observed_spki[-32:],
        dsse_pae(envelope["payloadType"], payload_bytes),
        signature,
    )

    spec = strict_json_loads(payload_bytes, "signed owner payload")
    if not isinstance(spec, dict):
        raise DispatchValidationError("signed owner payload must be an object")
    if spec.get("jobId") != selection.job_id:
        raise DispatchValidationError(
            "signed owner payload does not bind the selected job ID"
        )

    source = _exact_object(
        spec.get("source"),
        field="signed payload source",
        required=_SOURCE_FIELDS,
    )
    if (
        source["repoId"] != "szl-holdings/a11oy"
        or source["licenseId"].lower() != "apache-2.0"
        or source["revision"] != selection.source_revision
    ):
        raise DispatchValidationError(
            "signed envelope source revision does not equal github.sha"
        )

    outputs = _exact_object(
        spec.get("outputs"),
        field="signed payload outputs",
        required=_OUTPUT_FIELDS,
    )
    if (
        outputs["private"] is not True
        or outputs["publishCandidate"] is not False
    ):
        raise DispatchValidationError(
            "signed payload candidate publication boundary is not admitted"
        )
    if outputs["receiptsRepoId"] != selection.receipts_repo_id:
        raise DispatchValidationError(
            "signed payload receipt repository is not admitted"
        )

    owner_binding = _exact_object(
        spec.get("ownerDispatch"),
        field="signed payload ownerDispatch",
        required=_OWNER_BINDING_FIELDS,
    )
    expected_binding = {
        "workflowIdentity": selection.workflow_identity,
        "workflowBlob": selection.workflow_blob,
        "workflowVersion": selection.workflow_version,
        "trainingImage": selection.training_image,
        "candidateUpload": False,
        "modelCardUpload": False,
        "datasetUpload": False,
        "receiptsRepoId": selection.receipts_repo_id,
    }
    if owner_binding != expected_binding:
        raise DispatchValidationError(
            "signed payload does not bind the protected workflow and output boundary"
        )

    lineage = spec.get("lineage")
    if not isinstance(lineage, dict):
        raise DispatchValidationError(
            "signed successor payload must carry predecessor lineage"
        )
    if (
        lineage.get("predecessorJobId") != QUARANTINED_JOB_ID
        or lineage.get("automaticRetry") is not False
    ):
        raise DispatchValidationError(
            "signed successor lineage does not bind the retired attempt"
        )

    return EnvelopeEvidence(
        job_id=selection.job_id,
        bridge_revision=selection.bridge_revision,
        source_revision=selection.source_revision,
        envelope_sha256=observed_envelope_hash,
        payload_sha256=observed_payload_hash,
        owner_key_id=owner_key_id,
        workflow_identity=selection.workflow_identity,
        workflow_blob=selection.workflow_blob,
        workflow_version=selection.workflow_version,
    )


def write_github_env(
    selection: DispatchSelection,
    destination: pathlib.Path,
) -> None:
    values = {
        "JOB_ID": selection.job_id,
        "BRIDGE_REVISION": selection.bridge_revision,
        "EXPECTED_ENVELOPE_SHA256": selection.envelope_sha256,
        "EXPECTED_PAYLOAD_SHA256": selection.payload_sha256,
        "EXPECTED_WORKFLOW_BLOB": selection.workflow_blob,
    }
    for key, value in values.items():
        if "\r" in value or "\n" in value:
            raise DispatchValidationError(
                f"validated environment value contains a newline: {key}"
            )
    with destination.open("a", encoding="utf-8", newline="\n") as handle:
        for key, value in values.items():
            handle.write(f"{key}={value}\n")


def create_new_claim(
    selection: DispatchSelection,
    evidence: EnvelopeEvidence,
    *,
    bridge_root: pathlib.Path,
    run_id: str,
    run_attempt: str,
) -> pathlib.Path:
    if _POSITIVE_INTEGER.fullmatch(run_id) is None:
        raise DispatchValidationError("run ID must be a positive integer")
    if _POSITIVE_INTEGER.fullmatch(run_attempt) is None:
        raise DispatchValidationError("run attempt must be a positive integer")

    control_root = bridge_root / "control"
    control_root.mkdir(parents=True, exist_ok=True)
    claim_path = control_root / f"{selection.job_id}-attempt.claim.json"
    claim = {
        "bridgeRevision": selection.bridge_revision,
        "dispatchedRevision": selection.source_revision,
        "envelopeSha256": evidence.envelope_sha256,
        "jobId": selection.job_id,
        "payloadSha256": evidence.payload_sha256,
        "runAttempt": run_attempt,
        "runId": run_id,
        "workflowBlob": selection.workflow_blob,
        "workflowIdentity": selection.workflow_identity,
        "workflowVersion": selection.workflow_version,
    }
    claim_bytes = (
        json.dumps(
            claim,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        + "\n"
    ).encode("utf-8")

    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    try:
        descriptor = os.open(claim_path, flags, 0o600)
    except FileExistsError as exc:
        raise DispatchValidationError(
            "the selected governed attempt was already claimed"
        ) from exc
    try:
        offset = 0
        while offset < len(claim_bytes):
            written = os.write(descriptor, claim_bytes[offset:])
            if written <= 0:
                raise OSError("claim write made no forward progress")
            offset += written
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return claim_path


def _selection_from_args(args: argparse.Namespace) -> DispatchSelection:
    raw = os.environ.get(args.dispatch_json_env)
    if raw is None:
        raise DispatchValidationError(
            f"required dispatch JSON environment is missing: {args.dispatch_json_env}"
        )
    payload = strict_json_loads(raw, "repository_dispatch client_payload")
    return validate_dispatch(
        payload,
        github_sha=args.github_sha,
        workflow_path=args.workflow_path,
        workflow_blob=args.workflow_blob,
    )


def _add_selection_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--dispatch-json-env", required=True)
    parser.add_argument("--github-sha", required=True)
    parser.add_argument("--workflow-path", type=pathlib.Path, required=True)
    parser.add_argument("--workflow-blob", required=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    select = subparsers.add_parser("select")
    _add_selection_arguments(select)
    select.add_argument("--github-env", type=pathlib.Path, required=True)

    verify = subparsers.add_parser("verify-envelope")
    _add_selection_arguments(verify)
    verify.add_argument("--bridge-source", type=pathlib.Path, required=True)

    claim = subparsers.add_parser("create-claim")
    _add_selection_arguments(claim)
    claim.add_argument("--bridge-source", type=pathlib.Path, required=True)
    claim.add_argument("--bridge-root", type=pathlib.Path, required=True)
    claim.add_argument("--run-id", required=True)
    claim.add_argument("--run-attempt", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        selection = _selection_from_args(args)
        if args.command == "select":
            write_github_env(selection, args.github_env)
            report: dict[str, Any] = {"selection": asdict(selection)}
        else:
            evidence = verify_owner_envelope(
                selection,
                bridge_source=args.bridge_source,
            )
            report = {"selection": asdict(selection), "evidence": asdict(evidence)}
            if args.command == "create-claim":
                claim_path = create_new_claim(
                    selection,
                    evidence,
                    bridge_root=args.bridge_root,
                    run_id=args.run_id,
                    run_attempt=args.run_attempt,
                )
                report["claim"] = {
                    "created": True,
                    "name": claim_path.name,
                }
        print(json.dumps(report, sort_keys=True))
        return 0
    except (DispatchValidationError, OSError) as exc:
        print(f"owner dispatch rejected: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
