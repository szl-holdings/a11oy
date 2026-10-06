#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Services: inspect a fixed captured candidate, never invoke a provider writer."""

import argparse
import hashlib
import json
import logging
import math
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
# Isolated Python removes the script directory; qualification uses these
# source-owned sibling imports in both direct and package entry modes.
for _trusted_path in (ROOT / "scripts", ROOT):
    if str(_trusted_path) not in sys.path:
        sys.path.insert(0, str(_trusted_path))

SCHEMA = "szl.gdw-artifact-readonly-triage/v2"
REPOSITORY = "szl-holdings/a11oy"
WORKFLOW = ".github/workflows/gdw-artifact-readonly-triage.yml"
MAX_SECONDS = 240
MAX_EXPECTED_OBJECTS = 4096
OBJECT_WORKER_SCHEMA = "szl.gdw-artifact-object-worker/v1"
OBJECT_WORKER_BYTES = 4096
OBJECT_WORKER_SECONDS = 210
POST_READBACK_SECONDS = 15
HEX40 = re.compile(r"[0-9a-f]{40}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")

PRIOR_SOURCE = "62ca4d1506fe95f8bedf2143f5f8b60c786dcd74"
PRIOR_RUN = 37263869028
PRIOR_ATTEMPT = 1
PRIOR_JOB = 111616768413
PRIOR_ARTIFACT = 11325467455
PRIOR_ARTIFACT_BYTES = 389
PRIOR_ARTIFACT_SHA256 = "d290fa69bf530ec3cc27daccfd0daef13904064c2f3a75f73fe2bc71c2515afd"
PRIOR_REPORT_SHA256 = "f4e638d0b73f865add47e16c7de5bdfff9f9ce8b6b505ee4e6debf1098db35a2"


class TriageHeld(RuntimeError):
    pass


READ_BOUNDARIES = frozenset((
    'CONTEXT', 'CHECKOUT', 'NATIVE_AUTHORITY', 'PRIOR_ATTEMPT',
    'PRIVATE_OUTPUT', 'SDK_IMPORT', 'TRUSTED_ROOTS', 'REFERENCE_READ',
    'HEAD_BEFORE', 'CAPTURE_QUALIFICATION', 'LOCAL_ARTIFACTS',
    'OBJECT_PLAN', 'OBJECT_READBACK', 'HEAD_AFTER', 'COMPLETE',
))


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


