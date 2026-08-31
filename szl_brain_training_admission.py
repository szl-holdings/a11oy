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
import stat
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import urlsplit

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)


CANDIDATE_SCHEMA = "szl.brain-training-candidate.v2"
DECISION_SCHEMA = "szl.brain-training-admission-decision.v2"
REPORT_SCHEMA = "szl.brain-training-admission-report.v2"
ARTIFACT_MANIFEST_SCHEMA = "szl.brain-training-admission-artifact-manifest.v2"
SOURCE_EVIDENCE_SCHEMA = "szl.source-revision-evidence.v3"
RIGHTS_EVIDENCE_SCHEMA = "szl.rights-evidence.v3"
PRIVACY_EVIDENCE_SCHEMA = "szl.privacy-evidence.v1"
REVIEW_EVIDENCE_SCHEMA = "szl.admission-review-evidence.v1"
CONTAMINATION_EVIDENCE_SCHEMA = "szl.contamination-evidence.v2"
SPLIT_LEDGER_SCHEMA = "szl.brain-training-split-ledger.v1"
TRUST_STORE_SCHEMA = "szl.evidence-trust-store.v2"
POLICY_BUNDLE_SCHEMA = "szl.brain-training-admission-policy-bundle.v1"
SIGNATURE_ALGORITHM = "Ed25519"

PURPOSE_SOURCE = "SOURCE"
PURPOSE_RIGHTS = "RIGHTS"
PURPOSE_PRIVACY = "PRIVACY"
PURPOSE_CONTAMINATION = "CONTAMINATION"
PURPOSE_REVIEW = "REVIEW"
PURPOSE_SPLIT_LEDGER = "SPLIT_LEDGER"
PURPOSE_POLICY_ROOT = "POLICY_ROOT"
PURPOSE_ARTIFACT = "ARTIFACT"
EVIDENCE_PURPOSES = frozenset(
    {
        PURPOSE_SOURCE,
        PURPOSE_RIGHTS,
        PURPOSE_PRIVACY,
        PURPOSE_CONTAMINATION,
        PURPOSE_REVIEW,
        PURPOSE_SPLIT_LEDGER,
        PURPOSE_ARTIFACT,
    }
)

MAX_INPUT_BYTES = 32 * 1024 * 1024
MAX_ROWS = 20_000
MAX_ROW_BYTES = 256 * 1024
MAX_CONTENT_BYTES = 64 * 1024
MAX_EVIDENCE_BYTES = 4 * 1024 * 1024
MAX_KEY_BYTES = 64 * 1024
MAX_REFERENCES = 64

