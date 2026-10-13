#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Read-only qualification of this manual run's stopped private capture.

Only a bounded allowlist leaves the private runner. Qualification does not
admit restoration, acquisition, configuration, a restart, or deployment.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import signal
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import classify_hf_private_store_preservation as classifier
import qualify_gdw_store_recovery as recovery

p = recovery.preservation
SCHEMA = "szl.gdw-current-capture-qualification-public/v1"
HEAD_PATH = "a11oy/durable-store/v1/head.json"
WORKFLOW_REF = "szl-holdings/a11oy/.github/workflows/hf-preserve-current-stores.yml@refs/heads/main"
MAX_CAPTURE_AGE_SECONDS = 900
ROOT = Path(__file__).resolve().parents[1]


class CurrentReadOnlyHub(recovery.ReadOnlyCaptureHub):
    """No provider mutation methods or runtime constructors are exposed."""

    def space_info(self, **kwargs: Any) -> Any:
        return self._api.space_info(**kwargs)

    def get_space_runtime(self, **kwargs: Any) -> Any:
        return self._api.get_space_runtime(**kwargs)

    def get_paths_info(self, **kwargs: Any) -> Any:
        return self._api.get_paths_info(**kwargs)

    def hf_hub_download(self, **kwargs: Any) -> Any:
        return self._api.hf_hub_download(**kwargs)


def _timestamp(value: Any) -> datetime:
    if not isinstance(value, str):
        raise recovery.RecoveryError("CURRENT_CAPTURE_TIME_INVALID")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if result.tzinfo is None or result.utcoffset().total_seconds() != 0:
            raise ValueError()
        return result
    except (ValueError, AttributeError):
        raise recovery.RecoveryError("CURRENT_CAPTURE_TIME_INVALID") from None


def validate_current_reference(reference: dict, source: str, run_id: str,
                               run_attempt: str, now: datetime) -> str:
    _, valid = classifier.classify(reference, exit_code=2, expected_sha=source,
                                    run_id=run_id, run_attempt=run_attempt)
    if not valid or run_attempt != "1":
        raise recovery.RecoveryError("CURRENT_CAPTURE_BINDING_INVALID")
    started, completed = (_timestamp(reference.get(key)) for key in ("generated_at", "completed_at"))
    if not 0 <= (now - started).total_seconds() <= MAX_CAPTURE_AGE_SECONDS \
            or not started <= completed <= now:
        raise recovery.RecoveryError("CURRENT_CAPTURE_STALE")
    revisions = set()
    previous = started
    for observation in reference["observations"]:
        observed = _timestamp(observation.get("observed_at"))
        revision = observation.get("hf_revision")
        if (not recovery._digest(revision, 40) or observation.get("bucket_private") is not True
                or observation.get("mount_path") != "/data" or observation.get("mount_type") != "bucket"
                or not previous <= observed <= completed):
            raise recovery.RecoveryError("CURRENT_CAPTURE_OBSERVATION_INVALID")
        revisions.add(revision)
        previous = observed
    if len(revisions) != 1:
        raise recovery.RecoveryError("CURRENT_CAPTURE_REVISION_CHANGED")
    return revisions.pop()


def observe_private_head(api: CurrentReadOnlyHub, directory: Path, deadline: float) -> dict:
    recovery.check_budget(deadline)
    info = p._call(api.dataset_info, repo_id=p.BUCKET, revision="main", expand=["sha", "private"])
    revision = p._value(info, "sha")
    if p._value(info, "id") != p.BUCKET or p._value(info, "private") is not True \
            or not recovery._digest(revision, 40):
        raise recovery.RecoveryError("PRIVATE_HEAD_IDENTITY_UNAVAILABLE")
    rows = p._call(api.get_paths_info, repo_id=p.BUCKET, paths=[HEAD_PATH],
                   repo_type="dataset", revision=revision)
    recovery.check_budget(deadline)
    if type(rows) is not list or len(rows) > 1:
        raise recovery.RecoveryError("PRIVATE_HEAD_IDENTITY_UNAVAILABLE")
    if not rows:
        return {"revision": revision, "present": False}
    row = rows[0]
    size, blob = p._value(row, "size"), p._value(row, "blob_id")
    if (p._value(row, "path") != HEAD_PATH or type(size) is not int
            or not 1 <= size <= recovery.MAX_REFERENCE_BYTES or not recovery._digest(blob, 40)
            or p._value(row, "lfs") is not None):
        raise recovery.RecoveryError("PRIVATE_HEAD_IDENTITY_UNAVAILABLE")
    directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    expected = directory / HEAD_PATH
    result = p._call(api.hf_hub_download, repo_id=p.BUCKET, filename=HEAD_PATH,
                     repo_type="dataset", revision=revision, local_dir=directory,
                     cache_dir=directory / "cache")
    if type(result) is not str or Path(result) != expected:
        raise recovery.RecoveryError("PRIVATE_HEAD_READBACK_INVALID")
    data = recovery._bounded_file(expected, recovery.MAX_REFERENCE_BYTES, "PRIVATE_HEAD")
    if len(data) != size or hashlib.sha1(b"blob " + str(size).encode() + b"\0" + data).hexdigest() != blob \
            or type(recovery._json(data)) is not dict:
        raise recovery.RecoveryError("PRIVATE_HEAD_READBACK_INVALID")
    recovery.check_budget(deadline)
    return {"revision": revision, "present": True, "sha256": hashlib.sha256(data).hexdigest()}


