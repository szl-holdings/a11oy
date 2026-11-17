#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Observe a replacement writer after a canonical configuration batch.

This is a read-only publisher barrier, not storage admission, a handover request,
snapshot-object verification, or execution authority. Polling has a monotonic
deadline and each SDK child has a timeout; operating-system process creation
itself is not guaranteed to be interruptible by Python.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from functools import lru_cache
import importlib.util
import hashlib
from itertools import islice
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

SPACE = "SZLHOLDINGS/a11oy"
HUB_ORIGIN = "https://huggingface.co"
ORIGIN = "https://szlholdings-a11oy.hf.space"
DATASET = "SZLHOLDINGS/a11oy-state"
BUCKET = "SZLHOLDINGS/szl-evidence"
HEAD_PATH = "state/v2/head.json"
HEARTBEAT_PATH = "a11oy/state/v2/lease/heartbeat.json"
SCHEMA = "szl.hf-config-writer-observation/v1"
OBSERVATION_FIELDS = (
    "observed_at", "hf_revision", "source_revision", "runtime_boot_id",
    "head_commit", "head_sha256", "epoch", "sequence", "writer_id",
    "storage_boot_id", "claim", "state", "owner_source_revision",
    "heartbeat_at_unix", "heartbeat_age_seconds",
)
BASELINE_FIELDS = frozenset((
    "schema", "status", "origin", "provider_writes", "signature",
    "snapshot_objects_verified", "execution_authority", "same_process_binding",
    "observation",
))
STORES = frozenset(("gdw", "series_a", "khipu", "khipu_council", "unay", "khipu_lmdb", "khipu_repl"))
MAX_BYTES = 64 * 1024
SAMPLE_SECONDS = 30
TIMEOUT_SECONDS = 900
POLL_SECONDS = 10
STABLE_SECONDS = 30
MIN_SAMPLES = 3
HEARTBEAT_ADVANCE_SECONDS = 15
FRESH_SECONDS = 30
BASELINE_MAX_SECONDS = 900
CHILD_ENVIRONMENT = frozenset((
    "PATH", "SystemRoot", "SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT",
    "HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "TEMP", "TMP", "TMPDIR",
    "LANG", "LC_ALL", "SSL_CERT_FILE", "SSL_CERT_DIR", "REQUESTS_CA_BUNDLE",
    "CURL_CA_BUNDLE", "HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY", "NO_PROXY",
    "https_proxy", "http_proxy", "all_proxy", "no_proxy", "HF_TOKEN",
))


class Hold(RuntimeError):
    """Only fixed diagnostics may cross the process/report boundary."""


def require(condition, code):
    if not condition:
        raise Hold(code)


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def hex_value(value, size):
    return type(value) is str and re.fullmatch(r"[0-9a-f]{%d}" % size, value) is not None


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "DUPLICATE_JSON_KEY")
            result[key] = value
        return result

    def constant(_value):
        raise Hold("NONFINITE_JSON_VALUE")

    require(type(raw) is bytes and 0 < len(raw) <= 8 * MAX_BYTES, "JSON_SIZE_INVALID")
    try:
        value = json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
    except (ValueError, UnicodeError):
        raise Hold("JSON_INVALID") from None
    require(type(value) is dict, "JSON_OBJECT_REQUIRED")
    return value


def report_wrote(report, owner):
    schema = {"series-a": "szl.hf-series-a-runtime-config/v1",
              "gdw": "szl.hf-gdw-runtime-config/v1"}[owner]
    require(type(report) is dict and report.get("schema") == schema
            and report.get("repo_id") == SPACE and report.get("converged") is True
            and report.get("credential_authority_state") == "VERIFIED", "CONFIG_REPORT_INVALID")
    changed = report.get("variables_changed")
    require(type(changed) is list and len(changed) <= 256
            and all(type(x) is str and re.fullmatch(r"[A-Z][A-Z0-9_]{0,99}", x)
                    for x in changed) and len(changed) == len(set(changed)), "CONFIG_REPORT_INVALID")
    volume = report.get("volume_changed", False) if owner == "gdw" else report.get("volume_changed")
    require(type(volume) is bool and (owner != "gdw" or volume is False), "CONFIG_REPORT_INVALID")
    return bool(changed) or volume


