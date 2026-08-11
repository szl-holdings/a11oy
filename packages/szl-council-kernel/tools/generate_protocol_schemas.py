#!/usr/bin/env python3
from __future__ import annotations

"""Generate the strict public JSON Schemas for the Council Kernel protocol.

The generator is intentionally deterministic.  Protocol schemas are assembled
from one set of local definitions so the standalone records and the portable
settlement cannot silently drift apart.
"""

import copy
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "src" / "szl_council_kernel" / "schemas"

IDENTIFIER_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:/@+\-]{0,255}$"
DIGEST_PATTERN = r"^(sha256|sha3-256):[0-9a-f]{64}$"
B64URL_PATTERN = r"^[A-Za-z0-9_-]+$"
ROLES = ["AUTHORITY", "SENTINEL", "VERIFIER", "VALUE"]
VOTES = ["SUPPORT", "OPPOSE", "ABSTAIN", "VETO"]
RISKS = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
STATES = ["QUORUM_VERIFIED", "REQUIRE_HUMAN", "BLOCKED", "CONFLICT", "INSUFFICIENT", "INVALID"]
AXES = [
    "trust_domain",
    "key_id",
    "implementation_digest",
    "model_family",
    "evidence_domain",
    "operator_id",
    "retrieval_path",
    "provider_account",
]


def identifier() -> dict[str, Any]:
    return {"type": "string", "minLength": 1, "maxLength": 256, "pattern": IDENTIFIER_PATTERN}


def digest() -> dict[str, Any]:
    return {"type": "string", "pattern": DIGEST_PATTERN}


def datetime_value() -> dict[str, Any]:
    return {"type": "string", "format": "date-time"}


def bounded_string(maximum: int = 512, minimum: int = 1) -> dict[str, Any]:
    return {"type": "string", "minLength": minimum, "maxLength": maximum}


def nullable(value: dict[str, Any]) -> dict[str, Any]:
    return {"anyOf": [copy.deepcopy(value), {"type": "null"}]}


def string_array(*, maximum: int, item_maximum: int, minimum: int = 0, pattern: str | None = None) -> dict[str, Any]:
    item: dict[str, Any] = {"type": "string", "minLength": 1, "maxLength": item_maximum}
    if pattern is not None:
        item["pattern"] = pattern
    return {
        "type": "array",
        "minItems": minimum,
        "maxItems": maximum,
        "uniqueItems": True,
        "items": item,
    }


def role_array() -> dict[str, Any]:
    return {
        "type": "array",
        "minItems": 0,
        "maxItems": 4,
        "uniqueItems": True,
        "items": {"enum": ROLES},
    }


def object_schema(properties: dict[str, Any], required: list[str], **extra: Any) -> dict[str, Any]:
    value: dict[str, Any] = {
        "type": "object",
        "additionalProperties": False,
        "required": required,
        "properties": properties,
    }
    value.update(extra)
    return value


def document(title: str, urn: str, definition: dict[str, Any]) -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": urn,
        "title": title,
        **copy.deepcopy(definition),
    }


case_def = object_schema(
    {
        "schema": {"const": "szl.council-case/v1"},
        "case_id": identifier(),
        "subject": bounded_string(4096),
        "risk_class": {"enum": RISKS},
        "value_claimed": {"type": "boolean"},
        "evidence_manifest_digest": digest(),
        "policy_digest": digest(),
        "envelope_digest": digest(),
        "epochs_digest": digest(),
        "created_at": datetime_value(),
    },
    [
        "schema",
        "case_id",
        "subject",
        "risk_class",
        "value_claimed",
        "evidence_manifest_digest",
        "policy_digest",
        "envelope_digest",
        "epochs_digest",
        "created_at",
    ],
)

