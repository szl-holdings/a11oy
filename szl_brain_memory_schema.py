# SPDX-License-Identifier: Apache-2.0
# Signed-off-by: Codex <codex@openai.com>
"""Executable validation helpers for governed SZL memory records.

The validator is dependency-free so ingestion and test surfaces can enforce the
same minimum contract before a dedicated JSON Schema library is installed.
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
    """Return deterministic validation errors; an empty list means admitted."""

    errors: list[str] = []
    for field in REQUIRED_TOP_LEVEL:
        if field not in record:
            errors.append(f"missing required field: {field}")
    if errors:
        return errors

    if record.get("schema_version") != "szl-memory/1.0":
        errors.append("schema_version must equal szl-memory/1.0")
    if not isinstance(record.get("tenant_id"), str) or not record["tenant_id"].strip():
        errors.append("tenant_id must be a non-empty string")

    scope = record.get("scope", {})
    for field in REQUIRED_SCOPE:
        if not isinstance(scope.get(field), str) or not scope[field].strip():
            errors.append(f"scope.{field} must be a non-empty string")

    memory_type = record.get("type")
    if memory_type not in MEMORY_TYPES:
        errors.append(f"type must be one of {sorted(MEMORY_TYPES)}")

    content = record.get("content", {})
    if not isinstance(content.get("summary"), str) or not content["summary"].strip():
        errors.append("content.summary must be a non-empty string")

    provenance = record.get("provenance", {})
    if not isinstance(provenance.get("sources"), list) or not provenance["sources"]:
        errors.append("provenance.sources must contain at least one source")
    if provenance.get("trust_tier") not in TRUST_TIERS:
        errors.append(f"provenance.trust_tier must be one of {sorted(TRUST_TIERS)}")

    epistemic = record.get("epistemic_state", {})
    if epistemic.get("status") not in EPISTEMIC_STATUSES:
        errors.append(f"epistemic_state.status must be one of {sorted(EPISTEMIC_STATUSES)}")
    confidence = epistemic.get("confidence")
    if not isinstance(confidence, (int, float)) or isinstance(confidence, bool) or not 0 <= confidence <= 1:
        errors.append("epistemic_state.confidence must be a number from 0 through 1")

    governance = record.get("governance", {})
    if governance.get("classification") not in CLASSIFICATIONS:
        errors.append(f"governance.classification must be one of {sorted(CLASSIFICATIONS)}")
    if governance.get("admission_policy") not in ADMISSION_POLICIES:
        errors.append(f"governance.admission_policy must be one of {sorted(ADMISSION_POLICIES)}")
    if governance.get("classification") in {"RESTRICTED", "SECRET"} and not governance.get("allowed_consumers"):
        errors.append("restricted memory requires governance.allowed_consumers")
    if governance.get("training_allowed") and (
        governance.get("admission_policy") != "HUMAN_REVIEWED"
        or governance.get("human_review_required") is not True
    ):
        errors.append("training_allowed requires HUMAN_REVIEWED admission")
    if governance.get("propagation_allowed") and memory_type == "WORKING":
        errors.append("WORKING memory cannot propagate across ecosystem boundaries")

    usage = record.get("usage", {})
    for field in ("retrieval_count", "successful_outcomes", "failed_outcomes"):
        value = usage.get(field)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            errors.append(f"usage.{field} must be a non-negative integer")
    utility = usage.get("measured_utility")
    if not isinstance(utility, (int, float)) or isinstance(utility, bool) or not -1 <= utility <= 1:
        errors.append("usage.measured_utility must be a number from -1 through 1")

    integrity = record.get("integrity", {})
    digest = integrity.get("content_digest")
    if not isinstance(digest, str) or len(digest) != 64:
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
