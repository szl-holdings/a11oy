# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = (
    "action-request.schema.json",
    "authorization-receipt.schema.json",
    "deployment-identity.schema.json",
    "benchmark-result.schema.json",
    "environment.schema.json",
)


@pytest.mark.parametrize("name", SCHEMAS)
def test_schema_is_valid_draft_2020_12_and_strict_at_root(name):
    schema = json.loads((ROOT / "schemas" / name).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    assert schema["additionalProperties"] is False


def test_action_request_accepts_immutable_complete_request_and_rejects_unknown_field():
    schema = json.loads((ROOT / "schemas" / "action-request.schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER)
    request = {
        "request_id": "6a1e3862-8e98-4bdd-962d-c88208bb2e42",
        "trace_id": "a" * 32,
        "principal": "workload:release-agent",
        "action_type": "deploy.production",
        "target": "oci://ghcr.io/szl-holdings/a11oy@sha256:" + "1" * 64,
        "source_commit": "2" * 40,
        "artifact_digest": "sha256:" + "1" * 64,
        "requested_transition": {"from": "staging", "to": "production"},
        "preconditions": [],
        "test_receipts": [],
        "provenance_receipt": {
            "receipt_digest": "sha256:" + "4" * 64,
            "subject_digest": "sha256:" + "1" * 64,
            "source_commit": "2" * 40,
            "accepted": True,
            "verifier": "github-attestations",
            "verified_at": "2026-07-26T11:59:00Z",
            "source_repository": "github.com/szl-holdings/a11oy",
        },
        "security_receipts": [],
        "blast_radius": {
            "services": ["a11oy"],
            "users": "authorized internal users",
            "data": "no migration",
        },
        "rollback": {
            "receipt_digest": "sha256:" + "5" * 64,
            "target_digest": "sha256:" + "3" * 64,
            "verified": True,
            "tested_at": "2026-07-26T11:58:00Z",
        },
        "human_approvals": [
            {
                "approver": "human:release-owner",
                "action_type": "deploy.production",
                "target_digest": "sha256:" + "1" * 64,
                "environment": "production",
                "approved_at": "2026-07-26T12:00:00Z",
                "expires_at": "2026-07-26T12:04:00Z",
                "key_id": "human:release-owner:key-1",
                "signature": "A" * 64,
            }
        ],
        "expires_at": "2026-07-26T12:05:00Z",
    }
    validator.validate(request)
    request["debug_override"] = True
    with pytest.raises(ValidationError):
        validator.validate(request)
