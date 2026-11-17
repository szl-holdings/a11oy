#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Collect and evaluate bounded, unsigned runtime observations.

This tools-layer adapter does not approve a release. Endpoint statements are
self-reports, not verified signatures, source-byte binding, or hardware evidence.
The existing release controller must qualify those independent evidence classes.
Only GETs are performed. An optional MCP GET may refresh the server's inventory
cache; its result is retained separately and cannot repair the passive baseline.
"""
from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from http.client import HTTPException
from pathlib import Path
from typing import Any, Callable, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

try:
    from .szl_release_guard import ContractError, canonical, digest, immutable_json, strict_json
except ImportError:
    from szl_release_guard import ContractError, canonical, digest, immutable_json, strict_json

SNAPSHOT_SCHEMA = "szl.runtime-observation-snapshot/v1"
REPORT_SCHEMA = "szl.runtime-observation-report/v1"
SCOPE = "RUNTIME_OBSERVATION"
MAX_BODY_BYTES = 256_000
MAX_SNAPSHOT_BYTES = 5_000_000
MAX_OBSERVATION_AGE_S = 120
CLOCK_SKEW_S = 5
MAX_SIGNER_AGE_S = 60
MAX_MCP_AGE_S = 30
ROUTES = (
    ("healthz_baseline", "/api/a11oy/healthz"),
    ("health_baseline", "/api/health"),
    ("livez", "/api/livez"),
    ("build_info", "/api/build-info"),
    ("storage", "/api/a11oy/v1/storage/status"),
    ("brain", "/api/a11oy/v1/brain/capabilities"),
    ("source", "/.well-known/szl-source.json"),
    ("health_final", "/api/health"),
    ("healthz_final", "/api/a11oy/healthz"),
)
ACTIVE_ROUTES = (
    ("mcp_active", "/api/a11oy/v1/mcp/tools"),
    ("healthz_after_probe", "/api/a11oy/healthz"),
)
STORES = frozenset(("gdw", "series_a", "khipu", "khipu_council", "unay",
                    "khipu_lmdb", "khipu_repl"))
CAPABILITY_STATES = frozenset(("OPERATIONAL", "PARTIALLY OPERATIONAL", "MODELED",
                              "SIMULATED", "EXPERIMENTAL", "UNAVAILABLE"))
BOUNDARIES = {
    "release_approval": "NOT_EVALUATED",
    "signature_verification": "NOT_EVALUATED",
    "source_byte_binding": "NOT_EVALUATED",
    "image_attestation": "NOT_EVALUATED",
    "hardware_attestation": "NOT_EVALUATED",
    "execution_authority": "NONE",
}


def _object(value: Any, field: str) -> dict[str, Any]:
    if type(value) is not dict:
        raise ContractError(field + ":OBJECT_REQUIRED")
    return value


def _list(value: Any, field: str) -> list[Any]:
    if type(value) is not list:
        raise ContractError(field + ":ARRAY_REQUIRED")
    return value


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractError(field + ":NONEMPTY_STRING_REQUIRED")
    return value


def _boolean(value: Any, field: str) -> bool:
    if type(value) is not bool:
        raise ContractError(field + ":BOOLEAN_REQUIRED")
    return value


def _number(value: Any, field: str, *, positive: bool = False) -> float:
    if type(value) not in (int, float):
        raise ContractError(field + ":FINITE_NUMBER_REQUIRED")
    try:
        finite = math.isfinite(value)
    except OverflowError as exc:
        raise ContractError(field + ":NUMBER_OUT_OF_RANGE") from exc
    if not finite:
        raise ContractError(field + ":FINITE_NUMBER_REQUIRED")
    if value < 0 or (positive and value == 0):
        raise ContractError(field + ":NUMBER_OUT_OF_RANGE")
    return float(value)


def _integer(value: Any, field: str) -> int:
    if type(value) is not int or value < 0:
        raise ContractError(field + ":NONNEGATIVE_INTEGER_REQUIRED")
    return value


def _timestamp(value: Any, field: str) -> datetime:
    value = _text(value, field)
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContractError(field + ":INVALID_TIMESTAMP") from exc
    if result.tzinfo is None or result.utcoffset() != timedelta(0):
        raise ContractError(field + ":UTC_TIMESTAMP_REQUIRED")
    return result


def _sha(value: Any, size: int, field: str) -> str:
    if not isinstance(value, str) or re.fullmatch("[0-9a-f]{" + str(size) + "}", value) is None:
        raise ContractError(field + ":INVALID_SHA")
    return value


def _strings(value: Any, field: str) -> list[str]:
    return [_text(item, field) for item in _list(value, field)]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class Target:
    base_url: str
    repository: str
    source_revision: str
    signer_fingerprint: str

    def validate(self) -> None:
        _text(self.base_url, "TARGET_BASE_URL")
        try:
            url = urlsplit(self.base_url)
            url.port
        except ValueError as exc:
            raise ContractError("TARGET:INVALID_URL") from exc
        if (url.scheme != "https" or not url.hostname or url.username is not None
                or url.password is not None or url.query or url.fragment
                or self.base_url != url.scheme + "://" + url.netloc):
            raise ContractError("TARGET:HTTPS_ORIGIN_REQUIRED")
        if not isinstance(self.repository, str) or re.fullmatch(
                r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", self.repository) is None:
            raise ContractError("TARGET:INVALID_REPOSITORY")
        _sha(self.source_revision, 40, "TARGET_SOURCE")
        _sha(self.signer_fingerprint, 64, "TARGET_SIGNER")


@dataclass(frozen=True)
class Finding:
    severity: str
    observation: str
    code: str


@dataclass(frozen=True)
class Observation:
    name: str
    captured_at: datetime
    body: dict[str, Any]
    metadata: dict[str, Any]


class Checks:
    def __init__(self) -> None:
        self.findings: list[Finding] = []

    def blocked(self, name: str, code: str) -> None:
        self.findings.append(Finding("BLOCKED", name, code))

    def error(self, name: str, code: str) -> None:
        self.findings.append(Finding("ERROR", name, code))

    def require(self, condition: bool, name: str, code: str) -> None:
        if not condition:
            self.blocked(name, code)

    def run(self, name: str, check: Callable[[], None]) -> None:
        try:
            check()
        except ContractError as exc:
            self.error(name, str(exc))
        except KeyError as exc:
            self.error(name, str(exc.args[0]) + ":MISSING_FIELD")


def _cached_age(body: dict[str, Any], *, at: datetime, stamp: str, age: str,
                maximum: str, limit: float, name: str, checks: Checks) -> None:
    observed = _timestamp(body[stamp], stamp)
    reported = _number(body[age], age)
    claimed_limit = _number(body[maximum], maximum, positive=True)
    elapsed = (at - observed).total_seconds()
    checks.require(-CLOCK_SKEW_S <= elapsed <= min(claimed_limit, limit),
                   name, "CACHED_OBSERVATION_EXPIRED_OR_FUTURE")
    checks.require(reported <= min(claimed_limit, limit),
                   name, "REPORTED_CACHE_AGE_EXPIRED")
    checks.require(abs(elapsed - reported) <= CLOCK_SKEW_S,
                   name, "CACHE_TIMESTAMP_AGE_DISAGREEMENT")


def _signer(observation: Observation, target: Target, checks: Checks) -> None:
    name, body = observation.name, observation.body
    checks.require(body["status"] == "ok", name, "PROCESS_HEALTH_NOT_OK")
    signer = _object(body["signing_state"], "signing_state")
    if signer["schema"] != "szl.signing-state/v1":
        raise ContractError("signing_state:UNSUPPORTED_SCHEMA")
    _text(signer["runtime_boot_id"], "runtime_boot_id")
    checks.require(_boolean(signer["signing_ready"], "signing_ready"),
                   name, "SIGNING_NOT_READY")
    checks.require(signer["freshness"] == "FRESH", name, "SIGNER_NOT_FRESH")
    _cached_age(signer, at=observation.captured_at, stamp="observed_at",
                age="age_seconds", maximum="max_age_seconds",
                limit=MAX_SIGNER_AGE_S, name=name, checks=checks)
    # expected_key_fingerprint is never an observed fingerprint.
    for field in ("public_key_fingerprint", "loaded_key_fingerprint"):
        value = signer.get(field)
        checks.require(value is not None, name, field.upper() + "_NOT_OBSERVED")
        if value is not None:
            checks.require(_sha(value, 64, field) == target.signer_fingerprint,
                           name, field.upper() + "_MISMATCH")
    checks.require(signer["key_agreement"] == "MATCH", name, "SIGNER_KEY_DISAGREEMENT")
    checks.require(_text(signer["key_source"], "key_source").startswith("persistent:"),
                   name, "PERSISTENT_SIGNER_NOT_REPORTED")
    checks.require(not _strings(signer["blockers"], "signer.blockers"),
                   name, "SIGNER_BLOCKERS_REPORTED")
    capability = _object(signer["observed_capability"], "observed_capability")
    evidence = _object(capability["evidence"], "observed_capability.evidence")
    checks.require(_boolean(evidence["verified"], "selftest.verified"),
                   name, "SIGNER_SELFTEST_NOT_REPORTED_VERIFIED")
    selftest_at = _timestamp(evidence["observed_at"], "selftest.observed_at")
    _sha(evidence["payload_digest"], 64, "selftest.payload_digest")
    checks.require(-CLOCK_SKEW_S <= (observation.captured_at - selftest_at).total_seconds()
                   <= min(float(signer["max_age_seconds"]), MAX_SIGNER_AGE_S),
                   name, "SIGNER_SELFTEST_EXPIRED_OR_FUTURE")
    # This records the process assertion only; no signature is verified here.


def _healthz(observation: Observation, target: Target, checks: Checks) -> None:
    name, body = observation.name, observation.body
    checks.require(body["status"] == "ok", name, "SERVICE_HEALTH_NOT_OK")
    identity = _object(body["runtime_identity"], "runtime_identity")
    checks.require(identity["source_repository"] == target.repository,
                   name, "SOURCE_REPOSITORY_MISMATCH")
    checks.require(identity["source_revision_state"] == "OBSERVED",
                   name, "SOURCE_REVISION_NOT_OBSERVED")
    checks.require(identity["source_revision"] == target.source_revision,
                   name, "SOURCE_REVISION_MISMATCH")
    readiness = _object(body["operational_readiness"], "operational_readiness")
    ready = _boolean(readiness["ready"], "operational_readiness.ready")
    blockers = _strings(readiness["service_blockers"], "service_blockers")
    frontier = _object(readiness["frontier"], "frontier")
    frontier_ready = _boolean(frontier["ready"], "frontier.ready")
    ready_tiles = _strings(frontier["ready_tiles"], "ready_tiles")
    blocked_tiles = _list(frontier["blocked_tiles"], "blocked_tiles")
    for tile in blocked_tiles:
        tile = _object(tile, "blocked_tile")
        _text(tile["name"], "blocked_tile.name")
        _boolean(tile["ready"], "blocked_tile.ready")
        _strings(tile["reasons"], "blocked_tile.reasons")
    checks.require(readiness["status"] == "READY" and ready and not blockers
                   and frontier["state"] == "READY" and frontier_ready
                   and bool(ready_tiles) and not blocked_tiles,
                   name, "OPERATIONAL_READINESS_NOT_ESTABLISHED")
    inventory = _object(body["mcp_inventory"], "mcp_inventory")
    checks.require(inventory["label"] == "CACHED" and inventory["reason"] is None,
                   name, "MCP_BASELINE_NOT_FRESH")
    checks.require(inventory["source"] == "/api/a11oy/v1/mcp/tools",
                   name, "MCP_SOURCE_UNEXPECTED")
    checks.require(inventory["scope"] == "ADVERTISED_MANIFEST_ONLY",
                   name, "MCP_SCOPE_UNEXPECTED")
    checks.require(_boolean(inventory["capability_readiness_asserted"],
                            "capability_readiness_asserted") is False,
                   name, "MCP_INVENTORY_OVERCLAIM")
    if inventory["count"] is None or inventory["checked_at"] is None or inventory["age_s"] is None:
        checks.blocked(name, "MCP_OBSERVATION_MISSING")
    else:
        checks.require(_integer(inventory["count"], "mcp.count") > 0,
                       name, "MCP_INVENTORY_EMPTY")
        _cached_age(inventory, at=observation.captured_at, stamp="checked_at",
                    age="age_s", maximum="max_age_s", limit=MAX_MCP_AGE_S,
                    name=name, checks=checks)


def _build(observation: Observation, target: Target, checks: Checks) -> None:
    body = observation.body
    build = _object(body["build"], "build")
    checks.require(body["status"] == "OBSERVED" and build["state"] == "OBSERVED",
                   observation.name, "BUILD_IDENTITY_NOT_OBSERVED")
    checks.require(build["revision"] == target.source_revision,
                   observation.name, "SOURCE_REVISION_MISMATCH")
    checks.require(_text(build["revision_source"], "revision_source") != "UNKNOWN",
                   observation.name, "SOURCE_REVISION_ORIGIN_UNKNOWN")


def _source(observation: Observation, target: Target, checks: Checks) -> None:
    body = observation.body
    if body["schema"] != "szl.deployment-source/v1":
        raise ContractError("source:UNSUPPORTED_SCHEMA")
    source = _object(body["source"], "source")
    checks.require(source["repository"] == target.repository
                   and source["commit"] == target.source_revision,
                   observation.name, "DECLARED_SOURCE_TARGET_MISMATCH")
    _text(source["state"], "source.state")
    _text(body["verification_state"], "verification_state")
    # This endpoint never supplies publication_eligible or receipt_minted.
    # STRUCTURAL_ONLY is accurate metadata, not failed cryptographic verification.


def _storage(observation: Observation, checks: Checks) -> None:
    name, body = observation.name, observation.body
    if body["schema"] != "szl.a11oy-storage-status/v2":
        raise ContractError("storage:UNSUPPORTED_SCHEMA")
    writable = _boolean(body["writable"], "writable")
    unfenced = _boolean(body["unfenced"], "unfenced")
    alert = _boolean(body["alert"], "alert")
    checks.require(body["mode"] == "FENCED" and body["role"] == "WRITER"
                   and writable and not unfenced and not alert,
                   name, "STORAGE_WRITER_NOT_HEALTHY")
    checks.require(_integer(body["epoch"], "epoch") > 0, name, "STORAGE_EPOCH_MISSING")
    lease = _object(body["lease"], "lease")
    checks.require(lease["state"] == "ACTIVE", name, "STORAGE_LEASE_NOT_ACTIVE")
    _integer(lease["sequence"], "lease.sequence")
    _number(lease["heartbeat_age_s"], "lease.heartbeat_age_s")
    checks.require(not _object(body["active_errors"], "active_errors"),
                   name, "STORAGE_ACTIVE_ERRORS")
    stores = _object(body["stores"], "stores")
    checks.require(STORES.issubset(stores), name, "REQUIRED_STORES_MISSING")
    for store in stores.values():
        store = _object(store, "store")
        checks.require(store["health"] == "OK" and store["blocked_code"] is None,
                       name, "STORE_NOT_HEALTHY")
    # Historical errors and idle snapshot age are not active storage faults.


def _brain(observation: Observation, checks: Checks) -> None:
    name, body = observation.name, observation.body
    if body["schema"] != "szl.brain-capabilities.v1":
        raise ContractError("brain:UNSUPPORTED_SCHEMA")
    generated = _timestamp(body["generated_at"], "generated_at")
    checks.require(-CLOCK_SKEW_S <= (observation.captured_at - generated).total_seconds()
                   <= MAX_OBSERVATION_AGE_S, name, "BRAIN_OBSERVATION_EXPIRED_OR_FUTURE")
    summary = _object(body["summary"], "summary")
    capabilities = _list(body["capabilities"], "capabilities")
    total = _integer(summary["capabilities_total"], "capabilities_total")
    counts = _object(summary["status_counts"], "status_counts")
    if set(counts) != CAPABILITY_STATES:
        raise ContractError("status_counts:UNSUPPORTED_STATES")
    counts = {key: _integer(value, "status_count") for key, value in counts.items()}
    actual = dict.fromkeys(CAPABILITY_STATES, 0)
    seen = set()
    for item in capabilities:
        item = _object(item, "capability")
        identifier = _text(item["id"], "capability.id")
        status = _text(item["status"], "capability.status")
        if identifier in seen or status not in CAPABILITY_STATES:
            raise ContractError("capability:DUPLICATE_ID_OR_INVALID_STATUS")
        seen.add(identifier)
        actual[status] += 1
        blockers = _strings(item["blockers"], "capability.blockers")
        checks.require(item["status"] == "OPERATIONAL" and not blockers,
                       name, "ADVERTISED_CAPABILITY_NOT_OPERATIONAL")
    if total != len(capabilities) or counts != actual:
        raise ContractError("capabilities:SUMMARY_DISAGREEMENT")
    checks.require(total > 0 and body["overall_status"] == "OPERATIONAL",
                   name, "BRAIN_NOT_OPERATIONAL")


def _decode_observation(raw: Any, expected: tuple[str, str], target: Target,
                        now: datetime, checks: Checks) -> Observation | None:
    raw = _object(raw, "observation")
    name, path = expected
    required = {"name", "path", "url", "captured_at", "http_status", "content_type",
                "body_b64", "body_sha256", "truncated", "error"}
    if set(raw) != required or raw["name"] != name or raw["path"] != path:
        raise ContractError("observation:CONTRACT_OR_ORDER_MISMATCH")
    if raw["url"] != target.base_url + path:
        raise ContractError("observation:URL_TARGET_MISMATCH")
    captured = _timestamp(raw["captured_at"], "captured_at")
    elapsed = (now - captured).total_seconds()
    checks.require(-CLOCK_SKEW_S <= elapsed <= MAX_OBSERVATION_AGE_S,
                   name, "OBSERVATION_EXPIRED_OR_FUTURE")
    truncated = _boolean(raw["truncated"], "truncated")
    try:
        if not isinstance(raw["body_b64"], str):
            raise ContractError("body_b64:STRING_REQUIRED")
        body = base64.b64decode(raw["body_b64"], validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ContractError("body_b64:INVALID_ENCODING") from exc
    if len(body) > MAX_BODY_BYTES:
        raise ContractError("body:BYTES_EXCEEDED")
    if hashlib.sha256(body).hexdigest() != _sha(raw["body_sha256"], 64, "body_sha256"):
        raise ContractError("body:SHA256_MISMATCH")
    if raw["error"] is not None:
        _text(raw["error"], "error")
        checks.error(name, "COLLECTION_FAILED")
        return None
    if type(raw["http_status"]) is not int:
        raise ContractError("http_status:INTEGER_REQUIRED")
    checks.require(raw["http_status"] == 200, name, "HTTP_STATUS_NOT_200")
    if truncated:
        checks.error(name, "BODY_TRUNCATED")
        return None
    media_type = _text(raw["content_type"], "content_type").split(";", 1)[0].lower().strip()
    if media_type != "application/json" and not media_type.endswith("+json"):
        raise ContractError("content_type:JSON_REQUIRED")
    body_json = _object(strict_json(body, limit=MAX_BODY_BYTES), "body")
    return Observation(name, captured, body_json,
                       {key: value for key, value in raw.items() if key != "body_b64"})


def evaluate(snapshot: Any, target: Target, *, now: datetime) -> dict[str, Any]:
    """Pure evaluator; expected identity is supplied independently of the snapshot."""
    checks = Checks()
    observations: dict[str, Observation] = {}
    active: dict[str, Observation] = {}
    snapshot_hash = None

    def decode() -> None:
        nonlocal snapshot_hash
        target.validate()
        _timestamp(_iso(now), "evaluation_time")
        value = _object(snapshot, "snapshot")
        if set(value) != {"schema", "scope", "expected_target", "started_at",
                          "completed_at", "observations", "active_probe"}:
            raise ContractError("snapshot:FIELDS_MISMATCH")
        if value["schema"] != SNAPSHOT_SCHEMA or value["scope"] != SCOPE:
            raise ContractError("snapshot:UNSUPPORTED_SCHEMA_OR_SCOPE")
        if value["expected_target"] != asdict(target):
            raise ContractError("snapshot:TARGET_MISMATCH")
        snapshot_hash = digest(value)
        start = _timestamp(value["started_at"], "started_at")
        end = _timestamp(value["completed_at"], "completed_at")
        if end < start or (end - start).total_seconds() > MAX_OBSERVATION_AGE_S:
            raise ContractError("snapshot:INVALID_CAPTURE_WINDOW")
        items = _list(value["observations"], "observations")
        if len(items) != len(ROUTES):
            raise ContractError("snapshot:REQUIRED_OBSERVATIONS_MISSING")
        previous = start
        groups = [(items, ROUTES, observations)]
        if value["active_probe"] is not None:
            probe = _list(value["active_probe"], "active_probe")
            if len(probe) != len(ACTIVE_ROUTES):
                raise ContractError("active_probe:INCOMPLETE")
            groups.append((probe, ACTIVE_ROUTES, active))
        for rows, expected, destination in groups:
            for raw, route in zip(rows, expected):
                captured = _timestamp(_object(raw, "observation")["captured_at"], "captured_at")
                if not previous <= captured <= end:
                    raise ContractError("snapshot:OBSERVATION_ORDER_INVALID")
                previous = captured
                def read_one() -> None:
                    observation = _decode_observation(raw, route, target, now, checks)
                    if observation is not None:
                        destination[route[0]] = observation
                checks.run(route[0], read_one)

    checks.run("snapshot", decode)
    validators = {
        "healthz_baseline": lambda o: _healthz(o, target, checks),
        "healthz_final": lambda o: _healthz(o, target, checks),
        "health_baseline": lambda o: _signer(o, target, checks),
        "health_final": lambda o: _signer(o, target, checks),
        "livez": lambda o: checks.require(o.body["status"] == "PROCESS_ALIVE",
                                         o.name, "PROCESS_NOT_ALIVE"),
        "build_info": lambda o: _build(o, target, checks),
        "storage": lambda o: _storage(o, checks),
        "brain": lambda o: _brain(o, checks),
        "source": lambda o: _source(o, target, checks),
    }
    for name, observation in observations.items():
        checks.run(name, lambda o=observation, n=name: validators[n](o))
    if "health_baseline" in observations and "health_final" in observations:
        def continuity() -> None:
            first = _object(observations["health_baseline"].body["signing_state"], "signing_state")
            last = _object(observations["health_final"].body["signing_state"], "signing_state")
            checks.require(first["runtime_boot_id"] == last["runtime_boot_id"],
                           "health_final", "RUNTIME_BOOT_CHANGED")
        checks.run("continuity", continuity)
    # A fresh post-probe cache is informative only. It never removes baseline findings.
    active_checks = Checks()
    if "healthz_after_probe" in active:
        active_checks.run("healthz_after_probe",
                          lambda: _healthz(active["healthz_after_probe"], target, active_checks))
    severity = {finding.severity for finding in checks.findings}
    verdict = "ERROR" if "ERROR" in severity else "BLOCKED" if severity else "OBSERVATIONS_PASS"
    return {
        "schema": REPORT_SCHEMA, "scope": SCOPE, "verdict": verdict,
        "evaluated_at": _iso(now), "expected_target": asdict(target),
        "snapshot_canonical_sha256": snapshot_hash,
        "exit_code": 2 if verdict == "ERROR" else 1 if verdict == "BLOCKED" else 0,
        "findings": [asdict(item) for item in checks.findings],
        "observations": [item.metadata for item in observations.values()],
        "active_probe": {
            "performed": bool(active),
            "baseline_replaced": False,
            "findings": [asdict(item) for item in active_checks.findings],
            "observations": [item.metadata for item in active.values()],
        },
        "boundaries": dict(BOUNDARIES),
        "limits": [
            "Unsigned GET response bytes and process assertions only.",
            "Hashes detect byte changes; they do not authenticate a writer or a server.",
            "Matching source declarations do not establish deployed source-byte identity.",
            "Signer self-test status is not independently verified by this evaluator.",
            "Cache age is checked at capture; this is not a continuing availability claim.",
            "The five-second timestamp tolerance includes server clock difference and response latency.",
            "Release registries and status-only receipts are not accepted as observations.",
        ],
    }


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def collect(target: Target, *, active_probe: bool = False,
            opener: Any = None, clock: Callable[[], datetime] = _now) -> dict[str, Any]:
    """Bounded HTTPS GET collector. Baseline always precedes the optional probe."""
    target.validate()
    opener = opener or build_opener(_NoRedirect())
    result = {
        "schema": SNAPSHOT_SCHEMA, "scope": SCOPE, "expected_target": asdict(target),
        "started_at": _iso(clock()), "completed_at": None,
        "observations": [], "active_probe": None,
    }

    def fetch(route: tuple[str, str]) -> dict[str, Any]:
        name, path = route
        body, status, media_type, error, truncated = b"", None, "", None, False
        try:
            request = Request(target.base_url + path, headers={
                "Accept": "application/json", "Cache-Control": "no-cache",
                "User-Agent": "szl-runtime-observation/1",
            }, method="GET")
            try:
                response = opener.open(request, timeout=10)
            except HTTPError as exc:
                response = exc
            with response:
                status = response.status
                media_type = response.headers.get("Content-Type", "")
                if response.geturl() != target.base_url + path:
                    error = "RESPONSE_URL_MISMATCH"
                raw = response.read(MAX_BODY_BYTES + 1)
                truncated = len(raw) > MAX_BODY_BYTES
                body = raw[:MAX_BODY_BYTES]
        except (OSError, URLError, HTTPException, ValueError) as exc:
            error = type(exc).__name__
        return {
            "name": name, "path": path, "url": target.base_url + path,
            "captured_at": _iso(clock()), "http_status": status,
            "content_type": media_type, "body_b64": base64.b64encode(body).decode("ascii"),
            "body_sha256": hashlib.sha256(body).hexdigest(),
            "truncated": truncated, "error": error,
        }

    result["observations"] = [fetch(route) for route in ROUTES]
    if active_probe:
        result["active_probe"] = [fetch(route) for route in ACTIVE_ROUTES]
    result["completed_at"] = _iso(clock())
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("collect", "evaluate"):
        sub = commands.add_parser(command)
        sub.add_argument("--base-url", required=True)
        sub.add_argument("--repository", required=True)
        sub.add_argument("--source-revision", required=True)
        sub.add_argument("--signer-fingerprint", required=True)
        if command == "collect":
            sub.add_argument("--evidence-dir", required=True, type=Path)
            sub.add_argument("--active-mcp-probe", action="store_true")
        else:
            sub.add_argument("--snapshot", required=True, type=Path)
    args = parser.parse_args(argv)
    target = Target(args.base_url, args.repository, args.source_revision, args.signer_fingerprint)
    try:
        target.validate()
        if args.command == "collect":
            snapshot = collect(target, active_probe=args.active_mcp_probe)
            snapshot_path = immutable_json(args.evidence_dir, snapshot)
            snapshot_bytes = canonical(snapshot) + b"\n"
        else:
            with args.snapshot.open("rb") as source:
                snapshot_bytes = source.read(MAX_SNAPSHOT_BYTES + 1)
                snapshot = strict_json(snapshot_bytes, limit=MAX_SNAPSHOT_BYTES)
        report = evaluate(snapshot, target, now=_now())
        report["snapshot_file_sha256"] = hashlib.sha256(snapshot_bytes).hexdigest()
        if args.command == "collect":
            report["snapshot_file"] = str(snapshot_path)
            immutable_json(args.evidence_dir, report)
    except (ContractError, OSError, ValueError) as exc:
        report = {
            "schema": REPORT_SCHEMA, "scope": SCOPE, "verdict": "ERROR", "exit_code": 2,
            "boundaries": dict(BOUNDARIES),
            "findings": [{"severity": "ERROR", "observation": "input",
                          "code": str(exc) if isinstance(exc, ContractError) else type(exc).__name__}],
        }
    print(json.dumps(report, sort_keys=True, indent=2, allow_nan=False))
    return report["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
