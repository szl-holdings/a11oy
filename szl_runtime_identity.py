# SPDX-License-Identifier: Apache-2.0
"""Provenance: authenticated publication plus process-local source COPY checks.

The canonical GitHub workflow reports the HF commit (REPORTED). This process
hashes its /app source files (MEASURED), verifies GitHub's OIDC attestation, and
latches their binding once per boot. This is not a provider/VM/image/dependency
attestation, an independent execution witness, or authorization. No GET starts
verification or writes a receipt. Trust includes the OS and this verifier.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import tempfile
import threading
import time

from szl_readiness_artifact import (EvidenceBlocked, Transport, REPOSITORY_ID, digest,
                                    require, strict, validate_archive)

ROOT = Path(__file__).resolve().parent
MARKER = ".szl-runtime-marker.json"
REPOSITORY = "szl-holdings/a11oy"
TARGET = "SZLHOLDINGS/a11oy"
WORKFLOW = ".github/workflows/hf-sync.yml"
SIGNER = "szl-holdings/.github/.github/workflows/reusable-hf-deploy.yml"
METHOD = "GITHUB_ATTESTED_SOURCE_COPY_SET"
REQUIRED = {"observer_runtime.py", "szl_runtime_identity.py", "serve.py", "gdw_runtime.py",
            ".github/scripts/hf-sync.yml"}
MAX_FILE = 32 * 1024 * 1024
MAX_TOTAL = 256 * 1024 * 1024


def regular(root, relative, limit):
    require(type(relative) is str and 0 < len(relative) <= 512 and "\\" not in relative,
            "RUNTIME_PATH_INVALID")
    parts = PurePosixPath(relative).parts
    require(parts and not PurePosixPath(relative).is_absolute()
            and all(x not in ("", ".", "..") and ":" not in x for x in parts)
            and "/".join(parts) == relative, "RUNTIME_PATH_INVALID")
    path = root
    for part in parts:
        path = path / part
        require(not path.is_symlink() and not (getattr(path.lstat(), "st_file_attributes", 0) & 0x400),
                "RUNTIME_SYMLINK_FORBIDDEN")
    require(path.resolve().is_relative_to(root.resolve()), "RUNTIME_PATH_ESCAPE")
    descriptor = directory = None
    try:
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        if os.open in os.supports_dir_fd:
            directory = os.open(root, flags | os.O_DIRECTORY)
            for part in parts[:-1]:
                child = os.open(part, flags | os.O_DIRECTORY, dir_fd=directory)
                os.close(directory)
                directory = child
            descriptor = os.open(parts[-1], flags, dir_fd=directory)
        else:
            descriptor = os.open(path, flags)
        before = os.fstat(descriptor)
        require(stat.S_ISREG(before.st_mode), "RUNTIME_REGULAR_FILE_REQUIRED")
        require(before.st_size <= limit, "RUNTIME_FILE_TOO_LARGE")
        data = bytearray()
        while len(data) <= limit:
            chunk = os.read(descriptor, min(65536, limit + 1 - len(data)))
            if not chunk:
                break
            data.extend(chunk)
        require(len(data) <= limit, "RUNTIME_FILE_TOO_LARGE")
        after = os.fstat(descriptor)
        require((before.st_size, before.st_mtime_ns, before.st_ctime_ns)
                == (after.st_size, after.st_mtime_ns, after.st_ctime_ns), "RUNTIME_FILE_CHANGED_DURING_READ")
        return bytes(data)
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if directory is not None:
            os.close(directory)


def marker_document(raw):
    marker = strict(raw, 1024 * 1024)
    require(set(marker) == {"schema", "source_repository", "source_sha", "target", "run_id",
                           "run_attempt", "publisher_sha", "nonce", "catalog"}, "RUNTIME_MARKER_FIELDS")
    require(marker["schema"] == "szl.runtime-source-marker/v1"
            and marker["source_repository"] == REPOSITORY and marker["target"] == TARGET,
            "RUNTIME_TARGET_MISMATCH")
    require(digest(marker["source_sha"], 40) and digest(marker["publisher_sha"], 40)
            and digest(marker["nonce"]) and type(marker["run_id"]) is int and marker["run_id"] > 0
            and type(marker["run_attempt"]) is int and marker["run_attempt"] > 0,
            "RUNTIME_SELECTOR_INVALID")
    catalog = marker["catalog"]
    require(type(catalog) is dict and REQUIRED.issubset(catalog) and len(catalog) <= 10000,
            "RUNTIME_CATALOG_INCOMPLETE")
    for name, meta in catalog.items():
        require(type(name) is str and type(meta) is dict and set(meta) == {"source_path", "sha256", "size"}
                and type(meta["source_path"]) is str and digest(meta["sha256"])
                and type(meta["size"]) is int and 0 <= meta["size"] <= MAX_FILE,
                "RUNTIME_CATALOG_INVALID")
    return marker


def measure_catalog(root, marker):
    total = 0
    for name, meta in marker["catalog"].items():
        total += meta["size"]
        require(total <= MAX_TOTAL, "RUNTIME_CATALOG_TOO_LARGE")
        raw = regular(root, name, min(MAX_FILE, meta["size"]))
        require(len(raw) == meta["size"] and hashlib.sha256(raw).hexdigest() == meta["sha256"],
                "RUNTIME_SOURCE_BYTES_MISMATCH")


def pinned_publisher(root):
    text = regular(root, ".github/scripts/hf-sync.yml", 256 * 1024).decode("utf-8")
    matches = re.findall(r"(?m)^\s*uses:\s*" + re.escape(SIGNER) + r"@([0-9a-f]{40})\s*$", text)
    require(len(matches) == 1, "RUNTIME_PUBLISHER_PIN_UNAVAILABLE")
    return matches[0]


def verify_attestation(raw, marker, token):
    """Use the installed GitHub verifier; never accept caller JSON as a verdict."""
    env = {k: v for k, v in os.environ.items() if k in ("PATH", "SYSTEMROOT", "WINDIR", "TMP", "TEMP")}
    env.update(GH_TOKEN=token, GH_HOST="github.com", GH_PROMPT_DISABLED="1")
    with tempfile.TemporaryDirectory(prefix="a11oy-source-verify-") as tmp:
        # Isolate configuration/cache. No inherited GH_CONFIG_DIR or arbitrary
        # trust roots/proxy variables can select a different verification policy.
        env.update(HOME=tmp, USERPROFILE=tmp, GH_CONFIG_DIR=tmp, XDG_CACHE_HOME=tmp)
        path = Path(tmp) / "hf-runtime-binding.json"
        path.write_bytes(raw)
        command = ["gh", "attestation", "verify", str(path), "--repo", REPOSITORY,
                   "--signer-workflow", SIGNER, "--signer-digest", marker["publisher_sha"],
                   "--source-digest", marker["source_sha"], "--source-ref", "refs/heads/main",
                   "--cert-oidc-issuer", "https://token.actions.githubusercontent.com",
                   "--deny-self-hosted-runners", "--hostname", "github.com", "--format", "json",
                   "--limit", "1"]
        try:
            with tempfile.TemporaryFile() as output:
                result = subprocess.run(command, env=env, cwd=tmp, stdin=subprocess.DEVNULL,
                                        stdout=output, stderr=subprocess.DEVNULL, timeout=45, check=False)
                require(result.returncode == 0, "RUNTIME_ATTESTATION_REJECTED")
                output.seek(0)
                raw_result = output.read(2 * 1024 * 1024 + 1)
        except (OSError, subprocess.TimeoutExpired):
            raise EvidenceBlocked("RUNTIME_ATTESTATION_VERIFIER_UNAVAILABLE") from None
        require(len(raw_result) <= 2 * 1024 * 1024, "RUNTIME_VERIFIER_OUTPUT_TOO_LARGE")
        results = strict(b'{"results":' + raw_result + b'}', 2 * 1024 * 1024 + 64)["results"]
        require(type(results) is list and len(results) == 1 and type(results[0]) is dict,
                "RUNTIME_VERIFIER_OUTPUT_INVALID")
        verified = results[0].get("verificationResult")
        require(type(verified) is dict and type(verified.get("signature")) is dict,
                "RUNTIME_VERIFIER_OUTPUT_INVALID")
        cert = verified["signature"].get("certificate")
        expected_run = (f"https://github.com/{REPOSITORY}/actions/runs/{marker['run_id']}"
                        f"/attempts/{marker['run_attempt']}")
        # This certificate field is OIDC-derived. Uploaded artifact metadata or
        # a caller-controlled SLSA predicate cannot prove who signed this run.
        require(type(cert) is dict and cert.get("runInvocationURI") == expected_run,
                "RUNTIME_ATTESTATION_INVOCATION_MISMATCH")


def fetch_binding(transport, marker):
    run = transport.json(f"/actions/runs/{marker['run_id']}/attempts/{marker['run_attempt']}")
    require(run.get("id") == marker["run_id"] and run.get("run_attempt") == marker["run_attempt"]
            and run.get("head_sha") == marker["source_sha"] and run.get("head_branch") == "main"
            and run.get("path") == WORKFLOW and run.get("event") in ("push", "workflow_dispatch")
            and run.get("repository", {}).get("id") == REPOSITORY_ID
            and run.get("head_repository", {}).get("id") == REPOSITORY_ID,
            "RUNTIME_PUBLISHER_RUN_MISMATCH")
    listing = transport.json(f"/actions/runs/{marker['run_id']}/artifacts?per_page=100")
    artifacts = listing.get("artifacts")
    require(type(artifacts) is list and listing.get("total_count") == len(artifacts)
            and len(artifacts) <= 100 and all(type(a) is dict for a in artifacts),
            "RUNTIME_ARTIFACT_CENSUS_INCOMPLETE")
    name = f"hf-runtime-identity-{marker['run_id']}-{marker['run_attempt']}"
    selected = [a for a in artifacts if a.get("name") == name]
    require(len(selected) == 1, "RUNTIME_BINDING_ARTIFACT_UNAVAILABLE")
    artifact_id = selected[0].get("id")
    require(type(artifact_id) is int and artifact_id > 0, "RUNTIME_ARTIFACT_ID_INVALID")
    meta = transport.json(f"/actions/artifacts/{artifact_id}")
    archive_digest = str(meta.get("digest", "")).removeprefix("sha256:")
    return validate_archive(meta, transport.archive(artifact_id), artifact_id=artifact_id,
        expected_digest=archive_digest, expected_name=name, source=marker["source_sha"],
        run_id=marker["run_id"], repository_id=REPOSITORY_ID,
        members={"hf-runtime-binding.json"})["hf-runtime-binding.json"]


def validate_binding(raw, marker):
    body = strict(raw, 1024 * 1024)
    require(set(body) == {"schema", "marker", "hf_revision", "scope", "image_attestation",
                          "hardware_attestation", "execution_authority"}, "RUNTIME_BINDING_FIELDS")
    require(body["schema"] == "szl.runtime-source-binding/v1" and body["marker"] == marker
            and digest(body["hf_revision"], 40) and body["scope"] == "FINAL_APP_SOURCE_COPY_FILES"
            and body["image_attestation"] is False and body["hardware_attestation"] is False
            and body["execution_authority"] is False, "RUNTIME_PUBLICATION_BINDING_MISMATCH")
    return body["hf_revision"]


@dataclass(frozen=True)
class VerifiedSourceIdentity:
    source_revision: str
    hf_revision: str
    runtime_boot_id: str
    marker_sha256: str
    binding_sha256: str
    method: str = METHOD
    publication_evidence: str = "REPORTED"
    local_bytes_evidence: str = "MEASURED"


class ProcessIdentity:
    """Startup-owned, one-success latch; no refresh can replace its identity."""
    def __init__(self, boot_id, *, root=ROOT, marker_root=Path("/tmp"), environ=None):
        env = os.environ if environ is None else environ
        self.root, self.boot_id, self.marker_root = Path(root), boot_id, Path(marker_root)
        self._token = str(env.get("SZL_READINESS_GH_TOKEN") or "")
        self._source = str(env.get("SZL_GIT_SHA") or "")
        self._stop = threading.Event()
        self._lock = threading.RLock()
        self._thread = None
        self._verified = None
        self._poisoned = False
        self._raw = None
        self.error = "RUNTIME_IDENTITY_NOT_VERIFIED"
        try:
            raw = regular(self.marker_root, MARKER, 1024 * 1024)
            marker = marker_document(raw)
            require(marker["source_sha"] == self._source and bool(self.boot_id), "RUNTIME_SOURCE_MISMATCH")
            require(marker["publisher_sha"] == pinned_publisher(self.root), "RUNTIME_PUBLISHER_PIN_MISMATCH")
            measure_catalog(self.root, marker)
            self._raw = raw  # immutable captured bytes; never reread the selector from env
        except Exception as exc:
            self.error = safe_error(exc)

    def verify_once(self):
        require(self._raw is not None, self.error)
        with self._lock:
            require(not self._poisoned, "RUNTIME_IDENTITY_DRIFT_LATCHED")
            if self._verified is not None:
                return self._verified
        require(bool(self._token), "RUNTIME_GITHUB_READ_CREDENTIAL_REQUIRED")
        marker = marker_document(self._raw)
        transport = Transport(self._token, self._stop)
        try:
            raw = fetch_binding(transport, marker)
        finally:
            transport.close()
        revision = validate_binding(raw, marker)
        verify_attestation(raw, marker, self._token)
        with self._lock:
            require(not self._poisoned, "RUNTIME_IDENTITY_DRIFT_LATCHED")
            if self._verified is not None:
                return self._verified
            try:
                measure_catalog(self.root, marker)
                require(regular(self.marker_root, MARKER, 1024 * 1024) == self._raw, "RUNTIME_MARKER_CHANGED")
            except Exception as exc:
                self._poisoned = True
                self.error = safe_error(exc)
                raise EvidenceBlocked(self.error) from None
            self._verified = VerifiedSourceIdentity(marker["source_sha"], revision, self.boot_id,
                hashlib.sha256(self._raw).hexdigest(), hashlib.sha256(raw).hexdigest())
            self.error = None
            return self._verified

    def admitted(self):
        """Read-only admission: reject local drift, without network or signing."""
        with self._lock:
            require(self._verified is not None, "IMMUTABLE_PROCESS_HF_REVISION_UNAVAILABLE")
            try:
                require(regular(self.marker_root, MARKER, 1024 * 1024) == self._raw, "RUNTIME_MARKER_CHANGED")
                measure_catalog(self.root, marker_document(self._raw))
            except Exception as exc:
                self.error = safe_error(exc)
                self._verified = None
                self._poisoned = True
                raise EvidenceBlocked(self.error) from None
            return self._verified

    def start(self):
        if self._thread is not None or self._raw is None:
            return
        if not self._token:
            self.error = "RUNTIME_GITHUB_READ_CREDENTIAL_REQUIRED"
            return
        def worker():
            # A bounded startup window permits the artifact upload to race boot.
            # No HTTP read can start this worker or extend the window.
            deadline = time.monotonic() + 300
            while not self._stop.is_set() and time.monotonic() < deadline:
                try:
                    self.verify_once()
                    return
                except Exception as exc:
                    self.error = safe_error(exc)
                self._stop.wait(10)
        self._thread = threading.Thread(target=worker, name="runtime-source-identity", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    def snapshot(self):
        value = self._verified
        return {"status": "REPORTED" if value else "BLOCKED", "method": METHOD,
                "source_revision": value.source_revision if value else None,
                "hf_revision": value.hf_revision if value else None,
                "runtime_boot_id": self.boot_id, "error": self.error,
                "marker_sha256": value.marker_sha256 if value else None,
                "binding_sha256": value.binding_sha256 if value else None,
                "local_bytes_evidence": "MEASURED" if value else "UNAVAILABLE",
                "scope": "FINAL_APP_SOURCE_COPY_FILES", "hardware_attestation": False,
                "image_attestation": False, "execution_authority": False}


def safe_error(exc):
    code = str(exc)
    return code if re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}", code) else "RUNTIME_IDENTITY_UNAVAILABLE"