def qualify_current_capture(api: CurrentReadOnlyHub, reference: dict, anchors: dict,
                            historical_reference: dict, historical_digest: str, workspace: Path,
                            ownership: Callable[[], None], deadline: float, *,
                            source: str, run_id: str, run_attempt: str,
                            now: datetime | None = None) -> dict:
    public = {"schema": SCHEMA, "state": "BLOCKED", "qualification_state": "NOT_VERIFIED",
              "diagnostic_code": "CURRENT_CAPTURE_NOT_QUALIFIED", "deployment_admitted": False,
              "restore_admitted": False, "provider_writes_performed": False,
              "originals_mutated": False, "private_bytes_in_public_artifacts": False,
              "later_acknowledged_writes_verified": False}
    try:
        recovery.check_budget(deadline)
        revision = validate_current_reference(reference, source, run_id, run_attempt,
                                                now or datetime.now(timezone.utc))
        recovery.validate_current_historical_anchors(anchors, reference, historical_reference, historical_digest)
        public.update(source_revision=source, run_id=run_id, run_attempt=run_attempt)
        ownership()
        before = p.observe_stopped(api)
        if before["hf_revision"] != revision:
            raise recovery.RecoveryError("CURRENT_CAPTURE_REVISION_CHANGED")
        _, original_identities = p.paths_info(api, p.SOURCE_PATHS)
        recorded = {row["source_path"]: {key: row[key] for key in original_identities[row["source_path"]]}
                    for row in reference["files"] if row.get("present") and row.get("source_path") in original_identities}
        if original_identities != recorded or set(original_identities) != {
                row["source_path"] for row in reference["files"] if row.get("present")}:
            raise recovery.RecoveryError("CURRENT_ORIGINAL_IDENTITIES_CHANGED")
        head_before = observe_private_head(api, workspace / "head-before", deadline)
        report = recovery.qualify_capture(api, reference, workspace / "qualification", ownership, deadline,
                                           historical_anchors=anchors, historical_reference=historical_reference,
                                           capture_report_sha256=historical_digest)
        if (report.get("state") != "LOGICAL_CONTINUITY_VERIFIED"
                or report.get("historical_anchor_state") != "VERIFIED"
                or report.get("captured_historical_anchor_state") != "VERIFIED"):
            raise recovery.RecoveryError("CURRENT_CAPTURE_NOT_QUALIFIED")
        after = p.observe_stopped(api)
        if after["hf_revision"] != revision:
            raise recovery.RecoveryError("CURRENT_CAPTURE_REVISION_CHANGED")
        _, original_after = p.paths_info(api, p.SOURCE_PATHS)
        if original_after != original_identities:
            raise recovery.RecoveryError("CURRENT_ORIGINAL_IDENTITIES_CHANGED")
        head_after = observe_private_head(api, workspace / "head-after", deadline)
        if head_after != head_before:
            raise recovery.RecoveryError("PRIVATE_HEAD_CHANGED")
        ownership()
        recovery.check_budget(deadline)
        public.update(qualification_state="LOGICAL_CONTINUITY_VERIFIED",
                      diagnostic_code="RESTORE_CONTRACT_REQUIRED", historical_anchor_state="VERIFIED",
                      private_manifest_sha256=reference["private_manifest"]["sha256"],
                      private_head_observation_sha256=hashlib.sha256(p._json_bytes(head_before)).hexdigest(),
                      historical_capture_report_sha256=historical_digest,
                      stopped_hf_revision=revision)
    except (recovery.RecoveryError, p.PreservationError):
        # Provider diagnostics, generations, receipt contents and private paths
        # never enter this public result, even on malformed input or exceptions.
        pass
    except Exception:
        pass
    return public


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    public = {"schema": SCHEMA, "state": "BLOCKED", "qualification_state": "NOT_VERIFIED",
              "diagnostic_code": "CURRENT_CAPTURE_CONTEXT_INVALID", "deployment_admitted": False,
              "restore_admitted": False, "provider_writes_performed": False}
    previous_alarm = None
    try:
        source = os.environ.get("GITHUB_SHA", "")
        if (os.environ.get("GITHUB_ACTIONS") != "true"
                or os.environ.get("GITHUB_REPOSITORY") != "szl-holdings/a11oy"
                or os.environ.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
                or os.environ.get("GITHUB_REF") != "refs/heads/main"
                or os.environ.get("GITHUB_WORKFLOW_REF") != WORKFLOW_REF
                or os.environ.get("GITHUB_WORKFLOW_SHA") != source
                or os.environ.get("GITHUB_JOB") != "preserve"
                or os.environ.get("GITHUB_RUN_ATTEMPT") != "1"
                or os.environ.get("EXPECTED_SOURCE_SHA") != source or not recovery._digest(source, 40)
                or not os.environ.get("HF_TOKEN") or not os.environ.get("GH_TOKEN")):
            raise recovery.RecoveryError("CURRENT_CAPTURE_CONTEXT_INVALID")
        reference = recovery.read_reference(args.capture_report)
        anchors = recovery.read_reference(ROOT / "docs/operations/evidence/gdw-recovery-historical-anchors.json")
        historical, raw = recovery.read_reference_bytes(ROOT / "docs/operations/evidence/gdw-capture-37223162231.json")

        def ownership() -> None:
            p._require_supervised_main(source, os.environ["GH_TOKEN"])

        def timeout_handler(_signal: int, _frame: Any) -> None:
            raise recovery.RecoveryError("QUALIFICATION_DEADLINE_EXHAUSTED")

        previous_alarm = signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(recovery.DEADLINE_SECONDS)
        deadline = time.monotonic() + recovery.DEADLINE_SECONDS
        os.umask(0o077)
        logging.disable(logging.CRITICAL)
        os.environ.pop("HF_DEBUG", None)
        os.environ.update(HF_HUB_DISABLE_PROGRESS_BARS="1", HF_HUB_DISABLE_TELEMETRY="1",
                          HF_HUB_DISABLE_IMPLICIT_TOKEN="1")
        with tempfile.TemporaryDirectory(prefix="szl-current-qualification-") as temporary:
            for key, path in (("HF_HOME", "cache"), ("HF_HUB_CACHE", "cache/hub"), ("HF_XET_CACHE", "cache/xet")):
                os.environ[key] = str(Path(temporary) / path)
            with p._private_output():
                import huggingface_hub
                from huggingface_hub.utils import set_client_factory
                if huggingface_hub.__version__ != p.SDK_VERSION:
                    raise recovery.RecoveryError("SDK_VERSION_MISMATCH")
                set_client_factory(p.hub_http_client)
                api = CurrentReadOnlyHub(huggingface_hub.HfApi(endpoint=p.ENDPOINT, token=os.environ["HF_TOKEN"]))
                public = qualify_current_capture(api, reference, anchors, historical,
                    hashlib.sha256(raw).hexdigest(), Path(temporary), ownership, deadline,
                    source=source, run_id=os.environ.get("GITHUB_RUN_ID", ""), run_attempt="1")
    except Exception:
        public["qualification_state"] = "NOT_VERIFIED"
        public["diagnostic_code"] = "CURRENT_CAPTURE_NOT_QUALIFIED"
    finally:
        if previous_alarm is not None:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, previous_alarm)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(p._json_bytes(public))
    print(json.dumps(public, sort_keys=True))
    return 0 if public["qualification_state"] == "LOGICAL_CONTINUITY_VERIFIED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