def _aggregate(rows):
    encoded = json.dumps(rows, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(encoded).hexdigest()


def local_artifact_plan(database, directory, deadline, *, logical_roots=None):
    """Return a private exact-path plan only after validating every retained row."""
    from gdw_durable_artifacts import ArtifactCache, OBJECT_PREFIX, MAX_ARTIFACT_BYTES

    def publication_forbidden(*_args):
        raise AssertionError("provider publication is forbidden during reconciliation")

    before = _file_digest(database, deadline)
    directory.mkdir(mode=0o700, exist_ok=False)
    cache = ArtifactCache(directory, publication_forbidden, logical_roots=logical_roots)
    pending, validation = cache._validated_objects(database, deadline)
    require(0 < len(pending) <= MAX_EXPECTED_OBJECTS
        and validation.get("verified_count") == 0
        and validation.get("reconstructed_count") == len(pending)
        and validation.get("reconstruction") == "RECONSTRUCTED_FROM_RETAINED_PAYLOAD")
    rows = []
    for object_path, (physical_path, digest, size) in sorted(pending.items()):
        require(type(object_path) is str
            and re.fullmatch(re.escape(OBJECT_PREFIX) + r"/[0-9a-f]{64}/[0-9a-f]{64}\.json", object_path)
            and HEX64.fullmatch(digest) is not None
            and type(size) is int and 0 < size <= MAX_ARTIFACT_BYTES
            and physical_path.is_file() and physical_path.stat().st_size == size
            and _file_digest(physical_path, deadline) == digest)
        rows.append({"path": object_path, "sha256": digest, "size": size})
    require(_file_digest(database, deadline) == before)
    return pending, {
        "expected_object_count": len(rows),
        "expected_object_set_sha256": _aggregate(rows),
        "candidate_unchanged": True,
        "all_retained_rows_validated": True,
    }


class ReadOnlyArtifactHub:
    """Exact admitted artifact reads; deliberately exposes no provider mutation."""

    def __init__(self, api, admitted_objects, directory, require_source, deadline):
        from gdw_durable_artifacts import OBJECT_PREFIX, MAX_ARTIFACT_BYTES
        import gdw_durable_storage as storage
        require(storage._value(api, "endpoint") == storage.ENDPOINT
            and type(admitted_objects) is dict
            and 0 < len(admitted_objects) <= MAX_EXPECTED_OBJECTS)
        for path, identity in admitted_objects.items():
            require(type(path) is str
                and re.fullmatch(re.escape(OBJECT_PREFIX) + r"/[0-9a-f]{64}/[0-9a-f]{64}\.json", path)
                and type(identity) is tuple and len(identity) == 2
                and type(identity[0]) is str and HEX64.fullmatch(identity[0]) is not None
                and type(identity[1]) is int and 0 < identity[1] <= MAX_ARTIFACT_BYTES)
        self._api = api
        self._objects = dict(admitted_objects)
        self._directory = storage._private_directory(directory)
        self._require_source = require_source
        self._deadline = deadline

    def _before(self):
        require(time.monotonic() < self._deadline)
        self._require_source()
        require(time.monotonic() < self._deadline)

    def metadata(self):
        import gdw_durable_storage as storage
        self._before()
        info = self._api.bucket_info(bucket_id=storage.BUCKET)
        require(storage._value(info, "id") == storage.BUCKET
            and storage._value(info, "private") is True)
        return {"id": storage.BUCKET, "private": True}

    def observe(self, path):
        import gdw_durable_storage as storage
        require(type(path) is str and path in self._objects)
        self._before()
        found = []
        for item in self._api.get_bucket_paths_info(bucket_id=storage.BUCKET, paths=[path]):
            require(not found and storage._value(item, "path") == path
                and storage._value(item, "type") == "file"
                and type(storage._value(item, "size")) is int
                and 0 < storage._value(item, "size") <= 8 * 1024 * 1024
                and storage._digest(storage._value(item, "xet_hash")))
            found.append(item)
        require(time.monotonic() < self._deadline)
        return found[0] if found else None

    @staticmethod
    def identity(item):
        import gdw_durable_storage as storage
        return (storage._value(item, "path"), storage._value(item, "size"),
                storage._value(item, "xet_hash"))

    def download(self, observed, target):
        import gdw_durable_storage as storage
        path, observed_size, xet_hash = self.identity(observed)
        expected = self._objects.get(path)
        require(expected is not None and observed_size == expected[1]
            and storage._digest(xet_hash)
            and target.parent == self._directory and not os.path.lexists(target))
        self._before()
        self._api.download_bucket_files(bucket_id=storage.BUCKET, files=[(observed, target)],
                                        raise_on_missing_files=True)
        require(target.is_file() and target.stat().st_size == expected[1]
            and _file_digest(target, self._deadline) == expected[0])
        current = self.observe(path)
        require(current is not None and self.identity(current) == self.identity(observed))
        return xet_hash


def artifact_effect_observation(api, database, directory, require_source, deadline, *, logical_roots=None,
                                note=lambda _boundary: None):
    """Observe only the exact current retained-object set and return closed counts."""
    before = _file_digest(database, deadline)
    directory.mkdir(mode=0o700, exist_ok=False)
    pending, plan = local_artifact_plan(database, directory / "plan", deadline,
                                        logical_roots=logical_roots)
    note("OBJECT_READBACK")
    readbacks = directory / "readbacks"
    readbacks.mkdir(mode=0o700, exist_ok=False)
    admitted_objects = {path: (digest, size)
                        for path, (_physical_path, digest, size) in pending.items()}
    reader = ReadOnlyArtifactHub(api, admitted_objects, readbacks, require_source, deadline)
    require(reader.metadata() == {"id": "SZLHOLDINGS/szl-evidence", "private": True})
    observed_objects = []
    initial_identities = {}
    missing = 0
    for object_path, (_physical_path, digest, size) in sorted(pending.items()):
        observed = reader.observe(object_path)
        if observed is None:
            missing += 1
            initial_identities[object_path] = None
            continue
        import gdw_durable_storage as storage
        require(storage._value(observed, "size") == size)
        initial_identities[object_path] = reader.identity(observed)
        observed_objects.append((object_path, digest, size, observed))
    present = []
    for index, (object_path, digest, size, observed) in enumerate(observed_objects):
        xet_hash = reader.download(observed, readbacks / f"object-{index}.json")
        present.append({"path": object_path, "sha256": digest, "size": size, "xet_hash": xet_hash})
    for object_path in sorted(pending):
        current = reader.observe(object_path)
        require((None if current is None else reader.identity(current)) == initial_identities[object_path])
    require(reader.metadata() == {"id": "SZLHOLDINGS/szl-evidence", "private": True}
        and len(present) + missing == plan["expected_object_count"]
        and _file_digest(database, deadline) == before)
    if not present:
        classification = "NO_EXPECTED_OBJECTS_PRESENT_AT_READ_TIME"
    elif missing:
        classification = "PARTIAL_EXPECTED_OBJECT_SET_PRESENT_AT_READ_TIME"
    else:
        classification = "ALL_EXPECTED_OBJECTS_PRESENT_AND_VALIDATED_AT_READ_TIME"
    return dict(plan,
        classification=classification,
        present_object_count=len(present),
        missing_object_count=missing,
        observed_object_set_sha256=_aggregate(present),
        provider_objects_fully_validated=not missing,
        candidate_unchanged=True,
        provider_writes_performed=False,
        historical_writer_attribution="NOT_ESTABLISHED")


def artifact_namespace_absence(api, database, directory, require_source, deadline, *, logical_roots=None):
    """Prove the owned artifact prefix is empty with one bounded lazy listing.

    A fresh continuation cannot accept any pre-existing object under its owned
    prefix.  Listing that prefix is therefore both stronger and substantially
    smaller than issuing two exact-path reads for every reconstructed object.
    """
    import gdw_durable_storage as storage

    before = _file_digest(database, deadline)
    directory.mkdir(mode=0o700, exist_ok=False)
    pending, plan = local_artifact_plan(database, directory / "plan", deadline,
                                        logical_roots=logical_roots)
    require(len(pending) == plan["expected_object_count"])
    require_source()
    metadata_before = api.bucket_info(bucket_id=storage.BUCKET)
    require(storage._value(metadata_before, "id") == storage.BUCKET
        and storage._value(metadata_before, "private") is True)
    rows = iter(api.list_bucket_tree(bucket_id=storage.BUCKET,
        prefix=storage.ARTIFACT_PREFIX, recursive=True))
    marker = object()
    require(next(rows, marker) is marker)
    require_source()
    metadata_after = api.bucket_info(bucket_id=storage.BUCKET)
    require(storage._value(metadata_after, "id") == storage.BUCKET
        and storage._value(metadata_after, "private") is True
        and _file_digest(database, deadline) == before)
    require_source()
    return dict(plan,
        classification="NO_EXPECTED_OBJECTS_PRESENT_AT_READ_TIME",
        present_object_count=0,
        missing_object_count=plan["expected_object_count"],
        observed_object_set_sha256=_aggregate([]),
        provider_objects_fully_validated=False,
        provider_writes_performed=False,
        historical_writer_attribution="NOT_ESTABLISHED")


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


def _canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=True, allow_nan=False) + "\n").encode("ascii")


