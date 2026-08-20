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
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from szl_hf_bucket import HFBucket, Transport, SCHEMA  # noqa: E402


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

    def read_file(self, path):
        if self.unreachable:
            raise ConnectionError("network is unreachable")
        if self.fail_reads > 0:
            self.fail_reads -= 1
            raise _HTTPError(self.read_status)
        return self.files.get(path)

    def list_files(self, prefix):
        if self.unreachable:
            raise ConnectionError("network is unreachable")
        pref = prefix.rstrip("/") + "/"
        return sorted(p for p in self.files if p.startswith(pref))

    def commit(self, operations, message):
        if self.unreachable:
            raise ConnectionError("network is unreachable")
        if self.fail_commits > 0:
            self.fail_commits -= 1
            raise _HTTPError(self.commit_status)
        for path, blob in operations:
            self.files[path] = blob
        self.commits += 1
        return "oid%d" % self.commits


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
        self._tmp = tempfile.mkdtemp(prefix="hfbtest_")

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
