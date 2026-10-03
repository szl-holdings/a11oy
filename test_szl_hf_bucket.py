# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - Doctrine v11
#
# Network-free stdlib self-test for szl_hf_bucket.py.
#
# Proves the foundation contract WITHOUT touching Hugging Face:
#   * idempotent append (same content -> exactly one stored entry)
#   * dedup-id stability (id derived from content, not timestamp)
#   * queue-on-failure + flush (HF unreachable -> queued + honest status; later
#     flush drains the queue; no fabricated success)
#   * retry/backoff on transient 429/5xx then recovery
#   * recent/all read shape + head/chain-state
#
# Run by file path (the module is shipped flat next to serve.py):
#   python3 test_szl_hf_bucket.py
#
import json
import os
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from szl_hf_bucket import BucketError, HFBucket, Transport, SCHEMA, _HFTransport  # noqa: E402


class _HTTPError(Exception):
    def __init__(self, status_code):
        super().__init__("HTTP %s" % status_code)
        self.status_code = status_code


class FakeTransport(Transport):
    """In-memory append-only repo. Can be told to fail N times (transient) or
    raise a permanent connection error to simulate HF being unreachable."""

    def __init__(self):
        self.files = {}            # path -> bytes
        self.commits = 0
        self.fail_reads = 0        # transient read failures remaining
        self.fail_commits = 0      # transient commit failures remaining
        self.unreachable = False   # hard failure (offline)
        self.read_status = 503
        self.commit_status = 429
        self.tip = "0" * 40
        self.versions = {}
        self.snapshots = []
        self.read_revisions = []
        self.list_revisions = []
        self.parents = []
        self.before_commit = None
        self.after_snapshot = None
        self.lost_responses = 0
        self.empty_responses = 0
        self.offline_after_commit = False

    def snapshot(self):
        if self.unreachable:
            raise ConnectionError("network is unreachable")
        tip = self.tip
        self.versions[tip] = dict(self.files)
        self.snapshots.append(tip)
        if self.after_snapshot:
            callback, self.after_snapshot = self.after_snapshot, None
            callback()
        return tip

    def read_file(self, path, *, revision=None):
        if self.unreachable:
            raise ConnectionError("network is unreachable")
        if self.fail_reads > 0:
            self.fail_reads -= 1
            raise _HTTPError(self.read_status)
        self.read_revisions.append(revision)
        return (self.versions[revision] if revision is not None else self.files).get(path)

    def list_files(self, prefix, *, revision=None):
        if self.unreachable:
            raise ConnectionError("network is unreachable")
        pref = prefix.rstrip("/") + "/"
        self.list_revisions.append(revision)
        files = self.versions[revision] if revision is not None else self.files
        return sorted(p for p in files if p.startswith(pref))

    def commit(self, operations, message, *, parent_commit):
        self.parents.append(parent_commit)
        if self.before_commit:
            callback, self.before_commit = self.before_commit, None
            callback()
        if self.unreachable:
            raise ConnectionError("network is unreachable")
        if parent_commit != self.tip:
            raise _HTTPError(409)
        if self.fail_commits > 0:
            self.fail_commits -= 1
            raise _HTTPError(self.commit_status)
        for path, blob in operations:
            self.files[path] = blob
        self.commits += 1
        self.tip = "%040x" % self.commits
        if self.offline_after_commit:
            self.unreachable = True
            raise ConnectionError("response lost after commit")
        if self.lost_responses:
            self.lost_responses -= 1
            raise _HTTPError(503)
        if self.empty_responses:
            self.empty_responses -= 1
            return ""
        return self.tip


def _mk(tmp, transport, **kw):
    kw.setdefault("repo_id", "SZLHOLDINGS/test-bucket")
    kw.setdefault("source", "selftest")
    kw.setdefault("queue_dir", tmp)
    kw.setdefault("transport", transport)
    kw.setdefault("backoff_base", 0.0)   # no real sleeping in tests
    kw.setdefault("max_backoff", 0.0)
    kw.setdefault("sleep", lambda s: None)
    return HFBucket(**kw)


class BucketSelfTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="hfbtest_")
        self.addCleanup(temporary.cleanup)
        self._tmp = temporary.name

    def test_idempotent_append_one_entry(self):
        t = FakeTransport()
        b = _mk(self._tmp, t)
        r1 = b.append({"hello": "world"}, kind="greeting")
        r2 = b.append({"hello": "world"}, kind="greeting")  # same content
        self.assertEqual(r1["queued"], 1)
        self.assertEqual(r2["queued"], 0)
        self.assertEqual(r2["duplicates"], 1)
        self.assertEqual(r1["ids"], r2["ids"])  # dedup id stable
        out = b.flush_queue(force=True)
        self.assertEqual(out.get("committed"), 1)
        # Re-append identical content AFTER commit: still exactly one stored.
        b.append({"hello": "world"}, kind="greeting")
        b.flush_queue(force=True)
        allrecs = b.read_all()
        same = [r for r in allrecs if r.get("kind") == "greeting"]
        self.assertEqual(len(same), 1, "identical content must store exactly once")

    def test_dedup_id_stability_ignores_timestamp(self):
        t = FakeTransport()
        b = _mk(self._tmp, t)
        a = b.make_record({"x": 1}, kind="k", ts="2026-01-01T00:00:00.000000Z")
        c = b.make_record({"x": 1}, kind="k", ts="2026-12-31T23:59:59.000000Z")
        self.assertEqual(a["id"], c["id"], "id must depend on content, not ts")
        d = b.make_record({"x": 2}, kind="k")
        self.assertNotEqual(a["id"], d["id"])
        # explicit dedup_key overrides payload-based hashing
        e = b.make_record({"x": 1, "noise": 9}, kind="k", dedup_key={"x": 1})
        self.assertEqual(a["id"], e["id"])

    def test_queue_on_failure_then_flush(self):
        t = FakeTransport()
        t.unreachable = True
        b = _mk(self._tmp, t)
        res = b.append({"n": 1})  # offline: must NOT raise
        self.assertTrue(res["ok"])
        out = b.flush_queue(force=True)
        self.assertEqual(b.status()["state"], "unreachable")
        self.assertIsNotNone(b.status()["last_error"])
        self.assertEqual(t.commits, 0, "must not fabricate a commit while offline")
        self.assertEqual(out["pending"], 1)
        # Recovery: HF reachable again -> flush drains the queue.
        t.unreachable = False
        out2 = b.flush_queue(force=True)
        self.assertEqual(out2.get("committed"), 1)
        self.assertEqual(b.status()["state"], "idle")
        self.assertEqual(b.status()["pending"], 0)
        self.assertEqual(len(b.read_all()), 1)

    def test_retry_backoff_on_transient_then_success(self):
        t = FakeTransport()
        t.fail_commits = 2  # first two commit attempts 429, third succeeds
        b = _mk(self._tmp, t, max_retries=4)
        b.append({"n": 1})
        out = b.flush_queue(force=True)
        self.assertEqual(out.get("committed"), 1)
        self.assertEqual(t.commits, 1)
        self.assertEqual(b.status()["state"], "idle")

    def test_retry_gives_up_after_max_then_queues(self):
        t = FakeTransport()
        t.fail_commits = 99  # always transient-fail
        b = _mk(self._tmp, t, max_retries=3)
        b.append({"n": 1})
        out = b.flush_queue(force=True)
        self.assertEqual(out["pending"], 1)
        self.assertEqual(b.status()["state"], "unreachable")
        self.assertEqual(t.commits, 0)

    def test_read_recent_and_all_shape(self):
        t = FakeTransport()
        b = _mk(self._tmp, t)
        for i in range(5):
            b.append({"i": i}, kind="num")
        b.flush_queue(force=True)
        recent = b.read_recent(3)
        self.assertEqual(len(recent), 3)
        for r in recent:
            self.assertEqual(r["schema"], SCHEMA)
            self.assertIn("id", r)
            self.assertIn("ts", r)
            self.assertIn("payload", r)
        allrecs = b.read_all()
        self.assertEqual(len(allrecs), 5)

    def test_head_chain_state(self):
        t = FakeTransport()
        b = _mk(self._tmp, t)
        b.append_many([{"i": i} for i in range(3)], kind="num")
        b.flush_queue(force=True)
        h = b.head()
        self.assertEqual(h["count"], 3)
        self.assertIsNotNone(h["last_id"])
        self.assertEqual(h["pending"], 0)
        self.assertTrue(any(s.endswith(".ndjson") for s in h["shards"]))

    def test_append_many_dedup_within_batch(self):
        t = FakeTransport()
        b = _mk(self._tmp, t)
        res = b.append_many([{"v": 1}, {"v": 1}, {"v": 2}], kind="k")
        self.assertEqual(res["queued"], 2)
        self.assertEqual(res["duplicates"], 1)
        b.flush_queue(force=True)
        self.assertEqual(len(b.read_all()), 2)

    def test_no_token_does_not_raise_on_append(self):
        # Construction + append must not require a token or network.
        t = FakeTransport()
        b = _mk(self._tmp, t, token=None)
        r = b.append({"safe": True})
        self.assertTrue(r["ok"])

    def test_persistence_across_instances(self):
        # A second instance pointed at the same queue dir drains what the first
        # queued while offline (durable on-disk queue).
        t = FakeTransport()
        t.unreachable = True
        b1 = _mk(self._tmp, t)
        b1.append({"durable": 1})
        self.assertEqual(b1.status()["pending"], 1)
        t2 = t
        t2.unreachable = False
        b2 = _mk(self._tmp, t2)
        self.assertEqual(b2.status()["pending"], 1)  # saw the queued file
        b2.flush_queue(force=True)
        self.assertEqual(len(b2.read_all()), 1)


class BucketSnapshotTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="hfbsnapshot_")
        self.addCleanup(temporary.cleanup)
        self._tmp = temporary.name

    def _two_writers(self, *, other_day=None):
        transport = FakeTransport()
        first = _mk(os.path.join(self._tmp, "first"), transport, source="first")
        second = _mk(os.path.join(self._tmp, "second"), transport, source="second")
        first.append(first.make_record({"writer": 1}, ts="2026-01-02T00:00:00Z"))
        second.append(second.make_record(
            {"writer": 2}, ts=(other_day or "2026-01-02") + "T00:00:00Z"
        ))
        return transport, first, second

    def _assert_count(self, transport, expected):
        head = json.loads(transport.files["data/head.json"])
        actual = sum(
            len([line for line in transport.files[path].splitlines() if line.strip()])
            for path in head["shards"]
        )
        self.assertEqual(head["count"], actual)
        self.assertEqual(actual, expected)

    def test_same_shard_conflict_remerges_both_writers(self):
        t, first, second = self._two_writers()
        t.before_commit = lambda: second.flush_queue(force=True)
        out = first.flush_queue(force=True)
        self.assertEqual(out["committed"], 1)
        self.assertEqual(out["pending"], 0)
        self.assertEqual(t.commits, 2)
        self.assertEqual({r["source"] for r in first.read_all()}, {"first", "second"})
        self._assert_count(t, 2)
        self.assertNotEqual(t.parents[0], t.parents[-1])

    def test_snapshot_stays_pinned_when_main_moves_before_reads(self):
        t, first, second = self._two_writers()
        t.after_snapshot = lambda: second.flush_queue(force=True)
        out = first.flush_queue(force=True)
        self.assertEqual(out["pending"], 0)
        self.assertEqual(t.commits, 2)
        self.assertTrue(all(rev is not None for rev in t.read_revisions))
        self.assertTrue(all(rev is not None for rev in t.list_revisions))
        self.assertEqual(set(t.read_revisions), set(t.snapshots))
        self._assert_count(t, 2)

    def test_new_peer_shard_is_in_rebuilt_head(self):
        t, first, second = self._two_writers(other_day="2026-01-03")
        t.before_commit = lambda: second.flush_queue(force=True)
        first.flush_queue(force=True)
        self.assertEqual(
            json.loads(t.files["data/head.json"])["shards"],
            ["data/2026-01-02.ndjson", "data/2026-01-03.ndjson"],
        )
        self._assert_count(t, 2)

    def test_conflict_exhaustion_retains_queue_and_no_success(self):
        t = FakeTransport()
        t.fail_commits, t.commit_status = 99, 409
        b = _mk(self._tmp, t, max_retries=3)
        b.append({"n": 1})
        out = b.flush_queue(force=True)
        self.assertEqual(out["pending"], 1)
        self.assertEqual(out["state"], "unreachable")
        self.assertIsNone(out["last_commit"])
        self.assertEqual(len(t.snapshots), 3)
        self.assertEqual(t.commits, 0)

    def test_lost_response_reconciles_without_replaying_replacement(self):
        t = FakeTransport()
        t.lost_responses = 1
        b = _mk(self._tmp, t)
        b.append({"n": 1})
        out = b.flush_queue(force=True)
        self.assertEqual(out["committed"], 0)
        self.assertEqual(out["deduped"], 1)
        self.assertEqual(out["pending"], 0)
        self.assertIsNone(out["last_commit"])
        self.assertEqual(t.commits, 1)
        self.assertEqual(len(t.parents), 1)
        self._assert_count(t, 1)

    def test_empty_commit_response_is_reconciled_as_ambiguous(self):
        t = FakeTransport()
        t.empty_responses = 1
        b = _mk(self._tmp, t)
        b.append({"n": 1})
        out = b.flush_queue(force=True)
        self.assertEqual(out["deduped"], 1)
        self.assertEqual(out["pending"], 0)
        self.assertIsNone(out["last_commit"])
        self.assertEqual(t.commits, 1)

    def test_lost_response_does_not_overwrite_later_peer_append(self):
        t, first, second = self._two_writers()
        t.lost_responses = 1

        def arrange_later_writer():
            t.after_snapshot = lambda: second.flush_queue(force=True)

        t.before_commit = arrange_later_writer
        out = first.flush_queue(force=True)
        self.assertEqual(out["deduped"], 1)
        self.assertEqual(out["pending"], 0)
        self.assertEqual(t.commits, 2)
        self._assert_count(t, 2)
        self.assertEqual({r["source"] for r in first.read_all()}, {"first", "second"})

    def test_lost_response_and_unreadable_head_keeps_queue_until_recovery(self):
        t = FakeTransport()
        t.offline_after_commit = True
        b = _mk(self._tmp, t)
        b.append({"n": 1})
        out = b.flush_queue(force=True)
        self.assertEqual(out["pending"], 1)
        self.assertEqual(out["state"], "unreachable")
        self.assertIsNone(out["last_commit"])
        self.assertEqual(t.commits, 1)
        t.unreachable, t.offline_after_commit = False, False
        recovered = b.flush_queue(force=True)
        self.assertEqual(recovered["deduped"], 1)
        self.assertEqual(recovered["pending"], 0)
        self.assertEqual(t.commits, 1)

    def test_commit_denial_is_not_retried(self):
        t = FakeTransport()
        t.fail_commits, t.commit_status = 99, 403
        b = _mk(self._tmp, t)
        b.append({"n": 1})
        self.assertEqual(b.flush_queue(force=True)["pending"], 1)
        self.assertEqual(len(t.snapshots), 1)
        self.assertEqual(t.commits, 0)

    def test_missing_snapshot_contract_cannot_fall_back_to_unguarded_write(self):
        t = FakeTransport()
        t.snapshot = lambda: "main"
        b = _mk(self._tmp, t)
        b.append({"n": 1})
        out = b.flush_queue(force=True)
        self.assertEqual(out["pending"], 1)
        self.assertEqual(out["state"], "unreachable")
        self.assertEqual(t.parents, [])
        self.assertEqual(t.read_revisions, [])

    def test_listing_failure_never_drops_untouched_shards_from_head(self):
        t, first, second = self._two_writers(other_day="2026-01-03")
        second.flush_queue(force=True)
        before = dict(t.files)
        t.list_files = Mock(side_effect=_HTTPError(404))
        out = first.flush_queue(force=True)
        self.assertEqual(out["pending"], 1)
        self.assertEqual(t.files, before)
        self.assertEqual(t.list_files.call_count, 1)

    def test_existing_shard_bytes_are_preserved_including_whitespace(self):
        t = FakeTransport()
        old = b'  {"id": "older", "ts": "2026-01-02T00:00:00Z"}  \r\n\r\n'
        t.files["data/2026-01-02.ndjson"] = old
        b = _mk(self._tmp, t)
        b.append(b.make_record({"n": 1}, ts="2026-01-02T00:00:01Z"))
        b.flush_queue(force=True)
        self.assertTrue(t.files["data/2026-01-02.ndjson"].startswith(old))
        self._assert_count(t, 2)

    def test_invalid_existing_shard_is_never_replaced(self):
        for blob in (b'{"id":"older"}\ninvalid\n', b"\xff\n", b"[]\n"):
            with self.subTest(blob=blob):
                t = FakeTransport()
                t.files["data/2026-01-02.ndjson"] = blob
                b = _mk(self._tmp, t)
                b.append(b.make_record({"n": 1}, ts="2026-01-02T00:00:00Z"))
                out = b.flush_queue(force=True)
                self.assertEqual(out["pending"], 1)
                self.assertEqual(t.files["data/2026-01-02.ndjson"], blob)
                self.assertEqual(t.commits, 0)
                self.assertEqual(len(t.snapshots), 1)

    def test_listed_shard_missing_at_snapshot_is_not_empty(self):
        t = FakeTransport()
        t.list_files = lambda prefix, **kwargs: ["data/2026-01-02.ndjson"]
        b = _mk(self._tmp, t)
        b.append(b.make_record({"n": 1}, ts="2026-01-02T00:00:00Z"))
        self.assertEqual(b.flush_queue(force=True)["pending"], 1)
        self.assertEqual(t.commits, 0)