def _worker_budget(deadline):
    require(type(deadline) in (int, float) and math.isfinite(deadline)
            and time.monotonic() < deadline)


def validate_object_worker_request(value, *, now=None):
    require(type(value) is dict and set(value) == {"schema", "workspace", "source_revision",
        "run_id", "run_attempt", "candidate_sha256", "deadline"})
    require(value["schema"] == OBJECT_WORKER_SCHEMA
        and type(value["workspace"]) is str and 0 < len(value["workspace"]) <= 1024
        and not any(c in value["workspace"] for c in ("\0", "\n", "\r"))
        and type(value["source_revision"]) is str and HEX40.fullmatch(value["source_revision"])
        and value["source_revision"] != "0" * 40
        and type(value["candidate_sha256"]) is str and HEX64.fullmatch(value["candidate_sha256"])
        and value["candidate_sha256"] != "0" * 64
        and type(value["run_id"]) is int and 0 < value["run_id"] < 2**63
        and type(value["run_attempt"]) is int and value["run_attempt"] == 1)
    deadline = value["deadline"]
    require(type(deadline) in (int, float) and math.isfinite(deadline))
    require(0 < deadline - (time.monotonic() if now is None else now) <= OBJECT_WORKER_SECONDS)
    return dict(value)


def validate_artifact_effect_observation(value):
    fields = {"expected_object_count", "expected_object_set_sha256", "candidate_unchanged",
        "all_retained_rows_validated", "classification", "present_object_count", "missing_object_count",
        "observed_object_set_sha256", "provider_objects_fully_validated", "provider_writes_performed",
        "historical_writer_attribution"}
    require(type(value) is dict and set(value) == fields)
    expected, present, missing = (value[key] for key in
        ("expected_object_count", "present_object_count", "missing_object_count"))
    require(type(expected) is int and 0 < expected <= MAX_EXPECTED_OBJECTS
        and type(present) is int and 0 <= present <= expected
        and type(missing) is int and 0 <= missing <= expected and present + missing == expected)
    require(value["candidate_unchanged"] is True and value["all_retained_rows_validated"] is True
        and value["provider_writes_performed"] is False
        and value["historical_writer_attribution"] == "NOT_ESTABLISHED"
        and type(value["provider_objects_fully_validated"]) is bool
        and value["provider_objects_fully_validated"] is (missing == 0))
    for key in ("expected_object_set_sha256", "observed_object_set_sha256"):
        require(type(value[key]) is str and HEX64.fullmatch(value[key]) and value[key] != "0" * 64)
    classification = ("NO_EXPECTED_OBJECTS_PRESENT_AT_READ_TIME" if not present else
        "PARTIAL_EXPECTED_OBJECT_SET_PRESENT_AT_READ_TIME" if missing else
        "ALL_EXPECTED_OBJECTS_PRESENT_AND_VALIDATED_AT_READ_TIME")
    require(value["classification"] == classification)
    if not present:
        require(value["observed_object_set_sha256"] == _aggregate([]))
    return dict(value)


