#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Offline contracts for bounded readiness sweeps and background scheduling."""

from collections import Counter
from contextlib import ExitStack
import copy
import importlib.util
import json
import os
from pathlib import Path
import threading
import unittest
from unittest.mock import patch
import urllib.error


SPEC = importlib.util.spec_from_file_location(
    "readiness_sweep_under_test", Path(__file__).resolve().parents[1] / "szl_readiness.py")
readiness = importlib.util.module_from_spec(SPEC)
# The module accepts optional production tokens. This harness never reads them.
with patch.dict(os.environ, {}, clear=True):
    SPEC.loader.exec_module(readiness)


class ReadinessSweepTests(unittest.TestCase):
    def setUp(self):
        self.patches = ExitStack()
        self.addCleanup(self.patches.close)
        self.clock = 1000.0
        self.head_sha = "a" * 40
        self.version_sha = self.head_sha
        self.space_sha = "b" * 40
        self.anchor_sha = None
        with patch.dict(os.environ, {}, clear=True):
            self.cfg = readiness._a11oy_cfg()
        self.repo_url = readiness._GH_API + "repos/" + self.cfg["repo"]
        self.space_url = readiness._HF_API + "spaces/" + self.cfg["hf_space"]
        self.replace("_cfg_for", return_value=self.cfg)
        self.replace("_CACHE", {})
        self.replace("_DISK_LOADED", True)
        self.replace("_disk_save")
        self.replace("_SWEEP", threading.local())
        self.replace("_SNAPSHOT", {})
        self.replace("_BUILDING", set())
        self.replace("_BUILD_LOCKS", {})
        self.replace("_GH_TOKEN", "")
        self.replace("_GH_COOLDOWN_UNTIL", 0.0)
        self.replace("_HF_TOKEN", "")
        self.patches.enter_context(patch.object(
            readiness.time, "time", side_effect=lambda: self.clock))
        self.replace("_now_iso", side_effect=lambda: str(self.clock))
        # Endpoint contract probes are covered separately; count actual shared
        # provider-reader calls here without making any network or disk writes.
        self.replace("_endpoint_liveness", return_value={"reachable": True})
        self.patches.enter_context(patch.object(
            readiness.urllib.request, "urlopen",
            side_effect=AssertionError("offline sweep attempted real network access")))
        self.network = self.replace("_get", side_effect=self.response)

    def replace(self, name, *args, **kwargs):
        return self.patches.enter_context(patch.object(readiness, name, *args, **kwargs))

    def response(self, url, **_kwargs):
        if url == self.cfg["deployment"]["healthz_url"]:
            value = {"status": "ok", "organ": "a11oy"}
        elif url == self.cfg["deployment"]["version_url"]:
            value = {"version": "1", "git_sha": self.version_sha,
                     "hf_space_sha": self.space_sha}
            if self.anchor_sha:
                value["kernel_commit"] = self.anchor_sha
        elif url == self.repo_url:
            value = {"default_branch": "main", "html_url": "https://github.com/" + self.cfg["repo"]}
        elif url == self.repo_url + "/commits/main":
            value = {"sha": self.head_sha}
        elif url == self.repo_url + "/actions/runs?branch=main&per_page=1":
            value = {"workflow_runs": []}
        elif url == self.repo_url + "/releases/latest":
            value = {"tag_name": "v1"}
        elif url.startswith(self.repo_url + "/compare/"):
            value = {"ahead_by": 1, "behind_by": 0, "status": "ahead"}
        elif self.anchor_sha and url == self.repo_url + "/commits/" + self.anchor_sha:
            value = {"sha": self.anchor_sha}
        elif url == self.space_url:
            value = {"id": self.cfg["hf_space"], "sha": self.space_sha,
                     "runtime": {"stage": "RUNNING"}}
        else:
            raise AssertionError("unexpected offline URL: " + url)
        return json.dumps(value).encode()

    def request_counts(self):
        return Counter(call.args[0] for call in self.network.call_args_list)

    def sections(self, payload):
        return {section["id"]: section for section in payload["sections"]}

    def expected_shared_urls(self):
        return {
            self.cfg["deployment"]["healthz_url"],
            self.cfg["deployment"]["version_url"],
            self.repo_url,
            self.repo_url + "/commits/main",
            self.repo_url + "/actions/runs?branch=main&per_page=1",
            self.repo_url + "/releases/latest",
            self.space_url,
        }

    def test_primary_limit_suppresses_reads_until_observed_reset(self):
        def rate_limited(url, **kwargs):
            if url.startswith(readiness._GH_API):
                raise urllib.error.HTTPError(url, 403, "rate limited", {
                    "X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1300"}, None)
            return self.response(url, **kwargs)

        self.network.side_effect = rate_limited
        first = self.sections(readiness._assemble_index("a11oy", fresh=True))
        self.assertEqual([call.args[0] for call in self.network.call_args_list
                          if call.args[0].startswith(readiness._GH_API)], [self.repo_url])
        self.assertEqual(first["repo"]["mode"], "unreachable")
        self.assertEqual(readiness._GH_COOLDOWN_UNTIL, 1301.0)

        self.clock = 1240.0
        self.network.reset_mock()
        readiness._assemble_index("a11oy", fresh=True)
        self.assertFalse(any(call.args[0].startswith(readiness._GH_API)
                             for call in self.network.call_args_list))

        self.clock = 1301.0
        self.network.reset_mock()
        self.network.side_effect = self.response
        recovered = self.sections(readiness._assemble_index("a11oy", fresh=True))
        self.assertEqual(recovered["repo"]["mode"], "live")
        self.assertEqual(len([call for call in self.network.call_args_list
                              if call.args[0].startswith(readiness._GH_API)]), 4)

    def test_retry_after_preserves_last_good_clocks(self):
        readiness._assemble_index("a11oy", fresh=True)
        previous = copy.deepcopy(readiness._CACHE)
        self.clock = 1240.0

        def rate_limited(url, **kwargs):
            if url.startswith(readiness._GH_API):
                raise urllib.error.HTTPError(url, 429, "rate limited",
                                             {"Retry-After": "30"}, None)
            return self.response(url, **kwargs)

        self.network.reset_mock()
        self.network.side_effect = rate_limited
        sections = self.sections(readiness._assemble_index("a11oy", fresh=True))
        self.assertEqual([call.args[0] for call in self.network.call_args_list
                          if call.args[0].startswith(readiness._GH_API)], [self.repo_url])
        self.assertEqual(readiness._GH_COOLDOWN_UNTIL, 1270.0)
        self.assertEqual(sections["repo"]["mode"], "cached")
        self.assertEqual(sections["repo"]["fetched_at"], "1000.0")
        for key in previous:
            if key.startswith("gh"):
                self.assertEqual(readiness._CACHE[key], previous[key])

    def test_non_rate_forbidden_response_does_not_open_cooldown(self):
        def forbidden(url, **kwargs):
            if url.startswith(readiness._GH_API):
                raise urllib.error.HTTPError(url, 403, "forbidden", {}, None)
            return self.response(url, **kwargs)

        self.network.side_effect = forbidden
        self.sections(readiness._assemble_index("a11oy", fresh=True))
        self.assertEqual(readiness._GH_COOLDOWN_UNTIL, 0.0)
        self.assertEqual(len([call for call in self.network.call_args_list
                              if call.args[0].startswith(readiness._GH_API)]), 3)

    def test_full_forced_sweep_observes_each_shared_input_once(self):
        payload = readiness._assemble_index("a11oy", fresh=True)
        self.assertEqual(self.request_counts(), Counter(self.expected_shared_urls()))
        sections = self.sections(payload)
        self.assertEqual(sections["space"]["mode"], "live")
        self.assertEqual(sections["repo"]["mode"], "live")
        self.assertEqual(sections["parity"]["hf_space"]["live_hf_space_sha"], self.space_sha)
        self.assertIsNone(getattr(readiness._SWEEP, "observations", None))

    def test_unique_comparison_and_anchor_reads_still_run(self):
        self.version_sha = "c" * 40
        self.anchor_sha = "d" * 40
        readiness._assemble_index("a11oy", fresh=True)
        expected = self.expected_shared_urls() | {
            self.repo_url + "/compare/" + self.version_sha + "...main",
            self.repo_url + "/commits/" + self.anchor_sha,
        }
        self.assertEqual(self.request_counts(), Counter(expected))

    def test_failed_expired_sweep_reuses_fallback_without_retry_or_new_clock(self):
        readiness._assemble_index("a11oy", fresh=True)
        previous = copy.deepcopy(readiness._CACHE)
        self.clock += 1000
        self.network.side_effect = OSError("offline provider failure")
        for fresh in (True, False):
            with self.subTest(fresh=fresh):
                self.network.reset_mock()
                sections = self.sections(readiness._assemble_index("a11oy", fresh=fresh))
                expected = self.expected_shared_urls() - {self.repo_url + "/commits/main"}
                self.assertEqual(self.request_counts(), Counter(expected))
                self.assertEqual(readiness._CACHE, previous)
                for section_id in ("identity", "repo", "space"):
                    self.assertEqual(sections[section_id]["fetched_at"], "1000.0")
                self.assertEqual(sections["space"]["mode"], "cached")
                self.assertEqual(sections["parity"]["hf_space"]["mode"], "cached")
                self.assertEqual(sections["parity"]["build"]["repo_mode"], "cached")
                self.assertEqual(sections["parity"]["build"]["deployed_mode"], "cached")

    def test_next_forced_sweep_and_direct_read_do_not_reuse_previous_memo(self):
        readiness._assemble_index("a11oy", fresh=True)
        self.clock += 1
        self.space_sha = "e" * 40
        self.network.reset_mock()
        payload = readiness._assemble_index("a11oy", fresh=True)
        self.assertEqual(self.request_counts(), Counter(self.expected_shared_urls()))
        self.assertEqual(self.sections(payload)["space"]["fetched_at"], "1001.0")
        self.assertEqual(self.sections(payload)["parity"]["hf_space"]["live_hf_space_sha"],
                         self.space_sha)
        self.network.reset_mock()
        readiness._hf_space("SZLHOLDINGS", "a11oy", fresh=True)
        self.assertEqual(self.request_counts(), Counter({self.space_url: 1}))

    def test_public_cache_backed_sweep_preserves_observation_clocks(self):
        readiness._assemble_index("a11oy", fresh=True)
        self.clock += 1
        self.network.reset_mock()
        payload = readiness._assemble_index("a11oy")
        self.network.assert_not_called()
        self.assertEqual(self.sections(payload)["space"]["fetched_at"], "1000.0")
        self.assertEqual(self.sections(payload)["repo"]["fetched_at"], "1000.0")
        self.assertEqual(payload["checked_at"], "1001.0")

    def test_nested_observation_context_is_restored_after_success(self):
        previous = {"outer": "observation"}
        readiness._SWEEP.observations = previous
        readiness._assemble_index("a11oy", fresh=True)
        self.assertIs(readiness._SWEEP.observations, previous)
        self.assertEqual(previous, {"outer": "observation"})

    def test_failed_assembly_restores_context_and_releases_build_lock(self):
        previous = {"outer": "observation"}
        readiness._SWEEP.observations = previous

        def fail(_cfg, fresh=False):
            readiness._hf_space("SZLHOLDINGS", "a11oy", fresh=fresh)
            raise RuntimeError("offline section failure")

        with patch.object(readiness, "_SECTIONS", {"space": fail}), \
                patch.object(readiness, "_SECTION_ORDER", ["space"]):
            with self.assertRaisesRegex(RuntimeError, "offline section failure"):
                readiness._build_snapshot("a11oy", fresh=True)
        self.assertIs(readiness._SWEEP.observations, previous)
        self.assertNotIn("a11oy", readiness._SNAPSHOT)
        lock = readiness._BUILD_LOCKS["a11oy"]
        self.assertTrue(lock.acquire(blocking=False))
        lock.release()
        readiness._build_snapshot("a11oy", fresh=True)
        self.assertIn("a11oy", readiness._SNAPSHOT)

    def test_scheduled_build_waits_for_public_build_then_observes_fresh(self):
        public_entered = threading.Event()
        release_public = threading.Event()
        scheduled_waiting = threading.Event()
        fresh_entered = threading.Event()
        order, failures = [], []

        class ObservedLock:
            def __init__(self):
                self.lock = threading.Lock()

            def __enter__(self):
                if threading.current_thread().name == "scheduled-test":
                    scheduled_waiting.set()
                self.lock.acquire()
                return self

            def __exit__(self, *_args):
                self.lock.release()

        readiness._BUILD_LOCKS["a11oy"] = ObservedLock()

        def assemble(_ns, fresh=False):
            order.append(fresh)
            if fresh:
                fresh_entered.set()
            else:
                public_entered.set()
                if not release_public.wait(5):
                    raise AssertionError("public build was not released")
            return {"fresh": fresh}

        def build(fresh):
            try:
                readiness._build_snapshot("a11oy", fresh=fresh)
            except BaseException as error:
                failures.append(error)

        with patch.object(readiness, "_assemble_index", side_effect=assemble):
            public = threading.Thread(target=build, args=(False,), daemon=True)
            scheduled = threading.Thread(target=build, args=(True,), name="scheduled-test", daemon=True)
            public.start()
            try:
                self.assertTrue(public_entered.wait(2))
                scheduled.start()
                self.assertTrue(scheduled_waiting.wait(2))
                self.assertFalse(fresh_entered.is_set())
            finally:
                release_public.set()
                public.join(2)
                if scheduled.ident is not None:
                    scheduled.join(2)
            self.assertFalse(public.is_alive())
            self.assertFalse(scheduled.is_alive())
        self.assertEqual(failures, [])
        self.assertEqual(order, [False, True])
        self.assertTrue(fresh_entered.is_set())
        self.assertTrue(readiness._snapshot("a11oy")["payload"]["fresh"])

    def test_warmer_explicitly_requests_fresh_observations(self):
        class StopLoop(BaseException):
            pass

        sleeps = []

        def sleep(seconds):
            sleeps.append(seconds)
            if seconds == readiness._WARM_INTERVAL:
                raise StopLoop()

        with patch.object(readiness, "_WARM_NS", {"a11oy"}), \
                patch.object(readiness, "_build_snapshot") as build, \
                patch.object(readiness.time, "sleep", side_effect=sleep):
            with self.assertRaises(StopLoop):
                readiness._warm_loop()
        build.assert_called_once_with("a11oy", fresh=True)
        self.assertEqual(sleeps, [12, 2, readiness._WARM_INTERVAL])

    def test_public_kick_is_cache_backed_deduplicated_and_cleans_up_failure(self):
        targets = []

        class DeferredThread:
            def __init__(self, *, target, **_kwargs):
                self.target = target

            def start(self):
                targets.append(self.target)

        with patch.object(readiness.threading, "Thread", DeferredThread), \
                patch.object(readiness, "_build_snapshot", side_effect=RuntimeError("offline failure")) as build:
            readiness._kick_background_build("a11oy")
            readiness._kick_background_build("a11oy")
            self.assertEqual(len(targets), 1)
            self.assertIn("a11oy", readiness._BUILDING)
            targets[0]()
            build.assert_called_once_with("a11oy")
            self.assertNotIn("a11oy", readiness._BUILDING)
            readiness._kick_background_build("a11oy")
            self.assertEqual(len(targets), 2)
            targets[1]()
            self.assertNotIn("a11oy", readiness._BUILDING)


if __name__ == "__main__":
    unittest.main()
