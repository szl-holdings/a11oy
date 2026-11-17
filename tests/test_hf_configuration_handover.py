#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Offline evidence/timeout regressions for the canonical configuration barrier."""
from __future__ import annotations

import ast
import copy
from datetime import datetime, timezone
import importlib.util
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch
from contextlib import contextmanager, redirect_stdout

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".github/scripts/await_hf_configuration_handover.py"
SPEC = importlib.util.spec_from_file_location("config_writer_barrier", SCRIPT)
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)
SOURCE, HF = "a" * 40, "b" * 40
WALL = 1_800_000_000.0
STORE_KINDS = {
    "gdw": "sqlite", "series_a": "sqlite", "khipu": "sqlite",
    "khipu_council": "sqlite", "unay": "sqlite",
    "khipu_lmdb": "lmdb", "khipu_repl": "lmdb",
}
OWNER_TREE = ast.parse((ROOT / "a11oy_state_store.py").read_text(encoding="utf-8"))
OWNER_STATES = {
    target.id: node.value.value
    for node in OWNER_TREE.body if isinstance(node, ast.Assign)
    and isinstance(node.value, ast.Constant)
    for target in node.targets if isinstance(target, ast.Name)
    and target.id in ("STATE_ACTIVE", "STATE_HANDOVER", "STATE_RELEASED")
}