def _held_object_worker_report():
    return {"schema": OBJECT_WORKER_SCHEMA, "state": "HELD", "source_revision": None,
        "run_id": None, "run_attempt": None, "candidate_sha256": None,
        "artifact_effect_observation": None, "provider_writes_performed": False,
        "retry_admitted": False, "restore_admitted": False, "deployment_admitted": False}


def validate_object_worker_report(value):
    require(type(value) is dict and set(value) == set(_held_object_worker_report())
        and value["schema"] == OBJECT_WORKER_SCHEMA)
    require(all(value[key] is False for key in
        ("provider_writes_performed", "retry_admitted", "restore_admitted", "deployment_admitted")))
    if value["state"] == "HELD":
        require(all(value[key] is None for key in ("source_revision", "run_id", "run_attempt",
            "candidate_sha256", "artifact_effect_observation")))
        return dict(value)
    require(value["state"] == "OBSERVED"
        and type(value["source_revision"]) is str and HEX40.fullmatch(value["source_revision"])
        and value["source_revision"] != "0" * 40
        and type(value["candidate_sha256"]) is str and HEX64.fullmatch(value["candidate_sha256"])
        and value["candidate_sha256"] != "0" * 64
        and type(value["run_id"]) is int and 0 < value["run_id"] < 2**63
        and type(value["run_attempt"]) is int and value["run_attempt"] == 1)
    return dict(value, artifact_effect_observation=validate_artifact_effect_observation(value["artifact_effect_observation"]))


def encode_object_worker_report(value):
    return _canonical(validate_object_worker_report(value))


def decode_object_worker_report(raw):
    from scripts.gdw_acquisition_evidence import strict
    value = validate_object_worker_report(strict(raw, OBJECT_WORKER_BYTES))
    require(encode_object_worker_report(value) == raw)
    return value


