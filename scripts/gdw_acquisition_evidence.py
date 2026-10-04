#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Read exact canonical Actions metadata and small allowlisted JSON artifacts.

This module has no GitHub or Hugging Face write operation. Archive contents stay
in memory; neither paths nor executable content are extracted from an artifact.
The caller supplies a hard process deadline around all transport and parsing.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import io
import json
import math
import os
import re
import stat
import time
from typing import Any
from urllib.parse import urlsplit
import zipfile

REPOSITORY = "szl-holdings/a11oy"
WORKFLOW = ".github/workflows/hf-sync.yml"
API = "https://api.github.com"
MAX_JSON = 2 * 1024 * 1024
MAX_ARCHIVE = 2 * 1024 * 1024
MAX_MEMBER = 1024 * 1024
SOURCE_JOB = "Admit the queued source before provider mutation"
QUALIFICATION_JOB = "Check manual authority prerequisites before provider writes"
ACQUISITION_JOB = "Acquire qualified private storage through the canonical publisher"
ACQUISITION_JOB_KEY = "durable-acquisition"


class EvidenceBlocked(RuntimeError):
    """Fixed codes only; transport bodies, signed URLs and tokens stay private."""


def require(value: bool, code: str) -> None:
    if value is not True:
        raise EvidenceBlocked(code)


def digest(value: str, length: int = 64) -> bool:
    return type(value) is str and re.fullmatch(r"[0-9a-f]{" + str(length) + r"}", value) is not None and value != "0" * length


def strict(data: bytes, bound: int = MAX_JSON) -> dict:
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


def timestamp(value: Any) -> datetime:
    require(type(value) is str and len(value) <= 40, "EVIDENCE_TIMESTAMP_INVALID")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        require(result.tzinfo is not None and result.utcoffset().total_seconds() == 0,
                "EVIDENCE_TIMESTAMP_INVALID")
        return result
    except Exception:
        raise EvidenceBlocked("EVIDENCE_TIMESTAMP_INVALID") from None


def validate_archive(meta: dict, archive: bytes, *, artifact_id: int, expected_digest: str,
                     expected_name: str, source: str, run_id: int, repository_id: int,
                     members: frozenset[str]) -> dict[str, bytes]:
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
                        and (stat.S_IFMT(mode) in (0, stat.S_IFREG))
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