def setUpModule():
    # Only the unused transport imports are stubbed. The unmodified canonical
    # validate_state_store_status body executes in every candidate observation.
    def forbidden_transport(*_args, **_kwargs):
        raise AssertionError("storage validation must not construct a transport")
    requests = ModuleType("requests")
    requests.Session = forbidden_transport
    hub = ModuleType("huggingface_hub")
    hub.HfApi = forbidden_transport
    with patch.dict(sys.modules, {"requests": requests, "huggingface_hub": hub}):
        M._relock()


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
        "stores": {
            label: {"kind": kind, "health": "OK", "origin": "RESTORED",
                    "blocked_code": None, "last_error_code": None,
                    "snapshot_failures": 0,
                    "integrity": "lmdb_read" if kind == "lmdb" else "quick_check",
                    "sha16": "a" * 16, "last_snapshot_age_s": 20.0,
                    "unsnapshotted_change_age_s": None}
            for label, kind in STORE_KINDS.items()
        },
    }
    series = {"schema": "szl.series-a-status/v1", "source_revision": SOURCE, "runtime_boot_id": runtime_boot,
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


@contextmanager
def collector_fixture(raw=None, *, change_response=None, bucket_count=1,
                      on_chunk=None, wall=lambda: WALL):
    """Exercise the actual collector with only its external read adapters replaced."""
    raw = copy.deepcopy(sample(Clock()) if raw is None else raw)
    head_bytes = json.dumps(raw["head"]).encode()
    beat_bytes = json.dumps(raw["heartbeat"]).encode()
    state = {"calls": [], "bucket_yields": 0, "requests": []}
    calls = state["calls"]

    class Api:
        def space_info(self, repo):
            calls.append("space_info")
            assert repo == M.SPACE
            return SimpleNamespace(sha=HF)

        def get_space_runtime(self, repo):
            calls.append("get_space_runtime")
            assert repo == M.SPACE
            return SimpleNamespace(stage="RUNNING", raw={"sha": HF})

        def dataset_info(self, repo):
            calls.append("dataset_info")
            assert repo == M.DATASET
            return SimpleNamespace(private=True, sha="c" * 40)

        def get_paths_info(self, repo, paths, **options):
            calls.append("get_paths_info")
            assert repo == M.DATASET and paths == [M.HEAD_PATH]
            assert options == {"repo_type": "dataset", "revision": "c" * 40}
            return [SimpleNamespace(path=M.HEAD_PATH, size=len(head_bytes))]

        def get_bucket_paths_info(self, repo, paths):
            calls.append("get_bucket_paths_info")
            assert repo == M.BUCKET and paths == [M.HEARTBEAT_PATH]
            for _ in range(bucket_count):
                state["bucket_yields"] += 1
                yield SimpleNamespace(path=M.HEARTBEAT_PATH, size=len(beat_bytes))

        def download_bucket_files(self, repo, files, **options):
            calls.append("download_bucket_files")
            assert repo == M.BUCKET
            assert options == {"raise_on_missing_files": True}
            assert len(files) == 1 and files[0][0].path == M.HEARTBEAT_PATH
            Path(files[0][1]).write_bytes(beat_bytes)

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
        def __init__(self, value, url):
            self.value, self.url = value, url
            self.status_code = 200
            self.headers = {"content-type": "application/json"}
            self.body = None

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def iter_content(self, size):
            assert size == 16 * 1024
            if on_chunk is not None:
                on_chunk()
            yield json.dumps(self.value).encode() if self.body is None else self.body

    class Session:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def get(self, url, **options):
            calls.append("public_get")
            state["requests"].append((url, options))
            assert options["allow_redirects"] is False
            assert options["timeout"] == 10 and options["stream"] is True
            assert set(options["headers"]) == {"Accept", "Cache-Control"}
            assert options["headers"]["Accept"] == "application/json"
            assert url in (M.ORIGIN + "/api/a11oy/v1/storage/status",
                           M.ORIGIN + "/api/a11oy/v1/series-a/status")
            response = Response(raw["storage"] if url.endswith("/storage/status") else raw["series"], url)
            if change_response is not None:
                change_response(response)
            return response

    def api_factory(**options):
        assert options == {"endpoint": "https://huggingface.co", "token": "offline-fixture"}
        return Api()

    hub = SimpleNamespace(HfApi=api_factory, hf_hub_download=download)
    with patch.dict(sys.modules, {"huggingface_hub": hub, "requests": SimpleNamespace(Session=Session)}), \
         patch.dict(M.os.environ, {"HF_TOKEN": "offline-fixture"}), \
         patch.object(M.time, "time", side_effect=wall):
        yield state



class WriterBarrierTests(unittest.TestCase):
    def setUp(self):
        network = patch("socket.socket.connect", side_effect=AssertionError("network forbidden"))
        network.start()
        self.addCleanup(network.stop)

    def wait(self, clock, read=None, before=None, timeout=100, **kwargs):
        return M.await_writer(before or baseline(clock), read or (lambda _budget: sample(clock)),
                              clock=clock.now, wall=clock.wall, sleep=clock.sleep,
                              timeout=timeout, **kwargs)



    def test_retained_baseline_rejects_unknown_fields_without_echoing_surrogates(self):
        for scope in ("top", "observation"):
            with self.subTest(scope=scope), tempfile.TemporaryDirectory() as directory:
                before = baseline(Clock())
                target = before if scope == "top" else before["observation"]
                target["extra"] = {"token": "harmless-token-surrogate",
                                   "url": "https://example.invalid/private-fixture"}
                source = Path(directory) / "baseline.json"
                config_path, output = Path(directory) / "config.json", Path(directory) / "result.json"
                source.write_text(json.dumps(before), encoding="utf-8")
                config_path.write_text(json.dumps(config(changed=["A11OY_STATE_PERIODIC_SECONDS"])), encoding="utf-8")
                printed = io.StringIO()
                with patch.object(M, "read_sample", side_effect=AssertionError("invalid baseline must not read")), redirect_stdout(printed):
                    code = M.main(["wait", "--origin", M.ORIGIN, "--owner", "series-a",
                                   "--report", str(config_path), "--baseline", str(source), "--output", str(output)])
                result = json.loads(output.read_text())
                self.assertEqual(code, 2)
                self.assertEqual(result["reason"], "BASELINE_INVALID")
                rendered = output.read_text() + printed.getvalue()
                self.assertNotIn("harmless-token-surrogate", rendered)
                self.assertNotIn("example.invalid", rendered)
                self.assertNotIn("extra", rendered)

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

    def test_baseline_origin_exact_fields_and_authority_flags_fail_before_reads(self):
        mutations = {
            "foreign origin": lambda b: b.update(origin="https://example.invalid"),
            "missing origin": lambda b: b.pop("origin"),
            "foreign schema": lambda b: b.update(schema="unknown/v1"),
            "unavailable observation": lambda b: b.update(status="BASELINE_UNAVAILABLE"),
            "write admitted": lambda b: b.update(provider_writes=1),
            "boolean write count": lambda b: b.update(provider_writes=False),
            "floating write count": lambda b: b.update(provider_writes=0.0),
            "signed claim": lambda b: b.update(signature="SIGNED"),
            "snapshot authority": lambda b: b.update(snapshot_objects_verified=True),
            "integer snapshot flag": lambda b: b.update(snapshot_objects_verified=0),
            "execution authority": lambda b: b.update(execution_authority=True),
            "integer execution flag": lambda b: b.update(execution_authority=0),
            "same-process claim": lambda b: b.update(same_process_binding="ESTABLISHED"),
            "missing owner source": lambda b: b["observation"].pop("owner_source_revision"),
            "unknown observation field": lambda b: b["observation"].update(extra="untrusted"),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                clock, before = Clock(), baseline(Clock())
                mutate(before)
                with self.assertRaisesRegex(M.Hold, "^BASELINE_INVALID$"):
                    self.wait(clock, before=before,
                              read=lambda _budget: self.fail("invalid baseline must not read"))

    def test_real_canonical_storage_validator_is_reused(self):
        validator = M._relock().validate_state_store_status
        self.assertEqual(Path(validator.__code__.co_filename).resolve(),
                         (ROOT / ".github/scripts/verify_canonical_a11oy.py").resolve())
        value = sample(Clock())["storage"]
        self.assertEqual(validator(value), value)

    def test_canonical_snapshot_integrity_and_freshness_negatives_remain_required(self):
        mutations = {
            "wrong store kind": lambda s: s["gdw"].update(kind="lmdb"),
            "wrong SQLite integrity": lambda s: s["gdw"].update(integrity="lmdb_read"),
            "wrong LMDB integrity": lambda s: s["khipu_lmdb"].update(integrity="quick_check"),
            "missing snapshot digest": lambda s: s["gdw"].pop("sha16"),
            "malformed snapshot digest": lambda s: s["gdw"].update(sha16="g" * 16),
            "snapshot failure": lambda s: s["gdw"].update(snapshot_failures=1),
            "boolean failure count": lambda s: s["gdw"].update(snapshot_failures=False),
            "snapshot stale": lambda s: s["gdw"].update(last_snapshot_age_s=901),
            "snapshot future": lambda s: s["gdw"].update(last_snapshot_age_s=-1),
            "snapshot nonfinite": lambda s: s["gdw"].update(last_snapshot_age_s=float("nan")),
            "boolean snapshot age": lambda s: s["gdw"].update(last_snapshot_age_s=True),
            "unsnapshotted changes stale": lambda s: s["gdw"].update(unsnapshotted_change_age_s=901),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                value = sample(Clock())
                mutate(value["storage"]["stores"])
                with self.assertRaisesRegex(M.Hold, "^STORAGE_CONTRACT_NOT_HEALTHY$"):
                    M.validate_sample(value, now=WALL)

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
                self.assertEqual(job.count("await_hf_configuration_handover.py capture"), 2)
                self.assertEqual(job.count("await_hf_configuration_handover.py wait"), 2)
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

    def test_private_head_epoch_survives_failed_public_observation(self):
        mutations = {
            "unhealthy public store": lambda value: value["storage"]["stores"]["gdw"].update(health="BLOCKED"),
            "incomplete public source": lambda value: value["series"].pop("runtime_source_identity"),
            "mismatched heartbeat owner": lambda value: value["heartbeat"].update(writer_id="f" * 32),
            "private handover in progress": lambda value: value["head"].update(
                state=OWNER_STATES["STATE_HANDOVER"], transition="HANDOVER_REQUEST",
                handover={"requested_by": "e" * 32,
                          "requested_at": datetime.fromtimestamp(WALL, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                clock = Clock()
                def read(_budget):
                    if clock.elapsed == 0:
                        value = sample(clock, epoch=12, boot=3)
                        mutate(value)
                        return value
                    return sample(clock, epoch=11, boot=2)
                result = self.wait(clock, read, timeout=80)
                self.assertEqual(result["status"], "HOLD")
                self.assertEqual(result["max_observed_epoch"], 12)
                self.assertTrue(any(o.get("reason") == "OBSERVED_EPOCH_REGRESSED"
                                    for o in result["observations"]))

    def test_private_state_contract_matches_the_canonical_owner(self):
        self.assertEqual(set(OWNER_STATES), {"STATE_ACTIVE", "STATE_HANDOVER", "STATE_RELEASED"})
        clock = Clock()
        for state in OWNER_STATES.values():
            with self.subTest(state=state):
                value = sample(clock, state=state)
                self.assertIs(M.private_head(value, now=clock.wall()), value["head"])
                if state != OWNER_STATES["STATE_ACTIVE"]:
                    with self.assertRaises(M.Hold):
                        M.validate_sample(value, now=clock.wall())
        for invalid in ("HANDOVER", None, [], {}, True):
            with self.subTest(invalid=invalid), self.assertRaises(M.Hold):
                M.private_head(sample(clock, state=invalid), now=clock.wall())

    def test_new_owner_sequence_must_advance_the_global_head_sequence(self):
        transition = next(node for node in OWNER_TREE.body
                          if isinstance(node, ast.FunctionDef) and node.name == "validate_transition")
        # Execute only the reviewed pure transition validator, never StateStore.
        namespace = {**OWNER_STATES, "StorageBlocked": M.Hold}
        module = ast.Module(body=[ast.ImportFrom(module="__future__", level=0,
                            names=[ast.alias(name="annotations")]), transition], type_ignores=[])
        exec(compile(ast.fix_missing_locations(module), "canonical-transition", "exec"), namespace)
        before = {"epoch": 10, "sequence": 1000, "writer_id": "a", "state": "RELEASED", "snapshots": {}}
        for sequence in (1, 999, 1000):
            with self.subTest(sequence=sequence):
                after = {"epoch": 11, "sequence": sequence, "writer_id": "b", "state": "ACTIVE",
                         "snapshots": {}, "transition": "CLAIM"}
                with self.assertRaises(M.Hold):
                    namespace["validate_transition"](before, after)
                clock = Clock()
                def read(_budget):
                    value = sample(clock)
                    value["head"]["sequence"] = value["storage"]["lease"]["sequence"] = sequence
                    return value
                result = self.wait(clock, read, timeout=80)
                self.assertEqual(result["status"], "HOLD")
                self.assertEqual(result["reason"], "REPLACEMENT_SEQUENCE_NOT_ADVANCED")
                self.assertEqual(result["max_observed_epoch"], 11)
                self.assertEqual(result["max_observed_sequence"], 1000)
                self.assertEqual(clock.elapsed, 0)
        namespace["validate_transition"](before, dict(after, sequence=1001))

    def test_global_sequence_survives_failed_health_and_another_owner(self):
        for sequence in (1100, 1150):
            with self.subTest(sequence=sequence):
                clock = Clock()
                def read(_budget):
                    first = clock.elapsed == 0
                    value = sample(clock, epoch=11 if first else 12, boot=2 if first else 3)
                    value["head"]["sequence"] = value["storage"]["lease"]["sequence"] = 1150 if first else sequence
                    if first:
                        value["storage"]["stores"]["gdw"]["health"] = "BLOCKED"
                    return value
                result = self.wait(clock, read, timeout=80)
                self.assertEqual(result["status"], "HOLD")
                self.assertEqual(result["reason"], "REPLACEMENT_SEQUENCE_NOT_ADVANCED")
                self.assertEqual(result["max_observed_epoch"], 12)
                self.assertEqual(result["max_observed_sequence"], 1150)

    def test_canonical_pending_handover_retains_sequence_without_claiming_health(self):
        clock, records = Clock(), []
        def read(_budget):
            first = clock.elapsed == 0
            value = sample(clock, state=OWNER_STATES["STATE_HANDOVER"] if first else "ACTIVE")
            value["head"]["sequence"] = value["storage"]["lease"]["sequence"] = 1105 if first else 1104
            return value
        result = self.wait(clock, read, timeout=80, record=records.append)
        self.assertEqual(result["status"], "HOLD")
        self.assertEqual(result["max_observed_sequence"], 1105)
        self.assertEqual(records[0]["max_observed_sequence"], 1105)
        self.assertFalse(any(o.get("status") == "OBSERVED" for o in result["observations"]))

    def test_global_sequence_can_advance_across_clean_owners(self):
        clock = Clock()
        def read(_budget):
            first = clock.elapsed == 0
            value = sample(clock, epoch=11 if first else 12, boot=2 if first else 3)
            value["head"]["sequence"] = value["storage"]["lease"]["sequence"] = 1150 if first else 1151
            if first:
                value["storage"]["stores"]["gdw"]["health"] = "BLOCKED"
            return value
        result = self.wait(clock, read, timeout=80)
        self.assertEqual(result["status"], "WRITER_STABLE_AFTER_CONFIG")
        self.assertEqual(result["max_observed_epoch"], 12)
        self.assertEqual(result["max_observed_sequence"], 1151)

    def test_same_owner_cannot_move_backwards_from_handover_or_release(self):
        for before_state, after_state in (
                (OWNER_STATES["STATE_HANDOVER"], "ACTIVE"), ("RELEASED", "ACTIVE"),
                ("RELEASED", OWNER_STATES["STATE_HANDOVER"])):
            with self.subTest(before=before_state, after=after_state):
                clock = Clock()
                def read(_budget):
                    first = clock.elapsed == 0
                    value = sample(clock, state=before_state if first else after_state)
                    value["head"]["sequence"] = value["storage"]["lease"]["sequence"] = 1105 if first else 1106
                    return value
                result = self.wait(clock, read, timeout=80)
                self.assertEqual(result["status"], "HOLD")
                self.assertEqual(result["reason"], "LEASE_STATE_REGRESSED")
                self.assertEqual(clock.elapsed, 10)
                owner = next(o for o in result["owner_watermarks"] if o["epoch"] == 11)
                self.assertEqual(owner["furthest_state"], before_state)
                self.assertEqual(owner["max_sequence"], 1106)

    def test_forward_owner_states_then_a_clean_successor_can_settle(self):
        clock = Clock()
        def read(_budget):
            index = min(int(clock.elapsed // 10), 3)
            state = ("ACTIVE", OWNER_STATES["STATE_HANDOVER"], "RELEASED", "ACTIVE")[index]
            value = sample(clock, epoch=11 if index < 3 else 12,
                           boot=2 if index < 3 else 3, state=state)
            value["head"]["sequence"] = value["storage"]["lease"]["sequence"] = 1100 + index
            return value
        result = self.wait(clock, read, timeout=100)
        self.assertEqual(result["status"], "WRITER_STABLE_AFTER_CONFIG")
        self.assertEqual(clock.elapsed, 60)
        owners = {o["epoch"]: o for o in result["owner_watermarks"]}
        self.assertEqual(owners[11]["furthest_state"], "RELEASED")
        self.assertEqual(owners[12]["furthest_state"], "ACTIVE")
        self.assertEqual(result["max_observed_sequence"], 1103)

    def test_private_owner_identity_survives_failed_public_health(self):
        clock = Clock()
        def read(_budget):
            value = sample(clock, boot=2 if clock.elapsed == 0 else 3)
            if clock.elapsed == 0:
                value["storage"]["stores"]["gdw"]["health"] = "BLOCKED"
            return value
        result = self.wait(clock, read, timeout=80)
        self.assertEqual(result["status"], "HOLD")
        self.assertEqual(result["reason"], "LEASE_IDENTITY_CHANGED")
        self.assertEqual(clock.elapsed, 10)

    def test_private_sequence_survives_failed_public_health(self):
        clock = Clock()
        def read(_budget):
            value = sample(clock)
            value["head"]["sequence"] = value["storage"]["lease"]["sequence"] = (
                1105 if clock.elapsed == 0 else 1104)
            if clock.elapsed == 0:
                value["storage"]["stores"]["gdw"]["health"] = "BLOCKED"
            return value
        result = self.wait(clock, read, timeout=80)
        self.assertEqual(result["status"], "HOLD")
        owner = next(o for o in result["owner_watermarks"] if o["epoch"] == 11)
        self.assertEqual(owner["max_sequence"], 1105)

    def test_valid_private_heartbeat_survives_failed_public_health(self):
        clock = Clock()
        def read(_budget):
            value = sample(clock, beat=WALL - 1 if clock.elapsed == 10 else None)
            if clock.elapsed == 0:
                value["storage"]["stores"]["gdw"]["health"] = "BLOCKED"
            return value
        result = self.wait(clock, read, timeout=80)
        self.assertEqual(result["status"], "WRITER_STABLE_AFTER_CONFIG")
        self.assertTrue(any(o.get("reason") == "OBSERVATION_REGRESSED"
                            for o in result["observations"]))
        self.assertEqual(clock.elapsed, 50)

    def test_invalid_private_heartbeat_cannot_poison_an_owner_watermark(self):
        future = WALL + 600
        future_stamp = datetime.fromtimestamp(future, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        mutations = {
            "foreign owner": {"writer_id": "f" * 32, "at_unix": future, "at": future_stamp},
            "future time": {"at_unix": future, "at": future_stamp},
            "invalid timestamp": {"at": "private-value-not-for-report"},
            "boolean timestamp": {"at_unix": True},
            "nonfinite timestamp": {"at_unix": float("nan")},
        }
        for name, fields in mutations.items():
            with self.subTest(name=name):
                clock, records = Clock(), []
                def read(_budget):
                    value = sample(clock)
                    if clock.elapsed == 0:
                        value["heartbeat"].update(fields)
                        value["storage"]["stores"]["gdw"]["health"] = "BLOCKED"
                    return value
                result = self.wait(clock, read, timeout=80, record=records.append)
                first_owner = next(o for o in records[0]["owner_watermarks"] if o["epoch"] == 11)
                self.assertIsNone(first_owner["max_heartbeat_at_unix"])
                self.assertEqual(first_owner["max_sequence"], 1100)
                self.assertEqual(result["status"], "WRITER_STABLE_AFTER_CONFIG")
                self.assertEqual(clock.elapsed, 40)
                self.assertNotIn("private-value", json.dumps(result))

    def test_unbracketed_private_head_does_not_establish_an_epoch_watermark(self):
        clock = Clock()
        def read(_budget):
            if clock.elapsed == 0:
                value = sample(clock, epoch=12, boot=3)
                value["head_revision_after"] = "e" * 40
                return value
            return sample(clock, epoch=11, boot=2)
        result = self.wait(clock, read, timeout=80)
        self.assertEqual(result["status"], "WRITER_STABLE_AFTER_CONFIG")
        self.assertEqual(result["max_observed_epoch"], 11)
        self.assertEqual(clock.elapsed, 40)

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
        result = self.wait(clock, lambda _budget: sample(
            clock, epoch=11 if clock.elapsed == 0 else 12,
            boot=2 if clock.elapsed == 0 else 3,
            claim="UNCLEAN_HANDOVER" if clock.elapsed == 0 else "CLEAN"))
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

    def test_valid_foreign_source_is_terminal_even_when_other_evidence_fails(self):
        mutations = {
            "unhealthy public store": lambda value: value["storage"]["stores"]["gdw"].update(health="BLOCKED"),
            "unbracketed private HEAD": lambda value: value.update(head_revision_after="e" * 40),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                clock = Clock()
                def read(_budget):
                    value = sample(clock)
                    if clock.elapsed == 0:
                        value["series"]["source_revision"] = "f" * 40
                        value["series"]["runtime_source_identity"]["source_revision"] = "f" * 40
                        mutate(value)
                    return value
                result = self.wait(clock, read, timeout=80)
                self.assertEqual(result["status"], "HOLD")
                self.assertEqual(result["reason"], "PUBLICATION_CHANGED")
                self.assertEqual(clock.elapsed, 0)

    def test_malformed_source_identity_cannot_change_the_expected_source(self):
        mutations = {
            "unavailable identity": {"status": "UNAVAILABLE"},
            "unmeasured identity": {"local_bytes_evidence": "UNKNOWN"},
            "unsupported method": {"method": "UNKNOWN"},
            "foreign HF identity": {"hf_revision": "e" * 40},
            "mismatched process boot": {"runtime_boot_id": "boot_" + "e" * 32},
        }
        for name, fields in mutations.items():
            with self.subTest(name=name):
                clock = Clock()
                def read(_budget):
                    value = sample(clock)
                    if clock.elapsed == 0:
                        value["series"]["source_revision"] = "f" * 40
                        identity = value["series"]["runtime_source_identity"]
                        identity["source_revision"] = "f" * 40
                        identity.update(fields)
                        value["storage"]["stores"]["gdw"]["health"] = "BLOCKED"
                    return value
                result = self.wait(clock, read, timeout=80)
                self.assertEqual(result["status"], "WRITER_STABLE_AFTER_CONFIG")
                self.assertEqual(result["baseline"]["source_revision"], SOURCE)
                self.assertEqual(result["observation"]["source_revision"], SOURCE)
                self.assertEqual(clock.elapsed, 40)

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
                    code = M.main(["wait", "--origin", M.ORIGIN, "--owner", owner, "--report", str(report),
                                   "--baseline", str(Path(directory) / "absent.json"), "--output", str(output)])
                self.assertEqual(code, 0)
                self.assertEqual(json.loads(output.read_text())["status"], "NO_CONFIGURATION_WRITE")
        self.assertTrue(M.report_wrote(config(changed=["A11OY_STATE_PERIODIC_SECONDS"]), "series-a"))
        value = config()
        value["volume_changed"] = True
        self.assertTrue(M.report_wrote(value, "series-a"))

    def test_cli_requires_the_fixed_origin_before_capture_or_no_write(self):
        for mode in ("capture", "wait"):
            for origin in (None, "https://example.invalid", M.ORIGIN + "/", "http://szlholdings-a11oy.hf.space"):
                with self.subTest(mode=mode, origin=origin), tempfile.TemporaryDirectory() as directory:
                    output, report = Path(directory) / "result.json", Path(directory) / "config.json"
                    report.write_text(json.dumps(config()), encoding="utf-8")
                    args = [mode, "--output", str(output)]
                    if origin is not None:
                        args += ["--origin", origin]
                    if mode == "wait":
                        args += ["--owner", "series-a", "--report", str(report),
                                 "--baseline", str(Path(directory) / "absent.json")]
                    with patch.object(M, "read_sample", side_effect=AssertionError("origin must fail before read")), redirect_stdout(io.StringIO()):
                        code = M.main(args)
                    self.assertEqual(code, 2)
                    self.assertEqual(json.loads(output.read_text())["reason"], "CANONICAL_ORIGIN_REQUIRED")

    def test_cli_accepts_exactly_one_report_for_the_selected_owner(self):
        for owner, count, report_owner in (("series-a", 0, "series-a"),
                                            ("series-a", 2, "series-a"),
                                            ("series-a", 1, "gdw"),
                                            ("gdw", 1, "series-a")):
            with self.subTest(owner=owner, count=count, report_owner=report_owner), tempfile.TemporaryDirectory() as directory:
                report, output = Path(directory) / "config.json", Path(directory) / "result.json"
                report.write_text(json.dumps(config(report_owner)), encoding="utf-8")
                args = ["wait", "--origin", M.ORIGIN, "--owner", owner,
                        "--baseline", str(Path(directory) / "absent.json"), "--output", str(output)]
                for _ in range(count):
                    args += ["--report", str(report)]
                with patch.object(M, "read_sample", side_effect=AssertionError("invalid report must not read")), redirect_stdout(io.StringIO()):
                    code = M.main(args)
                self.assertEqual(code, 2)
                self.assertEqual(json.loads(output.read_text())["reason"],
                                 "ARGUMENTS_INVALID" if count != 1 else "CONFIG_REPORT_INVALID")

    def test_malformed_owner_specific_effects_are_rejected(self):
        oversized = config(changed=["VARIABLE_" + str(n) for n in range(257)])
        gdw_volume = config("gdw")
        gdw_volume["volume_changed"] = True
        for owner, value in (("series-a", oversized), ("gdw", gdw_volume)):
            with self.subTest(owner=owner), self.assertRaisesRegex(M.Hold, "^CONFIG_REPORT_INVALID$"):
                M.report_wrote(value, owner)

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
                code = M.main(["capture", "--origin", M.ORIGIN, "--output", str(output)])
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
                self.assertEqual(M.main(["capture", "--origin", M.ORIGIN, "--output", str(output)]), 0)
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
        self.assertEqual(called[0][0][-1], "sample")
        with patch.object(M.subprocess, "run", return_value=SimpleNamespace(
                returncode=2, stdout=b"private-value")):
            with self.assertRaisesRegex(M.Hold, "^SAMPLE_READ_UNAVAILABLE$"):
                M.read_sample(30)

    def test_child_budget_is_capped_and_invalid_budgets_do_not_spawn(self):
        with patch.object(M.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout=b"{}")) as runner:
            self.assertEqual(M.read_sample(900), {})
            self.assertEqual(runner.call_args.kwargs["timeout"], M.SAMPLE_SECONDS)
        for value in (0, -1, True, float("nan"), float("inf")):
            with self.subTest(value=value), patch.object(M.subprocess, "run") as runner:
                with self.assertRaisesRegex(M.Hold, "^READ_DEADLINE_EXHAUSTED$"):
                    M.read_sample(value)
                runner.assert_not_called()

    def test_duplicate_nonfinite_and_oversized_json_fail_closed(self):
        for raw in (b'{"x":1,"x":2}', b'{"x":NaN}', b"[]", b" " * (8 * M.MAX_BYTES + 1)):
            with self.assertRaises(M.Hold):
                M.strict_json(raw)


    def test_real_adapter_reads_iterable_bucket_metadata_and_never_forwards_hub_auth_to_public_gets(self):
        with collector_fixture() as fixture:
            observed = M.collect_sample()
            normalized = M.validate_sample(observed, now=WALL)
        calls = fixture["calls"]
        self.assertEqual(normalized["epoch"], 11)
        self.assertEqual(fixture["bucket_yields"], 1)
        self.assertEqual(calls.count("download_bucket_files"), 1)
        self.assertEqual(calls.count("public_get"), 2)
        self.assertEqual(calls.count("dataset_info"), 2)
        self.assertEqual(set(calls), {"space_info", "get_space_runtime", "dataset_info",
                                     "get_paths_info", "get_bucket_paths_info", "hf_hub_download",
                                     "download_bucket_files", "public_get"})

    def test_public_readback_refuses_redirect_non_json_and_malformed_bodies(self):
        cases = (
            ("redirect status", lambda r: setattr(r, "status_code", 302), "PUBLIC_READ_UNAVAILABLE"),
            ("foreign URL", lambda r: setattr(r, "url", "https://example.invalid/private-fixture"), "PUBLIC_REDIRECT_REFUSED"),
            ("HTML", lambda r: r.headers.update({"content-type": "text/html"}), "PUBLIC_READ_NOT_JSON"),
            ("missing content type", lambda r: r.headers.clear(), "PUBLIC_READ_NOT_JSON"),
            ("oversized", lambda r: setattr(r, "body", b"x" * (2 * M.MAX_BYTES + 1)), "PUBLIC_READ_TOO_LARGE"),
            ("malformed", lambda r: setattr(r, "body", b"private-body-surrogate"), "JSON_INVALID"),
            ("duplicate key", lambda r: setattr(r, "body", b'{"x":1,"x":2}'), "DUPLICATE_JSON_KEY"),
            ("nonfinite", lambda r: setattr(r, "body", b'{"x":NaN}'), "NONFINITE_JSON_VALUE"),
        )
        for name, mutate, reason in cases:
            with self.subTest(name=name), collector_fixture(change_response=mutate):
                with self.assertRaisesRegex(M.Hold, "^" + reason + "$") as caught:
                    M.collect_sample()
                self.assertNotIn("private-fixture", str(caught.exception))
                self.assertNotIn("private-body-surrogate", str(caught.exception))

    def test_iterable_bucket_metadata_is_bounded_and_requires_one_object(self):
        for count in (0, 3):
            with self.subTest(count=count), collector_fixture(bucket_count=count) as fixture:
                with self.assertRaisesRegex(M.Hold, "^HEARTBEAT_SIZE_INVALID$"):
                    M.collect_sample()
                self.assertEqual(fixture["bucket_yields"], min(count, 2))
                self.assertNotIn("download_bucket_files", fixture["calls"])

    def test_slow_public_body_cannot_make_a_late_final_observation_succeed(self):
        clock = Clock()
        def read(_budget):
            if clock.elapsed != 30:
                return sample(clock)
            with collector_fixture(sample(clock), on_chunk=lambda: clock.sleep(6), wall=clock.wall):
                return M.collect_sample()
        result = self.wait(clock, read, timeout=35)
        self.assertEqual(result["status"], "HOLD")
        self.assertEqual(result["reason"], "CONFIG_WRITER_TIMEOUT")

    def test_released_replacement_cannot_be_reported_as_a_settled_writer(self):
        clock = Clock()
        result = self.wait(clock, lambda _budget: sample(clock, state="RELEASED"), timeout=35)
        self.assertEqual(result["status"], "HOLD")
        self.assertEqual(result["reason"], "CONFIG_WRITER_TIMEOUT")
        self.assertTrue(any(value.get("reason") == "REPLACEMENT_NOT_ACTIVE"
                            for value in result["observations"]))

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
