# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Reference vectors for szl_action_identity.

Passing these tests does not admit a run-step and does not fix the ledger.
"""
from __future__ import annotations

import unittest

from szl_action_identity import ActionIdentity, canonical, compare, identity


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
