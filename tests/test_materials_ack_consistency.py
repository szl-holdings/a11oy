#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Contradictory receipt acknowledgements remain unknown without a second write."""
import json
import unittest
from unittest.mock import Mock, patch

import szl_lake_ingest as ingest
import szl_lake_store as store
import szl_materials_predict as materials


class MaterialsAckConsistencyTests(unittest.TestCase):
    def setUp(self):
        self.receipt = {"id": "ack-consistency", "payload": {"value": 1}}
        self.organ = materials.RECEIPT_ORGAN
        self.rid = store.receipt_identity(dict(self.receipt, organ=self.organ))

    def status(self, duplicate=False, **overrides):
        result = {"accepted": not duplicate, "duplicate": duplicate,
                  "receipt_id": self.rid, "organ": self.organ,
                  "state": "LOCAL_DUPLICATE" if duplicate else "LOCAL_ACKNOWLEDGED"}
        result.update(overrides)
        return result

    def hook_result(self, status):
        with patch.object(ingest, "record_receipt", return_value=status) as hook:
            result = materials._ledger(self.receipt)
        hook.assert_called_once_with(self.receipt, organ=self.organ)
        return result

    def append_result(self, status):
        ledger = Mock()
        ledger.append.return_value = status
        with patch.object(ingest, "get_default_ledger", return_value=ledger), \
             patch.object(ingest, "_mirror_to_dataset", return_value={"state": "queued"}) as mirror:
            result = ingest.record_receipt(self.receipt, organ=self.organ)
        ledger.append.assert_called_once_with(dict(self.receipt, organ=self.organ))
        return result, mirror

    def assert_unknown_hook(self, result):
        self.assertEqual(result["state"], "UNKNOWN")
        self.assertIsNone(result["recorded"])
        self.assertIs(result["accepted"], False)
        self.assertIs(result["duplicate"], False)
        self.assertIs(result["retry_admitted"], False)
        self.assertEqual(result["receipt_id"], self.rid)
        self.assertEqual(result["organ"], self.organ)
        json.dumps(result, allow_nan=False)

    def test_hook_new_acceptance_requires_missing_or_true_attempt_flag(self):
        for attempted in (False, None, 0, 1, "false", "true", [], {}):
            with self.subTest(write_attempted=attempted):
                self.assert_unknown_hook(self.hook_result(self.status(write_attempted=attempted)))

    def test_append_new_acceptance_never_mirrors_invalid_attempt_flag(self):
        for attempted in (False, None, 0, 1, "false", "true", [], {}):
            with self.subTest(write_attempted=attempted):
                result, mirror = self.append_result(self.status(write_attempted=attempted))
                self.assertEqual(result["state"], "UNKNOWN")
                self.assertIs(result["accepted"], False)
                self.assertIs(result["duplicate"], False)
                self.assertEqual(result["receipt_id"], self.rid)
                self.assertEqual(result["organ"], self.organ)
                self.assertEqual(result["mirror"]["state"], "NOT_ATTEMPTED")
                mirror.assert_not_called()

    def test_hook_duplicate_requires_boolean_when_attempt_flag_is_present(self):
        for attempted in (None, 0, 1, "false", "true", [], {}):
            with self.subTest(write_attempted=attempted):
                self.assert_unknown_hook(self.hook_result(self.status(True, write_attempted=attempted)))

    def test_append_duplicate_never_mirrors_malformed_attempt_flag(self):
        for attempted in (None, 0, 1, "false", "true", [], {}):
            with self.subTest(write_attempted=attempted):
                result, mirror = self.append_result(self.status(True, write_attempted=attempted))
                self.assertEqual(result["state"], "UNKNOWN")
                self.assertIs(result["accepted"], False)
                self.assertIs(result["duplicate"], False)
                mirror.assert_not_called()

    def test_legacy_omission_and_valid_boolean_acknowledgements_remain_local_only(self):
        statuses = [self.status(), self.status(write_attempted=True), self.status(True),
                    self.status(True, write_attempted=False), self.status(True, write_attempted=True)]
        for status in statuses:
            with self.subTest(status=status):
                hook = self.hook_result(status)
                self.assertIs(hook["recorded"], True)
                self.assertEqual(hook["state"], status["state"])
                self.assertEqual(hook["remote_publication"], "NOT_ACKNOWLEDGED")
                result, mirror = self.append_result(status)
                self.assertEqual(result["state"], status["state"])
                self.assertEqual(result["mirror"]["publication"], "NOT_ACKNOWLEDGED")
                mirror.assert_called_once()

    def test_foreign_rejection_never_rejects_requested_receipt(self):
        for foreign in ({"receipt_id": "different"}, {"organ": "different"},
                        {"receipt_id": None}, {"organ": None}):
            with self.subTest(foreign=foreign):
                status = self.status(accepted=False, state="REJECTED", write_attempted=False, **foreign)
                self.assert_unknown_hook(self.hook_result(status))

    def test_prevalidation_rejection_retains_matching_or_absent_identity(self):
        statuses = [self.status(accepted=False, state="REJECTED", write_attempted=False),
                    {"accepted": False, "duplicate": False,
                     "state": "REJECTED", "write_attempted": False}]
        for status in statuses:
            with self.subTest(status=status):
                result = self.hook_result(status)
                self.assertEqual(result["state"], "REJECTED")
                self.assertIs(result["recorded"], False)
                self.assertIs(result["retry_admitted"], False)


if __name__ == "__main__":
    unittest.main()
