#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Bounded, deterministic admission for Brain-derived train/eval rows.

This module does not turn raw Brain inventory into training data.  It evaluates
caller-supplied JSON/JSONL candidates and admits a row only when every required
provenance, rights, freshness, contamination, deduplication, and split
obligation is established by pinned, allowlisted Ed25519 evidence and a signed
cross-run split ledger.  Missing evidence is a reason-coded quarantine
decision; it is never guessed or filled in.

The gate performs no network access, starts no training, and grants no proof or
model-promotion credit.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import collections
import dataclasses
import datetime as dt
import hashlib
import json
import os
import pathlib
import re
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import urlsplit

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


CANDIDATE_SCHEMA = "szl.brain-training-candidate.v1"
DECISION_SCHEMA = "szl.brain-training-admission-decision.v1"
REPORT_SCHEMA = "szl.brain-training-admission-report.v1"
SOURCE_EVIDENCE_SCHEMA = "szl.source-revision-evidence.v2"
RIGHTS_EVIDENCE_SCHEMA = "szl.rights-evidence.v2"
CONTAMINATION_EVIDENCE_SCHEMA = "szl.contamination-evidence.v2"
SPLIT_LEDGER_SCHEMA = "szl.brain-training-split-ledger.v1"
TRUST_STORE_SCHEMA = "szl.evidence-trust-store.v1"
SIGNATURE_ALGORITHM = "Ed25519"

MAX_INPUT_BYTES = 32 * 1024 * 1024
MAX_ROWS = 20_000
MAX_ROW_BYTES = 256 * 1024
MAX_CONTENT_BYTES = 64 * 1024
MAX_EVIDENCE_BYTES = 4 * 1024 * 1024
MAX_REFERENCES = 64

DEFAULT_RIGHTS_BASES = ("PROJECT_AUTHORED_SCHEMA_GENERATED",)
DEFAULT_LICENSES = ("Apache-2.0",)
SPLITS = frozenset({"TRAIN", "EVAL"})

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_REVISION_RE = re.compile(r"^(?:git:[0-9a-f]{40,64}|sha256:[0-9a-f]{64})$")
_NODE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@+\-]{2,255}$")
_METHOD_RE = re.compile(r"^[A-Z0-9][A-Z0-9._:\-]{2,127}$")
_REFERENCE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@+\-]{1,255}$")

_ROW_FIELDS = frozenset(
    {
        "schema_version",
        "node_id",
        "content",
        "content_sha256",
        "source",
        "rights",
        "contamination",
        "split",
    }
)
_SOURCE_FIELDS = frozenset({"uri", "revision", "timestamp_utc", "evidence"})
_RIGHTS_FIELDS = frozenset({"basis", "license", "evidence"})
_CONTAMINATION_FIELDS = frozenset(
    {"result", "method", "checked_against", "evidence"}
)
_SIGNED_ENVELOPE_FIELDS = frozenset(
    {"schema_version", "issuer", "tool_identity", "issued_at_utc", "statement", "signature"}
)
_SIGNATURE_FIELDS = frozenset({"algorithm", "key_id", "value_base64"})
_RUN_RECEIPT_FIELDS = frozenset(
    {
        "run_id",
        "completed_at_utc",
        "tool_identity",
        "method",
        "candidate_content_sha256",
        "checked_against_sha256",
        "result",
    }
)


class AdmissionInputError(RuntimeError):
    """A bounded file-level input obligation failed before row evaluation."""


@dataclasses.dataclass(frozen=True)
class TrustedEvidenceSigner:
    """Pinned public-key identity allowed to issue admission evidence."""

    key_id: str
    issuer: str
    tool_identity: str
    public_key_path: str
    public_key_sha256: str


@dataclasses.dataclass(frozen=True)
class AdmissionPolicy:
    """Frozen policy inputs; ``as_of_utc`` is required for reproducibility."""

    as_of_utc: str
    evidence_root: pathlib.Path | str
    max_age_days: int = 365
    allowed_rights_bases: tuple[str, ...] = DEFAULT_RIGHTS_BASES
    allowed_licenses: tuple[str, ...] = DEFAULT_LICENSES
    protected_eval_content_sha256: frozenset[str] = frozenset()
    trusted_evidence_signers: tuple[TrustedEvidenceSigner, ...] = ()
    split_ledger_evidence: Mapping[str, str] | None = None

    def __post_init__(self) -> None:
        as_of = _parse_utc(self.as_of_utc)
        if as_of is None:
            raise AdmissionInputError("POLICY_AS_OF_UTC_INVALID")
        if not isinstance(self.max_age_days, int) or not 0 <= self.max_age_days <= 3650:
            raise AdmissionInputError("POLICY_MAX_AGE_DAYS_INVALID")
        root = pathlib.Path(self.evidence_root).resolve()
        if not root.is_dir():
            raise AdmissionInputError("POLICY_EVIDENCE_ROOT_UNAVAILABLE")
        bases = tuple(sorted(set(self.allowed_rights_bases)))
        licenses = tuple(sorted(set(self.allowed_licenses)))
        if not bases or not licenses or any(not value for value in (*bases, *licenses)):
            raise AdmissionInputError("POLICY_RIGHTS_ALLOWLIST_INVALID")
        protected = frozenset(self.protected_eval_content_sha256)
        if any(not _is_sha256(value) for value in protected):
            raise AdmissionInputError("POLICY_PROTECTED_EVAL_HASH_INVALID")
        signers = tuple(self.trusted_evidence_signers)
        if not signers:
            # Empty trust is valid policy construction, but every signed evidence
            # check will fail closed.  This keeps inspection-only use possible.
            pass
        if len({item.key_id for item in signers}) != len(signers):
            raise AdmissionInputError("POLICY_SIGNER_KEY_ID_DUPLICATE")
        for signer in signers:
            if not all(
                isinstance(value, str) and value.strip()
                for value in (signer.key_id, signer.issuer, signer.tool_identity)
            ):
                raise AdmissionInputError("POLICY_SIGNER_IDENTITY_INVALID")
            if not _is_sha256(signer.public_key_sha256):
                raise AdmissionInputError("POLICY_SIGNER_PUBLIC_KEY_SHA256_INVALID")
            key_path = _safe_evidence_path(root, signer.public_key_path)
            if key_path is None or not key_path.is_file():
                raise AdmissionInputError("POLICY_SIGNER_PUBLIC_KEY_UNAVAILABLE")
            if sha256_file(key_path) != signer.public_key_sha256:
                raise AdmissionInputError("POLICY_SIGNER_PUBLIC_KEY_HASH_MISMATCH")
            try:
                key = serialization.load_pem_public_key(key_path.read_bytes())
            except (OSError, ValueError, TypeError) as exc:
                raise AdmissionInputError("POLICY_SIGNER_PUBLIC_KEY_INVALID") from exc
            if not isinstance(key, Ed25519PublicKey):
                raise AdmissionInputError("POLICY_SIGNER_PUBLIC_KEY_NOT_ED25519")
        ledger_descriptor = self.split_ledger_evidence
        if ledger_descriptor is not None and (
            not isinstance(ledger_descriptor, Mapping)
            or set(ledger_descriptor) != {"path", "sha256"}
        ):
            raise AdmissionInputError("POLICY_SPLIT_LEDGER_DESCRIPTOR_INVALID")
        object.__setattr__(self, "as_of_utc", _format_utc(as_of))
        object.__setattr__(self, "evidence_root", root)
        object.__setattr__(self, "allowed_rights_bases", bases)
        object.__setattr__(self, "allowed_licenses", licenses)
        object.__setattr__(self, "protected_eval_content_sha256", protected)
        object.__setattr__(self, "trusted_evidence_signers", signers)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _receipted(value: Mapping[str, Any], field: str) -> dict[str, Any]:
    result = dict(value)
    result[field] = sha256_bytes(canonical_bytes(value))
    return result


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and _SHA256_RE.fullmatch(value) is not None