policy_fields = [
    "min_distinct_trust_domains",
    "min_distinct_keys",
    "min_distinct_implementations",
    "min_distinct_model_families",
    "min_distinct_evidence_domains",
    "min_distinct_operators",
    "min_distinct_retrieval_paths",
    "min_distinct_provider_accounts",
    "low_medium_support_threshold",
    "high_critical_support_threshold",
]
policy_bool_fields = [
    "require_authority_support",
    "require_verifier_support",
    "require_value_support_when_claimed",
    "preserve_minority_truth",
    "sentinel_veto_categorical",
    "verifier_veto_categorical",
]
policy_properties: dict[str, Any] = {
    "schema": {"const": "szl.council-policy/v1"},
    "policy_id": identifier(),
    "version": bounded_string(64),
    "minimum_effective_size": {"type": "number", "minimum": 1, "maximum": 4},
}
policy_properties.update({name: {"type": "integer", "minimum": 1, "maximum": 4} for name in policy_fields})
policy_properties.update({name: {"type": "boolean"} for name in policy_bool_fields})
policy_def = object_schema(
    policy_properties,
    ["policy_id", "version", *policy_fields, "minimum_effective_size", *policy_bool_fields, "schema"],
    allOf=[
        {
            "if": {
                "properties": {"low_medium_support_threshold": {"type": "integer"}},
                "required": ["low_medium_support_threshold", "high_critical_support_threshold"],
            },
            "then": {
                "properties": {
                    "high_critical_support_threshold": {"type": "integer", "minimum": 1, "maximum": 4}
                }
            },
        }
    ],
)

identity_def = object_schema(
    {
        "member_id": identifier(),
        "role": {"enum": ROLES},
        "key_id": digest(),
        "public_key": {"type": "string", "minLength": 43, "maxLength": 43, "pattern": B64URL_PATTERN},
        "trust_domain": bounded_string(512),
        "implementation_digest": digest(),
        "model_family": bounded_string(512),
        "evidence_domain": bounded_string(512),
        "operator_id": bounded_string(512),
        "retrieval_path": bounded_string(512),
        "provider_account": bounded_string(512),
        "not_before": datetime_value(),
        "not_after": datetime_value(),
        "schema": {"const": "szl.council-identity/v1"},
    },
    [
        "member_id",
        "role",
        "key_id",
        "public_key",
        "trust_domain",
        "implementation_digest",
        "model_family",
        "evidence_domain",
        "operator_id",
        "retrieval_path",
        "provider_account",
        "not_before",
        "not_after",
        "schema",
    ],
)

assessment_def = object_schema(
    {
        "schema": {"const": "szl.council-assessment/v1"},
        "case_id": identifier(),
        "role": {"enum": ROLES},
        "member_id": identifier(),
        "vote": {"enum": VOTES},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "reason_codes": string_array(maximum=64, item_maximum=128, minimum=1),
        "evidence_digests": string_array(maximum=256, item_maximum=72, pattern=DIGEST_PATTERN),
        "counterevidence_digests": string_array(maximum=256, item_maximum=72, pattern=DIGEST_PATTERN),
        "policy_digest": digest(),
        "subject_digest": digest(),
        "issued_at": datetime_value(),
        "expires_at": datetime_value(),
    },
    [
        "schema",
        "case_id",
        "role",
        "member_id",
        "vote",
        "confidence",
        "reason_codes",
        "evidence_digests",
        "counterevidence_digests",
        "policy_digest",
        "subject_digest",
        "issued_at",
        "expires_at",
    ],
    allOf=[
        {
            "if": {"properties": {"vote": {"const": "SUPPORT"}}, "required": ["vote"]},
            "then": {"properties": {"evidence_digests": {"minItems": 1}}},
        },
        {
            "if": {"properties": {"vote": {"enum": ["OPPOSE", "VETO"]}}, "required": ["vote"]},
            "then": {"properties": {"counterevidence_digests": {"minItems": 1}}},
        },
    ],
)

commitment_def = object_schema(
    {
        "schema": {"const": "szl.council-commitment/v1"},
        "case_id": identifier(),
        "member_id": identifier(),
        "role": {"enum": ROLES},
        "policy_digest": digest(),
        "subject_digest": digest(),
        "assessment_commitment": digest(),
        "issued_at": datetime_value(),
        "expires_at": datetime_value(),
    },
    [
        "schema",
        "case_id",
        "member_id",
        "role",
        "policy_digest",
        "subject_digest",
        "assessment_commitment",
        "issued_at",
        "expires_at",
    ],
)

