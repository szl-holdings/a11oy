# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Proof-carrying Trace IR for governed GenAI and MCP workflows.

This module is intentionally additive and authority-neutral. It creates a
deterministic, redacted event envelope that can be exported through OpenTelemetry
or attached to a Khipu receipt. It never authorizes an action.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from typing import Any

from .genai import redact

TRACE_IR_SCHEMA = "szl.trace-ir/v1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_STATUSES = frozenset({"STARTED", "SUCCEEDED", "FAILED", "ABSTAINED", "BLOCKED", "CANCELLED"})


def canonical_sha256(value: Any) -> str:
    """Hash a JSON-compatible value using a cross-language canonical form."""
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _require_hash(value: str | None, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise ValueError(f"{field} must be a lowercase SHA-256 hex digest")
    return value


def trace_event(
    *,
    trace_id: str,
    span_id: str,
    operation: str,
    status: str,
    actor: str = "a11oy",
    parent_span_id: str | None = None,
    input_hash: str | None = None,
    result_hash: str | None = None,
    model_hash: str | None = None,
    adapter_hash: str | None = None,
    dataset_version: str | None = None,
    invariant_set: tuple[str, ...] | list[str] = (),
    energy: Mapping[str, Any] | None = None,
    attributes: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build one deterministic, redacted trace event.

    The event carries enough identity to join model/tool/MCP actions to a
    receipt, dataset, invariant set, and measured energy record. The returned
    authorization effect is always NONE: telemetry cannot authorize.
    """
    if not trace_id or not span_id or not operation or not actor:
        raise ValueError("trace_id, span_id, operation, and actor are required")
    if status not in _STATUSES:
        raise ValueError(f"unsupported status: {status}")
    if parent_span_id == span_id:
        raise ValueError("span cannot be its own parent")
    invariants = tuple(sorted({str(item) for item in invariant_set if str(item)}))
    event = {
        "schema": TRACE_IR_SCHEMA,
        "trace_id": trace_id,
        "span_id": span_id,
        "parent_span_id": parent_span_id,
        "operation": operation,
        "actor": actor,
        "status": status,
        "input_sha256": _require_hash(input_hash, "input_hash"),
        "result_sha256": _require_hash(result_hash, "result_hash"),
        "model_sha256": _require_hash(model_hash, "model_hash"),
        "adapter_sha256": _require_hash(adapter_hash, "adapter_hash"),
        "dataset_version": dataset_version,
        "invariant_set": list(invariants),
        "energy": redact(dict(energy or {})),
        "attributes": redact(dict(attributes or {})),
        "authorization": {"effect": "NONE"},
    }
    event["event_sha256"] = canonical_sha256(
        {key: value for key, value in event.items() if key != "event_sha256"}
    )
    return event


def gated_minimum(
    scores: Mapping[str, float],
    *,
    threshold: float = 1.0,
    critical_failures: tuple[str, ...] | list[str] = (),
) -> dict[str, Any]:
    """Release only when every required score clears the threshold.

    A high average cannot hide a failed critical invariant. Empty score sets
    and non-finite values hold by construction.
    """
    normalized = {str(key): float(value) for key, value in scores.items()}
    failures = sorted({str(item) for item in critical_failures if str(item)})
    finite = all(value == value and abs(value) != float("inf") for value in normalized.values())
    below = sorted(key for key, value in normalized.items() if value < threshold)
    passed = bool(normalized) and finite and not below and not failures
    return {
        "schema": "szl.gated-minimum/v1",
        "verdict": "PASS" if passed else "HOLD",
        "threshold": threshold,
        "scores": normalized,
        "minimum": min(normalized.values()) if normalized else None,
        "below_threshold": below,
        "critical_failures": failures,
        "authorization_effect": "NONE",
    }
