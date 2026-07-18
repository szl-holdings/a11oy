# SPDX-License-Identifier: Apache-2.0
"""Offline, fail-closed assembly of signed Brain row evidence.

This module does one deliberately narrow job: join the immutable M1 Brain
ledger to a DSSE-signed evidence index on the exact
``(node_id, content_sha256)`` key. It does not scrape, infer evidence, approve
rights, admit training rows, sign receipts, train, publish, or promote.

The output candidate JSONL is input for ``szl_brain_training_admission.py``;
it is not itself an admission decision. Every M1 row without a signed evidence
entry is emitted to a content-free gap queue.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import copy
import hashlib
import json
import os
import pathlib
import re
import stat
import tempfile
from datetime import datetime
from typing import Any, Mapping, Sequence


EXPECTED_LEDGER_ROWS = 9_464
LEDGER_SCHEMA = "szl.m1-brain-ingest-decision/v1"
INDEX_SCHEMA = "szl.brain-row-evidence-index.v1"
EVIDENCE_ROW_SCHEMA = "szl.brain-row-evidence.v1"
CANDIDATE_SCHEMA = "szl.brain-training-candidate.v2"
GAP_SCHEMA = "szl.brain-row-evidence-gap.v1"
MANIFEST_SCHEMA = "szl.brain-row-evidence-assembly-manifest.v1"
PAYLOAD_TYPE = "application/vnd.szl.brain-row-evidence-index.v1+json"

MAX_LEDGER_BYTES = 128 * 1024 * 1024
MAX_LEDGER_LINE_BYTES = 256 * 1024
MAX_INDEX_BYTES = 64 * 1024 * 1024
MAX_CONTENT_BYTES = 65_536
MAX_EVIDENCE_ROWS = EXPECTED_LEDGER_ROWS

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_REVISION_RE = re.compile(r"^(?:git:[0-9a-f]{40,64}|sha256:[0-9a-f]{64})$")

_INDEX_FIELDS = {
    "schema_version",
    "source_ledger_sha256",
    "generated_at_utc",
    "rows",
}
_ROW_FIELDS = {
    "schema_version",
    "node_id",
    "content_sha256",
    "source",
    "rights",
    "privacy",
    "contamination",
    "review",
    "split",
}
_SOURCE_FIELDS = {"identity", "uri", "revision", "timestamp_utc", "evidence"}
_RIGHTS_FIELDS = {
    "author",
    "rightsholder",
    "basis",
    "license",
    "permission_scope",
    "evidence",
}
_PRIVACY_FIELDS = {"classification", "pii_result", "method", "evidence"}
_CONTAMINATION_FIELDS = {"result", "method", "checked_against", "evidence"}
_REVIEW_FIELDS = {"state", "reviewer", "reviewed_at_utc", "reasons", "evidence"}
_EVIDENCE_FIELDS = {"path", "sha256"}


class AssemblyRefused(RuntimeError):
    """Raised when any fail-closed assembly invariant is not satisfied."""


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _opaque_row_key(node_id: str, content_sha256: str) -> str:
    return _sha256_bytes(
        b"szl.brain-row-evidence-key.v1\0"
        + _canonical_bytes(
            {"node_id": node_id, "content_sha256": content_sha256}
        )
    )


def _no_duplicate_object(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise AssemblyRefused(f"duplicate JSON object key: {key}")
        out[key] = value
    return out


def _strict_json_loads(data: str | bytes, label: str) -> Any:
    try:
        return json.loads(data, object_pairs_hook=_no_duplicate_object)
    except AssemblyRefused:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AssemblyRefused(f"{label} is not strict UTF-8 JSON") from exc


def _read_stable_regular_file(
    path: pathlib.Path, max_bytes: int, label: str
) -> bytes:
    """Read once and reject path/descriptor mutation around that exact read."""

    try:
        path_before = path.lstat()
    except OSError as exc:
        raise AssemblyRefused(f"{label} is not readable") from exc
    if stat.S_ISLNK(path_before.st_mode) or not stat.S_ISREG(path_before.st_mode):
        raise AssemblyRefused(f"{label} must be a regular, non-symlink file")
    if path_before.st_size <= 0 or path_before.st_size > max_bytes:
        raise AssemblyRefused(f"{label} size is outside the bounded policy")
    try:
        with path.open("rb") as handle:
            descriptor_before = os.fstat(handle.fileno())
            data = handle.read(max_bytes + 1)
            descriptor_after = os.fstat(handle.fileno())
        path_after = path.lstat()
    except OSError as exc:
        raise AssemblyRefused(f"{label} changed while it was read") from exc
    identity = lambda value: (
        value.st_dev,
        value.st_ino,
        value.st_size,
        value.st_mtime_ns,
    )
    if (
        identity(path_before) != identity(descriptor_before)
        or identity(descriptor_before) != identity(descriptor_after)
        or identity(descriptor_after) != identity(path_after)
        or len(data) != descriptor_after.st_size
        or not data
        or len(data) > max_bytes
    ):
        raise AssemblyRefused(f"{label} changed while it was read")
    return data


def _require_exact_fields(value: Any, fields: set[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != fields:
        raise AssemblyRefused(f"{label} fields are not exact")
    return value


def _require_text(value: Any, label: str, *, maximum: int = 4096) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > maximum
        or any(ord(character) < 32 for character in value)
    ):
        raise AssemblyRefused(f"{label} is not a bounded non-empty string")
    return value


def _require_sha256(value: Any, label: str) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise AssemblyRefused(f"{label} is not a lowercase SHA-256")
    return value


def _require_timestamp(value: Any, label: str) -> str:
    text = _require_text(value, label, maximum=64)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AssemblyRefused(f"{label} is not an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise AssemblyRefused(f"{label} must carry an explicit timezone")
    return text


def _validate_evidence_descriptor(value: Any, label: str) -> None:
    descriptor = _require_exact_fields(value, _EVIDENCE_FIELDS, label)
    path_text = _require_text(descriptor["path"], f"{label}.path")
    path = pathlib.PurePosixPath(path_text.replace("\\", "/"))
    if path.is_absolute() or ".." in path.parts or "." in path.parts:
        raise AssemblyRefused(f"{label}.path must be a normalized relative path")
    _require_sha256(descriptor["sha256"], f"{label}.sha256")


def _validate_unique_text_list(
    value: Any, label: str, *, minimum: int = 0, maximum: int = 64
) -> None:
    if not isinstance(value, list) or not minimum <= len(value) <= maximum:
        raise AssemblyRefused(f"{label} has an invalid cardinality")
    normalized: list[str] = []
    for index, item in enumerate(value):
        normalized.append(_require_text(item, f"{label}[{index}]", maximum=256))
    if len(set(normalized)) != len(normalized):
        raise AssemblyRefused(f"{label} contains duplicates")


def _validate_evidence_row(raw: Any, index: int) -> tuple[str, str]:
    label = f"evidence.rows[{index}]"
    row = _require_exact_fields(raw, _ROW_FIELDS, label)
    if row["schema_version"] != EVIDENCE_ROW_SCHEMA:
        raise AssemblyRefused(f"{label}.schema_version is unsupported")
    node_id = _require_text(row["node_id"], f"{label}.node_id", maximum=256)
    content_sha = _require_sha256(row["content_sha256"], f"{label}.content_sha256")

    source = _require_exact_fields(row["source"], _SOURCE_FIELDS, f"{label}.source")
    _require_text(source["identity"], f"{label}.source.identity", maximum=256)
    _require_text(source["uri"], f"{label}.source.uri", maximum=2048)
    revision = _require_text(source["revision"], f"{label}.source.revision", maximum=80)
    if _REVISION_RE.fullmatch(revision) is None:
        raise AssemblyRefused(f"{label}.source.revision is not immutable")
    _require_timestamp(source["timestamp_utc"], f"{label}.source.timestamp_utc")
    _validate_evidence_descriptor(source["evidence"], f"{label}.source.evidence")

    rights = _require_exact_fields(row["rights"], _RIGHTS_FIELDS, f"{label}.rights")
    for field in ("author", "rightsholder", "basis", "license", "permission_scope"):
        _require_text(rights[field], f"{label}.rights.{field}", maximum=256)
    _validate_evidence_descriptor(rights["evidence"], f"{label}.rights.evidence")

    privacy = _require_exact_fields(row["privacy"], _PRIVACY_FIELDS, f"{label}.privacy")
    _require_text(privacy["classification"], f"{label}.privacy.classification", maximum=64)
    if privacy["pii_result"] not in {"CLEAR", "DETECTED", "UNKNOWN"}:
        raise AssemblyRefused(f"{label}.privacy.pii_result is unsupported")
    _require_text(privacy["method"], f"{label}.privacy.method", maximum=128)
    _validate_evidence_descriptor(privacy["evidence"], f"{label}.privacy.evidence")

    contamination = _require_exact_fields(
        row["contamination"], _CONTAMINATION_FIELDS, f"{label}.contamination"
    )
    if contamination["result"] not in {"CLEAR", "DETECTED", "UNKNOWN"}:
        raise AssemblyRefused(f"{label}.contamination.result is unsupported")
    _require_text(contamination["method"], f"{label}.contamination.method", maximum=128)
    _validate_unique_text_list(
        contamination["checked_against"],
        f"{label}.contamination.checked_against",
        minimum=1,
    )
    _validate_evidence_descriptor(
        contamination["evidence"], f"{label}.contamination.evidence"
    )

    review = _require_exact_fields(row["review"], _REVIEW_FIELDS, f"{label}.review")
    if review["state"] not in {"APPROVED", "REJECTED", "NEEDS_REVIEW"}:
        raise AssemblyRefused(f"{label}.review.state is unsupported")
    _require_text(review["reviewer"], f"{label}.review.reviewer", maximum=256)
    _require_timestamp(review["reviewed_at_utc"], f"{label}.review.reviewed_at_utc")
    _validate_unique_text_list(review["reasons"], f"{label}.review.reasons")
    _validate_evidence_descriptor(review["evidence"], f"{label}.review.evidence")

    if row["split"] not in {"TRAIN", "EVAL"}:
        raise AssemblyRefused(f"{label}.split is unsupported")
    return node_id, content_sha


def _load_ledger(
    path: pathlib.Path, expected_rows: int
) -> tuple[list[dict[str, Any]], str]:
    ledger_bytes = _read_stable_regular_file(path, MAX_LEDGER_BYTES, "M1 ledger")
    digest = _sha256_bytes(ledger_bytes)
    rows: list[dict[str, Any]] = []
    keys: set[tuple[str, str]] = set()
    node_ids: set[str] = set()
    for line_number, raw_line in enumerate(ledger_bytes.splitlines(keepends=True), 1):
        if not raw_line.endswith(b"\n"):
            raise AssemblyRefused(f"M1 ledger line {line_number} lacks a terminal newline")
        if len(raw_line) > MAX_LEDGER_LINE_BYTES:
            raise AssemblyRefused(f"M1 ledger line {line_number} is oversized")
        if not raw_line.strip():
            raise AssemblyRefused(f"M1 ledger line {line_number} is blank")
        raw = _strict_json_loads(raw_line, f"M1 ledger line {line_number}")
        if not isinstance(raw, dict) or raw.get("schema") != LEDGER_SCHEMA:
            raise AssemblyRefused(f"M1 ledger line {line_number} has an unsupported schema")
        node_id = _require_text(raw.get("node_id"), f"M1 ledger line {line_number}.node_id", maximum=256)
        content = raw.get("canonical_text")
        if not isinstance(content, str) or not content or len(content.encode("utf-8")) > MAX_CONTENT_BYTES:
            raise AssemblyRefused(f"M1 ledger line {line_number}.canonical_text is invalid")
        content_sha = _require_sha256(
            raw.get("canonical_text_sha256"),
            f"M1 ledger line {line_number}.canonical_text_sha256",
        )
        if _sha256_bytes(content.encode("utf-8")) != content_sha:
            raise AssemblyRefused(f"M1 ledger line {line_number} content hash mismatch")
        key = (node_id, content_sha)
        if key in keys or node_id in node_ids:
            raise AssemblyRefused(f"M1 ledger line {line_number} duplicates a row key")
        keys.add(key)
        node_ids.add(node_id)
        rows.append({"node_id": node_id, "content_sha256": content_sha, "content": content})
    if len(rows) != expected_rows:
        raise AssemblyRefused(
            f"M1 ledger row count is {len(rows)}, expected exactly {expected_rows}"
        )
    return rows, digest


def _pae(payload_type: str, payload: bytes) -> bytes:
    encoded_type = payload_type.encode("utf-8")
    return (
        b"DSSEv1 "
        + str(len(encoded_type)).encode("ascii")
        + b" "
        + encoded_type
        + b" "
        + str(len(payload)).encode("ascii")
        + b" "
        + payload
    )


def _verify_signed_index(
    index_path: pathlib.Path,
    public_key_path: pathlib.Path,
    expected_keyid: str,
    ledger_sha256: str,
) -> tuple[dict[tuple[str, str], dict[str, Any]], dict[str, Any]]:
    index_bytes = _read_stable_regular_file(
        index_path, MAX_INDEX_BYTES, "signed evidence index"
    )
    public_key_bytes = _read_stable_regular_file(
        public_key_path, 64 * 1024, "evidence public key"
    )
    expected_keyid = _require_text(expected_keyid, "expected keyid", maximum=256)
    envelope = _strict_json_loads(index_bytes, "signed evidence index")
    envelope = _require_exact_fields(
        envelope, {"payloadType", "payload", "signatures"}, "signed evidence index envelope"
    )
    if envelope["payloadType"] != PAYLOAD_TYPE:
        raise AssemblyRefused("signed evidence index payload type mismatch")
    signatures = envelope["signatures"]
    if not isinstance(signatures, list) or len(signatures) != 1:
        raise AssemblyRefused("signed evidence index must carry exactly one signature")
    signature = _require_exact_fields(signatures[0], {"keyid", "sig"}, "index signature")
    if signature["keyid"] != expected_keyid:
        raise AssemblyRefused("signed evidence index keyid mismatch")
    try:
        payload_bytes = base64.b64decode(envelope["payload"], validate=True)
        signature_bytes = base64.b64decode(signature["sig"], validate=True)
    except (TypeError, ValueError, binascii.Error) as exc:
        raise AssemblyRefused("signed evidence index has invalid base64") from exc
    if not payload_bytes or len(payload_bytes) > MAX_INDEX_BYTES or not signature_bytes:
        raise AssemblyRefused("signed evidence index payload/signature is empty or oversized")

    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import ec
    except ImportError as exc:
        raise AssemblyRefused("cryptography is required for signed evidence verification") from exc
    try:
        public_key = serialization.load_pem_public_key(public_key_bytes)
    except (TypeError, ValueError) as exc:
        raise AssemblyRefused("evidence public key is invalid") from exc
    if not isinstance(public_key, ec.EllipticCurvePublicKey) or not isinstance(
        public_key.curve, ec.SECP256R1
    ):
        raise AssemblyRefused("evidence public key must be ECDSA P-256")
    try:
        public_key.verify(
            signature_bytes,
            _pae(PAYLOAD_TYPE, payload_bytes),
            ec.ECDSA(hashes.SHA256()),
        )
    except InvalidSignature as exc:
        raise AssemblyRefused("signed evidence index signature did not verify") from exc

    payload = _strict_json_loads(payload_bytes, "signed evidence index payload")
    payload = _require_exact_fields(payload, _INDEX_FIELDS, "signed evidence index payload")
    if _canonical_bytes(payload) != payload_bytes:
        raise AssemblyRefused("signed evidence index payload is not canonical JSON")
    if payload["schema_version"] != INDEX_SCHEMA:
        raise AssemblyRefused("signed evidence index schema is unsupported")
    if _require_sha256(payload["source_ledger_sha256"], "index source ledger") != ledger_sha256:
        raise AssemblyRefused("signed evidence index is bound to a different M1 ledger")
    _require_timestamp(payload["generated_at_utc"], "index generated_at_utc")
    if not isinstance(payload["rows"], list) or len(payload["rows"]) > MAX_EVIDENCE_ROWS:
        raise AssemblyRefused("signed evidence index row count exceeds the bounded policy")

    evidence_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    evidence_node_ids: set[str] = set()
    for index, raw in enumerate(payload["rows"]):
        key = _validate_evidence_row(raw, index)
        if key in evidence_by_key or key[0] in evidence_node_ids:
            raise AssemblyRefused("signed evidence index contains a duplicate row key")
        evidence_by_key[key] = copy.deepcopy(raw)
        evidence_node_ids.add(key[0])

    public_der = public_key.public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    signature_receipt = {
        "payload_type": PAYLOAD_TYPE,
        "keyid": expected_keyid,
        "public_key_file_sha256": _sha256_bytes(public_key_bytes),
        "public_key_sha256": _sha256_bytes(public_der),
        "index_file_sha256": _sha256_bytes(index_bytes),
        "payload_sha256": _sha256_bytes(payload_bytes),
        "signature_verified": True,
        "generated_at_utc": payload["generated_at_utc"],
    }
    return evidence_by_key, signature_receipt


def _jsonl_bytes(rows: Sequence[Mapping[str, Any]]) -> bytes:
    if not rows:
        return b""
    return b"".join(_canonical_bytes(row) + b"\n" for row in rows)


def _atomic_write(path: pathlib.Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.parent.is_symlink():
        raise AssemblyRefused("output directory must not be a symlink")
    handle = tempfile.NamedTemporaryFile(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False
    )
    temporary = pathlib.Path(handle.name)
    try:
        with handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def assemble(
    ledger_path: pathlib.Path | str,
    signed_index_path: pathlib.Path | str,
    public_key_path: pathlib.Path | str,
    expected_keyid: str,
    output_dir: pathlib.Path | str,
    *,
    expected_rows: int = EXPECTED_LEDGER_ROWS,
) -> dict[str, Any]:
    """Assemble signed evidence with M1 content; never perform admission."""

    if not isinstance(expected_rows, int) or expected_rows <= 0 or expected_rows > EXPECTED_LEDGER_ROWS:
        raise AssemblyRefused("expected_rows is outside the bounded policy")
    ledger = pathlib.Path(ledger_path)
    signed_index = pathlib.Path(signed_index_path)
    public_key = pathlib.Path(public_key_path)
    output = pathlib.Path(output_dir)
    if output.exists() and (output.is_symlink() or not output.is_dir()):
        raise AssemblyRefused("output directory must be a regular directory")

    ledger_rows, ledger_sha = _load_ledger(ledger, expected_rows)
    evidence_by_key, signature_receipt = _verify_signed_index(
        signed_index, public_key, expected_keyid, ledger_sha
    )
    ledger_by_key = {
        (row["node_id"], row["content_sha256"]): row for row in ledger_rows
    }
    ledger_hash_by_node = {row["node_id"]: row["content_sha256"] for row in ledger_rows}
    for node_id, content_sha in evidence_by_key:
        if node_id in ledger_hash_by_node and ledger_hash_by_node[node_id] != content_sha:
            raise AssemblyRefused("signed evidence content hash mismatches its M1 node_id")
        if (node_id, content_sha) not in ledger_by_key:
            raise AssemblyRefused("signed evidence row key is absent from the M1 ledger")

    candidates: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    for key in sorted(ledger_by_key):
        ledger_row = ledger_by_key[key]
        evidence = evidence_by_key.get(key)
        if evidence is None:
            gaps.append(
                {
                    "schema_version": GAP_SCHEMA,
                    "row_key_sha256": _opaque_row_key(key[0], key[1]),
                    "missing_evidence": ["SIGNED_ROW_EVIDENCE"],
                }
            )
            continue
        candidates.append(
            {
                "schema_version": CANDIDATE_SCHEMA,
                "node_id": key[0],
                "content": ledger_row["content"],
                "content_sha256": key[1],
                "source": copy.deepcopy(evidence["source"]),
                "rights": copy.deepcopy(evidence["rights"]),
                "privacy": copy.deepcopy(evidence["privacy"]),
                "contamination": copy.deepcopy(evidence["contamination"]),
                "review": copy.deepcopy(evidence["review"]),
                "split": evidence["split"],
            }
        )

    candidate_bytes = _jsonl_bytes(candidates)
    gap_bytes = _jsonl_bytes(gaps)
    candidate_path = output / "brain-training-candidate.v2.jsonl"
    gap_path = output / "brain-row-evidence-gap-queue.v1.jsonl"
    manifest_path = output / "brain-row-evidence-assembly-manifest.v1.json"
    _atomic_write(candidate_path, candidate_bytes)
    _atomic_write(gap_path, gap_bytes)
    manifest = {
        "schema_version": MANIFEST_SCHEMA,
        "operation": "SIGNED_EVIDENCE_ASSEMBLY_NOT_TRAINING_ADMISSION",
        "source_ledger": {
            "sha256": ledger_sha,
            "expected_rows": expected_rows,
            "observed_rows": len(ledger_rows),
        },
        "signed_evidence_index": signature_receipt,
        "outputs": {
            "candidate": {
                "path": candidate_path.name,
                "sha256": _sha256_bytes(candidate_bytes),
                "rows": len(candidates),
                "state": "UNADMITTED_CANDIDATES",
            },
            "gap_queue": {
                "path": gap_path.name,
                "sha256": _sha256_bytes(gap_bytes),
                "rows": len(gaps),
                "content_policy": "OPAQUE_ROW_KEY_AND_GAP_CODES_ONLY",
            },
        },
        "coverage": {
            "signed_evidence_rows": len(evidence_by_key),
            "candidate_rows": len(candidates),
            "gap_rows": len(gaps),
            "complete_partition": len(candidates) + len(gaps) == len(ledger_rows),
        },
        "non_claims": [
            "NO_RIGHTS_OR_LICENSE_INFERENCE",
            "NO_PRIVACY_OR_REVIEWER_INFERENCE",
            "NO_TRAINING_ADMISSION",
            "NO_TRAINING_OR_MODEL_PROMOTION",
        ],
    }
    _atomic_write(manifest_path, _canonical_bytes(manifest) + b"\n")
    return manifest


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ledger", default="model_release/m1/brain-ingest-ledger.jsonl"
    )
    parser.add_argument("--signed-evidence-index", required=True)
    parser.add_argument("--public-key", required=True)
    parser.add_argument("--expected-keyid", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)
    try:
        manifest = assemble(
            args.ledger,
            args.signed_evidence_index,
            args.public_key,
            args.expected_keyid,
            args.output_dir,
            expected_rows=EXPECTED_LEDGER_ROWS,
        )
    except AssemblyRefused as exc:
        parser.exit(2, f"REFUSED: {exc}\n")
    print(json.dumps(manifest, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
