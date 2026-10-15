#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Services/provenance: read canonical readiness artifacts without provider writes.

GitHub artifacts are the retained evidence; this cache is process-local. Import
and snapshot reads never fetch, sign, write files or start a worker. No runtime
effect is admitted here. Legacy artifacts with unprobed contracts fail closed.
"""
from __future__ import annotations

import copy
from datetime import datetime, timezone
from functools import lru_cache
import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import re
import stat
import threading
import time
from urllib.parse import urlsplit
import zipfile

REPOSITORY = "szl-holdings/a11oy"
WORKFLOW = ".github/workflows/hf-sync.yml"
API = "https://api.github.com"
MAX_JSON = 2 * 1024 * 1024
MAX_ARCHIVE = 2 * 1024 * 1024
MAX_MEMBER = 1024 * 1024


class EvidenceBlocked(RuntimeError):
    """A fixed refusal code; response bodies, tokens and signed URLs stay private."""


def require(value, code):
    if value is not True:
        raise EvidenceBlocked(code)


def digest(value, length=64):
    return (type(value) is str
            and re.fullmatch(r"[0-9a-f]{" + str(length) + r"}", value) is not None
            and value != "0" * length)


def strict(data, bound=MAX_JSON):
    require(type(data) is bytes and 0 < len(data) <= bound, "EVIDENCE_BYTE_BOUND")

    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "EVIDENCE_DUPLICATE_FIELD")
            result[key] = value
        return result

    def finite(value):
        number = float(value)
        require(math.isfinite(number), "EVIDENCE_NONFINITE_NUMBER")
        return number

    try:
        value = json.loads(data, object_pairs_hook=pairs, parse_float=finite,
                           parse_constant=lambda _v: (_ for _ in ()).throw(ValueError()))
        require(type(value) is dict, "EVIDENCE_OBJECT_REQUIRED")
        return value
    except EvidenceBlocked:
        raise
    except Exception:
        raise EvidenceBlocked("EVIDENCE_JSON_INVALID") from None


def timestamp(value):
    require(type(value) is str and len(value) <= 40, "EVIDENCE_TIMESTAMP_INVALID")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        require(result.tzinfo is not None and result.utcoffset().total_seconds() == 0,
                "EVIDENCE_TIMESTAMP_INVALID")
        return result
    except Exception:
        raise EvidenceBlocked("EVIDENCE_TIMESTAMP_INVALID") from None


def validate_archive(meta, archive, *, artifact_id, expected_digest, expected_name,
                     source, run_id, repository_id, members):
    """Check a tiny allowlisted ZIP in memory without extracting any path."""
    require(digest(source, 40) and digest(expected_digest), "ARTIFACT_IDENTITY_INVALID")
    require(type(meta) is dict and meta.get("id") == artifact_id and meta.get("expired") is False
            and meta.get("name") == expected_name and meta.get("digest") == "sha256:" + expected_digest,
            "ARTIFACT_METADATA_MISMATCH")
    run = meta.get("workflow_run")
    require(type(run) is dict and run.get("id") == run_id and run.get("head_sha") == source
            and run.get("head_branch") == "main" and run.get("repository_id") == repository_id
            and run.get("head_repository_id") == repository_id, "ARTIFACT_RUN_MISMATCH")
    require(type(archive) is bytes and 0 < len(archive) <= MAX_ARCHIVE
            and type(meta.get("size_in_bytes")) is int and meta["size_in_bytes"] == len(archive)
            and hashlib.sha256(archive).hexdigest() == expected_digest, "ARTIFACT_ARCHIVE_MISMATCH")
    try:
        with zipfile.ZipFile(io.BytesIO(archive)) as reader:
            entries = reader.infolist()
            require(len(entries) == len(members) and {entry.filename for entry in entries} == members,
                    "ARTIFACT_MEMBER_MISMATCH")
            result = {}
            total = 0
            for entry in entries:
                mode = entry.external_attr >> 16
                require(not entry.is_dir() and not entry.flag_bits & 1
                        and stat.S_IFMT(mode) in (0, stat.S_IFREG)
                        and 0 < entry.file_size <= MAX_MEMBER and entry.compress_size <= MAX_ARCHIVE,
                        "ARTIFACT_MEMBER_INVALID")
                total += entry.file_size
                require(total <= MAX_JSON, "ARTIFACT_UNCOMPRESSED_BOUND")
                data = reader.read(entry)
                require(len(data) == entry.file_size, "ARTIFACT_MEMBER_SIZE_MISMATCH")
                strict(data, MAX_MEMBER)
                result[entry.filename] = data
            return result
    except EvidenceBlocked:
        raise
    except Exception:
        raise EvidenceBlocked("ARTIFACT_ARCHIVE_INVALID") from None

REPOSITORY_ID = 1225834126
ORIGIN = "https://szlholdings-a11oy.hf.space"
PRODUCER = "Probe and ingest exact post-deploy readiness verdict"
RELOCK = "Prove exact live source, runtime, routes, and singleton state"
ROOT = Path(__file__).resolve().parent
MATRIX = ROOT / "tools/readiness-harness/tabs.json"
INTERVAL = 240
DEADLINE = 30
SERVE_AGE = 86400


@lru_cache(maxsize=1)
def _validator():
    # Import the canonical pure validator, never its provider-writing main().
    source = ROOT / ".github/scripts/publish_readiness_verdict.py"
    if not source.is_file():
        # The reviewed Docker COPY batches this source into /app/scripts/.
        source = ROOT / "scripts/publish_readiness_verdict.py"
    spec = importlib.util.spec_from_file_location(
        "_readiness_artifact_validator",
        source,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def hosted(environ=None):
    env = os.environ if environ is None else environ
    return str(env.get("SPACE_ID", "")).casefold() == "szlholdings/a11oy"


class Transport:
    """One bounded GET-only attempt; no credentials follow object redirects."""

    def __init__(self, token, stop, *, client=None, clock=time.monotonic):
        require(type(token) is str and bool(token) and not any(c.isspace() for c in token),
                "GITHUB_READ_CREDENTIAL_REQUIRED")
        self.token, self.stop, self.clock = token, stop, clock
        self.deadline = clock() + DEADLINE
        if client is None:
            import httpx
            client = httpx.Client(timeout=5, follow_redirects=False, trust_env=False)
        self.client = client

    def close(self):
        self.client.close()

    def budget(self):
        require(not self.stop.is_set() and self.clock() < self.deadline,
                "READINESS_FETCH_DEADLINE")

    def _read(self, url, headers, limit, *, redirect=False):
        self.budget()
        try:
            with self.client.stream("GET", url, headers={**headers, "Accept-Encoding": "identity"},
                                    timeout=min(5, self.deadline - self.clock())) as response:
                if redirect:
                    require(response.status_code == 302, "ARTIFACT_DOWNLOAD_UNAVAILABLE")
                    return response.headers.get("location", "")
                require(response.status_code == 200, "GITHUB_READ_UNAVAILABLE")
                require(response.headers.get("content-encoding", "").strip().lower() in ("", "identity"),
                        "READINESS_RESPONSE_ENCODING_INVALID")
                data = bytearray()
                # An output chunk size buffers a slow trickle before budget checks.
                # Identity encoding also prevents a decompressor from delaying yields.
                for chunk in response.iter_bytes():
                    self.budget()
                    require(len(data) + len(chunk) <= limit, "READINESS_BYTE_BOUND")
                    data.extend(chunk)
                self.budget()
                return bytes(data)
        except EvidenceBlocked:
            raise
        except Exception:
            raise EvidenceBlocked("GITHUB_READ_UNAVAILABLE") from None

    def json(self, suffix):
        require(suffix.startswith("/") and "#" not in suffix, "GITHUB_READ_SCOPE_INVALID")
        raw = self._read(API + "/repos/" + REPOSITORY + suffix,
                         {"Authorization": "Bearer " + self.token,
                          "Accept": "application/vnd.github+json",
                          "X-GitHub-Api-Version": "2022-11-28"}, MAX_JSON)
        return strict(raw)

    def archive(self, artifact_id):
        require(type(artifact_id) is int and artifact_id > 0, "ARTIFACT_ID_INVALID")
        location = self._read(
            f"{API}/repos/{REPOSITORY}/actions/artifacts/{artifact_id}/zip",
            {"Authorization": "Bearer " + self.token}, 0, redirect=True,
        )
        try:
            parsed = urlsplit(location)
            host = parsed.hostname or ""
            require(parsed.scheme == "https" and parsed.port in (None, 443)
                    and not parsed.username and not parsed.password and not parsed.fragment
                    and len(location) <= 16384
                    and (host.endswith(".blob.core.windows.net")
                         or host.endswith(".actions.githubusercontent.com")),
                    "ARTIFACT_DOWNLOAD_DESTINATION_INVALID")
        except (TypeError, ValueError):
            raise EvidenceBlocked("ARTIFACT_DOWNLOAD_DESTINATION_INVALID") from None
        return self._read(location, {}, MAX_ARCHIVE)


def _complete(payload, key):
    values = payload.get(key)
    require(type(values) is list and type(payload.get("total_count")) is int
            and payload["total_count"] == len(values) and 0 < len(values) <= 100,
            "READINESS_CENSUS_INCOMPLETE")
    require(all(type(value) is dict for value in values), "READINESS_METADATA_INVALID")
    return values


def _main(transport, source):
    branch = transport.json("/branches/main")
    require(branch.get("name") == "main" and branch.get("protected") is True
            and type(branch.get("commit")) is dict and branch["commit"].get("sha") == source,
            "PROTECTED_SOURCE_NO_LONGER_CURRENT")


def validate_verdict(payload, matrix, *, source, now, job):
    summary, rows, specs = payload.get("summary"), payload.get("results"), matrix.get("endpoints")
    require(type(summary) is dict and type(summary.get("requiredNotProbed")) is int
            and summary["requiredNotProbed"] == 0
            and type(summary.get("skippedStateChanging")) is int
            and summary["skippedStateChanging"] == 0, "READINESS_UNPROBED_CONTRACT")
    require(type(specs) is dict and 0 < len(specs) <= 1000 and type(rows) is list
            and len(rows) == len(specs), "READINESS_MATRIX_INCOMPLETE")
    require(all(type(row) is dict and type(row.get("path")) is str for row in rows),
            "READINESS_RESULT_INVALID")
    require(len({row["path"] for row in rows}) == len(rows)
            and {row["path"] for row in rows} == set(specs), "READINESS_MATRIX_MISMATCH")
    degraded = 0
    for row in rows:
        spec = specs[row["path"]]
        require(type(spec) is dict and row.get("method") == spec.get("method", "GET")
                and row.get("skipped", False) is False
                and type(row.get("samples")) is int and row["samples"] > 0,
                "READINESS_RESULT_NOT_PROBED")
        require(all(row.get(k) is False for k in ("lie", "unreachable", "throttled"))
                and type(row.get("degraded")) is bool
                and all(row.get(k) is True for k in ("schemaOk", "citationOk", "labelPolicyOk"))
                and row.get("freshOk") is not False, "READINESS_RESULT_FAILED")
        require(spec.get("freshnessSLA") is None or row.get("freshOk") is True,
                "READINESS_FRESHNESS_UNAVAILABLE")
        require(type(row.get("status")) is int
                and row["status"] in spec.get("degradedRules", {}).get("allowStatuses", [200]),
                "READINESS_STATUS_FAILED")
        if row["degraded"]:
            require(spec.get("required", True) is False
                    or spec.get("degradedBlocksReadiness", True) is False,
                    "READINESS_REQUIRED_SOURCE_UNAVAILABLE")
            degraded += 1
    require(summary.get("endpoints") == len(rows) and summary.get("degraded") == degraded
            and summary.get("ok") == len(rows) - degraded, "READINESS_SUMMARY_MISMATCH")
    require(payload.get("sourceRevisionBefore") == source
            and payload.get("sourceRevisionAfter") == source
            and payload.get("sourceRevisionStatus") == "OBSERVED", "READINESS_SOURCE_BRACKET_INVALID")
    checked = timestamp(payload.get("checkedAt"))
    require(timestamp(job.get("started_at")) <= checked <= timestamp(job.get("completed_at")),
            "READINESS_OBSERVATION_TIME_INVALID")
    try:
        compact = _validator().compact_verdict(payload, expected_origin=ORIGIN,
                                              expected_source_sha=source, now=now)
    except Exception:
        raise EvidenceBlocked("READINESS_VERDICT_INVALID") from None
    compact["summary"]["requiredNotProbed"] = 0
    return compact


def acquire(transport, source, matrix, *, now):
    require(digest(source, 40), "READINESS_SOURCE_INVALID")
    _main(transport, source)
    listing = transport.json(f"/actions/workflows/hf-sync.yml/runs?head_sha={source}&per_page=1")
    runs = listing.get("workflow_runs")
    require(type(runs) is list and len(runs) == 1 and type(runs[0]) is dict,
            "READINESS_RUN_UNAVAILABLE")
    selected = runs[0]
    run_id, attempt = selected.get("id"), selected.get("run_attempt")
    require(type(run_id) is int and run_id > 0 and type(attempt) is int and attempt > 0,
            "READINESS_RUN_ID_INVALID")
    run = transport.json(f"/actions/runs/{run_id}/attempts/{attempt}")
    require(run.get("id") == run_id and run.get("run_attempt") == attempt
            and run.get("path") == WORKFLOW and run.get("event") in ("push", "workflow_dispatch")
            and run.get("head_sha") == source and run.get("head_branch") == "main"
            and run.get("status") == "completed" and run.get("conclusion") == "success"
            and run.get("repository", {}).get("id") == REPOSITORY_ID
            and run.get("repository", {}).get("full_name") == REPOSITORY
            and run.get("head_repository", {}).get("id") == REPOSITORY_ID,
            "READINESS_RUN_UNQUALIFIED")
    jobs = _complete(transport.json(f"/actions/runs/{run_id}/attempts/{attempt}/jobs?per_page=100"), "jobs")
    producer = None
    for name in (PRODUCER, RELOCK):
        matches = [job for job in jobs if job.get("name") == name]
        require(len(matches) == 1, "READINESS_JOB_UNAVAILABLE")
        job = matches[0]
        require(job.get("run_id") == run_id and job.get("run_attempt") == attempt
                and job.get("head_sha") == source and job.get("status") == "completed"
                and job.get("conclusion") == "success", "READINESS_JOB_UNQUALIFIED")
        require(timestamp(run.get("run_started_at")) <= timestamp(job.get("started_at"))
                <= timestamp(job.get("completed_at")) <= now, "READINESS_JOB_TIME_INVALID")
        if name == PRODUCER:
            producer = job
    artifacts = _complete(transport.json(f"/actions/runs/{run_id}/artifacts?per_page=100"), "artifacts")
    name = f"canonical-a11oy-readiness-{run_id}-{attempt}"
    matches = [artifact for artifact in artifacts if artifact.get("name") == name]
    require(len(matches) == 1, "READINESS_ARTIFACT_UNAVAILABLE")
    meta = matches[0]
    artifact_id = meta.get("id")
    require(type(artifact_id) is int and artifact_id > 0, "ARTIFACT_ID_INVALID")
    declared = meta.get("digest")
    require(type(declared) is str and declared.startswith("sha256:") and digest(declared[7:]),
            "ARTIFACT_DIGEST_INVALID")
    require(timestamp(producer.get("started_at")) <= timestamp(meta.get("created_at"))
            <= timestamp(producer.get("completed_at")), "ARTIFACT_ATTEMPT_TIME_MISMATCH")
    members = validate_archive(meta, transport.archive(artifact_id), artifact_id=artifact_id,
                               expected_digest=declared[7:], expected_name=name,
                               source=source, run_id=run_id, repository_id=REPOSITORY_ID,
                               members=frozenset({"readiness-verdict.json"}))
    verdict = validate_verdict(strict(members["readiness-verdict.json"]), matrix,
                               source=source, now=now, job=producer)
    _main(transport, source)
    return {"verdict": verdict, "reason": None, "source": source,
            "evidence": {"repository": REPOSITORY, "workflow": WORKFLOW,
                         "run_id": run_id, "run_attempt": attempt, "artifact_id": artifact_id,
                         "artifact_sha256": declared[7:], "checked_at": verdict["checkedAt"],
                         "retrieved_at": now.isoformat(), "signatures_verified": False}}


class Reader:
    def __init__(self, *, environ=None, fetch=acquire, transport_factory=Transport, interval=INTERVAL):
        self.env = os.environ if environ is None else environ
        self.fetch, self.transport_factory, self.interval = fetch, transport_factory, interval
        self.lock, self.lifecycle = threading.Lock(), threading.Lock()
        self.stop_event, self.thread = threading.Event(), None
        self.state = {"verdict": None, "reason": "NOT_OBSERVED", "evidence": None}

    def snapshot(self, *, now=None):
        with self.lock:
            state = copy.deepcopy(self.state)
        verdict = state.get("verdict")
        if verdict:
            age = ((now or datetime.now(timezone.utc)) - timestamp(verdict["checkedAt"])).total_seconds()
            if (not hosted(self.env) or state.get("source") != self.env.get("SZL_GIT_SHA")
                    or self.env.get("SZL_READINESS_CANONICAL_ORIGIN", ORIGIN) != ORIGIN
                    or not 0 <= age <= SERVE_AGE):
                return {"verdict": None, "reason": "SOURCE_OR_CLOCK_CHANGED", "evidence": None}
        return state

    def refresh(self):
        source = self.env.get("SZL_GIT_SHA", "")
        transport = None
        try:
            require(hosted(self.env), "CANONICAL_SPACE_REQUIRED")
            require(self.env.get("SZL_READINESS_CANONICAL_ORIGIN", ORIGIN) == ORIGIN,
                    "CANONICAL_ORIGIN_REQUIRED")
            token = next((self.env.get(k, "").strip() for k in
                          ("SZL_READINESS_GH_TOKEN", "GITHUB_TOKEN", "GH_TOKEN") if self.env.get(k)), "")
            transport = self.transport_factory(token, self.stop_event)
            with MATRIX.open("rb") as stream:
                matrix = strict(stream.read(MAX_JSON + 1))
            state = self.fetch(transport, source, matrix, now=datetime.now(timezone.utc))
            require(source == self.env.get("SZL_GIT_SHA") and hosted(self.env)
                    and self.env.get("SZL_READINESS_CANONICAL_ORIGIN", ORIGIN) == ORIGIN
                    and not self.stop_event.is_set(), "READINESS_IDENTITY_CHANGED")
        except EvidenceBlocked as error:
            state = {"verdict": None, "reason": str(error), "evidence": None}
        except Exception:
            state = {"verdict": None, "reason": "READINESS_EVIDENCE_UNAVAILABLE", "evidence": None}
        finally:
            if transport is not None:
                try:
                    transport.close()
                except Exception:
                    pass
        with self.lock:
            if not self.stop_event.is_set():
                self.state = state

    def _loop(self):
        while not self.stop_event.is_set():
            self.refresh()
            self.stop_event.wait(self.interval)

    def start(self):
        with self.lifecycle:
            if self.thread is not None and self.thread.is_alive():
                return False
            self.stop_event = threading.Event()
            with self.lock:
                self.state = {"verdict": None, "reason": "NOT_OBSERVED", "evidence": None}
            if not hosted(self.env):
                return False
            self.thread = threading.Thread(target=self._loop, name="a11oy-readiness-artifact", daemon=True)
            self.thread.start()
            return True

    def stop(self, timeout=6):
        with self.lifecycle:
            self.stop_event.set()
            thread = self.thread
            if thread is not None:
                thread.join(timeout=max(0, min(timeout, 6)))
            with self.lock:
                self.state = {"verdict": None, "reason": "READER_STOPPED", "evidence": None}
            # A still-stopping worker owns its event; start() will not replace it.
            if thread is None or not thread.is_alive():
                self.thread = None


reader = Reader()
