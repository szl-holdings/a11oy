# SPDX-License-Identifier: Apache-2.0
# Signed-off-by: Codex <codex@openai.com>
"""Dependency-free structural validation for portable SZL v1 memory records.

Structural validity does not grant admission, authorization, source rights, or
cryptographic verification. Those checks belong to their separate policy gates.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


MEMORY_TYPES = {
    "WORKING",
    "EPISODIC",
    "SEMANTIC",
    "PROCEDURAL",
    "POLICY",
    "PREFERENCE",
    "RESEARCH",
    "OUTCOME",
    "NEGATIVE",
}
EPISTEMIC_STATUSES = {
    "VERIFIED",
    "SUPPORTED",
    "INFERRED",
    "HYPOTHESIS",
    "DISPUTED",
    "SUPERSEDED",
    "RETRACTED",
}
ADMISSION_POLICIES = {
    "AUTOMATIC",
    "RULE_VALIDATED",
    "HUMAN_REVIEWED",
    "EXPERIMENTAL",
    "REJECTED",
}
CLASSIFICATIONS = {"PUBLIC", "INTERNAL", "CONFIDENTIAL", "RESTRICTED", "SECRET"}
TRUST_TIERS = {"T0", "T1", "T2", "T3", "T4", "T5"}

REQUIRED_TOP_LEVEL = (
    "schema_version",
    "memory_id",
    "tenant_id",
    "scope",
    "type",
    "content",
    "provenance",
    "epistemic_state",
    "governance",
    "usage",
    "integrity",
)
REQUIRED_SCOPE = (
    "organization",
    "product",
    "repository",
    "component",
    "environment",
    "project",
    "agent",
    "session",
)

# All declared properties of these v1 objects are required. Free-form signature
# and relation objects deliberately retain the portable schema's open shape.
_V1_FIELD_TYPES = {
    "": {
        "schema_version": "string", "memory_id": "string", "tenant_id": "string",
        "scope": "object", "type": "string", "content": "object",
        "provenance": "object", "epistemic_state": "object",
        "governance": "object", "usage": "object", "integrity": "object",
    },
    "scope": dict.fromkeys(REQUIRED_SCOPE, "string"),
    "content": {
        "summary": "string", "claims": "string array", "entities": "string array",
        "relations": "object array", "procedure": "string array",
        "open_questions": "string array",
    },
    "provenance": {
        "sources": "string array", "source_digests": "string array",
        "source_revisions": "string array", "extraction_method": "string",
        "created_by": "string", "observed_at": "string", "ingested_at": "string",
        "trust_tier": "string",
    },
    "epistemic_state": {
        "status": "string", "confidence": "number", "confidence_method": "string",
        "contradiction_ids": "string array", "supersedes": "string array",
        "superseded_by": "string array",
    },
    "governance": {
        "classification": "string", "admission_policy": "string",
        "retention_policy": "string", "expires_at": "string or null",
        "human_review_required": "boolean", "allowed_consumers": "string array",
        "propagation_allowed": "boolean", "training_allowed": "boolean",
        "export_allowed": "boolean",
    },
    "usage": {
        "retrieval_count": "integer", "last_retrieved_at": "string or null",
        "successful_outcomes": "integer", "failed_outcomes": "integer",
        "measured_utility": "number",
    },
    "integrity": {
        "content_digest": "string", "previous_version_digest": "string or null",
        "signature": "object", "receipt_id": "string",
    },
}


def _matches_type(value: Any, expected: str) -> bool:
    if expected == "string or null":
        return value is None or isinstance(value, str)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    return isinstance(value, {
        "string": str, "object": dict, "boolean": bool,
        "string array": list, "object array": list,
    }[expected])


def _validate_object(value: Any, path: str, errors: list[str]) -> None:
    if not isinstance(value, dict):
        errors.append(f"{path or 'record'} must be an object")
        return
    fields = _V1_FIELD_TYPES[path]
    for field, expected in fields.items():
        name = f"{path}.{field}" if path else field
        if field not in value:
            errors.append(f"missing required field: {name}")
            continue
        member = value[field]
        if not _matches_type(member, expected):
            errors.append(f"{name} must be {expected}")
        elif expected in {"string array", "object array"}:
            item_type = str if expected == "string array" else dict
            for index, item in enumerate(member):
                if not isinstance(item, item_type):
                    errors.append(f"{name}[{index}] must be {expected.split()[0]}")
    for field in sorted(value, key=repr):
        if field not in fields:
            name = f"{path}.{field}" if path else str(field)
            errors.append(f"unknown field: {name}")


def canonical_digest(payload: dict[str, Any]) -> str:
    """Return the record digest with mutable integrity claims blanked."""

    clone = json.loads(json.dumps(payload))
    integrity = clone.get("integrity")
    if isinstance(integrity, dict):
        integrity["content_digest"] = ""
        integrity["signature"] = {}
    encoded = json.dumps(clone, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def load_schema(path: str | Path = "execution/brain/MEMORY_SCHEMA.json") -> dict[str, Any]:
    """Load the portable JSON Schema used by external validators."""

    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def validate_memory_record(record: dict[str, Any]) -> list[str]:
    """Return deterministic v1 structural errors for any input shape.

    An empty list means structural validity only. It does not mean admission,
    authorization, digest verification, or signature verification.
    """

    errors: list[str] = []
    if not isinstance(record, dict):
        return ["record must be an object"]
    if "schema_version" in record and record["schema_version"] != "szl-memory/1.0":
        return ["unsupported schema_version: only szl-memory/1.0 is supported"]
    _validate_object(record, "", errors)
    for path in _V1_FIELD_TYPES:
        if path and path in record:
            _validate_object(record[path], path, errors)
    if errors:
        return errors

    if len(record["memory_id"]) < 12:
        errors.append("memory_id must contain at least 12 characters")
    if not record["tenant_id"].strip():
        errors.append("tenant_id must be a non-empty string")

    scope = record["scope"]
    for field in REQUIRED_SCOPE:
        if not scope[field].strip():
            errors.append(f"scope.{field} must be a non-empty string")

    memory_type = record["type"]
    if memory_type not in MEMORY_TYPES:
        errors.append(f"type must be one of {sorted(MEMORY_TYPES)}")

    content = record["content"]
    if not content["summary"].strip():
        errors.append("content.summary must be a non-empty string")

    provenance = record["provenance"]
    if not provenance["sources"]:
        errors.append("provenance.sources must contain at least one source")
    for field in ("extraction_method", "created_by"):
        if not provenance[field]:
            errors.append(f"provenance.{field} must be a non-empty string")
    if provenance.get("trust_tier") not in TRUST_TIERS:
        errors.append(f"provenance.trust_tier must be one of {sorted(TRUST_TIERS)}")

    epistemic = record["epistemic_state"]
    if epistemic.get("status") not in EPISTEMIC_STATUSES:
        errors.append(f"epistemic_state.status must be one of {sorted(EPISTEMIC_STATUSES)}")
    confidence = epistemic.get("confidence")
    if not 0 <= confidence <= 1:
        errors.append("epistemic_state.confidence must be a number from 0 through 1")

    governance = record["governance"]
    if governance.get("classification") not in CLASSIFICATIONS:
        errors.append(f"governance.classification must be one of {sorted(CLASSIFICATIONS)}")
    if governance.get("admission_policy") not in ADMISSION_POLICIES:
        errors.append(f"governance.admission_policy must be one of {sorted(ADMISSION_POLICIES)}")
    if not governance["retention_policy"]:
        errors.append("governance.retention_policy must be a non-empty string")
    if governance.get("classification") in {"RESTRICTED", "SECRET"} and not governance.get("allowed_consumers"):
        errors.append("restricted memory requires governance.allowed_consumers")
    if governance.get("training_allowed") and (
        governance.get("admission_policy") != "HUMAN_REVIEWED"
        or governance.get("human_review_required") is not True
    ):
        errors.append("training_allowed requires HUMAN_REVIEWED admission")
    if governance.get("propagation_allowed") and memory_type == "WORKING":
        errors.append("WORKING memory cannot propagate across ecosystem boundaries")

    usage = record["usage"]
    for field in ("retrieval_count", "successful_outcomes", "failed_outcomes"):
        value = usage.get(field)
        if value < 0:
            errors.append(f"usage.{field} must be a non-negative integer")
    utility = usage.get("measured_utility")
    if not -1 <= utility <= 1:
        errors.append("usage.measured_utility must be a number from -1 through 1")

    integrity = record["integrity"]
    digest = integrity.get("content_digest")
    if len(digest) != 64:
        errors.append("integrity.content_digest must be a 64-character SHA-256 digest")
    return errors


def build_example_memory() -> dict[str, Any]:
    """Build a valid, public, non-training demonstration record."""

    record: dict[str, Any] = {
        "schema_version": "szl-memory/1.0",
        "memory_id": "mem_demo_000001",
        "tenant_id": "szl-holdings",
        "scope": {
            "organization": "szl-holdings",
            "product": "a11oy",
            "component": "brain-quantum-evidence",
            "project": "a11oy",
            "repository": "szl-holdings/a11oy",
            "environment": "demonstration",
            "agent": "szl-verifier",
            "session": "demo-session",
        },
        "type": "RESEARCH",
        "content": {
            "summary": "The brain capability endpoint returned a governed manifest.",
            "claims": ["The endpoint returned a typed manifest."],
            "entities": ["a11oy", "brain-capabilities"],
            "relations": [{"subject": "a11oy", "predicate": "exposes", "object": "brain-capabilities"}],
            "procedure": ["GET the endpoint", "validate the schema"],
            "open_questions": ["Has the branch been deployed?"],
        },
        "provenance": {
            "sources": ["/api/a11oy/v1/brain/capabilities"],
            "source_digests": [],
            "source_revisions": ["demonstration"],
            "extraction_method": "deterministic HTTP observation",
            "created_by": "szl-verifier",
            "observed_at": "2026-07-21T00:00:00Z",
            "ingested_at": "2026-07-21T00:00:00Z",
            "trust_tier": "T2",
        },
        "epistemic_state": {
            "status": "VERIFIED",
            "confidence": 1.0,
            "confidence_method": "deterministic contract validation",
            "contradiction_ids": [],
            "supersedes": [],
            "superseded_by": [],
        },
        "governance": {
            "classification": "PUBLIC",
            "admission_policy": "RULE_VALIDATED",
            "retention_policy": "30_DAY_DEMO",
            "expires_at": "2026-08-20T00:00:00Z",
            "human_review_required": False,
            "allowed_consumers": ["public"],
            "propagation_allowed": True,
            "training_allowed": False,
            "export_allowed": True,
        },
        "usage": {
            "retrieval_count": 0,
            "last_retrieved_at": None,
            "successful_outcomes": 0,
            "failed_outcomes": 0,
            "measured_utility": 0.0,
        },
        "integrity": {
            "content_digest": "",
            "previous_version_digest": None,
            "signature": {},
            "receipt_id": "demo-unminted",
        },
    }
    record["integrity"]["content_digest"] = canonical_digest(record)
    return record
