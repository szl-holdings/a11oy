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
import subprocess
import sys
from dataclasses import asdict, dataclass
from typing import Any


DISPATCH_CONTRACT_VERSION = "szl-nemo-owner-dispatch.v3"
WORKFLOW_VERSION = "nemo-v3-owner-dispatch.v4"
GITHUB_CLIENT_PAYLOAD_PROPERTY_LIMIT = 10
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
BRIDGE_REPOSITORY_URL = (
    "https://github.com/szl-holdings/szl-gpu-bridge.git"
)
QUARANTINED_JOB_IDS = {
    "job-2026-nemo-v3-governed-attempt-1",
    "job-2026-nemo-v3-governed-attempt-2",
    "job-2026-nemo-v3-governed-attempt-4",
    "job-2026-nemo-v3-governed-attempt-5",
    "job-2026-nemo-v3-governed-attempt-6",
}
QUARANTINED_BRIDGE_REVISIONS = {
    "38ba3100b2e20075b6ac0c3e62745c0f811de370",
    "2237bb3f36663343ace29d98cda6c32e165450a0",
    "7045fe223703ba8fb2d710a59989f971080e7702",
}

# This is the active public Ed25519 owner-engine key. Its private key remains
# outside the repository under the owner-controlled offline credential
# boundary. The prior key is intentionally not admitted for new dispatches
# after its signing material became unavailable; historical verification is a
# bridge-ledger concern.
OWNER_KEY_ID = "b8041281c81c4caa"
OWNER_PUBLIC_KEY_SPKI_BASE64 = (
    "MCowBQYDK2VwAyEAstuDm9wVQ7BrOuBRmIyEHsOtyOutChFfRvCDenCDB6c="
)
ED25519_SPKI_PREFIX = bytes.fromhex("302a300506032b6570032100")

_FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_NEW_JOB_ID = re.compile(
    r"^job-[0-9]{4}-nemo-v3-governed-attempt-"
    r"(?P<generation>[2-9]|[1-9][0-9]+)$"
)
_POSITIVE_INTEGER = re.compile(r"^[1-9][0-9]*$")
_SETTLED_RELOCK_URL = re.compile(
    r"^https://github\.com/szl-holdings/a11oy/actions/runs/[1-9][0-9]*$"
)

