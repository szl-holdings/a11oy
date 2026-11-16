#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Offline receipt observations for the provenance layer.

A matching byte digest does not prove a receipt's claims, signature, lineage,
readiness, or authority. Only a small public metadata allowlist is retained.
"""

import hashlib
import json
import math
import re
from datetime import datetime, timezone
from typing import Any, Iterable
from urllib.parse import urlsplit

from szl_evidence_graph import EvidenceEdge

BUNDLE_SCHEMA = "szl.evidence-bundle/v1"
MAX_RECEIPT_BYTES = 1024 * 1024
MAX_BUNDLE_BYTES = 1024 * 1024
MAX_BUNDLE_EDGES = 128
MAX_BYTES = MAX_RECEIPT_BYTES
MAX_EDGES = MAX_BUNDLE_EDGES


class ReceiptImportError(ValueError):
    """A receipt or bundle violates the bounded observation contract."""


_SHA = re.compile(r"^[0-9a-f]{64}$")
_REVISION = re.compile(r"^[0-9a-f]{40}$")
_SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$")
_METADATA = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,159}$")
_MODEL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,95}(?:/[A-Za-z0-9][A-Za-z0-9._-]{0,95})?$")
_TIMESTAMP = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})$"
)
_SECRET = re.compile(r"(?:^|[/:\s])(?:hf_|gh[pousr]_|github_pat_|sk-|xox[baprs]-)", re.I)
_KINDS = frozenset({"training", "evaluation"})
_STATUSES = frozenset({
    "ok", "pass", "fail", "success", "failure", "pending", "complete",
    "completed", "running", "observed", "verified", "degraded", "unavailable",
    "not_ready", "ready", "error", "blocked", "candidate", "stopped",
})
_REASON = (
    "Receipt bytes match the supplied digest; reported metadata is unverified. "
    "No signature, readiness, execution authority, or semantic claim is established."
)
_AUTHORITY = {"execution_authorized": False, "method": "offline-receipt-byte-match"}
_INVARIANTS = ("artifact-hash-match", "receipt-observation-only")
_BASE_EVIDENCE = frozenset({
    "kind", "receipt_kind", "artifact_uri", "observed_at", "integrity",
    "signature_status", "claims_verified",
})
_OPTIONAL_EVIDENCE = frozenset({
    "reported_schema", "reported_kind", "reported_verdict", "reported_status",
    "reported_model", "reported_base", "reported_adapter",
})


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in items:
        if key in result:
            raise ReceiptImportError("duplicate JSON object key")
        result[key] = value
    return result


def _nonfinite(value: str) -> float:
    raise ReceiptImportError("nonfinite JSON number")


def _float(value: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ReceiptImportError("nonfinite JSON number")
    return result


def strict_json(raw: bytes) -> Any:
    """Decode at most 1 MiB of strict JSON, including nested duplicate checks."""
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_BYTES:
        raise ReceiptImportError("JSON input must contain 1 to 1048576 bytes")
    try:
        value = json.loads(
            raw.decode("utf-8"), object_pairs_hook=_pairs,
            parse_constant=_nonfinite, parse_float=_float,
        )
        stack = [(value, 0)]
        while stack:
            item, depth = stack.pop()
            if depth > 32:
                raise ReceiptImportError("JSON nesting exceeds 32 levels")
            if isinstance(item, dict):
                stack.extend((child, depth + 1) for child in item.values())
            elif isinstance(item, list):
                stack.extend((child, depth + 1) for child in item)
        return value
    except (UnicodeError, RecursionError, OverflowError) as exc:
        raise ReceiptImportError("invalid bounded UTF-8 JSON") from exc


def _sha(value: str) -> str:
    if not isinstance(value, str) or not _SHA.fullmatch(value):
        raise ReceiptImportError("expected_sha256 must be a lowercase SHA-256 digest")
    return value


def _uri(value: str) -> str:
    if not isinstance(value, str) or len(value) > 2048:
        raise ReceiptImportError("artifact_uri must be a bounded immutable Hugging Face URL")
    if any(char.isspace() or ord(char) < 32 for char in value) or any(char in value for char in "\\%?#"):
        raise ReceiptImportError("artifact_uri contains unsupported characters")
    parsed = urlsplit(value)
    if parsed.scheme != "https" or parsed.netloc != "huggingface.co" or parsed.query or parsed.fragment:
        raise ReceiptImportError("artifact_uri must use https://huggingface.co without credentials or query")
    parts = parsed.path.split("/")[1:]
    if parts and parts[0] == "datasets":
        parts = parts[1:]
    if len(parts) < 5 or parts[2] != "resolve" or not _REVISION.fullmatch(parts[3]):
        raise ReceiptImportError("artifact_uri must resolve an exact 40-hex commit")
    if not all(_SEGMENT.fullmatch(part) and part not in {".", ".."} for part in parts[:2] + parts[4:]):
        raise ReceiptImportError("artifact_uri path is not allowed")
    return value


def _timestamp(value: str) -> str:
    if not isinstance(value, str) or not _TIMESTAMP.fullmatch(value):
        raise ReceiptImportError("observed_at must be an ISO-8601 timestamp with timezone")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    except (ValueError, OverflowError) as exc:
        raise ReceiptImportError("observed_at is invalid") from exc


def _safe_metadata(value: Any) -> bool:
    return (
        isinstance(value, str) and bool(_METADATA.fullmatch(value))
        and not _SECRET.search(value) and "PRIVATE" not in value.upper()
    )


def _metadata(receipt: dict[str, Any]) -> dict[str, str]:
    result = {}
    for field in ("schema", "kind", "verdict", "status"):
        value = receipt.get(field)
        if _safe_metadata(value) and (field in {"schema", "kind"} or value.lower() in _STATUSES):
            result["reported_" + field] = value
    for output, fields in (
        ("reported_model", ("model_id", "model_repo", "model")),
        ("reported_base", ("base_model", "base_model_id", "base")),
        ("reported_adapter", ("adapter_repo", "adapter_id", "adapter")),
    ):
        for field in fields:
            value = receipt.get(field)
            if _safe_metadata(value) and _MODEL_ID.fullmatch(value):
                result[output] = value
                break
    return result


def import_receipt(
    raw: bytes, *, expected_sha256: str, artifact_uri: str, kind: str, observed_at: str,
) -> EvidenceEdge:
    """Observe exact bytes without fetching, signing, or trusting reported claims."""
    expected_sha256 = _sha(expected_sha256)
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_BYTES:
        raise ReceiptImportError("receipt must contain 1 to 1048576 bytes")
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ReceiptImportError("receipt SHA-256 mismatch")
    receipt = strict_json(raw)
    if not isinstance(receipt, dict):
        raise ReceiptImportError("receipt JSON must be an object")
    if not isinstance(kind, str) or kind not in _KINDS:
        raise ReceiptImportError("kind must be training or evaluation")
    evidence = {
        "kind": "receipt-artifact",
        "receipt_kind": kind,
        "artifact_uri": _uri(artifact_uri),
        "observed_at": _timestamp(observed_at),
        "integrity": "SHA256_MATCH",
        "signature_status": "UNVERIFIED",
        "claims_verified": False,
        **_metadata(receipt),
    }
    return EvidenceEdge(
        subject={"kind": kind, "id": "sha256:" + expected_sha256},
        source_revision=None, artifact_sha256=expected_sha256,
        evidence=evidence, authority=_AUTHORITY,
        invariant_ids=_INVARIANTS, verdict="OBSERVED", reason=_REASON,
    )


def _receipt_edge(value: Any) -> EvidenceEdge:
    required = {
        "schema", "subject", "source_revision", "artifact_sha256", "runtime",
        "evidence", "authority", "parents", "invariant_ids", "verdict", "reason", "receipt_id",
    }
    if not isinstance(value, dict) or set(value) != required:
        raise ReceiptImportError("bundle edge fields do not match the receipt-observation profile")
    artifact = _sha(value["artifact_sha256"])
    subject = value["subject"]
    if not isinstance(subject, dict) or subject not in (
        {"kind": kind, "id": "sha256:" + artifact} for kind in _KINDS
    ):
        raise ReceiptImportError("invalid receipt subject")
    if (
        value["schema"] != "szl.evidence-edge/v1" or value["source_revision"] is not None
        or value["runtime"] != {} or value["parents"] != []
        or value["verdict"] != "OBSERVED" or value["reason"] != _REASON
        or value["authority"] != _AUTHORITY
        or value["authority"].get("execution_authorized") is not False
        or value["invariant_ids"] != sorted(_INVARIANTS)
    ):
        raise ReceiptImportError("receipt edge attempts unsupported authority, lineage, or verdict")
    evidence = value["evidence"]
    if not isinstance(evidence, dict) or not _BASE_EVIDENCE <= set(evidence) <= _BASE_EVIDENCE | _OPTIONAL_EVIDENCE:
        raise ReceiptImportError("receipt evidence contains unsupported fields")
    if (
        evidence["kind"] != "receipt-artifact"
        or evidence["receipt_kind"] != subject["kind"]
        or evidence["integrity"] != "SHA256_MATCH"
        or evidence["signature_status"] != "UNVERIFIED"
        or evidence["claims_verified"] is not False
        or _timestamp(evidence["observed_at"]) != evidence["observed_at"]
    ):
        raise ReceiptImportError("receipt evidence attempts unsupported claims")
    _uri(evidence["artifact_uri"])
    for name in _OPTIONAL_EVIDENCE & set(evidence):
        if not _safe_metadata(evidence[name]):
            raise ReceiptImportError("receipt evidence contains unsafe metadata")
        if name in {"reported_verdict", "reported_status"} and evidence[name].lower() not in _STATUSES:
            raise ReceiptImportError("receipt evidence contains unsupported reported status")
        if name in {"reported_model", "reported_base", "reported_adapter"} and not _MODEL_ID.fullmatch(evidence[name]):
            raise ReceiptImportError("receipt evidence contains an invalid model identifier")
    if not isinstance(value["receipt_id"], str) or not value["receipt_id"].startswith("edge-"):
        raise ReceiptImportError("bundle edge must carry its canonical receipt_id")
    edge = EvidenceEdge.from_dict(value)
    if edge.as_dict() != value:
        raise ReceiptImportError("bundle edge is not in canonical receipt form")
    return edge


def build_bundle(edges: Iterable[EvidenceEdge]) -> dict[str, Any]:
    """Package observations deterministically; this is not a signature or DAG proof."""
    materialized = []
    for edge in edges:
        if len(materialized) >= MAX_EDGES:
            raise ReceiptImportError("bundle exceeds 128 receipt edges")
        if not isinstance(edge, EvidenceEdge):
            raise ReceiptImportError("bundle inputs must be EvidenceEdge objects")
        materialized.append(_receipt_edge(edge.as_dict()).as_dict())
    ordered = sorted({edge["receipt_id"]: edge for edge in materialized}.values(), key=lambda item: item["receipt_id"])
    unsigned = {"schema": BUNDLE_SCHEMA, "signature_status": "UNSIGNED", "edges": ordered}
    bundle = {**unsigned, "digest_sha256": _digest(unsigned)}
    if len(_canonical(bundle)) > MAX_BYTES:
        raise ReceiptImportError("bundle exceeds 1048576 bytes")
    return bundle


def decode_bundle(raw: bytes) -> list[EvidenceEdge]:
    """Validate bundle bytes and observation profile, without authenticating claims."""
    bundle = strict_json(raw)
    if not isinstance(bundle, dict) or set(bundle) != {"schema", "signature_status", "edges", "digest_sha256"}:
        raise ReceiptImportError("unsupported evidence bundle fields")
    if bundle["schema"] != BUNDLE_SCHEMA or bundle["signature_status"] != "UNSIGNED":
        raise ReceiptImportError("unsupported bundle schema or signature claim")
    if not isinstance(bundle["edges"], list) or len(bundle["edges"]) > MAX_EDGES:
        raise ReceiptImportError("bundle exceeds 128 receipt edges")
    unsigned = {key: bundle[key] for key in ("schema", "signature_status", "edges")}
    if _sha(bundle["digest_sha256"]) != _digest(unsigned):
        raise ReceiptImportError("bundle digest mismatch")
    edges = [_receipt_edge(value) for value in bundle["edges"]]
    ids = [edge.receipt_id for edge in edges]
    if ids != sorted(set(ids)):
        raise ReceiptImportError("bundle edge IDs must be unique and sorted")
    return edges