registry_def = object_schema(
    {
        "schema": {"const": "szl.council-registry/v1"},
        "identities": {
            "type": "array",
            "minItems": 4,
            "maxItems": 4,
            "uniqueItems": True,
            "items": {"$ref": "#/$defs/identity"},
            "allOf": [
                {
                    "contains": {"type": "object", "properties": {"role": {"const": role}}, "required": ["role"]},
                    "minContains": 1,
                    "maxContains": 1,
                }
                for role in ROLES
            ],
        },
        "registry_digest": digest(),
    },
    ["schema", "identities", "registry_digest"],
    **{"$defs": {"identity": identity_def}},
)

dsse_def = object_schema(
    {
        "schema": {"const": "szl.dsse-envelope/v1"},
        "envelope": object_schema(
            {
                "payloadType": bounded_string(512),
                "payload": {"type": "string", "minLength": 2, "maxLength": 16_777_216, "pattern": B64URL_PATTERN},
                "signatures": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 1,
                    "items": object_schema(
                        {
                            "keyid": digest(),
                            "sig": {"type": "string", "minLength": 86, "maxLength": 86, "pattern": B64URL_PATTERN},
                        },
                        ["keyid", "sig"],
                    ),
                },
            },
            ["payloadType", "payload", "signatures"],
        ),
        "envelope_digest": digest(),
        "signer_state": {"enum": ["SIGNED_TEST", "SIGNED_PERSISTENT"]},
    },
    ["schema", "envelope", "envelope_digest", "signer_state"],
)

axis_count = object_schema(
    {axis: {"type": "integer", "minimum": 1, "maximum": 4} for axis in AXES},
    AXES,
)
axis_effective = object_schema(
    {axis: {"type": "number", "minimum": 1, "maximum": 4} for axis in AXES},
    AXES,
)
axis_clusters = object_schema(
    {
        axis: {
            "type": "array",
            "minItems": 4,
            "maxItems": 4,
            "items": bounded_string(512),
        }
        for axis in AXES
    },
    AXES,
)
diversity_def = object_schema(
    {
        "schema": {"const": "szl.epistemic-diversity-report/v1"},
        "participant_count": {"const": 4},
        "distinct": axis_count,
        "effective_by_axis": axis_effective,
        "joint_effective_size": {"type": "number", "minimum": 1, "maximum": 4},
        "minimum_effective_size": {"type": "number", "minimum": 1, "maximum": 4},
        "requirements_met": {"type": "boolean"},
        "failed_requirements": string_array(maximum=9, item_maximum=128),
        "cluster_assignments": axis_clusters,
    },
    [
        "schema",
        "participant_count",
        "distinct",
        "effective_by_axis",
        "joint_effective_size",
        "minimum_effective_size",
        "requirements_met",
        "failed_requirements",
        "cluster_assignments",
    ],
    allOf=[
        {
            "if": {"properties": {"requirements_met": {"const": True}}, "required": ["requirements_met"]},
            "then": {"properties": {"failed_requirements": {"maxItems": 0}}},
            "else": {"properties": {"failed_requirements": {"minItems": 1}}},
        }
    ],
)