_CLIENT_PAYLOAD_FIELDS = {"selection"}
_SELECTION_FIELDS = {
    "contractVersion",
    "jobId",
    "envelopeRevision",
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
_AUTHORIZATION_FIELDS = {
    "coordinationMode",
    "correctedBridgeRevision",
    "cryptographicContinuityClaimed",
    "decisionAt",
    "engineKeyId",
    "enginePublicKeySpkiSha256",
    "oldKeyStatus",
    "previousEngineKeyId",
    "provisionalEngineKeyId",
    "provisionalKeyStatus",
    "recoveryIssueUrl",
    "rotationMode",
    "settledA11oyRelockRunUrl",
}
_LINEAGE_FIELDS = {
    "automaticRetry",
    "candidateProduced",
    "claimCreated",
    "eventCreated",
    "failurePhase",
    "holdoutsAccessed",
    "modelRepositoryCodeImported",
    "predecessorEnvelopeRevision",
    "predecessorEnvelopeSha256",
    "predecessorExecutionBridgeRevision",
    "predecessorJobId",
    "predecessorPayloadSha256",
    "receiptIntentProduced",
    "scienceInputsReused",
    "successorGeneration",
    "terminalLedgerWritten",
    "trainingStarted",
    "transportEvidenceUrl",
    "workflowRunCreated",
}
_LINEAGE_BOOLEAN_FIELDS = {
    "automaticRetry",
    "candidateProduced",
    "claimCreated",
    "eventCreated",
    "holdoutsAccessed",
    "modelRepositoryCodeImported",
    "receiptIntentProduced",
    "scienceInputsReused",
    "terminalLedgerWritten",
    "trainingStarted",
    "workflowRunCreated",
}
_QUARANTINE_FIELDS = {
    "dispatchAuthorized",
    "engineKeyId",
    "jobId",
    "kind",
    "preserveEnvelope",
    "queueFileSha256",
    "queuePath",
    "reason",
    "recordedAt",
    "replacement",
    "signedPayloadSha256",
    "sourceRevision",
    "status",
    "v",
}
_QUARANTINE_REPLACEMENT_FIELDS = {
    "engineKeyId",
    "enginePublicKeySpkiSha256",
    "reviewedJobId",
    "settledA11oyRelockRunUrl",
    "sourceRevision",
    "successorGeneration",
    "workflowBlob",
    "workflowVersion",
}


class DispatchValidationError(ValueError):
    """An owner dispatch or signed envelope failed closed."""


@dataclass(frozen=True)
class DispatchSelection:
    contract_version: str
    job_id: str
    envelope_revision: str
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
    envelope_revision: str
    execution_bridge_revision: str
    source_revision: str
    envelope_sha256: str
    payload_sha256: str
    owner_key_id: str
    engine_key_id: str
    engine_public_key_spki_sha256: str
    envelope_path: str
    workflow_identity: str
    workflow_blob: str
    workflow_version: str
    predecessor_job_id: str
    predecessor_envelope_revision: str
    predecessor_execution_bridge_revision: str
    predecessor_envelope_sha256: str
    predecessor_payload_sha256: str
    predecessor_queue_path: str


@dataclass(frozen=True)
class PredecessorEvidence:
    job_id: str
    envelope_revision: str
    execution_bridge_revision: str
    envelope_sha256: str
    payload_sha256: str
    queue_path: str


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


def _attempt_generation(value: Any, field: str) -> int:
    job_id = _string(value, field)
    match = _NEW_JOB_ID.fullmatch(job_id)
    if match is None:
        raise DispatchValidationError(
            f"{field} must identify a governed attempt"
        )
    return int(match.group("generation"))


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
    if (
        isinstance(payload, dict)
        and len(payload) > GITHUB_CLIENT_PAYLOAD_PROPERTY_LIMIT
    ):
        raise DispatchValidationError(
            "client_payload exceeds GitHub's repository-dispatch property limit"
        )
    client_payload = _exact_object(
        payload,
        field="client_payload",
        required=_CLIENT_PAYLOAD_FIELDS,
    )
    dispatch = _exact_object(
        client_payload["selection"],
        field="client_payload.selection",
        required=_SELECTION_FIELDS,
    )
    source_revision = _full_sha(
        dispatch["sourceRevision"], "client_payload.selection.sourceRevision"
    )
    expected_source = _full_sha(github_sha, "github.sha")
    if source_revision != expected_source:
        raise DispatchValidationError(
            "client_payload.selection source revision does not equal github.sha"
        )

    job_id = _string(
        dispatch["jobId"], "client_payload.selection.jobId"
    )
    if job_id in QUARANTINED_JOB_IDS:
        raise DispatchValidationError(
            "quarantined or stale governed attempt cannot be selected"
        )
    if _NEW_JOB_ID.fullmatch(job_id) is None:
        raise DispatchValidationError(
            "client_payload.selection.jobId must identify a new governed attempt"
        )

    envelope_revision = _full_sha(
        dispatch["envelopeRevision"],
        "client_payload.selection.envelopeRevision",
    )
    if envelope_revision in QUARANTINED_BRIDGE_REVISIONS:
        raise DispatchValidationError(
            "a quarantined Bridge revision cannot publish the selected envelope"
        )

    if (
        dispatch["contractVersion"] != DISPATCH_CONTRACT_VERSION
        or dispatch["workflowVersion"] != WORKFLOW_VERSION
    ):
        raise DispatchValidationError(
            "client_payload.selection contract or workflow version is not admitted"
        )
    if dispatch["workflowIdentity"] != WORKFLOW_IDENTITY:
        raise DispatchValidationError(
            "client_payload.selection workflow identity is not the protected main workflow"
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
        dispatch["workflowBlob"], "client_payload.selection.workflowBlob"
    )
    if workflow_blob != observed_blob:
        raise DispatchValidationError(
            "client_payload.selection workflow blob does not match checked-out bytes"
        )
    if dispatch["trainingImage"] != TRAINING_IMAGE:
        raise DispatchValidationError(
            "client_payload.selection training image is not the immutable approved digest"
        )
    for field in ("candidateUpload", "modelCardUpload", "datasetUpload"):
        _must_be_false(
            dispatch[field], f"client_payload.selection.{field}"
        )
    if dispatch["receiptsRepoId"] != RECEIPTS_REPOSITORY:
        raise DispatchValidationError(
            "client_payload.selection receipt repository is not admitted"
        )

    return DispatchSelection(
        contract_version=DISPATCH_CONTRACT_VERSION,
        job_id=job_id,
        envelope_revision=envelope_revision,
        envelope_sha256=_sha256(
            dispatch["envelopeSha256"],
            "client_payload.selection.envelopeSha256",
        ),
        payload_sha256=_sha256(
            dispatch["payloadSha256"],
            "client_payload.selection.payloadSha256",
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


def _quarantine_path(
    bridge_source: pathlib.Path,
    job_id: str,
    *,
    required: bool,
) -> pathlib.Path | None:
    source = bridge_source.resolve(strict=True)
    quarantine = (source / "queue" / "quarantine").resolve(strict=True)
    try:
        quarantine.relative_to(source)
    except ValueError as exc:
        raise DispatchValidationError(
            "bridge quarantine directory escapes the exact checkout"
        ) from exc
    candidate = quarantine / f"{job_id}.json"
    if candidate.parent != quarantine:
        raise DispatchValidationError(
            "quarantine path is not controlled by the validated job ID"
        )
    try:
        mode = candidate.lstat().st_mode
    except FileNotFoundError as exc:
        if not required:
            return None
        raise DispatchValidationError(
            "signed predecessor has no immutable quarantine record"
        ) from exc
    if not stat.S_ISREG(mode) or candidate.is_symlink():
        raise DispatchValidationError(
            "quarantine record must be a regular non-symlink file"
        )
    return candidate


def _verify_predecessor_envelope(
    *,
    bridge_source: pathlib.Path,
    job_id: str,
    expected_envelope_sha256: str,
    expected_payload_sha256: str,
    expected_execution_revision: str,
    expected_source_revision: str,
    owner_key_id: str,
    owner_spki: bytes,
) -> None:
    predecessor_path = _envelope_path(bridge_source, job_id)
    envelope_bytes = predecessor_path.read_bytes()
    if hashlib.sha256(envelope_bytes).hexdigest() != expected_envelope_sha256:
        raise DispatchValidationError(
            "quarantined predecessor envelope bytes do not match lineage"
        )
    envelope = _exact_object(
        strict_json_loads(envelope_bytes, "quarantined predecessor envelope"),
        field="quarantined predecessor envelope",
        required=_ENVELOPE_FIELDS,
    )
    if envelope["payloadType"] != NEMO_V3_PAYLOAD_TYPE:
        raise DispatchValidationError(
            "quarantined predecessor payloadType is not admitted"
        )
    observed_spki = _decode_base64(
        envelope["publicKeySpkiBase64"],
        "quarantined predecessor publicKeySpkiBase64",
    )
    if observed_spki != owner_spki:
        raise DispatchValidationError(
            "quarantined predecessor was not signed by the verified owner key"
        )
    signatures = envelope["signatures"]
    if not isinstance(signatures, list) or len(signatures) != 1:
        raise DispatchValidationError(
            "quarantined predecessor must contain exactly one owner signature"
        )
    signature_row = _exact_object(
        signatures[0],
        field="quarantined predecessor signature",
        required=_SIGNATURE_FIELDS,
    )
    if signature_row["keyid"] != owner_key_id:
        raise DispatchValidationError(
            "quarantined predecessor key ID is not the verified owner key"
        )
    payload_bytes = _decode_base64(
        envelope["payload"],
        "quarantined predecessor payload",
    )
    if hashlib.sha256(payload_bytes).hexdigest() != expected_payload_sha256:
        raise DispatchValidationError(
            "quarantined predecessor payload bytes do not match lineage"
        )
    _verify_ed25519(
        observed_spki[-32:],
        dsse_pae(envelope["payloadType"], payload_bytes),
        _decode_base64(
            signature_row["sig"],
            "quarantined predecessor signature",
        ),
    )
    spec = strict_json_loads(
        payload_bytes,
        "quarantined predecessor signed payload",
    )
    if not isinstance(spec, dict) or spec.get("jobId") != job_id:
        raise DispatchValidationError(
            "quarantined predecessor payload does not bind its job ID"
        )
    source = _exact_object(
        spec.get("source"),
        field="quarantined predecessor source",
        required=_SOURCE_FIELDS,
    )
    if (
        _string(
            source["repoId"],
            "quarantined predecessor source.repoId",
        )
        != "szl-holdings/a11oy"
        or _string(
            source["licenseId"],
            "quarantined predecessor source.licenseId",
        ).lower()
        != "apache-2.0"
        or source["revision"] != expected_source_revision
    ):
        raise DispatchValidationError(
            "quarantined predecessor source does not match its record"
        )
    authorization = _exact_object(
        spec.get("authorization"),
        field="quarantined predecessor authorization",
        required=_AUTHORIZATION_FIELDS,
    )
    if (
        authorization["correctedBridgeRevision"]
        != expected_execution_revision
    ):
        raise DispatchValidationError(
            "quarantined predecessor runtime revision does not match lineage"
        )
    if (
        authorization["engineKeyId"] != owner_key_id
        or authorization["enginePublicKeySpkiSha256"]
        != hashlib.sha256(owner_spki).hexdigest()
    ):
        raise DispatchValidationError(
            "quarantined predecessor engine key is not the verified owner key"
        )


def _verify_predecessor_lineage(
    selection: DispatchSelection,
    lineage_value: Any,
    *,
    envelope_source: pathlib.Path,
    owner_key_id: str,
    owner_spki: bytes,
    settled_a11oy_relock_run_url: str,
) -> PredecessorEvidence:
    lineage = _exact_object(
        lineage_value,
        field="signed payload lineage",
        required=_LINEAGE_FIELDS,
    )
    current_generation = _attempt_generation(
        selection.job_id,
        "signed payload jobId",
    )
    predecessor_job_id = _string(
        lineage["predecessorJobId"],
        "signed payload lineage.predecessorJobId",
    )
    predecessor_generation = _attempt_generation(
        predecessor_job_id,
        "signed payload lineage.predecessorJobId",
    )
    if (
        predecessor_job_id == selection.job_id
        or predecessor_generation + 1 != current_generation
    ):
        raise DispatchValidationError(
            "signed successor lineage must bind the immediately preceding attempt"
        )
    successor_generation = lineage["successorGeneration"]
    if (
        isinstance(successor_generation, bool)
        or not isinstance(successor_generation, int)
        or successor_generation != current_generation
    ):
        raise DispatchValidationError(
            "signed successor generation does not match the current attempt"
        )
    for field in _LINEAGE_BOOLEAN_FIELDS:
        if not isinstance(lineage[field], bool):
            raise DispatchValidationError(
                f"signed payload lineage.{field} must be boolean"
            )
    if (
        lineage["automaticRetry"] is not False
        or lineage["scienceInputsReused"] is not True
    ):
        raise DispatchValidationError(
            "signed successor lineage cannot retry or replace science inputs"
        )
    _string(
        lineage["failurePhase"],
        "signed payload lineage.failurePhase",
    )
    _string(
        lineage["transportEvidenceUrl"],
        "signed payload lineage.transportEvidenceUrl",
    )
    predecessor_envelope_revision = _full_sha(
        lineage["predecessorEnvelopeRevision"],
        "signed payload lineage.predecessorEnvelopeRevision",
    )
    predecessor_execution_revision = _full_sha(
        lineage["predecessorExecutionBridgeRevision"],
        "signed payload lineage.predecessorExecutionBridgeRevision",
    )
    if predecessor_envelope_revision == predecessor_execution_revision:
        raise DispatchValidationError(
            "predecessor envelope publication must remain data-only"
        )
    predecessor_envelope_sha256 = _sha256(
        lineage["predecessorEnvelopeSha256"],
        "signed payload lineage.predecessorEnvelopeSha256",
    )
    predecessor_payload_sha256 = _sha256(
        lineage["predecessorPayloadSha256"],
        "signed payload lineage.predecessorPayloadSha256",
    )

    if (
        _quarantine_path(
            envelope_source,
            selection.job_id,
            required=False,
        )
        is not None
    ):
        raise DispatchValidationError(
            "current governed attempt already has a quarantine record"
        )
    quarantine_path = _quarantine_path(
        envelope_source,
        predecessor_job_id,
        required=True,
    )
    assert quarantine_path is not None
    record = _exact_object(
        strict_json_loads(
            quarantine_path.read_bytes(),
            "predecessor quarantine record",
        ),
        field="predecessor quarantine record",
        required=_QUARANTINE_FIELDS,
    )
    statuses = record["status"]
    if (
        not isinstance(statuses, list)
        or not statuses
        or any(not isinstance(value, str) or not value for value in statuses)
        or len(set(statuses)) != len(statuses)
        or "NEVER_DISPATCH" not in statuses
    ):
        raise DispatchValidationError(
            "predecessor quarantine status must be unique and NEVER_DISPATCH"
        )
    expected_queue_path = f"queue/pending/{predecessor_job_id}.json"
    if (
        record["kind"] != "szl-nemo-v3-queue-quarantine"
        or isinstance(record["v"], bool)
        or record["v"] != 1
        or record["jobId"] != predecessor_job_id
        or record["queuePath"] != expected_queue_path
        or record["preserveEnvelope"] is not True
        or record["dispatchAuthorized"] is not False
        or record["engineKeyId"] != owner_key_id
    ):
        raise DispatchValidationError(
            "predecessor quarantine record is not immutable dispatch denial"
        )
    _string(record["recordedAt"], "predecessor quarantine recordedAt")
    _string(record["reason"], "predecessor quarantine reason")
    predecessor_source_revision = _full_sha(
        record["sourceRevision"],
        "predecessor quarantine sourceRevision",
    )
    if (
        _sha256(
            record["queueFileSha256"],
            "predecessor quarantine queueFileSha256",
        )
        != predecessor_envelope_sha256
        or _sha256(
            record["signedPayloadSha256"],
            "predecessor quarantine signedPayloadSha256",
        )
        != predecessor_payload_sha256
    ):
        raise DispatchValidationError(
            "signed predecessor hashes do not match immutable quarantine evidence"
        )
    replacement = _exact_object(
        record["replacement"],
        field="predecessor quarantine replacement",
        required=_QUARANTINE_REPLACEMENT_FIELDS,
    )
    replacement_generation = replacement["successorGeneration"]
    if (
        isinstance(replacement_generation, bool)
        or not isinstance(replacement_generation, int)
        or replacement_generation != current_generation
    ):
        raise DispatchValidationError(
            "predecessor quarantine replacement successorGeneration "
            "does not bind the immediate successor"
        )
    replacement_relock_url = _string(
        replacement["settledA11oyRelockRunUrl"],
        "predecessor quarantine replacement settledA11oyRelockRunUrl",
    )
    if _SETTLED_RELOCK_URL.fullmatch(replacement_relock_url) is None:
        raise DispatchValidationError(
            "predecessor quarantine replacement relock must be an immutable "
            "A11oy workflow run URL"
        )
    expected_spki_sha256 = hashlib.sha256(owner_spki).hexdigest()
    if replacement != {
        "sourceRevision": selection.source_revision,
        "workflowBlob": selection.workflow_blob,
        "workflowVersion": selection.workflow_version,
        "settledA11oyRelockRunUrl": settled_a11oy_relock_run_url,
        "engineKeyId": owner_key_id,
        "enginePublicKeySpkiSha256": expected_spki_sha256,
        "reviewedJobId": selection.job_id,
        "successorGeneration": current_generation,
    }:
        raise DispatchValidationError(
            "predecessor quarantine replacement does not bind this successor"
        )
    _verify_predecessor_envelope(
        bridge_source=envelope_source,
        job_id=predecessor_job_id,
        expected_envelope_sha256=predecessor_envelope_sha256,
        expected_payload_sha256=predecessor_payload_sha256,
        expected_execution_revision=predecessor_execution_revision,
        expected_source_revision=predecessor_source_revision,
        owner_key_id=owner_key_id,
        owner_spki=owner_spki,
    )
    return PredecessorEvidence(
        job_id=predecessor_job_id,
        envelope_revision=predecessor_envelope_revision,
        execution_bridge_revision=predecessor_execution_revision,
        envelope_sha256=predecessor_envelope_sha256,
        payload_sha256=predecessor_payload_sha256,
        queue_path=expected_queue_path,
    )


def verify_owner_envelope(
    selection: DispatchSelection,
    *,
    envelope_source: pathlib.Path,
    owner_key_id: str | None = None,
    owner_spki_base64: str | None = None,
) -> EnvelopeEvidence:
    if owner_key_id is None:
        owner_key_id = OWNER_KEY_ID
    if owner_spki_base64 is None:
        owner_spki_base64 = OWNER_PUBLIC_KEY_SPKI_BASE64
    envelope_path = _envelope_path(envelope_source, selection.job_id)
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

    authorization = _exact_object(
        spec.get("authorization"),
        field="signed payload authorization",
        required=_AUTHORIZATION_FIELDS,
    )
    execution_bridge_revision = _full_sha(
        authorization["correctedBridgeRevision"],
        "signed payload authorization.correctedBridgeRevision",
    )
    if execution_bridge_revision in QUARANTINED_BRIDGE_REVISIONS:
        raise DispatchValidationError(
            "signed payload selects a quarantined Bridge runtime revision"
        )
    if execution_bridge_revision == selection.envelope_revision:
        raise DispatchValidationError(
            "envelope publication revision must remain data-only"
        )
    engine_key_id = _string(
        authorization["engineKeyId"],
        "signed payload authorization.engineKeyId",
    )
    engine_spki_sha256 = _sha256(
        authorization["enginePublicKeySpkiSha256"],
        "signed payload authorization.enginePublicKeySpkiSha256",
    )
    settled_a11oy_relock_run_url = _string(
        authorization["settledA11oyRelockRunUrl"],
        "signed payload authorization.settledA11oyRelockRunUrl",
    )
    if _SETTLED_RELOCK_URL.fullmatch(settled_a11oy_relock_run_url) is None:
        raise DispatchValidationError(
            "signed payload relock must be an immutable A11oy workflow run URL"
        )
    expected_spki_sha256 = hashlib.sha256(observed_spki).hexdigest()
    if (
        engine_key_id != owner_key_id
        or engine_spki_sha256 != expected_spki_sha256
    ):
        raise DispatchValidationError(
            "signed payload engine identity does not match the verified owner key"
        )
    predecessor = _verify_predecessor_lineage(
        selection,
        lineage,
        envelope_source=envelope_source,
        owner_key_id=owner_key_id,
        owner_spki=observed_spki,
        settled_a11oy_relock_run_url=settled_a11oy_relock_run_url,
    )

    return EnvelopeEvidence(
        job_id=selection.job_id,
        envelope_revision=selection.envelope_revision,
        execution_bridge_revision=execution_bridge_revision,
        source_revision=selection.source_revision,
        envelope_sha256=observed_envelope_hash,
        payload_sha256=observed_payload_hash,
        owner_key_id=owner_key_id,
        engine_key_id=engine_key_id,
        engine_public_key_spki_sha256=engine_spki_sha256,
        envelope_path=str(envelope_path),
        workflow_identity=selection.workflow_identity,
        workflow_blob=selection.workflow_blob,
        workflow_version=selection.workflow_version,
        predecessor_job_id=predecessor.job_id,
        predecessor_envelope_revision=predecessor.envelope_revision,
        predecessor_execution_bridge_revision=(
            predecessor.execution_bridge_revision
        ),
        predecessor_envelope_sha256=predecessor.envelope_sha256,
        predecessor_payload_sha256=predecessor.payload_sha256,
        predecessor_queue_path=predecessor.queue_path,
    )


def write_github_env(
    selection: DispatchSelection,
    destination: pathlib.Path,
) -> None:
    values = {
        "JOB_ID": selection.job_id,
        "ENVELOPE_REVISION": selection.envelope_revision,
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


def write_verified_github_env(
    evidence: EnvelopeEvidence,
    destination: pathlib.Path,
) -> None:
    values = {
        "EXECUTION_BRIDGE_REVISION": evidence.execution_bridge_revision,
        "ENGINE_KEY_ID": evidence.engine_key_id,
        "VERIFIED_ENVELOPE_PATH": evidence.envelope_path,
    }
    for key, value in values.items():
        if "\r" in value or "\n" in value:
            raise DispatchValidationError(
                f"verified environment value contains a newline: {key}"
            )
    with destination.open("a", encoding="utf-8", newline="\n") as handle:
        for key, value in values.items():
            handle.write(f"{key}={value}\n")


def _git_output(
    git_executable: pathlib.Path,
    repository: pathlib.Path,
    *arguments: str,
) -> str:
    try:
        result = subprocess.run(
            [str(git_executable), "-C", str(repository), *arguments],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="strict",
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError, UnicodeError) as exc:
        raise DispatchValidationError(
            f"Bridge history verification could not run git {' '.join(arguments)}"
        ) from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()[:180]
        raise DispatchValidationError(
            f"Bridge history verification rejected git {' '.join(arguments)}: "
            f"{detail or 'nonzero exit'}"
        )
    return result.stdout.strip()


def _git_bytes(
    git_executable: pathlib.Path,
    repository: pathlib.Path,
    *arguments: str,
) -> bytes:
    try:
        result = subprocess.run(
            [str(git_executable), "-C", str(repository), *arguments],
            check=False,
            capture_output=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise DispatchValidationError(
            f"Bridge history verification could not run git {' '.join(arguments)}"
        ) from exc
    if result.returncode != 0:
        detail = result.stderr.decode(
            "utf-8",
            errors="replace",
        ).strip()[:180]
        raise DispatchValidationError(
            f"Bridge history verification rejected git {' '.join(arguments)}: "
            f"{detail or 'nonzero exit'}"
        )
    return result.stdout


def verify_bridge_history(
    selection: DispatchSelection,
    evidence: EnvelopeEvidence,
    *,
    envelope_source: pathlib.Path,
    execution_source: pathlib.Path,
    remote_main: str,
    git_executable: pathlib.Path,
) -> None:
    remote_revision = _full_sha(
        remote_main,
        "protected Bridge remote main",
    )
    if remote_revision != selection.envelope_revision:
        raise DispatchValidationError(
            "envelope revision is not exact protected Bridge main"
        )

    if envelope_source.is_symlink() or execution_source.is_symlink():
        raise DispatchValidationError(
            "Bridge envelope and execution checkouts cannot be symlinks"
        )
    try:
        envelope_root = envelope_source.resolve(strict=True)
        execution_root = execution_source.resolve(strict=True)
    except OSError as exc:
        raise DispatchValidationError(
            "Bridge envelope or execution checkout is absent"
        ) from exc
    if (
        not envelope_root.is_dir()
        or not execution_root.is_dir()
        or envelope_root.is_symlink()
        or execution_root.is_symlink()
        or envelope_root == execution_root
    ):
        raise DispatchValidationError(
            "Bridge envelope and execution checkouts must be distinct directories"
        )
    expected_envelope_path = _envelope_path(
        envelope_root,
        selection.job_id,
    ).resolve(strict=True)
    try:
        observed_envelope_path = pathlib.Path(
            evidence.envelope_path
        ).resolve(strict=True)
    except OSError as exc:
        raise DispatchValidationError(
            "verified envelope path is absent"
        ) from exc
    if observed_envelope_path != expected_envelope_path:
        raise DispatchValidationError(
            "verified envelope path is not bound to the envelope checkout"
        )

    envelope_head = _git_output(
        git_executable,
        envelope_root,
        "rev-parse",
        "HEAD",
    )
    protected_head = _git_output(
        git_executable,
        envelope_root,
        "rev-parse",
        "refs/remotes/origin/main",
    )
    execution_head = _git_output(
        git_executable,
        execution_root,
        "rev-parse",
        "HEAD",
    )
    origin_url = _git_output(
        git_executable,
        envelope_root,
        "remote",
        "get-url",
        "origin",
    )
    if (
        envelope_head != selection.envelope_revision
        or protected_head != selection.envelope_revision
        or origin_url.rstrip("/") != BRIDGE_REPOSITORY_URL.rstrip("/")
    ):
        raise DispatchValidationError(
            "envelope checkout is not exact protected Bridge main"
        )
    if execution_head != evidence.execution_bridge_revision:
        raise DispatchValidationError(
            "execution checkout does not equal the signed Bridge revision"
        )

    for label, source in (
        ("envelope", envelope_root),
        ("execution", execution_root),
    ):
        dirty = _git_output(
            git_executable,
            source,
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
        )
        if dirty:
            raise DispatchValidationError(
                f"{label} Bridge checkout is dirty"
            )

    _git_output(
        git_executable,
        envelope_root,
        "rev-parse",
        "--verify",
        f"{evidence.execution_bridge_revision}^{{commit}}",
    )
    for revision in (
        evidence.predecessor_execution_bridge_revision,
        evidence.predecessor_envelope_revision,
    ):
        _git_output(
            git_executable,
            envelope_root,
            "rev-parse",
            "--verify",
            f"{revision}^{{commit}}",
        )
    _git_output(
        git_executable,
        envelope_root,
        "merge-base",
        "--is-ancestor",
        evidence.predecessor_execution_bridge_revision,
        evidence.predecessor_envelope_revision,
    )
    _git_output(
        git_executable,
        envelope_root,
        "merge-base",
        "--is-ancestor",
        evidence.predecessor_envelope_revision,
        selection.envelope_revision,
    )
    historical_predecessor_envelope = _git_bytes(
        git_executable,
        envelope_root,
        "show",
        (
            f"{evidence.predecessor_envelope_revision}:"
            f"{evidence.predecessor_queue_path}"
        ),
    )
    if (
        hashlib.sha256(historical_predecessor_envelope).hexdigest()
        != evidence.predecessor_envelope_sha256
    ):
        raise DispatchValidationError(
            "protected predecessor envelope history does not match lineage"
        )
    _git_output(
        git_executable,
        envelope_root,
        "merge-base",
        "--is-ancestor",
        evidence.execution_bridge_revision,
        selection.envelope_revision,
    )


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
        "bridgeRevision": evidence.execution_bridge_revision,
        "dispatchedRevision": selection.source_revision,
        "envelopeRevision": selection.envelope_revision,
        "envelopeSha256": evidence.envelope_sha256,
        "executionBridgeRevision": evidence.execution_bridge_revision,
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
    verify.add_argument(
        "--envelope-source",
        type=pathlib.Path,
        required=True,
    )
    verify.add_argument("--github-env", type=pathlib.Path, required=True)

    history = subparsers.add_parser("verify-history")
    _add_selection_arguments(history)
    history.add_argument(
        "--envelope-source",
        type=pathlib.Path,
        required=True,
    )
    history.add_argument(
        "--execution-source",
        type=pathlib.Path,
        required=True,
    )
    history.add_argument("--remote-main", required=True)
    history.add_argument(
        "--git-executable",
        type=pathlib.Path,
        required=True,
    )

    claim = subparsers.add_parser("create-claim")
    _add_selection_arguments(claim)
    claim.add_argument(
        "--envelope-source",
        type=pathlib.Path,
        required=True,
    )
    claim.add_argument(
        "--execution-source",
        type=pathlib.Path,
        required=True,
    )
    claim.add_argument("--remote-main", required=True)
    claim.add_argument(
        "--git-executable",
        type=pathlib.Path,
        required=True,
    )
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
                envelope_source=args.envelope_source,
            )
            report = {"selection": asdict(selection), "evidence": asdict(evidence)}
            if args.command == "verify-envelope":
                write_verified_github_env(evidence, args.github_env)
            elif args.command == "verify-history":
                verify_bridge_history(
                    selection,
                    evidence,
                    envelope_source=args.envelope_source,
                    execution_source=args.execution_source,
                    remote_main=args.remote_main,
                    git_executable=args.git_executable,
                )
                report["history"] = {
                    "envelopeRevision": selection.envelope_revision,
                    "executionBridgeRevision": (
                        evidence.execution_bridge_revision
                    ),
                    "protected": True,
                }
            elif args.command == "create-claim":
                verify_bridge_history(
                    selection,
                    evidence,
                    envelope_source=args.envelope_source,
                    execution_source=args.execution_source,
                    remote_main=args.remote_main,
                    git_executable=args.git_executable,
                )
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
