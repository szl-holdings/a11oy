#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Services: inspect a fixed captured candidate, never invoke a provider writer."""

import argparse
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
if __package__ in (None, ""):
    sys.path.insert(0, str(ROOT))

SCHEMA = "szl.gdw-artifact-readonly-triage/v1"
REPOSITORY = "szl-holdings/a11oy"
WORKFLOW = ".github/workflows/gdw-artifact-readonly-triage.yml"
MAX_SECONDS = 240
HEX40 = re.compile(r"[0-9a-f]{40}\Z")


class TriageHeld(RuntimeError):
    pass


READ_BOUNDARIES = frozenset(('CONTEXT', 'CHECKOUT', 'NATIVE_AUTHORITY', 'PRIVATE_OUTPUT', 'SDK_IMPORT', 'TRUSTED_ROOTS', 'REFERENCE_READ', 'HEAD_BEFORE', 'CAPTURE_QUALIFICATION', 'LOCAL_ARTIFACTS', 'HEAD_AFTER', 'COMPLETE'))


def mark_boundary(record, boundary):
    if type(boundary) is not str or boundary not in READ_BOUNDARIES:
        raise TriageHeld("READ_ONLY_TRIAGE_HELD")
    record["read_boundary"] = boundary


class _PublicationNotAttempted(BaseException):
    """Observation-only sentinel: never returns a fabricated publication receipt."""


def require(condition):
    if not condition:
        raise TriageHeld("READ_ONLY_TRIAGE_HELD")


def local_artifact_observation(database, directory, deadline, *, logical_roots=None):
    from gdw_durable_artifacts import ArtifactCache, ARTIFACT_FAILURE_CODES
    from gdw_durable_runtime import DurableStorageUnavailable

    reached = False
    def stop_before_publication(_path, _object_path, _digest, _deadline):
        nonlocal reached
        reached = True
        raise _PublicationNotAttempted()

    before = _file_digest(database, deadline)
    result = {"state": "HELD", "diagnostic_code": "LOCAL_VALIDATION_UNAVAILABLE",
              "publication_callback_reached": False, "candidate_unchanged": False}
    try:
        directory.mkdir(mode=0o700, exist_ok=False)
        cache = ArtifactCache(directory, stop_before_publication, logical_roots=logical_roots)
        report = cache.prepare(database, deadline)
        require(report.get("verified_count") == 0 and not reached)
        result.update(state="OBSERVED", diagnostic_code="NO_RETAINED_ARTIFACTS")
    except _PublicationNotAttempted:
        result.update(state="OBSERVED", diagnostic_code="LOCAL_ROWS_VALIDATED_PUBLICATION_NOT_ATTEMPTED")
    except DurableStorageUnavailable as error:
        args = BaseException.args.__get__(error)
        if type(args) is tuple and len(args) == 1 and type(args[0]) is str and args[0] in ARTIFACT_FAILURE_CODES:
            result["diagnostic_code"] = args[0]
    except Exception:
        pass
    result["publication_callback_reached"] = reached
    result["candidate_unchanged"] = _file_digest(database, deadline) == before
    require(result["candidate_unchanged"])
    return result


def _file_digest(path, deadline):
    import stat
    digest = hashlib.sha256()
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        metadata = os.fstat(stream.fileno())
        require(stat.S_ISREG(metadata.st_mode) and metadata.st_nlink == 1 and metadata.st_size <= 256 * 1024 * 1024)
        total = 0
        while block := stream.read(1024 * 1024):
            require(time.monotonic() < deadline)
            total += len(block)
            require(total <= 256 * 1024 * 1024)
            digest.update(block)
        require(total == metadata.st_size)
    return digest.hexdigest()