def _parse_utc(value: Any) -> dt.datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(dt.timezone.utc)


def _format_utc(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _unique_reasons(reasons: Iterable[str]) -> list[str]:
    return sorted(set(reasons))


def _safe_evidence_path(root: pathlib.Path, raw_path: Any) -> pathlib.Path | None:
    if not isinstance(raw_path, str) or not raw_path or "\x00" in raw_path:
        return None
    relative = pathlib.Path(raw_path)
    if relative.is_absolute():
        return None
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate


def _trusted_signer(
    policy: AdmissionPolicy, key_id: Any
) -> TrustedEvidenceSigner | None:
    if not isinstance(key_id, str):
        return None
    return next(
        (item for item in policy.trusted_evidence_signers if item.key_id == key_id),
        None,
    )


def _signed_payload(envelope: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": envelope.get("schema_version"),
        "issuer": envelope.get("issuer"),
        "tool_identity": envelope.get("tool_identity"),
        "issued_at_utc": envelope.get("issued_at_utc"),
        "statement": envelope.get("statement"),
    }


def _verify_bound_evidence(
    descriptor: Any,
    policy: AdmissionPolicy,
    prefix: str,
    schema: str,
    expected: Mapping[str, Any],
    *,
    exact_statement_fields: bool = True,
) -> tuple[dict[str, Any], list[str], Mapping[str, Any] | None]:
    observed: dict[str, Any] = {
        "path": None,
        "sha256": None,
        "status": "UNVERIFIED",
    }
    reasons: list[str] = []
    if not isinstance(descriptor, Mapping) or set(descriptor) != {"path", "sha256"}:
        return observed, [f"{prefix}_EVIDENCE_DESCRIPTOR_INVALID"], None
    raw_path = descriptor.get("path")
    declared_sha = descriptor.get("sha256")
    observed["path"] = raw_path if isinstance(raw_path, str) else None
    observed["sha256"] = declared_sha if isinstance(declared_sha, str) else None
    if not _is_sha256(declared_sha):
        reasons.append(f"{prefix}_EVIDENCE_SHA256_INVALID")
    path = _safe_evidence_path(pathlib.Path(policy.evidence_root), raw_path)
    if path is None:
        reasons.append(f"{prefix}_EVIDENCE_PATH_UNSAFE")
        return observed, _unique_reasons(reasons), None
    if not path.is_file():
        reasons.append(f"{prefix}_EVIDENCE_FILE_MISSING")
        return observed, _unique_reasons(reasons), None
    size = path.stat().st_size
    observed["bytes"] = size
    if size > MAX_EVIDENCE_BYTES:
        reasons.append(f"{prefix}_EVIDENCE_FILE_TOO_LARGE")
        return observed, _unique_reasons(reasons), None
    actual_sha = sha256_file(path)
    observed["observed_sha256"] = actual_sha
    if declared_sha != actual_sha:
        reasons.append(f"{prefix}_EVIDENCE_HASH_MISMATCH")
        return observed, _unique_reasons(reasons), None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        reasons.append(f"{prefix}_EVIDENCE_JSON_INVALID")
        return observed, _unique_reasons(reasons), None
    if not isinstance(payload, Mapping) or set(payload) != _SIGNED_ENVELOPE_FIELDS:
        reasons.append(f"{prefix}_EVIDENCE_ENVELOPE_INVALID")
        return observed, _unique_reasons(reasons), None
    if payload.get("schema_version") != schema:
        reasons.append(f"{prefix}_EVIDENCE_SCHEMA_MISMATCH")
    statement = payload.get("statement")
    if not isinstance(statement, Mapping):
        reasons.append(f"{prefix}_EVIDENCE_STATEMENT_INVALID")
        statement = None
    else:
        if exact_statement_fields and set(statement) != set(expected):
            reasons.append(f"{prefix}_EVIDENCE_STATEMENT_FIELDS_INVALID")
        for field, expected_value in expected.items():
            if statement.get(field) != expected_value:
                reasons.append(f"{prefix}_EVIDENCE_BINDING_MISMATCH:{field}")

    issued_at = _parse_utc(payload.get("issued_at_utc"))
    as_of = _parse_utc(policy.as_of_utc)
    if issued_at is None:
        reasons.append(f"{prefix}_EVIDENCE_ISSUED_AT_INVALID")
    elif as_of is not None and issued_at > as_of:
        reasons.append(f"{prefix}_EVIDENCE_ISSUED_IN_FUTURE")

    signature = payload.get("signature")
    if not isinstance(signature, Mapping) or set(signature) != _SIGNATURE_FIELDS:
        reasons.append(f"{prefix}_EVIDENCE_SIGNATURE_DESCRIPTOR_INVALID")
    else:
        key_id = signature.get("key_id")
        signer = _trusted_signer(policy, key_id)
        if signature.get("algorithm") != SIGNATURE_ALGORITHM:
            reasons.append(f"{prefix}_EVIDENCE_SIGNATURE_ALGORITHM_INVALID")
        if signer is None:
            reasons.append(f"{prefix}_EVIDENCE_SIGNER_NOT_ALLOWLISTED")
        else:
            if payload.get("issuer") != signer.issuer:
                reasons.append(f"{prefix}_EVIDENCE_ISSUER_NOT_ALLOWLISTED")
            if payload.get("tool_identity") != signer.tool_identity:
                reasons.append(f"{prefix}_EVIDENCE_TOOL_NOT_ALLOWLISTED")
            try:
                signature_bytes = base64.b64decode(
                    signature.get("value_base64"), validate=True
                )
            except (binascii.Error, TypeError, ValueError):
                reasons.append(f"{prefix}_EVIDENCE_SIGNATURE_ENCODING_INVALID")
            else:
                key_path = _safe_evidence_path(
                    pathlib.Path(policy.evidence_root), signer.public_key_path
                )
                try:
                    if key_path is None:
                        raise ValueError("trusted public key path is unsafe")
                    public_key = serialization.load_pem_public_key(key_path.read_bytes())
                    if not isinstance(public_key, Ed25519PublicKey):
                        raise TypeError("trusted public key is not Ed25519")
                    public_key.verify(signature_bytes, canonical_bytes(_signed_payload(payload)))
                except InvalidSignature:
                    reasons.append(f"{prefix}_EVIDENCE_SIGNATURE_INVALID")
                except (OSError, TypeError, ValueError):
                    reasons.append(f"{prefix}_EVIDENCE_PUBLIC_KEY_VERIFICATION_FAILED")
    if not reasons:
        observed.update(
            {
                "status": "VERIFIED_SIGNED_CONTENT_BINDING",
                "issuer": payload.get("issuer"),
                "tool_identity": payload.get("tool_identity"),
                "key_id": signature.get("key_id") if isinstance(signature, Mapping) else None,
                "statement_sha256": sha256_bytes(canonical_bytes(statement)),
            }
        )
    return observed, _unique_reasons(reasons), statement


def _checked_against_sha256(references: Sequence[str]) -> str:
    return sha256_bytes(canonical_bytes(list(references)))


def _protected_eval_set_sha256(values: Iterable[str]) -> str:
    return sha256_bytes(canonical_bytes(sorted(set(values))))


def _verify_contamination_run_receipt(
    statement: Mapping[str, Any] | None,
    *,
    expected_tool_identity: str | None,
    method: Any,
    content_sha256: Any,
    checked_against_sha256: str,
    result: Any,
) -> list[str]:
    prefix = "CONTAMINATION"
    if not isinstance(statement, Mapping):
        return [f"{prefix}_RUN_RECEIPT_MISSING"]
    required = {
        "result",
        "method",
        "candidate_content_sha256",
        "checked_against_sha256",
        "run_receipt",
        "run_receipt_sha256",
    }
    reasons: list[str] = []
    if set(statement) != required:
        reasons.append(f"{prefix}_EVIDENCE_STATEMENT_FIELDS_INVALID")
    receipt = statement.get("run_receipt")
    if not isinstance(receipt, Mapping) or set(receipt) != _RUN_RECEIPT_FIELDS:
        reasons.append(f"{prefix}_RUN_RECEIPT_INVALID")
        return _unique_reasons(reasons)
    receipt_sha = statement.get("run_receipt_sha256")
    if not _is_sha256(receipt_sha) or receipt_sha != sha256_bytes(canonical_bytes(receipt)):
        reasons.append(f"{prefix}_RUN_RECEIPT_HASH_MISMATCH")
    expected_receipt = {
        "tool_identity": expected_tool_identity,
        "method": method,
        "candidate_content_sha256": content_sha256,
        "checked_against_sha256": checked_against_sha256,
        "result": result,
    }
    for field, expected_value in expected_receipt.items():
        if receipt.get(field) != expected_value:
            reasons.append(f"{prefix}_RUN_RECEIPT_BINDING_MISMATCH:{field}")
    if not isinstance(receipt.get("run_id"), str) or not receipt.get("run_id"):
        reasons.append(f"{prefix}_RUN_RECEIPT_RUN_ID_INVALID")
    if _parse_utc(receipt.get("completed_at_utc")) is None:
        reasons.append(f"{prefix}_RUN_RECEIPT_COMPLETED_AT_INVALID")
    return _unique_reasons(reasons)


def _load_split_ledger(
    policy: AdmissionPolicy,
) -> tuple[dict[str, str], dict[str, Any], list[str]]:
    descriptor = policy.split_ledger_evidence
    if descriptor is None:
        return {}, {"status": "MISSING"}, ["SPLIT_LEDGER_REQUIRED"]
    observed, reasons, statement = _verify_bound_evidence(
        descriptor,
        policy,
        "SPLIT_LEDGER",
        SPLIT_LEDGER_SCHEMA,
        {},
        exact_statement_fields=False,
    )
    if not isinstance(statement, Mapping):
        return {}, observed, _unique_reasons([*reasons, "SPLIT_LEDGER_STATEMENT_INVALID"])
    expected_fields = {
        "ledger_id",
        "as_of_utc",
        "previous_ledger_sha256",
        "protected_eval_set_sha256",
        "entries",
    }
    if set(statement) != expected_fields:
        reasons.append("SPLIT_LEDGER_STATEMENT_FIELDS_INVALID")
    if not isinstance(statement.get("ledger_id"), str) or not statement.get("ledger_id"):
        reasons.append("SPLIT_LEDGER_ID_INVALID")
    ledger_as_of = _parse_utc(statement.get("as_of_utc"))
    policy_as_of = _parse_utc(policy.as_of_utc)
    if ledger_as_of is None:
        reasons.append("SPLIT_LEDGER_AS_OF_INVALID")
    elif policy_as_of is not None and ledger_as_of > policy_as_of:
        reasons.append("SPLIT_LEDGER_AS_OF_IN_FUTURE")
    previous = statement.get("previous_ledger_sha256")
    if previous is not None and not _is_sha256(previous):
        reasons.append("SPLIT_LEDGER_PREVIOUS_HASH_INVALID")
    if statement.get("protected_eval_set_sha256") != _protected_eval_set_sha256(
        policy.protected_eval_content_sha256
    ):
        reasons.append("SPLIT_LEDGER_PROTECTED_EVAL_BINDING_MISMATCH")
    raw_entries = statement.get("entries")
    ledger: dict[str, str] = {}
    normalized: list[dict[str, str]] = []
    if not isinstance(raw_entries, list):
        reasons.append("SPLIT_LEDGER_ENTRIES_INVALID")
    else:
        for entry in raw_entries:
            if (
                not isinstance(entry, Mapping)
                or set(entry) != {"content_sha256", "split"}
                or not _is_sha256(entry.get("content_sha256"))
                or entry.get("split") not in SPLITS
            ):
                reasons.append("SPLIT_LEDGER_ENTRY_INVALID")
                continue
            content_sha = str(entry["content_sha256"])
            split = str(entry["split"])
            if content_sha in ledger:
                reasons.append(
                    "SPLIT_LEDGER_CONFLICTING_ENTRY"
                    if ledger[content_sha] != split
                    else "SPLIT_LEDGER_DUPLICATE_ENTRY"
                )
            else:
                ledger[content_sha] = split
                normalized.append({"content_sha256": content_sha, "split": split})
        expected_order = sorted(
            normalized, key=lambda item: (item["content_sha256"], item["split"])
        )
        if normalized != expected_order:
            reasons.append("SPLIT_LEDGER_NOT_DETERMINISTIC_ORDER")
    reasons = _unique_reasons(reasons)
    if reasons:
        observed["status"] = "UNVERIFIED"
        return {}, observed, reasons
    observed.update(
        {
            "status": "VERIFIED_SIGNED_FROZEN_LEDGER",
            "ledger_id": statement.get("ledger_id"),
            "as_of_utc": statement.get("as_of_utc"),
            "entry_count": len(ledger),
        }
    )
    return ledger, observed, []


def _uri_is_explicit(value: Any) -> bool:
    if not isinstance(value, str) or len(value) > 2048:
        return False
    parsed = urlsplit(value)
    return bool(parsed.scheme and (parsed.netloc or parsed.path) and not parsed.username)


def _validate_row(raw: Any, index: int, policy: AdmissionPolicy) -> dict[str, Any]:
    reasons: list[str] = []
    candidate_sha = sha256_bytes(canonical_bytes(raw))
    if not isinstance(raw, Mapping):
        return {
            "schema_version": DECISION_SCHEMA,
            "input_index": index,
            "candidate_row_sha256": candidate_sha,
            "node_id": None,
            "content_sha256": None,
            "split": None,
            "dedup_group": None,
            "source": {"status": "UNVERIFIED"},
            "rights": {"status": "UNVERIFIED"},
            "freshness": {"state": "UNKNOWN"},
            "contamination": {"observed_result": "NOT_ESTABLISHED"},
            "reason_codes": ["ROW_NOT_OBJECT"],
        }

    row_bytes = len(canonical_bytes(raw))
    if row_bytes > MAX_ROW_BYTES:
        reasons.append("ROW_TOO_LARGE")
    missing = sorted(_ROW_FIELDS - set(raw))
    extra = sorted(set(raw) - _ROW_FIELDS)
    if missing:
        reasons.append("ROW_REQUIRED_FIELDS_MISSING")
    if extra:
        reasons.append("ROW_UNRECOGNIZED_FIELDS")
    if raw.get("schema_version") != CANDIDATE_SCHEMA:
        reasons.append("ROW_SCHEMA_MISMATCH")

    node_id = raw.get("node_id")
    if not isinstance(node_id, str) or _NODE_ID_RE.fullmatch(node_id) is None:
        reasons.append("NODE_ID_INVALID")
        node_id = node_id if isinstance(node_id, str) else None

    content = raw.get("content")
    if not isinstance(content, str) or not content:
        reasons.append("CONTENT_MISSING")
        content_bytes = b""
    else:
        content_bytes = content.encode("utf-8")
        if len(content_bytes) > MAX_CONTENT_BYTES:
            reasons.append("CONTENT_TOO_LARGE")
    declared_content_sha = raw.get("content_sha256")
    if not _is_sha256(declared_content_sha):
        reasons.append("CONTENT_SHA256_INVALID")
        content_sha = declared_content_sha if isinstance(declared_content_sha, str) else None
    else:
        content_sha = declared_content_sha
        if not isinstance(content, str) or sha256_bytes(content_bytes) != content_sha:
            reasons.append("CONTENT_HASH_MISMATCH")

    split = raw.get("split")
    if split not in SPLITS:
        reasons.append("SPLIT_INVALID")
        split = split if isinstance(split, str) else None

    source_raw = raw.get("source")
    source_result: dict[str, Any] = {"status": "UNVERIFIED"}
    freshness: dict[str, Any] = {
        "source_timestamp_utc": None,
        "as_of_utc": policy.as_of_utc,
        "max_age_days": policy.max_age_days,
        "age_seconds": None,
        "state": "UNKNOWN",
    }
    if not isinstance(source_raw, Mapping):
        reasons.append("SOURCE_INVALID")
    else:
        if set(source_raw) != _SOURCE_FIELDS:
            reasons.append("SOURCE_FIELDS_INVALID")
        uri = source_raw.get("uri")
        revision = source_raw.get("revision")
        timestamp = source_raw.get("timestamp_utc")
        if not _uri_is_explicit(uri):
            reasons.append("SOURCE_URI_INVALID")
        if not isinstance(revision, str) or _REVISION_RE.fullmatch(revision) is None:
            reasons.append("SOURCE_IMMUTABLE_REVISION_REQUIRED")
        timestamp_value = _parse_utc(timestamp)
        if timestamp_value is None:
            reasons.append("SOURCE_TIMESTAMP_INVALID")
        else:
            as_of_value = _parse_utc(policy.as_of_utc)
            assert as_of_value is not None
            age_seconds = int((as_of_value - timestamp_value).total_seconds())
            freshness.update(
                {
                    "source_timestamp_utc": _format_utc(timestamp_value),
                    "age_seconds": age_seconds,
                }
            )
            if age_seconds < 0:
                freshness["state"] = "FUTURE"
                reasons.append("SOURCE_TIMESTAMP_IN_FUTURE")
            elif age_seconds > policy.max_age_days * 86_400:
                freshness["state"] = "STALE"
                reasons.append("SOURCE_STALE")
            else:
                freshness["state"] = "FRESH"
        source_evidence, source_reasons, _ = _verify_bound_evidence(
            source_raw.get("evidence"),
            policy,
            "SOURCE",
            SOURCE_EVIDENCE_SCHEMA,
            {
                "candidate_content_sha256": declared_content_sha,
                "source_uri": uri,
                "source_revision": revision,
            },
        )
        reasons.extend(source_reasons)
        source_shape_ok = (
            _uri_is_explicit(uri)
            and isinstance(revision, str)
            and _REVISION_RE.fullmatch(revision) is not None
        )
        source_result = {
            "uri": uri if isinstance(uri, str) else None,
            "revision": revision if isinstance(revision, str) else None,
            "revision_state": (
                "PINNED_IDENTIFIER_WITH_SIGNED_EVIDENCE"
                if not source_reasons
                and source_shape_ok
                else "UNVERIFIED"
            ),
            "evidence": source_evidence,
            "status": (
                "VERIFIED_SIGNED_BINDING"
                if not source_reasons and source_shape_ok
                else "UNVERIFIED"
            ),
        }

    rights_raw = raw.get("rights")
    rights_result: dict[str, Any] = {"status": "UNVERIFIED"}
    if not isinstance(rights_raw, Mapping):
        reasons.append("RIGHTS_INVALID")
    else:
        if set(rights_raw) != _RIGHTS_FIELDS:
            reasons.append("RIGHTS_FIELDS_INVALID")
        basis = rights_raw.get("basis")
        license_id = rights_raw.get("license")
        if basis not in policy.allowed_rights_bases:
            reasons.append("RIGHTS_BASIS_NOT_ALLOWED")
        if license_id not in policy.allowed_licenses:
            reasons.append("LICENSE_NOT_ALLOWED")
        revision = source_raw.get("revision") if isinstance(source_raw, Mapping) else None
        source_uri = source_raw.get("uri") if isinstance(source_raw, Mapping) else None
        rights_evidence, rights_reasons, _ = _verify_bound_evidence(
            rights_raw.get("evidence"),
            policy,
            "RIGHTS",
            RIGHTS_EVIDENCE_SCHEMA,
            {
                "candidate_content_sha256": declared_content_sha,
                "source_uri": source_uri,
                "source_revision": revision,
                "basis": basis,
                "license": license_id,
            },
        )
        reasons.extend(rights_reasons)
        rights_result = {
            "basis": basis if isinstance(basis, str) else None,
            "license": license_id if isinstance(license_id, str) else None,
            "evidence": rights_evidence,
            "status": (
                "VERIFIED_SIGNED_CONTENT_RIGHTS_BINDING"
                if not rights_reasons
                and basis in policy.allowed_rights_bases
                and license_id in policy.allowed_licenses
                else "UNVERIFIED"
            ),
        }

    contamination_raw = raw.get("contamination")
    contamination_result: dict[str, Any] = {
        "declared_result": None,
        "observed_result": "NOT_ESTABLISHED",
        "method": None,
        "checked_against": [],
        "evidence": {"status": "UNVERIFIED"},
    }
    if not isinstance(contamination_raw, Mapping):
        reasons.append("CONTAMINATION_INVALID")
    else:
        if set(contamination_raw) != _CONTAMINATION_FIELDS:
            reasons.append("CONTAMINATION_FIELDS_INVALID")
        declared_result = contamination_raw.get("result")
        method = contamination_raw.get("method")
        references = contamination_raw.get("checked_against")
        if declared_result != "CLEAR":
            reasons.append(
                "CONTAMINATION_DETECTED"
                if declared_result == "DETECTED"
                else "CONTAMINATION_NOT_CLEARED"
            )
        if not isinstance(method, str) or _METHOD_RE.fullmatch(method) is None:
            reasons.append("CONTAMINATION_METHOD_INVALID")
        references_valid = (
            isinstance(references, list)
            and 0 < len(references) <= MAX_REFERENCES
            and len(references) == len(set(references))
            and all(
                isinstance(item, str) and _REFERENCE_RE.fullmatch(item) is not None
                for item in references
            )
        )
        if not references_valid:
            reasons.append("CONTAMINATION_REFERENCE_SET_INVALID")
        checked_against = list(references) if references_valid else []
        reference_digest = _checked_against_sha256(checked_against)
        contamination_evidence, contamination_reasons, contamination_statement = _verify_bound_evidence(
            contamination_raw.get("evidence"),
            policy,
            "CONTAMINATION",
            CONTAMINATION_EVIDENCE_SCHEMA,
            {
                "result": declared_result,
                "method": method,
                "candidate_content_sha256": declared_content_sha,
                "checked_against_sha256": reference_digest,
            },
            exact_statement_fields=False,
        )
        contamination_reasons.extend(
            _verify_contamination_run_receipt(
                contamination_statement,
                expected_tool_identity=(
                    contamination_evidence.get("tool_identity")
                    if isinstance(contamination_evidence, Mapping)
                    else None
                ),
                method=method,
                content_sha256=declared_content_sha,
                checked_against_sha256=reference_digest,
                result=declared_result,
            )
        )
        contamination_reasons = _unique_reasons(contamination_reasons)
        if contamination_reasons:
            contamination_evidence["status"] = "UNVERIFIED"
        reasons.extend(contamination_reasons)
        contamination_result = {
            "declared_result": declared_result if isinstance(declared_result, str) else None,
            "observed_result": (
                "CLEAR_WITH_SIGNED_RUN_RECEIPT"
                if declared_result == "CLEAR"
                and not contamination_reasons
                and isinstance(method, str)
                and _METHOD_RE.fullmatch(method) is not None
                and references_valid
                else "NOT_ESTABLISHED"
            ),
            "method": method if isinstance(method, str) else None,
            "checked_against": checked_against,
            "evidence": contamination_evidence,
        }

    if (
        split == "TRAIN"
        and _is_sha256(content_sha)
        and content_sha in policy.protected_eval_content_sha256
    ):
        reasons.append("PROTECTED_EVAL_CONTENT_IN_TRAIN")
        contamination_result["observed_result"] = "PROTECTED_EVAL_MATCH"
    elif (
        split == "EVAL"
        and _is_sha256(content_sha)
        and content_sha in policy.protected_eval_content_sha256
    ):
        contamination_result["observed_result"] = "PROTECTED_EVAL_MEMBER"

    return {
        "schema_version": DECISION_SCHEMA,
        "input_index": index,
        "candidate_row_sha256": candidate_sha,
        "node_id": node_id,
        "content": content if isinstance(content, str) else None,
        "content_sha256": content_sha,
        "split": split,
        "dedup_group": f"sha256:{content_sha}" if _is_sha256(content_sha) else None,
        "canonical_node_id": node_id if isinstance(node_id, str) else None,
        "source": source_result,
        "rights": rights_result,
        "freshness": freshness,
        "contamination": contamination_result,
        "reason_codes": _unique_reasons(reasons),
    }


def _append_reason(record: dict[str, Any], reason: str) -> None:
    record["reason_codes"] = _unique_reasons([*record["reason_codes"], reason])


def _finalize_record(record: Mapping[str, Any]) -> dict[str, Any]:
    body = dict(record)
    reasons = list(body.pop("reason_codes", []))
    admitted = not reasons
    split = body.get("split")
    body.update(
        {
            "canonical_status": "CANONICAL" if admitted else "QUARANTINED",
            "admission_decision": (
                f"ADMIT_{split}" if admitted and split in SPLITS else "QUARANTINE"
            ),
            "training_eligible": admitted and split == "TRAIN",
            "evaluation_eligible": admitted and split == "EVAL",
            "reason_codes": reasons,
        }
    )
    if not admitted:
        body.pop("content", None)
        body["content_included"] = False
    else:
        body["content_included"] = True
    return _receipted(body, "decision_receipt_sha256")


def admit_rows(rows: Sequence[Any], policy: AdmissionPolicy) -> dict[str, Any]:
    """Evaluate a bounded in-memory batch and return a receipted machine report."""

    if len(rows) > MAX_ROWS:
        raise AdmissionInputError("INPUT_ROW_LIMIT_EXCEEDED")
    drafts = [_validate_row(raw, index, policy) for index, raw in enumerate(rows)]
    prior_split_ledger, split_ledger_observed, split_ledger_reasons = _load_split_ledger(
        policy
    )

    for record in drafts:
        split = record.get("split")
        content_sha = record.get("content_sha256")
        if split == "TRAIN":
            if not policy.protected_eval_content_sha256:
                _append_reason(record, "FROZEN_EVAL_HASHES_REQUIRED_FOR_TRAIN")
            for reason in split_ledger_reasons:
                _append_reason(record, reason)
        if not split_ledger_reasons and _is_sha256(content_sha):
            prior_split = prior_split_ledger.get(str(content_sha))
            if prior_split is not None:
                _append_reason(
                    record,
                    "CROSS_RUN_SPLIT_CONFLICT"
                    if prior_split != split
                    else "CROSS_RUN_CONTENT_REUSE",
                )
                record["contamination"]["observed_result"] = (
                    "CROSS_RUN_SPLIT_MATCH"
                    if prior_split != split
                    else "PRIOR_RUN_CONTENT_MATCH"
                )

    by_node: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    by_content: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for record in drafts:
        if isinstance(record.get("node_id"), str):
            by_node[record["node_id"]].append(record)
        if _is_sha256(record.get("content_sha256")):
            by_content[record["content_sha256"]].append(record)

    for group in by_node.values():
        if len(group) > 1:
            for record in group:
                _append_reason(record, "DUPLICATE_NODE_ID")

    for content_sha, group in by_content.items():
        if len(group) < 2:
            continue
        splits = {record.get("split") for record in group if record.get("split") in SPLITS}
        canonical = min(
            group,
            key=lambda record: (
                str(record.get("node_id") or "~"),
                str(record.get("candidate_row_sha256") or "~"),
                int(record.get("input_index") or 0),
            ),
        )
        canonical_node_id = canonical.get("node_id")
        for record in group:
            record["canonical_node_id"] = canonical_node_id
        if len(splits) > 1:
            for record in group:
                _append_reason(record, "DEDUP_GROUP_SPLIT_CONFLICT")
                record["contamination"]["observed_result"] = "CROSS_SPLIT_CONTENT_MATCH"
        else:
            for record in group:
                if record is not canonical:
                    _append_reason(record, "DUPLICATE_CONTENT")

    decisions = [_finalize_record(record) for record in drafts]
    reason_counts: collections.Counter[str] = collections.Counter()
    for decision in decisions:
        reason_counts.update(decision["reason_codes"])
    train_count = sum(item["admission_decision"] == "ADMIT_TRAIN" for item in decisions)
    eval_count = sum(item["admission_decision"] == "ADMIT_EVAL" for item in decisions)
    quarantine_count = sum(item["admission_decision"] == "QUARANTINE" for item in decisions)
    if not decisions:
        state = "EMPTY_INPUT"
    elif quarantine_count == len(decisions):
        state = "ALL_QUARANTINED"
    elif quarantine_count:
        state = "COMPLETE_WITH_QUARANTINE"
    else:
        state = "ADMISSION_COMPLETE"
    if split_ledger_reasons:
        next_split_ledger: dict[str, Any] = {
            "state": "BLOCKED_INVALID_OR_MISSING_PRIOR_LEDGER",
            "reason_codes": split_ledger_reasons,
        }
    else:
        next_entries = dict(prior_split_ledger)
        for decision in decisions:
            if decision.get("admission_decision") in {"ADMIT_TRAIN", "ADMIT_EVAL"}:
                next_entries[str(decision["content_sha256"])] = str(decision["split"])
        next_split_ledger = {
            "state": "UNSIGNED_CANDIDATE_SIGNATURE_REQUIRED_BEFORE_REUSE",
            "schema_version": SPLIT_LEDGER_SCHEMA,
            "previous_ledger_evidence_sha256": (
                policy.split_ledger_evidence.get("sha256")
                if isinstance(policy.split_ledger_evidence, Mapping)
                else None
            ),
            "protected_eval_set_sha256": _protected_eval_set_sha256(
                policy.protected_eval_content_sha256
            ),
            "entries": [
                {"content_sha256": content_sha, "split": split}
                for content_sha, split in sorted(next_entries.items())
            ],
        }
        next_split_ledger["entries_sha256"] = sha256_bytes(
            canonical_bytes(next_split_ledger["entries"])
        )
    body = {
        "schema_version": REPORT_SCHEMA,
        "state": state,
        "policy": {
            "as_of_utc": policy.as_of_utc,
            "max_age_days": policy.max_age_days,
            "allowed_rights_bases": list(policy.allowed_rights_bases),
            "allowed_licenses": list(policy.allowed_licenses),
            "protected_eval_hash_count": len(policy.protected_eval_content_sha256),
            "trusted_evidence_signer_count": len(policy.trusted_evidence_signers),
            "bounds": {
                "max_input_bytes": MAX_INPUT_BYTES,
                "max_rows": MAX_ROWS,
                "max_row_bytes": MAX_ROW_BYTES,
                "max_content_bytes": MAX_CONTENT_BYTES,
                "max_evidence_bytes": MAX_EVIDENCE_BYTES,
            },
        },
        "summary": {
            "observed_rows": len(decisions),
            "admitted_train_rows": train_count,
            "admitted_eval_rows": eval_count,
            "quarantined_rows": quarantine_count,
            "dedup_group_count": len(by_content),
            "reason_counts": dict(sorted(reason_counts.items())),
        },
        "training_input_state": (
            "ADMITTED_ROWS_PRESENT_NOT_TRAINING_AUTHORIZATION"
            if train_count
            else "BLOCKED_ZERO_ADMITTED_TRAIN_ROWS"
        ),
        "split_ledger": {
            "observed": split_ledger_observed,
            "reason_codes": split_ledger_reasons,
            "next_unsigned_candidate": next_split_ledger,
        },
        "claims_boundary": {
            "training_triggered": False,
            "network_used": False,
            "proof_credit": 0,
            "model_trust_delta": 0,
            "model_promotion_allowed": False,
            "provenance_inferred": False,
        },
        "decisions": decisions,
    }
    return _receipted(body, "report_receipt_sha256")


def load_candidate_rows(path: pathlib.Path | str) -> list[Any]:
    """Read bounded JSONL or JSON (array or ``{"rows": [...]}``) candidates."""

    source = pathlib.Path(path)
    if not source.is_file():
        raise AdmissionInputError("INPUT_FILE_MISSING")
    if source.stat().st_size > MAX_INPUT_BYTES:
        raise AdmissionInputError("INPUT_FILE_TOO_LARGE")
    if source.suffix.lower() == ".jsonl":
        rows: list[Any] = []
        try:
            with source.open("r", encoding="utf-8") as stream:
                for line_number, line in enumerate(stream, start=1):
                    if not line.strip():
                        continue
                    if len(line.encode("utf-8")) > MAX_ROW_BYTES:
                        raise AdmissionInputError(f"INPUT_JSONL_ROW_TOO_LARGE:{line_number}")
                    try:
                        rows.append(json.loads(line))
                    except json.JSONDecodeError as exc:
                        raise AdmissionInputError(
                            f"INPUT_JSONL_INVALID:{line_number}"
                        ) from exc
                    if len(rows) > MAX_ROWS:
                        raise AdmissionInputError("INPUT_ROW_LIMIT_EXCEEDED")
        except (OSError, UnicodeError) as exc:
            raise AdmissionInputError("INPUT_JSONL_UNREADABLE") from exc
        return rows
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AdmissionInputError("INPUT_JSON_INVALID") from exc
    rows = payload.get("rows") if isinstance(payload, Mapping) else payload
    if not isinstance(rows, list):
        raise AdmissionInputError("INPUT_JSON_ROWS_ARRAY_REQUIRED")
    if len(rows) > MAX_ROWS:
        raise AdmissionInputError("INPUT_ROW_LIMIT_EXCEEDED")
    return rows


def _jsonl_bytes(rows: Iterable[Mapping[str, Any]]) -> bytes:
    return b"".join(canonical_bytes(row) + b"\n" for row in rows)


def _atomic_write(path: pathlib.Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_bytes(content)
    temporary.replace(path)


def write_artifacts(report: Mapping[str, Any], output_dir: pathlib.Path | str) -> dict[str, Any]:
    """Write deterministic admitted/quarantine ledgers plus a receipted report."""

    output = pathlib.Path(output_dir)
    decisions = list(report.get("decisions") or [])
    ledgers = {
        "admitted_train": (
            "admitted-train.jsonl",
            [row for row in decisions if row.get("admission_decision") == "ADMIT_TRAIN"],
        ),
        "admitted_eval": (
            "admitted-eval.jsonl",
            [row for row in decisions if row.get("admission_decision") == "ADMIT_EVAL"],
        ),
        "quarantine": (
            "quarantine.jsonl",
            [row for row in decisions if row.get("admission_decision") == "QUARANTINE"],
        ),
    }
    artifacts: dict[str, Any] = {}
    encoded: dict[str, bytes] = {}
    for key, (name, rows) in ledgers.items():
        content = _jsonl_bytes(rows)
        encoded[name] = content
        artifacts[key] = {
            "path": name,
            "rows": len(rows),
            "bytes": len(content),
            "sha256": sha256_bytes(content),
        }
    body = dict(report)
    body.pop("report_receipt_sha256", None)
    body["artifacts"] = artifacts
    final_report = _receipted(body, "report_receipt_sha256")
    encoded["admission-report.json"] = (
        json.dumps(final_report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")
    for name, content in encoded.items():
        _atomic_write(output / name, content)
    return final_report


def admit_file(
    input_path: pathlib.Path | str,
    output_dir: pathlib.Path | str,
    policy: AdmissionPolicy,
) -> dict[str, Any]:
    return write_artifacts(admit_rows(load_candidate_rows(input_path), policy), output_dir)


def _load_protected_hashes(path: str | None) -> frozenset[str]:
    if path is None:
        return frozenset()
    try:
        value = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AdmissionInputError("PROTECTED_EVAL_HASH_FILE_INVALID") from exc
    if isinstance(value, Mapping):
        value = value.get("content_sha256")
    if not isinstance(value, list) or any(not _is_sha256(item) for item in value):
        raise AdmissionInputError("PROTECTED_EVAL_HASH_LIST_INVALID")
    return frozenset(value)


def _load_trusted_signers(path: str | None) -> tuple[TrustedEvidenceSigner, ...]:
    if path is None:
        return ()
    try:
        value = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AdmissionInputError("TRUST_STORE_FILE_INVALID") from exc
    if (
        not isinstance(value, Mapping)
        or set(value) != {"schema_version", "signers"}
        or value.get("schema_version") != TRUST_STORE_SCHEMA
        or not isinstance(value.get("signers"), list)
    ):
        raise AdmissionInputError("TRUST_STORE_SCHEMA_INVALID")
    signers: list[TrustedEvidenceSigner] = []
    required = {
        "key_id",
        "issuer",
        "tool_identity",
        "public_key_path",
        "public_key_sha256",
    }
    for item in value["signers"]:
        if not isinstance(item, Mapping) or set(item) != required:
            raise AdmissionInputError("TRUST_STORE_SIGNER_INVALID")
        try:
            signers.append(TrustedEvidenceSigner(**dict(item)))
        except TypeError as exc:
            raise AdmissionInputError("TRUST_STORE_SIGNER_INVALID") from exc
    return tuple(signers)


def _load_evidence_descriptor(path: str | None, error_code: str) -> Mapping[str, str] | None:
    if path is None:
        return None
    try:
        value = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AdmissionInputError(error_code) from exc
    if (
        not isinstance(value, Mapping)
        or set(value) != {"path", "sha256"}
        or not isinstance(value.get("path"), str)
        or not _is_sha256(value.get("sha256"))
    ):
        raise AdmissionInputError(error_code)
    return dict(value)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--evidence-root", required=True)
    parser.add_argument("--as-of-utc", required=True)
    parser.add_argument("--max-age-days", type=int, default=365)
    parser.add_argument("--protected-eval-hashes")
    parser.add_argument("--trust-store")
    parser.add_argument("--split-ledger-evidence")
    args = parser.parse_args(argv)
    try:
        policy = AdmissionPolicy(
            as_of_utc=args.as_of_utc,
            evidence_root=args.evidence_root,
            max_age_days=args.max_age_days,
            protected_eval_content_sha256=_load_protected_hashes(
                args.protected_eval_hashes
            ),
            trusted_evidence_signers=_load_trusted_signers(args.trust_store),
            split_ledger_evidence=_load_evidence_descriptor(
                args.split_ledger_evidence,
                "SPLIT_LEDGER_EVIDENCE_DESCRIPTOR_FILE_INVALID",
            ),
        )
        report = admit_file(args.input, args.output_dir, policy)
    except AdmissionInputError as exc:
        print(json.dumps({"ok": False, "reason_code": str(exc)}, sort_keys=True))
        return 2
    print(
        json.dumps(
            {
                "ok": True,
                "state": report["state"],
                "summary": report["summary"],
                "report_receipt_sha256": report["report_receipt_sha256"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
