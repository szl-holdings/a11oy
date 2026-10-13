"""Local ledger acknowledgement and inert exact-identity readback contracts."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import szl_lake_ingest as ingest
import szl_lake_store as store
import szl_materials_predict as materials


class LedgerOutcomeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.ledger = store.ReceiptLedger(self.temp.name)
        self.getter = patch.object(ingest, "get_default_ledger", return_value=self.ledger)
        self.getter.start()
        self.addCleanup(self.getter.stop)
        self.mirror = patch.object(ingest, "_mirror_to_dataset",
                                  return_value={"ok": True, "queued": 1, "state": "queued"})
        self.mirror_mock = self.mirror.start()
        self.addCleanup(self.mirror.stop)
        self.receipt = {"id": "stable-test-receipt", "payload": {"value": 1}}

    def fingerprint(self):
        return {str(p.relative_to(self.temp.name)): p.read_bytes()
                for p in Path(self.temp.name).rglob("*") if p.is_file()}

    def test_prewrite_rejection_never_opens_ledger_or_mirrors(self):
        with patch.object(ingest, "get_default_ledger") as getter:
            for receipt in (None, {"organ": "../bad"}, {"value": float("nan")}):
                with self.subTest(receipt=receipt):
                    result = ingest.record_receipt(receipt, organ="materials")
                    self.assertEqual(result["state"], "REJECTED")
                    self.assertFalse(result["write_attempted"])
            getter.assert_not_called()
        self.mirror_mock.assert_not_called()
        self.assertEqual(self.fingerprint(), {})

    def test_fsync_then_raise_preserves_unknown_and_reads_exact_identity_once(self):
        real_fsync = os.fsync
        def persisted_then_raise(fd):
            real_fsync(fd)
            raise OSError("acknowledgement lost after real fsync")
        with patch.object(store.os, "fsync", side_effect=persisted_then_raise), \
             patch.object(self.ledger, "append", wraps=self.ledger.append) as append:
            result = materials._ledger(self.receipt)
        self.assertIsNone(result["recorded"])
        self.assertEqual(result["state"], "UNKNOWN")
        self.assertFalse(result["retry_admitted"])
        self.assertEqual(result["receipt_id"], self.receipt["id"])
        self.assertEqual(result["result"]["readback"]["state"], "LOCAL_PRESENT")
        self.assertEqual(result["result"]["readback"]["local_fsync"], "UNKNOWN")
        append.assert_called_once()
        self.mirror_mock.assert_not_called()
        rows = self.ledger.query(organ=materials.RECEIPT_ORGAN, limit=0)
        self.assertEqual(len(rows), 1)
        before = self.fingerprint()
        for _ in range(2):
            lookup = self.ledger.lookup_receipt(result["receipt_id"], materials.RECEIPT_ORGAN)
            self.assertEqual(lookup["state"], "LOCAL_PRESENT")
            self.assertNotIn("receipt", lookup)
        self.assertEqual(self.fingerprint(), before)

    def test_absent_or_failed_readback_never_admits_retry_or_infers_rejection(self):
        for failed_readback in (False, True):
            with self.subTest(failed_readback=failed_readback), \
                 patch.object(self.ledger, "append", side_effect=OSError("uncertain")) as append:
                if failed_readback:
                    with patch.object(self.ledger, "lookup_receipt", side_effect=OSError("unreadable")):
                        result = materials._ledger(self.receipt)
                else:
                    result = materials._ledger(self.receipt)
                self.assertEqual(result["state"], "UNKNOWN")
                self.assertIsNone(result["recorded"])
                self.assertEqual(result["receipt_id"], self.receipt["id"])
                self.assertEqual(result["result"]["readback"]["state"], "UNKNOWN")
                self.assertFalse(result["retry_admitted"])
                append.assert_called_once()
        self.mirror_mock.assert_not_called()
        self.assertEqual(self.fingerprint(), {})

    def test_acknowledged_and_duplicate_remain_local_while_mirror_is_queued(self):
        first = materials._ledger(self.receipt)
        second = materials._ledger(self.receipt)
        self.assertEqual(first["state"], "LOCAL_ACKNOWLEDGED")
        self.assertEqual(second["state"], "LOCAL_DUPLICATE")
        for result in (first, second):
            self.assertTrue(result["recorded"])
            self.assertEqual(result["remote_publication"], "NOT_ACKNOWLEDGED")
            self.assertEqual(result["result"]["mirror"]["state"], "queued")
            self.assertEqual(result["result"]["mirror"]["publication"], "NOT_ACKNOWLEDGED")
        self.assertEqual(len(self.ledger.query(organ=materials.RECEIPT_ORGAN)), 1)

    def test_mirror_failure_does_not_erase_local_acknowledgement(self):
        self.mirror_mock.return_value = {"ok": False, "reason": "unavailable"}
        result = materials._ledger(self.receipt)
        self.assertEqual(result["state"], "LOCAL_ACKNOWLEDGED")
        self.assertTrue(result["recorded"])
        self.assertFalse(result["result"]["mirror"]["ok"])
        self.assertEqual(result["remote_publication"], "NOT_ACKNOWLEDGED")

    def test_unqualified_false_or_malformed_hook_remains_unknown(self):
        for status in ({"accepted": False}, None, {"accepted": True, "duplicate": True},
                       {"accepted": True, "state": "UNKNOWN"},
                       {"accepted": True, "receipt_id": "different-identity"},
                       {"accepted": False, "duplicate": True, "state": "UNKNOWN"}):
            with self.subTest(status=status), patch.object(ingest, "record_receipt", return_value=status) as hook:
                result = materials._ledger(self.receipt)
                self.assertEqual(result["state"], "UNKNOWN")
                self.assertIsNone(result["recorded"])
                self.assertEqual(result["receipt_id"], self.receipt["id"])
                hook.assert_called_once()
        with patch.object(ingest, "record_receipt", side_effect=RuntimeError("hook failure")) as hook:
            result = materials._ledger(self.receipt)
            self.assertEqual(result["state"], "UNKNOWN")
            self.assertIsNone(result["recorded"])
            hook.assert_called_once()

    def test_contradictory_append_ack_never_authorizes_mirror(self):
        for status in (None, {"accepted": True, "duplicate": True},
                       {"accepted": True, "duplicate": False, "receipt_id": "different"},
                       {"accepted": True, "duplicate": False,
                        "receipt_id": self.receipt["id"], "state": "UNKNOWN"}):
            with self.subTest(status=status), patch.object(self.ledger, "append", return_value=status):
                result = ingest.record_receipt(self.receipt, organ="materials")
                self.assertEqual(result["state"], "UNKNOWN")
                self.assertFalse(result["accepted"])
                self.assertEqual(result["receipt_id"], self.receipt["id"])
                self.assertEqual(result["mirror"]["state"], "NOT_ATTEMPTED")
        self.mirror_mock.assert_not_called()

    def test_absent_unreadable_and_bounded_lookup_stay_unknown_without_writes(self):
        organ = "materials"
        self.assertEqual(self.ledger.lookup_receipt("absent", organ)["state"], "UNKNOWN")
        self.ledger.append(dict(self.receipt, organ=organ))
        before = self.fingerprint()
        for kwargs in ({"max_bytes": 1}, {"max_partitions": 0}):
            self.assertEqual(self.ledger.lookup_receipt(self.receipt["id"], organ, **kwargs)["state"], "UNKNOWN")
        with patch("builtins.open", side_effect=OSError("unreadable")):
            self.assertEqual(self.ledger.lookup_receipt(self.receipt["id"], organ)["state"], "UNKNOWN")
        self.assertEqual(self.fingerprint(), before)

    def test_readback_get_is_inert_and_does_not_disclose_payload(self):
        try:
            from fastapi import FastAPI
            from starlette.testclient import TestClient
        except ImportError:
            self.skipTest("mounted route dependencies unavailable in minimal checkout")
        organ = "materials"
        self.ledger.append(dict(self.receipt, organ=organ))
        app = FastAPI()
        with patch.object(ingest.threading, "Thread") as thread:
            ingest.register(app)
        before = self.fingerprint()
        with patch.object(self.ledger, "append", side_effect=AssertionError("read must not append")), \
             patch.object(ingest, "_mirror_to_dataset", side_effect=AssertionError("read must not mirror")):
            response = TestClient(app).get("/api/lake/v1/receipts",
                params={"organ": organ, "receipt_id": self.receipt["id"]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["state"], "LOCAL_PRESENT")
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertNotIn("payload", response.text)
        self.assertEqual(self.fingerprint(), before)


if __name__ == "__main__":
    unittest.main()