def native_context(env, source):
    require(type(source) is str and HEX40.fullmatch(source) is not None)
    require(env.get("GITHUB_ACTIONS") == "true" and env.get("GITHUB_REPOSITORY") == REPOSITORY
        and env.get("GITHUB_REF") == "refs/heads/main" and env.get("GITHUB_EVENT_NAME") == "workflow_dispatch"
        and env.get("GITHUB_RUN_ATTEMPT") == "1" and env.get("GITHUB_JOB") == "triage"
        and env.get("GITHUB_SHA") == source and env.get("GITHUB_WORKFLOW_SHA") == source
        and env.get("GITHUB_WORKFLOW_REF") == f"{REPOSITORY}/{WORKFLOW}@refs/heads/main"
        and re.fullmatch(r"[1-9][0-9]*", env.get("GITHUB_RUN_ID", "")) is not None)
    return {"source_revision": source, "run_id": int(env["GITHUB_RUN_ID"]), "run_attempt": 1}


def github_json(session, suffix):
    # This function only reads the fixed repository; redirects are not followed.
    response = session.get(f"https://api.github.com/repos/{REPOSITORY}/" + suffix,
                           timeout=10, allow_redirects=False)
    try:
        require(response.status_code == 200 and len(response.content) <= 256 * 1024)
        value = json.loads(response.content)
        require(type(value) is dict)
        return value
    finally:
        response.close()


def verify_native(session, context):
    source = context["source_revision"]
    require(github_json(session, "git/ref/heads/main").get("object", {}).get("sha") == source)
    commit = github_json(session, "git/commits/" + source)
    require(commit.get("sha") == source and commit.get("verification", {}).get("verified") is True
            and commit.get("verification", {}).get("reason") == "valid")
    run = github_json(session, "actions/runs/" + str(context["run_id"]))
    require(run.get("id") == context["run_id"] and run.get("head_sha") == source
        and run.get("run_attempt") == 1 and run.get("head_branch") == "main"
        and run.get("event") == "workflow_dispatch" and run.get("path") == WORKFLOW
        and run.get("status") == "in_progress" and run.get("conclusion") is None)


def private_head_metadata(api):
    import gdw_durable_storage as storage
    meta = api.dataset_info(storage.DATASET, revision="main", expand=["sha", "private"])
    revision = storage._value(meta, "sha")
    require(storage._value(meta, "id") == storage.DATASET and storage._value(meta, "private") is True
            and type(revision) is str and HEX40.fullmatch(revision) is not None)
    items = api.get_paths_info(repo_id=storage.DATASET, paths=[storage.HEAD_PATH],
                              repo_type="dataset", revision=revision)
    require(type(items) is list and len(items) <= 1)
    if items:
        require(storage._value(items[0], "path") == storage.HEAD_PATH)
    return {"revision": revision, "head_presence": "PRESENT" if items else "ABSENT"}


def observe_capture(api, workspace, require_source, deadline, *, note=lambda _boundary: None):
    note("REFERENCE_READ")
    from scripts import qualify_gdw_store_recovery as recovery
    from scripts import acquire_gdw_durable_storage as acquisition
    reference_bytes = acquisition._read(ROOT / acquisition.CAPTURE_REFERENCE)
    anchor_bytes = acquisition._read(ROOT / acquisition.HISTORICAL_REFERENCE)
    reference, anchors = recovery._json(reference_bytes), recovery._json(anchor_bytes)
    capture_hash = hashlib.sha256(reference_bytes).hexdigest()
    recovery.validate_historical_anchors(anchors, reference, capture_hash)
    require_source()
    note("HEAD_BEFORE")
    before = private_head_metadata(api)
    note("CAPTURE_QUALIFICATION")
    qualified = recovery.qualify_capture(recovery.ReadOnlyCaptureHub(api), reference,
        workspace / "capture", require_source, deadline, historical_anchors=anchors,
        capture_report_sha256=capture_hash)
    require(qualified.get("state") == "LOGICAL_CONTINUITY_VERIFIED"
        and qualified.get("provider_writes_performed") is False and qualified.get("originals_mutated") is False
        and qualified.get("restore_admitted") is False and qualified.get("deployment_admitted") is False)
    note("LOCAL_ARTIFACTS")
    observation = local_artifact_observation(workspace / "capture/working/gdw/candidate.sqlite3",
                                             workspace / "local-artifacts", deadline)
    require_source()
    note("HEAD_AFTER")
    after = private_head_metadata(api)
    require(before == after)
    return {"capture_qualification": "LOGICAL_CONTINUITY_VERIFIED",
            "private_head_metadata": after, "metadata_stable_during_read": True,
            "local_artifact_observation": observation}


