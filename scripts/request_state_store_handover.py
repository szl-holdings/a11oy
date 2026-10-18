#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Operator-only v2 handover request; default is a read-only preflight.

This requests the existing writer's drain. It never initializes stores, claims a
lease, restarts a service, or publishes a Space. RELEASE observation alone does
not verify snapshot objects or authorize deployment. There is no cancellation.
"""

import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import a11oy_state_store as ss


class Hold(Exception):
    pass


def digest(body):
    return hashlib.sha256(body).hexdigest()


def utc(stamp):
    return datetime.fromtimestamp(stamp, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def timestamp(value):
    if not isinstance(value, str):
        raise Hold("UTC_TIMESTAMP_INVALID")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        raise Hold("UTC_TIMESTAMP_INVALID") from None
    if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != value:
        raise Hold("UTC_TIMESTAMP_INVALID")
    return parsed.timestamp()


def checked_hex(value, length):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{%d}" % length, value):
        raise Hold("EXPECTED_IDENTITY_INVALID")
    return value


def coverage(head):
    required = {spec.label: spec.kind for spec in ss.STORES}
    if set(head["snapshots"]) != set(required):
        raise Hold("REQUIRED_SNAPSHOT_COVERAGE_MISSING")
    for label, entry in head["snapshots"].items():
        if (entry["kind"] != required[label] or not 1 <= entry["epoch"] <= head["epoch"]
                or entry["seq"] < 1 or entry["logical_sha256"] is None):
            raise Hold("REQUIRED_SNAPSHOT_METADATA_INVALID")
        if ((entry["kind"] == "lmdb") != (entry["integrity"] == "lmdb_read")):
            raise Hold("REQUIRED_SNAPSHOT_METADATA_INVALID")
        timestamp(entry["taken_at"])


def fresh_heartbeat(objects, head, clock):
    lease = head["lease"]
    stale = lease["stale_after_seconds"]
    if (lease["heartbeat_path"] != ss.HEARTBEAT_PATH or type(stale) not in (int, float)
            or not math.isfinite(stale) or not 10 <= stale <= 3600):
        raise Hold("LEASE_METADATA_INVALID")
    timestamp(lease["renewed_at"])
    raw = objects.get_bytes(ss.HEARTBEAT_PATH, limit=ss.MAX_SMALL_OBJECT_BYTES)
    if type(raw) is not bytes or not 1 <= len(raw) <= ss.MAX_SMALL_OBJECT_BYTES:
        raise Hold("HEARTBEAT_UNAVAILABLE")
    try:
        beat = json.loads(raw)
    except (ValueError, UnicodeError):
        raise Hold("HEARTBEAT_INVALID") from None
    if (type(beat) is not dict or beat.get("schema") != ss.HEARTBEAT_SCHEMA
            or type(beat.get("epoch")) is not int
            or any(beat.get(key) != head[key] for key in ("epoch", "writer_id", "boot_id"))):
        raise Hold("HEARTBEAT_IDENTITY_MISMATCH")
    stamp = beat.get("at_unix")
    now = clock()
    if (type(stamp) not in (int, float) or not math.isfinite(stamp)
            or abs(timestamp(beat.get("at")) - stamp) >= 1
            or not 0 <= now - stamp <= min(stale, 120)):
        raise Hold("HEARTBEAT_NOT_FRESH")
    return {"sha256": digest(raw), "at": beat["at"], "age_seconds": now - stamp}


def expected_head(backend, expected, bucket):
    for key, length in (("commit", 40), ("sha256", 64), ("writer_id", 32), ("boot_id", 32)):
        checked_hex(expected.get(key), length)
    if type(expected.get("epoch")) is not int or expected["epoch"] < 1:
        raise Hold("EXPECTED_IDENTITY_INVALID")
    observed = backend.observe()
    if observed.revision != expected["commit"] or type(observed.body) is not bytes:
        raise Hold("EXPECTED_HEAD_COMMIT_MISMATCH")
    if digest(observed.body) != expected["sha256"]:
        raise Hold("EXPECTED_HEAD_DIGEST_MISMATCH")
    head = ss.parse_head(observed.body)
    if any(head[key] != expected[key] for key in ("writer_id", "boot_id", "epoch")):
        raise Hold("EXPECTED_WRITER_MISMATCH")
    if head["bucket"] != bucket:
        raise Hold("EXPECTED_BUCKET_MISMATCH")
    if head["state"] != ss.STATE_ACTIVE:
        raise Hold("HEAD_NOT_ACTIVE")
    coverage(head)
    return observed, head


def make_request(observed, head, requested_by, operation_id, now):
    checked_hex(requested_by, 32)
    checked_hex(operation_id, 32)
    if requested_by in (head["writer_id"], head["boot_id"]):
        raise Hold("REQUESTER_NOT_UNIQUE")
    if operation_id == head["operation_id"] or operation_id == requested_by:
        raise Hold("OPERATION_NOT_UNIQUE")
    proposal = copy.deepcopy(head)
    proposal.update(operation_id=operation_id, sequence=head["sequence"] + 1,
                    previous_manifest_sha256=digest(observed.body),
                    transition="HANDOVER_REQUEST", state=ss.STATE_HANDOVER,
                    handover={"requested_by": requested_by, "requested_at": utc(now)})
    timestamp(proposal["handover"]["requested_at"])
    ss.validate_head(proposal)
    ss.validate_transition(head, proposal)
    return proposal


def released_head(observed, request):
    if type(observed.body) is not bytes:
        raise Hold("RELEASE_HEAD_MISSING")
    checked_hex(observed.revision, 40)
    head = ss.parse_head(observed.body)
    body = ss.canonical(request)
    if observed.body == body:
        return None
    if (head["state"] != ss.STATE_RELEASED or head["transition"] != "RELEASE"
            or head["handover"] is not None
            or head["sequence"] != request["sequence"] + 1
            or head["previous_manifest_sha256"] != digest(body)
            or head["operation_id"] == request["operation_id"]):
        raise Hold("RELEASE_CAUSALITY_MISMATCH")
    for key in ("epoch", "writer_id", "boot_id", "bucket", "source_revision", "claim"):
        if head[key] != request[key]:
            raise Hold("RELEASE_IDENTITY_MISMATCH")
    if any(head["lease"][key] != request["lease"][key]
           for key in ("heartbeat_path", "stale_after_seconds")):
        raise Hold("RELEASE_LEASE_MISMATCH")
    if timestamp(head["lease"]["renewed_at"]) < timestamp(request["handover"]["requested_at"]):
        raise Hold("RELEASE_TIME_INVALID")
    ss.validate_transition(request, head)
    coverage(head)
    return head


def wait_release(backend, request, *, observed=None, timeout=180, poll=3,
                 monotonic=time.monotonic, sleep=time.sleep):
    deadline = monotonic() + timeout
    while True:
        observed = observed or backend.observe()
        released = released_head(observed, request)
        if released is not None:
            if backend.read_at(observed.revision) != observed.body:
                raise Hold("RELEASE_READBACK_MISMATCH")
            return {"commit": observed.revision, "sha256": digest(observed.body),
                    "sequence": released["sequence"], "epoch": released["epoch"],
                    "snapshot_sha256": {key: entry["sha256"]
                                        for key, entry in released["snapshots"].items()}}
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise Hold("RELEASE_TIMEOUT")
        sleep(min(poll, remaining))
        observed = None


def observe_receipt(backend, path, *, expected, bucket, dataset=ss.DEFAULT_DATASET, timeout=180,
                    monotonic=time.monotonic, sleep=time.sleep):
    """Read-only recovery of one recorded intent; never submit or claim."""
    report = {"schema": "szl.a11oy-handover-operator/v1", "status": "HOLD",
              "signature": "UNSIGNED", "execute": False, "mode": "OBSERVE_RECEIPT",
              "object_preservation": "NOT_VERIFIED", "runtime_health": "NOT_VERIFIED",
              "publication_authorized": False}
    try:
        if not math.isfinite(timeout) or not 1 <= timeout <= 900:
            raise Hold("WAIT_BOUND_INVALID")
        if path.stat().st_size > 1024 * 1024:
            raise Hold("RECEIPT_TOO_LARGE")
        previous, intent = None, None
        for sequence, line in enumerate(path.read_bytes().splitlines(keepends=True), 1):
            item = json.loads(line)
            if (ss.canonical(item) != line or item.get("sequence") != sequence
                    or item.get("previous_sha256") != previous or item.get("signature") != "UNSIGNED"):
                raise Hold("RECEIPT_CHAIN_INVALID")
            previous = digest(line)
            if item["payload"].get("event") == "REQUEST_INTENT":
                if intent is not None:
                    raise Hold("RECEIPT_INTENT_AMBIGUOUS")
                intent = item["payload"]
        if (intent is None or intent.get("expected") != expected
                or intent.get("target") != {"dataset": dataset, "bucket": bucket}):
            raise Hold("RECEIPT_EXPECTATION_MISMATCH")
        original = ss.Observation(expected["commit"], backend.read_at(expected["commit"]))
        # Reuse the strict initial checks against immutable original bytes,
        # without mistaking a later live RELEASED head for a new request target.
        class OriginalOnly:
            def observe(self):
                return original
        observed, head = expected_head(OriginalOnly(), expected, bucket)
        saved = intent["request"]
        request = make_request(observed, head, saved["requested_by"], saved["operation_id"],
                               timestamp(saved["requested_at"]))
        if digest(ss.canonical(request)) != saved["sha256"] or request["sequence"] != saved["sequence"]:
            raise Hold("RECEIPT_REQUEST_MISMATCH")
        report["release"] = wait_release(backend, request, timeout=timeout,
                                          monotonic=monotonic, sleep=sleep)
        report.update(status="RELEASE_OBSERVED", reason="OBJECT_AND_RUNTIME_VERIFICATION_REQUIRED")
    except Exception as error:
        report["reason"] = str(error) if isinstance(error, Hold) else "RECEIPT_OBSERVATION_FAILED"
    return report


class FreshSubmitBackend:
    """Recheck the original writer heartbeat before every CAS submission."""

    def __init__(self, backend, objects, head, clock):
        self.backend, self.objects, self.head, self.clock = backend, objects, head, clock

    def observe(self):
        return self.backend.observe()

    def read_at(self, revision):
        return self.backend.read_at(revision)

    def submit(self, parent, body, operation_id):
        fresh_heartbeat(self.objects, self.head, self.clock)
        return self.backend.submit(parent, body, operation_id)


def request_handover(backend, objects, *, expected, bucket, dataset=ss.DEFAULT_DATASET, execute=False,
                     record=None, clock=time.time, monotonic=time.monotonic,
                     sleep=time.sleep, timeout=180, poll=3, requested_by=None,
                     operation_id=None):
    """Return an unsigned report; execute requires a durable audit callback.

    Injected backends are for offline tests. Snapshot objects and runtime health
    are deliberately not certified here; they require separate verification.
    """
    report = {"schema": "szl.a11oy-handover-operator/v1", "status": "HOLD",
              "signature": "UNSIGNED", "execute": execute,
              "object_preservation": "NOT_VERIFIED", "runtime_health": "NOT_VERIFIED",
              "publication_authorized": False, "request_submission": "NOT_ATTEMPTED"}
    try:
        if any(not isinstance(value, str) or not re.fullmatch(
                r"[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*", value)
               for value in (dataset, bucket)):
            raise Hold("TARGET_IDENTITY_INVALID")
        if getattr(backend, "repo_id", dataset) != dataset:
            raise Hold("TARGET_DATASET_MISMATCH")
        report["target"] = {"dataset": dataset, "bucket": bucket}
        if (type(timeout) not in (int, float) or not math.isfinite(timeout) or not 1 <= timeout <= 900
                or type(poll) not in (int, float) or not math.isfinite(poll) or not 0 < poll <= 10):
            raise Hold("WAIT_BOUND_INVALID")
        observed, head = expected_head(backend, expected, bucket)
        beat = fresh_heartbeat(objects, head, clock)
        report.update(expected=dict(expected), heartbeat=beat, required_stores=sorted(head["snapshots"]))
        if not execute:
            report.update(status="PREFLIGHT_VERIFIED", reason="NO_PROVIDER_WRITE")
            return report
        if record is None:
            raise Hold("DURABLE_RECEIPT_REQUIRED")
        request = make_request(observed, head, requested_by or uuid.uuid4().hex,
                               operation_id or uuid.uuid4().hex, clock())
        report["request"] = {"operation_id": request["operation_id"],
                             "requested_by": request["handover"]["requested_by"],
                             "requested_at": request["handover"]["requested_at"],
                             "sha256": digest(ss.canonical(request)), "sequence": request["sequence"]}
        record(dict(report, event="REQUEST_INTENT"))
        report["request_submission"] = "OUTCOME_UNKNOWN"
        guarded = FreshSubmitBackend(backend, objects, head, clock)
        try:
            acknowledged = ss.cas_advance(guarded, observed, request)
        except ss.HeadChanged as changed:
            # A release can follow an uncertain request before its resolution
            # read. Only its exact predecessor proves this request was accepted.
            if released_head(changed.observed, request) is None:
                raise Hold("REQUEST_OUTCOME_UNRESOLVED")
            acknowledged = changed.observed
        report["request_submission"] = "ACCEPTED"
        record(dict(report, event="REQUEST_ACCEPTED"))
        report["release"] = wait_release(backend, request, observed=acknowledged, timeout=timeout,
                                          poll=poll, monotonic=monotonic, sleep=sleep)
        report.update(status="RELEASE_OBSERVED", reason="OBJECT_AND_RUNTIME_VERIFICATION_REQUIRED")
        record(dict(report, event="RELEASE_OBSERVED"))
        return report
    except Exception as error:
        # Provider messages may contain credentials or request URLs; never emit
        # them. Only locally defined Hold codes and storage codes are exposed.
        code = str(error) if isinstance(error, Hold) else getattr(error, "code", "OPERATOR_ERROR")
        if not isinstance(code, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]{2,79}", code):
            code = "OPERATOR_ERROR"
        report.update(status="HOLD", reason=code)
        if execute and record is not None:
            try:
                record(dict(report, event="HOLD"))
            except Exception:
                report["receipt_error"] = "AUDIT_WRITE_FAILED"
        return report


class ReceiptLog:
    """Exclusive local JSONL, hash chained and fsynced; explicitly unsigned."""

    def __init__(self, stream):
        self.stream, self.sequence, self.previous = stream, 0, None

    def __call__(self, payload):
        body = {"sequence": self.sequence + 1, "previous_sha256": self.previous,
                "signature": "UNSIGNED", "payload": payload}
        raw = ss.canonical(body)
        self.stream.write(raw.decode("utf-8"))
        self.stream.flush()
        os.fsync(self.stream.fileno())
        self.sequence += 1
        self.previous = digest(raw)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--observe-receipt", type=Path, help="Read-only recovery; never reissues a request")
    parser.add_argument("--dataset", default=ss.DEFAULT_DATASET)
    parser.add_argument("--bucket", default=ss.DEFAULT_BUCKET)
    parser.add_argument("--expected-head-commit", required=True)
    parser.add_argument("--expected-head-sha256", required=True)
    parser.add_argument("--expected-writer-id", required=True)
    parser.add_argument("--expected-boot-id", required=True)
    parser.add_argument("--expected-epoch", required=True, type=int)
    parser.add_argument("--receipt", type=Path, help="New JSONL file, required with --execute; never overwritten")
    parser.add_argument("--timeout", type=float, default=180)
    args = parser.parse_args(argv)
    if args.observe_receipt is not None and (args.execute or args.receipt is not None):
        parser.error("--observe-receipt cannot execute or write a receipt")
    if args.execute and args.receipt is None:
        parser.error("--execute requires a new --receipt path")
    if not args.execute and args.receipt is not None:
        parser.error("read-only preflight reports to stdout; --receipt is for --execute")
    if any(not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*", value)
           for value in (args.dataset, args.bucket)):
        parser.error("dataset and bucket must be explicit owner/name identifiers")
    expected = {"commit": args.expected_head_commit, "sha256": args.expected_head_sha256,
                "writer_id": args.expected_writer_id, "boot_id": args.expected_boot_id,
                "epoch": args.expected_epoch}
    stream = None
    try:
        from huggingface_hub import HfApi
        api = HfApi()  # Uses the caller's configured Hub authentication; never prints it.
        if args.execute:
            stream = args.receipt.open("x", encoding="utf-8", newline="\n")
        with tempfile.TemporaryDirectory(prefix="a11oy-handover-readback-") as scratch:
            backend = ss.HFDatasetHeadBackend(api, args.dataset, Path(scratch))
            if args.observe_receipt is not None:
                report = observe_receipt(backend, args.observe_receipt, expected=expected,
                                         bucket=args.bucket, dataset=args.dataset, timeout=args.timeout)
            else:
                objects = ss.HFBucketObjectStore(api, args.bucket, Path(scratch))
                report = request_handover(backend, objects, expected=expected, bucket=args.bucket,
                                          dataset=args.dataset,
                                          execute=args.execute, record=ReceiptLog(stream) if stream else None,
                                          timeout=args.timeout)
    except Exception:
        report = {"schema": "szl.a11oy-handover-operator/v1", "status": "HOLD",
                  "reason": "OPERATOR_SETUP_FAILED", "signature": "UNSIGNED",
                  "object_preservation": "NOT_VERIFIED", "publication_authorized": False}
    finally:
        if stream is not None:
            stream.close()
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0 if report["status"] in ("PREFLIGHT_VERIFIED", "RELEASE_OBSERVED") else 2


if __name__ == "__main__":
    raise SystemExit(main())