DEFAULT_RIGHTS_BASES = ("PROJECT_AUTHORED_SCHEMA_GENERATED",)
DEFAULT_LICENSES = ("Apache-2.0",)
DEFAULT_PERMISSION_SCOPES = ("TRAIN_DERIVATIVE_AND_REDISTRIBUTE",)
DEFAULT_PRIVACY_CLASSIFICATIONS = ("PUBLIC",)
SPLITS = frozenset({"TRAIN", "EVAL"})
ALLOWED_SOURCE_URI_SCHEMES = frozenset({"https", "git+https", "repo", "urn"})

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
        "privacy",
        "contamination",
        "review",
        "split",
    }
)
_SOURCE_FIELDS = frozenset(
    {"identity", "uri", "revision", "timestamp_utc", "evidence"}
)
_RIGHTS_FIELDS = frozenset(
    {
        "author",
        "rightsholder",
        "basis",
        "license",
        "permission_scope",
        "evidence",
    }
)
_PRIVACY_FIELDS = frozenset(
    {"classification", "pii_result", "method", "evidence"}
)
_CONTAMINATION_FIELDS = frozenset(
    {"result", "method", "checked_against", "evidence"}
)
_REVIEW_FIELDS = frozenset(
    {"state", "reviewer", "reviewed_at_utc", "reasons", "evidence"}
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
    purposes: tuple[str, ...]
    subject_id: str | None = None


@dataclasses.dataclass(frozen=True)
class ArtifactSigningKey:
    """Operator-supplied private key used only to sign the terminal manifest."""

    signer_key_id: str
    private_key_path: str


@dataclasses.dataclass(frozen=True)
class AdmissionPolicy:
    """Frozen policy inputs; ``as_of_utc`` is required for reproducibility."""

    as_of_utc: str
    evidence_root: pathlib.Path | str
    max_age_days: int = 365
    allowed_rights_bases: tuple[str, ...] = DEFAULT_RIGHTS_BASES
    allowed_licenses: tuple[str, ...] = DEFAULT_LICENSES
    allowed_permission_scopes: tuple[str, ...] = DEFAULT_PERMISSION_SCOPES
    allowed_privacy_classifications: tuple[str, ...] = DEFAULT_PRIVACY_CLASSIFICATIONS
    allowed_reviewers: tuple[str, ...] = ()
    enable_train_admission: bool = False
    protected_eval_content_sha256: frozenset[str] = frozenset()
    trusted_evidence_signers: tuple[TrustedEvidenceSigner, ...] = ()
    split_ledger_evidence: Mapping[str, str] | None = None
    expected_split_ledger_evidence_sha256: str | None = None
    policy_root_signer: TrustedEvidenceSigner | None = None
    policy_bundle_evidence: Mapping[str, str] | None = None
    artifact_signer_key_id: str | None = None
    _pinned_public_keys: Mapping[str, Ed25519PublicKey] = dataclasses.field(
        init=False, repr=False, compare=False, default_factory=dict
    )
    _policy_binding_sha256: str | None = dataclasses.field(
        init=False, repr=False, compare=False, default=None
    )

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
        permissions = tuple(sorted(set(self.allowed_permission_scopes)))
        privacy = tuple(sorted(set(self.allowed_privacy_classifications)))
        reviewers = tuple(sorted(set(self.allowed_reviewers)))
        if (
            not bases
            or not licenses
            or not permissions
            or not privacy
            or any(
                not isinstance(value, str) or not value.strip()
                for value in (*bases, *licenses, *permissions, *privacy, *reviewers)
            )
        ):
            raise AdmissionInputError("POLICY_RIGHTS_ALLOWLIST_INVALID")
        if any(_REFERENCE_RE.fullmatch(value) is None for value in reviewers):
            raise AdmissionInputError("POLICY_REVIEWER_ALLOWLIST_INVALID")
        if not isinstance(self.enable_train_admission, bool):
            raise AdmissionInputError("POLICY_TRAIN_ADMISSION_SWITCH_INVALID")
        protected = frozenset(self.protected_eval_content_sha256)
        if any(not _is_sha256(value) for value in protected):
            raise AdmissionInputError("POLICY_PROTECTED_EVAL_HASH_INVALID")
        signers = tuple(self.trusted_evidence_signers)
        root_signer = self.policy_root_signer
        all_signers = (*signers, *((root_signer,) if root_signer else ()))
        if len({item.key_id for item in all_signers}) != len(all_signers):
            raise AdmissionInputError("POLICY_SIGNER_KEY_ID_DUPLICATE")
        pinned_public_keys: dict[str, Ed25519PublicKey] = {}
        for signer in all_signers:
            if not all(
                isinstance(value, str) and value.strip()
                for value in (signer.key_id, signer.issuer, signer.tool_identity)
            ):
                raise AdmissionInputError("POLICY_SIGNER_IDENTITY_INVALID")
            purposes = tuple(sorted(set(signer.purposes)))
            allowed_purposes = (
                frozenset({PURPOSE_POLICY_ROOT})
                if signer is root_signer
                else EVIDENCE_PURPOSES
            )
            if (
                not purposes
                or any(purpose not in allowed_purposes for purpose in purposes)
                or purposes != signer.purposes
            ):
                raise AdmissionInputError("POLICY_SIGNER_PURPOSE_INVALID")
            if signer is root_signer and purposes != (PURPOSE_POLICY_ROOT,):
                raise AdmissionInputError("POLICY_ROOT_SIGNER_PURPOSE_INVALID")
            if PURPOSE_REVIEW in purposes:
                if purposes != (PURPOSE_REVIEW,) or signer.subject_id not in reviewers:
                    raise AdmissionInputError("POLICY_REVIEW_SIGNER_IDENTITY_INVALID")
            elif signer.subject_id is not None:
                raise AdmissionInputError("POLICY_SIGNER_SUBJECT_INVALID")
            if PURPOSE_ARTIFACT in purposes and purposes != (PURPOSE_ARTIFACT,):
                raise AdmissionInputError("POLICY_ARTIFACT_SIGNER_PURPOSE_INVALID")
            if not _is_sha256(signer.public_key_sha256):
                raise AdmissionInputError("POLICY_SIGNER_PUBLIC_KEY_SHA256_INVALID")
            pinned_public_keys[signer.key_id] = _pin_signer_public_key(root, signer)
        ledger_descriptor = self.split_ledger_evidence
        if ledger_descriptor is not None and (
            not isinstance(ledger_descriptor, Mapping)
            or set(ledger_descriptor) != {"path", "sha256"}
            or not _is_sha256(ledger_descriptor.get("sha256"))
        ):
            raise AdmissionInputError("POLICY_SPLIT_LEDGER_DESCRIPTOR_INVALID")
        expected_ledger_head = self.expected_split_ledger_evidence_sha256
        if expected_ledger_head is not None and not _is_sha256(expected_ledger_head):
            raise AdmissionInputError("POLICY_EXPECTED_SPLIT_LEDGER_HEAD_INVALID")
        artifact_signer_key_id = self.artifact_signer_key_id
        artifact_signer = next(
            (item for item in signers if item.key_id == artifact_signer_key_id), None
        )
        if artifact_signer_key_id is not None and (
            artifact_signer is None or artifact_signer.purposes != (PURPOSE_ARTIFACT,)
        ):
            raise AdmissionInputError("POLICY_ARTIFACT_SIGNER_NOT_ALLOWLISTED")
        policy_descriptor = self.policy_bundle_evidence
        if policy_descriptor is not None and (
            not isinstance(policy_descriptor, Mapping)
            or set(policy_descriptor) != {"path", "sha256"}
            or not _is_sha256(policy_descriptor.get("sha256"))
        ):
            raise AdmissionInputError("POLICY_BUNDLE_DESCRIPTOR_INVALID")
        object.__setattr__(self, "as_of_utc", _format_utc(as_of))
        object.__setattr__(self, "evidence_root", root)
        object.__setattr__(self, "allowed_rights_bases", bases)
        object.__setattr__(self, "allowed_licenses", licenses)
        object.__setattr__(self, "allowed_permission_scopes", permissions)
        object.__setattr__(self, "allowed_privacy_classifications", privacy)
        object.__setattr__(self, "allowed_reviewers", reviewers)
        object.__setattr__(self, "protected_eval_content_sha256", protected)
        object.__setattr__(self, "trusted_evidence_signers", signers)
        object.__setattr__(self, "_pinned_public_keys", pinned_public_keys)
        policy_statement = _policy_binding_statement(self)
        policy_binding_sha = sha256_bytes(canonical_bytes(policy_statement))
        object.__setattr__(self, "_policy_binding_sha256", policy_binding_sha)
        if self.enable_train_admission and (
            root_signer is None
            or policy_descriptor is None
            or artifact_signer is None
            or expected_ledger_head is None
        ):
            raise AdmissionInputError("POLICY_TRAIN_ROOTED_AUTHORIZATION_REQUIRED")
        if policy_descriptor is not None:
            if root_signer is None:
                raise AdmissionInputError("POLICY_ROOT_SIGNER_REQUIRED")
            _observed, policy_reasons, _statement = _verify_bound_evidence(
                policy_descriptor,
                self,
                "POLICY",
                POLICY_BUNDLE_SCHEMA,
                policy_statement,
                required_purpose=PURPOSE_POLICY_ROOT,
                signer_pool=(root_signer,),
            )
            if policy_reasons:
                raise AdmissionInputError(
                    "POLICY_BUNDLE_VERIFICATION_FAILED:" + ",".join(policy_reasons)
                )


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _strict_json_loads(value: str | bytes) -> Any:
    def reject_nonfinite(token: str) -> None:
        raise ValueError(f"non-finite JSON number: {token}")

    return json.loads(value, parse_constant=reject_nonfinite)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_confined_bytes_once(
    root: pathlib.Path, raw_path: Any, max_bytes: int
) -> tuple[pathlib.Path, bytes]:
    """Resolve beneath ``root`` and read one stable, bounded byte snapshot.

    Hashing, parsing, and signature verification must all consume the returned
    snapshot. Reopening the path or trusting a mutable symlink would reintroduce
    a substitution race.
    """

    root = root.resolve()
    if not isinstance(raw_path, str) or not raw_path or "\x00" in raw_path:
        raise AdmissionInputError("EVIDENCE_PATH_UNSAFE")
    relative = pathlib.Path(raw_path)
    if relative.is_absolute():
        raise AdmissionInputError("EVIDENCE_PATH_UNSAFE")
    lexical_path = root / relative
    try:
        lexical_before = lexical_path.lstat()
        is_junction = getattr(lexical_path, "is_junction", lambda: False)()
        if (
            stat.S_ISLNK(lexical_before.st_mode)
            or is_junction
            or not stat.S_ISREG(lexical_before.st_mode)
        ):
            raise AdmissionInputError("EVIDENCE_FILE_NOT_REGULAR")
        path = lexical_path.resolve(strict=True)
        path.relative_to(root)
        path_before = path.lstat()
        if stat.S_ISLNK(path_before.st_mode) or not stat.S_ISREG(path_before.st_mode):
            raise AdmissionInputError("EVIDENCE_FILE_NOT_REGULAR")
        if path_before.st_size <= 0:
            raise AdmissionInputError("EVIDENCE_FILE_EMPTY")
        if path_before.st_size > max_bytes:
            raise AdmissionInputError("EVIDENCE_FILE_TOO_LARGE")
        with path.open("rb") as stream:
            descriptor_before = os.fstat(stream.fileno())
            content = stream.read(max_bytes + 1)
            descriptor_after = os.fstat(stream.fileno())
        path_after = path.lstat()
        lexical_after = lexical_path.lstat()
        resolved_after = lexical_path.resolve(strict=True)
    except AdmissionInputError:
        raise
    except ValueError as exc:
        raise AdmissionInputError("EVIDENCE_PATH_UNSAFE") from exc
    except OSError as exc:
        raise AdmissionInputError("EVIDENCE_FILE_UNREADABLE") from exc
    identity = lambda value: (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_size,
        value.st_mtime_ns,
    )
    if (
        resolved_after != path
        or stat.S_ISLNK(path_after.st_mode)
        or not stat.S_ISREG(path_after.st_mode)
        or stat.S_ISLNK(lexical_after.st_mode)
        or not stat.S_ISREG(lexical_after.st_mode)
        or identity(lexical_before) != identity(path_before)
        or identity(path_before) != identity(descriptor_before)
        or identity(descriptor_before) != identity(descriptor_after)
        or identity(descriptor_after) != identity(path_after)
        or identity(path_after) != identity(lexical_after)
        or lexical_before.st_ctime_ns != path_before.st_ctime_ns
        or path_before.st_ctime_ns != path_after.st_ctime_ns
        or path_after.st_ctime_ns != lexical_after.st_ctime_ns
        or descriptor_before.st_ctime_ns != descriptor_after.st_ctime_ns
        or len(content) != descriptor_after.st_size
        or not content
    ):
        raise AdmissionInputError("EVIDENCE_FILE_UNSTABLE")
    if len(content) > max_bytes:
        raise AdmissionInputError("EVIDENCE_FILE_TOO_LARGE")
    return path, content


def _pin_signer_public_key(
    root: pathlib.Path, signer: TrustedEvidenceSigner
) -> Ed25519PublicKey:
    try:
        _path, key_bytes = _read_confined_bytes_once(
            root, signer.public_key_path, MAX_KEY_BYTES
        )
    except AdmissionInputError as exc:
        raise AdmissionInputError("POLICY_SIGNER_PUBLIC_KEY_UNAVAILABLE") from exc
    if sha256_bytes(key_bytes) != signer.public_key_sha256:
        raise AdmissionInputError("POLICY_SIGNER_PUBLIC_KEY_HASH_MISMATCH")
    try:
        key = serialization.load_pem_public_key(key_bytes)
    except (ValueError, TypeError) as exc:
        raise AdmissionInputError("POLICY_SIGNER_PUBLIC_KEY_INVALID") from exc
    if not isinstance(key, Ed25519PublicKey):
        raise AdmissionInputError("POLICY_SIGNER_PUBLIC_KEY_NOT_ED25519")
    return key


def _signer_policy_descriptor(signer: TrustedEvidenceSigner) -> dict[str, Any]:
    return {
        "key_id": signer.key_id,
        "issuer": signer.issuer,
        "tool_identity": signer.tool_identity,
        "public_key_sha256": signer.public_key_sha256,
        "purposes": list(signer.purposes),
        "subject_id": signer.subject_id,
    }


def _policy_binding_statement(policy: AdmissionPolicy) -> dict[str, Any]:
    """Canonical policy inputs authorized by the out-of-band policy root."""

    signers = sorted(
        (_signer_policy_descriptor(item) for item in policy.trusted_evidence_signers),
        key=lambda item: str(item["key_id"]),
    )
    return {
        "canonicalization": "SZL_CANONICAL_JSON_V1_SORTED_UTF8_NO_NONFINITE",
        "as_of_utc": policy.as_of_utc,
        "max_age_days": policy.max_age_days,
        "allowed_rights_bases": list(policy.allowed_rights_bases),
        "allowed_licenses": list(policy.allowed_licenses),
        "allowed_permission_scopes": list(policy.allowed_permission_scopes),
        "allowed_privacy_classifications": list(
            policy.allowed_privacy_classifications
        ),
        "allowed_source_uri_schemes": sorted(ALLOWED_SOURCE_URI_SCHEMES),
        "allowed_reviewers": list(policy.allowed_reviewers),
        "enable_train_admission": policy.enable_train_admission,
        "protected_eval_set_sha256": _protected_eval_set_sha256(
            policy.protected_eval_content_sha256
        ),
        "trusted_signers": signers,
        "trusted_signers_sha256": sha256_bytes(canonical_bytes(signers)),
        "split_ledger_evidence_sha256": (
            policy.split_ledger_evidence.get("sha256")
            if isinstance(policy.split_ledger_evidence, Mapping)
            else None
        ),
        "expected_split_ledger_evidence_sha256": (
            policy.expected_split_ledger_evidence_sha256
        ),
        "artifact_signer_key_id": policy.artifact_signer_key_id,
        "policy_root_key_id": (
            policy.policy_root_signer.key_id
            if policy.policy_root_signer is not None
            else None
        ),
        "bounds": {
            "max_input_bytes": MAX_INPUT_BYTES,
            "max_rows": MAX_ROWS,
            "max_row_bytes": MAX_ROW_BYTES,
            "max_content_bytes": MAX_CONTENT_BYTES,
            "max_evidence_bytes": MAX_EVIDENCE_BYTES,
        },
    }


def _rooted_admission_policy_ready(policy: AdmissionPolicy) -> bool:
    """Return whether release admission is anchored to all required roots."""

    return bool(
        policy.policy_root_signer is not None
        and policy.policy_bundle_evidence is not None
        and policy.expected_split_ledger_evidence_sha256 is not None
        and policy.artifact_signer_key_id is not None
        and policy._policy_binding_sha256 is not None
    )


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
    policy: AdmissionPolicy,
    key_id: Any,
    signer_pool: Sequence[TrustedEvidenceSigner] | None = None,
) -> TrustedEvidenceSigner | None:
    if not isinstance(key_id, str):
        return None
    return next(
        (
            item
            for item in (
                tuple(signer_pool)
                if signer_pool is not None
                else policy.trusted_evidence_signers
            )
            if item.key_id == key_id
        ),
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
    required_purpose: str,
    signer_pool: Sequence[TrustedEvidenceSigner] | None = None,
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
    try:
        _path, evidence_bytes = _read_confined_bytes_once(
            pathlib.Path(policy.evidence_root), raw_path, MAX_EVIDENCE_BYTES
        )
    except AdmissionInputError as exc:
        reason = str(exc)
        reason_suffix = {
            "EVIDENCE_FILE_TOO_LARGE": "FILE_TOO_LARGE",
            "EVIDENCE_FILE_EMPTY": "FILE_EMPTY",
            "EVIDENCE_FILE_NOT_REGULAR": "FILE_NOT_REGULAR",
            "EVIDENCE_FILE_UNSTABLE": "FILE_UNSTABLE",
            "EVIDENCE_PATH_UNSAFE": "PATH_UNSAFE",
        }.get(reason, "FILE_MISSING")
        reasons.append(f"{prefix}_EVIDENCE_{reason_suffix}")
        return observed, _unique_reasons(reasons), None
    observed["bytes"] = len(evidence_bytes)
    actual_sha = sha256_bytes(evidence_bytes)
    observed["observed_sha256"] = actual_sha
    if declared_sha != actual_sha:
        reasons.append(f"{prefix}_EVIDENCE_HASH_MISMATCH")
        return observed, _unique_reasons(reasons), None
    try:
        payload = _strict_json_loads(evidence_bytes.decode("utf-8"))
    except (UnicodeError, ValueError):
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
        signer = _trusted_signer(policy, key_id, signer_pool)
        if signature.get("algorithm") != SIGNATURE_ALGORITHM:
            reasons.append(f"{prefix}_EVIDENCE_SIGNATURE_ALGORITHM_INVALID")
        if signer is None:
            reasons.append(f"{prefix}_EVIDENCE_SIGNER_NOT_ALLOWLISTED")
        else:
            if required_purpose not in signer.purposes:
                reasons.append(f"{prefix}_EVIDENCE_SIGNER_PURPOSE_NOT_ALLOWED")
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
                try:
                    public_key = policy._pinned_public_keys.get(signer.key_id)
                    if public_key is None:
                        raise ValueError("trusted public key was not pinned")
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
                "signer_purpose": required_purpose,
                "signer_subject_id": signer.subject_id if signer is not None else None,
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
        required_purpose=PURPOSE_SPLIT_LEDGER,
    )
    expected_head = policy.expected_split_ledger_evidence_sha256
    if expected_head is None:
        reasons.append("SPLIT_LEDGER_EXPECTED_HEAD_REQUIRED")
    elif descriptor.get("sha256") != expected_head:
        reasons.append("SPLIT_LEDGER_HEAD_MISMATCH")
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
    return bool(
        parsed.scheme.lower() in ALLOWED_SOURCE_URI_SCHEMES
        and (parsed.netloc or parsed.path)
        and not parsed.username
        and not parsed.password
        and not parsed.query
        and not parsed.fragment
    )


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
            "privacy": {"status": "UNVERIFIED", "pii_result": "NOT_ESTABLISHED"},
            "freshness": {"state": "UNKNOWN"},
            "contamination": {"observed_result": "NOT_ESTABLISHED"},
            "review": {"status": "UNVERIFIED", "state": "NOT_ESTABLISHED"},
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
        identity = source_raw.get("identity")
        uri = source_raw.get("uri")
        revision = source_raw.get("revision")
        timestamp = source_raw.get("timestamp_utc")
        if not isinstance(identity, str) or _REFERENCE_RE.fullmatch(identity) is None:
            reasons.append("SOURCE_IDENTITY_INVALID")
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
                "source_identity": identity,
                "source_uri": uri,
                "source_revision": revision,
            },
            required_purpose=PURPOSE_SOURCE,
        )
        reasons.extend(source_reasons)
        source_shape_ok = (
            isinstance(identity, str)
            and _REFERENCE_RE.fullmatch(identity) is not None
            and _uri_is_explicit(uri)
            and isinstance(revision, str)
            and _REVISION_RE.fullmatch(revision) is not None
        )
        source_result = {
            "identity": identity if isinstance(identity, str) else None,
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
        author = rights_raw.get("author")
        rightsholder = rights_raw.get("rightsholder")
        basis = rights_raw.get("basis")
        license_id = rights_raw.get("license")
        permission_scope = rights_raw.get("permission_scope")
        if not isinstance(author, str) or _REFERENCE_RE.fullmatch(author) is None:
            reasons.append("RIGHTS_AUTHOR_INVALID")
        if (
            not isinstance(rightsholder, str)
            or _REFERENCE_RE.fullmatch(rightsholder) is None
        ):
            reasons.append("RIGHTS_RIGHTSHOLDER_INVALID")
        if basis not in policy.allowed_rights_bases:
            reasons.append("RIGHTS_BASIS_NOT_ALLOWED")
        if license_id not in policy.allowed_licenses:
            reasons.append("LICENSE_NOT_ALLOWED")
        if permission_scope not in policy.allowed_permission_scopes:
            reasons.append("PERMISSION_SCOPE_NOT_ALLOWED")
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
                "author": author,
                "rightsholder": rightsholder,
                "basis": basis,
                "license": license_id,
                "permission_scope": permission_scope,
            },
            required_purpose=PURPOSE_RIGHTS,
        )
        reasons.extend(rights_reasons)
        rights_result = {
            "author": author if isinstance(author, str) else None,
            "rightsholder": rightsholder if isinstance(rightsholder, str) else None,
            "basis": basis if isinstance(basis, str) else None,
            "license": license_id if isinstance(license_id, str) else None,
            "permission_scope": (
                permission_scope if isinstance(permission_scope, str) else None
            ),
            "evidence": rights_evidence,
            "status": (
                "VERIFIED_SIGNED_CONTENT_RIGHTS_BINDING"
                if not rights_reasons
                and isinstance(author, str)
                and _REFERENCE_RE.fullmatch(author) is not None
                and isinstance(rightsholder, str)
                and _REFERENCE_RE.fullmatch(rightsholder) is not None
                and basis in policy.allowed_rights_bases
                and license_id in policy.allowed_licenses
                and permission_scope in policy.allowed_permission_scopes
                else "UNVERIFIED"
            ),
        }

    privacy_raw = raw.get("privacy")
    privacy_result: dict[str, Any] = {
        "classification": None,
        "pii_result": "NOT_ESTABLISHED",
        "method": None,
        "evidence": {"status": "UNVERIFIED"},
        "status": "UNVERIFIED",
    }
    if not isinstance(privacy_raw, Mapping):
        reasons.append("PRIVACY_INVALID")
    else:
        if set(privacy_raw) != _PRIVACY_FIELDS:
            reasons.append("PRIVACY_FIELDS_INVALID")
        classification = privacy_raw.get("classification")
        pii_result = privacy_raw.get("pii_result")
        privacy_method = privacy_raw.get("method")
        if classification not in policy.allowed_privacy_classifications:
            reasons.append("PRIVACY_CLASSIFICATION_NOT_ALLOWED")
        if pii_result != "CLEAR":
            reasons.append(
                "PII_DETECTED"
                if pii_result == "DETECTED"
                else "PII_CLEARANCE_NOT_ESTABLISHED"
            )
        if (
            not isinstance(privacy_method, str)
            or _METHOD_RE.fullmatch(privacy_method) is None
        ):
            reasons.append("PRIVACY_METHOD_INVALID")
        privacy_evidence, privacy_reasons, _ = _verify_bound_evidence(
            privacy_raw.get("evidence"),
            policy,
            "PRIVACY",
            PRIVACY_EVIDENCE_SCHEMA,
            {
                "candidate_content_sha256": declared_content_sha,
                "classification": classification,
                "pii_result": pii_result,
                "method": privacy_method,
            },
            required_purpose=PURPOSE_PRIVACY,
        )
        reasons.extend(privacy_reasons)
        privacy_verified = (
            not privacy_reasons
            and classification in policy.allowed_privacy_classifications
            and pii_result == "CLEAR"
            and isinstance(privacy_method, str)
            and _METHOD_RE.fullmatch(privacy_method) is not None
        )
        privacy_result = {
            "classification": (
                classification if isinstance(classification, str) else None
            ),
            "pii_result": pii_result if isinstance(pii_result, str) else None,
            "method": privacy_method if isinstance(privacy_method, str) else None,
            "evidence": privacy_evidence,
            "status": (
                "VERIFIED_SIGNED_PII_CLEARANCE"
                if privacy_verified
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
            and all(
                isinstance(item, str) and _REFERENCE_RE.fullmatch(item) is not None
                for item in references
            )
            and len(references) == len(set(references))
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
            required_purpose=PURPOSE_CONTAMINATION,
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
    elif split == "EVAL":
        reasons.append("EVAL_CONTENT_NOT_IN_FROZEN_SET")

    review_raw = raw.get("review")
    review_result: dict[str, Any] = {
        "state": "NOT_ESTABLISHED",
        "reviewer": None,
        "reviewed_at_utc": None,
        "reasons": [],
        "evidence": {"status": "UNVERIFIED"},
        "status": "UNVERIFIED",
    }
    if not isinstance(review_raw, Mapping):
        reasons.append("REVIEW_INVALID")
    else:
        if set(review_raw) != _REVIEW_FIELDS:
            reasons.append("REVIEW_FIELDS_INVALID")
        review_state = review_raw.get("state")
        reviewer = review_raw.get("reviewer")
        reviewed_at = review_raw.get("reviewed_at_utc")
        review_reasons = review_raw.get("reasons")
        if review_state != "APPROVED":
            reasons.append(
                "REVIEW_REJECTED"
                if review_state == "REJECTED"
                else "REVIEW_APPROVAL_REQUIRED"
            )
        if (
            not isinstance(reviewer, str)
            or _REFERENCE_RE.fullmatch(reviewer) is None
        ):
            reasons.append("REVIEWER_ID_INVALID")
        elif reviewer not in policy.allowed_reviewers:
            reasons.append("REVIEWER_NOT_ALLOWLISTED")
        reviewed_at_value = _parse_utc(reviewed_at)
        as_of_value = _parse_utc(policy.as_of_utc)
        if reviewed_at_value is None:
            reasons.append("REVIEWED_AT_INVALID")
        elif as_of_value is not None and reviewed_at_value > as_of_value:
            reasons.append("REVIEWED_AT_IN_FUTURE")
        reasons_valid = (
            isinstance(review_reasons, list)
            and len(review_reasons) <= MAX_REFERENCES
            and all(
                isinstance(item, str) and _METHOD_RE.fullmatch(item) is not None
                for item in review_reasons
            )
            and len(review_reasons) == len(set(review_reasons))
        )
        if not reasons_valid:
            reasons.append("REVIEW_REASONS_INVALID")
        elif review_state == "APPROVED" and review_reasons:
            reasons.append("APPROVED_REVIEW_HAS_REJECTION_REASONS")
        normalized_review_reasons = list(review_reasons) if reasons_valid else []
        review_evidence, review_evidence_reasons, _ = _verify_bound_evidence(
            review_raw.get("evidence"),
            policy,
            "REVIEW",
            REVIEW_EVIDENCE_SCHEMA,
            {
                "candidate_content_sha256": declared_content_sha,
                "node_id": node_id,
                "state": review_state,
                "reviewer": reviewer,
                "reviewed_at_utc": reviewed_at,
                "reasons": normalized_review_reasons,
            },
            required_purpose=PURPOSE_REVIEW,
        )
        if (
            not review_evidence_reasons
            and review_evidence.get("signer_subject_id") != reviewer
        ):
            review_evidence_reasons.append(
                "REVIEW_EVIDENCE_SIGNER_SUBJECT_MISMATCH"
            )
            review_evidence["status"] = "UNVERIFIED"
        reasons.extend(review_evidence_reasons)
        review_verified = (
            not review_evidence_reasons
            and review_state == "APPROVED"
            and isinstance(reviewer, str)
            and reviewer in policy.allowed_reviewers
            and reviewed_at_value is not None
            and as_of_value is not None
            and reviewed_at_value <= as_of_value
            and not normalized_review_reasons
        )
        review_result = {
            "state": review_state if isinstance(review_state, str) else None,
            "reviewer": reviewer if isinstance(reviewer, str) else None,
            "reviewed_at_utc": (
                _format_utc(reviewed_at_value) if reviewed_at_value else None
            ),
            "reasons": normalized_review_reasons,
            "evidence": review_evidence,
            "status": (
                "VERIFIED_SIGNED_ALLOWLISTED_REVIEW"
                if review_verified
                else "UNVERIFIED"
            ),
        }

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
        "privacy": privacy_result,
        "freshness": freshness,
        "contamination": contamination_result,
        "review": review_result,
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
        # Quarantine is intended for broad operational circulation.  Do not copy
        # the very URI, path, authorship, reviewer, or content fields that may
        # have failed privacy/rights admission into that public artifact.
        body = {
            "schema_version": body.get("schema_version"),
            "input_index": body.get("input_index"),
            "candidate_row_sha256": body.get("candidate_row_sha256"),
            "node_id": None,
            "content_sha256": None,
            "split": body.get("split"),
            "dedup_group": None,
            "canonical_node_id": None,
            "source": {"status": (body.get("source") or {}).get("status", "UNVERIFIED")},
            "rights": {"status": (body.get("rights") or {}).get("status", "UNVERIFIED")},
            "privacy": {"status": (body.get("privacy") or {}).get("status", "UNVERIFIED")},
            "freshness": {"state": (body.get("freshness") or {}).get("state", "UNKNOWN")},
            "contamination": {
                "observed_result": (body.get("contamination") or {}).get(
                    "observed_result", "NOT_ESTABLISHED"
                )
            },
            "review": {
                "state": (body.get("review") or {}).get("state", "NOT_ESTABLISHED"),
                "status": (body.get("review") or {}).get("status", "UNVERIFIED"),
            },
            "canonical_status": "QUARANTINED",
            "admission_decision": "QUARANTINE",
            "training_eligible": False,
            "evaluation_eligible": False,
            "reason_codes": reasons,
            "content_included": False,
        }
    else:
        body["content_included"] = True
    return _receipted(body, "decision_receipt_sha256")


def admit_rows(rows: Sequence[Any], policy: AdmissionPolicy) -> dict[str, Any]:
    """Evaluate a bounded in-memory batch and return a receipted machine report."""

    if len(rows) > MAX_ROWS:
        raise AdmissionInputError("INPUT_ROW_LIMIT_EXCEEDED")
    try:
        drafts = [_validate_row(raw, index, policy) for index, raw in enumerate(rows)]
    except (TypeError, ValueError) as exc:
        raise AdmissionInputError("INPUT_ROW_NOT_CANONICAL_JSON") from exc
    prior_split_ledger, split_ledger_observed, split_ledger_reasons = _load_split_ledger(
        policy
    )

    for record in drafts:
        split = record.get("split")
        content_sha = record.get("content_sha256")
        if split == "EVAL" and not _rooted_admission_policy_ready(policy):
            _append_reason(record, "EVAL_ROOTED_ADMISSION_POLICY_REQUIRED")
        if split == "TRAIN":
            if not policy.enable_train_admission:
                _append_reason(record, "TRAIN_ADMISSION_DISABLED_BY_POLICY")
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
        "input_manifest": {
            "ordered_candidate_row_sha256": [
                item["candidate_row_sha256"] for item in decisions
            ],
            "ordered_candidate_rows_sha256": sha256_bytes(
                canonical_bytes(
                    [item["candidate_row_sha256"] for item in decisions]
                )
            ),
        },
        "policy": {
            "as_of_utc": policy.as_of_utc,
            "max_age_days": policy.max_age_days,
            "allowed_rights_bases": list(policy.allowed_rights_bases),
            "allowed_licenses": list(policy.allowed_licenses),
            "allowed_permission_scopes": list(policy.allowed_permission_scopes),
            "allowed_privacy_classifications": list(
                policy.allowed_privacy_classifications
            ),
            "allowed_reviewer_count": len(policy.allowed_reviewers),
            "allowed_reviewers_sha256": sha256_bytes(
                canonical_bytes(list(policy.allowed_reviewers))
            ),
            "enable_train_admission": policy.enable_train_admission,
            "protected_eval_hash_count": len(policy.protected_eval_content_sha256),
            "protected_eval_set_sha256": _protected_eval_set_sha256(
                policy.protected_eval_content_sha256
            ),
            "trusted_evidence_signer_count": len(policy.trusted_evidence_signers),
            "trusted_evidence_signers_sha256": sha256_bytes(
                canonical_bytes(
                    sorted(
                        (
                            _signer_policy_descriptor(item)
                            for item in policy.trusted_evidence_signers
                        ),
                        key=lambda item: str(item["key_id"]),
                    )
                )
            ),
            "policy_binding_sha256": policy._policy_binding_sha256,
            "policy_bundle_evidence_sha256": (
                policy.policy_bundle_evidence.get("sha256")
                if isinstance(policy.policy_bundle_evidence, Mapping)
                else None
            ),
            "policy_root_key_id": (
                policy.policy_root_signer.key_id
                if policy.policy_root_signer is not None
                else None
            ),
            "policy_verification_state": (
                "VERIFIED_ROOT_SIGNED"
                if policy.policy_bundle_evidence is not None
                else "UNSIGNED_INSPECTION_ONLY"
            ),
            "expected_split_ledger_evidence_sha256": (
                policy.expected_split_ledger_evidence_sha256
            ),
            "artifact_signer_key_id": policy.artifact_signer_key_id,
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
            "default_gradient_eligibility": False,
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
                        rows.append(_strict_json_loads(line))
                    except ValueError as exc:
                        raise AdmissionInputError(
                            f"INPUT_JSONL_INVALID:{line_number}"
                        ) from exc
                    if len(rows) > MAX_ROWS:
                        raise AdmissionInputError("INPUT_ROW_LIMIT_EXCEEDED")
        except (OSError, UnicodeError) as exc:
            raise AdmissionInputError("INPUT_JSONL_UNREADABLE") from exc
        return rows
    try:
        payload = _strict_json_loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
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


def _artifact_private_key(
    policy: AdmissionPolicy, signing_key: ArtifactSigningKey
) -> tuple[Ed25519PrivateKey, TrustedEvidenceSigner]:
    signer = _trusted_signer(policy, signing_key.signer_key_id)
    if signer is None or signer.purposes != (PURPOSE_ARTIFACT,):
        raise AdmissionInputError("ARTIFACT_SIGNER_NOT_ALLOWLISTED")
    try:
        _path, private_bytes = _read_confined_bytes_once(
            pathlib.Path(policy.evidence_root),
            signing_key.private_key_path,
            MAX_KEY_BYTES,
        )
        private_key = serialization.load_pem_private_key(private_bytes, password=None)
    except (AdmissionInputError, TypeError, ValueError) as exc:
        raise AdmissionInputError("ARTIFACT_PRIVATE_KEY_INVALID") from exc
    if not isinstance(private_key, Ed25519PrivateKey):
        raise AdmissionInputError("ARTIFACT_PRIVATE_KEY_NOT_ED25519")
    pinned = policy._pinned_public_keys.get(signer.key_id)
    if pinned is None:
        raise AdmissionInputError("ARTIFACT_PUBLIC_KEY_NOT_PINNED")
    private_public = private_key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    pinned_public = pinned.public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    if private_public != pinned_public:
        raise AdmissionInputError("ARTIFACT_PRIVATE_KEY_PUBLIC_KEY_MISMATCH")
    return private_key, signer


def verify_artifact_manifest(
    manifest: Mapping[str, Any], policy: AdmissionPolicy
) -> list[str]:
    """Verify the terminal self-hash, rooted policy binding, and Ed25519 signature."""

    reasons: list[str] = []
    if manifest.get("schema_version") != ARTIFACT_MANIFEST_SCHEMA:
        reasons.append("ARTIFACT_MANIFEST_SCHEMA_MISMATCH")
    signature = manifest.get("signature")
    if not isinstance(signature, Mapping) or set(signature) != _SIGNATURE_FIELDS:
        return [*reasons, "ARTIFACT_MANIFEST_SIGNATURE_INVALID"]
    signer = _trusted_signer(policy, signature.get("key_id"))
    if signer is None or signer.purposes != (PURPOSE_ARTIFACT,):
        reasons.append("ARTIFACT_MANIFEST_SIGNER_NOT_ALLOWLISTED")
    if signature.get("algorithm") != SIGNATURE_ALGORITHM:
        reasons.append("ARTIFACT_MANIFEST_SIGNATURE_ALGORITHM_INVALID")
    if signer is not None and (
        manifest.get("issuer") != signer.issuer
        or manifest.get("tool_identity") != signer.tool_identity
    ):
        reasons.append("ARTIFACT_MANIFEST_SIGNER_IDENTITY_MISMATCH")
    if manifest.get("policy_binding_sha256") != policy._policy_binding_sha256:
        reasons.append("ARTIFACT_MANIFEST_POLICY_BINDING_MISMATCH")
    expected_bundle_sha = (
        policy.policy_bundle_evidence.get("sha256")
        if isinstance(policy.policy_bundle_evidence, Mapping)
        else None
    )
    if manifest.get("policy_bundle_evidence_sha256") != expected_bundle_sha:
        reasons.append("ARTIFACT_MANIFEST_POLICY_BUNDLE_MISMATCH")
    unsigned = dict(manifest)
    unsigned.pop("signature", None)
    receipt = unsigned.pop("manifest_receipt_sha256", None)
    if receipt != sha256_bytes(canonical_bytes(unsigned)):
        reasons.append("ARTIFACT_MANIFEST_RECEIPT_MISMATCH")
    try:
        signature_bytes = base64.b64decode(signature.get("value_base64"), validate=True)
    except (binascii.Error, TypeError, ValueError):
        reasons.append("ARTIFACT_MANIFEST_SIGNATURE_ENCODING_INVALID")
    else:
        if signer is not None:
            try:
                policy._pinned_public_keys[signer.key_id].verify(
                    signature_bytes,
                    canonical_bytes({**unsigned, "manifest_receipt_sha256": receipt}),
                )
            except (InvalidSignature, KeyError):
                reasons.append("ARTIFACT_MANIFEST_SIGNATURE_INVALID")
    return _unique_reasons(reasons)


def write_artifacts(
    report: Mapping[str, Any],
    output_dir: pathlib.Path | str,
    *,
    policy: AdmissionPolicy | None = None,
    artifact_signing_key: ArtifactSigningKey | None = None,
) -> dict[str, Any]:
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
    report_bytes = (
        json.dumps(final_report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")
    encoded["admission-report.json"] = report_bytes
    decision_receipts = [
        str(row.get("decision_receipt_sha256") or "") for row in decisions
    ]
    admitted_rows_present = any(
        row.get("admission_decision") in {"ADMIT_TRAIN", "ADMIT_EVAL"}
        for row in decisions
    )
    if admitted_rows_present and (policy is None or artifact_signing_key is None):
        raise AdmissionInputError("ARTIFACT_SIGNING_KEY_REQUIRED_FOR_ADMISSION")
    signer: TrustedEvidenceSigner | None = None
    private_key: "Ed25519PrivateKey" | None = None
    if artifact_signing_key is not None:
        if policy is None:
            raise AdmissionInputError("ARTIFACT_SIGNING_POLICY_REQUIRED")
        private_key, signer = _artifact_private_key(policy, artifact_signing_key)
    artifact_manifest_body = {
        "schema_version": ARTIFACT_MANIFEST_SCHEMA,
        "report": {
            "path": "admission-report.json",
            "bytes": len(report_bytes),
            "sha256": sha256_bytes(report_bytes),
            "report_receipt_sha256": final_report["report_receipt_sha256"],
        },
        "ledgers": artifacts,
        "decision_set": {
            "rows": len(decisions),
            "ordered_decision_receipt_sha256": decision_receipts,
            "ordered_decision_receipts_sha256": sha256_bytes(
                canonical_bytes(decision_receipts)
            ),
        },
        "input_manifest": final_report.get("input_manifest"),
        "claims_boundary": {
            "training_triggered": False,
            "network_used": False,
            "model_promotion_allowed": False,
        },
        "policy_binding_sha256": (
            policy._policy_binding_sha256 if policy is not None else None
        ),
        "policy_bundle_evidence_sha256": (
            policy.policy_bundle_evidence.get("sha256")
            if policy is not None
            and isinstance(policy.policy_bundle_evidence, Mapping)
            else None
        ),
        "authorization_state": (
            "ROOTED_SIGNED_TERMINAL_MANIFEST"
            if signer is not None
            else "UNSIGNED_INSPECTION_ONLY"
        ),
        "issuer": signer.issuer if signer is not None else None,
        "tool_identity": signer.tool_identity if signer is not None else None,
        "issued_at_utc": policy.as_of_utc if signer is not None and policy else None,
    }
    artifact_manifest_unsigned = _receipted(
        artifact_manifest_body, "manifest_receipt_sha256"
    )
    artifact_manifest = {
        **artifact_manifest_unsigned,
        "signature": (
            {
                "algorithm": SIGNATURE_ALGORITHM,
                "key_id": signer.key_id,
                "value_base64": base64.b64encode(
                    private_key.sign(canonical_bytes(artifact_manifest_unsigned))
                ).decode("ascii"),
            }
            if signer is not None and private_key is not None
            else None
        ),
    }
    encoded["admission-manifest.json"] = (
        json.dumps(
            artifact_manifest, ensure_ascii=False, sort_keys=True, indent=2
        )
        + "\n"
    ).encode("utf-8")
    for name, content in encoded.items():
        _atomic_write(output / name, content)
    return final_report


def admit_file(
    input_path: pathlib.Path | str,
    output_dir: pathlib.Path | str,
    policy: AdmissionPolicy,
    artifact_signing_key: ArtifactSigningKey | None = None,
) -> dict[str, Any]:
    return write_artifacts(
        admit_rows(load_candidate_rows(input_path), policy),
        output_dir,
        policy=policy,
        artifact_signing_key=artifact_signing_key,
    )


def _load_protected_hashes(path: str | None) -> frozenset[str]:
    if path is None:
        return frozenset()
    try:
        value = _strict_json_loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise AdmissionInputError("PROTECTED_EVAL_HASH_FILE_INVALID") from exc
    if isinstance(value, Mapping):
        value = value.get("content_sha256")
    if not isinstance(value, list) or any(not _is_sha256(item) for item in value):
        raise AdmissionInputError("PROTECTED_EVAL_HASH_LIST_INVALID")
    return frozenset(value)


def _load_string_allowlist(path: str | None, error_code: str) -> tuple[str, ...]:
    if path is None:
        return ()
    try:
        value = _strict_json_loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise AdmissionInputError(error_code) from exc
    if isinstance(value, Mapping):
        value = value.get("values")
    if (
        not isinstance(value, list)
        or any(not isinstance(item, str) or not item.strip() for item in value)
        or len(value) != len(set(value))
    ):
        raise AdmissionInputError(error_code)
    return tuple(sorted(value))


def _load_trusted_signers(path: str | None) -> tuple[TrustedEvidenceSigner, ...]:
    if path is None:
        return ()
    try:
        value = _strict_json_loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
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
        "purposes",
        "subject_id",
    }
    for item in value["signers"]:
        if not isinstance(item, Mapping) or set(item) != required:
            raise AdmissionInputError("TRUST_STORE_SIGNER_INVALID")
        try:
            normalized = dict(item)
            purposes = normalized.get("purposes")
            if not isinstance(purposes, list) or any(
                not isinstance(purpose, str) for purpose in purposes
            ):
                raise AdmissionInputError("TRUST_STORE_SIGNER_PURPOSES_INVALID")
            normalized["purposes"] = tuple(purposes)
            signers.append(TrustedEvidenceSigner(**normalized))
        except TypeError as exc:
            raise AdmissionInputError("TRUST_STORE_SIGNER_INVALID") from exc
    return tuple(signers)


def _load_root_signer(path: str | None) -> TrustedEvidenceSigner | None:
    if path is None:
        return None
    signers = _load_trusted_signers(path)
    if len(signers) != 1 or signers[0].purposes != (PURPOSE_POLICY_ROOT,):
        raise AdmissionInputError("POLICY_ROOT_SIGNER_FILE_INVALID")
    return signers[0]


def _load_evidence_descriptor(path: str | None, error_code: str) -> Mapping[str, str] | None:
    if path is None:
        return None
    try:
        value = _strict_json_loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
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
    parser.add_argument("--expected-split-ledger-evidence-sha256")
    parser.add_argument("--reviewer-allowlist")
    parser.add_argument("--policy-root-signer")
    parser.add_argument("--policy-bundle-evidence")
    parser.add_argument("--artifact-signer-key-id")
    parser.add_argument("--artifact-signing-private-key")
    parser.add_argument(
        "--enable-train-admission",
        action="store_true",
        help=(
            "Permit otherwise fully admitted TRAIN rows to become gradient-eligible; "
            "disabled by default."
        ),
    )
    args = parser.parse_args(argv)
    try:
        policy = AdmissionPolicy(
            as_of_utc=args.as_of_utc,
            evidence_root=args.evidence_root,
            max_age_days=args.max_age_days,
            allowed_reviewers=_load_string_allowlist(
                args.reviewer_allowlist, "REVIEWER_ALLOWLIST_FILE_INVALID"
            ),
            enable_train_admission=args.enable_train_admission,
            protected_eval_content_sha256=_load_protected_hashes(
                args.protected_eval_hashes
            ),
            trusted_evidence_signers=_load_trusted_signers(args.trust_store),
            split_ledger_evidence=_load_evidence_descriptor(
                args.split_ledger_evidence,
                "SPLIT_LEDGER_EVIDENCE_DESCRIPTOR_FILE_INVALID",
            ),
            expected_split_ledger_evidence_sha256=(
                args.expected_split_ledger_evidence_sha256
            ),
            policy_root_signer=_load_root_signer(args.policy_root_signer),
            policy_bundle_evidence=_load_evidence_descriptor(
                args.policy_bundle_evidence,
                "POLICY_BUNDLE_EVIDENCE_DESCRIPTOR_FILE_INVALID",
            ),
            artifact_signer_key_id=args.artifact_signer_key_id,
        )
        artifact_signing_key = (
            ArtifactSigningKey(
                signer_key_id=str(args.artifact_signer_key_id),
                private_key_path=str(args.artifact_signing_private_key),
            )
            if args.artifact_signing_private_key
            and args.artifact_signer_key_id
            else None
        )
        report = admit_file(
            args.input,
            args.output_dir,
            policy,
            artifact_signing_key=artifact_signing_key,
        )
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
                "artifact_manifest_sha256": sha256_file(
                    pathlib.Path(args.output_dir) / "admission-manifest.json"
                ),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
