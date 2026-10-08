#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Provenance: exact Finance Hub projection bytes, not runtime or authority.

Construction is pure and DECLARED. The separate bounded public readback checks
the seven owned files and this record at one immutable Hub revision. It never
reads credentials, follows redirects, signs, executes payloads, or changes Hub
state. Retained Hub-only files and the old manifest are explicitly out of scope.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import http.client
import json
import math
import re
import ssl
import time

REPOSITORY = "SZLHOLDINGS/finance"
SOURCE_REPOSITORY = "szl-holdings/a11oy"
MANIFEST_PATH = "finance-projection-manifest.json"
LEGACY_MANIFEST_PATH = "szl-artifact-manifest.json"
OWNED_PATHS = ("app.py", "Dockerfile", "requirements.txt", "config.json",
               "index.html", "panels.html", "README.md")
MAX_BYTES = {name: 1_000_000 if name in ("app.py", "index.html", "panels.html")
             else 64_000 for name in (*OWNED_PATHS, MANIFEST_PATH)}
SCHEMA = "szl.finance.source-projection-manifest/v1"
SHA40 = re.compile(r"[0-9a-f]{40}")
FAILURE_CODES = frozenset(("DUPLICATE_JSON_KEY", "NONFINITE_JSON", "INVALID_JSON",
    "INVALID_SOURCE_IDENTITY", "INVALID_OWNED_PATHS", "INVALID_PAYLOAD_SIZE_OR_TYPE",
    "INVALID_PAYLOAD_ENCODING", "CONFIGURATION_BINDING_MISMATCH", "LEGACY_ARTIFACT_IDENTITY_MISMATCH",
    "HTML_BINDING_MISMATCH", "DESTINATION_DENIED", "ENCODED_RESPONSE_DENIED", "RESPONSE_TOO_LARGE",
    "RESPONSE_DEADLINE", "INVALID_HUB_REVISION", "AUTHORITY_UNAVAILABLE", "FILE_UNAVAILABLE",
    "PROJECTION_BYTES_MISMATCH"))
LEGACY_DIGEST = {
    "algorithm": "sha256-over-8-byte-big-endian-length-prefixed-utf8-slots",
    "slots": ["app.py", "Dockerfile", "requirements.txt", "index.html",
              "panels.html", "README.md", "forge-json-null"],
    "excludes": ["config.json", MANIFEST_PATH],
    "scope": "Existing renderer identity; not the complete published file table.",
}


class ProjectionError(ValueError):
    """Only fixed non-secret codes may leave this boundary."""


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def _revision(value) -> bool:
    return isinstance(value, str) and SHA40.fullmatch(value) is not None and value != "0" * 40


def _strict_json(raw: bytes):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ProjectionError("DUPLICATE_JSON_KEY")
            result[key] = value
        return result
    def invalid(_):
        raise ProjectionError("NONFINITE_JSON")
    def finite(value):
        parsed = float(value)
        if not math.isfinite(parsed):
            raise ProjectionError("NONFINITE_JSON")
        return parsed
    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid, parse_float=finite)
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        raise ProjectionError("INVALID_JSON") from None