def trusted_artifact_environment():
    from gdw_durable_artifacts import LOGICAL_ROOTS
    return {"GDW_PROOF_DIR": str(LOGICAL_ROOTS["proof_export"]),
            "GDW_RECEIPT_PROJECTION_DIR": str(LOGICAL_ROOTS["receipt_projection"])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = {"schema": SCHEMA, "state": "HELD", "diagnostic_code": "READ_ONLY_TRIAGE_HELD",
              "provider_writes_performed": False, "restore_admitted": False,
              "deployment_admitted": False, "retry_admitted": False,
              "prior_provider_effects": "NOT_ESTABLISHED", "private_bytes_reported": False,
              "read_boundary": "CONTEXT"}
    output = Path(args.output)
    old_mask = os.umask(0o077)
    try:
        context = native_context(os.environ, args.source_sha)
        require(output == Path(os.environ.get("RUNNER_TEMP", "")) / "gdw-artifact-triage.json")
        require(bool(os.environ.get("HF_TOKEN")) and bool(os.environ.get("GH_TOKEN")))
        mark_boundary(result, "CHECKOUT")
        checkout = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                                  capture_output=True, text=True, timeout=10, check=True)
        require(checkout.stdout.strip() == args.source_sha)
        result.update(context)
        signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TriageHeld("READ_ONLY_TRIAGE_HELD")))
        signal.alarm(MAX_SECONDS)
        import requests
        from scripts import qualify_gdw_store_recovery as recovery
        with requests.Session() as session:
            session.headers.update(Authorization="Bearer " + os.environ["GH_TOKEN"], Accept="application/vnd.github+json")
            mark_boundary(result, "NATIVE_AUTHORITY")
            verify_native(session, context)
            def owned():
                require(github_json(session, "git/ref/heads/main").get("object", {}).get("sha") == args.source_sha)
            mark_boundary(result, "PRIVATE_OUTPUT")
            with recovery.preservation._private_output(), tempfile.TemporaryDirectory(prefix="gdw-readonly-triage-") as directory:
                logging.disable(logging.CRITICAL)
                os.environ.update(HF_HUB_VERBOSITY="error", HF_DEBUG="0", HF_HUB_DISABLE_PROGRESS_BARS="1",
                                  HF_HOME=str(Path(directory) / "hub-cache"))
                mark_boundary(result, "SDK_IMPORT")
                import huggingface_hub
                from huggingface_hub import HfApi
                require(huggingface_hub.__version__ == "1.31.0")
                api = HfApi(endpoint="https://huggingface.co", token=os.environ["HF_TOKEN"])
                # Match the admitted worker roots; never inherit a caller override.
                mark_boundary(result, "TRUSTED_ROOTS")
                os.environ.update(trusted_artifact_environment())
                observation = observe_capture(api, Path(directory), owned, time.monotonic() + MAX_SECONDS - 10,
                                              note=lambda boundary: mark_boundary(result, boundary))
                result.update(observation)
            mark_boundary(result, "COMPLETE")
            result.update(state="OBSERVED", diagnostic_code="READ_ONLY_OBSERVATION_COMPLETE")
    except BaseException:
        # Never expose a provider/SQLite exception message or private report body.
        result.update(state="HELD", diagnostic_code="READ_ONLY_TRIAGE_HELD")
    finally:
        signal.alarm(0)
        os.umask(old_mask)
    encoded = json.dumps(result, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
    require(len(encoded) < 4096)
    # A fixed output file is the only uploaded artifact; no temporary captures.
    if output == Path(os.environ.get("RUNNER_TEMP", "")) / "gdw-artifact-triage.json":
        with output.open("x", encoding="utf-8") as stream:
            stream.write(encoded)
    print(encoded, end="")
    return 0 if result["state"] == "OBSERVED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
