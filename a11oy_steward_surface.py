#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Services layer: a fixed, pinned public Steward projection, without effectors."""

import hashlib
import json
import re
import stat
import types
from pathlib import Path

from fastapi.responses import JSONResponse

BASE = Path(__file__).absolute().parent
PREFIX = "/api/a11oy/v1/steward"
LOCK_PATH = BASE / "steward-source-lock.json"
MODULE_PATH = BASE / "steward_public.py"
PROJECTION_PATH = BASE / "steward-public.json"
REPOSITORY = "szl-holdings/szl-estate-os"
LOCK_SCHEMA = "szl.frontier-steward.dependency/v1"
MAX_LOCK_BYTES = 4096
MAX_MODULE_BYTES = 256 * 1024
HEADERS = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}
_LOCK_KEYS = {
    "schema_version", "repository", "revision", "module_sha256", "projection_sha256"
}


class PackageError(ValueError):
    """A fixed public package binding is missing or invalid."""


class GetOnlySteward:
    """Reserve the public read namespace; never delegate it to the legacy proxy."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        path = scope.get("path", "")
        reserved = path == PREFIX or path.startswith(PREFIX + "/")
        if reserved and scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 1008})
            return
        if reserved and scope["type"] == "http":
            method_denied = scope.get("method") != "GET"
            unknown = path not in {PREFIX + "/status", PREFIX + "/proposals"}
            if method_denied or unknown:
                response = JSONResponse(
                    {"state": "METHOD_NOT_ALLOWED" if method_denied else "NOT_FOUND",
                     "production_ready": False, "scope": "PUBLIC_READ_ONLY",
                     "mutation_policy": "PROPOSAL_ONLY"},
                    status_code=405 if method_denied else 404,
                    headers={**HEADERS, **({"Allow": "GET"} if method_denied else {})},
                )
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)


def _regular_bytes(path, limit):
    # Refuse reparse-point ancestors as well as symlinks; a fixed name must not
    # become an indirect path into a private volume or filesystem cache.
    if not path.is_absolute() or path.parent != BASE:
        raise PackageError("INVALID_PACKAGE_PATH")
    for part in (path, *path.parents):
        info = part.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise PackageError("INDIRECT_PACKAGE_PATH")
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
        raise PackageError("INVALID_PACKAGE_FILE")
    with path.open("rb") as stream:
        value = stream.read(limit + 1)
    if len(value) > limit:
        raise PackageError("PACKAGE_FILE_TOO_LARGE")
    return value


def _unique_object(items):
    result = {}
    for key, value in items:
        if key in result:
            raise PackageError("DUPLICATE_LOCK_KEY")
        result[key] = value
    return result


def _reject_constant(_value):
    raise PackageError("INVALID_LOCK_NUMBER")


def _lock():
    raw = _regular_bytes(LOCK_PATH, MAX_LOCK_BYTES)
    try:
        value = json.loads(
            raw.decode("utf-8"), object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise PackageError("INVALID_PACKAGE_LOCK") from exc
    if type(value) is not dict or set(value) != _LOCK_KEYS:
        raise PackageError("INVALID_PACKAGE_LOCK")
    if value["schema_version"] != LOCK_SCHEMA or value["repository"] != REPOSITORY:
        raise PackageError("INVALID_PACKAGE_LOCK")
    if type(value["revision"]) is not str or not re.fullmatch(r"[0-9a-f]{40}", value["revision"]):
        raise PackageError("INVALID_PACKAGE_LOCK")
    for key in ("module_sha256", "projection_sha256"):
        if type(value[key]) is not str or not re.fullmatch(r"[0-9a-f]{64}", value[key]):
            raise PackageError("INVALID_PACKAGE_LOCK")
    return value, hashlib.sha256(raw).hexdigest()


def _initialize():
    lock, lock_hash = _lock()
    source = _regular_bytes(MODULE_PATH, MAX_MODULE_BYTES)
    if hashlib.sha256(source).hexdigest() != lock["module_sha256"]:
        raise PackageError("SOURCE_MODULE_PIN_MISMATCH")
    # The source bytes are a fixed reviewed dependency, verified before package
    # initialization. Do not use import resolution, unverified .pyc, or reload
    # code from a GET. No caller can provide a source, path, or program.
    reader = types.ModuleType("a11oy_steward_public_pinned")
    reader.__file__ = str(MODULE_PATH)
    exec(compile(source, str(MODULE_PATH), "exec"), reader.__dict__)
    if not callable(getattr(reader, "load_public_projection", None)):
        raise PackageError("INVALID_SOURCE_MODULE")
    return {"lock": lock, "lock_hash": lock_hash, "reader": reader}


def _binding(package):
    lock, lock_hash = _lock()
    if lock_hash != package["lock_hash"] or lock != package["lock"]:
        raise PackageError("PACKAGE_LOCK_CHANGED")
    if hashlib.sha256(_regular_bytes(MODULE_PATH, MAX_MODULE_BYTES)).hexdigest() != lock["module_sha256"]:
        raise PackageError("SOURCE_MODULE_PIN_MISMATCH")
    return lock


def _snapshot(package):
    if package is None:
        return {"valid": False, "state": "UNAVAILABLE", "projection": None,
                "reason": "PACKAGE_INITIALIZATION_UNAVAILABLE"}
    try:
        lock = _binding(package)
        result = package["reader"].load_public_projection(
            PROJECTION_PATH,
            expected_source_revision=lock["revision"],
            expected_sha256=lock["projection_sha256"],
            allowed_directory=BASE,
        )
        _binding(package)
        if (type(result) is not dict or type(result.get("valid")) is not bool
                or result.get("state") not in {"CURRENT", "STALE", "INVALID", "UNAVAILABLE"}):
            raise PackageError("INVALID_READER_RESULT")
        if not result["valid"]:
            return {"valid": False,
                    "state": "UNAVAILABLE" if result["state"] == "UNAVAILABLE" else "INVALID",
                    "projection": None,
                    "reason": "PUBLIC_PROJECTION_UNAVAILABLE"}
        projection = result.get("projection")
        if type(projection) is not dict or result["state"] not in {"CURRENT", "STALE"}:
            raise PackageError("INVALID_READER_RESULT")
        if (projection.get("production_ready") is not False
                or not {"projected_at", "freshness", "plan", "audit", "integrity", "provider", "proposals"}
                <= projection.keys() or type(projection["proposals"]) is not list):
            raise PackageError("INVALID_READER_RESULT")
        return {"valid": True, "state": result["state"], "projection": projection,
                "reason": "PUBLIC_PROJECTION_CURRENT" if result["state"] == "CURRENT"
                else "PUBLIC_PROJECTION_STALE"}
    except FileNotFoundError:
        return {"valid": False, "state": "UNAVAILABLE", "projection": None,
                "reason": "PACKAGE_FILE_MISSING"}
    except Exception:
        return {"valid": False, "state": "INVALID", "projection": None,
                "reason": "PACKAGE_BINDING_INVALID"}


def _response(snapshot, package, include_proposals):
    current = snapshot["valid"] and snapshot["state"] == "CURRENT"
    body = {
        "schema_version": "szl.a11oy.steward.surface/v1",
        "state": snapshot["state"],
        "snapshot_current": current,
        "reason": snapshot["reason"],
        "scope": "PUBLIC_READ_ONLY",
        "mutation_policy": "PROPOSAL_ONLY",
        "production_ready": False,
        "model_invoked": False,
        "provider_calls": 0,
        "effectors": 0,
        "storage_writes": 0,
        "source": {"repository": REPOSITORY,
                   "revision": package["lock"]["revision"] if package else None},
        "snapshot": None,
    }
    if snapshot["valid"]:
        projection = snapshot["projection"]
        body["snapshot"] = {
            key: projection[key] for key in
            ("projected_at", "freshness", "plan", "audit", "integrity", "provider")
        }
    if include_proposals:
        body["proposals"] = snapshot["projection"]["proposals"] if current else []
    return JSONResponse(body, status_code=200 if current else 503, headers=HEADERS)


def register(app):
    """Register only fixed GET readers, ahead of existing proxy/SPA fallbacks."""
    if getattr(app.state, "steward_surface_registered", False):
        return {"registered": True, "read_only": True, "production_ready": False}
    try:
        package = _initialize()
    except Exception:
        package = None
    def status():
        return _response(_snapshot(package), package, False)

    def proposals():
        return _response(_snapshot(package), package, True)

    existing = len(app.router.routes)
    # Direct registrations remain visible to assembled-app route inventory on
    # versions that defer included APIRouters behind a wrapper.
    app.add_api_route(PREFIX + "/status", status, methods=["GET"])
    app.add_api_route(PREFIX + "/proposals", proposals, methods=["GET"])
    added = app.router.routes[existing:]
    del app.router.routes[existing:]
    app.router.routes[0:0] = added
    app.add_middleware(GetOnlySteward)
    app.state.steward_surface_registered = True
    return {"registered": True, "read_only": True, "production_ready": False,
            "route_count": len(added)}
