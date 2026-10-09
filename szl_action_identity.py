# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Restricted JSON identity for one logical action.

This is a local encoding shared with the reference tests. It is not RFC 8785.
It does not grant dispatch, deduplicate a ledger, or check current rights.
Floats are rejected so a decimal quantity needs an explicit typed representation.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass

ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")
MAX_SAFE_INT = 2**53 - 1
MAX_BYTES = 1_000_000


def require_id(value: object) -> str:
    if type(value) is not str or ID.fullmatch(value) is None:
        raise ValueError("Expected a nonempty bounded ASCII identifier")
    return value


def validate_json(value: object, depth: int = 0) -> None:
    if depth > 32:
        raise ValueError("JSON nesting exceeds reference limit")
    if value is None or type(value) is bool:
        return
    if type(value) is int:
        if abs(value) > MAX_SAFE_INT:
            raise ValueError("Integer outside shared exact-integer range")
        return
    if type(value) is str:
        if any(0xD800 <= ord(ch) <= 0xDFFF for ch in value):
            raise ValueError("Surrogate codepoint rejected")
        if len(value) > MAX_BYTES:
            raise ValueError("String too large")
        return
    if type(value) is list:
        if len(value) > 10000:
            raise ValueError("List too large")
        for item in value:
            validate_json(item, depth + 1)
        return
    if type(value) is dict:
        if len(value) > 10000:
            raise ValueError("Object too large")
        for key, item in value.items():
            if type(key) is not str or not key.isascii():
                raise ValueError("Object keys must be ASCII strings")
            validate_json(key, depth + 1)
            validate_json(item, depth + 1)
        return
    raise ValueError("Unsupported JSON type; floats are intentionally rejected")


def canonical(value: object) -> bytes:
    validate_json(value)
    encoded = json.dumps(
        value, ensure_ascii=True, allow_nan=False,
        sort_keys=True, separators=(",", ":")
    ).encode("ascii")
    if len(encoded) > MAX_BYTES:
        raise ValueError("Encoded object too large")
    return encoded


def digest(value: object) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def logical_document(tenant_id: str, run_id: str, step_id: str) -> dict:
    for item in (tenant_id, run_id, step_id):
        require_id(item)
    return {
        "schema": "szl.logical-action/v1",
        "tenant_id": tenant_id,
        "run_id": run_id,
        "step_id": step_id,
    }


def logical_digest(tenant_id: str, run_id: str, step_id: str) -> str:
    return digest(logical_document(tenant_id, run_id, step_id))


@dataclass(frozen=True)
class ActionIdentity:
    logical_id: str
    semantics_digest: str


def identity(
    *,
    tenant_id: str,
    run_id: str,
    step_id: str,
    plan_revision: str,
    operation: str,
    destination: str,
    arguments: object,
    execution_options: dict,
) -> ActionIdentity:
    for item in (
        tenant_id, run_id, step_id, plan_revision, operation, destination
    ):
        require_id(item)
    if type(execution_options) is not dict:
        raise ValueError("execution_options must be an explicit object")
    # Every dispatch option the caller applies belongs in execution_options.
    # This function does not infer sandbox, profile, model, or authority.
    logical = logical_document(tenant_id, run_id, step_id)
    semantics = {
        "schema": "szl.action-semantics/v1",
        "plan_revision": plan_revision,
        "operation": operation,
        "destination": destination,
        "arguments": arguments,
        "execution_options": execution_options,
    }
    return ActionIdentity(digest(logical), digest(semantics))


def compare(previous: ActionIdentity, incoming: ActionIdentity) -> str:
    if previous.logical_id != incoming.logical_id:
        return "DISTINCT_ACTION_REQUIRES_ADMISSION"
    if previous.semantics_digest != incoming.semantics_digest:
        return "CONFLICT_HOLD"
    # Not a completed-result assertion and never dispatch permission.
    return "REPLAY_CANDIDATE_REQUIRES_STATE_RIGHTS_AND_RESULT_CHECKS"