@lru_cache(maxsize=1)
def _relock():
    """Reuse the canonical storage-health invariants without provider effects."""
    path = Path(__file__).with_name("verify_canonical_a11oy.py")
    spec = importlib.util.spec_from_file_location("_configuration_handover_relock", path)
    require(spec is not None and spec.loader is not None, "STORAGE_VALIDATOR_UNAVAILABLE")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sample_freshness(sample, *, now):
    require(type(sample) is dict, "SAMPLE_INVALID")
    start, end = sample.get("started_at"), sample.get("observed_at")
    require(finite(start) and finite(end) and 0 <= end - start <= SAMPLE_SECONDS
            and 0 <= now - end <= 10, "SAMPLE_NOT_FRESH")


def private_head(sample, *, now):
    """Validate immutable HEAD evidence independently of public health reads."""
    sample_freshness(sample, now=now)
    revision = sample.get("head_revision")
    require(hex_value(revision, 40) and revision == sample.get("head_revision_after")
            and hex_value(sample.get("head_sha256"), 64), "HEAD_CHANGED_OR_UNAVAILABLE")
    head = sample.get("head")
    require(type(head) is dict, "OBSERVATION_INCOMPLETE")
    require(head.get("schema") == "szl.a11oy-state-head/v2"
            and head.get("bucket") == BUCKET and type(head.get("epoch")) is int
            and head["epoch"] >= 1 and type(head.get("sequence")) is int and head["sequence"] >= 1
            and hex_value(head.get("writer_id"), 32) and hex_value(head.get("boot_id"), 32),
            "HEAD_IDENTITY_INVALID")
    require(head.get("state") in ("ACTIVE", "HANDOVER", "RELEASED"), "HEAD_NOT_ACTIVE")
    claim, lease = head.get("claim"), head.get("lease")
    require(type(claim) is dict and claim.get("kind") in ("CLEAN", "UNCLEAN_HANDOVER", "FIRST_BOOT")
            and type(lease) is dict and lease.get("heartbeat_path") == HEARTBEAT_PATH
            and finite(lease.get("stale_after_seconds"))
            and 10 <= lease["stale_after_seconds"] <= 3600, "LEASE_INVALID")
    return head