def _object_worker_paths(workspace, *, before=True):
    import gdw_durable_storage as storage
    directory = Path(workspace)
    require(directory.is_absolute() and directory.resolve() == directory
        and directory.parent == Path(tempfile.gettempdir()).resolve()
        and re.fullmatch(r"gdw-readonly-triage-[A-Za-z0-9_-]{6,64}", directory.name))
    storage._private_directory(directory)
    database = directory / "capture/working/gdw/candidate.sqlite3"
    storage._private_path(database, directory)
    require(not any(os.path.lexists(str(database) + suffix) for suffix in ("-wal", "-shm", "-journal")))
    if before:
        require(not os.path.lexists(directory / "artifact-effects"))
    return directory, database


def _candidate_digest(database, directory, deadline):
    import gdw_durable_storage as storage
    return storage._file_identity(database, directory, 256 * 1024 * 1024, deadline)["sha256"]


def supervised_artifact_effect_observation(workspace, require_source, deadline, *, note=lambda _boundary: None):
    """Return v2 effects only after the existing supervisor confirms child cleanup."""
    from scripts import probe_gdw_runtime_base as base
    try:
        _worker_budget(deadline)
        context = native_context(os.environ, os.environ.get("GITHUB_SHA"))
        directory, database = _object_worker_paths(str(workspace))
        candidate_digest = _candidate_digest(database, directory, deadline)
        require_source()
        child_deadline = min(deadline - POST_READBACK_SECONDS, time.monotonic() + OBJECT_WORKER_SECONDS)
        request = validate_object_worker_request({"schema": OBJECT_WORKER_SCHEMA, "workspace": str(directory),
            **context, "candidate_sha256": candidate_digest, "deadline": child_deadline})
        names = ("HF_TOKEN", "GH_TOKEN", "GITHUB_ACTIONS", "GITHUB_REPOSITORY", "GITHUB_REF",
            "GITHUB_SHA", "GITHUB_WORKFLOW_REF", "GITHUB_WORKFLOW_SHA", "GITHUB_RUN_ID",
            "GITHUB_RUN_ATTEMPT", "GITHUB_EVENT_NAME", "GITHUB_JOB")
        environment = {name: os.environ[name] for name in names if name in os.environ}
        require(bool(environment.get("HF_TOKEN")) and bool(environment.get("GH_TOKEN")))
        # Bind the isolated child's temp root to the parent-validated canonical
        # workspace, never to an unchecked ambient TMPDIR/TEMP value.
        environment.update(PATH="/usr/local/bin:/usr/bin:/bin", PYTHONDONTWRITEBYTECODE="1",
                           TMPDIR=str(directory.parent))
        note("OBJECT_READBACK")
        raw = base._run([sys.executable, "-I", "-B", str(Path(__file__).resolve()), "--artifact-object-worker"],
            deadline=child_deadline, limit=OBJECT_WORKER_BYTES, env=environment, cwd=directory,
            input_bytes=_canonical(request))
        # _run has killed/reaped its owned process group before these checks.
        _object_worker_paths(str(directory), before=False)
        require(_candidate_digest(database, directory, deadline) == candidate_digest)
        require_source()
        _worker_budget(child_deadline)
        report = decode_object_worker_report(raw)
        require(report["state"] == "OBSERVED" and all(report[key] == request[key]
            for key in ("source_revision", "run_id", "run_attempt", "candidate_sha256")))
        return report["artifact_effect_observation"]
    except BaseException:
        raise TriageHeld("READ_ONLY_TRIAGE_HELD") from None


