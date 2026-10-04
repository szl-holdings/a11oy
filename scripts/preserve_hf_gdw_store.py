#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Preserve stopped canonical bucket databases; never admit or repair a store.

The only remote effect is a new capture beneath PRIVATE_PREFIX in the existing
private bucket. Originals are copied by their observed Xet content identities.
SQLite opens disposable local copies only. Public output is an allowlisted
metadata report, never provider exception text, SQL, rows, or database bytes.

The current bucket-mounted SQLite storage contract is not qualified. Successful
preservation therefore still blocks resume/deploy. A later reviewed storage and
restore change must supply that qualification; this script has no bypass flag.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import logging
import os
import re
import shutil
import signal
import sqlite3
import stat
import sys
import tempfile
import time
import uuid
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = "szl.hf-private-store-preservation/v1"
SPACE = "SZLHOLDINGS/a11oy"
BUCKET = "SZLHOLDINGS/szl-evidence"
ENDPOINT = "https://huggingface.co"
PRIVATE_PREFIX = "a11oy/incident-preservation/v1"
SDK_VERSION = "1.23.0"
SDK_COMMIT = "0c92853b8e07bc50ee0817e307e9fd88194dd4f3"
DATABASES = {
    "gdw": "a11oy/gdw/gdw.sqlite3",
    "series_a": "a11oy/series-a/control-plane-v2.sqlite3",
}
SUFFIXES = ("", "-journal", "-wal", "-shm")
SOURCE_PATHS = tuple(path + suffix for path in DATABASES.values() for suffix in SUFFIXES)
STOPPED_STAGES = {"RUNTIME_ERROR", "PAUSED"}
MAX_FILE_BYTES = 256 * 1024 * 1024
MAX_TOTAL_BYTES = 768 * 1024 * 1024
DEADLINE_SECONDS = 420
OBSERVATION_SECONDS = 5
INSPECTION_SECONDS = 30
HEX40 = re.compile(r"[0-9a-f]{40}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
GENERATION = re.compile(r"[0-9a-f]{32}\Z")
TABLES = {
    "gdw": ("schema_meta", "usage", "session_state", "requests", "receipts",
            "proof_outbox", "effect_outbox", "effect_recovery_audit"),
    "series_a": ("snapshots", "passports", "passport_executions", "receipts", "events", "metadata"),
}


class PreservationError(RuntimeError):
    """Only a fixed diagnostic code crosses the private/public boundary."""

    def __init__(self, code: str):
        if re.fullmatch(r"[A-Z][A-Z0-9_]{0,79}", code) is None:
            code = "PRESERVATION_UNAVAILABLE"
        self.code = code
        super().__init__(code)


class BatchOutcomeUnknown(RuntimeError):
    """A single attempted bucket mutation needs identity/readback resolution."""


def hub_http_client(*, transport: Any = None) -> Any:
    """Prevent SDK http_backoff from blindly retrying the canonical batch POST.

    The SDK's public client factory is the request boundary. Converting both
    retry statuses and transport failures into a non-httpx exception prevents
    its default five retries; the caller performs readback instead. Other
    endpoints retain normal SDK read behavior and cannot redirect.
    """
    import httpx

    class SingleAttemptClient(httpx.Client):
        def request(self, method: str, url: Any, *args: Any, **kwargs: Any) -> Any:
            mutation = method.upper() == "POST" and str(url) == f"{ENDPOINT}/api/buckets/{BUCKET}/batch"
            if not mutation:
                return super().request(method, url, *args, **kwargs)
            try:
                response = super().request(method, url, *args, **kwargs)
            except httpx.HTTPError:
                raise BatchOutcomeUnknown() from None
            if not 200 <= response.status_code < 300:
                response.close()
                raise BatchOutcomeUnknown()
            return response

    return SingleAttemptClient(timeout=20, follow_redirects=False, transport=transport)


def _value(obj: Any, key: str, default: Any = None) -> Any:
    return obj.get(key, default) if isinstance(obj, Mapping) else getattr(obj, key, default)


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode()


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _call(function: Callable, *args: Any, **kwargs: Any) -> Any:
    try:
        return function(*args, **kwargs)
    except PreservationError:
        raise
    except Exception:
        # Provider exception text can contain credentials, response bodies or
        # private paths. Never serialize it or allow a chained traceback.
        raise PreservationError("PROVIDER_OPERATION_UNAVAILABLE") from None


@contextlib.contextmanager
def _private_output():
    """Also suppress native SDK writes that bypass Python's stream objects."""
    sys.stdout.flush()
    sys.stderr.flush()
    saved = (os.dup(1), os.dup(2))
    try:
        with open(os.devnull, "w") as sink:
            os.dup2(sink.fileno(), 1)
            os.dup2(sink.fileno(), 2)
            with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
                yield
    finally:
        os.dup2(saved[0], 1)
        os.dup2(saved[1], 2)
        os.close(saved[0])
        os.close(saved[1])


def observe_stopped(api: Any) -> dict[str, Any]:
    if _value(api, "endpoint") != ENDPOINT:
        raise PreservationError("NONCANONICAL_ENDPOINT")
    bucket = _call(api.bucket_info, bucket_id=BUCKET)
    if _value(bucket, "id") != BUCKET or _value(bucket, "private") is not True:
        raise PreservationError("PRIVATE_BUCKET_REQUIRED")
    info = _call(api.space_info, repo_id=SPACE)
    if _value(info, "id") != SPACE:
        raise PreservationError("SPACE_IDENTITY_MISMATCH")
    revision = _value(info, "sha")
    if not isinstance(revision, str) or HEX40.fullmatch(revision) is None:
        raise PreservationError("SPACE_REVISION_UNAVAILABLE")
    configured_runtime = _value(info, "runtime")
    volumes = _value(configured_runtime, "volumes")
    if not isinstance(volumes, (list, tuple)):
        raise PreservationError("MOUNT_TOPOLOGY_UNAVAILABLE")
    data_volumes = []
    for volume in volumes:
        mount = _value(volume, "mount_path", _value(volume, "mountPath"))
        if not isinstance(mount, str):
            raise PreservationError("MOUNT_TOPOLOGY_UNAVAILABLE")
        if mount == "/data" or mount.startswith("/data/"):
            data_volumes.append(volume)
    if len(data_volumes) != 1:
        raise PreservationError("MOUNT_TOPOLOGY_CONFLICT")
    volume = data_volumes[0]
    if (_value(volume, "type") != "bucket" or _value(volume, "source") != BUCKET
            or _value(volume, "mount_path", _value(volume, "mountPath")) != "/data"
            or _value(volume, "read_only", _value(volume, "readOnly")) is not False
            or _value(volume, "path") not in (None, "")
            or _value(volume, "revision") is not None):
        raise PreservationError("MOUNT_TOPOLOGY_CONFLICT")
    runtime = _call(api.get_space_runtime, repo_id=SPACE)
    stage = _value(runtime, "stage")
    stage = _value(stage, "value", stage)
    if stage not in STOPPED_STAGES:
        raise PreservationError("STOPPED_RUNTIME_REQUIRED")
    return {"stage": stage, "hf_revision": revision, "observed_at": _utc(),
            "bucket_private": True, "mount_path": "/data", "mount_type": "bucket"}


def _timestamp(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise PreservationError("OBJECT_IDENTITY_MALFORMED")
    return value.astimezone(timezone.utc).isoformat()


def paths_info(api: Any, paths: tuple[str, ...]) -> tuple[dict[str, Any], dict[str, dict]]:
    """An exact finite paths-info request avoids an unbounded bucket census."""
    raw: dict[str, Any] = {}
    identities: dict[str, dict] = {}
    try:
        for item in api.get_bucket_paths_info(bucket_id=BUCKET, paths=paths):
            path = _value(item, "path")
            size = _value(item, "size")
            xet_hash = _value(item, "xet_hash")
            if (path not in paths or path in raw or _value(item, "type") != "file"
                    or type(size) is not int or not 0 <= size <= MAX_FILE_BYTES
                    or not isinstance(xet_hash, str) or HEX64.fullmatch(xet_hash) is None):
                raise PreservationError("OBJECT_IDENTITY_MALFORMED")
            raw[path] = item
            identities[path] = {"size": size, "xet_hash": xet_hash,
                                "mtime": _timestamp(_value(item, "mtime")),
                                "uploaded_at": _timestamp(_value(item, "uploaded_at"))}
    except PreservationError:
        raise
    except Exception:
        raise PreservationError("OBJECT_IDENTITIES_UNAVAILABLE") from None
    if sum(item["size"] for item in identities.values()) > MAX_TOTAL_BYTES:
        raise PreservationError("CAPTURE_SIZE_BOUND_EXCEEDED")
    return raw, identities


def _local_files(root: Path, identities: Mapping[str, Mapping], paths: Mapping[str, Path]) -> dict[str, str]:
    digests = {}
    for key, identity in identities.items():
        path = paths[key]
        try:
            status = path.lstat()
        except OSError:
            raise PreservationError("CAPTURE_FILE_UNAVAILABLE") from None
        if (not stat.S_ISREG(status.st_mode) or path.is_symlink()
                or root.resolve() not in path.resolve().parents or status.st_size != identity["size"]):
            raise PreservationError("CAPTURE_FILE_MISMATCH")
        digests[key] = _sha(path)
    return digests


def sqlite_header(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        header = handle.read(100)
    if len(header) != 100 or header[:16] != b"SQLite format 3\x00":
        return {"state": "SQLITE_HEADER_INVALID"}
    page_size = int.from_bytes(header[16:18], "big")
    return {"state": "OBSERVED", "page_size": 65536 if page_size == 1 else page_size,
            "write_version": header[18], "read_version": header[19],
            "page_count": int.from_bytes(header[28:32], "big"),
            "schema_cookie": int.from_bytes(header[40:44], "big"),
            "schema_format": int.from_bytes(header[44:48], "big"),
            "user_version": int.from_bytes(header[60:64], "big"),
            "application_id": int.from_bytes(header[68:72], "big"),
            "sqlite_version_number_last_modified": int.from_bytes(header[96:100], "big")}


def inspect_database(label: str, original: Path, directory: Path) -> dict[str, Any]:
    """Open only an isolated working copy, without importing runtime writers."""
    report: dict[str, Any] = {"header": sqlite_header(original),
                              "inspector_sqlite_version": sqlite3.sqlite_version,
                              "runtime_sqlite_version": "UNAVAILABLE",
                              "integrity": "NOT_RUN", "restore_admitted": False}
    directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    database = directory / original.name
    for suffix in SUFFIXES:
        source = original.with_name(original.name + suffix)
        if source.exists():
            shutil.copyfile(source, database.with_name(database.name + suffix))
    deadline = time.monotonic() + INSPECTION_SECONDS
    connection = None
    try:
        connection = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True, timeout=5)
        connection.enable_load_extension(False)
        connection.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
        connection.execute("PRAGMA trusted_schema=OFF")
        connection.execute("PRAGMA query_only=ON")
        connection.execute("BEGIN")
        result = [row[0] for row in connection.execute("PRAGMA integrity_check(100)").fetchall()]
        report["integrity_result_sha256"] = hashlib.sha256(_json_bytes(result)).hexdigest()
        report["integrity_result_count"] = len(result)
        report["integrity"] = "OK" if result == ["ok"] else "FAILED"
        if result != ["ok"]:
            lines = [line for value in result for line in value.splitlines()
                     if line != "*** in database main ***"]
            report["integrity_classification"] = (
                "UNREFERENCED_PAGES" if lines and all(re.fullmatch(r"Page [0-9]+: never used", line)
                                                      for line in lines) else "OTHER_SQLITE_INTEGRITY_ERROR")
        foreign = connection.execute("PRAGMA foreign_key_check").fetchmany(1001)
        report["foreign_key_violation_count"] = min(len(foreign), 1000)
        report["foreign_key_check_complete"] = len(foreign) < 1001
        schema = connection.execute(
            "SELECT type,name,tbl_name,sql FROM sqlite_schema ORDER BY type,name,tbl_name,sql"
        ).fetchmany(1001)
        if len(schema) > 1000:
            raise PreservationError("SQLITE_SCHEMA_BOUND_EXCEEDED")
        report["schema_sha256"] = hashlib.sha256(_json_bytes(schema)).hexdigest()
        report["schema_object_count"] = len(schema)
        ordinary = {row[1] for row in schema if row[0] == "table"
                    and row[3] and re.match(r"CREATE\s+TABLE\b", row[3], re.I)}
        report["table_counts"] = {}
        for table in TABLES[label]:
            if table in ordinary:
                report["table_counts"][table] = connection.execute(
                    'SELECT count(*) FROM "' + table + '"').fetchone()[0]
        report["expected_tables_present"] = set(TABLES[label]) <= ordinary
        if label == "gdw" and "schema_meta" in ordinary:
            rows = connection.execute(
                "SELECT schema_version,database_generation_id FROM schema_meta WHERE schema_name='gdw'"
            ).fetchmany(2)
            if len(rows) == 1 and type(rows[0][0]) is int and isinstance(rows[0][1], str) and GENERATION.fullmatch(rows[0][1]):
                report["schema_version"] = rows[0][0]
                report["database_generation_id"] = rows[0][1]
        if label == "series_a" and "metadata" in ordinary:
            rows = connection.execute("SELECT value FROM metadata WHERE key='storage_instance_id'").fetchmany(2)
            if len(rows) == 1 and isinstance(rows[0][0], str) and re.fullmatch(r"store_[0-9a-f]{32}", rows[0][0]):
                report["database_generation_id"] = rows[0][0]
        report["journal_mode_observed_on_copy"] = connection.execute("PRAGMA journal_mode").fetchone()[0]
        report["inspection_state"] = "COMPLETE"
    except PreservationError as exc:
        if exc.code == "PRESERVATION_DEADLINE_EXHAUSTED":
            raise
        report["inspection_state"] = exc.code
    except sqlite3.Error as exc:
        report["inspection_state"] = "SQLITE_READ_UNAVAILABLE"
        code = getattr(exc, "sqlite_errorname", "SQLITE_ERROR")
        report["sqlite_error_code"] = code if re.fullmatch(r"SQLITE_[A-Z_]{1,48}", code) else "SQLITE_ERROR"
    finally:
        if connection is not None:
            connection.close()
    return report


def preserve(api: Any, *, source_sha: str, run_id: str, run_attempt: str,
             workspace: Path, require_owned_source: Callable[[], None],
             sleep: Callable[[float], None] = time.sleep,
             nonce: str | None = None, deadline: float | None = None,
             clock: Callable[[], float] = time.monotonic) -> dict[str, Any]:
    report: dict[str, Any] = {"schema": SCHEMA, "generated_at": _utc(), "space": SPACE,
        "bucket": BUCKET, "state": "BLOCKED", "diagnostic_code": "PRESERVATION_NOT_RUN",
        "preservation_state": "NOT_RUN", "deployment_admitted": False, "restore_admitted": False,
        "storage_contract": "BUCKET_MOUNTED_SQLITE_UNQUALIFIED", "originals_mutated": False,
        "space_mutated": False, "secret_values_recorded": False, "private_bytes_in_public_artifacts": False,
        "sdk_version": SDK_VERSION, "sdk_source_commit": SDK_COMMIT, "observations": []}
    deadline = clock() + DEADLINE_SECONDS if deadline is None else deadline

    def check_budget() -> None:
        # SQLite can translate an exception raised by SIGALRM inside its
        # progress callback into SQLITE_INTERRUPT. The monotonic deadline is
        # authoritative even when that exception identity has been lost.
        if clock() >= deadline:
            raise PreservationError("PRESERVATION_DEADLINE_EXHAUSTED")

    try:
        check_budget()
        if (HEX40.fullmatch(source_sha) is None or re.fullmatch(r"[1-9][0-9]{0,19}", run_id) is None
                or re.fullmatch(r"[1-9][0-9]{0,5}", run_attempt) is None):
            raise PreservationError("SOURCE_CONTEXT_INVALID")
        nonce = nonce or uuid.uuid4().hex
        if GENERATION.fullmatch(nonce) is None:
            raise PreservationError("CAPTURE_ID_INVALID")
        capture_id = f"{run_id}-{run_attempt}-{source_sha}-{nonce}"
        prefix = f"{PRIVATE_PREFIX}/{capture_id}"
        report.update(source_revision=source_sha, capture_id=capture_id, private_capture_prefix=prefix)
        workspace.mkdir(mode=0o700, parents=True, exist_ok=False)
        require_owned_source()
        first_state = observe_stopped(api)
        report["observations"].append(first_state)
        raw, initial = paths_info(api, SOURCE_PATHS)
        if not all(path in initial for path in DATABASES.values()):
            raise PreservationError("ORIGINAL_DATABASE_MISSING")
        sleep(OBSERVATION_SECONDS)

        def stable_originals() -> None:
            check_budget()
            state = observe_stopped(api)
            report["observations"].append(state)
            if state["hf_revision"] != first_state["hf_revision"]:
                raise PreservationError("SPACE_REVISION_CHANGED")
            _, observed = paths_info(api, SOURCE_PATHS)
            if observed != initial:
                raise PreservationError("ORIGINAL_IDENTITIES_CHANGED")
            check_budget()

        stable_originals()
        report["initial_identities_stable"] = True
        captured = workspace / "captured"
        captured.mkdir(mode=0o700)
        local_paths = {}
        for path in initial:
            local = captured / path
            local.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            local_paths[path] = local
        _call(api.download_bucket_files, bucket_id=BUCKET,
              files=[(raw[path], local_paths[path]) for path in initial], raise_on_missing_files=True)
        hashes = _local_files(captured, initial, local_paths)
        stable_originals()
        destinations = {path: f"{prefix}/originals/{path}" for path in initial}
        target_paths = tuple(destinations.values())
        if any(path in SOURCE_PATHS or not path.startswith(prefix + "/originals/") for path in target_paths):
            raise PreservationError("DESTINATION_OUTSIDE_CAPTURE")
        require_owned_source()
        stable_originals()
        _, occupied = paths_info(api, target_paths)
        if occupied:
            raise PreservationError("CAPTURE_DESTINATION_EXISTS")
        check_budget()
        report["preservation_state"] = "COPY_REQUESTED"
        try:
            api.batch_bucket_files(bucket_id=BUCKET, copy=[
                ("bucket", BUCKET, initial[path]["xet_hash"], destinations[path]) for path in initial])
            report["copy_response"] = "RECEIVED"
        except PreservationError:
            raise
        except Exception:
            # The batch is not transactional. Inspect a lost/failed response;
            # never retry blindly or delete a possibly successful partial copy.
            report["copy_response"] = "UNAVAILABLE"
        copies_raw, copies = paths_info(api, target_paths)
        report["private_copy_count"] = len(copies)
        if set(copies) != set(target_paths) or any(
                copies[destinations[path]][key] != initial[path][key]
                for path in initial for key in ("xet_hash", "size")):
            raise PreservationError("PRIVATE_COPY_INCOMPLETE")
        verification = workspace / "verification"
        verification.mkdir(mode=0o700)
        verify_paths = {path: verification / str(index) for index, path in enumerate(initial)}
        _call(api.download_bucket_files, bucket_id=BUCKET,
              files=[(copies_raw[destinations[path]], verify_paths[path]) for path in initial],
              raise_on_missing_files=True)
        if _local_files(verification, initial, verify_paths) != hashes:
            raise PreservationError("PRIVATE_COPY_DIGEST_MISMATCH")
        stable_originals()
        report["preservation_state"] = "PRIVATE_OBJECTS_VERIFIED"
        report["files"] = [{"source_path": path, "private_copy_path": destinations.get(path),
                            "present": path in initial, **initial.get(path, {}),
                            "sha256": hashes.get(path)} for path in SOURCE_PATHS]
        report["databases"] = {
            label: inspect_database(label, local_paths[path], workspace / "inspection" / label)
            for label, path in DATABASES.items()}
        check_budget()
        if _local_files(captured, initial, local_paths) != hashes:
            raise PreservationError("LOCAL_ORIGINAL_CHANGED_DURING_INSPECTION")
        report["captured_originals_unchanged_after_inspection"] = True
        report["diagnostic_code"] = "STORAGE_RECOVERY_REQUIRED"
        # The manifest is a preservation record, not a mutable latest pointer or
        # a restoration admission. It references every expected sidecar/absence.
        manifest = _json_bytes(report)
        manifest_path = prefix + "/preservation-manifest.json"
        require_owned_source()
        stable_originals()
        _, occupied = paths_info(api, (manifest_path,))
        if occupied:
            raise PreservationError("CAPTURE_DESTINATION_EXISTS")
        check_budget()
        try:
            api.batch_bucket_files(bucket_id=BUCKET, add=[(manifest, manifest_path)])
        except PreservationError:
            raise
        except Exception:
            pass  # Resolve uncertain response from exact identity/readback below.
        manifest_raw, manifest_info = paths_info(api, (manifest_path,))
        if set(manifest_info) != {manifest_path} or manifest_info[manifest_path]["size"] != len(manifest):
            raise PreservationError("PRIVATE_MANIFEST_UNAVAILABLE")
        manifest_local = verification / "preservation-manifest.json"
        _call(api.download_bucket_files, bucket_id=BUCKET,
              files=[(manifest_raw[manifest_path], manifest_local)], raise_on_missing_files=True)
        manifest_hash = hashlib.sha256(manifest).hexdigest()
        if _local_files(verification, manifest_info, {manifest_path: manifest_local})[manifest_path] != manifest_hash:
            raise PreservationError("PRIVATE_MANIFEST_DIGEST_MISMATCH")
        stable_originals()
        check_budget()
        report.update(preservation_state="VERIFIED", diagnostic_code="STORAGE_RECOVERY_REQUIRED",
                      private_manifest={"path": manifest_path, "sha256": manifest_hash,
                                        "xet_hash": manifest_info[manifest_path]["xet_hash"]})
    except PreservationError as exc:
        report["diagnostic_code"] = exc.code
    except Exception:
        report["diagnostic_code"] = "PRESERVATION_UNAVAILABLE"
    report["completed_at"] = _utc()
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    # No target, repair, resume, overwrite or admission options exist.
    report: dict[str, Any] = {"schema": SCHEMA, "state": "BLOCKED", "deployment_admitted": False,
                              "diagnostic_code": "SOURCE_CONTEXT_INVALID", "secret_values_recorded": False}
    previous_alarm = None
    try:
        if (os.environ.get("GITHUB_ACTIONS") != "true"
                or os.environ.get("GITHUB_REPOSITORY") != "szl-holdings/a11oy"
                or os.environ.get("GITHUB_REF") != "refs/heads/main"):
            raise PreservationError("SOURCE_CONTEXT_INVALID")
        source_sha = os.environ.get("GITHUB_SHA", "")
        token = os.environ.get("HF_TOKEN", "")
        github_token = os.environ.get("GH_TOKEN", "")
        if not token or not github_token:
            raise PreservationError("CONTROL_CREDENTIAL_UNAVAILABLE")
        from hf_exact_main_ownership import fetch_main_sha

        def require_owned_source() -> None:
            if _call(fetch_main_sha, "szl-holdings/a11oy", github_token) != source_sha:
                raise PreservationError("SOURCE_NO_LONGER_CURRENT_MAIN")

        def timeout_handler(_signal: int, _frame: Any) -> None:
            raise PreservationError("PRESERVATION_DEADLINE_EXHAUSTED")

        previous_alarm = signal.signal(signal.SIGALRM, timeout_handler)
        deadline = time.monotonic() + DEADLINE_SECONDS
        signal.alarm(DEADLINE_SECONDS)
        os.umask(0o077)
        os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
        os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
        os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"
        os.environ.pop("HF_DEBUG", None)
        logging.disable(logging.CRITICAL)
        with tempfile.TemporaryDirectory(prefix="szl-private-store-") as temporary:
            # SDK caches/logs, downloaded originals and working copies share
            # this private ephemeral directory, never the artifact directory.
            os.environ["HF_HOME"] = str(Path(temporary) / "hf-cache")
            os.environ["HF_HUB_CACHE"] = str(Path(temporary) / "hf-cache" / "hub")
            os.environ["HF_XET_CACHE"] = str(Path(temporary) / "hf-cache" / "xet")
            with _private_output():
                import huggingface_hub
                from huggingface_hub.utils import set_client_factory
                if huggingface_hub.__version__ != SDK_VERSION:
                    raise PreservationError("SDK_VERSION_MISMATCH")
                set_client_factory(hub_http_client)
                api = huggingface_hub.HfApi(endpoint=ENDPOINT, token=token)
                report = preserve(api, source_sha=source_sha,
                                  run_id=os.environ.get("GITHUB_RUN_ID", ""),
                                  run_attempt=os.environ.get("GITHUB_RUN_ATTEMPT", ""),
                                  workspace=Path(temporary) / "capture",
                                  require_owned_source=require_owned_source, deadline=deadline)
    except PreservationError as exc:
        report["diagnostic_code"] = exc.code
    except Exception:
        report["diagnostic_code"] = "PRESERVATION_UNAVAILABLE"
    finally:
        if previous_alarm is not None:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, previous_alarm)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(_json_bytes(report))
    print(json.dumps({"schema": SCHEMA, "state": "BLOCKED",
                      "preservation_state": report.get("preservation_state", "NOT_RUN"),
                      "diagnostic_code": report["diagnostic_code"], "deployment_admitted": False}))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