result_def = object_schema(
    {
        "schema": {"const": "szl.council-result/v1"},
        "case_id": identifier(),
        "state": {"enum": STATES},
        "verified": {"type": "boolean"},
        "support_roles": role_array(),
        "oppose_roles": role_array(),
        "abstain_roles": role_array(),
        "veto_roles": role_array(),
        "missing_roles": role_array(),
        "reason_codes": string_array(maximum=128, item_maximum=128, minimum=1),
        "minority_evidence_digests": string_array(maximum=256, item_maximum=72, pattern=DIGEST_PATTERN),
        "received_support": {"type": "integer", "minimum": 0, "maximum": 4},
        "required_support": {"type": "integer", "minimum": 1, "maximum": 4},
        "diversity": {"$ref": "#/$defs/diversity"},
        "policy_digest": digest(),
        "subject_digest": digest(),
        "transcript_digest": digest(),
        "issued_at": datetime_value(),
    },
    [
        "schema",
        "case_id",
        "state",
        "verified",
        "support_roles",
        "oppose_roles",
        "abstain_roles",
        "veto_roles",
        "missing_roles",
        "reason_codes",
        "minority_evidence_digests",
        "received_support",
        "required_support",
        "diversity",
        "policy_digest",
        "subject_digest",
        "transcript_digest",
        "issued_at",
    ],
    allOf=[
        {
            "if": {"properties": {"state": {"const": "QUORUM_VERIFIED"}}, "required": ["state"]},
            "then": {
                "properties": {
                    "verified": {"const": True},
                    "oppose_roles": {"maxItems": 0},
                    "abstain_roles": {"maxItems": 0},
                    "veto_roles": {"maxItems": 0},
                    "missing_roles": {"maxItems": 0},
                    "diversity": {"properties": {"requirements_met": {"const": True}}},
                }
            },
            "else": {"properties": {"verified": {"const": False}}},
        }
    ],
    **{"$defs": {"diversity": diversity_def}},
)

gate_def = object_schema(
    {
        "decision": {"enum": ["ACT", "ESCALATE", "BLOCK"]},
        "risk_score": {"type": "number", "minimum": 0, "maximum": 1},
        "empirical_false_green_upper": {"type": "number", "minimum": 0, "maximum": 1},
        "reason_codes": string_array(maximum=64, item_maximum=128, minimum=1),
        "calibration_method": bounded_string(256),
        "formal_coverage_claimed": {"const": False},
        "issued_at": datetime_value(),
        "schema": {"const": "szl.act-escalate-gate-result/v1"},
    },
    [
        "decision",
        "risk_score",
        "empirical_false_green_upper",
        "reason_codes",
        "calibration_method",
        "formal_coverage_claimed",
        "issued_at",
        "schema",
    ],
)

minority_entry_def = object_schema(
    {
        "schema": {"const": "szl.minority-truth-entry/v1"},
        "case_id": identifier(),
        "role": {"enum": ROLES},
        "vote": {"enum": ["OPPOSE", "VETO"]},
        "assessment_digest": digest(),
        "counterevidence_digests": string_array(maximum=256, item_maximum=72, minimum=1, pattern=DIGEST_PATTERN),
        "reason_codes": string_array(maximum=64, item_maximum=128, minimum=1),
        "observed_at": datetime_value(),
        "prior_entry_digest": nullable(digest()),
        "entry_digest": digest(),
    },
    [
        "schema",
        "case_id",
        "role",
        "vote",
        "assessment_digest",
        "counterevidence_digests",
        "reason_codes",
        "observed_at",
        "prior_entry_digest",
        "entry_digest",
    ],
)

vault_verification_def = object_schema(
    {
        "schema": {"const": "szl.minority-truth-vault-verification/v1"},
        "status": {"enum": ["PASS", "FAIL"]},
        "entry_count": {"type": "integer", "minimum": 0, "maximum": 4},
        "head_digest": nullable(digest()),
        "errors": string_array(maximum=32, item_maximum=256),
    },
    ["schema", "status", "entry_count", "head_digest", "errors"],
    allOf=[
        {
            "if": {"properties": {"status": {"const": "PASS"}}, "required": ["status"]},
            "then": {"properties": {"errors": {"maxItems": 0}}},
            "else": {"properties": {"errors": {"minItems": 1}}},
        }
    ],
)

reveal_def = object_schema(
    {
        "assessment": {"$ref": "#/$defs/assessment"},
        "salt": bounded_string(256, 16),
        "signed_assessment": {"$ref": "#/$defs/dsse"},
    },
    ["assessment", "salt", "signed_assessment"],
)

role_dsse_map = object_schema(
    {role: {"$ref": "#/$defs/dsse"} for role in ROLES},
    ROLES,
)
role_reveal_map = object_schema(
    {role: {"$ref": "#/$defs/reveal"} for role in ROLES},
    [],
    minProperties=0,
    maxProperties=4,
)

