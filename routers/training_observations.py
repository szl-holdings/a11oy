#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Restricted read-only projection of external training-observer reports.

Taxonomy: services/provenance. This is an observation input, not a state store,
training controller, receipt verifier, or publication/promotion authority.
The producer owns the file. Reads neither copy it nor refresh its evidence time.
"""
import hashlib
import json
import math
import os
import re
import stat
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

API = "/api/a11oy/v1/models/training-observations"
SCHEMA = "szl.training-observation-view/v1"
SOURCE_SCHEMA = "szl.training-observation/v1"
FILE_ENV = "A11OY_TRAINING_OBSERVATION_FILE"
MAX_BYTES = 1024 * 1024
MAX_CANDIDATES = 32
MAX_AGE_SECONDS = 660
MAX_INTEGER = 2**53 - 1
METHODS = {"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "TRACE", "CONNECT"}
AUTHORITY = {name: False for name in (
    "training", "inference", "publication", "promotion", "deletion", "toolExecution")}
HEADERS = {"Cache-Control": "private, no-store", "Pragma": "no-cache",
           "Vary": "Authorization, X-A11oy-Tenant", "X-Content-Type-Options": "nosniff",
           "Referrer-Policy": "no-referrer"}
REPO = re.compile(r"SZLHOLDINGS/[A-Za-z0-9][A-Za-z0-9._-]{0,159}\Z")
SHA = re.compile(r"[0-9a-f]{40}\Z")
DIGEST = re.compile(r"[0-9a-f]{64}\Z")
PRODUCER_STATES = frozenset({"UNAVAILABLE", "NO_CHECKPOINT_OBSERVED",
    "TARGET_CONTRACT_MISMATCH", "TERMINAL_STEP_OVERSHOOT", "CHECKPOINT_PROGRESS_OBSERVED",
    "TERMINAL_METADATA_PRESENT", "TARGET_CHECKPOINT_WITHOUT_FINAL_BUNDLE"})


class ObservationError(ValueError):
    """An input cannot support this bounded observation projection."""


def require(condition):
    if not condition:
        raise ObservationError("INVALID_OBSERVATION")


def integer(value, *, minimum=0):
    require(type(value) is int and minimum <= value <= MAX_INTEGER)
    return value


def timestamp(value):
    require(isinstance(value, str) and 0 < len(value) <= 64)
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    require(result.tzinfo is not None and result.utcoffset() is not None)
    return result.astimezone(timezone.utc)


def iso(value):
    return value.isoformat().replace("+00:00", "Z")


def decode(raw):
    require(type(raw) is bytes and 0 < len(raw) <= MAX_BYTES)

    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result)
            result[key] = value
        return result

    def finite(value):
        result = float(value)
        require(math.isfinite(result))
        return result

    def reject(_):
        raise ObservationError("INVALID_OBSERVATION")

    return json.loads(raw, object_pairs_hook=unique, parse_float=finite,
                      parse_constant=reject)


def _freshness(now, observed, source_observed, ttl):
    expires = min(observed, source_observed) + timedelta(seconds=ttl)
    state = ("CLOCK_SKEW" if max(observed, source_observed) > now else
             "STALE" if now >= expires else "OBSERVED")
    return state, expires


def project(raw, *, now):
    """Validate the producer contract and expose only allowlisted observations.

    The report's digest identifies bytes read here. Trainer integrity is a
    producer-reported result, not an independent check performed by this reader.
    """
    try:
        require(isinstance(now, datetime) and now.tzinfo is not None)
        now = now.astimezone(timezone.utc)
        value = decode(raw)
        require(type(value) is dict and value.get("schema") == SOURCE_SCHEMA)
        require(value.get("promotion_authorized") is False
                and value.get("training_complete_verified") is False)
        source_observed = timestamp(value["observed_at_utc"])
        started = timestamp(value["started_at_utc"])
        require(started <= source_observed)
        integer(value["cycle"], minimum=1)
        ttl = min(integer(value["stale_after_seconds"], minimum=1), MAX_AGE_SECONDS)
        candidates = value["candidates"]
        require(type(candidates) is list and 1 <= len(candidates) <= MAX_CANDIDATES)
        rows, seen = [], set()
        for item in candidates:
            require(type(item) is dict)
            identity, producer_state = item.get("repo"), item.get("state")
            require(isinstance(identity, str) and REPO.fullmatch(identity) is not None
                    and ".." not in identity and identity not in seen)
            seen.add(identity)
            require(producer_state in PRODUCER_STATES)
            for name in ("training_complete_verified", "promotion_authorized",
                         "trainer_process_liveness_verified"):
                require(item.get(name) is False)
            target = integer(item["target_steps"], minimum=1)
            observed = timestamp(item["observed_at_utc"])
            require(started <= observed <= source_observed)
            state, expires = _freshness(now, observed, source_observed, ttl)
            snapshot, trainer, provider = item.get("snapshot"), item.get("trainer_state"), item.get("provider")
            revision = step = global_step = max_steps = trainer_digest = ready = None
            final = {name: None for name in ("adapter", "config", "tokenizer")}
            integrity = "UNAVAILABLE"
            if snapshot is not None:
                require(type(snapshot) is dict and snapshot.get("id") == identity)
                require(snapshot.get("status") == "OBSERVED"
                        and type(snapshot.get("private")) is bool)
                revision = snapshot.get("revision")
                require(isinstance(revision, str) and SHA.fullmatch(revision) is not None)
                step = snapshot.get("latest_checkpoint")
                if step is not None:
                    integer(step)
                require(snapshot.get("artifact_integrity") == "NOT_VERIFIED_BY_METADATA"
                        and snapshot.get("training_complete") == "UNVERIFIED"
                        and snapshot.get("process_liveness_verified") is False
                        and snapshot.get("evaluation") == "NOT_ASSESSED")
                for name in final:
                    flag = snapshot.get("final_" + name)
                    require(type(flag) is bool)
                    final[name] = flag
            if trainer is not None:
                require(type(trainer) is dict and revision is not None and step is not None)
                global_step = integer(trainer["global_step"])
                max_steps = integer(trainer["max_steps"], minimum=1)
                trainer_digest = trainer.get("trainer_state_sha256")
                require(isinstance(trainer_digest, str) and DIGEST.fullmatch(trainer_digest) is not None
                        and trainer.get("integrity") == "PINNED_OBJECT_BYTES_VERIFIED"
                        and global_step == step)
                integrity = "PINNED_OBJECT_BYTES_VERIFIED"
            if producer_state == "NO_CHECKPOINT_OBSERVED":
                require(snapshot is not None and step is None and trainer is None)
            elif producer_state != "UNAVAILABLE":
                require(trainer is not None)
                derived = ("TARGET_CONTRACT_MISMATCH" if max_steps != target else
                           "TERMINAL_STEP_OVERSHOOT" if step > target else
                           "CHECKPOINT_PROGRESS_OBSERVED" if step < target else
                           "TERMINAL_METADATA_PRESENT" if all(final.values()) else
                           "TARGET_CHECKPOINT_WITHOUT_FINAL_BUNDLE")
                require(producer_state == derived)
            if provider is not None:
                require(type(provider) is dict and provider.get("state") in ("OBSERVED", "UNAVAILABLE")
                        and provider.get("trainer_process_liveness_verified") is False)
                if provider["state"] == "OBSERVED":
                    count = integer(provider["instance_count"])
                    ready = integer(provider["ready_count"])
                    require(ready <= count)
            if producer_state == "UNAVAILABLE" and state == "OBSERVED":
                state = "UNAVAILABLE"
            rows.append({"id": identity, "producerState": producer_state, "state": state,
                "observedAt": iso(observed), "expiresAt": iso(expires),
                "ageSeconds": round((now - observed).total_seconds(), 3),
                "hubRevision": revision, "checkpointStep": step, "targetSteps": target,
                "trainerGlobalStep": global_step, "trainerMaxSteps": max_steps,
                "trainerStateSha256": trainer_digest, "trainerStateIntegrityReported": integrity,
                "finalFiles": final, "providerReadyCount": ready,
                "trainingCompleteVerified": False, "promotionAuthorized": False,
                "trainerProcessLivenessVerified": False, "evaluationVerified": False,
                "artifactIntegrityVerified": False, "proofVerified": False})
        overall = ("CLOCK_SKEW" if any(r["state"] == "CLOCK_SKEW" for r in rows) else
                   "STALE" if any(r["state"] == "STALE" for r in rows) else
                   "PARTIAL" if any(r["state"] == "UNAVAILABLE" for r in rows) else "OBSERVED")
        return {"schema": SCHEMA, "available": True, "state": overall,
            "evaluatedAt": iso(now), "sourceObservedAt": iso(source_observed),
            "reportSha256": hashlib.sha256(raw).hexdigest(), "sourceKind": "LOCAL_FILE_OBSERVATION",
            "signatureVerified": False, "producerAuthenticated": False,
            "durableRetentionVerified": False, "trainingCompleteVerified": False,
            "promotionAuthorized": False, "trainerProcessLivenessVerified": False,
            "authority": dict(AUTHORITY), "returned": len(rows), "candidates": rows}
    except (KeyError, TypeError, ValueError, UnicodeError, RecursionError, OverflowError) as exc:
        raise ObservationError("INVALID_OBSERVATION") from exc


class FileObservation:
    """A fixed external input; no writes, network client, cache, or durable store."""

    def __init__(self, configured):
        self.path = None
        self.reason = "NOT_CONFIGURED"
        if not configured:
            return
        try:
            require(isinstance(configured, str) and len(configured) <= 4096
                    and not configured.startswith(("\\\\", "//"))
                    and "://" not in configured and not any(ord(c) < 32 for c in configured))
            path = Path(configured)
            require(path.is_absolute() and ".." not in path.parts and len(path.parts) <= 32)
            if os.name == "nt":
                require(len(path.drive) == 2 and path.drive[1] == ":"
                        and ":" not in str(path)[2:])
            self.path = path
            self.reason = None
        except (ObservationError, OSError, ValueError):
            self.reason = "INVALID_SOURCE_CONFIG"

    def read(self):
        if self.path is None:
            raise ObservationError(self.reason)
        path = self.path
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NONBLOCK", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0)
        before = None
        if os.name == "nt":
            for part in (*reversed(path.parents), path):
                info = part.lstat()
                require(not stat.S_ISLNK(info.st_mode)
                        and not getattr(info, "st_file_attributes", 0) & 0x400)
            before = path.stat()
            require(stat.S_ISREG(before.st_mode) and 0 < before.st_size <= MAX_BYTES)
            fd = os.open(path, flags)
        else:
            # Retained directory handles prevent an ancestor being swapped to
            # a symlink between validation and open; O_NOFOLLOW alone protects
            # only the final component. Nonblocking open also refuses FIFOs.
            require(hasattr(os, "O_NOFOLLOW") and hasattr(os, "O_DIRECTORY"))
            directory = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY)
            try:
                for component in path.parts[1:-1]:
                    child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                                    dir_fd=directory)
                    os.close(directory)
                    directory = child
                fd = os.open(path.name, flags, dir_fd=directory)
            finally:
                os.close(directory)
        with os.fdopen(fd, "rb") as stream:
            opened = os.fstat(stream.fileno())
            require(stat.S_ISREG(opened.st_mode) and 0 < opened.st_size <= MAX_BYTES)
            if os.name == "nt":
                require((before.st_dev, before.st_ino) == (opened.st_dev, opened.st_ino))
                import ctypes
                import msvcrt
                kernel = ctypes.WinDLL("kernel32", use_last_error=True)
                final_path = kernel.GetFinalPathNameByHandleW
                final_path.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32]
                final_path.restype = ctypes.c_uint32
                buf = ctypes.create_unicode_buffer(32768)
                size = final_path(msvcrt.get_osfhandle(stream.fileno()), buf, len(buf), 0)
                require(0 < size < len(buf))
                resolved = buf.value.removeprefix("\\\\?\\")
                require(os.path.normcase(resolved) == os.path.normcase(str(path)))
            raw = stream.read(MAX_BYTES + 1)
            after = os.fstat(stream.fileno())
            require((opened.st_size, opened.st_mtime_ns) == (after.st_size, after.st_mtime_ns)
                    and 0 < len(raw) <= MAX_BYTES)
        return raw


def unavailable(reason):
    return {"schema": SCHEMA, "available": False, "state": "UNAVAILABLE", "reason": reason,
            "returned": None, "candidates": [], "authority": dict(AUTHORITY),
            "trainingCompleteVerified": False, "promotionAuthorized": False}


def _reply(request, body, status=200, headers=None):
    response = JSONResponse(body, status_code=status, headers={**HEADERS, **(headers or {})})
    if request.method == "HEAD":
        response.body = b""
    return response


def _admit(request):
    from szl_operator_auth import operator_refusal
    refusal = operator_refusal(request, "Private training observations")
    if refusal is not None:
        return refusal
    from a11oy_code_runloop import _tenant_refusal
    return _tenant_refusal(request)


def preflight(app):
    intended = {API, API + "/{rest:path}"}
    old = [r for r in app.routes if getattr(r, "path", None) in intended]
    if old and not (len(old) == len(intended) and {r.path for r in old} == intended
                   and all(getattr(r.endpoint, "__module__", None) == __name__
                           and r.methods == METHODS for r in old)):
        raise RuntimeError("TRAINING_OBSERVATION_ROUTE_COLLISION")
    return bool(old)


def register(app):
    if preflight(app):
        return {"state": "READ_ONLY", "alreadyRegistered": True}
    source = FileObservation(os.environ.get(FILE_ENV))
    router = APIRouter()

    @router.api_route(API, methods=sorted(METHODS), include_in_schema=False)
    def observations(request: Request) -> Response:
        if request.method not in ("GET", "HEAD"):
            return _reply(request, {"state": "METHOD_NOT_ALLOWED"}, 405, {"Allow": "GET, HEAD"})
        try:
            refusal = _admit(request)
        except Exception:
            return _reply(request, unavailable("ADMISSION_UNAVAILABLE"), 503)
        if refusal is not None:
            refusal.headers.update(HEADERS)
            if request.method == "HEAD":
                refusal.body = b""
            return refusal
        if request.url.query or request.headers.get("transfer-encoding") or request.headers.get("content-length", "0") != "0":
            return _reply(request, unavailable("REQUEST_OVERRIDES_REFUSED"), 400)
        try:
            raw = source.read()
            body = project(raw, now=datetime.now(timezone.utc))
            return _reply(request, body)
        except ObservationError as exc:
            reason = str(exc) if str(exc) in ("NOT_CONFIGURED", "INVALID_SOURCE_CONFIG") else "INVALID_OBSERVATION"
            return _reply(request, unavailable(reason), 503)
        except OSError:
            return _reply(request, unavailable("SOURCE_UNAVAILABLE"), 503)

    @router.api_route(API + "/{rest:path}", methods=sorted(METHODS), include_in_schema=False)
    def unmatched(request: Request) -> Response:
        return _reply(request, {"state": "NOT_FOUND"}, 404)

    app.router.routes[0:0] = router.routes
    return {"state": "READ_ONLY", "authority": dict(AUTHORITY)}