def _artifact_object_worker_observation(raw):
    from scripts.gdw_acquisition_evidence import strict
    import gdw_durable_storage as storage
    request = validate_object_worker_request(strict(raw, OBJECT_WORKER_BYTES))
    require(_canonical(request) == raw)
    deadline = request["deadline"]
    context = native_context(os.environ, request["source_revision"])
    require(all(context[key] == request[key] for key in ("source_revision", "run_id", "run_attempt")))
    require(bool(os.environ.get("HF_TOKEN")) and bool(os.environ.get("GH_TOKEN")))
    directory, database = _object_worker_paths(request["workspace"])
    require(_candidate_digest(database, directory, deadline) == request["candidate_sha256"])
    checkout = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                              capture_output=True, text=True, timeout=10, check=True)
    require(checkout.stdout.strip() == request["source_revision"])
    from scripts import qualify_gdw_store_recovery as recovery
    with recovery.preservation._private_output():
        logging.disable(logging.CRITICAL)
        os.umask(0o077)
        os.environ.update(HF_HUB_VERBOSITY="error", HF_DEBUG="0", HF_HUB_DISABLE_PROGRESS_BARS="1",
            HF_HUB_DISABLE_IMPLICIT_TOKEN="1", HF_HUB_DISABLE_TELEMETRY="1",
            HF_HOME=str(directory / "object-worker-cache"), **trusted_artifact_environment())
        import requests
        import huggingface_hub
        require(huggingface_hub.__version__ == "1.31.0")
        with requests.Session() as session:
            session.headers.update(Authorization="Bearer " + os.environ["GH_TOKEN"], Accept="application/vnd.github+json")
            verify_native(session, context)
            require(verify_prior_attempt(session).get("prior_native_metadata_verified") is True)
            def owned():
                require(github_json(session, "git/ref/heads/main").get("object", {}).get("sha")
                        == context["source_revision"])
            api = huggingface_hub.HfApi(endpoint=storage.ENDPOINT, token=os.environ["HF_TOKEN"])
            effects = artifact_effect_observation(api, database, directory / "artifact-effects", owned, deadline)
            _object_worker_paths(str(directory), before=False)
            require(_candidate_digest(database, directory, deadline) == request["candidate_sha256"])
            owned()
            _worker_budget(deadline)
    return {**_held_object_worker_report(), "state": "OBSERVED", **context,
        "candidate_sha256": request["candidate_sha256"], "artifact_effect_observation": effects}


def artifact_object_worker():
    try:
        report = _artifact_object_worker_observation(sys.stdin.buffer.read(OBJECT_WORKER_BYTES + 1))
        report = validate_object_worker_report(report)
    except BaseException:
        report = _held_object_worker_report()
    sys.stdout.buffer.write(encode_object_worker_report(report))
    return 0 if report["state"] == "OBSERVED" else 2


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


