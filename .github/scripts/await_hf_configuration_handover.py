#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Observe a completed configuration restart before canonical publication.

Capture the serving process before configuration writes. If the existing
configuration owners report a write, wait for a different, stable process and
a later clean writer epoch serving the same prepublication source. This helper
only performs fixed-origin GETs; it cannot restart, release, claim or publish.
"""

from __future__ import annotations

import argparse
from functools import lru_cache
import importlib.util
import json
import math
from pathlib import Path
import re
import time
from typing import Any, Callable, Mapping
import urllib.request


ORIGIN = "https://szlholdings-a11oy.hf.space"
SPACE = "SZLHOLDINGS/a11oy"
BASELINE_SCHEMA = "szl.hf-configuration-handover-baseline/v1"
RESULT_SCHEMA = "szl.hf-configuration-handover/v1"
PATHS = ("/api/build-info", "/api/a11oy/v1/series-a/status",
         "/api/a11oy/v1/storage/status")
REPORT_SCHEMAS = {"szl.hf-series-a-runtime-config/v1", "szl.hf-gdw-runtime-config/v1"}
MAX_BYTES = 1024 * 1024
REQUEST_SECONDS = 5
CAPTURE_SECONDS = 30
TIMEOUT_SECONDS = 600
BASELINE_MAX_AGE_SECONDS = 900
POLL_SECONDS = 10
REQUIRED_CONSECUTIVE = 3
ROLES = {"WRITER", "RELEASED", "HANDING_OVER", "FENCED", "BLOCKED"}
LEASE_STATES = {"ACTIVE", "HANDOVER_REQUESTED", "RELEASED"}
CLAIMS = {"CLEAN", "UNCLEAN_HANDOVER", "FIRST_BOOT"}
IDENTITY_FIELDS = {"source_revision", "runtime_boot_id", "storage_epoch", "storage_claim",
                   "storage_role", "storage_lease_state", "storage_writable"}
BASELINE_FIELDS = IDENTITY_FIELDS | {"schema", "origin", "observed_at_unix",
                                     "provider_writes_performed", "signature_status"}


class HandoverBlocked(RuntimeError):
    """Only fixed diagnostics cross the CLI boundary."""


def require(condition: bool, code: str) -> None:
    if condition is not True:
        raise HandoverBlocked(code)


def _positive_integer(value: Any) -> bool:
    return type(value) is int and value > 0


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "JSON_DUPLICATE_KEY")
        result[key] = value
    return result


def _reject_constant(_value):
    raise ValueError()


def _json(raw: bytes) -> dict[str, Any]:
    require(len(raw) <= MAX_BYTES, "JSON_BODY_TOO_LARGE")
    try:
        value = json.loads(raw, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    except Exception:
        raise HandoverBlocked("JSON_BODY_INVALID") from None
    require(type(value) is dict, "JSON_OBJECT_REQUIRED")
    return value


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


class ReadOnlyTransport:
    def __init__(self, origin: str, *, opener=None, clock=time.monotonic):
        require(origin == ORIGIN, "CANONICAL_ORIGIN_REQUIRED")
        self.origin, self.clock = origin, clock
        self.opener = opener or urllib.request.build_opener(_NoRedirect())

    def __call__(self, path: str, deadline: float) -> dict[str, Any]:
        require(path in PATHS, "FIXED_READ_ROUTE_REQUIRED")
        remaining = deadline - self.clock()
        require(remaining > 0, "READ_DEADLINE_EXHAUSTED")
        request = urllib.request.Request(self.origin + path, method="GET", headers={
            "Accept": "application/json", "Accept-Encoding": "identity",
            "Cache-Control": "no-store",
        })
        try:
            with self.opener.open(request, timeout=min(REQUEST_SECONDS, remaining)) as response:
                require(response.status == 200, "READ_HTTP_UNAVAILABLE")
                require(response.geturl() == self.origin + path, "READ_REDIRECT_REFUSED")
                require(response.headers.get_content_type() == "application/json",
                        "READ_JSON_REQUIRED")
                raw = bytearray()
                while True:
                    require(self.clock() < deadline, "READ_DEADLINE_EXHAUSTED")
                    chunk = response.read1(min(65536, MAX_BYTES + 1 - len(raw)))
                    require(self.clock() < deadline, "READ_DEADLINE_EXHAUSTED")
                    if not chunk:
                        return _json(bytes(raw))
                    raw.extend(chunk)
                    require(len(raw) <= MAX_BYTES, "JSON_BODY_TOO_LARGE")
        except HandoverBlocked:
            raise
        except Exception:
            raise HandoverBlocked("READ_UNAVAILABLE") from None


@lru_cache(maxsize=1)
def _relock():
    path = Path(__file__).with_name("verify_canonical_a11oy.py")
    spec = importlib.util.spec_from_file_location("_configuration_handover_relock", path)
    require(spec is not None and spec.loader is not None, "STORAGE_VALIDATOR_UNAVAILABLE")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _identity(build: Mapping, series: Mapping, storage: Mapping, *,
              require_ready: bool = False) -> dict[str, Any]:
    try:
        source = build["build"]["revision"]
        boot = series["runtime_boot_id"]
        require(type(source) is str and re.fullmatch(r"[0-9a-f]{40}", source) is not None,
                "SOURCE_IDENTITY_INVALID")
        require(series.get("schema") == "szl.series-a-status/v1"
                and series.get("source_revision") == source
                and type(boot) is str and re.fullmatch(r"boot_[0-9a-f]{32}", boot) is not None,
                "PROCESS_IDENTITY_INVALID")
        claim = storage.get("claim")
        role, lease = storage.get("role"), storage.get("lease")
        require(storage.get("schema") == "szl.a11oy-storage-status/v2"
                and storage.get("mode") == "FENCED" and storage.get("unfenced") is False
                and _positive_integer(storage.get("epoch"))
                and type(claim) is str and claim in CLAIMS
                and type(role) is str and role in ROLES
                and type(storage.get("writable")) is bool
                and type(lease) is dict and type(lease.get("state")) is str
                and lease["state"] in LEASE_STATES, "STORAGE_IDENTITY_INVALID")
        if require_ready:
            _relock().validate_state_store_status(storage)
            require(storage.get("active_errors") == {}, "STORAGE_ERRORS_UNRESOLVED")
        return {"source_revision": source, "runtime_boot_id": boot,
                "storage_epoch": storage["epoch"], "storage_claim": claim,
                "storage_role": role, "storage_lease_state": lease["state"],
                "storage_writable": storage["writable"]}
    except HandoverBlocked:
        raise
    except Exception:
        raise HandoverBlocked("RUNTIME_OBSERVATION_INVALID") from None


def observe(fetch: Callable, deadline: float, *, require_ready: bool = False) -> dict[str, Any]:
    # Reject process or storage identities that change across bracketed reads.
    first = _identity(*(fetch(path, deadline) for path in PATHS), require_ready=require_ready)
    second = _identity(*(fetch(path, deadline) for path in PATHS), require_ready=require_ready)
    require(first == second, "RUNTIME_IDENTITY_CHANGED_DURING_READ")
    return second


def capture(fetch: Callable, *, clock=time.monotonic, wall_clock=time.time) -> dict[str, Any]:
    identity = observe(fetch, clock() + CAPTURE_SECONDS)
    return {"schema": BASELINE_SCHEMA, "origin": ORIGIN,
            "observed_at_unix": int(wall_clock()), **identity,
            "provider_writes_performed": False, "signature_status": "UNSIGNED"}


def validate_baseline(value: Mapping, *, now: float) -> dict[str, Any]:
    require(type(value) is dict and set(value) == BASELINE_FIELDS
            and value.get("schema") == BASELINE_SCHEMA
            and value.get("origin") == ORIGIN
            and value.get("provider_writes_performed") is False
            and value.get("signature_status") == "UNSIGNED", "BASELINE_INVALID")
    require(type(value.get("source_revision")) is str
            and re.fullmatch(r"[0-9a-f]{40}", value["source_revision"]) is not None
            and type(value.get("runtime_boot_id")) is str
            and re.fullmatch(r"boot_[0-9a-f]{32}", value["runtime_boot_id"]) is not None
            and _positive_integer(value.get("storage_epoch"))
            and type(value.get("storage_claim")) is str
            and value["storage_claim"] in CLAIMS
            and type(value.get("storage_role")) is str and value["storage_role"] in ROLES
            and type(value.get("storage_lease_state")) is str
            and value["storage_lease_state"] in LEASE_STATES
            and type(value.get("storage_writable")) is bool,
            "BASELINE_IDENTITY_INVALID")
    stamp = value.get("observed_at_unix")
    require(type(stamp) is int and math.isfinite(now)
            and 0 <= now - stamp <= BASELINE_MAX_AGE_SECONDS, "BASELINE_STALE_OR_INVALID")
    return dict(value)


def configuration_wrote(reports: list[Mapping]) -> bool:
    require(type(reports) is list and len(reports) == 2, "CONFIGURATION_REPORTS_INVALID")
    schemas, wrote = set(), False
    for report in reports:
        require(type(report) is dict, "CONFIGURATION_REPORTS_INVALID")
        schema = report.get("schema")
        require(type(schema) is str and schema in REPORT_SCHEMAS and schema not in schemas
                and report.get("repo_id") == SPACE and report.get("converged") is True
                and report.get("credential_authority_state") == "VERIFIED",
                "CONFIGURATION_REPORTS_INVALID")
        schemas.add(schema)
        changes = report.get("variables_changed")
        require(type(changes) is list and len(changes) <= 256
                and all(type(name) is str and re.fullmatch(r"[A-Z][A-Z0-9_]{0,127}", name)
                        is not None for name in changes)
                and len(set(changes)) == len(changes), "CONFIGURATION_REPORTS_INVALID")
        volume = report.get("volume_changed", False)
        require(type(volume) is bool and (schema != "szl.hf-series-a-runtime-config/v1"
                or "volume_changed" in report), "CONFIGURATION_REPORTS_INVALID")
        wrote = wrote or bool(changes) or volume
    return wrote


def await_handover(fetch: Callable, baseline: Mapping, reports: list[Mapping], *,
                   clock=time.monotonic, wall_clock=time.time, sleep=time.sleep,
                   timeout: float = TIMEOUT_SECONDS) -> dict[str, Any]:
    baseline = validate_baseline(baseline, now=wall_clock())
    wrote = configuration_wrote(reports)
    result = {"schema": RESULT_SCHEMA, "origin": ORIGIN, "configuration_wrote": wrote,
              "baseline": baseline, "provider_writes_performed": False,
              "signature_status": "UNSIGNED", "publication_performed": False}
    if not wrote:
        return dict(result, state="NOT_REQUIRED", waited=False, polls=0)
    require(type(timeout) in {int, float} and math.isfinite(timeout)
            and 0 < timeout <= TIMEOUT_SECONDS, "WAIT_BOUND_INVALID")
    deadline = clock() + timeout
    streak, polls, previous = 0, 0, None
    while clock() < deadline:
        polls += 1
        try:
            current = observe(fetch, deadline, require_ready=True)
            require(current["source_revision"] == baseline["source_revision"],
                    "CONFIGURATION_SOURCE_CHANGED")
            require(current["runtime_boot_id"] != baseline["runtime_boot_id"]
                    and current["storage_epoch"] > baseline["storage_epoch"],
                    "NEW_CONFIGURATION_PROCESS_REQUIRED")
            require(current["storage_claim"] == "CLEAN", "CLEAN_CONFIGURATION_HANDOVER_REQUIRED")
            streak = streak + 1 if current == previous else 1
            previous = current
            if streak >= REQUIRED_CONSECUTIVE:
                return dict(result, state="CONFIGURATION_HANDOVER_OBSERVED", waited=True,
                            polls=polls, observation=current,
                            observed_at_unix=int(wall_clock()))
        except HandoverBlocked:
            streak, previous = 0, None
        remaining = deadline - clock()
        if remaining > 0:
            sleep(min(POLL_SECONDS, remaining))
    raise HandoverBlocked("CONFIGURATION_HANDOVER_NOT_OBSERVED")


def read_document(path: str) -> dict[str, Any]:
    try:
        with Path(path).open("rb") as stream:
            return _json(stream.read(MAX_BYTES + 1))
    except Exception:
        raise HandoverBlocked("LOCAL_OBSERVATION_DOCUMENT_INVALID") from None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("capture", "wait"))
    parser.add_argument("--origin", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--baseline")
    parser.add_argument("--report", action="append", default=[])
    args = parser.parse_args(argv)
    try:
        transport = ReadOnlyTransport(args.origin)
        if args.mode == "capture":
            require(args.baseline is None and not args.report, "CAPTURE_ARGUMENTS_INVALID")
            report = capture(transport)
        else:
            require(args.baseline is not None, "BASELINE_REQUIRED")
            report = await_handover(transport, read_document(args.baseline),
                                   [read_document(path) for path in args.report])
        exit_code = 0
    except HandoverBlocked as error:
        report = {"schema": RESULT_SCHEMA, "state": "BLOCKED", "diagnostic_code": str(error),
                  "provider_writes_performed": False, "signature_status": "UNSIGNED",
                  "publication_performed": False}
        exit_code = 1
    except Exception:
        report = {"schema": RESULT_SCHEMA, "state": "BLOCKED",
                  "diagnostic_code": "CONFIGURATION_OBSERVATION_UNAVAILABLE",
                  "provider_writes_performed": False, "signature_status": "UNSIGNED",
                  "publication_performed": False}
        exit_code = 1
    encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
    try:
        Path(args.output).write_text(encoded, encoding="utf-8")
    except Exception:
        print('{"state":"BLOCKED","diagnostic_code":"OBSERVATION_OUTPUT_UNAVAILABLE"}')
        return 1
    print(encoded, end="")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
