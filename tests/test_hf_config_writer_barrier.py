#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Offline evidence/timeout regressions for the canonical configuration barrier."""
from __future__ import annotations

import ast
from datetime import datetime, timezone
import importlib.util
import io
import json
from pathlib import Path
import re
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".github/scripts/await_hf_config_writer.py"
SPEC = importlib.util.spec_from_file_location("config_writer_barrier", SCRIPT)
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)
SOURCE, HF = "a" * 40, "b" * 40
WALL = 1_800_000_000.0


class Clock:
    def __init__(self):
        self.elapsed = 0.0

    def wall(self):
        return WALL + self.elapsed

    def now(self):
        return self.elapsed

    def sleep(self, seconds):
        self.elapsed += seconds


def sample(clock, *, epoch=11, boot=2, state="ACTIVE", claim="CLEAN", beat=None):
    storage_boot = f"{boot:032x}"
    writer = f"{boot + 100:032x}"
    runtime_boot = "boot_" + f"{boot + 200:032x}"
    stamp = clock.wall() - clock.elapsed % 15 if beat is None else beat
    provider = {"stage": "RUNNING", "runtime_sha": HF, "repository_sha": HF}
    head = {
        "schema": "szl.a11oy-state-head/v2", "bucket": M.BUCKET, "epoch": epoch,
        "sequence": epoch * 100, "writer_id": writer, "boot_id": storage_boot,
        "source_revision": SOURCE, "state": state,
        "claim": {"kind": claim, "origins": {label: "RESTORED" for label in M.STORES}},
        "lease": {"heartbeat_path": M.HEARTBEAT_PATH, "stale_after_seconds": 120},
    }
    heartbeat = {"schema": "szl.a11oy-state-heartbeat/v1", "epoch": epoch,
                 "writer_id": writer, "boot_id": storage_boot, "at_unix": stamp,
                 "at": datetime.fromtimestamp(stamp, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    status = {
        "schema": "szl.a11oy-storage-status/v2", "mode": "FENCED", "unfenced": False,
        "epoch": epoch, "claim": claim, "role": "WRITER" if state == "ACTIVE" else state,
        "writable": state == "ACTIVE", "alert": False, "active_errors": {},
        "pending_publish": [], "last_error": None,
        "lease": {"state": state, "sequence": head["sequence"],
                  "heartbeat_age_s": max(0, clock.wall() - stamp)},
        "stores": {label: {"health": "OK", "origin": "RESTORED",
                          "blocked_code": None, "last_error_code": None} for label in M.STORES},
    }
    series = {"source_revision": SOURCE, "runtime_boot_id": runtime_boot,
              "runtime_source_identity": {
                  "status": "REPORTED", "method": "GITHUB_ATTESTED_SOURCE_COPY_SET",
                  "local_bytes_evidence": "MEASURED", "error": None,
                  "hf_revision": HF, "source_revision": SOURCE, "runtime_boot_id": runtime_boot}}
    return {"started_at": clock.wall(), "observed_at": clock.wall(),
            "provider": provider, "provider_after": dict(provider),
            "head_revision": "c" * 40, "head_revision_after": "c" * 40, "head_sha256": "d" * 64,
            "head": head, "heartbeat": heartbeat, "storage": status, "series": series}


def baseline(clock, **kwargs):
    value = M.validate_sample(sample(clock, epoch=10, boot=1, **kwargs), now=clock.wall(), capture=True)
    return M.audit("BASELINE_OBSERVED", observation=value)


def config(owner="series-a", *, changed=None):
    value = {"schema": f"szl.hf-{owner}-runtime-config/v1", "repo_id": M.SPACE,
             "converged": True, "credential_authority_state": "VERIFIED",
             "variables_changed": [] if changed is None else changed}
    if owner == "series-a":
        value["volume_changed"] = False
    return value


class WriterBarrierTests(unittest.TestCase):
    def wait(self, clock, read=None, before=None, timeout=100, **kwargs):
        return M.await_writer(before or baseline(clock), read or (lambda _budget: sample(clock)),
                              clock=clock.now, wall=clock.wall, sleep=clock.sleep,
                              timeout=timeout, **kwargs)



    def test_retained_baseline_drops_unknown_token_and_url_surrogates(self):
        clock = Clock()
        before = baseline(clock)
        before["extra"] = {"token": "harmless-token-surrogate"}
        before["observation"]["extra"] = {"url": "https://example.invalid/private-fixture"}
        result = self.wait(clock, before=before)
        self.assertEqual(result["status"], "WRITER_STABLE_AFTER_CONFIG")
        encoded = json.dumps(result)
        self.assertNotIn("harmless-token-surrogate", encoded)
        self.assertNotIn("example.invalid", encoded)
        self.assertEqual(set(result["baseline"]), set(baseline(Clock())["observation"]))

    def test_retained_baseline_rejects_unvalidated_known_fields(self):
        mutations = (
            {"owner_source_revision": "https://example.invalid/private-fixture"},
            {"heartbeat_at_unix": "harmless-token-surrogate"},
            {"heartbeat_at_unix": True},
            {"heartbeat_age_seconds": "harmless-token-surrogate"},
            {"heartbeat_age_seconds": float("nan")},
            {"heartbeat_age_seconds": 1},
        )
        for change in mutations:
            with self.subTest(change=change):
                clock = Clock()
                before = baseline(clock)
                before["observation"].update(change)
                with self.assertRaisesRegex(M.Hold, "^BASELINE_INVALID$"):
                    self.wait(clock, before=before,
                              read=lambda _budget: self.fail("invalid baseline must not read"))

    def test_epoch_owner_identity_survives_an_unavailable_read(self):
        clock = Clock()
        def read(_budget):
            if clock.elapsed == 10:
                raise ConnectionError("temporary")
            return sample(clock, boot=2 if clock.elapsed == 0 else 3)
        result = self.wait(clock, read)
        self.assertEqual(result["reason"], "LEASE_IDENTITY_CHANGED")
        self.assertEqual(clock.elapsed, 20)

    def test_owner_heartbeat_watermark_survives_an_unavailable_read(self):
        clock = Clock()
        def read(_budget):
            if clock.elapsed == 10:
                raise ConnectionError("temporary")
            return sample(clock, beat=WALL - 1 if clock.elapsed == 20 else None)
        result = self.wait(clock, read)
        self.assertEqual(result["status"], "WRITER_STABLE_AFTER_CONFIG")
        self.assertEqual(clock.elapsed, 60)
        self.assertTrue(any(o.get("reason") == "OBSERVATION_REGRESSED"
                            for o in result["observations"]))

    def test_newer_sequence_is_retained_when_the_same_sample_regresses_heartbeat(self):
        clock = Clock()
        def read(_budget):
            value = sample(clock, beat=WALL - 1 if clock.elapsed == 10 else None)
            sequence = 1106 if clock.elapsed == 10 else 1105
            value["head"]["sequence"] = value["storage"]["lease"]["sequence"] = sequence
            return value
        result = self.wait(clock, read, timeout=80)
        self.assertEqual(result["status"], "HOLD")
        owner = next(o for o in result["owner_watermarks"] if o["epoch"] == 11)
        self.assertEqual(owner["max_sequence"], 1106)

    def test_workflow_budgets_preserve_the_prior_allowance_and_both_complete_barriers(self):
        source = (ROOT / ".github/workflows/hf-sync.yml").read_text(encoding="utf-8")
        for name, minutes, previous in (("preflight", 50, 15), ("runtime-config", 55, 20)):
            with self.subTest(job=name):
                match = re.search(r"(?ms)^  " + re.escape(name) + r":\n.*?(?=^  [A-Za-z0-9_-]+:\n|\Z)", source)
                self.assertIsNotNone(match)
                job = match.group(0)
                timeout = re.search(r"(?m)^    timeout-minutes: (\d+)$", job)
                self.assertIsNotNone(timeout)
                self.assertEqual(int(timeout.group(1)), minutes)
                self.assertEqual(job.count("await_hf_config_writer.py --capture"), 2)
                self.assertEqual(job.count("await_hf_config_writer.py --await-writer"), 2)
                minimum = previous * 60 + 2 * (M.TIMEOUT_SECONDS + M.SAMPLE_SECONDS)
                self.assertGreaterEqual(minutes * 60, minimum)

    def test_final_sample_arriving_after_the_deadline_cannot_succeed(self):
        clock = Clock()
        def read(budget):
            if clock.elapsed == 30:
                clock.sleep(budget + 1)
            return sample(clock)
        result = self.wait(clock, read, timeout=35)
        self.assertEqual(result["status"], "HOLD")
        self.assertEqual(result["reason"], "CONFIG_WRITER_TIMEOUT")

    def test_validation_finishing_after_the_deadline_cannot_succeed(self):
        clock = Clock()
        before = baseline(clock)
        original = M.validate_sample
        delayed = False
        def validate(*args, **kwargs):
            nonlocal delayed
            if clock.elapsed == 30 and not delayed:
                clock.sleep(6)
                delayed = True
            return original(*args, **kwargs)
        with patch.object(M, "validate_sample", side_effect=validate):
            result = self.wait(clock, before=before, timeout=35)
        self.assertEqual(result["status"], "HOLD")
        self.assertEqual(result["reason"], "CONFIG_WRITER_TIMEOUT")

    def test_highest_epoch_survives_boot_streak_reset_and_unavailable_reads(self):
        for interrupted in (False, True):
            with self.subTest(interrupted=interrupted):
                clock = Clock()
                def read(_budget):
                    if clock.elapsed == 0:
                        return sample(clock, epoch=12, boot=3)
                    if interrupted and clock.elapsed == 10:
                        raise ConnectionError("temporary")
                    return sample(clock, epoch=11, boot=2)
                result = self.wait(clock, read, timeout=80)
                self.assertEqual(result["status"], "HOLD")
                self.assertEqual(result["max_observed_epoch"], 12)
                self.assertTrue(any(o.get("reason") == "OBSERVED_EPOCH_REGRESSED"
                                    for o in result["observations"]))

    def test_owner_head_sequence_watermark_survives_an_unavailable_read(self):
        clock = Clock()
        def read(_budget):
            if clock.elapsed == 10:
                raise ConnectionError("temporary")
            value = sample(clock)
            sequence = 1105 if clock.elapsed == 0 else 1104
            value["head"]["sequence"] = value["storage"]["lease"]["sequence"] = sequence
            return value
        result = self.wait(clock, read, timeout=80)
        self.assertEqual(result["status"], "HOLD")
        owner = next(o for o in result["owner_watermarks"] if o["epoch"] == 11)
        self.assertEqual(owner["max_sequence"], 1105)

    def test_released_higher_epoch_also_prevents_settling_a_lower_epoch(self):
        clock = Clock()
        result = self.wait(clock, lambda _budget: sample(
            clock, epoch=12 if clock.elapsed == 0 else 11,
            boot=3 if clock.elapsed == 0 else 2,
            state="RELEASED" if clock.elapsed == 0 else "ACTIVE"), timeout=80)
        self.assertEqual(result["status"], "HOLD")
        self.assertEqual(result["max_observed_epoch"], 12)

    def test_same_writer_and_advancing_heartbeat_must_span_the_stability_window(self):
        clock = Clock()
        result = self.wait(clock)
        self.assertEqual(result["status"], "WRITER_STABLE_AFTER_CONFIG")
        self.assertEqual(result["samples"], 4)
        self.assertGreaterEqual(result["stable_seconds"], 30)
        self.assertGreaterEqual(result["heartbeat_advance_seconds"], 15)
        self.assertEqual(clock.elapsed, 30)
        self.assertEqual(result["provider_writes"], 0)
        self.assertFalse(result["execution_authority"])
        self.assertFalse(result["snapshot_objects_verified"])
        self.assertEqual(result["same_process_binding"], "NOT_ESTABLISHED")

    def test_old_running_process_never_satisfies_a_configuration_restart(self):
        clock = Clock()
        result = self.wait(clock, lambda _budget: sample(clock, epoch=10, boot=1), timeout=25)
        self.assertEqual(result["status"], "HOLD")
        self.assertEqual(result["reason"], "CONFIG_WRITER_TIMEOUT")
        self.assertEqual(clock.elapsed, 25)

    def test_boot_or_epoch_churn_resets_the_complete_stability_window(self):
        clock = Clock()
        def read(_budget):
            return sample(clock, epoch=11 if clock.elapsed < 20 else 12,
                          boot=2 if clock.elapsed < 20 else 3)
        result = self.wait(clock, read)
        self.assertEqual(result["status"], "WRITER_STABLE_AFTER_CONFIG")
        self.assertEqual(clock.elapsed, 50)
        self.assertEqual(result["samples"], 4)
        self.assertEqual(result["observation"]["epoch"], 12)

    def test_changed_writer_inside_the_same_epoch_holds_instead_of_resetting_green(self):
        clock = Clock()
        result = self.wait(clock, lambda _budget: sample(clock, boot=2 if clock.elapsed < 20 else 3))
        self.assertEqual(result["reason"], "LEASE_IDENTITY_CHANGED")
        self.assertEqual(clock.elapsed, 20)

    def test_a_replayed_fresh_heartbeat_cannot_prove_progress(self):
        clock = Clock()
        result = self.wait(clock, lambda _budget: sample(clock, beat=WALL), timeout=70)
        self.assertEqual(result["status"], "HOLD")
        self.assertEqual(clock.elapsed, 70)

    def test_heartbeat_or_sequence_regression_restarts_observation(self):
        for field in ("heartbeat", "sequence"):
            with self.subTest(field=field):
                clock = Clock()
                def read(_budget):
                    value = sample(clock)
                    if clock.elapsed == 20:
                        if field == "heartbeat":
                            value["heartbeat"]["at_unix"] = WALL - 1
                            value["heartbeat"]["at"] = datetime.fromtimestamp(WALL - 1, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                        else:
                            value["head"]["sequence"] -= 1
                            value["storage"]["lease"]["sequence"] -= 1
                    return value
                result = self.wait(clock, read)
                self.assertEqual(result["status"], "WRITER_STABLE_AFTER_CONFIG")
                self.assertEqual(clock.elapsed, 60)

    def test_partial_or_failed_observation_breaks_a_success_streak(self):
        for kind in ("partial", "transport"):
            with self.subTest(kind=kind):
                clock = Clock()
                def read(_budget):
                    if clock.elapsed == 20:
                        if kind == "transport":
                            raise ConnectionError("private-token-not-for-report")
                        value = sample(clock)
                        del value["storage"]["stores"]["unay"]
                        return value
                    return sample(clock)
                result = self.wait(clock, read)
                self.assertEqual(result["status"], "WRITER_STABLE_AFTER_CONFIG")
                self.assertEqual(clock.elapsed, 60)
                self.assertNotIn("private-token", json.dumps(result))

    def test_unclean_new_claim_stops_without_waiting_for_a_later_clean_claim(self):
        clock = Clock()
        result = self.wait(clock, lambda _budget: sample(clock, claim="UNCLEAN_HANDOVER"))
        self.assertEqual(result["reason"], "CONFIG_RESTART_NOT_CLEAN")
        self.assertEqual(clock.elapsed, 0)



    def test_new_unclean_claim_is_retained_even_while_public_startup_observation_is_partial(self):
        clock = Clock()
        def read(_budget):
            value = sample(clock, claim="UNCLEAN_HANDOVER")
            value["storage"] = {}
            return value
        result = self.wait(clock, read)
        self.assertEqual(result["reason"], "CONFIG_RESTART_NOT_CLEAN")
        self.assertEqual(result["candidate"]["epoch"], 11)
        self.assertEqual(result["candidate"]["owner_source_revision"], SOURCE)
        self.assertEqual(clock.elapsed, 0)

    def test_changed_publication_during_rebuild_holds_before_public_routes_are_ready(self):
        clock = Clock()
        def read(_budget):
            value = sample(clock)
            value["provider"].update(repository_sha="e" * 40, stage="RUNNING_BUILDING")
            value["storage"] = {}
            return value
        result = self.wait(clock, read)
        self.assertEqual(result["reason"], "PUBLICATION_CHANGED")
        self.assertEqual(clock.elapsed, 0)

    def test_old_unclean_or_released_process_may_remain_visible_before_the_replacement(self):
        for state in ("ACTIVE", "RELEASED"):
            with self.subTest(state=state):
                clock = Clock()
                before = baseline(clock, state=state, claim="UNCLEAN_HANDOVER")
                def read(_budget):
                    if clock.elapsed < 20:
                        return sample(clock, epoch=10, boot=1, state=state, claim="UNCLEAN_HANDOVER")
                    return sample(clock)
                result = self.wait(clock, read, before=before)
                self.assertEqual(result["status"], "WRITER_STABLE_AFTER_CONFIG")
                self.assertEqual(clock.elapsed, 50)
                self.assertEqual(result["baseline"]["claim"], "UNCLEAN_HANDOVER")

    def test_prior_unclean_history_is_retained_when_a_new_clean_writer_is_observed(self):
        clock = Clock()
        before = baseline(clock, claim="UNCLEAN_HANDOVER")
        result = self.wait(clock, before=before)
        self.assertEqual(result["status"], "WRITER_STABLE_AFTER_CONFIG")
        self.assertEqual(result["baseline"]["claim"], "UNCLEAN_HANDOVER")
        self.assertEqual(result["observation"]["claim"], "CLEAN")
        self.assertEqual(result["baseline"]["owner_source_revision"], SOURCE)

    def test_verified_released_maintenance_baseline_can_wait_for_a_new_clean_writer(self):
        clock = Clock()
        before = baseline(clock, state="RELEASED", claim="UNCLEAN_HANDOVER", beat=WALL - 600)
        result = self.wait(clock, before=before)
        self.assertEqual(result["status"], "WRITER_STABLE_AFTER_CONFIG")
        self.assertEqual(result["baseline"]["state"], "RELEASED")

    def test_publication_change_holds_without_synthesizing_a_new_expected_source(self):
        clock = Clock()
        def read(_budget):
            value = sample(clock)
            value["provider"]["runtime_sha"] = value["provider"]["repository_sha"] = "e" * 40
            value["provider_after"] = dict(value["provider"])
            value["series"]["runtime_source_identity"]["hf_revision"] = "e" * 40
            return value
        result = self.wait(clock, read)
        self.assertEqual(result["reason"], "PUBLICATION_CHANGED")

    def test_missing_or_expired_baseline_cannot_grant_a_wait(self):
        for mutation in (
            lambda b: b["observation"].pop("runtime_boot_id"),
            lambda b: b["observation"].pop("storage_boot_id"),
            lambda b: b["observation"].update(epoch=True),
            lambda b: b["observation"].update(observed_at=WALL - 901),
            lambda b: b["observation"].update(observed_at=WALL + 1),
        ):
            clock = Clock()
            before = baseline(clock)
            mutation(before)
            with self.assertRaises(M.Hold):
                self.wait(clock, before=before, read=lambda _budget: self.fail("unexpected provider read"))

    def test_timeout_budget_is_passed_to_each_bounded_sample_and_progress_is_retained(self):
        clock, budgets, records = Clock(), [], []
        def read(budget):
            budgets.append(budget)
            clock.sleep(min(12, budget))
            raise M.Hold("SAMPLE_TIMEOUT")
        result = self.wait(clock, read, timeout=25, record=records.append)
        self.assertEqual(result["status"], "HOLD")
        self.assertEqual(clock.elapsed, 25)
        self.assertEqual(budgets, [25, 3])
        self.assertTrue(records)
        self.assertEqual(records[-1]["status"], "WAITING")

    def test_invalid_or_partial_samples_never_establish_writer_health(self):
        cases = {
            "future heartbeat": lambda s: s["heartbeat"].update(at_unix=WALL + 1),
            "stale heartbeat": lambda s: s["heartbeat"].update(at_unix=WALL - 31),
            "heartbeat owner": lambda s: s["heartbeat"].update(writer_id="f" * 32),
            "heartbeat boot": lambda s: s["heartbeat"].update(boot_id="f" * 32),
            "heartbeat epoch bool": lambda s: s["heartbeat"].update(epoch=True),
            "nan heartbeat": lambda s: s["heartbeat"].update(at_unix=float("nan")),
            "public heartbeat stale": lambda s: s["storage"]["lease"].update(heartbeat_age_s=31),
            "head changed": lambda s: s.update(head_revision_after="e" * 40),
            "head revision missing": lambda s: s.pop("head_revision"),
            "stale body": lambda s: s.update(started_at=WALL - 20, observed_at=WALL - 20),
            "slow sample": lambda s: s.update(started_at=WALL - 31),
            "partial source": lambda s: s["series"].pop("runtime_source_identity"),
            "runtime boot mix": lambda s: s["series"].update(runtime_boot_id="boot_" + "e" * 32),
            "provider rebuild": lambda s: s["provider"].update(stage="RUNNING_BUILDING"),
            "provider changed": lambda s: s["provider_after"].update(runtime_sha="e" * 40),
            "handover requested": lambda s: s["head"].update(state="HANDOVER_REQUESTED"),
            "unfenced": lambda s: s["storage"].update(mode="SNAPSHOT_ONLY_UNFENCED"),
            "writable integer": lambda s: s["storage"].update(writable=1),
            "role fenced": lambda s: s["storage"].update(role="FENCED"),
            "lease epoch mix": lambda s: s["storage"].update(epoch=12),
            "lease sequence mix": lambda s: s["storage"]["lease"].update(sequence=1099),
            "active errors": lambda s: s["storage"].update(active_errors={"snapshot": {"code": "ERROR"}}),
            "pending publish": lambda s: s["storage"].update(pending_publish=["gdw"]),
            "store unknown": lambda s: s["storage"]["stores"]["gdw"].update(health="UNKNOWN"),
            "store absent": lambda s: s["storage"]["stores"].pop("gdw"),
            "restoration absent": lambda s: s["head"]["claim"]["origins"].pop("gdw"),
        }
        for name, mutate in cases.items():
            with self.subTest(name=name):
                clock = Clock()
                value = sample(clock)
                mutate(value)
                with self.assertRaises(M.Hold):
                    M.validate_sample(value, now=clock.wall())

    def test_only_explicit_valid_no_effect_reports_skip_provider_reads(self):
        for owner in ("series-a", "gdw"):
            with self.subTest(owner=owner), tempfile.TemporaryDirectory() as directory:
                report, output = Path(directory) / "config.json", Path(directory) / "result.json"
                report.write_text(json.dumps(config(owner)), encoding="utf-8")
                with patch.object(M, "read_sample", side_effect=AssertionError("must not read")), redirect_stdout(io.StringIO()):
                    code = M.main(["--await-writer", "--owner", owner, "--config-report", str(report),
                                   "--baseline", str(Path(directory) / "absent.json"), "--output", str(output)])
                self.assertEqual(code, 0)
                self.assertEqual(json.loads(output.read_text())["status"], "NO_CONFIGURATION_WRITE")
        self.assertTrue(M.report_wrote(config(changed=["A11OY_STATE_PERIODIC_SECONDS"]), "series-a"))
        value = config()
        value["volume_changed"] = True
        self.assertTrue(M.report_wrote(value, "series-a"))

    def test_malformed_convergence_report_is_not_interpreted_as_no_write(self):
        mutations = [
            lambda r: r.pop("variables_changed"),
            lambda r: r.update(variables_changed=[[]]),
            lambda r: r.update(variables_changed=["A", "A"]),
            lambda r: r.update(variables_changed=False),
            lambda r: r.update(converged=1),
            lambda r: r.update(credential_authority_state="UNKNOWN"),
            lambda r: r.update(volume_changed=0),
            lambda r: r.update(repo_id="other/space"),
        ]
        for change in mutations:
            value = config()
            change(value)
            with self.assertRaises(M.Hold):
                M.report_wrote(value, "series-a")


    def test_unavailable_baseline_is_recorded_but_only_an_actual_write_requires_it(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "baseline.json"
            with patch.object(M, "read_sample", side_effect=M.Hold("SAMPLE_TIMEOUT")), redirect_stdout(io.StringIO()):
                code = M.main(["--capture", "--output", str(output)])
            self.assertEqual(code, 0)
            before = json.loads(output.read_text())
            self.assertEqual(before["status"], "BASELINE_UNAVAILABLE")
            with self.assertRaisesRegex(M.Hold, "^BASELINE_INVALID$"):
                self.wait(Clock(), before=before)

    def test_capture_does_not_assert_writer_health_when_observation_is_partial(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "baseline.json"
            value = sample(Clock())
            del value["head"]
            with patch.object(M, "read_sample", return_value=value), patch.object(M.time, "time", return_value=WALL), redirect_stdout(io.StringIO()):
                self.assertEqual(M.main(["--capture", "--output", str(output)]), 0)
            result = json.loads(output.read_text())
            self.assertEqual(result["status"], "BASELINE_UNAVAILABLE")
            self.assertNotIn("observation", result)

    def test_child_deadline_and_provider_failure_are_sanitized(self):
        called = []
        def timeout(command, **kwargs):
            called.append((command, kwargs))
            raise subprocess.TimeoutExpired(command, kwargs["timeout"], stderr="secret-value")
        with patch.object(M.subprocess, "run", side_effect=timeout):
            with self.assertRaisesRegex(M.Hold, "^SAMPLE_TIMEOUT$"):
                M.read_sample(3)
        self.assertEqual(called[0][1]["timeout"], 3)
        self.assertEqual(called[0][1]["stderr"], subprocess.DEVNULL)
        self.assertNotIn("GITHUB_TOKEN", called[0][1]["env"])
        self.assertNotIn("GH_TOKEN", called[0][1]["env"])
        self.assertEqual(called[0][0][1:3], ["-I", "-B"])
        self.assertEqual(called[0][0][-1], "--sample")
        with patch.object(M.subprocess, "run", return_value=SimpleNamespace(
                returncode=2, stdout=b"private-value")):
            with self.assertRaisesRegex(M.Hold, "^SAMPLE_READ_UNAVAILABLE$"):
                M.read_sample(30)

    def test_duplicate_nonfinite_and_oversized_json_fail_closed(self):
        for raw in (b'{"x":1,"x":2}', b'{"x":NaN}', b"[]", b" " * (8 * M.MAX_BYTES + 1)):
            with self.assertRaises(M.Hold):
                M.strict_json(raw)


    def test_real_adapter_reads_iterable_bucket_metadata_and_never_forwards_hub_auth_to_public_gets(self):
        raw = sample(Clock())
        head_bytes = json.dumps(raw["head"]).encode()
        beat_bytes = json.dumps(raw["heartbeat"]).encode()
        calls = []
        class Api:
            def space_info(self, repo):
                calls.append("space_info")
                self.assert_repo(repo, M.SPACE)
                return SimpleNamespace(sha=HF)
            def get_space_runtime(self, repo):
                calls.append("get_space_runtime")
                self.assert_repo(repo, M.SPACE)
                return SimpleNamespace(stage="RUNNING", raw={"sha": HF})
            def dataset_info(self, repo):
                calls.append("dataset_info")
                self.assert_repo(repo, M.DATASET)
                return SimpleNamespace(private=True, sha="c" * 40)
            def get_paths_info(self, repo, paths, **options):
                calls.append("get_paths_info")
                self.assert_repo(repo, M.DATASET)
                assert paths == [M.HEAD_PATH]
                assert options == {"repo_type": "dataset", "revision": "c" * 40}
                return [SimpleNamespace(path=M.HEAD_PATH, size=len(head_bytes))]
            def get_bucket_paths_info(self, repo, paths):
                calls.append("get_bucket_paths_info")
                self.assert_repo(repo, M.BUCKET)
                assert paths == [M.HEARTBEAT_PATH]
                yield SimpleNamespace(path=M.HEARTBEAT_PATH, size=len(beat_bytes))
            def download_bucket_files(self, repo, files, **options):
                calls.append("download_bucket_files")
                self.assert_repo(repo, M.BUCKET)
                assert options == {"raise_on_missing_files": True}
                assert len(files) == 1 and files[0][0].path == M.HEARTBEAT_PATH
                Path(files[0][1]).write_bytes(beat_bytes)
            @staticmethod
            def assert_repo(actual, expected):
                assert actual == expected
            def __getattr__(self, name):
                raise AssertionError("unapproved provider method: " + name)
        def download(repo, path, **options):
            calls.append("hf_hub_download")
            assert repo == M.DATASET and path == M.HEAD_PATH
            assert options["revision"] == "c" * 40 and options["token"] == "offline-fixture"
            assert options["endpoint"] == "https://huggingface.co"
            target = Path(options["local_dir"]) / "head.json"
            target.write_bytes(head_bytes)
            return str(target)
        class Response:
            status_code = 200
            def __init__(self, value):
                self.value = value
            def __enter__(self):
                return self
            def __exit__(self, *_args):
                pass
            def iter_content(self, _size):
                yield json.dumps(self.value).encode()
        class Session:
            def __enter__(self):
                return self
            def __exit__(self, *_args):
                pass
            def get(self, url, **options):
                calls.append("public_get")
                assert options["allow_redirects"] is False
                assert options["timeout"] == 10 and options["stream"] is True
                assert "Authorization" not in options["headers"]
                assert url in (M.ORIGIN + "/api/a11oy/v1/storage/status",
                               M.ORIGIN + "/api/a11oy/v1/series-a/status")
                return Response(raw["storage"] if url.endswith("/storage/status") else raw["series"])
        def api_factory(**options):
            assert options == {"endpoint": "https://huggingface.co", "token": "offline-fixture"}
            return Api()
        hub = SimpleNamespace(HfApi=api_factory, hf_hub_download=download)
        with patch.dict("sys.modules", {"huggingface_hub": hub, "requests": SimpleNamespace(Session=Session)}), patch.dict(M.os.environ, {"HF_TOKEN": "offline-fixture"}), patch.object(M.time, "time", return_value=WALL):
            observed = M.collect_sample()
            normalized = M.validate_sample(observed, now=WALL)
        self.assertEqual(normalized["epoch"], 11)
        self.assertEqual(calls.count("download_bucket_files"), 1)
        self.assertEqual(calls.count("public_get"), 2)
        self.assertEqual(calls.count("dataset_info"), 2)
        self.assertEqual(set(calls), {"space_info", "get_space_runtime", "dataset_info",
                                     "get_paths_info", "get_bucket_paths_info", "hf_hub_download",
                                     "download_bucket_files", "public_get"})

    def test_read_closure_contains_no_provider_mutation_or_runtime_construction(self):
        tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
        methods = {n.func.attr for n in ast.walk(tree)
                   if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
        for name in ("create_commit", "restart_space", "pause_space", "add_space_variable",
                     "delete_space_variable", "set_space_volumes", "upload_bucket_files", "activate"):
            self.assertNotIn(name, methods)
        self.assertNotIn("a11oy_state_store", SCRIPT.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