def private_heartbeat(sample, head):
    """Return a validated heartbeat timestamp without inferring public health."""
    beat = sample.get("heartbeat")
    require(type(beat) is dict, "OBSERVATION_INCOMPLETE")
    require(beat.get("schema") == "szl.a11oy-state-heartbeat/v1"
            and all(beat.get(k) == head[k] for k in ("epoch", "writer_id", "boot_id"))
            and type(beat.get("epoch")) is int and finite(beat.get("at_unix")),
            "HEARTBEAT_IDENTITY_MISMATCH")
    try:
        stamp = datetime.strptime(beat.get("at"), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        raise Hold("HEARTBEAT_TIMESTAMP_INVALID") from None
    require(stamp.strftime("%Y-%m-%dT%H:%M:%SZ") == beat["at"]
            and abs(stamp.timestamp() - beat["at_unix"]) < 1, "HEARTBEAT_TIMESTAMP_INVALID")
    age = sample["observed_at"] - beat["at_unix"]
    require(age >= 0, "HEARTBEAT_NOT_FRESH")
    return beat["at_unix"], age


def runtime_identity(sample, *, now, hf_revision):
    """Validate reported source identity independently of storage health."""
    sample_freshness(sample, now=now)
    series = sample.get("series")
    require(type(series) is dict, "RUNTIME_IDENTITY_UNAVAILABLE")
    identity = series.get("runtime_source_identity")
    require(type(identity) is dict and identity.get("status") == "REPORTED"
            and identity.get("method") == "GITHUB_ATTESTED_SOURCE_COPY_SET"
            and identity.get("local_bytes_evidence") == "MEASURED" and identity.get("error") is None
            and identity.get("hf_revision") == hf_revision
            and hex_value(identity.get("source_revision"), 40)
            and series.get("source_revision") == identity["source_revision"]
            and type(series.get("runtime_boot_id")) is str
            and re.fullmatch(r"boot_[0-9a-f]{32}", series["runtime_boot_id"])
            and identity.get("runtime_boot_id") == series["runtime_boot_id"], "RUNTIME_IDENTITY_UNAVAILABLE")
    return identity


def validate_sample(sample, *, now, capture=False):
    head = private_head(sample, now=now)
    end, revision = sample["observed_at"], sample["head_revision"]
    provider = sample.get("provider")
    require(type(provider) is dict and provider == sample.get("provider_after")
            and provider.get("stage") == "RUNNING"
            and hex_value(provider.get("repository_sha"), 40)
            and provider.get("runtime_sha") == provider["repository_sha"], "PROVIDER_NOT_SETTLED")
    status, series = (sample.get(k) for k in ("storage", "series"))
    require(all(type(x) is dict for x in (status, series)), "OBSERVATION_INCOMPLETE")
    state, claim, lease = head["state"], head["claim"], head["lease"]
    require(state == "ACTIVE" or (capture and state == "RELEASED"), "HEAD_NOT_ACTIVE")
    heartbeat_at, age = private_heartbeat(sample, head)
    if state == "ACTIVE":
        require(0 <= age <= min(FRESH_SECONDS, lease["stale_after_seconds"]), "HEARTBEAT_NOT_FRESH")
    require(status.get("schema") == "szl.a11oy-storage-status/v2"
            and status.get("mode") == "FENCED" and status.get("unfenced") is False
            and status.get("epoch") == head["epoch"] and type(status.get("epoch")) is int
            and status.get("claim") == claim["kind"], "PUBLIC_STORAGE_IDENTITY_MISMATCH")
    public_lease = status.get("lease")
    require(type(public_lease) is dict and public_lease.get("state") == state
            and type(public_lease.get("sequence")) is int
            and public_lease["sequence"] == head["sequence"], "PUBLIC_LEASE_MISMATCH")
    require(status.get("role") == ("WRITER" if state == "ACTIVE" else "RELEASED")
            and status.get("writable") is (state == "ACTIVE")
            and status.get("alert") is False and status.get("active_errors") == {}
            and status.get("pending_publish") == [] and status.get("last_error") is None,
            "STORAGE_NOT_HEALTHY")
    if state == "ACTIVE":
        require(finite(public_lease.get("heartbeat_age_s"))
                and 0 <= public_lease["heartbeat_age_s"] <= FRESH_SECONDS, "PUBLIC_HEARTBEAT_NOT_FRESH")
    stores = status.get("stores")
    require(type(stores) is dict and set(stores) == STORES
            and all(type(v) is dict and v.get("health") == "OK"
                    and v.get("blocked_code") is None and v.get("last_error_code") is None
                    for v in stores.values()), "STORE_COVERAGE_NOT_HEALTHY")
    identity = runtime_identity(sample, now=now, hf_revision=provider["runtime_sha"])
    if not capture:
        require(claim["kind"] == "CLEAN", "CONFIG_RESTART_NOT_CLEAN")
        origins = claim.get("origins")
        require(type(origins) is dict and set(origins) == STORES
                and all(v == "RESTORED" for v in origins.values())
                and all(v.get("origin") == "RESTORED" for v in stores.values()), "RESTORE_NOT_OBSERVED")
        try:
            _relock().validate_state_store_status(status)
        except Exception:
            raise Hold("STORAGE_CONTRACT_NOT_HEALTHY") from None
    return {
        "observed_at": end, "hf_revision": provider["runtime_sha"],
        "source_revision": identity["source_revision"], "runtime_boot_id": series["runtime_boot_id"],
        "head_commit": revision, "head_sha256": sample["head_sha256"],
        "epoch": head["epoch"], "sequence": head["sequence"], "writer_id": head["writer_id"],
        "storage_boot_id": head["boot_id"], "claim": claim["kind"], "state": state,
        "owner_source_revision": head.get("source_revision") if hex_value(head.get("source_revision"), 40) else None,
        "heartbeat_at_unix": heartbeat_at, "heartbeat_age_seconds": age,
    }


def provider_state(api):
    info = api.space_info(SPACE)
    runtime = api.get_space_runtime(SPACE)
    return {"repository_sha": info.sha, "runtime_sha": runtime.raw.get("sha"),
            "stage": str(getattr(runtime.stage, "value", runtime.stage))}


def collect_sample():
    """Fixed metadata/object/GET read closure; no state-store instance is constructed."""
    from huggingface_hub import HfApi, hf_hub_download
    import requests

    require(bool(os.environ.get("HF_TOKEN")), "HF_READ_CREDENTIAL_MISSING")
    api = HfApi(endpoint=HUB_ORIGIN, token=os.environ["HF_TOKEN"])
    sample = {"started_at": time.time(), "provider": provider_state(api)}
    info = api.dataset_info(DATASET)
    require(info.private is True and hex_value(info.sha, 40), "HEAD_REPOSITORY_INVALID")
    sample["head_revision"] = info.sha
    with tempfile.TemporaryDirectory(prefix="hf-config-writer-read-") as temporary:
        paths = api.get_paths_info(DATASET, [HEAD_PATH], repo_type="dataset", revision=info.sha)
        require(len(paths) == 1 and paths[0].path == HEAD_PATH
                and type(paths[0].size) is int and 0 < paths[0].size <= MAX_BYTES, "HEAD_SIZE_INVALID")
        path = hf_hub_download(DATASET, HEAD_PATH, repo_type="dataset", revision=info.sha,
                               token=os.environ["HF_TOKEN"], endpoint=HUB_ORIGIN, local_dir=temporary)
        raw = Path(path).read_bytes()
        require(len(raw) == paths[0].size, "HEAD_SIZE_INVALID")
        sample["head"] = strict_json(raw)
        sample["head_sha256"] = hashlib.sha256(raw).hexdigest()
        paths = list(islice(api.get_bucket_paths_info(BUCKET, [HEARTBEAT_PATH]), 2))
        require(len(paths) == 1 and paths[0].path == HEARTBEAT_PATH
                and type(paths[0].size) is int and 0 < paths[0].size <= MAX_BYTES, "HEARTBEAT_SIZE_INVALID")
        target = Path(temporary) / "heartbeat.json"
        api.download_bucket_files(BUCKET, [(paths[0], target)], raise_on_missing_files=True)
        raw = target.read_bytes()
        require(len(raw) == paths[0].size, "HEARTBEAT_SIZE_INVALID")
        sample["heartbeat"] = strict_json(raw)
    with requests.Session() as session:
        for key, route in (("storage", "/api/a11oy/v1/storage/status"),
                           ("series", "/api/a11oy/v1/series-a/status")):
            with session.get(ORIGIN + route, allow_redirects=False, timeout=10, stream=True,
                             headers={"Accept": "application/json", "Cache-Control": "no-cache, no-store"}) as response:
                require(response.status_code == 200, "PUBLIC_READ_UNAVAILABLE")
                require(response.url == ORIGIN + route, "PUBLIC_REDIRECT_REFUSED")
                require(response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
                        == "application/json", "PUBLIC_READ_NOT_JSON")
                chunks, size = [], 0
                for chunk in response.iter_content(16 * 1024):
                    size += len(chunk)
                    require(size <= 2 * MAX_BYTES, "PUBLIC_READ_TOO_LARGE")
                    chunks.append(chunk)
                sample[key] = strict_json(b"".join(chunks))
    sample["head_revision_after"] = api.dataset_info(DATASET).sha
    sample["provider_after"] = provider_state(api)
    sample["observed_at"] = time.time()
    return sample


def read_sample(budget):
    require(finite(budget) and budget > 0, "READ_DEADLINE_EXHAUSTED")
    try:
        result = subprocess.run([sys.executable, "-I", "-B", str(Path(__file__).resolve()), "sample"],
                        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                        timeout=min(SAMPLE_SECONDS, budget), check=False,
                        env={key: value for key, value in os.environ.items() if key in CHILD_ENVIRONMENT})
    except subprocess.TimeoutExpired:
        raise Hold("SAMPLE_TIMEOUT") from None
    except Exception:
        raise Hold("SAMPLE_PROCESS_UNAVAILABLE") from None
    require(result.returncode == 0, "SAMPLE_READ_UNAVAILABLE")
    return strict_json(result.stdout)


def audit(status, **values):
    return {"schema": SCHEMA, "status": status, "origin": ORIGIN,
            "provider_writes": 0, "signature": "UNSIGNED",
            "snapshot_objects_verified": False, "execution_authority": False,
            "same_process_binding": "NOT_ESTABLISHED", **values}


def canonical_baseline(baseline, *, now):
    """Reject unexpected fields and validate retained baseline data before reporting."""
    require(type(baseline) is dict and set(baseline) == BASELINE_FIELDS
            and baseline.get("schema") == SCHEMA and baseline.get("origin") == ORIGIN
            and baseline.get("status") == "BASELINE_OBSERVED"
            and type(baseline.get("provider_writes")) is int and baseline["provider_writes"] == 0
            and baseline.get("signature") == "UNSIGNED"
            and baseline.get("snapshot_objects_verified") is False
            and baseline.get("execution_authority") is False
            and baseline.get("same_process_binding") == "NOT_ESTABLISHED"
            and type(baseline.get("observation")) is dict
            and set(baseline["observation"]) == set(OBSERVATION_FIELDS), "BASELINE_INVALID")
    value = baseline["observation"]
    require(all(hex_value(value.get(k), n) for k, n in (
                ("hf_revision", 40), ("source_revision", 40), ("head_commit", 40),
                ("head_sha256", 64), ("storage_boot_id", 32), ("writer_id", 32)))
            and type(value.get("runtime_boot_id")) is str
            and re.fullmatch(r"boot_[0-9a-f]{32}", value["runtime_boot_id"])
            and type(value.get("epoch")) is int and value["epoch"] >= 1
            and type(value.get("sequence")) is int and value["sequence"] >= 1
            and value.get("state") in ("ACTIVE", "RELEASED")
            and value.get("claim") in ("CLEAN", "UNCLEAN_HANDOVER", "FIRST_BOOT")
            and (value.get("owner_source_revision") is None
                 or hex_value(value["owner_source_revision"], 40)), "BASELINE_INVALID")
    require(finite(value.get("observed_at"))
            and 0 <= now - value["observed_at"] <= BASELINE_MAX_SECONDS, "BASELINE_EXPIRED")
    require(finite(value.get("heartbeat_at_unix")) and value["heartbeat_at_unix"] >= 0
            and finite(value.get("heartbeat_age_seconds")) and value["heartbeat_age_seconds"] >= 0
            and abs(value["observed_at"] - value["heartbeat_at_unix"]
                    - value["heartbeat_age_seconds"]) <= 0.001
            and (value["state"] == "RELEASED"
                 or value["heartbeat_age_seconds"] <= FRESH_SECONDS), "BASELINE_INVALID")
    return {key: value[key] for key in OBSERVATION_FIELDS}


def await_writer(baseline, read, *, clock=time.monotonic, wall=time.time, sleep=time.sleep,
                 timeout=TIMEOUT_SECONDS, record=None):
    before = canonical_baseline(baseline, now=wall())
    require(finite(timeout) and 0 < timeout <= TIMEOUT_SECONDS, "WAIT_BOUND_INVALID")
    deadline, first, previous, count = clock() + timeout, None, None, 0
    observations = []
    highest_epoch = before["epoch"]
    epoch_owners = {before["epoch"]: (before["writer_id"], before["storage_boot_id"])}
    owner_watermarks = {
        (before["epoch"], before["writer_id"], before["storage_boot_id"]):
            (before["sequence"], before["heartbeat_at_unix"]),
    }

    def report(status, **values):
        watermarks = [
            {"epoch": key[0], "writer_id": key[1], "storage_boot_id": key[2],
             "max_sequence": marks[0], "max_heartbeat_at_unix": marks[1]}
            for key, marks in sorted(owner_watermarks.items())
        ]
        return audit(status, baseline=before, observations=list(observations),
                     max_observed_epoch=highest_epoch, owner_watermarks=watermarks, **values)

    while clock() < deadline:
        try:
            sample = read(deadline - clock())
            require(clock() < deadline, "CONFIG_WRITER_TIMEOUT")
            head = sample.get("head") if type(sample) is dict else None
            if (type(head) is dict and head.get("schema") == "szl.a11oy-state-head/v2"
                    and type(head.get("epoch")) is int and head["epoch"] > before["epoch"]
                    and type(head.get("claim")) is dict
                    and head["claim"].get("kind") == "UNCLEAN_HANDOVER"):
                candidate = {"epoch": head["epoch"], "claim": "UNCLEAN_HANDOVER",
                             "head_commit": sample.get("head_revision") if hex_value(sample.get("head_revision"), 40) else None,
                             "owner_source_revision": head.get("source_revision") if hex_value(head.get("source_revision"), 40) else None}
                return report("HOLD", reason="CONFIG_RESTART_NOT_CLEAN", candidate=candidate)
            provider = sample.get("provider") if type(sample) is dict else None
            if type(provider) is dict and any(
                    hex_value(provider.get(key), 40) and provider[key] != before["hf_revision"]
                    for key in ("repository_sha", "runtime_sha")):
                raise Hold("PUBLICATION_CHANGED")
            try:
                observed_identity = runtime_identity(sample, now=wall(), hf_revision=before["hf_revision"])
            except Hold:
                observed_identity = None
            if observed_identity is not None:
                require(observed_identity["source_revision"] == before["source_revision"],
                        "PUBLICATION_CHANGED")
            # Preserve independently valid private evidence even when a later
            # heartbeat or public-health read cannot establish a healthy sample.
            head = private_head(sample, now=wall())
            require(clock() < deadline, "CONFIG_WRITER_TIMEOUT")
            require(head["epoch"] >= highest_epoch, "OBSERVED_EPOCH_REGRESSED")
            owner = (head["writer_id"], head["boot_id"])
            require(head["epoch"] not in epoch_owners
                    or epoch_owners[head["epoch"]] == owner, "LEASE_IDENTITY_CHANGED")
            watermark_key = (head["epoch"], *owner)
            marks = owner_watermarks.get(watermark_key)
            try:
                heartbeat_at, _age = private_heartbeat(sample, head)
            except Hold:
                heartbeat_at = None
            highest_epoch = max(highest_epoch, head["epoch"])
            epoch_owners[head["epoch"]] = owner
            known_heartbeats = [value for value in
                                (heartbeat_at, marks[1] if marks is not None else None)
                                if value is not None]
            owner_watermarks[watermark_key] = (
                max(head["sequence"], marks[0]) if marks is not None else head["sequence"],
                max(known_heartbeats) if known_heartbeats else None,
            )
            require(marks is None or (head["sequence"] >= marks[0]
                    and (heartbeat_at is None or marks[1] is None
                         or heartbeat_at >= marks[1])), "OBSERVATION_REGRESSED")
            current = validate_sample(sample, now=wall(), capture=True)
            require(clock() < deadline, "CONFIG_WRITER_TIMEOUT")
            require(current["hf_revision"] == before["hf_revision"]
                    and current["source_revision"] == before["source_revision"], "PUBLICATION_CHANGED")
            require(current["runtime_boot_id"] != before["runtime_boot_id"]
                    and current["storage_boot_id"] != before["storage_boot_id"]
                    and current["writer_id"] != before["writer_id"]
                    and current["epoch"] > before["epoch"], "REPLACEMENT_NOT_OBSERVED")
            require(current["state"] == "ACTIVE", "REPLACEMENT_NOT_ACTIVE")
            current = validate_sample(sample, now=wall())
            require(clock() < deadline, "CONFIG_WRITER_TIMEOUT")
            key = tuple(current[k] for k in ("hf_revision", "source_revision", "runtime_boot_id",
                                            "storage_boot_id", "writer_id", "epoch"))
            if previous is None or key != previous:
                first, count = (clock(), current["heartbeat_at_unix"]), 1
            else:
                count += 1
            previous = key
            observations.append({"status": "OBSERVED", **current})
            stable = clock() - first[0]
            advance = current["heartbeat_at_unix"] - first[1]
            if count >= MIN_SAMPLES and stable >= STABLE_SECONDS and advance >= HEARTBEAT_ADVANCE_SECONDS:
                require(clock() < deadline, "CONFIG_WRITER_TIMEOUT")
                return report("WRITER_STABLE_AFTER_CONFIG", observation=current,
                              samples=count, stable_seconds=stable, heartbeat_advance_seconds=advance)
        except Hold as error:
            reason = str(error)
            observations.append({"status": "UNAVAILABLE", "reason": reason})
            first, previous, count = None, None, 0
            if reason in ("CONFIG_WRITER_TIMEOUT", "CONFIG_RESTART_NOT_CLEAN",
                          "PUBLICATION_CHANGED", "LEASE_IDENTITY_CHANGED"):
                return report("HOLD", reason=reason)
        except Exception:
            observations.append({"status": "UNAVAILABLE", "reason": "OBSERVATION_UNAVAILABLE"})
            first, previous, count = None, None, 0
        if record is not None:
            record(report("WAITING"))
        remaining = deadline - clock()
        if remaining > 0:
            sleep(min(POLL_SECONDS, remaining))
    return report("HOLD", reason="CONFIG_WRITER_TIMEOUT")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("capture", "wait", "sample"))
    parser.add_argument("--origin")
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--report", action="append", type=Path, default=[])
    parser.add_argument("--owner", choices=("series-a", "gdw"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    valid_capture = False
    try:
        if args.mode == "sample":
            require(not any((args.origin, args.baseline, args.report, args.owner, args.output)),
                    "ARGUMENTS_INVALID")
            print(json.dumps(collect_sample(), allow_nan=False))
            return 0
        require(args.origin == ORIGIN, "CANONICAL_ORIGIN_REQUIRED")
        require(args.output is not None, "OUTPUT_REQUIRED")
        if args.mode == "capture":
            require(not any((args.baseline, args.report, args.owner)), "ARGUMENTS_INVALID")
            valid_capture = True
            report = audit("BASELINE_OBSERVED", observation=validate_sample(
                read_sample(SAMPLE_SECONDS), now=time.time(), capture=True))
        else:
            require(args.baseline is not None and len(args.report) == 1
                    and args.owner is not None, "ARGUMENTS_INVALID")
            config = strict_json(args.report[0].read_bytes())
            if not report_wrote(config, args.owner):
                report = audit("NO_CONFIGURATION_WRITE")
            else:
                report = await_writer(strict_json(args.baseline.read_bytes()), read_sample,
                                      record=lambda value: args.output.write_text(
                                          json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8"))
    except Hold as error:
        status = "BASELINE_UNAVAILABLE" if valid_capture else "HOLD"
        report = audit(status, reason=str(error))
    except Exception:
        status = "BASELINE_UNAVAILABLE" if valid_capture else "HOLD"
        report = audit(status, reason="OBSERVATION_UNAVAILABLE")
    if args.output is not None:
        args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("schema", "status", "provider_writes", "reason") if key in report}))
    return 2 if report["status"] == "HOLD" else 0


if __name__ == "__main__":
    raise SystemExit(main())