settlement_def = object_schema(
    {
        "schema": {"const": "szl.council-settlement/v2"},
        "session_time": datetime_value(),
        "case": {"$ref": "#/$defs/case"},
        "policy": {"$ref": "#/$defs/policy"},
        "result": {"$ref": "#/$defs/result"},
        "result_digest": digest(),
        "signed_result": {"$ref": "#/$defs/dsse"},
        "aggregator": object_schema(
            {
                "algorithm": {"const": "Ed25519"},
                "key_id": digest(),
                "public_key": {"type": "string", "minLength": 43, "maxLength": 43, "pattern": B64URL_PATTERN},
            },
            ["algorithm", "key_id", "public_key"],
        ),
        "registry": {"$ref": "#/$defs/registry"},
        "commitment_set_digest": digest(),
        "commitments": role_dsse_map,
        "reveal_order": {
            "type": "array",
            "minItems": 0,
            "maxItems": 4,
            "uniqueItems": True,
            "items": {"enum": ROLES},
        },
        "reveals": role_reveal_map,
        "minority_truth_vault": object_schema(
            {
                "entries": {
                    "type": "array",
                    "minItems": 0,
                    "maxItems": 4,
                    "items": {"$ref": "#/$defs/minority_entry"},
                },
                "verification": {"$ref": "#/$defs/vault_verification"},
            },
            ["entries", "verification"],
        ),
        "private_reasoning_included": {"const": False},
        "raw_evidence_included": {"const": False},
        "settlement_digest": digest(),
    },
    [
        "schema",
        "session_time",
        "case",
        "policy",
        "result",
        "result_digest",
        "signed_result",
        "aggregator",
        "registry",
        "commitment_set_digest",
        "commitments",
        "reveal_order",
        "reveals",
        "minority_truth_vault",
        "private_reasoning_included",
        "raw_evidence_included",
        "settlement_digest",
    ],
    **{
        "$defs": {
            "case": case_def,
            "policy": policy_def,
            "identity": identity_def,
            "assessment": assessment_def,
            "commitment": commitment_def,
            "registry": registry_def,
            "dsse": dsse_def,
            "diversity": diversity_def,
            "result": result_def,
            "minority_entry": minority_entry_def,
            "vault_verification": vault_verification_def,
            "reveal": reveal_def,
        }
    },
)

SCHEMAS: dict[str, dict[str, Any]] = {
    "council-case-v1.schema.json": document("SZL Council Case v1", "urn:szl:schema:council-case:v1", case_def),
    "council-policy-v1.schema.json": document("SZL Council Policy v1", "urn:szl:schema:council-policy:v1", policy_def),
    "council-identity-v1.schema.json": document("SZL Council Identity v1", "urn:szl:schema:council-identity:v1", identity_def),
    "council-assessment-v1.schema.json": document("SZL Council Assessment v1", "urn:szl:schema:council-assessment:v1", assessment_def),
    "council-commitment-v1.schema.json": document("SZL Council Commitment v1", "urn:szl:schema:council-commitment:v1", commitment_def),
    "council-registry-v1.schema.json": document("SZL Council Registry v1", "urn:szl:schema:council-registry:v1", registry_def),
    "dsse-envelope-v1.schema.json": document("SZL DSSE Envelope v1", "urn:szl:schema:dsse-envelope:v1", dsse_def),
    "epistemic-diversity-report-v1.schema.json": document(
        "SZL Epistemic Diversity Report v1", "urn:szl:schema:epistemic-diversity-report:v1", diversity_def
    ),
    "act-escalate-gate-result-v1.schema.json": document(
        "SZL Act/Escalate/Block Gate Result v1", "urn:szl:schema:act-escalate-gate-result:v1", gate_def
    ),
    "council-result-v1.schema.json": document("SZL Council Result v1", "urn:szl:schema:council-result:v1", result_def),
    "council-settlement-v2.schema.json": document(
        "SZL Portable Council Settlement v2", "urn:szl:schema:council-settlement:v2", settlement_def
    ),
}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for filename, schema in sorted(SCHEMAS.items()):
        path = OUT / filename
        path.write_text(json.dumps(schema, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "generated": sorted(SCHEMAS), "count": len(SCHEMAS)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