class HFTransportContractTest(unittest.TestCase):
    def setUp(self):
        self.transport = _HFTransport("org/bucket", None, revision="release")
        self.api = Mock()
        self.transport._api = self.api
        self.sha = "a" * 40

    def test_resolves_exact_sha_and_passes_parent_guard_to_sdk(self):
        self.api.repo_info.return_value = types.SimpleNamespace(sha=self.sha)
        self.assertEqual(self.transport.snapshot(), self.sha)
        self.api.repo_info.assert_called_once_with(
            repo_id="org/bucket", repo_type="dataset", revision="release", token=None,
        )
        self.api.list_repo_files.return_value = ["data/a.ndjson"]
        self.transport.list_files("data", revision=self.sha)
        self.assertEqual(self.api.list_repo_files.call_args.kwargs["revision"], self.sha)
        with tempfile.NamedTemporaryFile(delete=False) as handle:
            handle.write(b"existing")
            filename = handle.name
        self.addCleanup(os.remove, filename)
        self.api.hf_hub_download.return_value = filename
        self.assertEqual(self.transport.read_file("data/a.ndjson", revision=self.sha), b"existing")
        self.assertEqual(self.api.hf_hub_download.call_args.kwargs["revision"], self.sha)
        sdk = types.ModuleType("huggingface_hub")
        sdk.CommitOperationAdd = Mock()
        self.api.create_commit.return_value = types.SimpleNamespace(oid="b" * 40)
        with patch.dict(sys.modules, {"huggingface_hub": sdk}):
            self.assertEqual(
                self.transport.commit([("data/a.ndjson", b"new")], "append", parent_commit=self.sha),
                "b" * 40,
            )
        kwargs = self.api.create_commit.call_args.kwargs
        self.assertEqual(kwargs["parent_commit"], self.sha)
        self.assertEqual(kwargs["revision"], "release")
        self.assertIs(kwargs["create_pr"], False)

    def test_only_file_entry_not_found_is_empty(self):
        for name in ("EntryNotFoundError", "RemoteEntryNotFoundError"):
            self.api.hf_hub_download.side_effect = type(name, (Exception,), {})()
            self.assertIsNone(self.transport.read_file("data/new.ndjson", revision=self.sha))
        for name in ("RepositoryNotFoundError", "RevisionNotFoundError", "HTTPError"):
            error = type(name, (Exception,), {})()
            error.response = types.SimpleNamespace(status_code=404)
            self.api.hf_hub_download.side_effect = error
            with self.assertRaises(BucketError):
                self.transport.read_file("data/new.ndjson", revision=self.sha)
            self.api.list_repo_files.side_effect = error
            with self.assertRaises(BucketError):
                self.transport.list_files("data", revision=self.sha)

    def test_invalid_snapshot_and_parent_are_denied_before_write(self):
        for sha in (None, "", "main", "a" * 7):
            self.api.repo_info.return_value = types.SimpleNamespace(sha=sha)
            with self.assertRaises(BucketError):
                self.transport.snapshot()
            with self.assertRaises(BucketError):
                self.transport.commit([], "append", parent_commit=sha)
        self.api.create_commit.assert_not_called()

    def test_wrapped_sdk_conflict_restarts_snapshot_and_parent_guard(self):
        self._sdk_conflict_refreshes_parent(409)

    def test_wrapped_sdk_precondition_conflict_refreshes_parent(self):
        self._sdk_conflict_refreshes_parent(412)

    def _sdk_conflict_refreshes_parent(self, status):
        new_sha = "b" * 40
        self.api.repo_info.side_effect = [
            types.SimpleNamespace(sha=self.sha), types.SimpleNamespace(sha=new_sha),
        ]
        self.api.list_repo_files.return_value = []
        self.api.hf_hub_download.side_effect = type("EntryNotFoundError", (Exception,), {})()
        self.api.create_commit.side_effect = [
            _HTTPError(status), types.SimpleNamespace(oid="c" * 40),
        ]
        sdk = types.ModuleType("huggingface_hub")
        sdk.CommitOperationAdd = Mock()
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(sys.modules, {"huggingface_hub": sdk}):
                bucket = _mk(directory, self.transport)
                bucket.append({"n": 1})
                out = bucket.flush_queue(force=True)
        self.assertEqual(out["committed"], 1)
        self.assertEqual(out["pending"], 0)
        self.assertEqual(
            [call.kwargs["parent_commit"] for call in self.api.create_commit.call_args_list],
            [self.sha, new_sha],
        )
        self.assertEqual(
            [call.kwargs["revision"] for call in self.api.hf_hub_download.call_args_list],
            [self.sha, new_sha],
        )

    def test_wrapped_http_denial_keeps_queue_without_retry(self):
        self.api.repo_info.side_effect = _HTTPError(401)
        with tempfile.TemporaryDirectory() as directory:
            bucket = _mk(directory, self.transport)
            bucket.append({"n": 1})
            out = bucket.flush_queue(force=True)
            self.assertEqual(out["pending"], 1)
            self.assertEqual(out["state"], "unreachable")
        self.assertEqual(self.api.repo_info.call_count, 1)
        self.api.create_commit.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
