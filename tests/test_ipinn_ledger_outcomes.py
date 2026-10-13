#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Keep the PINN ledger claim aligned with the shared append outcome contract."""

import ast
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import szl_lake_ingest as ingest
import szl_lake_store as store


def _pinn_ledger_hook():
    # The PINN module loads the numerical engine at import time. Execute its
    # actual ledger function in isolation so this boundary stays stdlib-only.
    path = Path(__file__).resolve().parents[1] / "szl_governed_ipinn.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    function = next(node for node in tree.body
                    if isinstance(node, ast.FunctionDef)
                    and node.name == "record_pinn_receipt")
    namespace = {"RECEIPT_ORGAN": "a11oy-pinn", "json": json}
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(path), "exec"),
         namespace)
    return namespace["record_pinn_receipt"]


class PinnLedgerOutcomeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.ledger = store.ReceiptLedger(self.temp.name)
        getter = patch.object(ingest, "get_default_ledger", return_value=self.ledger)
        self.getter = getter.start()
        self.addCleanup(getter.stop)
        mirror = patch.object(ingest, "_mirror_to_dataset",
                              return_value={"state": "queued"})
        self.mirror = mirror.start()
        self.addCleanup(mirror.stop)
        self.record = _pinn_ledger_hook()
        self.receipt = {"id": "pinn-ledger-test", "payload": {"value": 1}}

    def test_acknowledgement_and_duplicate_prove_only_local_representation(self):
        first = self.record(self.receipt)
        second = self.record(self.receipt)
        self.assertEqual(first["state"], "LOCAL_ACKNOWLEDGED")
        self.assertEqual(second["state"], "LOCAL_DUPLICATE")
        for result in (first, second):
            self.assertTrue(result["recorded"])
            self.assertEqual(result["receipt_id"], self.receipt["id"])
            self.assertEqual(result["remote_publication"], "NOT_ACKNOWLEDGED")
        self.assertEqual(len(self.ledger.query(organ="a11oy-pinn")), 1)

    def test_prewrite_rejection_does_not_claim_recorded(self):
        result = self.record({"id": "invalid", "value": float("nan")})
        self.assertEqual(result["state"], "REJECTED")
        self.assertFalse(result["recorded"])
        self.getter.assert_not_called()
        self.mirror.assert_not_called()

    def test_lost_fsync_ack_stays_unknown_even_when_bytes_are_readable(self):
        real_fsync = os.fsync

        def persisted_then_raise(fd):
            real_fsync(fd)
            raise OSError("acknowledgement lost")

        with patch.object(store.os, "fsync", side_effect=persisted_then_raise):
            result = self.record(self.receipt)
        self.assertEqual(result["state"], "UNKNOWN")
        self.assertIsNone(result["recorded"])
        self.assertFalse(result["retry_admitted"])
        self.assertEqual(result["result"]["readback"]["state"], "LOCAL_PRESENT")
        self.mirror.assert_not_called()

    def test_malformed_foreign_and_raised_statuses_remain_unknown(self):
        statuses = (None, {"accepted": True, "duplicate": False,
                           "state": "LOCAL_ACKNOWLEDGED", "receipt_id": "foreign"},
                    {"accepted": True, "duplicate": False,
                     "state": "LOCAL_ACKNOWLEDGED", "receipt_id": self.receipt["id"],
                     "organ": "foreign"},
                    {"accepted": True, "duplicate": True,
                     "state": "LOCAL_ACKNOWLEDGED", "receipt_id": self.receipt["id"]},
                    {"accepted": True, "duplicate": False,
                     "state": "UNKNOWN", "receipt_id": self.receipt["id"]},
                    {"status": float("nan")})
        for status in statuses:
            with self.subTest(status=status), \
                 patch.object(ingest, "record_receipt", return_value=status):
                result = self.record(self.receipt)
                self.assertEqual(result["state"], "UNKNOWN")
                self.assertIsNone(result["recorded"])
                json.dumps(result, allow_nan=False)
        with patch.object(ingest, "record_receipt", side_effect=OSError("uncertain")):
            result = self.record(self.receipt)
        self.assertEqual(result["state"], "UNKNOWN")
        self.assertIsNone(result["recorded"])

    def acknowledgement(self, duplicate=False):
        return {"accepted": not duplicate, "duplicate": duplicate,
                "state": "LOCAL_DUPLICATE" if duplicate else "LOCAL_ACKNOWLEDGED",
                "receipt_id": self.receipt["id"], "organ": "a11oy-pinn"}

    def test_positive_looking_non_json_status_never_claims_recorded(self):
        cyclic = []
        cyclic.append(cyclic)
        malformed = {"nan": float("nan"), "infinity": float("inf"),
                     "object": object(), "cyclic": cyclic}
        for duplicate in (False, True):
            for name, value in malformed.items():
                status = dict(self.acknowledgement(duplicate), extra=value)
                with self.subTest(duplicate=duplicate, malformed=name), \
                     patch.object(ingest, "record_receipt", return_value=status) as hook:
                    result = self.record(self.receipt)
                self.assertEqual(result["state"], "UNKNOWN")
                self.assertIsNone(result["recorded"])
                self.assertFalse(result["retry_admitted"])
                self.assertEqual(result["receipt_id"], self.receipt["id"])
                self.assertEqual(result["remote_publication"], "NOT_ACKNOWLEDGED")
                json.dumps(result, allow_nan=False)
                hook.assert_called_once()
        self.getter.assert_not_called()
        self.mirror.assert_not_called()

    def test_serialization_recursion_failure_is_unknown(self):
        # JSON nesting limits vary by interpreter; exercise the actual failure
        # boundary without declaring a representable deep document invalid.
        for duplicate in (False, True):
            status = self.acknowledgement(duplicate)
            with self.subTest(duplicate=duplicate), \
                 patch.object(ingest, "record_receipt", return_value=status) as hook, \
                 patch.object(json, "dumps", side_effect=RecursionError("serializer limit")):
                result = self.record(self.receipt)
            self.assertEqual(result["state"], "UNKNOWN")
            self.assertIsNone(result["recorded"])
            self.assertFalse(result["retry_admitted"])
            json.dumps(result, allow_nan=False)
            hook.assert_called_once()

    def test_returned_acknowledgement_is_detached_from_sink_status(self):
        status = dict(self.acknowledgement(), nested={"state": "local"})
        with patch.object(ingest, "record_receipt", return_value=status):
            result = self.record(self.receipt)
        status["accepted"] = False
        status["nested"]["state"] = "mutated"
        self.assertTrue(result["recorded"])
        self.assertTrue(result["result"]["accepted"])
        self.assertEqual(result["result"]["nested"]["state"], "local")

    def test_missing_nonboolean_or_conflicting_acknowledgement_is_unknown(self):
        for duplicate in (False, True):
            for field in ("accepted", "duplicate", "receipt_id", "organ", "state"):
                for replacement in (None, 0, 1, "true", "foreign"):
                    status = self.acknowledgement(duplicate)
                    if replacement is None:
                        status.pop(field)
                    else:
                        status[field] = replacement
                    with self.subTest(duplicate=duplicate, field=field, replacement=replacement), \
                         patch.object(ingest, "record_receipt", return_value=status) as hook:
                        result = self.record(self.receipt)
                    self.assertEqual(result["state"], "UNKNOWN")
                    self.assertIsNone(result["recorded"])
                    self.assertFalse(result["retry_admitted"])
                    hook.assert_called_once()


if __name__ == "__main__":
    unittest.main()
