# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Restricted logical-action identity reference.

This module has no network, database, execution authority, or durable
deduplication. A passing test here does not admit an A11oy run. The encoding
is a shared ASCII JSON subset, not RFC 8785.
"""
from __future__ import annotations

import hashlib
import json
import re
import unittest
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
        sort_keys=True, separators=(",", ":"),
    ).encode("ascii")
    if len(encoded) > MAX_BYTES:
        raise ValueError("Encoded object too large")
    return encoded


def digest(value: object) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


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
    logical = {
        "schema": "szl.logical-action/v1",
        "tenant_id": tenant_id,
        "run_id": run_id,
        "step_id": step_id,
    }
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
    # Not a completed-result assertion and not dispatch permission.
    return "REPLAY_CANDIDATE_REQUIRES_STATE_RIGHTS_AND_RESULT_CHECKS"


class IdentityReferenceTests(unittest.TestCase):
    def make(self, **changes):
        values = dict(
            tenant_id="tenant-a", run_id="run-1", step_id="step-2",
            plan_revision="plan-1", operation="synthesize",
            destination="mock-engine", arguments={"prompt": "synthetic"},
            execution_options={"sandbox": False, "profile": "fixture"},
        )
        values.update(changes)
        return identity(**values)

    def test_retry_stable(self):
        self.assertEqual(self.make(), self.make())

    def test_distinct_step(self):
        self.assertNotEqual(
            self.make().logical_id,
            self.make(step_id="step-3").logical_id,
        )

    def test_new_run_is_new_intent(self):
        self.assertNotEqual(
            self.make().logical_id,
            self.make(run_id="run-2").logical_id,
        )

    def test_changed_operation_conflicts(self):
        self.assertEqual(
            compare(self.make(), self.make(operation="execute")),
            "CONFLICT_HOLD",
        )

    def test_changed_sandbox_conflicts(self):
        self.assertEqual(compare(
            self.make(),
            self.make(execution_options={"sandbox": True, "profile": "fixture"}),
        ), "CONFLICT_HOLD")

    def test_changed_arguments_conflict(self):
        self.assertEqual(
            compare(self.make(), self.make(arguments={"prompt": "changed"})),
            "CONFLICT_HOLD",
        )

    def test_plan_revision_conflicts(self):
        self.assertEqual(
            compare(self.make(), self.make(plan_revision="plan-2")),
            "CONFLICT_HOLD",
        )

    def test_mapping_order_is_stable(self):
        self.assertEqual(
            canonical({"b": 2, "a": 1}), canonical({"a": 1, "b": 2})
        )

    def test_invalid_inputs_rejected(self):
        for value in (0.1, float("nan"), 2**53, "\ud800", {"é": 1}):
            with self.subTest(value=repr(value)):
                with self.assertRaises(ValueError):
                    canonical(value)
        for value in ("", True, "contains space"):
            with self.assertRaises(ValueError):
                self.make(run_id=value)

    def test_falsey_arguments_are_explicit_values(self):
        for value in (None, False, 0, [], {}):
            self.assertIsInstance(self.make(arguments=value), ActionIdentity)

    def test_comparison_never_grants_authority(self):
        self.assertEqual(
            compare(self.make(), self.make()),
            "REPLAY_CANDIDATE_REQUIRES_STATE_RIGHTS_AND_RESULT_CHECKS",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