def manifest_bytes(files: dict[str, bytes], revision: str, run_id: int) -> bytes:
    """Bind the exact seven upload payloads, including configuration, without self-hash."""
    if not _revision(revision) or type(run_id) is not int or run_id <= 0:
        raise ProjectionError("INVALID_SOURCE_IDENTITY")
    if not isinstance(files, dict) or set(files) != set(OWNED_PATHS):
        raise ProjectionError("INVALID_OWNED_PATHS")
    for name, raw in files.items():
        if not isinstance(raw, bytes) or not raw or len(raw) > MAX_BYTES[name]:
            raise ProjectionError("INVALID_PAYLOAD_SIZE_OR_TYPE")
        try:
            raw.decode("utf-8")
        except UnicodeError:
            raise ProjectionError("INVALID_PAYLOAD_ENCODING") from None
    config = _strict_json(files["config.json"])
    if (not isinstance(config, dict) or config.get("slug") != "finance"
            or config.get("source_repository") != SOURCE_REPOSITORY
            or config.get("source_revision") != revision
            or type(config.get("workflow_run_id")) is not int
            or config["workflow_run_id"] != run_id
            or config.get("hf_repository") != REPOSITORY
            or config.get("public_experience") != "4.0.0"
            or config.get("forge") is not None):
        raise ProjectionError("CONFIGURATION_BINDING_MISMATCH")
    legacy = hashlib.sha256()
    for name in LEGACY_DIGEST["slots"]:
        raw = b"null" if name == "forge-json-null" else files[name]
        legacy.update(len(raw).to_bytes(8, "big"))
        legacy.update(raw)
    if config.get("artifact_set_sha256") != legacy.hexdigest():
        raise ProjectionError("LEGACY_ARTIFACT_IDENTITY_MISMATCH")
    for name, field in (("index.html", "landing_sha256"), ("panels.html", "panels_sha256")):
        if config.get(field) != hashlib.sha256(files[name]).hexdigest():
            raise ProjectionError("HTML_BINDING_MISMATCH")
    table = [{"path": name, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
             for name, raw in sorted(files.items())]
    body = {
        "schema": SCHEMA, "evidence_class": "DECLARED",
        "source_repository": SOURCE_REPOSITORY, "source_revision": revision,
        "workflow_run_id": run_id, "hf_repository": REPOSITORY,
        "public_experience": config["public_experience"],
        "artifact_set_sha256": config["artifact_set_sha256"],
        "artifact_set_semantics": LEGACY_DIGEST,
        "file_table_sha256": hashlib.sha256(canonical(table)).hexdigest(),
        "file_table_semantics": "SHA-256 of sorted compact UTF-8 JSON file table; includes config.json.",
        "files": table,
        "self_hash_excluded": MANIFEST_PATH,
        "hub_revision_binding": "The immutable Hub revision is recorded by the separate readback witness, not inside its own commit payload.",
        "legacy_manifest": {"path": LEGACY_MANIFEST_PATH,
            "writer_policy": "Not written or deleted by this publisher.", "retained_bytes_verified": False,
            "current_projection_attestation": False, "qualification": "UNKNOWN"},
        "scope": "Seven owned uploaded source-projection files only; unrelated retained Hub files are not attested.",
        "runtime_inclusion_verified": False, "signature_verified": False,
        "authority_established": False, "execution_enabled": False,
    }
    return canonical(body) + b"\n"


def read_public(revision: str, path: str, limit: int) -> tuple[int, bytes]:
    """One fixed immutable cache-route GET; no fallback, proxies, credentials or redirects.

    Endpoint availability is established only by actual readback, not by this
    source declaration. A non-200 response is returned without reading its body.
    Socket timeouts bound idle I/O, not absolute DNS/connect/header wall time.
    Body chunks and the completed observation have separate elapsed-time gates.
    """
    if (not _revision(revision) or path not in MAX_BYTES
            or type(limit) is not int or limit != MAX_BYTES[path]):
        raise ProjectionError("DESTINATION_DENIED")
    target = f"/api/resolve-cache/spaces/{REPOSITORY}/{revision}/{path}"
    connection = http.client.HTTPSConnection("huggingface.co", timeout=4,
                                            context=ssl.create_default_context())
    connection.set_debuglevel(0)
    try:
        connection.request("GET", target, headers={"Accept-Encoding": "identity",
            "Cache-Control": "no-cache", "User-Agent": "SZL-Finance-Projection-Witness/1.0"})
        response = connection.getresponse()
        if response.status != 200:
            return response.status, b""
        if (response.getheader("Content-Encoding") or "identity").lower() not in ("", "identity"):
            raise ProjectionError("ENCODED_RESPONSE_DENIED")
        declared = response.getheader("Content-Length")
        if declared and (not declared.isdigit() or int(declared) > limit):
            raise ProjectionError("RESPONSE_TOO_LARGE")
        chunks, size = [], 0
        deadline = time.monotonic() + 4
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ProjectionError("RESPONSE_DEADLINE")
            if connection.sock is not None:
                connection.sock.settimeout(min(4, remaining))
            chunk = response.read1(min(65_536, limit + 1 - size))
            if time.monotonic() >= deadline:
                raise ProjectionError("RESPONSE_DEADLINE")
            if not chunk:
                break
            size += len(chunk)
            if size > limit:
                raise ProjectionError("RESPONSE_TOO_LARGE")
            chunks.append(chunk)
        return 200, b"".join(chunks)
    finally:
        connection.close()


def observe_projection(files: dict[str, bytes], revision: str, run_id: int,
                       hf_revision: str, *, request=read_public) -> dict:
    """Require expected manifest AND every owned payload at the same immutable revision."""
    result = {"schema": "szl.finance.source-projection-witness/v1",
        "observed_at": datetime.now(timezone.utc).isoformat(), "evidence_class": "UNAVAILABLE",
        "complete": False, "source_repository": SOURCE_REPOSITORY,
        "source_revision": revision if _revision(revision) else None,
        "workflow_run_id": run_id if type(run_id) is int and run_id > 0 else None,
        "hf_repository": REPOSITORY, "hf_revision": hf_revision if _revision(hf_revision) else None,
        "credentials_sent": False, "provider_mutations": 0, "signature_verified": False,
        "runtime_inclusion_verified": False, "authority_established": False,
        "execution_enabled": False, "terminal_authority_failure": False, "files": []}
    try:
        manifest = manifest_bytes(files, revision, run_id)
        if not _revision(hf_revision):
            raise ProjectionError("INVALID_HUB_REVISION")
        expected = {MANIFEST_PATH: manifest, **files}
        deadline = time.monotonic() + 40
        for path, raw in expected.items():
            if time.monotonic() >= deadline:
                raise ProjectionError("RESPONSE_DEADLINE")
            status, observed = request(hf_revision, path, MAX_BYTES[path])
            row = {"path": path, "http_status": status if type(status) is int else None,
                   "accepted": False}
            result["files"].append(row)
            # Authority denial remains terminal even when its response arrives
            # after the elapsed-time gate. It must not be retried as a timeout.
            if type(status) is int and status in (401, 403):
                result["terminal_authority_failure"] = True
                raise ProjectionError("AUTHORITY_UNAVAILABLE")
            if time.monotonic() >= deadline:
                raise ProjectionError("RESPONSE_DEADLINE")
            if type(status) is not int or status != 200:
                raise ProjectionError("FILE_UNAVAILABLE")
            if not isinstance(observed, bytes) or len(observed) > MAX_BYTES[path]:
                raise ProjectionError("RESPONSE_TOO_LARGE")
            row.update(bytes=len(observed), sha256=hashlib.sha256(observed).hexdigest())
            if observed != raw:
                raise ProjectionError("PROJECTION_BYTES_MISMATCH")
            row["accepted"] = True
        manifest_sha256 = hashlib.sha256(manifest).hexdigest()
        file_table_sha256 = _strict_json(manifest)["file_table_sha256"]
        # Digest and JSON work are part of the completed observation, including
        # the last row. A timely final response must not admit a late result.
        if time.monotonic() >= deadline:
            raise ProjectionError("RESPONSE_DEADLINE")
        result.update(complete=True, evidence_class="MEASURED",
                      manifest_sha256=manifest_sha256,
                      file_table_sha256=file_table_sha256)
    except ProjectionError as exc:
        code = str(exc)
        result["failure_code"] = code if code in FAILURE_CODES else "INVALID_RESPONSE"
    except Exception:
        result["failure_code"] = "TRANSPORT_UNAVAILABLE"
    return result


def witness_matches(witness: dict, files: dict[str, bytes], revision: str,
                    run_id: int, hf_revision: str) -> bool:
    """Admission binds every witness row and digest, not just its complete flag."""
    try:
        manifest = manifest_bytes(files, revision, run_id)
        if not _revision(hf_revision) or not isinstance(witness, dict):
            return False
        expected_fields = {"schema": "szl.finance.source-projection-witness/v1",
            "evidence_class": "MEASURED", "complete": True,
            "source_repository": SOURCE_REPOSITORY, "source_revision": revision,
            "workflow_run_id": run_id, "hf_repository": REPOSITORY, "hf_revision": hf_revision,
            "credentials_sent": False, "provider_mutations": 0, "signature_verified": False,
            "runtime_inclusion_verified": False, "authority_established": False,
            "execution_enabled": False, "terminal_authority_failure": False,
            "manifest_sha256": hashlib.sha256(manifest).hexdigest(),
            "file_table_sha256": _strict_json(manifest)["file_table_sha256"]}
        if any(type(witness.get(key)) is not type(value) or witness.get(key) != value
               for key, value in expected_fields.items()):
            return False
        expected = {MANIFEST_PATH: manifest, **files}
        rows = witness.get("files")
        if not isinstance(rows, list) or len(rows) != len(expected):
            return False
        seen = set()
        for row in rows:
            if not isinstance(row, dict):
                return False
            path = row.get("path")
            if not isinstance(path, str) or path not in expected or path in seen:
                return False
            seen.add(path)
            raw = expected[path]
            if (row.get("accepted") is not True or type(row.get("http_status")) is not int
                    or row["http_status"] != 200 or type(row.get("bytes")) is not int
                    or row["bytes"] != len(raw)
                    or row.get("sha256") != hashlib.sha256(raw).hexdigest()):
                return False
        return seen == set(expected) and "failure_code" not in witness
    except (ProjectionError, TypeError, ValueError):
        return False