def verify_prior_attempt(session):
    """Bind the one historical ambiguity without downloading any capture bytes."""
    run = github_json(session, f"actions/runs/{PRIOR_RUN}/attempts/{PRIOR_ATTEMPT}")
    require(run.get("id") == PRIOR_RUN and run.get("run_attempt") == PRIOR_ATTEMPT
        and run.get("head_sha") == PRIOR_SOURCE and run.get("head_branch") == "main"
        and run.get("event") == "push" and run.get("path") == ".github/workflows/hf-sync.yml"
        and run.get("status") == "completed" and run.get("conclusion") == "failure"
        and run.get("repository", {}).get("id") == 1225834126
        and run.get("repository", {}).get("full_name") == REPOSITORY
        and run.get("head_repository", {}).get("id") == 1225834126)
    listing = github_json(session, f"actions/runs/{PRIOR_RUN}/attempts/{PRIOR_ATTEMPT}/jobs?per_page=100")
    jobs = listing.get("jobs")
    expected = {
        111616471901: ("Admit the queued source before provider mutation", "success"),
        111616522098: ("Reconcile the held acquisition before provider mutation", "success"),
        111616609573: ("Check manual authority prerequisites before provider writes", "success"),
        PRIOR_JOB: ("Acquire qualified private storage through the canonical publisher", "failure"),
        111616769593: ("Resume the canonical Space without changing its allocation", "skipped"),
        111616946613: ("Deploy, source-bind, and attest exact surface", "skipped"),
        111616947075: ("Verify post-deploy configuration and bounded live proofs", "skipped"),
        111616947443: ("Publish and live-verify six domain-native flagship Spaces", "skipped"),
        111616948013: ("Probe and ingest exact post-deploy readiness verdict", "skipped"),
        111616948054: ("Prove exact live source, runtime, routes, and singleton state", "skipped"),
        111616948338: ("Rebind and functionally verify the existing Finance projection", "skipped"),
        111616948584: ("Re-authorize exact protected main after all publication proofs", "skipped"),
        111616948662: ("Await strict live and repository parity", "skipped"),
    }
    require(listing.get("total_count") == len(expected) and type(jobs) is list and len(jobs) == len(expected))
    seen = set()
    producer = None
    for job in jobs:
        require(type(job) is dict and type(job.get("id")) is int and job["id"] not in seen
            and job.get("id") in expected and job.get("head_sha") == PRIOR_SOURCE
            and job.get("run_id") == PRIOR_RUN and job.get("run_attempt") == PRIOR_ATTEMPT
            and job.get("status") == "completed"
            and (job.get("name"), job.get("conclusion")) == expected[job["id"]])
        seen.add(job["id"])
        if job["id"] == PRIOR_JOB:
            producer = job
    require(seen == set(expected) and producer is not None)
    steps = producer.get("steps")
    require(type(steps) is list and len(steps) <= 30
        and all(type(step) is dict and type(step.get("name")) is str
                and step.get("status") == "completed" for step in steps))
    by_name = {step["name"]: step for step in steps}
    require(len(by_name) == len(steps)
        and [step["name"] for step in steps if step.get("conclusion") == "failure"]
            == ["Reconcile again, verify native candidates, and acquire private storage once"]
        and by_name.get("Install the persistent old-source guard and both managed configurations once", {}).get("conclusion") == "skipped"
        and by_name.get("Retain only the immutable selector and safe guarded configuration result", {}).get("conclusion") == "success")
    artifact = github_json(session, f"actions/artifacts/{PRIOR_ARTIFACT}")
    require(artifact.get("id") == PRIOR_ARTIFACT
        and artifact.get("name") == f"canonical-durable-acquisition-{PRIOR_RUN}-{PRIOR_ATTEMPT}"
        and artifact.get("size_in_bytes") == PRIOR_ARTIFACT_BYTES
        and artifact.get("expired") is False
        and artifact.get("digest") == "sha256:" + PRIOR_ARTIFACT_SHA256
        and artifact.get("workflow_run", {}).get("id") == PRIOR_RUN
        and artifact.get("workflow_run", {}).get("repository_id") == 1225834126
        and artifact.get("workflow_run", {}).get("head_repository_id") == 1225834126
        and artifact.get("workflow_run", {}).get("head_branch") == "main"
        and artifact.get("workflow_run", {}).get("head_sha") == PRIOR_SOURCE)
    return {
        "prior_source_revision": PRIOR_SOURCE,
        "prior_run_id": PRIOR_RUN,
        "prior_run_attempt": PRIOR_ATTEMPT,
        "prior_job_id": PRIOR_JOB,
        "prior_acquisition_artifact_id": PRIOR_ARTIFACT,
        "prior_acquisition_archive_sha256": PRIOR_ARTIFACT_SHA256,
        "prior_acquisition_report_sha256": PRIOR_REPORT_SHA256,
        "prior_stage": "ARTIFACT_PUBLICATION",
        "prior_stage_state": "BOUNDARY_ENTERED",
        "prior_native_metadata_verified": True,
    }


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


def _qualified_capture_databases(qualified, expected_labels):
    """Admit only the complete nested qualifier result for both known stores."""
    require(type(expected_labels) is frozenset
        and expected_labels == frozenset(("gdw", "series_a")))
    databases = qualified.get("databases")
    require(type(databases) is dict and set(databases) == expected_labels)
    for label in expected_labels:
        item = databases[label]
        require(type(item) is dict
            and item.get("state") == "LOGICAL_CONTINUITY_VERIFIED"
            and item.get("captured_originals_unchanged") is True
            and item.get("all_declared_stored_values_unchanged") is True)
    return databases


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
    expected_labels = frozenset(recovery.preservation.DATABASES)
    databases = _qualified_capture_databases(qualified, expected_labels)
    note("LOCAL_ARTIFACTS")
    note("OBJECT_PLAN")
    effects = supervised_artifact_effect_observation(workspace, require_source, deadline, note=note)
    require_source()
    note("HEAD_AFTER")
    after = private_head_metadata(api)
    require_source()
    require(before == after)
    return {"capture_qualification": "LOGICAL_CONTINUITY_VERIFIED",
            "qualified_database_count": len(databases),
            "captured_originals_unchanged_during_qualification": True,
            "private_head_metadata": after, "metadata_stable_during_read": True,
            "artifact_effect_observation": effects}


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
              "historical_writer_attribution": "NOT_ESTABLISHED",
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
            mark_boundary(result, "PRIOR_ATTEMPT")
            result.update(verify_prior_attempt(session))
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
    raise SystemExit(artifact_object_worker() if sys.argv[1:] == ["--artifact-object-worker"] else main())