class NativeEvidence:
    """Current canonical main run, fixed repository and same-run producer jobs."""
    def __init__(self, environ: dict[str, str], deadline: float, *, client=None):
        require(environ.get("GITHUB_ACTIONS") == "true" and environ.get("GITHUB_REPOSITORY") == REPOSITORY
                and environ.get("GITHUB_REF") == "refs/heads/main"
                and environ.get("GITHUB_WORKFLOW_REF") == REPOSITORY + "/" + WORKFLOW + "@refs/heads/main"
                and environ.get("GITHUB_EVENT_NAME") in {"push", "workflow_dispatch"}, "CANONICAL_CONTEXT_REQUIRED")
        self.source = environ.get("GITHUB_SHA", "")
        require(digest(self.source, 40), "CANONICAL_SOURCE_INVALID")
        for name in ("GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT", "GITHUB_REPOSITORY_ID"):
            require(type(environ.get(name)) is str and re.fullmatch(r"[1-9][0-9]{0,18}", environ[name]) is not None,
                    "CANONICAL_CONTEXT_INVALID")
        self.run_id, self.attempt, self.repository_id = (int(environ[name]) for name in
            ("GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT", "GITHUB_REPOSITORY_ID"))
        self.event = environ["GITHUB_EVENT_NAME"]
        self.executing_job = environ.get("GITHUB_JOB")
        self.token = environ.get("GH_TOKEN", "")
        require(type(self.token) is str and bool(self.token) and not any(c.isspace() for c in self.token),
                "GITHUB_READ_CREDENTIAL_REQUIRED")
        self.deadline = deadline
        if client is None:
            import httpx
            client = httpx.Client(timeout=20, follow_redirects=False, trust_env=False)
        self.client = client
        self.jobs = {}
        self.started = None
        self.run = None

    def budget(self):
        require(time.monotonic() < self.deadline, "NATIVE_EVIDENCE_DEADLINE")

    def request(self, path: str) -> dict:
        require(path.startswith("/repos/" + REPOSITORY + "/") and "#" not in path,
                "GITHUB_READ_SCOPE_INVALID")
        self.budget()
        try:
            with self.client.stream("GET", API + path, headers={"Authorization": "Bearer " + self.token,
                    "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}) as response:
                require(response.status_code == 200, "GITHUB_READ_UNAVAILABLE")
                data = bytearray()
                for chunk in response.iter_bytes(chunk_size=8192):
                    self.budget()
                    require(len(data) + len(chunk) <= MAX_JSON, "GITHUB_READ_BYTE_BOUND")
                    data.extend(chunk)
            self.budget()
            return strict(bytes(data))
        except EvidenceBlocked:
            raise
        except Exception:
            raise EvidenceBlocked("GITHUB_READ_UNAVAILABLE") from None

    def require_current_main(self) -> None:
        branch = self.request(f"/repos/{REPOSITORY}/branches/main")
        require(branch.get("name") == "main" and branch.get("protected") is True
                and type(branch.get("commit")) is dict and branch["commit"].get("sha") == self.source,
                "PROTECTED_SOURCE_NO_LONGER_CURRENT")

    def observe_run(self) -> None:
        run = self.request(f"/repos/{REPOSITORY}/actions/runs/{self.run_id}/attempts/{self.attempt}")
        require(run.get("id") == self.run_id and run.get("run_attempt") == self.attempt
                and run.get("path") == WORKFLOW and run.get("event") == self.event
                and run.get("head_sha") == self.source and run.get("head_branch") == "main"
                and run.get("repository", {}).get("id") == self.repository_id
                and run.get("repository", {}).get("full_name") == REPOSITORY
                and run.get("head_repository", {}).get("id") == self.repository_id,
                "CANONICAL_RUN_UNQUALIFIED")
        self.started = timestamp(run.get("run_started_at"))
        self.run = run
        require(self.started <= datetime.now(timezone.utc), "CANONICAL_RUN_TIME_INVALID")
        listing = self.request(f"/repos/{REPOSITORY}/actions/runs/{self.run_id}/attempts/{self.attempt}/jobs?per_page=100")
        values = listing.get("jobs")
        require(type(values) is list and type(listing.get("total_count")) is int
                and listing["total_count"] == len(values) and 1 <= len(values) <= 100, "CANONICAL_JOB_CENSUS_INCOMPLETE")
        self.jobs = {}
        for value in values:
            require(type(value) is dict and type(value.get("name")) is str
                    and value["name"] not in self.jobs and value.get("run_id") == self.run_id
                    and value.get("run_attempt") == self.attempt and value.get("head_sha") == self.source
                    and type(value.get("id")) is int and value["id"] > 0, "CANONICAL_JOB_IDENTITY_INVALID")
            self.jobs[value["name"]] = value
        self.require_current_main()

    def require_active_acquisition(self) -> None:
        """Acquisition can act only in its live native job; fetch remains read-only."""
        require(self.executing_job == ACQUISITION_JOB_KEY, "CANONICAL_ACQUISITION_JOB_REQUIRED")
        require(type(self.run) is dict and self.run.get("status") == "in_progress"
                and self.run.get("conclusion") is None, "CANONICAL_ACQUISITION_RUN_NOT_ACTIVE")
        job = self.jobs.get(ACQUISITION_JOB)
        require(type(job) is dict and job.get("status") == "in_progress" and job.get("conclusion") is None
                and job.get("completed_at") is None, "CANONICAL_ACQUISITION_JOB_NOT_ACTIVE")
        require(self.started is not None and self.started <= timestamp(job.get("started_at"))
                <= datetime.now(timezone.utc), "CANONICAL_ACQUISITION_JOB_TIME_INVALID")

    def source_context(self, source_receipt: bytes, job_name: str) -> dict:
        receipt = strict(source_receipt, MAX_MEMBER)
        require(receipt.get("schema") == "szl.hf-main-ownership/v1" and receipt.get("repository") == REPOSITORY
                and receipt.get("branch") == "main" and receipt.get("expected_sha") == self.source
                and receipt.get("observed_main_sha") == self.source and receipt.get("status") == "OWNED"
                and receipt.get("source_verified") is True and receipt.get("publish") is True
                and receipt.get("external_writes_performed") is False and receipt.get("secret_values_recorded") is False,
                "CANONICAL_SOURCE_RECEIPT_UNQUALIFIED")
        require(job_name in self.jobs, "CANONICAL_JOB_UNAVAILABLE")
        return {"repository": REPOSITORY, "ref": "refs/heads/main", "revision": self.source,
                "workflow_path": WORKFLOW, "run_id": self.run_id, "run_attempt": self.attempt,
                "job_id": self.jobs[job_name]["id"], "event_name": self.event,
                "source_admission_state": "VERIFIED", "source_admission_sha256": hashlib.sha256(source_receipt).hexdigest()}

    def artifact(self, artifact_id: int, archive_digest: str, *, name: str,
                 job_name: str, members: frozenset[str]) -> dict[str, bytes]:
        require(type(artifact_id) is int and artifact_id > 0 and digest(archive_digest), "ARTIFACT_SELECTOR_INVALID")
        require(job_name in self.jobs and self.jobs[job_name].get("status") == "completed"
                and self.jobs[job_name].get("conclusion") == "success", "ARTIFACT_PRODUCER_UNQUALIFIED")
        meta = self.request(f"/repos/{REPOSITORY}/actions/artifacts/{artifact_id}")
        require(self.started is not None and self.started <= timestamp(meta.get("created_at"))
                <= timestamp(self.jobs[job_name].get("completed_at")), "ARTIFACT_ATTEMPT_TIME_MISMATCH")
        self.budget()
        try:
            with self.client.stream("GET", f"{API}/repos/{REPOSITORY}/actions/artifacts/{artifact_id}/zip",
                    headers={"Authorization": "Bearer " + self.token, "Accept": "application/vnd.github+json"}) as response:
                require(response.status_code == 302, "ARTIFACT_DOWNLOAD_REDIRECT_REQUIRED")
                location = response.headers.get("location", "")
            parsed = urlsplit(location)
            host = parsed.hostname or ""
            require(parsed.scheme == "https" and parsed.port in (None, 443) and not parsed.username
                    and not parsed.password and not parsed.fragment and len(location) <= 16384
                    and (host.endswith(".blob.core.windows.net") or host.endswith(".actions.githubusercontent.com")),
                    "ARTIFACT_DOWNLOAD_DESTINATION_INVALID")
            # The signed object request deliberately carries no GitHub header.
            with self.client.stream("GET", location, headers={}) as response:
                require(response.status_code == 200, "ARTIFACT_DOWNLOAD_UNAVAILABLE")
                archive = bytearray()
                for chunk in response.iter_bytes(chunk_size=8192):
                    self.budget()
                    require(len(archive) + len(chunk) <= MAX_ARCHIVE, "ARTIFACT_DOWNLOAD_BYTE_BOUND")
                    archive.extend(chunk)
            self.budget()
        except EvidenceBlocked:
            raise
        except Exception:
            raise EvidenceBlocked("ARTIFACT_DOWNLOAD_UNAVAILABLE") from None
        return validate_archive(meta, bytes(archive), artifact_id=artifact_id, expected_digest=archive_digest,
            expected_name=name, source=self.source, run_id=self.run_id, repository_id=self.repository_id, members=members)
