#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Offline lifecycle regressions, collected by test_state_store_handover.py.

These use real SQLite capture/readback and the existing in-memory CAS backend.
The seven-store admission envelope is explicitly synthetic; no live durability
or provider recovery is claimed by these tests.
"""

import copy
import importlib.util
import json
import sys
import tempfile
import threading
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import a11oy_state_store as ss
from tests.state_store_support import FakeClock, FakeHeadBackend, make_db, replica


class TestStateStoreErrorLifecycle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Only the pure status validator is used. No verifier transport exists.
        requests = types.ModuleType("requests")
        requests.Session = requests.Response = object
        hub = types.ModuleType("huggingface_hub")
        hub.HfApi = object
        path = Path(__file__).resolve().parents[1] / ".github/scripts/verify_canonical_a11oy.py"
        spec = importlib.util.spec_from_file_location("storage_lifecycle_verifier", path)
        cls.verifier = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, requests=requests, huggingface_hub=hub):
            spec.loader.exec_module(cls.verifier)

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="state-error-lifecycle-")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.clock = FakeClock()
        self.objects = ss.LocalDirObjectStore(self.root / "bucket")
        self.backend = FakeHeadBackend()
        self.store = self.replica("a")
        self.store.boot()
        make_db(self.store.local_path("gdw"), 3)

    def replica(self, name):
        store = replica(self.root, name, self.objects, self.backend, self.clock)
        self.addCleanup(store._close_watchers)
        return store

    def fail_heartbeat(self, remote, body):
        if remote == ss.HEARTBEAT_PATH:
            raise ss.StorageBlocked("OBJECT_UNAVAILABLE")
        return self.put_bytes(remote, body)

    def publication_failure(self):
        self.backend.unreachable = True
        self.store.snapshot_once(force=True)
        self.backend.unreachable = False
        self.assertEqual(self.store.status()["pending_publish"], ["gdw"])
        self.assertIn("publish", self.store.status()["active_errors"])

    def recover_publication(self):
        self.clock.advance(301)
        self.store.snapshot_once()
        self.assertEqual(self.store.status()["pending_publish"], [])

    def assert_recovered(self, where):
        status = self.store.status()
        self.assertNotIn(where, status["active_errors"])
        self.assertIsNotNone(status["last_error_history"][where]["recovered_at"])
        return status

    def healthy_envelope(self):
        # Use the actual runtime's lease and errors, with synthetic evidence for
        # the six stores this focused SQLite fixture does not instantiate.
        self.store.snapshot_once(force=True)
        self.store.heartbeat_once()
        payload = self.store.status()
        payload["stores"] = {
            label: dict(payload["stores"]["gdw"], kind=kind,
                        integrity="lmdb_read" if kind == "lmdb" else "quick_check")
            for label, kind in self.verifier.STATE_STORE_KINDS.items()
        }
        self.verifier.validate_state_store_status(payload)
        return payload

    def test_publication_retry_clears_legacy_last_error_after_verified_recovery(self):
        self.backend.unreachable = True
        self.store.snapshot_once(force=True)
        self.assertEqual(self.store.last_error["where"], "publish")
        self.backend.unreachable = False
        self.clock.advance(301)
        self.store.snapshot_once()
        self.assertEqual(self.store.status()["pending_publish"], [])
        self.assertIsNone(self.store.status()["last_error"])

    def test_heartbeat_retry_clears_legacy_last_error_after_successful_upload(self):
        self.put_bytes = self.objects.put_bytes
        with patch.object(self.objects, "put_bytes", self.fail_heartbeat):
            self.store.heartbeat_once()
        self.assertEqual(self.store.last_error["where"], "heartbeat")
        self.clock.advance(15)
        self.store.heartbeat_once()
        self.assertEqual(self.store.status()["lease"]["heartbeat_age_s"], 0)
        self.assertIsNone(self.store.status()["last_error"])

    def test_publication_recovery_retains_history_and_clears_only_after_cas(self):
        self.publication_failure()
        error = self.store.last_error.copy()
        self.store.heartbeat_once()
        self.assertEqual(self.store.last_error, error)
        self.recover_publication()
        status = self.assert_recovered("publish")
        self.assertEqual(status["active_errors"], {})
        self.assertIsNone(status["last_error"])
        history = status["last_error_history"]["publish"]
        self.assertEqual({key: history[key] for key in error}, error)
        self.assertEqual(history["occurrences"], 1)

    def test_publish_success_cannot_clear_failed_heartbeat(self):
        self.publication_failure()
        self.put_bytes = self.objects.put_bytes
        with patch.object(self.objects, "put_bytes", self.fail_heartbeat):
            self.store.heartbeat_once()
        self.recover_publication()
        status = self.assert_recovered("publish")
        self.assertEqual(set(status["active_errors"]), {"heartbeat"})
        self.assertEqual(status["last_error"]["where"], "heartbeat")
        self.store.heartbeat_once()
        self.assertIsNone(self.assert_recovered("heartbeat")["last_error"])

    def test_heartbeat_success_cannot_clear_failed_publication(self):
        self.publication_failure()
        self.put_bytes = self.objects.put_bytes
        with patch.object(self.objects, "put_bytes", self.fail_heartbeat):
            self.store.heartbeat_once()
        self.store.heartbeat_once()
        status = self.assert_recovered("heartbeat")
        self.assertEqual(set(status["active_errors"]), {"publish"})
        self.assertEqual(status["last_error"]["where"], "publish")
        self.recover_publication()
        self.assertIsNone(self.store.last_error)

    def test_snapshot_upload_failure_requires_matching_capture(self):
        with patch.object(self.objects, "put_file", side_effect=ss.StorageBlocked("OBJECT_UNAVAILABLE")):
            self.store.snapshot_once(force=True)
        self.store.heartbeat_once()
        self.store.snapshot_once()  # Backoff and signature observation are not capture success.
        self.assertIn("snapshot:gdw", self.store.status()["active_errors"])
        self.assertEqual(self.store.status()["stores"]["gdw"]["snapshot_failures"], 1)
        self.store.snapshot_once(force=True)
        status = self.assert_recovered("snapshot:gdw")
        self.assertEqual(status["stores"]["gdw"]["snapshot_failures"], 0)
        self.assertIsNone(status["stores"]["gdw"]["last_error_code"])
        self.assertIsNone(status["last_error"])

    def test_readback_failure_requires_verified_readback(self):
        get_file = self.objects.get_file

        def corrupt(remote, local):
            get_file(remote, local)
            Path(local).write_bytes(b"offline corrupt readback")

        with patch.object(self.objects, "get_file", corrupt):
            self.store.snapshot_once(force=True)
        self.assertEqual(self.store.last_error["code"], "SNAPSHOT_READBACK_MISMATCH")
        self.assertEqual(self.backend.head()["snapshots"], {})
        self.store.snapshot_once(force=True)
        self.assertIsNone(self.assert_recovered("snapshot:gdw")["last_error"])
        self.assertIn("gdw", self.backend.head()["snapshots"])

    def test_capture_recovery_does_not_clear_new_publication_failure(self):
        with patch.object(self.objects, "put_file", side_effect=ss.StorageBlocked("OBJECT_UNAVAILABLE")):
            self.store.snapshot_once(force=True)
        self.backend.unreachable = True
        self.store.snapshot_once(force=True)
        status = self.assert_recovered("snapshot:gdw")
        self.assertEqual(set(status["active_errors"]), {"publish"})
        self.assertEqual(status["pending_publish"], ["gdw"])

    def test_successful_other_store_cannot_clear_snapshot_failure(self):
        make_db(self.store.local_path("series_a"), 2)
        put_file = self.objects.put_file

        def fail_gdw(local, remote):
            if "/gdw/" in remote:
                raise ss.StorageBlocked("OBJECT_UNAVAILABLE")
            return put_file(local, remote)

        with patch.object(self.objects, "put_file", fail_gdw):
            self.store.snapshot_once(force=True)
        status = self.store.status()
        self.assertEqual(set(status["active_errors"]), {"snapshot:gdw"})
        self.assertIn("series_a", self.backend.head()["snapshots"])
        self.assertNotIn("gdw", self.backend.head()["snapshots"])
        self.store.snapshot_once(force=True)
        self.assertIsNone(self.assert_recovered("snapshot:gdw")["last_error"])

    def test_missing_signature_is_not_recovery(self):
        signature = self.store._signature

        def fail_gdw(spec):
            if spec.label == "gdw":
                raise OSError("offline signature failure")
            return signature(spec)

        with patch.object(self.store, "_signature", fail_gdw):
            self.store.snapshot_once(force=True)
        self.store.heartbeat_once()
        with patch.object(self.store, "_signature", return_value=None):
            self.store.snapshot_once(force=True)
        self.assertIn("signature:gdw", self.store.status()["active_errors"])
        self.store.snapshot_once(force=True)
        self.assertIsNone(self.assert_recovered("signature:gdw")["last_error"])

    def test_head_observation_failure_is_not_recovered_by_upload_or_publish(self):
        self.backend.unreachable = True
        self.store.heartbeat_once()
        self.assertEqual(self.store.status()["lease"]["heartbeat_age_s"], 0)
        self.assertEqual(set(self.store.status()["active_errors"]), {"heartbeat-observe"})
        self.backend.unreachable = False
        old = self.store.head
        self.store.snapshot_once(force=True)
        self.assertIn("heartbeat-observe", self.store.status()["active_errors"])
        with patch.object(self.backend, "observe", return_value=old):
            self.store.heartbeat_once()
        self.assertIn("heartbeat-observe", self.store.status()["active_errors"])
        self.store.heartbeat_once()
        self.assertIsNone(self.assert_recovered("heartbeat-observe")["last_error"])

    def test_missing_authoritative_head_fences_instead_of_clearing_observation_error(self):
        self.backend.unreachable = True
        self.store.heartbeat_once()
        self.backend.unreachable = False
        with patch.object(self.backend, "observe", return_value=ss.Observation("f" * 40, None)):
            self.store.heartbeat_once()
        status = self.store.status()
        self.assertEqual(status["role"], ss.ROLE_FENCED)
        self.assertFalse(status["writable"])
        self.assertEqual(set(status["active_errors"]), {"heartbeat-observe", "lease"})
        self.assertIsNone(status["last_error_history"]["heartbeat-observe"]["recovered_at"])

    def test_repeated_failure_after_recovery_reopens_component_and_preserves_counts(self):
        self.put_bytes = self.objects.put_bytes
        with patch.object(self.objects, "put_bytes", self.fail_heartbeat):
            self.store.heartbeat_once()
        first = self.store.status()["last_error_history"]["heartbeat"]
        self.clock.advance(15)
        self.store.heartbeat_once()
        self.assert_recovered("heartbeat")
        self.clock.advance(15)
        with patch.object(self.objects, "put_bytes", self.fail_heartbeat):
            self.store.heartbeat_once()
        status = self.store.status()
        self.assertEqual(status["last_error"]["where"], "heartbeat")
        history = status["last_error_history"]["heartbeat"]
        self.assertEqual(history["first_at"], first["at"])
        self.assertEqual(history["occurrences"], 2)
        self.assertIsNone(history["recovered_at"])
        self.assertNotEqual(history["at"], first["at"])

    def test_repeated_error_remains_latest_when_another_component_recovers(self):
        self.store._error(ss.StorageBlocked("OBJECT_UNAVAILABLE"), "snapshot:gdw")
        self.store._error(ss.StorageBlocked("STATE_DATASET_UNREACHABLE"), "publish")
        self.store._error(ss.StorageBlocked("OBJECT_UNAVAILABLE"), "snapshot:gdw")
        self.store._error(ss.StorageBlocked("OBJECT_UNAVAILABLE"), "heartbeat")
        self.store.heartbeat_once()
        self.assertEqual(self.store.last_error["where"], "snapshot:gdw")
        self.assertEqual(len(self.store.status()["last_error_history"]), 3)

    def test_fenced_and_blocked_roles_never_recover_on_noop(self):
        for role in (ss.ROLE_FENCED, ss.ROLE_BLOCKED):
            with self.subTest(role=role):
                self.store._error(ss.StorageBlocked("STATE_DATASET_UNREACHABLE"), "publish")
                self.store._fence("WRITER_FENCED")
                self.store.role = role
                before = self.store.status()
                self.store.heartbeat_once()
                self.store.snapshot_once(force=True)
                after = self.store.status()
                self.assertFalse(after["writable"])
                self.assertTrue(after["alert"])
                self.assertEqual(after["active_errors"], before["active_errors"])
                self.assertEqual(after["last_error_history"], before["last_error_history"])

    def test_quiesce_and_failed_final_capture_remain_terminal(self):
        def fail_quiesce():
            raise RuntimeError("offline quiesce failure")

        self.store.add_quiesce_hook(fail_quiesce)
        self.store._release(self.store.head)
        status = self.store.status()
        self.assertEqual(status["role"], ss.ROLE_FENCED)
        self.assertEqual(set(status["active_errors"]), {"quiesce", "lease"})
        self.assertNotEqual(self.backend.head()["state"], ss.STATE_RELEASED)
        self.store.heartbeat_once()
        self.assertEqual(self.store.status()["active_errors"], status["active_errors"])

    def test_failed_final_snapshot_retains_capture_and_release_evidence(self):
        with patch.object(self.objects, "put_file", side_effect=ss.StorageBlocked("OBJECT_UNAVAILABLE")):
            self.store._release(self.store.head)
        status = self.store.status()
        self.assertEqual(status["role"], ss.ROLE_FENCED)
        self.assertEqual(set(status["active_errors"]), {"snapshot:gdw", "release", "lease"})
        self.assertEqual(status["last_error"]["code"], "STATE_FINAL_SNAPSHOT_INCOMPLETE")
        self.store.heartbeat_once()
        self.store.snapshot_once(force=True)
        self.assertEqual(self.store.status()["active_errors"], status["active_errors"])

    def test_transient_boot_recovery_clears_only_boot_retry(self):
        # A fresh first boot has no active writer to wait for.
        backend = FakeHeadBackend()
        store = replica(self.root, "boot", self.objects, backend, self.clock)
        self.addCleanup(store._close_watchers)
        backend.unreachable = True
        self.clock.on_sleep.append(lambda: setattr(backend, "unreachable", False))
        store.boot()
        status = store.status()
        self.assertEqual(status["role"], ss.ROLE_WRITER)
        self.assertEqual(status["active_errors"], {})
        self.assertIsNone(status["last_error"])
        self.assertIsNotNone(status["last_error_history"]["boot-retry"]["recovered_at"])
        self.assertIsNone(status["lease"]["heartbeat_age_s"])
        with self.assertRaises(self.verifier.RelockError):
            self.verifier.validate_state_store_status(status)

    def test_boot_deadline_failure_stays_blocked_after_provider_recovers(self):
        backend = FakeHeadBackend()
        store = replica(self.root, "deadline", self.objects, backend, self.clock, boot_deadline_s=2)
        self.addCleanup(store._close_watchers)
        backend.unreachable = True
        with self.assertRaises(ss.StorageBlocked):
            store.boot()
        backend.unreachable = False
        before = store.status()
        store.heartbeat_once()
        store.snapshot_once(force=True)
        self.assertEqual(store.status()["active_errors"], before["active_errors"])
        self.assertEqual(store.role, ss.ROLE_BLOCKED)
        self.assertFalse(store.writable())

    def test_new_process_requires_its_own_heartbeat_and_snapshot_health(self):
        self.publication_failure()
        self.recover_publication()
        self.store.close()
        successor = self.replica("successor")
        successor.boot()
        status = successor.status()
        self.assertEqual(status["active_errors"], {})
        self.assertEqual(status["last_error_history"], {})
        self.assertIsNone(status["lease"]["heartbeat_age_s"])
        self.assertEqual(status["stores"]["gdw"]["origin"], ss.ORIGIN_RESTORED)
        with self.assertRaises(self.verifier.RelockError):
            self.verifier.validate_state_store_status(status)
        self.assertIsNotNone(self.store.status()["last_error_history"]["publish"]["recovered_at"])

    def test_unactivated_status_does_not_claim_observed_health(self):
        with patch.object(ss, "_ACTIVE", None), patch.dict("os.environ", {ss.ENABLE_ENV: ss.ENABLED_VALUE}):
            status = ss.status()
        self.assertIsNone(status["active_errors"])
        self.assertEqual(status["role"], ss.ROLE_NOT_ACTIVATED)
        self.assertFalse(status["writable"])
        with self.assertRaises(self.verifier.RelockError):
            self.verifier.validate_state_store_status(status)

    def test_status_reads_do_not_clear_errors_or_expose_mutable_diagnostics(self):
        self.publication_failure()
        before = self.store.status()
        with patch.object(self.objects, "put_bytes", side_effect=AssertionError("status cannot write")), \
                patch.object(self.backend, "observe", side_effect=AssertionError("status cannot observe")), \
                patch.object(self.backend, "submit", side_effect=AssertionError("status cannot submit")):
            changed = self.store.status()
            changed["last_error"]["code"] = "caller mutation"
            changed["active_errors"]["publish"]["code"] = "caller mutation"
            changed["last_error_history"]["publish"]["recovered_at"] = "caller mutation"
            self.assertEqual(self.store.status(), before)

    def test_existing_verifier_accepts_recovery_but_rejects_missing_or_stale_health(self):
        self.publication_failure()
        self.recover_publication()
        payload = self.healthy_envelope()
        self.assertIsNotNone(payload["last_error_history"]["publish"]["recovered_at"])
        for change in (
            lambda item: item.pop("lease"),
            lambda item: item["lease"].update(heartbeat_age_s=None),
            lambda item: item["lease"].update(heartbeat_age_s=121),
            lambda item: item["stores"].pop("gdw"),
            lambda item: item["stores"]["gdw"].update(health=None),
            lambda item: item["stores"]["gdw"].update(sha16=None),
            lambda item: item["stores"]["gdw"].update(last_snapshot_age_s=901),
        ):
            with self.subTest(change=change):
                broken = copy.deepcopy(payload)
                change(broken)
                with self.assertRaises(self.verifier.RelockError):
                    self.verifier.validate_state_store_status(broken)
        self.put_bytes = self.objects.put_bytes
        with patch.object(self.objects, "put_bytes", self.fail_heartbeat):
            self.store.heartbeat_once()
        payload.update({key: self.store.status()[key] for key in ("last_error", "active_errors")})
        with self.assertRaises(self.verifier.RelockError):
            self.verifier.validate_state_store_status(payload)

    def test_unmatched_repair_errors_are_never_cleared_by_other_success(self):
        self.store._error(RuntimeError("sensitive-path-must-not-appear"), "close")
        self.store._error(ss.StorageBlocked("OBJECT_UNAVAILABLE"), "repair-receipt:gdw")
        self.store.heartbeat_once()
        self.store.snapshot_once(force=True)
        status = self.store.status()
        self.assertEqual(set(status["active_errors"]), {"close", "repair-receipt:gdw"})
        self.assertNotIn("sensitive-path-must-not-appear", json.dumps(status))

    def test_status_remains_available_while_provider_io_is_stalled(self):
        started, release, finished = threading.Event(), threading.Event(), threading.Event()
        put_bytes = self.objects.put_bytes

        def stalled(remote, body):
            if remote == ss.HEARTBEAT_PATH:
                started.set()
                if not release.wait(5):
                    raise RuntimeError("offline test release timed out")
            return put_bytes(remote, body)

        result = []
        def read_status():
            result.append(self.store.status())
            finished.set()

        with patch.object(self.objects, "put_bytes", stalled):
            heartbeat = threading.Thread(target=self.store.heartbeat_once)
            heartbeat.start()
            self.assertTrue(started.wait(2))
            reader = threading.Thread(target=read_status)
            reader.start()
            try:
                self.assertTrue(finished.wait(1), "status must not wait for provider I/O")
                self.assertIsNone(result[0]["lease"]["heartbeat_age_s"])
            finally:
                release.set()
                heartbeat.join(2)
                reader.join(2)
            self.assertFalse(heartbeat.is_alive())
            self.assertFalse(reader.is_alive())

    def run_ticks(self, count):
        ticks = 0
        def wait(_timeout):
            nonlocal ticks
            ticks += 1
            self.clock.advance(15)
            return ticks > count
        with patch.object(self.store._stop, "wait", wait):
            self.store._run()

    def test_snapshot_work_directory_failure_is_attributed_and_recovers(self):
        with patch.object(self.store, "_work", side_effect=OSError("offline scratch unavailable")):
            self.store.snapshot_once(force=True)
        self.assertEqual(set(self.store.status()["active_errors"]), {"snapshot:gdw"})
        self.store.snapshot_once(force=True)
        self.assertIsNone(self.assert_recovered("snapshot:gdw")["last_error"])

    def test_unexpected_snapshot_loop_failure_requires_complete_capture_and_publication(self):
        signature = self.store._signature
        failed = False
        def once(spec):
            nonlocal failed
            if not failed:
                failed = True
                raise RuntimeError("offline unexpected signature failure")
            return signature(spec)
        with patch.object(self.store, "_signature", once):
            self.run_ticks(1)
        self.assertIn("snapshot-loop", self.store.status()["active_errors"])
        with patch.object(self.objects, "put_file", side_effect=ss.StorageBlocked("OBJECT_UNAVAILABLE")):
            self.store.snapshot_once()
        self.assertIn("snapshot-loop", self.store.status()["active_errors"])
        self.clock.advance(301)
        self.backend.unreachable = True
        self.store.snapshot_once()
        self.assertIn("snapshot-loop", self.store.status()["active_errors"])
        self.backend.unreachable = False
        self.store.snapshot_once()
        self.assertIn("snapshot-loop", self.store.status()["active_errors"])
        self.clock.advance(301)
        self.store.snapshot_once()
        status = self.assert_recovered("snapshot-loop")
        self.assertEqual(status["active_errors"], {})
        self.assertIn("gdw", self.backend.head()["snapshots"])

    def test_missing_published_store_cannot_clear_snapshot_loop_failure(self):
        self.store.snapshot_once(force=True)
        self.store._error(RuntimeError("offline unexpected failure"), "snapshot-loop")
        make_db(self.store.local_path("series_a"), 2)
        signature = self.store._signature
        def missing(spec):
            return None if spec.label == "gdw" else signature(spec)
        with patch.object(self.store, "_signature", missing):
            self.store.snapshot_once()
        self.assertIn("snapshot-loop", self.store.status()["active_errors"])
        self.store.snapshot_once()
        self.assertIsNone(self.assert_recovered("snapshot-loop")["last_error"])

    def test_unexpected_heartbeat_loop_failure_requires_upload_and_authoritative_observation(self):
        with patch.object(self.store, "_on_head_changed", side_effect=RuntimeError("offline head handling failure")):
            self.run_ticks(1)
        self.assertIn("heartbeat-loop", self.store.status()["active_errors"])
        self.backend.unreachable = True
        self.store.heartbeat_once()
        self.assertIn("heartbeat-loop", self.store.status()["active_errors"])
        self.backend.unreachable = False
        self.put_bytes = self.objects.put_bytes
        with patch.object(self.objects, "put_bytes", self.fail_heartbeat):
            self.store.heartbeat_once()
        self.assertIn("heartbeat-loop", self.store.status()["active_errors"])
        self.store.heartbeat_once()
        self.assertIsNone(self.assert_recovered("heartbeat-loop")["last_error"])

    def test_disappearing_source_between_signature_and_capture_is_not_recovery(self):
        self.store._error(RuntimeError("offline unexpected failure"), "snapshot-loop")
        signature = self.store._signature
        calls = 0
        def disappears(spec):
            nonlocal calls
            if spec.label == "gdw":
                calls += 1
                if calls > 1:
                    return None
            return signature(spec)
        with patch.object(self.store, "_signature", disappears):
            self.store.snapshot_once()
        self.assertEqual(set(self.store.status()["active_errors"]), {"snapshot-loop", "signature:gdw"})
        self.assertEqual(self.store.last_error["code"], "STATE_STORE_SOURCE_MISSING")
        self.store.snapshot_once()
        self.assertIsNone(self.assert_recovered("snapshot-loop")["last_error"])

    def test_empty_pass_does_not_recover_an_unexpected_snapshot_failure(self):
        self.store._error(RuntimeError("offline unexpected failure"), "snapshot-loop")
        with patch.object(self.store, "_signature", return_value=None):
            self.store.snapshot_once()
        self.assertIn("snapshot-loop", self.store.status()["active_errors"])
        self.store.snapshot_once()
        self.assertIsNone(self.assert_recovered("snapshot-loop")["last_error"])

    def test_unfenced_manifest_retries_without_changed_database_bytes(self):
        for loop_failure in (False, True):
            with self.subTest(loop_failure=loop_failure):
                objects = ss.LocalDirObjectStore(self.root / f"unfenced-bucket-{loop_failure}")
                store = replica(self.root, f"unfenced-{loop_failure}", objects, None, self.clock)
                self.addCleanup(store._close_watchers)
                store.boot()
                make_db(store.local_path("gdw"), 2)
                if loop_failure:
                    store._error(RuntimeError("offline unexpected failure"), "snapshot-loop")
                put_bytes = objects.put_bytes
                attempts = []
                def fail_manifest(remote, body):
                    if remote == ss.UNFENCED_HEAD_PATH:
                        attempts.append(remote)
                        raise ss.StorageBlocked("OBJECT_UNAVAILABLE")
                    return put_bytes(remote, body)
                with patch.object(objects, "put_bytes", fail_manifest):
                    store.snapshot_once(force=True)
                    store.snapshot_once()
                self.assertEqual(len(attempts), 1, "backoff must apply to loop recovery too")
                self.assertIn("unfenced-head", store.status()["active_errors"])
                self.clock.advance(301)
                store.snapshot_once()
                status = store.status()
                self.assertEqual(status["active_errors"], {})
                self.assertIsNone(status["last_error"])
                self.assertIsNotNone(status["last_error_history"]["unfenced-head"]["recovered_at"])
                self.assertEqual(status["mode"], ss.MODE_UNFENCED)
                with self.assertRaises(self.verifier.RelockError):
                    self.verifier.validate_state_store_status(status)


if __name__ == "__main__":
    unittest.main()
